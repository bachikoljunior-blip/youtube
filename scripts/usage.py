#!/usr/bin/env python3
"""今週これまでに使ったトークンを数え、週間使用量の%に換算する。

    python scripts/usage.py

なぜ要るか。**予算はこれまでオーナーに教えてもらうしかなかった。**
「今週の残りは2%」と言われて初めて分かる状態で、`A1`（私側への指示を必ず読むとは
限らない）に照らすと危うい。**自分で測れるなら、そのほうがいい。**

測り方。Claude Code はセッションの記録を `~/.claude/projects/**/*.jsonl` に残していて、
1応答ごとの `usage`（入力・出力・キャッシュ）が入っている。**そこを数える。**

換算の較正（オーナーの実測）:

    2026-08-05 16:00以降の 94M トークン ＝ 1〜2%   → 1% は 47M〜94M
    2026-08-06 09:00以降の 5.5M トークン ＝ 0.2%   → 1% は **27M**（Opus 5）

**2つ目が範囲の外に出た。** モデルが変わると換算も変わる、という予想どおり。
新しいほうを採る（同じモデル・同じ日・応答数も分かっている）。

**「安全側」の向きを取り違えていた。** 1%あたりのトークン数が**大きい**ほど、
同じトークン数を少ない%に換算する。つまり 47M は**消費を少なく見せる＝危険側**。
47M を「安全側」と書いて使っていたせいで、**今週の累計を 8.3% と見ていたが
実際は 14.4% だった。** 定常15%をほぼ使い切っている。

**残量を多めに見せるほうが危険。** 迷ったら小さい値を使うこと。

**この換算は推測混じりです。** 桁を掴むためのもので、正確な残量ではありません。
オーナーから実際の%を聞けたら、`TOKENS_PER_PCT` を較正し直すこと。

**モデルが変わると換算も変わるはずです。** サブスクの消費は1トークンあたり一律では
なく、モデルごとに重みが違うのが普通。較正した 47M/% がどのモデルでの値なのかは
記録が無い（2026-08-05 の対話は途中でモデルが変わっている）。
**だから「トークン数」は正確でも、「%」は目安。** 桁が合っていれば十分という前提で
使い、割り当てを使い切ったと出たら**素直に切ること**（多めに見積もる側に倒してある）。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))

# 1% あたりのトークン数。較正は上の docstring。
# **小さいほうが安全側**（消費を多めに見積もる）。2026-08-06 の実測が 27M。
TOKENS_PER_PCT = 27_000_000
TOKENS_PER_PCT_OPTIMISTIC = 47_000_000

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


def summary(since: datetime | None = None) -> dict:
    """since 以降の使用量。省略したら週の区切りから。

    **「今週これまで何%」と「この時点から何%」は別の量。**
    オーナーの割り当ては後者で来ることがある（2026-08-05「今から1.5%」）。
    累計で測ると、すでに使ったぶんが混ざって指示の意味が変わってしまう。
    """
    since = since or week_start()
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
