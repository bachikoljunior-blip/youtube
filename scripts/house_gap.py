#!/usr/bin/env python3
"""床（オーナーの与件）と、予測が実際に前に置いている供給の差を数える。

オフラインで完結する。API を1単位も使わない。

    python scripts/house_gap.py

## なぜ

与件は「1日一本・作り置きなし」（2026-09-01 から）。
2026-08-31 に数えたところ、その床はどこにも実装されておらず、
`scripts/eta.py` は `PLAN_PUBLISH_PER_DAY = 25` で到達日と段1〜4 を解いていた。

**床より多い供給を前に置くと、腕の順位が壊れる。**
供給が効く腕（density など）が過大に、効かない腕（RPM・維持率）が過小に出る。
その順位で腕を選んでいる限り、「最適化されているか」の答えは いいえ。

この道具は、その差を毎回その場で数えるためのもの。**印字を信じず、ここを見ること。**
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.house_rule import (  # noqa: E402
    COUNT_BACKLOG_AS_SUPPLY,
    EFFECTIVE_FROM,
    PUBLISH_PER_DAY,
)


def _eta_plan_density() -> int | None:
    """`scripts/eta.py` が実際に前に置いている密度。import せずに読む
    （eta.py の import は重く、外の口を触る経路がある）。"""
    text = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    for line in text.splitlines():
        if line.startswith("PLAN_PUBLISH_PER_DAY"):
            return int(line.split("=", 1)[1].split("#")[0].strip())
    return None


def _scheduled_ahead() -> tuple[int, str | None, int]:
    """予約済みで、まだ公開されていない本数と、いちばん先の日付。"""
    path = ROOT / "data" / "uploaded.jsonl"
    if not path.is_file():
        return 0, None, 0
    days: Counter[str] = Counter()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        at = row.get("at") or row.get("publish_at") or row.get("uploaded_at") or ""
        if at:
            days[at[:10]] += 1
    if not days:
        return 0, None, 0
    ahead = {d: n for d, n in days.items() if d >= EFFECTIVE_FROM}
    return sum(ahead.values()), (max(ahead) if ahead else None), len(ahead)


def main() -> int:
    plan = _eta_plan_density()
    backlog, furthest, spread_days = _scheduled_ahead()

    print("床（オーナーの与件・src/house_rule.py）")
    print(f"  1日に公開してよい本数     {PUBLISH_PER_DAY} 本/日（{EFFECTIVE_FROM} から）")
    print(f"  作り置きを供給に数えるか   {'はい' if COUNT_BACKLOG_AS_SUPPLY else 'いいえ'}")
    print()
    print("予測が実際に前に置いているもの（scripts/eta.py）")
    print(f"  PLAN_PUBLISH_PER_DAY     {plan} 本/日")

    if plan is None:
        print("  ! PLAN_PUBLISH_PER_DAY が読めません。eta.py を見ること。")
        return 1

    ratio = plan / PUBLISH_PER_DAY
    print()
    if ratio > 1:
        print(f"**差 ×{ratio:.0f}** —— 到達日も段1〜4 も腕の順位も、")
        print(f"  床の {ratio:.0f}倍 の供給の上で解かれています。")
        print("  供給が効く腕が過大に、効かない腕が過小に出ます。")
        print("  **この差がある間、「最適化されているか」の答えは いいえ です。**")
    else:
        print("差なし。予測は床の上で解かれています。")

    print()
    print("作り置き（与件4: 使わない・前提にしない・再利用しない。**消さない**）")
    print(f"  {EFFECTIVE_FROM} 以降に散っている予約  {backlog} 本 / {spread_days} 日")
    if furthest:
        print(f"  いちばん先                        {furthest}")
    if backlog and not COUNT_BACKLOG_AS_SUPPLY:
        print(f"  → 予測の供給から外すべき本数      {backlog} 本")

    return 0 if ratio <= 1 else 2


if __name__ == "__main__":
    raise SystemExit(main())
