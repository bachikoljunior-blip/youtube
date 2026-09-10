"""`trend.views_absent` —— `viewCount` の欄が無い読みを、台帳から周をまたいで数える。

§7 (j)（`yt.views_of` の覆る条件 (1)）は「いま 0件・7本 過ぎて 1度も立たなければ外してよい」と
書きながら、**その 0件 も 7本 も、どこも数えていませんでした**（2026-09-10 21:0x に足した口）。

**陽性対照**（撃って落とした）:
`views_absent` の門（`r.get("views_absent")`）を外して全部の `measured` を数えると
`test_立っていない回は0件` が落ち、`VIEWS_ABSENT_SINCE` の刻の門を外すと
`test_口が在ってからの本だけを門の分母にする` が落ち、`ours` の絞りを外すと
`test_旧作りの本は門の分母に入れない` が落ちる。
"""
import datetime as dt

from studio import trend

JST = dt.timezone(dt.timedelta(hours=9))
SINCE = dt.datetime.fromisoformat(trend.VIEWS_ABSENT_SINCE)


def _m(vid: str, at: dt.datetime, views: int = 0, absent: bool = False) -> dict:
    r = {"event": "measured", "id": vid, "age_h": 1.0, "views": views,
         "at": at.isoformat()}
    if absent:
        r["views_absent"] = True
    return r


def _sched(vid: str) -> dict:
    return {"event": "scheduled", "video_id": vid, "at": SINCE.isoformat()}


def test_立っていない回は0件():
    rows = [_sched("a"), _m("a", SINCE + dt.timedelta(hours=1), views=12)]
    a = trend.views_absent(rows)
    assert a["n"] == 0 and a["books"] == []
    assert "欄が無い読み: 0件" in trend.views_absent_line(rows)


def test_立った本は名指しして0回を数から外させる():
    rows = [_sched("a"),
            _m("a", SINCE + dt.timedelta(hours=1), absent=True),
            _m("a", SINCE + dt.timedelta(hours=2), absent=True)]
    a = trend.views_absent(rows)
    assert a["n"] == 2 and a["books"] == ["a"], "行ではなく本で数える欄も持つこと"
    line = trend.views_absent_line(rows)
    assert "2件・1本" in line and "a" in line
    assert "数から外すこと" in line


def test_口が在ってからの本だけを門の分母にする():
    """陽性対照: 刻の門を外すと `since_books` が 2 になる。"""
    rows = [_sched("old"), _sched("new"),
            _m("old", SINCE - dt.timedelta(hours=3), views=5),
            _m("new", SINCE + dt.timedelta(hours=3), views=5)]
    assert trend.views_absent(rows)["since_books"] == 1


def test_旧作りの本は門の分母に入れない():
    """陽性対照: `ours` の絞りを外すと `since_books` が 2 になる。"""
    rows = [_sched("mine"),
            _m("mine", SINCE + dt.timedelta(hours=1), views=5),
            _m("legacy", SINCE + dt.timedelta(hours=1), views=5)]
    assert trend.views_absent(rows)["since_books"] == 1


def test_同じ本が毎周立っても本の数は1本():
    rows = [_sched("a")] + [_m("a", SINCE + dt.timedelta(hours=h), absent=True)
                            for h in (1, 2, 3, 4)]
    a = trend.views_absent(rows)
    assert (a["n"], len(a["books"])) == (4, 1)
