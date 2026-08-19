#!/usr/bin/env python3
"""**月20万円に、いつ届くか。毎回これを出してから作業を決める。**

    python scripts/eta.py              # 予測を出して data/eta.jsonl に積む
    python scripts/eta.py --no-record  # 出すだけ（積まない）
    python scripts/eta.py --offline    # API を叩かず、積んである最後の点から出す

## なぜ要るか（2026-08-19 オーナー指示 33699957）

> 実行の初めに、YouTube収益月収20万がいつ達成されるかを予測し、
> それを早めることを考えてから進めること。

**この指示は「見積もりを書け」ではありません。**「早めることを考えてから進め」＝
**その回の作業をどれにするかを、予測日を動かすかどうかで決めろ**、という意味に読みます。

そして**文書に手順として書くだけでは飛ばされます。**`docs/trigger_main.md` は
135KB あり、実際に §3 が読み飛ばされた記録があります（2026-08-18 23:4x）。
だから**道具にして、数字が勝手に出る形**にしました。

## この道具が答えるのは3つ

1. **いつ届くか**（いまの実測のまま伸ばしたら）
2. **どの数字が止めているか**（門を1つずつ当てて、最初に落ちるものを名指しする）
3. **いま考えている作業は、その日付を動かすか**（動かさないなら、やる理由がない）

## 天井の検査が本体です

いちばん効くのは (1) ではなく、**「いまの構成の上限は目標に届くのか」**です。

    1本あたりの再生 × 1日に出せる上限（92本）× 30日 ÷ 1000 × RPM

これが 200,000 円に届かないなら、**本数を増やしても、在庫を増やしても、
予測日は永遠に来ません。** 増やすべきは本数ではなく、
**1本あたりの再生数か RPM のほう**です。**その判定を毎回やります。**

## 割り引いて読むこと

- **RPM は実測ではありません**（収益化前なので自分の数字が無い）。
  だから幅で出します。**この幅の中で結論が変わるなら、結論は出ていません**
- 登録率・1本あたり再生は**実測**（YouTube Analytics）。ここは推測ではありません
- ショートの視聴時間は 4,000時間の門に**入りません**。長尺の視聴時間だけが入ります
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

LOG = ROOT / "data" / "eta.jsonl"

# --- 門（YouTube の公表値。守るのではなく、通らないと収入が0になる事実）---
SUBS_GATE = 1_000
LONG_HOURS_GATE = 4_000          # 直近12か月・長尺のみ
SHORTS_VIEWS_GATE = 10_000_000   # 直近90日・ショート
TARGET_YEN = 200_000             # 月収の目標

# --- 1日に出せる本数の上限（実測。data/upload_cap.jsonl の窓と同じ）---
UPLOAD_CAP_PER_DAY = 92

# --- 公開の密度（1日に何本「公開」するか。投稿＝予約とは別物）---
#     いまの予約は 246本が39.5日に散って 1日6.4本。詰めれば25本（受け取り帳 3c7e12a3）
PUBLISH_SCENARIOS = (4, 10, 25, 92)

# --- RPM の幅（**実測ではない**。収益化前なので自分の数字が無い）---
RPM_SCENARIOS = {
    "ショート 低": 20,
    "ショート 中": 35,
    "ショート 高": 60,
    "長尺 お金 低": 400,
    "長尺 お金 中": 1_000,
    "長尺 お金 高": 2_000,
}

NEVER = 10 ** 9  # 「届かない」を日数で表すときの番人


def _measure() -> dict:
    """YouTube Analytics から、予測に要る実測値だけを取る。"""
    from googleapiclient.discovery import build
    from src.auth import credentials

    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()

    def q(days: int, metrics: str, **kw) -> list:
        start = end - timedelta(days=days)
        res = analytics.reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
            metrics=metrics, **kw,
        ).execute()
        return res.get("rows") or []

    base = "views,estimatedMinutesWatched,subscribersGained,subscribersLost"
    all_rows = q(3650, base)
    d90 = q(90, base)
    d28 = q(28, base)
    d7 = q(7, base)

    # 長尺の視聴時間は流入経路では割れない。再生場所（SHORTS_FEED か否か）で割る。
    place = q(365, "views,estimatedMinutesWatched", dimensions="insightPlaybackLocationType")
    long_minutes_365 = sum(r[2] for r in place if r[0] != "SHORTS_FEED")
    shorts_views_90 = 0
    place90 = q(90, "views,estimatedMinutesWatched", dimensions="insightPlaybackLocationType")
    shorts_views_90 = sum(r[1] for r in place90 if r[0] == "SHORTS_FEED")

    # 1本あたりの再生（直近28日に再生のあった本の中央値。分母の小さい本は外す）
    per_video = q(28, "views", dimensions="video", sort="-views", maxResults=200)
    vals = sorted(r[1] for r in per_video if r[1] >= 30)
    median_views = vals[len(vals) // 2] if vals else 0

    def row(rows, i):
        return rows[0][i] if rows else 0

    return {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subs_net": row(all_rows, 2) - row(all_rows, 3),
        "views_all": row(all_rows, 0),
        "views_7d": row(d7, 0),
        "views_28d": row(d28, 0),
        "views_90d": row(d90, 0),
        "subs_gained_28d": row(d28, 2),
        "subs_gained_90d": row(d90, 2),
        "long_hours_365": round(long_minutes_365 / 60, 1),
        "shorts_views_90d": shorts_views_90,
        "median_views_per_video": median_views,
        "videos_with_views_28d": len(vals),
    }


def _days_to(need: float, per_day: float) -> float:
    """必要量と1日あたりから日数。進んでいないなら NEVER。"""
    if need <= 0:
        return 0.0
    if per_day <= 0:
        return NEVER
    days = need / per_day
    # 100年より先は「届かない」と同じに畳む。**桁の大きい数を残すと、
    # 前の回との差（縮んだぶん）がその桁に埋もれて読めなくなります。**
    return NEVER if days > 36_500 else days


def _fmt_days(days: float) -> str:
    if days >= NEVER:
        return "**届きません**（いまの速さでは増えていない）"
    if days <= 0:
        return "**通過済み**"
    if days > 36_500:  # 100年より先は、日付を書いても意味がない
        return f"**{days/365:,.0f}年後 ＝ 事実上いまの形では届きません**"
    when = date.today() + timedelta(days=math.ceil(days))
    if days > 3650:
        return f"{days/365:.0f}年後（{when.isoformat()}）"
    if days > 365:
        return f"{days/365:.1f}年後 ＝ {math.ceil(days):,}日（{when.isoformat()}）"
    return f"**{math.ceil(days):,}日後（{when.isoformat()}）**"


def analyse(m: dict) -> dict:
    """実測から、門ごとの日数と天井を出す。"""
    views_day_7 = m["views_7d"] / 7
    views_day_28 = m["views_28d"] / 28
    # 予測には速いほうを使う（伸びている最中に遅いほうで測ると、悲観に倒れる）
    views_day = max(views_day_7, views_day_28)

    sub_rate = (m["subs_gained_28d"] / m["views_28d"]) if m["views_28d"] else 0.0
    subs_per_day = views_day * sub_rate

    a = {
        "views_per_day": views_day,
        "views_per_day_7d": views_day_7,
        "views_per_day_28d": views_day_28,
        "sub_rate": sub_rate,
        "subs_per_day": subs_per_day,
        "subs_remaining": max(0, SUBS_GATE - m["subs_net"]),
    }

    # --- 門1: 登録者1,000人 ---
    a["days_subs"] = _days_to(a["subs_remaining"], subs_per_day)

    # --- 門2a: 長尺4,000時間（ショートは入らない）---
    long_hours_per_day = m["long_hours_365"] / 365
    a["days_long_hours"] = _days_to(LONG_HOURS_GATE - m["long_hours_365"], long_hours_per_day)

    # --- 門2b: ショート 直近90日で1,000万再生 ---
    a["shorts_needed_per_day"] = SHORTS_VIEWS_GATE / 90
    a["days_shorts_gate"] = 0.0 if views_day >= a["shorts_needed_per_day"] else NEVER

    # 収益化はどちらかの門2 ＋ 門1
    a["days_monetized"] = max(a["days_subs"], min(a["days_long_hours"], a["days_shorts_gate"]))

    # --- 天井: いまの構成で出せる最大の月収 ---
    per_video = m["median_views_per_video"]
    ceiling_views_month = per_video * UPLOAD_CAP_PER_DAY * 30
    a["ceiling_views_month"] = ceiling_views_month
    a["ceiling"] = {k: ceiling_views_month / 1000 * rpm for k, rpm in RPM_SCENARIOS.items()}

    # 目標に要る月間再生数（RPM ごと）
    a["views_needed_month"] = {k: TARGET_YEN * 1000 / rpm for k, rpm in RPM_SCENARIOS.items()}
    # 1日92本の上限で、その再生数に要る「1本あたり再生」
    a["per_video_needed"] = {
        k: v / (UPLOAD_CAP_PER_DAY * 30) for k, v in a["views_needed_month"].items()
    }
    a["per_video_now"] = per_video
    return a


def report(m: dict, a: dict) -> list[str]:
    out: list[str] = []
    P = out.append
    P("=" * 66)
    P("=== 月20万円に、いつ届くか（実測から。RPM だけが推測）===")
    P("=" * 66)
    P("")
    P("--- いま出ている数（YouTube Analytics。推測ではありません）---")
    P(f"  登録者（純）      {m['subs_net']:>10,} 人   （門は {SUBS_GATE:,} 人・**あと {a['subs_remaining']:,} 人**）")
    P(f"  再生／日          {a['views_per_day_7d']:>10,.0f} 回（直近7日）  {a['views_per_day_28d']:>7,.0f} 回（直近28日）")
    P(f"  登録率            {a['sub_rate']*100:>10.4f} %   ＝ 再生 {1/a['sub_rate']:,.0f} 回につき1人" if a["sub_rate"] else "  登録率            **0** ＝ 何回再生されても増えていない")
    P(f"  長尺の視聴時間    {m['long_hours_365']:>10,.1f} 時間（直近365日。門は {LONG_HOURS_GATE:,}）")
    P(f"  ショート90日      {m['shorts_views_90d']:>10,} 回（門は {SHORTS_VIEWS_GATE:,}）")
    P(f"  1本あたり再生     {m['per_video_now'] if 'per_video_now' in m else a['per_video_now']:>10,} 回（中央値・直近28日に再生のあった {m['videos_with_views_28d']} 本）")
    P("")
    P("--- 門を1つずつ当てる（**最初に落ちるものが、いまの律速**）---")
    P(f"  [門1] 登録者 {SUBS_GATE:,}人      {_fmt_days(a['days_subs'])}")
    P(f"        いまの速さ ＝ 1日 {a['subs_per_day']:.2f} 人（再生 {a['views_per_day']:,.0f}／日 × 登録率 {a['sub_rate']*100:.4f}%）")
    P(f"  [門2a] 長尺 {LONG_HOURS_GATE:,}時間    {_fmt_days(a['days_long_hours'])}")
    if a["days_shorts_gate"] == 0:
        shorts_line = "**通っています**"
    else:
        shorts_line = (f"**届きません**（1日 {a['shorts_needed_per_day']:,.0f}回 要る"
                       f"／いま {a['views_per_day']:,.0f}回）")
    P(f"  [門2b] ショート90日で{SHORTS_VIEWS_GATE:,}回    {shorts_line}")
    P(f"  → **収益化そのもの: {_fmt_days(a['days_monetized'])}**")
    P("")
    P("--- 天井（**ここが本体**）---")
    P(f"  1日に出せる上限 {UPLOAD_CAP_PER_DAY}本 × 1本 {a['per_video_now']:,}回 × 30日 = 月 {a['ceiling_views_month']:,.0f} 再生")
    P("  その月間再生で立つ収入と、月20万に要る1本あたりの再生:")
    for k in RPM_SCENARIOS:
        yen = a["ceiling"][k]
        need = a["per_video_needed"][k]
        mark = "**届く**" if yen >= TARGET_YEN else "届かない"
        ratio = need / a["per_video_now"] if a["per_video_now"] else float("inf")
        P(f"    {k:<12} RPM ¥{RPM_SCENARIOS[k]:>5,}  上限 ¥{yen:>10,.0f}  {mark:<8} "
          f"要 1本 {need:>9,.0f}回（いまの **{ratio:,.1f}倍**）")
    P("")
    reachable = [k for k in RPM_SCENARIOS if a["ceiling"][k] >= TARGET_YEN]
    unreachable = [k for k in RPM_SCENARIOS if a["ceiling"][k] < TARGET_YEN]
    if unreachable:
        P(f"  [!] **1日の上限まで出しても月20万に届かない帯: {', '.join(unreachable)}**")
        P("      この帯にいる限り、**本数を増やしても在庫を増やしても、日付は動きません。**")
        P("      動くのは **1本あたりの再生数** か **RPM（＝ニッチと尺）** の2つだけです。")
    if not reachable:
        P("  [!] **どの帯でも届きません。いまの構成は、上限そのものが目標の下にあります。**")
    else:
        P(f"  上限で届く帯: {', '.join(reachable)}")
        P("      **ただし RPM は実測ではありません。** 収益化後に自分の数字で測り直すこと。")
    P("")
    P("--- 早めるには、どれを何倍にするか（**倍率が小さいものから手を付ける**）---")
    for label, now, need in _levers(m, a):
        P(f"    {label:<26} いま {now:<16} → 要 {need}")
    P("")
    P("--- **公開の密度を上げたら、門1はいつ通るか**（1本あたり再生を据え置いた見積り）---")
    P(f"    ＝ 1日に公開する本数 × {a['per_video_now']:,}回 × 登録率 {a['sub_rate']*100:.4f}%")
    for n in PUBLISH_SCENARIOS:
        v = n * a["per_video_now"]
        d = _days_to(a["subs_remaining"], v * a["sub_rate"])
        P(f"    1日 {n:>3}本 公開 → 再生 {v:>9,.0f}／日 → 門1 {_fmt_days(d)}")
    P("    **これは推測です**（1日N本でも1本あたりが保つかは未測定＝M14 の「配信の壁」）。")
    P("    ただし 4本/日 までは崩れないことが実測済み（2026-08-19 04:4x・中央値 +50.5%）。")
    return out


def _levers(m: dict, a: dict) -> list[tuple[str, str, str]]:
    """門1（登録者1,000人）を1年以内に通すのに、各数字が何倍要るか。"""
    rows = []
    need_subs_per_day = a["subs_remaining"] / 365
    if a["subs_per_day"] > 0:
        x = need_subs_per_day / a["subs_per_day"]
    else:
        x = float("inf")
    rows.append(("登録者／日（門1を1年で）", f"{a['subs_per_day']:.2f}人", f"{need_subs_per_day:.2f}人 ＝ **{x:,.0f}倍**"))
    rows.append(("　うち 登録率", f"{a['sub_rate']*100:.4f}%",
                 f"{a['sub_rate']*100*x:.3f}%（再生数を据え置くなら）"))
    rows.append(("　うち 再生／日", f"{a['views_per_day']:,.0f}回",
                 f"{a['views_per_day']*x:,.0f}回（登録率を据え置くなら）"))
    per_day_cap = a["per_video_now"] * UPLOAD_CAP_PER_DAY
    rows.append(("本数だけで届く上限", f"{a['views_per_day']:,.0f}回／日",
                 f"{per_day_cap:,.0f}回／日（92本の上限。**{per_day_cap/max(a['views_per_day'],1):,.1f}倍まで**）"))
    return rows


def _drift(current: dict) -> list[str]:
    """前の回の予測と比べる。**近づいていないなら、その回の作業は効いていない。**"""
    if not LOG.exists():
        return ["", "  （前の点がありません。次の回からは、この行に「何日ぶん縮んだか」が出ます）"]
    prev = None
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                prev = json.loads(line)
            except json.JSONDecodeError:
                continue
    if not prev:
        return []
    out = ["", "--- 前の回からの差（**縮んでいないなら、その回の作業は日付を動かしていない**）---"]
    pd_ = prev.get("days_monetized")
    cd = current["days_monetized"]
    if pd_ is None:
        return out
    try:
        elapsed = (datetime.fromisoformat(current["at"]) - datetime.fromisoformat(prev["at"])).total_seconds() / 86400
    except (ValueError, KeyError):
        elapsed = 0.0
    if pd_ >= NEVER and cd >= NEVER:
        out.append("    収益化まで: **どちらも「届かない」**。**律速はまだ1つも動いていません。**")
    elif pd_ >= NEVER:
        out.append("    収益化まで: 「届かない」→ " + _fmt_days(cd) + "  **道が開きました**")
    elif cd >= NEVER:
        out.append("    収益化まで: " + _fmt_days(pd_) + " → **「届かない」に戻りました**")
    else:
        # 何もしなければ、経過したぶんだけ縮む。それ以上縮んだぶんが「効いた」ぶん。
        gained = (pd_ - cd) - elapsed
        out.append(f"    収益化まで: {pd_:,.0f}日 → {cd:,.0f}日（{elapsed:.2f}日 経過）")
        out.append(f"    **作業で縮んだぶん: {gained:+,.1f}日**"
                   + ("  ← 効いています" if gained > 0.5 else "  ← **効いていません**"))
    for key, label in (("views_per_day", "再生／日"), ("sub_rate", "登録率"), ("per_video_now", "1本あたり再生")):
        if key in prev and prev[key]:
            now = current.get(key, 0)
            if now:
                out.append(f"    {label}: {prev[key]:,.4g} → {now:,.4g}（{(now/prev[key]-1)*100:+.1f}%）")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="月20万に届く日を予測して積む")
    ap.add_argument("--no-record", action="store_true", help="data/eta.jsonl に積まない")
    ap.add_argument("--offline", action="store_true", help="API を叩かず、積んである最後の点から出す")
    args = ap.parse_args()

    if args.offline:
        if not LOG.exists():
            print("[eta] 積んだ点がありません。--offline は使えません。")
            return 1
        m = json.loads([l for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()][-1])
        print("[eta] **積んである最後の点で出しています（いまの実測ではありません）**")
    else:
        try:
            m = _measure()
        except Exception as exc:  # noqa: BLE001 — 予測で回を止めない
            print(f"[eta] 実測を取れませんでした: {type(exc).__name__}: {exc}")
            print("[eta] **回は止めないこと。** `--offline` で最後の点から読めます。")
            return 1

    a = analyse(m)
    m["per_video_now"] = a["per_video_now"]
    for line in report(m, a):
        print(line)
    row = {**m, **{k: v for k, v in a.items() if isinstance(v, (int, float))}}
    for line in _drift(row):
        print(line)

    if not args.no_record:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\n[eta] 積みました: {LOG.relative_to(ROOT)}（{sum(1 for _ in LOG.open(encoding='utf-8'))}点目）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
