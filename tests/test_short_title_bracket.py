"""ショートの題の門 —— **`【 】` が1つ在るか**（`script_writer.short_title_problems`）。

## なぜ要るか（2026-09-05 06:0x）

`RULES` のタイトルの節は、この日まで「**「」や【】は使わない**」と命じていました。
外の帯の実測は正反対です —— ショート 132本 で `【】` が在る本は 1.46回/日、
無い本は 0.26回/日 ＝ **×5.52**（n=55対77）。`niche_ceiling.title_features('short')` が
出す9つの特徴のうち、**両側の升が厚い（n≥20）のは 2つだけ**で、差が大きいほうがこれです。

禁止は完全に効いていました —— 自分の題の実測: `【】` は **ショート 0本／552本**。
**規則が、その形でいちばん大きい手を止めていました。**

## 何を固定するか

**「位置を命じないこと」を固定します。** この検査の最初の版は `startswith("【")` で、
測った特徴（正規表現 `r"【"` ＝ 位置を見ない）と別のものを門にしていました。
下の `帯の実物` は `data/niche_corpus.jsonl`（2026-09-05・ショート n=132）の実物で、
**末尾に置いた本が 3件**入っています。頭を強いると、この3件は落ちます。

    頭が【        n=36   0.82回/日（`【なし` の ×3.15）
    途中/末尾に【   n=19   5.93回/日（`【なし` の ×22.8）  ← 薄い升
    【なし        n=77   0.26回/日

**覆る条件**: 上の2つの升が両方 n≥20 になり、どちらかが他方の 2倍 を越えたら、
位置を門にしてよい（そのときこのファイルを書き換えること）。
`niche_ceiling.title_features('short')` の `【】` の倍率が 1.0 を割ったら、
門ごと落とすこと —— **語を足して通すのではなく、脚ごと落とす。**
"""
import re

import pytest

from src import script_writer as sw

#: 外の帯のショートの実物（`data/niche_corpus.jsonl` 2026-09-05）。**位置がばらばら**です。
帯の実物 = [
    ("【節税】「リアルタイムの質疑応答で理解できました」というご感想をいただきました！", "頭"),
    ("【報告】退職金が入ったよ。果たして金額はいくら！？", "頭"),
    ("退職金はいくらもらえる？学歴・企業規模別・退職金の平均相場【わかりやすく解説】", "末尾"),
    ("「倒れるまで働く」71歳年金世代のリアル【お給料いくら？】", "末尾"),
]

#: 自分のショートの実物（`data/uploaded.jsonl`・2026-09-05 時点で **552本 全部**がこの形）。
自分の題 = [
    "育休181日目 手取り比22.0614pt低下 #Shorts",
    "小規模企業共済 同じ840万円で税額3.46倍 #Shorts",
    "iDeCoの効きが落ちる年収は91点中11点 #Shorts",
]


@pytest.mark.parametrize("title,where", 帯の実物)
def test_帯の実物はどこに置いてあっても通ること(title, where):
    """**位置を門にしないこと。** 頭を強いると、末尾に置いた本が落ちます。"""
    assert sw.short_title_problems({"title": title}) == [], where


@pytest.mark.parametrize("title", 自分の題)
def test_自分のショートの題は全部この門で落ちること(title):
    """**0本／552本** —— 禁止が効いていた証拠を、検査として残します。"""
    problems = sw.short_title_problems({"title": title})
    assert len(problems) == 1
    assert "【 】" in problems[0]


def test_題が読めない回は何も言わないこと():
    """**推測で落とさないこと。** 題が空の台本は、別の検査の仕事です。"""
    assert sw.short_title_problems({"title": ""}) == []
    assert sw.short_title_problems({}) == []


def test_門は台本の検査に配線されていること():
    """**測るだけでは1本も変わりません**（`src/outside_short.py` が 09/05 に踏んだ形）。
    `short_script_problems` は `generate()` が直させる側と `pipeline` が落とす側の
    **唯一の正本**なので、そこから呼ばれていること自体を固定します。"""
    src = (sw.short_script_problems.__code__.co_names
           + sw.short_script_problems.__code__.co_consts)
    assert "short_title_problems" in sw.short_script_problems.__code__.co_names, src


def test_規則の本文が禁止をやめていること():
    """**文章と門が食い違うと、生成側が通したものを門が落とし続けます**
    （`short_script_problems` の docstring・2026-08-08〜09 に5回）。"""
    assert "【】は使わない" not in sw.ROLE
    assert "【 】を1つ入れること" in sw.ROLE


def test_測った特徴と門が同じものを見ていること():
    """`niche_ceiling.TITLE_FEATURES['【】']` は `r"【"` ＝ **位置を見ません。**
    門がそれより狭いと、`×5.52` を根拠に別のものを固定したことになります。"""
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(sw.__file__).resolve().parents[1] / "scripts"))
    import niche_ceiling as nc

    rx = re.compile(nc.TITLE_FEATURES["【】"])
    for title, where in 帯の実物:
        assert rx.search(title), title
        assert sw.short_title_problems({"title": title}) == [], where
