"""`trend.mouth_closed_line` —— **口が閉じてから周が何回 立ったか**（`docs/GOAL.md` (4-f-6) を読む印字）。

2026-09-14 19:4x・optimizer・Opus。18:5x の `hourly` は (4-f-6) に「**3周 続けて 3行 のままなら**」と
書きましたが、**その 3周 を数える物がどこにもありませんでした**（§5 教訓の形 7つ目 ＝
覆る条件を書いたら、それを読む印字も一緒に作ること）。

**陽性対照**（撃って落とした）:
 (1) `channel` の行で黙る枝（口が戻った側）を外すと `test_口が戻ったら黙る` が落ちる。
 (2) 周へ畳まずに行を数えると `test_同じ周に_2回_拒まれても_1周` が落ちる。
 (3) 門（3周）を 0 にすると `test_門は_3周` が落ちる。
"""
import datetime as dt

from studio import trend

JST = dt.timezone(dt.timedelta(hours=9))


def _t(h, m=0):
    return dt.datetime(2026, 9, 14, h, m, tzinfo=JST).isoformat()


def _rounds(*hs):
    return [{"round": _t(h), "role": r} for h in hs for r in ("hourly", "optimizer")]


def _now(h, m=0):
    return dt.datetime(2026, 9, 14, h, m, tzinfo=JST)


CH = {"event": "channel", "id": "UChTXZ", "at": _t(17, 15)}


def test_拒まれた行が無ければ黙る():
    assert trend.mouth_closed_line([CH], _rounds(17, 18), now=_now(19)) == ""


def test_口が戻ったら黙る():
    rows = [{"event": "token_rejected", "id": "-", "at": _t(18, 50)},
            {"event": "channel", "id": "UChTXZ", "at": _t(19, 5)}]
    assert trend.mouth_closed_line(rows, _rounds(18, 19), now=_now(19, 30)) == ""


def test_同じ周に_2回_拒まれても_1周():
    rows = [CH,
            {"event": "token_rejected", "id": "-", "at": _t(18, 50)},
            {"event": "token_rejected", "id": "-", "at": _t(18, 55)}]
    line = trend.mouth_closed_line(rows, _rounds(17, 18), now=_now(19))
    assert "**1周" in line and "あと 2周" in line


def test_門は_3周():
    rows = [CH] + [{"event": "token_rejected", "id": "-", "at": _t(h, 50)} for h in (18, 19, 20)]
    line = trend.mouth_closed_line(rows, _rounds(18, 19, 20), now=_now(21))
    assert "**3周" in line and "**引かれました**" in line


def test_行は口の名と置く物の在り処を出す():
    rows = [CH, {"event": "token_rejected", "id": "-", "at": _t(18, 50)}]
    line = trend.mouth_closed_line(rows, _rounds(18), now=_now(19))
    assert line.startswith("!! **口（`YT_REFRESH_TOKEN`）は閉じたままです**")
    assert "(4-f)" in line and "owner_ask.py" in line
