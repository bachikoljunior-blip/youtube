"""Hard stop for the paused YouTube generation/upload tactic.

Analytics and repository inspection remain available. Content-changing entry points are
blocked while AUTOMATION_PAUSED.md exists, unless a deliberately explicit one-process
override is set.
"""
from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAUSE_FILE = ROOT / "AUTOMATION_PAUSED.md"
OVERRIDE_NAME = "ALLOW_POLICY_PAUSED_AUTOMATION"
OVERRIDE_VALUE = "I_ACCEPT_YPP_POLICY_RISK"

# Entry-point filenames that create, upload, schedule, or optimize the currently
# non-monetizable AI finance-persona tactic. Analysis-only tools are not listed.
BLOCKED_ENTRYPOINTS = {
    "pipeline.py",
    "uploader.py",
    "upload_only.py",
    "batch_build.py",
    "shorts_subs.py",
    "reschedule.py",
    "refresh_thumbnail.py",
    "retitle.py",
    "link_longform.py",
    "post_pending_comments.py",
}

MESSAGE = (
    "AUTOMATION PAUSED: the current synthetic finance/tax/career persona conflicts "
    "with YouTube's monetization policy for AI personas on sensitive topics. "
    "Generation, upload and channel-modification entry points are blocked. "
    "Read AUTOMATION_PAUSED.md."
)


# --- Why this is not keyed on the marker file alone -------------------------
# The first version of this guard opened as soon as AUTOMATION_PAUSED.md was
# missing. That fails OPEN: a single `rm` silently re-enables the whole tactic
# while every other part of the guard (hooks, CI, imports) stays in place and
# still looks armed. On 2026-08-31 that is exactly what happened — the marker
# was deleted and not one of the six resume conditions had been met.
#
# So the gate is keyed on the thing the policy actually cares about: what
# config/channel.yaml currently declares. The marker file still pauses on its
# own, but removing it is no longer sufficient. The gate opens when the
# configured channel stops tripping the conditions below — which is the same
# work the resume gate asks for, so a genuine fix opens it automatically and
# no separate ceremony is needed.

CHANNEL_FILE = ROOT / "config" / "channel.yaml"

# YouTube treats these as sensitive topics; an AI persona presenting itself as
# a human expert on them is not monetizable.
SENSITIVE_TOPIC_MARKERS = (
    "お金", "税金", "税", "金融", "投資", "資産", "年金", "保険",
    "法律", "法務", "労基", "制度", "キャリア", "転職", "給与", "医療", "健康",
)

# Phrases by which the configured persona claims lived human professional
# experience. This is the "presenting as a human expert" half of the rule.
HUMAN_EXPERT_MARKERS = (
    "元・", "元事業会社", "実務で回してきた", "立場から解説",
    "経理", "人事", "税理士", "社労士", "弁護士", "専門家として",
    "私が担当", "現役", "経験から",
)


def _channel_text() -> str:
    """Raw text of the channel config. Read as text on purpose: this must work
    even if the YAML is malformed, and it must not import src.config (which
    imports this module)."""
    try:
        return CHANNEL_FILE.read_text(encoding="utf-8")
    except OSError:
        # Cannot read the config -> cannot prove the tactic is compliant.
        return ""


def _persona_block(text: str) -> str:
    """The persona: block plus the niche/audience lines around it."""
    keep = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        keep.append(line)
    return "\n".join(keep)


def config_trips_policy() -> tuple[bool, str]:
    """True when config/channel.yaml still describes the non-monetizable tactic:
    an AI/synthetic-voice persona claiming human professional standing on a
    sensitive topic. Returns (tripped, human-readable reason)."""
    text = _persona_block(_channel_text())
    if not text.strip():
        return True, "config/channel.yaml is unreadable or empty — compliance cannot be shown"

    topic_hits = sorted({m for m in SENSITIVE_TOPIC_MARKERS if m in text})
    expert_hits = sorted({m for m in HUMAN_EXPERT_MARKERS if m in text})

    if topic_hits and expert_hits:
        return True, (
            "config/channel.yaml still declares a persona claiming human professional "
            f"standing ({', '.join(expert_hits)}) on sensitive topics "
            f"({', '.join(topic_hits)}). Narration is synthetic and production is an "
            "automated template pipeline, so this is the exact combination YouTube "
            "lists as non-monetizable."
        )
    return False, ""


def is_paused() -> bool:
    if PAUSE_FILE.is_file():
        return True
    tripped, _ = config_trips_policy()
    return tripped


def pause_reason() -> str:
    """Why the gate is closed right now, for messages and tooling."""
    tripped, why = config_trips_policy()
    if tripped:
        return why
    if PAUSE_FILE.is_file():
        return f"{PAUSE_FILE.name} is present"
    return ""


def override_enabled() -> bool:
    return os.environ.get(OVERRIDE_NAME, "") == OVERRIDE_VALUE


def _raise_if_blocked(names: set[str]) -> None:
    if not is_paused() or override_enabled():
        return
    if names & BLOCKED_ENTRYPOINTS:
        reason = pause_reason()
        raise RuntimeError(f"{MESSAGE} Reason: {reason}" if reason else MESSAGE)


def enforce_current_process() -> None:
    """Block known content-changing command entry points as early as possible."""
    _raise_if_blocked({Path(sys.argv[0]).name})


def enforce_call_stack() -> None:
    """Catch indirect imports/calls that bypass the normal command entry point."""
    names = {Path(frame.filename).name for frame in inspect.stack(context=0)}
    _raise_if_blocked(names)
