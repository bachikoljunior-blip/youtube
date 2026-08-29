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
    """公開日（JST）→ その日に公開した本の、`target` 時間時点の再生。

    **`min_views` に届かなかった本は入りません。** その日に何本 置いたかは
    `placed_per_day()` のほうで数えます（下の docstring）。
    """
    out: dict[str, list[int]] = collections.defaultdict(list)
    for vid, points in by_id.items():
        got = views_at(points, target)
        if got is None or got < min_views:
            continue
        out[published_at(points).date().isoformat()].append(got)
    return out


def placed_per_day(by_id, *, target: float) -> dict[str, int]:
    """公開日（JST）→ **その日に置いた本の数**（再生の床を当てない）。

    **`--group` の段は、この数で括ります。** `per_day()` の本数ではありません。

    ## なぜ分けたか（2026-08-29 に踏んだ。**待ちが9回 鳴って、9回とも答えが出ない**）

    `config/watches.yaml` の `予約30分きざみ-3日` は、`src/watches.py` の
    `_k_days_with_min_videos` で **「その日に置いた本」を数えて**「満ちました」を
    出します（実測 08/20 **25本** ／ 08/21 **32本** ／ 08/22 **25本**）。
    ところが `--group 8-13,16-99` は `len(vs)` ——
    **`min_views` を通った本だけ**で括っていました（同じ3日が **10 / 11 / 12本**）。

    **`16-99本/日` に入る日は、この道具の側には永久に現れません。**
    実測 2026-08-29: `**該当日0日。判定できません**`。
    待ちは 00:58 から **9回** 鳴り、`then:` が名指しするこの1行が、
    **9回とも同じ「判定できません」を返していました。**

    **門と判定が別の母集団を数える**形は、`config/hypotheses.yaml` の
    「深い題のショート」で一度 直っています（`src/deep_short.py`・
    2026-08-29 の `fix: 門と判定の手順が、別の母集団を数えていた`）。**同じ形の2件目です。**

    そして**中身の側でも、置いた本数で括るほうが正しい** ——
    この待ちが問うているのは「**1日に何本 置くと1本あたりが落ちるか**」で、
    主語は**置いた本数**です。生き残った本数で括ると、
    実測 08/20（置いた 25本・生きた 10本・中央 374回）と
    08/23（置いた 13本・生きた 10本・中央 1,046回）が
    **同じ「10本/日」の段に入ります**（中央値は **2.8倍** ちがう）。
    **括る軸そのものが、測りたいものと別でした。**

    **覆る条件**: `_k_days_with_min_videos` が床を当てるようになったら、
    こちらも合わせること（**数え方は片方だけ動かさない**）。
    検査は `tests/test_per_day_views_group.py`。
    """
    out: dict[str, int] = collections.Counter()
    for vid, points in by_id.items():
        if views_at(points, target) is None:
            continue          # その時点の読みが無い本は、置いた数にも入れない
        out[published_at(points).date().isoformat()] += 1
    return dict(out)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="公開日ごとの「1本あたりの再生」")
    ap.add_argument("--hours", type=float, default=24.0,
                    help="何時間時点で比べるか（既定 24）")
    ap.add_argument("--min-views", type=int, default=DEFAULT_MIN_VIEWS,
                    help=f"これ未満は長尺とみなして外す（既定 {DEFAULT_MIN_VIEWS}）")
    ap.add_argument("--group", default="",
                    help="本数で括って中央値を比べる。例 1-2,3-6,7-99")
    args = ap.parse_args(argv)

    by_id = _load()
    days = per_day(by_id, target=args.hours, min_views=args.min_views)
    placed = placed_per_day(by_id, target=args.hours)
    if not days:
        print("[per_day] 読める点がありません。")
        return 1

    print(f"=== 公開日べつ 1本あたりの再生（{args.hours:.0f}時間時点・"
          f"{args.min_views}再生未満は長尺として除外）===")
    print("  **置いた** は、その日に置いた本の数（床を当てない）。"
          "**下の段は、この数で括ります。**")
    for day in sorted(days):
        vals = sorted(days[day], reverse=True)
        print(f"  {day}  置いた {placed.get(day, 0):>3}本 / 生きた {len(vals):>3}本"
              f"  中央 {statistics.median(vals):>7.0f}   {vals}")

    if not args.group:
        return 0

    print("\n=== 本数の段べつ（**M14 の物差し。2割以上の下げが上限の合図**）===")
    print("  **括るのは「置いた本数」です**（`src/watches.py` の"
          " `_k_days_with_min_videos` と同じ数え方。"
          "生きた本数で括ると、門が『満ちました』と言う日がこの表に現れません）。")
    bands = []
    for spec in args.group.split(","):
        lo, hi = (int(x) for x in spec.split("-"))
        hit = [d for d in days if lo <= placed.get(d, 0) <= hi]
        vals = [v for d in hit for v in days[d]]
        n_days = len(hit)
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
