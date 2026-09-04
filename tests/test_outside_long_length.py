# -*- coding: utf-8 -*-
"""**作れと言う尺が、測った帯の速い側を向いていること。**（2026-09-05 02:0x・毎時の回）

## この検査が守っているもの

`script_writer.OUTSIDE_LONG_RULE` は **「尺は20分前後」**と書いていました。
同じ repo が別の場所で測った数は、こうです（外の長尺 365本・`data/niche_corpus.jsonl`）:

    20〜25分  n=37    823回/日
    25〜30分  n=34  3,507回/日   ← **×4.3**
    30〜40分  n=32  2,885回/日

＝ **書き手への指示が、自分で測った帯の遅い側を名指ししていました。**
その指示で出た実物が `GFvAcxvDmYM`（台本 7,699字・`duration_s` 1,361.1秒 ＝ **22.7分**）で、
**切れ目 25分 の 2.3分 下**。09/07 の判定は、この本で読まれます。

**尺は書き手からは見えません。見えるのは文字数だけです。**
だから指示は**文字数**で書くこと —— 実効 5.62字/秒（`daily_pick.LONG_CHARS_PER_SECOND`）。
"""
import re

from src import daily_pick as dp
from src import script_writer as sw


def _nums(pattern, text):
    return [int(x.replace(",", "")) for x in re.findall(pattern, text)]


def test_指示は帯の切れ目の上を向いていること():
    """**「20分前後」が戻ってこないこと。**"""
    r = sw.OUTSIDE_LONG_RULE
    assert "尺は20分前後" not in r, (
        "外の型の長尺に『20分前後』と指示しています —— "
        "自分で測った帯では 20〜25分 は 823回/日、25〜30分 は 3,507回/日（×4.3）"
    )
    assert "26〜29分" in r, "指示に狙う尺が書かれていません"


def test_指示の文字数が狙う尺と実効の速さで合っていること():
    """**8,800〜9,800字 が 26〜29分 × 5.62字/秒 と一致すること。**

    ここがずれると、書き手は文字数だけを見るので**尺だけが静かにずれます**
    （それがちょうど 09/05 の本に起きたことです）。
    """
    r = sw.OUTSIDE_LONG_RULE
    m = re.search(r"ナレーションの合計を ([\d,]+)〜([\d,]+)文字", r)
    assert m, "指示に文字数の幅が書かれていません"
    lo, hi = int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))
    rate = dp.LONG_CHARS_PER_SECOND
    lo_min, hi_min = lo / rate / 60, hi / rate / 60
    assert 25.0 <= lo_min, (
        f"下の {lo:,}字 は {lo_min:.1f}分 ＝ 切れ目 25分 の下です（実効 {rate}字/秒）"
    )
    assert hi_min <= 30.0, (
        f"上の {hi:,}字 は {hi_min:.1f}分 ＝ いちばん速い帯（25〜30分）の外です"
    )


def test_狙う尺は帯の切れ目の上に在ること():
    """`OUTSIDE_LONG_KNEE_SEC` と指示が同じほうを向いていること。"""
    r = sw.OUTSIDE_LONG_RULE
    m = re.search(r"ナレーションの合計を ([\d,]+)〜", r)
    assert m
    lo_sec = int(m.group(1).replace(",", "")) / dp.LONG_CHARS_PER_SECOND
    assert lo_sec >= dp.OUTSIDE_LONG_KNEE_SEC, (
        f"指示の下限 {lo_sec:.0f}秒 が切れ目 {dp.OUTSIDE_LONG_KNEE_SEC}秒 の下です"
    )


def test_章の数が尺と食い違っていないこと():
    """**5〜7章 のままだと、字数だけ増やせと言うことになります**（＝ 水増しの指示）。"""
    r = sw.OUTSIDE_LONG_RULE
    assert "章を5〜7つ" not in r, (
        "尺を上げたのに章の数が 5〜7 のままです —— "
        "同じ章数で字数だけ増やすのは水増しの指示です"
    )
    assert "7〜9つ" in r


def test_水増しを禁じる1行が在ること():
    """**字数を埋めるために同じ話を繰り返せ、と読めないこと。**

    オーナーの固定指示「動画内の説明は人間にわかるようにして」に直に当たります。
    """
    r = sw.OUTSIDE_LONG_RULE
    assert "水増し" in r or "繰り返さないこと" in r, (
        "字数の指示に、水増しを禁じる1行がありません"
    )
    assert "題材を替えること" in r, "足す判断が無いときの逃げ道が書かれていません"


def test_実効の速さが1か所にしかないこと():
    """**指示の中に、5.62 と食い違う『字/秒』が書かれていないこと。**"""
    r = sw.OUTSIDE_LONG_RULE
    rates = {float(x) for x in re.findall(r"([\d.]+)\s*文字/秒", r)}
    assert rates <= {dp.LONG_CHARS_PER_SECOND}, (
        f"指示の中の字/秒 {rates} が "
        f"`daily_pick.LONG_CHARS_PER_SECOND`（{dp.LONG_CHARS_PER_SECOND}）と違います"
    )
