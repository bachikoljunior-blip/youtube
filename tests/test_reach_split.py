"""`src/reach_split.py` の検査（**API を1単位も叩かない**）。

ここで固定しているのは、2026-08-20 21:4x に**実物で踏んだ2つの欠陥**です。

1. **CTR の列は割合**（百分率ではない）。`/100` していたあいだ、
   クリックは100分の1に見えていました
2. **報告は全部読む**（`reach.py` が新しい3本しか落としていなかった）。
   こちらは `tests/test_reach_ingest.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import reach_split as R  # noqa: E402


def row(date: str, vid: str, imp, ctr) -> dict:
    return {"date": date, "video_id": vid,
            "video_thumbnail_impressions": imp,
            "video_thumbnail_impressions_ctr": ctr}


def test_CTRの列は割合であって百分率ではない():
    # 実物: impressions 148 / ctr 0.0067567... ＝ 1/148 ＝ クリック1
    r = row("20260810", "YHiigJ3Zpj4", "148", "0.0067567567567567571")
    assert abs(R._clicks(r) - 1.0) < 1e-6


def test_CTR1は全部押されたという意味():
    assert R._clicks(row("20260810", "x", "1", "1")) == 1.0


def test_壊れた値でも落ちない():
    assert R._clicks(row("20260810", "x", "", "")) == 0.0
    assert R._imp(row("20260810", "x", "abc", "0")) == 0.0


def test_同じ日と動画は最後の行だけ残る():
    rows = [row("20260810", "a", "10", "0"), row("20260810", "a", "12", "0"),
            row("20260811", "a", "5", "0")]
    out = R.dedupe(rows)
    assert len(out) == 2
    assert sum(R._imp(r) for r in out) == 17


def test_長尺とショートで割る():
    rows = [row("20260810", "L1", "100", "0.01"), row("20260810", "S1", "50", "0.02")]
    sm = R.summary(rows, {"L1"})
    assert sm["長尺"]["impressions"] == 100
    assert abs(sm["長尺"]["clicks"] - 1.0) < 1e-9
    assert abs(sm["長尺"]["ctr"] - 1.0) < 1e-9      # 1/100 ＝ 1%
    assert sm["ショート"]["impressions"] == 50
    assert sm["days"] == 1


def test_控えに無い動画はショート側へ入れる():
    """**長尺の側を大きく見せないこと。** 分からないものは分母の大きいほうへ。"""
    sm = R.summary([row("20260810", "unknown", "10", "0")], {"L1"})
    assert sm["ショート"]["impressions"] == 10
    assert sm["長尺"]["impressions"] == 0


def test_直近N日は日付の実物で切る():
    rows = [row(f"2026081{i}", "a", "10", "0") for i in range(1, 6)]
    assert len({str(r["date"]) for r in R.tail(rows, 2)}) == 2
    assert sorted({str(r["date"]) for r in R.tail(rows, 2)}) == ["20260814", "20260815"]


def test_足りない倍率はCTR100パーセントの上限で出す():
    """**サムネを極限まで直した先**と比べる。そこでも足りなければ、面の話。"""
    sm = R.summary([row("20260810", "L1", "10", "0")], {"L1"})
    g = R.gap(sm, need_views_month=3000)
    assert g["ceiling_views_month"] == 300      # 1日10回 × 30日
    assert g["short_by"] == 10


def test_面が1回も無ければ無限大にする():
    sm = R.summary([row("20260810", "S1", "10", "0")], {"L1"})
    assert R.gap(sm, need_views_month=1)["short_by"] == float("inf")


def test_段4の要求は写しでなく計算で出す():
    # 月20万 ÷ RPM ¥400 × 1000
    assert R.plan_views_month(200_000, 400) == 500_000
    assert R.plan_views_month(200_000, 2_000) == 100_000


def test_1行も無いときは何をすればいいかを出す():
    out = R.render([], {"L1"})
    assert "まだ1行もありません" in out
    assert "reach.py" in out


def test_出す節はインプレッションとCTRの両方を名指しする():
    rows = [row("20260810", "L1", "100", "0.01"), row("20260810", "S1", "50", "0.02")]
    out = R.render(rows, {"L1"})
    assert "長尺" in out and "ショート" in out
    assert "直近" in out
