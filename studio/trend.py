"""台帳（data/studio/ledger.jsonl）だけを読んで、本ごとの「齢 → 再生」の並びを出す。API 0単位。

**なぜ要るか（2026-09-07 18:3x JST・optimizer・Opus が実測して足した）**:
§7 は「その回に見た1点」で書かれ続け、2回 続けて外れた。

  1本目 EkNqtkK49Bw   9.6h 127 → 28.4h 122 まで **19時間 平ら** → 30.6h 129 → 32.6h **139**
  2本目 nQbVxuWpWw8   4.4h 28 → 6.6h 28 で平ら → 8.6h **68**（2時間で +40 ＝ 2.4倍）

09/07 16:3x の §7 は「1本目は 6時間で 100%」「2本目が 28回 で止まった」と書いたが、
**どちらも平らな区間の中で見た点**だった。同じ日の旧作りと並べた「38%」も同じで、
2時間 あとには 68 対 73 ＝ **93%** になっている（旧作りのほうは 7.6h 73 → 9.6h 73 で平ら）。
＝ **平らは「止まった」ではない。** 数え直しの間隔なのか配信の波なのかは台帳からは決められないが、
どちらでも **齢の浅い1点で本と本を比べてはいけない** ことは決まる。

だからこの道具は、1本につき**並び全部**と、直近の伸び（+N回/時）を出す。
**覆る条件**: 平らな区間のあとに一度も伸びない本が 3本 続いたら、平らは本当に止まりで、
そのときは「最後の点」で比べてよい（この註と §7 の警告を消す）。
"""
from __future__ import annotations

import datetime as dt
import json

from .common import JST, ROOT, ledger_rows, now_jst


def _at(row: dict) -> dt.datetime:
    return dt.datetime.fromisoformat(row["at"]).astimezone(JST)


def ours(rows: list[dict]) -> set[str]:
    """こちらの作りの本（scheduled 行が持つ video_id）。旧作りと分けて並べるため。"""
    return {r["video_id"] for r in rows if r.get("event") == "scheduled" and r.get("video_id")}


def series(rows: list[dict]) -> dict[str, list[dict]]:
    """id → measured の点（齢の順）。同じ齢の重複は後の行を採る。"""
    out: dict[str, dict[float, dict]] = {}
    for r in rows:
        if r.get("event") != "measured" or "age_h" not in r:
            continue
        out.setdefault(r["id"], {})[round(float(r["age_h"]), 1)] = r
    return {vid: [pts[k] for k in sorted(pts)] for vid, pts in out.items()}


def pending(rows: list[dict]) -> dict[str, tuple[dt.datetime, str]]:
    """id → （公開予定の刻, 題）。`measure` が毎回 書く `pending` 行から（最後の行を採る）。

    **なぜ日ごとの本数に「予約」を足すか**（2026-09-08 23:0x JST・optimizer・Opus が踏んだ）:
    この道具は `measured`（＝**公開ずみ**）だけを数えるので、**その日に出る予定の本は 1本 も数に入らない。**
    実測 09/08: 旧作りの `Yy7GmcGoQ6I` が 08/19 に上げられ 09/02 に `reschedule.py` で
    **09/08 23:00 JST** の publishAt を打たれたまま private で待っていた。`status` の「きょうの枠」には
    private として出ていたが、**この道具の日の見出しは 22時間 ずっと「09/08（1本）」**で、
    §7 は 15:0x〜21:4x の **5回 続けて**「3本目は **1本 だけの日** に出た」と書き、
    「同じ条件の 2点目」を 09/09 に期待していた。23:00 にその本が出て、**09/08 は 2本 の日になった。**
    ＝ §1 の「量は毒」がそのまま効く軸（その日の本数）が、**判定を書いている当の数から抜けていた。**
    **覆る条件**: 予約が「その日に本当に出る」ことの確からしさが崩れたら（予約のまま出なかった本が出たら）、
    見出しは「＋予約」ではなく別の印を使う（`pending` 行は残るので数え直せる）。
    """
    out: dict[str, tuple[dt.datetime, str]] = {}
    for r in rows:
        if r.get("event") != "pending" or not r.get("publish_at"):
            continue
        out[r["id"]] = (dt.datetime.fromisoformat(r["publish_at"]).astimezone(JST), r.get("title", ""))
    return out


