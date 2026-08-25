"""**入れ替えは、1日の本数も時刻の埋まり方も変えてはいけない。**

`scripts/queue_lag.py` は「判定に要る本を前へ、要らない本を後ろへ」を組みます。
**前へ詰めるのではなく、2本の公開時刻を交換します。** 理由は1つで、
1日に再生が付く本数に上限（実測 10本）があるからです ——
前詰めにすると、その日が上限を超えて**足したぶんが 0再生**になり、
「判定に要る本を早めたのに、その本には再生が付かない」という形になります。

だからここが見るのは、**交換が交換のままか**です:

    1日の本数        1つも変わらないこと
    時刻の埋まり方    集合として1つも変わらないこと（＝重なりを増やさない）
    測定の窓         置き先からも、動かす対象からも外れていること
    判定に要る本     後ろへ送る側に選ばれていないこと

そして **1手で `ready` が縮まなくても止まらないこと**（2026-08-26 の最初の版が
ここで落ちました。`opening_motion` の対照は 8本ちょうどで N も 8 なので、
**4本を全部前へ出すまで 1日も縮まず**、1手ごとに縮むことを条件にすると
その群だけ永久に動きませんでした）。
"""
from __future__ import annotations

import collections
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import queue_lag as Q  # noqa: E402
from src import judgeable, measure_window  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 8, 26, 1, 0, tzinfo=JST)


def _slot(day: int, hour: int) -> datetime:
    return datetime(2026, 8, day, hour, 0, tzinfo=JST)


def _fake(monkeypatch, *, n: int, members: dict[str, list[tuple[date, str]]],
          extra: list[tuple[str, datetime]], window: set[str] | None = None):
    """群 1件ぶんの世界を作る。`extra` は「どの群にも要らない本」。"""
    at: dict[str, datetime] = {}
    for g in members.values():
        for d, v in g:
            at[v] = datetime(d.year, d.month, d.day, 9, 0, tzinfo=JST)
    for v, t in extra:
        at[v] = t
    rows = [{"video_id": v, "at": t, "topic": v, "publish": t.date()}
            for v, t in sorted(at.items(), key=lambda kv: kv[1])]

    floor = judgeable.Floor(
        key="t", deadline=date(2026, 9, 30),
        groups={g: sorted(d for d, _ in ms) for g, ms in members.items()},
        min_per_group=n)
    monkeypatch.setattr(Q, "scheduled", lambda now=None: rows)
    monkeypatch.setattr(judgeable, "floors", lambda: [floor])
    monkeypatch.setattr(judgeable, "members", lambda key: members)
    blocked = window or set()
    monkeypatch.setattr(measure_window, "inside",
                        lambda d, w=None, today=None: d in blocked)
    return rows


def _plan(monkeypatch, **kw) -> tuple[Q.Plan, dict[str, datetime]]:
    rows = _fake(monkeypatch, **kw)
    before = {str(r["video_id"]): r["at"] for r in rows}
    p = Q.Plan(now=NOW)
    p.improve(50)
    return p, before


# 群がちょうど N本（＝1手では ready が縮まない形）
CHOUDO = {
    "対照": [(date(2026, 8, 27), "c1"), (date(2026, 8, 27), "c2"),
             (date(2026, 9, 6), "c3"), (date(2026, 9, 6), "c4")],
    "処置": [(date(2026, 8, 27), "t1"), (date(2026, 8, 27), "t2"),
             (date(2026, 8, 28), "t3"), (date(2026, 8, 28), "t4")],
}
YOSOMONO = [(f"x{i}", _slot(28, 10 + i)) for i in range(6)]


def test_群がちょうどN本でも前へ出る(monkeypatch):
    p, before = _plan(monkeypatch, n=4, members=CHOUDO, extra=YOSOMONO)
    assert p.swaps, "**1手も組めていません。**ちょうど N本 の群が動きません"
    a = p.readies()["t"]
    b = p.before["t"]
    assert a is not None and b is not None and a < b, (
        f"判定日が縮んでいません（{b} → {a}）")


def test_1日の本数と時刻の埋まり方が1つも変わらない(monkeypatch):
    p, before = _plan(monkeypatch, n=4, members=CHOUDO, extra=YOSOMONO)
    assert (collections.Counter(t.date() for t in before.values())
            == collections.Counter(t.date() for t in p.at.values())), \
        "**1日の本数が変わりました。**交換ではなく前詰めになっています"
    assert (collections.Counter(before.values())
            == collections.Counter(p.at.values())), \
        "**時刻の集合が変わりました。**重なりが増えている可能性があります"


def test_測定の窓は_置き先からも対象からも外れる(monkeypatch):
    p, before = _plan(monkeypatch, n=4, members=CHOUDO, extra=YOSOMONO,
                      window={"2026-08-28"})
    moved = [v for v in before if before[v] != p.at[v]]
    bad = [v for v in moved
           if before[v].date().isoformat() == "2026-08-28"
           or p.at[v].date().isoformat() == "2026-08-28"]
    assert not bad, f"窓の日を動かしました: {bad}"


def test_判定に要る本は後ろへ送らない(monkeypatch):
    p, before = _plan(monkeypatch, n=4, members=CHOUDO, extra=YOSOMONO)
    need = {v for ms in CHOUDO.values() for _, v in ms}
    okuretа = [v for v in need if p.at[v] > before[v]]
    assert not okuretа, f"判定に要る本を後ろへ送りました: {okuretа}"


def test_送る先が無ければ何もしない(monkeypatch):
    """よそ者が1本も無い ＝ 交換の相手がいない。**黙って壊さないこと。**"""
    p, before = _plan(monkeypatch, n=4, members=CHOUDO, extra=[])
    assert p.at == before
    assert not p.swaps


def test_合計は必ず減る(monkeypatch):
    p, before = _plan(monkeypatch, n=4, members=CHOUDO, extra=YOSOMONO)
    now = p.potential()
    for a, b in reversed(p.swaps):      # 全部もとに戻すと、合計は増えるはず
        p.at[a], p.at[b] = p.at[b], p.at[a]
    assert p.potential() > now, "合計（`potential`）が減っていません"


def test_群の作り方を_この道具の中で持ち直していない():
    """振り分けは `src/judgeable.py` の1か所。**写すと片方だけが直ります。**"""
    src = (ROOT / "scripts" / "queue_lag.py").read_text(encoding="utf-8")
    assert "judgeable.members(" in src
    for banned in ("EXPERIMENTS[", "motion_groups", "build_times("):
        assert banned not in src, (
            f"`{banned}` を `queue_lag.py` が直接見ています。"
            "群の作り方は `judgeable` に1か所だけ置くこと")


@pytest.mark.skipif(not (ROOT / "data" / "uploaded.jsonl").exists(),
                    reason="控えが無い")
def test_実物でも交換のままである():
    """実物の控えで組んでも、1日の本数と時刻の集合が変わらないこと。"""
    p = Q.Plan()
    before = dict(p.at)
    p.improve(60)
    assert (collections.Counter(t.date() for t in before.values())
            == collections.Counter(t.date() for t in p.at.values()))
    assert (collections.Counter(before.values())
            == collections.Counter(p.at.values()))
    moved = [v for v in before if before[v] != p.at[v]]
    for v in moved:
        for d in (before[v], p.at[v]):
            assert not measure_window.inside(d.date().isoformat()), \
                f"測定の窓（{d:%m/%d}）の本を動かしています: {v}"
