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

from .common import JST, env

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


def day_end_jst(date: str) -> dt.datetime:
    """報告の日 `YYYYMMDD` の**期間の終わり**を JST で（＝ 翌日の 16:00 JST）。

    報告の期間は 07:00Z 〜 翌 07:00Z ＝ **16:00 JST 〜 翌 16:00 JST**（`pt_day` の裏）。
    ＊夏時間の切り替えで 07:00Z は 08:00Z になります（11月〜3月）——`pt_day` と同じ覆る条件。

    **この境目が、この口のいちばん使える所です**: 公開は 10:00 JST に固定なので、
    **その本の最初の報告の日の終わりは、齢 6.0時間 ちょうど**。
    `trend.hold` が「6h ちょうどの点が無いので挟みで読む」と毎周 書いている当の点が、
    **複製から返らない口で 1本に 1つ 立ちます**（`trend.report_vs_ledger` が印字する）。
    """
    d = dt.datetime.strptime(date, "%Y%m%d")
    return dt.datetime(d.year, d.month, d.day, 16, tzinfo=JST) + dt.timedelta(days=1)


def missing_days(rows: list[dict]) -> list[str]:
    """積んだ行の**最初の日から最後の日まで**で、1行 も無い日（＝ 穴）。

    **なぜ数えるか（2026-09-11 18:4x・optimizer・Opus。この回に踏んだ）**:
    17:5x の回は 報告 **21本**（30日 のうち **20日**）で `views_by_day` を読み、
    **10日 が穴**でした（08/12・08/15・08/16・08/18・08/22・08/27・09/02・09/04・09/05・**09/07**）。
    そのうち **09/07 は `lQHX9LJ80Sg` の最初の 6時間**（09/08 10:00〜16:00 JST）で、
    穴のままだと**その本の累計が 256回 低く出ます**。
    **印字はどこにも「穴が在る」と言っていませんでした** —— `cli.cmd_reporting` は
    「報告 N本」と「報告の日 最初〜最後」しか出さないので、**間が抜けていても同じ顔で出ます。**
    ＝ §6 `cli.comments_to_show` の 01:4x・`trend.pair_gap` の 02:2x と**同じ族**
    （数は出るのに、その数が全部そろっているかが出ない）。

    **穴の出どころは 遡りの途中**でした: **同じ回の 1時間 後（18:4x）に撃ち直したら 31本・穴 0日**
    ＝ ジョブを作った直後の遡り（30日）は**まとめて置かれず、数時間かけて埋まります**。
    ＝ **「報告 N本」は動いている数で、30日 ぶんがそろうまでは読む側が穴を踏みます。**

    **覆る条件**: (1) 穴が **2周 続けて同じ日**に残ったら、それは遡りの途中ではなく
        置かれない日 ＝ そのときは `freshness`（いちばん新しい報告だけを見る）ではなく
        **日の数**で遅れを見ること。
    (2) 遡りが 30日 より長い口が来たら（ジョブの作成から 30日 を越えた回）、
        最初の日は遡りの縁なので、縁の 1日 は穴に数えないこと。
    """
    days = sorted({r.get("date", "") for r in rows if r.get("date")})
    if len(days) < 2:
        return []
    a = dt.datetime.strptime(days[0], "%Y%m%d").date()
    b = dt.datetime.strptime(days[-1], "%Y%m%d").date()
    have = set(days)
    out, d = [], a
    while d <= b:
        k = d.strftime("%Y%m%d")
        if k not in have:
            out.append(k)
        d += dt.timedelta(days=1)
    return out


def cum_views(rows: list[dict], video_id: str) -> list[tuple[str, int, int]]:
    """1本の「報告の日 → その日の再生・**その日までの累計**」。

    **累計が使えるのは穴が無いときだけです**（`missing_days`）—— 穴の日のぶんは黙って抜けます。
    """
    out, c = [], 0
    for d, v in views_by_day(rows, video_id):
        c += v
        out.append((d, v, c))
    return out


