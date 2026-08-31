"""長尺の在庫が尽きた回に、**床がショートとして数えている題**を取らないこと。

## なぜ要る（2026-08-29 11:0x に踏んだ）

`scripts/family_gap.py` の群分けは **id が `s-` で始まるか**だけを見ます
（`is_short = topic.startswith("s-")`）—— **尺は1秒も見ていません。**
`config/hypotheses.yaml` の `族を外へ-ribo8本` の `needs` も同じで、
`startswith('s-ribo-')` で数えます。

だから `s-ribo-…` を**長尺として**出すと:

    床（needs）      「8本 埋まった」と出る      ← 尺を見ていない
    判定（family_gap）「ショート」の群に5分の本が入る ← ここで壊れる

実測: 長尺の在庫が尽きた回に `_hoist_floor_topics` が `s-ribo-` を先頭へ上げ、
`--long` のフォールバックがそのまま2本 作りはじめました。
**外からは成功に見えます**（落ちも警告も出ない）。

**投稿は止めません。** 外したあとに何も残らない回は今までどおり通し、
「その前提の群は、この回のぶんだけ汚れます」と印字します。

**覆る条件**: `family_gap.groups()` が id の接頭辞ではなく実尺
（`data/video_forms.json` など）で群を作るようになったら、この門は要りません。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

import batch_build as b  # noqa: E402


def _pool():
    return [
        {"id": "s-ribo-a", "calc": "ribo", "score": 1.0, "title_seed": "a"},
        {"id": "s-ribo-b", "calc": "ribo", "score": 1.0, "title_seed": "b"},
        {"id": "s-yukyu-a", "calc": "yukyu", "score": 1.0, "title_seed": "c"},
    ]


def test_床の題は長尺のフォールバックから外れる(monkeypatch, capsys):
    from src import floor_topics
    monkeypatch.setattr(floor_topics, "starved",
                        lambda *a, **k: [{"prefix": "s-ribo-", "short": 6}])
    monkeypatch.setattr(b.config, "load_topics", lambda: {"topics": _pool()})
    monkeypatch.setattr(b, "_posted_including_ledger", lambda: set())
    monkeypatch.setattr(b, "_built_ids", lambda: set(), raising=False)
    got = b.pick(2, [], long_form=True)
    ids = [t["id"] for t in got]
    assert ids and all(not i.startswith("s-ribo-") for i in ids), ids


def test_それしか無ければ通す(monkeypatch):
    """**投稿を止めない。** 在庫切れで止めるほうが高い。"""
    from src import floor_topics
    monkeypatch.setattr(floor_topics, "starved",
                        lambda *a, **k: [{"prefix": "s-ribo-", "short": 6,
                                          "need": 8, "built": 2,
                                          "deadline": "2026-09-19",
                                          "lever": "rpm", "stock": 6}])
    only = [t for t in _pool() if t["id"].startswith("s-ribo-")]
    monkeypatch.setattr(b.config, "load_topics", lambda: {"topics": only})
    monkeypatch.setattr(b, "_posted_including_ledger", lambda: set())
    got = b.pick(1, [], long_form=True)
    assert [t["id"] for t in got] == ["s-ribo-a"]
