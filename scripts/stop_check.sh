#!/usr/bin/env bash
# ターンを終えようとしたときに1回だけ割り込み、「いま終わるのが目標に対して
# 最善か」を問い直す。**2回目は通す**ので堂々巡りにはならない。
#
# なぜ文書ではなくフックなのか。同じことを docs/GOAL.md に書いたのに、
# 書いた本人が次の回で破ったから。文書は思い出させるだけで、止めない。
#
# **これは「終わるな」ではない。** 2026-08-05 にオーナーが常時稼働をやめると
# 決めたので、終わってよい回のほうが多い。トークンには週100クレジットの上限が
# あり、無駄に起きているのは上限を食う。**問うているのは「終わるかどうか」ではなく
# 「終わるのが最善かを考えたかどうか」。** 考えた上で終わるなら、それが正解。
set -u

SENTINEL="/tmp/claude-youtube-stop-checked"
NOW=$(date +%s)

# 5分以内に一度問うていれば通す
if [ -f "$SENTINEL" ]; then
  LAST=$(cat "$SENTINEL" 2>/dev/null || echo 0)
  if [ $((NOW - LAST)) -lt 300 ]; then
    rm -f "$SENTINEL"
    exit 0
  fi
fi
echo "$NOW" > "$SENTINEL"

# --- いまの状態を集める（ネットワークは使わない。フックは速いこと） ---
if pgrep -f "src.pipeline" > /dev/null 2>&1; then
  RUNNING="あり（src.pipeline が動いている。**コンテナ再起動で消えるので当てにしない**）"
else
  RUNNING="なし"
fi

if [ -n "$(git -C "$(dirname "$0")/.." status --porcelain 2>/dev/null)" ]; then
  DIRTY="あり（push していない変更がある）"
else
  DIRTY="なし"
fi

# 週の区切りは土曜07:00 JST。リセットまでの残り時間を出す。
HOURS=$(TZ=Asia/Tokyo python3 - <<'PY' 2>/dev/null || echo "?"
from datetime import datetime, timedelta
now = datetime.now()
end = now.replace(hour=7, minute=0, second=0, microsecond=0)
while end.weekday() != 5 or end <= now:
    end += timedelta(days=1)
print(f"{(end - now).total_seconds() / 3600:.0f}")
PY
)

cat <<EOF >&2
【終わる前の確認】いま終わるのが**目標に対して**最善か、答えてから終わってください。

- 背後で走っているもの: ${RUNNING}
- 未コミットの変更: ${DIRTY}
- トークン予算のリセットまで: あと ${HOURS} 時間（週100クレジット／土曜07:00 JST 区切り）

**これは「終わるな」ではありません。** 常時稼働はしない方針なので、
終わってよい回のほうが多い。無駄に起きているのは予算を食い、使い切れば
次のリセットまで分析も投稿も止まります。

天秤にかけるのはこの2つです。

1. **投稿の予約は切れていないか。** 切れそうなら、他を削ってでも生成に使う。
   投稿が途切れるのが最大の損失。予約が数日先まで埋まっているなら、
   **起きなくてもチャンネルは動くので終わってよい。**
   分からなければ \`python scripts/status.py\` の「予約が入っていない日」を見る。
2. **判定を先送りしていないか。** 期限の来た前提（config/hypotheses.yaml）を
   放置して終わると、推測が推測のまま残る。

終わると決めたなら、**未コミットの変更を push してから**終わること。
そのうえでもう一度終了すれば、この確認は通ります。
EOF

# decision=block で1回だけ引き止める
printf '{"decision":"block","reason":"上の確認に答えてから終わってください"}\n'
exit 0
