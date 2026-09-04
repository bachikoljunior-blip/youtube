"""**決めと枠の食い違いが、門から出ること。**

## なぜ要るか（2026-09-05・最適化の回。**実物で踏んだ**）

`data/daily_pick.jsonl` は書く先で、押す先ではない。09/05 のあいだに決めは **6回**
書き換わり（00:38 長尺 → 01:17 → 01:48 → 05:09 ショート → 05:11 → 05:37）、
**チャンネルの予約は1度も変わらなかった** —— 09/05 09:00 は `GFvAcxvDmYM`
（長尺・見込み 齢48h 1回）のままで、決めは ショート（同 164回）。

押されない理由は `ahead_sweep.today_plan()` の `if count >= max(1, cap)` で、
**どの本が入っているかを見ていない**。`place_today()` はその手前で
`if count < house_rule.cap()` のときしか候補を読まないので、食い違いは構造上 見えない。

**覆る条件**: `today_plan()` が枠の中身まで見て入れ替えるようになったら、この門は
空振りしかしない（そのとき外してよい。**先に外さないこと**）。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _load():
    spec = importlib.util.spec_from_file_location("_sg", ROOT / "scripts" / "slot_gate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


TODAY = date(2026, 9, 5)


def _row(vid: str, at: str, topic: str = "s-x", title: str = "題"):
    return {"id": vid, "at": at, "topic": topic, "title": title, "scheduled": True}


def test_決めと枠が食い違えば鳴る():
    sg = _load()
    out = sg.mismatch_lines(
        rows=[_row("inSlot", "2026-09-05T00:00:00Z")],
        today=TODAY,
        picked={TODAY: {"video_id": "decided", "form": "ショート", "expected_48h": 164.0}},
        published=set(),
    )
    assert out, "**食い違いが鳴っていません**"
    body = "\n".join(out)
    assert "inSlot" in body and "decided" in body
    assert "--unschedule inSlot" in body and "--move decided" in body


def test_合っていれば黙る():
    sg = _load()
    assert sg.mismatch_lines(
        rows=[_row("same", "2026-09-05T00:00:00Z")],
        today=TODAY,
        picked={TODAY: {"video_id": "same", "form": "ショート"}},
        published=set(),
    ) == []


def test_公開ずみの題材が枠に居れば鳴る():
    sg = _load()
    out = sg.mismatch_lines(
        rows=[_row("dup", "2026-09-05T00:00:00Z", topic="s-done")],
        today=TODAY,
        picked={TODAY: {"video_id": "dup", "form": "ショート"}},   # 決めとは合っている
        published={"s-done"},
    )
    assert out, "**公開ずみの題材が枠に居るのに黙っています**"
    assert "s-done" in "\n".join(out)


def test_空の日はこの門の担当ではない():
    """空きは `lines()` の担当。ここで二重に鳴らさない。"""
    sg = _load()
    assert sg.mismatch_lines(rows=[], today=TODAY,
                             picked={TODAY: {"video_id": "decided"}},
                             published=set()) == []
