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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "data" / "rpm_mix.jsonl"
#: **YouTube 自身が「長尺／ショート」と数えた控え。**`--record` のたびに書き直します。
#: 読むのは `src/reach_split.long_ids()`（あちらは API を叩かない約束なので、
#: 測るこちらが置いていきます）。**手で書かないこと。**
FORMS = ROOT / "data" / "video_forms.json"

#: **Analytics の日次がどこまで届いているか**の点（`scripts/status.py` が積む）。
#: ここを読むのに API は要りません。**日枠が閉じている回でも読めます。**
LAG = ROOT / "data" / "analytics_lag.jsonl"

#: 公開の台帳。`at` が公開時刻（UTC）、無ければ `uploaded_at` で代える。
UPLOADED = ROOT / "data" / "uploaded.jsonl"

JST = timezone(timedelta(hours=9))

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
# **この数字が、どこまでの日を含んでいるか**（2026-08-21 に足した）
# --------------------------------------------------------------------------
# **なぜ要るか。** `fetch_mix` は窓の終わりに `date.today()` を渡し、
# 積んだ点にもそう書きます。**しかし Analytics の日次はそこまで来ていません。**
# 実測（`data/analytics_lag.jsonl`、2026-08-21 に3回）—— **最終日は 2026-08-18**。
# つまり `window.end: 2026-08-21` と書かれた点の中身は **08/18 まで**です。
#
# これが何を壊したか。「長尺を出して測り直す」という申し送りが
# **6回続けて次の回へ持ち越されました**（08/21 05:1x／06:2x／07:1x／08:3x／
# 11:1x／13:1x）。撃った回は毎回この道具を叩き、**同じ11再生**を読み、
# 「長尺は伸びない」と受け取っています。**新しく出した本は、まだ1本も
# この数字に入っていません。** 道具は入っていないことを一言も言いませんでした。
#
# **窓の終わりを実データの最終日に合わせ、入っていない公開を数えて、
# いつ読めるかを同じ画面に出します。**「届きません」ではなく
# 「**この日になれば読めます**」と言えるようにするのが目的です。
def data_last_day(path: Path | None = None) -> str | None:
    """Analytics の日次が**届いている最終日**。**API を叩きません。**

    無ければ `None`（呼ぶ側が「分からない」と言えるように。
    **今日で埋めないこと** —— それがこの欠陥そのものです）。
    """
    p = path or LAG
    if not p.exists():
        return None
    days = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line).get("last_day")
        except json.JSONDecodeError:
            continue
        if isinstance(d, str) and d:
            days.append(d)
    return max(days) if days else None