def published_at(points: list[dict]) -> dt.datetime:
    """公開の刻 ＝ 最初の点の「いつ測ったか」から齢を引く（API を撃たずに日で束ねるため）。"""
    p = points[0]
    return _at(p) - dt.timedelta(hours=float(p["age_h"]))


def _growth(pts: list[dict]) -> str:
    """直近の2点の伸び。平らな区間の中で「止まった」と読まないための目印。"""
    if len(pts) < 2:
        return ""
    a, b = pts[-2], pts[-1]
    dh = float(b["age_h"]) - float(a["age_h"])
    dv = int(b["views"]) - int(a["views"])
    if dh <= 0:
        return ""
    return f"   [直近 {dv:+d}回 / {dh:.1f}h]"


#: **再生が1度も増えていない時間帯**（2026-09-08 04:4x JST・optimizer・Opus に台帳から数えた）。
#:
#: §7 は 10:2x・14:2x・16:3x・00:5x と、平らな点から「止まった／絞られている」を繰り返し引いてきた。
#: `_growth()` は「直近の2点」を出すだけなので、**その2点がどの時間帯に落ちたか**は見えていない。
#: 台帳の `measured` の連続する2点 549組 を刻で分けた実測:
#:
#:     02:00〜10:00 JST に落ちた2点目   伸びた **0組** ／ 平ら 178組（**178/178**）
#:     それ以外                          伸びた 15組 ／ 平ら 356組
#:
#: **＝ この帯で測った回は、何を見ても平らです。** 04:4x のこの回も 15本 全部 +0 だった。
#:
#: **交絡を先に書く（これを書かずに引くのが §7 の踏んだ形そのもの）**: このチャンネルは
#: **10:00 JST に公開する**ので、「2点目が 02〜10時」は「その本の齢が 16〜19h か 40〜43h か 64〜67h」と
#: **完全に重なっています**。齢 10h 未満の本がこの帯で測られたことは1度も無い ＝
#: **刻のせいなのか齢のせいなのかは、この台帳からは分けられません。**
#: 分けるには公開の刻を変えた本が要る（§7 の「時刻 10:00」の行）。
#:
#: > **【2026-09-09 00:2x・optimizer・Opus】この「分けられません」は、半分だけ本当でした。**
#: > **新しい作りは 10:00 JST 固定ですが、旧作りは 06:59〜18:59 のいろいろな刻に公開されています。**
#: > 実測: 帯に落ちる2点組は **42本 ぶん・齢は 9h〜191h に散っている**（`band_vs_age`）。
#: > ＝ **齢を揃えたうえで帯と外を比べられます。** 齢の束ごとに「帯の外の伸び率 × 帯の組数」を足すと、
#: > **齢だけで説明できるなら帯の中に 7.33組 の伸びが在るはず**で、実際は **0組**。
#: > 伸びの札を本の中で並べ替える検定（相関を殺さない形）で **p = 0.012**、
#: > 本ごと×齢の束ごとの、いちばん厳しい並べ替えでも **p = 0.031**。
#: > ＝ **帯の 0 は、齢だけでは説明できません。刻の側に何かが残ります。**
#: > **ただし「視聴者が寝ている」と「YouTube の数え直しが夜は回らない」は、まだ分けられません**
#: > （どちらも同じ形に出る）。**手は変わりません** —— この帯の回は伸びを読まないこと。
#:
#: **それでも手は決まります**: 原因がどちらでも、**この帯の回は伸びを読めない**。
#: だから数を並べるだけにして、「止まった」と書かないこと。
#: **覆る条件**: この帯で伸びた組が 1つでも出たら、この註の 178/178 は破れる（数は毎回 台帳から数え直すので、
#: 印字のほうは自動で追随する）。公開の刻を変えた本が出たら、交絡が解けるので分けて数え直すこと。
DEAD_START, DEAD_END = 2, 10

