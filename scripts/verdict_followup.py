#!/usr/bin/env python3
"""**外れた前提の「次の手」が、記録されないまま残っていないか。**

中身と、なぜ要るかは `src/followup.py` の冒頭にあります。**ここは薄い口だけ**です
（`src/day_cap.py` と `scripts/` の関係と同じ）。

    python scripts/verdict_followup.py            古い順に3件
    python scripts/verdict_followup.py --all      全部
    python scripts/verdict_followup.py --gate     印字して、残っていれば exit 2

`--gate` は `scripts/stop_check.sh` が呼びます。**API は叩きません**
（読むのは `config/hypotheses.yaml` だけ・一瞬）。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import followup  # noqa: E402  （`sys.path` を通した後でないと読めません）


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true",
                    help="古い順に3件ではなく、全部出す")
    ap.add_argument("--gate", action="store_true",
                    help="残っていれば exit 2（stop フックが読む）")
    args = ap.parse_args(argv)

    doc = followup.load()
    text, overdue = followup.report(doc, limit=10_000 if args.all else 3)
    print(text)
    if args.gate and overdue:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
