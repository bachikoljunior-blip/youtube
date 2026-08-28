"""**`day_cap.live_ids()` は長尺を除きません。** いまは 0本 の差ですが、機構は在ります。

## なぜこの検査が要るか（2026-08-29）

`day_cap.by_day()` は既定で長尺を外します（`include_long=False`）——
あそこが測っているのは**ショートの面の上限**で、長尺は `SHORTS_FEED` の枠を
1つも使わないからです。**ところが `live_ids()` は外していません。**

08/29 05:4x の申し送り②が、これを名指ししていました:

    **`day_cap.live_ids()` は長尺を除きません。** この回は `eta.py` の側で
    先に `_long_ids` を引いてから渡しています。**`live_ids()` 自体に
    `include_long=False` を入れるほうが正しい**（`by_day()` は既定でそうしています）。
    他の呼び手（`live_lines` / `scripts/live_slots.py`）が同じ穴を
    踏んでいないか、次の回が見ること。

**見ました。実測で差は 0本 です**（2026-08-29 07:5x・控えと公開済み 578本）:

    live_ids(全部)              **452本**
    live_ids(長尺を先に除く)     **452本**
    長尺が帯の枠を取っている数    **0本**
    そのせいで落ちたショート      **0本**

**だから既定は変えていません。** 意味の変わる直しを、0本 のために
`judgeable` / `deep_short` / `motion_groups` / `watch_eta` / `live_slots` /
`batch_build` の6つの呼び手へ同時に流すのは、割に合いません
（どれも A/B の標本の切り方に使っています）。

**ただし機構は在ります。** 長尺 11本 のうち **7本 が 9〜12時**、
つまり帯の中の時刻に公開されています。`_spaced` と `cap()` は
**形を見ずに時刻の早い順で切る**ので、長尺が帯の中へ寄れば、
そのぶんショートが `alive` から落ちます。**いま 0本 なのは、
その日の本数が上限に届いていない日にしか長尺が居ないからです。**

## この検査が落ちたときにやること

**落ちたら、そのときが直す回です。** `live_ids()` に
`include_long: bool = False` を足し、`by_day()` と同じ形で
`_long_ids()` を先に落とすこと。**そのとき6つの呼び手を全部 見ること** ——
標本が広がる向きなので、A/B の判定はどれも動きます。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_長尺が帯の枠を奪っていないこと():
    """奪いはじめたら落ちる。**そのときが `include_long` を足す回。**"""
    from src import day_cap
    from src.ab_split import published

    rows = [r for r in published() if r.get("at")]
    if not rows:
        pytest.skip("控えが読めません（データが無い環境）")
    longs = day_cap._long_ids()
    if not longs:
        pytest.skip("data/video_forms.json に長尺の分類がありません")

    keep_all = day_cap.live_ids(rows)
    keep_no_long = day_cap.live_ids(
        [r for r in rows if str(r.get("video_id") or "") not in longs])

    taken = keep_all & longs
    lost = keep_no_long - keep_all
    assert not taken, (
        f"長尺 {len(taken)}本 が、ショートの帯の枠を取っています。"
        "`day_cap.live_ids()` に `include_long=False` を足すこと"
        "（`by_day()` と同じ形）。**6つの呼び手を全部 見ること** —— "
        "judgeable / deep_short / motion_groups / watch_eta / live_slots / batch_build")
    assert not lost, (
        f"長尺のせいで、ショート {len(lost)}本 が帯から落ちています。"
        "`day_cap.live_ids()` に `include_long=False` を足すこと")
