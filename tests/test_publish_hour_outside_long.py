"""**外の作りを写した長尺の日は、公開時刻を掃かない**（2026-09-03・最適化の回）。

前提「外の作り方を写した長尺」は n=2 の試験で、`sweep_hour()` の奇数日（未試行の時刻）に
載せると 1本目 17時・2本目 9時 と時刻の交絡が乗り、48h の判定が 09/06 の枠の 2時間前に落ちる。
`publish_hour.place_hour()` はその日の1本が `style: outside_long` なら対照（`best_hour()`）に置く。
"""
from __future__ import annotations

import datetime as _dt
import json

from src import publish_hour


def _picks(tmp_path, rows):
    p = tmp_path / "daily_pick.jsonl"
    p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return p


TOPICS = [{"id": "zaishoku-2026-62man", "style": "outside_long"},
          {"id": "s-shokibo", "style": ""}]


def test_外の作りの長尺の日は対照の時刻に置く(monkeypatch, tmp_path):
    day = _dt.date(2026, 9, 4)
    picks = _picks(tmp_path, [{"for_day": "2026-09-04", "form": "長尺", "topic": "zaishoku-2026-62man"}])
    assert publish_hour.outside_long_day(day, picks_path=picks, topics=TOPICS) is True
    monkeypatch.setattr(publish_hour, "outside_long_day", lambda d, **kw: True)
    monkeypatch.setattr(publish_hour, "best_hour", lambda rows=None: 9)
    # 掃く側が 17時 と言っても、対照の 9時 に置く
    assert publish_hour.place_hour(day, sweep=lambda d: 17, config=lambda: 19) == 9


def test_ショートの日は掃く(monkeypatch, tmp_path):
    day = _dt.date(2026, 9, 3)
    picks = _picks(tmp_path, [{"for_day": "2026-09-03", "form": "ショート", "topic": "s-shokibo"}])
    assert publish_hour.outside_long_day(day, picks_path=picks, topics=TOPICS) is False
    monkeypatch.setattr(publish_hour, "outside_long_day", lambda d, **kw: False)
    assert publish_hour.place_hour(day, sweep=lambda d: 17, config=lambda: 9) == 17


def test_決めの無い日は掃く(tmp_path):
    day = _dt.date(2026, 9, 9)
    picks = _picks(tmp_path, [])
    assert publish_hour.outside_long_day(day, picks_path=picks, topics=TOPICS) is False


def test_対照が無ければ既定へ倒れる(monkeypatch):
    day = _dt.date(2026, 9, 4)
    monkeypatch.setattr(publish_hour, "outside_long_day", lambda d, **kw: True)
    monkeypatch.setattr(publish_hour, "best_hour", lambda rows=None: None)
    assert publish_hour.place_hour(day, sweep=lambda d: 17, config=lambda: 11) == 11


def test_実物の09_04の決めは対照に置く():
    """repo の実物（`data/daily_pick.jsonl`・`config/topics.yaml`）で、09/04・09/05 が外の作りの長尺で
    在るあいだは、この2日は対照の時刻。決めが変わったらこの検査は意味を失うので、その日は消してよい。"""
    from src import daily_pick
    for d in (_dt.date(2026, 9, 4), _dt.date(2026, 9, 5)):
        cur = daily_pick.current(d)
        if not cur:
            continue
        if publish_hour.outside_long_day(d):
            assert publish_hour.place_hour(d) == (publish_hour.best_hour() or publish_hour.config_hour() or 9)
