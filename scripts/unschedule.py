#!/usr/bin/env python3
"""**予約中の本を1本、公開させないようにする。** 作り直して差し替えるときの最後の1手。

    python scripts/unschedule.py <video_id> --why "<1行の理由>"   # 予約を外す（既定）
    python scripts/unschedule.py <video_id> --why "..." --delete   # 消す（弾かれる）

## 消すのをやめた理由（2026-08-15 に既定を入れ替えた）

**この道具は 8/15 に4回とも弾かれ、1本も処理できませんでした。**
`videos().delete` は取り消せないので、環境の判定が止めるのは当然です。
**そして親が確かめたところ、この判定を外す手段はオーナーの画面に存在しません**
（権限モードは3つしか選べず、「確認しない」に当たるものが無い。
`docs/FOR_OWNER.md` 済み3）。**つまり「消す」道は、待っても開きません。**

**しかし目標が要求しているのは「消すこと」ではなく、
「欠陥のある本を公開させないこと」です。** それは `videos().update` で
`privacyStatus=private` にし、`publishAt` を落とせば足ります。

- **取り消せます**（もう一度予約すれば戻る）。だから判定が止める理由がない
- **公開はされません。** 予約が消えるので、その日時が来ても出ない
- 本体はアカウントに残るので、**あとで見直す材料としても残る**

**「消す」ほうは `--delete` に退避してあります**（弾かれる前提。
判定が変わったとき用に、条件つきで残す）。

## 守っていること

**公開済みには触れません。** 誰かが URL を持っている・再生や評価やコメントが
付いている可能性があるものを private にすると、その視聴者から見えなくなります。
触ってよいのは**一度も公開されていない予約中の本**だけで、そちらは
再生も評価もコメントも0なので、失うものがありません
（§5「予約中の本は一度も公開されていないので…渋る理由は URL ではない」）。

**順番も守ること。** §5 は「**先に作る、次に予約を移す、最後に外す**」。
先に外すと、その間ずっと予約に穴が空きます
（**投稿が途切れるのが最大の損失**）。この道具は最後に呼ぶもの。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import reschedule  # noqa: E402  （書き込みの実装は1か所だけ）
from src import uploader  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(
        description="予約中の本を1本、公開させないようにする（公開済みには触らない）")
    ap.add_argument("video_id")
    ap.add_argument("--why", required=True, help="外す理由を1行で。JOURNAL に写すため")
    ap.add_argument("--delete", action="store_true",
                    help="予約を外すのではなく消す。**取り消せません。**"
                         "環境の判定に弾かれる前提で残してあります")
    ap.add_argument("--force-public", action="store_true",
                    help="公開済みでも実行する。**視聴者から見えなくなります**")
    args = ap.parse_args()

    yt = uploader._service()
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
        print("[unschedule] **公開済みなので触りません。** "
              "URL を持っている人がいる可能性があり、その人から見えなくなります。"
              "本当にやるなら --force-public")
        return 2
    if views > 0 and not args.force_public:
        print(f"[unschedule] **再生が {views} 回ついているので触りません。** "
              "予約中なら0のはずで、0でないなら一度公開されています")
        return 2

    if args.delete:
        yt.videos().delete(id=args.video_id).execute()
        print(f"[unschedule] 消しました: {args.video_id}")
        print(f"[unschedule] 理由: {args.why}")
        print("[unschedule] **`docs/JOURNAL.md` に理由を書くこと。** "
              "消した記録が残らないと、次の回が『なぜ予約が1本減ったか』を追えません")
        return 0

    if not publish_at and privacy == "private":
        print("[unschedule] **すでに予約なしの private です。** 何もしません")
        return 0

    # **書き込みは `reschedule._update` に任せること**（2026-08-16 18:5x）。
    # ここには同じ書き込みが**もう1つ**あり、`status` のうち4つの欄しか写して
    # いませんでした（あちらは読み取り専用の欄だけ落として全部写す）。
    # **同じことをする実装が2つある**のは、この repo が7回踏んだ「片方だけ直す」形
    # そのものです。実際この道具は `auth.youtube()`（**存在しない関数**）で
    # 落ちたまま放置されていて、気づいたのは 18:5x に実際に呼んだときでした。
    reschedule._update(yt, args.video_id, None)

    after = yt.videos().list(part="status", id=args.video_id).execute()
    a_status = ((after.get("items") or [{}])[0].get("status") or {})
    a_privacy = a_status.get("privacyStatus")
    a_publish = a_status.get("publishAt")
    print(f"[unschedule] 予約を外しました: {args.video_id}")
    print(f"             いま 公開状態 {a_privacy} / 予約 {a_publish or 'なし'}")
    print(f"[unschedule] 理由: {args.why}")
    if a_publish:
        print("[unschedule] **予約が残っています。落ちていません。** "
              "この日時に公開されるので、確かめ直すこと")
        return 3
    print("[unschedule] **`docs/JOURNAL.md` に理由を書くこと。** "
          "記録が残らないと、次の回が『なぜ予約が1本減ったか』を追えません")
    print("[unschedule] 本体は残っています（private）。"
          "戻すなら同じ動画IDに publishAt を置き直すだけです")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
