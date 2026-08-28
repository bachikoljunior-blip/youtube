#!/usr/bin/env python3
"""**「深い題のショート」の前提を、`falsified_if` の手順そのままで判定する。**

中身は `src/deep_short.py`（門の `count_expr` も同じ関数を呼びます ——
**2か所が別々に同じ問いを解くのをやめました**。理由はそちらの docstring）。

    python scripts/deep_short_verdict.py      # API 0単位

exit 0 なら判定が出ています（survived / falsified）。exit 2 は「まだ判定できない」。
"""
from __future__ import annotations

import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import deep_short as D  # noqa: E402


def render(m: dict) -> list[str]:
    p = [f"=== 深い題のショート（`falsified_if` の手順そのまま・API 0単位）"
         f"／{m['as_of']} ===",
         f"  群（齢 {D.AGE_H:.0f}時間・**その日の生きた帯の中だけ**）: "
         f"処置 **{m['n_treat']}本** ／ 対照 **{m['n_ctrl']}本**"
         f"（どちらも {D.MIN_PER_ARM}本 要る）"]
    if m["per_day"]:
        p.append("  公開日ごと（処置の平均 ÷ 対照の平均）:")
        for d, s in sorted(m["per_day"].items()):
            t, c = s.get("処置") or [], s.get("対照") or []
            r = m["ratios"].get(d)
            p.append(f"    {d}  処置 {len(t):>2}本 平均 {statistics.fmean(t):>8,.0f}"
                     f" ／ 対照 {len(c):>2}本 平均 {statistics.fmean(c):>8,.0f}"
                     + (f"  → **×{r:.2f}**" if r else "  → 対照が0再生（比を出しません）"))
    else:
        p.append("  **処置と対照が同じ日に居る公開日が1日もありません。**")
    if m["blocked"]:
        p.append("  → **判定できません**: " + " ／ ".join(m["blocked"]))
        p.append("     **`falsified_if` を緩めないこと。** 動かすのは期限のほうです"
                 "（`python scripts/deadline_check.py`）。"
                 "**「まだ分からない」で閉じないこと。**")
        return p
    p.append(f"  比の**中央値**: **×{m['median']:.2f}**（合格点 ×{D.BAR}）")
    p.append(f"  → **{m['verdict']}**")
    if m["verdict"] == "falsified":
        p.append("     `next_if_false`: 次に疑うのは**族**。深い題は `calc_sections` を"
                 "持つぶん族が偏っている（`src/family_perf.py` が族べつに4倍の差）。"
                 "**同じ族の `s-` 題と深い題**で比べ直すこと")
    return p


def main() -> int:
    m = D.measure()
    print("\n".join(render(m)))
    return 0 if m["verdict"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
