"""**登録率の天井を、定義ではなく実測から出す。**（2026-08-28 に足した）

## なぜ要るか（実測。`scripts/eta.py` の出力がそのまま根拠です）

`scripts/eta.py` の `physical_caps()` は、`sub_rate`（登録率）の天井を
**ずっと「登録率 100%」**で置いていました。同じ関数の docstring が

    sub_rate   登録率 100%（**定義上の上限**。測った天井ではありません）

と自分で断っており、印字にも `← **実測の天井ではありません**` が出ます。
**断ってはいましたが、軌跡はその数をそのまま歩いていました。**
2026-08-28 の実測:

    天井 `sub_rate` ×3,153.91 …… 登録率 100%（定義上の上限）
    軌跡の 56日目の内訳        …… `sub_rate` ×10.36
    この腕を凍らせると軌跡は **+114日** → **必要な腕です**

つまり **到達日 2027-01-07 は、「登録率が ×10.36 になる」という前提の上**に
乗っていました。その ×10.36 が実在の幅の中かどうかを、
**誰も確かめていません**（確かめようがない ——「100%」は測った数ではないので、
どんな倍率でも天井の下に入ります）。

`per_video` の天井は**実測の最大**（1本あたり再生 1,891回・ショート39本の最大）です。
**同じ物差しを登録率にも当てる**、というのがこのファイルです。

## 出すもの

`data/shorts_subs.json` の `videos`（動画べつの `views` と `subs_gained`）から、
**1本あたり登録率の実測の最大**を出します。2026-08-28 の実物:

    いまの登録率（チャンネル28日）  0.0317%  ＝ 1,000再生に 0.317人
    実測の最大（1,000再生以上の76本） 0.2066% ＝ 1,000再生に 2.07人
                                     `CdX2oIb7BG8`（1,452再生・3人）
    → 天井 **×6.5**（×3,153.91 ではない）

**門（登録者1,000人）に要るのは 0.066%** なので、**この天井の下にあります** ——
つまりこの直しは「届かない」と言っていません。**要る倍率 ×2.08 と、
実在する幅 ×6.5 を、同じ物差しで並べられるようにしただけ**です。

## 割り引いて読むこと

- **最大は上振れした統計です。** 76本のうち最大を採るので、
  当たり前に「たまたま良かった1本」が出ます。**天井としては、それでよい** ——
  下限ではなく「実際に一度は起きた線」を採るのが `per_video` と同じ扱いです
- **1本の登録者数は小さい整数です。** 3人／1,452再生なので、
  **±1人で ±0.07%** 動きます。だから `min_views` を置いて、
  **1人が丸ごと天井になる本を外します**（既定 1,000再生 ＝ 1人でも 0.1%）
- **`data/shorts_subs.json` は API で取り直すもの**なので古くなります。
  `age_days` を `why` に出します。**古い＝低いほうへ寄る**（新しい本が入らない）ので、
  古い天井は**低め**に出ます。天井としては安全側です
- `subs_lost` は引きません（`scripts/eta.py` の `sub_rate` が
  `subs_gained_28d ÷ views_28d` なので、**分子の定義をそろえています**）

**覆る条件**: 動画べつの登録者を Analytics が返さなくなったら（`traffic_subs_supported`
が False の日がある）、`videos` が空になり `None` を返します ——
そのとき `physical_caps()` は**元の「100%」に落ちます**。
消したのではなく、**測れた回だけ実測を使う**形です。
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "data" / "shorts_subs.json"

#: 1本が丸ごと天井になるのを避けるための下限。
#: **1,000再生あれば、登録1人でも 0.1%** で、いまのチャンネル（0.0317%）の 3.2倍。
#: これより低くすると「200再生で1人＝0.5%」のような本が天井になります。
MIN_VIEWS = 1000.0


def _age_days(at: str | None) -> float | None:
    if not at:
        return None
    try:
        t = datetime.fromisoformat(at)
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400.0


def best_per_video(path: Path | None = None,
                   min_views: float = MIN_VIEWS) -> dict | None:
    """**1本あたり登録率の実測の最大**。測れなければ `None`。

    返すのは割合（`rate`）そのもので、`scripts/eta.py` の
    `a0["sub_rate"]` と**同じ単位**（再生1回あたりの人数）です。

    >>> best_per_video(Path("/does/not/exist"))    # 無ければ黙って None
    """
    p = Path(path) if path is not None else SRC
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(doc, dict):
        return None
    vids = doc.get("videos")
    if not isinstance(vids, list):
        return None

    best: dict | None = None
    n = 0
    for v in vids:
        if not isinstance(v, dict):
            continue
        try:
            views = float(v.get("views") or 0.0)
            subs = float(v.get("subs_gained") or 0.0)
        except (TypeError, ValueError):
            continue
        if views < min_views:
            continue
        n += 1
        rate = subs / views
        if best is None or rate > best["rate"]:
            best = {"rate": rate, "video": v.get("id"), "title": v.get("title"),
                    "form": v.get("form"), "views": views, "subs": subs}
    if best is None or best["rate"] <= 0:
        return None
    best["n"] = n
    best["min_views"] = min_views
    best["at"] = doc.get("at")
    best["age_days"] = _age_days(doc.get("at"))
    return best


def swing(best: dict) -> tuple[float, float]:
    """**分子が1人 増減したときの、この天井の上下**（割合で返す）。

    登録率の分子は**人数の整数**なので、1人 動くと天井がまるごと動きます。
    `per_video` の分子は再生回数（4桁）なので、**この揺れは向こうにありません。**
    """
    views = float(best["views"])
    subs = float(best["subs"])
    return (max(0.0, subs - 1) / views, (subs + 1) / views)


def why(best: dict) -> str:
    """`physical_caps()` の `why` に入れる1行（**出どころを必ず併記する**）。

    ##### **分子の人数と、その ±1人 の幅を、同じ行に出すこと**（2026-08-29 に足した）

    このモジュールの docstring は、最初からこう断っていました ——
    「**1本の登録者数は小さい整数です。**3人／1,452再生なので、±1人で ±0.07% 動きます」。
    **断りは docstring にしか無く、判断する側が読む行には出ていませんでした。**

    判断する側の行は `scripts/eta.py --alloc` の

        天井 `sub_rate` ×6.86 …… 1本あたり登録率の**実測の最大** 0.2091%
            （`CdX2oIb7BG8` 1,435再生 3人／38本 中…） ← **`per_video` と同じ物差し**

    で、**「`per_video` と同じ物差し」だけが強調されています。**
    物差し（実測の最大）は同じですが、**分子の桁が違います** ——
    向こうは再生 1,891回、こちらは **3人**。3人の最大は、38本ぶんの
    「たまたま」を最大で拾った数なので、**±1人で天井が3分の2 から 3分の4 まで動きます。**

    実測: `--alloc` の名指し（`sub_rate` がいちばん早い）は
    **4回 続けて見送られています**（08-28 19:5x / 21:3x / 08-29 00:5x / 04:0x）。
    4回とも理由は別々でしたが、**見送る側が毎回この揺れを手で確かめ直していました。**
    **手で確かめ直すものは、印字する側に置くこと。**

    **覆る条件**: `min_views` を上げて分子が2桁になったら、この註は要りません
    （そのとき `swing()` の幅は自然に狭まるので、印字も短くなります）。
    """
    age = best.get("age_days")
    stale = f"・**{age:.1f}日前の観測**" if age is not None else ""
    low, high = swing(best)
    return (f"1本あたり登録率の**実測の最大** {best['rate'] * 100:.4f}%"
            f"（`{best.get('video')}` {best['views']:,.0f}再生 {best['subs']:,.0f}人"
            f"／{best['n']}本 中・{best['min_views']:,.0f}再生 以上{stale}）"
            f" ← **`per_video` と同じ物差し**（実測の最大）。"
            f"**登録率100% は測った天井ではないので、こちらが低いときはこちらを採ります**"
            f"。 [!] **分子は {best['subs']:,.0f}人 の整数です** ——"
            f" ±1人 で天井は {low * 100:.4f}%〜{high * 100:.4f}% まで動きます"
            f"（`per_video` の分子は再生回数なので、**向こうにこの揺れはありません**）")
