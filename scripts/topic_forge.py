#!/usr/bin/env python3
"""**テーマ在庫を、手ではなく機械で作る。**

    python scripts/topic_forge.py --list            # 未使用の見出しを数える（無料・数秒）
    python scripts/topic_forge.py --count 6         # 6件つくって config/topics.yaml に足す
    python scripts/topic_forge.py --count 6 --long  # **長尺**の企画を作る（既定はショート）
    python scripts/topic_forge.py --count 6 --dry-run   # 出すだけで書かない

**`--long` を付け忘れないこと**（2026-08-25 に足しました）。この道具は
長らく**ショートの企画しか書けませんでした**。ところが `scripts/eta.py` の逆算では
**門2b（ショート90日1,000万回）は API の上限まで出しても 0.53倍で届かず、
残る道は門2a（長尺4,000時間）だけ**です。そして**ショートの視聴時間は
そこに1分も入りません**（受け取り帳 `88e9fb44`・YouTube 公式ヘルプの原文）。
**唯一の門を開ける形を、在庫の側が1件も作れない**作りでした
（実測: 予約の待ち行列は 長尺11本 / ショート310本 ＝ **3.4%**）。

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
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import config  # noqa: E402
from src.claude_cli import ask  # noqa: E402

TOPICS_YAML = ROOT / "config" / "topics.yaml"
CALC_DIR = ROOT / "src" / "calc"
ID_RE = re.compile(r"^s-[a-z][a-z0-9]*(-[a-z0-9]+)*$")
#: **長尺の id には `s-` を付けません。** `src/pipeline.py` が `s-` で始まる id を
#: 「ショート。`topics.yaml` に置かず、その場で作る」と読むためです
#: （`scripts/eta.py:316` も同じ規則で形を数えています）。
LONG_ID_RE = re.compile(r"^(?!s-)[a-z][a-z0-9]*(-[a-z0-9]+)*$")


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


def sections_for(topic: dict, secs: dict[str, str]) -> str:
    """テーマの `calc_sections` に当たる節の本文をつなげて返す。

    **`calc_sections` は見出しそのものではありません。見出しに含まれる語です。**
    引く側は `any(語 in 見出し for 語 in calc_sections)` の**部分一致**で、
    正本は `src/script_writer.py`（生成のときに実際にこれで絞っています）。

    **2026-08-19 に、これを知らずに完全一致で引いて12分払いました。**
    予約246本を今の表と突き合わせる測定が、**246件とも「節が無い」**になり、
    測り直しになっています。手順にも `sections()` の docstring にも
    部分一致だと書いた行が1つも無く、**写す側が毎回間違えます。**
    だから、引き方のほうをここに1つ置きました。
    """
    words = topic.get("calc_sections") or []
    if not words:
        return "\n".join(secs.values())
    return "\n".join(body for head, body in secs.items()
                     if any(w in head for w in words))


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


#: 節を掘るときに実際に使われた「形」を、`data/runs.jsonl` の ship の1行から数える。
#: **散文を数えています**（構造の欄ではありません）。だから**当たった行を必ず出します** ——
#: 数だけ出すと、次の回が検算できないので。
DIG_METHODS: tuple[tuple[str, str, str], ...] = (
    ("族をまたいだ比較",
     r"族をまた",
     "別の族の `ASSUMPTIONS` が自分で名指ししている穴を、金額表にする"),
    ("掃引の候補から",
     r"掃引(の候補)?(から|を使っ)(?!.{0,6}(いない|ていない|ません))",
     "`python -m src.section_sweep --calc <族>` が出す形の候補を採る"),
)


def dig_method_lines(path: Path | None = None, limit: int = 400) -> list[str]:
    """**「節をどう掘るか」の道を、実績つきで出す。**

    ## なぜ要るか（2026-08-28 に測って足した）

    ここは長らく「`section_sweep --calc <族>` が形の候補を出します」の**1行だけ**で、
    **在庫切れの回が読む助言はそれしかありませんでした。**

    ところが実測では、その候補の当たり率は **0/23**（`docs/JOURNAL.md`
    2026-08-28 01:4x が「候補は 2,476件 積んであって、当たり率は実測 0/23」）で、
    **直近の在庫掘りは5回とも別の道を採っています**
    （08/27 kouki・08/28 iryohi／nenkin／shougai／keihi は
    どれも「族をまたいだ比較」で、ship の1行に「掃引の候補は使っていない」と
    書いてあります）。

    **助言の文は、閉じても自分では黙りません**（`docs/trigger_main.md` §2.7）。
    ここが1つの道しか名指ししていないせいで、**在庫切れの回はまず
    当たり率 0/23 の一覧を開くところから始めます。**

    ## なぜ「構造がある側」ではなく散文を数えているか

    `run_marker.py --ship` に道の欄はありません。足すこともできますが、
    **足した日から先しか数えられない**ので、いま効いている差
    （5回 対 0回）が見えません。だから既にある `what` の散文を数えます。

    **散文なので外れます。** だから数だけでなく**当たった行の頭**を出し、
    次の回がその場で検算できるようにしてあります。

    **覆る条件**: `run_marker.py --ship` に道の欄が入ったら、そちらで数えること
    （散文は言い回しが変わると黙って0になります）。
    """
    p = path or (ROOT / "data" / "runs.jsonl")
    if not p.exists():
        return ["  （`data/runs.jsonl` が無いので、道の実績は出せません）"]
    ships: list[str] = []
    claims: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except Exception:
            continue
        what = row.get("what") or ""
        if not what:
            continue
        if row.get("kind") == "ship":
            ships.append(what)
        elif row.get("kind") == "claim":
            claims.append(what)
    ships, claims = ships[-limit:], claims[-limit:]

    out = ["  **節の掘り方には道が2つあり、実績が違います**"
           f"（`data/runs.jsonl` の直近 {len(ships)}件 の ship の散文から）:"]
    for name, pattern, how in DIG_METHODS:
        hit = [w for w in ships if re.search(pattern, w)]
        want = [w for w in claims if re.search(pattern, w)]
        tail = (f"（**取りかかると宣言した回は {len(want)}回**）"
                if len(want) > len(hit) else "")
        out.append(f"    {name:<12} **出した {len(hit)}回**{tail} …… {how}")
        for w in hit[-2:]:
            out.append(f"        └ {w[:70]}")
    out.append("    → **数えているのは `ship` だけです。** `claim` は"
               "「取りかかる」の宣言で、**そのまま出せたとは限りません** ——"
               "実際、掃引を claim した回が、掃引を使わずに ship しています。")
    out.append("    → **`section_sweep` はその族の中だけを振るので、"
               "族をまたいだ形はそもそも候補に出てきません。**"
               "掃引の候補の当たり率は実測 0/23（`docs/JOURNAL.md` 2026-08-28 01:4x）。")
    out.append("    → **どちらを採ってもよい。ただし採った道を "
               "`--ship` の1行に書くこと** —— ここの数がそれで動きます。")
    return out


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

# ---- 長尺（2026-08-25 に足した。**この道具はショートしか作れませんでした**）----
#
# ## なぜ要るか
#
# `scripts/eta.py` の逆算はこう言っています ——
# **門2b（ショート90日1,000万回）は、API の上限 1日92本を全部出しても
# 111,111回/日 に対し 58,696回/日 ＝ 0.53倍。届きません。**
# 残る道は **門2a（長尺4,000時間）だけ**で、しかも受け取り帳 `88e9fb44`
# （YouTube 公式ヘルプの原文）のとおり、**ショートの視聴時間はそこに1分も入りません。**
#
# ところが在庫を作る道具は、**ショートの企画しか書けませんでした。**
# 上の `PROMPT_HEAD` は「YouTube ショート（縦・30秒前後）」で始まり、
# `angle` に「**ショート。1つのことだけ言う。**」と書かせ、id を `s-` に強制します。
# **唯一の門を開ける形を、在庫の側が1件も作れない**という作りです。
# 実測: 予約の待ち行列は **長尺11本 / ショート310本（3.4%）**。
#
# ## 何を変えたか
#
# **節の選び方も、貼り直しも、検査も、全部そのまま**です。変わるのは
# 「書かせる文」と「id の形」の2つだけ。同じ節から長尺とショートの
# 両方を作れるわけではありません（節は1件で使い切ります）。
LONG_PROMPT_HEAD = """\
YouTube の長尺（横・**{target:g}分前後**）の企画を {n} 件つくります。

