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


JA = re.compile(r"[ぁ-んァ-ヴ一-龥]")


def lang_of(text) -> str:
    """`takeaway` の言語（`"ja"` / `"en"`）。**仮名か漢字が 1字でも在れば `ja`**。

    **なぜ この雑な述語でよいか**（2026-09-11 23:4x・optimizer・Opus が台帳 79件 で数えた）:
    冷読の返しは「日本語の1文」か「英語の1文」かのどちらかで、**混ざった行は 1件も在りません**
    （英語の 6件 は 1字も仮名漢字を含まず、日本語の 73件 は必ず含む）。
    ＝ 実物の形を列挙してから置いた門です（§5 の教訓 4つ目）。

    **覆る条件**: (1) 日本語の中に英語の語だけが混ざる行（「iDeCo は…」の類）を
    `en` と読んだ回が出たら、ここは**割合**（仮名漢字の字数 ÷ 全体）へ移すこと。
    (2) `takeaway` は日本語なのに `unclear` に英語が混ざる行が出たら、
    見る先を `takeaway` から `takeaway + unclear` へ広げること —— いまは広げていません。
    **`takeaway` が日本語だった 73行 は、`unclear` も 1つ残らず日本語**（73/73）で、
    英語が混ざるのは **`takeaway` が英語だった 6行 のうち 5行 だけ**
    ＝ **takeaway 1つ を見れば、その行ぜんぶの言語が決まります**（引き直しは 1 draw ぶんの値段）。
    """
    return "ja" if JA.search(str(text or "")) else "en"


