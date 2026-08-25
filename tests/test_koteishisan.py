"""`src/calc/koteishisan.py` —— 固定資産税（地方税法349条の3の2・351条・附則15条の6）。

**この表の主題は「1枚の土地の中で1㎡あたりの税額が何倍ちがうか」**です。
制度の説明はどれも「200㎡までが6分の1、超えた分は3分の1」で止まり、
**3つめの帯（家屋の床面積の10倍を超えた部分＝特例なし）を書きません。** 出すと次が出ます。

1. 1㎡あたりの単価は **1 : 2 : 6**。帯は2つでなく **3つ**
2. 面積を2倍にしたときの倍率は **2.00 → 3.00 → 2.25 → 4.33** と**単調でない**
3. 200㎡を使い切れるのは **床面積20㎡以上**の家だけ（決めているのは土地でなく家屋）
4. 免税点の崖は住宅用地なら帯によらず **6,000円**。**特例なしの 5,100円 が最も低い**
5. 新築3年間は **98㎡と49㎡が同額**。50㎡未満はどの広さでも**ちょうど2倍**の家と同額
6. 4年目の倍率は **120㎡まで平らな 2.00倍**、両端は 1.00倍（理由が正反対）
7. 都市計画税を足すと、住宅用地の有利さは **6.00倍 → 5.10倍**

**割合を float で持つと免税点の判定が逆になります**（`test_免税点は分数で判定している`）。
実際に落ちた欠陥なので、検査に残しています。
"""
from __future__ import annotations

import re
from fractions import Fraction

import pytest

from src.calc import _checks, koteishisan as kt


def test_制度の値の検査が通る():
    kt.check_tables()


# ---- 1. 帯は3つ ----------------------------------------------------------

def test_1平米あたりの単価は1対2対6():
    small = kt.unit_tax("小規模")
    assert kt.unit_tax("一般") == pytest.approx(small * 2)
    assert kt.unit_tax("特例なし") == pytest.approx(small * 6)


def test_帯は地積を過不足なく3つに割る():
    for area in (50, 200, 201, 999, 1_000, 1_001, 5_000):
        b = kt.bands(area, kt.FLOOR_BASE)
        assert sum(b.values()) == Fraction(area)
        assert all(v >= 0 for v in b.values())


def test_3つめの帯は家屋の床面積が決めている():
    # 同じ2,000㎡でも、家屋が広ければ特例なしの部分は消える
    assert kt.bands(2_000, 100)["特例なし"] == 1_000
    assert kt.bands(2_000, 200)["特例なし"] == 0


def test_小規模は200平米で頭打ち():
    for area in (200, 500, 10_000):
        assert kt.bands(area, 1_000)["小規模"] == kt.SHOKIBO_AREA


# ---- 2. 面積2倍の倍率は単調でない ----------------------------------------

def test_面積2倍の倍率は単調でない():
    ratios = [r["税額の倍率"] for r in kt.double_grid()]
    assert ratios == [2.0, 3.0, 2.25, 4.33]
    # **山が2つ**（3.00 のあとに下がって、また上がる）
    assert ratios[1] > ratios[2] < ratios[3]


def test_同じ帯の中だけなら倍率はちょうど2倍():
    assert kt.land_tax(100) * 2 == pytest.approx(kt.land_tax(200))


def test_地積が増えれば税額は必ず増える():
    _checks.increases_with(lambda a: kt.land_tax(a, kt.FLOOR_BASE),
                           [50, 200, 201, 1_000, 1_001, 3_000], "地積と税額")


# ---- 3. 200㎡を使えるかは家屋が決める ------------------------------------

def test_200平米を使い切れる境目は床面積20平米():
    assert kt.residential_cap(20) == kt.SHOKIBO_AREA
    assert kt.residential_cap(19) < kt.SHOKIBO_AREA
    assert kt.residential_cap(21) > kt.SHOKIBO_AREA


def test_家が小さいほど同じ土地の税額は高い():
    taxes = [kt.land_tax(300, f) for f in (10, 19, 20, 30)]
    assert taxes == sorted(taxes, reverse=True)


def test_床面積30平米を超えると300平米の税額は変わらない():
    # 300㎡の土地では、床面積30㎡（上限300㎡）から先は形が変わらない
    assert kt.land_tax(300, 30) == pytest.approx(kt.land_tax(300, 200))


# ---- 4. 免税点 -----------------------------------------------------------

def test_免税点は分数で判定している():
    """**float で持つと 299,999.99999999994 になり、判定が逆になります。**"""
    base = kt.land_base(200, kt.FLOOR_BASE, 9_000)
    assert base == kt.MENZEI_LAND          # ちょうど300,000円（分数なので厳密）
    assert kt.land_tax(200, kt.FLOOR_BASE, 9_000) > 0
    assert kt.land_tax(200, kt.FLOOR_BASE, 8_999) == 0


def test_非課税でいられる評価額は帯で6倍ちがう():
    assert kt.menzei_limit("小規模") == pytest.approx(1_800_000)
    assert kt.menzei_limit("一般") == pytest.approx(900_000)
    assert kt.menzei_limit("特例なし") == pytest.approx(300_000)


