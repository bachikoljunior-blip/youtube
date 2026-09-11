"""**維持率と流入の口**（`studio/analytics.py`・`cli.cmd_analytics`・`trend.analytics_line`）。

2026-09-10 16:1x・optimizer・Opus。**規則A**（`studio` を import しているので live の印が機械で付く・§6）。

**陽性対照は「壊したら落ちる」まで撃つこと**（§5 の教訓の形3つ目）——
下の 3つ は、この回に実際に壊して落ちるのを見てから置いています。
"""
from __future__ import annotations

import datetime as dt

import pytest

from studio import analytics, cli, trend

JST = dt.timezone(dt.timedelta(hours=9))


def _at(s: str) -> str:
    return dt.datetime.fromisoformat(s).replace(tzinfo=JST).isoformat(timespec="seconds")


# ---------------------------------------------------------------- analytics.py

def test_返りの欄の名前は返り自身から取る():
    """`metrics` に並べた順ではなく `columnHeaders` から読むこと（API が並べ替えても壊れない）。"""
    res = {"columnHeaders": [{"name": "video"}, {"name": "views"}],
           "rows": [["abc", 12]]}
    assert analytics._rows(res) == [{"video": "abc", "views": 12}]


def test_行が無ければ空の並び():
    assert analytics._rows({}) == []


def test_遅れは最後の日から数える():
    rows = [{"day": "2026-09-05"}, {"day": "2026-09-07"}, {"day": "2026-09-06"}]
    assert analytics.lag_days(rows, today=dt.date(2026, 9, 10)) == 3


def test_行が1つも無い回は遅れを0にしない():
    """**引けなかったと 0日 は別**（`analytics` の覆る条件 (2)）。"""
    assert analytics.lag_days([], today=dt.date(2026, 9, 10)) is None


def test_本の並びは重複を畳んで上限で切る(monkeypatch):
    got = {}

    def fake(**kw):
        got.update(kw)
        return {"columnHeaders": [{"name": "video"}], "rows": []}

    monkeypatch.setattr(analytics, "_query", fake)
    analytics.per_video(["a", "a", "b"] + [f"v{i}" for i in range(80)], "2026-09-01", "2026-09-07")
    ids = got["filters"].split("==")[1].split(",")
    assert len(ids) == analytics.MAX_IDS
    assert ids[:2] == ["a", "b"]          # 重複は畳む・順は保つ


def test_本が0本なら撃たない(monkeypatch):
    def boom(**kw):
        pytest.fail("撃ってはいけない")

    monkeypatch.setattr(analytics, "_query", boom)
    assert analytics.per_video([], "2026-09-01", "2026-09-07") == []


# ---------------------------------------------------------------- cli の門

def test_引く回かは前に引いた刻で決まる():
    now = dt.datetime(2026, 9, 10, 16, 0, tzinfo=JST)
    assert cli.analytics_due([], now=now) is True
    fresh = [{"event": "analytics_day", "id": "2026-09-07", "at": _at("2026-09-10 06:00")}]
    assert cli.analytics_due(fresh, now=now) is False
    old = [{"event": "analytics_day", "id": "2026-09-06", "at": _at("2026-09-09 06:00")}]
    assert cli.analytics_due(old, now=now) is True


def test_引く本は旧作りも入れる():
    """**旧作りを落とすと、§7「90秒の上限」の比べる相手が 0本 になります。**"""
    now = dt.datetime(2026, 9, 10, 16, 0, tzinfo=JST)
    rows = [
        {"event": "measured", "id": "new1", "at": _at("2026-09-10 15:00")},
        {"event": "measured", "id": "old1", "at": _at("2026-09-10 14:00")},
        {"event": "measured", "id": "old1", "at": _at("2026-09-10 15:00")},
        {"event": "measured", "id": "toooold", "at": _at("2026-08-01 15:00")},
        {"event": "scheduled", "id": "x", "video_id": "new1", "at": _at("2026-09-10 09:00")},
    ]
    got = cli.analytics_recent_ids(rows, now=now)
    assert got == ["new1", "old1"]          # 窓の外は落ちる・重複は畳む・新しい順


# ---------------------------------------------------------------- trend の行

