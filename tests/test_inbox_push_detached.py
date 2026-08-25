"""`src/inbox.py` の push が、**分離 HEAD でも通ること**。

`docs/trigger_main.md` §0 は「分離 HEAD のまま1周まわしてよい」と勧めています。
**その形だと引数なしの `git push` は必ず落ちます**（`You are not currently on a branch`）。
2026-08-19 に `--open` と `--close` の両方で実測しました。

**受け取り帳は、オーナーの依頼が次の子へ渡る唯一の経路**です。
押せないまま死ぬと依頼が消えるので、ここは道具の中で通ること。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from src import inbox

ROOT = Path(__file__).resolve().parent.parent


def _run(*argv, cwd):
    return subprocess.run(["git", "-C", str(cwd), *argv], check=True,
                          capture_output=True, text=True)


@pytest.fixture()
def 分離HEADの複製(tmp_path, monkeypatch):
    """origin つきの小さな repo を作り、**分離 HEAD で**立たせる。"""
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True,
                   capture_output=True)
    subprocess.run(["git", "clone", str(origin), str(work)], check=True, capture_output=True)
    _run("config", "user.email", "t@example.com", cwd=work)
    _run("config", "user.name", "t", cwd=work)
    (work / "data").mkdir()
    (work / "data" / "inbox.jsonl").write_text("", encoding="utf-8")
    _run("add", "-A", cwd=work)
    _run("commit", "-m", "init", cwd=work)
    _run("push", "-u", "origin", "main", cwd=work)
    # 手順どおり、作業枝を切って origin に置き、**分離 HEAD で**乗る
    _run("checkout", "-b", "claude/w", cwd=work)
    _run("commit", "--allow-empty", "-m", "branch tip", cwd=work)
    _run("push", "-u", "origin", "claude/w", cwd=work)
    _run("switch", "--detach", "origin/claude/w", cwd=work)
    assert _run("rev-parse", "--abbrev-ref", "HEAD", cwd=work).stdout.strip() == "HEAD"

    monkeypatch.setattr(inbox, "ROOT", work)
    monkeypatch.setattr(inbox, "LEDGER", work / "data" / "inbox.jsonl")
    return work, origin


def test_分離HEADでも押せる(分離HEADの複製):
    work, origin = 分離HEADの複製
    (work / "data" / "inbox.jsonl").write_text('{"id":"abc"}\n', encoding="utf-8")
    ok, detail = inbox.git_save("inbox: 受け取った")
    assert ok, detail
    # **origin 側に本当に届いていること**（「押せた」と言うだけの検査にしない）
    got = subprocess.run(["git", "-C", str(origin), "show", "claude/w:data/inbox.jsonl"],
                         capture_output=True, text=True)
    assert got.returncode == 0, got.stderr
    assert "abc" in got.stdout


def test_引数なしのpushに戻さないこと(分離HEADの複製):
    """**写しに戻す形の再発を止める。** 枝を決めてから押していること。"""
    src = (ROOT / "src" / "inbox.py").read_text(encoding="utf-8")
    assert "_target_branch" in src
    assert 'f"HEAD:{branch}"' in src
    # `pull --rebase` は分離 HEAD で落ちるので、枝が分かるときは fetch+rebase を使う
    assert '_git("fetch", "origin", branch' in src


def test_枝が分からない回でも例外にしない(分離HEADの複製, monkeypatch):
    """**依頼を受け取った直後に道具が落ちるのがいちばん高い**（元からの方針）。"""
    work, _ = 分離HEADの複製
    _run("remote", "remove", "origin", cwd=work)
    (work / "data" / "inbox.jsonl").write_text('{"id":"zzz"}\n', encoding="utf-8")
    ok, detail = inbox.git_save("inbox: 受け取った")
    assert ok is False and detail  # 押せないが、例外ではなく「押せなかった」で返る
