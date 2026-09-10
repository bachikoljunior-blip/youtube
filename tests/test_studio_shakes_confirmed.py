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

**決め（19:0x）**: 分子は `confirmed`（`still` かつ `after == "high"`）だけ。
`after` がまだ無い／`between` は**保留**で、`settle_stats` を動かす理由にならない。

**【2026-09-10 20:2x に、その分子をもう一度 移しました】** その `confirmed` が実物で 1行 出て、
**同じ行が「中央値へ移す」を否定しました** —— あとの点が高い側なら低い読みは捨ててよい側
（`max` が正解）・低い側で水準になれば それは数え直しで、包絡を落とすのは `recounts()` の仕事。
＝ **割れの決着は、どちらへ転んでも `settle_stats` を動かしません。**
動かす理由になるのは **`over_max`**（その本の確定した水準 ＝ `recounts()` の `to` より、
その行で `max` が書いた値のほうが高い）だけ。**実物 いま 0行。**

**陽性対照**（この検査の要）: `confirmed` の条件を `verdict == "still"` だけに戻すと
「保留」の行が分子に入り、下の 3件 が落ちます。`over_max` の側は
`test_陽性対照_数え直しが水準を落としたら_maxが高すぎた行になる` が落とします。
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
    assert "低い読みが一過性 0行" in line
    assert "`max` が高すぎた行 0行" in line
    assert "保留 1行" in line
    assert "これは「第3の口」ではありません" in line
    assert "`settle_stats` は動かさないこと" in line
    # **なぜ `recounts()` が挙げないかを、行が自分で言うこと**（次の回が手で引かないため）
    assert "1度目の数え直し" in line


def test_決着しても_settle_statsは動かさないと印字される():
    """**20:2x にここを裏返しました** —— 決着（高い側）は「`max` が正しかった」の札です。"""
    base = _base()
    rows = (_flat("C") + [_split("C", base, 287, 290)]
            + [_row("C", base + 0.7 * (i + 1), 290) for i in range(3)])
    line = trend.shakes_line(rows)
    assert "低い読みが一過性 1行" in line
    assert "保留 0行" in line
    assert "`max` が高すぎた行 0行" in line
    assert "`settle_stats` を動かす理由になりません" in line


def test_陽性対照_数え直しが水準を落としたら_maxが高すぎた行になる():
    """**新しい分子が、本当に別の物を見ているか**（§5 の教訓の形）。

    `max` が 290 と書いたあと、その本の水準が 6時間 以上 287 に留まって
    `recounts()` が 290 → 287 と落としたら、**290 は実物より高い値**でした ＝ 分子 1行。
    （上の `test_あとの点が低い側に落ちたら…` は 3点 しか続かないので `recounts()` は挙げません）
    """
    base = _base()
    rows = (_flat("C") + [_split("C", base, 287, 290)]
            + [_row("C", base + 0.7 * (i + 1), 287) for i in range(12)])
    assert [r["id"] for r in trend.recounts(rows)] == ["C"]
    s = trend.shakes(rows)[0]
    assert s["verdict"] == "recount"          # 2度目以降は `recounts()` が当てる
    assert s["over_max"] is True, "確定した水準より高い値を書いた行を、分子に数えていない"
    line = trend.shakes_line(rows)
    assert "`max` が高すぎた行 1行" in line
    assert "ここで初めて `settle_stats` の覆る条件" in line


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
