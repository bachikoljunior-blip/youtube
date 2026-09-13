"""冷読は「**分かったが、本文は説明していない**」側（`assumed`）も訊く。

2026-09-13 14:2x（hourly・Opus）に足した。

**足した理由**（derivation は `critic.cold_read` の註・JOURNAL 09/13 14:2x）:
`unclear` は「**分からなかった**」を訊くので、**模型が元から知っている語の欠落は原理的に落ちます**。
実物: 09/14 の本は **免除 と 未納 の差**だけを 12コマ 使って計算しながら、その 2つ の違い
（**申請したかどうか**）を コマ9 の落ちまで 1度も言わず、**輪 5周・冷読 5回・critique 5回 が
1度も名指ししていません**。オーナーは翌日「**説明不足があると思うな。話がつかめない**」（`2e87f87e`）。

**この検査が守るのは、問いの向きです** —— 「分からなかったか」ではなく
「**知っている自分を差し引くと、動画の言葉だけで追えるか**」。
向きが戻ったら（`assumed` が `unclear` の言い換えになったら）、この道具は 5周 通した本を
また通します。**覆る条件 3つ は `critic.cold_read` の註**。
"""
from __future__ import annotations

import studio.critic as critic
from studio.script import Script

_SCRIPT = {
    "id": "t1", "date": "2026-09-14", "title": "t", "takeaway": "たてまえ",
    "description": "", "notes": "",
    "segments": [
        {"say": "全額免除の月は半分です。", "show": "a", "sub": "b"},
        {"say": "未納は0です。", "show": "c", "sub": "d"},
    ],
}


def _prompt(monkeypatch, reply='{"takeaway": "あ", "unclear": [], "assumed": []}'):
    seen = {}

    def fake_ask(p, model="haiku", timeout=120):
        seen["prompt"] = p
        return reply

    monkeypatch.setattr(critic, "ask", fake_ask)
    seen["out"] = critic.cold_read(Script(**_SCRIPT))
    return seen


def test_assumed_を訊いている(monkeypatch):
    p = _prompt(monkeypatch)["prompt"]
    assert "assumed" in p, "欄が消えると、知っている語の欠落は二度と落ちてこない"
    assert "説明していない" in p


def test_分からなかったとは別物だと言っている(monkeypatch):
    """ここが混ざると `assumed` は `unclear` の写しになり、足した意味が消えます。"""
    p = _prompt(monkeypatch)["prompt"]
    assert "「分からなかった」ではありません" in p
    assert "元から知っていたから分かった" in p


def test_日本語で返せと言っている(monkeypatch):
    """`unclear` と同じ理由 —— 英語の draw は件数が別物になります（`cold_read` の註）。"""
    assert "assumed も、かならず日本語" in _prompt(monkeypatch)["prompt"]


def test_返りの_assumed_を落とさない(monkeypatch):
    r = _prompt(monkeypatch, '{"takeaway": "あ", "unclear": [], "assumed": ["未納とは何か"]}')["out"]
    assert r.get("assumed") == ["未納とは何か"], "台帳と印字が読む欄なので、ここで落とすと数えられない"
