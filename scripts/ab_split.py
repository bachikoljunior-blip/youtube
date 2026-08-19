#!/usr/bin/env python3
"""走っている A/B の群を数える（**指示が入った本だけ**）。

    python scripts/ab_split.py [--as-of YYYY-MM-DD]

判定できるかどうかは、**IDで割った件数ではなく、指示が入った本の数**で決まります。
理由は `src/ab_split.py` の冒頭に書いてあります。
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.ab_split import report  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--as-of", help="判定日（既定は実験ごとの期限）")
    a = ap.parse_args()
    when = date.fromisoformat(a.as_of) if a.as_of else None
    print(report(as_of=when))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
