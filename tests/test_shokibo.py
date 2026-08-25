"""`src/calc/shokibo.py` —— 小規模企業共済。

**この表の主題は、「全額所得控除」と「20年未満は元本割れ」を
同じ表に並べないと1つも出ません。** どちらも一般の解説が言うことですが、
並べると次が出ます。

1. 節税額は所得税の帯で **3.6667倍**（126,000円 ↔ 462,000円）
2. 80パーセントを節税が埋める線は税率だけで決まらず、**掛けた額でも動く**
   （22.28% → 31.1%、上限は3分の1）。足りる帯が20%から23%に切り替わるのは **60か月**
3. 支給率が止まっているあいだは**まっすぐな下り坂**（毎月 -1,400円・54か月で赤）
4. 退職所得控除で無税にできる月額は、**掛金の上限70,000円に永久に届かない**
   （20年以下は33,333円で一定・漸近線は58,333円）
5. 控除が1年ぶん跳ぶ月が **38件**あり、跳びの大きさは **5種類**
6. 同じ額でも辞め方の名前で税額が **3.46倍**
7. いちばん深い段差は20年ではなく、**11か月と12か月のあいだ**（掛金1か月の8.53倍）

**docstring の表そのものを読んで突き合わせています**（下の `test_docstring_*`）。
この repo は「値は正しく、文だけが古い」で複数回落ちています。
"""
from __future__ import annotations

import re

import pytest

from src.calc import _checks, shokibo as sk


def test_制度の値の検査が通る():
    sk.check_tables()


# ---- 節1: 節税額は税率で決まる -------------------------------------------
def test_節税率は所得税率に住民税10パーセントを足したもの():
    for rate in sk.BRACKET_RATES:
        assert sk.combined_rate(rate) == pytest.approx(rate + 0.10)


def test_いちばん上といちばん下の節税額の比は3_6667倍():
    rows = sk.deduction_grid()
    assert rows[0]["年間の節税額"] == 126_000
    assert rows[-1]["年間の節税額"] == 462_000
    assert rows[-1]["年間の節税額"] / rows[0]["年間の節税額"] == pytest.approx(3.6667, abs=1e-4)


def test_実質の負担は税率が上がると減る():
    vals = [r["実質の負担"] for r in sk.deduction_grid()]
    assert vals == sorted(vals, reverse=True)


# ---- 節2: 分かれ目の線 ---------------------------------------------------
def test_分かれ目の節税率は掛けた額が増えると上がる():
    vals = [sk.break_even_rate(70_000, m) for m in (12, 24, 36, 48, 60, 72, 83)]
    assert vals == sorted(vals)
    assert vals[0] == pytest.approx(0.2228, abs=1e-4)
    assert vals[-1] == pytest.approx(0.3110, abs=1e-4)


def test_分かれ目の上限は3分の1で超えない():
    """**一時所得の特別控除50万円が一定なので、掛金が大きいほど3分の1に近づきます。**"""
    huge = sk.break_even_rate(70_000, 83)
    assert huge < 1 / 3
    # 特別控除が無ければちょうど 0.2/0.6 = 1/3 になる
    p = sk.total_paid(70_000, 83)
    got = int(p * 0.8)
    assert (p - got) / (p - got * 0.5) == pytest.approx(1 / 3, abs=1e-9)


def test_足りる帯が20から23に切り替わるのは60か月():
    rows = {r["掛けた月数"]: r for r in sk.break_even_grid()}
    assert rows[48]["足りる最低の所得税率"] == 0.20
    assert rows[60]["足りる最低の所得税率"] == 0.23


def test_分かれ目のすぐ上と下で符号が変わる():
    for months in (12, 36, 83):
        t = sk.break_even_rate(70_000, months)
        below = sk.net_after_kaiyaku(70_000, months, t - 0.10 - 0.005)
        above = sk.net_after_kaiyaku(70_000, months, t - 0.10 + 0.005)
        assert below["元本との差"] < 0 < above["元本との差"]


