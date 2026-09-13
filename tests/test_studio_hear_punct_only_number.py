"""**句読点だけの「数」で `hear` が落ちない**
（2026-09-14 01:3x・optimizer・Opus。derivation は JOURNAL 01:3x・註は `hear.num_to_kana`）。

**規則A**（`studio` を import しているので live の印が機械で付く・§6）。
**陽性対照は「壊したら落ちる」まで撃つこと**（§5 の教訓の形3つ目）。
"""
from __future__ import annotations

import pytest

from studio import hear


def test_数字を1つも持たない字は空で返す():
    """`_kana_by_janome` の数の buf は `[0-9.,]+` で集めるので、`.` や `,` だけの buf が来ます。"""
    assert hear.num_to_kana("") == ""
    assert hear.num_to_kana(".") == ""
    assert hear.num_to_kana(",") == ""
    assert hear.num_to_kana(",.") == ""


def test_数の読みは変わっていない_陽性対照():
    """上の門が、本来の数まで空にしていないこと。"""
    assert hear.num_to_kana("423700") == "よんじゅうにまんさんぜんななひゃく"
    assert hear.num_to_kana("0.7") == "れいてんなな"
    assert hear.num_to_kana("1,000") == "せん"
    assert hear.num_to_kana("0") == "れい"


def test_ASCIIの句読点を書いた文でもto_kanaが通る():
    """**実物で踏んだ形**: この 1行 で `hear.check` が `ValueError` で止まっていました。"""
    got = hear.to_kana("けいさんすると, 15まんえん. です")
    assert "じゅうごまんえん" in got
    assert "," not in got and "." not in got


def test_degenerateも止まらない():
    """`check()` が最初に呼ぶ口（落ちていた当のもの）。"""
    hear.degenerate("けいさんすると, 15まんえん. です", "けいさんするとじゅうごまんえんです")


@pytest.mark.parametrize("bad", ["", ".", ","])
def test_陽性対照_門を外すと落ちる(bad):
    """門（`any(c.isdigit() ...)`）を外した形 ＝ 直す前の振る舞いが、いまも例外であること。"""
    with pytest.raises(ValueError):
        int(bad.replace(",", ""))
