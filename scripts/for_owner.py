#!/usr/bin/env python3
"""docs/FOR_OWNER.md の「出す」列を扱う。

**なぜこれが要るか。** 親は毎時発火しますが、同じセッションが続くので
文脈が要約されます。**つまり「前回これを出したか」を親は覚えていません。**
覚えていないまま「未処理をそのまま出す」と、同じ依頼が毎時くり返されます
（2026-08-16、オーナーから「繰り返すな」と指示）。

**解き方は「記憶を持たせる」ではなく「記憶を要らなくする」です。**
依頼1件ごとに **出す時間帯（窓）** をファイル側に書いておき、親は
**いまの時刻が窓に入っているかだけ**を見る。窓は1時間で、親の cron は毎時なので、
**1つの窓には発火がちょうど1回しか入りません** ＝ 1回だけ出ます。

    親が要るもの: 現在時刻と、このファイル。それだけ
    親が要らないもの: 前回の記憶、状態ファイル、書き込み権限

**窓が過ぎれば自動的に出なくなります。** 子が片付けに来なくても正しく黙るので、
**正しさが子の実行タイミングに依存しません。** 子がやるのは整理だけです。

使い方:

    python scripts/for_owner.py                    いま親が出すはずの本文を出す
    python scripts/for_owner.py --at '2026-08-16 11:09'   その時刻で試す
    python scripts/for_owner.py --list             窓の一覧（過去・未来も）
    python scripts/for_owner.py --check            書式の検査（CI 向け。異常なら 1）
    python scripts/for_owner.py --expire           窓が過ぎた分を「出した」へ移す
"""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

JST = timezone(timedelta(hours=9))
DOC = Path(__file__).resolve().parent.parent / "docs" / "FOR_OWNER.md"

SEC_OUT = "## 出す"
SEC_DONE = "## 出した（記録）"

# ### 出す 2026-08-16 11:00〜12:00 JST — 見出し
HEAD_RE = re.compile(
    r"^### 出す (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})〜(\d{2}:\d{2}) JST(?: — (.*))?$"
)


class Block:
    def __init__(self, head: str, start: datetime, end: datetime,
                 label: str, lines: list[str]):
        self.head = head
        self.start = start
        self.end = end
        self.label = label
        self.lines = lines          # 見出しの次から、次の見出しの手前まで（生の行）

    @property
    def body(self) -> str:
        """引用（`> `）の中身だけ。親が出すのはこれです。"""
        out = []
        for ln in self.lines:
            if ln.startswith(">"):
                out.append(ln[1:].lstrip(" ") if ln[1:2] == " " else ln[1:])
            elif not ln.strip() and out:
                out.append("")
        while out and not out[-1].strip():
            out.pop()
        return "\n".join(out)

    def text(self) -> str:
        return "\n".join([self.head] + self.lines).rstrip() + "\n"


def _split(md: str) -> tuple[list[str], list[str], list[str]]:
    """(出す節より前, 出す節の中身, 出す節より後) に切る。"""
    lines = md.split("\n")
    try:
        i = lines.index(SEC_OUT)
    except ValueError:
        raise SystemExit(f"{DOC} に「{SEC_OUT}」の節がありません")
    j = i + 1
    while j < len(lines) and not (lines[j].startswith("## ")):
        j += 1
    return lines[: i + 1], lines[i + 1 : j], lines[j:]


