"""**門の節が、まだ測れていない面（説明欄）を出しているか。**（2026-08-30 夜）

## なぜ要るか

解除条件 1・2・5 を閉じた根拠は `src/legacy_corpus.py` で、
そこが見たのは **`data/critique_queue/<id>.json` の台本の控え 694本**です。
**説明欄（`description_body`）は、その分母に1本も入っていません。**

ところが出口の門 `verify._check_no_human_expert_claim()` は、
**`description_body` を第2の欄として当てています** ——
つまり**これから作る本では見ている面を、既にある735本では一度も見ていない。**
審査する側から見ると、説明欄は**動画を再生しなくても読める面**です。

**穴は、見えなければ埋まりません。** `scripts/status.py` は
`descriptions` を1文字も呼んでおらず、停止中の正本 `eta.py --gate` にも
出ていませんでした。**だから毎周この節に出します。**

実測 2026-08-30 22:31Z: `--refresh` は `quotaExceeded`（403）で 0/735。
**日枠は JST 16:00 に戻ります** —— 止まっている理由は判断ではなく、枠です。

## 覆る条件

**測り終わったら、この行は消えること**（`got >= asked`）。
消えないなら、それは「毎周 同じ警告を出す」だけの飾りになります。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import eta  # noqa: E402
from src import descriptions as D  # noqa: E402


def _gate(monkeypatch, payload: dict | None) -> str:
    monkeypatch.setattr(D, "load", lambda *a, **k: payload)
    return "\n".join(eta.gate_lines())


def test_the_hole_is_named_while_nothing_is_measured(monkeypatch):
    out = _gate(monkeypatch, {"asked": 735, "got": 0, "partial": True,
                              "videos": []})
    assert "説明欄は、まだ測れていません" in out
    assert "0 / 735本" in out


def test_it_says_how_to_shoot_it_and_what_it_costs(monkeypatch):
    out = _gate(monkeypatch, {"asked": 735, "got": 0, "partial": True,
                              "videos": []})
    assert "python -m src.descriptions --refresh" in out
    assert "15単位" in out


def test_a_quota_stop_is_not_reported_as_missing_videos(monkeypatch):
    """**「返らなかった」を「無い」と言わないこと**（`src/descriptions.py` と同じ門）。"""
    out = _gate(monkeypatch, {"asked": 735, "got": 0, "partial": True,
                              "videos": []})
    assert "quotaExceeded" in out
    assert "「チャンネルに無い」ではありません" in out


def test_it_tells_the_next_round_to_reopen_1_and_2_if_a_persona_shows_up(monkeypatch):
    out = _gate(monkeypatch, {"asked": 735, "got": 0, "partial": True,
                              "videos": []})
    assert "--open-gate 1" in out


def test_it_fires_when_nothing_has_ever_been_taken(monkeypatch):
    out = _gate(monkeypatch, None)
    assert "説明欄は、まだ測れていません" in out
    assert "1度も取っていません" in out


def test_it_goes_quiet_once_every_book_is_measured(monkeypatch):
    """**測り終わったら消えること。** 消えないなら、ただの飾りです。"""
    payload = {"asked": 3, "got": 3, "partial": False,
               "videos": [{"video_id": v, "description": "本文"}
                          for v in ("a", "b", "c")]}
    assert "説明欄は、まだ測れていません" not in _gate(monkeypatch, payload)


def test_the_shipped_cache_is_still_the_partial_one():
    """**この repo の実物**（控えを読む側が壊れていないか）。"""
    p = ROOT / "data" / "descriptions.json"
    if not p.is_file():
        return
    d = json.loads(p.read_text(encoding="utf-8"))
    assert isinstance(d.get("asked"), int)
    assert len(d.get("videos") or []) <= d["asked"]
