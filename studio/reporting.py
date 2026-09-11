"""**YouTube Reporting API（一括レポート）の最小限。** 2026-09-10 18:0x・optimizer・Opus。

**Data API の日枠（10,000単位/日）は 1単位 も使いません** —— これは **3つ目の API・3つ目の枠**
（`youtubereporting.googleapis.com`）。Analytics API v2（`studio/analytics.py`）ともまた別です。
**「0単位」と書くときは、どちらの枠の話かを必ず書くこと。**

**なぜ足したか（この回に撃って測った 2つの数）**:

    Analytics API v2 の遅れ   **3日**（きょう 09/10 に引ける最後の日は 09-07・`analytics.lag_days`）
    Reporting API の遅れ      **1.07日**（実測: 期間 09-08 07:00Z〜09-09 07:00Z の報告が
                              **09-10 08:50Z に置かれた** ＝ 期間の終わりから **25.7時間**）

＝ **同じ数（本ごとの日ごとの再生・登録の増え・いいね）が、2日 早く読めます。**
§7 (o-1)「遅れ 3日 が縮むか」に対する答えで、(o-2)「5本目・6本目 が載る日（09/13 ごろ）」は
この口では **09/11〜09/12** に前倒しできます。

**仕組みが Analytics と違う**（`scripts/reach.py` の冒頭が 08/15 に書いたとおり）:
その場では返らず、ジョブを作ると YouTube が **1日1回 CSV を置いていきます**。
**作った時点から最大 30日 ぶんを遡って埋めます**（`channel_reach_basic_a1` のジョブは 64本 置かれている）。
この回に `channel_basic_a3`（本ごとの日ごとの 再生・視聴分・平均視聴秒・登録の増減・いいね）の
ジョブを作りました（**2026-09-10T09:07:27Z**）。**最初の CSV は 24〜48時間後** ＝ 次の回が拾うこと。

**日の区切りは JST ではありません（この口のいちばん高い罠）**: 報告の期間は **07:00Z 〜 翌 07:00Z**
＝ **太平洋時間の 1日**（16:00 JST 〜 翌 16:00 JST）。
＝ **10:00 JST に公開した本の最初の 6時間 は、前日の行に入ります**
（09/10 10:00 JST ＝ 09/10 01:00Z ＝ 期間 09-09 07:00Z〜09-10 07:00Z）。`pt_day()` が畳みます。
**覆る条件 (1)**: 最初の CSV が届いた回に、5本目 `2YZ_4FXC-XI`（09/10 10:00 JST 公開）の行が
**どの `date` に付いたか**を見ること —— `20260909` なら上のとおり・`20260910` ならこの段落を書き直すこと。

**インプレッションと CTR について**（この回に data から数え直した・API 0単位）:
METHOD §6・`studio/analytics.py` は「Studio だけなのはインプレッションと CTR」と書いていますが、
**この API では取れています** —— `channel_reach_basic_a1` のジョブが 2026-08-14 から回っており、
`data/reach.jsonl` に **2,095行**（07/15〜09/01）在ります。
**ただし、その数はショートの配りを測りません**（＝ 取れても答えは出ません）:
08/15〜08/30 公開・100回 以上 の **103本** で **インプレッション ÷ 再生 ＝ 11.3%**
（7,340 ÷ 65,162）・**中央値 4.5%**・**よく配られた本ほど低い**（1,800回 級の 5本 は **1.0〜5.0%**）。
＝ サムネの面はこのチャンネルの配りの 1/10〜1/20 しか見ていません（流入 SHORTS 86.7% と一致）。
**「見せられていない」か「見せたのに押されない」かを、ショートについてこの口で分けることはできません。**
**覆る条件 (2)**: `reportTypes.list()` にショートのフィードの面（インプレッション）を持つ型が出たら、
この段落を書き直すこと（この回の一覧 20型 には在りません）。

**覆る条件 (3)**: 期間の終わりから **48時間** 経っても報告が置かれない回が 2度 続いたら、
「2日 早い」は消えます ＝ この口を毎周 見るのをやめ、Analytics だけに戻すこと（`freshness()` が数を出します）。
**覆る条件 (4)**: 同じ日の報告が**置き直される**ことがあります（数の訂正）。
**書く側は報告IDで畳み、読む側は同じ日の中でいちばん新しい報告を採ること**（`latest_rows()`）。
畳まずに足すと、同じ日が二重に積まれます（`scripts/reach.py` が 08/20 に踏んだ穴の裏返し）。
"""
from __future__ import annotations

