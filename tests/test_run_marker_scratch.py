"""`run_marker.scratch_dir()` —— **この回だけの一時置き場**。

**なぜ検査が要るか**（2026-08-29 に踏んだ）: 一時置き場の道は
`CLAUDE_CODE_SESSION_ID` から作られていて、**同じ親から立ったサブは
全員 同じ ID を持ちます**（環境変数はコンテナに1つ）。
つまりきょうだいは全員 同じディレクトリを見ており、
`status.txt` `eta.txt` `build.log` のような当たり前の名前は
**書いた先から上書きされます**（実測: `status.py` の出力 266行 → 24行）。

`docs/trigger_main.md` は 2026-08-26 から正しい逃げ方を書いていますが、
**書いてあっても踏みます**。だから掘る側を `--write` へ移しました。

ここが守るのは3つ:

    1. 作業コピーの名前で分かれること（**セッションIDでは分かれません**）
    2. 掘れない置き方（環境変数が無い・glob が当たらない・親）で**空を返す**こと
       —— ここで落ちると、印そのものが打てなくなります
    3. `--write` の印字にその道が出ること
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import run_marker  # noqa: E402

SID = "sess-scratch-test"


def _tmp_with_scratchpad(tmp_path: Path) -> Path:
    root = tmp_path / "claude-0" / "-home-user-youtube" / SID / "scratchpad"
    root.mkdir(parents=True)
    return root


def test_作業コピーの名前で分かれること(tmp_path, monkeypatch):
    root = _tmp_with_scratchpad(tmp_path)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.setattr(run_marker, "_TMP", tmp_path)

    got = []
    for tag in ("agent-aaaaaaaaaaaaaa1", "agent-bbbbbbbbbbbbbb2"):
        monkeypatch.setattr(run_marker, "worktree_tag", lambda t=tag: t)
        got.append(run_marker.scratch_dir())

    assert all(got), "掘れるはずの置き方で空が返りました"
    assert got[0] != got[1], "きょうだいが同じ所へ落ちています"
    for d in got:
        assert Path(d).is_dir()
        assert Path(d).parent == root


def test_掘れない置き方では空を返すこと(tmp_path, monkeypatch):
    _tmp_with_scratchpad(tmp_path)
    monkeypatch.setattr(run_marker, "_TMP", tmp_path)

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    monkeypatch.setattr(run_marker, "worktree_tag", lambda: "")
    assert run_marker.scratch_dir() == "", "親（作業コピーでない）では空のはず"

    monkeypatch.setattr(run_marker, "worktree_tag", lambda: "agent-x")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    assert run_marker.scratch_dir() == "", "IDが無ければ空のはず"

    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "該当なし")
    assert run_marker.scratch_dir() == "", "glob が当たらなければ空のはず"


def test_writeがその道を印字すること(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(run_marker, "is_parent", lambda: False)
    monkeypatch.setattr(run_marker, "actor_id", lambda: "sess#agent-zzz")
    monkeypatch.setattr(run_marker, "_append", lambda rec: "{}")
    monkeypatch.setattr(run_marker, "_claim_lines", lambda *a, **k: [])
    monkeypatch.setattr(run_marker, "scratch_dir", lambda: str(tmp_path / "zzz"))

    run_marker.write()
    out = capsys.readouterr().out
    assert "一時置き場" in out
    assert str(tmp_path / "zzz") in out
