"""**機械が自分で自分を止められないことを、検査で床にする。**（2026-08-31）

オーナー原文（`AUTOMATION_PAUSED.md` を見せたうえで、2つ）:

    > **「だから俺はそんなの決めてないから、勝手にそれで止まるのなし。
    >    今後そういうことがないようにして」**
    > **「既存のもの外すだけじゃなくて同じことが起こらないようにして」**

**何が起きたか（事実だけ）**: 2026-08-30、`AUTOMATION_PAUSED.md` という
**ファイル1枚**が置かれ、生成・投稿・予約の変更が全部 止まりました。
**約22時間・4周ぶんの生成が落ちています。** 2026-08-31、オーナー本人が
GitHub の画面からそのファイルを削除しました（commit `1aa1e65a`）。
**「既存のもの外す」はそこで済んでいます。この検査は「同じことが起こらないように」**
のほうです。

**なぜ「文書に書く」では足りないか**: この repo でいちばん多い壊れ方は
**「言っている所と、している所が別」**です（`CLAUDE.md` が何度もそう書いています ——
配色の節・密度の上限の節）。規則を文書に置くと、**次に来た側が読まずに書き直せます。**
**だから検査にします。戻すには、この検査を消すしかありません**（消せば diff に出ます）。

**この検査が見ている4つ**:

    1. `AUTOMATION_PAUSED.md` が在るだけでは止まらないこと
       （止まるには `.owner-pause` が要る ＝ **人の手**が要る）
    2. 止まるかどうかの判定が**1か所**しかないこと
       —— 4か所（`src/pause_guard`・`src/resume_gate`・`scripts/policy_pause.sh`・
       `scripts/spawn_prompt.py`）に散っていたので、**片方だけ直した回が
       「動いているのに停止中と印字する」**形を作れました
    3. **その印を作るコードが、この repo に1行も無いこと**
       —— 足せば、それは「勝手に止まる」ことそのものです
    4. `.gitignore` がその印を隠さないこと
       —— オーナーは GitHub の画面から repo を触ります（08/31 の削除も画面から）。
       無視されると、置いても届きません

**覆る条件**: オーナーが「止めろ」と言ったとき。そのときは `.owner-pause` を
**人の手で**置くこと。**機械が置いてはいけません。**
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import pause_guard, resume_gate  # noqa: E402


# ---------------------------------------------------------------- 1. 1枚では止まらない

def test_停止の文書が在るだけでは止まらない(tmp_path, monkeypatch):
    """**ファイル1枚では止まりません。** これが今回の床そのものです。

    2026-08-30 の判定は `PAUSE_FILE.is_file()` **だけ**でした。
    **その1枚は、この repo のどの回でも書けます。**
    """
    doc = tmp_path / "AUTOMATION_PAUSED.md"
    doc.write_text("# AUTOMATION PAUSED — 2026-08-30\n", encoding="utf-8")
    monkeypatch.setattr(pause_guard, "PAUSE_FILE", doc)
    monkeypatch.setattr(pause_guard, "OWNER_PAUSE_MARKER", tmp_path / ".owner-pause")

    assert pause_guard.is_paused() is False


def test_オーナーの印を人が置いたときだけ止まる(tmp_path, monkeypatch):
    """**外したのは「機械が止める力」であって、オーナーが止める道ではありません。**

    印を手で置けば、`BLOCKED_ENTRYPOINTS` は今までどおり全部 止まります。
    **止める中身は1つも減らしていません。**
    """
    marker = tmp_path / ".owner-pause"
    monkeypatch.setattr(pause_guard, "PAUSE_FILE", tmp_path / "AUTOMATION_PAUSED.md")
    monkeypatch.setattr(pause_guard, "OWNER_PAUSE_MARKER", marker)

    assert pause_guard.is_paused() is False
    marker.write_text("", encoding="utf-8")
    assert pause_guard.is_paused() is True

    with pytest.raises(RuntimeError):
        pause_guard._raise_if_blocked({"pipeline.py"})
    pause_guard._raise_if_blocked({"status.py"})  # 読むだけの道具は通ること


def test_いまこの_repo_は止まっていない():
    """**実物で見ます。**

    オーナーが 08/31 に `AUTOMATION_PAUSED.md` を消し、印は置いていません。
    ここが False でなくなるのは、**誰かが `.owner-pause` を置いたとき**だけです。
    """
    assert pause_guard.OWNER_PAUSE_MARKER.exists() is False
    assert pause_guard.is_paused() is False


# ---------------------------------------------------------------- 2. 判定は1か所

def test_止まるかどうかの判定は1か所しかない(tmp_path, monkeypatch):
    """**床が散らばっていないこと。**

    `src/resume_gate` は 2026-08-31 まで `PAUSE_FILE.is_file()` を**独立に**
    見ていました。片方だけ直すと、**動いているのに「停止中」と印字する**形が
    作れます。**同じ問いに2つの答えがある状態**は、この repo が何度も踏んだ形です。
    """
    assert resume_gate.is_paused() is pause_guard.is_paused()

    # 委譲していれば、片方を動かしたときに両方 動きます（写しなら動きません）。
    monkeypatch.setattr(pause_guard, "OWNER_PAUSE_MARKER", tmp_path / ".owner-pause")
    (tmp_path / ".owner-pause").write_text("", encoding="utf-8")
    assert pause_guard.is_paused() is True
    assert resume_gate.is_paused() is True


def test_判定を独立に書いた場所がもう無い():
    """**停止をファイルの有無で判定するコードが、`src/pause_guard.py` の外に無いこと。**

    文書を**読む**のは構いません（`resume_gate._pause_text()` は Resume gate の
    本文を読むだけ）。禁じているのは「**有無を問うこと**」です。
    """
    offenders: list[str] = []
    pat = re.compile(
        r"""(AUTOMATION_PAUSED\.md|\.owner-pause)["']?\s*\)?\s*\.\s*(is_file|exists)\s*\(\)"""
        r"""|(PAUSE_FILE|OWNER_PAUSE_MARKER)\s*\.\s*(is_file|exists)\s*\(\)"""
        r"""|\[\[\s*!?\s*-[fes]\s+AUTOMATION_PAUSED\.md\s*\]\]"""
    )
    targets = (list(ROOT.glob("src/**/*.py"))
               + list(ROOT.glob("scripts/**/*.py"))
               + list(ROOT.glob("scripts/**/*.sh")))
    for path in sorted(targets):
        if path == ROOT / "src" / "pause_guard.py":
            continue
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if pat.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
    assert not offenders, (
        "停止の判定は `src/pause_guard.is_paused()` 1か所だけです。"
        "ここに出た行は、独立にファイルの有無を見ています:\n" + "\n".join(offenders)
    )


