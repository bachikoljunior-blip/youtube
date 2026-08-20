"""`density` の伸びしろを、**天井が立っている密度**で割っているか。

2026-08-21 01:5x に踏んだ欠陥の再発防止。

段4 の天井は `per_video × density_sustained`（＝ `min(25, 作る速さ)`・実測 7.8本/日）で
立ちます。ところが `physical_caps` は伸びしろを `PLAN_PUBLISH_PER_DAY`（25本/日・**計画の数**）
で割っていました。分母が違うので、腕は

    7.8本/日 × (92 / 25) = 28.7本/日

で頭打ちになり、**実物の上限 92本/日 の 3.2分の1**しか歩けません。
軌跡が「腕を全部振っても出ません」と言っていた天井の、3.2倍ぶんが欠けていました。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eta)


def test_sustained_density_reads_the_sustained_rate():
    """`min(計画, 続けられる速さ)`。**バーストの `rate_per_day` では上書きしない。**"""
    assert eta.sustained_density({"sustained_rate_per_day": 7.8,
                                  "rate_per_day": 36.5}) == 7.8
    # 続けられる速さが計画より速いなら、頭打ちは計画のほう
    assert eta.sustained_density({"sustained_rate_per_day": 99.0}) == \
        eta.PLAN_PUBLISH_PER_DAY
    # 供給が読めない回は、前と同じ計画の数に落ちる（黙って 0 にしない）
    assert eta.sustained_density(None) == eta.PLAN_PUBLISH_PER_DAY
    assert eta.sustained_density({}) == eta.PLAN_PUBLISH_PER_DAY


def test_density_cap_is_measured_against_the_sustained_density():
    """**92 ÷ 7.8 であること。** 92 ÷ 25（＝計画の数）に戻ったら落とす。"""
    sup = {"sustained_rate_per_day": 7.8, "rate_per_day": 36.5}
    caps = eta.physical_caps({"sub_rate": 0.0004}, supply=sup)
    got = caps["density"]["factor"]
    assert abs(got - eta.UPLOAD_CAP_PER_DAY / 7.8) < 1e-9, got
    # 計画の数で割った側（×3.68）に戻っていないこと
    assert got > eta.UPLOAD_CAP_PER_DAY / eta.PLAN_PUBLISH_PER_DAY + 1e-9, got


def test_density_cap_lands_on_the_real_upload_cap():
    """腕を天井まで振ったとき、**実物の上限 92本/日 に着く**こと。"""
    sup = {"sustained_rate_per_day": 7.8}
    dens = eta.sustained_density(sup)
    caps = eta.physical_caps({"sub_rate": 0.0004}, supply=sup)
    assert abs(dens * caps["density"]["factor"] - eta.UPLOAD_CAP_PER_DAY) < 1e-9


def test_capped_arms_passes_supply_through():
    """`_capped_arms` が `supply` を落とすと、既定の 25 に黙って戻る。"""
    sup = {"sustained_rate_per_day": 7.8}
    arms = eta._capped_arms({"sub_rate": 0.0004}, arms={"density": {"cap": None}},
                            supply=sup)
    assert abs(arms["density"]["cap"] - eta.UPLOAD_CAP_PER_DAY / 7.8) < 1e-9
