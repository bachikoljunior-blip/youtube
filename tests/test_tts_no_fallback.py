"""**外の作りを写した長尺は、google が落ちても open-jtalk へ倒さない**（2026-09-03）。

理由は `src/tts.synthesize_segments` の docstring。ここは3つだけ見る:
  1. `allow_fallback=False` で google が落ちたら例外（open-jtalk は1度も呼ばれない）
  2. 既定（`True`）は今までどおり open-jtalk へ倒れる（ショート・従来の長尺）
  3. `pipeline` は `style: outside_long` の題材にだけ `allow_fallback=False` を渡す（字面）
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src import tts

ROOT = Path(__file__).resolve().parents[1]


def _fake_engines(monkeypatch, *, google_fails: bool):
    calls = {"google": 0, "open-jtalk": 0}

    def google(text, dest: Path, cfg):
        calls["google"] += 1
        if google_fails:
            raise RuntimeError("403 quota")
        dest.write_bytes(b"RIFF")

    def jtalk(text, dest: Path, cfg):
        calls["open-jtalk"] += 1
        dest.write_bytes(b"RIFF")

    monkeypatch.setattr(tts, "_google", google)
    monkeypatch.setattr(tts, "_open_jtalk", jtalk)
    monkeypatch.setattr(tts, "choose_engine", lambda cfg: "google")
    monkeypatch.setattr(tts, "probe_duration", lambda p: 1.0)
    monkeypatch.setattr(tts, "to_speech", lambda t: t)
    return calls


def test_outside_long_does_not_fall_back(tmp_path, monkeypatch):
    calls = _fake_engines(monkeypatch, google_fails=True)
    with pytest.raises(RuntimeError, match="open-jtalk へ"):
        tts.synthesize_segments(["あ", "い"], {"engine": "google"}, tmp_path, allow_fallback=False)
    assert calls["open-jtalk"] == 0


def test_default_still_falls_back(tmp_path, monkeypatch):
    calls = _fake_engines(monkeypatch, google_fails=True)
    out = tts.synthesize_segments(["あ", "い"], {"engine": "google"}, tmp_path)
    assert len(out) == 2 and calls["open-jtalk"] == 2


def test_google_ok_never_touches_jtalk(tmp_path, monkeypatch):
    calls = _fake_engines(monkeypatch, google_fails=False)
    out = tts.synthesize_segments(["あ"], {"engine": "google"}, tmp_path, allow_fallback=False)
    assert len(out) == 1 and calls["open-jtalk"] == 0


def test_pipeline_passes_flag_for_outside_long_only():
    src = (ROOT / "src/pipeline.py").read_text(encoding="utf-8")
    m = re.search(r'allow_fallback=str\(topic\.get\("style"\) or ""\) != "outside_long"', src)
    assert m, "pipeline が outside_long にだけ allow_fallback=False を渡す字面が無い"
