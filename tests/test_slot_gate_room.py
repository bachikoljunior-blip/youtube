"""**上限（`house_rule.PUBLISH_PER_DAY`）まで、きょうの枠にまだ何本 置けるかを、門が印字すること。**

## なぜ要るか（2026-09-05 15:5x・最適化の回）

`PUBLISH_PER_DAY` が 09/05 に 1 → 10 へ動いたあとも、`scripts/slot_gate.py` と
`docs/trigger_main.md` §4 の1番目は「きょうの予約が 0本 → upload」のままだった。
1本 入った瞬間に満たされるので、その日の残りの回は全部 `improve`/`fix` へ落ちた
（実測 09/04 12:00〜09/05 14:00: ship 315件・upload 7件・別題材は 3件）。

この検査は「**上限が 1 なら黙る／足りなければ本数を言う／満ちたら黙る**」の3つを、
控えを注入して確かめる（**発火したことのない検査は検査ではない**）。

## 覆る条件

- `room_lines()` を `--gate` の exit 2 へ格上げしたら（覆る条件3）、`main()` 側の検査を足すこと。
- `per_day()` の数え方（JST・`today` の 0時 を床）が変わったら、下の `_row` も追うこと。
"""
from __future__ import annotations

import importlib.util
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))

_spec = importlib.util.spec_from_file_location("slot_gate_room_mod", ROOT / "scripts" / "slot_gate.py")
slot_gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(slot_gate)

TODAY = date(2026, 9, 5)


def _row(d: date, hour: int, vid: str) -> dict:
    t = datetime(d.year, d.month, d.day, hour, 0, tzinfo=JST)
    return {"video_id": vid, "at": t.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")}


def test_silent_when_cap_is_one():
    rows = [_row(TODAY, 10, "a")]
    assert slot_gate.room_lines(rows, today=TODAY, cap=1) == []


def test_says_how_many_more_when_below_cap():
    rows = [_row(TODAY, 10, "a")]
    out = slot_gate.room_lines(rows, today=TODAY, cap=10)
    assert out, "1本／上限10本 なのに黙っている"
    assert "1本／上限 10本" in out[0] and "あと 9本" in out[0]
    assert "upload" in out[1] and "新しい題材" in out[1]


def test_silent_when_cap_is_met():
    rows = [_row(TODAY, 9 + i, f"v{i}") for i in range(10)]
    assert slot_gate.room_lines(rows, today=TODAY, cap=10) == []


def test_counts_already_published_today_as_filled():
    """きょう既に公開ずみの本（`today` の 0時 を床にする `per_day` の註）も枠を埋めている。"""
    rows = [_row(TODAY, 1, "early"), _row(TODAY, 23, "late")]
    out = slot_gate.room_lines(rows, today=TODAY, cap=3)
    assert out and "2本／上限 3本" in out[0] and "あと 1本" in out[0]


def test_real_cap_follows_house_rule():
    """`cap` を渡さない回は `house_rule.cap()` を読む（定数を2か所に持たない）。"""
    from src import house_rule
    rows = [_row(TODAY, 10, "a")]
    out = slot_gate.room_lines(rows, today=TODAY)
    if house_rule.cap() <= 1:
        assert out == []
    else:
        assert out and f"上限 {house_rule.cap()}本" in out[0]
