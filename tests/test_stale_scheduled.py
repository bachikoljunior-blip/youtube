r"""予約に入っている本の主役の数字が、いまの表に在るか（2026-08-19）。

**丸めの言い換えで鳴らせてはいけません。** 実測（予約246本）では、
題の数字をそのまま見ると16件鳴って本物は1件。
**「精密な数だけ」に絞ると 1件鳴って 1件とも本物**でした。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import stale_scheduled as ss


def test_rounded_numbers_are_not_precise():
    """「1000万円」の 1000 や、万どまり・千どまりの数では鳴らないこと。"""
    for n in (1000, 3000, 42_850_000, 4_318_000, 900, 22):
        assert not ss.is_precise(n), n


def test_full_precision_numbers_are_precise():
    """百円の位まで意味を持つ数は見ること（本物はここに出る）。"""
    for n in (49_043_334, 11_212_500, 106_470, 10_764_000 + 1):
        assert ss.is_precise(n), n


def test_floats_are_never_precise():
    """小数（率・倍率）はこの門の対象外。**金額の話しかしていない。**"""
    assert not ss.is_precise(2.34)
    assert not ss.is_precise(5.0)
