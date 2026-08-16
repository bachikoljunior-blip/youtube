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


def test_空白なしで数が2つ並ぶ表示_年金の歳とか月():
    """**16:0x の直しが届かなかった形**（2026-08-16 18:5x に実物で踏んだ）。

    `AoBABYXSUas`（8/31 13:00 予約）の実データそのもの ——
    棒は `82歳10か月` / `86歳3か月`、`value` は年の小数、`scale_base` は 81.0。
    `display.split()[0]` は**空白が無いので display 全体**を返し、
    末尾から拾って **「※ 棒の起点は0ではなく 81か月」** になっていました。
    棒が83歳あたりなのに、起点だけ6年9か月です。
    """
    assert visuals._fmt_axis(81.0, "82歳10か月") == "81歳"
    assert visuals._fmt_axis(81.0, "86歳3か月") == "81歳"
    # 空白のある形（16:0x の本命）も、同じ道で通り続けること
    assert visuals._fmt_axis(50000.0, "6万2927円 実効22.8%") == "5万円"


def test_最初の数の単位を取る_単体():
    assert visuals._first_unit("35万9318円") == "円"
    assert visuals._first_unit("82歳10か月") == "歳"
    assert visuals._first_unit("73.5%") == "%"
    assert visuals._first_unit("1,234円") == "円"
    assert visuals._first_unit("6万2927円 実効22.8%") == "円"
    assert visuals._first_unit("0.856") == ""
    # 桁の字は、**うしろに数が続くときだけ**数の一部
    assert visuals._first_unit("12万円").lstrip("万億千") == "円"


def test_図の注記に歳とか月が混ざらない():
    """通しで見る（**呼ぶ側で組み直していないこと**）。上の単体だけだと素通りします。"""
    html = visuals._chart_html(
        {
            "kind": "chart",
            "bars": [
                {"label": "額面", "value": 82.83, "display": "82歳10か月"},
                {"label": "手取り", "value": 86.25, "display": "86歳3か月"},
            ],
            "scale_base": 81.0,
        },
        portrait=True,
    )
    assert "棒の起点は0ではなく" in html
    note = html.split("棒の起点は0ではなく", 1)[1].split("<", 1)[0]
    assert "か月" not in note, note
    assert "歳" in note, note
