#!/usr/bin/env python3
"""**予約中の動画の、公開時刻だけを動かす／予約を外す。**

    python scripts/reschedule.py --list                     # 予約の一覧（同じテーマの二重予約に印）
    python scripts/reschedule.py --move <videoId> 2026-09-04T09:00
    python scripts/reschedule.py --unschedule <videoId>     # 予約を外す（private のまま残る）

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

from src import history, uploader  # noqa: E402

JST = timezone(timedelta(hours=9))
MARKER = re.compile(r"\[t:([a-z0-9\-]+)\]")


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
    svc.videos().update(part="status", body={"id": video_id, "status": status}).execute()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="予約中の動画の公開時刻を動かす／外す")
    ap.add_argument("--list", action="store_true", help="予約の一覧を出す（二重予約に印）")
    ap.add_argument("--move", nargs=2, metavar=("VIDEO_ID", "JST"),
                    help="公開時刻を動かす。例: --move abc123 2026-09-04T09:00")
    ap.add_argument("--unschedule", metavar="VIDEO_ID",
                    help="予約を外す（private のまま残るので、時刻を入れ直せば戻ります）")
    args = ap.parse_args(argv)

    svc = uploader._service()

    if args.move:
        vid, when = args.move
        at = datetime.fromisoformat(when).replace(tzinfo=JST).astimezone(timezone.utc)
        if at <= datetime.now(timezone.utc):
            raise SystemExit(f"過去の時刻です: {when} JST")
        _update(svc, vid, at.strftime("%Y-%m-%dT%H:%M:%SZ"))
        print(f"[reschedule] {vid} を {when} JST へ移しました")
        return 0

    if args.unschedule:
        _update(svc, args.unschedule, None)
        print(f"[reschedule] {args.unschedule} の予約を外しました（private のまま残っています）")
        return 0

    _show(_scheduled(svc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
