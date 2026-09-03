"""焼きかけのまま器ごと消えた回を、「いま焼いています」と読まないこと。

実測 2026-09-03: 15:00:54 に `1huadpEk6HY`（sha bd162bda6fd5）の印と `start`。
15:47 に器が入れ替わり `pipeline` は1本も居ない。それでも
`rebake_attempted()` は True（印が 3時間 より若い）で、`--write` の画面は
**「いま焼いています —— 手で撃たないこと」**と言い続けていた。
註は `ahead_sweep.rebake_died()`。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import ahead_sweep

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 3, 15, 57, tzinfo=JST)

_START = [{"at": "2026-09-03T15:00:54+09:00", "kind": "start", "video_id": "A", "sha": "s1"}]


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict],
           *, busy: bool) -> None:
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    monkeypatch.setattr(ahead_sweep, "_rebake_rows", lambda root=None: rows)
    monkeypatch.setattr(ahead_sweep, "rebake_busy", lambda: busy)
    (tmp_path / "A-s1").write_text("2026-09-03T15:00:54+09:00", encoding="utf-8")


def test_錠が空いていれば死んでいる(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch, _START, busy=False)
    assert ahead_sweep.rebake_died("A", "s1", now=NOW) is True


def test_錠を誰かが握っていれば生きている(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch, _START, busy=True)
    assert ahead_sweep.rebake_died("A", "s1", now=NOW) is False


def test_起きた直後は死んだと読まない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`start` は spawn の前に書かれる。錠を握るまでの数秒を「死んだ」にしない。"""
    _setup(tmp_path, monkeypatch, _START, busy=False)
    just_after = datetime(2026, 9, 3, 15, 1, 30, tzinfo=JST)
    assert ahead_sweep.rebake_died("A", "s1", now=just_after) is False


def test_done_が在れば死んでいない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    rows = _START + [{"at": "2026-09-03T15:20:00+09:00", "kind": "done",
                      "video_id": "A", "sha": "s1", "rc": 0}]
    _setup(tmp_path, monkeypatch, rows, busy=False)
    assert ahead_sweep.rebake_died("A", "s1", now=NOW) is False


def test_死んだ回は焼いたことにしない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """印の齢 3時間 を待たずに、もう一度 焼けること（これが直したかった所）。"""
    _setup(tmp_path, monkeypatch, _START, busy=False)
    assert ahead_sweep.rebake_attempted("A", "s1", now=NOW) is False


def test_生きている間は焼いたことにする(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch, _START, busy=True)
    assert ahead_sweep.rebake_attempted("A", "s1", now=NOW) is True


# ---------------------------------------------------------------- 心拍
#
# `start` は**決める側**が spawn の前に書く ＝ 錠を握れたことを1つも言っていない。
# 手で `--rebake-run` を撃った回は `start` すら残さないので、画面の「いま焼いています」が
# **前の回の時刻**を出していた（2026-09-03 16:2x に実測）。`beat` は錠を取った印。

_BEAT = [{"at": "2026-09-03T15:00:54+09:00", "kind": "start", "video_id": "A", "sha": "s1"},
         {"at": "2026-09-03T15:01:10+09:00", "kind": "beat", "video_id": "A", "sha": "s1"}]


def test_心拍だけでも死んでいると読める(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch, _BEAT, busy=False)
    assert ahead_sweep.rebake_died("A", "s1", now=NOW) is True


def test_心拍のあと錠が握られていれば生きている(tmp_path: Path,
                                     monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch, _BEAT, busy=True)
    assert ahead_sweep.rebake_died("A", "s1", now=NOW) is False


def test_心拍は_その日の上限を食わない() -> None:
    """`_baked_today()` は `start` しか数えないこと（心拍で二重に数えない）。"""
    assert ahead_sweep._baked_today(_BEAT, "2026-09-03", busy=False) == 0
    assert ahead_sweep._baked_today(_BEAT, "2026-09-03", busy=True) == 1
