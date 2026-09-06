"""親が渡す「最初の1手」の `origin/main` の行は、決め打ちではなく数えた数（2026-09-06 22:5x・optimizer）。

それまで `FIRST_MOVE` は「`origin/main` は枝の先頭まで進めてあるので、もう `CLAUDE.md` では衝突しません」と
08/26 の1回の実測を 12日 そのまま渡していた。実物は 237 commit（1.5日）後ろだった。
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import spawn_prompt  # noqa: E402


def test_決め打ちの断定は消えている():
    assert "進めてあるので" not in spawn_prompt.FIRST_MOVE
    assert "<<main_gap>>" in spawn_prompt.FIRST_MOVE


def test_数えられたら数を言う(monkeypatch):
    calls = []

    def fake_run(cmd, **kw):
        calls.append(cmd)
        out = "237\n" if "rev-list" in cmd else "09/05 07:17\n"
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)
    line = spawn_prompt.main_gap(ROOT, "claude/x")
    assert "237 commit" in line and "09/05 07:17" in line
    assert "origin/main..origin/claude/x" in " ".join(calls[0])


def test_同じなら同じと言う(monkeypatch):
    monkeypatch.setattr(subprocess, "run", lambda cmd, **kw: subprocess.CompletedProcess(cmd, 0, stdout="0\n" if "rev-list" in cmd else "09/06 22:28\n", stderr=""))
    assert "枝の先頭と同じ" in spawn_prompt.main_gap(ROOT, "claude/x")


def test_数えられなければそう言う(monkeypatch):
    def boom(cmd, **kw):
        raise FileNotFoundError("no git")

    monkeypatch.setattr(subprocess, "run", boom)
    line = spawn_prompt.main_gap(ROOT, "claude/x")
    assert "数えられなかった" in line
    assert "進めてある" not in line


def test_本文に数の行が入る():
    text = spawn_prompt.build("optimizer")
    assert "最初の1手" in text
    assert "origin/main" in text and "<<main_gap>>" not in text


def test_写しには数を焼き込まない(tmp_path, monkeypatch):
    """写しは commit される静的な生成物。数を焼くと commit のたびに変わり、写しの検査が永久に赤になる
    （09/06 13:40〜09/07 03:1x に実際に赤・「写しを焼き直し」の commit 7件）。`_clock_block` と同じ扱い。"""
    monkeypatch.setattr(spawn_prompt, "RENDERED", tmp_path / "r.md")
    spawn_prompt.write_rendered()
    got = (tmp_path / "r.md").read_text(encoding="utf-8")
    assert "commit** 後ろ" not in got and "枝の先頭と同じ" not in got
    assert "git rev-list --count origin/main..HEAD" in got
    assert "<<branch>>" not in got
    # 立てる瞬間の本文（CLI）には数えた行が入ること
    live = spawn_prompt.build("hourly")
    assert "この checkout の origin の写しで数えた" in live or "数えられなかった" in live
