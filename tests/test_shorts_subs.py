"""`scripts/shorts_subs.py` —— **「どちらとも言えない」と言えることを守る検査**。

この道具が答えるのは「ショートは登録者を連れてくるのか」で、いま手元にある
登録は**全部で18人**です。**そこから率の差を読み取ろうとすると必ず嘘になります。**

だからこの検査が守るのは、数字が出ることではなく次の3つです。

1. **分母が0のとき、0で割って0と言わないこと**（長尺は59再生しかありません）。
   `per_1000` / `rate_ci_per_1000` は **None** を返し、表示は「—」になる
2. **区間が重なったら「差がある」と言わないこと**（`overlap`）。
   17件と1件で「長尺のほうが62倍」と書けてしまうのが、この日6件出た
   「計器が測りたいものを測っていない」の同じ形です
3. **区間そのものが正しいこと**。Poisson の厳密区間は既知の値があるので、
   そこで留める（n=0 で上限 3.689、n=1 で [0.0253, 5.572]、n=17 で [9.90, 27.22]）
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("shorts_subs", ROOT / "scripts" / "shorts_subs.py")
ss = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ss)


def test_per_1000_returns_none_when_no_views():
    """**分母0を0%と言わない。** 長尺の分母はいま59再生しかありません。"""
    assert ss.per_1000(3, 0) is None
    assert ss.rate_ci_per_1000(3, 0) is None
    assert ss.per_1000(17, 62982) == 17 / 62982 * 1000


def test_poisson_ci_matches_known_values():
    lo, hi = ss.poisson_ci(0)
    assert lo == 0.0
    assert abs(hi - 3.6889) < 0.01

    lo, hi = ss.poisson_ci(1)
    assert abs(lo - 0.0253) < 0.005
    assert abs(hi - 5.5716) < 0.01

    lo, hi = ss.poisson_ci(17)
    assert abs(lo - 9.9036) < 0.02
    assert abs(hi - 27.2216) < 0.02


def test_overlap_refuses_to_call_a_winner_at_this_sample_size():
    """**実測そのもの**（2026-08-25）。ショート 17/62,982・長尺 1/59。

    点推定は 0.270 と 16.9 で **62倍** に見えますが、区間は重なります。
    **ここが「重ならない」に変わったら、それは分母が育ったということ**なので、
    そのときは結論を書き直してよい。
    """
    short = ss.rate_ci_per_1000(17, 62982)
    long = ss.rate_ci_per_1000(1, 59)
    assert short[1] < 1.0 < long[1]
    assert ss.overlap(short, long) is True


def test_overlap_is_true_when_one_side_is_missing():
    """**分母が無い側と比べたら、必ず「言えない」に倒す。**"""
    assert ss.overlap(None, (1.0, 2.0)) is True
    assert ss.overlap((1.0, 2.0), None) is True
    assert ss.overlap((0.1, 0.4), (0.5, 9.0)) is False


def test_views_for_subs():
    """あと981人を 0.270/千再生 で連れてくるのに要る再生数（≒363万）。"""
    need = ss.views_for_subs(981, 17 / 62982 * 1000)
    assert abs(need - 3_634_432) < 2_000
    assert ss.views_for_subs(981, None) is None
    assert ss.views_for_subs(981, 0) is None
