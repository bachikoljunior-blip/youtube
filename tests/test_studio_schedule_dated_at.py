"""`schedule --at` は `HH:MM`（きょう）と `YYYY-MM-DD HH:MM`（その日）を読む（2026-09-14 20:3x・hourly・Fable）。

それまで `cmd_schedule` は「当日以外には予約しない」で止めていました。その床はオーナーが 09/14 06:1x・09:0x に
外しており、同じ日に口（`YT_REFRESH_TOKEN`）が 2時間 死んで「当日の朝に口が無ければ 1日 出せない」形が実物で見えた
＝ 前の晩に翌日の枠へ置けるようにした。「1日1本」の門は **その日** で数える（`yt.today_lineup(date=...)`）。
"""
import datetime as dt

import pytest

from studio import cli, yt


def test_HHMMはきょう(monkeypatch):
    monkeypatch.setattr(cli, "now_jst", lambda: dt.datetime(2026, 1, 2, 9, 0, tzinfo=cli.JST))
    at = cli.parse_at("10:00")
    assert (at.date(), at.hour, at.minute) == (dt.date(2026, 1, 2), 10, 0)


def test_日付つきはその日():
    at = cli.parse_at("2026-09-15 10:00")
    assert at == dt.datetime(2026, 9, 15, 10, 0, tzinfo=cli.JST)
    assert cli.parse_at("2026-09-15T10:00") == at


def test_読めない形はNone():
    """陽性対照: 形が崩れていたら None（黙って きょう に倒さない）。"""
    assert cli.parse_at("10時") is None
    assert cli.parse_at("09/15 10:00") is None


def test_1日1本の門はその日で数える(monkeypatch):
    """翌日の枠に置くとき、門が数えるのは翌日の本であって きょう の本ではない。"""
    JST = cli.JST
    vids = [
        {"id": "TODAY", "privacy": "public", "publish_at": None, "published_at": "2026-01-02T01:00:00Z"},
        {"id": "TOMORROW", "privacy": "private", "publish_at": "2026-01-03T01:00:00Z", "published_at": "2026-01-02T05:00:00Z"},
    ]
    monkeypatch.setattr(yt, "scheduled_all", lambda: [v for v in vids if v["publish_at"] and v["privacy"] != "public"])
    monkeypatch.setattr(yt, "now_jst", lambda: dt.datetime(2026, 1, 2, 20, 0, tzinfo=JST))
    assert [v["id"] for v in yt.today_lineup(vids)] == ["TODAY"]
    assert [v["id"] for v in yt.today_lineup(vids, date=dt.date(2026, 1, 3))] == ["TOMORROW"]
