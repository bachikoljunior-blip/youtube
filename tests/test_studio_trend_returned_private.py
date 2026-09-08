"""公開されたあと private へ戻した本を、`trend` が**その日の本数に数えない**か。

実測 2026-09-09 08:5x JST（optimizer・Opus）: 旧 `reschedule.py` が 09/02 に打った publishAt が
**09/08 23:00 JST** に発火して `Yy7GmcGoQ6I` が public になり、**7分後**に前の回が private へ戻して
台帳に `unscheduled` を書いた（`data/studio/ledger.jsonl`）。それでも `trend` の見出しは
**10時間 たっても「09/08（2本）」**のままで、行は **「0.1h 0」で凍って**いた ——
private の本は `measure` が二度と見ないので、この点は永久に更新されない。

§7 は浅い齢の再生で「お試し配信は毎回 来るか」を見ている。**7分だけ public だった本の 0回**は
その問いの答えではないのに、並びの上では「0回 の本」と同じ形をしている。
§7 が 09/07 16:3x に踏んだ穴（その日に出た本を1本も見ていなかった）と**同じ型で向きが逆**
（あちらは数え落とし・こちらは数えすぎ）。ここで止めるのは、その形に戻ること。

**消していない**（オーナー 08/31・§8）—— 行は「戻」として印字する。
"""
import datetime as dt

from studio import trend
from studio.common import JST

NOW = dt.datetime(2026, 9, 9, 8, 44, tzinfo=JST)


def _m(vid, at, age_h, views):
    return {"event": "measured", "id": vid, "at": at, "age_h": age_h, "views": views,
            "likes": 0, "comments": 0, "title": vid}


ROWS = [
    {"event": "scheduled", "id": "2026-09-08-x", "at": "2026-09-08T02:00:00+09:00", "video_id": "NEW3"},
    _m("NEW3", "2026-09-09T07:49:00+09:00", 21.8, 405),
    _m("NEW3", "2026-09-09T08:46:00+09:00", 22.7, 402),
    # 23:00 に発火して public になり、23:03 に測られ、23:07 に private へ戻された旧作りの本
    _m("BACK", "2026-09-08T23:03:19+09:00", 0.1, 0),
    {"event": "unscheduled", "id": "BACK", "at": "2026-09-08T23:07:57+09:00",
     "was_public_at": "2026-09-08T23:00+09:00", "views_at_unschedule": 0, "reason": "旧 publishAt が発火"},
]


def test_戻した本は日の本数に入らない():
    out = trend.lines(ROWS, now=NOW)
    assert out[0] == "09/08（1本）", out


def test_戻した本の行は消さずに印字する():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "戻 BACK" in out, out
    assert "private へ戻した" in out, out


def test_もう一度_公開されたら数に戻る():
    """`unscheduled` より後の `measured` が付いたら、その本は普通の1本に戻る。"""
    rows = ROWS + [_m("BACK", "2026-09-09T08:46:00+09:00", 2.0, 31)]
    out = trend.lines(rows, now=NOW)
    assert out[0] == "09/08（2本）", out
    assert "戻 BACK" not in "\n".join(out), out
