"""`src/calc/kyugyo.py` の**この回で足した3節の主張**を固定する（2026-08-17）。

節そのものは (B)（既にある表に節を足す）で出しました。使ったのは
**書いてあるのに一度も印字していなかった引数**です ——
`boundary_worked_days(calendar_days)`・`average_wage(..., worked_days)`・
`ratio_to_monthly(monthly)` の3つ。

主張は次の3つで、**どれも「休業手当は平均賃金の6割」の外側**にあります。

1. **最低保障が勝つ境目は、週あたりに直すと 4.2日 で動かない** ——
   労働日数のほうは暦日89〜92日に応じて 53.4〜55.2日 と動くのに、
   週あたりでは暦日が約分で消え、`0.6 × 7` だけが残る
2. **賃金も労働日数も同じで、時給制か月給制かだけが違うと額が変わる** ——
   最低保障は日給・時間給・出来高払にしか掛からない（12条1項但書）。
   しかも時給制の側は日給に率を掛けるだけなので、**勤務日数を減らしても動かない**
3. **月給に対する率は、月給の額では動かない** —— 賃金が約分で消える。
   動かしているのは暦日と労働日数の2つだけで、37.17%〜46.51%

**`check_tables()` が緑であることは、ここでは証拠になりません**
（自分を呼んで自分を確かめているだけ）。式を壊したときに**本当に落ちるか**は
外から壊して確かめます（`tests/test_calc_checks.py` と同じ考え方）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calc import _checks, kyugyo  # noqa: E402


def test_制度の値の検査は通る():
    kyugyo.check_tables()


# ---- 1. 境目は週4.2日 ---------------------------------------------------

def test_境目の労働日数は暦日で動く():
    rows = {r["3か月の暦日"]: r["境目の労働日数"] for r in kyugyo.weekly_boundary()}
    assert rows[89] == pytest.approx(53.4)
    assert rows[92] == pytest.approx(55.2)
    assert rows[89] < rows[92], "暦日が増えれば境目の労働日数も増えるはず"


def test_週あたりに直すと暦日が消えて4_2日で一定():
    weekly = {round(r["週あたりに直すと"], 9) for r in kyugyo.weekly_boundary()}
    assert weekly == {4.2}, weekly


def test_境目の週日数は率と曜日だけで決まる():
    """`0.6 × 7`。**時給も賃金総額も暦日も入っていない。**"""
    assert kyugyo.MINIMUM_RATE * kyugyo.DAYS_PER_WEEK == pytest.approx(4.2)


def test_週5日は暦日割_週4日以下は最低保障_境目4_2日の帰結():
    sides = {r["週の勤務日数"]: r["採った側"] for r in kyugyo.shift_grid()}
    assert sides[5] == "暦日割"
    for wd in (4, 3, 2):
        assert sides[wd] == "最低保障", wd


# ---- 2. 給与の形だけが違う2人 -------------------------------------------

def test_週5日では時給制と月給制で1円も違わない():
    row = {r["週の勤務日数"]: r for r in kyugyo.pay_form_gap()}[5]
    assert row["日額の差"] == 0
    assert row["時給制の日額"] == row["月給制の日額"] == 4_114


def test_週4日以下は時給制のほうが高い():
    by_week = {r["週の勤務日数"]: r for r in kyugyo.pay_form_gap()}
    for wd in (4, 3, 2):
        assert by_week[wd]["時給制の日額"] > by_week[wd]["月給制の日額"], wd
    assert by_week[2]["倍率"] == pytest.approx(2.10, abs=0.01)


def test_時給制の日額は勤務日数を減らしても動かない():
    """最低保障は `日給 × 0.6 × 0.6`。**勤務日数が式に入っていない。**"""
    by_week = {r["週の勤務日数"]: r for r in kyugyo.pay_form_gap()}
    assert {by_week[wd]["時給制の日額"] for wd in (4, 3, 2)} == {3_456}
    assert 3_456 == int(1_200 * 8 * kyugyo.MINIMUM_RATE * kyugyo.KYUGYO_RATE)


def test_月給制の日額は勤務日数を減らせば下がり続ける():
    by_week = {r["週の勤務日数"]: r["月給制の日額"] for r in kyugyo.pay_form_gap()}
    assert by_week[2] < by_week[3] < by_week[4] < by_week[5]


def test_月給制には最低保障が掛からない_12条1項但書():
    """`worked_days` を渡さなければ最低保障の欄は空のまま。"""
    a = kyugyo.average_wage(374_400, 91)
    assert a["最低保障"] is None
    assert a["採った側"] == "暦日割"


# ---- 3. 率を決めているのはカレンダー -----------------------------------

def test_月給を6_7倍にしても率は動かない():
    ratios = [r["月給に対する率"] for r in kyugyo.ratio_by_monthly()]
    for r in ratios:
        assert r == pytest.approx(ratios[0], abs=1e-4)
    assert ratios[0] == pytest.approx(0.3956, abs=1e-4)


def test_率の幅は暦日と労働日数だけで9_3ポイント():
    span = kyugyo.ratio_span()
    hi, lo = span["いちばん高い率"], span["いちばん低い率"]
    assert (hi["3か月の暦日"], hi["その月の労働日数"]) == (89, 23)
    assert (lo["3か月の暦日"], lo["その月の労働日数"]) == (92, 19)
    assert span["率の幅"] == pytest.approx(0.0934, abs=1e-4)
    assert hi["月給に対する率"] < kyugyo.KYUGYO_RATE, "6割には届かないはず"


# ---- 故障注入（**検査が本当に落ちるか**） -------------------------------

def test_境目を暦日で持たせると検査が落ちる(monkeypatch):
    """週あたりに直す割り算を落とすと `4.2` にならない。"""
    monkeypatch.setattr(kyugyo, "weekly_boundary", lambda: [
        {"3か月の暦日": 91, "境目の労働日数": 54.6, "週あたりに直すと": 54.6}])
    with pytest.raises(_checks.TableError):
        kyugyo.check_tables()


def test_最低保障を月給制にも掛けると検査が落ちる(monkeypatch):
    """週5日で差が出るようになるので、(g) の最初の門で止まる。"""
    original = kyugyo.average_wage
    monkeypatch.setattr(
        kyugyo, "average_wage",
        lambda total, days, worked=None: original(total, days, worked or 52))
    with pytest.raises(_checks.TableError):
        kyugyo.check_tables()


def test_時給制の日額が勤務日数で動くと検査が落ちる(monkeypatch):
    rows = kyugyo.pay_form_gap()
    for r in rows:
        if r["週の勤務日数"] in (3, 2):
            r["時給制の日額"] += r["週の勤務日数"]
    monkeypatch.setattr(kyugyo, "pay_form_gap", lambda **kw: rows)
    with pytest.raises(_checks.TableError):
        kyugyo.check_tables()


def test_率が月給で動くと検査が落ちる(monkeypatch):
    monkeypatch.setattr(kyugyo, "ratio_by_monthly", lambda **kw: [
        {"月給": 150_000, "休業手当の日額": 2_967,
         "その月の休業手当": 59_340, "月給に対する率": 0.3956},
        {"月給": 1_000_000, "休業手当の日額": 19_780,
         "その月の休業手当": 395_600, "月給に対する率": 0.4500}])
    with pytest.raises(_checks.TableError):
        kyugyo.check_tables()


def test_率がいちばん高い組み合わせを取り違えると検査が落ちる(monkeypatch):
    span = kyugyo.ratio_span()
    span["いちばん高い率"] = {"3か月の暦日": 92, "その月の労働日数": 23,
                       "休業手当の日額": 5_869, "その月の休業手当": 134_987,
                       "月給に対する率": 0.4499}
    monkeypatch.setattr(kyugyo, "ratio_span", lambda **kw: span)
    with pytest.raises(_checks.TableError):
        kyugyo.check_tables()
