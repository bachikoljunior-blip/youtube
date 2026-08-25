"""段階表示で**いま増えた要素そのもの**に印が付くこと（`reveal_new` / `fresh_flags`）。

## なぜ要るか（2026-08-16。**独立評価9体ぶんの実測**）

`reveal_variants` は表・棒・箇条書きを1つずつ足していく複数コマに割ります。
増えた要素は**見出し**にだけ出していました（`_reveal_headline` の「＋600万」）。
**それでは足りませんでした。** 同日に回した3本 × 3体 ＝ **9体が全員**、
別々の本について同じことを書いています:

    「同じ表に600万の行が1行足されるだけ。表以外は完全に同じ画面」
    「同じ表に3行足しただけで、これも実質同じ画面」
    「画面は『切り替わる』より『増える』で、スクロール中の目には止まって見えます」

`YhHeqMKql7U` は3体そろって **4/4/3点**（記録した中で最低）。

## 実測（`scripts/bake_slides.py`。同じ元の絵から、印だけを外して焼き比べた）

    組                    印なし    印あり
    表 ＋1行              5.11%  →  7.53%
    前提の表 最後の1行    4.49%  → 13.51%   ← **3.0倍**
    steps ＋1項目         5.87%  →  8.66%
    compare ＋1項目      11.31%  → 23.04%
    最小                  4.49%  →  7.53%

**この数字は「よくなった」の証拠ではありません**（8/15 22:0x が、画素差では
本物と偽物の順序が逆転することを実測しています）。**言えるのは「画面が
塗り替わる量が増えた」までで、engaged に効くかは仮説**です
（`config/hypotheses.yaml` に反証条件つきで登録しました）。

## 検査が押さえているもの

- **印は「増えたぶん」だけに付く**（全部に付いたら、動く強調にならない）
- **1コマ目には付かない**（そこは全部が新しいので、強調に意味がない）
- **最後のコマでも消えない**（`out[-1]` を組み直すところで落ちやすい）
- **`kind=stat`（冒頭）には掛からない** —— 9/5 判定の実験中で、触らない約束
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import visuals  # noqa: E402


def table(n: int) -> dict:
    return {"kind": "table", "headline": "所得割と上限額の対応",
            "headers": ["年収", "所得割"],
            "rows": [[f"{i}00万", f"{i}万円"] for i in range(1, n + 1)]}


def test_増えたぶんだけに印が付く():
    parts = visuals.reveal_variants(table(3), 3)
    assert [p["reveal_new"] for p in parts] == [0, 1, 1]
    # 印の位置＝各コマの**末尾**。次のコマでは1つ下へ移る
    assert visuals.fresh_flags(parts[1], 2) == [False, True]
    assert visuals.fresh_flags(parts[2], 3) == [False, False, True]


def test_一コマ目には印が付かない():
    """**そこは全部が新しい。** 全行を光らせたら、動く強調になりません。"""
    parts = visuals.reveal_variants(table(3), 3)
    assert visuals.fresh_flags(parts[0], 1) == [False]


def test_最後のコマでも印が消えない():
    """`out[-1] = dict(visual)` で組み直すところ。**落ちやすい1行**です。

    落ちると `k=2`（割った2枚）のとき、**印の付くコマが1枚も無くなります。**
    """
    parts = visuals.reveal_variants(table(2), 2)
    assert parts[-1]["reveal_new"] == 1
    assert visuals.fresh_flags(parts[-1], 2) == [False, True]


def test_二つ以上まとめて増えた回はまとめて光る():
    """要素が多くて枚数が少ないと、1コマで2つ増えます。**両方に付くこと。**"""
    parts = visuals.reveal_variants(table(4), 2)
    assert parts[1]["reveal_new"] == 2
    assert visuals.fresh_flags(parts[1], 4) == [False, False, True, True]


def test_割らない回には印が無い():
    """1枚のままなら、比べる相手がいないので印は要りません。"""
    (only,) = visuals.reveal_variants(table(3), 1)
    assert only.get("reveal_new", 0) == 0


def test_stat_には掛からない():
    """**冒頭は 9/5 判定の実験中。** ここに印が入ると実験の条件が変わります。"""
    v = {"kind": "stat", "headline": "手取り", "stat": "30万3000円",
         "note": "年収600万・給与のみ"}
    for part in visuals.reveal_variants(v, 2):
        assert part.get("reveal_new", 0) == 0
        # **CSS には `.fresh` が必ず出ます**（配色は全コマ共通）。
        # 見るのは**要素に付いたか**のほう。ここを間違えると、
        # 「掛かっていない」を確かめたつもりで CSS を見ることになります。
        html = visuals.build_html(part, portrait=True)
        assert 'class="fresh"' not in html and "bar-row fresh" not in html


def test_表の画面に印が出る():
    parts = visuals.reveal_variants(table(3), 3)
    html = visuals.build_html(parts[2], portrait=True)
    assert html.count('<tr class="fresh">') == 1
    assert "tr.fresh td" in html       # CSS 側も入っていること（印だけあって無地は無意味）
    # 印の無いコマには出ない（**片側だけ検査しないこと**）
    assert '<tr class="fresh">' not in visuals.build_html(parts[0], portrait=True)


def test_箇条書きの画面に印が出る():
    v = {"kind": "steps", "headline": "調べ方",
         "items": ["通知書を開く", "所得割の欄を見る", "上限を確かめる"]}
    parts = visuals.reveal_variants(v, 3)
    assert visuals.build_html(parts[2], portrait=True).count('<li class="fresh">') == 1


def test_棒グラフの画面に印が出る():
    v = {"kind": "chart", "headline": "年収べつ",
         "bars": [{"label": f"{i}00万", "value": i * 1000.0, "display": f"{i}千円"}
                  for i in (1, 2, 3)]}
    parts = visuals.reveal_variants(v, 3)
    assert visuals.build_html(parts[2], portrait=True).count('bar-row fresh') == 1


def test_印の数が要素の数を超えない():
    """壊れた `reveal_new` を渡されても、はみ出さないこと。"""
    assert visuals.fresh_flags({"reveal_new": 99}, 2) == [True, True]
    assert visuals.fresh_flags({"reveal_new": -3}, 2) == [False, False]
    assert visuals.fresh_flags({}, 2) == [False, False]
