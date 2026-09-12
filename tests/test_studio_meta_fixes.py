"""**上がった本の 題・説明欄を、あとから直した回**を数える口（`trend.meta_fixes`）。

2026-09-12 15:0x JST（optimizer・Opus）に足した。**踏んだ形**: 台帳に
`meta_updated` 3件・`meta_update` 1件 が在り、`grep meta_update studio/ scripts/ tests/` は
**0件** —— **誰も読んでいませんでした**。4件目 を書いた回は本文に手で「4件目」と数えており
＝ 数えている人は居るのに、数える口が無い（`cli.record_over` と同じ族）。

ここで止めるのは 3つ:
  * **2つ の event 名のうち片方だけを数える**（＝ 4件 が 3件 になる）
  * **予約の前と後を分けない**（＝ §4 の出口を抜けた数が出ない）
  * **`--replace` で置き換えられた本を分母に数える**（＝ 7本 が 8本 になる）
"""
import datetime as dt

import pytest

from studio import trend
from studio.common import JST


def _sched(sid, vid, at, replaced=None):
    return {"event": "scheduled", "id": sid, "video_id": vid, "at": at, "replaced": replaced}


def _m(vid, at, age_h, views=1):
    return {"event": "measured", "id": vid, "at": at, "age_h": age_h,
            "views": views, "likes": 0, "title": vid}


# 予約 09/08 00:54 → 公開 09/08 10:00（`measured` の齢から引く ＝ `trend.published_at`）
ROWS = [
    _sched("2026-09-08-a", "AAA", "2026-09-08T00:54:00+09:00"),
    _m("AAA", "2026-09-08T16:00:00+09:00", 6.0, 200),
    _sched("2026-09-09-b", "BBB", "2026-09-09T00:30:00+09:00"),
    _m("BBB", "2026-09-09T16:00:00+09:00", 6.0, 300),
]


def test_予約の前と後と公開の後を分ける():
    rows = ROWS + [
        # 予約の前（§4 の出口の中で捕まった側）
        {"event": "meta_updated", "id": "2026-09-08-a", "video_id": "AAA",
         "at": "2026-09-08T00:10:00+09:00"},
        # 予約の後・公開の前（出口を抜けた）
        {"event": "meta_updated", "id": "2026-09-08-a", "video_id": "AAA",
         "at": "2026-09-08T02:00:00+09:00"},
        # 公開の後（視聴者が読んだあと）
        {"event": "meta_updated", "id": "2026-09-09-b", "video_id": "BBB",
         "at": "2026-09-09T20:00:00+09:00"},
    ]
    q = trend.meta_fixes(rows)
    assert (q["n"], q["books"]) == (3, 2), q
    assert (q["before"], q["after_sched"], q["after_pub"]) == (1, 1, 1), q
    assert q["unresolved"] == 0, q


def test_event_名は2つとも拾う():
    """`meta_update`（単数・`id` が video id・`video_id` が無い）も同じ物。"""
    rows = ROWS + [
        {"event": "meta_updated", "id": "2026-09-08-a", "video_id": "AAA",
         "at": "2026-09-08T02:00:00+09:00"},
        {"event": "meta_update", "id": "AAA", "field": "description",
         "at": "2026-09-08T02:30:00+09:00"},
    ]
    q = trend.meta_fixes(rows)
    assert q["n"] == 2, q
    assert q["names"] == {"meta_updated": 1, "meta_update": 1}, q
    assert q["after_sched"] == 2, q
    assert q["books"] == 1, q          # 同じ本の 2件 は 1本
    assert q["unresolved"] == 0, q


def test_片方の名だけを数えると1件落ちる():
    """**陽性対照**: `META_FIX_EVENTS` を片方に縮めたら、この検査は落ちること。"""
    rows = ROWS + [
        {"event": "meta_update", "id": "AAA", "at": "2026-09-08T02:30:00+09:00"},
    ]
    assert trend.meta_fixes(rows)["n"] == 1
    orig = trend.META_FIX_EVENTS
    try:
        trend.META_FIX_EVENTS = ("meta_updated",)
        assert trend.meta_fixes(rows)["n"] == 0     # ← 名を 1つ にすると落ちる
    finally:
        trend.META_FIX_EVENTS = orig


