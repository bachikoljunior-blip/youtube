#!/bin/sh
# `pytest tests/ -q`（`-x` 無しの通し）の結果を、周が終わっても残る所へ写す。
# **scratchpad は周と一緒に消えます** —— 次の周が読むのは `work/_full_suite.log`。
# **待ちは pid で見ます**（`pgrep -f <字>` は自分自身の cmdline に当たる ＝
# 2026-09-19 17:38 の待ちが 37分 抜けなかった形・JOURNAL 09/20 §10）。
SRC="$1"
PID="$2"
DST=$(python -c 'from studio.common import WORK; print(WORK / "_full_suite.log")')
[ -n "$SRC" ] && [ -n "$PID" ] || exit 2
while [ -d "/proc/$PID" ]; do sleep 20; done
sleep 2
[ -f "$SRC" ] && cp "$SRC" "$DST"
