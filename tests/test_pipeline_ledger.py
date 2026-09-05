"""**`pipeline` で上げた本も、`data/uploaded.jsonl` に控えること**（2026-09-05 11:5x・サブの回）。

実測: `python -m src.pipeline --topic s-teikibin-todoita-kakyu-ni-nai --short` は投稿（`3gZ38lfsJpY`）も
`[queue]` の控えも通したのに、`data/uploaded.jsonl` には 1行も入らなかった —— `dupes.remember()` を呼ぶのは
`scripts/upload_only.py` だけだった。門（slot_gate・placed_at・sibling_check・upload_cap・forms）は
その控えでしか答えを出せないので、その本は**どの門からも見えない**。
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_pipeline_は投稿の後に_dupes_remember_を呼ぶ():
    src = (ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    stash = src.index("_cq.stash(")
    assert "_dupes.remember(" in src[stash:], "投稿後の段に `dupes.remember()` が無い（控えの穴）"
    # `upload_only.py` と同じ引数の形（公開予定時刻 ＋ 秒数）
    tail = src[src.index("_dupes.remember(", stash):]
    assert "duration_s=" in tail[:400]
    assert "publish_at" in tail[:400]
