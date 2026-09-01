"""**「潰せないもの」と「偽陽性」を、持ち越しの一覧で分ける。**

## なぜ要るか（2026-09-01 08:1x に、**2件目**を踏んで足した）

持ち越しの各行は既に「**言及 N回 ／ 実物に当たった回 M回**」を出しています
（`retro.worked_on()`・2026-09-01 07:1x に足った）。
**その2つの比は、どこにも読まれていませんでした。**

N が伸びるのに M が伸びない語は、たいてい「難しくて潰せない」のではなく、
**その語を出している道具の側が間違っています**:

    premise_subject  4周とも「次の回へ」と書かれ、4周とも実物は開かれず、
                     5周目に開いたら**直す先は台帳ではなく道具の側**だった
    unwired_tools    「未決2本」が3周 運ばれ、4周目に開いたら**2本とも
                     最初から配線ずみ**だった（`.sh` と `.claude/settings.json`
                     から毎回 撃たれており、`_corpus()` がそこを読んでいなかった）

**2件とも、実物に当たった回が 1回 以下のまま3周 以上 運ばれています。**
**3件目を待たないこと。**
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

_spec = importlib.util.spec_from_file_location("retro_mod", ROOT / "scripts" / "retro.py")
retro = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(retro)


def test_線は_実測2件を_両方とも拾う():
    """**線は、拾いたい実物から決めること**（こちらで数を想像して置かないこと）。"""
    assert retro.tool_suspect(4, 0), "`premise_subject`（4周・実物 0回）を拾えていません"
    assert retro.tool_suspect(3, 1), "`unwired_tools`（3周・実物 1回）を拾えていません"


def test_よく触られている語は_拾わない():
    """**「毎周 実物を開いているのに、まだ終わらない」は、道具の欠陥ではありません。**

    そこまで印を付けると、この一覧は「全部 疑え」と言うのと同じになります。
    """
    assert not retro.tool_suspect(5, 4)
    assert not retro.tool_suspect(2, 0), "2周では早い（1回 運ばれ直しただけ）"
    assert not retro.tool_suspect(3, 2)


def test_印字に配線されている():
    """**読まれない判定は、無い判定と同じです**（この repo で通算11回の形）。

    行ごとの印だけでは 20行 の中に埋もれるので、**まとめの1か所**も要ります
    —— この一覧が5周 手で運ばれたのと同じ理由です。
    """
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    body = src[src.index("def main() -> int:"):]
    assert "tool_suspect(" in body, (
        "`main()` が `tool_suspect()` を呼んでいません。**呼ばない判定は、"
        "次の回から手で数え直されます**"
    )
    assert body.count("道具の側を先に疑うこと") >= 2, (
        "行ごとの印か、まとめの1か所かが欠けています。**両方 要ります** ——"
        "印だけだと 20行 の中に埋もれ、まとめだけだとどの行か分かりません"
    )


def test_選ぶ順を_持ち上げないこと():
    """**「疑え」は「選べ」ではありません。**

    枠や時計で塞がっている語は `_sinks()` が下へ沈めています。
    そこへ「先に見ろ」を重ねると、**この回で打てない手を勧めます**
    （2026-09-01 に `open_zero` で同じ所を踏み、直した跡があります）。
    """
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    body = src[src.index("def main() -> int:"):]
    assert "**これは「この語を選べ」ではありません**" in body, (
        "まとめの節が「選べ」と読まれないための1行が消えています"
    )


def test_線に_覆る条件が書いてある():
    """**理由と覆る条件の無い線は、次に来た側が判断できず惰性で残ります**（CLAUDE.md）。"""
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    head = src[:src.index("def tool_suspect")]
    block = head[head.rindex("#: **「潰せないもの」"):]
    assert "覆る条件" in block
    assert "premise_subject" in block and "unwired_tools" in block, (
        "線の根拠にした実測2件が書かれていません。**数だけ残ると、"
        "次の回はなぜ 3 と 1 なのかを判断できません**"
    )


# ----------------------------------------------------------------------------
# **枠で塞がっている語に、この線を当てないこと**（2026-09-01 11:5x に足した）
#
# 10:4x の回の申し送り(2) が名指ししていた1件です。この回の実測（印の付いた 4件）:
#
#     python scripts/pool_drain.py --apply   ← 同じ行に「いまは潰せません（単位枠）」
#     python -m src.pipeline                 ← 同じ行に「いまは潰せません（単位枠）」
#     [pool] [!]                             ← 塞がっていない
#     実物に当たった回 0                      ← 塞がっていない
#
# **1行の中で逆のことを言っていました。** 枠で塞がっている語の「実物に当たった回」は
# **構造的に 0** です（撃てば 403 なので撃たない）——「道具を疑え」の根拠になりません。
# ----------------------------------------------------------------------------


def test_塞がっている語には_線を当てない():
    """**M/N が読めるのは、撃てた窓だけです。**

    枠が切れている 13時間ぶんの回は、その語を撃てば 403 になるので撃ちません。
    **M が 0 なのは道具のせいではなく、窓が閉じているから**です。
    """
    assert retro.tool_suspect(6, 0), "塞がっていなければ、線は今までどおり当たります"
    assert not retro.tool_suspect(6, 0, sunk=True), (
        "枠で塞がっている語に「道具の側を先に疑え」を出しています。"
        "**同じ行の3語 上が「いまは潰せません（単位枠）」と言っています**"
    )


def test_塞がりが解けたら_線は戻る():
    """**沈めるのではなく、当てないだけ。** 窓が戻ったら、そこで初めて読める数になります。

    枠が戻ったのに触られない語は、そのとき**本当に**道具を疑う対象です。
    """
    assert retro.tool_suspect(4, 0, sunk=False)
    assert not retro.tool_suspect(5, 4, sunk=False), "よく触られている語は、戻っても拾いません"


def test_門が印字に配線されている():
    """**「選べではありません」の1行は、門ではありません**（この repo の「註と実装のずれ」）。

    この検査が在る前、`test_選ぶ順を_持ち上げないこと` は
    **印字の1行が在るかしか見ておらず**、`suspect` の一覧には
    枠で塞がった語がそのまま並んでいました（実測 4件中 2件）。
    """
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    body = src[src.index("def main() -> int:"):]
    assert body.count("sunk=_sinks(") >= 2, (
        "`main()` の2か所（行ごとの印・まとめの一覧）の両方で `sunk` を渡していません。"
        "**片方だけだと、一覧と行の印が食い違います**"
    )


def test_外した語を_黙って消していない():
    """**落としたものは必ず言うこと**（この節の末尾と同じ規則）。

    黙って削ると「そんな語は無かった」に見え、窓が戻った回が探し直します。
    """
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    body = src[src.index("def main() -> int:"):]
    assert "印を外しています" in body, (
        "塞がりで印を外した語の数と名前を印字していません"
    )


def test_sunk_に_覆る条件が書いてある():
    """**理由と覆る条件の無い門は、次に来た側が判断できず惰性で戻します**（CLAUDE.md）。"""
    src = (ROOT / "scripts" / "retro.py").read_text(encoding="utf-8")
    fn = src[src.index("def tool_suspect"):src.index("def main() -> int:")]
    assert "覆る条件" in fn
    assert "pool_drain" in fn, (
        "`sunk` の根拠にした実測が書かれていません。**数だけ残ると、"
        "次の回はなぜ外したのかを判断できません**"
    )
