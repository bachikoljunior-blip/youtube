#!/usr/bin/env python3
"""公開済み動画の再生数を、公開からの経過時間つきで1行ずつ残す。

なぜ要るか。**「いつ伸びたか」を一度も記録していなかった。**

2026-08-06、m74wgCTi2n0 が 1245（公開12時間後）→ 1257（24時間後）で止まった。
バーストが一度きりなのは分かったが、**FSAN9tjIX10 が同じ形かを比べる基準が無い。**
公開13分後の0回が良いのか悪いのかも判断できない。総再生数だけ見ていると、
**当たり外れが決まる最初の数時間が丸ごと抜ける。**

律速は「1本あたりの当たり率」なので、そこが見えないのは致命的。
`status.py` から毎回自動で呼ぶ。人が思い出す前提にしない。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

LOG = Path(__file__).resolve().parent.parent / "data" / "views.jsonl"


def record(videos: list[dict]) -> int:
    """公開済み動画の現在値を追記する。追記した本数を返す。"""
    LOG.parent.mkdir(parents=True, exist_ok=True)
    now = datetime.now(timezone.utc)
    rows = []
    for v in videos:
        if v["status"]["privacyStatus"] != "public":
            continue
        published = datetime.fromisoformat(v["snippet"]["publishedAt"].replace("Z", "+00:00"))
        rows.append({
            "at": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "id": v["id"],
            "hours": round((now - published).total_seconds() / 3600, 2),
            "views": int(v["statistics"].get("viewCount", 0)),
            "likes": int(v["statistics"].get("likeCount", 0)),
        })
    with LOG.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


def history(video_id: str) -> list[dict]:
    """1本の時系列を古い順に返す。"""
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        if d.get("id") == video_id:
            out.append(d)
    return sorted(out, key=lambda d: d["hours"])


def print_curves(ids: list[str], titles: dict[str, str]) -> None:
    """公開から48時間以内の動画について、伸び方を並べる。

    **横に並べないと比べられない。** 1本ずつ見ていると「多いか少ないか」の
    感覚だけが残り、前の1本と比較できない。
    """
    rows = [(i, history(i)) for i in ids]
    rows = [(i, h) for i, h in rows if h and h[-1]["hours"] <= 48]
    if not rows:
        return
    print("\n=== 公開後の伸び方（48時間以内）===")
    for vid, h in sorted(rows, key=lambda r: r[1][-1]["hours"]):
        点 = "  ".join(f"{d['hours']:.0f}h:{d['views']}" for d in h[-6:])
        print(f"  {titles.get(vid, vid)[:26]:28s} {点}")
