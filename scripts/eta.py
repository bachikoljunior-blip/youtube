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
import os
import sys
from collections import deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import arm_speed, day_cap, levers, rpm_mix  # noqa: E402  （`sys.path` を通した後でないと読めません）

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

# --- 「月20万」は**流量ではなく、30日ぶんの合計**です（2026-08-20 08:1x に足した）---
#
# ここが無かったので、段4 の期日に **段3（収益化の審査が終わる日）をそのまま代入**
# していました（`d_target = d_monetized`）。印字は「月20万の到達見込み」ですが、
# **中身は収益化の日付**です —— オーナー追記（原文）:
#
#   > 勝手に20万達成以外の日時の予測だけにしないで
#
# 収益化した日に入るのは**その日ぶんの収入**であって、月20万ではありません。
# 月20万を名乗れるのは、**収益化してから30日ぶん積んだ合計**が20万を超えた日です。
# 収益化前の再生は1円も生まないので、この30日は前借りできません。
REVENUE_WINDOW_DAYS = 30

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
    # **JST で数えること。** この器は UTC なので `date.today()` を使うと、
    # 日本時間の朝9時までのあいだ **1日ずれた日付**を印字します。
    # `headline` は `today_jst()` で作るので、そこと1日ちがう字が並びます。
    when = today_jst() + timedelta(days=math.ceil(days))
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


# --- 到達日を「解く」ための道具（2026-08-20 08:0x。**オーナー指示3回目**）---
#
# > 「20万達成までのプランを作って**達成日時を予測**して、
# >   毎回達成日時を早めることを考えてから進めるようにして」
#
# **段4（月20万）の期日は、8/20 まで `d_monetized` の写しでした。**
# つまり「収益化が終わる日」を「20万に届く日」として印字していた。
# 合格点（1本あたり◯回）は別に書いてあるのに、**それを満たす日を解いていません。**
# 写しである以上、per_video を10倍にしても RPM を5倍にしても**日付は1日も動きません** ——
# 「早めることを考えてから進めろ」という指示が、**動かない数字に向かって出されていました。**
#
# ここで解くのは次の1本です。
#
#     直近30日の再生数(d) ÷ 1000 × RPM ≧ 200,000円
#
# 未知は「再生数がどう伸びるか」だけなので、**伸び率を実測から出して**
# 上の不等式を満たす最初の日 d を探します（`solve_revenue_day`）。
# 天井（1日あたり出せる本数 × 1本あたり再生）で頭を打つので、
# **届かない帯は「届かない」と出ます** —— そこは伸び率の問題ではなく形の問題です。

#: 7日窓の重心は 3.5日前、28日窓の重心は 14日前。**差は 10.5日**。
#: 2つの窓の比を、この日数ぶんの複利として読みます。
WINDOW_CENTROID_GAP_DAYS = 10.5

#: `data/eta.jsonl` の履歴から伸び率を測るのに要る最小の期間（日）。
#: **これより短い履歴で測ると、Analytics の3日遅れと同じ幅のノイズを伸び率と読みます。**
GROWTH_MIN_SPAN_DAYS = 7.0

#: 「何を何倍にすれば何日後か」を出すときの、期日の候補（今日からの日数）。
GROWTH_HORIZONS = (30, 60, 90, 180, 365)

#: 伸び率を探すときの上限（1日で倍。**これを超える伸びは、探しても意味がない**）。
GROWTH_SEARCH_MAX = 1.0


def growth_per_day(m: dict, points: list[dict] | None = None) -> dict:
    """**再生数の1日あたり複利の伸び率**を実測から出す。

    出どころは2つあり、**長いほうを優先**します。

    1. `data/eta.jsonl` の履歴（`views_per_day` の最初と最後）。
       ただし **7日ぶん貯まってから**（それ未満だと Analytics の3日遅れが
       そのまま伸び率に化けます）
    2. **いま持っている2つの窓の比**（直近7日／直近28日）。重心の差 10.5日ぶんの
       複利として読む。**履歴が無い日でも必ず出る**のが利点で、
       欠点は**公開本数を増やしている最中の伸びが混ざる**こと（＝上振れ側）

    返すのは `{"g": 1日あたり, "basis": どちらで測ったか, "span_days": 期間, "caveat": 断り}`。
    **測れないときは `g=None`**（0 と区別すること。0 は「伸びていない」、
    None は「まだ言えない」）。
    """
    v7 = m.get("views_7d", 0) / 7 if m.get("views_7d") else 0.0
    v28 = m.get("views_28d", 0) / 28 if m.get("views_28d") else 0.0

    if points:
        rows = [p for p in points if p.get("views_per_day")]
        if len(rows) >= 2:
            try:
                t0 = datetime.fromisoformat(rows[0]["at"])
                t1 = datetime.fromisoformat(rows[-1]["at"])
                span = (t1 - t0).total_seconds() / 86400
            except (KeyError, ValueError):
                span = 0.0
            a0, a1 = rows[0]["views_per_day"], rows[-1]["views_per_day"]
            if span >= GROWTH_MIN_SPAN_DAYS and a0 > 0 and a1 > 0:
                return {
                    "g": (a1 / a0) ** (1 / span) - 1,
                    "basis": f"履歴（`data/eta.jsonl` の {len(rows)}点・{span:.1f}日）",
                    "span_days": span,
                    "caveat": "公開本数を増やしている最中の伸びが混ざります（＝上振れ側）",
                }

    if v7 > 0 and v28 > 0:
        return {
            "g": (v7 / v28) ** (1 / WINDOW_CENTROID_GAP_DAYS) - 1,
            "basis": f"2つの窓の比（直近7日 {v7:,.0f}／日 ÷ 直近28日 {v28:,.0f}／日）",
            "span_days": WINDOW_CENTROID_GAP_DAYS,
            "caveat": ("**公開本数を増やしている最中の伸びが混ざります**（＝上振れ側）。"
                       f"履歴が {GROWTH_MIN_SPAN_DAYS:.0f}日ぶん貯まったら、そちらに切り替わります"),
        }

    return {"g": None, "basis": "測れません（窓に再生がありません）",
            "span_days": 0.0, "caveat": ""}


def solve_revenue_day(views_day_now: float, growth: float | None,
                      ceiling_views_day: float, need_month: float,
                      horizon: int = 3_650) -> float:
    """**直近30日の再生数が `need_month` に達する最初の日**（今日を0日目）。

    `views_day_now` から複利 `growth` で伸ばし、**天井 `ceiling_views_day` で頭打ち**。
    天井のままで30日ぶんが足りないなら `NEVER`（＝**伸び率の問題ではなく形の問題**。
    そこで要るのは「もっと待つ」ではなく「1本あたり再生か RPM か密度を変える」）。

    **なぜ「その日の再生数」ではなく「直近30日の合計」で見るか。**
    月20万は**月の収入**なので、その水準の日が1日来ても届きません。
    伸びている最中は、日次が達したあとに合計が追いつきます —— その差を無視すると、
    **到達日が数日から数週間ぶん早く出ます。**

    ## **時間の頭打ちは入れません。頭打ちは `ceiling_views_day` のほうです**

    2026-08-20 20:0x に「伸び率を測った窓（10.5日）の先まで延ばすな」という
    指摘を受けて、**実際に入れて測りました。結果は入れないほうが正しい**です。

    伸び率は「天井へ**どれだけ速く**近づくか」しか決めていません。**水準を
    決めているのは天井**（密度 × 1本あたり再生）で、`v = min(v * (1 + growth), cap)`
    が毎日それを当てています。だから「1日5.38%を100日 ＝ 180倍」は**起きません**
    （実測では 56日目に天井に着いて、そこで止まります）。
    伸び率に時間の頭打ちを足すと、**天井と二重に縛る**ことになり、
    `plan()` は入力を問わず `NEVER` を返しました（検査10件が落ちた）——
    それは「**予測を届きませんで終わらせない**」（オーナー 2026-08-20 06:2x）に反します。

    **13倍の開きを埋めていたのは、伸び率ではなく天井のほうでした。**
    天井の密度が `min(25, 3.3時間の実測36.5) = 25` になっていて、
    直すと（`src.supply.MIN_SUSTAINED_HOURS`）天井は 1日 3,230回まで下がり、
    **同じ伸び率のままで到達日は「届かない」に変わります。**

    **覆る条件**: 天井が「速さ」まで決めるようになったら（例: 密度を時間の
    関数にしたら）、ここにも時間の制限が要ります。いまは天井が水準だけを
    決めているので、要りません。**`tests/test_eta_growth_ceiling.py` が
    「伸び率をいくら上げても天井×30日を超えない」を固定しています。**
    """
    if need_month <= 0:
        return 0.0
    if views_day_now <= 0:
        return NEVER
    cap = ceiling_views_day if ceiling_views_day and ceiling_views_day > 0 else float("inf")
    if cap * 30 < need_month:
        return NEVER
    v = min(views_day_now, cap)
    window = deque([v] * 30, maxlen=30)
    total = v * 30
    if total >= need_month:
        return 0.0
    if not growth or growth <= 0:
        return NEVER
    for d in range(1, horizon + 1):
        v = min(v * (1 + growth), cap)
        total += v - window[0]
        window.append(v)
        if total >= need_month:
            return float(d)
    return NEVER


def required_growth(views_day_now: float, ceiling_views_day: float,
                    need_month: float, days: int) -> float | None:
    """**その日までに届かせるには、1日あたり何%の伸びが要るか。**

    届かせられないなら `None`（＝天井が足りない。**伸び率をいくら上げても無駄**）。
    予測が「届きません」で終わらないための逆算です（オーナー指示 2026-08-20 06:2x）。
    """
    if days <= 0:
        return None
    if ceiling_views_day * 30 < need_month:
        return None
    if solve_revenue_day(views_day_now, GROWTH_SEARCH_MAX, ceiling_views_day, need_month) > days:
        return None
    lo, hi = 0.0, GROWTH_SEARCH_MAX
    for _ in range(60):
        mid = (lo + hi) / 2
        if solve_revenue_day(views_day_now, mid, ceiling_views_day, need_month) <= days:
            hi = mid
        else:
            lo = mid
    return hi


def double_days(growth: float) -> float:
    """その伸び率で、再生数が2倍になるまでの日数。**%より、こちらのほうが読める。**

    **`math.log(1 + growth)` は 0 を返します**（2026-08-20 23:3x に踏んだ）——
    `growth` が 1e-16 より小さいと `1 + growth` が浮動小数で 1.0 に丸まり、
    対数が厳密に 0 になって **`ZeroDivisionError` で回そのものが落ちます。**
    `required_growth` は「ほとんど伸びなくても間に合う」帯で、その大きさを返します。
    `log1p` なら丸まらず、それでも 0 なら **無限大（＝2倍にならない）**として返します。
    """
    if not growth or growth <= 0:
        return float("inf")
    denom = math.log1p(growth)
    return math.log(2) / denom if denom > 0 else float("inf")


#: 腕を1つだけ動かしてみるときの倍率（`lever_days`）。**1.0 が「いまのまま」**
DEFAULT_SCALE = {"per_video": 1.0, "sub_rate": 1.0, "rpm": 1.0, "density": 1.0}


def _scale(scale: dict | None) -> dict:
    sc = dict(DEFAULT_SCALE)
    for k, v in (scale or {}).items():
        if k not in sc:
            raise KeyError(f"知らない腕です: {k}（{sorted(DEFAULT_SCALE)}）")
        sc[k] = float(v)
    return sc


def analyse(m: dict, points: list[dict] | None = None,
            scale: dict | None = None) -> dict:
    """実測から、門ごとの日数と天井を出す。

    `points` は `data/eta.jsonl` の履歴（新しい順ではなく**積んだ順**）。
    **伸び率を測るためだけ**に使い、渡さなければ2つの窓の比で代用します
    （`growth_per_day`）。**渡しても渡さなくても、他の数字は1つも変わりません。**

    `scale` は「**その腕を◯倍にしたら**」を測るための倍率です（既定は全部 1.0
    ＝ いまの実測そのまま）。`lever_days` がここを使って、
    **腕べつに到達日が何日動くか**を出します —— オーナー指示（2026-08-20 16:0x）:

    > 分析して制作に活かして視聴回数などを上げることが予測に使えることじゃない？

    **`views_day_now` は倍率を掛けません。** いま出ている再生は、いま出ている数です。
    1本あたり再生を上げても、**過去に公開した本の再生数は遡って増えません** ——
    掛けると「明日から全部が2倍」を予測として印字することになります。
    倍率が効くのは**これから公開する本の側**（天井・門1の登録者）だけです。
    """
    sc = _scale(scale)
    views_day_7 = m["views_7d"] / 7
    views_day_28 = m["views_28d"] / 28
    # 予測には速いほうを使う（伸びている最中に遅いほうで測ると、悲観に倒れる）
    views_day = max(views_day_7, views_day_28)

    sub_rate = ((m["subs_gained_28d"] / m["views_28d"]) if m["views_28d"] else 0.0) * sc["sub_rate"]
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
    # **本数のうち、再生が付くぶんだけを数えます**（2026-08-21 16:2x）。
    # ここは長らく `n` をそのまま掛けていて、**25本/日 なら 25本ぶんの再生**と
    # 読んでいました。実測は違います（`src/day_cap.py`）:
    #   08/20 は 25本 公開して **#11から先の15本が 0〜3再生**。#10 は 1,111再生。
    #   時刻ではなく**その日の通し番号**で割れます（08/16 の14時 #4 は 1,361再生）。
    # つまり段1 の日付は、上限を超えて出したぶんだけ**楽観に倒れて**いました。
    a["view_cap_per_day"] = day_cap.cap()
    a["days_subs_at"] = {
        n: _days_to(a["subs_remaining"],
                    min(n, a["view_cap_per_day"]) * _per_video(m)
                    * sc["per_video"] * sub_rate)
        for n in sorted(set(PUBLISH_SCENARIOS) | {PLAN_PUBLISH_PER_DAY})
    }
    # **門1 に要る「本数」**（日数ではなく本数）。供給の側から日を解くのに要ります。
    _pv = _per_video(m) * sc["per_video"]
    a["videos_needed_gate1"] = (
        (a["subs_remaining"] / (_pv * sub_rate)) if (_pv > 0 and sub_rate > 0) else float("inf")
    )

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
    per_video = _per_video(m) * sc["per_video"]
    long_per_video = m.get("long_per_video")
    if long_per_video is not None:
        long_per_video = long_per_video * sc["per_video"]
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
    a["views_needed_month"] = {
        k: TARGET_YEN * 1000 / (rpm * sc["rpm"]) for k, rpm in RPM_SCENARIOS.items()
    }
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

    # --- 到達日を解くための入力（2026-08-20 08:0x に足した）---
    #     **ここが無い間、段4 の期日は段3 の写しでした。**
    g = growth_per_day(m, points)
    a["growth"] = g
    a["growth_per_day"] = g["g"] if g["g"] is not None else 0.0
    a["views_day_now"] = views_day
    a["scale"] = sc
    return a


def report(m: dict, a: dict) -> list[str]:
    out: list[str] = []
    P = out.append
    P("=" * 66)
    # **「RPM だけが推測」は、この道具の見出しとして正しくありませんでした**
    # （2026-08-23 にオーナーの問い「軌跡の予測は全て実測や確かな情報から
    # 導き出される妥当な可能性？」で数え直した）。**推測は少なくとも5つあります。**
    # 見出しが1つしか言わないと、読む側は残り4つを実測だと思って使います。
    P("=== 月20万円に、いつ届くか ===")
    P("  **実測**: 登録者・再生／日・登録率・視聴時間・1本あたり再生（Analytics）／"
      "腕の動く速さ（閉じた前提の実績）／1日の再生が付く本数の上限（day_cap）")
    P("  **推測**（この5つは測っていません。日付はこの上に乗っています）:")
    P(f"    1) RPM ——`RPM_SCENARIOS` の帯。ニッチで10倍変わる")
    P(f"    2) 収益化の審査 {MONETIZE_REVIEW_DAYS}日 —— YouTube の公表値。**実測ではない**")
    P("    3) 長尺の合格点 —— n=8・登録者が9人だった頃の標本")
    P("    4) 1日N本出しても1本あたりが保つか —— **未測定**（配信の壁）")
    P("    5) **日次再生の複利は入っていません** —— 実測 10.2%/日（t=2.17・有意）だが、"
      "区間が 0.96〜20.3%/日 と広く、上端は30日で破綻値になるため保留（2026-08-23）")
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


