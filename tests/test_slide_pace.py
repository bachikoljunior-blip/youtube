"""**ショートの刻み（1コマの秒数）を、テーマIDで2つに振り分ける**（2026-08-27）。

オーナー原文（2026-08-27 21:0x）:

> 「動画についてまず何言ってるか分かんないね。音声だけで理解できない説明なのに
> **画面はすぐ切り替わるし。**説明を理解するにはかなり視聴者側の推論が必要だと思う」

実測（`data/critique_queue/` の控え 502本）:

    ショート 439本  尺 26.3秒 ／ 13.0コマ → **1コマ 2.06秒**（3秒未満が100%）
    長尺      63本  尺 322.9秒 ／ 17.0コマ → 1コマ 19.5秒

再生の 99.8% は `SHORTS_FEED`、1再生あたり 20秒 ——
**視聴者が見ている20秒のあいだに、画面は約10回 変わります。**

`SHORT_SLIDE_SECONDS = 2.5` は **M13（独立評価・終わった手段）の言い分だけ**で
決まっていて、**視聴者の実データで一度も確かめられていません。**
だから「直す」ではなく「振り分けて測る」形にしてあります。
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import pipeline, script_writer  # noqa: E402

IDS = [f"s-{i}" for i in range(4000)]


def _slow(tid: str) -> bool:
    return pipeline.slide_pace(tid) == pipeline.SHORT_SLIDE_SECONDS_SLOW


def test_同じテーマIDは何度呼んでも同じ側():
    """**乱数にしないこと。** 作り直しで群が移ると比較が壊れます。"""
    for tid in IDS[:50]:
        assert pipeline.slide_pace(tid) == pipeline.slide_pace(tid)


def test_割合はおおむね半々():
    got = sum(1 for t in IDS if _slow(t)) / len(IDS)
    assert abs(got - pipeline.SLOW_PACE_SHARE) < 0.03, got


def test_share_の両端で振り分けが止まる():
    """**0 にすると振り分けが止まります**（勝ち負けが付いた後の畳み方）。"""
    assert all(pipeline.slide_pace(t, share=0.0) == pipeline.SHORT_SLIDE_SECONDS
               for t in IDS[:200])
    assert all(pipeline.slide_pace(t, share=1.0) == pipeline.SHORT_SLIDE_SECONDS_SLOW
               for t in IDS[:200])


def test_他の実験と重なっていない():
    """**塩を変えること。** 同じにすると2つの実験が完全に重なり、
    どちらが効いたのか永久に分かりません（`hook_form` の docstring）。
    """
    pace = [_slow(t) for t in IDS]
    for name, fn, yes in (("hook", script_writer.hook_form, "問い"),
                          ("title", script_writer.title_form, "問い"),
                          ("request", script_writer.request_form, "途中あり")):
        other = [fn(t) == yes for t in IDS]
        agree = sum(1 for a, b in zip(pace, other) if a == b) / len(IDS)
        assert abs(agree - 0.5) < 0.05, f"{name} と重なっています（一致率 {agree:.3f}）"


def test_遅い側のほうが本当に遅い():
    assert pipeline.SHORT_SLIDE_SECONDS_SLOW > pipeline.SHORT_SLIDE_SECONDS


def test_pipeline_が_この関数を通している():
    """**定数を直に読んでいたら、振り分けが1本も効きません。**

    ここが落ちたら、`want` の計算が `slide_pace()` を通らなくなっています。
    """
    src = Path(pipeline.__file__).read_text(encoding="utf-8")
    assert "want = max(1, math.ceil(dur / pace))" in src
    assert "pace = slide_pace(" in src
    # **定数を直に割り算に使っていないこと**（写しが増えると片方だけ直ります）
    assert "dur / SHORT_SLIDE_SECONDS" not in src
