"""**再生の付かない枠に居る本を、A/B の標本として数えていないか。**

2026-08-26 に見つけた壊れ方: `src/day_cap.py` が実測で「1日 10本」「30分より詰めた本は
死ぬ」と言っているのに、`src/judgeable.py` は公開日だけで群を数えていて、
**0再生と分かっている本も1本と数えていました**（実物で `opening_motion 対照` が
8本中5本、`stat_split 処置(後)` が 23本中10本）。

`falsified_if` は「上回らなければ外れ」なので、**足りない標本はそのまま「外れ」に化けます。**
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pytest

from src import day_cap

ROOT = Path(__file__).resolve().parent.parent

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
    """`SOURCES` は `members()` から畳むこと。**別の道で作ると2か所が割れます。**

    **`ACCRUING` の前提は `SOURCES` に入りません**（`src/judgeable.py` の註 ——
    これから積む群を入れると `Floor.ready` が `None` のまま赤で居座る）。
    ここは長らく `MEMBER_SOURCES` を全部 引いていて、`request_form` が
    `ACCRUING` に入った回に `KeyError` で落ちました。**畳み方の門であって、
    どの鍵が入るかの門ではありません** —— 除外の理由は向こうが持っています。
    """
    from src import judgeable

    for key in judgeable.MEMBER_SOURCES:
        if key in judgeable.ACCRUING:
            continue
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


# ---- 「空いた生きた枠」の数え方 ---------------------------------------------
#
# **私はこの数を、2026-08-26 の1周のうちに手で2回 数え間違えました**
# （1回目は「その日の**予約**の本数」で数え、2回目は**数える時点**を間違えた）。
# **どちらも、答えの向きが逆になる間違い**です:
#
#     予約の本数で数える  → 予約11本・上限10本 を「超過・余り0」と読む。
#                           実際は **15分きざみで詰めた本が死んでいる**ので、
#                           生きているのは7本、**まだ3本 入る**（実物の 09/02）
#     置く前に数える      → その3本は**このあとの群が置く先**だった。**実際は0本**
#
# **死ぬ理由は帯ではなく間隔です**（帯の外に居ても、その日が上限に届いて
# いなければ生きています —— `Board._alive_on` の註）。ここが縛るのは次の2つ。

def _live_board(rows, now="2026-09-02"):
    from scripts import live_slots
    return live_slots.Board(
        rows, now=dt.datetime.fromisoformat(now).replace(tzinfo=JST))


def test_空きは予約の本数ではなく生きている本の数で数える():
    """**15分きざみで詰めた本は死んでいるので、その日はまだ入ります。**

    実物（08/26 の 09/02）: 予約 11本・上限 10本 —— 予約の本数で数えると
    「超過・余り0」ですが、`09:00 / 09:15 / 09:30 …` と詰まっているので
    **生きているのは 7本**で、**空きは 3本**でした。
    """
    from scripts import live_slots
    # 15分きざみで8本 → 生きるのは 09:00 / 09:30 / 10:00 / 10:30 の **4本**
    rows = [_row(f"v{i}", "2026-09-02", f"{9 + i // 4:02d}:{(i % 4) * 15:02d}")
            for i in range(8)]
    board = _live_board(rows)
    assert board._alive_on(dt.date(2026, 9, 2)) == 4, "生きている本の数え方が違います"
    free = live_slots._free_live_before(board, dt.date(2026, 9, 2))
    assert free == day_cap.cap() - 4, (
        f"空きを {free}本 と数えました（正しくは {day_cap.cap() - 4}本）。"
        "**予約の本数（8本）で数えると 2本 になります** —— "
        "詰めて死んでいる本は、生きた枠を埋めていません")


def test_測定の窓の日は空きに数えない():
    """窓の日は置き先にしないので、**空きとして数えないこと。**"""
    from scripts import live_slots
    from src import measure_window
    board = _live_board([])
    lim = dt.date(2026, 9, 2)
    real = live_slots._free_live_before(board, lim)
    saved = measure_window.inside
    try:
        measure_window.inside = lambda d, w=None, today=None: True
        assert live_slots._free_live_before(board, lim) == 0, (
            f"窓の日を空きに数えています（窓でない日は {real}本）")
    finally:
        measure_window.inside = saved


def test_埋め方は_手を全部置いたあとに言う():
    """**ループの途中で数えると、あとの群が使う枠まで「空いている」と数えます。**

    実物（08/26）: 途中で数えたら「3本 空いています」と出ましたが、
    **その3本とも、次の群の置き先**でした。置き終えたあとは **0本** です。
    """
    src = (ROOT / "scripts" / "live_slots.py").read_text(encoding="utf-8")
    body = src[src.index("def plan(board: Board)"):src.index("def plan_all(")]
    assert "shortfalls.append(" in body, "不足を溜めていません"
    assert body.count("_how_to_fill(") == 1, (
        "`_how_to_fill` を手の途中でも呼んでいます。**置き終えてから1回だけ**")
    assert body.index("shortfalls.append(") < body.index("_how_to_fill("), (
        "溜める前に言っています")


# --- 交換の相手（**押し出してよい本**）--------------------------------------
#
# 上限に達している日には、**空いた生きた枠というものがありません。** その日に
# 生きるのはちょうど `cap()` 本で、どの時刻に置いても本数は変わらないので、
# **新しく足した本は必ず `cap()+1` 本目（0再生）**になります。
# だから「枠を空けてから入れる」は成立せず（空けた瞬間に別の本が繰り上がる）、
# **成立するのは `at` の交換だけ**です —— (日, 時刻) の集合は1つも変わらないので、
# 生きている本の総数も再生の総数も動かず、**実験の情報だけが増えます。**
#
# **相手に選んでよいのは「余り」だけ**です。どこかの群が床のぶんとして
# 使っている本を押し出すと、**別の前提を1件 遅らせます。**

def _fake_groups(monkeypatch, groups):
    from scripts import live_slots
    monkeypatch.setattr(live_slots, "_groups", lambda: groups)


def test_床のぶんとして使われている本は交換の相手にしない(monkeypatch):
    from scripts import live_slots
    rows = [_row(f"v{i}", "2026-09-02", f"{9 + i // 2:02d}:{(i % 2) * 30:02d}")
            for i in range(4)]
    board = _live_board(rows, now="2026-09-01")
    # 床 2本 の群が v0/v1 を使っている → 押し出してよいのは v2/v3 だけ
    _fake_groups(monkeypatch, {"k": ({"g": ["v0", "v1"]}, 2)})
    got = [v for v, _ in live_slots._swap_candidates(board, dt.date(2026, 9, 2), 4)]
    assert "v0" not in got and "v1" not in got, (
        "床のぶんの本を押し出そうとしています。**別の前提を1件 遅らせます**")
    assert got == ["v2", "v3"]


def test_床を上回っているぶんは交換の相手になる(monkeypatch):
    """`stat_split 対照(前)` は 床 16 に対して 316本 生きています。**余りです。**"""
    from scripts import live_slots
    rows = [_row(f"v{i}", "2026-09-02", f"{9 + i // 2:02d}:{(i % 2) * 30:02d}")
            for i in range(4)]
    board = _live_board(rows, now="2026-09-01")
    _fake_groups(monkeypatch, {"k": ({"g": ["v0", "v1", "v2", "v3"]}, 2)})
    got = [v for v, _ in live_slots._swap_candidates(board, dt.date(2026, 9, 2), 4)]
    # 早い順の先頭2本が床のぶん。残りは押し出してよい
    assert got == ["v2", "v3"]


def test_期限より後の本は交換の相手にしない(monkeypatch):
    from scripts import live_slots
    rows = [_row("v0", "2026-09-02", "09:00"), _row("v1", "2026-09-20", "09:00")]
    board = _live_board(rows, now="2026-09-01")
    _fake_groups(monkeypatch, {})
    got = [v for v, _ in live_slots._swap_candidates(board, dt.date(2026, 9, 2), 4)]
    assert got == ["v0"], "期限より後の枠と交換しても、その前提は判定できません"


def test_0再生の枠の本は交換の相手にしない(monkeypatch):
    """**押し出す意味がありません。**相手が生きていないと、枠は手に入りません。"""
    from scripts import live_slots
    # 15分きざみ → 09:15 は間隔で死ぬ
    rows = [_row("v0", "2026-09-02", "09:00"), _row("v1", "2026-09-02", "09:15")]
    board = _live_board(rows, now="2026-09-01")
    _fake_groups(monkeypatch, {})
    got = [v for v, _ in live_slots._swap_candidates(board, dt.date(2026, 9, 2), 4)]
    assert got == ["v0"]


def test_規則5では1手も出さない():
    """**先の日付へ本を置く手は、いま禁じられています**（2026-09-02・固定その4）。

    オーナー原文: 「**現在の日付にしか予約しないってことだからね？**」

    この道具が出すのは全部 `reschedule.py --move <id> <先の日付>` ＝
    **先の日付へ置く手**です。「0再生の枠から生きた枠へ逃がす」という理屈は
    それ自体 正しいのですが、**「先の日付に本が並んでいる」ことを前提**にしており、
    規則5 の下では**その前提のほうが欠陥**です（外す手は `pool_drain --keep 0`）。

    **すぐ上の `test_全部逃がす手は生きている本を増やす` は `if board.moves:` で
    守られているので、規則5 の下では空振りします。** この検査が無いと、
    「1手も出さない」が**検査されないまま**通ります。
    """
    from src import house_rule

    ls = pytest.importorskip("scripts.live_slots")
    if not house_rule.same_day_only():
        return                                  # 規則5 が外れている回は、上の一群が正
    board = ls.Board(ls._rows())
    for make in (ls.plan, ls.plan_all, ls.plan_band):
        out = make(board)
        body = "\n".join(out)
        assert "reschedule.py --move" not in body, (make.__name__, body)
        assert "pool_drain.py --apply --keep 0" in body, (make.__name__, body)
    assert board.moves == [], board.moves
