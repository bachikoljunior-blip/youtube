"""**帯の外に居る本を、同じ日の帯へ入れ直す手**（`live_slots.plan_band`）の検査。

## なぜ要るか（2026-08-29・最適化の回。**実測で見つけた**）

`live_slots.plan_all()` は `same_day_first=False` で走り、理由をこう書いていました ——
「同じ日へ動かしても、別の1本を押し出すだけで**生きる本は増えません**」。

**その「増えません」が成り立つのは (A) を真としたときだけ**です。
`board.live()` ＝ `day_cap.live_ids()` が実装しているのは
**(A)「その日の先頭 `cap()` 本」だけ**で、帯（09:00〜13:30）を1文字も見ていません。
`day_cap.window()` は **(A)/(B) をまだ切り分けていません**（`confounded`）。

実測（この検査を足した回・控えの予約ぶん）:

    (A) で生きている本            446本
    **そのうち帯の外に居る本      78本**   ← (B) なら全部 0再生
    同じ日の帯に空き分があった本   78本   ← **全部 入る**
    入れ直したあとの (A) の生存数  446本  ← **±0。押し出していません**

## この検査が守るもの（**赤くなったら、直すのは実装のほう**）

1. **(A) の生存数を減らさない**（減らす手は撃たない ＝ 賭けにしない）
2. **置き先は必ず帯の中・同じ日**（別の日へ跳ばすのは `plan_all()` の仕事）
3. **測定の窓の日には触らない**（`measure_window`）

**覆る条件**: `day_cap.window()` が **(A)** と決めたら、`plan_band` ごと要りません
（この検査も一緒に消すこと）。**(B)** と決まったら、直す先は
`plan_all()` の `same_day_first=False` のほうです。
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from scripts import live_slots as ls
from src import day_cap, measure_window

JST = dt.timezone(dt.timedelta(hours=9))
GRID = set(ls.GRID)


def _board(rows: list[dict], now: dt.datetime) -> ls.Board:
    b = ls.Board.__new__(ls.Board)
    b.at = {r["video_id"]: r["at"] for r in rows}
    b.now = now
    b.cap = day_cap.cap()
    b.moves = []
    return b


def _row(vid: str, day: str, hhmm: str) -> dict:
    h, m = (int(x) for x in hhmm.split(":"))
    return {"video_id": vid,
            "at": dt.datetime.fromisoformat(day).replace(hour=h, minute=m, tzinfo=JST)}


def _free_day() -> str:
    """**測定の窓に当たらない日**を1つ選ぶ（窓は実物から動きます。日付を書かないこと）。"""
    day = dt.date(2026, 9, 5)
    for _ in range(60):
        if not measure_window.inside(day.isoformat()):
            return day.isoformat()
        day += dt.timedelta(days=1)
    raise AssertionError("窓に当たらない日が60日 見つかりません")


def test_帯の外の本が同じ日の帯へ入る():
    """(A) では生きているのに帯の外に居る本を、**同じ日の空き分**へ入れ直す。"""
    day = _free_day()
    rows = [_row("a", day, "09:00"), _row("b", day, "09:30"), _row("c", day, "18:00")]
    now = dt.datetime.fromisoformat(day).replace(tzinfo=JST) - dt.timedelta(days=2)
    board = _board(rows, now)
    assert "c" in board.live(), "前提: (A) では 3本とも生きている"
    assert len(ls.band_stray(board)) == 1, "帯の外に居るのは c の1本のはず"

    ls.plan_band(board)
    assert [v for v, _ in board.moves] == ["c"]
    when = board.at["c"]
    assert when.date().isoformat() == day, "**別の日へ跳ばさないこと**"
    assert when.hour * 60 + when.minute in GRID, "置き先が帯の中ではありません"


def test_生きている数を減らす手は撃たない():
    """門は1つ ——**1手ごとに数え直して、減ったら戻す。**"""
    day = _free_day()
    cap = day_cap.cap()
    # 帯をちょうど埋めて、そのうえで帯の外に1本 置く（＝入れ替えしか起きえない形）
    rows = [_row(f"v{i}", day, f"{9 + i // 2:02d}:{'30' if i % 2 else '00'}")
            for i in range(cap)]
    rows.append(_row("late", day, "18:00"))
    now = dt.datetime.fromisoformat(day).replace(tzinfo=JST) - dt.timedelta(days=2)
    board = _board(rows, now)
    before = len(board.live())
    ls.plan_band(board)
    assert len(board.live()) >= before, "**生きている本を減らす手を撃っています**"


def test_測定の窓の日には触らない():
    """**窓は実物から引くこと**（日付を書くと、窓が動いた回に赤くなります）。"""
    day = None
    probe = dt.date.today()
    for _ in range(120):
        if measure_window.inside(probe.isoformat()):
            day = probe.isoformat()
            break
        probe += dt.timedelta(days=1)
    if day is None:
        pytest.skip("これから120日 に測定の窓がありません")
    rows = [_row("a", day, "09:00"), _row("b", day, "18:00")]
    now = dt.datetime.fromisoformat(day).replace(tzinfo=JST) - dt.timedelta(days=2)
    board = _board(rows, now)
    assert ls.band_stray(board) == [], "**窓の日の本を動かす候補に入れています**"
    ls.plan_band(board)
    assert board.moves == []


def test_枠を測っているABの本には触らない():
    """`ab_split.slot_half` は**帯の中のどの枠に置くか**を測っている。

    こちらが枠を動かすと、**その実験が測っている当のものを壊します。**
    落とすのは `landed` より後に**作った**本だけ（公開日ではない）。
    """
    from src import ab_split
    exp = ab_split.EXPERIMENTS.get("slot_half")
    if exp is None:
        pytest.skip("slot_half は閉じています（この門はもう要りません）")
    board = ls.Board(ls._rows())
    skip = ls._slot_ab_cohort(board)
    stray = set(ls.band_stray(board))
    assert not (skip & stray), (
        "**枠を測っている A/B の本を、動かす候補に入れています。**"
        f"{sorted(skip & stray)[:5]}")


def test_batch_buildの3段目が2段目の早い_return_で飛ばされない():
    """**(2) に手が無い回は平常の姿**（逃がし終えた状態）。そこで (3) を落とさないこと。

    最初に書いたときは枠の門を (2) の中に埋めていて、
    `gain <= 0 or not board.moves` の `return` が **(3) ごと飛ばして**いました。
    **門は (2) と (3) の手前に1回**。
    """
    src = (Path(__file__).resolve().parent.parent
           / "scripts" / "batch_build.py").read_text(encoding="utf-8")
    body = src.split("def _rescue_dead_slots", 1)[1].split("\ndef ", 1)[0]
    gate = body.index("quota_lines")
    gain = body.index("gain = len(board.live()) - was")
    band = body.index("plan_band(")
    assert gate < gain < band, (
        "枠の門が (2) の中に戻っています。**(2) に手が無い回に (3) が走りません**")
    assert "plan_band(board, limit=_RESCUE_MAX)" in body, (
        "(3) が `_RESCUE_MAX` で切られていません（1回で日枠を持っていきます）")


def test_実物でも生存数が減らない():
    """**控えの実物**で回して、(A) の生存数が落ちないこと（この手の値打ちの根）。"""
    board = ls.Board(ls._rows())
    before = len(board.live())
    ls.plan_band(board)
    assert len(board.live()) >= before, (
        "実物で生存数が減りました。**撃たないこと** —— 門（1手ごとの数え直し）が"
        "効いていないか、`day_cap.live_ids` の読み方が変わっています")
    for vid, when in board.moves:
        assert when.hour * 60 + when.minute in GRID
        assert not measure_window.inside(when.date().isoformat())