def _published_at(row: dict) -> datetime | None:
    """公開時刻。`at`（予約時刻）が正本で、無ければ `uploaded_at`。"""
    raw = row.get("at") or row.get("uploaded_at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None


def pending_after(last_day: str | None, *, now: datetime | None = None,
                  uploaded_path: Path | None = None,
                  long_ids: set[str] | None = None) -> dict[str, Any]:
    """**その最終日より後に公開され、まだこの数字に入っていない本。**

    `readable_on` は「いちばん新しい公開日 ＋ いま見えている遅れ」です。
    **遅れは帳面から測ります**（`today - last_day`）。定数で書くと、
    向こうが速くなった／遅くなったときに黙って外れます。
    """
    empty = {"total": 0, "long": 0, "first": None, "last": None, "readable_on": None,
             "lag_days": None}
    if not last_day:
        return empty
    now = now or datetime.now(JST)
    lag = (now.date() - date.fromisoformat(last_day)).days
    p = uploaded_path or UPLOADED
    if not p.exists():
        return {**empty, "lag_days": lag}
    cut = datetime.fromisoformat(last_day + "T23:59:59").replace(tzinfo=JST)
    longs = long_ids if long_ids is not None else set()
    hit = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        when = _published_at(row)
        if when is None or not (cut < when <= now):
            continue
        hit.append((when, row))
    if not hit:
        return {**empty, "lag_days": lag}
    hit.sort(key=lambda kv: kv[0])
    newest = hit[-1][0].astimezone(JST).date()
    return {
        "total": len(hit),
        "long": sum(1 for _, r in hit if r.get("video_id") in longs),
        "first": hit[0][0].astimezone(JST).isoformat(timespec="minutes"),
        "last": hit[-1][0].astimezone(JST).isoformat(timespec="minutes"),
        # **その本が数字に出るのは、公開日が最終日に追いついた回**です。
        "readable_on": (newest + timedelta(days=lag)).isoformat(),
        "lag_days": lag,
    }


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

    # **窓の終わりを2つ返します。**`end` は問い合わせた日、`data_end` は
    # **実際に中身がある最終日**。同じ欄に入れると、次に読む側が区別できません。
    return {
        "days": days,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "data_end": data_last_day(),
        "by_form": {r[0]: {"views": float(r[1]), "minutes": float(r[2])}
                    for r in _q("creatorContentType")},
        "by_country": {r[0]: {"views": float(r[1]), "minutes": float(r[2])}
                       for r in _q("country")},
    }


def fetch_video_forms(days: int = 90) -> dict[str, str]:
    """**動画1本ずつの形**を YouTube に聞く（`video` × `creatorContentType`）。

    返りは `{video_id: "長尺" | "ショート"}`。**失敗しても回は止めません**
    （空を返すと、控えは前のまま ＝ いままでの答えのまま）。

    Analytics を形の数だけ引きます（いまは2回）。**Data API は0単位です。**
    """
    from googleapiclient.discovery import build

    from .auth import credentials

    analytics = build("youtubeAnalytics", "v2", credentials=credentials(),
                      cache_discovery=False)
    end = date.today()
    start = end - timedelta(days=days)
    out: dict[str, str] = {}
    for raw_form, name in FORM_OF.items():
        try:
            res = analytics.reports().query(
                ids="channel==MINE",
                startDate=start.isoformat(),
                endDate=end.isoformat(),
                metrics="views",
                dimensions="video",
                filters=f"creatorContentType=={raw_form}",
                sort="-views",
                maxResults=200,
            ).execute()
        except Exception as exc:                               # noqa: BLE001
            print(f"[rpm_mix] {raw_form} の本べつが取れませんでした（続行）: "
                  f"{type(exc).__name__}: {exc}")
            continue
        for r in res.get("rows", []) or []:
            out[str(r[0])] = name
    return out


def save_video_forms(forms: dict[str, str], days: int = 90,
                     path: Path | None = None) -> dict | None:
    """控えを書き直す。**空なら書きません**（前の控えを消さないため）。

    **消さないのが要点です。** 再生が0本の長尺は Analytics が返さないので、
    空で上書きすると「長尺が1本も無い」に化けます。
    """
    if not forms:
        return None
    p = path or FORMS
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {"at": date.today().isoformat(), "window_days": days,
           "source": "youtubeAnalytics: video x creatorContentType",
           "forms": dict(sorted(forms.items()))}
    p.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n",
                 encoding="utf-8")
    return rec


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
    # **天井は「いちばん大きかった1日」で読みます**（2026-08-24 に直した）。
    #
    #     ここは 2026-08-20 から **全期間の平均**（`impressions / days`）でした。
    #     すぐ上の行に「**天井は上振れ側で読むこと**」と書いてあるのに、
    #     **中身は平均**です —— この輪で繰り返し出ている
    #     「同じことを2か所が別々に言っていて、片方しか読まれていない」の形です。
    #
    #     平均が天井にならない理由は、ゆらぎではなく**分母**でした。実測（08/24）:
    #     38日の平均 **73.0回/日** ／ 最大の1日 **1,285回**（08/21）。
    #     最初の20日は長尺の公開前で、**面そのものが存在しない日**です。
    #     存在しなかった日を分母に数えて「上限」を作っていました。
    #
    #     この 73.0 が、そのまま次へ流れていました:
    #       長尺の面 73.0回/日 → 実効RPM の天井 **¥287** → 段4 の合格点
    #       **695,675回/月** → 1日の再生の天井 6,650回 では **3.5倍 足りない**
    #       → **「月20万の到達予測: 出ません」**（軌跡・幅・据え置き線の3本とも）
    #     つまり **恒久の「届きません」は、面の平均の分母1つから出ていました。**
    #
    #     **上限の測り方は、この機械の中で既に決まっています** ——
    #     `per_video` の天井は「ショート39本の実測の**最大**」です。面だけ平均でした。
    #
    #     `per_day_max` を持たない古い呼び（検査・保存済みの点）は、
    #     **今までどおり平均に落ちます**。どちらで出したかは `imp_day_basis` に残します。
    imp_mean = float(long_row.get("impressions") or 0.0) / reach_days
    imp_max = float(long_row.get("per_day_max") or 0.0)
    if imp_max > 0:
        imp_day, imp_basis = imp_max, "最大の1日"
    else:
        imp_day, imp_basis = imp_mean, "全期間の平均"

    # **段取り（段2）が乗るのは、天井ではなく「いま続いている量」です**（2026-08-25）。
    #     ここは天井を出す関数なので `imp_day` は最大の1日のままにしますが、
    #     **同じ返りに続いている量も入れて出します。** 入れないと、呼ぶ側
    #     （`scripts/eta.py` の段2）から見える面の数が「平均」と「最大」の
    #     2つしかなく、**どちらも 450日 続けられるかの答えになりません。**
    #     実際 08/25 に、段2 は最大の1日（1,285.0）を当てて
    #     「面は足りています（6.7倍）」と印字し、同じ回の `status.py` は
    #     直近7日（190.6）から「87倍 足りません」と印字していました。
    #     **古い点は `imp_day_recent` を持ちません** —— 呼ぶ側は
    #     **平均のほう（下振れ側）へ落ちること**。最大へ落とすと、
    #     測っていない回ほど「足りている」と出ます。
    imp_recent = float(long_row.get("per_day_recent") or 0.0)
    # **その「続いている量」が、窓の中の1日で作られていないか**（2026-08-26）。
    #     `reach_split.per_day_sustained` は、1日が窓の半分以上を占めていたら
    #     中央値へ落ちます。実測 08/26: 平均 190.6（96% が 08/21 の1日）→ 中央値 8.0。
    #     **段2 の分母はこちらです。**古い呼び（保存済みの点・検査）は持たないので、
    #     その場合は今までどおり平均に落ちます。
    imp_sustained = float(long_row.get("per_day_sustained") or 0.0)
    sustained_basis = long_row.get("per_day_sustained_basis")
    now = effective_rpm(views, "低", bands)
    if imp_day <= 0 or now <= 0:
        return {"factor": None, "rpm_now": now, "rpm_max": None,
                "long_share_max": None, "imp_day": imp_day,
                "imp_day_basis": imp_basis, "imp_day_mean": imp_mean,
                "imp_day_max": imp_max or None,
                "imp_day_max_on": long_row.get("per_day_max_on"),
                "imp_day_live_days": long_row.get("live_days"),
                "imp_day_recent": imp_recent or None,
                "imp_day_recent_days": long_row.get("recent_days"),
                "imp_day_sustained": imp_sustained or None,
                "imp_day_sustained_basis": sustained_basis,
                "reach_days": reach_days,
                "reach_last_day": (reach or {}).get("last_day"),
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
        # **どちらで出した天井か**を必ず残す。残さないと、次に読む側が
        # 「平均の版か最大の版か」を区別できません（`weight` を残しているのと同じ理由）。
        "imp_day_basis": imp_basis,
        "imp_day_mean": imp_mean,
        "imp_day_max": imp_max or None,
        "imp_day_max_on": long_row.get("per_day_max_on"),
        "imp_day_live_days": long_row.get("live_days"),
        # **いま続いている量**（直近 `reach_split.RECENT_DAYS` 日の平均）。
        #     天井ではなく**段取りの分母**です。上のコメントを読むこと。
        "imp_day_recent": imp_recent or None,
        "imp_day_recent_days": long_row.get("recent_days"),
        # **1日の立ち上がりを外した「続いている量」**（2026-08-26）。段2 の分母。
        "imp_day_sustained": imp_sustained or None,
        "imp_day_sustained_basis": sustained_basis,
        "reach_days": reach_days,
        "reach_last_day": (reach or {}).get("last_day"),
        "short_views_day": short_views_day,
        # 診断だけ（重みには使いません。使うと長尺を実際より重く数えます）
        "long_minutes_per_view": long_minutes_per_view(mix.get("by_form") or {}),
        "long_minutes_share_now": (mins.get("長尺", 0.0) / sum(mins.values())) if sum(mins.values()) else 0.0,
        "why": (f"長尺の面 {imp_day:,.1f}回/日（{imp_basis}"
                + (f"・{long_row.get('per_day_max_on')}" if imp_basis == "最大の1日"
                   and long_row.get("per_day_max_on") else "")
                + f"／全期間の平均は {imp_mean:,.1f}回/日）"
                f" × CTR100% ＝ 再生の {share_max * 100:.1f}% が上限 "
                f"→ 実効RPM ¥{rpm_max:,.0f}"),
    }


