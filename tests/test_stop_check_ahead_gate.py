"""**Stop フックが、先の日付の予約を 0本 にしないまま終わらせないこと。**

## なぜ要るか（2026-09-02・オーナー原文）

> **「1日一本になってないんだけど、今後こういうことが一切ないようにしろ」**

規則5（固定その4）は 08/31 に固定され、それから2日で先の日付の予約は
**459本 → 107本 にしか減っていません**。減らす手（`pool_drain --apply`）は在り、
手順にも書いてあり、何度も名指しされていました。**それでも撃たれなかったのは
「その回が選べば撃つ」形だったから**です（09/01 の実測: `fix` 82% ／ `upload` 0件）。

`scripts/stop_check.sh` の (1.45) はそれを門にしたものです。
**この検査は、その門が「発火したことのない検査」にならないよう、
故障を注入して発火を確かめます**（`CLAUDE.md`「発火したことのない検査は検査ではない」）。

## **無いファイルで鳴らないこと**（2026-09-01 に実物で踏んだ形）

`python3 <無いファイル>` も **exit 2** です。砂場に道具を置いていない検査で
1.4 の門が「穴あり」と読み、**後ろの門を全部 覆い隠していました。**
だから印字が空でないことも見ます —— `test_道具が無い砂場では鳴らない` がそれです。

## 手で `bash scripts/stop_check.sh` を打たないこと

その形の実行は権限判定に掛かり、**無人の子は永久に止まります**
（8/16 07:04 に1件死亡）。**この検査も別名にコピーして打ちます。**
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

#: **この回が周を回したこと**の印（これが無いと、フックは最初から黙ります）。
MARKS = [{"session": "session_KID", "kind": "start"},
         {"session": "session_KID", "kind": "ship", "text": "何か出した"}]


def _root(tmp_path: Path, gate_rc: int | None, gate_out: str = "") -> Path:
    """砂場の repo を作る。`gate_rc` が `None` なら `ahead_gate.py` を置かない。"""
    (tmp_path / "scripts").mkdir()
    (tmp_path / "data").mkdir()
    (tmp_path / "config").mkdir()
    shutil.copy(SRC, tmp_path / "scripts" / "probe.sh")
    (tmp_path / "data" / "runs.jsonl").write_text(
        "".join(json.dumps(m, ensure_ascii=False) + "\n" for m in MARKS),
        encoding="utf-8")
    (tmp_path / "config" / "parents.txt").write_text("", encoding="utf-8")
    # **手前の門を黙らせる。** そうしないと、この門まで届く前に
    # 別の門が引き止め、**この検査は自分の門を1度も見ません**
    # （実際に踏んだ: `drift.py --gate` が先に鳴った）。
    for other in ("drift", "verdict_followup", "deadline_check",
                  "slot_gate", "relay"):
        (tmp_path / "scripts" / f"{other}.py").write_text(
            "raise SystemExit(0)\n", encoding="utf-8")
    if gate_rc is not None:
        (tmp_path / "scripts" / "ahead_gate.py").write_text(
            "import sys\n"
            f"sys.stdout.write({gate_out!r})\n"
            f"raise SystemExit({gate_rc})\n",
            encoding="utf-8")
    return tmp_path


def _run(root: Path, session: str) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_CODE_REMOTE_SESSION_ID"] = session
    # **数え上げの置き場を、この検査の中だけに閉じる**（実物の引き止めを食わない）。
    env["YOUTUBE_STOP_STATE_DIR"] = str(root / "state")
    (root / "state").mkdir(exist_ok=True)
    env.pop("YOUTUBE_PIPELINE_CHILD", None)
    return subprocess.run(
        ["bash", str(root / "scripts" / "probe.sh")],
        capture_output=True, text=True, env=env, timeout=60,
    )


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_故障を注入すると発火する_先の日付に残っている(tmp_path):
    """**注入する故障**: `ahead_gate --gate` が exit 2 ＋ 理由を返す。"""
    root = _root(tmp_path, gate_rc=2, gate_out="[ahead] 先の日付の予約 107本\n")
    got = _run(root, "cse_KID")
    assert '"decision":"block"' in got.stdout
    assert "先の日付に予約が残っています" in got.stderr
    assert "107本" in got.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_0本なら_この門では止めない(tmp_path):
    """**常に止める実装を落とす検査。** 0本の回にこの門の字が出ないこと。"""
    root = _root(tmp_path, gate_rc=0, gate_out="[ahead] 先の日付は空です\n")
    got = _run(root, "cse_KID")
    assert "先の日付に予約が残っています" not in got.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_道具が無い砂場では鳴らない(tmp_path):
    """`python3 <無いファイル>` も exit 2。**印字が空なら鳴らないこと**（09/01 の実測）。"""
    root = _root(tmp_path, gate_rc=None)
    got = _run(root, "cse_KID")
    assert "先の日付に予約が残っています" not in got.stderr


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_引き止めは回数で緩めないこと(tmp_path):
    """**他の門は3回。ここは 12回。**

    通す条件を回数にすると、それが「その回が選べば撃つ」形そのものに戻ります。
    浅くした回は、ここで落ちます。
    """
    text = SRC.read_text(encoding="utf-8")
    block = text.split("(1.45)", 1)[1]
    assert 'AHEADGATE=$(cd "$ROOT" && timeout 60 python3 scripts/ahead_gate.py --gate' in block
    assert '"$AN" -lt 12' in block


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_門が配線されていること():
    """**外したら、ここで分かること。** 削除は diff に出ます。"""
    text = SRC.read_text(encoding="utf-8")
    assert "scripts/ahead_gate.py --gate" in text
    assert "claude-youtube-ahead-blocks-" in text
