"""持ち越しの並び —— **申し送りが時刻を指定している語も、上位に置かないこと。**

## なぜ要るか（2026-08-27 12:3x に踏んだ。**`quota_blocked` の穴**）

`quota_blocked()` は **日枠（16:00）だけ**を見ています。ところが申し送りは
他の時刻でも塞がります。12:3x に始まった回の持ち越しの**上位4件**は
全部これでした:

    4回  09:00 より前も生きるか / PROVEN_FROM_MIN / 生きた本数 / day_cap
         → どれも「**【08/27 14:00 JST 以降の回へ】** その時刻に判定できます」

`docs/trigger_main.md` §2.7 は「持ち越しが出ていたら、そこから選ぶのが既定」と
言っているので、**既定に従うと、その回は何も選べない**ことになります。
`src/alerts.py` が塞ぎに来た「**一覧が当たりを含まないまま育つ**」の同じ形で、
`quota_blocked` が 2026-08-17 に半分だけ塞いでいた残りです。

## 沈めるだけで、消さないこと

時刻が来た回では、逆にこの4件こそがその回でしか打てない仕事です。
だから落とさず、時刻が過ぎたら `None` を返して上へ戻します。
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("retro_clock", ROOT / "scripts" / "retro.py")
retro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retro)

JST = timezone(timedelta(hours=9))


def _block(date: str, lines: list[str]):
    return (date, lines, 0)


BLOCKS = [
    _block("2026-08-27 06:1x", [
        "1. **【08/27 14:00 JST 以降の回へ】** `day_cap` の (A)/(B) は"
        "**その時刻に判定できます**。読むのは `PROVEN_FROM_MIN` を下げないこと。",
        "2. **`topic_forge` の在庫が尽きます。** いつでも打てます。",
    ]),
    _block("2026-08-27 09:2x", [
        "1. **【08/27 14:00 JST 以降の回へ】** 読むのは「`生きた本数`」が11本以上か。"
        "`PROVEN_FROM_MIN` を下げないこと。",
        "2. **`topic_forge` をもう一度。** 未使用の節が0件です。",
    ]),
]

# JST の 12:30 と 15:00
BEFORE = datetime(2026, 8, 27, 12, 30, tzinfo=JST).astimezone(timezone.utc)
AFTER = datetime(2026, 8, 27, 15, 0, tzinfo=JST).astimezone(timezone.utc)


def test_時刻で塞がっている語は沈む():
    got = retro.clock_blocked(BLOCKS, "PROVEN_FROM_MIN", now=BEFORE)
    assert got is not None
    assert 1.4 < got < 1.6          # 12:30 → 14:00 は 1.5時間


def test_時刻が来たら沈まない():
    assert retro.clock_blocked(BLOCKS, "PROVEN_FROM_MIN", now=AFTER) is None


def test_時刻の印が無い項目を含む語は沈まない():
    """**全部が時刻がらみのときだけ沈める**（`quota_blocked` と同じ規則）。"""
    assert retro.clock_blocked(BLOCKS, "topic_forge", now=BEFORE) is None


def test_1件しか言われていない語は沈めない():
    """1件では癖と言えない（`quota_blocked` と同じ）。"""
    one = [BLOCKS[0]]
    assert retro.clock_blocked(one, "PROVEN_FROM_MIN", now=BEFORE) is None


def test_日枠の16時は時刻の印としても読める():
    """**二重に沈めても害はありません**（印は片方だけ出す）。ここは読めることの確認。"""
    blocks = [
        _block("a", ["1. **【16:00 JST 以降の回へ】** `refresh_thumbnail.py --missing`"]),
        _block("b", ["1. **【16:00 JST 以降の回へ】** `refresh_thumbnail.py --missing` を1回"]),
    ]
    at_noon = datetime(2026, 8, 27, 12, 0, tzinfo=JST).astimezone(timezone.utc)
    assert retro.clock_blocked(blocks, "refresh_thumbnail.py --missing", now=at_noon)
    assert retro.quota_blocked(blocks, "refresh_thumbnail.py --missing")


def test_ありえない時刻は読み飛ばす():
    blocks = [
        _block("a", ["1. **【99:99 JST 以降の回へ】** `foo`"]),
        _block("b", ["1. **【99:99 JST 以降の回へ】** `foo`"]),
    ]
    assert retro.clock_blocked(blocks, "foo", now=BEFORE) is None
