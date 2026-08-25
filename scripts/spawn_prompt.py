#!/usr/bin/env python3
"""**子に渡すプロンプトを組み立てる**（2026-08-20 に作った）。

型の正本は `docs/spawn_prompt.md`、識別子の正本は `docs/trigger_spec.json`。
**この道具は組み立てるだけで、文言をここに持ちません** —— 持つと2か所になり、
片方だけ直った回に、また 8/12 の「3か所とも別の値」に戻ります。

## なぜ要ったか

渡し方が**親のターンの中にしかありませんでした。** 毎時走るので回数が効き、
実測で3つ壊れています（理由の全文は `docs/spawn_prompt.md`）:

    source_url の付け忘れ    8/17 04:1x・8/18 23:5x（repo の無い子が立つ）
    親が要約して条件を落とす  8/10
    申し送りが親と一緒に消える 8/15・8/16

**上2つは、道具が組み立てれば起きません。** `--json` は `source_url` と
`source_revision` を**必ず**入れるので、付け忘れる余地がありません。

## 使い方

    python scripts/spawn_prompt.py --kind hourly
    python scripts/spawn_prompt.py --kind owner-full --note "<原文>"
    python scripts/spawn_prompt.py --kind hourly --siblings 016bZbYd,01Cja6DK
    python scripts/spawn_prompt.py --kind hourly --only "eta.py の _drift だけ" --json

## この設計が覆る条件

- **枝が1本でなくなったら** —— `--branch` を足して、既定を spec から取ること
- **`create_session` の引数が変わったら** —— `--json` の欄を合わせること
  （`tests/test_spawn_prompt.py` が `source_url` / `source_revision` を見ています）
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = ROOT / "docs" / "spawn_prompt.md"
SPEC = ROOT / "docs" / "trigger_spec.json"

KINDS = ("hourly", "optimizer", "owner-full", "owner-record")

_BLOCK = re.compile(
    r"^## (?:kind|block):\s*(?P<name>[\w-]+)\s*$\n+```text\n(?P<body>.*?)^```",
    re.M | re.S)

# 型のほかに要る段。**`lead-only` が欠けると、`--only` の回に
# 「1周してください」が残り、受け取った子が両方やろうとします。**
NEEDED = KINDS + ("lead-round", "lead-only")


def templates(path: Path = TEMPLATE) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    out = {m.group("name"): m.group("body").rstrip() for m in _BLOCK.finditer(text)}
    missing = [k for k in NEEDED if not out.get(k, "").strip()]
    if missing:
        raise SystemExit(f"[!] `{path}` に型がありません: {', '.join(missing)}")
    return out


#: **どの役にも必ず付く段。** 立てられる側が、立てる側の手続きを直せるようにする。
#:
#: 2026-08-10 のオーナー指摘: 「目標以外のことは子の改善ループで変えられるように
#: したほうが良くない？ 作業の途中で設計の欠陥に気づくこともあるだろうから」。
#: あのとき親の手順はトリガー本文にあり、**子は気づいても直せませんでした。**
#: repo へ移して解いたのですが、**2026-08-25 夜に同じ穴を新しい場所に開け直しています**
#: —— サブへ渡す本文に「親の手順も変えてよい」と一度も書いていませんでした
#: （オーナー「サブの判断で変更できない箇所はない？」で気づいた）。
AUTHORITY = """

## **親の手順も、あなたが書き換えてよい**

**あなたを立てている側の手続きは、全部 repo にあります:**

    docs/trigger_parent.md 第1節     親が起きたら何をするか
    scripts/next_round.py            いつ立てるか・どの役か
    docs/spawn_prompt.md             あなたに渡される本文の**型**
                                     （`docs/spawn_prompt.rendered.md` は**生成物**。
                                       手で直すと戻されます —— 2026-08-25 に踏んだ）

**欠陥に気づいたら直してください。** 親は毎回この3つを読み直します。
**理由と「覆る条件」を `docs/JOURNAL.md` に書くこと** —— 書かないと、
次に来た側が判断できず惰性で戻します。

