"""**「親は喋るな」と「親は第1節を撃つ」は、両方 立てること**（2026-09-02）。

## なぜ要るか（この回に、実際に片方が片方を消した）

2026-09-02、オーナーが**4回目**の「喋るな／思考するな」を言い、その回が
原文6件を `docs/trigger_parent.md` の**`##` の第1節**として先頭へ置きました。
**言われたことは正しく、置いた場所だけが外れていました** ——
`tests/test_parent_first_move.py` が即座に赤くなっています:

    第1節  「サブを立てる。中身は判断しない」（`next_round.py` / `worktree` /
            `spawn_prompt.rendered.md` が全部ここに在る）
      ↓ 入れ替わった
    第1節  「親は喋らない。考えない。」（**撃つものが1つも書いていない**）

**あの検査が守っているのは「先頭にあるものだけが確実に実行される」**で、
喋るなと言われている親が、**代わりに何をするか**を先頭に持っていなければ、
残るのは「喋るな」だけです。**親が黙って止まります。**
`A10`（自動実行は永久に止まることがないように設計すること）に正面から当たります。

## 直し方（**どちらも捨てない**）

原文6件を **`##` の節ではなく前書き**（表題と第1節のあいだ）へ下げました。
**文言は1字も変えていません。** 前書きは第1節よりさらに前に読まれるので、
**オーナーの順番は1つも落ちていません。**

## この検査が固定するもの

    1. 原文6件が `docs/trigger_parent.md` に在ること（**消させない**）
    2. それが**最初の `## ` より前**に在ること（**第1節を奪わせない**）

**1だけだと、次の回がまた `##` に上げて第1節を奪えます。
2だけだと、次の回が原文を消せます。** 片方ずつだと、この回と同じことが起きます。

**覆る条件**: オーナーが「親も喋っていい」と自分の言葉で言ったとき。
そのときは 1 を外すこと —— **2 は、それとは別の理由で残ります**
（第1節は、撃つものが書いてある節でなければならない）。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
DOC = ROOT / "docs" / "trigger_parent.md"

#: オーナー原文（**一字も変えないこと**）。`docs/trigger_parent.md` の前書きにある。
VERBATIM = [
    "親がいちいち喋んなくていいよ",
    "あんたがベラベラ喋らないでくれない？",
    "聞いてないのにベラベラ喋んないで",
    "お前が思考すんな。コスパ悪い",
    "今後一才親が思考しないで。",
    "親が思考して喋るの何回言っても直ってないから直して",
]


def _doc() -> str:
    assert DOC.is_file(), f"{DOC} がありません"
    return DOC.read_text(encoding="utf-8")


def _preamble(body: str) -> str:
    """表題から、**最初の `## ` の直前**まで。`test_parent_first_move` と同じ切り方。"""
    return re.split(r"^## ", body, flags=re.M)[0]


@pytest.mark.parametrize("line", VERBATIM)
def test_オーナー原文が消えていないこと(line: str):
    """**要約しないこと・言い換えないこと。** 4回 言われている。"""
    assert line in _doc(), (
        f"オーナー原文が `docs/trigger_parent.md` から消えています:\n"
        f"    「{line}」\n"
        "  **一字も変えないこと。** 言い換えも要約も不可。"
    )


@pytest.mark.parametrize("line", VERBATIM)
def test_原文は前書きに在ること_第1節を奪わないこと(line: str):
    """**`##` の節に上げないこと。** 上げた瞬間に第1節が「撃つもの」を失います。"""
    body = _doc()
    pre = _preamble(body)
    assert line in pre, (
        f"オーナー原文「{line}」が、**最初の `## ` より後ろ**にあります。\n"
        "  `##` の節にすると、第1節が「サブを立てる」から入れ替わり、\n"
        "  **`next_round.py` が先頭から落ちます**（2026-09-02 に実際に起きた）。\n"
        "  **前書き（表題と第1節のあいだ）へ置くこと。** そこは第1節よりさらに\n"
        "  前に読まれるので、オーナーの順番は1つも落ちません。"
    )


def test_前書きは第1節の代わりにならないこと():
    """**前書きに「撃つもの」を書き足して、第1節を空にしないこと。**

    逃げ道を1つ塞ぎます —— 原文を前書きに置いたまま、手順の中身まで
    前書きへ移してしまえば、第1節はまた空になります。
    **撃つものの出どころは第1節1か所**（`test_parent_first_move` が見ている所）。
    """
    body = _doc()
    pre = _preamble(body)
    sections = re.split(r"^## ", body, flags=re.M)
    assert len(sections) >= 2, "`## ` の節が1つもありません"
    first = sections[1]

    for token in ("next_round.py", "worktree", "spawn_prompt.rendered.md"):
        assert token in first, (
            f"第1節から `{token}` が落ちています"
            "（`tests/test_parent_first_move.py` と同じ不具合）"
        )
    # 前書きは「何をするか」を1行 指してよいが、手順そのものを持たないこと
    assert not ("worktree" in pre and "spawn_prompt.rendered.md" in pre), (
        "**前書きが第1節の代わりになっています。** 手順の中身は第1節に置くこと ——\n"
        "  前書きに移すと、`test_parent_first_move` は通るのに\n"
        "  **実際に読まれる順番はまた入れ替わります。**"
    )