**この企画の作りかた（守ること）**

- 制度の解説はしません。**すでに計算済みの表から、自分で出した数字を発表します**
- 数字を新しく考えないこと。**下に貼った表に無い数字は、1つも書かないこと**
- **{floor:g}分を下回ると投稿前の検査が止めます。** 1つの表を最後まで読み切る分量を書くこと
- **前提と計算式は、画面にも説明欄にも全部出します。** 視聴者が追試できることが主題です
- 「必ずこうなる」と言わないこと。**その前提のときの数字**だと言い切る
- 特定のウェブサイト・リポジトリ・出典名を出さないこと

**ショートとの違い（ここを外さないこと）**

- ショートは「1つのことだけ」ですが、**長尺は表を全部読みます。**
  主役の1行を出したあと、**同じ表の他の行がなぜそうなるか**まで進みます
- **棒グラフになる行を最低3つ**選ぶこと（`kind=chart`）。棒の長さは計算結果そのものです
- 途中で**前提を1つ動かして、数字がどう変わるか**を見せる段を1つ入れること

**1件ぶんに書くもの**

    id          **`s-` で始めないこと**（`s-` はショートの印です）。
                `<計算モジュール名>-<内容>` の形。小文字とハイフンだけ。既存と重ならないこと
    title_seed  題の種。**10〜44文字。** 数字を1つ入れる。煽らない
    angle       この1本で何を出すかの指示。**6〜10行**の日本語。
                「**長尺。表を最後まで読み切る。**」で始め、
                主役の数字／前提として画面に出すもの／棒にする3行以上／
                途中で動かす前提／最後の問いかけを書く

**既に出した題**（言い換えでも重ねないこと）:
{seen}

