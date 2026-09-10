"""**YouTube Analytics API v2** の最小限（2026-09-10 16:1x・optimizer・Opus）。

**Data API の日枠（10,000単位/日）は 1単位 も使いません** —— これは別の API・別の枠です
（`youtubeanalytics.googleapis.com`。1周に撃つのは 3クエリ）。**「0単位」と書くときは、
どちらの枠の話かを必ず書くこと** —— この repo の「単位」は Data API v3 の側です。

**なぜ足したか（この回に実測して、METHOD の 2つの行が偽だと分かった）**:

  METHOD §7「90秒の上限」  「**維持率が Studio でしか見えない**ので、機械で測れる代わりの数は
                           `measured` の 6時間再生／48時間再生の比」
  METHOD §7 20:4x         「likes は 0/1 しか動かないので分解能が無い」（＝ 反応の分解能が無い）

**維持率は Studio だけではありません。** `averageViewPercentage` と `averageViewDuration` は
このAPIが本ごとに返します（この回に撃って確かめた・下の実測）。Studio だけなのは
**インプレッションと CTR** で、それは `metrics=impressions` に 400 が返ることで別に確かめてあります
（`src/analytics.fetch_traffic` の註・旧道具が 08月 に踏んでいた）。

**この回の実測（2026-09-10 16:1x・窓 2026-09-05〜09-07）**:

    本                     再生   平均視聴  平均視聴率  登録+  いいね
    4C7_gciPt8c（旧・09/06） 439    12秒     47.83%     0     0
    N75-k7r6pLw（旧・09/06） 350    15秒     53.56%     0     0
    CIPYV_r1Hdo（旧・09/06） 294    15秒     50.19%     0     1
    **EkNqtkK49Bw（新・09/06・90.8秒）** 145 **38秒** **42.09%** 0 0
    PhQ2KvuQASQ（旧・09/07）  76     8秒     25.41%     0     0
    **nQbVxuWpWw8（新・09/07・92.9秒）** 67 **42秒** **45.52%** 0 0
    o6P0ageZd9k（旧・09/06）  17    11秒     34.85%     0     0

  ＝ **維持率（%）では 新しい作りは旧作りの下**（42.1〜45.5% 対 47.8〜53.6%）だが、
    **1回あたりの視聴の秒数は 2.5〜3.5倍**（38・42秒 対 11〜15秒）。
    **どちらを見るかで向きが逆になります。** §7 の「90秒の上限」は
    「60秒以内の本と越えた本で差が出たら締める」と書いていましたが、
    **差は出ており、向きは 2つ です。判定は `hourly`（§5）。**

  流入（同じ窓・チャンネル全体）: **SHORTS 2,738 / YT_SEARCH 94 / SUBSCRIBER 62 /
  YT_OTHER_PAGE 25 / RELATED_VIDEO 2 / NO_LINK_OTHER 1** ＝ **93.7% がショートのフィード**。
  ＝ **「配りは YouTube が持っている」（§1）は、この窓では 93.7% という数になります。**

  **登録は 7本 とも +0**（§7 の収益の節の覆る条件 (1)「登録率が 0.5% を越えたら」は、
  **分子が 0 のまま**。`record_channel` の覆る条件 (2) が言っていた形そのもの）。

**遅れ**: このAPIは**当日を返しません**。この回の実測で最後の日は **2026-09-07**（＝ **3日**）。
旧道具の `data/analytics_lag.jsonl` も 09/05 の回に `last_day 09/02`（同じ 3日）と書いています。
＝ **きょう公開した本には答えられません。** 5本目 `2YZ_4FXC-XI` の 0回 をこの口で見るのは
**09/13 ごろ**です（§7 (c) はそれまで Data API の側で見ること）。

**覆る条件**:
  (1) `lag_days()` が **3日 より短い**回が出たら、この註の「3日」を書き直すこと
      （短くなれば、公開した本の維持率をその週のうちに読めます）。
  (2) 認証が落ちたら（`refresh_token` のスコープに `yt-analytics.readonly` が無い）
      `svc()` が例外を投げます。**そのときは黙って 0 を返さないこと** ——
      「引けなかった」と「0だった」を分けるのは §4 (0-b) の族そのものです。
  (3) `averageViewPercentage` が本ごとに **同じ値**しか返さない回が続いたら、
      それは窓が短すぎる（点が少ない）側 ＝ 窓を伸ばして数え直すこと。
  (4) **7本 過ぎて、維持率が §7 の判定を1度も動かさなければ、この口は毎日 撃たなくてよい**
      （`zero_probe` の (2) と同じ数え方）。
"""
from __future__ import annotations

import datetime as dt

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .common import env

#: 本ごとに引く数（`dimensions=video`）。**並びが台帳の欄の名前になります。**
VIDEO_METRICS = ("views", "estimatedMinutesWatched", "averageViewDuration",
                 "averageViewPercentage", "subscribersGained", "likes")

#: 1度に投げる本の数の上限（`filters=video==` はカンマ区切り。安全側で切る）。
MAX_IDS = 50

_svc = None


def svc():
    global _svc
    if _svc is None:
        creds = Credentials(token=None, refresh_token=env("YT_REFRESH_TOKEN"),
                            token_uri="https://oauth2.googleapis.com/token",
                            client_id=env("YT_CLIENT_ID"), client_secret=env("YT_CLIENT_SECRET"))
        _svc = build("youtubeAnalytics", "v2", credentials=creds, cache_discovery=False)
    return _svc


