"""`day_quota().line` の「この窓で使った単位」が、**帳面（読みも載る）**を数えること。

実測 2026-09-03 00:5x（窓 09/02 07:00Z〜）。同じ画面に2つの数が並んでいました:

    `day_quota().line`   「この窓で使った単位 **6,550** ／ 前例 9,400 → **あと 2,850**」
    `quota_ledger.spent`  **13,764** / 10,000

上は `data/day_quota.jsonl`（書き込みだけ）、下は `data/api_calls.jsonl`（読みも）。
差の大半は `niche_ceiling.py` の `search.list` 52回 ＝ **5,200単位** で、
09/01 は 12,859 通過後に 403 —— **「あと 2,850」は、もう無い余裕でした。**
`retro.py` はこの行を持ち越しの節に「**いまなら潰せます**」の根拠として刷ります。

守るのは3つ:

  1. 帳面に行が在る窓では、刷る数は帳面の **ok** 行の Data API 単位（読みも）
  2. `ok=False`（403／429）は数えない —— 失敗は単位を使わない（`_ledger_hold` と同じ）
  3. 帳面に行が無い窓（08/31 より前）では、今までどおり書き込みだけの数を刷り、
     **「帳面に行が無い」と言うこと**（推測で埋めない）
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from src import quota_ledger, upload_cap

NOW = datetime(2026, 9, 2, 15, 0, tzinfo=timezone.utc)      # 窓 09/02 07:00Z〜


def _write(root, name: str, rows: list[dict]) -> None:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def _at(hours: float) -> str:
    return (upload_cap.window_start(NOW) + timedelta(hours=hours)).isoformat(timespec="seconds")


def test_帳面が在る窓では読みも数えた単位を刷る(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_cap, "_root", lambda: tmp_path)
    _write(tmp_path, upload_cap.DAY_QUOTA_HITS, [
        {"at": _at(1), "ok": True, "detail": "videos.update a"},
        {"at": _at(2), "ok": True, "detail": "videos.update b"},
    ])
    _write(tmp_path, quota_ledger.LEDGER, [
        {"at": _at(1), "api": "data", "method": "videos.update", "units": 50, "ok": True},
        {"at": _at(2), "api": "data", "method": "videos.update", "units": 50, "ok": True},
        *[{"at": _at(3), "api": "data", "method": "search.list", "units": 100, "ok": True}
          for _ in range(50)],
        *[{"at": _at(4), "api": "data", "method": "search.list", "units": 100, "ok": False}
          for _ in range(5)],                                  # 429 —— 数えない
        {"at": _at(5), "api": "analytics", "method": "reports.query", "units": 0, "ok": True},
    ])
    b = upload_cap.measured_budget(NOW)
    assert b["spent"] == 100                                   # 書き込みだけ（意味は変えない）
    assert b["ledger_spent"] == 5_100                          # 読みも・失敗は数えない
    q = upload_cap.day_quota(NOW)
    assert q.open and "5,100" in q.line and "読みも数える" in q.line
    assert "あと 2,850" not in q.line


def test_前例は帳面の側でも403の前に通った単位で出す(tmp_path, monkeypatch):
    """09/01 の窓: 帳面で 12,859 通って 403。**それが前例**（9,400 ではなく）。"""
    monkeypatch.setattr(upload_cap, "_root", lambda: tmp_path)
    prev = upload_cap.window_start(NOW) - timedelta(days=1)
    hit = (prev + timedelta(hours=9)).isoformat(timespec="seconds")
    _write(tmp_path, upload_cap.DAY_QUOTA_HITS, [
        {"at": (prev + timedelta(hours=1)).isoformat(timespec="seconds"),
         "ok": True, "detail": "videos.update a"},
        {"at": hit, "ok": False, "detail": "quotaExceeded"},
        {"at": _at(1), "ok": True, "detail": "videos.update z"},
    ])
    _write(tmp_path, quota_ledger.LEDGER, [
        {"at": (prev + timedelta(hours=1)).isoformat(timespec="seconds"),
         "api": "data", "method": "videos.update", "units": 50, "ok": True},
        *[{"at": (prev + timedelta(hours=2)).isoformat(timespec="seconds"),
           "api": "data", "method": "search.list", "units": 100, "ok": True} for _ in range(30)],
        {"at": (prev + timedelta(hours=10)).isoformat(timespec="seconds"),   # 403 の後 —— 前例に入れない
         "api": "data", "method": "videos.list", "units": 1, "ok": True},
        {"at": _at(1), "api": "data", "method": "videos.update", "units": 50, "ok": True},
        *[{"at": _at(2), "api": "data", "method": "search.list", "units": 100, "ok": True}
          for _ in range(40)],
    ])
    b = upload_cap.measured_budget(NOW)
    assert b["floor"] == 50 and b["ledger_floor"] == 3_050
    assert b["ledger_spent"] == 4_050
    line = upload_cap.day_quota(NOW).line
    assert "前例 **3,050**" in line and "超えています" in line


def test_帳面に行が無い窓では書き込みだけの数を刷りそう言う(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_cap, "_root", lambda: tmp_path)
    prev = upload_cap.window_start(NOW) - timedelta(days=1)
    _write(tmp_path, upload_cap.DAY_QUOTA_HITS, [
        {"at": (prev + timedelta(hours=1)).isoformat(timespec="seconds"),
         "ok": True, "detail": "videos.update a"},
        {"at": _at(1), "ok": True, "detail": "videos.update z"},
    ])
    b = upload_cap.measured_budget(NOW)
    assert b["ledger_spent"] is None and b["ledger_floor"] == 0
    line = upload_cap.day_quota(NOW).line
    assert "**50**" in line and "帳面に行が無い窓" in line
