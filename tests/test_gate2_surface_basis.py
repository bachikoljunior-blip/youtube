#!/usr/bin/env python3
"""**段2 の面は「いま続いている量」で読む。最大の1日で読まない。**（2026-08-25）

## なぜこの検査が要るか（**同じ帳面の読み手2つが、逆を向いていた**。この形は4件目）

`tests/test_surface_ceiling_basis.py` が 2026-08-24 に、天井の分母を
「全期間の平均」から「**最大の1日**」へ固定しました。**天井としては正しい**
—— 「腕 `rpm` は届きうるか」は上振れ側で読む質問です。

ところが `scripts/eta.py` の**段2** は、同じ `imp_day` をそのまま読んでいました。
段2 が問うているのは「門2a（長尺4,000時間）を **450日 かけて開けられるか**」で、
**38日でいちばん良かった1日は、その答えになりません。**

実測（2026-08-25・同じ `data/reach.jsonl`・同じ回）:

    scripts/eta.py 段2   最大の1日 1,285.0回/日 → 合格点 191 → **面は足りています（6.7倍）**
    scripts/status.py    直近7日   190.6回/日 → 段4 の要求 → **87倍 足りません**

そして段2 の文は、次に引く腕まで名指ししていました ——
**「ここから先で効くのは CTR のほうです（サムネと題）」**。
**面が足りていないのに CTR を直しても、面は動きません。**

## この検査が守ること

1. `reach_split.summary()` が `per_day_recent`（直近 `RECENT_DAYS` 日の平均）を返す
2. `rpm_mix.surface_ceiling()` が、天井（`imp_day` ＝ 最大の1日）とは**別の欄**で
   それを渡す（**天井のほうは動かさない**）
3. `eta._gate2_surface_basis()` が、続いている量 → 平均 → 最大 の順に落ちる。
   **上（最大）へは落ちない** —— 測っていない回ほど「足りている」と出るため
4. 同点（×1.00）を「足りている」と印字しない

**覆る条件**: 段2 の期日が 450日 から**数日**まで縮んだとき（そのときだけ、
1日ぶんの当たりが段取りの分母になり得ます）。または `RECENT_DAYS` の窓が
面の burst より短いと判定されたとき（そのときは窓を広げる。平均へは戻さない）。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import reach_split, rpm_mix  # noqa: E402


def _eta():
    """`scripts/eta.py` は `-` を含まないがパッケージ外なので、直に読む。"""
    spec = importlib.util.spec_from_file_location("eta_mod", ROOT / "scripts" / "eta.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


def _rows(series: dict[str, float], vid: str = "LONG1") -> list[dict]:
    return [{"date": d, "video_id": vid, "video_thumbnail_impressions": v,
             "video_thumbnail_impressions_ctr": 0.01} for d, v in series.items()]


#: 08/01〜08/21。**最初の14日は面が5回しか無く、08/21 だけ 1,285回**。
#: 全期間の平均・直近7日・最大の1日 が、はっきり別の数になる形。
_SERIES = {f"202608{d:02d}": 5.0 for d in range(1, 15)}
_SERIES.update({f"202608{d:02d}": 100.0 for d in range(15, 21)})
_SERIES["20260821"] = 1285.0


def test_summary_は続いている量を返す():
    sm = reach_split.summary(_rows(_SERIES), {"LONG1"})
    long = sm["長尺"]
    assert long["recent_days"] == reach_split.RECENT_DAYS
    # 直近7日 = 08/15〜08/21 = 100×6 + 1285 = 1885 / 7
    assert round(long["per_day_recent"], 1) == round(1885.0 / 7, 1)
    # 全期間の平均・最大の1日は、いままでどおり別の数のまま
    assert round(long["per_day"], 1) == round(sum(_SERIES.values()) / 21, 1)
    assert long["per_day_max"] == 1285.0


def test_天井は動かないまま_続いている量だけが足される():
    sm = reach_split.summary(_rows(_SERIES), {"LONG1"})
    mix = {"days": 90, "by_form": {"shorts": {"views": 9000.0, "minutes": 4500.0},
                                   "video": {"views": 11.0, "minutes": 33.0}}}
    got = rpm_mix.surface_ceiling(mix, sm)
    # **天井は最大の1日のまま**（2026-08-24 の決定を壊さない）
    assert got["imp_day"] == 1285.0
    assert got["imp_day_basis"] == "最大の1日"
    # そのうえで、段取りが読む数が別の欄で出ている
    assert round(got["imp_day_recent"], 1) == round(1885.0 / 7, 1)
    assert got["imp_day_recent_days"] == reach_split.RECENT_DAYS


def test_段2は続いている量を選ぶ():
    eta = _eta()
    imp, basis, span = eta._gate2_surface_basis(
        {"imp_day": 1285.0, "imp_day_max": 1285.0, "imp_day_mean": 73.0,
         "imp_day_recent": 190.6, "imp_day_recent_days": 7})
    assert imp == 190.6
    assert "直近7日" in basis
    # 他の2つも読み手に見せる（取り違えの再発を、字面で止める）
    assert span["mean"] == 73.0 and span["max"] == 1285.0


def test_点が古ければ平均へ落ちる_最大へは落ちない(tmp_path, monkeypatch):
    """`imp_day_recent` を持たない保存済みの点。**下振れ側へ落ちること。**"""
    eta = _eta()
    # `data/reach.jsonl` から測り直す道を塞いで、点だけで判断させる
    monkeypatch.setattr(reach_split, "load_rows", lambda *a, **k: [])
    imp, basis, _ = eta._gate2_surface_basis(
        {"imp_day": 1285.0, "imp_day_max": 1285.0, "imp_day_mean": 73.0})
    assert imp == 73.0, "最大の1日へ落ちてはいけない（測っていない回ほど足りて見える）"
    assert "平均" in basis


def test_同点を足りているとは書かない():
    eta = _eta()
    note = eta._gate2_surface_note(190.6, 191.0, "直近7日の平均",
                                  {"mean": 73.0, "max": 1285.0})
    assert "面は足りています" not in note
    assert "余裕がありません" in note
    # 「1.0倍 足りません」は、丸めると足りているように読める字面
    assert "1.0倍 足りません" not in note


def test_本当に足りているときは足りていると書く():
    eta = _eta()
    note = eta._gate2_surface_note(1000.0, 191.0, "直近7日の平均",
                                  {"mean": 73.0, "max": 1285.0})
    assert "面は足りています" in note
    assert "要る CTR" in note


def test_足りないときは腕をCTRに向けない():
    eta = _eta()
    note = eta._gate2_surface_note(73.0, 191.0, "全期間の平均",
                                  {"mean": 73.0, "max": 1285.0})
    assert "サムネと題（CTR）では動きません" in note
    assert "要る CTR" not in note


# ---------------------------------------------------------------------------
# **2026-08-26 に足した。上の 4件目 と同じ形の、8件目。**
#
# 上の検査は「最大の1日ではなく、続いている量で読め」と言っています。**正しい。**
# ところが `per_day_sustained` が返す「続いている量」は**カレンダーの1日あたり**で、
# 実測（2026-08-26）では**その窓の7日のうち5日が、長尺の公開0本**でした。
#
#     08/17 5 ／ 08/18 7 ／ 08/19 8 ／ 08/20 17 ／ 08/21 1,368 ／ 08/22 335 ／ 08/23 492
#     → 中央値 **17.0回/日** → 段2「**10.5倍 足りません**」
#
# **公開が0本の日の面は、「続いている量」ではなく「公開を止めていた量」です。**
# 段2 の問い（門2a を 450日 かけて開けられるか）は、**これから公開する予定**の上に
# 乗ります。予定は控えにあり（`data/uploaded.jsonl` の `at`）、API は1単位も要りません。
# ---------------------------------------------------------------------------

def test_窓が公開0本の日で埋まっていたら予定のほうで読む():
    """**中央値は消さない。** どちらも正しく、問いが別。"""
    eta = _eta()
    imp, basis, span = eta._gate2_surface_basis({
        "imp_day": 1368.0, "imp_day_max": 1368.0, "imp_day_mean": 85.9,
        "imp_day_recent": 17.0, "imp_day_recent_days": 7,
        "imp_day_recent_dry": 5,
        "imp_day_planned": 677.6, "imp_day_planned_pubs": 2.43,
        "imp_day_per_publish": 279.0,
        "imp_day_dry_span": ("20260908", "20260920", 13)})
    assert imp == 677.6
    assert "予約" in basis and "公開1本あたり" in basis
    # **中央値がどこへ行ったかを、同じ行に残すこと**
    assert "17.0" in basis
    assert span["recent"] == 17.0


def test_窓に公開0本の日が無ければ_いままでどおり続いている量():
    eta = _eta()
    imp, basis, _ = eta._gate2_surface_basis({
        "imp_day": 1368.0, "imp_day_max": 1368.0, "imp_day_mean": 85.9,
        "imp_day_recent": 300.0, "imp_day_recent_days": 7,
        "imp_day_recent_dry": 0,
        "imp_day_planned": 677.6, "imp_day_planned_pubs": 2.43,
        "imp_day_per_publish": 279.0})
    assert imp == 300.0


def test_予定表の穴を同じ行で名指しする():
    """**足りている/足りないより先に、どこで落ちるか。**"""
    eta = _eta()
    note = eta._gate2_surface_note(
        677.6, 178.0, "これから7日の予約から",
        {"mean": 85.9, "max": 1368.0, "ctr": 1.44,
         "dry_span": ("20260908", "20260920", 13)})
    assert "2026-09-08〜2026-09-20 の 13日" in note
    assert "長尺の予約が0本" in note


def test_足りていると書くときは実測のCTRを並べる():
    """**「面は足りています」を裸で出さないこと。**

    この節は CTR 100% を仮に置いた面の話で、再生になるのは `面 × 実測の CTR`。
    要る CTR（26.3%）と実測（1.44%）を並べないと、
    「もう手はいらない」と読めます。
    """
    eta = _eta()
    note = eta._gate2_surface_note(
        677.6, 178.0, "これから7日の予約から",
        {"mean": 85.9, "max": 1368.0, "ctr": 1.44})
    assert "面は足りています" in note
    assert "実測の CTR は 1.44%" in note
    assert "倍 足りません" in note
