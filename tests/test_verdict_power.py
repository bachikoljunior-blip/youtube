"""**検出できない反証条件を、機械で捕まえられているか。**

2026-08-24、「ショートの最後で登録を頼むな」という規則が
**3回に1回は素で起きる目**を証拠にして入っていた。同じ形が戻らないよう門を置く。
"""
import math

from src import verdict_power as vp


def test_借りてきた率で引いた標本は検出できないと出る():
    """実測 0.0318% で 3,000再生 は、0人でも何も否定できない。"""
    base = 0.000318
    p = vp.power(base, 3000, threshold=0.001)
    assert p["detects_nothing"] is True
    assert 0.35 < p["p_zero_if_no_effect"] < 0.42
    # 0.1% は実測の3倍以上。**生き残るほうが不可能な門だった**
    assert p["threshold_multiple"] > 3.0


def test_実測の率で引き直した標本は検出できる():
    base = 0.000318
    p = vp.power(base, 30000, threshold=14 / 30000)
    assert p["detects_nothing"] is False
    assert p["expected"] > 9          # 効きなしでも9人以上が期待値
    assert 1.4 < p["threshold_multiple"] < 1.6


def test_必要な再生数は倍率が小さいほど増える():
    base = 0.000318
    assert vp.n_for(base, 1.5) > vp.n_for(base, 2.0) > vp.n_for(base, 3.0)
    assert vp.n_for(base, 2.0) > 9000


def test_人数で置いた門を率より優先して読む():
    """率で読むと、地の文の実測値を拾う。**実際に一度誤読した。**"""
    rows = vp.scan_hypotheses()
    hit = [r for r in rows if "登録を直接1回頼む" in r["claim"]]
    assert hit, "開け直した前提が読めていません"
    assert hit[0]["n"] == 30000
    assert hit[0]["gate"] == "14人未満"
    assert math.isclose(hit[0]["threshold"], 14 / 30000)


def test_実測の率は借りてきた一般値ではない():
    base, views, subs = vp.baseline_rate()
    assert views > 1000 and subs >= 0
    assert base < 0.003, "0.3% は業界の一般値。**ここに入っていたら壊れています**"