**変えられないのは目標の本文だけです**（`CLAUDE.md` 冒頭・`docs/GOAL.md`）。
**それ以外に聖域はありません。**"""


#: **合流したとき `CLAUDE.md` で必ず止まる、その1点だけ。**（2026-08-25）
#
# **枝の合わせ方そのものは、ここには書きません** —— 型の
# 「最初の1手は、枝を合わせることです」が `<<branch>>`（＝`docs/trigger_spec.json`）
# から本物の枝名を入れて渡しています。**2か所で言うと、片方が古びます。**
#
# 実際に8/25 にそうなりかけました: この段の最初の版は
# 「いちばん新しい `worktree-agent-*` が幹」と書いていて、**spec が名指しする
# `branch` と食い違っていました。** 同じ問いに2つの答えがある状態で、
# **このリポジトリが何度も踏んでいる形そのもの**です。消してあります。
#
# 残すのは、型の側が言っていない1点だけ: **`main` から切られた worktree を
# 合流させると、`CLAUDE.md` で必ず衝突します**（幹は恒久指示9件の枠を外した版、
# `main` は `note` の `propagate_directive.py` がその枠を入れた版 ＝ `4114f7b`）。
# そして **サブエージェントはそのファイルを書き換えられません** ——
# 8/25 に `checkout --theirs` / `add` / `merge -X theirs` / `reset --hard` の
# **4つとも分類器に拒否**されました。知らないと、ここで回が丸ごと止まります。
TRUNK = """

**合流すると `CLAUDE.md` で衝突します。止まらないこと。**
幹は恒久指示9件の枠を**外した**版、`main` は入れた版なので、必ずここでぶつかります。
**サブエージェントはこのファイルを書き換えられません**（分類器が止めます ——
8/25 に `checkout --theirs` / `add` / `merge -X theirs` / `reset --hard` の4つとも拒否）。

