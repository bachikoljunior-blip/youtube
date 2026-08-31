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


@pytest.fixture(autouse=True)
def _machine_is_running(monkeypatch):
    """**この検査は「機械が動いているとき」の話をしています。**（2026-08-30 に足した）

    2026-08-30 から `AUTOMATION_PAUSED.md` が在り、`deadline_check._paused_supply()`
    が**群の足りない前提を「停止中は埋まりません」で打ち切ります**（`unreachable`）。
    `opening_motion` の対照は **あと2本** なので、まさにそれに当たります ——
    `why` は「**予約の並びで決まっています**」ではなく「**停止中は埋まりません**」に
    なり、この検査は赤くなりました。

    **`_paused_supply()` のほうが正しい振る舞い**です。ここが守っているのは
    **走っているときに `_QUEUE_GAIN` が群の行に出ること**（出ないと、
    自分で作った 30日 の待ちの前で回が手を止める）なので、世界を1つに固定します。
    `tests/test_deadline_check.py` の同名 fixture と同じ判断・同じ理由です。

    **これは 2026-08-30 の `00dd270d` から赤で、この回まで誰も直していません**
    （＝ 全体の走りを読んだ回が無かった）。**停止中の振る舞いは
    `tests/test_paused_supply.py` と `tests/test_paused_accrual.py` が別に見ています。**

    **覆る条件**: `AUTOMATION_PAUSED.md` が消えたら、この fixture は何もしなくなります
    （そのとき外してよい）。
    """
    import src.pause_guard as PG

    monkeypatch.setattr(PG, "is_paused", lambda: False)


@pytest.fixture
def _full_groups(monkeypatch):
    """**群を、実物ではなく合成で満たす。**（2026-08-30 に足した）

    ここが固定したいのは「**`_QUEUE_GAIN` が群の行に出る**」という規則だけです。
    ところが `_ans_group_key` は `src/judgeable.SOURCES` 越しに**予約の実物**を読むので、
    **対照群が床（8本）を割った日に、この検査は規則と関係なく赤くなります。**

    実測 2026-08-30: 対照(動きなし) は **6本**（床 8本）——
    `why` は「**群がそろわないので日が出ません**」になり、
    `_QUEUE_GAIN` の行はそもそも出る場所へ届きませんでした。

    **これはこのファイルが一度 踏んだ穴の、1段 上です。** 下の註が
    「`ready` の実物をべた書きしていて、予約が1本 動くだけで赤くなった」と
    書いていますが、**日付を外しても、群の本数のほうが実物のまま残っていました。**
    **規則を測る検査は、実物の在庫に依存させないこと。**

    **覆る条件**: `_ans_group_key` が `SOURCES` 以外から群を取るようになったら、
    ここも一緒に移すこと（`src/judgeable.SOURCES` の1か所に置く、という
    2026-08-25 の合流の約束が生きているあいだは、ここで足ります）。
    """
    from src import judgeable as SJ

    days = [date(2026, 9, 20 + i) for i in range(8)]            # 8本目 = 09/27
    monkeypatch.setitem(SJ.SOURCES, "opening_motion",
                        (lambda: {"処置": list(days), "対照": list(days)}, 8))


def test_gain_is_reported_on_the_group_line(monkeypatch, _full_groups) -> None:
    need = {"kind": "group_key", "key": "opening_motion"}
    # **比べる相手は、同じ日の「倒し方が無い」ほうです**（2026-08-29 に直した）。
    #     ここは長らく `assert ans.ready == date(2026, 10, 7)` と
    #     **その日の実物をべた書き**していました。`ready` は予約の並びから
    #     毎回 解き直される数なので、**予約が1本 動くだけで赤くなります** ——
    #     実際 08/29 18:29 の回が `opening_motion` の期限を 10-07 → 10-06 へ
    #     縮めた時点で、この行だけが落ちました（**直す先はこの検査**で、
    #     向こうの縮めは正しい）。
    #     **固定したいのは「`_QUEUE_GAIN` は `ready` を動かさない」という規則**で、
    #     その日の日付ではありません。だから同じ問いを2回 解いて突き合わせます。
    monkeypatch.setattr(deadline_check, "_QUEUE_GAIN", {})
    without = deadline_check.answer(need, date(2026, 8, 29), 3)

    monkeypatch.setattr(
        deadline_check, "_QUEUE_GAIN",
        {"opening_motion": (date(2026, 10, 7), date(2026, 9, 7), 30)})
    ans = deadline_check.answer(need, date(2026, 8, 29), 3)
    assert "10/07 → 09/07（30日 手前）" in ans.why
    assert "予約の並びで決まっています" in ans.why
    # **期限そのものは動かしません** —— 言うのは「待ちは自分で作っている」だけ
    assert ans.ready == without.ready


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


def test_the_summary_line_carries_it_too(monkeypatch) -> None:
    """**まとめの側にも出すこと。**

    群の行にだけ書いた版は、**まとめしか読まない回には届きません** ——
    `eta.py` が「`[!]` 18件 は、頭と尾だけ読む手順では1本も読まれない」と
    自分で印字しているのと同じ穴です。
    """
    monkeypatch.setattr(
        deadline_check, "_QUEUE_GAIN",
        {"opening_motion": (date(2026, 10, 7), date(2026, 9, 7), 30),
         "hook_form": (date(2026, 9, 9), date(2026, 9, 7), 2)})
    out = "\n".join(deadline_check.lines([], 3))
    assert "予約の並び替えだけで倒せる待ち: 2件・合計 32日" in out
    assert "最大 opening_motion の **30日**" in out
    # **「期限が遅すぎる」と混ぜないこと** —— あちらはデータが揃っている件
    assert "「期限が遅すぎる」とは別の話です" in out
