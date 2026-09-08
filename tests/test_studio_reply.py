"""`studio.cli reply` —— 視聴者のコメント1件に、手で書いた返信を1つ付ける口（2026-09-08 15:1x・hourly・Fable）。

門は3つ: 台帳の `viewer_comment` に在る ID にだけ撃つ・同じ ID に2度 撃たない・文が空なら撃たない。
旧 `scripts/post_pending_comments.py` の自動投稿とは違い、背景から呼ぶ口は無い。
"""
from __future__ import annotations

import json

import studio.cli as cli
import studio.common as common
import studio.yt as yt


class _Svc:
    def __init__(self):
        self.bodies = []

    def comments(self):
        return self

    def insert(self, **kw):
        self.bodies.append(kw)
        return self

    def execute(self):
        return {"id": "reply-1"}


def _ledger(tmp_path, monkeypatch, rows):
    p = tmp_path / "ledger.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    monkeypatch.setattr(common, "LEDGER", p)
    monkeypatch.setattr(common, "DATA", tmp_path)
    return p


class _A:
    def __init__(self, comment_id, text, dry_run=False):
        self.comment_id, self.text, self.dry_run = comment_id, text, dry_run


VC = {"event": "viewer_comment", "id": "v1", "comment_id": "c1", "author": "@x", "text": "そこが知りたい"}


def test_台帳に在るIDへ_parentIdで1件_撃って_repliedを残す(tmp_path, monkeypatch):
    p = _ledger(tmp_path, monkeypatch, [VC])
    svc = _Svc()
    monkeypatch.setattr(yt, "svc", lambda: svc)
    assert cli.cmd_reply(_A("c1", "はい、そのとおりです。")) == 0
    assert len(svc.bodies) == 1
    assert svc.bodies[0]["body"]["snippet"]["parentId"] == "c1"
    assert svc.bodies[0]["body"]["snippet"]["textOriginal"] == "はい、そのとおりです。"
    rows = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines()]
    assert rows[-1]["event"] == "replied" and rows[-1]["comment_id"] == "c1" and rows[-1]["id"] == "v1"


def test_台帳に無いIDには撃たない(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch, [VC])
    svc = _Svc()
    monkeypatch.setattr(yt, "svc", lambda: svc)
    assert cli.cmd_reply(_A("c9", "…")) == 1
    assert svc.bodies == []


def test_同じIDに2度は撃たない(tmp_path, monkeypatch):
    _ledger(tmp_path, monkeypatch, [VC, {"event": "replied", "id": "v1", "comment_id": "c1", "text": "x"}])
    svc = _Svc()
    monkeypatch.setattr(yt, "svc", lambda: svc)
    assert cli.cmd_reply(_A("c1", "もう一度")) == 1
    assert svc.bodies == []


def test_空の文と_dry_runは撃たない(tmp_path, monkeypatch):
    p = _ledger(tmp_path, monkeypatch, [VC])
    svc = _Svc()
    monkeypatch.setattr(yt, "svc", lambda: svc)
    assert cli.cmd_reply(_A("c1", "   ")) == 1
    assert cli.cmd_reply(_A("c1", "本文", dry_run=True)) == 0
    assert svc.bodies == []
    assert "replied" not in p.read_text(encoding="utf-8")
