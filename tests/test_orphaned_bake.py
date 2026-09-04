"""**焼き直しの親が死に、`src.pipeline` だけが孤児で残る形**を見つけられること。

## なぜ要るか（2026-09-05 06:5x に実測した）

`docs/spawn_prompt.md` は、焼き直しの生死を**この2つで見ろ**と書いていました ——
`pgrep -f "ahead_sweep.py --rebake-run"`（「**これが正本**」）と
`data/rebake.jsonl` の `done` / `late`。**両方が「走っていません」と答える状態**を踏みました::

    pgrep -f "ahead_sweep.py --rebake-run"  → 一致なし
    ahead_sweep.rebake_busy()               → False（錠は空いている）
    ps                                      → 10641  PPID **1**  02:38:08
                                              timeout 12000 python -m src.pipeline
                                                --topic nenkin-uketorikata-65-70-75-handan
                                                --visibility private

`done` / `late` を書くのは `rebake_run()` の末尾なので、**親が死んだ回では永久に書かれません。**
`data/rebake.jsonl` が長らく **start 22件 ／ done 0件** だったのは、焼きが遅いからではなく
**記録する側が先に死んでいた**からです。

**この検査はプロセス表も時計も読みません**（`tests/test_tests_are_clockless.py`）——
`pgrep` の出力を注入します。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import ahead_sweep as a  # noqa: E402

#: 実測した `pgrep -af src.pipeline` の出力（この回のもの）。
REAL = (
    "10641 timeout 12000 python -m src.pipeline "
    "--topic nenkin-uketorikata-65-70-75-handan --visibility private\n"
    "10642 python -m src.pipeline "
    "--topic nenkin-uketorikata-65-70-75-handan --visibility private\n"
)

#: 回が**自分で**焼いている下書き。**これを焼き直しと読まないこと。**
MINE = (
    "26110 python -m src.pipeline --topic s-shokibo-yamekata-3-46bai --short --dry-run\n"
)


class _Out:
    def __init__(self, stdout: str) -> None:
        self.stdout = stdout


def _pgrep(monkeypatch, stdout: str) -> None:
    import subprocess

    monkeypatch.setattr(subprocess, "run", lambda *a_, **k: _Out(stdout))


def test_finds_the_orphan(monkeypatch):
    """孤児が居れば pid と題材を返す。"""
    _pgrep(monkeypatch, REAL)
    assert a.orphaned_bake() == ("10641", "nenkin-uketorikata-65-70-75-handan")


def test_ignores_my_own_dry_run(monkeypatch):
    """`--dry-run` は、回が自分で焼いている下書き。**焼き直しではない。**"""
    _pgrep(monkeypatch, MINE)
    assert a.orphaned_bake() == ("", "")


def test_nothing_running(monkeypatch):
    """何も走っていなければ空。"""
    _pgrep(monkeypatch, "")
    assert a.orphaned_bake() == ("", "")


def test_never_raises_when_pgrep_is_missing(monkeypatch):
    """`pgrep` が無い器でも**黙る**（自分の事故で回を止めない）。"""
    import subprocess

    def _boom(*a_, **k):
        raise FileNotFoundError("pgrep")

    monkeypatch.setattr(subprocess, "run", _boom)
    assert a.orphaned_bake() == ("", "")


def test_lines_say_done_will_never_come(monkeypatch):
    """回に読ませる行が、**待たせない**ことを言っていること。"""
    _pgrep(monkeypatch, REAL)
    text = "\n".join(a.orphaned_bake_lines())
    assert "10641" in text and "nenkin-uketorikata-65-70-75-handan" in text
    # 待つな・枠へ入らない・錠は空、の3つが出ること
    assert "永久に書かれません" in text
    assert "枠へ入ることもありません" in text
    assert "錠は空いている" in text


def test_lines_are_empty_when_no_orphan(monkeypatch):
    """居なければ**1行も出さない**（空振りで画面を埋めない）。"""
    _pgrep(monkeypatch, "")
    assert a.orphaned_bake_lines() == []
