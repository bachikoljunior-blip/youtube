"""**「動かせる側」と言うなら、その側の天井も同じ行に出すこと。**

`scripts/eta.py` の段2 は、長尺の再生が合格点に届かないとき
「同じ不足を面の側で閉じるなら…**そちらは動かせる側です**（族の数）」と印字します。
**同じ走りの下のほう**には `src/day_cap.long_form()` の実測が出ています ——
「長尺の面: 7本/日 で崩れました → **上限は 6本/日**」。

実測 2026-08-30: 要る **34.5本/日** 対 天井 **6本/日** ＝ **5.75倍**。
**2行は同じ出力の中にあり、どこにも繋がっていませんでした。**
そして直近の ship は2件とも長尺の族と長尺の予約でした
（`data/runs.jsonl` 08/30 01:58／02:12）。

**天井は動かせます**（`day_cap.long_form()` の覆る条件）。
だから断りは「無理」ではなく「先に天井を測り直す前提が要る」です。

**覆る条件**: 天井が要る本数を上回ったら、この断りは自分で消えます。
そのとき**この検査も落ちる**ので、そこで畳むこと。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_族の数と天井が同じ行に並ぶ() -> None:
    out = subprocess.run([sys.executable, "scripts/eta.py"],
                         cwd=ROOT, capture_output=True, text=True, timeout=900).stdout
    if "そちらは動かせる側です" not in out:
        return          # その段に入らない回（面が足りている／CTR が縛っている）
    from src import day_cap
    lf = day_cap.long_form()
    if not lf.get("collapsed"):
        return          # まだ崩れを観測していない ＝ 天井が測れていない
    assert "その「動かせる側」にも、測った天井があります" in out, (
        "段2 が族を名指ししているのに、`day_cap.long_form()` の上限が"
        "同じ行に出ていません。**2か所が別々に言っている形です。**")
    assert "族を増やしても、この段は族では閉じません" in out
