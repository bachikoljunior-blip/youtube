"""**`-` で始まる動画IDが、`--move` を通ること**（2026-08-26 に踏んだ）。

YouTube の動画IDは `A-Za-z0-9_-` の64種から作るので、**1/64 は `-` で始まります**
（実測: 予約中の 487本 に 8本）。argparse は先頭の `-` を旗と読むので、
`reschedule.py --move -rNsh53STNw <時刻>` は

    error: argument --move: expected 2 arguments

で落ちます。**貼っても落ち、呼んでも落ちます** —— 2026-08-26 16:0x の
`queue_lag --apply` は 51手 のうち **6手目**で止まり、
`live_slots --apply --all` の 35手 にも `-LBSPCCE8Aw` が入っていました。
**この2つが、到達日を動かす手の1位と2位**です（77日 と +35本）。
"""
from __future__ import annotations

from scripts import reschedule


def test_dash_id_survives_the_parser() -> None:
    argv, lifted = reschedule._lift_dash_ids(
        ["--move", "-rNsh53STNw", "2026-09-03T11:30", "--force-window"])
    assert lifted["move"] == ["-rNsh53STNw", "2026-09-03T11:30"]
    assert argv == ["--force-window"]


def test_plain_id_is_untouched() -> None:
    argv, lifted = reschedule._lift_dash_ids(
        ["--move", "AFfHrkaAHzk", "2026-09-03T11:30"])
    assert lifted["move"] == ["AFfHrkaAHzk", "2026-09-03T11:30"]
    assert argv == []


def test_unschedule_takes_a_dash_id() -> None:
    argv, lifted = reschedule._lift_dash_ids(["--unschedule", "-LBSPCCE8Aw"])
    assert lifted["unschedule"] == "-LBSPCCE8Aw"
    assert argv == []


def test_other_flags_still_reach_argparse() -> None:
    argv, lifted = reschedule._lift_dash_ids(
        ["--compact", "--apply", "--max", "10"])
    assert lifted == {}
    assert argv == ["--compact", "--apply", "--max", "10"]


def test_parser_accepts_the_lifted_form() -> None:
    """**受け口ごと通ること。** 上の4つは抜き出しだけを見ています。"""
    argv, lifted = reschedule._lift_dash_ids(
        ["--move", "-rNsh53STNw", "2026-09-03T11:30", "--force-window"])
    args = reschedule.build_parser().parse_args(argv)
    for key, val in lifted.items():
        setattr(args, key, val)
    assert args.move == ["-rNsh53STNw", "2026-09-03T11:30"]
    assert args.force_window is True
