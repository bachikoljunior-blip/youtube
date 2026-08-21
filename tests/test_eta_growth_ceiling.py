"""**13倍の開きを埋めていたのは、伸び率ではなく天井のほうだった。**

## 何を判定したか（2026-08-20 20:0x・オーナー経由の指摘3点）

    ① 段4（月20万）の期日が「門＋30日」に張り付いている        → **半分外れ**
    ② `density_month` が 25.0 に戻っている                     → **当たり**
    ③ `growth_per_day 0.0538` の複利が 13倍を埋めている        → **外れ**

**③ が外れである理由が、この検査です。** 指摘は「100日 複利で約180倍。
13倍はこの1つの仮定で埋まる。**無いなら頭打ちを入れること**」でしたが、
`solve_revenue_day` は毎日 `v = min(v * (1 + growth), cap)` を当てており、
**頭打ちはもう在ります**（`cap` ＝ 天井 ＝ 密度 × 1本あたり再生）。
実測の点では 55日目に天井へ着いてそこで止まるので、**180倍は起きません。**

伸び率に**時間の**頭打ちを足すと、天井と二重に縛ることになり、
`plan()` は入力を問わず `NEVER` を返しました（この5ファイルで検査10件が落ちた）。
それは「**予測を届きませんで終わらせない**」（オーナー 2026-08-20 06:2x）に反します。

**ではなぜ 13倍が埋まって見えたか。** 天井の密度が
`min(25, 3.3時間の実測 36.5) = 25` になっていたからです（＝②）。
直すと天井は 1日 23,075回 → **3,230回**に落ち、**伸び率は1つも触らないまま**
到達日が「届かない」に変わります。**下の最後の2件がそれを固定しています。**

**覆る条件**: 天井が「水準」だけでなく「速さ」まで決めるようになったら
（例: 密度を時間の関数にしたら）、伸び率の側にも時間の制限が要ります。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("_eta_growth_ceiling", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

import _eta_pin  # noqa: E402


# --- **天井は2つあり、どちらもこの file の主題ではありません**（2026-08-22 に足した）---
#
# ここが測っているのは「伸び率と天井のどちらが13倍を埋めたか」で、
# **天井の値そのものではありません。** ところが `plan()` は
# `src/day_cap.cap()`（1日に再生が付く本数）と `src/rpm_mix.last()`（実効 RPM）を
# 実測から直に読むので、**こちらが1回測るたびに合成データが帯から外れます** ——
# 08/21 の day_cap 実測（25→17本/日）で `density_month` が 25.0 → 17.0 になり、
# 「直す前の姿」を再現する検査が落ちました（`tests/_eta_pin.py` に全文）。
@pytest.fixture(autouse=True)
def _天井は主題ではない(monkeypatch):
    _eta_pin.pin_ceilings(monkeypatch, eta.PLAN_PUBLISH_PER_DAY)


def _trailing30(views_day_now: float, growth: float, cap: float, days: int) -> float:
    """`solve_revenue_day` と同じ歩き方で、`days` 日目の直近30日合計を出す。"""
    v = min(views_day_now, cap)
    window = [v] * 30
    total = v * 30
    for _ in range(days):
        v = min(v * (1 + growth), cap)
        total += v - window.pop(0)
        window.append(v)
    return total


# ---------------------------------------------- ③ 頭打ちは在る（＝指摘は外れ）

def test_伸び率をいくら上げても天井の30日ぶんを超えない():
    """**これが「頭打ちが無い」の反証です。**

    1日 +100%（＝毎日2倍）を1年ぶん歩かせても、直近30日の合計は
    `天井 × 30` を1回も超えません。**180倍は出ません。**
    """
    cap = 3_230.5
    for days in (10, 55, 100, 365):
        assert _trailing30(1_257.4, 1.0, cap, days) <= cap * 30 + 1e-6


def test_天井の30日ぶんが足りないなら伸び率は関係ない():
    """**伸び率の問題ではなく形の問題**。ここで要るのは「待つ」ではありません。"""
    cap = 3_230.5                       # 密度 3.5本 × 1本 923回
    need = 500_000.0                    # RPM ¥400 で月20万に要る再生
    assert cap * 30 < need
    for g in (0.0538, 0.5, 1.0):
        assert eta.solve_revenue_day(1_257.4, g, cap, need) >= eta.NEVER


def test_天井に着いたらそこで止まる():
    """実測の点（伸び 5.38%／日・天井 23,075回）では **55日目**に着きます。"""
    g, cap = 0.05382775482818136, 923.0 * 25
    v = 1_257.4285714285713
    days = 0
    while v < cap and days < 3_650:
        v = min(v * (1 + g), cap)
        days += 1
    assert days == 56, days                      # 56日目に天井へ乗る
    assert v == pytest.approx(cap)
    # その先は何日歩いても伸びない ＝ **複利は止まっている**
    assert min(v * (1 + g), cap) == pytest.approx(cap)


# ------------------------------------ ② 天井のほうが 13倍を埋めていた（＝当たり）

def _metrics() -> dict:
    """2026-08-20 の実測と同じ側に置いた1点（`data/eta.jsonl` の最新点）。"""
    return {
        "views_7d": 8_802, "views_28d": 20_303,
        "subs_gained_28d": 9, "subs_net": 9,
        "long_hours_365": 0.1, "shorts_views_90d": 22_515,
        "views_per_video": 923, "median_views_per_video": 1_041,
        "long_per_video": 2, "long_videos_28d": 5, "long_views_28d": 11,
    }


def _supply(rate: float, sustained: float | None) -> dict:
    return {"stock": 26, "novel": 502, "rate_per_day": rate,
            "rate": {"per_day": rate, "thin": True, "sustained": False, "hours": 3.3},
            "sustained_rate_per_day": sustained,
            "sustained_basis": "実際に公開になった本数（4日の実測）",
            "measured": True, "sweep_age_hours": 1.0}


def test_バーストの速さを入れると13倍が埋まってしまう():
    """**直す前の姿**。3.3時間で +5本 ＝ 1日 36.5本 を入れると、

        density_month = min(25, 36.5) = **25.0**   ← 外させたはずの 25 が戻る
        天井 = 923回 × 25本 = 1日 23,075回 ＝ 月 692,250回 > 要る 500,000回

    ——**伸び率を1つも触らずに、13倍の開きが埋まります。**
    """
    m = _metrics()
    a = eta.analyse(m)
    pl = eta.plan(m, a, supply=_supply(36.53, 36.53))
    assert pl["density_month"] == pytest.approx(25.0)
    assert pl["days_revenue"] < eta.NEVER
    assert pl["binding"] == "収益化の門＋その後の30日"


def test_1日続く速さを入れると同じ伸び率のまま届かなくなる():
    """**直した後**。伸び率は上と**まったく同じ**です。動かしたのは天井だけ。"""
    m = _metrics()
    a = eta.analyse(m)
    burst = eta.plan(m, a, supply=_supply(36.53, 36.53))
    fixed = eta.plan(m, a, supply=_supply(36.53, 3.5))
    assert burst["growth"]["g"] == pytest.approx(fixed["growth"]["g"])
    assert fixed["density_month"] == pytest.approx(3.5)
    assert fixed["ceiling_day"] < burst["ceiling_day"]
    assert fixed["days_revenue"] >= eta.NEVER
    assert fixed["binding"] == "再生数が天井に当たっている"


def test_持続する速さが無い回は25の写しに戻らずに未検証だと言う():
    """**測れないときに 25 を黙って使わないこと**（2026-08-20 16:0x の穴）。"""
    m = _metrics()
    a = eta.analyse(m)
    g1 = eta.solve_gate1(a, density=eta.PLAN_PUBLISH_PER_DAY,
                         supply=_supply(36.53, None))
    assert g1["measured"] is False
