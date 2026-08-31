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
    for k in ("impressions", "clicks", "ctr", "ctr_median", "ctr_best", "headroom", "n"):
        assert k in cs, f"{k} が出ていません（腕を割れていない）"
    assert cs["impressions"] > 0
    # **CTR は割合です**（`reach_split._clicks` の docstring に裏取り）。
    #     百分率として読むと 100倍 ずれます —— 2026-08-20 に踏んだ穴。
    assert 0.0 <= cs["ctr"] <= 1.0, f"CTR が割合になっていません: {cs['ctr']}"
    assert 0.0 <= cs["ctr_best"] <= 1.0
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
