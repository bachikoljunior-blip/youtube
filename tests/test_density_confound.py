"""`src/density_confound.py` の検査。**API は1単位も叩きません。**"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src import density_confound as dc

JST = timezone(timedelta(hours=9))


def _pub(spec: dict[str, tuple[int, int]]) -> dict[str, datetime]:
    return {vid: datetime(2026, m, d, 12, tzinfo=JST) for vid, (m, d) in spec.items()}


def test_per_day_counts_the_whole_population():
    pub = _pub({"A": (8, 4), "B": (8, 4), "C": (8, 20)})
    assert dc.per_day(pub) == {datetime(2026, 8, 4).date(): 2,
                               datetime(2026, 8, 20).date(): 1}


def test_density_of_reads_the_day_not_the_group():
    """群に入った本だけで数えると、その日に何本出たかではなく群の大きさになる。"""
    pub = _pub({"A": (8, 4), "B": (8, 4), "C": (8, 4)})
    assert dc.density_of(["A"], pub) == [3]


def test_overlap_flags_a_two_fold_difference():
    pub = _pub({f"L{i}": (8, 4) for i in range(2)} | {f"H{i}": (8, 20) for i in range(9)})
    got = dc.overlap(["L0", "L1"], [f"H{i}" for i in range(9)], pub)
    assert got["confounded"] is True
    assert got["median_a"] == 2 and got["median_b"] == 9


def test_overlap_is_quiet_when_the_groups_share_density():
    pub = _pub({"A": (8, 4), "B": (8, 4), "C": (8, 20), "D": (8, 20)})
    got = dc.overlap(["A", "B"], ["C", "D"], pub)
    assert got["confounded"] is False
    assert got["fold"] == 1.0


def test_overlap_survives_an_empty_group():
    pub = _pub({"A": (8, 4)})
    got = dc.overlap([], ["A"], pub)
    assert got["confounded"] is False and got["median_a"] is None


def test_line_never_returns_an_empty_string():
    """黙ると読まれない —— 交絡が無い回も1行出す。"""
    pub = _pub({"A": (8, 4), "B": (8, 20)})
    assert dc.line(["A"], ["B"], pub).strip()
    assert dc.line([], [], pub).strip()


def test_unknown_ids_are_skipped_not_counted_as_zero():
    pub = _pub({"A": (8, 4)})
    assert dc.density_of(["A", "GHOST"], pub) == [1]