def channel_reach(rows: list[dict], days: int = 7) -> list[tuple[str, int, int, float]]:
    """**チャンネル ぜんたい**の「報告の日 → 面（インプレッション）・押された数・CTR(%)」。

    `reach_by_day` は 1本ぶんで、**チャンネルの合計を出す口がありませんでした**
    （2026-09-16 13:5x に足した）。**足した理由は、合計にしか出ない形が在るからです** ——
    この回に手で足したら:

        日        面      押された   CTR
        08/28   **2,000**   28     1.40%
        09/01     1,199     10     0.83%
        09/05       415     10     2.41%
        09/08       245     12     **4.90%**
        09/11     **166**    6     3.61%

    **CTR は 4〜6倍 に上がり、同じ窓で面が 1/12 に落ちています**（掛け算は 28 → 6 ＝ 1/4.7）。
    ＝ **率が良くなっているのに、量が勝って絶対値が落ちている。**
    `trend` は再生しか見ていないので、**この形はどの門にも鳴っていませんでした。**

    **この口はショートの配りを見ません**（モジュールの註・実測 面 ÷ 再生 11.3%）——
    ここに出るのは長尺・ブラウズ側です。**「配られていない」とは読まないこと。**

    **覆る条件**: (1) 報告は 1〜2日 遅れて置かれます ＝ **いちばん新しい 2日 を「落ちた」と読まないこと**
    （その 2日 はまだ全部の行が来ていない）。(2) 新しい長尺の面がこの表に立ち始めたら、
    落ちが「古い本が枯れた」のか「抑えられた」のかが分かれます —— そのときに読み直すこと。
    """
    imp: dict[str, float] = {}
    clicks: dict[str, float] = {}
    for r in latest_rows(rows):
        d = r.get("date", "")
        i = float(r.get("video_thumbnail_impressions") or 0)
        imp[d] = imp.get(d, 0.0) + i
        clicks[d] = clicks.get(d, 0.0) + i * float(r.get("video_thumbnail_impressions_ctr") or 0)
    out = [(d, int(v), int(round(clicks[d])), (clicks[d] / v * 100 if v else 0.0))
           for d, v in sorted(imp.items())]
    return out[-days:] if days else out


def reach_line(rows: list[dict] | None = None, days: int = 7) -> str:
    """`trend` が毎周 印字する 1行（**API 0単位**・台帳だけ）。`channel_reach` の註が出どころ。"""
    # **`REACH_STORE` から読むこと**（既定の `STORE` ではありません・2026-09-16 14:0x に踏んだ）——
    # `latest_rows` の鍵は (日・本) で **報告の種類を見ません**。既定の store には
    # `channel_basic_a3`（面の欄を持たない側）の行が入っていて `_created` が新しいので、
    # 同じ (日・本) の面の行を**黙って押し出します** ＝ 表が 7日 とも 0 になります
    # （この回に実際にそう出た。**赤は出ません** —— 0 は「面が無かった」と同じ字だからです）。
    rows = load_rows(REACH_STORE) if rows is None else rows
    tbl = channel_reach(rows, days)
    if not tbl:
        return ("**面（サムネのインプレッション）**: 報告が 1行も在りません"
                "（`python -m studio.cli report --reach` を撃つこと）")
    head = " → ".join(f"{d[4:]} 面{i}・押{c}・{r:.1f}%" for d, i, c, r in tbl)
    first, last = tbl[0], tbl[-1]
    di = (last[1] / first[1]) if first[1] else 0.0
    dc = (last[3] / first[3]) if first[3] else 0.0
    return (f"**面（サムネのインプレッション・チャンネル合計・`reporting.channel_reach`・**Data API 0単位**）"
            f"・最後の報告の日 {last[0][4:]}**: {head}"
            f"　＝ この窓で **面 ×{di:.2f}・CTR ×{dc:.2f}**。"
            "**率と量は別の腕です** —— CTR（題とサムネ）が上がっても、面が落ちれば押された数は落ちます。"
            "**いちばん新しい 2日 は報告がまだ揃っていないので、そこだけで「落ちた」と読まないこと**"
            "（`channel_reach` の覆る条件 (1)）。**この口はショートの配りを見ません**（同 註）")


# ---------------------------------------------------------------------------
# **新しい本に配られる面（trial impressions）** —— 2026-09-18 11:2x・optimizer・Opus
# ---------------------------------------------------------------------------

#: 公開の刻の出どころ（**2つ を合わせる**。片方だけを見ないこと）。
#: `data/studio/ledger.jsonl` の `scheduled` は studio が出した本だけ（09/05 以降・39本）で、
#: **285本 のうち大半は旧道具が出しており、そちらは `data/uploaded.jsonl` にしか在りません。**
_UPLOADED = Path("data/uploaded.jsonl")
_LEDGER_FOR_PUB = Path("data/studio/ledger.jsonl")


def publish_days() -> dict[str, str]:
    """`video_id` → **報告の日**（`pt_day`）。台帳 2つ を合わせる。

    **`pt_day` で返すこと** —— 面の行の `date` は太平洋時間の日で、JST の日と 1日 ずれます
    （`pt_day` の註）。**JST の日で突き合わせると、公開日の面が丸ごと「前日」に落ちます。**
    """
    out: dict[str, str] = {}

    def put(vid: str, when: str) -> None:
        if not vid or not when or vid in out:
            return
        try:
            t = dt.datetime.fromisoformat(str(when).replace("Z", "+00:00"))
        except ValueError:
            return
        if t.tzinfo is None:
            t = t.replace(tzinfo=JST)
        out[vid] = pt_day(t)

    for path, when_keys in ((_LEDGER_FOR_PUB, ("publish_at",)),
                            (_UPLOADED, ("at", "uploaded_at"))):
        if not path.exists():
            continue
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                r = json.loads(line)
            except json.JSONDecodeError:
                continue
            for k in when_keys:
                if r.get(k):
                    put(str(r.get("video_id", "")), r[k])
                    break
    return out


