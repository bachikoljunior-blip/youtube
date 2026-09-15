"""同じニッチの**他人のチャンネル**を数える（2026-09-15 21:0x・optimizer・Fable 5.1・ultracode）。

**なぜ要るか（この道具が無かったあいだ、何を間違えていたか）**:
09/13 21:0x から 09/15 19:0x まで、**7周** が固定 2（期限内に届くか）に
「**できない**」と答えてきました。その答えはどれも**自分の数だけ**を伸ばした外挿です
（`trend.rev_deadline` の 168倍・29倍・39〜62倍）。**比べる相手が 1つ もありませんでした。**

**この口で 09/15 21:0x に測ったもの**（`data/niche_corpus.jsonl` に既に在った 297チャンネル・
`channels.list` **6単位** ＝ 日枠の 0.06%）:

    齢 400日 未満のチャンネル        **55本**（同じニッチ ＝ 年金・給付金・退職・税）
    いちばん速い                   **831人/日**（`年金・給付金完全攻略チャンネル`・齢 178日・登録 14.8万・本 17）
    齢 44日 のチャンネル             **カメ先生のもらえるお金**・登録 **5,780人**・総再生 **89.3万回**・本 **40**
    うちの口（同じ日）               登録 **29人**・総再生 **9.0万回**・本 **283**・**0.38人/日**

＝ **「3ヶ月でこの門は抜けない」は、この口の数では嘘です。** 同じニッチで、**44日**の
チャンネルが本 40本 で 89万回 を出しています（1本 median 1,163回・最大 65万回）。
**届かないのは期限ではなく、うちの 1本あたりの数**です。

**そして、その 40本 は全部 長尺でした**（下の実測）。速い側 6チャンネルの**尺の中央値**:

    年金・給付金完全攻略     **2,200秒（36.7分）**・本 17・再生 median 65,623・いいね率 1.269%
    元ハロワ職員まゆみ       **1,116秒（18.6分）**・本 52・再生 median 71,010・いいね率 1.442%
    元社労士ゆき            **1,189秒（19.8分）**・本 15・再生 median 34,869・いいね率 1.211%
    元ハロワ職員ケン         **891秒（14.9分）**・本 31・再生 median  4,182・いいね率 1.379%
    カメ先生（齢44日）       **1,619秒（27.0分）**・本 40・再生 median  1,163・いいね率 0.543%
    あき姉（ショート 72本）   全体 105秒 だが**上位 6本 は全部 908〜1,674秒の長尺**
    ----------------------------------------------------------------------------
    **うちの長尺**           **320〜487秒（5.3〜8.1分）**・うちのショート 60〜90秒・いいね率 **0.151%**

**＝ うちの「長尺」は、この族の尺の 1/3〜1/7 です。** 扉(b) の通貨は**時間**なので、
尺は再生数と同じ重みの掛け算です（25分 × 40% ＝ 10分/回 対 7分 × 45% ＝ 3.2分/回 ＝ **3.1倍**）。

**覆る条件**:
 (1) うちの長尺の 48h 中央値が、この族の**下端**（カメ先生 1,163回）を越えたら、
     「尺が足りない」は説明として弱くなる ＝ この段を数え直すこと。
 (2) この 6チャンネルのうち **2つ 以上**が 90日 のあいだに伸びを止めたら（`peers` を撃ち直して比べる）、
     族そのものが縮んでいる側 ＝ 題材の外へ出る話になる。
 (3) 齢 400日 未満・登録/日 60人 以上 の門（`YOUNG_DAYS`・`FAST_SUBS_PER_DAY`）は、
     **55本 のうち 6本 が残る**ように置いた数です。残りが 2本 を切ったら門を緩めること
     （比べる相手が減ると、この口は何も言えなくなる）。
 (4) **この口は「なぜ伸びたか」を言いません。** 尺・題・登録数を並べるだけで、
     因果は撃って確かめる側（`docs/GOAL.md` (4-j) の A/B）。

**単位**: `channels.list` 1単位/50件・`playlistItems.list` 1単位/50件・`videos.list` 1単位/50件。
速い 6チャンネル ぶんで **約 30単位**（日枠 10,000 の 0.3%）。台帳が `PEERS_MIN_H` より新しければ
API を撃たずに台帳から読みます。
"""
from __future__ import annotations

