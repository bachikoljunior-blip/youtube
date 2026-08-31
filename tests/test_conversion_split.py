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
