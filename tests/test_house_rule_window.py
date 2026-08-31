"""**期日を延ばしても満ちない要件**の検査（2026-09-01）。

## なぜ要るか

`src/house_rule.needs_beyond_rule()` は **期日までの日数**で解いています ——
`allowed = (期日 − 今日) × PUBLISH_PER_DAY`。**だから期日を延ばすと黙ります。**
ところが `config/hypotheses.yaml` の `長尺1本あたり-30本` の `falsified_if` は

    **30本 に満たなければ判定せず、期限だけ延ばすこと**

と書いています。**指示と検査が同じ向きに壊れていました** ——
延ばせば警告が消え、前提は永久に開いたまま残ります。

`window_unreachable()` は**判定が読む窓**で解くので、延ばしても黙りません。
**この検査が落ちたら、その穴が開き直っています。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import house_rule  # noqa: E402


# --- 単位の見分け（ここが偽陽性の出どころ） ---------------------------------

def test_counts_items_true_for_item_counters():
    """`sum(1 for …)` と `len(…)` は**本数**。公開の上限に縛られる側。"""
    assert house_rule.counts_published_items(
        "sum(1 for v in long_ids() if latest_views().get(v, 0) > 0)") is True
    assert house_rule.counts_published_items("len({r['video_id'] for r in uploaded()})") is True


def test_counts_items_false_for_value_sums():
    """`sum(<値> for …)` は**量**（再生数）。本数の上限には縛られない。

    **ここを見ずに数だけ比べると偽陽性になります** —— `長尺-1000再生` の
    `need: 1000` は再生数で、規則の 1日1本 とは何の関係もありません。
    """
    assert house_rule.counts_published_items(
        "sum(latest_views().get(v, 0) for v in long_ids())") is False
    assert house_rule.counts_published_items(
        "sum(v for v in latest_views().values() if v < 342)") is False


def test_counts_items_none_when_unreadable():
    """読めないものは `None` ＝ **通す**（測っていないことを落とす側に倒さない）。"""
    assert house_rule.counts_published_items(None) is None
    assert house_rule.counts_published_items("") is None
    assert house_rule.counts_published_items("min(arm('a'), arm('b'))") is None


# --- 窓の読み取り -----------------------------------------------------------

def test_window_of_takes_the_narrowest():
    row = {"claim": "直近90日 の話", "falsified_if": "判定は 直近28日 の窓",
           "needs": [{"what": "直近60日"}]}
    assert house_rule.window_of(row) == 28


def test_window_of_none_when_absent():
    assert house_rule.window_of({"claim": "窓のことは書いていない"}) is None


# --- 本体 -------------------------------------------------------------------

def _row(need, expr, window_txt, **kw):
    r = {"claim": "c", "deadline": "2026-09-13", "watch": "w", "lever": "per_video",
         "falsified_if": window_txt,
         "needs": [{"kind": "accrual", "need": need, "count_expr": expr}]}
    r.update(kw)
    return r


def test_flags_need_above_window_capacity():
    """30本 ／ 窓 28日 ／ 1日1本 → **窓に 28本 しか入らないので永久に満ちない。**"""
    hits = house_rule.window_unreachable(
        [_row(30, "sum(1 for v in long_ids())", "判定は 直近28日 の窓")])
    assert len(hits) == 1
    assert hits[0]["need"] == 30
    assert hits[0]["window_days"] == 28
    assert hits[0]["allowed"] == 28


def test_does_not_flag_when_it_fits():
    hits = house_rule.window_unreachable(
        [_row(20, "sum(1 for v in long_ids())", "判定は 直近28日 の窓")])
    assert hits == []


def test_does_not_flag_value_sums():
    """**再生数の `need` は当てない。** ここが偽陽性の本体でした。"""
    hits = house_rule.window_unreachable(
        [_row(1000, "sum(latest_views().get(v, 0) for v in long_ids())",
              "判定は 直近90日 の窓")])
    assert hits == []


def test_does_not_flag_closed_rows():
    hits = house_rule.window_unreachable(
        [_row(30, "sum(1 for v in long_ids())", "直近28日", closed_on="2026-08-01")])
    assert hits == []


def test_extending_the_deadline_does_not_silence_it():
    """**この検査がこの節の存在理由です。**

    `needs_beyond_rule()` は期日を延ばせば黙りますが、こちらは日付を
    1つも見ないので黙りません。**「期限だけ延ばすこと」で逃げられない。**
    """
    row = _row(30, "sum(1 for v in long_ids())", "直近28日", deadline="2099-12-31")
    assert len(house_rule.window_unreachable([row])) == 1


def test_silent_if_owner_lifts_the_rule():
    """**覆る条件**: 規則が外れて 1日2本 になれば、窓に 56本 入るので黙る。"""
    row = _row(30, "sum(1 for v in long_ids())", "直近28日")
    assert house_rule.window_unreachable([row], per_day=2) == []


def test_lines_are_empty_when_nothing_is_stuck():
    assert house_rule.window_unreachable_lines([]) == []


def test_lines_name_the_blocked_lever():
    """**どの腕が止まっているか**を出すこと —— それが到達日への効き目そのもの。"""
    out = house_rule.window_unreachable_lines(
        [_row(30, "sum(1 for v in long_ids())", "直近28日")])
    assert out and any("per_video" in ln for ln in out)


def test_unreachable_lines_includes_the_window_section():
    """`scripts/deadline_check.py` は `unreachable_lines()` を印字するだけなので、
    **ここに入っていなければ、主実行の1周には出ません。**"""
    row = _row(30, "sum(1 for v in long_ids())", "直近28日", deadline="2099-12-31")
    out = house_rule.unreachable_lines([row], today="2026-09-01")
    assert any("期日を延ばしても満ちない" in ln for ln in out)
