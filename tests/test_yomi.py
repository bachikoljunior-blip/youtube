"""読みの回帰検査。

2026-08-16、オーナーが動画を聞いて「額」が「ひたい」と読まれているのを見つけた。
検査に音が1つも無かったので6日間残った。ここは**その穴を塞ぐ側**で、
API キーも音声ファイルも要らずに毎回走る。

Google TTS の実測は `scripts/probe_yomi.py`（耳）、
open-jtalk の形態素解析での検算は `scripts/check_yomi.py` が持つ。
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.verify import _check_yomi
from src.yomi import FIXES, remaining_risks, to_speech


def test_裸の額は仮名になる():
    # 実際に公開済みの動画に入っていた文。
    assert to_speech("実際の額は賃金日額で決まります。") == "実際のがくは賃金日額で決まります。"
    assert to_speech("税率が下がれば額も下がります。") == "税率が下がればがくも下がります。"


@pytest.mark.parametrize("word", ["控除額", "差額", "総額", "年額", "月額", "全額", "額面", "賃金日額"])
def test_複合語は触らない(word):
    """複合語は Google TTS が実測で全部「がく」と読む。触ると逆に壊れる。"""
    assert to_speech(f"{word}は10万円です。") == f"{word}は10万円です。"


def test_表の全件が置換される():
    for fix in FIXES:
        for case in fix.cases:
            assert to_speech(case) != case, f"置換が効いていない: {case}"
            assert not remaining_risks(case), f"壊れる形が残っている: {case}"


def test_画面に出る文字は変えない():
    """`to_speech` は TTS の直前だけで使う。字幕・説明欄は元の文のまま。"""
    original = "実際の額は賃金日額で決まります。"
    to_speech(original)
    assert original == "実際の額は賃金日額で決まります。"


def test_投稿前の検査が誤読を止める():
    bad = {"segments": [{"narration": "実際の額は賃金日額で決まります。"}]}
    # 台本の narration そのものは直っていない（直すのは TTS 層）。
    # verify は「TTS に渡したあとに壊れる形が残るか」を見るので、通るのが正しい。
    assert _check_yomi(bad) == []

    # 表を空にしたら（＝直しが外れたら）、同じ文で落ちること。歯があるかの確認。
    saved = FIXES[0].repl
    FIXES[0].repl = "額"
    try:
        assert _check_yomi(bad), "読みの直しを外しても検査が素通りしている"
    finally:
        FIXES[0].repl = saved


@pytest.mark.skipif(not shutil.which("open_jtalk"), reason="open-jtalk が入っていない")
def test_形態素解析でも読みがガクになる():
    """置換後の文を実際に音声エンジンの解析器に通し、ガクが出ることを固定する。"""
    result = subprocess.run(
        [sys.executable, "scripts/check_yomi.py"],
        cwd=Path(__file__).resolve().parent.parent, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
