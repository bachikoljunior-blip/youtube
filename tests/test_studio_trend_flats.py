"""`trend.flats`（平らな区間が伸びを取り戻したか）の検査（2026-09-10 08:4x・optimizer・Opus）。

**なぜ**: 冒頭の註「平らは『止まった』ではない」の覆る条件（「一度も伸びない本が 3本」）を
**数える所がどこにも無く**、しかも文字どおり読むと**落ち着いた本は全部そこに当たり**ました
（どの本も最後は平らで終わる）。＝ 引けない条件ではなく、**いつでも引けてしまう条件**。
**陽性対照つき** —— 開いている平らを長さで見ない形へ戻すと落ちる。
**門 `FLAT_STOP_H` は 20.9時間（`EkNqtkK49Bw` が平らのあとに伸びた長さ）より上**でなければならない。
"""
from __future__ import annotations

import datetime as dt

from studio import trend


def _rows(vals: list[tuple[float, int]], vid: str = "V1") -> list[dict]:
    base = dt.datetime(2026, 9, 9, 10, 0, tzinfo=trend.JST)
    out: list[dict] = [{"event": "scheduled", "video_id": vid, "at": base.isoformat()}]
    out += [{"event": "measured", "id": vid, "age_h": a, "views": v,
             "at": (base + dt.timedelta(hours=a)).isoformat()} for a, v in vals]
    return out


def test_伸びを取り戻した平らを数える():
    """実物の形（`lQHX9LJ80Sg` 齢 30.3→33.2h の 468 が 5点 続き、34.0h で 501）。"""
    got = trend.flats(_rows([(30.3, 468), (31.3, 468), (32.2, 468), (33.2, 468), (34.0, 501), (45.6, 536)]))
    assert got["resumed"] == 1
    assert got["stayed"] == []


def test_短い平らは数えない():
    """陰性対照: 測りの間隔（床 41分）と区別が付かない長さは平らと呼ばない。"""
    got = trend.flats(_rows([(30.3, 468), (30.9, 468), (31.5, 501), (45.0, 536)]))
    assert got["resumed"] == 0


def test_まだ見ている途中の平らは_戻らないままに数えない():
    """**陽性対照の当のもの**: 開いている平らを長さで見ずに `stayed` へ入れると、
    毎周それが入って「3件」がすぐ埋まる（＝ いつでも引けてしまう条件に戻る）。"""
    got = trend.flats(_rows([(17.4, 927), (18.8, 927), (20.2, 927), (21.6, 927)]))
    assert got["stayed"] == []
    assert got["open"] == 1


def test_24時間を越えて戻らなければ数える():
    got = trend.flats(_rows([(17.4, 927), (25.0, 927), (35.0, 927), (44.0, 927)]))
    assert len(got["stayed"]) == 1
    assert got["stayed"][0]["views"] == 927
    assert got["resumed"] == 0


def test_48hを越えた平らは数えない():
    """陰性対照: 48h 超の平らは「止まり」と読んでよい側（比べる相手が無い）。"""
    got = trend.flats(_rows([(50.0, 66), (55.0, 66), (60.0, 66), (69.6, 66)]))
    assert got["stayed"] == [] and got["resumed"] == 0


def test_こちらの作りの本だけ数える():
    rows = _rows([(17.4, 927), (18.8, 927), (20.2, 927), (30.0, 927)])
    rows = [r for r in rows if r.get("event") != "scheduled"]  # scheduled が無い ＝ 旧作り
    assert trend.flats(rows)["stayed"] == []
