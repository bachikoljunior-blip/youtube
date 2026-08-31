"""**門1 の「再生／日」が、規則の外の本数で作られていたら、そう言うこと**（2026-08-31）。

## この検査が持っている主題

**同じ1つの出力の中に、門1 の日付が 2つ ありました。**

    [門1] 登録者 1,000人   3.1年後 ＝ **1,140日**（2029-10-15）
    1日 1本 公開 → 門1     9.0年後 ＝ **3,296日**（2035-09-10） ← **規則。いまの計画はこの行**

**2,156日 ちがいます。** そして**頭の要約（`headline`）が引くのは上のほう**です。

差の出どころは、掛けている「再生／日」::

    上（1,140日）  `views_per_day` **2,724回/日** ＝ Analytics の実測（直近28日）
    下（3,296日）  `per_video_now × PUBLISH_PER_DAY` ＝ **942回/日**（規則 1本/日）

**測り方はどちらも正しい。** 食い違っているのは**本数**です ——
直近28日に実際に出たのは **1日 7〜34本**（予約の消化。控えは 359本）で、
**規則は 1日1本**（`src/house_rule.py`・オーナーが固定・**覆る条件なし**）。

## この検査が見ている3点

1. **規則の外の本数で作られた回に、断りが出ること**（＋ 規則の下の数が出ること）
2. **規則に収まっている回には、何も出さないこと**（片側だけの検査にしない）
3. **数を直していないこと** —— `views_per_day` は実測です。
   実測を模型で置き換えると、この機械は「測った」と「そう置いた」の区別を失います

**緩めないこと。** 消えた瞬間、頭の要約は**規則が禁じた本数で作られた日付**を、
断りなしで出し続けます。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _eta():
    spec = importlib.util.spec_from_file_location("etamod_g1", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_規則の外の本数で作られた再生には断りが出る():
    """**1 の検査。** 実測とほぼ同じ場（2,724 対 942）で撃ちます。"""
    eta = _eta()
    rule = float(eta.house_rule.PUBLISH_PER_DAY)
    a = {"per_video_now": 942.125, "views_per_day": 2724.1, "subs_per_day": 0.86}
    lines = eta.rule_sustain_lines(a)
    assert lines, (
        "いまの再生／日 が、規則の下で続く数の 2.89倍 なのに、断りが1行も出ません。"
        " **頭の要約は、規則が禁じた本数で作られた門1の日付を、断りなしで出しています**"
    )
    joined = "".join(lines)
    assert f"{942.125 * rule:,.0f}回" in joined, (
        f"規則の下で続く再生／日（{942.125 * rule:,.0f}回）が出ていません: {joined!r}"
    )
    # 規則の下の登録者の速さ ＝ 0.86 ÷ 2.89 ≈ 0.30
    assert "0.30人" in joined, (
        f"規則の下の速さ（1日 0.30人）が出ていません: {joined!r}"
    )


def test_規則に収まっている回は_何も言わない():
    """**2 の検査。** 片側だけを見る検査は、片側だけの証拠。

    ここが無いと、上の検査は「いつでも警告を出す」実装でも緑になります。
    """
    eta = _eta()
    rule = float(eta.house_rule.PUBLISH_PER_DAY)
    # 規則の下で続く数（per_video × rule）と、いまの再生／日 が同じ場
    a = {"per_video_now": 942.125, "views_per_day": 942.125 * rule,
         "subs_per_day": 0.30}
    assert eta.rule_sustain_lines(a) == [], (
        "規則に収まっているのに断りを出しています。**毎回 出る警告は、誰も読みません**"
    )


def test_門1の行から実際に呼ばれている():
    """**印字に繋がっていること。** 関数だけ在って呼ばれていない形を塞ぎます。

    **この repo でいちばん多い壊れ方は「言っている所と、している所が別」**です。
    `rule_sustain_lines()` を書いても、`report()` が呼んでいなければ 0行 と同じ。
    """
    eta = _eta()
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    body = src[src.index("[門1] 登録者"):]
    head = body[:1200]
    assert "rule_sustain_lines" in head, (
        "`[門1]` の印字のすぐ後ろで `rule_sustain_lines()` を呼んでいません。"
        " **関数だけ在って呼ばれていない**のは、無いのと同じです"
    )


def test_実測を模型で置き換えていない():
    """**3 の検査。** `views_per_day` そのものを書き換えていないこと。

    この関数は**文字列を返すだけ**で、`a` を触りません。
    触る実装に変わると、`analyse()` の返りが「測った数」でなくなります。
    """
    eta = _eta()
    a = {"per_video_now": 942.125, "views_per_day": 2724.1, "subs_per_day": 0.86}
    before = dict(a)
    eta.rule_sustain_lines(a)
    assert a == before, (
        f"`rule_sustain_lines()` が `analyse()` の返りを書き換えました: {before} → {a}。"
        " **実測を模型で置き換えないこと** —— 置き換えると、この機械は"
        "「測った」と「そう置いた」の区別を失います"
    )
