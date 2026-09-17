"""**撃った API を、撃った所で 1本ずつ数える**（2026-09-17 06:2x・optimizer・Fable 5.1・ultracode）。**API 0単位**。

**踏んだ当のもの**（この回に数え直した実測・`data/studio/ledger.jsonl`）:

    枠の頭 09/16 16:00 JST（Data API の日枠は 16:00 JST に戻る）
    16:49:51  `channel`（`channels.list` **1単位**）**通った** —— subs 29・本 278
    19:01:08  `status` **403 quotaExceeded**
    21:14:44  `channel` **通った** —— subs 32・本 280（**19:01 の 403 より後です**）
    21:17:47  `watermark`（50単位）**403**
    以降 いまに至るまで **1単位 の `videos.list` も 403**（この回に撃って確かめた・06:05 JST）

**この窓で台帳に出た消費は、合わせて 数十単位 です**（`scheduled` 0件・`rethumb` 0件・
`measured` 0件 ＝ 1,600単位 の口は 1度 も撃っていません）。**それで 10,000 が尽きています。**

**＝ 枠を食っているものが、台帳の外に居ます。** `budget` の覆る条件 (1)（「台帳に `units` を
書かない口の分は入っていない ＝ この数は過小」）は**これまで「読みの口（1単位）を数えていない」の意味**で
書かれていましたが、読みの口を全部 足しても 数百単位 にしかならず、**10,000 には届きません。**

**だから推計をやめます。** `budget` は event の名から**値段表を引いて**数えていたので、
「うちが撃った物」しか数えられず、**撃っていないのに尽きている**という、いちばん知りたい形が
原理的に出ませんでした。この module は **`googleapiclient` が HTTP を撃つ 1か所**に掛けて、
**方法の名（`youtube.videos.list`）と値段と通ったかを、撃つたびに 1行**（`data/studio/api.jsonl`）
残します。次の窓は、これで 2つ に割れます:

    うちの合計が 10,000 に届いて 403     ＝ **うちが使い切っている** → 出す本数か測りの回数を減らす
    うちの合計が 数百 で 403            ＝ **別の誰かが同じ GCP プロジェクトの枠を食っている**
                                        か、**プロジェクトの割り当てが 10,000 ではない**
                                        → どちらも**オーナーの手**（別プロジェクト・枠の申請）

**どちらなのかを、いまの道具は 1度も言えたことがありません。** 09/16 03:4x の回は台帳を数えて
「5本 の予約だけで 8,250」と当てましたが、それは**その窓が たまたま うちの消費で説明できた**からで、
**この窓は説明できません。**

**値段は公表の表**（https://developers.google.com/youtube/v3/determine_quota_cost）。
**この表は写しです** —— Google が値段を変えたら、ここだけ直すこと。

**覆る条件**:
 (1) `api.jsonl` の合計と、Google Cloud の画面の消費が **2窓 続けて食い違ったら**、
     食い違うのは値段表か、掛け損ねた口（`next_chunk` の族）です ＝ まず `UNKNOWN` の行を数えること。
 (2) **`UNKNOWN` の行が 1つ でも出たら**、その `method` を `UNITS` に足すこと
     （既定は書き 50・読み 1 に寄せてあるので、黙って 2桁 外れます）。
 (3) この窓の答えが「別の誰かが食っている」だったら、**数える口はもう要りません** ——
     要るのは枠そのもの（別プロジェクトか申請）＝ そのとき この module は残してよいが、
     `budget` の印字からは外してよい（毎周 読む行を増やさない）。
 (4) 1周に 2体 以上 立てる形へ戻したら、`api.jsonl` は**周をまたいで混ざります** ——
     そのときは行に周の印を足すこと（いまは 1周 1体・オーナー 2026-09-14 20:22）。
"""
from __future__ import annotations

import datetime as dt
import json
import os

from .common import DATA, JST, LEDGER, _REAL_LEDGER, now_jst

