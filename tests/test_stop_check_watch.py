"""Stop フックは、**満ちた待ちに答えないまま終わらせない**こと。

## なぜ要るか（2026-08-20。オーナー「これからも同じことにならないようにするんだよ」）

8/10〜8/20、`scripts/retention.py` は「30秒設計の3本が出れば測れるようになります」と
**正しく印字していました。3本は 8/18 に出て、誰も気づきませんでした。**

条件を `config/watches.yaml` に移して毎周 `status.py` に出すところまでは
**印字の格上げでしかありません** —— 出ていても、読まずに終われる。
**止めるのはここです。**

## 手で `bash scripts/stop_check.sh` を打たないこと

その形の実行は権限判定に掛かり、無人の子は永久に止まります
（`tests/test_stop_check_quiet.py` の冒頭）。**別名にコピーして打ちます。**
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

SESSION = "cse_WATCHTEST"

#: 尺の違う2本。`length_spread` の分母になる。
SCAN = {"at": "2026-08-20T00:00:00+09:00", "values": {
    "動画.aaa.views": 100, "動画.aaa.尺": 30,
    "動画.bbb.views": 100, "動画.bbb.尺": 60}}

WATCH = """
watches:
  - id: 試験の待ち
    what: 試しの判定
    cond: 尺のばらつきが 0 以上（＝必ず満ちる）
    then: python scripts/試しを走らせる.py
    source: tests
    kind: length_spread
    need: 0.0
    min_views: 1
{answered}
exempt: {{}}
"""


def _root(tmp_path: Path, answered: str = "") -> Path:
    (tmp_path / "scripts").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config").mkdir()
    (tmp_path / "state").mkdir()
    shutil.copy(SRC, tmp_path / "scripts" / "probe.sh")
    shutil.copytree(ROOT / "src", tmp_path / "src")
    (tmp_path / "data" / "runs.jsonl").write_text(
        json.dumps({"session": f"session_{SESSION[4:]}", "kind": "ship",
                    "what": "何か"}, ensure_ascii=False) + "\n", encoding="utf-8")
    (tmp_path / "data" / "scan.jsonl").write_text(
        json.dumps(SCAN, ensure_ascii=False) + "\n", encoding="utf-8")
    (tmp_path / "config" / "parents.txt").write_text("", encoding="utf-8")
    (tmp_path / "config" / "watches.yaml").write_text(
        WATCH.format(answered=('    answered: "2026-08-20 判定済み"' if answered else "")),
        encoding="utf-8")
    return tmp_path


def _run(root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_CODE_REMOTE_SESSION_ID"] = SESSION
    env["YOUTUBE_STOP_STATE_DIR"] = str(root / "state")
    env.pop("YOUTUBE_PIPELINE_CHILD", None)
    return subprocess.run(["bash", str(root / "scripts" / "probe.sh")],
                          capture_output=True, text=True, env=env, timeout=60)


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_満ちて答えの無い待ちがあると引き止める(tmp_path):
    got = _run(_root(tmp_path))
    assert "満ちた待ち" in got.stderr, got.stderr[:400]
    assert "試験の待ち" in got.stderr, "どの待ちかが出ていません"
    assert "試しを走らせる" in got.stderr, "走らせるものが出ていません"
    assert '"decision":"block"' in got.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_三回で通す(tmp_path):
    """**止まったまま死ぬほうが確実に悪い**ので、無限には引き止めない。"""
    root = _root(tmp_path)
    for _ in range(3):
        assert "満ちた待ち" in _run(root).stderr
    assert "満ちた待ち" not in _run(root).stderr


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_答えが書いてあれば引き止めない(tmp_path):
    got = _run(_root(tmp_path, answered="yes"))
    assert "満ちた待ち" not in got.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_台帳が読めない回でも回を殺さない(tmp_path):
    """**計器が落ちても終われること。** 台帳が壊れていたら黙って通す。

    ここを「読めなければ引き止める」にすると、**壊れた台帳で回が全部死にます。**
    """
    root = _root(tmp_path)
    (root / "config" / "watches.yaml").write_text("watches: [[[", encoding="utf-8")
    got = _run(root)
    assert "満ちた待ち" not in got.stderr
    assert got.returncode == 0
