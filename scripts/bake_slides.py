#!/usr/bin/env python3
"""図解だけを焼いて、**隣のコマとどれだけ違うか**を数字で出す。

    python scripts/bake_slides.py --plan build/<ID>/slides_plan.json --short
    python scripts/bake_slides.py --script build/<ID>/script.json --short
    python scripts/bake_slides.py --plan <file> --short --only 3      # 1枚だけ焼く
    python scripts/bake_slides.py --plan <file> --short --out /tmp/x  # 置き場所を指定

## なぜ要るか（2026-08-15）

**申し送りに2回出て、2回とも作られませんでした。**

  18:3x「図解を1枚だけ焼いて目で見る道具を作ること。描画の直しは、いま
        フル生成10分を通さないと1ピクセルも見えません」
  21:1x「`reveal_variants` は『絵が変わったか』を見ていません。
        `slides_plan.json` は既に残っているので、画素差で判定できるはずです」

**同じ道具の話です。** 描画の直しを1回試すのに `claude -p` の台本生成（6〜11分）と
音声合成とエンコードを毎回通していたので、**1周で試せる回数が実質1回**でした。
それが「直したつもりが実画面では効いていない」を3回繰り返した理由の1つです
（`_reveal_headline` の説明にある `OePniwSIcTE` の8コマ中4コマ）。

台本は要りません。**`slides_plan.json` は画面に出る側そのもの**なので、
これを食わせれば `visuals.render` だけを 30秒 で回せます。

## この道具が答えること

- **隣り合うコマが、画面のどれだけを塗り替えているか**（`verify.slide_change_ratios`）。
  `verify.NEAR_DUPE_RATIO` を下回る組に `[!]` を付ける。
  **しきい値を実測で置くための目盛りが、これまでどこにもありませんでした**
  （`verify.py` のコメントは「実測で置くこと」と言っているのに、
  実測する手段が無かった）
- 見出しの文字列。**同じ見出しが並んでいないか**は目で1秒で分かる

## この道具が答えないこと

**「その絵でいいのか」は答えません。** 差が大きくても中身が悪いことはあります。
目視（contact sheet）と独立評価（`docs/CRITIQUE.md`）の代わりにはなりません。
ここが見ているのは**「動いたか」だけ**です。
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import visuals, verify                      # noqa: E402
from src.pipeline import SHORT_SLIDE_SECONDS         # noqa: E402


def expand(plan: list[dict], durations: list[float] | None) -> list[dict]:
    """`--script` から来たときだけ、pipeline と同じ割り方をする。

    尺が分からないので、1文あたり `SHORT_SLIDE_SECONDS × 2` と置きます
    （実測の1文は5〜6秒で、目標が `SHORT_SLIDE_SECONDS`）。
    **正確な枚数が要るなら `--plan` を使うこと。** そちらは実物です。
    """
    out: list[dict] = []
    for i, visual in enumerate(plan):
        dur = durations[i] if durations and i < len(durations) else SHORT_SLIDE_SECONDS * 2
        want = max(1, math.ceil(dur / SHORT_SLIDE_SECONDS))
        out.extend(visuals.reveal_variants(visual, want))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--plan", help="slides_plan.json（**割った後**。実物）")
    src.add_argument("--script", help="script.json（割る前。ここで割ります）")
    ap.add_argument("--short", action="store_true", help="縦画面で焼く")
    ap.add_argument("--topic", default="", help="配色を決めるテーマID")
    ap.add_argument("--only", type=int, default=None, help="この番号の1枚だけ焼く")
    ap.add_argument("--out", default="", help="出力先（既定は入力の隣の bake/）")
    args = ap.parse_args()

    if args.plan:
        path = Path(args.plan)
        plan = json.loads(path.read_text(encoding="utf-8"))
    else:
        path = Path(args.script)
        script = json.loads(path.read_text(encoding="utf-8"))
        plan = [s["visual"] for s in script.get("segments", [])]
        if args.short:
            plan = expand(plan, None)

    if args.only is not None:
        plan = plan[args.only:args.only + 1]

    out_dir = Path(args.out) if args.out else path.parent / "bake"
    slides = visuals.render(
        plan, out_dir, args.topic, theme_index=None, portrait=args.short
    )
    print(f"\n{len(slides)} 枚 → {out_dir}")

    if len(slides) < 2:
        return 0

    ratios = verify.slide_change_ratios(slides)
    print(f"\n=== 隣とどれだけ違うか（下限 {verify.NEAR_DUPE_RATIO * 100:.1f}%）===")
    bad = 0
    for i, r in enumerate(ratios):
        mark = "[!]" if r < verify.NEAR_DUPE_RATIO else "   "
        if r < verify.NEAR_DUPE_RATIO:
            bad += 1
        head = " ".join(str(plan[i + 1].get("headline", "")).split())[:34]
        print(f"  {mark} {i:2d}→{i + 1:2d}  {r * 100:6.2f}%   {head}")
    print(f"\n下限を下回った組: {bad} 件 / {len(ratios)}")
    print("  **この数字を見てから `verify.NEAR_DUPE_RATIO` を動かすこと。**"
          "コメントは最初から「実測で置くこと」と言っています")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
