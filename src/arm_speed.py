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

## **`effect` の一巡は終わりました**（2026-08-26 夕・サブ。**4周 持ち越されていた**）

**4回続けて「閉じた21件の `effect` が、その腕が数えた値の倍率か、まだ1件も見ていない」
と申し送られていました。** 一巡した結果を残します —— **直すところはありませんでした。**
**同じ探索を5周目に始めないこと。**

`closed()` が `effect` から作るのは **`hit = effect > 1.0` の1ビットだけ**です
（`p` と、当たった行の中央値 `g`）。だから当たるのは**符号の側**で、
1.0 と 0.77 と 0.0037 の違いは、到達日に1日も効きません。

    `> 1.0` の4件   per_video 1.85（年金1,257 対 残業代680 ＝ 1本あたり再生）
                    per_video 1.20（engaged 中央値。**再生そのものは 1.67〜2.11倍**だが
                                    p=0.068〜0.360 で見分けられない ＝ **控えめな側**）
                    density   1.75（2本 出した日の合計 3,104 ÷ 1本目 1,777 ＝ 1日の再生）
                    rpm     256.00（同じ日・同じ本数で ショート256回 対 長尺1回）
    `≤ 1.0` の17件  全部 `outcome: falsified` か、**下がったことを実測している**
                    （density 0.77 ＝ 本数 3.4倍 で1日の再生が減った、
                      per_video 0.71 ＝ engaged 34.7%→24.7%）

**`rpm` の 256 だけは、名前と中身がずれています** —— あれは
「形を替えたら**1本あたり再生**が2桁 動いた」で、¥/1000再生 の倍率ではありません。
**それでも直しません**: `rpm` は閉じた前提が1件 ＝ `MIN_N` 未満なので
**全体の値で代用**され、`g` は**平均ではなく中央値**（4件で 1.8）なので、
**この1件は順位にも倍率にも効いていません**（冒頭「創業時の1件が桁で外れています」）。

**覆る条件**: `rpm` の閉じた前提が **3件**（`MIN_N`）に達したら、
そのとき 256 は `rpm` 自前の中央値に入ります。**その回に、単位を揃えて置き直すこと。**

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


