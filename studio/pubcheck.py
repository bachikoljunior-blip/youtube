"""**予約した本が、その刻に本当に public になったか**を、YouTube Data API を 1単位も使わずに確かめる。

2026-09-16 23:3x（optimizer・Fable 5.1・ultracode）に足した。**踏んだ形**:

    09/15 21:00 の枠  `FLLHpj27v7s`   刻から 26.5時間  **public にならないまま**
    09/16 12:00 の枠  `4MpH3QliNi4`   刻から 11.5時間  **public にならないまま**

**2日で 7本 上げて、2本（29%）が黙って出ていませんでした。** どちらも
`reschedule`（`videos.update` part=status）で刻を前へ動かした本で、**動かしていない本は 5本 とも
刻どおりに出ています**（`BzWoZR1Y4ZI` は 09/16 21:00 に出た ＝ 同じ日の同じ形で出ている）。

**なぜ、機械の側は 1周も気づかなかったか** —— 見ている口が、この失敗を見ない所に在ります:

    `yt.readiness()`   uploadStatus / processingStatus だけ。**`publishAt` を読んでいません**
                       ＝ 刻を失った本も `ok: true` を返し続ける（実測 `ready_checked` 8周 とも ok）
    `trend.pending()`  台帳の `pending` 行から「予約」を数えるだけ ＝ 出たかどうかは見ない
                       （**その docstring の覆る条件「予約のまま出なかった本が出たら別の印を使う」が、
                         これです**）
    `budget`/`status`  きょうの枠は `all_videos()` の privacy を読むが、**日枠が尽きた周は引けません**
                       ＝ 壊れているのが見える窓と、見えない窓が、同じ理由（日枠）で閉じます

**だから、この口は YouTube Data API を使いません。** oEmbed（`https://www.youtube.com/oembed`）は
公開の口で、日枠にも OAuth にも関係がありません ＝ **日枠が尽きている周こそ効きます**（今がそれ）。

**載せている判定は 1つ だけ ——「刻が過ぎたのに public でない」。**
oEmbed が返す番号の読み分け（200 public / 401 / 403）は**判定に使いません**（下の `HINT` の註）。
実測 2026-09-16 23:3x（各 3回・答えは 3回とも同じ）:

    200  `vum9GV8Sp6c` `uc0SceBfoxQ` `PyVf22V74Ks` `Ws32ZrBAuFQ` `BzWoZR1Y4ZI`  ＝ 出ている
    403  `xyMsBJxaj4M` `ukEFxTt1PEY` `9WdbGJaI2hU`                             ＝ まだ刻の前（予約は生きている）
    401  `FLLHpj27v7s` `4MpH3QliNi4`                                          ＝ **刻が過ぎても出ていない**

**覆る条件**:
 (1) oEmbed が 200 を返さない public の本が 1本 でも出たら（地域・年齢の制限など）、
     この口は「出ていない」を誤って鳴らします ＝ そのときは **鳴った本を `videos.list`（1単位）で
     確かめてから**、ここに例外の形を足すこと。**鳴らなくする方へ先に倒さないこと**
     （見落としの値段 ＝ 本 1本 ＋ 枠 1つ ＝ 1,650単位 と 1日。誤報の値段 ＝ 1単位）。
 (2) 401 と 403 の読み分けが変わったら（YouTube の側の都合）、`HINT` だけが古くなります。
     **判定（刻 × public か）は番号に依っていないので、そのままで動きます。**
 (3) 1周に 20本 を越えて予約を持つ形になったら、毎周 全部 撃つのはやめて
     「刻が過ぎた本だけ」に絞ること（いまは `overdue()` が既にそう絞っています）。
"""
from __future__ import annotations

import datetime as dt
import json
import urllib.error
import urllib.parse
import urllib.request

from .common import JST, now_jst

OEMBED = "https://www.youtube.com/oembed?format=json&url="
WATCH = "https://www.youtube.com/watch?v="

#: **判定には使いません**（覆る条件 (2)）。鳴った行に添える見立てだけ。
HINT = {200: "public", 401: "刻が消えている見立て", 403: "まだ刻の前の見立て"}

#: 刻を過ぎてから、これだけ経っても public でなければ鳴らす。
#: YouTube の予約は刻ちょうどに出ないことがあるので、実測（`cli` の「上げてから処理まで 中央 18分」）より
#: 長く取ってある。**短くするのは、誤報が 0 のまま 1週間 続いた回**。
GRACE_MIN = 25


def probe(video_id: str, timeout: float = 20.0) -> int:
    """oEmbed の番号を返す（**YouTube Data API 0単位**）。届かなければ 0。

    0 は「分からない」で、**鳴らしません**（網が落ちている周に毎回 鳴るのは誤報の側）。
    """
    url = OEMBED + urllib.parse.quote(WATCH + video_id, safe="")
    try:
        with urllib.request.urlopen(url, timeout=timeout) as r:
            json.loads(r.read())          # 形が読めることまで確かめる
            return int(r.status)
    except urllib.error.HTTPError as e:
        return int(e.code)
    except Exception:
        return 0


