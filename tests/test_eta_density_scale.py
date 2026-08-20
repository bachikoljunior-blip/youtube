"""`density` の倍率が、**段4 の天井に本当に入っているか**。

2026-08-21 02:3x に踏んだ欠陥の再発防止。

`solve_gate1` は 2026-08-20 20:0x に、読む欄を `rate_per_day`（バーストが混じる）から
`sustained_rate_per_day`（1日続けられる速さ）へ移しました。ところが `plan()` 側は
**古い欄だけに倍率を掛けたまま**で、

    density_sustained = min(密度 × 倍率, sustained_rate_per_day)   ← 第2項が素通し

の第2項が動かず、天井 `per_video × density_sustained` に `density` の倍率が
**1ミリも入っていませんでした**。腕を天井（×11.79）まで振っても `7.8本/日` のまま ——
**引いても日付が動かない腕**でした。軌跡が「全部振っても出ません」と言っていた理由の1つです。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eta)


def _analysis():
    return {"videos_needed_gate1": 5_000, "days_subs_at": {}}


def test_scale_moves_the_sustained_rate():
    """倍率を掛けたら `density_sustained` が動くこと。**動かなければ腕が死んでいる。**"""
    a = _analysis()
    sup = {"sustained_rate_per_day": 7.8, "rate_per_day": 36.5, "stock": 20,
           "novel": 500}
    base = eta.solve_gate1(a, density=eta.PLAN_PUBLISH_PER_DAY, supply=sup)
    assert base["density_sustained"] == 7.8

    sup2 = dict(sup, sustained_rate_per_day=7.8 * 4, rate_per_day=36.5 * 4)
    up = eta.solve_gate1(a, density=eta.PLAN_PUBLISH_PER_DAY * 4, supply=sup2)
    assert up["density_sustained"] > base["density_sustained"], up["density_sustained"]
    assert abs(up["density_sustained"] - 31.2) < 1e-9, up["density_sustained"]


def test_plan_applies_the_density_scale_to_both_keys():
    """`plan()` が **両方の欄**に倍率を当てること（片方だけなら第2項で頭打ち）。"""
    seen: dict[str, dict] = {}
    real = eta.solve_gate1

    def spy(a, density, supply=None):
        seen["density"] = density
        seen["supply"] = dict(supply or {})
        return real(a, density=density, supply=supply)

    eta.solve_gate1 = spy
    try:
        a = {"per_video_now": 922.0, "scale": dict(eta.DEFAULT_SCALE, density=4.0),
             "videos_needed_gate1": 5_000, "days_subs_at": {}}
        try:
            eta.plan({}, a, supply={"sustained_rate_per_day": 7.8,
                                    "rate_per_day": 36.5, "stock": 0, "novel": 0},
                     sensitivity=False)
        except Exception:                       # plan() の先で落ちても、掛け値は見た
            pass
    finally:
        eta.solve_gate1 = real

    assert abs(seen["supply"]["sustained_rate_per_day"] - 7.8 * 4) < 1e-9, seen["supply"]
    assert abs(seen["supply"]["rate_per_day"] - 36.5 * 4) < 1e-9, seen["supply"]
    assert abs(seen["density"] - eta.PLAN_PUBLISH_PER_DAY * 4) < 1e-9, seen["density"]


def test_density_arm_at_its_cap_lands_on_the_upload_cap():
    """腕を天井まで振ったとき、天井の密度が **実物の上限 92本/日** に着くこと。"""
    a = _analysis()
    sup = {"sustained_rate_per_day": 7.8, "rate_per_day": 36.5, "stock": 0, "novel": 0}
    cap = eta.physical_caps({"sub_rate": 0.0004}, supply=sup)["density"]["factor"]
    sup2 = {k: (v * cap if k.endswith("rate_per_day") else v) for k, v in sup.items()}
    g1 = eta.solve_gate1(a, density=eta.PLAN_PUBLISH_PER_DAY * cap, supply=sup2)
    assert abs(g1["density_sustained"] - eta.UPLOAD_CAP_PER_DAY) < 1e-6