# --------------------------------------------------------------------------
# 積む・読む（`eta.py` は `--offline` でも動くので、最後の点をファイルから読みます）
# --------------------------------------------------------------------------
def _long_ids() -> set[str]:
    """長尺の動画ID。**口は `reach_split.long_ids()` 1つ**。

    正本は「**測った控え（`data/video_forms.json`）∪ `config/pairs.yaml`**」です
    —— `pairs.yaml` だけを見ていた頃は、**対になっていない長尺が入りませんでした**
    （2026-08-24 の実測で 6本 対 12本）。理由は `reach_split.long_ids` の docstring。
    """
    try:
        from . import reach_split
        return reach_split.long_ids()
    except Exception:                                          # noqa: BLE001
        return set()


def record(mix: dict, ceiling: dict, path: Path | None = None) -> dict:
    p = path or LOG
    p.parent.mkdir(parents=True, exist_ok=True)
    rec = {
        "at": date.today().isoformat(),
        # **重みが何か**を必ず残す。最初の版は視聴分で重みを付けていて（天井 ×41.5）、
        # 単位が合っていませんでした。欄が無いと、次に読む側が区別できません。
        "weight": "views",
        "window": {"start": mix.get("start"), "end": mix.get("end"),
                    "days": mix.get("days"),
                    # **中身がある最終日。**`end` と食い違うのが普通です（日次は遅れる）。
                    "data_end": mix.get("data_end")},
        # **この数字に入っていない公開**。入っていないことを、点の側に残します。
        "pending": pending_after(mix.get("data_end"), long_ids=_long_ids()),
        "minutes_by_form": minutes_by_form(mix.get("by_form") or {}),
        "views_by_form": views_by_form(mix.get("by_form") or {}),
        "jp_share": jp_share(mix.get("by_country") or {}),
        "rpm_now": ceiling.get("rpm_now"),
        "rpm_max": ceiling.get("rpm_max"),
        "factor": ceiling.get("factor"),
        "long_share_now": ceiling.get("long_share_now"),
        "long_share_max": ceiling.get("long_share_max"),
        "imp_day": ceiling.get("imp_day"),
        # **天井をどちらで出したか**（2026-08-24）。平均で出した点と最大で出した点が
        # 同じ帳面に並ぶので、欄が無いと次の回が比べられません。
        "imp_day_basis": ceiling.get("imp_day_basis"),
        "imp_day_mean": ceiling.get("imp_day_mean"),
        "imp_day_max": ceiling.get("imp_day_max"),
        "imp_day_max_on": ceiling.get("imp_day_max_on"),
        "imp_day_live_days": ceiling.get("imp_day_live_days"),
        # **段取り（段2）が読む分母。** 天井（`imp_day`）とは別物なので、
        #     点の側に別の欄で残します（欄が無いと次の回が区別できません）。
        "imp_day_recent": ceiling.get("imp_day_recent"),
        "imp_day_recent_days": ceiling.get("imp_day_recent_days"),
        # **面の側の鮮度**（2026-08-24 に足した）。天井は「Analytics の混ざり方」と
        # 「Reporting の面」の**2つの実測の積**なのに、鮮度の表示は
        # **Analytics の側にしか付いていませんでした。** この回、`data/reach.jsonl`
        # が4日ぶん止まっていて、天井が ¥184 と出ました（撃ち直したら ¥287）。
        # **止まっていたことは、どこにも表示されていません。**
        "reach": {"days": ceiling.get("reach_days"),
                  "last_day": ceiling.get("reach_last_day")},
        "why": ceiling.get("why"),
    }
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def rule_capped(point: dict, per_publish: float | None,
                per_day_rule: float,
                bands: dict[str, int] | None = None) -> dict | None:
    """**その天井は、オーナーが固定した「1日1本」の下でも立つか。**（API 0単位）

    `surface_ceiling()` は長尺の面を **「いちばん大きかった1日」**で読みます。
    実測（2026-08-31）だと、その日は **20260821・長尺 1,368回/日**です。

        その日に公開した長尺は **7本**（`reach_split.publishes_per_day`）。
        オーナーが固定した規則は **1本/日**（`src/house_rule.PUBLISH_PER_DAY`）。

    **つまり `rpm` の天井は、規則の 7倍 の供給の上に立っています。**
    `scripts/eta.physical_caps` の docstring は自分の仕事をこう書いています ——
    「**腕を「実在する幅」で止める。（軌跡が実在しない世界を歩かないため）**」。
    そこは `density` を `house_rule` で止めていますが、**`rpm` は規則を
    1度も見ていませんでした。** `trajectory.py` の供給の天井（×92）・
    `physical_caps` の `density`（×10）と**同じ欠陥の3件目**です。

    ## 何で置き換えるか（**新しい推測を1つも足しません**）

    面は公開で立ちます。だから規則の下で立つ面は::

        規則の下の長尺の面/日 ＝ per_publish × PUBLISH_PER_DAY

    `per_publish` は `reach_split.summary()["長尺"]["per_publish"]`
    ＝ **直近の窓で、長尺の公開1本あたり何回サムネが見られたか**（実測）。
    **これは平均へ落とすことではありません** —— 直近の窓は
    「公開が0本の日」を分母に数えており（実測 7日中 4日）、
    公開1本あたりで読み直すと **毎日1本 出す世界**の面になります。

    ## 実測（2026-08-31・`data/reach.jsonl` 42日・**API 0単位**）

        置き方                              面/日     長尺の割合   実効RPM    倍率
        いま（最大の1日 20260821・7本公開） 1,368.0    61.5%     ¥1,252   ×59.77
        **規則 1本/日 × 公開1本あたり 320.6**  320.6    27.2%     ¥  588   **×28.05**
        （参考）その日の公開1本あたり 195.4    195.4    18.6%     ¥  420   ×20.04
        （参考）全期間の平均                 126.4    12.8%     ¥  309   ×14.76

    **×59.77 は ×28.05 の 2.13倍 甘い数でした。**
    「腕の天井を全部 同時に当てても 目標の 56.7%」も、この倍率をそのまま
    引いています（→ **26.6%**）。

    ## 覆る条件

    - **オーナーが 1日1本 を自分の言葉で外したとき**（`src/house_rule.py`)。
      `per_day_rule` が上がれば、ここは自動でゆるみます。
    - `per_publish` が測れないとき（長尺の公開が窓に0本）。そのときは
      **`None` を返します** —— 黙って元の天井へ戻さず、呼ぶ側が
      「規則で止められていない」と言えるようにするためです。
    - 規則の下の面が、いま読んでいる天井より**上**になったとき。
      そのときは止める意味がないので、そのまま `None` を返します。

    **短い側の再生（`short_views_day`）は動かしていません。** 点に欄が無いので
    保存済みの `imp_day` と `long_share_max` から復元します
    （`S = L × (1 - share) / share`）。**規則の下では、その1枠を長尺に
    使うほどショートは減ります** —— つまりここは**まだ甘い側**です。
    """
    bands = bands or BANDS
    if not point or not per_day_rule or per_day_rule <= 0:
        return None
    try:
        L = float(point.get("imp_day") or 0.0)
        share = float(point.get("long_share_max") or 0.0)
        now = float(point.get("rpm_now") or 0.0)
    except (TypeError, ValueError):
        return None
    if L <= 0 or now <= 0 or not (0.0 < share < 1.0):
        return None
    if per_publish is None or float(per_publish) <= 0:
        return None
    short_views_day = L * (1.0 - share) / share
    capped = float(per_publish) * float(per_day_rule)
    if capped >= L:
        # 規則の下の面のほうが広い ＝ 止める意味がありません。
        return None
    denom = capped + short_views_day
    share_max = (capped / denom) if denom > 0 else 0.0
    rpm_max = (share_max * float(bands["長尺 お金 高"])
               + (1.0 - share_max) * float(bands["ショート 高"]))
    return {
        "factor": rpm_max / now,
        "rpm_now": now,
        "rpm_max": rpm_max,
        "long_share_max": share_max,
        "imp_day": capped,
        "imp_day_basis": "規則 1日{:.0f}本 × 公開1本あたりの面".format(per_day_rule),
        "imp_day_before": L,
        "imp_day_before_basis": point.get("imp_day_basis"),
        "imp_day_before_on": point.get("imp_day_max_on"),
        "per_publish": float(per_publish),
        "factor_before": float(point.get("factor") or 0.0),
        "short_views_day": short_views_day,
        "why": (f"長尺の面 {capped:,.1f}回/日"
                f"（**オーナーが固定した規則 {per_day_rule:.0f}本/日**"
                f"・`src/house_rule.py` × 公開1本あたり {float(per_publish):,.1f}回・実測）"
                f" × CTR100% ＝ 再生の {share_max * 100:.1f}% が上限"
                f" → 実効RPM ¥{rpm_max:,.0f}。"
                f"**据え置きの {L:,.1f}回/日 は"
                + (f"「{point.get('imp_day_basis')}」"
                   f"（{point.get('imp_day_max_on')}"
                   if point.get("imp_day_max_on") else
                   f"「{point.get('imp_day_basis')}」（")
                + "・長尺を **7本** 公開した日）で、"
                  "**規則の 7倍 の供給の上に立っていました**"),
    }


