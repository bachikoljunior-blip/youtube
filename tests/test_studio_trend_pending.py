"""`trend` の日ごとの本数に、**まだ公開前の本（予約）**が入るか。

実測 2026-09-08 23:0x JST（optimizer・Opus）: 旧作りの `Yy7GmcGoQ6I` は 08/19 に上げられ、
09/02 に旧 `reschedule.py` が **09/08 23:00 JST** の publishAt を打ったまま private で待っていた。
`status` の「きょうの枠」には private として出ていたが、`trend` は `measured`（＝公開ずみ）しか
数えないので、日の見出しは 22時間 ずっと「09/08（1本）」だった。
§7 は 15:0x〜21:4x の **5回 続けて**「3本目は 1本 だけの日 に出た」と書き、23:00 にその本が出て
**09/08 は 2本 の日**になった（§1「量は毒」の軸が、判定を書いている数から抜けていた）。
ここで止めるのは、その形に戻ること。
"""
import datetime as dt

from studio import trend
from studio.common import JST

NOW = dt.datetime(2026, 9, 8, 21, 40, tzinfo=JST)


def _m(vid, at, age_h, views):
    return {"event": "measured", "id": vid, "at": at, "age_h": age_h, "views": views, "likes": 0, "title": vid}


ROWS = [
    {"event": "scheduled", "id": "2026-09-08-x", "at": "2026-09-08T02:00:00+09:00", "video_id": "NEW3"},
    _m("NEW3", "2026-09-08T19:00:00+09:00", 9.0, 298),
    _m("NEW3", "2026-09-08T21:40:00+09:00", 11.7, 328),
    {"event": "pending", "id": "OLDSCH", "at": "2026-09-08T21:40:00+09:00",
     "publish_at": "2026-09-08T23:00:00+09:00", "title": "自動車税 2012年度登録の重課は何年度から"},
]


def test_予約の本が日の見出しの本数に入る():
    out = trend.lines(ROWS, now=NOW)
    assert out[0] == "09/08（1本＋予約 1本）", out


def test_予約の本が行として出る():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "23:00 予 OLDSCH" in out, out
    assert "まだ公開前" in out, out


def test_公開されて_measured_が付いたら予約として二重に数えない():
    rows = ROWS + [_m("OLDSCH", "2026-09-09T00:00:00+09:00", 1.0, 0)]
    now = dt.datetime(2026, 9, 9, 0, 0, tzinfo=JST)
    out = trend.lines(rows, now=now)
    assert out[0] == "09/08（2本）", out
    assert "予約" not in "\n".join(out), out


def test_予約が無い日の見出しは変わらない():
    rows = [r for r in ROWS if r.get("event") != "pending"]
    assert trend.lines(rows, now=NOW)[0] == "09/08（1本）", trend.lines(rows, now=NOW)
