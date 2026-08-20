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
