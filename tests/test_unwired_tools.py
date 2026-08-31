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
        assert set(r) == {"name", "path", "dormant_says", "decided"}
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


def test_倒した回の跡が_次の回にも見える():
    """**倒しても一覧が縮まないなら、次の回は同じ三択をやり直します。**

    実測 2026-09-01 06:0x —— `token_probe` は 06:01 に (c) へ倒され
    （`--closes token_probe` つきで ship 済み）、その **4分後**の `retro.py` の
    出力で、**まだ決まっていない3本と同じ字**で並んでいました。
    `deixis_count` が **6周** 持ち越したのは、これが理由です ——
    01:3x の回が「(c) かもしれない」と書いてから5周、誰も**決めた形**を
    残せませんでした（残す先が無かった）。

    **`dormant_says` は「その道具が寝ている理由を書いている」だけ**で、
    **誰かが決めたかどうかを1文字も言っていません。** 分けるのが `decided` です。

    **覆る条件**: この2本を (a) 配線する／(b) 消す に倒したら、この検査は
    「決まった行が無い」で落ちます。そのときは別の (c) へ差し替えるか、
    **`decided` を持つ道具が1本も無くなったなら、この検査ごと消すこと。**
    """
    by = {r["name"]: r for r in retro.unwired_tools()}
    decided = [n for n, r in by.items() if r["decided"]]
    assert decided, (
        "(c) に**倒しずみ**の道具が1件も拾えていません。"
        "倒す側が書く1行は `## **(c) わざと寝かせてある —— <なぜ>**（<日付> に決めた）`。"
        "**書式を変えたなら `_DECIDED_RE` も直すこと**"
    )
    for name in ("deixis_count", "token_probe"):
        assert by[name]["decided"], (
            f"`{name}` は (c) に倒してあります（docstring に見出しで残っています）。"
            "それがここに出ないなら、`_DECIDED_RE` が実物と食い違っています"
        )


def test_散文で_わざと寝かせてある_と書いても_倒したことにならない():
    """**「そう書いてある」と「決めた」を、同じ字で数えないこと。**

    `DORMANT_MARKS` は素の語（「わざと」「寝かせ」…）に当たるので、
    **理由を説明しただけの行**でも拾います。それは正しい —— あちらは
    「この道具はこう言っています」を見せるためのものです。
    **`decided` のほうを同じ緩さで拾うと、寝ている理由を書いた道具が
    全部「決まった」に化け、一覧は二度と縮みません**（縮まない一覧は、
    5周 手で運ばれたあの一覧と同じものになります）。

    だから当てるのは**見出しの形**だけです。
    """
    assert not retro._DECIDED_RE.search(
        "この道具は (c) わざと寝かせてある、と散文で書いてあるだけです")
    assert not retro._DECIDED_RE.search("わざと寝かせてあります")
    assert retro._DECIDED_RE.search(
        "## **(c) わざと寝かせてある —— なぜか**（2026-09-01 に決めた）")


def test_未決と倒しずみを_分けて印字する():
    """**印字に出ないものは、次の回には無いのと同じです**（この一覧が5周 手で
    運ばれた理由がそれ）。`unwired_tools()` が `decided` を返しても、
    `main()` が同じ行に並べたままなら、読む側からは何も変わりません。
    """
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    body = src[src.index("def main() -> int:"):]
    assert 'r["decided"]' in body, (
        "`main()` が `decided` を読んでいません。**読まない状態は、無い状態と同じです**"
    )
    assert "倒しずみ" in body and "未決" in body


def test_遅くしないこと():
    """**遅い検査は、次の回から走らなくなります。**

    2026-09-01、この検査は最初 **44秒**（4件）かかりました。
    その間に、同じ枝のきょうだいが
    `--deselect tests/test_unwired_tools.py` / `--ignore=...` を付けて
    **全体 `pytest` から外しはじめています**（`ps` で実測。2つの回）。
    **外された検査は、赤くなっても誰も見ません。**

    原因は「道具ごとに全文へ正規表現を当てる」形で、**60本 × 10MB ＝ 9.7秒**。
    呼び方の形（`scripts/<名前>.py` や import）は道具の名前を含まないので、
    **1回なめて名前を集めれば足ります** → **0.64秒**。

    **覆る条件**: 機械が混んでいる回では素で遅くなります（この repo は
    同じ枝で複数の回が同時に `pytest` を回します）。**上げてよい。**
    ただし **10秒 に近づいたら、それは1本ずつ全文へ当てに戻ったということ**です ——
    上げる前に `_CALL_RE` の1回なめが残っているかを見ること。
    """
    import time

    retro._corpus.cache_clear()
    t0 = time.time()
    retro.unwired_tools()
    took = time.time() - t0
    assert took < 5.0, (
        f"`unwired_tools()` に {took:.1f}秒 かかっています（素は 0.6秒）。"
        "**道具ごとに全文へ当てる形へ戻っていないか**（`_CALL_RE` の1回なめ）。"
        "混んでいるだけなら、この線は上げてよい"
    )
