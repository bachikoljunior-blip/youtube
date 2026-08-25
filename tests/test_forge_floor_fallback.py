"""金額の主張をしていない題を、`realign` が「表の外の数字」と誤って落とす形（2026-08-16）。

`section_floor` は **calc ごと**に下限を決めます。金額の表を1つでも持っていれば
1000 です。ところが `nenkin` の節の多くは**年齢と月数の表**で、主役の数字は
`81歳10か月` `28か月` のように全部3桁以下です。

書き手には「**表に無い数字は1つも書かないこと**」と指示しているのに、
指示どおり表の数字だけで題を書くと `numbers(text, 1000)` が空集合になり、
一致数が全節で0 → **「表の外の数字を使っています」で落ちます。**
**門の文言のほうが嘘**でした（書き手は表の外へ出ていません）。

実測: `=== 年金額べつ / …===` から `--count 1` を2回頼み、**2回とも**同じ理由で
落ちました。`kyugyo` と同じで確率のぶれではなく、**その節からは今後ずっと
1件も通らない**形です。

直しは「**題の側に下限以上の数字が1つも無いときだけ** `SMALL_FLOOR` へ落とす」。
下の検査は、**直した側だけでなく、直していない側が動いていないこと**を固定します
（このリポジトリが通算7回踏んでいる「片方だけ直す」を、ここでは最初から見る）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import topic_forge as tf  # noqa: E402


MONEY = {
    "=== 金額の節 ===": "  年収400万円 → 手取り 3,120,000円  控除 480,000円",
    "=== 年齢の節 ===": "  分岐点 81歳10か月 → 84歳2か月（28か月うしろ）",
}


def test_金額の題はこれまでどおり1000で測る():
    """**大多数はここを通ります。挙動が1文字も変わらないこと。**"""
    ranked = tf.best_section("手取りが3,120,000円になる", MONEY)
    assert ranked[0][0] == 1
    assert ranked[0][1] == "=== 金額の節 ==="
    # 480,000 も金額なので拾える。小さい数（400）に引きずられないこと
    ranked = tf.best_section("控除は480,000円", MONEY)
    assert ranked[0][1] == "=== 金額の節 ==="


def test_金額を1つも言っていない題は小さい数で測る():
    """直す前は一致0 ＝ 無条件で落ちていた題。"""
    ranked = tf.best_section("分岐点は81歳10か月から84歳2か月へ", MONEY)
    assert ranked[0][0] > 0
    assert ranked[0][1] == "=== 年齢の節 ==="


def test_表に無い数字は下限を下げても落ちる():
    """**門が空になっていないこと。** ここが緩むと誤情報がそのまま公開されます。"""
    ranked = tf.best_section("分岐点は92歳7か月まで動く", MONEY)
    assert ranked[0][0] == 0


def test_実物の_nenkin_で2回落ちた形が通る():
    sections = tf.sections("nenkin")
    assert tf.section_floor(sections) == tf.MONEY_FLOOR
    for text in ("70歳まで待つと分岐点は81歳10か月から84歳2か月へ",
                 "年金額べつ 手取りの分岐点は28か月うしろ"):
        assert tf.best_section(text, sections)[0][0] > 0, text


def test_実物の_nenkin_で作り話は落ちたまま():
    """**この検査は 2026-08-25 まで赤でした。原因は門ではなく、この題のほうです。**

    もとは `分岐点は92歳7か月まで動く` を「表に無い年齢」として使っていました。
    2026-08-24 に `nenkin` へ `deferral_irr` の節が入り、その表に
    **`92歳` の行が実在します**（寿命べつの年利）。つまり **92 は表の中の数**で、
    **数字を見る門では、もう落とせません。**（`7` は下限10で消えるので残るのは 92 だけ）

    嘘なのは数字ではなく**主張のほう**（分岐点が 92歳7か月 だとは、どの表も
    言っていない）。**数字の門に、主張の判定を期待しないこと。**
    だから題のほうを、**いまの `nenkin` のどの表にも無い年齢**へ差し替えます
    （97 は 10〜99 のうち `nenkin` が持っていない22個の1つ）。

    **数は1つだけ書きます。**`97歳11か月` にすると `11か月` は表にあるので
    割合が 1/2 になり、割合の門（1/3）を**通ってしまいます** ——
    **短い題では割合が粗い**（数が2つなら 0 か 0.5 か 1.0 しか出ない）。
    実物は `title_seed + angle` で数が10個前後あるので、そこでは効きます
    （実測は下の `test_…偶然の1個では通らない`）。

    **この検査が次に赤くなったら、まず `nenkin` に 97 が入ったことを疑うこと。**
    表が深くなるほど2桁は埋まります（実測: `nenkin` は 90個中 68個を既に持つ）。
    **そのときは数字を替えるのではなく、下の `test_…偶然の1個では通らない` の
    ほうを見ること** —— 割合の門は表が深くなっても効きます。
    """
    sections = tf.sections("nenkin")
    assert tf.best_section("分岐点は97歳まで動く", sections)[0][0] == 0


def test_実物の_nenkin_で偶然の1個では通らない():
    """**一致1個は「表から書いた」証拠になりません**（2026-08-25 22:xx に足した）。

    `92` は実在します（上の節）。ところが残りが全部でたらめでも、
    **これまでは一致1で通っていました。** 実測では、実物486件の数字を
    全部でたらめに置き換えた 1,458本のうち **378本（25.9%）**が通り、
    **通った件の一致数は中央値1**でした。

    `backed_ratio` は「題の数字のうち、表に載っている割合」を見ます。
    しきい値 1/3 で、でたらめの通過は **25.9% → 0.8%**、
    本物は 486件中 **484件**が残ります（落ちる2件は丸めた散文）。
    """
    sections = tf.sections("nenkin")
    # 92 だけが実在。47・53・99 は `nenkin` のどの表にも無い → 1/4 = 0.25 < 1/3
    fake = "分岐点は92歳から47か月・53か月・99か月へ動く"
    assert tf.best_section(fake, sections)[0][0] == 0
    assert tf.backed_ratio(tf.numbers(fake, tf.SMALL_FLOOR),
                           sections, tf._by_floor(tf.SMALL_FLOOR)) == 0.25


def test_実物の_nenkin_で本物は残る():
    """**片方だけ直さない。** 上を厳しくした結果、本物が落ちていないこと。"""
    sections = tf.sections("nenkin")
    for text in ("70歳まで待つと分岐点は81歳10か月から84歳2か月へ",
                 "年金額べつ 手取りの分岐点は28か月うしろ"):
        assert tf.best_section(text, sections)[0][0] > 0, text


def test_割合の門は下限を持つ():
    """**しきい値そのものを固定する。** 動かすときは実測を添えること。"""
    assert tf.MATCH_RATIO_FLOOR == 1 / 3
    small = {"=== 日数の節 ===": "  20年で241日  年5日  時季指定義務"}
    rung = tf._by_floor(tf.SMALL_FLOOR)
    assert tf.backed_ratio({20, 241}, small, rung) == 1.0
    assert tf.backed_ratio({20, 241, 88, 99}, small, rung) == 0.5
    assert tf.backed_ratio(set(), small, rung) == 0.0


def test_金額を持たない_calc_はこれまでどおり():
    """`yukyu` `jikangai`（8/16 06:2x に足した道）が変わっていないこと。"""
    small = {"=== 日数の節 ===": "  20年で241日  年5日  時季指定義務"}
    assert tf.section_floor(small) == tf.SMALL_FLOOR
    assert tf.best_section("20年で241日を捨てる", small)[0][0] > 0
