"""**末尾の問いかけ（コメント・共有を取る枠）の判定を、Data API 抜きで下す。**

## 何を判定するか

`config/hypotheses.yaml`:

    claim         ショートの最後を「答えやすい問いかけ」で終えると、共有とコメントが付く
    deadline      2026-08-22
    falsified_if  問いかけ型にした後のショートが計2000再生に達した時点で、コメントが2件未満

**Analytics は日次で3日遅れる**ので、期限から3日を引いた **08/19 が実効の期限**です
（`docs/trigger_main.md` §4）。この道具を書いた 08/20 の時点で、**すでに過ぎています。**

## なぜ Data API を使わないか（2026-08-20 08:2x に M8 で踏んだのと同じ形）

母集団を決めるのに「公開済みの動画IDを全部引く」と、`playlistItems` と
`videos.list` を叩くことになります。**日枠（JST 16:00 に戻り、数時間で尽きる）**
なので、**1日のうち16時間、この判定は構造的に下せません。**

母集団は手元にあります —— `data/uploaded.jsonl`（テーマID → 動画ID・題）と
`data/critique_queue/<動画ID>.json`（`narration`。**読み上げの全文**）。
**最後の1行が問いかけかどうかは、その控えを読めば分かります。**

## 「問いかけ型」をどう決めるか

**日付で切らないこと。** 型を変えた日は日誌にしか無く、写しはずれます。
控えの `narration[-1]` を見て、**問いかけの形かどうか**で決めます。

    「あなたの所定給付日数は、何日ですか。」          → 問いかけ
    「率と額、どちらで見ていましたか。コメントで…」   → 問いかけ
    「前提は再就職手当の給付率です。」                → ちがう

日本語の疑問文は文末が「か」で終わるとは限りません（「…ですか。コメントで
教えてください。」のように**後ろに文が続く**）。だから**文末ではなく、
行のどこかに疑問の印があるか**で見ます。

## **数えてみたら、比較する群がありませんでした**（2026-08-20 10:2x）

控えのあるショート **375本が375本とも問いかけ型**です（読み上げが空の2本を除く）（`population()` の内訳）。
つまりこの仮説には**対照群が1本もありません** —— 「問いかけ型のほうが付く」は、
**付くか付かないかしか言えない形**で置かれていました。
反証条件（`2000再生でコメント2件未満`）が絶対値なのはそのためです。

**この判定で言えるのは「この枠ではコメントは取れない」までで、
「問いかけが悪い」ではありません。** 型を変えても比較先が無いので、
次に置く仮説は**同じ日の本を2群に割る形**にすること
（`script_writer.title_form` / `hook_form` と同じ）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LEDGER = ROOT / "data" / "uploaded.jsonl"
QUEUE = ROOT / "data" / "critique_queue"

#: 疑問の印。**文末に限定しないこと**（上の節）。
ASK = re.compile(r"(ですか|ますか|ませんか|でしょうか|ましたか|でしたか|[？?]|コメントで教えて)")

#: `falsified_if` の数。**設定と道具を離さないため、ここに置く。**
TRIGGER_VIEWS = 2000   # 問いかけ型のショートがこれに達して初めて判定に入る
NEED_COMMENTS = 2      # これ未満なら外れ


def load_ledger(path: Path | None = None) -> list[dict]:
    """`data/uploaded.jsonl` を素で返す。**API を叩かない。**"""
    lines = (path or LEDGER).read_text(encoding="utf-8").splitlines()
    return [json.loads(x) for x in lines if x.strip()]


def is_ask(narration: list[str]) -> bool:
    """読み上げの**最後の1行**が問いかけの形か。"""
    if not narration:
        return False
    return bool(ASK.search(narration[-1]))


def is_request(narration: list[str]) -> bool:
    """読み上げの**最後の1行**が「登録の依頼」か。（2026-08-26 夕に足した）

    ## なぜ `is_ask` の裏ではないのか

    **両方 入っている本があります。** `src/script_writer.py` は
    「**問いかけを残す余裕があるなら残してよいが、優先は依頼のほう**」と
    書いています。だから「問いかけでない ＝ 依頼」ではありません ——
    **依頼が在るかどうかを、独立に見ること。**

    そして「問いかけでない」の側には**長尺の「明日やること」型**も落ちます
    （長尺は依頼を書かない ＝ `src/script_writer.py`「維持率が落ちる」）。
    `not_ask` を依頼の群として数えると、**長尺の手順型が混ざります。**

    ## 何に使うか

    `config/hypotheses.yaml` 期限 2026-10-11
    「**ショートの最後で登録を直接1回頼むと、登録率が上がる**」の**処置群**は、
    これが真の本です。`scripts/deadline_check.py` の `published_group` に
    `endcard: request` を書くと、ここで絞ります。

    **覆る条件**: 依頼の文言が「登録」を含まない形（「チャンネルを追加して」など）に
    変わったら、ここに足すこと。**変えた回が足さないと、処置群が黙って空になります。**
    """
    if not narration:
        return False
    return "登録" in narration[-1]


def narration_of(video_id: str, queue: Path | None = None) -> list[str] | None:
    """その本の読み上げ全文。**読めなければ `None`**（空リストと区別すること）。

    `form_of()` がここを2度 読んでいたのを、1か所にまとめました。
    """
    path = (queue or QUEUE) / f"{video_id}.json"
    if not path.exists():
        return None
    try:
        nar = (json.loads(path.read_text(encoding="utf-8")) or {}).get("narration")
    except (OSError, ValueError):
        return None
    return list(nar) if isinstance(nar, list) else None


def is_mid_request(narration: list[str]) -> bool:
    """読み上げの**最後より前の行**に、登録の依頼が在るか。（2026-08-26 夜に足した）

    `src/script_writer.request_form()` の A/B の**処置**がこれです ——
    「終端の依頼はそのまま残したうえで、途中にもう1回」。

    ## `is_request` の否定ではありません

    `is_request` は `narration[-1]` **だけ**を見ます。ここは `narration[:-1]` を見ます。
    **両方 真の本が処置群**、**`is_request` だけ真の本が対照群**です。
    どちらも偽の本（依頼そのものが無い＝長尺・08/24 より前の本）は、
    **どちらの群でもありません**（`src/judgeable.py` が落とします）。

    ## 見分けの語を `is_request` と揃えてあること

    どちらも「登録」の1語で見ています。**片方だけ語を足さないこと** ——
    足すと、終端の判定と途中の判定で別の物差しになります。
    **覆る条件**: 依頼の文言が「登録」を含まない形に変わったら、**両方に**足すこと。
    """
    if len(narration) < 2:
        return False
    return any("登録" in str(line) for line in narration[:-1])


def mid_request_compliance(video_ids: list[str], queue: Path | None = None) -> dict:
    """処置群として作った本のうち、**実際に途中の依頼が入った割合**。

    ## なぜ要るか（`config/hypotheses.yaml` の `mid_request` が読みます）

    群はテーマIDのハッシュで割っています（`request_form`）。**割り当ては正しくても、
    モデルが指示に従ったとは限りません。** 従っていない本が処置群に混ざると、
    差は薄まり、`falsified_if` は「上回らなければ外れ」なので**外れに化けます**。
    2026-08-26 の `endcard: request` が、まさにその形で 51本中 46本を取り違えていました。

    **判定の前にここを見ること。** 8割を切っていたら、判定ではなく
    `MID_REQUEST_RULE` の書き方を直すのが先です。
    """
    seen = ok = missing = no_end = 0
    for vid in video_ids:
        nar = narration_of(vid, queue)
        if nar is None or not nar:
            missing += 1
            continue
        if not is_request(nar):
            no_end += 1          # 終端の依頼そのものが無い（＝群に入れない本）
            continue
        seen += 1
        ok += 1 if is_mid_request(nar) else 0
    return {
        "数えた": seen, "途中あり": ok, "控えが無い": missing, "終端の依頼が無い": no_end,
        "従った率": (ok / seen) if seen else None,
    }


def form_of(video_id: str, queue: Path | None = None) -> str | None:
    """その本の終端の型。`"request"` / `"ask"` / `"other"`、読めなければ `None`。

    **読めない本を `"other"` にしないこと** —— 型が分からないだけで、
    数えると群が実際より大きく見えます（`population()` の同じ注意）。
    """
    nar = narration_of(video_id, queue)
    if not nar:
        return None
    if is_request(nar):
        return "request"
    return "ask" if is_ask(nar) else "other"


def population(ledger: list[dict], queue: Path | None = None) -> tuple[list[str], dict]:
    """判定の母集団（**問いかけ型のショートの動画ID**）と、その内訳を返す。

    落とすもの:

        控えが無い本   … 型が読めない（08/15 より前に投稿した本がここに落ちます）
        読み上げが空   … 同上
        長尺           … `falsified_if` は「ショート」と書いてあります
        問いかけでない本

    **控えが無い本を「問いかけでない」に数えないこと。** 型が分からないだけで、
    数えると分母が実際より大きく見えます（＝反証条件が甘くなる）。
    """
    queue = queue or QUEUE
    ask, not_ask, no_queue, no_nar, longs = [], [], [], [], []
    seen: set[str] = set()
    for row in ledger:
        vid = row["video_id"]
        if vid in seen:
            continue
        seen.add(vid)
        if "#Shorts" not in (row.get("title") or ""):
            longs.append(vid)
            continue
        path = queue / f"{vid}.json"
        if not path.exists():
            no_queue.append(vid)
            continue
        nar = (json.loads(path.read_text(encoding="utf-8")) or {}).get("narration") or []
        if not nar:
            # 控えはあるが読み上げが空。**「問いかけでない」に数えないこと** ——
            # 型が分からないだけで、数えると分母が実際より大きく見えます。
            no_nar.append(vid)
            continue
        (ask if is_ask(nar) else not_ask).append(vid)
    return ask, {"ask": len(ask), "not_ask": len(not_ask), "no_narration": len(no_nar),
                 "no_queue": len(no_queue), "long": len(longs)}


def verdict(views: int, comments: int, shares: int) -> dict:
    """反証条件をそのまま当てる。

    `state` は3つだけ:

        "not_yet"    … 問いかけ型がまだ 2,000再生 に届いていない（判定しない）
        "falsified"  … 届いていて、コメントが2件未満（**外れ**）
        "held"       … 届いていて、コメントが2件以上（**保つ**）

    **共有は判定に入れません。** `falsified_if` が名指しているのはコメントだけで、
    共有は claim の本文にしか出てきません。**条件文のほうで判定すること**
    （`docs/HYPOTHESES.md`）。共有は返りに載せて、読む側が見ます。
    """
    base = {"views": views, "comments": comments, "shares": shares}
    if views < TRIGGER_VIEWS:
        return {**base, "state": "not_yet",
                "line": f"問いかけ型 {views:,}再生 < {TRIGGER_VIEWS:,} ＝ **まだ判定しない**"}
    if comments < NEED_COMMENTS:
        return {**base, "state": "falsified",
                "line": (f"問いかけ型 {views:,}再生 ≥ {TRIGGER_VIEWS:,}／"
                         f"コメント {comments}件 < {NEED_COMMENTS} ＝ **外れ**"
                         f"（共有 {shares}件）")}
    return {**base, "state": "held",
            "line": (f"問いかけ型 {views:,}再生 ≥ {TRIGGER_VIEWS:,}／"
                     f"コメント {comments}件 ≥ {NEED_COMMENTS} ＝ **保つ**"
                     f"（共有 {shares}件）")}


# ---------------------------------------------------------------------------
# **閉じた後の「覆る条件」**（2026-08-31 に、実際に発火してから書き直した）
# ---------------------------------------------------------------------------

#: 「この枠が効いている」と言えるコメント率の目安。**0.2%**。
#: 出所は `config/hypotheses.yaml` のこの前提の判定文
#: 「効く場合の目安として置いた 0.2%（2,000再生で期待4件）」。
#: **ここだけが目安の正本です。** 判定文の側を直したら、ここも直すこと。
BENCHMARK_RATE = 0.002

#: 覆るのは、目安の **1/4** に届いたとき。
#: なぜ 1/4 か: 目安ちょうど（0.2%）を門にすると「効いていると確定するまで
#: 測り直さない」になり、測り直す意味が無くなります。**測り直す値打ちが出る**のは
#: 「効いている水準と同じ桁に乗ったとき」なので、桁の下端を取っています。
REVERSAL_RATE = BENCHMARK_RATE / 4          # = 0.05%

#: 率だけだと、窓が小さいときに 1/1000 のような跳ねで発火します。**件数の床**。
REVERSAL_MIN_COMMENTS = 5


def reversal(views: int, comments: int) -> dict:
    """**閉じた判定が覆るか。** 覆るなら `{"reversed": True, ...}`。

    ## なぜ「1件でも付いたら覆る」をやめたか（2026-08-31 に、発火してから直した）

    2026-08-20 に閉じたとき、覆る条件はこう書いてありました:

        **チャンネル全体のコメントが、28日窓で1件でも視聴者から付いたとき**
        いまは 20,332再生で 0件なので、**1件出た時点でこの枠に信号があることになり、
        率を測り直す値打ちが出ます。**

    **2026-08-31 に、そのとおり発火しました** —— 問いかけ型 56,751再生 で
    **コメント 1件**（チャンネル全体 76,316再生 で 1件）。**初めて視聴者の
    コメントが付いた日**です（`videos.statistics.commentCount` ではなく
    `youtubeAnalytics` の `comments`。こちらは自チャンネルの書き込みを数えません ——
    135本に自分のコメントを付けてあって、なお 1件 なのがその証拠）。

    **それでも覆りません。** 率で見ると:

        1 / 56,751 = **0.0018%**   目安 0.2% の **1/114**

    **条件のほうが壊れていました。** 「1件でも」は**分母が伸びれば必ず満たされます** ——
    どんなに小さい底の率でも、再生が十分に積もれば 1件は出ます。
    **効果ではなく、時間の経過で発火する条件**です。閉じた判定を、
    効果の証拠が1つも無いまま開け直させます。

    そして今回は、**古い条件より強いことが言えるようになりました。** 08/20 は
    「20,332再生で 0件」＝ 率の上限しか言えませんでしたが、いまは
    **1件という実測**があるので、率そのものが 0.0018% と置けます。
    **「まだ測れていない」から「測ったら 114倍 足りない」へ変わった**ので、
    この前提はむしろ**閉じる側に固まりました。**

    ## これが覆る条件（**この関数そのものの**）

    - 目安 0.2% の出所（`BENCHMARK_RATE`）が実測で覆ったら、両方の数を直すこと。
      いまの 0.2% は「効く場合の目安として置いた」もので、**実測ではありません。**
    - コメントが収益に直で効く経路ができたら（例: コメント数が配信に効くと実測できたら）、
      率ではなく別の物差しに替えること。
    - **「1件でも」型の条件を、この repo の他の前提で見つけたら同じ形に直すこと。**
      `config/hypotheses.yaml` には 覆る条件 が 40件 あります。
    """
    rate = (comments / views) if views else 0.0
    ok_rate = rate >= REVERSAL_RATE
    ok_count = comments >= REVERSAL_MIN_COMMENTS
    reversed_ = ok_rate and ok_count
    return {
        "reversed": reversed_,
        "views": views,
        "comments": comments,
        "rate": rate,
        "need_rate": REVERSAL_RATE,
        "need_comments": REVERSAL_MIN_COMMENTS,
        "line": (
            f"覆る: コメント率 {rate*100:.4f}% >= {REVERSAL_RATE*100:.2f}% "
            f"かつ {comments}件 >= {REVERSAL_MIN_COMMENTS} ＝ **測り直す**"
            if reversed_ else
            f"覆らない: コメント率 {rate*100:.4f}%"
            + (f"（目安 {BENCHMARK_RATE*100:.1f}% の 1/{BENCHMARK_RATE/rate:.0f}）"
               if rate else "（0件）")
            + f"／門は {REVERSAL_RATE*100:.2f}% かつ {REVERSAL_MIN_COMMENTS}件"
        ),
    }
