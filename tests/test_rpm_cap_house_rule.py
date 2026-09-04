"""**`rpm` の天井は、オーナーが固定した「1日1本」の下でも立つか。**（2026-08-31・最適化の回）

`scripts/eta.physical_caps` の docstring は、自分の仕事をこう書いています ——

    **腕を「実在する幅」で止める。（軌跡が実在しない世界を歩かないため）**

そこは `density` を `src/house_rule.PUBLISH_PER_DAY` で止めています。
**`rpm` だけが、規則を1度も見ていませんでした。**

実測（2026-08-31・`data/reach.jsonl` 42日・**API 0単位**）:

    `rpm_mix.surface_ceiling()` の面 ＝ **1,368.0回/日**（いちばん大きかった1日 20260821）
    その日に公開した長尺   ＝ **7本**（`reach_split.publishes_per_day`）
    オーナーが固定した規則 ＝ **1本/日**

**天井が、規則の 7倍 の供給の上に立っています。**
`trajectory.py` の供給の天井（×92）・`physical_caps` の `density`（×10）と
**同じ欠陥の3件目**です。

    置き方                                   面/日    実効RPM   倍率
    いま（最大の1日・7本 公開）             1,368.0   ¥1,252   ×59.77
    **規則 1本/日 × 公開1本あたり 320.6**    320.6   ¥  588   **×28.05**

**覆る条件**: オーナーが 1日1本 を自分の言葉で外したとき
（`src/house_rule.py` に原文を書き足して `PUBLISH_PER_DAY` を動かす）。
`per_day_rule` が上がれば `rule_capped()` は自動でゆるみ、
規則の下の面が元の天井を超えた時点で `None`（＝止めない）に戻ります。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import house_rule, reach_split, rpm_mix  # noqa: E402


#: `surface_ceiling()` が返す形の、最小の点。
POINT = {"imp_day": 1368.0, "long_share_max": 0.6145736619844859,
         "rpm_now": 20.95235634559735, "rpm_max": 1252.27, "factor": 59.7676,
         "imp_day_basis": "最大の1日", "imp_day_max_on": "20260821"}


def test_rule_capped_lowers_the_ceiling():
    """規則 1本/日 × 公開1本あたりの面 で、天井が下がること。"""
    r = rpm_mix.rule_capped(POINT, per_publish=320.5833333333333, per_day_rule=1.0)
    assert r is not None, "**規則で止まっていません。**7本 公開した日の面のままです"
    assert r["imp_day"] == pytest.approx(320.583, rel=1e-3)
    assert r["factor"] == pytest.approx(28.05, abs=0.05), (
        f"×28.05 のはずが ×{r['factor']:.2f}")
    assert r["factor"] < POINT["factor"], "止めたのに天井が下がっていません"
    assert "house_rule" in r["why"], "**どの規則で止めたかが `why` に出ていません**"


def test_rule_capped_returns_none_when_it_would_not_bind():
    """規則の下の面のほうが広いなら、止める意味はない ＝ `None`。

    **オーナーが 1日1本 を外したときに、ここが自動でゆるむ**ことの検査です。
    """
    assert rpm_mix.rule_capped(POINT, per_publish=320.58, per_day_rule=7.0) is None
    assert rpm_mix.rule_capped(POINT, per_publish=None, per_day_rule=1.0) is None
    assert rpm_mix.rule_capped(POINT, per_publish=0.0, per_day_rule=1.0) is None
    assert rpm_mix.rule_capped({}, per_publish=320.58, per_day_rule=1.0) is None


def test_rule_capped_scales_with_the_rule():
    """`PUBLISH_PER_DAY` が上がれば、天井もそのぶん上がること（据え置きの数まで）。"""
    a = rpm_mix.rule_capped(POINT, 320.583, 1.0)
    b = rpm_mix.rule_capped(POINT, 320.583, 2.0)
    assert a and b
    assert b["imp_day"] == pytest.approx(2 * a["imp_day"], rel=1e-6)
    assert b["factor"] > a["factor"]


def test_physical_caps_rpm_is_stopped_by_the_rule():
    """**この検査が本体です** —— `physical_caps` の `rpm` が規則を見ること。"""
    import eta as E

    caps = E.physical_caps({"sub_rate": 0.000317, "per_video_now": 100.0})
    rpm = caps.get("rpm")
    assert rpm, "`rpm` の腕がありません"
    if not rpm.get("rule_binds"):
        # 窓に長尺の公開が0本のときだけ、ここへ落ちます。
        # **黙って落ちないこと**が要件なので、断りが出ているかを見ます。
        assert "規則（1日1本）では止めていません" in rpm["why"], (
            "**規則で止めていないのに、そう名乗っていません。**"
            f" いまの why: {rpm['why'][:200]}")
        return
    assert "house_rule" in rpm["why"], (
        "**`rpm` の天井が、どの規則で止まったかを言っていません。**"
        f" いまの why: {rpm['why'][:200]}")
    before = rpm.get("factor_before_rule")
    assert before and rpm["factor"] < before, (
        f"止めたのに天井が下がっていません（{rpm['factor']:.2f} / 前 {before}）")


def test_the_max_day_really_broke_the_rule():
    """**前提のほうを検査する** —— 天井が読んでいる日が、本当に規則の外か。

    ## 2026-09-05: 前提が成り立たなくなりました（**消していません**）

    ここは「赤くなったら上の3件ごと消すこと」と書いていました。実際に
    `PUBLISH_PER_DAY` が 1 → 10 になった日に、前提が成り立たなくなります ——
    天井が読んでいる日の長尺の公開は **4本** で、規則 10本/日 の**中**です。

    **それでも消しません。** 上の3件が見ているのは「**規則が止めるとき、
    そう名乗って天井を下げるか**」という仕掛けのほうで、その仕掛けは
    規則が何本でも要ります（**規則がまた下がれば、すぐまた止める側になります**）。
    消すと、次に規則が下がった回に**誰も見ていない**状態で戻ります。

    **代わりに、前提が成り立っていない回は飛ばします** —— 前提の検査なので、
    前提が無い日に赤くしても、それは欠陥を指していません。

    **覆る条件**: 規則が「天井が読んでいる日の本数」より下がったら、
    この検査はまた本文を撃ちます（`skip` の行が消えます）。
    """
    rows = reach_split.dedupe(reach_split.load_rows())
    sm = reach_split.summary(rows, reach_split.long_ids())
    day = sm["長尺"].get("per_day_max_on")
    if not day:
        pytest.skip("面の帳面に長尺の日がありません")
    pubs = reach_split.publishes_per_day(reach_split.long_ids())
    n = pubs.get(day, 0)
    if n <= house_rule.PUBLISH_PER_DAY:
        pytest.skip(
            f"天井が読んでいる日 {day} の長尺の公開は {n}本 で、"
            f"規則 {house_rule.PUBLISH_PER_DAY}本/日 の中です"
            " —— **規則がこの本数より下がるまで、上の3件は止める側になりません**"
            "（仕掛けは残してあります。docstring を読むこと）")
    assert n > house_rule.PUBLISH_PER_DAY


# --------------------------------------------------------------------------
# **同じ欠陥の4件目** —— 段2 の「動かせる側」も、規則を見ていませんでした。
# --------------------------------------------------------------------------
def test_long_form_need_ratio_is_capped_by_the_rule():
    """**要る長尺の本数は、`day_cap` ではなく「規則との低いほう」で割ること。**

    段2（面の不足）の末尾は `day_cap.long_form()` の **6本/日** だけを読み、
    「要る 46.3本/日 は、その **7.71倍**」と印字したうえで、
    **「先に動かすのは天井のほう（`day_cap.long_form()` の覆る条件）」と
    次の手を名指し**していました。

    **その手は、規則の下では1日も効きません。** `day_cap.long_form()` を
    測り直して上限が 92本/日 と出ても、出せるのは **1本/日** のままです
    （`src/house_rule.PUBLISH_PER_DAY`・覆る条件なし）。
    **この機械でいちばん詳しい診断が、規則が禁じている作業を名指し**していました。

    実測 2026-08-31: **7.71倍 → 46.28倍**。名指しする手も `rpm` へ入れ替わります。

    **覆る条件**: オーナーが 1日1本 を自分の言葉で外したとき。
    そのとき律速は測った天井（`day_cap.long_form()`）へ戻り、文面も自分で戻ります。
    """
    import eta as E

    src = Path(E.__file__).read_text(encoding="utf-8")
    i = src.find("_rule_binds_long")
    assert i > 0, "段2 の「動かせる側」が、規則（`src/house_rule.py`）を見ていません"
    # 規則は `src.house_rule` から引くこと（数を写さない）。
    assert "_rule_long = float(house_rule.PUBLISH_PER_DAY)" in src, (
        "規則の数を写しています。出どころは `src/house_rule.py` の1か所")
    # **規則で閉じている枝では、`day_cap` を測り直す手を名指ししないこと。**
    # 文面は f-string で分かれているので、**1つのリテラルに収まる断片**で見ます。
    assert "を測り直す手は、" in src, (
        "規則で閉じているのに、`day_cap.long_form()` を測り直す手が"
        "まだ名指しされたままです")
    # 旧文面（測った天井を名指しする側）は**消さずに残す** ——
    # 規則が外れたらそちらへ戻るため。
    assert "先に動かすのは天井のほう" in src, (
        "規則が外れたときに戻る文面ごと消しています")


def test_long_form_cap_takes_the_lower_of_rule_and_measurement():
    """低いほうを採ること —— **規則が外れたら、測った天井へ戻る**こと。"""
    for cap_meas, rule, want in ((6.0, 1.0, 1.0), (6.0, 7.0, 6.0),
                                 (0.0, 1.0, 1.0), (6.0, 6.0, 6.0)):
        binds = (cap_meas <= 0) or (rule < cap_meas)
        got = rule if binds else cap_meas
        assert got == want, f"cap_meas={cap_meas} rule={rule} → {got}（{want} のはず）"
