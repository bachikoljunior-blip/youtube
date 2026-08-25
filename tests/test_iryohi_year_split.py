"""年をまたいで医療費を払ったときの節（`src/calc/iryohi.py`）。

**節が言い切っていることを、そのまま検査にしています。**

    「消える控除は医療費の額によらない。またぎ1回につき足切り1回ぶん」
    「ただし控除そのものが尽きたら、そこで頭打ち」
    「5年に分けると、医療費が足切り×5以下では1円も戻らない」

言い切りが壊れたら赤くなること、壊していないときは通ることの両方を見ます。
"""
from src.calc import iryohi

TI = 3_000_000          # 総所得（足切りは10万円で頭打ち）
FLOOR = 100_000
RATE = 0.10


def test_分けても総額は1円も減らない():
    for paid, years in ((600_000, 5), (500_001, 5), (7, 3), (0, 2)):
        assert sum(iryohi.year_split_shares(paid, years)) == paid


def test_1年に集中させれば消える控除は0():
    r = iryohi.year_split_loss(600_000, 1, TI, RATE)
    assert r["lost_deduction"] == 0
    assert r["deduction_apart"] == r["deduction_together"]


def test_消える控除はまたぎの回数かける足切り():
    for years in (2, 3, 4, 5):
        r = iryohi.year_split_loss(1_000_000, years, TI, RATE)
        assert r["lost_deduction"] == (years - 1) * FLOOR


def test_消える控除は医療費の額によらない():
    """**この節の主張そのもの。** 1年あたりが足切りを超えている限り同じ額。"""
    got = {iryohi.year_split_loss(paid, 2, TI, RATE)["lost_deduction"]
           for paid in (300_000, 600_000, 1_000_000, 1_800_000)}
    assert got == {FLOOR}


def test_1年あたりが足切り以下なら頭打ちになる():
    """**頭打ちの側。** 控除が尽きるので、またぎの値段より損は小さい。"""
    r = iryohi.year_split_loss(150_000, 2, TI, RATE)
    assert r["deduction_apart"] == 0
    assert r["capped"] is True
    assert r["lost_deduction"] == 50_000 < FLOOR


def test_またぎ1回の値段は足切りかける係数():
    assert iryohi.cross_year_cost(TI, RATE) == int(FLOOR * iryohi.coefficient(RATE))
    assert iryohi.cross_year_cost(TI, RATE) == 20_210


def test_またぎの値段は総所得200万円で頭打ち():
    """足切りが「10万円と5%の少ないほう」なので、値段もそこで止まる。"""
    below = iryohi.cross_year_cost(1_000_000, RATE)
    at = iryohi.cross_year_cost(2_000_000, RATE)
    above = iryohi.cross_year_cost(5_000_000, RATE)
    assert below < at == above


def test_5年に分けて0円になるのは足切りかける5まで():
    """境目の両側を見る（同値を含めるので、片側だけでは決まらない）。"""
    edge = FLOOR * iryohi.RECLAIM_YEARS
    assert iryohi.year_split_deduction(edge, 5, TI) == 0
    assert iryohi.year_split_deduction(edge + 1, 5, TI) > 0


def test_控除が1円でも還付は0円になりうる():
    """円未満は切り捨てなので、控除の0と還付の0はずれる。"""
    r = iryohi.year_split_loss(FLOOR * iryohi.RECLAIM_YEARS + 1, 5, TI, RATE)
    assert r["deduction_apart"] == 1
    assert r["refund_apart"] == 0


def test_控除が0になる年数は切り上げ():
    assert iryohi.zero_years(600_000, TI) == 6
    assert iryohi.zero_years(650_000, TI) == 7
    assert iryohi.year_split_deduction(650_000, 6, TI) > 0
    assert iryohi.year_split_deduction(650_000, 7, TI) == 0


def test_分けるほど控除は減る一方():
    got = [iryohi.year_split_deduction(1_000_000, n, TI) for n in range(1, 11)]
    assert got == sorted(got, reverse=True)
    assert got[-1] == 0            # 10年 ＝ 1年あたり10万円で足切りちょうど


def test_表の行がそのまま節と一致する():
    rows = iryohi.year_split_grid(600_000, TI, RATE)
    assert [r["years"] for r in rows] == [1, 2, 3, 4, 5]
    assert rows[-1]["deduction_apart"] == 100_000
    assert rows[-1]["lost_yen"] == 80_840