def coupled(point: dict, short_scale: float,
            bands: dict[str, int] | None = None) -> dict | None:
    """**腕を引いてショートの再生が増えると、長尺の割合は薄まる。**（API 0単位）

    ## なぜ要るか（2026-09-01・最適化の回に測って足した）

    `surface_ceiling()` の天井はこう置かれています::

        share_max = 長尺の面/日 ÷ (長尺の面/日 + **いまの**ショート再生/日)

    分母の後半が **「いま」で固まっています。** ところが `scripts/eta.py` の
    `plan()` は、腕 `per_video` を天井まで引いた世界の
    `ceiling_day`（＝ ショートの再生/日）を**分子**に使いながら、
    合格点（`need_month`）は**この固まった天井**から出していました。

    **ショートを 4.16倍 に伸ばした世界では、長尺の割合はその分 薄まります。**
    実測（2026-09-01・保存済みの点 `at=2026-08-29`）::

        腕            長尺の面/日  ショート再生/日  長尺の割合  実効RPM   要る再生/月
        据え置き        1,368.0        857.9      61.5%   ¥1,252    159,710
        `per_video` ×4.16  1,368.0      3,569.0      27.7%   **¥598**  **334,696**

    そして「**3本とも同時に天井まで引くと 目標の 73.6%（残り ×1.36）**」は、
    **×4.16 の分子と、×1.00 の分母を掛けた数**でした。同じ土俵で解き直すと::

        目標の **73.6%** → **35.1%**   残り **×1.36** → **×2.85**（**2.1倍 甘い**）

    **この数は、毎周「立てるべき前提の大きさ」として印字されています**
    （`src/joint_cap.lines()`）。**前提の寸法が 2.1倍 小さく出ていました。**

    `rule_capped()` の末尾が「**短い側の再生（`short_views_day`）は
    動かしていません**」と書いているのと**同じ欠陥の、腕の側**です。

    ## 何を足していないか

    **推測を1つも足しません。** 長尺の面（`imp_day`）は据え置き ——
    ショートの腕を引いても長尺のサムネが見られる回数は増えないからです
    （増えるなら、それは `rpm` の腕のほうの話で、別に数えます）。
    動かすのは**分母の後半だけ**です。

    ## 使い方

        rpm_mix.coupled(point, short_scale=4.16)   # → 新しい rpm_max / long_share_max

    `short_scale` は **据え置きを 1.0 とした、ショート再生/日 の倍率**。
    `1.0` を渡すと、点に入っている `rpm_max` をそのまま復元します
    （復元できなければ **`None`** ＝「この点は別の帯で出ている」）。

    ## 覆る条件

    - `surface_ceiling()` が `short_views_day` を点に書くようになったら、
      ここの復元（`S = L × (1 - share) / share`）は要りません。
    - 帯（`BANDS`）が `長尺 お金 高` / `ショート 高` 以外で出された点には
      **当たりません**（自己検査で外れるので `None` を返します）。
    - 腕 `rpm` が「長尺の面そのものを増やす」形で測れるようになったら、
      `imp_day` の据え置きはやめること。
    """
    bands = bands or BANDS
    if not point:
        return None
    try:
        L = float(point.get("imp_day") or 0.0)
        share = float(point.get("long_share_max") or 0.0)
        now = float(point.get("rpm_now") or 0.0)
        scale = float(short_scale)
    except (TypeError, ValueError):
        return None
    if L <= 0 or now <= 0 or not (0.0 < share < 1.0) or scale <= 0:
        return None
    long_band = float(bands["長尺 お金 高"])
    short_band = float(bands["ショート 高"])
    # **自己検査**: 据え置きの割合から復元した RPM が、点の `rpm_max` と
    #     合わないなら、その点は別の帯（`level`）で出ています。**黙って
    #     上書きしないこと** —— 呼ぶ側が「当てられなかった」と言えるように。
    stored = point.get("rpm_max")
    check = share * long_band + (1.0 - share) * short_band
    if stored is None or abs(float(stored) - check) > max(1.0, abs(check) * 0.01):
        return None
    short_views_day = L * (1.0 - share) / share
    scaled = short_views_day * scale
    denom = L + scaled
    share_max = (L / denom) if denom > 0 else 0.0
    rpm_max = share_max * long_band + (1.0 - share_max) * short_band
    return {
        "factor": rpm_max / now,
        "rpm_now": now,
        "rpm_max": rpm_max,
        "long_share_max": share_max,
        "imp_day": L,
        "short_views_day": scaled,
        "short_views_day_before": short_views_day,
        "short_scale": scale,
        "rpm_max_before": float(stored),
        "long_share_max_before": share,
        "why": (f"ショートの再生を ×{scale:,.2f}"
                f"（{short_views_day:,.1f} → {scaled:,.1f}回/日）に伸ばすと、"
                f"長尺の面 {L:,.1f}回/日 は据え置きなので"
                f" 長尺の割合は {share * 100:.1f}% → **{share_max * 100:.1f}%**、"
                f" 実効RPM の天井は ¥{float(stored):,.0f} → **¥{rpm_max:,.0f}**"),
    }


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


