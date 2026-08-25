"""**この回が触った所だけを検査する。**（API 0単位）

## なぜ要るか（2026-08-26・最適化の回）

前の回の申し送りはこうでした:

> **全体の `pytest` は16〜18分 かかるので、どの回も撃っていません**
> （この回の日誌にも「全体の pytest はこの回も通していません」と3回 書かれています）。
> **16分の検査は、実質 走っていない検査です。** 赤が何日も残るのはその帰結で、
> **次に何かを壊したとき、赤が1件 増えても誰も気づきません。**
>
> **次に来た者への申し送り**: **`-k` の抜き撃ちを既定にすること。**

**申し送りでは直りません。** 同じ日誌が3回そう書いています ——
「申し送りに書き置くと腐る —— 3回それで外しています」。だから**手順にします。**

しかも、あの申し送りは `-k` の中身を**文字列で書き置いて**いました:

    -k "judgeable or live_slots or motion or batch or drift or dead_arm or
        supply or queue_lag or ab_ or levers or eta"

**これは次の回には合いません。** 次の回が触るのは別のファイルだからです。
**書き置いた瞬間に古くなる** —— この repo が何度も踏んでいる形です。

## だから、選び方を**その回の diff から**出します

`git diff` が名指ししたファイルの basename を、そのまま `-k` の語にします。
`src/day_cap.py` を触ったら `day_cap`、`scripts/drift.py` を触ったら `drift`。
**触っていないものは走りません。走らせるべきでもありません** ——
16分 かかるから誰も撃たない、というのが元の欠陥なので。

## **これは全体の検査の代わりではありません**

抜き撃ちが緑でも、**触った所から離れた壊れ方は見えません。**
だから最後に必ず「**この選択が見ていないもの**」を印字します。
`--all` で全体を撃てますが、**16分 かかることを承知で撃つこと。**

    python scripts/fast_tests.py            # この回の diff から選ぶ
    python scripts/fast_tests.py --base X   # 比べる相手を変える
    python scripts/fast_tests.py --all      # 全体（16分）
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

#: **どの回でも撃つ芯。** 目標の判断に直で効く道具（到達予測・腕・合否の数え方）で、
#: ここが赤いと**その回の判断そのものが狂います**。触っていなくても撃つこと。
CORE = ("eta", "levers", "arm_speed", "drift")

#: 比べる相手の既定。**幹の名前をここに書き写しています** —— 変わったら直すこと
#: （`--base` で上書きできます）。
DEFAULT_BASE = "origin/claude/youtube-auto-post-revenue-ggedij"


def _run(args: list[str]) -> str:
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True,
                              text=True, timeout=60).stdout
    except Exception:                                          # noqa: BLE001
        return ""


def changed_files(base: str) -> list[str]:
    """**この回が触ったファイル。** 積んだぶんも、まだ積んでいないぶんも。"""
    out: set[str] = set()
    for args in (["git", "diff", "--name-only", base, "--"],
                 ["git", "diff", "--name-only", "--"],
                 ["git", "diff", "--name-only", "--cached", "--"],
                 # **まだ git に入っていない新しいファイルも触った所です。**
                 #     `git diff` はこれを1件も出しません —— **新しく足した
                 #     `src/*.py` と、その検査が丸ごと落ちます**（この道具自身が
                 #     最初にそれを踏みました: 自分を書いた回に「触った .py 0件」）。
                 ["git", "ls-files", "--others", "--exclude-standard"]):
        for line in _run(args).splitlines():
            if line.strip():
                out.add(line.strip())
    return sorted(out)


def keywords(files: list[str]) -> list[str]:
    """触ったファイルから `-k` の語を作る。**書き置きではなく、その場の diff から。**"""
    words: set[str] = set()
    for f in files:
        p = Path(f)
        if p.suffix != ".py":
            continue
        stem = p.stem
        if stem.startswith("test_"):
            stem = stem[len("test_"):]
        if stem in ("__init__", "conftest"):
            continue
        words.add(stem)
    return sorted(words)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default=DEFAULT_BASE,
                    help="比べる相手（既定: 幹）")
    ap.add_argument("--all", action="store_true",
                    help="全体を撃つ（**16分 かかります**）")
    ap.add_argument("--list", action="store_true",
                    help="選ぶだけで撃たない")
    args = ap.parse_args(argv)

    if args.all:
        print("[fast_tests] **全体を撃ちます（16分）。**")
        return subprocess.call([sys.executable, "-m", "pytest", "-q"], cwd=ROOT)

    files = changed_files(args.base)
    words = keywords(files)
    picked = sorted(set(words) | set(CORE))

    print(f"[fast_tests] この回が触った .py: {len(words)}件"
          + (f" —— {'／'.join(words)}" if words else "（無し）"))
    print(f"[fast_tests] 芯（毎回撃つ）: {'／'.join(CORE)}")
    print(f"[fast_tests] -k: {' or '.join(picked)}")
    if not words:
        print("[fast_tests] **触ったファイルが1つも見つかりません。**"
              f" `--base {args.base}` が正しいか見ること —— "
              "見つからないときは芯だけを撃ちます（**この回の変更は見ていません**）")
    if args.list:
        return 0

    code = subprocess.call(
        [sys.executable, "-m", "pytest", "-q", "-k", " or ".join(picked)], cwd=ROOT)

    print()
    print("[fast_tests] **これは全体の検査ではありません。**"
          " 触った所から離れた壊れ方は、この選択では見えません。")
    print("[fast_tests] 全体は `python scripts/fast_tests.py --all`（16分）。"
          "**押す前に1度は撃つこと** —— "
          "16分 かかるから誰も撃たない、が赤を何日も残した原因です。")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
