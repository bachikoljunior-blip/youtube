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
import json
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


#: 走った印の帳面。**この回がいつ始まったか**がここにしかありません。
RUNS = ROOT / "data" / "runs.jsonl"


def round_start() -> str:
    """**この回が始まった時刻**（`data/runs.jsonl` の `kind="start"`）。無ければ空。

    ## なぜ `origin` では足りないのか（2026-08-29 に実測で踏んだ）

    `DEFAULT_BASE` は幹（`origin/claude/...`）です。ところが**サブに渡される本文は
    「節目ごとに commit して push すること。最後にまとめないこと」を要求します**
    （`docs/spawn_prompt.md`。親のコンテナが畳まれるとサブも道連れになるため、
    押さなければその回の成果はどこにも残りません）。

    **この2つは正面から食い違います** —— 押した瞬間に、その変更は幹に入ります。
    だから `git diff origin/<幹>` は**指示どおりに働いた回ほど空になります。**

    実測 2026-08-29（4件 ship した回・`scripts/batch_build.py` ほか5ファイルを変更）:

        [fast_tests] この回が触った .py: 0件（無し）
        [fast_tests] -k: arm_speed or drift or eta or levers
        494 passed in 561.55s

    **9分21秒 かけて 494件 緑を出し、その回の変更を1件も見ていません。**
    しかも印字は緑なので、**撃たないより悪い**（撃った気になれる）。
    この道具の docstring が言う「16分 かかるから誰も撃たない、が赤を何日も残した
    原因」の、次の形がこれです。

    **警告の文は出ていました** —— ただし「`--base` が正しいか見ること」で、
    **「指示どおり押した回は必ずこうなる」とは書いていません。**
    読む側は自分の設定を疑い、道具の作りのほうは疑いません。

    ## だから、幹ではなく**この回の始まり**に錨を打ちます

    `scripts/run_marker.py --write` が周の頭で
    `{"at": ..., "session": "...#agent-<札>", "kind": "start"}` を積んでいます。
    **押しても動かない錨は、いまここにしかありません。**

    **覆る条件**: 印を打たない回（親・オーナーとの会話）では空が返り、
    そのときは今までどおり幹との diff だけになります。**それで正しい** ——
    印が無い回は「周ではない」と決めてあります（`run_marker.worktree_tag()`）。
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from run_marker import worktree_tag                    # noqa: PLC0415
        tag = worktree_tag()
    except Exception:                                          # noqa: BLE001
        tag = ""
    if not tag or not RUNS.exists():
        return ""
    at = ""
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if row.get("kind") == "start" and tag in str(row.get("session", "")):
            at = str(row.get("at") or "")
    return at


def own_commits(limit: int = 200) -> list[str]:
    """**この作業コピーが自分で積んだ commit** を、新しい順に返す（他の回のぶんは入らない）。

    ## なぜ要るか（2026-08-29 に実測で踏んだ。`round_start()` の穴の、次の形）

    `round_start()` は `data/runs.jsonl` の **`kind="start"`** に錨を打ちます。
    ところがその行を書くのは `run_marker.py --write` **だけ**で、
    **最適化の回に渡される本文は `--write` を1文字も言いません**
    （`docs/spawn_prompt.md` が名指しするのは `--ship` のほう）。

    実測 2026-08-29（`scripts/batch_build.py` と `tests/test_batch_slots.py` を
    変更し、4回 押した回）:

        worktree_tag()                  'agent-a40e6e0659b3605fc'   ← 出ている
        runs.jsonl の start 行           67件（**うち この札は 0件**）
        → round_start()                 ''  ← 錨が打てない
        → git diff origin/<幹>           押した後なので **空**
        → keywords()                    **[]**（`-k` は CORE だけ）

    **つまり `round_start()` の直した穴が、`--write` を撃たない役では開いたままです。**
    印字は緑で出るので、docstring の言う「**撃たないより悪い**」がそのまま起きます。

    ## 何に錨を打つか —— **押しても動かないのは reflog のほう**

    `git reflog show HEAD` は、**この作業コピーが行った操作だけ**を持っています。
    そこから `commit:` の行を拾えば、**きょうだいから merge で入ってきたぶんは
    1件も混ざりません**（実測: 幹との diff は 30ファイル 超、こちらは 2ファイル ちょうど）。
    押しても消えません（push は reflog を書き換えないため）。

    **覆る条件**: `git reflog` の無い置き方（浅いクローン・reflog を切った設定）では
    空が返り、そのときは今までどおり `base` との diff だけになります。**それで正しい**
    —— この関数は**足すだけ**で、選択を狭めることは一度もありません。
    """
    out: list[str] = []
    for line in _run(["git", "reflog", "show", "HEAD"]).splitlines():
        # `<sha> HEAD@{N}: commit: …` / `commit (amend): …` / `commit (initial): …`
        parts = line.split(": ", 2)
        if len(parts) < 2:
            continue
        what = parts[1].strip()
        if what == "commit" or what.startswith("commit ("):
            sha = line.split()[0].strip()
            if sha and sha not in out:
                out.append(sha)
        if len(out) >= limit:
            break
    return out


def changed_files(base: str) -> list[str]:
    """**この回が触ったファイル。** 積んだぶんも、まだ積んでいないぶんも。"""
    out: set[str] = set()
    since = round_start()
    sources = [["git", "diff", "--name-only", base, "--"],
               ["git", "diff", "--name-only", "--"],
               ["git", "diff", "--name-only", "--cached", "--"]]
    if since:
        # **押したぶんは幹との diff から消えます**（`round_start()` の docstring）。
        # この回の頭から後の commit を、名前だけ拾い直します。
        sources.append(["git", "log", f"--since={since}", "--name-only",
                        "--pretty=format:", "HEAD"])
    # **錨が打てない回でも、自分の commit は分かります**（`own_commits()`）。
    # `--write` を撃たない役（最適化の回）は `round_start()` が空を返すので、
    # ここが無いと**押した瞬間に「触った .py 0件」**になります。
    mine = own_commits()
    if mine:
        sources.append(["git", "show", "--name-only", "--pretty=format:", *mine])
    for args in (*sources,
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
              " 芯だけを撃ちます ——"
              " **この回の変更は1件も見ていません。緑が出ても、それは緑ではありません。**")
        if not round_start():
            print("[fast_tests] 走った印がありません（`python scripts/run_marker.py"
                  " --write` を周の頭で撃つこと）。**印が無いと、押したぶんが"
                  f"幹（`{args.base}`）に入った時点で見えなくなります** ——"
                  " 手順は「節目ごとに push」を要求するので、"
                  "**指示どおり働いた回ほどここが 0件 になります**"
                  "（`round_start()` の docstring に実測）。")
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
