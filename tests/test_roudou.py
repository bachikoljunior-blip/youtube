"""労働時間まわりの3本（`yukyu` / `jikangai` / `kyugyo`）を、**壊して**確かめる。

**通ることを見ても、検査が働いているかは分かりません。** 2026-08-15 に4回続いた
「人が見れば一目で分かる欠陥を、機械検査が素通りさせた」は、
**検査が0件のまま緑だった**ことが原因でした（`tests/test_chart_base.py` の収集エラー）。

だからここでは、**制度の値を1つずつ書き換えて `check_tables()` が落ちるか**を見ます。
落ちない値は、**置いてあるだけで何も守っていません。**
"""
from __future__ import annotations

import pytest

from src.calc import _checks, jikangai, kyugyo, yukyu


# ----------------------------------------------------------------- yukyu

def test_yukyu_の表がそのままなら通る():
    yukyu.check_tables()


def test_勤続6か月の付与日数を書き換えると落ちる(monkeypatch):
    """**39条1項の10日**。ここが動くと、以降の表の意味が全部ずれます。"""
    monkeypatch.setattr(yukyu, "FULL_TIME", (9,) + yukyu.FULL_TIME[1:])
    with pytest.raises(_checks.TableError):
        yukyu.check_tables()


def test_比例付与の列を1つ入れ替えると落ちる(monkeypatch):
    """週3日と週4日を取り違えた形。**週の日数が増えたのに日数が増えない**で捕まります。"""
    swapped = dict(yukyu.PRORATED)
    swapped[4], swapped[3] = yukyu.PRORATED[3], yukyu.PRORATED[4]
    monkeypatch.setattr(yukyu, "PRORATED", swapped)
    with pytest.raises(_checks.TableError):
        yukyu.check_tables()


def test_時季指定義務の境目は週の日数で動く():
    """**この動画の主題そのもの。** 週2日以下は一生かかりません。"""
    assert yukyu.obligation_starts(5) == 0.5
    assert yukyu.obligation_starts(4) == 3.5
    assert yukyu.obligation_starts(3) == 5.5
    assert yukyu.obligation_starts(2) is None
    assert yukyu.obligation_starts(1) is None


def test_使い切れば1日も消えない():
    assert all(r["時効で消えた日数"] == 0 for r in yukyu.expiry_run(15, 20))


def test_年5日しか使わないと定常で15日ずつ消える():
    run = yukyu.expiry_run(20, 5)
    assert run[-1]["時効で消えた日数"] == 15
    assert run[-1]["消えた日数の累計"] == 241


# -------------------------------------------------------------- jikangai

def test_jikangai_の表がそのままなら通る():
    jikangai.check_tables()


def test_99時間を2か月続けた並びは通らない():
    """**2か月平均80時間 ＝ 合計160時間。** 単月の上限だけ見ていると素通りします。"""
    sched = [99, 99] + [0] * 10
    assert jikangai.violations(sched)


def test_単月100時間ちょうどは通らない():
    """条文は「100時間**未満**」。等号を入れ違えると1時間ぶん緩みます。"""
    assert jikangai.violations([100] + [0] * 11)


def test_月60時間を12か月は年720時間でも通らない():
    """年の合計は上限ぴったりでも、**45時間超が12回**で落ちます。"""
    sched = [60] * 12
    assert sum(sched) == jikangai.LIMIT_YEAR_SPECIAL
    assert jikangai.violations(sched)


@pytest.mark.parametrize("builder", [jikangai.extreme_schedule,
                                     jikangai.flat_schedule])
def test_構成した並びは全部の条件を通り年720時間ぴったり(builder):
    sched = builder()
    assert jikangai.violations(sched) == []
    assert sum(sched) == jikangai.LIMIT_YEAR_SPECIAL


def test_複数月平均の上限を書き換えると落ちる(monkeypatch):
    monkeypatch.setattr(jikangai, "MULTI_MONTH_AVG", 85)
    with pytest.raises(_checks.TableError):
        jikangai.check_tables()


def test_3か月に置ける上限は240時間で月99時間の足し算と57時間ちがう():
    assert jikangai.concentrated_max(3) == 240
    assert jikangai.MONTH_MAX * 3 - jikangai.concentrated_max(3) == 57


def test_忙しい6か月だけでは年720時間に届かない():
    f = jikangai.quiet_months_floor()
    assert f["45時間超の月で運べる最大"] == 594
    assert f["ふつうの月が負う最低"] == 126


# ---------------------------------------------------------------- kyugyo

def test_kyugyo_の表がそのままなら通る():
    kyugyo.check_tables()


def test_休業手当の率を書き換えると落ちる(monkeypatch):
    monkeypatch.setattr(kyugyo, "KYUGYO_RATE", 0.5)
    with pytest.raises(_checks.TableError):
        kyugyo.check_tables()


def test_暦日数は月の日数から足したものと一致する():
    """**思い出しで書いた 89〜92 を、実際の月の長さで裏づけます。**"""
    spans = [s for _, s in kyugyo.calendar_day_spans()]
    assert min(spans) == kyugyo.CALENDAR_DAYS_MIN
    assert max(spans) == kyugyo.CALENDAR_DAYS_MAX


def test_同じ月給でも暦日が増えれば休業手当は減る():
    """**この動画の主題そのもの。** 分母が暦日なので、季節で変わります。"""
    a = kyugyo.daily_allowance(900_000, 89)
    b = kyugyo.daily_allowance(900_000, 92)
    assert a - b == 198
    assert (a - b) * 20 == 3_960


def test_週4日以下は最低保障が採られる():
    sides = {r["週の勤務日数"]: r["採った側"] for r in kyugyo.shift_grid()}
    assert sides[5] == "暦日割"
    assert all(sides[wd] == "最低保障" for wd in (4, 3, 2))


def test_月給に対する率は6割に届かない():
    """暦日で割ってから労働日だけ払うので、**26条の6割は月給の6割ではありません。**"""
    for row in kyugyo.ratio_to_monthly():
        assert row["月給に対する率"] < kyugyo.KYUGYO_RATE