**割り当て**（この順に、1件ずつ書くこと。表の外の数字を使わないこと）
"""


def build_prompt(picked: list[tuple[str, str]], all_sections, topics,
                 long_form: bool = False) -> str:
    """割り当てた節ごとに、表と **「主役にしてはいけない金額」** を貼る。

    後者は 2026-08-18 に足しました。**同じ calc で既に題に出した金額**を
    もう一度主役にすると、`upload_only.py` の門（`dupes.blocking` の
    `same-yen`）が**必ず**止めます。止まった本は捨てになり、
    **その節は使用済みのまま二度と戻りません。**

    実測（この回。未投稿125件を実際に門へ通した）: **4件が該当**。
    4件とも節そのものは新しく、**題の主役に選んだ数だけが既出**でした ——

        s-jidou-hitori-atari-6480000-todokanai  6,480,000円
          ← `児童手当 第3子は648万円 第1子の2.77倍`（09/14 予約）と同じ数

    **表には他にも数字があります。** 塞ぐのは節ではなく、数の選び方です。
    """
    from src import dupes

    seen = "\n".join(f"  - {t['title_seed']}" for t in topics)
    if long_form:
        # **尺は決め打ちにしない**（2026-08-25 に踏んだ。最初の版は「8分30秒以上」と
        # 書きましたが、実物は 2026-08-09 から **4分**です ——
        # 「通っていない門（ミッドロール広告の8分）のための制約だった」と
        # `config/channel.yaml` に理由ごと書いてあります）。
        # **決め打ちは、覆った側の判断を静かに巻き戻します。**
        vid = config.load_channel()["video"]
        parts = [LONG_PROMPT_HEAD.format(
            n=len(picked), seen=seen,
            floor=float(vid["min_minutes"]), target=float(vid["target_minutes"]))]
    else:
        parts = [PROMPT_HEAD.format(n=len(picked), seen=seen)]
    used = dupes.used_amounts({t["id"]: t.get("calc", "") for t in topics})
    for i, (mod, head) in enumerate(picked, 1):
        body = all_sections[mod][head]
        block = (f"\n--- {i} 件目 / calc={mod} / 節={head}\n"
                 f"この節の表（**ここに無い数字は使わない**）:\n```\n{body[:2400]}\n```\n")
        taken = used.get(mod, [])
        if taken:
            shown = "・".join(f"{int(v):,}円" for v in taken[:12])
            block += (f"**この calc で既に題に出した金額**: {shown}\n"
                      f"→ **この数を title_seed の主役に選ばないこと。**"
                      f"投稿の門が必ず止めます（表の別の数字を使う）\n")
        parts.append(block)
    return "\n".join(parts)


# ---------------------------------------------------------------- 検証して書く

# **`万` の後ろは、空けないこと・`千` を捨てないこと**（2026-08-19 に実測して直した）。
# 旧: `(\d[\d,]*)\s*万\s*(\d[\d,]*)?`。`\s*` があるので
# **`2000万 1日で106,470円` の「1日」の 1 を万の下に吸って 20,000,001** を作り、
# **`431万8千円` は「千」を読まずに 4,310,008**（正しくは 4,318,000）にしていました。
# どちらも**実在しない数**なので、`best_section` の突き合わせでは当たらず、
# `validate` では「表の外の数字」に見えます（`43.2万円`→20,000 と同じ形。3件目）。
# 実測: `config/topics.yaml` 413件のうち **8件**の数が変わり、8件とも新しい側が正しい。
_NUM = re.compile(
    r"(\d[\d,]*(?:\.\d+)?)万(?:(\d[\d,]*)千|(\d[\d,]*))?"
    r"|(\d[\d,]*(?:\.\d+)?)")


MONEY_FLOOR = 1000   # 金額の表を持つ calc で捨てる下限（年数・回数を当てにしない）
SMALL_FLOOR = 10     # 金額を1つも持たない calc（日数・時間の表）で使う下限

# **calc をまたいで貼り直すのに要る、一致数の差**（`realign` の該当節）。
# 1個差では動かしません —— 制度の定数（基礎控除43万円など）は calc をまたいで
# 同じ数が出るので、弱い証拠で動かすと**正しく貼られた件のほうがずれます。**
CROSS_MARGIN = 2

# **長尺の `angle` の下限**（文字数）。ショートは 40 字で足りますが、
# 長尺は 8分30秒 を埋める指示が要ります。短いまま通すと、
# **作ってから `src/verify.py` に落とされ、生成1本ぶんが捨てになります。**
LONG_ANGLE_MIN = 200


def _value(digits: str) -> int | float:
    """`"1,655"` → 1655 ／ `"1.636"` → 1.636。**整数になる小数は整数に戻す。**

    戻すのは、`2.0` と `2` を**別の数として数えないため**です
    （`src/_checks._as_keys` が同じ理由で `77.0` と `77` を揃えています）。
    Python では `2.0 == 2` かつ `hash(2.0) == hash(2)` なので集合演算は
    どちらでも通りますが、**印字したときに別物に見える**ので揃えておきます。
    """
    plain = digits.replace(",", "")
    if "." not in plain:
        return int(plain)
    value = float(plain)
    return int(value) if value.is_integer() else value


def numbers(text: str, floor: float = MONEY_FLOOR) -> set[int | float]:
    r"""文中の数を集める。**「80万円」も「800,000円」も同じ 800000 にする。**

    表は `800,000円` と印字し、`angle` は `80万円` と書きます。
    **書き方が違うだけで同じ数**なので、揃えないと突き合わせになりません。

    `floor` より小さい数は捨てます。既定の1000は「年数や桁の小さい語は
    当てにしない」ためですが、**その calc が金額を扱っている場合にだけ正しい**
    仮定です（下の `section_floor` を見ること）。

    ## **小数を拾うこと**（2026-08-18 20:1x に実測して直した）

    ここは長らく整数だけを見ていました。**そのせいで2つ壊れていました。**

    1. **倍率と率だけで成り立つ節は、突き合わせに1つも参加できません。**
       `koyouhoken` の「業種の差は労働者側では同じ0.1ポイント、建設だけ
       事業主で2倍」は、表に `0.1` `0.2` `2.0` しか持っていません。
       整数だけを見ると全部が消えるので、**この節からは4回頼んで4回とも
       落ちました**（門の文言は「表の外の数字を使っています」。**嘘です**）。
    2. **`43.2万円` が 20,000 になっていました。** 旧の正規表現は
       `(\d[\d,]*)\s*万` なので、`43.2万` の中の **`2万` だけ**に当たります。
       正しい 432,000 はどこにも出ず、代わりに実在しない 20,000 が出て、
       **同じ誤りを含む節と偶然に一致していました**（`s-nenkin-kuriage-…` の
       3件が、繰上げの題なのに**繰下げの節**に貼られていたのはこれです）。

    実測（`config/topics.yaml` の352件に当て直した）: 一致0で落ちる題が
    **3件 → 0件**、貼り先が変わったのが15件。**変わった側は繰上げ↔繰下げの
    取り違えなど、こちらが正しい側**でした。
    """
    out: set[int | float] = set()
    for man, sen, rest, plain in _NUM.findall(text):
        if man:
            value = _value(man) * 10_000
            if sen:                                     # 「431万8千円」の 8千
                value += int(sen.replace(",", "")) * 1_000
            elif rest:                                  # 「1121万2500円」の 2500
                value += int(rest.replace(",", ""))
            out.add(int(value) if float(value).is_integer() else value)
            out.add(_value(man))   # 「1000万」の 1000 単体も拾う
        elif plain:
            out.add(_value(plain))
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

    ## **「空か」ではなく「当たったか」で降りること**（2026-08-18 20:1x に直した）

    上の直しは **`numbers(text, floor)` が空のときだけ**降ります。
    **空でなければ降りないので、1個でも余計な数があると効きません。**

    実測（`s-koyouhoken-jigyounushi-1636bai`）—— 題の中身は
    `1.636倍` `0.55パーセント` `0.9パーセント` `1.45パーセント` で、
    **どれも1000にも10にも届きません**。ところが `angle` には
    **「1枚目は…（22文字以内）」という書き方の指示**が入っていて、
    その **22** だけが 10 を超えます。だから「空ではない」と判定され、
    **降りずに一致0で落ちます。** 主張の数字は1つも見ていないのに、です。

    **降りる条件は「一致したか」のほうです。** 下限を 1000 → 10 → 0 と
    順に下げ、**どこかで1つでも当たったらそこで止める。**

    - **当たっている題は、これまでどおり最初の下限で止まります**（大多数）。
      挙動が変わりようがありません
    - 降りるのは、**これまで無条件に落ちていた題だけ**です
    - **下限0は「何でも通る」ではありません。** 表に無い数は、0まで下げても
      当たりません（`分岐点は92歳7か月まで動く` は下限0でも一致0のまま）
    - ただし **1桁の数はどの表にも出やすい**ので、下限0まで降りた題の
      一致は弱い証拠です。**降りたことは呼び出し側に返します**（`match_floor`）
    """
    scored: list[tuple[int, str]] = []
    for rung in rungs(sections):
        want = rung(text)
        scored = sorted([(len(want & rung(body)), head)
                         for head, body in sections.items()], key=lambda x: -x[0])
        if scored and scored[0][0] > 0:
            if backed_ratio(want, sections, rung) >= MATCH_RATIO_FLOOR:
                return scored
            # **一致はした。証拠が薄いだけ** —— 下の段へ降りる（下の `backed_ratio`）
    # **薄い一致は、一致していないのと同じ扱いにします。**
    # ここで `weak` をそのまま返すと `realign` の `top` が 0 になりません。
    return [(0, head) for _, head in scored] if scored else scored


