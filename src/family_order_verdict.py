"""**「族べつの engaged 比率は、次に作る題材の順番に使える」の判定**（期限 2026-08-27）。

## 何を比べるか

`config/hypotheses.yaml`:

    claim         族べつの engaged 比率は、次に作る題材の順番に使える（実績は事前分布として効く）
    needs         published_group / created_after 2026-08-16 / count 13 / settle_days 3
    falsified_if  2026-08-30 時点で、この順番で作った本（8/16 以降に `pick` が選んだもの）の
                  engaged 比率の中央値が、8/4〜8/15 に公開した13本の中央値 34.7% を
                  **上回っていない**（同点も外れとみなす）。

## **群は「作った日」で割ります。公開日ではありません**（ここがこの判定の要点）

順番を決めているのは `pick` で、それが効くのは **作るとき**です。
公開日で割ると、**8/16 より前に作った本が 8/16 以降に公開されるぶんだけ**
処置群に混ざります（実測で 100本を超えます）。だから群は
`data/batch_runs.jsonl` の `at`（作った時刻・JST の暦日）で割り、
`results[].video_id` をそのまま使います。**API は1単位も使いません。**

`src/ab_split.py` が同じ理由で同じファイルを読んでいます（あちらは題と冒頭の A/B）。

## **なぜ 08-30 を待たずに下せるのか**（2026-08-26。前の回が「4日早い」として見送った所）

`falsified_if` に書いてある **2026-08-30 は、群がそろう日の見積り**でした
（書いた 8/16 の時点では熟成 7日 を仮定していた）。`src/settle.py` の実測で
**熟成は 3日**と分かり、`deadline` は 08-30 → 08-27 へ縮めてあります。

**日を待っても、この群には1本も足されません。** 群の上限は「8/16 以降に作って、
すでに公開され、公開から 熟成3日 ＋ 実データの遅れ3日 がたった本」で、
`scripts/deadline_check.py` が **13本目の公開 08/20** → 読めるのは **08-26** と出しています。
08-30 まで待つと**増えるのは同じ13本の齢だけ**です。

**それでも「早い判定は外れに倒れる」向きは残ります。**
その向きを、当てずに測ります —— `src/settle.py` の `engaged_curve()` は
**engaged 比率が確定値からどれだけ離れているか**を実測しており、
72時間の時点で **中央値 0.16pt・いちばん遅い本でも 0.64pt**（n=20）です。
**齢のせいにできる幅は 1pt 未満**なので、それより大きい差はこの向きでは説明できません。
`age_objection()` がこの幅を毎回引き直し、`report()` が差と並べて印字します。

熟成の齢そのものも振ります（`sweep_settle`）が、**齢を伸ばすと処置群が 0本になります**
（8/16 以降に作った本で 8/18 までに公開されたものは1本も無い）。
**0本の欄は「上回らない」ではなく「測れない」**と出します ——
標本が消えたことを答えの側に数えると、待てば待つほど「外れ」に見えます。

## 基準の 34.7% は写しません。**日付で切り直します**

`falsified_if` の「34.7%」「13本」は書いた日の実測です。`length_verdict` の
「本数は写さない」と同じ理由で、**8/4〜8/15 という日付の範囲**のほうを条件とみなし、
中央値はその場で数え直します。**書いてある 34.7% でも同時に判定**し、
**両方で答えが一致したときだけ `decided`** とします（食い違ったら、それは基準が動いた合図）。

## 読むもの

    作った日・族   data/batch_runs.jsonl（**API 0単位**）
    公開時刻       scripts/eta.py の published_at()（**API 0単位**）
    engaged        YouTube Analytics の views / engagedViews（**Data API は使わない**）

**Data API の日枠が閉じている窓でも下せます**（判定に要るのは Analytics だけ）。
"""
from __future__ import annotations

import json
import statistics
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src import density_confound
from src.ab_power import rank_sum_p
from src.length_verdict import MIN_VIEWS, _published, fetch_engaged, ratios
from src.settle import SETTLE_DAYS, analytics_lag_days

ROOT = Path(__file__).resolve().parent.parent
BATCH = ROOT / "data" / "batch_runs.jsonl"

JST = timezone(timedelta(hours=9))

#: 処置群 ＝ この日以降に**作った**本（`pick` が実績で順番を決めるようになった日）。
CREATED_AFTER = date(2026, 8, 16)

