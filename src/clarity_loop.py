"""**説明が分かりやすいかの修正ループ**（2026-09-03）。

## なぜ要るか（オーナー原文・`CLAUDE.md` 冒頭・**一字も変えないこと**）

> **「説明が分かりやすいかの修正ループ回してから、その全文照合修正ループ回すようにして」**
> （09/03 09:5x ＝ 毎本の出口の順: **(1) 分かりやすさの輪 → (2) 完成音声の全文照合の輪**）
>
> **「説明が分かりやすいかの修正ループは評価する時に分かりにくい部分を批判的に全て上げ、
> 1番可能性が高いものがほとんど言いがかりになったらループおわり。」**（09/03 10:0x）
>
> **「修正してからまた初めから評価する」**（09/03 10:0x ＝ 直したら本文全体を白紙から
> 評価し直す。**前の列挙は引き継がない**）

## ここまでに在ったものと、空いていた穴

    verify._check_ear_load          一息で耳が持たされる数の個数（上限5個）  ← 生成の輪に配線ずみ
    script_writer.*_script_problems 生成中の書き直し 3回まで（**機械的な条件だけ**）
    scripts/deixis_count            画面を見ないと指す先が分からない語（寝かせ）
    src/clarity.py                  上の物差しが、人の側の数（維持率）と相関するかの測り

**どれも「数を数える」形です。** 「この文は、耳で聞いて意味が取れるか」を
**本文そのものに当てて言う役は、1つもありませんでした。**
`clarity.py` が測ったとおり、数の個数は維持率と**向きが安定しません** ——
数え上げの物差しだけでは「分かりやすいか」に届かない、という実測が既に在ります。

ここが足すのは**評価者**です。読み上げ全文を渡して、
**分かりにくい所を批判的に全部 挙げさせ**、直して、**白紙から評価し直す**。

## **「ほとんど言いがかり」を、どう機械で決めるか**（ここがこの module の要）

オーナーの止め方は「**1番可能性が高いものが、ほとんど言いがかりになったら終わり**」です。
評価者に「これは言いがかりですか」と訊いてはいけません —— 挙げた本人に採点させると、
**自分の指摘は全部 正当だと言います**（この repo が何度も踏んでいる「言っている所と、
している所が別」の形）。だから**指摘の外側**に、2つの門を置きました。

    門A  **根拠が本文に在るか**（機械。模型を使わない）
         指摘は `quote`（読み上げからの**逐語引用**）を必ず持つ。
         その文字列が、そのコマの `narration` に**そのまま無ければ落とす** ——
         本文に無い所を指しているものは、**本文の評価ではありません**

    門B  **独立にもう1回 評価して、再現するか**（オーナーが例に挙げた物差し）
         同じ読み上げ全文を、**別のセッションで**もう1回 評価させる。
         run A の指摘が、run B の**同じコマの、重なる範囲**にも挙がっていれば「再現した」。
         再現しないものは、その回の模型の揺れ ＝ **言いがかり**

    **輪の終わり**  門A を通った指摘のうち**いちばん上のもの**が、門B で再現しなければ
                   ＝「1番可能性が高いものが、ほとんど言いがかり」→ **輪を終える**

**なぜ「いちばん上」だけを見るか。** オーナーの文がそう言っているからです。
評価者には「可能性が高い順に並べろ」と指示してあるので、
**先頭が言いがかりなら、その下はもっと言いがかり**という読み方になります。
（覆る条件: 先頭だけが外れて 2位以下が毎回 再現する、が実測で続いたら、
  「上位 N件 のうち1件でも再現すれば続ける」に変えること。**そのときは
  `data/clarity_loop.jsonl` の `top_confirmed` と `any_confirmed` の差を数えてから。**）

## 直すのは narration だけ（**絵・棒・図は1つも触らない**）

書き直しの指示は「**言い換えだけ。新しい数を足さない・画面に無い数を言わない**」です。
理由は、この repo の検査が**耳と目の対応**を見ているから ——
`_check_narrated_shown`（耳が言った数は画面に在るか）・`_check_ear_load`（一息の数の個数）・
`_check_assumption_value_shown`。narration に数を足すと、**絵を描き直さない限り**
そこが落ちます。だから**言い換えに閉じ**、さらに**機械でも縛ります**:

    書き直しの前後で `verify.script_only_problems` と
    `script_writer.{long,short}_script_problems` を数え、**増えたらその周を捨てる**
    （＝ 直前の台本に戻して輪を止める）。**分かりやすくして検査に落ちるのは、退化です。**

### **1周で全部を直させないこと**（2026-09-03 に実測して足した）

最初は「その周の再現した指摘を**全部**」書き直させました。**09/05 の本で 27件 が
1回の書き直しに乗り、機械の検査が 0件 → 3件 に増えて、周ごと捨てになりました**
（前提の値がコマから消えた 2件 ＋ 一息の数が 5個 になった 1件）。
どうせ**毎周 白紙から評価し直す**ので、1周で直すのは**上位 `FIX_PER_ROUND` 件**だけです。
残りは次の周に、また上から挙がります。

### 検査が増えたら、**捨てる前に直させる**（同じ回に足した）

`script_writer.generate()` が既にやっている形と同じです —— 落ちた事実をそのまま
渡して、`REWRITE_FIX_TRIES` 回まで書き直させる。それでも増えるなら、
その周を捨てて止めます（**分かりやすくして検査に落ちるのは、退化**）。

## 止め方（上限と、直らないときの出口）

    1. 門A を通った指摘が 0件                     → 終わり（言いがかりしか無い）
    2. いちばん上の指摘が門B で再現しない           → 終わり（**オーナーの止め方**）
    3. いちばん上の指摘の `quote` が、前の周と同一   → **直っていない** → 止める
    4. 書き直しで機械の検査が増えた                 → その周を捨てて止める
    5. `ROUNDS_MAX` 周                            → 止める

3 が要るのは、書き直しが**その文に触らなかった**ときです。同じ引用が2周 続けて
先頭に来るなら、**この評価者と書き手の組では直りません** ——
回し続けても模型の時間を払うだけなので、そこで出します（残りは控えに残る）。

## 模型の選び方（オーナー 09/03 07:3x）

> 「単純な記録、定型検査、機械的修正は軽いモデル ● 仮説検証、題材選定、動画の構成改善など
>   高レバレッジ部分はFable ● Fableを使う価値が実測で薄い仕事には使わない
>   ● 仕事ごとにFable・Opus・Sonnet・Haikuを選ぶ」

**評価と書き直しは、既定で台本を書くのと同じ模型**（`config/channel.yaml` の
`generation.model` ＝ いま `opus`）です。**Fable にしていません**:

    毎本 **評価 2回 × 最大4周 ＋ 書き直し 最大4回** ＝ 1本で最大12回の呼び出し。
    台本の生成そのもの（1本 4〜6回）より多く、**毎日 全部の本に当たります。**
    「Fable のみ」の枠は 100% で止まり、越えた1日はサブが全部 落ちます
    （`scripts/quota.fable_rate()` の註）。**そこへ毎本 12回を積む理由が、まだ実測に無い。**

**覆る条件**（Fable へ倒す条件を、先に書いておきます）:

    `data/clarity_loop.jsonl` で、**門A・門B を通った指摘が 1本あたり 0.5件 未満**が
    10本 続いたら、この模型では「分かりにくい所」を見つけられていない ——
    そのときは1本だけ `CLARITY_MODEL=fable` で撃ち、同じ本で件数を比べること。
    増えなければ**この仕事に Fable を使う価値は薄い**（オーナーの3行目）ので、
    模型ではなく**評価の訊き方**を疑うこと。
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path

from pydantic import BaseModel, Field

from . import config

#: 輪の上限。**評価2回 ＋ 書き直し1回 が1周**なので、4周で最大12回の呼び出し。
ROUNDS_MAX = int(os.environ.get("CLARITY_ROUNDS_MAX", "4"))

#: 1回の評価で受け取る指摘の上限（**「批判的に全て」を潰さない数**）。
FINDINGS_MAX = 40

#: **1周の書き直しに乗せる指摘の数**（上の「1周で全部を直させないこと」）。
#: 毎周 白紙から評価し直すので、残りは次の周にまた上から挙がります。
FIX_PER_ROUND = 8

#: 書き直しが機械の検査を増やしたときに、**落ちた事実を渡して直させる**回数。
REWRITE_FIX_TRIES = 2

#: 仕事場に残す控え。`verify._check_clarity_loop()` がこれを門にする。
REPORT_NAME = "clarity_loop.json"

#: 何周で何件 直したかの帳面（模型の選び方の「覆る条件」を判定する行）。
LEDGER = config.ROOT / "data" / "clarity_loop.jsonl"

_SPACE = re.compile(r"[\s　]+")


class Finding(BaseModel):
    """分かりにくい所 1件。**`quote` が無いものは、門A で落ちます。**"""

    seg: int = Field(description="コマ番号（1から数える）")
    quote: str = Field(description="そのコマの読み上げからの**逐語引用**（10〜40文字）")
    why: str = Field(description="耳だけで聞いたとき、なぜ意味が取れないか")
    fix: str = Field(description="どう言い換えれば取れるか（数を足さずに）")


class Reading(BaseModel):
    """1回ぶんの評価。**分かりにくい可能性が高い順**に並べる。"""

    findings: list[Finding] = Field(description="分かりにくい所を、可能性が高い順に全部")


class Rewritten(BaseModel):
    seg: int = Field(description="コマ番号（1から数える）")
    narration: str = Field(description="言い換えた読み上げ（数は足さない・減らさない）")


class Rewrite(BaseModel):
    segments: list[Rewritten] = Field(description="書き直したコマだけ")


# ---------------------------------------------------------------- 訊き方

READ_PROMPT = """次は、日本語の解説動画1本ぶんの**読み上げ全文**です。
コマ番号つきで並べます。

