"""`src/calc/keihi.py` —— 経費1万円の値打ち。

**この表の主題は「速算表の税率では足りない」の1点**なので、
そこが崩れたら止まるようにしてあります。
docstring の数字も見ています —— この repo は
**「値は正しく、文だけが古い」で3回落ちています**（`docs/JOURNAL.md`）。
"""
from __future__ import annotations

import pytest

from src.calc import keihi


def test_制度の値の検査が通る():
    keihi.check_tables()


@pytest.mark.parametrize("profit", [2_000_000, 3_000_000, 5_000_000,
                                    7_000_000, 9_000_000, 12_000_000])
def test_実効率は速算表の税率より必ず大きい(profit):
    """**この表の主題。** 「税率ぶんだけ得」が小さすぎることそのもの。"""
    assert keihi.marginal(profit)["実効率"] > keihi.bracket_rate(profit)


def test_同じ税率の帯でも所得が多いほうが値打ちが小さい():
    """700万と900万は**どちらも速算表20パーセント**。それでも逆転します。"""
    low = keihi.marginal(7_000_000)
    high = keihi.marginal(9_000_000)
    assert keihi.bracket_rate(7_000_000) == keihi.bracket_rate(9_000_000) == 0.20
    assert high["実効率"] < low["実効率"]
    assert round((low["実効率"] - high["実効率"]) * 100, 2) == 2.25


def test_逆転は表の中に必ず1組はある():
    """**単調だと書いたら、それは嘘です。** 0組になったら節ごと直すこと。"""
    assert keihi.reversals()


def test_事業税の入口は青色申告特別控除を引く前で判定される():
    edge = keihi.jigyozei_edge()
    assert edge["事業税の入口（青色控除前）"] == keihi.JIGYOZEI_KOJO
    assert edge["そのときの事業所得（青色控除後）"] == 2_250_000
    assert keihi.business_tax(keihi.JIGYOZEI_KOJO) == 0
    assert keihi.business_tax(keihi.JIGYOZEI_KOJO + 100_000) > 0


def test_青色申告特別控除をいくら増やしても事業税は動かない():
    rows = keihi.aoiro_rows()
    assert len({r["事業税"] for r in rows}) == 1
    # そのかわり、他の3本は必ず減る
    assert rows[0]["所得税"] > rows[-1]["所得税"]
    assert rows[0]["住民税"] > rows[-1]["住民税"]
    assert rows[0]["国民健康保険料"] > rows[-1]["国民健康保険料"]


def test_払った経費より多く戻る所得がある():
    """国保の軽減の判定をまたぐ1点。**正味の費用がマイナスになります。**"""
    c = keihi.cliff()
    assert c["値打ち"] > keihi.STEP
    assert keihi.marginal(c["所得"])["正味の費用"] < 0


def test_率をそのまま足すと必ず多すぎる():
    for profit in (3_000_000, 5_000_000, 7_000_000, 9_000_000):
        got = keihi.chain_loss(profit)
        assert got["差"] > 0, profit
        assert got["実際の値打ち"] < got["素直な足し算"], profit


def test_国保が限度額に当たっていれば二重勘定は起きない():
    """**戻る道が無ければ、取り返しも0です。**"""
    got = keihi.chain_loss(12_000_000)
    assert keihi.kokuho_rate(12_000_000) == 0.0
    assert got["差"] == 0


def test_所得が増えれば負担の合計も増える():
    got = [keihi.burden(p)["合計"] for p in keihi.PROFITS]
    assert got == sorted(got)


DOC_ROWS = [
    (2_000_000, 2_654, 7_346),
    (3_000_000, 3_155, 6_845),
    (5_000_000, 3_614, 6_386),
    (7_000_000, 4_533, 5_467),
    (9_000_000, 4_308, 5_692),
    (12_000_000, 4_869, 5_131),
]


@pytest.mark.parametrize("profit,value,net", DOC_ROWS)
def test_docstringの表が実際の計算と合っている(profit, value, net):
    m = keihi.marginal(profit)
    assert m["値打ち"] == value
    assert m["正味の費用"] == net
    assert f"{value:,}円" in keihi.__doc__


def test_docstringに書いた崖の額が実際と合っている():
    c = keihi.cliff()
    assert c["所得"] == 1_400_000
    assert c["値打ち"] == 24_475
    assert "24,475円" in keihi.__doc__


def test_docstringに書いた青色の差が実際と合っている():
    rows = keihi.aoiro_rows()
    diff = rows[0]["合計"] - rows[-1]["合計"]
    kokuho_diff = rows[0]["国民健康保険料"] - rows[-1]["国民健康保険料"]
    assert diff == 193_352
    assert kokuho_diff == 71_225
    assert f"{diff:,}円" in keihi.__doc__
    assert f"{kokuho_diff:,}円" in keihi.__doc__
