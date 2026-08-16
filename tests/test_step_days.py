"""`status.py` の「8本の日」の節を検査する。

前の回（2026-08-16 21:0x）の設計の見直しが残した1手です ——

  > `pick(8)` が8件返るのに、5件で1日を閉じて3件を余らせています。
  > 次の1手: **`status.py` に「あと何本で8本の日が1日増えるか」を日ごとに出させる。**
  > いまは毎回、予約一覧を目で数えていて、**3回続けて同じ数え方をしています。**

**目で数えるのをやめるための節なので、検査はまず「数が合うこと」を見ます。**
そして**空いている時刻**（`--hours` にそのまま渡す）が、既存の予約と
1つもぶつからないこと。ここがずれると、次の回が `upload_only.py` の
重なりの門で止まります。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.status import (  # noqa: E402
    JST,
    STEP_SIZE,
    STEP_SLOT_HOURS,
    STEP_TARGET_DAYS,
    print_step_days,
)


def _day(offset: int) -> str:
    return (datetime.now(JST) + timedelta(days=offset)).strftime("%Y-%m-%d")


def _run(short_hours, **kw) -> str:
    import io
    import contextlib

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        print_step_days(short_hours, **kw)
    return buf.getvalue()


def test_counts_full_days():
    """8本ある日だけを「段」に数える。7本は数えない。"""
    short_hours = {
        _day(8): set(range(9, 17)),      # 8本
        _day(9): set(range(9, 17)),      # 8本
        _day(10): set(range(9, 16)),     # 7本 ← 数えない
    }
    out = _run(short_hours)
    assert f"いま **2日** / {STEP_TARGET_DAYS}日" in out
    assert f"あと {STEP_TARGET_DAYS - 2}日" in out


def test_cheapest_day_first_and_free_hours_do_not_collide():
    """安い順に出す。そして出した時刻が既存の予約と1つもぶつからない。"""
    cheap, dear = _day(8), _day(9)
    short_hours = {
        cheap: {9, 10, 11, 12, 13},      # あと3本
        dear: {9, 10},                   # あと6本
    }
    out = _run(short_hours)
    lines = [ln for ln in out.splitlines() if "→ **あと" in ln]
    assert lines[0].startswith(f"    {cheap[5:]}"), out
    assert "**あと3本**" in lines[0]
    assert "**あと6本**" in lines[1]

    # 出した空きが、既に埋まっている時刻を1つも含まないこと
    hours = lines[0].split("空き")[1].strip().split()[0]
    got = [int(h) for h in hours.split(",")]
    assert len(got) == STEP_SIZE - len(short_hours[cheap])
    assert not (set(got) & short_hours[cheap]), got
    assert all(h in STEP_SLOT_HOURS for h in got)


def test_past_days_are_ignored():
    """**過ぎた日を数えない。** 段は「これから乗せる日」の話です。"""
    short_hours = {
        _day(-3): set(range(9, 17)),     # もう公開された8本
        _day(5): set(range(9, 17)),
    }
    out = _run(short_hours)
    assert "いま **1日**" in out


def test_m14_window_is_marked_not_hidden():
    """窓の中の日は**外さず印を付ける。** 外すと理由が見えなくなる。"""
    import scripts.status as st

    # 窓を「明日」に差し替えて測る（実物の窓は 8/23 で切れるため）
    target = _day(1)
    saved = sys.modules.get("batch_build")
    import batch_build

    old = batch_build.M14_WINDOW
    batch_build.M14_WINDOW = (target, target)
    try:
        out = _run({target: {9, 10, 11, 12, 13, 14, 15}})
        assert target[5:] in out                      # 消えていない
        assert "M14 の比較の窓" in out                 # 印が付いている
        assert "batch_build.py --count" not in out    # 打てる形では出さない
    finally:
        batch_build.M14_WINDOW = old
        if saved is not None:
            sys.modules["batch_build"] = saved
    assert st.STEP_SIZE == 8


def test_ready_to_paste_command_matches_the_cheapest_day():
    """そのまま打てる1行が、安い日と本数と空き時刻に一致すること。

    **窓を空にしてから測ります。** 日付をずらして窓の外へ逃げると、
    窓が動いたときに検査のほうが黙って壊れます（M14 の窓は 8/23 で切れる）。
    """
    import batch_build

    cheap = _day(6)
    old = batch_build.M14_WINDOW
    batch_build.M14_WINDOW = ("", "")
    try:
        out = _run({cheap: {9, 10, 11, 12, 13, 14}})
    finally:
        batch_build.M14_WINDOW = old
    assert f"--count 2 --date {cheap} --hours 15,16" in out


def test_no_partial_day_says_so():
    """足せる日が無いときは、黙らずにそう言う（次の回が新しい日を立てる）。"""
    out = _run({_day(4): set(range(9, 17))})
    assert "足せる日がありません" in out
