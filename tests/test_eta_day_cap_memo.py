"""`eta.py` が `day_cap.cap()` を1回だけ読むこと。**差し替えは見落とさないこと。**

## なぜ要るか（2026-08-28 に測った。**軌跡の 38% がこの1行でした**）

`day_cap.cap()` は `measure()` → `by_day()` と降りて、**`data/views.jsonl` を
毎回まるごと読み直します**（実測 **59.1 ms/回**）。この呼び出しは
`analyse()` と `plan()` の**中**にあり、その2つは `trajectory()` のループが
`t` の日数ぶん回します::

    analyse           58.0 ms/回   ← **うち day_cap.cap() が 59.1 ms**（ほぼ全部）
    plan(sens=False)  93.6 ms/回   ← ここにも1回 入っている
    軌跡 base 1本     20.0秒 ＝ 約131回まわる（軌跡は1回の eta.py で7本）

つまり **1回の `eta.py` が 1,000回 前後、同じファイルを読み直して同じ数を出して**
いました。`eta.py` は `data/views.jsonl` に1行も書きません（積むのは
`data/eta.jsonl` だけ）ので、**走っているあいだ答えは変わりません。**

## この検査が守っているもの

1. **同じ走りの中では、`day_cap.cap()` を1回しか呼ばない**
2. **`day_cap.cap` が差し替えられたら、取り直す** ——
   `tests/_eta_pin.py` と `tests/test_eta_day_cap.py` は
   **同じ関数の中で 10 → 1,000 と差し替えて**天井が効いているかを見ます。
   `functools.lru_cache` で畳むと、2つ目が素通りして
   **「天井が効いていない」を検査が見逃します**（この節がその代わり）
3. **覚えるのは「どの関数から取ったか」で、`id()` ではない** ——
   `id()` は差し替えが GC された後に別の関数へ回るので、静かに誤答します。
   ここでは**関数そのものを持って**、`is` で見ます
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_day_cap_memo_mod",
                                               ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _fresh(monkeypatch):
    """畳んだ答えを捨てる（検査どうしが持ち越さないように）。"""
    monkeypatch.setattr(eta, "_DAY_CAP_MEMO", None, raising=False)


def test_reads_day_cap_once_per_run(monkeypatch):
    """1: 同じ走りの中では1回だけ読む。**ここが軌跡の 38% でした。**"""
    _fresh(monkeypatch)
    calls = []

    def counted(*a, **k):
        calls.append(1)
        return 10

    monkeypatch.setattr(eta.day_cap, "cap", counted)
    got = [eta._view_cap_per_day() for _ in range(200)]
    assert got == [10] * 200
    assert len(calls) == 1, (
        f"`day_cap.cap()` を {len(calls)}回 読んでいます。"
        "**1回の eta.py で 1,000回 前後 呼ばれる場所です**（実測 59.1 ms/回）")


def test_a_replaced_day_cap_is_not_missed(monkeypatch):
    """2: 差し替えたら取り直すこと。**`lru_cache` だとここが落ちます。**

    `tests/test_eta_day_cap.py` は同じ関数の中で 10 → 1,000 と差し替えて、
    天井が効いているかを見ます。畳んだまま返すと、**その検査が
    「天井が効いていない」を見逃します。**
    """
    _fresh(monkeypatch)
    monkeypatch.setattr(eta.day_cap, "cap", lambda *a, **k: 10)
    assert eta._view_cap_per_day() == 10
    monkeypatch.setattr(eta.day_cap, "cap", lambda *a, **k: 1_000)
    assert eta._view_cap_per_day() == 1_000, (
        "`day_cap.cap` の差し替えを見落としています —— "
        "**天井を外した検査が、外れていないほうの答えを読みます**")
    monkeypatch.setattr(eta.day_cap, "cap", lambda *a, **k: 10)
    assert eta._view_cap_per_day() == 10, "戻した側も見落としています"


def test_memo_holds_the_function_not_its_id(monkeypatch):
    """3: 覚えているのは**関数そのもの**（`id()` だと再利用で静かに誤答する）。"""
    _fresh(monkeypatch)
    fn = lambda *a, **k: 7                                     # noqa: E731
    monkeypatch.setattr(eta.day_cap, "cap", fn)
    eta._view_cap_per_day()
    memo = eta._DAY_CAP_MEMO
    assert memo is not None and memo[0] is fn, (
        "畳んだ組が関数そのものを持っていません。"
        "**`id()` で覚えると、差し替えが GC された後に同じ id が別の関数へ回ります**")
    assert memo[1] == 7


def test_analyse_and_plan_both_go_through_the_memo(monkeypatch):
    """`analyse()` と `plan()` の**両方**が畳んだ側を通ること（ループの中の2口）。"""
    _fresh(monkeypatch)
    calls = []
    monkeypatch.setattr(eta.day_cap, "cap", lambda *a, **k: (calls.append(1), 10)[1])

    m = dict(views_7d=7000, views_28d=28000, subs_gained_28d=28, subs_net=100,
             long_hours_365=0.1, views_per_video=100, median_views_per_video=100,
             videos_with_views_28d=20, long_per_video=2.0, long_median_per_video=2,
             long_videos_28d=5, long_views_28d=11, shorts_views_90d=1000,
             views_90d=90000, subs_gained_90d=90, views_all=100000)
    a = eta.analyse(dict(m), None)
    eta.plan(dict(m), a, sensitivity=False)
    assert len(calls) == 1, (
        f"`analyse()` と `plan()` を1回ずつ通しただけで {len(calls)}回 読んでいます")
