#!/usr/bin/env bash
set -euo pipefail

if [[ ! -f AUTOMATION_PAUSED.md ]]; then
  exit 0
fi

cat <<'EOF'
<system-reminder>
CURRENT TACTIC IS HARD-PAUSED.

The automated synthetic persona for money/tax/career content conflicts with the current YouTube monetization policy for AI personas on sensitive topics. Do not generate, upload, schedule, retitle, re-thumbnail, link, or otherwise extend this tactic. Read AUTOMATION_PAUSED.md before acting.

Allowed: analytics, data preservation, policy-compliant replacement research.
Blocked: content generation and all channel-modifying entry points.
Do not ask the owner for permission to keep the old tactic running.
</system-reminder>
EOF
