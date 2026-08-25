"""**答えの行が出ていないコマに、式を置かない**（2026-08-16）。

実物 `s-souzoku-kosuu-1nin-sa-345` の1コマに、これが並んで出ました:

    A 子1人 基礎控除 4200万円                ← 見えている唯一の行
    4800万円 ＝ 3000万円 ＋ 600万円 × 3人       ← 式

**台本は正しい。** `items` は2行あり、式はその2行目のことを言っています。
**壊したのは `reveal_variants`** で、`dict(visual)` が式ごと全コマに配り、
**答えの行が出る前のコマにも同じ式を置いていました。**

画面だけを見ると **4200 と 4800 が矛盾して見えます。**
この動画の根幹は「視聴者が自分で追試できること」なので、
**追試すると合わない画面**は見栄えの問題ではなく、根幹そのものを崩します。

**なぜ機械で見張るか。** `_check_formula_shown` は台本を見ており、
**台本は正しいので永久に気づきません**（見た層と直す層のずれ。通算6回目）。
`kind=stat` の側は 8/15 に `first["formula"] = ""` で塞いであり、
**割るループにだけ守りが無い**という、片側だけ直した形でした。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.visuals import reveal_variants  # noqa: E402

# 実物そのまま（`build/s-souzoku-kosuu-1nin-sa-345/script.json` の3枚目）
REAL = {
    "kind": "compare",
    "headline": "基礎控除は人数で変わる",
    "stat": "", "note": "", "stat_source": "",
    "formula": "4800万円 ＝ 3000万円 ＋ 600万円 × 3人",
    "items": ["子1人 基礎控除4200万円", "子2人 基礎控除4800万円"],
    "headers": [], "rows": [], "bars": [],
}


def test_答えの行が出る前のコマには式を出さない():
    out = reveal_variants(dict(REAL), 3)
    assert out[0]["items"] == ["子1人 基礎控除4200万円"]
    assert not out[0].get("formula"), (
        "4200万円しか出ていないコマに『4800万円 ＝ …』が残っている。"
        "**画面上で矛盾します**"
    )


def test_答えの行が出たコマには式を残す():
    """**消しすぎないこと。** 根幹は「計算式を画面に出す」側にあります。"""
    out = reveal_variants(dict(REAL), 3)
    assert out[-1]["formula"] == REAL["formula"], \
        "全部出ているコマからも式が消えている（1本に1枚も式が無くなる）"
    assert "子2人 基礎控除4800万円" in out[-1]["items"]


def test_割らない本は素通りする():
    v = dict(REAL)
    assert reveal_variants(dict(v), 1)[0]["formula"] == REAL["formula"]


def test_左辺に数の無い式は判定しない():
    """`手取り ＝ 額面 − 控除` のような形を、誤って落とさないこと。"""
    v = dict(REAL)
    v["formula"] = "手取り ＝ 額面 − 社会保険料 − 税"
    out = reveal_variants(v, 3)
    assert out[0]["formula"] == v["formula"]


def test_桁区切りの有無で見落とさない():
    """台本は `4,800万円`、式は `4800万円` と書くことがあります。"""
    v = dict(REAL)
    v["items"] = ["子1人 基礎控除4,200万円", "子2人 基礎控除4,800万円"]
    out = reveal_variants(v, 3)
    assert not out[0].get("formula"), "桁区切りのせいで一致を取り逃している"
    assert out[-1]["formula"] == v["formula"], "桁区切りのせいで消しすぎている"


def test_棒グラフでも同じ守りが効く():
    v = {
        "kind": "chart", "headline": "給付日数", "stat": "", "note": "",
        "formula": "240日 ＝ 120日 ＋ 120日",
        "items": [], "headers": [], "rows": [],
        "bars": [{"label": "自己都合", "value": 120},
                 {"label": "会社都合", "value": 240}],
    }
    out = reveal_variants(v, 2)
    assert not out[0].get("formula"), "棒が1本しか出ていないコマに合計の式が残っている"
    assert out[-1]["formula"] == v["formula"]
