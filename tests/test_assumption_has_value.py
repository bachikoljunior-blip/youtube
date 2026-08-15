"""**「これは仮定です」と名乗った量に、値が書いてあること**（`_checks.assumption_values`）。

## なぜ要るか —— **申し送りを8回運んでも閉じなかった穴**

2026-08-16 01:3x に `verify._check_assumption_value_shown` が入りました。
独立評価の3体が2本続けて「手取り率が何パーセントなのか最後まで画面に出ない」と
書いたのを受けて、**画面に前提の値が出ているか**を見る検査です。

**それでも閉じませんでした。** 同じ申し送りが、この文のまま8回運ばれています ——

> `ASSUMPTIONS` そのものに値が無い calc がある（`nenkin` の手取り率）。
> 画面に出せと言われても、**calc 側が値を持っていない**ものは書きようがありません。

実物はこうでした。**率が何%なのかが、どこにも書いていない。**

    "手取り率は制度の値ではなく、この計算での仮定です。額が上がるほど下がるものとして置いています"

モジュールの中の `NET_RATE_POINTS` は実際の値を持っていて、計算にも使っています。
**値は在るのに、前提の文が持っていない。** 台本の書き手に渡るのは
`ASSUMPTIONS` の文だけなので（`src/script_writer.py`）、書き手にできるのは
**黙って落とす**（→ `verify` が1本まるごと捨てる）か
**自分で数字を作る**（→ 裏の取れない数字が動画に入る）かの2つだけです。

**片側にしか検査が無かったので、8回運ばれても閉じませんでした。**

## この検査が固定するもの

1. **`src/calc/` の全部**が、いま通ること（**新しい calc も勝手にここに乗る**）
2. **直す前の実物4行**が、ちゃんと落ちること（故障注入）
3. **偽陽性の形**が通ること —— 量の名前を出しただけの行、
   前提を名乗った文と量の出てくる文が別の行
4. **語彙が1か所しか無いこと** —— `verify` が `_checks` から輸入していること
"""
from __future__ import annotations

import importlib
import pkgutil
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calc import _checks  # noqa: E402
from src.calc._checks import TableError, assumption_values  # noqa: E402


def _calc_names() -> list[str]:
    import src.calc as calc_pkg
    return sorted(m.name for m in pkgutil.iter_modules(calc_pkg.__path__)
                  if not m.name.startswith("_"))


# ------------------------------------------------ 1. 実物が全部通ること

@pytest.mark.parametrize("name", _calc_names())
def test_every_calc_passes(name):
    """**`src/calc/` に足した本は、黙ってここに乗ります。**

    一覧を手で持たないのは、**足し忘れに気づけないから**です
    （`SUBJECT_WORDS` は通算4回、足し忘れで素通りしました）。
    """
    module = importlib.import_module(f"src.calc.{name}")
    assumptions = getattr(module, "ASSUMPTIONS", None)
    assert assumptions is not None, (
        f"src/calc/{name}.py に ASSUMPTIONS がありません"
        "（`src/calc/__init__.py` が必須だと書いています）")
    if isinstance(assumptions, str):
        assumptions = [assumptions]
    assumption_values(assumptions, name=name)


# --------------------------------------- 2. 直す前の実物が落ちること（故障注入）

#: **2026-08-16 に直す前の、実際の行です。** 作った例ではありません。
BEFORE_THE_FIX = [
    ("nenkin",
     "手取り率は制度の値ではなく、この計算での仮定です。"
     "額が上がるほど下がるものとして置いています"),
    ("furusato",
     "社会保険料率はこの計算での仮定です。"
     "加入している健康保険や介護保険の対象かどうかで実際は変わります"),
    ("tedori",
     "社会保険料は年収に対する一定率として置いています。"
     "実際は標準報酬月額の等級で階段状に動きます"),
    ("yukyu",
     "週の所定労働日数は年間を通じて一定としています。途中で変わると付与日数も変わります"),
]


