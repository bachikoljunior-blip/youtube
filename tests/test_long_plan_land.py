"""`--long` の回の着地点が、**長尺の帯**から出ていること。

## なぜ要る（2026-08-29 に踏んだ）

`main()` は `_drop_queue_tail_calcs` に「この回の本が着く日」を渡し、門は
**その前後 7日** に出ている calc を避けます。ところが `--date` の無い回は
着地点を **`live_plan()`**（ショートの生きる帯 09:00〜13:30）から取っていました。
**長尺はその帯へは1本も置きません** —— 置き先は `_long_ring()` の 18〜22時 です。

実測（`--count 4 --long --hour 20`）:

    印字された着地点  2026-09-06   ← `live_plan()`
    実際に着く日      2026-09-19   ← 20時 が最初に空く日
    門が選んだ4本     teiji×2 ＋ shokyu×2（09/16 に teiji×2・shokyu×1 が既に在る）

**13日 ずれた窓で門を掛けていたので、避けるべき calc が1件も見えていません。**

**覆る条件**: `slots()` が長尺の置き先を変えたら（`ring` をやめる・帯を移す）、
`long_plan()` の写しも同じ回に直すこと。**写しである以上、片方だけ動くと黙って外れます。**
"""
from __future__ import annotations

import sys
from datetime import datetime, date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import batch_build as b  # noqa: E402


NOW = datetime(2026, 8, 29, 10, 0, tzinfo=b.JST)


def test_ひとつの時刻なら1日ずつ後ろへ積む():
    taken = {"2026-08-29": {20}, "2026-08-30": {20}, "2026-08-31": {20}}
    plan = b.long_plan(3, (20,), now=NOW, taken=taken)
    assert plan == [(20, date(2026, 9, 1)), (20, date(2026, 9, 2)),
                    (20, date(2026, 9, 3))]


def test_埋まっている日を飛ばす():
    taken = {d: {20} for d in ("2026-08-29", "2026-08-30",
                               "2026-08-31", "2026-09-01")}
    plan = b.long_plan(1, (20,), now=NOW, taken=taken)
    assert plan == [(20, date(2026, 9, 2))]


def test_輪は時刻を順に配ってから日を解く():
    plan = b.long_plan(4, (20, 21), now=NOW, taken={})
    assert plan == [(20, date(2026, 8, 29)), (21, date(2026, 8, 29)),
                    (20, date(2026, 8, 30)), (21, date(2026, 8, 30))]


def test_渡した控えを書き換えない():
    taken = {"2026-08-29": {20}}
    b.long_plan(2, (20,), now=NOW, taken=taken)
    assert taken == {"2026-08-29": {20}}


def test_ショートの帯とは別の日になる():
    """**この検査が落ちたら、長尺の着地点がまたショートの帯から出ています。**"""
    taken = {"2026-08-29": {20}, "2026-08-30": {20}, "2026-08-31": {20}}
    plan = b.long_plan(1, (20,), now=NOW, taken=taken)
    assert plan[0][0] == 20
    assert plan[0][1] not in (date(2026, 8, 29), date(2026, 8, 30),
                              date(2026, 8, 31))


def test_時刻を明示した回は輪を使わない():
    """`--hour 20` は「20時に1日1本」。**輪で黙って上書きしないこと。**

    2026-08-29 の実測: `--count 4 --long --hour 20` が 09/19 の
    19/20/21/22時 へ4本 入りました。`hour_given` の註は
    「**明示は常に通す**」と書いてあり、`slots(live=…)` はそれを守っています ——
    守っていなかったのは `ring` の側だけ（`--hours` 複数形しか見ていなかった）。

    **覆る条件**: 長尺を1日に詰めるほうが 面 に効くと実測で出たら、
    既定（何も書かない回）の輪はそのままなので、この検査は触らなくてよい。
    """
    import inspect
    src = inspect.getsource(b.main)
    assert "not hours and not hour_given" in src