#: **長さの違う2点組を、同じ分母に入れないための閾**
#: （2026-09-09 00:2x JST・optimizer・Opus が数えて足した）。
#:
#: 同じ回に `measure` を2回 撃つと、数分しか離れていない2点組が台帳に入ります。実測:
#: 台帳の 818組 のうち **74組 が 10分 未満**（23:03/23:08/23:10 のように、道具を直した回が
#: 確かめのために撃ち直したぶん）。**74組 は全部 帯の外**に落ちており、`dead_window` の
#: 「それ以外」の分母だけを 541 → 615 に膨らませていました（伸びの率 4.1% → 3.7%）
#: ＝ 帯との差を**小さく見せる**向き。帯の側（203組）は中央値 151分・最小 119.6分 で 1組も混ざっていません。
#:
#: **足すときに「構造的に平ら（数え直しは分では動かない）」と書きかけて、撃ったら外れました。**
#: 74組 のうち **2組 は動いています**:
#:
#:     EkNqtkK49Bw  09/07 16:30 **122** → 16:35 **129**   5.2分 で **+7**
#:     nQbVxuWpWw8  09/08 23:08  **68** → 23:10  **66**   1.6分 で **-2**
#:
#: ＝ **YouTube の数え直しは分の粒度でも動きます。** 落とす理由は「情報が無いから」ではなく、
#: **`dead_window` が「組あたりの率」を数えているから**です —— 2分の組と 2時間の組を同じ分母に
#: 入れると、短い組は「伸びなかった」側にばかり積まれます（短い組の伸びは 1/74 ＝ 1.4%、
#: 10分 以上の組は 22/541 ＝ 4.1%。**時間が短いぶんだけ低い**、それだけのこと）。
#: **23:0x の回が「数え直しの揺れ」と呼んだ -2 は、この 1.6分 の組です**（本が減ったのではない）。
#:
#: **覆る条件**: (1) `dead_window` を「組あたり」から「組×時間あたり」に変えたら、
#: 長さを揃える必要が無くなるので、この閾ごと要らなくなる（`band_vs_age` の `per_hour` が既にその形）。
#: (2) 数え直しの間隔が 10分 より短い回り方に変えたら、閾はその間隔まで下げること。
MIN_PAIR_MIN = 10.0

#: 齢の帯（`band_vs_age` が「同じ齢どうし」で突き合わせるときの束）。
AGE_BUCKETS = ((0, 12), (12, 24), (24, 36), (36, 48), (48, 72), (72, 10_000))


def _pairs(rows: list[dict]) -> list[dict]:
    """`measured` の連続する2点を、判定に要る形だけにして並べる。

    **`MIN_PAIR_MIN` より短い組は落とします**（上の註）。
    """
    out: list[dict] = []
    for vid, pts in series(rows).items():
        for a, b in zip(pts, pts[1:]):
            va, vb = a.get("views"), b.get("views")
            if va is None or vb is None:
                continue
            ta, tb = _at(a), _at(b)
            if (tb - ta).total_seconds() / 60.0 < MIN_PAIR_MIN:
                continue
            age = b.get("age_h")
            bucket = next(((lo, hi) for lo, hi in AGE_BUCKETS
                           if age is not None and lo <= age < hi), None)
            out.append({"vid": vid, "age": age, "bucket": bucket,
                        "gap_min": (tb - ta).total_seconds() / 60.0,
                        "band": DEAD_START <= tb.hour < DEAD_END,
                        "delta": int(vb) - int(va),
                        "a": int(va), "b": int(vb), "at": tb,
                        "grew": int(vb) - int(va) > 0})
    return out