def _freshness_lines(rec: dict) -> list[str]:
    """**この数字がどこまでの日を含んでいるか**を、数字と同じ画面に出す。

    **無ければ黙る**のではなく、「分かりません」と言うこと。
    黙ると、読む側は窓の終わり（＝今日）を信じます。**それが元の欠陥です。**
    """
    win = rec.get("window") or {}
    end, data_end = win.get("end"), win.get("data_end")
    if not data_end:
        return ["  [?] **この数字がどこまでの日を含むか分かりません**"
                "（`data/analytics_lag.jsonl` に点がありません）。"
                "**窓の終わり＝今日と読まないこと。**"]
    out = []
    pend = rec.get("pending") or {}
    lag = pend.get("lag_days")
    if end and data_end < end:
        out.append(f"  **中身は {data_end} まで**です"
                   + (f"（Analytics の日次は **{lag}日遅れ**）。" if lag is not None else "。")
                   + f"窓の終わり {end} は**問い合わせた日**であって、届いている日ではありません")
    if pend.get("total"):
        out.append(f"    **この数字に入っていない公開: {pend['total']:,}本**"
                   f"（{(pend.get('first') or '')[5:16]} → {(pend.get('last') or '')[5:16]}）"
                   f"／うち長尺 {pend.get('long', 0)}本")
        if pend.get("readable_on"):
            out.append(f"    → **{pend['readable_on']} より前に撃っても、その本は1本も出ません。**"
                       f"（この日に撃ち直すこと）")
    elif end and data_end < end:
        out.append("    入っていない公開はありません（この窓の後に出した本が無い）")
    return out


