#!/usr/bin/env python3
"""**「最適化されてんの？（過去の実行に対して）」の数を、1発で出す。**（API 0単位・数秒）

    python scripts/optimized.py            # 直近 5日
    python scripts/optimized.py --days 3

## なぜ要るか（2026-09-03 05:5x・最適化の回）

09/02 17:3x〜09/03 05:3x の **12時間で最適化の回が 17回** 立ち、17回とも同じ問いに
「いいえ」と答え、**毎回 一から `runs.jsonl`／`eta.jsonl`／`git log` を数え直していました**
（1回あたり 5〜10分・Fable の effort 最大）。数は毎回ほぼ同じで（ship の 7割が `fix`・
`--moves` は 99% が 0・到達日は 08/20 から出ていない）、違ったのは名指しした欠陥だけ。
**数える時間が、主実行に触る時間を食っていました。**

この道具は「数」だけを出します。**答え（はい／いいえ）と名指しは出しません** ——
それは、その回が実物を見て言うものです。ここに結論を書いた瞬間、書き置きになります。

## 見るもの

- `data/runs.jsonl`   ship の種別・腕・`moves` の分布（日別）
- `data/eta.jsonl`    `target_date` が最後に出た日／再生・登録の実測の推移
- `data/views.jsonl`  1日1本の規則の下で出た本の、齢24h／48h の再生（形べつ）
- `data/daily_pick.jsonl`  決めてある「その日の1本」

**覆る条件**: 最適化の回が問いに答え終えて、`docs/spawn_prompt.md` の optimizer の型から
「過去の回を数える」が消えたら、この道具は要りません。消してよい。
"""
from __future__ import annotations

import argparse
import collections
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
JST = timezone(timedelta(hours=9))


def _jsonl(p: Path) -> list[dict]:
    out = []
    try:
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if ln:
                try:
                    out.append(json.loads(ln))
                except json.JSONDecodeError:
                    pass
    except OSError:
        pass
    return out


def ships(days: int) -> list[str]:
    runs = _jsonl(ROOT / "data" / "runs.jsonl")
    since = (datetime.now(JST) - timedelta(days=days)).strftime("%Y-%m-%d")
    sh = [r for r in runs if r.get("kind") == "ship" and str(r.get("at", ""))[:10] >= since]
    out = [f"=== ship（直近 {days}日・{len(sh)}件・`data/runs.jsonl`）==="]
    by_day: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for r in sh:
        by_day[str(r.get("at", ""))[:10]][str(r.get("ship_kind") or "?")] += 1
    for d in sorted(by_day):
        c = by_day[d]
        tot = sum(c.values())
        parts = " ".join(f"{k} {v}" for k, v in c.most_common())
        out.append(f"  {d}  {tot:>3}件  {parts}")
    kinds = collections.Counter(str(r.get("ship_kind") or "?") for r in sh)
    if sh:
        fix = kinds.get("fix", 0)
        out.append(f"  種別: {' '.join(f'{k} {v}' for k, v in kinds.most_common())}"
                   f"  ← fix {fix / len(sh):.0%}")
    mv = collections.Counter(r.get("moves") for r in sh)
    nz = sum(v for k, v in mv.items() if k not in (0, None))
    out.append(f"  --moves: 0 が {mv.get(0, 0)}件・0 以外 {nz}件・未記入 {mv.get(None, 0)}件")
    optim = [r for r in sh if "最適化され" in str(r.get("what") or "")[:80]]
    if optim:
        out.append(f"  「最適化されてんの？」に答えた ship: {len(optim)}件"
                   f"（最初 {optim[0]['at'][5:16]}・最後 {optim[-1]['at'][5:16]}）")
    return out