def _query(**kw) -> dict:
    return svc().reports().query(ids="channel==MINE", **kw).execute()


def _rows(res: dict) -> list[dict]:
    """返りを {欄の名前: 値} の並びにする。**欄の名前は返り自身の `columnHeaders` から取る**
    —— こちらが並べた `metrics` の順を当てにすると、API が並べ替えた回に黙ってずれます。"""
    names = [c["name"] for c in res.get("columnHeaders", [])]
    return [dict(zip(names, r)) for r in res.get("rows", [])]


def daily(days: int = 14, today: dt.date | None = None) -> list[dict]:
    """チャンネル全体の日ごとの再生（`day` 次元）。**遅れのぶん、末尾は今日ではありません。**"""
    end = today or dt.date.today()
    start = end - dt.timedelta(days=days)
    return _rows(_query(startDate=start.isoformat(), endDate=end.isoformat(),
                        metrics="views,estimatedMinutesWatched", dimensions="day", sort="day"))


def lag_days(rows: list[dict], today: dt.date | None = None) -> int | None:
    """`daily()` の返りから「最後の日は何日 前か」。行が無ければ `None`（**0 ではない**）。"""
    if not rows:
        return None
    last = max(dt.date.fromisoformat(r["day"]) for r in rows)
    return ((today or dt.date.today()) - last).days


def per_video(ids: list[str], start: str, end: str) -> list[dict]:
    """本ごとの 再生・視聴分・**平均視聴秒**・**平均視聴率**・登録の増え・いいね。

    **窓の中の数であって、本の通算ではありません** —— `start`〜`end` に付いたぶんだけ。
    """
    ids = list(dict.fromkeys(ids))[:MAX_IDS]
    if not ids:
        return []
    return _rows(_query(startDate=start, endDate=end, metrics=",".join(VIDEO_METRICS),
                        dimensions="video", filters="video==" + ",".join(ids), sort="-views"))


def traffic(start: str, end: str) -> list[dict]:
    """流入経路べつの再生（`insightTrafficSourceType`）。**ショートのフィードに乗っているかを見る唯一の口。**

    主な値: `SHORTS`（ショートのフィード）・`YT_SEARCH`・`SUBSCRIBER`・`BROWSE_FEATURES`・
    `RELATED_VIDEO`・`YT_OTHER_PAGE`・`NO_LINK_OTHER`。
    """
    return _rows(_query(startDate=start, endDate=end, metrics="views",
                        dimensions="insightTrafficSourceType", sort="-views"))

#: 維持率カーブを引く本の、この窓の再生の下限（下で実測）。
CURVE_MIN_VIEWS = 100

#: 1周に引くカーブの数の上限（1本 1クエリ。Data API の枠とは別）。
CURVE_MAX = 6

#: カーブを読む刻（動画の長さに対する割合）。
CURVE_MARKS = (0.10, 0.25, 0.50, 0.75, 0.95)


def curve(vid: str, start: str, end: str) -> dict[float, float]:
    """**維持率カーブ**（`audienceWatchRatio` × `elapsedVideoTimeRatio`・100点）。
    返りは {割合: 残っている率}。**引けなければ空**。

    **窓が狭いと、データが在っても空で返ります**（2026-09-10 16:4x に実測して踏んだ）:
    `EkNqtkK49Bw` は 窓 09/06〜09/07 で **0点**・窓 08/25〜09/07 で **100点**。
    ＝ **空を「カーブが無い」と読まないこと**（§4 (0-b) の族）。**窓は 14日 以上 取ること。**

    **下限の実測**（同じ回・窓 08/25〜09/07）: 再生 **145回 → 100点**・**76回 → 0点**
    （`PhQ2KvuQASQ`）。＝ 境目は 76〜145回 のあいだ。`CURVE_MIN_VIEWS` はその上側に置いてあります。

    **陽性対照**: `data/retention.json` の 136本（**125本 は #Shorts**）が 100点 で返るので、
    **ショートにカーブが出ないのではありません**（この回に 3本 撃って確かめた）。

    **覆る条件**: (1) 再生 `CURVE_MIN_VIEWS` を越えた本が 3本 続けて空で返ったら、
    下限ではなく**齢**の側（上流の作りが追いついていない）＝ 窓ではなく日を待つこと。
    (2) 500 が返る回がある（`9zkfjEH48PY` で 1度）——**エラーと空を分けること**。
    """
    rows = _rows(_query(startDate=start, endDate=end, metrics="audienceWatchRatio",
                        dimensions="elapsedVideoTimeRatio", filters="video==" + vid))
    return {round(float(r["elapsedVideoTimeRatio"]), 2): float(r["audienceWatchRatio"])
            for r in rows}


def curve_marks(c: dict[float, float]) -> dict[str, float] | None:
    """カーブを `CURVE_MARKS` の刻で読む。1つでも欠けたら `None`（**穴を 0 で埋めない**）。"""
    if not c:
        return None
    out = {}
    for m in CURVE_MARKS:
        v = c.get(round(m, 2))
        if v is None:
            return None
        out[f"p{int(m * 100)}"] = round(v, 3)
    return out
