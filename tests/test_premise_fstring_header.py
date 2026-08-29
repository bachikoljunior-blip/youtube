"""**f 文字列の見出しが、節の切れ目として見えるか**（2026-08-27 に踏んだ）。

`src/premise.py` の `_header` は長らく `ast.Constant` の引数しか見ておらず、
**見出しに計算した数を入れると（`f"=== …{lo}時間だけ ==="`）節の切れ目が消えて**
いました。消えると、その節のリテラルが**まるごと1つ前の節の持ち物**になります。

実際に出た誤報（`src/calc/ideco_deguchi.py`）:

    節「出口の税が初めて1円以上になる利回り（0.1パーセントきざみで探す）」は
    10,000 で計算しているのに、その値が節のどこにも出ていません

**10,000 はその節のものではありません。** 2つ下の
`same_year_break(step=10_000)` のもので、**見出しが f 文字列だったせいで
そこに流れ込んでいました。**

**逆向きの害のほうが大きい**（この検査が本当に守っているもの）:
切れ目が消えると2つの節が1つに見えるので、**後ろの節の前提が
「前の節に出ている」ことになって素通りします。** `jutaku` がそれで、
`_header` を直した回に **「同じペアの13年ぶん」の 600万・100万 が
1つも画面に出ていない**ことが初めて当たりました。

**この検査を消さないこと。** 消すと、見出しに数を入れた節（＝いちばん
親切に書かれた節）だけが前提の検査から外れます。
"""
from __future__ import annotations

import textwrap

from src import premise


SRC = textwrap.dedent(
    '''
    if __name__ == "__main__":
        print("\\n=== ふつうの見出し ===")
        for row in table(1_000_000):
            print(row)

        print(f"\\n=== f 文字列の見出し（{2 + 3}件）===")
        for row in other(9_000_000):
            print(row)

        print("\\n=== 暗黙の連結の見出し"
              f"（{7}件）===")
        for row in third(4_000_000):
            print(row)
    '''
)


def test_f文字列の見出しが節の切れ目になる():
    heads = [h for h, _ in premise.sections(SRC)]
    assert len(heads) == 3, heads
    assert "ふつうの見出し" in heads[0]
    assert "f 文字列の見出し" in heads[1]
    assert "暗黙の連結の見出し" in heads[2]


def test_後ろの節のリテラルが前の節へ流れ込まない():
    got = dict(premise.sections(SRC))
    first = next(v for k, v in got.items() if "ふつうの見出し" in k)
    second = next(v for k, v in got.items() if "f 文字列の見出し" in k)
    third = next(v for k, v in got.items() if "暗黙の連結の見出し" in k)
    assert first == {1_000_000}, first
    assert second == {9_000_000}, second
    assert third == {4_000_000}, third


def test_見出しの字の部分だけを名前にする():
    """`{}` の中身は落ちてよい —— 要るのは切れ目であって、完全な名前ではない。"""
    heads = [h for h, _ in premise.sections(SRC)]
    assert heads[1].startswith("===")
    assert heads[1].endswith("===")