def eta_trace() -> list[str]:
    rows = _jsonl(ROOT / "data" / "eta.jsonl")
    out = ["=== 到達日と実物（`data/eta.jsonl`）==="]
    last_target = None
    for r in rows:
        if r.get("target_date"):
            last_target = (str(r.get("at", ""))[:10], r["target_date"])
    if last_target:
        out.append(f"  `target_date` が最後に出た日: {last_target[0]}（そのときの日付 {last_target[1]}）")
    else:
        out.append("  `target_date` は一度も出ていません")
    by_day: dict[str, dict] = {}
    for r in rows:
        if r.get("views_per_day_7d") is not None:
            by_day[str(r.get("at", ""))[:10]] = r
    keys = sorted(by_day)
    for d in keys[-8:]:
        r = by_day[d]
        out.append(f"  {d}  再生/日(7d) {float(r.get('views_per_day_7d') or 0):>7,.0f}"
                   f"  1本あたり {float(r.get('per_video_now') or 0):>6,.0f}"
                   f"  登録 {r.get('subs_net')}  登録/日 {float(r.get('subs_per_day') or 0):.2f}")
    if len(keys) >= 2:
        a, b = by_day[keys[0]], by_day[keys[-1]]
        va, vb = float(a.get("views_per_day_7d") or 0), float(b.get("views_per_day_7d") or 0)
        peak_d = max(keys, key=lambda k: float(by_day[k].get("views_per_day_7d") or 0))
        vp = float(by_day[peak_d].get("views_per_day_7d") or 0)
        out.append(f"  再生/日(7d): 最大 {vp:,.0f}（{peak_d}）→ いま {vb:,.0f}"
                   f"（{(vb / vp - 1) if vp else 0:+.0%}）／ 最初の点 {keys[0]} {va:,.0f}")
    return out


def aged() -> list[str]:
    out = ["=== 齢24h／48h の再生（形べつ・`data/views.jsonl`・`daily_pick.aged_views`）==="]
    try:
        from src import daily_pick
    except Exception as exc:                                    # noqa: BLE001
        return out + [f"  読めません: {str(exc)[:80]}"]
    for h in (24, 48):
        by: dict[str, list[int]] = collections.defaultdict(list)
        for r in daily_pick.aged_views(h):
            by[str(r.get("form"))].append(int(r.get("views") or 0))
        for f, vs in sorted(by.items()):
            vs.sort()
            out.append(f"  {h}h {f:<4} n={len(vs):>3}  中央値 {vs[len(vs) // 2]:>5}  上位 {vs[-3:]}")
    return out


def picks() -> list[str]:
    out = ["=== 決めてある「その日の1本」（`data/daily_pick.jsonl`）==="]
    rows = _jsonl(ROOT / "data" / "daily_pick.jsonl")
    last: dict[str, dict] = {}
    for r in rows:
        last[str(r.get("for_day"))] = r
    today = datetime.now(JST).date().isoformat()
    for d in sorted(last):
        if d < today:
            continue
        r = last[d]
        hour = ""
        try:
            from src import publish_hour
            from datetime import date
            hour = f"{publish_hour.place_hour(date.fromisoformat(d))}時"
        except Exception:                                      # noqa: BLE001
            pass
        out.append(f"  {d} {hour} {r.get('form')} {r.get('topic')} {r.get('video_id') or ''}")
    if len(out) == 1:
        out.append("  無し")
    return out


def git_touch(days: int) -> list[str]:
    out = [f"=== git（直近 {days}日・commit が触った場所）==="]
    try:
        log = subprocess.run(["git", "log", f"--since={days} days ago", "--name-only",
                              "--pretty=format:@@%h"], cwd=ROOT, capture_output=True,
                             text=True, timeout=30).stdout
    except Exception as exc:                                    # noqa: BLE001
        return out + [f"  読めません: {str(exc)[:80]}"]
    n_commit = 0
    top = collections.Counter()
    for ln in log.splitlines():
        if ln.startswith("@@"):
            n_commit += 1
        elif ln.strip():
            top[ln.split("/")[0]] += 1
    out.append(f"  commit {n_commit}件  触った場所: "
               + " ".join(f"{k} {v}" for k, v in top.most_common(8)))
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=5)
    a = ap.parse_args()
    for block in (ships(a.days), eta_trace(), aged(), picks(), git_touch(a.days)):
        print("\n".join(block))
        print()
    print("答え（はい／いいえ／部分的に）と名指しは、この数と実物を見て、その回が言うこと。ここには書かない。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
