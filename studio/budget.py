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

from . import meter
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
    # コメント欄の成果報酬の塊（`studio/asp.comment_block`・`cli cta`・`commentThreads.insert`）。
    "cta_comment": 50,
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


#: **撃って通った証拠**になる event（その行が在る ＝ その刻に Data API が通った）。
#: `analytics_*` は入れません —— あちらは**別の枠**（`cmd_analytics`「**Data API 0単位**」）で、
#: Data API が尽きていても通るので、「通った証拠」にすると尽きているのを見落とします。
LIVE_EVENTS = {
    "channel", "scheduled", "measured", "zero_probe", "views_over", "rethumb", "retitled",
    "meta_updated", "meta_update", "meta_repaired", "replied", "watermark_set", "unscheduled",
    "ready_checked", "cold_read", "viewer_comment",
}


#: **読みの 1行 に多めに当てる単位**（上端を作るための数・実費は 1単位）。
#: `all_videos` は 280本 を 50件/ページ で 6回 引くので、1つ の event の裏に最大 6本 の
#: `videos.list` が居ます。**10 は その倍**（上端は上に外すこと）。
READ_UNITS_CEILING = 10


def spent_ceiling(rows: list[dict], now: dt.datetime | None = None) -> dict:
    """**この窓で「うち」が使った分の上端**（**API 0単位**・2026-09-17 11:0x・optimizer・Opus）。

    `spent` は書きの口しか値段を持たないので **過小**です（覆る条件 (1)）。
    それは「あと何本 出せるか」には安全側ですが、**「尽きたのはうちか」には逆向き**です ——
    過小な数では「うちじゃない」と言い切れません。だからここでは**逆に振った数**を作ります:
    台帳に出た読みの event を 1行 `READ_UNITS_CEILING` 単位 で数え、書きの値段に足す。

    **これが `DAY_UNITS` の半分にも届かないのに 403 なら、枠を食ったのは この機械ではありません。**

    **踏んだ当のもの**（09/16 16:00 の窓・この関数を足させた実測）:

        16:49:51  `channel` ＋ 読み 8行  **通った**（＝ この刻に枠は生きていた）
        （**うちの台帳はここから 2時間11分 1行も在りません**）
        19:01:08  `status` **403 quotaExceeded**
        21:14:44  `channel` ＋ 読み 5行  **また通った**（403 より後に通っている）

    ＝ うちの上端は **150単位 未満**。**10,000 は うちが食べていません。**
    21:14 が 19:01 の 403 より後に通っているのは、**尽きた枠が時々 1本 だけ通す形**
    （2026-09-17 10:3x に手で数えた: 45本 中 1本 だけ通った）＝ 別の口が枠の縁で回っている側。

    **覆る条件**:
     (1) 台帳に出ない口で撃つ道具が足されたら、この上端は上端でなくなります
         （`LIVE_EVENTS` に足していない event ＝ ここでも数えられない）。
     (2) `READ_UNITS_CEILING` を超える引きをする読みが足されたら（`search.list` は **100単位**）、
         その event は `UNITS_BY_EVENT` に値段を書くこと。
     (3) `DAY_UNITS` が 10,000 でないと分かったら（＝ オーナーが画面を見た結果）、
         半分の門はその数で引き直すこと。
    """
    lo = window_start(now).isoformat(timespec="seconds")
    base = spent(rows, now)
    reads = 0
    for r in rows:
        at = r.get("at") or ""
        if not at or at < lo:
            continue
        ev = r.get("event") or "?"
        if isinstance(r.get("units"), int) or UNITS_BY_EVENT.get(ev):
            continue
        if ev in LIVE_EVENTS:
            reads += 1
    return {"since": lo, "writes": base["total"], "reads": reads,
            "total": base["total"] + reads * READ_UNITS_CEILING}


