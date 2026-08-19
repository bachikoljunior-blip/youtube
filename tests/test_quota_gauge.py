"""`quota.py --gauge` の検査 —— **オーナーの画面の%を1行で積む**。

## なぜこの道具が要ったか（2026-08-19 21:2x・オーナー指示「毎回やるようにして」）

**%はこの機械からは読めません。** `list_sessions` の `rate_limit_info` は
`allowed` / `warning` / `rejected` しか返さず、残り%も分母も入っていません。
**唯一の目盛りはオーナーの画面**で、それを積む手は「`data/usage.jsonl` に手で
JSONL を書く」でした。

結果、**目盛りは 08/16 13:00 の 22% で 3.3日ぶん止まりました。** そのあいだ
機械は 22%＋外挿で間隔を決めていて、実測が入ったら **75%** ——
**持続できる間隔は 41分 → 65分**。**その差のぶんだけ速く走っていました。**

**手が重いと、正しい手順でも運用が落ちます。** ここで見るのは、
その1行が**正しい形で積まれること**と、**5時間枠を週枠に混ぜないこと**の2つです。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

import importlib.util
from pathlib import Path

from src.config import ROOT

spec = importlib.util.spec_from_file_location("quota", ROOT / "scripts" / "quota.py")
quota = importlib.util.module_from_spec(spec)
spec.loader.exec_module(quota)


@pytest.fixture()
def log(tmp_path, monkeypatch):
    p = tmp_path / "usage.jsonl"
    monkeypatch.setattr(quota, "USAGE_LOG", p)
    monkeypatch.setattr(quota, "pace_report", lambda *a, **k: None)
    return p


def _rows(p):
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_週枠の1行が_画面の字のまま積まれる(log):
    assert quota.record_gauge(75, "08/19 21:21", note="検査") == 0
    (row,) = _rows(log)
    assert row["window_id"] == "seven_day"
    assert row["used_percent"] == 75 and row["remaining_percent"] == 25
    assert row["source"] == "owner-manual"
    assert row["fetched_at"].startswith("2026-08-19T21:21")


def test_リセットは次の土曜7時が既定(log):
    """画面の『リセット: 土 7:00』。**08/19（水）の次の土は 08/22。**"""
    quota.record_gauge(75, "2026-08-19 21:21")
    (row,) = _rows(log)
    resets = datetime.fromisoformat(row["resets_at_iso"].replace("Z", "+00:00"))
    assert resets.astimezone(quota.JST).strftime("%Y-%m-%d %H:%M") == "2026-08-22 07:00"


def test_土曜の朝に撮った画面は_その日の7時を過ぎていれば翌週(log):
    """**境目で1週ずれると、残り時間が7日ぶん狂います。**（速さがそのまま7分の1に）"""
    quota.record_gauge(5, "2026-08-22 08:00")
    (row,) = _rows(log)
    resets = datetime.fromisoformat(row["resets_at_iso"].replace("Z", "+00:00"))
    assert resets.astimezone(quota.JST).strftime("%Y-%m-%d %H:%M") == "2026-08-29 07:00"


def test_5時間枠は別の行になり_週枠に混ざらない(log):
    """**分母が別**（`quota.py` 冒頭）。同じ行に入れると速さが壊れます。"""
    quota.record_gauge(75, "08/19 21:21", session_pct=2, session_in_min=288)
    rows = _rows(log)
    assert [r["window_id"] for r in rows] == ["seven_day", "five_hour"]
    five = rows[1]
    assert five["used_percent"] == 2
    r5 = datetime.fromisoformat(five["resets_at_iso"].replace("Z", "+00:00"))
    # 21:21 + 288分 = 8/20 02:09 JST（5時間枠の刻みと一致する）
    assert r5.astimezone(quota.JST).strftime("%m-%d %H:%M") == "08-20 02:09"


def test_読めない時刻は積まずに落ちる(log):
    """**黙って積まないこと。** 時刻が狂うと、速さの区間がそのまま狂います。"""
    assert quota.record_gauge(75, "きのうの夜") == 1
    assert not log.exists() or _rows(log) == []


def test_時刻なしの_gauge_は口が止める():
    """`--at` の無い `--gauge` は通らないこと（あとから積むと速さが狂う）。"""
    import subprocess, sys
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "quota.py"), "--gauge", "75"],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "--at" in r.stderr
