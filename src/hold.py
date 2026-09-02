"""**次の1本の再生を「同じ日の中で」当てるのは何か —— 維持率（見続けさせる側）か、族か、公開日か。**（API 0単位。貯めの補充だけ Analytics）

    python -m src.hold            # 画面（`run_marker.py --write` の `[きょうの1本]` の中に同じ塊が出る）
    python -m src.hold --no-fetch # 貯め（`data/retention.json`）を補充しない

## なぜ要るか（2026-09-03 01:xx JST・最適化の回。「最適化されてんの？（過去の実行に対して）」→ いいえ）

規則（1日1本）の下で、回が目標に触れる手は **次に出る1本を良くする（`improve`）** だけです。
その `improve` が何を良くしてきたかを `data/runs.jsonl` で数えると、15件 全部が
**読み（発音）・題への制度名・段の説明** —— **どれも「再生を当てる数字」を持っていませんでした。**
当てどころが無いまま磨いた結果は、`data/views.jsonl` に出ています:
同じ日に出た本の中で、何が抜けるかを誰も測っていなかった。

この回に自分で撃った数（`data/retention.json` 132本 × `data/views.jsonl`・齢48h・ショート）:

    同じ日の中の順位（日で割った残差）を当てるもの
      維持率 audienceWatchRatio 15%/30%/50%点
        repo の残差（`aged_views` の JST 公開日・同じ形）   ρ=+0.11／+0.13／+0.04（n=117・門 0.18）← 雑音
        控えの `at`（UTC）で日を切った log 残差            ρ=+0.24／+0.25／+0.24（n=114・門 0.18）← 縁
        **＝ 割り方で門の上下を行き来する ＝ 当てるとしても ×1.5 の幅。**
      族（`calc`）の順位              ρ=+0.10（n=185・門 0.14）  ← 雑音（`daily_pick.family_loo`）
    日そのもの（同じ中身が、公開した日で）  ×23（08-19 作の 43本: 08-19 1,172回 → 08-31 51回・`per_video_why.py`）
      その間 avg% viewed は 56% → 60〜95%（Analytics `day,creatorContentType`・08-18→08-30）
      ＝ **維持率は落ちていない。配信（チャンネルの状態）が落ちた。** 1本/日 に戻した 09/01 以降も
      日の中央値は 08/30 131回・08/31 121回・09/02 112回（13h）で、戻っていません

**＝ 回が触れる側（中身）には、次の1本の再生を当てる数字が1つも無い。**
日の側（配信）は ×23 で、**中身をどう磨いても届きません。** だから画面は、
(1) 中身の `improve` は `verify` が通る所で止めろと書き、(2) 日の側（1本/日 で日の中央値が戻るか・
公開時刻の掃き・外の帯と作りが違う点を1つ 入れる）へ残りの時間を向け、(3) その ρ と日の揺れを
**毎周 数え直して**出します（定数は無い）。
**「読みを直した」「題に制度名を入れた」は、この画面の数字を1つも動かしません。**

## 覆る条件

- 維持率の ρ が門を越える日が続いたら（1本/日 で日の差が消えれば、越えうる）、画面は自分で
  「当てどころはこの区間」に切り替わります（`lines()` の `sig`）。定数は無い。
- 日の中央値の最大／最小（同じ形・5本以上の日）が ×2 を切ったら、配信は揺れていない。
  そのとき初めて、生の再生で中身を比べてよい（`daily_pick._attach_residual` の覆る条件と同じ）。
- `relativeRetentionPerformance`（YouTube の相対値）のほうが ρ が高くなったら、そちらへ替える
  （`curves()` の列 2）。
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RETENTION = ROOT / "data" / "retention.json"
QUEUE = ROOT / "data" / "critique_queue"

#: 当てる点（動画の何%の位置か）。15% ＝ 中央カーブが 1.10 から落ち始める位置、50% ＝ 半分。
POINTS = (0.15, 0.30, 0.50)
#: 中央カーブを画面に出す点。
CURVE_POINTS = (0.05, 0.15, 0.30, 0.50, 0.70, 0.90)
#: 1回の `--write` で貯めに足す本数の上限（Analytics の枠。Data API の日枠とは別）。
FETCH_MAX = 6


def curves(path: Path | None = None) -> dict[str, list]:
    """`data/retention.json`（`scripts/retention.py` が貯める）。`{id: [[x, watch, relative], ...]}`。"""
    p = path or RETENTION
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


def at(curve: list, x: float, col: int = 1) -> float | None:
    """カーブの位置 `x`（0〜1）の値。無ければ `None`。"""
    best = None
    for pt in curve:
        try:
            if abs(float(pt[0]) - x) < 0.006:
                best = float(pt[col])
                break
        except (TypeError, ValueError, IndexError):
            continue
    return best


def predictor(rows: list[dict], cv: dict[str, list], *, form: str = "ショート",
              points: tuple[float, ...] = POINTS, key: str = "res") -> dict:
    """点ごとの Spearman ρ（維持率 × 日で割った残差）。`{x: {"rho", "n", "gate"}}`。

    `rows` は `daily_pick.aged_views()` の行（`res` 付き）。**同じ日に 2本以上** の本だけ
    （1本の日は残差が必ず 1.0 で、順位が無い）。
    """
    from .daily_pick import _spearman                          # noqa: PLC0415
    per_day: dict = defaultdict(int)
    for r in rows:
        if r.get("form") == form:
            per_day[r["pub"]] += 1
    out = {}
    for x in points:
        xs, ys = [], []
        for r in rows:
            if r.get("form") != form or r.get(key) is None or per_day[r["pub"]] < 2:
                continue
            c = cv.get(r["video_id"])
            v = at(c, x) if c else None
            if v is None:
                continue
            xs.append(v)
            ys.append(float(r[key]))
        n = len(xs)
        out[x] = {"rho": _spearman(xs, ys), "n": n, "gate": (1.96 / n ** 0.5) if n else None}
    return out


def median_curve(cv: dict[str, list], ids: set[str] | None = None,
                 points: tuple[float, ...] = CURVE_POINTS) -> dict[float, float | None]:
    vals: dict[float, list[float]] = defaultdict(list)
    for vid, c in cv.items():
        if ids is not None and vid not in ids:
            continue
        for x in points:
            v = at(c, x)
            if v is not None:
                vals[x].append(v)
    return {x: (statistics.median(vals[x]) if vals[x] else None) for x in points}


def day_spread(rows: list[dict], *, form: str = "ショート", min_n: int = 5) -> dict:
    """日の中央値の最大／最小（同じ形・`min_n` 本以上の日）。配信の揺れの大きさ。"""
    by_day: dict = defaultdict(list)
    for r in rows:
        if r.get("form") == form:
            by_day[r["pub"]].append(int(r["views"]))
    med = {d: statistics.median(v) for d, v in by_day.items() if len(v) >= min_n}
    if not med:
        return {"n_days": 0}
    hi = max(med, key=med.get)
    lo = min(med, key=med.get)
    return {"n_days": len(med), "hi": (hi, med[hi]), "lo": (lo, med[lo]),
            "ratio": (med[hi] + 1) / (med[lo] + 1),
            "recent": sorted(med.items())[-4:]}


def recent_with_curves(rows: list[dict], cv: dict[str, list], *, form: str = "ショート",
                       k: int = 3) -> list[dict]:
    """公開が新しい順に、カーブの在る本を `k` 本（その本の 50%点と 48h 再生）。"""
    got = [r for r in rows if r.get("form") == form and r["video_id"] in cv]
    got.sort(key=lambda r: (r["pub"], r["video_id"]), reverse=True)
    out = []
    for r in got[:k]:
        c = cv[r["video_id"]]
        out.append({"video_id": r["video_id"], "pub": r["pub"], "views": r["views"],
                    "p15": at(c, 0.15), "p50": at(c, 0.50), "res": r.get("res")})
    return out


def missing_recent(rows: list[dict], cv: dict[str, list], *, form: str = "ショート",
                   max_n: int = FETCH_MAX) -> list[str]:
    """カーブがまだ無い、公開が新しい順の本（齢 48h 以上は `rows` に入っている本だけ）。"""
    got = [r for r in rows if r.get("form") == form and r["video_id"] not in cv]
    got.sort(key=lambda r: (r["pub"], r["video_id"]), reverse=True)
    return [r["video_id"] for r in got[:max_n]]


def refresh(rows: list[dict], cv: dict[str, list], *, path: Path | None = None,
            max_n: int = FETCH_MAX, fetch=None) -> int:
    """貯めに無い新しい本のカーブを、最大 `max_n` 本だけ引いて貯める（Analytics。Data API の日枠は 0）。

    `scripts/retention.py` は走査（`data/scan.jsonl`）に載った本しか引かず、走査は
    2026-08-27 以降 尺を持たないので、**新しい本のカーブは誰も引いていませんでした**
    （この回の実測: 貯め 132本 のうち 08-31 以降の本 0本）。ここで毎周 少しずつ埋めます。
    """
    ids = missing_recent(rows, cv, max_n=max_n)
    if not ids:
        return 0
    if fetch is None:
        try:
            from .analytics import fetch_retention as fetch   # noqa: PLC0415
        except Exception:                                      # noqa: BLE001
            return 0
    added = 0
    for vid in ids:
        try:
            got = fetch(vid)
        except Exception:                                      # noqa: BLE001
            break
        if got:
            cv[vid] = [list(x) for x in got]
            added += 1
    if added:
        p = path or RETENTION
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(cv, ensure_ascii=False), encoding="utf-8")
        except OSError:
            pass
    return added


def _segments_of(video_id: str | None, queue: Path | None = None) -> list[str]:
    """その本の読み上げ（`data/critique_queue/<ID>.json` の `narration`）。無ければ空。"""
    if not video_id:
        return []
    p = (queue or QUEUE) / f"{video_id}.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
        return [str(s) for s in d.get("narration") or []]
    except (OSError, json.JSONDecodeError, AttributeError):
        return []


def drop_window(mc: dict[float, float | None]) -> tuple[float, float] | None:
    """中央カーブで**いちばん多く去る区間**（隣り合う点の差が最大の所）。"""
    pts = [(x, v) for x, v in sorted(mc.items()) if v is not None]
    if len(pts) < 2:
        return None
    best = max(range(1, len(pts)), key=lambda i: pts[i - 1][1] - pts[i][1])
    return pts[best - 1][0], pts[best][0]


def _fx(v: float | None) -> str:
    return "—" if v is None else f"{v:.2f}"


def lines(rows: list[dict], next_row: dict | None = None, *, cv: dict[str, list] | None = None,
          fetch: bool = False, retention_path: Path | None = None,
          queue: Path | None = None, form: str = "ショート") -> list[str]:
    """`[きょうの1本]` の中に出る塊。**当てる数字と、当てどころ（次の本のどの段か）まで。**"""
    cv = curves(retention_path) if cv is None else cv
    added = 0
    if fetch and not os.environ.get("HOLD_NO_FETCH"):
        added = refresh(rows, cv, path=retention_path)
    pr = predictor(rows, cv, form=form)
    sp = day_spread(rows, form=form)
    ids = {r["video_id"] for r in rows if r.get("form") == form}
    mc = median_curve(cv, ids)
    out = []
    sig = [x for x, d in pr.items() if d["rho"] is not None and d["gate"] and abs(d["rho"]) > d["gate"]]
    parts = " ／ ".join(
        f"{int(x * 100)}%点 ρ={d['rho']:+.2f}" if d["rho"] is not None else f"{int(x * 100)}%点 —"
        for x, d in pr.items())
    n0 = next(iter(pr.values()), {}).get("n", 0)
    g0 = next(iter(pr.values()), {}).get("gate")
    out.append("     何が次の1本を当てるか（同じ日の中の順位・日で割った残差・Spearman・API 0単位）: "
               f"**維持率**（audienceWatchRatio）{parts}（n={n0}・門 {g0:.2f}・"
               f"{'**有意**' if sig else '**雑音**'}）"
               + (f"　＋ 貯めに {added}本 足した" if added else ""))
    if sp.get("n_days"):
        hi, lo = sp["hi"], sp["lo"]
        rec = "・".join(f"{d:%m/%d} {int(m)}回" for d, m in sp["recent"])
        out.append(f"     **公開した日そのもの**: 日の中央値は 最大 {hi[0]:%m/%d} {int(hi[1])}回 ／ "
                   f"最小 {lo[0]:%m/%d} {int(lo[1])}回 ＝ **×{sp['ratio']:.0f}**（{sp['n_days']}日・5本以上の日）"
                   f"　直近: {rec}")
    if any(v is not None for v in mc.values()):
        cur = " → ".join(f"{int(x * 100)}%:{_fx(v)}" for x, v in mc.items())
        dw = drop_window(mc)
        out.append(f"     ショート {len(ids & set(cv))}本 の中央カーブ（先頭を 1 とした残り）: {cur}"
                   + (f"　＝ **{int(dw[0] * 100)}%〜{int(dw[1] * 100)}% の間にいちばん去る**" if dw else ""))
        if dw and sig:
            out.append("     → **`improve` の当てどころは、この区間で見続けさせること**（コマの切り替え・"
                       "言い切りの位置・数字の出る順）。**読みの直し・題の言い換えは、上の ρ を持っていません**"
                       "（当たる数字が無い手に時間を使わないこと）")
        elif not sig:
            out.append("     → 維持率は門の下 ＝ **中身の側に、次の1本の再生を当てる数字がありません**"
                       "（族も雑音・上の行）。**読みの直し・題の言い換え・段の説明を足す `improve` は、"
                       "どの数字も動かしません** —— 中身は `verify` が通る所で止め、残りの時間は"
                       "日の側へ: (1) 1本/日 で日の中央値が戻るか（上の直近）を毎周 見る "
                       "(2) 公開時刻の掃き（`src/publish_hour.sweep_hour`）を続ける "
                       "(3) 外の帯の上位（`niche_ceiling.py --form short`）と**作りが違う点**を1つ、次の1本に入れる"
                       "（同じ作りの中で磨いても ×1 ／ 作りを変えた1本だけが ×10 を試せる）")
        if dw and next_row:
            segs = _segments_of(next_row.get("video_id"), queue)
            if segs:
                k = len(segs)
                a = max(0, int(dw[0] * k))
                b = min(k, int(dw[1] * k + 0.999))
                tgt = segs[a:b] or segs[:1]
                out.append(f"     次に出る本 `{next_row.get('video_id')}`（{k}段）でその区間に当たる段: "
                           + " ／ ".join(f"{a + i + 1}「{s[:22]}」" for i, s in enumerate(tgt)))
    rc = recent_with_curves(rows, cv, form=form)
    if rc:
        out.append("     直近の公開ずみショート（カーブ在り）: "
                   + " ／ ".join(f"`{r['video_id']}` {r['pub']:%m/%d} 15%:{_fx(r['p15'])} 50%:{_fx(r['p50'])}"
                                 f" {r['views']}回（残差 ×{(r['res'] or 0):.2f}）" for r in rc))
    return out


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--no-fetch", action="store_true")
    a = ap.parse_args(argv)
    from . import daily_pick, next_slot                       # noqa: PLC0415
    rows = daily_pick.aged_views()
    nxt = next_slot.next_video() or (next_slot.drafts() or [None])[0]
    pk = next_slot.picked_row()
    for ln in lines(rows, pk or nxt, fetch=not a.no_fetch):
        print(ln)
    return 0


if __name__ == "__main__":
    sys.exit(main())
