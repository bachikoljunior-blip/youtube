#!/usr/bin/env python3
"""**月20万円に、いつ届くか。毎回これを出してから作業を決める。**

    python scripts/eta.py              # 予測を出して data/eta.jsonl に積む
    python scripts/eta.py --no-record  # 出すだけ（積まない）
    python scripts/eta.py --offline    # API を叩かず、積んである最後の点から出す

## なぜ要るか（2026-08-19 オーナー指示 33699957）

> 実行の初めに、YouTube収益月収20万がいつ達成されるかを予測し、
> それを早めることを考えてから進めること。

**この指示は「見積もりを書け」ではありません。**「早めることを考えてから進め」＝
**その回の作業をどれにするかを、予測日を動かすかどうかで決めろ**、という意味に読みます。

そして**文書に手順として書くだけでは飛ばされます。**`docs/trigger_main.md` は
135KB あり、実際に §3 が読み飛ばされた記録があります（2026-08-18 23:4x）。
だから**道具にして、数字が勝手に出る形**にしました。

## この道具が答えるのは3つ

1. **いつ届くか**（いまの実測のまま伸ばしたら）
2. **どの数字が止めているか**（門を1つずつ当てて、最初に落ちるものを名指しする）
3. **いま考えている作業は、その日付を動かすか**（動かさないなら、やる理由がない）

## 天井の検査が本体です

いちばん効くのは (1) ではなく、**「いまの構成の上限は目標に届くのか」**です。

    1本あたりの再生 × 1日に出せる上限（92本）× 30日 ÷ 1000 × RPM

これが 200,000 円に届かないなら、**本数を増やしても、在庫を増やしても、
予測日は永遠に来ません。** 増やすべきは本数ではなく、
**1本あたりの再生数か RPM のほう**です。**その判定を毎回やります。**

## 割り引いて読むこと

- **RPM は実測ではありません**（収益化前なので自分の数字が無い）。
  だから幅で出します。**この幅の中で結論が変わるなら、結論は出ていません**
- 登録率・1本あたり再生は**実測**（YouTube Analytics）。ここは推測ではありません
- ショートの視聴時間は 4,000時間の門に**入りません**。長尺の視聴時間だけが入ります
- **門2の「届きません」は、長尺の実力ではありません**（2026-08-19 12:0x に直した）。
  `days_long_hours` は直近365日の伸びを延ばした数なので、**長尺を1本も出していない限り
  必ず無限**になります。「長尺では開かない」と「まだ試していない」は別の命題です。
  だから最後の節が、**開けるのに要る「長尺1本あたり再生」**を逆算して出します
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

from src import levers  # noqa: E402  （`sys.path` を通した後でないと読めません）

LOG = ROOT / "data" / "eta.jsonl"

# --- 門（YouTube の公表値。守るのではなく、通らないと収入が0になる事実）---
SUBS_GATE = 1_000
LONG_HOURS_GATE = 4_000          # 直近12か月・長尺のみ
SHORTS_VIEWS_GATE = 10_000_000   # 直近90日・ショート
TARGET_YEN = 200_000             # 月収の目標

# --- 1日に出せる本数の上限（実測。data/upload_cap.jsonl の窓と同じ）---
UPLOAD_CAP_PER_DAY = 92

# --- 公開の密度（1日に何本「公開」するか。投稿＝予約とは別物）---
#     いまの予約は 246本が39.5日に散って 1日6.4本。詰めれば25本（受け取り帳 3c7e12a3）
PUBLISH_SCENARIOS = (4, 10, 25, 92)

# --- いま計画している密度（受け取り帳 3c7e12a3 の詰め直しが着地する所）---
#     門2a の逆算は「門1 が通る日まで」で割るので、この1つを正本にします
PLAN_PUBLISH_PER_DAY = 25

# --- 収益化の審査にかかる日数（YouTube 公表「通常1か月以内」。**実測ではない**）---
MONETIZE_REVIEW_DAYS = 30

# --- 段取りを立てるときに使う RPM は、その形の**いちばん低い帯** ---
#     `RPM_SCENARIOS` の 低/中/高 は「別の道」ではなく**同じニッチの幅**です。
#     いちばん高い帯で段取りを立てると、**計画そのものが上振れ側に乗ります**
#     （倍率の小さい帯を選ぶ `nearest` の論法をそのまま使うと、必ず「高」が出ます）。
PLAN_BAND_BY_FORM = {"ショート": "ショート 低", "長尺 お金": "長尺 お金 低"}

# --- RPM の幅（**実測ではない**。収益化前なので自分の数字が無い）---
RPM_SCENARIOS = {
    "ショート 低": 20,
    "ショート 中": 35,
    "ショート 高": 60,
    "長尺 お金 低": 400,
    "長尺 お金 中": 1_000,
    "長尺 お金 高": 2_000,
}

# --- 「長尺」と呼ぶ尺の下限（秒）---
#     Analytics は尺を返さないので、**平均視聴秒 ÷ 平均視聴率**で尺を復元して割ります
#     （`averageViewDuration / (averageViewPercentage/100)`）。ショートの上限は60秒、
#     この作りの長尺は4分以上（`src/verify.py`）なので、あいだの180秒に置いています。
LONG_FORM_SECONDS = 180

# --- 長尺1本が生む視聴分（**推測**。長尺の実測が無いので、尺×維持率で置く）---
#     ショートの実測は「1再生あたり22秒 ＝ 尺の49%」（2026-08-19 status.py）。
#     長尺は WATCH が通算13回しかないので、維持率を測れません。
#     **だから幅で置きます。** 低いほう（20%）で足りるなら、幅の中のどこでも足ります。
LONG_SHAPES = (
    ("尺4分・維持20%", 4, 0.20),
    ("尺5分・維持40%", 5, 0.40),
    ("尺7分・維持40%", 7, 0.40),
)

# --- 門2a を長尺で開けるとき、1日に何本の長尺を足すか ---
LONG_PER_DAY_SCENARIOS = (1, 2, 4)

NEVER = 10 ** 9  # 「届かない」を日数で表すときの番人

# --- **1本あたり再生の標本に、入れてよい本の条件**（2026-08-20 03:1x に足した） ---
#
# **伸びきるまでに要る時間**（`data/views.jsonl` を実測。n=9 ＝ 最後の観測が
# 168時間より後で、かつ 100再生を超えた本だけ）:
#
#       6時間  中央値  0.0%      36時間  中央値  98.8%
#      12時間  中央値 77.6%      48時間  中央値 100.0%
#      24時間  中央値 99.1%     168時間  中央値 100.0%
#
# **48時間で伸びが終わります。** だから「まだ48時間経っていない本」を標本に入れると、
# その本は**一生ぶんではなく数時間ぶん**を持って平均に入り、天井を下振れさせます。
MATURE_HOURS = 48


# --- **測定が返ってくる日**（2026-08-20 07:1x に足した） ---
#
# `blocking`（段取りを止めている未測定の入力）は「**どう測るか**」は書きますが、
# **「いつ答えが返るか」を1行も書いていませんでした。** そこが空いていたので、
# 測定の的にする日は「穴の空いている日」——つまり**公開の断絶を埋める都合**——で
# 選ばれていました（08/19 の申し送りは 3回続けて `--date 2026-09-02`）。
#
# **穴埋めと測定は、別の仕事です。** 穴埋めは「いつ埋めても同じ」ですが、
# 測定は**遅らせたぶんだけ段取り全体が遅れます**。実測（`data/uploaded.jsonl`・
# 2026-08-20 時点）では、いちばん近い穴は **09/02** で、いちばん早く予約できる日
# （明日）との差は **12日**。答えが返るのが 12日 遅くなります。
#
# 答えが返るまでにかかる日数は、この2つの和です:
#
#     公開 → 伸びきる    MATURE_HOURS（48時間）= 2日   `drop_unripe` が標本に入れる条件
#     伸びきる → 読める  ANALYTICS_LAG_DAYS（3日）     Analytics は日次で3日遅れ
#
# **覆る条件**: 日枠が朝のうちに開いている回なら「今日」も予約できるので、
# `soonest` は1日早くなります。ここは**閉じている側に倒して**明日から数えています
# （名指しした日に予約できないほうが損なので）。
ANALYTICS_LAG_DAYS = 3

# **予約の日付は全部 JST です。**`date.today()` はコンテナの TZ（＝UTC）を読むので、
# **JST の 00:00〜09:00 は前日を返します。** 2026-08-20 07:1x（JST）に足したこの節が、
# 最初の版で「いちばん早く予約できる日 ＝ 08/20」と印字しました。08/20 は
# **その時点で既に今日**（しかも 25本 予約済み）で、明日ではありません。
JST = timezone(timedelta(hours=9))


def today_jst() -> date:
    return datetime.now(JST).date()


def answer_day(publish: date) -> date:
    """その日に**公開**した本の1本あたり再生を、**読めるようになる日**（JST）。"""
    return publish + timedelta(days=math.ceil(MATURE_HOURS / 24) + ANALYTICS_LAG_DAYS)


def measure_targets(today: date, uploaded_path: Path | None = None) -> dict:
    """測定の的にできる2つの日と、**選び方で失う日数**を出す。

    - `soonest` …… いちばん早く予約できる日（**明日**。上の「覆る条件」）
    - `hole`    …… いちばん近い「予約が0本の日」＝**穴埋めの手順が選ぶ日**
    - `days_lost` …… `hole` を選ぶと、答えが何日遅れるか

    穴が無ければ `hole` は `None`（そのときは失うものもありません）。
    """
    uploaded_path = uploaded_path or (ROOT / "data" / "uploaded.jsonl")
    booked: set[date] = set()
    if uploaded_path.exists():
        for line in uploaded_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            at = row.get("at")
            if not at:
                continue
            try:
                d = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            booked.add(d.date())

    soonest = today + timedelta(days=1)
    hole: date | None = None
    # **予約が1件も無ければ「穴」はありません。** 空を「全部が穴」と読むと、
    # `soonest` 自身が穴として返り、差が 0日 なのに競合しているように見えます。
    last = max(booked) if booked else None
    day = soonest
    while last is not None and day <= last:
        if day not in booked:
            hole = day
            break
        day += timedelta(days=1)

    ans_soon = answer_day(soonest)
    out = {
        "soonest": soonest, "answer_soonest": ans_soon,
        "hole": hole, "answer_hole": answer_day(hole) if hole else None,
        "days_lost": (hole - soonest).days if hole else 0,
    }
    return out


def published_at(views_path: Path | None = None,
                 uploaded_path: Path | None = None) -> dict[str, datetime]:
    """`video_id` → **公開時刻**（UTC）。

    ## 出どころは2つ。**順番に意味があります**

    1. `data/views.jsonl` の `at - hours`（`hours` は公開からの経過時間）。
       **観測のたびに追記されるので、いちばん古い行がいちばん正確**です。
       `scripts/per_day_views.py` が同じ復元をしています
    2. `data/uploaded.jsonl` の `at`（**予約した公開時刻**）。1 に無い本 ——
       つまり**まだ一度も観測されていない本**は、ここでしか年齢が分かりません

    **`src/build_perf.py` の `first_seen()` とは別物です。** あちらは
    「最初に観測した時刻」で、こちらは「公開した時刻」。観測は公開の後なので、
    `first_seen` は必ず遅れます（実測で最大 38.7時間）。
    **年齢の門に使うなら、遅れるほうを使ってはいけません。**
    """
    views_path = views_path or (ROOT / "data" / "views.jsonl")
    uploaded_path = uploaded_path or (ROOT / "data" / "uploaded.jsonl")
    out: dict[str, datetime] = {}

    def _parse(v) -> datetime | None:
        try:
            d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

    if views_path.exists():
        for line in views_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = row.get("id") or row.get("video_id")
            at = _parse(row.get("at"))
            hours = row.get("hours")
            if not vid or at is None or hours is None:
                continue
            try:
                born = at - timedelta(hours=float(hours))
            except (TypeError, ValueError):
                continue
            # いちばん古い観測が、いちばん正確（誤差は観測の間隔ぶんしか無い）
            if vid not in out or born < out[vid]:
                out[vid] = born

    if uploaded_path.exists():
        for line in uploaded_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = row.get("video_id")
            at = _parse(row.get("at"))
            if vid and at is not None:
                out.setdefault(vid, at)   # 1 のほうが正確なので、上書きしない
    return out


def drop_unripe(rows, pub: dict[str, datetime], now: datetime,
                window_days: int = 28) -> tuple[list, dict[str, list[str]]]:
    """**1本あたり再生の標本から、数えてはいけない本を落とす。**

    返すのは `(残した行, 落とした理由 → video_id の一覧)`。

    ## なぜ要るか（2026-08-20 03:1x。**実測で見つけました**）

    天井は `1本あたり再生 × 92本 × 30日` です。この `1本あたり再生` は
    **「1本が一生に集める再生数」**でなければ、掛け算が意味を持ちません。
    ところが測っていたのは **「直近28日の窓に落ちた再生数」**で、
    次の2つが混ざっていました。

    **(1) まだ公開されていない本**（`未公開`）。実測 2本 —— `KdlvGxloIg4` は
    `uploaded.jsonl` の `at` が **08/24**（予約）で、Analytics には
    **1再生**の行が立っています。**予約は 359本あります。**
    そのうち何本かが1再生ずつ漏れて標本に入るたび、平均は 0 のほうへ引かれます。
    **本数を増やすほど天井が下がる**という、向きの逆さまな計器になります。

    **(2) 公開から48時間が経っていない本**（`未熟`）。上の `MATURE_HOURS` の実測どおり、
    48時間で伸びは終わります。**それより若い本は、一生ぶんではなく数時間ぶん**を
    持って平均に入ります。

    **(3) 窓より前に公開された本**（`窓の外`）。いまは1本もいませんが、
    **08/22 ごろから出ます** —— 08/06 の本は、窓が動けば「28日窓の中の再生 ≒ 0」に
    なります。伸びは48時間で終わっているので、**残っているのは尻尾だけ**です。
    それを「1本あたり」として平均に入れると、**チャンネルが古くなるだけで
    天井が下がり続けます。**

    ## 落とし先が無くなったら、落とさない

    `views.jsonl` は Data API の読みで作られるので、**日枠が閉じた窓では更新が止まります**
    （実測: 08/18 09:08 で止まったまま 1.7日）。**年齢の出どころが全部欠けたときに
    標本を空にすると、この道具の本体（天井）が黙って 0 になります。**
    そのときは**落とさずに全部返し、理由に `落とし先なし` を立てます。**
    """
    kept: list = []
    dropped: dict[str, list[str]] = {"未公開": [], "未熟": [], "窓の外": []}
    ripe_before = now - timedelta(hours=MATURE_HOURS)
    window_open = now - timedelta(days=window_days)
    for r in rows:
        vid = r[0]
        born = pub.get(vid)
        if born is None or born > now:
            dropped["未公開"].append(vid)
        elif born > ripe_before:
            dropped["未熟"].append(vid)
        elif born < window_open:
            dropped["窓の外"].append(vid)
        else:
            kept.append(r)
    if not kept:
        return list(rows), {"落とし先なし": [r[0] for r in rows]}
    return kept, {k: v for k, v in dropped.items() if v}


def split_per_video(rows) -> tuple[list[int], list[int]]:
    """`dimensions=video` の行を、**尺で2つに割る**（2026-08-19 14:2x に足した）。

    返すのは `(ショートの再生・昇順, 長尺の再生・昇順)`。

    ## なぜ割るか

    ここは長らく1行でした ——

        vals = sorted(r[1] for r in per_video if r[1] >= 30)

    **その `>= 30` が、長尺を5本とも落としていました。** 実測は 4/3/2/1/1回で、
    **30を超える長尺は1本もありません。** 落ちた結果 `median_views_per_video` は
    **ショートだけの中央値（1,092回）**になり、天井の表がそれを長尺の帯にも当てて
    **「長尺 お金 中 … 届く／いまの 0.1倍」**と印字していました。
    **長尺の実測を当てると 36倍**です。**桁が2つちがい、向きが逆になります。**

    28b90d6 が門2a で塞いだのと同じ形（「まだ試していない」が
    「もう届いている」に化ける）が、**円の側に残っていました。**

    ## 尺の出し方

    Analytics は尺そのものを返しません。**平均視聴秒 ÷ 平均視聴率**で復元します。
    `averageViewPercentage` が 0 の行は割れないので、**ショート側**に置きます
    （長尺に置くと、測れていない行が長尺の中央値を下げます）。

    **長尺には 30再生の床を当てません。** 当てると1本も残らず、
    「測っていない」と「0だった」の区別がつかなくなります。

    ## **ショートの床も外しました**（2026-08-19 15:0x）

    ここは `elif views >= 30` でした。**床は標本からは落としますが、
    天井の掛け算からは落としません。** 天井は

        1本あたり再生 × **92本/日** × 30日

    で、この 92 は「作った本数」です。**床を通った本だけの数字を、
    落ちた本まで含む本数に掛けている**ので、
    **落ちた本が全部「通った本と同じだけ回る」ことになっていました。**

    実測（直近28日・ショート22本）: 床を通ったのは20本で、
    落ちた2本は**1回ずつ**。**床は「まだ伸びていない本」を落とすつもりの道具でしたが、
    見ているのは年齢ではなく再生数**なので、伸びなかった本と区別がつきません。

    落とすなら**本数のほうも同じ割合で削る**必要があり、それは結局
    **全部を平均する**のと同じです（`_measure` の平均）。
    """
    shorts: list[int] = []
    longs: list[int] = []
    for row in rows:
        views = row[1]
        avg_sec = row[2] if len(row) > 2 else 0
        avg_pct = row[3] if len(row) > 3 else 0
        seconds = (avg_sec / (avg_pct / 100)) if avg_pct else 0.0
        if seconds >= LONG_FORM_SECONDS:
            longs.append(views)
        else:
            shorts.append(views)
    return sorted(shorts), sorted(longs)


def _measure() -> dict:
    """YouTube Analytics から、予測に要る実測値だけを取る。"""
    from googleapiclient.discovery import build
    from src.auth import credentials

    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()

    def q(days: int, metrics: str, **kw) -> list:
        start = end - timedelta(days=days)
        res = analytics.reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
            metrics=metrics, **kw,
        ).execute()
        return res.get("rows") or []

    base = "views,estimatedMinutesWatched,subscribersGained,subscribersLost"
    all_rows = q(3650, base)
    d90 = q(90, base)
    d28 = q(28, base)
    d7 = q(7, base)

    # 長尺の視聴時間は流入経路では割れない。再生場所（SHORTS_FEED か否か）で割る。
    place = q(365, "views,estimatedMinutesWatched", dimensions="insightPlaybackLocationType")
    long_minutes_365 = sum(r[2] for r in place if r[0] != "SHORTS_FEED")
    shorts_views_90 = 0
    place90 = q(90, "views,estimatedMinutesWatched", dimensions="insightPlaybackLocationType")
    shorts_views_90 = sum(r[1] for r in place90 if r[0] == "SHORTS_FEED")

    # 1本あたりの再生（直近28日に再生のあった本の中央値）。
    #
    # **形ごとに別々に出すこと**（2026-08-19 14:2x に足した）。ここは長らく
    # `if r[1] >= 30` の1本だけで、**その30が長尺を5本とも落としていました** ——
    # 実測は 4/3/2/1/1再生で、**30を超える長尺は1本もありません。**
    # 落ちた結果 `median_views_per_video` は**ショートだけの数**になり、
    # それを天井の表が長尺の帯にも当てて **「長尺 お金 中 … 届く」** と印字していました。
    # **「まだ試していない」を「もう届いている」と読み替える形**で、
    # 28b90d6 が門2a で塞いだ穴と同じものが、円の側に残っていました。
    #
    # 尺は Analytics では取れないので、**平均視聴秒 ÷ 平均視聴率**で復元します。
    per_video = q(28, "views,averageViewDuration,averageViewPercentage",
                  dimensions="video", sort="-views", maxResults=200)
    # **標本に入れてよい本だけにする**（2026-08-20 03:1x。`drop_unripe` に理由）。
    # 予約したまま公開されていない本と、公開から48時間が経っていない本は、
    # **一生ぶんではない再生数**を持って平均に入り、天井を下振れさせます。
    per_video, unripe = drop_unripe(per_video, published_at(),
                                    datetime.now(timezone.utc), window_days=28)
    vals, long_sorted = split_per_video(per_video)
    median_views = vals[len(vals) // 2] if vals else 0
    long_median = long_sorted[len(long_sorted) // 2] if long_sorted else None
    # **天井が要るのは中央値ではなく平均です**（2026-08-19 15:0x に直した）。
    # 天井は「N本ぶんの**合計**」なので、合計 ＝ N × **平均**。
    # 中央値を掛けてよいのは分布が対称なときだけで、ショートの再生は必ず右に歪みます。
    # 実測（直近28日・ショート22本）: 中央値 1,092 に対し **平均 909**（**17%の差**）。
    # そして「いちばん近い帯」の倍率は **1.1倍 → 1.33倍** に変わります。
    mean_views = round(sum(vals) / len(vals)) if vals else 0
    long_mean = round(sum(long_sorted) / len(long_sorted)) if long_sorted else None

    def row(rows, i):
        return rows[0][i] if rows else 0

    return {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subs_net": row(all_rows, 2) - row(all_rows, 3),
        "views_all": row(all_rows, 0),
        "views_7d": row(d7, 0),
        "views_28d": row(d28, 0),
        "views_90d": row(d90, 0),
        "subs_gained_28d": row(d28, 2),
        "subs_gained_90d": row(d90, 2),
        "long_hours_365": round(long_minutes_365 / 60, 1),
        "shorts_views_90d": shorts_views_90,
        # **天井を動かすのはこちら**（平均）。中央値は「典型的な1本」用に残します。
        "views_per_video": mean_views,
        "median_views_per_video": median_views,
        "videos_with_views_28d": len(vals),
        # **長尺だけの1本あたり再生**（`None` ＝ 直近28日に長尺の再生が1本も無い）
        "long_per_video": long_mean,
        "long_median_per_video": long_median,
        "long_videos_28d": len(long_sorted),
        "long_views_28d": sum(long_sorted),
        # **標本から落とした本**（理由 → 本数）。0件でも鍵は残す（黙って消えないため）
        "per_video_dropped": {k: len(v) for k, v in unripe.items()},
    }


def _per_video(m: dict) -> float:
    """1本あたり再生（ショート）。**天井を動かす数なので、平均のほうを使います。**

    `data/eta.jsonl` の古い点には `views_per_video` がありません（8点目まで）。
    **無い点を 0 と読むと、差の節が「1,092 → 0」＝ -100% と印字します**ので、
    落ちる先を中央値に置いています。**中央値は上振れ側**なので、
    古い点との差は「縮んだ」側に寄って見えることに注意すること。
    """
    v = m.get("views_per_video")
    return v if v is not None else m.get("median_views_per_video", 0)


def _days_to(need: float, per_day: float) -> float:
    """必要量と1日あたりから日数。進んでいないなら NEVER。"""
    if need <= 0:
        return 0.0
    if per_day <= 0:
        return NEVER
    days = need / per_day
    # 100年より先は「届かない」と同じに畳む。**桁の大きい数を残すと、
    # 前の回との差（縮んだぶん）がその桁に埋もれて読めなくなります。**
    return NEVER if days > 36_500 else days


def _print_dropped(P, m: dict) -> None:
    """**標本から何本落としたか**を、天井の行のすぐ下に出す（2026-08-20 03:1x）。

    ここは長らく、こう**断って済ませて**いました ——

        **下振れ側で読むこと** —— 直近数日に公開した本はまだ伸びきっていないので、
        平均はその分だけ低く出ます。

    **断りは、下振れの大きさを言いません。**（実測では 869 → 952 ＝ **+9.6%**、
    いちばん近い帯までの倍率が **1.4倍 → 1.27倍**）。**測って落とせるものでした。**
    """
    dropped = m.get("per_video_dropped") or {}
    if not dropped:
        P("      （標本から落とした本はありません）")
        return
    if "落とし先なし" in dropped:
        P(f"      [!] **年齢が1本も引けませんでした**（{dropped['落とし先なし']}本）。"
          "`data/views.jsonl` が古い可能性 → **落とさずに全部数えています。下振れ側で読むこと。**")
        return
    order = ("未公開", "未熟", "窓の外")
    why = {
        "未公開": "**まだ公開されていない**（予約のまま Analytics に行が立つ。予約は 359本ある）",
        "未熟": f"公開から **{MATURE_HOURS}時間**が経っていない（伸びが終わっていない）",
        "窓の外": "**28日の窓より前**に公開（窓に落ちているのは伸びた後の尻尾だけ）",
    }
    P("      標本から落とした本（**一生ぶんの再生数を持っていない本**）:")
    for k in order:
        if dropped.get(k):
            P(f"        {k}  {dropped[k]}本 …… {why[k]}")


def _fmt_days(days: float) -> str:
    if days >= NEVER:
        return "**届きません**（いまの速さでは増えていない）"
    if days <= 0:
        return "**通過済み**"
    if days > 36_500:  # 100年より先は、日付を書いても意味がない
        return f"**{days/365:,.0f}年後 ＝ 事実上いまの形では届きません**"
    when = date.today() + timedelta(days=math.ceil(days))
    if days > 3650:
        return f"{days/365:.0f}年後（{when.isoformat()}）"
    if days > 365:
        return f"{days/365:.1f}年後 ＝ {math.ceil(days):,}日（{when.isoformat()}）"
    return f"**{math.ceil(days):,}日後（{when.isoformat()}）**"


def _long_break_even(a: dict) -> list[dict]:
    """**門1 が通る日までに門2a も開けるには、長尺1本あたり何回の再生が要るか。**

    返すのは形（尺×維持率）ごとの1行で、`views` は「長尺を1日L本足したとき」の
    必要な1本あたり再生を L べつに持ちます。

    **なぜ「本数」ではなく「1本あたり再生」を解くか。** 本数はこちらで決められます
    （在庫と日枠の話で、`upload_cap` が上限を知っている）。決められないのは
    **長尺が何回再生されるか**のほうで、そこだけが未知です。
    未知の側を解いて出せば、**段2 に入った瞬間に当たり外れが判定できます**
    （M20 の「推測を測れる形にする」と同じ形）。
    """
    days = a["days_subs_at"].get(PLAN_PUBLISH_PER_DAY, NEVER)
    minutes = a["long_minutes_needed"]
    rows = []
    for label, length_min, retention in LONG_SHAPES:
        per_view = length_min * retention
        views = {}
        for per_day in LONG_PER_DAY_SCENARIOS:
            slots = per_day * days
            views[per_day] = (minutes / (slots * per_view)) if slots > 0 and per_view > 0 else float("inf")
        rows.append({"label": label, "min_per_view": per_view, "views": views})
    return rows


def analyse(m: dict) -> dict:
    """実測から、門ごとの日数と天井を出す。"""
    views_day_7 = m["views_7d"] / 7
    views_day_28 = m["views_28d"] / 28
    # 予測には速いほうを使う（伸びている最中に遅いほうで測ると、悲観に倒れる）
    views_day = max(views_day_7, views_day_28)

    sub_rate = (m["subs_gained_28d"] / m["views_28d"]) if m["views_28d"] else 0.0
    subs_per_day = views_day * sub_rate

    a = {
        "views_per_day": views_day,
        "views_per_day_7d": views_day_7,
        "views_per_day_28d": views_day_28,
        "sub_rate": sub_rate,
        "subs_per_day": subs_per_day,
        "subs_remaining": max(0, SUBS_GATE - m["subs_net"]),
    }

    # --- 門1: 登録者1,000人 ---
    a["days_subs"] = _days_to(a["subs_remaining"], subs_per_day)

    # 公開の密度べつの門1（report のループが手で計算していたものをここへ寄せた。
    # **門2a の逆算がこの日数を要る**ので、2か所で別々に計算すると必ずずれます）
    a["days_subs_at"] = {
        n: _days_to(a["subs_remaining"], n * _per_video(m) * sub_rate)
        for n in sorted(set(PUBLISH_SCENARIOS) | {PLAN_PUBLISH_PER_DAY})
    }

    # --- 門2a: 長尺4,000時間（ショートは入らない）---
    long_hours_per_day = m["long_hours_365"] / 365
    a["days_long_hours"] = _days_to(LONG_HOURS_GATE - m["long_hours_365"], long_hours_per_day)

    # **その無限は「遠い」ではなく「測定になっていない」。**
    #
    # `days_long_hours` は伸び率を先へ延ばした数なので、伸びが実質ゼロなら
    # 必ず無限になります。**そのとき無限が言っているのは長尺の実力ではなく、
    # 長尺をまだ出していないこと**です。しきい値を手で決めずに済む言い方はこれ:
    # **延ばした先が100年より遠いなら、その伸び率は0と区別がつかない**
    # ＝ 測定として成立していない（`_days_to` が100年で NEVER に畳むのと同じ線）。
    # 実測 0.1時間/365日 は、まさにこの帯です。
    a["long_untried"] = a["days_long_hours"] >= NEVER
    a["long_hours_365_seen"] = m["long_hours_365"]

    # --- 門2b: ショート 直近90日で1,000万再生 ---
    a["shorts_needed_per_day"] = SHORTS_VIEWS_GATE / 90
    a["days_shorts_gate"] = 0.0 if views_day >= a["shorts_needed_per_day"] else NEVER

    # 収益化はどちらかの門2 ＋ 門1
    a["days_monetized"] = max(a["days_subs"], min(a["days_long_hours"], a["days_shorts_gate"]))

    # --- 門2a を「長尺を足して」開けるなら、長尺1本に何回の再生が要るか ---
    #
    # **これが無かったので、この道具は 8/19 の初回から「届きません」しか言えず、
    # 段2（M20）が要求している数字を一度も出していませんでした。**
    # `days_long_hours` は「直近365日の長尺の伸び」をそのまま延ばした数で、
    # 長尺を1本も出していない以上、**必ず「届かない」になります**（0で割る）。
    # それは「長尺では開かない」ではなく「**まだ試していない**」です。
    #
    # 開けるかどうかは、次の1本の式で決まります:
    #     残り視聴分 = 長尺の本数 × 長尺1本あたり再生 × 1再生あたり視聴分
    # 門1 が通る日までに開けたいので、本数は「1日L本 × 門1の日数」で埋まります。
    # **未知は「長尺1本あたり再生」だけ**なので、そこを解いて出します。
    a["long_minutes_needed"] = max(0.0, (LONG_HOURS_GATE - m["long_hours_365"]) * 60)
    a["long_break_even"] = _long_break_even(a)

    # --- 天井: いまの構成で出せる最大の月収 ---
    #
    # **帯ごとに、その形の実測を当てます**（2026-08-19 14:2x）。
    # ここは長らく1つの `per_video`（＝**ショートだけ**の中央値）を全部の帯に当てていて、
    # 長尺の帯に「**届く**」と印字していました。**長尺の実測は 1本 2回**（n=5）で、
    # ショートの 1,092回 とは**546倍ちがいます。** 混ぜると、
    # 「長尺をまだ出していない」が「長尺なら届く」に化けます。
    per_video = _per_video(m)
    long_per_video = m.get("long_per_video")
    a["long_per_video"] = long_per_video
    a["long_videos_28d"] = m.get("long_videos_28d", 0)
    a["long_views_28d"] = m.get("long_views_28d", 0)

    def _band_per_video(key: str) -> float:
        """その帯の1本あたり再生。**長尺の実測が無いときだけ**ショートで代用する。"""
        if key.startswith("長尺") and long_per_video is not None:
            return long_per_video
        return per_video

    a["per_video_by_band"] = {k: _band_per_video(k) for k in RPM_SCENARIOS}
    a["band_measured"] = {
        k: ("長尺" if (k.startswith("長尺") and long_per_video is not None) else "ショート")
        for k in RPM_SCENARIOS
    }
    ceiling_views_month = per_video * UPLOAD_CAP_PER_DAY * 30
    a["ceiling_views_month"] = ceiling_views_month
    a["ceiling_views_month_by_band"] = {
        k: a["per_video_by_band"][k] * UPLOAD_CAP_PER_DAY * 30 for k in RPM_SCENARIOS
    }
    a["ceiling"] = {
        k: a["ceiling_views_month_by_band"][k] / 1000 * rpm for k, rpm in RPM_SCENARIOS.items()
    }
    # **「ショート並みに伸びたら」の側も残します。** 実測 2回 は
    # 「登録者9人のチャンネルの長尺」であって「長尺の実力」ではない（M20）ので、
    # **片方だけ出すと、こんどは逆向きに読み違えます。**
    a["ceiling_if_shorts_rate"] = {
        k: ceiling_views_month / 1000 * rpm for k, rpm in RPM_SCENARIOS.items()
    }

    # 目標に要る月間再生数（RPM ごと）
    a["views_needed_month"] = {k: TARGET_YEN * 1000 / rpm for k, rpm in RPM_SCENARIOS.items()}
    # 1日92本の上限で、その再生数に要る「1本あたり再生」
    a["per_video_needed"] = {
        k: v / (UPLOAD_CAP_PER_DAY * 30) for k, v in a["views_needed_month"].items()
    }
    # **要る倍率は、その帯の形の実測で割ること**（ここが混ざると 36倍 が 0.1倍 に見える）
    a["per_video_ratio"] = {
        k: (a["per_video_needed"][k] / a["per_video_by_band"][k]
            if a["per_video_by_band"][k] else float("inf"))
        for k in RPM_SCENARIOS
    }
    a["per_video_now"] = per_video
    return a


def report(m: dict, a: dict) -> list[str]:
    out: list[str] = []
    P = out.append
    P("=" * 66)
    P("=== 月20万円に、いつ届くか（実測から。RPM だけが推測）===")
    P("=" * 66)
    P("")
    P("--- いま出ている数（YouTube Analytics。推測ではありません）---")
    P(f"  登録者（純）      {m['subs_net']:>10,} 人   （門は {SUBS_GATE:,} 人・**あと {a['subs_remaining']:,} 人**）")
    P(f"  再生／日          {a['views_per_day_7d']:>10,.0f} 回（直近7日）  {a['views_per_day_28d']:>7,.0f} 回（直近28日）")
    P(f"  登録率            {a['sub_rate']*100:>10.4f} %   ＝ 再生 {1/a['sub_rate']:,.0f} 回につき1人" if a["sub_rate"] else "  登録率            **0** ＝ 何回再生されても増えていない")
    P(f"  長尺の視聴時間    {m['long_hours_365']:>10,.1f} 時間（直近365日。門は {LONG_HOURS_GATE:,}）")
    P(f"  ショート90日      {m['shorts_views_90d']:>10,} 回（門は {SHORTS_VIEWS_GATE:,}）")
    P(f"  1本あたり再生     {a['per_video_now']:>10,} 回（**ショート**・**平均**・"
      f"直近28日に再生のあった本のうち、**標本に残った {m['videos_with_views_28d']} 本**）")
    if m.get("median_views_per_video") and m["median_views_per_video"] != a["per_video_now"]:
        P(f"    （中央値は {m['median_views_per_video']:,} 回 ＝ **典型的な1本**。"
          "**天井には平均のほうを使います** —— 天井は N本ぶんの合計で、合計 ＝ N × 平均）")
    if a.get("long_per_video") is None:
        P("  1本あたり再生（長尺）    **測れていません**（直近28日に長尺の再生が0本）")
    else:
        P(f"  1本あたり再生（長尺）{a['long_per_video']:>10,} 回（平均・n={a['long_videos_28d']}・合計 {a['long_views_28d']:,}回）"
          f"  ← ショートの **1/{(a['per_video_now'] / a['long_per_video']):,.0f}**")
    P("")
    P("--- 門を1つずつ当てる（**最初に落ちるものが、いまの律速**）---")
    P(f"  [門1] 登録者 {SUBS_GATE:,}人      {_fmt_days(a['days_subs'])}")
    P(f"        いまの速さ ＝ 1日 {a['subs_per_day']:.2f} 人（再生 {a['views_per_day']:,.0f}／日 × 登録率 {a['sub_rate']*100:.4f}%）")
    P(f"  [門2a] 長尺 {LONG_HOURS_GATE:,}時間    {_fmt_days(a['days_long_hours'])}")
    if a["long_untried"]:
        # **「遠い」と「分母が0」は別。** ここを同じ字で出していたので、
        # 2回とも「長尺では開かない」と読まれかけました（下の逆算の節が答えです）。
        P(f"         ↑ **これは長尺の実力ではありません。** 直近365日の長尺の視聴時間が"
          f" {a['long_hours_365_seen']:,.1f}時間 ＝ **伸び率が0と区別がつきません**。")
        P("         延ばした数が無限なのは、長尺が弱いからではなく**まだ出していない**から。")
        P("         **「開かない」ではなく「まだ試していない」です。** 合格点は下の節に出します。")
    if a["days_shorts_gate"] == 0:
        shorts_line = "**通っています**"
    else:
        shorts_line = (f"**届きません**（1日 {a['shorts_needed_per_day']:,.0f}回 要る"
                       f"／いま {a['views_per_day']:,.0f}回）")
    P(f"  [門2b] ショート90日で{SHORTS_VIEWS_GATE:,}回    {shorts_line}")
    P(f"  → **収益化そのもの: {_fmt_days(a['days_monetized'])}**")
    if a["long_untried"] and a["days_monetized"] >= NEVER:
        P("       **この「届きません」を、諦める理由に使わないこと。** 門2a の無限が"
          "そのまま出ているだけで、**未着手を測った数ではありません**。")
    P("")
    P("--- 天井（**ここが本体**）---")
    lpv = a.get("long_per_video")
    P(f"  1本あたり再生は**形ごとに別の実測**です（直近28日。混ぜると長尺が「もう届く」に見えます）:")
    P(f"    ショート  **{a['per_video_now']:,}回**／本（**平均**・n={m.get('videos_with_views_28d', 0)}・**床は当てていません**）")
    P("      **床（30再生未満は除外）を外しました**（2026-08-19 15:0x）。床は標本からは落としますが、")
    P(f"      **下の {UPLOAD_CAP_PER_DAY}本 からは落としません。** 落ちた本まで「通った本と同じだけ回る」ことになっていました。")
    P("      **天井は「本数を増やす意味があるか」を決める数**なので、上振れ側で読むと『届く』を作ります。")
    _print_dropped(P, m)
    if lpv is None:
        P("    長尺      **測れていません**（直近28日に長尺の再生が1本もない）"
          " → 下の長尺の行は**ショートの数で代用**しています。**実測ではありません。**")
    else:
        P(f"    長尺      **{lpv:,}回**／本（**平均**・n={a['long_videos_28d']}・合計 {a['long_views_28d']:,}回・"
          "**30再生の床は当てていません**。当てると1本も残りません）")
    P(f"  1日に出せる上限 {UPLOAD_CAP_PER_DAY}本 × 30日 に、**その形の実測**を当てた上限:")
    for k in RPM_SCENARIOS:
        yen = a["ceiling"][k]
        need = a["per_video_needed"][k]
        mark = "**届く**" if yen >= TARGET_YEN else "届かない"
        ratio = a["per_video_ratio"][k]
        src = a["band_measured"][k]
        P(f"    {k:<12} RPM ¥{RPM_SCENARIOS[k]:>5,}  上限 ¥{yen:>10,.0f}  {mark:<8} "
          f"要 1本 {need:>9,.0f}回（{src}の実測の **{ratio:,.1f}倍**）")
    if lpv is not None:
        P("")
        P("  **長尺が「ショート並み（1本 "
          f"{a['per_video_now']:,}回）に伸びたら」の側も出します**（片方だけだと逆向きに読み違えます）:")
        for k in RPM_SCENARIOS:
            if not k.startswith("長尺"):
                continue
            yen2 = a["ceiling_if_shorts_rate"][k]
            mark2 = "**届く**" if yen2 >= TARGET_YEN else "届かない"
            P(f"    {k:<12} RPM ¥{RPM_SCENARIOS[k]:>5,}  上限 ¥{yen2:>10,.0f}  {mark2}")
        P(f"  **実測 {lpv:,}回 は「長尺の実力」ではありません**（M20）。"
          f"n={a['long_videos_28d']} で、登録者 {m['subs_net']} 人のチャンネルに出した本の数です。")
        P("  **決まったのは1つだけ**: いまの実測を当てるかぎり、"
          "**長尺の帯も上限が目標の下**にあります。")
        P("  だから段2 は「長尺に替えれば届く」ではなく、"
          f"**1本あたりを {lpv:,}回 から上げられるか**を測る段です。")
    P("")
    # **いちばん近い帯を名指しする**（2026-08-19 14:2x に足した）。
    #
    # 表は6行あって、どれも「届かない」と書いてあります。**そこで読むのをやめると、
    # 6つが同じくらい遠いように見えます。** 実際には倍率が2桁ちがい、
    # 前の回は「ショート単独は原理的に閉じている」と読んで長尺へ寄せました。
    # **RPM ¥60 の帯では、要るのは 1本あたり 1.1倍です。**
    nearest = min(RPM_SCENARIOS, key=lambda k: a["per_video_ratio"][k])
    nr = a["per_video_ratio"][nearest]
    npv = a["per_video_by_band"][nearest]
    P(f"  **いちばん近い帯: {nearest}**（RPM ¥{RPM_SCENARIOS[nearest]:,}）"
      f" ＝ 1本あたりを **{nr:,.1f}倍**（{npv:,}回 → {a['per_video_needed'][nearest]:,.0f}回）")
    P("      **6行とも「届かない」でも、遠さは同じではありません。**"
      "倍率の小さい帯から手を付けること。")
    P("")
    reachable = [k for k in RPM_SCENARIOS if a["ceiling"][k] >= TARGET_YEN]
    unreachable = [k for k in RPM_SCENARIOS if a["ceiling"][k] < TARGET_YEN]
    if unreachable:
        P(f"  [!] **1日の上限まで出しても月20万に届かない帯: {', '.join(unreachable)}**")
        P("      この帯にいる限り、**本数を増やしても在庫を増やしても、日付は動きません。**")
        P("      動くのは **1本あたりの再生数** か **RPM（＝ニッチと尺）** の2つだけです。")
    if not reachable:
        P("  [!] **どの帯でも届きません。いまの構成は、上限そのものが目標の下にあります。**")
    else:
        P(f"  上限で届く帯: {', '.join(reachable)}")
        P("      **ただし RPM は実測ではありません。** 収益化後に自分の数字で測り直すこと。")
    P("")
    P("--- 早めるには、どれを何倍にするか（**倍率が小さいものから手を付ける**）---")
    for label, now, need in _levers(m, a):
        P(f"    {label:<26} いま {now:<16} → 要 {need}")
    P("")
    P("--- **公開の密度を上げたら、門1はいつ通るか**（1本あたり再生を据え置いた見積り）---")
    P(f"    ＝ 1日に公開する本数 × {a['per_video_now']:,}回 × 登録率 {a['sub_rate']*100:.4f}%")
    for n in PUBLISH_SCENARIOS:
        v = n * a["per_video_now"]
        P(f"    1日 {n:>3}本 公開 → 再生 {v:>9,.0f}／日 → 門1 {_fmt_days(a['days_subs_at'][n])}")
    P("    **これは推測です**（1日N本でも1本あたりが保つかは未測定＝M14 の「配信の壁」）。")
    P("    ただし 4本/日 までは崩れないことが実測済み（2026-08-19 04:4x・中央値 +50.5%）。")
    out.extend(_report_long_gate(m, a))
    return out


def plan(m: dict, a: dict, density: int = PLAN_PUBLISH_PER_DAY,
         today: date | None = None) -> dict:
    """**月20万に届くまでの段取りを、必ず1つ返す。**

    2026-08-20 06:2x・オーナー指示（原文）——

    > 「毎回の実行の最初にいつ20万の達成できるかを予測して、それを早めるには
    >   どうしたらいいかを考えてから進めて。**予測は達成できないで終わらせず、
    >   達成できるまでのプランを決めるようにして。**」

    **この道具は「どの帯でも届きません」で終わっていました。**
    `data/eta.jsonl` の29点とも同じ行で終わっていて、**日付が1つも出ていません。**
    それは診断であって予測ではありません。そして診断で終わるので、
    次の回は「では何をするか」を毎回いちから決め直していました
    （`retro.py` の縦読み: 直近5回とも「何を出すか決めるところ」が最大の時間食い）。

    **なぜ「届かない」が出ていたか。** 天井の表は
    `1本あたり再生 × 92本/日 × 30日` で、この 92 は **API の日枠**であって
    出せる本数ではありません（08/19 の実測は 28本で閉じた）。そして長尺の帯は
    **実測 2回/本**（n=5・登録者9人・配信ゼロの頃）で割っていました。
    **上振れの本数と、下振れの1本あたりを、同時に当てていた**わけです。

    ここは逆に組みます。**出せる密度（既定 25本/日）で、目標に要る
    「1本あたり再生」を解き、それをショートの実測で割る。**
    ショートの1本あたりは、この機械が持つ**唯一の当てになる実測**です。

    返すのは段の並びで、**最後の段には必ず日付が入ります。**
    未測定の入力があるときは、その1つを `blocking` に名指しして
    「これを測れば期日が決まる」と言う形にします（**空で返さない**）。
    """
    per_video = a["per_video_now"]
    monthly_slots = density * 30

    # --- どの形で月20万を取りに行くか（**下振れの RPM で比べる**）---
    forms: dict[str, dict] = {}
    for form, band in PLAN_BAND_BY_FORM.items():
        need_month = a["views_needed_month"][band]
        need_per_video = need_month / monthly_slots if monthly_slots else float("inf")
        forms[form] = {
            "band": band,
            "rpm": RPM_SCENARIOS[band],
            "views_needed_month": need_month,
            "per_video_needed": need_per_video,
            # **物差しはショートの実測**。長尺の実測（2回）で割ると、
            # 「登録者9人の頃に出した5本」が計画の分母になります（M20）。
            "ratio_vs_shorts": (need_per_video / per_video) if per_video else float("inf"),
        }
    spine = min(forms, key=lambda f: forms[f]["ratio_vs_shorts"])
    sp = forms[spine]

    # --- 段1: 門1（登録者1,000人）。**実測のあるショートで開ける** ---
    d_gate1 = a["days_subs_at"].get(density, NEVER)

    # --- 段2: 門2a（長尺4,000時間）。段1と**並行**。合格点は1本あたり再生 ---
    #     いちばん甘い形（尺が長く維持率が高い）を取る。**本数は決められる／
    #     決められないのは1本あたり再生のほう**なので、そちらを解いて出す。
    rows = _long_break_even(a)
    per_day_long = max(LONG_PER_DAY_SCENARIOS)
    best = min(rows, key=lambda r: r["views"][per_day_long])
    gate2_bar = best["views"][per_day_long]

    # --- 段3: 収益化の審査 ---
    d_monetized = d_gate1 + MONETIZE_REVIEW_DAYS if d_gate1 < NEVER else NEVER

    # --- 段4: 月20万 ---
    #     収益化した時点で段4の合格点を満たしていれば、その日が到達日。
    d_target = d_monetized

    stages = [
        {
            "no": 1, "lever": "density", "when": d_gate1,
            "title": f"門1（登録者1,000人）を、実測のあるショートで開ける",
            "bar": (f"1日{density}本 公開 ＝ 再生 {density * per_video:,.0f}／日"
                    f" × 登録率 {a['sub_rate'] * 100:.4f}% ＝ 1日 {density * per_video * a['sub_rate']:,.1f}人"),
            "measured": True,
        },
        {
            "no": 2, "lever": "rpm", "when": d_gate1,
            "title": f"門2a（長尺4,000時間）を、段1と並行で開ける",
            "bar": (f"長尺を1日{per_day_long}本・{best['label']} で出し、"
                    f"**1本あたり {gate2_bar:,.0f}回**（ショート実測の {gate2_bar / per_video:.2f}倍）"),
            "measured": False,
        },
        {
            "no": 3, "lever": "none", "when": d_monetized,
            "title": f"収益化の審査（公表「通常1か月以内」＝ {MONETIZE_REVIEW_DAYS}日と置く）",
            "bar": "門1・門2a の両方を満たしたら申請。**待つだけの段**",
            "measured": False,
        },
        {
            "no": 4, "lever": "rpm", "when": d_target,
            "title": f"月20万に到達（{sp['band']}・RPM ¥{sp['rpm']:,}）",
            "bar": (f"1日{density}本 × **1本あたり {sp['per_video_needed']:,.0f}回**"
                    f" ＝ 月 {sp['views_needed_month']:,.0f}回"
                    f"（ショート実測 {per_video:,.0f}回 の **{sp['ratio_vs_shorts']:.2f}倍**）"),
            "measured": False,
        },
    ]

    # --- 段取り全体を止めている「まだ測っていない入力」を1つ名指しする ---
    #     **計画を空にしない**ための欄です。ここが埋まっていれば、
    #     次の回は「何をするか」を決め直さずに、この1手から始められます。
    lpv = a.get("long_per_video")
    n_long = a.get("long_videos_28d", 0)
    if spine.startswith("長尺") and (lpv is None or n_long < 20):
        blocking = {
            "what": "長尺の1本あたり再生",
            "now": (f"{lpv:,.0f}回（n={n_long}・登録者が9人だった頃の標本）"
                    if lpv is not None else "測っていない"),
            "need": f"{sp['per_video_needed']:,.0f}回（段4）／{gate2_bar:,.0f}回（段2）",
            "how": "長尺を出して、公開から48時間おいた本で測り直す",
            "why": ("段2・段4 の期日がこの1つに乗っている。"
                    "ショートは952回出ているので、要るのはその"
                    f"{sp['ratio_vs_shorts']:.2f}倍。**まだ一度も測り直していない**"),
            "targets": measure_targets(today or today_jst()),
        }
    else:
        blocking = {
            "what": "段1の登録率",
            "now": f"{a['sub_rate'] * 100:.4f}%",
            "need": "据え置きでよい（段1は実測だけで立っている）",
            "how": "1日25本の公開を保つ",
            "why": "段取りの入力に、未測定のものが無い",
            "targets": None,
        }

    return {
        "density": density, "spine": spine, "spine_band": sp["band"],
        "forms": forms, "stages": stages, "blocking": blocking,
        "days_to_target": d_target,
    }


def _report_plan(m: dict, a: dict) -> list[str]:
    """**この節を、いちばん最後に出すこと**（`main()` が `_drift` / `levers` の後に呼ぶ）。

    ここより後ろに「届きません」を置かないこと —— 読み手が最後に見るものが
    そのまま次の回の入口になります（オーナー指示 2026-08-20 06:2x）。
    """
    out: list[str] = []
    P = out.append
    pl = plan(m, a)
    d = pl["density"]

    P("")
    P("=" * 66)
    P("=== **月20万に到達するまでの段取り**（予測を「届きません」で終わらせない）===")
    P("=" * 66)
    P(f"  **出せる密度で解いています: 1日 {d}本 公開**（92本は API の日枠であって、"
      "出せる本数ではありません）")
    P(f"  **物差しはショートの実測 {a['per_video_now']:,.0f}回/本**"
      "（この機械が持つ唯一の当てになる1本あたり）")
    P("")
    P("--- どの形で取りに行くか（**その形のいちばん低い RPM で比べる**）---")
    for form, f in pl["forms"].items():
        mark = " ← **これで立てる**" if form == pl["spine"] else ""
        P(f"    {form:<8} RPM ¥{f['rpm']:>5,}  月 {f['views_needed_month']:>10,.0f}回 要る"
          f"  → 1本あたり **{f['per_video_needed']:>7,.0f}回**"
          f"（ショート実測の {f['ratio_vs_shorts']:>5.2f}倍）{mark}")
    P("")
    P("--- 段取り（**最後の段に日付が入るまでが1つの予測**）---")
    for st in pl["stages"]:
        P(f"    段{st['no']}［腕 {st['lever']}］{st['title']}")
        P(f"        期日: {_fmt_days(st['when'])}")
        P(f"        合格点: {st['bar']}")
    P("")
    P(f"  → 月20万の到達見込み: {_fmt_days(pl['days_to_target'])}")
    P(f"     （{pl['spine_band']}・1日{d}本・審査{MONETIZE_REVIEW_DAYS}日を置いた線）")
    P("")
    b = pl["blocking"]
    P("--- **この段取りを止めている、まだ測っていない入力は1つです** ---")
    P(f"    {b['what']}")
    P(f"      いま: {b['now']}")
    P(f"      要る: {b['need']}")
    P(f"      測り方: {b['how']}")
    P(f"      なぜここか: {b['why']}")
    t = b.get("targets")
    if t:
        P("")
        P("      **いつ答えが返るか**（公開 → 伸びきる 48時間 → Analytics 3日遅れ）:")
        P(f"        いちばん早く予約できる日 **{t['soonest']}** に置く"
          f" → 読めるのは **{t['answer_soonest']}**")
        if t["hole"]:
            P(f"        いちばん近い「予約0本の日」 {t['hole']} に置く"
              f" → 読めるのは {t['answer_hole']}"
              f"（**{t['days_lost']}日 遅い**）")
            if t["days_lost"] > 0:
                P("        [!] **穴埋めと測定を同じ `--date` で兼ねないこと。**"
                  " 穴はいつ埋めても同じですが、")
                P(f"            測定は遅らせたぶんだけ段取り全体が遅れます"
                  f"（この差が **{t['days_lost']}日**）。")
                P("            **穴は別の回に、ショートで埋めること。**")
        else:
            P("        予約0本の日はありません（穴埋めと測定が競合しません）")
    P("")
    P("  **この回の一手は、上の1行を測ることです。** 測れない窓（日枠が閉じている等）なら、")
    P("  **測れる窓に入ってすぐ撃てる形まで用意してから畳むこと。**")
    return out


def _report_long_gate(m: dict, a: dict) -> list[str]:
    """**門2a を長尺で開けるなら、長尺1本に何回の再生が要るか。**

    ここが無い間、この道具は門2について「届きません」しか言えませんでした。
    **その「届きません」は、長尺の実力ではなく「長尺を1本も出していない」ことの
    言い換え**です（`days_long_hours` は直近365日の伸びを延ばした数なので、
    伸びが0なら必ず無限になる）。**別の命題を同じ字で書いていました。**
    """
    out: list[str] = []
    P = out.append
    days = a["days_subs_at"][PLAN_PUBLISH_PER_DAY]
    P("")
    P("--- **門2a（長尺4,000時間）を、長尺を足して開けるなら** ---")
    P(f"    門2b（ショート90日1,000万）は、**1日92本の上限まで出しても"
      f"{a['shorts_needed_per_day']:,.0f}回/日に対し {a['per_video_now'] * UPLOAD_CAP_PER_DAY:,.0f}回/日"
      f" ＝ {a['per_video_now'] * UPLOAD_CAP_PER_DAY / a['shorts_needed_per_day']:.2f}倍**。門2a のほうを見ます。")
    P(f"    残り {a['long_minutes_needed']:,.0f}分（{a['long_minutes_needed']/60:,.0f}時間）を、"
      f"**門1 が通る日（1日{PLAN_PUBLISH_PER_DAY}本公開で {_fmt_days(days)}）までに**埋める。")
    P("")
    P("    **要る「長尺1本あたり再生」**（長尺を1日L本足したとき。**これが合格点**）:")
    P(f"      {'形（推測）':<18}{'1再生の視聴分':>12}" + "".join(f"{'L=' + str(n) + '本/日':>12}" for n in LONG_PER_DAY_SCENARIOS))
    for r in a["long_break_even"]:
        cells = "".join(
            (f"{r['views'][n]:>11,.0f}回" if r["views"][n] < 10 ** 6 else f"{'届かない':>12}")
            for n in LONG_PER_DAY_SCENARIOS
        )
        P(f"      {r['label']:<18}{r['min_per_view']:>10.1f}分" + cells)
    P("")
    P(f"    いまショートは **1本 {a['per_video_now']:,}回**（実測）。")
    lpv = a.get("long_per_video")
    if lpv is None:
        P("    長尺の1本あたり再生は**測れていません**（直近28日に長尺の再生が0本）。"
          "**上の数字は、その未知に対する合格点です。**")
    else:
        # **ここは「未測定」と書いてありました**（2026-08-19 14:2x に直した）。
        # 実際には直近28日に長尺が n 本ぶん再生されていて、**測れています。**
        # 「未測定」と書いてあるかぎり、この表は誰とも突き合わされません。
        P(f"    **長尺の1本あたり再生は測れています: 1本 {lpv:,}回**"
          f"（直近28日・n={a['long_videos_28d']}・合計 {a['long_views_28d']:,}回）。"
          "**上の合格点と、いま突き合わせます:**")
        worst = None
        for shape in a["long_break_even"]:
            for per_day in LONG_PER_DAY_SCENARIOS:
                need = shape["views"][per_day]
                if need == float("inf"):
                    continue
                short_by = need / lpv if lpv else float("inf")
                if worst is None or short_by < worst[0]:
                    worst = (short_by, shape["label"], per_day, need)
        if worst:
            short_by, label, per_day, need = worst
            P(f"    **いちばん甘い行でも {label}・L={per_day}本/日 で {need:,.0f}回 ＝ "
              f"実測の {short_by:,.0f}倍**。全部の行を下回っています。")
        P(f"    **これは「長尺では開かない」ではありません**（M20）。n={a['long_videos_28d']} で、"
          f"登録者 {m['subs_net']} 人のチャンネルに出した本の数です。"
          "**決まったのは「いまのままでは開かない」**で、段2 が測るのは"
          f"**1本あたりを {lpv:,}回 から何倍にできるか**のほうです。")
    if a.get("long_per_video") is None:
        P("    **長尺を出したら、この表の1行と突き合わせること。** 下回るなら長尺では開きません。")
    return out


def _levers(m: dict, a: dict) -> list[tuple[str, str, str]]:
    """門1（登録者1,000人）を1年以内に通すのに、各数字が何倍要るか。"""
    rows = []
    need_subs_per_day = a["subs_remaining"] / 365
    if a["subs_per_day"] > 0:
        x = need_subs_per_day / a["subs_per_day"]
    else:
        x = float("inf")
    rows.append(("登録者／日（門1を1年で）", f"{a['subs_per_day']:.2f}人", f"{need_subs_per_day:.2f}人 ＝ **{x:,.0f}倍**"))
    rows.append(("　うち 登録率", f"{a['sub_rate']*100:.4f}%",
                 f"{a['sub_rate']*100*x:.3f}%（再生数を据え置くなら）"))
    rows.append(("　うち 再生／日", f"{a['views_per_day']:,.0f}回",
                 f"{a['views_per_day']*x:,.0f}回（登録率を据え置くなら）"))
    per_day_cap = a["per_video_now"] * UPLOAD_CAP_PER_DAY
    rows.append(("本数だけで届く上限", f"{a['views_per_day']:,.0f}回／日",
                 f"{per_day_cap:,.0f}回／日（92本の上限。**{per_day_cap/max(a['views_per_day'],1):,.1f}倍まで**）"))
    return rows


#: 実データが動いたかを見る鍵。**予測の入力そのものだけ**を並べること。
#: 派生値（`days_*`・天井）を混ぜると、こちらの計算式を変えただけで「動いた」になります。
_INPUT_KEYS = ("views_7d", "views_28d", "views_90d", "views_all",
               "subs_net", "subs_gained_28d", "long_hours_365", "shorts_views_90d")


def _same_inputs(a: dict, b: dict) -> bool:
    """2つの点で、**実測の入力が1つも動いていない**か。"""
    return all(a.get(k) == b.get(k) for k in _INPUT_KEYS)


def _drift(current: dict) -> list[str]:
    """前の回の予測と比べる。**近づいていないなら、その回の作業は効いていない。**"""
    if not LOG.exists():
        return ["", "  （前の点がありません。次の回からは、この行に「何日ぶん縮んだか」が出ます）"]
    points = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                points.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not points:
        return []
    prev = points[-1]

    # **実データが動いていない回では、差を「効いていない」と読まないこと**
    # （2026-08-19 21:2x に、18点ぶんを数えて直した）。
    #
    # Analytics は**日次で、3日遅れ**です。回は約41分ごとに回るので、
    # **1日のうちに入力は1度も動きません。** 実際 `data/eta.jsonl` の18点は
    # `views_7d` も `subs_net` も**全部同じ値**でした。それでもここは毎回
    # 「**作業で縮んだぶん -0.0日 ← 効いていません**」と印字していました ——
    # **その回が何をしたかと無関係に、常に同じ字**です。
    #
    # 「効いていません」を毎周見せられた側が、日付を動かす作業から離れていくのは
    # 自然です。**だから、動いていないときは「測れない」と言うこと。**
    # 比べる相手も、**入力が実際に違う最後の点**にします（同じ値どうしを引いても
    # 0 しか出ません）。
    stale = _same_inputs(points[-1], current)
    older = next((p for p in reversed(points) if not _same_inputs(p, current)), None)
    if stale and older is not None:
        prev = older
    out = ["", "--- 前の回からの差（**縮んでいないなら、その回の作業は日付を動かしていない**）---"]
    if stale:
        span = ""
        try:
            hours = (datetime.fromisoformat(current["at"])
                     - datetime.fromisoformat(points[-1]["at"])).total_seconds() / 3600
            span = f"（前の点は {hours:.1f}時間前。そこから実データは1つも動いていません）"
        except (ValueError, KeyError):
            pass
        out.append(f"    [!] **実データがまだ動いていません**{span}")
        out.append("        Analytics は**日次で3日遅れ**。回はそれよりずっと速く回るので、"
                   "**この回の作業が効いたかは、ここでは測れません。**")
        out.append("        **「効いていない」ではありません。** 下の差は、"
                   + ("入力が最後に違った点との比較です。" if older is not None
                      else "比べられる点がまだありません。"))
        if older is None:
            out.append("    → いま1周ごとに測れるのは、**どの腕を選んだか**のほうです（下）。")
            # **物差しの断りは、この道でも出すこと**（2026-08-19 21:2x に検査が落ちて気づいた）。
            # 物差しの取り替えは**実データが動かなくても起きます**（こちらの計算式の話なので）。
            # 早い return で落とすと、**入力が同値の日にかぎって断りが消えます** ——
            # 取り替えの直後はまさにその形（同じ日に積み直す）なので、いちばん要る回で黙ります。
            out.extend(_scale_note(prev, current))
            return out
    pd_ = prev.get("days_monetized")
    cd = current["days_monetized"]
    if pd_ is None:
        return out
    try:
        elapsed = (datetime.fromisoformat(current["at"]) - datetime.fromisoformat(prev["at"])).total_seconds() / 86400
    except (ValueError, KeyError):
        elapsed = 0.0
    if pd_ >= NEVER and cd >= NEVER:
        out.append("    収益化まで: **どちらも「届かない」**。**律速はまだ1つも動いていません。**")
    elif pd_ >= NEVER:
        out.append("    収益化まで: 「届かない」→ " + _fmt_days(cd) + "  **道が開きました**")
    elif cd >= NEVER:
        out.append("    収益化まで: " + _fmt_days(pd_) + " → **「届かない」に戻りました**")
    else:
        # 何もしなければ、経過したぶんだけ縮む。それ以上縮んだぶんが「効いた」ぶん。
        gained = (pd_ - cd) - elapsed
        out.append(f"    収益化まで: {pd_:,.0f}日 → {cd:,.0f}日（{elapsed:.2f}日 経過）")
        out.append(f"    **作業で縮んだぶん: {gained:+,.1f}日**"
                   + ("  ← 効いています" if gained > 0.5 else "  ← **効いていません**"))
    # **収益化が「届かない」のままだと、上の3行は何周でも同じ字を出します。**
    # 動いている所が見えないので、門1（いまの律速）の日数も並べます。
    if prev.get("days_subs") and current.get("days_subs"):
        pds, cds = prev["days_subs"], current["days_subs"]
        if pds < NEVER and cds < NEVER:
            gained = (pds - cds) - elapsed
            out.append(f"    門1（登録者1,000人）: {pds:,.0f}日 → {cds:,.0f}日"
                       f"  **作業で縮んだぶん {gained:+,.1f}日**")
    for key, label in (("views_per_day", "再生／日"), ("sub_rate", "登録率"), ("per_video_now", "1本あたり再生")):
        if key in prev and prev[key]:
            now = current.get(key, 0)
            if now:
                out.append(f"    {label}: {prev[key]:,.4g} → {now:,.4g}（{(now/prev[key]-1)*100:+.1f}%）")
    # **物差しを取り替えた回は、その差を「悪くなった」と読まないこと**（2026-08-19 15:0x）。
    # 9点目までの `per_video_now` は「30再生の床つきの中央値」、10点目からは
    # 「床なしの平均」です。**チャンネルは何も変わっていないのに 1,092 → 869 と出ます。**
    # 差の節は「作業が効いたか」を見る所なので、ここで断らないと
    # **物差しの取り替えが、実績の悪化として next の判断に入ります。**
    out.extend(_scale_note(prev, current))
    return out


def _scale_note(prev: dict, current: dict) -> list[str]:
    """**物差しを取り替えた回は、その差を「悪くなった」と読ませない。**

    **向きは両方あります**（2026-08-20 03:1x に足した）。取り替えは
    悪くなる側にも良くなる側にも出るので、**良くなった側でも断ること** ——
    断らないと、次の回が **+9.6% を「この回の作業が効いた」と読みます。**
    """
    out: list[str] = []
    if prev.get("views_per_video") is None and current.get("views_per_video") is not None:
        out += ["    [!] **1本あたり再生の物差しが、この点から変わりました**"
                "（床つきの中央値 → 床なしの平均）。",
                "        **上の変化は実績ではありません。** 実績として読めるのは、次の点からです。"]
    if prev.get("per_video_dropped") is None and current.get("per_video_dropped") is not None:
        out += ["    [!] **1本あたり再生の標本が、この点から変わりました**"
                "（予約のまま公開していない本・公開から48時間未満の本・28日の窓より前の本を落とした）。",
                "        **上の変化は実績ではありません**（実測 869 → 952 ＝ +9.6%）。"
                " 実績として読めるのは、次の点からです。"]
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="月20万に届く日を予測して積む")
    ap.add_argument("--no-record", action="store_true", help="data/eta.jsonl に積まない")
    ap.add_argument("--offline", action="store_true", help="API を叩かず、積んである最後の点から出す")
    args = ap.parse_args()

    if args.offline:
        if not LOG.exists():
            print("[eta] 積んだ点がありません。--offline は使えません。")
            return 1
        m = json.loads([l for l in LOG.read_text(encoding="utf-8").splitlines() if l.strip()][-1])
        print("[eta] **積んである最後の点で出しています（いまの実測ではありません）**")
    else:
        try:
            m = _measure()
        except Exception as exc:  # noqa: BLE001 — 予測で回を止めない
            print(f"[eta] 実測を取れませんでした: {type(exc).__name__}: {exc}")
            print("[eta] **回は止めないこと。** `--offline` で最後の点から読めます。")
            return 1

    a = analyse(m)
    m["per_video_now"] = a["per_video_now"]
    for line in report(m, a):
        print(line)
    row = {**m, **{k: v for k, v in a.items() if isinstance(v, (int, float))}}
    for line in _drift(row):
        print(line)
    # **「予測 → 腕を選ぶ → 進む」の、選んだ側の実績**（オーナー指示 2026-08-19 21:2x）。
    # 1周ごとに動くのは日付ではなく**ここ**です（`src/levers.py` の説明）。
    for line in levers.report(ROOT / "data" / "runs.jsonl"):
        print(line)
    # **段取りは、いちばん最後に出すこと**（オーナー指示 2026-08-20 06:2x）。
    # 読み手が最後に見たものが、そのまま次の回の入口になります。
    # ここより後ろに「届きません」を置かないこと。
    for line in _report_plan(m, a):
        print(line)

    if not args.no_record:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\n[eta] 積みました: {LOG.relative_to(ROOT)}（{sum(1 for _ in LOG.open(encoding='utf-8'))}点目）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
