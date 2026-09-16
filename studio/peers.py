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
        f"**この分布は検索の上位に寄っています ＝ 上振れの側**（覆る条件 (2)）。")


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
