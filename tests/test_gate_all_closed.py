"""**門を閉じ切った日に、`scripts/eta.py` が落ちないか。**（2026-08-30 夜に踏んだ）

## 1. 残り 0件 の日に `--gate` が `TypeError` で落ちていた

`resume_gate.days_to_close()` は **自分の docstring でこう言っています** ——
「**残りが 0件 なら、速さが測れていなくても 0日**（閉じるものがない）」。
だから `left_days` は `0.0` で返り、`eta.gate_lines()` は
`left_days is None` ではない側の枝へ入ります。**その枝は
`days_per_close()` を `:.1f` で組み立てます** ——ところが同じ日に
まとめて閉じた回は窓が `MIN_SPAN_DAYS` に満たず、そちらは `None` です。

    TypeError: unsupported format string passed to NoneType.__format__

**落ちるのが `scripts/eta.py` なのが、いちばん高い代金です。**
`CLAUDE.md`「毎回の実行で必ずやること」の1番がこれなので、
**門を閉じ切った次の回から、毎周いちばん最初に落ちます。**
そして**門を閉じるほど壊れる形**なので、最後の1件を閉じるまで誰も踏めません。

## 2. `## Resume gate` の節に番号を書いたら、門が 6件 → 9件 に増えた

`conditions()` は `## Resume gate` から次の `##` までの**番号つきの行を
全部 条件として数えます**。字下げしたコードブロックの中も同じでした。
「解除したら、最初の1周でやること」を `1. 2. 3.` で書いた回があり、
`--gate` は **9/9** と印字しました。

**黙って増えるだけではありません。** `state()` は番号で台帳と突き合わせるので、
**足された 1〜3 は本物の 1〜3 の判定をそのまま貰って「閉じた」になります** ——
**増えたことも、閉じたことも、出力からは見えません。**

## 覆る条件

条件そのものを字下げして書く形に `docs/RESUME_GATE.md` が変わったら、
`conditions()` の字下げの門ごと直すこと。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import resume_gate  # noqa: E402

DOC = """\
## Resume gate

次の全条件が記録されるまで解除しない。

1. 一つめ
2. ふたつめ
3. みっつめ

**解除したら、最初の1周でやること**:

    1. これは条件ではない（字下げしたコードブロック）
    2. これも条件ではない
    3. これも条件ではない

## 次の見出し
"""


# --- 1. 番号の拾い方 -------------------------------------------------------

def test_字下げした番号は条件に数えない():
    got = resume_gate.conditions(DOC)
    assert [n for n, _ in got] == [1, 2, 3]
    assert [b for _, b in got] == ["一つめ", "ふたつめ", "みっつめ"]


def test_正本の門はいまも6件():
    """**この数が動いたら、まず `docs/RESUME_GATE.md` の書き足しを疑うこと。**"""
    assert len(resume_gate.conditions()) == 6


# --- 2. 残り 0件 の日 ------------------------------------------------------

def test_残りが0件なら日数は0で返る():
    """`None`（測れない）ではなく `0.0`。**閉じるものが無いので 0日**。"""
    doc = "## Resume gate\n\n1. 一つめ  **← 2026-08-30 に閉じた**\n"
    assert resume_gate.days_to_close(doc, path=Path("/nonexistent.jsonl")) == 0.0


def test_残りが0件でも門の行が組み立つ():
    """**ここが 2026-08-30 夜に `TypeError` で落ちていた所です。**

    `days_to_close()` は `0.0`、`days_per_close()` は `None` ——
    その組み合わせで印字できることを見ます。
    """
    import importlib

    eta = importlib.import_module("eta")
    lines = eta.gate_lines("###")
    assert lines
    body = "\n".join(lines)
    assert "残り 0件" in body or "開いている" in body


def test_門が全部閉じたときは_止めるのは人だと印字する():
    """**閉じた ≠ 解除** …… でしたが、2026-08-31 に前提が変わりました。

    ここには `assert "解除はまだ別の1手" in body` と書いてありました。
    **「停止は人の手で入っているので、機械はまだ解除できない」**という意味で、
    書いた時点では正しかった。**いまは逆を言わせる形になっています** ——
    オーナーが 08-31 に停止を解き、原文で
    **「勝手にそれで止まるのなし。今後そういうことがないようにして」**と言いました。
    この検査を残すと、**機械は毎周「まだ解除されていません」と印字し続けます。**

    だから見るものを入れ替えます —— **止める側が人であること**。
    `.owner-pause` と `pause_guard` が名指しされていれば、次に読んだ側は
    「自分で止められる」と読み違えません。

    **覆る条件**: 印字の文言を変えるのは自由。**「機械が自分で止める／
    止まったままにする」を意味する文言に戻したら、そこが間違い**です
    （`tests/test_pause_needs_owner.py`）。
    """
    import importlib

    eta = importlib.import_module("eta")
    body = "\n".join(eta.gate_lines("###"))
    if len(resume_gate.open_items()) == 0:
        assert "解除はまだ別の1手" not in body, (
            "門が閉じているのに「まだ解除されていない」と印字しています —— "
            "停止は 2026-08-31 にオーナーが解いています")
        assert ".owner-pause" in body and "pause_guard" in body, (
            "止めるのが誰か（人の手で置く `.owner-pause`）が名指しされていない")


def test_日ごとの速さが測れなくても落ちない():
    """同じ日にまとめて閉じた回は `days_per_close()` が `None` になります。

    **残りが 1件 以上あって、かつ速さが測れない**組み合わせでも、
    `:.1f` に `None` を渡さないこと。
    """
    import importlib

    eta = importlib.import_module("eta")
    assert eta.gate_lines("###")          # 落ちなければよい
    assert resume_gate.days_per_close(
        "## Resume gate\n\n1. 一つめ\n2. ふたつめ  **← 2026-08-30 に閉じた**\n",
        path=Path("/nonexistent.jsonl"), today=date(2026, 8, 30)) is None
