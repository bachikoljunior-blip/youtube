"""役ごとの模型に、09/03 09:5x の optimizer が重ねた2点（`quota.role_model` の註）:

    高レバレッジ（optimizer）  1体ぶん（`fable_cost_per_sub`）を足して 100% に届くなら Opus
    軽い役（owner-record）     Fable の残りに関係なく `LIGHT_MODEL`（sonnet）

本体の線（定型の役は予備の線 90%）は `tests/test_model_by_role.py`。
**覆る条件**: `quota.ROLE_TIER` の註。
"""
from datetime import datetime, timezone

from scripts import next_round_owner as owner
from scripts import quota


def _fe(est: float):
    at = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)
    return {"gauge": {"pct": est, "at": at, "resets": None}, "rate": 0.0,
            "rate_source": "measured", "est": est, "exhaust_at": None, "stale_hours": 0.0}


def test_leverage_role_stops_one_sub_short_of_100(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(99.0))
    monkeypatch.setattr(quota, "fable_cost_per_sub", lambda now=None: 1.8)
    m, why = quota.sub_model(role="optimizer")
    assert m == "opus" and "100% を越えて落とさない" in why


def test_leverage_role_keeps_fable_when_one_sub_fits(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(97.0))
    monkeypatch.setattr(quota, "fable_cost_per_sub", lambda now=None: 1.8)
    assert quota.sub_model(role="optimizer")[0] == "fable"


def test_unknown_cost_does_not_block(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(99.0))
    monkeypatch.setattr(quota, "fable_cost_per_sub", lambda now=None: None)
    assert quota.sub_model(role="optimizer")[0] == "fable"


def test_record_role_is_light(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(10.0))
    assert quota.sub_model(role="owner-record")[0] == quota.LIGHT_MODEL == "sonnet"
    at = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(owner.quota, "fable_gauge",
                        lambda: {"pct": 10.0, "at": at, "resets": None})
    assert owner.corrected_sub_model(role="owner-record")[0] == "sonnet"


def test_cost_per_sub_is_delta_over_births(monkeypatch):
    at = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(quota, "fable_rate", lambda now=None, anchors=None: {
        "rate": 6.0, "source": "measured", "from_at": at, "to_at": at,
        "from_pct": 60.0, "to_pct": 71.0})
    monkeypatch.setattr(quota, "_births_from_runs", lambda a, b: 11)
    assert abs(quota.fable_cost_per_sub() - 1.0) < 1e-9
