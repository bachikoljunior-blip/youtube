"""**1本あたりの再生が落ちたとき、「中身の版」と「公開した日」を切り分ける。**

    python scripts/per_video_why.py                 # 既定
    python scripts/per_video_why.py --cut 2026-08-25 # 「いつから落ちたか」を指定

**API 0単位**（`data/views.jsonl` と `data/batch_runs.jsonl` だけを読みます）。

## なぜ要るか（2026-08-28 に、この道具が無くて1度 外しかけた）

オーナーの問い「**1,2日間の動画前より再生数少ないのはなんで？**」に答えようとした
とき、手元にあった道具は `scripts/per_day_views.py` **1つだけ**で、あれは
**公開日でしか括れません。** ところが公開日は、**中身の版とは別の軸**です ——
この機械は本を作ってから**何日も後**に公開するので、
**同じバッチで作った本が、6日にわたって公開されます。**

実測（2026-08-28）: **08-19 に作った 43本**が 08-19 から 08-27 まで公開され、

    公開 08-19  中央 1172        公開 08-25  中央  201
    公開 08-20  中央  377        公開 08-26  中央  134
    公開 08-21  中央  279        公開 08-27  中央  150

**中身は同じバッチです。** それでも公開日で **8.7倍** ちがいます。
つまり「1本あたりが落ちたのは、作り方を変えたせいだ」という読みは、
**この表を見ないかぎり確かめられません。**

そのとき実際に疑われていたのは「1バッチ全部が同じ配色」と
「図が完成した最後の1〜2秒しか映らない」の2件で、どちらも 08-27〜08-28 に
直っています。**しかし上の 43本 は、その2件を**両方とも持ったまま**
高い側（1172）にも低い側（134）にも居ます。** だから
**あの2件では、この落ち方を説明できません。**
「08-29 以降の本で切り分ける」という段取りは、**もう手元にある表で
片が付いていた**（＝ その待ちは要らなかった）ことになります。

## 何を見ているか（**写した定数を持ちません**）

- **帯（その日の「生きる」本）は `src/day_cap.py` から引きます** ——
  `cap()` と `MIN_GAP_MIN` は**実測から動く数**なので、
  ここに `08:59〜13:30` や `10本` と書くと、動いた日にこの道具だけが古びます
  （`src/density_verdict.live_band` が同じ理由で 2026-08-26 に直っています）
- **齢をそろえます。** 既定は「齢 20〜120時間 の最初の読み」。
  24h → 72h の伸びは実測 **中央 x1.00**（この道具が毎回 測り直して印字します）
  なので、この幅の中ならどの読みでも比べられます
- **落とした本を必ず数えて出します**（下の「なぜ数えるか」）

## なぜ「落とした本」を数えるか（**ここで1度 外しかけた**）

`per_day_views.py` は本を**2か所で黙って落とします**:

    (1) `--min-views 10` 未満 ＝「長尺とみなす」    → **死んだ本が消えます**
    (2) 齢 24h ±35% に読みが無い                  → **その日の一部しか残りません**

(2) の実害（2026-08-28 実測）: **08-25 は帯内 10本 のうち 3本**にしか
24h の読みが無く、`per_day_views.py` は「**3本 中央 226**」と出します。
**7本 落ちたことは、どこにも出ません。** たまたま 48h まで広げた中央値も
**220** だったので結論は変わりませんでしたが、**それは運です。**
この道具は、読めた本と落ちた本を**必ず並べて**出します。
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
BATCH = ROOT / "data" / "batch_runs.jsonl"

#: 齢をそろえる幅。24h → 72h の伸びが x1.00 なので、この中ならどれでも比べられる。
#: **この2つが正しいかを、走るたびに `growth()` が測り直して印字します。**
AGE_LO, AGE_HI = 20.0, 120.0


def load_points(path: Path | None = None) -> dict[str, list[tuple[float, int, datetime]]]:
    """`data/views.jsonl` → 動画ID ごとの (齢, 再生, 読んだ時刻)。"""
    path = path or VIEWS
    by: dict[str, list[tuple[float, int, datetime]]] = collections.defaultdict(list)
    if not path.exists():
        return {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            at = datetime.fromisoformat(str(row["at"]).replace("Z", "+00:00"))
            by[row["id"]].append((float(row["hours"]), int(row["views"]), at))
        except (ValueError, KeyError, TypeError):
            continue
    return by


def published_at(points) -> datetime:
    """公開時刻を `at - hours` の**中央値**で復元する（読みごとの丸めを均す）。"""
    ests = sorted(p[2] - timedelta(hours=p[0]) for p in points)
    return ests[len(ests) // 2].astimezone(JST)


def aligned(points, lo: float = AGE_LO, hi: float = AGE_HI) -> int | None:
    """齢 `lo`〜`hi` の**最初の**読み。無ければ `None`（**黙って捨てない**）。"""
    for hours, views, _at in sorted(points):
        if lo <= hours <= hi:
            return views
    return None


def growth(by, lo: float = 24.0, hi: float = 72.0) -> tuple[int, float]:
    """`lo` 時間 → `hi` 時間 の伸び（本数, 中央）。**齢をそろえてよい根拠。**"""
    def near(points, target, tol=0.35):
        best = None
        for h, v, _ in sorted(points):
            if not (1 - tol) * target <= h <= (1 + tol) * target:
                continue
            if best is None or abs(h - target) < abs(best[0] - target):
                best = (h, v)
        return best

    ratios = []
    for points in by.values():
        a, b = near(points, lo), near(points, hi)
        if a and b and a[1] >= 5:
            ratios.append(b[1] / a[1])
    return len(ratios), (statistics.median(ratios) if ratios else float("nan"))


def band_params() -> tuple[int, float, str, bool]:
    """`src/day_cap.py` から (C, 間隔, 窓の右端 T, 切り分けたか) を引く。

    **写しません** —— どれも実測で動きます。`window()` が `confounded=True`
    のあいだは、**どちらのモデルが正しいか決まっていない**ので、
    この道具は帯を1つに決めず、**両方の中央値を並べて出します**。
    """
    try:
        from src import day_cap
        w = day_cap.window()
        return (day_cap.cap(), day_cap.MIN_GAP_MIN,
                str(w.get("T") or "13:30"), not w.get("confounded", True))
    except Exception:                                        # noqa: BLE001
        return 10, 30.0, "13:30", False


def _spaced(rows: list[tuple[datetime, str]], gap_min: float) -> list[tuple[datetime, str]]:
    """早い順に見て、前に残した本から `gap_min` 未満のものを落とす（`day_cap` の1段目）。"""
    kept: list[tuple[datetime, str]] = []
    for when, vid in sorted(rows):
        if not kept or (when - kept[-1][0]).total_seconds() / 60.0 >= gap_min - 1.0:
            kept.append((when, vid))
    return kept


def band_of_day(rows: list[tuple[datetime, str]], model: str,
                cap_n: int, gap_min: float, edge: str) -> list[str]:
    """その日の「生きる帯」に入る動画ID。**`src/day_cap.py` の2つのモデル。**

        model="count"   間隔で残ったうちの**先頭 `cap_n` 本**
        model="window"  間隔で残ったうちの **`edge` までに出した本 全部**

    **2026-08-28 に、片方だけで出して1度 外しかけました。** 08-27 は
    05:00〜08:30 に 8本 出しており（どれも0再生）、`count` はその 8本 を
    帯に入れて中央値 **0**、`window` は 08:59 以降を採って **199** を出します。
    **どちらが正しいかは決まっていません**（`window()` が `confounded`）。
    **片方だけを印字すると、決まっていないことを決まったように見せます。**
    """
    kept = _spaced(rows, gap_min)
    if model == "count":
        return [vid for _w, vid in kept[:cap_n]]
    hh, mm = (int(x) for x in edge.split(":"))
    return [vid for w, vid in kept if (w.hour, w.minute) <= (hh, mm)]


def build_dates(path: Path | None = None) -> tuple[dict[str, datetime], dict[str, str]]:
    """`data/batch_runs.jsonl` → 動画ID ごとの (作った時刻, テーマID)。"""
    path = path or BATCH
    built: dict[str, datetime] = {}
    topic: dict[str, str] = {}
    if not path.exists():
        return built, topic
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            at = datetime.fromisoformat(row["at"]).astimezone(JST)
        except (ValueError, KeyError, TypeError):
            continue
        for res in row.get("results", []):
            vid = res.get("video_id")
            if vid:
                built[vid] = at
                topic[vid] = res.get("topic", "")
    return built, topic


def family(topic_id: str) -> str:
    """テーマID → 制度の族（`s-nenkin-...` → `nenkin`）。"""
    parts = (topic_id or "").split("-")
    return parts[1] if len(parts) > 1 else (parts[0] if parts else "?")


def collect(by, built, topic, since: str, model: str,
            cap_n: int, gap_min: float, edge: str):
    """帯内の本だけを (公開日, 作った日, 族, 再生 or None) にして返す。"""
    per_day: dict[str, list[tuple[datetime, str]]] = collections.defaultdict(list)
    for vid, points in by.items():
        when = published_at(points)
        per_day[when.date().isoformat()].append((when, vid))

    rows = []
    for day, entries in per_day.items():
        if day < since:
            continue
        for vid in band_of_day(entries, model, cap_n, gap_min, edge):
            b = built.get(vid)
            rows.append({
                "day": day,
                "vid": vid,
                "built": b.date().isoformat() if b else None,
                "fam": family(topic.get(vid, "")) if vid in topic else None,
                "views": aligned(by[vid]),
            })
    return rows


def _med(vals):
    return statistics.median(vals) if vals else float("nan")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="1本あたり再生の落ち方を、中身の版と公開日に切り分ける")
    ap.add_argument("--since", default="2026-08-18", help="この日以降の公開だけを見る")
    ap.add_argument("--cut", default="", help="「落ちた」境目の日（族の入れ替わりを前後で比べる）")
    ap.add_argument("--model", default="window", choices=("window", "count"),
                    help="下の表で使う帯（既定 window）。**上の表は必ず両方 出します**")
    args = ap.parse_args(argv)

    by = load_points()
    if not by:
        print("[why] data/views.jsonl が読めません。")
        return 1
    built, topic = build_dates()
    cap_n, gap_min, edge, decided = band_params()

    n, ratio = growth(by)
    print(f"=== 齢をそろえてよいか（24h → 72h の伸び・n={n}）: **中央 x{ratio:.2f}** ===")
    print(f"  x1 に近いので、齢 {AGE_LO:.0f}〜{AGE_HI:.0f}h の最初の読みで比べます。"
          f"**1.2 を超えたら、この道具の前提が崩れています**")

    print(f"\n=== 公開日べつ 1本あたり再生（齢そろえ・**帯は2つのモデルを両方**）===")
    print(f"  (A) 本数 ＝ 間隔で残った先頭 {cap_n}本   "
          f"(B) 窓 ＝ {edge} までに出した本 全部")
    if not decided:
        print("  **どちらが正しいかは、まだ決まっていません**"
              "（`day_cap.window()` が `confounded`）。**片方だけを読まないこと**")
    both = {}
    for model in ("count", "window"):
        rows_m = collect(by, built, topic, args.since, model, cap_n, gap_min, edge)
        d = collections.defaultdict(list)
        for r in rows_m:
            d[r["day"]].append(r)
        both[model] = d
    print("\n  公開日        (A)本数 中央 (n/落)    (B)窓 中央 (n/落)   食い違い")
    for day in sorted(set(both["count"]) | set(both["window"])):
        line = f"  {day}  "
        meds = {}
        for model in ("count", "window"):
            rs = both[model].get(day, [])
            got = [r["views"] for r in rs if r["views"] is not None]
            meds[model] = _med(got)
            miss = len(rs) - len(got)
            cell = f"{_med(got):>7.0f} ({len(got)}/{miss})"
            line += f"{cell:>20}"
        a, b = meds["count"], meds["window"]
        if a == a and b == b:                       # NaN でない
            worse, better = min(a, b), max(a, b)
            gap = "同じ" if abs(a - b) < 1e-9 else (
                f"**x{better / worse:.1f}**" if worse > 0 else "**片方が 0**")
        else:
            gap = "—"
        print(line + f"   {gap}")
    print("  （`n/落` ＝ 読めた本 / **齢の合う読みが無くて落とした本**。"
          "落ちた本は黙って消しません）")

    rows = collect(by, built, topic, args.since, args.model, cap_n, gap_min, edge)
    if not rows:
        print("[why] 帯に入る本がありません。")
        return 1
    print(f"\n  ↓ ここから下は **(B) {args.model}** の帯で読みます"
          f"（`--model` で替えられます）")
    days = collections.defaultdict(list)
    for r in rows:
        days[r["day"]].append(r)

    print("\n=== 作った日 × 公開日（**中身の版と、公開の日を切り分ける**）===")
    cell = collections.defaultdict(list)
    for r in rows:
        if r["built"] and r["views"] is not None:
            cell[(r["built"], r["day"])].append(r["views"])
    bs = sorted({b for b, _ in cell})
    ps = sorted({p for _, p in cell})
    if not cell:
        print("  作った日の分かる本がありません（`data/batch_runs.jsonl` に控えなし）")
    else:
        print("  作った日  \\  公開日 " + " ".join(f"{p[5:]:>9}" for p in ps))
        for b in bs:
            line = f"  {b} "
            for p in ps:
                vs = cell.get((b, p))
                line += f"{(f'{_med(vs):.0f}/{len(vs)}' if vs else '·'):>10}"
            print(line)
        print("  （読み: `中央/本数`。**横に読むと「同じ中身が、公開日でどう変わったか」**）")

    # 同じバッチが複数の日に公開されている所を名指しする ＝ 中身を固定した比較
    print("\n=== 同じバッチが、公開日でどれだけ変わったか（**中身は固定**）===")
    found = False
    for b in bs:
        spread = {p: cell[(b, p)] for p in ps if cell.get((b, p))}
        if len(spread) < 2:
            continue
        found = True
        meds = {p: _med(v) for p, v in spread.items()}
        best, worst = max(meds.values()), min(meds.values())
        print(f"  作 {b}: " + "  ".join(f"{p[5:]}:{meds[p]:.0f}({len(spread[p])}本)"
                                        for p in sorted(spread)))
        if worst > 0:
            print(f"    → **同じ中身で {best / worst:.1f}倍** の開き。"
                  f"この開きは、作り方の変更では説明できません")
    if not found:
        print("  複数の日にまたがったバッチがありません（切り分けられません）")

    if args.cut:
        print(f"\n=== 族の入れ替わり（{args.cut} の前後）===")
        before = collections.defaultdict(list)
        after = collections.defaultdict(list)
        for r in rows:
            if r["views"] is None or not r["fam"]:
                continue
            (after if r["day"] >= args.cut else before)[r["fam"]].append(r["views"])
        crossing = sorted(set(before) & set(after))
        ratios, solid = [], []
        for f in crossing:
            mb, ma = _med(before[f]), _med(after[f])
            nb, na = len(before[f]), len(after[f])
            thin = "" if nb >= 2 and na >= 2 else "  ← **片側1本。比を読まない**"
            if mb:
                ratios.append(ma / mb)
                if nb >= 2 and na >= 2:
                    solid.append(ma / mb)
            print(f"  {f:<14} 前 {mb:>6.0f}(n={nb})   "
                  f"後 {ma:>6.0f}(n={na})   x{ma / mb if mb else float('nan'):.2f}{thin}")
        if ratios:
            print(f"  → またぐ族 {len(crossing)}件 ぜんぶ: 比の中央 x{_med(ratios):.2f}"
                  f"（**片側1本の族が {len(ratios) - len(solid)}件 混ざっています**）")
        if solid:
            print(f"  → **両側 2本以上 の族 {len(solid)}件 だけ: 比の中央 x{_med(solid):.2f}**"
                  "  ← 族を固定して残る落ち幅は、こちらで読むこと")
        else:
            print("  → **両側 2本以上 の族が 0件。族を固定した比較は、まだできません。**"
                  "ここから「族では説明できない」と読まないこと")
        ob = [v for f in before if f not in after for v in before[f]]
        oa = [v for f in after if f not in before for v in after[f]]
        if ob and oa:
            print(f"  前だけの族 {len(ob)}本 中央 {_med(ob):.0f}   "
                  f"後だけの族 {len(oa)}本 中央 {_med(oa):.0f}   "
                  f"→ 入れ替わりぶん **x{_med(oa) / _med(ob):.2f}**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
