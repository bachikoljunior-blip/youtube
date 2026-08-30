"""**門が閉じる速さを「件数 ÷ 経過」で作らないこと。**（2026-08-30・最適化の回）

## なぜ要るか（この回に撃って出た実測）

`AUTOMATION_PAUSED.md` が在るあいだ、到達日を動かせる腕は1本もありません
（`src/pause_guard` が生成・投稿を塞いでいます）。**動く床は「門が閉じる日」だけ**で、
主実行はそこを見て「門をやるか、腕へ戻るか」を決めます。

直す前の `rate_per_day` は `閉じた件数 ÷ 停止からの経過日数` でした。
門1・2 は**停止したその日**（2026-08-30）に閉じているので、3件目を同じ日に足すと:

    today       rate/日   残り日数   門が閉じる日
    2026-08-31     3.00       1.0   2026-09-01   ← **「残り3件は明日 閉じる」**
    2026-09-01     1.50       2.0   2026-09-03
    2026-09-02     1.00       3.0   2026-09-05   ← **1日 経つと2日 遠のく**

**その2つが、この検査が二度と起こさせないものです。**

1. 主実行が「門は ほぼ ただ」と読んで、**塞がっている腕へ戻る**（＝その回は何も動かない）
2. 閉じる日が **1日 経つごとに2日 遠のき、永久に来ない**

## 覆る条件

種別ごとに閉じる速さの実績が貯まったら、**同じ難しさだと置く**のをやめて
種別で分けること。そのときはこの検査の「一括で1つの速さ」という前提ごと書き直す。
"""
from __future__ import annotations

import json
from datetime import date, timedelta

import pytest

from src import resume_gate

# 6件の門を持つ、最小の `AUTOMATION_PAUSED.md`。**本文は正本を写さないこと**
# （`src/resume_gate` の「覆る条件」3）。ここは形だけが要ります。
_PAUSE_TEXT = """# AUTOMATION PAUSED — 2026-08-30

## Resume gate

1. 条件いち
2. 条件に
3. 条件さん
4. 条件よん
5. 条件ご
6. 条件ろく

## Override
"""


def _ledger(tmp_path, closes):
    """`closes` は `(番号, "YYYY-MM-DD")` の並び。"""
    p = tmp_path / "gate.jsonl"
    p.write_text("".join(
        json.dumps({"at": f"{d}T10:00:00+09:00", "n": n,
                    "state": "closed", "evidence": "x"}, ensure_ascii=False) + "\n"
        for n, d in closes), encoding="utf-8")
    return p


def test_same_day_closes_do_not_become_a_rate(tmp_path):
    """**同じ日に3件 閉じても、翌日「残り3件は明日」とは言わないこと。**"""
    led = _ledger(tmp_path, [(1, "2026-08-30"), (2, "2026-08-30"), (3, "2026-08-30")])

    # 閉じたその日は、まだ何も測れていない（間隔が 0日）
    assert resume_gate.days_per_close(_PAUSE_TEXT, led, date(2026, 8, 30)) is None
    assert resume_gate.days_to_close(_PAUSE_TEXT, led, date(2026, 8, 30)) is None

    # 翌日。**直す前はここが 1.0日**（残り3件が明日 閉じる）でした。
    assert resume_gate.days_to_close(_PAUSE_TEXT, led, date(2026, 8, 31)) == pytest.approx(3.0)


def test_no_news_never_improves_the_estimate(tmp_path):
    """**1件も閉じないまま日が経ったら、残り日数は縮まないこと。**

    **遠のくこと自体は正しい**（閉じないまま待った日数は、次の1件の下限です）。
    直す前の壊れ方は遠のき方ではなく、**出発点**でした ——
    同じ日にまとめて閉じた分を速さに繰り入れて、翌日に「残り全部が あと1日」
    から始めていました。ここが縛るのは、**縮まないこと**と**下限**の2つです。
    """
    led = _ledger(tmp_path, [(1, "2026-08-30"), (2, "2026-08-30"), (3, "2026-08-30")])
    prev = None
    for d in range(1, 21):
        day = date(2026, 8, 30) + timedelta(days=d)
        left = resume_gate.days_to_close(_PAUSE_TEXT, led, day)
        assert left is not None
        # **すでに待った日数を、残り日数が下回らないこと**
        assert left >= d, f"{day}: 待った {d}日 より短い {left}日 を返した"
        if prev is not None:
            assert left >= prev, f"{day}: 1件も閉じていないのに {prev}→{left} と縮んだ"
        prev = left


def test_a_burst_of_cheap_closes_cannot_make_the_last_gate_hours_away(tmp_path):
    """**安い門を5件まとめて閉じても、残り1件が「5時間後」にはならないこと。**

    直す前は `5件 ÷ 1日 ＝ 5.00件/日` → 残り1件は **0.2日**。
    主実行はそれを読んで「門は ほぼ 済んでいる」と判断できてしまいます。
    """
    led = _ledger(tmp_path, [(n, "2026-08-30") for n in range(1, 6)])
    left = resume_gate.days_to_close(_PAUSE_TEXT, led, date(2026, 8, 31))
    assert left == pytest.approx(1.0), f"残り1件が {left}日 になっている"


def test_the_wait_since_the_last_close_is_a_floor(tmp_path):
    """**すでに待った日数より速く閉じる、とは言わせないこと。**

    間隔が 1日 の実績でも、最後に閉じてから 10日 空いていれば、
    次の1件を 1日 とは見積もりません（打ち切りの間隔のほうを採る）。
    """
    led = _ledger(tmp_path, [(1, "2026-08-30"), (2, "2026-08-31"), (3, "2026-09-01")])
    # 完了した間隔は 1日。**最後に閉じた翌日**なら、そのまま 1日/件
    assert resume_gate.days_per_close(_PAUSE_TEXT, led, date(2026, 9, 2)) == pytest.approx(1.0)
    # 10日 空いたら、1件あたりは 10日（1日 のままにしない）
    assert resume_gate.days_per_close(_PAUSE_TEXT, led, date(2026, 9, 11)) == pytest.approx(10.0)
    assert resume_gate.days_to_close(_PAUSE_TEXT, led, date(2026, 9, 11)) == pytest.approx(30.0)


def test_all_closed_is_zero_days_even_when_the_rate_is_unmeasured(tmp_path):
    """**残りが 0件 なら 0日。** 速さが測れていなくても、閉じるものがありません。"""
    led = _ledger(tmp_path, [(n, "2026-08-30") for n in range(1, 7)])
    assert resume_gate.closed_count(_PAUSE_TEXT, led) == 6
    assert resume_gate.days_per_close(_PAUSE_TEXT, led, date(2026, 8, 30)) is None
    assert resume_gate.days_to_close(_PAUSE_TEXT, led, date(2026, 8, 30)) == 0.0


def test_summary_carries_where_the_number_came_from(tmp_path):
    """**「残り N日」の出どころが `summary()` に載っていること。**

    印字がここを出さないと、次に読む側は間隔と経過を区別できません。
    """
    led = _ledger(tmp_path, [(1, "2026-08-30"), (2, "2026-08-30"), (3, "2026-08-30")])
    s = resume_gate.summary(_PAUSE_TEXT, led, date(2026, 9, 4))
    assert s["since_last_close"] == 5
    assert s["days_per_close"] == pytest.approx(5.0)
    assert s["days_to_close"] == pytest.approx(15.0)
    assert s["rate_per_day"] == pytest.approx(1 / 5.0)
