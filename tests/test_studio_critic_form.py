"""**判じる側にも形を渡す**（2026-09-14 17:5x・optimizer・Opus）。

14:2x に長尺（4〜10分・横 1920x1080）を `studio/` へ足したが、`critic` の 3つ の問いは
本の形を **字で** 持っていた:

    cold_read   「次は、**60秒のショート動画**のナレーション全文です」
    critique    「これは **60〜90秒 のショート**です。全部を説明しないこと自体は欠陥ではありません」
    crosscheck  「次は、**1本のショート動画**の『声で読む文』と…」

＝ 10分 の台本を渡しても、**判じる側は 90秒 の本として読みます**。とくに critique の 1文は
「短いから全部は言えない」を**免罪符として渡している**ので、長尺では向きが逆になり得ます。
**赤は 1件も出ません** —— 問いは通り、答えだけが別の本のものになるからです。

**この検査のいちばんの仕事は陰性対照**（下の literal）—— `short` の問いが **1字も動いていない**こと。
**判定の文は 1字も足していません**（それが長尺でも正しいかは `hourly`・GOAL (4-g) 1・§5）。
"""
import pytest

from studio import critic, script


def _script(form="short", n=6):
    title = "t #Shorts" if form == "short" else "t"
    return script.Script(id="t-critic", date="2026-09-15", title=title, takeaway="t", form=form,
                         description="d", notes="n",
                         segments=[script.Segment(say="あ" * 20, show="x") for _ in range(n)])


def _prompt(monkeypatch, fn, s):
    """問いの本文だけを取り出す（`claude -p` は撃たない ＝ **API 0単位・0円**）。"""
    seen = {}

    def _ask(prompt, model="sonnet", timeout=300):
        seen["p"] = prompt
        return "{}"

    monkeypatch.setattr(critic, "ask", _ask)
    fn(s)
    return seen["p"]


# ---- 陰性対照: `short` の字は 1字も動かない -------------------------------------------

def test_cold_readの1行目はshortで不変(monkeypatch):
    p = _prompt(monkeypatch, critic.cold_read, _script("short"))
    assert p.startswith("次は、60秒のショート動画のナレーション全文です。"
                        "あなたは、この話題を知らない一般の視聴者です。\n")


def test_critiqueの1行目と尺の文はshortで不変(monkeypatch):
    p = _prompt(monkeypatch, critic.critique, _script("short"))
    assert p.startswith("次は、60秒のショート動画のナレーション全文と、画面に出る字です。")
    assert "これは 60〜90秒 のショートです。全部を説明しないこと自体は欠陥ではありません。" in p


def test_crosscheckの1行目はshortで不変(monkeypatch):
    p = _prompt(monkeypatch, critic.crosscheck, _script("short"))
    assert p.startswith("次は、1本のショート動画の「声で読む文」と、"
                        "同じ動画の「説明欄」「制作メモ（notes）」です。\n")


# ---- 陽性対照: `long` では 90秒 の字が 1つも残らない ------------------------------------

@pytest.mark.parametrize("fn", [critic.cold_read, critic.critique, critic.crosscheck])
def test_長尺の問いにショートの字が残らない(monkeypatch, fn):
    p = _prompt(monkeypatch, fn, _script("long", n=25))
    head = p.split("---")[0]
    assert "ショート" not in head and "60秒" not in head and "60〜90秒" not in head
    assert "5〜30分" in head or "長尺" in head


def test_長尺のcritiqueは尺を長尺として言う(monkeypatch):
    p = _prompt(monkeypatch, critic.critique, _script("long", n=25))
    assert "これは 5〜30分 の長尺です。" in p
    # **判定の文は 1字も足していない**（長尺でも正しいかは `hourly`・§5）。
    assert "全部を説明しないこと自体は欠陥ではありません。" in p


# ---- 正本は 1か所（`script.Form.words`） -----------------------------------------------

def test_言い方の正本は形の表(monkeypatch):
    """**陽性対照** —— 表を書き換えれば問いが動くこと（＝ `critic` は字を持っていない）。"""
    monkeypatch.setitem(script.LONG.words, "kind", "ためし")
    p = _prompt(monkeypatch, critic.crosscheck, _script("long", n=25))
    assert "1本のためし動画の" in p


def test_形ごとに3つの言い方がそろっている():
    for f in script.FORMS.values():
        assert set(f.words) == {"lead", "span", "kind"}
        assert all(f.words.values())