def _reach_freshness_lines(rec: dict) -> list[str]:
    """**面（`data/reach.jsonl`）が、Analytics の側に追いついているか。**

    2026-08-24 に足しました。理由はこの日踏んだものそのものです ——
    天井は **2つの実測の積**（混ざり方 × 面）なのに、鮮度の表示は
    Analytics の側にしか付いていませんでした。`data/reach.jsonl` は
    08/17 で止まっていて、そのまま出た天井が **¥184**。
    `scripts/reach.py` を撃ち直したら **¥287** です。
    **止まっていたことは、どこにも表示されていませんでした。**

    **「今日」と比べないこと。** Reporting も Analytics と同じく数日遅れるので、
    今日と比べると**追いついている日も必ず鳴ります**（鳴りっぱなしの警告は
    読まれません）。比べるのは **Analytics の中身の最終日**（`window.data_end`）
    —— そこに追いついていれば、面は取れるだけ取れています。
    """
    reach = rec.get("reach") or {}
    last_day = reach.get("last_day")
    if not last_day:
        return ["  [?] **面（インプレッション）がいつまでの日か分かりません**"
                "（`data/reach.jsonl` に日付がありません）。"
                "**`python scripts/reach.py` を撃つこと。**"]
    have = _iso(last_day)
    data_end = ((rec.get("window") or {}).get("data_end"))
    days = reach.get("days")
    if not data_end:
        return [f"    面（インプレッション）は **{have}** まで（{days}日ぶん）"]
    if have >= data_end:
        return [f"    面（インプレッション）は **{have}** まで（{days}日ぶん）"
                f" ＝ **Analytics の側（{data_end}）に追いついています**"]
    try:
        gap = (date.fromisoformat(data_end) - date.fromisoformat(have)).days
    except ValueError:
        gap = 0
    return [f"  [!] **面（インプレッション）が {gap}日ぶん遅れています**"
            f"（{have} まで・{days}日ぶん。Analytics の中身は {data_end} まで）。"
            f"**天井はこの面に乗っているので、いまの数字は低く出ます** ——"
            f" `python scripts/reach.py` を撃ってから読むこと"
            f"（2026-08-24 の実測: 4日ぶんで ¥184 → ¥287）"]


