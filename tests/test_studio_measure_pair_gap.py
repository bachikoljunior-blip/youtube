"""`measure` が「この測りは2点組に入るか」を言うこと（2026-09-10 02:2x・optimizer・Opus）。

**踏んだ実物**: 前の周の optimizer が 02:06:25 に測り、その 1分後 に親が穴埋めで
次の optimizer を立て（`parent_wakes.jsonl` の `patch: true`）、この回は 02:13:29 に測った。
差 7.1分 は `trend.MIN_PAIR_MIN`（10分）より短いので `_pairs` が丸ごと落とす ＝
**§7 (2) の分母は動かないのに、印字は「記した: 19本」だけ**だった。

**陽性対照**（この文書の決め・§6「検査を足したら、壊して落ちることを確かめること」）:
  - `pair_gap` が `MIN_PAIR_MIN` を読まずに 10 を直書きすると `test_門は定数から読む` が落ちる
  - `cmd_measure` から印字を外すと `test_measure_が撃つ前に言う` が落ちる
"""
from __future__ import annotations

import datetime as dt

from studio import cli, trend
from studio.common import JST


def _row(at: dt.datetime, vid: str = "v1") -> dict:
    return {"event": "measured", "id": vid, "at": at.isoformat(), "views": 1, "age_h": 5.0}


def test_門より短ければ入らないと言う():
    at = dt.datetime(2026, 9, 10, 2, 13, 29, tzinfo=JST)
    rows = [_row(at - dt.timedelta(minutes=7.1))]
    g = trend.pair_gap(rows, at)
    assert g["pairs"] is False
    assert round(g["gap_min"], 1) == 7.1
    line = trend.pair_gap_line(rows, at)
    assert "2点組に入りません" in line
    assert "あと 2.9分" in line


def test_門より長ければ入ると言う():
    at = dt.datetime(2026, 9, 10, 2, 13, 29, tzinfo=JST)
    rows = [_row(at - dt.timedelta(minutes=45.2))]
    g = trend.pair_gap(rows, at)
    assert g["pairs"] is True
    assert "2点組に入ります" in trend.pair_gap_line(rows, at)


def test_門は定数から読む():
    """`MIN_PAIR_MIN` を動かすと、判定も印字の数も一緒に動くこと（直書きを禁じる）。"""
    at = dt.datetime(2026, 9, 10, 2, 13, 29, tzinfo=JST)
    rows = [_row(at - dt.timedelta(minutes=12.0))]
    assert trend.pair_gap(rows, at)["pairs"] is True
    old = trend.MIN_PAIR_MIN
    try:
        trend.MIN_PAIR_MIN = 20.0
        assert trend.pair_gap(rows, at)["pairs"] is False
        assert "門 20分" in trend.pair_gap_line(rows, at)
    finally:
        trend.MIN_PAIR_MIN = old


def test_帯の中か外かを言う():
    rows = [_row(dt.datetime(2026, 9, 10, 2, 0, tzinfo=JST))]
    inband = trend.pair_gap_line(rows, dt.datetime(2026, 9, 10, 3, 0, tzinfo=JST))
    outband = trend.pair_gap_line(rows, dt.datetime(2026, 9, 10, 12, 0, tzinfo=JST))
    assert "帯 02:00〜10:00 JST の中" in inband
    assert "帯の外" in outband


def test_台帳が空でも落ちない():
    at = dt.datetime(2026, 9, 10, 2, 13, tzinfo=JST)
    g = trend.pair_gap([], at)
    assert g["gap_min"] is None and g["pairs"] is True
    assert "1点目" in trend.pair_gap_line([], at)


def test_measured_以外の行は数えない():
    """`pending`・`built` などの行を「前の測り」と読み違えないこと。"""
    at = dt.datetime(2026, 9, 10, 2, 13, tzinfo=JST)
    rows = [{"event": "pending", "id": "v1", "at": (at - dt.timedelta(minutes=1)).isoformat()},
            _row(at - dt.timedelta(minutes=40))]
    assert round(trend.pair_gap(rows, at)["gap_min"]) == 40


def test_measure_が撃つ前に言う():
    """`cmd_measure` の1行目が `pair_gap_line` であること（API を撃つ前に出す）。"""
    src = cli.cmd_measure.__code__.co_consts
    import inspect
    body = inspect.getsource(cli.cmd_measure)
    assert "pair_gap_line" in body
    # API を撃つ行（`yt.published`）より前に在ること
    assert body.index("pair_gap_line") < body.index("yt.published")
    assert src is not None
