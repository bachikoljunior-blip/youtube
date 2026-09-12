"""`scripts/checks.py`（検査の 2つの束）の見張り。

**なぜ**（2026-09-13 08:1x JST・optimizer・Opus）: この撃ち方は `docs/METHOD.md` §7 の
「いまの数」に**恒久の手順 15行**として載っていた側で、道具へ移しました（同 script の註）。
**移したら、守るのは検査です** —— 束の中身・`-x` を付けないこと・旧 `src/` の赤 2件 を
どちらの束にも入れないこと（§8）。**陽性対照つき**（壊したら落ちることを撃って確かめてある）。
"""
from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("checks_script", ROOT / "scripts" / "checks.py")
    mod = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(mod)
    return mod


checks = _load()


def test_studio_bundle_is_the_grep_selection():
    """束の中身は 02:5x の `grep -rln 'from studio import\\|studio\\.' tests/*.py` と同じ file。"""
    grep = subprocess.run(
        ["grep", "-rln", r"from studio import\|studio\.", "tests"],
        cwd=ROOT, capture_output=True, text=True,
    ).stdout.split()
    want = sorted(f for f in grep
                  if f.endswith(".py") and Path(f).name.startswith("test_") and Path(f).name not in checks.OLD_RED)
    assert checks.studio_files() == want
    assert want, "束が空 ＝ 選びが壊れている（`studio` を読む検査は 1件も無いはずがない）"


def test_parent_bundle_has_the_files_the_decisions_name():
    got = checks.parent_files()
    for name in ("tests/test_parent_record_before_spawn.py", "tests/test_spawn_siblings_touched.py"):
        assert name in got, f"親の手続きの束に {name} が無い"
    assert all(p.startswith("tests/") for p in got)
    assert len(got) == len(set(got)), "glob が重なって同じ file を 2度 渡している"


def test_neither_bundle_is_the_whole_tests_dir():
    """決め (2): `tests/` を丸ごと撃たない（旧 `src/` の重い検査で 15分 経っても 12%・§8）。"""
    all_tests = {str(p.relative_to(ROOT)) for p in (ROOT / "tests").glob("test_*.py")}
    both = set(checks.studio_files()) | set(checks.parent_files())
    assert both < all_tests, "束が `tests/` 丸ごとと同じ ＝ 決め (2) が効いていない"


def test_old_red_is_in_neither_bundle():
    """決め (3): 旧 `src/` の赤 2件 は追わない（§8）。"""
    both = set(checks.studio_files()) | set(checks.parent_files())
    for name in checks.OLD_RED:
        assert not any(Path(p).name == name for p in both), f"{name} が束に入っている"


def test_old_red_is_dropped_even_when_it_reads_studio(tmp_path):
    """**陽性対照**: 旧 `src/` の赤が `studio.` を含む形になっても、束に入らない。"""
    d = tmp_path / "tests"
    d.mkdir()
    (d / "test_ceiling_drift.py").write_text("from studio import script\n", encoding="utf-8")
    (d / "test_something_else.py").write_text("from studio import script\n", encoding="utf-8")
    got = [Path(p).name for p in checks.studio_files(d)]
    assert got == ["test_something_else.py"]


def test_studio_pattern_needs_the_word(tmp_path):
    """**陽性対照**: `studio` を読まない検査は束に入らない（語を消したら落ちる側）。"""
    d = tmp_path / "tests"
    d.mkdir()
    (d / "test_no_studio.py").write_text("import json\n\n\ndef test_x():\n    assert json\n", encoding="utf-8")
    (d / "test_yes_studio.py").write_text("import studio.script as s\n", encoding="utf-8")
    assert [Path(p).name for p in checks.studio_files(d)] == ["test_yes_studio.py"]


def test_build_cmd_never_carries_dash_x():
    """決め (1): `-x` は組み立てず、渡されても落とす（赤 1件 で止まると残りが見えない）。"""
    cmd = checks.build_cmd(["tests/test_a.py"], ["-x", "--exitfirst", "-p", "no:cacheprovider"])
    assert "-x" not in cmd and "--exitfirst" not in cmd
    assert cmd[:4] == [sys.executable, "-m", "pytest", "-q"]
    assert cmd[-1] == "tests/test_a.py"
    assert "-p" in cmd and "no:cacheprovider" in cmd, "`-x` 以外の引数まで落としている"


def test_build_cmd_passes_every_file_by_name():
    files = ["tests/test_a.py", "tests/test_b.py"]
    cmd = checks.build_cmd(files)
    assert cmd[-2:] == files


def test_tail_counts_reads_the_summary_line():
    assert checks._tail_counts("...\n906 passed in 80.73s (0:01:20)\n") == "906 passed in 80.73s (0:01:20)"
    assert checks._tail_counts("...\n1 failed, 5 passed in 2.0s\n") == "1 failed, 5 passed in 2.0s"


def test_unknown_bundle_stops_loudly():
    """黙って 0件 を返さないこと（`method_growth` の覆る条件 (3) と同じ向き）。"""
    try:
        checks.files_for("hourly")
    except KeyError:
        return
    raise AssertionError("知らない束に KeyError を投げていない")


def test_list_prints_both_bundles_and_the_old_red_line():
    r = subprocess.run([sys.executable, "scripts/checks.py", "--list"], cwd=ROOT, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert re.search(r"^studio: \d+ file$", r.stdout, re.M)
    assert re.search(r"^parent: \d+ file$", r.stdout, re.M)
    assert "旧 src の赤 2件" in r.stdout


def test_method_points_at_this_tool_instead_of_carrying_the_commands():
    """METHOD の「いまの数」は、撃ち方を抱えずここを指すこと（08:1x の決め）。"""
    method = (ROOT / "docs" / "METHOD.md").read_text(encoding="utf-8")
    assert "scripts/checks.py" in method, "METHOD からこの道具を指していない"
    head = method.index("### いまの数")
    tail = method.index("次に見る所", head)
    now = method[head:tail]
    assert "grep -rln" not in now, "「いまの数」が撃ち方（grep の行）を抱えたまま ＝ 08:1x の削りが戻っている"
