#!/bin/sh
# `pytest tests/ -q`（`-x` 無しの通し）の結果を、周が終わっても残る所へ写す。
# **scratchpad は周と一緒に消えます** —— 次の周が読むのは `work/_full_suite.log`。
# **待ちは pid で見ます**（`pgrep -f <字>` は自分自身の cmdline に当たる ＝
# 2026-09-19 17:38 の待ちが 37分 抜けなかった形・JOURNAL 09/20 §10）。
#
# **2026-09-20 05:xx に足した「効いたか」の 3行**（optimizer・Opus 5・ultracode）——
# 09/19 の通しは **`1240 failed, 8444 passed`** で終わり、`tail -3` はその字を見せました。
# **そのうち 1件 も本物ではありません**: 走っている最中に**親がその worktree を掃き**
# （4,461 file → 6 file）、import が `FileNotFoundError` で落ちただけです
# （同じ 3 file をこの周の worktree で撃ち直すと **350 passed / 12秒**）。
# **申し送りの「最後が `N passed` の形なら、それが答え」は、この形を素通しします** ——
# 終わりの字は**ちゃんと終わった形**をしていて、中身が空だからです。
# そこで、**写したあとに「走った木がまだ在るか」を数えて末尾に足します**。
# `tail -3` が見るのはこの行なので、**次の周は数を読む前に無効を知れます**。
SRC="$1"
PID="$2"
DST=$(python -c 'from studio.common import WORK; print(WORK / "_full_suite.log")')
[ -n "$SRC" ] && [ -n "$PID" ] || exit 2
# 走り出しの木（`SRC` が置かれている worktree の根）と、そのときの file 数
ROOT=$(cd "$(dirname "$SRC")" 2>/dev/null && git rev-parse --show-toplevel 2>/dev/null)
[ -n "$ROOT" ] || ROOT=$(pwd)
N0=$(find "$ROOT" -type f -not -path '*/.git/*' 2>/dev/null | wc -l)
while [ -d "/proc/$PID" ]; do sleep 20; done
sleep 2
[ -f "$SRC" ] || exit 0
cp "$SRC" "$DST"
N1=$(find "$ROOT" -type f -not -path '*/.git/*' 2>/dev/null | wc -l)
{
  echo ""
  echo "--- 走った木（この行は scripts/keep_full_suite_log.sh が足しました）---"
  echo "root: $ROOT"
  echo "file: 走り出し $N0 → 終わり $N1"
  # 木が痩せていたら（掃かれた）、上の数は**読まないこと**
  if [ "$N1" -lt $((N0 / 2)) ]; then
    echo "!! **この通しの数は無効です** —— 走っている最中に木が掃かれました"
    echo "!! （$N0 → $N1 file）。失敗は import が落ちただけで、**repo の壊れではありません**。"
    echo "!! **数を読まないこと。** 通しが要るなら、この周の worktree で撃ち直すこと。"
  else
    echo "OK: 木は最後まで在りました ＝ **上の数はこの通しの答えです**"
  fi
} >> "$DST"
