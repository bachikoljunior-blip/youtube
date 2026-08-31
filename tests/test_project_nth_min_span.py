"""**0日 の窓から「1日 N本 作れる」を名乗らないこと。**（2026-08-27・最適化の回）

## 何が壊れていたか

`scripts/deadline_check._project_nth()` は、群がまだ床に満たないとき
「あと何日で N本目が公開されるか」を **`rate = have / (as_of - since).days`** で
推定します。分母は `max(1, ...)` でした ——**その日に立てた A/B は、窓 0日 で
`have / 1` を「実測の伸び率」として名乗ります。**

**同じファイルの `_ans_accrual` は、その1日 前に同じ穴を塞いでいます**
（`_MIN_SPAN_DAYS = 2`。原文「**1日の窓から伸び率を出さないこと**」）。
**同じ日に、同じ目的で書かれた隣の関数**に、門が付いていませんでした。

実測 2026-08-27 22:2x（塞ぐ前に実際に印字されていた偽の日付）::

    slide_pace    since 2026-08-27（**窓 0日**）  速い 5本 → **5.00本/日**
                                                 遅い 3本 → **3.00本/日**
                  → 16本目 09/13・09/15 → **判定 09-21**
    request_form  since 2026-08-26（**窓 1日**）  22本 → **22.00本/日**

この日付は `src/arm_speed.forward()` の分子（＝到達日の入力）に乗ります。

## なぜ `None` に戻さないか

`_ans_accrual` は窓が足りないと日を出しません。**こちらで同じことをすると
`forward()` の `undated` に落ち、腕が丸ごと凍ります** ——
`_project_nth` の docstring が、まさにその実測（`sub_rate` が機械から
見えていなかった）から書かれています。**日は出し、分母だけ下限で押さえる。**

## 覆る条件

群の本ごとに「作った時刻」が引けるようになったら（`batch_runs.jsonl` の `at` を
群へ結び直す）、`since` からの経過ではなく**実際に作った時刻の幅**で割れます。
そのときこの下限は要らなくなり、この検査も消してよい。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check                                          # noqa: E402


def _rows() -> list[dict]:
    """`uploaded.jsonl` の形（`uploaded_at` ＝ 作った日・`at` ＝ 公開の予約日）。"""
    return [{"uploaded_at": "2026-08-27", "at": "2026-09-06"} for _ in range(5)]


def test_zero_day_window_does_not_claim_a_rate() -> None:
    """**窓 0日 で `have / 1` を名乗らない。**"""
    as_of = date(2026, 8, 27)
    pub = ["2026-09-06"] * 5
    got = deadline_check._project_nth(_rows(), pub, 16, "2026-08-27", as_of)
    assert got is not None, "日を出さずに返しています（`None` は腕を凍らせます）"
    _nth, rate, _lead, _slack, warn = got
    assert rate <= 5 / deadline_check._MIN_SPAN_DAYS + 1e-9, (
        f"窓 0日 から **{rate:.2f}本/日** を名乗っています"
        f"（分母の下限 {deadline_check._MIN_SPAN_DAYS}日 が効いていません）")
    assert warn, "下限を当てたのに、そう言っていません（実測の伸び率として読まれます）"


def test_long_enough_window_is_untouched() -> None:
    """**窓が足りている回は、1日も動かさない。**（下限は上書きではありません）"""
    as_of = date(2026, 8, 27)
    since = (as_of - timedelta(days=10)).isoformat()
    pub = ["2026-09-06"] * 5
    _nth, rate, _lead, _slack, warn = deadline_check._project_nth(
        _rows(), pub, 16, since, as_of)
    assert abs(rate - 5 / 10) < 1e-9, f"窓 10日 の伸び率が {rate:.3f} に化けています"
    assert not warn, "下限を当てていないのに、当てたと言っています"


def test_slower_rate_pushes_the_date_out_not_in() -> None:
    """下限を当てた回の日付は、**当てない場合より後ろ**（＝楽観を取り下げる向き）。"""
    as_of = date(2026, 8, 27)
    pub = ["2026-08-28"] * 5                       # 既にある本は近い日（clamp を避ける）
    rows = [{"uploaded_at": "2026-08-27", "at": "2026-08-28"} for _ in range(5)]
    nth, _r, _l, _s, _w = deadline_check._project_nth(rows, pub, 16, "2026-08-27", as_of)
    # 窓 0日 のまま `have/1 = 5.00本/日` なら ceil(11/5)=3日、
    # 下限 2日 を当てると `5/2 = 2.50本/日` で ceil(11/2.5)=5日。**2日 後ろへ。**
    assert nth >= as_of + timedelta(days=5), (
        f"{nth} —— 下限を当てても日付が手前のままです（楽観が残っています）")