#: 撃った 1本ごとの行（`data/studio/api.jsonl`）。**台帳とは別の綴じ**にしてあります ——
#: `ledger.jsonl` は 1周に 1回 まるごと読まれるので、1周 数十行 の読みを混ぜると そちらが重くなる。
API = DATA / "api.jsonl"

#: **方法 → 単位**（公表の表の写し・`youtube.` を落とした名で引く）。
UNITS = {
    # 読み
    "videos.list": 1,
    "channels.list": 1,
    "playlists.list": 1,
    "playlistItems.list": 1,
    "commentThreads.list": 1,
    "comments.list": 1,
    "subscriptions.list": 1,
    "captions.list": 50,
    "search.list": 100,
    # 書き
    "videos.insert": 1600,
    "videos.update": 50,
    "videos.rate": 50,
    "videos.delete": 50,
    "thumbnails.set": 50,
    "watermarks.set": 50,
    "watermarks.unset": 50,
    "channels.update": 50,
    "playlists.insert": 50,
    "playlists.update": 50,
    "playlists.delete": 50,
    "playlistItems.insert": 50,
    "playlistItems.update": 50,
    "playlistItems.delete": 50,
    "commentThreads.insert": 50,
    "comments.insert": 50,
    "comments.update": 50,
    "comments.delete": 50,
    "captions.insert": 400,
    "captions.update": 450,
}

#: 表に無い方法の既定（**黙って 0 と数えないこと** ＝ 覆る条件 (2)）。書きは 50・読みは 1。
DEFAULT_WRITE = 50
DEFAULT_READ = 1

#: Data API の日枠に**乗らない**サービス（別の枠）。行は残すが、単位は 0 で数える。
OTHER_APIS = ("youtubeAnalytics", "youtubereporting")

_installed = False


def _blocked() -> bool:
    """検査から本物の綴じへ書かない（`common._ledger_blocked` と同じ門・同じ理由）。"""
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and LEDGER == _REAL_LEDGER


def split(method_id: str) -> tuple[str, str]:
    """`youtube.videos.list` → `("youtube", "videos.list")`。形が違えば `("", 全部)`。"""
    parts = (method_id or "").split(".")
    if len(parts) >= 2:
        return parts[0], ".".join(parts[1:])
    return "", method_id or ""


def cost(method_id: str) -> int:
    """その 1本 が日枠から引く単位。**知らない方法は 0 にしない**（覆る条件 (2)）。"""
    api, name = split(method_id)
    if api in OTHER_APIS:
        return 0
    if name in UNITS:
        return UNITS[name]
    tail = name.rsplit(".", 1)[-1]
    return DEFAULT_READ if tail in ("list", "get") else DEFAULT_WRITE


def reason_of(exc) -> tuple[str, str]:
    """`googleapiclient` の失敗から **`reason` と `message` の字**を取り出す。

    **なぜ要るか**（2026-09-17 15:0x・optimizer・Fable 5.1・ultracode）:
    09/16 の窓の実測は **403 → 通った → 403** でした（`ledger` 16:49 通った・19:01 403・
    **21:14 通った**・21:17 403）。**日枠は単調なので、尽きたものが同じ窓で戻ることはありません。**
    ＝ 19:01 の 403 は「日枠 10,000 を使い切った」ではない可能性が在るのに、
    **うちの口は 403 を全部 `quota_exceeded` と書いていました**（`ledger` の event 名）。

    `reason` が 1字 残っていれば、この 2つ は次の窓で割れます:

        `quotaExceeded`／`dailyLimitExceeded`  日枠（16:00 JST まで戻らない）
        `rateLimitExceeded`／`userRateLimitExceeded`／`servingLimitExceeded`
                                             **短い窓の絞り**（待てば戻る ＝ 周を止める理由にならない）

    **実物が在ります**: `data/batch_runs.jsonl`（2026-08-24）には
    `Quota exceeded for quota metric 'Search Queries' and limit 'Search Queries per day'`
    ＝ **`reason: rateLimitExceeded`・HTTP 429** が残っていました。
    **＝ この口は、metric ごとに別の枠を持ちます。** 「日枠 10,000」1つ で読んではいけません。

    **覆る条件**: `reason` が 2窓 続けて `quotaExceeded` だけなら、この列は役目を終えます
    （そのときは `budget` の側の話 ＝ オーナーの手・`owner_ask` の `yt_quota_not_ours`）。
    """
    try:
        raw = getattr(exc, "content", None)
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8", "replace")
        if not raw:
            return "", ""
        err = (json.loads(raw) or {}).get("error") or {}
        errs = err.get("errors") or []
        reason = (errs[0].get("reason") if errs else "") or err.get("status") or ""
        return str(reason)[:64], str(err.get("message") or "")[:300]
    except Exception:  # noqa: BLE001
        return "", ""


