"""`trend.shakes` の **数え直しの本** の札と、あとの点での決着（2026-09-10 17:3x・optimizer・Opus）。

**なぜ**（実物で踏んだ）: `lywTMXD6WDM` 齢 103.4h が **213 対 214** で割れ、
窓（6時間）の先頭 214 より低いので `_lag_evidence` は「遅れでは説明が付かない」＝ `still`。
**ところが同じ本は `recounts()` が挙げている 5本 の 1つ**（216→214）で、
**この本の再生は実測で1度 下がっています** ＝「再生は減らない」を前提にした窓の門は当たらない。
`shakes` の覆る条件 (1) は「`recounts()` も挙げているかを**先に見ること**」と書いてあるだけで、
**その手は道具に入っておらず、次の回が手で見る形**でした。ここで道具に入れます。

**陽性対照**（この検査の要）: 同じ形の割れでも、`recounts()` が挙げていない本は `still` のまま。
＝ 札を分けているのは join そのもの。
"""
from __future__ import annotations

import datetime as dt

from studio import trend

JST = dt.timezone(dt.timedelta(hours=9))
T0 = dt.datetime(2026, 9, 7, 10, 0, tzinfo=JST)


def _row(vid: str, age: float, views: int, **kw) -> dict:
    r = {"event": "measured", "id": vid, "age_h": round(age, 1), "views": views,
         "at": (T0 + dt.timedelta(hours=age)).isoformat()}
    r.update(kw)
    return r


def _recounted_book(vid: str, n: int = 100) -> list[dict]:
    """実物 `lywTMXD6WDM` の形: 初点 216 → 214 が長く続く（＝ `recounts()` が挙げる本）。"""
    return [_row(vid, 30.6, 216)] + [_row(vid, 32.6 + 0.7 * i, 214) for i in range(n)]


def _flat_book(vid: str, n: int = 100) -> list[dict]:
    """同じ長さ・同じ水準だが、数え直しの峰を持たない本（＝ `recounts()` は挙げない）。"""
    return [_row(vid, 32.6 + 0.7 * i, 214) for i in range(n)]


def _split(vid: str, age: float, low: int, high: int) -> dict:
    return _row(vid, age, high, views_min=low, n_values=2)


def test_数え直しの本の割れは数え直しの札になる():
    rows = _recounted_book("A") + [_split("A", 32.6 + 0.7 * 100, 213, 214)]
    assert [r["id"] for r in trend.recounts(rows)] == ["A"]
    sh = [s for s in trend.shakes(rows) if s["id"] == "A"]
    assert len(sh) == 1
    assert sh[0]["verdict"] == "recount"
    assert sh[0]["recounted"] is True
    assert sh[0]["floor"] == 214 and sh[0]["low"] == 213


def test_陽性対照_数え直しを持たない本は第3の口のまま():
    """join を外した世界（＝ `recounts()` が挙げない本）では、同じ割れが `still`。"""
    rows = _flat_book("B") + [_split("B", 32.6 + 0.7 * 100, 213, 214)]
    assert trend.recounts(rows) == []
    sh = [s for s in trend.shakes(rows) if s["id"] == "B"]
    assert sh[0]["verdict"] == "still"
    assert sh[0]["recounted"] is False


def test_遅れの行は札が変わらない():
    """低い読みが窓で通った値なら、数え直しの本でも `lag`（門の向きを壊していないこと）。"""
    rows = _recounted_book("A") + [
        _row("A", 32.6 + 0.7 * 100, 215),
        _split("A", 32.6 + 0.7 * 101, 214, 215),
    ]
    sh = [s for s in trend.shakes(rows) if s["id"] == "A"]
    assert [s["verdict"] for s in sh] == ["lag"]


def test_あとの点が無ければ言えない():
    rows = _recounted_book("A") + [_split("A", 32.6 + 0.7 * 100, 213, 214)]
    assert trend.shakes(rows)[0]["after"] is None


def test_あとの点が低い側に落ち着けば数え直しで決着():
    base = 32.6 + 0.7 * 100
    rows = (_recounted_book("A") + [_split("A", base, 213, 214)]
            + [_row("A", base + 0.7 * (i + 1), 213) for i in range(3)])
    assert trend.shakes(rows)[0]["after"] == "low"


def test_あとの点が高い側に戻れば第3の口の側():
    base = 32.6 + 0.7 * 100
    rows = (_recounted_book("A") + [_split("A", base, 213, 214)]
            + [_row("A", base + 0.7 * (i + 1), 214) for i in range(3)])
    assert trend.shakes(rows)[0]["after"] == "high"


def test_1行で数え直しと第3の口を分けて印字する():
    rows = (_recounted_book("A") + [_split("A", 32.6 + 0.7 * 100, 213, 214)]
            + _flat_book("B") + [_split("B", 32.6 + 0.7 * 100, 213, 214)])
    line = trend.shakes_line(rows)
    assert "数え直しの本 1行" in line
    # **`still` はあとの点が付くまで「保留」**（2026-09-10 19:0x）。
    # 分子は 20:2x から `max` が高すぎた行だけ（`trend.shakes` の註）。
    assert "低い読みが一過性 0行" in line
    assert "掘り起こした行 0行" in line
    assert "保留 1行" in line
    # **どちらの本を名指ししているかが、行から読めること**（次の回が手で引かないため）
    assert "A 齢" in line and "B 齢" in line


def test_数え直しの本で割れても分子は0と印字する():
    """**数え直しが落とした先（214）より高い値を書いていなければ、分子は 0**（20:2x）。"""
    rows = _recounted_book("A") + [_split("A", 32.6 + 0.7 * 100, 213, 214)]
    line = trend.shakes_line(rows)
    assert "掘り起こした行 0行" in line
    assert "第3の口には数えません" in line
