#!/usr/bin/env bash
# 目標を、判断のたびに文脈へ差し戻す。
#
# なぜ要るか。CLAUDE.md はセッション開始時と要約後にしか入らない。長い作業の
# 途中では薄れるし、薄れたことには気づけない。実際、覚えてはいたのに適用せず、
# オーナーに2回指摘されている（docs/JOURNAL.md 2026-08-04）。
#
# このフックは UserPromptSubmit で毎回発火し、docs/GOAL.md の中身を
# additionalContext としてモデルに戻す。定期実行の撃ち込みもユーザーの発話として
# 届くので、**毎日の実行の冒頭で必ず目標が入る**。
#
# 中身は docs/GOAL.md 側にある。ここは運び役なので、文面を変えたいときは
# GOAL.md を編集すること（このスクリプトも settings.json も触らなくてよい）。
set -uo pipefail

GOAL="$(dirname "$0")/../docs/GOAL.md"
[ -f "$GOAL" ] || exit 0

# JSON に安全に埋めるため、python で文字列化する。jq が無い環境でも動く。
python3 - "$GOAL" <<'PY' 2>/dev/null || exit 0
import json, sys, pathlib
text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8")
print(json.dumps({
    "hookSpecificOutput": {
        "hookEventName": "UserPromptSubmit",
        "additionalContext": (
            "以下はオーナーが定めた目標と、判断のたびに確認すべき項目です。"
            "覚えているだけでなく、実際に適用したかを毎回確かめてください。\n\n" + text
        ),
    },
    "suppressOutput": True,
}, ensure_ascii=False))
PY
