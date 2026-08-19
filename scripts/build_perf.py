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


def _rho(v: float | None) -> str:
    if v is None:
        return "  （本数が足りない）"
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
    print(f"  {'特徴':<14}{'engaged との向き':<22}再生 との向き")
    for name, a, b in build_perf.correlations(rows):
        print(f"  {name:<14}{_rho(a):<22}{_rho(b)}")
    print()
    print("  **理由はここからは分かりません**（公開時刻・族・配信の広さ・題材の人気と交絡）。")

    strong = [n for n, a, _ in build_perf.correlations(rows) if a is not None and abs(a) >= 0.3]
    if strong:
        print(f"  [!] **向きの出た特徴: {', '.join(strong)}** —— 次はここを動かして測ること")
    else:
        print("  [!] **どの特徴も無関係（|ρ| < 0.3）でした。**")
        print("      engaged の幅は上のとおり大きいのに、**いまここで測れている「作り」では"
              "1つも説明できていません。**")
        print("      ＝ 効いているのは、この一覧に**無い**もの（最初の1〜2秒の絵・声・"
              "題材そのもの）の側です。")
        print("      **特徴を足して測り直すこと。**当てずっぽうで作りを変えないこと。")

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
            print(f"  {int(r['views']):5d}回  engaged {r['engaged']:5.1%}  "
                  f"図{int(f['図の枚数'])} 棒{int(f['棒の本数']):2d} "
                  f"幅{int(f['題の幅']):3d} 桁{int(f['題の数字の桁'])}  {r['topic']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
