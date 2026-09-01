"""**当日の予約は、池の一覧の先頭に出ること。**（2026-09-01・オーナーが画面で踏んだ）

## 何が起きたか（事実だけ）

2026-09-01 16:33 JST、オーナーの YouTube Studio に **09/01 の 18:00 / 19:00 /
20:00 / 21:00 の予約が4本**出ていました。同じ時刻に `scripts/pool_drain.py` を
撃つと、一覧は **09/02 から**しか出ません。**いちばん早い当日の4本が、
外す一覧から丸ごと落ちていました。** 外す順は「公開時刻の早い順」なのに、
**その日に出てしまう本だけが見えない**という形です。
放っておけば当日5本 公開され、**規則1（1日1本）が破れます。**

## 穴の位置（`src/house_rule.is_stockpile()`）

    at = str(row.get("at") or "")[:10]
    if at <= (today or _jst_today()):
        return False                      # もう公開になっている ＝ 実績

**日付の文字列だけを比べていました。** 起きることは2つ:

  1. **まだ来ていない当日の予約**（09/01 18:00 JST を 16:33 に見る）が
     「もう公開になっている ＝ 実績」に倒れ、作り置きから外れる
     → `pool_drain.pool()` が落とす → **一覧に出ない**
  2. `at` は UTC（`2026-09-02T04:00:00Z`）、`today` は JST の日付。
     **物差しが違います。** 09/02 00:30 JST（＝ 09/01 15:30Z）の予約は
     `at[:10] == "2026-09-01"` なので、**翌日の未明ぶんまで同じ穴に落ちます。**

1本ずれではありません。**当日ぶんが構造的に見えない**ので、
「毎日いちばん早い本だけが外し残る」＝ 同じ穴が翌日も開きます。

## この検査が押さえているもの

    1. 当日の未来の予約が、一覧の**先頭**に来ること（外す順は公開の早い順）
    2. 翌日の未明（JST）の予約が、UTC 日付のせいで落ちないこと
    3. 当日でも**もう過ぎた**予約は入らないこと（触らない側は変えない）
    4. 規則の下で作った本（`STOCKPILE_SINCE` 以降）は、当日でも入らないこと
       ＝ `tests/test_pool_drain_keeps_new.py` の約束を壊していないこと

**戻すにはこの検査を消すしかありません。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import pool_drain  # noqa: E402
from src import house_rule  # noqa: E402

JST = timezone(timedelta(hours=9))

#: オーナーが画面を見た瞬間（2026-09-01 16:33 JST）。
NOW = datetime(2026, 9, 1, 16, 33, tzinfo=JST).astimezone(timezone.utc)

#: 規則より前に作った本 ＝ 作り置き。
MADE = "2026-08-20T00:00:00+00:00"


def _row(vid: str, at_jst: datetime, made: str = MADE) -> dict:
    """控え（`data/uploaded.jsonl`）の1行の形。`at` は**控えと同じ UTC の Z 表記**。"""
    return {"id": vid, "video_id": vid, "title": vid, "topic": vid,
            "uploaded_at": made,
            "at": at_jst.astimezone(timezone.utc)
                        .strftime("%Y-%m-%dT%H:%M:%SZ")}


def _at(y: int, m: int, d: int, h: int, mi: int = 0) -> datetime:
    return datetime(y, m, d, h, mi, tzinfo=JST)


def test_当日の予約が一覧の先頭に来る():
    """オーナーが見た4本（18/19/20/21時）＋ 翌日以降。**先頭は当日の18時。**"""
    rows = [_row("d0902", _at(2026, 9, 2, 13)),
            _row("d0904", _at(2026, 9, 4, 13))]
    rows += [_row(f"today{h}", _at(2026, 9, 1, h)) for h in (18, 19, 20, 21)]

    ids = [r["id"] for r in pool_drain.pool(now=NOW, rows=rows)]

    assert ids[:4] == ["today18", "today19", "today20", "today21"], (
        f"池の一覧が {ids} です。**当日の予約が先頭に来ていません。**\n"
        "  外す順は『公開時刻の早い順』——いちばん早いのは当日ぶんです。\n"
        "  落ちる所は `src.house_rule.is_stockpile()` の『もう公開になっている』の判定"
        "（日付の文字列ではなく、**時刻で**比べること）。"
    )


def test_当日の予約が1本でもあれば先頭は当日():
    """**1本でも**。オーナーの回は4本でしたが、押さえるのは『1本でも』のほう。"""
    rows = [_row("later", _at(2026, 9, 20, 13)),
            _row("today", _at(2026, 9, 1, 22))]
    got = pool_drain.pool(now=NOW, rows=rows)
    assert got and got[0]["id"] == "today", (
        f"先頭が {[r['id'] for r in got]} です。"
        "**当日の1本が、その日のうちに公開されます**（規則1が破れます）。"
    )


def test_翌日未明_JST_の予約が_UTC_日付で落ちない():
    """09/02 00:30 JST ＝ 09/01 15:30Z。**`at[:10]` で比べると当日扱いで落ちます。**"""
    row = _row("mid", _at(2026, 9, 2, 0, 30))
    assert row["at"].startswith("2026-09-01"), "前提（UTC では前日）が崩れています"
    ids = [r["id"] for r in pool_drain.pool(now=NOW, rows=[row])]
    assert ids == ["mid"], (
        "翌日未明（JST）の予約が池から落ちています ——"
        " `at` は UTC、`today` は JST の日付で、**物差しが違います。**"
    )


def test_当日でも過ぎた予約は触らない():
    """**証明できない行は触らない**（`pool()` の冒頭の姿勢）。過ぎた本は入れません。"""
    past = _row("gone", _at(2026, 9, 1, 9))       # 16:33 から見て過去
    assert pool_drain.pool(now=NOW, rows=[past]) == []


def test_当日でも規則の下で作った本は池に入らない():
    """規則3の1本（`STOCKPILE_SINCE` 以降に作った本）は、当日でも外しません。"""
    new = _row("keep", _at(2026, 9, 1, 22),
               made=house_rule.STOCKPILE_SINCE + "T08:40:00+00:00")
    assert pool_drain.pool(now=NOW, rows=[new]) == [], (
        "規則の下で作った『きょうの1本』が池に入りました ——"
        " `tests/test_pool_drain_keeps_new.py` の約束を壊しています。"
    )


def test_is_stockpile_は時刻で比べること():
    """穴の位置そのもの。**同じ日でも、まだ来ていない予約は作り置き。**"""
    row = {"video_id": "x", "at": "2026-09-01T09:00:00Z", "uploaded_at": MADE}
    assert house_rule.is_stockpile(row, now=NOW), (
        "09/01 18:00 JST の予約を、16:33 の時点で『もう公開になっている』"
        "と読んでいます。**日付ではなく時刻で比べること。**"
    )


def test_きょうぶんを数える口があること():
    """**画面に1行 出すため**の口（`today_rows`）。0本のときも 0本 と言わせます。"""
    rows = [_row("today", _at(2026, 9, 1, 22)), _row("tom", _at(2026, 9, 2, 13))]
    got = pool_drain.pool(now=NOW, rows=rows)
    mine = pool_drain.today_rows(got, now=NOW)
    assert [r["id"] for r in mine] == ["today"], (
        f"{[r['id'] for r in mine]} —— きょう（JST）ぶんだけを返すこと。"
        " 一覧に当日ぶんが在るかどうかは、`--apply` の前に見える唯一の行です。"
    )
    assert pool_drain.today_rows([], now=NOW) == []