def dead_window(rows: list[dict]) -> tuple[int, int, int, int]:
    """`measured` の連続する2点を、2点目の刻で「02〜10時 JST」と「それ以外」に分け、
    それぞれ（伸びた組, 全体の組）を数える。**写しを持たず、毎回 台帳から数える。**"""
    nm = nt = om = ot = 0
    for p in _pairs(rows):
        if p["band"]:
            nt += 1
            nm += p["grew"]
        else:
            ot += 1
            om += p["grew"]
    return nm, nt, om, ot


def drops(rows: list[dict]) -> tuple[int, int, int, str]:
    """再生が**減った**2点組を数える（組数, 減った組, いちばん大きい減り, その組の説明）。

    **`dead_window` とまったく同じ `_pairs` から数えます。ここが要点です** ——
    §7 は 17:0x（2026-09-08）から毎周この数を手で数え直しており、
    **同じ段落の中で分母が2つ**になっていました:

        帯の率      `dead_window` ＝ **`MIN_PAIR_MIN` で短い組を落としたあと**の組
        減りの数    手で書いた script ＝ **落とす前**の組（00:2x の「818組」）

    実測 2026-09-09 01:5x: 落とす前 **854組・減り 7組**／落としたあと **769組・減り 6組**。
    差の1組は `nQbVxuWpWw8` の **1.6分** の組（68 → 66）で、
    **00:2x の回が「これは数え直しの揺れで、本が減ったのではない」と名指しした当のもの**です。
    ＝ 落とす理由を書いた回自身が、**減りのほうは落とさずに数えていました。**
    手で数えるかぎり、次の回もどちらの分母を使ったか分かりません。→ 道具の側に置く。

    **何に使うか**: §7 17:0x は「床（旧作りの中央値）を越えたか」を、
    **「ここから床まで落ちるには、この台帳に1度も無い大きさの減りが要る」**という形で読んでいます。
    その「1度も無い大きさ」がこの関数の3つ目の返り値で、**覆る条件はそこに掛かっています**
    （減りが -5回 を越えた組が出たら、余裕の倍率を数え直すこと）。

    **覆る条件**: `MIN_PAIR_MIN` を変えたら、ここの数も一緒に動きます（同じ `_pairs` なので自動）。
    減りが「数え直しの揺れ」ではなく本当の取り下げ（本が消える・非公開に戻る）で出るようになったら、
    その組は別に数えること —— いまは `unscheduled` の本が measured から落ちるだけなので、組にならない。
    """
    ps = _pairs(rows)
    dec = [p for p in ps if p["delta"] < 0]
    if not dec:
        return len(ps), 0, 0, ""
    worst = min(dec, key=lambda p: p["delta"])
    where = (f"{worst['vid']} {worst['at']:%m/%d %H:%M} {worst['a']}→{worst['b']}")
    return len(ps), len(dec), worst["delta"], where


