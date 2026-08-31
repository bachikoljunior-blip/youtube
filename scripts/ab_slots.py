#!/usr/bin/env python3
"""**A/B の群の本は、再生が付く枠に入っているか。**（API は 0単位。読むのは控えだけ）

    python scripts/ab_slots.py

## なぜ要るか（2026-08-26 に実測して作った）

`src/ab_split.split_counts` は「16本そろったか」を**公開日だけ**で数えます。
**その本に再生が付くかは見ていません。**

そして再生が付く本数には上限があります（`src/day_cap.py`・実測 **10本/日**）。
このチャンネルは 1日 13〜30本 予約しているので、**その日の11本目から後ろは 0再生**です。
0再生の本は engaged 比率を持たないので、**判定の比較には入りません**
（どの `falsified_if` も「30再生以上」を要求します）。

つまり **「16本そろった」と数えながら、実際に比べるのは その一部**になります。
実測（2026-08-26・判定に入る最初の16本のうち、再生が付く枠にいる本）:

    title_form  問い **8本/16**（50%）  ／ 断定 14本/16（88%）
    hook_form   問い 14本/16（88%）     ／ 条件 **7本/16**（44%）

**片群 8本 は、床を 16 に上げる前の数です。** `src/ab_power.py` の実測では
1.3倍を当てる率が **8本 64% → 16本 76%**。**登録した力より低い賭けになります。**

**さらに悪いのは、偏りが群と相関していること**です。上の2件は
**別々の群が痩せています。** 痩せた群に残るのは「たまたま生きた枠に入った本」で、
生きた枠の本ばかりの群とは**配信の条件が違います。** 差が出ても出なくても、
それが「作りの差」なのか「枠の差」なのかを分けられません。

## 直し方（**この道具は撃ちません。数えるだけです**）

**入れ替え**です（`scripts/queue_lag.py` と同じ機構）——
痩せた群の本と、同じ日の 11本目以降にいる**実験外の本**の公開時刻を交換する。
**1日の本数も、時刻の埋まり方も変わりません。** 1手 50単位。

**08/27 には触らないこと。** その日は「上限は本数か、13:30 の時刻の窓か」を
測っている対照日です（`config/hypotheses.yaml`）。

## 覆る条件

- **`day_cap.cap()` が「本数」ではなく「時刻の窓」だと分かったら、数え方が変わります**
  （窓なら、順位ではなく **13:30 JST より前かどうか**で数えること）。
  答えが出るのは 09/01 ごろ
- **`MIN_PER_GROUP` を変えたら、ここの「最初の16本」も一緒に動きます**
"""
from __future__ import annotations

import collections
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import ab_split                                           # noqa: E402
from src import day_cap                                            # noqa: E402
from src.ab_split import EXPERIMENTS, MIN_PER_GROUP, build_times, published  # noqa: E402


def live_set(rows: list[dict] | None = None) -> set[str]:
    """**再生が付く側の `video_id`**。`src/day_cap.live_ids()` が1か所で決めています。

    ## ここで自前に数えないこと（2026-08-26 に合流したときに直した）

    この下の `slot_rank()` は「その日の何番目か」しか見ていませんでした。
    **`day_cap` の規則は2段**です ——
    (1) 間隔 30分 未満の本を落とす → (2) 残ったうちの先頭 `cap()` 本。

    **(1) が抜けていると、同じ分に2本入っている日で答えが割れます**
    （実物: 09/06 の 09:00/10:00/11:00 が各2本。順番だけで数えると両方が
    「10番目まで」に入って**2本とも生きている**ことになりますが、
    実際は少なくとも片方が死にます）。

    同じことを2か所が別々に数えるのは、このリポジトリで**14件目**です。
    **数えるのは `day_cap` の1か所だけ**にしました。
    """
    rows = published() if rows is None else rows
    return day_cap.live_ids([r for r in rows if r.get("video_id") and r.get("at")])


def slot_rank(rows: list[dict] | None = None) -> dict[str, int]:
    """`video_id` → **その日の何番目に公開されるか**（1始まり）。

    **順番を見せるためだけ**に残しています。**生きているかの判定に使わないこと** ——
    それは `live_set()`（＝ `day_cap.live_ids`）の仕事です。間隔の段が抜けています。
    """
    rows = published() if rows is None else rows
    by_day: dict[object, list[dict]] = collections.defaultdict(list)
    for r in rows:
        if r.get("publish") is not None and r.get("at") is not None:
            by_day[r["publish"]].append(r)
    out: dict[str, int] = {}
    for items in by_day.values():
        for i, r in enumerate(sorted(items, key=lambda x: x["at"])):
            out[str(r.get("video_id") or r.get("topic"))] = i + 1
    return out


def judging_set(exp, rows: list[dict] | None = None,
                builds: dict | None = None) -> dict[str, list[dict]]:
    """群 → **判定に入る最初の `MIN_PER_GROUP` 本**（公開の早い順）。"""
    rows = published() if rows is None else rows
    bt = build_times() if builds is None else builds
    out: dict[str, list[dict]] = {}
    for g in (exp.treated, exp.control):
        mine = []
        for r in rows:
            topic = str(r.get("topic") or "")
            # **凍らせた名札が勝ちます**（`src/ab_split.group_of`）。
            if r.get("publish") is None or ab_split.group_of(exp, topic) != g:
                continue
            built = bt.get(topic)
            if built is None or built < exp.landed:
                continue          # 指示より前に作った本は、この群の本ではない
            mine.append(r)
        mine.sort(key=lambda r: (r["publish"], r.get("at") or 0))
        out[g] = mine[:MIN_PER_GROUP]
    return out


def report() -> list[str]:
    cap = day_cap.cap()
    rows = published()
    live = live_set(rows)
    bt = build_times()
    out = [f"=== A/B の本は、再生が付く枠に入っているか（上限 {cap}本/日・"
           f"床 片群 {MIN_PER_GROUP}本）===",
           "  **`split_counts` は公開日だけで数えます。**上限より後ろの本は 0再生 ＝ "
           "比較に入りません"]
    for name, exp in EXPERIMENTS.items():
        out.append(f"  {name}")
        thin: list[tuple[str, int]] = []
        for g, items in judging_set(exp, rows, bt).items():
            if not items:
                out.append(f"    {g:12s} **まだ1本も予約に在りません**")
                continue
            n_live = sum(1 for r in items if str(r.get("video_id") or "") in live)
            mark = " ← **痩せています**" if n_live < MIN_PER_GROUP * 0.75 else ""
            out.append(f"    {g:12s} 最初の{len(items):2d}本 → 再生が付く枠 **{n_live:2d}本**"
                       f"（{n_live / len(items) * 100:3.0f}%）  {len(items)}本目の公開 "
                       f"{items[-1]['publish']}{mark}")
            thin.append((g, n_live))
        if len(thin) == 2 and min(t[1] for t in thin) < max(t[1] for t in thin) * 0.8:
            lo = min(thin, key=lambda t: t[1])
            hi = max(thin, key=lambda t: t[1])
            out.append(f"      → **群のあいだで枠の当たりが偏っています**"
                       f"（{lo[0]} {lo[1]}本 対 {hi[0]} {hi[1]}本）。"
                       f"差が出ても「作りの差」と「枠の差」を分けられません。"
                       f"**{lo[0]} の本を、同じ日の上限より後ろにいる実験外の本と"
                       f"入れ替えること**（`scripts/reschedule.py --move`・1手50単位。"
                       f"**08/27 には触らないこと** ——測定の対照日です）")
    return out


if __name__ == "__main__":  # pragma: no cover
    print("\n".join(report()))
