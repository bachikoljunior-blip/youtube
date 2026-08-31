#!/usr/bin/env bash
# **停止中の差し込み。判定はここに持ちません**（2026-08-31）。
#
# 2026-08-30 まで、この script は `[[ -f AUTOMATION_PAUSED.md ]]` を**独立に**
# 見ていました。`src/pause_guard` も `src/resume_gate` も `scripts/spawn_prompt.py`
# も、それぞれ別に同じファイルを見ていました。**同じ問いに4つの答え**です ——
# 片方だけ直した回が「**動いているのに、読んだ側は全員 停止中だと思い込む**」
# 形を作れます。ここはフックなので、いちばん強く効きます。
#
# いまは `src/pause_guard.is_paused()` に聞きます（判定は1か所）。
# **読めなかったときは「止まっていない」側に倒します** —— 機械が自分の都合
# （python が無い・import が壊れた）で自分を止められないようにするためです。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PY="${PYTHON:-python3}"
command -v "$PY" >/dev/null 2>&1 || PY=python
command -v "$PY" >/dev/null 2>&1 || exit 0

if ! "$PY" - "$ROOT" <<'PY' 2>/dev/null; then
import importlib.util
import sys
from pathlib import Path

root = Path(sys.argv[1])
spec = importlib.util.spec_from_file_location("_pause_guard", root / "src" / "pause_guard.py")
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)
sys.exit(0 if guard.is_paused() else 1)
PY
  exit 0
fi

cat <<'EOF'
<system-reminder>
THE OWNER HAS PAUSED THIS REPOSITORY BY HAND.

The marker file `.owner-pause` is present in the repository root. No code in this
repository creates it - only a human places it. Generation, upload, scheduling,
retitling, re-thumbnailing and every other channel-modifying entry point is blocked
(`src/pause_guard.BLOCKED_ENTRYPOINTS`).

Allowed: analytics, data preservation, research, and repository work that does not
modify the channel.

Do NOT remove `.owner-pause` and do NOT set ALLOW_POLICY_PAUSED_AUTOMATION to work
around it. Ask the owner. If a defect in this repository is what made you want to
pause, fix the defect - do not add a way for the machine to stop itself.
</system-reminder>
EOF
