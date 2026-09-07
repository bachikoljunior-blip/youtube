"""**親は「周を記録して押す」を、サブを立てるより先にやること。**

## この検査が守っているもの（2026-09-07 22:4x・optimizer・Opus）

それまでの順は「**立てる → 記録 → 押す**」で、2つ壊していた。

**(1) サブの最初の `git fetch` が、この周の押しに間に合わない。**
サブの本文の第1手は「fetch して merge しろ」だが、親がまだ押していないので
`Already up to date.` と出る。**実測 09/07 に2回** —— 10:19（origin の先頭
`613ac913` は 10:18:55 に在った）と 22:39（2度目の fetch で `89619b55` へ早送り）。
この食い違いに 01:3x の回が `git merge-base --is-ancestor` の「確かめ」を足し、
12:4x の回が撃って**同じ述語を同じ古い ref に訊いているだけ**と分かって外した
＝ **順のせいで生まれた欠陥を、2周ぶんが追いかけた。**

**(2) サブを立てているあいだ、周が押されない窓が丸ごと開く。**
その窓で別の親が起きると `data/rounds.jsonl` は空のままなので、両方が GO を読む。
実測: 交代の日に親が2人になり、オーナー「**なんでサブ増えてんの？**」（08-25）。

**覆る条件**: 記録したのに立てられなかった回（429 など）が続いたら、失うのは1周ぶん。
そのときは**順を戻すのではなく立て直す** —— 戻すと (2) の側に戻り、そちらが高くつく。
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PARENT_DOC = ROOT / "docs" / "trigger_parent.md"
NEXT_ROUND = ROOT / "scripts" / "next_round.py"


def _first_move_block() -> str:
    """親の第1節の手順ブロック（`git pull` から始まる、起動口の下の塊）。"""
    doc = PARENT_DOC.read_text(encoding="utf-8")
    i = doc.index("**どちらで起きても、やることは同じです。考えることはありません。**")
    return doc[i : i + 3000]


def test_手順の記録と押しが立てるより先にある() -> None:
    """`--record` の行が、Agent へ本文を渡す行より**上**にあること。"""
    block = _first_move_block()
    record = block.index("next_round.py --record")
    spawn = block.index("Agent ツールへ渡す")
    assert record < spawn, (
        "親の手順で `--record` がサブを立てるより後ろに戻っています。"
        "戻すと (1) サブの最初の fetch がこの周の押しに間に合わず、"
        "(2) 立てているあいだ 周が押されない窓が開きます（この file の docstring）。"
    )


def test_手順の押しが立てるより先にある() -> None:
    """`push` の行も、Agent へ渡す行より上にあること（記録だけ先でも窓は閉じない）。"""
    block = _first_move_block()
    push = block.index("push")
    spawn = block.index("Agent ツールへ渡す")
    assert push < spawn, (
        "記録だけ先にして押しを後ろに置くと、周は origin に出ないので "
        "(1)(2) のどちらも閉じません。"
    )


def test_道具の印字も同じ順を言う() -> None:
    """**手順は道具の側にある** —— GO の枝が「先に記録して押す」を印字すること。

    親は毎周この印字を読む。文書だけ直して印字が古いと、印字のほうが勝つ
    （`docs/trigger_parent.md` の「順番を本文に写さないこと」と同じ形）。
    """
    src = NEXT_ROUND.read_text(encoding="utf-8")
    go = src.index('print("GO " + " ".join(roles))')
    tail = src[go : go + 4000]
    assert "先に記録して押すこと（立てる前）" in tail, (
        "`next_round.py` の GO の枝が「先に記録して押すこと（立てる前）」を"
        "印字しなくなっています。親は印字のほうを読みます。"
    )
    assert not re.search(r"立てたら:\s*python scripts/next_round\.py --record", src), (
        "「立てたら: --record」の印字が戻っています ＝ 立てる → 記録 の古い順です。"
    )


def test_覆る条件が書いてある() -> None:
    """順を戻すときの条件が文書に残っていること（理由の無い規則は惰性で戻される）。"""
    doc = PARENT_DOC.read_text(encoding="utf-8")
    i = doc.index("なぜ「記録と押し」が先なのか")
    block = doc[i : i + 2500]
    assert "覆る条件" in block
    assert "立て直す" in block
