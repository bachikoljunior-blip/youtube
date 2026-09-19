#!/bin/sh
# 葬祭費・埋葬料シリーズ（09/24 の 6本）を、周から切り離して順に焼く。
# **重い物を 2つ 同時に走らせないこと**（前の周の申し送り 1.）——
# `_longform_chain` は 2026-09-19 17:49:31 UTC に終わっています。
# 読むのは `tail work/_sousaihi_chain.log`。**重ねて撃たないこと。**
cd /home/user/youtube/.claude/worktrees/agent-a8ef10048051845ee || exit 1
# **`work/` は worktree ごとではなく共有の checkout に在ります**（`studio/common.WORK` ＝
# `_shared_root(ROOT)/work`）。worktree の相対パスで書くと、鎖は始まる前に落ちます
# （2026-09-20 03:xx にここで 1度 落ちた ＝ exit 2）。
LOG=$(python -c 'from studio.common import WORK; print(WORK / "_sousaihi_chain.log")')
echo "===== sousaihi chain 始め $(date -u '+%Y-%m-%d %H:%M:%S UTC') =====" >> "$LOG"
for id in 2026-09-24-sousaihi-kouki-short \
          2026-09-24-sousaihi-kokuho-short \
          2026-09-24-maisouryou-honnin-short \
          2026-09-24-maisouryou-kazoku-short \
          2026-09-24-maisouryou-taishoku-3kagetsu-short \
          2026-09-24-maisouhi-jippi-short; do
  echo "===== $id $(date -u '+%Y-%m-%d %H:%M:%S UTC') 焼き始め =====" >> "$LOG"
  python -m studio.cli build "$id" >> "$LOG" 2>&1
done
echo "===== sousaihi chain 終わり $(date -u '+%Y-%m-%d %H:%M:%S UTC') =====" >> "$LOG"
