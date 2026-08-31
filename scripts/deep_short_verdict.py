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
        p += render_family(D.by_family(m["as_of"]))
    return p


def render_family(f: dict) -> list[str]:
    """`next_if_false`（族を疑え）の答えを、**同じ回のうちに**並べる。

    **これは 2026-08-31 に、この前提を閉じた回が配線しました。**
    ここには長らく `next_if_false` の本文を印字するだけの3行がありました ——
    **「次はこれをやれ」と言うだけで、誰もやらないまま閉じる**のが
    `src/followup.py` の見つけた壊れ方（外れた前提 14件・31手・実行 0件）です。
    **数は既にあるので、言うのではなく出します。**
    """
    if not f["ratios"]:
        return ["  族をそろえた比: **両群がそろう族が1件もありません**"]
    p = ["  --- `next_if_false`（族を疑え）の答え ＝ **族をそろえて出し直した比** ---"]
    for fam, r in sorted(f["ratios"].items(), key=lambda x: x[1]):
        s = f["per_family"][fam]
        p.append(f"    {fam:<16} 処置 {len(s['処置']):>2}本 平均 "
                 f"{statistics.fmean(s['処置']):>7,.0f} ／ 対照 {len(s['対照']):>2}本 平均 "
                 f"{statistics.fmean(s['対照']):>7,.0f}  → **×{r:.2f}**")
    below = sum(1 for r in f["ratios"].values() if r < 1.0)
    p.append(f"  族をそろえた比の**中央値**: **×{f['median']:.2f}**"
             f"（合格点 ×{f['bar']}・族 {f['families']}件・うち 1.0未満 {below}件）")
    p.append("  → **族ではありません。** 族をそろえると比は**さらに下がります**"
             "（交絡なら合格点へ寄るはずでした）。"
             "**覆る条件**は `src/deep_short.by_family` の docstring")
    return p


def main() -> int:
    m = D.measure()
    print("\n".join(render(m)))
    return 0 if m["verdict"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
