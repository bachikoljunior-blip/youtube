"""`claude -p` を Fable で撃つときは `--effort high` を渡すこと。

オーナー 09/03 11:1x「エフォートレベル全て高にして」「Fable5.1使う時は」。
`CLAUDE.md` 冒頭が正本。実装は `src/claude_cli.effort_for()`。
"""
from __future__ import annotations

import subprocess

import pytest

from src import claude_cli


def test_fable_なら_high(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(claude_cli.EFFORT_ENV, raising=False)
    assert claude_cli.effort_for("fable") == "high"
    assert claude_cli.effort_for("claude-fable-5-1") == "high"
    assert claude_cli.effort_for("Fable") == "high"


def test_ほかの模型には渡さない(monkeypatch: pytest.MonkeyPatch) -> None:
    """指示は「Fable5.1使う時は」と範囲を切っている（09/03 07:3x の軽い模型と逆を向かない）。"""
    monkeypatch.delenv(claude_cli.EFFORT_ENV, raising=False)
    for model in ("opus", "sonnet", "haiku", ""):
        assert claude_cli.effort_for(model) is None


def test_環境変数で上書きできる(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(claude_cli.EFFORT_ENV, "medium")
    assert claude_cli.effort_for("opus") == "medium"
    monkeypatch.setenv(claude_cli.EFFORT_ENV, "")
    assert claude_cli.effort_for("fable") is None


def test_撃つ引数に並ぶ(monkeypatch: pytest.MonkeyPatch) -> None:
    """`_invoke()` の組み立てそのものを見る（`effort_for` が正しくても配線が外れうる）。"""
    monkeypatch.delenv(claude_cli.EFFORT_ENV, raising=False)
    seen: list[list[str]] = []

    class _Proc:
        returncode = 0
        stdout = '{"result": "{}"}'
        stderr = ""

    def _fake_run(args: list[str], **kw: object) -> _Proc:
        seen.append(list(args))
        return _Proc()

    monkeypatch.setattr(claude_cli, "_binary", lambda: "claude")
    monkeypatch.setattr(claude_cli, "_parse_envelope", lambda out: ("{}", ""))
    monkeypatch.setattr(subprocess, "run", _fake_run)

    claude_cli._invoke("p", "fable", None, 10)
    assert seen[-1][seen[-1].index("--effort") + 1] == "high"

    claude_cli._invoke("p", "opus", None, 10)
    assert "--effort" not in seen[-1]