# ---- 節3: 下り坂 ---------------------------------------------------------
def test_80パーセントの区間はまっすぐな下り坂():
    b = sk.best_month(70_000, 0.20)
    assert b["いちばん得な月数"] == 12
    assert b["そのときの元本との差"] == 58_200
    assert b["1か月あたりの傾き"] == -1_400
    assert b["赤に転じる月数"] == 54
    assert b["83か月まで続けたときの差"] == -41_200


def test_傾きは掛金の20パーセントと節税の差で説明できる():
    """**-1,400 ＝ -70,000×0.2 ＋ 70,000×0.3 − 一時所得の税の増え方。**"""
    rows = sk.surplus_curve(70_000, 0.20)
    diffs = {b["元本との差"] - a["元本との差"] for a, b in zip(rows, rows[1:])}
    assert diffs == {-1_400}


# ---- 節4: 無税の月額上限 -------------------------------------------------
def test_20年以下の無税の月額上限は年数によらず一定():
    assert {sk.tax_free_monthly(y) for y in (2, 5, 10, 15, 20)} == {33_333}


def test_無税の月額上限は掛金の上限に永久に届かない():
    assert sk.tax_free_monthly(40) == 45_833
    assert sk.tax_free_monthly(10_000) < sk.TAISHOKU_UNIT_HIGH / 12 < sk.KAKEKIN_MAX


def test_上限まで掛けると受取時に必ず課税される():
    for years in (5, 10, 20, 30, 40):
        t = sk.taishoku_tax(70_000 * 12 * years, 12 * years)
        assert t["課税退職所得"] > 0
        assert t["税額"] > 0


# ---- 節5: 跳ぶ月 ---------------------------------------------------------
def test_240か月と241か月で勤続年数が1年ちがう():
    assert sk.service_years(240) == 20
    assert sk.service_years(241) == 21
    a = sk.taishoku_tax(70_000 * 240, 240)
    b = sk.taishoku_tax(70_000 * 241, 241)
    assert b["退職所得控除"] - a["退職所得控除"] == 700_000
    assert int(a["税額"]) == 892_500
    assert int(b["税額"]) == 798_000
    手取りの差 = (70_000 * 241 - b["税額"]) - (70_000 * 240 - a["税額"])
    assert int(手取りの差) == 164_500


def test_跳ぶ月は38件で大きさは5種類():
    jumps = sk.month_step_jumps()
    assert len(jumps) == 38
    sizes = sk.jump_sizes()
    assert [r["差し引き"] for r in sizes] == [24_750, 26_250, 33_000, 49_500, 94_500]
    assert [r["件数"] for r in sizes] == [7, 1, 6, 4, 20]
    assert sum(r["件数"] for r in sizes) == len(jumps)


def test_跳ぶのは12か月ごと():
    """**勤続年数が切り上げなので、13か月目・25か月目…で1年ぶん増えます。**"""
    months = [j["この月数で跳ぶ"] for j in sk.month_step_jumps()]
    assert all(m % 12 == 1 for m in months)


# ---- 節6: 辞め方の名前 ---------------------------------------------------
def test_同じ額でも辞め方の名前で税額が3_46倍():
    rows = sk.exit_kind_grid()
    assert {r["受取額"] for r in rows} == {8_400_000}
    assert rows[0]["税額"] == rows[1]["税額"] == 342_500
    assert rows[2]["税額"] == 1_185_000
    assert sk.exit_kind_ratio() == pytest.approx(3.46, abs=0.005)


def test_一時所得は掛金を経費に入れない():
    """**掛けた年に所得控除を受けているので、二重には引けません。**"""
    got = sk.ichiji_tax(8_400_000, 0.20)
    assert got["一時所得（課税分）"] == (8_400_000 - 500_000) * 0.5


# ---- 節7: 11か月と12か月 -------------------------------------------------
def test_11か月は掛け捨てで12か月から80パーセント():
    assert sk.kaiyaku_amount(70_000, 11) == 0
    assert sk.kaiyaku_amount(70_000, 12) == 672_000