def _ledger(videos) -> list[dict]:
    rows = [
        {"event": "analytics_day", "id": "2026-09-06", "views": 783, "minutes": 57,
         "at": _at("2026-09-10 16:00")},
        {"event": "analytics_day", "id": "2026-09-07", "views": 318, "minutes": 104,
         "at": _at("2026-09-10 16:00")},
        {"event": "analytics_traffic", "id": "2026-09-07", "lag_days": 3,
         "sources": {"SHORTS": 3413, "YT_SEARCH": 273}, "at": _at("2026-09-10 16:00")},
    ]
    for vid, studio, views, sec, pct, subs in videos:
        rows.append({"event": "analytics_video", "id": vid, "studio": studio, "views": views,
                     "avg_seconds": sec, "avg_percent": pct, "subs_gained": subs,
                     "day": "2026-09-07", "at": _at("2026-09-10 16:00")})
    return rows


def test_新と旧を分けるのは行に書いてある印():
    rows = _ledger([("n1", True, 145, 38, 42.09, 0), ("n2", True, 256, 45, 48.56, 0),
                    ("o1", False, 350, 15, 53.56, 0), ("o2", False, 294, 15, 50.19, 1)])
    a = trend.analytics_state(rows, now=dt.datetime(2026, 9, 10, 17, 0, tzinfo=JST))
    assert a["new"]["n"] == 2 and a["old"]["n"] == 2
    assert a["new"]["sec_med"] == 45 and a["old"]["sec_med"] == 15
    assert a["subs"] == 1
    assert round(a["shorts_pct"], 1) == 92.6
    assert a["lag_days"] == 3


def test_再生の少ない本は維持率の比べに入れない():
    """**陽性対照**: 門を外すと、1回 の本の 0.0% と 107.8% が幅を決めます。"""
    rows = _ledger([("n1", True, 145, 38, 42.09, 0),
                    ("o1", False, 350, 15, 53.56, 0),
                    ("junk1", False, 1, 0, 0.0, 0),
                    ("junk2", False, 6, 29, 107.78, 0)])
    a = trend.analytics_state(rows)
    assert a["old"]["n"] == 1
    assert a["old"]["avg_percent"] == [53.56]


def test_同じ本を2度引いたら新しいほうだけ():
    rows = _ledger([("n1", True, 100, 30, 40.0, 0)])
    rows.append({"event": "analytics_video", "id": "n1", "studio": True, "views": 145,
                 "avg_seconds": 38, "avg_percent": 42.09, "subs_gained": 0,
                 "day": "2026-09-07", "at": _at("2026-09-10 17:00")})
    a = trend.analytics_state(rows)
    assert a["new"]["n"] == 1 and a["new"]["sec_med"] == 38


def test_1度も引いていなければ撃つ道を印字する():
    line = trend.analytics_line([])
    assert "1度も引いていません" in line and "studio.cli analytics" in line


def test_行は遅れとショートの割合を必ず出す():
    rows = _ledger([("n1", True, 145, 38, 42.09, 0), ("o1", False, 350, 15, 53.56, 0)])
    line = trend.analytics_line(rows, now=dt.datetime(2026, 9, 10, 17, 0, tzinfo=JST))
    assert "遅れ 3日" in line
    assert "きょう公開した本には答えません" in line
    assert "ショートのフィード 92.6%" in line
    assert "中央 38秒" in line and "中央 15秒" in line


def test_trend_の毎周の行に入っている():
    """**印字する口が付いているか**（`zero_probe` が 05:3x → 05:4x で踏んだ族）。"""
    import inspect
    src = inspect.getsource(trend.lines)
    assert "analytics_line(" in src


# ---------------------------------------------------------------- 維持率カーブ

def test_カーブは刻が1つでも欠けたら空を返す():
    """**穴を 0 で埋めない**（埋めると「そこで全員 落ちた」に化ける）。"""
    full = {round(i / 100, 2): 1.0 - i / 200 for i in range(1, 101)}
    assert analytics.curve_marks(full) is not None
    holed = dict(full)
    del holed[0.50]
    assert analytics.curve_marks(holed) is None
    assert analytics.curve_marks({}) is None


def test_カーブの刻は5つ():
    full = {round(i / 100, 2): 0.5 for i in range(1, 101)}
    assert list(analytics.curve_marks(full)) == ["p10", "p25", "p50", "p75", "p95"]


def test_カーブは割合と率だけを返す(monkeypatch):
    monkeypatch.setattr(analytics, "_query", lambda **kw: {
        "columnHeaders": [{"name": "elapsedVideoTimeRatio"}, {"name": "audienceWatchRatio"}],
        "rows": [[0.1, 1.0608], [0.25, 0.66]]})
    assert analytics.curve("v", "2026-08-20", "2026-09-07") == {0.1: 1.0608, 0.25: 0.66}