import datetime as dt
import json
import re
import statistics as st
from pathlib import Path

from .common import DATA, now_jst

#: 比べる相手を選ぶ門（覆る条件 (3)）。
YOUNG_DAYS = 400
FAST_SUBS_PER_DAY = 60.0
#: 1チャンネルあたり何本まで引くか（`playlistItems` の 1ページ ＝ 50本 で足りる側）。
MAX_VIDEOS = 100
#: 台帳がこれより新しければ API を撃たない。
PEERS_MIN_H = 24.0
#: 短尺と長尺の境（YouTube の Shorts は 180秒 まで）。
SHORT_SECS = 180

PEERS = DATA / "peers.jsonl"
CORPUS = DATA.parent / "niche_corpus.jsonl"


def corpus_channels() -> list[str]:
    """`data/niche_corpus.jsonl`（既に在る・API 0単位）に出てくるチャンネル id。"""
    out: set[str] = set()
    if not CORPUS.exists():
        return []
    for line in CORPUS.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            continue
        c = d.get("channel")
        if isinstance(c, str) and c.startswith("UC"):
            out.add(c)
    return sorted(out)


def iso_secs(d: str) -> int:
    """`PT36M40S` → 2200。"""
    m = re.match(r"^P(?:(\d+)D)?T(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", d or "")
    if not m:
        return 0
    day, h, mi, s = (int(x) if x else 0 for x in m.groups())
    return day * 86400 + h * 3600 + mi * 60 + s


def rank(rows: list[dict], now: dt.datetime | None = None) -> list[dict]:
    """チャンネルの行に「登録/日」を付けて並べ替える（API 0単位・この関数が門の唯一の出どころ）。"""
    now = now or now_jst()
    out = []
    for r in rows:
        try:
            cr = dt.datetime.fromisoformat((r.get("created") or "").replace("Z", "+00:00"))
        except ValueError:
            continue
        days = max((now - cr.astimezone(now.tzinfo)).days, 1)
        out.append({**r, "age_days": days, "subs_per_day": r.get("subs", 0) / days})
    out.sort(key=lambda r: -r["subs_per_day"])
    return out


def young_fast(rows: list[dict]) -> list[dict]:
    """比べる相手 ＝ 齢が若く、速いもの（覆る条件 (3) の門はここ 1か所）。"""
    return [r for r in rank(rows)
            if r["age_days"] < YOUNG_DAYS and r["subs_per_day"] >= FAST_SUBS_PER_DAY]


def shape(items: list[dict]) -> dict:
    """1チャンネルの本の束 → 尺・再生・いいね率（この道具が言う「形」はこの 1か所）。"""
    if not items:
        return {}
    secs = [iso_secs(i.get("dur", "")) for i in items]
    views = [int(i.get("views", 0)) for i in items]
    tv = sum(views) or 1
    longs = [s for s in secs if s > SHORT_SECS]
    return {
        "n": len(items),
        "secs_median": int(st.median(secs)),
        "secs_median_long": int(st.median(longs)) if longs else 0,
        "long": len(longs), "short": len(secs) - len(longs),
        "views_median": int(st.median(views)), "views_max": max(views),
        "like_rate": 100 * sum(int(i.get("likes", 0)) for i in items) / tv,
        "comment_rate": 100 * sum(int(i.get("comments", 0)) for i in items) / tv,
    }


def last_pull() -> dict | None:
    if not PEERS.exists():
        return None
    rows = [json.loads(l) for l in PEERS.read_text(encoding="utf-8").splitlines() if l.strip()]
    return rows[-1] if rows else None


def fresh_enough(row: dict | None, now: dt.datetime | None = None) -> bool:
    if not row:
        return False
    now = now or now_jst()
    try:
        at = dt.datetime.fromisoformat(row["at"])
    except (KeyError, ValueError):
        return False
    return (now - at).total_seconds() / 3600 < PEERS_MIN_H


