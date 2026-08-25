"""**作り始める前に、道具が入っているかを見る**ことを固定する。

## なぜ要るか（2026-08-22 に実測）

この回のコンテナには **ffmpeg も ffprobe も open_jtalk も入っていませんでした。**
`scripts/setup.sh` は「何度でも安全」と書いてあるのに、**生成の道の上で
誰も呼んでいません** —— `scripts/preflight.py` はまったく同じ検査
（`shutil.which`）を持っているのに、`batch_build` からも `src.pipeline` からも
呼ばれていませんでした。**検査はあった。道の上に無かった**だけです。

実測の損: **3本 × 2回 ＝ 約8分**を使ってから `ffprobe が見つかりません` で
全部落ちました。1周は実測 44分なので、**その回の2割**です。

**そして症状が理由を隠しました。** 1回目に落ちたのは図の重なりの門
（`台本の時点で過去の図と重なっています`）で、道具が無いことは
**作り直しの側にしか出ません。** 読む側からは「テーマが悪い」に見えます。

だから検査するのは「setup.sh が動くか」ではなく、次の2つです。

1. **欠けていたら、作る前に気づく**（`build_one` へ1本も入れない）
2. **揃っていたら、何も撃たない**（普通の回の費用がゼロであること）
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import batch_build  # noqa: E402


def test_要る道具の一覧に音と動画の両方がある():
    """**片方だけでは落ちます。** 音は open_jtalk、尺の測りは ffprobe。"""
    assert set(batch_build.NEEDED_BINS) == {"ffmpeg", "ffprobe", "open_jtalk"}


def test_揃っていれば何も撃たない(monkeypatch):
    """普通の回の費用はゼロ。**`setup.sh` を呼んだら失敗**とする。"""
    monkeypatch.setattr(batch_build.shutil, "which", lambda name: f"/usr/bin/{name}")

    def 撃ってはいけない(*a, **k):                      # pragma: no cover
        raise AssertionError("道具が揃っているのに setup.sh を撃ちました")

    monkeypatch.setattr(batch_build.subprocess, "run", 撃ってはいけない)
    assert batch_build.ensure_toolchain() is True


def test_欠けていたら_setupを撃って入れ直す(monkeypatch):
    """**訊かずに撃つ**（CLAUDE.md 2「人間の作業に依存する計画を立てない」）。"""
    入った: list[str] = []
    撃った: list[list[str]] = []

    def which(name):
        return f"/usr/bin/{name}" if name in 入った else None

    def run(cmd, **k):
        撃った.append(cmd)
        入った.extend(batch_build.NEEDED_BINS)          # setup.sh が入れた
        return batch_build.subprocess.CompletedProcess(cmd, 0, "準備完了", "")

    monkeypatch.setattr(batch_build.shutil, "which", which)
    monkeypatch.setattr(batch_build.subprocess, "run", run)

    assert batch_build.ensure_toolchain() is True
    assert len(撃った) == 1, "setup.sh は1回だけ"
    assert 撃った[0][0] == "bash" and 撃った[0][1].endswith("scripts/setup.sh")


def test_撃っても入らなければ作り始めない(monkeypatch):
    """**False を返すこと。** ここで止めないと、8分先で3本とも落ちます。"""
    monkeypatch.setattr(batch_build.shutil, "which", lambda name: None)
    monkeypatch.setattr(
        batch_build.subprocess, "run",
        lambda cmd, **k: batch_build.subprocess.CompletedProcess(cmd, 1, "だめでした", ""),
    )
    assert batch_build.ensure_toolchain() is False


def test_setupが終わらなければ作り始めない(monkeypatch):
    """**待ち続けないこと。** 1周は実測 44分で、15分は既に3分の1です。"""
    def timeout(cmd, **k):
        raise batch_build.subprocess.TimeoutExpired(cmd, k.get("timeout", 900))

    monkeypatch.setattr(batch_build.shutil, "which", lambda name: None)
    monkeypatch.setattr(batch_build.subprocess, "run", timeout)
    assert batch_build.ensure_toolchain() is False


def test_preflightと同じ道具を見ている():
    """**2か所に分かれた瞬間に古くなります**（`docs/TRIGGER.md` の「写した瞬間に古くなる」）。

    `preflight.py` が見ていて `batch_build` が見ていないものが出たら、
    そこがまた「8分先で落ちる」入口になります。
    """
    text = (ROOT / "scripts" / "preflight.py").read_text(encoding="utf-8")
    for name in batch_build.NEEDED_BINS:
        assert f'"{name}"' in text, f"preflight.py が {name} を見ていません"


@pytest.mark.parametrize("bins", [("ffmpeg",), ("ffprobe",), ("open_jtalk",)])
def test_1つでも欠けたら撃つ(monkeypatch, bins):
    """**全部欠けている回だけではありません。** open_jtalk だけ無い回が実在します
    （`setup.sh` の apt が途中で落ちると、ffmpeg は入って音だけ入りません）。
    """
    欠け = set(bins)
    撃った: list = []
    monkeypatch.setattr(batch_build.shutil, "which",
                        lambda n: None if n in 欠け else f"/usr/bin/{n}")

    def run(cmd, **k):
        撃った.append(cmd)
        欠け.clear()
        return batch_build.subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(batch_build.subprocess, "run", run)
    assert batch_build.ensure_toolchain() is True
    assert len(撃った) == 1
