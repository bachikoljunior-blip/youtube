"""`critic.critique()` は「2つ を比べる本で、その違いが先に言われているか」を必ず訊く。

2026-09-13 14:xx（hourly・Opus）に足した。**足した理由は実物 1件**:

  09/14 の本（`2026-09-14-menjo-2bunno1`）は **免除 と 未納 の差**だけを 12コマ 使って計算するのに、
  **その 2つ の違い（申請したかどうか）を コマ9 の落ちまで 1度も言っていませんでした**
  ＝ 視聴者は コマ1〜8 を「何と何を比べているか」を持たずに聞く。
  **輪は 5周 閉じており**（`loop_sig` `2:b8ce2f192bf9`）、冷読 も critique も 1度も名指ししていません。

**なぜ §3 の 2 で止まらなかったか**: あの行は「制度名を出したら、その場で1文で言い換える」で、
`未納` は**制度名に見えません**（漢字2字の日常語に見えて、中身は「申請しなかった」という法の区別）。
＝ 語の見た目では拾えない ＝ **問いの側に置くしかない**（オーナー 2026-09-11 19:3x
「今回だけ教えてもまたおんなじことになるだろ」＝ その本だけ直さず 型 に入れる）。

**この検査が落ちたら**、critique の問いからこの行が消えたということ ——
消すなら、同じ問いをどこが持つかを先に決めてから消すこと（決めは `docs/METHOD.md` §3 の 2-b）。
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


def _prompt(monkeypatch):
    seen = {}

    def fake_ask(p, model="sonnet", timeout=300):
        seen["prompt"] = p
        return '{"items": []}'

    monkeypatch.setattr(critic, "ask", fake_ask)
    critic.critique(Script(**_SCRIPT))
    return seen["prompt"]


def test_比べる2つの違いを先に言っているかを訊いている(monkeypatch):
    p = _prompt(monkeypatch)
    assert "2つ を比べているなら" in p, "比べる本の問いが消えている"
    assert "比べ始めるより前" in p, "「先に言われているか」の向きが消えると、落ちに置いた本を通す"


def test_言われていなければrealだと言っている(monkeypatch):
    """nitpick で返されると、輪は「1番目が言いがかり」で閉じます（§4 (1) の終わり条件）。"""
    p = _prompt(monkeypatch)
    i = p.find("2つ を比べているなら")
    assert i >= 0
    assert "real" in p[i:i + 400], "この問いの答えの重みが指定されていない"