def band_vs_age(rows: list[dict], iters: int = 2000, seed: int = 20260909) -> dict:
    """**帯の 0 は「刻」なのか「齢」なのかを、台帳の中だけで分けにいく**
    （2026-09-09 00:2x JST・optimizer・Opus が足した）。

    上の註は「公開が 10:00 JST なので、帯は齢 16〜19h／40〜43h と重なっており、
    **刻と齢を分けられません**」と書いていた。**それは半分だけ本当でした** ——
    旧作りは 06:59〜18:59 JST のいろいろな刻に公開されているので、
    **帯に落ちる2点組の齢は 9h〜191h に散っています**（42本・実測）。
    ＝ 齢を揃えたうえで帯と外を比べる余地が、台帳の中に在ります。

    出すもの:

      `expected`  齢の束ごとに「帯の外の伸び率 × 帯の組数」を足したもの
                  ＝ **齢だけで説明できるなら、帯の中でこれだけ伸びているはず**の数
      `observed`  帯の中で実際に伸びた組（いまは 0）
      `p_video`   伸びの札を**本ごとに**並べ替えて、帯に落ちる数が observed 以下になる率
      `p_va`      同じ並べ替えを**本ごと×齢の束ごと**にしたもの（いちばん厳しい）

    **並べ替えを使う理由**: 2点組は本ごとに強く相関する（伸びる本は続けて伸びる）ので、
    ポアソンや χ² は「独立な 818組」と読んで p を小さく出しすぎます。
    札を本の中でだけ入れ替えれば、**本ごとの伸びの回数はそのまま**で、
    「その伸びが帯を避けたのは偶然か」だけを訊けます。

    **これは §5 の「教訓の形」（確かめる手を足すときは、それが元の手と違う物を見ているかを先に撃つ）
    を通してあります**: 生の 0/203 は齢で全部 説明できてしまう見込みが在り、
    齢を揃えると `expected` が 7.33 → p_va 0.031 と**別の答え**になりました（足した回の実測）。

    **覆る条件**: (1) `p_va` が 0.05 を越えたら、帯の 0 は齢で説明できる範囲に戻る
    （そのときは §7 の「帯の回は伸びを読めない」を、齢の帯の話に書き直すこと）。
    (2) 公開の刻を変えた本が出たら交絡そのものが解けるので、並べ替えは要らなくなる。
    """
    import random

    pairs = _pairs(rows)
    observed = sum(1 for p in pairs if p["band"] and p["grew"])
    per_bucket: list[tuple[tuple[int, int] | None, int, int, int, int]] = []
    expected = 0.0
    for lo, hi in AGE_BUCKETS:
        bi = [p for p in pairs if p["bucket"] == (lo, hi) and p["band"]]
        ou = [p for p in pairs if p["bucket"] == (lo, hi) and not p["band"]]
        rate = (sum(p["grew"] for p in ou) / len(ou)) if ou else 0.0
        expected += rate * len(bi)
        per_bucket.append(((lo, hi), sum(p["grew"] for p in bi), len(bi),
                           sum(p["grew"] for p in ou), len(ou)))

    rng = random.Random(seed)

    def _perm(by_bucket: bool) -> float:
        groups: dict[tuple, list[dict]] = {}
        for p in pairs:
            groups.setdefault((p["vid"], p["bucket"]) if by_bucket else (p["vid"],), []).append(p)
        live = [(g, sum(x["grew"] for x in g)) for g in groups.values()]
        live = [(g, k) for g, k in live if k]
        if not live:
            return 1.0
        hits = 0
        for _ in range(iters):
            tot = 0
            for g, k in live:
                tot += sum(rng.sample([x["band"] for x in g], k))
            if tot <= observed:
                hits += 1
        return hits / iters

    # **長さで揃える**（齢で揃えるより素直な対照）。
    # 帯の組は**外の組より長い**（中央 151分 対 123分・平均 189分 対 144分）ので、
    # 帯は伸びる機会を**多く**持っていて 0 です ＝ 長さの偏りは、この結論と**逆向き**に効いています。
    band_h = sum(p["gap_min"] for p in pairs if p["band"]) / 60.0
    out_h = sum(p["gap_min"] for p in pairs if not p["band"]) / 60.0
    out_grew = sum(1 for p in pairs if not p["band"] and p["grew"])
    per_hour = (out_grew / out_h) if out_h else 0.0
    matched = [p for p in pairs if 100 <= p["gap_min"] <= 200]
    mb = [p for p in matched if p["band"]]
    mo = [p for p in matched if not p["band"]]

    return {"observed": observed, "expected": expected,
            "p_video": _perm(False), "p_va": _perm(True),
            "buckets": per_bucket, "pairs": len(pairs),
            # 帯が外と同じ「組×時間あたり」で伸びていたら、帯の中に在るはずの伸びの数
            "expected_per_hour": per_hour * band_h,
            "band_hours": band_h, "out_hours": out_h,
            # 100〜200分 の組だけで揃えたもの（伸びた/全体）
            "matched": (sum(p["grew"] for p in mb), len(mb),
                        sum(p["grew"] for p in mo), len(mo))}


