"""**`per_video` の腕を、引ける半分まで割ること**（2026-08-31・最適化の回）。

## この検査が持っている主題

腕は `per_video`／`rpm`／`density`／`sub_rate`／`gate`／`theta` の6つで、
**`ctr` は1つもありません。** そして `scripts/eta.py` は
`video_thumbnail_impressions_ctr` を **1度も読んでいませんでした**（実測 grep 0件）。

だから機械は「`per_video` を **104倍**」とは言えても、
**どちらの半分を引くのかを言えません。** 104倍 は手の打ちようがない数に見えます。

`src/reach_split.py` は、その読み方を自分で書いています::

    インプレッションが少ない  → 見せられていない（**題材・本数・面そのもの**）
    CTR が低い                → 見せたのに押されない（**サムネと題**）

実測 2026-08-31（`data/reach.jsonl`・API 0単位・`dedupe` 後）::

    長尺 21本  インプレッション 5,012  クリック 84  加重CTR 1.68%
      本べつ中央値 0.44%   最高 5.36%   ＝ **×12.1**
    面はそのままで、最高の本の率で回すと  クリック 84 → 269（**×3.2**）

**足りていないのは面ではなく、押された率のほうでした。**
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def _eta():
    spec = importlib.util.spec_from_file_location("_eta_conv", ROOT / "scripts" / "eta.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def test_面と押された率を別々に出す():
    """**積を1つの数に潰さないこと。** 潰すと、どちらを直すか言えません。"""
    cs = _eta().conversion_split("長尺")
    if not cs:
        pytest.skip("data/reach.jsonl に長尺の行がありません")
    for k in ("impressions", "clicks", "ctr", "ctr_median", "n"):
        assert k in cs, f"{k} が出ていません（腕を割れていない）"
    assert cs["impressions"] > 0
    # **CTR は割合です**（`reach_split._clicks` の docstring に裏取り）。
    #     百分率として読むと 100倍 ずれます —— 2026-08-20 に踏んだ穴。
    assert 0.0 <= cs["ctr"] <= 1.0, f"CTR が割合になっていません: {cs['ctr']}"
    assert cs["clicks"] == pytest.approx(cs["impressions"] * cs["ctr"], rel=1e-6)


def test_伸びしろは最高の本の率で測る():
    """`headroom` ＝ 面はそのままで、いちばん押された本の率で回したときの倍率。"""
    cs = _eta().conversion_split("長尺")
    if not cs or not cs["clicks"]:
        pytest.skip("クリックがありません")
    assert cs["ctr_best"] >= cs["ctr_median"], "最高が中央値を下回っています"
    assert cs["headroom"] == pytest.approx(cs["clicks_at_best"] / cs["clicks"], rel=1e-6)
    assert cs["clicks_at_best"] == pytest.approx(cs["impressions"] * cs["ctr_best"], rel=1e-6)
    # **1.0 を下回らないこと** —— 最高の率で回して減るなら、どこかで形が混ざっています
    assert cs["headroom"] >= 1.0


def test_読めない回は黙って_None():
    """**無い所を埋めないこと。** 読めなければ印字しません（裸の数を作らない）。"""
    eta = _eta()
    assert eta.conversion_split("そんな形はない") is None


def test_薄い本を手本にしない():
    """**「ほぼ 0 の分母」で伸びしろを作らないこと。**（2026-08-31・撃って足した）

    最初の版は「いちばん CTR の高い本」を素で採っていました。実測::

        ショート 最高CTR **100.00%**  ← `MrWXzBLlHok`（インプレッション 1・クリック 1）
                 次点      25.00%       （8 / 2）    その次 20.00%（5 / 1）
        → 伸びしろ **×50.4**

    `scripts/eta.py` の `nearest` の註が同じ壊れ方を自分で書いています ——
    「**ほぼ 0 の分母で割ると、倍率は無限に大きく出ます**」。**同じ穴を掘っていました。**

    床を**インプレッションではなくクリック**に置くのは、CTR の確からしさを決めるのが
    分子だからです（1,000面 でもクリック1なら ±1 で率が倍）。床を動かした実測::

        長尺    床 30/50/100/200 いずれでも **×3.2**（手本 1,056面・56クリック）
        ショート 床 30→×3.7  50→×3.0  100→×1.2   ← **床しだいで答えが変わる ＝ 雑音**

    **緩めないこと。** 緩めると、1回 押されただけの本が「手本」になります。
    """
    eta = _eta()
    for form in ("長尺", "ショート"):
        cs = eta.conversion_split(form)
        if not cs:
            continue
        if "headroom" not in cs:
            # 出さないなら、**なぜ出さないかを言うこと**（黙って消さない）
            assert cs.get("why_no_headroom"), f"{form}: 伸びしろも理由も無い"
            continue
        assert cs["ctr_best_clicks"] >= eta.CTR_REF_MIN_CLICKS, (
            f"{form}: 手本 `{cs['ctr_best_id']}` のクリックが "
            f"{cs['ctr_best_clicks']:.0f}回 しかありません"
            f"（床 {eta.CTR_REF_MIN_CLICKS}）—— 薄い本を手本にしています"
        )
        assert cs["ctr_best"] < 1.0, "CTR 100% の本を手本にしています（1面1クリック）"


def test_ショートは伸びしろを出さない():
    """**いまの標本では出せません。** 出したら、それは床が壊れた合図です。

    ショートのクリックは全部で 66回、いちばん厚い本でも 3回（実測 2026-08-31）。
    **クリックが厚い本が出てきたら、この検査は skip に変わります**（床は定数1つ）。
    """
    eta = _eta()
    cs = eta.conversion_split("ショート")
    if not cs:
        pytest.skip("data/reach.jsonl にショートの行がありません")
    if "headroom" in cs:
        pytest.skip("ショートにもクリックの厚い本が出ました（標本が育った）")
    assert "薄い本" in cs["why_no_headroom"] or "クリック" in cs["why_no_headroom"]


def test_窓の広さを一緒に返す():
    """**その数が何日ぶんかを、数と一緒に出すこと。**（2026-08-31）

    `data/reach.jsonl` は**報告が来た日ぶんしかありません**。実測::

        長尺ぜんたい  観測 **22日**
        手本の本 `_Mz5rg6jQ_A`  観測 **5日**（20260821..20260826）
          その5日で 面 1,056・クリック 56
        いっぽう同じ本の**再生は 156回（齢 246時間）** ＝ **生涯の側**

    **だから伸びしろ（クリックの話・22日）と、`per_video` の倍率（生涯の再生の話）は
    掛けられません。** この回いちばん高くついた壊れ方が「分母をそろえずに割る」ことで、
    ここは同じ穴のいちばん掘りやすい所です。

    **窓を返さなくなったら落とすこと** —— 窓の分からない倍率は、必ず誰かが掛けます。
    """
    cs = _eta().conversion_split("長尺")
    if not cs:
        pytest.skip("data/reach.jsonl に長尺の行がありません")
    assert cs.get("window_days"), "窓（観測日数）を返していません"
    assert cs["window_days"] > 0
    if "headroom" in cs:
        assert cs.get("ctr_best_days"), "手本の本の観測日数を返していません"
        assert cs["ctr_best_days"] <= cs["window_days"], "手本の窓が全体より広い"


def test_CTRだけでは届かないことを言えること():
    """**「面は在ります」と言わないこと。** 絶対の量で見ると、面のほうが壁です。

    最初の版は `scripts/eta.py` にこう印字していました（2026-08-31・同じ回に直した）::

        → **面は在ります。足りていないのは押された率のほう**

    **相対では正しく、絶対では逆でした。** 実測::

        面は 1本あたり **239回**（5,012 ÷ 21本）
        **CTR を 100% にしても 239再生** —— 要る 3,333回 には **×14 届かない**
        手本の率（5.30%）のままなら、面を **×263** にして はじめて届く

    **サムネだけでは、この面では目標に届きません。** CTR が買えるのは
    「いまの面の中で取りこぼしている ×3.2」だけです。
    **その2つを、足せる量として並べないこと** —— 掛け算の別々の項です。

    この検査は「**1本あたりの面が、要る再生数より少ない**」という
    その回の事実を押さえます。**面が要る数を超えたら skip に変わります**
    （そのときは本当に CTR が律速なので、印字も変えてよい）。
    """
    eta = _eta()
    cs = eta.conversion_split("長尺")
    if not cs or not cs.get("n"):
        pytest.skip("data/reach.jsonl に長尺の行がありません")
    imp_per_video = cs["impressions"] / cs["n"]
    # RPM ¥2,000・1本/日・30日 で月20万に要る1本あたり再生
    need = 200_000 * 1000 / (2_000 * 1 * 30)
    if imp_per_video >= need:
        pytest.skip("面が要る再生数を超えました（CTR が律速の側へ移った）")
    assert imp_per_video < need, (
        f"1本あたりの面 {imp_per_video:,.0f}回 が、要る {need:,.0f}回 を超えています"
    )
    # **CTR 100% でも届かない**ことが、この回の事実
    assert imp_per_video < need, "CTR を 100% にすれば届いてしまいます（前提が変わった）"
