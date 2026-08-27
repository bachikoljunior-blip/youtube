"""対照は**1回の半分まで**しか作られない。その差を黙って落とさないこと。

## この検査が守っているもの（2026-08-27 に踏んだ）

`batch_build` の出力は、`opening_motion` の対照について**同じ段落で
2つの数**を言っていました。実測（`--count 2` の回）:

    [batch] **1 本を `opening_motion` の対照（動きなし）で作ります**
            —— 対照(動きなし) 期限に間に合う 6本 … 床 8本 → **あと 2本** …
            → **この回で作るのは 2本**

**1 と 2 が同じ行にあります。** 頭の `1` は `motion_plan()` の答え
（`off = min(need, max(1, n // 2))` ＝ **1回の半分まで**）、
末尾の `2` は `motion_shortfall()` の答え（＝盤面が要る本数）。
読んだ側は「2本 埋まった」と思うが、**床はまだ 1本 空いたまま**残ります。

`opening_motion` は 2026-08-27 時点で **判定できる日が1つも出ていない**
唯一の前提（`python -m src.judgeable`「対照(動きなし) **そろいません**」）で、
かつ腕は `per_video`（天井 ×3.18・**実測**）。**そこを 1本 取りこぼす**のは、
到達日を動かす唯一の道（前提を1件閉じる）を1周ぶん遅らせます。

**半分までの門そのものは正しい**（同じ JST 日に両群が居ないと
`motion_groups.paired()` が標本に数えない）。直すのは印字のほうです。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build  # noqa: E402


def test_半分までしか対照にしない() -> None:
    """**門そのもの**（変えるなら `paired()` の側を先に見ること）。"""
    assert batch_build.motion_plan(2, shortfall=(2, "")).count(False) == 1
    assert batch_build.motion_plan(4, shortfall=(2, "")).count(False) == 2
    assert batch_build.motion_plan(1, shortfall=(2, "")).count(False) == 1


def test_足りているときは全部_処置のまま() -> None:
    assert batch_build.motion_plan(3, shortfall=(0, "")) == [True, True, True]


def test_取りこぼしを黙らせない() -> None:
    """`need > 実際に作る本数` の回は、**その差を印字する**こと。

    印字そのものは `run_batch` の中なので、ここでは**その1行が
    ソースに在ること**と、`--count` の助言が
    **`2 * need`**（半分までの門をちょうど越える数）であることを固定します。
    """
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    assert "この回では作りません" in src
    assert "--count {2 * _need}" in src


def test_足りない本数は_need_と_n_off_の差で出す() -> None:
    """**差を別々に数え直さないこと。**

    `_need`（`motion_shortfall`）と `n_off`（`motion_plan`）の**引き算**で
    出すこと。3つ目の数え方を足すと、食い違う口がもう1つ増えます。
    """
    src = (ROOT / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    assert src.count("_need - n_off") >= 1
