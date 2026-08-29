"""**控えは追記だけの帳面。1行 ＝ 1本ではない。**

`data/uploaded.jsonl` は追記だけで、`scripts/reschedule.py` が予約を動かすと
**同じ `video_id` が別の `at` でもう1行**入ります。`reach_split` の2つの数え手は
長らく**行ごと**に数えていて、実測で

    これから7日の長尺  行 8.43本/日 ／ 実際 4.29本/日（**1.97倍**）
    予約の先          行 20261012 ／ 実際 20261009（**3日 長く見えていた**）

になっていました。返りは `surface_forecast()` の掛け算と `per_publish` の
割り算の**両方**に入るので、`scripts/eta.py` の段2 の面がそのぶん狂います。

**覆る条件**: 控えが追記でなくなったら（上書きにしたら）、この検査ごと畳むこと。
"""
from __future__ import annotations

import json
from pathlib import Path

from src import reach_split


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "uploaded.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return p


def test_同じ本を2回書いても1本と数える(tmp_path: Path) -> None:
    p = _write(tmp_path, [
        {"video_id": "A", "at": "2026-09-04T11:00:00Z"},
        {"video_id": "A", "at": "2026-09-04T11:00:00Z"},   # そのままの重複
        {"video_id": "B", "at": "2026-09-04T12:00:00Z"},
    ])
    got = reach_split.publishes_per_day(longs={"A", "B"}, ledger_path=p)
    assert got == {"20260904": 2}, got


def test_予約を動かした本は古い日に残らない(tmp_path: Path) -> None:
    """`reschedule.py` が前へ動かした本。**後の行が勝つ。**"""
    p = _write(tmp_path, [
        {"video_id": "A", "at": "2026-10-12T11:00:00Z"},
        {"video_id": "A", "at": "2026-09-01T11:00:00Z"},   # 前倒しした
    ])
    got = reach_split.publishes_per_day(longs={"A"}, ledger_path=p)
    assert got == {"20260901": 1}, got
    # **古い日が「予約の先」に化けないこと**（この向きが危ないほう）
    assert reach_split.last_scheduled_day(ledger_path=p) == "20260901"


def test_本物の控えでも行数より少ない() -> None:
    """実物で「行 ＞ id」が起きていることを、数で押さえる。

    ここが等しくなったら、控えの書き方が変わったということなので、
    上の2つの検査の意味も変わります。**そのときは節ごと読み直すこと。**
    """
    ledger = Path(__file__).resolve().parent.parent / "data" / "uploaded.jsonl"
    if not ledger.exists():
        return
    lines = [ln for ln in ledger.read_text(encoding="utf-8").splitlines() if ln.strip()]
    ids = {json.loads(ln).get("video_id") for ln in lines}
    assert len(ids) <= len(lines)
    by_id = reach_split._ledger_by_id(ledger)
    assert len(by_id) == len({i for i in ids if i})
