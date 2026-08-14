#!/usr/bin/env bash
# ターンを終えようとしたときに割り込み、**目標に対していま終わるのが最善か**を問う。
#
# 与えられているのは目標だけです（`docs/GOAL.md` 冒頭）。このフックも含めて、
# **ほかは全部こちらの判断**なので、目標に照らして中身を変えてよい。
# ただし**問いそのものを消さないこと。** 消すと、何度も踏んだ穴に戻ります。
#
# なぜ文書ではなくフックなのか。同じことを docs/GOAL.md に書いたのに、
# 書いた本人が次の回で破ったから。文書は思い出させるだけで、止めない。
#
# ## 2026-08-15 に足したもの（オーナー指示「子が、少しの作業で終わるの直して」）
#
# **8/12〜8/15 の回は、全部「分析して日誌を書いて終わり」でした。**
# 文書のほうが「1回の分量は小さくてよい」「ほとんどの回は作らずに終わるのが正しい」
# と書いていたので、**そのとおりに動いていただけ**です。文書は直しました。
# ここでは**機械で確かめられる形**にします:
#
#   `run_marker.py --write` の印はあるのに `--ship` の印が無い
#   ＝ **その回はまだ何も出していない。**
#
# 引き止めるのは **3回まで**。そのあとは通します。
# **止まったまま死ぬほうが、目標に対して確実に悪い**（次の回が来なくなる）。
set -u

# **台本生成の子プロセスでは黙る。**
# 2026-08-07、`goal_reminder.sh` だけにガードを入れて**こちらを忘れた。**
# 子プロセスが「終わるのが最善か」を考えて答え、JSON を返さず生成が3回とも失敗した。
# **フックは全部の子プロセスに効く。片方だけ直しても意味がない。**
[ -n "${YOUTUBE_PIPELINE_CHILD:-}" ] && exit 0

ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# --- いまの状態を集める（ネットワークは使わない。フックは速いこと） ---
if pgrep -f "src.pipeline" > /dev/null 2>&1; then
  RUNNING="あり（src.pipeline が動いている。**畳めばコンテナごと消えるので、待つこと**）"
else
  RUNNING="なし"
fi

if [ -n "$(git -C "$ROOT" status --porcelain 2>/dev/null)" ]; then
  DIRTY="あり（push していない変更がある）"
else
  DIRTY="なし"
fi

# --- この回はもう「出した」か（定期の回だけ効く） ---
# **オーナーと会話している回には効かせません。** 印を打っていない回＝定期ではない。
RAW="${CLAUDE_CODE_REMOTE_SESSION_ID:-}"
ME="${RAW/#cse_/session_}"
SHIP_STATE=$(python3 - "$ROOT/data/runs.jsonl" "$ME" <<'PY' 2>/dev/null || echo unknown
import json, sys, pathlib
path, me = pathlib.Path(sys.argv[1]), sys.argv[2]
if not me or not path.exists():
    print("unknown"); raise SystemExit
started = shipped = False
for ln in path.read_text(encoding="utf-8").splitlines():
    try:
        r = json.loads(ln)
    except Exception:
        continue
    if r.get("session") != me:
        continue
    if r.get("kind") == "ship":
        shipped = True
    else:
        started = True
print("shipped" if shipped else ("empty" if started else "unknown"))
PY
)

COUNTER="/tmp/claude-youtube-ship-blocks-${ME:-none}"
SENTINEL="/tmp/claude-youtube-stop-checked"
NOW=$(date +%s)

# --- (1) 何も出していない定期の回は、3回まで引き止める ---
if [ "$SHIP_STATE" = "empty" ]; then
  N=$(cat "$COUNTER" 2>/dev/null || echo 0)
  if [ "$N" -lt 3 ]; then
    echo $((N + 1)) > "$COUNTER"
    cat <<EOF >&2
【この回はまだ何も出していません】（${N}→$((N + 1))回目・3回で通します）

\`run_marker.py --write\` の印はありますが、\`--ship\` の印がありません。
**分析・日誌・文書の整理は、出したものに数えません。** 前提であって成果ではない。

オーナーの指示（2026-08-15・原文）: **「子が、少しの作業で終わるの直して」**

**次のどれか1つを、いま最後までやってから終わってください**（\`docs/trigger_main.md\` §4）:

  upload   動画を1本。**予約まで入れる。**（生成だけで畳むと build ごと消えます）
  means    \`docs/MEANS.md\` の未着手を1件、**実際に動かす**（実装・実行まで）
  verdict  期限の来た前提を、実データで**判定する**（\`config/hypotheses.yaml\`）
  fix      実測で見つかった欠陥を1つ塞ぐ（道具・生成・投稿のどれか）

やり終えたら:

    python scripts/run_marker.py --ship "<何を出したか1行>"

**本当に出せないなら、その理由を \`docs/JOURNAL.md\` に書いてから終わること。**
「見るところが無かった」は理由になりません。**台帳が短いことのほうを疑う。**

- 背後で走っているもの: ${RUNNING}
- 未コミットの変更: ${DIRTY}
EOF
    printf '{"decision":"block","reason":"この回はまだ何も出していません。上の4つから1つ出してから終わってください"}\n'
    exit 0
  fi
  rm -f "$COUNTER"
  cat <<EOF >&2
【3回問いました。通します】
**出せないまま終わる回になります。** 理由を \`docs/JOURNAL.md\` に必ず書くこと。
書かないと、次の回も同じところで止まります。
EOF
  exit 0
fi

# --- (2) 普通の「終わるのが最善か」。5分以内に一度問うていれば通す ---
if [ -f "$SENTINEL" ]; then
  LAST=$(cat "$SENTINEL" 2>/dev/null || echo 0)
  if [ $((NOW - LAST)) -lt 300 ]; then
    rm -f "$SENTINEL"
    exit 0
  fi
fi
echo "$NOW" > "$SENTINEL"

cat <<EOF >&2
【終わる前の確認】いま終わるのが**目標に対して**最善か、答えてから終わってください。

- 背後で走っているもの: ${RUNNING}
- 未コミットの変更: ${DIRTY}
- この回が出したもの: ${SHIP_STATE}（shipped ＝ 記録済み／unknown ＝ 定期の回ではない）

**これは「終わるな」ではありません。** 問うているのは
「終わるかどうか」ではなく**「終わるのが最善かを考えたか」**です。

**使用量は目標のためにあります。残すこと自体に価値はありません。**
予算を理由に作業を見送らないこと。ただし**速さは別の話**で、
先に使い切ると次の回が起きられません（\`docs/TRIGGER.md\`）。

天秤にかけるのはこの3つです。

1. **投稿の予約は切れていないか。** 切れそうなら、他を削ってでも生成に使う。
   投稿が途切れるのが最大の損失。\`python scripts/status.py\` の「予約が入っていない日」。
2. **判定を先送りしていないか。** 期限の来た前提（config/hypotheses.yaml）を
   放置して終わると、推測が推測のまま残る。
3. **自分で決めた条件を惰性で守っていないか**（\`docs/CONSTRAINTS.md\`）。
   与件は目標だけです。**数字がそれを覆したら変えてよい。**

終わると決めたなら、**未コミットの変更を push してから**終わること。
そのうえでもう一度終了すれば、この確認は通ります。
EOF

printf '{"decision":"block","reason":"上の確認に答えてから終わってください"}\n'
exit 0
