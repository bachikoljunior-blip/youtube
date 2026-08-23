"""`src/hook_verdict.py` の判定線を固定する。**API は叩かない。**

守っているのは3つ:

1. **群は日付で切る**（本数を写さない）。A=8/16〜18・B=8/19〜21
2. **同点は外れ**（`falsified_if` が「上回らない」なので、`>` でなければならない）
3. **標本が空なら「測っていない」**（survived に化けさせない）
"""
from datetime import datetime, timedelta, timezone

from src.hook_verdict import groups, verdict

JST = timezone(timedelta(hours=9))


def _at(day: int, hour: int = 12) -> datetime:
    return datetime(2026, 8, day, hour, tzinfo=JST)


def test_groups_split_by_jst_date() -> None:
    pub = {
        "a1": _at(16), "a2": _at(18, 23), "b1": _at(19), "b2": _at(21, 23),
        "before": _at(15, 23), "after": _at(22),
    }
    a, b = groups(pub)
    assert a == ["a1", "a2"]
    assert b == ["b1", "b2"]


def test_tie_is_falsified() -> None:
    """**同点も外れ。** `falsified_if` は「上回らない」と書いてある。"""
    assert verdict([0.3, 0.3], [0.3, 0.3]) == "falsified"


def test_b_higher_survives() -> None:
    assert verdict([0.20, 0.20], [0.30, 0.30]) == "survived"


def test_b_lower_is_falsified() -> None:
    assert verdict([0.30, 0.30], [0.20, 0.20]) == "falsified"


def test_empty_sample_is_not_a_verdict() -> None:
    """標本が無いのは survived ではない（8/09 の「survived だが未測定」と同じ穴）。"""
    assert verdict([], [0.3]) == "測っていない"
    assert verdict([0.3], []) == "測っていない"