def note(method_id: str, ok: bool, status: int | None = None, exc=None) -> None:
    """1行 足す。**ここで例外を出さないこと** —— 数えるために本番を落とさない。"""
    try:
        if _blocked():
            return
        api, name = split(method_id)
        row = {"at": now_jst().isoformat(timespec="seconds"),
               "api": api or "?", "method": name or "UNKNOWN",
               "units": cost(method_id), "ok": bool(ok)}
        if status is not None:
            row["status"] = status
        if exc is not None:
            # **403 の中身は 1種類ではありません**（上の `reason_of` の註）。
            reason, message = reason_of(exc)
            if reason:
                row["reason"] = reason
            if message:
                row["message"] = message
        if not name or (api == "youtube" and name not in UNITS):
            row["unknown"] = True
        DATA.mkdir(parents=True, exist_ok=True)
        with API.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass


def install() -> None:
    """`googleapiclient` が HTTP を撃つ 1か所 に掛ける（**何度 呼んでも 1度だけ**）。

    掛けるのは 2つ です: ふつうの `execute()` と、**積み上げの `next_chunk()`**
    （`videos.insert` は `resumable=True` なので `execute()` を通りません ＝
    **いちばん高い 1,600単位 の口が、`execute` だけ掛けると丸ごと数から落ちます**）。
    `next_chunk` は 1本 の上げで何度も呼ばれるので、**最後の 1回（resp が返った回）だけ**数えます。
    """
    global _installed
    if _installed:
        return
    from googleapiclient.http import HttpRequest

    _execute = HttpRequest.execute
    _next_chunk = HttpRequest.next_chunk

    def execute(self, *a, **kw):
        mid = getattr(self, "methodId", "") or ""
        try:
            out = _execute(self, *a, **kw)
        except Exception as e:  # noqa: BLE001
            note(mid, False, getattr(getattr(e, "resp", None), "status", None), exc=e)
            raise
        note(mid, True)
        return out

    def next_chunk(self, *a, **kw):
        mid = getattr(self, "methodId", "") or ""
        try:
            st, resp = _next_chunk(self, *a, **kw)
        except Exception as e:  # noqa: BLE001
            note(mid, False, getattr(getattr(e, "resp", None), "status", None), exc=e)
            raise
        if resp is not None:          # 上げ終わった回だけ数える（途中の塊は同じ 1本）
            note(mid, True)
        return st, resp

    HttpRequest.execute = execute
    HttpRequest.next_chunk = next_chunk
    _installed = True


def rows() -> list[dict]:
    if not API.exists():
        return []
    return [json.loads(l) for l in API.read_text(encoding="utf-8").splitlines() if l.strip()]