#: 対照群 ＝ この範囲に**公開**した本（`pick` が手書きの score だけで選んでいた頃）。
BASE_FROM, BASE_TO = date(2026, 8, 4), date(2026, 8, 15)

#: `falsified_if` に書いてある基準。**写しですが、消しません** ——
#: 日付で数え直した中央値と**両方**で判定し、食い違ったら `undecided` にするため。
WRITTEN_BASELINE = 0.347


def built(path: Path | None = None) -> dict[str, dict[str, Any]]:
    """`video_id` → `{"created": JSTの暦日, "calc": 族}`。**純関数（API 0単位）。**

    同じ本が2度出てきたら**先に作ったほう**を採ります（作り直しは順番の産物ではない）。
    """
    path = path or BATCH
    out: dict[str, dict[str, Any]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            at = datetime.fromisoformat(str(row.get("at")).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            continue
        if at.tzinfo is None:
            at = at.replace(tzinfo=timezone.utc)
        made = at.astimezone(JST).date()
        for r in row.get("results") or []:
            vid = r.get("video_id")
            if not vid or r.get("error"):
                continue
            prev = out.get(vid)
            if prev is None or made < prev["created"]:
                out[vid] = {"created": made, "calc": r.get("calc") or "?"}
    return out


def readable_by(as_of: date | None = None, settle_days: int | None = None) -> date:
    """**この日までに公開された本なら、実データが読める**（公開日の上限）。

    `deadline_check.py` と同じ引き算です —— 熟成（`src/settle.py`）＋ 実データの遅れ。
    """
    as_of = as_of or datetime.now(JST).date()
    settle = SETTLE_DAYS if settle_days is None else settle_days
    return as_of - timedelta(days=settle + analytics_lag_days(as_of))


def groups(published: dict[str, datetime] | None = None,
           builds: dict[str, dict[str, Any]] | None = None,
           as_of: date | None = None,
           settle_days: int | None = None) -> tuple[list[str], list[str]]:
    """`(対照, 処置)`。**処置は作った日で、対照は公開日で切ります。**

    非対称なのは条件がそう書いてあるからです ——
    対照は「8/4〜8/15 に**公開**した本」、処置は「8/16 以降に `pick` が**選んだ**本」。
    """
    published = published if published is not None else _published()
    builds = builds if builds is not None else built()
    cutoff = readable_by(as_of, settle_days)
    base: list[str] = []
    treat: list[str] = []
    for vid, born in published.items():
        d = born.astimezone(JST).date()
        if BASE_FROM <= d <= BASE_TO:
            base.append(vid)
        made = (builds.get(vid) or {}).get("created")
        if made is not None and made >= CREATED_AFTER and d <= cutoff:
            treat.append(vid)
    return sorted(base), sorted(treat)


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def verdict(base: list[float], treat: list[float],
            written: float = WRITTEN_BASELINE) -> dict[str, Any]:
    """**上回ったか。** `falsified_if` は「上回っていない（同点も外れ）」。

    **数え直した基準と、書いてある基準の両方で判定します。**
    食い違ったら `decided=False` —— 答えが「どちらの基準を採るか」で決まるなら、
    それは前提が答えたのではなく、こちらが選んだだけです。
    """
    med_base, med_treat = _median(base), _median(treat)
    if med_base is None or med_treat is None:
        return {"decided": False, "why": "片方の群に測れる本が1つもありません",
                "median_base": med_base, "median_treat": med_treat,
                "n_base": len(base), "n_treat": len(treat)}
    up_measured = med_treat > med_base
    up_written = med_treat > written
    return {
        "decided": up_measured == up_written,
        "upheld": up_measured if up_measured == up_written else None,
        "why": "" if up_measured == up_written
               else f"数え直した基準 {med_base*100:.1f}% と、書いてある基準 {written*100:.1f}% で答えが割れました",
        "median_base": med_base,
        "median_treat": med_treat,
        "written_baseline": written,
        "upheld_measured": up_measured,
        "upheld_written": up_written,
        "n_base": len(base),
        "n_treat": len(treat),
    }


def sweep_settle(rows: list[dict[str, Any]], base_ids: list[str],
                 builds: dict[str, dict[str, Any]],
                 published: dict[str, datetime],
                 as_of: date | None = None,
                 settles: tuple[int, ...] = (3, 5, 7)) -> list[dict[str, Any]]:
    """**熟成の日数を振って、答えが変わらないかを見る。**

    「4日早い判定は外れに倒れる」という向きを、**当てずに測る**ための欄です。
    齢を伸ばすほど処置群は減ります（若い本が落ちる）。**どの齢でも同じなら、齢のせいではない。**
    """
    r = ratios(rows)
    base = [r[v] for v in base_ids if v in r]
    out = []
    for s in settles:
        cutoff = readable_by(as_of, s)
        ids = [v for v, born in published.items()
               if (builds.get(v) or {}).get("created") is not None
               and builds[v]["created"] >= CREATED_AFTER
               and born.astimezone(JST).date() <= cutoff]
        t = [r[v] for v in ids if v in r]
        out.append({"settle_days": s, "n_treat": len(t), "n_base": len(base),
                    "median_treat": _median(t), "median_base": _median(base),
                    # **標本が消えた欄を「上回らない」に数えないこと。** 数えると、
                    # 齢を伸ばすほど自動で「外れ」になります（答えではなく標本の話）。
                    "upheld": None if not (t and base) else _median(t) > _median(base)})
    return out


def age_objection(ages: tuple[float, ...] = (60, 72, 96)) -> dict[str, Any]:
    """**「4日早い判定だから低く出たのでは」に、幅で答える。**

    `src/settle.py` の実測（`engaged_curve`）から、**熟成 `SETTLE_DAYS` の時点で
    engaged 比率が確定値からどれだけ離れうるか**（pt）を引き直します。
    ここより大きい差は、**齢では説明できません。**
    """
    from src.settle import engaged_curve

    hours = float(SETTLE_DAYS * 24)
    try:
        curve = engaged_curve(tuple(sorted(set(ages) | {hours})))
    except Exception as exc:  # pragma: no cover - 実測が無い環境でも判定は続ける
        return {"hours": hours, "n": 0, "median_pt": None, "max_pt": None, "why": str(exc)}
    hit = curve.get(hours)
    if not hit:
        return {"hours": hours, "n": 0, "median_pt": None, "max_pt": None,
                "why": "この齢の実測がまだありません"}
    return {"hours": hours, "n": hit["n"],
            "median_pt": hit["median"] * 100, "max_pt": hit["max"] * 100, "why": ""}


def sweep_min_views(rows: list[dict[str, Any]], base_ids: list[str], treat_ids: list[str],
                    thresholds: tuple[int, ...] = (1, 10, 30, 50)) -> list[dict[str, Any]]:
    """**下限の再生数を振る**（`length_verdict.sweep` と同じ趣旨。線の産物でないことを見る）。"""
    out = []
    for mv in thresholds:
        r = ratios(rows, min_views=mv)
        b = [r[v] for v in base_ids if v in r]
        t = [r[v] for v in treat_ids if v in r]
        out.append({"min_views": mv, "n_base": len(b), "n_treat": len(t),
                    "median_base": _median(b), "median_treat": _median(t),
                    "upheld": bool(b and t and _median(t) > _median(b))})
    return out


def by_family(rows: list[dict[str, Any]], ids: list[str],
              builds: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    """族べつの engaged 比率（本数の多い順）。**claim の中身そのもの**なので必ず出します。"""
    r = ratios(rows)
    buckets: dict[str, list[float]] = {}
    for vid in ids:
        if vid not in r:
            continue
        fam = (builds.get(vid) or {}).get("calc") or "?"
        buckets.setdefault(fam, []).append(r[vid])
    out = [{"calc": k, "n": len(v), "median": statistics.median(v)} for k, v in buckets.items()]
    out.sort(key=lambda x: (-x["n"], -x["median"]))
    return out


def report(as_of: date | None = None) -> dict[str, Any]:
    as_of = as_of or datetime.now(JST).date()
    published = _published()
    builds = built()
    base_ids, treat_ids = groups(published, builds, as_of)
    rows = fetch_engaged(base_ids + treat_ids, BASE_FROM, as_of)
    r = ratios(rows)
    base = [r[v] for v in base_ids if v in r]
    treat = [r[v] for v in treat_ids if v in r]
    out = verdict(base, treat)
    out["ids_base"], out["ids_treat"] = base_ids, treat_ids
    out["cutoff"] = readable_by(as_of).isoformat()
    out["sweep_settle"] = sweep_settle(rows, base_ids, builds, published, as_of)
    out["sweep_min_views"] = sweep_min_views(rows, base_ids, treat_ids)
    out["by_family"] = by_family(rows, treat_ids, builds)
    out["p_treat_higher"] = rank_sum_p(treat, base)
    out["p_base_higher"] = rank_sum_p(base, treat)
    out["age_objection"] = age_objection()
    out["density"] = density_confound.overlap(base_ids, treat_ids, published)
    out["density_line"] = density_confound.line(base_ids, treat_ids, published)
    gap = out.get("median_base"), out.get("median_treat")
    out["gap_pt"] = None if None in gap else (gap[0] - gap[1]) * 100
    return out


def _pct(x: float | None) -> str:
    return "—" if x is None else f"{x * 100:.1f}%"


def main() -> None:  # pragma: no cover - 画面出力だけ
    out = report()
    print("=" * 70)
    print("### 族べつの engaged 比率は、次に作る題材の順番に使える —— 判定")
    print("=" * 70)
    print(f"  処置 ＝ **作った日** {CREATED_AFTER} 以降 かつ 公開が {out['cutoff']} まで"
          f"（熟成 {SETTLE_DAYS}日 ＋ 実データの遅れ {analytics_lag_days()}日）")
    print(f"  対照 ＝ **公開日** {BASE_FROM}〜{BASE_TO}")
    print(f"  母集団: 対照 {len(out['ids_base'])}本 ／ 処置 {len(out['ids_treat'])}本"
          f"   （{MIN_VIEWS}再生以上 対照 {out.get('n_base')}本 ／ 処置 {out.get('n_treat')}本）")
    print()
    print(f"  対照の中央値（数え直し） {_pct(out.get('median_base'))}"
          f"   ／ 条件に書いてある基準 {_pct(out.get('written_baseline'))}")
    print(f"  処置の中央値             {_pct(out.get('median_treat'))}")
    print(f"  片側 p（処置のほうが高い） {out.get('p_treat_higher', 1.0):.3f}"
          f" ／ 逆（対照のほうが高い） {out.get('p_base_higher', 1.0):.3f}   （α=0.20）")
    print()
    ao = out.get("age_objection") or {}
    if out.get("gap_pt") is not None and ao.get("max_pt") is not None:
        print(f"  --- 「4日早いから低く出たのでは」への答え（`src/settle.py` の実測）---")
        print(f"    差は **{out['gap_pt']:.1f}pt**。熟成 {SETTLE_DAYS}日 の時点で確定値から離れる幅は"
              f" 中央値 {ao['median_pt']:.2f}pt・最大 {ao['max_pt']:.2f}pt（n={ao['n']}）")
        print(f"    → 齢で説明できるのは最大 {ao['max_pt']:.2f}pt。"
              f"**{'説明できません' if out['gap_pt'] > ao['max_pt'] else '説明の内側です'}**")
        print()
    print("  --- 熟成の齢を振る（標本が消える所まで）---")
    for s in out.get("sweep_settle", []):
        mark = "測れない（処置 0本）" if s["upheld"] is None else ("上回る" if s["upheld"] else "上回らない")
        print(f"    熟成 {s['settle_days']}日: 処置 {s['n_treat']}本 {_pct(s['median_treat'])}"
              f" 対 対照 {_pct(s['median_base'])} → {mark}")
    print("  --- 下限の再生数を振る ---")
    for s in out.get("sweep_min_views", []):
        print(f"    {s['min_views']}再生以上: 処置 {s['n_treat']}本 {_pct(s['median_treat'])}"
              f" 対 対照 {s['n_base']}本 {_pct(s['median_base'])}"
              f" → {'上回る' if s['upheld'] else '上回らない'}")
    print("  --- 交絡（`src/density_confound.py`）---")
    print(out.get("density_line", ""))
    if (out.get("density") or {}).get("confounded"):
        print("    **この判定は、順番の効果と公開密度の効果を分けられていません。**")
        print("    engaged は密度と逆向きに動きます（1〜2本/日 34.8% 対 9本以上/日 19.4%・片側 p=0.057）。")
    print("  --- 処置群の族べつ（claim の中身）---")
    for f in out.get("by_family", []):
        print(f"    {f['calc']:<12} {f['n']}本  {_pct(f['median'])}")
    print()
    if not out.get("decided"):
        print(f"  → **undecided**   {out.get('why')}")
        print("     **期限も条件も動かさないこと。**")
    else:
        print(f"  → **{'survived' if out['upheld'] else 'falsified'}**")
        if not out["upheld"]:
            print("     実績を事前分布に使っても、engaged の中央値は上がりませんでした。")


if __name__ == "__main__":  # pragma: no cover
    main()
