"""**`drift.py` の1回の出力が、同じ前提について逆のことを言わないこと。**

2026-08-28 08:2x の実測（本物の台帳・本物の時計）:

    期限が来ていて、いま判定できる前提: **なし**
      ↑ `split_overdue()`。「判定できるのは 08-28 の **16:00 JST 以降**
        （計器がそれまで読めません）」「**この回は撃たないこと**」
    次に1件 閉じられるのは **2026-08-28**（期日は0日 過ぎています
      ＝ **この回に閉じられます**）
      ↑ `theta_response()`。**16:00 がここで落ちています**

同じ画面の 8行 違いです。上を読んだ回は待ち、下を読んだ回は撃ちに行って
403 を1つ買って帰ります。

**`ready_at` は 2026-08-28 04:0x に `_judge_state_by_claim()` まで持ち上がり、
`split_overdue()` は正しく使っていました。** 来ていなかったのは在庫の側
（`closable_within`）で、`_closable_est` を足したときの註が名指ししている
空振りと、**同じ形の2件目**です。

この検査が見るのは3つ:

    1. `_time_gated()` が「今日・時刻はまだ」を True にする
    2. その前提は「次に1件 閉じられるのは」に渡らない
    3. **代わりに、時刻つきの1行がその真下に出る**（黙って消さない）

**3 が要るのは、外すだけだと「今日は何も閉じられない」に見えるから**です。
実際には数時間 待てば閉じられます —— その回が待つべきなのか、
別の腕を引くべきなのかは、時刻が出ていないと決められません。
"""

from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts import drift  # noqa: E402

JST = timezone(timedelta(hours=9))


def _stock(closable_on: str, ready_at=None, est: bool = False) -> dict:
    return {"claim": f"c-{closable_on}-{ready_at}",
            "_closable_on": closable_on,
            "_closable_est": est,
            "_ready_at": ready_at}


def test_time_gated_true_when_today_and_clock_not_reached():
    """今日・時刻はまだ → **閉じられない**。"""
    now = datetime(2026, 8, 28, 8, 21, tzinfo=JST)
    at = datetime(2026, 8, 28, 16, 0, tzinfo=JST)
    assert drift._time_gated(_stock("2026-08-28", at), "2026-08-28", now) is True


def test_time_gated_false_after_the_clock():
    """同じ日でも、時刻を過ぎていれば閉じられる。"""
    now = datetime(2026, 8, 28, 16, 1, tzinfo=JST)
    at = datetime(2026, 8, 28, 16, 0, tzinfo=JST)
    assert drift._time_gated(_stock("2026-08-28", at), "2026-08-28", now) is False


def test_time_gated_false_for_other_days():
    """**明日以降の時刻待ちは外さないこと。**

    外すと「次に1件 閉じられるのは」から在庫が丸ごと消え、
    「閉じられる日が出せません」に倒れます —— 今日の話ではないので、
    その回にできることが変わりません。
    """
    now = datetime(2026, 8, 28, 8, 21, tzinfo=JST)
    at = datetime(2026, 8, 29, 16, 0, tzinfo=JST)
    assert drift._time_gated(_stock("2026-08-29", at), "2026-08-28", now) is False


def test_time_gated_false_without_ready_at():
    """`ready_at` の無い前提は、これまでどおり日付だけで見る。"""
    now = datetime(2026, 8, 28, 8, 21, tzinfo=JST)
    assert drift._time_gated(_stock("2026-08-28", None), "2026-08-28", now) is False


def test_gated_prior_is_not_offered_as_closable_this_round(monkeypatch):
    """**時刻待ちの前提を「この回に閉じられます」と言わないこと。**（本体）

    旧実装（`_closable_est` だけで濾していた版）はここで落ちます。
    """
    now = datetime(2026, 8, 28, 8, 21, tzinfo=JST)
    at = datetime(2026, 8, 28, 16, 0, tzinfo=JST)
    stock = [_stock("2026-08-28", at), _stock("2026-08-30", None)]

    monkeypatch.setattr(drift, "closable_within", lambda *a, **k: stock)
    monkeypatch.setattr(drift, "rounds_per_day", lambda *a, **k: 15.0)
    monkeypatch.setattr(drift, "closed_per_day", lambda *a, **k: 5)
    monkeypatch.setattr(drift, "role_gap_hours", lambda *a, **k: 1.59)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(drift, "datetime", _FixedDatetime)

    text, _dry = drift.supply_report("2026-08-28")

    assert "この回に閉じられます" not in text, text
    # 次に閉じられるのは、時刻待ちではないほう
    assert "次に1件 閉じられるのは **2026-08-30**" in text, text


def test_gated_prior_still_prints_its_clock(monkeypatch):
    """**黙って消さないこと。** 時刻つきの1行が残る。"""
    now = datetime(2026, 8, 28, 8, 21, tzinfo=JST)
    at = datetime(2026, 8, 28, 16, 0, tzinfo=JST)
    stock = [_stock("2026-08-28", at), _stock("2026-08-30", None)]

    monkeypatch.setattr(drift, "closable_within", lambda *a, **k: stock)
    monkeypatch.setattr(drift, "rounds_per_day", lambda *a, **k: 15.0)
    monkeypatch.setattr(drift, "closed_per_day", lambda *a, **k: 5)
    monkeypatch.setattr(drift, "role_gap_hours", lambda *a, **k: 1.59)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(drift, "datetime", _FixedDatetime)

    text, _dry = drift.supply_report("2026-08-28")

    assert "16:00 JST" in text, text
    assert "この回は撃たないこと" in text, text
    # **時刻の行は「次に1件」のすぐ下**（あいだに予定表の θ の6行を挟まないこと）
    lines = [ln for ln in text.splitlines() if ln.strip()]
    i = next(i for i, ln in enumerate(lines) if "次に1件 閉じられるのは" in ln)
    assert "16:00 JST" in lines[i + 1], lines[i:i + 3]


@pytest.mark.parametrize("est", [True, False])
def test_estimated_days_stay_excluded(est, monkeypatch):
    """**`_closable_est` の濾しを壊していないこと**（2026-08-27 の直しの回帰）。"""
    now = datetime(2026, 8, 28, 8, 21, tzinfo=JST)
    stock = [_stock("2026-08-28", None, est=est)]

    monkeypatch.setattr(drift, "closable_within", lambda *a, **k: stock)
    monkeypatch.setattr(drift, "rounds_per_day", lambda *a, **k: 15.0)
    monkeypatch.setattr(drift, "closed_per_day", lambda *a, **k: 5)
    monkeypatch.setattr(drift, "role_gap_hours", lambda *a, **k: 1.59)

    class _FixedDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return now if tz is None else now.astimezone(tz)

    monkeypatch.setattr(drift, "datetime", _FixedDatetime)

    text, _dry = drift.supply_report("2026-08-28")
    if est:
        assert "次に閉じられる日は出せません" in text, text
    else:
        assert "この回に閉じられます" in text, text
