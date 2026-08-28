"""**`print_long_stock()` の (1) に、候補の一覧を出す**（2026-08-29 に足した）。

## なぜ要るか（実測）

`print_long_stock()` は族を増やす道を2つ並べます。

    (1) `src/calc/` に**新しい表**を書く（実測 20〜25分）
    (2) **既にある表**に節を足して `--count N --long`（実測 15分）
      **(2) で選べる族: 64件** aoiro fudosanshutoku fuka …

**(2) にだけ候補の一覧が付いています。** (1) は「新しい表を書く」としか言いません。
**候補が並んでいるほうが選ばれます** —— 実測で、この節を読んで (1) を選んだ回は
**3回とも題材を自分でゼロから考えています**（08/26 01:5x・02:3x・08/29 04:0x）。

ところが候補は `config/topics.yaml` に**ずっと在りました** —— `calc` が空のまま
残っている長尺のテーマで、`angle` には表の設計そのものが書いてあります
（「排気量の帯 × 経過年数の表」「一部支給の逓減 ＝ 実質の限界税率」）。

**その7件は、これまで「死に在庫」と呼ばれていました** ——
`pick()` は `calc` を要求するので永久に選ばれず、
`topics.yaml` を手で数えた回が「長尺の在庫が7件ある」と読み違えます
（`docs/JOURNAL.md` 2026-08-29 02:2x で実際に踏んだ）。
申し送りは2回続けて「`calc` を当てるか、行ごと消すか」と言っていましたが、
**どちらも中身を捨てます。** 出せば、読み違えは消えて中身は候補として残ります。

## ここで留めているもの

1. **`calc` が空・未投稿・`s-` で始まらない題が、(1) の候補として出る**
2. **「在庫ではありません」と、その場で言う**（読み違えの再発を、文で止める）
3. **在庫の数（`長尺向けのテーマ N件`）には数えない** —— 数えたら元の読み違えです
"""
from __future__ import annotations

import importlib.util
import io
import contextlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "topic_forge", ROOT / "scripts" / "topic_forge.py")
forge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(forge)


def _out(monkeypatch, topics, ledger) -> str:
    from src import config, dupes
    monkeypatch.setattr(config, "load_topics", lambda: {"topics": topics})
    monkeypatch.setattr(dupes, "ledger_rows", lambda: ledger)
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        forge.print_long_stock()
    return buf.getvalue()


def test_calcが空の長尺の題が1の候補として出る(monkeypatch):
    topics = [
        {"id": "with-calc", "calc": "zoyo", "title_seed": "在庫のほう"},
        {"id": "kuruma-zei-juka", "title_seed": "13年目の自動車税は、いくら上がるか"},
        {"id": "s-short-idea", "title_seed": "ショートなので候補ではない"},
    ]
    text = _out(monkeypatch, topics, [])

    assert "**(1) の候補: 1件**" in text
    assert "kuruma-zei-juka" in text
    assert "13年目の自動車税は、いくら上がるか" in text
    assert "**在庫ではありません**" in text, "読み違えを、その場の文で止めること"
    assert "s-short-idea" not in text, "ショートは長尺の候補ではない"


def test_候補は在庫の数に入れない(monkeypatch):
    """**入れたら、元の読み違えそのものです。**

    `pick()` は `calc` を要求するので、候補は1本も作れません。
    在庫に足すと「20件あるのに8本しか取れない」の分子が嘘になります。
    """
    topics = [
        {"id": "a", "calc": "zoyo", "title_seed": "x"},
        {"id": "b", "calc": "zoyo", "title_seed": "y"},
        {"id": "idea-1", "title_seed": "候補1"},
        {"id": "idea-2", "title_seed": "候補2"},
    ]
    text = _out(monkeypatch, topics, [])

    assert "長尺向けのテーマ **2件**" in text, "候補を在庫に数えないこと"
    assert "**(1) の候補: 2件**" in text


def test_投稿済みの題は候補に出さない(monkeypatch):
    """出したものは、もう題材ではありません。"""
    topics = [
        {"id": "a", "calc": "zoyo", "title_seed": "x"},
        {"id": "done-idea", "title_seed": "もう出した"},
    ]
    text = _out(monkeypatch, topics, [{"topic": "done-idea"}])
    assert "done-idea" not in text
    assert "(1) の候補" not in text, "候補が0件なら、その行ごと出さないこと"


def test_実物の帳面でも候補の行が出る():
    """**合成ではなく、この機械が実際に持っている `topics.yaml` で1回 通すこと。**

    見るのは件数ではなく、**行が出ること**です（件数は回ごとに動きます）。
    候補が0件になったら、この検査は「行が無い」ほうを通します
    —— そのときは `print_long_stock` の側も黙るのが正しい。
    """
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        forge.print_long_stock()
    text = buf.getvalue()
    assert "長尺向けのテーマ" in text
    if "(1) の候補" in text:
        assert "**在庫ではありません**" in text
