"""役ごとの模型（`quota.role_model`・`quota.ROLE_TIER`）。

2026-09-07 08:1x（optimizer・Fable）に段を組み替えた —— オーナー原文「他モデル活用しないの？」
（受け取り帳 `ef27930d`）。理由と数は `quota.ROLE_TIER` の註・`docs/JOURNAL.md` 09/07 08:1x。

    hourly（台本を持つ・leverage）   100% の1体手前まで Fable（`tests/test_role_model.py`）
    optimizer（other）               Fable の目盛りに関係なく Opus（他モデルの半分を同時に使う）
    定型の役（owner-full・routine）   予備の線 90% 以上 → Opus ／ 未満 → Fable
    役を渡さない呼び                  今までどおり枠の門だけ
    次の周の親（next_round_owner）    同じ答え
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
    m, why = quota.sub_model(role="owner-full")
    assert m == "opus" and "予備の線" in why


def test_routine_role_keeps_fable_below_reserve(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(60.0))
    assert quota.sub_model(role="owner-full")[0] == "fable"


def test_hourly_holds_the_script_so_it_is_fable_until_full(monkeypatch):
    monkeypatch.setattr(quota, "fable_cost_per_sub", lambda now=None: None)
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(97.0))
    m, why = quota.sub_model(role="hourly")
    assert m == "fable" and "高レバレッジ" in why
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(100.0))
    assert quota.sub_model(role="hourly")[0] == "opus"


def test_optimizer_is_opus_regardless_of_fable_gauge(monkeypatch):
    for est in (10.0, 60.0, 97.0):
        monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(est))
        m, why = quota.sub_model(role="optimizer")
        assert m == quota.OTHER_MODEL == "opus" and "他モデル" in why


def test_no_role_is_gate_only(monkeypatch):
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(95.0))
    assert quota.sub_model()[0] == "fable"


def test_owner_wrapper_gives_same_answers(monkeypatch):
    at = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)
    monkeypatch.setattr(quota, "fable_cost_per_sub", lambda now=None: None)
    monkeypatch.setattr(owner.quota, "fable_gauge",
                        lambda: {"pct": 41.0, "at": at, "resets": None})
    monkeypatch.setattr(owner.quota, "fable_estimate", lambda now=None, **kw: _fe(41.0))
    assert owner.corrected_sub_model(role="hourly")[0] == "fable"
    assert owner.corrected_sub_model(role="optimizer")[0] == "opus"
    assert owner.corrected_sub_model(role="owner-full")[0] == "fable"
    assert owner.corrected_sub_model()[0] == "fable"


def test_record_model_choice_has_gate_fields(tmp_path, monkeypatch):
    monkeypatch.setattr(quota, "MODEL_CHOICE_FILE", tmp_path / "mc.jsonl")
    monkeypatch.setattr(quota, "fable_estimate", lambda now=None, **kw: _fe(92.0))
    monkeypatch.setattr(quota, "pace", lambda now=None: {"used_now": 54.5})
    row = quota.record_model_choice("optimizer", "opus", "why")
    for k in ("work_kind", "model", "all_models_week_pct", "fable_only_pct",
              "expected_goal_effect", "why"):
        assert k in row
    assert row["work_kind"] == "optimizer:other" and "他モデル" in row["expected_goal_effect"]
    assert row["all_models_week_pct"] == 54.5 and row["fable_only_pct"] == 92.0
    assert (tmp_path / "mc.jsonl").read_text(encoding="utf-8").count("\n") == 1
