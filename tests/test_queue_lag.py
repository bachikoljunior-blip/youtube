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


# ---------------- 待ち時間そのもの（2026-08-26。**印字していた数が別物でした**）

JST9 = timezone(timedelta(hours=9))
NOW = datetime(2026, 8, 26, 4, 0, tzinfo=JST9)


def _row(vid: str, when: datetime) -> dict:
    return {"video_id": vid, "at": when}


def _at(day_offset: int, hour: int, minute: int = 0) -> datetime:
    d = NOW.date() + timedelta(days=day_offset)
    return datetime(d.year, d.month, d.day, hour, minute, tzinfo=JST9)


def _queue() -> list[dict]:
    """**手で作った予約。実物と同じ形** —— 後ろは遠いが、**手前がすかすか**。

    実測（2026-08-26）: 328本・いちばん後ろ 32日先。それでいて 09/25 は 1本、
    09/26 は 1本。`depth()` はこの「32日」を返し、`lag_lines()` はそれを
    「**いま作った本が公開されるのは 32日後**」と印字していました。
    **新しい本は、その 1本しか居ない日より手前の空きに入ります。**

    ここでは 1〜5日目を**上限（10本）以上・全部 13:30 より後**にしてあります。
    そうすると2つのモデルが割れます —— (A) は「その5日は満杯」、
    (B) は「13:30 より前は全部空いている」。
    """
    rows = []
    for d in range(1, 6):
        for i in range(12):                      # 上限10本を超える／全部 14:00 以降
            rows.append(_row(f"d{d}-{i}", _at(d, 14 + i // 2, 30 * (i % 2))))
    rows.append(_row("far", _at(30, 9)))         # ずっと先に1本 ＝ 「いちばん後ろ」
    rows.sort(key=lambda r: r["at"])
    return rows


def test_いま作った本の待ちは_いちばん後ろの日ではない(monkeypatch):
    """**`depth()` と `placement_days()` は別物。**

    ここが同じ数を返していたので、判定日も θ も「税は2回」も、
    全部いちばん後ろの日の上に乗っていました。

    **窓は切っておきます** —— 実物の `measure_window.WINDOWS` が動くたびに
    ここが赤くなると、**測ったこと（進歩）を検査が「壊れた」と言います**。
    窓そのものは下の専用の1件で縛っています。
    """
    monkeypatch.setattr(Q, "_in_window", lambda d: False)
    rows = _queue()
    assert Q.depth(rows, NOW) == 30                    # いちばん後ろ（変えていない）

    place = Q.placement_days(rows, NOW)
    assert place["min_days"] == 1, place               # 明日の 09:00 は空いている
    assert place["min_days"] < Q.depth(rows, NOW), \
        "**いちばん後ろの日を、新しい本の待ちとして返しています**"


def test_再生が付く日は本数で数える_同じ分の重なりで手前へずれないこと(monkeypatch):
    """**`{(時,分)}` の大きさで数えないこと**（2026-08-26 に踏んだ）。

    同じ分に2本ある日があります（`day_cap.ties()`: 08/27 は 5組10本）。
    集合で数えると**本数より小さく**出て、(A)「その日はまだ空いている」が
    **手前へずれます**。ここは 12本を6つの時刻へ2本ずつ置いた日で、
    集合なら 6（＜上限10 ＝ 空きあり）、本数なら 12（空き無し）です。
    """
    from src import day_cap

    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    monkeypatch.setattr(day_cap, "window",
                        lambda *a, **k: {"T": "13:30", "confounded": True,
                                         "verdict": None})
    monkeypatch.setattr(Q, "_in_window", lambda d: False)   # 実物の窓に左右されない
    rows = []
    for i in range(6):                       # 6つの時刻に2本ずつ ＝ 12本
        rows.append(_row(f"a{i}", _at(1, 14 + i)))
        rows.append(_row(f"b{i}", _at(1, 14 + i)))
    rows.append(_row("z", _at(2, 14)))       # 翌々日は1本 ＝ 本当の「空きのある最初の日」
    rows.sort(key=lambda r: r["at"])

    v = Q.views_days(rows, NOW)
    assert v["count_days"] == 2, \
        f"同じ分の重なりを 1本 と数えて、空きのある日が手前へずれました: {v}"


def test_2つのモデルが割れているあいだは両方印字する(monkeypatch):
    """**片方だけを印字しないこと。** それが θ そのもので、桁が変わります。"""
    from src import day_cap

    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    monkeypatch.setattr(day_cap, "window",
                        lambda *a, **k: {"T": "13:30", "confounded": True,
                                         "verdict": None})
    monkeypatch.setattr(Q, "_in_window", lambda d: False)   # 実物の窓に左右されない
    rows = _queue()
    v = Q.views_days(rows, NOW)
    assert v["count_days"] == 6 and v["window_days"] == 1, v   # 割れている

    out = "\n".join(Q.lag_lines(rows, NOW))
    assert "(A)" in out and "(B)" in out, out
    assert "まだ決まっていません" in out
    # **いちばん後ろの日を「公開されるのは N日後」と言わないこと**
    assert "いま作った本が公開されるのは 30日後" not in out


def test_測定の窓の日は_置ける日として数えない(monkeypatch):
    """**`next_publish_at()` は窓の日を飛ばします。ここも飛ばすこと。**

    2026-08-26 に踏んだ形 —— 明日（08/27）は `day_cap` の切り分けの窓でした。
    飛ばさないと「**明日 置けます**」と印字して、**実際には置けない日**を指します。
    """
    from src import day_cap

    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: 10)
    monkeypatch.setattr(day_cap, "window",
                        lambda *a, **k: {"T": "13:30", "confounded": True,
                                         "verdict": None})
    rows = [_row("far", _at(30, 9))]                  # 手前は全部 空

    # 窓が無ければ、明日（1日後）に置ける
    monkeypatch.setattr(Q, "_in_window", lambda d: False)
    assert Q.placement_days(rows, NOW)["min_days"] == 1
    assert Q.views_days(rows, NOW)["window_days"] == 1

    # 明日だけが窓なら、明後日へ下りる
    tomorrow = NOW.date() + timedelta(days=1)
    monkeypatch.setattr(Q, "_in_window", lambda d: d == tomorrow)
    assert Q.placement_days(rows, NOW)["min_days"] == 2, "**窓の日を置ける日と数えています**"
    assert Q.views_days(rows, NOW)["window_days"] == 2
    assert Q.views_days(rows, NOW)["count_days"] == 2
