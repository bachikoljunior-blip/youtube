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


def _ledger(tmp_path, monkeypatch, clarity: str, rebake: str) -> None:
    monkeypatch.setattr(ahead_sweep.config, "ROOT", str(tmp_path))
    d = tmp_path / "data"
    d.mkdir(parents=True, exist_ok=True)
    if clarity is not None:
        (d / "clarity_loop.jsonl").write_text(clarity, encoding="utf-8")
    if rebake is not None:
        (d / "rebake.jsonl").write_text(rebake, encoding="utf-8")


def test_done_が在れば本物の長さを返す(tmp_path, monkeypatch) -> None:
    """**`done` が 1件でも在れば、`seconds` の中央値**（焼き始め → 終わりの本物の長さ）。

    2026-09-04 07:40 に、この repo で初めて焼き直しが最後まで通りました
    （`seconds` 4692 ＝ **78.2分**）。それまで返していた下限は 37分 で、
    **2.1倍 外れて**いました。`rc` は見ません —— 落ちた焼きも、
    そこまでに同じ時間を使っています（測っているのは「成功したか」ではなく
    「**どれだけ待たされるか**」）。
    """
    _ledger(tmp_path, monkeypatch,
            '{"seconds": 600}\n',
            '{"kind": "start"}\n'
            '{"kind": "done", "rc": 1, "seconds": 4692}\n'
            '{"kind": "done", "rc": 0, "seconds": 4800}\n')
    mins, n = ahead_sweep.bake_minutes()
    assert n == 2
    # 中央値（偶数なら上側）＝ 4800秒 ＝ 80.0分。輪だけの下限（10分 ＋ 焼き）ではない
    assert mins == 80.0


def test_done_が無ければ輪の下限へ落ちる(tmp_path, monkeypatch) -> None:
    """**まだ1件も終わっていない間だけ**、分かりやすさの輪 ＋ 焼き の**下限**。"""
    _ledger(tmp_path, monkeypatch, '{"seconds": 600}\n', '{"kind": "start"}\n')
    mins, n = ahead_sweep.bake_minutes()
    assert (mins, n) == (10.0 + ahead_sweep.BAKE_RENDER_MIN, 1)


def test_どちらも無ければ何も返さない(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(ahead_sweep.config, "ROOT", str(tmp_path))
    (tmp_path / "data").mkdir(parents=True, exist_ok=True)
    assert ahead_sweep.bake_minutes() == (None, 0)


def test_枠までの線は実測より長いこと() -> None:
    """**`REBAKE_LEAD` は「1回の焼きの長さ」より長くなければ意味がありません。**

    100分 の線は、実測 78.2分 ＋ 上げ に対して余裕が 20分 しかなく、しかも
    読み照合の輪の 32分 は**誤読 0件 で1周**の値でした（誤読が出れば +30分）。
    この検査は、次に誰かが線を実測へ近づけたときに鳴ります。
    """
    mins, n = ahead_sweep.bake_minutes()
    if mins is None or not n:
        pytest.skip("焼きの長さがまだ 1件も測れていない")
    lead = ahead_sweep.REBAKE_LEAD.total_seconds() / 60.0
    assert lead >= mins * 1.5, f"線 {lead:.0f}分 が実測 {mins:.1f}分 に近すぎます"
