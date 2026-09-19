#!/bin/bash
# **長尺の焼きを「周」から切り離す runner**（2026-09-20 00:xx JST・optimizer・Opus 5・ultracode）
#
#     bash scripts/longform_chain.sh <id> [<id> ...]
#
# ## なぜ在るか（09/19 23:xx の周が「1周 に 3本 は入りません」と書いた当の所）
#
# 長尺 1本 の焼きは **30分 を越えます**（182コマ・`slide-*.png` 2,000枚超・実測）。
# 床は 98分 なので、前の周は「1周 に 1本、それも周の大半を食う」と書きました。
# **その読みは外れていました。** この周が `ps` で見たら、**前の周の焼きはまだ走っていました**
# （周が畳まれた 15分 後・ffmpeg の mux 段）。**焼きは周に紐付いていません。**
#
# ところが前の周の chain は、**2本目 で必ず死にます** —— 走らせた shell の `cd` 先が
# `\.claude/worktrees/agent-a002ab13dd0b4eaea`（**その周の worktree**）で、
# **worktree は周が畳まれると消されるから**です（この周が `ls` で確かめた ＝ 消えていた）。
# 1本目 が焼き上がるのは、python が**もう import を済ませていた**からで、
# 2本目 の `python -m studio.cli build` は cwd ごと無くなっています。
#
#   ＝ **焼きが周を越えられないのではなく、焼きを置いた場所が周と一緒に消えていた。**
#
# ## この道具が直していること（3つ）
#
#   1. **自分を本体の checkout へ写してから走る。** bash は台本を**少しずつ読む**ので、
#      走っている最中に台本が消えると途中で死にます。写し先は `work/` の下
#      （`work/` は `common._shared_root` で周をまたいで共有・`prune_work` は
#      **ディレクトリしか掃きません**のでこの 2つ のファイルは残ります）。
#   2. **`cd` は本体の checkout。** `studio/` は worktree と本体で同じ物でした
#      （この周が `md5sum` で全部 突き合わせた）。台帳（`common.LEDGER` ＝ `ROOT/data/studio`）も
#      本体の側に落ちます ＝ **親が押す checkout と同じ側**（worktree の台帳は周ごと消えます）。
#   3. **同時には焼かない。** CPU は 4個 で、ffmpeg 1本 が 340% 持っていきます
#      （前の周が焼きと `-m live` を重ねて、検査が 500秒 で落ちた当のもの）。
#      先に走っている焼きが在れば、**終わるまで待ってから**次を撃ちます。
#
# ## 覆る条件
#
#  (1) 1周に 2体 以上 立てる形へ戻したら、2体 が同じ id を同時に焼く道が開きます
#      （`common._shared_root` の覆る条件 (1) と同じ 1か所）。そのときは写し先に周の印を足すこと。
#  (2) worktree が畳まれなくなったら、写す段（1）は要りません。**`cd` の段（2）は残すこと** ——
#      台帳が周ごとに分かれる所は、worktree が残っても直りません。
#  (3) 焼きが 98分 の床より短くなったら（コマを減らす・`viz` を間引く）、この道具ごと畳んでよい。
#  (4) `python -m studio.cli build` の名前が変われば下の `pgrep` の字も変えること
#      （待ちが効かなくなると、同時に 2本 焼いて両方 遅くなります ＝ 落ちるのは速さだけ）。
set -u

self="$(readlink -f "$0")"
here="$(cd "$(dirname "$self")/.." && pwd)"

# 本体の checkout（`.claude/worktrees/<名>` の手前）＝ `studio/common._shared_root` と同じ規則。
case "$here" in
  */.claude/worktrees/*) ROOT="${here%%/.claude/worktrees/*}" ;;
  *)                     ROOT="$here" ;;
esac

STABLE="$ROOT/work/.longform_chain.sh"
LOG="$ROOT/work/_longform_chain.log"

if [ "$#" -eq 0 ]; then
  echo "使い方: bash scripts/longform_chain.sh <id> [<id> ...]" >&2
  exit 2
fi

# ---- 切り離す段（呼ばれた側が 1度だけ通る）----------------------------------
if [ "${CHAIN_DETACHED:-}" != "1" ]; then
  mkdir -p "$ROOT/work" || exit 1
  cp "$self" "$STABLE" || exit 1
  chmod +x "$STABLE"
  CHAIN_DETACHED=1 STUDIO_CHAIN_ROOT="$ROOT" \
    setsid nohup bash "$STABLE" "$@" >>"$LOG" 2>&1 < /dev/null &
  echo "切り離した: $STABLE"
  echo "  root : $ROOT"
  echo "  log  : $LOG"
  echo "  本   : $*"
  echo "  見る : tail -f $LOG  ／  cat \$ROOT/work/<id>/build.sig"
  exit 0
fi

# ---- 焼く段（写したほうが走る）----------------------------------------------
ROOT="${STUDIO_CHAIN_ROOT:-$ROOT}"
cd "$ROOT" || { echo "!! cd 失敗: $ROOT"; exit 1; }

echo "===== chain 開始 $(date -u +'%F %T') UTC  root=$ROOT  本=$* ====="

for v in "$@"; do
  # 先に走っている焼きが終わるのを待つ（自分の pid は数えない）。
  waited=0
  while pgrep -f "studio\.cli build" >/dev/null 2>&1 || pgrep -x ffmpeg >/dev/null 2>&1; do
    sleep 20
    waited=$((waited + 20))
    if [ "$((waited % 300))" -eq 0 ]; then
      echo "  ... 先の焼きを待っている（${waited}秒）"
    fi
  done

  # すでに台本と同じ指紋で焼けていれば撃たない（`cli.shippable_line` と同じ問い）。
  if python - "$v" <<'PY'
import sys
try:
    from studio import cli, render, script
    s = script.load(sys.argv[1])
    sys.exit(0 if render.built_sig(s.id) == s.build_sig(cli.image_for(s.id)) else 1)
except Exception:
    sys.exit(1)
PY
  then
    echo "===== $v $(date -u +'%T') ＝ もう焼けている（撃たない）====="
    continue
  fi

  echo "===== $v $(date -u +'%F %T') UTC 焼き始め ====="
  t0=$(date +%s)
  python -m studio.cli build "$v" 2>&1 | tail -14
  t1=$(date +%s)
  echo "----- $v  $((t1 - t0))秒  sig: $(cat "$ROOT/work/$v/build.sig" 2>/dev/null) -----"
done

echo "===== chain 終わり $(date -u +'%F %T') UTC ====="
