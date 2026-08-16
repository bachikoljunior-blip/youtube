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
    sections = tf.sections("nenkin")
    assert tf.best_section("分岐点は92歳7か月まで動く", sections)[0][0] == 0


def test_金額を持たない_calc_はこれまでどおり():
    """`yukyu` `jikangai`（8/16 06:2x に足した道）が変わっていないこと。"""
    small = {"=== 日数の節 ===": "  20年で241日  年5日  時季指定義務"}
    assert tf.section_floor(small) == tf.SMALL_FLOOR
    assert tf.best_section("20年で241日を捨てる", small)[0][0] > 0
