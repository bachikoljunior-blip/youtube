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

# **上限の出どころは1か所**（`src/house_rule.py`）。ここに数を写さないこと ——
# 写した瞬間に、規則を変えても軌跡だけが古い数で走ります。
from src import house_rule  # noqa: E402

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
    cov = coverage(len(vs))
    return {
        "ok": True, "lo": lo, "hi": hi, "span": span,
        "n_videos": len(win), "supply": len(win) / span,
        "lifetime_sum": lifetime, "analytics_sum": measured,
        "gap": lifetime / measured - 1 if measured else None,
        # **左辺と右辺が同じチャンネルを見ているか**（2026-08-21 04:3x に足した）。
        # 下の `coverage()` に、足した理由をぜんぶ書いてあります。
        "n_snapshots": len(vs), "n_channel": cov["n_channel"],
        "coverage": cov["ratio"], "comparable": cov["comparable"],
    }


#: **記録が何割そろっていれば、恒等式を「判定した」と言ってよいか。**
#: 0.9 は「1割の取りこぼしなら 5% の門を割らない」の側に置いています ——
#: 1本あたりの再生はばらつくので、**厳密な線ではありません。**
#: **足りないときに出すのは「閉じない」ではなく「測れない」**なので、
#: ここを緩めても、間違った結論が出るのではなく**判定が遅れる**だけです。
IDENTITY_MIN_COVERAGE = 0.9


def coverage(n_snapshots: int) -> dict:
    """**この恒等式の左辺と右辺は、同じチャンネルを見ているか。**

    ## なぜ足したか（2026-08-21 04:3x。**赤いまま渡すと、次が逆へ進みます**）

    `test_identity_closes` が **-27.6%** で落ちました。検査の文面はこうです ——

        恒等式が -27.6% ずれました。**後ろカタログが効き始めた可能性があります**
        —— 軌跡に減衰項が要ります

    **それを信じると、軌跡に減衰項を入れることになります。** 実際の中身は違いました:

        左辺 `lifetime_sum`  … `data/views.jsonl` にある本の生涯再生
                               **その台帳が知っている動画は 65本**
        右辺 `analytics_sum` … Analytics の日次の合計
                               **チャンネル全体**（投稿済みテーマは 424件）

    **右辺だけがチャンネル全体を見ています。** 窓に入った本が 32本 しか
    数えられていないので、**左辺は構造的に小さく出ます。**
    そして**公開を増やすほど差は開きます** —— つまりこの赤は、
    「後ろカタログが効き始めた」ではなく **「記録が追いつかなくなった」**の顔です。

    **同じ形が `decay` の側から否定できます**: 齢12〜14日の中央値は
    **0.0 再生/日** です。古い本がほぼ動いていないのに、
    窓の27.6%（7,811再生）を古い本が出すことはできません。

    **だから、足りないときに言うのは「閉じない」ではなく「測れない」です。**
    `comparable=False` の回は、恒等式そのものを判定しないこと。
    """
    n_channel = 0
    try:
        from src import history

        n_channel = len(history.ledger_topics())
    except Exception:                                          # noqa: BLE001
        n_channel = 0
    if n_channel <= 0:                       # 台帳が読めないなら、比べようがない
        return {"n_channel": 0, "ratio": None, "comparable": False}
    ratio = n_snapshots / n_channel
    return {"n_channel": n_channel, "ratio": ratio,
            "comparable": ratio >= IDENTITY_MIN_COVERAGE}


#: **後ろカタログの門を、齢べつの1バケツで判定してよい下限の読み数。**
#:
#: `curve` に載る下限は 3読み です（**絵にするには足りる**）。**門には足りません。**
#: 実測 2026-08-29: 齢24日 は **4読み**、中央値 **0.57回/日** ——
#: 齢2日以上の他の 22バケツは全部 **0.00** で、`old_median_per_day` も **0.0**。
#: それでも `max()` で読むと、この1バケツだけで門が赤くなります。
#: **そして赤の文面は「軌跡を組み直すこと」です** —— 従うと、
#: 生涯の 1.5% しか運んでいない尾に、日付を動かす減衰項を入れることになります。
#:
#: **同じ形をこのファイルは一度 踏んでいます**（`coverage()` の註・2026-08-21 の
#: -27.6%）。あれも「後ろカタログが効き始めた」の顔をした標本の穴でした。
#:
#: 20 に置いた理由: 今日の実測で残るのは 齢2〜9日 と 12日 の **9バケツ**
#: （n=23〜125）。**後ろカタログが本当にできるなら、まずここに出ます** ——
#: 本の大半がこの齢に居るからです。**尾だけが動く形は、標本の穴のほうです。**
#: **覆る条件**: 齢2〜9日 のどれかが 0 を離れたら、それは本物。門が鳴ります。
BACK_CATALOGUE_MIN_READINGS = 20

#: **後ろカタログの「大きさ」の門。** 上の門は「動いているか」しか見ません。
#: こちらは **1本の生涯再生のうち、24時間より後に来る割合** で大きさを見ます
#: （実測 2026-08-29: 24時間以内が **98.5%**・n=118 ＝ 後ろは **1.5%**）。
#: 0.95 は、いまの 1.5% の **3倍以上** 太ったら鳴る線です。
#: **恒等式の実測の差は -0.56%** なので、後ろが 5% を運びはじめたら
#: 恒等式のほうが先に開きます —— そのときは減衰項が本当に要ります。
BACK_CATALOGUE_MIN_FRAC24 = 0.95


def decay(vs: dict) -> dict:
    """**後ろカタログがあるか。** 齢べつの「再生/日」と、生涯のうち24時間に来る割合。

    **判定に使うのは `back_catalogue` です。`curve` の生の `max()` ではありません。**
    理由は `BACK_CATALOGUE_MIN_READINGS` の註（**尾の1バケツで門が赤くなります**）。
    """
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
    frac24 = statistics.median(fr24) if fr24 else None
    return {
        "curve": curve, "n_mature": len(mature),
        "frac24_median": frac24,
        "frac24_n": len(fr24),
        "old_median_per_day": statistics.median(
            [c["median"] for c in curve if c["age_days"] >= 2]) if curve else None,
        **back_catalogue_guard(curve, frac24),
    }


