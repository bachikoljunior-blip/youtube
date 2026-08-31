"""**「engaged 比率は、その日に出した本数が増えると下がる」を、公開ずみの日だけで判定する。**

    python -m src.density_engaged_verdict

## なぜ要るか（2026-09-01）

`config/hypotheses.yaml` の期限 2026-10-03 の前提です。
`falsified_if` は **2026-09-25〜09-26（1〜2本/日）に公開した本**と、
その前後7日のうち **9本以上/日** の日に公開した本を比べます。

**その日は来ません。** オーナーが 2026-08-31 に規則を固定しました
（`src/house_rule.py`・`CLAUDE.md` 冒頭）——**1日1本**。
09/25 以降、**9本以上/日 の日は二度と作れません。**
`scripts/deadline_check.py` の末尾がこの1件を名指ししています ——
「**規則（1日1本）の下では、期日までに満ちない要件**」。

`scripts/eta.py` は毎周「**軌跡の腕が動くのは前提を1件 閉じたときだけ**」と
印字しています。**閉じられない前提は、腕を永久に止めます。**

## なぜ「公開ずみの日」で解けるのか

`deadline_check.py` が挙げる直し方は2つ ——
**(1) 要件を 1日1本 で届く形へ書き直す ／ (2) すでに公開ずみの日で判定できるなら、いま閉じる。**

**この前提は (2) で解けます。** 比べたい2つの群は**過去に両方とも存在します**:

    2026-08-05〜08-18   1〜2本/日 の日が 11日（**規則が固定される前**）
    2026-08-20〜08-22   25本 / 32本 / 25本 の日     ← 9本以上/日

**そして両者は7日 以内に隣り合っています**（08/13〜08/18 と 08/20〜08/22）。
`falsified_if` が「前後7日で挟む」と言っている理由 —— 曜日とチャンネルの成長を
そろえること —— は、**この並びでそのまま満たせます。**

**帯（1〜2本/日 ／ 9本以上/日）も、前後7日 も、30再生以上5本 の床も、
1つも緩めていません。** 動かしたのは**どの日を使うか**だけです。

## 公開時刻は `data/views.jsonl` から引きます（`data/uploaded.jsonl` ではなく）

`data/uploaded.jsonl` の `at` は **08/16 より前が空**です（この控えは
その日から積み始めた）。**低密度の日は全部その前**にあるので、
あちらで数えると 1〜2本/日 の群が **2本**しか出ず、床（5本）に届きません。

`data/views.jsonl` は各行に `at`（読んだ時刻）と `hours`（そのときの齢）を持つので、
**`at - hours` が公開時刻**です。**いちばん古い読みから引きます** ——
新しい読みほど、`hours` の丸めが積みます。

## 数えない本

    engaged 比率は Analytics（`views` / `engagedViews`）。**Data API は1単位も使いません**
    再生 30回 未満の本は落とす（`length_verdict.MIN_VIEWS` と同じ理由 ——
      再生1回の本は `engagedViews` も 1 になり、比率 100% で中央値を持ち上げる）

## 覆る条件

**低密度の日が「規則の下で作られた日」に置き換わったら、こちらを使わないこと。**
2026-09-01 から規則は 1本/日 なので、**09/08 以降は「1〜2本/日 の日」が毎日 増えます。**
ただし**比べる相手（9本以上/日）は二度と増えません** —— だから
「前後7日」を満たす組は、**この 08月 の並びが最後**です。
"""
from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

JST = timezone(timedelta(hours=9))
ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"

#: `falsified_if` の帯。**1文字も緩めていません。**
LOW_MAX = 2         # 「1〜2本/日」
HIGH_MIN = 9        # 「9本以上/日」
WITHIN_DAYS = 7     # 「その前後7日」
MIN_VIEWS = 30      # 「30再生以上」
FLOOR = 5           # 「5本に満たなければ、期限だけを延ばす」


def born(path: Path | None = None) -> dict[str, datetime]:
    """**公開時刻**（`at - hours`）。いちばん古い読みから引きます。"""
    out: dict[str, datetime] = {}
    p = path or VIEWS
    for ln in p.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        vid, at, hours = row.get("id"), row.get("at"), row.get("hours")
        if not vid or not at or hours is None:
            continue
        try:
            t = (datetime.fromisoformat(str(at).replace("Z", "+00:00"))
                 - timedelta(hours=float(hours)))
        except (ValueError, TypeError):
            continue
        if vid not in out or t < out[vid]:
            out[vid] = t
    return out