# **題の数字のうち、何割がその calc の表に載っていれば「表から書いた」と見なすか。**
# 3分の1。**実測で決めました**（下の `backed_ratio` の docstring）。
MATCH_RATIO_FLOOR = 1 / 3


def why_dropped(text: str, sections: dict[str, str]) -> str:
    """落とした理由を、**そのとき本当に起きたこと**で書く。

    **文言と中身が食い違うのは、この門が繰り返し踏んでいる形です**
    （`section_floor` と `best_section` の docstring に、同じ事故が3回出てきます。
    どれも「表の外の数字を使っています」と言いながら、書き手は表の外へ出ていなかった）。
    **割合の門を足すと、4回目を自分で作ります** —— 数字は表にあるのに、
    足りないのは**割合**のほうだからです。だから理由を2つに分けます。

        一致0        → 本当に1つも載っていない
        割合が足りない → 載ってはいる。**足りないのは何割か**と、どの数が無いか

    **次に読む側が、どちらを直せばよいかを迷わないこと**が目的です。
    """
    for rung in rungs(sections):
        want = rung(text)
        if not want:
            continue
        union: set = set()
        for body in sections.values():
            union |= rung(body)
        hit = want & union
        if hit:
            miss = sorted(want - union)[:8]
            return (f"数字は載っているが、割合が足りません"
                    f"（{len(hit)}/{len(want)} = {len(hit)/len(want):.2f}"
                    f" < {MATCH_RATIO_FLOOR:.2f}）。"
                    f"表に無い数: {miss}"
                    f" —— **その数を落とすか、表を持っている calc へ移すこと**")
    return ("題と狙いの数字が、この calc のどの節の表にも載っていません"
            "（表の外の数字を使っています）")


def backed_ratio(want: set, sections: dict[str, str], rung) -> float:
    r"""題の数字のうち、**その calc のどこかの表に載っている割合**。

    ## なぜ「一致数」では足りないか（2026-08-25 22:xx に実測して足した）

    `best_section` はこれまで **「一致が1つでもあれば通す」**でした。
    門の文言は「表の外の数字を使っています」ですが、**実際に見ていたのは
    『表の中の数字を1つでも使っているか』**です。**向きが逆です。**
    題の9割がでたらめでも、1つ当たれば通ります。

    実測（`config/topics.yaml` の実物 486件を土台に、**数字だけ全部でたらめに
    置き換えた題 1,458本**を通した）:

        通ってしまった      **378本（25.9%）**
        通った件の一致数    **中央値 1**   ← 偶然ひとつ当たっただけ

    偶然が効くのは、**表が深いほど 2桁の数がほとんど埋まる**からです
    （実測: `nenkin` は 10〜99 のうち **68個（75.6%）**を持っています。
    61本の中央値は 10個）。**在庫を増やすほど、この門は弱くなります** ——
    いま進めている「既にある表に節を足す」は、まさにその向きの作業です。

    ## 見るのは割合のほう

    表から書いた題は、**数字のほとんどが表に載っています**。
    偶然当たっただけの題は、1つしか載っていません。**分布は重なりません**:

        本物 486件      中央 **1.00** ／ 25%点 1.00 ／ 5%点 0.71
        でたらめ 378件  中央 **0.12** ／ 75%点 0.20 ／ 95%点 ほぼ 0.3

        しきい値   本物が残る   でたらめが通る（通った件のうち）
          0.25      100.0%        14.6%
          **1/3**   **99.6%**     **3.2%**   ← ここ
          0.50       99.2%         2.7%

    **1/3 にすると、でたらめの通過は 25.9% → 0.8% になります**（1/30 以下）。
    本物で落ちるのは 486件中 **2件**で、中身を見ると2件とも
    **丸めた散文**です（`s-kojo-4` の「所得900万円」、`s-zoyo-…` の 4,299.5万）——
    表には `9,619,168` のような端数が載っていて、題は `961万円` と丸める。
    `numbers()` は両方を別の数として数えるので、**分母だけが膨らみます。**

    **覆る条件**: 本番の批（`--count N`）で「表の外の数字を使っています」が
    増え、中身が丸めた散文ばかりなら、**しきい値を下げる前に分母を直すこと** ——
    `numbers()` が `961万` から足している素の `961` と、丸めた側の数を
    分母から外すほうが先です。しきい値は最後の手段。

    分母は「題にある数」、分子は「**節をまたいだ和集合**に載っている数」です。
    節ごとに見ないのは、題が2つの節から数字を引くのが普通だからです
    （`nenkin-kurisage` は繰下げ表と手取り表の両方を見ています）。
    """
    if not want:
        return 0.0
    union: set = set()
    for body in sections.values():
        union |= rung(body)
    return len(want & union) / len(want)


