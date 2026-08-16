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

    ## 並べる順（2026-08-16 に入れ替えた。**前は「余りの多い順」でした**）

    ここは長らく `-len(free[m])` ＝ **未使用の節が多い calc から**でした。
    **それは実績と何の関係もありません。** むしろ逆に効きます ——
    節をよく使っている calc ほど余りが減るので、**当たっている族ほど後ろに回ります。**

    実測（同日 09:5x）。上位3族は engaged 45.6 / 45.5 / 38.7% で未使用は 0〜1件、
    いっぽう未測定の労基法系（`yukyu` 4件・`jikangai` 2件）が余りを持っていました。
    その状態で3回まわすと、**3件とも `yukyu`・`jikangai` に行き、
    実績2位の `shitsugyo` はこの回で足した節を1つも取れませんでした。**

    **これは M15 を空回りさせます。** M15 は「作る題材の順番を実績で決める」手ですが、
    順番を付ける相手（＝在庫）が全部未測定の族なら、**順番は何も選べません。**
    前の回の申し送り1件目が、まさにここを指しています ——
    「`status.py` の族べつの実績を `topic_forge` 側にも通すこと。いま名指しはするが、
    **節を書く先を機械が選んではいない**」。

    だから `pick` と**同じ物差し**（`src/family_perf.scorer`）で並べます。
    余りの数は順番から外し、**在庫が有るかどうか**だけに使います
    （`pool` が空の calc は回り番から自然に落ちます）。

    **未知の calc は全体平均**が返るので（`family_perf`）、**探索は殺しません。**
    実績が取れない回は、前と同じ「余りの多い順」に落ちます。
    """
    try:
        from src import family_perf
        score = family_perf.scorer()
        order = sorted(free, key=lambda m: (-score(m), m))
    except Exception as exc:      # 実績が読めない回でも、在庫づくりは止めない
        print(f"[forge] 族べつの実績が読めないので余りの多い順に落とします: {exc}")
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

_NUM = re.compile(r"(\d[\d,]*)\s*万\s*(\d[\d,]*)?|(\d[\d,]*)")


MONEY_FLOOR = 1000   # 金額の表を持つ calc で捨てる下限（年数・回数を当てにしない）
SMALL_FLOOR = 10     # 金額を1つも持たない calc（日数・時間の表）で使う下限


def numbers(text: str, floor: int = MONEY_FLOOR) -> set[int]:
    """文中の整数を集める。**「80万円」も「800,000円」も同じ 800000 にする。**

    表は `800,000円` と印字し、`angle` は `80万円` と書きます。
    **書き方が違うだけで同じ数**なので、揃えないと突き合わせになりません。

    `floor` より小さい数は捨てます。既定の1000は「年数や桁の小さい語は
    当てにしない」ためですが、**その calc が金額を扱っている場合にだけ正しい**
    仮定です（下の `section_floor` を見ること）。
    """
    out: set[int] = set()
    for man, rest, plain in _NUM.findall(text):
        if man:
            value = int(man.replace(",", "")) * 10_000
            if rest:
                value += int(rest.replace(",", ""))
            out.add(value)
            out.add(int(man.replace(",", "")))   # 「1000万」の 1000 単体も拾う
        elif plain:
            out.add(int(plain.replace(",", "")))
    return {n for n in out if n >= floor}


def section_floor(sections: dict[str, str]) -> int:
    """その calc の表に合わせて、捨てる下限を決める。

    **2026-08-16 に、実際に踏んで足しました。** ここは長らく 1000 固定で、
    理由は「年数や桁の小さい語を当てにしない」でした。**その仮定は、
    表に載っているのが金額のときだけ成り立ちます。**

    同日に足した `yukyu`（有給の日数）と `jikangai`（残業時間の上限）は、
    **表の数字が全部3桁以下**です。1000で切ると `numbers()` が空集合を返し、
    `best_section` の一致数が全節で0になって、**`realign` が
    「表の外の数字を使っています」と誤って止めます。**
    実際に2回連続で止まりました（`s-jikangai-6month-480h-cap` /
    `s-jikangai-6month-114h-gap`。どちらの数字も、表にちゃんと載っています）。

    **これは「新しい題材を足すと止まる」形の欠陥です。** 金額の calc 16本では
    一度も出ないので、在庫の幅を広げるまで誰も踏みません。

    直し方は、**下限を表から決めること**。金額らしい数（1000以上）が1つでも
    あれば、これまでどおり1000で切ります（**既存16本は挙動が変わりません**）。
    1つも無ければ、その calc は金額の表を持っていないので10まで下げます。
    """
    for body in sections.values():
        if numbers(body, MONEY_FLOOR):
            return MONEY_FLOOR
    return SMALL_FLOOR


def best_section(text: str, sections: dict[str, str]) -> list[tuple[int, str]]:
    """`text` の数字が、どの節の表にいちばん多く載っているか。多い順に返す。

    ## 金額の主張をしていない題は、小さい数で突き合わせる（2026-08-16 に実測して直した）

    `section_floor` は **calc ごと**に下限を決めます。`nenkin` は金額の表を
    持っているので、**どの節を見ていても下限は1000**です。ところが
    `nenkin` の節の多くは**年齢と月数の表**で、主役の数字は
    `81歳10か月` `28か月` のように**全部3桁以下**です。

    すると、書き手が指示どおり**表に載っている数字だけ**で題を書いても、
    `numbers(text, 1000)` が空集合になり、一致数が全節で0になって、
    `realign` が **「表の外の数字を使っています」と落とします。**
    書き手は表の外へ出ていないのに、そう言われます。**門の文言のほうが嘘です。**

    実測（2026-08-16、この節を足した回）——
    `=== 年金額べつ / …===` から `--count 1` を **2回**頼み、
    **2回とも同じ理由で落ちました**（`…-tedori-bunkiten` と `…-hasso-zure`）。
    `kyugyo` が2回とも同じ理由で落ちたのと同じ形で、**確率のぶれではありません。
    この節が残っているかぎり、そこからは今後ずっと1件も通りません。**

    直しは、**題の側に下限以上の数字が1つも無いときだけ** `SMALL_FLOOR` へ落とすこと。

    - **金額の題（大多数）は1文字も挙動が変わりません。** `numbers(text, 1000)` が
      空でないので、そのまま従来の道を通ります
    - 落ちるのは、これまで**無条件に捨てられていた題だけ**です。悪くなりようがない
    - **門が空になるわけではありません。** 実測で
      `分岐点は92歳7か月まで動く`（表に無い年齢）は、下限10でも**一致0のまま落ちます**

    **`section_floor` を節ごとにしても、これは直りません。** この節は金額の列も
    持っているので、節ごとに測っても下限は1000のままです。**効くのは題の側です。**
    """
    floor = section_floor(sections)
    if floor > SMALL_FLOOR and not numbers(text, floor):
        floor = SMALL_FLOOR
    want = numbers(text, floor)
    scored = [(len(want & numbers(body, floor)), head)
              for head, body in sections.items()]
    return sorted(scored, key=lambda x: -x[0])


def realign(forged: ForgedSet, picked, all_sections,
            dropped: list[str]) -> list[tuple[str, str] | None]:
    """**書かせた順に節を貼らない。**中身の数字が載っている節へ貼り直す。

    2026-08-16 に実際に踏んだ穴です。`zoyo` の4件を頼んだところ、
    書き手は**1つめの節から2件**書き、残りが1つずつ後ろへずれました。
    ところが `zip` は順番だけで貼るので、
    **「1年から2年で80万円浮く」に「誰から誰への贈与か」の表**が付きました。
    `calc_sections` は**画面に出す表そのものを選ぶ鍵**なので、
    ずれたまま作ると**語っている数字と、画面の表が別物になります。**
    8/15 の「題と中身の取り違え」（`docs/MEANS.md` M14）と同じ壊れ方で、
    すり抜ければ**誤情報のまま公開**されます。

    貼り直しても**節がぶつかったら、ぶつかった側だけ落とします**。同じ節から2本作ると
    在庫の数え方が崩れ、「同じ絵を続けない」にも当たるためです。

    ## **落とすのは1件ずつ。回ごと殺さないこと**（2026-08-16 10:5x に実測して直した）

    ここは長らく、**1件でも当たらなければ `SystemExit` で回ごと落として**いました。
    その回の実測 ——

        --count 4 → nenkin ✓ / jikangai ✓（貼り直しも通った）/ kyugyo ✗ / yukyu ?
        → **通った2件ごと捨てて exit 1。** 同じことが2回起きて約7分。

    そして `kyugyo` の失敗は**確率のぶれではありませんでした**（2回とも同じ節・
    同じ理由）。つまり**この節が残っているかぎり、`--count` を3以上にすると
    今後もずっと回ごと死にます。** 件数を減らして呼び直す道しかなく、
    §5 が言う「同じ `--count` で何回か回す」も効きません。

    落とすほうが安全側でもあります。**落ちた1件は動画になりません**。
    回ごと殺しても同じで、違うのは**通った件まで消えるかどうか**だけです。
    """
    fixed: list[tuple[str, str] | None] = []
    for item, (mod, head) in zip(forged.topics, picked):
        text = f"{item.title_seed} {item.angle}"
        ranked = best_section(text, all_sections[mod])
        top, best = ranked[0][0], ranked[0][1]
        if top == 0:
            dropped.append(
                f"{item.id}: 題と狙いの数字が、この calc のどの節の表にも載っていません"
                f"（表の外の数字を使っています）")
            fixed.append(None)
            continue
        # **同点では動かさない**（2026-08-16 に足した）。ここは長らく
        # 「一致数が最大の節」を無条件に採っていましたが、**同点のときに
        # 勝つのは dict の順で、根拠がありません。** 節をまたいで同じ数字が
        # 出るのはむしろ普通で（制度の定数・同じ日額）、実際に
        # `s-yukyu-shukikan-shitei-5-5nen` が同点1で隣の節へ飛び、
        # そのあと「同じ節に2件」で回ごと落ちました。
        # **貼り直すのは、割り当て先より厳密に強い証拠があるときだけです。**
        assigned = next((n for n, h in ranked if h == head), 0)
        if top > assigned:
            print(f"  [貼り直し] {item.id}\n"
                  f"      書かせた順の節: {head}（一致 {assigned} 個）\n"
                  f"      数字が載っている節: {best}（一致 {top} 個）")
            fixed.append((mod, best))
        else:
            fixed.append((mod, head))

    # 同じ節に2件以上が当たったら、**先に来たほうを残して後を落とす。**
    # 回ごと殺していたのをやめた（上）。順番は `picked` の順で決まるので、
    # 同じ入力なら同じ結果になります。
    seen: set[tuple[str, str]] = set()
    for i, slot in enumerate(fixed):
        if slot is None:
            continue
        if slot in seen:
            dropped.append(
                f"{forged.topics[i].id}: 節 `{slot[1].strip('= ').strip()}` に"
                f"すでに1件が当たっています（書き手が同じ表から複数書いた）")
            fixed[i] = None
            continue
        seen.add(slot)
    return fixed


def validate(forged: ForgedSet, picked, all_sections,
             known_ids) -> tuple[list[dict], list[str]]:
    """通った件だけを返す。**落ちた件は理由と一緒に、第2の返りで報せる。**

    件数の食い違いだけは、いまも回ごと落とします —— **どの節がどれに当たるかが
    決まらない**ので、1件ずつ落とす判断そのものができません。
    """
    if len(forged.topics) != len(picked):
        raise SystemExit(f"{len(picked)}件 頼んで {len(forged.topics)}件 返りました")

    dropped: list[str] = []
    slots = realign(forged, picked, all_sections, dropped)
    rows, used = [], set(known_ids)
    for item, slot in zip(forged.topics, slots):
        if slot is None:
            continue
        mod, head = slot
        tid = item.id.strip()
        if not ID_RE.match(tid):
            dropped.append(f"id の形が不正: {tid!r}")
            continue
        if tid in used:
            dropped.append(f"id が重複: {tid!r}")
            continue

        title = item.title_seed.strip()
        if not 8 <= len(title) <= 48:
            dropped.append(f"{tid}: title_seed の長さが範囲外（{len(title)}文字）")
            continue

        # `calc_sections` は見出しそのものではなく、**見出しに含まれる語**で持つ。
        # `===` と装飾を落として、`script_writer` の包含判定に必ず当たる形にする。
        key = head.strip("= ").strip()
        if not any(key in h for h in all_sections[mod]):
            dropped.append(f"{tid}: 節の指定が実際の見出しに当たりません: {key!r}")
            continue

        angle = item.angle.strip()
        if len(angle) < 40:
            dropped.append(f"{tid}: angle が短すぎます（{len(angle)}文字）")
            continue

        used.add(tid)
        rows.append({"id": tid, "title_seed": title, "angle": angle,
                     "calc": mod, "calc_sections": [key]})
    return rows, dropped


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
    rows, dropped = validate(forged, picked, all_sections, known_ids)

    # **黙って減らさないこと**（`docs/trigger_main.md`「no silent caps」）。
    # 落ちた件を出さないと、`--count 4` で2件しか増えなかったときに
    # 「そういうものだ」と読めてしまいます。
    if dropped:
        print(f"\n=== 落ちたもの {len(dropped)}件（**残りは通っています**）===")
        for why in dropped:
            print(f"  - {why}")

    if not rows:
        print("\n**1件も通りませんでした。**")
        return 1

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
