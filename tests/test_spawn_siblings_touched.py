"""**兄弟が居ると書くなら、何を触ったかを見る手も渡すこと。**（2026-08-31）

## なぜ要るか —— **実測で衝突しました**

`scripts/spawn_prompt._siblings_block()` は、兄弟が居る回にこう書いていました:

    **いま同じ枝で走っています: hourly**
    **あなたの担当は、上のどれとも別のファイルのはずです。**

**確かめようがありません。** 受け取った側に渡っているのは相手の**名前だけ**で、
相手が何を触っているかを知る手が**1行も書かれていません**。規則ではなく願いです。

2026-08-31 の最適化の回が、そのとおり衝突しました:

    22:34  hourly  `d2c4cae2 fix: 説明欄の測定が、日枠で止まった回を
                    「チャンネルに無い」と印字していた`      src/descriptions.py
    22:40  こちら  `a89ab889 fix: 測れていない説明欄を「0件」と印字しない`
                                                             src/descriptions.py
    22:42  併合で3か所が衝突。両方を残すのに、さらに1手

**同じファイルの同じ欠陥を、6分 差で2人が直しています。**
見つけた欠陥は本物でしたが、**2人で見つけました。**

これは並列の税です。`scripts/eta.py` が解いている速さは `rate = p·log(g)·θ` で、
`θ` は**回転の数**。2人が同じ所を掘れば θ は2倍ではなく1倍にしかならず、
**律速そのものが半分になります。**

`d2c4cae2` は**押されていた**ので、`git log --name-only` に出ていました ——
つまり**この回の衝突は、数秒の1手で防げていました。**

## 覆る条件

**押す前の作業は、この窓に出ません**（こちらの `a89ab889` も、撃った時点では
相手に見えていない）。そこを詰めるなら、次は「取ったファイルを先に宣言する」形。
ただしそれには**押す前に見える置き場**が要り、この枝には在りません。
置き場ができたら、この検査ごと書き換えること。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import spawn_prompt as sp

ROOT = Path(__file__).resolve().parent.parent


def test_兄弟が居る回は_触った所を見る手が入る():
    out = sp._siblings_block(["016bZbYd"])
    assert "git log origin/" in out and "--name-only" in out, (
        "**名前だけ渡して『別のファイルのはずです』と書くのをやめました。**\n"
        "相手の作業は git に在ります。**主張ではなく手を渡すこと。**\n" + out)
    assert "取られていると読むこと" in out


def test_願いの1行は_もう出さない():
    out = sp._siblings_block(["016bZbYd"])
    assert "別のファイルのはずです。" not in out.replace(
        "「別のファイルのはずです」", ""), (
        "確かめる手を渡さずに『はずです』と書くと、規則ではなく願いになります。\n" + out)


def test_兄弟が居ない回は_この手を出さない():
    """居ない回に出すと、**毎回 撃つ手**が1つ増えるだけです。"""
    out = sp._siblings_block([])
    assert "--name-only" not in out
    assert "立てた時点ではいません" in out


def test_枝の名前を写さない():
    """`docs/trigger_spec.json` が正本。写すと、枝を変えた回に黙って古くなります。"""
    src = (ROOT / "scripts" / "spawn_prompt.py").read_text(encoding="utf-8")
    branch = json.loads(
        (ROOT / "docs" / "trigger_spec.json").read_text(encoding="utf-8"))["branch"]
    assert branch and branch not in src, (
        f"`{branch}` が `spawn_prompt.py` に写されています。"
        "`<<branch>>` を出して、`build()` の末尾に当てさせること")


def test_組み上げた本文で_枝名が実体に置き換わる():
    """`<<branch>>` が本文に**そのまま残らない**こと（2026-08-25/26 に2回 踏んだ穴）。"""
    text = sp.build("hourly", siblings=["016bZbYd"])
    assert "<<branch>>" not in text, "差し込み口が本文に生で残っています"
    branch = json.loads(
        (ROOT / "docs" / "trigger_spec.json").read_text(encoding="utf-8"))["branch"]
    assert f"git log origin/{branch}" in text, text[:400]


@pytest.mark.parametrize("kind", ["hourly"])
def test_兄弟の段は_どの種別でも本文に入る(kind):
    text = sp.build(kind, siblings=["016bZbYd"])
    assert "いま同じ枝で走っています" in text
