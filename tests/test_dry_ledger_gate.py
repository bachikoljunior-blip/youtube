"""**台帳が空の日の免除が、きょうの枠の本に絞られているか。**

## なぜ要るか（2026-09-04 19:xx・最適化の回）

`judgeable_today()` が 0件 の日、`fix` の門は**どんな `fix` でも通し**ていました。
免除の理由は「止めても残るのは**歩留り 0.0% の `improve``」ですが、`improve` の
`moves` は `MOVING_KINDS` の註のとおり **定義上 0** です。
**定義で 0 にした数を、腕を捨てる根拠に使っていた** —— そこを絞ります。

この検査が守るのは3つ:

1. **止める**: 台帳が空・枠の本が名乗れる・その本を名乗っていない `fix`。
2. **止めない**: 枠の本を名乗った `fix`（規則3。**門が自分の出口を塞がないこと**）。
3. **止めない**: 測れなかった（`ready is None`）／枠の本が名乗れない／
   きょう撃てる `verdict` が在る日（そちらの門が立つ）。

**覆る条件**: `improve` の `moves` が 0 以外を出しはじめたら、上の理由が消えます。
そのときは `dry_ledger_gate()` の註ごと書き直すこと（この検査も一緒に）。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from run_marker import dry_ledger_gate  # noqa: E402

SLOT = {"video_id": "XwB8nxtN5D8", "topic": "nenkin-uketorikata-65-70-75-handan"}


def test_台帳が空の日に計器だけを直す_fix_は止まる():
    r = dry_ledger_gate("fix: eta.py の印字がずれていた", [], SLOT, over=True)
    assert r["dry"] is True
    assert r["slot_fix"] is False
    assert r["trip"] is True
    assert r["target"] == "XwB8nxtN5D8"


def test_枠の本を名乗った_fix_は通る():
    r = dry_ledger_gate(
        "fix: XwB8nxtN5D8 の冒頭2文を、前提を先・数字を後へ割った", [], SLOT, over=True)
    assert r["slot_fix"] is True
    assert r["trip"] is False


def test_題材で名乗っても通る():
    r = dry_ledger_gate(
        "improve: nenkin-uketorikata-65-70-75-handan の章頭を書き直した",
        [], SLOT, over=True)
    assert r["slot_fix"] is True
    assert r["trip"] is False


def test_測れなかった日は立てない():
    """**「測れない」を「立っている」と読ませないこと。**"""
    r = dry_ledger_gate("fix: eta.py", None, SLOT, over=True)
    assert r["dry"] is False
    assert r["trip"] is False


def test_きょう撃てる_verdict_が在る日は立てない():
    """その日は `judgeable_today()` の側の門が立ちます（二重に止めない）。"""
    r = dry_ledger_gate("fix: eta.py", ["その天井は天井ではない"], SLOT, over=True)
    assert r["dry"] is False
    assert r["trip"] is False


def test_枠の本が名乗れない日は免除のまま():
    """名指しできる行き先が無い門は、遅れと言い換えを作るだけです。"""
    r = dry_ledger_gate("fix: eta.py", [], {"video_id": "", "topic": ""}, over=True)
    assert r["dry"] is True
    assert r["can_name"] is False
    assert r["trip"] is False


def test_連が上限に届いていない回は立てない():
    r = dry_ledger_gate("fix: eta.py", [], SLOT, over=False)
    assert r["dry"] is False
    assert r["trip"] is False


def test_出口が実際に在ること():
    """**詰まないことの検査。** 止まった回が、その場で通せる手を持っているか。

    止められた `--ship` に枠の本の名前を足すだけで通る —— これが在るかぎり、
    この門は「撃てない `verdict` を要求する門」にはなりません。
    """
    blocked = "fix: eta.py の印字がずれていた"
    assert dry_ledger_gate(blocked, [], SLOT, over=True)["trip"] is True
    assert dry_ledger_gate(
        blocked + "（枠の本 XwB8nxtN5D8 の側）", [], SLOT, over=True)["trip"] is False
