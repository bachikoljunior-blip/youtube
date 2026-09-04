# -*- coding: utf-8 -*-
"""**群が足りなくて日が出ない床を、規則の密度で日にする**（2026-09-04 19:3x に足した）。

## なぜこの検査が要るか（**実測で踏んだ形**）

同じ `src/judgeable.py` を読んでいる2つの道具が、同じ床（`stat_split`）に
**逆の指示**を出していました:

    scripts/queue_lag.py       「1本/日 なら最後の1本は 2026-09-14 →
                                公開の締切 2026-08-31 → **14日 越えます**」
    scripts/deadline_check.py  「**まだ数えはじめたところです。
                                この回は何もしないのが正解です**」

違いは1つだけ —— `Floor.ready` は**予約に在る本**しか見ないので、群が1つでも
足りないと `None` を返します。`None` は `Verdict.warming` ＝「待てば日が出る」に
化け、**`--extend` が `slips` に入れません。** その結果、構造的に届かない期限
（09-07。片群 6本／床 16本）がそのまま立ち、期限の日が来ると
`falsified_if` の「上回らなければ外れ（同点も外れ）」が
**見分けられなかっただけの実験を『外れ』で閉じます。**
その腕は `per_video` ＝ `scripts/eta.py` が「引けるのはこれだけ」と名指しする1本。

**この検査は、その2つが同じ数を出すことだけを見ます。**

**覆る条件**: 足りない群が埋まれば `ready_at_rule` は `None` を返し、`ready` が
引き継ぎます（この検査の1件目はそのとき「`None` である」を見ます）。
**床（`MIN_PER_GROUP`）を下げて緑にしないこと。**
"""
from __future__ import annotations

import math
from datetime import date, timedelta

from src import house_rule, judgeable
from src.ab_split import SETTLE_DAYS
from src.judgeable import ANALYTICS_LAG_DAYS, Floor


def _floor(short: int, *, deadline: date) -> Floor:
    """片群だけ `short` 本 足りない床を1つ作る（**実物は読みません**）。"""
    have = judgeable.MIN_PER_GROUP - short
    day = date(2026, 8, 1)
    return Floor(
        key="_test_",
        deadline=deadline,
        groups={
            "処置": [day] * judgeable.MIN_PER_GROUP,
            "対照": [day] * max(0, have),
        },
    )


def test_群がそろっている床は規則の日を出さない():
    """`ready` が出ている床では `ready_at_rule` は黙ること（**推定で実物を上書きしない**）。"""
    f = _floor(0, deadline=date(2026, 12, 1))
    assert f.ready is not None
    assert f.ready_at_rule is None


def test_足りない群は今日から規則の密度で日が出る():
    """足りぶん ÷ 1日N本 ＋ 落ち着き ＋ 遅れ。**`queue_lag` と同じ式**。"""
    f = _floor(10, deadline=date(2026, 9, 7))
    assert f.ready is None, "群が足りないので実物の日は出ません"
    got = f.ready_at_rule
    assert got is not None
    cap = max(1.0, float(house_rule.cap()))
    days = math.ceil(10 / cap)          # 割合は実物の帳面から来るので、上限側で見ます
    latest = (date.today() + timedelta(days=days)
              + timedelta(days=SETTLE_DAYS + ANALYTICS_LAG_DAYS))
    assert got <= latest, (got, latest)
    assert got > date.today(), got


def test_deadline_checkが規則の日をslipsに入れる():
    """**`--extend` が動かせる形になっていること**（`warming` に化けないこと）。

    ここが赤になったら、直すのは期限ではなく `deadline_check._ready_at_rule()` の
    配線です。**この検査を消して緑にしないこと。**
    """
    import scripts.deadline_check as dc   # noqa: PLC0415

    item = {
        "claim": "_test_",
        "key": "_test_",
        "deadline": "2026-09-07",
        "needs": [{"kind": "after", "on_date": "2026-09-07", "what": "_test_"}],
    }
    orig, orig_ans = dc._ready_at_rule, dc.answer
    try:
        dc._ready_at_rule = lambda key: date(2026, 9, 21) if key == "_test_" else None
        # **この `needs` からは日が出ない**（＝ 群がそろっていない床と同じ姿）。
        dc.answer = lambda n, as_of, lag: dc.Answer(None, "_test_: 群がそろいません")
        vs = dc.check([item], as_of=date(2026, 9, 4), lag=3)
        v = vs[0]
        assert v.ready == date(2026, 9, 21), v.ready
        assert v.ready_from_rule is True
        assert v.warming is False, "「まだ数えはじめたところ」に化けないこと"
        assert v.slips is True, "`--extend` が拾える側に入ること"
    finally:
        dc._ready_at_rule, dc.answer = orig, orig_ans


def test_実物のstat_splitで2つの道具が同じ日を出す():
    """**同じ数が2か所から出ていること**（片方だけ直る形をここで止めます）。

    実物の帳面を読みます。床が埋まって `ready_at_rule` が `None` になったら
    この検査は黙って通ります（**そのときは `ready` が正本**）。
    """
    for f in judgeable.floors():
        if f.ready_at_rule is None:
            continue
        assert f.ready is None, f"{f.key}: 実物の日が在るのに推定も出ています"
        assert sum(f.shortfall().values()) > 0, f.key
