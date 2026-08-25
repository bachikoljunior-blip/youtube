r"""倍率と率だけで成り立つ節は、いまの門を**構造的に**通れなかった（2026-08-18 20:1x）。

`scripts/topic_forge.py` の `numbers()` は整数しか拾いませんでした。だから
`src/calc/koyouhoken.py` の

    === 業種の差は労働者側では同じ0.1ポイント、建設だけ事業主で2倍になる ===

のように **表の数字が `0.1` `0.2` `2.0` だけ**の節は、どんなに正直に題を書いても
一致0になり、**4回頼んで4回とも**「表の外の数字を使っています」で落ちました。
門の文言のほうが嘘です（書き手は表の外へ出ていません）。

同じ正規表現に、もう1つ隠れていました。`(\d[\d,]*)\s*万` は **`43.2万` の中の
`2万` だけ**に当たるので、`43.2万円` が **20,000** になります。正しい 432,000 は
どこにも出ず、代わりに実在しない 20,000 が出て、**同じ誤りを含む節と偶然に
一致**していました（`s-nenkin-kuriage-…` が繰上げの題なのに**繰下げの節**へ
貼られていたのはこれです）。

## 下限0にしなかった理由（**書いて、その場で落とされた**）

申し送りは「`best_section` の逃げ道をもう一段（下限0）」でした。そのとおりに
書いたところ、`test_forge_floor_fallback.py::test_実物の_nenkin_で作り話は落ちたまま`
が即座に落ちました —— `分岐点は92歳7か月まで動く` が **一致1**。
**1桁の整数はどの表にも出ます。** 下限0は門を開けるのではなく、壊します。

だから最後の段は**小数だけ**を見ます。`0.1` `1.636` `2.0` は表を名指しできますが、
`7` は名指しできません。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import topic_forge as tf  # noqa: E402


RATIO = {
    "=== 倍率だけの節 ===": "  一般 1.636倍 ／ 農林水産 1.538倍 ／ 建設 1.692倍",
    "=== ポイントだけの節 ===": "  労働者 0.1 ／ 事業主 農林水産 0.1・建設 0.2（2.0倍）",
}

MONEY = {
    "=== 金額の節 ===": "  年収400万円 → 手取り 3,120,000円  控除 480,000円",
    "=== 年齢の節 ===": "  分岐点 81歳10か月 → 84歳2か月（28か月うしろ）",
}


# ---------------------------------------------------------------- 小数を読む

def test_小数と万をあわせて読む():
    """**旧は `43.2万円` を 20,000 にしていました**（`2万` にだけ当たっていた）。"""
    assert tf.numbers("減る額は年43.2万円") == {432000}
    assert tf.numbers("65歳で年180.0万円") == {1800000}


def test_整数の万はこれまでどおり():
    """**大多数はここを通ります。1文字も変わらないこと。**"""
    assert 800000 in tf.numbers("80万円")
    assert 1000 in tf.numbers("1000万円")          # 「1000万」の 1000 単体
    assert 10000000 in tf.numbers("1000万円")
    assert tf.numbers("1,234万5,678円") == {12345678, 1234}


def test_小数はそのまま数として拾う():
    assert tf.numbers("1.636倍", floor=0) >= {1.636}
    # 整数になる小数は整数へ戻す（`2.0` と `2` を別の数として数えない）
    assert 2 in tf.numbers("2.0倍", floor=0)


def test_decimals_は整数を1つも拾わない():
    assert tf.decimals("0.1ポイントと0.2ポイントで2.0倍") == {0.1, 0.2, 2.0}
    assert tf.decimals("分岐点は92歳7か月まで動く") == set()
    assert tf.decimals("3,120,000円") == set()


# ---------------------------------------------------------------- 段の降り方

def test_倍率と率だけの節に当たる():
    """直す前は、この題は**どう書いても**一致0でした。"""
    ranked = tf.best_section("事業主の差は建設だけ0.2ポイントで2.0倍", RATIO)
    assert ranked[0][0] > 0
    assert ranked[0][1] == "=== ポイントだけの節 ==="


def test_書き方の指示だけが下限を超える題でも降りる():
    """**「空か」ではなく「当たったか」で降りること。**

    実物（`s-koyouhoken-jigyounushi-1636bai`）の `angle` には
    「1枚目は…（22文字以内）」という**書き方の指示**が入っています。
    主張の数字は `1.636` `0.55` `0.9` だけなのに、**22 だけが 10 を超える**ので、
    旧の「`numbers(text, floor)` が空のときだけ降りる」は降りませんでした。
    """
    text = "事業主は労働者の1.636倍（1枚目は22文字以内）"
    assert tf.numbers(text, tf.SMALL_FLOOR) == {22}      # 空ではない
    assert tf.best_section(text, RATIO)[0][0] > 0        # それでも当たる


def test_整数で当たっている題は段を降りない():
    """降りるのは**これまで無条件に落ちていた題だけ**。"""
    ranked = tf.best_section("手取りが3,120,000円になる", MONEY)
    assert ranked[0][0] == 1
    assert ranked[0][1] == "=== 金額の節 ==="
    # 段は 1000 のまま（400 は捨てられ、小数の段まで降りていない）
    assert tf.match_scale("手取りが3,120,000円になる", MONEY)(
        "3,120,000円と400") == {3120000}


def test_表に無い小数も落ちる():
    """**門が空になっていないこと。** ここが緩むと誤情報がそのまま公開されます。"""
    assert tf.best_section("事業主は労働者の9.99倍", RATIO)[0][0] == 0


def test_1桁の整数では通さない():
    """下限0にすると `7` が表のどこかに当たります。**それは名指しではありません。**"""
    assert tf.best_section("分岐点は92歳7か月まで動く", MONEY)[0][0] == 0


# ---------------------------------------------------------------- 実物

def test_実物の_koyouhoken_の節が通る():
    sections = tf.sections("koyouhoken")
    head = "=== 業種の差は労働者側では同じ0.1ポイント、建設だけ事業主で2倍になる ==="
    assert head in sections
    text = ("一般の事業を基準にすると労働者側は農林水産も建設も0.1ポイント、"
            "事業主側は農林水産0.1・建設0.2ポイントで2.0倍")
    ranked = tf.best_section(text, sections)
    assert ranked[0][0] > 0
    assert ranked[0][1] == head


def test_実物の_nenkin_の繰上げが繰下げの節に貼られない():
    """`43.2万円` → 20,000 の取り違えが、実物で起こしていた形。"""
    sections = tf.sections("nenkin")
    text = ("60歳から受け取ると年金は年43.2万円減る 65歳で年180.0万円の人が"
            "60歳0か月から繰上げると倍率0.760、年額136.8万円")
    assert "繰上げ" in tf.best_section(text, sections)[0][1]


def test_全部の_calc_で段が壊れていない():
    """`rungs()` は必ず厳しいほうから並び、最後は小数の段。"""
    for mod in tf.calc_modules():
        ladder = tf.rungs(tf.sections(mod))
        assert ladder[-1] is tf.decimals, mod
        floors = [f.floor for f in ladder[:-1]]
        assert floors == sorted(floors, reverse=True), (mod, floors)


# ---------------------------------------------------------------- 総覧の判定

def test_swallows_は渡された段で比べる():
    """小数の段で選ばれた節を、1000 の目盛りで判定しないこと。

    1000 では両側とも空集合になり `mine` が空 → 常に False ＝
    **総覧の吸い込みを素通りさせます。**
    """
    sections = {
        "=== 総覧 ===": "  0.1 ／ 0.2 ／ 2.0 ／ 1.636 ／ 1.538",
        "=== 部分 ===": "  0.1 ／ 0.2",
    }
    assert tf.swallows(sections, "=== 総覧 ===", "=== 部分 ===", tf.decimals)
    assert not tf.swallows(sections, "=== 総覧 ===", "=== 部分 ===")   # 既定＝1000
