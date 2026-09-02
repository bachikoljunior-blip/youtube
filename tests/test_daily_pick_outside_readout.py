"""`daily_pick.outside_long_readout` —— 外の作りの長尺の 24h の先読みの門（2026-09-03 03:xx・最適化の回）。

1日1本の下で、1本目の 48h（＝ 3日目の枠の時刻）を待つと 3枠が盲目で決まる。
24h の数で「次の未決の日の形」を先に決める門が、画面に出ること。API 0単位。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from src import daily_pick

TOPICS = [
    {"id": "zaishoku-2026-62man", "calc": "zaishoku", "style": "outside_long"},
    {"id": "nenkin-uketorikata-65-70-75-handan", "calc": "nenkin", "style": "outside_long"},
    {"id": "kakyu-nenkin-shinsei-teikibin-ni-nai", "calc": "kakyu", "style": "outside_long"},
    {"id": "s-kokuho-2wari", "calc": "kokuho"},
]
PUB = datetime(2026, 9, 4, 8, 0, tzinfo=timezone.utc)   # 09/04 17:00 JST


def _files(tmp_path: Path, hours: float, views: int) -> tuple[Path, Path]:
    up = tmp_path / "uploaded.jsonl"
    up.write_text(json.dumps({"video_id": "LONG1", "topic": "zaishoku-2026-62man",
                              "at": PUB.strftime("%Y-%m-%dT%H:%M:%SZ"),
                              "uploaded_at": "2026-09-02T17:14:31+00:00"}) + "\n"
                  + json.dumps({"video_id": "LONG2", "topic": "nenkin-uketorikata-65-70-75-handan",
                                "at": None, "uploaded_at": "2026-09-02T17:27:00+00:00"}) + "\n",
                  encoding="utf-8")
    vw = tmp_path / "views.jsonl"
    vw.write_text(json.dumps({"at": "x", "id": "LONG1", "hours": hours, "views": views}) + "\n",
                  encoding="utf-8")
    return up, vw


def test_24h前は待てと言い判定は無い(tmp_path):
    up, vw = _files(tmp_path, 6.0, 3)
    lines, v = daily_pick.outside_long_readout(PUB + timedelta(hours=6), topics=TOPICS,
                                               uploaded_path=up, views_path=vw)
    assert v is None
    assert "まで待つ" in "\n".join(lines)


def test_24hで門の上ならgo(tmp_path):
    up, vw = _files(tmp_path, 25.0, daily_pick.OUTSIDE_24H_GATE)
    lines, v = daily_pick.outside_long_readout(PUB + timedelta(hours=25), topics=TOPICS,
                                               uploaded_path=up, views_path=vw)
    assert v == "go"
    assert "次の未決の日の1本も外の作りの長尺" in "\n".join(lines)


def test_24hで門の下ならstop(tmp_path):
    up, vw = _files(tmp_path, 25.0, daily_pick.OUTSIDE_24H_GATE - 1)
    lines, v = daily_pick.outside_long_readout(PUB + timedelta(hours=25), topics=TOPICS,
                                               uploaded_path=up, views_path=vw)
    assert v == "stop"
    joined = "\n".join(lines)
    # 門の下でも形はショートへ戻さない（ショートの視聴時間は 4,000時間 の門に 0 入る・`gate_arithmetic`）
    assert "それでも次の未決の日の1本は長尺" in joined
    assert "規則の密度のショート" not in joined
    assert "1つ変える" in joined


def test_まだ出ていない本は時刻だけ出す(tmp_path):
    up, vw = _files(tmp_path, 0.0, 0)
    lines, v = daily_pick.outside_long_readout(PUB - timedelta(hours=10), topics=TOPICS,
                                               uploaded_path=up, views_path=vw)
    assert v is None
    assert "09/04 17:00 JST に出ます" in lines[0]
    assert "09/05 17:00" in lines[0] and "09/06 17:00" in lines[0]


def test_stopでも形は長尺のままで下書きを名指しする(monkeypatch):
    """2026-09-03 夜: 門の下で「その日はショート」へ倒すのをやめた。ショートは 4,000時間 の門に 0時間
    （`gate_arithmetic`）。門の下は「形を戻す」ではなく「作りを1つ変える」。"""
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "2026-09-07")
    drafts = [{"video_id": "LONG2", "topic": "nenkin-uketorikata-65-70-75-handan"}]
    out = daily_pick.outside_long_lines(date(2026, 9, 6), None, topics=TOPICS, drafts=drafts,
                                        readout=(["(先読み)"], "stop"))
    joined = "\n".join(out)
    assert "09/06 の1本も長尺のまま" in joined
    assert "規則の密度のショート" not in joined
    assert "1つ変える" in joined
    assert "LONG2" in joined and "これにすること" in joined


def test_stopで下書きが尽きていても次の題材を作る手を出す(monkeypatch, tmp_path):
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "2026-09-07")
    up, _ = _files(tmp_path, 25.0, 3)
    out = daily_pick.outside_long_lines(date(2026, 9, 6), None, topics=TOPICS, drafts=[],
                                        readout=(["(先読み)"], "stop"), uploaded_path=up)
    joined = "\n".join(out)
    assert "python -m src.pipeline --topic kakyu-nenkin-shinsei-teikibin-ni-nai --dry-run" in joined
    assert "作りを1つ変えて" in joined


def test_goで下書きが尽きていれば次の題材を作る手を出す(monkeypatch, tmp_path):
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "2026-09-07")
    up, _ = _files(tmp_path, 25.0, 50)
    out = daily_pick.outside_long_lines(date(2026, 9, 6), None, topics=TOPICS, drafts=[],
                                        readout=(["(先読み)"], "go"), uploaded_path=up)
    joined = "\n".join(out)
    assert "python -m src.pipeline --topic kakyu-nenkin-shinsei-teikibin-ni-nai --dry-run" in joined
    assert "外の作りの長尺の次の1本" in joined


def test_判定が無いうちは3本目を作らない(monkeypatch, tmp_path):
    monkeypatch.setattr(daily_pick, "_outside_long_deadline", lambda: "2026-09-07")
    monkeypatch.setattr(daily_pick, "PICKS", tmp_path / "picks.jsonl")
    (tmp_path / "picks.jsonl").write_text(
        json.dumps({"for_day": "2026-09-05", "video_id": "LONG2"}) + "\n", encoding="utf-8")
    drafts = [{"video_id": "LONG2", "topic": "nenkin-uketorikata-65-70-75-handan"}]
    out = daily_pick.outside_long_lines(date(2026, 9, 6), None, topics=TOPICS, drafts=drafts,
                                        readout=([], None))
    joined = "\n".join(out)
    assert "まだ決めないこと" in joined
    assert "src.pipeline" not in joined


def test_実物の題材に未着手の外の作りが1件は残っている():
    """`go` が出た瞬間に作る題材が無いと、先読みの門は画面を1行 増やしただけになる。"""
    tops = [t for t in daily_pick._topics() if str(t.get("style") or "") == "outside_long"]
    assert tops, "style: outside_long の題材が台帳に無い"
    assert all(int(t.get("minutes") or 0) >= 15 for t in tops), "outside_long は minutes: 20 の口で作る"
    assert daily_pick._unbuilt_outside(tops), (
        "外の作りの題材が全部 上げずみ —— `go` が出ても作る題材が無い。`config/topics.yaml` に1件 足すこと")
