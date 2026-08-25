"""**順に並べた2つの窓を比べる判定に、公開密度の交絡を必ず添える。**（2026-08-26）

## なぜ足したか

`src/length_verdict.py`・`src/hook_verdict.py`・`src/family_order_verdict.py` は
**どれも「前の窓 対 後の窓」**で engaged 比率を比べています。3件とも**外れ**ました:

    8/4〜8/15（旧設計）        34.8%
    8/16〜8/18（30秒設計）     30.1%   ← length_verdict: 外れ
    8/19〜8/21（冒頭22文字）   22.8%   ← hook_verdict: 外れ
    8/19〜8/20（実績の順番）   24.5%   ← family_order_verdict: 外れ

**同じ期間に、1日の公開本数が 2本 → 25本 へ動いています。**
そして engaged 比率は、その日の本数と**逆向きに動きます**（2026-08-26 の実測・
公開が 08/20 までの 39本）:

    1〜2本/日   n=15   中央値 34.8%
    3〜8本/日   n=14   中央値 25.8%
    9本以上/日  n=10   中央値 19.4%
    片側 p（1〜2本/日 のほうが高い）= **0.057**（α=0.20）

**つまり3件の「外れ」は、どれも密度と完全に共線です。**
処置の効果を測ったのか、その日に何本出したかを測ったのかが**分離できていません。**

## この道具がすること

**分離はできません**（過去のデータでは交絡が解けない）。できるのは
**「解けていない」ことを、判定と同じ画面に出す**ことです。
`overlap()` は2群の「公開日あたりの本数」の中央値を出し、**倍以上ちがえば
`confounded=True`** を返します。judgment を止めはしません —— 止めると
`falsified_if` を緩めたことになるからです。**印字するだけ。**

## 解くには

**同じ日の中で群を割ること**（`src/motion_groups.py` の共有日と同じ考え方）。
順に並べた窓では、密度・季節・チャンネルの成長が全部まざります。
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from typing import Any, Iterable

JST = timezone(timedelta(hours=9))

#: 2群の密度がこの倍率以上ちがったら「交絡している」と言う。
#: **2倍**は、上の実測（2本/日 と 9本以上/日 で 中央値が 15pt ちがう）から置いた線。
FOLD = 2.0


def per_day(published: dict[str, datetime]) -> dict[date, int]:
    """**公開日ごとの本数**（JST の暦日）。母集団は「予約も含む全部」を渡すこと ——
    群に入った本だけで数えると、その日に何本出たかではなく群の大きさを測ります。"""
    out: dict[date, int] = defaultdict(int)
    for born in published.values():
        out[born.astimezone(JST).date()] += 1
    return dict(out)


def density_of(ids: Iterable[str], published: dict[str, datetime],
               counts: dict[date, int] | None = None) -> list[int]:
    """群の各本について「**その本が出た日の本数**」を返す。"""
    counts = counts if counts is not None else per_day(published)
    out = []
    for vid in ids:
        born = published.get(vid)
        if born is None:
            continue
        out.append(counts.get(born.astimezone(JST).date(), 0))
    return out


def overlap(a_ids: Iterable[str], b_ids: Iterable[str],
            published: dict[str, datetime]) -> dict[str, Any]:
    """2群の公開密度を並べ、**倍以上ちがえば交絡していると言う。**"""
    counts = per_day(published)
    a, b = density_of(a_ids, published, counts), density_of(b_ids, published, counts)
    if not a or not b:
        return {"confounded": False, "why": "片方の群が空です",
                "median_a": None, "median_b": None, "fold": None}
    ma, mb = statistics.median(a), statistics.median(b)
    lo, hi = min(ma, mb), max(ma, mb)
    fold = float("inf") if lo == 0 else hi / lo
    return {
        "confounded": fold >= FOLD,
        "median_a": ma, "median_b": mb, "fold": fold,
        "why": "" if fold < FOLD else
               f"公開密度が {ma:.0f}本/日 対 {mb:.0f}本/日（{fold:.1f}倍）。"
               "**処置の効果と分離できていません**",
    }


def line(a_ids: Iterable[str], b_ids: Iterable[str],
         published: dict[str, datetime]) -> str:
    """判定の画面に1行で足すための文字列。**空文字は返しません**（黙ると読まれない）。"""
    r = overlap(a_ids, b_ids, published)
    if r["median_a"] is None:
        return "  交絡（公開密度）: " + r["why"]
    head = "[!] **交絡あり**" if r["confounded"] else "交絡なし"
    return (f"  公開密度: 対照 {r['median_a']:.0f}本/日 ／ 処置 {r['median_b']:.0f}本/日"
            f"（{r['fold']:.1f}倍） → {head}")