def lines(rows: list[dict], within_h: float = 24 * 3, now: dt.datetime | None = None) -> list[str]:
    now = now or now_jst()
    mine = ours(rows)
    ser = series(rows)
    days: dict[str, list[tuple[dt.datetime, str, list[dict]]]] = {}
    for vid, pts in ser.items():
        pub = published_at(pts)
        if (now - pub).total_seconds() / 3600 > within_h:
            continue
        days.setdefault(pub.strftime("%m/%d"), []).append((pub, vid, pts))
    # まだ公開前の本（予約）も日ごとに束ねる —— 見出しの本数から抜けると §7 が「1本 だけの日」と読む（`pending` の註）。
    waiting_days: dict[str, list[tuple[dt.datetime, str, str]]] = {}
    for vid, (pub, title) in pending(rows).items():
        if vid in ser:  # もう公開されて measured が付いた本は「予約」ではない
            continue
        if (now - pub).total_seconds() / 3600 > within_h:
            continue
        waiting_days.setdefault(pub.strftime("%m/%d"), []).append((pub, vid, title))
    out: list[str] = []
    for day in sorted(set(days) | set(waiting_days), reverse=True):
        cohort = sorted(days.get(day, []))
        waiting = sorted(waiting_days.get(day, []))
        out.append(f"{day}（{len(cohort)}本" + (f"＋予約 {len(waiting)}本" if waiting else "") + "）")
        for pub, vid, pts in cohort:
            mark = "新" if vid in mine else "旧"
            trail = " → ".join(f"{p['age_h']:.1f}h {p['views']}" for p in pts[-6:])
            out.append(f"  {pub:%H:%M} {mark} {vid:12s} {trail}{_growth(pts)}")
        for pub, vid, title in waiting:
            out.append(f"  {pub:%H:%M} 予 {vid:12s} まだ公開前（この日の本数に入る） {title[:30]}")
    if not out:
        out.append("（台帳に、この日数のうちに公開された本の measured がありません）")
    # **帯の数は、帯の中に居る回だけでなく毎回 印字する** —— §7 は毎周この数を書き写しており、
    # 手で数え直すたびに数え方が揺れていた（2026-09-09 00:2x）。
    nm, nt, om, ot = dead_window(rows)
    out.append(
        f"帯 {DEAD_START:02d}:00〜{DEAD_END:02d}:00 JST の2点組 **{nm}/{nt}** が伸びた"
        f"（それ以外は {om}/{ot}）。**{MIN_PAIR_MIN:.0f}分 未満の2点組は数えていません**"
        "（長さの違う組を同じ分母に入れないため —— studio/trend.py の `MIN_PAIR_MIN` の註）。")
    np_, nd, worst, where = drops(rows)
    out.append(
        f"同じ {np_}組 のうち、再生が**減った**組 **{nd}**"
        + (f"・いちばん大きい減り **{worst}回**（{where}）" if nd else "")
        + "。**帯の率と同じ分母です**（手で数え直すと分母が2つになる —— studio/trend.py の `drops` の註）。")
    # **この一文は最後に置くこと**（`tests/test_studio_trend.py` が末尾で止めている）。
    out.append("平らは「止まった」ではない —— 実測は studio/trend.py の註。齢の浅い1点で本を比べないこと。")
    if DEAD_START <= now.hour < DEAD_END:
        nm, nt, om, ot = dead_window(rows)
        out.append(
            f"**いまは {DEAD_START:02d}:00〜{DEAD_END:02d}:00 JST ＝ この台帳で再生が伸びたことのない帯です**"
            f"（この帯の2点組 {nm}/{nt} が伸びた・それ以外は {om}/{ot}）。"
            "**この回の「平ら」からは、止まったかどうかを読めません。**"
            "数を並べるだけにして、判定は帯の外の回へ渡すこと（交絡は studio/trend.py の註 —— "
            "公開が 10:00 JST なので、この帯は「齢 16〜19h／40〜43h」と重なっており、刻と齢を分けられません）。")
    return out


