"""`studio.critic.crosscheck()` は **声と 説明欄・notes の食い違い**だけを見る（§4 (0) の機械の側）。

2026-09-08 02:5x（optimizer・Opus）に足した。**足した理由は実測 2回**:

  2026-09-07 05:4x  説明欄の側に実の誤り1つ・言い過ぎ1つが、critique **5周** を抜けて残った
  2026-09-08 02:5x  **逆向き** —— 説明欄と notes は正しく、**声が2か所 間違っていた**
                    （加給年金を「配偶者といっしょに住んでいたらもらえます」＝ 同居 と言い、
                      同じファイルの説明欄は「同居が必須ではなく、別居でも生計が同じなら対象」。
                      critique は 3周 とも素通り）

**なぜ critique では見つからないか**（この検査がいちばん守りたい所）:
`critic.critique()` が模型に渡すのは `say`/`show`/`sub` **だけ**で、`description` と `notes` を
1文字も渡していない。**渡していない物は、何周 回しても見えない。** だから輪を増やしても解けない。
＝ 下の `test_critique_は説明欄とnotesを渡していない` が、この道具の存在理由そのものです。
**この検査が落ちたら、crosscheck は要らなくなったのではなく、critique の側が変わったということ** ——
そのときは「どちらが (0) を持つか」を先に決めてから、片方を消すこと。
"""
from __future__ import annotations

import studio.critic as critic
from studio.script import Script

_SCRIPT = {
    "id": "t1", "date": "2026-09-09", "title": "t", "takeaway": "たてまえ",
    "description": "同居が必須ではなく、別居でも生計が同じなら対象です",
    "notes": "生計を維持していること（配偶者の年収850万円未満）",
    "segments": [
        {"say": "配偶者といっしょに住んでいたらもらえます。", "show": "a", "sub": "b"},
        {"say": "毎年42万3700円です。", "show": "c", "sub": "d"},
    ],
}


def _s():
    return Script(**_SCRIPT)


def _prompt(monkeypatch, fn):
    """`ask()` を差し替えて、模型に渡る本文をそのまま取り出す。"""
    seen = {}

    def fake_ask(p, model="sonnet", timeout=300):
        seen["prompt"] = p
        seen["model"] = model
        return '{"items": []}'

    monkeypatch.setattr(critic, "ask", fake_ask)
    fn()
    return seen


def test_crosscheck_は説明欄とnotesと声を全部渡す(monkeypatch):
    seen = _prompt(monkeypatch, lambda: critic.crosscheck(_s()))
    p = seen["prompt"]
    assert "同居が必須ではなく" in p, "説明欄が渡っていない ＝ 食い違いは原理的に見つからない"
    assert "生計を維持していること" in p, "notes が渡っていない"
    assert "配偶者といっしょに住んでいたら" in p, "声が渡っていない"
    assert "コマ1" in p and "コマ2" in p, "どのコマかを言えないと直せない"


def test_critique_は説明欄とnotesを渡していない(monkeypatch):
    """**これが crosscheck の存在理由。** critique に説明欄が渡る日が来たら、この検査が教える。"""
    seen = _prompt(monkeypatch, lambda: critic.critique(_s()))
    p = seen["prompt"]
    assert "同居が必須ではなく" not in p
    assert "生計を維持していること" not in p


def test_食い違いが無ければ空で返してよいと言っている(monkeypatch):
    seen = _prompt(monkeypatch, lambda: critic.crosscheck(_s()))
    assert "無理に挙げない" in seen["prompt"], "空を許さないと、毎回 何かを捏造して挙げてくる"


def test_分かりやすさは見ないと言っている(monkeypatch):
    """critique と同じ物を二重に挙げさせない —— 取り分が重なると、直す側がどちらに従うか決められない。"""
    seen = _prompt(monkeypatch, lambda: critic.crosscheck(_s()))
    assert "分かりやすさの評価ではありません" in seen["prompt"]


def test_模型はsonnet(monkeypatch):
    seen = _prompt(monkeypatch, lambda: critic.crosscheck(_s()))
    assert seen["model"] == "sonnet"


def test_返りの形(monkeypatch):
    monkeypatch.setattr(critic, "ask", lambda *a, **k: '{"items": [{"where": "コマ1", "kind": "contradiction"}]}')
    got = critic.crosscheck(_s())
    assert got["items"][0]["kind"] == "contradiction"


def test_cliに口が在る():
    """道具は、口が無ければ撃たれない（§6 の「載せないと次の回が見つけられない」）。"""
    import studio.cli as cli
    assert hasattr(cli, "cmd_crosscheck")
    assert "crosscheck" in cli.__doc__, "docstring の一覧に無い道具は撃たれない"
