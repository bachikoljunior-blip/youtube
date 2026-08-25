"""**回の最初に環境が落ちていたら、回が始まる前に直っていること。**

2026-08-21 11:1x の回は、いちばん最初の `python scripts/eta.py` が
`ModuleNotFoundError: No module named 'googleapiclient'` で落ち、
`scripts/status.py` は `_cffi_backend` が無く pyo3 が panic しました。
**`scripts/setup.sh` は直せる中身を持っていたのに、誰も呼びません。**

だから `scripts/env_guard.sh` を SessionStart フックに置きました。
**この検査は、その配線が外れていないことだけを見ます**（実際の pip は叩きません）。
配線が外れると、次にコンテナが作り直された回が**また症状から辿ります。**
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GUARD = ROOT / "scripts" / "env_guard.sh"
SETTINGS = ROOT / ".claude" / "settings.json"


def _hooks() -> dict:
    return json.loads(SETTINGS.read_text(encoding="utf-8"))["hooks"]


def test_env_guard_があること() -> None:
    assert GUARD.exists(), f"{GUARD} がありません"


def test_env_guard_の文法が通ること() -> None:
    proc = subprocess.run(["bash", "-n", str(GUARD)],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_SessionStart_で呼ばれていること() -> None:
    starts = _hooks().get("SessionStart")
    assert starts, ".claude/settings.json に SessionStart がありません"
    cmds = [h["command"] for group in starts for h in group["hooks"]]
    assert any("env_guard.sh" in c for c in cmds), (
        f"SessionStart から env_guard.sh を呼んでいません: {cmds}")


def test_健康なときは何も出さずに素早く終わること() -> None:
    """**フックなので、健康な回の邪魔をしないこと。**"""
    proc = subprocess.run(["bash", str(GUARD)], capture_output=True,
                          text=True, cwd=ROOT, timeout=120)
    assert proc.returncode == 0, proc.stderr
    # いまこの検査が動いている＝ python 側は揃っているので、直しには入らない
    assert "入れ直します" not in proc.stderr, proc.stderr


def test_直し方が_ignore_installed_であること() -> None:
    """**`--upgrade` では直りません**（RECORD が無く剥がせない）。実測 2026-08-21。"""
    text = GUARD.read_text(encoding="utf-8")
    assert "--ignore-installed" in text, (
        "ディストリの cryptography は剥がせないので、--ignore-installed で"
        "上に置くしかありません（--upgrade は Cannot uninstall で止まります）")


def test_setup_sh_も_import_で確かめていること() -> None:
    """`pip install -r requirements.txt` は**成功しても import が通らない**ことがある。"""
    text = (ROOT / "scripts" / "setup.sh").read_text(encoding="utf-8")
    assert "google.oauth2.credentials" in text, (
        "setup.sh が、入ったかどうかを実際の import で確かめていません")
    assert "--ignore-installed cffi cryptography" in text, (
        "setup.sh に、ディストリの cryptography を上書きする手が入っていません")


def test_import_の一式が実際に通ること() -> None:
    """**この検査が通る＝この回は API を叩ける。** 落ちたら env_guard が仕事をしていない。"""
    proc = subprocess.run(
        [sys.executable, "-c",
         "from google.oauth2.credentials import Credentials\n"
         "import googleapiclient.discovery, yaml, pydantic, numpy, pytest"],
        capture_output=True, text=True, cwd=ROOT, timeout=120)
    assert proc.returncode == 0, proc.stderr[-800:]
