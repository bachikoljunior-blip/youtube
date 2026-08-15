#!/usr/bin/env python3
"""**テーマ在庫を、手ではなく機械で作る。**

    python scripts/topic_forge.py --list            # 未使用の見出しを数える（無料・数秒）
    python scripts/topic_forge.py --count 6         # 6件つくって config/topics.yaml に足す
    python scripts/topic_forge.py --count 6 --dry-run   # 出すだけで書かない

## なぜ要るか（2026-08-15）

`docs/MEANS.md` M14 が、8本/日の段について**同じことを3回書いています。**

    「**次に詰まるのもここです。** 8本/日にするなら在庫の作り方そのものを機械化すること」
    「**8の段は在庫のほうが先に折れます。** 段を上げる前に calc を増やすこと」
    「着手して分かった律速: **手段ではなく在庫でした**」

そして `scripts/retro.py` が拾う「次の回へ」でも、
**在庫の機械化が2回続けて持ち越し**になっていました。**手で足していたからです。**
8/15 の回は `config/topics.yaml` に8件を**手で**書いて9件に戻していますが、
それは1周ぶんの延命で、**次の回でまた同じ手作業に戻ります。**

## この道具が何をしているか（**新しい計算は1つも足しません**）

`src/calc/*.py` の出力は `=== 見出し ===` の節に分かれていて、
`topics.yaml` の `calc_sections:` が**そのうち1つを指す**仕組みです
（`src/script_writer.py`「渡さない表は、そもそもプロンプトに入れない」）。

つまり **1つの計算モジュールから、節の数だけ別のテーマが取れます。**
そして節がちがえば **画面に出る表そのものがちがう** ので、
`CLAUDE.md` の「同じ絵を続けない」に**構造として**当たりません。

    2026-08-15 の実測: 全 45 節のうち **16 節が未使用**

**この道具は、その未使用の節を数えて、割り当てて、題と狙いだけを書かせます。**
数字を発明させる余地はありません（数字は必ず `src/calc/` が出したもの）。

## 守っていること

- **calc をばらす。** 割り当ては calc モジュールを1つずつ回るので、
  N件つくれば calc は最大N種類にばらけます（同じ計算を並べると量産判定に当たる）
- **既に使われている節は二度と割り当てない。** `calc_sections` と実際の見出しを
  突き合わせて判定します。**文字列の一致ではなく、`script_writer` と同じ包含判定**です
- **書き込む前に検証する。** id の重複・形式、`calc` の実在、
  `calc_sections` が**実際にその節に当たること**を、書き込み前に確かめます
- **YAML はテキストとして末尾に足す。** `topics:` はファイル末尾のリストなので、
  読み書きし直して**コメントを全部落とす**ことを避けています
"""
from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.claude_cli import ask  # noqa: E402

TOPICS_YAML = ROOT / "config" / "topics.yaml"
CALC_DIR = ROOT / "src" / "calc"
ID_RE = re.compile(r"^s-[a-z][a-z0-9]*(-[a-z0-9]+)*$")


class Forged(BaseModel):
    id: str = Field(description="s- で始まる小文字とハイフンだけの識別子")
    title_seed: str = Field(description="題の種。10〜44文字")
    angle: str = Field(description="この1本で何を出すかの指示。3〜6行")


class ForgedSet(BaseModel):
    topics: list[Forged]


# ---------------------------------------------------------------- 見出しを読む

def calc_modules() -> list[str]:
    return sorted(p.stem for p in CALC_DIR.glob("*.py") if not p.stem.startswith("_"))


def sections(module: str) -> dict[str, str]:
    """`=== 見出し ===` ごとに、見出し → 本文（見出し込み）を返す。"""
    proc = subprocess.run(
        [sys.executable, "-m", f"src.calc.{module}"],
        capture_output=True, text=True, cwd=ROOT, timeout=300,
    )
    if proc.returncode != 0:
        raise SystemExit(f"src.calc.{module} が落ちました:\n{proc.stderr[-800:]}")
    out: dict[str, str] = {}
    head, body = None, []
    for line in proc.stdout.splitlines():
        if line.startswith("==="):
            if head:
                out[head] = "\n".join(body)
            head, body = line.strip(), [line]
        elif head:
            body.append(line)
    if head:
        out[head] = "\n".join(body)
    return out