import csv
import datetime as dt
import io
import json
from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from .common import env

#: 本ごとの日ごとの 再生・視聴分・平均視聴秒・登録の増減・いいね。
REPORT_TYPE = "channel_basic_a3"

#: 積む先（`data/studio/ledger.jsonl` とは別。台帳には 1回の取り込みにつき 1行 だけ残す）。
STORE = Path("data/studio/reporting.jsonl")

#: **サムネの面（インプレッションと CTR）を持つ、もう1つのジョブ。**
#: 2026-08-14 から回っており、`scripts/reach.py`（旧道具）が 09/02 に止まってから
#: **置かれた報告を誰も読んでいません**（2026-09-10 23:5x に数えた・下の註）。
REACH_TYPE = "channel_reach_basic_a1"
#: その積む先（旧道具が書いた形のまま足す。**報告ID を持たない古い行が在ります** ——`seen_marks` の註）。
REACH_STORE = Path("data/reach.jsonl")

#: **取り込む型と、その積む先**。`cmd_reporting` はこの並びを回ります。
#: **1つの型だけを見る形に戻さないこと**（2026-09-10 23:5x・optimizer・Opus。**この回に踏んだ穴**）——
#: 18:0x は `REPORT_TYPE` 1つ だけを見ており、**同じ口に在る `channel_reach_basic_a1` の
#: 8日ぶん（09/02〜09/09・すでに置かれていた）が、道具からは 1行 も見えませんでした。**
#: ＝ §4 (0-b) の族の裏返し（**「報告 0本」は、その型の話でしかない**）。
JOBS: tuple[tuple[str, Path], ...] = ((REPORT_TYPE, STORE), (REACH_TYPE, REACH_STORE))

#: 期間の終わりから報告が置かれるまでの実測（2026-09-10・25.7時間）。これを越えたら註の (3)。
LATE_H = 48.0

_svc = None


def svc():
    global _svc
    if _svc is None:
        creds = Credentials(token=None, refresh_token=env("YT_REFRESH_TOKEN"),
                            token_uri="https://oauth2.googleapis.com/token",
                            client_id=env("YT_CLIENT_ID"), client_secret=env("YT_CLIENT_SECRET"))
        _svc = build("youtubereporting", "v1", credentials=creds, cache_discovery=False)
    return _svc


def jobs(service=None) -> list[dict]:
    return (service or svc()).jobs().list().execute().get("jobs", [])


def job_for(report_type: str, js: list[dict]) -> dict | None:
    """その型のジョブ（無ければ `None`。**空の dict を返さないこと** ——
    「無い」と「在るが空」を分けるのは §4 (0-b) の族）。"""
    return next((j for j in js if j.get("reportTypeId") == report_type), None)


def create_job(report_type: str, name: str = "studio", service=None) -> dict:
    return (service or svc()).jobs().create(
        body={"reportTypeId": report_type, "name": name}).execute()


def reports(job_id: str, service=None) -> list[dict]:
    """その ジョブに置かれた報告の一覧（**期間の終わりの順**）。"""
    res = (service or svc()).jobs().reports().list(jobId=job_id).execute()
    return sorted(res.get("reports", []), key=lambda r: r.get("endTime", ""))


def _t(s: str) -> dt.datetime | None:
    """RFC3339（`...Z`・小数秒つき）を UTC の時刻に。空なら `None`。"""
    if not s:
        return None
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return dt.datetime.fromisoformat(s)


def freshness(reps: list[dict], now: dt.datetime | None = None) -> dict | None:
    """**いちばん新しい報告は、どこまでの数で、何時間 遅れているか。**

    返り: `{"end": 期間の終わり, "lag_h": いまから何時間前までの数か,
            "made_h": 期間の終わりから置かれるまでの時間, "late": LATE_H を越えたか}`。
    **報告が 1本 も無ければ `None`（0 ではない）** —— ジョブを作った直後はこれが正しい姿です。
    """
    if not reps:
        return None
    r = max(reps, key=lambda x: x.get("endTime", ""))
    end, made = _t(r.get("endTime", "")), _t(r.get("createTime", ""))
    now = now or dt.datetime.now(dt.timezone.utc)
    return {"end": end, "lag_h": round((now - end).total_seconds() / 3600, 1),
            "made_h": (None if not made else round((made - end).total_seconds() / 3600, 1)),
            "late": bool(made and (made - end).total_seconds() / 3600 > LATE_H)}


