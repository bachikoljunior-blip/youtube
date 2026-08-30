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


def is_paused() -> bool:
    return PAUSE_FILE.is_file()


def override_enabled() -> bool:
    return os.environ.get(OVERRIDE_NAME, "") == OVERRIDE_VALUE


def _raise_if_blocked(names: set[str]) -> None:
    if not is_paused() or override_enabled():
        return
    if names & BLOCKED_ENTRYPOINTS:
        raise RuntimeError(MESSAGE)


def enforce_current_process() -> None:
    """Block known content-changing command entry points as early as possible."""
    _raise_if_blocked({Path(sys.argv[0]).name})


def enforce_call_stack() -> None:
    """Catch indirect imports/calls that bypass the normal command entry point."""
    names = {Path(frame.filename).name for frame in inspect.stack(context=0)}
    _raise_if_blocked(names)
