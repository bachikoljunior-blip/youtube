"""`src/family_order_verdict.py` の検査。**API は1単位も叩きません。**"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

from src import family_order_verdict as fv

JST = timezone(timedelta(hours=9))


def _batch(tmp_path, rows):
    p = tmp_path / "batch_runs.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    return p


def test_built_reads_created_day_and_family(tmp_path):
    p = _batch(tmp_path, [
        {"at": "2026-08-19T09:00:00+09:00",
         "results": [{"topic": "a", "calc": "keihi", "video_id": "V1", "error": ""}]},
        {"at": "2026-08-20T09:00:00+09:00",
         "results": [{"topic": "b", "calc": "rousai", "video_id": "V2", "error": ""}]},
    ])
    got = fv.built(p)
    assert got["V1"] == {"created": date(2026, 8, 19), "calc": "keihi"}
    assert got["V2"]["calc"] == "rousai"


def test_built_drops_failed_builds(tmp_path):
    p = _batch(tmp_path, [
        {"at": "2026-08-19T09:00:00+09:00",
         "results": [{"topic": "a", "calc": "keihi", "video_id": "", "error": "boom"},
                     {"topic": "b", "calc": "keihi", "video_id": "V9", "error": "boom"}]},
    ])
    assert fv.built(p) == {}


def test_built_keeps_the_earliest_build(tmp_path):
    """作り直しは順番の産物ではないので、**先に作ったほう**を採る。"""
    p = _batch(tmp_path, [
        {"at": "2026-08-21T09:00:00+09:00",
         "results": [{"calc": "keihi", "video_id": "V1", "error": ""}]},
        {"at": "2026-08-17T09:00:00+09:00",
         "results": [{"calc": "keihi", "video_id": "V1", "error": ""}]},
    ])
    assert fv.built(p)["V1"]["created"] == date(2026, 8, 17)


def test_groups_split_treated_by_build_day_not_publish_day():
    """**ここがこの判定の要点。** 8/16 より前に作って後から公開した本は処置に入れない。"""
    pub = {
        "OLD": datetime(2026, 8, 10, 12, tzinfo=JST),   # 対照（公開日で切る）
        "LATE": datetime(2026, 8, 19, 12, tzinfo=JST),  # 8/15 に作った → 処置ではない
        "NEW": datetime(2026, 8, 19, 12, tzinfo=JST),   # 8/17 に作った → 処置
    }
    builds = {
        "OLD": {"created": date(2026, 8, 10), "calc": "x"},
        "LATE": {"created": date(2026, 8, 15), "calc": "x"},
        "NEW": {"created": date(2026, 8, 17), "calc": "x"},
    }
    base, treat = fv.groups(pub, builds, as_of=date(2026, 8, 26))
    assert base == ["OLD"]
    assert treat == ["NEW"]


def test_groups_drop_books_whose_data_has_not_landed():
    """熟成 ＋ 実データの遅れ を足した日より後に公開した本は、まだ読めない。"""
    pub = {"YOUNG": datetime(2026, 8, 25, 12, tzinfo=JST)}
    builds = {"YOUNG": {"created": date(2026, 8, 24), "calc": "x"}}
    _, treat = fv.groups(pub, builds, as_of=date(2026, 8, 26))
    assert treat == []


def test_verdict_needs_both_baselines_to_agree():
    """数え直した基準と、書いてある基準で答えが割れたら `undecided`。"""
    split = fv.verdict([0.20, 0.20, 0.20], [0.30, 0.30, 0.30], written=0.40)
    assert split["decided"] is False
    assert split["upheld"] is None


def test_verdict_falsified_when_treated_is_lower():
    got = fv.verdict([0.34, 0.35, 0.36], [0.24, 0.245, 0.25], written=0.347)
    assert got["decided"] is True
    assert got["upheld"] is False


def test_verdict_tie_is_a_miss():
    """`falsified_if` は「上回っていない（同点も外れ）」。"""
    got = fv.verdict([0.347], [0.347], written=0.347)
    assert got["decided"] is True
    assert got["upheld"] is False


def test_verdict_undecided_when_a_group_is_empty():
    assert fv.verdict([], [0.3])["decided"] is False
    assert fv.verdict([0.3], [])["decided"] is False


def test_sweep_settle_marks_an_empty_treated_arm_as_unmeasurable():
    """標本が消えた欄を「上回らない」に数えると、待つほど自動で外れになる。"""
    pub = {"OLD": datetime(2026, 8, 10, 12, tzinfo=JST),
           "NEW": datetime(2026, 8, 19, 12, tzinfo=JST)}
    builds = {"OLD": {"created": date(2026, 8, 10), "calc": "x"},
              "NEW": {"created": date(2026, 8, 17), "calc": "x"}}
    rows = [{"video": "OLD", "views": 100, "engagedViews": 35},
            {"video": "NEW", "views": 100, "engagedViews": 25}]
    got = fv.sweep_settle(rows, ["OLD"], builds, pub, as_of=date(2026, 8, 26), settles=(3, 7))
    assert got[0]["upheld"] is False and got[0]["n_treat"] == 1
    assert got[1]["upheld"] is None and got[1]["n_treat"] == 0


def test_by_family_groups_treated_books():
    builds = {"A": {"created": date(2026, 8, 19), "calc": "keihi"},
              "B": {"created": date(2026, 8, 19), "calc": "keihi"},
              "C": {"created": date(2026, 8, 19), "calc": "rousai"}}
    rows = [{"video": "A", "views": 100, "engagedViews": 20},
            {"video": "B", "views": 100, "engagedViews": 30},
            {"video": "C", "views": 100, "engagedViews": 40}]
    got = fv.by_family(rows, ["A", "B", "C"], builds)
    assert got[0] == {"calc": "keihi", "n": 2, "median": 0.25}
    assert got[1] == {"calc": "rousai", "n": 1, "median": 0.40}


def test_min_views_line_is_borrowed_not_redrawn():
    """線を引き直すと比較が壊れる（`length_verdict` から借りていること）。"""
    from src.length_verdict import MIN_VIEWS

    assert fv.MIN_VIEWS is MIN_VIEWS == 30


def test_readable_by_matches_settle_plus_lag():
    from src.settle import SETTLE_DAYS, analytics_lag_days

    as_of = date(2026, 8, 26)
    assert fv.readable_by(as_of) == as_of - timedelta(days=SETTLE_DAYS + analytics_lag_days(as_of))
