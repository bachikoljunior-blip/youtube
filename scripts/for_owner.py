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

# ---------------------------------------------------------------------------
# **窓の本文（＝ 親が出す `>` の中身）の上限**（2026-09-19 06:2x・optimizer・opus・ultracode）
# ---------------------------------------------------------------------------
# **オーナー原文**（受け取り帳 `476e04fa`・2026-09-19 06:2x JST）:
#
#     「操作依頼出す時は最小手順出すようにしてくれない？」
#
# **踏んだ実測**（この註を書いた回に数えた・生きていた窓 3つ）:
#
#     09/19 09:00  **1,920字**   手順は 3行。残りは「なぜ、これがいま一番大事か」「この1枚で決まること」「距離」
#     09/19 20:00  **1,188字**   手順は 3行。残りは「なぜ、いま一番これなのか」（日ごとの表の説明）
#     09/20 09:00  **1,145字**   手順は 4行。残りは (A)/(B) の分かれ目の説明
#     書き直したあと **512 / 412 / 233字**
#
# **`docs/FOR_OWNER.md`「子が守ること」には、2026-08-16 から
# 「引用の中に『操作依頼』以外を書かないこと」と書いてありました。**
# **3つ とも、その字を破っていました。** ＝ 字で書いても守られないので、**形の検査**にします
# （`quote_runs` を足したときと同じ理由・この file 冒頭の註）。
#
# **700 は、書き直した中でいちばん長い窓（512字）の 1.4倍**です。
# 手順とリンクだけなら届かず、理由を 1段 足すと越えます。
#
# **覆る条件**:
#  (1) 手順そのものが 700字 を越える操作が来たら（例: 貼る文面が長い申請フォーム）、
#      **数を上げる前に「貼る文面」を `>` の外に置けないかを見ること**
#      —— 09/19 20:00 の窓は、貼る文面 160字 を中に置いたまま 412字 に収まっています。
#  (2) オーナーが「理由も一緒に出して」と言ったら、この検査ごと畳むこと（原文が上書きします）。
# ---------------------------------------------------------------------------
#: 窓の本文の上限（字）。上の註のとおり **オーナーの原文が根拠**です。
BODY_MAX = 700

SEC_OUT = "## 出す"
SEC_DONE = "## 出した（記録）"

# ### 出す 2026-08-16 11:00〜12:00 JST — 見出し
#
# **ダッシュは `—`（1つ）でも `——`（2つ）でも通します**（2026-09-19 00:2x・optimizer・opus）。
# **なぜ緩めたか（実測。踏んだのはこの 1回 ではありません）**: 09/18 23:xx の回が
# `### 出す 2026-09-19 08:00〜09:00 JST —— **1行だけ貼ってください…**` と書き、
# **`——`（2つ）だったので この行に当たらず、窓は 1つも登録されませんでした** ——
# `--list` に出ず、親も出しません。**その窓は「これが通るまで動画が1本も作れません」でした。**
# repo の見出しは `docs/` も `CLAUDE.md` も **ほぼ全部 `——`（2つ）**で書かれているので、
# 1つ だけを通す形は「この file だけが repo と違う字を要求する」罠です。**罠の側を直しました。**
# `--check` は前から NG を出しますが（exit 1）、**書いた回が撃っていませんでした** ——
# 同じ註が `docs/FOR_OWNER.md`「子が守ること」にも在り、**2度目です**（1度目 2026-09-08 15:1x の 2時間 窓）。
# ＝ **「撃て」と書く手はもう 2度 効かなかったので、撃たれなくても通る形にする側を採りました。**
# 後ろの字は飾りで、親が読むのは日付と刻だけです（`Block.body` は引用の中身しか出しません）。
#
# **覆る条件**: (1) 見出しの後ろの字で親の出し分けを決める回が来たら、ここを厳しく戻すこと
#     （いまは `label` を誰も読んでいません）。(2) `——` 以外の区切り（`:` や `|`）で書いた回が
#     出たら、字を足さずに **`--check` を CI に入れる**こと ——字を足す競争にしない。
HEAD_RE = re.compile(
    r"^### 出す (\d{4}-\d{2}-\d{2}) (\d{2}:\d{2})〜(\d{2}:\d{2}) JST(?: —{1,2} (.*))?$"
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


def quote_runs(lines: list[str]) -> int:
    """窓の本文の中で、`>` の行が**いくつの塊に分かれているか**を数える。

    **なぜ要るか（2026-09-19 05:5x・optimizer・opus・実物を踏んだ）**:
    `6308651e` が 09/19 09:00 の窓へ 【3】 を足したとき、**次の窓の見出し
    `### 出す 2026-09-19 20:00〜21:00 JST` を、足す字で上書きして消しました。**
    見出しが消えると、その窓の本文（`>` の塊）は**手前の窓の本文の続きになります** ——
    親は 09:00 に 4件 を出し、20:00 には何も出しません。

    **`--check` は 3つ とも通していました**: 重なりも、長すぎる窓も、空の本文も
    無いからです。**窓が 1つ 減ったことを見る目が、どこにも在りませんでした**
    （`--list` も「8件 → 7件」としか出ず、減った事実は数を覚えていないと分かりません）。
    **ここで効く不変量は「窓の本文は `>` の 1塊」です** —— 実測で、
    健全な窓 7つ は全部 1塊、壊れた窓だけが 2塊 でした（偽陽性 0）。

    **この形は 3度目です**（この file 冒頭の註に 2度分: 2026-09-08 15:1x の 2時間窓・
    09/18 23:xx の `——` の見出し）。どちらも「書いた回が `--check` を撃て」と直しましたが、
    **2度とも撃たれていません。** ＝ **撃たれなくても壊れない側**（形の検査）を足します。

    **覆る条件**: (1) 引用を意図的に 2塊 に割りたい窓が出たら（例: 本文の途中に
        表や図を素の行で挟む）、この検査ではなく**その書き方**を疑うこと ——
        `Block.body` は素の行を落とすので、挟んだ字はどのみち親に出ません。
        それでも要るなら、塊の間を `>` の空行（`>` だけの行）でつなぐこと ＝ 1塊 のまま書けます。
    (2) 見出しの書式を緩めた回が来たら、この検査と一緒に読むこと
        （見出しが当たらない ＝ ここでも 2塊 に見えます。**同じ壊れ方の別の入口**です）。
    """
    runs, inrun = 0, False
    for ln in lines:
        if ln.startswith(">"):
            if not inrun:
                runs += 1
                inrun = True
        else:
            inrun = False
    return runs


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
        if len(b.body) > BODY_MAX:
            problems.append(
                f"窓の本文が {len(b.body)}字 で上限 {BODY_MAX}字 を越えています"
                "（＝ 最小手順ではありません。理由・背景・数字は `>` の外へ出すこと。"
                "オーナー 2026-09-19 06:2x「操作依頼出す時は最小手順出すようにしてくれない？」）"
                f": {b.head!r}"
            )
        if quote_runs(b.lines) > 1:
            problems.append(
                "1つ の窓の中に引用の塊が2つ以上あります"
                "（**手前の窓が、次の窓の見出しごと本文を飲み込んだ形**です。"
                f"飲み込まれた側は出ません）: {b.head!r}"
            )
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
