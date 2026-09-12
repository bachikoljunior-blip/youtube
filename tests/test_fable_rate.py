"""「Fable のみ」の目盛りは、**自身の速さ**で運ぶ（2026-09-03 03:5x に踏んだ）。

公式仕様: Fable に使えるのは全モデル週間上限の 50% ぶん → 「Fable のみ」の目盛りは
全部を Fable で走らせているあいだ、全モデルの 2倍 の速さで進む。
`quota.sub_model` は全モデルの速さ（1.69 %/時）で運んでいたので、100% に届く時刻を
**1日 遅く**見ていた（実物 09/03 18:47 JST ／ あの数では 09/04 20:4x）。
その 1日、親は `fable` を渡し続け、立てたサブは落ちる（A10）。

戻すには、この検査を消すしかありません。
"""
from datetime import datetime, timedelta

import pytest

from scripts import next_round_owner as owner
from scripts import quota

JST = quota.JST
RESETS = "2026-09-04T22:00:00Z"


def _rows(with_second: bool = True) -> list[dict]:
    rows = [{"fetched_at": "2026-09-02T19:39:00+09:00", "window_id": "seven_day",
             "used_percent": 15, "resets_at_iso": RESETS, "fable_percent": 12}]
    if with_second:
        rows.append({"fetched_at": "2026-09-02T22:01:00+09:00", "window_id": "seven_day",
                     "used_percent": 19, "resets_at_iso": RESETS, "fable_percent": 21})
    rows.sort(key=lambda r: r["fetched_at"], reverse=True)
    return rows


#: この検査の中だけの作り: **1時間に fable のサブ 4体**が立つ（`data/model_choice.jsonl` の代わり）。
#: 2026-09-13 06:3x から `fable_estimate` は**体の数**で運ぶので、体が立たない盤では
#: 目盛りは 1%も 進みません（＝ 時間で運んでいた頃の数はここでは出ません）。
def _subs(since, until, model=None):
    return int(max(0.0, (until - since).total_seconds() / 3600) * 4)


@pytest.fixture
def two_points(monkeypatch):
    monkeypatch.setattr(quota, "_anchors", lambda: _rows(True))
    monkeypatch.setattr(quota, "pace", lambda now=None: {"carry_rate": 1.69})
    monkeypatch.setattr(quota, "_subs_from_choices", _subs)


@pytest.fixture
def one_point(monkeypatch):
    monkeypatch.setattr(quota, "_anchors", lambda: _rows(False))
    monkeypatch.setattr(quota, "pace", lambda now=None: {"carry_rate": 1.69})


def test_official_share_is_half_and_shared_with_owner_wrapper():
    assert quota.OFFICIAL_FABLE_SHARE == 0.5
    assert owner.OFFICIAL_FABLE_SHARE_OF_REGULAR_WEEK == quota.OFFICIAL_FABLE_SHARE


def test_measured_rate_comes_from_fable_points_not_all_models(two_points):
    fr = quota.fable_rate(datetime(2026, 9, 3, 3, 40, tzinfo=JST))
    assert fr["source"] == "measured"
    assert fr["rate"] == pytest.approx(9 / (2 + 22 / 60), rel=1e-3)     # 3.80 %/時
    assert fr["all_rate"] == pytest.approx(4 / (2 + 22 / 60), rel=1e-3)  # 1.69 %/時
    # 比が公式の 1/0.5 ＝ 2 に近い（全部 Fable で走っていた区間）
    assert 1.8 <= fr["rate"] / fr["all_rate"] <= 2.6


def test_single_point_falls_back_to_official_ratio(one_point):
    fr = quota.fable_rate(datetime(2026, 9, 3, 3, 40, tzinfo=JST))
    assert fr["source"] == "official"
    assert fr["rate"] == pytest.approx(1.69 / 0.5)


def test_exhaust_time_uses_fable_own_rate(two_points):
    fe = quota.fable_estimate(datetime(2026, 9, 3, 3, 40, tzinfo=JST))
    # 21% @ 22:01 ＋ 22体 × 1.0%/体 ＝ 43%。残り 57% ÷ 3.89 %/時 ＝ 14.6時間
    # → 09/03 18:1x JST（**全モデルの速さで運べば 09/04** ＝ この検査が守っている側）
    assert fe["rate_source"] == "subs"
    assert fe["exhaust_at"].astimezone(JST).strftime("%m/%d %H") == "09/03 18"
    assert 40 <= fe["est"] <= 46


