"""分かりやすさの外部評価。台本を書いた本人（Fable）は自分の文が分かりにくいと気づけないので、
文脈を持たない別の模型に「初めて聞く視聴者」として読ませる。

  cold_read  Haiku   … 1文で言い返させる。takeaway と食い違えば、伝わっていない（安い。毎回）
  critique   Sonnet  … 分かりにくい所を全部、厳しく挙げさせ、各項目に「本当か／言いがかりか」を付けさせる。
                       1番目が「言いがかり」になったら輪を閉じる（オーナー 09/03 の終了条件）

`claude -p` はサブスクの OAuth で動く（API 鍵は使わない）。cwd は repo の外（CLAUDE.md を混ぜない）。
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile

from .script import Script

MODELS = {"haiku": "claude-haiku-4-5", "sonnet": "claude-sonnet-4-5", "opus": "claude-opus-4-5"}


def ask(prompt: str, model: str = "sonnet", timeout: int = 300) -> str:
    cwd = tempfile.mkdtemp(prefix="studio-critic-")
    r = subprocess.run(["claude", "-p", prompt, "--model", MODELS.get(model, model), "--output-format", "json"],
                       cwd=cwd, capture_output=True, text=True, timeout=timeout,
                       env={**__import__("os").environ, "YOUTUBE_PIPELINE_CHILD": "1"})
    if r.returncode != 0:
        raise RuntimeError(f"claude -p rc={r.returncode}: {r.stderr[-400:]}")
    return json.loads(r.stdout)["result"]


def _json(text: str):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group()) if m else {"raw": text}


def narration(s: Script) -> str:
    return "\n".join(seg.say for seg in s.segments)


def cold_read(s: Script) -> dict:
    p = ("次は、60秒のショート動画のナレーション全文です。あなたは、この話題を知らない一般の視聴者です。\n"
         "一度だけ聞いた前提で、(1) この動画が言いたいことを1文で、(2) 分からなかった言葉や文を箇条書きで、\n"
         "JSON {\"takeaway\": \"...\", \"unclear\": [\"...\"]} だけを返してください。\n\n---\n" + narration(s))
    return _json(ask(p, "haiku", 120))


def critique(s: Script) -> dict:
    p = ("次は、60秒のショート動画のナレーション全文と、画面に出る字です。あなたは、この話題を初めて聞く、"
         "40〜60代の一般の視聴者です。専門用語も前提知識もありません。\n"
         "分かりにくい所・引っかかる所・話の飛び・数字の出どころが分からない所を、批判的に全部挙げてください。\n"
         "挙げた項目は、可能性が高い順に並べ、各項目に severity を付けてください: "
         "\"real\" ＝ そこで初めて聞く人が話を見失う（何の話か・何を足すのか・結論が何かが分からなくなる）。"
         "\"nitpick\" ＝ 補足があれば親切だが、無くても話は通る（背景の制度説明・計算の途中式・用語の由来など）。\n"
         "これは 60〜90秒 のショートです。全部を説明しないこと自体は欠陥ではありません。"
         "1本で1つの結論が伝わるかで判定してください。\n"
         "最後に、全体として一度で理解できるかを 1〜5 で。\n"
         "JSON {\"items\": [{\"where\": \"コマ番号か引用\", \"why\": \"...\", \"fix\": \"直し方の案\", \"severity\": \"real|nitpick\"}], "
         "\"understand\": 1〜5, \"takeaway\": \"1文\"} だけを返してください。\n\n---\n")
    for i, seg in enumerate(s.segments, 1):
        p += f"コマ{i} 画面「{seg.show}」{('/' + seg.sub) if seg.sub else ''}\n  声: {seg.say}\n"
    return _json(ask(p, "sonnet", 300))


def loop_done(c: dict) -> bool:
    items = c.get("items") or []
    return (not items) or items[0].get("severity") == "nitpick"
