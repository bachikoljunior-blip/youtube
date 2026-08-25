"""**`--long` は、選ぶ側にも効くこと**を固定する（2026-08-26 に踏んだ）。

`scripts/batch_build.py --long` は長らく `build_one(topic, long_form)` にしか
`--long` を渡しておらず、**題は在庫の上から取っていました。**
在庫はショート向け（`s-` で始まる id）が圧倒的多数なので、
**`--long` を付けても、ほぼ確実にショート向けの題で長尺を作ります。**

実測（2026-08-26 01:5x）: 長尺向けの題を7件足した直後の `--count 1 --long` が
`s-zangyo-nenkan-kyujitsu-tanka` を取り、5.4分の長尺として投稿しました。
**落ちも警告も出ません** —— ショート向けの細い表が尺に引き伸ばされるだけで、
外からは成功に見えます。だから**検査でしか気づけません。**

ここで固定するのは3つ:

1. `--long` のときは `s-` の題を取らない
2. **長尺向けが在庫に無い回は、止めずにショート向けを取る**
   （投稿が途切れるのが最大の損失。`CLAUDE.md`）
3. 既定（ショート）のときは、今までどおり両方から取る
"""
from __future__ import annotations

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from scripts import batch_build  # noqa: E402


def _topics(*ids: str) -> dict:
    return {"topics": [{"id": i, "calc": i.split("-")[-1], "score": 1.0,
                        "calc_sections": [f"節 {i}"]} for i in ids]}


def _stub(monkeypatch, *ids: str) -> None:
    from src import config

    monkeypatch.setattr(config, "load_topics", lambda: _topics(*ids))
    monkeypatch.setattr(batch_build, "_posted_including_ledger", lambda: set())
    monkeypatch.setattr(batch_build, "_drop_doomed", lambda u, p: u)
    monkeypatch.setattr(batch_build, "_drop_queue_tail_calcs", lambda u, p: u)


def test_長尺はショート向けの題を取らない(monkeypatch):
    _stub(monkeypatch, "s-alpha", "s-bravo", "charlie", "s-delta")
    got = [t["id"] for t in batch_build.pick(3, [], long_form=True)]
    assert got == ["charlie"], got


def test_長尺向けが無い回は止めずにショート向けを取る(monkeypatch):
    _stub(monkeypatch, "s-alpha", "s-bravo")
    got = [t["id"] for t in batch_build.pick(2, [], long_form=True)]
    assert len(got) == 2, got
    assert all(i.startswith("s-") for i in got), got


def test_既定は両方から取る(monkeypatch):
    _stub(monkeypatch, "s-alpha", "charlie")
    got = [t["id"] for t in batch_build.pick(2, [])]
    assert sorted(got) == ["charlie", "s-alpha"], got
