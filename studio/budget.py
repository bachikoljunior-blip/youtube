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
     （いまの 400 は 写し 128 ＋ `refresh_stats` 約15 ＋ `channel()` 約100 ＝ 約245 ＋ 余り）。
 (4) **`RESERVE` を上げる前に、その周が「公開ページで読めない物」を読んでいたか見ること**
     （2026-09-19 12:xx）—— 再生・登録・出たか は `measure --public`／`pubcheck` が **0単位** で読みます。
     403 で止まったのがその 3つ なら、直すのは `RESERVE` ではなく**呼ぶ口**です。
 (5) **6本/日 を 2日 撃って、6本目 が 2日 とも 403 なら**（`quota_exceeded` の台帳・0単位）、
     Google の数えはこちらの写しより多い ＝ `RESERVE` を 600 に戻し `day_upload_cap` を 5 へ戻すこと。
     **1日 だけの 403 で戻さないこと** —— その日は `catchup` の 302単位 が先に出ていた側を先に疑う
     （撃つ順は「出す側が先」。`cmd_catchup` の cta の門・同刻）。
 (6) **6本目 の 24h 中央が、同じ日の 1〜5本目 の中央の 半分 未満なら**、枠が薄まった側
     ＝ 6本目 の枠（`SHORT_SLOTS` の 21:00）を疑い、刻を動かすか 5本 に戻すこと。
     **1日 で決めないこと**（09/18 の 5本 は 802〜1,165 で、1本 の幅が 1.45倍 ある）。
"""
from __future__ import annotations

import datetime as dt

from . import meter
from .common import JST, now_jst

#: 日枠（`studio/yt.py` 冒頭と同じ数。**写しなので、変えるときは両方**）。
DAY_UNITS = 10_000
#: 枠が戻る刻（JST）。
RESET_H = 16
#: 測る側（`status`／`measure`／`analytics`／`comments`）のために空けておく単位（覆る条件 (3)・(4)）。
#:
#: **【2026-09-19 12:xx・optimizer・Opus 5・1周 1体】600 → 400 に下げました。**
#: **なぜ**: この数が守っていたのは「測れない日を作らないこと」でした（この file の冒頭・
#: 「`measure` が撃てない周は `trend` の判定に数が 1つ も入りません」）。
#: **その前提は 2026-09-19 11:xx に消えています** —— `pubcheck.shorts_views()` ＋
#: `cli measure --public` が、再生も登録も**公開ページから 0単位 で**読みます
#: （同日 10:56 の実測 11本 が台帳に在る）。**＝ 日枠が 0 でも盲にはなりません。**
#: 残りの 400 が払うのは Data API でしか読めない側だけです:
#: 写し（`yt.all_videos` 32単位 × 寿命 6時間 ＝ 4回/日 ＝ 128）＋ `refresh_stats` 1単位/周（約15）
#: ＋ `channel()` 約100/日 ＝ **約245**。
#: **この 200単位 の差が 6本目 の立つ/立たない を分けます**（下の `UPLOAD_UNITS_SHORT` の註）。
RESERVE = 400
#: 1本 出すのにかかる単位（`videos.insert` 1,600 ＋ `thumbnails.set` 50）。**長尺の値段です。**
UPLOAD_UNITS = 1650
#: **ショート 1本 の値段**（`videos.insert` 1,600 **のみ** ＝ `thumbnails.set` を撃たない）。
#:
#: **【2026-09-19 12:xx・optimizer・Opus 5・1周 1体】足しました。**
#: **なぜ 50 を落とせるか**: `cli.thumbnail_for` の註が 2026-09-15 から
#: 「**`short` は 1コマ目の画面のまま**（縦のフィードでサムネは見られない・答えを変えない）」と
#: 書いており、撃っていたのは **YouTube が既定で選ぶのとほぼ同じ絵**でした。
#: 効く面は フィードの外（チャンネル一覧・検索）だけで、実測の配りは
#: **SHORTS 4,919 / YT_SEARCH 160 / YT_CHANNEL 6**（`analytics_traffic` 2026-09-19 10:37）＝ **3.4%**。
#: **5本/日 で 250単位** を、その 3.4% に払っていました。
#:
#: **これで 1日 6本 が立ちます**（`cli.day_upload_cap`）:
#:
#:     6本 × 1,600 ＝ 9,600  ＋ 測る側 400 ＝ **10,000**（ちょうど）
#:     （前: 5本 × 1,650 ＝ 8,250 ＋ 600 ＝ 8,850・余り 1,150 ＜ 1,600 ＝ 6本目 が立たない）
#:
#: **外した方の負けは小さい**: 6本目 が 403 で撥ねられても **0単位**（`quotaExceeded` は課金されない・
#: 台帳の 403 69本 が 0単位 の実測）＝ **撃ってみることの下振れは「5本 のまま」だけ**です。
#: **覆る条件**: (5)（下）。
UPLOAD_UNITS_SHORT = 1600

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
    # チャンネルの説明欄（`studio/asp.channel_description`・`cli channel-desc`・`channels.list` 1 ＋ `channels.update` 50）。
    "channel_desc_set": 51,
    "channel_desc_refused": 51,
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
    left = DAY_UNITS - total
    return {"since": lo, "total": total, "per": per, "left": left,
            # **長尺の値段で数えた側**（安全側・`schedule --replace` の門はこちらを見る）
            "uploads_left": max((left - RESERVE) // UPLOAD_UNITS, 0),
            # **ショートの値段で数えた側**（`day_upload_cap` と同じ物差し・2026-09-19 12:xx）
            "uploads_left_short": max((left - RESERVE) // UPLOAD_UNITS_SHORT, 0)}


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
           f"＝ あと **{s['uploads_left_short']}本** 出せる（ショート 1本 {UPLOAD_UNITS_SHORT:,}単位・"
           f"測る側に {RESERVE} 残す。**長尺を混ぜると 1本 {UPLOAD_UNITS:,} ＝ あと "
           f"{s['uploads_left']}本**）"]
    if s["per"]:
        out.append("    " + " ／ ".join(f"{k} {v:,}" for k, v in
                                        sorted(s["per"].items(), key=lambda x: -x[1])[:5]))
    if s["left"] < RESERVE:
        out.append("    !! **残りが測る側の取り分を割っています** ＝ この周は Data API の読みが落ちる側（403）。"
                   "**ただし盲にはなりません**（2026-09-19 12:xx）—— 再生・登録・出たかは "
                   "`measure --public`／`pubcheck` が **0単位** で読みます。"
                   "Data API でしか読めないのは 写し（`yt.all_videos`）と `refresh_stats` だけ。"
                   "判定はこの周が決めること")
    if real:
        out.append(real)
    out.append("    ※ 上の推計は 台帳に `units` を書かない口を数えません ＝ **過小**（覆る条件 (1)）。"
               "**実測の行が在れば、そちらが本当の消費です**（`studio/meter.py`）")
    out += one_shot_lines(rows)
    return out
