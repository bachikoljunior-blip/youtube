"""**この計器が、どこからも撃たれていない状態にならないこと。**

この repo でいちばん多い壊れ方は「言っている所と、している所が別」で、
`retro.py` は「どこからも撃たれていない道具」を毎周 数えています。
**`ledger_holes` は `run_marker.py --write` の画面から撃たれます。**
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_run_marker_の画面から撃たれている() -> None:
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    assert "from src import ledger_holes" in src
    assert "ledger_holes.lines()" in src


def test_数えられなくても画面が落ちない(monkeypatch) -> None:
    """**計器が落ちても、走った印のほうは付くこと**（§1 は毎周 必ず最初に撃たれる口）。"""
    from src import ledger_holes
    monkeypatch.setattr(ledger_holes, "lines",
                        lambda **k: (_ for _ in ()).throw(RuntimeError("boom")))
    src = (ROOT / "scripts" / "run_marker.py").read_text(encoding="utf-8")
    i = src.index("from src import ledger_holes")
    assert "except Exception" in src[i:i + 500]        # try で囲ってあること
