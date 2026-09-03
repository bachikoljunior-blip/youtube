"""**焼きがどこまで進んだかは、log ではなく `build/<題材>/` で見ること**（2026-09-04 22:0x）。

`data/rebake.log` の末尾は **最大 20分 古い**です（子が 8KB ずつためる・`_run_out()` の註）。
実測: 末尾が「分かりやすさの輪 2周目」のまま止まって見えた 20分 の間に、実物は
3周目・4周目 を終え、**音 62本 まで焼き終えていました。**

**待つ側が log だけを見ると「固まった」と読んで降ります** —— この回がまさに読みかけ、
`ps -o time=`（CPU 29分）と `build/` の mtime で、初めて生きていると分かりました。
`build/<題材>/` の mtime は子の buffer を通らないので、**そこだけは嘘をつきません。**
"""
from __future__ import annotations

from pathlib import Path

import pytest

from scripts import ahead_sweep


def _mk(root: Path, topic: str, names: list[str]) -> None:
    d = root / "build" / topic
    d.mkdir(parents=True, exist_ok=True)
    for n in names:
        p = d / n
        if n in ("audio", "clips"):
            p.mkdir(exist_ok=True)
        else:
            p.write_text("x", encoding="utf-8")


def test_いちばん進んだ段を返す(tmp_path) -> None:
    _mk(tmp_path, "t", ["script.json", "clarity_loop.json", "audio", "clips", "final.mp4"])
    got = ahead_sweep.bake_stage("t", root=tmp_path)
    assert "焼き上がり" in got and "build/t/final.mp4" in got


def test_音まで来ていれば読み照合の輪(tmp_path) -> None:
    _mk(tmp_path, "t", ["script.json", "clarity_loop.json", "audio"])
    got = ahead_sweep.bake_stage("t", root=tmp_path)
    assert "読み照合の輪" in got


def test_台本だけなら分かりやすさの輪(tmp_path) -> None:
    _mk(tmp_path, "t", ["script.json"])
    assert "分かりやすさの輪" in ahead_sweep.bake_stage("t", root=tmp_path)


def test_無い題材は空(tmp_path) -> None:
    assert ahead_sweep.bake_stage("nope", root=tmp_path) == ""
    assert ahead_sweep.bake_stage("", root=tmp_path) == ""


def test_下限は読み照合の輪を数に入れていない() -> None:
    """**`bake_minutes()` は下限です。** 上振れするので、そう読むこと。

    分かりやすさの輪（実測）＋ 焼き（13分）しか入っていません。**いちばん長い
    読み照合の輪は 0 と置いてあります** —— `done` が 1件も無く、終わりの時刻が
    どこにも無いからです（`rebake_tally()` の註）。
    """
    mins, n = ahead_sweep.bake_minutes()
    if mins is None:
        pytest.skip("分かりやすさの輪の実測がまだ 1件も無い")
    assert n >= 1
    assert mins > ahead_sweep.BAKE_RENDER_MIN
