"""**いま出ている再生/日を、自分の計器（`data/views.jsonl`）から取る。**（2026-09-05・最適化の回）**API 0単位。**

## なぜ要るか（**実測で名指しした欠陥を1つ潰す**）

回が自分を採点する物差し `gate1p_days`（門1'・登録者 500人 までの日数）は、
`475 ÷ (再生/日 × 登録率)` で、その「再生/日」は **Analytics の `max(7d/7, 28d/28)`** でした。
落ちている最中は 28日 の平均が勝ち、登録率も 28日 の箱なので、
**102行 すべて 511.538 のまま**でした（`scripts/optimized.py` が数えた）。

同じ 5日 のあいだに、**自分の計器はこう動いていました**（この回に数えた。
`data/views.jsonl` の、日ごとの再生の差の合計）::

    09/02  356再生/日     09/03  171     09/04  62     09/05  0（途中）

**物差しが動かないので、どの ship も「動かず」で通り、`fix` が 48% を占めました。**
近づかない回が選ばれ続けたのは、**近づいていないと分かる数が回に届かなかったから**です。

## 返す物

`views_per_day(hours=24)` → dict::

    views_24h   直近 `hours` 時間の再生の増分の合計を 24時間 に直した数（**実測の差**）
    n           差が取れた本の数
    at          いちばん新しい観測の時刻（ISO・UTC）
    span_h      いちばん新しい観測と、比べた観測との隔たり（時間・中央値）
    ok          `n >= MIN_VIDEOS` で、観測が `STALE_H` より新しい

## 覆る条件

1. `data/views.jsonl` が `STALE_H` 以上 止まっていたら `ok=False` —— そのときは
   Analytics の 7日 の平均へ落ちること（`scripts/eta._row()` がそうしている）。
2. `scripts/snapshot.py` が新しい本から順に読まなくなったら、ここは古い本の
   増分しか数えません（**この回に、古い順 → 新しい順に直した**。日枠が尽きた日は
   1組目の 50本 しか取れないので、順が命です）。
"""
from __future__ import annotations

import bisect
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "views.jsonl"

#: これより少ない本数でしか差が取れないときは `ok=False`。
MIN_VIDEOS = 5
#: いちばん新しい観測がこれより古いときは `ok=False`（計器が止まっている）。
STALE_H = 36.0


def _parse(ts: str) -> datetime:
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def views_per_day(hours: float = 24.0, log: Path | None = None,
                  now: datetime | None = None) -> dict:
    """直近 `hours` 時間の再生の増分（全本の合計）を 24時間 に直して返す。"""
    path = log or LOG
    by: dict[str, list[tuple[datetime, int]]] = defaultdict(list)
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        lines = []
    for ln in lines:
        if not ln.strip():
            continue
        try:
            d = json.loads(ln)
            by[str(d["id"])].append((_parse(str(d["at"])), int(d.get("views") or 0)))
        except (KeyError, ValueError, TypeError, json.JSONDecodeError):
            continue
    if not by:
        return {"views_24h": None, "n": 0, "at": None, "span_h": None, "ok": False}
    latest = max(p[-1][0] for p in by.values() if p)
    now = now or datetime.now(timezone.utc)
    total = 0.0
    spans: list[float] = []
    for pts in by.values():
        pts.sort()
        t1, v1 = pts[-1]
        # いちばん新しい観測から 12時間 以内に読めた本だけ（古い本の古い点を混ぜない）
        if (latest - t1) > timedelta(hours=12):
            continue
        cut = t1 - timedelta(hours=hours)
        i = bisect.bisect_right([p[0] for p in pts], cut)
        if i == 0:
            continue
        t0, v0 = pts[i - 1]
        span = (t1 - t0).total_seconds() / 3600
        if span <= 0:
            continue
        total += max(0, v1 - v0) * (24.0 / span)
        spans.append(span)
    n = len(spans)
    spans.sort()
    span_h = spans[n // 2] if n else None
    stale = (now - latest).total_seconds() / 3600 > STALE_H
    return {"views_24h": round(total, 1) if n else None, "n": n,
            "at": latest.isoformat(timespec="seconds"),
            "span_h": round(span_h, 1) if span_h else None,
            "ok": bool(n >= MIN_VIDEOS and not stale)}


if __name__ == "__main__":
    print(json.dumps(views_per_day(), ensure_ascii=False))
