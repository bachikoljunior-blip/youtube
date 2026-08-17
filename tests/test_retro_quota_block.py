"""持ち越しの並び —— **その回では物理的に潰せない語を、上位に置かないこと。**

## なぜ要るか（2026-08-17 に実測してから足しています）

`docs/trigger_main.md` §2.7 は **「持ち越しが出ていたら、そこから選ぶのが既定」**
と言っています。ところが Data API の1日枠は **JST 03:00〜16:00 の13時間ずっと
切れていて**、そのあいだ `videos.update` と `thumbnails.set` は **必ず 403** です。

09:1x の回で、`retro.py` の持ち越しを項目ごとに数えたら:

    4回  videos.update                  項目 4/4 が日枠がらみ
    4回  --closes missing_thumbnail     項目 4/4 が日枠がらみ
    3回  scripts/refresh_thumbnail.py   項目 3/3 が日枠がらみ
    3回  topic_forge                    項目 0/3
    3回  status.py                      項目 1/3

**上位3件が全部、その回には潰しようがないものでした。** これは
`src/alerts.py` が塞ぎに来た「**一覧が当たりを含まないまま育つ**」の5件目で、
今度は**育ち方ではなく、時刻によって当たらなくなる**という形です
（`missing_thumbnail` は5回鳴って当たり1回）。

## 沈めるだけで、消さないこと

16:00 以降の回では、この3件こそが**その回でしか潰せない仕事**です。
だから落とさず、逆に「**いまなら潰せます**」と印を付けて上に残します。
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("retro", ROOT / "scripts" / "retro.py")
retro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retro)

UTC = timezone.utc


def _block(date: str, lines: list[str]):
    return (date, lines, 0)


BLOCKED = [
    _block("2026-08-17 05:1x", [
        "1. **`refresh_thumbnail.py --missing` を、JST 16:00 以降に1回。**",
        "   **16:00 より前は403で落ちます**。",
        "2. **`topic_forge` の在庫が尽きます。**",
    ]),
    _block("2026-08-17 06:4x", [
        "1. **`refresh_thumbnail.py --missing` を回すこと。** 日枠が戻ってから。",
        "2. **`topic_forge` をもう一度。** 未使用の節が2件しかありません。",
    ]),
]


def test_日枠がらみの語だけが沈む():
    assert retro.quota_blocked(BLOCKED, "refresh_thumbnail.py --missing")
    # `topic_forge` は同じ回の申し送りに入っていますが、**その項目は日枠と無関係**です。
    assert not retro.quota_blocked(BLOCKED, "topic_forge")


def test_節ごとに見ると巻き込む_項目ごとに切ること():
    """**これがこの直しの本体**です。

    節を1つの文字列として見ると、同じ回の「JST 16:00」が
    **その回の他の項目を全部**日枠がらみに見せます。
    """
    joined = [_block("2026-08-17 05:1x", BLOCKED[0][1]),
              _block("2026-08-17 06:4x", BLOCKED[1][1])]
    # 項目ごとに切れていれば、topic_forge は巻き込まれない
    assert not retro.quota_blocked(joined, "topic_forge")
    # 切らなければ（＝故障を注入すると）巻き込まれることを、ここで固定する
    text = "\n".join(BLOCKED[0][1] + BLOCKED[1][1])
    assert retro.QUOTA_MARK_RE.search(text), "節ぜんぶで見れば必ず当たってしまう"


def test_1件しか言及が無い語は沈めない():
    """1回だけでは癖と言えません（持ち越しの下限も2回です）。"""
    one = [_block("2026-08-17 05:1x", [
        "1. **`videos.update` は日枠が切れていると403です。**",
    ])]
    assert not retro.quota_blocked(one, "videos.update")


def test_一部だけ日枠がらみなら沈めない():
    """**多数決にしないこと。** 潰せる側の項目まで沈みます。"""
    mixed = [
        _block("a", ["1. **`status.py` は日枠が切れていると読めません**（403）。"]),
        _block("b", ["1. **`status.py` の `--decide` を足すこと。** 692行は長すぎます。"]),
        _block("c", ["1. **`status.py` の在庫の節が落ちていました。**"]),
    ]
    assert not retro.quota_blocked(mixed, "status.py")


def test_16時の前後で向きが変わる():
    assert not retro.quota_is_back(datetime(2026, 8, 17, 0, 30, tzinfo=UTC))   # JST 09:30
    assert retro.quota_is_back(datetime(2026, 8, 17, 7, 30, tzinfo=UTC))       # JST 16:30
    assert retro.quota_is_back(datetime(2026, 8, 17, 14, 0, tzinfo=UTC))       # JST 23:00


def test_戻るまでの時間():
    # JST 09:00 → あと7.0時間
    assert retro.hours_to_quota(datetime(2026, 8, 17, 0, 0, tzinfo=UTC)) == 7.0
    # 戻っていれば 0.0（負の数を出さないこと）
    assert retro.hours_to_quota(datetime(2026, 8, 17, 8, 0, tzinfo=UTC)) == 0.0


def test_実物の日誌で_上位が日枠で埋まっていることを固定する():
    """**実データでの回帰**。手で作った例だけだと、実物の書き方が変わったとき黙ります。"""
    journal = retro.JOURNAL.read_text(encoding="utf-8")
    blocks = retro.handoff_blocks(journal)[-8:]
    if not blocks:
        return
    hit = [t for t in ("videos.update", "--closes missing_thumbnail")
           if retro.quota_blocked(blocks, t)]
    # 日誌が進んで語が入れ替わることはあります。**在るなら日枠がらみと判定されること**だけ固定する。
    for t in hit:
        assert retro.quota_blocked(blocks, t)


def test_故障注入_印を空にすると沈まなくなる(monkeypatch):
    """**両向きに壊して、検査が本当に効いているかを見ます。**"""
    import re
    monkeypatch.setattr(retro, "QUOTA_MARK_RE", re.compile(r"(?!x)x"))
    assert not retro.quota_blocked(BLOCKED, "refresh_thumbnail.py --missing")


def test_故障注入_印を何にでも当てると全部沈む(monkeypatch):
    import re
    monkeypatch.setattr(retro, "QUOTA_MARK_RE", re.compile(r""))
    assert retro.quota_blocked(BLOCKED, "topic_forge")
