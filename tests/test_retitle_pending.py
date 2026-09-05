"""**閉じた窓で決めた題が、戻った窓の掃きで書かれること**（2026-09-05 13:4x）。

`src.retitles.queue()`（0単位）→ `ahead_sweep.retitle_pending()`（窓が戻った周に 50単位）。
済みの印は別に持たず、`retitle.py` が帳面（`data/retitled.jsonl`）へ足した字で消える。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import retitles  # noqa: E402

_gspec = importlib.util.spec_from_file_location(
    "ahead_gate_for_retitle", ROOT / "scripts" / "ahead_gate.py")
ahead_gate = importlib.util.module_from_spec(_gspec)
sys.modules.setdefault("ahead_gate", ahead_gate)
_gspec.loader.exec_module(ahead_gate)
_sspec = importlib.util.spec_from_file_location(
    "ahead_sweep_for_retitle", ROOT / "scripts" / "ahead_sweep.py")
sweep = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(sweep)

NOW = datetime(2026, 9, 5, 7, 30, tzinfo=timezone.utc)


def test_queue_then_pending_then_cleared_by_the_ledger(tmp_path: Path) -> None:
    q = tmp_path / "retitle_pending.jsonl"
    led = tmp_path / "retitled.jsonl"
    retitles.queue("vid1", "【定期便】古い案", why="a", path=q,
                   at=datetime(2026, 9, 5, 4, 0, tzinfo=timezone.utc))
    retitles.queue("vid1", "【定期便】新しい案？", why="b", path=q,
                   at=datetime(2026, 9, 5, 4, 30, tzinfo=timezone.utc))
    rows = retitles.pending(path=q, ledger=led)
    assert [r["title"] for r in rows] == ["【定期便】新しい案？"]   # 本ごとに最新の1行
    # `retitle.py` が通った ＝ 帳面がその字 → 待ちは消える
    retitles.record("vid1", "【定期便】新しい案？", prev="x", path=led)
    assert retitles.pending(path=q, ledger=led) == []


def test_sweep_waits_while_the_day_quota_is_closed(capsys) -> None:
    calls: list[list[str]] = []
    line = sweep.retitle_pending(NOW, pending=[{"video_id": "v", "title": "【t】？"}],
                                 quota_open=False, run=lambda a: calls.append(a) or 0)
    assert calls == []
    assert "日枠" in line
    assert "[retitle]" in capsys.readouterr().out


def test_sweep_writes_each_pending_title_when_the_window_is_back() -> None:
    calls: list[list[str]] = []
    line = sweep.retitle_pending(NOW, pending=[{"video_id": "v1", "title": "【a】？"},
                                               {"video_id": "v2", "title": "【b】？"}],
                                 quota_open=True, run=lambda a: calls.append(a) or 0)
    assert [c[-2:] for c in calls] == [["v1", "【a】？"], ["v2", "【b】？"]]
    assert all(c[1].endswith("scripts/retitle.py") for c in calls)
    assert "2本 を書きました" in line


def test_sweep_dry_run_does_not_write() -> None:
    calls: list[list[str]] = []
    sweep.retitle_pending(NOW, dry_run=True, pending=[{"video_id": "v1", "title": "【a】？"}],
                          quota_open=True, run=lambda a: calls.append(a) or 0)
    assert calls == []


def test_sweep_is_silent_and_free_when_nothing_is_pending() -> None:
    calls: list[list[str]] = []
    line = sweep.retitle_pending(NOW, pending=[], quota_open=None,
                                 run=lambda a: calls.append(a) or 0)
    assert calls == [] and "0単位" in line


def test_hold_title_line_measures_the_queued_title(monkeypatch) -> None:
    """`[きょうの1本]` は帳面の古い題ではなく、待ち行列の題で特徴を測り、待ちが在ると言う。"""
    from src import hold
    monkeypatch.setattr(retitles, "pending",
                        lambda **_k: [{"video_id": "vq", "title": "【定期便】届いたら？"}])
    out = "\n".join(hold.title_feature_line({"video_id": "vq", "title": "古い題", "duration_s": 150.0},
                                            "ショート"))
    if not out:                       # 帯の実測（niche_corpus）が無い作業場では何も出ない
        return
    assert "[題の待ち]" in out and "【定期便】届いたら？" in out