def test_サブに配る本文も同じ床を見ている():
    """**親は動くのに、子だけ止まる**形を作らないこと。

    `scripts/spawn_prompt.py` は 08/31 まで `AUTOMATION_PAUSED.md` の有無を
    独立に見ていました。親からは見えないので、いちばん気づきにくい形です。
    """
    out = subprocess.run(
        [sys.executable, "scripts/spawn_prompt.py", "--kind", "hourly"],
        cwd=ROOT, capture_output=True, text=True, timeout=600,
    )
    assert out.returncode == 0, out.stderr
    assert "【停止中】" not in out.stdout


def test_毎ターンの差し込みも同じ床を見ている():
    """`scripts/policy_pause.sh` が停止の札を流し込まないこと。

    ここが独立していると、**機械は動けるのに、読んだ側が全員
    「止まっている」と思い込みます。**（フックなので、いちばん強く効きます）
    """
    out = subprocess.run(
        ["bash", "scripts/policy_pause.sh"],
        cwd=ROOT, capture_output=True, text=True, timeout=120,
    )
    assert out.returncode == 0, out.stderr
    assert "PAUSED" not in out.stdout


# ---------------------------------------------------------------- 3. 印を作るコードが無い

def test_この印を作るコードが_repo_に無い():
    """**ここが、この回のいちばんの床です。**

    印を作れるコードが1行でもあれば、**機械はまた自分で自分を止められます。**
    `.owner-pause` へ**書き込む・触る・作る**行を探して、あったら落とします。
    """
    marker = pause_guard.OWNER_PAUSE_MARKER.name
    esc = re.escape(marker)
    # **読むのは通します。書くのだけを落とします。**（`git log -- .owner-pause` や
    # `[ -e .owner-pause ]` は「誰が置いたか」を人に見せるためのもので、印を作りません）
    write_pat = re.compile(
        # python: `OWNER_PAUSE_MARKER.touch()` / `(ROOT / ".owner-pause").write_text(...)`
        r"""OWNER_PAUSE_MARKER\s*\.\s*(touch|write_text|write_bytes|mkdir|open)\s*\("""
        + r"""|""" + esc + r"""["'\)\]]*\s*\)?\s*\.\s*(touch|write_text|write_bytes|mkdir|open)\s*\("""
        + r"""|open\s*\([^)\n]*""" + esc + r"""[^)\n]*,\s*["'][wax]"""
        # shell: `touch .owner-pause` / `echo ... > .owner-pause` / `tee .owner-pause`
        + r"""|\b(touch|tee|install|cp|mv)\b[^\n|;&]{0,40}""" + esc
        + r"""|>>?\s*["']?[^\s|;&"'`]*""" + esc
    )
    offenders: list[str] = []
    candidates = (list(ROOT.glob("src/**/*.py"))
                  + list(ROOT.glob("scripts/**/*"))
                  + list(ROOT.glob(".github/**/*.yml")))
    for path in sorted(candidates):
        if not path.is_file() or path.suffix not in {".py", ".sh", ".yml", ".yaml", ""}:
            continue
        try:
            body = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        if marker not in body:
            continue
        for i, line in enumerate(body.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if write_pat.search(line):
                offenders.append(f"{path.relative_to(ROOT)}:{i}: {line.strip()}")
    assert not offenders, (
        f"`{marker}` を作るコードが repo に入っています。**それは「勝手に止まる」"
        "ことそのものです。** 印はオーナーが手で置くものです:\n" + "\n".join(offenders)
    )


def test_印が_gitignore_で隠されていない():
    """オーナーは GitHub の画面から repo を触ります（08/31 の削除も画面から）。

    `.gitignore` に入れると、**置いても届きません。**
    """
    path = ROOT / ".gitignore"
    if not path.exists():
        return
    name = pause_guard.OWNER_PAUSE_MARKER.name
    lines = [ln.strip() for ln in path.read_text(encoding="utf-8").splitlines()]
    assert name not in lines and name.lstrip(".") not in lines, (
        f"`{name}` を `.gitignore` に入れないこと（オーナーが置いても届かなくなります）"
    )


# ---------------------------------------------------------------- 4. 止める中身は減らしていない

def test_何を止めるかの一覧は残っている():
    """**外したのは「機械が自分で全部を止められる」経路だけ**です。

    印が置かれたときに何を止めるかの一覧（`BLOCKED_ENTRYPOINTS`）は、
    **止める仕掛けではなく止め方の中身**なので残します。
    """
    assert {"pipeline.py", "uploader.py", "batch_build.py"} <= pause_guard.BLOCKED_ENTRYPOINTS