@pytest.mark.parametrize("name,line", BEFORE_THE_FIX, ids=[n for n, _ in BEFORE_THE_FIX])
def test_the_real_broken_lines_fail(name, line):
    with pytest.raises(TableError) as got:
        assumption_values([line], name=name)
    # **直し方まで渡すこと。** 落ちた理由だけ言われても、次に来た側は
    # 「どの値を書けばよいか」が分からず、文のほうを削って通します。
    assert "として置いています" in str(got.value)
    assert name in str(got.value)


# ------------------------------------------------ 3. 偽陽性を作らないこと

def test_naming_a_quantity_without_claiming_it_is_an_assumption_passes():
    """**量の名前を出しただけの行は見ません。**

    `ASSUMPTIONS` の大半は「〜は入れていません」「〜は変わります」で、
    そこに出てくる量は**この計算の仮定ではありません。**
    文単位の名乗り（`仮定` `前提` `として置` …）に絞る前は、
    実測で 22件中 16件がこの形の偽陽性でした。
    """
    assumption_values([
        "増額率も減額率も、一度決まると生涯そのままです",
        "ふるさと納税以外の所得控除は入れていません。医療費控除があると上限は下がります",
        "給付制限期間・受給期間の延長・給付日数の延長は考慮していません",
    ], name="t")


def test_marker_and_quantity_in_different_sentences_passes():
    """名乗った文に量が無ければ見ません（**実物**: `yukyu` の繰り越しの行）。

    行ごとに当てると、「古いほうから使う**前提です**」という順序の仮定に
    「消える**日数**」が引っ張られて落ちます。**順序に値は書けません。**
    """
    assumption_values([
        "繰り越した有給は古いほうから使う前提です。"
        "新しいほうから使う運用だと、消える日数はここより増えます",
    ], name="t")


def test_value_may_sit_in_the_next_sentence():
    """**値は行のどこにあってもよい。** `verify` の「前後14字」は使いません。

    向こうが近さを見るのは、画面が別々のコマの文字を全部つないだものだからです。
    こちらの1行は前提そのものなので、行の中の数字はその前提の値です。
    **この形を落とすと、`nenkin` の正しい直し方が通りません**（実際に落ちました）。
    """
    assumption_values([
        "手取り率は制度の値ではなく、この計算での仮定です。"
        "年額78万円で100パーセント、500万円で79パーセントとして置いています",
    ], name="t")


def test_zenkaku_digits_count():
    """全角数字も値として読むこと。**`ASSUMPTIONS` は日本語の散文です。**"""
    assumption_values(["社会保険料率は１５パーセントの仮定です"], name="t")


# --------------------------------- 4. 語彙が1か所しか無いこと（片方だけ育たせない）

def test_verify_imports_the_same_vocabulary():
    """**`verify` と `_checks` が同じ語彙を見ていること。**

    この穴が8回運ばれた理由が「片側にしか検査が無かった」ことなので、
    **定義を2つ持った瞬間に、また同じ形で開きます。**
    ここは同一性（`is`）で見ます —— 値が等しいだけでは、
    片方に語を足した日に静かに離れます。
    """
    import src.verify as verify
    assert verify._QUANTITY_TAILS is _checks.QUANTITY_TAILS
    assert verify._ASSUMPTION_MARKERS is _checks.ASSUMPTION_MARKERS
    assert verify._VALUE_NEAR_CHARS == _checks.VALUE_NEAR_CHARS
    assert verify._trim_particles is _checks.trim_particles


def test_script_writer_runs_the_check_before_generating():
    """**生成に入る前に止まること。**

    `verify` で止めても、そのときには台本生成とレンダリングが終わっています
    （1本ぶん捨てる）。渡す側が空だと分かっているなら、**渡す前に止める**のが安い。
    """
    import inspect

    import src.script_writer as sw
    src = inspect.getsource(sw.calc_block)
    assert "assumption_values" in src, (
        "`calc_block` が ASSUMPTIONS を書き手に渡す直前で "
        "`_checks.assumption_values` を呼んでいません")