def per_day(times: dict[str, datetime]) -> dict[date, list[str]]:
    """**公開日（JST）ごとの本**。母集団は「公開ずみの全部」を渡すこと。"""
    out: dict[date, list[str]] = defaultdict(list)
    for vid, t in times.items():
        out[t.astimezone(JST).date()].append(vid)
    return dict(out)


def groups(times: dict[str, datetime] | None = None, *,
           low_max: int = LOW_MAX, high_min: int = HIGH_MIN,
           within: int = WITHIN_DAYS) -> dict[str, Any]:
    """**低密度の群と、その前後 `within` 日の高密度の群**を返す。

    低密度の日は、**高密度の日と `within` 日 以内で隣り合っているものだけ**を採ります
    （`falsified_if` の「その前後7日のうち」）。孤立した低密度の日を混ぜると、
    曜日とチャンネルの成長が入ります —— それを避けるための条件です。
    """
    days = per_day(times if times is not None else born())
    low_days = sorted(d for d, ids in days.items() if len(ids) <= low_max)
    high_days = sorted(d for d, ids in days.items() if len(ids) >= high_min)
    paired_low = [d for d in low_days
                  if any(abs((d - h).days) <= within for h in high_days)]
    paired_high = [h for h in high_days
                   if any(abs((h - d).days) <= within for d in paired_low)]
    return {
        "days": days,
        "low_days": paired_low,
        "high_days": paired_high,
        "low_ids": [v for d in paired_low for v in days[d]],
        "high_ids": [v for d in paired_high for v in days[d]],
        "low_dropped": [d for d in low_days if d not in paired_low],
    }


def report(fetch=None) -> dict[str, Any]:
    """**判定**。`fetch(ids, start, end)` は Analytics（既定は `length_verdict`）。"""
    times = born()
    g = groups(times)
    if not g["low_ids"] or not g["high_ids"]:
        return {"decided": False, "why": "群が片方 空です", **g}
    if fetch is None:
        from .length_verdict import fetch_engaged as fetch
    ids = g["low_ids"] + g["high_ids"]
    # **窓の頭は、いちばん早い公開より 3日 前に置きます**（2026-09-01 に踏んだ）。
    # Analytics の暦日は PT なので、`min(公開)` の JST の暦日をそのまま渡すと
    # **その日の早い本が窓の外に落ちます** —— 実測: 頭を 08/13 にすると
    # 低密度の群が 6本 → **5本**、中央値が 19.8% → 20.9% へ動きました。
    # **群の大きさが窓の頭で動くなら、その判定は窓の産物です。**
    start = min(times[v] for v in ids).astimezone(JST).date() - timedelta(days=3)
    rows = fetch(ids, start, datetime.now(JST).date())
    ratio = {}
    for row in rows:
        vid, views = row.get("video"), row.get("views") or 0
        if vid and views >= MIN_VIEWS:
            ratio[vid] = (row.get("engagedViews") or 0) / views
    low = [ratio[v] for v in g["low_ids"] if v in ratio]
    high = [ratio[v] for v in g["high_ids"] if v in ratio]
    out_raw = {r["video"]: (r.get("views") or 0, r.get("engagedViews") or 0)
               for r in rows if r.get("video")}

    out: dict[str, Any] = {
        "low_days": g["low_days"], "high_days": g["high_days"],
        "low_dropped": g["low_dropped"],
        "n_low": len(low), "n_high": len(high),
        "median_low": statistics.median(low) if low else None,
        "median_high": statistics.median(high) if high else None,
    }
    if len(low) < FLOOR or len(high) < FLOOR:
        out.update(decided=False, extend=True,
                   why=f"30再生以上の本が {FLOOR}本 に満たない群があります"
                       f"（低 {len(low)} ／ 高 {len(high)}）——"
                       " `falsified_if` は「期限だけを延ばす」と言っています")
        return out
    from .ab_power import hit_rate, observed_ratios, rank_sum_p
    out.update(
        decided=True,
        # `falsified_if`:「**上回っていない**（同点も外れとみなす）」
        upheld=out["median_low"] > out["median_high"],
        p_one_sided=rank_sum_p(low, high),
        sweep=sweep(out_raw, g),
        # **見分けられたはずか。** `note` が言う効き（34.8% 対 19.4% ＝ ×1.79）を、
        # この本数で当てられる率。**低いなら「効きが無い」ではなく「測っていない」**
        # （`docs/JOURNAL.md` の「見分けられなかっただけの実験を閉じない」）。
        power_at_note_effect=hit_rate(observed_ratios(),
                                      min(len(low), len(high)), 1.79),
    )
    return out


