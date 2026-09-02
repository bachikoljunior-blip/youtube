"""`daily_pick.outside_long_lines`: 外の作りを写した長尺の下書きが池に在る日は、
その日の1本をそれにする行が出ること（2026-09-03・最適化の回）。API 0単位。"""
from __future__ import annotations

from datetime import date

from src import daily_pick

TOPICS = [
    {"id": "nenkin-uketorikata-65-70-75-handan", "calc": "nenkin", "style": "outside_long"},
    {"id": "s-kokuho-2wari", "calc": "kokuho"},
]


def test_下書きが在って別の本を決めていたら名指しする(monkeypatch):
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "2026-09-07")
    drafts = [{"video_id": "LONGID12345", "topic": "nenkin-uketorikata-65-70-75-handan"}]
    cur = {"video_id": "SHORTID1234", "form": "ショート", "topic": "s-kokuho-2wari"}
    out = daily_pick.outside_long_lines(date(2026, 9, 4), cur, topics=TOPICS, drafts=drafts)
    joined = "\n".join(out)
    assert "LONGID12345" in joined
    assert "09/04 の1本はこれにすること" in joined
    assert "--pick 長尺 nenkin-uketorikata-65-70-75-handan --video LONGID12345 --day 2026-09-04" in joined


def test_その本を決めていれば命令の行は出ない(monkeypatch):
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "2026-09-07")
    drafts = [{"video_id": "LONGID12345", "topic": "nenkin-uketorikata-65-70-75-handan"}]
    cur = {"video_id": "LONGID12345", "form": "長尺", "topic": "nenkin-uketorikata-65-70-75-handan"}
    out = daily_pick.outside_long_lines(date(2026, 9, 4), cur, topics=TOPICS, drafts=drafts)
    assert len(out) == 1
    assert "これにすること" not in out[0]


def test_下書きが無ければ作る手を出す(monkeypatch):
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "2026-09-07")
    out = daily_pick.outside_long_lines(date(2026, 9, 4), None, topics=TOPICS, drafts=[])
    joined = "\n".join(out)
    assert "まだ池に1本も在りません" in joined
    assert "python -m src.pipeline --topic nenkin-uketorikata-65-70-75-handan --dry-run" in joined


def test_前提が閉じていれば何も出ない(monkeypatch):
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "")
    drafts = [{"video_id": "LONGID12345", "topic": "nenkin-uketorikata-65-70-75-handan"}]
    assert daily_pick.outside_long_lines(date(2026, 9, 4), None, topics=TOPICS, drafts=drafts) == []


def test_実物の前提が開いているあいだは期限が読める():
    dl = daily_pick._outside_long_deadline()
    assert dl == "" or dl.startswith("2026-")
