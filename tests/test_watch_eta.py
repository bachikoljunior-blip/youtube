"""`src/watch_eta.py`。**「満ちない待ち」を見つける計器**の線を固定する。

守っているのは4つ:

1. 速さから**埋まる日**が出る
2. **速さが0以下なら「届かない」**（`fills_on is None`）
3. **数える窓がまだ来ていない待ちを「届かない」と言わない**（誤報を出す計器は信用されない）
4. 期限の拾い方（`期限 2026-09-15` と `期限 09/05` の2形）
"""
from datetime import date

from src.watch_eta import Forecast, deadline_of
from src.watches import Watch


def _w(what: str = "", cond: str = "") -> Watch:
    return Watch(id="x", what=what, cond=cond, then="", source="", kind="scan_sum")


def test_deadline_full_form() -> None:
    assert deadline_of(_w(what="判定（期限 2026-09-15）")) == date(2026, 9, 15)


def test_deadline_short_form() -> None:
    got = deadline_of(_w(what="判定（期限 09/05）"))
    assert got is not None and (got.month, got.day) == (9, 5)


def test_no_deadline_is_none() -> None:
    assert deadline_of(_w(what="期限は書いていない")) is None


def test_in_time_true_when_already_met() -> None:
    f = Forecast("x", now=10, need=10, per_day=0.0, fills_on=date(2026, 8, 23), deadline=None)
    assert f.in_time is True


def test_unreachable_is_not_in_time() -> None:
    f = Forecast("x", now=18, need=1000, per_day=0.0, fills_on=None, deadline=date(2026, 9, 15))
    assert f.in_time is False


def test_late_is_not_in_time() -> None:
    f = Forecast("x", now=18, need=1000, per_day=1.4,
                 fills_on=date(2028, 7, 25), deadline=date(2026, 9, 15))
    assert f.in_time is False


def test_not_started_is_not_a_verdict() -> None:
    """**窓が来ていないだけの待ちを「届かない」と言わない。** 0件は伸び0ではない。"""
    f = Forecast("x", now=0, need=15000, per_day=0.0, fills_on=None,
                 deadline=date(2026, 9, 20), not_started=True)
    assert f.in_time is None
