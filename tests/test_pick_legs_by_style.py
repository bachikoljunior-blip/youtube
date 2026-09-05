"""`daily_pick.pick_legs` / `draft_legs` は、**題材の `style` で物差しを選ぶ**。

2026-09-05 15:0x に実測: 09/06 の枠の `3gZ38lfsJpY`（156秒・`outside_short.probe` = yes）に
`pick_legs` が長尺の5脚を当て、`next_slot.legs_under_current_code()` が
「いまのコードで数え直すと 5脚 落ちています —— 焼き直す理由が在ります」と刷っていた
（`next_slot._stash_legs` は 13:1x に自分の側だけ直っていた ＝ 同じ物差しの、もう1つの読み口）。
"""
from __future__ import annotations

import json
from pathlib import Path

from src import daily_pick, next_slot, outside_short


def _stash(tmp_path: Path, vid: str, chars: int, title: str, topic: str) -> Path:
    q = tmp_path / "data" / "critique_queue"
    q.mkdir(parents=True, exist_ok=True)
    body = ("ねんきん定期便を上から順に開けます。" * 60)[:chars]
    (q / f"{vid}.script.json").write_text(json.dumps({
        "title": title, "segments": [{"narration": body}]}, ensure_ascii=False), encoding="utf-8")
    (q / f"{vid}.json").write_text(json.dumps({"video_id": vid, "topic": topic}), encoding="utf-8")
    return q


def _wire(monkeypatch, tmp_path: Path, q: Path, style: str) -> None:
    monkeypatch.setattr(next_slot, "ROOT", tmp_path)
    monkeypatch.setattr(daily_pick, "ROOT", tmp_path)
    monkeypatch.setattr(daily_pick, "QUEUE", q)
    monkeypatch.setattr(daily_pick, "_topics", lambda: [{"id": "t", "style": style}])


def test_outside_short_in_band_passes_without_the_long_legs(monkeypatch, tmp_path):
    lo, _hi = outside_short.total_chars_band()
    q = _stash(tmp_path, "v1", lo + 20, "【定期便】開ける順", "t")
    _wire(monkeypatch, tmp_path, q, "outside_short")
    # 題材は控えの `<ID>.json` から引く（`topic` を渡さなくてよい）
    assert daily_pick.pick_legs("v1") == ([], None)
    assert daily_pick.pick_legs("v1", topic="t") == ([], None)
    out = "\n".join(next_slot.legs_under_current_code("v1"))
    assert "焼き直す理由が在ります" not in out
    assert "冒頭" not in out and "間合い" not in out


def test_outside_short_below_the_band_fails_only_the_length_leg(monkeypatch, tmp_path):
    q = _stash(tmp_path, "v2", 140, "【定期便】開ける順", "t")
    _wire(monkeypatch, tmp_path, q, "outside_short")
    bad, why = daily_pick.pick_legs("v2")
    assert bad == ["(1) 尺"] and why is None
    # soft の脚（題・中身）は `bad` に入れない
    assert daily_pick.metadata_only(bad) is False


def test_topic_without_a_style_keeps_the_long_legs(monkeypatch, tmp_path):
    lo, _hi = outside_short.total_chars_band()
    q = _stash(tmp_path, "v3", lo + 20, "【定期便】開ける順", "t")
    _wire(monkeypatch, tmp_path, q, "")
    bad, why = daily_pick.pick_legs("v3")
    assert why is None
    assert "尺" in bad          # 700字 の本は長尺の物差しでは尺で落ちる


def test_draft_legs_uses_the_short_ruler_for_outside_short(monkeypatch, tmp_path):
    lo, _hi = outside_short.total_chars_band()
    q = _stash(tmp_path, "v4", lo + 20, "【定期便】開ける順", "t")
    _wire(monkeypatch, tmp_path, q, "outside_short")
    d = tmp_path / "data" / "scripts"
    d.mkdir(parents=True)
    (d / "t.script.json").write_text((q / "v4.script.json").read_text(encoding="utf-8"),
                                     encoding="utf-8")
    assert daily_pick.draft_legs("t") == ([], None)


def test_stash_legs_is_now_just_pick_legs(monkeypatch, tmp_path):
    lo, _hi = outside_short.total_chars_band()
    q = _stash(tmp_path, "v5", lo + 20, "【定期便】開ける順", "t")
    _wire(monkeypatch, tmp_path, q, "outside_short")
    assert next_slot._stash_legs("v5", "t", q, daily_pick) == ([], None, [])
