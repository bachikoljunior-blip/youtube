"""`scripts/eta.py` の `frozen_days()` —— **その腕を凍らせたら、軌跡は何日 遠のくか。**

## この検査が守っているもの（2026-08-26・最適化の回）

同じ日・同じ点・同じ台帳で、`eta.py` の2か所が**正反対**を印字していました:

    eta.py（腕の表）  **上の日付を動かせない腕: `sub_rate`／`density`**
                      —— **ここに前提を置いても、到達日は動きません**

    eta.py --alloc    **いちばん早いのは `sub_rate`**（そのままより **3日 早い**）
                      立てるときは `hypotheses.yaml` に `lever:` をその腕で書くこと

**「置いても動かない」と「次はここに置くのが最短」が、同じプログラムから同時に。**

前者は `lever_days()` の表で、**他の3本を今日の実測で凍らせたまま 1本だけを
天井まで引く**モデルです。`CLAUDE.md` がそれを名指ししています ——
「**凍らせた企画についての恒真式**であって、予測ではない」。

`frozen_days()` は、その取り違えを**測って**割ります。腕の `rate` を 0 にして
軌跡を解き直すと、`_factors_at()` はその腕を `live` から外し、
**空いた配分は残りの腕へ配り直されます** ＝
「**この腕に回していた回転を、全部よそへ回したら**」の線。
**それが「必要か」の問いの形**です（「十分か」ではありません）。

    差 > 0   凍らせると遠のく ＝ **必要な腕**（十分でなくても）
    差 = 0   回転をよそへ回しても同じ ＝ **要らない腕**
    差 None  base が届かない回など、比べられない
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_frozen_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _tr(base_days: float) -> dict:
    return {"base": {"days": base_days},
            "arms": {"per_video": {"rate": 0.05, "share": 0.5, "cap": 3.0},
                     "sub_rate": {"rate": 0.02, "share": 0.3, "cap": 100.0},
                     "density": {"rate": 0.01, "share": 0.2, "cap": 1.0}}}


def _patch(monkeypatch, days_by_frozen: dict[str, float]) -> list[str]:
    """`trajectory` を差し替えて、**どの腕が 0 に落ちたか**で日数を返す。"""
    seen: list[str] = []

    def fake(m, a0, **kw):
        arms = kw.get("arms") or {}
        cold = [k for k, v in arms.items() if not (v.get("rate") or 0.0)]
        assert len(cold) == 1, f"凍らせるのは1本だけ: {cold}"
        seen.append(cold[0])
        return {"days": days_by_frozen[cold[0]]}

    monkeypatch.setattr(eta, "trajectory", fake)
    return seen


def test_凍らせると遠のく腕は正の差で返る(monkeypatch):
    seen = _patch(monkeypatch, {"sub_rate": 230.0, "density": 115.0})
    out = eta.frozen_days({}, {}, _tr(115.0), ["sub_rate", "density"])
    assert out["sub_rate"] == 115.0, "凍らせると +115日 ＝ 必要な腕"
    assert out["density"] == 0.0, "凍らせても同じ ＝ 要らない腕"
    assert sorted(seen) == ["density", "sub_rate"]


def test_凍らせるのはその腕だけで_ほかの腕の速さは残る(monkeypatch):
    """**空いた配分は残りへ配り直されます**（`_factors_at` の `live`）。

    ここを「全部 0 にする」に変えると、測っているのは「腕が1本も動かない世界」に
    なり、**どの腕も必要に見えます**（＝ 何も判別しない検査）。
    """
    captured: list[dict] = []

    def fake(m, a0, **kw):
        captured.append(kw.get("arms") or {})
        return {"days": 200.0}

    monkeypatch.setattr(eta, "trajectory", fake)
    eta.frozen_days({}, {}, _tr(115.0), ["sub_rate"])
    arms = captured[0]
    assert arms["sub_rate"]["rate"] == 0.0
    assert arms["per_video"]["rate"] > 0, "よその腕の速さは残すこと"
    assert arms["density"]["rate"] > 0


def test_凍らせると届かなくなる腕は_地平で頭打ちにする(monkeypatch):
    """**`NEVER`（10億）をそのまま出さないこと。**

    「+1,000,000,000日」と印字されると、読み手はまず数字を疑い、
    **主張のほうを読みません。** 意味は変わりません ——
    「3年 先まで見ても戻ってこない ＝ 必要」。
    """
    _patch(monkeypatch, {"sub_rate": float(eta.NEVER)})
    out = eta.frozen_days({}, {}, _tr(115.0), ["sub_rate"])
    assert out["sub_rate"] == float(eta.TRAJECTORY_HORIZON_DAYS) - 115.0
    assert out["sub_rate"] < 10_000, "地平で頭打ちにすること"


def test_base_が届かない回では判定しない(monkeypatch):
    """**読めないことと「要らない」は別です。** `None` を返して、印字側に言わせる。"""
    _patch(monkeypatch, {"sub_rate": 999.0})
    assert eta.frozen_days({}, {}, _tr(float(eta.NEVER)), ["sub_rate"]) == {"sub_rate": None}
    assert eta.frozen_days({}, {}, {"base": {}, "arms": {}}, ["sub_rate"]) == {"sub_rate": None}


def test_解けなかった腕は_要らないではなく判定なし(monkeypatch):
    """**回を止めないこと。** ただし「0日」と嘘をつかないこと（＝要らない腕に見える）。"""
    def boom(m, a0, **kw):
        raise RuntimeError("解けません")

    monkeypatch.setattr(eta, "trajectory", boom)
    assert eta.frozen_days({}, {}, _tr(115.0), ["sub_rate"]) == {"sub_rate": None}
