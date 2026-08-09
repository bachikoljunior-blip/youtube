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
WINDOW_DAYS = 28

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


def collect(days: int = WINDOW_DAYS) -> dict:
    """**使えると分かっているものを、全部引く。**

    返すのは平らな辞書（鍵 → 数値）。前回と引き算できる形にしておく。
    """
    api = _api()
    end = date.today()
    start = end - timedelta(days=days)
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
            for row in query(per, dimensions="video", sort="-views", limit=30):
                vid = row["video"]
                for k, v in row.items():
                    if k != "video":
                        out[f"動画.{vid}.{k}"] = v
            covered.update(per)
            covered.add("video")
        except Exception:
            out["動画.（取れず）"] = None

    missed = sorted(
        set(avail["metrics"] + avail["dimensions"]) - covered - {"video"}
    )
    return {
        "at": datetime.now(JST).isoformat(timespec="seconds"),
        "days": days,
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
    print(f"\n=== 全走査（直近{snap['days']}日 / {snap['at'][:16]}）===")
    cur = snap["values"]

    if prev is None:
        print("  前回の走査がありません。**この回が基準になります。**")
    else:
        old = prev["values"]
        moved = []
        for k, v in cur.items():
            o = old.get(k)
            if isinstance(v, (int, float)) and isinstance(o, (int, float)) and v != o:
                moved.append((k, o, v))
        appeared = [k for k in cur if k not in old]
        gone = [k for k in old if k not in cur]

        print(f"  前回 {prev['at'][:16]} と比べて **動いた {len(moved)}件"
              f" / 増えた {len(appeared)}件 / 消えた {len(gone)}件**")
        if not moved and not appeared:
            print("  **何も動いていません。**")
        for k, o, v in sorted(moved, key=lambda x: -abs(x[2] - x[1]))[:25]:
            print(f"    {k:46} {o} → {v}  ({v - o:+g})")
        for k in appeared[:10]:
            print(f"    [新] {k:42} {cur[k]}")
        for k in gone[:10]:
            print(f"    [消] {k:42} （前回 {old[k]}）")

    if full:
        print("\n  --- 全部の値 ---")
        for k in sorted(cur):
            print(f"    {k:46} {cur[k]}")

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