def survey() -> tuple[dict[str, dict[str, str]], dict[str, list[str]], set[str]]:
    """(モジュール→節, モジュール→未使用の見出し, 既存のテーマID) を返す。"""
    topics = config.load_topics()["topics"]
    known_ids = {t["id"] for t in topics}
    all_sections = {m: sections(m) for m in calc_modules()}

    claimed: dict[str, set[str]] = {m: set() for m in all_sections}
    for t in topics:
        calc = t.get("calc")
        wanted = t.get("calc_sections") or []
        if not calc or calc not in all_sections or not wanted:
            continue
        # **`script_writer` と同じ包含判定**にすること（前方一致や完全一致にしない）
        for head in all_sections[calc]:
            if any(w in head for w in wanted):
                claimed[calc].add(head)

    free = {m: [h for h in all_sections[m] if h not in claimed[m]] for m in all_sections}
    return all_sections, free, known_ids


def assign(free: dict[str, list[str]], count: int) -> list[tuple[str, str]]:
    """calc を1つずつ回りながら (モジュール, 見出し) を count 件とる。

    **回すのが本体です。** まとめ取りすると同じ calc が並び、量産判定に当たります。
    """
    order = sorted(free, key=lambda m: (-len(free[m]), m))
    pool = {m: list(free[m]) for m in order}
    picked: list[tuple[str, str]] = []
    while len(picked) < count and any(pool.values()):
        for m in order:
            if not pool[m]:
                continue
            picked.append((m, pool[m].pop(0)))
            if len(picked) == count:
                break
    return picked


# ---------------------------------------------------------------- 書かせる

PROMPT_HEAD = """\
YouTube ショート（縦・30秒前後）の企画を {n} 件つくります。

**この企画の作りかた（守ること）**

- 制度の解説はしません。**すでに計算済みの表から、数字を1つ発表します**
- 数字を新しく考えないこと。**下に貼った表に無い数字は、1つも書かないこと**
- 1本で言うことは1つだけ。前提（年収・税率・勤続年数など）は必ず添える
- 「必ずこうなる」と言わないこと。**その前提のときの数字**だと言い切る
- 特定のウェブサイト・リポジトリ・出典名を出さないこと

**1件ぶんに書くもの**

    id          `s-` で始まり、小文字とハイフンだけ。既存と重ならないこと
    title_seed  題の種。**10〜44文字。** 数字を1つ入れる。煽らない
    angle       この1本で何を出すかの指示。3〜6行の日本語。
                「**ショート。1つのことだけ言う。**」で始め、
                どの数字を主役にするか、前提として何を画面に出すか、
                1枚目に何を置くか（22文字以内）、最後の問いかけを書く

**既に出した題**（言い換えでも重ねないこと）:
{seen}

**割り当て**（この順に、1件ずつ書くこと。表の外の数字を使わないこと）
"""


def build_prompt(picked: list[tuple[str, str]], all_sections, topics) -> str:
    seen = "\n".join(f"  - {t['title_seed']}" for t in topics)
    parts = [PROMPT_HEAD.format(n=len(picked), seen=seen)]
    for i, (mod, head) in enumerate(picked, 1):
        body = all_sections[mod][head]
        parts.append(
            f"\n--- {i} 件目 / calc={mod} / 節={head}\n"
            f"この節の表（**ここに無い数字は使わない**）:\n```\n{body[:2400]}\n```\n"
        )
    return "\n".join(parts)


# ---------------------------------------------------------------- 検証して書く

