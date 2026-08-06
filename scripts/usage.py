#!/usr/bin/env python3
"""今週これまでに使ったトークンを数え、週間使用量の%に換算する。

    python scripts/usage.py

なぜ要るか。**予算はこれまでオーナーに教えてもらうしかなかった。**
「今週の残りは2%」と言われて初めて分かる状態で、`A1`（私側への指示を必ず読むとは
限らない）に照らすと危うい。**自分で測れるなら、そのほうがいい。**

測り方。Claude Code はセッションの記録を `~/.claude/projects/**/*.jsonl` に残していて、
1応答ごとの `usage`（入力・出力・キャッシュ）が入っている。**そこを数える。**

**単純なトークン数では合わない。** 種類ごとに重みが違う。

オーナーの実測が2点ある。どちらも claude-opus-5 なので、モデル差では説明できない。

    期間A  2026-08-05 16:00〜19:00   209応答  1〜2%
    期間B  2026-08-06 09:00〜09:40    35応答   0.2%

何に比例するかを、2点のずれの小ささで選んだ:

    キャッシュ読み込み   82.5M/%  vs 52.5M/%   → **1.57倍ずれる**（合わない）
    応答数            0.0072%  vs 0.0057%   → 1.26倍
    出力トークン        4.70%/M  vs 4.27%/M   → 1.10倍
    **重み付き和**      10.6〜21.2M/% vs 14.2M/% → **範囲に収まる**

重みは API の価格体系に倣った（出力5・キャッシュ書1.25・入力1・キャッシュ読0.1）。
**期間Bの値が期間Aの幅の中に入るのは、この置き方だけだった。**

**私が主に数えていたキャッシュ読み込みが、いちばん説明力が低かった。**
文脈が積もるとキャッシュ読みは膨らむが、そこは安い。**高いのは出力。**
つまり律速は「文脈の長さ」より **「どれだけ書いたか」**。

**「安全側」の向きに注意。** 1%あたりの値が**大きい**ほど消費を**少なく**見せる。
2026-08-06 に 47M を「安全側」と書いて使い、残量を倍近く多く見ていた。
**迷ったら小さい値**（期間Aの下限 11M）を使うこと。

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

# 種類ごとの重み。API の価格体系に倣う。**出力が一番高い。**
WEIGHTS = {
    "input_tokens": 1.0,
    "cache_creation_input_tokens": 1.25,
    "cache_read_input_tokens": 0.1,
    "output_tokens": 5.0,
}
# 1% あたりの重み付き合計。**小さいほうが安全側**（消費を多めに見積もる）。
# 11M = 期間Aの下限（＝Aが2%だった場合）。14M = 期間Bの実測。
TOKENS_PER_PCT = 11_000_000
TOKENS_PER_PCT_OPTIMISTIC = 14_000_000

TRANSCRIPTS = Path.home() / ".claude" / "projects"


def week_start(now: datetime | None = None) -> datetime:
    """直近の土曜07:00 JST（予算の区切り）を返す。"""
    now = now or datetime.now(JST)
    start = now.replace(hour=7, minute=0, second=0, microsecond=0)
    while start.weekday() != 5 or start > now:   # 5 = 土曜
        start -= timedelta(days=1)
    return start


def tokens_since(since: datetime) -> tuple[float, int]:
    """since 以降のトークン数と応答数を返す。

    **セッションをまたいで数える。** 記録は複数ファイルに分かれるので全部見る。
    **種類ごとに重みを掛けて足す。** 単純な合計では2つの実測点が
    1.57倍ずれた（docstring 参照）。出力が一番高く、キャッシュ読みが一番安い。
    """
    total, replies = 0.0, 0
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
                    total += sum(u.get(k, 0) * w for k, w in WEIGHTS.items())
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
    print("  重み付き合計。出力5・キャッシュ書1.25・入力1・キャッシュ読0.1。")
    sys.exit(0)
