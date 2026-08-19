#!/usr/bin/env python3
"""**動画の作りの特徴 × engaged** を突き合わせる（`src/build_perf.py` の口）。

    python scripts/build_perf.py

**API を1単位も使いません**（手元の `data/scan.jsonl` と `data/uploaded.jsonl` だけ）。
なぜこれを測るのかは `src/build_perf.py` の冒頭に書いてあります。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import build_perf  # noqa: E402


def _rho(d: dict, key: str) -> str:
    if d["why"] == "本数不足":
        return f"（測れた本が{d['n']}本・{build_perf.MIN_N}本から出す）"
    if d["why"] == "変化なし":
        return f"（{d['n']}本とも同じ値＝**一度も試していない**）"
    v = d[key]
    if v is None:
        return "（向きが出ません）"
    word = "同じ向き" if v >= 0.3 else ("逆向き" if v <= -0.3 else "無関係")
    return f"{v:+.2f}  {word}"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rows", action="store_true", help="1本ずつの表も出す")
    args = ap.parse_args(argv)

    rows, dropped = build_perf.collect()
    if not rows:
        print("[build_perf] 測れる本がありません（`data/scan.jsonl` が空か、控えが引けません）")
        return 1

    eng = sorted(r["engaged"] for r in rows)
    print("=== 動画の作りの特徴 × engaged（**向きだけ**）===")
    print(f"  測れた {len(rows)}本 ／ 落とした {len(dropped)}本（下に内訳）")
    print(f"  engaged の幅: {eng[0]:.1%} 〜 {eng[-1]:.1%} ＝ **{eng[-1]/eng[0]:.1f}倍**"
          if eng[0] else "  engaged の幅: 下端が0です")
    print("  **要るのは 1本あたり再生の 1.4倍**（`scripts/eta.py` の天井）。"
          "幅のほうが大きいなら、倍率としては足ります")
    print()
    cors = build_perf.correlations(rows)
    print(f"  {'特徴':<14}{'engaged との向き':<40}再生 との向き")
    for d in cors:
        print(f"  {d['name']:<14}{_rho(d, 'eng'):<40}{_rho(d, 'views')}")
    print()
    print("  **理由はここからは分かりません**（公開時刻・族・配信の広さ・題材の人気と交絡）。")

    measured = [d for d in cors if not d["why"]]
    strong = [d["name"] for d in measured if d["eng"] is not None and abs(d["eng"]) >= 0.3]
    if strong:
        print(f"  [!] **向きの出た特徴: {', '.join(strong)}** —— 次はここを動かして測ること")
    else:
        print("  [!] **測れた特徴は、どれも engaged と無関係（|ρ| < 0.3）でした。**")
        print("      engaged の幅は上のとおり大きいのに、**いまここで測れている「作り」では"
              "1つも説明できていません。**")

    waiting = [d for d in cors if d["why"] == "本数不足"]
    untried = [d for d in cors if d["why"] == "変化なし"]
    if waiting:
        print()
        print(f"  --- **待てば出る {len(waiting)}件**（控えのある本が {build_perf.MIN_N}本 に届いていない）---")
        for d in waiting:
            print(f"    {d['name']:<14} いま {d['n']:2d}本")
        print("    出どころは `data/critique_queue/<video_id>.json`。**控えを取り始めたのは 08/17** で、")
        print("    いま再生の付いている本は 08/04〜08/15 に公開したものです。")
        print("    **これは道具の穴ではなく、日数です。**1日25本の公開が始まっているので、")
        print("    08/17 以降の本に再生が付けば自動で増えます。**当てずっぽうで埋めないこと。**")
    if untried:
        print()
        print(f"  --- [!] **待っても出ない {len(untried)}件**（全部の本が同じ値）---")
        for d in untried:
            print(f"    {d['name']:<14} {d['n']}本とも同じ")
        print("    **これは「効かない」ではありません。「一度も試していない」です。**")
        print("    向きを知りたければ、**違う値の本を作って出すしかありません。**")

    if dropped:
        print()
        print(f"  --- 落とした {len(dropped)}本（**落とした側が答えである可能性は消えません**）---")
        by: dict[str, int] = {}
        for _, why in dropped:
            by[why] = by.get(why, 0) + 1
        for why, n in sorted(by.items(), key=lambda t: -t[1]):
            print(f"    {n:3d}本  {why}")

    if args.rows:
        print()
        print("  --- 1本ずつ ---")
        for r in rows:
            f = r["features"]
            head = "" if f["冒頭の声の幅"] is None else f"冒頭{int(f['冒頭の声の幅']):3d} "
            print(f"  {int(r['views']):5d}回  engaged {r['engaged']:5.1%}  "
                  f"尺{int(f['尺（秒）'] or 0):3d}s 図{int(f['図の枚数'])} 棒{int(f['棒の本数']):2d} "
                  f"幅{int(f['題の幅']):3d} 数字まで{int(f['数字までの幅']):3d} "
                  f"{head} {r['topic']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
