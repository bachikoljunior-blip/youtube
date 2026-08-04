#!/usr/bin/env bash
# ターンを終えようとしたときに割り込んで、「いま終わるのが最善か」を必ず問う。
#
# なぜフックにするのか。同じことを docs/GOAL.md に書いたが、書いた本人が
# 次の回で破った（残り10分のレンダリングに22分の待機を置いてモデルを止めた）。
# **文書は思い出させるだけで、止めない。** 止めるには実行される仕組みが要る。
#
# 1回だけ差し込んで、2回目は通す。通さないと終われなくなって堂々巡りになるため。
# 差し込みの記録は sentinel に置き、5分で失効させる（次のターンでは再び効く）。
set -uo pipefail

SENTINEL=/tmp/claude-youtube-stop-checked

if [ -f "$SENTINEL" ]; then
  age=$(( $(date +%s) - $(stat -c %Y "$SENTINEL" 2>/dev/null || echo 0) ))
  if [ "$age" -lt 300 ]; then
    rm -f "$SENTINEL"
    exit 0
  fi
fi
touch "$SENTINEL"

# いまの状態を集める。判断材料が無いと、問いが形式的になって効かない。
if pgrep -f "src\.pipeline" >/dev/null 2>&1; then
  running="あり（src.pipeline が動いている）"
else
  running="**なし**"
fi

cd "$(dirname "$0")/.." || exit 0
if [ -n "$(git status --porcelain 2>/dev/null)" ]; then
  dirty="**あり（未コミット）**"
else
  dirty="なし"
fi

python3 - "$running" "$dirty" <<'PY' 2>/dev/null || exit 0
import json, sys
running, dirty = sys.argv[1], sys.argv[2]
print(json.dumps({
    "decision": "block",
    "reason": (
        "【終わる前の確認】いま終わるのが目標に対して最善か、答えてから終わってください。\n\n"
        f"- 背後で走っているもの: {running}\n"
        f"- 未コミットの変更: {dirty}\n\n"
        "終わってよいのは次の3つだけです。\n"
        "1. 文脈が限界に近く、続けると判断が雑になる\n"
        "2. オーナーの判断が要る分岐に当たった\n"
        "3. 実時間の経過そのものを待つしかない（予約公開の時刻、実績の反映）\n\n"
        "3 の場合でも、**待っているものと、やれることは別物**です。"
        "レンダリングを待つあいだにショートも計算も台本も書けます。"
        "docs/GOAL.md の「いつでも手をつけられる仕事」を見て、"
        "依存していない作業が残っていないか確かめてください。\n\n"
        "終わると決めたなら、その前に必ず (a) 背後で次を走らせる "
        "(b) send_later で自分を呼び戻す (c) 変更を push する。\n"
        "そのうえでもう一度終了すれば、この確認は通ります。"
    ),
}, ensure_ascii=False))
PY
