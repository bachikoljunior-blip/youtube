# -*- coding: utf-8 -*-
"""`OUTSIDE_LONG_RULE` (4e) —— **サムネの1行の長さ**（2026-09-04 20:0x に足した）。

## なぜ足したか（**外の上位の絵を目で読んだ数**・API 0単位）

    J6i7L0QSRSQ  5,095,519回  「年金の繰り上げ」7 ／「60歳からが」6 ／「超絶お得です」6   → 最大 **7**
    D9BI69GFWvs  4,415,973回  「9月中に必ず確認して！」11 ／「申請をしないと」7 ／「234万円失う！」8 → 最大 **11**
    mL0bwzi8KFM  3,254,713回  「R8年4月から」7 ／「年金に」3 ／「7万円 一生上乗せ」9      → 最大 **9**

こちらの実物（09/05 の1本 `e6sLHLmPhrk`）の `thumbnail_kicker` は **17文字** ＝ 外の最大の 1.5倍。
しかも3つの中で**いちばん小さい字**で刷られます（`src/thumbnail.py` の黄色い箱）——
**前提を運んでいる行が、いちばん読めない行**でした。
`thumbnail_line1`（8）と `thumbnail_line2`（9）は外の帯の中に在ります。

(4a)〜(4d) は `thumbnail_line1` / `line2` の**中身**（金額・判断の語）だけを数えていて、
**長さと、黄色い箱そのものは、どの脚も見ていませんでした。**

**n=3 です。強い証拠ではありません** —— 上限は「外の最大」に置いてあるので、
落ちるのは**外のどの本よりも長い行**だけです。

**短くするために前提を落とさないこと**（`CLAUDE.md`「制度や金額には必ず適用条件を添える」）。
`src/thumbnail._create_outside` はこの行を**1行で**刷る（折り返さない・`_fit_font` が
字を縮めるだけ）ので、逃げ道は「書き方を詰める」か「条件を `thumbnail_line1` へ移す」の2つ。
実物で確かめた例:「75歳まで生きた場合・年180万円」17 →「年180万・75歳まで」11 ＝
**年額と存命年齢の2つとも残ります。上限は満たせない数ではありません。**
"""
from __future__ import annotations

from src import script_writer as sw


def _script(**over) -> dict:
    d = {
        "title": "【60歳以上の方へ】75歳までなら総額2052万円差 何歳から受け取るか",
        "thumbnail_line1": "差は2052万円",
        "thumbnail_line2": "何歳から受け取るか",
        "thumbnail_kicker": "年180万・75歳まで",
    }
    d.update(over)
    return d


def test_外の帯の中の長さは通る():
    """外の最大（11文字）以内なら、この脚は何も言わないこと。"""
    got = sw.outside_title_problems(_script())
    assert not [p for p in got if "文字以内" in p], got


def test_黄色い箱が長いと落ちる():
    """**`thumbnail_kicker` も数えること** —— ここが (4a)〜(4d) の見ていなかった所。"""
    got = sw.outside_title_problems(_script(thumbnail_kicker="75歳まで生きた場合・年180万円"))
    hit = [p for p in got if "thumbnail_kicker" in p]
    assert hit, got
    assert "17文字" in hit[0], hit


def test_上限は外の上位の最大に置いてある():
    """**数を勝手に下げないこと。** 下げると、外の帯の中の本まで落ちます。

    上げるときは `data/niche_thumbs/<id>.jpg` を**目で読み直して**から
    （`OUTSIDE_THUMB_LINE_MAX` の註。題の文字数ではありません）。
    """
    assert sw.OUTSIDE_THUMB_LINE_MAX == 11


def test_規則の本文にこの脚が書いてある():
    """**本文と数える口をずらさないこと**（`tests/test_outside_rule_legs.py` と対）。"""
    assert "どの行も全角11文字以内" in sw.OUTSIDE_LONG_RULE
    assert "thumbnail_kicker" in sw.OUTSIDE_LONG_RULE


def test_上限は満たせる数である():
    """**満たせない上限を置かないこと。** この本の前提は 11文字 に収まります。

    「75歳まで生きた場合・年180万円」(17) → 「年180万・75歳まで」(11) ＝
    **年額（180万）と存命年齢（75歳まで）の2つとも残ります。**
    落ちたのは「生きた場合」「円」という、無くても意味の変わらない字だけ。
    """
    kicker = "年180万・75歳まで"
    assert len(kicker) == sw.OUTSIDE_THUMB_LINE_MAX
    assert "180万" in kicker and "75歳" in kicker
    assert not [p for p in sw.outside_title_problems(_script(thumbnail_kicker=kicker))
                if "文字以内" in p]
