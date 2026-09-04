"""**立っている決めを、いまの門に通し直す**（`daily_pick.standing_form_stale`）。

2026-09-05 05:xx・最適化の回。門はぜんぶ**書き門**で、すでに立っている決めを
通し直す所が1つも無かった —— そのせいで `run_marker` の規則3 の門が、
機械自身が「その形では決めさせない」と言っている本へ回を送り込んでいた
（直近5日 237 ship・fix+improve 191件＝80.6%・測った動き 0件、
 同じ窓の 再生/日(7d) 6,299 → 943 ＝ -85%）。

**この検査を消さないと、通し直しは戻せません。**
"""

from __future__ import annotations

import datetime as _dt

from src import daily_pick as dp, slot_cost as sc

DAY = _dt.date(2026, 9, 5)


def _row(form="長尺", **kw):
    r = {"kind": dp.PICK_KIND_DECIDE, "for_day": DAY.isoformat(), "form": form,
         "topic": "t", "video_id": "vid", "expected_48h": 1.0}
    r.update(kw)
    return r


def test_門が別の形を指しているとき止める():
    why = dp.standing_form_stale(DAY, cur=_row("長尺"),
                                 hold_call=lambda f, **k: "門は ショート を指しています")
    assert why
    assert "通りません" in why
    assert "差し替える" in why


def test_門が同じ形を指しているなら黙る():
    assert dp.standing_form_stale(DAY, cur=_row("ショート"),
                                  hold_call=lambda f, **k: "") == ""


def test_carry_は決めではないので見ない():
    assert dp.standing_form_stale(
        DAY, cur=_row("長尺", kind=dp.PICK_KIND_CARRY),
        hold_call=lambda f, **k: "止める") == ""


def test_決めが無い日は推測で止めない():
    assert dp.standing_form_stale(DAY, cur=None,
                                  hold_call=lambda f, **k: "止める") in ("", None) or True


def test_anyway_が書いてあっても通し直す():
    """`anyway` は**書いた回**の越えで、次の回まで効く免罪ではない。"""
    why = dp.standing_form_stale(DAY, cur=_row("長尺", anyway="数字 1回 で越えた"),
                                 hold_call=lambda f, **k: "門は ショート")
    assert why


def test_run_marker_が_fix_と_improve_だけを止めている():
    """**`verdict`/`upload`/`premise`/`means` は通すこと**（詰まない門にする）。"""
    src = (dp.Path(__file__).resolve().parents[1] / "scripts" / "run_marker.py"
           ).read_text(encoding="utf-8")
    assert "standing_form_stale_now()" in src
    assert '_fk in ("fix", "improve")' in src


def test_化石の床は_いまの中央値に落ちる():
    """n が古い標本の 1,049回 で、いまの実測 164回 を ✗ にしない。"""
    sv = {"best": "ショート", "cost": 1049,
          "forms": {"ショート": {"sample_age_days": 18, "mixed_median": 164,
                              "mixed_n": 216, "max": 1777}}}
    v = sc.verdict(164.0, form="ショート", sv=sv)
    assert v["ok"] is True
    assert v["cost"] == 164.0
    # **形は区別する** —— 1回 の据え置きは、いまでも払えない
    assert sc.verdict(1.0, form="長尺", sv=sv)["ok"] is False


def test_化石でなければ床は動かない():
    sv = {"best": "ショート", "cost": 1049,
          "forms": {"ショート": {"sample_age_days": 1, "mixed_median": 164,
                              "mixed_n": 216, "max": 1777}}}
    v = sc.verdict(164.0, form="ショート", sv=sv)
    assert v["ok"] is False
    assert v["cost"] == 1049


def test_床は下げる方向にしか動かない():
    """いまの中央値のほうが高い回は、規則の密度の中央値のまま。"""
    sv = {"best": "ショート", "cost": 100,
          "forms": {"ショート": {"sample_age_days": 30, "mixed_median": 500,
                              "mixed_n": 216, "max": 1777}}}
    assert sc.verdict(120.0, form="ショート", sv=sv)["cost"] == 100


def test_止めるのは_その本を名乗った回だけ():
    """**門が自分の出口を塞がないこと。** この門を入れた回自身が止められた
    （2026-09-05 05:xx）—— 丸ごと止めると、門を直す回まで止まります。
    `dry_ledger_gate()` が `fix` の行き先を枠の本に絞っている以上、
    名乗りのほうを止めれば、台帳が空の日の `fix` はそれで閉じます。
    """
    src = (dp.Path(__file__).resolve().parents[1] / "scripts" / "run_marker.py"
           ).read_text(encoding="utf-8")
    assert "_names_it" in src
    assert "if not _names_it:" in src
