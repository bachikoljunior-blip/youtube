#!/usr/bin/env bash
# **恒久指示を、判断のたびに文脈へ差し戻す。**（恒久指示 A4）
#
# なぜ要るか。CLAUDE.md はセッション開始時と要約後にしか入らない。長い作業の
# 途中では薄れるし、薄れたことには気づけない。実際、覚えてはいたのに適用せず、
# オーナーに2回指摘されている（docs/JOURNAL.md 2026-08-04）。
#
# **中身は docs/CONSTRAINTS.md から機械的に抜き出す。** 手で写すと必ずずれる
# （実際「週100クレジット」が5ファイルに散った）。あちらを直せばここも直る。
#
# 以前は docs/GOAL.md を丸ごと（209行）注入していたが、**肝心の恒久指示が
# 揃っていなかった。** 目標本文はあっても、リポジトリを伏せる・週300ドル・
# あらゆる手段を実行してよい、などが入っていない。手順や方法論（B）ばかりが
# 毎回入って、守るべきもの（A）が入っていないのは本末転倒だった。
#
# いまは **A だけを入れる。** 手順は docs/GOAL.md、B の一覧は
# docs/CONSTRAINTS.md にあり、必要なときに読めばよい。短いほうが確実に読まれる。
set -uo pipefail

ROOT="$(dirname "$0")/.."
[ -f "$ROOT/docs/CONSTRAINTS.md" ] || exit 0

python3 - "$ROOT/docs/CONSTRAINTS.md" <<'PY' 2>/dev/null || exit 0
import json, re, sys, pathlib

src = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")

# A の表（| A1 | 内容 | 日 | 効いている場所 |）を抜く
rows = re.findall(r"^\| (A\d+) \| (.+?) \| [^|]* \| [^|]* \|$", src, re.M)

# **抜き出しが壊れたら黙るのではなく、大声で言う。**
# 表の書式に依存しているので、列を増減すると 0 件になる。0 件のまま静かに
# 通すと A4（恒久指示を忘れないように設計する）が誰にも気づかれず破れる。
if not rows:
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": (
                "**[!] 恒久指示の抜き出しが壊れています。**\n"
                "`docs/CONSTRAINTS.md` の A の表から1件も取れませんでした。\n"
                "表の書式（`| A番号 | 内容 | 日 | 場所 |`）が変わった可能性が高い。\n"
                "**他の作業より先に `scripts/goal_reminder.sh` の正規表現を直すこと。**\n"
                "直るまで、恒久指示は `docs/CONSTRAINTS.md` を直接読むこと。"
            ),
        },
        "suppressOutput": True,
    }, ensure_ascii=False))
    raise SystemExit(0)

items = "\n".join(
    "- **{}** {}".format(n, re.sub(r"（下に全文。書き換え厳禁）", "", b).strip())
    for n, b in rows
)

# A1 の全文（引用ブロック）を抜く
m = re.search(r"### A1 の全文[^\n]*\n\n((?:> .*\n)+)", src)
goal = m.group(1).strip() if m else ""

context = f"""**恒久指示（これだけは変えられない。{len(rows)}件）**

{items}

**これ以外は全部あなたの考えで変えてよい**（A14）。承認は要りません。
**「昔オーナーがそう言ったから」は理由になりません。** 上に無いなら恒久指示ではない。
**A に無いものを A のように扱うのが、一番よくある壊れ方です。**

**A1 の全文（オーナーの言葉のまま。絶対に書き換えないこと）**

{goal}

**判断の前に確かめること** — いまのやり方が最短だと思っていないか／根拠は数字か推測か／
オーナーの作業に依存していないか／投稿は途切れないか／ポリシーに触れていないか。
**覚えているだけでは足りません。実際に適用したかを確かめてください。**

手順と方法論は `docs/GOAL.md`、変えてよいもの（B）の一覧と根拠は
`docs/CONSTRAINTS.md`。必要なときに読むこと。"""

print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": context,
    },
    "suppressOutput": True,
}, ensure_ascii=False))
PY
