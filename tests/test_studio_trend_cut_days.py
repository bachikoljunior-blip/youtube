"""`trend` の窓（`--days`）より前の日が、**黙って消えていないか**。

実測 2026-09-09 15:2x JST（optimizer・Opus）: 既定の `--days 3`（72時間）で
**09/06 が丸ごと消えていた** —— いちばん若い本が 73.3h ＝ 窓の外に出たため。

09/09 10:4x の直しは、**一部だけ**が窓に入る日に
「この日は N本・**この窓に出るのは M本**。窓の縁で切れている」を付けた。
しかし**その日の本が1本も窓に入らない日**は `days` に入らないので、
**見出しごと出ない** ＝ 読む側は「09/06 は無かった」と「09/06 は切れた」を区別できない。

09/06 は 8本 の日で、**§7 の「天井 437回」も「中央値 196回」もこの日から引いています**
（＝ §7 が毎周 引く対照が、道具の既定の窓から黙って落ちた）。

陰性対照つき: 切れた日が無ければ、この行は出ない。
"""
import datetime as dt

from studio import trend
from studio.common import JST

NOW = dt.datetime(2026, 9, 9, 15, 20, tzinfo=JST)


def _m(vid, at, age_h, views):
    return {"event": "measured", "id": vid, "at": at, "age_h": age_h,
            "views": views, "likes": 0, "title": vid}


# 09/09 の本は窓の中・09/06 の 2本 は窓（72h）の外
ROWS = [
    _m("NEW4", "2026-09-09T14:20:00+09:00", 4.3, 359),
    _m("NEW4", "2026-09-09T15:20:00+09:00", 5.3, 458),
    _m("OLD6A", "2026-09-09T14:20:00+09:00", 75.3, 437),
    _m("OLD6A", "2026-09-09T15:20:00+09:00", 76.3, 437),
    _m("OLD6B", "2026-09-09T14:20:00+09:00", 72.3, 290),
    _m("OLD6B", "2026-09-09T15:20:00+09:00", 73.3, 290),
]


def test_窓より前の日は名指しで出る():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "09/06（2本）" in out, out
    assert "出ていません" in out, out


def test_その日は無かったと読ませない():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "「その日は無かった」ではありません" in out, out
    assert "--days" in out, out


def test_窓の中の日は行として出たまま():
    out = "\n".join(trend.lines(ROWS, now=NOW))
    assert "09/09（1本）" in out, out
    assert "5.3h 458" in out, out


def test_陰性対照_切れた日が無ければ行は出ない():
    """窓を伸ばして全部の日が入れば、この行は出ない（＝ 毎回 出る飾りではない）。"""
    out = "\n".join(trend.lines(ROWS, within_h=24 * 30, now=NOW))
    assert "出ていません" not in out, out
    assert "09/06（2本）" in out, out  # 見出しとしては出る


def test_窓の長さが行に出る():
    """`--days` を伸ばせと言う以上、いまの窓の長さを名乗ること。"""
    out = "\n".join(trend.lines(ROWS, within_h=24 * 3, now=NOW))
    assert "`--days 3`" in out, out
