"""`next_slot.rebake_input_lines` は、ショート（`style: outside_short`）を**ショートの物差し**で数える。

2026-09-05 13:1x に実測: 09/06 の枠の `3gZ38lfsJpY`（156秒・`outside_short.probe` = yes）に
長尺の脚（冒頭／章・締め／間合い／尺 20分〜）を当てて「台本ごと書き下ろす焼き直し」を勧めていた。
"""
from __future__ import annotations

import json
from pathlib import Path

from src import daily_pick, next_slot, outside_short


def _stash(tmp_path: Path, vid: str, chars: int, title: str) -> Path:
    q = tmp_path / "data" / "critique_queue"
    q.mkdir(parents=True)
    body = ("ねんきん定期便を上から順に開けます。" * 40)[:chars]
    (q / f"{vid}.script.json").write_text(json.dumps({
        "title": title, "segments": [{"narration": body}]}, ensure_ascii=False), encoding="utf-8")
    return q


def _wire(monkeypatch, tmp_path: Path, q: Path, style: str) -> None:
    monkeypatch.setattr(next_slot, "ROOT", tmp_path)
    monkeypatch.setattr(daily_pick, "QUEUE", q)
    monkeypatch.setattr(daily_pick, "_topics", lambda: [{"id": "t", "style": style}])


def test_outside_short_that_passes_the_hard_leg_offers_script_rebake(monkeypatch, tmp_path):
    lo, _hi = outside_short.total_chars_band()
    q = _stash(tmp_path, "v1", lo + 20, "【定期便】開ける順")
    _wire(monkeypatch, tmp_path, q, "outside_short")
    out = "\n".join(next_slot.rebake_input_lines("v1", "t"))
    assert "--script" in out
    assert "台本ごと書き下ろす" not in out
    assert "冒頭" not in out and "間合い" not in out


def test_outside_short_below_the_band_asks_for_a_rewrite(monkeypatch, tmp_path):
    q = _stash(tmp_path, "v2", 140, "【定期便】開ける順")
    _wire(monkeypatch, tmp_path, q, "outside_short")
    out = "\n".join(next_slot.rebake_input_lines("v2", "t"))
    assert "台本ごと書き下ろす" in out
    assert "(1) 尺" in out
    assert "冒頭" not in out


def test_topic_without_a_style_still_uses_the_long_legs(monkeypatch, tmp_path):
    lo, _hi = outside_short.total_chars_band()
    q = _stash(tmp_path, "v3", lo + 20, "【定期便】開ける順")
    _wire(monkeypatch, tmp_path, q, "")
    out = "\n".join(next_slot.rebake_input_lines("v3", "t"))
    # 長尺の物差し（`pick_legs`）のまま —— 700字 の本は 尺 で落ちる
    assert "台本ごと書き下ろす" in out
    assert "尺" in out
