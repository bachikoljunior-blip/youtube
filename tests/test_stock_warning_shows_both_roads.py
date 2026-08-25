"""**在庫が尽きかけている警告が、安いほうの道を隠していないか**（2026-08-26）。

`status.py` の在庫の節には、未使用の節の数で3つの枝があります。

    n_free == 0    「余地がありません」 → `_print_deepening`（**(A) と (B) の両方**）
    n_free  < 5    「残りN件です」      → **ここが (A) しか言っていませんでした**
    それ以外       「余地のある calc: …」

**0件の側は 2026-08-17 に直っています** —— 「増やす道は1つだけ ＝ 新しい表を書く」
は嘘で、**既にある表に節を足す道**があり、そちらは題材の作り直しが要らない
（`src/section_depth.py` の冒頭。実測で (A) は直近8回のうち7回いちばんの時間食い・
20〜25分、(B) は10〜15分）。

**その手前で鳴るほうは、直された事実を知らないまま残っていました。**
実測（2026-08-26 05:2x）: `n_free=3` でこちらに落ち、出た指示は「表を足すこと」だけ。
**早く鳴る警告のほうが、安い道を隠している**という形です。
`n_free` は 0 に向かって減るので、**こちらが先に鳴ります** ——
つまり **(B) を知らせる機会は、いつもこちらが先に潰していました。**

ここが落ちたら、`status.py` の `elif n_free < 5:` の枝から
`_print_deepening` が消えたか、(A) だけを名指しする文が戻ったということです。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
STATUS = ROOT / "scripts" / "status.py"


def _stock_branch() -> str:
    """在庫の3つの枝（`if n_free == 0:` から次の節まで）を切り出す。"""
    src = STATUS.read_text(encoding="utf-8")
    start = src.index("if n_free == 0:")
    end = src.index("if n_pick < 8 and n_free > 0:", start)
    return src[start:end]


def _nearly_empty_branch() -> str:
    """`elif n_free < 5:` の枝だけ。**ここが直した先です。**"""
    branch = _stock_branch()
    start = branch.index("elif n_free < 5:")
    end = branch.index("\n    else:", start)
    return branch[start:end]


def test_尽きかけの枝も両方の道を出す():
    """**`_print_deepening` を呼ぶこと。** (B) の候補はそこにしかありません。"""
    assert "_print_deepening" in _nearly_empty_branch(), (
        "`n_free < 5` の枝が `_print_deepening` を呼んでいません。"
        "**(B)（既にある表に節を足す）が、いちばん安いのに出ません。**"
    )


def test_0件の枝も両方の道を出す():
    """2026-08-17 に直った側。**こちらを壊さずに直したことの確認です。**"""
    branch = _stock_branch()
    zero = branch[:branch.index("elif n_free < 5:")]
    assert "_print_deepening" in zero


def test_尽きかけの枝が_新しい表だけを名指ししない():
    """**「表を足すこと」だけを指示に出さない。**

    (A) は2つのうち高いほうです。**名指しするなら両方**、
    でなければ道具（`_print_deepening`）に出させること。
    """
    branch = _nearly_empty_branch()
    # 実際に印字される文字列だけを見る（コメント行の説明は数えない）
    printed = "".join(re.findall(r'"([^"]*)"', branch))
    if "src/calc/" in printed and "表を足す" in printed:
        assert "節を足す" in printed, (
            "尽きかけの警告が「`src/calc/` へ表を足すこと」＝ (A) だけを"
            "名指ししています。**(B) のほうが安い**（実測 20〜25分 対 10〜15分）ので、"
            "ここで (A) に倒すと、その回の半分が題材の作り直しに消えます。"
        )


def test_3つの枝が全部ある():
    """故障注入。**枝そのものが消えたら、上の検査は素通りします。**"""
    branch = _stock_branch()
    for needle in ("if n_free == 0:", "elif n_free < 5:", "\n    else:"):
        assert needle in branch, f"在庫の枝 {needle!r} が消えています"


def test_しきい値は0より上にある():
    """**尽きてから鳴る警告には値打ちがありません。**

    `n_free < 5` の 5 を 1 まで下げると、鳴った回にはもう
    `topic_forge` が空振りしています。**手前で鳴ることが、この枝の存在理由**です。
    """
    m = re.search(r"elif n_free < (\d+):", _stock_branch())
    assert m, "`elif n_free < N:` の形が変わっています"
    assert int(m.group(1)) >= 2, (
        "尽きかけの線が低すぎます。**気づいたときには尽きています。**"
    )


@pytest.mark.parametrize("counts,expect", [
    ({"a": 2, "b": 5, "c": 9, "d": 13}, True),   # 浅い表があれば候補が出る
    ({"a": 9, "b": 9, "c": 9, "d": 9}, False),   # 横一線なら「あと何節」は出ない
])
def test_候補の中身が実物から出ている(counts, expect):
    """**`_print_deepening` を呼ぶだけでは足りません。**

    呼び先が空を返すなら、警告は結局 (A) しか言っていないのと同じです。
    """
    from src import section_depth

    mods = {m: {f"=== {m}{i} ===": "" for i in range(n)}
            for m, n in counts.items()}
    rows = section_depth.candidates(mods)
    assert bool(rows) is expect
