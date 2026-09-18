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
#: corpus の 218チャンネル の `statistics`（`channels.list` 5単位 で引いて落とした台帳）。
#: **これが在るかぎり `capacity_by_size` は API 0単位** です。
NICHE_CHANNELS = DATA.parent / "niche_channels.jsonl"
#: 登録者の帯（`capacity_by_size` の唯一の出どころ）。**うちは 29人 ＝ いちばん下の帯**。
SUB_BANDS = ((0, 1_000), (1_000, 10_000), (10_000, 100_000), (100_000, 10 ** 9))


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


# ---- 門の**先**の距離（`trend.rev_deadline` が持っていない側）-----------------------
#
# **2026-09-16 10:xx・optimizer・Fable 5.1・ultracode が足した。**
#
# `trend.rev_deadline` は **門まで**の距離しか出しません（扉(a) 1,000万回／扉(b) 4,000時間・登録1,000人）。
# **オーナーの目標は門ではなく「月収20万」** ＝ 門を通った**あと**の数で、そこは 09/13〜09/16 の
# どの周も 1度も口を持っていませんでした。固定2（期限内に届くか）に「できない」と答えた 7周 は、
# **門の倍率だけ**を見て答えています。**この口は、その残り半分を出します。**
#
# **やり方**: 要る再生 ＝ 200,000円 ÷ RPM × 1000。それを、同じニッチの他人の実測の分布に当てる
# （`data/niche_corpus.jsonl` ＝ `demand` の種で引いた検索結果。**API 0単位**・ファイルを読むだけ）。
#
# **RPM は うちでは未測です**（収益化前 ＝ 1円も入っていない）。だから帯で出します。
# 上端は `data/rpm_mix.jsonl` の `rpm_max`（長尺の取り分を上げたときの実効RPM・¥1,252〜1,420）。
#
# **覆る条件**:
#  (1) 収益化が通って **実測のRPM が 1か月ぶん**たまったら、帯ではなくその数で引き直すこと
#      （そこがこの口のいちばん大きい前提）。
#  (2) `niche_corpus` は **検索結果の上位**なので、ニッチ全体ではなく「検索で当たる側」に寄っています
#      ＝ この分布は**上振れの側**。中央値ではなく「何本が門を越えているか」で読むこと。
#  (3) 1チャンネルあたりの本数が **2本 を越えた**ら、下の `title_shape` の「分けられない」を数え直すこと。

#: 目標（円/月）。オーナーの本文（`docs/GOAL.md`）。
GOAL_YEN = 200_000
#: 引く RPM の帯（円/1000回）。下端は日本の解説系の下側・上端は `data/rpm_mix.jsonl` の `rpm_max`。
RPM_BAND = (500.0, 1000.0, 1400.0)


def corpus_longs() -> list[dict]:
    """`niche_corpus` の長尺を、動画ごとに 1行 に畳む（同じ動画が何度も引かれている）。"""
    best: dict[str, dict] = {}
    if not CORPUS.exists():
        return []
    for ln in CORPUS.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("form") != "long" or not isinstance(r.get("views"), int):
            continue
        if r["id"] not in best or r["views"] > best[r["id"]]["views"]:
            best[r["id"]] = r
    return list(best.values())


