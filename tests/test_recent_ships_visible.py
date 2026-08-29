"""重なりを避ける口は、**claim だけでなく ship も**見ること。

## この検査が守っているもの（2026-08-27 19:0x に踏んだ）

`--claim` は**任意**、`--ship` は**必須**（`docs/trigger_main.md` §4 の最低ライン）。
それなのに `run_marker.py --write` の「他の回が何に取りかかっているか」は
**`kind == "claim"` の行しか見ていませんでした。**

実測: この回の `--write` は「直近60分の claim **0件**」を返しました。
同じ時刻の `data/runs.jsonl` には、きょうだいの ship が
**18:0x〜18:4x に4件**（長尺の在庫を掘る回）あります。
この回はそれを見ずに「在庫の底」を claim し、**中身を捨てています。**

`claims()` が見ているのは**意図**、`recent_ships()` が見ているのは**実物**。
重なりを避けるのに効くのは実物のほうです。
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import run_marker  # noqa: E402


def _rows(now: datetime) -> list[dict]:
    return [
        {"at": (now - timedelta(minutes=10)).isoformat(), "session": "other",
         "kind": "ship", "what": "upload 長尺 A を予約"},
        {"at": (now - timedelta(minutes=20)).isoformat(), "session": "me",
         "kind": "ship", "what": "自分のぶん（出さない）"},
        {"at": (now - timedelta(days=3)).isoformat(), "session": "other",
         "kind": "ship", "what": "古すぎる"},
        {"at": (now - timedelta(minutes=5)).isoformat(), "session": "other",
         "kind": "start", "what": ""},
    ]


def test_他の回の直近の_ship_が見える(monkeypatch) -> None:
    now = datetime.now(run_marker.JST)
    monkeypatch.setattr(run_marker, "_records", lambda: _rows(now))
    got = run_marker.recent_ships(60, me="me")
    assert [r["what"] for r in got] == ["upload 長尺 A を予約"], (
        "自分のぶん・古いぶん・ship でないぶんが混ざっています")


def test_claim_が0件でも_ship_があれば黙らない(monkeypatch) -> None:
    """**この検査が本体です。** 08/27 に踏んだのはこの形ちょうど。"""
    now = datetime.now(run_marker.JST)
    monkeypatch.setattr(run_marker, "_records", lambda: _rows(now))
    monkeypatch.setattr(run_marker, "actor_id", lambda: "me")
    lines = run_marker._claim_lines(60)
    assert lines, "claim が 0件 でも、他の回の ship が在れば黙ってはいけません"
    assert any("実際に出したもの" in ln for ln in lines)
    assert any("upload 長尺 A を予約" in ln for ln in lines)


def test_どちらも無ければ何も出さない(monkeypatch) -> None:
    monkeypatch.setattr(run_marker, "_records", list)
    monkeypatch.setattr(run_marker, "actor_id", lambda: "me")
    assert run_marker._claim_lines(60) == []


def test_数え方を写していない() -> None:
    """`claims` と `recent_ships` は、**同じ `_records()` の行**を読むこと。

    別々の口から読み始めると、片方だけが古くなります（この輪が
    いちばん多く踏んでいる形）。
    """
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    body = src[src.index("def recent_ships("):src.index("def _claim_lines(")]
    assert "_records()" in body
