"""**`trend.watch_vs_reach`** —— いまの作り（≈90秒）で「見られた割合」が配りを決めているか。

**なぜこの検査が在るか**（2026-09-20 01:5x・optimizer・Opus 5・ultracode・1周 1体）:
`reporting.watched_short` の **5.9倍** は **8秒 の古い窓**の数で、印字は自分でそう言っています。
それでも決めの理由としては使われ続けました（METHOD §5 2026-09-19 13:0x）。
この検査は、**新しい側が同じ穴に落ちないための 3つ** を留めます ——
**尺で袋を分けること**・**齢の門**・**n の札**。

**陰性対照**（(4)）: 割合と再生が本当に一緒に動く台帳を作ると、相関は正で返ること。
これが無いと「いつでも 0 を返す関数」が検査を通ります。
"""
from __future__ import annotations

from studio import trend


def _av(vid: str, pct: float, sec: float, views: int = 100,
        likes: int = 0, studio: bool = True) -> dict:
    return {"event": "analytics_video", "id": vid, "studio": studio, "views": views,
            "avg_percent": pct, "avg_seconds": sec, "likes": likes, "subs_gained": 0}


def _m(vid: str, views: int, age_h: float) -> dict:
    return {"event": "measured", "id": vid, "views": views, "age_h": age_h,
            "title": vid, "likes": 0}


def _pair(vid: str, final: int, pct: float, length: float, age_h: float = 100.0,
          likes: int = 0, studio: bool = True) -> list[dict]:
    return [_m(vid, final, age_h), _av(vid, pct, length * pct / 100.0,
                                       views=final, likes=likes, studio=studio)]


def test_1_short_and_long_go_in_different_bags():
    """(1) **尺で分かれること** —— 長尺を同じ袋に入れると、相関は尺の相関になる。"""
    rows: list[dict] = []
    for i in range(9):
        rows += _pair(f"s{i}", 100 + i, 40.0 + i, 90.0)
    rows += _pair("L0", 1, 20.0, 520.0)
    rows += _pair("L1", 13, 33.0, 370.0)
    d = trend.watch_vs_reach(rows)
    assert d["n_short"] == 9
    assert d["n_long"] == 2
    assert {r["id"] for r in d["long"]} == {"L0", "L1"}


def test_2_young_videos_are_left_out():
    """(2) **齢の門** —— 48h より若い本は「確定した再生」を持たない。"""
    rows: list[dict] = []
    for i in range(9):
        rows += _pair(f"s{i}", 100 + i, 40.0 + i, 90.0)
    rows += _pair("young", 5, 95.0, 90.0, age_h=3.0)
    d = trend.watch_vs_reach(rows)
    assert "young" not in {r["id"] for r in d["short"]}
    assert d["n_short"] == 9


def test_3_thin_n_prints_the_tag_and_forbids_reading_the_sign():
    """(3) **n の札** —— `WVR_MIN_N` に届かない回は符号を読ませない。"""
    rows: list[dict] = []
    for i in range(4):
        rows += _pair(f"s{i}", 100 + i * 50, 40.0 + i * 10, 90.0)
    d = trend.watch_vs_reach(rows)
    assert d["enough"] is False
    line = trend.watch_vs_reach_line(rows)
    assert "符号を読まないこと" in line


def test_4_negative_control_a_real_slope_comes_back_positive():
    """(4) **陰性対照** —— 割合と再生が一緒に動く台帳なら、相関は正で返ること。"""
    rows: list[dict] = []
    for i in range(10):
        rows += _pair(f"s{i}", 100 * (i + 1), 20.0 + i * 6.0, 90.0)
    d = trend.watch_vs_reach(rows)
    assert d["enough"] is True
    assert d["rho_pct"] > 0.9


def test_5_likes_are_returned_both_raw_and_per_1k():
    """(5) **いいねは再生に機械的に乗る** —— 生だけを読ませない。"""
    rows: list[dict] = []
    for i in range(10):
        rows += _pair(f"s{i}", 100 * (i + 1), 45.0, 90.0, likes=i + 1)
    d = trend.watch_vs_reach(rows)
    assert d["rho_likes"] > 0.9          # 生は再生と一緒に上がる
    assert d["rho_like1k"] < d["rho_likes"]   # 1,000回 あたりに直すと平らになる
    line = trend.watch_vs_reach_line(rows)
    assert "1,000回 あたりに直すと" in line


def test_6_only_our_own_videos_are_counted():
    """(6) `studio: false`（旧作り）は入れないこと —— 別の作り・別の声。"""
    rows: list[dict] = []
    for i in range(9):
        rows += _pair(f"s{i}", 100 + i, 40.0 + i, 90.0)
    rows += _pair("old0", 3, 1.4, 1100.0, studio=False)
    d = trend.watch_vs_reach(rows)
    ids = {r["id"] for r in d["short"]} | {r["id"] for r in d["long"]}
    assert "old0" not in ids


def test_7_empty_ledger_says_so_instead_of_returning_zero():
    """(7) **黙って 0 を返さない**（§4 (0-b)）—— 数えられる本が 0本 なら、そう言うこと。"""
    d = trend.watch_vs_reach([])
    assert d["n_short"] == 0
    assert "0本" in trend.watch_vs_reach_line([])


def test_8_rewatch_over_100_percent_is_not_dropped():
    """(8) 再視聴（100% 超）は落とさない（`reporting.watched` の覆る条件 (3) と同じ）。"""
    rows: list[dict] = []
    for i in range(8):
        rows += _pair(f"s{i}", 100 + i, 40.0 + i, 90.0)
    rows += _pair("loop", 180, 126.2, 90.0)
    d = trend.watch_vs_reach(rows)
    assert "loop" in {r["id"] for r in d["short"]}
