"""`scripts/per_day_views.py` —— M14 の物差し（1本あたりの再生）。

**この検査が守るのは3つ**です。どれも 2026-08-19 に実物で踏んでいます。

1. **長尺を混ぜないこと** —— 24時間で 0〜2再生なので、その日に長尺が
   1本あるかどうかだけで中央値が動きます。**本数の話ではありません**
2. **公開時刻を1点で決めないこと** —— `hours` は読みごとに丸められています
3. **符号は「変化」で出すこと** —— 上がった段を `-50%` と出すと、
   **下がったように読めます**（実際に1度そう出しました）
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import per_day_views as pdv  # noqa: E402

JST = timezone(timedelta(hours=9))


def _pt(hours: float, views: int, at: str):
    return (hours, views, datetime.fromisoformat(at.replace("Z", "+00:00")))


def test_公開時刻は_at_から_hours_を引いて復元する():
    pts = [_pt(1.0, 10, "2026-08-20T01:00:00Z"),
           _pt(25.0, 900, "2026-08-21T01:00:00Z")]
    got = pdv.published_at(pts)
    assert got.strftime("%Y-%m-%d %H:%M") == "2026-08-20 09:00"


def test_公開時刻を1点で決めない():
    """1点だけ `hours` がずれていても、中央値なので引きずられない。"""
    pts = [_pt(1.0, 10, "2026-08-20T01:00:00Z"),
           _pt(2.0, 20, "2026-08-20T02:00:00Z"),
           _pt(99.0, 30, "2026-08-20T03:00:00Z")]     # ← 壊れた1点
    assert pdv.published_at(pts).date().isoformat() == "2026-08-20"


def test_近い読みを採る_ちょうどの点は無い():
    pts = [_pt(20.0, 800, "2026-08-21T05:00:00Z"),
           _pt(26.0, 900, "2026-08-21T11:00:00Z")]
    assert pdv.views_at(pts, 24.0) == 900          # 26 のほうが 24 に近い


def test_離れすぎた読みは採らない():
    pts = [_pt(2.0, 50, "2026-08-20T11:00:00Z")]
    assert pdv.views_at(pts, 24.0) is None


def test_長尺は外れる():
    """24時間で 2再生の長尺が、その日の中央値を動かさないこと。"""
    by_id = {
        "short1": [_pt(24.0, 900, "2026-08-20T09:00:00Z")],
        "short2": [_pt(24.0, 1100, "2026-08-20T09:00:00Z")],
        "long1": [_pt(24.0, 2, "2026-08-20T09:00:00Z")],
    }
    days = pdv.per_day(by_id, target=24.0, min_views=pdv.DEFAULT_MIN_VIEWS)
    vals = days["2026-08-19"] or days["2026-08-20"]
    assert sorted(vals) == [900, 1100]


def test_実データで段が1つ以上出る():
    """**0件で緑になる検査を作らないこと**（`docs/trigger_main.md` §4）。"""
    days = pdv.per_day(pdv._load(), target=24.0, min_views=pdv.DEFAULT_MIN_VIEWS)
    assert len(days) >= 5
    assert any(len(v) >= 3 for v in days.values()), "本数の段が1つも無い"