def test_置き換えられた本は分母に数えない():
    rows = [
        _sched("2026-09-06-z", "OLD", "2026-09-06T00:00:00+09:00"),
        _sched("2026-09-06-z", "NEW", "2026-09-06T01:00:00+09:00", replaced="OLD"),
        _m("NEW", "2026-09-06T16:00:00+09:00", 6.0, 50),
    ]
    assert trend.meta_fixes(rows)["scheduled_books"] == 1, trend.meta_fixes(rows)


def test_台本idはいちばん新しい予約のvideo_idを指す():
    """`--replace` の台本は video_id を 2つ 持つ ＝ **古いほうに当てないこと**。"""
    rows = [
        _sched("2026-09-06-z", "OLD", "2026-09-06T00:00:00+09:00"),
        _sched("2026-09-06-z", "NEW", "2026-09-06T01:00:00+09:00", replaced="OLD"),
        _m("NEW", "2026-09-06T16:00:00+09:00", 6.0, 50),
        {"event": "meta_updated", "id": "2026-09-06-z", "at": "2026-09-06T02:00:00+09:00"},
    ]
    q = trend.meta_fixes(rows)
    assert [r["vid"] for r in q["rows"]] == ["NEW"], q
    assert q["after_sched"] == 1, q


def test_引けない行はunresolvedで名指しする():
    rows = ROWS + [{"event": "meta_updated", "id": "どこにも無い", "at": "2026-09-08T02:00:00+09:00"}]
    q = trend.meta_fixes(rows)
    assert (q["n"], q["unresolved"]) == (1, 1), q
    assert "本を引けなかった行 1件" in trend.meta_fix_line(rows)


def test_0件の行は数を言う():
    line = trend.meta_fix_line(ROWS)
    assert "0件" in line and "meta_updated" in line, line
    # `tests/test_studio_trend_pending.py` は「並びのどこにも 予約 が出ない」で
    # `pending` の行の不在を見ています ＝ **0件 の文に「予約」の2字を入れないこと。**
    assert "予約" not in line, line


def test_公開の後の行は本を名指しする():
    rows = ROWS + [
        {"event": "meta_updated", "id": "2026-09-09-b", "video_id": "BBB",
         "at": "2026-09-09T20:00:00+09:00"},
    ]
    line = trend.meta_fix_line(rows)
    assert "公開の後: BBB" in line, line


@pytest.mark.parametrize("at,want", [
    ("2026-09-08T00:53:59+09:00", "before"),
    ("2026-09-08T00:54:00+09:00", "after_sched"),
    ("2026-09-08T09:59:59+09:00", "after_sched"),
    ("2026-09-08T10:00:00+09:00", "after_pub"),
])
def test_境目は予約の刻と公開の刻そのもの(at, want):
    rows = ROWS + [{"event": "meta_updated", "id": "2026-09-08-a", "video_id": "AAA", "at": at}]
    q = trend.meta_fixes(rows)
    assert q[want] == 1, (at, want, q)


def test_公開の刻はmeasuredの齢から引く():
    """`scheduled` の `publish_at` を読まないこと（最初の 3行 は欄そのものが無い）。"""
    rows = [
        _sched("2026-09-08-a", "AAA", "2026-09-08T00:54:00+09:00"),
        _m("AAA", "2026-09-08T16:00:00+09:00", 6.0, 200),
    ]
    assert trend.published_at(trend.series(rows)["AAA"]) == dt.datetime(
        2026, 9, 8, 10, 0, tzinfo=JST)


def test_measuredが1点も無い本は公開の後に倒さない():
    """まだ 1度も測っていない本（＝ 公開前）の直しを「公開の後」と数えない。"""
    rows = [
        _sched("2026-09-13-c", "CCC", "2026-09-13T00:20:00+09:00"),
        {"event": "meta_updated", "id": "2026-09-13-c", "video_id": "CCC",
         "at": "2026-09-13T01:00:00+09:00"},
    ]
    q = trend.meta_fixes(rows)
    assert (q["after_sched"], q["after_pub"]) == (1, 0), q
