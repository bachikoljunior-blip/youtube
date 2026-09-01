"""棚が**時間とともに**上がっているか（`src/form_tail.shelf_drift()`・2026-09-02）。

`tail_elasticity()` が回す相手は「その日の本数」、こちらは**日付**です。
別の量なので両方 要ります —— 本数を減らして上がらなくても、
**チャンネルが育って上がる**なら、天井は定数ではありません。

**この検査は「上がっている／いない」を固定しません。** 測り方が
壊れていないこと（傾きが出ること・作り物の右肩上がりを右肩上がりと言うこと）だけを見ます。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import form_tail  # noqa: E402


def _rows(maxes: list[int]) -> list[tuple]:
    """1日1本の帳面を作る（`_settled()` と同じ (日, id, 生涯再生) の形）。"""
    base = date(2026, 8, 1)
    return [(base + timedelta(days=i), f"v{i}", m) for i, m in enumerate(maxes)]


def test_右肩上がりの棚は右肩上がりと出る():
    got = form_tail.shelf_drift(_rows([100, 150, 220, 330, 500, 750, 1100, 1600]))
    assert got and got["rising"], got
    assert got["fit"]["b"] > 0


def test_平らな棚は0と区別が付かないと出る():
    got = form_tail.shelf_drift(_rows([500, 480, 520, 510, 490, 505, 495, 515]))
    assert got and not got["rising"], got


def test_日が足りなければ黙る():
    assert form_tail.shelf_drift(_rows([100, 200, 300])) is None


def test_実物でも傾きが出る():
    """`data/views.jsonl` を読んで、数が返ること（**向きは固定しない**）。"""
    got = form_tail.shelf_drift()
    if got is None:
        return                     # 帳面が薄い環境では飛ばす
    assert got["days"] >= 4
    assert "b" in got["fit"] and "lo" in got["fit"] and "hi" in got["fit"]
    assert got["fit"]["lo"] <= got["fit"]["b"] <= got["fit"]["hi"]
