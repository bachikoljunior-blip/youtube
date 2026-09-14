"""`trend.sub_rate_cohorts` —— **本ごとの登録率**（台帳の `analytics_video` だけ・Data API 0単位）。

**なぜ要るか**（2026-09-14 21:2x・optimizer・Opus）: 同じ回に `rev_deadline` へ
**扉(b)（長尺 4,000時間）**を足したら、**扉(b) で縛るのは再生ではなく登録率**でした
（要る **1.62%** 対 チャンネル全体 **0.026%**）。ところが `trend` は本ごとの登録率を
**1つも持っていませんでした** —— 0.026% は `channel_growth` の「登録の増え ÷ 総再生の増え」で、
**どの本が登録を連れてきたかを言いません。** 数は台帳にもう在ります（`cli.analytics` の `subs_gained`）。

**陽性対照**（撃って落とした）:
尺を台帳の `seconds` の欄から取ると `test_長尺の数は尺の口から出す` が落ち
（**欄は在りません** ＝ 黙って 0本 を返す・この口を書いた回に実際に踏んだ）、
長尺に再生の下限を当てると `test_長尺に再生の下限を当てない` が落ち、
`studio` の札と尺を同じ側にすると `test_札の側と尺の側は別` が落ちる。
"""
import pytest

from studio import trend


def _v(vid: str, views: int, subs: int, *, studio: bool, pct: float,
       sec: float, minutes: float = 0.0, at: str = "2026-09-13T04:38:20+09:00") -> dict:
    """`avg_percent` と `avg_seconds` から尺が出ます（`trend.curve_seconds`）。"""
    return {"event": "analytics_video", "id": vid, "views": views, "subs_gained": subs,
            "studio": studio, "avg_percent": pct, "avg_seconds": sec * pct / 100,
            "minutes": minutes, "likes": 0, "day": "2026-09-10", "at": at}


def _chan(at: str, subs: int, views: int) -> dict:
    return {"event": "channel", "id": "c", "subs": subs, "views": views, "at": at}


def _rows() -> list[dict]:
    return [_chan("2026-09-10T20:00:00+09:00", 27, 80_000),
            _chan("2026-09-13T20:00:00+09:00", 28, 88_000),
            {"event": "analytics_day", "id": "2026-09-10", "views": 700,
             "at": "2026-09-13T04:38:20+09:00"},
            _v("s1", 1_000, 1, studio=True, pct=45.0, sec=60),
            _v("s2", 1_000, 0, studio=True, pct=45.0, sec=60),
            _v("o1", 500, 1, studio=False, pct=48.0, sec=30),
            _v("L1", 20, 0, studio=False, pct=10.0, sec=600, minutes=12.0),
            _v("L2", 10, 0, studio=False, pct=10.0, sec=300, minutes=5.0)]


def test_札で分けた率が出る():
    c = trend.sub_rate_cohorts(_rows())
    assert c["new"]["n"] == 2 and c["new"]["views"] == 2_000 and c["new"]["subs"] == 1
    assert c["new"]["rate"] == pytest.approx(1 / 2_000)
    assert c["old"]["n"] == 1, "L1・L2 は再生 30回 未満 ＝ 札の側の分母に入れない"


def test_再生の下限より下の本は札の側に入れない():
    """1〜6回 の本を混ぜると、1人 の登録で 20% のような率が出る。"""
    c = trend.sub_rate_cohorts(_rows() + [_v("tiny", 5, 1, studio=True, pct=45.0, sec=60)])
    assert c["new"]["n"] == 2, f"下限 {trend.SUB_RATE_MIN_VIEWS}回 を当てること"


def test_長尺の数は尺の口から出す():
    """**陽性対照**: `analytics_video` に `seconds` の欄は在りません。

    この口を書いた回に `r.get("seconds")` と書き、**黙って 0本**を返していました
    （実物の台帳には長尺が 5本 在る）。尺は `curve_seconds`
    （`avg_seconds / avg_percent × 100`）から出すこと。
    """
    rows = _rows()
    assert all("seconds" not in r for r in rows if r.get("event") == "analytics_video")
    c = trend.sub_rate_cohorts(rows)
    assert c["long_n"] == 2 and c["long"]["n"] == 2, "L1（600秒）と L2（300秒）"


def test_長尺に再生の下限を当てない():
    """陽性対照: 下限（30回）を当てると L1・L2 が消え、扉(b) の分子が「無い」に化ける。"""
    c = trend.sub_rate_cohorts(_rows())
    assert c["long"]["views"] == 30 and c["long"]["subs"] == 0
    assert c["long"]["hours"] == pytest.approx(17 / 60)
    assert c["long_times"] == pytest.approx(trend.REV_LONG_HOURS / (17 / 60))


def test_札の側と尺の側は別():
    """陽性対照: 同じ側にすると、扉の違う本が 1つの中央値に混ざる（(4-g) 4）。"""
    c = trend.sub_rate_cohorts(_rows())
    assert c["new"]["n"] + c["old"]["n"] != c["long"]["n"]
    assert c["old"]["n"] == 1 and c["long"]["n"] == 2


def test_要る率は_rev_deadline_の扉bから引く():
    """**門は 1か所** —— この口は自分で 1.62% を持たないこと。"""
    rows = _rows()
    assert trend.sub_rate_cohorts(rows)["need_b"] == trend.rev_deadline(rows)["sub_rate_need_b"]


def test_台帳に_analytics_video_が無くても落ちない():
    line = trend.sub_rate_line([{"event": "analytics_day", "id": "2026-09-10", "views": 1,
                                 "at": "2026-09-13T04:38:20+09:00"}])
    assert "まだ測れていません" in line


def test_行は下端だと毎周言う():
    """Analytics は登録をチャンネルのページ側へも付ける ＝ 本ごとの合計は小さく出る。"""
    line = trend.sub_rate_line(_rows())
    assert "下端" in line and "判定は `hourly` とオーナー" in line
    assert "率ではなく時間で読むこと" in line, "扉(b) の通貨は時間"
