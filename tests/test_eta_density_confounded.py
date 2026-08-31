"""**「引き代なし」を、決まっていない枝の上で断定していないか。**

2026-08-26・最適化の回。`CLAUDE.md` の (イ) が禁じている形の実例です ——

> **「届きません」と印字するたびに、何を固定したせいでそう出たのかを
> 同じ行に並べる。裸の「届きません」を出さないこと。**

`src/day_cap.py` の `window()` は**毎回** `confounded=True` と言っています。
同じ生データに当てはまる説明が2つあり、測れている日はどれも同じ数を出すからです:

    (A) 1日 C本 まで              早く置いても後ろが死ぬ。差し引き 0
    (B) T までに出した本は全部生きる  T より前に置いたぶんは丸ごと上積み

ところが `cap()` は (A) の数だけを返し、`scripts/eta.py` の `physical_caps` は
それだけを読んで

    density 天井 ×1.00 …… **すでに上限を 1.8倍 超えて出しています ＝ 引き代なし**

と印字していました。**分かっていないほうの枝を、断定して印字しています。**
賭かっているのは小さくありません —— (A) なら腕は死に、(B) なら **×1.8**
（**作る本数は1本も増えず**、置く時刻を変えるだけ）。

**`factor` は (A) のままにします。** 測っていない (B) で軌跡を歩かせると、
`physical_caps` の docstring が禁じている「実在しない世界」をそのまま歩きます。
**この検査が縛るのは印字だけ**です。

**覆る条件**: 08/27 の切り分けの日が答え、`window()["confounded"]` が False に
なったら `cap_if_window()` は `None` を返し、この検査は自動で黙ります
（`test_silent_once_decided`）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(spec)
spec.loader.exec_module(eta)

import _eta_pin  # noqa: E402


# --- **オーナーの規則（1日1本）は、この file の主題ではありません**（2026-08-31）---
#
# `src/house_rule.PUBLISH_PER_DAY = 1` が乗ると `sustained_density()` は
# `min(1, 続けられる速さ)` ＝ 1.0 を返し、`density` の腕の伸びしろは ×1.0 になります。
# **それは正しい振る舞いです**（規則の外の世界を軌跡に歩かせないための天井）。
# 落ちたのは形ではなく「合成データが、腕の動く帯に居るか」だけ ——
# `_eta_pin` の冒頭にある day_cap / rpm_mix / subs_cap と**同じ壊れ方の4回目**です。
# **規則の効きは `tests/test_house_rule.py` / `tests/test_density_cap.py` が持ちます。**
@pytest.fixture(autouse=True)
def _no_house_rule_ceiling(monkeypatch):
    _eta_pin.pin_house_rule(monkeypatch, eta, _eta_pin.PLAN_DENSITY)


from src import day_cap  # noqa: E402


def test_cap_if_window_is_derived_not_written_down():
    """(B) の数は、その場の実物から出ていること（**書き写しを禁じる**）。"""
    fork = day_cap.cap_if_window()
    if fork is None:
        return                      # 切り分け済み。下の検査が本体
    w = day_cap.window()
    assert fork["T"] == w["T"], "T は window() のものを使うこと"
    assert fork["step_min"] == int(day_cap.MIN_GAP_MIN), (
        "きざみは MIN_GAP_MIN（このファイルが既に持っている実測）を使うこと。"
        "2か所に同じ数を置かない")
    assert fork["measured"] is False, (
        "08:59 より早く公開した日がまだ無い以上、これは**測った天井ではありません**")
    span = int(fork["cap"]) - 1
    assert span * fork["step_min"] <= (
        int(fork["T"][:2]) * 60 + int(fork["T"][3:])
        - int(fork["earliest"][:2]) * 60 - int(fork["earliest"][3:])
    ), "枠の数が T を越えている"


def test_density_ceiling_names_the_branch_it_froze():
    """`density` の `why` が、(A) を固定したと**同じ行で**言っていること。"""
    caps = eta.physical_caps({}, supply=None)
    d = caps.get("density")
    if d is None:
        return
    fork = day_cap.cap_if_window()
    if fork is None:
        assert not d.get("confounded"), "切り分け済みなのに confounded が立っている"
        return
    assert d.get("confounded") is True
    why = d["why"]
    assert "confounded" in why, "どの道具がそう言っているかを名指しすること"
    assert "(A)" in why and "(B)" in why, "2つの枝を両方 出すこと"
    assert fork["answer_on"] in why, "**いつ決まるか**を書くこと（申し送りでは腐る）"
    assert d.get("answer_on") == fork["answer_on"]


def test_trajectory_still_walks_the_conservative_branch():
    """**軌跡は (A) のまま。** 測っていない (B) で歩かせないこと。"""
    caps = eta.physical_caps({}, supply=None)
    d = caps.get("density")
    if d is None or not d.get("confounded"):
        return
    arm_cap = min(float(eta.UPLOAD_CAP_PER_DAY), float(day_cap.cap()))
    density = eta.sustained_density(None, eta.PLAN_PUBLISH_PER_DAY)
    assert d["factor"] == max(1.0, arm_cap / density), (
        "factor が (B) を混ぜている。印字だけを変えること")
    # **(B) の側に引き代が無いこともあります**（2026-08-27 に測って分かった）。
    # ここは長らく `factor_if_window > factor` を**無条件で**要求していました
    # ——「(B) が (A) 以下なら、この節そのものが要らない」という理屈です。
    # **その前提のほうが外れました。** 05:00〜08:30 に置いた 8本 は全部 0再生で、
    # 窓の左端は 08:59。08:59〜13:30 は30分きざみで**ちょうど10枠** ＝ (A) と同じです。
    #
    # **節は要ります。** 要らなくなるのは「上振れがある」という**主張**のほうで、
    # そのときは**無いと言う**のが仕事です（次の回が、無い上振れを取りにいかないように）。
    if d["factor_if_window"] > d["factor"]:
        assert "(A)" in d["why"] and "(B)" in d["why"], "2つの枝を両方 出すこと"
    else:
        assert d["factor_if_window"] == d["factor"], "(B) が (A) を下回るのは数え方の誤り"
        assert "引き代はありません" in d["why"], (
            "(B) に上振れが無いなら、**そう言うこと** —— "
            "「切り分けが済んでいない」とだけ書くと、次の回が無い上振れを取りにいく")


def test_the_two_branches_are_measured_against_the_same_baseline():
    """(B) の倍率の分母は「再生が付く本数」であること。

    **作る本数（18.2本/日）と比べないこと。** 比べると ×0.99 と出て
    「(B) でも引き代なし」に見えますが、それは別の問いの答えです ——
    (B) が言っているのは「もっと作れ」ではなく「**いま死んでいる本を
    T より前に置き直せ**」。分母は `arm_cap`（いま T より前に居る本数）。
    """
    caps = eta.physical_caps({}, supply=None)
    d = caps.get("density")
    fork = day_cap.cap_if_window()
    if d is None or fork is None or not d.get("confounded"):
        return
    arm_cap = min(float(eta.UPLOAD_CAP_PER_DAY), float(day_cap.cap()))
    assert abs(d["factor_if_window"] - fork["cap"] / arm_cap) < 1e-9


def test_silent_once_decided():
    """切り分けが済んだら、この節は自動で消えること（手で消させない）。"""
    import inspect
    src = inspect.getsource(day_cap.cap_if_window)
    assert 'if not w.get("confounded")' in src, (
        "confounded=False になったら None を返すこと。"
        "でないと、決まった後もずっと「分かっていません」と言い続けます")