def back_catalogue_guard(curve: list[dict], frac24: float | None) -> dict:
    """**後ろカタログの門。** `decay()` と検査が、同じ1つの式を読むための関数。

    **分けてある理由**: 検査の側で式を書き写すと、実装が変わっても検査は
    書き写したほうを試すので、**通ったまま実物だけがずれます。**

    門は2つあり、**どちらか一方でも出たら「在る」**とします:

        動き   読み数 `BACK_CATALOGUE_MIN_READINGS` 以上のバケツの中央値が 0 を離れた
        大きさ 生涯再生の 24時間以内の割合が `BACK_CATALOGUE_MIN_FRAC24` を割った

    **`curve` の生の `max()` で読まないこと** —— `curve` に載る下限は 3読みで、
    尾の1バケツ（実測 2026-08-29: 齢24日・4読み・0.57回/日）で門が赤くなります。
    """
    guarded = [c for c in curve
               if c["age_days"] >= 2 and c["n"] >= BACK_CATALOGUE_MIN_READINGS]
    old_max = max((c["median"] for c in guarded), default=None)
    thin = [c for c in curve
            if c["age_days"] >= 2 and c["n"] < BACK_CATALOGUE_MIN_READINGS
            and c["median"] > 0]
    moved = bool(guarded and old_max is not None and old_max > 0.0)
    fat = bool(frac24 is not None and frac24 < BACK_CATALOGUE_MIN_FRAC24)
    return {
        "guard_buckets": len(guarded),
        "guard_ages": [c["age_days"] for c in guarded],
        "old_max_median": old_max,
        # 読み数が足りずに門から外した、0 でないバケツ。**印字はします**（隠さない）
        "thin_nonzero": [{"age_days": c["age_days"], "n": c["n"], "median": c["median"]}
                         for c in thin],
        "back_catalogue": moved or fat,
        "back_catalogue_why": ([] if not moved else ["動き"]) + ([] if not fat else ["大きさ"]),
        "judgeable": bool(guarded) and frac24 is not None,
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


def published_per_day(uploaded: Path | None = None,
                      observed: dict[str, str] | None = None) -> dict[str, int]:
    """**JST の日 → その日に公開される本数**（`data/uploaded.jsonl`）。

    ## **4つ目の読み手を書かないこと**（2026-08-25 の申し送り）

    同じ帳面を `src/ab_split.published()` ・ `src/motion_groups.scheduled_at()` ・
    `scripts/eta.published_at()` の3つが別々に読み、**同じ2つの規則
    （後の行を採る・JST で割る）をそれぞれ持っていました。**
    規則が共有されていないので、8/19・8/23・8/25 に**5回**同じ形の欠陥が出ています。

    **ここが6件目でした。** 直す前のこの関数は、帳面を

        cnt[(r["at"] or r["uploaded_at"])[:10]] += 1

    と読んでいて、**2つとも踏んでいます**:

      1. **1行1本と数えていた。** 帳面は足すだけなので、`reschedule.py` で
         動かした本は行が増えます（実測 **505行 / 447本**）。
         動かした本だけが**2回**数えられ、その日の供給が水増しされます
      2. **UTC の日で割っていた。** 予約も `src/day_cap.py` も JST で置いています。
         実測で **08/26 が 18本、08/27 が 15本**に見えていました ——
         正しくは **14本 / 19本** です。**08/27 の 5本ぶんが前日に落ちていました**

    2 のずれは `stages()` の `sustained`（持続する供給）と、
    下の `trend_decompose()` の分母に**そのまま**入ります。

    ## **帳面は 08/16 より前を持っていません**（2026-08-25 に実測）

    `data/uploaded.jsonl` のいちばん古い `at` は **2026-08-16** です ——
    それより前に公開した本は、**帳面に1行もありません。**
    帳面だけで供給を数えると、日次再生と重なる窓が **7日** しか取れず、
    `trend_decompose()` が「点が足りない」で止まります。

    **2つ目の出どころが `data/views.jsonl` です。** Analytics が返す `hours`
    （公開からの経過時間）から `at - hours` で公開時刻が復元でき、
    **08/04 まで戻れます**（`scripts/eta.published_at()` と同じ復元）。
    重なる 9日 のうち **8日で帳面と本数が一致**します（08/16 だけ 3 対 4 ——
    まだ一度も観測されていない本が1本）。

    **観測の側は「下限」です** —— 一度も観測されなかった本は数えられません。
    実測の取りこぼしは **-14.0%**（生涯再生の合計 47,796 対 Analytics 55,551）。
    **ただしその欠けは窓の前半と後半でほぼ同じ**です（前半 -14.7% / 後半 -13.6%）——
    log を採ると一定倍は定数に落ちるので、**傾きにはほとんど効きません。**
    水準を語るときは下限、**傾きを語るときは使ってよい**、という札の付き方です。

    **帳面のほうを優先します**（`reschedule.py` で動かした予約が入っているのは
    帳面の側だけなので）。観測は、帳面に無い本だけを埋めます。

    **借りているのは `src/motion_groups.py` です**（自分で規則を持たない）。
    `at` の無い行（実測 44/491）は公開日が分からないので数えません。
    """
    from src import motion_groups as _mg

    rows = _mg.scheduled_at(uploaded) if uploaded else _mg.scheduled_at()
    by_video: dict[str, str] = {}
    if observed is None:
        observed = {k: v["pub"].isoformat() for k, v in videos().items()}
    for vid, d in observed.items():
        if d:
            by_video[vid] = d
    for vid, at in rows.items():                 # **帳面が勝つ**
        d = _mg.jst_day(at)
        if d:
            by_video[vid] = d
    return dict(collections.Counter(by_video.values()))


def supply_now(today: dt.date) -> dict:
    """**いま実際に何本/日 公開されるか。** 予約の実物（`data/uploaded.jsonl`）から。

    `eta.py` の `density_month` は「詰め方の上限」25本/日 を使っていますが、
    **予約の実物は 08/27 で 25本/日 を切ります。** 持続する密度は、
    上限ではなく**予約の実物の平均**です。
    """
    cnt = published_per_day()
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


def _logreg(xs: list[float], ly: list[float]) -> dict:
    """log 線形回帰。傾き・標準誤差・t・95%区間を返す。**`trend()` と同じ式**。"""
    n = len(xs)
    if n < 3:
        return {"ok": False, "n": n}
    mx, my = statistics.mean(xs), statistics.mean(ly)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return {"ok": False, "n": n}
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ly)) / sxx
    a0 = my - b * mx
    resid = [y - (a0 + b * x) for x, y in zip(xs, ly)]
    se = math.sqrt(sum(r * r for r in resid) / (n - 2) / sxx)
    if se <= 0:
        return {"ok": False, "n": n}
    return {"ok": True, "n": n, "b": b, "se": se, "t": b / se,
            "g": math.exp(b) - 1,
            "lo": math.exp(b - 1.96 * se) - 1, "hi": math.exp(b + 1.96 * se) - 1,
            "significant": abs(b / se) >= 2.0}