def cold_read(s: Script, tries: int = 2) -> dict:
    """**返しが英語で来たら、1回だけ引き直す**（2026-09-11 23:4x・optimizer・Opus。§15 の申し送り）。

    **なぜ**: 冷読は `unclear` の**件数**を周をまたいで比べる口（§4 (1)）ですが、
    **英語の draw は件数が別物になります**（実測 09/11 23:1x・hourly: 英語 0件 と 3件 対 日本語 5件）。
    台帳 79件 のうち **6件（7.6%）が英語**で、**その 6件 は全部 `takeaway` が丸ごと英語**でした。

    **手は 2つ**（どちらも `ask` の側は触らない ＝ 他の口に影響しない）:
      (1) 促しに「**日本語で**」を 1行 足す（値段 0）
      (2) それでも英語なら **1回だけ引き直す**（値段は 7.6% の回にだけ 1 draw）

    **捨てた draw は消さずに返します**（`dropped`）—— `cli read` が台帳へ書くので、
    次の回は「(1) が効いたか」を **引き直しの回数**で数えられます（印字も `cli read` が出す）。

    **覆る条件**:
      (1) `dropped` が **10回** たまっても 1回目の英語率が 7.6% から下がらなければ、
          (1) の促しは効いていない ＝ 促しを戻して (2) だけ残すこと（値段が同じで、字が減る）。
      (2) 引き直した 2回目まで英語だった回が **2回** 出たら、`tries` を上げるのではなく
          **模型の側**を見ること（haiku → sonnet は 1 draw の値段が変わる ＝ §5 の模型の割り当て）。
      (3) `unclear` だけが英語で返る行が 2件 目に出たら、`lang_of` の覆る条件 (2) の側へ。

    **(3) `assumed`（分かったが、本文は説明していない）を 2026-09-13 14:2x に足した**（hourly・Opus）。
    **なぜ**: `unclear` は「**分からなかった**」なので、**模型が元から知っている語の欠落は、原理的に落ちません**
    （知っているので分かってしまう）。実物: 09/14 の本は **免除 と 未納 の差**だけを 12コマ 使って計算しながら、
    その 2つ の違い（**申請したかどうか**）を コマ9 の落ちまで 1度も言わず、
    **輪 5周・冷読 5回・critique 5回 が 1度も名指ししていません**。
    オーナーは翌日それを「**説明不足があると思うな。話がつかめない**」と言っています（`2e87f87e`）。
    **同じ族の言葉は 09/10 から 4日 続いており**（`python scripts/owner_words.py`・門 3日 ＝ **引かれた**）、
    **その 3回 の当て先は 3回 とも `docs/METHOD.md` §3 の規則**でした ＝ **規則を足す手が効いていない側**。
    ＝ この回の当て先は規則ではなく**物差しの目**にしました: **判定（分かるか）ではなく列挙（何を自分で補ったか）**。
    模型は「知らないふり」はできませんが、「**自分の知識で補った所を並べる**」ことはできます。

    **覆る条件**（数えるのは `hourly`・§5）:
      (a) `assumed` が **3本** 続けて 0件 なら、この問いは何も足していない ＝ 外すこと（値段は 0 だが字は増える）。
      (b) `assumed` が挙げた所を直した本 **3本** で、オーナーの「分かりにくい」の連
          （`scripts/owner_words.py`）が **1度も切れなかった**ら、当て先はここでもない
          ＝ そのときに疑うのは**尺と結論の数**（1本に載せている事実の数）で、問いの側ではありません。
      (c) `assumed` が毎回 10件 以上 返るなら、60〜90秒 の本では原理的に全部は説明できない
          ＝ **件数ではなく「結論に至る道の上に在るか」で絞ること**（道の外は説明欄）。
    """
    p = ("次は、60秒のショート動画のナレーション全文です。あなたは、この話題を知らない一般の視聴者です。\n"
         "一度だけ聞いた前提で、(1) この動画が言いたいことを1文で、(2) 分からなかった言葉や文を箇条書きで、\n"
         "(3) **あなたには意味が取れたけれど、この動画が一度も説明していない語・前提**を箇条書きで。\n"
         "(3) は「分からなかった」ではありません —— **あなたが元から知っていたから分かった**もの、"
         "つまり この話題を本当に知らない人なら つまずく所です。知っている自分を差し引いて、"
         "**動画の中の言葉だけ**で追えるかを見てください。\n"
         "JSON {\"takeaway\": \"...\", \"unclear\": [\"...\"], \"assumed\": [\"...\"]} だけを返してください。\n"
         "**takeaway も unclear も assumed も、かならず日本語で書いてください**（英語では返さない）。\n\n---\n" + narration(s))
    draws = []
    for _ in range(max(1, tries)):
        draws.append(_json(ask(p, "haiku", 120)))
        if lang_of(draws[-1].get("takeaway")) == "ja":
            break
    r = draws[-1]
    r["lang"] = lang_of(r.get("takeaway"))
    r["dropped"] = [d.get("takeaway") for d in draws[:-1]]
    return r


def critique(s: Script) -> dict:
    p = ("次は、60秒のショート動画のナレーション全文と、画面に出る字です。あなたは、この話題を初めて聞く、"
         "40〜60代の一般の視聴者です。専門用語も前提知識もありません。\n"
         "分かりにくい所・引っかかる所・話の飛び・数字の出どころが分からない所を、批判的に全部挙げてください。\n"
         "挙げた項目は、可能性が高い順に並べ、各項目に severity を付けてください: "
         "\"real\" ＝ そこで初めて聞く人が話を見失う（何の話か・何を足すのか・結論が何かが分からなくなる）。"
         "\"nitpick\" ＝ 補足があれば親切だが、無くても話は通る（背景の制度説明・計算の途中式・用語の由来など）。\n"
         "これは 60〜90秒 のショートです。全部を説明しないこと自体は欠陥ではありません。"
         "1本で1つの結論が伝わるかで判定してください。\n"
         "**この本が 2つ を比べているなら**（結論が「A と B の差」の形）、"
         "その 2つ の**違いそのもの**が、比べ始めるより前に 1文で言われているかを必ず見てください。"
         "言われていなければ **real** です —— 聞く人は、何と何を比べているかを持たないまま計算を聞くことになります。\n"
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
