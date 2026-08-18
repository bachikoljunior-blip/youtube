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


def test_山は格子の上に乗っていない():
    """**刻みが答えを決める形**（2026-08-19 に見つけた）。

    `peak()` は 10万円きざみの `rate_curve()` の上を `max` で取るだけで、
    山が幅1円しかないため**一度も本当の山を見ていませんでした**。
    """
    p = keihi.peak()
    assert p["所得"] == 1_390_200
    assert p["値打ち"] == 25_176
    assert f'{p["値打ち"]:,}円' in keihi.__doc__

    # 粗い格子は必ず低いほうを返す（＝この検査が守っているもの）
    coarse = max(keihi.rate_curve(step=100_000), key=lambda r: r["実効率"])
    assert coarse["所得"] == 1_400_000 and coarse["値打ち"] == 24_475
    assert coarse["値打ち"] < p["値打ち"]
    assert p["値打ち"] - coarse["値打ち"] == 701

    # 山は1円幅（両隣は必ず低い）
    for d in (-1, 1):
        assert keihi.marginal(p["所得"] + d)["実効率"] < p["実効率"]


def test_cliffはpeakの複製ではない():
    """2026-08-19 まで `cliff()` は `peak()` と1文字ちがわない複製でした。"""
    c = keihi.cliff()
    assert c["所得"] != keihi.peak()["所得"]
    assert c["所得"] - c["1円下の所得"] == 1          # 跳びは1円の中で起きる
    assert c["1円下の所得"] == 1_390_000
    assert c["値打ち"] - c["前の値打ち"] == 22_980
    assert round(c["上がり幅"] * 100, 1) == 229.8
    assert "22,980円" in keihi.__doc__


@pytest.mark.parametrize("shotoku, value, haba", [
    (1_089_994, 17_815, 7),
    (1_390_200, 25_176, 1),
    (1_651_800, 16_758, 1),
])
def test_軽減の段ごとの山は全部10円未満の幅(shotoku, value, haba):
    m = keihi.marginal(shotoku)
    assert m["値打ち"] == value
    n = 1
    while keihi.marginal(shotoku - n)["実効率"] == m["実効率"]:
        n += 1
    lo = shotoku - n + 1
    n = 1
    while keihi.marginal(shotoku + n)["実効率"] == m["実効率"]:
        n += 1
    assert shotoku + n - lo == haba
    assert f"{value:,}円" in keihi.__doc__


def test_docstringに書いた青色の差が実際と合っている():
    rows = keihi.aoiro_rows()
    diff = rows[0]["合計"] - rows[-1]["合計"]
    kokuho_diff = rows[0]["国民健康保険料"] - rows[-1]["国民健康保険料"]
    assert diff == 193_352
    assert kokuho_diff == 71_225
    assert f"{diff:,}円" in keihi.__doc__
    assert f"{kokuho_diff:,}円" in keihi.__doc__
