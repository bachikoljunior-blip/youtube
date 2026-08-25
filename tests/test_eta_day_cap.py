"""**段1 を押すのは、出した本数ではなく「再生が付いた本数」**（2026-08-21 16:2x）。

`scripts/eta.py` の `solve_gate1` は長らく `plan_density = PLAN_PUBLISH_PER_DAY`
（25本/日）をそのまま使い、**25本出せば 25本ぶんの登録者が来る**と読んでいました。

実測（`src/day_cap.py`・`data/views.jsonl`）:

    08/20 は 25本 公開して、**#11から先の15本が 0〜3再生**（#10 は 1,111再生）
    時刻ではなく**その日の通し番号**で割れる:
        08/16 の 14時 = #4  → 1,361再生
        08/20 の 14時 = #12 →     0再生

**これが `density` の腕の天井そのものです。** 天井を無視した側へ戻ると、
「本数を増やせば門が開く」と出て、**また在庫の作業へ戻ります**
（`tests/test_eta.py` が守っているのと同じ壊れ方の、別の入口）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_cap_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

from src import day_cap  # noqa: E402


def _a(need=2000.0):
    return {"videos_needed_gate1": need, "days_subs_at": {}, "scale": eta.DEFAULT_SCALE}


def _supply(rate=34.0, stock=36):
    return {"sustained_rate_per_day": rate, "rate_per_day": rate, "stock": stock,
            "novel": 500, "rate": {"thin": False}}


def test_上限を超えた密度は段1を早めない(monkeypatch):
    """**25本/日 と 10本/日 で、段1 の期日が同じであること。**

    上限が 10 なら、11本目から先は 0再生 ＝ 門を1ミリも押しません。
    ここが「25のほうが速い」に戻ったら、天井を素通ししています。
    """
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    at_10 = eta.solve_gate1(_a(), density=10, supply=_supply())["days"]
    at_25 = eta.solve_gate1(_a(), density=25, supply=_supply())["days"]
    at_92 = eta.solve_gate1(_a(), density=92, supply=_supply())["days"]
    assert at_10 == at_25 == at_92, "上限を超えたぶんが門を押しています"


def test_上限を無視した昔の読みより遅くなること(monkeypatch):
    """**直しの向きを固定します。** 天井を入れると期日は必ず**後ろ**へ動きます。

    予測が早まる向きに動いたら、それは直りではなく壊れです。
    """
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    capped = eta.solve_gate1(_a(), density=25, supply=_supply())["days"]
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 1_000)   # 天井なしと同じ
    uncapped = eta.solve_gate1(_a(), density=25, supply=_supply())["days"]
    assert capped > uncapped, "天井を入れたのに期日が早まっています"


def test_上限より低い密度はそのまま通ること(monkeypatch):
    """**天井は上から押さえるだけ。** 4本/日 を 10本/日 に水増ししないこと。"""
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    slow = eta.solve_gate1(_a(), density=4, supply=_supply())["days"]
    fast = eta.solve_gate1(_a(), density=10, supply=_supply())["days"]
    assert slow > fast


def test_段4の月あたり本数も天井を超えないこと(monkeypatch):
    """段4（月20万）は `density_sustained` で数えます。**そこも天井の内側**。"""
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    g1 = eta.solve_gate1(_a(), density=25, supply=_supply(rate=34.0))
    assert g1["density_sustained"] <= 10


# ---------------------------------------------------------------------------
# **天井の表の分母**（2026-08-25 22:4x に直した、最後の1か所）
#
# 08/24 に `solve_gate1` / `days_subs_at` / `physical_caps` は
# **92 → `day_cap.cap()`** へ移りました。**天井の表だけが 92 のまま**でした。
# 92 は API の日枠で、実測は 10本/日。**超えたぶんは 0再生**です。
#
# 直した効果は「長尺がショート並みに伸びたら」の行に出ます:
#     直す前  ¥400 ¥704,352 **届く** ／ ¥1,000 ¥1,760,880 **届く**
#     直した後 ¥400 ¥76,560 届かない ／ ¥1,000 ¥191,400 届かない（¥2,000 だけ届く）
# **「長尺さえ動けばどの帯でも超える」は、92 の産物でした。**
# ---------------------------------------------------------------------------

def _measured(**over):
    base = dict(
        at="2026-08-25T13:00:00+00:00",
        subs_net=19, views_all=65_128, views_7d=35_252, views_28d=55_552,
        views_90d=57_698, subs_gained_28d=19, subs_gained_90d=19,
        long_hours_365=0.6, shorts_views_90d=57_698,
        median_views_per_video=638, videos_with_views_28d=87,
    )
    base.update(over)
    return base


def test_天井の分母は_口の日枠ではなく再生が付く上限(monkeypatch):
    """**`UPLOAD_CAP_PER_DAY`(92) で掛けていないこと。**

    掛けている1本あたり再生は「**再生が付いた本**だけの平均」なので、
    92 を掛けると、付かない 82本まで「付いた本と同じだけ回る」ことになります。
    """
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    a = eta.analyse(_measured())
    assert a["ceiling_per_day"] == 10
    assert a["ceiling_views_month"] == 638 * 10 * 30
    assert a["ceiling_views_month"] != 638 * eta.UPLOAD_CAP_PER_DAY * 30, (
        "API の日枠 92本/日 で天井を立てています（**再生は付きません**）")


def test_要る倍率も同じ分母で割ること(monkeypatch):
    """`per_video_needed` が 92 で割ると、**要る倍率が 9.2分の1 に見えます。**"""
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    a = eta.analyse(_measured())
    need = a["per_video_needed"]["ショート 高"]
    assert need == a["views_needed_month"]["ショート 高"] / (10 * 30)
    assert need != a["views_needed_month"]["ショート 高"] / (eta.UPLOAD_CAP_PER_DAY * 30)


def test_上限が上がれば天井も上がること(monkeypatch):
    """**定数ではありません。** `day_cap` が育てば天井も追います。"""
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    低 = eta.analyse(_measured())["ceiling"]["ショート 高"]
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 20)
    高 = eta.analyse(_measured())["ceiling"]["ショート 高"]
    assert 高 == pytest.approx(低 * 2)


def test_天井は口の日枠を超えないこと(monkeypatch):
    """上限が口より大きく読めても、**出せない本は回りません**。"""
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 1_000)
    a = eta.analyse(_measured())
    assert a["ceiling_per_day"] == eta.UPLOAD_CAP_PER_DAY


def test_長尺がショート並みでも_低い帯は届かないこと(monkeypatch):
    """**この直しの値打ちそのもの。**

    直す前は ¥400 の帯まで「届く」と出ていて、
    「長尺さえ動けばどの帯でも目標を超える」と読めていました。
    """
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    a = eta.analyse(_measured())
    c = a["ceiling_if_shorts_rate"]
    assert c["長尺 お金 低"] < eta.TARGET_YEN
    assert c["長尺 お金 中"] < eta.TARGET_YEN
    assert c["長尺 お金 高"] >= eta.TARGET_YEN
