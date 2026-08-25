"""`src/calc/iryohi` —— **保険金は「その給付の目的となった医療費」が限度。**

2026-08-22 に足した節。確定申告の入力欄は「支払った医療費」と「補填される金額」の
2つしかないので、**総額どうしで引くと、入院費からはみ出した給付金まで
他の医療費の控除を削ります。** ここが固定するのは、その差が
**画面に出る額として**正しく出ること。

**先に置いた「既知の当たり」**（`docs/trigger_main.md` §4）——
入院費30万・給付金45万・その他の医療費25万・総所得300万・所得税率10% のとき、
**正しい控除は15万円、総額どうしで引くと0円。** 手で解ける1件です:

    正しい : (300,000+250,000) - min(450,000, 300,000) - 100,000 = 150,000
    誤り   : (300,000+250,000) -     450,000            - 100,000 =       0
"""
from __future__ import annotations

import pytest

from src.calc import iryohi


def test_既知の当たり_はみ出した給付金は他の医療費を削らない():
    r = iryohi.benefit_loss(hospital_cost=300_000, benefit=450_000,
                            other_paid=250_000, total_income=3_000_000, rate=0.10)
    assert r["applied"] == 300_000 and r["over"] == 150_000
    assert r["deduction_right"] == 150_000
    assert r["deduction_wrong"] == 0
    assert r["lost_deduction"] == 150_000
    assert r["lost_yen"] > 0


def test_はみ出しが無ければ差は出ない():
    for benefit in (0, 100_000, 300_000):
        r = iryohi.benefit_loss(300_000, benefit, 250_000, 3_000_000, 0.10)
        assert r["over"] == 0
        assert r["lost_yen"] == 0, "はみ出していないのに差が出ています"


def test_捨てる額には天井がある():
    """**給付金が青天井でも、削られるのは「その他の医療費 － 足切り」まで。**"""
    cap = iryohi.benefit_ceiling(other_paid=250_000, total_income=3_000_000, rate=0.10)
    assert cap["lost_deduction"] == 150_000
    for benefit in (450_000, 1_000_000, 100_000_000):
        r = iryohi.benefit_loss(300_000, benefit, 250_000, 3_000_000, 0.10)
        assert r["lost_deduction"] <= cap["lost_deduction"]
        assert r["lost_yen"] <= cap["lost_yen"]


def test_天井の額は表と同じ丸めで出す():
    """**同じ画面に出る数字どうしが1円ずれないこと**（実測 30,315 と 30,314）。"""
    cap = iryohi.benefit_ceiling(250_000, 3_000_000, 0.10)
    worst = max(iryohi.benefit_grid(300_000, 250_000, 3_000_000, 0.10),
                key=lambda r: r["lost_yen"])
    assert worst["lost_yen"] == cap["lost_yen"]


def test_全部引いた側が0になる給付金():
    zero_at = iryohi.benefit_zero_paid(300_000, 250_000, 3_000_000)
    assert zero_at == 550_000 - 100_000
    assert iryohi.benefit_loss(300_000, zero_at, 250_000, 3_000_000,
                               0.10)["deduction_wrong"] == 0
    assert iryohi.benefit_loss(300_000, zero_at - 1, 250_000, 3_000_000,
                               0.10)["deduction_wrong"] == 1


def test_足切りが下がる総所得では捨てる額も変わる():
    """総所得200万円未満は足切りが5%。**天井はそのぶん上がります。**"""
    low = iryohi.benefit_ceiling(250_000, 1_000_000, 0.05)
    high = iryohi.benefit_ceiling(250_000, 3_000_000, 0.05)
    assert low["floor"] == 50_000 and high["floor"] == 100_000
    assert low["lost_deduction"] > high["lost_deduction"]


@pytest.mark.parametrize("hospital_cost,benefit", [(0, 100_000), (100_000, 0)])
def test_端でも落ちない(hospital_cost, benefit):
    r = iryohi.benefit_loss(hospital_cost, benefit, 250_000, 3_000_000, 0.10)
    assert r["lost_yen"] >= 0
