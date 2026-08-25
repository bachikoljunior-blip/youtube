"""医療費控除で戻る額の内訳（`src/calc/iryohi.py`）。

**現金で戻るのは所得税ぶんだけ**で、住民税ぶんは翌年6月からの負担減です。
住民税は一律10%なので、**所得税率が低いほど戻りに占める住民税の割合が高い。**
入れ替わる率は速算表の段のあいだに落ちていて、**その率の納税者はいません。**
"""
import pytest

from src.calc import iryohi


def test_入れ替わる率は速算表に無い():
    tip = iryohi.cash_share_tipping_rate()
    assert tip not in iryohi.INCOME_TAX_RATES
    assert 0.05 < tip < 0.10
    assert round(tip, 6) == round(0.10 / 1.021, 6)


def test_5パーセントの帯では住民税ぶんのほうが多い():
    r = iryohi.refund_split(200_000, 0.05)
    assert r["cash_now"] < r["next_year"]
    assert r["resident_over_cash"] > 1


@pytest.mark.parametrize("rate", [0.10, 0.20, 0.23, 0.33, 0.40, 0.45])
def test_10パーセント以上では所得税ぶんのほうが多い(rate):
    r = iryohi.refund_split(200_000, rate)
    assert r["cash_now"] > r["next_year"]


def test_住民税ぶんは税率によらず一定():
    """一律10%なので、動くのは所得税ぶんだけ。"""
    assert len({r["next_year"] for r in iryohi.refund_timing_grid()}) == 1


def test_現金の割合は税率とともに上がる():
    shares = [r["cash_share"] for r in iryohi.refund_timing_grid()]
    assert shares == sorted(shares)
    assert shares[0] < 0.5 < shares[1]


def test_合計はrefundと一致する():
    """内訳の割り方を変えても、既存の `refund()` とずれないこと。"""
    for rate in iryohi.INCOME_TAX_RATES:
        d = iryohi.deduction(300_000, 0, 3_000_000)
        assert iryohi.refund_split(d, rate)["total"] == \
            iryohi.refund(300_000, 0, 3_000_000, rate)["total"]


def test_故障注入_住民税率を下げると入れ替わりが帯の外へ出て検査が落ちる(monkeypatch):
    monkeypatch.setattr(iryohi, "RESIDENT_RATE", 0.02)
    with pytest.raises(ValueError, match="速算表の 5% と 10% のあいだにない"):
        iryohi.check_tables()


def test_故障注入_復興特別所得税を外すと入れ替わりが速算表の率に重なる(monkeypatch):
    """1.021 が 1.0 になると、入れ替わる率がちょうど10%＝速算表の段に乗る。"""
    monkeypatch.setattr(iryohi, "RECONSTRUCTION", 0.0)
    with pytest.raises(ValueError, match="速算表の率と一致している"):
        iryohi.check_tables()


def test_壊していないときは通る():
    iryohi.check_tables()
