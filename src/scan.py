"""**取れるものを全部引いて、前回との差を出す。**

## なぜ要るか

2026-08-09、オーナーに「毎回取得できる情報の全て踏まえて分析してる?」と聞かれ、
確かめたら**していなかった。** その日のうちに、同じ根から3つ出た。

1. **棚卸しが「使っていない次元が8個」と毎回出していたのに、一度も中身を見なかった。**
   見たら「視聴の99.95%がショートのフィード内・視聴ページは28日で2人」だった
2. **見た直後に読み違えた。** `estimatedMinutesWatched ÷ 再生数` で「8.5秒」と出し、
   API が直接返す `averageViewDuration`（22秒）を見ていなかった。**2.6倍ずれた**
3. **`dimensions=video` に `sort` を付け忘れて 400 を食い、
   「この12指標は動画べつには取れない」と誤って分類した。** 付ければ全部取れた

**3つとも「情報が無い」ではなく「持っているのに見ていない／読み違えた」。**

## だから、この設計にした

- **選ばない。** `data/audit.json` に「使える」と記録された指標・次元を**全部**引く。
  こちらが毎回どれを見るか選んでいる限り、選ばなかったものは永久に見えない
- **出し漏れを機械が言う。** 使えるのに出力に現れなかったものは、末尾で警告する。
  **静かに減るのが一番怖い**
- **差を出す。** 生の値を並べるだけでは「分析」にならない。前回の走査と比べて
  **動いたものだけ**を先頭に出す。動いていなければ「動いていない」と出す
- **読み違いを型で塞ぐ。** 既知の罠（下の `TRAPS`）を、該当する数字の隣に必ず出す

## 使い方

    python -m src.scan            # 走査して、前回との差を出す
    python -m src.scan --full     # 差だけでなく全部の値を出す
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from googleapiclient.discovery import build

from . import config
from .auth import credentials

JST = timezone(timedelta(hours=9))
SNAPSHOTS = config.ROOT / "data" / "scan.jsonl"
PROBE = config.ROOT / "data" / "audit.json"

# **窓を動かさない。ここが差分の要。**
#
# 最初は「直近28日」で引いていた。1回目の実データ差分で**全項目が一律 −16**
# になり、設計の穴が見えた。移動窓だと、差分が3つを混ぜてしまう。
#
#     (1) 本当に増えた       … 見たいもの
#     (2) 無効再生の除外     … YouTube が後から引く。正常（8/8 に確認済み）
#     (3) 窓から古い日が抜けた … **こちらの引き方の都合。中身と無関係**
#
# (3) が混ざると、伸びているのに減って見える日が出る。
# 開始日を固定すれば (3) は消え、**増えたら本物・減ったら無効再生の除外**になる。
#
# 2026-08-04 はこの中身で出し始めた日。前身の動画はこれより前なので、
# 固定するとついでに**前身のぶんが混ざらなくなる**（チャンネル合計の罠）。
ERA_START = date(2026, 8, 4)

# **読み違えたことのある組み合わせを、ここに残す。**
# 該当する数字を出すときに必ず並べる。忘れたころに同じ間違いをするので、
# 「気をつける」ではなく**出力に混ぜる。**
TRAPS = {
    "averageViewDuration":
        "**`estimatedMinutesWatched ÷ 再生数` で出さないこと。2.6倍ずれる**"
        "（8/9 に 8.5秒 と誤報。正しくは 22秒）",
    "comments":
        "**`videos.statistics.commentCount` は自分の最初のコメントを数える。**"
        "こちらの Analytics 側は数えない（8/9 に確認）",
    "day":
        "**日次は2〜3日遅れる。**「24時間で〇再生」の判定にはここを使わないこと",
    "動画.":
        "**Data API と Analytics で到着時刻が違う。** `status.py` の一覧は "
        "`videos.statistics`（早い）、ここは Analytics（2〜3日遅い）。"
        "同じ動画で数字が食い違っても、**どちらかが壊れているのではない**"
        "（8/10 に `8rXlUhkfMEU` が Data 側439・Analytics 側は行すら無い状態で確認）",
}


def _available() -> dict:
    """棚卸しが測った「使えるもの」を読む。**こちらが選ばない。**"""
    if not PROBE.exists():
        raise RuntimeError(
            "data/audit.json がありません。先に `python scripts/audit.py` を実行して、"
            "**何が使えるかを機械に測らせること。** 手で選ぶと、選ばなかったものが消えます"
        )
    a = json.loads(PROBE.read_text(encoding="utf-8"))["analytics"]
    return {
        "metrics": a["metrics"],
        "dimensions": a["dimensions"],
        "per_video": a.get("per_video_metrics") or [],
    }


def _api():
    return build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)


def collect(start: date = ERA_START) -> dict:
    """**使えると分かっているものを、全部引く。**

    返すのは平らな辞書（鍵 → 数値）。前回と引き算できる形にしておく。
    **開始日は固定**（`ERA_START` の説明を読むこと）。
    """
    api = _api()
    end = date.today()
    avail = _available()
    out: dict[str, float] = {}
    covered: set[str] = set()

    def query(metrics, dimensions=None, sort=None, limit=25):
        kw = {"ids": "channel==MINE", "startDate": start.isoformat(),
              "endDate": end.isoformat(), "metrics": ",".join(metrics)}
        if dimensions:
            kw["dimensions"] = dimensions
            kw["sort"] = sort or "-views"
            kw["maxResults"] = limit
        r = api.reports().query(**kw).execute()
        head = [h["name"] for h in r.get("columnHeaders", [])]
        return [dict(zip(head, row)) for row in r.get("rows", [])]

    # 1. チャンネル全体。**次元なしの総計**を、使える指標すべてで。
    #    多すぎて1回で通らないことがあるので小分けにする。
    chunk = 8
    for i in range(0, len(avail["metrics"]), chunk):
        ms = avail["metrics"][i:i + chunk]
        try:
            for row in query(ms):
                for k, v in row.items():
                    out[f"合計.{k}"] = v
                    covered.add(k)
        except Exception:
            for m in ms:                      # 1つずつ落として原因を特定する
                try:
                    for row in query([m]):
                        out[f"合計.{m}"] = row[m]
                        covered.add(m)
                except Exception:
                    out[f"合計.{m}"] = None

    # 2. 次元べつ。**使えると測れた次元は全部回す。**
    for dim in avail["dimensions"]:
        if dim == "video":
            continue                          # 動画べつは 3. でまとめて扱う
        try:
            rows = query(["views", "estimatedMinutesWatched"], dimensions=dim)
        except Exception:
            out[f"{dim}.（取れず）"] = None
            continue
        for row in rows:
            key = str(row.get(dim))
            out[f"{dim}.{key}"] = row["views"]
        covered.add(dim)

    # 3. 動画べつ。**engaged と平均視聴秒は本ごとに見ないと意味がない。**
    per = [m for m in ("views", "engagedViews", "averageViewDuration",
                       "averageViewPercentage", "shares", "comments", "likes",
                       "subscribersGained", "videosAddedToPlaylists")
           if m in avail["per_video"]]
    if per:
        try:
            for row in query(per, dimensions="video", sort="-views", limit=200):
                vid = row["video"]
                for k, v in row.items():
                    if k != "video":
                        out[f"動画.{vid}.{k}"] = v
            covered.update(per)
            covered.add("video")
        except Exception:
            out["動画.（取れず）"] = None

    # 4. **チャンネルそのものの状態。Analytics ではないので走査から漏れていた。**
    #
    # 2026-08-10 に気づいた。棚卸しは Analytics の指標しか数えていないので、
    # **`isChannelMonetizationEnabled`（このプロジェクトの目標そのもの）が
    # 一度も視界に入っていなかった。** 登録者の実数も同じ
    # （Analytics にあるのは `subscribersGained` という増分だけ）。
    #
    # **目標の数字が差分に乗っていないのは、走査として穴。**
    # ここが True に変わる日が来たら、その回の差分に必ず出る。
    try:
        ch = build("youtube", "v3", credentials=credentials(),
                   cache_discovery=False).channels().list(
            part="statistics,status", mine=True).execute()["items"][0]
        st, stat = ch.get("statistics", {}), ch.get("status", {})
        out["チャンネル.登録者"] = int(st.get("subscriberCount", 0))
        out["チャンネル.動画数"] = int(st.get("videoCount", 0))
        # **収益化されたか。これが True になるのが目標の門。**
        out["チャンネル.収益化"] = 1 if stat.get("isChannelMonetizationEnabled") else 0
        out["チャンネル.長尺投稿可"] = 1 if stat.get("longUploadsStatus") == "allowed" else 0
        out["チャンネル.公開"] = 1 if stat.get("privacyStatus") == "public" else 0
        # **前身の再生を含む総計。** こちらの成果ではないので、
        # 単体で読まないこと（`status.py` にも同じ注意がある）。
        # それでも入れるのは、**動いたら何かが起きた合図**になるから。
        out["チャンネル.総再生（前身込み）"] = int(st.get("viewCount", 0))
        # **再生リストに実際に入っているか。** パイプラインが毎回
        # 「再生リストに追加」と出しているが、**本数を確かめたことが一度も無かった。**
        # 追加に失敗しても投稿は成功するので、静かにずれうる。
        y3 = build("youtube", "v3", credentials=credentials(), cache_discovery=False)
        pls = y3.playlists().list(part="snippet,contentDetails", mine=True,
                                  maxResults=25).execute().get("items", [])
        for pl in pls:
            name = pl["snippet"]["title"]
            out[f"再生リスト.{name}"] = pl["contentDetails"]["itemCount"]
    except Exception:
        out["チャンネル.（取れず）"] = None

    missed = sorted(
        set(avail["metrics"] + avail["dimensions"]) - covered - {"video"}
    )
    return {
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "since": start.isoformat(),
        "values": out,
        "missed": missed,
    }


def _previous() -> dict | None:
    if not SNAPSHOTS.exists():
        return None
    lines = [ln for ln in SNAPSHOTS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for ln in reversed(lines):
        try:
            return json.loads(ln)
        except json.JSONDecodeError:
            continue
    return None


KEEP = 240          # 1時間ごとなら10日ぶん。差分に要るのは直近だけ


def save(snap: dict) -> None:
    """追記して、古いものを落とす。**放っておくと毎時伸びる。**"""
    SNAPSHOTS.parent.mkdir(parents=True, exist_ok=True)
    lines = []
    if SNAPSHOTS.exists():
        lines = [ln for ln in SNAPSHOTS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    lines.append(json.dumps(snap, ensure_ascii=False))
    SNAPSHOTS.write_text("\n".join(lines[-KEEP:]) + "\n", encoding="utf-8")


def report(snap: dict, prev: dict | None, full: bool = False) -> None:
    since = snap.get("since") or f"直近{snap.get('days', '?')}日"
    print(f"\n=== 全走査（{since} 以降の累計 / {snap['at'][:16]}）===")
    cur = snap["values"]

    if prev is None:
        print("  前回の走査がありません。**この回が基準になります。**")
    elif prev.get("since") != snap.get("since"):
        # **窓が変わったら、差は中身の変化ではない。**
        # 2026-08-09、移動窓から固定窓に変えた直後に一律 −16 が出た。
        # 引き方が変わっただけなのに「減った」と読める形で出ていた。
        # **測り方を変えた回の差分を、実績として読まないこと。**
        print(f"  [!] 前回と**引く範囲が違う**"
              f"（前回 {prev.get('since') or '移動窓'} / 今回 {snap.get('since')}）。")
        print("      **この差分は中身の変化ではありません。** 比較は次の回から。")
    else:
        old = prev["values"]
        moved = []
        for k, v in cur.items():
            o = old.get(k)
            if isinstance(v, (int, float)) and isinstance(o, (int, float)) and v != o:
                moved.append((k, o, v))
        appeared = [k for k in cur if k not in old]
        gone = [k for k in old if k not in cur]

        # **遅れて届いたデータを「増えた」と読まないこと。**
        #
        # 2026-08-10 04:12、合計が +466 になった。伸びたのではなく、
        # **2〜3日遅れていた 8/7 のぶんが届いただけ**だった
        # （`day.2026-08-07` が新しく現れ、その値が466で増加分と完全に一致）。
        #
        # 累計で見ている以上、**後追いの到着と本物の伸びは同じ形で出る。**
        # 見分ける手がかりは `day.*` の新出。ここで名指ししておく。
        backfill = sum(cur[k] for k in appeared
                       if k.startswith("day.") and isinstance(cur[k], (int, float)))
        grew = cur.get("合計.views", 0) - old.get("合計.views", 0)

        print(f"  前回 {prev['at'][:16]} と比べて **動いた {len(moved)}件"
              f" / 増えた {len(appeared)}件 / 消えた {len(gone)}件**")
        if backfill:
            days = [k[4:] for k in appeared if k.startswith("day.")]
            if grew and abs(grew - backfill) <= max(2, grew * 0.05):
                print(f"  [!] **この増加は新しい視聴ではありません。**"
                      f" {'・'.join(days)} のデータが遅れて届いたぶん（{backfill}）で、"
                      f"合計の増加（{grew:+d}）とほぼ一致します")
            else:
                print(f"  [!] {'・'.join(days)} のデータが遅れて届いています（{backfill}）。"
                      f"合計の増加 {grew:+d} のうち、**そのぶんは新しい視聴ではありません**")
        if not moved and not appeared:
            print("  **何も動いていません。**")
        # **割合と平均は「無効再生の除外」で説明できない。**
        # 2026-08-10、`averageViewPercentage` が 29.59→29.51 と動いたとき、
        # 下の一括ラベルが**「無効再生の除外です」と断言した。** 割合は
        # 分母と分子の両方が動くので、減った理由は1つに決まらない。
        # **もっともらしい説明を機械に言わせてはいけない**（今日の教訓そのもの）。
        def _is_count(key: str) -> bool:
            tail = key.split(".")[-1]
            return not any(w in tail for w in
                           ("average", "Rate", "Percentage", "cpm", "Cpm"))

        counts = [x for x in moved if _is_count(x[0])]
        ratios = [x for x in moved if not _is_count(x[0])]
        ups = [x for x in counts if x[2] > x[1]]
        downs = [x for x in counts if x[2] < x[1]]
        for k, o, v in sorted(moved, key=lambda x: -abs(x[2] - x[1]))[:25]:
            print(f"    {k:46} {o} → {v}  ({v - o:+g})")
        # **開始日を固定してあるので、減ったら中身の話ではない。**
        # YouTube が後から無効な再生を引いている（8/8 に確認済み。正常）。
        # ここを「伸びが止まった」と読み違えないための1行。
        if downs and not ups:
            print(f"  **実数 {len(downs)}件がすべて減少。開始日は固定なので、"
                  "これは無効再生の除外です**（正常。伸びが止まったのではない）")
        elif downs:
            print(f"  （実数: 増えた {len(ups)}件 / 減った {len(downs)}件。"
                  "減少は無効再生の除外。開始日を固定してあるので窓の影響ではない）")
        if ratios:
            print(f"  （割合・平均が {len(ratios)}件 動いた。**理由は1つに決まらない**"
                  "ので、実数のほうを見て判断すること）")
        for k in appeared[:10]:
            print(f"    [新] {k:42} {cur[k]}")
        for k in gone[:10]:
            print(f"    [消] {k:42} （前回 {old[k]}）")

    if full:
        print("\n  --- 全部の値 ---")
        for k in sorted(cur):
            print(f"    {k:46} {cur[k]}")

    # **走査そのものの整合を確かめる。**
    #
    # 2026-08-10、`合計.views` と `day.*` の和が **47 ずれていた**。
    # 1時間後に一致した。**集計値が先に修正され、日次の内訳が遅れて追いつく。**
    # ずれている間は、どちらの差分も「いつ起きたか」を取り違える
    # （この日、内訳が追いついただけの −47 を「無効再生の除外」と読みかけた）。
    #
    # **2つの経路で同じものを数えているので、合わなければどちらかが途中。**
    total = cur.get("合計.views")
    day_sum = sum(v for k, v in cur.items()
                  if k.startswith("day.") and isinstance(v, (int, float)))
    if isinstance(total, (int, float)) and day_sum and total != day_sum:
        print(f"  [!] **走査の中で数字が合っていません**"
              f"（合計 {total} / 日次の和 {day_sum}、差 {day_sum - total:+d}）。")
        print("      集計値と日次の内訳は**別々に修正される**ので、"
              "合うまでは差分の時点を信用しないこと")

    for name, note in TRAPS.items():
        if any(name in k for k in cur):
            print(f"  [注] {name}: {note}")

    # **出し漏れは黙らせない。** 使えると測れたのに走査に現れなかったもの。
    if snap["missed"]:
        print(f"\n  [!] **使えるのに引けていない {len(snap['missed'])}件**: "
              f"{', '.join(snap['missed'])}")
        print("      これが増えたら、この走査自体が壊れている。**放置しないこと。**")
    else:
        print("\n  出し漏れ: なし（棚卸しが使えると測ったものは全部引いた）")


def main(argv: list[str] | None = None) -> int:
    import sys

    argv = sys.argv[1:] if argv is None else argv
    snap = collect()
    prev = _previous()
    report(snap, prev, full="--full" in argv)
    save(snap)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