def lines(row: dict, mine: dict | None = None) -> list[str]:
    """印字する行（判定はしない ＝ 数を並べるだけ・覆る条件 (4)）。"""
    out = [f"**同じニッチの他人**（`peers`・{row['at'][:16]}・{row.get('units', 0)}単位・"
           f"母数 {row.get('scanned', 0)}チャンネル・門 齢<{YOUNG_DAYS}日・登録/日≧{FAST_SUBS_PER_DAY:.0f}）:"]
    for c in row.get("channels", []):
        s = c.get("shape") or {}
        if not s:
            continue
        out.append(
            f"  {c['subs_per_day']:7.1f}人/日 登録{c['subs']:>8,} 齢{c['age_days']:>4}日 "
            f"本{s['n']:>3}（長{s['long']}/短{s['short']}） 尺中央 {s['secs_median']:>5}秒 "
            f"再生中央 {s['views_median']:>7,} 最大 {s['views_max']:>9,} "
            f"いいね {s['like_rate']:.3f}%  {c['title'][:20]}")
    if mine:
        out.append(f"  {mine.get('subs_per_day', 0):7.1f}人/日 登録{mine.get('subs', 0):>8,} "
                   f"齢{mine.get('age_days', 0):>4}日 本{mine.get('n', 0):>3} "
                   f"尺中央 {mine.get('secs_median', 0):>5}秒 再生中央 {mine.get('views_median', 0):>7,} "
                   f"最大 {mine.get('views_max', 0):>9,} いいね {mine.get('like_rate', 0):.3f}%  ← **うち**")
    return out


def pull(svc, ids: list[str] | None = None, now: dt.datetime | None = None) -> dict:
    """API を撃って 1行 作る（約 30単位）。`svc` は `yt.svc()`。検査は偽の svc を渡す。"""
    ids = ids if ids is not None else corpus_channels()
    units = 0
    rows = []
    for i in range(0, len(ids), 50):
        r = svc.channels().list(part="snippet,statistics", id=",".join(ids[i:i + 50])).execute()
        units += 1
        for it in r.get("items", []):
            s = it.get("statistics", {})
            sn = it.get("snippet", {})
            rows.append({"id": it["id"], "title": sn.get("title", ""),
                         "created": sn.get("publishedAt", ""),
                         "subs": int(s.get("subscriberCount", 0) or 0),
                         "views": int(s.get("viewCount", 0) or 0),
                         "videos": int(s.get("videoCount", 0) or 0)})
    picked = young_fast(rows)
    for c in picked:
        r = svc.channels().list(part="contentDetails", id=c["id"]).execute()
        units += 1
        items = r.get("items", [])
        if not items:
            continue
        up = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
        vids, token = [], None
        while len(vids) < MAX_VIDEOS:
            pr = svc.playlistItems().list(part="contentDetails", playlistId=up,
                                          maxResults=50, pageToken=token).execute()
            units += 1
            vids += [i["contentDetails"]["videoId"] for i in pr.get("items", [])]
            token = pr.get("nextPageToken")
            if not token:
                break
        got = []
        for i in range(0, len(vids), 50):
            vr = svc.videos().list(part="snippet,statistics,contentDetails",
                                   id=",".join(vids[i:i + 50])).execute()
            units += 1
            for it in vr.get("items", []):
                s = it.get("statistics", {})
                got.append({"id": it["id"], "title": it["snippet"]["title"],
                            "pub": it["snippet"].get("publishedAt", ""),
                            "dur": it.get("contentDetails", {}).get("duration", ""),
                            "views": int(s.get("viewCount", 0) or 0),
                            "likes": int(s.get("likeCount", 0) or 0),
                            "comments": int(s.get("commentCount", 0) or 0)})
        c["shape"] = shape(got)
        # `id` を足したのは 2026-09-16 02:0x（optimizer・Fable・ultracode）。
        # **サムネを見るため**です —— 21:0x は題の形だけを写しましたが、一覧で先に目に入るのは絵の側で、
        # `studio/thumb.py` は peers が在る前（09/15 00:xx）に**手もとの理屈だけ**で描いた形のままでした。
        # サムネの URL は `https://i.ytimg.com/vi/<id>/maxresdefault.jpg`（**API 0単位**・公開）。
        c["top"] = [{"id": g["id"], "views": g["views"], "secs": iso_secs(g["dur"]), "title": g["title"]}
                    for g in sorted(got, key=lambda g: -g["views"])[:6]]
    return {"at": (now or now_jst()).isoformat(timespec="seconds"),
            "scanned": len(rows), "units": units, "channels": picked}


def save(row: dict) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    with PEERS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")
