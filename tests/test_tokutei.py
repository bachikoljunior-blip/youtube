"""`src/calc/tokutei.py` —— 特定支出控除（所得税法57条の2）。

**この表の主題は「敷居 ＝ 給与所得控除の2分の1」を年収べつに並べること**です。
制度の説明はどれも「2分の1を超えた分」で止まり、**その2分の1がいくらかを
年収の関数として出しません。** 出すと次が出ます。

1. 敷居は年収 8,500,000円 の **975,000円** で頭打ち。1,500万円の人と同額
2. 敷居の増え方は両端が **0円**で、真ん中（162.5万〜180万）が **200,000円/100万** と最急
3. 壁は下にも上にもあり**向きが逆**。**275,000円以下**は必ず 0円、
   **975,000円 超**はどの年収でも必ず引ける
4. 勤務必要経費の上限 650,000円 は、年収 **4,300,000円** で引ける額が 0円 になる
5. 節税額の山は年収がいちばん低い点ではなく、**引ける額を所得税で使い切る点**
   （特定支出 1,200,000円 で年収 2,457,143円・118,714円）
6. 敷居の対年収比が**増える帯は1つだけ**（16.923% → 17.222%）

**docstring の表そのものを読んで突き合わせています**（下の `test_docstring_*`）。
この repo は「値は正しく、文だけが古い」で複数回落ちています。
"""
from __future__ import annotations

import re

import pytest

from src.calc import _checks, tokutei as tk


def test_制度の値の検査が通る():
    tk.check_tables()


def test_給与所得控除は法定の6段でつながっている():
    # 境目の両側で値が飛ばないこと（1円ぶんの増分の中に収まる）
    for cap, _rate, _add in tk.KYUYO_TABLE:
        if cap is None:
            continue
        assert abs(tk.kyuyo_kojo(cap + 1) - tk.kyuyo_kojo(cap)) <= 1.0


def test_敷居は給与所得控除のちょうど半分():
    for income in (1_000_000, 1_700_000, 3_000_000, 7_000_000, 20_000_000):
        assert tk.shikii(income) == pytest.approx(tk.kyuyo_kojo(income) / 2)


def test_敷居は年収850万円で頭打ちになる():
    assert tk.shikii(8_500_000) == 975_000
    for income in (8_500_001, 10_000_000, 15_000_000, 50_000_000):
        assert tk.shikii(income) == 975_000


def test_敷居の下限は275000円():
    assert tk.shikii(1) == 275_000
    assert tk.shikii(1_625_000) == 275_000
    assert min(tk.shikii(i) for i in range(100_000, 20_000_001, 100_000)) == 275_000


def test_敷居の増え方は両端が0で真ん中が最急():
    rows = tk.slope_grid()
    slopes = [r["年収100万円あたりの敷居の増え方"] for r in rows]
    assert slopes[0] == 0            # 給与所得控除が定額の帯
    assert slopes[-1] == 0           # 頭打ちの帯
    assert max(slopes) == 200_000
    assert slopes == [0, 200_000, 150_000, 100_000, 50_000, 0]


def test_敷居以下の支出はどの年収でも1円も引けない():
    for income in range(500_000, 20_000_001, 500_000):
        assert tk.deductible(income, 275_000) == 0
        assert tk.deductible(income, 250_000) == 0
    # 敷居の上限ちょうどは境目。**年収850万円以上でだけ 0円**（向きが逆）
    for income in range(8_500_000, 30_000_001, 500_000):
        assert tk.deductible(income, 975_000) == 0
    assert tk.deductible(5_000_000, 975_000) == 255_000


def test_敷居の上限を超える支出はどの年収でも引ける():
    assert tk.vanish_income(975_001) is None
    for income in range(500_000, 30_000_001, 500_000):
        assert tk.deductible(income, 1_200_000) > 0