def trial_reach(rows: "list[dict] | None" = None, window_days: int = 7,
                first_day: str = "20260818", last_day: "str | None" = None) -> dict:
    """**1本の新しい本が、公開から `window_days` のあいだに何回 面に出たか。**

    **なぜこの数か（2026-09-18 11:2x に初めて数えた・`trend`／`status` はどちらも持っていなかった）**:

        窓 08/18〜09/05 に出した **232本**    面の中央 **12.5**・押されたの中央 **0**
                                            面の平均 64.4・押されたの平均 1.13
                                            p90 85 ／ p99 1,484 ／ 最大 1,946
        その 232本 の合計                    面 **14,938**・押された **262**

    ＝ **ふつうの新しい本は、1週間で 13回 しか面に出ません。**
    **`long_per_video` の「長尺 1回/本」は、ここで説明が付きます** ——
    面 13回 × CTR 2% ＝ **1回**。**謎ではありませんでした。**

    **この数が効かせる決め（ここが大事）**: 面が 13回 なら、**CTR を何倍にしても再生は動きません**
    （13 × 20% ＝ 2.6回）。**題・サムネ・分かりやすさ・読みの輪は、全部 CTR の腕**です。
    ＝ **縛っている腕は面のほうで、そこに手が届いていない。**
    **この行を読まずに CTR の手を選んだ回は、効かない腕を磨いています。**

    **この口はショートの配りを見ません**（モジュールの註・面 ÷ 再生 11.3%）。
    ＝ **ここに出るのは長尺・ブラウズ側の配り**で、ショートは別（`analytics` の `SHORTS` 93.9%）。

    **覆る条件**:
      (1) 報告が止まっています（`reach_stale_days`）。**止まったままの窓を伸ばさないこと。**
      (2) 面の中央が **100回 を越えた**回が出たら、そこで初めて CTR が縛る腕になります
          —— そのときに `thumb.py`／題の手を上へ戻すこと。
      (3) `publish_days` に刻の無い本は分母から落ちています（`n` と台帳の本数を比べること）。
    """
    import statistics
    rows = load_rows(REACH_STORE) if rows is None else rows
    pub = publish_days()
    per: dict = {}
    for r in latest_rows(rows):
        vid, day = r.get("video_id", ""), r.get("date", "")
        if not vid or not day:
            continue
        i = float(r.get("video_thumbnail_impressions") or 0)
        c = i * float(r.get("video_thumbnail_impressions_ctr") or 0)
        per.setdefault(vid, []).append((day, i, c))
    imps: list = []
    clicks: list = []
    for vid, days in per.items():
        p = pub.get(vid)
        if not p or p < first_day or (last_day and p > last_day):
            continue
        end = (dt.datetime.strptime(p, "%Y%m%d")
               + dt.timedelta(days=window_days)).strftime("%Y%m%d")
        imps.append(sum(i for d, i, _ in days if p <= d <= end))
        clicks.append(sum(c for d, _, c in days if p <= d <= end))
    if not imps:
        return {"n": 0}
    s = sorted(imps)
    return {"n": len(s), "window_days": window_days,
            "median": statistics.median(s), "mean": statistics.mean(s),
            "p90": s[min(len(s) - 1, int(len(s) * 0.9))], "max": s[-1],
            "clicks_median": statistics.median(sorted(clicks)),
            "clicks_mean": statistics.mean(clicks),
            "imp_sum": sum(s), "clicks_sum": sum(clicks)}


def reach_stale_days(rows: "list[dict] | None" = None,
                     now: "dt.datetime | None" = None) -> float:
    """**面の報告が何日 止まっているか**（いちばん新しい `date` から きょうまで）。

    **足した理由（2026-09-18 11:2x に踏んだ）**: `python -m studio.cli reporting` は
    **`403 SERVICE_DISABLED`（YouTube Reporting API がプロジェクト 219932230272 で無効）**
    を返しており、面の行は **2026-09-11 で止まっています**。
    それでも `reach_line` は台帳に残った古い 7日 を毎周 元気に印字していたので、
    **7日 のあいだ 誰も気づきませんでした** ＝ **黙って凍る盤**。
    「0」と「報告が来ていない」が同じ字になる族（`reach_line` の註と同じ罠）。

    **覆る条件**: プロジェクトで API を戻した回が出たら、この註の日付と 403 の行を書き直すこと。
    """
    rows = load_rows(REACH_STORE) if rows is None else rows
    days = [r.get("date", "") for r in rows if r.get("date")]
    if not days:
        return float("inf")
    now = now or dt.datetime.now(JST)
    # **報告の日の「終わり」から数えること**（`pt_day` の逆・2026-09-18 11:3x に検査が捕まえた）。
    # `date` は太平洋時間の日 ＝ 期間は **その日の 07:00Z 〜 翌日 07:00Z**。
    # 日の**始まり**（JST 00:00）から数えると、止まっていない報告を **1.5日 遅れ**と印字します
    # ＝ 門（3日）を偽で鳴らす向き。
    end = (dt.datetime.strptime(max(days), "%Y%m%d")
           + dt.timedelta(days=1)).replace(hour=7, tzinfo=dt.timezone.utc)
    return round((now - end).total_seconds() / 86400.0, 1)