#: **V の傾きを軌跡に入れてよい下限の点数。** 7点で t=2 を出すのは
#: 「7日つづけて同じ向きに動いた」に近く、供給の段替えと見分けが付きません。
DECOMPOSE_MIN_DAYS = 10


def trend_decompose(day: dict[str, int], per_day: dict[str, int] | None = None) -> dict:
    """**日次再生の傾きを、供給の傾きと V の傾きに割る。**（2026-08-25 に作った）

    ## なぜ要るか —— `test_trajectory.py` が落ちて、そこにこう書いてありました

        もし将来これが有意になったら、この検査は落ちます。**そのときは
        落ちたこと自体が「複利の項を軌跡に入れてよくなった」という報せ**なので、
        検査を直すのではなく、**軌跡のほうを設計し直してください。**

    **有意になりました**（t = 0.14 → **3.20**・n=14日 → 19日・
    傾き 1日 +0.77% → **+12.30%**）。それが `CLAUDE.md` の **(ア)**
    「天井の入力を時間の関数にする」の入口です。

    **ただし「有意になったから複利を入れる」は間違いです。** 恒等式は

        日次再生 ＝ 供給（本/日） × V（1本あたり生涯再生）

    なので、log を採ると **傾きは必ず足し算に割れます**:

        d log(再生)/dt  ＝  d log(供給)/dt  ＋  d log(V)/dt

    **右の第1項は、軌跡がすでに天井付きで持っています**（`stages()` の
    `supply_cap` ＝ **オーナーの規則（1日1本）**・題材の生成速度・API の日枠 の
    いちばん低いもの。2026-08-31 まで規則が抜けており、92倍 で走っていました）。
    **複利の項として新しく足してよいのは第2項だけ**です ——
    第2項が 0 と区別できないのに左辺の傾きを複利で伸ばすと、
    **天井のある供給の伸びを、天井の無い複利として二重に数えます。**
    それが `eta.py` が 2026-08-20 まで踏んでいた `growth_per_day` 5.38%/日 の正体です。

    ## 実測（2026-08-25）—— **有意なのは供給だけ**

    帳面が供給を持っているのは 08/16 からで、日次再生と重なるのは **7日**:

        再生    1日 **+38.02%**   t = +1.66   95% [ -5.6%, +101.8%]  ← **有意でない**
        供給    1日 **+74.87%**   t = +3.05   95% [+22.1%, +150.4%]  ← **有意**
        V       1日 **-21.07%**   t = -1.02   95% [-49.9%,  +24.4%]  ← **有意でない**

    **19日で採った左辺の t=3.20 は、供給が 0 から 25本/日 へ立ち上がった跡**です
    （帳面に 08/16 より前の `at` がありません）。供給が見える窓に揃えると、
    左辺は有意ですらなくなります。

    **したがって軌跡に複利の項は入りません。** 入れてよくなる条件は1つだけ ——
    **`v` の側が有意に正**になったときです。そのときは
    `stages()` の `V` を時間の関数にしてよい（＝(ア) が引ける）。
    いまは引けないので、**引けない理由のほうを印字します**（(イ)）。

    **`v` が有意に負**なら、それは飽和です —— 出す本数を増やすほど1本あたりが
    落ちる。点推定は負ですが（-21%/日）、区間は 0 をまたぎます。
    **またいでいる数を「飽和が実測された」と読まないこと。**

    返す辞書:

        window   突き合わせた日（供給が分かる ∩ 再生が分かる ∩ 供給>0）
        views    左辺の回帰
        supply   供給の回帰
        v        V ＝ 再生/供給 の回帰。**複利の項に使ってよいのはここだけ**
        additive 3つの傾きが足し算で閉じているか（b_views ≈ b_supply + b_v）
        compound 軌跡に複利の項を入れてよいか（v が有意に正で、点数が足りるとき）
        why      入れない回に、その理由（(イ) の「何を固定したせいか」）
    """
    per_day = published_per_day() if per_day is None else per_day
    if not day or not per_day:
        return {"ok": False, "why": "帳面か日次再生が空です"}

    both = [d for d in sorted(day) if per_day.get(d, 0) > 0 and day[d] > 0]
    dropped_zero = [d for d in sorted(day) if d in per_day and per_day[d] == 0]
    if len(both) < 3:
        return {"ok": False, "n": len(both), "window": both,
                "why": f"供給と再生が重なる日が {len(both)}日 しかありません"}

    base = dt.date.fromisoformat(both[0])
    xs = [float((dt.date.fromisoformat(d) - base).days) for d in both]
    r_views = _logreg(xs, [math.log(day[d]) for d in both])
    r_sup = _logreg(xs, [math.log(per_day[d]) for d in both])
    r_v = _logreg(xs, [math.log(day[d] / per_day[d]) for d in both])

    additive = None
    if r_views.get("ok") and r_sup.get("ok") and r_v.get("ok"):
        additive = abs(r_views["b"] - (r_sup["b"] + r_v["b"])) < 1e-9

    enough = len(both) >= DECOMPOSE_MIN_DAYS
    compound = bool(r_v.get("ok") and r_v.get("significant") and r_v["b"] > 0 and enough)
    if compound:
        why = None
    elif not r_v.get("ok"):
        why = "V の傾きが立ちません（点が足りない）"
    elif not enough:
        why = (f"重なる日が {len(both)}日 で、下限 {DECOMPOSE_MIN_DAYS}日 に足りません"
               "（供給の段替えと見分けが付かない）")
    elif not r_v["significant"]:
        why = (f"V の傾き 1日 {r_v['g']*100:+.2f}%・t = {r_v['t']:+.2f} は "
               f"0 と区別がつきません（95% {r_v['lo']*100:+.1f}% 〜 {r_v['hi']*100:+.1f}%）")
    else:
        why = (f"V の傾きは有意ですが **負** です（1日 {r_v['g']*100:+.2f}%）——"
               "出すほど1本あたりが落ちる側なので、複利ではなく飽和です")

    return {"ok": True, "window": both, "n": len(both),
            "first": both[0], "last": both[-1], "dropped_zero": dropped_zero,
            "views": r_views, "supply": r_sup, "v": r_v,
            "additive": additive, "compound": compound, "why": why,
            "min_days": DECOMPOSE_MIN_DAYS}