def test_引けなくなる年収は敷居が支出に追いつく点():
    for spend in (300_000, 500_000, 650_000, 800_000, 975_000):
        v = tk.vanish_income(spend)
        assert v is not None
        assert tk.shikii(v) == pytest.approx(spend, abs=1)
        assert tk.deductible(v, spend) == pytest.approx(0, abs=1)
        assert tk.deductible(v - 10_000, spend) > 0


def test_勤務必要経費の上限は年収430万円で消える():
    assert tk.KINMU_HITSUYO_CAP == 650_000
    assert tk.vanish_income(tk.KINMU_HITSUYO_CAP) == pytest.approx(4_300_000)
    assert tk.deductible(4_300_000, tk.KINMU_HITSUYO_CAP) == pytest.approx(0, abs=1)
    assert tk.deductible(3_600_000, tk.KINMU_HITSUYO_CAP) == 70_000


def test_節税額の山は引ける額を使い切る点にある():
    for spend in (500_000, 1_200_000):
        peak = tk.full_use_income(spend)
        top = tk.saving(peak, spend)
        # 走査でこれを超える点が無いこと（1円の丸め幅で見る）
        for x in range(400_000, 20_000_001, 25_000):
            assert tk.saving(x, spend) <= top + 1
        assert tk.wasted(peak - 200_000, spend) > 0
        assert tk.wasted(peak + 200_000, spend) == 0


def test_低い年収では引ける額が捨てられている():
    rows = {r["年収"]: r for r in tk.waste_grid(1_200_000)}
    assert rows[1_500_000]["捨てた額"] == 680_000
    assert rows[1_500_000]["引ける額"] == 925_000
    # 引ける額は最大なのに、節税額は最大ではない
    best = max(rows.values(), key=lambda r: r["節税額"])
    assert rows[1_500_000]["引ける額"] == max(r["引ける額"] for r in rows.values())
    assert best["年収"] != 1_500_000


def test_節税額は年収に対して単調ではない():
    rows = tk.spend_grid(1_200_000)
    savings = [r["節税額"] for r in rows]
    assert savings != sorted(savings)
    assert savings != sorted(savings, reverse=True)
    # 右端は税率の帯で上がり返す
    assert rows[-1]["節税額"] > rows[-2]["節税額"]


def test_敷居の対年収比が増える帯は1つだけ():
    ratios = [(i, tk.shikii(i) / i) for i in range(200_000, 20_000_001, 100_000)]
    rising = [a for (a, ra), (_b, rb) in zip(ratios, ratios[1:]) if rb > ra]
    assert rising, "増える点が1つも無い"
    assert min(rising) >= 1_600_000
    assert max(rising) < 1_800_000


def test_表の行は年収で一意():
    _checks.unique_by(tk.shikii_grid(), lambda r: r["年収"], "年収べつの敷居")


def test_ASSUMPTIONS_に仮定の値が書いてある():
    _checks.assumption_values(tk.ASSUMPTIONS, name="tokutei")
    joined = "".join(tk.ASSUMPTIONS)
    assert "15パーセント" in joined      # 社会保険料の仮定
    assert "10パーセント" in joined      # 住民税


@pytest.mark.parametrize("income,shikii", [
    (1_500_000, 275_000),
    (1_800_000, 310_000),
    (2_500_000, 415_000),
    (3_600_000, 580_000),
    (5_000_000, 720_000),
    (6_600_000, 880_000),
    (8_500_000, 975_000),
    (15_000_000, 975_000),
])
def test_docstring_の敷居の表(income, shikii):
    doc = tk.__doc__ or ""
    assert tk.shikii(income) == shikii
    assert f"{shikii:,}円" in doc


def test_docstring_の節税額の山():
    doc = tk.__doc__ or ""
    peak = tk.saving_peak(1_200_000)
    assert peak["節税額が最大の年収"] == 2_457_143
    assert peak["そのときの節税額"] == 118_714
    assert "2,457,143円" in doc
    assert "118,714円" in doc
    assert re.search(r"680,000円", doc)
