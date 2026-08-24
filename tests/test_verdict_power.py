"""**検出できない反証条件を、機械で捕まえられているか。**

2026-08-24、「ショートの最後で登録を頼むな」という規則が、
**主張どおりの効きがあっても7割は「外れ」と出る門**を証拠にして入っていた。
同じ形が戻らないよう門を置く。
"""
import math

from src import verdict_power as vp

BASE = 0.000318          # 実測（47,102再生 → 15人）


def test_8月08日の門は主張の効きがあっても外れと出る():
    """alpha は小さいのに beta が大きい。**片側だけ見ると通ってしまう。**"""
    q = vp.power(BASE, 3000, gate=3, target=3.1)
    assert q["alpha"] < 0.10          # 効きなしで生き残る率は小さい
    assert q["beta"] > 0.40           # **主張どおりでも4割は外れと出る**
    assert q["detects_nothing"] is True


def test_開け直した門は両側とも1割で見分けられる():
    q = vp.power(BASE, 30000, gate=14, target=2.0)
    assert q["alpha"] <= 0.20 and q["beta"] <= 0.20
    assert q["detects_nothing"] is False


def test_大きい倍率を狙う門を2倍の物差しで測らない():
    """10倍を狙う設計を「見分けられない」と誤って挙げない。"""
    assert vp.power(BASE, 1000, gate=2, target=10.0)["detects_nothing"] is False
    assert vp.power(BASE, 1000, gate=2, target=2.0)["detects_nothing"] is True
    assert vp.claimed_target("長尺の登録率はショートより1桁以上高い", "") == 10.0
    assert vp.claimed_target("3倍になる", "") == 3.0
    assert vp.claimed_target("上がる", "") == 2.0


def test_0人が否定できるのは実測の何倍までか():
    z = vp.zero_means(BASE, 2720)
    assert z["p_zero_if_no_effect"] > 0.35     # **3回に1回は素で起きる**
    assert z["rules_out_multiple"] > 3.0       # 3倍超しか否定できない
    assert vp.n_for(BASE, 1.5) > vp.n_for(BASE, 2.0) > vp.n_for(BASE, 3.0)


def test_人数で置いた門を率より優先して読む():
    """率で読むと、地の文の実測値を拾う。**実際に一度誤読した。**"""
    hit = [r for r in vp.scan_hypotheses() if "登録を直接1回頼む" in r["claim"]]
    assert hit, "開け直した前提が読めていません"
    assert hit[0]["n"] == 30000 and hit[0]["gate"] == 14
    assert hit[0]["gate_label"] == "14人未満"


def test_実測の率は借りてきた一般値ではない():
    base, views, subs = vp.baseline_rate()
    assert views > 1000 and subs >= 0
    assert base < 0.003, "0.3% は業界の一般値。**ここに入っていたら壊れています**"
    assert math.isclose(base, subs / views)
