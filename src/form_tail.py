"""**形ごとに、1本あたり再生の「上の裾」がどんな形か**（**API 0単位**）。

読むのは `data/views.jsonl` と `data/video_forms.json` だけです。
YouTube には1回も触りません。

## なぜ要るか（2026-09-02 01:2x に測って足した）

`scripts/eta.py` は毎周こう印字します:

    → **引けるのは `per_video` だけです。** 日付が出はじめるのは ×101.09、
      いまの天井は ×4.16 —— **天井そのものを ×24.31 上げないと出ません。**
      ＝ **この回に立てるべき前提は「その天井は天井ではない」**

その天井（`src/rule_per_video.ceiling_at_rule()` ＝ 3,918回）は、
**記録 1,891回（`NHKylqsNfTw`）を1段 外挿したもの**です。
つまり**この repo の per_video の天井は、実質「観測された最大値」1本で立っています。**

**最大値が天井かどうかは、上の裾の形で分かります。** 硬い壁があるなら
上位は壁に張り付いて団子になり、裾が伸びているなら上位は散らばります。

## この回に測った値（**同じ引数で誰でも再現できます**）

    ショート  n=171  max=1,891  max/10位 **1.33**  Hill(k=10) **8.81**
    長尺      n= 24  max=  156  max/10位 **39.00** Hill(k=10) **0.77**

**団子は 1.33 の側です。** ただし `max/10位` は n で動くので、そのままでは
比べられません（本数が少ないほど上位は散らばります）。**間引いて揃えました**
—— ショートを **n=24 へ 2,000回** 間引くと `max/10位` の中央値は **4.20**
（5〜95%: 1.74〜8.08・2,000回の最大 16.38）。

    **長尺の実測 39.00 は、その 2,000回 のどれよりも大きい（p < 0.0005）**

**＝ 本数の差では説明できません。** 同じチャンネル・同じ台本の作り・同じ合成音声で、
**ショートの上だけが詰まっています。** 中身の天井なら両方に出るはずの形です。

**これは「長尺のほうが伸びる」という話ではありません**（長尺の最大は 156回で、
ショートの 1/12 です）。言えるのは**壁の在り所**だけ ——
**1,891 はショートの面（SHORTS_FEED）の、1本あたり配信の上限に見える**、という一点です。

## 覆る条件

- **長尺が 24本 しかありません。** 本数が増えて `max/10位` が 4.20 前後まで
  落ちたら、この差は消えます（そのとき上の前提は falsified）
- `data/video_forms.json` の形の札は Analytics の `creatorContentType` で、
  **90日窓**です。窓の外の本は `None` に落ちます（この回は 53本）
- 面そのものを測れるようになったら（`insightTrafficSourceType`）、
  **形の代わりに面で割ること。** 形は面の代理でしかありません
"""
from __future__ import annotations

import json
import math
import random
from datetime import date
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"
FORMS = ROOT / "data" / "video_forms.json"

#: 上位の団子ぐあいを見る順位（`max ÷ K位`）。
TOP_K = 10
#: 間引きの回数（`p` の分母）。
DRAWS = 2000
#: 種。**固定します** —— 同じ数が二度 出ないと、前提の判定に使えません。
SEED = 20260902


def best_views(path: Path | None = None) -> dict[str, int]:
    """本ごとの生涯最大の再生（`data/views.jsonl` の観測の最大）。"""
    out: dict[str, int] = defaultdict(int)
    p = path or VIEWS
    if not p.is_file():
        return {}
    with p.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            vid, v = r.get("id"), r.get("views")
            if not vid or v is None:
                continue
            try:
                v = int(v)
            except (TypeError, ValueError):
                continue
            if v > out[vid]:
                out[vid] = v
    return dict(out)


def forms_map(path: Path | None = None) -> dict[str, str]:
    """本 → 形（`ショート` / `長尺`）。読めなければ空。"""
    p = path or FORMS
    if not p.is_file():
        return {}
    try:
        return dict(json.loads(p.read_text()).get("forms") or {})
    except (ValueError, AttributeError):
        return {}


def top_ratio(vals, k: int = TOP_K) -> float | None:
    """`max ÷ k位`。**大きいほど上位が散らばっています**（＝ 壁が無い）。"""
    vals = sorted(vals, reverse=True)
    if len(vals) <= k or vals[k - 1] <= 0:
        return None
    return vals[0] / float(vals[k - 1])


