#!/usr/bin/env python3
"""**天井は「最大の1日」で読む。平均で読まない。**（2026-08-24）

## なぜこの検査が要るか

`src/rpm_mix.surface_ceiling()` は 2026-08-20 から、長尺の面を
**全期間の平均**（`impressions / days`）で読んでいました。すぐ上の行には
**「天井は上振れ側で読むこと」**と書いてあります —— 註と中身が逆でした。

実測（2026-08-24）で効いていた量:

    38日の平均      **73.0回/日**   ← 最初の20日は長尺の公開前（面が存在しない日）
    最大の1日     **1,285.0回**     ← 08/21。**全期間 2,773回 の46%が この1日**

そして 73.0 は、そのまま最後まで流れていました:

    面 73.0回/日 → 実効RPM の天井 ¥287 → 段4 の合格点 695,675回/月
    → 1日 23,183回 が要る／天井は 6,650回（10本 × 665回）→ **3.5倍 足りない**
    → **「月20万の到達予測: 出ません」**

最大の1日で読むと **4,698回/日** で、**同じ天井の下に入ります。**
つまり「原理的に届かない」は、**面の平均の分母1つ**から出ていました。

**この検査が守るのは「最大で読む」ことだけ**です。1,285 が繰り返すかどうかは
別の話で、そちらは `config/hypotheses.yaml` の期限つきの前提が判定します。

**覆る条件**: 最大の1日が「1回きりの実験」だと判定されたとき（前提
「長尺の面は 08/21 の 1,285回/日 を再現する」が外れたとき）。そのときは
平均へ戻すのではなく、**再現した中でいちばん大きい日**へ落とすこと ——
平均は、存在しない日を分母に数えるので、どちらにしても天井にはなりません。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import reach_split, rpm_mix  # noqa: E402


def _mix(short_views: float, long_views: float, days: float = 90) -> dict:
    return {
        "days": days,
        "by_form": {
            "shorts": {"views": short_views, "minutes": short_views * 0.5},
            "video": {"views": long_views, "minutes": long_views * 3.0},
        },
    }


def _reach(*, total: float, days: float, per_day_max: float | None,
           max_on: str = "20260821", live_days: int = 18) -> dict:
    row: dict = {"impressions": total}
    if per_day_max is not None:
        row.update({"per_day_max": per_day_max, "per_day_max_on": max_on,
                    "live_days": live_days})
    return {"長尺": row, "ショート": {"impressions": 0.0}, "days": days}


def test_天井は最大の1日で読む():
    """平均 73.0 ではなく 最大 1285.0 が分子に入ること。"""
    got = rpm_mix.surface_ceiling(
        _mix(9000, 11), _reach(total=2773.0, days=38, per_day_max=1285.0))
    assert got["imp_day"] == 1285.0
    assert got["imp_day_basis"] == "最大の1日"
    assert abs(got["imp_day_mean"] - 2773.0 / 38) < 1e-9


def test_平均で読むと天井が下がる_数で押さえる():
    """**この差が「届きません」の出どころ**でした。順序が逆転したら赤にする。

    実物の混ざり方（08/24 の点: 90日で ショート 49,440再生 ＝ 549回/日）で当てます。
    平均 ¥288 → 最大 ¥1,419。段4 の合格点は RPM の逆数なので
    **1日 23,183回 → 4,698回**、天井 6,650回/日（10本 × 665回）の**下へ入ります**。
    """
    mix = _mix(49440, 30, days=90)
    mean_only = rpm_mix.surface_ceiling(
        mix, _reach(total=2773.0, days=38, per_day_max=None))
    with_max = rpm_mix.surface_ceiling(
        mix, _reach(total=2773.0, days=38, per_day_max=1285.0))
    assert mean_only["imp_day_basis"] == "全期間の平均"
    assert with_max["rpm_max"] > mean_only["rpm_max"] * 3

    need_per_day = lambda c: 200_000 * 1000 / c["rpm_max"] / 30   # noqa: E731
    assert need_per_day(mean_only) > 6650      # 天井の上 ＝ **届きません**
    assert need_per_day(with_max) < 6650       # 天井の下 ＝ 届きます


def test_古い呼びは平均へ落ちる():
    """`per_day_max` を持たない保存済みの点・検査を壊さないこと。"""
    got = rpm_mix.surface_ceiling(
        _mix(9000, 11), _reach(total=3400.0, days=34, per_day_max=None))
    assert got["imp_day_basis"] == "全期間の平均"
    assert abs(got["imp_day"] - 100.0) < 1e-9


def test_なぜの行にどちらで出したかが出る():
    """点を並べたとき、平均の版と最大の版が見分けられること。"""
    got = rpm_mix.surface_ceiling(
        _mix(9000, 11), _reach(total=2773.0, days=38, per_day_max=1285.0))
    assert "最大の1日" in got["why"]
    assert "20260821" in got["why"]
    assert "全期間の平均" in got["why"]


def test_積んだ点にどちらで出したかが残る(tmp_path):
    """欄が無いと、次の回が「天井が上がったのか測り方が変わったのか」を切り分けられません。"""
    mix = _mix(9000, 11)
    ceiling = rpm_mix.surface_ceiling(
        mix, _reach(total=2773.0, days=38, per_day_max=1285.0))
    log = tmp_path / "rpm_mix.jsonl"
    rec = rpm_mix.record(mix, ceiling, path=log)
    assert rec["imp_day_basis"] == "最大の1日"
    assert rec["imp_day_max_on"] == "20260821"
    assert rec["imp_day_mean"] is not None


def test_面が測れていない回でもどちらで出したかは言う():
    got = rpm_mix.surface_ceiling(_mix(9000, 11),
                                  _reach(total=0.0, days=38, per_day_max=None))
    assert got["factor"] is None
    assert got["imp_day_basis"] == "全期間の平均"


# --- summary() の側 ----------------------------------------------------------
def _rows(series: dict[str, float], vid: str = "L1") -> list[dict]:
    return [{"date": d, "video_id": vid, "video_thumbnail_impressions": str(int(v)),
             "video_thumbnail_impressions_ctr": "0"} for d, v in series.items()]


def test_summary_は最大の1日とその日付を出す():
    rows = _rows({"20260801": 0, "20260802": 5, "20260803": 1285, "20260804": 17})
    sm = reach_split.summary(rows, {"L1"})
    L = sm["長尺"]
    assert L["per_day_max"] == 1285.0
    assert L["per_day_max_on"] == "20260803"
    assert L["per_day"] == (0 + 5 + 1285 + 17) / 4


def test_中身のある日だけの平均は0の日を分母から外す():
    rows = _rows({"20260801": 0, "20260802": 0, "20260803": 100, "20260804": 200})
    L = reach_split.summary(rows, {"L1"})["長尺"]
    assert L["live_days"] == 2
    assert L["per_day_live"] == 150.0
    assert L["per_day"] == 75.0
