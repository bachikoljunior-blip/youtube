#!/usr/bin/env python3
"""**予約中の本を1本消す。** 作り直して差し替えるときの最後の1手。

    python scripts/unschedule.py <video_id> --why "<1行の理由>"

## なぜ要るか（2026-08-15）

`docs/trigger_main.md` §5 は「**動画ファイル本体は直せない。絵と音を直すには
消して上げ直すしかない**」と書いているのに、**消す道具がどこにもありませんでした。**
その場で書いた1行は auto mode classifier に弾かれます（当然で、
`videos().delete` は取り消せない操作です）。**手順が要求する操作は、
毎回その場で書くのではなく、条件を書いた道具にしておくこと。**

## 守っていること

**公開済みは消しません。** 誰かが URL を持っている・再生や評価やコメントが
付いている可能性があるものは、消すと本当に失われます。
消してよいのは**一度も公開されていない予約中の本**だけで、そちらは
再生も評価もコメントも0なので、動画IDが変わっても失うものがありません
（§5「予約中の本は一度も公開されていないので…渋る理由は URL ではない」）。

**順番も守ること。** §5 は「**先に作る、次に予約を移す、最後に消す**」。
消してから作ると、その間ずっと予約に穴が空きます
（**投稿が途切れるのが最大の損失**）。この道具は最後に呼ぶもの。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import auth


def main() -> int:
    ap = argparse.ArgumentParser(description="予約中の本を1本消す（公開済みは消さない）")
    ap.add_argument("video_id")
    ap.add_argument("--why", required=True, help="消す理由を1行で。JOURNAL に写すため")
    ap.add_argument("--force-public", action="store_true",
                    help="公開済みでも消す。**再生・評価・コメントを失います**")
    args = ap.parse_args()

    yt = auth.youtube()
    resp = yt.videos().list(part="status,snippet,statistics", id=args.video_id).execute()
    items = resp.get("items") or []
    if not items:
        print(f"[unschedule] {args.video_id} が見つかりません（既に消えている？）")
        return 1

    item = items[0]
    status = item.get("status") or {}
    stats = item.get("statistics") or {}
    privacy = status.get("privacyStatus")
    publish_at = status.get("publishAt")
    views = int(stats.get("viewCount") or 0)
    title = (item.get("snippet") or {}).get("title", "")

    print(f"[unschedule] {args.video_id} 『{title}』")
    print(f"             公開状態 {privacy} / 予約 {publish_at or 'なし'} / 再生 {views}")

    if privacy == "public" and not args.force_public:
        print("[unschedule] **公開済みなので消しません。** "
              "URL を持っている人がいる可能性があり、再生も評価も失われます。"
              "本当に消すなら --force-public")
        return 2
    if views > 0 and not args.force_public:
        print(f"[unschedule] **再生が {views} 回ついているので消しません。** "
              "予約中なら0のはずで、0でないなら一度公開されています")
        return 2

    yt.videos().delete(id=args.video_id).execute()
    print(f"[unschedule] 消しました: {args.video_id}")
    print(f"[unschedule] 理由: {args.why}")
    print("[unschedule] **`docs/JOURNAL.md` に理由を書くこと。** "
          "消した記録が残らないと、次の回が『なぜ予約が1本減ったか』を追えません")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
