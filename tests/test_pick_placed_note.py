"""**決めの本がもう その日の枠に在るなら、`[きょうの1本]` は `--move` を勧めないこと。**（`daily_pick.placed_at`）

## なぜ要るか（2026-09-05 09:2x に実測で踏んだ）

`a23e696j0f8` は 10:00 JST に予約ずみなのに、画面は毎周
「→ この本を 09/05 の枠へ（いま置けます）: `reschedule.py --move a23e696j0f8 2026-09-05T10:00`」
を出していた。撃てば同じ時刻に 50単位。置く側（`ahead_sweep.placed_today`）と同じ床で見る。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import daily_pick, next_slot  # noqa: E402

DAY = date(2026, 9, 5)


def _rows(at):
    return {"a23e696j0f8": {"video_id": "a23e696j0f8", "at": at, "topic": "s-x"}}


def test_その日に予約ずみなら_時刻が返る(monkeypatch):
    monkeypatch.setattr(next_slot, "latest_rows", lambda path=None: _rows("2026-09-05T01:00:00Z"))
    assert daily_pick.placed_at("a23e696j0f8", DAY) == "10:00"


def test_別の日か予約なしなら_None(monkeypatch):
    monkeypatch.setattr(next_slot, "latest_rows", lambda path=None: _rows("2026-09-06T01:00:00Z"))
    assert daily_pick.placed_at("a23e696j0f8", DAY) is None
    monkeypatch.setattr(next_slot, "latest_rows", lambda path=None: _rows(None))
    assert daily_pick.placed_at("a23e696j0f8", DAY) is None
    assert daily_pick.placed_at("", DAY) is None


def test_画面は_在る本に_move_を勧めない():
    body = (ROOT / "src" / "daily_pick.py").read_text(encoding="utf-8")
    i = body.index("_placed = placed_at(vid, day)")
    tail = body[i:i + 600]
    assert "もう" in tail and "の枠に在ります" in tail
    assert "elif vid:" in tail and "ahead_move_note(day)" in tail
