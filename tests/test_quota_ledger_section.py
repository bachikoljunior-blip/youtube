"""**消費の帳面は、畳まれる警告の中に置かないこと**（2026-09-01 に踏んだ）。

`scripts/status.py` は 2026-08-31 に `src/quota_ledger.render()` の呼び出しを
足しました。**置いた場所が `_print_missing_thumbnails()` の本体の中**で、
しかも `if _r.folded: return` の**後ろ**でした。あの警告は
**101回 続けて鳴って手が打たれていない**ので畳まれています。つまり

    足した日から、消費の帳面は **1度も印字されていません**
    （見つけ方: `python scripts/status.py | grep 何が消費したか` → **0件**）

**呼び出しは在る。検査も通る。出力に無い。**
この repo でいちばん多い壊れ方（言っている所と、している所が別）の、
いちばん静かな形です。

**値打ちの実測**: 2026-09-01 の回は「枠が尽きた回に何を直すか」を探すのに
1周の4割を使い、答えはこの帳面の1行が持っていました ——
`history.py:channel_video_ids` が **3,409単位**（枠 10,000 の **34%**）。
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import status  # noqa: E402


def test_the_ledger_has_a_section_of_its_own():
    """**独立した関数**であること（畳める警告の身内にしない）。"""
    assert callable(status.print_quota_ledger)


def test_the_ledger_is_not_printed_from_inside_a_foldable_alert():
    """**畳まれる警告の本体から呼ばないこと。** ここが 101周ぶんの空振りの正体。"""
    for name in ("_print_missing_thumbnails", "_print_collisions"):
        src = inspect.getsource(getattr(status, name))
        assert "quota_ledger" not in src, (
            f"{name}() は `_alerts.ring(...).folded` で早期 return します。"
            " 帳面をこの中に置くと、畳まれた窓では1行も出ません")


def test_the_ledger_section_is_actually_called():
    """**呼ばれていること。** 関数を作っただけの回を通さない。"""
    src = inspect.getsource(status._print_inventory_from_ledger)
    assert "print_quota_ledger()" in src


def test_the_ledger_section_is_timed_like_the_others():
    """節ごとの時計に載っていること（`(a2) 問い1` を推測で答えないため）。"""
    names = [n for n, _ in status._SECTION_TIMERS] if hasattr(
        status, "_SECTION_TIMERS") else None
    if names is None:                       # 一覧が名前を変えたら、字面で見る
        src = Path(status.__file__).read_text(encoding="utf-8")
        assert '("print_quota_ledger", ' in src
    else:
        assert "print_quota_ledger" in names
