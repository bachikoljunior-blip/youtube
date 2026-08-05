#!/usr/bin/env python3
"""今週これまでに使ったトークンを数え、週間使用量の%に換算する。

    python scripts/usage.py

なぜ要るか。**予算はこれまでオーナーに教えてもらうしかなかった。**
「今週の残りは2%」と言われて初めて分かる状態で、`A1`（私側への指示を必ず読むとは
限らない）に照らすと危うい。**自分で測れるなら、そのほうがいい。**

測り方。Claude Code はセッションの記録を `~/.claude/projects/**/*.jsonl` に残していて、
1応答ごとの `usage`（入力・出力・キャッシュ）が入っている。**そこを数える。**

換算の較正（2026-08-05、オーナーの実測）:

    16:00以降の 94M トークン ＝ 週間使用量の 1〜2%

つまり 1% は 47M〜94M。**安全側（47M）を使う。** 使用量を多めに見積もるほうが、
使い切って何もできなくなるより安い。**幅があること自体を忘れないこと。**

**この換算は推測混じりです。** 桁を掴むためのもので、正確な残量ではありません。
オーナーから実際の%を聞けたら、`TOKENS_PER_PCT` を較正し直すこと。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

# 1% あたりのトークン数。較正は上の docstring。
# 47M = 安全側（94M が 2% だった場合）。94M = 楽観側（94M が 1% だった場合）。
TOKENS_PER_PCT = 47_000_000
TOKENS_PER_PCT_OPTIMISTIC = 94_000_000

TRANSCRIPTS = Path.home() / ".claude" / "projects"


def week_start(now: datetime | None = None) -> datetime:
    """直近の土曜07:00 JST（予算の区切り）を返す。"""
    now = now or datetime.now(JST)
    start = now.replace(hour=7, minute=0, second=0, microsecond=0)
    while start.weekday() != 5 or start > now:   # 5 = 土曜
        start -= timedelta(days=1)
    return start


def tokens_since(since: datetime) -> tuple[int, int]:
    """since 以降のトークン数と応答数を返す。

    **セッションをまたいで数える。** 記録は複数ファイルに分かれるので全部見る。
    数え方は較正時と揃えること（入力＋キャッシュ書き込み＋キャッシュ読み込み）。
    出力は較正時で0.3%未満だったので入れていない。
    """
    total = replies = 0
    if not TRANSCRIPTS.exists():
        return 0, 0
    for path in TRANSCRIPTS.rglob("*.jsonl"):
        try:
            with path.open(encoding="utf-8") as f:
                for line in f:
                    try:
                        d = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    ts = d.get("timestamp")
                    u = (d.get("message") or {}).get("usage")
                    if not ts or not u:
                        continue
                    t = datetime.fromisoformat(ts.replace("Z", "+00:00")).astimezone(JST)
                    if t < since:
                        continue
                    replies += 1
                    total += (u.get("input_tokens", 0)
                              + u.get("cache_creation_input_tokens", 0)
                              + u.get("cache_read_input_tokens", 0))
        except OSError:
            continue
    return total, replies


def summary() -> dict:
    since = week_start()
    total, replies = tokens_since(since)
    return {
        "since": since,
        "tokens": total,
        "replies": replies,
        "pct": total / TOKENS_PER_PCT,
        "pct_optimistic": total / TOKENS_PER_PCT_OPTIMISTIC,
    }


if __name__ == "__main__":
    s = summary()
    print(f"週の区切り: {s['since']:%m/%d %H:%M JST} から")
    print(f"  応答 {s['replies']:,} 回 / {s['tokens'] / 1e6:.0f}M トークン")
    print(f"  週間使用量に換算して **{s['pct']:.1f}%**（楽観側なら {s['pct_optimistic']:.1f}%）")
    print()
    print("  換算は較正済みだが幅がある（94M = 1〜2%）。桁を掴む用。")
    sys.exit(0)
