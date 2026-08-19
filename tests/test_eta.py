"""`scripts/eta.py` —— 月20万に届く日の予測。

**この検査が守っているのは「予測が出ること」ではありません。**
守っているのは、**天井の判定が本数では動かないこと**です。

2026-08-19 の実測で、`1本1,092回 × 92本/日` の上限が
ショート RPM ¥35 で月10.5万円にしかならないことが分かりました。
**本数を増やしても、在庫を増やしても、この数字は動きません。**
ここが逆向きに壊れると（本数を増やせば届くと出ると）、
**また15周ぶん在庫の作業に戻ります。**
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _measured(**over):
    """2026-08-19 の実測をそのまま置く（数字を変える検査は over で上書きする）。"""
    base = dict(
        at="2026-08-19T02:30:00+00:00",
        subs_net=9,
        views_all=27_484,
        views_7d=11_002,
        views_28d=20_010,
        views_90d=22_241,
        subs_gained_28d=9,
        subs_gained_90d=11,
        long_hours_365=0.1,
        shorts_views_90d=22_222,
        median_views_per_video=1_092,
        videos_with_views_28d=20,
    )
    base.update(over)
    return base


def test_門の順は_登録者ではなく視聴時間のほうが遠い():
    """**門1より門2のほうが遠い。** ここを取り違えると「登録者を増やせば通る」になる。"""
    a = eta.analyse(_measured())
    assert a["days_subs"] < a["days_long_hours"]
    assert a["days_shorts_gate"] >= eta.NEVER
    # 収益化は「門1 と 門2の速いほう」の両方が要る＝遅いほうで決まる
    assert a["days_monetized"] == a["days_long_hours"]


def test_登録率は実測から出る():
    a = eta.analyse(_measured())
    assert a["sub_rate"] == pytest.approx(9 / 20_010)
    # 予測には速いほう（直近7日）を使う。伸びている最中に遅いほうで測ると悲観に倒れる
    assert a["views_per_day"] == pytest.approx(11_002 / 7)


def test_天井は本数では動かない():
    """**この検査が本体です。** 在庫や本数の作業は、天井を1円も上げません。"""
    a = eta.analyse(_measured())
    ceiling_short = a["ceiling"]["ショート 中"]
    assert ceiling_short < eta.TARGET_YEN, "ショートの上限が目標に届くなら、前提が変わっている"
    # 1本あたりの再生を据え置いたまま「本数が2倍出せるようになった」としても、
    # 上限は UPLOAD_CAP_PER_DAY で頭打ちなので、天井は同じ数字のまま
    a2 = eta.analyse(_measured(views_7d=22_004, views_28d=40_020))
    assert a2["ceiling"]["ショート 中"] == ceiling_short


def test_天井を動かすのは1本あたり再生と_RPM_の2つだけ():
    base = eta.analyse(_measured())["ceiling"]["ショート 中"]
    より上 = eta.analyse(_measured(median_views_per_video=2_184))["ceiling"]["ショート 中"]
    assert より上 == pytest.approx(base * 2)
    # RPM は表そのもの。長尺の帯なら同じ再生数で桁が変わる
    a = eta.analyse(_measured())
    assert a["ceiling"]["長尺 お金 中"] > eta.TARGET_YEN


def test_増えていない数字は_届かない_と出る():
    """0 で割って例外にしないこと。**予測で回を止めない。**"""
    a = eta.analyse(_measured(subs_gained_28d=0, long_hours_365=0.0))
    assert a["days_subs"] >= eta.NEVER
    assert a["days_long_hours"] >= eta.NEVER
    assert "届きません" in eta._fmt_days(a["days_subs"])


def test_門を通り越した数字は_通過済み_と出る():
    a = eta.analyse(_measured(subs_net=1_200))
    assert a["subs_remaining"] == 0
    assert a["days_subs"] == 0
    assert "通過済み" in eta._fmt_days(a["days_subs"])


def test_報告は例外を出さずに全部の行を出す():
    m = _measured()
    a = eta.analyse(m)
    m["per_video_now"] = a["per_video_now"]
    lines = eta.report(m, a)
    text = "\n".join(lines)
    assert "月20万円に、いつ届くか" in text
    # **ショートの帯は必ず「届かない」側に名指しされること。** ここが本体
    assert "ショート 中" in text
    assert "1日の上限まで出しても月20万に届かない帯" in text
    assert "ショート 低" in text.split("届かない帯")[1].split("\n")[0]


def test_百年より先は日付を書かない():
    """`date` の上限を超えると例外になる。**予測で回を止めない**（8/19 に踏んだ）。"""
    assert "年後" in eta._fmt_days(40_000 * 365)
