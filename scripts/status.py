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
# 1応答あたりの%。**固定値をやめた**（2026-08-07）。
# 消費は出力が支配的で、長い JOURNAL を書く回と status.py を読むだけの回では
# 桁が違う。**平均を固定で持つと、どちらの場面でも外れる。**
# 直近の実績から毎回計算し、取れないときだけこの値に落ちる。
PCT_PER_REPLY_FALLBACK = 0.0072


def _pct_per_reply() -> float:
    """直近の実績から「1応答あたり何%か」を出す。

    **場面によって桁が違うので、平均でしか語れない。** それでも固定値より
    実態に近い。今週ぶんで平均するのは、短い窓だと直前の1回に引きずられるから。
    """
    try:
        from usage import summary
        s = summary()
        if s["replies"] >= 20:
            return max(s["pct"] / s["replies"], 1e-5)
    except Exception:
        pass
    return PCT_PER_REPLY_FALLBACK

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
ALLOWANCE = ("2026-08-05T20:48+09:00", 1.0)   # 「Opus5でいまから1%」→ **較正し直したら超過していた**


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



# 使用量の正本。**実メーターを読んでいる唯一の場所**（2026-08-08）。
# チェックアウトが無ければ GitHub 経由で `state/claude-usage.json` を読む。
USAGE_REPO = Path("/workspace/-chatgpt-usage-monitorprivate")


def _print_real_usage() -> bool:
    """**本物の使用量**を出す。出せたら True。

    `-chatgpt-usage-monitorPrivate` が Anthropic の OAuth usage を実際に叩いて
    `state/claude-usage.json` に保存している。**これが正本。**

    `scripts/usage.py` の換算は当てにならない。2026-08-08 に突き合わせたら、
    換算が「今週0.8%」と出しているとき**実際は26%使っていた**（30倍以上の過小評価）。
    オーナーが「なんの当てにもならない」と明言したとおりだった。
    """
    import json

    path = USAGE_REPO / "state" / "claude-usage.json"
    if not path.exists():
        return False
    try:
        d = json.loads(path.read_text(encoding="utf-8"))
        fetched = datetime.fromisoformat(d["fetched_at"].replace("Z", "+00:00")).astimezone(JST)
        windows = d["quota_windows"]
    except Exception as exc:
        print(f"  使用量の正本が読めません: {str(exc)[:60]}")
        return False

    age = (datetime.now(JST) - fetched).total_seconds() / 3600
    print(f"  **実測（{fetched:%m/%d %H:%M} 時点"
          f"{'／%.0f時間前' % age if age >= 1 else '／さきほど'}）**")
    for w in windows:
        hrs = (datetime.fromisoformat(w["resets_at_iso"].replace("Z", "+00:00")).astimezone(JST)
               - datetime.now(JST)).total_seconds() / 3600
        print(f"    {w['window_name']}: **{w['used_percent']}% 使用"
              f"（残り {w['remaining_percent']}%）**"
              f"／リセットまで {hrs:.0f} 時間")
    gov = d.get("governing_window") or {}
    if gov.get("remaining_percent") is not None:
        print(f"  **いま効いている枠: {gov.get('window_name')} "
              f"／残り {gov['remaining_percent']}%**")
    if age > 3:
        print("    [!] 3時間以上前の値。`node show-usage.mjs` で取り直すこと。")
    return True


def print_budget() -> None:
    """使用量を出す。**正本は実メーターだけ。**

    2026-08-08 に恒久指示が変わり、**予算制限は無くなった**（A15）。
    「どちらの使用量もチャットgptsparkの使用量も全てあなたが使っていい」。
    だから**残量は「使い切りそうか」を見るためだけ**に読む。絞る理由にはしない。

    **`scripts/usage.py` の換算はここから外した。** 実メーターと突き合わせたら
    「今週0.8%」と出しているとき**実際は26%**で、30倍以上ずれていた。
    並べて出すと、どちらを信じるか迷う分だけ判断が鈍る。**正本だけ出す。**
    """
    print("\n=== 使用量（実メーター）===")
    if not _print_real_usage():
        return
    print("  **全部使ってよい**（恒久指示 A15）。残すこと自体に価値は無い。")
    print("  絞る理由にしないこと。使い切りそうなときだけ、短く切る。")
    print("  取り直すには:")
    print(f"    node {USAGE_REPO}/scripts/show-usage.mjs")


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

    # **公開後の伸び方を毎回残す。** 総再生数だけ見ていると、当たり外れが
    # 決まる最初の数時間が抜ける（2026-08-06）。人が思い出す前提にしない。
    try:
        from snapshot import print_curves, record
        record(videos)
        print_curves([v["id"] for v in videos],
                     {v["id"]: v["snippet"]["title"] for v in videos})
    except Exception as exc:
        print(f"  伸び方を記録できませんでした: {str(exc)[:70]}")

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

    # **意図して伏せたものは警告しない。** 毎回鳴る警告は無視されるようになり、
    # 本当に予約し忘れたときに効かなくなる（2026-08-05）。理由は withheld.yaml に。
    withheld = {}
    wpath = Path(__file__).resolve().parent.parent / "config" / "withheld.yaml"
    if wpath.exists():
        import yaml
        withheld = {w["id"]: w.get("why", "") for w in
                    (yaml.safe_load(wpath.read_text(encoding="utf-8")) or {}).get("withheld", [])}

    unexpected = [s for s in stranded if s.split()[0] not in withheld]
    if unexpected:
        print("\n[!] 公開されないまま止まっている動画があります:")
        for s in unexpected:
            print("  " + s)
        print("  予約し忘れならこのまま永久に出ません。意図的なら config/withheld.yaml に理由ごと書くこと。")
    on_purpose = [s for s in stranded if s.split()[0] in withheld]
    if on_purpose:
        print(f"\n（意図して伏せている動画 {len(on_purpose)}本。理由は config/withheld.yaml）")

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
