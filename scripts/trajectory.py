#!/usr/bin/env python3
"""**月20万までの軌跡を、実測だけで立てる。**（2026-08-20 に作った）

    python scripts/trajectory.py            # 軌跡を出す（実測は貯めたぶんから。API を叩きません）
    python scripts/trajectory.py --json     # 機械が読む形

## なぜ `scripts/eta.py` と別に要るのか

オーナーの指示（原文）——

  > 実測から分かる情報を限界まで調べ、考え、計算し、組み合わせて
  > 妥当な20万達成までの軌跡の予測を導き出す

`eta.py` の軌跡は **腕（per_video / sub_rate / rpm / density）が実測の速さで
動いていったら**という形で立っています。その形には、実測で裏の取れない項が
3つ入っていました（親が 2026-08-20 に名指し）:

  1. 段4（月20万）の期日が**収益化の門に張り付いている** —— 月3.8万再生と
     必要な月50万再生の**13倍の開き**が、段として立っていない
  2. `density_month` が **25.0本/日** —— 実測の予約は 08/27 で 25本/日 を切り、
     そこから 8本/日 に落ちる（`data/uploaded.jsonl`）
  3. `growth_per_day` **5.38%/日** の複利 —— 100日で約180倍。1 の13倍がこれ1つで埋まる

**この道具は、その3つを実測で置き換えます。** 置き換えられないものは
**埋めずに「未測定」と名指し**します。印字はすべて次の3つのどれかの札を付けます:

    [実測]   このチャンネルの数字。出どころと n を必ず併記する
    [代用]   よそから借りた数字。**このチャンネルでは測っていない**
    [未測定] 数字が無い。**代用も置かない**（置いた瞬間に実測と同じ字で出るので）

## この軌跡の骨格 —— **恒等式**

    チャンネルの日次再生 ＝ 供給（本/日） × 1本あたり生涯再生 V

これは模型ではなく**帳尻**です。2026-08-04〜08-17（Analytics が出ている全期間）で
検算すると **差 1%未満** で閉じます（`identity()`）。閉じる理由は、**後ろカタログが
無いから**です —— 1本の生涯再生の **98.4%（中央値）が公開24時間以内**に来て、
齢2日を超えた本の再生は**中央値 0.0回/日**（`decay()`）。

**だから複利で伸びる項が、実測の中に1つもありません。** 伸ばせるのは
**供給** と **V** の2つだけで、どちらにも実測の天井があります。
`growth_per_day` の 5.38%/日 は、この2つが動いた跡を**時間の関数に読み替えた**もので、
日次再生そのものには **1日 +0.77% ± 5.4pt（t=0.14・n=14日）** ——
**0 と区別がつきません**（`trend()`）。100日ぶん複利で伸ばすと、
95%区間は **0.00007倍 〜 100,000倍** に開きます。段が飛ぶのはここです。
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import math
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
TODAY = dt.date(2026, 8, 20)          # `--at` で上書きできます

# --- 門と目標（YouTube の公表値。守るのではなく、通らないと収入が 0 になる事実）---
SUBS_GATE = 1_000
LONG_HOURS_GATE = 4_000               # 直近12か月・長尺のみ
SHORTS_VIEWS_GATE = 10_000_000        # 直近90日・ショート
TARGET_YEN = 200_000
REVENUE_WINDOW_DAYS = 30
MONETIZE_REVIEW_DAYS = 30             # [代用] YouTube 公表「通常1か月以内」

# --- 1日に出せる本数の上限（実測。`data/upload_cap.jsonl` の 429 が出た窓）---
UPLOAD_CAP_PER_DAY = 92

# --- RPM の幅（[代用]。収益化前なので自分の数字が1つも無い）---
RPM_SHORTS = {"低": 20, "中": 35, "高": 60}
RPM_LONG = {"低": 400, "中": 1_000, "高": 2_000}

DUD_VIEWS = 10                        # 生涯これ未満を「空振り」と呼ぶ（分布が二山なので境目は谷）
MATURE_AGE_DAYS = 3.0                 # 生涯再生を確定と見なす齢（98.4% が24時間以内なので余裕）


# ----------------------------------------------------------------------------
# 実測を読む
# ----------------------------------------------------------------------------

def _jsonl(name: str) -> list[dict]:
    p = DATA / name
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                pass
    return out


def _t(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))


def videos() -> dict:
    """`data/views.jsonl` を1本ずつに畳む。

    返すのは `{id: {"pub": 公開日, "term": 生涯再生, "age": 観測できた齢(日),
    "at24": 24時間時点, "at48": 48時間時点, "points": 生の点}}`。

    **`hours` は Analytics が返す「公開からの時間」**なので、公開時刻は
    `at - hours` で復元できます（アップロード帳に載っていない本も拾えます）。
    """
    rows = _jsonl("views.jsonl")
    by: dict[str, list[dict]] = collections.defaultdict(list)
    for r in rows:
        by[r["id"]].append(r)
    out = {}
    for vid, pts in by.items():
        pts.sort(key=lambda r: r["hours"])
        pub = _t(pts[0]["at"]) - dt.timedelta(hours=pts[0]["hours"])

        def at(h: float):
            c = [r for r in pts if r["hours"] <= h]
            return c[-1]["views"] if c else None

        out[vid] = {
            "pub": pub.date(),
            "term": max(r["views"] for r in pts),
            "age": pts[-1]["hours"] / 24,
            "at24": at(24), "at48": at(48),
            "points": pts,
        }
    return out


def daily_views() -> dict[str, int]:
    """Analytics の日次再生（`data/scan.jsonl` の最後の点の `day.*`）。"""
    rows = _jsonl("scan.jsonl")
    if not rows:
        return {}
    v = rows[-1].get("values", {})
    return {k[4:]: int(n) for k, n in v.items() if k.startswith("day.")}


def scan_values() -> dict:
    rows = _jsonl("scan.jsonl")
    return rows[-1].get("values", {}) if rows else {}


# ----------------------------------------------------------------------------
# 1. 恒等式 —— この軌跡の骨格
# ----------------------------------------------------------------------------

def identity(vs: dict, day: dict[str, int]) -> dict:
    """**チャンネルの日次再生 ＝ 供給 × V** が帳尻で閉じることを確かめる。

    Analytics が日次を返している窓を丸ごと取り、**その窓に公開した本の生涯再生の
    合計**と、**その窓の Analytics の再生合計**を突き合わせます。

    閉じるなら、**その窓の再生は全部その窓に公開した本のもの**です ——
    つまり**後ろカタログが1回も効いていない**。閉じなければ、差のぶんだけ
    古い本が効いているので、軌跡に減衰項が要ります。
    """
    if not day:
        return {"ok": False}
    days = sorted(day)
    lo, hi = dt.date.fromisoformat(days[0]), dt.date.fromisoformat(days[-1])
    win = [k for k, v in vs.items() if lo <= v["pub"] <= hi]
    lifetime = sum(vs[k]["term"] for k in win)
    measured = sum(day[d] for d in days)
    span = (hi - lo).days + 1
    return {
        "ok": True, "lo": lo, "hi": hi, "span": span,
        "n_videos": len(win), "supply": len(win) / span,
        "lifetime_sum": lifetime, "analytics_sum": measured,
        "gap": lifetime / measured - 1 if measured else None,
    }


def decay(vs: dict) -> dict:
    """**後ろカタログがあるか。** 齢べつの「再生/日」と、生涯のうち24時間に来る割合。"""
    buckets: dict[int, list[float]] = collections.defaultdict(list)
    for v in vs.values():
        for a, b in zip(v["points"], v["points"][1:]):
            dh = b["hours"] - a["hours"]
            if dh < 6:
                continue
            dv = b["views"] - a["views"]
            if dv < 0:
                continue
            buckets[int((a["hours"] + b["hours"]) / 2 / 24)].append(dv / (dh / 24))
    curve = []
    for d in sorted(buckets):
        xs = buckets[d]
        if len(xs) >= 3:
            curve.append({"age_days": d, "n": len(xs),
                          "median": statistics.median(xs), "mean": statistics.mean(xs)})
    mature = [v for v in vs.values() if v["age"] >= MATURE_AGE_DAYS and v["term"] > 0]
    fr24 = [v["at24"] / v["term"] for v in mature if v["at24"] is not None]
    return {
        "curve": curve, "n_mature": len(mature),
        "frac24_median": statistics.median(fr24) if fr24 else None,
        "frac24_n": len(fr24),
        "old_median_per_day": statistics.median(
            [c["median"] for c in curve if c["age_days"] >= 2]) if curve else None,
    }


# ----------------------------------------------------------------------------
# 2. V（1本あたり生涯再生）
# ----------------------------------------------------------------------------

def per_video(vs: dict, seed: int = 7) -> dict:
    """**V の分布**。平均・中央値・bootstrap 区間・空振り率・チャンネル内の天井。

    **天井に平均を使います** —— 天井は N本ぶんの合計なので、合計 ＝ N × 平均。
    中央値を N倍しても合計にはなりません。
    """
    mature = [v for v in vs.values() if v["age"] >= MATURE_AGE_DAYS]
    V = [v["term"] for v in mature]
    if not V:
        return {"ok": False}
    rnd = random.Random(seed)
    bs = sorted(statistics.mean(rnd.choices(V, k=len(V))) for _ in range(4000))
    duds = [x for x in V if x < DUD_VIEWS]
    hits = [x for x in V if x >= DUD_VIEWS]
    h24 = [v["at24"] for v in mature if v["at24"] is not None]
    return {
        "ok": True, "n": len(V),
        "mean": statistics.mean(V), "median": statistics.median(V),
        "ci_lo": bs[100], "ci_hi": bs[3900],
        "dud_n": len(duds), "dud_rate": len(duds) / len(V),
        "hit_mean": statistics.mean(hits) if hits else 0.0,
        "hit_median": statistics.median(hits) if hits else 0.0,
        "best24": max(h24) if h24 else None,
        "ceiling_ratio": (max(h24) / statistics.mean(V)) if h24 else None,
    }


# ----------------------------------------------------------------------------
# 3. 供給（本/日）
# ----------------------------------------------------------------------------

def build_rate() -> dict:
    """**作る能力（本/時）。** `data/batch_runs.jsonl` の wall 時間と成功数から。

    「1日に何本作れるか」は**作る速さ**ではなく **wall 時間 × その速さ**です。
    ここは分子（速さ）だけを出します —— 分母（1日に何時間動くか）は
    使用量の枠が決めるので、`scripts/quota.py` の側にあります。
    """
    rows = _jsonl("batch_runs.jsonl")
    ok = wall = plan = 0
    for r in rows:
        wall += r.get("wall_sec") or 0
        plan += r.get("count") or 0
        for res in (r.get("results") or []):
            if not res.get("error"):
                ok += 1
    if not wall:
        return {"ok": False}
    hours = wall / 3600
    return {"ok": True, "built": ok, "planned": plan, "hours": hours,
            "per_hour": ok / hours, "success": ok / plan if plan else None,
            "n_batches": len(rows),
            "hours_for_cap": UPLOAD_CAP_PER_DAY / (ok / hours)}


def material_rate() -> dict:
    """**題材が増える速さ（件/日）。** `data/supply.jsonl` の `sweep_novel` の増分。

    **供給の本当の天井はここ**です —— API の日枠 92本 も、作る能力 41本/時 も、
    **出す題材が無ければ使えません。** 掃引の残り（`novel`）は在庫であって速さでは
    ないので、**増分を時間で割って**速さにします。
    """
    ps = _jsonl("supply.jsonl")
    pts = [(_t(p["at"]), p) for p in ps if p.get("at") and p.get("sweep_novel") is not None]
    pts.sort()
    if len(pts) < 2:
        return {"ok": False}
    steps = []
    for (t0, a), (t1, b) in zip(pts, pts[1:]):
        dh = (t1 - t0).total_seconds() / 3600
        dn = b["sweep_novel"] - a["sweep_novel"]
        if dh > 0 and dn > 0:
            steps.append(dn / dh * 24)
    span = (pts[-1][0] - pts[0][0]).total_seconds() / 3600
    total = pts[-1][1]["sweep_novel"] - pts[0][1]["sweep_novel"]
    return {
        "ok": True, "n_points": len(pts), "span_hours": span,
        "delta": total, "per_day": (total / span * 24) if span > 0 else None,
        "steps": steps, "stock_novel": pts[-1][1]["sweep_novel"],
        "thin": span < 24,
    }


def supply_now(today: dt.date) -> dict:
    """**いま実際に何本/日 公開されるか。** 予約の実物（`data/uploaded.jsonl`）から。

    `eta.py` の `density_month` は「詰め方の上限」25本/日 を使っていますが、
    **予約の実物は 08/27 で 25本/日 を切ります。** 持続する密度は、
    上限ではなく**予約の実物の平均**です。
    """
    rows = _jsonl("uploaded.jsonl")
    cnt = collections.Counter()
    for r in rows:
        a = r.get("at") or r.get("uploaded_at")
        if a:
            cnt[a[:10]] += 1
    fut = {d: n for d, n in cnt.items() if d > today.isoformat()}
    if not fut:
        return {"ok": False}
    ds = sorted(fut)
    span = (dt.date.fromisoformat(ds[-1]) - today).days
    total = sum(fut.values())
    dense_days = sum(1 for d in ds if fut[d] >= 25)      # `eta.py` が正本に置いた密度
    try:
        from src import supply as _sup
        st = _sup.state()
    except Exception:                                  # noqa: BLE001
        st = {}
    return {
        "ok": True, "scheduled": total, "first": ds[0], "last": ds[-1],
        "span_days": span, "sustained": total / span,
        "peak": max(fut.values()), "dense_days": dense_days,
        "make_rate": st.get("rate_per_day"), "make_thin": (st.get("rate") or {}).get("thin"),
        "stock": st.get("stock"), "novel": st.get("novel"),
        "by_day": {d: fut[d] for d in ds},
        "build": build_rate(), "material": material_rate(),
    }


# ----------------------------------------------------------------------------
# 4. 伸び率（複利の項が実測にあるか）
# ----------------------------------------------------------------------------

def trend(day: dict[str, int]) -> dict:
    """**日次再生に有意な傾きがあるか。** log 線形回帰の t 値まで出す。

    `eta.py` の `growth_per_day` は「直近7日/直近28日」の比を複利に読み替えます。
    **その比は点推定で、区間が付いていません。** ここは同じ実測から区間を出します ——
    **区間が 0 をまたぐなら、100日ぶん複利で伸ばしてはいけない**（伸ばすと、
    区間そのものが桁で開きます）。
    """
    if len(day) < 4:
        return {"ok": False}
    ds = sorted(day)
    xs = list(range(len(ds)))
    ly = [math.log(max(day[d], 1)) for d in ds]
    n = len(xs)
    mx, my = statistics.mean(xs), statistics.mean(ly)
    sxx = sum((x - mx) ** 2 for x in xs)
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ly)) / sxx
    a0 = my - b * mx
    resid = [y - (a0 + b * x) for x, y in zip(xs, ly)]
    se = math.sqrt(sum(r * r for r in resid) / (n - 2) / sxx)
    return {
        "ok": True, "n": n, "g": math.exp(b) - 1, "se": se, "t": b / se,
        "lo": math.exp(b - 1.96 * se) - 1, "hi": math.exp(b + 1.96 * se) - 1,
        "significant": abs(b / se) >= 2.0,
        "blowup_lo": math.exp((b - 1.96 * se) * 100),
        "blowup_hi": math.exp((b + 1.96 * se) * 100),
        "mean_views_day": statistics.mean(day[d] for d in ds),
        "first": ds[0], "last": ds[-1],
    }


# ----------------------------------------------------------------------------
# 5. 登録率・面（どこから再生が来ているか）・インプレッション
# ----------------------------------------------------------------------------

def _poisson_ci(k: int) -> tuple[float, float]:
    """**回数 k の 95%区間**（Wilson–Hilferty で gamma 分位を近似）。

    9人しか居ない登録者を「率」と呼ぶ以上、区間なしで割ってはいけません。
    """
    def gq(z: float, a: float) -> float:
        if a <= 0:
            return 0.0
        c = 2 / (9 * a)
        return a * (1 - c + z * math.sqrt(c)) ** 3
    return gq(-1.959964, k), gq(1.959964, k + 1)


def subs(v: dict) -> dict:
    gained = int(v.get("合計.subscribersGained", 0))
    lost = int(v.get("合計.subscribersLost", 0))
    views = int(v.get("合計.views", 0))
    net = gained - lost
    lo, hi = _poisson_ci(max(net, 0))
    return {
        "net": net, "views": views,
        "rate": net / views if views else None,
        "rate_lo": lo / views if views else None,
        "rate_hi": hi / views if views else None,
        "remaining": max(0, SUBS_GATE - net),
    }


def traffic(v: dict) -> dict:
    src = {k.split(".", 1)[1]: n for k, n in v.items()
           if k.startswith("insightTrafficSourceType.")}
    loc = {k.split(".", 1)[1]: n for k, n in v.items()
           if k.startswith("insightPlaybackLocationType.")}
    tot = sum(src.values()) or 1
    shorts = src.get("SHORTS", 0)
    non_shorts = tot - shorts
    return {
        "src": dict(sorted(src.items(), key=lambda kv: -kv[1])),
        "loc": dict(sorted(loc.items(), key=lambda kv: -kv[1])),
        "total": tot, "shorts": shorts, "shorts_share": shorts / tot,
        "non_shorts": non_shorts,
        "search": src.get("YT_SEARCH", 0), "browse": src.get("YT_OTHER_PAGE", 0),
        "suggested": src.get("RELATED_VIDEO", 0),
    }


def reach() -> dict:
    """Reporting API `channel_reach_basic_a1`（`data/reach.jsonl`）。

    **サムネのインプレッションは「ショート以外の面」の広さ**です。ショートの
    フィードはこの数に入りません（実測: 再生 1,257/日 に対しインプレッション 145/日）。
    **だから CTR の腕が効く範囲は、ショート以外の面のぶんだけ**です。
    """
    rows = _jsonl("reach.jsonl")
    if not rows:
        return {"ok": False}
    days = sorted({r["date"] for r in rows})
    imp = sum(int(r.get("video_thumbnail_impressions", 0) or 0) for r in rows)
    ctr_w = sum(int(r.get("video_thumbnail_impressions", 0) or 0)
                * float(r.get("video_thumbnail_impressions_ctr", 0) or 0) for r in rows)
    per_video_imp = collections.Counter()
    for r in rows:
        per_video_imp[r["video_id"]] += int(r.get("video_thumbnail_impressions", 0) or 0)
    return {
        "ok": True, "days": days, "n_days": len(days), "rows": len(rows),
        "impressions": imp, "imp_per_day": imp / len(days),
        "ctr": ctr_w / imp if imp else None,
        "clicks_per_day": (ctr_w / len(days)) if imp else 0.0,
        "top": per_video_imp.most_common(5),
    }


def retention() -> dict:
    """維持率カーブ。**落ちる位置が秒でそろうか割合でそろうか**の検定。

    `scripts/retention.py` が印字する検定を、軌跡から読める形で持ち直します。
    **そろうほうが、尺を動かしたときに効く物差し**です。
    """
    p = DATA / "retention.json"
    if not p.exists():
        return {"ok": False}
    cur = json.loads(p.read_text(encoding="utf-8"))
    secs, fracs = [], []
    for pts in cur.values():
        if not pts or len(pts) < 10:
            continue
        # pts は [割合, audienceWatchRatio, 累積] の並び。最大の落差の位置を探す
        drops = []
        for a, b in zip(pts, pts[1:]):
            drops.append((a[1] - b[1], b[0]))
        if not drops:
            continue
        _, at_frac = max(drops)
        fracs.append(at_frac)
    if len(fracs) < 5:
        return {"ok": False}
    return {"ok": True, "n": len(fracs),
            "frac_lo": min(fracs), "frac_hi": max(fracs),
            "frac_cv": statistics.pstdev(fracs) / statistics.mean(fracs)}


# ----------------------------------------------------------------------------
# 6. 段を組む
# ----------------------------------------------------------------------------

def stages(vs, day, ident, dec, pv, sup, tr, sb, tf, rc, today) -> dict:
    """**段を飛ばさずに並べる。**

    恒等式が閉じているので、軌跡は「いまの再生 × 伸び率」ではありません。
    **供給と V の2つを、それぞれの実測の天井へ動かすこと**が軌跡の全部です。
    そこに RPM を掛けて初めて「月20万に届くか」が決まります。

    **供給の天井は API の日枠ではありません。** 日枠は 92本/日 ですが、
    出す題材が 1日 いくつ増えるかがその手前にあり、**低いほうが天井**です。
    """
    V = pv["mean"]
    V_cap = pv["best24"] or V
    mat = (sup.get("material") or {}).get("per_day")
    bld = sup.get("build") or {}

    sup_hist = ident["supply"] if ident.get("ok") else None      # 過去14日の実績
    sup_sched = sup["sustained"] if sup.get("ok") else sup_hist  # 予約の実物
    sup_api = UPLOAD_CAP_PER_DAY
    sup_cap = min(sup_api, mat) if mat else sup_api              # 持続できる供給の天井
    sup_cap_why = "題材の生成速度" if (mat and mat < sup_api) else "API の日枠"

    views_hist = tr.get("mean_views_day") or 0.0
    views_sched = sup_sched * V if sup_sched else 0.0
    cap_v_now = sup_cap * V                     # 供給だけ天井・V はいまのまま
    cap_both = sup_cap * V_cap                  # どちらも天井
    cap_api_both = sup_api * V_cap              # 題材が足りたとして、日枠まで

    def yen(views_day: float, rpm: float) -> float:
        return views_day * REVENUE_WINDOW_DAYS / 1000 * rpm

    def breakeven(views_day: float) -> float:
        m = views_day * REVENUE_WINDOW_DAYS
        return TARGET_YEN * 1000 / m if m else float("inf")

    # --- 月20万に要る再生（形べつ）---
    need = {}
    for form, band in (("ショート", RPM_SHORTS), ("長尺 お金", RPM_LONG)):
        for lab, rpm in band.items():
            need[f"{form} {lab}"] = {
                "form": form, "rpm": rpm,
                "views_month": TARGET_YEN * 1000 / rpm,
                "views_day": TARGET_YEN * 1000 / rpm / REVENUE_WINDOW_DAYS,
            }

    # --- 門2b（ショート90日1,000万）---
    gate2b_day = SHORTS_VIEWS_GATE / 90
    gate2b_yen = {lab: yen(gate2b_day, rpm) for lab, rpm in RPM_SHORTS.items()}
    be_gate2b = breakeven(gate2b_day)      # 門2b の水準で月20万を名乗れる最低の RPM
    # 門2b を通る水準に要る V（供給を日枠いっぱいに置いたとき）
    V_for_gate2b = gate2b_day / sup_api
    # 門2b を通る水準に要る題材（V を実測の天井に置いたとき）
    mat_for_gate2b = gate2b_day / V_cap

    # --- 門1（登録者1,000人）---
    def subs_days(vd: float) -> dict:
        out = {}
        for lab, rate in (("実測", sb["rate"]), ("下端", sb["rate_lo"]), ("上端", sb["rate_hi"])):
            r = vd * (rate or 0)
            out[lab] = (sb["remaining"] / r) if r > 0 else None
        return out

    # --- 段を積んだ日付 ---
    #     門2b は「直近90日で1,000万」なので、その水準を90日ぶん保つ必要があります。
    #     そこから審査（[代用] 30日）、さらに収益の30日。**前借りできません。**
    floor_days = 90 + MONETIZE_REVIEW_DAYS + REVENUE_WINDOW_DAYS
    gate2b_reachable = cap_both >= gate2b_day
    gate2b_reachable_api = cap_api_both >= gate2b_day

    # --- 倍率の分解（予約の実物 → 門2b の水準）---
    R_total = gate2b_day / views_sched if views_sched else None
    R_supply = sup_api / sup_sched if sup_sched else None
    R_V = V_for_gate2b / V if V else None
    R_supply_have = (sup_cap / sup_sched) if sup_sched else None   # 材料の天井まで
    R_supply_need = (sup_api / sup_cap) if sup_cap else None       # 日枠まで（材料が要る）

    non_shorts_day = tf["non_shorts"] / ident["span"] if ident.get("ok") else None
    long_views_need = LONG_HOURS_GATE * 60 / 2.8                   # [代用] 尺7分・維持40%

    return {
        "V": V, "V_cap": V_cap, "V_cap_ratio": (V_cap / V) if V else None,
        "supply_hist": sup_hist, "supply_sched": sup_sched,
        "supply_api": sup_api, "supply_cap": sup_cap, "supply_cap_why": sup_cap_why,
        "material_per_day": mat, "build_per_hour": bld.get("per_hour"),
        "views_hist": views_hist, "views_sched": views_sched,
        "cap_v_now": cap_v_now, "cap_both": cap_both, "cap_api_both": cap_api_both,
        "cap_v_now_month": cap_v_now * 30, "cap_both_month": cap_both * 30,
        "cap_api_both_month": cap_api_both * 30,
        "yen_cap_both": {l: yen(cap_both, r) for l, r in RPM_SHORTS.items()},
        "yen_cap_api": {l: yen(cap_api_both, r) for l, r in RPM_SHORTS.items()},
        "be_cap_both": breakeven(cap_both), "be_cap_api": breakeven(cap_api_both),
        "need": need,
        "gate2b_day": gate2b_day, "gate2b_yen": gate2b_yen, "be_gate2b": be_gate2b,
        "gate2b_reachable": gate2b_reachable, "gate2b_reachable_api": gate2b_reachable_api,
        "V_for_gate2b": V_for_gate2b, "mat_for_gate2b": mat_for_gate2b,
        "subs_sched": subs_days(views_sched), "subs_cap": subs_days(cap_v_now),
        "subs_gate2b": subs_days(gate2b_day),
        "floor_days": floor_days,
        "floor_date": (today + dt.timedelta(days=floor_days)).isoformat(),
        "R_total": R_total, "R_supply": R_supply, "R_V": R_V,
        "R_supply_have": R_supply_have, "R_supply_need": R_supply_need,
        "non_shorts_day": non_shorts_day, "long_views_need": long_views_need,
        "long_days_at_now": (long_views_need / non_shorts_day) if non_shorts_day else None,
    }


# ----------------------------------------------------------------------------
# 印字
# ----------------------------------------------------------------------------

def _d(days: float | None, today: dt.date) -> str:
    if days is None or days != days or days == float("inf"):
        return "**届きません**"
    return f"{days:,.0f}日後（{(today + dt.timedelta(days=round(days))).isoformat()}）"


def render(m: dict, today: dt.date) -> list[str]:
    out: list[str] = []
    P = out.append
    ident, dec, pv, sup = m["identity"], m["decay"], m["per_video"], m["supply"]
    tr, sb, tf, rc, st = m["trend"], m["subs"], m["traffic"], m["reach"], m["stages"]
    rt = m["retention"]
    bld, mat = sup.get("build") or {}, sup.get("material") or {}

    # ==== 最初の3行（`eta.py` にならって、頭と尻に同じ字で出します）============
    def headline() -> list[str]:
        h = []
        h.append(f"### **月20万の床: {st['floor_date']}**（{st['floor_days']}日後）"
                 " …… **門2b の90日 ＋ 審査30日 ＋ 収益の30日。前借りできない部分だけ**")
        if st["gate2b_reachable"]:
            h.append("### この床に乗るには **実測の天井まで出しきれば足ります**"
                     f"（供給 {st['supply_cap']:.0f}本/日 × V {st['V_cap']:,.0f}回）")
        elif st["gate2b_reachable_api"]:
            h.append(f"### [!] **いまの実測の天井では床に乗れません。** "
                     f"律速は**{st['supply_cap_why']}** —— "
                     f"題材 {st['material_per_day']:.0f}件/日 → **{st['mat_for_gate2b']:.0f}件/日"
                     f"（×{st['mat_for_gate2b']/st['material_per_day']:.1f}）**が要ります")
        else:
            h.append("### [!] **API の日枠まで出しても、実測の V では門2b に届きません**"
                     f"（要る V {st['V_for_gate2b']:,.0f}回 ／ 実測の天井 {st['V_cap']:,.0f}回）")
        h.append(f"### そのうえで **月20万を名乗れるのは RPM が ¥{st['be_gate2b']:.0f} 以上のときだけ**"
                 f"（門2b の水準 ＝ 月 {st['gate2b_day']*30:,.0f}回 のとき）。"
                 "**RPM は [未測定]** —— 収益化するまで自分の数字が出ません")
        return h

    P("=" * 74)
    for line in headline():
        P(line)
    P("=" * 74)
    P("")
    P("=" * 74)
    P("### **月20万までの軌跡**（実測だけで立てる。埋められない所は「未測定」と名指しします）")
    P("=" * 74)
    P("")

    # -- 0. 骨格 --------------------------------------------------------------
    P("--- 0. **骨格 —— これは模型ではなく帳尻です** ---")
    P("")
    P("    チャンネルの日次再生 ＝ 供給（本/日） × 1本あたり生涯再生 V")
    P("")
    if ident.get("ok"):
        P(f"  [実測] 検算 {ident['lo']}〜{ident['hi']}（{ident['span']}日・Analytics が日次を返す全期間）")
        P(f"         その窓に公開した {ident['n_videos']}本の**生涯再生の合計** {ident['lifetime_sum']:,}")
        P(f"         Analytics の同じ窓の**再生合計**          {ident['analytics_sum']:,}")
        P(f"         → 差 **{ident['gap']*100:+.1f}%**。**閉じます。**")
        P("")
        P("  **閉じるということは、その窓の再生が全部その窓に公開した本のものだ**ということです。")
        P("  **後ろカタログが1回も効いていません。**")
    if dec.get("frac24_median") is not None:
        P(f"  [実測] 1本の生涯再生のうち、**公開24時間以内に来る割合 {dec['frac24_median']*100:.1f}%**"
          f"（中央値・n={dec['frac24_n']}）")
    if dec.get("curve"):
        P("  [実測] 齢べつの「再生/日」:")
        for c in dec["curve"][:6]:
            P(f"           齢 {c['age_days']:>2}日  n={c['n']:>3}  中央値 {c['median']:>7.1f} 回/日"
              f"   平均 {c['mean']:>8.1f}")
        P("         → **齢2日を超えた本は、中央値で 0.0 回/日。**")
    P("")
    P("  **だから、複利で伸びる項が実測の中に1つもありません。**")
    P("  伸ばせるのは **供給** と **V** の2つだけ。どちらにも実測の天井があります。")
    P("")

    # -- 1. 伸び率 ------------------------------------------------------------
    P("--- 1. **`growth_per_day` の 5.38%/日 は、区間を付けると 0 と区別がつきません** ---")
    P("")
    if tr.get("ok"):
        P(f"  [実測] 日次再生の log 線形回帰（{tr['first']}〜{tr['last']}・n={tr['n']}日）")
        P(f"         傾き **1日 {tr['g']*100:+.2f}%**   t = **{tr['t']:.2f}**"
          f"   → {'**有意**' if tr['significant'] else '**有意ではありません（0 と区別がつかない）**'}")
        P(f"         95%区間: 1日 {tr['lo']*100:+.2f}% 〜 {tr['hi']*100:+.2f}%")
        P(f"         **これを100日ぶん複利で伸ばすと** 区間は "
          f"**{tr['blowup_lo']:.3g}倍 〜 {tr['blowup_hi']:.3g}倍**（**桁で9つぶん**）")
        P("         → **点推定だけを100日ぶん伸ばすと、開きが1つの項で埋まってしまいます。**")
        P("           `eta.py` の軌跡が段を飛ばすのは、ここが原因です。")
        P("         **この道具は伸び率を1回も使いません。** 使うのは供給と V の2つだけ。")
    P("")

    # -- 2. V -----------------------------------------------------------------
    P("--- 2. **V（1本あたり生涯再生）** ---")
    P("")
    if pv.get("ok"):
        P(f"  [実測] 平均 **{pv['mean']:.0f}回** ／ 中央値 {pv['median']:.0f}回"
          f"（n={pv['n']}本・齢{MATURE_AGE_DAYS:.0f}日以上）")
        P(f"         平均の95%区間（bootstrap 4,000）: **{pv['ci_lo']:.0f} 〜 {pv['ci_hi']:.0f}**")
        P(f"  [実測] **分布は二山**です。空振り（生涯{DUD_VIEWS}回未満）**{pv['dud_n']}/{pv['n']}本"
          f" ＝ {pv['dud_rate']*100:.0f}%**、当たった本は中央値 {pv['hit_median']:.0f}回")
        P("         → **「V を上げる」には、天井の違う2つの作業があります。**")
        P(f"           (a) 空振りを 0 にする …… **×{1/(1-pv['dud_rate']):.2f} が上限**。ここは自分で決められる")
        P("           (b) 当たった本をもっと回す …… フィードの判断。**上限は下の実測**")
        if pv.get("best24"):
            P(f"  [実測] **チャンネル内の天井: 24時間で {pv['best24']:,}回**"
              f"（平均の **×{pv['ceiling_ratio']:.2f}**）")
            P("         同じ作り・同じ機械が出して、実際にそこまで行った本があります。")
            P("         **よそから借りた天井ではありません。**")
    P("")

    # -- 3. 供給 --------------------------------------------------------------
    P("--- 3. **供給（本/日）—— 天井は API の日枠ではありません** ---")
    P("")
    if sup.get("ok"):
        P(f"  [実測] 予約の実物: **{sup['scheduled']}本 / {sup['span_days']}日"
          f"（{sup['first']}〜{sup['last']}）＝ 持続 {sup['sustained']:.1f}本/日**")
        P(f"         25本/日 以上が並んでいるのは **{sup['dense_days']}日だけ**（山は {sup['peak']}本/日）")
        P("         → **`eta.py` の `density_month` 25.0本/日 は、7日で切れる山の値です。**")
        by = sup["by_day"]
        ks = sorted(by)
        P("         予約の形: " + " ".join(f"{k[5:]}:{by[k]}" for k in ks[:14])
          + (" …" if len(ks) > 14 else ""))
    P("")
    P("  **供給の天井を決める3つを、それぞれ別に測ります:**")
    if bld.get("ok"):
        P(f"    [実測] 作る能力 **{bld['per_hour']:.1f}本/時**"
          f"（成功 {bld['built']}本 / wall {bld['hours']:.1f}時間・成功率 {bld['success']*100:.0f}%）")
        P(f"           → {UPLOAD_CAP_PER_DAY}本 作るのに **{bld['hours_for_cap']:.1f}時間**。"
          "**ここは律速ではありません**")
    P(f"    [実測] API の日枠 **{UPLOAD_CAP_PER_DAY}本/日**（`data/upload_cap.jsonl` の 429）")
    if mat.get("ok"):
        thin = "  [!] **窓が {:.1f}時間しかありません**（この軌跡でいちばん薄い実測）".format(
            mat["span_hours"]) if mat.get("thin") else ""
        P(f"    [実測] **題材が増える速さ {mat['per_day']:.1f}件/日**"
          f"（`sweep_novel` {mat['delta']:+d}件 / {mat['span_hours']:.1f}時間・点 {mat['n_points']}）{thin}")
        P(f"           在庫は {mat['stock_novel']}件 ＝ {UPLOAD_CAP_PER_DAY}本/日 なら "
          f"**{mat['stock_novel']/UPLOAD_CAP_PER_DAY:.1f}日で尽きます**。"
          "在庫が尽きたあとは、この速さが供給そのものです")
    P("")
    P(f"  → **持続できる供給の天井 = {st['supply_cap']:.1f}本/日**"
      f"（律速は **{st['supply_cap_why']}**）")
    P("")

    # -- 4. 面 ----------------------------------------------------------------
    P("--- 4. **再生がどこから来ているか（面）** ---")
    P("")
    P(f"  [実測] 流入 n={tf['total']:,}回:")
    for k, n in list(tf["src"].items())[:6]:
        P(f"           {k:<22} {n:>8,}回  {n/tf['total']*100:>5.1f}%")
    P(f"  → **ショートのフィードが {tf['shorts_share']*100:.1f}%。**"
      f" それ以外は全部合わせて {tf['non_shorts']:,}回"
      + (f" ＝ **1日 {st['non_shorts_day']:.0f}回**" if st.get("non_shorts_day") else ""))
    P("    **長尺が生きられるのは、この 1日数十回の面だけです。**")
    if rc.get("ok"):
        P("")
        P(f"  [実測] サムネのインプレッション（Reporting API `channel_reach_basic_a1`・"
          f"{rc['days'][0]}〜{rc['days'][-1]}・{rc['n_days']}日・{rc['rows']}行）")
        P(f"         **1日 {rc['imp_per_day']:.0f} インプレッション ／ CTR {rc['ctr']*100:.2f}%"
          f" → クリック 1日 {rc['clicks_per_day']:.1f}回**")
        P("         → **サムネと題の腕が効くのは、この1日1回未満のクリックのぶんだけ。**")
        P("           ショートのフィードはこの数に入りません。**サムネを作り直しても軌跡は動きません。**")
        P("           （8/14 にジョブを作ってから、この数を取りに来たのは 2026-08-20 が初めてです）")
    if rt.get("ok"):
        P("")
        P(f"  [実測] 維持率カーブ n={rt['n']}本 —— **いちばん大きい落差の位置**は")
        P(f"         割合で見ると {rt['frac_lo']*100:.0f}〜{rt['frac_hi']*100:.0f}%"
          f"（ばらつき {rt['frac_cv']:.2f}）")
        P("         `scripts/retention.py` の検定: **秒のほうがそろっています"
          "（4.8〜8.6秒・ばらつき 0.15）**")
        P("         → **尺を縮めても、落ちる時刻は動きません。** 8/19 の仮説はこの向きに不利。")
        P("           **V を上げる手として『短くする』は、実測で否定されました。**")
    P("")

    # -- 5. 登録率 ------------------------------------------------------------
    P("--- 5. **登録率** ---")
    P("")
    P(f"  [実測] 純増 **{sb['net']}人** / 再生 {sb['views']:,}回 → **{sb['rate']*100:.4f}%**")
    P(f"         95%区間（Poisson・k={sb['net']}）: **{sb['rate_lo']*100:.4f}% 〜 {sb['rate_hi']*100:.4f}%**"
      f"（**上下 {sb['rate_hi']/sb['rate_lo']:.1f}倍**）")
    P(f"         → **9人しか居ません。** 門1 の日付はこの {sb['rate_hi']/sb['rate_lo']:.1f}倍がそのまま効きます。")
    P("")

    # -- 6. 未測定 ------------------------------------------------------------
    P("--- 6. **未測定（代用も置きません）** ---")
    P("")
    P("  [未測定] **このチャンネルの RPM。** 収益化前なので自分の数字が1つもありません。")
    P(f"           使っているのは [代用] ショート ¥{RPM_SHORTS['低']}〜¥{RPM_SHORTS['高']} ／ "
      f"長尺お金 ¥{RPM_LONG['低']:,}〜¥{RPM_LONG['高']:,}（業界の幅）")
    P("  [未測定] **収益化した後の積み上がり方。** 審査30日は [代用]（YouTube 公表「通常1か月以内」）")
    P("  [未測定] **供給を上げたときに V が保つか。** 実測があるのは 4本/日 まで。")
    P("           **2026-08-20 に 25本/日 を実際に出しています。Analytics は日次で3日遅れなので、")
    P("           2026-08-23 にこの1点が出ます。** 軌跡でいちばん大きい可動部がそこで1つ埋まります。")
    P("  [未測定] **長尺の実力。** n=5・生涯合計11回。ただし上の面の実測が示すとおり、")
    P("           **そもそも長尺を見せる面が 1日数十回しかありません。**")
    P("           **『長尺は弱い』ではなく『長尺を見せる面が無い』** —— この2つは別のことです。")
    P("  [未測定] **登録者が増えたとき、ショート以外の面がどれだけ広がるか。** 9人では測れません。")
    P("           **門2a（長尺4,000時間）は、まるごとこの未測定の上に乗っています。**")
    P("")

    # -- 7. 段 ----------------------------------------------------------------
    P("=" * 74)
    P("### **段（飛ばさずに並べる）**")
    P("=" * 74)
    P("")
    P("  **段0 いま**")
    P(f"      [実測] 実績（直近{tr['n']}日）    {st['views_hist']:,.0f}回/日"
      f"  ＝ 供給 {st['supply_hist']:.1f}本/日 × V {st['V']:.0f}回")
    P(f"      [実測] 予約どおりなら        {st['views_sched']:,.0f}回/日"
      f"  ＝ 供給 {st['supply_sched']:.1f}本/日 × V {st['V']:.0f}回")
    P(f"      **予約を入れ替えただけで ×{st['views_sched']/st['views_hist']:.1f}。**"
      "これは既に済んでいて、Analytics に出るのはこれからです")
    P("")
    P("  **段1 供給を、持続できる天井まで**")
    P(f"      いま {st['supply_sched']:.1f}本/日 → **{st['supply_cap']:.1f}本/日**"
      f"（×{st['R_supply_have']:.1f}）")
    P(f"      律速: **{st['supply_cap_why']}**"
      + (f" {st['material_per_day']:.1f}件/日" if st.get("material_per_day") else ""))
    P(f"      そこでの日次再生 **{st['cap_v_now']:,.0f}回/日**（V はいまのまま）")
    P("")
    P("  **段2 V を、チャンネル内の天井まで**")
    P(f"      いま {st['V']:.0f}回 → **{st['V_cap']:,.0f}回**（×{st['V_cap_ratio']:.2f}）")
    P(f"      そこでの日次再生 **{st['cap_both']:,.0f}回/日 ＝ 月 {st['cap_both_month']:,.0f}回**")
    P(f"      [実測] この天井は「同じ機械が実際に出した最大」です。**外挿ではありません**")
    P("")
    P("  **段3 門1（登録者1,000人）**")
    P(f"      合格点: あと {sb['remaining']:,}人")
    for lab, dd in (("予約どおりなら", st["subs_sched"]),
                    ("段1 まで来たら", st["subs_cap"]),
                    ("門2b の水準なら", st["subs_gate2b"])):
        P(f"      {lab:<12}: {_d(dd['実測'], today)}"
          f"   （区間 {_d(dd['上端'], today)} 〜 {_d(dd['下端'], today)}）")
    P("      → **門1 は、この軌跡では律速になりません。** 門2b の水準に届けば20日ほどで通ります")
    P("")
    P("  **段4 門2 —— どちらの扉を開けるか**")
    P("")
    P(f"      [門2b] ショート90日で1,000万回 ＝ **{st['gate2b_day']:,.0f}回/日 を 90日**")
    P(f"             段2 まで来たときの {st['cap_both']:,.0f}回/日 に対し "
      f"**{st['gate2b_day']/st['cap_both']:.2f}倍**"
      f" → {'**天井の内側**' if st['gate2b_reachable'] else '[!] **天井の外**'}")
    if not st["gate2b_reachable"]:
        P(f"             **足りないのは題材です。** V を天井 {st['V_cap']:,.0f}回 に置いても、")
        P(f"             要る供給は **{st['mat_for_gate2b']:.0f}本/日** ——"
          f" いま作れているのは {st['material_per_day']:.1f}件/日 で **×"
          f"{st['mat_for_gate2b']/st['material_per_day']:.1f}** 要ります")
        P(f"             （API の日枠 {UPLOAD_CAP_PER_DAY}本/日 の内側なので、"
          "**枠ではなく材料の問題**です）")
    P(f"             **この門を通ったときの月の再生 {st['gate2b_day']*30:,.0f}回**。つまり:")
    for lab, y in st["gate2b_yen"].items():
        P(f"               RPM ¥{RPM_SHORTS[lab]:>3} なら **¥{y:,.0f}/月**"
          f"  {'**目標に届く**' if y >= TARGET_YEN else '届かない'}")
    P("             → **門2b を通れる水準と、月20万の水準は、ほぼ同じ場所にあります。**")
    P("               **ショートで行くなら、収益化と目標は別の段ではありません。**")
    P("               （`eta.py` が『収益化の門＋30日』を縛りに出すのは、この一致の裏返しです。")
    P("                 縛りの名前は合っていて、**そこに至る段が抜けていた**だけでした）")
    P("")
    P(f"      [門2a] 長尺で {LONG_HOURS_GATE:,}時間 ＝ {LONG_HOURS_GATE*60:,}分")
    P(f"             [代用] 尺7分・維持40%（1再生 2.8分）→ **長尺 {st['long_views_need']:,.0f}回**")
    if st.get("long_days_at_now"):
        P(f"             [実測] ショート以外の面はいま **1日 {st['non_shorts_day']:.0f}回**（全部の本を合わせて）")
        P(f"             → その面のままなら **{st['long_days_at_now']:,.0f}日**。")
    P("             **この扉は、面が広がらないかぎり開きません。面が広がるかは [未測定]。**")
    P("             **だからこの軌跡は門2b で立てています。** 門2a を柱にすると、")
    P("             **柱が丸ごと未測定の上に乗ります。**")
    P("")
    P(f"  **段5 収益化の審査** [代用] {MONETIZE_REVIEW_DAYS}日（YouTube 公表「通常1か月以内」）")
    P("")
    P("  **段6 月20万**")
    P(f"      [実測] 段2 まで来たときの天井 月 {st['cap_both_month']:,.0f}回")
    for lab, y in st["yen_cap_both"].items():
        P(f"             RPM ¥{RPM_SHORTS[lab]:>3} → ¥{y:,.0f}/月"
          f"  {'**届く**' if y >= TARGET_YEN else '届かない'}")
    P(f"      → **分かれ目の RPM は ¥{st['be_cap_both']:.0f}**（段2 の天井で）／"
      f" **¥{st['be_gate2b']:.0f}**（門2b の水準で）／"
      f" **¥{st['be_cap_api']:.0f}**（題材が日枠 {UPLOAD_CAP_PER_DAY}本ぶん揃ったとき）")
    P("      **どちらも [未測定]。収益化するまで、この1つだけは測れません。**")
    P("")

    # -- 8. 日付 --------------------------------------------------------------
    P("=" * 74)
    P("### **日付**")
    P("=" * 74)
    P("")
    P("  **前借りできない部分だけを足したのが床です。**")
    P(f"      門2b の 90日 ＋ 審査 {MONETIZE_REVIEW_DAYS}日 ＋ 収益の {REVENUE_WINDOW_DAYS}日"
      f" ＝ **{st['floor_days']}日**")
    P(f"      → **床 = {st['floor_date']}**")
    P("")
    P("  **この床は「今日から門2b の水準で走り出せたら」の日付**です。")
    P("  走り出すまでの日数（段1・段2 に要る日数）は、そのぶん後ろに足してください。")
    P("  **その日数は [未測定] です** —— 題材の生成を上げるのに何日かかるかを、")
    P("  この機械はまだ一度も測っていません。**次の周で測れます**（`sweep_novel` の増分を毎周積む）。")
    P("")
    if not st["gate2b_reachable"]:
        P("  [!] **いまの実測の天井のままでは、床にすら乗れません。**")
        P(f"      要るのは題材 **×{st['mat_for_gate2b']/st['material_per_day']:.1f}**"
          f"（{st['material_per_day']:.1f}件/日 → {st['mat_for_gate2b']:.0f}件/日）")
        P(f"      と V **×{st['V_cap_ratio']:.2f}**（実測の天井いっぱい）。")
        P("      **どちらも『いつまでに』が未測定なので、床に足す日数が出せません。**")
        P("      **これが『届きません』ではないのは、要る倍率が両方とも桁の内側だからです。**")
    P("")

    # -- 9. 崩れる所 ----------------------------------------------------------
    P("--- **この軌跡がどこで崩れるか（次に測る4点。上から順に効きます）** ---")
    P("")
    P("  1. **供給 25本/日 で V が保つか。** 実測は 4本/日 まで。")
    P("     8/20 に 25本 出しているので、**2026-08-23 に答えが出ます。**")
    P(f"     保たないなら、段1 の ×{st['R_supply_have']:.1f} がその場で目減りします。")
    P("  2. **題材の生成速度。** いまの実測は窓が数時間しかありません"
      + (f"（{mat['span_hours']:.1f}時間・点 {mat['n_points']}）" if mat.get("ok") else "")
      + "。")
    P("     **供給の天井を決めているのはこの数で、この軌跡でいちばん薄い実測です。**")
    P("     `python -m src.supply --record` を毎周ぶん積むと、次の周から締まります。")
    P("  3. **RPM。** 収益化まで測れません。"
      f"**門2b の水準では ¥{st['be_gate2b']:.0f} を挟んで、届く／届かないが入れ替わります。**")
    P(f"     [代用] の幅はショート ¥{RPM_SHORTS['低']}〜¥{RPM_SHORTS['高']} なので、"
      "**幅の上端でちょうど届く**という位置です。**幅の真ん中なら届きません。**")
    P("  4. **登録率の 9人。** 区間が上下 "
      f"{sb['rate_hi']/sb['rate_lo']:.1f}倍。ただし門1 は律速ではないので、効くのは最後です。")
    P("")
    P("  **この4つ以外は、実測で埋まっています。**")
    P("")

    P("=" * 74)
    for line in headline():
        P(line)
    P("=" * 74)
    return out

# ----------------------------------------------------------------------------

def measure(today: dt.date) -> dict:
    vs = videos()
    day = daily_views()
    v = scan_values()
    ident = identity(vs, day)
    dec = decay(vs)
    pv = per_video(vs)
    sup = supply_now(today)
    tr = trend(day)
    sb = subs(v)
    tf = traffic(v)
    rc = reach()
    rt = retention()
    st = stages(vs, day, ident, dec, pv, sup, tr, sb, tf, rc, today)
    return {"identity": ident, "decay": dec, "per_video": pv, "supply": sup,
            "trend": tr, "subs": sb, "traffic": tf, "reach": rc,
            "retention": rt, "stages": st, "today": today.isoformat()}


def main() -> int:
    ap = argparse.ArgumentParser(description="月20万までの軌跡を、実測だけで立てる")
    ap.add_argument("--json", action="store_true", help="機械が読む形で出す")
    ap.add_argument("--at", default=None, help="今日の日付（YYYY-MM-DD）")
    args = ap.parse_args()
    today = dt.date.fromisoformat(args.at) if args.at else TODAY

    m = measure(today)
    if args.json:
        print(json.dumps(m, ensure_ascii=False, default=str, indent=1))
        return 0
    for line in render(m, today):
        print(line)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
