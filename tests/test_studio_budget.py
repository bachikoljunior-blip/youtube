"""`studio/budget.py` —— きょうの日枠を台帳から数える（**API 0単位**）。

**陽性対照 2つ**: 枠の頭をまたぐ行を外していること・`RESERVE` を動かすと「あと何本」が変わること。
"""
import datetime as dt

from studio import budget
from studio.common import JST


def _t(s):
    return dt.datetime.fromisoformat(s).replace(tzinfo=JST)


def test_枠の頭は直近の16時():
    assert budget.window_start(_t("2026-09-16T03:34:00")) == _t("2026-09-15T16:00:00")
    assert budget.window_start(_t("2026-09-16T16:00:00")) == _t("2026-09-16T16:00:00")
    assert budget.window_start(_t("2026-09-16T15:59:00")) == _t("2026-09-15T16:00:00")


def test_予約1本は1650単位():
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "scheduled"}]
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["total"] == budget.UPLOAD_UNITS


def test_枠の頭より前の行は数えない():
    """**陽性対照 1**: 同じ行でも、刻が枠の外なら 0。"""
    rows = [{"at": "2026-09-15T15:59:00+09:00", "event": "scheduled"}]
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["total"] == 0
    assert budget.spent(rows, _t("2026-09-15T15:59:30"))["total"] == budget.UPLOAD_UNITS


def test_行が持つunitsのほうを先に読む():
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "peers", "units": 28}]
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["total"] == 28


def test_知らないeventは0で数える():
    """覆る条件 (1) ＝ **この数は過小**。知らない口は 0 になる。"""
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "まだ知らない口"}]
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["total"] == 0


def test_残り本数は測る側の取り分を引いてから割る():
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "scheduled"} for _ in range(5)]
    s = budget.spent(rows, _t("2026-09-16T03:00:00"))
    assert s["total"] == 5 * budget.UPLOAD_UNITS          # 8,250
    assert s["left"] == budget.DAY_UNITS - s["total"]      # 1,750
    assert s["uploads_left"] == 0                          # (1,750 - 600) // 1,650 == 0


def test_取り分を0にすると1本ぶん増える(monkeypatch):
    """**陽性対照 2**: `RESERVE` を動かすと答えが変わる ＝ 取り分が効いている。"""
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "scheduled"} for _ in range(5)]
    monkeypatch.setattr(budget, "RESERVE", 0)
    assert budget.spent(rows, _t("2026-09-16T03:00:00"))["uploads_left"] == 1


def test_取り分を割ったら印字が名指しする():
    rows = [{"at": "2026-09-15T20:00:00+09:00", "event": "scheduled"} for _ in range(6)]
    out = "\n".join(budget.lines(rows, _t("2026-09-16T03:00:00")))
    assert "残りが測る側の取り分を割っています" in out
    assert "判定が止まります" in out


def test_印字は過小だと毎回言う():
    out = "\n".join(budget.lines([], _t("2026-09-16T03:00:00")))
    assert "0単位" in out and "過小" in out
