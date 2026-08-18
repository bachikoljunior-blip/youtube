r"""`万` の下に、隣の語の数字を吸い込んでいた（2026-08-19 に実測）。

`scripts/topic_forge.py` の `_NUM` は長らく

    (\d[\d,]*(?:\.\d+)?)\s*万\s*(\d[\d,]*)?

で、**`万` の後ろに `\s*` があります。** 「1121万2500円」を 11,212,500 と読むための
枝ですが、空白をまたぐので **`退職金2000万 1日で106,470円の差` の「1日」の 1**
まで万の下に吸い、**20,000,001** という実在しない数を作っていました。

同じ枝が **`千` を読みません。** 「431万8千円」は `man=431 / rest=8` と割れて
**4,310,008**（正しくは 4,318,000）になります。

**どちらも「実在しない数」を作る**ので、向きは1つです ——
`best_section()` の突き合わせでは当たらず（＝正しい節に貼られない）、
`validate()` では「表の外の数字を使っています」に見えます。
**`43.2万円` → 20,000 と同じ形で、これが3件目**です。

実測（`config/topics.yaml` 413件）: 数の集合が変わるのは **8件**で、
**8件とも新しい側が正しい**（`12万9千` が 120,009 → 129,000 など）。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import topic_forge as tf


def test_man_does_not_swallow_the_next_word():
    """「2000万 1日で…」の 1 を、万の下に吸わないこと。"""
    got = tf.numbers("退職金2000万 1日で106,470円の差")
    assert 20_000_000 in got
    assert 20_000_001 not in got, "空白の向こうの数字を万の下位に足している"
    assert 106_470 in got


def test_sen_is_a_thousand():
    """「431万8千円」は 4,318,000。**8 をそのまま足さない。**"""
    got = tf.numbers("任意継続と国保 1人は431万8千円で逆転")
    assert 4_318_000 in got
    assert 4_310_008 not in got


def test_man_plus_digits_still_works():
    """「1121万2500円」の枝は残っていること（この直しで壊しやすい）。"""
    got = tf.numbers("相続税 配偶者25%で1121万2500円")
    assert 11_212_500 in got and 1121 in got


def test_decimal_man_still_works():
    """`43.2万円` → 432,000（2026-08-18 の直しを踏み直さない）。"""
    assert 432_000 in tf.numbers("43.2万円")
    assert 20_000 not in tf.numbers("43.2万円")


def test_plain_man_keeps_both_forms():
    """「1000万円」は 10,000,000 と 1000 の両方。"""
    got = tf.numbers("1000万円")
    assert {1000, 10_000_000} <= got


def test_sections_for_is_substring_matching():
    """`calc_sections` は**見出しに含まれる語**であって、見出しそのものではない。

    完全一致で引くと、実物では1件も当たりません（2026-08-19 に12分払った）。
    """
    secs = {"=== 配偶者にどれだけ寄せるか（課税価格1億5000万円・子2人） ===": "本文A",
            "=== 相続人の数で1人あたりはどう変わるか ===": "本文B"}
    topic = {"calc_sections": ["配偶者にどれだけ寄せるか"]}
    assert tf.sections_for(topic, secs) == "本文A"
    assert tf.sections_for({}, secs) == "本文A\n本文B"   # 指定なしは全部
