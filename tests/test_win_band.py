# -*- coding: utf-8 -*-
"""**当たりの門が、枠の代金と並んでいること。**（2026-09-05 01:5x・毎時の回）

## この検査が守っているもの

`config/hypotheses.yaml` の前提「外の作り方を写した長尺」の**当たりの門は 100回**で、
その出どころは claim にそのまま書いてあります —— 「**いまの長尺の中央値 1回 の ×100**」。
**＝ 自分の記録だけで作った数（鏡）です。**

同じ枠をショートに使ったときの実測は **1,049回**（規則の密度・齢48h の中央値）。
＝ **101回 で「当たり」と読み、そこから形を長尺へ寄せると、測った数の上で
毎日 損を選ぶことになります。** 09/07 09:00 の判定は、この帯のどこに落ちるか次第です。

**この検査は門を1つも動かしません。** 「当たり」が2つに割れていること、
そして `unpaid`（＝ 前提は当たり・枠の代金は払えていない）が
**形を動かしてよいと言わないこと**だけを見ます。
"""
import math

import pytest

from src import slot_cost


def _sv(short_median, long_median=1.0):
    """`slot_value()` の形（返り値だけ）。API は撃ちません。"""
    return {
        "forms": {
            "ショート": {"n": 15, "median": short_median, "p90": None, "max": None},
            "長尺": {"n": 7, "median": long_median, "p90": None, "max": None},
        },
        "best": "ショート",
        "cost": short_median,
        "thin": ["長尺"],
        "hours": 48,
    }


def test_門をまたいでも枠の代金に届かない数は形を動かさない():
    """**101回 は前提の当たりだが、枠の代金は払えていない。**"""
    b = slot_cost.win_band(101, gate=100, sv=_sv(1049))
    assert b["band"] == "unpaid"
    assert b["may_move_form"] is False, (
        "101回 で形を長尺へ寄せてよいと言っています —— "
        "同じ枠のショートの実測 1,049回 に負けている数です"
    )
    assert "1,049" in b["line"], "譲る側の実測が、判定の1行に出ていません"


def test_枠の代金を越えた数だけが形を動かせる():
    b = slot_cost.win_band(1049, gate=100, sv=_sv(1049))
    assert b["band"] == "paid"
    assert b["may_move_form"] is True


def test_門を割った数は外れのまま():
    for v in (0, 16, 99):
        b = slot_cost.win_band(v, gate=100, sv=_sv(1049))
        assert b["band"] == "miss", v
        assert b["may_move_form"] is False, v


def test_帯の境目は3つの門で1度も重ならない():
    """**3帯は隙間なく、重なりなく並ぶこと。** どの数もちょうど1つの帯に落ちます。"""
    sv = _sv(1049)
    seen = []
    for v in (0, 99, 100, 101, 1048, 1049, 1050, 10 ** 6):
        b = slot_cost.win_band(v, gate=100, sv=sv)
        assert b["band"] in slot_cost.BANDS, (v, b["band"])
        seen.append(b["band"])
    # 単調（miss → unpaid → paid）で、戻らないこと。
    order = {"miss": 0, "unpaid": 1, "paid": 2}
    ranks = [order[x] for x in seen]
    assert ranks == sorted(ranks), seen


def test_門が枠の代金以上に置き直されたら帯は自分で2つに縮む():
    """**覆る条件がそのまま効くこと。** `unpaid` の幅が 0 になったら、その帯は出ません。"""
    sv = _sv(1049)
    for v in (1049, 2000):
        assert slot_cost.win_band(v, gate=1049, sv=sv)["band"] == "paid"
    for v in (100, 1048):
        assert slot_cost.win_band(v, gate=1049, sv=sv)["band"] == "miss"


def test_読めない数は推測で埋めない():
    """`None`・`nan`・字 は **帯を名乗らない**（`band=None`・`line` は空）。"""
    for v in (None, float("nan"), float("inf"), "たくさん"):
        b = slot_cost.win_band(v, gate=100, sv=_sv(1049))
        assert b["band"] is None, v
        assert b["line"] == "", v
        assert b["may_move_form"] is False, v


def test_枠の代金が測れない回はpaidを名乗らない():
    """**払えたことを、測らずに言わないこと。**"""
    b = slot_cost.win_band(10 ** 6, gate=100, sv=_sv(None))
    assert b["band"] == "unpaid"
    assert b["may_move_form"] is False
    assert b["cost"] is None


def test_台帳が101回で形を長尺へ寄せると書いていないこと():
    """**`config/hypotheses.yaml` に、鏡の門で形を動かす1行が残っていないこと。**

    09/05 01:5x まで、姉妹の前提（外の作りのショート）の `note` にこう在りました ——
    「**覆る条件**: `外の作り方を写した長尺` が当たった（48h で 100回 超え）なら、
    **形を長尺へ寄せる判断が先**」。**その1行が、101回 で枠を長尺へ寄せます。**
    """
    from pathlib import Path
    text = (Path(__file__).resolve().parent.parent
            / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    bad = "（48h で 100回 超え）なら、\n      **形を長尺へ寄せる判断が先**"
    assert bad not in text, (
        "100回 超えだけで形を長尺へ寄せる1行が台帳に在ります —— "
        "同じ枠のショートの実測（`slot_cost.slot_value()`）と並べること"
    )
    # 置き換えた側が在ること（消しただけで終わっていないこと）。
    assert "`slot_cost.win_band` の帯そのもの" in text
    assert "枠の代金は払えていない" in text


def test_実物のslot_valueでも帯が出ること():
    """**`sv` を渡さない実物の経路が落ちないこと。** API 0単位。"""
    b = slot_cost.win_band(101, gate=slot_cost.__dict__.get("_GATE", 100))
    assert b["band"] in slot_cost.BANDS or b["band"] is None
    if b["band"] is not None:
        assert isinstance(b["line"], str) and b["line"]


def test_daily_pickの読み出しに帯の行が入っていること():
    """**印字まで届いていること**（関数を足しただけで、画面に出ていない足を防ぐ）。"""
    from src import daily_pick as dp
    src = (dp.__file__)
    text = open(src, encoding="utf-8").read()
    assert "slot_cost.win_band" in text or "win_band(" in text, (
        "`daily_pick` が `win_band` を1度も呼んでいません —— "
        "帯は毎周の画面に出て初めて決定を変えます"
    )
