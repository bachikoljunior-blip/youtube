"""**要る倍率のとなりに、この台帳が実際に出した倍率が並ぶこと。**

2026-08-26・最適化の回。`scripts/eta.py` の「いちばん近い帯: ×18.1」は、
**となりに何も無いと「あと少し」に読めます。** 実際には `per_video` の腕が
これまでに出した最大は **×1.85** で、**9.8倍 足りません。**

**この検査が守っているのは、主に「取り違えないこと」のほうです** ——
台帳ぜんたいの最大は `rpm` の **×256**（ショート 対 長尺）ですが、
**それは伸びしろではなく、すでに取ってある差**（予約の 92% はもうショート）。
ここを「台帳の実力」として出すと **「積み上げれば届く」と逆の結論**が出ます。
だから比べる側は **同じ腕（`per_video`）に限る**こと。
"""
from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import eta  # noqa: E402


def _rows():
    return [
        {"effect": 256.0, "lever": "rpm", "note": "ショート256回 対 長尺1回"},
        {"effect": 1.85, "lever": "per_video", "note": "題材の選び方"},
        {"effect": 1.0, "lever": "per_video", "note": "動かず"},
        {"effect": 1.0, "lever": "per_video", "note": "動かず"},
        {"effect": 1.75, "lever": "density", "note": "密度2倍"},
    ]


def test_比べるのは同じ腕_per_videoの最大が出る(monkeypatch):
    monkeypatch.setattr(eta.arm_speed, "closed", lambda *a, **k: _rows())
    out = "\n".join(eta._ledger_reach(18.1))
    assert "×1.85" in out, "per_video の最大が出ていません"
    assert "9.8倍" in out, "足りない倍率が出ていません"


def test_台帳ぜんたいの最大は伸びしろとして足し込まない(monkeypatch):
    """**×256 を「この腕の実力」として出さないこと。**逆の結論が出ます。"""
    monkeypatch.setattr(eta.arm_speed, "closed", lambda *a, **k: _rows())
    out = "\n".join(eta._ledger_reach(18.1))
    # 註としては出る（何だったかが読めないと、次の回がまた拾う）
    assert "×256" in out and "すでに取ってある差" in out
    # ただし「届かない」の判定は per_video の 1.85 で下りていること
    assert "届きません" in out, "×256 で判定して『届く』側に倒れています"


def test_要る倍率が射程に入ったら警告は消える(monkeypatch):
    monkeypatch.setattr(eta.arm_speed, "closed", lambda *a, **k: _rows())
    out = "\n".join(eta._ledger_reach(1.5))   # ×1.85 で足りる
    assert "足りません" not in out
    assert "×1.85" in out, "実績そのものは、届いていても出すこと"


def test_台帳が空でも落ちない(monkeypatch):
    monkeypatch.setattr(eta.arm_speed, "closed", lambda *a, **k: [])
    assert eta._ledger_reach(18.1) == []


def test_読めなくても回を止めない(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("読めません")

    monkeypatch.setattr(eta.arm_speed, "closed", boom)
    assert eta._ledger_reach(18.1) == []


@pytest.mark.parametrize("lever", ["rpm", "density", "sub_rate"])
def test_per_videoが1件も無ければ何も出さない(monkeypatch, lever):
    """**他の腕の数字で per_video の穴を埋めないこと。**"""
    monkeypatch.setattr(eta.arm_speed, "closed",
                        lambda *a, **k: [{"effect": 9.0, "lever": lever, "note": "x"}])
    assert eta._ledger_reach(18.1) == []
