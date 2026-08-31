"""**予約済みの長尺を前へ詰める割り当て**（`reschedule.long_pack_plan`）。

## なぜ要るか

**4,000時間の門に入るのは長尺だけ**です（`src/levers.py`／`src/day_cap.py`）。
ショートは再生の 99.9% を取りますが（実測 2026-08-26・直近28日:
`SHORTS_FEED` 64,283再生 ／ `WATCH` 67再生）、**その門には1分も積みません。**

実測 2026-08-26: 長尺 28本 が 08/26〜10/10 の **21日** に散っていました
（1.3本/日）。作る側は 08/25 だけで 25本 出しています ——
**散らしていたのは置き方だけ**（`slots()` が同じ時刻を count 回 返し、
`next_publish_at()` が「その時刻で最初に空いている**日**」を返すため）。
詰め直すと **最後の1本が 10/10 → 09/01（39日 早い）**・前倒しの合計 369日。

## ここが壊れたと分かる形

後ろへ下がる本が出たら、途中で止まった回が**もう一度走らせても
同じ割り当てにならない**（`compact_plan` と同じ不変条件）。
1日の本数が実測の上限を超えたら、**測っていない天井を黙って測りにいきます。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import reschedule  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 8, 26, 10, 0, tzinfo=JST)


def _row(vid: str, at: datetime, topic: str = "t") -> dict:
    return {"id": vid, "topic": topic,
            "at": at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def _spread(n: int, start_day: int = 28) -> tuple[list[dict], dict[str, float]]:
    """長尺 n本 を、**1日1本ずつ**（いまの散り方）並べる。"""
    rows, dur = [], {}
    for i in range(n):
        vid = f"L{i:02d}"
        rows.append(_row(vid, datetime(2026, 8, start_day, 20, 0, tzinfo=JST)
                         + timedelta(days=i)))
        dur[vid] = 300.0
    return rows, dur


def test_packs_one_per_day_into_five_per_day():
    rows, dur = _spread(10)
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5)
    days = {p["new"].date() for p in plan}
    assert len(plan) >= 5, "1日1本のままです"
    assert max(sum(1 for p in plan if p["new"].date() == d) for d in days) <= 5


def test_never_moves_a_book_later():
    """**後ろへは下げないこと。** 途中で止まっても割り当てが変わらないため。"""
    rows, dur = _spread(12)
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5)
    assert plan
    for p in plan:
        assert p["new"] < p["old"], f"{p['id']} が後ろへ下がっています"


def test_never_lands_on_a_taken_slot():
    """**埋まっている枠は使わないこと**（ショートの枠も含めて）。"""
    rows, dur = _spread(6)
    busy = datetime(2026, 8, 28, 20, 0, tzinfo=JST)
    rows.append(_row("SHORT1", busy))
    dur["SHORT1"] = 45.0                       # ショート（詰める対象ではない）
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5)
    assert all(p["new"] != busy for p in plan), "ショートの枠へ重ねています"
    assert all(p["id"] != "SHORT1" for p in plan), "ショートを動かしています"


def test_shorts_are_never_touched():
    """ショートだけの控えでは、**1本も動かさないこと**。"""
    rows, dur = [], {}
    for i in range(8):
        vid = f"S{i}"
        rows.append(_row(vid, datetime(2026, 9, 1, 9, 0, tzinfo=JST) + timedelta(days=i)))
        dur[vid] = 45.0
    assert reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5) == []


def test_per_day_is_respected():
    """`per_day` を下げたら、**その本数を超えないこと**（崩れた日の作法）。"""
    rows, dur = _spread(9)
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=2)
    for d in {p["new"].date() for p in plan}:
        assert sum(1 for p in plan if p["new"].date() == d) <= 2


def test_targets_are_unique():
    """置き先が重ならないこと（重なると1本が上書きで消えます）。"""
    rows, dur = _spread(14)
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5)
    assert len({p["new"] for p in plan}) == len(plan)


def test_lead_min_is_respected():
    """**いまから `lead_min` より手前へは置かないこと**（YouTube が受けません）。"""
    rows, dur = _spread(10)
    plan = reschedule.long_pack_plan(rows, dur, now=NOW, per_day=5, lead_min=60)
    assert all(p["new"] > NOW + timedelta(minutes=60) for p in plan)
