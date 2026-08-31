"""**途中で止まる前提の輪が、順番を持っていること。**

## なぜこの検査があるか（2026-09-01）

`scripts/refresh_thumbnail.py --missing` は控えに溜まったぶんを全部 押します
（実測 2026-09-01: **158本 ＝ 7,900単位**）。日枠は 10,000単位/日 で、
**同じ枠を池化（`scripts/pool_drain.py`・残り 13,617単位）と取り合います。**

この輪には門が3つ在り（`day_quota()` ／ `thumbnail_yield_to_schedule()` ／
`reserve_hold()`）、**輪の中でも1本ごとに訊きます** ——
つまり **途中で止まるのが普通**の輪です。

**それなのに、一覧は本IDのアルファベット順でした**
（`critique_queue.missing_thumbnail()` の `sorted(STASH.glob("*.json"))`）。
実測: 並べ替える前の先頭は `-19CJiICv_w`（公開 09/24）で、
**その日のうちに公開される `UIWHsypOPPg`（09/01 22:00 JST）は
158本 のどこか**でした。

**手順の側は「必ず `--video` を付けること」と書いていました。**
それは**撃つ側が思い出したときにしか効きません** ——
`batch_build.slots()` の一行:
「**人の記憶と手写しに依存する門は、この輪では毎回落ちる側**」。

**これは止める仕掛けではありません**（`CLAUDE.md`「作りに問題を見つけたら、
止めるのではなく直すこと」）。押す本数も条件も1つも変えていません。
**変えたのは順番だけ**です。

**覆る条件**: `missing_thumbnail()` 自身が公開時刻を持つようになったら、
並べ替えはあちらへ移すこと（2か所で並べないこと）。
"""
from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import refresh_thumbnail as rt  # noqa: E402

NOW = dt.datetime(2026, 9, 1, 0, 0, tzinfo=dt.timezone.utc)


def _row(vid: str) -> dict:
    return {"video_id": vid, "topic": vid, "thumb": None, "stashed_at": None}


def _t(day: int, hour: int = 0) -> dt.datetime:
    return dt.datetime(2026, 9, day, hour, tzinfo=dt.timezone.utc)


def test_まだ出ていない本が先に来る():
    """**サムネイルは、公開の山が来る前に載っていないと効きません。**

    `src/settle.py`: ショートは 48時間 で伸びきる（96.2%）。
    **3日前に出た本の山は、もう終わっています。**
    """
    rows = [_row("old"), _row("soon")]
    times = {"old": _t(1) - dt.timedelta(days=3), "soon": _t(1, 13)}
    got = [r["video_id"] for r in rt.order_by_publish(rows, times, now=NOW)]
    assert got[0] == "soon", (
        "もう出た本が先に来ています。**過去のほうが「早い」ので、"
        "1本の物差しで並べると必ずこうなります** —— 段を分けること")


def test_まだ出ていない本の中は_早い順():
    rows = [_row("c"), _row("a"), _row("b")]
    times = {"a": _t(1, 13), "b": _t(12), "c": _t(28)}
    got = [r["video_id"] for r in rt.order_by_publish(rows, times, now=NOW)]
    assert got == ["a", "b", "c"], got


def test_もう出た本の中は_新しい順():
    """**山が残っている順**。古い本ほど、押しても取り返せる再生が少ない。"""
    rows = [_row("old"), _row("new"), _row("mid")]
    times = {"old": _t(1) - dt.timedelta(days=9),
             "mid": _t(1) - dt.timedelta(days=3),
             "new": _t(1) - dt.timedelta(hours=6)}
    got = [r["video_id"] for r in rt.order_by_publish(rows, times, now=NOW)]
    assert got == ["new", "mid", "old"], got


def test_控えに時刻の無い本は最後():
    """**示せない本を先に押さないこと。**（`pool_drain.pool()` と同じ扱い）"""
    rows = [_row("unknown"), _row("known")]
    times = {"known": _t(28)}
    got = [r["video_id"] for r in rt.order_by_publish(rows, times, now=NOW)]
    assert got == ["known", "unknown"], got


def test_1本も落とさないこと():
    """**並べ替えであって、絞りではありません。**

    ここが「古い本を捨てる」に化けると、**サムネイルの無い本が
    一覧から消えて二度と拾われません**（`critique_queue.mark_thumbnail_set()`
    の註と同じ事故）。
    """
    rows = [_row(f"v{i}") for i in range(20)]
    times = {"v3": _t(5), "v7": _t(2)}
    got = rt.order_by_publish(rows, times, now=NOW)
    assert len(got) == len(rows)
    assert {r["video_id"] for r in got} == {r["video_id"] for r in rows}


def test_押す前に並べ替えていること():
    """**関数を足しただけで、呼ばれていない道**を塞ぐ。

    `order_by_publish()` が在っても `push_missing()` が呼ばなければ、
    実物の順番は1つも変わりません（この repo で一番多い壊れ方 ——
    「言っている所と、している所が別」）。
    """
    src = (ROOT / "scripts" / "refresh_thumbnail.py").read_text(encoding="utf-8")
    body = src[src.index("def push_missing("):]
    i = body.index("critique_queue.missing_thumbnail()")
    j = body.index("y = build(")
    assert "order_by_publish(" in body[i:j], (
        "`push_missing()` が一覧を取ったあと、押す前に "
        "`order_by_publish()` を呼んでいません"
    )
