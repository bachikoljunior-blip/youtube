"""**1本あたり再生は、規則が固定した公開密度で測ること。**（2026-08-31・最適化の回）

天井も門1 も、分子は `per_video` です。その分子を「1日に 3〜21本 出した日」の本で
測ると、**規則（`house_rule.PUBLISH_PER_DAY = 1`）と単位が合いません。**

この検査が守るのは3つ:

1. **規則の密度の帯は、規則から引くこと**（定数を書かない）
2. **弾力性の区間が 0 をまたいだら、分子を動かさないこと**（`per_video()` が `None`）
3. **`per_video()` が返すのは平均**（天井は N × 平均 で解くため）
"""
from __future__ import annotations

import json
import math

import pytest

from src import house_rule, rule_per_video


def _views(rows):
    """`(id, hours, views, at)` の並びを views.jsonl の行に。"""
    return "\n".join(json.dumps({"id": i, "hours": h, "views": v, "at": a})
                     for i, h, v, a in rows)


def _write(tmp_path, rows, forms):
    p = tmp_path / "views.jsonl"
    p.write_text(_views(rows), encoding="utf-8")
    return p


def _day(n_days, per_day, views_each, start_day=1, vid_prefix="v"):
    """`n_days` 日ぶん、1日 `per_day` 本、それぞれ `views_each` 回。"""
    rows = []
    for d in range(n_days):
        day = start_day + d
        for k in range(per_day):
            vid = f"{vid_prefix}{day}_{k}"
            at = f"2026-08-{day:02d}T00:00:00Z"
            # 齢 0時間 と 100時間 の2点（100h > ショートの門 48h なので伸びきり）
            rows.append((vid, 0.0, 0, at))
            rows.append((vid, 100.0, views_each, f"2026-09-{day:02d}T04:00:00Z"))
    return rows


def test_band_comes_from_the_house_rule(tmp_path):
    """帯は `house_rule.PUBLISH_PER_DAY` から引くこと。**定数を書かない。**"""
    rows = _day(6, 1, 1000) + _day(6, 9, 100, start_day=10)
    forms = {v[0]: "ショート" for v in rows}
    p = _write(tmp_path, rows, forms)

    e1 = rule_per_video.estimate(views_path=p, forms=forms, per_day=1)
    e3 = rule_per_video.estimate(views_path=p, forms=forms, per_day=3)
    assert e1["band"] == 1 * rule_per_video.RULE_BAND_MULT
    assert e3["band"] == 3 * rule_per_video.RULE_BAND_MULT

    # 既定は規則そのものを読む
    e = rule_per_video.estimate(views_path=p, forms=forms)
    assert e["per_day"] == house_rule.PUBLISH_PER_DAY


def test_picks_the_rule_density_days_not_the_pool(tmp_path):
    """規則の密度の日と、それを超えた日を、別々に出すこと。"""
    rows = _day(6, 1, 1000) + _day(6, 9, 100, start_day=10)
    forms = {v[0]: "ショート" for v in rows}
    p = _write(tmp_path, rows, forms)
    e = rule_per_video.estimate(views_path=p, forms=forms, per_day=1)

    assert e["rule_days"] == 6
    assert e["over_days"] == 6
    assert e["at_rule"] == pytest.approx(1000)
    assert e["over_median"] == pytest.approx(100)
    # 混ぜると、本数の多い側（100回）に引きずられる
    assert e["pooled"] < e["at_rule"]
    # 標本の大半は規則が禁じた密度の日の本
    assert e["share_over_band"] > 0.8


def test_per_video_returns_the_mean_not_the_median(tmp_path):
    """**天井は N × 平均 で解く。** だから返すのは平均。"""
    # 規則の密度の日を、平均と中央値がずれる形に
    rows = _day(5, 1, 100) + [
        *_day(1, 1, 1000, start_day=6, vid_prefix="big"),
    ] + _day(6, 9, 10, start_day=10)
    forms = {v[0]: "ショート" for v in rows}
    p = _write(tmp_path, rows, forms)
    e = rule_per_video.estimate(views_path=p, forms=forms, per_day=1)

    assert e["at_rule"] != pytest.approx(e["at_rule_mean"])
    got = rule_per_video.per_video(views_path=p, forms=forms, per_day=1)
    assert got == pytest.approx(e["at_rule_mean"])


def test_no_effect_means_no_numerator_change(tmp_path):
    """**弾力性の区間が 0 をまたいだら `None`。** 呼び手は混ぜた平均へ落ちる。"""
    # どの密度でも同じ回数 → 弾力性は 0
    rows = _day(6, 1, 500) + _day(6, 9, 500, start_day=10)
    forms = {v[0]: "ショート" for v in rows}
    p = _write(tmp_path, rows, forms)
    e = rule_per_video.estimate(views_path=p, forms=forms, per_day=1)

    assert e["significant"] is False
    assert rule_per_video.per_video(views_path=p, forms=forms, per_day=1) is None


def test_unripe_videos_are_not_counted(tmp_path):
    """**伸びきっていない本を入れないこと**（`settle.mature_hours`）。"""
    ripe = _day(4, 1, 900)
    unripe = [("young", 0.0, 0, "2026-08-20T00:00:00Z"),
              ("young", 5.0, 3, "2026-08-20T05:00:00Z")]
    rows = ripe + unripe
    forms = {v[0]: "ショート" for v in rows}
    p = _write(tmp_path, rows, forms)
    e = rule_per_video.estimate(views_path=p, forms=forms, per_day=1)
    assert e["n_videos"] == 4          # young は落ちる
    assert e["at_rule"] == pytest.approx(900)


def test_long_form_is_not_mixed_in(tmp_path):
    """**形をまたがないこと。** 既定はショート。"""
    rows = _day(4, 1, 900) + [
        ("L1", 0.0, 0, "2026-08-20T00:00:00Z"),
        ("L1", 200.0, 4, "2026-08-28T08:00:00Z"),
    ]
    forms = {v[0]: "ショート" for v in rows}
    forms["L1"] = "長尺"
    p = _write(tmp_path, rows, forms)
    e = rule_per_video.estimate(views_path=p, forms=forms, per_day=1)
    assert e["n_videos"] == 4
    assert e["form"] == "ショート"


def test_live_measurement_is_significant_and_above_the_pool():
    """**いまの実測**（`data/views.jsonl`）で、規則の密度のほうが高いこと。

    **覆る条件**: 規則 1本/日 の下で公開した日がたまって、帯の差が消えたら
    ここは落ちます。**落ちたら、それはこの道具の役目が終わったということ**
    （分子はもう規則の密度で測れている）。そのときは `significant` の側を見ること。
    """
    e = rule_per_video.estimate()
    if not e.get("ok") or e.get("at_rule") is None:
        pytest.skip("手元の控えが空です")
    assert e["elasticity"]["ok"]
    # 向きだけを固定する（数は控えが伸びれば動く）
    assert e["elasticity"]["b"] < 0
    assert e["at_rule"] > e["pooled"]