def capacity(rows: list[dict] | None = None) -> dict:
    """門の**先**（月20万）に、このニッチの 1本 が届くか。**判定はしない ＝ 数を並べるだけ**。"""
    L = corpus_longs() if rows is None else rows
    vs = sorted(r["views"] for r in L)
    need = {rpm: int(GOAL_YEN / rpm * 1000) for rpm in RPM_BAND}
    chans: dict[str, int] = {}
    for r in L:
        c = r.get("channel", "")
        chans[c] = max(chans.get(c, 0), r["views"])

    def over(n):
        return sum(1 for v in vs if v >= n)

    return {
        "n": len(vs), "channels": len(chans),
        "p50": vs[len(vs) // 2] if vs else 0,
        "p75": vs[3 * len(vs) // 4] if vs else 0,
        "p90": vs[9 * len(vs) // 10] if vs else 0,
        "max": vs[-1] if vs else 0,
        "need": need,
        "over": {rpm: over(n) for rpm, n in need.items()},
        "over_ch": {rpm: sum(1 for v in chans.values() if v >= n) for rpm, n in need.items()},
        "gate_views": 60_000,        # 扉(b) 4,000時間 ÷ 4分/回（`trend.rev_deadline` の前提）
        "over_gate": over(60_000),
        "over_gate_ch": sum(1 for v in chans.values() if v >= 60_000),
        "per_ch": (len(vs) / len(chans)) if chans else 0.0,
    }


def capacity_line(rows: list[dict] | None = None) -> str:
    """毎周 印字する1行（**API 0単位**）。**§7 へ数を写さないこと。**"""
    c = capacity(rows)
    if not c["n"]:
        return ("**門の先（月20万）の距離**: `data/niche_corpus.jsonl` に長尺が 1本 もありません "
                "＝ この口は何も言えません（`demand` → `peers` を撃つこと）。")
    need = c["need"]
    parts = " ／ ".join(
        f"RPM {int(r):,}円 なら **{need[r]:,}回/月** ＝ この族で越えている本 **{c['over'][r]}本**"
        f"（{c['over'][r] / c['n']:.0%}）・チャンネル {c['over_ch'][r]}"
        for r in RPM_BAND)
    return (
        f"**門の先（月20万）の距離**（`peers.capacity`・**API 0単位**・`niche_corpus` の長尺 "
        f"**{c['n']}本 / {c['channels']}チャンネル**・再生 中央 {c['p50']:,}・"
        f"上位1/4 {c['p75']:,}・上位1/10 {c['p90']:,}・最大 {c['max']:,}）: "
        f"要る再生は **20万円 ÷ RPM** —— {parts}。"
        f"**扉(b)（4,000時間 ＝ 60,000回・4分/回）を 1本 で越えている本 {c['over_gate']}本"
        f"（{c['over_gate'] / c['n']:.0%}）・チャンネル {c['over_gate_ch']}**。"
        f"＝ **月20万は、この族の「上位1/4 の1本」1本/月 と同じ大きさ**で、"
        f"**門は その 1本 の 1/3 以下**です（`trend.rev_deadline` が出すのは門までで、ここは出しません）。"
        f"**RPM はうちでは未測です**（収益化前 ＝ 帯で出しています・覆る条件 (1)）。"
        f"**この分布は検索の上位に寄っています ＝ 上振れの側**（覆る条件 (2)）。\n"
        # **この 1行 を外さないこと**（2026-09-16 17:0x）。上の「上位1/4 の1本」は
        #  corpus 全体の比で、**その比が測っているのはチャンネルの大きさ**でした
        #  （同じ罠の 3度目 ＝ JOURNAL 15:1x の覆る条件が引かれた）。
        #  **比を出す口そのものに控えを返させる** ＝ 生の比だけが印字される道を塞ぐ。
        + capacity_by_size_line(rows))


def niche_channels() -> dict[str, dict]:
    """corpus のチャンネルの登録者数（**API 0単位** ＝ 台帳 `data/niche_channels.jsonl` を読むだけ）。

    空の dict が返ったら台帳が無いということで、そのときは `capacity_by_size` は
    「**分けられない**」と印字します（**黙って生の比を返してはいけません**）。
    取り直しは `channels.list` を `corpus_channels()` に当てて **5単位**。
    """
    if not NICHE_CHANNELS.exists():
        return {}
    last = None
    for ln in NICHE_CHANNELS.read_text(encoding="utf-8").splitlines():
        if ln.strip():
            try:
                last = json.loads(ln)
            except ValueError:
                continue
    if not last:
        return {}
    return {c["id"]: c for c in last.get("channels", []) if c.get("id")}


def capacity_by_size(rows: list[dict] | None = None) -> dict:
    """`capacity` の**控え** —— 同じ分布を「そのチャンネルの登録者数」で割る（**API 0単位**）。

    **なぜ要るか（2026-09-16 17:0x・optimizer・Fable 5.1・ultracode が撃って分かったこと）**:
    `capacity` は corpus 全体で「**16% の本が 400,000回 を越えている**」と印字し、
    `docs/GOAL.md` (4-l) はそれを根拠に固定2 へ「**できる**」と答えていました。
    **その 16% は、このニッチの1本の力ではなく、その本を出したチャンネルの大きさでした**:

        登録者帯          長尺  ch  再生中央    最大      ≧60,000  ≧142,857  ≧200,000  ≧400,000
        0〜    1,000     104  83      555   34,677    **0本**   **0本**   **0本**   **0本**
        1,000〜10,000     68  54    3,249  548,720    7本 10%   5本  7%   4本  6%   3本  4%
        10,000〜100,000   56  43   61,358 1,355,819   28本 50%  22本 39%  18本 32%   9本 16%
        100,000〜        107  38  271,741 5,124,861   83本 78%  68本 64%  60本 56%  41本 38%

    **うちは いちばん下の帯です（登録 29人）。その帯の 104本 で、扉(b)（60,000回）を
    越えた本は 1本 もありません。最大が 34,677回 です。**
    ＝ 「月20万 ＝ この族の上位1/4 の1本 1本/月」は、**うちの大きさでは 0/104 の出来事**でした。

    **この repo が同じ罠を踏むのは 3度目です**（`title_shape` 54.4倍 → 同じch内 1.02倍 ／
    `families` の床 5,087倍 → 同じ口の中 2.35倍 ／ この `capacity` の 16%）。
    **JOURNAL 2026-09-16 15:1x の覆る条件（「3つ目が出たら、比を出す口そのものに控えを返させる」）
    が、この回に引かれました。** だから `capacity_line` は、この控えを**必ず隣に並べます**
    （生の比だけを印字する道は、もうありません）。

    **この口が言わないこと**: 「だから無理」ではありません。**帯を上がれば分布が変わる**、
    までです —— 10,000人 の帯では**中央値の本**が 61,358回 ＝ 扉(b) を 1本 で越えます。
    ＝ 期限までの 88日 に置く的は「200,000回 の本 1本」ではなく「**帯を上がること**」です。

    **覆る条件**:
     (1) 台帳（`niche_channels`）が **30日** より古くなったら引き直すこと（登録者は動く・5単位）。
     (2) 登録 1,000人 未満の帯で **60,000回 を越えた本が 1本 でも出たら**、
         「0/104」は数え直す側 ＝ この註の表を撃ち直すこと。
     (3) corpus は**検索結果の上位**なので、どの帯も**上振れの側**です
         （`capacity` の覆る条件 (2) と同じ。帯どうしの比には効きません ＝ 同じ偏りが全帯に乗る）。
     (4) **これは相関で、因果ではありません。** 「登録者が多いから伸びる」のか
         「伸びる本を作れるから登録者が多い」のかを、この口は分けません。
         分けるのは A/B（うちの本が帯の中央 555回 を越えるか）です。
    """
    L = corpus_longs() if rows is None else rows
    info = niche_channels()
    if not info:
        return {"n": len(L), "have": 0, "bands": []}
    need = {rpm: int(GOAL_YEN / rpm * 1000) for rpm in RPM_BAND}
    joined = [{**r, "subs": info[r["channel"]]["subs"]} for r in L if r.get("channel") in info]
    bands = []
    for lo, hi in SUB_BANDS:
        sub = [r for r in joined if lo <= r["subs"] < hi]
        if not sub:
            continue
        vs = sorted(r["views"] for r in sub)
        bands.append({
            "lo": lo, "hi": hi, "n": len(vs), "channels": len({r["channel"] for r in sub}),
            "p50": vs[len(vs) // 2], "max": vs[-1],
            "secs_median": int(st.median([r.get("secs") or 0 for r in sub])),
            "over_gate": sum(1 for v in vs if v >= 60_000),
            "over": {rpm: sum(1 for v in vs if v >= n) for rpm, n in need.items()},
        })
    return {"n": len(L), "have": len(joined), "need": need, "bands": bands}


def capacity_by_size_line(rows: list[dict] | None = None) -> str:
    """毎周 印字する1行。**`capacity_line` は必ずこれを隣に並べます**（覆る条件 (4) ＝ 3度目の罠）。"""
    c = capacity_by_size(rows)
    if not c.get("bands"):
        return ("**`capacity` の控え（登録者の帯で割る）は引けません** —— "
                "`data/niche_channels.jsonl` が在りません（`channels.list` **5単位** で取り直すこと）。"
                "**それまで上の 16%／24%／28% を「このニッチの1本の力」と読まないこと** ＝ "
                "同じ罠を 2度 踏んでいます（`title_shape` 54.4→1.02倍・`families` 5,087→2.35倍）。")
    out = ["**`capacity` の控え —— 同じ分布を登録者の帯で割る**（`peers.capacity_by_size`・**API 0単位**・"
           f"台帳 `niche_channels` {c['have']}本 ぶん）。**うちは いちばん下の帯（登録 29人）**:"]
    for b in c["bands"]:
        hi = "以上" if b["hi"] > 10 ** 8 else f"〜{b['hi']:,}"
        over = " ".join(f"≧{n:,} **{b['over'][r]}本({b['over'][r] / b['n']:.0%})**"
                        for r, n in c["need"].items())
        out.append(f"  登録 {b['lo']:>7,}{hi:<9} 長尺{b['n']:>4}本/ch{b['channels']:>3} "
                   f"尺中央{b['secs_median']:>5}秒 再生中央 {b['p50']:>8,} 最大 {b['max']:>9,}  "
                   f"扉(b)≧60,000 {b['over_gate']:>3}本({b['over_gate'] / b['n']:.0%})  {over}")
    low = c["bands"][0]
    out.append(
        f"  ＝ **うちの帯（登録1,000人未満）の {low['n']}本 で、扉(b) を越えた本は {low['over_gate']}本・"
        f"最大は {low['max']:,}回**。「月20万 ＝ 上位1/4 の1本」は、**うちの大きさでは 0/{low['n']} の出来事**です。"
        f"**期限までの的は「200,000回 の本 1本」ではなく「帯を上がること」** —— "
        f"10,000人 の帯では**中央値の本**が扉(b) を 1本 で越えます。"
        f"**相関であって因果ではありません**（覆る条件 (4)）。")
    return "\n".join(out)


#: 転換率を数えるときの床（小さすぎる口は比が暴れる）。
CONV_MIN_VIEWS = 1_000
CONV_MIN_VIDEOS = 5


def conversion(mine: dict | None = None) -> dict:
    """**登録 ÷ 総再生**（チャンネル合計・**標本ではない**）を corpus と並べる（**API 0単位**）。

    **なぜ要るか（2026-09-16 17:1x・optimizer・Fable 5.1・ultracode が撃って分かったこと）**:
    09/13 からの 14周 は、ぜんぶ **1本あたり再生**の側を触っていました
    （尺・題の形・絵・族・検索の語・分かりやすさの輪）。**そこはうちの弱点ではありませんでした。**

        corpus 215口（総再生1,000回以上・本5本以上）   **うち**
        登録/1,000再生  下1/4 2.55・中央 **5.29**・上1/4 8.40    **0.32** ← **下から 2/215**
        1本あたり再生   下1/4  780・中央 3,857・上1/4 38,280      **323** ← 下から 28/215（下位13%）

    **＝ 1本あたり再生は「悪いが分布の中」、転換率は「215口 中 213口 が持っていない欠陥」です。**
    中央値で転換していれば、**いまの 89,850回 は 475人** になっていました（実物 29人）。

    **形の言い訳は、同じ corpus の中で消えます** —— `あき姉` は **100本 中 72本 がショート**で
    93,200人 / 8,757,276回 ＝ **10.64/1,000**（**うちの 33倍**）。
    ＝ 「うちはショートだから低い」では 33倍 は説明できません。

    **期限の側が、この数で書き換わります**（`docs/GOAL.md` (4-o)）:
    門（あと 971人）までに要る再生は、**転換率をいくつに置くかで割り算が変わります** ——
    いまの 0.32 なら 303万回、corpus の中央 5.29 なら **18.4万回**（58日 で 3,165回/日 ＝ いまの **3.7倍**）。
    **「138倍」は、壊れた転換率を固定したまま再生だけを伸ばした数でした。**

    **覆る条件**:
     (1) **うちの分子と分母は形が混ざっています**（総再生の 97% がショート面）。
         **半分は閉じています**（`data/shorts_subs.jsonl` 09/05・API 0単位）——
         ショートは 88,545回・+22 ＝ **0.248/1,000（CI 0.16〜0.38）**で、**上端でも corpus の
         下1/4（2.55）の 1/6.7** ＝ 形では埋まりません。長尺は 500回・+1 ＝ CI 0.05〜11.14 で**読めない**。
         **長尺が 3本 たまったら引き直すこと**（そこで 2.55 を越えたら、欠陥はチャンネルではなく
         ショートという形の側 ＝ この節は「長尺へ寄せる」の根拠に変わる）。
     (2) corpus の分母は**全期間の総再生**、分子は**いまの登録者**です（口ごとの齢が混ざる）。
         比の順位には効きますが、**倍率を予測にそのまま代入しないこと**（`lines` の覆る条件 (4) と同じ）。
     (3) corpus には会社の口が混ざります（下位 8口 のうち 4口 が矯正歯科・不動産・人材）。
         **うちがその並びに居ること自体がこの節の中身**なので、外さずに数えています。
     (4) うちの転換率が **corpus の下1/4（2.55）を越えたら**、この節は役目を終えます ＝
         そのときに縛るのは 1本あたり再生の側へ戻る（`capacity_by_size` の帯）。
    """
    info = niche_channels()
    rows = []
    for c in info.values():
        v, n = c.get("views") or 0, c.get("videos") or 0
        if v < CONV_MIN_VIEWS or n < CONV_MIN_VIDEOS:
            continue
        rows.append({"title": c.get("title", ""), "subs": c.get("subs") or 0, "views": v,
                     "videos": n, "sub_per_1k": 1000 * (c.get("subs") or 0) / v,
                     "views_per_video": v / n})
    if not rows:
        return {"n": 0}
    sp = sorted(r["sub_per_1k"] for r in rows)
    vp = sorted(r["views_per_video"] for r in rows)
    out = {"n": len(rows),
           "sub_per_1k": {"q1": sp[len(sp) // 4], "p50": st.median(sp), "q3": sp[3 * len(sp) // 4]},
           "views_per_video": {"q1": vp[len(vp) // 4], "p50": st.median(vp), "q3": vp[3 * len(vp) // 4]}}
    if mine and mine.get("views"):
        m_sp = 1000 * mine["subs"] / mine["views"]
        m_vp = mine["views"] / max(mine.get("videos") or 1, 1)
        out["mine"] = {
            "sub_per_1k": m_sp, "views_per_video": m_vp,
            "rank_sub": sum(1 for x in sp if x < m_sp) + 1, "rank_views": sum(1 for x in vp if x < m_vp) + 1,
            "x_to_p50": (out["sub_per_1k"]["p50"] / m_sp) if m_sp else 0.0,
        }
    return out


def conversion_line(mine: dict | None = None) -> str:
    """毎周 印字する1行（**API 0単位**）。数はここが持つ ＝ **§7／GOAL へ写さないこと**。"""
    c = conversion(mine)
    if not c.get("n"):
        return ("**転換率（登録÷総再生）の控えは引けません** —— `data/niche_channels.jsonl` が在りません"
                "（`channels.list` **5単位**）。")
    s, v = c["sub_per_1k"], c["views_per_video"]
    head = (f"**転換率（登録÷総再生・`peers.conversion`・**API 0単位**・corpus {c['n']}口）**: "
            f"登録/1,000再生 下1/4 {s['q1']:.2f}・**中央 {s['p50']:.2f}**・上1/4 {s['q3']:.2f} ／ "
            f"1本あたり再生 下1/4 {v['q1']:,.0f}・中央 {v['p50']:,.0f}・上1/4 {v['q3']:,.0f}。")
    m = c.get("mine")
    if not m:
        return head
    return head + (
        f"\n  **うち**: 登録/1,000再生 **{m['sub_per_1k']:.2f}**（下から **{m['rank_sub']}/{c['n']}**）・"
        f"1本あたり **{m['views_per_video']:,.0f}回**（下から {m['rank_views']}/{c['n']}）。"
        f"\n  ＝ **1本あたり再生は「分布の中の下のほう」、転換率は「{c['n'] - m['rank_sub']}口 が持っていない欠陥」** "
        f"（中央まで **{m['x_to_p50']:.1f}倍**）。**ショートだから、では説明が付きません** —— "
        f"`あき姉` は 100本 中 72本 がショートで **10.64/1,000**。"
        f"**門（登録 1,000人）までに要る再生は、この率で割り算が変わります**（`docs/GOAL.md` (4-o)）。")


# ---------------------------------------------------------------------------
# **3因子の分解**（`throughput` / `throughput_line`・2026-09-18 08:xx・optimizer・Opus 5・ultracode）
# ---------------------------------------------------------------------------

#: **登録/日 ＝ 本/日 × 1本あたり再生 × 登録/再生。** 恒等式です（約分すると 登録/日）。
#: 3つ とも corpus で測れ、3つ とも うちで測れるので、**どの軸に居るか**が順位で出ます。
#:
#: **なぜ要るか（この回に撃って出た・`conversion`（09/16 17:1x）が見ていなかった側）**:
#: `conversion` は **登録/再生 が下から 2/215** と **1本あたり再生 が下から 28/215** を並べ、
#: 「前者が欠陥・後者は分布の中」と読みました。**3つ目の軸を数えていません** ——
#: **本/日 です。** 数えたら、うちは **p97.7**（実測 1.82本/日・台帳の `channel` の差）、
#: **生涯平均（283本 ÷ 齢 76日 ＝ 3.72）なら p99.5** でした。
#: **うちより多く出している口は corpus に 1つ だけで、それは TBS NEWS DIG（全国放送局・14.4本/日）です。**
#: 2位・3位 は 2.44／2.42本/日 で、**そこから下は 1本/日 を割ります。**
#:
#:     順位相関（Spearman・登録/日 と）     corpus 215口      齢<400日 の 47口
#:     1本あたり再生                      **+0.886**        **+0.863**
#:     登録/再生                           +0.431            +0.562
#:     **本/日**                           +0.369          **-0.073**
#:     本/日 と 1本あたり再生                +0.015
#:
#: **＝ 唯一 p97 より上に在る軸が、いちばん効かない軸です。**そして 本/日 と 1本あたり再生 は
#: **無相関（+0.015）** ＝ **本数を落としても 1本あたりは下がりません**（上がりもしません）。
#:
#: **齢の交絡は測って外しました**: `rho(齢, 1本あたり再生) = +0.053` ＝ 1本あたり再生は
#: 古さの産物ではありません（`rho(齢, 本/日) = -0.353`）。
#: 齢を 30〜400日 に揃えた 47口 でも 1本あたり再生 は +0.863 のまま、**本/日 は符号が反転**します。
#:
#: **門（登録/日 20人 以上）を抜けている 66口 の形**（`THR_TARGET_SPD`）:
#:
#:     本/日 中央 **0.223**（＝ 4.5日 に 1本）・1本あたり **63,066回**・登録/再生 **0.77%**
#:     うちとの比               **×0.12**            **×196**          **×22**
#:
#: **ただし「本数を落とせば伸びる」ではありません。** -0.014 は「落としても 1本あたりは動かない」
#: までしか言わず、いま落とせば 登録/日 は**そのぶん下がります**（恒等式なので）。
#: この口が言えるのは **「本/日 に残っている伸びしろは 0 —— 積む先を間違えている」**の 1つ だけです。
#:
#: **できる側の存在証明**（固定2 に答える数・同じ corpus の中）:
#: `宅建合格の急所`（齢 173日）は **1本あたり 694回**（うち 322回 と同じ帯）で、
#: **本/日 1.63**（うちの実測 1.82 と同じ帯）、**登録/再生 1.32%** ＝ **登録 14.9人/日**。
#: ＝ **1本あたり再生 を 1回も増やさなくても、登録/再生 が niche 並みなら 登録/日 は 2桁 に乗ります。**
#: 齢 200日 未満の 24口 のうち、**うちの 登録/再生 を下回るのは 1口 だけ**です。
#: **これが固定2 の「できる」側の形で、いまの手（本数・刻・枠）はこの軸を 1つ も動かしていません。**
#:
#: **覆る条件**:
#:  (1) corpus の 本/日 は**生涯の本数 ÷ 生涯の齢**、うちの 本/日 は**台帳 `channel` の
#:      `videos` の差**（直近の実測）です。**形が違います** —— 実測 1.82 で p97.7、
#:      生涯平均 3.72 で p99.5 と、**どちらで数えても p97 を割りません**が、
#:      **比を予測に代入しないこと**（`conversion` (2) と同じ）。
#:  (2) `rho(本/日, 登録/日)` が **2窓 続けて +0.5 を越えたら**、本数は効く側 ＝ この節は役目を終えます。
#:  (3) corpus は検索の語で集めた口です ＝ **配られた口しか入っていません**（生存者）。
#:      「本数が少ないから伸びた」ではなく「伸びた口は本数が少なかった」までしか言えません。
#:  (4) うちの 登録/再生 が corpus の下1/4 を越えたら、縛るのは 1本あたり再生 へ移ります
#:      （`conversion` (4) と同じ刻）。
#:  (5) オーナーが本数に言葉を出したら、その言葉が正本。

#: 3因子の母数に入れる齢の床（若すぎる口は 本/日 が跳ねる）。
THR_MIN_AGE = 30
#: 「門を抜けている」と数える 登録/日（`docs/GOAL.md` の門 1,000人 を 50日 で割った帯）。
THR_TARGET_SPD = 20.0
#: うちの 本/日 を台帳の `channel` 行から引くときの、最短の窓（これより短い差は数えない）。
THR_MINE_MIN_DAYS = 2.0


def _rho(a: list[float], b: list[float]) -> float:
    """Spearman の順位相関（**同値は出た順に順位を付ける近似** ＝ 連続量だけに使うこと）。"""
    ra = {v: i for i, v in enumerate(sorted(a))}
    rb = {v: i for i, v in enumerate(sorted(b))}
    x = [ra[v] for v in a]
    y = [rb[v] for v in b]
    mx, my = st.mean(x), st.mean(y)
    num = sum((i - mx) * (j - my) for i, j in zip(x, y))
    den = (sum((i - mx) ** 2 for i in x) * sum((j - my) ** 2 for j in y)) ** 0.5
    return (num / den) if den else 0.0


def _thr_rows(today=None) -> list[dict]:
    """corpus の口を 3因子に開く（**API 0単位** ＝ `niche_channels()` を読むだけ）。"""
    out = []
    for c in niche_channels().values():
        v, n = c.get("views") or 0, c.get("videos") or 0
        created = c.get("created") or ""
        if v < CONV_MIN_VIEWS or n < CONV_MIN_VIDEOS or not created:
            continue
        age = _age_days(created, today)
        if age < THR_MIN_AGE:
            continue
        out.append({"title": c.get("title", ""), "age": age, "subs": c.get("subs") or 0,
                    "vpd": n / age, "vpv": v / n, "spv": (c.get("subs") or 0) / v,
                    "spd": (c.get("subs") or 0) / age})
    return out


def mine_videos_per_day(channel_rows: list[dict] | None) -> float | None:
    """**うちの 本/日** を台帳の `channel` 行の `videos` の差から引く（**API 0単位**）。

    `cli.record_channel` が毎周 残す行だけを読みます。両端の差が
    `THR_MINE_MIN_DAYS` より短ければ **None**（黙って 0 や跳ねた値を返さない）。
    """
    rows = [r for r in (channel_rows or []) if r.get("videos") and r.get("at")]
    if len(rows) < 2:
        return None
    first, last = rows[0], rows[-1]
    try:
        t0 = dt.datetime.fromisoformat(str(first["at"]))
        t1 = dt.datetime.fromisoformat(str(last["at"]))
    except ValueError:
        return None
    days = (t1 - t0).total_seconds() / 86400.0
    if days < THR_MINE_MIN_DAYS:
        return None
    dn = int(last["videos"]) - int(first["videos"])
    return (dn / days) if dn >= 0 else None


def throughput(mine: dict | None = None, channel_rows: list[dict] | None = None,
               today=None) -> dict:
    """**登録/日 ＝ 本/日 × 1本あたり再生 × 登録/再生** を corpus と並べる（**API 0単位**）。

    決めと覆る条件は**この節の頭の註**（`THR_MIN_AGE` の上）。
    """
    rows = _thr_rows(today)
    if len(rows) < 8:
        return {"n": len(rows)}
    young = [r for r in rows if r["age"] <= YOUNG_DAYS]
    spd = [r["spd"] for r in rows]
    out = {
        "n": len(rows), "n_young": len(young),
        "p50": {k: st.median([r[k] for r in rows]) for k in ("vpd", "vpv", "spv")},
        "rho": {k: _rho([r[k] for r in rows], spd) for k in ("vpd", "vpv", "spv")},
        "rho_vpd_vpv": _rho([r["vpd"] for r in rows], [r["vpv"] for r in rows]),
        "rho_age_vpv": _rho([r["age"] for r in rows], [r["vpv"] for r in rows]),
    }
    if len(young) >= 8:
        ys = [r["spd"] for r in young]
        out["rho_young"] = {k: _rho([r[k] for r in young], ys) for k in ("vpd", "vpv", "spv")}
    fast = [r for r in rows if r["spd"] >= THR_TARGET_SPD]
    if fast:
        out["target"] = {"n": len(fast),
                         **{k: st.median([r[k] for r in fast]) for k in ("vpd", "vpv", "spv", "spd")}}
    if mine and mine.get("views") and mine.get("videos"):
        v, n = mine["views"], mine["videos"]
        m = {"vpv": v / n, "spv": mine.get("subs", 0) / v,
             "vpd": mine_videos_per_day(channel_rows)}
        m["pct"] = {}
        for k in ("vpd", "vpv", "spv"):
            if m.get(k) is None:
                continue
            xs = sorted(r[k] for r in rows)
            m["pct"][k] = 100.0 * sum(1 for x in xs if x < m[k]) / len(xs)
        if m["vpd"]:
            m["spd"] = m["vpd"] * m["vpv"] * m["spv"]
        out["mine"] = m
    return out


def throughput_line(mine: dict | None = None, channel_rows: list[dict] | None = None,
                    today=None) -> str:
    """毎周 印字する1行（**API 0単位**）。**数はここが持つ ＝ §7／METHOD／GOAL へ写さないこと。**"""
    t = throughput(mine, channel_rows, today)
    if not t.get("n"):
        return ("**3因子の分解は引けません** —— `data/niche_channels.jsonl` に `created` つきの口が"
                "足りません（`channels.list` **5単位**）。")
    p, r = t["p50"], t["rho"]
    ry = t.get("rho_young") or {}
    head = (f"**3因子の分解（`peers.throughput`・**API 0単位**・corpus {t['n']}口）**: "
            f"**登録/日 ＝ 本/日 × 1本あたり再生 × 登録/再生**（恒等式）。"
            f"\n  corpus 中央: 本/日 {p['vpd']:.3f}・1本あたり {p['vpv']:,.0f}回・"
            f"登録/再生 {100 * p['spv']:.3f}%"
            f"\n  順位相関（登録/日 と）: **1本あたり再生 {r['vpv']:+.3f}** ／ "
            f"登録/再生 {r['spv']:+.3f} ／ **本/日 {r['vpd']:+.3f}**"
            + (f"（齢<{YOUNG_DAYS}日 の {t['n_young']}口 だけなら **{ry['vpd']:+.3f}**）" if ry else "")
            + f"。本/日 と 1本あたり再生 は {t['rho_vpd_vpv']:+.3f}（無相関）")
    tg = t.get("target")
    if tg:
        head += (f"\n  門（登録/日 {THR_TARGET_SPD:.0f}人 以上）を抜けている {tg['n']}口 の中央: "
                 f"本/日 **{tg['vpd']:.3f}**（{1 / tg['vpd']:.1f}日 に 1本）・"
                 f"1本あたり {tg['vpv']:,.0f}回・登録/再生 {100 * tg['spv']:.2f}%")
    m = t.get("mine")
    if not m:
        return head
    pct = m.get("pct", {})
    body = "\n  **うち**: "
    if m.get("vpd") is not None:
        body += f"本/日 **{m['vpd']:.2f}**（**p{pct.get('vpd', 0):.1f}**）・"
    else:
        body += f"本/日 **引けません**（台帳の `channel` の窓が {THR_MINE_MIN_DAYS:.0f}日 未満）・"
    body += (f"1本あたり {m['vpv']:,.0f}回（p{pct.get('vpv', 0):.1f}）・"
             f"登録/再生 {100 * m['spv']:.4f}%（p{pct.get('spv', 0):.1f}）")
    if pct.get("vpd", 0) >= 90 > min(pct.get("vpv", 100), pct.get("spv", 100)):
        body += ("\n  ＝ **唯一 p90 より上に在る軸が、順位相関のいちばん低い軸です。**"
                 "**本/日 に残っている伸びしろは 0** —— 積む先の話であって、"
                 "「本数を落とせば伸びる」ではありません（`throughput` の註 (1)〜(5)）。")
    return head + body

# ---------------------------------------------------------------------------
# **人格の印**（`persona` / `persona_line`・2026-09-16 19:xx・optimizer・Fable 5.1・ultracode）
# ---------------------------------------------------------------------------

#: **肩書き（人間の専門家の経歴）の語。** `config/channel.yaml` 2026-08-30 が落とした側で、
#: **うちには永久に閉じている腕**です —— 合成音声が税・保険・年金という「視聴者が自分の金で動く題」を
#: 実在しない人間の経歴を根拠に話す形は、YouTube が収益化不可として名指ししており、
#: `src/verify._check_no_human_expert_claim()` が台本の側でも塞いでいます。
#: **だから、この語を持つ口は corpus から外してから数えます**（外さないと、
#: うちが取れない腕の効きを、取れる腕の効きとして読むことになる）。
CRED_RE = re.compile(
    r"(社労士|税理士|銀行員|FP|看護師|ナース|弁護士|会計士|行政書士|証券|学長|アドバイザー"
    r"|プランナー|相談員|ハロワ|ハローワーク|職員|投資家|薬剤師|教授|講師|眼科医|医師|大学)")

#: **名前 ＋ の ＋ 題材**（`きな子のシニアお金ゼミ`／`としこの年金相談所`／`タヌキの年金相談室`）。
#: **肩書きではありません** —— 名乗っているのは名前だけで、人間の経歴を 1つ も主張していません。
#: ＝ **うちに開いている側**（`タヌキ`・`フクロウ` は人ですらない）。
PERSONA_RE = re.compile(
    r"^[^\s]{0,6}?[ぁ-んァ-ヶ][ぁ-んァ-ヶー]{1,6}(子|さん|先生|姉|兄|ちゃん|くん|ママ|パパ)?の[^\s]")

#: 古さの控え（`persona` はこの齢より若い口だけでも数え、両方を並べます）。
PERSONA_AGE_CAP = 1000


def _age_days(created: str, today=None) -> int:
    try:
        y, m, d = (int(x) for x in created[:10].split("-"))
    except Exception:
        return 1
    return max(((today or now_jst().date()) - dt.date(y, m, d)).days, 1)


def persona(today=None) -> dict:
    """**題に「名前」が在るか**と、転換率・登録/日・1本あたり再生 を並べる（**API 0単位**）。

    **なぜ要るか（2026-09-16 19:xx に撃って出た）**: `conversion`（17:1x）は
    **うちの転換率が 215口 中 下から 2番目**だと出しましたが、**では何をすれば上がるのかは
    言っていません**でした（「見た人に登録する理由を渡していない」で止まっている）。
    この口は、その「理由」を corpus の中で 1つ 名指しします。

    **まず、取れない腕を外します。** corpus のいちばん速い層は
    `元ハローワーク職員ケン`／`元社労士事務所勤務ゆき`／`あき姉 元銀行員FP` のように
    **名前 ＋ 人間の肩書き**を題に持ち、**転換 13.5・登録 89.8人/日・1本 74,690回**（齢<400日・5口）です。
    **これはうちには閉じた腕です**（`CRED_RE` の註 ＝ `config/channel.yaml` 08/30）。
    **だから肩書きを持つ口を全部 外した 161口 で数えます**（`CONV_MIN_*` の床の後）。

        肩書きを持たない 161口        ch    転換中央   登録/日中央   1本中央   本/日中央
        名前 ＋ の ＋ 題材            24     5.75      11.9     13,123     0.13
        そうでない                  137     4.14       1.5      2,911     0.17
        齢<1000日 だけ（古さの控え）
        名前 ＋ の ＋ 題材            16     5.94      12.7     27,291     0.13
        そうでない                   57     4.93       1.9      2,585     0.29

    **＝ 齢を揃えて 転換 1.2倍・登録/日 6.8倍・1本あたり 10.6倍。**
    **そして「名前」の側は、本を 少なく 出しています**（0.13 対 0.29本/日）＝
    **「名前」は「たくさん出した」の言い換えではありません**（その控えがこの列です）。

    **いちばん大事なのは、この口が撃った側の仮説を 半分 落としたことです。**
    この口は「うちの転換率が下から2番目なのは、名乗る人が居ないからだ」を確かめに行って、
    **転換では 1.2倍 しか出ませんでした**（齢を揃えた後）。**大きいのは 1本あたり再生 10.6倍 の側**です。
    ＝ **「名前」は 転換の腕ではなく、届く量の腕**として corpus に写っています。
    **うちの転換率 0.32 は、肩書きを外した母集団の中央 4.14 の 1/13 で、
    その差は「名前が無いから」では説明が付きません**（形でも・出す数でも付かない ——
    `conversion` の覆る条件 (1) と `persona` の本文）。**まだ名前の付いていない欠陥が 1つ 在ります。**

    **うちに開いている形であることを、corpus の中で確かめました** ——
    `タヌキの年金相談室`（転換 **18.03**・45本・0.08本/日）と
    `フクロウの年金・給付金解説室`（転換 6.03・45本・1本 171,712回）は
    **人ですらない名前**で、**人間の経歴を 1つ も主張していません**。
    `きな子のシニアお金ゼミ`（9.37）・`としこの年金相談所`（10.48）も同じで、
    **どれも うちと同じ「年金・シニアのお金」の族**です。
    **うちの題は `お金と仕事の教科書`** ＝ **教科書**で、名乗る人が居ません。

    **覆る条件**:
     (1) **これは相関で、因果ではありません。** 「名前を付けたから伸びた」のか
         「作りが丁寧な口は名前も付ける」のかを、この口は分けません。
         **分ける手は 1つ しかありません ＝ うちが名前を付けて、前後を測ること**
         （`conversion` が毎周 印字する ＝ 付けた日を刻んで、その前後で引くこと）。
     (2) **n が小さい**（齢<1000日 の控えで 16口）。`niche_channels` が増えたら引き直すこと。
     (3) `PERSONA_RE` は**題の字面**しか見ていません。`サラダのお金相談所` を名前として拾い、
         名前を**題に出さずに本の中で名乗る**口は拾えません ＝ **この数は「名前の効き」の下限**です。
     (4) **うちの転換率が corpus の下1/4（2.55）を越えたら、この節は役目を終えます**
         （`conversion` の覆る条件 (4) と同じ門・**門は 1か所**）。
     (5) 肩書きを外す線（`CRED_RE`）を動かしたら、上の表の数は全部 変わります。
         **動かすなら、動かした後の表を JOURNAL へ写してから**。
    """
    info = niche_channels()
    rows = []
    for c in info.values():
        v, n = c.get("views") or 0, c.get("videos") or 0
        if v < CONV_MIN_VIEWS or n < CONV_MIN_VIDEOS:
            continue
        t = c.get("title", "")
        if CRED_RE.search(t):          # **取れない腕は数えない**（上の註）
            continue
        age = _age_days(c.get("created", ""), today)
        rows.append({"title": t, "subs": c.get("subs") or 0, "views": v, "videos": n,
                     "age": age, "persona": bool(PERSONA_RE.match(t)),
                     "sub_per_1k": 1000 * (c.get("subs") or 0) / v,
                     "views_per_video": v / n,
                     "subs_per_day": (c.get("subs") or 0) / age,
                     "videos_per_day": n / age})
    if not rows:
        return {"n": 0}

    def cut(rs: list[dict]) -> dict:
        if not rs:
            return {"n": 0}
        return {"n": len(rs),
                "conv": st.median([r["sub_per_1k"] for r in rs]),
                "spd": st.median([r["subs_per_day"] for r in rs]),
                "vpv": st.median([r["views_per_video"] for r in rs]),
                "vpd": st.median([r["videos_per_day"] for r in rs]),
                "age": st.median([r["age"] for r in rs])}

    young = [r for r in rows if r["age"] < PERSONA_AGE_CAP]
    out = {"n": len(rows),
           "all": {"named": cut([r for r in rows if r["persona"]]),
                   "plain": cut([r for r in rows if not r["persona"]])},
           "young": {"named": cut([r for r in young if r["persona"]]),
                     "plain": cut([r for r in young if not r["persona"]])}}
    named = sorted([r for r in rows if r["persona"]], key=lambda r: -r["subs_per_day"])
    out["examples"] = named[:8]
    return out


def persona_line(mine_title: str = "") -> str:
    """毎周 印字する（**API 0単位**）。**控えを必ず隣に並べます** ——
    生の「N倍」だけが出る道を塞ぐため（2026-09-16 15:1x の覆る条件「3つ目が出たら共通の口へ」）。
    """
    p = persona()
    if not p.get("n"):
        return ("**人格の印（`peers.persona`）は引けません** —— `data/niche_channels.jsonl` が"
                "在りません（`channels.list` **5単位**）。")
    out = [f"**題に「名前」が在るか（`peers.persona`・**API 0単位**・肩書きを持つ口を外した {p['n']}口）**。"
           f"**肩書きの腕は うちには閉じています**（`config/channel.yaml` 08/30・"
           f"`_check_no_human_expert_claim`）＝ **外してから数えています**:"]
    for key, nm in (("all", "全部    "), ("young", f"齢<{PERSONA_AGE_CAP}日")):
        a, b = p[key]["named"], p[key]["plain"]
        if not a.get("n") or not b.get("n"):
            continue
        out.append(f"  {nm}  名前あり ch{a['n']:>3} 転換{a['conv']:>6.2f} 登録/日{a['spd']:>7.1f} "
                   f"1本{a['vpv']:>9,.0f} **本/日{a['vpd']:>5.2f}**")
        out.append(f"  {'':8}  名前なし ch{b['n']:>3} 転換{b['conv']:>6.2f} 登録/日{b['spd']:>7.1f} "
                   f"1本{b['vpv']:>9,.0f} **本/日{b['vpd']:>5.2f}**")
    y = p["young"]
    if y["named"].get("n") and y["plain"].get("n") and y["plain"]["conv"]:
        out.append(f"  ＝ 齢を揃えて 転換 **{y['named']['conv'] / y['plain']['conv']:.1f}倍**・"
                   f"登録/日 **{y['named']['spd'] / max(y['plain']['spd'], 1e-9):.1f}倍**・"
                   f"1本 **{y['named']['vpv'] / max(y['plain']['vpv'], 1e-9):.1f}倍**。"
                   f"**名前の側は本を 少なく 出しています**（{y['named']['vpd']:.2f} 対 {y['plain']['vpd']:.2f}本/日）"
                   f" ＝ **「たくさん出した」の言い換えではありません**（これが控え）。")
    ex = [e for e in p.get("examples", []) if e["age"] < PERSONA_AGE_CAP][:4]
    if ex:
        out.append("  うちに**開いている**形（人間の経歴を 1つ も主張していない口）: "
                   + "・".join(f"{e['title'][:16]}（転換{e['sub_per_1k']:.1f}・{e['videos']}本）" for e in ex))
    if mine_title:
        hit = bool(PERSONA_RE.match(mine_title))
        out.append(f"  **うちの題 `{mine_title}`**: 名前 **{'在り' if hit else '無し'}**"
                   + ("" if hit else " ＝ **名乗る人が居ません**。**判定は立ったサブとオーナー**"
                                     "（`docs/GOAL.md` (4-p)）。"))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# **題の身元 ＝ 名前 × 制度名**（`title_identity`・2026-09-17 02:xx・optimizer・Fable 5.1・ultracode）
# ---------------------------------------------------------------------------

#: **チャンネルの題が「何の口か」を名指ししているか。** `年金`・`退職金`・`給付金` のような
#: **制度の名**であって、`お金`・`マネー`・`家計` のような広い語ではありません
#: （その2つは下の `TOPIC_BROAD_RE` で分けて数えます ——
#:  **分けないと、うちの `お金と仕事の教科書` が「題材が在る」側に入ります**）。
TOPIC_NARROW_RE = re.compile(
    r"(年金|退職金|老後|シニア|定年|相続|介護|給付金|失業|社会保険|確定申告|控除|住宅ローン|NISA|iDeCo)")
TOPIC_BROAD_RE = re.compile(r"(お金|マネー|家計|節約|貯金|貯蓄|投資|資産|税金|節税|保険|副業|転職|稼)")

#: 升に人を置く床（これを下回る升は数を出さない ＝ 1口 の外れ値で升が動くのを塞ぐ）。
CELL_MIN_CH = 5


def title_identity(today=None) -> dict:
    """**名前（`PERSONA_RE`）× 制度名（`TOPIC_NARROW_RE`）の 2×2**（**API 0単位**）。

    **なぜ要るか（2026-09-17 02:xx に撃って出た）**: `persona`（09/16 19:xx）は
    **名前の 1軸 だけ**で割って「転換は齢を揃えると 1.2倍 しか動かない ＝
    名前は転換の腕ではない」と読み、**そこで棚に上げました**（`docs/GOAL.md` (4-p) 2）。
    **読んだ列が違いました。** 扉(b) の通貨は転換率ではなく **登録/日** で、
    その列では 名前 1軸 でも **7.4倍**、**制度名と掛け合わせると 49倍** 開きます。

        齢<1000日・肩書きを外した 161口 の中        ch   転換中央  登録/日中央    1本中央
        名前 ＋ 制度名                              5    9.37     **78.8**    58,041
        名前 ＋ 制度名なし                          11    5.48       11.9     22,462
        名前なし ＋ 制度名                          11    5.63        9.7     16,487
        **名前なし ＋ 制度名なし（＝ うちの居る升）**  46    3.97      **1.6**     1,410

    **門が要るのは 11.1人/日**（`trend.rev_deadline`）。
    **うちの升の中央は 1.6人/日 で、うちはその半分（0.80）です** ＝
    **この升に居るかぎり、期限内に門は開きません**（升の中央でも 7倍 足りない）。
    **隣の 2升 は どちらも 9.7／11.9人/日 ＝ 単独で門の要求に届きます。**

    **どちらの軸も、うちに開いています** —— `タヌキの年金相談室`（転換 18.03）・
    `フクロウの年金・給付金解説室` は**人ですらない名前**で、人間の経歴を 1つ も主張していません
    （`CRED_RE` で外している「肩書き」とは別物）。

    **覆る条件は `title_identity_line` の下と `docs/GOAL.md` (4-r)。**
    """
    rows = []
    for c in niche_channels().values():
        v, n = c.get("views") or 0, c.get("videos") or 0
        t = c.get("title", "")
        if v < CONV_MIN_VIEWS or n < CONV_MIN_VIDEOS or CRED_RE.search(t):
            continue
        age = _age_days(c.get("created", ""), today)
        rows.append({"title": t, "age": age, "videos": n,
                     "conv": 1000 * (c.get("subs") or 0) / v,
                     "spd": (c.get("subs") or 0) / age, "vpv": v / n,
                     "named": bool(PERSONA_RE.match(t)), "topic": bool(TOPIC_NARROW_RE.search(t))})
    if not rows:
        return {"n": 0}

    def cell(rs: list[dict]) -> dict:
        if len(rs) < CELL_MIN_CH:
            return {"n": len(rs)}
        return {"n": len(rs), "conv": st.median(r["conv"] for r in rs),
                "spd": st.median(r["spd"] for r in rs), "vpv": st.median(r["vpv"] for r in rs)}

    young = [r for r in rows if r["age"] < PERSONA_AGE_CAP]
    out = {"n": len(rows), "n_young": len(young), "cells": {}}
    for nm, want_named, want_topic in (("named_topic", True, True), ("named_plain", True, False),
                                       ("plain_topic", False, True), ("plain_plain", False, False)):
        out["cells"][nm] = cell([r for r in young
                                 if r["named"] is want_named and r["topic"] is want_topic])
    out["examples"] = sorted([r for r in young if r["topic"]], key=lambda r: -r["conv"])[:8]
    return out


def title_identity_line(mine_title: str = "", need_spd: float | None = None) -> str:
    """毎周 印字する（**API 0単位**）。**数はここが持つ ＝ `docs/METHOD.md` §7／GOAL へ写さないこと。**

    **覆る条件**:
     (1) **相関であって因果ではありません**（`persona` の (4-p-1) と同じ穴）。
         **分ける手は 1つ ＝ うちが動かして前後を測ること** ——
         動かした日は `docs/GOAL.md` (4-r) に刻んであります。
         **その日から 14日 の登録/日 を、動かす前の 14日 と並べること。**
     (2) **升が小さい**（いちばん効く升で {CELL_MIN_CH}口）。`niche_channels` が増えたら引き直すこと。
     (3) `TOPIC_NARROW_RE` / `PERSONA_RE` は**題の字面**しか見ません
         ＝ 上の倍率は**下限**です（題に出さず本の中で名乗る口を拾えない）。
     (4) **うちが `named_topic` の升へ移った後は、この行が読むのは「升の差」ではなく
         「うちの前後」です** —— 升の表は控えとして残しますが、判定は (1) の前後の数へ移ること。
     (5) **`CRED_RE` を動かしたら升は全部 変わります**（`persona` の (4-p-5) と同じ）。
    """
    p = title_identity()
    if not p.get("n"):
        return ("**題の身元（`peers.title_identity`）は引けません** —— "
                "`data/niche_channels.jsonl` が在りません（`channels.list` **5単位**）。")
    c = p["cells"]
    out = [f"**題の身元 ＝ 名前 × 制度名**（`peers.title_identity`・**API 0単位**・"
           f"肩書きを外した {p['n']}口 のうち 齢<{PERSONA_AGE_CAP}日 の {p['n_young']}口）。"
           f"**読む列は転換ではなく 登録/日**（扉(b) の通貨・`trend.rev_deadline`）:"]
    for key, nm in (("named_topic", "名前 ＋ 制度名      "), ("named_plain", "名前 ＋ 制度名なし   "),
                    ("plain_topic", "名前なし ＋ 制度名   "), ("plain_plain", "名前なし ＋ 制度名なし")):
        a = c.get(key, {})
        if a.get("conv") is None:
            out.append(f"  {nm} ch{a.get('n', 0):>3}  （{CELL_MIN_CH}口 未満 ＝ 数えない）")
            continue
        out.append(f"  {nm} ch{a['n']:>3}  転換{a['conv']:>6.2f}  **登録/日{a['spd']:>7.1f}**  "
                   f"1本{a['vpv']:>9,.0f}")
    if mine_title:
        named, topic = bool(PERSONA_RE.match(mine_title)), bool(TOPIC_NARROW_RE.search(mine_title))
        broad = bool(TOPIC_BROAD_RE.search(mine_title))
        key = ("named_topic" if named and topic else "named_plain" if named else
               "plain_topic" if topic else "plain_plain")
        mine_cell = c.get(key, {})
        line = (f"  **うちの題 `{mine_title}`** ＝ 名前 {'在り' if named else '**無し**'}・"
                f"制度名 {'在り' if topic else '**無し**'}"
                + ("（`お金`/`マネー` のような広い語は在りますが、制度名ではありません）" if broad and not topic else "")
                + f" ＝ **`{key}` の升**")
        if mine_cell.get("spd") is not None:
            line += f"（升の中央 登録/日 **{mine_cell['spd']:.1f}**）"
        out.append(line)
        # **門との関係は、どの升に居ても言うこと**（2026-09-19 03:5x に直した）。
        #  **この 1文 は長らく `key == "plain_plain"` の中だけに在りました** ＝
        #  **09/18 20:2x に題が `named_topic` へ移った瞬間、この行は門について黙りました。**
        #  下の docstring の 覆る条件 (4) は その場合を 09/17 から予告していたのに、
        #  **書いてあったのは註だけで、印字する側が持っていませんでした**
        #  （この repo でいちばん多い壊れ方 ＝ 言っている所と、している所が別）。
        #  **覆る条件**: 升の中央と「うちの実測」を同じ行に並べたくなったら、
        #  並べるのはこの行ではなく `trend.rename_effect_line`（あちらが前後を持つ）。
        if need_spd and mine_cell.get("spd") is not None:
            short = need_spd / max(mine_cell["spd"], 1e-9)
            if short > 1:
                best = c.get("named_topic", {})
                out.append(f"  **門が要るのは {need_spd:.1f}人/日** ＝ **この升の中央でも "
                           f"{short:.1f}倍 足りません。**"
                           + (f" 隣の升は {c['plain_topic']['spd']:.1f}／{c['named_plain']['spd']:.1f}人/日 ＝ "
                              f"**どちらも単独で門の要求に届きます**（両方 ＝ {best['spd']:.1f}）。"
                              if c.get("plain_topic", {}).get("spd") and c.get("named_plain", {}).get("spd")
                              and best.get("spd") else "")
                           + " **判定は立ったサブとオーナー**（`docs/GOAL.md` (4-r)）。")
            else:
                out.append(f"  **門が要るのは {need_spd:.1f}人/日** ＝ この升の中央（{mine_cell['spd']:.1f}）は "
                           f"**{1 / short:.1f}倍 上回ります**。 !! **これは「うちが足りている」ではありません** —— "
                           f"**升の中央は corpus の数で、うちの数ではありません。** "
                           f"**うちの実測は `trend.rename_effect_line` が持ちます**"
                           f"（題を変えた前後・門に届くまで判定を出さない側）＝ **ここへ写さないこと**。"
                           f" **この行が読むのは、もう「升の差」ではなく「うちの前後」です**"
                           f"（覆る条件 (4)・`docs/GOAL.md` (4-x)）。")
    ex = p.get("examples", [])[:4]
    if ex:
        out.append("  うちに**開いている**形（人間の経歴を 1つ も主張していない・制度名を持つ口）: "
                   + "・".join(f"{e['title'][:18]}（転換{e['conv']:.1f}・登録/日{e['spd']:.0f}）" for e in ex))
    return "\n".join(out)



def title_shape(rows: list[dict] | None = None) -> dict:
    """題の型（【】・！？・N選・改正・数）と再生の関係。**チャンネルの大きさで揃えた側も出します。**

    **2026-09-16 10:xx に撃って分かったこと**: 生の比は **8〜54倍** 出ますが、
    **同じチャンネルの中で比べると全部 消えます**（両側を持つチャンネルが 1〜4 しか無い）。
    ＝ **生の比が測っているのは題ではなく、その型を使うチャンネルの大きさ**です。
    **この口の数を「この題の型が効く」と読まないこと。**

    答えを出すには corpus の **1チャンネルあたりの本数**（いま 1.5本）を増やす番です ——
    `playlistItems` 1単位/50本 ＋ `videos` 1単位/50本 ＝ **1チャンネル 2単位**。
    218チャンネル で **約 450単位**（日枠 10,000 の 4.5%）。**覆る条件 (3)**。
    """
    L = corpus_longs() if rows is None else rows
    feats = {
        "【】": lambda t: "【" in t,
        "！？": lambda t: any(ch in t for ch in "！？!?"),
        "損・失う": lambda t: any(w in t for w in ("損", "失う", "もらえ", "消え")),
        "N選・Nつ": lambda t: bool(re.search(r"[0-9０-９]+(選|つ)", t)),
        "改正・202x": lambda t: bool(re.search(r"202[0-9]|改正|変更|新制度", t)),
        "解説": lambda t: "解説" in t,
        "題に数": lambda t: bool(re.search(r"[0-9０-９,]{2,}(円|歳|万)", t)),
    }
    byc: dict[str, list[dict]] = {}
    for r in L:
        byc.setdefault(r.get("channel", ""), []).append(r)
    out = {}
    for name, f in feats.items():
        a = [r["views"] for r in L if f(r.get("title", ""))]
        b = [r["views"] for r in L if not f(r.get("title", ""))]
        ma = st.median(a) if a else 0
        mb = st.median(b) if b else 0
        paired = []
        for g in byc.values():
            ga = [r["views"] for r in g if f(r.get("title", ""))]
            gb = [r["views"] for r in g if not f(r.get("title", ""))]
            if len(ga) >= 2 and len(gb) >= 2:
                paired.append((st.median(ga) + 1) / (st.median(gb) + 1))
        out[name] = {"n_yes": len(a), "med_yes": ma, "med_no": mb,
                     "raw": (ma + 1) / (mb + 1),
                     "paired_n": len(paired),
                     "paired": st.median(paired) if paired else None}
    return out


def title_shape_line(rows: list[dict] | None = None) -> str:
    """毎周 印字する1行（**API 0単位**）。**向きは言いません** —— 言えないことが答えです。"""
    d = title_shape(rows)
    if not d:
        return ""
    worst = max(d.values(), key=lambda v: v["raw"])
    pn = max(v["paired_n"] for v in d.values())
    body = " ／ ".join(f"{k} 生 {v['raw']:.1f}倍（{v['n_yes']}本）"
                      + (f"・同じch内 {v['paired']:.2f}倍" if v["paired"] else "・同じch内 測れない")
                      for k, v in d.items())
    return (
        f"**題の型と再生**（`peers.title_shape`・**API 0単位**）: {body}。"
        f"!! **生の比（最大 {worst['raw']:.1f}倍）を「この型が効く」と読まないこと** —— "
        f"**同じチャンネルの中で比べられる型は 0〜{pn}チャンネル分 しかなく、そこでは比が消えます**"
        f"（＝ 生の比が測っているのは題ではなく、その型を使うチャンネルの大きさ）。"
        f"**答えを出す番は corpus の深さ**（いま 1チャンネルあたり "
        f"{capacity(rows)['per_ch']:.1f}本 ＝ `playlistItems`＋`videos` で 1チャンネル 2単位・"
        f"218チャンネル 約450単位）。**判定は立ったサブとオーナー。**")


# ---- corpus を **深く** する（`title_shape` の穴を埋める唯一の手）------------------
#
# **2026-09-16 11:xx・optimizer・Fable 5.1・ultracode が足した。この回は撃っていません**（日枠が尽きていた）。
#
# **なぜ要るか**: `title_shape` が出す生の比（最大 54.4倍）は、**同じチャンネルの中で比べると消えます**。
# 消える理由は 1つ —— corpus が **1チャンネルあたり 1.5本** しかないからです（`demand` の種で
# `search.list` を撃つと、**広く浅く**集まる。1チャンネルから 1本 ずつ 218チャンネル）。
# **題の型が効くかどうかは、同じチャンネルの中でしか測れません**（チャンネルの大きさが交絡するため）。
#
# **値段**: `playlistItems.list` 1単位/50本 ＋ `videos.list` 1単位/50本 ＝ **1チャンネル 2単位**
# （`contentDetails` を引く `channels.list` は 50件 で 1単位）。
# **218チャンネル・1チャンネル 50本 で 約450単位**（日枠 10,000 の **4.5%**）。
# `search.list` なら 1回 100単位 なので、**同じ深さを search で買うと 100倍 かかります。**
#
# **この口は `niche_corpus.jsonl` に追記します**（`peers.jsonl` ではありません）——
# `corpus_longs` / `title_shape` / `capacity` が読むのは corpus の側なので。
# **同じ動画が何度 入っても構いません**（`corpus_longs` が id で畳みます）。
#
# **覆る条件**:
#  (1) 深く引いたあとの `title_shape` で、**同じch内の比が 1.5倍 を越えた型**が出たら、
#      その型は本物 ＝ `retitle` の根拠になります（`docs/GOAL.md` (4-m-1)）。
#  (2) **3ch 以上 で 0.7倍 を下回った型**が出たら、それは逆に効く型 ＝ 題から外すこと（(4-m-2)）。
#  (3) 1チャンネルあたりが 2本 を越えても同じch内の比が立たないなら、**交絡はチャンネルではなく
#      題材の側**（同じチャンネルでも題材で桁が変わる）＝ そのときは題材を揃えて比べ直すこと。
#  (4) `DEEP_MAX_UNITS` は**日枠を食い切らないための蓋**です。上げるのは、その周に
#      予約（1,650単位/本）を撃たないと決めた回だけ。

#: 1チャンネルから何本まで引くか（`playlistItems` 1ページ ＝ 50本 ＝ 1単位）。
DEEP_PER_CHANNEL = 50
#: この口が 1回 に使ってよい単位の蓋（覆る条件 (4)）。
DEEP_MAX_UNITS = 500


def deep_pull(svc, ids: list[str] | None = None, per_channel: int = DEEP_PER_CHANNEL,
              max_units: int = DEEP_MAX_UNITS, now: dt.datetime | None = None) -> dict:
    """corpus のチャンネルを 1つずつ開いて、その本を corpus へ追記する。

    **蓋に当たったら、その時点までを返します**（途中で止まっても、集まった分は使えます）。
    返すのは {units, channels, videos, rows} —— `rows` はそのまま corpus へ書く行。
    """
    ids = ids if ids is not None else corpus_channels()
    at = (now or now_jst()).isoformat(timespec="seconds")
    units = 0
    rows: list[dict] = []
    done = 0
    for cid in ids:
        if units + 2 > max_units:
            break
        try:
            r = svc.channels().list(part="contentDetails", id=cid).execute()
            units += 1
            items = r.get("items", [])
            if not items:
                continue
            up = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            vids, token = [], None
            while len(vids) < per_channel and units < max_units:
                pr = svc.playlistItems().list(part="contentDetails", playlistId=up,
                                              maxResults=50, pageToken=token).execute()
                units += 1
                vids += [i["contentDetails"]["videoId"] for i in pr.get("items", [])]
                token = pr.get("nextPageToken")
                if not token:
                    break
            vids = vids[:per_channel]
            for i in range(0, len(vids), 50):
                if units >= max_units:
                    break
                vr = svc.videos().list(part="snippet,statistics,contentDetails",
                                       id=",".join(vids[i:i + 50])).execute()
                units += 1
                for it in vr.get("items", []):
                    s = it.get("statistics", {})
                    secs = iso_secs(it.get("contentDetails", {}).get("duration", ""))
                    rows.append({
                        "at": at, "id": it["id"],
                        "views": int(s.get("viewCount", 0) or 0),
                        "secs": secs,
                        "form": "long" if secs > SHORT_SECS else "short",
                        "channel": cid,
                        "title": it["snippet"]["title"],
                        "published": it["snippet"].get("publishedAt", ""),
                        "q": "deep",
                    })
            done += 1
        except Exception:                                        # noqa: BLE001
            # **1チャンネルで転んでも止めない** —— 集まった分は次の周が使えます。
            continue
    return {"at": at, "units": units, "channels": done, "videos": len(rows), "rows": rows}


def deep_save(rows: list[dict]) -> int:
    """corpus へ追記する（同じ動画が重なっても `corpus_longs` が id で畳みます）。"""
    if not rows:
        return 0
    with CORPUS.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(rows)


# ---- 題材の**族**ごとの天井（ニッチは 1つ ではありません）------------------------
#
# **2026-09-16 11:xx・optimizer・Fable 5.1・ultracode が足した。**
#
# `capacity` は「このニッチの 1本」で数えますが、**corpus の `q`（引いた検索語）で割ると、
# 族ごとの中央値が 3,000倍 ちがいます**:
#
#     年金 手取り いくら      n=38  中央 **605,548**  最大 5,124,861
#     退職金 税金 いくら      n=36  中央 **325,807**  最大 2,023,357
#     加給年金 いくら        n=35  中央  **91,269**  最大 4,422,714
#     所得税 控除 節税       n=39  中央   68,276
#     遺族年金 いくら 計算     n=21  中央   59,469
#     …
#     医療費控除 いくら戻る    n=25  中央     **190**
#
# **＝ 「どのニッチか」ではなく「そのニッチの、どの族か」で天井が決まります。**
# `capacity` が言う「上位1/4 の1本」は、**族を選べば中央値の側**です
# （年金 手取り の族なら、中央の本が 605,548回 ＝ 月20万の 3倍）。
#
# **この口は判定しません** —— 族と数と、うちが何本 持っているかを並べるだけ（`lines` の覆る条件 (4) と同じ）。
#
# **覆る条件**:
#  (1) `q` は `demand` の種で引いた語なので、**族は種の側の都合**です。種を変えたら族も変わります
#      ＝ この表を「ニッチの地図」と読まないこと。
#  (2) うちの長尺が 3本 たまった族が出たら、**その族の中央値とうちの 48h を並べること**
#      （族の中央値が高いのに うちが伸びないなら、効いていないのは族ではなく作りの側）。
#  (3) 族ごとの n が 10本 を切ったら、その行の中央値は読まないこと（いま 14〜40本）。

#: 中央値を読んでよい最小の本数（覆る条件 (3)）。
FAMILY_MIN_N = 10
#: 族の語のうち、当てはめに使わない語（**どの本にも在る語**）。`mine_by_family` の註。
FAMILY_STOPWORDS = frozenset({"いくら", "計算", "とは", "上限", "節税", "いくら戻る", "最新", "条件"})

# ---------------------------------------------------------------------------
# **族の「床」（p25）** —— 2026-09-16 14:4x・optimizer・Fable 5.1・ultracode・**API 0単位**
#
# **なぜ 中央値ではなく p25 を足したか。**
# 上の `family_line` は族の**中央値**を並べ、上と下で 3,187倍 と印字していました。
# しかし中央値は「うまくいったらどこまで行くか」の側で、**こちらが選ぶときに要るのは
# 「外したときにどこまで落ちるか」**です（うちは 29人 のチャンネルなので、族の中の下側に落ちる前提で選ぶ）。
# 同じ corpus を p25 で割り直すと、**族の差は中央値よりさらに開きます**（撃って数えた・下）:
#
#     年金 手取り いくら        p25 **117,006**  中央 605,548  n=38 ch=24
#     退職金 税金 いくら        p25  **99,851**  中央 325,807  n=36 ch=22
#     加給年金 いくら          p25  **31,682**  中央  91,269  n=35 ch=26
#     所得税 控除 節税         p25   **9,500**  中央  68,276  n=39 ch=24
#     遺族年金 いくら 計算      p25   **2,939**  中央  59,469  n=21 ch=19
#     再就職手当 計算          p25     **549**  中央   4,586  n=14 ch=13
#     変動金利 5年ルール 未払利息 p25   **1,835**  中央   3,387  n=31 ch=25
#     標準報酬月額 計算        p25     **591**  中央   1,588  n=26 ch=20
#     ふるさと納税 上限 計算     p25     **222**  中央   1,332  n=31 ch=27
#     不動産取得税 計算        p25     **314**  中央   1,094  n=40 ch=37
#     医療費控除 いくら戻る      p25      **23**  中央     190  n=25 ch=21
#
# **生では 上と下で 5,087倍**（中央値の 3,187倍 より大きい）。
#
# !! **その 5,087倍 を「族の効き」と読まないこと。**（2026-09-16 15:0x に、**同じ回が自分で撃って外しました**）
# `title_shape` が「**生の比（最大 54.4倍）を『この型が効く』と読まないこと** —— 同じチャンネルの中で
# 比べると比が消える ＝ 生の比が測っているのは題ではなく、その型を使うチャンネルの大きさ」と
# 書いているのと **同じ罠**です。**族でも同じ控えを撃たなければなりません**（`family_within_channel`）:
#
#     2族 以上 に本を持つチャンネル       **29 / 218**
#     その中で 上の族 対 下の族（同じ口）   **比の中央 2.35倍**・**上が大きい 23/29**
#                                     （符号だけの検定で p ≒ 0.0007 ＝ **向きは本物**）
#
# **＝ 族は効きます。ただし 5,087倍 ではなく 2.35倍 です**（同じチャンネルの中で、
# その口が持ついちばん上の族と いちばん下の族 を比べた値 ＝ **取れる中でいちばん広い対比**）。
# **残りの 2,000倍 は、族ではなく「どのチャンネルがその語で上位に出るか」＝ 口の大きさです。**
#
# **この数が効く所**: 扉(b)（4,000時間）は、狙いの尺 900秒 × 維持率 45.5% ＝ 0.114時間/回 で割ると
# **35,164回**です。**うちの長尺はいま 100〜1,000回 なので、族を変えて得られる 2.35倍 では届きません**
# ＝ **族の選び方は「ただで 2.35倍」であって、扉(b) を開ける手ではありません。**
# 扉を開ける側は口の大きさ（尺・題の形・browse）で、そちらは `peers.py` 冒頭と `docs/GOAL.md` (4-j)。
#
# **うちが 2026-09-15 に出した `2026-09-15-iryohi-koujo-10man` は、
# 測った 11族 のうち いちばん下（p25 23回）の族です** ＝ **ただの 2.35倍 を捨てていた側**。
#
# **覆る条件**:
#  (1) corpus は**検索の上位**なので、どの族も「検索で当たった側」だけです ＝ p25 は
#      「その題材で作った本の下から1/4」ではなく「**その語で上位に出た本の下から1/4**」。
#      **上振れの側**（`lines` の覆る条件 (2) と同じ）。
#  (1-b) **生の比は読まないこと。読むのは `family_within_channel` の側**（上の 2.35倍）。
#      生の側を引くのは「その語でどれだけ大きい口が上位に居るか」を見るときだけ。
#  (2) うちの長尺が **その族で 2本** 公開されて、**48h が族の p25 の 1/100 にも届かなかったら**、
#      縛っているのは族ではなく口（配り）の側 ＝ この段は使えません（GOAL (4-i) の枝 B へ）。
#  (3) 族ごとの n が 10本 を切ったら、その族の p25 は読まないこと。
#  (4) **p25 の順が中央値の順と入れ替わる族が出たら**、その族は本数が足りないか、
#      2つ の別の族が同じ語に入っています（`q` を割り直すこと）。
#  (5) **2族 以上 に本を持つチャンネルが 29 を下回ったら**、`family_within_channel` の 2.35倍 は読めません
#      （`title_shape` が「同じch内は 0〜6チャンネル分 しかない」で詰まったのと同じ所）＝
#      corpus の**深さ**を増やす番（1チャンネル 2単位・`playlistItems`＋`videos`）。
#  (6) **「チャンネルの大きさで割る」正規化を足さないこと** —— この回に撃って **1.1倍** と出ましたが、
#      **189/218 のチャンネルは 1族 しか持たないので、自分の中央値で自分を割って 1.00 になるだけ**です
#      （分母が分子を含む ＝ 退化）。**控えとして使えるのは 2族 以上 の 29口 だけ。**
# ---------------------------------------------------------------------------

#: 族の「床」として読む分位（覆る条件 (1)）。
FAMILY_FLOOR_Q = 0.25


def _quantile(vals: list[int], p: float) -> float:
    """線形補間の分位。`statistics.quantiles` は n=1 で落ちるので自前（族は n≧10 だが、呼び先は選ばない）。"""
    v = sorted(vals)
    if not v:
        return 0.0
    k = (len(v) - 1) * p
    f = int(k)
    c = min(f + 1, len(v) - 1)
    return v[f] + (v[c] - v[f]) * (k - f)


def families(rows: list[dict] | None = None) -> list[dict]:
    """corpus を `q`（引いた語）で割って、族ごとの長尺の中央値・最大・本数を出す。"""
    L = corpus_longs() if rows is None else rows
    by: dict[str, dict[str, int]] = {}
    for r in L:
        q = r.get("q", "") or "（語なし）"
        by.setdefault(q, {})[r["id"]] = r["views"]
    out = []
    for q, m in by.items():
        v = sorted(m.values())
        if not v:
            continue
        # `floor` は p25（**外したときにどこまで落ちるか**・上の註）。`median` は残す（読み手が 2つ）。
        out.append({"q": q, "n": len(v), "median": st.median(v), "max": v[-1],
                    "floor": _quantile(v, FAMILY_FLOOR_Q), "p10": _quantile(v, 0.10)})
    return sorted(out, key=lambda d: -d["median"])


def family_match(hay: str, fams: list[str]) -> list[str]:
    """題＋tags の字（空白を抜いたもの）が入る族を全部 返す。

    族の語は空白区切りの並び。**「いくら」「計算」のような当たり前の語を外し、
    残りが全部 題か tags に在る本だけ**を、その族に入れます。
    **1語 でも当たれば入れる形にしないこと** —— 「年金」は 11本 のうち 10本 に在り、
    そうすると族の表が「どの族も全部 持っている」と嘘をつきます（2026-09-16 11:xx に踏んだ）。
    """
    out = []
    for q in fams:
        need = [w for w in q.split() if w and w not in FAMILY_STOPWORDS]
        if need and all(w in hay for w in need):
            out.append(q)
    return out


def family_of(title: str, tags: list[str] | None = None,
              rows: list[dict] | None = None) -> list[dict]:
    """1本 の題＋tags が入る族を、**床（p25）の高い順**に返す（**ファイルを読むだけ・API 0単位**）。

    返すのは `families()` の行そのもの（`q` / `n` / `median` / `floor` / `p10` / `max`）。
    **入る族が 1つも無いとき は空**で、それは「天井が低い」ではなく **「測っていない」** です
    （corpus は `demand` の種の都合 ＝ `FAMILY_FLOOR_Q` の註の覆る条件 (1)）。
    """
    fs = [f for f in families(rows) if f["n"] >= FAMILY_MIN_N]
    hay = (title + " " + " ".join(tags or [])).replace(" ", "")
    hit = set(family_match(hay, [f["q"] for f in fs]))
    return sorted([f for f in fs if f["q"] in hit], key=lambda f: -f["floor"])


def mine_by_family(scripts_dir: Path | None = None) -> dict[str, list[str]]:
    """うちの長尺の台本が、どの族の語を題か tags に持っているか（**ファイルを読むだけ**）。"""
    d = scripts_dir or (DATA / "scripts")
    fams = [f["q"] for f in families()]
    out: dict[str, list[str]] = {q: [] for q in fams}
    if not d.exists():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            s = json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            continue
        if s.get("form") != "long":
            continue
        hay = (s.get("title", "") + " " + " ".join(s.get("tags", []))).replace(" ", "")
        for q in family_match(hay, fams):
            out[q].append(s.get("id", p.stem))
    return out


def family_line(rows: list[dict] | None = None) -> str:
    """毎周 印字する1行（**API 0単位**）。**判定はしません。**"""
    fs = [f for f in families(rows) if f["n"] >= FAMILY_MIN_N]
    if not fs:
        return ""
    mine = mine_by_family()
    top = fs[0]
    bot = fs[-1]
    body = " ／ ".join(f"{f['q']} 中央 **{f['median']:,.0f}**（{f['n']}本・うち {len(mine.get(f['q'], []))}本）"
                      for f in fs[:6])
    return (
        f"**題材の族ごとの天井**（`peers.families`・**API 0単位**・`niche_corpus` の `q` で割った・"
        f"門 n≧{FAMILY_MIN_N}本）: {body}"
        f" … いちばん下は **{bot['q']} 中央 {bot['median']:,.0f}**（{bot['n']}本）。"
        f"**＝ 上と下で {top['median'] / max(bot['median'], 1):,.0f}倍** —— "
        f"**天井を決めるのはニッチではなく族です**（`capacity` が言う「上位1/4 の1本」は、"
        f"いちばん上の族なら**中央値の側**）。**族は `demand` の種の都合**なので"
        f"「ニッチの地図」と読まないこと（覆る条件 (1)）。**判定は立ったサブとオーナー。**")


#: 扉(b)（収益化の基準1）の視聴時間。**与件**（YouTube の公表条件）。
DOOR_B_HOURS = 4_000
#: 扉(b) を回数に直すときの 1本 の狙いの尺（秒）。正本は `script.LONG_TARGET_SECONDS`（§2）。
#: **ここへ写しているのは「族の床と同じ行で読む」ためだけ**で、決めるのは §2 の側です。
DOOR_B_SECS = 900
#: 同じく、実測の平均視聴率（`trend.analytics_traffic` の新しい作り 7本 の中央 45.5%）。
DOOR_B_HOLD = 0.455


def door_b_views(secs: int = DOOR_B_SECS, hold: float = DOOR_B_HOLD) -> int:
    """扉(b)（4,000時間）を**回数**に直す。**この数は尺と維持率で動きます**（点で読まない）。"""
    per = max(secs * hold / 3600.0, 1e-9)
    return int(DOOR_B_HOURS / per)


def family_within_channel(rows: list[dict] | None = None) -> dict:
    """**同じチャンネルの中で**、上の族 対 下の族（`title_shape` の「同じch内」と同じ控え）。

    生の族の比は「その語でどれだけ大きい口が上位に居るか」をほとんど測っています。
    **族そのものの効きは、1つ の口が 2族 以上 に本を持っている所でしか読めません。**
    返り: `n_channels`（2族 以上 の口）・`ratio`（比の中央）・`up` / `total`（向きの数）。
    **判定はしません。** 覆る条件は `FAMILY_FLOOR_Q` の註 (1-b)(5)(6)。
    """
    L = corpus_longs() if rows is None else rows
    fs = [f for f in families(L) if f["n"] >= FAMILY_MIN_N]
    pos = {f["q"]: i for i, f in enumerate(sorted(fs, key=lambda f: -f["floor"]))}
    by: dict[str, dict[str, list[int]]] = {}
    for r in L:
        q = r.get("q", "")
        if q in pos:
            by.setdefault(r.get("channel", ""), {}).setdefault(q, []).append(r["views"])
    ratios = []
    for m in by.values():
        qs = sorted(m, key=lambda q: pos[q])
        hi, lo = qs[0], qs[-1]
        if pos[hi] == pos[lo]:
            # **1族 しか持たない口はここで落ちます**（hi と lo が同じ族）。
            # 落とさないと、その口は 1.00 を 1つ 投げ込み、比の中央値を 1 のほうへ薄めます
            # —— **189/218 が 1族 なので、薄めれば「族は効かない」に見えます**（覆る条件 (6)）。
            continue
        ratios.append(st.median(m[hi]) / max(st.median(m[lo]), 1))
    return {"n_channels": sum(1 for m in by.values() if len(m) >= 2),
            "total": len(ratios), "up": sum(1 for r in ratios if r > 1),
            "ratio": st.median(ratios) if ratios else 0.0,
            "channels": len(by)}


def family_floor_line(rows: list[dict] | None = None) -> str:
    """族の**床**（p25）と、扉(b) が要る回数を同じ行に並べる（**API 0単位・判定はしません**）。

    `family_line` は**中央値**（うまくいったらどこまで）。この行は**床**（外したらどこまで）です。
    決めと覆る条件は `FAMILY_FLOOR_Q` の註。
    """
    fs = [f for f in families(rows) if f["n"] >= FAMILY_MIN_N]
    if not fs:
        return ""
    fs = sorted(fs, key=lambda f: -f["floor"])
    mine = mine_by_family()
    need = door_b_views()
    w = family_within_channel(rows)
    body = " ／ ".join(
        f"{f['q']} 床 **{f['floor']:,.0f}**（中央 {f['median']:,.0f}・{f['n']}本・うち {len(mine.get(f['q'], []))}本）"
        for f in fs[:6])
    over = [f for f in fs if f["floor"] >= need]
    bot = fs[-1]
    return (
        f"**族の「床」（下から1/4・`peers.family_floor_line`・**API 0単位**・`niche_corpus` の `q` で割った・"
        f"門 n≧{FAMILY_MIN_N}本）: {body}"
        f" … いちばん下は **{bot['q']} 床 {bot['floor']:,.0f}**（{bot['n']}本）。"
        f"**生では 上と下は {fs[0]['floor'] / max(bot['floor'], 1):,.0f}倍**"
        f"（中央値の {fs[0]['median'] / max(min(f['median'] for f in fs), 1):,.0f}倍 より大きい）。 "
        f"!! **その生の比を「族の効き」と読まないこと** —— **同じチャンネルの中で比べると "
        f"{w['ratio']:.2f}倍**（2族 以上 に本を持つ口 **{w['n_channels']}/{w['channels']}**・"
        f"上が大きい **{w['up']}/{w['total']}**）＝ **残りは族ではなく口の大きさ**"
        f"（`title_shape` が『生の比が測っているのは題ではなくチャンネルの大きさ』と言うのと同じ罠・"
        f"`family_within_channel`）。 "
        f"**扉(b)（{DOOR_B_HOURS:,}時間）を回数に直すと {need:,}回**"
        f"（尺 {DOOR_B_SECS}秒 × 維持率 {DOOR_B_HOLD:.1%} ＝ 0.114時間/回・**尺と維持率で動く数**）"
        f" ＝ **生の床だけなら 1本 で越える族 {len(over)}つ**"
        + (f"（{'・'.join(f['q'] for f in over)}）" if over else "")
        + f"**だが、うちが族を変えて得るのは {w['ratio']:.2f}倍 です**（いま 100〜1,000回）＝ "
        "**族の選び方は「ただで効く分」であって、扉(b) を開ける手ではありません。** "
        "**この p25 は「その語で検索の上位に出た本の下から1/4」**（上振れの側）。"
        "**判定は立ったサブとオーナー。**")


# ---------------------------------------------------------------------------
# **扉(b) を「期限の中で越えた口」が在るかを、corpus から数える**
# （2026-09-19 03:xx・optimizer・Opus 5・ultracode・**API 0単位**）
# ---------------------------------------------------------------------------
#
# **なぜ足したか**: 02:5x の回が `trend.gate_measured` を新設し、うちの
# `data/studio/reporting.jsonl`（33日・249本）から扉(b) までの距離を測って
# **「17,870日（49年）・縛るほうで 210倍」**と印字し、こう結びました ——
# **「扉(b) は『遠い』のではなく、扉(a) と同じ側に在ります」**。
#
# **その同じ repo の、このファイルの冒頭（09/15 21:0x）には、反例が既に書いてありました** ——
# 齢 **44日** の `カメ先生のもらえるお金`（同じニッチ・本 40本・全部 長尺・総再生 89万回）。
# **2つ の口が、同じ `status` の中で、逆の答えを出していました。**
#
# **どちらも正しく、測っているものが違います**:
#
#     `trend.gate_measured`   **うちの出力**から扉(b) までの距離   ＝ 49年
#     この口                  **扉(b) が期限の長さで越えられるか** ＝ 越えた口が在る
#
# **＝ 02:5x の結びは、「うちの歩幅」を「扉の位置」と読んだ**ものです。
# この repo が繰り返し踏んでいる形（**片方の答えが、もう片方の答えと同じ字で出る** ——
# `reach_line` の 0／未着・`form_yield` の tail 空・`shakes` の `still`／`nowindow`）の **6例目**で、
# 今度は **「測って遠い」と「その形では遠い」** が同じ字で出ていました。
#
# **数えたもの**（`data/niche_channels.jsonl` の 218チャンネル・**API 0単位**）:
# **齢が期限（85日）より短い口は 218 のうち 4つ しかありません。** その 4つ の内訳が、
# この口の全部です —— 1つ が両方の扉を越え、1つ が届きかけ、2つ は うちと同じ所に居ます。
# **＝ これは「越えられる」の存在証明であって、「越えられる確率 1/4」ではありません**（n=4）。
#
# **決め（この口が変えるのは読み方 1つ だけ）**:
# **「期限の中に扉(b) は無い」と書くときは、この行に反例が 0本 であることを先に見ること。**
# 反例が 1本 でも在るなら、期限ではなく**うちの 1本あたり**を名指しすること。
# **この行は「長尺にしろ」とは言いません**（判断は立ったサブ・オーナー 09/06 14:0x）。
#
# **覆る条件**:
#  (1) 反例が **0本 になったら**（corpus が古びて若い口が全部 85日 を越えたら）、
#      この行は「反例なし」と印字します。**そのとき初めて「期限の側」を疑ってよい。**
#      いまの corpus は 2026-09-16 の写しで、**日が経つと若い口は自動で落ちます**
#      ＝ **0本 は「越えられない」ではなく「測れていない」**（`shakes` の `nowindow` と同じ札）。
#      **corpus を取り直すのは `channels.list` 5単位。**
#  (2) 扉(b) の判定は **総再生 × 1回あたりの分** で、**分のほうは corpus に在りません**
#      ＝ この口が出すのは「**4,000時間 に要る 分/回**」だけです。
#      **`GATE_PROOF_MAX_MIN_PER_VIEW`（4.0分）より小さい口だけを「越えた」と数えます** ——
#      `REV_LONG_MIN_PER_VIEW` と同じ前提の数で、**実測ではありません**。
#      カメ先生は **0.27分/回** で足りる ＝ **この前提を 15倍 甘くしても結論は動きません**
#      （その口の 89万回 は 1% の維持率でも 4,000時間 を越えます）。
#      **届きかけの口（2.41分/回）は前提に効きます** ＝ そちらは「越えた」に数えません。
#  (3) 登録の扉は **いまの登録者数**で見ています（`subs >= REV_GOAL_SUBS`）。
#      **収益化が実際に通ったかは、外から見えません** ＝ この口が言えるのは
#      「**門の条件を満たす所まで来た**」までで、「**収益化された**」ではありません。
#  (4) **1つ の口は分布ではありません。** 期限の中で越えた口が 1/4 だからといって、
#      うちが 1/4 で越えるという意味には**なりません**（相関ですらない ＝ ただの存在証明）。

#: 反例を探す窓（日）。既定は `trend.REV_DEADLINE_DAYS` ではなく、**渡された期限**を使います。
GATE_PROOF_DEADLINE_D = 85
#: 扉(b) を「越えた」と数えるときの、1回あたりの視聴の上限（分）。**前提**（覆る条件 (2)）。
GATE_PROOF_MAX_MIN_PER_VIEW = 4.0
#: 登録の扉（`trend.REV_GOAL_SUBS` と同じ数。**写しを持たないため、ここでは 1,000 を直に書きます**）。
GATE_PROOF_SUBS = 1_000


def gate_proof(deadline_days: int = GATE_PROOF_DEADLINE_D,
               now: "dt.datetime | None" = None) -> dict:
    """**扉(b) を「期限の長さ」で越えた口が在るか**（**API 0単位**・上の註）。

    返り: `{"at","n_corpus","deadline_days","young":[...],"passed":[...],
             "min_days": 越えた口のうち いちばん若い齢, "counter": 反例の本数}`
    `young` の各行: `id,title,age_days,subs,views,videos,views_per_day,subs_per_day,
    videos_per_day,need_min_per_view,subs_ok,hours_ok,both`
    **台帳が無ければ `young` は空**（**黙って「越えられない」と返してはいけません** ＝ 覆る条件 (1)）。
    """
    chs = niche_channels()
    now = now or now_jst()
    out: list[dict] = []
    for c in chs.values():
        s = (c.get("created") or "").replace("Z", "+00:00")
        try:
            born = dt.datetime.fromisoformat(s)
        except ValueError:
            continue
        if born.tzinfo is None:
            born = born.replace(tzinfo=dt.timezone.utc)
        age = (now - born).total_seconds() / 86400.0
        if age <= 0 or age > deadline_days:
            continue
        views = int(c.get("views") or 0)
        subs = int(c.get("subs") or 0)
        need = (DOOR_B_HOURS * 60.0 / views) if views else None
        subs_ok = subs >= GATE_PROOF_SUBS
        hours_ok = need is not None and need <= GATE_PROOF_MAX_MIN_PER_VIEW
        out.append({
            "id": c.get("id"), "title": c.get("title", ""), "age_days": age,
            "subs": subs, "views": views, "videos": int(c.get("videos") or 0),
            "views_per_day": views / age, "subs_per_day": subs / age,
            "videos_per_day": (int(c.get("videos") or 0)) / age,
            "need_min_per_view": need, "subs_ok": subs_ok, "hours_ok": hours_ok,
            "both": bool(subs_ok and hours_ok),
        })
    out.sort(key=lambda r: -r["subs"])
    passed = [r for r in out if r["both"]]
    return {"at": now.isoformat(timespec="seconds"), "n_corpus": len(chs),
            "deadline_days": deadline_days, "young": out, "passed": passed,
            "counter": len(passed),
            "min_days": (min(r["age_days"] for r in passed) if passed else None)}


def gate_proof_line(deadline_days: int = GATE_PROOF_DEADLINE_D,
                    now: "dt.datetime | None" = None) -> str:
    """毎周 1行。**`trend.gate_measured_line` の真下に必ず並べます**（上の註 ＝ 6例目の罠）。"""
    g = gate_proof(deadline_days, now)
    head = ("**その距離を「扉の位置」と読まないための控え —— 期限の長さで扉を越えた口が在るか**"
            f"（`peers.gate_proof`・**API 0単位**・台帳 `niche_channels` {g['n_corpus']}チャンネル）: ")
    if not g["n_corpus"]:
        return (head + "**台帳が在りません** ＝ **反例は「0本」ではなく「測っていない」**です"
                "（`channels.list` **5単位** で取り直すこと・覆る条件 (1)）。")
    if not g["young"]:
        return (head + f"**齢 {g['deadline_days']}日 未満の口が corpus に 1つ もありません** ＝ "
                "**反例なし ではなく 窓が空**です（corpus は 2026-09-16 の写し・覆る条件 (1)）。")
    out = [head + f"**齢 < {g['deadline_days']}日 の口は {len(g['young'])}本**"
                  f"（218 のうち）。**そのうち 両方の扉を越えている口 {g['counter']}本**"
           + (f"・いちばん若いので **{g['min_days']:.0f}日**" if g["min_days"] else "") + ":"]
    for r in g["young"]:
        need = (f"{r['need_min_per_view']:6.2f}分/回"
                if r["need_min_per_view"] is not None else "   —   ")
        mark = "**両扉 ○**" if r["both"] else ("登録のみ○" if r["subs_ok"] else
                                              ("時間のみ○" if r["hours_ok"] else "  −  "))
        out.append(f"  齢{r['age_days']:5.0f}日 登録{r['subs']:>7,} 総再生{r['views']:>10,} "
                   f"本{r['videos']:>4}（{r['videos_per_day']:.2f}本/日） "
                   f"再生{r['views_per_day']:>8,.0f}/日 登録{r['subs_per_day']:>6.1f}/日 "
                   f"4,000時間に要る {need} {mark}  {r['title'][:22]}")
    if g["counter"]:
        out.append(
            f"  ＝ **「期限の中に扉(b) は無い」は、この口の数では引けません**（反例 {g['counter']}本）。"
            "**すぐ上の行（`gate_measured`）が測っているのは扉の位置ではなく、うちの歩幅**です。"
            f"**名指しすべきは期限ではなく、うちの 1本あたり**（うちの長尺 **71回/本**・"
            "**0.19分/回** ＝ 7日 たった本で 6〜32回）。"
            "**この行は「長尺にしろ」とは言いません**（判断は立ったサブ）。"
            "**n は小さく、越えた口が在ることだけが言えます**（覆る条件 (4)）。")
    else:
        out.append("  ＝ **反例は 0本 です。** ただし窓に入る口が "
                   f"{len(g['young'])}本 しかないので、**「越えられない」ではなく「まだ出ていない」**"
                   "の側から先に疑うこと（覆る条件 (1)・(4)）。")
    return "\n".join(out)
