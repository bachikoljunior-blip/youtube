"""傷病手当金の「手取りで比べた置換率」を、既知の当たりで固定する。

**この節を書いた回は、逆の予想から入っている**（`src/calc/shobyo.py` の註）。
所得税と雇用保険料がかからないぶん、手取りで比べれば3分の2より**高くなる**
と考えて書きはじめ、回したら**下回っていた** —— 社会保険料は標準報酬月額から
計算されるので、手当金が3分の2に減っても引かれる額が1円も減らないため。

**向きが逆に壊れたら、ここが鳴る。** 節の主張そのものが数字なので、
数字を検査に固定しておかないと、次に触った回が静かに反転させられる。
"""
from __future__ import annotations

import pytest

from src.calc import shobyo


def test_手取りの置換率は額面の3分の2を下回る():
    """**これが節の主張。** 逆向きに壊れたら鳴る。"""
    for row in shobyo.replacement_grid():
        assert row["ratio"] < shobyo.BENEFIT_RATIO, row


def test_下回る理由は社会保険料が満額引かれること():
    """保険料だけを引いた比が、既に3分の2を下回っている。"""
    for row in shobyo.replacement_grid():
        assert row["base_ratio"] < shobyo.BENEFIT_RATIO, row
        # 非課税と雇用保険料ぶんは、必ず押し上げる向きに効く
        assert row["base_ratio"] < row["koyou_ratio"] < row["ratio"], row


def test_置換率は標準報酬月額が上がるほど高い():
    """押し戻しているのは累進の所得税なので、上の行ほど有利になる。"""
    rows = shobyo.replacement_grid()
    ratios = [r["ratio"] for r in rows]
    assert ratios == sorted(ratios), ratios
    # 下の行と上の行で、2ポイント以上ひらく（実測 3.13ポイント）
    assert ratios[-1] - ratios[0] > 0.02


def test_雇用保険料ぶんの押し上げは率なのでどの行でも同じ():
    """率をそのまま掛けているので、比で見れば標準報酬月額によらない。"""
    lifts = [r["koyou_part"] for r in shobyo.recovery_grid()]
    assert max(lifts) - min(lifts) < 0.0005, lifts


def test_取り返し率は1を超えない():
    """**58,000〜650,000円のどこにも「手取りでも3分の2」の人はいない。**"""
    scan = shobyo.recovery_scan()
    assert scan["reach"] is None
    assert scan["best"]["recovery"] < 1.0
    assert scan["scanned"] == 593


def test_介護保険料があるほうが置換率は低い():
    """40歳以上は分子だけがさらに削られる（分母の給料も同額 削られるが、分子のほうが小さい）。"""
    for pay in (200_000, 300_000, 500_000):
        assert (shobyo.replacement(pay, care=True)["ratio"]
                < shobyo.replacement(pay)["ratio"])


@pytest.mark.parametrize("pay,expected", [(200_000, 0.6281), (300_000, 0.6307),
                                          (650_000, 0.6594)])
def test_既知の当たり(pay: int, expected: float):
    """2026-08-27 の実測。**丸めの順番を変えると、ここがずれる。**"""
    assert round(shobyo.replacement(pay)["ratio"], 4) == expected
