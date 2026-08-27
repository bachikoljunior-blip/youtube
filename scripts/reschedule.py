#!/usr/bin/env python3
"""**予約中の動画の、公開時刻だけを動かす／予約を外す。**

    python scripts/reschedule.py --list                     # 予約の一覧（同じテーマの二重予約に印）
    python scripts/reschedule.py --move <videoId> 2026-09-04T09:00
    python scripts/reschedule.py --unschedule <videoId>     # 予約を外す（private のまま残る）
    python scripts/reschedule.py --compact                  # 予約を前に詰める割り当て（API 0単位）
    python scripts/reschedule.py --compact --apply          # そのとおりに撃つ（1本50単位）

## なぜ要るか（2026-08-15 23:0x）

`docs/trigger_main.md` §5 は「予約済みの本は**公開時刻・題名・サムネなら
API で差し替えられる**」と書いていますが、**時刻を動かす道具がありませんでした**
（あるのは `retitle.py` と `refresh_thumbnail.py` だけ）。

必要になったのは、`src/history.py` が予約中の動画を見落としていたせいで
**同じテーマが2本ずつ予約に入った**からです（`s-tedori-1` `s-iryohi-1`
`s-kojo-2` `s-kojo-3` の4組）。YouTube は「同じチャンネルの動画を続けて数本
視聴した後、繰り返しのように感じられる可能性のあるコンテンツ」を
**収益化の対象外**と書いています。**収益化されなければ収入はゼロ**なので、
片方を止めるのは見栄えの話ではありません。

## なぜ消さずに「予約を外す」のか

**消すと戻せません。** 予約を外した動画は private のまま残るので、
判断が間違っていたと分かれば時刻を入れ直すだけで戻ります。
説明欄の `[t:テーマID]` も残るので、**投稿済みの数え方は変わりません**
（同じテーマの新しいほうが予約に入っているので、そちらが公開されます）。

## 分かっている穴

- **公開済みの動画には効きません**（`publishAt` は予約中のものだけ）
- 時刻は **JST で受けて UTC に直します**。`upload_only.py` と同じ約束
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import functools  # noqa: E402

from googleapiclient.errors import HttpError  # noqa: E402

from src import (auth, dupes, forms, history, measure_window,  # noqa: E402
                 upload_cap, uploader)

JST = timezone(timedelta(hours=9))
# `--compact` で詰める日数の**床**。判定に要る3日＋1日（`compact_plan` の節）。
# **穴が空くときは、ここから上へ自動で探します**（`_compact`）。
DEFAULT_MAX_DAYS = 4
# `--spread` の1日あたりの Shorts の上限。**08/20 の実測**（`spread_plan` の節）:
# 25本出して、公開の早い10本は 185〜1,394、**11本目から先は 0〜3**。
# 1日の合計は 4本の日（5,301）と 25本の日（5,948）でほぼ同じでした。
#
# **2026-08-24: 定数をやめて、計器（`src/day_cap.py`）から取ります。**
# 上限は測り直しで動きます（この日 17本 → 10本）。定数のままだと、
# **上限が上がっても下がっても、置き方が付いていきません**。
# `day_cap` が読めない・崩れを観測していない回は、既定の 10 に落ちます。
@functools.cache
def _measured_per_day(fallback: int = 10) -> int:
    """**呼ばれたときに測ります**（import では読みません。`views.jsonl` は1万行あり、
    ここを import 時に読むと全部の道具の起動が遅くなります）。"""
    try:
        from src import day_cap
        m = day_cap.measure()
        return int(m["cap"]) if m.get("measured") else fallback
    except Exception:
        return fallback


DEFAULT_PER_DAY = 10          # **読めない回の既定**。実際に使う数は `_measured_per_day()`
MARKER = re.compile(r"\[t:([a-z0-9\-]+)\]")


def _is_quota(exc: Exception) -> bool:
    """日枠切れ（403 quotaExceeded）かどうか。

    **本文で見ています。** `resp.status` だけだと、権限が無い 403 と
    区別が付かず、**直し方が正反対**（待てば直る／待っても直らない）になります。
    """
    if not isinstance(exc, HttpError) or getattr(exc.resp, "status", None) != 403:
        return False
    # **`str(exc)` だけを見ないこと。** `HttpError.__str__` が出すのは
    # 解釈できた `reason` の1行で、`errors[].reason` はそこに載りません
    # （解釈に失敗すると `Forbidden` とだけ出ます）。**中身のほうを読みます。**
    body = getattr(exc, "content", b"") or b""
    if isinstance(body, bytes):
        body = body.decode("utf-8", "replace")
    return "quotaExceeded" in (str(exc) + body)


def _scheduled(svc) -> list[dict]:
    """予約中（`publishAt` を持つ）動画を、公開時刻の順に返す。

    **取り口は `history.channel_video_ids` と1つにします。** uploads
    プレイリストだけを読むと、**予約中の動画がまるごと落ちます**
    （落ちるのは、まさにここで見たいものだけ）。
    """
    ch = svc.channels().list(part="contentDetails", mine=True).execute()
    uploads = ch["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    ids = history.channel_video_ids(svc, uploads)

    rows = []
    for i in range(0, len(ids), 50):
        for v in svc.videos().list(part="snippet,status",
                                   id=",".join(ids[i:i + 50])).execute()["items"]:
            at = v["status"].get("publishAt")
            if not at:
                continue
            m = MARKER.search(v["snippet"].get("description", ""))
            rows.append({"id": v["id"], "at": at, "topic": m.group(1) if m else "",
                         "title": v["snippet"]["title"]})
    return sorted(rows, key=lambda r: r["at"])


def _forms_of(rows: list[dict]) -> dict[str, bool]:
    """予約中の本を、**ショートか長尺か**に分ける（動画ID → ショートなら True）。

    `src.forms.classify()` に任せます —— 実測（`data/video_forms.json`）→
    秒数 → 題名の `#Shorts` の順で決まる、この repo で唯一の決め方です。
    **予約中の本は Analytics にまだ出ない**ので、実測は当たりません。
    そこで秒数を控え（`data/uploaded.jsonl`）から足してから訊きます。
    """
    dur: dict[str, float] = {}
    try:
        from src import dupes as _dupes
        for row in _dupes.ledger_rows():
            vid, sec = row.get("video_id"), row.get("duration_s")
            if vid and sec:
                dur[str(vid)] = float(sec)
    except Exception:                                          # noqa: BLE001
        pass

    from src import forms as _forms
    measured = _forms.measured_forms()
    out = {}
    for r in rows:
        row = {"id": r["id"], "title": r.get("title") or ""}
        if r["id"] in dur:
            row["duration_s"] = dur[r["id"]]
        out[r["id"]] = _forms.classify(row, measured)[0]
    return out


def _show(rows: list[dict]) -> None:
    """予約の一覧。**同じテーマの二重予約に印を付ける。**

    ## 形式をまたぐ組に印を付けないこと（2026-08-26 12:xx に直した）

    ここは長らく**テーマIDだけ**で数えていました。実物（受け取り帳 `c23c90a9`・
    親からの申し送り 08/24）:

        08/26 14:00  cFZd55jRxAw  長尺    65歳で年180万円 繰下げで元が取れる最後は何歳か
        09/05 12:00  rRYgdX9GFJA  ショート 85歳まで生きるなら繰下げは何歳まで得か #Shorts

    **10日 離れ・形式ちがい・切り口ちがい。** これは `CLAUDE.md` が明記している
    「長尺1本から何本も切り出せる」の形**そのもの**です。
    ところがここは「**片方を外すこと**」と印字していました ——
    **その指示に従うと、正しい在庫を捨てます。**

    だから数えるのを `(テーマ, 形式)` にしました。**同じ形式で2本**なら、
    今までどおり「繰り返し」として印を付けます。**形式がちがう組**は
    別の行で、**捨てろとは言いません。**

    ## それでも残る本当の欠陥は、ID の衝突のほう

    投稿済みの復元は説明欄の `[t:テーマID]` でやるので、
    **長尺とショートが同じIDだと、チャンネル越しに2本を区別できません。**
    上の実物は `s-nenkin-motowotoreru-saigo-73sai1` が2本 出た形です。

    **出どころは 2026-08-26 01:5x に閉じています** —— `--long` が
    選ぶ側に効いておらず、ショート向けの題（`s-`）で長尺を作っていました
    （`tests/test_pick_long.py`）。いまは長尺は非 `s-` からしか取りません。
    **新しい衝突は出ない**ので、ここでは印字だけにします。

    **覆る条件**: 形式ちがいの組が **08/26 より後に上がった本**で出たら、
    `--long` の側がまた漏れています。そのときは検出器ではなく
    `pick()` を見ること。
    """
    is_short = _forms_of(rows)
    by_key: dict[tuple, list[str]] = defaultdict(list)
    by_topic: dict[str, set[bool]] = defaultdict(set)
    for r in rows:
        if r["topic"]:
            by_key[(r["topic"], is_short[r["id"]])].append(r["id"])
            by_topic[r["topic"]].add(is_short[r["id"]])
    dup = {k[0] for k, v in by_key.items() if len(v) > 1}
    # **形式がちがうだけの組**（捨てさせない）
    crossed = {t for t, fs in by_topic.items() if len(fs) > 1} - dup

    for r in rows:
        jst = datetime.fromisoformat(r["at"].replace("Z", "+00:00")).astimezone(JST)
        mark = " **二重**" if r["topic"] in dup else (
            " （形式ちがい）" if r["topic"] in crossed else "")
        form = " short" if is_short[r["id"]] else "long "
        print(f"{jst:%m/%d %H:%M}  {r['id']}  {form}  "
              f"{r['topic']:<22s}{mark}  {r['title'][:34]}")
    if dup:
        print(f"\n**同じテーマ・同じ形式が2本以上 予約に入っています: {'・'.join(sorted(dup))}**")
        print("  続けて見たときに「繰り返し」と映る形です。**片方を外すこと。**")
    if crossed:
        print(f"\n同じテーマですが**形式がちがいます**: {'・'.join(sorted(crossed))}")
        print("  **外さないこと。**『長尺1本から何本も切り出す』の形です（`CLAUDE.md`）。")
        print("  ただし `[t:テーマID]` は形式を持たないので、**チャンネル越しには"
              "2本を区別できません**。08/26 より後に上がった本で出たなら、"
              "`--long` の選ぶ側がまた漏れています（`pick()` を見ること）。")
    if not dup and not crossed:
        print("\n二重予約はありません。")


def _update(svc, video_id: str, publish_at: str | None,
            fallback_status: dict | None = None) -> None:
    """`status` だけを差し替える。**snippet を触らないこと** —— 部分更新なので、
    渡さなかった欄は消えます（題名や説明欄を巻き添えで空にしない）。

    `fallback_status` を渡すと、**現状を読めなかった回だけ**それで代えます
    （2026-08-17 に足した）。**既定は None ＝ これまでどおり読めなければ落ちる**：
    呼ぶ側が「この本は自分が上げた予約中の本だ」と**示せたときだけ**渡すこと
    （`unschedule.py` は手元の控えで示しています）。

    **黙って代えないのはわざとです。** ここで読んでいるのは
    「他人が変えたかもしれない欄」で、示せないまま既定値で上書きすると、
    **`videos().update` は部分更新ではない**ので他の欄が巻き添えになります。
    """
    try:
        cur = svc.videos().list(part="status", id=video_id).execute()["items"]
    except Exception as exc:                                  # noqa: BLE001
        if fallback_status is None:
            raise
        print(f"[reschedule] **現状を読めません**: {str(exc)[:90]}")
        print("[reschedule] 呼ぶ側が渡した `status` で代えます"
              "（投稿のときにこちらが立てた4欄）")
        cur = [{"status": dict(fallback_status)}]
    if not cur:
        raise SystemExit(f"動画が見つかりません: {video_id}")
    status = dict(cur[0]["status"])
    for k in ("uploadStatus", "failureReason", "rejectionReason"):
        status.pop(k, None)
    status["privacyStatus"] = "private"
    if publish_at:
        status["publishAt"] = publish_at
    else:
        status.pop("publishAt", None)
    try:
        svc.videos().update(part="status",
                            body={"id": video_id, "status": status}).execute()
    except HttpError as exc:
        if not _is_quota(exc):
            raise
        # **観測を残してから止まること**（2026-08-19 に足した）。ここは長らく
        # `SystemExit` を投げるだけで、`data/day_quota.jsonl` に1行も残していません
        # でした。残さないと `upload_cap.day_quota()` が **open=True**（＝まだ押せる）
        # と答え続け、次の回が同じ 403 をもう一度買います。
        auth.note_day_quota(exc, f"videos.update {video_id}")
        raise SystemExit(
            f"[reschedule] **{video_id} の予約は、いま外せません（日枠切れ）。**\n"
            "  `videos.update` は日枠に当たります。**`videos.insert` とは違います** ——\n"
            "  投稿（insert・1600単位）は日枠が切れていても通るのに、\n"
            "  差し替え（update・50単位）は 403 で止まります。**安いほうが先に閉じます。**\n"
            "  読みを控えで代えても、**書き込みの側は代えられません**\n"
            "  （控えは手元にありますが、YouTube 側の状態を変えるのは口だけです）。\n"
            "  → **JST 16:00 以降にやり直すこと**（日枠は太平洋時間の0時に戻ります）。\n"
            "  **まだ作り直さないこと。** §5「外す → 作る → 上げ直す」の順は、\n"
            "  ここで止まれば1本も捨てないためにあります"
        ) from exc
    else:
        # **通ったことも残すこと**（2026-08-26 に実測して足した）。
        # 403 のあとに通った呼び出しは、**その 403 が日枠でなかった証拠**です
        # （日枠は窓の中で戻らない）。`upload_cap.note_quota_ok` に理由。
        try:
            upload_cap.note_quota_ok(detail=f"videos.update {video_id}")
        except Exception:                                      # noqa: BLE001
            pass


def _parse_at(value) -> datetime | None:
    """控えの `at` を datetime に。**読めなければ None**（その行は飛ばす）。"""
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


#: 長尺を同じ日に置くときの時刻（`scripts/batch_build.LONG_HOURS_JST` と同じ並び）。
#: **長尺は `SHORTS_FEED` の枠を1つも使いません**（`src/day_cap.py`）。
#: 夜に置いても生死に掛からないので、要るのは「空いている別々の時刻」だけです。
LONG_HOURS_JST = (20, 21, 22, 19, 18)


def long_pack_plan(rows: list[dict], durations: dict[str, float], *,
                   now: datetime, per_day: int = 5, lead_min: int = 60,
                   long_min_s: float = 180.0,
                   window: tuple[str, str] | None = None) -> list[dict]:
    """**予約済みの長尺だけを前へ詰める割り当て**（API 0単位・純関数）。

    返すのは `{"id", "topic", "old", "new"}` の並びで、**動かす本だけ**です。

    ## なぜ長尺だけ別に詰めるのか

    **4,000時間の門に入るのは長尺だけ**です（`src/levers.py` / `src/day_cap.py` /
    `src/verify.py` が同じことを書いています）。ショートは再生の 99.9% を
    取っていますが（実測 08/26・直近28日: `SHORTS_FEED` 64,283 / `WATCH` 67）、
    **その門には1分も積みません。** つまり長尺の公開が後ろへ流れたぶん、
    **いま開いている唯一の門だけが止まります。**

    `compact_plan` はこれをやりません —— あちらは**全部**を詰める道具で、
    「真ん中に穴を空けない」を守ります。長尺は日ごとに在ったり無かったりが
    普通なので、あの穴の判定に掛けると必ず止まります。**別の問いです。**

    ## なぜ散っていたか（2026-08-26 に数えた）

    `scripts/batch_build.slots()` は `--date` が無いと**同じ時刻を count 回**返し、
    `uploader.next_publish_at()` は「その時刻で最初に空いている**日**」を返します。
    つまり **N本 = N日 に1本ずつ**。実測: 長尺 28本 が 08/26〜10/10 の
    **21日** に散っていた（1.3本/日）。作る側は 08/25 だけで **25本** 出しています。
    **散らしているのは置き方だけ**でした。

    （作る側は `batch_build._long_ring()` で直してあります。**こちらは
    もう予約に入っている本の後始末**で、そちらの直しは効きません。）

    ## **日が縮まない入れ替えは、1つも出しません**（2026-08-27 に測って直した）

    08-26 版は「動かす長尺の枠は空いている」として**全部を並べ替え**ていました。
    実測（08/27・本物の控えで撃った）:

        14手 ／ **前倒しの合計 0日**   08/28 21:00 → 08/28 **19:00**
                                       08/28 22:00 → 08/28 **18:00** …

    **同じ日の中で時刻をずらしているだけ**です。`batch_build._pack_long_form()` は
    これを毎周 撃つので、**1周あたり 14手 × 50単位 ＝ 700単位** が
    「前倒し 0日」に消えていました。日枠は 10,000単位・`videos.insert` は
    1本 1,600単位なので、**上げられたはずの本に換算して 1周 0.4本**です。

    **長尺の時刻に意味はありません**（`LONG_HOURS_JST` の註 ——
    長尺は `SHORTS_FEED` の枠を使わないので、夜に置いても生死に掛からない）。
    **意味があるのは日付だけ**なので、日が縮まない手は値打ちが 0 です。

    いまは (1) **本当に空いている枠にだけ置き**、(2) **後ろの本から順に
    いちばん早い空き枠へ**割り当てます。(2) が要るのは、08-26 版が
    「早い本から早い枠へ」だったため —— 早い本はもう早い日に居るので
    `slot >= old` で捨てられ、**穴の後ろに取り残された本まで順番が回りません。**

    ## 守っている不変条件

    - **新しい時刻は必ず今より前か同じ。** 後ろへ下げる本は1つも作りません
      （`compact_plan` と同じ理由 —— 途中で止まっても、もう一度走らせれば
      同じ割り当てになるため）
    - **公開日が1日も縮まない手は出しません**（すぐ上の節）
    - **埋まっている枠は使いません**（ショートの枠も含めて全部避ける）
    - 測定の窓（`src.measure_window`）の日は置き先から外します
    - `per_day` を超えて同じ日に置きません。**既定 5 は実測の上限**
      （`src/day_cap.long_form()`: `most=5` `alive=5` `collapsed=False` ＝
      5本 出した日は5本とも再生が付いた。**6本目は一度も観測されていません**）

    ## 覆る条件

    `day_cap.long_form()` の `collapsed` が True になったら（＝いちばん多く
    出した日に「出したのに付かない」本が出たら）、`per_day` をその日の本数より
    1つ下げること。**黙って上げないこと** —— 上げるのは前提を立てて測る手です。

    **長尺の面で「時刻べつの生死」が測れたら**、上の「時刻に意味はありません」が
    崩れます。そのときは日付だけでなく時刻も値打ちになるので、
    「0日 の手を出さない」を測った実測で置き直すこと。
    """
    floor = now.astimezone(JST) + timedelta(minutes=lead_min)
    parsed: list[tuple[datetime, dict]] = []
    for r in rows:
        at = _parse_at(r.get("at"))
        if at is None:
            continue
        parsed.append((at.astimezone(JST), r))
    # **埋まっている枠は、長尺の枠も含めて全部です**（2026-08-27 に直した）。
    #     ここは 08-26 版では「動かさない本が居ない時刻」＝ **動かす長尺の枠は
    #     空いている**、としていました。全部を並べ替える前提なら筋が通りますが、
    #     並べ替えは同じ日の 21:00→19:00 のような **0日 の入れ替え**を大量に生み、
    #     `videos.update` を 1手 50単位 で焼きます（実測 08/27: 14手・**前倒し 0日**）。
    #     いまは**本当に空いている枠にだけ置きます。**
    occupied = {at for at, _ in parsed}
    longs = [(at, r) for at, r in parsed
             if durations.get(r.get("id"), 0.0) >= long_min_s and at > floor]
    if not longs:
        return []
    # その日に**すでに居る長尺**の本数（公開済みも数える。置き先の上限に効きます）
    per_date: dict = {}
    for at, r in parsed:
        if durations.get(r.get("id"), 0.0) >= long_min_s:
            per_date[at.date()] = per_date.get(at.date(), 0) + 1

    # **いちばん後ろの本から、いちばん早い空き枠へ。**
    #     08-26 版は「早い本から順に、早い枠へ」でした ——
    #     早い本はもう早い日に居るので `slot >= old` で捨てられ、
    #     **穴の後ろに取り残された本まで順番が回りません**
    #     （実測 08/27: 長尺 14本 が 09/24〜10/03 の**ショートの帯**に居るのに、
    #      計画は 08/28〜09/03 の同じ日の入れ替えだけを出していました）。
    pool = sorted(longs, key=lambda t: (t[0], str(t[1].get("id", ""))), reverse=True)
    hours = sorted(list(LONG_HOURS_JST)[:max(1, per_day)])
    plan: list[dict] = []
    day = floor.date()
    last = max(at for at, _ in longs).date()
    guard = 0
    while pool and day <= last and guard < 400:
        guard += 1
        if measure_window.inside(day.strftime("%Y-%m-%d"), window):
            day += timedelta(days=1)
            continue
        for h in hours:
            if not pool or per_date.get(day, 0) >= per_day:
                break
            slot = datetime(day.year, day.month, day.day, h, 0, tzinfo=JST)
            if slot <= floor or slot in occupied:
                continue
            old, row = pool[0]
            # **日が縮まない入れ替えは出しません**（50単位 を捨てるだけなので）。
            #     `pool` は後ろ順なので、先頭で縮まないなら残りも縮みません。
            #     枠はこの先どんどん後ろになるので、ここで打ち切って構いません。
            if old.date() <= slot.date():
                pool = []
                break
            pool.pop(0)
            occupied.add(slot)
            occupied.discard(old)
            per_date[day] = per_date.get(day, 0) + 1
            per_date[old.date()] = per_date.get(old.date(), 1) - 1
            plan.append({"id": row.get("id"), "topic": row.get("topic", ""),
                         "old": old, "new": slot})
        day += timedelta(days=1)
    return plan


def compact_plan(rows: list[dict], *, now: datetime, step_min: int = 30,
                 hour: int = 9, until_hour: int = 21, max_days: int = DEFAULT_MAX_DAYS,
                 lead_min: int = 60,
                 window: tuple[str, str] | None = None) -> list[dict]:
    """**予約を前に詰める割り当てを作る**（API 0単位・純関数）。

    `rows` は控え（`src.dupes.ledger_rows`）の形。返すのは
    `{"id", "topic", "title", "old", "new"}` の並びで、**動かす本だけ**です。

    ## なぜ要るか（2026-08-18 に控えで数えた）

    予約 256本の分は **全部 `:00`**、公開は **1日 8〜13本**、最後は **09/27**。
    置ける枠は 30分きざみなら 9〜21時で **1日25個**あります。
    **足りていないのは在庫でも投稿枠でもなく、目盛りでした**
    （`scripts/batch_build.slots` の `step_min` は同じ穴を作る側で塞いであります。
    こちらは**既に予約に入っている本**の側で、そちらの直しは効きません）。

    ## 全部は詰めません（既定 `max_days=4`）

    「1時間より詰めても1本あたりの再生は落ちない」は**まだ前提**です
    （`config/hypotheses.yaml`・9/05 判定・**該当日が0日なので判定できません**）。
    落ちるなら、全部詰めた時点で在庫を1本あたり半額で売ったことになります。
    **判定に要るのは3日**なので、既定は4日ぶんだけ詰めます。
    残りは触りません。**判定してから決めること。**

    ## 守っている不変条件 —— **新しい時刻は必ず今より前か同じ**

    これは「早めるため」だけの規則ではありません。**途中で止まっても、
    もう一度走らせれば同じ割り当てになる**ための条件です。
    `at` の昇順に詰めるので、`new_i <= old_i` なら、k本目まで動かした後に
    並べ直しても順番は変わりません（`new_k <= old_k <= old_(k+1)`）。
    **`videos.update` は1日の単位枠（10,000）で 190本ぶんしか撃てない**ので、
    途中で止まる回が必ず出ます。破れたら例外にします（黙って別の割り当てにしない）。

    測定の窓（`src.measure_window`）の日は、**置き先からも、動かす対象からも外します。**

    ## 置き先は「いちばん早い予約の日」から。**それより前へは出しません**

    今日や明日へ出せば、もっと詰まります。**やりません** —— その手前にあるのは
    測定の窓（M14）か、**もう手元で確かめようがないほど目前の日**だからです。
    いちばん早い予約の日から後ろへ埋めるだけなら、**公開の順番も間隔の意図も壊れません。**
    `lead_min` より手前の枠も落とします（YouTube は直前の予約を受けません）。
    """
    if not 1 <= step_min <= 60 or 60 % step_min:
        raise SystemExit(f"--step-min は 60 の約数で 1〜60 のどれか: {step_min}")
    if not 0 <= hour <= until_hour <= 23:
        raise SystemExit(f"時刻の範囲がおかしい: {hour}〜{until_hour}")

    floor = now + timedelta(minutes=lead_min)
    live = []
    for r in rows:
        if not r.get("at"):
            continue
        try:
            at = datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if at <= floor:
            continue
        jst = at.astimezone(JST)
        if measure_window.inside(jst.strftime("%Y-%m-%d"), window):
            continue          # 測定中の日は動かさない（M14）
        live.append((at, r))
    live.sort(key=lambda t: (t[0], t[1].get("id", "")))
    if not live:
        return []

    day = live[0][0].astimezone(JST).date()
    grid: list[datetime] = []
    days_used = 0
    while days_used < max_days:
        if not measure_window.inside(day.isoformat(), window):
            for m in range(hour * 60, until_hour * 60 + 1, step_min):
                slot = datetime(day.year, day.month, day.day,
                                m // 60, m % 60, tzinfo=JST)
                if slot > floor:
                    grid.append(slot)
            days_used += 1
        day += timedelta(days=1)

    plan = []
    for slot, (old, row) in zip(grid, live):
        new = slot.astimezone(timezone.utc)
        if new > old:
            raise SystemExit(
                f"[compact] **{row.get('id')} を後ろへ動かす割り当てになりました**"
                f"（{old.astimezone(JST):%m/%d %H:%M} → {slot:%m/%d %H:%M} JST）。\n"
                "        前に詰める道具なので、これは割り当ての誤りです。\n"
                "        **--hour を早めるか --step-min を細かくすること。**\n"
                "        （後ろへ動かすと、途中で止まった回をやり直せなくなります）"
            )
        if new == old:
            continue
        plan.append({"id": row.get("id", ""), "topic": row.get("topic", ""),
                     "title": row.get("title", ""),
                     "old": old.strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "new": new.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return plan


def _is_short(row: dict) -> bool:
    """その本が Shorts かどうか。**`src.forms` が1か所で決めます。**

    **テーマIDの `s-` 頭で見ないこと**（2026-08-21 に踏んだ）。長尺は Shorts の
    テーマから起こすので `s-` を継いでいて、控えの実物では **10本が長尺なのに
    `s-` 頭**でした（逆に `#Shorts` は付いているのに `s-` でない本が18本）。
    長尺を Shorts に数えると、上の上限がその日の Shorts を不当に減らします。

    長尺は Shorts のフィードに出ないので、**下の1日の上限には数えません**
    （目盛りの取り合いには数えます —— 同じ時刻に2本置かないため）。

    ## **`#Shorts` だけで見るのをやめました**（2026-08-25。**実測で4本ずれていた**）

    ここは「**題名の `#Shorts` だけで見ます**」でした。ところが
    `scripts/status.py:150` は同じ問いに「**尺で見る。題の #Shorts は
    付け忘れがある**」と書いてあり、**同じ帳面の読み手2つが逆を向いていました。**

    突き合わせた実測（控え493本）:

        WuTf0Z-tRJc   **5分51秒の長尺**なのに `#Shorts` 付き（公開済み・**1再生**）
        pMHDwK5tB2E / YmJ7psxW3co / FSAN9tjIX10   **ショートなのに札が無い**

    前者はその日の Shorts 枠を1本ぶん食いつぶし、後者は上限から漏れます。
    **どちらも `--spread` が本を動かす向きを狂わせます。**
    しかも `CfzcVmRncPg`（5分9秒・`#Shorts` 付き）は **08/27** ——
    **day_cap の切り分けの日**に載っていました。

    測った形（Analytics → 控えの秒数）を先に見て、**何も測っていない本だけ
    札に落ちます**（`src.forms.classify` の3段）。
    """
    return forms.is_short(row)


def _say_conflicts(rows: list[dict]) -> None:
    """**この割り当ては、何本ぶん推測の上に乗っているか**を先に言う（2026-08-25）。

    控えは git で配られるので、同時に走った回の行が merge で両方残ります。
    `src.dupes.ledger_rows()` は1本にたたみますが、**`at` が食い違う組では
    どちらが本物かを行から言えません**（`retimed_at` の印がある側が勝ちますが、
    印は 2026-08-25 から押しはじめたので、それより古い組には付いていません）。

    たたむ前の 2026-08-25 の実測では、**上限に達していない 09/05・09/06・09/24 が
    12・14・11本に見えていて**、`--spread --per-day 10` はそこから実物を
    11本 動かすところでした。**数のほうは直っています。**
    残るのは「その本が今どちらの枠にいるか」で、そこは `videos.update` が
    上書きするので**動かす向きは安全**です。ただし**黙っては進まないこと。**
    """
    bad = {r["id"]: r["at_others"] for r in rows if r.get("at_others")}
    if not bad:
        return
    print(f"[reschedule] [!] **{len(bad)}本は、控えに予約時刻が2つ残っています**"
          "（同時に走った回の行が merge で両方残った跡）。")
    print("        数える側は1本にたたんでいるので、**日ごとの本数は実物どおり**です。")
    print("        どちらの枠に居るかだけが推測で、`videos.update` が上書きするので"
          "動かす向きは安全です: "
          + " ".join(sorted(bad)[:6]) + (" …" if len(bad) > 6 else ""))


def spread_plan(rows: list[dict], *, now: datetime, per_day: int = 10,
                hour: int = 9, until_hour: int = 21, step_min: int = 30,
                lead_min: int = 60, from_day: date | None = None,
                window: tuple[str, str] | None = None) -> list[dict]:
    """**1日に置く Shorts の本数に上限をかけ、あふれたぶんを後ろの空き日へ送る**
    （API 0単位・純関数）。返す形は `compact_plan` と同じ。

    ## なぜ要るか（2026-08-21 08:2x に実測した）

    08/20 に Shorts を **25本**出しました。`data/views.jsonl` を公開時刻で並べると、
    **10本目と11本目のあいだで切れています**（同じ経過11時間の時点で）:

        09:00 208  09:30 409  10:00 1394 10:30 1000 11:00 246
        11:30 185  12:00 1133 12:30 211  13:00 352  13:30 1111   ← ここまで
        14:00   0  14:30   0  15:00   1  15:30   0  16:00   3    ← ここから 0 が並ぶ
        …… 21:00 まで15本、0が9本・残りも1〜3

    **経過時間の差ではありません** —— 10本目（11.8時間で 1111）と
    11本目（11.3時間で 0）は**30分しか離れていません**。
    公開から3時間で数字が出る本があるので、「まだ着いていない」でもありません
    （55時間たっても 0 のままの本があります）。

    1日の合計で見ると、もっとはっきりします（**同じ経過11時間の時点**）:

        08/16   4本 → 合計 5,301（1本 1,325）
        08/20  25本 → 合計 5,948（1本   541）

    **6倍出しても、その日に届く数は 12% しか増えていません。**
    1日あたりに配られる量のほうに天井があり、本数はそれを分け合うだけです。
    だから11本目から先は、**在庫を捨てているのと同じ**です
    （空いている日に置けば1本 600前後は取れる）。

    ## 動かすのは後ろへだけ。**上限を超えた日の、遅いほうから**

    `compact_plan` の不変条件（新しい時刻は必ず今より前）と**向きが逆**です。
    こちらは `new >= old` を守ります。理由は同じで、**途中で止まっても
    もう一度走らせれば続きになる**ためです（遅いほうから撃つので、
    動かした本が、まだ動かしていない本を追い越しません）。

    置き先は「その日より後で、まだ上限に届いていない日」の**空いている目盛り**。
    詰まっている所を避けて、**いちばん間の空いた目盛りから**埋めます。

    ## **置き先は「生きる目盛り」の中だけ**（2026-08-24 に直した。それまで0再生へ送っていた）

    この docstring は上で **「14:00 以降は15本中9本が 0、残りも1〜3」**と自分で
    測っています。それなのに置き先の選び方は `9〜21時` の全部から
    **「いちばん間の空いた目盛り」**を採っており、空いているのは当然**遅いほう**でした。
    実測（08/24 16:2x・`--spread --since 2026-08-28` の割り当て22本）:

        09/05 14:30 → **09/20 21:00**      09/05 15:00 → **09/20 18:30**
        09/06 12:30 → **09/22 16:30**      09/06 13:00 → **09/22 19:30**

    **「その日の11本目だから0再生」を「19:30 だから0再生」に付け替えただけ**で、
    22本ぶんの移動（1,100単位）が1再生も生みません。

    直し方は、`per_day` と同じ数字から窓を起こすことです。**その日の先頭から
    `per_day` 本ぶんの目盛り**（既定 09:00〜13:30）だけを置き先にします。

    **なぜこの窓の作り方が、08/28 の判定より先に決められるか。**
    `config/hypotheses.yaml` は「1日10本まで」か「13:30 JST で閉じる窓」かを
    まだ切り分けていません。**どちらでも、生きるのは同じ10枠です** ——
    本数の説明なら先頭10本、窓の説明なら 09:00〜13:30 の10枠。
    だから判定を待たずに直せます。**判定が「窓」に出たら、変えるのは
    `hour` を前へ倒すことだけ**で、ここの式はそのまま使えます。

    ## `from_day` より前の日は、**上限もかけないし、置き先にもしません**

    測定中の日を壊さないためです。`config/hypotheses.yaml` の
    「予約の間隔を1時間より詰めても、1本あたりの再生は落ちない」は
    **1日16本以上の日が3日ぶん**そろわないと判定しません（08/20・21・22 で
    ちょうど3日・判定は 08/23）。ここで 08/22 を10本に削ると、
    **登録した条件のほうを、都合よく後から緩めた**ことになります。
    払うのは 08/22 の15本ぶんで、**返るのは n=1 ではなく n=3 の答え**です。
    """
    if per_day < 1:
        raise SystemExit(f"--per-day は1以上: {per_day}")
    if not 1 <= step_min <= 60 or 60 % step_min:
        raise SystemExit(f"--step-min は 60 の約数で 1〜60 のどれか: {step_min}")
    if not 0 <= hour <= until_hour <= 23:
        raise SystemExit(f"時刻の範囲がおかしい: {hour}〜{until_hour}")

    floor = now + timedelta(minutes=lead_min)
    live: list[tuple[datetime, dict]] = []
    for r in rows:
        if not r.get("at"):
            continue
        try:
            at = datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if at <= floor:
            continue
        jst = at.astimezone(JST)
        if measure_window.inside(jst.strftime("%Y-%m-%d"), window):
            continue          # 測定中の日は動かさない（M14）
        if from_day is not None and jst.date() < from_day:
            continue          # 判定に要る日は、削らないし埋めない
        live.append((at, r))
    live.sort(key=lambda t: (t[0], t[1].get("id", "")))
    if not live:
        return []

    # その日に埋まっている時刻（**長尺も数えます** —— 同じ時刻に2本置かないため）
    taken: dict[date, set[datetime]] = defaultdict(set)
    # その日の Shorts の本数（**上限はこちらで数えます**）
    shorts: dict[date, list[tuple[datetime, dict]]] = defaultdict(list)
    for at, r in live:
        jst = at.astimezone(JST)
        taken[jst.date()].add(jst.replace(second=0, microsecond=0))
        if _is_short(r):
            shorts[jst.date()].append((at, r))

    # あふれた本（上限を超えた日の、**遅いほう**から）
    over: list[tuple[datetime, dict]] = []
    for day in sorted(shorts):
        rest = shorts[day][per_day:]
        for at, r in rest:
            taken[day].discard(at.astimezone(JST).replace(second=0, microsecond=0))
        over.extend(rest)
    if not over:
        return []
    counts = {d: min(len(v), per_day) for d, v in shorts.items()}

    last_day = max(shorts)
    # **その日の先頭から per_day 本ぶんの目盛り**が「生きる」範囲です（下の節）。
    # per_day=10・hour=9・step=30 なら 09:00〜13:30。**定数ではありません** ——
    # `day_cap` の実測が上がれば、窓もいっしょに広がります。
    live_edge_min = hour * 60 + (per_day - 1) * step_min
    plan: list[dict] = []
    for at, row in sorted(over, key=lambda t: (t[0], t[1].get("id", ""))):
        old_day = at.astimezone(JST).date()
        day = old_day + timedelta(days=1)
        placed = None
        while placed is None and day <= last_day + timedelta(days=400):
            if (not measure_window.inside(day.isoformat(), window)
                    and counts.get(day, 0) < per_day):
                free = []
                for m in range(hour * 60, until_hour * 60 + 1, step_min):
                    slot = datetime(day.year, day.month, day.day,
                                    m // 60, m % 60, tzinfo=JST)
                    if slot <= floor or slot.astimezone(timezone.utc) < at:
                        continue
                    if slot in taken[day]:
                        continue
                    free.append(slot)
                # **生きる目盛りの中だけ**から選ぶ（下の `live_edge_min`）
                free = [s for s in free
                        if s.hour * 60 + s.minute <= live_edge_min]
                if free:
                    # **いちばん間の空いた目盛り**を選ぶ（同点なら早いほう）
                    def gap(s: datetime) -> float:
                        others = taken[day]
                        if not others:
                            return 1e9
                        return min(abs((s - o).total_seconds()) for o in others)
                    placed = max(free, key=lambda s: (gap(s), -s.timestamp()))
            if placed is None:
                day += timedelta(days=1)
        if placed is None:
            raise SystemExit(
                f"[spread] **{row.get('id')} の置き先が見つかりません**"
                f"（{old_day} より後・1日 {per_day}本まで）。--per-day を上げること"
            )
        taken[day].add(placed)
        counts[day] = counts.get(day, 0) + 1
        new = placed.astimezone(timezone.utc)
        if new < at:
            raise SystemExit(
                f"[spread] **{row.get('id')} を前へ動かす割り当てになりました**"
                f"（{at.astimezone(JST):%m/%d %H:%M} → {placed:%m/%d %H:%M} JST）。"
                "\n        後ろへ送る道具なので、これは割り当ての誤りです。"
            )
        plan.append({"id": row.get("id", ""), "topic": row.get("topic", ""),
                     "title": row.get("title", ""),
                     "old": at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                     "new": new.strftime("%Y-%m-%dT%H:%M:%SZ")})
    return plan


def _spread(args) -> int:
    """`--spread`。**既定は割り当てを出すだけ**で、`--apply` で初めて撃ちます。

    **遅いほうから撃ちます**（`spread_plan` の不変条件。途中で止まっても続きになる）。
    """
    rows = [r for r in dupes.ledger_rows() if r.get("at")]
    if not rows:
        raise SystemExit("控え（data/uploaded.jsonl）に予約の行がありません")
    _say_conflicts(rows)
    now = datetime.now(timezone.utc)
    from_day = (datetime.strptime(args.since, "%Y-%m-%d").date()
                if args.since else None)
    plan = spread_plan(rows, now=now, per_day=args.per_day, hour=args.hour,
                       until_hour=args.until_hour, step_min=args.step_min,
                       lead_min=args.lead_min, from_day=from_day)
    if not plan:
        print(f"[spread] 1日 {args.per_day}本を超えている日はありません。")
        return 0

    before: dict[str, int] = defaultdict(int)
    after: dict[str, int] = defaultdict(int)
    moved = {p["id"] for p in plan}
    for r in rows:
        if not r.get("at") or not _is_short(r):
            continue
        try:
            at = datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00"))
        except ValueError:
            continue
        if at <= now or (from_day and at.astimezone(JST).date() < from_day):
            continue
        before[at.astimezone(JST).strftime("%m/%d")] += 1
        if r.get("id") not in moved:
            after[at.astimezone(JST).strftime("%m/%d")] += 1
    for p in plan:
        after[datetime.fromisoformat(p["new"].replace("Z", "+00:00"))
              .astimezone(JST).strftime("%m/%d")] += 1

    print(f"[spread] 予約の Shorts のうち、**動かすのは {len(plan)}本**"
          f"（1日 {args.per_day}本まで・{args.hour}〜{args.until_hour}時）")
    for p in plan[:12]:
        o = datetime.fromisoformat(p["old"].replace("Z", "+00:00")).astimezone(JST)
        n = datetime.fromisoformat(p["new"].replace("Z", "+00:00")).astimezone(JST)
        print(f"  {o:%m/%d %H:%M} → {n:%m/%d %H:%M}  {p['id']}  {p['topic'][:26]}")
    if len(plan) > 12:
        print(f"  …… ほか {len(plan) - 12}本")
    print("[spread] Shorts の本数/日（前 → 後）: "
          + " ".join(f"{d}={before.get(d, 0)}→{after.get(d, 0)}"
                     for d in sorted(set(before) | set(after))))
    if not args.apply:
        print("[spread] **これは割り当てだけです。**撃つには --apply を付けること"
              f"（`videos.update` は1本 50単位・日枠 10,000 ＝ {args.max}本で止めます）")
        return 0

    svc = uploader._service()
    done = 0
    # **遅いほうから**（追い越しを作らない）
    for p in sorted(plan, key=lambda p: p["old"], reverse=True)[:args.max]:
        _update(svc, p["id"], p["new"], fallback_status=uploader.base_status())
        dupes.retime(p["id"], p["new"])
        done += 1
        n = datetime.fromisoformat(p["new"].replace("Z", "+00:00")).astimezone(JST)
        print(f"[spread] {p['id']} → {n:%m/%d %H:%M} JST（{done}/{min(len(plan), args.max)}）",
              flush=True)
    left = len(plan) - done
    print(f"[spread] **{done}本を動かしました。**残り {left}本"
          + ("（もう一度 --spread --apply を走らせること）" if left else ""))
    return 0


def _horizon(rows: list[dict], plan: list[dict], now: datetime) -> tuple[str, float]:
    """詰めた後の「予約の最後」を JST の日付と、いまからの日数で返す。"""
    moved = {p["id"]: p["new"] for p in plan}
    last = None
    for r in rows:
        at = moved.get(r.get("id", "")) or r.get("at")
        if not at:
            continue
        try:
            when = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except ValueError:
            continue
        if when > now and (last is None or when > last):
            last = when
    if last is None:
        return "（予約なし）", 0.0
    return last.astimezone(JST).strftime("%m/%d %H:%M"), (last - now).total_seconds() / 86400


def hole_days(rows: list[dict], plan: list[dict], now: datetime) -> list[str]:
    """**詰めたあと、公開が1本も無い日**（JST の `MM/DD`）を返す。

    **「無くなる日」ではありません**（下の「もともと空いていた日も、穴です」）。

    ## なぜ要るか（2026-08-19 12:5x に、撃つ直前の空撃ちで見つけた）

    `--min-days` は **「予約の最後」しか見ていません。** `--max-days 10` で
    控えの実物（317本）を詰めると、こうなります:

        08/20〜08/29  各25本（狙いどおり）
        **08/30〜09/11  0本**  ← **13日間、1本も公開されない**
        09/12〜09/27  そのまま（詰め切れなかったぶん）

    最後は 09/27 のままなので `--min-days 8` は **38.9日ある** と読んで通します。
    **穴は真ん中に空くので、端しか見ない門には映りません。**

    `docs/CLAUDE.md` は「**投稿が途切れるのが最大の損失**」と書いています。
    ここを通してしまうと、いちばん避けたい形をこちらから作ることになります。

    ## 最後より後ろの「0本の日」は穴ではありません

    全部を前に詰め切ると、後ろは当然からになります（それは**地平線が縮んだ**
    だけで、`--min-days` がすでに見ている側です）。**数えるのは、新しい
    「予約の最後」より手前で0本になる日だけ**にします。

    ## **もともと空いていた日も、穴です**（2026-08-19 17:0x に直した）

    ここは長らく `before - after` を返していました ——
    **「本があったのに、動かしたせいで無くなった日」**しか数えない形です。
    だから **もともと1本も無かった日は、`before` に居ないので永久に映りません。**

    実測でこうなりました。控え345本の実物は **08/28〜09/03 が0本**（7日連続）で、
    既定の `--max-days 4` は「動かすのは 0本」＝ `plan` が空なので
    `before == after`。**穴0件で静かに通ります。**
    `suggest_max_days` も同じ返りを見ているので、**「4 で穴は空きません」と答えます。**

    **守っていたのは「これ以上ひどくしないこと」だけで、
    「いま途切れているか」は一度も見ていませんでした。**
    これは `scripts/status.py` の `_print_per_day` が同じ日に踏んだのと**同じ形**です ——
    **「本のある日」の集合からは、「本の無い日」は原理的に出てきません。**
    どちらも直し方は1つで、**集合ではなく暦を歩くこと。**

    ## 今日は数えません

    今日の枠は半分が過ぎています（`old <= now` の本は既に公開済み）。
    今日を入れると「今日が0本＝穴」と**毎回鳴ります**。数えるのは**明日から**。
    """
    moved = {p["id"]: p["new"] for p in plan}
    after: set[date] = set()
    last: datetime | None = None
    for r in rows:
        at = r.get("at")
        if not at:
            continue
        try:
            old = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
        except ValueError:
            continue
        if old <= now:
            continue                       # もう公開済み／直前のものは対象外
        try:
            new = datetime.fromisoformat(
                str(moved.get(r.get("id", ""), at)).replace("Z", "+00:00"))
        except ValueError:
            continue
        after.add(new.astimezone(JST).date())
        if last is None or new > last:
            last = new
    if last is None:
        return []
    # **集合の差ではなく、暦を歩くこと**（docstring の理由）。
    # `before` はもう作りません —— あれを引き算に使うと、
    # **もともと空いていた日が構造的に落ちます。**
    edge = last.astimezone(JST).date()
    day = now.astimezone(JST).date() + timedelta(days=1)   # 今日は数えない
    holes: list[str] = []
    while day < edge:
        if day not in after:
            holes.append(day.strftime("%m/%d"))
        day += timedelta(days=1)
    return holes


def suggest_max_days(rows: list[dict], now: datetime, args, *,
                     ceiling: int = 40, start: int | None = None,
                     window: tuple[str, str] | None = None) -> int | None:
    """**穴が空かない `--max-days`** を探して返す（見つからなければ None）。

    純関数を回すだけなので API は 0単位です。**人に「減らすか増やすか」を
    考えさせないため**に、道具の側で答えまで出します（穴は `--max-days` を
    **増やして**詰め切ると消えるので、直感と逆向きです）。

    探しはじめる値は `start`（既定は `args.max_days`）。**下げる方向には探しません** ——
    `DEFAULT_MAX_DAYS` は「判定に要る3日＋1日」で決めた**床**で、
    穴を避けるために上げることはあっても、下げる理由は別の話だからです。

    `window` は `compact_plan` へそのまま渡します（既定 `None` ＝ 実物の
    `measure_window.WINDOWS` を見る）。**検査が渡せるようにするために足しました**
    （2026-08-24）。ここが渡せないと、検査は**日付を直に書いたまま実物の窓に
    ぶつかります** —— 実際 `2026-08-27` を窓に入れた回で、この関数を使う検査が
    3件落ちました（`v2` の置き先が窓の中だったので `None` しか返せなくなった）。
    **検査の日付を動かして直すと、次に窓が増えた回にまた落ちます。**
    """
    first = args.max_days if start is None else start
    for md in range(first, ceiling + 1):
        try:
            plan = compact_plan(rows, now=now, step_min=args.step_min, hour=args.hour,
                                until_hour=args.until_hour, max_days=md,
                                lead_min=args.lead_min, window=window)
        except SystemExit:
            continue
        if hole_days(rows, plan, now):
            continue
        _, days = _horizon(rows, plan, now)
        if days >= args.min_days:
            return md
    return None


def _compact(args) -> int:
    """`--compact`。**既定は割り当てを出すだけ**で、`--apply` で初めて撃ちます。

    ## `--max-days` を書かなかったときは、道具が決めます（2026-08-19 18:0x）

    ここは長らく**既定 4 で撃って、穴が残ったら止まり、`--max-days N` を
    名指しして終わり**でした。**答えを出せるのに、撃つのは次の手**という形です。
    実測では、この2手ぶんの往復が**24周ぶん持ち越されています** ——
    その間ずっと 08/28〜09/03 の7日が空いたままでした。

    **床は動かしません。** 探しはじめは `DEFAULT_MAX_DAYS`（判定に要る3日＋1日）で、
    そこから**穴が消えるまで上げるだけ**です。`--max-days N` と明示した回は
    **その N で撃ちます**（自動で上げません。逃げ道を残すため）。
    """
    rows = [r for r in dupes.ledger_rows() if r.get("at")]
    if not rows:
        raise SystemExit("控え（data/uploaded.jsonl）に予約の行がありません")
    _say_conflicts(rows)
    now = datetime.now(timezone.utc)
    if args.max_days is None:
        args.max_days = DEFAULT_MAX_DAYS
        found = suggest_max_days(rows, now, args, start=DEFAULT_MAX_DAYS)
        if found is not None and found != DEFAULT_MAX_DAYS:
            print(f"[compact] **--max-days を {DEFAULT_MAX_DAYS} → {found} に上げました**"
                  f"（穴の空かない最小の日数。API 0単位で数え直した結果）")
        if found is not None:
            args.max_days = found
        # 見つからなかったときは床のまま進みます。
        # **下の穴の節が、そのまま「どれだけ増やしても埋まりません」と言います。**
    plan = compact_plan(rows, now=now, step_min=args.step_min, hour=args.hour,
                        until_hour=args.until_hour, max_days=args.max_days,
                        lead_min=args.lead_min)
    where, days = _horizon(rows, plan, now)
    per_day: dict[str, int] = defaultdict(int)
    for p in plan:
        jst = datetime.fromisoformat(p["new"].replace("Z", "+00:00")).astimezone(JST)
        per_day[jst.strftime("%m/%d")] += 1

    print(f"[compact] 控えの予約 {len(rows)}本のうち、**動かすのは {len(plan)}本**"
          f"（{args.step_min}分きざみ・{args.hour}〜{args.until_hour}時・{args.max_days}日ぶん）")
    for p in plan:
        o = datetime.fromisoformat(p["old"].replace("Z", "+00:00")).astimezone(JST)
        n = datetime.fromisoformat(p["new"].replace("Z", "+00:00")).astimezone(JST)
        print(f"  {o:%m/%d %H:%M} → {n:%m/%d %H:%M}  {p['id']}  {p['topic'][:26]}")
    if per_day:
        print("[compact] 詰めたあとの本数/日: "
              + " ".join(f"{d}={n}" for d, n in sorted(per_day.items())))
    print(f"[compact] 予約の最後: {where}（あと {days:.1f}日）")
    if days < args.min_days:
        raise SystemExit(
            f"[compact] **予約の先が {days:.1f}日しか残りません**"
            f"（下限 {args.min_days}日）。\n"
            "        **投稿が途切れるのが最大の損失**なので、ここは止めます。\n"
            "        --max-days を減らすか、--min-days を下げること（理由を JOURNAL に）。"
        )

    holes = hole_days(rows, plan, now)
    if holes:
        print(f"[compact] [!] **詰めたあと、公開が0本の日が {len(holes)}日**"
              f"（**もともと空いていた日も含みます**）: "
              + " ".join(holes))
    if holes and not args.allow_gap:
        hint = suggest_max_days(rows, now, args)
        fix = (f"        → **`--max-days {hint}` なら穴は空きません**"
               "（詰め切るので、後ろが減るぶんは `--min-days` が見ます）。\n"
               if hint else
               "        → `--max-days` をどれだけ増やしても埋まりません。"
               "**在庫を足してから詰めること。**\n")
        raise SystemExit(
            f"[compact] **真ん中に {len(holes)}日ぶんの穴が残ります**"
            f"（{holes[0]}〜{holes[-1]}）。\n"
            "        **投稿が途切れるのが最大の損失**なので、ここは止めます。\n"
            "        `--min-days` は「予約の最後」しか見ないので、**この穴は映りません**\n"
            "        （最後は動かないまま、真ん中だけが空になる形です）。\n"
            + fix +
            "        承知のうえで撃つなら `--allow-gap`（**理由を JOURNAL に書くこと**）。"
        )

    if not plan:
        print("[compact] 動かすものはありません。")
        return 0
    if not args.apply:
        print("[compact] **これは割り当てだけです。**撃つには --apply を付けること"
              f"（`videos.update` は1本 50単位・日枠 10,000 ＝ {args.max}本で止めます）")
        return 0

    # **1日で撃ち切れないときは、途中の姿にも穴が空きます**（2026-08-19 12:5x）。
    # `videos.update` は50単位・日枠 10,000 ＝ **1日195本まで**なので、
    # 318本の割り当ては必ず2日に割れます。前に詰めた本が抜けた跡は
    # **翌日の窓で埋まるまで空いたまま**なので、いつまでに続きを撃つかが要ります。
    if len(plan) > args.max:
        mid = hole_days(rows, plan[:args.max], now)
        print(f"[compact] **1回では撃ち切れません**（{len(plan)}本 / 1回 {args.max}本）。"
              f"残り {len(plan) - args.max}本は次の窓（JST 16:00）で。")
        if mid:
            print(f"[compact] [!] **途中の姿には {len(mid)}日ぶんの穴が残ります**: "
                  + " ".join(mid))
            print(f"[compact] [!] **{mid[0]} が来る前に、続きを撃ち切ること。**"
                  "  撃ち切れなければ、その日は公開が0本になります")

    svc = uploader._service()
    done = 0
    for p in plan[:args.max]:
        _update(svc, p["id"], p["new"], fallback_status=uploader.base_status())
        dupes.retime(p["id"], p["new"])
        done += 1
        n = datetime.fromisoformat(p["new"].replace("Z", "+00:00")).astimezone(JST)
        print(f"[compact] {p['id']} → {n:%m/%d %H:%M} JST（{done}/{min(len(plan), args.max)}）",
              flush=True)
    left = len(plan) - done
    print(f"[compact] **{done}本を動かしました。**残り {left}本"
          + ("（もう一度 --compact --apply を走らせること。割り当ては同じに出ます）"
             if left else ""))
    return 0


def build_parser() -> argparse.ArgumentParser:
    """引数の受け口だけを組む（**既定値を検査から読むため**に分けてあります）。"""
    ap = argparse.ArgumentParser(description="予約中の動画の公開時刻を動かす／外す")
    ap.add_argument("--list", action="store_true", help="予約の一覧を出す（二重予約に印）")
    ap.add_argument("--move", nargs=2, metavar=("VIDEO_ID", "JST"),
                    help="公開時刻を動かす。例: --move abc123 2026-09-04T09:00")
    ap.add_argument("--unschedule", metavar="VIDEO_ID",
                    help="予約を外す（private のまま残るので、時刻を入れ直せば戻ります）")
    ap.add_argument("--force-window", action="store_true",
                    help="測定の窓の中へ動かす／**窓の中から動かす**"
                         "（**理由を JOURNAL に書くこと**）")
    ap.add_argument("--compact", action="store_true",
                    help="予約を前に詰める割り当てを出す（**API 0単位**。撃つには --apply）")
    ap.add_argument("--spread", action="store_true",
                    help="**1日の Shorts に上限をかけ、あふれたぶんを後ろの空き日へ送る**"
                         "（**API 0単位**。撃つには --apply）")
    ap.add_argument("--per-day", type=int, default=_measured_per_day(DEFAULT_PER_DAY),
                    help=f"--spread の1日あたりの Shorts の上限（既定{_measured_per_day(DEFAULT_PER_DAY)}＝実測。"
                         "08/20 の実測で11本目から先が 0 だった）")
    ap.add_argument("--since", metavar="YYYY-MM-DD",
                    help="--spread で、この日より前は上限をかけず置き先にもしない"
                         "（**測定中の日を壊さないため**）")
    ap.add_argument("--apply", action="store_true",
                    help="--compact の割り当てを実際に撃つ（`videos.update`・1本50単位）")
    ap.add_argument("--step-min", type=int, default=30, help="--compact の目盛り（分・既定30）")
    ap.add_argument("--hour", type=int, default=9, help="--compact の1日の始まり（既定9時）")
    ap.add_argument("--until-hour", type=int, default=21, help="--compact の1日の終わり（既定21時）")
    ap.add_argument("--max-days", type=int, default=None,
                    help=f"--compact で詰める日数（**既定は自動**: {DEFAULT_MAX_DAYS}日から始めて、"
                         "公開0本の日が消えるまで上げる。明示した N は上げません）")
    ap.add_argument("--min-days", type=float, default=8.0,
                    help="詰めた後に残す予約の先（日・既定8）。下回ったら止めます")
    ap.add_argument("--lead-min", type=int, default=60, help="いまから何分後より先に置くか（既定60）")
    ap.add_argument("--allow-gap", action="store_true",
                    help="詰めたあと**真ん中に公開0本の日ができる**のを承知で撃つ"
                         "（**理由を JOURNAL に書くこと**）")
    ap.add_argument("--max", type=int, default=100,
                    help="1回で撃つ本数の上限（既定100 ＝ 約5,100単位。"
                         "日枠 10,000 はサムネイル 49件 2,450単位と分け合います）")
    return ap


def _current_day(video_id: str) -> str | None:
    """その本が**いま**予約されている日（JST の `YYYY-MM-DD`）。控えから引く。

    **控えは足すだけの帳面**なので、`src.ab_split.published()` に畳ませます
    （同じ `video_id` の行が動かすたびに増える／日は JST で採る、の2つを
    あそこが持っています。**ここで畳み直さないこと** —— 畳み方が2か所に
    なった時点で、片方だけが直る形になります）。
    """
    try:
        from src.ab_split import published
    except Exception:
        return None
    for row in published():
        if str(row.get("video_id") or "") == video_id:
            day = row.get("publish")
            return day.isoformat() if day is not None else None
    return None


def _check_source_window(video_id: str, *, force: bool = False, tool: str = "") -> None:
    """**動かす「元」の日も窓で見る。**（2026-08-26。実害が1回出ている）

    ## なぜ要るか

    `measure_window.check()` は `--move` の**行き先**にしか当たっていませんでした。
    ところが 2026-08-24 に実際に壊れたのは**元の側**です ——
    `--spread` が 08/27 を「14本 ＝ 上限超え」と読んで4本を後ろへ送り、
    さらに別の回が送って、**窓に残ったのは1本だけ**でした
    （`src/measure_window.py` の 08-27 の `why` に、その顛末が書いてあります）。

    `--spread` と `--compact` は、そのあと**動かす対象からも窓の日を外しました**
    （このファイルの `_spread` / `_compact`）。**`--move` と `--unschedule` だけが
    取り残されていました。** 手で1本ずつ動かす道は残っているので、
    「窓の日から1本ずつ抜く」は、いまも黙って通ります。

    **同じ約束を守る所が3つあって、2つにしか付いていない形**です。
    このリポジトリで通算7件目（`src/measure_window.py` 冒頭の「入口ではなく
    合流点で直す」）。ここは合流点が無い（`--move` は時刻を外から受ける）ので、
    **入口に付けるしかありません。検査で固定します**
    （`tests/test_reschedule_window.py`）。

    ## 分かっていないこと

    - **控えに無い本は止めません**（`None` を返す）。止めると、控えを持たない
      古い本を動かす道が消えます。**投稿を止めないほうを採ります**（`CLAUDE.md`）
    """
    day = _current_day(video_id)
    if day is None:
        return
    measure_window.check(day, force=force,
                         tool=f"{tool}（**元の日** {day} が測定日です）")


def _lift_dash_ids(argv: list[str] | None) -> tuple[list[str] | None, dict]:
    """**`-` で始まる動画ID を、argparse の手前で抜き出す**（2026-08-26 に踏んだ）。

    YouTube の動画IDは 64種の字（`A-Za-z0-9_-`）から作られるので、
    **`-rNsh53STNw` `-LBSPCCE8Aw` のように `-` で始まるものが 1/64 ある**
    ——実測で、予約中の 487本 のうち **8本**がこの形です。

    argparse は先頭の `-` を旗と読むので、そのまま渡すと落ちます:

        queue_lag.py: error: argument --move: expected 2 arguments

    **これは「打ち方が悪い」ではありません。** `--plan` が出す行をそのまま
    貼っても、`apply_moves()` が `reschedule.main(["--move", vid, when])` と
    呼んでも、**同じ所で落ちます** —— 2026-08-26 16:0x の `queue_lag --apply` は
    51手のうち **6手 目**で止まりました（`-rNsh53STNw`）。
    `live_slots --apply --all` の 35手にも `-LBSPCCE8Aw` が入っています。

    **`--move` は `nargs=2` なので `=` で書く逃げ道がありません。**
    だから受け口の手前で外し、`parse_args` の後に戻します。
    """
    if argv is None:
        argv = sys.argv[1:]         # **CLI から貼った行も同じ所で落ちます**
    out: list[str] = []
    lifted: dict = {}
    i = 0
    while i < len(argv):
        tok = argv[i]
        if tok == "--move" and len(argv) - i >= 3:
            lifted["move"] = [argv[i + 1], argv[i + 2]]
            i += 3
            continue
        if tok == "--unschedule" and len(argv) - i >= 2:
            lifted["unschedule"] = argv[i + 1]
            i += 2
            continue
        out.append(tok)
        i += 1
    return out, lifted


def main(argv: list[str] | None = None) -> int:
    argv, lifted = _lift_dash_ids(argv)
    args = build_parser().parse_args(argv)
    for key, val in lifted.items():
        setattr(args, key, val)

    if args.spread:
        return _spread(args)
    if args.compact:
        return _compact(args)

    if args.move:
        # **API を呼ぶ前に見ること。** 窓の門は認証も枠も要らないので、
        # 通らない移動で単位（50単位）を捨てないため。
        measure_window.check(args.move[1][:10], force=args.force_window,
                             tool="reschedule.py --move")
        _check_source_window(args.move[0], force=args.force_window,
                             tool="reschedule.py --move")
    if args.unschedule:
        _check_source_window(args.unschedule, force=args.force_window,
                             tool="reschedule.py --unschedule")

    svc = uploader._service()

    if args.move:
        vid, when = args.move
        at = datetime.fromisoformat(when).replace(tzinfo=JST).astimezone(timezone.utc)
        if at <= datetime.now(timezone.utc):
            raise SystemExit(f"過去の時刻です: {when} JST")
        iso = at.strftime("%Y-%m-%dT%H:%M:%SZ")
        _update(svc, vid, iso)
        # **控えにも書き戻すこと**（2026-08-18 に実測で見つけた）。
        # `--compact` は控えだけを見るので、ここを飛ばすと
        # **実物は動いたのに、次の回は古い時刻のまま割り当てを組みます。**
        dupes.retime(vid, iso)
        print(f"[reschedule] {vid} を {when} JST へ移しました")
        return 0

    if args.unschedule:
        _update(svc, args.unschedule, None)
        dupes.retime(args.unschedule, None)
        print(f"[reschedule] {args.unschedule} の予約を外しました（private のまま残っています）")
        return 0

    _show(_scheduled(svc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
