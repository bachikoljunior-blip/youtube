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

import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.uploader import _service  # noqa: E402

JST = timezone(timedelta(hours=9))
LOOKAHEAD_DAYS = 3      # 何日先まで予約の空きを見るか
# 予算の単位は **週間使用量の%**。API換算のドルは実際の消費と対応しないので使わない
# （2026-08-05 に $258 と見積もって大きく外した。実測では1〜2%だった）。
WEEKLY_PCT = 15          # 定常。土曜07:00 JST 区切り（2026-08-05 30%→15% オーナー指示）
PCT_PER_REPLY = 0.0107   # 実測: 161応答の対話セッションで1〜2%

# オーナーが個別に出した割り当て。**「この時刻から、この%まで」** と読む。
#   (開始時刻 ISO8601, %)
# 定常（WEEKLY_PCT）より絞ることも緩めることもある。
#
# **累計ではなく「そこから先」で数えること。** 2026-08-05 に「今から1.5%」と
# 言われた。その時点で今週の累計は6.7%あり、累計で測ると指示の意味が変わる。
# **区切りの時刻を持たないと、この2つを区別できない。**
#
# 週の区切り（土曜07:00 JST）を過ぎたら自動で無視され、定常に戻る。
# 次に指示が来たらこの2つの値だけ差し替えること。
ALLOWANCE = ("2026-08-05T19:11+09:00", 0.75)   # 1.5 の半分（同日オーナー指示）


def _is_short(video: dict) -> bool:
    """ショートかどうか。**尺で見る。** 題の #Shorts は付け忘れがある。"""
    dur = video["contentDetails"]["duration"]
    m = re.fullmatch(r"PT(?:(\d+)M)?(?:(\d+)S)?", dur)
    if not m:
        return False
    return int(m.group(1) or 0) * 60 + int(m.group(2) or 0) <= 180


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
    """トークン予算を出す。**単位は週間使用量の%。**

    土曜07:00 JST 区切り。定常は30%、週ごとに絞ることがある。

    **API換算のドルで見積もらないこと。** 2026-08-05 にセッション記録から
    トークン数を集計して「$258 使った」と報告したが、実際のサブスク消費は
    週間使用量の1〜2%だった。**計算は合っていたが、比べる相手が違った。**
    数字を出す前に「これは何と比較できる量か」を問うこと。

    較正: 161応答の対話セッションで1〜2% → 1応答あたり約0.01%。
    **律速は頻度ではなく、1回が長引くこと。** 通常の自動起動は10〜20応答で収まる。
    """
    now = datetime.now(JST)
    end = now.replace(hour=7, minute=0, second=0, microsecond=0)
    while end.weekday() != 5 or end <= now:      # 5 = 土曜
        end += timedelta(days=1)
    hours = (end - now).total_seconds() / 3600
    wakes = max(1, round(hours / 6))

    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from usage import summary, week_start

    since, pct = ALLOWANCE
    start = datetime.fromisoformat(since)
    active = start >= week_start(now)        # 週をまたいだら失効し、定常に戻る
    budget = pct if active else WEEKLY_PCT

    print("\n=== トークン予算（単位は週間使用量の%）===")
    print(f"  今週のリセット: {end.strftime('%m/%d %H:%M JST')}（あと {hours:.0f} 時間）")

    # **実測。** これまでオーナーに教えてもらうしかなかったが、セッション記録から数えられる。
    try:
        if active:
            s = summary(start)
            left = budget - s["pct"]
            print(f"  **{start:%m/%d %H:%M JST} から {pct}%** の割り当て（定常は {WEEKLY_PCT}%）")
            print(f"  実測: それ以降 {s['replies']:,}応答 / {s['tokens']/1e6:.0f}M トークン"
                  f" → **{s['pct']:.2f}%**（楽観側 {s['pct_optimistic']:.2f}%）")
            print(f"  残り **{left:.2f}%**（≒{max(0, left) / PCT_PER_REPLY:.0f}応答）")
            if left <= 0:
                print("  [!] 割り当てを使い切った可能性がある。**いま切ること。**")
            w = summary()
            print(f"  参考: 今週の累計は {w['pct']:.1f}%（割り当てとは別の量。混ぜないこと）")
        else:
            print(f"  定常 {WEEKLY_PCT}%")
            s = summary()
            print(f"  実測: 今週これまで {s['replies']:,}応答 / {s['tokens']/1e6:.0f}M トークン"
                  f" → **{s['pct']:.1f}%**（楽観側 {s['pct_optimistic']:.1f}%）")
            if s["pct"] > budget:
                print(f"  [!] 割り当て {budget}% を超えている可能性がある。**この回は短く切ること。**")
    except Exception as exc:
        print(f"  実測できませんでした: {str(exc)[:70]}")

    per = budget / wakes
    print(f"  6時間おきなら残り約 {wakes} 回 → 1回あたり {per:.2f}%（≒{per / PCT_PER_REPLY:.0f}応答）")
    if per / PCT_PER_REPLY < 10:
        print("  [!] 1回10応答を下回る。日次（cron `0 23 * * *`）に落とすことを検討")
        print("      落とすときは戻す仕組みも一緒に用意する（docs/TRIGGER.md）")
    print("  **律速は頻度ではなく、1回が長引くこと。** 通常の自動起動は10〜20応答で収まる。")
    print("  API換算のドルはサブスクの消費と対応しない。混同しないこと。")
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
    short_days: set[str] = set()      # ショートが予約されている日（MM/DD）

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
            if _is_short(v):
                short_days.add(_fmt(publish_at).split()[0])
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
    # **日付だけ見てはいけない。形式ごとに見る。**
    # 2026-08-05、8/6 と 8/7 は「予約あり」と出ていたが、どちらも長尺だった。
    # 長尺は4本すべて0〜1回で、**露出が出ているのはショートだけ。**
    # 「予約が入っている日」を空きでないと数えたせいで、唯一効いている形式が
    # 翌日から途切れる状態を見落としかけた。**効いている形式で数える。**
    gaps = []
    for ahead in range(1, LOOKAHEAD_DAYS + 1):
        day = (datetime.now(JST) + timedelta(days=ahead)).strftime("%m/%d")
        if day not in short_days:
            gaps.append(day)
    if gaps:
        print(f"\n[!] **ショート**の予約が入っていない日: {', '.join(gaps)}")
        print("    投稿が途切れるのが最大の損失。生成を撃ち直すこと。")
        print("    長尺が入っていても空きとみなす。露出が出ているのはショートだけだから。")
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
