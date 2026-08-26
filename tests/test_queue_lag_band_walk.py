"""**枠を「平均」で割らないこと**（2026-08-27。実測で 11日 楽観でした）。

`scripts/queue_lag.band_lines()` は長らく
「帯の空き枠の**1日あたり平均** ÷ 足りない本数」で日数を出していました。
**置く側はそう置きません** —— `batch_build.live_plan()`（＝ `live_ring()` の中身）は
**手前の日から順に**埋めます。予約は先の日ほど疎なので、
平均は先の空いている日に持ち上げられ、**手前の詰まりを隠します**。

    平均で割ると   1日 5.7枠 → 128本 に 23日
    実際に置くと   128本目は +34日

そして同じ回に、**帯を広げる値打ちが (A)/(B) で符号ごと変わる**ことが出ました。
古い印字は「10 → 18枠/日 で **10日 早い**」と無条件に言っていましたが:

    (A) 1日 C本 まで    広げると +67日（**33日 遅い**）。上限のほうが先に当たり、
                        朝より前に置いてある本がその上限を食う
    (B) T までに出す    広げると +12日（**22日 早い**）

**14:00 の切り分けが決めているのはここです。** 片方だけ出すと、
次の回はその測定の値打ちを間違えます。
"""
from __future__ import annotations

import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build  # noqa: E402
import queue_lag as QL  # noqa: E402


def test_live_ring_は_live_plan_の写しである():
    """**置く側と数える側を、2本 別々に持たないこと。**

    `live_ring()` が時刻しか返さないので、日は `next_publish_at()` が
    探し直します。数える側（`queue_lag`）が別の式を持つと、
    **印字と実際が食い違います**（この輪は一度それで 11日 外しました）。
    """
    plan = batch_build.live_plan(6)
    ring = batch_build.live_ring(6)
    assert plan, "live_plan が空です（控えが読めていません）"
    assert ring == [t for t, _ in plan]


def test_置く日は前へ戻らない():
    plan = batch_build.live_plan(24)
    days = [d for _t, d in plan]
    assert days == sorted(days), days


def test_上限なしは_上限ありより後ろにならない():
    """`cap=None`（(B)）は縛りが1つ少ないので、遅くなりようがありません。"""
    grid = batch_build._band_grid()
    a = batch_build.live_plan(40, grid=grid, horizon=240)
    b = batch_build.live_plan(40, grid=grid, horizon=240, cap=None)
    assert a and b and len(a) == len(b) == 40
    assert b[-1][1] <= a[-1][1], (a[-1], b[-1])


def _need_and_lines(need: int = 60):
    rows = QL.scheduled()
    short = [("request_form", "途中あり", need)]
    return rows, QL.band_lines(rows, short)


def test_見出しの日数は_平均ではなく_置いた最後の1本():
    """**平均に戻したら、ここが落ちます。**"""
    need = 60
    rows, lines = _need_and_lines(need)
    assert lines, "band_lines が何も返していません"
    head = [ln for ln in lines if "最後の1本は" in ln]
    assert head, lines
    m = re.search(r"\+(\d+)日", head[0])
    assert m, head[0]
    plan = batch_build.live_plan(need, grid=batch_build._band_grid(), horizon=240)
    assert len(plan) == need
    want = (plan[-1][1] - datetime.now(QL.JST).date()).days
    assert int(m.group(1)) == want, (head[0], want)


def test_平均も残すが_使うなと書いてある():
    """平均を消さないこと —— 消すと、なぜ数が変わったのか次が追えません。"""
    _rows, lines = _need_and_lines()
    ref = [ln for ln in lines if "平均" in ln]
    assert ref, lines
    assert "判断に使わないこと" in "".join(ref)


def test_帯を広げる値打ちは_AとBを両方だす():
    """**片方だけ出さないこと。** 符号が逆になります。"""
    _rows, lines = _need_and_lines()
    body = "\n".join(lines)
    if "PROVEN_FROM_MIN" not in body:
        return                      # 帯が既に広げてある回（差が無い）
    assert "(A)" in body and "(B)" in body, body
    assert "(A) か (B) か" in body, body