def _end_mark(when: str) -> str:
    """報告の**期間の終わり**を、書き方の違いに依らない鍵に（空なら空）。"""
    t = _t(when)
    return "end:" + t.isoformat() if t else ""


def seen_marks(path: Path | None = None) -> set[str]:
    """**もう積んだ報告の見分け** —— 報告ID と、**期間の終わり**の両方。
    **追記しかしない store なので、ここで畳まないと同じ日が二重に積まれます。**

    **2つ 見るのは、古い store が報告ID を持たないからです**（2026-09-10 23:5x・optimizer・Opus）。
    `data/reach.jsonl` は旧道具 `scripts/reach.py` が書いたもので、行に在るのは `_report_end` だけ。
    **ID だけで見分けると、その 2,095行 は「1本も積んでいない」と読めます** ——
    そのまま `unseen` に渡せば 64本 を全部 落とし直し、**同じ日を二重に積みます**（註の (4) の当のもの）。
    ＝ **「0件」を「起きていない」と読む形**（§4 (0-b) の族）が、畳む側にも在りました。

    **覆る条件**: 同じ期間の終わりで報告が**置き直された**とき（数の訂正・註の (4)）、
    期間の終わりを鍵にすると訂正版を落とせません。**ID を持つ store（`STORE`）では
    ID のほうが先に当たる**ので効きませんが、`REACH_STORE` の古い行だけは訂正を取り込めません
    —— 訂正を追う必要が出たら、その store を **1度だけ** 作り直すこと（報告は 60日 残ります）。
    """
    p = path or STORE
    if not p.exists():
        return set()
    out: set[str] = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("_report_id"):
            out.add(str(row["_report_id"]))
        for k in ("_period_end", "_report_end"):
            if row.get(k):
                out.add(_end_mark(str(row[k])))
    out.discard("")
    return out


def unseen(reps: list[dict], seen: set[str]) -> list[dict]:
    """**まだ積んでいない報告は、全部 返すこと。**

    `scripts/reach.py` は 08/20 まで `reports[-3:]` しか落としておらず、
    **在るのに一度も読んでいない日**が残っていました（ジョブは 30日 遡って埋めます）。
    ここで件数を切らないのは、その穴の裏返しです。

    見分けは **ID と 期間の終わり の両方**（`seen_marks` の註）。
    """
    return [r for r in reps
            if str(r.get("id", "")) not in seen
            and _end_mark(str(r.get("endTime", ""))) not in seen]


def parse(text: str, rep: dict) -> list[dict]:
    """CSV 1本 を行の並びに。**どの報告から来たか**を各行に残します（畳む側が使う）。"""
    out = []
    for row in csv.DictReader(io.StringIO(text)):
        row["_report_id"] = str(rep.get("id", ""))
        row["_period_end"] = rep.get("endTime", "")
        row["_created"] = rep.get("createTime", "")
        out.append(row)
    return out


def download(rep: dict, service=None) -> str:
    service = service or svc()
    return service._http.request(rep["downloadUrl"])[1].decode("utf-8")  # noqa: SLF001


def append(rows: list[dict], path: Path | None = None) -> int:
    p = path or STORE
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    return len(rows)


def load_rows(path: Path | None = None) -> list[dict]:
    p = path or STORE
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


#: **この報告は「1日1本 1行」ではありません。** `channel_basic_a3` の 1行 は
#: **（日・本・国・登録の有無・生か収録か）** で割れており、1本1日 が **6行** になることが在ります
#: （実測 2026-09-11 17:5x: `lQHX9LJ80Sg` の 09/08 は ZZ 0回 / JP 232回 / US 1回 / HK 1回 /
#:   BR 1回 / JP(登録者) 3回 の **6行**）。**読む側は、その日のぶんを足すこと。**
DIMS = ("country_code", "subscribed_status", "live_or_on_demand",
        "traffic_source_type", "traffic_source_detail", "device_type",
        "operating_system", "playback_location_type")


def _dim_key(r: dict) -> tuple:
    """同じ報告の中で行を見分ける鍵（**次元の組**）。無い欄は空で埋める。"""
    return tuple(str(r.get(d, "")) for d in DIMS)


