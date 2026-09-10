"""`trend.shakes` の分子は札ではなく**決着**（2026-09-10 19:0x・optimizer・Opus）。

**なぜ**（実物で踏んだ）: 18:38 の `measure` で `CIPYV_r1Hdo` 齢 101.6h が **290 対 287** で割れた。
287 は台帳に 1度も無く（24周 続けて 290）、窓の先頭も 290 なので `_lag_evidence` は
「遅れでは説明が付かない」＝ `still`。`recounts()` はこの本を挙げていない。
**ところが `recounts()` は、挙げられません** —— あれは生が包絡を `ENVELOPE_LAG_H`（6時間）より
長く下回ったまま戻らなかった峰を拾うので、**数え直しが始まった瞬間の `hours_below` は 0**。
＝ **どの本の 1度目の数え直しも、その瞬間は必ず `still` に見えます**
（17:3x の join が当てられるのは、2度目以降 ＝ 1度目が 6時間 前に確定している本だけ）。

それでも `shakes_line` は「**第3の口が出ています ＝ 覆る条件 (3) が本当に引かれました**」と
言い切りながら、同じ文で「この回では言えない」と印字していました
（**言っている所と、している所が別**）。§7 (h) の「`still` が 1行 でも出たら `settle_stats` の側」に
従うと max → 中央値 へ移すことになり、`trend.shakes` の実測はそれが**悪くなる**と数で示しています
（141/141/142 の中央値は 141 ＝ 新しい値を捨てる・637 対 886 では -249回 へ戻る）。

**決め**: 分子は `confirmed`（`still` かつ `after == "high"`）だけ。
`after` がまだ無い／`between` は**保留**で、`settle_stats` を動かす理由にならない。

**陽性対照**（この検査の要）: `confirmed` の条件を `verdict == "still"` だけに戻すと
「保留」の行が分子に入り、下の 3件 が落ちます。
"""
from __future__ import annotations

import datetime as dt

from studio import trend

JST = dt.timezone(dt.timedelta(hours=9))
T0 = dt.datetime(2026, 9, 6, 13, 0, tzinfo=JST)


def _row(vid: str, age: float, views: int, **kw) -> dict:
    r = {"event": "measured", "id": vid, "age_h": round(age, 1), "views": views,
         "at": (T0 + dt.timedelta(hours=age)).isoformat()}
    r.update(kw)
    return r


def _flat(vid: str, n: int = 24, level: int = 290, start: float = 85.0) -> list[dict]:
    """実物 `CIPYV_r1Hdo` の形: 同じ値が長く続く（＝ `recounts()` はまだ挙げない）。"""
    return [_row(vid, start + 0.7 * i, level) for i in range(n)]


def _split(vid: str, age: float, low: int, high: int) -> dict:
    return _row(vid, age, high, views_min=low, n_values=2)


def _base(n: int = 24) -> float:
    return 85.0 + 0.7 * n


def test_割れた瞬間はまだ第3の口ではない():
    """実物の形（290 が 24周 → 290 対 287）。札は `still` でも、分子には入らない。"""
    rows = _flat("C") + [_split("C", _base(), 287, 290)]
    s = trend.shakes(rows)[0]
    assert s["verdict"] == "still"
    assert s["after"] is None
    assert s["confirmed"] is False


def test_あとの点が高い側へ戻って初めて分子に入る():
    base = _base()
    rows = (_flat("C") + [_split("C", base, 287, 290)]
            + [_row("C", base + 0.7 * (i + 1), 290) for i in range(3)])
    s = trend.shakes(rows)[0]
    assert s["after"] == "high"
    assert s["confirmed"] is True


def test_あとの点が低い側に落ちたら数え直しで分子に入らない():
    """1度目の数え直しの形 —— 札は `still` のままでも、決着は数え直しの側。"""
    base = _base()
    rows = (_flat("C") + [_split("C", base, 287, 290)]
            + [_row("C", base + 0.7 * (i + 1), 287) for i in range(3)])
    s = trend.shakes(rows)[0]
    assert s["verdict"] == "still"
    assert s["after"] == "low"
    assert s["confirmed"] is False


def test_あいだに落ちた点も保留のまま():
    base = _base()
    rows = (_flat("C") + [_split("C", base, 287, 290)]
            + [_row("C", base + 0.7 * (i + 1), 288) for i in range(3)])
    s = trend.shakes(rows)[0]
    assert s["after"] == "between"
    assert s["confirmed"] is False


def test_保留は保留と印字し_分子を動かさないこと():
    rows = _flat("C") + [_split("C", _base(), 287, 290)]
    line = trend.shakes_line(rows)
    assert "第3の口（決着） 0行" in line
    assert "保留 1行" in line
    assert "これは「第3の口」ではありません" in line
    assert "`settle_stats` は動かさないこと" in line
    # **なぜ `recounts()` が挙げないかを、行が自分で言うこと**（次の回が手で引かないため）
    assert "1度目の数え直し" in line


def test_決着した行だけが第3の口として印字される():
    base = _base()
    rows = (_flat("C") + [_split("C", base, 287, 290)]
            + [_row("C", base + 0.7 * (i + 1), 290) for i in range(3)])
    line = trend.shakes_line(rows)
    assert "第3の口（決着） 1行" in line
    assert "保留 0行" in line
    assert "settle_stats` の覆る条件" in line


def test_1度目の数え直しはrecountsに挙がりようがないこと():
    """陽性対照の土台 —— join だけでは分けられないことを、実測の形で押さえる。

    数え直しが始まった点では `hours_below` が 0 なので、`recounts()` は空。
    そのあと 6時間 以上 低い値が続いて、初めて挙がる。
    """
    base = _base()
    onset = _flat("C") + [_split("C", base, 287, 290)]
    assert trend.recounts(onset) == []
    later = onset + [_row("C", base + 0.7 * (i + 1), 287) for i in range(12)]
    assert [r["id"] for r in trend.recounts(later)] == ["C"]
