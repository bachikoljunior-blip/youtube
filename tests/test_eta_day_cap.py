"""**段1 を押すのは、出した本数ではなく「再生が付いた本数」**（2026-08-21 16:2x）。

`scripts/eta.py` の `solve_gate1` は長らく `plan_density = PLAN_PUBLISH_PER_DAY`
（25本/日）をそのまま使い、**25本出せば 25本ぶんの登録者が来る**と読んでいました。

実測（`src/day_cap.py`・`data/views.jsonl`）:

    08/20 は 25本 公開して、**#11から先の15本が 0〜3再生**（#10 は 1,111再生）
    時刻ではなく**その日の通し番号**で割れる:
        08/16 の 14時 = #4  → 1,361再生
        08/20 の 14時 = #12 →     0再生

**これが `density` の腕の天井そのものです。** 天井を無視した側へ戻ると、
「本数を増やせば門が開く」と出て、**また在庫の作業へ戻ります**
（`tests/test_eta.py` が守っているのと同じ壊れ方の、別の入口）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_cap_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

from src import day_cap  # noqa: E402


def _a(need=2000.0):
    return {"videos_needed_gate1": need, "days_subs_at": {}, "scale": eta.DEFAULT_SCALE}


def _supply(rate=34.0, stock=36):
    return {"sustained_rate_per_day": rate, "rate_per_day": rate, "stock": stock,
            "novel": 500, "rate": {"thin": False}}


def test_上限を超えた密度は段1を早めない(monkeypatch):
    """**25本/日 と 10本/日 で、段1 の期日が同じであること。**

    上限が 10 なら、11本目から先は 0再生 ＝ 門を1ミリも押しません。
    ここが「25のほうが速い」に戻ったら、天井を素通ししています。
    """
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    at_10 = eta.solve_gate1(_a(), density=10, supply=_supply())["days"]
    at_25 = eta.solve_gate1(_a(), density=25, supply=_supply())["days"]
    at_92 = eta.solve_gate1(_a(), density=92, supply=_supply())["days"]
    assert at_10 == at_25 == at_92, "上限を超えたぶんが門を押しています"


def test_上限を無視した昔の読みより遅くなること(monkeypatch):
    """**直しの向きを固定します。** 天井を入れると期日は必ず**後ろ**へ動きます。

    予測が早まる向きに動いたら、それは直りではなく壊れです。
    """
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    capped = eta.solve_gate1(_a(), density=25, supply=_supply())["days"]
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 1_000)   # 天井なしと同じ
    uncapped = eta.solve_gate1(_a(), density=25, supply=_supply())["days"]
    assert capped > uncapped, "天井を入れたのに期日が早まっています"


def test_上限より低い密度はそのまま通ること(monkeypatch):
    """**天井は上から押さえるだけ。** 4本/日 を 10本/日 に水増ししないこと。"""
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    slow = eta.solve_gate1(_a(), density=4, supply=_supply())["days"]
    fast = eta.solve_gate1(_a(), density=10, supply=_supply())["days"]
    assert slow > fast


def test_段4の月あたり本数も天井を超えないこと(monkeypatch):
    """段4（月20万）は `density_sustained` で数えます。**そこも天井の内側**。"""
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    g1 = eta.solve_gate1(_a(), density=25, supply=_supply(rate=34.0))
    assert g1["density_sustained"] <= 10
