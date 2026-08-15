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
# 申し送りの中で「同じものを指している」と機械で言える語だけを拾う。
# 散文の名詞を拾うと何もかも一致するので、**識別子と鉤括弧に限る。**
TOKEN_RE = re.compile(r"`([^`\n]{3,40})`|「([^」\n]{3,30})」")


def handoff_blocks(text: str) -> list[tuple[str, list[str]]]:
    lines = text.split("\n")
    blocks: list[tuple[str, list[str]]] = []
    for i, line in enumerate(lines):
        if not HANDOFF_RE.match(line):
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
        blocks.append((date, body))
    return blocks


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

    blocks = handoff_blocks(JOURNAL.read_text(encoding="utf-8"))[-args.n:]
    print(f"\n\n## 「次の回へ」（{len(blocks)} 件）\n")
    for date, body in blocks:
        print(f"── {date}")
        for line in body:
            print(f"  {line}")
        print()

    seen: defaultdict[str, list[str]] = defaultdict(list)
    for date, body in blocks:
        for tok in tokens(body):
            seen[tok].append(date[:16])
    carried = {t: ds for t, ds in seen.items() if len(ds) >= 2}
    print("\n## 持ち越し（2回以上の申し送りに出てくる語）\n")
    if carried:
        for tok, dates in sorted(carried.items(), key=lambda kv: -len(kv[1])):
            print(f"  {len(dates)}回  {tok}")
            print(f"        {' / '.join(dates)}")
        print("\n  **これは「毎回言っているのに、まだ潰れていない」ものの候補です。**")
        print("  この回で1件は潰すこと。潰せないなら、なぜ潰さないかを JOURNAL に書く。")
    else:
        print("  ありません。（申し送りが毎回すべて片づいている、"
              "か、書き方が毎回違って機械では追えていない）")

    print("\n" + "=" * 72)
    print("**同じ種類の穴が続いていないか。** 直近の題名を並べて、種類で括ってみること。")
    print("違う穴を毎回1つずつ塞いでいるように見えて、**種類が同じなら、")
    print("塞ぐべきは穴ではなく、穴を作っている側**です。")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