def _iso(day: str) -> str:
    """`20260821` も `2026-08-21` も `2026-08-21` にする（Reporting は詰めた形）。"""
    d = str(day)
    return f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 and d.isdigit() else d


def render(rec: dict | None) -> str:
    if not rec:
        return ("=== RPM の帯（実測の混ざり方）===\n"
                "  **まだ一度も測っていません。** `python -m src.rpm_mix --record`\n")
    mins = rec.get("minutes_by_form") or {}
    total = sum(mins.values()) or 1.0
    win = rec.get("window") or {}
    lines = ["=== RPM の帯（実測の混ざり方・`creatorContentType`）==="]
    lines.append(f"  窓 {win.get('start')}〜{win.get('end')}"
                 f"（{win.get('days')}日）／ JP の視聴分 {rec.get('jp_share', 1.0) * 100:.1f}%")
    lines.extend(_freshness_lines(rec))
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
    # **天井のすぐ下に置くこと。** 天井は「混ざり方 × 面」の積で、
    # 面が止まっていれば天井は低く出ます（2026-08-24 の実測: ¥184 → ¥287）。
    lines.extend(_reach_freshness_lines(rec))
    if rec.get("jp_share", 1.0) < JP_SHARE_FLOOR:
        lines.append(f"  [!] JP の視聴分が {rec['jp_share'] * 100:.1f}% ＝ **帯そのものを見直すこと**"
                     f"（この表は日本のお金の帯です）")
    return "\n".join(lines) + "\n"