def rungs(sections: dict[str, str]) -> list[Callable[[str], set]]:
    """`best_section` が上から順に試す物差し。**必ず厳しいほうから。**

    最後の段が `decimals` で、**下限0（全部の整数）ではありません。**
    そこは 2026-08-18 20:1x に1回書いて、**その場で自分の検査に落とされた**所です:

        tests/test_forge_floor_fallback.py::test_実物の_nenkin_で作り話は落ちたまま
        「分岐点は92歳7か月まで動く」→ 下限0だと **一致1**（表のどこかに 7 か 92 がある）

    **1桁の整数は、どの表にも出ます。** 下限を0にすると門が
    「表に無い数字を使っていないか」を見なくなり、**誤情報がそのまま通ります。**
    通したいのは倍率と率だけで成り立つ節なので、**見るのは小数のほうです** ——
    `0.1` `1.636` `2.0` は表を名指しできますが、`7` は名指しできません。
    """
    out: list[Callable[[str], set]] = []
    for floor in (section_floor(sections), SMALL_FLOOR):
        if not out or floor < _floor_of(out[-1]):
            out.append(_by_floor(floor))
    out.append(decimals)
    return out


def _by_floor(floor: float) -> Callable[[str], set]:
    def rung(text: str) -> set[int | float]:
        return numbers(text, floor)
    rung.floor = floor          # `match_scale` が段を名前で返せるように
    return rung


def _floor_of(rung) -> float:
    return getattr(rung, "floor", 0)


_DECIMAL = re.compile(r"\d[\d,]*\.\d+")


def decimals(text: str) -> set[float]:
    """文中の**小数だけ**を集める（`0.1` `1.636` `2.0`）。整数は1つも拾わない。

    倍率・率・ポイントだけで成り立つ節を突き合わせるための物差しです。
    `2.0` は `numbers()` では整数 2 に丸めますが、**ここでは丸めません** ——
    丸めると「表が小数として印字した」という情報が消え、
    `2倍` と書いた散文の `2` と区別できなくなります。
    """
    return {float(m.replace(",", "")) for m in _DECIMAL.findall(text)}


def match_scale(text: str, sections: dict[str, str]):
    """`best_section` が実際に当たりを出した段。当たらなければ最後の段。

    `swallows` が同じ物差しで節どうしを比べるために要ります。**ここが食い違うと、
    「一致数で勝ったのは総覧だから」の判定が別の目盛りで行われます。**
    """
    ladder = rungs(sections)
    for rung in ladder:
        want = rung(text)
        if any(want & rung(body) for body in sections.values()):
            # **`best_section` と同じ条件で降りること**（2026-08-25 22:xx）。
            # 割合の門をこちらに入れ忘れると、`best_section` が捨てた段を
            # `swallows` が物差しに使い、**同じ題を2つの目盛りで測ります。**
            # このリポジトリが通算7回踏んでいる「片方だけ直す」の形です。
            if backed_ratio(want, sections, rung) >= MATCH_RATIO_FLOOR:
                return rung
    return ladder[-1]


