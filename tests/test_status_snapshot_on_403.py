"""日枠の 403 で `status.py` が落ちても、θ の計器だけは取りに行くこと。

## なぜ要るか（2026-08-31・最適化の回）

`scripts/snapshot.py` の冒頭は「`status.py` から毎回自動で呼ぶ。
**人が思い出す前提にしない**」と書いてあります。ところがその呼び出しは
`_channel_main` の中（動画の表を組む節）に在って、日枠が尽きると
`channels.list` が 403 →`ids` が空 →`RuntimeError` で**表ごと落ち、
`record()` まで届きません。**

実測 2026-08-31 05:1x:

    `data/views.jsonl` のいちばん新しい点  08-29 17:31 JST（**45時間 前**）
    08/30・08/31 に積まれた行              **0行**（08/06 以来はじめて2日 続けて0）
    その計器を数えている開いた前提          **3件**

到達日をいちばん大きく動かすのは θ（前提が閉じる速さ）なので、
**止まった計器のぶんだけ θ が低く出ます。**

`main()` の例外側で `snapshot.main()` を1回 試す形にしました。
**この節は「落ちたのは片方だけ」を3度 書き直しています**
（「チャンネル側の数字は出ません」＝嘘・「枠が戻るまで `upload` は
選べません」＝嘘・そしてこれ）。**4度目を黙って作らないため**に留めます。
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for _p in (str(ROOT), str(ROOT / "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

SRC = (ROOT / "scripts" / "status.py").read_text(encoding="utf-8")


def _fallback_body() -> str:
    """`main()` の `except` 節（外の口が落ちた側）の本文。"""
    i = SRC.index("def main(days: int = 7) -> int:")
    j = SRC.index("Data API（読みの側）が落ちました", i)
    k = SRC.index("\ndef ", j)
    return SRC[j:k]


def test_403の側でも_snapshot_を1回は試すこと():
    body = _fallback_body()
    assert re.search(r"import snapshot", body), (
        "日枠が閉じた回で `snapshot` を呼んでいません。"
        "`_channel_main` の中の `record(videos)` は、その回 道連れで落ちています —— "
        "`data/views.jsonl` が止まると θ がそのぶん低く出ます"
    )
    assert "_snap.main()" in body


def test_snapshotが落ちてもこの回を止めないこと():
    """**門を増やさないこと。** ここは「出せるものは出す」節です。"""
    body = _fallback_body()
    seg = body[body.index("import snapshot"):]
    assert "except Exception" in seg, "`snapshot` の失敗で status が落ちてはいけません"
    assert "raise" not in seg.split("=" * 66)[0]


def test_snapshotは手元の控えからidを取ること():
    """`videos.list` だけで済む＝ **上と別の呼び**であることの根拠。

    `channels.list` / `playlistItems.list` / `search` を使うなら、
    上が落ちた回はこちらも同じ理由で落ちるので、試す意味がありません。
    """
    snap = (ROOT / "scripts" / "snapshot.py").read_text(encoding="utf-8")
    assert "_ids_from_ledger" in snap
    assert "uploaded.jsonl" in snap
    for forbidden in ("channels().list", "playlistItems().list", "search().list"):
        assert forbidden not in snap, f"snapshot.py が {forbidden} を使っています"
