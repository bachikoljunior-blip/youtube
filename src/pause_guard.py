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
#
# **2026-08-30: `shorts_subs.py` を外しました（最適化の回）。** 理由は3つ、
# **どれもこのファイル自身と `AUTOMATION_PAUSED.md` が言っていること**です:
#
#   1. **すぐ上の1行**が「Analysis-only tools are not listed」と言っています。
#      `scripts/shorts_subs.py` は Analytics を読んで表を出すだけで、
#      生成も投稿も予約も改題もしません（チャンネルへの書き込みが1つも無い）
#   2. `AUTOMATION_PAUSED.md` の "What remains allowed" が
#      「analytics/status/reach/retention の読取」「dry analysis that does not
#      generate, upload, schedule, retitle or otherwise modify channel content」
#      と書いています。**この道具はその中にあります**
#   3. **載っていても、止まっていませんでした。** `shorts_subs.py` は `src` を
#      1つも import していなかったので、`enforce_current_process()` が
#      走る機会がありません —— **`python scripts/shorts_subs.py` は最後まで動き、
#      API も叩きます。** 効いていたのは1つだけで、**この道具の中から
#      `src` の何かを import した瞬間に、そこだけが黙って失敗する**ことでした
#      （2026-08-30 に踏んだ: `day_cap.cap()` が `None` になり、
#      **天井の節が丸ごと消えたまま**、残りの表がふつうに出ました）。
#      **止めるでも通すでもなく、報告に穴が開く**のがいちばん悪い形です。
#
# **覆る条件**: この道具に、チャンネルを書き換える口が1つでも生えたら戻すこと。
# 検査は `tests/test_pause_guard_list.py`（**載っている名前は実際に止まること**・
# **読むだけの道具は載っていないこと**）。
BLOCKED_ENTRYPOINTS = {
    "pipeline.py",
    "uploader.py",
    "upload_only.py",
    "batch_build.py",
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
