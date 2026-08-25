"""医療費控除の上限200万円で「1人にまとめる」が逆転する節（`src/calc/iryohi.py`）。

**この節が言っていることを、そのまま検査にしています。**
節の主張が壊れたら赤くなること、壊していないときは通ることの両方を見ます。
"""
import pytest

from src.calc import iryohi

TI = 3_000_000          # 総所得（足切りは10万円で頭打ち）
FLOOR = 100_000
CAP = 2_000_000
TIP = CAP + FLOOR * 2   # 2,200,000円 ＝ まとめと2人分けが並ぶ点


def test_境目は上限と足切りから導いた額に一致する():
    assert iryohi.claimant_tips(1, TI) == [TIP]
    assert TIP == 2_200_000


def test_境目でまとめと2人分けが並ぶ():
    assert iryohi.together_deduction(TIP, TI) == iryohi.split_deduction(TIP, 2, TI)


def test_境目の手前ではまとめが勝つ():
    p = TIP - 10_000
    assert iryohi.together_deduction(p, TI) > iryohi.split_deduction(p, 2, TI)


def test_境目の先では2人に分けたほうが勝つ():
    p = TIP + 10_000
    assert iryohi.together_deduction(p, TI) < iryohi.split_deduction(p, 2, TI)


def test_上限に当たらない範囲では分けると必ず損する():
    """`split_loss` の元の主張。**この帯では今も正しい。**"""
    for p in (300_000, 800_000, 1_500_000, 2_000_000):
        assert iryohi.split_deduction(p, 2, TI) < iryohi.together_deduction(p, TI)


def test_split_lossは上限を超えると負を返す():
    """docstring の「分けて得になることは無い」は嘘だった（2026-08-18）。"""
    r = iryohi.split_loss(3_000_000, 1_500_000, TI, 0.20)
    assert r["lost_deduction"] < 0
    assert r["lost_yen"] < 0


def test_境目の間隔は上限プラス足切りで一定():
    tips = iryohi.claimant_tips(4, TI)
    assert {b - a for a, b in zip(tips, tips[1:])} == {CAP + FLOOR}
    assert tips == [2_200_000, 4_300_000, 6_400_000, 8_500_000]


@pytest.mark.parametrize("paid", [
    500_000, 2_100_000, 2_200_000, 2_300_000, 4_300_000, 5_000_000, 9_000_000,
])
def test_最善の人数より多い控除を出す人数は無い(paid):
    n = iryohi.best_claimants(paid, TI)["claimants"]
    best = iryohi.split_deduction(paid, n, TI)
    for m in range(1, 10):
        assert iryohi.split_deduction(paid, m, TI) <= best


def test_同点のときは少ないほうの人数を返す():
    """手続きが1つで済むほうを選ぶ。境目はちょうど同点。"""
    assert iryohi.best_claimants(TIP, TI)["claimants"] == 1
    assert iryohi.best_claimants(TIP, TI)["gain"] == 0


def test_表は境目の両側を必ず含む():
    """**1点だけ印字すると、折れているのか頭打ちなのかが読めません。**"""
    rows = iryohi.claimant_grid_by_paid(TI, 0.20)
    paids = [r["paid"] for r in rows]
    for tip in iryohi.claimant_tips(2, TI):
        assert tip - 10_000 in paids
        assert tip in paids
        assert tip + 10_000 in paids
    assert sum(1 for r in rows if r["at_tip"]) == 2


def test_人数が0以下なら落ちる():
    with pytest.raises(ValueError, match="申告する人数が範囲外"):
        iryohi.split_deduction(1_000_000, 0, TI)
    with pytest.raises(ValueError, match="件数が範囲外"):
        iryohi.claimant_tips(0, TI)


def test_故障注入_上限を外すと検査が落ちる(monkeypatch):
    """上限が無ければ「分けると損」は例外なく正しくなり、この節は消える。"""
    monkeypatch.setattr(iryohi, "DEDUCTION_CAP", 10**12)
    with pytest.raises(ValueError, match="上限を超える医療費でも、分けると損のまま"):
        iryohi.check_tables()


def test_故障注入_足切りの上限を動かすと境目がずれて検査が落ちる(monkeypatch):
    """境目は「上限 ＋ 足切り×2」。足切りが動けば境目も動く。"""
    monkeypatch.setattr(iryohi, "FLOOR_CAP", 150_000)
    with pytest.raises(ValueError):
        iryohi.check_tables()


def test_壊していないときは通る():
    iryohi.check_tables()          # 鳴らしてはいけない側
