"""`studio/meter.py` —— **撃った API を撃った所で数える**綴じの見張り。

守っているのは 4つ:
 1. **値段表**（`videos.insert` 1,600 ／ `videos.list` 1 ／ Analytics は 0単位）
 2. **403 で撥ねられた 1本 は 0単位**（枠を食っていない ＝ 水増ししない）
 3. **`next_chunk` も掛かる**（`videos.insert` は `execute()` を通らない ＝ いちばん高い口が落ちる穴）
 4. **綴じが窓の頭から無い窓では「誰が食ったか」を言い切らない**（道具を足した日の弱い証拠）
"""
from __future__ import annotations

import datetime as dt

from studio import meter


def test_値段表():
    assert meter.cost("youtube.videos.insert") == 1600
    assert meter.cost("youtube.thumbnails.set") == 50
    assert meter.cost("youtube.videos.list") == 1
    assert meter.cost("youtube.search.list") == 100
    # Analytics は別の枠 ＝ Data API の日枠には乗らない
    assert meter.cost("youtubeAnalytics.reports.query") == 0
    # 表に無い方法を 0 と数えないこと（読みは 1・書きは 50 に寄せる）
    assert meter.cost("youtube.captions.download") == 50
    assert meter.cost("youtube.members.list") == 1


def test_403で撥ねられた分は枠を食っていない():
    since = "2026-09-17T16:00:00+09:00"
    rows = [
        {"at": "2026-09-17T16:10:00+09:00", "api": "youtube", "method": "videos.insert",
         "units": 1600, "ok": True},
        {"at": "2026-09-17T16:20:00+09:00", "api": "youtube", "method": "videos.list",
         "units": 1, "ok": False, "status": 403},
        {"at": "2026-09-17T16:30:00+09:00", "api": "youtube", "method": "videos.update",
         "units": 50, "ok": False, "status": 500},
    ]
    s = meter.spent(since, rows)
    assert s["total"] == 1650          # 403 の 1単位 は入らない・500 は安全側で入る
    assert s["calls"] == 3 and s["refused"] == 1
    # 窓の手前の行は入らない
    assert meter.spent("2026-09-17T16:25:00+09:00", rows)["total"] == 50


def test_うちが食っていない窓は名指しするが綴じが欠けていれば言い切らない():
    since = "2026-09-17T16:00:00+09:00"
    dry = "2026-09-17T19:00:00+09:00"
    covered = [{"at": "2026-09-17T16:05:00+09:00", "api": "youtube", "method": "videos.list",
                "units": 1, "ok": True}]
    line = meter.outside_line(since, 10_000, dry, covered)
    assert line and "この機械ではありません" in line

    # 窓の頭から 1時間 より後にしか綴じが無い ＝ 言い切らない
    late = [{"at": "2026-09-17T22:00:00+09:00", "api": "youtube", "method": "videos.list",
             "units": 1, "ok": True}]
    line2 = meter.outside_line(since, 10_000, dry, late)
    assert line2 and "決まりません" in line2 and "この機械ではありません" not in line2

    # 403 が出ていない窓では、そもそも出さない
    assert meter.outside_line(since, 10_000, None, covered) is None
    # うちの実測が枠の半分を越えていたら、食ったのはうち ＝ 出さない
    big = [{"at": "2026-09-17T16:05:00+09:00", "api": "youtube", "method": "videos.insert",
            "units": 1600, "ok": True} for _ in range(4)]
    assert meter.outside_line(since, 10_000, dry, big) is None


def test_掛ける先は_execute_と_next_chunk_の両方():
    """`videos.insert` は `resumable=True` ＝ `execute()` を通らない（`meter.install` の註）。"""
    from googleapiclient.http import HttpRequest

    meter._installed = False
    before = (HttpRequest.execute, HttpRequest.next_chunk)
    try:
        meter.install()
        assert HttpRequest.execute is not before[0]
        assert HttpRequest.next_chunk is not before[1]
        # 2度 掛けない
        again = (HttpRequest.execute, HttpRequest.next_chunk)
        meter.install()
        assert (HttpRequest.execute, HttpRequest.next_chunk) == again
    finally:
        HttpRequest.execute, HttpRequest.next_chunk = before
        meter._installed = False


def test_名の割り():
    assert meter.split("youtube.videos.list") == ("youtube", "videos.list")
    assert meter.split("youtube.playlistItems.list") == ("youtube", "playlistItems.list")
    assert meter.split("") == ("", "")


def test_窓の頭は16時JST():
    now = dt.datetime(2026, 9, 17, 6, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    assert meter.window_line(now).startswith("2026-09-16T16:00")
    now2 = dt.datetime(2026, 9, 17, 17, 0, tzinfo=dt.timezone(dt.timedelta(hours=9)))
    assert meter.window_line(now2).startswith("2026-09-17T16:00")
