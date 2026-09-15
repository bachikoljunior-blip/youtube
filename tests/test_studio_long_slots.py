"""長尺の枠は 1日に複数（`cli.LONG_SLOTS`）・予約の刻だけ動かす口（`cli.cmd_reschedule`）。

2026-09-15 14:xx・optimizer・Fable 5.1（ultracode）。固定 2（期限内にできるか → できる以外なら やり方を疑え）で
疑った先: 閉じた長尺が 09/18・09/19 の枠で 3〜4日 座っていた（1周 1本 焼けるのに、出す枠が 1日 1本 だった）。
理由と覆る条件は `cli.LONG_SLOTS` の註・JOURNAL 2026-09-15 14:xx。

**陽性対照**（撃って落とした）: `LONG_SLOT_LEAD_H` を 0 にすると `test_2時間より先` が落ち、
`cmd_reschedule` の public の門を外すと `test_公開ずみは動かさない` が落ちる。
"""
import datetime as dt

import pytest

from studio import cli, yt

JST = cli.JST
NOW = dt.datetime(2026, 9, 15, 14, 30, tzinfo=JST)


def _t(m, d, hh, mm=0):
    return dt.datetime(2026, m, d, hh, mm, tzinfo=JST)


def test_2時間より先の空いている枠を早い順に():
    taken = [_t(9, 15, 10), _t(9, 15, 19), _t(9, 16, 10), _t(9, 16, 19)]
    got = cli.next_long_slots(taken, NOW)
    assert got == [_t(9, 15, 21), _t(9, 16, 12), _t(9, 16, 21)]


def test_2時間より先():
    """いま 14:30 → 16:30 より前の刻は出ない（処理と差し替えの余地）。"""
    assert cli.next_long_slots([], _t(9, 15, 17, 30))[0] == _t(9, 15, 21)
    assert cli.next_long_slots([], _t(9, 15, 9, 30))[0] == _t(9, 15, 12)


def test_近い刻に本が在れば埋まっている():
    """19:30 に本が在れば 19:00 の枠は取らない（±60分）。"""
    got = cli.next_long_slots([_t(9, 16, 19, 30)], _t(9, 16, 8))
    assert _t(9, 16, 19) not in got
    assert got[0] == _t(9, 16, 12)


def test_門の数は1か所():
    assert cli.LONG_SLOTS == ("12:00", "19:00", "21:00")
    assert cli.LONG_SLOT_LEAD_H >= 1.0


def _stage(monkeypatch, tmp_path, privacy="private", publish_at="2026-09-18T10:00:00Z"):
    sid = "2026-09-18-x"
    (tmp_path / f"{sid}.json").write_text(
        '{"id": "%s", "date": "2026-09-18", "title": "t", "takeaway": "k", "description": "d", "tags": [],'
        ' "form": "long", "segments": []}' % sid,
        encoding="utf-8")
    monkeypatch.setattr(cli.script, "SCRIPTS", tmp_path)
    rows = [{"event": "scheduled", "id": sid, "video_id": "VID", "publish_at": "2026-09-18T19:00+09:00",
             "at": "2026-09-15T11:00:00+09:00"}]
    monkeypatch.setattr(cli, "ledger_rows", lambda: rows)
    written = []
    monkeypatch.setattr(cli, "ledger", lambda ev, vid, **kw: written.append({"event": ev, "id": vid, **kw}))
    monkeypatch.setattr(cli, "now_jst", lambda: NOW)
    live = [{"id": "VID", "privacy": privacy, "publish_at": publish_at, "published_at": "2026-09-15T02:00:00Z",
             "title": "t", "views": 0, "likes": 0}]
    monkeypatch.setattr(yt, "all_videos", lambda refresh=False: live)
    monkeypatch.setattr(yt, "scheduled_all", lambda: [v for v in live if v["publish_at"] and v["privacy"] != "public"])
    monkeypatch.setattr(yt, "now_jst", lambda: NOW)
    moved = []
    monkeypatch.setattr(yt, "reschedule", lambda vid, at: moved.append((vid, at)))
    return sid, written, moved


class _A:
    def __init__(self, id, at, force=False, dry_run=False):
        self.id, self.at, self.force, self.dry_run = id, at, force, dry_run


def test_刻だけ動かして台帳に行を足す(monkeypatch, tmp_path):
    sid, written, moved = _stage(monkeypatch, tmp_path)
    assert cli.cmd_reschedule(_A(sid, "2026-09-15 21:00", force=True)) == 0
    assert moved == [("VID", _t(9, 15, 21))]
    assert written[-1]["event"] == "scheduled"
    assert written[-1]["video_id"] == "VID"
    assert written[-1]["publish_at"] == "2026-09-15T21:00+09:00"
    assert written[-1]["moved_from"] == "2026-09-18T19:00+09:00"


def test_公開ずみは動かさない(monkeypatch, tmp_path):
    sid, written, moved = _stage(monkeypatch, tmp_path, privacy="public", publish_at=None)
    assert cli.cmd_reschedule(_A(sid, "2026-09-15 21:00", force=True)) == 1
    assert moved == [] and written == []


def test_同じ日に本が在れば_force_が要る(monkeypatch, tmp_path, capsys):
    sid, written, moved = _stage(monkeypatch, tmp_path)
    other = {"id": "OTHER", "privacy": "public", "publish_at": None, "published_at": "2026-09-15T01:00:00Z",
             "title": "o", "views": 1, "likes": 0}
    live = yt.all_videos() + [other]
    monkeypatch.setattr(yt, "all_videos", lambda refresh=False: live)
    assert cli.cmd_reschedule(_A(sid, "2026-09-15 21:00")) == 1
    assert "もう本がある" in capsys.readouterr().out
    assert moved == []


def test_過ぎた刻は拒む(monkeypatch, tmp_path):
    sid, written, moved = _stage(monkeypatch, tmp_path)
    assert cli.cmd_reschedule(_A(sid, "2026-09-15 14:00", force=True)) == 1
    assert moved == []


def test_statusの1行は空いている枠を3つ言う():
    vids = [{"id": "A", "privacy": "public", "publish_at": None, "published_at": "2026-09-15T01:00:00Z"},
            {"id": "B", "privacy": "private", "publish_at": "2026-09-15T10:00:00Z", "published_at": "2026-09-15T02:00:00Z"}]
    line = cli.long_slot_line(vids, NOW)
    assert "09/15 21:00" in line and "09/16 12:00" in line
    assert "09/15 19:00" not in line
