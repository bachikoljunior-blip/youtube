# -*- coding: utf-8 -*-
"""**生の読み（`views_live`）の刻み**（`trend.live_drops`）の検査
（2026-09-19 22:4x JST・optimizer・Opus 5・ultracode・1周 1体）。

**なぜ在るか**: 前の周（JOURNAL 09/19 21:xx §6）が、同じ 4本 を **50分 あけて 2回** 生で読み、
その差（**+0**／+8／+38／+75）で「`oNiKmRKi4N4` は配りが止まっている側」を立てました。
**この周が撃って確かめたところ、その差は物差しの刻みより小さいものでした** ——
台帳の `views_over` は **377組 のうち 19組 で 生の読みが 減って** おり（最大 **-37回**）、
本物の再生は減らないので、**その大きさは本ではなく物差し**です。

**陽性対照を先に置く**（`test_pubcheck_shorts_views.py` と同じ形）:
    (1) 実物の 2組（`uc0SceBfoxQ` 77→40・`oNiKmRKi4N4` 139→132）から **-37** と **短い組の -7** が出ること
    (2) 減りが 1組 も無い台帳では **「落ち着いています」** と印字し、`worst` は 0 であること
    (3) 伸びだけの組は 1組 も減りに数えないこと（符号を取り違えていない）
    (4) **門ではない**こと ＝ 返り値に「止める」印が無く、行はただの字であること
"""
from __future__ import annotations

from studio import trend


def _mark(vid: str, at: str, live: int, ledger: int = 0) -> dict:
    return {"event": "views_over", "id": vid, "at": at,
            "views_live": live, "views_ledger": ledger, "over": live - ledger}


# 実物（`data/studio/ledger.jsonl` の `views_over`・2026-09-18〜09-19）。
REAL = [
    _mark("uc0SceBfoxQ", "2026-09-18T15:39:00+09:00", 77),
    _mark("uc0SceBfoxQ", "2026-09-18T16:02:00+09:00", 40),      # -37（22分）
    _mark("oNiKmRKi4N4", "2026-09-19T22:30:00+09:00", 139),
    _mark("oNiKmRKi4N4", "2026-09-19T22:34:00+09:00", 132),      # -7（4分・10分 以内）
]


def test_陽性対照_実物の2組から刻みが出る():
    d = trend.live_drops(REAL)
    assert d["pairs"] == 2 and d["drops"] == 2 and d["videos"] == 2
    assert d["worst"] == -37
    assert "uc0SceBfoxQ" in d["worst_where"] and "77→40" in d["worst_where"]
    # 10分 以内の組でも減る ＝ **速い連読では見えない**側の証拠
    assert d["near"] == -7 and "oNiKmRKi4N4" in d["near_where"]


def test_行は刻みを名指しして_門ではない():
    line = trend.live_drops_line(REAL)
    assert "±37回" in line
    assert "門ではありません" in line
    # 止める語を持たない（`schedule` も `status` も止めない）
    assert "止めます" not in line and "[!]" not in line


def test_伸びだけの台帳では_減りは0組_落ち着いていると印字する():
    up = [
        _mark("AAAAAAAAAAA", "2026-09-19T10:00:00+09:00", 100),
        _mark("AAAAAAAAAAA", "2026-09-19T11:00:00+09:00", 140),
        _mark("AAAAAAAAAAA", "2026-09-19T12:00:00+09:00", 141),
    ]
    d = trend.live_drops(up)
    assert d["pairs"] == 2 and d["drops"] == 0 and d["worst"] == 0 and d["near"] == 0
    assert "落ち着いています" in trend.live_drops_line(up)


def test_組が0なら_まだ数えられないと言う_0件とは言わない():
    assert trend.live_drops([])["pairs"] == 0
    line = trend.live_drops_line([])
    assert "まだ数えられません" in line
    # 「減りは 0件」と読ませない（分母が無いのと、減りが無いのは別）
    assert "落ち着いています" not in line


def test_本ごとに組む_別の本の値をまたがない():
    mixed = [
        _mark("AAAAAAAAAAA", "2026-09-19T10:00:00+09:00", 900),
        _mark("BBBBBBBBBBB", "2026-09-19T10:01:00+09:00", 10),   # 別の本 ＝ 組にしない
        _mark("AAAAAAAAAAA", "2026-09-19T11:00:00+09:00", 901),
    ]
    d = trend.live_drops(mixed)
    assert d["pairs"] == 1 and d["drops"] == 0


def test_実データ_台帳の生の読みは減る():
    """**この行が落ちたら、覆る条件 (1) が引かれた**（物差しが落ち着いた ＝ 行を外してよい）。"""
    import json
    import pathlib
    p = pathlib.Path(__file__).resolve().parents[1] / "data" / "studio" / "ledger.jsonl"
    rows = [json.loads(l) for l in p.open(encoding="utf-8") if l.strip()]
    d = trend.live_drops(rows)
    assert d["pairs"] > 50, "組が足りない ＝ まだ読めない（覆る条件 (4)）"
    assert d["drops"] > 0, "減りが 0組 ＝ 覆る条件 (1)：この口は外してよい"
    assert d["worst"] <= -5, f"刻みが -5回 まで縮んだ: {d}"
