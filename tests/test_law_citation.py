"""**条文の引用が、calc の書いているとおりに写されていること**を固定する。

## なぜ要るか（2026-08-16）

独立評価の3体が `8PMLfjjCe4w` について、独立に
「**`雇用保険法22条23条` の条番号が壊れている**」と書きました
（1体は「読み上げは『別表』なのに画面は条番号で、一致しない」とも）。

**出どころを測ったら、生成側でも描画側でもありませんでした。**

    src/calc/shitsugyo.py  「所定給付日数は雇用保険法22条・23条の別表どおり」
    画面（表の1行）          「雇用保険法22条23条」          ← 中黒が消えている
    読み上げ                「日数は雇用保険法の別表」        ← 条番号を言っていない

折り返し（`visuals._wrap`）を実物の文で走らせても中黒は残ります。落としたのは
**台本の書き手**で、`ASSUMPTIONS` を表の1行に詰めるときに区切りごと消えました。
`雇用保険法22条23条` は法令の引用として**存在しない形**です。

数字（`_check_headline_from_calc`）・式（`_check_formula_shown`）・
前提の値（`_check_assumption_value_shown`）は calc と突き合わせているのに、
**条文の引用だけ、誰も突き合わせていませんでした。**

## ここで固定すること

1. **実際に画面に出た壊れ方を落とすこと**（落とさなければ、この直しは何もしていない）
2. **写した形を通すこと** —— 偽陽性は投稿を止め、それが最大の損失にあたります
3. **`script_writer.short_script_problems` を通って届くこと** ——
   関数を足しても、呼ばれていなければ**緑のまま0件で通ります**
   （2026-08-15 に `pytest tests/` が収集エラーで1件も走っていなかった回があります）
4. **calc が引けない事情で例外を投げないこと** ——
   生成中に呼ばれるので、落ちると台本作りごと止まります
5. **中黒を照合から落とさないこと**（故障注入）——
   均しすぎると、この検査は**自分が捕まえるべきものを自分で通します**
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import script_writer, verify  # noqa: E402

# `src/calc/shitsugyo.py` が実際に書いている引用。
GOOD = "雇用保険法22条・23条"
# 2026-08-16 に実際に画面へ出たもの（`8PMLfjjCe4w` の6コマ目・表の1行）。
BROKEN = "雇用保険法22条23条"

SHITSUGYO = Path("build/s-shitsugyo-6")     # calc=shitsugyo
IKUJI = Path("build/s-ikuji-67-tedori-849")  # calc=ikuji


def _script(cell: str, narration: str = "") -> dict:
    return {"segments": [{
        "narration": narration,
        "visual": {"kind": "table", "headline": "この計算の前提",
                   "headers": ["項目", "置き方"],
                   "rows": [["給付日数", cell], ["日額", "令和8年8月1日改定"]]},
    }]}


def test_実際に画面へ出た壊れ方を落とす():
    problems = verify._check_law_citation_verbatim(SHITSUGYO, _script(BROKEN))
    assert problems, f"{BROKEN} を通した。これが直しの目的そのもの"
    assert BROKEN in problems[0]
    # 直し方に、写すべき形が入っていること（助詞ごと見せない）。
    assert GOOD in problems[0]
    assert "所定給付日数は雇用保険法" not in problems[0]


def test_写した形は通す():
    assert not verify._check_law_citation_verbatim(SHITSUGYO, _script(GOOD))


def test_条番号を出さない形は通す():
    """3体のうち1体は「読み上げの『別表』と画面が一致しない」と書いた。

    **条番号を出さないのは正しい逃げ道**なので、ここを塞がないこと。
    """
    assert not verify._check_law_citation_verbatim(SHITSUGYO, _script("雇用保険法の別表"))


def test_読み上げ側も見る():
    s = _script("雇用保険法の別表", narration=f"日数は{BROKEN}の別表どおりです。")
    problems = verify._check_law_citation_verbatim(SHITSUGYO, s)
    assert problems and "読み上げ" in problems[0]


def test_枝番号を落とした引用を落とす():
    """`雇用保険法61条の7第5項` → `雇用保険法61条7項` は**別の条文**。"""
    assert verify._check_law_citation_verbatim(IKUJI, _script("雇用保険法61条7項"))
    assert not verify._check_law_citation_verbatim(IKUJI, _script("雇用保険法61条の7第5項"))


def test_条文を引いていないcalcに引用が出たら落とす():
    """`src/calc/tedori.py` は条文を1つも引いていない。

    そこに条番号が出たなら、**calc の外から持ってきた**ことになる。
    """
    problems = verify._check_law_citation_verbatim(Path("build/s-tedori-1"), _script("所得税法89条"))
    assert problems


def test_calcの無いテーマは素通しする():
    """引用の照合ができないことを理由に投稿を止めるのは割に合わない。"""
    assert not verify._check_law_citation_verbatim(Path("build/存在しないテーマ"), _script(BROKEN))
    assert not verify._check_law_citation_verbatim(SHITSUGYO, None)
    assert not verify._check_law_citation_verbatim(SHITSUGYO, {"segments": []})


def test_同じ引用は1度しか言わない():
    """同じ文字列が何コマにも出るので、まとめないと同じ指摘が並ぶ。"""
    s = _script(BROKEN)
    s["segments"].append(dict(s["segments"][0]))
    assert len(verify._check_law_citation_verbatim(SHITSUGYO, s)) == 1


def test_中黒を均すと自分で通してしまう():
    """**故障注入。** 照合の前に中黒を落とすと、この検査は何も見なくなる。

    `_normalize_citation` は「均す」関数なので、**次に触る側は
    中黒も落としたくなります。** そこを踏んだら落ちるようにしておく。
    """
    real = verify._normalize_citation
    try:
        verify._normalize_citation = lambda t: real(t).replace("・", "")
        assert not verify._check_law_citation_verbatim(SHITSUGYO, _script(BROKEN)), (
            "中黒を落とす実装でも落ちてしまう＝この検査は中黒を見ていない"
        )
    finally:
        verify._normalize_citation = real
    # 元に戻したら、また落とすこと
    assert verify._check_law_citation_verbatim(SHITSUGYO, _script(BROKEN))


def test_作り直しの輪に入っていること():
    """`script_writer` 側から呼ばれていなければ、直す口の無いところでしか落ちない。

    `_calc_source_problems` は生成中に呼ばれるので、**例外を投げないこと**も見る。
    """
    problems = script_writer._calc_source_problems("s-shitsugyo-6", _script(BROKEN))
    assert any(BROKEN in p for p in problems), "輪の中に届いていない"


def test_輪の中で例外を投げない():
    for topic in ("s-shitsugyo-6", "存在しないテーマ"):
        for data in ({}, {"segments": []}, _script(GOOD)):
            script_writer._calc_source_problems(topic, data)