def validate(forged: ForgedSet, picked, all_sections, known_ids) -> list[dict]:
    if len(forged.topics) != len(picked):
        raise SystemExit(f"{len(picked)}件 頼んで {len(forged.topics)}件 返りました")

    rows, used = [], set(known_ids)
    for item, (mod, head) in zip(forged.topics, picked):
        tid = item.id.strip()
        if not ID_RE.match(tid):
            raise SystemExit(f"id の形が不正: {tid!r}")
        if tid in used:
            raise SystemExit(f"id が重複: {tid!r}")
        used.add(tid)

        title = item.title_seed.strip()
        if not 8 <= len(title) <= 48:
            raise SystemExit(f"title_seed の長さが範囲外（{len(title)}文字）: {title!r}")

        # `calc_sections` は見出しそのものではなく、**見出しに含まれる語**で持つ。
        # `===` と装飾を落として、`script_writer` の包含判定に必ず当たる形にする。
        key = head.strip("= ").strip()
        if not any(key in h for h in all_sections[mod]):
            raise SystemExit(f"節の指定が実際の見出しに当たりません: {key!r}")

        angle = item.angle.strip()
        if len(angle) < 40:
            raise SystemExit(f"angle が短すぎます（{len(angle)}文字）: {tid}")

        rows.append({"id": tid, "title_seed": title, "angle": angle,
                     "calc": mod, "calc_sections": [key]})
    return rows


def to_yaml(rows: list[dict]) -> str:
    out = []
    for r in rows:
        out.append(f"\n  - id: {r['id']}")
        out.append(f"    title_seed: {yaml_scalar(r['title_seed'])}")
        out.append("    angle: >")
        for line in r["angle"].splitlines():
            out.append(f"      {line.strip()}" if line.strip() else "")
        out.append(f"    calc: {r['calc']}")
        out.append("    calc_sections:")
        for s in r["calc_sections"]:
            out.append(f"      - {yaml_scalar(s)}")
        out.append("    score: 1.0")
    return "\n".join(out) + "\n"


def yaml_scalar(text: str) -> str:
    """**必ず引用符でくくる。** 題には `:` も `#` も入りうる。"""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=0, help="つくる件数")
    ap.add_argument("--list", action="store_true", help="未使用の見出しを数えるだけ")
    ap.add_argument("--dry-run", action="store_true", help="出すだけで書かない")
    ap.add_argument("--model", default="opus")
    args = ap.parse_args()

    all_sections, free, known_ids = survey()
    total = sum(len(v) for v in all_sections.values())
    spare = sum(len(v) for v in free.values())

    print(f"=== 計算の節 {total} 件 / **未使用 {spare} 件** ===")
    for mod in sorted(all_sections):
        print(f"  {mod:10} 全{len(all_sections[mod]):2}  未使用{len(free[mod]):2}")
        for h in free[mod]:
            print(f"       {h}")

    if args.list or not args.count:
        if not spare:
            print("\n**未使用が0件です。** ここが本当の在庫切れなので、"
                  "`src/calc/` に新しい表を足すこと（この道具では増えません）。")
        return 0

    picked = assign(free, args.count)
    if not picked:
        print("\n割り当てられる節がありません。")
        return 1
    if len(picked) < args.count:
        print(f"\n**{args.count}件 頼まれましたが、未使用が {len(picked)}件 しかありません。**")

    print(f"\n=== 割り当て {len(picked)}件（calc は {len({m for m, _ in picked})}種類）===")
    for mod, head in picked:
        print(f"  {mod:10} {head}")

    topics = config.load_topics()["topics"]
    prompt = build_prompt(picked, all_sections, topics)
    print("\n[forge] 書かせています…")
    forged, _ = ask(ForgedSet, prompt, model=args.model)
    rows = validate(forged, picked, all_sections, known_ids)

    block = to_yaml(rows)
    print("\n=== できたもの ===")
    print(block)

    if args.dry_run:
        print("[forge] --dry-run なので書きません")
        return 0

    with TOPICS_YAML.open("a", encoding="utf-8") as fh:
        fh.write(block)
    print(f"[forge] {len(rows)}件を {TOPICS_YAML} に足しました")

    # **足した直後に読み直す。** 壊れた YAML を次の回に持ち越さないため。
    after = config.load_topics()["topics"]
    print(f"[forge] 読み直し OK — テーマ全 {len(after)}件")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
