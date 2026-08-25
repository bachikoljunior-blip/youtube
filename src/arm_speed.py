"""**腕が動く速さ。**（API は 0 単位。読むのは `config/hypotheses.yaml` だけ）

## なぜ要るか（2026-08-20 18:xx・オーナー指示。原文）

> 腕とやらをそう設定した時に達成がいつになるって予測じゃなくて、じゃあその腕を
> そうなるまでにどれくらい時間がかかるのかとか予測しないとダメだよ。特定条件の
> 予測じゃなくて、実際にどういう軌跡を辿るか予測して、いつ達成かを予測するんだよ。

`scripts/eta.py` の `lever_days` は **「`per_video` を2倍にしたら 2027-01-19」**
を出していました。**2倍になるのに何日かかるかは、1行も出していません。**

同じ回に「1日25本」を外したばかりです —— あれも
**満たせるか分からない前提の上に日付が乗っていた**という欠陥でした。
**腕の側に、まったく同じ穴が残っていた**わけです。

## 腕の速さ ＝ 1回転の日数 × 当たる確率 × 当たったときの伸び幅

3つとも、この機械が既に持っています（**推測ではありません**）:

    1回転の日数    閉じた前提が何日に1件出ているか（`closed_on` の実測）
    当たる確率     閉じた前提のうち、**1日の再生を実際に増やした**割合
    伸び幅         増やした回の倍率（`effect`）の**中央値**

**「当たり」を `outcome` で数えないこと。** 反証条件を満たさなかっただけの前提
（「固めて出すと後発に露出が回らない」など）は生き残っていますが、
**1日の再生を1倍も増やしていません**。`effect > 1.0` で数えます。

## 出てくる形：1日あたりの伸び率

腕の倍率を `x(t)` と置くと、1回転で `log x` が `p · log g` だけ増えます。
1日に `θ` 回転するので

    d(log x)/dt = p · log(g) · θ   →   x(t) = exp(rate · t)

**指数で置くのは、当たりが掛け算で乗るからです**（1.85倍の当たりが2回なら 3.4倍）。
足し算で置くと、当たりが増えるほど効きが薄くなる形になり、実測と合いません。

## 天井（**腕は無限には伸びません**）

閉じた前提が**天井を測ってしまった**ときは `ceiling` が入ります。
いま入っているのは1件だけ:

    per_video   1本あたり再生 **1,891回**（24時間・39本の実測の最大。3,000超は0本。
                **2026-08-21 に n=7 の最大 1,447 から数え直した** —— 天井を
                7本の最大で置くと、標本が増えるたびに必ず外側が出ます）
                外す道は形を替えること（＝腕 `rpm`）だけ

**軌跡は、天井のある腕をそれ以上伸ばしません。** ここを外すと
「ショートのまま1本あたり10万回」という**実在しない世界**を歩きます。

## この道具が言えないこと

- **腕ごとの標本が薄い。** `rpm` は閉じた前提が1件、`sub_rate` は2件です。
  `MIN_N` に満たない腕は**全体の確率と伸び幅で代用**し、`source` にそう書きます。
  代用だと分かる形で出すこと —— 黙って埋めると、薄い腕ほど自信ありげに見えます
- **配分は実績のままです。** 「この腕に全部振ったら」は `focus_rate` に別で出します。
  実際にどう振ってきたかが `share`（閉じた前提の本数の割合）です
- **創業時の1件が桁で外れています**（形をショートへ替えて 256倍）。だから
  伸び幅は**平均ではなく中央値**です。平均だと、その1件だけで全部決まります
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"

JST = timezone(timedelta(hours=9))

#: 腕ごとに自前の確率・伸び幅を使ってよい最低件数。**下回ったら全体で代用する。**
#: 3 にした理由: 2件だと「1件当たり／1件外れ」で確率が 0.5 に跳ね、
#: **全体（0.2 前後）の2倍以上**になります。1件の当たりで倍率が2.5倍動く帯です。
MIN_N = 3

#: 予測に使う腕（`src/levers.py` の `MOVING` と同じ並び。`none` は入れない）
ARMS = ("per_video", "sub_rate", "rpm", "density")


def today_jst() -> date:
    return datetime.now(JST).date()


def _load() -> dict:
    if not HYPOTHESES.exists():
        return {}
    return yaml.safe_load(HYPOTHESES.read_text(encoding="utf-8")) or {}


def closed(doc: dict | None = None) -> list[dict]:
    """**判定の済んだ前提**を、判定した日の古い順に返す。

    `hypotheses` の `closed_on` と `confirmed` の `confirmed_on` を同じ列に並べます
    （**どちらも「1件の実験が閉じた」ことに変わりはありません**）。
    欄の無い行は**黙って飛ばさず**、`missing` に数えられる形で落とします
    （`stats` が「何件を読めなかったか」を出します）。
    """
    doc = _load() if doc is None else doc
    rows: list[dict] = []
    for key, day_key in (("hypotheses", "closed_on"), ("confirmed", "confirmed_on")):
        for h in doc.get(key) or []:
            if not isinstance(h, dict):
                continue
            when = h.get(day_key) or h.get("closed_on")
            if when is None or h.get("effect") is None or not h.get("lever"):
                continue
            try:
                day = date.fromisoformat(str(when))
            except ValueError:
                continue
            rows.append({
                "claim": h.get("claim", ""),
                "closed_on": day,
                "outcome": h.get("outcome"),
                "lever": h["lever"],
                "effect": float(h["effect"]),
                "note": h.get("effect_note"),
                "hit": float(h["effect"]) > 1.0,
                "ceiling": h.get("ceiling"),
            })
    rows.sort(key=lambda r: r["closed_on"])
    return rows


def unreadable(doc: dict | None = None) -> int:
    """**欄が足りなくて数えられなかった、閉じた前提の件数。**

    判定文（`verdict`）はあるのに `effect` が無い行がここに出ます。
    **0 でないなら、確率も伸び幅も下振れしています**（当たりを取りこぼす側）。
    """
    doc = _load() if doc is None else doc
    n = 0
    for h in doc.get("hypotheses") or []:
        if isinstance(h, dict) and h.get("verdict") is not None and h.get("effect") is None:
            n += 1
    for h in doc.get("confirmed") or []:
        if isinstance(h, dict) and h.get("effect") is None:
            n += 1
    return n


def ceilings(doc: dict | None = None) -> dict[str, dict]:
    """**測ってしまった天井**を腕ごとに返す（`{"per_video": {...}}`）。"""
    out: dict[str, dict] = {}
    for h in (_load() if doc is None else doc).get("hypotheses") or []:
        c = h.get("ceiling") if isinstance(h, dict) else None
        if isinstance(c, dict) and c.get("lever") and c.get("value") is not None:
            out[c["lever"]] = {**c, "from": h.get("claim", "")}
    return out


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2


def throughput(rows: list[dict], today: date | None = None) -> dict:
    """**1日に何件の実験が閉じているか**（＝回転の速さ）。

    窓は「**最初に閉じた日 → 今日**」です。閉じた日どうしの間隔ではありません ——
    実験は同時に走るので、**間隔は1回転の長さを言っていません**
    （実測: 08/20 だけで4件が閉じている。間隔は 0.0日 ですが、
    その4件はどれも何日も前に立てたものです）。
    """
    today = today or today_jst()
    if not rows:
        return {"per_day": None, "n": 0, "days": 0.0, "first": None, "missing": "閉じた前提が0件"}
    first = rows[0]["closed_on"]
    days = max((today - first).days, 1)
    return {"per_day": len(rows) / days, "n": len(rows), "days": float(days),
            "first": first, "missing": None}


def arm(lever: str, rows: list[dict] | None = None, today: date | None = None,
        caps: dict[str, dict] | None = None, per_video_now: float | None = None) -> dict:
    """**その腕の速さ**を1つにまとめて返す。

    返り（欠けている数は `None` のまま返し、`missing` に名前を残す）:

        n            その腕で閉じた実験の件数
        hits         うち「1日の再生を増やした」件数（`effect > 1.0`）
        p            当たる確率
        gain         当たったときの倍率（中央値）
        share        全体のうち、この腕に振ってきた割合（**実績の配分**）
        rate         1日あたりの伸び率（実績の配分のまま進んだ場合）
        focus_rate   **この腕に全部振った**場合の1日あたりの伸び率
        cap          天井（倍率。無ければ `None`）
        source       "自前" か "全体で代用"
        missing      無い数の名前（**無いものは無いと言う**）
    """
    rows = closed() if rows is None else rows
    today = today or today_jst()
    caps = ceilings() if caps is None else caps
    th = throughput(rows, today)

    mine = [r for r in rows if r["lever"] == lever]
    pool = [r for r in rows if r["lever"] in ARMS]

    missing: list[str] = []
    if th["per_day"] is None:
        missing.append("回転の速さ（閉じた前提が0件）")

    use, source = (mine, "自前") if len(mine) >= MIN_N else (pool, "全体で代用")
    if source == "全体で代用" and len(mine) < MIN_N:
        missing.append(f"この腕だけの実績（{len(mine)}件 < {MIN_N}件）")

    hits = [r for r in use if r["hit"]]
    p = (len(hits) / len(use)) if use else None
    gain = _median([r["effect"] for r in hits])
    if p == 0.0 or gain is None:
        missing.append("当たったときの伸び幅（この腕はまだ1件も当てていない）")

    share = (len(mine) / len(pool)) if pool else None
    rate = focus = None
    if p and gain and gain > 1.0 and th["per_day"]:
        focus = p * math.log(gain) * th["per_day"]
        # **実績の配分のまま進んだ場合**は、その腕に回る回転だけが効きます。
        rate = focus * (share if share is not None else 0.0)

    cap = None
    c = caps.get(lever)
    if c is not None:
        base = per_video_now if lever == "per_video" else None
        if base:
            cap = float(c["value"]) / float(base)
        else:
            cap = None
            missing.append(f"天井の倍率（{c['unit']} は測れているが、いまの実測が渡されていない）")

    return {
        "lever": lever, "n": len(mine), "hits": sum(1 for r in mine if r["hit"]),
        "p": p, "gain": gain, "share": share,
        "rate": rate, "focus_rate": focus,
        "cap": cap, "ceiling": c,
        "source": source, "throughput": th["per_day"],
        "missing": missing,
    }


def all_arms(rows: list[dict] | None = None, today: date | None = None,
             per_video_now: float | None = None) -> dict[str, dict]:
    rows = closed() if rows is None else rows
    caps = ceilings()
    return {k: arm(k, rows, today, caps, per_video_now) for k in ARMS}


def factor_at(a: dict, days: float) -> float:
    """**`days` 日たったとき、その腕は何倍になっているか。**（天井で頭打ち）

    ## **天井 ×1.00 は「天井が無い」ではありません**（2026-08-22 に踏んで直した）

    ここは長らく `min(x, cap) if cap and cap > 1.0 else x` でした。
    **`cap == 1.0` は「もう1ミリも伸びない」＝ いちばんきつい天井**なのに、
    その行は `cap > 1.0` が偽になるので**頭打ちを丸ごと外していました。**
    `_capped_arms` は実在する幅（`physical_caps`）を当てるので、
    **伸びしろが無い腕には 1.00 が入ります** —— 実測で `density` がそれでした。

    結果、軌跡は**動かせない腕を ×3.43 まで伸ばした世界**を歩き、
    そのぶん到達日が早く出ていました（`tests/test_eta_trajectory.py` の
    「天井を超えた倍率まで腕を伸ばさない」が、まさにここで落ちています）。
    **早く出た日付は、待つ理由に使われます。**
    """
    rate = a.get("rate")
    if not rate or rate <= 0 or days <= 0:
        return 1.0
    x = math.exp(rate * days)
    cap = a.get("cap")
    if cap is None or cap <= 0:
        return x
    return min(x, max(float(cap), 1.0))


def days_to_factor(a: dict, factor: float) -> float:
    """**その倍率に届くまでの日数。**届かない（天井の外／速さが0）なら `inf`。"""
    if factor <= 1.0:
        return 0.0
    cap = a.get("cap")
    if cap and factor > cap:
        return math.inf
    rate = a.get("rate")
    if not rate or rate <= 0:
        return math.inf
    return math.log(factor) / rate


def miss_streak(rows: list[dict] | None = None) -> dict:
    """**いま何連続で外しているか**（新しい順に、`effect <= 1.0` が続いた数）。

    3連続で外している最中に「次の1本は当たる」前提の軌跡を出すと嘘になります。
    ここが返す `days` は、**その連敗が同じだけ続いた場合に腕が止まる日数**です
    （＝ 連敗の件数 ÷ 回転の速さ）。
    """
    rows = closed() if rows is None else rows
    th = throughput(rows)
    n = 0
    for r in reversed(rows):
        if r["hit"]:
            break
        n += 1
    expected = (1 / p) if (p := _pooled_p(rows)) else None
    return {
        "n": n,
        "expected_gap": expected,
        "days": (n / th["per_day"]) if th["per_day"] else None,
        "unusual": bool(expected and n > 2 * expected),
    }


def _pooled_p(rows: list[dict]) -> float | None:
    pool = [r for r in rows if r["lever"] in ARMS]
    return (sum(1 for r in pool if r["hit"]) / len(pool)) if pool else None


def band(rows: list[dict] | None = None) -> dict:
    """**当たる確率の幅**（Jeffreys 区間・90%）。軌跡の「早い／遅い」はここから出す。

    `k` 件の当たりを `n` 件で観測したときの Beta(k+0.5, n-k+0.5) の 5%／95% 点。
    **標本が15件しかないので、点推定だけを出すのは嘘に近い**（当たり3件です）。
    """
    rows = closed() if rows is None else rows
    pool = [r for r in rows if r["lever"] in ARMS]
    n = len(pool)
    k = sum(1 for r in pool if r["hit"])
    if n == 0:
        return {"p": None, "lo": None, "hi": None, "n": 0, "k": 0}
    try:
        from statistics import NormalDist  # 標準ライブラリだけで済ませる
    except Exception:                                          # noqa: BLE001
        return {"p": k / n, "lo": k / n, "hi": k / n, "n": n, "k": k}
    # Beta の分位点は標準ライブラリに無いので、**ロジット正規で近似**します。
    # （scipy を入れない。**回を止めないほうが速い**）
    a, b = k + 0.5, n - k + 0.5
    mean = a / (a + b)
    var = a * b / ((a + b) ** 2 * (a + b + 1))
    z = NormalDist().inv_cdf(0.95)
    lo = max(1e-6, mean - z * math.sqrt(var))
    hi = min(1.0, mean + z * math.sqrt(var))
    return {"p": k / n, "lo": lo, "hi": hi, "mean": mean, "n": n, "k": k}


def lines(arms: dict[str, dict], streak: dict, bd: dict,
          unread: int = 0) -> list[str]:
    """`eta.py` に出す数行。**速さを出す前に、その出どころを見せること。**"""
    out = ["", "--- **腕が動く速さ**（閉じた前提の実測。"
           f"当たり {bd['k']}件 / {bd['n']}件）---"]
    P = out.append
    any_arm = next(iter(arms.values()), None)
    th = any_arm.get("throughput") if any_arm else None
    if th:
        P(f"    回転の速さ  **1日 {th:.2f}件** が閉じている"
          f"（最初に閉じた日からの実測。**間隔ではありません** —— 実験は同時に走ります）")
    for k, a in arms.items():
        if a["rate"]:
            cap = a["cap"]
            if cap and cap < 2.0:
                reach = (f"**天井 ×{cap:.2f} まで {math.log(cap) / a['rate']:,.0f}日"
                         f"（2倍には届きません）**")
            else:
                reach = f"**2倍まで {math.log(2) / a['rate']:,.0f}日**"
                if cap:
                    reach += f"／天井 ×{cap:.2f}"
            P(f"    `{k:<10}` 当たり {a['hits']}/{a['n']}件"
              f"  p={a['p']:.2f}  伸び幅 ×{a['gain']:.2f}"
              f"  配分 {a['share']:.0%}  → {reach}"
              f"（{a['source']}）")
        else:
            why = a["missing"][-1] if a["missing"] else "速さが出ません"
            P(f"    `{k:<10}` 当たり {a['hits']}/{a['n']}件"
              f"  → **動きません**（{why}）")
    if streak["n"]:
        note = "（当たりの間隔の実測は "
        note += (f"{streak['expected_gap']:.1f}件なので、"
                 + ("**外れすぎです**" if streak["unusual"] else "**まだ範囲の中**")
                 + "）") if streak["expected_gap"] else "）"
        P(f"    いま **{streak['n']}連続で外しています**{note}")
    if unread:
        P(f"    [!] 閉じているのに欄の無い前提が **{unread}件**。"
          "**当たりを取りこぼす側にずれます**（`closed_on`/`lever`/`effect` を足すこと）")
    return out

def next_close(doc: dict | None = None, today: date | None = None,
               ready: dict[str, date] | None = None) -> dict:
    """**次に前提を1件閉じられるのはいつか。**

    軌跡の腕は閉じた前提でしか動かないので（この節の上を参照）、
    **その日までは、どんな作業をしても印字される到達日は動きません。**
    2026-08-21 の回は `make_rate` を 22.85 → 46.7 と2倍にして **+0日** でした。
    そのとき開いていた前提13件のうち、いちばん早い期日は **2026-08-26** ——
    **その回に日付を動かす道は、そもそも1本も無かった**わけです。

    ## **`deadline` は「判定できる日」ではありません**（2026-08-25 22:5x）

    ここは長らく `deadline` だけを読んでいました。`deadline` は**置いた回の勘**で、
    **データが実際に揃う日**（`scripts/deadline_check.py` の `ready`）とは別物です。
    実測（2026-08-25・開いている16件）:

        ready ≤ deadline が **10件**、合計 **46日** ／ 平均 **4.6日** 早い
        いちばん大きいもの: ready 08-29 に対し deadline 09-12 ＝ **14日**

    **`deadline_check.py` は `ready > deadline`（期限が早すぎる）しか見ていませんでした。**
    逆向き ——**データはもう揃っているのに期限がまだ先** —— は
    「**期限に間に合います**」という緑の行で流れていました。
    その 46日 は、**軌跡がまるごと止まっている日数**です
    （腕は閉じた前提でしか動かないので）。

    `ready` を渡すと、**claim ごとにそちらを優先**します
    （`ready > deadline` でも `ready` が正 —— 期限が守れないだけで、
    判定できる日は動きません）。渡さなければ従来どおり `deadline` で読みます。

    返り: `{"on": date|None, "days": int|None, "open": 件数, "source": "ready"|"deadline"}`
    """
    doc = _load() if doc is None else doc
    today = today or today_jst()
    ready = ready or {}
    days: list[tuple[date, str]] = []
    n_open = 0
    for h in doc.get("hypotheses", []) or []:
        if not isinstance(h, dict) or h.get("closed_on"):
            continue
        n_open += 1
        when = h.get("settle_by") or h.get("decide_by") or h.get("deadline")
        if isinstance(when, str):
            try:
                when = date.fromisoformat(when)
            except ValueError:
                when = None
        src = "deadline"
        r = ready.get(str(h.get("claim") or ""))
        if isinstance(r, date):
            when, src = r, "ready"
        if isinstance(when, date):
            days.append((when, src))
    if not days:
        return {"on": None, "days": None, "open": n_open, "source": None}
    soonest, src = min(days, key=lambda x: x[0])
    return {"on": soonest, "days": (soonest - today).days,
            "open": n_open, "source": src}
