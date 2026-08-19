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
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from googleapiclient.errors import HttpError  # noqa: E402

from src import auth, dupes, history, measure_window, uploader  # noqa: E402

JST = timezone(timedelta(hours=9))
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


def _show(rows: list[dict]) -> None:
    by_topic: dict[str, list[str]] = defaultdict(list)
    for r in rows:
        if r["topic"]:
            by_topic[r["topic"]].append(r["id"])
    dup = {t for t, v in by_topic.items() if len(v) > 1}

    for r in rows:
        jst = datetime.fromisoformat(r["at"].replace("Z", "+00:00")).astimezone(JST)
        mark = " **二重**" if r["topic"] in dup else ""
        print(f"{jst:%m/%d %H:%M}  {r['id']}  {r['topic']:<22s}{mark}  {r['title'][:34]}")
    if dup:
        print(f"\n**同じテーマが2本以上予約に入っています: {'・'.join(sorted(dup))}**")
        print("  続けて見たときに「繰り返し」と映る形です。**片方を外すこと。**")
    else:
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


def compact_plan(rows: list[dict], *, now: datetime, step_min: int = 30,
                 hour: int = 9, until_hour: int = 21, max_days: int = 4,
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
    """**詰めたあと、公開が1本も無くなる日**（JST の `MM/DD`）を返す。

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
    """
    moved = {p["id"]: p["new"] for p in plan}
    before: set[str] = set()
    after: set[str] = set()
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
        before.add(old.astimezone(JST).strftime("%m/%d"))
        try:
            new = datetime.fromisoformat(
                str(moved.get(r.get("id", ""), at)).replace("Z", "+00:00"))
        except ValueError:
            continue
        after.add(new.astimezone(JST).strftime("%m/%d"))
        if last is None or new > last:
            last = new
    if last is None:
        return []
    edge = last.astimezone(JST).strftime("%m/%d")
    return sorted(d for d in before - after if d < edge)


def suggest_max_days(rows: list[dict], now: datetime, args, *, ceiling: int = 40) -> int | None:
    """**穴が空かない `--max-days`** を探して返す（見つからなければ None）。

    純関数を回すだけなので API は 0単位です。**人に「減らすか増やすか」を
    考えさせないため**に、道具の側で答えまで出します（穴は `--max-days` を
    **増やして**詰め切ると消えるので、直感と逆向きです）。
    """
    for md in range(args.max_days, ceiling + 1):
        try:
            plan = compact_plan(rows, now=now, step_min=args.step_min, hour=args.hour,
                                until_hour=args.until_hour, max_days=md,
                                lead_min=args.lead_min)
        except SystemExit:
            continue
        if hole_days(rows, plan, now):
            continue
        _, days = _horizon(rows, plan, now)
        if days >= args.min_days:
            return md
    return None


def _compact(args) -> int:
    """`--compact`。**既定は割り当てを出すだけ**で、`--apply` で初めて撃ちます。"""
    rows = [r for r in dupes.ledger_rows() if r.get("at")]
    if not rows:
        raise SystemExit("控え（data/uploaded.jsonl）に予約の行がありません")
    now = datetime.now(timezone.utc)
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
        print(f"[compact] [!] **詰めたあと、公開が0本になる日が {len(holes)}日**: "
              + " ".join(holes))
    if holes and not args.allow_gap:
        hint = suggest_max_days(rows, now, args)
        fix = (f"        → **`--max-days {hint}` なら穴は空きません**"
               "（詰め切るので、後ろが減るぶんは `--min-days` が見ます）。\n"
               if hint else
               "        → `--max-days` をどれだけ増やしても埋まりません。"
               "**在庫を足してから詰めること。**\n")
        raise SystemExit(
            f"[compact] **真ん中に {len(holes)}日ぶんの穴が空きます**"
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="予約中の動画の公開時刻を動かす／外す")
    ap.add_argument("--list", action="store_true", help="予約の一覧を出す（二重予約に印）")
    ap.add_argument("--move", nargs=2, metavar=("VIDEO_ID", "JST"),
                    help="公開時刻を動かす。例: --move abc123 2026-09-04T09:00")
    ap.add_argument("--unschedule", metavar="VIDEO_ID",
                    help="予約を外す（private のまま残るので、時刻を入れ直せば戻ります）")
    ap.add_argument("--force-window", action="store_true",
                    help="M14 の比較の窓の中へ動かす（**理由を JOURNAL に書くこと**）")
    ap.add_argument("--compact", action="store_true",
                    help="予約を前に詰める割り当てを出す（**API 0単位**。撃つには --apply）")
    ap.add_argument("--apply", action="store_true",
                    help="--compact の割り当てを実際に撃つ（`videos.update`・1本50単位）")
    ap.add_argument("--step-min", type=int, default=30, help="--compact の目盛り（分・既定30）")
    ap.add_argument("--hour", type=int, default=9, help="--compact の1日の始まり（既定9時）")
    ap.add_argument("--until-hour", type=int, default=21, help="--compact の1日の終わり（既定21時）")
    ap.add_argument("--max-days", type=int, default=4,
                    help="--compact で詰める日数（既定4。**全部は詰めません**）")
    ap.add_argument("--min-days", type=float, default=8.0,
                    help="詰めた後に残す予約の先（日・既定8）。下回ったら止めます")
    ap.add_argument("--lead-min", type=int, default=60, help="いまから何分後より先に置くか（既定60）")
    ap.add_argument("--allow-gap", action="store_true",
                    help="詰めたあと**真ん中に公開0本の日ができる**のを承知で撃つ"
                         "（**理由を JOURNAL に書くこと**）")
    ap.add_argument("--max", type=int, default=100,
                    help="1回で撃つ本数の上限（既定100 ＝ 約5,100単位。"
                         "日枠 10,000 はサムネイル 49件 2,450単位と分け合います）")
    args = ap.parse_args(argv)

    if args.compact:
        return _compact(args)

    if args.move:
        # **API を呼ぶ前に見ること。** 窓の門は認証も枠も要らないので、
        # 通らない移動で単位（50単位）を捨てないため。
        measure_window.check(args.move[1][:10], force=args.force_window,
                             tool="reschedule.py --move")

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
