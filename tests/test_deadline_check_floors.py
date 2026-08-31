"""**題材の床は、`deadline_check` の隣に並べる**（2026-08-29 13:4x・定期の回）

## なぜ

08/29 12:0x の申し送りの3番（原文）:

> 開いた前提の「床にあと何本 足りないか」を、一覧で出す道具が要ります。
> いまは `status.py` の `pick()` が**副産物として1件だけ**出すので、
> **在庫の節を読んだ回しか気づけません。** この回の `s-ribo-` は
> 公開 0本 / 床 8本 で、気づかなければ 09-19 に「外れ」と出ていました。

**物は既に在りました** —— `src/floor_topics.lines()` は全行を返し、docstring も
「`batch_build` と `deadline_check` が同じ字を出すため」と書いています。
**`deadline_check` からは一度も呼ばれておらず**、`batch_build` は
`lines([r])[0]`（1件だけ）で呼んでいました。**足りなかったのは呼び口です。**

## 既知の当たり

- **書き戻し（`--shrink` / `--extend` / `--fit`）には掛けないこと。**
  題材の床は `falsified_if` の外（「その本を誰かが作るか」）なので、
  混ぜると**作られていない床を理由に期限が動きます。**
- **`lines()` を1件に絞らないこと**（それが元の欠陥そのもの）。

## 覆る条件

`pick()` が床を全件ぶん先頭へ寄せるようになったら、この検査は
「まだ埋まっていない床の確認」に縮みます。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import deadline_check  # noqa: E402
from src import floor_topics  # noqa: E402


def test_床の一覧が_deadline_check_から出る():
    assert hasattr(deadline_check, "_print_starved_floors")
    src = (ROOT / "scripts" / "deadline_check.py").read_text(encoding="utf-8")
    assert "_print_starved_floors()" in src.split("def _print_starved_floors")[1], (
        "定義しただけで、どこからも呼ばれていません"
    )


def test_書き戻しの枝には掛けないこと():
    """`--shrink` / `--extend` / `--fit` の枝は、床を読まずに `return 0` すること。

    **題材の床は `falsified_if` の外**です。書き戻しの判断に混ぜると、
    「まだ誰も作っていない」ことを理由に期限が動きます。
    """
    src = (ROOT / "scripts" / "deadline_check.py").read_text(encoding="utf-8")
    body = src.split("def main(")[1]
    head, _, tail = body.partition("vs = check(load()")
    assert "_print_starved_floors" not in head, (
        "書き戻し（--shrink/--extend/--fit）の枝から床を読んでいます。"
        " **期限は、作られていない床を理由に動かしてはいけません**"
    )
    assert "_print_starved_floors()" in tail


def test_lines_は全件を返す():
    """1件に絞らないこと（`batch_build` の `lines([r])[0]` が元の欠陥）。"""
    rows = [
        {"prefix": "s-tests-a-", "need": 8, "built": 2, "short": 6, "stock": 6,
         "deadline": "2026-12-31", "lever": "rpm"},
        {"prefix": "s-tests-b-", "need": 8, "built": 0, "short": 8, "stock": 0,
         "deadline": "2026-12-31", "lever": "per_video"},
    ]
    out = floor_topics.lines(rows)
    assert len(out) == 2
    assert "s-tests-a-" in out[0] and "作るだけで埋まります" in out[0]
    assert "s-tests-b-" in out[1] and "在庫が0件" in out[1]
