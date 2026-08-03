"""投稿履歴。トピックと動画IDを紐づけて、後から実績を評価できるようにする。"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from .config import ROOT

STATE_PATH = ROOT / "state" / "published.json"


def load() -> list[dict]:
    if not STATE_PATH.exists():
        return []
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def record(video_id: str, topic_id: str, title: str) -> None:
    entries = load()
    entries.append({
        "video_id": video_id,
        "topic_id": topic_id,
        "title": title,
        "published_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(entries, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
