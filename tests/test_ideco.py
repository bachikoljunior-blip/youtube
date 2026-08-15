"""`src/calc/ideco.py` の**主張そのもの**を固定する（2026-08-16）。

この calc が動画で言うのは、次の3つです。**どれも「税率＋10パーセント」の外側にあります。**

1. **実効節税率は「掛ける前の税率＋住民税10パーセント」にならない** ——
   所得控除は課税所得を上から削るので、掛金が区分の境目をまたぐと
   **後半は1つ下の税率でしか効きません**
2. **ずれる向きは必ず下** —— 掛ける前の税率で計算すると多めに出る。
   「30パーセント戻る」と読んだ人が、実際には28.3パーセントだった、という形でしか外れません
3. **所得税がほとんど無い年収でも、住民税ぶんは残る** ——
   所得税の側が先に薄くなるので、合計は0にならない

**`check_tables()` が緑であることは、ここでは証拠になりません。**
`check_tables()` は自分自身を呼んで自分を確かめており、**式を壊したときに本当に
落ちるか**は、外から壊してみないと分かりません（`tests/test_calc_checks.py` と
同じ考え方。故障注入で確かめる）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calc import _checks, ideco  # noqa: E402


def test_制度の値の検査は通る():
    ideco.check_tables()


def test_拠出限度額は月額から年額へ12倍しているだけ():
    assert ideco.SALARIED_CAP == 23_000 * 12 == 276_000
    assert ideco.SELF_CAP == 68_000 * 12 == 816_000


def test_掛金を引くと税は必ず減る_増えることはない():
    for income in (2_000_000, 4_600_000, 6_800_000, 10_000_000):
        before = ideco.taxes(income, 0)["合計"]
        after = ideco.taxes(income, ideco.SALARIED_CAP)["合計"]
        assert after < before, income


def test_実効節税率は掛ける前の税率で出した額を超えない():
    """**これが動画の主張の中心。** 向きが逆なら、動画は嘘になる。"""
    for income in range(2_000_000, 12_000_001, 100_000):
        r = ideco.saving(income, ideco.SALARIED_CAP)
        # 所得税と住民税をそれぞれ円未満で切り捨てるので、丸めは最大2円
        assert r["節税額"] <= r["掛ける前の税率で見た額"] + 2, income


def test_税率どおりにならない年収が実在する():
    """**主題そのもの。** ここが空なら、この calc から動画は作れない。"""
    cliffs = ideco.cliff_incomes()
    assert cliffs, "またぐ年収が1件も無い"
    # 実測（2026-08-16）: 年収460万円で 17.3%、680万円で 28.3%
    by_income = {row["年収"]: row["実効節税率"] for row in cliffs}
    assert round(by_income[4_600_000] * 100, 1) == 17.3
    assert round(by_income[6_800_000] * 100, 1) == 28.3


def test_またいだ年収では最後の1段のほうが安く効く():
    rows = ideco.last_step(4_600_000)
    assert rows[0]["この1段の効き"] > rows[-1]["この1段の効き"]
    # 20.2% から 15.1% へ落ちる（1つ下の区分）
    assert round(rows[0]["この1段の効き"] * 100, 1) == 20.2
    assert round(rows[-1]["この1段の効き"] * 100, 1) == 15.1


def test_所得税が薄い年収でも住民税ぶんは残る():
    r = ideco.saving(1_500_000, ideco.SALARIED_CAP)
    assert r["住民税の減り"] == int(ideco.SALARIED_CAP * 0.10)
    assert r["節税額"] > r["住民税の減り"]


def test_年収が上がっても節税額は減らない():
    """**許容は2円。** 所得税と住民税をそれぞれ円未満で切り捨てているので、
    同じ税率の帯の中でも1〜2円だけ上下します（年収280万円で実際に1円下がる）。
    2円を超えて下がったら、それは丸めではなく計算の向きが壊れています。
    """
    prev = -1
    for income in range(2_000_000, 12_000_001, 200_000):
        cut = ideco.saving(income, ideco.SALARIED_CAP)["節税額"]
        assert cut >= prev - 2, income
        prev = max(prev, cut)


# ---- 故障注入。**検査が本当に落ちるかを、外から壊して確かめる** ----------

def test_拠出限度額を壊すと検査が落ちる(monkeypatch):
    monkeypatch.setattr(ideco, "SALARIED_CAP", 240_000)
    with pytest.raises(_checks.TableError):
        ideco.check_tables()


def test_桁を取り違えると検査が落ちる(monkeypatch):
    """月2万3000円を「2万3000」ではなく「230」と書いた場合。"""
    monkeypatch.setattr(ideco, "CAPS", [("会社員", 230, "桁を落とした")])
    with pytest.raises(_checks.TableError):
        ideco.check_tables()


def test_同じ名前を2度書くと検査が落ちる(monkeypatch):
    monkeypatch.setattr(ideco, "CAPS", [
        ("会社員", 23_000, "一度目"), ("会社員", 20_000, "二度目")])
    with pytest.raises(_checks.TableError):
        ideco.check_tables()


def test_控除を引かずに掛金ぶんを足してしまうと検査が落ちる(monkeypatch):
    """符号を逆にする＝掛金を増やすほど税が増える。向きの検査が拾うはず。"""
    real = ideco._taxable

    def flipped(income, extra, *, resident, social_rate):
        return real(income, -extra, resident=resident, social_rate=social_rate)

    monkeypatch.setattr(ideco, "_taxable", flipped)
    with pytest.raises(_checks.TableError):
        ideco.check_tables()


def test_またぐ年収が消えると検査が落ちる(monkeypatch):
    """区分をまたがない設計に変わったら、主題が消えたと言って落ちること。"""
    monkeypatch.setattr(ideco, "cliff_incomes", lambda premium=None: [])
    with pytest.raises(_checks.TableError):
        ideco.check_tables()
