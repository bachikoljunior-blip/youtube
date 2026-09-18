"""`studio/trend.slot_saturation` —— **周を注いでも本が増えなくなる所**（**API 0単位**）。

**2026-09-19 07:xx・optimizer（Opus 5・ultracode・1周 1体）。** derivation は `docs/JOURNAL.md` 同刻。

**なぜ在るか**: 同じ日の前の回が `lap_value` を足し、覆る条件 (1) に
**「在庫 ≦ 枠/日 なら枠が縛る」**と書きました。**その問いは「きょう」しか見ていません。**
在庫 13本 は 2.6日ぶんなので、きょうの答え（周が縛る）は正しい。
**期限 85日 で数えると入れ替わります**:

    吸える枠   85日 × 5本/日 ＝ **425本**（**日枠 10,000 が天井**・6本目 は入らない）
    書ける周   85日 × **13周/日**（commit の日ごとの中位）＝ **1,105周**
    要る周     (425 − 在庫13) × **0.7周/本** ＝ **293周**
    ------------------------------------------------------------------
    **293 / 1,101 ＝ 27%** ＝ **書く周の 73% は本を 1本 も増やせません**

＝ 28%目 の周が書いた本には座る枠が無く、限界の値打ちは **¥1,960 ではなく ¥0**。

**この検査が守っているのは 4つ**:
 (1) **中位で数える**（09/15 の 35周 は積み戻しの外れ値。平均だと 1日 が全部を決める）
 (2) **きょうは数に入れない**（終わっていない日を中位に混ぜると下へ引かれる）
 (3) **在庫は要る周から引く**（もう書いてある枠ぶん）
 (4) **1.0 を跨いだら向きが変わる**（＜1 ＝ 枠が縛る／≧1 ＝ 周が縛る）＝ **陽性対照つき**
"""
from __future__ import annotations

import datetime as dt

import pytest

from studio import trend
from studio.common import JST


def _rows(n_sched: int = 0) -> list[dict]:
    return [{"event": "scheduled", "id": f"s-{i}", "video_id": f"V{i}"} for i in range(n_sched)]


# ---- (1)(2) 周/日 は中位・きょうは入れない ---------------------------------

def test_周_日は実物のgitから中位で出る():
    v = trend.lap_per_day()
    if v is None:
        pytest.skip("git の台帳が引けない所")
    # **数はここへ写しません**（親の間隔が変われば動く ＝ 覆る条件 (9)）。見るのは形だけ。
    assert v > 0
    # 中位は平均より下（09/15 の 35周 が外れ値 ＝ この不等号が (1) の当のもの）。
    assert v < 24 * 60, "1周 1分 未満は、周の数え方が壊れています"


def test_きょうは中位に入れない(monkeypatch):
    """終わっていない日（commit がまだ 1〜2個）を混ぜると、中位が下へ引かれます。"""
    class _R:
        stdout = ("@@@ 2026-09-16\ndata/studio/scripts/a.json\n"
                  "@@@ 2026-09-16\ndata/studio/scripts/b.json\n"
                  "@@@ 2026-09-17\ndata/studio/scripts/c.json\n"
                  "@@@ 2026-09-17\ndata/studio/scripts/d.json\n"
                  "@@@ 2026-09-19\ndata/studio/scripts/e.json\n")

    monkeypatch.setattr(trend, "now_jst",
                        lambda: dt.datetime(2026, 9, 19, 7, 0, tzinfo=JST))
    monkeypatch.setattr("studio.common.run", lambda *a, **k: _R())
    # 09/16 が 2周・09/17 が 2周・09/19（きょう）は 1周 ＝ 入れなければ中位 2.0
    assert trend.lap_per_day(since="2026-09-15") == 2.0


# ---- (3) 在庫を引く --------------------------------------------------------

def test_在庫は要る周から引かれる(monkeypatch, tmp_path):
    monkeypatch.setattr(trend, "lap_per_day", lambda *a, **k: 10.0)
    monkeypatch.setattr(trend, "lap_cost",
                        lambda **k: {"short": {"laps_per": 1.0, "n": 1, "laps": 1, "revs_per": 1.0},
                                     "_lap": {}})
    now = dt.datetime(2026, 12, 3, 0, 0, tzinfo=JST)           # 残り ちょうど 10日
    for i in range(7):
        (tmp_path / f"x{i}.json").write_text("{}", encoding="utf-8")
    a = trend.slot_saturation([], tmp_path, now)               # 在庫 7本
    b = trend.slot_saturation(_rows(0), tmp_path, now)
    assert a["inventory"] == 7
    # 枠 10日 × 5 ＝ 50本。在庫 7本 を引いて 43本 × 1.0周/本 ＝ 43周。
    assert round(a["laps_needed"]) == 43
    assert a["laps_needed"] == b["laps_needed"]


