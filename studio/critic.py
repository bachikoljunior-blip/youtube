"""分かりやすさの外部評価。台本を書いた本人（Fable）は自分の文が分かりにくいと気づけないので、
文脈を持たない別の模型に「初めて聞く視聴者」として読ませる。

  cold_read  Haiku   … 1文で言い返させる。takeaway と食い違えば、伝わっていない（安い。毎回）
  crosscheck Sonnet  … 声と 説明欄・notes が食い違っていないか（§4 (0)。critique は say/show/sub しか読まない）
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
    p += critique_screen(s)
    return _json(ask(p, "sonnet", 300))


def critique_screen(s: Script) -> str:
    """critique に渡す画面と声の写し。**札（tag）と まん中の板（board）も渡す**（2026-09-10 13:2x・hourly・Fable）——
    §14 の 10:0x は「声の中だけで閉じている数列」を critique が拾わなかった実測。板に数列が出れば、critic はそれを読める。
    検査 `tests/test_studio_slides_board.py`。"""
    out = ""
    for i, seg in enumerate(s.segments, 1):
        head = f"コマ{i}" + (f" [札: {seg.tag}]" if seg.tag else "")
        out += f"{head} 画面「{seg.show}」{('/' + seg.sub) if seg.sub else ''}\n"
        if seg.board:
            out += "  板（そのコマまでの積み上がり・最後の行がいまのコマ）: " + " ／ ".join(seg.board) + "\n"
        out += f"  声: {seg.say}\n"
    return out


def loop_done(c: dict) -> bool:
    items = c.get("items") or []
    return (not items) or items[0].get("severity") == "nitpick"


def crosscheck(s: Script) -> dict:
    """§4 (0) の機械の側 —— **声と、説明欄・notes が食い違っていないか**だけを見る。

    `critique` は `say`/`show`/`sub` しか読まない（`critique()` を見れば分かる）ので、
    **声が説明欄や notes と正面から反対でも、輪を何周 回しても素通りする。**
    実測で 2回 出ている:
      2026-09-07 05:4x  説明欄の側に実の誤り1つ・言い過ぎ1つ（critique 5周 を抜けた）
      2026-09-08 02:5x  **逆向き** —— 説明欄と notes は正しく、**声が2か所 間違っていた**
                        （加給年金の要件を「いっしょに住んでいたら」＝ 同居 と言った。
                          同じファイルの説明欄は「同居が必須ではなく、別居でも生計が同じなら対象」。
                          もう1つは「配偶者にも20年以上あると はじめから出ません」で、
                          notes の「配偶者が…権利を持つと停止」と食い違い、
                          かつ**その本の例そのもの**を否定していた）

    ここは分かりやすさを見ない・事実を外から調べない。**同じ本の中で言っていることが割れている所**だけを挙げる。
    ＝ 追加の資料が要らないので、模型が確かめられる問いに閉じている（critique と違い、答え合わせの相手が本の中に在る）。
    """
    p = ("次は、1本のショート動画の「声で読む文」と、同じ動画の「説明欄」「制作メモ（notes）」です。\n"
         "あなたの仕事は、**分かりやすさの評価ではありません**。**同じ動画の中で、言っていることが食い違っている所だけ**を"
         "見つけてください。事実を外から調べる必要はありません —— **この3つを突き合わせるだけ**です。\n"
         "見つけるもの:\n"
         "  contradiction … 声が言っていることを、説明欄か notes が**否定している**"
         "（例: 声「いっしょに住んでいたらもらえます」／説明欄「同居は必須ではない」）\n"
         "  sharper       … 声のほうが**言い過ぎ**（条件・断定・範囲が、説明欄や notes より強い）\n"
         "  missing_cond  … 説明欄や notes が要件として書いていることを、声が**落として**いて、"
         "そのせいで声だけを聞いた人が判定を間違える\n"
         "**食い違いが無ければ items を空で返してください。**無理に挙げないこと。\n"
         'JSON {"items": [{"where": "コマ番号", "say": "声の引用", "doc": "説明欄か notes の引用", '
         '"why": "なぜ食い違うか", "kind": "contradiction|sharper|missing_cond"}]} だけを返してください。\n\n---\n')
    p += "【声】\n"
    for i, seg in enumerate(s.segments, 1):
        p += f"コマ{i}: {seg.say}\n"
    p += f"\n【説明欄】\n{s.description}\n\n【制作メモ notes】\n{s.notes}\n"
    return _json(ask(p, "sonnet", 300))
