"""`src/calc/tsukin.py` —— 通勤手当の非課税限度額。

**この表の主題は3つ**で、どれも「限度額の表を写す」だけでは出ません。

1. 額でいちばん大きい崖は **2つあって同点**（15km と 25km）。率で聞くと 15km が単独
2. 1kmあたりの単価は**のこぎり**で、入口の高さそのものが単調ではない
3. 非課税でも厚生年金はかかり、**31,600円は等級の幅より大きいので必ずまたぐ**

docstring の数字も見ています —— この repo は
**「値は正しく、文だけが古い」で3回落ちています**（`docs/JOURNAL.md`）。
"""
from __future__ import annotations

import pytest

from src.calc import shahoken, tsukin


def test_制度の値の検査が通る():
    tsukin.check_tables()


# ---- 節1: 崖 -------------------------------------------------------------
def test_額の1位は2件で同点():
    """**1つを名指すと嘘になります。** 8/18 04:1x の「同名2つ」と同じ形。"""
    top = tsukin.biggest_cliffs_by_yen()
    assert [r["境目km"] for r in top] == [15, 25]
    assert {r["跳ぶ額"] for r in top} == {5_800}


def test_率の1位は単独で15km():
    """**額と率で答えが違う**ことが、この節の中身です。"""
    top = tsukin.biggest_cliff_by_ratio()
    assert top["境目km"] == 15
    others = [r["倍率"] for r in tsukin.cliffs()
              if r["倍率"] is not None and r["境目km"] != 15]
    assert all(x < top["倍率"] for x in others)


def test_2kmの崖だけ倍率が出ない():
    """手前が0円なので割れません。**外さずに数えると率の1位が壊れます。**"""
    first = tsukin.cliffs()[0]
    assert first["境目km"] == 2
    assert first["倍率"] is None


@pytest.mark.parametrize("km,limit", [(0, 0), (1.99, 0), (2, 4_200),
                                      (9.999, 4_200), (10, 7_100),
                                      (14.999, 7_100), (15, 12_900),
                                      (24.999, 12_900), (25, 18_700),
                                      (34.999, 18_700), (35, 24_400),
                                      (44.999, 24_400), (45, 28_000),
                                      (54.999, 28_000), (55, 31_600),
                                      (500, 31_600)])
def test_限度額は下限以上上限未満で読む(km, limit):
    """**境目は「以上・未満」です。** 55.0km は 31,600円の側に入ります。"""
    assert tsukin.car_limit(km) == limit


# ---- 節2: 単価 -----------------------------------------------------------
def test_単価の最大と最小はちょうど5倍():
    ex = tsukin.per_km_extremes()
    assert ex["最大の単価"] == pytest.approx(2_100.0)
    assert ex["最小の単価"] == pytest.approx(420.0, abs=0.1)
    assert ex["比"] == pytest.approx(5.0, abs=1e-3)


def test_入口の単価は単調に下がらない():
    """**「遠いほど1kmあたりは安い」は成り立ちません。**10km→15kmで上がります。"""
    assert tsukin.entry_prices_are_monotone() is False
    rows = {r["帯の入口km"]: r["入口の単価"] for r in tsukin.per_km_grid()}
    assert rows[15] > rows[10]


def test_上限のない帯は出口を持たない():
    """**最小を取るときに外していないと、0円/kmに漸近して壊れます。**"""
    last = tsukin.per_km_grid()[-1]
    assert last["帯の入口km"] == 55
    assert last["出口の単価"] is None


# ---- 節3: 非課税でも厚生年金はかかる ------------------------------------
def test_31600円は等級の幅より大きいので必ずまたぐ():
    """**この節の主題。** 逃げ道が無いことそのもの。"""
    assert max(tsukin.grade_widths()) == 30_000
    assert tsukin.always_crosses(tsukin.TOP_ALLOWANCE) is True
    assert tsukin.pension_zero_rows(tsukin.TOP_ALLOWANCE) == []


def test_4200円は幅より小さいので分かれる():
    """**手当が小さいうちは運です。**全部が0でも全部が非0でもない。"""
    assert tsukin.always_crosses(tsukin.SMALL_ALLOWANCE) is False
    rows = tsukin.pension_grid(tsukin.SMALL_ALLOWANCE, step=1_000)
    zero = tsukin.pension_zero_rows(tsukin.SMALL_ALLOWANCE, step=1_000)
    assert 0 < len(zero) < len(rows)


def test_報酬月額30万の代表値():
    """docstring に出している数字。**文と値がずれたらここで止まります。**"""
    p = tsukin.pension_increase(tsukin.BASE_MONTHLY)
    assert p["標準報酬月額(前)"] == 300_000
    assert p["標準報酬月額(後)"] == 340_000
    assert p["増える年額"] == 43_920
    assert p["手当に対する割合"] == pytest.approx(0.11582, abs=1e-5)


def test_増える年額は3通りしかない():
    """docstring の表が3行であることの裏。**増えたら文を直すこと。**"""
    assert sorted({r["増える年額"] for r in tsukin.pension_grid()}) == [
        21_960, 32_940, 43_920]


def test_実際にかかる割合は保険料率の上下に散らばる():
    """**率は9.15パーセントの一定なのに、手当に対しては一定になりません。**"""
    ratios = [r["手当に対する割合"] for r in tsukin.pension_grid()]
    assert min(ratios) < shahoken.HALF < max(ratios)
    assert tsukin.pension_over_rate_rows()


# ---- 節4: 手段の差 -------------------------------------------------------
def test_電車とマイカーの上限は4_75倍():
    g = tsukin.mode_gap()
    assert g["月の差"] == 118_400
    assert g["年の差"] == 1_420_800
    assert g["倍率"] == pytest.approx(4.7468, abs=1e-4)
    assert g["併用したとき定期券に回せる額"] == 118_400


# ---- 節5・6: 実費と頭打ち ------------------------------------------------
def test_自腹になるのは3か所だけ():
    """**「遠い人ほど損」ではありません。**近い人と9km台と68km以上だけ。"""
    wins = tsukin.short_windows()
    assert len(wins) == 3
    assert wins[0]["限度額"] == 0
    assert wins[1]["自腹の始まり"] == pytest.approx(9.0)
    assert wins[2]["自腹の始まり"] == pytest.approx(67.714, abs=1e-3)


@pytest.mark.parametrize("km", [10.0, 12, 15, 25, 35, 45, 55, 67.0])
def test_10kmから67kmまでは実費を上回る(km):
    assert tsukin.coverage(km)["まかなう割合"] > 1.0


@pytest.mark.parametrize("km", [1.0, 9.5, 9.99, 70, 100, 200])
def test_自腹の範囲では実費を下回る(km):
    assert tsukin.coverage(km)["まかなう割合"] < 1.0


def test_55km以上は距離という軸が消える():
    rows = tsukin.flat_top_grid()
    assert len({r["限度額"] for r in rows}) == 1
    assert tsukin.car_limit(55) == tsukin.car_limit(200) == 31_600
    # 距離が伸びるほど、まかなう割合だけが下がる
    ratios = [r["まかなう割合"] for r in rows]
    assert all(a > b for a, b in zip(ratios, ratios[1:]))


# ---- 表そのものの形 ------------------------------------------------------
def test_帯は隙間なく繋がっている():
    for (_, high, _), (low, _, _) in zip(tsukin.CAR_BANDS,
                                         tsukin.CAR_BANDS[1:]):
        assert high == low


def test_前提に値が書いてある():
    """**「仮定です」と書いたら、その値を同じ行に書くこと。**"""
    from src.calc import _checks
    _checks.assumption_values(tsukin.ASSUMPTIONS, name="tsukin")