def test_在庫が枠を越えたら要る周は0(monkeypatch, tmp_path):
    """**もう全部 書いてある**なら、書く周は 1周 も要りません（負にしないこと）。"""
    monkeypatch.setattr(trend, "lap_per_day", lambda *a, **k: 10.0)
    monkeypatch.setattr(trend, "lap_cost",
                        lambda **k: {"short": {"laps_per": 1.0, "n": 1, "laps": 1, "revs_per": 1.0},
                                     "_lap": {}})
    for i in range(80):
        (tmp_path / f"x{i}.json").write_text("{}", encoding="utf-8")
    s = trend.slot_saturation([], tmp_path, dt.datetime(2026, 12, 3, 0, 0, tzinfo=JST))
    assert s["laps_needed"] == 0.0
    assert s["write_share"] is None          # **0 ではなく「読めない」**（要る周が 0）


# ---- (4) 1.0 を跨ぐと向きが変わる（**陽性対照**） --------------------------

def test_周が余っていれば1未満_枠が縛る(monkeypatch, tmp_path):
    monkeypatch.setattr(trend, "lap_per_day", lambda *a, **k: 100.0)   # 周は潤沢
    monkeypatch.setattr(trend, "lap_cost",
                        lambda **k: {"short": {"laps_per": 0.7, "n": 1, "laps": 1, "revs_per": 1.0},
                                     "_lap": {}})
    s = trend.slot_saturation([], tmp_path, dt.datetime(2026, 12, 3, 12, 0, tzinfo=JST))
    assert s["write_share"] < 1.0


def test_陽性対照_周が細れば1を越える_周が縛る(monkeypatch, tmp_path):
    """**この検査が死んでいないこと** —— 入力を逆へ振れば、判定も逆へ出ること。"""
    monkeypatch.setattr(trend, "lap_per_day", lambda *a, **k: 1.0)     # 1日 1周 しか立たない
    monkeypatch.setattr(trend, "lap_cost",
                        lambda **k: {"short": {"laps_per": 5.0, "n": 1, "laps": 1, "revs_per": 1.0},
                                     "_lap": {}})
    s = trend.slot_saturation([], tmp_path, dt.datetime(2026, 12, 3, 12, 0, tzinfo=JST))
    assert s["write_share"] > 1.0


def test_いちばん安い形の周_本で数える(monkeypatch, tmp_path):
    """**いちばん安く枠を埋める道**で数えます（long 5.0 ではなく short 0.7）。"""
    monkeypatch.setattr(trend, "lap_per_day", lambda *a, **k: 10.0)
    monkeypatch.setattr(trend, "lap_cost",
                        lambda **k: {"short": {"laps_per": 0.7, "n": 1, "laps": 1, "revs_per": 1.0},
                                     "long": {"laps_per": 5.0, "n": 1, "laps": 1, "revs_per": 1.0},
                                     "_lap": {}})
    s = trend.slot_saturation([], tmp_path, dt.datetime(2026, 12, 3, 12, 0, tzinfo=JST))
    assert s["laps_per"] == 0.7


# ---- 実物（毎周 印字される側に在ること） ------------------------------------

def test_期限は目標の本文から来ている():
    # オーナー 2026-09-13 20:0x「達成期限3ヶ月」＝ 09/13 から 3か月。
    assert trend.LAP_DEADLINE == "2026-12-13"


def test_行に期限の側が出る():
    from studio.common import ledger_rows
    line = trend.lap_value_line(ledger_rows())
    if "周が数えられません" in line or "まだ 1本 も読めていません" in line:
        pytest.skip("git／台帳が引けない所")
    assert "期限まで数えると" in line
    assert "書く周の" in line and "% で枠が満ちます" in line


def test_門は1か所(monkeypatch, tmp_path):
    """**判定は `slot_saturation` だけ**（行は印字するだけ・数を持たない）。"""
    monkeypatch.setattr(trend, "slot_saturation", lambda *a, **k: {})
    from studio.common import ledger_rows
    line = trend.lap_value_line(ledger_rows())
    assert "期限まで数えると" not in line
