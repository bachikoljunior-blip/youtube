"""**Fable を枠の終わりまで配る線**（`quota.fable_ration` / `quota.role_model`）。

2026-09-11 19:5x・optimizer・Opus。オーナー原文（受け取り帳 `c2d075b2`・`06fec2ad`）:

    「リセットされたらfableにするよな？フェイブルずっと使えるように調整するよな？」
    「ずっと使えるように調整すんの？」

同じ問いは 09/03 07:3x に既に在り（「Fableのみは100％到達になって使えなくなるように
ならないほうが良くない？」）、**2枠 続けて守れていません**（実測 `data/usage.jsonl`:
この枠は リセットの **18.4時間 前**・前の枠は **15.3時間 前**に 100%）。

**なぜ既存の門では止まらないか**: `FABLE_CAP_PCT` も `FABLE_RESERVE_PCT` も
`fable_cost_per_sub` も **崖の手前で止める門**で、崖に着く**時刻**は動かしません。
崖で止めれば落ちないだけで、そのあとずっと Fable は使えません。

**きょうの状態を不変条件として書かないこと**（METHOD §5 教訓の形 6つ目）＝
この検査は実物の目盛りを1つも読まず、目盛りも刻もその場で組みます。

**陽性対照**（`.pyc` を消してから撃った・教訓の形 3つ目）:
`role_model` の配りの枝を外すと **2件**／`fable_ration` の枠の巻き直し（`rolled`）を
外すと **2件**／線を `100.0` 固定にすると **4件** 落ちる。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts import next_round_owner as owner
from scripts import quota

WEEK = quota.FABLE_WINDOW_HOURS


def _gauge(pct: float, resets, at: datetime) -> dict:
    return {"pct": pct, "at": at, "all_pct": 0.0, "resets": resets}


def _no_subs(monkeypatch) -> None:
    """目盛りの後に立った fable のサブは 0体（台帳を読ませない）。"""
    monkeypatch.setattr(quota, "_subs_from_choices", lambda *a, **kw: 0)
    monkeypatch.setattr(quota, "fable_cost_per_sub", lambda *a, **kw: None)


def test_線は枠の頭から終わりまでの直線(monkeypatch) -> None:
    _no_subs(monkeypatch)
    resets = datetime(2026, 9, 12, 7, 0, tzinfo=quota.JST)
    now = resets - timedelta(hours=WEEK / 2)
    r = quota.fable_ration(now, gauge=_gauge(50.0, resets, now))
    assert r is not None
    assert abs(r["line"] - 50.0) < 0.01
    assert r["over"] is False


def test_線の上なら_hourly_も_opus(monkeypatch) -> None:
    """**これが本体** —— 崖（100%）にはまだ遠いのに、線の上なら Opus。

    陽性対照: `role_model` の配りの枝を外すと落ちる。
    """
    _no_subs(monkeypatch)
    resets = datetime(2026, 9, 12, 7, 0, tzinfo=quota.JST)
    now = resets - timedelta(hours=WEEK / 2)
    g = _gauge(70.0, resets, now)
    monkeypatch.setattr(quota, "fable_gauge", lambda: g)
    monkeypatch.setattr(quota, "fable_estimate", lambda *a, **kw: {
        "gauge": g, "rate": 0.0, "rate_source": "measured", "est": 70.0,
        "exhaust_at": None, "stale_hours": 0.0})
    m, why = quota.sub_model(now, "hourly")
    assert m == "opus"
    assert "配りの線" in why and "この周は Opus" in why
    assert "100% を越えて落とさない" not in why


def test_線の下なら_hourly_は_fable(monkeypatch) -> None:
    _no_subs(monkeypatch)
    resets = datetime(2026, 9, 12, 7, 0, tzinfo=quota.JST)
    now = resets - timedelta(hours=WEEK / 2)
    g = _gauge(30.0, resets, now)
    monkeypatch.setattr(quota, "fable_gauge", lambda: g)
    monkeypatch.setattr(quota, "fable_estimate", lambda *a, **kw: {
        "gauge": g, "rate": 0.0, "rate_source": "measured", "est": 30.0,
        "exhaust_at": None, "stale_hours": 0.0})
    m, why = quota.sub_model(now, "hourly")
    assert m == "fable" and "配りの線" in why


def test_リセットされたら_fable_に戻る_かつ配りも始まる(monkeypatch) -> None:
    """オーナーの問いの**両側**（前半 ＝ fable へ戻す・後半 ＝ ずっと使えるように配る）。

    **前の目盛りは 100% のまま**（画面は人手でしか入らない）。それでも枠が戻っていれば
    新しい枠の頭は前の `resets` そのものなので、**画面を待たずに** 0% から配れます。
    陽性対照: `fable_ration` の巻き直し（`rolled`）を外すと落ちる。
    """
    _no_subs(monkeypatch)
    resets = datetime(2026, 9, 12, 7, 0, tzinfo=quota.JST)
    now = resets + timedelta(hours=1)
    g = _gauge(100.0, resets, resets - timedelta(hours=12))
    monkeypatch.setattr(quota, "fable_gauge", lambda: g)
    monkeypatch.setattr(owner.quota, "fable_gauge", lambda: g)

    r = quota.fable_ration(now, gauge=g)
    assert r is not None and r["rolled"] is True
    assert r["est"] == 0.0 and r["line"] < 1.0 and r["over"] is False
    assert r["resets"] == resets + timedelta(hours=WEEK)

    assert owner.corrected_sub_model(now, "hourly")[0] == "fable"
    monkeypatch.setattr(quota, "fable_estimate", lambda *a, **kw: {
        "gauge": g, "rate": 0.0, "rate_source": "reset", "est": 100.0,
        "exhaust_at": None, "stale_hours": 0.0})
    assert quota.sub_model(now, "hourly")[0] == "fable"


def test_リセット直後でも_使いすぎたら_opusへ倒す(monkeypatch) -> None:
    """**戻った枠でも線は効くこと** —— 素の `"fable"` を返す形に戻ったら落ちます。"""
    monkeypatch.setattr(quota, "fable_cost_per_sub", lambda *a, **kw: 1.0)
    monkeypatch.setattr(quota, "_subs_from_choices", lambda *a, **kw: 20)
    resets = datetime(2026, 9, 12, 7, 0, tzinfo=quota.JST)
    now = resets + timedelta(hours=1)
    g = _gauge(100.0, resets, resets - timedelta(hours=12))
    monkeypatch.setattr(quota, "fable_gauge", lambda: g)
    monkeypatch.setattr(owner.quota, "fable_gauge", lambda: g)
    r = quota.fable_ration(now, gauge=g)
    assert r["est"] == 20.0 and r["over"] is True
    assert owner.corrected_sub_model(now, "hourly")[0] == "opus"


def test_optimizerは配りに関係なく_opus(monkeypatch) -> None:
    """`ROLE_TIER` の `other` は Fable の目盛りに関係なく Opus（§5・09/07 08:1x）。"""
    _no_subs(monkeypatch)
    resets = datetime(2026, 9, 12, 7, 0, tzinfo=quota.JST)
    now = resets - timedelta(hours=WEEK / 2)
    g = _gauge(10.0, resets, now)
    monkeypatch.setattr(quota, "fable_gauge", lambda: g)
    monkeypatch.setattr(quota, "fable_estimate", lambda *a, **kw: {
        "gauge": g, "rate": 0.0, "rate_source": "measured", "est": 10.0,
        "exhaust_at": None, "stale_hours": 0.0})
    assert quota.sub_model(now, "optimizer")[0] == "opus"


def test_目盛りに_resets_が無ければ_線は何も言わない(monkeypatch) -> None:
    """**古い呼び（`resets` を持たない目盛り）を黙って倒さないこと。**"""
    _no_subs(monkeypatch)
    at = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)
    assert quota.fable_ration(at, gauge=_gauge(97.0, None, at)) is None
    assert quota.fable_ration_words(None) == ""


def test_役の段は_呼ぶ側が渡した目盛りだけを見る(monkeypatch) -> None:
    """**`role_model` の中で `fable_ration()` を呼ばないこと**（§5 教訓の形 1つ目の族）。

    呼ぶ側が差し替えた目盛りと、実物の `data/usage.jsonl` の 2つ を読むと、
    **同じ問いに違う答え**が出ます（この回に 1度 踏み、検査 5件 が赤くなった）。
    """
    def _boom(*a, **kw):
        raise AssertionError("role_model が自分で fable_ration を呼んでいる")
    monkeypatch.setattr(quota, "fable_ration", _boom)
    m, why = quota.role_model("fable", "why", 50.0, "hourly", None)
    assert m == "fable" and "配りの線" not in why


# ---------------------------------------------------------------------------
# **親の【枠】の段は、この線を「道具の字のまま」運ぶこと**
# （§5 教訓の形 7つ目 —— 註と印字が食い違えば、読まれるのは印字のほう）
# ---------------------------------------------------------------------------


def test_親の枠の段が_配りの行を運ぶ(monkeypatch) -> None:
    import sys
    import types

    from scripts import spawn_prompt as sp

    mod = types.ModuleType("quota_stub")
    mod.JST = quota.JST
    mod.fable_ration = lambda *a, **kw: {"x": 1}
    mod.fable_ration_words = lambda r: "配りの線 10.0% 対 いま推定 5.0% ＝ 線の下 → Fable"
    for name in ("scripts.quota", "quota"):
        monkeypatch.setitem(sys.modules, name, mod)
    assert "配りの線" in sp._fable_ration_words()


def test_古い_quota_でも親を止めない(monkeypatch) -> None:
    """**`fable_ration` を持たない `quota` でも空を返すだけ**（親は落ちない）。"""
    import sys
    import types

    from scripts import spawn_prompt as sp

    mod = types.ModuleType("quota_stub")
    mod.JST = quota.JST
    for name in ("scripts.quota", "quota"):
        monkeypatch.setitem(sys.modules, name, mod)
    assert sp._fable_ration_words() == ""
