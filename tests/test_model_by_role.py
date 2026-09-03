"""役ごとの模型と予備の線（オーナー原文 2026-09-03 07:3x・`quota.role_model`）。

    定型の役（hourly）        予備の線 90% 以上 → Opus ／ 未満 → Fable
    高レバレッジ（optimizer）  100% まで Fable
    役を渡さない呼び          今までどおり枠の門だけ
    次の周の親（next_round_owner）も同じ答え
"""
from datetime import datetime, timezone

from scripts import next_round_owner as owner
from scripts import quota


def _fe(est: float):
    at = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)
    return {"gauge": {"pct": est, "at": at, "resets": None}, "rate": 0.0,
            "rate_source": "measured", "est": est, "exhaust_at": None, "stale_hours": 0.0}


def test_routine_role_yields_to_opus_above_reserve(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(92.0))
    m, why = quota.sub_model(role="hourly")
    assert m == "opus" and "予備の線" in why


def test_routine_role_keeps_fable_below_reserve(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(60.0))
    assert quota.sub_model(role="hourly")[0] == "fable"


def test_leverage_role_keeps_fable_until_full(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(97.0))
    m, why = quota.sub_model(role="optimizer")
    assert m == "fable" and "高レバレッジ" in why
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(100.0))
    assert quota.sub_model(role="optimizer")[0] == "opus"


def test_no_role_is_gate_only(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(95.0))
    assert quota.sub_model()[0] == "fable"


def test_owner_wrapper_applies_same_reserve(monkeypatch):
    at = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(owner.quota, "fable_gauge",
                        lambda: {"pct": 93.0, "at": at, "resets": None})
    monkeypatch.setattr(owner.quota, "fable_estimate", lambda now=None, **kw: _fe(93.0))
    assert owner.corrected_sub_model(role="hourly")[0] == "opus"
    assert owner.corrected_sub_model(role="optimizer")[0] == "fable"
    assert owner.corrected_sub_model()[0] == "fable"


def test_record_model_choice_has_gate_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", tmp_path / "mc.jsonl")
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(92.0))
    monkeypatch.setattr(quota, "pace", lambda now=None: {"used_now": 54.5})
    row = quota.record_model_choice("hourly", "opus", "why")
    for k in ("work_kind", "model", "all_models_week_pct", "fable_only_pct",
              "expected_goal_effect", "why"):
        assert k in row
    assert row["all_models_week_pct"] == 54.5 and row["fable_only_pct"] == 92.0
    assert (tmp_path / "mc.jsonl").read_text(encoding="utf-8").count("\n") == 1
