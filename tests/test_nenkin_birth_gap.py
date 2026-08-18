"""生まれた日で繰上げの減額率が変わる節（`src/calc/nenkin.py`）。

**節が言い切っていることを、そのまま検査にしています。**

    「減る額の比は、繰り上げた月数によらない（0.5% ÷ 0.4%）」
    「追い抜かれる年齢は、旧率のほうが必ず早い」
    「ずれは4年ぶんだが、繰上げが深いほど大きくなるとは限らない」
"""
from src.calc import nenkin

BASE = 180.0


def test_旧率のほうが倍率は小さい():
    for m in range(1, 61):
        assert nenkin.rate_for(-m, born_before_s37=True) < nenkin.rate_for(-m)


def test_減る額の比は月数によらない():
    """**この節の主張そのもの。** 集合が1点になること。"""
    got = {round(nenkin.birth_gap_ratio(m), 9) for m in range(1, 61)}
    assert got == {1.25}
    assert nenkin.RATE_DOWN_PER_MONTH_OLD / nenkin.RATE_DOWN_PER_MONTH == 1.25


def test_60歳繰上げは年10万8千円ちがう():
    r = nenkin.birth_gap(60, BASE)
    assert r["倍率_新"] == 0.76 and r["倍率_旧"] == 0.70
    assert r["年の差"] == 10.8
    assert r["生涯の差"] == 270.0      # 85歳まで＝25年ぶん


def test_生涯の差は受け取る月数に比例する():
    a = nenkin.birth_gap(60, BASE, until_age=85)["生涯の差"]
    b = nenkin.birth_gap(60, BASE, until_age=90)["生涯の差"]
    assert round(b - a, 6) == round(10.8 * 5, 6)


def test_旧率のほうが必ず早く追い抜かれる():
    for r in nenkin.birth_gap_grid(BASE):
        assert r["ずれ_月"] > 0


def test_ずれは50か月でぴったり一定():
    """**繰り上げた月数によりません。**

    厳密にやると `新 = 1030 - m`・`旧 = 980 - m`（月齢）なので、差は必ず 50。
    **浮動小数でやると 49〜51 を行き来します**（同点にちょうど着くため）。
    """
    gaps = [r["ずれ_月"] for r in nenkin.birth_gap_grid(BASE)]
    assert gaps == [50] * len(gaps)
    for m in (1, 7, 12, 37, 60):
        new = nenkin.catch_up(m, BASE)
        old = nenkin.catch_up(m, BASE, born_before_s37=True)
        assert new[0] * 12 + new[1] == 1030 - m
        assert old[0] * 12 + old[1] == 980 - m


def test_年額の基準を変えても倍率と分岐点は動かない():
    """額面の分岐点は年額によらない（`ASSUMPTIONS` が言い切っている性質）。

    **8/18 まではここが年額で1か月動いていました**（同点を float で判定していた）。
    """
    a = nenkin.birth_gap(60, 180.0)
    b = nenkin.birth_gap(60, 300.0)
    assert a["分岐点_新"] == b["分岐点_新"]
    assert a["分岐点_旧"] == b["分岐点_旧"]
    assert a["倍率_旧"] == b["倍率_旧"]


def test_catch_up_の既定は新しい率のまま():
    """**既存の呼び出しを1つも変えていないこと。**"""
    assert nenkin.catch_up(60, BASE) == nenkin.catch_up(60, BASE, born_before_s37=False)
    assert nenkin.catch_up(60, BASE) != nenkin.catch_up(60, BASE, born_before_s37=True)
