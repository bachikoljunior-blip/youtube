"""**止まるかどうかを決める、ただ1か所。**（`is_paused()`）

**2026-08-31: 機械は、自分で自分を止められません。** オーナー直接指示です。

    > **「だから俺はそんなの決めてないから、勝手にそれで止まるのなし。
    >    今後そういうことがないようにして」**
    > **「既存のもの外すだけじゃなくて同じことが起こらないようにして」**

**何が起きたか（事実だけ）**: 2026-08-30、`AUTOMATION_PAUSED.md` という
**ファイル1枚**が置かれ、生成・投稿・予約の変更が全部 止まりました。
**約22時間・4周ぶんの生成が落ちています。** 2026-08-31、オーナー本人が
GitHub の画面からそのファイルを削除しました（commit `1aa1e65a`）。

**穴はどこだったか**: 判定が `PAUSE_FILE.is_file()` **だけ**でした。
**その1枚は、この repo のどの回でも書けます。** つまり機械が、自分の判断で
自分を丸ごと止められる状態でした。**それが「勝手に止まる」ことそのもの**です。

**いま何が要るか**: 止まるのは `OWNER_PAUSE_MARKER`（`.owner-pause`）が
在るときだけです。**この印を作るコードは、この repo に1行もありません**
（足せば、それは「勝手に止まる」の再発です。`tests/test_pause_needs_owner.py`
 が、印を作る書き込みが repo に無いことを検査しています）。

**なぜ「文書 AND 印」ではなく「印だけ」にしたか**（下書きからの意図的な変更）:
下書きは `PAUSE_FILE.is_file() and OWNER_PAUSE_MARKER.exists()` でした。
それだと**オーナーが `.owner-pause` を手で置いても、何も止まりません** ——
`AUTOMATION_PAUSED.md` はもう存在しないからです。**オーナーの「止めろ」が
黙って空振りする形**は、今回いちばん作ってはいけないものです。
文書を判定から**完全に外す**ほうが、「1枚では止まらない」より強い床です
（1枚あっても止まらない、ではなく、**その1枚はもう switch ではない**）。

`PAUSE_FILE` は**理由を書いた文書の置き場所**として残します（`src/resume_gate`
が Resume gate の本文をここから読みます）。**switch ではありません。**

**覆る条件**: オーナーが「止めろ」と言ったとき。そのときは `.owner-pause` を
**人の手で**置くこと（GitHub の画面から足せます）。**機械が置いてはいけません。**

止めている中身（何を止めるかの一覧 = `BLOCKED_ENTRYPOINTS`）は**残してあります**。
外したのは「機械が自分で全部を止められる」経路だけです。
"""
from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: **止める印。人の手でしか置きません。**
#:
#: この repo のコードは、このファイルを**作りません・触りません**。
#: 検査: `tests/test_pause_needs_owner.py::test_この印を作るコードが repo に無い`。
#: **`.gitignore` に入れないこと** —— オーナーは GitHub の画面から repo を
#: 触ります（08/31 の削除も画面からでした）。無視されると、置いても届きません。
OWNER_PAUSE_MARKER = ROOT / ".owner-pause"

#: **理由を書く文書の置き場所。switch ではありません**（上の註）。
#: 2026-08-31 時点で、このファイルは存在しません（オーナーが削除）。
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
    "AUTOMATION PAUSED BY THE OWNER: the marker file `.owner-pause` is present. "
    "Only a human places it - no code in this repository creates it. "
    "Generation, upload and channel-modification entry points are blocked. "
    "Read AUTOMATION_PAUSED.md if it exists, and ask the owner before removing "
    "the marker."
)


def is_paused() -> bool:
    """**止まるかどうかの判定は、ここ1つだけです。**

    他の場所で `.owner-pause` や `AUTOMATION_PAUSED.md` の有無を**独立に**
    見ないこと。2026-08-31 まで `src/resume_gate`・`scripts/policy_pause.sh`・
    `scripts/spawn_prompt.py` が別々に見ていて、**片方だけ直した回が
    「動いているのに停止中と印字する」形**を作れました。
    """
    return OWNER_PAUSE_MARKER.exists()


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
