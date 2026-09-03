"""役ごとの模型（`quota.role_model`）。オーナー原文 2026-09-03 07:3x:
「仕事ごとに Fable・Opus・Sonnet・Haiku を選ぶ／Fable のみを 100% に届かせない」。

**覆る条件**: `quota.ROLE_TIER` の註。
"""
from datetime import datetime, timedelta, timezone

from scripts import quota

JST = timezone(timedelta(hours=9))


def _fe(est, rate=6.0, hours_to_reset=46.0, now=None):
    now = now or datetime.now(timezone.utc)
    return {"gauge": {"at": now - timedelta(hours=1), "pct": est, "all_pct": 45.0,
                      "resets": now + timedelta(hours=hours_to_reset)},
            "rate": rate, "rate_source": "measured", "est": est,
            "exhaust_at": now + timedelta(hours=(100 - est) / rate), "stale_hours": 1.0}


def _wire(monkeypatch, est, per_sub=1.8, hours_to_reset=46.0, gate=("fable", "ok")):
    monkeypatch.setattr(quota, "sub_model", lambda now=None: gate)
    monkeypatch.setattr(quota, "fable_estimate",
                        lambda now=None, gauge=None: _fe(est, hours_to_reset=hours_to_reset))
    monkeypatch.setattr(quota, "fable_cost_per_sub", lambda now=None: per_sub)


def test_record_role_is_always_light(monkeypatch):
    _wire(monkeypatch, est=10.0)
    assert quota.role_model("owner-record")[0] == "sonnet"


def test_plenty_left_both_roles_fable(monkeypatch):
    # 残り 90%・戻りまで 2時間 に 12% 要る → 両役とも Fable
    _wire(monkeypatch, est=10.0, hours_to_reset=2.0)
    assert quota.role_model("hourly")[0] == "fable"
    assert quota.role_model("optimizer")[0] == "fable"


def test_scarce_hourly_goes_opus_optimizer_keeps_fable(monkeypatch):
    # 09/03 09:2x の実物: 推定 90%・残り 10%・戻りまで 46時間（両役で 273% 要る）
    _wire(monkeypatch, est=90.0, hours_to_reset=46.0)
    m_h, why_h = quota.role_model("hourly")
    m_o, _ = quota.role_model("optimizer")
    assert m_h == "opus" and "optimizer" in why_h
    assert m_o == "fable"


def test_last_round_does_not_cross_100(monkeypatch):
    # 残り 1%・サブ1体 1.8% → optimizer も opus（100% を越えて落とさない）
    _wire(monkeypatch, est=99.0)
    assert quota.role_model("optimizer")[0] == "opus"
    assert quota.role_model("hourly")[0] == "opus"


def test_gate_wins_when_not_fable(monkeypatch):
    _wire(monkeypatch, est=10.0, gate=("opus", "100% 到達"))
    assert quota.role_model("hourly") == ("opus", "100% 到達")
    assert quota.role_model("optimizer") == ("opus", "100% 到達")
    assert quota.role_model("owner-record")[0] == "sonnet"


def test_go_prints_model_per_role(monkeypatch, capsys):
    from scripts import next_round
    _wire(monkeypatch, est=90.0, hours_to_reset=46.0)
    monkeypatch.setattr(next_round, "decide", lambda **kw: {
        "go": True, "roles": list(next_round.ROLES), "why": "test", "live": 0,
        "live_source": "test", "floor_min": 140.0, "source": "test"})
    monkeypatch.setattr("sys.argv", ["next_round.py", "--live", "0"])
    try:
        next_round.main()
    except SystemExit:
        pass
    out = capsys.readouterr().out
    assert 'model: "opus" ← `kind: hourly`' in out
    assert 'model: "fable" ← `kind: optimizer`' in out