def live_schedule(rows: list[dict]) -> dict[str, tuple[str, dt.datetime, str]]:
    """いま生きている予約 ＝ video_id → (台本 id, 公開の刻, 題)。

    台帳の `scheduled` を古い順に読み、**`replaced` に名が出た video は落とす**（上げ直された前の版）。
    同じ video_id が 2行 以上 あれば最後が勝つ（`reschedule` ＝ 刻だけ動かした行）。
    `unscheduled`（private へ戻した）も落とす。
    """
    out: dict[str, tuple[str, dt.datetime, str]] = {}
    for r in rows:
        ev = r.get("event")
        if ev == "scheduled":
            vid, at = r.get("video_id"), r.get("publish_at")
            if not vid or not at:
                continue
            if r.get("replaced"):
                out.pop(r["replaced"], None)
            out[vid] = (r.get("id", ""), dt.datetime.fromisoformat(at).astimezone(JST), r.get("title", ""))
        elif ev == "retitled":
            # 題を直した本は、`scheduled` の行の題が古いまま（`retitled` の `id` は **video_id**）。
            # 鳴った行に古い題を出すと、次の回が「別の本か」を数え直します。
            # 実測 2026-09-16 23:5x: `uc0SceBfoxQ`・`BzWoZR1Y4ZI` は 09/15 21:14 に peer の形へ直っており、
            # **生きている題（oEmbed で読んだ）は新しいほうと一致**（＝ 題の書き込みは通っている）。
            vid = r.get("id")
            if vid in out and r.get("new_title"):
                sid, at, _ = out[vid]
                out[vid] = (sid, at, r["new_title"])
        elif ev == "unscheduled":
            for vid in (r.get("video_id"), r.get("id")):
                if vid:
                    out.pop(vid, None)
    return out


def overdue(rows: list[dict], now: dt.datetime | None = None,
            grace_min: int = GRACE_MIN) -> list[tuple[str, str, dt.datetime, str]]:
    """**刻が過ぎた予約**（まだ撃っていない）。(video_id, 台本 id, 刻, 題) の並び・古い順。"""
    now = now or now_jst()
    cut = now - dt.timedelta(minutes=grace_min)
    return sorted(((v, sid, at, t) for v, (sid, at, t) in live_schedule(rows).items() if at <= cut),
                  key=lambda x: x[2])


def missing(rows: list[dict], now: dt.datetime | None = None, grace_min: int = GRACE_MIN,
            probe_fn=probe) -> list[dict]:
    """**刻が過ぎたのに public でない本**（＝ 黙って出ていない本）。API 0単位。

    番号が 0（届かない）の本は**入れません**（覆る条件 (1) の誤報の側）。
    """
    now = now or now_jst()
    out = []
    for vid, sid, at, title in overdue(rows, now, grace_min):
        code = probe_fn(vid)
        if code in (200, 0):
            continue
        out.append({"video_id": vid, "script": sid, "publish_at": at, "title": title, "code": code,
                    "late_h": (now - at).total_seconds() / 3600,
                    "hint": HINT.get(code, "見立てなし")})
    return out


def taken_slots(rows: list[dict], now: dt.datetime | None = None) -> list[dt.datetime]:
    """**台帳だけから**「もう本が座っている刻」（**API 0単位**）。

    `cli.long_slot_line` は同じ物を `yt.all_videos()` から作りますが、**日枠が尽きた周は引けません**
    ＝ 鳴っている周に限って「どこへ動かせばよいか」が出なくなる。ここは台帳で足りるので台帳から作ります。

    **出ていない本が座っていた刻も、そのまま座らせます** —— 打ち直す先は `cli.next_long_slots` が
    `LONG_SLOT_LEAD_H` より先だけから選ぶので、**過ぎた刻は初めから候補に入りません**
    ＝ 外しても 1つ も増えず、代わりに「出た本の刻」まで外す穴が開きます
    （2026-09-16 23:5x に撃って確かめた: `BzWoZR1Y4ZI` は刻どおり出ているのに、
      「刻を過ぎた」だけで外れて空き枠に数えられた）。
    """
    now = now or now_jst()
    return [at for _, (_, at, _) in live_schedule(rows).items() if at > now - dt.timedelta(days=1)]


def line(rows: list[dict], now: dt.datetime | None = None, grace_min: int = GRACE_MIN,
         probe_fn=probe, slots: list[dt.datetime] | None = None) -> str:
    """毎周の 1〜N行（**API 0単位**）。鳴っていなければ 1行 で終わる。

    `slots` ＝ 打ち直す先の候補（`cli.next_long_slots`）。渡されれば行に名指しします ——
    **鳴っている周に「どこへ」まで書いてないと、次の回がもう一度 数え直すことになるため。**
    """
    now = now or now_jst()
    late = overdue(rows, now, grace_min)
    if not late:
        return "**出たか（oEmbed・API 0単位）**: 刻を過ぎた予約は 0本 ＝ 見るものがありません"
    bad = missing(rows, now, grace_min, probe_fn)
    if not bad:
        return f"**出たか（oEmbed・API 0単位）**: 刻を過ぎた予約 {len(late)}本 は **全部 public** ＝ 出ています"
    head = (f"!! **出ていない本が {len(bad)}本 あります**（刻は過ぎているのに public でない・"
            f"oEmbed・**API 0単位**・`pubcheck.missing`）。"
            f"**本 1本 と 枠 1つ が、黙って消えています**（上げ直しの値段 1,650単位）")
    body = [f"   {b['publish_at']:%m/%d %H:%M} の枠  {b['video_id']:12s} "
            f"**{b['late_h']:.1f}時間 過ぎている**（{b['code']} ＝ {b['hint']}）  {b['script']} {b['title'][:26]}"
            for b in bad]
    where = ("  空いている枠: " + " / ".join(f"{s:%m/%d %H:%M}" for s in slots[:len(bad) + 1])) if slots else ""
    tail = ["   潰す: 日枠が戻ったら `videos.list part=status`（**1単位**）で `publishAt` を見て、"
            "消えていれば `reschedule --at <空き枠>`（**50単位**）で打ち直すこと。"
            "**`schedule --replace`（1,650単位）は要りません** —— 本も題も絵も、上がっている物のままです。"
            + where]
    return "\n".join([head, *body, *tail])
