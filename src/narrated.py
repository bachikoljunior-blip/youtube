"""**読み上げが言った数が、その文の絵に1つも出ていないか。**

## なぜ要るか（2026-08-17。**独立評価の指摘を測って入れた**）

前の回の独立評価で2体が「図解の棒に、読み上げが言った行が無い」と書き、
申し送りが3回運ばれました。`src/premise.py` は**節を決めている値**（コード側）が
画面に出ているかを見ますが、**読み上げの文そのものは誰も見ていません。**

    premise.py   計算の入力  →  画面   （書き手が持っていなかった値）
    narrated.py  読み上げの数 →  絵     （書き手が言ったのに描かなかった値）

**向きが逆で、当たる相手も別です。** `premise.py` の2件と、この道具が拾う3件は
1件も重なりません（2026-08-17 に実物84本で確認）。

耳が「85歳までの手取り差は49万5643円」と言っているのに、画面には
`1609万5643円` と `1560万円` しか無い —— **引き算の答えだけが絵に無い。**
視聴者は暗算するか、聞き流すかの二択になります。`CLAUDE.md` の

> **前提と計算式を、画面と説明欄に全部出す。**

に直接あたります。**耳で言って目に出さない数は、追試できません。**

## 実測（2026-08-17・投稿済み84本 / 読み上げ491行）

    素で数えると          8件 ／ 7本
    丸めと表記ゆれを外す  **3件 ／ 3本**（残り5件は全部誤報。下記）

**残った3件は全部本物**でした。

    9hqzUxqBjBE  「1,000円上げると年32,940円増です」
                 画面は 394,999円 → 395,000円（＝1円差）と 30,000円 の段。
                 **1,000円 はどこにも無い**
    WSJAjK1Xo-I  「85歳までの手取り差は49万5643円」
                 画面は 1609万5643円 と 1560万円 だけ。**差そのものが無い**
    YBZFmrsL_kk  「42万5千円からは25等級」
                 画面は 424,999円 まで。**25等級の入口 425,000 が無い**

### 外した5件は、2つの形しかありませんでした

**① 丸めて言っている**（4件）。`16万円台` に対し画面は `16万1782円`、
`1121万円` に対し `1121万2500円`。**これは欠陥ではありません** ——
耳で7桁を読み上げないのは、むしろ正しい。
だから**言った桁までで比べます**（`16万` なら 16万〜17万のどこかに
実物があれば通す。`49万5643` のように1円まで言ったものは1円まで一致を要求）。

**② 表記がちがう**（1件）。`1億5000万円` と読み、画面は `1億5千万`。
**同じ値です。** だから字面ではなく**値**で比べます。

## 見るもの

**その読み上げ文にあてた絵だけ**を見ます（`reveal_variants` が割った
コマをまとめ直したもの）。**動画ぜんたいで見ないこと** ——
別の文の絵に出ていても、その5秒間の視聴者には見えていません。
実測でも、ぜんたいで見ると 9hqzUxqBjBE の1件が消えます。

**描かれていない棒（`scale_bars`）は画面に数えません。** あれは軸を
固定するためだけの控えで、そのコマには描かれていません。

**1000未満は見ません**（`premise.py` と同じ）。年・月数・日数・人数・
等級番号・率が大半で、当たりが薄いわりに誤報だけ増えます。
"""
from __future__ import annotations

import re

# 1,234 / 12.5 / 20万1千 / 1億5千万 …
_NUM = re.compile(r"[0-9][0-9,]*(?:\.[0-9]+)?(?:[億万千百][0-9,]*(?:\.[0-9]+)?)*")
_UNIT = {"億": 10 ** 8, "万": 10 ** 4, "千": 10 ** 3, "百": 10 ** 2}

# **1000未満を見ない理由は `premise.py` と同じ。** 下げると誤報だけが増えます。
FLOOR = 1_000


def parse(tok: str) -> tuple[float, float] | None:
    """`1億5千万` → (150000000, 10000000)。値と、**言った桁の大きさ**を返す。

    2つめが要るのは、**丸めて言うのは欠陥ではない**からです。
    `16万` は「16万〜17万のどこか」しか言っておらず、画面の `16万1782円` と
    食い違ってはいません。1円まで言ったものだけ、1円まで一致を要求します。
    """
    s = tok.replace(",", "")
    if not s or not s[0].isdigit():
        return None
    return _split(s, 1.0)


def _split(s: str, scale: float) -> tuple[float, float] | None:
    """大きい位から順に切って足す。**位は右にあるものが左へ掛かります。**

    `1億5千万` の `5千` は「5×千」ではなく「5×千×万」です（＝5000万）。
    左から順に足す書き方だと、ここで必ず落ちます（2026-08-17 に踏んだ）。
    """
    if s == "":
        return 0.0, 0.0
    for unit, mult in _UNIT.items():
        head, sep, tail = s.partition(unit)
        if not sep:
            continue
        if head == "":
            return None
        left = _split(head, scale * mult)
        right = _split(tail, scale)
        if left is None or right is None:
            return None
        places = [p for p in (left[1], right[1]) if p]
        return left[0] + right[0], (min(places) if places else scale)
    try:
        return float(s) * scale, scale
    except ValueError:
        return None


def numbers(text: str) -> list[tuple[str, float, float]]:
    """文の中の数を `(書き方, 値, 言った桁)` で返す。"""
    out = []
    for m in _NUM.finditer(text):
        tok = m.group(0).rstrip(",.")
        got = parse(tok)
        if got is not None:
            out.append((tok, got[0], got[1]))
    return out


def shown_values(frames: list[dict]) -> set[float]:
    """そのコマ群に**実際に描かれている**数。`scale_bars` は入れません。"""
    buf: list[str] = []
    for f in frames:
        for k in ("headline", "stat", "note", "stat_source", "formula"):
            buf.append(str(f.get(k) or ""))
        buf.extend(str(x) for x in (f.get("items") or []))
        buf.extend(str(x) for x in (f.get("headers") or []))
        for row in f.get("rows") or []:
            buf.extend(str(c) for c in row)
        for b in f.get("bars") or []:
            buf.append(str(b.get("label") or ""))
            buf.append(str(b.get("display") or ""))
    return {v for _, v, _ in numbers("\n".join(buf))}


def unshown(line: str, frames: list[dict]) -> list[str]:
    """その文が言った数のうち、**その絵に1つも出ていないもの**を返す。"""
    seen = shown_values(frames)
    out = []
    for tok, value, place in numbers(line):
        if value < FLOOR:
            continue
        # 言った桁の中に実物があれば通す（`16万` は 16万〜17万のどこかを指す）。
        if any(value - 0.5 <= d < value + max(place, 1.0) for d in seen):
            continue
        out.append(tok)
    return out


def scan(narration: list[str], groups: list[list[dict]]) -> list[str]:
    """人が読む1行の一覧。空なら問題なし。

    `groups[i]` は `narration[i]` にあてたコマ群です。**数が合わないときは
    見送ります**（対応が取れないものを当てずっぽうで突き合わせない）。
    """
    if len(groups) != len(narration):
        return []
    problems = []
    for line, frames in zip(narration, groups):
        for tok in unshown(line, frames):
            problems.append(
                f"読み上げ「{line}」の {tok} が、その文の絵に1つも出ていません。"
                "**耳で言って目に出していない数です。** 棒か行か見出しに足すこと"
            )
    return problems