def _stage4(m: dict, a: dict, sp: dict, density: int, per_video: float,
            d_monetized: float, today: date, proxy: bool = False,
            d_revenue: float = 0.0) -> dict:
    """**月20万の期日を、20万の条件そのものから出す。段3の日を代入しない。**

    2026-08-20 08:1x・オーナー追記（原文）——

    > 勝手に20万達成以外の日時の予測だけにしないで

    **直していること。** ここは1行 `d_target = d_monetized` でした。
    段3（収益化の審査が終わる日）を段4の期日として印字していたので、
    画面の「月20万の到達見込み」は、**中身が収益化の日付**でした。
    門1（登録者1,000人）・門2a（長尺4,000時間）・審査30日 ——
    **どれも20万の日付ではありません。**

    月20万の条件は、門の条件とは形がちがいます。門は**積み上がれば通る**（累積）
    ので、速さで割れば日が出ます。20万は**その月の水準**なので、日が出るには
    2つ要ります:

        (1) 合格点が立つこと    1日に出す本数 × 1本あたり再生 × RPM が 20万に届く
        (2) その水準で30日ぶん積むこと（`REVENUE_WINDOW_DAYS`）

    (2) は収益化より前には始められません（収益化前の再生は1円も生まない）。
    **だから 段4 は、段3 + 30日 より後ろにしか来ません。** 同じ日には決してならない
    （例外は、門が「届かない」で返って下の `fallback` に落ちたとき —— そこでは
    段3 が日付を持っていないので、比べる相手そのものがありません）。

    そして (1) は**実測で立っているとは限りません。** 立っていないなら、
    「届きません」で畳まずに、**何を何倍にすれば、いつ出るのか**を返します
    （同じ追記の後半。倍率は `ratio`、その倍率が本当かを**確かめられる最短の日**が
    `verify_day` ＝ 公開の翌日 → 伸びきる48時間 → Analytics 3日遅れ）。
    """
    need_per_video = sp["per_video_needed"]
    ratio = (need_per_video / per_video) if per_video else float("inf")
    # **倍率が1を切っていても、それだけでは「立っている」と言えません。**
    #     `per_video` はショートの実測で、段4 が立てているのは長尺です。
    #     別の形の実測を当てているあいだは、合格点は**推測**です（`proxy`）——
    #     ここを見落とすと、20万の期日がまた「測っていない数字の写し」になります。
    met = (ratio <= 1.0) and not proxy

    # **倍率が本当かを確かめられる最短の日**（今日からの日数）。
    # 段4 は、確かめる前に来ることはありません —— 立っていない合格点の上に
    # 期日を置くと、それは予測ではなく願望になります。
    #     **日付そのものを持たせます**（`_fmt_days` は TZ を持たない `date.today()`
    #     ＝ UTC に足すので、JST の 00:00〜09:00 は1日ずれた日を印字します）。
    verify_on = answer_day(today + timedelta(days=1))
    verify_day = float((verify_on - today).days)

    # --- 合格点が立つ日 ---
    #
    # **`d_revenue` が入るまで、ここは「収益化の日」か「確かめる日」でした**
    # （2026-08-20 08:3x の版。同じ回の申し送りに「**要る倍率が上がっても日数は
    # 動かない（1本あたり再生の伸び率を持っていないため）**」と書いてあります）。
    # いまは伸び率を実測して解いた日が入ります（`solve_revenue_day`）——
    # **倍率が上がれば、この日が後ろへ動きます。**
    bar_day = max(d_revenue, d_monetized if met else max(d_monetized, verify_day))

    # --- 門が「届かない」で返ってきたときも、日付を1つ出す ---
    #     `days_subs_at` が NEVER になるのは、**登録が28日で0件**のとき（0で割る）。
    #     倍率では出ません（0 を何倍しても 0）。**出るのは「1人でも出れば」のほう**なので、
    #     28日に1人の線（＝この機械が観測しうる最小の非ゼロ）で引き直します。
    #     **見るのは門のほう**（`d_monetized`）です。`bar_day` で見ると、
    #     再生数の側が「届かない」でも門の引き直しが走り、**関係のない仮定で
    #     日付が出ます**（引き直しても再生数は届かないままなので、意味がない）。
    fallback = None
    if d_monetized >= NEVER:
        views_28d = m.get("views_28d") or 0
        rate_min = (1.0 / views_28d) if views_28d else 0.0
        subs_day = density * per_video * rate_min
        d1 = _days_to(a["subs_remaining"], subs_day)
        if d1 < NEVER:
            d_monetized = d1 + MONETIZE_REVIEW_DAYS
            bar_day = max(d_revenue, d_monetized if met else max(d_monetized, verify_day))
            fallback = {
                "why": "登録が28日で0件なので、いまの実測では門1が開きません",
                "assume": (f"**28日に1人でも登録が出れば**（登録率 {rate_min * 100:.4f}%"
                           f" ＝ この機械が観測しうる最小の非ゼロ）"),
                "gate1_days": d1,
            }

    # --- ②の30日は前借りできない ---
    #     **ただし `d_revenue` に足さないこと。** あちらは「直近30日の合計」が
    #     必要量に達する日なので、**30日ぶんの積み上げを既に含んでいます。**
    #     足すと二重に数え、到達日が1か月ぶん遠くなります。
    #     前借りできないのは**収益化より前の再生**のほうなので、床はこの2つ:
    gate_floor = d_monetized + REVENUE_WINDOW_DAYS if d_monetized < NEVER else NEVER
    verify_floor = (verify_day + REVENUE_WINDOW_DAYS) if (not met) else 0.0
    floor = max(gate_floor, verify_floor)
    when = max(d_revenue, floor) if (d_revenue < NEVER and floor < NEVER) else NEVER

    return {
        "when": when,
        "floor": floor, "gate_floor": gate_floor, "verify_floor": verify_floor,
        "d_revenue": d_revenue,
        "bar_day": bar_day,
        "verify_day": verify_day, "verify_on": verify_on,
        "ratio": ratio,
        "met": met,
        "need_per_video": need_per_video,
        "per_video_now": per_video,
        "window": REVENUE_WINDOW_DAYS,
        # **条件つきの日付であることを、道具の側が持っておく**（画面で断るため）。
        # 満たしていない合格点の上に立っているなら、それは「最早」であって見込みではない。
        "conditional": (not met) or fallback is not None,
        "fallback": fallback,
        "proxy": proxy,
    }


#: 腕を1つだけ「これだけ上げたら」と置いてみる倍率。**2倍は、この機械が
#: 実際に出した幅の中にあります**（1本あたり再生の実測は 22本で 30回〜4,000回超）。
LEVER_FACTOR = 2.0

#: 到達日を動かしうる腕。**`none`（道具の整備）はここには入りません** ——
#: 日付を動かさないと自分で言っている腕なので、比べる意味がありません。
LEVERS = ("per_video", "sub_rate", "rpm", "density")

LEVER_LABEL = {
    "per_video": "1本あたり再生（分析→制作に反映）",
    "sub_rate": "登録率（終端の作り・シリーズ化）",
    "rpm": "RPM（ニッチ・尺・形式）",
    "density": "作る速さ（節を書く／出す）",
}


def lever_days(m: dict, a: dict, pl0: dict, today: date | None = None,
               supply: dict | None = None, points: list[dict] | None = None,
               factor: float = LEVER_FACTOR, mix: dict | None = None) -> list[dict]:
    """**腕べつに、到達日が何日動くか。**（2026-08-20 16:0x・オーナー指示）

    > 分析して制作に活かして視聴回数などを上げることが予測に使えることじゃない？

    **予測に使えていませんでした。** 到達日の入力は
    「1日25本」「収益化の審査30日」で、**1本あたり再生は天井の表に出てくるだけ**——
    上げても下げても、印字される日付は動きませんでした。だから
    「次にどの腕を引くか」は `binding`（どの床がいちばん遅いか）という
    **診断**から決めていて、**引いた結果どれだけ縮むか**は誰も出していません。

    ここがやるのは1つだけです。**腕を1つずつ `factor` 倍にして、
    予測をまるごと解き直し、到達日の差を取る。** 差が大きい腕が、
    この回に引くべき腕です。**名前ではなく、日数で決まります。**

    返り: 腕ごとに `{"lever", "label", "days", "date", "gain", "reachable"}`。
    `gain` は**縮んだ日数**（正なら早まる）。届かない側は `gain=0.0`。

    **これは「2倍にできる」と言っていません。** 言っているのは
    「2倍にしたら何日縮むか」だけで、**できるかどうかは別の話**です。
    比べられるのは、どの腕も**同じ倍率**で並べているからです。
    """
    base = pl0.get("days_to_target", NEVER)
    rows: list[dict] = []
    for lever in LEVERS:
        try:
            a2 = analyse(m, points=points, scale={lever: factor})
            pl2 = plan(m, a2, today=today, supply=supply, sensitivity=False,
                       points=points, mix=mix)
        except Exception:                                      # noqa: BLE001
            continue
        d = pl2.get("days_to_target", NEVER)
        reachable = d < NEVER
        # **`base` が NEVER のときも、そのまま引くこと。**
        #     ここを「届く側は一律に最大」と書いていたら、**届く腕が全部同点**になり、
        #     並び順は `LEVERS` に書いた順（＝こちらの都合）で決まっていました。
        #     引き算のままなら、`NEVER - d` は **d が小さい腕ほど大きい** ので、
        #     「いまは出ない」帯でも**早く出るほうが上**に来ます。
        gain = (base - d) if reachable else 0.0
        rows.append({
            "lever": lever,
            "label": LEVER_LABEL[lever],
            "factor": factor,
            "days": d,
            "date": ((today or today_jst()) + timedelta(days=math.ceil(d)))
                    if reachable else None,
            "gain": max(0.0, gain),
            "reachable": reachable,
        })
    rows.sort(key=lambda r: -r["gain"])
    return rows


def sustained_density(supply: dict | None,
                     density: float = PLAN_PUBLISH_PER_DAY) -> float:
    """**天井を立てている密度**（1日に「続けられる」本数）を1か所で出す。

    `plan()` の `density_sustained`（`min(PLAN_PUBLISH_PER_DAY, 作る速さ)`）と
    **同じ数**です。写しではなく、同じ入口から読むために関数にしてあります。

    ## なぜ要るか（2026-08-21 01:5x に踏んだ）

    段4 の天井は `per_video × density_sustained`（実測 7.8本/日）で立ちます。
    ところが `physical_caps` は `density` の伸びしろを
    **`PLAN_PUBLISH_PER_DAY`（25本/日）で割っていました** ——
    25 は「予約を詰め直したらこうなる」という**計画の数**で、
    同じファイルが天井からは外している数です（`density_sustained` の注記）。

        天井が立っている密度   7.8本/日（実測）
        伸びしろの分母          25本/日（計画）  ← **別の数**
        → 腕は 7.8 × (92/25) ＝ **28.7本/日 で頭打ち**。実物の上限 92本/日 の **3.2分の1**

    軌跡は「腕を全部振っても出ません」と印字していましたが、その天井の
    3.2倍ぶんは**そもそも歩かせてもらえていません**でした。
    **`tests/test_eta_density_cap.py` が、分母が計画の数に戻ったら落とします。**
    """
    if supply is None:
        return float(density)
    rate = supply.get("sustained_rate_per_day")
    if rate is None:
        rate = supply.get("rate_per_day")
    if rate is None:
        return float(density)
    return min(float(density), float(rate))


def physical_caps(a0: dict, density: float = PLAN_PUBLISH_PER_DAY,
                  supply: dict | None = None) -> dict[str, dict]:
    """**腕を「実在する幅」で止める。**（軌跡が実在しない世界を歩かないため）

    最初の版はここが無く、実測の速さのまま 224日ぶん外挿して
    **`density` を ×4,421**（＝1日 110,525本）まで伸ばしていました。
    **同じ回に「1日25本」を外したばかり**で、まったく同じ欠陥です ——
    伸ばした先が満たせるかを、誰も確かめていませんでした。

    ここが返す倍率は全部**この機械の中にある数**で、出どころを併記します:

        density    `UPLOAD_CAP_PER_DAY`（92本/日・**実測**）÷ いまの密度
        rpm        `RPM_SCENARIOS` の最大（**推測の幅の上端**）÷ いま立てている帯
        sub_rate   登録率 100%（**定義上の上限**。測った天井ではありません）
        per_video  ここでは付けません（`config/hypotheses.yaml` の `ceiling` が実測で持っています）

    **`rpm` と `sub_rate` は実測の天井ではありません。** どちらも
    「これ以上は誰も主張していない」という線で、**測れば動きます**
    （`sub_rate` の実測は仮説「長尺の登録率はショートより1桁以上高い」・期限 2026-09-15）。
    """
    caps: dict[str, dict] = {}
    # **分母は「天井が立っている密度」**（`sustained_density`）。
    #     計画の 25本/日 で割ると、腕は実物の上限 92本/日 まで歩けません。
    density = sustained_density(supply, density)
    if density > 0:
        # **腕の天井は「出せる本数」ではなく「再生が付く本数」**（2026-08-21 16:2x）。
        #     ここは `UPLOAD_CAP_PER_DAY`（1日92本・**投稿の口の上限**）で割って
        #     いました。出せはします。**ただし再生は付きません** ——
        #     08/20 は 25本 公開して #11から先の15本が 0〜3再生（`src/day_cap.py`）。
        #     天井を口の側で立てると、**腕を ×3.7 まで歩けると出て、
        #     実際には1日も縮まない**という形になります。
        arm_cap = min(float(UPLOAD_CAP_PER_DAY), float(day_cap.cap()))
        raw = arm_cap / density
        # **倍率が 1 を下回るのは「引き代がマイナス」ではありません** ——
        #     **すでに上限より多く出している**、という意味です。そのまま返すと
        #     腕を 0.4倍 に「引ける」ことになり、軌跡が**密度を減らす向きに歩きます**。
        #     引き代は 0（＝×1.0 が天井）。**超えていること自体は `why` に残します。**
        over = raw < 1.0
        caps["density"] = {"factor": max(1.0, raw),
                           "why": (f"1日に再生が付く上限 {arm_cap:.0f}本（実測・`src/day_cap.py`）"
                                   f" ÷ いま続けられる {density:.1f}本/日"
                                   f"（出せる口の上限は {UPLOAD_CAP_PER_DAY}本ですが、"
                                   f"そこまで出しても再生は付きません）"
                                   + ("。**すでに上限を {:.1f}倍 超えて出しています ＝ 引き代なし**"
                                      "（超えたぶんは 0再生）".format(1 / raw) if over else "")),
                           "measured": True,
                           "at_ceiling": over}
    # --- `rpm` の天井は、2026-08-20 22:2x に**実測に入れ替えました**（`src/rpm_mix.py`）---
    #     ここには `max(RPM_SCENARIOS) / band`（¥2,000 ÷ ¥20 ＝ ×100）が入っていて、
    #     この関数の docstring 自身が「測った天井ではありません」と言っていました。
    #     入れ替えたのは**混ざり方**です —— RPM は1本に付く数ではなく
    #     「視聴分がどちらの形に何%乗っているか」で決まるので、
    #     長尺のサムネが見せられている回数（実測）より上には行けません。
    #     初測: 実効 ¥20.9 → 天井 ¥866（×41.5）。**据え置きの ×100 は 2.4倍 甘かった。**
    #     **測れていないときだけ**、前の据え置きへ落ちます（黙って落ちないよう why に出す）。
    mixed = rpm_mix.last()
    if mixed and mixed.get("factor"):
        caps["rpm"] = {"factor": float(mixed["factor"]),
                       "why": (f"実測の混ざり方 ¥{mixed.get('rpm_now', 0):,.1f} → "
                               f"¥{mixed.get('rpm_max', 0):,.0f}（{mixed.get('why', '')}）"),
                       "measured": True}
    else:
        band = RPM_SCENARIOS.get(PLAN_BAND_BY_FORM.get("ショート", ""), 0)
        if band:
            caps["rpm"] = {"factor": max(RPM_SCENARIOS.values()) / band,
                           "why": (f"RPM の幅の上端 ¥{max(RPM_SCENARIOS.values()):,}"
                                   "（**まだ測っていません**: `python -m src.rpm_mix --record`）"),
                           "measured": False}
    sr = a0.get("sub_rate") or 0.0
    if sr > 0:
        caps["sub_rate"] = {"factor": 1.0 / sr,
                            "why": "登録率 100%（定義上の上限）",
                            "measured": False}
    return caps


def _capped_arms(a0: dict, arms: dict | None = None,
                 density: float = PLAN_PUBLISH_PER_DAY,
                 supply: dict | None = None) -> dict:
    """実測の天井（`hypotheses.yaml`）と、実在する幅（`physical_caps`）の**低いほう**を当てる。"""
    if arms is None:
        arms = arm_speed.all_arms(per_video_now=a0.get("per_video_now"))
    phys = physical_caps(a0, density, supply=supply)
    out = {}
    for lever, a in arms.items():
        a = dict(a)
        p = phys.get(lever)
        if p and p["factor"] > 0:
            if a.get("cap") is None or p["factor"] < a["cap"]:
                a["cap"] = p["factor"]
                a["cap_why"] = p["why"]
                a["cap_measured"] = p["measured"]
        if a.get("cap") is not None and "cap_why" not in a and a.get("ceiling"):
            a["cap_why"] = f"実測の天井 {a['ceiling']['value']:,}（{a['ceiling']['unit']}）"
            a["cap_measured"] = True
        out[lever] = a
    return out


