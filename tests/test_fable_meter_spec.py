from datetime import datetime, timedelta, timezone

from scripts import next_round_owner as owner


def _gauge(pct: float) -> dict:
    now = datetime.now(timezone.utc)
    return {
        "at": now - timedelta(minutes=1),
        "pct": pct,
        "all_pct": 90.0,  # 全モデル目盛りはFable到達判定に直結させない
        "resets": now + timedelta(days=1),
    }


def test_official_share_and_ui_full_scale():
    assert owner.OFFICIAL_FABLE_SHARE_OF_REGULAR_WEEK == 0.50
    assert owner.FABLE_ONLY_GAUGE_FULL_PCT == 100.0


def test_fable_only_50_percent_is_still_available(monkeypatch):
    monkeypatch.setattr(owner.quota, "fable_gauge", lambda: _gauge(50.0))
    model, why = owner.corrected_sub_model()
    assert model == "fable"
    assert "50%では止めない" in why


def test_all_models_50_percent_is_not_the_switch(monkeypatch):
    row = _gauge(12.0)
    row["all_pct"] = 50.0
    monkeypatch.setattr(owner.quota, "fable_gauge", lambda: row)
    model, _ = owner.corrected_sub_model()
    assert model == "fable"


def test_fable_only_100_percent_exhausts_included_fable_share(monkeypatch):
    monkeypatch.setattr(owner.quota, "fable_gauge", lambda: _gauge(100.0))
    model, why = owner.corrected_sub_model()
    assert model == "opus"
    assert "内訳上限100%" in why
