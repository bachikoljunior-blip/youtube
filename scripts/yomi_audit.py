#!/usr/bin/env python3
"""**公開ずみの読み上げ全文**を形態素解析にかけ、危ない語を機械が名指しする。

    python scripts/yomi_audit.py            # 全文（時間がかかる。--limit で刻める）
    python scripts/yomi_audit.py --limit 400
    python scripts/yomi_audit.py --report   # 前に作った data/yomi_risk.json を読むだけ

## なぜ要るか

`src/verify._check_yomi` が見ていた語は **1語**（裸の「額」）。
この repo の読み上げは **694本・6,206行・漢字のかたまり 異なり 3,514語** ある。
**0.03% しか見ていない門**を「読みの検査」と呼んでいた。

ここが作るのは `data/yomi_risk.json`。中身は
**「同じ表層が文脈で別の発音になった語」**（＝ R1「割れる」）の実測表で、
`src/yomi_gate.inspect()` がそれを引いて門にする。

## 測り方（**推測を1つも混ぜない**）

公開ずみ台本の読み上げ行を `data/critique_queue/*.json` から集め、
1行ずつ open-jtalk の `-ot`（形態素解析の生出力）に通して
`(表層 → 発音の集合)` を積む。**2つ以上の発音が観測された表層が「割れる語」。**

**open-jtalk は入力の1行目しか解析しない**（2026-09-02 に実測。改行区切りで
まとめて渡すと2行目から先が黙って落ちる）。だから1行ずつ撃っている。
速さは実測 **約7ms/文字**（音声合成の側が律速で、`-s` を下げても変わらない）。

## この表が言えること・言えないこと

言えるのは「**open-jtalk の中で読みが割れる**」まで。本番は Google TTS なので、
**割れる ≠ 誤読**。ここは候補を漏れなく作る役で、判定は耳
（`scripts/probe_yomi.py`）→ `data/yomi_ledger.json`。

**覆る条件**: 耳で測って `safe` が9割を超えたら、この条件は粗すぎる。
"""
from __future__ import annotations

import argparse
import collections
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import yomi_gate as G  # noqa: E402
from src.yomi import to_speech  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
STASH = ROOT / "data" / "critique_queue"
OUT = ROOT / "data" / "yomi_risk.json"
KANJI = re.compile(f"[{G.KANJI}]")


def lines() -> list[str]:
    """公開ずみ台本の読み上げ行（異なり）。**作った順に並べる。**"""
    seen: dict[str, None] = {}
    for path in sorted(STASH.glob("*.json")):
        if path.name.endswith(".plan.json"):
            continue
        try:
            meta = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for line in meta.get("narration") or []:
            s = str(line).strip()
            if s and KANJI.search(s):
                seen.setdefault(s, None)
    return list(seen)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0, help="先頭から N 行だけ")
    ap.add_argument("--report", action="store_true", help="作らずに読むだけ")
    args = ap.parse_args()

    if args.report:
        blob = json.loads(OUT.read_text(encoding="utf-8")) if OUT.exists() else {}
        split = blob.get("split", {})
        print(f"[yomi] {blob.get('at', '?')} 時点: 行 {blob.get('lines', 0)} / "
              f"漢字の表層 異なり {blob.get('surfaces', 0)} / **割れる語 {len(split)}**")
        for s, prons in sorted(split.items(), key=lambda kv: -len(kv[1]))[:40]:
            print(f"   {s:<8} {'/'.join(sorted(prons))}")
        return 0

    if not G.available():
        print("[yomi] open-jtalk が無いので測れません（bash scripts/setup.sh）")
        return 0

    rows = lines()
    if args.limit:
        rows = rows[:args.limit]
    prons: dict[str, set] = collections.defaultdict(set)
    silent: dict[str, int] = collections.Counter()
    started, chars = time.time(), 0
    for i, line in enumerate(rows):
        spoken = to_speech(line)            # **TTS に渡る形**で測る（置換後）
        chars += len(spoken)
        try:
            toks = G.analyze(spoken)
        except RuntimeError:
            continue
        for t in toks:
            s = t["surface"]
            if not KANJI.search(s):
                continue
            if t["pron"] in G._SILENT:
                silent[s] += 1
            else:
                prons[s].add(t["pron"])
        if i % 200 == 199:
            rate = chars / max(1e-9, time.time() - started)
            print(f"   {i + 1}/{len(rows)} 行  {rate:.0f}文字/秒  "
                  f"割れる語 {sum(1 for v in prons.values() if len(v) > 1)}", flush=True)

    split = {s: sorted(v) for s, v in prons.items() if len(v) > 1}
    blob = {
        "at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "lines": len(rows), "surfaces": len(prons),
        "seconds": round(time.time() - started, 1),
        "split": split,
        "silent": dict(silent),
    }
    OUT.write_text(json.dumps(blob, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"[yomi] 行 {len(rows)} / 漢字の表層 異なり {len(prons)} / "
          f"**割れる語 {len(split)}**（{len(split) / max(1, len(prons)) * 100:.1f}%）"
          f" / 音にならない語 {len(silent)}  → {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