#: 軌跡を追う地平（日）。ここより先は「届かない」と同じに扱う。
#: 3年 ＝ 目標の「最短」から見ればとっくに別の道を選んでいる長さです。
TRAJECTORY_HORIZON_DAYS = 1_095


def _factors_at(arms: dict, days: float, *, focus: str | None = None,
                rate_scale: float = 1.0, realloc: bool = True) -> dict:
    """**`days` 日たったときの、腕ごとの倍率。**（天井で頭打ち）

    `focus` を渡すと、**その腕に回転を全部振った**場合になります
    （他の腕は動きません ＝ 1.0 のまま）。回転は1本しかないので、
    「全部の腕を全力で」は**実在しない世界**です。

    ## `realloc` ——**天井に着いた腕から、回転を引き上げる**（2026-08-21 02:1x）

    `rate = focus_rate × share` で、`share` は**実績の配分**（過去にどの腕を
    何回引いたか）です。ここが**固定**だったので、天井に着いた腕にも
    回転が回り続けていました。実測では `per_video` の配分が **57%** で、
    その腕は **×1.57 で天井**です —— **回転の半分以上を、
    もう伸びない腕に永久に注ぎ続ける世界**を歩いていました。
    軌跡が「腕を全部振っても出ません」と言っていた正体はこれです。

    これは物理ではなく**この機械の振る舞い**で、しかも
    **毎回 `lever_hint` を読んで腕を選び直している**のだから、
    固定するほうが手順と食い違っています。天井に着いた腕を外して
    **残りで配分を割り直す**のが、実際にやっていることです。

    `realloc=False` で前の（配分を固定した）線に戻せます。
    **`tests/test_eta_realloc.py` が、固定に戻ったら落とします。**
    """
    if focus is not None or not realloc:
        out = {}
        for lever, a in arms.items():
            if focus is None:
                rate = a.get("rate")
            else:
                rate = a.get("focus_rate") if lever == focus else 0.0
            rate = (rate or 0.0) * rate_scale
            out[lever] = arm_speed.factor_at({**a, "rate": rate}, days)
        return out

    # --- 天井に着いた腕を外しながら、配分を割り直して進める ---
    #     速さは log で線形（`x(t) = exp(rate·t)`）なので、
    #     「次にどれかが天井に着く時刻」まで進めては割り直す、で厳密に解けます。
    logf = {k: 0.0 for k in arms}
    # **`cap == 1.00` は「天井が無い」ではなく「もう伸びない」**（2026-08-22 に直した）。
    #     ここは `> 1.0` で弾いていたので、**伸びしろゼロの腕だけが野放し**になり、
    #     軌跡が `density` を ×3.43 まで歩いていました（`arm_speed.factor_at` に全文）。
    caps = {}
    for k in arms:
        c = arms[k].get("cap")
        caps[k] = None if (c is None or c <= 0) else max(float(c), 1.0)
    # **足すのではなく、空いた配分だけを配り直します。**
    #     `rate` は「実績の配分のまま進んだ速さ」＝ `focus_rate × share`。
    #     天井に着いた腕の `share` が空くので、残りは
    #     `rate ÷ (残っている share の合計)` に上がります。
    #     **全部が生きている t=0 では、これは `rate` そのもの**です
    #     （`share` の合計は1）。だから前の線と食い違いません ——
    #     `tests/test_eta_trajectory.py` の「倍率は速さと日数から出ている」が、
    #     そこ（`x(t) = exp(rate·t)`）を固定しています。
    base_rate = {k: ((arms[k].get("rate") or 0.0) * rate_scale) for k in arms}
    share = {k: (arms[k].get("share") or 0.0) for k in arms}
    live = {k for k in arms if base_rate[k] > 0
            and (caps[k] is None or caps[k] > 1.0)}
    t = 0.0
    while t < days and live:
        tot = sum(share[k] for k in live)
        if tot <= 0:
            break
        step = float("inf")
        rate = {}
        for k in live:
            rate[k] = base_rate[k] / tot
            if caps[k] is not None and rate[k] > 0:
                step = min(step, (math.log(caps[k]) - logf[k]) / rate[k])
        step = min(step, days - t)
        if not (step > 0):                       # 天井に着いている腕は外して割り直す
            live -= {k for k in live
                     if caps[k] is not None and logf[k] >= math.log(caps[k]) - 1e-12}
            continue
        for k in live:
            logf[k] += rate[k] * step
        t += step
        live -= {k for k in live
                 if caps[k] is not None and logf[k] >= math.log(caps[k]) - 1e-12}
    out = {}
    for k in arms:
        x = math.exp(logf[k])
        out[k] = min(x, caps[k]) if caps[k] else x
    return out


def trajectory(m: dict, a0: dict, *, supply: dict | None = None,
               points: list[dict] | None = None, today: date | None = None,
               arms: dict | None = None, focus: str | None = None,
               rate_scale: float = 1.0,
               horizon: int = TRAJECTORY_HORIZON_DAYS,
               mix: dict | None = None) -> dict:
    """**腕が実測の速さで動いていったとき、いつ月20万に届くか。**

    2026-08-20 18:xx・オーナー指示（原文）——

    > 腕とやらをそう設定した時に達成がいつになるって予測じゃなくて、じゃあその腕を
    > そうなるまでにどれくらい時間がかかるのかとか予測しないとダメだよ。**特定条件の
    > 予測じゃなくて、実際にどういう軌跡を辿るか予測して、いつ達成かを予測するんだよ。**

    `lever_days` が出していたのは「**×2 になったら** 2027-01-19」で、
    **×2 に何日かかるかを1行も予測していませんでした。** 同じ回に
    「1日25本」を外したばかりです —— **満たせるか分からない前提の上に日付が乗る**
    という、まったく同じ欠陥が腕の側に残っていました。

    ## 解いている形

    腕の倍率は時間の関数です（`src/arm_speed`。閉じた前提15件の実測）:

        x_l(t) = min( exp(rate_l · t), 天井_l )

    `t` 日ぶん腕を動かしてから走らせたときの到達日は `t + D(x(t))` で、
    `D` は既存の `plan()` をそのまま解き直したものです。**軌跡の到達日は
    その最小値**です:

        T = min_t [ t + D(x(t)) ]

    最小を取る `t` が「**腕をどれだけ動かしてから走らせるのが最短か**」で、
    そこが 0 なら**いま走らせるのが最短**、大きければ**先に腕を動かせ**という意味です。

    **`t` のあいだの進みを足していません**（＝ 遅い側に倒しています）。
    腕を動かしている最中にも公開は続き、登録者も再生も積み上がるので、
    実際の到達はこれより早いほうへ動きえます。**上振れ側に倒すより、
    こちらのほうが目標に対して安全です** —— 早く出た日付は、待つ理由に使われます。

    返り: `days` / `date` / `t_work`（腕を動かす日数）/ `factors`（そのときの倍率）/
    `blocking`（届かないときに**名指しした理由**）。
    """
    today = today or today_jst()
    # **腕は実在する幅の中でしか伸びません**（`physical_caps`）。
    #     ここを外すと、軌跡は 1日 110,525本 のような世界を歩きます。
    arms = _capped_arms(a0, arms, supply=supply)

    best = {"days": NEVER, "t_work": None, "factors": None}
    rates = {k: ((a.get("focus_rate") if focus == k else (0.0 if focus else a.get("rate"))) or 0.0)
             * rate_scale for k, a in arms.items()}
    # **腕が全部止まっているなら、`t` を回す意味はありません**（`t=0` だけ見る）。
    moving = any(r > 0 for r in rates.values())
    # **天井まで行き着いたら、その先は `t` が増えるだけ**なので打ち切る。
    saturate = 0.0
    for k, a in arms.items():
        r, cap = rates[k], a.get("cap")
        if r > 0:
            # **天井 ×1.00 の腕は、0日で行き着いています**（`t` を回す意味がない）。
            #     ここも `cap > 1` で弾いていたので、**動かない腕のために
            #     地平（3年）ぶんの探索**を回していました。
            if cap is not None and cap > 0:
                saturate = max(saturate, math.log(max(float(cap), 1.0)) / r)
            else:
                saturate = max(saturate, float(horizon))
    last = int(min(horizon, math.ceil(saturate))) if moving else 0

    for t_work in range(0, last + 1):
        # **打ち切りは厳密です**（近似ではありません）。`D >= 0` なので、
        #     `t` が今の最良を超えた時点で `t + D(t)` は必ずそれより大きくなります。
        if t_work >= best["days"]:
            break
        fac = _factors_at(arms, t_work, focus=focus, rate_scale=rate_scale)
        try:
            a2 = analyse(m, points=points, scale=fac)
            pl2 = plan(m, a2, today=today, supply=supply, sensitivity=False, points=points,
                       mix=mix)
        except Exception:                                      # noqa: BLE001 — 回を止めない
            continue
        d = pl2.get("days_to_target", NEVER)
        if d >= NEVER:
            continue
        total = t_work + d
        if total < best["days"]:
            best = {"days": total, "t_work": t_work, "factors": fac,
                    "binding": pl2.get("binding"), "plan_days": d}

    out = {
        "arms": arms, "focus": focus, "rate_scale": rate_scale,
        "days": best["days"], "t_work": best["t_work"], "factors": best["factors"],
        "binding": best.get("binding"), "plan_days": best.get("plan_days"),
        "date": (today + timedelta(days=math.ceil(best["days"])))
                if best["days"] < NEVER else None,
        "searched_days": last,
    }
    out["blocking"] = _trajectory_blocking(arms, out)
    return out


def _trajectory_blocking(arms: dict, out: dict) -> list[str]:
    """**軌跡が出なかったとき、何が塞いでいるかを名指しする。**

    「届きません」で終えないこと（`plan()` の `blocking` と同じ作り）。
    ここが空のまま「出ません」と印字したら、**次の回は何を測ればいいか分かりません。**
    """
    if out["date"] is not None:
        return []
    why: list[str] = []
    for lever, a in arms.items():
        if not a.get("rate"):
            note = a["missing"][-1] if a.get("missing") else "速さが出ていない"
            why.append(f"`{lever}` が動きません（{note}）")
        cap = a.get("cap")
        if cap and a.get("ceiling"):
            c = a["ceiling"]
            why.append(f"`{lever}` は **×{cap:.2f} が天井**（実測 {c['value']:,} ・{c['unit']}）。"
                       f"外す腕は `{c.get('escape')}`")
    if not why:
        why.append(f"腕を {out['searched_days']:,}日 動かしても、到達日が出ませんでした"
                   "（天井そのものが目標の下）")
    return why


def trajectory_choice(m: dict, a0: dict, base: dict, **kw) -> list[dict]:
    """**この回の回転を、どの腕に振るのがいちばん早いか。**

    `base` は実績の配分のまま進んだ軌跡です。ここが返すのは
    **「全部この腕に振ったら軌跡が何日動くか」** —— 名前ではなく日数で選べる形にします。
    **回転は1本しかありません。** 4本とも全力で動かす線は、実在しません。
    """
    rows = []
    for lever in arm_speed.ARMS:
        t = trajectory(m, a0, focus=lever, **kw)
        rows.append({
            "lever": lever, "days": t["days"], "date": t["date"],
            "t_work": t["t_work"],
            "gain": (base["days"] - t["days"]) if (base["days"] < NEVER and t["days"] < NEVER)
                    else (NEVER - t["days"] if t["days"] < NEVER else 0.0),
            "reachable": t["days"] < NEVER,
        })
    rows.sort(key=lambda r: (r["days"], r["lever"]))
    return rows


def trajectory_all(m: dict, a0: dict, *, supply: dict | None = None,
                   points: list[dict] | None = None,
                   today: date | None = None) -> dict:
    """**軌跡を1回で全部解く**（本線・幅・腕べつ）。`main` と検査の入口はここ1つ。

    返り:

        base     実績の配分のまま進んだ軌跡（**これが印字する1つの日付**）
        fast/slow 当たる確率の幅（Jeffreys 90%）の両端で解き直した軌跡
        choice   「全部この腕に振ったら」を腕べつに解いたもの（早い順）
        streak   いま何連続で外しているか
        band     当たり件数と確率の幅（出どころ）
    """
    today = today or today_jst()
    rows = arm_speed.closed()
    bd = arm_speed.band(rows)
    arms = _capped_arms(a0, supply=supply)
    kw = dict(supply=supply, points=points, today=today, arms=arms)
    base = trajectory(m, a0, **kw)
    p = bd.get("p") or 0.0
    fast = slow = None
    if p > 0 and bd.get("lo") and bd.get("hi"):
        # **速さは当たる確率に比例します**（`rate = p·log g·θ`）。だから幅は
        # 確率の幅をそのまま倍率にして入れます。**腕ごとの p は別ですが、
        # 幅の出どころは1つ**（標本15件）なので、同じ比を当てています。
        fast = trajectory(m, a0, rate_scale=bd["hi"] / p, **kw)
        slow = trajectory(m, a0, rate_scale=bd["lo"] / p, **kw)
    return {
        "base": base, "fast": fast, "slow": slow,
        "choice": trajectory_choice(m, a0, base, **kw),
        "streak": arm_speed.miss_streak(rows),
        "band": bd, "arms": arms, "unread": arm_speed.unreadable(),
    }


def supply_min_sustained_hours() -> float:
    """`src.supply.MIN_SUSTAINED_HOURS`。**読めない回でも印字を止めない。**"""
    try:
        from src import supply as supply_mod

        return float(supply_mod.MIN_SUSTAINED_HOURS)
    except Exception:                                          # noqa: BLE001
        return 24.0


def supply_state() -> dict | None:
    """**予測に渡す供給の実測**（読めなければ `None`。回は止めない）。"""
    try:
        from src import supply as supply_mod

        return supply_mod.state()
    except Exception:                                          # noqa: BLE001
        return None


def solve_gate1(a: dict, *, density: float, supply: dict | None,
                view_cap: float | None = None) -> dict:
    """**門1（登録者1,000人）が通る日を、「出せる本数」から解く。**

    2026-08-20 16:0x・オーナー指示（原文）——

    > 25は物理的に不可ならそれを予測に使うのはどうなの？

    **そのとおりでした。** ここは `a["days_subs_at"][25]` の1行で、
    `25` は `PLAN_PUBLISH_PER_DAY` ——「**予約を詰め直したらこうなる**」という
    置き方であって、**作れる本数ではありません**（定数の脇の註がそう書いてある）。
    実測は **在庫37本・未使用の節0件**。25本/日 は 1.5日で尽きます。
    **満たせない前提を入力にした日付は、予測ではありません。**

    いま解いているのは、次の2本の直線の**低いほう**です（`src.supply`）:

        予約の詰め方   density × t           在庫が足りているあいだの上限
        作る速さ       在庫 + 実測の速さ × t  在庫を食い終わった先の上限

    **「作る速さ」は実測です**（`supply.make_rate`。テーマ総数の増え方）。
    固定値ではなく、**この回が節を書けば上がる数**なので、`density` の腕は
    ここに効きます —— 効いたぶんだけ、次の回の予測が前に動きます。

    **ただし、読むのは `sustained_rate_per_day`（1日続けられる速さ）のほうです**
    （2026-08-20 20:0x）。`rate_per_day` は窓が3時間でも数を返すので、
    **3.3時間で +5本 ＝ 1日 36.5本**というバーストが `min(25, 36.5) = 25` を通り、
    **同じ日に外させた 25 が別の入口から戻っていました。**
    窓が 24時間 をまたいでいない回は、`src.supply.state()` が
    **出口の実測**（実際に公開になった本数／日）へ落とします。

    供給が読めないとき（`supply is None`）は前と同じ直線に落ちますが、
    **`measured: False` を返すので、画面は「未検証の前提」と断ります。**
    """
    need = a.get("videos_needed_gate1", float("inf"))
    # **出した本数ではなく、再生が付いた本数だけが門を押します**（2026-08-21 16:2x）。
    #     ここは長らく `plan_density = 25` をそのまま使い、**25本/日 出せば
    #     25本ぶんの登録者が来る**と読んでいました。実測は違います
    #     （`src/day_cap.py`）—— 08/20 は 25本 公開して **#11から先の15本が
    #     0〜3再生**。時刻ではなく**その日の通し番号**で割れます
    #     （08/16 の 14時 #4 は 1,361再生／08/20 の 14時 #12 は 0再生）。
    #     **上限は腕では動きません。** `density` を倍に振っても、上限を超えたぶんは
    #     0再生のままなので、ここは倍率の**後**に掛けます。
    #     **これが `density` の腕の天井そのもの**で、`tests/test_eta_day_cap.py`
    #     が「上限を無視した側へ戻ったら」落とします。
    view_cap = day_cap.cap() if view_cap is None else view_cap
    density = min(float(density), float(view_cap))
    # **使ってよいのは「1日続けられる速さ」だけ**（2026-08-20 20:0x に踏んだ）。
    #     `rate_per_day` をそのまま使うと、**3.3時間で +5本 ＝ 1日36.5本**という
    #     バーストが入り、`min(25, 36.5)` を通って **25 が別の入口から戻ります**
    #     —— 同じ日にオーナーが「物理的に不可なら予測に使うな」と外させた数です。
    #     `src.supply.state()` が `sustained_rate_per_day` を出すので、そちらを読む。
    #     （手で作った塊にその欄が無い回は、前と同じ `rate_per_day` に落ちます）
    if supply is None:
        rate_raw = None
    elif "sustained_rate_per_day" in supply:
        rate_raw = supply["sustained_rate_per_day"]
    else:
        rate_raw = supply.get("rate_per_day")

    if rate_raw is None:
        return {"days": a["days_subs_at"].get(int(density), NEVER),
                "measured": False, "need_videos": need,
                "density_sustained": density, "dry_days": None,
                "rate_per_day": None, "stock": None, "density_basis": None}

    from src import supply as supply_mod

    rate = float(rate_raw)
    stock = int((supply or {}).get("stock") or 0)
    days = supply_mod.days_for(need, stock=stock, rate_per_day=rate,
                               plan_density=density, never=NEVER)
    return {
        "days": days,
        "measured": True,
        "need_videos": need,
        # 収益の窓（30日）は在庫を食い終わった先にあるので、**そこでの密度は
        # 「作る速さ」で頭打ち**です。段4 はこちらで立てること。
        "density_sustained": min(float(density), rate),
        "density_basis": (supply or {}).get("sustained_basis"),
        # **材料が尽きる日だけは、速いほうの実測で見ます。**
        #     掃引の候補を食うのは「節を書く手」＝ `make_rate` のほうで、
        #     持続する速さ（＝出口の実測）はその下限でしかありません。
        #     下限で割ると尽きる日が**後ろにずれ、警告が甘くなります**
        #     （実測: 3.5本/日 なら 22日、36.5本/日 なら 2日）。
        "dry_days": supply_mod.material_dry_days(
            novel=supply.get("novel"),
            rate_per_day=max(rate, float((supply or {}).get("rate_per_day") or 0.0))),
        "rate_per_day": rate,
        "rate_burst": (supply or {}).get("rate_per_day"),
        "stock": stock,
        "thin": bool(supply.get("rate", {}).get("thin")),
    }


