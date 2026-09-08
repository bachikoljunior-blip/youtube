"""`studio.cli reply` —— 視聴者のコメント1件に、手で書いた返信を1つ付ける口（2026-09-08 15:1x・hourly・Fable）。

門は3つ: 台帳の `viewer_comment` に在る ID にだけ撃つ・同じスレッドに同じ文を2度 撃たない（別の文は通す。会話は同じスレッドに続く）・文が空なら撃たない。
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


def test_同じスレッドに同じ文は2度撃たない_別の文は通る(tmp_path, monkeypatch):
    # 2026-09-08 20:3x（hourly・Fable）: 会話は同じスレッドに続く（1問目の返信に視聴者が2問目を返した実測）。
    # 止めるのは「同じ文」だけ。別の文（次の問いへの答え）は通す。
    _ledger(tmp_path, monkeypatch, [VC, {"event": "replied", "id": "v1", "comment_id": "c1", "text": "x"}])
    svc = _Svc()
    monkeypatch.setattr(yt, "svc", lambda: svc)
    assert cli.cmd_reply(_A("c1", "x")) == 1
    assert svc.bodies == []
    assert cli.cmd_reply(_A("c1", "2問目への答え")) == 0
    assert len(svc.bodies) == 1


def test_空の文と_dry_runは撃たない(tmp_path, monkeypatch):
    p = _ledger(tmp_path, monkeypatch, [VC])
    svc = _Svc()
    monkeypatch.setattr(yt, "svc", lambda: svc)
    assert cli.cmd_reply(_A("c1", "   ")) == 1
    assert cli.cmd_reply(_A("c1", "本文", dry_run=True)) == 0
    assert svc.bodies == []
    assert "replied" not in p.read_text(encoding="utf-8")


def test_人間だと名乗る文とAIを否定する文は撃たない_はいと答える文は通る(tmp_path, monkeypatch):
    # 2026-09-08 21:4x（hourly・Fable）: オーナー「コメントで視聴者にAIですかって聞かれたら何で答えるの？」→ 答えは「はい」。
    # 声は聞けば分かる（08/29「ＡＩナレーショングダグダ」）ので隠せず、嘘が1つ見つかると数字まで疑われる。
    # 陽性対照: 否定の形 3つ と 名乗りの形 1つ が止まり、定型の答え（data/studio/replies/ai-desu.txt）は通る。
    _ledger(tmp_path, monkeypatch, [VC])
    svc = _Svc()
    monkeypatch.setattr(yt, "svc", lambda: svc)
    for bad in ("いいえ、AIではありません。", "ＡＩじゃないですよ。", "人間が書いています。", "私は元社労士として答えます。"):
        assert cli.cmd_reply(_A("c1", bad)) == 1, bad
    assert svc.bodies == []
    honest = "はい。声は機械の読み上げで、台本もAIが書いています。数字は日本年金機構などの公表ページで確かめてから出しています。"
    assert cli.cmd_reply(_A("c1", honest)) == 0
    assert len(svc.bodies) == 1


def test_定型の答えのファイルは門を通る():
    from pathlib import Path
    import studio.script as script
    text = Path("data/studio/replies/ai-desu.txt").read_text(encoding="utf-8").strip()
    assert text.startswith("はい")
    assert not script.AI_DENIAL.search(text) and not script.HUMAN_CLAIM.search(text)