{body}

## あなたの仕事

視聴者は**耳だけで**これを聞きます（画面は見ていない・巻き戻さない・前提の知識は無い）。
**分かりにくい部分を、批判的に、1つ残らず挙げてください。** 遠慮しないこと ——
「まあ分かるだろう」で見逃すより、挙げすぎるほうが良い。

分かりにくさの例（これに限りません）:

- 指す先が音だけでは決まらない（「この2つ」「そちら」「先ほどの線」）
- 1文で数を持たされすぎて、耳に残らない
- 語の定義が出る前に、その語で説明している
- 主語や条件が落ちていて、誰の・いつの話か決まらない
- 文が長く、係り受けが音で切れない
- 同じ音の語が近くにあって、どちらか決まらない（同音異義）
- 前のコマとの繋がりが飛んでいて、話題が変わったことが分からない

## 出し方の決まり

- **可能性が高い（＝ほんとうに分かりにくい）順に並べること。** 先頭を1番にする。
- `quote` は、そのコマの読み上げから**一字一句そのまま**写すこと
  （**写し違えた指摘は機械が捨てます**）。10〜40文字。
- `fix` は**言い換えだけ**を書くこと。**新しい数字を足さない。**
  画面に出ていない値を持ち出さない。
- 分かりにくい所が本当に1つも無ければ、`findings` は空にしてよい。
- 多くても {findings_max} 件まで。
"""

FIX_PROMPT = """次の読み上げの、下に挙げるコマが**耳だけでは分かりにくい**と評価されました。

