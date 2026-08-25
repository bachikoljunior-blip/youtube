"""`src/calc/seimeihoken.py` —— 生命保険料控除。

**この表の主題は、所得税と住民税を「同時に」動かさないと1つも出ません。**

1. 表は4段ずつなのに、**手取りで見た段は6段**。折れ点が完全に交互に並ぶ
2. 頭打ちになる保険料が **80,000円と56,000円**で、あいだの24,000円は住民税が動かない
3. 区分ごとの上限×3 が、**住民税だけ**全体の上限を14,000円はみ出す
4. 同じ控除に届く保険料が、**払い方で16,000円ちがう**（所得税では0円）
5. 最初の1円と最後の1円の比は、**税率が低い人ほど大きい**（5%で12倍・45%で4.89倍）
6. 保険料6.67倍に対して、戻る額は2.87倍

**docstring の表そのものを読んで突き合わせています**（下の `test_docstring_*`）。
この repo は「値は正しく、文だけが古い」で4回落ちていて、
**この表を書いた回もその場で1件やりました**（節6の所得税控除を 66,000 と書いた。
実際は 86,001）。**人が書き写す欄がある以上、機械が読むしかありません。**
"""
from __future__ import annotations

import re

import pytest

from src.calc import _checks, seimeihoken as sh


def test_制度の値の検査が通る():
    sh.check_tables()


# ---- 節1: 段は6段。境目は交互 -------------------------------------------
def test_折れ点は6つで完全に交互():
    """**どちらか一方の表だけを見ていると、この6段は現れません。**"""
    bp = sh.breakpoints()
    assert [r["保険料"] for r in bp] == [12_000, 20_000, 32_000,
                                        40_000, 56_000, 80_000]
    assert [r["どちらの表"] for r in bp] == ["住民税", "所得税", "住民税",
                                            "所得税", "住民税", "所得税"]
    assert sh.breakpoints_alternate()


def test_表は4段ずつなのに手取りは6段():
    assert len(sh.INCOME_STEPS) == len(sh.RESIDENT_STEPS) == 4
    assert len(sh.marginal_levels()) == 6


def test_戻る額は下がりっぱなし():
    """途中で上がると「6段」の意味が変わります。"""
    levels = sh.marginal_levels()
    assert all(a > b for a, b in zip(levels, levels[1:]))
    assert levels[0] == pytest.approx(0.30)
    assert levels[-1] == pytest.approx(0.05)


@pytest.mark.parametrize("premium,income,resident", [
    (0, 0, 0),
    (12_000, 12_000, 12_000),
    (20_000, 20_000, 16_000),
    (32_000, 26_000, 22_000),
    (40_000, 30_000, 24_000),
    (56_000, 34_000, 28_000),
    (80_000, 40_000, 28_000),
    (200_000, 40_000, 28_000),
])
def test_段階表を引く(premium, income, resident):
    assert sh.income_deduction(premium) == income
    assert sh.resident_deduction(premium) == resident


def test_保険料が負なら止まる():
    with pytest.raises(ValueError):
        sh.income_deduction(-1)


# ---- 節2: 頭打ちの点が2つ -----------------------------------------------
def test_頭打ちの点は24000円ずれる():
    caps = sh.cap_points()
    assert caps["住民税が止まる保険料"] == 56_000
    assert caps["所得税が止まる保険料"] == 80_000
    assert caps["ずれ"] == 24_000


def test_そのあいだは住民税が1円も増えない():
    """**24,000円払って1,200円。**戻り率5.0パーセント。"""
    dz = sh.dead_zone()
    assert dz["払う額"] == 24_000
    assert dz["増える住民税控除"] == 0
    assert dz["増える所得税控除"] == 6_000
    assert dz["戻る額"] == pytest.approx(1_200)
    assert dz["戻り率"] == pytest.approx(0.05)


# ---- 節3: 上限の合計がはみ出す ------------------------------------------
def test_所得税はぴったり_住民税だけはみ出す():
    over = {r["制度"]: r for r in sh.cap_overflow()}
    assert over["所得税"]["はみ出す額"] == 0
    assert over["住民税"]["はみ出す額"] == 14_000
    # 14,000円は区分ごとの上限28,000円のちょうど半分＝実質2.5区分ぶん
    assert over["住民税"]["はみ出す額"] * 2 == sh.RESIDENT_CAP_PER_KIND
    assert over["住民税"]["使える区分の数"] == pytest.approx(2.5)


# ---- 節4: 払い方でちがう ------------------------------------------------
def test_住民税は寄せると16000円損する():
    split = {r["制度"]: r for r in sh.split_cost()}
    assert split["住民税"]["均等に払う"] == pytest.approx(112_000)
    assert split["住民税"]["寄せて払う"] == pytest.approx(128_000)
    assert split["住民税"]["差"] == pytest.approx(16_000)


def test_所得税は払い方によらない():
    """**区分ごとの上限×3 が全体の上限とぴったり同じ**なので差が出ません。"""
    split = {r["制度"]: r for r in sh.split_cost()}
    assert split["所得税"]["差"] == pytest.approx(0)
    assert split["所得税"]["均等に払う"] == pytest.approx(240_000)
    assert sh.INCOME_CAP_PER_KIND * sh.KINDS == sh.INCOME_CAP_TOTAL


# ---- 節5: 最初と最後の比 ------------------------------------------------
def test_比は税率が低いほど大きい():
    """**額では逆向き**（高税率ほど1円あたりの戻りは大きい）。"""
    grid = sh.first_last_grid()
    ratios = [r["比"] for r in grid]
    assert all(a > b for a, b in zip(ratios, ratios[1:]))
    firsts = [r["最初の1円"] for r in grid]
    assert all(a < b for a, b in zip(firsts, firsts[1:]))
    assert ratios[0] == pytest.approx(12.0)
    assert ratios[-1] == pytest.approx(44 / 9)


def test_最後の帯は所得税だけが効く():
    """住民税の傾きが0なので、戻るのは所得税ぶんの4分の1だけ。"""
    for rate in sh.INCOME_RATES:
        assert sh.first_last_ratio(rate)["最後の1円"] == pytest.approx(0.25 * rate)


# ---- 節6: 払った額と戻る額 ----------------------------------------------
def test_保険料は6_67倍_戻りは2_87倍():
    rows = sh.refund_grid()
    assert rows[0]["戻り率"] == pytest.approx(0.30)
    assert rows[-1]["戻る額"] == pytest.approx(31_000)
    paid = rows[-1]["保険料"] / rows[0]["保険料"]
    got = rows[-1]["戻る額"] / rows[0]["戻る額"]
    assert paid == pytest.approx(20 / 3)
    assert got == pytest.approx(31_000 / 10_800)
    assert paid > got


def test_全体の上限で切っている():
    """3区分とも8万円払っても、住民税の控除は70,000円で止まります。"""
    d = sh.total_deduction([80_000, 80_000, 80_000])
    assert d["所得税の控除"] == 120_000
    assert d["住民税の控除"] == 70_000   # 84,000 ではない


def test_区分の数がちがうと止まる():
    with pytest.raises(ValueError):
        sh.total_deduction([80_000, 80_000])


# ---- docstring と値の突き合わせ -----------------------------------------
#
# **人が書き写した欄は、必ず古くなります。**この表を書いた回そのものが
# 節6の所得税控除を書き間違えました（66,000 と書いて、実際は 86,001）。
# **値のほうは検査が守っているので、残る穴は文だけ**です。

_NUM = r"\*{0,2}([\d,]+(?:\.\d+)?)"


def _doc_rows(pattern: str) -> list[tuple[str, ...]]:
    return re.findall(pattern, sh.__doc__, re.M)


def test_docstring_節1の帯の表が値と合っている():
    rows = _doc_rows(
        r"^\s+([\d,]+)\s+〜\s+([\d,]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)円")
    bands = [b for b in sh.marginal_bands() if b["上限"] is not None]
    assert len(rows) == len(bands) == 6
    for (low, high, si, sj, back), band in zip(rows, bands):
        assert int(low.replace(",", "")) == band["下限"]
        assert int(high.replace(",", "")) == band["上限"]
        assert float(si) == pytest.approx(band["所得税の傾き"])
        assert float(sj) == pytest.approx(band["住民税の傾き"])
        assert float(back) == pytest.approx(band["1円あたり戻る額"])


def test_docstring_節5の税率の表が値と合っている():
    rows = _doc_rows(r"^\s+(\d+)%\s+([\d.]+)円\s+([\d.]+)円\s+" + _NUM + "倍")
    grid = sh.first_last_grid()
    assert len(rows) == len(grid) == len(sh.INCOME_RATES)
    for (pct, first, last, ratio), row in zip(rows, grid):
        assert int(pct) / 100 == pytest.approx(row["所得税率"])
        assert float(first) == pytest.approx(row["最初の1円"], abs=5e-4)
        assert float(last) == pytest.approx(row["最後の1円"], abs=5e-5)
        assert float(ratio) == pytest.approx(row["比"], abs=5e-3)


def test_docstring_節6の戻り率の表が値と合っている():
    """**この検査が、この回の書き間違いを実際に捕まえた形です。**"""
    rows = _doc_rows(
        r"^\s+([\d,]+)円\s+([\d,]+)円\s+([\d,]+)円\s+([\d,]+)円\s+([\d.]+)%")
    grid = sh.refund_grid()
    assert len(rows) == len(grid) == 3
    for (paid, inc, res, back, pct), row in zip(rows, grid):
        n = lambda s: float(s.replace(",", ""))
        assert n(paid) == pytest.approx(row["保険料"], abs=1)
        assert n(inc) == row["所得税の控除"]
        assert n(res) == row["住民税の控除"]
        assert n(back) == pytest.approx(row["戻る額"], abs=1)
        assert float(pct) / 100 == pytest.approx(row["戻り率"], abs=5e-5)


def test_docstring_節3の上限の表が値と合っている():
    rows = _doc_rows(
        r"^\s+(所得税|住民税)\s+([\d,]+)円\s+([\d,]+)円\s+([\d,]+)円\s+\*{0,2}"
        r"(−?[\d,]+)円")
    over = {r["制度"]: r for r in sh.cap_overflow()}
    assert len(rows) == 2
    for name, per, three, total, gap in rows:
        n = lambda s: int(s.replace(",", "").replace("−", "-"))
        assert n(per) == over[name]["区分ごとの上限"]
        assert n(three) == over[name]["3区分の合計"]
        assert n(total) == over[name]["全体の上限"]
        assert n(gap) == -over[name]["はみ出す額"] or n(gap) == 0


def test_前提に値が書いてある():
    """**「仮定です」と書いたら、その値を同じ行に書くこと。**"""
    _checks.assumption_values(sh.ASSUMPTIONS, name="seimeihoken")
