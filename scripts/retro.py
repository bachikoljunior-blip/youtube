#!/usr/bin/env python3
"""1周の頭で、**前の回の申し送りを受け取る**。

**これは「設計の見直し」ではありません。** 見直し本体は
`docs/trigger_main.md` §6 (a2)（終わりぎわ）です。オーナーの2件目が
「**実行の最初ではなく**」と訂正しており、そちらに従っています。

これは **(a2) の渡し先を開ける道具**です。(a2) は自分でこう書いています ——
「ここで気づいた設計変更は、この回では実行できません。次の子に渡るところまでが1件」。
渡し先は日誌の「次の回へ」で、**それを読む手順がどこにもありませんでした。**

`docs/trigger_main.md` に `JOURNAL.md` は4回出てきますが、
**4回とも「書け」で、「読め」が1回もありません。**
`CLAUDE.md` には「末尾10件を読む」とありますが、**実際の手順書のほうに無い。**
**受け取る側が無ければ、(a2) は空に書き込むだけになります。**

その結果が、8/15 の題名です ——
「計器が3つ壊れていた」「独立評価が実績と永久に突き合わない」
「棒グラフの目盛りが2種類壊れていた」「画面に主語が出ていない」。
**毎回ちがう穴を見つけていますが、種類は全部同じ**（＝人が見れば一目で分かる欠陥を、
機械検査が素通りさせている）。**前の回を読んでいれば、次の穴を探しに行けたはずです。**

`grep -n "^### 次の回" docs/JOURNAL.md` は **20件**返ります。
**20回ぶんが、読まれないまま積まれていました。**

## 出すもの

1. 直近の `ship`（`data/runs.jsonl`）を種類別に。**偏っていたら、それが設計の癖**
2. 直近 N 回の「**次の回へ**」を全文
3. **2回以上の申し送りに出てくる語** ＝ 持ち越し。潰れていない証拠
4. **§6 (a2) の問い1を、縦に**（2026-08-15 に足した）
5. **前に「道筋」を見てから何回か。** 8回で1度、(a2) の問い4を出す

## 4 と 5 を足した理由（2026-08-15）

オーナーから「終わりに設計を見直す、は全部見てる？」と訊かれ、**答えは「いいえ」**でした
（(a2) の問い3つは主語が全部「この回」）。**そのとき一緒に見つかったのが 4 です。**

**(a2) の答えが、書かれたきり読み返されていませんでした。** ただし全部ではありません ——
実測すると、**問い3は6件中4件が「次の回へ」に昇格**しており（3件は「（上の見直し3）」と明記）、
**問い2は答えが「手順を直す」なのでその回のうちに `trigger_main.md` が書き換わります。**

**届いていなかったのは問い1だけ**でした。そして**問い1は、1回ぶんでは何も言いません。**
6件を縦に並べると「**作る段が4回・対象のせいが5回**」で、
**8/15 19:0x の並列化（CPU 2〜4%）は、この形に気づいた回**です。
**気づいたのは偶然で、並べる道具はありませんでした。** それが 4 です。

    python scripts/retro.py            # 直近8回
    python scripts/retro.py --n 12
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JOURNAL = ROOT / "docs" / "JOURNAL.md"
RUNS = ROOT / "data" / "runs.jsonl"

HANDOFF_RE = re.compile(r"^#{2,4}\s*次の回")
DATE_RE = re.compile(r"^##\s+(.*)$")
# §6 (a2) の節。見出しは 2026-08-15 に固定したが、**それ以前の3種類も拾う**
# （「この回の設計の見直し（§6 (a2)）」「この回の見直し（§6 a2）」「設計の見直し（§6 (a2)）」）。
# 過去のぶんが読めないと、縦に並べる意味がありません。
REVIEW_RE = re.compile(r"^#{2,4}\s*(?:この回の)?(?:設計の)?見直し（§6")
ITEM_RE = re.compile(r"^\s*([1-9])\.\s+(.*)$")
# 問い4に答えた回の印。次はここから数える（§6 (a2)「発火のさせ方」）。
ROUTE_MARK = "[道筋]"
ROUTE_EVERY = 8
# 申し送りの中で「同じものを指している」と機械で言える語だけを拾う。
# 散文の名詞を拾うと何もかも一致するので、**識別子と鉤括弧に限る。**
TOKEN_RE = re.compile(r"`([^`\n]{3,40})`|「([^」\n]{3,30})」")
# **潰した宣言**。日誌は「〜はこの回で閉じました」と、毎回この形で書いています
# （実測7件・2026-08-16）。**書く側はあったのに、読む側がありませんでした**（下）。
#
# **「閉じた」まで拾わないこと**（2026-08-16 09:5x に、入れた直後の実物で踏みました）。
# 「**一度閉じた後の再発**」という、**閉じていないことを言うための行**が
# 宣言として読まれ、`critique_queue` が丸ごと黙りました。**言葉の向きが逆です。**
# 丁寧形（「閉じました」）だけが宣言で、連体形は文中の言及に出ます。
CLOSED_RE = re.compile(r"閉じました")
# 宣言の形をしていても、**閉じていないことを言っている行**は数えない。
REOPEN_RE = re.compile(r"再発|閉じていない|閉じたつもり|閉じられていない")
# **引用符の中の「閉じました」は、宣言ではなく“その文字列の名前”です**
# （2026-08-16 10:xx。**同じ穴の3枚目**を実物で踏みました）。
#
# 09:5x の回が、自分の踏んだ穴をこう書き残しました ——
#
#     `closures()` を「`閉じました` か `閉じた`」で書いて回したら、`critique_queue` が
#
# **この行そのものが宣言として読まれ、`critique_queue` がまた丸ごと黙りました。**
# 09:5x が足した `REOPEN_RE` は効きません（この行に `再発` が無い）。
# **偽の宣言を説明する文が、次の偽の宣言になっています。**
#
# 直すのは語彙の足し算ではなく、**どこを読むか**のほう。バッククォートの中は
# 「その語を名指ししている」ので、**動詞として読まない。**
# 語（`TOKEN_RE`）は逆に中からしか拾わないので、両者は同じ行を別々に見ます。
CODE_SPAN_RE = re.compile(r"`[^`\n]*`")


def prose_only(line: str) -> str:
    """バッククォートで囲った部分を落とし、**地の文だけ**を返す。"""
    return CODE_SPAN_RE.sub("　", line)


def blocks_under(text: str,
                 head_re: re.Pattern[str]) -> list[tuple[str, list[str], int]]:
    """`head_re` に当たる見出しの中身を、直前の `## 日付` と**行番号**と一緒に返す。

    行番号を返すのは、**「潰したと宣言された後の言及か」を時系列で見るため**です
    （`carry_over()`）。日付だけだと、同じ回の中で「閉じました」と書いた行そのものが
    持ち越しの1回として数えられます。
    """
    lines = text.split("\n")
    blocks: list[tuple[str, list[str], int]] = []
    for i, line in enumerate(lines):
        if not head_re.match(line):
            continue
        date = ""
        for j in range(i, -1, -1):
            m = DATE_RE.match(lines[j])
            if m:
                date = m.group(1)
                break
        body: list[str] = []
        for k in range(i + 1, len(lines)):
            if re.match(r"^#{1,4}\s", lines[k]):
                break
            body.append(lines[k])
        while body and not body[-1].strip():
            body.pop()
        blocks.append((date, body, i))
    return blocks


def handoff_blocks(text: str) -> list[tuple[str, list[str], int]]:
    return blocks_under(text, HANDOFF_RE)


def closures(text: str) -> dict[str, int]:
    """**「この語はこの回で閉じました」を、日誌から拾う。**

    返すのは `語 → 宣言された行番号`（同じ語が何度も閉じられていたら**最後の1回**）。
    行番号で持つのは、**閉じた後にまた出てきたら、それは本当の再発**だからです
    （`critique_queue` は 04:2x に閉じて、そのあと別の理由で戻っています）。
    """
    found: dict[str, int] = {}
    for i, line in enumerate(text.split("\n")):
        # **宣言かどうかは地の文で見る。語は元の行から拾う**（`prose_only`）。
        bare = prose_only(line)
        if not CLOSED_RE.search(bare) or REOPEN_RE.search(bare):
            continue
        for m in TOKEN_RE.finditer(line):
            tok = (m.group(1) or m.group(2)).strip()
            if tok:
                found[tok] = i
    return found


def first_lines(body: list[str], want: str) -> str:
    """(a2) の節から、番号 `want` の項目の**1行目だけ**を返す。

    全文を出すと「次の回へ」と二重になって重くなります。**縦に並べたいのは
    「どこが重かったか」の一言だけ**なので、1行目で足ります。
    """
    for line in body:
        m = ITEM_RE.match(line)
        if m and m.group(1) == want:
            return m.group(2).strip()
    return ""


def tokens(body: list[str]) -> set[str]:
    found = set()
    for m in TOKEN_RE.finditer("\n".join(body)):
        tok = (m.group(1) or m.group(2)).strip()
        if tok:
            found.add(tok)
    return found


def ship_summary(n: int) -> tuple[Counter, list[str]]:
    kinds: Counter = Counter()
    recent: list[str] = []
    if not RUNS.exists():
        return kinds, recent
    rows = []
    for line in RUNS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    ships = [r for r in rows if r.get("kind") == "ship"]
    for r in ships[-n:]:
        what = r.get("what", "")
        head = what.split(":", 1)[0].strip() if ":" in what[:12] else "?"
        kinds[head] += 1
        recent.append(f"  {r.get('at', '')[5:16]}  {what[:96]}")
    return kinds, recent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=8, help="さかのぼる回数。既定8")
    args = ap.parse_args()

    print("=" * 72)
    print(f"前の回を読む（直近 {args.n} 回）— **設計を見直してから、この回を決めること**")
    print("=" * 72)

    kinds, recent = ship_summary(args.n)
    print(f"\n## 出したもの（直近 {args.n} 件の ship）\n")
    if kinds:
        total = sum(kinds.values())
        for k, c in kinds.most_common():
            print(f"  {k:<8} {c:2d} 件  ({c * 100 // total}%)")
        print()
        for line in recent:
            print(line)
        if kinds.most_common(1)[0][1] * 2 > total:
            top = kinds.most_common(1)[0][0]
            print(f"\n  → **{top} に偏っています。** 同じ種類の手だけを打っていないか。")
    else:
        print("  記録がありません。")

    journal = JOURNAL.read_text(encoding="utf-8")
    closed = closures(journal)
    blocks = handoff_blocks(journal)[-args.n:]
    print(f"\n\n## 「次の回へ」（{len(blocks)} 件）\n")
    for date, body, _ in blocks:
        print(f"── {date}")
        for line in body:
            print(f"  {line}")
        print()

    seen: defaultdict[str, list[str]] = defaultdict(list)
    muted: defaultdict[str, int] = defaultdict(int)
    for date, body, start in blocks:
        for tok in tokens(body):
            if tok in closed and start <= closed[tok]:
                muted[tok] += 1      # **潰したと宣言された後より前の言及**
                continue
            seen[tok].append(date[:16])
    carried = {t: ds for t, ds in seen.items() if len(ds) >= 2}
    print("\n## 持ち越し（2回以上の申し送りに出てくる語）\n")
    if carried:
        for tok, dates in sorted(carried.items(), key=lambda kv: -len(kv[1])):
            tail = "  ← **一度閉じた後の再発**" if tok in closed else ""
            print(f"  {len(dates)}回  {tok}{tail}")
            print(f"        {' / '.join(dates)}")
        print("\n  **これは「毎回言っているのに、まだ潰れていない」ものの候補です。**")
        print("  この回で1件は潰すこと。潰せないなら、なぜ潰さないかを JOURNAL に書く。")
    else:
        print("  ありません。（申し送りが毎回すべて片づいている、"
              "か、書き方が毎回違って機械では追えていない）")
    # **落としたものは必ず言うこと。** 黙って削ると「全部見た」に見えます。
    if muted:
        print("\n  --- **閉じたと日誌が宣言しているので、上から外したもの** ---")
        for tok, n in sorted(muted.items(), key=lambda kv: -kv[1]):
            print(f"  {n}回ぶん  {tok}")
        print("  **宣言のほうが間違っていることもあります**（閉じたつもりで閉じていない）。"
              "\n  疑うなら日誌の宣言を読み、実物に当たること。**言及の回数は証拠になりません。**")

    review_all = blocks_under(journal, REVIEW_RE)
    reviews = review_all[-args.n:]
    print(f"\n\n## 設計の見直し（§6 (a2)）を**縦に読む**（{len(reviews)} 件）\n")
    if reviews:
        print("  1回ぶんでは何も言いませんが、**並べると癖が出ます。**")
        print("  （問い1の1行目だけ。全文は日誌に）\n")
        for date, body, _ in reviews:
            q1 = first_lines(body, "1")
            print(f"  {date[:16]:<18} {q1[:88] if q1 else '（問い1に答えていない回）'}")
    else:
        print("  記録がありません。")

    # 問い4（いまの道筋）は判断で決めない。前の [道筋] から数えて機械が言う。
    since = None
    for i, (_, body, _s) in enumerate(reversed(review_all)):
        if any(ROUTE_MARK in line for line in body):
            since = i
            break
    print()
    if since is None:
        print(f"  **道筋の見直しは、まだ1度もありません**（(a2) は {len(review_all)} 件）。")
        due = len(review_all) >= ROUTE_EVERY
    else:
        print(f"  前に道筋を見てから **{since} 回**（{ROUTE_EVERY} 回で1度）。")
        due = since >= ROUTE_EVERY
    if due:
        print("  → **この回は、(a2) の問い4（いまの道筋）に答えること。**")
        print(f"     答えたら (a2) の節に `{ROUTE_MARK}` と書く（次がここから数えます）。")
    else:
        print("  → この回は問い1〜3だけでよい。")

    print("\n" + "=" * 72)
    print("**同じ種類の穴が続いていないか。** 直近の題名を並べて、種類で括ってみること。")
    print("違う穴を毎回1つずつ塞いでいるように見えて、**種類が同じなら、")
    print("塞ぐべきは穴ではなく、穴を作っている側**です。")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