def _curve_rows(items) -> list[dict]:
    out = []
    for vid, studio, p10, p95 in items:
        out.append({"event": "analytics_curve", "id": vid, "studio": studio, "views": 200,
                    "marks": {"p10": p10, "p25": 0.6, "p50": 0.4, "p75": 0.3, "p95": p95},
                    "at": _at("2026-09-10 16:40")})
    return out


def test_カーブの行は新旧を10パーセントの刻で分ける():
    rows = _curve_rows([("n1", True, 0.71, 0.21), ("n2", True, 0.81, 0.21),
                        ("o1", False, 1.06, 0.14), ("o2", False, 1.21, 0.29)])
    line = trend.curve_line(rows)
    assert "新しい作り 2本 **10% で 0.71〜0.81**" in line
    assert "旧作り 2本 **10% で 1.06〜1.21**" in line
    assert "判定は `hourly`" in line


def test_空のカーブは名指しで数える():
    """**空を「カーブが無い」と読ませない**（`analytics.curve` の覆る条件 (1)）。"""
    rows = _curve_rows([("n1", True, 0.71, 0.21)])
    rows.append({"event": "analytics_curve", "id": "n2", "studio": True, "views": 150,
                 "marks": None, "at": _at("2026-09-10 16:40")})
    assert "**空 1本**" in trend.curve_line(rows)
    assert trend.curve_state(rows)["empty"] == ["n2"]


def test_カーブが1本も無ければ行を出さない():
    assert trend.curve_line([]) == ""


def test_カーブの行も毎周の並びに入っている():
    import inspect
    assert "curve_line(" in inspect.getsource(trend.lines)


def test_エラーで返った本は空とは別に数える():
    """**1本 の 500 で残りを落とさない・`error` を残す**（`analytics.curve` の覆る条件 (2)）。"""
    import inspect
    src = inspect.getsource(cli.cmd_analytics)
    assert "except Exception" in src and 'error=str(e)' in src
    rows = _curve_rows([("n1", True, 0.71, 0.21)])
    rows.append({"event": "analytics_curve", "id": "n2", "studio": True, "views": 150,
                 "marks": None, "error": "HttpError 500", "at": _at("2026-09-10 16:45")})
    assert trend.curve_state(rows)["empty"] == ["n2"]

# ---- 維持率カーブの 5xx は 1度だけ引き直す（2026-09-11 12:2x・optimizer・Opus）----
#
# 実測: 20時間 の門の後ろで `lQHX9LJ80Sg`（§7 (o-3) が待っている本）が 500 を返し、
# その本のカーブは **次の日まで引けない**ところでした（500 は 2度目 —— 1度目は `9zkfjEH48PY`）。


class _Resp(dict):
    def __init__(self, status):
        super().__init__(status=status, reason="test")
        self.status = status
        self.reason = "test"


def _http_error(status):
    from googleapiclient.errors import HttpError
    return HttpError(_Resp(status), b"{}")


def _patch_once(monkeypatch, seq):
    """`_curve_once` を並びで差し替える（例外なら投げ、辞書なら返す）。撃たれた回数を返す。"""
    calls = []

    def fake(vid, start, end):
        calls.append(vid)
        v = seq[len(calls) - 1]
        if isinstance(v, Exception):
            raise v
        return v

    monkeypatch.setattr(analytics, "_curve_once", fake)
    monkeypatch.setattr(analytics.time, "sleep", lambda *_: None)
    return calls


def test_500_は1度だけ引き直して通ること(monkeypatch):
    calls = _patch_once(monkeypatch, [_http_error(500), {0.1: 0.8}])
    assert analytics.curve("v", "2026-08-25", "2026-09-08") == {0.1: 0.8}
    assert len(calls) == 2                                   # 引き直しは 1度 だけ


def test_positive_control_400_は引き直さないこと(monkeypatch):
    """**陽性対照** —— 5xx だけを引き直す（400 は問いの側が違う ＝ 引き直しても同じ）。
    引き直しの条件を外すと、この検査は落ちます。"""
    calls = _patch_once(monkeypatch, [_http_error(400), {0.1: 0.8}])
    with pytest.raises(Exception):
        analytics.curve("v", "2026-08-25", "2026-09-08")
    assert len(calls) == 1


def test_2度とも500なら投げること(monkeypatch):
    """**回数は増やさない**（註の覆る条件 (3)）—— 2本 続けて出たら本の側を疑う側へ回す。"""
    calls = _patch_once(monkeypatch, [_http_error(500), _http_error(500)])
    with pytest.raises(Exception):
        analytics.curve("v", "2026-08-25", "2026-09-08")
    assert len(calls) == 2
