"""**前の `--apply` が判定日を1日も動かしていないなら、もう一度は撃たない。**

2026-08-26 の実測（枠が戻った窓・`queue_lag --apply` を4回）:

    1回目  46手  stat_split 10/04 → 09/05 ／ opening_motion 10/16 → 09/12
    2回目  24手  （動いた）
    3回目  26手  （動いた）
    4回目  20手  **判定日 4つとも 3回目と同じ** ＝ 1,000単位 の空振り

それでも `--plan` は毎回「合計 12日 早まる」と出します
（`docs/JOURNAL.md`「印字と門のあいだで 38日 が止まっていた」と同じ形の3件目）。
**単位はこの機械のいちばん狭い所**で、同じ窓の `refresh_thumbnail --missing` 29本 と
`live_slots --all` 10本 が 403 で落ちています。
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from scripts import queue_lag


class _Plan:
    """`stuck_lines` が読むのは `before` だけです。"""

    def __init__(self, before: dict) -> None:
        self.before = before


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    path = tmp_path / "queue_lag.jsonl"
    monkeypatch.setattr(queue_lag, "PROGRESS", path)
    return path


def _row(before: dict, moves: int) -> str:
    return json.dumps({"at": "2026-08-26T07:20:00+00:00",
                       "before": {k: (v.isoformat() if v else None)
                                  for k, v in before.items()},
                       "promised": {}, "moves": moves}, ensure_ascii=False)


def test_no_ledger_means_go(ledger) -> None:
    lines, ok = queue_lag.stuck_lines(_Plan({"a": date(2026, 9, 6)}))
    assert ok is True
    assert lines == []


def test_same_state_as_last_apply_is_refused(ledger) -> None:
    before = {"a": date(2026, 9, 6), "b": None}
    ledger.write_text(_row(before, 20) + "\n", encoding="utf-8")
    lines, ok = queue_lag.stuck_lines(_Plan(dict(before)))
    assert ok is False
    assert any("判定日を1日も動かしていません" in x for x in lines)
    assert any("--force-stuck" in x for x in lines)


def test_a_moved_state_is_allowed(ledger) -> None:
    ledger.write_text(_row({"a": date(2026, 9, 6)}, 20) + "\n", encoding="utf-8")
    lines, ok = queue_lag.stuck_lines(_Plan({"a": date(2026, 9, 4)}))
    assert ok is True
    assert lines == []


def test_a_run_that_moved_nothing_does_not_arm_the_gate(ledger) -> None:
    """**0手 の回は門を張りません**（撃っていないので、動かなくて当たり前）。"""
    ledger.write_text(_row({"a": date(2026, 9, 6)}, 0) + "\n", encoding="utf-8")
    lines, ok = queue_lag.stuck_lines(_Plan({"a": date(2026, 9, 6)}))
    assert ok is True


def test_only_the_last_row_counts(ledger) -> None:
    """帳面は追記です。**見るのは最後の1行だけ。**"""
    ledger.write_text(
        _row({"a": date(2026, 9, 6)}, 20) + "\n"
        + _row({"a": date(2026, 9, 4)}, 20) + "\n", encoding="utf-8")
    _, ok = queue_lag.stuck_lines(_Plan({"a": date(2026, 9, 6)}))
    assert ok is True                       # 最後の行（09/04）とは違う
    _, ok = queue_lag.stuck_lines(_Plan({"a": date(2026, 9, 4)}))
    assert ok is False


def test_note_apply_round_trips(ledger) -> None:
    queue_lag._note_apply({"a": date(2026, 9, 6)}, {"a": date(2026, 9, 4)}, 20)
    last = queue_lag._last_apply()
    assert last["before"] == {"a": "2026-09-06"}
    assert last["promised"] == {"a": "2026-09-04"}
    assert last["moves"] == 20
