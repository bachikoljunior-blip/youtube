"""**物差し `gate1p_days` は、自分の計器（直近 24時間 の再生の差）で動くこと。**

## なぜ要るか（2026-09-05 13:xx JST・最適化の回。**実測で名指しした欠陥**）

`gate1p_days` は `475 ÷ (max(7d/7, 28d/28) × 登録率28d)` で、**102行 すべて 511.538**
でした（`scripts/optimized.py`）。同じ 5日 に `data/views.jsonl` の再生/日 は
**356 → 171 → 62 → 0** です。動かない物差しでは、どの ship も「動かず」で通り、
`fix` が 48% を占めました。**近づかない回が選ばれ続けた理由は、近づいていないと
分かる数が回に届かなかったこと**なので、分子の「再生/日」を自分の計器へ移しました。

この検査が落ちる ＝ 物差しが 28日 の箱へ戻った（または basis の違う行どうしを
引いて、式の差を「その回の動き」と数えている）。

**覆る条件**: `traj_days`（到達日）が有限に戻ったら、`run_marker` はそちらを読みます。
そのときこの検査は残しても害はありません。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import live_views  # noqa: E402


def _load(name: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_live_views_sums_24h_deltas(tmp_path):
    log = tmp_path / "views.jsonl"
    _write(log, [
        {"at": "2026-09-04T03:00:00Z", "id": "a", "hours": 10, "views": 100},
        {"at": "2026-09-05T03:00:00Z", "id": "a", "hours": 34, "views": 160},
        {"at": "2026-09-04T03:00:00Z", "id": "b", "hours": 10, "views": 10},
        {"at": "2026-09-05T03:00:00Z", "id": "b", "hours": 34, "views": 10},
        # 24時間 より新しい点しか無い本は差が取れない（数に入れない）
        {"at": "2026-09-05T02:00:00Z", "id": "c", "hours": 1, "views": 5},
    ])
    from datetime import datetime, timezone
    now = datetime(2026, 9, 5, 4, 0, tzinfo=timezone.utc)
    out = live_views.views_per_day(log=log, now=now)
    assert out["views_24h"] == 60.0
    assert out["n"] == 2
    assert out["ok"] is False          # MIN_VIDEOS 未満
    assert out["at"].startswith("2026-09-05T03:00:00")


def test_live_views_is_not_ok_when_stale(tmp_path):
    log = tmp_path / "views.jsonl"
    rows = []
    for i in range(6):
        rows.append({"at": "2026-09-01T03:00:00Z", "id": f"v{i}", "hours": 10, "views": 1})
        rows.append({"at": "2026-09-02T03:00:00Z", "id": f"v{i}", "hours": 34, "views": 2})
    _write(log, rows)
    from datetime import datetime, timezone
    now = datetime(2026, 9, 5, 4, 0, tzinfo=timezone.utc)
    out = live_views.views_per_day(log=log, now=now)
    assert out["n"] == 6 and out["ok"] is False


def test_gate1p_live_falls_back_to_analytics_7d_and_stays_finite(monkeypatch):
    eta = _load("eta")
    monkeypatch.setattr(live_views, "views_per_day",
                        lambda *a, **k: {"ok": False, "views_24h": None})
    basis, days, v24 = eta._gate1p_live({}, {"fan_subs_remaining": 475, "sub_rate": 0.001,
                                             "views_per_day_7d": 100.0})
    assert basis == "analytics7d" and v24 is None
    assert abs(days - 4750.0) < 1e-6
    # 0再生/日 でも 10^9 にしない（`run_marker._gate1p_now()` が捨てて「無い」に戻る）
    basis, days, _ = eta._gate1p_live({}, {"fan_subs_remaining": 475, "sub_rate": 0.001,
                                           "views_per_day_7d": 0.0})
    assert days == eta.GATE1P_LIVE_CAP_DAYS < 1e8


def test_gate1p_live_uses_own_meter_when_ok(monkeypatch):
    eta = _load("eta")
    monkeypatch.setattr(live_views, "views_per_day",
                        lambda *a, **k: {"ok": True, "views_24h": 50.0})
    basis, days, v24 = eta._gate1p_live({}, {"fan_subs_remaining": 475, "sub_rate": 0.001,
                                             "views_per_day_7d": 100.0})
    assert basis == "live24h" and v24 == 50.0
    assert abs(days - 9500.0) < 1e-6


def test_last_ship_gate1p_only_pairs_same_basis(tmp_path, monkeypatch):
    rm = _load("run_marker")
    marks = tmp_path / "runs.jsonl"
    _write(marks, [
        {"at": "2026-09-05T01:00:00+09:00", "kind": "ship", "gate1p_days": 511.5},
        {"at": "2026-09-05T02:00:00+09:00", "kind": "ship", "gate1p_days": 20000.0,
         "gate1p_basis": "live24h"},
        {"at": "2026-09-05T03:00:00+09:00", "kind": "ship", "gate1p_days": 511.5},
    ])
    monkeypatch.setattr(rm, "MARKS", marks)
    assert rm._last_ship_gate1p() == 511.5
    assert rm._last_ship_gate1p("live24h") == 20000.0
    assert rm._last_ship_gate1p("analytics7d") is None


def test_snapshot_reads_newest_first():
    snap = _load("snapshot")
    ids = snap._ids_from_ledger()
    led = ROOT / "data" / "uploaded.jsonl"
    last = None
    for ln in reversed(led.read_text(encoding="utf-8").splitlines()):
        if ln.strip():
            last = json.loads(ln).get("video_id")
            break
    assert ids and ids[0] == last, "日枠が尽きた日に 1組目で取れるのは新しい 50本 であること"