def latest_rows(rows: list[dict]) -> list[dict]:
    """同じ（日・本）が 2度 置かれていたら、**いちばん新しい報告のほうを採る**（註の (4)）。

    数の訂正で報告は置き直されます。**古いほうを混ぜて足すと、その日が二重になります。**

    **【2026-09-11 17:5x・optimizer・Opus】(日・本) で 1行 に畳んでいました ＝ 次元の行を捨てていた。**
    18:0x の形は `best[(date, video)] = r` で、**同じ日の残りの行を黙って落とします**。
    実測（この回に初めて a3 の CSV が届いて撃った）: `lQHX9LJ80Sg` の 09/08 は
    **JP 232回** が在るのに、道具は**先に来た `ZZ` の行（0回）**だけを返し、
    `views_by_day` は「**0908 0回 → 0909 1回**」と印字していました（台帳の側は 692回）
    ＝ **2桁 小さい側へ、しかも「止まっている」向きへ外れます。**
    §7 (o-4)(3) は「**複製から返らない唯一の口で、(m) を外から当てられるのはここだけ**」と
    言っている当のものなので、ここが外れると当て先ごと狂います。
    いまは**いちばん新しい報告の行を全部**返し、**足すのは読む側**（`views_by_day` / `reach_by_day`）。
    同じ次元の行が二重に積まれていても `_dim_key` で 1つ に畳みます。
    """
    best: dict[tuple[str, str], tuple[str, dict[tuple, dict]]] = {}
    for r in rows:
        key = (r.get("date", ""), r.get("video_id", ""))
        created = str(r.get("_created", ""))
        cur = best.get(key)
        if cur is None or created > cur[0]:
            best[key] = (created, {_dim_key(r): r})
        elif created == cur[0]:
            cur[1][_dim_key(r)] = r
    return [r for _, d in best.values() for r in d.values()]


def pt_day(when: dt.datetime) -> str:
    """その時刻が入る**報告の日**（太平洋時間の日 ＝ 期間 07:00Z〜翌 07:00Z）を `YYYYMMDD` で。

    **10:00 JST の公開は、前日の行に入ります**（09/10 10:00 JST → `20260909`）。
    ＊夏時間の切り替えで 07:00Z は 08:00Z になります（11月〜3月）。
    **覆る条件**: 冬の報告の `_period_end` が `08:00Z` になっていたら、この 07:00 を実物から取ること。
    """
    u = when.astimezone(dt.timezone.utc) - dt.timedelta(hours=7)
    return u.strftime("%Y%m%d")


def reach_by_day(rows: list[dict], video_id: str) -> list[tuple[str, int, float]]:
    """1本の「報告の日 → サムネのインプレッション・CTR(%)」（`channel_reach_basic_a1`）。

    **これはショートの配りを測りません**（モジュールの註・実測 インプレッション ÷ 再生 11.3%）。
    使える所は 1つ だけ: **再生 0回 の本に、この面の数が付いているか** ——
    付いていれば「見せたのに押されない」側の証拠が 1つ、0 なら「この面には出ていない」までです
    （**「配られていない」ではありません** —— この面は配りの 1/10〜1/20 しか見ていない）。

    **次元で割れた行は日ごとに足します**（`latest_rows` の註）——
    CTR は**インプレッションで重みを付けた平均**（行ごとの %をそのまま平均しないこと）。
    """
    imp: dict[str, float] = {}
    clicks: dict[str, float] = {}
    for r in latest_rows(rows):
        if r.get("video_id") != video_id:
            continue
        d = r.get("date", "")
        i = float(r.get("video_thumbnail_impressions") or 0)
        imp[d] = imp.get(d, 0.0) + i
        clicks[d] = clicks.get(d, 0.0) + i * float(r.get("video_thumbnail_impressions_ctr") or 0)
    return sorted((d, int(v), (clicks[d] / v * 100 if v else 0.0)) for d, v in imp.items())


def views_by_day(rows: list[dict], video_id: str) -> list[tuple[str, int]]:
    """1本の「報告の日 → 再生」。**`videos.list` の複製とは別の口**（§7 の「割れた読み」を外から当てられます）。

    **1日は 1行 ではありません** —— 国・登録の有無・生か収録か で割れた行を**足します**
    （`latest_rows` の註・2026-09-11 17:5x に直した。それまでは 1行 だけを採り、
    `lQHX9LJ80Sg` の 09/08 を **232回 → 0回** と読んでいました）。
    """
    tot: dict[str, int] = {}
    for r in latest_rows(rows):
        if r.get("video_id") != video_id:
            continue
        d = r.get("date", "")
        tot[d] = tot.get(d, 0) + int(float(r.get("views") or 0))
    return sorted(tot.items())