def spent(since: str, rows_: list[dict] | None = None) -> dict:
    """`since`（JST の ISO）からの**実測**。`total` は Data API の日枠に乗る分だけ。

    **403 で撥ねられた 1本 は、枠を 1単位 も食っていません**（Google が数える前に断る）＝
    `total` から外します。**外さないと、尽きた窓ほど実測が水増しされ**、
    `outside_line` の「うちは食っていない」が出なくなります（この回に踏んだ形の裏返し）。
    403 以外の失敗（500 など）は、食ったか分からないので**食った側に数えます**（安全側）。
    """
    total, per, n, unknown, refused = 0, {}, 0, 0, 0
    for r in (rows() if rows_ is None else rows_):
        at = r.get("at") or ""
        if not at or at < since:
            continue
        # **数えるのは Data API の口だけ**（2026-09-17 08:4x・optimizer・Fable 5.1・ultracode）。
        # `youtubeAnalytics` / `youtubereporting` は**別の枠**で、0単位 のまま `calls` を
        # 押し上げます —— 実測 09/17 08:19 の `analytics` 1回 で **9本**。
        # 「うちが 10,000 を使い切ったのか」を読む行なので、本数も Data API に揃えること。
        if (r.get("api") or "youtube") != "youtube":
            continue
        n += 1
        if r.get("unknown"):
            unknown += 1
        if not r.get("ok") and r.get("status") == 403:
            refused += 1
            continue
        u = int(r.get("units") or 0)
        if u:
            total += u
            k = r.get("method") or "?"
            per[k] = per.get(k, 0) + u
    return {"since": since, "total": total, "per": per, "calls": n,
            "unknown": unknown, "refused": refused}


def line(since: str, day_units: int, rows_: list[dict] | None = None) -> str | None:
    """`budget` が 1行 として出す字。**綴じが空なら None**（まだ 1本 も撃っていない窓）。"""
    s = spent(since, rows_)
    if not s["calls"]:
        return None
    head = (f"    実測（`api.jsonl`・撃った所で数えた）: **{s['total']:,}単位** / {day_units:,}"
            f"（{s['calls']}本" + (f"・うち 403 で撥ねられた {s['refused']}本 は 0単位" if s["refused"] else "") + "）")
    if s["per"]:
        head += " ＝ " + " ／ ".join(f"{k} {v:,}" for k, v in
                                    sorted(s["per"].items(), key=lambda x: -x[1])[:4])
    if s["unknown"]:
        head += f" ／ **値段を知らない方法 {s['unknown']}本**（`meter` の覆る条件 (2)）"
    # **403 の `reason` を、字のまま並べる**（2026-09-17 15:0x・`reason_of` の註）。
    # **`quotaExceeded` だけなら日枠・`rateLimitExceeded` が混ざれば短い窓の絞り**で、
    # 後者は**待てば戻る ＝ 周を止める理由になりません**。
    # **出どころの無い行は数えません**（`reason` の列は この回より前の行には在りません）。
    rs = reasons(since, rows_)
    if rs:
        # **`403 の` と書かないこと**（2026-09-17 16:1x に直した）—— 実際に出たのは
        # `missingRequiredParameter`／`required` の **400** で、行の字が嘘になっていました。
        head += ("\n    失敗の `reason`: " + " ／ ".join(f"**{k}** {v}本" for k, v in rs)
                 + "（`quotaExceeded`／`dailyLimitExceeded` ＝ 日枠・"
                   "`rateLimitExceeded`／`userRateLimitExceeded` ＝ **短い窓の絞り ＝ 待てば戻る**）")
    return head


def reasons(since: str, rows_: list[dict] | None = None) -> list[tuple[str, int]]:
    """`since` から先の、失敗した口の `reason` を多い順に。**この回より前の行は `reason` を持ちません。**"""
    per: dict[str, int] = {}
    for r in (rows() if rows_ is None else rows_):
        at = r.get("at") or ""
        if not at or at < since or r.get("ok"):
            continue
        k = r.get("reason")
        if k:
            per[k] = per.get(k, 0) + 1
    return sorted(per.items(), key=lambda x: -x[1])