def is_ready(prev: dict | None, now_last_day: str | None) -> tuple[bool, str]:
    """**前の点より中身が進んでいるか。**進んでいないなら撃つ意味がありません。

    実測（2026-08-21）—— `data/rpm_mix.jsonl` の最後の2行は**1バイト違わず同じ**
    でした。同じ日の中で2回撃ったからではありません。**中身の最終日が
    08/18 のまま動いていない**からで、何回撃っても同じ行が積まれます。
    申し送りが6回続けて「撃つこと」と言い、6回とも同じ答えを読んでいました。

    **「まだです」で終わらせないこと**（目標側の理由）。返す文には
    **いつなら進むか**を必ず入れます。
    """
    if not now_last_day:
        return True, ("  **中身の最終日が分かりません**"
                      "（`data/analytics_lag.jsonl` が空）→ 測ります")
    prev_end = ((prev or {}).get("window") or {}).get("data_end")
    if not prev_end:
        return True, f"  前の点に最終日の欄がありません（中身は {now_last_day} まで）→ 測ります"
    if now_last_day > prev_end:
        return True, f"  中身が **{prev_end} → {now_last_day}** に進みました → 測ります"
    pend = pending_after(now_last_day, long_ids=_long_ids())
    # **「次に動く日」は最終日の翌日ではありません** —— それはもう過ぎています。
    # 動くのは**こちらの明日**で、そのとき中身が1日ぶん進みます。
    tomorrow = datetime.now(JST).date() + timedelta(days=1)
    reach = date.fromisoformat(now_last_day) + timedelta(days=1)
    when = pend.get("readable_on")
    tail = (f"／待っている本が出るのは **{when}**" if when else "")
    return False, (f"  **測りません。**中身は前の点と同じ **{now_last_day}** までで、"
                   f"撃っても同じ行が積まれるだけです\n"
                   f"    入っていない公開 {pend.get('total', 0):,}本"
                   f"（うち長尺 {pend.get('long', 0)}本）。"
                   f"**次に中身が動くのは {tomorrow.isoformat()}**"
                   f"（そのとき {reach.isoformat()} まで入る）{tail}")


def main(argv: list[str] | None = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="RPM の帯を、実測の混ざり方から出す")
    ap.add_argument("--record", action="store_true", help="測って data/rpm_mix.jsonl に積む")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--show", action="store_true", help="最後に積んだ点を出すだけ（API を叩かない）")
    ap.add_argument("--if-ready", action="store_true",
                    help="**中身が前の点より進んでいるときだけ測る。**進んでいなければ "
                         "API を1回も叩かずに rc=2 と「次に意味がある日」を返す")
    ap.add_argument("--forms", action="store_true",
                    help="**本べつの形の控え（data/video_forms.json）だけ取り直す。**"
                         "Analytics 2回。RPM の帯は測らず、jsonl にも積まない")
    args = ap.parse_args(argv)

    # **控えだけを取り直す道**（2026-08-27 夜・最適化の回に足した）。
    #
    # `data/video_forms.json` を書き直すのは、長らく**この main の本処理だけ**
    # でした。本処理は `--record` を要り、`--if-ready` は「RPM の帯が動いたか」で
    # 門を閉めます。**分類の控えは、その門とは何の関係もありません** ——
    # 新しく公開した本の分類は毎日 増えるのに、RPM の帯が動かない日は
    # **1本も控えに入りません。**
    #
    # 実測 2026-08-27: 控えは **08-26 に取ったきり**で、分類し終えている
    # いちばん新しい公開日は **08-24**。前提「深い題のショート」が要る
    # 「両群がそろう公開日」は 08/25・08/26・08/27 と**もう3日ぶん公開済み**
    # なのに、`scripts/deadline_check.py` は **0日** と数え、
    # 「**まだ数えはじめたところ。この回は何もしないのが正解**」と毎周 出していました。
    # **待っても永久に 0 のまま**です（`_stale_todo()` の註）。
    #
    # だから「控えだけ」を切り出します。**2回の Analytics で済み**、
    # RPM の帯（`fetch_mix`）も `rpm_mix.jsonl` への追記も起こしません。
    if args.forms:
        saved = save_video_forms(fetch_video_forms(args.days), args.days)
        if not saved:
            print("  **取れませんでした。**控えは前のままです"
                  "（空で上書きすると『長尺が1本も無い』に化けます）")
            return 2
        longs = sum(1 for v in saved["forms"].values() if v == "長尺")
        print(f"  本べつの形を控え直しました: {len(saved['forms'])}本"
              f"（うち長尺 {longs}本）→ {FORMS.relative_to(ROOT)}")
        return 0

    if args.show or not args.record:
        print(render(last()))
        return 0

    if args.if_ready:
        ready, why = is_ready(last(), data_last_day())
        print(why)
        if not ready:
            return 2

    from . import reach_split

    mix = fetch_mix(args.days)
    # **控えを先に書き直します。** 面（インプレッション）を数える集合が
    # `config/pairs.yaml`（手で書く対応表）だけだと、新しく出した長尺が
    # 入らず、**出しても天井が動かない**形になります（2026-08-24）。
    saved = save_video_forms(fetch_video_forms(args.days), args.days)
    if saved:
        longs = sum(1 for v in saved["forms"].values() if v == "長尺")
        print(f"  本べつの形を控え直しました: {len(saved['forms'])}本"
              f"（うち長尺 {longs}本）→ {FORMS.relative_to(ROOT)}")
    rows = reach_split.dedupe(reach_split.load_rows())
    reach = reach_split.summary(rows, reach_split.long_ids())
    ceiling = surface_ceiling(mix, reach)
    rec = record(mix, ceiling)
    print(render(rec))
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