def test_崖の高さは住宅用地なら帯によらず同額():
    assert kt.menzei_cliff("小規模") == pytest.approx(kt.menzei_cliff("一般"))
    assert kt.menzei_cliff("小規模") == pytest.approx(6_000)
    # **いちばん低いのは特例のまったく効かない土地**
    assert kt.menzei_cliff("特例なし") == pytest.approx(5_100)
    assert kt.menzei_cliff("特例なし") < kt.menzei_cliff("小規模")


# ---- 5. 新築の減額 -------------------------------------------------------

def test_50平米の崖は下向き():
    """1㎡広げると税額が半分近くまで下がる。**広いほうが安い。**"""
    assert kt.house_tax(50, 1) < kt.house_tax(49, 1)
    assert kt.house_tax(50, 1) / kt.house_tax(49, 1) == pytest.approx(0.5102, abs=1e-4)


def test_281平米の崖は上向き():
    assert kt.house_tax(281, 1) > kt.house_tax(280, 1)
    assert kt.house_tax(281, 1) / kt.house_tax(280, 1) == pytest.approx(1.2773, abs=1e-4)


@pytest.mark.parametrize("small", [30, 40, 45, 49])
def test_50平米未満はちょうど2倍の広さの家と同額(small):
    twin = kt.same_tax_floor(small)
    assert twin == pytest.approx(small * 2)
    assert kt.house_tax(twin, 1) == pytest.approx(kt.house_tax(small, 1))


def test_減額の対象なら同額になる相手は無い():
    assert kt.same_tax_floor(50) is None
    assert kt.same_tax_floor(120) is None


def test_減額は120平米までの部分にしか効かない():
    # 120㎡を超えた部分は、減額前後で同じ税額のまま増える
    step = kt.house_tax(200, 1) - kt.house_tax(150, 1)
    assert step == pytest.approx(50 * kt.HOUSE_UNIT * kt.KOTEI_RATE)


def test_4年目に減額が切れる():
    assert kt.house_tax(100, 3) < kt.house_tax(100, 4)
    assert kt.house_tax(100, 4) == pytest.approx(100 * kt.HOUSE_UNIT * kt.KOTEI_RATE)


# ---- 6. 4年目の倍率の形 --------------------------------------------------

@pytest.mark.parametrize("floor", [50, 60, 80, 100, 120])
def test_120平米までの倍率はちょうど2倍で平ら(floor):
    assert kt.year4_ratio(floor) == pytest.approx(2.0)


def test_120平米を超えると倍率は下がり続ける():
    _checks.decreases_with(kt.year4_ratio, [120, 130, 150, 200, 280],
                           "床面積と4年目の倍率")


def test_両端は同じ1倍で理由が逆():
    assert kt.year4_ratio(49) == 1.0     # 狭すぎて対象外
    assert kt.year4_ratio(281) == 1.0    # 広すぎて対象外
    assert kt.year4_ratio(50) == pytest.approx(2.0)
    assert kt.year4_ratio(280) == pytest.approx(1.2727, abs=1e-4)


# ---- 7. 実効税率 ---------------------------------------------------------

def test_小規模住宅用地の実効税率は300分の1():
    assert kt.effective_rate("小規模") == pytest.approx(1 / 3)


def test_都市計画税を入れると6倍が5点1倍に縮む():
    only = kt.effective_rate("特例なし", with_toshi=False) / \
        kt.effective_rate("小規模", with_toshi=False)
    both = kt.effective_rate("特例なし") / kt.effective_rate("小規模")
    assert only == pytest.approx(6.0)
    assert both == pytest.approx(5.1)
    assert both < only


def test_一般住宅用地は小規模のちょうど2倍():
    assert kt.effective_rate("一般") == pytest.approx(
        kt.effective_rate("小規模") * 2)


# ---- docstring の表を読んで突き合わせる ----------------------------------

def test_docstring_の単位つきの数は全部出力で裏が取れる():
    """**値は正しく、文だけが古いを構造で塞ぐ**（`_checks.numbers_backed`）。"""
    import io
    import contextlib
    import runpy
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_module("src.calc.koteishisan", run_name="__main__")
    _checks.numbers_backed(kt.__doc__, buf.getvalue(), name="koteishisan")


def test_docstring_の帯の表が実際の単価と合っている():
    rows = dict(re.findall(r"(200㎡まで|200㎡超〜1,000㎡|1,000㎡超)\s+"
                           r"評価額の?[^\s]*\s+([\d.]+)円", kt.__doc__))
    assert len(rows) == 3
    want = {"200㎡まで": "小規模", "200㎡超〜1,000㎡": "一般", "1,000㎡超": "特例なし"}
    for label, part in want.items():
        assert float(rows[label]) == pytest.approx(kt.unit_tax(part), abs=0.01)


def test_前提に値の書いていない仮定が無い():
    _checks.assumption_values(kt.ASSUMPTIONS, name="koteishisan")
