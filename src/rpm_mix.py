"""**RPM の帯を、推測ではなく実測の混ざり方から出す。**（腕 `rpm` の天井）

`scripts/eta.py` の `physical_caps()` は、腕 `rpm` の天井をこう置いていました。

    caps["rpm"] = max(RPM_SCENARIOS.values()) / band     # ¥2,000 ÷ ¥20 = ×100
    "measured": False

そして `eta.py` は自分でこう言っています ——
**「`rpm` の天井 ×100.00 は測った天井ではありません。軌跡はここに寄りかかって
います —— 測れば動きます」**。この道具は、その1行を測るために書きました。

---

## 何を測るか（**どちらも Analytics に元から在る。推測が1つも要りません**）

    creatorContentType   shorts / videoOnDemand べつの再生数と視聴分
    country              国べつの再生数と視聴分

**`creatorContentType` は「ショートか長尺か」をチャンネル側の定義で返します。**
`eta.py` は `LONG_FORM_SECONDS = 180` を使い、
**平均視聴秒 ÷ 平均視聴率で尺を復元して**割っていました（＝復元した尺で当てる推測）。
ここでは復元しません。**YouTube 自身がどちらに数えているか**を読みます。

## なぜ「帯」ではなく「混ざり方」なのか

RPM は1本ごとに付く数ではなく、**チャンネル全体の収益 ÷ 全体の再生数 × 1000**です。
だから効いているのは帯そのものではなく、**再生がどちらの形に何%乗っているか**:

    収益 ＝ Σ_形（その形の再生 ÷ 1000 × その形の帯）
    実効RPM ＝ 収益 ÷ 全体の再生 × 1000 ＝ Σ_形（**再生**の割合 × その形の帯）

**重みは再生数です。視聴分ではありません。**（最初に書いた版は視聴分で重みを
付けていて、天井が ×41.5 と出ました。帯 ¥400 / ¥20 が「1,000**再生**あたり」の
数である以上、割合も再生で取らないと単位が合いません。視聴分で取ると
**長尺を実際より重く数えます**（1再生あたりの視聴分が長尺のほうが長いので）。
再生で取り直した天井は **×15.5**。視聴分は下に診断として残します）

`eta.py` は「いまは `ショート 低`」と**決め打ち**していました。ここは測ります。
（2026-08-20 の初測: ショート 99.77% ／ 長尺 0.23% ＝ 実効 ¥20.9。
**決め打ちは当たっていました** —— ただし当たっていたことも、いままで誰も
確かめていません。次に長尺が伸びたら、この決め打ちのほうが先に古くなります）

## 天井（**ここが ×100 と入れ替わる**）

「全部が `長尺 お金 高` になったら ¥2,000」は、**混ざり方を無視した線**です。
長尺の再生は、**長尺のサムネが見せられている回数**より上には行けません。

    長尺の1日あたり再生の上限 ＝ 長尺インプレッション/日 × CTR 100%
    混ざり方の上限           ＝ その上限 ÷（その上限 ＋ ショートの1日あたり再生）
    実効RPMの天井             ＝ 上限の割合 × 長尺お金高 ＋ 残り × ショート高

**CTR 100% は実在しませんが、上限としては正しい**（`status.py` の
「CTR 100% でも月531回」と同じ読み方です）。

**この天井は固定値ではありません。** 長尺を出せばインプレッションの面が増え、
次の回の測り直しでこの天井は上がります。**「長尺を出すと `rpm` の天井が上がる」
が、そのまま数字に出る**ということです。据え置きの ×100 では出ませんでした。
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "rpm_mix.jsonl"

#: `scripts/eta.py` の `RPM_SCENARIOS` と**同じもの**。
#: `eta.py` を import すると循環するので写していますが、
#: **`tests/test_rpm_mix.py` が食い違ったら落とします**（写しが黙って古くなる形を塞ぐ）。
BANDS = {
    "ショート 低": 20,
    "ショート 中": 35,
    "ショート 高": 60,
    "長尺 お金 低": 400,
    "長尺 お金 中": 1_000,
    "長尺 お金 高": 2_000,
}

#: Analytics の `creatorContentType` の値 → こちらの形の呼び名。
#: `liveStream` / `story` は実績が0なので、出てきたらショート側に寄せず**別に数えます**。
FORM_OF = {"shorts": "ショート", "videoOnDemand": "長尺"}

#: 国べつで「この帯でよいか」を判断する床。
#: **JP 以外の RPM は帯が違います**（日本のお金の帯は世界の中でも高いほう）。
#: いまは JP 100% なので割り引きは掛けていません。**下回ったら掛けること。**
JP_SHARE_FLOOR = 0.90


# --------------------------------------------------------------------------
# 実測（Analytics を2回だけ。Data API は叩きません）
# --------------------------------------------------------------------------
def fetch_mix(days: int = 90) -> dict[str, Any]:
    """`creatorContentType` と `country` を1回ずつ。**失敗しても回は止めない。**"""
    from googleapiclient.discovery import build

    from .auth import credentials

    analytics = build("youtubeAnalytics", "v2", credentials=credentials(),
                      cache_discovery=False)
    end = date.today()
    start = end - timedelta(days=days)

    def _q(dim: str) -> list[list]:
        try:
            res = analytics.reports().query(
                ids="channel==MINE",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics="views,estimatedMinutesWatched",
                dimensions=dim,
                sort="-views",
                maxResults=200,
            ).execute()
            return res.get("rows", []) or []
        except Exception as exc:  # noqa: BLE001 —— 計器は回を止めない
            print(f"[rpm_mix] {dim} を取れませんでした（続行）: {type(exc).__name__}: {exc}")
            return []

    return {
        "days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "by_form": {r[0]: {"views": float(r[1]), "minutes": float(r[2])}
                    for r in _q("creatorContentType")},
        "by_country": {r[0]: {"views": float(r[1]), "minutes": float(r[2])}
                       for r in _q("country")},
    }


# --------------------------------------------------------------------------
# 混ざり方と実効 RPM
# --------------------------------------------------------------------------
def minutes_by_form(by_form: dict[str, dict]) -> dict[str, float]:
    """`creatorContentType` の行を、こちらの形の呼び名でまとめる。"""
    out: dict[str, float] = {}
    for key, row in (by_form or {}).items():
        name = FORM_OF.get(key, key)
        out[name] = out.get(name, 0.0) + float(row.get("minutes") or 0.0)
    return out


def views_by_form(by_form: dict[str, dict]) -> dict[str, float]:
    out: dict[str, float] = {}
    for key, row in (by_form or {}).items():
        name = FORM_OF.get(key, key)
        out[name] = out.get(name, 0.0) + float(row.get("views") or 0.0)
    return out


def jp_share(by_country: dict[str, dict]) -> float:
    """視聴分に占める JP の割合。**行が無ければ 1.0**（割り引きを勝手に掛けない）。"""
    total = sum(float(v.get("minutes") or 0.0) for v in (by_country or {}).values())
    if total <= 0:
        return 1.0
    return float((by_country.get("JP") or {}).get("minutes") or 0.0) / total


def effective_rpm(views: dict[str, float], level: str = "低",
                  bands: dict[str, int] | None = None) -> float:
    """**再生数**で重みを付けた実効 RPM。**帯そのものではありません。**

    重みが再生なのは、帯（¥20 / ¥400 …）が「1,000**再生**あたり」の数だからです。
    視聴分で重みを付けると、1再生あたりが長い長尺を実際より重く数えます。

    `level` は帯の段（低 / 中 / 高）。形の名前が帯に無ければ**0円として数えます**
    （`liveStream` などが混ざったときに、黙ってショート扱いにしないため）。
    """
    bands = bands or BANDS
    total = sum(views.values())
    if total <= 0:
        return 0.0
    acc = 0.0
    for form, v in views.items():
        key = f"{form} {level}" if form == "ショート" else f"{form} お金 {level}"
        acc += (v / total) * float(bands.get(key, 0))
    return acc


def long_minutes_per_view(by_form: dict[str, dict]) -> float:
    """長尺の1再生あたり視聴分。**行が無ければ 0**（推測を混ぜない）。"""
    for key, row in (by_form or {}).items():
        if FORM_OF.get(key) == "長尺":
            v = float(row.get("views") or 0.0)
            if v > 0:
                return float(row.get("minutes") or 0.0) / v
    return 0.0


def surface_ceiling(mix: dict, reach: dict, level: str = "高",
                    bands: dict[str, int] | None = None) -> dict:
    """**サムネを見せられている面から、実効 RPM の天井を出す。**

    `reach` は `src.reach_split.summary()` の返り（形べつのインプレッションと日数）。
    面が測れていなければ `factor=None` を返します —— **測れないときに
    据え置きの ×100 へ黙って戻らないため**、呼ぶ側で分かるようにしています。
    """
    bands = bands or BANDS
    views = views_by_form(mix.get("by_form") or {})
    mins = minutes_by_form(mix.get("by_form") or {})
    days = max(1.0, float(mix.get("days") or 1))
    short_views_day = views.get("ショート", 0.0) / days

    long_row = (reach or {}).get("長尺") or {}
    reach_days = max(1.0, float((reach or {}).get("days") or 1))
    # 全期間の1日あたりで取ります（直近7日ではなく）。**天井は上振れ側で読むこと** ——
    # 面が細っている7日で天井を作ると、「もう届かない」を面のゆらぎで作ってしまいます。
    imp_day = float(long_row.get("impressions") or 0.0) / reach_days

    now = effective_rpm(views, "低", bands)
    if imp_day <= 0 or now <= 0:
        return {"factor": None, "rpm_now": now, "rpm_max": None,
                "long_share_max": None, "imp_day": imp_day,
                "why": "長尺の面（インプレッション）が測れていません"}

    long_views_day_max = imp_day                    # CTR 100% の上限
    denom = long_views_day_max + short_views_day
    share_max = (long_views_day_max / denom) if denom > 0 else 0.0
    rpm_max = (share_max * float(bands[f"長尺 お金 {level}"])
               + (1 - share_max) * float(bands[f"ショート {level}"]))
    total_views = sum(views.values())
    return {
        "factor": rpm_max / now,
        "rpm_now": now,
        "rpm_max": rpm_max,
        "long_share_max": share_max,
        "long_share_now": (views.get("長尺", 0.0) / total_views) if total_views else 0.0,
        "imp_day": imp_day,
        "short_views_day": short_views_day,
        # 診断だけ（重みには使いません。使うと長尺を実際より重く数えます）
        "long_minutes_per_view": long_minutes_per_view(mix.get("by_form") or {}),
        "long_minutes_share_now": (mins.get("長尺", 0.0) / sum(mins.values())) if sum(mins.values()) else 0.0,
        "why": (f"長尺の面 {imp_day:,.1f}回/日 × CTR100% ＝ 再生の {share_max * 100:.1f}% が上限 "
                f"→ 実効RPM ¥{rpm_max:,.0f}"),
    }


# --------------------------------------------------------------------------
# 積む・読む（`eta.py` は `--offline` でも動くので、最後の点をファイルから読みます）
# --------------------------------------------------------------------------
def record(mix: dict, ceiling: dict, path: Path | None = None) -> dict:
    p = path or LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "at": date.today().isoformat(),
        # **重みが何か**を必ず残す。最初の版は視聴分で重みを付けていて（天井 ×41.5）、
        # 単位が合っていませんでした。欄が無いと、次に読む側が区別できません。
        "weight": "views",
        "window": {"start": mix.get("start"), "end": mix.get("end"), "days": mix.get("days")},
        "minutes_by_form": minutes_by_form(mix.get("by_form") or {}),
        "views_by_form": views_by_form(mix.get("by_form") or {}),
        "jp_share": jp_share(mix.get("by_country") or {}),
        "rpm_now": ceiling.get("rpm_now"),
        "rpm_max": ceiling.get("rpm_max"),
        "factor": ceiling.get("factor"),
        "long_share_now": ceiling.get("long_share_now"),
        "long_share_max": ceiling.get("long_share_max"),
        "imp_day": ceiling.get("imp_day"),
        "why": ceiling.get("why"),
    }
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def last(path: Path | None = None) -> dict | None:
    """最後に積んだ実測。**無ければ None**（呼ぶ側が「測っていない」と言えるように）。"""
    p = path or LOG
    if not p.exists():
        return None
    lines = [x for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
    if not lines:
        return None
    try:
        return json.loads(lines[-1])
    except json.JSONDecodeError:
        return None


def render(rec: dict | None) -> str:
    if not rec:
        return ("=== RPM の帯（実測の混ざり方）===\n"
                "  **まだ一度も測っていません。** `python -m src.rpm_mix --record`\n")
    mins = rec.get("minutes_by_form") or {}
    total = sum(mins.values()) or 1.0
    lines = ["=== RPM の帯（実測の混ざり方・`creatorContentType`）==="]
    lines.append(f"  窓 {rec.get('window', {}).get('start')}〜{rec.get('window', {}).get('end')}"
                 f"（{rec.get('window', {}).get('days')}日）／ JP の視聴分 {rec.get('jp_share', 1.0) * 100:.1f}%")
    for form, m in sorted(mins.items(), key=lambda kv: -kv[1]):
        v = (rec.get("views_by_form") or {}).get(form, 0)
        lines.append(f"    {form:<6} 視聴分 {m:>10,.0f}（{m / total * 100:5.2f}%）／ 再生 {v:>10,.0f}")
    if rec.get("rpm_now") is not None:
        lines.append(f"  **いまの実効 RPM: ¥{rec['rpm_now']:,.1f}**"
                     f"（帯の決め打ち `ショート 低` ¥{BANDS['ショート 低']} と比べること）")
    if rec.get("factor"):
        lines.append(f"  **天井（実測）: ¥{rec['rpm_max']:,.0f} ＝ ×{rec['factor']:,.1f}**  {rec.get('why', '')}")
        lines.append("      ↑ **据え置きの ×100（¥2,000 ÷ ¥20）は、混ざり方を無視した線でした。**")
        lines.append("      長尺を出せば面が増え、次の回の測り直しでこの天井は上がります。")
    else:
        lines.append(f"  天井: **測れていません** —— {rec.get('why', '')}")
    if rec.get("jp_share", 1.0) < JP_SHARE_FLOOR:
        lines.append(f"  [!] JP の視聴分が {rec['jp_share'] * 100:.1f}% ＝ **帯そのものを見直すこと**"
                     f"（この表は日本のお金の帯です）")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="RPM の帯を、実測の混ざり方から出す")
    ap.add_argument("--record", action="store_true", help="測って data/rpm_mix.jsonl に積む")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--show", action="store_true", help="最後に積んだ点を出すだけ（API を叩かない）")
    args = ap.parse_args(argv)

    if args.show or not args.record:
        print(render(last()))
        return 0

    from . import reach_split

    mix = fetch_mix(args.days)
    rows = reach_split.dedupe(reach_split.load_rows())
    reach = reach_split.summary(rows, reach_split.long_ids())
    ceiling = surface_ceiling(mix, reach)
    rec = record(mix, ceiling)
    print(render(rec))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
