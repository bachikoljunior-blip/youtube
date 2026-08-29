"""**「判定できるのは 10-07」の日が、予約の並びで決まっているなら、そう言うこと。**

2026-08-29 の実測 —— 同じ日に、2つの道具が同じ前提について別々の日を言っていた:

    deadline_check  [OK] 10-08  opening_motion 対照(動きなし) 予約10本/**8本目 09/30**
                    → 判定できるのは **10-07**。**期限はその帯の中。書き換えないこと**
    queue_lag       opening_motion 判定 10/07 → **09/07** → **30日 早まる**
                    （**新しい本は1本も要らない。**もう予約に在る本の入れ替えだけ）

対照は**ちょうど10本**で `min_per_group` は 8 ＝ **8本目は後ろから3本目**。
後ろの6本を手前の空き枠へ入れ替えれば 8本目は 09/30 → 08/31 に来ます。

**`[OK]` と「書き換えないこと」しか読まなかった回は、そこで手を止めます** ——
自分で作った 30日 の待ちの前で。だから `deadline_check` の側から言わせます。
"""
from __future__ import annotations

from datetime import date

import pytest

from scripts import deadline_check


@pytest.fixture(autouse=True)
def _clear_cache(monkeypatch):
    monkeypatch.setattr(deadline_check, "_QUEUE_GAIN", None)


def test_gain_is_reported_on_the_group_line(monkeypatch) -> None:
    monkeypatch.setattr(
        deadline_check, "_QUEUE_GAIN",
        {"opening_motion": (date(2026, 10, 7), date(2026, 9, 7), 30)})
    ans = deadline_check.answer(
        {"kind": "group_key", "key": "opening_motion"}, date(2026, 8, 29), 3)
    assert "10/07 → 09/07（30日 手前）" in ans.why
    assert "予約の並びで決まっています" in ans.why
    # **期限そのものは動かしません** —— 言うのは「待ちは自分で作っている」だけ
    assert ans.ready == date(2026, 10, 7)


def test_no_gain_means_no_extra_line(monkeypatch) -> None:
    monkeypatch.setattr(deadline_check, "_QUEUE_GAIN", {})
    ans = deadline_check.answer(
        {"kind": "group_key", "key": "opening_motion"}, date(2026, 8, 29), 3)
    assert "予約の並びで決まっています" not in ans.why


def test_queue_gain_never_breaks_the_tool(monkeypatch) -> None:
    """**倒せるかどうかは、期限の正しさではありません。** 落ちても止めないこと。"""
    import scripts.queue_lag as QL

    def boom(*a, **k):
        raise RuntimeError("控えが読めません")

    monkeypatch.setattr(QL, "Plan", boom)
    assert deadline_check.queue_gain() == {}


def test_the_cache_solves_the_plan_once(monkeypatch) -> None:
    """`_ans_group_key` は要件ごとに呼ばれます。**`Plan()` は1回だけ**。"""
    calls = []

    class _Plan:
        before = {"k": date(2026, 10, 7)}

        def __init__(self, *a, **k):
            calls.append(1)

        def improve(self, *a, **k):
            return None

        def readies(self):
            return {"k": date(2026, 9, 7)}

    import scripts.queue_lag as QL
    monkeypatch.setattr(QL, "Plan", _Plan)
    assert deadline_check.queue_gain()["k"][2] == 30
    assert deadline_check.queue_gain()["k"][2] == 30
    assert len(calls) == 1
