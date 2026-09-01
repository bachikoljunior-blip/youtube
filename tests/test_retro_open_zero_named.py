"""**「この N件 から選ぶのが既定です」の N件 に、名前を出す。**

## なぜ要るか（2026-09-01 10:3x に踏んだ。**判定は正しく、印字だけが逆を指していた**）

持ち越しのまとめは、最後に「実物に当たった回が 0 の語」から
**この回で打てるものだけ**を既定として勧めます（`open_zero`）。
枠や時計で塞がっている語は `_sinks()` が除いてあり、**その除き方は正しい**。

**ところが、そこは件数しか印字していませんでした。** 実測（この回の `retro.py` の出力）:

    **そのうち 2件 は、3周 以上 運ばれて、実物に当たったのが 1回 以下 です**
        python scripts/pool_drain.py --apply     ← 枠で塞がっている（403）
        [pool] [!]                               ← 枠で塞がっている（403）
    …
    **そのうち 5件 は、実物に当たった回が 0 です**
    …
    **この 2件 から選ぶのが既定です。**          ← 中身は `waived` ／ `--claim`

**直前に名前が並んでいるのは `suspect` のほう**、つまり
`_sinks()` が**除いたはずの側**です。しかも件数まで **2件 対 2件** で一致します。
読む側から見ると「この2件」の指す先は、直前に名前の出ている2件しかありません ——
**同じ出力の6行 上が「この回で選ぶのは、その上にあるものから」と言っている、
まさにその 403 の2件**です。

**`_sinks()` の註（「そこへ『0回 だから先に選べ』を重ねると、この回で打てない手を
勧めます」）は正しく、選び方も正しく、印字だけが逆を指していました。**
`suspect` の側は同じ節で名前を並べています。**片方だけ並べたのが誤りです。**

**覆る条件**: `suspect` の並びをこの下へ動かしたら、直前の名前は別物になります。
そのときも名前は出すこと —— 順で守るのは「たまたま当たっている」だけです。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("retro_mod", ROOT / "scripts" / "retro.py")
retro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retro)


def _main_body() -> str:
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    return src[src.index("def main() -> int:"):]


def test_open_zero_の中身を印字している():
    """**件数だけでは、指す先が直前の一覧に化けます。**"""
    body = _main_body()
    head = body.index("open_zero = [")
    tail = body.index("この回で1件は潰すこと", head)
    block = body[head:tail]
    assert "for t in open_zero:" in block, (
        "`open_zero` の中身を印字していません。**件数だけを出すと、"
        "直前に名前の並んでいる `suspect`（＝ `_sinks()` が除いた側）を指して読まれます** ——"
        "2026-09-01 の実測では件数まで 2件 対 2件 で一致していました"
    )


def test_suspect_と_open_zero_は別の集合である():
    """**この2つは、意図して逆向きです。**

    `suspect`   = 何周も運ばれて実物に当たっていない → **開くならここから**
    `open_zero` = 実物に当たっておらず、**かつ この回で打てる** → **選ぶならここから**

    枠が塞がっている窓では、前者が後者を1件も含まないことがあります
    （実測 2026-09-01: `suspect` 2件 は両方 403 で、`open_zero` には 1件も入らない）。
    **同じ節に、片方だけ名前を出さないこと。**
    """
    carried = {
        "pool_drain --apply": ["09-01 06:2x", "09-01 07:0x", "09-01 08:1x"],
        "waived": ["09-01 03:5x", "09-01 09:4x"],
    }
    touched = {"pool_drain --apply": 0, "waived": 0}
    blocked = {"pool_drain --apply"}          # この窓では 403

    def sinks(t: str) -> bool:
        return t in blocked

    suspect = [t for t, ds in carried.items()
               if retro.tool_suspect(len(ds), touched[t])]
    zero = [t for t in carried if touched[t] == 0]
    open_zero = [t for t in zero if not sinks(t)]

    assert suspect == ["pool_drain --apply"]
    assert open_zero == ["waived"]
    assert not (set(suspect) & set(open_zero)), (
        "この窓では、疑う先と選ぶ先が1件も重なりません。**それでも件数は"
        "どちらも 1件 です** —— 名前を出さないと見分けられません"
    )


def test_名前を出す側が_両方そろっている():
    """**片方だけ名前を出すのが、この欠陥の形そのものです。**"""
    body = _main_body()
    assert "for t in suspect:" in body, "`suspect` の名前が印字されていません"
    assert "for t in open_zero:" in body, "`open_zero` の名前が印字されていません"
