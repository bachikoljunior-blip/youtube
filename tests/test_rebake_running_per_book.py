"""**錠はひとつしか無いので、「誰かが焼いている」を「この本を焼いている」と読まないこと。**

実測 2026-09-04 03:2x（この検査を足した回が、実物で踏んだ）:

    23:28:27  `1huadpEk6HY`（sha d4ec75716d0e）の `beat` —— そのあと `done` 無し
    03:15:50  `DfFyu8qZq3I` の `start` → 03:16:10 `beat`（**錠はこちらが握った**）
    03:2x     `machine_rebake_lines()` が **2本とも**「いま焼いています」と印字

`rebake_died()` の最後が `return not rebake_busy()` で、`rebake_busy()` は
**錠がひとつ**なので「誰か」しか言えなかった。そのせいで `--write` の `[次の枠]` は
09/04 09:00 に出る `1huadpEk6HY` について「`improve` は機械の側で進んでいます →
**本ではなく別の所へ**」と刷り続け、**規則3 の当てどころが毎周 選択肢から消えていた**
（実物の機械は `rebake_plan_for` で `do: False`＝**未来永劫この本を焼かない**）。

`beat` は `rebake_run()` が `flock` を取った**直後にしか**書かれないので、
**より新しい `beat` が別の本に在る ＝ この本は錠を手放している**。
註は `ahead_sweep.rebake_running()`。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import ahead_sweep

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 4, 3, 25, tzinfo=JST)

# 実物の帳面と同じ並び（古い順）。A は 23:28 に錠を取り、B は 03:16 に取った。
_ROWS = [
    {"at": "2026-09-03T23:28:13+09:00", "kind": "start", "video_id": "A", "sha": "sa"},
    {"at": "2026-09-03T23:28:27+09:00", "kind": "beat", "video_id": "A", "sha": "sa"},
    {"at": "2026-09-04T03:15:50+09:00", "kind": "start", "video_id": "B", "sha": "sb"},
    {"at": "2026-09-04T03:16:10+09:00", "kind": "beat", "video_id": "B", "sha": "sb"},
]


def _setup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, rows: list[dict],
           *, busy: bool) -> None:
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    monkeypatch.setattr(ahead_sweep, "_rebake_rows", lambda root=None: rows)
    monkeypatch.setattr(ahead_sweep, "rebake_busy", lambda: busy)
    (tmp_path / "A-sa").write_text("2026-09-03T23:28:13+09:00", encoding="utf-8")
    (tmp_path / "B-sb").write_text("2026-09-04T03:15:50+09:00", encoding="utf-8")


def test_錠を握っているのは最後に心拍を書いた本だけ(tmp_path: Path,
                                                    monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch, _ROWS, busy=True)
    assert ahead_sweep.rebake_running("B", "sb") is True
    # **ここが 2026-09-04 に踏んだ所** —— 前は錠が塞がっているだけで True になっていた
    assert ahead_sweep.rebake_running("A", "sa") is False


def test_錠が空いていれば誰も焼いていない(tmp_path: Path,
                                          monkeypatch: pytest.MonkeyPatch) -> None:
    _setup(tmp_path, monkeypatch, _ROWS, busy=False)
    assert ahead_sweep.rebake_running("B", "sb") is False
    assert ahead_sweep.rebake_running("A", "sa") is False


def test_別の本が焼いている間_この本は死んだ扱い(tmp_path: Path,
                                                monkeypatch: pytest.MonkeyPatch) -> None:
    """`rebake_died()` は「誰か」ではなく「この本か」で決めること。"""
    _setup(tmp_path, monkeypatch, _ROWS, busy=True)
    assert ahead_sweep.rebake_died("A", "sa", now=NOW) is True
    assert ahead_sweep.rebake_died("B", "sb", now=NOW) is False


def test_心拍が1つも無い帳面では錠の誰かをそのまま返す(tmp_path: Path,
                                                      monkeypatch: pytest.MonkeyPatch) -> None:
    """`--rebake-run` を手で撃った古い回（`beat` を残さない）では割れない。前の形のまま。"""
    rows = [r for r in _ROWS if r["kind"] != "beat"]
    _setup(tmp_path, monkeypatch, rows, busy=True)
    assert ahead_sweep.rebake_running("A", "sa") is True