def hill(vals, k: int = TOP_K) -> float | None:
    """Hill の裾指数。**小さいほど裾が重い**（＝ 上が伸びている）。"""
    vals = sorted(vals, reverse=True)
    if len(vals) <= k or vals[k] <= 0:
        return None
    s = sum(math.log(vals[i]) - math.log(vals[k]) for i in range(k))
    return (k / s) if s > 0 else None


def shape(views_path: Path | None = None, forms_path: Path | None = None,
          k: int = TOP_K, draws: int = DRAWS, seed: int = SEED) -> dict:
    """**形ごとの上の裾と、本数を揃えたときの差**（**API 0単位**）。

    返すのは `{"ショート": {...}, "長尺": {...}, "matched": {...}}`。
    `matched` は「**多いほうを少ないほうの本数へ間引いた**とき、
    少ないほうの実測がどれくらい珍しいか」（`p`）。
    """
    best = best_views(views_path)
    forms = forms_map(forms_path)
    groups: dict[str, list[int]] = defaultdict(list)
    for vid, v in best.items():
        f = forms.get(vid)
        if f:
            groups[f].append(v)
    out: dict = {}
    for f, vals in groups.items():
        vals = sorted(vals, reverse=True)
        out[f] = {"n": len(vals), "max": vals[0] if vals else None,
                  "top_ratio": top_ratio(vals, k), "hill": hill(vals, k)}
    big, small = None, None
    if len(groups) >= 2:
        order = sorted(groups.items(), key=lambda kv: -len(kv[1]))
        big, small = order[0], order[1]
    if not big or not small or len(small[1]) <= k:
        out["matched"] = None
        return out
    obs = top_ratio(small[1], k)
    rng = random.Random(seed)
    got = []
    for _ in range(draws):
        r = top_ratio(rng.sample(big[1], len(small[1])), k)
        if r:
            got.append(r)
    got.sort()
    out["matched"] = {
        "big": big[0], "small": small[0], "n": len(small[1]), "draws": len(got),
        "median": (got[len(got) // 2] if got else None),
        "p05": (got[int(0.05 * len(got))] if got else None),
        "p95": (got[int(0.95 * len(got))] if got else None),
        "max": (got[-1] if got else None),
        "observed": obs,
        # **0.0 は「2,000回に1回も出なかった」**（＜ 1/draws）。0 と書かないこと。
        "p": (sum(1 for x in got if obs is not None and x >= obs) / len(got)
              if got else None),
    }
    return out


#: 「棚」を数える高さ（`max` の何割以上を、棚に載っているとみなすか）。
#: **0.75 は掛け算してから置きました** —— `max/10位` が 1.33 ＝ 10位が max の 75.1%
#: なので、**この高さは「上位10本がまるごと入るぎりぎり」**です。0.9 に上げると
#: 3本しか残らず「たまたま近い2本」と区別が付かず、0.5 まで下げると 45本 ＝
#: 分布の胴まで拾って、棚かどうかを言えなくなります。
SHELF_FRAC = 0.75
#: 棚と呼ぶのに要る本数（これ未満なら「たまたま近い数本」）。
SHELF_MIN_N = 5
#: 棚と呼ぶのに要る、初観測日の広がり（日）。**同じ日の本だけなら、
#: 面ではなくその日の出来事（1本が跳ねて連れて上がった）で説明が付きます。**
SHELF_MIN_SPAN_DAYS = 7


def first_seen(path: Path | None = None) -> dict[str, str]:
    """本 → いちばん最初にその本を観測した時刻（`data/views.jsonl` の並び順）。"""
    out: dict[str, str] = {}
    p = path or VIEWS
    if not p.is_file():
        return {}
    with p.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except ValueError:
                continue
            vid, at = r.get("id"), r.get("at")
            if vid and at and vid not in out:
                out[vid] = str(at)
    return out


def shelf(form: str = "ショート", frac: float = SHELF_FRAC,
          views_path: Path | None = None, forms_path: Path | None = None) -> dict:
    """**その形の上端は「棚」か、それとも「1本の飛び出し」か**（**API 0単位**）。

    `max/10位` は「上位が団子か」しか言いません。**団子は1日で作れます** ——
    1本が跳ねて、同じ日の隣の本を連れて上げれば、上位は簡単に固まります。
    **棚（＝配信の上限）なら、別々の日に出した別々の題が、
    何度でも同じ高さで止まります。**

    返すのは `{"n", "max", "shelf_n", "span_days", "days", "is_shelf"}`。
    `is_shelf` が真なのは **`shelf_n >= SHELF_MIN_N` かつ
    `span_days >= SHELF_MIN_SPAN_DAYS`** のとき。

    **これは `matched` の p 値とは別の証拠です** —— あちらは
    「本数の差では説明できない」、こちらは「その日の出来事では説明できない」。
    """
    best = best_views(views_path)
    forms = forms_map(forms_path)
    seen = first_seen(views_path)
    vals = sorted(((v, vid) for vid, v in best.items() if forms.get(vid) == form),
                  reverse=True)
    if not vals:
        return {"n": 0, "max": None, "shelf_n": 0, "span_days": None,
                "days": [], "is_shelf": False}
    top = vals[0][0]
    on = [(v, vid) for v, vid in vals if v >= top * frac]
    days = sorted({seen[vid][:10] for _, vid in on if vid in seen})
    # **1日しか無い ＝ 幅 0日**（`None` にしないこと —— `None` は
    # 「日付が1つも読めなかった」の意味に取っておきます。混ぜると
    # 「同じ日に固まった団子」が「測れていない」と同じ扱いになり、門が素通りします）。
    span = None
    if len(days) == 1:
        span = 0
    elif len(days) >= 2:
        a = date.fromisoformat(days[0])
        b = date.fromisoformat(days[-1])
        span = (b - a).days
    return {
        "n": len(vals), "max": top, "shelf_n": len(on),
        "span_days": span, "days": days,
        "is_shelf": (len(on) >= SHELF_MIN_N
                     and span is not None and span >= SHELF_MIN_SPAN_DAYS),
    }


#: 上端の弾力性を、平均の弾力性と比べるときの有意水準（両側 95%）。
Z95 = 1.96


def _ols(xs: list[float], ys: list[float]) -> dict | None:
    """log-log の最小二乗。返すのは `{"b", "se", "t", "lo", "hi", "n"}`。"""
    n = len(xs)
    if n < 4:
        return None
    mx = sum(xs) / n
    my = sum(ys) / n
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx <= 0:
        return None
    b = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx
    a = my - b * mx
    s2 = sum((y - (a + b * x)) ** 2 for x, y in zip(xs, ys)) / (n - 2)
    # **残差 0（＝ 完全に乗っている）は `None` にしないこと。**
    # 傾きが厳密に決まっている、という意味であって「測れなかった」ではありません。
    # `None` を返すと、作り物の帳面で試した回が「道具が壊れている」と読みます。
    se = math.sqrt(s2 / sxx) if s2 > 0 else 0.0
    t = (b / se) if se > 0 else (math.inf if b else 0.0)
    return {"b": b, "se": se, "t": t,
            "lo": b - Z95 * se, "hi": b + Z95 * se, "n": n}


def tail_elasticity(rows=None) -> dict | None:
    """**その日の本数を減らすと上がるのは「平均」か、「上端」もか**（**API 0単位**）。

    ## なぜ要るか（2026-09-02 に測って足した）

    `src/rule_per_video.ceiling_at_rule()` は、**観測された最大**（1,891回・
    3本/日 の日の本）に `n ** (-b)` を掛けて 1本/日 へ外挿します。
    その `b` は `rule_per_video.estimate()` の弾力性 ——
    **「その日の本数 → 1本あたり再生」の回帰**で、
    **`1本あたり再生` は平均（中心）**です。

    **平均に当てた傾きを、極値（最大）に当てています。**
    上端が棚（`shelf()` で確かめた配信の上限）なら、
    **その傾きは上端まで届きません** —— 密度を下げても棚は上がらないからです。

    ## だから、上端そのものの傾きを測ります

    日ごとに `log(その日の最大)` と `log(その日の平均)` を、
    それぞれ `log(その日の本数)` へ回帰して並べます。

    **`b_max` の 95% 区間が `b_mean` を含まなければ、外挿は上端に効いていません。**
    そのとき `ceiling_at_rule()` の `value` は `raw`（＝ 観測された最大）の
    `n ** (-b_mean)` 倍だけ上振れしていることになります。

    返すのは `{"max": {...}, "mean": {...}, "reaches_tail": bool, "inflation": float}`。
    `inflation` は「上端に効かないなら、天井は何倍 上振れか」（3 ** (-b_mean)）。
    """
    if rows is None:
        from src import rule_per_video as _rp
        rows = _rp._settled()
    if not rows:
        return None
    by: dict[str, list[int]] = defaultdict(list)
    for day, _vid, life in rows:
        if life and life > 0:
            by[day].append(int(life))
    pts = [(len(v), max(v), sum(v) / len(v)) for v in by.values() if v]
    if len(pts) < 4:
        return None
    xs = [math.log(n) for n, _mx, _mn in pts]
    fit_max = _ols(xs, [math.log(mx) for _n, mx, _mn in pts])
    fit_mean = _ols(xs, [math.log(mn) for _n, _mx, mn in pts])
    if not fit_max or not fit_mean:
        return None
    # **区間の端は、丸めの誤差で外れます。** 完全に乗っている帳面（残差 0）では
    # 区間が1点になるので、そのぶんの遊びを持たせること。
    eps = 1e-9
    reaches = fit_max["lo"] - eps <= fit_mean["b"] <= fit_max["hi"] + eps
    return {
        "max": fit_max, "mean": fit_mean, "reaches_tail": reaches,
        # **`CEILING_MAX_PER_DAY`（3本/日）から 1本/日 への1段ぶん。**
        "inflation": 3.0 ** (-fit_mean["b"]),
    }


def shelf_drift(rows=None) -> dict | None:
    """**その棚は、時間とともに上がっているか**（**API 0単位**・`data/views.jsonl` だけ）。

    ## なぜ要るか（2026-09-02 に足した）

    同じ日に2件 閉じました ——「上端は棚（配信の上限）」と
    「その棚への外挿は、平均に当てた傾きを極値に当てている」。
    **どちらも『天井はここだ』の側**で、`eta.py` は毎周
    「**この回に立てるべき前提は『その天井は天井ではない』**」と名指しします。

    棚が**チャンネルの大きさ**（登録者・面の割り当て）で決まっているなら、
    棚は**時間とともに上がるはず**です。中身をどう変えても動かないが、
    チャンネルが育てば動く —— そのとき天井は定数ではなく、
    `per_video` は「引けないが、待てば上がる」腕になります。

    **逆に傾きが 0 と区別が付かなければ、棚は本当に定数**で、
    `eta.py` の「あと ×23.24」は**待っても縮みません**
    （＝ 形を替えるしかない ＝ 腕 `rpm` の側へ逃げる根拠になります）。

    ## 測り方

    伸びきった本を**日ごと**にまとめ、`log(その日の最大)` を
    **日付の通し番号**（いちばん古い日を 0）へ回帰します。
    `tail_elasticity()` が回帰する相手は「その日の本数」で、**こちらは時間**です
    —— 別の量なので、両方 要ります。

    返すのは `{"fit": {...}, "days": n, "span_days": N, "rising": bool}`。
    `rising` は「傾きの 95% 区間が 0 より上」＝ **棚は上がっている**。
    """
    if rows is None:
        from src import rule_per_video as _rp
        rows = _rp._settled()
    if not rows:
        return None
    by: dict[str, list[int]] = defaultdict(list)
    for day, _vid, life in rows:
        if life and life > 0:
            by[day].append(int(life))
    days = sorted(by)
    if len(days) < 4:
        return None
    # `_settled()` は `date` を返しますが、作り物の帳面では文字列で来ます
    # （`shelf()` の `first_seen` 側は文字列）。**どちらでも通すこと。**
    def _d(v):
        return v if isinstance(v, date) else date.fromisoformat(str(v))

    base = _d(days[0])
    xs, ys = [], []
    for day in days:
        xs.append(float((_d(day) - base).days))
        ys.append(math.log(max(by[day])))
    fit = _ols(xs, ys)
    if not fit:
        return None
    return {"fit": fit, "days": len(days),
            "span_days": int(xs[-1] - xs[0]),
            # **片側ではなく両側の 95%** で見ます（`_ols` の `lo`/`hi` がそれ）。
            "rising": fit["lo"] > 0.0}


def lines(**kw) -> list[str]:
    """画面へ。**壁が形の側にあるかどうかを1行で。**"""
    s = shape(**kw)
    out = []
    for f in ("ショート", "長尺"):
        g = s.get(f)
        if not g:
            continue
        out.append(f"  {f:<5} n={g['n']:>4}  max={g['max']:>6}回"
                   f"  max/{TOP_K}位={g['top_ratio']:.2f}" if g["top_ratio"]
                   else f"  {f:<5} n={g['n']:>4}  max={g['max']}回（{TOP_K}位が無い）")
    m = s.get("matched")
    if m and m["observed"] and m["median"]:
        p = m["p"]
        ptxt = f"< {1.0 / max(1, m['draws']):.4f}" if not p else f"{p:.4f}"
        out.append(f"  **本数を {m['n']}本 へ揃えた**（{m['big']} を {m['draws']}回 間引き）:"
                   f" 中央値 {m['median']:.2f}（5〜95%: {m['p05']:.2f}〜{m['p95']:.2f}"
                   f"・最大 {m['max']:.2f}）")
        out.append(f"  **{m['small']} の実測 {m['observed']:.2f} が出る割合 p {ptxt}**"
                   " —— 本数の差では説明できません")
    sh = shelf(views_path=kw.get("views_path"), forms_path=kw.get("forms_path"))
    if sh["max"]:
        verdict = ("**棚です**" if sh["is_shelf"]
                   else "**棚とは呼べません**（本数か日数が足りない）")
        out.append(f"  ショート の上端 {sh['max']}回 の {int(SHELF_FRAC * 100)}% 以上に"
                   f" **{sh['shelf_n']}本**が載り、初観測日は **{len(sh['days'])}日**に"
                   f"わたります（幅 {sh['span_days']}日） → {verdict}")
        out.append("    **`max/10位` とは別の証拠です** —— あちらは「本数の差では"
                   "説明できない」、こちらは**「その日の出来事では説明できない」**。"
                   "別の日の別の題が、何度でも同じ高さで止まっています")
    te = tail_elasticity()
    if te:
        mx, mn = te["max"], te["mean"]
        out.append(f"  **その日の本数を減らして上がるのは「平均」だけです** ——"
                   f" 日ごとの**平均**の弾力性 b={mn['b']:+.3f}（t={mn['t']:+.2f}）に対し、"
                   f" 日ごとの**最大**は b={mx['b']:+.3f}（t={mx['t']:+.2f}"
                   f"・95%[{mx['lo']:+.3f}, {mx['hi']:+.3f}]・n={mx['n']}日）")
        if te["reaches_tail"]:
            out.append("    → 上端の区間が平均の b を**含んでいます**。"
                       "`ceiling_at_rule()` の外挿は上端にも効いているとみてよい")
        else:
            out.append(f"    → 上端の区間が平均の b を**含みません**。"
                       f" **`rule_per_video.ceiling_at_rule()` は、平均に当てた傾きを"
                       f"極値に当てています** ＝ 天井は **×{te['inflation']:.2f}** の上振れ"
                       f"（規則の 1日1本 での天井は、記録 {sh['max']}回 とほぼ同じ）")
    return out


if __name__ == "__main__":                                     # pragma: no cover
    import sys

    if "--drift" in sys.argv[1:]:
        print("=== その棚は上がっているか（API 0単位・`data/views.jsonl` だけ）===")
        d = shelf_drift()
        if not d:
            print("  日が 4日 に満たないので測れません")
        else:
            f = d["fit"]
            print(f"  伸びきった日 {d['days']}日／幅 {d['span_days']}日")
            print(f"  log(その日の最大) を日付へ回帰: b={f['b']:+.4f}"
                  f"  t={f['t']:+.2f}  95%[{f['lo']:+.4f}, {f['hi']:+.4f}]")
            if d["rising"]:
                print("  → **棚は上がっています。** 天井は定数ではなく、"
                      "チャンネルが育つと動く量です（`per_video` は待てば上がる腕）")
            else:
                print("  → **0 と区別が付きません。** 棚は定数として扱うこと ——"
                      " 待っても `eta.py` の隔たりは縮みません（逃げ先は形の側 ＝ 腕 `rpm`）")
    else:
        print("=== 形ごとの上の裾（API 0単位・`data/views.jsonl` だけ）===")
        for line in lines():
            print(line)
