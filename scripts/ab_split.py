#!/usr/bin/env python3
"""走っている A/B の群を数える（**指示が入った本だけ**）。

    python scripts/ab_split.py [--as-of YYYY-MM-DD] [--outlook]

判定できるかどうかは、**IDで割った件数ではなく、指示が入った本の数**で決まります。
理由は `src/ab_split.py` の冒頭に書いてあります。

`--outlook` を付けると、**足りない本を残りの在庫で埋められるか**まで出します
（2026-08-20 04:4x に足した。`src/ab_split.outlook` の冒頭に理由）。
**在庫を数えるので数十秒かかります。API は1単位も使いません。**
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ab_split import EXPERIMENTS, report  # noqa: E402


def stock_by_experiment(count: int = 60) -> dict[str, dict[str, int]]:
    """実験ごとに「未投稿の在庫が、どちらの腕に何本あるか」。

    **`batch_build.pick` が返す本だけ**を数えます（在庫全部ではありません ——
    1つの calc から2本までという門が先に効くので、`pick` の返りが実際に作れる上限です）。
    """
    from scripts.ab_balance import _pool, tally

    rows = _pool(count)
    out: dict[str, dict[str, int]] = {}
    for name, exp in EXPERIMENTS.items():
        out[name] = {g: len(v) for g, v in tally(rows, exp.split).items()}
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", help="判定日（既定は実験ごとの期限）")
    ap.add_argument("--outlook", action="store_true",
                    help="足りない本を残りの在庫で埋められるかまで出す（在庫を数えるので数十秒）")
    a = ap.parse_args()
    when = date.fromisoformat(a.as_of) if a.as_of else None
    stock = stock_by_experiment() if a.outlook else None
    print(report(as_of=when, stock=stock))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
