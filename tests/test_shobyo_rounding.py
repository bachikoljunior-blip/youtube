"""傷病手当金の、丸め・落ち幅・住民税・保険料率の節（`src/calc/shobyo.py`）。

**節が言い切っていることを、そのまま検査にしています。**

    「日額の丸めで得か損かは、標準報酬月額を900で割った余りだけで決まる（9通り）」
    「その差は546日ぶんで2,790.67円ひらく」
    「額面比から手元比への落ち幅は、標準報酬月額がいくらでも保険料の割合そのもの」
    「手元比が行ごとに動くのは、保険料ではなく日額の丸めだけが理由」
    「健康保険料率が1ポイント違うと、比では常にちょうど1ポイント動く」

言い切りが壊れたら赤くなること、壊していないときは通ることの両方を見ます。
"""
from fractions import Fraction

from src.calc import shobyo


def test_余りが同じなら丸めの差も同じ():
    """**この節の主張そのもの。** 900で割った余りだけで決まる。"""
    by_remainder: dict[int, set[Fraction]] = {}
    for pay in range(100_000, 700_001, shobyo.PAY_STEP):
        by_remainder.setdefault(pay % shobyo.ROUND_MOD, set()).add(
            shobyo.rounding_gain(pay))
    assert set(by_remainder) == set(range(0, shobyo.ROUND_MOD, 100))
    for rem, gains in by_remainder.items():
        assert len(gains) == 1, f"余り{rem}で丸めの差が1つに定まらない: {gains}"


def test_900より小さい周期では決まらない():
    """**900が最小であること。** 300でも600でも足りない（片側の検査）。"""
    for mod in (100, 300, 600):
        seen: dict[int, set[Fraction]] = {}
        for pay in range(100_000, 700_001, shobyo.PAY_STEP):
            seen.setdefault(pay % mod, set()).add(shobyo.rounding_gain(pay))
        assert any(len(v) > 1 for v in seen.values()), f"{mod}で決まってしまう"


def test_余りの表は9行で例も余りどおり():
    rows = shobyo.rounding_grid()
    assert len(rows) == 9
    assert [r["remainder"] for r in rows] == list(range(0, 900, 100))
    for r in rows:
        assert r["example_pay"] % shobyo.ROUND_MOD == r["remainder"]
        assert r["example_pay"] % shobyo.PAY_STEP == 0
        assert r["per_limit"] == r["per_day"] * shobyo.MAX_DAYS


def test_丸めの幅は546日で2790円と3分の2():
    sp = shobyo.rounding_spread()
    assert sp["spread_limit"] == Fraction(23, 9) * 2 * shobyo.MAX_DAYS
    assert sp["spread_limit"] == Fraction(25116, 9)
    assert round(float(sp["spread_limit"]), 2) == 2_790.67
    assert sp["best"]["remainder"] == 200
    assert sp["worst"]["remainder"] == 700
    assert sp["best"]["per_day"] == -sp["worst"]["per_day"] == Fraction(23, 9)


def test_余り0では丸めの差が1円も出ない():
    zero = [r for r in shobyo.rounding_grid() if r["remainder"] == 0][0]
    assert zero["per_day"] == 0
    assert zero["per_limit"] == 0


def test_落ち幅は標準報酬月額によらず保険料の割合そのもの():
    """**この節の主張そのもの。** 行がいくつあっても落ち幅は1つ。"""
    for care in (False, True):
        drops = {round(r["drop"], 10) for r in shobyo.drop_grid(care=care)}
        assert len(drops) == 1
        assert drops == {round(shobyo.premium_ratio(care=care), 10)}


def test_落ち幅は40歳未満1415ポイント40歳以上1495ポイント():
    assert round(shobyo.premium_ratio() * 100, 4) == 14.1500
    assert round(shobyo.premium_ratio(care=True) * 100, 4) == 14.9500
    assert round(shobyo.premium_ratio(care=True) - shobyo.premium_ratio(),
                 10) == shobyo.CARE_RATE


def test_手元比の幅は丸めのぶんだけ():
    """落ち幅が一定なので、手元比の幅は額面比の幅と1円もずれない。"""
    ns = shobyo.net_ratio_spread()
    rows = shobyo.drop_grid()
    face = (max(r["benefit_ratio"] for r in rows)
            - min(r["benefit_ratio"] for r in rows))
    assert round(ns["spread"], 12) == round(face, 12)
    assert round(ns["spread"] * 100, 4) == 0.0350


def test_半分を割る住民税は手元から半分を引いた額():
    for r in shobyo.resident_tax_edges():
        assert r["half_edge"] == r["net"] - r["standard_pay"] // 2
        assert r["zero_edge"] == r["net"]
        got = shobyo.net_month(r["standard_pay"], resident_tax=r["half_edge"])
        assert got["net"] == r["standard_pay"] // 2
        assert got["net_ratio"] == 0.5


def test_半分を割る住民税は1円足すと割る():
    for r in shobyo.resident_tax_edges():
        over = shobyo.net_month(r["standard_pay"], resident_tax=r["half_edge"] + 1)
        assert over["net_ratio"] < 0.5


def test_率は呼ぶ側から動かせる():
    """**直した所。** `net_month` が率を `premiums` へ通していなかった。"""
    base = shobyo.net_month(300_000)
    up = shobyo.net_month(300_000, health_rate=shobyo.HEALTH_RATE + 0.01)
    assert up["net"] < base["net"]
    assert base["net"] - up["net"] == 3_000
    pen = shobyo.net_month(300_000, pension_rate=shobyo.PENSION_RATE + 0.01)
    assert base["net"] - pen["net"] == 3_000


def test_率1ポイントの差は比ではどこでも1ポイント():
    """**額は標準報酬に比例して開くのに、比では一定。**"""
    rows = shobyo.rate_step()
    for r in rows:
        assert round(r["diff_ratio"] * 100, 6) == 1.0
        assert r["diff_month"] == r["standard_pay"] // 100
        assert round(r["diff_limit"]) == round(r["diff_month"] * shobyo.MAX_DAYS / 30)
    amounts = [r["diff_limit"] for r in rows]
    assert amounts == sorted(amounts)
    assert round(max(amounts) / min(amounts), 4) == 3.25
