"""`scripts/reschedule.py --spread` の割り当て（API 0単位の純関数）。

**なぜこの検査が要るか**（2026-08-21）: 08/20 に Shorts を25本出したところ、
公開の早い10本は 185〜1,394 再生、**11本目から先は 0〜3** でした
（同じ経過11時間の時点。10本目と11本目は30分しか離れていません）。
1日に配られる量に天井があるので、**上限を超えたぶんは在庫を捨てている**のと
同じです。ここが壊れると、その捨てるほうへ黙って戻ります。
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))


def _mod():
    spec = importlib.util.spec_from_file_location(
        "reschedule_mod", ROOT / "scripts" / "reschedule.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _row(i: int, at_jst: datetime, *, short: bool = True) -> dict:
    return {"id": f"v{i:03d}", "topic": f"s-t{i}",
            "title": f"だい{i} " + ("#Shorts" if short else ""),
            "at": at_jst.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}


def _day(y=2026, m=9, d=1, h=9, mi=0):
    return datetime(y, m, d, h, tzinfo=JST) + timedelta(minutes=mi)


NOW = datetime(2026, 8, 31, 0, 0, tzinfo=JST).astimezone(timezone.utc)


def test_over_the_cap_moves_later_and_lands_under_the_cap():
    rows = [_row(i, _day(h=9, mi=30 * i)) for i in range(25)]   # 09/01 に25本
    mod = _mod()
    plan = mod.spread_plan(rows, now=NOW, per_day=10)
    assert len(plan) == 15, plan
    per_day = {}
    moved = {p["id"]: p["new"] for p in plan}
    for r in rows:
        at = moved.get(r["id"], r["at"])
        key = datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(JST).date()
        per_day[key] = per_day.get(key, 0) + 1
    assert max(per_day.values()) <= 10, per_day


def test_never_moves_earlier():
    """**不変条件**: 新しい時刻は必ず元より後。途中で止まっても続きになるため。"""
    rows = [_row(i, _day(h=9, mi=30 * i)) for i in range(25)]
    mod = _mod()
    for p in mod.spread_plan(rows, now=NOW, per_day=10):
        assert p["new"] > p["old"], p


def test_longform_is_not_counted_in_the_cap():
    """長尺は Shorts のフィードに出ないので、上限に数えません。

    テーマIDの `s-` 頭で見ると長尺を巻き込みます（控えの実物で10本）。
    """
    rows = ([_row(i, _day(h=9, mi=30 * i)) for i in range(10)]
            + [_row(90 + i, _day(h=15, mi=30 * i), short=False) for i in range(5)])
    mod = _mod()
    assert mod.spread_plan(rows, now=NOW, per_day=10) == []


def test_no_two_videos_share_a_slot():
    rows = ([_row(i, _day(h=9, mi=30 * i)) for i in range(25)]
            + [_row(50 + i, _day(d=2, h=9, mi=30 * i)) for i in range(3)])
    mod = _mod()
    plan = mod.spread_plan(rows, now=NOW, per_day=10)
    moved = {p["id"]: p["new"] for p in plan}
    seen = set()
    for r in rows:
        at = moved.get(r["id"], r["at"])
        when = datetime.fromisoformat(at.replace("Z", "+00:00")).astimezone(JST)
        assert when not in seen, when
        seen.add(when)


def test_under_the_cap_moves_nothing():
    rows = [_row(i, _day(h=9, mi=60 * i)) for i in range(8)]
    mod = _mod()
    assert mod.spread_plan(rows, now=NOW, per_day=10) == []


def test_default_per_day_is_the_measured_ten():
    mod = _mod()
    assert mod.DEFAULT_PER_DAY == 10


def test_置き先は生きる目盛りの中だけ_遅い時間へ送らない():
    """**あふれたぶんを 14:00 以降へ送らないこと**（2026-08-24 に直した）。

    この道具の docstring は「14:00 以降は15本中9本が0、残りも1〜3」と
    自分で測っています。それでも置き先は `9〜21時` の全部から
    **いちばん間の空いた目盛り**（＝遅いほう）を採っていたため、
    「その日の11本目だから0」を「19:30 だから0」に付け替えるだけでした。
    実測 08/24: 22本の割り当てのうち 09/20 21:00・09/22 19:30 など。

    生きるのは**その日の先頭から per_day 本ぶん**の目盛りです
    （per_day=10・hour=9・step=30 なら 09:00〜13:30）。
    """
    rows = [_row(i, _day(h=9, mi=30 * i)) for i in range(25)]   # 09/01 に25本
    mod = _mod()
    plan = mod.spread_plan(rows, now=NOW, per_day=10)
    assert plan
    edge = 9 * 60 + (10 - 1) * 30                              # 13:30
    for p in plan:
        when = datetime.fromisoformat(p["new"].replace("Z", "+00:00")).astimezone(JST)
        assert when.hour * 60 + when.minute <= edge, p


def test_窓は_per_day_から起こす_定数ではない():
    """`day_cap` の実測が上がれば、窓もいっしょに広がること。

    **ここを 13:30 の定数で書くと、上限が上がった日に窓だけ取り残されます。**
    """
    rows = [_row(i, _day(h=9, mi=30 * i)) for i in range(20)]
    mod = _mod()
    plan = mod.spread_plan(rows, now=NOW, per_day=14)           # → 窓は 15:30 まで
    assert plan
    late = [p for p in plan
            if datetime.fromisoformat(p["new"].replace("Z", "+00:00"))
            .astimezone(JST).hour >= 14]
    assert late, "per_day を上げても窓が 13:30 のままなら、定数で書かれています"
