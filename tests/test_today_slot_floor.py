"""**間隔の下限が、固定その4 の下で毎周 外れていました**（2026-09-04 07:0x に実測）。

## なぜ

`sibling_check --phase spawn` は「在庫が薄いときは、間隔の下限より生成を優先する」
（`RUNWAY_FLOOR_DAYS` ＝ 14日）を持っています。**8/16 に入れたときは正しい線**でした ——
当時は作り置きで、`runway_days()`（予約が何日先まで埋まっているか）は本当に在庫でした。

**固定その4**（オーナー原文「現在の日付にしか予約しないってことだからね？」）が入って、
`runway_days()` は**定義上 ≤1日**になりました。しかも `CLAUDE.md` はそれを
「**先の日付が空であることが、正しい状態です**」と書いています。

＝ **`runway < 14日` は毎周 真** → **間隔の下限は毎周 外れる。**
オーナーの「今までの最高速度の**二分の一**の速度でやって」（2026-09-02 18:4x）を
毎周 数え直している `quota.effective_floor_minutes()`（実測 101分）は、
**印字されるだけで、1度も効いていませんでした。** 実測の出力:

    在庫: 予約は **0.1日先**まで（下限を外す境目は 14日）
      → **間隔の下限 101分を外します。**在庫が薄いので、生成の回数のほうが目標に近い。

**この repo でいちばん多い壊れ方（言っている所と、している所が別）の、この行ぶんです。**

## 置き直した線

危ないのは「先が空なこと」ではなく **「きょうの枠がまだ空なこと」**です。
きょうの本が置かれていれば、その日の公開は続きます。置かれないまま日が暮れると、
**その日が丸ごと落ちます** —— そこだけが下限より重い。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sibling_check  # noqa: E402

from src import house_rule, next_slot  # noqa: E402


def test_きょうの枠が埋まっていれば空でないと答える(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_slot, "today_count", lambda now=None: 1)
    monkeypatch.setattr(house_rule, "cap", lambda: 1)
    assert sibling_check.today_slot_empty() is False


def test_きょうの枠が空なら空と答える(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(next_slot, "today_count", lambda now=None: 0)
    monkeypatch.setattr(house_rule, "cap", lambda: 1)
    assert sibling_check.today_slot_empty() is True


def test_読めなければ_None_で_下限はそのまま(monkeypatch: pytest.MonkeyPatch) -> None:
    """**計器が黙った回だけ、いちばん速く回る形にしないこと。**

    `None` は「読めなかった」で、呼ぶ側はそのとき**下限をそのまま効かせます**
    （`--phase spawn` の枝）。`False`（＝ 埋まっている）と混ぜないこと。
    """
    def _boom(now=None):
        raise RuntimeError("控えが読めない")
    monkeypatch.setattr(next_slot, "today_count", _boom)
    assert sibling_check.today_slot_empty() is None


def test_先の日付が空でも_それだけでは下限を外さない(monkeypatch: pytest.MonkeyPatch) -> None:
    """**固定その4 の下では、先の日付が空なのが正しい状態です。**

    ここが `runway_days()` を見ていたあいだ、下限は毎周 外れていました。
    """
    monkeypatch.setattr(next_slot, "today_count", lambda now=None: 1)
    monkeypatch.setattr(house_rule, "cap", lambda: 1)
    # 先の予約が 0本（＝ runway ≒ 0日）でも、きょうが埋まっていれば「空でない」
    assert sibling_check.today_slot_empty() is False
