"""`src/quota_refute.py` —— 帳面の「尽きた」を実物（越えた後の読み書き・403）と突き合わせる。

実測 2026-09-03（窓 09/02 16:00 JST〜）: 帳面は 16:07 に 10,000 を越え、その後 13.5時間
読みが 740回 通り、403 は 0件、書き込みは 1回も試していない ＝「読みだけ通る」。
この検査は、その4つの判定が入れ替わらないことを見る。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from src import quota_refute

T0 = datetime(2026, 9, 2, 7, 5, tzinfo=timezone.utc)      # 窓 09/02 07:00Z の 5分後


def _row(minutes: float, method: str, units: int, ok: bool = True) -> dict:
    return {"at": (T0 + timedelta(minutes=minutes)).isoformat(), "api": "data",
            "method": method, "units": units, "ok": ok, "by": "t"}


def _crossing() -> list[dict]:
    """`videos.update` 200回 ＝ 10,000単位 で越える。"""
    return [_row(i * 0.1, "videos.update", 50) for i in range(200)]


def _reads(n: int, start_min: float, span_min: float) -> list[dict]:
    return [_row(start_min + i * span_min / max(n - 1, 1), "videos.list", 1) for i in range(n)]


def test_越えた後に読みが通り続ける窓は_読みだけ通る() -> None:
    rows = _crossing() + _reads(30, 60, 12 * 60)
    ws = quota_refute.windows(rows, hits=[], cap=10_000)
    assert len(ws) == 1
    w = ws[0]
    assert w["crossed_at"] is not None
    assert w["reads_after"] == 30
    assert w["hours_after"] >= 12
    assert w["verdict"] == "読みだけ通る"
    assert quota_refute.probed_windows(rows, hits=[]) == 0


def test_同じ分に束で通った読みは証拠にしない() -> None:
    rows = _crossing() + _reads(30, 20, 5)                 # 越えてから 5分の中に 30回
    w = quota_refute.windows(rows, hits=[], cap=10_000)[0]
    assert w["verdict"] == "不明"


def test_403を観測した窓は_尽きた() -> None:
    rows = _crossing() + _reads(30, 60, 12 * 60)
    hits = [{"at": (T0 + timedelta(hours=3)).isoformat(), "ok": False, "detail": "x"}]
    w = quota_refute.windows(rows, hits, cap=10_000)[0]
    assert w["hits_403"] == 1
    assert w["verdict"] == "尽きた"
    assert quota_refute.probed_windows(rows, hits) == 1


def test_越えた後に書き込みが通った窓は_帳面が外れ() -> None:
    rows = _crossing() + _reads(30, 60, 12 * 60) + [_row(8 * 60, "thumbnails.set", 50)]
    w = quota_refute.windows(rows, hits=[], cap=10_000)[0]
    assert w["writes_ok"] == 1
    assert w["verdict"] == "帳面が外れ"
    assert quota_refute.probed_windows(rows, hits=[]) == 1


def test_insertは書き込みの試行に数えない() -> None:
    """`videos.insert` は別の枠から出ている（実測 3度）。通っても「帳面が外れ」の証拠にならない。"""
    rows = _crossing() + _reads(30, 60, 12 * 60) + [_row(8 * 60, "videos.insert", 1600)]
    w = quota_refute.windows(rows, hits=[], cap=10_000)[0]
    assert w["writes_ok"] == 0
    assert w["verdict"] == "読みだけ通る"


def test_越えていない窓は_未達() -> None:
    rows = _reads(30, 60, 12 * 60)
    w = quota_refute.windows(rows, hits=[], cap=10_000)[0]
    assert w["crossed_at"] is None
    assert w["verdict"] == "未達"


def test_落ちた読みは通った単位に足さない() -> None:
    rows = [_row(i * 0.1, "search.list", 100, ok=False) for i in range(200)]
    w = quota_refute.windows(rows, hits=[], cap=10_000)[0]
    assert w["used"] == 0
    assert w["verdict"] == "未達"


def test_renderが本物の帳面で落ちないこと() -> None:
    out = quota_refute.render()
    assert "突き合わせ" in out
