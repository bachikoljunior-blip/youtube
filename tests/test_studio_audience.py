"""**相手（齢×性別）の口**（`analytics.audience`／`audience_summary`・`trend.audience_split`／`audience_line`）。

2026-09-19 10:4x・optimizer・Fable 5.1・ultracode。**規則A**（`studio` を import しているので live の印が機械で付く・§6）。

なぜ在るか: 09/19 まで「誰に配られているか」を引く口が 1つ も無く、天井（~1,000回）の読みが
相手違い(a)／反応の薄さ(b) のどちらか決められなかった（`analytics.audience` の註）。
**陽性対照は「壊したら落ちる」まで撃った**（下の 2つ）。
"""
from __future__ import annotations

import datetime as dt

from studio import analytics, trend

JST = dt.timezone(dt.timedelta(hours=9))

ROWS = [
    {"age": "age65-", "gender": "female", "pct": 37.3},
    {"age": "age65-", "gender": "male", "pct": 29.1},
    {"age": "age55-64", "gender": "male", "pct": 15.9},
    {"age": "age55-64", "gender": "female", "pct": 12.7},
    {"age": "age45-54", "gender": "male", "pct": 4.1},
    {"age": "age45-54", "gender": "female", "pct": 0.9},
]


# ---------------------------------------------------------------- analytics.py

def test_畳みは55歳以上と65歳以上と最大の1組():
    s = analytics.audience_summary(ROWS)
    assert s["measured"] is True
    assert s["p55"] == 95.0
    assert s["p65"] == 66.4
    assert s["top"] == {"age": "age65-", "gender": "female", "pct": 37.3}
    assert s["n"] == 6


def test_行が無ければ測っていない_0パーセントではない():
    s = analytics.audience_summary([])
    assert s == {"measured": False}


def test_陽性対照_若い層だけなら55歳以上は0():
    """壊したら落ちる側: 55歳以上 に若い札を数えていないこと。"""
    s = analytics.audience_summary([{"age": "age25-34", "gender": "male", "pct": 60.0},
                                    {"age": "age35-44", "gender": "female", "pct": 40.0}])
    assert s["p55"] == 0.0 and s["p65"] == 0.0


def test_audienceは返りの欄の名前から読む(monkeypatch):
    """`columnHeaders` の順が入れ替わっても壊れないこと（`_rows` の規則）。"""
    res = {"columnHeaders": [{"name": "gender"}, {"name": "ageGroup"}, {"name": "viewerPercentage"}],
           "rows": [["female", "age65-", 37.34], ["male", "age55-64", 15.9]]}
    seen = {}

    def fake(**kw):
        seen.update(kw)
        return res
    monkeypatch.setattr(analytics, "_query", fake)
    got = analytics.audience("2026-09-06", "2026-09-16", ids=["a", "b", "a"])
    assert got == [{"age": "age65-", "gender": "female", "pct": 37.3},
                   {"age": "age55-64", "gender": "male", "pct": 15.9}]
    assert seen["dimensions"] == "ageGroup,gender"
    assert seen["metrics"] == "viewerPercentage"
    assert seen["filters"] == "video==a,b"          # 重なりは 1つ に


# ---------------------------------------------------------------- trend.py

def _row(day: str, p55: float, p65: float) -> dict:
    return {"event": "analytics_audience", "id": day, "start": "2026-09-06", "p55": p55, "p65": p65,
            "top": {"age": "age65-", "gender": "female", "pct": 37.3},
            "at": f"{day}T10:00:00+09:00"}


def test_台帳に行が無ければ測っていない():
    s = trend.audience_split([{"event": "analytics_traffic", "id": "2026-09-16"}])
    assert s["measured"] is False
    line = trend.audience_line([])
    assert "測っていません" in line and "若いとも老いているとも" in line


def test_行はいちばん新しい引きを読む(monkeypatch):
    monkeypatch.setattr(trend, "now_jst", lambda: dt.datetime(2026, 9, 19, 10, 0, tzinfo=JST))
    rows = [_row("2026-09-10", 50.0, 20.0), _row("2026-09-16", 95.0, 66.4)]
    s = trend.audience_split(rows)
    assert s["measured"] is True and s["day"] == "2026-09-16" and s["p55"] == 95.0
    line = trend.audience_line(rows)
    assert "55歳以上 95.0%" in line and "65歳以上 66.4%" in line
    assert "相手違いではありません" in line


def test_陽性対照_80を切ったら相手違いの側へ倒す(monkeypatch):
    monkeypatch.setattr(trend, "now_jst", lambda: dt.datetime(2026, 9, 19, 10, 0, tzinfo=JST))
    line = trend.audience_line([_row("2026-09-16", 54.8, 30.3)])
    assert "80% を切っています" in line and "相手違いではありません" not in line


def test_古すぎる引きは読まない(monkeypatch):
    monkeypatch.setattr(trend, "now_jst", lambda: dt.datetime(2026, 9, 30, 10, 0, tzinfo=JST))
    line = trend.audience_line([_row("2026-09-16", 95.0, 66.4)])
    assert "古すぎて読めません" in line and "55歳以上 95.0%" not in line