def test_estimate_is_carried_by_subs_not_by_hours(two_points, monkeypatch):
    """**体が 1つも立たない区間では、目盛りは進みません**（`pace()` の 2026-09-06 の決め）。

    2026-09-13 06:2x の実物: `fable_rate` が**前の枠の天井の 2点**（100 → 100）から
    「measured 0.00 %/時」を返し、**推定が目盛りのまま凍って** 親の【枠】の段が
    「Fable のみ いま推定 **0%**」と「いま推定 **14.0%**」を同じ段に並べていた
    （＝ 同じ数の口が 2つ）。**時間で運ぶ形に戻すと、この検査は落ちます。**
    """
    monkeypatch.setattr(quota, "_subs_from_choices", lambda *a, **k: 0)
    fe = quota.fable_estimate(datetime(2026, 9, 3, 3, 40, tzinfo=JST))
    assert fe["est"] == pytest.approx(21.0)      # 5.6時間 経っても 目盛りのまま
    assert quota.fable_ration(datetime(2026, 9, 3, 3, 40, tzinfo=JST))["est"] == fe["est"]


def test_saturated_pair_in_a_past_window_is_not_a_speed(monkeypatch):
    """**天井で貼りついた 2点**（100 → 100）と、**別の枠の 2点**は、速さではありません。

    2026-09-13 06:2x の `data/usage.jsonl` の形（前の枠の 09/11 12:38 と 19:23 が
    どちらも 100%・いまの目盛りは 09/12 07:20 の 0%）。
    """
    rows = [
        {"fetched_at": "2026-09-11T12:38:00+09:00", "window_id": "seven_day",
         "used_percent": 83, "resets_at_iso": "2026-09-11T22:00:00Z", "fable_percent": 100},
        {"fetched_at": "2026-09-11T19:23:00+09:00", "window_id": "seven_day",
         "used_percent": 88, "resets_at_iso": "2026-09-11T22:00:00Z", "fable_percent": 100},
        {"fetched_at": "2026-09-12T07:20:00+09:00", "window_id": "seven_day",
         "used_percent": 0, "resets_at_iso": "2026-09-18T22:00:00Z", "fable_percent": 0},
    ]
    monkeypatch.setattr(quota, "_anchors", lambda: rows)
    monkeypatch.setattr(quota, "pace", lambda now=None: {"carry_rate": 0.0})
    fr = quota.fable_rate(datetime(2026, 9, 13, 6, 30, tzinfo=JST))
    assert fr["source"] == "official"           # measured 0.00 %/時 と言わない


def test_sub_model_switches_to_opus_once_fable_gauge_is_estimated_full(two_points):
    m_before, why_before = quota.sub_model(datetime(2026, 9, 3, 3, 40, tzinfo=JST))
    m_after, why_after = quota.sub_model(datetime(2026, 9, 3, 19, 30, tzinfo=JST))
    assert m_before == "fable" and "100% は 09/03 18:" in why_before, why_before
    assert m_after == "opus" and "新しい画面が来るまで Opus" in why_after


def test_owner_wrapper_agrees_with_sub_model(two_points):
    for when in (datetime(2026, 9, 3, 3, 40, tzinfo=JST), datetime(2026, 9, 3, 19, 30, tzinfo=JST)):
        assert owner.corrected_sub_model(when)[0] == quota.sub_model(when)[0]


def test_owner_wrapper_still_does_not_stop_at_50(two_points, monkeypatch):
    now = datetime(2026, 9, 3, 3, 40, tzinfo=JST)
    g = {"at": now - timedelta(minutes=1), "pct": 50.0, "all_pct": 90.0,
         "resets": now + timedelta(days=1)}
    # 目盛りを差し替えても、運ぶ速さは目盛り自身の速さ（1分で +0.06%）→ 50% は fable のまま
    monkeypatch.setattr(owner.quota, "fable_gauge", lambda: g)
    model, why = owner.corrected_sub_model(now)
    assert model == "fable" and "50%では止めない" in why
