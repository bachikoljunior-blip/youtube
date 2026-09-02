"""`daily_pick.outside_long_lines`: **ほかの日に決めてある**外の作りの下書きの冒頭も数えて見せること
（2026-09-03 05:0x の定期の回）。API 0単位。

なぜ要るか: 画面は決めた日の1本の冒頭しか数えておらず、09/05 の決め `dRZnZrRy2Lw`（冒頭 4件 型の外）は
04:2x の回の申し送りでしか見えなかった。`rebake_today` は `for_day` の本しか焼き直さないので、
先の日の本は**台本を直す回**が要る —— 見えなければ、その回は来ない。
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from src import daily_pick

TOPICS = [
    {"id": "topic-a", "calc": "nenkin", "style": "outside_long"},
    {"id": "topic-b", "calc": "nenkin", "style": "outside_long"},
]


def _picks(tmp_path: Path, rows: list[dict]) -> Path:
    p = tmp_path / "daily_pick.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return p


def test_ほかの日に決めてある下書きの冒頭も出る(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "2026-09-07")
    monkeypatch.setattr(daily_pick, "PICKS", _picks(tmp_path, [
        {"for_day": "2026-09-04", "video_id": "VIDA0000001", "topic": "topic-a", "form": "長尺"},
        {"for_day": "2026-09-05", "video_id": "VIDB0000001", "topic": "topic-b", "form": "長尺"},
    ]))
    seen: list[str] = []

    def fake_lines(vid: str, topic: str, root=None, reset_hm: str = "16:00") -> list[str]:
        seen.append(vid)
        if vid == "VIDB0000001":
            return [f"     [!] **上がっている本 `{vid}` の冒頭は、外の上位4本の型の外**（4件）"]
        return [f"     冒頭（最初の 4コマ）: 控え `{vid}` は**外の上位4本の型の中**"]

    monkeypatch.setattr(daily_pick, "outside_opening_lines", fake_lines)
    drafts = [{"video_id": "VIDA0000001", "topic": "topic-a"},
              {"video_id": "VIDB0000001", "topic": "topic-b"}]
    cur = {"video_id": "VIDA0000001", "form": "長尺", "topic": "topic-a"}
    out = daily_pick.outside_long_lines(date(2026, 9, 4), cur, topics=TOPICS, drafts=drafts,
                                        readout=([], None))
    joined = "\n".join(out)
    assert seen == ["VIDA0000001", "VIDB0000001"]
    assert "ほかの日（09/05）に決めてある外の作りの下書き `VIDB0000001` `topic-b`" in joined
    assert "VIDB0000001` の冒頭は、外の上位4本の型の外" in joined


def test_ほかの日に決めていない下書きは数えない(monkeypatch, tmp_path: Path):
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "2026-09-07")
    monkeypatch.setattr(daily_pick, "PICKS", _picks(tmp_path, [
        {"for_day": "2026-09-04", "video_id": "VIDA0000001", "topic": "topic-a", "form": "長尺"},
    ]))
    seen: list[str] = []
    monkeypatch.setattr(daily_pick, "outside_opening_lines",
                        lambda vid, topic, root=None, reset_hm="16:00": seen.append(vid) or [])
    drafts = [{"video_id": "VIDA0000001", "topic": "topic-a"},
              {"video_id": "VIDB0000001", "topic": "topic-b"}]
    cur = {"video_id": "VIDA0000001", "form": "長尺", "topic": "topic-a"}
    out = daily_pick.outside_long_lines(date(2026, 9, 4), cur, topics=TOPICS, drafts=drafts,
                                        readout=([], None))
    assert seen == ["VIDA0000001"]
    assert "ほかの日" not in "\n".join(out)
