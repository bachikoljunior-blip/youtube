#!/usr/bin/env python3
"""走っている A/B の群を数える（**指示が入った本だけ**）。

    python scripts/ab_split.py [--as-of YYYY-MM-DD] [--outlook] [--power]

判定できるかどうかは、**IDで割った件数ではなく、指示が入った本の数**で決まります。
理由は `src/ab_split.py` の冒頭に書いてあります。

`--outlook` を付けると、**足りない本を残りの在庫で埋められるか**まで出します
（2026-08-20 04:4x に足した。`src/ab_split.outlook` の冒頭に理由）。
**在庫を数えるので数十秒かかります。API は1単位も使いません。**

`--power` は **判定の規則そのものが当てられるか**を、実データから測って表にします
（2026-08-20 05:2x に足した。`src/ab_power.py` の冒頭に理由）。
**中央値の大小だけでは、効きが無くても 49% で「上回った」と出ます。**
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import ab_power  # noqa: E402
from src.ab_split import EXPERIMENTS, report, settle_by  # noqa: E402


def stock_by_experiment(count: int = 60, today: date | None = None) -> dict[str, dict[str, int]]:
    """実験ごとに「未投稿の在庫が、どちらの腕に何本あるか」。

    **実験ごとに締切までの日数で数えます**（2026-08-20 19:2x に測って直した）。

    ここは長らく `_pool(count)` —— つまり **1日ぶんの上限**でした。
    `pick` の `per_calc=2` は「同じ制度の本が**1日に**何本も並ぶと繰り返しに見える」
    ための門なので、**締切が20日先なら 2本/日 × 20日 まで置けます。**
    1日ぶんで数えると、実測で **33本の在庫が 26本**に見えました
    （aoiro 5→2・zoyo 4→2・kogaku 3→2・nenkinmenjo 3→2）。

    `hook_form` の床は両群16本＝**32本**なので、この7本の差が
    「在庫だけでは床に届きません」と「届きます」を分けます。
    """
    from scripts.ab_balance import _pool, days_until, tally

    out: dict[str, dict[str, int]] = {}
    for name, exp in EXPERIMENTS.items():
        days = days_until(settle_by(exp), today)
        rows = _pool(count, days)
        out[name] = {g: len(v) for g, v in tally(rows, exp.split).items()}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", help="判定日（既定は実験ごとの期限）")
    ap.add_argument("--outlook", action="store_true",
                    help="足りない本を残りの在庫で埋められるかまで出す（在庫を数えるので数十秒）")
    ap.add_argument("--power", action="store_true",
                    help="判定の規則そのものが当てられるかを、実データから測って表にする")
    a = ap.parse_args()
    if a.power:
        print(ab_power.table())
        print()
    when = date.fromisoformat(a.as_of) if a.as_of else None
    stock = stock_by_experiment() if a.outlook else None
    print(report(as_of=when, stock=stock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
