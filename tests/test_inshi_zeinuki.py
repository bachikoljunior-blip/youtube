"""`inshi.zeinuki_limit` は閉じた式であること。

**走査に戻すと、検査そのものが終わらなくなります**（2026-08-18 17:4x に踏んだ）。
**同じ欠陥に、同じ時刻に、別の回も当たっています**（`c242855`。直しはあちらを採用）。
あちらが足した検査は「`src/calc/` の全部の表で `check_tables()` が1秒を超えないこと」で、
**掛かる先が違います** —— あちらは表ぜんぶ、こちらはこの関数1つ。**両方残します。**
`tests/test_section_sweep.py` は `kind` の全部の値で呼ぶので、
第1号文書の境目 5,000,000,001円で **1回あたり5億回**まわりました。
26分たっても終わらず、前の回はこの検査を緑と書けないまま畳んでいます。

**だから、ここで見るのは値だけではありません。**「遅い」は値の検査では出ないので、
**ソースの字**（走査の構文が残っていないこと）も見ます。
戻したときに**落ちる**ようにしてあります —— 戻したときに**止まる**のでは、
次の回がまた26分を払うからです。
"""
import ast
import inspect
import time

import pytest

from src.calc import inshi


def _by_definition(edge: int) -> int:
    """定義そのもの（**遅いほう**）。小さい値でだけ突き合わせます。"""
    x = edge
    while (x + 1) * 100 // 110 < edge:
        x += 1
    return x


@pytest.mark.parametrize("edge", [1, 2, 11, 100, 1_001, 50_001, 100_001,
                                  500_001, 1_000_001])
def test_matches_the_definition(edge):
    assert inshi.zeinuki_limit(edge) == _by_definition(edge)


def test_is_the_largest_tax_included_amount_below_the_edge():
    """**返る値そのものは帯の内側、1円足すと外側。**"""
    for edge in (100_001, 1_000_001, 5_000_000_001):
        top = inshi.zeinuki_limit(edge)
        assert top * 100 // 110 < edge
        assert (top + 1) * 100 // 110 >= edge


def test_the_largest_edge_is_instant():
    """第1号文書の最大の境目でも一瞬で返ること（走査だと5億回）。"""
    start = time.monotonic()
    assert inshi.zeinuki_limit(5_000_000_001) == 5_500_000_001
    assert time.monotonic() - start < 0.5


def test_no_loop_in_the_source():
    """**走査の構文が1つも無いこと。** 戻したときに、止まるのではなく落ちます。"""
    tree = ast.parse(inspect.getsource(inshi.zeinuki_limit))
    loops = [n for n in ast.walk(tree)
             if isinstance(n, (ast.While, ast.For, ast.comprehension))]
    assert loops == [], "zeinuki_limit に走査が戻っています（閉じた式で書くこと）"


def test_keigen_shapes_prints_the_total():
    """**内訳だけでなく合計も**（`11段のうち6段` の 11 が画面に出せるように）。"""
    shapes = inshi.keigen_shapes()
    assert shapes["段の合計"] == sum(shapes["割合べつの段数"].values()) == 11