def trial_reach_line(rows: "list[dict] | None" = None,
                     now: "dt.datetime | None" = None) -> str:
    """`trend`／`status` が毎周 印字する 1行（**どの API も 0単位**・台帳だけ）。

    `now` は検査のための口（既定は いま）。**止まりの日数は `reach_stale_days` が数えます。**
    """
    rows = load_rows(REACH_STORE) if rows is None else rows
    d = trial_reach(rows)
    stale = reach_stale_days(rows, now=now)
    # **止まりの報せは、数えられない回でも出すこと**（2026-09-18 11:3x に検査が捕まえた）——
    # 「数えられる本が 1本も在りません」で早く返すと、**報告が止まっている周ほど
    # 警告が消えます**（＝ いちばん要る回に黙る向き。この repo の「0 と 無い を同じ字にする」族）。
    tail = (f"　**⚠ 面の報告は {stale:.0f}日 止まっています**"
            "（`reach_stale_days`・実測 `403 SERVICE_DISABLED` ＝ "
            "Reporting API がプロジェクトで無効）**＝ この数は古い窓のものです。**"
            ) if stale >= 3 else ""
    if not d.get("n"):
        return ("**新しい本に配られる面**: 数えられる本が 1本も在りません"
                "（`trial_reach` の覆る条件 (3)）" + tail)
    head = (f"**新しい本に配られる面（`reporting.trial_reach`・公開から {d['window_days']}日・"
            f"どの API も 0単位）**: {d['n']}本 の中央 **{d['median']:.0f}回**"
            f"（平均 {d['mean']:.0f}・p90 {d['p90']:.0f}・最大 {d['max']:.0f}）"
            f"・押されたの中央 **{d['clicks_median']:.0f}**（平均 {d['clicks_mean']:.2f}）"
            f"・合計 面 {d['imp_sum']:.0f} → 押された {d['clicks_sum']:.0f}")
    body = ("　＝ **面が 2桁 なら CTR は縛っていません**（13 × 20% ＝ 2.6回）。"
            "**題・サムネ・分かりやすさ・読みの輪は全部 CTR の腕**で、"
            "**縛っているのは面のほう**（`trial_reach` の註・覆る条件 (2)）。"
            "**この口はショートの配りを見ません**（`channel_reach` の註）")
    return head + body + tail


def trial_reach_short(rows: "list[dict] | None" = None,
                      now: "dt.datetime | None" = None) -> str:
    """`status` に置く短い形（`trial_reach_line` の長い形と対。**同じ段落を 2度 読ませない**）。

    **`status` にも置く理由**: **固定2（期限内に届くか）は立った側がいちばん最初に答える問い**で、
    そのとき最初に撃つのが `status` です。**この行が無いと、その回は
    「CTR の腕（題・サムネ・分かりやすさ）を磨く」を最初の手に選びます** ——
    面が 2桁 のあいだ、それは効かない腕です（`trial_reach` の註）。

    **覆る条件**: `status` と `trend` を同じ周に両方 読む形でなくなったら、片方に畳むこと
    （`trend.yen_now_short` と同じ行）。
    """
    d = trial_reach(rows)
    if not d.get("n"):
        return ""
    stale = reach_stale_days(rows, now=now)
    s = (f"**新しい本に配られる面 中央 {d['median']:.0f}回/本**（{d['n']}本・押された中央 "
         f"{d['clicks_median']:.0f}・合計 面 {d['imp_sum']:.0f} → 押された {d['clicks_sum']:.0f}）"
         f" ＝ **縛っているのは面で、CTR ではありません**"
         f"（題・サムネ・分かりやすさ・読みの輪は全部 CTR の腕・derivation は "
         f"`reporting.trial_reach`・**どの API も 0単位**）")
    if stale >= 3:
        s += f"　**⚠ 報告は {stale:.0f}日 止まっています**（`reach_stale_days`・403 SERVICE_DISABLED）"
    return s
