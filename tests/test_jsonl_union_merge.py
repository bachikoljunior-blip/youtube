"""**追記専用のファイルを、合流で選ばせない**（2026-08-20 09:5x）。

## なぜ要るか

`data/*.jsonl` は観測を1行ずつ足すだけで、**どちらかを選ぶ場面がありません。**
それでも既定の合流は衝突と言い、`docs/trigger_main.md` §6 (b) は
「マーカー3行を落として、残った行を全部残す」と**手順で**書いていました。

**手でやると消えます。** 2026-08-20 09:4x、この枝に押している別の回が
**`data/watch.jsonl` を空にして押し**、428行を戻す commit を別に押しています（d6aaec4）。
同じ日に、こちらも1周のうちに3回まわしました
（いまこの枝には、毎時の回とオーナー指示の回が**3つ**押しています）。

`union` は git の組み込みの合流方式で、**両側の行をそのまま残します。**
ここで見るのは「書いてあるか」ではなく、**実際に合流させて衝突しないこと**です。
"""
from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_data_の_jsonl_は_union_で合流する():
    """**`.gitattributes` の行を読むだけでは足りません**（効いているかは git が決める）。"""
    got = subprocess.run(
        ["git", "check-attr", "merge", "--", "data/quota.jsonl"],
        cwd=ROOT, capture_output=True, text=True, check=True).stdout
    assert "merge: union" in got, f"効いていません: {got!r}"


def test_両側の追記が両方とも残る(tmp_path):
    """**実際に合流させること。** 消えるのは、いつも解決の側です。"""
    def git(*a, cwd=tmp_path):
        return subprocess.run(["git", *a], cwd=cwd, capture_output=True,
                              text=True, check=True).stdout

    (tmp_path / "data").mkdir()
    git("init", "-q", "-b", "main", ".")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    (tmp_path / ".gitattributes").write_text(
        (ROOT / ".gitattributes").read_text(encoding="utf-8"), encoding="utf-8")
    f = tmp_path / "data" / "views.jsonl"
    f.write_text('{"n": 1}\n', encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base")

    git("checkout", "-q", "-b", "side")
    f.write_text('{"n": 1}\n{"n": "side"}\n', encoding="utf-8")
    git("commit", "-qam", "side")
    git("checkout", "-q", "main")
    f.write_text('{"n": 1}\n{"n": "main"}\n', encoding="utf-8")
    git("commit", "-qam", "main")

    merged = subprocess.run(["git", "merge", "--no-edit", "side"],
                            cwd=tmp_path, capture_output=True, text=True)
    assert merged.returncode == 0, f"衝突しています:\n{merged.stdout}{merged.stderr}"
    got = f.read_text(encoding="utf-8")
    assert '{"n": "side"}' in got and '{"n": "main"}' in got, got
    assert "<<<<<<<" not in got
