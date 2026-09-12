"""この repo の検査を、意味のある **2つの束**で撃つ（API 0単位・pytest だけ）。

    python scripts/checks.py                # 2束 とも撃つ
    python scripts/checks.py studio         # `studio/` を読む検査だけ
    python scripts/checks.py parent         # 親の手続き（`scripts/quota.py`・`next_round.py`・`spawn_prompt.py`）の検査だけ
    python scripts/checks.py --list         # 撃たずに、束ごとの件数と file を並べる

**なぜ道具にしたか**（2026-09-13 08:1x JST・optimizer・Opus）:
この撃ち方は `docs/METHOD.md` §7 の「いまの数」（**毎周 上書き**・**数と口の名だけ**を置く塊）に
**15行の恒久の手順**として載っていました —— 数でも口の名でもないのに、**2体 が毎周 読む側**に在り、
しかも「906件 33秒」のような**その日の実測**を抱えたまま古くなっていきます。
METHOD が繰り返し書いている形（**門は、読む人ではなく道具が見る**・`trend` / `method_growth` と同じ扱い）を
当てて、**METHOD からは 1行 でここを指す**ようにしました。derivation は `docs/JOURNAL.md` 09/13 08:1x。

**束の選び方**（METHOD 02:5x／06:3x の実測をそのまま道具にした）:

    studio   `tests/*.py` のうち **`from studio import` か `studio.` を含む file**
             —— 「`studio/` を直した回は、この選びで足ります」（02:5x）
    parent   `test_quota*` `test_next_round*` `test_parent*` `test_spawn*` `test_fable*`
             `test_model_by_role.py` `test_role_model.py` `test_pace*`
             —— 「`scripts/quota.py` を直した回は、この選びで足ります。
                 `studio` の側は 1件も読みません」（06:3x に測った）

**決め 3つ**（守るのは道具の側。次の回は覚えていなくてよい）:

    (1) **`-x` は付けない** —— 赤 1件 で止まると、残りの赤が見えません。
        `build_cmd()` は `-x` を組み立てず、`extra` に混ぜても落とします（検査つき）。
    (2) **`tests/` を丸ごと撃たない** —— 旧 `src/` の重い検査で **15分 経っても 12%**（§8）。
        この道具は束の file を名指しでしか渡しません。
    (3) **旧 `src/` の赤 2件**（`test_ceiling_drift` / `test_form_record`）は
        **2026-09-09 08:5x から前のまま**・§8 のとおり**追わない** ＝ どちらの束にも入れません
        （`OLD_RED` ＝ 入っていないことを検査が見ています）。

**秒は印字しますが、どこにも書き置きません** —— 同じ束でも機械の混み具合で 33秒 にも 81秒 にもなります
（09/13 08:1x の実測: studio 80.7秒 ／ parent 33.6秒。02:5x の実測は 33秒 ／ 22秒）。
**METHOD へ秒を写さないこと。**

**覆る条件**:
 (1) `studio/` でも親の手続きでもない所を直した回が **2回** 続いたら、束は 2つ では足りない
     ＝ 3つ目の束（または `--files` で渡す口）をここへ足すこと。
 (2) `studio` の束が `grep` で拾えない検査（`studio` を import せずに `python -m studio.cli` を
     叩く形など）が出たら、選びは語ではなく **import の解析**へ移すこと。
 (3) 旧 `src/` の赤が 2件 から動いたら（増えても減っても）、それは §8 の前提が動いた刻
     ＝ `OLD_RED` を直す前に JOURNAL に書くこと。
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"

#: `studio/` を読む検査を拾う語（02:5x の `grep -rln` と同じ 2つ）
STUDIO_PAT = re.compile(r"from studio import|studio\.")

#: 親の手続きの検査（06:3x の選び。`studio` の側は 1件も読まない）
PARENT_GLOBS = (
    "test_quota*.py",
    "test_next_round*.py",
    "test_parent*.py",
    "test_spawn*.py",
    "test_fable*.py",
    "test_model_by_role.py",
    "test_role_model.py",
    "test_pace*.py",
)

#: 旧 `src/` の赤（§8・2026-09-09 08:5x から前のまま）。**どちらの束にも入れないこと**
OLD_RED = ("test_ceiling_drift.py", "test_form_record.py")

BUNDLES = ("studio", "parent")


def _rel(p: Path) -> str:
    """ROOT の下なら相対・外（検査の tmp など）なら そのまま（黙って落とさない）。"""
    try:
        return str(p.relative_to(ROOT))
    except ValueError:
        return str(p)


def studio_files(tests_dir: Path | None = None) -> list[str]:
    """`studio/` を読む検査の file（並びは名前順・ROOT からの相対）。"""
    d = tests_dir or TESTS
    out = []
    for p in sorted(d.glob("test_*.py")):
        if p.name in OLD_RED:
            continue
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if STUDIO_PAT.search(text):
            out.append(_rel(p))
    return out


def parent_files(tests_dir: Path | None = None) -> list[str]:
    """親の手続きの検査の file（重複は畳む・並びは名前順）。"""
    d = tests_dir or TESTS
    seen: dict[str, None] = {}
    for g in PARENT_GLOBS:
        for p in sorted(d.glob(g)):
            if p.name in OLD_RED:
                continue
            seen[_rel(p)] = None
    return sorted(seen)


def files_for(bundle: str, tests_dir: Path | None = None) -> list[str]:
    if bundle == "studio":
        return studio_files(tests_dir)
    if bundle == "parent":
        return parent_files(tests_dir)
    raise KeyError(f"束は {BUNDLES} のどれか: {bundle!r}")


def build_cmd(files: list[str], extra: list[str] | None = None) -> list[str]:
    """pytest の argv。**`-x` は組み立てず、渡されても落とします**（決め (1)）。"""
    safe = [a for a in (extra or []) if a not in ("-x", "--exitfirst")]
    return [sys.executable, "-m", "pytest", "-q", *safe, *files]


def _tail_counts(out: str) -> str:
    """pytest の最後の要約の行（`906 passed in 80.73s` など）。無ければ末尾の非空行。"""
    for line in reversed(out.strip().splitlines()):
        if re.search(r"\d+ (passed|failed|error)", line):
            return line.strip()
    return out.strip().splitlines()[-1].strip() if out.strip() else ""


def run_bundle(bundle: str, extra: list[str] | None = None) -> dict:
    files = files_for(bundle)
    cmd = build_cmd(files, extra)
    t0 = time.time()
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "bundle": bundle,
        "files": len(files),
        "sec": round(time.time() - t0, 1),
        "rc": r.returncode,
        "line": _tail_counts(r.stdout + r.stderr),
        "out": r.stdout + r.stderr,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("bundle", nargs="?", choices=[*BUNDLES, "all"], default="all")
    ap.add_argument("--list", action="store_true", help="撃たずに、束ごとの件数と file を並べる")
    ap.add_argument("pytest_args", nargs="*", help="pytest へそのまま渡す（`-x` は落とします）")
    a = ap.parse_args(argv)

    names = list(BUNDLES) if a.bundle == "all" else [a.bundle]

    if a.list:
        for b in names:
            fs = files_for(b)
            print(f"{b}: {len(fs)} file")
            for f in fs:
                print(f"    {f}")
        print(f"旧 src の赤 2件 は どちらの束にも入れていません（§8・決め (3)）: {', '.join(OLD_RED)}")
        return 0

    rc = 0
    rows = []
    for b in names:
        res = run_bundle(b, a.pytest_args)
        print(res["out"].rstrip())
        rows.append(res)
        rc = rc or res["rc"]

    print()
    for res in rows:
        mark = "緑" if res["rc"] == 0 else "**赤**"
        print(f"{res['bundle']}: {res['line']}（file {res['files']}・{res['sec']}秒）＝ {mark}")
    print("**秒は書き置かないこと**（機械の混み具合で 2倍 以上 振れます・この道具の註）。"
          "**`-x` は付けません**（赤 1件 で止まると残りが見えない）。"
          "**旧 `src/` の赤 2件 は追わないこと**（§8）。")
    return rc


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
