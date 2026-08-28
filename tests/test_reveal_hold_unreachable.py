"""**文が 2.5秒 より短いと、めくりをどう割っても `verify` は必ず落ちます。**

2026-08-28 に測って足しました。

`verify._check_reveal_hold` は「完成形が `MIN_COMPLETE_SECONDS`（2.5秒）以上
画面に残っているか」を見ます。ところが `pipeline.reveal_durations` は
**完成形が 2.5秒 に届くまで頭のコマを落とす**ので、文そのものが 2.5秒 より
短い場合は **1コマ（＝文の全長）**になります。完成形は文の 100% を占めていて、
**それでも下限に届きません。**

    dur=2.3 の文 → want が 1 でも 4 でも `[2.30]` の1コマ → **必ず落ちる**

つまりこれは「割り方が悪い」のではなく **台本の問題**で、
**直せるのは文を長くすることだけ**です。

ところが判定は `verify`（final.mp4 のあと）にしかありませんでした。
実測で 08/28 に2回、**スライド描画と ffmpeg を全部やってから 2.3秒 で落ちて**、
まるごと作り直しています。`pipeline` は音声の尺が出た時点で同じことが
分かるので、**描く前に**落とすようにしました。

この検査が守るのは2つです。

1. `reveal_durations` が「1コマ・下限未満」を返す帯が本当にあること
   （＝ `verify` 側の下限を上げても、この帯は割り方では救えない）
2. **早い側の門が消えていないこと**（消すと、また ffmpeg のあとで落ちます）
"""
from __future__ import annotations

import math
from pathlib import Path

import pytest

from src import pipeline, verify

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("dur", [1.0, 1.5, 2.0, 2.3, 2.49])
@pytest.mark.parametrize("want", [1, 2, 3, 4, 8])
def test_下限より短い文は割り方で救えない(dur: float, want: int) -> None:
    """**どう割っても1コマ**で、完成形は文の全長のまま。"""
    secs = pipeline.reveal_durations(dur, want)
    assert len(secs) == 1, f"dur={dur} want={want} が1コマになっていません: {secs}"
    assert secs[-1] == pytest.approx(dur)
    assert secs[-1] + 1e-6 < verify.MIN_COMPLETE_SECONDS
    assert sum(secs) == pytest.approx(dur), "音とずれます（合計は変えないこと）"


@pytest.mark.parametrize("dur", [2.5, 3.0, 4.0, 6.0, 9.0])
@pytest.mark.parametrize("want", [1, 2, 3, 4, 8])
def test_下限以上の文は完成形が下限を満たす(dur: float, want: int) -> None:
    """**上の裏返し。** ここが落ちるなら、早い側の門が正しい文まで止めます。"""
    secs = pipeline.reveal_durations(dur, want)
    assert secs[-1] + 1e-6 >= verify.MIN_COMPLETE_SECONDS, (
        f"dur={dur} want={want} → {secs}：完成形が下限を割っています")
    assert sum(secs) == pytest.approx(dur)


def test_描く前に落とす門が残っている() -> None:
    """**この門を消すと、また `final.mp4` のあとで落ちます**（実測 2件・08/28）。

    `visuals.render` より**前**にあることまで見ます ——
    後ろへ動かすと、スライドと ffmpeg のぶんが捨てになります。
    """
    src = (ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    assert "MIN_COMPLETE_SECONDS" in src, (
        "`pipeline` から完成形の下限が消えています。"
        "`verify` だけになると、描いたあとでしか落ちません")
    gate = src.find("番目の文が")
    render = src.find("slides = visuals.render")
    assert gate != -1, "描く前に落とす門が消えています"
    assert render != -1, "`visuals.render` の呼び出しが見つかりません"
    assert gate < render, (
        "門が `visuals.render` より後ろにあります。"
        "**描く前に落とす**のがこの門の目的です")


def test_下限はverifyから借りている() -> None:
    """**同じ規則を2か所に書かないこと**（`short_script_problems` の docstring）。"""
    src = (ROOT / "src" / "pipeline.py").read_text(encoding="utf-8")
    gate = src[src.find("番目の文が") - 800:src.find("番目の文が") + 800]
    assert "verify.MIN_COMPLETE_SECONDS" in gate, (
        "門が下限を自前で持っています。`verify` から借りること "
        "——片方だけ動かすと、描く前の門と最後の砦がずれます")
