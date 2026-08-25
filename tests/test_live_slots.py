"""**再生の付かない枠に居る本を、A/B の標本として数えていないか。**

2026-08-26 に見つけた壊れ方: `src/day_cap.py` が実測で「1日 10本」「30分より詰めた本は
死ぬ」と言っているのに、`src/judgeable.py` は公開日だけで群を数えていて、
**0再生と分かっている本も1本と数えていました**（実物で `opening_motion 対照` が
8本中5本、`stat_split 処置(後)` が 23本中10本）。

`falsified_if` は「上回らなければ外れ」なので、**足りない標本はそのまま「外れ」に化けます。**
"""
from __future__ import annotations

import datetime as dt

import pytest

from src import day_cap

JST = dt.timezone(dt.timedelta(hours=9))


def _row(vid: str, day: str, hhmm: str) -> dict:
    h, m = (int(x) for x in hhmm.split(":"))
    return {"video_id": vid,
            "at": dt.datetime.fromisoformat(day).replace(hour=h, minute=m, tzinfo=JST)}


def test_上限を超えたぶんは生きている側に入らない():
    """1日に `cap()` 本より多く置いたら、**後ろのぶんは 0再生の側**。"""
    cap = day_cap.cap()
    rows = [_row(f"v{i}", "2026-09-10", f"{5 + i // 2:02d}:{'30' if i % 2 else '00'}")
            for i in range(cap + 4)]
    live = day_cap.live_ids(rows)
    assert len(live) == cap, f"上限 {cap} 本のはずが {len(live)} 本"
    assert {f"v{i}" for i in range(cap)} == live, "生きるのは**先頭から**のはず"


def test_30分より詰めた本は生きている側に入らない():
    """`MIN_GAP_MIN` 未満で並べた本は、**後ろが落ちる**（08/21 の :15/:45 が7本とも0）。"""
    rows = [_row("a", "2026-09-10", "05:00"),
            _row("b", "2026-09-10", "05:15"),   # a から15分 → 落ちる
            _row("c", "2026-09-10", "05:45")]   # a から45分 → 残る
    live = day_cap.live_ids(rows)
    assert "a" in live and "c" in live
    assert "b" not in live, "30分より詰めた本を生きている側に入れています"


def test_同じ分に2本あるとき_片方だけが生きる():
    """間隔0（同じ分）は `_spaced` の外側。**両方を数えないこと。**"""
    rows = [_row("a", "2026-09-10", "09:00"), _row("b", "2026-09-10", "09:00")]
    assert len(day_cap.live_ids(rows)) == 1


def test_日をまたいでも上限は日ごとに数える():
    cap = day_cap.cap()
    rows = ([_row(f"x{i}", "2026-09-10", f"{5 + i // 2:02d}:{'30' if i % 2 else '00'}")
             for i in range(cap)]
            + [_row(f"y{i}", "2026-09-11", f"{5 + i // 2:02d}:{'30' if i % 2 else '00'}")
               for i in range(cap)])
    assert len(day_cap.live_ids(rows)) == cap * 2


def test_judgeable_は0再生の本を標本に数えない(monkeypatch):
    """**この検査がこのファイルの本体です。**

    群の作り方（`MEMBER_SOURCES`）はそのままに、**死に枠の本を1本 混ぜて**、
    `members()` がそれを落とすことを見ます。落とさないと、`falsified_if` が
    「上回らなければ外れ」なので、その1本ぶんが外れ側に効きます。
    """
    from src import judgeable

    day = "2026-09-10"
    good = [_row(f"g{i}", day, f"{5 + i:02d}:00") for i in range(3)]
    dead = _row("dead1", day, "20:00")            # 帯の外・上限の後ろ

    def fake_make():
        return {"処置": [(r["at"].date(), r["video_id"]) for r in good + [dead]],
                "対照": [(r["at"].date(), r["video_id"]) for r in good]}

    monkeypatch.setitem(judgeable.MEMBER_SOURCES, "_t", (fake_make, 2))
    monkeypatch.setattr(judgeable, "_live_ids",
                        lambda: {r["video_id"] for r in good})
    got = judgeable.members("_t")
    assert "dead1" not in [v for _, v in got["処置"]], \
        "0再生と分かっている本を、A/B の標本に数えています"
    assert len(got["処置"]) == 3


def test_控えが読めない回は絞らない(monkeypatch):
    """**観測できないものを「無い」ことにしない。** 群が空になると期限が壊れます。"""
    from src import judgeable

    def fake_make():
        return {"処置": [(dt.date(2026, 9, 10), "a")], "対照": [(dt.date(2026, 9, 10), "b")]}

    monkeypatch.setitem(judgeable.MEMBER_SOURCES, "_t2", (fake_make, 1))
    monkeypatch.setattr(judgeable, "_live_ids", lambda: None)
    got = judgeable.members("_t2")
    assert [v for _, v in got["処置"]] == ["a"], "読めない回に群を空にしています"


