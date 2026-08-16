"""棒グラフの「起点」の単位（2026-08-16 に、独立評価が外から指した）。

## なにが起きていたか

棒の起点を0からずらしたとき、`_chart_html` は画面に1行そえます ——
**「※ 棒の起点は0ではなく 〇〇」**。その単位を `_fmt_axis` が
`display` の**末尾**から取っていました。ところが `display` には
数が2つ入ることがあります（実物 `vS6PGatxPQw` ／ iDeCo）:

    display = "6万2927円 実効22.8%"   value = 62927.0   base = 50000
    → 単位が "%" になり、画面には **「※ 棒の起点は0ではなく 50,000%」**

**棒の長さを決めているのは `value`＝円のほう**なので、この1行は嘘です。
独立評価の3体のうち**2体が別々にここを指しました**
（「単位が壊れていて、グラフの読み方そのものを疑う」「円と%の混在」）。
**機械検査は素通りしています** —— 起点の単位を見る検査が1つもありませんでした。
`verify.py` は「指示どおり折ったか」しか見ないので、この形は目視でも出ません
（**注記の中の1語**で、絵としては何も壊れて見えない）。

## ついでに出たもの

上を直す途中で、**前からある欠陥**が実物で出ました。

    _fmt_axis(120000, "12万円") → **"12万万円"**

`_axis_unit` が `"万円"` をまるごと単位として返し、下の「万」への書き換えが
もう一度 `万` を足します。**`display` が万どまりの丸い額のときだけ**出るので、
これまで誰も踏んでいませんでした。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import visuals


def test_数が2つある表示は最初のほうの単位を使う():
    """**これが本命。** 上から2つめの数（%）を拾うと 50,000% になります。"""
    got = visuals._fmt_axis(50000.0, "6万2927円 実効22.8%")
    assert got == "5万円", got
    assert "%" not in got


def test_ふつうの円():
    assert visuals._fmt_axis(50000.0, "35万9318円") == "5万円"
    assert visuals._fmt_axis(5500.0, "8万3959円") == "5,500円"


def test_割合はそのまま():
    assert visuals._fmt_axis(30.0, "73.5%") == "30%"


def test_桁の字を単位に数えない():
    """`"12万円"` の単位は `円` です。`万円` と読むと万が二重になります。"""
    assert visuals._fmt_axis(120000.0, "12万円") == "12万円"


def test_図の注記に単位ちがいが出ない():
    """`_chart_html` を通しで見る（**呼ぶ側で組み直していないこと**の確認）。"""
    html = visuals._chart_html(
        {
            "kind": "chart",
            "bars": [
                {"label": "年収660万", "value": 62927.0, "display": "6万2927円 実効22.8%"},
                {"label": "年収680万", "value": 78242.0, "display": "7万8242円 実効28.3%"},
            ],
            "scale_base": 50000,
        },
        portrait=True,
    )
    # **「注記が出ていること」を先に立てる。** ここを `if` で包むと、
    # 起点の行が出なくなった日に**緑のまま素通り**します（§4 の「0件で通る検査」）。
    assert "棒の起点は0ではなく" in html
    note = html.split("棒の起点は0ではなく", 1)[1].split("<", 1)[0]
    assert "%" not in note, note
    assert "円" in note, note
