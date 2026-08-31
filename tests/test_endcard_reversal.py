"""**「1件でも付いたら覆る」に戻らないための検査**（2026-08-31）。

## なぜ要るか（実測。推測ではありません）

`config/hypotheses.yaml` の前提「ショートの最後を『答えやすい問いかけ』で終えると、
共有とコメントが付く」は 2026-08-20 に **falsified** で閉じました。そのとき
覆る条件をこう書いていました:

    **チャンネル全体のコメントが、28日窓で1件でも視聴者から付いたとき**
    いまは 20,332再生で 0件なので、**1件出た時点でこの枠に信号があることになり、
    率を測り直す値打ちが出ます。**

**2026-08-31 に、そのとおり発火しました** —— `scripts/endcard_check.py` の実測で
問いかけ型 **56,751再生／コメント 1件**（チャンネル全体 76,316再生／1件）。
**チャンネル初の、視聴者からのコメント**です。

**それでも覆りません。** 1/56,751 = **0.0018%** ＝ 判定文が置いた目安 0.2% の
**1/114**。**条件のほうが壊れていました** —— 「1件でも」は分母が伸びれば
必ず満たされるので、**効果ではなく時間の経過で発火します。**

この検査が固定するのは、その直しです。**赤くなったら、
「率ではなく件数で覆る」形に戻ったということ。**

## この検査が覆る条件

`BENCHMARK_RATE`（目安 0.2%）が実測で覆ったら、ここの数も一緒に直すこと。
`REVERSAL_RATE` は目安の 1/4 という関係で書いてあるので、
**目安だけを直せばここは自動で追います**（下の `test_門は目安の四分の一` が見ます）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from src import endcard_verdict as ev

ROOT = Path(__file__).resolve().parent.parent


def test_2026_08_31_の実測では覆らない():
    """**この検査の中心。** 実測 56,751再生／1件 は、覆る側に落ちてはならない。"""
    r = ev.reversal(56751, 1)
    assert r["reversed"] is False
    assert r["comments"] == 1
    # 率が目安の 1/100 より下であることまで固定する（1/114）。
    assert r["rate"] < ev.BENCHMARK_RATE / 100


def test_件数だけでは覆らない():
    """**分母が伸びれば件数は増えます。** 件数だけで開け直させないこと。"""
    # 100件でも、1,000万再生なら率は 0.001% —— 目安の 1/200。
    assert ev.reversal(10_000_000, 100)["reversed"] is False


def test_率だけでも覆らない():
    """窓が小さいときの跳ね（1/1000 = 0.1%）で開け直させないこと。"""
    r = ev.reversal(1000, 1)
    assert r["rate"] > ev.REVERSAL_RATE      # 率の門は超えている
    assert r["reversed"] is False            # それでも覆らない（件数の床）


def test_率と件数がそろえば覆る():
    """**開け直す口を塞いだのではありません。** 本物の信号なら覆ること。"""
    assert ev.reversal(10_000, 5)["reversed"] is True      # ちょうど 0.05%・5件
    assert ev.reversal(56_751, 30)["reversed"] is True     # 0.053%・30件


def test_ゼロ除算で落ちない():
    """まだ1再生も無い窓（新しいチャンネル・データの遅れ）で落ちないこと。"""
    r = ev.reversal(0, 0)
    assert r["reversed"] is False
    assert r["rate"] == 0.0


def test_門は目安の四分の一():
    """**2つの数を別々に動かさないこと。** 関係のほうを固定する。"""
    assert ev.REVERSAL_RATE == pytest.approx(ev.BENCHMARK_RATE / 4)
    assert ev.BENCHMARK_RATE == pytest.approx(0.002)   # 判定文の「0.2%」


def test_判定文に写しではなく正本の名前が在る():
    """`config/hypotheses.yaml` の側が、**関数を名指ししている**こと。

    写しだけを置くと、片方が黙って古びます（この repo の一番よくある壊れ方）。
    """
    text = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    assert "src/endcard_verdict.reversal()" in text
    # **「1件でも付いたとき」を、いまの条件として書き戻していないこと。**
    # （履歴として「前はこう書いてあった」と引用するのは可。だから
    #   「これが覆る条件」の見出しの直後に来ていないことだけを見る）
    head = text.split("## **これが覆る条件**", 1)[1][:400]
    assert "1件でも" not in head