def ours(rows: list[dict], now: dt.datetime | None = None) -> bool:
    """**尽きた枠を食べたのが「うち」か**（上端が半分に届いていれば True ＝ うちの側）。"""
    return spent_ceiling(rows, now)["total"] >= DAY_UNITS // 2


def dry_observed(rows: list[dict], now: dt.datetime | None = None) -> str | None:
    """**実測で尽きているか** ——尽きているなら、その 403 の刻を返す（**API 0単位**）。

    **2026-09-16 21:2x に足した**（optimizer・Fable 5.1・ultracode）。**踏んだ当のもの**:
    この回の `budget.lines` は「使った **0** / 10,000・残り **10,000** ＝ **あと 5本 出せる**」と
    印字し、その **数十秒後**に `watermark`（50単位）も `channels.list`（**1単位**）も
    **403 quotaExceeded** で落ちました（`reason: quotaExceeded`・撃って確かめた）。
    ＝ **この module の覆る条件 (1)（台帳は過小）が、いちばん高い所で出ました** ——
    「あと 5本 出せる」は、**1単位 も撃てない周**に出ていた字です。

    **推計（`spent`）と実測（403）が食い違ったら、実測が勝ちます。**
    見るのは `spent` の残りではなく「**いまの枠の中で、最後に通った刻より後に 403 が在るか**」
    ——通った刻より後の 403 だけを見るので、枠が戻れば（次に 1本 通った瞬間に）**ひとりでに消えます**。

    **覆る条件**:
     (1) 403 の後に `LIVE_EVENTS` の行が出ているのに、この関数が「尽きている」と言い続けたら、
         その event が `LIVE_EVENTS` に無い ＝ 足すこと（**通った証拠の取りこぼし**）。
     (2) 逆に、**通っていないのに** `LIVE_EVENTS` の行を書く口が出たら（台帳に先に書いて
         それから撃つ口）、その event を外すこと。
     (3) `quotaExceeded` 以外の理由の 403 を `cli.quota_exceeded` が拾うようになったら
         （あちらの覆る条件 (1)）、この関数は「日枠」ではない物まで日枠と読みます ＝ そのとき分けること。
    """
    lo = window_start(now).isoformat(timespec="seconds")
    qx = ok = ""
    for r in rows:
        at = r.get("at") or ""
        if not at or at < lo:
            continue
        ev = r.get("event")
        if ev == "quota_exceeded":
            qx = max(qx, at)
        elif ev in LIVE_EVENTS:
            ok = max(ok, at)
    return qx if qx and qx > ok else None


#: **1度 置けば ずっと効く安い手**（event の名 → 値段と字）。**まだ 1行も無い物だけを印字します。**
#:
#: **2026-09-17 06:4x に足した**（optimizer・Fable 5.1・ultracode）。**踏んだ当のもの**:
#: 09/16 15:3x の回が `watermark`（登録ボタンの重ね・**公開ずみの 280本 にも後から載る、ただ 1つ の腕**）を
#: 道具として足し、**21:17 に撃って 403**（日枠）。**そこで消えました** —— `status` のどこにも
#: 「まだ置いていない」と出る所が無く、**次に枠が戻った周は、置いたかどうかを知る手がありません**。
#: これは この repo で通算 13回 の形（**やると決めた手を、数える口が無いまま次の周へ渡す**）です。
#: 値段は **50単位 ＝ 1本 上げる 1,650 の 1/33**。**「いま縛っているのが登録率か」は、ここでは決めません**
#: （同じ周 06:4x に撃ち直したら、縛っていたのは登録率ではなく**配り**でした ——
#:  長尺は **5本 で再生 20回**・`sub_rate_line`。`JOURNAL` 2026-09-17 06:4x の差し替え）。
#: **この行が言うのは 1つ だけ: 50単位 の、1度きりの、まだ撃っていない手が在る。**
#:
#: **覆る条件**: (1) 撃って `watermark_set` が 1行 入ったら、この行はひとりでに消えます（数える口がそれ）。
#: (2) 同じ形の「1度きりの安い手」が増えたら ここへ足すこと —— **3つ を越えたら**、
#: 並べる場所を `status` から `docs/METHOD.md` の一覧へ移すこと（毎周 読む行を増やさない）。
#: (3) 透かしを置いて **登録率が 2週 動かなかったら**、腕はここではありません ＝ この行を消して
#: `sub_rate_line` の側（本ごとの登録率）へ戻すこと。
#: (4) **撃つ順は この行が決めません** —— 枠が戻った窓で先に来るのは、出ていない長尺 2本 の
#: 打ち直し（`pubcheck.missing` の行・1単位 ＋ 50単位 ×2）です。**どちらも 3桁 安いので、順は
#: その周が決めれば足ります**（両方 撃っても 152単位 ＝ 本 1本 の 1/11）。
ONE_SHOT = {
    "watermark_set": (50, "**透かし（登録ボタンの重ね）がまだ 1度も置かれていません**"
                          "（`python -m studio.cli watermark`・**50単位** ＝ 本 1本 の 1/33）＝ "
                          "**公開ずみの本にも後から載る、ただ 1つ の腕**。"
                          "**登録率の数は `trend.sub_rate_line`**（ここへ写さない）"),
}