def parse(md: str) -> tuple[list[Block], list[str]]:
    """出す節の中の窓ブロックと、書式の問題を返す。"""
    _, body, _ = _split(md)
    blocks: list[Block] = []
    problems: list[str] = []
    cur: Block | None = None
    for ln in body:
        if ln.startswith("### "):
            m = HEAD_RE.match(ln)
            if not m:
                # 窓ではない見出し（説明の小見出し）は無視する。ただし「出す」で
                # 始まっていて形が違うものは、書き間違いなので必ず言うこと。
                if ln.startswith("### 出す"):
                    problems.append(f"窓の見出しの書式が違う: {ln!r}")
                cur = None
                continue
            day, hs, he, label = m.groups()
            start = datetime.strptime(f"{day} {hs}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)
            end = datetime.strptime(f"{day} {he}", "%Y-%m-%d %H:%M").replace(tzinfo=JST)
            if end <= start:
                problems.append(f"窓の終わりが始まり以前: {ln!r}")
                cur = None
                continue
            if end - start > timedelta(hours=1):
                problems.append(
                    f"窓が1時間より長い（毎時の発火が2回入り、2回出ます）: {ln!r}"
                )
            cur = Block(ln, start, end, label or "", [])
            blocks.append(cur)
        elif cur is not None:
            cur.lines.append(ln)
    for b in blocks:
        if not b.body.strip():
            problems.append(f"本文（`> ` の行）が空: {b.head!r}")
    for a, b in zip(blocks, blocks[1:]):
        if a.start <= b.start < a.end or b.start <= a.start < b.end:
            problems.append(f"窓が重なっている（同じ回で2件出ます）: {a.head!r} / {b.head!r}")
    return blocks, problems


def now_jst() -> datetime:
    return datetime.now(timezone.utc).astimezone(JST)


def due(blocks: list[Block], at: datetime) -> list[Block]:
    return [b for b in blocks if b.start <= at < b.end]


def cmd_show(blocks: list[Block], at: datetime) -> int:
    hit = due(blocks, at)
    if not hit:
        return 0
    print("\n\n".join(b.body for b in hit))
    return 0


def cmd_list(blocks: list[Block], at: datetime) -> int:
    if not blocks:
        print("（窓はありません ＝ 親は何も出しません）")
        return 0
    for b in blocks:
        state = "いま出す" if b.start <= at < b.end else ("これから" if at < b.start else "過ぎた")
        print(f"{b.start:%Y-%m-%d %H:%M}〜{b.end:%H:%M} JST  [{state}]  {b.label}")
    return 0


def cmd_expire(md: str, at: datetime) -> int:
    blocks, _ = parse(md)
    passed = [b for b in blocks if at >= b.end]
    if not passed:
        print("移すものはありません")
        return 0
    head, body, tail = _split(md)
    keep: list[str] = []
    cur_passed = False
    for ln in body:
        if ln.startswith("### "):
            cur_passed = any(ln == b.head for b in passed)
        if not cur_passed:
            keep.append(ln)
    new = head + keep + tail
    md2 = "\n".join(new)

    moved = "\n".join(
        b.text().replace("### 出す ", "### 出した ", 1) for b in passed
    )
    out = md2.split("\n")
    if SEC_DONE in out:
        # 節の**末尾**に足す（先頭に足すと、節の説明文が記録の下に潜ります）
        i = out.index(SEC_DONE)
        j = i + 1
        while j < len(out) and not out[j].startswith("## "):
            j += 1
        while j > i + 1 and not out[j - 1].strip():
            j -= 1
        md2 = "\n".join(out[:j] + ["", moved.rstrip()] + out[j:])
    else:
        md2 = md2.rstrip() + "\n\n---\n\n" + SEC_DONE + "\n\n" + moved.rstrip() + "\n"
    DOC.write_text(md2.rstrip() + "\n", encoding="utf-8")
    for b in passed:
        print(f"移した: {b.start:%m/%d %H:%M}〜{b.end:%H:%M} {b.label}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--at", help="この時刻(JST, 'YYYY-MM-DD HH:MM')で判定する")
    ap.add_argument("--list", action="store_true", help="窓の一覧")
    ap.add_argument("--check", action="store_true", help="書式の検査")
    ap.add_argument("--expire", action="store_true", help="過ぎた窓を「出した」へ移す")
    a = ap.parse_args()

    at = (
        datetime.strptime(a.at, "%Y-%m-%d %H:%M").replace(tzinfo=JST)
        if a.at
        else now_jst()
    )
    md = DOC.read_text(encoding="utf-8")

    if a.expire:
        return cmd_expire(md, at)

    blocks, problems = parse(md)
    if a.check:
        for p in problems:
            print(f"NG: {p}", file=sys.stderr)
        if problems:
            return 1
        print(f"OK: 窓 {len(blocks)} 件、書式に問題なし")
        return 0
    if problems:
        for p in problems:
            print(f"警告: {p}", file=sys.stderr)
    if a.list:
        return cmd_list(blocks, at)
    return cmd_show(blocks, at)


if __name__ == "__main__":
    raise SystemExit(main())
