"""**公開日ごとに「1本あたりの再生」を出す**（`docs/MEANS.md` M14 の物差し）。

    python scripts/per_day_views.py            # 24時間時点。既定
    python scripts/per_day_views.py --hours 72

M14 は「1日の本数を段階的に上げ、1本あたりが崩れる点を探す」手段で、
止まる条件は **「1段上げて1本あたりの中央値が2割以上落ちたら、そこが上限」**です。

## なぜ道具にしたか（2026-08-19）

**その中央値を出す道具が、どこにもありませんでした。**
2 → 4 の段は 8/16 に置かれ、判定は「8/18 ごろに 1〜2本/日の日と比べる」と
書いてあるだけで、**比べる手は誰の手元にもありません。**
この回は手で組み立てて出しましたが、**次の段（08/24〜08/27 の 22〜25本/日）でも
同じものが要ります。** 手で組み立て直すと、そのたびに違う切り方になります。

## 何を見ているか

- **公開時刻は `data/views.jsonl` から復元します**（`at - hours`）。
  控え（`data/uploaded.jsonl`）は 8/16 以降しか無く、**比較の相手（8/05〜8/15）が
  丸ごと落ちます。** `views.jsonl` は 8/04 から全部あります
- **長尺を外します**（`--min-views`）。長尺は 24時間で 0〜2再生なので、
  混ぜると中央値がその日の長尺の有無だけで動きます。**本数の話ではありません**
- **`hours` の近い点を採ります**（±35%）。読みは1本ずつ時刻がずれるので、
  ちょうど24.0時間の点はありません
"""
from __future__ import annotations

import argparse
import collections
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

JST = timezone(timedelta(hours=9))
VIEWS = ROOT / "data" / "views.jsonl"

# 長尺は24時間で 0〜2再生。**その日に長尺が1本あるかどうかで中央値が動く**ので外す。
DEFAULT_MIN_VIEWS = 10
# 読みは1本ずつ時刻がずれる。ちょうどの点は無いので、近いものを採る。
TOLERANCE = 0.35


def _load(path: Path = VIEWS) -> dict[str, list[tuple[float, int, datetime]]]:
    by_id: dict[str, list[tuple[float, int, datetime]]] = collections.defaultdict(list)
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            at = datetime.fromisoformat(str(row["at"]).replace("Z", "+00:00"))
            by_id[row["id"]].append((float(row["hours"]), int(row["views"]), at))
        except (ValueError, KeyError, TypeError):
            continue          # 壊れた行は落とす（読みの側の事故で判定を止めない）
    return by_id


def published_at(points: list[tuple[float, int, datetime]]) -> datetime:
    """公開時刻を `at - hours` の**中央値**で復元する。

    1点だけで決めないのは、`hours` が読みごとに丸められているためです。
    """
    ests = sorted(p[2] - timedelta(hours=p[0]) for p in points)
    return ests[len(ests) // 2].astimezone(JST)


def views_at(points: list[tuple[float, int, datetime]], target: float) -> int | None:
    """`target` 時間にいちばん近い読みを返す。無ければ `None`。"""
    best: tuple[float, int] | None = None
    for hours, views, _ in sorted(points):
        if not (1 - TOLERANCE) * target <= hours <= (1 + TOLERANCE) * target:
            continue
        if best is None or abs(hours - target) < abs(best[0] - target):
            best = (hours, views)
    return None if best is None else best[1]


def per_day(by_id, *, target: float, min_views: int) -> dict[str, list[int]]:
    """公開日（JST）→ その日に公開した本の、`target` 時間時点の再生。"""
    out: dict[str, list[int]] = collections.defaultdict(list)
    for vid, points in by_id.items():
        got = views_at(points, target)
        if got is None or got < min_views:
            continue
        out[published_at(points).date().isoformat()].append(got)
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="公開日ごとの「1本あたりの再生」")
    ap.add_argument("--hours", type=float, default=24.0,
                    help="何時間時点で比べるか（既定 24）")
    ap.add_argument("--min-views", type=int, default=DEFAULT_MIN_VIEWS,
                    help=f"これ未満は長尺とみなして外す（既定 {DEFAULT_MIN_VIEWS}）")
    ap.add_argument("--group", default="",
                    help="本数で括って中央値を比べる。例 1-2,3-6,7-99")
    args = ap.parse_args(argv)

    days = per_day(_load(), target=args.hours, min_views=args.min_views)
    if not days:
        print("[per_day] 読める点がありません。")
        return 1

    print(f"=== 公開日べつ 1本あたりの再生（{args.hours:.0f}時間時点・"
          f"{args.min_views}再生未満は長尺として除外）===")
    for day in sorted(days):
        vals = sorted(days[day], reverse=True)
        print(f"  {day}  {len(vals):>3}本  中央 {statistics.median(vals):>7.0f}   {vals}")

    if not args.group:
        return 0

    print("\n=== 本数の段べつ（**M14 の物差し。2割以上の下げが上限の合図**）===")
    bands = []
    for spec in args.group.split(","):
        lo, hi = (int(x) for x in spec.split("-"))
        vals = [v for d, vs in days.items() if lo <= len(vs) <= hi for v in vs]
        n_days = sum(1 for vs in days.values() if lo <= len(vs) <= hi)
        if not vals:
            print(f"  {spec:>8}本/日  **該当日0日。判定できません**")
            continue
        med = statistics.median(vals)
        bands.append((spec, med))
        print(f"  {spec:>8}本/日  {n_days}日 {len(vals):>3}本  中央 {med:>7.0f}")
    for (lo_spec, lo_med), (hi_spec, hi_med) in zip(bands, bands[1:]):
        ratio = hi_med / lo_med if lo_med else float("inf")
        # **符号は「変化」で出すこと。** 「落ち幅」で出すと、上がった段が
        # `-50%` と表示されて**下がったように読めます**（2026-08-19 に1度そう出した）。
        change = (ratio - 1) * 100
        verdict = ("**2割以上落ちた ＝ ここが上限**" if change <= -20
                   else "落ちていない ＝ **まだ上げられる**")
        print(f"  {lo_spec} → {hi_spec}: {ratio:.3f}倍（{change:+.1f}%）  {verdict}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
