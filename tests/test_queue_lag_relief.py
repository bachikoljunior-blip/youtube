"""**「間に合いません」は、予約を動かせない場合の話でしかない**（2026-08-29・最適化の回）。

`scripts/queue_lag.supply_lines()` は長らく3つの断定を印字していました:

    **この群だけを最優先しても間に合いません**
    **材料を足しても、この床は期限内に埋まりません**
    この N日 は**下限**です —— 実際は1周ずつ置くので、**遅れこそすれ早まりません**

**3つとも偽**でした。どれも `live_plan()` が**いまの予約を固定して**歩いた
結果ですが、**動かす道具は同じファイルに在ります**（`--apply` の `--move`）。

実測 2026-08-29（`request_form`・要 95本・期限までに公開 09/29）:

    いまのまま                    最後の1本 **10/02**（3日 越え）
    死に枠を **13本** 後ろへ動かす  最後の1本 **09/29** ← **間に合う**
    死に枠を  60本                 09/20
    死に枠を 145本                 09/13

**死に枠** ＝ どの開いた前提の判定日も動かさない本（`answering()` の `ans` の外）。
判定日は「その群の N本目の公開日」で決まるので、N本目より後ろの本を動かしても
**開いている前提は1つも動きません** —— 動くのは、その本が抱えていた**枠**だけ。

この床は `request_form` ＝ 腕 `sub_rate` の**ただ1つ 走っている実験**なので、
偽の「間に合いません」は**律速の門（登録者1,000人）を誤って手放させます。**

## この検査が守っているもの

1. `live_plan()` の `taken=` の継ぎ目が生きていること（**反実仮想の唯一の入口**）
2. `dead_slots()` が `ans` の本を**返さない**こと（返したら、どけると判定が壊れる）
3. `relief()` が「どければ間に合う」回に**最小の本数**を返すこと
4. `relief()` が `None` を返すのは「**全部どけても間に合わない**」ときだけ
   （`0` と混ぜないこと ——`0` は呼ぶ側が既に外しています）

## 覆る条件

`answering()` の `ans` の作り方が「N本目まで」から変わったら、
**2 が安全でなくなります** —— そのときは `dead_slots()` も一緒に直すこと。
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build as BB  # noqa: E402
import queue_lag as QL  # noqa: E402

GRID = [(9, 0), (9, 30), (10, 0)]


def _rows(start: date, days: int, per_day: int) -> list[dict]:
    """`start` の翌日から `days` 日、毎日 `per_day` 本を帯の頭から埋める。"""
    out = []
    for i in range(1, days + 1):
        d = start + timedelta(days=i)
        for j in range(per_day):
            h, m = GRID[j]
            out.append({"video_id": f"v{i}-{j}", "topic": f"t{i}-{j}",
                        "at": datetime(d.year, d.month, d.day, h, m,
                                       tzinfo=QL.JST)})
    return out


def test_live_plan_は_taken_を差し替えて歩ける(monkeypatch):
    """**1: 反実仮想の唯一の継ぎ目。**

    ここが死ぬと `relief()` は「どけても1日も動きません」と答えます ——
    **この回に実際に踏んだ形**です。最初は `queue_lag.scheduled` のほうを
    差し替えましたが、あれは**呼ぶたびに新しい dict を作る**ので
    `id()` で本を落とすと1本も落ちず、**「145本 どけても 10/02 のまま」**
    という偽の答えが出ました（＝ この節ごと捨てるところでした）。
    """
    today = date(2026, 8, 29)
    monkeypatch.setattr(QL, "_in_window", lambda _d: False)
    monkeypatch.setattr(BB, "_band_grid", lambda: list(GRID))
    now = datetime(today.year, today.month, today.day, 5, 0, tzinfo=QL.JST)

    rows = _rows(today, 10, 2)                  # 3枠/日 のうち 2枠 が埋まっている
    taken = QL._taken(rows)
    full = BB.live_plan(6, now=now, grid=GRID, cap=None, taken=taken)
    assert len(full) == 6
    # 1日1枠 しか空いていないので、6本目は 6日後
    assert full[-1][1] == today + timedelta(days=6)

    # **同じ呼びで、予約の側だけを差し替える。**
    empty = BB.live_plan(6, now=now, grid=GRID, cap=None, taken={})
    assert empty[-1][1] < full[-1][1], "taken= が効いていません（継ぎ目が死んでいます）"

    # **渡した辞書を書き換えないこと**（呼ぶ側が使い回します）
    before = {d: set(s) for d, s in taken.items()}
    BB.live_plan(6, now=now, grid=GRID, cap=None, taken=taken)
    assert taken == before


def test_dead_slots_は_判定日を決めている本を返さない(monkeypatch):
    """**2: どけて安全なのは `ans` の外だけ。**

    `ans` は「その群の N本目までに入っている本」＝ **判定日そのもの**です。
    ここが混ざると、`relief()` の提案どおり動かした回が**判定を壊します。**
    """
    today = date(2026, 8, 29)
    rows = _rows(today, 3, 2)
    ids = {r["video_id"] for r in rows}
    monkeypatch.setattr(QL.day_cap, "live_ids", lambda _r: ids)
    monkeypatch.setattr(QL, "published", lambda: rows)

    now = datetime(today.year, today.month, today.day, 5, 0, tzinfo=QL.JST)
    ans = {"v1-0", "v2-1"}
    got = QL.dead_slots(rows, ans, today + timedelta(days=3), GRID, now=now)
    assert {r["video_id"] for r in got} & ans == set()
    assert len(got) == len(rows) - len(ans)
    # **早い順**（手前の枠から空けるほうが効きます）
    assert [r["at"] for r in got] == sorted(r["at"] for r in got)

    # 期限より後ろの本は候補に入りません（空けても手前は詰まったまま）
    near = QL.dead_slots(rows, set(), today + timedelta(days=1), GRID, now=now)
    assert {r["video_id"] for r in near} == {"v1-0", "v1-1"}


def test_どければ間に合う回は_最小の本数を返す(monkeypatch):
    """**3: 「間に合いません」を、数のある腕に変えること。**"""
    today = date(2026, 8, 29)
    monkeypatch.setattr(QL, "_in_window", lambda _d: False)
    now = datetime(today.year, today.month, today.day, 5, 0, tzinfo=QL.JST)
    monkeypatch.setattr(BB, "live_plan",
                        lambda *a, **k: _plan(*a, now=now, **k))

    rows = _rows(today, 12, 2)                  # 1日1枠 だけ空き
    cand = [r for r in rows if r["at"].astimezone(QL.JST).date()
            <= today + timedelta(days=6)]
    cand.sort(key=lambda r: r["at"])
    due = today + timedelta(days=4)

    # 4本 を 4日 以内に置きたい。空きは 1日1枠 なので、そのままなら 4日目 ＝ ぎりぎり
    got = QL.relief(BB, 6, due, cand, GRID, rows, cap=None)
    assert got is not None, "どければ間に合う回に None を返しています"
    n, last = got
    assert last <= due
    assert 0 < n <= len(cand)
    # **最小であること** —— 1本 少なくすると間に合わない
    fewer = QL.relief(BB, 6, due, cand[:n - 1], GRID, rows, cap=None)
    assert fewer is None


def test_全部どけても間に合わない回だけ_None(monkeypatch):
    """**4: `None` と `0` を混ぜないこと。**

    ここを緩めると、今度は「どければ必ず間に合う」に倒れます。
    """
    today = date(2026, 8, 29)
    monkeypatch.setattr(QL, "_in_window", lambda _d: False)
    now = datetime(today.year, today.month, today.day, 5, 0, tzinfo=QL.JST)
    monkeypatch.setattr(BB, "live_plan",
                        lambda *a, **k: _plan(*a, now=now, **k))

    rows = _rows(today, 12, 2)
    cand = sorted(rows, key=lambda r: r["at"])
    # 枠は 3/日 しか無いので、20本 を 2日 で置くのは**どけても**無理
    assert QL.relief(BB, 20, today + timedelta(days=2), cand, GRID, rows,
                     cap=None) is None
    # 候補が1本も無ければ、そもそも動かせない
    assert QL.relief(BB, 6, today + timedelta(days=4), [], GRID, rows,
                     cap=None) is None


def _plan(count, now=None, grid=None, horizon=90, cap="auto", taken=None):
    """`now` を固定した `live_plan`（テストの中で日付を動かさないため）。"""
    return _REAL(count, now=now, grid=grid, horizon=horizon, cap=cap, taken=taken)


_REAL = BB.live_plan