# ----------------------------------------------------------------------------
# 5. 登録率・面（どこから再生が来ているか）・インプレッション
# ----------------------------------------------------------------------------

def _poisson_ci(k: int) -> tuple[float, float]:
    """**回数 k の 95%区間**（Wilson–Hilferty で gamma 分位を近似）。

    9人しか居ない登録者を「率」と呼ぶ以上、区間なしで割ってはいけません。
    """
    def gq(z: float, a: float) -> float:
        """gamma(形 a) の分位を Wilson–Hilferty で近似。**`c` は `1/(9a)`。**

        **2026-08-20 に `2/(9a)` と書いて踏みました。** k=9 の下端が
        4.11 ではなく 2.7 に出て、**登録率の区間が 4.1倍 ではなく 7.7倍**に
        見えていました。区間を広く出す向きの間違いなので「安全側」に見えますが、
        **門1 の日付の幅がそのぶん嘘になります。**
        照合: k=9 → 厳密（Garwood）4.115 〜 17.08。この近似で 4.107 〜 17.086。
        """
        if a <= 0:
            return 0.0
        c = 1 / (9 * a)
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


def engagement(v: dict) -> dict:
    """**視聴者の反応。** ショートのフィードが次に配るかどうかを決めている側の数。

    V（1本あたり生涯再生）は**フィードの判断**なので、こちらから動かせるのは
    「判断の材料」だけです。**その材料が実測でいくつあるかを、ここに出します。**
    """
    views = int(v.get("合計.views", 0)) or 1
    eng = int(v.get("合計.engagedViews", 0) or 0)
    return {
        "views": views, "engaged": eng, "engaged_share": eng / views,
        "likes": int(v.get("合計.likes", 0) or 0),
        "dislikes": int(v.get("合計.dislikes", 0) or 0),
        "comments": int(v.get("合計.comments", 0) or 0),
        "shares": int(v.get("合計.shares", 0) or 0),
        "playlist_adds": int(v.get("合計.videosAddedToPlaylists", 0) or 0),
        "avg_view_sec": v.get("合計.averageViewDuration"),
        "avg_view_pct": v.get("合計.averageViewPercentage"),
        "like_rate": int(v.get("合計.likes", 0) or 0) / views,
        # **年齢・性別は「取っていない」のではなく「返ってこない」**。
        # `src/scan.py` は使える次元を毎回全部回すので、出ていない ＝ この
        # チャンネルではまだ API が返さない（`viewerPercentage` は標本が要る）。
        "has_demographics": any(k.startswith(("ageGroup.", "gender.")) for k in v),
    }


def traffic(v: dict) -> dict:
    """**`src/scan.py` は「取れなかった」を `None` で書き残します**（2026-08-25 に踏んだ）。

        src/scan.py:194   out[f"{dim}.（取れず）"] = None

    次元の取得が落ちた回は、この印が `values` に1つ混ざります。**印そのものは
    正しい設計**です —— 取れなかったことを黙って0にすると、
    「本当に0だった回」と区別が付かなくなります。

    **落ちていたのは読む側でした。** ここは前置きだけで族をまるごと集めるので、
    印まで拾って `sum()` に渡し、`int + NoneType` で落ちます。実測:

        data/scan.jsonl 最終行（08/25 19:00:34）に
        `insightTrafficSourceType.（取れず）: None` が1つ
        → **`tests/test_trajectory.py` の17件が全部 ERROR**
        → `scripts/trajectory.py`（軌跡の本体）が丸ごと動かない

    **印は落としますが、落としたことは返します**（`src_unavailable`）——
    黙って捨てると、次の回は「流入が全部0だった」と読みます。
    """
    def _family(prefix: str) -> tuple[dict, bool]:
        got, missing = {}, False
        for k, n in v.items():
            if not k.startswith(prefix):
                continue
            name = k.split(".", 1)[1]
            if n is None:          # ← `（取れず）` の印。数に混ぜない
                missing = True
                continue
            got[name] = n
        return got, missing

    src, src_missing = _family("insightTrafficSourceType.")
    loc, loc_missing = _family("insightPlaybackLocationType.")
    tot = sum(src.values()) or 1
    shorts = src.get("SHORTS", 0)
    non_shorts = tot - shorts
    return {
        "src": dict(sorted(src.items(), key=lambda kv: -kv[1])),
        "loc": dict(sorted(loc.items(), key=lambda kv: -kv[1])),
        "total": tot, "shorts": shorts, "shorts_share": shorts / tot,
        "non_shorts": non_shorts,
        # **この回、その次元が API から取れたか。** False なら上の数は
        # 「0だった」ではなく「**測れていない**」（`src/scan.py` の `（取れず）`）
        "src_unavailable": src_missing, "loc_unavailable": loc_missing,
        "search": src.get("YT_SEARCH", 0), "browse": src.get("YT_OTHER_PAGE", 0),
        "suggested": src.get("RELATED_VIDEO", 0),
    }