def report(within_h: float = 24 * 3) -> list[str]:
    return lines(ledger_rows(), within_h=within_h)


#: **「その日に何本 出したか」を軸にして 48時間 の再生を並べ直す**
#: （2026-09-08 17:0x JST・optimizer・Opus が §7 の覆る条件に呼ばれて足した）。
#:
#: §7 15:0x/16:0x の覆る条件は「`lQHX9LJ80Sg` が 48h で 214回（09/06 の旧作りの中央値）を越えたら、
#: **日ごとの本数を軸に入れて数え直すこと**」と書いていた。17:0x に 7.1h 236回 で越えたので数え直した結果、
#: **この軸は、この台帳では日付と同じ物でした**:
#:
#:     4本/日 → 08/16 だけ    5本/日 → 09/05 だけ    13本/日 → 08/23 だけ    25本/日 → 08/22 だけ
#:     ＝ ほとんどの「本数」の値は **1日 にしか出ていない**ので、
#:       「本数ごとの中央値」は「その日の中央値」を書き写したものになる。
#:
#: 2日以上に出ている値で比べると、**同じ本数でも日が違えば桁が変わります**:
#:
#:     8本/日   08/19 中央値 1094  ／  09/06 中央値 196    （5.6倍）
#:     10本/日  08/24 中央値 1146  ／  08/31 中央値 121    （9.5倍）
#:     1本/日   08/14 の 1451 から 09/01 の 3 まで（同じ「1本/日」で 480倍）
#:
#: **＝ 本数を軸にしても、日付のぶんが丸ごと混ざったままです。** 04:4x の「刻 と 齢 が
#: 完全に重なっていて分けられない」と同じ形で、分けるには**同じ日に本数だけ変えた実測**が要る
#: （＝ 本数を変えた日を作らないと出ない。いまは 1本/日 に収束しているので、この軸は当分 埋まらない）。
#:
#: だからこの関数は**中央値を1つ出して終わりにせず**、値ごとに「何日ぶんか」を必ず一緒に印字する。
#: **数は毎回 台帳と `data/views.jsonl` から数え直す（写しを持たない）。**
#: **覆る条件**: 同じ本数の日が 3日 以上そろった値が出たら、そこで初めて日付と本数を分けられる
#: （そのときはこの註を数え直して書き換える）。1本/日 の日が増えるのが最短の道。
VIEWS_JSONL = ROOT / "data" / "views.jsonl"


def _old_series(path=None) -> dict[str, list[tuple[float, int, dt.datetime]]]:
    """旧道具が残した測り `data/views.jsonl` を読む（**過去のデータ** ＝ §8 の「使わない道具」ではない）。
    id → [(齢, 再生, 測った刻)]。無ければ空。"""
    path = VIEWS_JSONL if path is None else path
    out: dict[str, list[tuple[float, int, dt.datetime]]] = {}
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("hours") is None or r.get("views") is None:
            continue
        at = dt.datetime.fromisoformat(str(r["at"]).replace("Z", "+00:00")).astimezone(JST)
        out.setdefault(r["id"], []).append((float(r["hours"]), int(r["views"]), at))
    return out


