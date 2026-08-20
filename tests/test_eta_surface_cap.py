"""`scripts/eta.py` —— **段2 と段4 が、測ってある「面」を見ているか。**

## この検査が守っているもの（2026-08-20 23:2x）

前の周の申し送りの①がこれでした ——
**「段4 は今も純長尺 ¥400。実測だと月 639,000再生 要る（1.28倍 甘い）。段2と同時に」。**

`RPM_SCENARIOS["長尺 お金 低"] = 400` は、**再生の 100% が長尺**のときの数です。
ところが長尺のサムネが見せられている面は実測 **37.6回/日**しかなく
（`src/reach_split.py`）、**CTR 100% でも長尺は再生の 13.0% までしか取れません**。
そのときの実効 RPM の天井は **¥313**（`src/rpm_mix.py`）で、**¥400 はその上**です。

段2 も同じ面に乗っています。合格点は「長尺を1日4本・1本あたり 221回」＝ 884回/日 で、
いまの面は CTR 100% でも 37.6回/日 ＝ **23.5倍 足りません。**

**固定するのは次の4つです。**

1. 段4 の RPM が、実測の混ざり方の天井を**越えないこと**（越えたら合格点が甘くなる）
2. 腕 `rpm` を何倍にしても、**面が増えるまでは天井を越えないこと**
3. **測れていないときは、黙って天井へ落ちないこと**（据え置きの帯に戻り、`capped=False`）
4. 天井が足りないとき、**面で埋めるなら何回/日 要るか**を出すこと
   （「届きません」で畳まない。面だけでは埋まらないなら、そう言う）
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_surface_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

# 2026-08-20 の実測（`data/rpm_mix.jsonl` の最後の点）
MIX = {
    "at": "2026-08-20",
    "weight": "views",
    "window": {"start": "2026-05-22", "end": "2026-08-20", "days": 90},
    "views_by_form": {"ショート": 22_549.0, "長尺": 11.0},
    "minutes_by_form": {"ショート": 3_032.0, "長尺": 7.0},
    "rpm_now": 20.185283687943265,
    "rpm_max": 313.0819361995087,
    "factor": 15.510405552858963,
    "long_share_max": 0.13045460628840652,
    "imp_day": 37.588235294117645,
    "why": "長尺の面 37.6回/日 × CTR100% ＝ 再生の 13.0% が上限 → 実効RPM ¥313",
}


def _measured(**over):
    base = dict(
        at="2026-08-19T22:21:32+00:00",
        subs_net=9, views_all=27_806, views_7d=11_324, views_28d=20_332,
        views_90d=22_563, subs_gained_28d=9, subs_gained_90d=11,
        long_hours_365=0.1, shorts_views_90d=22_515,
        views_per_video=952, median_views_per_video=1_041,
        videos_with_views_28d=21,
        long_per_video=2, long_videos_28d=5, long_views_28d=11,
    )
    base.update(over)
    return base


def _plan(monkeypatch, mix=MIX, **over):
    monkeypatch.setattr(eta.rpm_mix, "last", lambda *a, **k: mix)
    m = _measured(**over)
    return eta.plan(m, eta.analyse(m))


# --- 1. 段4 の RPM は、実測の天井を越えない -------------------------------------

def test_段4のRPMは実測の混ざり方の天井で頭打ちになる(monkeypatch):
    """**帯 ¥400 をそのまま当てないこと。** 越えたら、合格点が 1.28倍 甘くなる。"""
    pl = _plan(monkeypatch)
    long = pl["forms"]["長尺 お金"]
    assert long["rpm_band"] == 400, "帯そのものが変わっています（比較の相手が消えます）"
    assert long["capped"] is True
    assert long["rpm"] == MIX["rpm_max"], (
        "段4 の RPM が実測の天井（¥313）になっていません。"
        "**純長尺 ¥400 は「再生の100%が長尺」の数で、面がそれを許していません**"
    )


def test_合格点は帯ではなく天井から出る(monkeypatch):
    """500,000回/月 ではなく 639,000回/月。**この差が 1.28倍 の甘さです。**"""
    pl = _plan(monkeypatch)
    need = pl["forms"]["長尺 お金"]["views_needed_month"]
    assert abs(need - eta.TARGET_YEN * 1000 / MIX["rpm_max"]) < 1.0
    assert 630_000 < need < 645_000, f"要る月間再生が {need:,.0f} 回です（実測なら約 639,000 回）"
    assert need > eta.TARGET_YEN * 1000 / 400, "帯 ¥400 の側（500,000回）に戻っています"


# --- 2. 腕 `rpm` は、面が増えるまで天井を越えない --------------------------------

def test_腕rpmを何倍にしても面が増えるまで天井を越えない(monkeypatch):
    """**ここが抜けると、軌跡が測ってある天井の外へ出ます。**

    `scale` は軌跡が腕を動かすための倍率です。RPM を ×5 しても、
    長尺が再生に占める割合の上限は面（インプレッション）が決めるので、
    **実効 RPM は ¥313 のまま**でなければなりません。
    """
    monkeypatch.setattr(eta.rpm_mix, "last", lambda *a, **k: MIX)
    m = _measured()
    a = eta.analyse(m)
    a["scale"] = dict(eta.DEFAULT_SCALE, rpm=5.0)
    pl = eta.plan(m, a)
    assert pl["forms"]["長尺 お金"]["rpm"] == MIX["rpm_max"]
    assert pl["surface"]["capped"] is True


# --- 3. 測れていないときは、黙って天井へ落ちない ---------------------------------

def test_面が測れていなければ据え置きの帯に戻る(monkeypatch):
    """**測れていない回に、前の回の天井を使い回さないこと。**"""
    pl = _plan(monkeypatch, mix=None)
    long = pl["forms"]["長尺 お金"]
    assert long["capped"] is False
    assert long["rpm"] == 400
    assert pl["surface"]["rpm_cap"] is None
    assert pl["surface"]["long_views_day_cap"] is None


# --- 4. 段2 は、合格点を面と突き合わせる -----------------------------------------

def test_段2は合格点を面と突き合わせる(monkeypatch):
    """段2 の合格点（1日 L本 × 1本あたり）が、面の上限より上なら**そう言うこと**。"""
    pl = _plan(monkeypatch)
    st2 = next(s for s in pl["stages"] if s["no"] == 2)
    assert st2.get("note"), "段2 が面（インプレッション）を一度も見ていません"
    assert "インプレッション" in st2["note"]
    assert "37.6" in st2["note"] or "37" in st2["note"]


def test_段2の注記は面が測れていなければ出ない(monkeypatch):
    """**推測で注記を出さないこと**（面が無いのに「足りません」と言わない）。"""
    pl = _plan(monkeypatch, mix=None)
    st2 = next(s for s in pl["stages"] if s["no"] == 2)
    assert not st2.get("note")


# --- 5. 「届きません」で畳まない（面で埋めるなら何回/日） -------------------------

def test_面だけでは埋まらないならそう言う(monkeypatch):
    """**予測を「届きません」で終わらせない**（オーナー指示 2026-08-20 06:2x）。

    1本あたり 100回 まで落とすと、要る実効 RPM は ¥2,000（帯の上端）を超えます。
    **そのときは「面を増やせば届く」と言ってはいけません** —— 再生の 100% を
    長尺にしても足りないので、1本あたり再生か密度も同時に動かす必要があります。
    """
    pl = _plan(monkeypatch, views_per_video=100)
    assert pl["ceiling_short"] > 1
    sn = pl["surface_needed"]
    assert sn, "天井が足りないのに、面での埋め方が出ていません"
    assert sn["imp_day_now"] == MIX["imp_day"]
    # 要る実効 RPM ＝ 20万 × 1000 ÷ いまの天井（月の再生）
    assert abs(sn["rpm_needed"] - eta.TARGET_YEN * 1000 / (pl["ceiling_day"] * 30)) < 1e-6
    assert sn["rpm_needed"] > eta.RPM_SCENARIOS["長尺 お金 高"]
    assert sn["impossible"] is True
    assert sn["still_short"] > 1
    assert sn["rpm_at_full"] == eta.RPM_SCENARIOS["長尺 お金 高"]


def test_面で埋められる帯なら要るインプレッションが数で出る(monkeypatch):
    """**天井が少しだけ足りない側**では、面の必要量が数で出ること（逆の枝）。"""
    pl = _plan(monkeypatch, views_per_video=400)
    assert pl["ceiling_short"] > 1
    sn = pl["surface_needed"]
    assert sn["impossible"] is False
    assert 0 < sn["share_needed"] < 1
    assert sn["imp_day_needed"] > sn["imp_day_now"]
    assert sn["imp_factor"] > 1
    # 面 ＝ 割合 ÷ (1−割合) × ショートの再生/日（CTR 100% の定義そのもの）
    short_day = MIX["views_by_form"]["ショート"] / MIX["window"]["days"]
    want = sn["share_needed"] / (1 - sn["share_needed"]) * short_day
    assert abs(sn["imp_day_needed"] - want) < 1e-6


def test_天井が足りていれば逆算は出ない(monkeypatch):
    """**要らないときに出さないこと**（画面に嘘の宿題を積まない）。"""
    pl = _plan(monkeypatch)
    assert pl["ceiling_short"] <= 1, "この標本の前提が変わりました（検査のほうを直すこと）"
    assert not pl["surface_needed"]


# --- 6. 踏んだもの: 伸び率が小さすぎて回そのものが落ちた -------------------------

def test_伸び率が極小でも2倍日数で落ちない():
    """`math.log(1 + 1e-18)` は **厳密に 0** で、割ると `ZeroDivisionError`。

    2026-08-20 23:3x に、天井が足りている標本で実際に踏みました
    （`required_growth` が「ほとんど伸びなくても間に合う」帯の値を返す）。
    **予測そのものが落ちるので、無限大（＝2倍にならない）で返すこと。**
    """
    # `log1p` なら丸まらないので、**落ちずに「とてつもなく先」**が返ります
    assert eta.double_days(8.673617379884035e-19) > 1e12
    assert eta.double_days(0) == float("inf")
    assert eta.double_days(-0.1) == float("inf")
    assert 13 < eta.double_days(0.0538) < 14      # 実測 +5.38%/日 ＝ 13日で2倍


# --- 7. 踏んだもの: `--offline` の点が「前の回」になっていた -----------------------

def test_offlineの点は予測の点として数えない(tmp_path, monkeypatch):
    """**印は 875814c が足していました。読む側が1つも無かった。**

    `--offline` は「最後の実測の**写し**をもう一度解く」だけです。
    周の中で直しを確かめるために撃つと、その点が末尾に積まれ、
    **周の終わりの `--reflect` が、自分の debug の点を「前の回」として掴みます。**

    実際にこの回が踏みました —— 前後差が
    **2027-04-06 → 届かない** ではなく **「どちらも届かない」**と出ました。
    **その回の作業ぶんが、まるごと消えます。**
    """
    import json
    log = tmp_path / "eta.jsonl"
    log.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in [
        {"at": "2026-08-20T13:00:00+00:00", "traj_date": "2027-04-06"},
        {"at": "2026-08-20T14:00:00+00:00", "traj_date": "2027-04-06", "offline": True},
        {"at": "2026-08-20T14:30:00+00:00", "kind": eta.REFLECT_KIND},
    ]) + "\n", encoding="utf-8")
    monkeypatch.setattr(eta, "LOG", log)

    pts = eta._points()
    assert [p["at"] for p in pts] == ["2026-08-20T13:00:00+00:00"], (
        "`--offline` の点か、反映の行が、予測の点として数えられています"
    )
    # **写しそのものを読みたいときだけ、明示して取れること**
    assert len(eta._points(offline=True)) == 2
    assert len(eta._points(reflect=True)) == 2
    assert len(eta._points(reflect=True, offline=True)) == 3
