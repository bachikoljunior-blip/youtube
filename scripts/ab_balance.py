#!/usr/bin/env python
"""**A/B の腕を、在庫の側で埋める。**

## なぜ要るか（2026-08-20 00:2x に実測して書いた）

`hook_form` の判定（`config/hypotheses.yaml`・2026-09-16）は
**どちらの群も8本に満たなければ判定しない**と書いてあります。
この回の頭で数えたとき、`pick(60)` が返す在庫は **問い 7 / 条件 9** ——
**問いの側が床に1本足りない**状態でした。

そこで5本の表に節を14本掘り、`topic_forge` で在庫を **16 → 27本** に増やしました。
**それでも問いの側は 7本のままでした。**

    足した11本の振り分け:  条件 11 / 問い 0

`hook_form()` はテーマIDの SHA-1 で半々に割ります。全434件では 210 / 224 と
きれいに割れているので、**この11連続は偏った実装ではなく、ただの引き**です
（同じ向きに11回続く確率は 1/2048）。**しかし結果は同じで、律速の腕は1本も増えません。**

**ここが構造の穴です。** 在庫を増やす手（節を掘る → `topic_forge`）は、
**どちらの腕に入るかを選べません。** 腕の片方が床に届かない限り実験は判定できず、
`eta.py` が名指しする唯一の近い腕（1本あたり 1.4倍）は永久に測れません。
**在庫の総数を見ているだけでは、この穴は見えません。**

## 何をするか

**まだ投稿していないテーマのIDを付け替えて、腕の数をそろえます。**

`hook_form()` が見ているのは**テーマIDの hash だけ**で、
題材にも計算にも触れていません。だから ID を付け替えることは
**「その本をもう一度コインで振り直す」ことと同じ**で、中身に偏りは入りません。
まだ投稿していない本だけを動かすので、**公開済みの群も、判定の条件も、
`hypotheses.yaml` のしきい値も、1文字も変わりません。**

**投稿済みのテーマには触れません**（説明欄の `[t:テーマID]` から群を引き直すので、
付け替えると過去の本の群が変わってしまいます）。

    python scripts/ab_balance.py --target 12            # 空撃ち。何をするかだけ出す
    python scripts/ab_balance.py --target 12 --apply    # config/topics.yaml を書き換える
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import batch_build                     # noqa: E402
from src import config                              # noqa: E402
from src import script_writer                       # noqa: E402
from src.ab_split import EXPERIMENTS, settle_by     # noqa: E402
from src.supply import today_jst                    # noqa: E402

TOPICS = ROOT / "config" / "topics.yaml"

#: 割り振りの関数（名前 → 呼ぶもの）。**足すときはここだけ**。
SPLITS = {
    "hook_form": script_writer.hook_form,
    "title_form": script_writer.title_form,
}

#: それぞれの腕の名前。**在庫の側から数えないこと** ——
#: 片方が0本の回（＝この道具がいちばん要る回）に、腕そのものが消えて見えます
#: （2026-08-20 に検査で踏んだ）。
ARMS = {
    "hook_form": ("問い", "条件"),
    "title_form": ("問い", "断定"),
}

#: 付け替えに使う接尾。**意味を持たせないこと**（IDから中身が読めると人が選び始めます）。
SUFFIXES = tuple(f"-r{i}" for i in range(2, 40))


def days_until(settle: date, today: date | None = None) -> int:
    """締切の日までに**置ける日数**（今日も含む）。過ぎていても 1 は返します。"""
    return max(1, (settle - (today or today_jst())).days + 1)


def _pool(count: int = 60, days: int = 1) -> list[dict]:
    """締切までの `days` 日ぶんに置ける本。

    ## `per_calc` は「1日に何本まで」の門です（2026-08-20 19:2x に測って直した）

    ここは長らく `batch_build.pick(count, [])` —— つまり **1日ぶんの上限**でした。
    `pick` の `per_calc=2` は「**同じ制度の本が1日に何本も並ぶと繰り返しに見える**」
    という理由で置かれた門なので（`batch_build.pick` の docstring）、
    **20日先の締切に何本置けるかを聞く場面では、掛ける日数のぶんだけ緩みます。**

    実測（2026-08-20 19:2x）:

        未投稿・calc あり            **33本**
        pick(60)（＝1日ぶん）        **26本**   ← 7本が見えていなかった
          内訳: aoiro 5→2 / zoyo 4→2 / kogaku 3→2 / nenkinmenjo 3→2

    `hook_form` は両群 16本＝**32本**が床で、締切は 09/09（20日先）。
    **26本と読むと「在庫だけでは床に届きません」になり、33本と読むと届きます。**
    `ab_balance` はそこで `**動かせません。**` と言って降りていました ——
    `eta.py` がこの回に名指しした腕（`per_video`）を測る唯一の実験が、
    **在庫の数え方だけで畳まれる**形です（`src/ab_split.py` 冒頭の `next_if_false`）。

    **1日の門はそのまま**です。20日に散らすので、aoiro の5本は
    2本/日 × 20日 = 40本の枠に収まります。
    """
    days = max(1, days)
    return batch_build.pick(count, [], per_calc=batch_build.DEFAULT_PER_CALC * days)


def tally(rows: list[dict], split) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for r in rows:
        out.setdefault(split(r["id"]), []).append(r["id"])
    return out


def rename_for(topic_id: str, want: str, split, taken: set[str]) -> str | None:
    """`want` の腕に入る新しいIDを探す。**既にあるIDは避けます。**

    もとのIDに接尾を足すだけなので、**題材も calc も変わりません。**
    """
    base = re.sub(r"-r\d+$", "", topic_id)
    for suf in ("",) + SUFFIXES:
        cand = base + suf
        if cand in taken or cand == topic_id:
            continue
        if split(cand) == want:
            return cand
    return None


def plan(target: int, split_name: str = "hook_form",
         count: int = 60, days: int = 1) -> tuple[dict[str, list[str]], list[tuple[str, str]], str]:
    """どの本を、どちらの腕へ付け替えるか。**書き込みはしません。**

    `days` は**締切までに置ける日数**（`days_until`）。`per_calc` は1日ぶんの門なので、
    ここを 1 にすると在庫を**実際より少なく**数えます（`_pool` の冒頭）。
    """
    split = SPLITS[split_name]
    rows = _pool(count, days)
    counts = tally(rows, split)
    for arm in ARMS[split_name]:
        counts.setdefault(arm, [])          # **0本の腕も、腕として数える**
    arms = sorted(ARMS[split_name], key=lambda a: len(counts[a]))
    short, long_ = arms[0], arms[-1]
    need = target - len(counts[short])
    if need <= 0:
        return counts, [], f"**{short} は既に {len(counts[short])}本**（目標 {target}本）。動かしません"
    spare = len(counts[long_]) - target
    if spare < need:
        need = max(0, min(need, spare))
    if need <= 0:
        return counts, [], (f"**動かせません。** {long_} は {len(counts[long_])}本 しかなく、"
                            f"{target}本 を残すと出せる本がありません。"
                            "**在庫を増やすのが先**です（節を掘る → `topic_forge`）")
    taken = {t["id"] for t in config.load_topics()["topics"]}
    moves: list[tuple[str, str]] = []
    # **後ろから取ります**（`pick` は score の高い順なので、良い本を先に残す）
    for tid in reversed(counts[long_]):
        if len(moves) >= need:
            break
        new = rename_for(tid, short, split, taken)
        if new is None:
            continue
        taken.add(new)
        moves.append((tid, new))
    note = (f"**{short} を {len(counts[short])} → {len(counts[short]) + len(moves)}本**、"
            f"{long_} を {len(counts[long_])} → {len(counts[long_]) - len(moves)}本 にします")
    return counts, moves, note


def apply(moves: list[tuple[str, str]]) -> int:
    """`config/topics.yaml` の `id:` の行だけを書き換える。**他の行は触りません。**"""
    text = TOPICS.read_text(encoding="utf-8")
    done = 0
    for old, new in moves:
        pat = re.compile(rf"^(\s*-?\s*id:\s*){re.escape(old)}\s*$", re.M)
        text, n = pat.subn(lambda m: m.group(1) + new, text)
        if n != 1:
            raise SystemExit(f"`id: {old}` が {n} 行に当たりました（1行のはず）。**書きません**")
        done += n
    TOPICS.write_text(text, encoding="utf-8")
    return done


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="hook_form", choices=sorted(SPLITS))
    ap.add_argument("--target", type=int, default=12,
                    help="どちらの腕にも、この本数を用意する（判定の床は8本）")
    ap.add_argument("--count", type=int, default=60, help="`pick` に頼む数")
    ap.add_argument("--days", type=int, default=0,
                    help="締切までに置ける日数（既定は実験の締切から数える）")
    ap.add_argument("--apply", action="store_true", help="実際に書き換える")
    a = ap.parse_args()

    days = a.days or days_until(settle_by(EXPERIMENTS[a.split]))
    counts, moves, note = plan(a.target, a.split, a.count, days)
    print(f"=== {a.split} の腕（締切まで {days}日 に置ける本）===")
    for arm in sorted(counts):
        print(f"  {arm:6s} {len(counts[arm]):3d}本")
    print(f"  目標 {a.target}本（判定の床は8本）")
    print(f"\n{note}")
    if not moves:
        return
    print(f"\n=== 付け替える {len(moves)}件（**まだ投稿していない本だけ**）===")
    for old, new in moves:
        print(f"  {old}\n    → {new}")
    if not a.apply:
        print("\n**空撃ちです。**書き換えるには `--apply` を付けること")
        return
    n = apply(moves)
    print(f"\n[ab_balance] {n}件を書き換えました: {TOPICS}")
    counts2 = tally(_pool(a.count, days), SPLITS[a.split])
    print("=== 書き換えた後 ===")
    for arm in sorted(counts2):
        print(f"  {arm:6s} {len(counts2[arm]):3d}本")


if __name__ == "__main__":
    main()