def cohorts(rows: list[dict], old_path=None, lo: float = 40.0, hi: float = 60.0):
    """本ごとに（公開日, 公開の刻, 48時間 に最も近い点）を出す。台帳と旧データの両方から。

    返すのは (48h の点が取れた本, 公開日ごとの「その日に出た本の数」)。
    **本数は「48h の点が取れた本」ではなく、刻が分かる本 全部 で数える** ——
    そうしないと軸そのものが狂う（実測 08/24 は 10本/日 だが 48h の点は 2本 しか無い）。
    48h の点が `lo`〜`hi` の外にしか無い本は、比べられないので中央値からは落とす。
    """
    pts: dict[str, list[tuple[float, int, dt.datetime]]] = {}
    for vid, ps in _old_series(old_path).items():
        pts.setdefault(vid, []).extend(ps)
    for vid, ps in series(rows).items():
        pts.setdefault(vid, []).extend(
            (float(p["age_h"]), int(p["views"]), _at(p)) for p in ps if p.get("views") is not None)
    mine = ours(rows)
    per_day_total: dict[dt.date, int] = {}
    out = []
    for vid, ps in pts.items():
        ps.sort()
        pub = min(at - dt.timedelta(hours=h) for h, _, at in ps)
        per_day_total[pub.date()] = per_day_total.get(pub.date(), 0) + 1
        near = [(abs(h - 48.0), h, v) for h, v, _ in ps if lo <= h <= hi]
        if not near:
            continue
        near.sort()
        out.append((pub.date(), pub, vid, near[0][1], near[0][2], vid in mine))
    out.sort()
    return out, per_day_total


def _median(xs: list[int]) -> float:
    xs = sorted(xs)
    n = len(xs)
    return float(xs[n // 2]) if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2


def by_day_count(rows: list[dict], old_path=None) -> list[str]:
    """「その日に何本 出したか」ごとに 48時間 の再生を並べる。**値ごとに「何日ぶんか」を必ず出す。**"""
    co, total = cohorts(rows, old_path)
    if not co:
        return ["（48時間 の点が取れた本が、台帳にも data/views.jsonl にもありません）"]
    per_day: dict[dt.date, list[tuple[int, str, bool]]] = {}
    for day, pub, vid, _h, v, isnew in co:
        per_day.setdefault(day, []).append((v, vid, isnew))
    out = ["== 公開日ごとの 48時間 再生 =="]
    for day in sorted(per_day):
        vs = [v for v, _, _ in per_day[day]]
        n_new = sum(1 for _, _, isnew in per_day[day] if isnew)
        got = f"（48h の点 {len(vs)}本）" if len(vs) != total[day] else ""
        out.append(f"  {day}  {total[day]:2d}本/日{got}  中央値 {_median(vs):7.1f}  範囲 {min(vs)}〜{max(vs)}"
                   f"{f'  ← 新しい作り {n_new}本' if n_new else ''}")
    by_n: dict[int, list[dt.date]] = {}
    for day in per_day:
        by_n.setdefault(total[day], []).append(day)
    out.append("")
    out.append("== 「その日の本数」ごと ——「何日ぶんか」を必ず見ること ==")
    for n in sorted(by_n):
        days = sorted(by_n[n])
        meds = [_median([v for v, _, _ in per_day[d]]) for d in days]
        spread = (f"  同じ本数の日どうしで {max(meds) / max(min(meds), 1):.1f}倍 ちがう"
                  if len(days) > 1 else "")
        out.append(f"  {n:2d}本/日  {len(days)}日ぶん（{', '.join(d.strftime('%m/%d') for d in days)}）"
                   f"  中央値 {' / '.join(f'{m:.0f}' for m in meds)}{spread}")
    multi = [n for n, d in by_n.items() if len(d) > 1]
    out.append("")
    out.append(f"**「本数」の値 {len(by_n)}個 のうち、2日以上に出ているのは {len(multi)}個** —— "
               "残りは 1日 しか無いので、その中央値は「その日の中央値」の書き写しです。"
               "**本数を軸にしても、日付のぶんは分けられません**（studio/trend.py の註。"
               "分けるには、同じ日に本数だけ変えた実測が要る）。")
    return out