def plan(m: dict, a: dict, density: int = PLAN_PUBLISH_PER_DAY,
         view_cap: float | None = None,
         today: date | None = None, supply: dict | None = None,
         sensitivity: bool = False, points: list[dict] | None = None,
         mix: dict | None = None) -> dict:
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
    sc = a.get("scale") or DEFAULT_SCALE
    # **密度の腕は、いまや「作る速さ」に効きます**（`solve_gate1`）。
    #     予約の詰め方（`density`）も一緒に動かさないと、倍率が片肺になります。
    density = density * sc["density"]
    # **倍率は `sustained_rate_per_day` にも当てること**（2026-08-21 02:3x に踏んだ）。
    #     `solve_gate1` は 2026-08-20 20:0x に **読む欄を `rate_per_day` から
    #     `sustained_rate_per_day` へ移しました**。ところがここは古い欄だけを
    #     掛けたままで、**段4 の天井（`per_video × density_sustained`）に
    #     `density` の倍率が1ミリも入っていませんでした** ——
    #     `density_sustained = min(密度, 続けられる速さ)` の第2項が素通しなので、
    #     腕を天井（×11.79）まで振っても `7.8本/日` のまま。
    #     **`density` は、掛け値なしに「引いても日付が動かない腕」でした。**
    #     軌跡が「全部振っても出ません」と言っていた理由の1つがこれです。
    #     **`tests/test_eta_density_scale.py` が、片方だけに戻ったら落とします。**
    if supply is not None and sc["density"] != 1.0:
        upd = {}
        for key in ("rate_per_day", "sustained_rate_per_day"):
            if supply.get(key) is not None:
                upd[key] = supply[key] * sc["density"]
        if upd:
            supply = dict(supply, **upd)
    g1 = solve_gate1(a, density=density, supply=supply, view_cap=view_cap)
    # **段4（月20万）は在庫を食い終わった先にあります。**
    #     そこでの密度は「予約の詰め方」ではなく「作る速さ」で頭打ちなので、
    #     月に何本出せるかは `density_sustained` で数えること。
    #     ここを 25 のままにすると、**1.5日ぶんの在庫で1か月ぶんを数えます。**
    density_month = g1["density_sustained"]
    monthly_slots = density_month * 30

    # --- **面（サムネのインプレッション）の実測を、段2と段4に当てる**（2026-08-20 23:2x）---
    #
    #     **段2 と段4 は、同じ1つの測り忘れに乗っていました。**
    #
    #     段4 は「純長尺・RPM ¥400」で立っていました。¥400 は
    #     **再生の 100% が長尺**のときの数です。ところが長尺のサムネが
    #     見せられている面は実測 **37.6回/日**しかなく（`src/reach_split.py`）、
    #     **CTR 100% でも長尺は再生の 13.0% までしか取れません。**
    #     そのときの実効 RPM の天井は **¥313**（`src/rpm_mix.py`）で、
    #     **¥400 はその上にあります。** ＝ 段4 の合格点 500,000回/月 は
    #     実測だと **639,000回/月**で、**1.28倍 甘い**数字でした。
    #
    #     段2 も同じです。合格点は「長尺を1日4本・1本あたり 221回」＝ 884回/日 ですが、
    #     いまの面は CTR 100% でも 37.6回/日 です（**23.5倍 足りません**）。
    #     **足りないのはインプレッションで、サムネと題（CTR）では動きません。**
    #
    #     **天井は固定ではありません。** 長尺を出せば面が増え、次の回の
    #     `python -m src.rpm_mix --record` でこの天井は上がります。
    #     **測れていないときは据え置きの帯へ落ちます**（`capped=False` で分かるようにする）。
    #     **この天井は、呼ぶ側から差せます**（`mix=` / 2026-08-22 に足した）。
    #     既定（`None`）は今までどおり `rpm_mix.last()` ——**本番の数字は1つも変わりません。**
    #     差せるようにしたのは、**構造を測る検査が実測の混ざり方に乗っていた**からです:
    #     `tests/test_eta_target_date.py` は「段4 は段3 の写しでないこと」など
    #     **形**を固定していますが、合格点（`need_month`）は実効 RPM の逆数なので、
    #     `--record` を1回撃つたびに動きます。08/20 の初測（帯 ¥400 → 実効 ¥253）で
    #     合格点が 500,000 → 789,922回/月 に上がり、**天井 714,000回/月 を追い越して**
    #     `days_to_target` が全部 `NEVER` に落ち、検査3件が赤になりました
    #     （**形は1行も壊れていないのに**です）。`view_cap` を差せるようにしたのと同じ理由で、
    #     **物差しを実データの偶然から外します**（`docs/trigger_main.md` §4「既知の当たりを
    #     実データの偶然に置かないこと」）。`mix={}` ＝「混ざり方を測っていない」＝ 帯そのまま。
    mix = (rpm_mix.last() or {}) if mix is None else dict(mix)
    rpm_cap = float(mix.get("rpm_max") or 0.0) or None
    long_views_day_cap = float(mix.get("imp_day") or 0.0) or None

    # --- どの形で月20万を取りに行くか（**下振れの RPM で比べる**）---
    forms: dict[str, dict] = {}
    for form, band in PLAN_BAND_BY_FORM.items():
        # **帯（¥400）と、実際に出せる実効 RPM（混ざり方）は別物です。**
        #     腕 `rpm` を何倍にしても、面が増えるまで実効 RPM は天井を越えません。
        band_rpm = RPM_SCENARIOS[band] * sc["rpm"]
        capped = bool(rpm_cap and band_rpm > rpm_cap)
        rpm_plan = min(band_rpm, rpm_cap) if rpm_cap else band_rpm
        need_month = (TARGET_YEN * 1000 / rpm_plan) if rpm_plan > 0 else float("inf")
        need_per_video = need_month / monthly_slots if monthly_slots else float("inf")
        forms[form] = {
            "band": band,
            "rpm": rpm_plan,
            "rpm_band": float(RPM_SCENARIOS[band] * sc["rpm"]),
            "capped": capped,
            "views_needed_month": need_month,
            "per_video_needed": need_per_video,
            # **物差しはショートの実測**。長尺の実測（2回）で割ると、
            # 「登録者9人の頃に出した5本」が計画の分母になります（M20）。
            "ratio_vs_shorts": (need_per_video / per_video) if per_video else float("inf"),
        }
    spine = min(forms, key=lambda f: forms[f]["ratio_vs_shorts"])
    sp = forms[spine]

    # --- 段1: 門1（登録者1,000人）。**実測のあるショートで開ける** ---
    #     **供給（作る速さ）で解きます。** 定数 25 は上限としてしか使いません。
    d_gate1 = g1["days"]

    # --- 段2: 門2a（長尺4,000時間）。段1と**並行**。合格点は1本あたり再生 ---
    #     いちばん甘い形（尺が長く維持率が高い）を取る。**本数は決められる／
    #     決められないのは1本あたり再生のほう**なので、そちらを解いて出す。
    rows = _long_break_even(a)
    per_day_long = max(LONG_PER_DAY_SCENARIOS)
    best = min(rows, key=lambda r: r["views"][per_day_long])
    gate2_bar = best["views"][per_day_long]

    # --- 段3: 収益化の審査 ---
    d_monetized = d_gate1 + MONETIZE_REVIEW_DAYS if d_gate1 < NEVER else NEVER

    # --- 段4: 月20万に届く日を、**解いて出す**（2026-08-20 08:0x と 08:3x の合流）---
    #
    # **2つの回が、同じ1行（`d_target = d_monetized`）を別々に見つけました。**
    # 片方は「20万は水準なので、**収益化してから30日ぶん積んだ合計**でしか名乗れない」
    # （`REVENUE_WINDOW_DAYS`・`_stage4`）。もう片方は「**合格点が立つ日そのものを、
    # 実測の伸び率で解いていない**」（`solve_revenue_day`）。**どちらも要ります。**
    #
    #   ① 直近30日の再生が、月に要る回数に達する日          ← 伸び率で解く
    #   ② その30日が**まるごと収益化の後**にあること        ← 収益化前の再生は1円も生まない
    #   ③ 合格点の倍率が**推測**なら、確かめた後であること  ← 別の形の実測を当てている間
    #
    # 到達日は、この3つの**いちばん遅いほう**です。
    # **どれが縛っているかが、次に引く腕を決めます。**
    # 天井も**持続する密度**で。予約の詰め方で掛けると、在庫の無い先まで
    # 「1日25本」が続く天井を印字します。
    ceiling_day = per_video * density_month
    ceiling_day_long = (a.get("long_per_video") or 0) * density_month
    need_month = sp["views_needed_month"]
    growth = a.get("growth") or growth_per_day(m)
    g = growth.get("g")
    views_day_now = a.get("views_day_now", a["views_per_day"])

    d_revenue = solve_revenue_day(views_day_now, g, ceiling_day, need_month)
    # **長尺の実測（2回/本）をそのまま当てた側**も出します。片方だけ出すと、
    # 「まだ測っていない」が「届く」にも「届かない」にも化けます（M20）。
    d_revenue_long = solve_revenue_day(views_day_now, g, ceiling_day_long, need_month)

    # --- **物差しが「別の形の実測」になっていないか** ---
    #     段4 が立てているのは長尺で、割っているのはショートの実測です。
    #     長尺の実測が無い／標本が薄いあいだ、合格点は**推測**でしかありません。
    #     （下の `blocking` と同じ条件。2か所で別々に書くと必ずずれるので、ここで1回）
    lpv = a.get("long_per_video")
    n_long = a.get("long_videos_28d", 0)
    proxy = spine.startswith("長尺") and (lpv is None or n_long < 20)

    s4 = _stage4(m, a, sp, density_month, per_video, d_monetized,
                 today or today_jst(), proxy=proxy, d_revenue=d_revenue)
    d_target = s4["when"]

    # **どれが到達日を縛っているか。** ここが、この回に引く腕を決めます。
    if d_revenue >= NEVER:
        binding, hint = "再生数が天井に当たっている", "rpm"
    elif d_revenue >= s4["floor"]:
        binding, hint = "再生数（段4の (a)）", "per_video"
    elif s4["conditional"] and s4["verify_floor"] >= s4["gate_floor"]:
        binding, hint = "合格点がまだ推測（確かめ待ち）", "rpm"
    else:
        binding, hint = "収益化の門＋その後の30日", "density"

    # --- 「何を何倍にすれば何日後か」（**届かないで終わらせない**）---
    #     ②の30日は前借りできないので、**期日から30日を引いた所まで**に
    #     再生の水準が立っていなければ間に合いません。そこを逆算します。
    base = today or today_jst()
    horizons = []
    for h in GROWTH_HORIZONS:
        rg = required_growth(views_day_now, ceiling_day, need_month,
                             h - REVENUE_WINDOW_DAYS)
        horizons.append({
            "days": h,
            "date": base + timedelta(days=h),
            "growth": rg,
            "double_days": double_days(rg) if rg else None,
            "reachable": rg is not None,
        })
    # 天井そのものが足りないときは、**伸び率ではなく形の話**になる
    ceiling_month = ceiling_day * 30
    ceiling_short = need_month / ceiling_month if ceiling_month > 0 else float("inf")

    # --- **足りない天井を、面（長尺のインプレッション）で埋めるなら何回/日 要るか** ---
    #     「届きません」で畳まないための逆算（オーナー指示 2026-08-20 06:2x）。
    #     **この機械が RPM を上げる道は1つだけ**です —— 長尺が再生に占める割合を上げること。
    #     その割合の上限は面が決めます（`rpm_mix.surface_ceiling`: CTR 100% でも
    #     `imp_day / (imp_day + ショートの再生/日)` まで）。だから逆に解けます:
    #
    #         要る実効RPM = 20万 × 1000 ÷ いまの天井（月の再生）
    #         要る長尺の割合 = (要る実効RPM − ショートの帯) ÷ (長尺の帯 − ショートの帯)
    #         要る面 = 割合 ÷ (1 − 割合) × ショートの再生/日
    #
    #     **帯は `高` を使います**（¥2,000 / ¥60）。上の天井 ¥313 が `高` で出ているので、
    #     ここだけ `低` にすると、同じ画面の中で2つの物差しが混ざります。
    #     割合が 1 を超えたら、**面だけでは埋まりません**（＝1本あたり再生か密度も要る）。
    surface_needed: dict = {}
    if ceiling_short > 1 and ceiling_month > 0 and long_views_day_cap:
        r_long = float(RPM_SCENARIOS["長尺 お金 高"])
        r_short = float(RPM_SCENARIOS["ショート 高"])
        rpm_needed = TARGET_YEN * 1000 / ceiling_month
        share_needed = (rpm_needed - r_short) / (r_long - r_short)
        views_form = (mix.get("views_by_form") or {})
        days_mix = max(1.0, float((mix.get("window") or {}).get("days") or 1))
        short_day = float(views_form.get("ショート") or 0.0) / days_mix
        surface_needed = {
            "rpm_needed": rpm_needed, "rpm_long": r_long, "rpm_short": r_short,
            "share_needed": share_needed, "imp_day_now": long_views_day_cap,
        }
        if share_needed >= 1.0 or short_day <= 0:
            surface_needed.update({"impossible": True, "rpm_at_full": r_long,
                                   "still_short": rpm_needed / r_long})
        else:
            imp_req = share_needed / (1 - share_needed) * short_day
            surface_needed.update({"impossible": False, "imp_day_needed": imp_req,
                                   "imp_factor": imp_req / long_views_day_cap})

    # **結論はこの1つの比較に乗っています。**
    # 「②と③で決まる床までに、再生数のほうが間に合うか」——
    # 間に合うなら到達日は門と窓で決まり（引く腕は density / sub_rate）、
    # 間に合わないなら再生数で決まります（引く腕は per_video / rpm）。
    # **どちらかを言うだけでは、次の回が「余裕があるのか、ぎりぎりなのか」を測れません。**
    g_needed = (required_growth(views_day_now, ceiling_day, need_month,
                                int(s4["floor"]))
                if s4["floor"] < NEVER else None)

    stages = [
        {
            "no": 1, "lever": "density", "when": d_gate1,
            "title": "門1（登録者1,000人）を、実測のあるショートで開ける",
            "bar": (f"要る本数 **{g1['need_videos']:,.0f}本**"
                    f"（1本あたり {per_video:,.0f}回 × 登録率 {a['sub_rate'] * 100:.4f}%）を、"
                    + (f"在庫 {g1['stock']}本 ＋ **作る速さ 1日 {g1['rate_per_day']:.1f}本の実測**"
                       f"（詰め方の上限 {density:.0f}本/日）で埋める"
                       if g1["measured"] else
                       f"**1日{density:.0f}本という未検証の前提**で埋める"
                       "（`src/supply.py` が読めませんでした）")),
            "measured": g1["measured"],
        },
        {
            "no": 2, "lever": "rpm", "when": d_gate1,
            "title": f"門2a（長尺4,000時間）を、段1と並行で開ける",
            # **面（インプレッション）と突き合わせる。**
            #     合格点は「1日 per_day_long 本 × 1本あたり gate2_bar 回」＝ 再生/日 です。
            #     いまの面は CTR 100% でも `long_views_day_cap` 回/日 しか出せません。
            "note": ((f"**いまの面（長尺のインプレッション {long_views_day_cap:,.1f}回/日・実測）は、"
                      f"CTR 100% でも {long_views_day_cap:,.0f}回/日**。"
                      f"合格点の {gate2_bar * per_day_long:,.0f}回/日 に "
                      f"**{gate2_bar * per_day_long / long_views_day_cap:,.1f}倍 足りません**。"
                      "**足りないのはインプレッションで、サムネと題（CTR）では動きません**"
                      "（`src/reach_split.py`）")
                     if long_views_day_cap else None),
            "bar": (f"長尺を1日{per_day_long}本・{best['label']} で出し、"
                    f"**1本あたり {gate2_bar:,.0f}回**"
                    # **0除算で回を止めないこと。** 1本あたり再生が 0 で返る日
                    # （Analytics が空・窓に公開が1本も無い）に、予測そのものが落ちます。
                    # `plan()` は 2026-08-20 08:0x から `report()` より**先**に走るので、
                    # ここで落ちると**実測の表ごと失います**（前は段取りの節だけでした）。
                    + (f"（ショート実測の {gate2_bar / per_video:.2f}倍）"
                       if per_video else "（ショートの実測がまだありません）")),
            "measured": False,
        },
        {
            "no": 3, "lever": "none", "when": d_monetized,
            "title": f"収益化の審査（公表「通常1か月以内」＝ {MONETIZE_REVIEW_DAYS}日と置く）",
            "bar": "門1・門2a の両方を満たしたら申請。**待つだけの段**",
            "measured": False,
        },
        {
            "no": 4, "lever": ("rpm" if ceiling_short > 1 else "per_video"),
            "when": d_target,
            "title": (f"月20万に到達（{sp['band']}・RPM ¥{sp['rpm']:,.0f}"
                      + ("／**帯の ¥{:,.0f} は、実測の混ざり方の天井で頭打ち**".format(sp["rpm_band"])
                         if sp.get("capped") else "")
                      + "）"),
            "bar": (f"直近30日で **{sp['views_needed_month']:,.0f}回**"
                    f"（＝1日{density}本 × 1本あたり {sp['per_video_needed']:,.0f}回）を、"
                    f"**収益化の後に {REVENUE_WINDOW_DAYS}日ぶん**積む。"
                    f"いま 1日 {views_day_now:,.0f}回、伸び率 "
                    + (f"**{g * 100:+.2f}%／日**（{double_days(g):,.0f}日で2倍）"
                       if g and g > 0 else "**0以下 ＝ 伸びていません**")
                    + f"、天井 1日 {ceiling_day:,.0f}回"),
            "measured": s4["met"],
            # **段取りの一覧だけを読む人にも、条件つきだと分かるようにする。**
            #     ここが無いと「2027-01-21 に届く」とだけ読めます。
            "note": ("**この日付は条件つきの「最早」です**（合格点がまだ実測で"
                     "立っていない）。下の「その日付は、どこから出ているか」を読むこと"
                     if s4["conditional"] else None),
        },
    ]

    # --- 段取り全体を止めている「まだ測っていない入力」を1つ名指しする ---
    #     **計画を空にしない**ための欄です。ここが埋まっていれば、
    #     次の回は「何をするか」を決め直さずに、この1手から始められます。
    if proxy:
        blocking = {
            "what": "長尺の1本あたり再生",
            "now": (f"{lpv:,.0f}回（n={n_long}・登録者が9人だった頃の標本）"
                    if lpv is not None else "測っていない"),
            "need": f"{sp['per_video_needed']:,.0f}回（段4）／{gate2_bar:,.0f}回（段2）",
            "how": "長尺を出して、公開から48時間おいた本で測り直す",
            "why": ("段2・段4 の期日がこの1つに乗っている。"
                    f"ショートは{per_video:,.0f}回出ているので、要るのはその"
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

    out = {
        "density": density, "density_month": density_month,
        "gate1": g1, "supply": supply,
        "spine": spine, "spine_band": sp["band"],
        # **面の実測**（段2 と段4 が、これを見ないまま立っていました）
        "surface": {"rpm_cap": rpm_cap, "long_views_day_cap": long_views_day_cap,
                    "capped": sp.get("capped", False),
                    "rpm_band": sp.get("rpm_band"), "rpm_plan": sp["rpm"]},
        "forms": forms, "stages": stages, "blocking": blocking,
        "days_to_target": d_target, "target": s4,
        "target_date": (base + timedelta(days=math.ceil(d_target))) if d_target < NEVER else None,
        "days_monetized": d_monetized,
        "days_revenue": d_revenue,
        "days_revenue_long": d_revenue_long,
        "binding": binding,
        "lever_hint": hint,
        "growth": growth,
        "ceiling_day": ceiling_day,
        "ceiling_day_long": ceiling_day_long,
        "ceiling_short": ceiling_short,
        "surface_needed": surface_needed,
        "growth_needed_by_gate": g_needed,
        "need_month": need_month,
        "views_day_now": views_day_now,
        "horizons": horizons,
    }
    # --- **腕べつに、到達日が何日動くか**（オーナー指示 2026-08-20 16:0x）---
    #     `sensitivity=False` で呼ばれた回は測りません（`lever_days` が
    #     `plan()` を呼び直すので、そのままだと無限に潜ります）。
    if sensitivity:
        out["lever_days"] = lever_days(m, a, pl0=out, today=today, supply=supply,
                                       points=points, mix=mix)
        best = max(out["lever_days"], key=lambda r: r["gain"], default=None)
        # **縛っている床の名前より、実測の差のほうを信じる。**
        #     「門が縛っている＝density」は正しい診断ですが、**どの腕がいちばん
        #     日付を動かすか**は別の問いで、そこは掛け算の形で決まります。
        if best and best["gain"] > 0:
            out["lever_measured"] = best["lever"]
            out["lever_hint_binding"] = out["lever_hint"]
            out["lever_hint"] = best["lever"]
    return out


REFLECT_KIND = "reflect"


def _points(*, reflect: bool = False, offline: bool = False) -> list[dict]:
    """`data/eta.jsonl` を積んだ順に読む。**壊れた行は黙って飛ばす**（回を止めない）。

    **既定では「反映の行」を外します**（2026-08-20・オーナー指示「毎回その予測に
    反映して」の配線）。周の終わりに `--reflect` が積む行は、
    **同じ実測をもう一度解き直したもの**です。予測の点として数えると:

      * `growth_per_day()` の回帰に、**中身が同じで時刻だけ違う点**が入る
      * `_drift()` の「前の回」が、**同じ回の自分自身**になる

    どちらも「チャンネルが動いた」と読める形の嘘になります。**だから外す。**
    読みたいときだけ `reflect=True`（`_reflect_rows()` がそれを使います）。

    **`offline: true` の点も、同じ理由で外します**（2026-08-20 23:5x）。
    `--offline` は「最後の実測の**写し**をもう一度解く」ので、印は 875814c が
    足していました。**ところが、その印を読む側が1つもありませんでした。**

    実際に踏んだ形（この回）——
    周の中で `--offline` を3回撃って直しを確かめたら、その3点が末尾に積まれ、
    **周の終わりの `--reflect` が、自分の debug の点を「前の回」として掴みました。**
    結果、この回の前後差は **2027-04-06 → 届かない** ではなく
    **「どちらも届かない」**と出ました —— **その回の作業ぶんが、消えます。**

    読みたいときだけ `offline=True`。
    """
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not reflect and row.get("kind") == REFLECT_KIND:
            continue
        if not offline and row.get("offline"):
            continue
        out.append(row)
    return out


def headline(pl: dict, prev: dict | None = None,
             tr: dict | None = None) -> list[str]:
    """**この回のいちばん最初と、いちばん最後に出す3行。**

    ## なぜ2回出すか（2026-08-20 08:0x・オーナー指示3回目）

    > 「20万達成までのプランを作って**達成日時を予測**して、
    >   **毎回達成日時を早めることを考えてから進める**ようにして」

    同じ趣旨の指示は 08-19（33699957）・08-20 06:2x に続き**3回目**です。
    **3回言われている ＝ まだ形になっていない。**

    出ていなかった理由は2つあり、どちらも「書いてなかった」ではありません。

    1. **段4 の期日が段3 の写しだった** …… 日付は出ていたが、それは
       「収益化が終わる日」で、**20万に届く日ではありませんでした**（`plan()`）
    2. **その日付が、出力の 200行目あたりにあった** …… `eta.py` の出力は長く、
       読み手が最初に見るのは天井の表です。**最初に見た数字が、その回の入口**になります

    だから**日付と、引くべき腕を、最初と最後の両方に置きます。**
    真ん中は読み飛ばしても、この3行だけで「今日は何を動かすか」が決まる形にすること。
    """
    bar = "###"
    out = ["", "=" * 66]
    # **いちばん上に出す日付は「軌跡」のほうです**（2026-08-20 18:xx・オーナー指示）。
    #     腕を据え置いた線（`pl["target_date"]`）は、**腕が1ミリも動かない未来**の
    #     日付です。この機械は毎周かならず腕を1つ引いているので、それは
    #     「特定条件の予測」であって、辿る道ではありません。
    base = (tr or {}).get("base")
    if base is not None:
        if base["date"] is not None:
            out.append(f"{bar} **月20万の到達予測（軌跡）: {base['date'].isoformat()}**"
                       f"（{math.ceil(base['days']):,}日後）"
                       f" …… 腕を {base['t_work']}日 動かして、そこから"
                       f" {base['plan_days']:,.0f}日")
        else:
            out.append(f"{bar} **月20万の到達予測（軌跡）: 出ません**"
                       f" …… {base['blocking'][0] if base['blocking'] else '塞いでいる所が名指しできていません'}")
        fast, slow = (tr or {}).get("fast"), (tr or {}).get("slow")
        if fast and slow:
            def _d(x):
                return x["date"].isoformat() if x["date"] else "出ません"
            out.append(f"{bar} 幅（当たる確率の90%区間）: 早い **{_d(fast)}**"
                       f" ／ 遅い **{_d(slow)}**（遅い側が「外れ続けた場合」）")
    # **軌跡が解けなかった回でも、「到達予測」の字は必ず出すこと。**
    #     ここを「据え置いた線」だけにすると、軌跡が落ちた回の出力から
    #     **到達予測という言葉ごと消えます**（検査が1件それを見ています）。
    label = ("腕を**据え置いた**線" if base is not None
             else "**月20万の到達予測（腕を据え置いた線）**")
    if pl["target_date"] is not None:
        out.append(f"{bar} {label}: {pl['target_date'].isoformat()}"
                   f"（{_fmt_days(pl['days_to_target'])}）"
                   + ("" if base is None else " ← **腕が1ミリも動かない未来。辿る道ではありません**"))
    else:
        out.append(f"{bar} {label}: **出ません**"
                   "（天井が足りない。下に「どの腕をいくつにすれば出るか」）")
    out.append(f"{bar} 縛っているのは **{pl['binding']}**"
               f" → **この回に引く腕は `{pl['lever_hint']}`**"
               + (f"（**軌跡が名指し**。床の名前は `{pl['lever_hint_binding']}` ですが、"
                  "それは診断であって、引いて何日縮むかは言っていません）"
                  if pl.get("lever_from") == "軌跡" else ""))
    top = next((r for r in (tr or {}).get("choice", []) if r["reachable"]), None)
    if top is not None:
        gain = (base["days"] - top["days"]) if base and base["days"] < NEVER else None
        out.append(f"{bar} **回転を全部振るなら `{top['lever']}`** →"
                   f" {top['date'].isoformat()}"
                   + (f"（軌跡より **{gain:,.0f}日 早い**）" if gain and gain > 0
                      else "（軌跡と同じか、遅い）"))
    # **腕の名前を出したら、その腕が何で動くのかも同じ3行に出す**
    # （2026-08-21 05:xx に測って足した）。この回は `density` の入力
    # `make_rate` を **22.85 → 46.7（2倍）** に動かしましたが、
    # 到達日は **+0日** でした。軌跡の腕は `config/hypotheses.yaml` の
    # **閉じた前提の実測**だけで動くので、テーマを作っても在庫から出しても
    # 1ミリも動きません。**その区別が3行の中に無いと、次の回も同じ所へ来ます。**
    arms = (tr or {}).get("arms") or {}
    hint = pl.get("lever_hint")
    a_hint = arms.get(hint)
    if a_hint is not None:
        th = a_hint.get("throughput")
        turn = f"実測 {1 / th:,.1f}日に1件" if th else "実測なし（閉じた前提が0件）"
        pr = a_hint.get("p")
        prob = f"・当たり {pr:.0%}" if pr is not None else ""
        out.append(
            f"{bar} **軌跡の腕が動くのは、`config/hypotheses.yaml` の前提を"
            f"1件閉じたときだけ**（`{hint}`: {turn}{prob}）。"
            "**作る・出す・直すは、軌跡の入力に入りません** ——"
            "段の側（`--reflect` が測る入力）は動きますが、"
            "**上の日付は動きません**")
        # **そのうえで「いつなら動くのか」を出す**（2026-08-21 06:xx）。
        # 期日の来た前提が1件も無い回は、**何をしても到達日は動きません。**
        # それを先に言わないと、その回は外れる `--moves` を立てるだけで終わります。
        try:
            nc = arm_speed.next_close()
        except Exception:
            nc = None
        if nc and nc.get("on") is not None:
            if (nc.get("days") or 0) > 0:
                out.append(
                    f"{bar} **この回に閉じられる前提はありません** ——"
                    f" いちばん早い期日は **{nc['on'].isoformat()}**"
                    f"（{nc['days']}日後・開いている前提 {nc['open']}件）。"
                    "**それまでは、どんな作業をしても上の日付は動きません**"
                    "（`--moves 0` が正しい回です）")
            else:
                out.append(
                    f"{bar} **期日の来た前提があります**"
                    f"（{nc['on'].isoformat()}・開いている前提 {nc['open']}件）→"
                    " **この回は `verdict` で日付が動かせます**")
    # **腕の名前だけで終わらせない。** その腕を引いたら日付が何日動くかを、
    # 同じ3行の中に出します（オーナー指示 2026-08-20 16:0x「分析して制作に
    # 活かして視聴回数などを上げることが予測に使えることじゃない？」）。
    ld = pl.get("lever_days") or []
    top = [r for r in ld if r["reachable"]][:2]
    if top:
        f = top[0]["factor"]
        out.append(f"{bar} **{f:.0f}倍にしたら:** "
                   + " ／ ".join(
                       f"`{r['lever']}` → **{r['date'].isoformat()}**"
                       + (f"（**{pl['days_to_target'] - r['days']:,.0f}日 早まる**）"
                          if pl["days_to_target"] < NEVER
                          else "（いまは日付が出ません → **出ます**）")
                       for r in top))
    how = _how_to_pull(pl)
    if how:
        out.append(f"{bar} {how}")
    prev_date = None
    # **比べるのは同じ物差しどうし。** 軌跡が出ている回は軌跡の日付と、
    # 出ていない回は据え置きの日付と比べます（混ぜると「1日で200日早まった」が出ます）。
    key = "traj_date" if (base is not None and prev and prev.get("traj_date")) else "target_date"
    cur_date = base["date"] if (key == "traj_date" and base is not None) else pl["target_date"]
    if prev and prev.get(key):
        try:
            prev_date = date.fromisoformat(str(prev[key]))
        except ValueError:
            prev_date = None
    if prev_date and cur_date:
        delta = (cur_date - prev_date).days
        mark = ("**早まりました**" if delta < 0
                else "動いていません" if delta == 0 else "**遠のきました**")
        out.append(f"{bar} 前の回の予測 {prev_date.isoformat()} → **{delta:+d}日** {mark}"
                   + ("（軌跡どうし）" if key == "traj_date" else "（据え置きの線どうし）"))
    elif prev_date and cur_date is None:
        out.append(f"{bar} 前の回は {prev_date.isoformat()} → **今回は日付が出ません**"
                   "（前提が変わったか、実測が落ちた）")
    # **物差しを取り替えた回は、その差を「遠のいた」と読ませない**（`_scale_note` と同じ形）。
    #     密度の入力が「1日25本という前提」から「作る速さの実測」に替わった回は、
    #     チャンネルは何も変わっていないのに日付が大きく動きます。
    if prev is not None and prev.get("make_rate_per_day") is None \
            and (pl.get("gate1") or {}).get("measured"):
        out.append(f"{bar} [!] **この回から、密度の入力が変わりました**"
                   f"（「1日{pl['density']:.0f}本」という前提 → "
                   f"**作る速さ {pl['gate1']['rate_per_day']:.1f}本/日 の実測**）。"
                   "**上の差は実績ではありません。**")

    elif prev and prev.get(key) is None and cur_date:
        out.append(f"{bar} 前の回は日付が出ていませんでした → **道が開きました**")
    else:
        out.append(f"{bar} （比べられる前の点がまだありません）")
    out.append("=" * 66)
    return out


def _report_plan(m: dict, a: dict, pl: dict | None = None) -> list[str]:
    """**この節を、いちばん最後に出すこと**（`main()` が `_drift` / `levers` の後に呼ぶ）。

    ここより後ろに「届きません」を置かないこと —— 読み手が最後に見るものが
    そのまま次の回の入口になります（オーナー指示 2026-08-20 06:2x）。
    """
    out: list[str] = []
    P = out.append
    pl = pl or plan(m, a, supply=supply_state(), sensitivity=True)
    d = pl["density"]

    P("")
    P("=" * 66)
    P("=== **月20万に到達するまでの段取り**（予測を「届きません」で終わらせない）===")
    P("=" * 66)
    g1 = pl.get("gate1") or {}
    if g1.get("measured"):
        P(f"  **密度は実測から解いています: 1日続けられる速さ {g1['rate_per_day']:.1f}本"
          f"（在庫 {g1['stock']}本）／詰め方の上限 {d:.0f}本/日**")
        if g1.get("density_basis"):
            P(f"     出どころ: **{g1['density_basis']}**")
        # **バーストを持続と読み替えていないか、画面に出す**（2026-08-20 20:0x）。
        #     3.3時間の窓の 36.5本/日 が `min(25, 36.5) = 25` を通って
        #     `density_month` に入り、**外させたはずの 25 が戻っていました。**
        burst = g1.get("rate_burst")
        if burst is not None and g1["rate_per_day"] < burst - 1e-9:
            P(f"     [!] **直近の作る速さ {burst:.1f}本/日 は使っていません**"
              f"（窓 {((pl.get('supply') or {}).get('rate') or {}).get('hours', 0.0):.1f}時間"
              f" < {supply_min_sustained_hours():.0f}時間 ＝ **1日続く速さとは言えない**）。"
              "24時間をまたぐ点が貯まれば、自動でそちらに切り替わります")
        P(f"  → **段4（月20万）が乗るのは、持続する {pl['density_month']:.1f}本/日 のほう**"
          "（収益の30日は在庫を食い終わった先にあります）")
        if g1.get("dry_days") is not None:
            P(f"  → 掃引の材料は **{g1['dry_days']:.0f}日**で尽きます"
              "（その先は `src/calc/` に**新しい表**が要る）")
        basis = ((pl.get("supply") or {}).get("rate") or {}).get("basis")
        if basis:
            P(f"     （作る速さの出どころ: **{basis}**。"
              "**2つの物差しは混ぜていません** —— 実測で 20本ちがいました）")
        if g1.get("thin"):
            P("  [!] **作る速さの窓が 6時間 未満です**（1本の増減で桁が動く帯）。"
              "`python -m src.supply --record` を毎周ぶん積むと締まります")
    else:
        P(f"  [!] **密度は未検証の前提です: 1日 {d:.0f}本**"
          "（`src/supply.py` が読めませんでした。**作れる本数ではありません**）")
    P("     （92本は API の日枠であって、出せる本数ではありません）")
    P(f"  **物差しはショートの実測 {a['per_video_now']:,.0f}回/本**"
      "（この機械が持つ唯一の当てになる1本あたり）")
    P("")
    P("--- どの形で取りに行くか（**その形のいちばん低い RPM で比べる**）---")
    sf = pl.get("surface") or {}
    if sf.get("rpm_cap"):
        P(f"    **帯（¥400 など）は「再生の100%がその形」のときの数です。**"
          f" いまの混ざり方の天井は **¥{sf['rpm_cap']:,.0f}**（実測）")
        P(f"      長尺の面 {sf['long_views_day_cap']:,.1f}回/日（実測）× CTR100% までしか"
          "長尺の再生は増えません。**帯をそのまま当てると合格点が甘くなります**")
    else:
        P("    [!] **面（長尺のインプレッション）が測れていません。**"
          " 帯をそのまま当てています（`python -m src.rpm_mix --record`）")
    for form, f in pl["forms"].items():
        mark = " ← **これで立てる**" if form == pl["spine"] else ""
        cap = "  ← **帯 ¥{:,.0f} を、実測の混ざり方の天井で頭打ち**".format(f["rpm_band"]) \
            if f.get("capped") else ""
        P(f"    {form:<8} RPM ¥{f['rpm']:>5,.0f}  月 {f['views_needed_month']:>10,.0f}回 要る"
          f"  → 1本あたり **{f['per_video_needed']:>7,.0f}回**"
          f"（ショート実測の {f['ratio_vs_shorts']:>5.2f}倍）{mark}{cap}")
    P("")
    P("--- 段取り（**最後の段に日付が入るまでが1つの予測**）---")
    for st in pl["stages"]:
        P(f"    段{st['no']}［腕 {st['lever']}］{st['title']}")
        P(f"        期日: {_fmt_days(st['when'])}")
        P(f"        合格点: {st['bar']}")
        if st.get("note"):
            P(f"        [!] {st['note']}")
    P("")
    tg = pl["target"]
    P(f"  → 月20万の到達見込み: {_fmt_days(pl['days_to_target'])}")
    P(f"     （{pl['spine_band']}・1日{d}本・審査{MONETIZE_REVIEW_DAYS}日を置いた線）")
    P(f"     内訳（**いちばん遅いものが到達日**）:")
    P(f"       (a) 直近30日の再生が、月に要る回数に達する日 …… {_fmt_days(pl['days_revenue'])}")
    P(f"       (b) その30日がまるごと収益化の後にある日 …… {_fmt_days(tg['gate_floor'])}"
      f"（収益化 {_fmt_days(pl['days_monetized'])} ＋ {REVENUE_WINDOW_DAYS}日）")
    if tg["verify_floor"]:
        P(f"       (c) 合格点の倍率を確かめ終えている日 …… {_fmt_days(tg['verify_floor'])}"
          f"（確認 {tg['verify_on'].isoformat()} ＋ {REVENUE_WINDOW_DAYS}日）")
    P(f"     **縛っているのは {pl['binding']}**"
      f" → **この回に引く腕は `{pl['lever_hint']}`**"
      "（ここを動かさない作業は、上の日付を1日も動かしません）")
    gr = pl["growth"]
    if gr.get("g") is not None:
        P(f"     伸び率 **{gr['g'] * 100:+.2f}%／日**"
          f"（{double_days(gr['g']):,.0f}日で2倍）… {gr['basis']}")
    else:
        P(f"     伸び率: {gr['basis']}")
    if gr.get("caveat"):
        P(f"       断り: {gr['caveat']}")
    # **測った窓と、延ばしている先の比を出す**（2026-08-20 20:0x）。
    #     水準を決めているのは天井のほうなので、ここに時間の頭打ちは入れません
    #     （`solve_revenue_day` の註）。**ただし、何倍先まで延ばしているかは見せる。**
    span = gr.get("span_days") or 0.0
    if span > 0 and tg.get("d_revenue", NEVER) < NEVER:
        P(f"       **{span:.1f}日ぶんの窓で測った伸びを、{tg['d_revenue']:,.0f}日先"
          f"（{tg['d_revenue'] / span:,.1f}倍）まで延ばしています。**"
          f" 水準の頭打ちは天井（1日 {pl['ceiling_day']:,.0f}回 ＝"
          f" 密度 {pl['density_month']:.1f}本 × {a['per_video_now']:,.0f}回）のほうです")
    gn, gnow = pl.get("growth_needed_by_gate"), (gr.get("g") or 0.0)
    if gn is not None:
        room = (gnow / gn) if gn > 0 else float("inf")
        P(f"     **(b)(c) の床（{_fmt_days(tg['floor'])}）までに (a) を満たすのに要る伸び:"
          f" {gn * 100:+.2f}%／日**"
          f" ／ 実測 {gnow * 100:+.2f}%／日"
          + (f" → **足りています（{room:,.1f}倍の余裕）**" if gnow >= gn
             else f" → **足りません（{gn / gnow:,.1f}倍 要る）**" if gnow > 0
             else " → **伸びていません**"))
        P("       ← **結論はこの1行に乗っています。** 伸びが落ちれば、"
          "到達日を縛るのは門と窓ではなく再生数 (a) のほうに移ります。")
    if pl["ceiling_day_long"] > 0:
        P(f"     **長尺の実測（{pl['ceiling_day_long'] / d:,.0f}回/本）をそのまま当てた側**: "
          f"再生数 {_fmt_days(pl['days_revenue_long'])}")
        P("       ← 上の線はショートの実測を長尺に当てています。"
          "**この2つの幅が、まだ測っていないぶんです**（下の1行）。")
    P("")
    P("--- **何を何倍にすれば、いつ届くか**（予測を「届きません」で終わらせない）---")
    for h in pl["horizons"]:
        if h["reachable"]:
            P(f"    {h['date']}（{h['days']:>3}日後）まで … 1日あたり **{h['growth'] * 100:+.2f}%** の伸び"
              f"（{h['double_days']:,.0f}日で2倍）")
        else:
            P(f"    {h['date']}（{h['days']:>3}日後）まで … **伸び率をいくら上げても届きません**")
    if pl["ceiling_short"] > 1:
        P(f"    → **天井が {pl['ceiling_short']:,.2f}倍 足りません。待っても届きません。**")
        # **「いま ¥400」と印字していました。** 帯をそのまま出していたので、
        #     実測の混ざり方で頭打ちになった後も、画面は帯のままでした。
        P(f"       1本あたり再生（いま {pl['ceiling_day'] / d:,.0f}回）か RPM（いま ¥{sf.get('rpm_plan', 0):,.0f}）"
          f"か 密度（いま {d}本/日）を、掛けて {pl['ceiling_short']:,.2f}倍 にすること")
        # --- **その天井を、面（長尺のインプレッション）で埋めるなら何回/日 要るか** ---
        #     「届きません」で畳まないための逆算です（オーナー指示 2026-08-20 06:2x）。
        #     RPM を上げる道はこの機械では1つしかありません ——
        #     **長尺の再生の割合を上げること**で、その割合の上限は面が決めます。
        need_sf = pl.get("surface_needed") or {}
        if need_sf.get("impossible"):
            P(f"       [!] **面だけでは埋まりません。** 再生の 100% を長尺にして"
              f"（RPM ¥{need_sf['rpm_long']:,.0f}）も 実効 ¥{need_sf['rpm_at_full']:,.0f} "
              f"＝ 要る ¥{need_sf['rpm_needed']:,.0f} に **{need_sf['still_short']:,.2f}倍 足りません**。"
              "**1本あたり再生か密度も、同時に動かすこと**")
        elif need_sf.get("imp_day_needed"):
            P(f"       **面で埋めるなら: 長尺のインプレッション {need_sf['imp_day_now']:,.1f}回/日 → "
              f"{need_sf['imp_day_needed']:,.0f}回/日（×{need_sf['imp_factor']:,.1f}）**"
              f"（長尺が再生の {need_sf['share_needed'] * 100:.1f}% になる面。実効 RPM ¥{need_sf['rpm_needed']:,.0f}）")
    else:
        P(f"    （天井は足りています: 1日 {pl['ceiling_day']:,.0f}回 × 30日 ＝ 月 {pl['ceiling_day'] * 30:,.0f}回"
          f" ≧ 要る {pl['need_month']:,.0f}回）")
    P("")
    P("--- **その日付は、どこから出ているか**（20万以外の日付で代用しない）---")
    P(f"    合格点 : 1本あたり **{tg['need_per_video']:,.0f}回**"
      f"（いまの物差し {tg['per_video_now']:,.0f}回 の **{tg['ratio']:.2f}倍**）")
    if tg["fallback"]:
        f = tg["fallback"]
        P(f"    [!] {f['why']}。**倍率では出ません**（0を何倍しても0）。")
        P(f"        {f['assume']} → 門1 {_fmt_days(f['gate1_days'])}")
    if tg["met"]:
        P(f"    ① 合格点は**いまの実測で立っています**（{tg['ratio']:.2f}倍 ≤ 1.00）"
          f" → 立つ日は収益化と同じ {_fmt_days(tg['bar_day'])}")
    else:
        if tg["proxy"]:
            P(f"    ① 合格点は**まだ立っていません**。倍率は ×{tg['ratio']:.2f} ですが、"
              "**割っているのはショートの実測**です。")
            P(f"        段4 が立てているのは長尺で、そこは測っていません"
              f"（{pl['blocking']['now']}）。**別の形の実測を当てているあいだ、"
              "合格点は推測です。**")
        else:
            P(f"    ① 合格点は**まだ立っていません**。要るのは"
              f" **1本あたり ×{tg['ratio']:.2f}**。")
        P(f"        それが本当かを確かめられる最短が"
          f" **{tg['verify_on'].isoformat()}**（{tg['verify_day']:.0f}日後"
          "。公開の翌日 → 伸びきる48時間 → Analytics 3日遅れ）")
        P(f"        → 合格点が立つ日 {_fmt_days(tg['bar_day'])}")
    P(f"    ② その水準で **{tg['window']}日ぶん積んだ合計**が、"
      "**まるごと収益化の後**にあること"
      "（収益化前の再生は1円も生まないので、この30日は前借りできません）")
    P(f"       → 床は {_fmt_days(tg['floor'])}")
    P(f"    ①と②の遅いほう ＝ {_fmt_days(pl['days_to_target'])}")
    P("      （①は伸び率で解いた日なので、**倍率が上がればここが後ろへ動きます**。"
      "**②に①を足さないこと** —— ①は直近30日の合計で見ているので、"
      "足すと1か月ぶん二重に数えます）")
    if tg["conditional"]:
        P("    [!] **これは「見込み」ではなく「最早」です。**"
          " 上の倍率が出なければ、この日は来ません（出た日に引き直すこと）。")
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
    out.extend(_report_supply(pl))
    P("")
    if pl["lever_hint"] == "density":
        P(f"  **この回の一手は、門を開ける側（`{pl['lever_hint']}` / `sub_rate`）です** ——"
          " 到達日を縛っているのは収益化の門と、その後の30日のほうで、")
        P("  再生数 (a) はそれより先に満たせる見込みだからです。"
          "**ただし段2 の合格点は上の1行が未測定のまま**なので、")
        P("  **同じ回で測定の的を撃てるなら撃つこと**（穴埋めとは別の日に）。")
    else:
        P(f"  **この回の一手は、`{pl['lever_hint']}` を動かすことです** ——"
          " 到達日を縛っているのは再生数（段4）のほうで、")
        P("  門をいくら早く開けても、20万に届く日は動きません。"
          "**上の1行の測定が、その倍率を確定させます。**")
    return out


def _report_levers(pl: dict) -> list[str]:
    """**腕べつに、到達日が何日動くか**（2026-08-20 16:0x・オーナー指示）。

    > 分析して制作に活かして視聴回数などを上げることが予測に使えることじゃない？

    **使えていませんでした。** 到達日を決めていたのは「1日25本」と「審査30日」で、
    1本あたり再生は**天井の表に出てくるだけ**。上げても下げても日付は動かず、
    それでいて `lever_hint` は毎回 `density` を名指ししていました。
    **動かない数字に向かって「早めろ」と言われていた**わけです。

    ここが出すのは、腕を1つずつ同じ倍率にして**予測をまるごと解き直した差**です。
    **できるかどうかは言っていません。** 言っているのは
    「引けたら何日縮むか」だけ —— それが分かれば、**同じ手間なら差の大きい腕**を
    選べます。名前ではなく日数で決まる形にすること。
    """
    rows = pl.get("lever_days") or []
    if not rows:
        return []
    base = pl.get("days_to_target", NEVER)
    out = ["", "--- **腕べつに、到達日が何日動くか**"
           f"（それぞれ **{rows[0]['factor']:.0f}倍**にして解き直した）---"]
    P = out.append
    if base < NEVER:
        P(f"    いまの実測のまま        {_fmt_days(base)}")
    else:
        P("    いまの実測のまま        **日付が出ません**（天井が足りない）")
    for r in rows:
        if not r["reachable"]:
            P(f"    `{r['lever']:<10}` ×{r['factor']:.0f}   **それでも出ません**"
              f"   {r['label']}")
            continue
        gain = (f"**{base - r['days']:,.0f}日 早まる**" if base < NEVER
                else "**日付が出るようになる**")
        P(f"    `{r['lever']:<10}` ×{r['factor']:.0f}   {r['date'].isoformat()}"
          f"（{r['days']:,.0f}日後）  {gain}   {r['label']}")
    if pl.get("lever_measured"):
        P(f"    → **この回に引く腕は `{pl['lever_measured']}`。**"
          f" 床の名前（{pl.get('lever_hint_binding')}）ではなく、**差の大きさで選んでいます**")
    P("    **「2倍にできる」とは言っていません。** 言っているのは"
      "「2倍にしたら何日縮むか」だけで、**できるかどうかは別の話**です。")
    return out


def _report_trajectory(tr: dict, pl: dict) -> list[str]:
    """**腕が動く速さを含んだ、1本の軌跡**（2026-08-20 18:xx・オーナー指示）。

    > 特定条件の予測じゃなくて、実際にどういう軌跡を辿るか予測して、
    > いつ達成かを予測するんだよ。

    上の `_report_levers` は「×2 にしたら」の表です。**そこには
    「×2 に何日かかるか」が1行もありません** —— 満たせるか分からない前提の上に
    日付が乗る形で、同じ回に外したばかりの「1日25本」とまったく同じ欠陥でした。

    ここが出すのは**時間の関数としての腕**です。倍率は実測の速さで伸び、
    実測の天井で止まります。**表ではなく、1つの日付**にすること。
    """
    base, bd, st = tr["base"], tr["band"], tr["streak"]
    out = ["", "=" * 66,
           "=== **軌跡**（腕が「実測の速さ」で動いていった場合。条件つきの表ではありません）===",
           "=" * 66]
    P = out.append
    for line in arm_speed.lines(tr["arms"], st, bd, tr.get("unread", 0)):
        P(line)
    for lever, a in tr["arms"].items():
        if a.get("cap") and a.get("cap_why"):
            mark = "" if a.get("cap_measured") else "  ← **実測の天井ではありません**"
            P(f"      天井 `{lever}` ×{a['cap']:,.2f} …… {a['cap_why']}{mark}")

    P("")
    if base["date"] is not None:
        P(f"  → **軌跡の到達日: {base['date'].isoformat()}**"
          f"（{math.ceil(base['days']):,}日後）")
        P(f"     内訳: **腕を {base['t_work']}日ぶん動かして**"
          f"（そのとき "
          + " ／ ".join(f"`{k}` ×{v:,.2f}" for k, v in (base["factors"] or {}).items())
          + f"）、そこから {base['plan_days']:,.0f}日 で届く")
        P(f"     そのとき縛っているのは **{base['binding']}**")
    else:
        P("  → **軌跡でも到達日が出ません。** 塞いでいるのは次のものです:")
        for why in base["blocking"]:
            P(f"       - {why}")

    if tr["fast"] and tr["slow"]:
        def _d(x):
            return x["date"].isoformat() if x["date"] else "出ません"
        P(f"     幅（当たる確率 {bd['k']}件/{bd['n']}件 の 90% 区間"
          f" {bd['lo']:.0%}〜{bd['hi']:.0%}）: "
          f"**早い {_d(tr['fast'])} ／ 遅い {_d(tr['slow'])}**")
        P("       **遅いほうが「外れ続けた場合」です。** いまの連敗を確率の更新に使うより、"
          "標本15件ぶんの幅で読むほうが素直です")
    if st["n"]:
        P(f"     いま **{st['n']}連続で外れ**。当たりの間隔の実測は "
          f"{st['expected_gap']:.1f}件 なので "
          + ("**外れすぎです**（速さの前提そのものを疑うこと）" if st["unusual"]
             else "**まだ範囲の中**（「次は当たる」でも「もう当たらない」でもありません）"))

    P("")
    P("--- **この回の回転を、どの腕に振るのがいちばん早いか**"
      "（回転は1本しかありません。4本とも全力の線は実在しません）---")
    for r in tr["choice"]:
        if not r["reachable"]:
            P(f"    `{r['lever']:<10}` **全部振っても出ません**")
            continue
        gain = ((base["days"] - r["days"]) if base["days"] < NEVER else None)
        note = (f"**{gain:,.0f}日 早い**" if gain and gain > 0
                else "**軌跡より遅い**" if gain is not None and gain < 0
                else "**日付が出るようになる**")
        P(f"    `{r['lever']:<10}` → {r['date'].isoformat()}"
          f"（腕を {r['t_work']}日 動かして 計 {math.ceil(r['days']):,}日）  {note}")
    top = next((r for r in tr["choice"] if r["reachable"]), None)
    if top:
        a = tr["arms"][top["lever"]]
        P(f"    → **この回に振る腕は `{top['lever']}`。**")
        if a["source"] != "自前":
            P(f"      [!] ただし `{top['lever']}` の速さは **{a['source']}**"
              f"（この腕で閉じた前提は {a['n']}件・当たり {a['hits']}件）。"
              "**この1行が、いま軌跡でいちばん薄い数です**")
        if a.get("cap") and not a.get("cap_measured"):
            P(f"      [!] `{top['lever']}` の天井 ×{a['cap']:,.2f} は"
              "**測った天井ではありません。** **軌跡はここに寄りかかっています** ——"
              " 測れば動きます")
    P("  **これは「腕がその倍率になる」と言っていません。** 言っているのは"
      "「閉じた前提15件の実測の速さで進んだら、そこに着く」だけです。"
      "速さも天井も、**次に閉じる1件で動きます**。")
    return out


def _report_supply(pl: dict) -> list[str]:
    """**その密度を出せるかを、在庫の側から確かめる**（2026-08-20 13:4x に足した）。

    ## なぜ要るか（**この節が無い間、日付は supply を一度も見ていませんでした**）

    `plan()` は `PLAN_PUBLISH_PER_DAY = 25` で段1 を解き、段1 が段3 を、
    段3 が段4 を押します。**到達予測の日付は、まるごとこの 25 の上に乗っています。**
    ところが定数の脇の註は「受け取り帳 3c7e12a3 の**詰め直し**が着地する所」——
    **予約の置き方**であって、**作れる本数ではありません。**

    実測（足した回）: 未投稿の在庫 36本・**未使用の節 0件**・
    `config/topics.yaml` は 08/19 16:34 UTC から **20時間 増えていません**。
    その 20時間に公開のほうは 25本/日 で進んでいます。
    **25本/日 × 157日 ＝ 3,925本** に対し、いま在るもの（在庫＋掃引の候補）は **527本**。

    **「届かない」と言うためではありません。** 出すのは
    **1周あたり何本の節を書けば 25本/日 が保つか**（実測 **1.0本/周**）——
    `density` の腕は、この回では**そこにしか無い**からです
    （投稿の本数枠が閉じている窓では `upload` を選べません。1日16時間前後がそれ）。

    ## **2026-08-20 16:0x に、ここは日付を動かすようになりました**

    足した回のこの註は「**この節は日付を動かしません**（`plan()` の段には
    入れていません）」でした。理由は「supply は人が節を書けば伸びるので、
    床として使うと『書かない未来』を予測として印字する」——
    **理屈は合っていますが、結論が逆でした。** オーナー指示（原文）:

    > 25は物理的に不可ならそれを予測に使うのはどうなの？

    **足りないと分かっている前提を、日付には反映しないまま印字していた**
    わけです。いま `plan()` が入力にしているのは、
    **在庫（＝いま在るもの）と、テーマが増える速さの実測**（`supply.make_rate`）です。

    - **材料（掃引の候補）は壁にしていません。** 壁にすれば、まさに
      「新しい表を1本も書かない未来」を印字することになります。
      材料は**尽きる日**として出すだけ（`material_dry_days`）
    - **速さのほうは実測**です。固定値ではなく、この回が節を書けば上がるので、
      `density` の腕はそこに効きます

    この節が残っているのは、**その密度が在庫の側から見てどう見えるか**を
    並べて読むためです。**日付そのものは `plan()` の `gate1` にあります。**
    """
    from src import supply as supply_mod

    out: list[str] = []
    P = out.append
    days = pl.get("days_to_target")
    horizon = days if isinstance(days, (int, float)) and days < NEVER else None
    try:
        sw = supply_mod.sweep_novel()
        sp = supply_mod.supply(pl["density"], novel=sw["novel"], horizon_days=horizon)
    except Exception as exc:      # 台帳が読めなくても、予測そのものは止めないこと
        return [f"    （在庫の supply は読めませんでした: {exc}）"]
    out.extend(supply_mod.lines(sp))
    g1 = pl.get("gate1") or {}
    if g1.get("measured"):
        P(f"    → **予測が使っているのはこちらです: 作る速さ 1日 {g1['rate_per_day']:.1f}本の実測**"
          f"（段1 は {_fmt_days(g1['days'])}）。**上の 25本/日 は詰め方の上限**です")
    # **作れても、出しても、再生が付く本数には上限があります**（2026-08-21 16:2x）
    out.extend(day_cap.lines())
    if sw.get("age_hours") is not None and sw["age_hours"] > 24:
        P(f"    （掃引の点は {sw['age_hours']:.0f}時間前。測り直しは"
          " `python -m src.supply --measure`。**掃引を回さず速さだけ積むなら**"
          " `python -m src.supply --record`）")
    return out



def _how_to_pull(pl: dict) -> str | None:
    """**腕の名前だけでは足りない。** その腕を、この窓でどう引くかまで書く。

    2026-08-20 14:2x に足した（前の回の宿題。`docs/JOURNAL.md` 問い3）。
    `density` には道が2つあります —— **出す**（`upload`）と **作る**（節を書く）。
    **どちらが今この窓で通るかは、この道具の外**（`upload_cap.state()`）にあり、
    2つの道具を突き合わせて初めて分かる形でした。**その突き合わせが、
    実測で1周の35分**です（8/20 13:1x と 14:1x が続けて同じ所で使っています）。

    `upload_cap.state()` は控えと `data/*.jsonl` だけを読みます（**API 0単位**）。
    読めなかったら黙って何も足しません —— **予測そのものは止めないこと。**
    """
    if pl.get("lever_hint") != "density":
        return None
    try:
        from src import supply as supply_mod
        from src import upload_cap

        st = upload_cap.state()
        days = pl.get("days_to_target")
        horizon = days if isinstance(days, (int, float)) and days < NEVER else None
        sw = supply_mod.sweep_novel()
        sp = supply_mod.supply(pl["density"], novel=sw["novel"], horizon_days=horizon)
        per_run = sp.get("sections_per_run_needed")
    except Exception:                                          # noqa: BLE001
        return None

    need = (f"この回ぶんは **節 {per_run:.1f}本**"
            if isinstance(per_run, (int, float)) and per_run == per_run
            and per_run != float("inf") else "この回ぶんは `src/supply.py` が出します")
    back = st.resets_at.astimezone(JST).strftime("%m/%d %H:%M JST")
    cap_open = st.remaining > 0 and not st.closed

    # **在庫が密度を支えていないなら、答えは本数枠と関係なく「作る」です**
    # （2026-08-21 04:0x に、この回の実測で直した）。
    #
    # ここは長らく **本数枠が開いているかどうかだけ**で「出す」「作る」を決めていました。
    # **本数枠は「今この窓で何本 API に通せるか」しか言っていません。**
    # ところが `density` の腕が読んでいる入力は `supply.make_rate`
    # ＝ **テーマが1日に何本増えているか**のほうです。
    #
    # **在庫から出すだけでは、その入力は1ミリも動きません。** それどころか、
    # 新しいテーマを1本も作らずに周を1つ進めると、窓だけ伸びて**下がります。**
    #
    # **実測（2026-08-21 03:1x の回）。** 本数枠は開（あと72本）で、ここは
    # 「引き方は『出す』」と言いました。そのとおり在庫から10本を予約したあとの
    # `--reflect` がこれです:
    #
    #     make_rate_per_day: 22.85 → **21.2**     ← 下がっている
    #     到達日（軌跡）: 2026-12-02 → 2026-12-02（**+0日**）
    #
    # **腕を選んで、その腕を引けない道を案内していた**ことになります。
    # `docs/JOURNAL.md`（8/20 18:1x）の申し送りは「`density` を引く回は、
    # 掃引ではなく表を1本書くこと」と、**既に正しいほうを言っていました** ——
    # この道具だけが、本数枠を見て逆を言っていた。
    #
    # **`holds` は「いまの在庫と作る速さで、その密度を期限まで保てるか」**です
    # （`src/supply.py`）。保てないなら、出す先は在庫の食い減らしにしかなりません。
    if sp.get("measured") and not sp.get("holds", True):
        covered = sp.get("days_covered")
        cov = f"{covered:.1f}日ぶん" if isinstance(covered, (int, float)) else "測定中"
        cap = (f"本数枠は開（あと {st.remaining}本）だが" if cap_open
               else f"本数枠は閉（{back} 戻り）。そのうえ")
        return (f"**{cap}、在庫が密度を支えていません（{cov}）"
                f"→ 引き方は「作る」**（`src/calc/` に節を書く）。{need}"
                f"  ＊**在庫から出しても `make_rate` は上がりません**"
                f"（08/21 03:1x の実測: 10本 予約して **+0日**・`make_rate` は下がった）")
    if cap_open:
        return (f"**本数枠は開（あと {st.remaining}本）→ 引き方は「出す」**"
                f"（`batch_build.py`）。作る側なら {need}")
    return (f"**本数枠は閉（{back} 戻り）→ 引き方は「作る」**"
            f"（`src/calc/` に節を書く）。{need}")


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


def solve(m: dict, points: list[dict]) -> dict:
    """**実測 `m` から、予測を最後まで解く。**（2026-08-20 に `main()` から出した）

    出したのは、**周の終わりの「反映」が同じ道を通るため**です
    （オーナー指示・原文: **「毎回その予測に反映して」**）。
    `reflect()` が自前で解き直す形にすると、**2つの道が別々に古びます** ——
    片方だけに腕の上限や供給が入る、という壊れ方は、外から見えません。

    返すのは `{"a", "sup", "pl", "tr", "row"}`。**印字はしません**
    （`main()` は 200行出し、`reflect()` は 10行しか出さないため）。
    """
    a = analyse(m, points)
    m["per_video_now"] = a["per_video_now"]

    # **段取りを先に解いて、日付を最初に出す**（オーナー指示3回目・2026-08-20 08:0x）。
    # 出力は200行あり、読み手が最初に見た数字がその回の入口になります。
    #     **供給の実測を渡すこと**（2026-08-20 16:0x）。渡さないと段1 は
    #     「1日25本」という**満たせない前提**で解かれます（`solve_gate1`）。
    sup = supply_state()
    pl = plan(m, a, supply=sup, sensitivity=True, points=points)
    # **腕が動く速さを含んだ軌跡**（2026-08-20 18:xx・オーナー指示）。
    #     ここが出ないと、印字される日付は「腕が1ミリも動かない未来」になります。
    #     **回を止めないこと** —— 軌跡が解けなくても、据え置きの線だけで出します。
    try:
        tr = trajectory_all(m, a, supply=sup, points=points)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[eta] 軌跡を解けませんでした: {type(exc).__name__}: {exc}")
        tr = None
    # **引く腕は1つに絞ること。** 軌跡が出た回は、そちらが名指しした腕を採ります。
    #     `plan()` の `lever_hint` は「いちばん遅い床の名前」＝**診断**で、
    #     **引いたら何日縮むか**は言っていません。同じ見出しに2つの腕が並ぶと、
    #     読み手はどちらでも選べてしまい、**後から理由を付ける**側に戻ります。
    if tr is not None:
        _top = next((r for r in tr["choice"] if r["reachable"]), None)
        if _top is not None and _top["lever"] != pl["lever_hint"]:
            pl["lever_hint_binding"] = pl["lever_hint"]
            pl["lever_hint"] = _top["lever"]
            pl["lever_from"] = "軌跡"
    return {"a": a, "sup": sup, "pl": pl, "tr": tr,
            "row": _row(m, a, pl, tr, sup)}


def _row(m: dict, a: dict, pl: dict, tr: dict | None, sup: dict | None) -> dict:
    """`data/eta.jsonl` に積む1行を組む。**`solve()` と同じ理由でここに出しています。**"""
    row = {**m, **{k: v for k, v in a.items() if isinstance(v, (int, float))}}
    # **予測日そのものを積む。** 積まないと、次の回が「早まったか」を測れません
    # （`headline` の3行目と、`run_marker.py --ship --moves` の突き合わせ）。
    row["days_to_target"] = pl["days_to_target"]
    row["target_date"] = pl["target_date"].isoformat() if pl["target_date"] else None
    row["days_revenue"] = pl["days_revenue"]
    row["binding"] = pl["binding"]
    row["lever_hint"] = pl["lever_hint"]
    # **供給の実測も積む**（次の回が「作る速さは上がったか」を測れる形にする）
    row["density_month"] = pl.get("density_month")
    row["make_rate_per_day"] = (sup or {}).get("rate_per_day")
    row["days_gate1"] = pl.get("gate1", {}).get("days")
    # **軌跡そのものを積む。** 積まないと、次の回が「軌跡が早まったか」を測れません
    # （据え置きの線と混ぜないこと ＝ 別の欄にする）。
    if tr is not None:
        _b = tr["base"]
        row["traj_days"] = _b["days"]
        row["traj_date"] = _b["date"].isoformat() if _b["date"] else None
        row["traj_t_work"] = _b["t_work"]
        row["traj_focus"] = next((r["lever"] for r in tr["choice"] if r["reachable"]), None)
        row["arm_rates"] = {k: a["rate"] for k, a in tr["arms"].items()}
        row["arm_hits"] = f"{tr['band']['k']}/{tr['band']['n']}"
    row["videos_needed_gate1"] = pl.get("gate1", {}).get("need_videos")
    # --- **天井（面と混ざり方）も積む**（2026-08-20 23:3x。前の周の申し送り②）---
    #     `--reflect` は「出発点の行」と「解き直した行」の差を取ります。
    #     ところが行には**天井が1つも入っていなかった**ので、
    #     22:2x の回が `rpm` の天井を ×100 → ×15.5 に**測り直したのに、
    #     反映は「動かせる入力なし」と言いました。** 測った当人の回が、です。
    #     天井は入力です（実測が同じでも、測り直せば動く ＝ その回の作業ぶん）。
    _sf = pl.get("surface") or {}
    row["rpm_cap"] = _sf.get("rpm_cap")                 # 実測の混ざり方の天井（¥）
    row["rpm_plan"] = _sf.get("rpm_plan")               # 段4 が実際に当てている RPM
    row["long_imp_day"] = _sf.get("long_views_day_cap")  # 長尺の面（回/日・実測）
    row["need_month"] = pl.get("need_month")            # 段4 の合格点（月の再生）
    row["ceiling_short"] = pl.get("ceiling_short")      # 天井が何倍 足りないか
    return row


# ---------------------------------------------------------------------------
# **周の終わりの「反映」**（2026-08-20・オーナー指示。原文は次の1行）
#
#     > 毎回の実行で予測するように言ったはずなので、毎回その予測に反映して
#
# **予測を出すことは、既に毎回やっています。** 言われているのは**反映**のほうです。
# いま起きているのはこう:
#
#   * 判定や実測が出ても、**予測に入るのは次の回か、あるいは入らない**
#   * 2026-08-20 の実例 —— 歩留り 1.0→0.156・供給 21日→4日・A/B の在庫の
#     数え方・掃引の候補数・`retention` の6本。**どれもその回の予測に
#     入っていません**
#   * 逆に、入れてはいけないもの（`density_month 25.0`）が別の欄から戻って
#     **予測を3分の1にしました**
#
# だから、周の終わりに**もう一度解いて、日付の前後差を残します。**
#
# ## なぜ Analytics を取り直さないか（`--reflect` が offline なのは、そのため）
#
# Analytics は**日次で3日遅れ**。回は1時間ごとに回るので、**1日のうち
# 入力は1度も動きません**（実測: `data/eta.jsonl` の18点は `views_7d` も
# `subs_net` も全部同値）。取り直すと API を叩く時間がかかるうえ、
# **たまたま日が変わった回だけ、チャンネル側の変化がこちらの作業のぶんに混ざります。**
#
# **出発点と同じ実測を使えば、動いた差は「この回が触った所」だけになります。**
# ＝ 反映の差は、定義として**この回の作業ぶん**です。
# ---------------------------------------------------------------------------

# **差として数えない鍵**（時刻・種別・反映そのものが書く欄）。
_REFLECT_IGNORE = {
    "at", "kind", "session", "base_at", "note", "moved", "no_movable_input",
    "traj_date_before", "target_date_before", "traj_delta_days", "target_delta_days",
    "traj_days_before", "days_to_target_before", "traj_solved",
}


def _reflect_session() -> str:
    """自分のセッションID。**推測しないこと**（`run_marker.session_id()` と同じ読み）。"""
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
    return ("session_" + raw[4:]) if raw.startswith("cse_") else raw


def _moved(before: dict, after: dict) -> dict:
    """**この回で動いた入力**を、鍵ごとに `[前, 後]` で返す。

    **鍵を列挙しないこと。** 列挙すると、次に足された入力が黙って漏れます
    （`density_month` が別の欄から戻って予測を3分の1にしたのが、まさにその形）。
    実測（Analytics 由来）は出発点のものをそのまま使うので、**ここには構造上出ません** ——
    出るのは供給・密度・腕の速さ・こちらの計算式だけです。
    """
    out: dict = {}
    for k in sorted(set(before) | set(after)):
        if k in _REFLECT_IGNORE:
            continue
        b, a = before.get(k), after.get(k)
        if b == a:
            continue
        if isinstance(b, (int, float)) and isinstance(a, (int, float)) \
                and not isinstance(b, bool) and not isinstance(a, bool):
            if abs(a - b) <= 1e-9 * max(1.0, abs(b)):
                continue
        out[k] = [b, a]
    return out


def _date_delta(before: str | None, after: str | None) -> int | None:
    """**負なら早まった**（`--moves` と同じ向き）。片方でも無ければ `None`。"""
    if not before or not after:
        return None
    try:
        return (date.fromisoformat(after) - date.fromisoformat(before)).days
    except ValueError:
        return None


def _fmt_moved(moved: dict, limit: int = 8) -> list[str]:
    def one(v):
        if isinstance(v, float):
            return f"{v:,.4g}"
        if isinstance(v, dict):
            return "{…}"
        return "無し" if v is None else str(v)
    keys = list(moved)
    out = [f"      {k}: {one(moved[k][0])} → {one(moved[k][1])}" for k in keys[:limit]]
    if len(keys) > limit:
        out.append(f"      （ほか {len(keys) - limit} 件。`data/eta.jsonl` の `moved` に全部あります）")
    return out


def reflect(note: str | None = None, *, record: bool = True) -> tuple[int, dict]:
    """**この回で動いた入力を、この回のうちに予測へ入れ直す。**

    返すのは `(終了コード, 積んだ行)`。**回を止めません** —— 解けなくても 0 を返し、
    「解けませんでした」とだけ言います（反映は記録であって門ではない）。
    """
    points = _points()
    if not points:
        print("[eta] 積んだ点がありません。**まず `python scripts/eta.py` を撃つこと。**")
        return 1, {}
    base = points[-1]
    # **出発点と同じ実測で解き直す**（上のコメント参照）。`solve()` は `m` を書き換えるので複製。
    m = {k: v for k, v in base.items() if k not in _REFLECT_IGNORE or k == "at"}
    try:
        s = solve(dict(m), points)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[eta] 反映を解けませんでした: {type(exc).__name__}: {exc}")
        print("[eta] **回は止めないこと。** 理由を docs/JOURNAL.md に1行書いて進むこと。")
        return 0, {}
    row = s["row"]
    # **軌跡が解けなかった回に、出発点の日付を「後」として読ませないこと。**
    #     `_row()` は `tr is None` のとき軌跡の欄を書きません。反映は
    #     **出発点の行そのものを `m` として渡す**ので、書かれなければ
    #     `traj_date` は出発点の値のまま残り、**差が黙って +0日**になります。
    #     ＝「動かなかった」と「測れなかった」が同じ字になる、いちばん悪い形。
    if s["tr"] is None:
        for k in ("traj_date", "traj_days", "traj_t_work", "traj_focus", "arm_rates", "arm_hits"):
            row.pop(k, None)
    moved = _moved(base, row)
    # **日付そのものは「動いた入力」ではなく「結果」です。** 差の一覧からは外し、
    # 下の前後差として別に出します（混ぜると「入力が動いた」に見える）。
    #     **`per_video_now` は落としません** —— あれは入力の側です
    #     （実測が同じでも、`_per_video()` の式を変えれば動く ＝ この回の作業ぶん）。
    for k in ("target_date", "traj_date", "days_to_target", "traj_days",
              "days_revenue", "binding", "lever_hint", "traj_focus"):
        moved.pop(k, None)
    t_before, t_after = base.get("traj_date"), row.get("traj_date")
    s_before, s_after = base.get("target_date"), row.get("target_date")
    t_delta, s_delta = _date_delta(t_before, t_after), _date_delta(s_before, s_after)

    out = ["", "=== この回の反映（**動いた入力を、この回のうちに予測へ入れ直す**）==="]
    out.append(f"    出発点: {base.get('at', '?')}（同じ実測で解き直しています）")
    if moved:
        out.append(f"    **この回で動いた入力: {len(moved)}件**")
        out.extend(_fmt_moved(moved))
    else:
        # **「効いていない」と混同しないこと**（`_drift` に同じ趣旨の断りがあります）。
        out.append("    [!] **この回で動かせる入力は、1つもありませんでした。**")
        out.append("        **「効いていない」ではありません。** Analytics は日次で3日遅れ、"
                   "回はそれよりずっと速い。")
        out.append("        この回が触った所が、**予測の入力に1つも入っていない**という意味です"
                   "（道具・文書・手順の整備はここに出ません）。")
        out.append("        → 次の回は、**入力に入る腕**（per_video / sub_rate / rpm / density）"
                   "を選ぶこと。")

    def line(label, b, a, d):
        if b is None and a is None:
            return f"    {label}: **どちらも「届かない」**"
        if d is None:
            return f"    {label}: {b or '届かない'} → **{a or '届かない'}**（前後のどちらかが「届かない」＝差は出せません）"
        arrow = "**早まりました**" if d < 0 else ("**遠のきました**" if d > 0 else "動いていません")
        return f"    {label}: {b} → **{a}**（{d:+d}日）  {arrow}"

    if s["tr"] is None:
        out.append("    [!] **軌跡を解けませんでした。** 下の「軌跡」の行は**測れていません**"
                   "（動かなかった、ではありません）。据え置きの線のほうを読むこと。")
    out.append(line("到達日（軌跡）", t_before, t_after, t_delta))
    out.append(line("到達日（腕を据え置いた線）", s_before, s_after, s_delta))
    if moved and t_delta == 0 and s_delta == 0:
        out.append("    → 入力は動いたのに**日付は動いていません。** その入力は"
                   "**いまの律速の外**にあります（`binding` を見ること）。")
    for ln in out:
        print(ln)

    rec = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": REFLECT_KIND,
        "session": _reflect_session() or None,
        "base_at": base.get("at"),
        "moved": moved,
        "no_movable_input": not moved,
        "traj_date_before": t_before, "traj_date": t_after, "traj_delta_days": t_delta,
        "target_date_before": s_before, "target_date": s_after, "target_delta_days": s_delta,
        "traj_days_before": base.get("traj_days"), "traj_days": row.get("traj_days"),
        "days_to_target_before": base.get("days_to_target"),
        "days_to_target": row.get("days_to_target"),
        "binding": row.get("binding"), "lever_hint": row.get("lever_hint"),
        "traj_solved": s["tr"] is not None,
    }
    if note:
        rec["note"] = note
    if record:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        try:
            where = LOG.relative_to(ROOT)
        except ValueError:                                     # 検査は tmp に積みます
            where = LOG
        print(f"[eta] **反映を残しました**: {where}"
              f"（`kind=\"{REFLECT_KIND}\"`。予測の点としては数えません）")
    return 0, rec


def _reflect_recap(limit: int = 3) -> list[str]:
    """**前の回たちが「入れ直した」結果を、この回の頭で見せる。**（2026-08-20）

    `_drift()` は**予測の点どうし**（周の頭と周の頭）を比べます。**周の中で
    動いた入力は、そこには出ません** —— 出るのは次の回か、あるいは永久に出ない。
    それがオーナー指示（**「毎回その予測に反映して」**）の指している穴でした。

    反映そのものは `reflect()` が周の終わりに残します。**ここはその読み口**です ——
    残す所と読む所の両方が無いと、`retention.py` が 8/10〜8/20 に踏んだ形
    （**正しく印字していたが、誰も読まなかった**）をもう一度やります。
    """
    rows = [r for r in _points(reflect=True) if r.get("kind") == REFLECT_KIND]
    if not rows:
        return []
    out = ["", "--- 前の回たちの**反映**（周の中で動いた入力 → 日付がどう動いたか）---"]
    for r in rows[-limit:]:
        when = str(r.get("at", "?"))[5:16].replace("T", " ")
        if r.get("no_movable_input"):
            out.append(f"    {when}  **動かせる入力なし**"
                       f"（{(r.get('note') or '')[:40]}）"
                       "  ← **「効いていない」ではありません**")
            continue
        d = r.get("traj_delta_days")
        if d is None:
            d = r.get("target_delta_days")
        moved = ", ".join(list(r.get("moved") or {})[:3])
        out.append(f"    {when}  {moved or '(入力の記録なし)'}"
                   + (f"  → **{d:+d}日**" if isinstance(d, int) else "  → 差は出せません")
                   + (f"（{(r.get('note') or '')[:40]}）" if r.get("note") else ""))
    n_moved = sum(1 for r in rows if not r.get("no_movable_input"))
    out.append(f"    **入れ直した回: {len(rows)}回 / うち入力が動いたのは {n_moved}回**"
               "（動かなかった回は、触った所が予測の入力に無かったということ）")
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description="月20万に届く日を予測して積む")
    ap.add_argument("--no-record", action="store_true", help="data/eta.jsonl に積まない")
    ap.add_argument("--offline", action="store_true", help="API を叩かず、積んである最後の点から出す")
    # **周の終わりに打つ**（オーナー指示 2026-08-20「毎回その予測に反映して」）。
    # `run_marker.py --ship` が自動で呼びます。**手で打つのは、ship の外で入力を動かした回だけ。**
    ap.add_argument("--reflect", action="store_true",
                    help="周の終わり: この回で動いた入力を予測へ入れ直し、日付の前後差を残す")
    ap.add_argument("--note", metavar="1行", help="--reflect に添える1行（何を入れ直したか）")
    args = ap.parse_args()

    if args.reflect:
        return reflect(args.note, record=not args.no_record)[0]

    if args.offline:
        if not LOG.exists():
            print("[eta] 積んだ点がありません。--offline は使えません。")
            return 1
        # **反映の行を掴まないこと**（`_points()` が既に外しています）。
        m = _points()[-1]
        print("[eta] **積んである最後の点で出しています（いまの実測ではありません）**")
    else:
        try:
            m = _measure()
        except Exception as exc:  # noqa: BLE001 — 予測で回を止めない
            print(f"[eta] 実測を取れませんでした: {type(exc).__name__}: {exc}")
            print("[eta] **回は止めないこと。** `--offline` で最後の点から読めます。")
            return 1

    points = _points()
    _s = solve(m, points)
    a, sup, pl, tr = _s["a"], _s["sup"], _s["pl"], _s["tr"]
    prev = points[-1] if points else None
    for line in headline(pl, prev, tr):
        print(line)

    for line in report(m, a):
        print(line)
    row = _row(m, a, pl, tr, sup)
    # **`--offline` の点だと分かる形で積む**（2026-08-20）。中身は最後の実測の**写し**で、
    # 新しい実測ではありません。印が無いと、次の回は写しを実測として数えます
    # （`_points()` の履歴は、伸び率の分母になります）。
    if args.offline:
        row["offline"] = True
    for line in _drift(row):
        print(line)
    # **周の中で動いた入力は `_drift` には出ません**（あれは点どうしの比較）。
    # 反映の読み口はこちら。**残す所と読む所の両方が要ります。**
    for line in _reflect_recap():
        print(line)
    # **「予測 → 腕を選ぶ → 進む」の、選んだ側の実績**（オーナー指示 2026-08-19 21:2x）。
    # 1周ごとに動くのは日付ではなく**ここ**です（`src/levers.py` の説明）。
    for line in levers.report(ROOT / "data" / "runs.jsonl"):
        print(line)
    # **腕を「日数の差」で並べる**（2026-08-20 16:0x）。ここが無いと、
    # 引く腕は `binding`（どの床が遅いか）という診断からしか決まりません。
    for line in _report_levers(pl):
        print(line)
    # **「×2 にしたら」の表の、すぐ下に軌跡を置くこと。**
    #     表だけを見た読み手は「2倍にすればいい」で終わります。
    #     2倍に何日かかるかは、ここにしかありません。
    if tr is not None:
        for line in _report_trajectory(tr, pl):
            print(line)
    # **段取りは、いちばん最後に出すこと**（オーナー指示 2026-08-20 06:2x）。
    # 読み手が最後に見たものが、そのまま次の回の入口になります。
    # ここより後ろに「届きません」を置かないこと。
    for line in _report_plan(m, a, pl):
        print(line)
    # **最後にもう一度、日付と腕。** 真ん中を読み飛ばしても、ここだけで決まる形にする。
    for line in headline(pl, prev, tr):
        print(line)
    print("  **この回の作業は、上の日付を動かすものを選ぶこと。**"
          " 出したら `run_marker.py --ship \"…\" --lever <腕> --moves <見込みの日数>`。")

    if not args.no_record:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\n[eta] 積みました: {LOG.relative_to(ROOT)}（{sum(1 for _ in LOG.open(encoding='utf-8'))}点目）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
