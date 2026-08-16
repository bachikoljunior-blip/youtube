"""Stop フックは、**周を回していない回では1文字も出さない**こと。

## なぜ要るか（2026-08-16、オーナーが親の画面を見せてきた）

親（常駐セッション）は毎時起き、ほとんどの回は出すものがありません。
それでもこのフックが引き止めるので、**親は毎回「済み。」と答えていました。**
オーナーの言葉は **「これもいらない」** です。

名簿（`config/parents.txt`）に親IDを足す形は 8/15 に入っていましたが、
**効いていませんでした** —— 親は常駐で、手元のチェックアウトは
コンテナが立った時点のまま（親は `git` を打たない）。**新しい名簿を読めません。**

だから判定を**IDに依らない形**に変えました:

    `data/runs.jsonl` にこの回の印が無い ＝ 周ではない ＝ **何も出さない**

親は構造上ここに印を打てません（リポジトリを触らないので）。
**新しい親を立てても、名簿を書き忘れても、最初から黙ります。**

## 手で `bash scripts/stop_check.sh` を打たないこと

その形の実行は権限判定に掛かり、**無人の子は永久に止まります**
（8/16 07:04 に1件死亡）。**だからこの検査は、別名にコピーして打ちます。**
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "scripts" / "stop_check.sh"


def _fake_root(tmp_path: Path, marks: list[dict], parents: str = "") -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config").mkdir()
    # **別名にする**（`stop_check.sh` を打つ形を、検査からも消しておく）
    shutil.copy(SRC, tmp_path / "scripts" / "probe.sh")
    (tmp_path / "data" / "runs.jsonl").write_text(
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in marks), encoding="utf-8"
    )
    (tmp_path / "config" / "parents.txt").write_text(parents, encoding="utf-8")
    return tmp_path


def _run(root: Path, session: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_CODE_REMOTE_SESSION_ID"] = session
    # **数え上げの置き場を、この検査の中だけに閉じる。**
    # 既定は `/tmp` の固定名で、**実物の「3回まで引き止める」と共有になります** ——
    # 検査を2度回すと3回ぶん進み、**3度目から引き止めなくなって落ちました**
    # （2026-08-16 に実際に踏んだ。**検査が実物の状態を食っていた**）。
    env["YOUTUBE_STOP_STATE_DIR"] = str(root / "state")
    (root / "state").mkdir(exist_ok=True)
    env.pop("YOUTUBE_PIPELINE_CHILD", None)
    return subprocess.run(
        ["bash", str(root / "scripts" / "probe.sh")],
        capture_output=True, text=True, env=env, timeout=30,
    )


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_no_mark_no_output(tmp_path):
    """**印が無い回（親・会話の回）は、標準出力も標準エラーも空。**"""
    root = _fake_root(tmp_path, marks=[])
    got = _run(root, "cse_PARENTLIKE")
    assert got.stdout == ""
    assert got.stderr == ""
    assert got.returncode == 0


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_no_mark_stays_quiet_even_if_others_ran(tmp_path):
    """**他の子の印があっても黙る。** 見るのは「この回が打ったか」だけ。"""
    root = _fake_root(tmp_path, marks=[{"session": "session_OTHER", "kind": "start"}])
    got = _run(root, "cse_PARENTLIKE2")
    assert got.stdout == ""
    assert got.stderr == ""


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_ran_but_shipped_nothing_is_blocked(tmp_path):
    """**周を回した子は、いままでどおり引き止める**（A9 を殺していないこと）。"""
    root = _fake_root(tmp_path, marks=[{"session": "session_KID", "kind": "start"}])
    got = _run(root, "cse_KID")
    assert '"decision":"block"' in got.stdout
    assert "まだ何も出していません" in got.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_named_parent_is_quiet(tmp_path):
    """名簿に載っている親も黙る（**古い経路。残してあるが、これ単独に頼らない**）。"""
    root = _fake_root(
        tmp_path,
        marks=[{"session": "session_P", "kind": "start"}],
        parents="session_P\n",
    )
    got = _run(root, "cse_P")
    assert got.stdout == ""
    assert got.stderr == ""
