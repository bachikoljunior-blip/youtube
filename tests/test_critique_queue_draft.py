"""**規則5 の下では、次に出る1本は「予約なし」で隠れます。**

## 実物（2026-09-02 16:3x に踏んだ）

`python scripts/critique_queue.py` の出力:

    出していない 435本: **予約なし**（重なりで外した本）。
    直す先も engaged も無いので評価しても捨てになります
      … MqQKSnbM0OI …

`MqQKSnbM0OI` は **09/03 に出す本**（09/02 13:57 に `--draft` で焼いたもの）で、
その回の仕事はまさに「これを出る瞬間まで良くし続ける」（規則3）でした。
**独立評価の当てどころを出す道具が、その1本だけを隠していました。**

## なぜそうなっていたか

段分け（`deadlines()`）は **2026-08-16** のもので、
**規則5（固定その4「1日の回り方」）より前**です。規則5 はこう回ります ——

    公開したら → すぐ次の日の1本を作り始める → 次の枠まで改善し続ける
               → **その日になったら、その日で予約して出す**

つまり **次に出る1本は、その日が来るまで必ず `at` が空 ＝ 段2（予約なし）**。
段2 の説明は「直す先も較正の材料も無い」ですが、**公開も予約もしていない本は、
いちばん自由に直せる1本**です（題も台本もサムネも、まだ誰も見ていません）。

## ここで固定するもの

1. 下書き（`next_slot.drafts()` ＝ `retimed_at` が無い本）は段2 から段0 へ戻す
2. **池化した本（一度 予約して外した本）は段2 のまま**（捨てで合っています）
3. 口が読めなくても**この道具を止めない**

## 覆る条件

オーナーが規則5 を外して先の日付に予約できるようになったら、次に出る本は
最初から段0 に入るので、この上書きは何もしなくなります。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

_spec = importlib.util.spec_from_file_location(
    "critique_queue_draft_mod", ROOT / "scripts" / "critique_queue.py")
cq = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cq)

from src import next_slot  # noqa: E402


def test_下書きは段0へ戻す(monkeypatch):
    monkeypatch.setattr(next_slot, "drafts",
                        lambda *a, **k: [{"video_id": "draft1"}])
    out = {"draft1": (2, 0.0), "drained": (2, 0.0),
           "sched": (0, 12.0), "live": (1, 0.0)}
    got = cq._mark_drafts(dict(out))
    assert got["draft1"][0] == 0, "**次に出る1本を、捨てに分類しないこと**"
    assert got["drained"] == (2, 0.0), "**池化した本は段2 のまま**（捨てで合っています）"
    assert got["sched"] == (0, 12.0), "予約ずみの猶予を書き換えないこと"
    assert got["live"] == (1, 0.0)


def test_下書きは段0の末尾に置く(monkeypatch):
    """**公開が迫っている予約ずみの本より急ぎではありません。**

    下書きは「その日が来るまで直し続けられる」ので、猶予は `inf`。
    段0 の中では最後に並びます。
    """
    monkeypatch.setattr(next_slot, "drafts",
                        lambda *a, **k: [{"video_id": "draft1"}])
    got = cq._mark_drafts({"draft1": (2, 0.0), "sched": (0, 12.0)})
    order = sorted(got, key=lambda k: (got[k][0], got[k][1], k))
    assert order == ["sched", "draft1"], order


def test_口が読めなくても止まらない(monkeypatch):
    def _boom(*a, **k):
        raise RuntimeError("控えが読めません")
    monkeypatch.setattr(next_slot, "drafts", _boom)
    got = cq._mark_drafts({"draft1": (2, 0.0)})
    assert got == {"draft1": (2, 0.0)}, "**段2 のまま返すこと**（落ちないこと）"
