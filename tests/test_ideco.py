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


# --- 帯（`straddle_bands`）— 2026-08-17 に足した -------------------------------
#
# 掃引が ideco に出した候補3件は、**3件とも既存の節（`cliff_incomes` の表）が
# もう言っていること**でした。掃引の件数を (B) の順番の同点破りに使っているので、
# **「既に節がある候補」で件数が水増しされます。**
# ここで足したのは、その表の**まだ誰も言っていない側**です ——
# 「またぐ年収がどれだけ狭いか」と「落ち幅が何で決まるか」。


def test_またぐ年収は3つの島に分かれる():
    """連続した1本の帯ではありません。**離れた島です。**"""
    bands = ideco.straddle_bands()
    assert len(bands) == 3
    for band in bands:
        assert band["帯の下端"] <= band["いちばん深い年収"] <= band["帯の上端"]


def test_落ち幅は所得税率の段差に還元できる():
    """**住民税10%は定率なので、差では消えます。**

    数え上げ（`last_step` の実額）と、式（段差 × 1.021）が独立に一致すること。
    """
    for band in ideco.straddle_bands():
        implied = band["またいだ所得税率の段差"] * 100
        assert min(abs(implied - r) for r in (3.0, 5.0, 10.0)) < 0.02


def test_いちばん深い帯は端ではなく真ん中():
    """所得税でいちばん大きい段差は 10→20% の10ポイント。**上端ではありません。**"""
    bands = ideco.straddle_bands()
    depths = [b["落ち幅"] for b in bands]
    assert depths.index(max(depths)) == 1
    assert bands[-1]["落ち幅"] < bands[0]["落ち幅"]     # 高い年収ほど軽い


def test_帯の端は途中までなので最大で見る():
    """端は掛金の一部しか境目を越えないので、落ち幅が浅く出ます。

    **端で帯を代表させると、10.21pt の帯を 4.17pt と言うことになります。**
    """
    rows = {r["年収"]: r for r in ideco.cliff_incomes()}
    edge = rows[6_500_000]["最初の1段"] - rows[6_500_000]["最後の1段"]
    deep = rows[6_700_000]["最初の1段"] - rows[6_700_000]["最後の1段"]
    assert edge < deep
    band = [b for b in ideco.straddle_bands() if b["帯の下端"] == 6_500_000][0]
    assert band["いちばん深い年収"] != 6_500_000


def test_いちばん深い帯が端へ移ったら検査が落ちる(monkeypatch):
    """この節の主題は「端ではない」ことなので、崩れたら台本を書かせない。"""
    real = ideco.straddle_bands

    def flattened(*a, **k):
        bands = [dict(b) for b in real(*a, **k)]
        bands[0]["落ち幅"] = 1.0                      # 端をいちばん深くする
        bands[0]["またいだ所得税率の段差"] = 0.05
        return bands

    monkeypatch.setattr(ideco, "straddle_bands", flattened)
    with pytest.raises(_checks.TableError):
        ideco.check_tables()
