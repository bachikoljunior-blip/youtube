"""**「どこからも撃たれていない道具」の一覧を、手で運ばせない。**

## なぜ要るか（2026-09-01）

この一覧は **5周 続けて申し送りに運ばれていました** ——
「`retro.py` の『どこからも呼ばれない』は残り N本」。
**ところが `retro.py` にそんな一覧はありませんでした**
（`grep -n 呼ばれない scripts/retro.py` → 0件）。
毎回、来た側が手で数え直していたということです。

そして**手で運ぶうちに、中身がずれていました。** 最後に運ばれた値は「残り **2本**」で、
実物は **4本** —— 2本は**一度も申し送りに出ていません。**
**運ばれなかったものは、存在しないことになります。**

だから `scripts/retro.py` に `unwired_tools()` を置き、毎周 印字させました。
**この検査は、その配線が外れたら赤になります。**

## **この検査自身が、一度この一覧を壊しています**

道具は最初 `\\b<名前>\\b` の**素の言及**で「撃たれている」を数えていました。
**この検査が道具の名前を散文で書いた瞬間に、一覧は 4本 → 0本 になりました**
（同じ形で `retro.py` 自身の docstring でも踏んでいます。**2回**）。
いまは**呼び方の形**（`scripts/<名前>.py` か import）にしか当たらないので、
**この検査が名前を何度書いても一覧は動きません。**
下の `test_散文で名前を書いても_一覧は動かない` がそれを固定しています。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("retro_mod", ROOT / "scripts" / "retro.py")
retro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retro)


def test_一覧は道具から出る():
    rows = retro.unwired_tools()
    assert isinstance(rows, list)
    for r in rows:
        assert set(r) == {"name", "path", "dormant_says"}
        assert (ROOT / r["path"]).exists()
        assert r["path"].startswith("scripts/")


def test_毎周の印字に配線されている():
    """**道具が在るだけでは足りません。** この一覧が5周 手で運ばれた理由がそれです
    —— 計器はどこにも無く、印字もされていませんでした。"""
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    body = src[src.index("def main() -> int:"):]
    assert "unwired_tools()" in body, (
        "`main()` が `unwired_tools()` を呼んでいません。"
        "**呼ばない一覧は、次の回から手で運ばれます**（5周 そうなっていました）。"
    )
    assert "どこからも撃たれていない道具" in body


def test_散文で名前を書いても_一覧は動かない():
    """**一覧に載せる行為が、載せたものを消していた**（2026-09-01 に2回 踏んだ）。

    この検査は、下の名前を**散文で**書きます。素の言及で数えていた頃は、
    これだけで4本とも「配線ずみ」に化けました。**いまは化けません。**

    **覆る条件**: ここに挙げた道具が本当に配線されたら（`scripts/<名前>.py` を
    誰かが撃つ、または import する）、その名前はこの assert から外すこと。
    **全部 外れたらこの検査ごと消してよい** —— 一覧が空になったということです。
    """
    rows = {r["name"] for r in retro.unwired_tools()}
    # ↓ この4つは「名前を書いただけ」。呼んでいません。
    assert "deixis_count" in rows
    assert "token_probe" in rows
    assert "statusline_usage" in rows
    assert "verdict_followup" in rows


def test_わざと寝かせてある側が_三択から落ちない():
    """**(a) 配線する ／ (b) 消す の二択では、(c) が落ちます。**

    申し送りが5周 繰り返し頼んでいたのはここです ——
    `deixis_count` は自分の docstring に「だから検査は足していません」と書き、
    覆る条件まで置いてあります。**判定はしません。その一行を見せるだけです。**

    **覆る条件**: `deixis_count` を配線するか消すかしたら、この検査は
    「(c) の付いた行が1件も無い」で落ちます。そのときは、
    **別の (c) が在るならそちらへ差し替え、無ければこの検査ごと消すこと。**
    """
    marked = [r for r in retro.unwired_tools() if r["dormant_says"]]
    assert marked, (
        "(c)「わざと寝かせてある」の目印が1件も拾えていません。"
        "`DORMANT_MARKS` の語が、道具の docstring の実物と食い違っていないか"
        "（**こちらで言い回しを想像して足すと、当たらないまま増えます**）"
    )
