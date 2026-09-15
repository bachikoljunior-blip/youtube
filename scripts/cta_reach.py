#!/usr/bin/env python3
"""**一手（登録の言葉）が、どこに置けば何人に届くか**を、この repo の実測から数え直す。

2026-09-16 08:5x・optimizer・Fable 5.1・ultracode が足した。**API 0単位**
（読むのは `data/retention.json` と `data/video_forms.json` だけ ＝ 既に引いてある物）。

`studio/script.EARLY_CTA_LO` / `EARLY_CTA_HI` の窓は、この出力の数から引いてあります。
**窓を動かすときは、まずこれを撃って数を見ること**（覆る条件は `script.py` の同じ註）。

    python scripts/cta_reach.py
"""
from __future__ import annotations

import json
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
POSITIONS = [0.02, 0.04, 0.05, 0.08, 0.10, 0.15, 0.20, 0.25, 0.33, 0.50, 0.75, 1.00]


def curves() -> dict[str, list[list[list[float]]]]:
    """形ごとの retention 曲線。曲線は [[位置, 残っている割合, ...], ...]。"""
    ret = json.loads((ROOT / "data" / "retention.json").read_text())
    forms = json.loads((ROOT / "data" / "video_forms.json").read_text())["forms"]
    out: dict[str, list] = {}
    for vid, c in ret.items():
        f = forms.get(vid)
        if not f or not c:
            continue
        out.setdefault(f, []).append(sorted(c, key=lambda r: r[0]))
    return out


def at(curve: list[list[float]], p: float) -> float:
    """位置 p にいちばん近い目盛りの、残っている割合。"""
    return min(curve, key=lambda r: abs(r[0] - p))[1]


def table(cs: list[list[list[float]]]) -> dict[float, float]:
    return {p: st.median([at(c, p) for c in cs]) for p in POSITIONS}


def main() -> int:
    cs = curves()
    for form in ("長尺", "ショート"):
        if form not in cs:
            print(f"{form}: retention が 1本も無い")
            continue
        t = table(cs[form])
        end = t[1.00]
        print(f"\n=== {form}  n={len(cs[form])}本   出口 = {end:.1%}")
        print("  位置    残っている割合   出口の何倍")
        for p in POSITIONS:
            mul = (t[p] / end) if end else float("inf")
            print(f"  {p:5.0%}   {t[p]:12.1%}   {mul:8.1f}倍")
    lo, hi = _window()
    if "長尺" in cs:
        t = table(cs["長尺"])
        end = t[1.00]
        print(f"\nいまの窓 {lo:.0%}〜{hi:.0%} ＝ 長尺で 出口の "
              f"{t[_near(hi)] / end:.1f}〜{t[_near(lo)] / end:.1f}倍"
              if end else "")
    return 0


def _near(p: float) -> float:
    return min(POSITIONS, key=lambda q: abs(q - p))


def _window() -> tuple[float, float]:
    sys.path.insert(0, str(ROOT))
    from studio import script  # noqa: PLC0415
    return script.EARLY_CTA_LO, script.EARLY_CTA_HI


if __name__ == "__main__":
    raise SystemExit(main())
