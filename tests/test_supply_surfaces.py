"""**在庫を、面べつに数える**（`src.supply.surfaces`）。2026-08-27 に測って足した。

## なぜ要るか

`supply()` は在庫を **`day_cap.cap()`（＝ショートの 10本/日）**で割り、
「**足ります**」と印字します。**その面は天井です** ——
`eta.py` の `density_surfaces` の実測:

    ショート  at_ceiling=True  measured=True   （超えたぶんは 0再生）
    長尺      at_ceiling=False measured=False  （崩れる所を一度も見ていない）

そして **4,000時間の門に入るのは長尺だけ**（実測 08/26・直近28日:
`SHORTS_FEED` 64,283再生 ／ `WATCH` **67再生**）。
**「足ります」は、いま開いている唯一の門とは別の面についての合格**でした。

実測（2026-08-27・控えを畳んで数えた）:

    長尺の予約    36本  08/28〜09/04 の **8日**（09/05 以降は 0本）
    ショートの予約 347本  10/12 まで ＝ **46日**

**6倍 ちがい、長い側が門に1分も積まない面**です。

## ここが壊れたと分かる形

面べつの行が消えたら、次に来た側は「足ります」だけを読んで、
**天井の面に材料を注ぎ続けます。**
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import supply  # noqa: E402

JST = timezone(timedelta(hours=9))




def _write(tmp_path, rows, dur):
    import json
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "uploaded.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps({"video_id": r["id"], "topic": r.get("topic", "t"),
                                 "at": r["at"],
                                 "duration_s": dur[r["id"]]}) + "\n")


def _row(vid, at, topic="t"):
    return {"id": vid, "topic": topic,
            "at": at.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def _setup(tmp_path, monkeypatch, longs, shorts, today):
    from src import config, dupes
    rows, dur = [], {}
    for i, d in enumerate(longs):
        vid = f"L{i}"
        rows.append(_row(vid, datetime(2026, 8, d, 20, 0, tzinfo=JST)))
        dur[vid] = 300.0
    for i, d in enumerate(shorts):
        vid = f"S{i}"
        rows.append(_row(vid, datetime(2026, 8, d, 10, 0, tzinfo=JST)))
        dur[vid] = 45.0
    _write(tmp_path, rows, dur)
    monkeypatch.setattr(config, "ROOT", tmp_path)
    monkeypatch.setattr(supply, "today_jst", lambda: today)
    monkeypatch.setattr(dupes, "ledger_rows", lambda: rows)
    monkeypatch.setattr(config, "load_topics", lambda: {"topics": [
        {"id": "deep-a", "calc": "x"}, {"id": "s-b", "calc": "x"}]})
    return rows, dur


def test_面べつの滑走路を日で出す(tmp_path, monkeypatch):
    today = datetime(2026, 8, 27, tzinfo=JST).date()
    _setup(tmp_path, monkeypatch, longs=[28, 29], shorts=[28, 29, 30, 31], today=today)
    su = supply.surfaces()
    assert su["long"]["booked"] == 2
    assert su["long"]["runway_days"] == 3          # 08/27 → 08/29
    assert su["short"]["booked"] == 4
    assert su["short"]["runway_days"] == 5         # 08/27 → 08/31


def test_長尺の在庫はs始まりを数えない(tmp_path, monkeypatch):
    today = datetime(2026, 8, 27, tzinfo=JST).date()
    _setup(tmp_path, monkeypatch, longs=[28], shorts=[28], today=today)
    su = supply.surfaces()
    assert su["long"]["stock"] == 1, "`s-` の題を長尺の在庫に数えています"


def test_長尺のほうが短ければそう名指しする(tmp_path, monkeypatch):
    today = datetime(2026, 8, 27, tzinfo=JST).date()
    _setup(tmp_path, monkeypatch, longs=[28], shorts=[28, 30, 31], today=today)
    text = "\n".join(supply.surface_lines())
    assert "短いのは長尺の側です" in text
    assert "門は1分も動きません" in text


def test_ショートのほうが短ければ名指ししない(tmp_path, monkeypatch):
    today = datetime(2026, 8, 27, tzinfo=JST).date()
    _setup(tmp_path, monkeypatch, longs=[28, 30, 31], shorts=[28], today=today)
    text = "\n".join(supply.surface_lines())
    assert "短いのは長尺の側です" not in text
    assert "律速は滑走路ではありません" in text


def test_公開済みは滑走路に数えない(tmp_path, monkeypatch):
    today = datetime(2026, 8, 27, tzinfo=JST).date()
    _setup(tmp_path, monkeypatch, longs=[20, 28], shorts=[21], today=today)
    su = supply.surfaces()
    assert su["long"]["booked"] == 1, "きのうまでの本を滑走路に数えています"
    assert su["short"]["booked"] == 0


def test_本物の控えでも落ちない():
    """**実物で1度は撃つこと。** 差し替えた盤面だけで緑になる形を避けます。"""
    su = supply.surfaces()
    assert set(su) == {"long", "short"}
    assert supply.surface_lines(su)
