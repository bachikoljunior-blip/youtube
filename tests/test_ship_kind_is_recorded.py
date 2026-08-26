"""**ship の種別を、書く側が残すこと。**（2026-08-26・最適化の回）

## なぜ

`scripts/drift.py` の `_kind_of()` は `what` の**先頭の語だけ**を見ていて、
その docstring は「**欄を足すのが本筋ですが、既存の240件を読めなくなる**ので」と
書いて、頭の語のほうを選んでいました。**その理由は当たっていません** ——
欄を足しても、欄の無い古い行は頭の語で読めばよいだけです。

**代償は実測できます**（2026-08-26 18:5x）: **ship 381件 のうち 155件（41%）が「その他」。**
中身は「その他」ではありません ——「長尺1本を 09/07 20:00 JST に予約」（`upload`）、
「M9（配信の上限は…）を実データで判定」（`verdict`）が同じ袋に入っています。

**そしてこの数は門に乗っています**: `drifting = bool(od_now) and verdicts_tail == 0`。
**4割こぼす目盛りの上で、漂流かどうかを決めていました。**

## 覆る条件

`data/runs.jsonl` の「その他」が 5% を下回ったら（＝頭の語の慣習が守られている）、
この欄は要りません。そのとき `_kind_of_rec()` を消し、この検査も消すこと。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import drift  # noqa: E402
import run_marker  # noqa: E402


def test_明示した種別がそのまま残る() -> None:
    assert run_marker.ship_kind_of("M9 を実データで判定", "verdict") == "verdict"


def test_省いたら頭の語から読む() -> None:
    assert run_marker.ship_kind_of("upload: 長尺1本を予約") == "upload"
    assert run_marker.ship_kind_of("fix: なにかを直した") == "fix"


def test_どちらでも読めないものは_その他_になる() -> None:
    """**黙って `fix` などに寄せないこと。** 読めないことが見えるほうが速い。"""
    assert run_marker.ship_kind_of("長尺1本を 09/07 20:00 JST に予約") == "その他"


def test_drift_は欄を先に読み_古い行は頭の語で読む() -> None:
    # 欄がある行 —— `what` の頭と食い違っていても、**欄が勝つ**
    assert drift._kind_of_rec({"what": "M9 を判定", "ship_kind": "verdict"}) == "verdict"
    # 欄が無い古い行 —— 頭の語で読む（**過去の行が読めなくなっていないこと**）
    assert drift._kind_of_rec({"what": "fix: 古い行"}) == "fix"
    assert drift._kind_of_rec({"what": "頭の語が無い古い行"}) == "その他"
    # 壊れた欄は無視して `what` へ落ちる
    assert drift._kind_of_rec({"what": "fix: x", "ship_kind": 7}) == "fix"


def test_2つの並びが同じ() -> None:
    """**片方だけ変えると、書いた種別を読む側が知らない、が起きます。**"""
    assert tuple(run_marker.SHIP_KINDS) == tuple(drift.KINDS)