def outside_line(since: str, day_units: int, dry: str | None,
                 rows_: list[dict] | None = None, ceiling: int | None = None) -> str | None:
    """**403 が出ているのに、うちの実測が枠に遠く届いていない**ときだけ出す 1行。

    これが出た窓は、**うちが使い切ったのではありません** —— 同じ GCP プロジェクトの枠を
    別の誰かが食っているか、割り当てが 10,000 ではない側です（この module の冒頭）。
    どちらも**オーナーの手**（別プロジェクトを作る・枠を申請する）でしか動きません。
    **門は 5割** —— 実測が枠の半分にも届いていないのに 403 なら、うちの数え落としでは説明できません
    （数え落としは読みの口 1単位 の族で、まとめて数百単位です）。
    """
    if not dry:
        return None
    s = spent(since, rows_)
    if not s["calls"] or s["total"] >= day_units // 2:
        return None
    # **綴じが窓の頭から在るときだけ言い切ること**（2026-09-17 06:3x に足した理由）——
    # この綴じは この回に足した物なので、足した窓では**頭から 14時間 が数えられていません**。
    # その窓で「うちは食っていない」と言い切ると、**道具を足した日に、いちばん強い主張が
    # いちばん弱い証拠で出ます**（この repo で通算 12回 の形）。
    first = min((r.get("at") or "" for r in (rows() if rows_ is None else rows_)
                 if (r.get("at") or "") >= since), default="")
    covered = bool(first) and (dt.datetime.fromisoformat(first)
                               - dt.datetime.fromisoformat(since)) <= dt.timedelta(hours=1)
    if not covered:
        # **綴じが窓の頭から無くても、台帳の側に上端が在れば決まります**
        # （2026-09-17 11:0x・optimizer・Opus）。この `covered` は「`api.jsonl` の前に
        # 撃った分が分からない」ことを言っていましたが、**その分は `ledger.jsonl` に出ています** ——
        # `budget.spent_ceiling` は窓の頭から数え、読みを 1行 10単位 に振って**上へ外した**数です。
        # 上端でも半分に届かないなら、綴じの穴は結論を変えません。
        # **覆る条件**: 台帳に出ない口で撃つ道具が足されたら、この逃げ道は閉じること
        # （`budget.spent_ceiling` の覆る条件 (1)）。
        if ceiling is not None and ceiling < day_units // 2:
            return ("    !! **台帳の上端でも " + f"{ceiling:,}単位" + " しか撃っていないのに 403 です** ＝ "
                    "枠を食っているのは この機械ではありません（同じ GCP プロジェクトを別の口が使っているか、"
                    f"割り当てが {day_units:,} ではない）。**この 2つ はオーナーの手でしか動きません** —— "
                    "Google Cloud Console の **YouTube Data API v3 → Quotas** で『Queries per day』の"
                    "上限と使用量を見ること（`studio/meter.py` 冒頭・`budget.spent_ceiling`）")
        return (f"    （実測の綴じは {first[5:16] or '—'} JST からしか在りません ＝ 窓の頭"
                f"（{since[5:16]} JST）からの分は数えていない ＝ **この窓では「誰が枠を食ったか」は決まりません。"
                "決まるのは次の窓です**・`studio/meter.py` 冒頭）")
    return ("    !! **うちの実測は " + f"{s['total']:,}単位（{s['calls']}本）" + "しかないのに 403 です** ＝ "
            "枠を食っているのは この機械ではありません（同じ GCP プロジェクトを別の口が使っているか、"
            "割り当てが 10,000 ではない）。**この 2つ はオーナーの手でしか動きません** —— "
            "別のプロジェクトで OAuth を取り直すか、枠の申請を出すこと（`studio/meter.py` 冒頭）")


def window_line(now: dt.datetime | None = None) -> str:
    """いまの窓の頭（`budget.window_start` と同じ刻）を ISO で。"""
    now = (now or now_jst()).astimezone(JST)
    head = now.replace(hour=16, minute=0, second=0, microsecond=0)
    if now < head:
        head -= dt.timedelta(days=1)
    return head.isoformat(timespec="seconds")