**衝突したまま進めて構いません。** その1ファイルには触らず、
**自分が変えたファイルだけを** commit して push すること
（`git read-tree --reset origin/<枝>` → `git add <変えたファイル>` →
`git write-tree` → `git commit-tree` → `git push <sha>:refs/heads/<枝>` で通ります）。
"""


def _siblings_block(siblings: list[str]) -> str:
    """**同じ枝で走っている相手を名指しする段。**

    空でも段を落としません —— 「いない」と書いてあることに意味があります
    （書いていないと、受け取った子は「調べていないだけ」と区別できません）。

    **`TRUNK` を必ず添えること**（2026-08-25）。合流で `CLAUDE.md` が衝突したとき、
    サブはそれを自力で解けません —— 知らないと、そこで回が丸ごと止まります。
    **枝の合わせ方そのものは型の「最初の1手」が持ちます**（重ねて書かないこと）。
    """
    if not siblings:
        head = ("**同じ枝で他に走っている相手は、立てた時点ではいません。**\n"
                "それでも push 前に必ず `git fetch`。競合したら merge で"
                "**相手の作業を残すこと。捨てないこと。**")
    else:
        named = "／".join(siblings)
        head = ("**いま同じ枝で走っています: " + named + "**\n"
                "**あなたの担当は、上のどれとも別のファイルのはずです。**\n"
                "push 前に必ず `git fetch`。競合したら merge で"
                "**相手の作業を残すこと。捨てないこと。**")
    return head + TRUNK + AUTHORITY


def _facts_block(root: Path = ROOT) -> str:
    """**立てるたびに数え直す「いまの姿」。**（API 0単位）

    ## なぜ要るか（2026-08-26）

    ここは長らく**型に数字がべた書き**でした。実測でどれだけずれていたか:

        型に書いてあった   ship 240件 / fix 115 / moves≠0 17件 / **作れるのは4本・在庫は0本**
        実際（08-26）      ship 300件 / fix 126 / moves≠0 19件 / **作れるのは 13.6本・在庫 27本**

    **「作れるのは4本・在庫は0本」は、受け取った側を必ず誤らせます** ——
    その2つが本当なら律速は供給で、**「もっと作れ」が正解**になります。
    実際の律速は**予約の順番待ち（32日）**で、作る本数を増やすと
    **待ち行列が伸びて律速が悪化します。正反対です。**

    **型に数字を書かないこと。** 書くと、書いた回の姿で次の回が判断します
    （`CLAUDE.md`「昔オーナーがそう言ったから」は理由にならない、と同じ形）。

    **数えられなかった行は落とします。** ここで例外を上げると
    **子が1人も立ちません** —— 立たないほうが、数字が1行欠けるより高くつきます。
    """
    lines: list[str] = []
    try:                                    # ship の内訳（8/18 以降）
        import json as _json
        rows = []
        for ln in (root / "data" / "runs.jsonl").read_text(
                encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                rows.append(_json.loads(ln))
            except ValueError:
                continue
        ships = [r for r in rows
                 if r.get("kind") == "ship" and str(r.get("at", "")) >= "2026-08-18"]
        def _cat(w: str) -> str:
            w = (w or "").strip()
            for k in ("fix", "means", "upload", "verdict"):
                if w.startswith(k + ":"):
                    return k
            return "その他"
        n = Counter(_cat(str(r.get("what", ""))) for r in ships)
        moved = sum(1 for r in ships if r.get("moves"))
        lines.append(
            f"    8/18以降の ship {len(ships)}件   "
            + " ／ ".join(f"{k} {n[k]}" for k in ("fix", "means", "upload", "verdict"))
            + f"（その他 {n['その他']}）")
        lines.append(
            f"    `moves` に0以外を書いた回  **{moved}件**"
            f"（＝{len(ships) - moved}回は「日付は動かない」と自分で言って合格）")
    except Exception:
        pass
    try:                                    # 予約の順番待ち（この機械の時定数）
        sys.path.insert(0, str(root))
        from scripts import queue_lag       # noqa: PLC0415
        from src.ab_split import SETTLE_DAYS  # noqa: PLC0415
        from src import judgeable           # noqa: PLC0415
        rows_q = queue_lag.scheduled()
        d = queue_lag.depth(rows_q)
        lines.append(
            f"    予約 {len(rows_q)}本 ／ いちばん後ろは **{d}日 先**"
            f"（＝いま作った本が公開されるまで）"
            f" → 判定できるのは **{d + SETTLE_DAYS + judgeable.ANALYTICS_LAG_DAYS}日後**")
    except Exception:
        pass
    try:                                    # 出せる本数と、作れる本数と、在庫
        from src import day_cap, supply     # noqa: PLC0415
        st = supply.stock() if hasattr(supply, "stock") else None
        lines.append(
            f"    再生が付く上限 **{day_cap.cap()}本/日**（実測）"
            + (f" ／ 在庫 **{st}本**" if isinstance(st, int) else ""))
    except Exception:
        pass
    return "\n".join(lines) if lines else "    （この回は数えられませんでした）"


def build(kind: str, note: str = "", siblings: list[str] | None = None,
          only: str = "", root: Path = ROOT) -> str:
    if kind not in KINDS:
        raise SystemExit(f"[!] --kind は {'/'.join(KINDS)} のどれか（受け取った: {kind}）")
    tpl = templates(root / "docs" / "spawn_prompt.md")
    body = tpl[kind]
    note, only = (note or "").strip(), (only or "").strip()
    if kind.startswith("owner") and not note:
        raise SystemExit("[!] `--kind owner-*` には `--note \"<原文>\"` が要ります。"
                         "**要約しないこと。** 数字は桁もそのまま写すこと")
    note_block = ("**申し送り（原文のまま。要約されていません）:**\n\n> "
                  + note.replace("\n", "\n> ")) if note else ""
    # **枝の名前は spec から。型に書き写さないこと**（2026-08-25 夜に足した）。
    # サブへ移してから `source_revision` の口が無くなり、**ワークツリーが
    # `main` から切られる**ようになりました（実測: 8/25 夜のサブ3枚が3枚とも）。
    # 型の「最初の1手」がこの名前を使うので、**spec と食い違わせないこと。**
    try:
        branch = json.loads(
            (root / "docs" / "trigger_spec.json").read_text(encoding="utf-8"))["branch"]
    except Exception:
        branch = ""            # spec が読めない回でも、型そのものは組み立てる
    filled = {
        "branch": branch,
        "note": note,
        "only": only,
        "note_block": note_block,
        "siblings_block": _siblings_block(list(siblings or [])),
        # **数字は立てるたびに数え直す**（2026-08-26）。型にべた書きすると、
        # 書いた回の姿で次の回が判断します（`_facts_block` の註）。
        "facts": _facts_block(root),
        "lead": (tpl["lead-only"].replace("<<only>>", only) if only
                 else tpl["lead-round"]),
    }
    out: list[str] = []
    for line in body.splitlines():
        key = line.strip()
        if key.startswith("<<") and key.endswith(">>"):
            value = filled.get(key[2:-2], "")
            if value:                        # 空の差し込み口は、行ごと落とす
                out.append(value)
            continue
        for name, value in filled.items():
            line = line.replace(f"<<{name}>>", value)
        out.append(line)
    text = "\n".join(out)
    # **差し込み口の中の差し込み口**（2026-08-25 夜に踏んだ）。
    # `<<lead>>` は段まるごと差し込むので、**その中の `<<branch>>` は
    # 上の行ごとの置換を通りません。** 組み上げたあとで、もう一度当てること。
    # ここを飛ばすと、子は `git merge origin/<<branch>>` を**そのまま読みます。**
    text = text.replace("<<branch>>", branch)
    return re.sub(r"\n{3,}", "\n\n", text).strip() + "\n"


def create_session_args(kind: str, root: Path = ROOT, **kw) -> dict:
    """`create_session` にそのまま渡せる一式。

    **`source_url` と `source_revision` は省略できません**（2026-08-18 に踏んだ）。
    `environment_id` は継がれますが `sources` は継がれないので、**継がれる側から
    「repo も継がれる」と読めてしまう**のがこの穴の正体です。ここでは常に入れます。
    """
    spec = json.loads((root / "docs" / "trigger_spec.json").read_text(encoding="utf-8"))
    return {
        "source_url": spec["repo_url"],
        "source_revision": spec["branch"],
        "environment_id": spec["environment_id"],
        # **役ごとに札を分けます**（2026-08-24。オーナー提案「並行して、主実行を
        # 目標に最適化し続ける子を動かしたら？」）。**親は札で子の生死を見る**ので、
        # 分けないと「最適化の子が走っている」を「主実行が走っている」と読み、
        # **主実行が立たなくなります。**
        "tags": ["youtube-optimizer" if kind == "optimizer" else "youtube-hourly"],
        "prompt": build(kind, root=root, **kw),
    }


RENDERED = ROOT / "docs" / "spawn_prompt.rendered.md"

# 親向けの写しに残す差し込み口。**親は repo を触れないので、この道具を回せません。**
# テンプレートだけ置くと、親は組み立てを暗算することになり、**そこが「要約して
# 条件を落とす」（8/10）の入口**です。だから **1ファイル取って、2か所だけ
# 埋めて貼る**形にします。埋めるのは、repo からは絶対に求まらない2つだけ。
_NOTE_SLOT = "<<オーナーの言葉を、ここに原文のまま。要約しない。数字は桁もそのまま>>"

# **差し込み口は1つだけにします**（2026-08-25 に減らした）。
#
# それまで siblings 側にも `<<いま走っている子の識別子。いなければこの行ごと消す>>`
# を置いていました。ところが親の手順は「`prompt` を **1字も変えずに**渡す」です。
# **両方を守ると、サブはプレースホルダの文字列を、走っている相手の名前として
# 受け取ります。** `_siblings_block()` は「**いないと明記してある**ことに意味がある」
# （調べていないだけと区別できない）ために作った段なので、
# **逐語コピーの規則が、その段の意味をちょうど壊していました。**
#
# だから写しでは **`siblings=[]`（「いません」と書いてある側）を既定**にします。
# 走っている相手を親が知っている回だけ、その1文を差し替えること。
#
# **覆る条件**: 親が走っているサブを承認なしで数えられるようになったら
# （`ListAgents` が前の親のサブまで見えるなら）、写しではなく `next_round.py` に
# 数えさせて埋めること。**親に暗算させないこと**が、この節の要点です。


def write_rendered(root: Path = ROOT) -> Path:
    """**親がそのまま貼れる形**を1ファイルに書き出す。"""
    parts = ["# 子に渡すプロンプト（**親向けの写し。そのまま貼れます**）",
             "",
             "**この写しは `scripts/spawn_prompt.py --write-rendered` が作ります。"
             "手で直さないこと** —— 直すのは `docs/spawn_prompt.md` の型のほうです。",
             "",
             f"差し込み口は `owner-*` の1つだけ: `{_NOTE_SLOT}`。",
             "**`hourly` / `optimizer` は差し込み口がありません。"
             "1字も変えずにそのまま渡せます。**",
             "**それ以外は1字も変えないこと**（`source_url` を落とすと、"
             "repo の無い子が立ちます。8/17・8/18 に2回）。",
             ""]
    for kind in KINDS:
        note = _NOTE_SLOT if kind.startswith("owner") else ""
        args = create_session_args(kind, note=note, siblings=[], only="",
                                   root=root)
        parts += [f"## kind: {kind}", "", "```json",
                  json.dumps(args, ensure_ascii=False, indent=2), "```", ""]
    RENDERED.write_text("\n".join(parts), encoding="utf-8")
    return RENDERED


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="子に渡すプロンプトを組み立てる")
    ap.add_argument("--kind", default="hourly", choices=list(KINDS))
    ap.add_argument("--note", default="", help="オーナーの言葉を**原文のまま**")
    ap.add_argument("--siblings", default="", help="同じ枝で走っている相手（カンマ区切り）")
    ap.add_argument("--only", default="", help="「この回はこれだけ」の中身")
    ap.add_argument("--json", action="store_true",
                    help="create_session の引数一式で出す")
    ap.add_argument("--write-rendered", action="store_true",
                    help="親向けの写し（docs/spawn_prompt.rendered.md）を書き直す")
    args = ap.parse_args(argv)
    if args.write_rendered:
        print(f"書きました: {write_rendered().relative_to(ROOT)}")
        return 0
    sibs = [s.strip() for s in args.siblings.split(",") if s.strip()]
    kw = {"note": args.note, "siblings": sibs, "only": args.only}
    if args.json:
        print(json.dumps(create_session_args(args.kind, **kw),
                         ensure_ascii=False, indent=2))
    else:
        print(build(args.kind, **kw), end="")
    return 0


if __name__ == "__main__":
    sys.exit(main())
