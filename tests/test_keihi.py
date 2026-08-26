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


# ---- 年齢だけで動く値打ち（2026-08-20 に足した節）------------------------
# **固定するのは「差 ＝ 介護分の所得割そのもの」の1点**です。
# 率が変わったら値も変わるので、数字を直書きせず率から出しています。

def test_介護分が乗る年齢と乗らない年齢で値打ちが所得割のぶんだけ違う():
    from src.calc import kokuho

    rate = kokuho.RATES["介護納付金分"]["所得割"]
    g = keihi.care_age_gap(5_000_000)
    assert g["差"] == round(keihi.STEP * rate)      # 1万円 × 2.25% ＝ 225円
    assert g["45歳の値打ち"] > g["39歳の値打ち"]


@pytest.mark.parametrize("age, kaigo", [
    (39, False), (40, True), (64, True), (65, False),
])
def test_境目は40歳と65歳(age, kaigo):
    from src.calc import kokuho

    base = keihi.marginal(5_000_000, age=39)["値打ち"]
    got = keihi.marginal(5_000_000, age=age)["値打ち"]
    assert (got > base) is kaigo
    assert (kokuho.KAIGO_FROM <= age <= kokuho.KAIGO_TO) is kaigo


def test_賦課限度額に当たった帯では年齢の差が消える():
    # 介護分が限度額（17万円）で止まっているので、経費を増やしても減らない。
    assert abs(keihi.care_age_gap(9_000_000)["差"]) <= 1
    assert abs(keihi.care_age_gap(12_000_000)["差"]) <= 1


def test_差が残るいちばん上の所得はゆらぎを拾わない():
    # **1円の差は端数処理のゆらぎ**（所得943万・946万…）。100円の床で外す。
    got = keihi.care_gap_vanishes()
    assert got == 7_900_000
    assert keihi.care_age_gap(got)["差"] >= 100
    assert keihi.care_age_gap(got + 100_000)["差"] < 100


# ---- 2026-08-26 に足した4節 --------------------------------------------
#
# **どれも「同じ結果が2つの理由から出る」形**です。値ではなく、
# その区別が消えていないかを見ています。


def test_経費が1円も効かない帯は所得割が立つ所得で終わる():
    ze = keihi.kokuho_zero_edges()
    ends = ze["下端が終わる所得"]
    # 帯の中では、経費1万円で負担が1円も減らない。
    assert keihi.marginal(ends - 1)["値打ち"] == 0
    # その1円上で跳ぶ。**跳びは1円の中で起きます。**
    assert keihi.marginal(ends)["値打ち"] > 0
    # 帯の出口は「青色控除後の所得が住民税の基礎控除ちょうど」の1円上。
    assert keihi.after_aoiro(ends - 1) == keihi.KISO_JUMIN


def test_国保が減らない理由は上端と下端で別物():
    lo = keihi.kokuho_zero_reason(1_000_000)
    hi = keihi.kokuho_zero_reason(12_000_000)
    assert lo["国保の減り"] == hi["国保の減り"] == 0
    assert lo["理由"] == keihi.ZERO_NO_SHOTOKUWARI
    assert hi["理由"] == keihi.ZERO_AT_LIMIT
    # **同じ「0」でも、値打ちは同じではありません。**
    assert lo["値打ち"] == 0
    assert hi["値打ち"] > 0


def test_member_limitは理由を持ち歩く():
    # **「賦課限度額に当たった点」とは限りません。**
    # 低い所得では所得割がそもそも0で、1人目から止まります。
    assert keihi.member_limit(1_000_000)["理由"] == keihi.ZERO_NO_SHOTOKUWARI
    for p in keihi.MEMBER_PROFITS:
        assert keihi.member_limit(p)["理由"] == keihi.ZERO_AT_LIMIT


def test_人数がふえた国保は単調で逆転しない():
    # 掃引が拾った「逆転 burden（合計）… members=6 が最大」は**目盛りの粗さ**。
    # 1人ずつ数えると単調にふえて、限度額で止まります。
    rows = keihi.member_cost()
    got = [r["国民健康保険料"] for r in rows]
    assert got == sorted(got)
    assert got[-1] == got[-2]          # 止まっている
    assert max(got) <= 1_130_000       # 賦課限度額の合計


def test_国保の増分は3割が税で戻り率は人数によらない():
    mr = keihi.member_cost_rate()
    assert 0.29 < mr["いちばん低い割合"] < 0.31
    assert 0.29 < mr["いちばん高い割合"] < 0.31
    assert mr["幅"] < 0.01             # 人数で動かない
    assert mr["止まるまでの正味"] < mr["止まるまでの国保のふえた額"]


def test_経費と控除の差の坂は控除の額とぴったり同じ幅():
    rp = keihi.keihi_ramp()
    assert rp["坂の幅"] == rp["額"]
    assert rp["差が0で終わる所得"] == keihi.JIGYOZEI_KOJO
    assert rp["満額になる所得"] == keihi.JIGYOZEI_KOJO + rp["額"]
    # 満額の1円下は、まだ満額ではない。
    assert rp["1円下の差"] < rp["満額の差"]


def test_天井は最高税率の段で止まる():
    cl = keihi.ceiling()
    steps = keihi.ceiling_steps()
    assert cl["速算表の税率"] == 45
    assert cl["値打ち"] == keihi.marginal(1_000_000_000)["値打ち"]
    # **段は上へ行くほど高い**（国保が消えたあとは速算表だけが動かす）。
    got = [r["値打ち"] for r in steps]
    assert got == sorted(got)
    # 天井の内訳: 国保は1円も効かない。住民税と事業税は所得で動かない。
    for r in steps:
        assert r["国保の減り"] == 0
        assert r["事業税の減り"] == int(keihi.STEP * keihi.JIGYOZEI_RATE)
        assert r["住民税の減り"] == int(keihi.STEP * keihi.JUMIN_RATE)
    # **速算表の税率そのものより、必ず高い**（この表の主題）。
    assert cl["実効率"] > 0.45
