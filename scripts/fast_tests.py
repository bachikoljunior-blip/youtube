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
#
# ## 台帳の門を足した理由（2026-09-01・最適化の回。**赤が押される所まで通った**）
#
# 下の `keywords()` は `.py` 以外を1件も `-k` に入れません。ところが
# **`premise` の回が触るのは `config/hypotheses.yaml` ただ1つ**です ——
# 実測（`scripts/retro.py`・直近8回）: **premise 3件（37%）**。
# つまり **ship の 37% は、その変更を見ている検査が1つも選ばれないまま押されます。**
# 画面には「この回が触った .py: N件」としか出ないので、
# **触った `.yaml` が無防備だったことは、撃った側にも見えませんでした。**
#
# 実際に通りました —— 2026-09-01 に立った前提が `CHECKABLE`／`UNCHECKABLE` の
# どちらにも入らないまま押され、`tests/test_hypothesis_deadline_reachable.py` が
# 赤のまま枝に載りました（見つけたのは、その 40分 後に全件を撃った回）。
#
# **道を名指しして選ぶ道は採りませんでした** —— `config/hypotheses.yaml` を
# 名指ししている `tests/test_*.py` は **71件** あり、その中には
# 絵を焼く重い検査（`test_contact_sheet_padding` など）が入っていて**遅い**。
# 台帳を**ついでに読んでいるだけ**の検査まで拾ってしまいます。
#
# **代わりに、台帳の「形」を見ている検査を芯に入れます。** 実測 2026-09-01 ——
# **同じ1件の前提が、3つの門を同時に赤くしていました**（どれも別の欠け方）:
#
#     tests/test_hypothesis_deadline_reachable  CHECKABLE/UNCHECKABLE のどちらにも無い
#     tests/test_settle                          settle_days: 2（実測は 4日）
#     tests/test_watches                         数の門を書いたのに watch: が無い
#
# **1つ塞いでも、残り2つで赤いままです。** だから語を1つに絞れません:
#
#     語を 6つ（…dead_arm まで）        281件・**22.8秒** → 3つのうち **1つ**しか捕まえない
#     ＋ settle / watches               338件・**66.1秒** → **2つ**
#     ＋ judgeable                      355件・**71.8秒** → **3つとも**  ← これを採った
#     道で選ぶ（`config/hypotheses.yaml` を名指しする 71件）
#                                       704件・**219.2秒** ＝ **3.1倍 遅くて、同じ3件**
#     全件（`--all`）                 2,346件・**386.6秒**
#
# **`judgeable` は +5.7秒 で1件 増やします。** 入れない理由がありません。
#
# **上の秒数は「足したぶんだけ」を単独で撃った数です。芯 全体ではありません。**
# 同じ回に `scripts/fast_tests.py` をそのまま撃つと、元の芯
# （`eta`／`levers`／`arm_speed`／`drift`）と触ったファイルのぶんも乗るので:
#
#     足す前  612件・**207.5秒**
#     足した後 957件・**271.6秒**   ＝ **+64.1秒**（上の 71.8秒 と同じ桁）
#
# **選ぶときに見るのは「足したぶん」、押すときに待つのは「全体」です。**
# 混ぜて読むと、割るかどうかの判断を間違えます。
#
# **覆る条件**: 芯**全体**が重くなって（目安 **5分**）誰も撃たなくなったら、そこで割ること
# —— **16分 かかるから誰も撃たない、が赤を何日も残した原因**です
# （下の `--all` の註と同じ理由）。**そのつど撃って測ること。上の数を写さないこと。**
CORE = ("eta", "levers", "arm_speed", "drift",
        # --- 台帳（`config/hypotheses.yaml`）の形を見ている門（上の註） ---
        "hypothes", "premise", "unreachable", "house_rule",
        "dead_ledger", "dead_arm", "settle", "watches", "judgeable")

#: 比べる相手の既定。**幹の名前をここに書き写しています** —— 変わったら直すこと
#: （`--base` で上書きできます）。
DEFAULT_BASE = "origin/claude/youtube-auto-post-revenue-ggedij"


