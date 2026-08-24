"""**同じ分に2本置いてしまうのを、共有の状態なしで避けられているか。**

2026-08-25。控えは**そのコンテナの中にしか無い**ので、同じ回に走っている
きょうだいが今しがた置いた本は見えません（`git` で配られるのは push のあと）。
実測: 08/27 に5組・09/06 に3組が同じ分に入っていました。

ここで検査するのは1つだけです ——
**控えが同じでも、車線が違えば同じ分を選ばないこと。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.batch_build import slots  # noqa: E402
from src import lanes  # noqa: E402

GRID = list(range(9 * 60, 24 * 60, 30))


def test_lane_is_stable_for_the_same_id() -> None:
    """**同じIDなら毎回同じ車線。** `hash()` だとプロセスごとに変わって分けられません。"""
    assert lanes.lane("session_01AAA") == lanes.lane("session_01AAA")


def test_lanes_split_the_ids() -> None:
    """IDが違えば、少なくとも**両方の車線が出る**こと（全部0番なら分けていない）。"""
    seen = {lanes.lane(f"session_{i:03d}") for i in range(50)}
    assert seen == {0, 1}


def test_lane_of_ignores_the_ledger() -> None:
    """車線は**分そのもの**から決まる。控えの中身に依存しないのが要点。"""
    assert lanes.lane_of(9 * 60, 30, 2) == 0
    assert lanes.lane_of(9 * 60 + 30, 30, 2) == 1
    assert lanes.lane_of(10 * 60, 30, 2) == 0


def test_two_lanes_never_pick_the_same_minute() -> None:
    """**これがこの直しの本体です。** 控えが同じでも、選ぶ分が重なりません。"""
    a = lanes.order(GRID, step_min=30, lanes=2, lane_no=0)[:5]
    b = lanes.order(GRID, step_min=30, lanes=2, lane_no=1)[:5]
    assert not set(a) & set(b)


def test_each_lane_keeps_the_min_gap() -> None:
    """自分の本どうしは 30分（`day_cap.MIN_GAP_MIN`）以上あくこと。"""
    for lane_no in (0, 1):
        picked = sorted(lanes.order(GRID, step_min=30, lanes=2, lane_no=lane_no)[:5])
        gaps = [b - a for a, b in zip(picked, picked[1:])]
        assert min(gaps) >= 30


def test_five_stay_inside_the_window() -> None:
    """**1回5本なら、どちらの車線でも 13:30 の窓の内側**に収まること。

    `LANES` を 4 に上げると 2時間間隔になり、5本目が 17:00 まで落ちて
    窓（`src/measure_window.py` の切り分け）の外へ出ます。**2 の理由がこれです。**
    """
    for lane_no in (0, 1):
        picked = lanes.order(GRID, step_min=30, lanes=lanes.LANES, lane_no=lane_no)[:5]
        assert max(picked) <= 13 * 60 + 30


def test_lane_falls_back_when_its_own_is_full() -> None:
    """車線を使い切ったら**となりへ回り込む**（捨てない）。"""
    got = lanes.order(GRID, step_min=30, lanes=2, lane_no=0)
    assert sorted(got) == sorted(GRID)


def test_lanes_off_is_the_old_order() -> None:
    assert lanes.order(GRID, step_min=30, lanes=1) == GRID


def test_missing_session_id_does_not_stop_us(monkeypatch) -> None:
    """IDが読めない回でも**止めない**（投稿が途切れるのが最大の損失）。"""
    monkeypatch.delenv("CLAUDE_CODE_REMOTE_SESSION_ID", raising=False)
    assert lanes.lane() == 0


def test_slots_uses_the_lane() -> None:
    """`batch_build.slots()` から見ても、車線ごとに別の分が返ること。"""
    a = slots(4, 9, "2026-09-30", [], step_min=30, taken_min=set(), lanes_n=1)
    assert a == ["2026-09-30@9:00", "2026-09-30@9:30",
                 "2026-09-30@10:00", "2026-09-30@10:30"]


def test_lanes_must_be_positive() -> None:
    with pytest.raises(ValueError):
        lanes.lane("x", lanes=0)