def test_いちばん深い段差は20年ではなく最初の1年の入口():
    step = sk.cliff_step(70_000, 0.20)
    assert step["11か月の元本との差"] == -539_000
    assert step["12か月の元本との差"] == 58_200
    assert step["1か月で動く額"] == 597_200
    assert step["掛金の何倍"] == pytest.approx(8.53, abs=0.005)
    # 20年の線（支給率100パーセント）で動く額より大きいこと
    a = sk.net_after_kaiyaku(70_000, 239 + 1, 0.20)  # 240か月＝支給率100%
    b = sk.net_after_kaiyaku(70_000, 83, 0.20)
    assert step["1か月で動く額"] > abs(a["元本との差"] - b["元本との差"]) / 157


def test_84か月から240か月未満の支給率は計算しない():
    """**表に無い率を、こちらで作らないこと。**"""
    with pytest.raises(ValueError):
        sk.kaiyaku_amount(70_000, 120)


# ---- docstring を機械が読む ----------------------------------------------
def _doc() -> str:
    return sk.__doc__ or ""


def test_docstring_節税額の表が実際の値と合う():
    rows = {r["所得税率"]: r for r in sk.deduction_grid()}
    for line in _doc().splitlines():
        m = re.match(r"\s+(\d+)%\s+([\d.]+)%\s+([\d,]+)円\s+([\d,]+)円", line)
        if not m:
            continue
        rate = int(m.group(1)) / 100
        row = rows[rate]
        assert row["節税率"] * 100 == pytest.approx(float(m.group(2)), abs=1e-9)
        assert row["年間の節税額"] == int(m.group(3).replace(",", ""))
        assert row["実質の負担"] == int(m.group(4).replace(",", ""))


def test_docstring_分かれ目の表が実際の値と合う():
    rows = {r["掛けた月数"]: r for r in sk.break_even_grid()}
    found = 0
    for line in _doc().splitlines():
        m = re.match(r"\s+(\d+)か月\s+([\d,]+)円\s+([\d.]+)%", line)
        if not m:
            continue
        row = rows[int(m.group(1))]
        assert row["掛金累計"] == int(m.group(2).replace(",", ""))
        assert round(row["分かれ目の節税率"] * 100, 2) == pytest.approx(float(m.group(3)))
        found += 1
    assert found == 7


def test_docstring_無税の月額上限の表が実際の値と合う():
    rows = {r["掛けた年数"]: r for r in sk.tax_free_grid()}
    found = 0
    for line in _doc().splitlines():
        m = re.match(r"\s+(\d+)年\s+([\d,]+)円\s+([\d,]+)円\s+([\d,]+)円", line)
        if not m:
            continue
        row = rows[int(m.group(1))]
        assert row["退職所得控除"] == int(m.group(2).replace(",", ""))
        assert row["無税の月額上限"] == int(m.group(3).replace(",", ""))
        assert row["上限70,000円との差"] == int(m.group(4).replace(",", ""))
        found += 1
    assert found == 6


def test_docstring_跳びの一覧が実際の件数と合う():
    sizes = {r["差し引き"]: r for r in sk.jump_sizes()}
    found = 0
    for line in _doc().splitlines():
        m = re.match(r"\s+差し引き ([\d,]+)円 …\s+(\d+)件（(\d+)か月", line)
        if not m:
            continue
        row = sizes[int(m.group(1).replace(",", ""))]
        assert row["件数"] == int(m.group(2))
        assert row["最初の月"] == int(m.group(3))
        found += 1
    assert found == 5


def test_docstring_の数は全部この表のどこかに在る():
    """**単位つきの数だけを見ます**（`_checks.numbers_backed`）。"""
    import subprocess
    import sys
    out = subprocess.run([sys.executable, "-m", "src.calc.shokibo"],
                         capture_output=True, text=True).stdout
    src = open("src/calc/shokibo.py", encoding="utf-8").read()
    _checks.numbers_backed(_doc(), out + src, name="shokibo")


def test_前提に率の値が書いてある():
    _checks.assumption_values(sk.ASSUMPTIONS, name="shokibo")