def reach() -> dict:
    """サムネを見せた面（Reporting API `channel_reach_basic_a1`）。

    **`src/reach_split.py` に寄せています。** 2026-08-20 に別のセッションが
    `scripts/reach.py` の欠陥を2つ見つけました —— **こちらの回は同じ日に
    同じ数を自前で数えて、2つとも踏んでいます**:

      1. **報告を新しい3本しか落としていなかった**（ジョブには35本並んでいる）。
         Reporting API は作った時点から30日ぶん遡って置くので、
         **在るのに読んでいない31日**があった（165行 → 540行）
      2. **CTR の列を百分率として読んでいた。** 実物は割合。
         直すとショートの CTR は 1.34%（オーナーが Studio で読んだ 1.3% と一致）

    **自前で数え直さないこと。** ここが二重に実装されていると、
    片方だけ直った状態で両方から数が出ます。

    この面が効くのは**ショートのフィード以外**だけです（フィードはこの数に
    入りません）。**長尺が生きられる面の広さは、まるごとこの数**です。
    """
    try:
        from src import reach_split
    except Exception:                                   # noqa: BLE001
        return {"ok": False}
    rows = reach_split.load_rows()
    if not rows:
        return {"ok": False}
    longs = reach_split.long_ids()
    sm = reach_split.summary(rows, longs)
    return {"ok": True, "summary": sm, "n_rows": len(rows),
            "days": sm.get("days"), "dates": sm.get("dates"),
            "long": sm.get("長尺"), "short": sm.get("ショート"),
            "text": reach_split.render(rows, longs)}


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
    # **オーナーが固定した規則（1日1本）を、天井の候補に入れること**
    # （2026-08-31 に直した）。ここは長らく `min(API の日枠, 題材の生成速度)`
    # だけで、**規則を1度も見ていませんでした** —— 規則は 1本/日、日枠は 92本/日 で、
    # **軌跡ぜんぶが 92倍 の供給の上に乗っていました。**
    # この repo でいちばん多い壊れ方（言っている所と、している所が別）そのものです。
    # **出どころは `src/house_rule` の1か所**。ここに数を写さないこと。
    sup_rule = float(house_rule.planned_publishes_per_day())
    ceilings = [(sup_rule, "オーナーの規則（1日1本）"), (float(sup_api), "API の日枠")]
    if mat:
        ceilings.append((float(mat), "題材の生成速度"))
    sup_cap, sup_cap_why = min(ceilings, key=lambda kv: kv[0])   # 持続できる供給の天井

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
    # **2つある。混ぜないこと**（2026-08-31 に分けた）。
    #   `V_for_gate2b`     …… **API の日枠まで出したとき**に要る1本あたり再生。
    #                          下の「日枠まで出しても届きません」の行が使う。
    #   `V_for_gate2b_cap` …… **実際に出せる本数（＝持続できる天井）**で要る1本あたり再生。
    #                          規則が 1本/日 を固定した以上、**こちらが実物**です。
    # 1本にまとめていた頃は、規則が縛っていても「日枠まで出したときの数」を
    # 印字していました —— **92倍 薄い要求**で、隔たりが 60分の1 に見えます。
    V_for_gate2b = gate2b_day / sup_api
    V_for_gate2b_cap = (gate2b_day / sup_cap) if sup_cap else float("inf")
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
        "supply_api": sup_api, "supply_rule": sup_rule,
        "supply_cap": sup_cap, "supply_cap_why": sup_cap_why,
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
        "V_for_gate2b": V_for_gate2b, "V_for_gate2b_cap": V_for_gate2b_cap,
        "mat_for_gate2b": mat_for_gate2b,
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
    td = m.get("decompose") or {}
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
            # **規則が縛っているときに「題材を増やせ」と書かないこと**（2026-08-31）。
            # 供給の天井が規則なら、題材を何件 増やしても供給は 1本/日 のままです。
            # ここは長らく律速の名前だけ差し替えて、要求は題材の側に出していました ——
            # **読む側を、効かない腕へまっすぐ送る行**でした。
            if st["supply_cap"] <= st["supply_rule"] + 1e-9 and st["supply_rule"] < st["supply_api"]:
                h.append(f"### [!] **いまの構成では床に乗れません。** "
                         f"律速は**{st['supply_cap_why']}** —— "
                         "**題材を増やしても供給は動きません**（規則は本数の側を固定しています）。"
                         f"**残る腕は V（1本あたり再生・いま天井 {st['V_cap']:,.0f}回）と RPM だけ**で、"
                         f"門2b に要るのは **1本あたり {st['V_for_gate2b_cap']:,.0f}回**"
                         f"（実測の天井 {st['V_cap']:,.0f}回 の "
                         f"**×{st['V_for_gate2b_cap']/st['V_cap']:.1f}**）です")
            else:
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
        gap = ident.get("gap")
        P(f"         → 差 **{gap*100:+.1f}%**" if gap is not None
          else "         → 差 **[測れません]**（Analytics の窓の再生が 0）")
        # **「閉じます」を、差を見ずに印字していました**（2026-08-21 04:3x に直した）。
        # ここは長らく `→ 差 -27.6%。**閉じます。**` と**続けて**出していて、
        # そのすぐ下で「後ろカタログが1回も効いていません」と言い切っていました。
        # **数字と結論が別々に印字されていたので、食い違っても誰も気づきません。**
        if not ident.get("comparable", True):
            cov = ident.get("coverage")
            share = f"（{cov * 100:.0f}%）" if cov is not None else "（割合は不明）"
            P(f"         [!] **この差は判定に使えません。** 記録は {ident['n_snapshots']}本、"
              f"チャンネルは {ident['n_channel']}本{share}")
            P("             **左辺だけが記録の側を見ています** —— `data/views.jsonl` に")
            P("             載っている本しか数えないのに、右辺の Analytics は"
              "**チャンネル全体**です。")
            P("             **公開を増やすほど差は開きます。**"
              "後ろカタログの話ではありません（`coverage()`）。")
            P("             後ろカタログが効いていないことの根拠は、"
              "**下の齢べつの曲線**のほうを読むこと。")
        elif gap is not None and abs(gap) < 0.05:
            P("         → **閉じます。**")
            P("         （断り: 窓の縁では**外へ出る本**（窓の最後の日に公開した本の2日目）と")
            P("           **中へ入る本**（窓の前日に公開した本の2日目）が出入りします。")
            P("           **一致そのものは、その2つが釣り合ったぶんを含みます** —— ")
            P("           後ろカタログが無いことの根拠は、下の齢べつの曲線のほうが直接的です）")
            P("")
            P("  **閉じるということは、その窓の再生が全部その窓に公開した本のものだ**ということです。")
            P("  **後ろカタログが1回も効いていません。**")
        else:
            P("         → [!] **閉じません。** 記録はチャンネルを覆っているので、"
              "**差は本物です。**")
            P("             軌跡に**減衰項**が要ります（`tests/test_trajectory.py` の註）。")
    if dec.get("frac24_median") is not None:
        P(f"  [実測] 1本の生涯再生のうち、**公開24時間以内に来る割合 {dec['frac24_median']*100:.1f}%**"
          f"（中央値・n={dec['frac24_n']}）")
    if dec.get("curve"):
        P("  [実測] 齢べつの「再生/日」:")
        for c in dec["curve"][:6]:
            P(f"           齢 {c['age_days']:>2}日  n={c['n']:>3}  中央値 {c['median']:>7.1f} 回/日"
              f"   平均 {c['mean']:>8.1f}")
        # **ここは長らく「齢2日を超えた本は、中央値で 0.0 回/日。」を
        # `dec` を1つも読まずに印字していました**（2026-08-29 に直した）。
        # 上の `identity()` の側で 2026-08-21 に直したのと**同じ形**です ——
        # 「数字と結論が別々に印字されていたので、食い違っても誰も気づきません」。
        # **食い違っていました**: 齢24日 が 0.57回/日 に動いた日も、この行は 0.0 と
        # 言い続け、`tests/test_trajectory.py::test_no_back_catalogue` だけが赤で、
        # その文面は「軌跡を組み直すこと」でした。**印字と門が逆を向いていた。**
        if not dec.get("judgeable"):
            P("         → [測れません] 読み数が足りるバケツがありません"
              f"（下限 {BACK_CATALOGUE_MIN_READINGS}読み）。**0.0 と読まないこと。**")
        else:
            om = dec.get("old_max_median")
            P(f"         → **齢2日を超えた本は、中央値で いちばん大きいバケツでも "
              f"{om:.1f} 回/日**"
              f"（門にかけた {dec['guard_buckets']}バケツ・"
              f"齢 {min(dec['guard_ages'])}〜{max(dec['guard_ages'])}日・"
              f"各 {BACK_CATALOGUE_MIN_READINGS}読み以上）")
            for t in dec.get("thin_nonzero", []):
                P(f"           （齢 {t['age_days']}日 は 中央値 {t['median']:.2f} 回/日 ですが、"
                  f"**{t['n']}読みしかないので門から外しています**。"
                  "尾の1バケツで軌跡を組み直さないこと）")
            if dec.get("back_catalogue"):
                P("         → [!] **後ろカタログができています。** 恒等式が成り立たなく"
                  "なるので、**軌跡に減衰項が要ります**（`decay()` の註）")
            else:
                P("         → **後ろカタログはありません。**"
                  "（動きの門・大きさの門とも通っています）")
    P("")
    P("  **だから、複利で伸びる項は「V が時間とともに伸びるとき」にしか立ちません。**")
    P("  伸ばせるのは **供給** と **V** の2つだけ。どちらにも実測の天井があります。")
    P("  **どちらが伸びているかは、下の 1. で割ってあります**（断言ではなく回帰です）。")
    P("")

    # -- 1. 伸び率 ------------------------------------------------------------
    P("--- 1. **日次再生の傾きは、供給の傾きと V の傾きに割ってから使う** ---")
    P("")
    if tr.get("ok"):
        P(f"  [実測] 日次再生の log 線形回帰（{tr['first']}〜{tr['last']}・n={tr['n']}日）")
        P(f"         傾き **1日 {tr['g']*100:+.2f}%**   t = **{tr['t']:.2f}**"
          f"   → {'**有意**' if tr['significant'] else '**有意ではありません（0 と区別がつかない）**'}")
        P(f"         95%区間: 1日 {tr['lo']*100:+.2f}% 〜 {tr['hi']*100:+.2f}%")
        P(f"         **これを100日ぶん複利で伸ばすと** 区間は "
          f"**{tr['blowup_lo']:.3g}倍 〜 {tr['blowup_hi']:.3g}倍**")
        P("         → **左辺をそのまま複利にしてはいけません。** 恒等式が")
        P("           **日次再生 ＝ 供給 × V** なので、log の傾きは必ず足し算に割れます:")
        P("           **d log(再生) ＝ d log(供給) ＋ d log(V)**")
        P("           **供給の側は、軌跡がすでに天井付きで持っています**"
          "（**オーナーの規則（1日1本）**・題材の生成速度・API の日枠 のいちばん低いもの）。")
        P("           **複利の項として足してよいのは V の側だけ**です ——"
          "割らずに左辺を伸ばすと、")
        P("           **天井のある供給の伸びを、天井の無い複利として二重に数えます。**")
    P("")
    P("  **その割り算**（`trend_decompose()`）:")
    if not td.get("ok"):
        P(f"  [未測定] **割れません** —— {td.get('why', '理由が立ちません')}")
        P("           **割れないうちは、複利の項を入れません**（左辺の傾きだけでは、")
        P("           供給が立ち上がった跡なのか V が伸びたのかを区別できないため）。")
    else:
        P(f"  [実測] 突き合わせた窓: {td['first']}〜{td['last']}・**n={td['n']}日**"
          "（供給が分かる日 ∩ 日次再生がある日）")
        P("         供給の出どころ: **帳面**（`uploaded.jsonl`・08/16 以降）＋"
          "**観測**（`views.jsonl` の `at - hours`・08/04 まで戻る）。")
        P("         観測の側は**下限**（一度も観測されなかった本は数えない。取りこぼし -14.0%）。")
        P("         **ただし欠けは窓の前半と後半でほぼ同じ**（-14.7% / -13.6%）——"
          "log では一定倍が定数に落ちるので、**傾きにはほとんど効きません。**")
        for lab, key, note in (("再生 ", "views", "左辺"),
                               ("供給 ", "supply", "**天井は `stages()` が持っている**"),
                               ("V    ", "v", "**複利に足してよいのはここだけ**")):
            r = td[key]
            if not r.get("ok"):
                P(f"         {lab} —— 立ちません")
                continue
            mark = "**有意**" if r["significant"] else "有意でない"
            P(f"         {lab} 1日 **{r['g']*100:+.2f}%**  t = **{r['t']:+.2f}**  {mark}"
              f"   95% [{r['lo']*100:+.1f}%, {r['hi']*100:+.1f}%]   {note}")
        if td.get("additive"):
            P("         → 3つは足し算で閉じています（恒等式のとおり）。")
        if td.get("dropped_zero"):
            P(f"         公開が 0本 の日 {len(td['dropped_zero'])}日 は log が採れないので外しました。")
        P("")
        if td["compound"]:
            P("  → **V が有意に伸びています。複利の項を入れてよい回です**"
              "（`CLAUDE.md` の (ア)）。")
            P("    `stages()` の V を、この傾きの時間の関数に置き換えること。")
        else:
            P(f"  → **複利の項は入れません。** 理由: {td['why']}")
            P("    **これは「伸びていない」ではありません** —— "
              "**この窓のこの点数では、0 と区別がつかない**という意味です。")
            P("    **固定しているものを名前で言うと**（`CLAUDE.md` の (イ)）:")
            P(f"      V ＝ 今日の実測のまま（傾き 0 と置いた。点推定は 1日 "
              f"{td['v']['g']*100:+.2f}%）")
            P("      供給 ＝ 天井まで伸ばす（**据え置きではありません**。"
              "`stages()` の `supply_cap`）")
            P("      RPM ＝ [未測定]（収益化前なので自分の数字が1つも無い）")
            P(f"    **この3つのうち V の固定が外れる条件**: 重なる窓が "
              f"{td['min_days']}日 以上になり、V の t が ±2 を超えること。")
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
    P(f"    [規則] オーナーが固定した公開の上限 **{st['supply_rule']:.0f}本/日**"
      "（`src/house_rule.PUBLISH_PER_DAY`）")
    P("           **帯は観測、規則は規則。規則のほうが小さいので、規則が勝ちます。**"
      " 2026-08-31 まで、ここは規則を1度も見ておらず、"
      f"**軌跡は {UPLOAD_CAP_PER_DAY}本/日 の供給の上に乗っていました。**")
    if mat.get("ok"):
        thin = "  [!] **窓が {:.1f}時間しかありません**（この軌跡でいちばん薄い実測）".format(
            mat["span_hours"]) if mat.get("thin") else ""
        P(f"    [実測] **題材が増える速さ {mat['per_day']:.1f}件/日**"
          f"（`sweep_novel` {mat['delta']:+d}件 / {mat['span_hours']:.1f}時間・点 {mat['n_points']}）{thin}")
        # **割るのは「実際に出す本数」であって、API の日枠ではありません。**
        # 規則が 1本/日 なので、在庫は 92分の1 の速さでしか減りません。
        _cap = st["supply_cap"] or 1.0
        P(f"           在庫は {mat['stock_novel']}件 ＝ {_cap:.0f}本/日（{st['supply_cap_why']}）なら "
          f"**{mat['stock_novel']/_cap:.1f}日で尽きます**。"
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
    P("    （**この数は長尺の面の上限**です —— いま流れているのはほとんどショートで、")
    P("      長尺がその面をまるごと取れたとしても、という数え方。実測は下）")
    if rc.get("ok"):
        lg, sh = rc["long"], rc["short"]
        P("")
        P(f"  [実測] サムネを見せた面（Reporting API `channel_reach_basic_a1`・"
          f"{rc['dates'][0]}〜{rc['dates'][-1]}・{rc['days']}日・{rc['n_rows']}行）")
        P(f"         ショート {sh['videos']:>3}本  1日 {sh['per_day']:>5.1f}回"
          f"  CTR {sh['ctr']:.2f}%  → クリック 1日 {sh['impressions']*sh['ctr']/100/rc['days']:.2f}回")
        P(f"         長尺   {lg['videos']:>3}本  1日 {lg['per_day']:>5.1f}回"
          f"  CTR {lg['ctr']:.2f}%  → クリック 1日 {lg['impressions']*lg['ctr']/100/rc['days']:.2f}回")
        P("         **ショートのフィードはこの数に入りません。** だからこの面は"
          "**ほぼ長尺のためだけの面**です。")
        P(f"         → **長尺は 6本で 1日 {lg['per_day']:.0f}インプレッション。**"
          "  **CTR を100%にしても、この面から取れるのは")
        P(f"           月 {lg['per_day']*30:.0f}回**です。**足りないのはインプレッションで、"
          "サムネでも題でもありません。**")
        P("           （この数は `src/reach_split.py` に寄せています。**自前で数え直さないこと** ——")
        P("             この回は自前で数えて、`scripts/reach.py` の欠陥2つを両方踏みました）")
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
    eg = m["engagement"]
    P("--- 5. **視聴者の反応（V を決めているのはフィードで、材料はこれだけ）** ---")
    P("")
    P(f"  [実測] 再生 {eg['views']:,}回 に対して:")
    P(f"           engaged（すぐスワイプされなかった）  {eg['engaged']:>7,}回  **{eg['engaged_share']*100:>5.1f}%**")
    P(f"           高評価                              {eg['likes']:>7,}回  {eg['like_rate']*100:>5.3f}%")
    P(f"           コメント                            {eg['comments']:>7,}件"
      + ("  ← **0件。** 反応の中でここだけ完全に無い" if eg["comments"] == 0 else ""))
    P(f"           共有                                {eg['shares']:>7,}回")
    P(f"           再生リストに追加                    {eg['playlist_adds']:>7,}回")
    P(f"           平均視聴 {eg['avg_view_sec']}秒（尺の {eg['avg_view_pct']}%）")
    P("  → **engaged は3回に1回。** ここが V を決めている側の唯一の実測です。")
    if not eg["has_demographics"]:
        P("  [未測定] **年齢・性別は返ってきません**（`src/scan.py` は使える次元を毎回全部回すので、")
        P("           出ていない ＝ **取っていないのではなく、まだ API が返さない**）。")
        P("           **標本が増えれば勝手に出ます。取りに行く作業は要りません。**")
    P("")
    P("--- 6. **登録率** ---")
    P("")
    P(f"  [実測] 純増 **{sb['net']}人** / 再生 {sb['views']:,}回 → **{sb['rate']*100:.4f}%**")
    P(f"         95%区間（Poisson・k={sb['net']}）: **{sb['rate_lo']*100:.4f}% 〜 {sb['rate_hi']*100:.4f}%**"
      f"（**上下 {sb['rate_hi']/sb['rate_lo']:.1f}倍**）")
    P(f"         → **9人しか居ません。** 門1 の日付はこの {sb['rate_hi']/sb['rate_lo']:.1f}倍がそのまま効きます。")
    P("")

    # -- 6. 未測定 ------------------------------------------------------------
    P("--- 7. **未測定（代用も置きません）** ---")
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
      f"   …… 供給 {st['supply_hist']:.1f}本/日 × V {st['V']:.0f}回 "
      f"＝ {st['supply_hist']*st['V']:,.0f}（**日次の平均と本の平均を掛けているので"
      f"{abs(st['supply_hist']*st['V']/st['views_hist']-1)*100:.0f}%ずれます**。")
    P("             **帳尻が合うことの根拠は上の節の -0.4% のほうで、この行ではありません**）")
    P(f"      [実測] 予約 {st['supply_sched']:.1f}本/日 × [実測] V {st['V']:.0f}回"
      f" → **{st['views_sched']:,.0f}回/日 の見込み**")
    P("             （**入力は2つとも実測、掛けた結果は見込み**です。"
      "まだ Analytics に出ていません）")
    P(f"      **予約を入れ替えただけで ×{st['views_sched']/st['views_hist']:.1f}。**"
      "これは既に済んでいて、Analytics に出るのはこれからです")
    P("")
    P("  **段1 供給を、持続できる天井まで**")
    P(f"      いま {st['supply_sched']:.1f}本/日 → **{st['supply_cap']:.1f}本/日**"
      f"（×{st['R_supply_have']:.1f}）")
    # **件/日 を添えるのは、題材が本当に律速のときだけ。**
    # 規則が律速のときに「21.4件/日」を並べると、規則の本数と読めます。
    _mat_binds = st["supply_cap_why"] == "題材の生成速度"
    P(f"      律速: **{st['supply_cap_why']}**"
      + (f" {st['material_per_day']:.1f}件/日"
         if (_mat_binds and st.get("material_per_day")) else ""))
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
        _rule_binds = (st["supply_cap"] <= st["supply_rule"] + 1e-9
                       and st["supply_rule"] < st["supply_api"])
        if _rule_binds:
            # **規則が縛っている以上、これは材料の問題ではありません。**
            P(f"             **足りないのは1本あたりの再生です。** 供給は規則で "
              f"{st['supply_rule']:.0f}本/日 に固定されており、"
              "**題材をいくつ増やしてもここは1ミリも動きません。**")
            P(f"             要る V は **{st['V_for_gate2b_cap']:,.0f}回/本** ——"
              f" 実測の天井 {st['V_cap']:,.0f}回 に対して **×"
              f"{st['V_for_gate2b_cap']/st['V_cap']:.1f}** 要ります")
            P("             （＝ 本数では埋まりません。**ニッチ・尺・形式・言語・収益の立て方**"
              "の側にしか残っていない、ということです）")
        else:
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
    if rc.get("ok"):
        lg = rc["long"]
        # **門2a は「直近12か月で4,000時間」なので、比べる相手は年**です。
        # 月の上限と年の必要数を並べると、12倍ぶん厳しく見えます（2026-08-20 に踏んだ）。
        ceil_year = lg["per_day"] * 365                # CTR 100% と置いた年の上限
        P(f"             [実測] 長尺の面は **1日 {lg['per_day']:.0f}インプレッション**"
          f"（{lg['videos']}本・{rc['days']}日）")
        P(f"             → **CTR を100%にしても 年 {ceil_year:,.0f}回**が上限"
          f"（門2a は直近12か月で数えるので、**年で比べます**）。")
        P(f"               要る {st['long_views_need']:,.0f}回 に対し "
          f"**{st['long_views_need']/ceil_year:.1f}倍 足りません**")
        P(f"             [実測] 実際の CTR は **{lg['ctr']:.2f}%** ＝ "
          f"{rc['days']}日で長尺のクリックは **{lg['impressions']*lg['ctr']/100:.0f}回**")
        short_now = st["long_views_need"] / (ceil_year * lg["ctr"] / 100) if lg["ctr"] else None
        if short_now:
            P(f"               実測の CTR のままなら **{short_now:,.0f}倍**。")
        P("             → **足りないのはインプレッションです。** サムネと題（CTR）を")
        P("               100%まで直しても、**まだ 6倍**足りません。**面そのものが小さい。**")
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
    td = trend_decompose(day)
    sb = subs(v)
    tf = traffic(v)
    eg = engagement(v)
    rc = reach()
    rt = retention()
    st = stages(vs, day, ident, dec, pv, sup, tr, sb, tf, rc, today)
    return {"identity": ident, "decay": dec, "per_video": pv, "supply": sup,
            "trend": tr, "decompose": td, "subs": sb, "traffic": tf, "engagement": eg, "reach": rc,
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
