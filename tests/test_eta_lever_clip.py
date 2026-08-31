"""**「無限大にしても0日」を名乗れるのは、無限大が腕へ届いたときだけ。**

## なぜ要るか（2026-09-01・最適化の回に踏んだ）

`scripts/eta.py` は `LEVER_INF_SCALE`（×10^9）で腕を撃ち、日付が出なければ
`dead_at_inf` を立てて画面に

    **無限大にしても到達日が 0日 しか動かない腕が 3本 あります:
      `sub_rate`／`rpm`／`density`**（オーナー規則2: ゼロなら、そこは律速ではない）。
      **引かないこと。**

と印字していました。ところが `solve_gate1()` は 1行目で

    density = min(float(density), float(view_cap))   # view_cap = 10（`src/day_cap.py`）

と切ります。**×10^9 は腕まで届いていません。** 模型の中では ×10 で、
そこでの効き目は `per_video` ×10 と1ミリも変わりません（同じ `ceiling_day`）。
撃って出た数（2026-09-01・本番と同じ道）::

    density ×1     ceiling_day    942.1   ceiling_short 17.69
    density ×10    ceiling_day  9,421.3   ceiling_short  1.77
    density ×10^9  ceiling_day  9,421.3   ceiling_short  1.77   ← 切られている

切られた腕の「0日」は「効かない」ではなく「**そこで止められている**」です。
律速は腕ではなく**止めている物**（`day_cap` の 10本／`house_rule` の 1本）。
規則2 の名前でそれを「引かないこと」と印字すると、**読む側は止めている物を
見ません。** ここが落とすのは、その混ざり方が戻ったときです。

## この検査が落とす条件

1. `LEVER_EFFECT_KEY` の欄が `plan()` から消えた（対応表が腐った）
2. 切られている腕が、また `dead_at_inf` に混ざった
3. 画面の2行（`dead_at_inf` と `clipped`）が、1行に戻った

**覆る条件**: `solve_gate1` が `view_cap` で切るのをやめたら、
`density` は切られなくなります。そのときこの検査の 2. は
「切られている腕が無い」で通ります（`clip_at` が `None` になるだけ）。
**検査そのものを消さないこと** —— 切る経路は `rpm`（`RPM_SCENARIOS` の
帯の上端）にも在ります。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def _eta():
    spec = importlib.util.spec_from_file_location(
        "eta_for_clip_test", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def eta():
    return _eta()


def test_対応表の欄は全部_plan_が返す(eta):
    """`LEVER_EFFECT_KEY` が指す欄は、`plan()` の返りに実在すること。"""
    m = eta._points()[-1]
    a = eta.analyse(m)
    pl = eta.plan(m, a, sensitivity=False)
    missing = [(lev, key) for lev, key in eta.LEVER_EFFECT_KEY.items()
               if key not in pl]
    assert not missing, (
        f"`LEVER_EFFECT_KEY` の欄が `plan()` に在りません: {missing}。"
        "対応表が腐ると、切り所の挟み込みが黙って `None` を返します")


def test_腕は全部_対応表に居る(eta):
    assert set(eta.LEVERS) <= set(eta.LEVER_EFFECT_KEY), (
        "腕が増えたのに `LEVER_EFFECT_KEY` に足されていません。"
        "足さないと、その腕は切られていても `dead_at_inf` を名乗ります")


def test_切られている腕は_dead_at_inf_を名乗れない(eta):
    """`clip_at` が立った腕が `dead_at_inf` にも入っていたら落とす。"""
    m = eta._points()[-1]
    a = eta.analyse(m)
    pl0 = eta.plan(m, a, sensitivity=False)
    rows = eta.lever_days(m, a, pl0=pl0)
    both = [r["lever"] for r in rows
            if r.get("clip_at") and r.get("dead_at_inf")]
    assert not both, (
        f"{both} は模型の中で切られている（×10^9 が腕まで届いていない）のに、"
        "『無限大にしても0日 ＝ 律速ではない』を名乗っています。"
        "規則2 のゼロは、無限大が届いたときにしか言えません")


def test_density_を_view_cap_の上まで撃っても効き目が止まる(eta):
    """**切る経路そのもの**を、模型に撃って確かめる（写しではありません）。

    `solve_gate1` の `min(密度, view_cap)` が生きているかぎり、
    `density_month` は `view_cap` で頭打ちになります。
    """
    m = eta._points()[-1]
    cap = float(eta._view_cap_per_day())
    a_hi = eta.analyse(m, scale={"density": 1e9})
    pl_hi = eta.plan(m, a_hi, sensitivity=False)
    got = pl_hi.get("density_month")
    assert got is not None
    assert got <= cap + 1e-6, (
        f"density ×10^9 で `density_month`={got} —— `view_cap`={cap} を"
        "超えました。切る経路が変わったなら、`LEVER_EFFECT_KEY` の docstring と"
        "この検査の『覆る条件』を書き直すこと")


def test_画面は2つを別の行で言う(eta):
    """`dead_at_inf` の行と `clipped` の行が、1行に戻っていないこと。"""
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    assert "lever_clipped" in src, (
        "`lever_clipped` が消えました。切られている腕は、また"
        "『引かないこと』の側へ混ざります")
    assert "が腕まで届いていない腕が" in src, (
        "切られている腕を名指しする行が消えました")
