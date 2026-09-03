#!/usr/bin/env python3
"""**説明が分かりやすいかの修正ループ**を、台本1本に手で当てる（2026-09-03）。

    python scripts/clarity_loop.py data/scripts/<題材>.script.json           # 見るだけ
    python scripts/clarity_loop.py data/scripts/<題材>.script.json --write   # 直した本文を書き戻す

毎本の輪は `src/pipeline.py` が回します（`clarify_and_fix`）。ここは
**すでに在る本の台本**に同じ輪を当てるための口です（差し替えのとき）。

なぜ要るかと、「ほとんど言いがかり」の決め方は `src/clarity_loop.py` の docstring に
全部あります。**評価は模型を叩きます**（既定は台本と同じ `opus`。`CLARITY_MODEL` で差し替え）。

## **(c) わざと寝かせてある —— 毎本の輪は `src/pipeline.py`（`clarify_and_fix`）が回します。ここは**手で当てる口**です**（2026-09-03 に決めた）

**どこからも撃たれていないのが正しい形です。**（`scripts/retro.py` の三択を、この回が (c) で倒しました。**やり直さないこと**）
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import clarity_loop as C          # noqa: E402


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("script", type=Path, help="台本の JSON")
    ap.add_argument("--topic", default="", help="題材ID（機械の検査に要る）")
    ap.add_argument("--write", action="store_true", help="直した本文を書き戻す")
    ap.add_argument("--short", action="store_true", help="ショートとして検査する")
    ap.add_argument("--rounds", type=int, default=C.ROUNDS_MAX)
    ap.add_argument("--model", default="", help="評価と書き直しの模型")
    ap.add_argument("--work", type=Path, default=None, help="控えの置き場（既定は build/<題材>）")
    args = ap.parse_args(argv)

    blob = json.loads(args.script.read_text(encoding="utf-8"))
    topic = args.topic or args.script.name.split(".")[0]
    work = args.work or (ROOT / "build" / topic)
    before = C.lines(blob)

    report = C.loop(blob, topic, work, portrait=args.short, rounds=args.rounds,
                    model=args.model or None)

    if report["changed"]:
        print("\n=== 書き換わったコマ ===")
        for i, (a, b) in enumerate(zip(before, C.lines(blob)), 1):
            if a != b:
                print(f"\nコマ{i}\n  前: {a}\n  後: {b}")
        if args.write:
            args.script.write_text(
                json.dumps(blob, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            print(f"\n[clarity] {args.script} に書き戻しました")
        else:
            print("\n[clarity] `--write` を付けると書き戻します")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
