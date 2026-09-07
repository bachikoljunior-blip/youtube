"""`studio.trend` —— 台帳から「齢 → 再生」の並びを出す（§7 の判定を1点で下さないため）。

実測 2026-09-07 18:3x JST（optimizer・Opus）: §7 が 2回 続けて、平らな区間の中で見た1点から
「止まった」と書いていた（1本目 9.6h〜28.4h が平ら → 32.6h で 139・2本目 4.4h〜6.6h が平ら → 8.6h で 68）。
ここで止めるのは「並びのうち最後の点だけを見せる」形に戻ること。
"""
import datetime as dt

from studio import trend
from studio.common import JST

NOW = dt.datetime(2026, 9, 7, 18, 30, tzinfo=JST)


def _m(vid, at, age_h, views):
    return {"event": "measured", "id": vid, "at": at, "age_h": age_h, "views": views, "likes": 0, "title": vid}


ROWS = [
    {"event": "scheduled", "id": "2026-09-07-x", "at": "2026-09-07T02:00:00+09:00", "video_id": "NEW1"},
    _m("NEW1", "2026-09-07T16:30:00+09:00", 6.5, 28),
    _m("NEW1", "2026-09-07T18:30:00+09:00", 8.5, 68),
    _m("OLD1", "2026-09-07T16:30:00+09:00", 7.5, 73),
    _m("OLD1", "2026-09-07T18:30:00+09:00", 9.5, 73),
]


def test_1本の並びが全部出る():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "6.5h 28 → 8.5h 68" in out, out  # 最後の点だけにしない
    assert "7.5h 73 → 9.5h 73" in out, out


def test_直近の伸びが出る():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "[直近 +40回 / 2.0h]" in out, out
    assert "[直近 +0回 / 2.0h]" in out, out


def test_こちらの作りと旧作りを分ける():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "新 NEW1" in out and "旧 OLD1" in out, out


def test_同じ日の本は同じ束に並ぶ():
    out = trend.lines(ROWS, now=NOW)
    assert out[0] == "09/07（2本）", out


def test_古い本は落ちる():
    old = ROWS + [_m("ANCIENT", "2026-09-07T18:30:00+09:00", 24 * 9, 500)]
    out = "\n".join(trend.lines(old, now=NOW, within_h=24 * 3))
    assert "ANCIENT" not in out, out


def test_公開の刻は齢から戻す():
    pub = trend.published_at(trend.series(ROWS)["NEW1"])
    assert pub.strftime("%m/%d %H:%M") == "09/07 10:00", pub


def test_平らは止まりではないと必ず書く():
    # この一文を消すのは、平らを「止まった」と読んでよいと決めたとき（trend.py の覆る条件）。
    assert "平らは「止まった」ではない" in trend.lines(ROWS, now=NOW)[-1]
