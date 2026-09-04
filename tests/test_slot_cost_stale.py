"""**枠の機会費用が、いつの本で出来ているか**を隠さないこと（2026-09-05 02:5x）。

`slot_cost.slot_value()` は 1,049回 を「**この1枠は何回 か**」として印字し、
`win_band()` はその数を `paid`（＝ 形の判断を動かしてよい）の境目に使っています。
ところが実測すると、その 15本 は **2026-08-05〜08-18** の本だけで、
**いちばん新しい1本が 18日前**でした。`scripts/eta.py` は同じ帯・同じ日付の化石を
`per_video` について毎周 名指ししているのに、**こちらは何も言っていませんでした。**

ここが赤になるのは、**齢の配線が外れたとき**です（数そのものは1つも縛っていません）。
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from src import slot_cost as S


def _rows(pairs, form="ショート", day_count=1):
    """(公開日, 48h再生) の並びを `aged_views()` の行の形にする。"""
    return [{"video_id": f"v{i}", "form": form, "pub": p, "views": v,
             "day_count": day_count, "age_h": 48.0}
            for i, (p, v) in enumerate(pairs)]


def _cmp(rows, *, recent=None):
    from src import daily_pick as dp
    return {"rows": rows,
            "rule": dp.by_form(rows, max_per_day=dp.RULE_BAND_MULT),
            "all": dp.by_form(rows),
            "recent": recent if recent is not None else dp.by_form(rows),
            "recent_days": 14}


NOW = datetime(2026, 9, 5, 2, 55, tzinfo=timezone.utc)


def test_sample_window_reads_first_and_last_publish_day():
    rows = _rows([(date(2026, 8, 5), 100), (date(2026, 8, 18), 300)])
    w = S.sample_window(rows, "ショート", max_per_day=2)
    assert (w["first"], w["last"], w["n"]) == (date(2026, 8, 5), date(2026, 8, 18), 2)


def test_sample_window_drops_days_over_the_rule_density():
    rows = _rows([(date(2026, 8, 5), 100)]) + _rows([(date(2026, 9, 3), 9)], day_count=9)
    w = S.sample_window(rows, "ショート", max_per_day=2)
    assert w["last"] == date(2026, 8, 5) and w["n"] == 1


def test_slot_value_carries_the_age_of_the_cost():
    rows = _rows([(date(2026, 8, 5), 100), (date(2026, 8, 18), 300)])
    s = S.slot_value(cmp=_cmp(rows), now=NOW)
    assert s["best"] == "ショート"
    assert s["cost_age_days"] == 18
    assert "ショート" in s["stale"]


def test_a_fresh_sample_is_not_called_stale():
    rows = _rows([(date(2026, 9, 4), 300), (date(2026, 9, 5), 200)])
    s = S.slot_value(cmp=_cmp(rows), now=NOW)
    assert s["cost_age_days"] == 0
    assert s["stale"] == []
    assert S.stale_lines(sv=s) == []


def test_stale_lines_name_the_window_and_the_recent_median():
    from src import daily_pick as dp
    rows = _rows([(date(2026, 8, 5), 100), (date(2026, 8, 18), 300)])
    recent = dp.by_form(_rows([(date(2026, 9, 1), 129)] * 3, day_count=9))
    out = S.stale_lines(sv=S.slot_value(cmp=_cmp(rows, recent=recent), now=NOW))
    assert out, "化石なのに1行も出ていない"
    blob = "\n".join(out)
    assert "2026-08-05" in blob and "2026-08-18" in blob and "18日前" in blob
    assert "129回" in blob, "直近の数が並んでいない（片方だけでは『いま』が読めない）"
    # **どちらも『いま』ではない**と言い切るところまでが、この註の仕事。
    assert "きれいで新しい数は、いま1つも在りません" in blob


def test_lines_prints_the_stale_note_next_to_the_cost():
    rows = _rows([(date(2026, 8, 5), 100), (date(2026, 8, 18), 300)])
    blob = "\n".join(S.lines(cmp=_cmp(rows), now=NOW))
    assert "この1枠は" in blob
    assert "「いま」ではありません" in blob


@pytest.mark.parametrize("v,band", [(50, "miss"), (101, "unpaid"), (5000, "paid")])
def test_win_band_marks_a_stale_boundary_but_does_not_move_it(v, band):
    rows = _rows([(date(2026, 8, 5), 100), (date(2026, 8, 18), 300)])
    s = S.slot_value(cmp=_cmp(rows), now=NOW)
    r = S.win_band(v, gate=100, sv=s)
    assert r["band"] == band, "帯そのものは1つも動かしていないこと"
    assert r["cost_age_days"] == 18 and r["cost_stale"] is True
    if band == "miss":
        assert "日前の帯の高さ" not in r["line"], "外れの行に境目の齢は要らない"
    else:
        assert "18日前の帯の高さ" in r["line"]


def test_win_band_stays_silent_when_the_sample_is_fresh():
    rows = _rows([(date(2026, 9, 4), 300), (date(2026, 9, 5), 200)])
    r = S.win_band(101, gate=100, sv=S.slot_value(cmp=_cmp(rows), now=NOW))
    assert r["cost_stale"] is False
    assert "日前の帯の高さ" not in r["line"]
