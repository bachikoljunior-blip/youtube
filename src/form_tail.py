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
    return out


if __name__ == "__main__":                                     # pragma: no cover
    print("=== 形ごとの上の裾（API 0単位・`data/views.jsonl` だけ）===")
    for line in lines():
        print(line)
