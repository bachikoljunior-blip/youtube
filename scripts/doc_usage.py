#!/usr/bin/env python3
"""**手順書のどの節が、実際に使われているか**を数える（2026-08-18 に足した）。

## なぜ要るか（**測ってから作っています**）

`retro.py` の問い1（この回でいちばん時間を食ったのはどこか）を縦に読むと、
**直近2回が2回とも「`trigger_main.md` を読むところ」**でした。

    2026-08-17 23:1x   約12分（1648行）
    2026-08-18 01:2x   約20分（1696行）  ← 読む時間 ≒ 作る時間（実装2件で約18分）

**そのあいだに文書は 48行 増えています。** 1周が42分なので、
**読むだけで1周の3〜5割**です。これは在庫でも投稿でもなく、**手順の重さ**が
そのまま目標から遠ざけている形です。

## 何を測っているか（**そして、測っていないもの**）

**測れないもの**: 「その回が実際にどの節を読んだか」。読むのは人（私）の中で
起きるので、記録が残りません。**そこを推測で埋めないこと。**

**測れるもの**: **その節に固有の語が、日誌と ship の本文に出てくるか。**
日誌はその回が実際にやったことの記録なので、
**「この節の話題が、実際の回に一度でも登場したか」**の下限になります。

    参照 0件 の節 = **20回以上の回で、一度も話題になっていない**

**これは「要らない」の証明ではありません。** §0 の枝合わせのように
**毎回使うのに日誌に書かれない**節があります（当たり前すぎて書かない）。
だから出すのは**候補**で、**捨てる判断は人がやること。**

## 語の作り方（**手で並べないこと**）

節に固有の語は、**その節の本文から機械で引きます** ——
バッククォートで囲まれた識別子（`sibling_check.py` `_hit_outcome` など）と、
`session_...` のID、`2026-08-NN` の日付。**手で語彙を並べると、
次に節を足した回が必ず書き忘れます**（このリポジトリで通算11回の形）。

**ありふれた語は落とします**（`python` `git` など。**閾値で落とすので、
禁止語の一覧を持ちません** —— 一覧は育たないまま古くなるため）。

    python scripts/doc_usage.py                     # 大きい順・参照0件を先頭に
    python scripts/doc_usage.py --doc docs/GOAL.md  # 別の文書でも同じことをする
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# バッククォートの中の識別子・ファイル名・関数名。**節の本文から引きます。**
_TOKEN = re.compile(r"`([^`\n]{3,60})`")
# 日付（節が「いつ踏んだか」を書く形。日誌にも同じ日付が出ます）
_DATE = re.compile(r"20\d\d-0\d-\d\d")
# 見出し。`#` の数が深さ。
_HEAD = re.compile(r"^(#{2,5})\s+(.*)$")

# **ありふれすぎて、どの節にも属さない語**を落とす閾値。
# 文書全体で **この回数を超えて出てくる語**は、節の固有名ではありません。
COMMON_AT = 6


def sections(text: str) -> list[dict]:
    """見出しで切って、節ごとの本文と行数を返す。"""
    lines = text.splitlines()
    heads = [(i, m.group(1), m.group(2).strip())
             for i, ln in enumerate(lines) if (m := _HEAD.match(ln))]
    out = []
    for n, (i, hashes, title) in enumerate(heads):
        end = heads[n + 1][0] if n + 1 < len(heads) else len(lines)
        out.append({"line": i + 1, "depth": len(hashes), "title": title,
                    "lines": end - i, "body": "\n".join(lines[i:end])})
    return out


def tokens_of(body: str) -> set[str]:
    """その節に出てくる、固有名らしい語。**手で並べていません。**"""
    got = {t.strip() for t in _TOKEN.findall(body)}
    got |= set(_DATE.findall(body))
    # 記号だけ・数字だけ・日本語の文らしいものを落とす。
    return {t for t in got
            if len(t) >= 3 and not t.isdigit()
            and re.search(r"[A-Za-z_./]|20\d\d-", t)
            and " " not in t.strip()}


def haystack(recent: int = 0) -> str:
    """**その回が実際にやったこと**の記録。日誌と ship の本文。

    ## `recent` を足した理由（**最初の版は何も言えませんでした**）

    2026-08-18 の最初の実装は、**日誌の全文**を相手にしていました。
    結果は **参照0件の節が 0件** ——「全部の節が使われている」に見えますが、
    **判定が甘いだけ**です。日誌は2万行あり、節が挙げる道具の名前
    （`status.py` `batch_build` …）は**どこかには必ず出てきます。**

    **「一度でも出たか」は、ほぼ全部に当たる質問でした。**
    これは `src/alerts.py` が畳んでいる「当たりを含まないまま育つ一覧」と
    同じ形で、**向きが逆**（育つのではなく、最初から全部が当たりになる）。

    だから既定を **直近 N 回**にします。訊いているのは
    **「この節の話題は、最近の回に出てきたか」**です。
    """
    parts = []
    j = ROOT / "docs" / "JOURNAL.md"
    if j.exists():
        text = j.read_text(encoding="utf-8")
        if recent:
            # 回の切れ目は `## 2026-..` の見出し。**末尾から N 回ぶん。**
            heads = [m.start() for m in re.finditer(r"(?m)^## 20\d\d-\d\d-\d\d", text)]
            if len(heads) > recent:
                text = text[heads[-recent]:]
        parts.append(text)
    r = ROOT / "data" / "runs.jsonl"
    if r.exists():
        rows = []
        for line in r.read_text(encoding="utf-8").splitlines():
            try:
                row = json.loads(line)
            except Exception:                                  # noqa: BLE001
                continue
            if row.get("what"):
                rows.append(str(row["what"]))
        parts.extend(rows[-recent * 3:] if recent else rows)
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--doc", default="docs/trigger_main.md")
    ap.add_argument("--top", type=int, default=15)
    ap.add_argument("--recent", type=int, default=20,
                    help="直近この回数ぶんの日誌と ship だけを相手にする（0で全文）")
    args = ap.parse_args()

    path = ROOT / args.doc
    if not path.exists():
        print(f"[!] ありません: {args.doc}")
        return 1
    text = path.read_text(encoding="utf-8")
    secs = sections(text)
    hay = haystack(args.recent)

    # **文書全体での出現数**で、ありふれた語を落とす。
    everywhere = Counter()
    for s in secs:
        for t in tokens_of(s["body"]):
            everywhere[t] += 1

    for s in secs:
        own = {t for t in tokens_of(s["body"]) if everywhere[t] <= COMMON_AT}
        s["tokens"] = own
        s["hits"] = sum(1 for t in own if t in hay)

    total = len(text.splitlines())
    print(f"=== {args.doc}（{total}行 / 節 {len(secs)}件）===")
    print(f"  相手にした記録: **直近 {args.recent} 回**"
          if args.recent else "  相手にした記録: **日誌の全文**（甘すぎます。註を読むこと）")
    print("  **その節に固有の語が、日誌と ship の本文に出てくるか**を数えています。")
    print("  **「読んだか」は測れません**（記録が残らない）。**これは下限です。**")

    # **語が1つも取れなかった節は、判定できません。** 0件と混ぜないこと。
    unjudgeable = [s for s in secs if not s["tokens"]]
    cold = [s for s in secs if s["tokens"] and s["hits"] == 0]

    print(f"\n--- **参照0件で、行数の大きい節**（上位{args.top}）---")
    print("  **「要らない」の証明ではありません。** 毎回使うのに日誌に書かれない節"
          "（§0 の枝合わせなど）があります。**捨てる判断は人がやること。**")
    for s in sorted(cold, key=lambda x: -x["lines"])[:args.top]:
        print(f"  {s['lines']:4d}行  L{s['line']:<5d} {'#' * s['depth']} {s['title'][:58]}")
    print(f"  参照0件の節は {len(cold)}件・合計 {sum(s['lines'] for s in cold)}行"
          f"（文書の {sum(s['lines'] for s in cold) / max(total, 1):.0%}）")

    print(f"\n--- 判定できない節 {len(unjudgeable)}件"
          f"（固有の語が1つも取れなかった。**0件と混ぜないこと**）---")
    for s in sorted(unjudgeable, key=lambda x: -x["lines"])[:5]:
        print(f"  {s['lines']:4d}行  L{s['line']:<5d} {'#' * s['depth']} {s['title'][:58]}")

    hot = sorted((s for s in secs if s["hits"]), key=lambda x: -x["hits"])[:8]
    print("\n--- よく出てくる節（**残すほう**）---")
    for s in hot:
        print(f"  参照{s['hits']:3d}件  {s['lines']:4d}行  {'#' * s['depth']} {s['title'][:52]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
