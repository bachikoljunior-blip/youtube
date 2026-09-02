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


@pytest.fixture
def two_points(monkeypatch):
    monkeypatch.setattr(quota, "_anchors", lambda: _rows(True))
    monkeypatch.setattr(quota, "pace", lambda now=None: {"carry_rate": 1.69})


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
    # 21% @ 22:01 + 79% ÷ 3.80 %/時 ＝ 20.8時間 → 09/03 18:4x JST（全モデルの速さなら 09/04）
    assert fe["exhaust_at"].astimezone(JST).strftime("%m/%d %H") == "09/03 18"
    assert 40 <= fe["est"] <= 46


def test_sub_model_switches_to_opus_once_fable_gauge_is_estimated_full(two_points):
    m_before, why_before = quota.sub_model(datetime(2026, 9, 3, 3, 40, tzinfo=JST))
    m_after, why_after = quota.sub_model(datetime(2026, 9, 3, 19, 30, tzinfo=JST))
    assert m_before == "fable" and "100% は 09/03 18:" in why_before
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
