"""**予定表の θ は、どちらへ動けば「良い」のか。**（2026-08-27・最適化の回）

`docs/spawn_prompt.md` は 2026-08-27 に、この数を最適化の役の
**1周ごとの合否**にしました。ところが本物の台帳で当てると:

    いまのまま                          **0.786/日**（11件）
    前提を**1件 閉じた**あと            **0.714/日**（10件）  ← **−9.2%**
    中身の無い複製を**1件 足した**あと  **0.857/日**（12件）  ← **+9.1%**

**符号が逆です。** `eta.py` は毎回「軌跡の腕が動くのは**前提を1件閉じたとき
だけ**」と印字しています —— その唯一の手を撃つと採点器は**下がり**、
**中身を問わず1件 足すだけ**で同じ幅 上がる。

そして机上の話ではありません。同じ日に **0.64（9件）→ 0.71（10件）→
0.79（11件）** と上がり、**閉じた前提は 0件**でした（`closed_on` の最後は 08-26）。

この検査は「直った」ことを縛るものでは**ありません** ——
**この性質が在るあいだ、`drift.py` がそれを印字していること**を縛ります。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import drift as D  # noqa: E402

from src import arm_speed  # noqa: E402


def _doc(n_open: int) -> tuple[dict, dict]:
    """開いた前提 `n_open` 件（＋閉じたもの2件）と、その判定日の対応。"""
    today = date.today()
    hyps = [{"claim": f"c{i}", "deadline": str(today + timedelta(days=3))}
            for i in range(n_open)]
    hyps += [{"claim": f"z{i}", "closed_on": str(today - timedelta(days=i + 1)),
              "verdict": "survived"} for i in range(2)]
    ready = {f"c{i}": today + timedelta(days=3) for i in range(n_open)}
    return {"hypotheses": hyps}, ready


def _theta(n_open: int) -> float:
    doc, ready = _doc(n_open)
    fw = arm_speed.forward(ready, doc=doc)
    return next(h["per_day"] for h in fw["horizons"] if h["days"] == 14)


def test_前提を1件閉じると予定表のθは下がる():
    """**上がったら、`forward()` の分子が直ったということ。**

    そのときは `drift._forward_sign_lines()` の3行を外すこと
    （＝あの3行の「覆る条件」がこれです）。
    """
    before, after = _theta(11), _theta(10)
    assert after < before, (
        "予定表の θ が、前提を閉じても下がらなくなりました。"
        "`forward()` の分子が『開いた前提』から『決着の付く前提』へ直ったのなら、"
        "`drift._forward_sign_lines()` の3行と、この検査を外すこと")


def test_中身を問わず1件足すと予定表のθは上がる():
    assert _theta(12) > _theta(11)


def test_drift_がその向きを同じ画面に印字する():
    """**数だけ出して向きを出さないなら、読んだ回は上がったことを成果と読みます。**"""
    out = "\n".join(D._forward_sign_lines(11, 11 / 14))
    assert "0.71" in out and "0.86" in out, out
    assert "下がります" in out and "上がります" in out
    assert "在庫の数であって、閉じた速さではありません" in out


def test_件数が0なら黙る():
    assert D._forward_sign_lines(0, 0.0) == []