def sweep(raw: dict[str, tuple[int, int]], g: dict[str, Any],
          lines: tuple[int, ...] = (1, 10, 30, 50, 100)) -> list[dict[str, Any]]:
    """**下限の再生数を振って、答えがその線の産物でないか見る。**

    `src/length_verdict.sweep()` と同じ考え方 ——
    「1つの線で出した答えは、その線の産物かもしれません。**振って同じなら、線のせいではない。**」
    """
    from .ab_power import rank_sum_p

    out = []
    for mv in lines:
        r = {v: e / n for v, (n, e) in raw.items() if n >= mv}
        lo = [r[v] for v in g["low_ids"] if v in r]
        hi = [r[v] for v in g["high_ids"] if v in r]
        out.append({
            "min_views": mv, "n_low": len(lo), "n_high": len(hi),
            "median_low": statistics.median(lo) if lo else None,
            "median_high": statistics.median(hi) if hi else None,
            "upheld": bool(lo and hi
                           and statistics.median(lo) > statistics.median(hi)),
            "p": rank_sum_p(lo, hi) if lo and hi else 1.0,
        })
    return out


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def render(r: dict[str, Any]) -> str:
    ln = ["### engaged 比率は、その日に出した本数が増えると下がる —— 判定"
          "（**公開ずみの日だけ**・Data API 0単位）"]
    if r.get("low_days"):
        ln.append(f"  低密度（{LOW_MAX}本/日 以下）の日: "
                  + " ".join(str(d) for d in r["low_days"]))
        ln.append(f"  高密度（{HIGH_MIN}本/日 以上・前後{WITHIN_DAYS}日）の日: "
                  + " ".join(str(d) for d in r["high_days"]))
    if r.get("low_dropped"):
        ln.append(f"  **前後{WITHIN_DAYS}日 に高密度の日が無くて落とした低密度の日: "
                  f"{len(r['low_dropped'])}日**"
                  "（孤立した日を混ぜると曜日と成長が入ります）")
    ln.append(f"  低密度 n={r.get('n_low', 0)} 中央値 {_pct(r.get('median_low'))}"
              f"  ／  高密度 n={r.get('n_high', 0)} 中央値 {_pct(r.get('median_high'))}"
              f"（再生 {MIN_VIEWS}回 以上の本だけ）")
    if not r.get("decided"):
        ln.append(f"  **判定できません**: {r.get('why')}")
        return "\n".join(ln)
    ln.append(f"  片側 p（低密度のほうが高い）= {r['p_one_sided']:.3f}"
              f"  ／ note の効き（×1.79）をこの本数で当てられる率 "
              f"{r.get('power_at_note_effect', 0):.0%}")
    for s_ in r.get("sweep", []):
        ln.append(f"    下限 {s_['min_views']:3}再生  "
                  f"低 n={s_['n_low']:3} {_pct(s_['median_low'])}"
                  f"  高 n={s_['n_high']:3} {_pct(s_['median_high'])}"
                  f"  上回った={s_['upheld']}  p={s_['p']:.3f}")
    if r["upheld"]:
        ln.append("  → **survived**（低密度の中央値が高密度を上回った）。"
                  "**順に並べた窓の A/B は、密度と共線です** ——"
                  " `src/density_confound.py` の警告はそのまま。")
    else:
        ln.append("  → **falsified**（上回っていない・同点も外れ）。"
                  "`next_if_false`: 密度は engaged を下げていない ＝"
                  " 3件の verdict はそのままでよい。")
    return "\n".join(ln)


def main() -> int:  # pragma: no cover - 画面出力だけ
    print(render(report()))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