def swallows(sections: dict[str, str], candidate: str, assigned: str,
             rung=None) -> bool:
    """`candidate` が `assigned` の数字を**丸ごと含む**か（＝総覧の節か）。

    ## なぜ要るか（2026-08-18 に実測して足した。**同じ題を6件つくった**）

    `realign` は「一致数が厳密に多い節へ貼り直す」。**その比べ方は、
    全部の行を1つの表に並べた「総覧の節」があると必ず壊れます** ——
    総覧は他の節の数字を全部持っているので、**どの題に対しても一致数が最大**になり、
    **割り当てがどこであっても、そこへ吸い込まれます。**

    実測（`src/calc/keihi.py` を足した回）:

        1節目 === 経費1万円の値打ちは…（所得10段の総覧）===   数字 40個
        2節目 === 経費の値打ちは、所得が上がるほど…ではない === 数字 2個（総覧の部分集合）

        --count 1 を6回 → **6回とも2節目に割り当てられ、6件とも1節目へ貼り直された**
        → `calc_sections` が6件とも1節目を指す
        → `survey()` は2節目を「未使用」のまま数える
        → 次の回もまた2節目を割り当てる …… **同じ題が無限に増えます**

    **6件のうち5件が、言っていることまで同じでした**（700万と900万の逆転）。
    これは「続けて数本見たときに繰り返しに感じられる」判定に**そのまま当たります**。

    ## 判定は「一致数」ではなく「節どうしの包含」で

    貼り直しの根拠は **「割り当て先には無い数字が、候補にはある」**ことです。
    候補が割り当て先の数字を**丸ごと含んでいる**なら、一致数が多いのは
    **候補の表が大きいから**であって、題がそちらを語っている証拠ではありません。

    - 部分的に重なっているだけなら、これまでどおり貼り直します
      （`zoyo` の4件のずれ・`=== A ===`/`=== B ===` の検査は挙動が変わりません）
    - **割り当ての無い件（余り）には掛けません。** 比べる相手が無いので、
      総覧へ落ちるのがむしろ正しい
    """
    if assigned not in sections or candidate not in sections:
        return False
    # **`best_section` が当たりを出した段で比べること**（2026-08-18 20:1x）。
    # 既定の `section_floor` のままだと、小数の段で選ばれた節を
    # **1000 の目盛りで**「総覧かどうか」判定することになります。
    # 倍率と率だけの節は 1000 では両側とも空集合になり、`mine` が空 →
    # 常に False ＝ 総覧の吸い込みを**素通りさせます。**
    if rung is None:
        rung = _by_floor(section_floor(sections))
    mine = rung(sections[assigned])
    theirs = rung(sections[candidate])
    return bool(mine) and mine <= theirs


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

    ## **ずれるのは節だけではありません。calc ごとずれます**（2026-08-25 に踏んだ）

    上の直しは **`all_sections[mod]` の中だけ**を探し直します。
    ところが実測（`--count 5` / kokuho・kaigo・taishoku・tsukin・zangyo）では、
    書き手が **4件しか返さず**、2件目から**まるごと1つずれました**:

        書いた中身        貼られた calc     この直しの前の結果
        kokuho の節       kokuho            ✓
        zangyo の節       kaigo             ✗ 一致1で「当たった」ことになり、通る
        kaigo の節        taishoku          ✗ 同上
        taishoku の節     tsukin            ✗ 同上

    **`top == 0` の門はここを止めません。** 1桁の数や `20` のような
    ありふれた数がどの表にも出るので、**別の calc でも一致1が出ます。**
    そのまま作れば、**語っている制度と、画面に出る表が別の制度**になります
    —— 8/16 に節の中で踏んだ穴と同じ壊れ方が、**1つ上の粒度**で残っていました。

    直しは、**この回で頼んだ calc 全部**に当て直し、割り当て先より
    **`CROSS_MARGIN` 個以上多く**当たる calc があれば、そちらへ移すこと。

    - **正しく貼られている件は動きません。** 自分の calc の節には主役の数字が
      そのまま載るので一致数が大きく、他の calc が2個ぶん追い越すことはまずありません
      （実測: zangyo の題は zangyo で4・kaigo で1・taishoku で2）
    - **同点や1個差では動かしません。** 制度の定数（基礎控除43万円など）は
      calc をまたいで同じ数が出るので、弱い証拠で動かすと逆にずれます
    - 移った先の節が埋まっていれば、**下の重複判定が1件だけ落とします**
      （回ごとは殺しません）
    """
    # 割り当て先の無い件（頼んだ数より多く返ってきたぶん）は、
    # **どの calc から選ぶか**をここで決めます。候補は「この回で頼んだ calc」だけ。
    mods = [m for m, _ in picked if m]

    fixed: list[tuple[str, str] | None] = []
    for item, (mod, head) in zip(forged.topics, picked):
        text = f"{item.title_seed} {item.angle}"
        if mod is None:
            # **余りの件。** 割り当てが無いので、中身がいちばん当たる節を置き先にする。
            # `assigned` は 0 —— 「割り当て先より強い証拠があるときだけ動かす」の
            # 規則はそのままで、比べる相手が無いだけです。
            cand = [(best_section(text, all_sections[m])[0], m) for m in mods]
            (top, best), mod = max(cand, key=lambda c: c[0][0])
            ranked = []
        else:
            ranked = best_section(text, all_sections[mod])
            top, best = ranked[0][0], ranked[0][1]
            # **ずれるのは節だけではありません。calc ごとずれます**
            # （2026-08-25 に踏んだ。下の `CROSS_MARGIN` の節）。
            cross = [(best_section(text, all_sections[m])[0], m)
                     for m in mods if m != mod]
            if cross:
                (ctop, cbest), cmod = max(cross, key=lambda c: c[0][0])
                if ctop >= top + CROSS_MARGIN:
                    print(f"  [calc ごと貼り直し] {item.id}\n"
                          f"      書かせた順の calc: {mod} / {head}（一致 {top} 個）\n"
                          f"      数字が載っている calc: {cmod} / {cbest}"
                          f"（一致 {ctop} 個）")
                    mod, head, best, top = cmod, cbest, cbest, ctop
                    ranked = best_section(text, all_sections[mod])
        used_rung = match_scale(text, all_sections[mod])
        if top == 0:
            dropped.append(f"{item.id}: {why_dropped(text, all_sections[mod])}")
            fixed.append(None)
            continue
        # **同点では動かさない**（2026-08-16 に足した）。ここは長らく
        # 「一致数が最大の節」を無条件に採っていましたが、**同点のときに
        # 勝つのは dict の順で、根拠がありません。** 節をまたいで同じ数字が
        # 出るのはむしろ普通で（制度の定数・同じ日額）、実際に
        # `s-yukyu-shukikan-shitei-5-5nen` が同点1で隣の節へ飛び、
        # そのあと「同じ節に2件」で回ごと落ちました。
        # **貼り直すのは、割り当て先より厳密に強い証拠があるときだけです。**
        assigned = next((n for n, h in ranked if h == head), 0) if ranked else 0
        if top > assigned and swallows(all_sections[mod], best, head, used_rung):
            # **総覧の節は、いつでも一致数で勝ちます。** 下の節を見ること
            print(f"  [動かしません] {item.id}\n"
                  f"      割り当て: {head}（一致 {assigned} 個）\n"
                  f"      一致は多いが、{best} は割り当て先の数字を丸ごと含む総覧です")
            fixed.append((mod, head))
            continue
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
             known_ids, long_form: bool = False) -> tuple[list[dict], list[str]]:
    """通った件だけを返す。**落ちた件は理由と一緒に、第2の返りで報せる。**

    ## **件数の食い違いでも、回ごと落とさない**（2026-08-17 11:5x に実測して直した）

    ここは長らく、こう書いて `SystemExit` していました ——
    「**どの節がどれに当たるかが決まらない**ので、1件ずつ落とす判断そのものが
    できません」。**決まります。`realign()` がやっていることそのものです。**

    §5 は「`--count` を calc の種類数まで抑えれば衝突しない」と言っていましたが、
    11:5x の回は **`--count 1`**（未使用の節を持つ calc は1種類）で踏んでいます:

        === 割り当て 1件（calc は 1種類）===
          saishushoku === 早く決めるほど、雇用保険からの受取は必ず減る ===
        [forge] 書かせています…
        **1件 頼んで 5件 返りました**      ← 書かせた5件を全部捨てて exit

    **件数は原因ではありません。** 節の見出しが並んでいる族だと、書き手が
    **割り当てられた1節ではなく族ごと書く**ことがある。`--count` を1まで
    下げても起きるので、**下げる方向に直しはありませんでした。**

    余った件には割り当て先が無いだけなので、**中身で置き先を決めさせ**、
    節がぶつかったぶんは既にある「先に来たほうを残す」で落ちます。
    これは 8/16 10:5x に「1件ずつ落とす。回ごと殺さない」へ直したのと**同じ形**で、
    **その回が塞ぎ残していた最後の1本**です。

    足りない側（頼んだより少ない）は、余った割り当てを使わないだけです。
    """
    dropped: list[str] = []
    picked = list(picked)
    if len(forged.topics) != len(picked):
        dropped.append(
            f"（{len(picked)}件 頼んで {len(forged.topics)}件 返りました。"
            "**回ごとは落としません** —— 余りは中身で置き先を決め、"
            "節がぶつかったものだけ落とします）")
        if len(forged.topics) > len(picked):
            picked += [(None, None)] * (len(forged.topics) - len(picked))
        else:
            picked = picked[:len(forged.topics)]

    slots = realign(forged, picked, all_sections, dropped)
    rows, used = [], set(known_ids)
    for item, slot in zip(forged.topics, slots):
        if slot is None:
            continue
        mod, head = slot
        tid = item.id.strip()
        # **`s-` はショートの印です**（`src/pipeline.py` / `scripts/eta.py`）。
        # 長尺に付けると `topics.yaml` に置いても pipeline がその場で作り直し、
        # **`calc_sections` を渡さないまま台本を書かせます。**
        if not (LONG_ID_RE if long_form else ID_RE).match(tid):
            want = "`s-` で始めないこと" if long_form else "`s-` で始めること"
            dropped.append(f"id の形が不正（{want}）: {tid!r}")
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
        # **長尺は下限を上げます。** 8分30秒を下回ると `src/verify.py` が止めるので、
        # 指示が短いと**作ってから落ちます**（生成1本ぶんが捨てになる）。
        floor = LONG_ANGLE_MIN if long_form else 40
        if len(angle) < floor:
            dropped.append(
                f"{tid}: angle が短すぎます（{len(angle)}文字 / 下限 {floor}）")
            continue

        used.add(tid)
        rows.append({"id": tid, "title_seed": title, "angle": angle,
                     "calc": mod, "calc_sections": [key]})
    return rows, dropped


def drop_doomed(rows: list[dict], topics: list[dict]) -> tuple[list[dict], list[str]]:
    """**投稿の門が必ず止める種を、`topics.yaml` に書く前に外す**（2026-08-18）。

    `scripts/batch_build._drop_doomed` は同じことを**作る前**にやっていますが、
    そちらは**もう `topics.yaml` に入ってしまったもの**を毎回よけるだけです。
    **よけられたテーマは節を握ったまま残る**ので（`survey()` の `claimed`）、
    **その節は二度と割り当てられません。** 実測: 未投稿125件のうち4件がこれで、
    **4件とも節は新しく、題の主役に選んだ数だけが既出**でした。

    ここで落とせば、`topics.yaml` に1行も書かないので**節は未使用のまま残り**、
    次の回が同じ節を別の数字で書き直せます。

    **同じ回の中で作った2件どうしの衝突は見ません**（控えにまだ載っていないため）。
    そこは門が受けます。**節がぶつかるほうは `realign()` が既に落としています。**
    """
    from src import dupes

    calc_of = {t["id"]: t.get("calc", "") for t in topics}
    calc_of.update({r["id"]: r.get("calc", "") for r in rows})
    kept, dropped = [], []
    for r in rows:
        hits = dupes.blocking(r["title_seed"], r["id"], [], calc_of)
        if hits:
            dropped.append(f"{r['id']}: **投稿の門が必ず止めます** — {hits[0]['why']}"
                           f"（節は未使用のまま残すので、次の回が別の数字で書けます）")
        else:
            kept.append(r)
    return kept, dropped


ITEM_RE = re.compile(r"^([ \t]*)- id:", re.MULTILINE)


def list_indent(text: str) -> str:
    """`topics:` のリスト項目が、いま何字下げで書かれているか。

    ## なぜ読み取るのか（2026-08-25 に踏んだ）

    ここは長らく **2字下げ決め打ち**でした。ところが `config/topics.yaml` の
    項目は **503件すべてが0字下げ**（`- id:` が行頭）で、
    追記した5件だけが2字下げになり、**ファイル全体が読めなくなりました。**

        yaml.parser.ParserError: while parsing a block mapping
          expected <block end>, but found '-'

    **書いた直後の読み直しがこれを捕まえます**が、そのときには**もう書いた後**で、
    `topics.yaml` は壊れたまま残ります（実測：その回の `--count 5` は
    5件を書いてから落ちた）。**壊れた `topics.yaml` は、次の回の
    `status.py` も `pipeline` も全部止めます。**

    決め打ちを直しても同じことが起きます —— **どちらが正しいかは、
    そのときのファイルにしか書いていません。** だから読み取ります。
    項目が1つも無いファイルなら、YAML のブロック列の既定（0字下げ）を返します。
    """
    hits = ITEM_RE.findall(text)
    return hits[-1] if hits else ""


def to_yaml(rows: list[dict], indent: str = "") -> str:
    pad = indent
    out = []
    for r in rows:
        out.append(f"\n{pad}- id: {r['id']}")
        out.append(f"{pad}  title_seed: {yaml_scalar(r['title_seed'])}")
        out.append(f"{pad}  angle: >")
        for line in r["angle"].splitlines():
            out.append(f"{pad}    {line.strip()}" if line.strip() else "")
        out.append(f"{pad}  calc: {r['calc']}")
        out.append(f"{pad}  calc_sections:")
        for s in r["calc_sections"]:
            out.append(f"{pad}    - {yaml_scalar(s)}")
        out.append(f"{pad}  score: 1.0")
    return "\n".join(out) + "\n"


def yaml_scalar(text: str) -> str:
    """**必ず引用符でくくる。** 題には `:` も `#` も入りうる。"""
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


# **7日ぶんの長尺で取れる本数は、節ではなく族の数で決まります**（2026-08-26 に踏んだ）
#
# `--list` は長らく節しか数えていませんでした。**長尺の律速はそこではありません** ——
# `scripts/batch_build.pick` は `_drop_queue_tail_calcs` で
# **これから7日ぶんの長尺に出ている calc を丸ごと落とし**、さらに1回の batch で
# 同じ calc から取れるのは `per_calc`（既定2）までです。つまり
# **1族に7節あっても、7日で取れるのは2本。**
#
# 実測（2026-08-26 02:0x）: `jouto` の節を7つ足した直後、長尺向けのテーマは6件
# 残っていたのに `pick(long_form=True)` は **1件も返しませんでした**
# （`jouto` が7日ぶんの予約に載っていたため）。
# **節の数を見ているかぎり、この形は数字に出ません。**
PER_CALC_DEFAULT = 2
LONG_WINDOW_DAYS = 7


def print_long_stock() -> None:
    """長尺向けのテーマを、**族の数**で数えて出す。**API は叩きません。**"""
    from src import config, dupes

    try:
        pool = config.load_topics()["topics"]
        used = {r["topic"] for r in dupes.ledger_rows() if r.get("topic")}
    except Exception as exc:                                   # noqa: BLE001
        print(f"\n[長尺] 在庫が読めませんでした: {str(exc)[:120]}")
        return

    longs = [t for t in pool
             if t.get("calc") and t["id"] not in used
             and not t["id"].startswith("s-")]
    families = sorted({t["calc"] for t in longs})
    ceiling = min(len(longs), len(families) * PER_CALC_DEFAULT)
    print(f"\n=== 長尺向けのテーマ **{len(longs)}件** / 族 **{len(families)}** ===")
    if families:
        print("  " + " ".join(families))
    print(f"  **{LONG_WINDOW_DAYS}日ぶんで取れるのは最大 {ceiling}本**"
          f"（1族から {PER_CALC_DEFAULT}本まで。`batch_build` の `--per-calc` と"
          f" `_drop_queue_tail_calcs`）。")
    # **「別の族を書く」は、いちばん高い道でした**（2026-08-26 03:5x に測って直した）
    #
    # ここは長らく「増やすなら `src/calc/` に**別の族**を書くこと」とだけ
    # 言っていました。**そのとおりに読んだ回が2回、新しい表を書くところから
    # 始めています**（実測 20〜25分。`docs/JOURNAL.md` 2026-08-26 01:5x / 02:3x）。
    #
    # **族を1つ増やすのに、新しい表は要りません。** 長尺の族に数えられるのは
    # 「まだ投稿していない・`s-` で始まらないテーマ」の calc なので、
    # **既にある表のうち、まだ長尺のテーマを持っていない族**に節を1つ足して
    # `--count N --long` を撃てば、その族がそのまま1つ増えます。
    # 実測（08/26 03:2x）: `shougai` に節を3つ足して長尺で forge —— 族 3→4、
    # 7日ぶんの上限 6本→8本。**新しい表は1本も書いていません。**
    print(f"  **族を1つ増やすと、ここが {PER_CALC_DEFAULT}本 増えます。**"
          f" 道は2つあり、**下のほうが速い**:")
    print(f"    (1) `src/calc/` に**新しい表**を書く（実測 20〜25分）")
    print(f"    (2) **既にある表**のうち、まだ長尺のテーマを持っていない族に"
          f"**節を足して** `--count N --long`（実測 15分・08/26 03:2x に `shougai` で）")
    rest = sorted({t["calc"] for t in pool if t.get("calc")} - set(families))
    if rest:
        print(f"  **(2) で選べる族: {len(rest)}件**"
              f"（長尺のテーマをまだ1件も持っていない族。ここから選べば族が増えます）")
        print("    " + " ".join(rest[:12])
              + (" …" if len(rest) > 12 else ""))
    if len(longs) > ceiling:
        print(f"  **いま在庫は {len(longs)}件 あるのに {ceiling}本 しか取れません** —— "
              f"詰まっているのは節ではなく**族の数**です。"
              f"**同じ族に節を足しても、この数は1本も増えません。**")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--count", type=int, default=0, help="つくる件数")
    ap.add_argument("--list", action="store_true", help="未使用の見出しを数えるだけ")
    ap.add_argument("--dry-run", action="store_true", help="出すだけで書かない")
    ap.add_argument("--long", action="store_true",
                    help="**長尺（8分30秒以上）の企画を作る。**"
                         "既定はショート。門2a（長尺4,000時間）が唯一の門なので、"
                         "面を増やすならこちら（`LONG_PROMPT_HEAD` の節）")
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
        print_long_stock()
        if not spare:
            print("\n**未使用が0件です。** ここが本当の在庫切れなので、"
                  "`src/calc/` の表に節を足すこと（この道具では増えません）。"
                  "\n  **新しい表を書く必要はありません** —— 既にある表に"
                  "節を1つ足せば、その族から1本ぶんの在庫が出ます。")
            for line in dig_method_lines():
                print(line)
            print("  **長尺の在庫を増やすなら、足す先を"
                  "「まだ長尺のテーマを持っていない族」から選ぶこと** ——"
                  "上の族の数がそのまま7日ぶんの上限です。")
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
    prompt = build_prompt(picked, all_sections, topics, args.long)
    print(f"\n[forge] 書かせています…（{'**長尺**' if args.long else 'ショート'}）")
    forged, _ = ask(ForgedSet, prompt, model=args.model)
    rows, dropped = validate(forged, picked, all_sections, known_ids, args.long)
    rows, doomed = drop_doomed(rows, topics)
    dropped += doomed

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

    # **字下げは決め打ちにしない**（`list_indent` の節。2026-08-25 に壊した）
    existing = TOPICS_YAML.read_text(encoding="utf-8")
    block = to_yaml(rows, list_indent(existing))
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
