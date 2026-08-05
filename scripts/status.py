#!/usr/bin/env python3
"""チャンネルのいまの状態を1画面に出す。

    python scripts/status.py [日数]

なぜ要るか。**判断の側の間違いも、被覆の問題だった。**

この日、2つ間違えかけた。ひとつは `statistics.viewCount` が 5634 なのを見て
ショートが伸びたと思ったこと。実際には動画ごとに数えると合計2回で、5634 は
このチャンネルの前身のものだった。**チャンネル単位の数字は前身を含む。**

もうひとつは、予約公開のはずの動画が private のまま publishAt を持っていない、
という状態を見落としかけたこと。これは黙って永久に公開されない。

どちらも「毎回いくつも API を叩いて頭の中で組み立てる」からこそ起きる。
組み立てを機械にやらせて、危ない状態には印を付ける。

`scripts/inspect_build.py` が目視に対してやったことを、判断に対してやる。
面倒だから飛ばされる、という同じ原因を、同じやり方で潰している。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.uploader import _service  # noqa: E402

JST = timezone(timedelta(hours=9))
LOOKAHEAD_DAYS = 3      # 何日先まで予約の空きを見るか
WEEKLY_CREDITS = 100    # 土曜07:00 JST 区切り。オーナーが決めた上限


def _fmt(iso: str) -> str:
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(JST).strftime("%m/%d %H:%M")


def print_hypotheses() -> None:
    """検証していない前提と、その期限を毎回出す。

    **推測は、期限を切らないと永久に推測のまま残る。** JOURNAL に書くだけでは
    読み飛ばされるので、状態を見るたびに目に入る場所に出す。
    期限を過ぎたものは目立たせる。そこで必ず判定させる。
    """
    import yaml

    path = Path(__file__).resolve().parent.parent / "config" / "hypotheses.yaml"
    if not path.exists():
        return
    items = yaml.safe_load(path.read_text(encoding="utf-8")).get("hypotheses", [])
    if not items:
        return

    today = datetime.now(JST).date()
    print("\n=== まだ検証していない前提 ===")
    for h in items:
        due = datetime.strptime(str(h["deadline"]), "%Y-%m-%d").date()
        left = (due - today).days
        mark = "[!] 期限切れ" if left < 0 else ("[!] 今日が期限" if left == 0 else f"あと{left}日")
        print(f"  {mark}  {h['claim']}")
        print(f"        外れとみなす条件: {h['falsified_if']}")
        if left <= 0:
            print("        → いま判定すること。外れていたら次を順に試す:")
            for nxt in h.get("next_if_false", []):
                print(f"           - {nxt}")


def print_budget() -> None:
    """トークン予算の残り時間を出す。

    **土曜07:00 JST から翌土曜07:00 JST までで API換算100クレジット**
    （2026-08-05 にオーナーが決めた）。使い切ると次のリセットまで何もできない。
    投稿が止まるのが最大の損失なので、**予算は投稿の予約を切らさない側に使う。**

    クレジットの実消費はここからは読めないので、出せるのは「残り時間」と
    「1日あたりいくら使える計算か」まで。**残り時間に対して自分が何回起きるかを
    数えて、1回の重さを決めること。**
    """
    now = datetime.now(JST)
    end = now.replace(hour=7, minute=0, second=0, microsecond=0)
    while end.weekday() != 5 or end <= now:      # 5 = 土曜
        end += timedelta(days=1)
    hours = (end - now).total_seconds() / 3600

    print("\n=== トークン予算 ===")
    print(f"  今週のリセット: {end.strftime('%m/%d %H:%M JST')}（あと {hours:.0f} 時間）")
    print(f"  週 {WEEKLY_CREDITS} クレジット。1日あたり約 {WEEKLY_CREDITS / 7:.0f}")
    print("  高いもの: 画像(contact sheet)の Read／長い生成を待つこと／同じ確認の繰り返し")
    print("  **投稿は予約済みなら起きなくても公開される。** 無理に起きないこと")


def main(days: int = 7) -> int:
    youtube = _service()
    channel = youtube.channels().list(part="snippet,contentDetails,statistics", mine=True).execute()["items"][0]
    stats = channel["statistics"]

    print(f"=== {channel['snippet']['title']} ===")
    print(f"登録者 {stats.get('subscriberCount', '?')}人")
    print(
        f"チャンネル総再生 {stats.get('viewCount', '?')}回"
        "  ← 前身の動画も含む。こちらの成果ではない。下の動画ごとの数字で見ること\n"
    )

    uploads = channel["contentDetails"]["relatedPlaylists"]["uploads"]
    items = youtube.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50).execute()
    ids = [i["contentDetails"]["videoId"] for i in items.get("items", [])]
    if not ids:
        print("動画がありません")
        return 0

    videos = youtube.videos().list(
        part="snippet,status,statistics,contentDetails", id=",".join(ids)
    ).execute()["items"]

    now = datetime.now(timezone.utc)
    ours = 0
    stranded: list[str] = []
    scheduled: list[str] = []

    print(f"{'ID':13s} {'状態':16s} {'尺':>7s} {'再生':>5s} {'高評価':>4s}  題")
    for v in videos:
        st, sn = v["status"], v["snippet"]
        vs = v["statistics"]
        views = int(vs.get("viewCount", 0))
        ours += views

        publish_at = st.get("publishAt")
        if st["privacyStatus"] == "public":
            state = f"公開 {_fmt(sn['publishedAt'])}"
        elif publish_at:
            hours = (datetime.fromisoformat(publish_at.replace("Z", "+00:00")) - now).total_seconds() / 3600
            state = f"予約 {_fmt(publish_at)}"
            scheduled.append(f"{v['id']} {_fmt(publish_at)}（あと{hours:.1f}時間）")
        else:
            state = f"{st['privacyStatus']} 予約なし"
            stranded.append(f"{v['id']} {sn['title'][:34]}")

        dur = v["contentDetails"]["duration"].replace("PT", "").lower()
        print(f"{v['id']:13s} {state:16s} {dur:>7s} {views:5d} {vs.get('likeCount', 0):>4s}  {sn['title'][:34]}")

    print(f"\nこちらの動画の再生 合計 {ours}回（{len(videos)}本）")

    if scheduled:
        print("\n[予約中]")
        for s in scheduled:
            print("  " + s)

    # 予約が埋まっていない日を出す。**背後の生成はコンテナ再起動で消える**ので、
    # 「走らせたはず」は当てにならない。実際に 8/7 が空になっていたのを見落としかけた。
    # 投稿が途切れるのが最大の損失なので、空きは目立たせる。
    covered = {s.split()[1].split("/")[0] + "/" + s.split()[1].split("/")[1] for s in scheduled}
    gaps = []
    for ahead in range(1, LOOKAHEAD_DAYS + 1):
        day = (datetime.now(JST) + timedelta(days=ahead)).strftime("%m/%d")
        if day not in covered:
            gaps.append(day)
    if gaps:
        print(f"\n[!] 予約が入っていない日: {', '.join(gaps)}")
        print("    投稿が途切れるのが最大の損失。生成を撃ち直すこと。")
        print("    背後の生成はコンテナ再起動で消えるので、ログが残っていてもプロセスは死んでいる。")

    if stranded:
        print("\n[!] 公開されないまま止まっている動画があります:")
        for s in stranded:
            print("  " + s)
        print("  意図的に伏せているものか確認すること。予約し忘れならこのまま永久に出ません。")

    # 流入経路。表示されているのかどうかが、他の全部の前提になる。
    print(f"\n=== 流入経路（直近{days}日） ===")
    try:
        from src.analytics import fetch_traffic

        rows = fetch_traffic(days)
        if not rows or sum(r.get("views", 0) for r in rows) == 0:
            print("  まだ数字が返りません（Analytics は当日ぶんが遅れます）")
        for r in rows:
            print(f"  {r.get('insightTrafficSourceType', '?'):18s} 再生{r.get('views', 0):5d}"
                  f"  視聴{r.get('estimatedMinutesWatched', 0):5d}分")
    except Exception as exc:
        print(f"  読めませんでした: {str(exc)[:120]}")

    print_hypotheses()
    print_budget()

    # 収益化の門。律速がどちらかを毎回見せる（docs/GOAL.md の掛け算）。
    subs = int(stats.get("subscriberCount", 0) or 0)
    print("\n=== 収益化の門まで ===")
    print(f"  登録者     {subs:6d} / 1000   あと {max(0, 1000 - subs)}人")
    print("  総再生時間 は Analytics 側。登録率0.3%なら1000人は約33万再生で、")
    print("  4000時間ぶん（約6万再生）の5倍以上。**律速は登録者のほう。**")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(int(sys.argv[1]) if len(sys.argv) > 1 else 7))