def planned(doc: dict | None = None) -> dict:
    """**これから閉じる前提の配分。**（`share` は閉じた前提 ＝ 過去の写し）

    ## なぜ要るか（2026-08-26・最適化の回）

    軌跡は**未来**を解きます。その速さは `rate = focus_rate × share` で、
    `share` は **閉じた前提の腕べつの割合 ＝ 過去にどう振ってきたか**です。

    **しかし未来の配分は、過去ではなく「いま開いている前提」が既に決めています。**
    16本作って2週間待たないと1件も閉じないので、**これから2週間に閉じるのは、
    いま台帳に開いている15件だけ**です。**そこに per_video の前提が1件も無ければ、
    per_video の腕は、実績が何%であろうと動きません。**

    実測 2026-08-26 —— 過去と未来が食い違っていました::

        実績（閉じた21件）  per_video 60% ／ density 25% ／ sub_rate 10% ／ rpm 5%
        これから（開いた5件）rpm 60% ／ sub_rate 20% ／ density 20% ／ **per_video 0%**
        **腕の名前が無い前提 10件**（開いた15件の 67%）

    軌跡は「回転の 60% が per_video に回る」前提で 2026-12-28 を出しますが、
    **台帳には per_video の前提が1件もありません。**
    どちらの数もこの機械が持っていて、**照らし合わせている所がどこにも無い**
    ——`docs/JOURNAL.md` が「いちばん当たる」と書いている形そのものです
    （**同じことを2か所が別々に言っていて、片方しか読まれていない**）。

    ## `lever` の無い前提は、閉じたときに**丸ごと落ちます**

    `closed()` は `lever` か `effect` の無い行を `continue` で飛ばします。
    飛ばされた分は `throughput()`（＝ θ）にも入らないので、
    **1件を黙って落とすたびに、腕の速さは全部いっしょに下がります**
    （`rate = p · log(g) · θ`）。いまは閉じた21件が全部そろっていますが、
    **それは閉じるときに書き足しているからで、開いた時点では 67% が空です。**
    `unassigned` はその数です。**0 でないなら、この配分は上限側の推測**です。

    返り::

        {"share": {腕: 割合}, "n": 腕の付いた開いた前提の件数,
         "by_lever": {腕: 件数}, "unassigned": 腕の名前が無い開いた前提の件数,
         "total": 開いた前提の件数}

    **`closed()` と同じく、`hypotheses` だけを見ます**（`confirmed` は閉じた側）。
    """
    doc = _load() if doc is None else doc
    by_lever: dict[str, int] = {}
    unassigned = total = 0
    for h in doc.get("hypotheses") or []:
        if not isinstance(h, dict) or h.get("outcome") is not None:
            continue
        total += 1
        lever = h.get("lever")
        if lever in ARMS:
            by_lever[lever] = by_lever.get(lever, 0) + 1
        elif lever == "none":
            # **`none` は「この前提は腕を動かさない」と宣言した側**です。
            # 分母から外すこと —— 入れると、動かないと分かっている前提が
            # 「未来の配分」を薄めます。`unassigned`（＝空欄）とも別物です。
            continue
        else:
            unassigned += 1
    n = sum(by_lever.values())
    share = {k: by_lever.get(k, 0) / n for k in ARMS} if n else {}
    return {"share": share, "n": n, "by_lever": by_lever,
            "unassigned": unassigned, "total": total}


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

    mine = [r for r in rows if r["lever"] == lever]
    pool = [r for r in rows if r["lever"] in ARMS]
    # **θ は `pool` で数えます**（`rows` ではありません。2026-08-27 に直した）。
    #
    # `rate = p · log(g) · θ · share` の `θ · share` は「**1日に腕 X で閉じる件数**」の
    # つもりですが、`share = len(mine)/len(pool)` なので、θ を `rows`（＝ `closed()`
    # そのもの）で数えると分子だけ `none` を含み、**合計が実測とずれます**::
    #
    #     θ(rows) · Σshare = n_all  / days    ← `lever: none` を含む
    #     腕の回転の実測    = n_pool / days
    #
    # 実測 2026-08-27: **21件 ÷ 23日 = 0.913/日** に対し、腕の付いた実測は
    # **17件 ÷ 23日 = 0.739/日**。**4本の腕の伸び率が、そろって 23.5% 水増し**でした。
    # `none` は「**この前提は腕を動かさない**」と宣言した側なので、
    # **動かさないと宣言した前提が、閉じるたびに到達日を早めていた**ことになります
    # （実測の効き: `per_video` の「2倍まで」が **15日 → 19日**）。
    #
    # **同じファイルの `_pooled_p()` と `band()` は、最初から `pool` で絞っています。**
    # `planned()`（未来の配分）も 2026-08-26 に `none` を分母から外しました。
    # **4か所のうち、ここ1つだけが直っていませんでした。**
    # 検査は `tests/test_theta_arm_bearing.py`。
    th = throughput(pool, today)

    missing: list[str] = []
    if th["per_day"] is None:
        missing.append("回転の速さ（腕の付いた閉じた前提が0件）")

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
    # **連敗も θ も、腕の付いた行だけで数えます**（2026-08-27 に直した）。
    # `expected_gap` は `_pooled_p()`（＝ `ARMS` だけ）から出ているので、
    # 連敗のほうに `none` を混ぜると**別の母集団どうしを比べて**
    # 「外れすぎです」と言い出します（`none` は必ず `effect: 1.0` ＝ 非当たり）。
    pool = [r for r in rows if r["lever"] in ARMS]
    th = throughput(pool)
    n = 0
    for r in reversed(pool):
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
          f"（**腕の付いた前提だけ**。`lever: none` は数えません ——"
          "「動かさない」と宣言した前提が腕を速めていました。2026-08-27 に直した）"
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
               ready: dict[str, date] | None = None,
               unready: set[str] | None = None) -> dict:
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

    ## **`ready` が出せなかった claim を、`deadline` へ落とさないこと**（2026-08-26 20:4x）

    `ready_by_claim()` は `ready is None` の claim を**黙って落とします。**
    落ちた claim はここで `deadline` のほうへ流れ、
    **「今日が期限 ＝ 今日 閉じられる」**として印字されていました。
    実測: `eta.py` が「期日の来た前提があります → **この回は `verdict` で
    日付が動かせます**」と出した同じ1件を、`deadline_check.py` は
    「まだ数えはじめたところです。**何もしないのが正解**」と言っています。
    判定に要る本は **0本** でした（要 8本 に対し公開済み 7本・使える公開日 0日）。

    `unready`（`deadline_check.unready_claims()`）を渡すと、**その claim を
    まるごと外します** —— 開いている件数（`open`）には残しますが、
    「次に閉じられる日」の候補にはしません。渡さなければ従来どおり。

    返り: `{"on": date|None, "days": int|None, "open": 件数, "source": "ready"|"deadline"}`
    """
    doc = _load() if doc is None else doc
    today = today or today_jst()
    ready = ready or {}
    unready = unready or set()
    days: list[tuple[date, str]] = []
    n_open = 0
    for h in doc.get("hypotheses", []) or []:
        if not isinstance(h, dict) or h.get("closed_on"):
            continue
        n_open += 1
        if str(h.get("claim") or "") in unready:
            # **判定できる日が出せない前提。** `deadline` へ落とさないこと。
            continue
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


#: `forward()` が数える窓（日）。**14 を先頭に置くこと** —— いちばん短い窓が
#: いちばん過去に近く、「合っていない」を最小に見積もった姿になります。
FORWARD_HORIZONS = (14, 30, 60)


def forward(ready: dict[str, date] | None = None, doc: dict | None = None,
            today: date | None = None,
            horizons: tuple[int, ...] = FORWARD_HORIZONS) -> dict:
    """**予定表から数えた θ**（＝これから何日に1件 閉じる見込みか）。API は 0単位。

    ## なぜ要るか（2026-08-26・最適化の回。**到達日の 40% がこの1つの数に乗っています**）

    `throughput()`（＝ `scripts/eta.py` が使う θ）は
    **`closed_on` の実測 ÷ 経過日数**です。**過去だけを見ています。**
    `eta.py` の頭は「腕を **50日** 動かして、そこから 73日」と出しますが、
    その 50日 は `rate = p · log(g) · θ` の θ にそのまま反比例します
    —— **124日 のうち 50日 が、この1つの数の上に乗っています。**

    **その θ が、この機械自身の予定表と合っていません**（2026-08-26 の実測）:

        `throughput()`   21件 ÷ 22日 ＝ **0.955/日**
        予定表（開いている前提の「判定できる日」・`deadline_check.ready_by_claim()`）
                         今後14日 **7件 → 0.500/日**（過去の 0.52倍）
                         今後30日 **10件 → 0.333/日**（0.35倍）
                         今後60日 **12件 → 0.200/日**（0.21倍）

    **さらに、過去の 0.955 は率ではありません。**
    `config/hypotheses.yaml` を git の履歴で数え直すと:

        08/04〜08/19（16日間）  閉じた前提 **0件**
        08/20（1日）            **12件**   ← 溜めた16日ぶんを、1回でまとめて閉じた
        08/20〜08/26（6日間）   **5件**（0.83/日）

    **21件のうち 12件（57%）が1日に集中しています。** 分母の 22日 は
    「その速さで回っていた22日」ではなく、**16日 止まって1日で追いついた**姿です。

    ## **窓を伸ばすほど下がるのは、予定表のせいではありません**（2026-08-27）

    **`ratio` を「予定表が過去の N倍 遅い」と読まないこと。**
    分子は「**いま開いている前提**のうち、窓の内側に判定日があるもの」で、
    **`n_open` を超えられません。** 分母 `h` だけが伸びるので、
    `per_day` は窓を伸ばすほど必ず下がります —— **予定表が完璧でも**です
    （`h → ∞` で 0 に行きます）。だから `cap_per_day = n_open / h` を同じ行に出します。

    実測 2026-08-27（開いた前提 19件・過去 θ 0.913/日）::

        窓    実際      取りうる最大   実際/最大   印字していた倍率
        14日  0.643/日  1.357/日      **47%**     0.70倍
        30日  0.367/日  0.633/日      **58%**     0.40倍
        60日  0.250/日  0.317/日      **79%**     0.27倍

    **印字していた倍率と、実際/最大は、窓に対して逆を向いています。**
    「遠くを見るほど悪い」と読める行が出ていましたが、実際は
    **遠くを見るほど予定表は最大に近く、縛っているのは台帳の件数のほう**です。
    60日窓で 0.27倍 が出るのは、19件しか無い台帳を60で割ったからで、
    **予定を1日も動かせない**（最大 0.35倍）。**そこを直しに行くと空振りします** ——
    長い窓の θ を上げる手は**前提を増やすこと**だけで、
    それは `scripts/eta.py --alloc`（どの腕に立てるか）の側の話です。

    ### **`cap_per_day` は緩い天井です**（この註を消さないこと）

    `n_open / h` は「**開いた前提が全部、窓の内側で判定できたら**」の数で、
    **短い窓ほど届かない**天井です —— 前提を立ててから判定できるまでは
    「群の床（16〜72本）＋ 落ち着き7日 ＋ Analytics 3日」かかるので、
    14日窓で19件が全部そろうことは**物理的にありません。**
    だから `head`（実際/最大）は、短い窓で**低く出すぎます。**

    **それでも `ratio` だけを出すよりましです。** `ratio` は
    「予定表が過去の N倍 遅い」と読まれ、**直しに行ける所を名指ししません。**
    `head` は緩くても「**どちらの窓が予定で動くか**」を分けます。

    **覆る条件**: `scripts/queue_lag.py` の「入れ替えるだけで何日 早まるか」は、
    予定を最適に組み直したときの `ready` を実際に解いています。
    **あれを窓ごとに全前提へ広げられたら、天井はそちらへ差し替えること**
    （`n_open / h` は要らなくなります）。広げないうちに
    `head` の**絶対値**を根拠に何かを決めないこと —— 使ってよいのは
    **窓どうしの向き**（どちらが予定で動くか）だけです。

    ## **予定表の側は下限です**（この註を消さないこと）

    数えているのは**いま開いている前提だけ**で、これから立つぶんは入っていません。
    実測では **1.5件/日 立って 0.83件/日 閉じています**（08/20〜08/26・git 履歴）。
    立ったものの一部は窓の内側で閉じるので、**本当の θ は予定表と過去の間**です。

    **その凍結が効く度合いは、窓ごとに違います。** 前提を立ててから判定できるまでは
    「16本 ＋ 落ち着き7日 ＋ Analytics 3日」＝ **最短でも2週間ほど**かかるので、
    **14日窓では『これから立つぶん』はほとんど入りません**（凍結は無害に近い）。
    60日窓では 90件（1.5/日 × 60）が入らないまま割っていて、**凍結が支配します。**
    **短い窓ほど信用できる、というのはこの意味です。**

    **だから片方に置き換えないこと。** `eta.py` は `throughput()` を使い続け、
    **予定表の側を同じ行に並べます** —— `CLAUDE.md` が
    「**裸の『届きません』を出さないこと。何を固定したせいでそう出たのかを
    同じ行に並べること**」と言っているのと、同じ扱いです。
    **θ にも同じことが要る**、というだけの話です。

    ## 覆る条件

    - **予定表の側が過去に追いついたら**（14日 窓の比が 0.8 を超えたら）、
      この行は要りません。並べる意味は「合っていない」ことにあります
    - **`ready` が空で返るとき**（`deadline_check` が読めない）は
      `per_day` を出さず `missing` に理由を残します。**黙って 0 にしないこと** ——
      0 にすると θ が 0 になり、到達日が「出ません」に化けます

    返り: `{"horizons": [{"days", "n", "per_day", "ratio"}...], "dated": 件数,
             "undated": 件数, "backward": float|None, "missing": str|None}`
    """
    doc = _load() if doc is None else doc
    today = today or today_jst()
    # **ここの `back` は `arm()` の θ とは別の数です**（2026-08-27 に分かれた）。
    #   `arm()` は `lever` が `ARMS` の行だけで θ を数えます（`none` を入れると
    #   「動かさないと宣言した前提」が4本の腕を速めるため。実測 23.5% 水増し）。
    #   こちらの分子は「**いま開いている前提のうち、窓の内側に判定日があるもの**」で、
    #   腕の有無で絞っていません。**同じ母集団と比べるには、こちらも `none` 込み**です。
    #   だから `arm()` の 0.74/日 と、ここの 0.91/日 は**食い違いではありません。**
    #   **片方を写して置き換えないこと** —— 揃えるなら、分子の側も同時に絞ること。
    back = throughput(closed(doc), today)["per_day"]

    n_open = sum(1 for h in (doc.get("hypotheses") or [])
                 if isinstance(h, dict) and not h.get("closed_on"))

    if not ready:
        return {"horizons": [], "dated": 0, "undated": n_open, "backward": back,
                "missing": "判定できる日が1件も取れませんでした"
                           "（`deadline_check.ready_by_claim()` が空）"}

    days = sorted(d for d in ready.values() if isinstance(d, date))
    out = []
    for h in horizons:
        n = sum(1 for d in days if 0 <= (d - today).days <= h)
        per = n / h
        # --- **その窓で取りうる最大**（2026-08-27・最適化の回。下の註を読むこと） ---
        #     分子は「**いま開いている前提**のうち、窓の内側に判定日があるもの」で、
        #     **`n_open` を超えられません。** 分母 `h` だけが伸びるので、
        #     `per_day` は窓を伸ばすほど必ず下がります —— **予定表が完璧でも**です。
        cap = (n_open / h) if h else None
        out.append({"days": h, "n": n, "per_day": per,
                    "ratio": (per / back) if back else None,
                    "cap_per_day": cap,
                    "cap_ratio": (cap / back) if (back and cap is not None) else None,
                    "head": (per / cap) if cap else None})
    return {"horizons": out, "dated": len(days),
            "undated": max(n_open - len(days), 0), "backward": back,
            "open": n_open, "missing": None}


def forward_line(fw: dict) -> str | None:
    """`forward()` を、`eta.py` の頭に並べる1行にする。**合っていれば `None`。**

    **黙って消える条件は1つだけ**（14日 窓が過去の 0.8倍 以上 ＝ 予定表が
    過去に追いついている）。読めなかったときは**消さずに、読めなかったと言います。**
    """
    if fw.get("missing"):
        return ("### **腕の回転 θ の裏取りができません** —— "
                f"{fw['missing']}。**到達日はこの θ に反比例します**"
                "（`eta.py` の『腕を N日 動かして』の N）")
    hs = fw.get("horizons") or []
    if not hs:
        return None
    first = hs[0]
    if first.get("ratio") is not None and first["ratio"] >= 0.8:
        return None
    back = fw.get("backward")
    # **`ratio` だけを並べないこと**（2026-08-27・最適化の回）。
    #     分子は開いた前提の件数で頭打ち、分母だけが伸びるので、
    #     **予定表が完璧でも窓を伸ばすほど `ratio` は下がります。**
    #     「遠くほど悪い」と読める行が出て、直しに行くと空振りします ——
    #     長い窓を上げる手は**前提を増やすこと**だけ（`eta.py --alloc`）。
    #     だから `実際/取りうる最大` を同じ括弧に入れます。
    parts = ", ".join(
        f"今後{h['days']}日 **{h['per_day']:.2f}/日**（{h['ratio']:.2f}倍"
        + (f"／この窓で取りうる最大の **{h['head']:.0%}**" if h.get("head") else "")
        + "）"
        for h in hs if h.get("ratio") is not None)
    extra = (f"／**日の付いていない開いた前提 {fw['undated']}件**は数えていません"
             if fw.get("undated") else "")
    # **どこを直せば上がるか**を、同じ行に名指しする（裸の倍率を出さない）。
    # **`cap_ratio` まで揃っている窓だけを候補にすること。** `back` が無い回は
    #     `cap_ratio` が `None` になり、下の書式で `TypeError` を上げます ——
    #     そこは `eta.py` 側が `except Exception` で飲むので、
    #     **この行ごと黙って消えます**（消えたことは誰にも見えません）。
    usable = [h for h in hs
              if h.get("head") is not None and h.get("cap_ratio") is not None]
    worst = min(usable, key=lambda h: h["head"], default=None)
    best = max(usable, key=lambda h: h["head"], default=None)
    how = ""
    if worst is not None and best is not None:
        how = (f" **上げ方は窓で違います**: 今後{worst['days']}日 は最大の"
               f" {worst['head']:.0%} なので**予定を手前に倒せば上がります**"
               f"（`scripts/queue_lag.py`）。今後{best['days']}日 は既に"
               f" {best['head']:.0%} で、**台帳が {fw.get('open')}件 しか無いのが天井**"
               f"（最大 {best['cap_ratio']:.2f}倍）—— **予定を動かしても上がりません。"
               "前提を増やすこと**（`python scripts/eta.py --alloc`）。")
    return (f"### **上の日付は θ＝{back:.2f}/日（`closed_on` の過去の実測）に"
            f"反比例します。予定表から数えると {parts}** —— "
            "予定表の側は**下限**です（これから立つ前提を数えていない。"
            "**凍結は短い窓ほど無害**: 立ててから判定できるまで最短2週間）が、"
            "**この差のぶん、上の日付は早すぎます**"
            f"（`src/arm_speed.forward()`{extra}）。{how}")


#: `speed_weights()` が使う窓（日）。**14日 ではなく 30日 を既定にしています。**
#
# 14日 窓は 2026-08-27 の実測で `sub_rate` が **0件**（＝ θ=0）になります。
# 重みを 0 にすると `rate` が 0 になり、その腕が「出ません」に化けます ——
# **予定表は下限**（これから立つ前提を数えていない）なので、
# 「いま近い期日が無い」を「永久に閉じない」と読むのは行きすぎです。
# 30日 窓は 4本とも非ゼロで、しかも差はそのまま残ります
# （実測 per_video 0.100 ／ sub_rate 0.033 ／ rpm 0.133 ／ density 0.100）。
SPEED_WINDOW_DAYS = 30


def forward_by_arm(ready: dict[str, date] | None = None,
                   doc: dict | None = None,
                   today: date | None = None,
                   horizons: tuple[int, ...] = FORWARD_HORIZONS) -> dict[str, dict]:
    """**腕べつの「予定表 θ」。** `forward()` を腕で割ったもの。API は 0単位。

    ## なぜ要るか（2026-08-27 に足した。**`--alloc` の推薦が裏返る幅です**）

    `scripts/eta.py --alloc`（「次の前提をどの腕に立てるのがいちばん早いか」）は、
    `rate = focus_rate × share` の `focus_rate` を腕ごとに出しています。
    ところが `focus_rate = p · log(g) · θ` の **θ は `throughput()`** ——
    **全体の実測ひとつを、4本とも同じ値で使っています。**

    さらに `arm()` は、閉じた前提が `MIN_N`（=3）に満たない腕の
    `p` と `g` を**全体で代用**します。つまり `sub_rate`（2件）と
    `rpm`（1件）は **p も g も θ も全部 同じ値**になり、
    **順位が天井の遠さだけで決まります**（`alloc_search()` 自身がそう印字しています）。

    **その結果、実測 2026-08-27 に `--alloc` はこう言いました**:

        **いちばん早いのは `sub_rate`**（そのままより **4日 早い**）

    同じ日に、台帳の**開いている前提の「判定できる日」**を腕で割るとこうです
    （`deadline_check.ready_by_claim()`）:

        腕          閉じた  開いた   今後14日   今後30日   今後60日
        per_video     10      5      0.214     0.100     0.067
        sub_rate       2      4      **0.000** 0.033     0.050
        rpm            1      4      0.214     0.133     0.067
        density        4      5      0.214     0.100     0.067

    **`sub_rate` は、今後14日 に1件も閉じられません**（いちばん早い判定日が
    2026-09-16 ＝ 20日 先）。他の3本はどれも 14日 以内に1件あります
    （density 08-28 ／ rpm 09-01 ／ per_video 09-05）。
    **`--alloc` は、4本のうち唯一 near-term の回転がゼロの腕を推薦していました。**

    独立の裏も取れています —— 2026-08-27 06:1x の回は
    「`sub_rate` の実験は、思っていたより **15倍 遠い**。この速さだと **約20周**」
    と測って、同じ結論に別の道から着いています（`docs/JOURNAL.md`）。

    ## 返り

    腕 → `forward()` と同じ形の辞書（`horizons` / `dated` / `undated` /
    `backward` / `missing`）。**`backward` は全体の値のまま**です
    （腕べつに割ると分母が1〜2件になり、率になりません）。

    ## 覆る条件

    - **どの腕も `MIN_N` に届いたら**（`arm()` の `source` が4本とも「自前」）、
      順位は `p` と `g` で割れるので、この重みは要らなくなるかもしれません。
      そのときは重みを外して、順位が変わるかを見ること
    - **`ready` が空**（`deadline_check` が読めない）なら、腕べつも出せません。
      `missing` に理由を残して、**黙って 1.0 にしないこと**
    """
    doc = _load() if doc is None else doc
    today = today or today_jst()
    # **ここの `back` は `arm()` の θ とは別の数です**（2026-08-27 に分かれた）。
    #   `arm()` は `lever` が `ARMS` の行だけで θ を数えます（`none` を入れると
    #   「動かさないと宣言した前提」が4本の腕を速めるため。実測 23.5% 水増し）。
    #   こちらの分子は「**いま開いている前提のうち、窓の内側に判定日があるもの**」で、
    #   腕の有無で絞っていません。**同じ母集団と比べるには、こちらも `none` 込み**です。
    #   だから `arm()` の 0.74/日 と、ここの 0.91/日 は**食い違いではありません。**
    #   **片方を写して置き換えないこと** —— 揃えるなら、分子の側も同時に絞ること。
    back = throughput(closed(doc), today)["per_day"]

    lever_of: dict[str, str] = {}
    open_n: dict[str, int] = {k: 0 for k in ARMS}
    for h in doc.get("hypotheses") or []:
        if not isinstance(h, dict) or h.get("closed_on"):
            continue
        lev = h.get("lever")
        if lev in ARMS:
            lever_of[str(h.get("claim"))] = lev
            open_n[lev] += 1

    out: dict[str, dict] = {}
    if not ready:
        for k in ARMS:
            out[k] = {"horizons": [], "dated": 0, "undated": open_n[k],
                      "backward": back,
                      "missing": "判定できる日が1件も取れませんでした"
                                 "（`deadline_check.ready_by_claim()` が空）"}
        return out

    dated: dict[str, list[date]] = {k: [] for k in ARMS}
    for claim, lev in lever_of.items():
        d = ready.get(claim)
        if isinstance(d, date):
            dated[lev].append(d)

    for k in ARMS:
        days = sorted(dated[k])
        hs = []
        for h in horizons:
            n = sum(1 for d in days if 0 <= (d - today).days <= h)
            per = n / h
            hs.append({"days": h, "n": n, "per_day": per,
                       "ratio": (per / back) if back else None})
        out[k] = {"horizons": hs, "dated": len(days),
                  "undated": max(open_n[k] - len(days), 0),
                  "backward": back, "missing": None}
    return out


def speed_weights(by_arm: dict[str, dict] | None = None,
                  window: int = SPEED_WINDOW_DAYS) -> dict:
    """**腕べつの「回転の重み」**（平均が 1 になるように正規化した倍率）。

    `focus_rate` に掛けて使います。**全体の水準は動かしません** ——
    動かすのは腕どうしの**並び**だけです。

    ## なぜ「置き換え」ではなく「重み」なのか

    `forward()` の註がこう言っています（**消さないこと**）:

        **予定表の側は下限です。** 数えているのは いま開いている前提だけで、
        これから立つぶんは入っていません。**だから片方に置き換えないこと。**

    到達日の**水準**は `throughput()`（過去の実測）のままにして、
    **腕どうしの比だけ**を予定表から取ります。平均を 1 に正規化してあるので、
    4本を平らに均せば全体の速さは変わりません。

    ## 下限であることの効かせ方（**縮め**）

    生の比をそのまま使うと、近い期日が1件も無い腕が 0 になります。
    予定表は下限なので、それは行きすぎです。**平均を1件ぶんの「事前」として足します**:

        w_arm = (θ_arm + m) / (θ_mean + m)     m = θ_mean

    実測 2026-08-27（30日 窓・θ_mean = 0.0917/日）:

        per_video 0.100 → **1.05**   sub_rate 0.033 → **0.68**
        rpm       0.133 → **1.23**   density  0.100 → **1.05**

    **生の比なら sub_rate は 0.36 でした。** 縮めで 0.68 —— 半分だけ効きます。

    ## 覆る条件

    - **予定表が過去に追いついたら**（`forward()` の 14日 窓の比が 0.8 以上）、
      腕べつの差も過去の配分で説明できるので、この重みは要りません
    - **縮めの強さ（いまは「平均1件ぶん」）は勘です。**
      `--alloc` の推薦どおりに立てた前提が、その腕の予定どおりに閉じたかを
      3件 集めたら、縮めをその実績で決め直すこと

    返り: `{"weights": {腕: 倍率}, "raw": {腕: θ}, "mean": float,
             "window": int, "missing": str|None}`
    """
    by_arm = forward_by_arm() if by_arm is None else by_arm
    raw: dict[str, float] = {}
    for k in ARMS:
        hs = (by_arm.get(k) or {}).get("horizons") or []
        hit = [h for h in hs if h.get("days") == window]
        if not hit:
            return {"weights": {k2: 1.0 for k2 in ARMS}, "raw": {}, "mean": None,
                    "window": window,
                    "missing": ((by_arm.get(k) or {}).get("missing")
                                or f"{window}日 の窓が `forward_by_arm()` にありません")}
        raw[k] = float(hit[0]["per_day"])

    mean = sum(raw.values()) / len(raw) if raw else 0.0
    if mean <= 0:
        # **全部 0** ＝ 予定表に近い期日が1件も無い。並べ替える根拠が無いので
        # **1.0 のまま返します**（黙って 0 にすると到達日が「出ません」に化ける）。
        return {"weights": {k: 1.0 for k in ARMS}, "raw": raw, "mean": mean,
                "window": window,
                "missing": f"{window}日 以内に判定できる前提が、どの腕にもありません"}

    weights = {k: (raw[k] + mean) / (mean + mean) for k in ARMS}
    return {"weights": weights, "raw": raw, "mean": mean,
            "window": window, "missing": None}
