"""**出したものを予測へ入れ直さないまま、回を終われないこと。**

## なぜ要るか（2026-08-20・オーナー指示。原文）

> 毎回の実行で予測するように言ったはずなので、毎回その予測に反映して

予測は回の**最初**に出ます（`CLAUDE.md` 1）。腕を引いたのはそのあとなので、
撃ち直すまで**出したものはどの日付にも入っていません。**

**置き場所を `docs/trigger_main.md` にしないこと。** あれは 197KB で、
§3 が読み飛ばされた記録があります（2026-08-18 23:4x）。機械的に必ず入るのは
フックの文字列・`CLAUDE.md`・**走って落ちるもの**の3つだけです。ここは3つ目。

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

from src import reflect

ROOT = Path(__file__).resolve().parent.parent
SESSION = "cse_REFLECTTEST"
ME = f"session_{SESSION[4:]}"


def _ledger(tmp_path: Path, *, eta_at: str | None) -> Path:
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "runs.jsonl").write_text("\n".join([
        json.dumps({"at": "2026-08-20T20:00:00+09:00", "session": ME, "kind": "start"}),
        json.dumps({"at": "2026-08-20T21:00:00+09:00", "session": ME, "kind": "ship",
                    "what": "何かを出した", "lever": "per_video", "moves": -3,
                    "eta_target": "2026-11-29"}, ensure_ascii=False),
    ]) + "\n", encoding="utf-8")
    if eta_at is not None:
        (tmp_path / "data" / "eta.jsonl").write_text(
            json.dumps({"at": eta_at, "target_date": "2026-11-29"}) + "\n", encoding="utf-8")
    return tmp_path


def test_出したのに撃ち直していなければ鳴る(tmp_path):
    # eta の点は ship（＝12:00Z）より **前**。作業前の予測しか無い
    p = reflect.pending(_ledger(tmp_path, eta_at="2026-08-20T11:15:00+00:00"))
    assert p is not None
    assert p["lever"] == "per_video"
    body = "\n".join(reflect.lines(tmp_path))
    assert "作業の前の日付" in body
    assert "eta.py" in body, "何をすれば消えるかが出ていません"


def test_撃ち直してあれば黙る(tmp_path):
    """ship（21:00+09:00 ＝ 12:00Z）より **後** の点が1つあれば足りる。"""
    assert reflect.pending(_ledger(tmp_path, eta_at="2026-08-20T12:30:00+00:00")) is None
    assert reflect.lines(_ledger(tmp_path, eta_at="2026-08-20T12:30:00+00:00")) == []


def test_時刻の書き方が混ざっていても比べられる(tmp_path):
    """台帳は `+09:00`、eta は `+00:00` で積まれています。**素の文字列比較は嘘をつきます。**"""
    assert reflect.pending(_ledger(tmp_path, eta_at="2026-08-20T13:00:00+00:00")) is None


def test_出していない回では鳴らない(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "runs.jsonl").write_text(
        json.dumps({"at": "2026-08-20T20:00:00+09:00", "session": ME, "kind": "start"}) + "\n",
        encoding="utf-8")
    assert reflect.pending(tmp_path) is None


def test_台帳が無くても壊れていても回を殺さない(tmp_path):
    """**計器が落ちても終われること。** ここを「読めなければ止める」にすると回が全部死ぬ。"""
    assert reflect.pending(tmp_path) is None                     # 台帳そのものが無い
    root = _ledger(tmp_path, eta_at=None)                        # eta が1点も無い
    assert reflect.pending(root) is not None                     # ← これは鳴る（撃ち直していない）
    (root / "data" / "runs.jsonl").write_text("{{{壊れた\n", encoding="utf-8")
    assert reflect.pending(root) is None


def test_この回だけを見る指定(tmp_path):
    """フックは**自分の回**を見ます。よその回の ship で引き止めない。"""
    root = _ledger(tmp_path, eta_at="2026-08-20T11:15:00+00:00")
    assert reflect.pending(root, session=ME) is not None
    assert reflect.pending(root, session="session_よそ") is None


# --- 走って落ちる側（フック） -------------------------------------------------

def _hook_root(tmp_path: Path, *, eta_at: str | None) -> Path:
    for d in ("scripts", "config", "state"):
        (tmp_path / d).mkdir(exist_ok=True)
    shutil.copy(ROOT / "scripts" / "stop_check.sh", tmp_path / "scripts" / "probe.sh")
    shutil.copytree(ROOT / "src", tmp_path / "src")
    (tmp_path / "config" / "parents.txt").write_text("", encoding="utf-8")
    return _ledger(tmp_path, eta_at=eta_at)


def _run(root: Path) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    env["CLAUDE_CODE_REMOTE_SESSION_ID"] = SESSION
    env["YOUTUBE_STOP_STATE_DIR"] = str(root / "state")
    env.pop("YOUTUBE_PIPELINE_CHILD", None)
    return subprocess.run(["bash", str(root / "scripts" / "probe.sh")],
                          capture_output=True, text=True, env=env, timeout=60)


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_フックが引き止める(tmp_path):
    got = _run(_hook_root(tmp_path, eta_at="2026-08-20T11:15:00+00:00"))
    assert "予測に入っていません" in got.stderr, got.stderr[:400]
    assert '"decision":"block"' in got.stdout


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_フックは三回で通す(tmp_path):
    """**止まったまま死ぬほうが確実に悪い**ので、無限には引き止めない。"""
    root = _hook_root(tmp_path, eta_at="2026-08-20T11:15:00+00:00")
    for _ in range(3):
        assert "予測に入っていません" in _run(root).stderr
    assert "予測に入っていません" not in _run(root).stderr


@pytest.mark.skipif(sys.platform == "win32", reason="bash が要る")
def test_撃ち直してあればフックは黙る(tmp_path):
    got = _run(_hook_root(tmp_path, eta_at="2026-08-20T12:30:00+00:00"))
    assert "予測に入っていません" not in got.stderr
    assert got.returncode == 0


def test_statusの先頭が同じ判定を出している():
    """**印字の側を消さないこと。** 消すと、前の回の取りこぼしが誰にも見えなくなる。"""
    body = (ROOT / "scripts" / "status.py").read_text(encoding="utf-8")
    assert "_reflect.lines()" in body
    assert body.index("_reflect.lines()") < body.index("return _channel_main(days)")


def test_CLAUDEmdに手順が載っている():
    """**必ず読まれる2つ目**（セッション開始時に自動で入る）。文書だけに逃がさない。"""
    body = (ROOT / "CLAUDE.md").read_text(encoding="utf-8")
    assert "予測へ入れ直す" in body