def _pytest(extra: list[str]) -> tuple[int, list[str]]:
    """`pytest` を流しながら、落ちた名前だけ拾って返す。（2026-08-30 に足した）

    ## なぜ要るか（**この道具の判定が、読まれる所に無かった**）

    実測 2026-08-30 06:1x —— この道具が出した最後の12行:

        ...............F........................................................ [ 55%]
        ........................................................................ [ 69%]
        ...................................................
        [fast_tests] **これは全体の検査ではありません。** …
        [fast_tests] 全体は `python scripts/fast_tests.py --all`（16分）。…

    **`F` が1つ出ているのに、名前がどこにもありません。**
    `pytest -q` は落ちた名前を進捗の**後ろ**に出しますが、この道具は
    そのあとに自分の2行を足すので、**端末で `| tail -N` すると
    名前だけが押し出されます**（この repo の走らせ方は必ず尾を読みます）。
    結果、**赤い走りと緑の走りが、いちばん下だけ見ると同じ顔**になります。

    この道具の docstring は自分でこう言っています ——
    「**16分の検査は、実質 走っていない検査です**」。
    **判定が尾に無い検査も、実質 走っていない検査**です。同じ形の1段 上です。

    実測: この `F` の名前を突き止めるのに、**別の走りを7本**（約35分）使いました。

    ## 何をするか

    `-rf` を付けて `FAILED` / `ERROR` の行を拾い、**いちばん下**で言い直します。
    流しながら出すので、進捗はこれまでどおり見えます。

    **覆る条件**: `pytest` の短い要約の書式（`FAILED tests/x.py::y`）が変わったら
    ここは何も拾えません。そのときは `code != 0` の側だけが残ります
    （**それでも「赤」とは言えます**。名前が出ないだけ）。
    検査 `tests/test_fast_tests_verdict.py`。
    """
    proc = subprocess.Popen([sys.executable, "-m", "pytest", *extra],
                            cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, bufsize=1)
    failed: list[str] = []
    assert proc.stdout is not None
    for line in proc.stdout:
        sys.stdout.write(line)
        sys.stdout.flush()
        if line.startswith(("FAILED ", "ERROR ")):
            failed.append(line.rstrip())
    return proc.wait(), failed


def _verdict(code: int, failed: list[str]) -> None:
    """**いちばん下に、この道具の言葉で判定を置く。**（`_pytest` の docstring に理由）"""
    if code == 0:
        print("[fast_tests] **緑**（この `-k` の範囲で）。")
        return
    print(f"[fast_tests] **赤 {len(failed)}件**（pytest exit={code}）"
          if failed else
          f"[fast_tests] **赤**（pytest exit={code}・名前が拾えませんでした）")
    for line in failed:
        print(f"    {line}")
    print("[fast_tests] **緑にしてから押すこと。**"
          " 直せないなら、**何が赤いかを `docs/JOURNAL.md` に名前で書くこと** ——"
          "名前の無い赤は、次に来た側から見て「無い」のと同じです。")


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
        code, failed = _pytest(["-q", "-rf"])
        _verdict(code, failed)
        return code

    files = changed_files(args.base)
    words = keywords(files)
    picked = sorted(set(words) | set(CORE))

    print(f"[fast_tests] この回が触った .py: {len(words)}件"
          + (f" —— {'／'.join(words)}" if words else "（無し）"))
    # **落としたものを黙って落とさないこと**（2026-09-01・最適化の回）。
    #     `keywords()` は `.py` 以外を1件も `-k` に入れません。**それ自体は
    #     変えていません**（道で選ぶと重い検査まで来る。`CORE` の註）が、
    #     **落としたことが画面に出ないのが欠陥でした** —— `premise` の回は
    #     `config/hypotheses.yaml` しか触らないので、毎回「触った .py: 0件」に
    #     見え、**何が無防備なのかを撃った側が言えませんでした。**
    other = [f for f in files if not f.endswith(".py")]
    if other:
        print(f"[fast_tests] この回が触った .py 以外: {len(other)}件"
              f" —— {'／'.join(other)}")
        print("[fast_tests]   **これらは `-k` に入りません**（ファイル名から"
              "検査の名前は出ないため）。`config/hypotheses.yaml` の形だけは"
              "**芯**が見ています（`CORE` の註）。**それ以外の `.yaml` /"
              " `.jsonl` を触った回は、`--all` を撃つこと。**")
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

    code, failed = _pytest(["-q", "-rf", "-k", " or ".join(picked)])

    print()
    print("[fast_tests] **これは全体の検査ではありません。**"
          " 触った所から離れた壊れ方は、この選択では見えません。")
    print("[fast_tests] 全体は `python scripts/fast_tests.py --all`（16分）。"
          "**押す前に1度は撃つこと** —— "
          "16分 かかるから誰も撃たない、が赤を何日も残した原因です。")
    _verdict(code, failed)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
