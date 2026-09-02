"""**外の上位の絵が、題・尺と同じ帳面から手元に落ちること。**（2026-09-03）

`[きょうの1本]` は毎周「外の帯の上位と**作りが違う点**を1つ、次の1本に入れる」と言うが、
帳面（`data/niche_ceiling.jsonl`）に在るのは題と尺だけで、**絵はどこにも無かった**。
02:4x の回は curl で4枚 取って初めて型（黄色い箱・赤字に白縁・人の顔）が見えた。
`niche_ceiling.fetch_thumbs()` がそれを毎周の道具にする。API 0単位。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import niche_ceiling as nc  # noqa: E402


def _rows():
    return [
        {"id": "L1", "views": 500, "form": "long", "secs": 1500, "title": "長1"},
        {"id": "L2", "views": 900, "form": "long", "secs": 1600, "title": "長2"},
        {"id": "S1", "views": 100, "form": "short", "secs": 60, "title": "短1"},
    ]


def test_形ごとに再生の多い順で落ち_在るものは撃たない(tmp_path):
    calls: list[str] = []

    def fake(url: str) -> bytes:
        calls.append(url)
        return b"JPG"

    got = nc.fetch_thumbs(_rows(), keep=1, root=tmp_path, fetch=fake)
    assert sorted(p.name for p in got) == ["L2.jpg", "S1.jpg"]
    assert calls == [nc.THUMB_URL.format(id="S1"), nc.THUMB_URL.format(id="L2")]
    # 2度目は撃たない
    calls.clear()
    got2 = nc.fetch_thumbs(_rows(), keep=1, root=tmp_path, fetch=fake)
    assert calls == [] and len(got2) == 2


def test_取れない絵は飛ばして止まらない(tmp_path, capsys):
    got = nc.fetch_thumbs(_rows(), keep=2, root=tmp_path,
                          fetch=lambda url: b"" if "L1" in url else b"x")
    assert sorted(p.name for p in got) == ["L2.jpg", "S1.jpg"]
    assert "取れませんでした: L1" in capsys.readouterr().out


def test_top_lines_は_絵の在りかを出す(tmp_path, monkeypatch):
    ledger = tmp_path / "niche_ceiling.jsonl"
    ledger.write_text(json.dumps({
        "at": "2026-09-02T16:25:02+00:00", "queries": ["q"], "form": "any",
        "summary": {"long": {"n": 2, "max": 900, "p90": 900, "median": 700, "channels": 2}},
        "top": [r for r in _rows() if r["form"] == "long"],
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    monkeypatch.setattr(nc, "THUMBS", tmp_path / "thumbs")
    from datetime import datetime, timezone
    now = datetime(2026, 9, 3, 0, 0, tzinfo=timezone.utc)
    lines = nc.top_lines("long", path=ledger, now=now)
    assert any("絵が手元に無い本 2本" in ln and "--thumbs-only" in ln for ln in lines), lines
    nc.fetch_thumbs([r for r in _rows() if r["form"] == "long"], keep=5,
                    root=tmp_path / "thumbs", fetch=lambda url: b"x")
    lines = nc.top_lines("long", path=ledger, now=now)
    assert any("絵は全部" in ln for ln in lines), lines
    assert any("niche_thumbs/L2.jpg" in ln for ln in lines), lines