{body}

## 直すところ

{findings}

## 決まり（**ここを外すと、直した本が投稿前の検査に落ちます**）

- **言い換えだけ。** 新しい数字・割合・年・金額を1つも足さないこと。
  いま読み上げに在る数は、**そのまま同じ数だけ**残すこと（**減らすのも不可** ——
  そのコマから数が消えると「前提の値が画面のどこにもない」で落ちます）。
- **1つのコマに、数（金額・年齢・割合・個数・順位）を5個以上 入れないこと。**
  いま5個 以上 入っているコマは、**その数のまま**（増やさない）。
- 画面（図・表）は書き直しません。だから**画面に無い値を新しく言わないこと。**
- 1文を短く切るのは良い。指す先を名詞で言い直すのも良い。
- **挙げられたコマだけ**を出すこと。触っていないコマは出さない。
- 文字数は元の ±25% に収めること（尺が動くので）。
{extra}"""

RETRY_NOTE = """
## **前の書き直しは、投稿前の検査に落ちました。** 直してください

{problems}

上の決まりを守ったまま、**同じコマをもう一度**出し直してください。
"""


# ---------------------------------------------------------------- 本文

def lines(script: dict) -> list[str]:
    """読み上げ全文（コマの順）。"""
    return [str(s.get("narration") or "") for s in script.get("segments", [])]


def fingerprint(text_lines: list[str]) -> str:
    """読み上げ全文の指紋。**控えが本当にこの本のものか**を verify が確かめるのに使う。"""
    body = "\n".join(str(x) for x in text_lines).encode("utf-8")
    return hashlib.sha256(body).hexdigest()[:16]


def body_of(text_lines: list[str]) -> str:
    return "\n".join(f"{i + 1}. {ln}" for i, ln in enumerate(text_lines))


def norm(s: str) -> str:
    """引用を比べる形（空白だけ畳む。**文字は落とさない** —— 逐語であることが門A）。"""
    return _SPACE.sub("", s or "")


# ---------------------------------------------------------------- 門A・門B

def span(f: Finding, text_lines: list[str]) -> tuple[int, int] | None:
    """**門A** —— その引用が、そのコマの読み上げに逐語で在るか。無ければ `None`。"""
    i = int(f.seg) - 1
    if i < 0 or i >= len(text_lines):
        return None
    hay, needle = norm(text_lines[i]), norm(f.quote)
    if len(needle) < 4:
        return None                      # 短すぎる引用は、どこでも当たる ＝ 根拠にならない
    at = hay.find(needle)
    return None if at < 0 else (at, at + len(needle))


def grounded(findings: list[Finding], text_lines: list[str]) -> list[Finding]:
    """門A を通ったものだけ（**順番は保つ** —— 先頭が「1番可能性が高いもの」）。"""
    return [f for f in findings if span(f, text_lines) is not None]


def reproduced(f: Finding, other: list[Finding], text_lines: list[str]) -> Finding | None:
    """**門B** —— もう1回の評価に、同じコマの**重なる範囲**の指摘が在るか。"""
    a = span(f, text_lines)
    if a is None:
        return None
    for g in other:
        if int(g.seg) != int(f.seg):
            continue
        b = span(g, text_lines)
        if b is not None and a[0] < b[1] and b[0] < a[1]:
            return g
    return None


def confirmed(a: list[Finding], b: list[Finding], text_lines: list[str]) -> list[Finding]:
    """2回の評価の**両方に出た**指摘（run A の順を保つ）。"""
    return [f for f in a if reproduced(f, b, text_lines) is not None]


# ---------------------------------------------------------------- 模型を叩く

def model_name(channel: dict | None = None) -> str:
    """使う模型（上の「模型の選び方」）。`CLARITY_MODEL` で差し替えられる。"""
    forced = os.environ.get("CLARITY_MODEL", "").strip()
    if forced:
        return forced
    try:
        return str((channel or config.load_channel())["generation"]["model"])
    except Exception:                                          # noqa: BLE001
        return "opus"


def read_once(text_lines: list[str], *, model: str, timeout: int = 900) -> list[Finding]:
    """評価を1回。**セッションを共有しないこと**（門B が独立でなくなる）。"""
    from .claude_cli import ask                                # noqa: PLC0415

    out, _ = ask(Reading,
                 READ_PROMPT.format(body=body_of(text_lines), findings_max=FINDINGS_MAX),
                 model=model, timeout=timeout)
    return list(out.findings)[:FINDINGS_MAX]


def rewrite_once(text_lines: list[str], findings: list[Finding], extra: str = "", *,
                 model: str, timeout: int = 900) -> dict[int, str]:
    """指摘されたコマを**言い換えさせる**。返るのは `{コマ番号(0起点): 新しい読み上げ}`。

    `extra` には、前の書き直しが落とした機械の検査をそのまま渡します
    （`script_writer.generate()` の書き直しの輪と同じ形）。
    """
    from .claude_cli import ask                                # noqa: PLC0415

    said = "\n".join(
        f"- コマ{f.seg}「{f.quote}」…… {f.why}（直し方の案: {f.fix}）" for f in findings)
    out, _ = ask(Rewrite,
                 FIX_PROMPT.format(body=body_of(text_lines), findings=said, extra=extra),
                 model=model, timeout=timeout)
    fixed: dict[int, str] = {}
    for row in out.segments:
        i = int(row.seg) - 1
        text = str(row.narration or "").strip()
        if 0 <= i < len(text_lines) and text:
            fixed[i] = text
    return fixed


# ---------------------------------------------------------------- 機械の検査（退化の門）

def mech_problems(script: dict, topic_id: str, portrait: bool) -> list[str]:
    """**書き直しで壊れていないか**を数える所（上の「直すのは narration だけ」）。"""
    from . import verify                                       # noqa: PLC0415
    from .script_writer import (VideoScript, long_script_problems,  # noqa: PLC0415
                                short_script_problems)
    out = list(verify.script_only_problems(script, portrait))
    try:
        model = VideoScript.model_validate(script)
    except Exception as exc:                                   # noqa: BLE001
        return out + [f"台本の形が壊れた（{type(exc).__name__}）"]
    out += (short_script_problems(model, topic_id) if portrait
            else long_script_problems(model, topic_id))
    return out


# ---------------------------------------------------------------- 輪

def loop(script: dict, topic_id: str, work: Path | None = None, *,
         channel: dict | None = None, portrait: bool = False,
         rounds: int = ROUNDS_MAX, model: str | None = None,
         reader=None, rewriter=None, log=print) -> dict:
    """**毎本これを撃つ。** オーナーの3文をそのまま形にしたもの。

        1. 読み上げ全文を、**批判的に全部** 評価する（2回・独立に）
        2. 門A（根拠が本文に在るか）・門B（もう1回で再現するか）を通す
        3. **いちばん上が再現しなければ 終わり**（「ほとんど言いがかり」）
        4. 再現したら、その周の**再現した指摘を全部** 言い換えさせる
        5. **白紙から** 1 へ戻る（前の列挙は1件も引き継がない）

    返すのは控えの dict。`script` は**その場で書き換えます**（narration だけ）。
    `reader` / `rewriter` を渡すと模型を叩かずに回せる（検査用）。
    """
    model = model or model_name(channel)
    reader = reader or (lambda ls: read_once(ls, model=model))
    rewriter = rewriter or (lambda ls, fs, extra="": rewrite_once(ls, fs, extra, model=model))

    text_lines = lines(script)
    start_print = fingerprint(text_lines)
    try:
        base = mech_problems(script, topic_id, portrait)
    except Exception as exc:                                   # noqa: BLE001
        # **ここで投げないこと。** 投げると控えが1つも残らず、`verify` の門が
        # 「輪を通っていない」と読んで**その本を落とします**（＝ 投稿が1日 落ちる）。
        log(f"[clarity] 機械の検査を数えられませんでした（{type(exc).__name__}）")
        base = []
    report: dict = {"rounds": [], "model": model, "fixed": 0, "start": start_print,
                    "segments": len(text_lines), "reason": "", "topic": topic_id}
    last_top = ""

    for r in range(1, max(1, rounds) + 1):
        try:
            a = reader(text_lines)
            b = reader(text_lines)
        except Exception as exc:                               # noqa: BLE001
            # **ここで投稿を止めないこと。** 模型が落ちたのは、本の欠陥ではない。
            report["reason"] = f"評価に失敗（{type(exc).__name__}: {exc}）"
            log(f"[clarity] 評価に失敗しました（{type(exc).__name__}）。輪を抜けます")
            break
        ga, gb = grounded(a, text_lines), grounded(b, text_lines)
        hits = confirmed(ga, gb, text_lines)
        row = {"round": r, "raw": [len(a), len(b)], "grounded": [len(ga), len(gb)],
               "confirmed": len(hits),
               "top": (ga[0].model_dump() if ga else None),
               # **見るのは「いちばん上」だけ**（オーナーの止め方。上の節）。
               # `hits[0]` と比べないこと —— 同じ引用が2件 挙がると取り違えます。
               "top_confirmed": bool(ga and reproduced(ga[0], gb, text_lines) is not None),
               "any_confirmed": bool(hits)}
        report["rounds"].append(row)
        log(f"[clarity] {r}周目: 挙がった {len(a)}件/{len(b)}件 → "
            f"根拠あり {len(ga)}件/{len(gb)}件 → 両方に出た {len(hits)}件")

        if not ga:
            row["stop"] = "根拠のある指摘が1件も無い"
            report["reason"] = row["stop"]
            log("[clarity] 根拠のある指摘が0件 → 輪を終えます")
            break
        # **オーナーの止め方** —— いちばん上が再現しない ＝ ほとんど言いがかり。
        if not row["top_confirmed"]:
            row["stop"] = "1番可能性が高いものが、独立の評価で再現しなかった（＝ほとんど言いがかり）"
            report["reason"] = row["stop"]
            log(f"[clarity] 先頭「{ga[0].quote[:24]}」は2回目に出ませんでした → 輪を終えます")
            break
        # **直っていない**（書き直しがその文に触らなかった）。
        if norm(ga[0].quote) == last_top:
            row["stop"] = "同じ指摘が2周 続けて先頭に来た（この組では直らない）"
            report["reason"] = row["stop"]
            log(f"[clarity] 同じ指摘が直りません（{ga[0].quote[:24]}） → 止めます")
            break
        last_top = norm(ga[0].quote)

        # **1周で全部を直させないこと**（上の節。27件 を1回に乗せて周ごと捨てた実測）。
        take = hits[:FIX_PER_ROUND]
        row["asked"] = len(take)
        extra = ""
        fixed: dict[int, str] = {}
        after = list(text_lines)
        grew = base
        for attempt in range(REWRITE_FIX_TRIES + 1):
            try:
                fixed = rewriter(text_lines, take, extra)
            except Exception as exc:                           # noqa: BLE001
                row["stop"] = f"書き直しに失敗（{type(exc).__name__}）"
                fixed = {}
                log(f"[clarity] 書き直しに失敗しました（{type(exc).__name__}）")
                break
            if not fixed:
                row["stop"] = "書き直しが1コマも返らなかった"
                break
            after = list(text_lines)
            for i, text in fixed.items():
                after[i] = text
            if after == text_lines:
                row["stop"] = "書き直しても本文が変わらなかった"
                fixed = {}
                break
            trial = json.loads(json.dumps(script))
            for i, text in fixed.items():
                trial["segments"][i]["narration"] = text
            grew = mech_problems(trial, topic_id, portrait)
            if len(grew) <= len(base):
                break
            # **捨てる前に、落ちた事実を渡して直させる**（`script_writer` と同じ形）。
            row["broke"] = grew[:3]
            row["retries"] = attempt + 1
            log(f"[clarity] 書き直しが検査を増やしました（{len(base)}→{len(grew)}件）"
                f"。落ちた事実を渡して直させます（{attempt + 1}/{REWRITE_FIX_TRIES}）")
            if attempt >= REWRITE_FIX_TRIES:
                # **分かりやすくして検査に落ちるのは退化。** その周は捨てる。
                row["stop"] = f"書き直しで機械の検査が {len(base)}件 → {len(grew)}件 に増えた"
                fixed = {}
                break
            extra = RETRY_NOTE.format(
                problems="\n".join(f"- {p}" for p in grew[len(base):] or grew[:3]))
        if not fixed:
            report["reason"] = row.get("stop") or "書き直しが通らなかった"
            break

        for i, text in fixed.items():
            script["segments"][i]["narration"] = text
        text_lines = after
        base = grew
        row["rewrote"] = sorted(i + 1 for i in fixed)
        report["fixed"] += len(fixed)
        log(f"[clarity] {len(fixed)}コマ を言い換えました（コマ {row['rewrote']}）"
            " → **白紙から評価し直します**")
    else:
        report["reason"] = f"上限 {rounds}周 に達した"
        log(f"[clarity] 上限 {rounds}周 に達しました")

    report["end"] = fingerprint(text_lines)
    report["changed"] = report["end"] != start_print
    if work is not None:
        work.mkdir(parents=True, exist_ok=True)
        (work / REPORT_NAME).write_text(
            json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    record(report)
    log(f"[clarity] {len(report['rounds'])}周・{report['fixed']}コマ 直した"
        f"（{report['reason']}）")
    return report


def record(report: dict) -> None:
    """帳面へ1行（模型の選び方の「覆る条件」を判定するのに要る）。"""
    rows = report.get("rounds") or []
    row = {"topic": report.get("topic", ""), "model": report.get("model", ""),
           "rounds": len(rows), "fixed": report.get("fixed", 0),
           "confirmed": sum(int(x.get("confirmed") or 0) for x in rows),
           "grounded": sum(int((x.get("grounded") or [0, 0])[0]) for x in rows),
           "raw": sum(int((x.get("raw") or [0, 0])[0]) for x in rows),
           "reason": report.get("reason", ""), "changed": bool(report.get("changed"))}
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass
