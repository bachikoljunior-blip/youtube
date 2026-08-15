"""「1日にN本」を置けるか、そして**測定の窓を踏まないか**を検査する。

M14（`docs/MEANS.md`）は本数の段を 2 → 4 → 8 と上げる手ですが、
`--hour` は「その時刻で最初に空いている**日**」を返すので、
8本ぶん呼ぶと **8日にばらけて 1日1本の実験になります。**
段を上げる道そのものが無かった、というのがここで塞いだ穴です。

窓の検査も一緒に置いてあります。「実験の窓を踏まないこと」は文書に3か所
書いてありましたが、**守っていたのは毎回こちらの記憶**でした。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from scripts.batch_build import check_window, slots  # noqa: E402
from src.uploader import JST, next_publish_at  # noqa: E402


# --- slots: 1日にN本を置けるか -------------------------------------------

def test_no_date_keeps_old_behaviour():
    """日付を渡さなければ従来どおり。全部同じ時刻＝1日ずつ後ろへ積まれる。"""
    assert slots(3, 9, None, []) == ["9", "9", "9"]


def test_date_spreads_hours_on_one_day():
    """日付を渡すと、**同じ日**の別々の時刻になる。これが8の段。"""
    assert slots(4, 10, "2026-08-24", []) == [
        "2026-08-24@10", "2026-08-24@11", "2026-08-24@12", "2026-08-24@13",
    ]


def test_explicit_hours_win():
    assert slots(2, 9, "2026-08-24", [14, 20]) == [
        "2026-08-24@14", "2026-08-24@20",
    ]


def test_hours_are_trimmed_to_count():
    assert slots(2, 9, "2026-08-24", [1, 2, 3]) == [
        "2026-08-24@1", "2026-08-24@2",
    ]


def test_too_few_hours_is_refused():
    with pytest.raises(SystemExit):
        slots(3, 9, "2026-08-24", [10, 11])


def test_duplicate_hours_are_refused():
    """同じ時刻に2本置くと食い合う（`next_publish_at` の元の理由と同じ）。"""
    with pytest.raises(SystemExit):
        slots(2, 9, "2026-08-24", [10, 10])


def test_hour_out_of_range_is_refused():
    with pytest.raises(SystemExit):
        slots(2, 23, "2026-08-24", [])   # 23, 24 → 24 が範囲外


# --- check_window: 測定の窓を機械に持たせる -------------------------------

@pytest.mark.parametrize("date", ["2026-08-16", "2026-08-20", "2026-08-23"])
def test_window_blocks(date):
    with pytest.raises(SystemExit):
        check_window(date, force=False)


@pytest.mark.parametrize("date", ["2026-08-15", "2026-08-24", "2026-09-01"])
def test_outside_window_passes(date):
    check_window(date, force=False)


def test_force_window_passes():
    check_window("2026-08-20", force=True)


# --- next_publish_at: 日付の釘づけ ---------------------------------------

def _future_date(days: int) -> str:
    return (datetime.now(JST) + timedelta(days=days)).strftime("%Y-%m-%d")


def test_pinned_date_is_returned_as_is():
    day = _future_date(9)
    got = next_publish_at(10, 0, taken=set(), date_jst=day)
    want = datetime.strptime(f"{day} 10:00", "%Y-%m-%d %H:%M") \
        .replace(tzinfo=JST).astimezone(timezone.utc) \
        .strftime("%Y-%m-%dT%H:%M:%SZ")
    assert got == want


def test_pinned_date_does_not_slide_when_taken():
    """**埋まっていても翌日へ送らない。** 送ると「1日8本」が7本+1本に化ける。"""
    day = _future_date(9)
    taken = {next_publish_at(10, 0, taken=set(), date_jst=day)}
    with pytest.raises(ValueError):
        next_publish_at(10, 0, taken=taken, date_jst=day)


def test_pinned_past_date_is_refused():
    with pytest.raises(ValueError):
        next_publish_at(10, 0, taken=set(), date_jst=_future_date(-1))


def test_pinned_bad_date_is_refused():
    with pytest.raises(ValueError):
        next_publish_at(10, 0, taken=set(), date_jst="8/24")


def test_unpinned_still_slides_a_day():
    """日付を渡さない側の動きは変えていない（作り置きが重ならない）。"""
    first = next_publish_at(10, 0, taken=set())
    second = next_publish_at(10, 0, taken={first})
    assert second != first
    a = datetime.strptime(first, "%Y-%m-%dT%H:%M:%SZ")
    b = datetime.strptime(second, "%Y-%m-%dT%H:%M:%SZ")
    assert (b - a) == timedelta(days=1)
