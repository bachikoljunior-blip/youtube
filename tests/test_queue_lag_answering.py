"""**枠は「本数」ではなく「中身」で数えること**（2026-08-27・最適化の回に測って足した）。

`queue_lag` は長らく **何本 予約に在るか／いちばん後ろは何日 先か**しか
出していませんでした。ところが `eta.py` は毎回こう印字しています:

    **軌跡の腕が動くのは、前提を1件閉じたときだけ**（作る・出す・直すは
    軌跡の入力に入りません）

つまり枠の値打ちは「置けるか」ではなく「**その本が、どれかの群の N本目までに
入るか**」で決まります。判定日は N本目の公開日だからです（`_ready()`）。

実測（足した回・予約 367本）: これから 10/13 までの再生が付く枠 **334本**のうち、
判定日を決めている本は **63本（19%）**。**81% は、出しても判定日を1日も動かしません。**
そして足りない群は `request_form`（腕 `sub_rate`）の **あと 63本 と 65本** だけ。

ここで固定するのは3つ:

1. **N本目より後ろの本を「効く」と数えないこと。**
   これを外すと `stat_split` / `opening_motion` が `_members_by_landed()` で
   **全部の本をどちらかの群に入れる**ので、**95% が「効く」**と出ます
   （この回が一度そう書いて外しました。数字は出るが、何も言っていない）
2. **`needs:` の下にしか `key:` が無い群を落とさないこと。**
   `request_form` は yaml の直下に `key:` を**わざと付けていません**
   （付けると `tests/test_judgeable.py` が2週間 赤で居座るため）。
   **いちばん足りない群が、その置き場所の都合で一覧から消えていました**
3. `floors()` は変わらないこと（`request_form` は `ACCRUING` で最初から外れている）
"""
from __future__ import annotations

import pathlib
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from src import judgeable  # noqa: E402
from scripts import queue_lag  # noqa: E402

JST = timezone(timedelta(hours=9))


def _row(day: int, hour: int, vid: str) -> dict:
    return {"at": datetime(2026, 9, day, hour, 0, tzinfo=JST), "video_id": vid}


def test_N本目より後ろの本は効くと数えない(monkeypatch):
    """群に 3本 在って床が 2本 なら、3本目は判定日を動かさない。"""
    rows = [_row(7, 9, "a"), _row(7, 10, "b"), _row(7, 11, "c")]
    monkeypatch.setattr(queue_lag, "published", lambda: rows)
    monkeypatch.setattr(queue_lag.day_cap, "live_ids", lambda _r: {"a", "b", "c"})
    monkeypatch.setattr(
        queue_lag, "open_floors",
        lambda: [("k", "群", 2, [(date(2026, 9, 7), "a"),
                                 (date(2026, 9, 7), "b"),
                                 (date(2026, 9, 7), "c")])])
    per_day, ans, short = queue_lag.answering(rows)
    assert ans == {"a", "b"}, ans
    assert per_day[date(2026, 9, 7)] == [3, 2], per_day
    assert short == []


def test_床に足りない群は本数つきで返る(monkeypatch):
    rows = [_row(7, 9, "a")]
    monkeypatch.setattr(queue_lag, "published", lambda: rows)
    monkeypatch.setattr(queue_lag.day_cap, "live_ids", lambda _r: {"a"})
    monkeypatch.setattr(
        queue_lag, "open_floors",
        lambda: [("k", "群", 5, [(date(2026, 9, 7), "a")])])
    _per_day, _ans, short = queue_lag.answering(rows)
    assert short == [("k", "群", 4)], short


def test_needs_の下にしかない群も期限の一覧に出る():
    """`request_form` は yaml の直下に `key:` を持ちません。**それでも出ること。**"""
    want = judgeable.deadlines()
    assert "request_form" in want, sorted(want)


def test_floors_は_ACCRUING_の群を拾わない():
    """上の二重読みで `Floor` の側が増えていないこと（テストが赤くならない条件）。"""
    assert "request_form" not in {f.key for f in judgeable.floors()}


def test_実物で枠の節が出る():
    rows = queue_lag.scheduled()
    lines = queue_lag.answering_lines(rows)
    if not rows:
        assert lines == []
        return
    assert any("開いている前提の群に入る本" in ln for ln in lines), lines
