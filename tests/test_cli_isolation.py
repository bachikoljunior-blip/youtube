"""`claude -p` を**プロセスごとに別の場所**で走らせているかを検査する。

## なぜ要るか（2026-08-15 20:0x、実測で見つけた）

`--jobs 5` で10本まとめて作ったら3本しか通りませんでした。落ちた本のログを読んだら、
落ちていた理由は並列の負荷ではなく **中身の取り違え**でした。

    テーマ s-shitsugyo-60dai-kaiko-1nen-60nichi（失業給付・60代）
    → 出てきた題は「**同居特別障害者控除** 5年で179万6500円」
       ＝ **同時に走っていた** s-kojo-zeiritsu40-dokyo の出力

`claude` の CLI はセッションを**作業ディレクトリごと**に持ち、`ask()` は形式が
崩れると `--resume` で会話を続けます。**同じ場所で並走すると、やり直しが隣の
会話に着くことがあります。**（混ざったのは、実際にやり直しへ入った本でした）

**これは「落ちた」より悪い欠陥です。** 今回は `verify.py` の主語検査が
たまたま止めましたが、**取り違えた中身が検査をすり抜ければ、題と中身の
合わない動画がそのまま公開されます。**

だからここで見るのは「速いか」ではなく、**混ざらない形になっているか**です。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import claude_cli  # noqa: E402


@pytest.fixture(autouse=True)
def _reset():
    claude_cli._CLI_CWD = None
    yield
    claude_cli._CLI_CWD = None


def test_cwd_is_outside_the_repository():
    """リポジトリの中で走らせない。**`build/` も `CLAUDE.md` も見せない。**"""
    cwd = claude_cli._cli_cwd()
    assert cwd.is_dir()
    assert ROOT not in cwd.parents and cwd != ROOT


def test_same_process_reuses_one_directory():
    """やり直し（`--resume`）は同じ会話に着かないと直りません。**使い回すこと。**"""
    assert claude_cli._cli_cwd() == claude_cli._cli_cwd()


def test_directory_is_recreated_if_it_disappears():
    """消えていたら作り直す。無い cwd で subprocess を起こすと落ちます。"""
    first = claude_cli._cli_cwd()
    first.rmdir()
    second = claude_cli._cli_cwd()
    assert second.is_dir() and second != first


def test_separate_processes_get_separate_directories():
    """**これが本体。** 別プロセスなら別の場所＝セッションが混ざらない。"""
    code = (
        "import sys; sys.path.insert(0, %r);"
        "from src import claude_cli; print(claude_cli._cli_cwd())" % str(ROOT)
    )
    got = {
        subprocess.run([sys.executable, "-c", code], capture_output=True,
                       text=True, check=True).stdout.strip()
        for _ in range(2)
    }
    assert len(got) == 2, f"2つのプロセスが同じ場所を使っています: {got}"


def test_invoke_passes_the_directory_to_subprocess(monkeypatch):
    """`_invoke` が実際に cwd を渡しているか。**渡し忘れたら混線が戻ります。**"""
    seen: dict = {}

    class _Proc:
        returncode = 0
        stdout = '{"type":"result","result":"{}","session_id":"s1"}'
        stderr = ""

    def fake_run(args, **kw):
        seen.update(kw)
        return _Proc()

    monkeypatch.setattr(claude_cli.subprocess, "run", fake_run)
    monkeypatch.setattr(claude_cli, "_binary", lambda: "/usr/bin/true")
    claude_cli._invoke("p", "opus", None, 10)

    assert seen.get("cwd") == str(claude_cli._cli_cwd())
    assert os.path.isdir(seen["cwd"])
