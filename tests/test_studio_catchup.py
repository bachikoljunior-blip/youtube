"""`studio.cli catchup` —— 日枠が戻った周に、詰まっている手を安い順で撃つ口（2026-09-17 08:4x）。

守っているのは 3つ:
  (1) **安い順で撃つ** —— 1単位 の口（`yt.channel`）が先。ここで 403 なら 50単位 の口へ進まない。
  (2) **`publishAt` が在る本は打ち直さない**（`cmd_catchup` の覆る条件 (2)）。
  (3) **透かしは 1度だけ** —— 台帳に `watermark_set` が在れば撃たない。
`--dry-run` は **0単位**（`yt` を 1度も呼ばない）。
"""
from __future__ import annotations

import argparse
import datetime as dt

import pytest

from studio import cli
from studio.common import JST


class _Boom(Exception):
    pass


def _bad(vid="VID1", sid="script-1", at=None):
    return {"video_id": vid, "script": sid, "publish_at": at or dt.datetime(2026, 9, 15, 21, 0, tzinfo=JST),
            "title": "題", "code": 401, "late_h": 30.0, "hint": "刻が消えている見立て"}


def test_dry_run_は_口を1度も呼ばない(monkeypatch, capsys):
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [_bad()])
    monkeypatch.setattr(cli, "ledger_rows", lambda: [])
    monkeypatch.setattr(cli.yt, "channel", lambda: pytest.fail("dry-run で口を撃った"))
    assert cli.cmd_catchup(argparse.Namespace(dry_run=True)) == 0
    assert "dry-run" in capsys.readouterr().out


def test_1単位の口が落ちたら_50単位の口へ進まない(monkeypatch):
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [_bad()])
    monkeypatch.setattr(cli, "ledger_rows", lambda: [])
    monkeypatch.setattr(cli.yt, "channel", lambda: (_ for _ in ()).throw(_Boom()))
    monkeypatch.setattr(cli.yt, "readiness", lambda *a, **k: pytest.fail("1単位 の口が落ちたのに進んだ"))
    monkeypatch.setattr(cli, "cmd_watermark", lambda *a, **k: pytest.fail("1単位 の口が落ちたのに進んだ"))
    with pytest.raises(_Boom):
        cli.cmd_catchup(argparse.Namespace(dry_run=False))


def test_刻が在る本は打ち直さない(monkeypatch, capsys):
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [_bad()])
    monkeypatch.setattr(cli.pubcheck, "taken_slots", lambda *a, **k: [])
    monkeypatch.setattr(cli, "ledger_rows", lambda: [{"event": "watermark_set"}])
    monkeypatch.setattr(cli.yt, "channel", lambda: {"subscriberCount": 32, "viewCount": 1})
    monkeypatch.setattr(cli.yt, "readiness", lambda vid: {
        "no_publish_at": False, "publish_at": "2026-09-18T10:00:00Z", "privacy": "private"})
    monkeypatch.setattr(cli, "cmd_reschedule", lambda *a, **k: pytest.fail("刻が在るのに打ち直した"))
    assert cli.cmd_catchup(argparse.Namespace(dry_run=False)) == 0
    assert "打ち直しません" in capsys.readouterr().out


def test_刻が無い本は空き枠へ打ち直し_透かしも置く(monkeypatch):
    calls = []
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [_bad()])
    monkeypatch.setattr(cli.pubcheck, "taken_slots", lambda *a, **k: [])
    monkeypatch.setattr(cli, "next_long_slots",
                        lambda taken, now, n=3: [dt.datetime(2026, 9, 18, 19, 0, tzinfo=JST)])
    monkeypatch.setattr(cli, "ledger_rows", lambda: [])
    monkeypatch.setattr(cli.yt, "channel", lambda: {"subscriberCount": 32, "viewCount": 1})
    monkeypatch.setattr(cli.yt, "readiness", lambda vid: {
        "no_publish_at": True, "publish_at": None, "privacy": "private"})
    monkeypatch.setattr(cli, "cmd_reschedule", lambda ns: calls.append(("reschedule", ns.id, ns.at)) or 0)
    monkeypatch.setattr(cli, "cmd_watermark", lambda ns: calls.append(("watermark",)) or 0)
    assert cli.cmd_catchup(argparse.Namespace(dry_run=False)) == 0
    assert calls == [("reschedule", "script-1", "2026-09-18 19:00"), ("watermark",)]


def test_透かしが置いてあれば撃たない(monkeypatch):
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [])
    monkeypatch.setattr(cli, "ledger_rows", lambda: [{"event": "watermark_set"}])
    monkeypatch.setattr(cli.yt, "channel", lambda: pytest.fail("撃つものが無いのに口を撃った"))
    monkeypatch.setattr(cli, "cmd_watermark", lambda *a, **k: pytest.fail("2度目 の透かし"))
    assert cli.cmd_catchup(argparse.Namespace(dry_run=False)) == 0


def test_catchup_line_は_詰まった手を1行で名指しする(monkeypatch):
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [_bad()])
    s = cli.catchup_line([])
    assert "出ていない本 1本" in s and "透かし 未" in s and "約102単位" in s
    monkeypatch.setattr(cli.pubcheck, "missing", lambda *a, **k: [])
    assert cli.catchup_line([{"event": "watermark_set"}]).endswith("0件")


def test_meter_は_Data_APIの口だけ数える():
    from studio import meter
    rs = [{"at": "2026-09-17T08:00:00+09:00", "api": "youtube", "method": "channels.list", "units": 1, "ok": True},
          {"at": "2026-09-17T08:01:00+09:00", "api": "youtubeAnalytics", "method": "reports.query",
           "units": 0, "ok": True}]
    s = meter.spent("2026-09-17T00:00:00+09:00", rs)
    assert s["calls"] == 1 and s["total"] == 1
