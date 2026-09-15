"""きょうの**日枠**（YouTube Data API・10,000単位/日・16:00 JST に戻る）を、台帳から数える。**API 0単位**。

**なぜ要るか（2026-09-16 03:4x に踏んだ当のもの）**:
この周の最初の `python -m studio.cli status` が **403 quotaExceeded** で落ちました。
台帳を数えたら、09/15 16:00 JST（枠の頭）からの消費は:

    scheduled（＝ `videos.insert` 1,600 ＋ `thumbnails.set` 50）  **5本 で 8,250**
    rethumb（`thumbnails.set` 50）                                8件 で   400
    retitled（`videos.update` 50）                                4件 で   200
    meta_repaired ほか                                                    101
    peers（`channels.list` ほか）                                           28
    ------------------------------------------------------------------------
                                                                  **約 8,979 / 10,000**

**残り 1,000単位 ほどを `status`／`measure`／`analytics` が食い切って、口が閉じました。**
閉じたのは印字だけではありません —— **`measure` が撃てない周は、`trend` の判定に数が 1つ も入りません。**
GOAL (4-i) の枝（A／B／C）は **48h の再生の中位**で選ぶので、
**測れない日が続くと、期限の判定そのものが止まります。**
＝ **出す本を 1本 増やすことと、その本が効いたかを知ることは、同じ枠を取り合っています。**

**この道具は判定しません。止めもしません**（投稿が途切れるのが最大の損失 ＝ `CLAUDE.md` 4）。
**数を印字するだけ**で、何本 出すかはその周が決めます（09/06 14:0x「サブが判断する」）。

**覆る条件**:
 (1) 台帳に `units` を書かない口が足されたら、この数は**過小**になります
     （`UNITS_BY_EVENT` に無い event は 0 で数える）＝ 403 が出たのに この行が「余っている」と言ったら、
     まずその口を `UNITS_BY_EVENT` に足すこと。**この行を信じて枠を使い切らないこと。**
 (2) Google が日枠を増やした（申請が通った）ら `DAY_UNITS` を置き換えること。
 (3) `measure`／`status`／`analytics` の実測が `RESERVE` に収まらない周が 2度 出たら、`RESERVE` を上げること
     （いまの 600 は `status` 約 35単位 ＋ `measure` 約 20単位 ＋ `comments` 3単位 ＋ 余り）。
"""
from __future__ import annotations

import datetime as dt

from .common import JST, now_jst

#: 日枠（`studio/yt.py` 冒頭と同じ数。**写しなので、変えるときは両方**）。
DAY_UNITS = 10_000
#: 枠が戻る刻（JST）。
RESET_H = 16
#: 測る側（`status`／`measure`／`analytics`／`comments`）のために空けておく単位（覆る条件 (3)）。
RESERVE = 600
#: 1本 出すのにかかる単位（`videos.insert` 1,600 ＋ `thumbnails.set` 50）。
UPLOAD_UNITS = 1650

#: 台帳の event → その 1行 が使った単位。**`units` を持つ行はそちらを優先する**。
UNITS_BY_EVENT = {
    "scheduled": UPLOAD_UNITS,
    "rethumb": 50,
    "retitled": 50,
    "meta_updated": 50,
    "meta_update": 50,
    "meta_repaired": 50,
    "replied": 50,
}


def window_start(now: dt.datetime | None = None) -> dt.datetime:
    """いまの日枠が始まった刻（直近の 16:00 JST）。"""
    now = (now or now_jst()).astimezone(JST)
    head = now.replace(hour=RESET_H, minute=0, second=0, microsecond=0)
    return head if now >= head else head - dt.timedelta(days=1)


def spent(rows: list[dict], now: dt.datetime | None = None) -> dict:
    """枠の頭からの消費（**台帳に出た口だけ** ＝ 覆る条件 (1) のとおり過小）。"""
    lo = window_start(now).isoformat(timespec="seconds")
    total = 0
    per: dict[str, int] = {}
    for r in rows:
        at = r.get("at") or ""
        if not at or at < lo:
            continue
        ev = r.get("event") or "?"
        u = r.get("units")
        if not isinstance(u, int):
            u = UNITS_BY_EVENT.get(ev, 0)
        if u:
            total += u
            per[ev] = per.get(ev, 0) + u
    return {"since": lo, "total": total, "per": per,
            "left": DAY_UNITS - total, "uploads_left": max((DAY_UNITS - total - RESERVE) // UPLOAD_UNITS, 0)}


def lines(rows: list[dict], now: dt.datetime | None = None) -> list[str]:
    """印字（**判定はしない** ＝ 数を並べるだけ・この module の註）。"""
    s = spent(rows, now)
    nxt = window_start(now) + dt.timedelta(days=1)
    out = [f"**日枠**（`budget`・**0単位**・{s['since'][5:16]} JST から・戻るのは {nxt:%m/%d %H:%M} JST）: "
           f"使った **{s['total']:,}** / {DAY_UNITS:,} ・ 残り **{s['left']:,}** "
           f"＝ あと **{s['uploads_left']}本** 出せる（1本 {UPLOAD_UNITS}単位・測る側に {RESERVE} 残す）"]
    if s["per"]:
        out.append("    " + " ／ ".join(f"{k} {v:,}" for k, v in
                                        sorted(s["per"].items(), key=lambda x: -x[1])[:5]))
    if s["left"] < RESERVE:
        out.append("    !! **残りが測る側の取り分を割っています** ＝ この周は `measure`／`status`／`analytics` が"
                   "落ちる側（403）。**測れない周は `trend` に数が 1つ も入らず、GOAL (4-i) の枝の判定が止まります**"
                   "（`studio/budget.py` の註）。判定はこの周が決めること")
    out.append("    ※ 台帳に `units` を書かない口の分は入っていません ＝ **この数は過小**（覆る条件 (1)）")
    return out
