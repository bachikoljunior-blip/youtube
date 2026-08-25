"""`density` の腕を、この窓でどう引くか（`_how_to_pull`）。

**守るのは1つです** —— **在庫が密度を支えていないなら、本数枠が開いていても
答えは「作る」**。

## なぜ検査で留めるか（2026-08-21 04:0x の実測）

ここは長らく**本数枠が開いているかどうかだけ**で決めていました。
本数枠は「今この窓で何本 API に通せるか」しか言っていません。ところが
`density` の腕が読んでいる入力は `supply.make_rate` ＝ **テーマが1日に
何本増えているか**です。**在庫から出すだけでは、その入力は動きません。**

08/21 03:1x の回は、本数枠が開（あと72本）でここが「出す」と言ったので、
在庫から10本を予約しました。`--reflect` の結果:

    make_rate_per_day: 22.85 → 21.2   （**下がった**）
    到達日（軌跡）: 2026-12-02 → 2026-12-02（**+0日**）

**腕を選ばせておいて、その腕を引けない道を案内していました。**
"""
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))


def _load():
    spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class _Cap:
    def __init__(self, remaining: int, closed: bool):
        self.remaining, self.closed = remaining, closed
        self.resets_at = datetime(2026, 8, 21, 16, 0, tzinfo=JST)


def _patch(monkeypatch, mod, cap, sp):
    from src import supply as supply_mod
    from src import upload_cap

    monkeypatch.setattr(upload_cap, "state", lambda: cap)
    monkeypatch.setattr(supply_mod, "sweep_novel", lambda: {"novel": 502})
    monkeypatch.setattr(supply_mod, "supply", lambda *a, **k: sp)


PLAN = {"lever_hint": "density", "density": 25.0, "days_to_target": 103}
THIN = {"measured": True, "holds": False, "days_covered": 3.6,
        "sections_per_run_needed": 1.0}
ENOUGH = {"measured": True, "holds": True, "days_covered": 40.0,
          "sections_per_run_needed": 1.0}


def test_在庫が支えないなら本数枠が開いていても作る(monkeypatch):
    m = _load()
    _patch(monkeypatch, m, _Cap(72, False), THIN)
    line = m._how_to_pull(PLAN)
    assert "「作る」" in line
    assert "「出す」" not in line
    assert "3.6日ぶん" in line          # 何日ぶんなのかを数で言う


def test_在庫が支えていて枠も開いていれば出す(monkeypatch):
    m = _load()
    _patch(monkeypatch, m, _Cap(72, False), ENOUGH)
    line = m._how_to_pull(PLAN)
    assert "「出す」" in line


def test_枠が閉じていれば作る(monkeypatch):
    m = _load()
    _patch(monkeypatch, m, _Cap(0, True), ENOUGH)
    line = m._how_to_pull(PLAN)
    assert "「作る」" in line


def test_まだ測っていない在庫では本数枠の判断に戻す(monkeypatch):
    """`measured=False` は「支えていない」ではありません。**取り違えないこと。**"""
    m = _load()
    _patch(monkeypatch, m, _Cap(72, False),
           {"measured": False, "holds": False, "days_covered": None,
            "sections_per_run_needed": float("nan")})
    line = m._how_to_pull(PLAN)
    assert "「出す」" in line


def test_腕がdensityでなければ何も言わない(monkeypatch):
    m = _load()
    _patch(monkeypatch, m, _Cap(72, False), THIN)
    assert m._how_to_pull({**PLAN, "lever_hint": "per_video"}) is None
