#!/usr/bin/env python3
r"""**予約に入っている本の主役の数字が、いまの表にまだ在るか。**

    python scripts/stale_scheduled.py            # 鳴った本だけ出す
    python scripts/stale_scheduled.py --all      # 全件の内訳

## なぜ要るか（2026-08-19。**間に合ったのは偶然でした**）

`src/calc/*.py` を直すと、**その表から既に作って予約に入れた本**が、
黙って嘘になります。**本はもう YouTube 側にあるので、こちらの直しは届きません。**

実際に起きました。08-19 00:07 に `souzoku.best_ratio` を
0.25きざみ → 1%きざみへ直したとき、**その粗い格子の答えを主役にした本が
2本、予約に入ったまま**でした（`E5i0YfIkmnA` は 08-24 公開予定で、
主役の 4904万3334円 が実際は 5014万1334円）。**直した回は、自分が直す前に
作った本を見ていません。** 気づいたのは6日前で、**たまたま**です。

## 何を見るか（**当たり率を測ってから、この形にしました**）

見るのは **`uploaded.jsonl` の題（＝主役の数字）** が、
そのテーマの `calc_sections` の**いまの本文**に在るか、の1点です。

    測った形                              鳴った件数    うち本物
    angle 全部の数字（246本）                 53件        1件
    題の数字だけ                              16件        1件
    題の数字のうち **精密なものだけ**           **1件**      **1件**

「精密」は「万どまり・千どまりの丸めでない数」（`>= 10,000` かつ `% 1000 != 0`）です。
落とした15件は全部**丸めの言い換え**でした ——「1000万円」の `1000` 単体、
`4285万円`（実 42,857,142）のように**題で丸めた数**。
**これは書き手の嘘ではないので、鳴らせてはいけません。**

**この道具は「数字が変わったか」しか見ません。** `KPGuqj5v1Qs` のように
**数字は正しいが「いちばん安い」という言い方が偽**になる形は、ここには出ません
（言い方は表の数字と一致するため）。**calc の意味を変えた回は、
鳴らなくても自分で見にいくこと。**
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import topic_forge as tf  # noqa: E402
import yaml  # noqa: E402

from src import alerts  # noqa: E402


def is_precise(n) -> bool:
    """丸めの言い換えでない数だけを見る（上の当たり率の表）。"""
    return isinstance(n, int) and n >= 10_000 and n % 1_000 != 0


def scheduled(now: dt.datetime) -> list[dict]:
    """まだ公開されていない予約本（控えから）。**同じ題は最後の行が正。**"""
    out: dict[str, dict] = {}
    with open(ROOT / "data/uploaded.jsonl", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            at = row.get("at")
            if not at:
                continue
            when = dt.datetime.fromisoformat(at.replace("Z", "+00:00"))
            if when > now:
                out[row["topic"]] = row
    return sorted(out.values(), key=lambda r: r["at"])


def topics_by_id() -> dict[str, dict]:
    items = yaml.safe_load((ROOT / "config/topics.yaml").read_text(encoding="utf-8"))
    if isinstance(items, dict):
        items = items.get("topics", items)
    return {x["id"]: x for x in items}


def check(show_all: bool = False) -> list[dict]:
    now = dt.datetime.now(dt.timezone.utc)
    rows, by_id = scheduled(now), topics_by_id()
    mods = sorted({by_id[r["topic"]]["calc"] for r in rows if r["topic"] in by_id})
    cache: dict[str, dict[str, str]] = {}
    for m in mods:
        try:
            cache[m] = tf.sections(m)
        except SystemExit as exc:
            print(f"[stale] src.calc.{m} が落ちました: {str(exc)[:120]}")
            cache[m] = {}
    bad = []
    for r in rows:
        topic = by_id.get(r["topic"])
        if topic is None:
            continue
        secs = cache.get(topic["calc"], {})
        body = tf.sections_for(topic, secs)
        floor = tf.section_floor(secs)
        have = tf.numbers(body, floor) | tf.decimals(body)
        miss = [n for n in sorted(tf.numbers(r.get("title", ""), floor) - have)
                if is_precise(n)]
        if show_all:
            print(f"  {r['at'][:16]} {r['topic']}  {'鳴った' if miss else 'ok'}")
        if miss:
            bad.append({"video_id": r.get("video_id"), "topic": r["topic"],
                        "at": r["at"], "title": r.get("title", ""), "miss": miss})
    return bad


def main() -> int:
    ap = argparse.ArgumentParser(description="予約本の主役の数字が、いまの表に在るか")
    ap.add_argument("--all", action="store_true", help="全件の内訳を出す")
    args = ap.parse_args()

    bad = check(show_all=args.all)
    ring = alerts.ring("stale_scheduled", len(bad))
    if ring.folded:
        print(ring.line)
        return 0
    if not bad:
        print("[stale] 予約本の主役の数字は、全部いまの表に在ります")
        return 0
    print(f"[stale] **{len(bad)}本の主役の数字が、いまの表にありません。**")
    print("        表を直した回が、直す前に作った本を残しています。"
          "**公開の前に外すこと**（`scripts/unschedule.py <video_id> --why ...`）")
    for b in bad:
        print(f"  {b['at'][:16]}  {b['video_id']}  {b['topic']}")
        print(f"      『{b['title']}』  表に無い数: {b['miss']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
