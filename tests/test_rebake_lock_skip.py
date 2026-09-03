"""錠に弾かれた焼き直しは、印も その日の上限も 食わないこと。

実測 2026-09-03: 11:41 に印が立ち 1秒後に `skip`（`why: locked`）→
13:10 の掃きが 09/04 も 09/05 も焼かなかった（片方は「一度 焼いた」、
片方は「きょう既に 2回 焼いた」）。註は `ahead_sweep._drop_mark()`。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import ahead_sweep

JST = timezone(timedelta(hours=9))


def _rows() -> list[dict]:
    return [
        {"at": "2026-09-03T05:02:35+09:00", "kind": "start", "video_id": "A", "sha": "s1"},
        {"at": "2026-09-03T11:41:52+09:00", "kind": "start", "video_id": "B", "sha": "s2"},
        {"at": "2026-09-03T11:41:53+09:00", "kind": "skip", "video_id": "B", "sha": "s2",
         "why": "locked"},
    ]


def test_弾かれた回は上限の分子に入らない() -> None:
    assert ahead_sweep._baked_today(_rows(), "2026-09-03") == 1


def test_別の日は数えない() -> None:
    assert ahead_sweep._baked_today(_rows(), "2026-09-04") == 0


def test_弾かれた回が印を残さない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """印が残ると `rebake_attempted()` が 3時間 True を返し、その台本が焼けなくなる。"""
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    mark = tmp_path / "B-s2"
    now = datetime(2026, 9, 3, 11, 41, tzinfo=JST)
    mark.write_text(now.isoformat(timespec="seconds"), encoding="utf-8")

    assert ahead_sweep.rebake_attempted(
        "B", "s2", now=now + timedelta(minutes=30), root=tmp_path) is True
    ahead_sweep._drop_mark("B", "s2")
    assert not mark.exists()
    assert ahead_sweep.rebake_attempted(
        "B", "s2", now=now + timedelta(minutes=30), root=tmp_path) is False


def test_印が無くても倒れない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    ahead_sweep._drop_mark("nope", "nope")


def test_焼いている最中は_起こす側が見送る(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """掃きは 20分 ごとに来る。長い1本（実測 25分 超）のあいだ、起こすたびに
    `start` と `skip` が1組 積まれていた（09/03 13:2x〜13:3x に実物で2組）。"""
    import fcntl

    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    assert ahead_sweep.rebake_busy() is False

    fh = open(tmp_path / "rebake.lock", "a+", encoding="utf-8")
    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert ahead_sweep.rebake_busy() is True
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()

    assert ahead_sweep.rebake_busy() is False
