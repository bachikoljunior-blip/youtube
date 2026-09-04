"""**待つ側と殺す側が、同じ数を持つこと。**（2026-09-04 16:39 に踏んで足した）

`REBAKE_LEAD` は「焼き上がるのに **150分** 見る」と言い、焼く側を殺す秒数は
`5400`（**90分**）と直に書いてありました —— **同じ file の中で 60分 食い違い**。

実測（`data/rebake.jsonl` の `done` 3件）:

    07:40  rc=1    4,692秒（78分）  読み照合の輪 1周
    14:42  rc=0    3,325秒（55分）  読み照合の輪 1周
    16:39  rc=124  5,400秒（90分・**殺された**）  読み照合の輪が **2周**

＝ **誤読が見つかって音を作り直した回だけ、必ず殺される**（オーナー指示の輪が
正しく回った回ほど損をする）形でした。
"""
from __future__ import annotations

import inspect

from scripts import ahead_sweep


def test_殺す秒数は待つ側と同じ数から作る() -> None:
    assert ahead_sweep.REBAKE_RUN_TIMEOUT == int(ahead_sweep.REBAKE_LEAD.total_seconds())


def test_殺す秒数は待つ側より短くない() -> None:
    """短いと、**枠に間に合う見込みで始めた焼きを、自分で殺します。**"""
    assert ahead_sweep.REBAKE_RUN_TIMEOUT >= ahead_sweep.REBAKE_LEAD.total_seconds()


def test_実測の最長より長いこと() -> None:
    """輪が2周した回（90分 で殺された）を通せること。**通らないなら数が古い。**"""
    assert ahead_sweep.REBAKE_RUN_TIMEOUT > 5400


def test_焼く側がその数を使っていること() -> None:
    """**定数を足しても、呼ぶ側が直の数のままなら1ミリも変わりません。**"""
    src = inspect.getsource(ahead_sweep.rebake_run)
    assert "REBAKE_RUN_TIMEOUT" in src
    assert "5400" not in src
