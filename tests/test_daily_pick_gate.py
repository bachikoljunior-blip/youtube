"""`daily_pick.gate_arithmetic` —— 形を「収益化の門の数」で数える行（2026-09-03 夜・最適化の回）。

`[きょうの1本]` は形を 齢48時間の再生（ショート 173回 対 長尺 1回）で並べ、外の作りの長尺の 24h が
門の下なら「その日はショート」へ倒していた。門（`scripts/eta.py`）は 長尺 4,000時間／ショート 1,000万回
で、**ショートの視聴時間は 4,000時間 に 0 入る**。この行は前提が閉じても消えない。API 0単位。
"""
from __future__ import annotations

import sys
from pathlib import Path

from src import daily_pick

ROOT = Path(__file__).resolve().parents[1]


def _cmp(short_rule=1049, short_recent=110, short_max=1864, long_life=4, long_max=196):
    st = lambda m, mx=None: {"n": 10, "median": m, "p90": m, "max": (mx if mx is not None else m)}  # noqa: E731
    return {
        "rule": {"ショート": st(short_rule), "長尺": st(1)},
        "recent": {"ショート": st(short_recent), "長尺": st(1)},
        "all": {"ショート": st(173, short_max), "長尺": st(1, 73)},
        "life": {"ショート": st(200), "長尺": st(long_life, long_max)},
        "rows": [],
    }


SNAP = {"long_hours_365": 3.1, "shorts_views_90d": 82991, "subs_net": 25}


def test_門の定数は_scripts_eta_と同じ():
    here = str(ROOT / "scripts")
    if here not in sys.path:
        sys.path.insert(0, here)
    import eta                                                   # noqa: PLC0415
    c = daily_pick._gate_constants()
    assert c["long_hours"] == eta.LONG_HOURS_GATE
    assert c["shorts_views"] == eta.SHORTS_VIEWS_GATE
    assert c["window_days"] == eta.LONG_HOURS_WINDOW_DAYS
    assert c["subs"] == eta.SUBS_GATE


def test_ショートは4000時間に0入り_1本あたりは1000万を90で割った数():
    g = daily_pick.gate_arithmetic(_cmp(), snapshot=SNAP, duration_min=20, frac=(0.16, 1))
    assert g["shorts"]["hours_to_gate2a"] == 0.0
    assert abs(g["shorts"]["need_per_video"] - 10_000_000 / 90) < 1e-6
    assert round(g["shorts"]["x_median"]) == round((10_000_000 / 90) / 1049)


def test_長尺の要る回数は残り時間を窓と視聴分で割った数():
    g = daily_pick.gate_arithmetic(_cmp(), snapshot=SNAP, duration_min=20, frac=(0.16, 1))
    l = g["long"]
    assert abs(l["left_hours"] - (4000 - 3.1)) < 1e-9
    per_day_h = (4000 - 3.1) / 365
    assert abs(l["need_per_video"] - per_day_h * 60 / (20 * 0.16)) < 1e-6
    assert l["frac_measured"] is True and l["frac_n"] == 1


def test_いまの数では長尺のほうが門に近い():
    g = daily_pick.gate_arithmetic(_cmp(), snapshot=SNAP, duration_min=20, frac=(0.16, 1))
    assert g["nearer"] == "長尺"
    assert g["long"]["x_median"] < g["shorts"]["x_median"]


def test_カーブが無ければ仮の割合を使いそう書く():
    g = daily_pick.gate_arithmetic(_cmp(), snapshot=SNAP, duration_min=20, frac=(None, 0))
    assert g["long"]["frac"] == daily_pick.ASSUMED_LONG_FRAC
    assert g["long"]["frac_measured"] is False
    lines = daily_pick.gate_lines(_cmp(), None, snapshot=SNAP, topics=[], cv={})
    joined = "\n".join(lines)
    assert "ASSUMED_LONG_FRAC" in joined
    assert "0 入る" in joined
    assert "門に近い形は **長尺**" in joined


def test_ショートの中央値が要る数に届けば向きは入れ替わる():
    g = daily_pick.gate_arithmetic(_cmp(short_rule=200_000), snapshot=SNAP, duration_min=20, frac=(0.16, 1))
    assert g["nearer"] == "ショート"


def test_long_watch_fraction_は長尺のカーブだけ平均する():
    rows = [{"video_id": "L1", "form": "長尺"}, {"video_id": "S1", "form": "ショート"}, {"video_id": "L2", "form": "長尺"}]
    cv = {"L1": [[0.1, 0.2, 0.5], [0.5, 0.1, 0.5]], "S1": [[0.1, 0.9, 0.5]], "L2": [[0.1, 0.4, 0.5]]}
    fr, n = daily_pick.long_watch_fraction(rows, cv)
    assert n == 2
    assert abs(fr - ((0.15 + 0.4) / 2)) < 1e-9
    assert daily_pick.long_watch_fraction([{"video_id": "S1", "form": "ショート"}], cv) == (None, 0)


def test_決めていない日の機械の形は門に近い側で_外の作りの下書きが先頭():
    assert daily_pick.fallback_form(_cmp(), snapshot=SNAP, topics=[], cv={}) == "長尺"
    assert daily_pick.fallback_form(_cmp(short_rule=200_000), snapshot=SNAP, topics=[], cv={}) == "ショート"
    tops = [{"id": "zaishoku-2026-62man", "style": "outside_long"}, {"id": "old-5min"}]
    pool = [{"video_id": "A", "topic": "old-5min"}, {"video_id": "B", "topic": "zaishoku-2026-62man"}]
    assert [p["video_id"] for p in daily_pick.outside_first(pool, tops)] == ["B", "A"]
