"""**止める名前は、実際に止まること。読むだけの道具は、載っていないこと。**

（2026-08-30・最適化の回。**踏んでから足しました**）

## なぜ要るか

`src/pause_guard.BLOCKED_ENTRYPOINTS` は**ファイル名の集合**で、
`enforce_current_process()` が `sys.argv[0]` の名前と突き合わせます。
**この仕掛けは、そのプロセスが `src` を import して初めて走ります。**

だから、**`src` を1つも import しない script を載せると、こうなります**:

    載っている        → 読む側は「止まっている」と思う
    実際は動く        → `python scripts/<それ>.py` は最後まで走り、API も叩く
    **ただし**        → その script の中から `src` の何かを import した瞬間、
                        **そこだけが RuntimeError で落ちる**

2026-08-30 に `scripts/shorts_subs.py` でこれを踏みました。
`from src import day_cap` を足したところ、**例外が握りつぶされて `cap=None`**、
**「天井で解き直す」の節が丸ごと消えたまま、残りの表がふつうに出ました。**
**止めるでも通すでもなく、報告に穴が開く** —— いちばん悪い形です。

## この検査が縛る2つ

1. **載っている名前は、その script を走らせたときに実際に止まること**
   （＝ `src` を import する経路を持っていること）
2. **読むだけの道具は載っていないこと**（`BLOCKED_ENTRYPOINTS` のすぐ上の
   コメント「Analysis-only tools are not listed」と、`AUTOMATION_PAUSED.md` の
   "What remains allowed" が、そう言っています）

## 覆る条件

停止が明けたら（`AUTOMATION_PAUSED.md` が消えたら）この集合は誰も見ません。
そのときこの検査は「名前が実在すること」だけを言う検査に落ちます —— 消してよい。
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from src import pause_guard

ROOT = Path(__file__).resolve().parent.parent

#: **チャンネルに書き込まない道具**。ここに載っているものが
#: `BLOCKED_ENTRYPOINTS` に混ざったら、測定が黙って止まります。
READ_ONLY_TOOLS = {
    "shorts_subs.py",   # Analytics を読んで表を出すだけ（2026-08-30 に外した）
    "eta.py",
    "status.py",
    "reach.py",
    "retention.py",
    "snapshot.py",
    "audit.py",
    "drift.py",
    "queue_lag.py",
}


def _find(name: str) -> Path | None:
    for base in (ROOT / "scripts", ROOT / "src"):
        p = base / name
        if p.is_file():
            return p
    return None


def test_read_only_tools_are_not_blocked():
    """**読むだけの道具を止めると、止まらずに『穴の開いた報告』が出ます。**"""
    overlap = READ_ONLY_TOOLS & pause_guard.BLOCKED_ENTRYPOINTS
    assert not overlap, (
        f"チャンネルに書き込まない道具が止められています: {sorted(overlap)}。"
        " `BLOCKED_ENTRYPOINTS` のすぐ上の行が「Analysis-only tools are not listed」"
        "と言っています。止める理由があるなら、その行のほうを直すこと。")


@pytest.mark.parametrize("name", sorted(pause_guard.BLOCKED_ENTRYPOINTS))
def test_every_blocked_name_actually_stops(name):
    """**載っているだけで止まらない名前を残さないこと。**

    止まる条件は「そのプロセスが `src` を import すること」です
    （`src/__init__.py` が `enforce_current_process()` を呼びます）。
    `src` を一度も import しない script は、**名前が載っていても動きます。**
    """
    p = _find(name)
    assert p is not None, f"{name} が repo に見あたりません（消えた名前が残っている）"
    body = p.read_text(encoding="utf-8")
    # `src/` の下のものは、それ自体が `src` パッケージなので必ず通ります。
    if p.parent.name == "src":
        return
    imports_src = re.search(r"^\s*(from\s+src[\s.]|import\s+src\b)", body, re.M)
    calls_guard = "pause_guard" in body
    assert imports_src or calls_guard, (
        f"{name} は `BLOCKED_ENTRYPOINTS` に載っていますが、`src` を import せず"
        f" `pause_guard` も呼んでいません ＝ **止まりません。**"
        f" 止めたいなら import を足すこと。止めなくてよいなら名前を外すこと。"
        f"（載っているのに動く状態がいちばん悪い）")
