"""`src/rule_per_video.tail_headroom()` の検査。**外へは1回も出ません。**

## なぜこの道具が要るか（2026-09-01・最適化の回）

`config/hypotheses.yaml` の「1本あたり再生の分布には硬い右端」は、
**立てた回が手で測った裾**（上位20本・Hill の α）を本文に書き置いています。
**書き置かれた数は、標本が入れ替わると黙って腐ります** ——
そしてその前提は、`eta.py` が毎周 名指しする腕 `per_video` の天井そのものを
「本数では動かない」と言い切る根拠になっています。**腐ったまま効き続けます。**

だから同じ測り方を関数にして、**判定の日に撃ち直せる**ようにしました。
この検査が見るのは3つ:

    1. 少ない標本では **黙って None**（幻の裾を出さない）
    2. 重い裾（Pareto α=1.2）と軽い裾（詰まった上位）を**区別できる**
    3. 台帳の本文が、その道具を**名指ししている**（配線が切れていないこと）
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from src import rule_per_video as rpv

ROOT = Path(__file__).resolve().parent.parent


def _rows(vals):
    return [(None, f"v{i}", int(v)) for i, v in enumerate(vals)]


def test_標本が足りなければ黙る():
    """**100本 に満たないと None。** 幻の裾を出すより、何も言わないほうが安全。"""
    assert rpv.tail_headroom(rows=[]) is None
    assert rpv.tail_headroom(rows=_rows([500] * 99)) is None


def test_重い裾と軽い裾を区別する():
    """**α が逆転しないこと。** ここが逆なら、前提の結論も逆になります。"""
    rnd = random.Random(20260901)
    # 重い裾（Pareto α=1.2）: 最大は本数で大きく伸びる
    heavy = _rows([100 * (1 - rnd.random()) ** (-1 / 1.2) for _ in range(400)])
    # 軽い裾（上限つき）: 上位が壁に詰まる
    light = _rows([min(1900, 100 * (1 - rnd.random()) ** (-1 / 6.0))
                   for _ in range(400)])
    h, l = rpv.tail_headroom(rows=heavy), rpv.tail_headroom(rows=light)
    assert h and l
    assert h["alpha"] < l["alpha"], (h["alpha"], l["alpha"])
    assert h["gain"] > l["gain"], (h["gain"], l["gain"])
    # **軽い裾で「本数を足せば天井が動く」と言わせないこと。**
    assert l["gain"] < 2.0, l["gain"]


def test_倍率は現在の最大を下回らない():
    """**`gain` は「n → n+ahead」の伸び**なので、必ず 1.0 以上。

    分位そのもの（`vals[k] * ((n+ahead)/k)^(1/α)`）で出していた版は、
    いまの最大が裾の典型より上に居る回に **×0.96** を返しました。
    「本数を足すと天井が下がる」は読み方の誤りで、外れた値のせいです。
    """
    rnd = random.Random(7)
    rows = _rows([100 * (1 - rnd.random()) ** (-1 / 4.0) for _ in range(300)])
    t = rpv.tail_headroom(rows=rows)
    assert t and t["gain"] >= 1.0
    assert math.isclose(t["proj"], t["max"] * t["gain"], rel_tol=1e-9)


def test_台帳がこの道具を名指ししている():
    """**撃たれない道具の効果はゼロ。** 前提の本文から切れていないことを見る。"""
    y = (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8")
    assert "1本あたり再生の分布には硬い右端" in y, \
        "前提そのものが消えています（この道具は、その前提を撃ち直すために在ります）"
    assert "tail_headroom" in y, (
        "前提の本文が `tail_headroom()` を名指ししていません。"
        "**手で測った裾の数を本文に書き置いたままにしないこと** —— "
        "標本が入れ替わると黙って腐り、腐ったまま `per_video` の天井を決めます")
