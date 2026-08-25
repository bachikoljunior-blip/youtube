"""**ショートは登録者を連れてくるのか**を、実データで答える（2026-08-25）。

    python scripts/shorts_subs.py                 # 全期間。既定
    python scripts/shorts_subs.py --since 2026-08-01
    python scripts/shorts_subs.py --min-age-days 7   # 熟した本だけで率を出し直す

## 何を測るか

**登録者は「1000人の門」、視聴時間は「4000時間の門」。別の門です。**
どちらが詰まっているかで引く腕が変わるので、**形（ショート／長尺）で割って**、
両方を同じ窓で出します。

## 計器が測りたいものを測っているか（**書く前にここを読むこと**）

この repo はこの日、同じ欠陥を6件出しています —— 「計器が測りたいものを測っていない」。
ここで開きうる穴は4つあり、**全部ふさいであります**:

1. **形の決め方**。題名の `#Shorts` で分けない（付け忘れ・付け間違いが実在する。
   `src/forms.py` 参照）。**YouTube 自身が返す `creatorContentType` で分けます**
   （`filters=creatorContentType==shorts` / `==videoOnDemand`）。
   **札ではなく、向こうが数えた形です。**

2. **分母と分子の出どころを揃える**。`subscribersGained` と `views` を
   **同じ1回の問い合わせ**から取ります。別々の窓から取ると、片方だけ新しくなります。

3. **公開直後の本**。Analytics は**日次で3日遅れ**なので、今日出した本は
   分子にも分母にも1つも入りません（＝率は下がりも上がりもしない）。
   それでも「露出の日数が足りない本」は混ざるので、`--min-age-days` で
   **熟した本だけの率**も同時に出し、両方を並べます。**片方だけ見ないこと。**

4. **動画に紐づかない登録**。チャンネルページや検索から登録した人は、
   `creatorContentType` が `creatorContentTypeUnspecified` の行に落ちます。
   **これを動画の率に混ぜません。**別の行として出します。

## 取れないもの（**推測で埋めないこと**）

- **流入経路べつの登録者は取れません。** `dimensions=insightTrafficSourceType` に
  `subscribersGained` を足すと **400 "The query is not supported."** が返ります
  （2026-08-25 実測）。だから「どの流入から登録したか」は**この口からは分かりません**。
  出せるのは「**どの動画から**」までです。
- **収益化の門の進捗そのもの**（公開視聴時間4000時間のうち何時間か）は、
  Analytics API に欄がありません。**ショートの分がその4000時間に入るかどうかを、
  この口では確かめられません。** ここは「入らないはず」と書かず、
  **形べつの時間を出して、判断は読む側に渡します。**

## 覆る条件

登録が2桁になったら、Poisson の幅（`--conf`）が縮んで形の差が見えるようになります。
**いまは幅のほうが差より大きい**ので、この道具は「どちらとも言えない」と言います。
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

JST = timezone(timedelta(hours=9))

OUT_JSON = ROOT / "data" / "shorts_subs.json"
OUT_LOG = ROOT / "data" / "shorts_subs.jsonl"
UPLOADED = ROOT / "data" / "uploaded.jsonl"
VIEWS = ROOT / "data" / "views.jsonl"

#: `creatorContentType` の値 → こちらの呼び名。`src/rpm_mix.FORM_OF` と同じ。
FORM_OF = {"shorts": "ショート", "videoOnDemand": "長尺",
           "creatorContentTypeUnspecified": "動画に紐づかない"}

METRICS = ("views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,"
           "likes,subscribersGained,subscribersLost")

#: 収益化の門
SUB_DOOR = 1000
HOUR_DOOR = 4000
#: もう1つの道（ショート 90日で1000万再生）。**この条件自体は API から読めません。**
SHORTS_DOOR_90D = 10_000_000


# --------------------------------------------------------------------------
# 数の道具（**API を叩かない。ここだけ検査できる**）
# --------------------------------------------------------------------------
def per_1000(events: float, views: float) -> float | None:
    """再生1000回あたりの件数。**分母が0なら None**（0で割って0と言わない）。"""
    if not views:
        return None
    return events / views * 1000.0


def _poisson_cdf(k: int, lam: float) -> float:
    if lam <= 0:
        return 1.0
    total, term = 0.0, math.exp(-lam)
    for i in range(0, k + 1):
        if i:
            term *= lam / i
        total += term
    return min(total, 1.0)


def poisson_ci(n: int, conf: float = 0.95) -> tuple[float, float]:
    """観測 `n` 件のときの、真の平均件数の区間（Garwood の厳密区間を二分法で）。

    **登録が1桁のうちは、この幅が結論そのものです。**
    「ショートのほうが低い」と言えるかは、幅が重ならないかで決まります。
    """
    alpha = 1.0 - conf
    if n < 0:
        raise ValueError("n は0以上")

    def solve(target: float, k: int, lo: float, hi: float) -> float:
        # CDF(k; lam) は lam について単調減少
        for _ in range(200):
            mid = (lo + hi) / 2.0
            if _poisson_cdf(k, mid) > target:
                lo = mid
            else:
                hi = mid
        return (lo + hi) / 2.0

    hi_guess = max(10.0, n * 4.0 + 20.0)
    upper = solve(alpha / 2.0, n, 0.0, hi_guess)
    lower = 0.0 if n == 0 else solve(1.0 - alpha / 2.0, n - 1, 0.0, hi_guess)
    return lower, upper


def rate_ci_per_1000(events: int, views: float, conf: float = 0.95) -> tuple[float, float] | None:
    """率（/1000再生）の区間。**分母が0なら None。**"""
    if not views:
        return None
    lo, hi = poisson_ci(events, conf)
    return lo / views * 1000.0, hi / views * 1000.0


def overlap(a: tuple[float, float] | None, b: tuple[float, float] | None) -> bool:
    """2つの区間が重なるか。**重なっていたら「差がある」と言わないこと。**"""
    if a is None or b is None:
        return True
    return a[0] <= b[1] and b[0] <= a[1]


def views_for_subs(remaining: int, rate_per_1000: float | None) -> float | None:
    """あと `remaining` 人を、いまの率で連れてくるのに要る再生数。"""
    if not rate_per_1000:
        return None
    return remaining / rate_per_1000 * 1000.0


# --------------------------------------------------------------------------
# 公開時刻（**API を叩かない。手元の控えだけ**）
# --------------------------------------------------------------------------
def published_at() -> dict[str, datetime]:
    """動画ID → 公開時刻（UTC）。

    2つの控えを合わせます。**どちらも欠けます**:

        data/uploaded.jsonl   8/16 以降しか無い（`at` が予約時刻＝公開時刻）
        data/views.jsonl      8/04 から全部ある（`at - hours` で復元できる）

    **片方だけ見ると、古い本が丸ごと落ちます**（`scripts/per_day_views.py` と同じ罠）。
    """
    out: dict[str, datetime] = {}

    if VIEWS.exists():
        for line in VIEWS.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
                at = datetime.fromisoformat(str(row["at"]).replace("Z", "+00:00"))
                born = at - timedelta(hours=float(row["hours"]))
            except (json.JSONDecodeError, KeyError, ValueError, TypeError):
                continue
            vid = str(row.get("id") or "")
            if vid and (vid not in out or born < out[vid]):
                out[vid] = born

    if UPLOADED.exists():
        for line in UPLOADED.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = str(row.get("video_id") or "")
            raw = row.get("at") or row.get("uploaded_at")
            if not vid or not isinstance(raw, str) or not raw:
                continue
            try:
                born = datetime.fromisoformat(raw.replace("Z", "+00:00"))
            except ValueError:
                continue
            # 予約時刻（`at`）のほうが「公開時刻」として正しい。控えを優先する
            if row.get("at"):
                out[vid] = born
            elif vid not in out:
                out[vid] = born

    return out


def titles() -> dict[str, str]:
    """動画ID → 題名（**手元の控えだけ。Data API を叩かない**）。"""
    out: dict[str, str] = {}
    if not UPLOADED.exists():
        return out
    for line in UPLOADED.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        vid, title = str(row.get("video_id") or ""), str(row.get("title") or "")
        if vid and title:
            out[vid] = title
    return out


# --------------------------------------------------------------------------
# Analytics（**Data API とは別枠**。ここは5回だけ叩く）
# --------------------------------------------------------------------------
def _client():
    from googleapiclient.discovery import build

    from src.auth import credentials
    return build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)


def _query(an, start: str, end: str, **kw) -> tuple[list[dict], str | None]:
    """`(行, 落ちた理由)`。**落ちても回は止めません**（何が取れなかったかを残す）。"""
    try:
        res = an.reports().query(ids="channel==MINE", startDate=start, endDate=end, **kw).execute()
    except Exception as exc:                                    # noqa: BLE001
        return [], f"{type(exc).__name__}: {str(exc)[:180]}"
    headers = [h["name"] for h in res.get("columnHeaders", [])]
    return [dict(zip(headers, row)) for row in res.get("rows", []) or []], None


def collect(start: str, end: str, with_channel: bool = True) -> dict:
    an = _client()
    out: dict = {"window": {"start": start, "end": end}, "errors": {}}

    agg, err = _query(an, start, end, metrics=METRICS, dimensions="creatorContentType")
    if err:
        out["errors"]["creatorContentType"] = err
    out["by_form"] = agg

    for raw in ("shorts", "videoOnDemand"):
        rows, err = _query(an, start, end, metrics=METRICS, dimensions="video",
                           filters=f"creatorContentType=={raw}", sort="-views", maxResults=200)
        if err:
            out["errors"][f"video/{raw}"] = err
        out.setdefault("videos", {})[raw] = rows

    days, err = _query(an, start, end, metrics="views,estimatedMinutesWatched,"
                                              "subscribersGained,subscribersLost",
                       dimensions="day", sort="day")
    if err:
        out["errors"]["day"] = err
    out["days"] = days

    # **形べつの「1日あたり」**。門までの日数は、総量ではなく速さで決まります。
    day_form, err = _query(an, start, end, metrics="views,estimatedMinutesWatched",
                           dimensions="day,creatorContentType", sort="day", maxResults=200)
    if err:
        out["errors"]["day+creatorContentType"] = err
    out["days_by_form"] = day_form

    traffic, err = _query(an, start, end, metrics="views,estimatedMinutesWatched",
                          dimensions="insightTrafficSourceType", sort="-views")
    if err:
        out["errors"]["insightTrafficSourceType"] = err
    out["traffic"] = traffic

    # **取れないことを、取れないと記録する**（次の回が同じ問いをもう一度撃たないため）
    _, err = _query(an, start, end, metrics="subscribersGained",
                    dimensions="insightTrafficSourceType")
    out["traffic_subs_supported"] = err is None
    if err:
        out["errors"]["insightTrafficSourceType+subscribersGained"] = err

    if with_channel:
        out["channel_now"] = channel_now()

    return out


def channel_now() -> dict:
    """いまの登録者数と総再生（**Data API・1単位**）。

    **突き合わせのためだけに叩きます。** Analytics の純増は日次で3日遅れなので、
    **この2つは必ずずれます。** ずれ幅そのものが「遅れ何日ぶんか」の目盛りです。
    枠（403）で取れなくても回は止めません。
    """
    try:
        from googleapiclient.discovery import build

        from src.auth import credentials, note_day_quota
    except Exception as exc:                                    # noqa: BLE001
        return {"error": f"{type(exc).__name__}: {exc}"}
    try:
        yt = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
        res = yt.channels().list(part="statistics", mine=True).execute()
        st = (res.get("items") or [{}])[0].get("statistics", {})
        return {"subscribers": int(st.get("subscriberCount", 0)),
                "views": int(st.get("viewCount", 0)),
                "videos": int(st.get("videoCount", 0))}
    except Exception as exc:                                    # noqa: BLE001
        try:
            note_day_quota(exc, detail="shorts_subs.channel_now")
        except Exception:                                       # noqa: BLE001
            pass
        return {"error": f"{type(exc).__name__}: {str(exc)[:160]}"}


# --------------------------------------------------------------------------
# まとめ
# --------------------------------------------------------------------------
def summarize(raw: dict, min_age_days: int, conf: float, today: date) -> dict:
    born = published_at()
    name = titles()

    forms: dict[str, dict] = {}
    for row in raw.get("by_form", []):
        key = FORM_OF.get(row.get("creatorContentType", ""), row.get("creatorContentType", "?"))
        forms[key] = {
            "views": float(row.get("views") or 0),
            "minutes": float(row.get("estimatedMinutesWatched") or 0),
            "avg_view_seconds": float(row.get("averageViewDuration") or 0),
            "avg_view_percent": float(row.get("averageViewPercentage") or 0),
            "likes": float(row.get("likes") or 0),
            "subs_gained": int(row.get("subscribersGained") or 0),
            "subs_lost": int(row.get("subscribersLost") or 0),
        }
        f = forms[key]
        f["subs_net"] = f["subs_gained"] - f["subs_lost"]
        f["subs_per_1000"] = per_1000(f["subs_gained"], f["views"])
        f["likes_per_1000"] = per_1000(f["likes"], f["views"])
        f["ci_per_1000"] = rate_ci_per_1000(f["subs_gained"], f["views"], conf)
        f["hours"] = f["minutes"] / 60.0

    videos: list[dict] = []
    for raw_form, rows in (raw.get("videos") or {}).items():
        for row in rows:
            vid = str(row.get("video") or "")
            b = born.get(vid)
            age = (today - b.date()).days if b else None
            videos.append({
                "id": vid,
                "form": FORM_OF.get(raw_form, raw_form),
                "title": name.get(vid, ""),
                "published": b.astimezone(JST).isoformat() if b else None,
                "age_days": age,
                "views": float(row.get("views") or 0),
                "minutes": float(row.get("estimatedMinutesWatched") or 0),
                "avg_view_seconds": float(row.get("averageViewDuration") or 0),
                "likes": float(row.get("likes") or 0),
                "subs_gained": int(row.get("subscribersGained") or 0),
                "subs_lost": int(row.get("subscribersLost") or 0),
            })
    videos.sort(key=lambda v: (-v["subs_gained"], -v["views"]))

    def cohort(rows: list[dict], form: str, mature_only: bool) -> dict:
        sel = [v for v in rows if v["form"] == form]
        if mature_only:
            sel = [v for v in sel if v["age_days"] is not None and v["age_days"] >= min_age_days]
        views = sum(v["views"] for v in sel)
        subs = sum(v["subs_gained"] for v in sel)
        return {
            "videos": len(sel),
            "views": views,
            "minutes": sum(v["minutes"] for v in sel),
            "likes": sum(v["likes"] for v in sel),
            "subs_gained": subs,
            "with_subs": sum(1 for v in sel if v["subs_gained"] > 0),
            "subs_per_1000": per_1000(subs, views),
            "ci_per_1000": rate_ci_per_1000(subs, views, conf),
            "unknown_age": sum(1 for v in sel if v["age_days"] is None),
        }

    cohorts = {
        form: {"all": cohort(videos, form, False), "mature": cohort(videos, form, True)}
        for form in ("ショート", "長尺")
    }

    # **ショートの中で、何が登録に効いているか**を探す。
    # 「見られてはいるが登録する理由が無い」が本当なら、**維持の高い本ほど登録が付く**はず。
    # **区間が重なれば「効いている」と言えません。**
    def split(rows: list[dict], key: str) -> dict:
        vals = sorted(r[key] for r in rows)
        if not vals:
            return {}
        mid = vals[len(vals) // 2]
        out = {}
        for label, sel in (("上半分", [r for r in rows if r[key] >= mid]),
                           ("下半分", [r for r in rows if r[key] < mid])):
            views = sum(r["views"] for r in sel)
            subs = sum(r["subs_gained"] for r in sel)
            out[label] = {"videos": len(sel), "views": views, "subs_gained": subs,
                          "subs_per_1000": per_1000(subs, views),
                          "ci_per_1000": rate_ci_per_1000(subs, views, conf)}
        out["median"] = mid
        return out

    live_shorts = [v for v in videos if v["form"] == "ショート" and v["views"] > 0]
    splits = {
        "平均視聴秒": split(live_shorts, "avg_view_seconds"),
        "再生数": split(live_shorts, "views"),
    }
    like_views = sum(v["views"] for v in live_shorts)
    splits["高評価"] = {
        "likes": sum(v["likes"] for v in live_shorts),
        "per_1000": per_1000(sum(v["likes"] for v in live_shorts), like_views),
        "zero_like_videos": sum(1 for v in live_shorts if v["likes"] == 0),
        "videos": len(live_shorts),
    }

    # **計器の健全性**。ここが黙ると、上の率がどれだけずれているか分からなくなります。
    #  - 本べつの合計と、形べつの合計は**一致しません**（消した動画は本べつから落ちる）
    #  - 題名の `#Shorts` と、YouTube が数えた形の**食い違い**の実数
    tagged_wrong = [v for v in videos
                    if ("#Shorts" in (v["title"] or "")) != (v["form"] == "ショート")
                    and v["title"]]
    health = {
        "views_by_form_total": sum(f["views"] for f in forms.values()),
        "views_by_video_total": sum(v["views"] for v in videos),
        "videos_listed": len(videos),
        "videos_without_publish_time": sum(1 for v in videos if v["age_days"] is None),
        "title_tag_mismatch": [{"id": v["id"], "form": v["form"], "title": v["title"]}
                               for v in tagged_wrong],
    }
    health["views_gap"] = health["views_by_form_total"] - health["views_by_video_total"]

    days = raw.get("days", [])
    with_data = [d for d in days if float(d.get("views") or 0) > 0]
    data_end = with_data[-1]["day"] if with_data else None
    recent = with_data[-7:]
    views_per_day = (sum(float(d["views"]) for d in recent) / len(recent)) if recent else 0.0

    # 形べつの「1日あたりの視聴分」（直近7日／**日次が届いている日だけ**）
    recent_days = {d["day"] for d in recent}
    per_day_minutes: dict[str, float] = {}
    for row in raw.get("days_by_form", []):
        if row.get("day") not in recent_days:
            continue
        key = FORM_OF.get(row.get("creatorContentType", ""), row.get("creatorContentType", "?"))
        per_day_minutes[key] = per_day_minutes.get(key, 0.0) + float(
            row.get("estimatedMinutesWatched") or 0)
    n = max(len(recent), 1)
    per_day_minutes = {k: v / n for k, v in per_day_minutes.items()}

    short = forms.get("ショート", {})
    rate = short.get("subs_per_1000")
    ci = short.get("ci_per_1000")
    subs_net_total = sum(f["subs_net"] for f in forms.values())
    remaining = SUB_DOOR - subs_net_total
    need_views = views_for_subs(remaining, rate)
    need_views_slow = views_for_subs(remaining, ci[0]) if ci else None
    need_views_fast = views_for_subs(remaining, ci[1]) if ci else None

    door = {
        "subs_net_measured": subs_net_total,
        "remaining_to_1000": remaining,
        "views_needed_at_measured_rate": need_views,
        "views_needed_ci": [need_views_fast, need_views_slow],
        "views_per_day_recent7": views_per_day,
        "days_at_current_pace": (need_views / views_per_day) if (need_views and views_per_day) else None,
        "hours_shorts": forms.get("ショート", {}).get("hours"),
        "hours_long": forms.get("長尺", {}).get("hours"),
        "hour_door": HOUR_DOOR,
        "minutes_per_day_recent7": per_day_minutes,
    }
    for label, key in (("if_shorts_count", "ショート"), ("if_only_long", "長尺")):
        mins = per_day_minutes.get(key, 0.0)
        if label == "if_shorts_count":
            mins += per_day_minutes.get("長尺", 0.0)
            have = (door["hours_shorts"] or 0) + (door["hours_long"] or 0)
        else:
            have = door["hours_long"] or 0
        left = max(HOUR_DOOR - have, 0) * 60.0
        door[f"days_to_4000h_{label}"] = (left / mins) if mins else None

    # **もう1つの道**（ショート 90日で1000万再生）。**制度の条件は API から読めません** ——
    # ここで出すのは「**いまの速さの何倍か**」だけで、条件そのものは実測ではありません。
    door["shorts_views_90d_at_current_pace"] = views_per_day * 90
    door["shorts_10m_multiple"] = (SHORTS_DOOR_90D / (views_per_day * 90)) if views_per_day else None
    door["shorts_10m_views_per_day_needed"] = SHORTS_DOOR_90D / 90.0

    now = raw.get("channel_now") or {}
    reconcile = None
    if now.get("subscribers") is not None:
        reconcile = {
            "subscribers_now": now["subscribers"],
            "subs_net_in_analytics": subs_net_total,
            "gap": now["subscribers"] - subs_net_total,
            "views_now": now.get("views"),
            "views_in_analytics": sum(f["views"] for f in forms.values()),
            "note": "Analytics は日次で3日遅れ。ずれは「まだ届いていない日」の分",
        }

    return {
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "window": raw.get("window"),
        "channel_now": now,
        "reconcile": reconcile,
        "data_end": data_end,
        "min_age_days": min_age_days,
        "conf": conf,
        "forms": forms,
        "cohorts": cohorts,
        "videos": videos,
        "splits": splits,
        "health": health,
        "traffic": raw.get("traffic", []),
        "traffic_subs_supported": raw.get("traffic_subs_supported"),
        "door": door,
        "errors": raw.get("errors", {}),
    }


# --------------------------------------------------------------------------
# 表示
# --------------------------------------------------------------------------
def _fmt(x, digits=2, dash="—"):
    if x is None:
        return dash
    if isinstance(x, float):
        return f"{x:,.{digits}f}"
    return f"{x:,}"


def render(s: dict) -> str:
    L: list[str] = []
    w = s["window"]
    L.append(f"### ショートは登録者を連れてくるのか（窓 {w['start']} 〜 {w['end']}／"
             f"日次が届いている最終日 **{s['data_end'] or '不明'}**）")
    L.append("")

    r = s.get("reconcile")
    if r:
        L.append(f"いまのチャンネル: 登録 **{r['subscribers_now']}人** / 総再生 "
                 f"{_fmt(r.get('views_now'),0)}回  ——  Analytics の純増 "
                 f"{r['subs_net_in_analytics']}人（差 {r['gap']:+}人 ＝ まだ届いていない日の分）")
        L.append("")

    L.append("## 1. 形べつ（`creatorContentType`。**題名の札ではなく YouTube が数えた形**）")
    L.append("")
    L.append(f"{'形':<14}{'再生':>10}{'視聴分':>10}{'平均秒':>8}"
             f"{'登録+':>7}{'登録-':>7}{'高評価':>8}{'登録/千再生':>13}  95%区間")
    for key in ("ショート", "長尺", "動画に紐づかない"):
        f = s["forms"].get(key)
        if not f:
            continue
        ci = f.get("ci_per_1000")
        ci_txt = f"[{_fmt(ci[0],3)} 〜 {_fmt(ci[1],3)}]" if ci else "—（分母0）"
        L.append(f"{key:<14}{_fmt(f['views'],0):>10}{_fmt(f['minutes'],0):>10}"
                 f"{_fmt(f['avg_view_seconds'],0):>8}{f['subs_gained']:>7}{f['subs_lost']:>7}"
                 f"{_fmt(f['likes'],0):>8}{_fmt(f['subs_per_1000'],3):>13}  {ci_txt}")
    L.append("")

    sh = s["forms"].get("ショート", {})
    lo = s["forms"].get("長尺", {})
    if sh and lo:
        if overlap(sh.get("ci_per_1000"), lo.get("ci_per_1000")):
            L.append("→ **2つの区間が重なっています。この実測では「どちらの率が高い」と言えません。**")
        else:
            higher = "長尺" if (lo.get("subs_per_1000") or 0) > (sh.get("subs_per_1000") or 0) else "ショート"
            L.append(f"→ 区間が重なりません。**{higher} のほうが登録率が高い**と言えます。")
        L.append(f"   （長尺の分母は **{_fmt(lo.get('views'),0)}再生** です。"
                 "**ここが小さいうちは、率の比較そのものが成り立ちません。**）")
    L.append("")

    L.append(f"## 2. 本べつ（**{s['min_age_days']}日以上たった本だけ**の率も並べる）")
    L.append("")
    for form, c in s["cohorts"].items():
        for label, key in (("全部", "all"), (f"{s['min_age_days']}日以上", "mature")):
            d = c[key]
            ci = d["ci_per_1000"]
            ci_txt = f"[{_fmt(ci[0],3)} 〜 {_fmt(ci[1],3)}]" if ci else "—"
            L.append(f"{form:<6}{label:<10} {d['videos']:>3}本  再生 {_fmt(d['views'],0):>8}  "
                     f"登録 {d['subs_gained']:>3}（{d['with_subs']}本が1人以上）  "
                     f"登録/千再生 {_fmt(d['subs_per_1000'],3):>7}  {ci_txt}")
    L.append("")

    sp = s.get("splits") or {}
    if sp:
        L.append("## 2b. ショートの中で、何が登録を分けているか（**区間が重なれば「効いていない」**）")
        L.append("")
        for key in ("平均視聴秒", "再生数"):
            d = sp.get(key) or {}
            if not d:
                continue
            L.append(f"  {key}（中央値 {_fmt(d.get('median'),0)}）で2つに割る")
            for label in ("上半分", "下半分"):
                v = d.get(label)
                if not v:
                    continue
                ci = v["ci_per_1000"]
                ci_txt = f"[{_fmt(ci[0],3)} 〜 {_fmt(ci[1],3)}]" if ci else "—"
                L.append(f"    {label}  {v['videos']:>3}本  再生 {_fmt(v['views'],0):>8}  "
                         f"登録 {v['subs_gained']:>3}  率 {_fmt(v['subs_per_1000'],3):>7}  {ci_txt}")
            if overlap((d.get("上半分") or {}).get("ci_per_1000"),
                       (d.get("下半分") or {}).get("ci_per_1000")):
                L.append("    → **重なっています。この切り口では説明できません。**")
            else:
                L.append("    → **重なりません。この切り口は効いています。**")
        lk = sp.get("高評価") or {}
        if lk:
            L.append(f"  高評価: {_fmt(lk.get('likes'),0)}件（{_fmt(lk.get('per_1000'),2)}/千再生）。"
                     f"**{lk.get('zero_like_videos')} / {lk.get('videos')} 本が0件**")
        L.append("")

    L.append("## 3. 登録の出どころ（**動画べつ。流入べつは取れません**）")
    L.append("")
    got = [v for v in s["videos"] if v["subs_gained"] > 0]
    for v in got:
        L.append(f"  {v['subs_gained']}人  {v['form']}  {v['id']}  "
                 f"再生 {_fmt(v['views'],0):>6}  平均 {_fmt(v['avg_view_seconds'],0)}秒  "
                 f"{(v['title'] or '')[:34]}")
    if not got:
        L.append("  （この窓では0件）")
    unattr = s["forms"].get("動画に紐づかない")
    if unattr:
        L.append(f"  **動画に紐づかない: +{unattr['subs_gained']} / -{unattr['subs_lost']}**"
                 "（チャンネルページ・検索など。**動画の率には混ぜていません**）")
    if not s.get("traffic_subs_supported"):
        L.append("  **流入経路べつの登録者は、この API では取れません**"
                 "（`insightTrafficSourceType` × `subscribersGained` は 400）。")
    L.append("")
    L.append("  参考：流入経路べつの**再生**（登録ではない）")
    for t in s["traffic"][:6]:
        L.append(f"    {t.get('insightTrafficSourceType',''):<18}"
                 f"再生 {_fmt(t.get('views'),0):>8}  視聴分 {_fmt(t.get('estimatedMinutesWatched'),0):>7}")
    L.append("")

    d = s["door"]
    L.append("## 4. 2つの門")
    L.append("")
    L.append(f"  登録 {SUB_DOOR}人 —— 実測の純増 **{d['subs_net_measured']}人**／"
             f"あと {d['remaining_to_1000']}人")
    L.append(f"    いまのショートの率（{_fmt(s['forms'].get('ショート',{}).get('subs_per_1000'),3)}/千再生）だと "
             f"**{_fmt(d['views_needed_at_measured_rate'],0)}再生**が要る")
    if d["views_needed_ci"][0]:
        L.append(f"    95%区間で {_fmt(d['views_needed_ci'][0],0)} 〜 {_fmt(d['views_needed_ci'][1],0)} 再生")
    if d["days_at_current_pace"]:
        L.append(f"    直近7日の速さ（{_fmt(d['views_per_day_recent7'],0)}再生/日）が続くなら "
                 f"**{_fmt(d['days_at_current_pace'],0)}日**")
    L.append("")
    L.append(f"  視聴 {HOUR_DOOR}時間 —— ショート **{_fmt(d['hours_shorts'],1)}時間**／"
             f"長尺 **{_fmt(d['hours_long'],2)}時間**")
    mpd = d.get("minutes_per_day_recent7") or {}
    L.append(f"    直近7日の視聴分/日: ショート {_fmt(mpd.get('ショート'),0)} ／ "
             f"長尺 {_fmt(mpd.get('長尺'),1)}")
    L.append("    **ショートの分がこの4000時間に入るかどうかは、この API では確かめられません**"
             "（門の進捗を返す欄がありません）。**だから両方を出します。**")
    L.append(f"      入るなら（ショート＋長尺）… あと **{_fmt(d.get('days_to_4000h_if_shorts_count'),0)}日**")
    L.append(f"      入らないなら（長尺だけ）… 到達 {_fmt((d['hours_long'] or 0) / HOUR_DOOR * 100, 4)}%、"
             f"あと **{_fmt(d.get('days_to_4000h_if_only_long'),0)}日**")
    L.append(f"    もう1つの道（ショート90日で1000万再生）… いまの速さなら90日で "
             f"{_fmt(d.get('shorts_views_90d_at_current_pace'),0)}再生。"
             f"**{_fmt(d.get('shorts_10m_multiple'),0)}倍**要る"
             f"（{_fmt(d.get('shorts_10m_views_per_day_needed'),0)}再生/日）")
    L.append("    **この2つの道の条件そのものは、API からは読めません**"
             "（公開されている制度の話で、ここでの実測ではありません）。")
    L.append("")

    h = s.get("health") or {}
    if h:
        L.append("## 5. 計器そのものの点検（**この数字がずれていたら、上は全部ずれます**）")
        L.append("")
        L.append(f"  形べつの再生の合計 {_fmt(h['views_by_form_total'],0)} ／ "
                 f"本べつの合計 {_fmt(h['views_by_video_total'],0)}  → **差 {_fmt(h['views_gap'],0)}**")
        L.append("    差は「本べつに出てこない再生」です（**消した動画の分**。"
                 "本べつの率はこの分を分母に含めていません）。")
        L.append(f"  公開時刻が分からない本: {h['videos_without_publish_time']} / {h['videos_listed']}")
        L.append(f"  **題名の `#Shorts` と、YouTube が数えた形の食い違い: {len(h['title_tag_mismatch'])}本**")
        for m in h["title_tag_mismatch"][:5]:
            L.append(f"    {m['id']}  向こうの数え方は **{m['form']}**  {m['title'][:40]}")
        L.append("    → **だからこの道具は題名で分けていません。**")
        L.append("")

    if s["errors"]:
        L.append("## 落ちた問い合わせ")
        for k, v in s["errors"].items():
            L.append(f"  {k}: {v}")
    return "\n".join(L)


def main() -> int:
    p = argparse.ArgumentParser(description="ショートと長尺で、登録率と視聴時間を分けて出す")
    p.add_argument("--since", default="2020-01-01", help="窓の開始日（既定は全期間）")
    p.add_argument("--min-age-days", type=int, default=7,
                   help="「熟した本」の下限（既定7日。Analytics の遅れは3日）")
    p.add_argument("--conf", type=float, default=0.95, help="区間の信頼度")
    p.add_argument("--no-channel", action="store_true",
                   help="Data API を1単位も使わない（登録者数の突き合わせを省く）")
    p.add_argument("--offline", action="store_true",
                   help="API を叩かず、data/shorts_subs.json を読み直して表示だけする")
    args = p.parse_args()

    today = date.today()
    if args.offline:
        if not OUT_JSON.exists():
            print("data/shorts_subs.json がありません（--offline は前回の控えを読みます）")
            return 1
        summary = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    else:
        raw = collect(args.since, today.isoformat(), with_channel=not args.no_channel)
        summary = summarize(raw, args.min_age_days, args.conf, today)
        OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
        OUT_JSON.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n",
                            encoding="utf-8")
        slim = {k: v for k, v in summary.items() if k != "videos"}
        with OUT_LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(slim, ensure_ascii=False) + "\n")

    print(render(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