def one_shot_lines(rows: list[dict]) -> list[str]:
    """**まだ 1度も撃っていない、1度きりの安い手**（`ONE_SHOT` の註・**API 0単位**）。"""
    done = {r.get("event") for r in rows}
    return [f"    未着手: {txt}" for ev, (_u, txt) in ONE_SHOT.items() if ev not in done]


def lines(rows: list[dict], now: dt.datetime | None = None) -> list[str]:
    """印字（**判定はしない** ＝ 数を並べるだけ・この module の註）。"""
    s = spent(rows, now)
    nxt = window_start(now) + dt.timedelta(days=1)
    dry = dry_observed(rows, now)
    # **実測**（`studio/meter.py`・撃った所で 1本ずつ数えた綴じ）。推計（`spent`）と並べます ——
    # 推計は「うちが撃った物」しか数えられないので、**撃っていないのに尽きている**形が出ません。
    since = window_start(now).isoformat(timespec="seconds")
    try:
        real = meter.line(since, DAY_UNITS)
        outside = meter.outside_line(since, DAY_UNITS, dry,
                                     ceiling=spent_ceiling(rows, now)["total"])
    except Exception:  # noqa: BLE001  数えが転んでも周を止めない（`cli.main` の前置きと同じ決め）
        real = outside = None
    if dry:
        # **実測が推計に勝つ側**（`dry_observed` の註）。**「あと N本 出せる」を出さないこと** ——
        # 出せない周に出せると書くのが、この回が踏んだ当のものです。
        out = [f"**日枠**（`budget`・**0単位**・{s['since'][5:16]} JST から・戻るのは {nxt:%m/%d %H:%M} JST）: "
               f"**実測で尽きています**（{dry[5:16]} JST に 403 quotaExceeded・"
               f"それより後に通った口が 1つ もありません）。**出せる本は 0本**"]
        out.append(f"    台帳の推計は 使った {s['total']:,} / {DAY_UNITS:,}（残り {s['left']:,}）ですが、"
                   "**推計は過小で、実測が勝ちます**（覆る条件 (1)）。"
                   "撃つ前に 1単位 の口で試すこと ——**1,650単位 の `schedule` から試さないこと**")
        if real:
            out.append(real)
        if outside:
            out.append(outside)
        out += one_shot_lines(rows)
        return out
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
    if real:
        out.append(real)
    out.append("    ※ 上の推計は 台帳に `units` を書かない口を数えません ＝ **過小**（覆る条件 (1)）。"
               "**実測の行が在れば、そちらが本当の消費です**（`studio/meter.py`）")
    out += one_shot_lines(rows)
    return out