def test_群の作り方は1か所():
    """`SOURCES` は `members()` から畳むこと。**別の道で作ると2か所が割れます。**"""
    from src import judgeable

    for key in judgeable.MEMBER_SOURCES:
        make, n = judgeable.SOURCES[key]
        folded = make()
        live = judgeable.members(key)
        assert {g: len(v) for g, v in folded.items()} == \
               {g: len(v) for g, v in live.items()}, \
            f"{key}: SOURCES と members が別の群を見ています"


def test_入れ替えで生きている本を減らさない():
    """**減らしたら本末転倒です。**

    増えるぶんには構いません（上限に余りのある日へ置けたぶん）。
    **2026-08-26 まで「増えてもいけない」と書いてありました。** その思い込みが
    `_slots()` の空きを `_in_band()`（帯の中の本数）で数えさせていて、
    **埋まっている日を空いていると読んで**いました ——
    同じ 24手 で **+4本** しか増えないところを、正しく数えて **+24本** に直しています。
    """
    ls = pytest.importorskip("scripts.live_slots")
    board = ls.Board(ls._rows())
    before = len(board.live())
    ls.plan(board)
    after = len(board.live())
    assert after >= before, \
        f"入れ替えで生きている本が {before} → {after} に**減りました**"


def test_全部逃がす手は生きている本を増やす():
    """`--all` は**上限に余りのある日**へ逃がすので、総数が増えるはずです。"""
    ls = pytest.importorskip("scripts.live_slots")
    board = ls.Board(ls._rows())
    before = len(board.live())
    lines = ls.plan_all(board)
    after = len(board.live())
    if board.moves:
        assert after > before, \
            ("0再生の枠から動かしたのに生きている本が増えていません"
             f"（{before} → {after}）。空きの数え方がずれています\n" + "\n".join(lines))


def test_入れ替えは測定の窓の日を動かさない():
    """窓の日を動かすと、`day_cap` の切り分けそのものが壊れます。"""
    from src import measure_window

    ls = pytest.importorskip("scripts.live_slots")
    board = ls.Board(ls._rows())
    before = dict(board.at)
    ls.plan(board)
    for vid, when in board.moves:
        assert not measure_window.inside(when.date().isoformat()), \
            f"{vid} を測定の窓の日へ置こうとしています"
        assert not measure_window.inside(before[vid].date().isoformat()), \
            f"{vid} は測定の窓の日の本です。動かせません"


def test_入れ替え先は生きる帯の中():
    from src import collisions

    ls = pytest.importorskip("scripts.live_slots")
    board = ls.Board(ls._rows())
    ls.plan(board)
    for vid, when in board.moves:
        m = when.hour * 60 + when.minute
        assert collisions.LIVE_FROM_MIN <= m <= collisions.LIVE_TO_MIN, \
            f"{vid} を帯の外（{when:%H:%M}）へ置こうとしています"
        assert m % collisions.STEP_MIN == 0, f"{vid} が30分きざみに乗っていません"


# --- `queue_lag` が判定を壊さないか（2026-08-26 に足した門）--------------------

def _fake_plan(before: dict, after: dict):
    class P:
        before_at = before
        at = after
        swaps = [("a", "b")]
    return P()


def test_queue_lag_は要る本数を割る入れ替えを撃たない(monkeypatch):
    """**「何日 早まるか」より「判定を壊さないか」のほうが強い門です。**

    日付だけを見て入れ替えると、「早い枠へ移した」つもりが
    「死んだ枠へ移した」になりえます。そのとき `ready` は早まるのに、
    **その群の生きた本が要る数を割ります。**
    """
    from scripts import queue_lag
    import scripts.live_slots as ls

    day = dt.datetime(2026, 9, 10, 5, 0, tzinfo=JST)
    before = {f"v{i}": day + dt.timedelta(minutes=30 * i) for i in range(3)}
    after = dict(before)
    after["v2"] = day + dt.timedelta(minutes=15)      # v1 から15分 → 落ちる

    monkeypatch.setattr(ls, "_groups",
                        lambda: {"k": ({"処置": ["v0", "v1", "v2"]}, 3)})
    lines, ok = queue_lag.live_cost_lines(_fake_plan(before, after))
    assert not ok, "要る本数を割る入れ替えを、通しています\n" + "\n".join(lines)
    assert any("割ります" in ln for ln in lines)


def test_queue_lag_は割らない入れ替えを止めない(monkeypatch):
    """**止めすぎないこと。** 余っている群が減るだけなら通します。"""
    from scripts import queue_lag
    import scripts.live_slots as ls

    day = dt.datetime(2026, 9, 10, 5, 0, tzinfo=JST)
    before = {f"v{i}": day + dt.timedelta(minutes=30 * i) for i in range(5)}
    after = dict(before)
    after["v4"] = day + dt.timedelta(minutes=15)

    monkeypatch.setattr(ls, "_groups",
                        lambda: {"k": ({"処置": [f"v{i}" for i in range(5)]}, 2)})
    _lines, ok = queue_lag.live_cost_lines(_fake_plan(before, after))
    assert ok, "余っている群が減っただけで止めています"
