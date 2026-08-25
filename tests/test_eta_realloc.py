"""天井に着いた腕から、**回転を引き上げているか**。

2026-08-21 02:1x に足した。

`rate = focus_rate × share` の `share` は**実績の配分**（過去にどの腕を何回引いたか）で、
そこが固定だったので、**天井に着いた腕にも回転が回り続けて**いました。
実測では `per_video` の配分が 57%、その腕は ×1.57 で天井 ——
**回転の半分以上を、もう伸びない腕に永久に注ぐ世界**を歩いていました。

これは物理ではなく、この機械の振る舞いです。しかも毎回 `lever_hint` を読んで
腕を選び直しているのだから、固定するほうが手順と食い違っています。
"""
from __future__ import annotations

import importlib.util
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eta)


ARMS = {
    # すぐ天井に着く腕。配分の 3/4 を持っている
    "per_video": {"share": 0.75, "focus_rate": 0.10, "rate": 0.075, "cap": 1.10},
    # 天井の遠い腕。配分は 1/4 しかない
    "rpm": {"share": 0.25, "focus_rate": 0.10, "rate": 0.025, "cap": 100.0},
}


def test_capped_arm_hands_its_rotation_over():
    """`per_video` が天井に着いた後、`rpm` は**全部振ったときの速さ**で進むこと。"""
    t_cap = math.log(ARMS["per_video"]["cap"]) / (0.10 * 0.75)     # 約 1.27日
    t = 40.0
    got = eta._factors_at(ARMS, t)["rpm"]
    # 引き渡し前は share=0.25、引き渡し後は 1.0
    want = math.exp(0.10 * 0.25 * t_cap + 0.10 * 1.0 * (t - t_cap))
    assert abs(got - want) / want < 1e-6, (got, want)


def test_realloc_is_strictly_faster_than_the_frozen_split():
    """割り直した側が、**必ず速いか同じ**であること（遅くなったら符号が逆）。"""
    for t in (1.0, 5.0, 20.0, 100.0):
        a = eta._factors_at(ARMS, t)
        b = eta._factors_at(ARMS, t, realloc=False)
        assert a["rpm"] >= b["rpm"] - 1e-12, (t, a, b)
    assert eta._factors_at(ARMS, 100.0)["rpm"] > \
        eta._factors_at(ARMS, 100.0, realloc=False)["rpm"]


def test_nobody_passes_its_ceiling():
    """割り直しても、天井は越えないこと。"""
    f = eta._factors_at(ARMS, 10_000)
    assert f["per_video"] <= ARMS["per_video"]["cap"] + 1e-9
    assert f["rpm"] <= ARMS["rpm"]["cap"] + 1e-9


def test_focus_still_means_only_that_arm_moves():
    """`focus` の意味は変えていないこと（回転は1本）。"""
    f = eta._factors_at(ARMS, 10.0, focus="rpm")
    assert f["per_video"] == 1.0
    assert f["rpm"] > 1.0
