"""**選ぶ側にも控えを通す**（2026-08-16 07:5x）。

`pick` はチャンネルの説明欄からだけ「投稿済み」を復元していました。
復元の口は**両方とも欠けます** —— uploads プレイリストは予約中を落とし、
`search` は1日枠を使い切ります（HTTP 429）。欠けたぶんは**未投稿として
選び直され**、動画を1本まるごと作った後で、投稿直前の門が止めます。

**実測（この回）**: 作った8本のうち **2本（25%）が、この形で捨てになりました。**

    s-furusato-5   作った → 却下（既にある b3ZewNvalXc と同じテーマID）
    s-shitsugyo-6  作った → 却下（既にある 8PMLfjjCe4w と同じテーマID）

**門は正しく働いています。**間違っていたのは**選ぶ側**です。
ここが緩むと、静かに生成の何割かが消えます（**落ちないので気づけません** ——
`data/batch_runs.jsonl` に「予約が失敗」と出るだけで、原因は書かれない）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build  # noqa: E402


@pytest.fixture
def ledger(monkeypatch, tmp_path):
    """控えを差し替える。**実物の `data/uploaded.jsonl` は触らない。**"""
    def _write(rows):
        path = tmp_path / "uploaded.jsonl"
        path.write_text(
            "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
            encoding="utf-8")
        from src import config, dupes
        monkeypatch.setattr(config, "ROOT", tmp_path)
        monkeypatch.setattr(dupes, "LEDGER", "uploaded.jsonl")
    return _write


def _row(topic, vid="v1"):
    return {"video_id": vid, "topic": topic, "title": f"{topic} の題",
            "at": "2026-08-26T01:00:00Z"}


def test_口が落としたテーマを控えが拾う(monkeypatch, ledger):
    ledger([_row("s-shitsugyo-6")])
    monkeypatch.setattr(batch_build.history, "posted_topic_ids", lambda: {"s-kojo-1"})
    posted = batch_build._posted_including_ledger()
    assert "s-shitsugyo-6" in posted, \
        "控えにしか無い投稿済みテーマを取り逃している（作ってから却下される）"
    assert "s-kojo-1" in posted, "チャンネル側のぶんが落ちている"


def test_控えが空でもチャンネルのぶんは残る(monkeypatch, ledger):
    ledger([])
    monkeypatch.setattr(batch_build.history, "posted_topic_ids", lambda: {"s-kojo-1"})
    assert batch_build._posted_including_ledger() == {"s-kojo-1"}


def test_足したことを黙らない(monkeypatch, ledger, capsys):
    """差は「口が欠けた量」そのもの。**読める場所がここしかありません。**"""
    ledger([_row("s-shitsugyo-6")])
    monkeypatch.setattr(batch_build.history, "posted_topic_ids", lambda: set())
    batch_build._posted_including_ledger()
    out = capsys.readouterr().out
    assert "s-shitsugyo-6" in out and "控え" in out, \
        "控えから足したことが表に出ていない（口の欠けに気づけない）"


def test_テーマIDの無い行は数えない(monkeypatch, ledger):
    ledger([{"video_id": "v9", "topic": "", "title": "題", "at": None}])
    monkeypatch.setattr(batch_build.history, "posted_topic_ids", lambda: set())
    assert batch_build._posted_including_ledger() == set(), \
        "空のテーマIDを投稿済みに数えている"


def test_pickが控えのぶんを実際に外す(monkeypatch, ledger):
    """和を取るだけでなく、**`pick` の返りから消えている**ことまで見る。"""
    ledger([_row("s-aaa-1")])
    monkeypatch.setattr(batch_build.history, "posted_topic_ids", lambda: set())
    monkeypatch.setattr(batch_build.config, "load_topics", lambda: {"topics": [
        {"id": "s-aaa-1", "calc": "aaa", "score": 9.0},
        {"id": "s-bbb-1", "calc": "bbb", "score": 1.0},
    ]})
    got = [t["id"] for t in batch_build.pick(2, [])]
    assert got == ["s-bbb-1"], f"控えのテーマが選ばれている: {got}"
