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

from .common import JST, ledger_rows, now_jst


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
#: **それでも手は決まります**: 原因がどちらでも、**この帯の回は伸びを読めない**。
#: だから数を並べるだけにして、「止まった」と書かないこと。
#: **覆る条件**: この帯で伸びた組が 1つでも出たら、この註の 178/178 は破れる（数は毎回 台帳から数え直すので、
#: 印字のほうは自動で追随する）。公開の刻を変えた本が出たら、交絡が解けるので分けて数え直すこと。
DEAD_START, DEAD_END = 2, 10


def dead_window(rows: list[dict]) -> tuple[int, int, int, int]:
    """`measured` の連続する2点を、2点目の刻で「02〜10時 JST」と「それ以外」に分け、
    それぞれ（伸びた組, 全体の組）を数える。**写しを持たず、毎回 台帳から数える。**"""
    ser = series(rows)
    nm = nt = om = ot = 0
    for pts in ser.values():
        for a, b in zip(pts, pts[1:]):
            va, vb = a.get("views"), b.get("views")
            if va is None or vb is None:
                continue
            moved = int(vb) - int(va) > 0
            if DEAD_START <= _at(b).hour < DEAD_END:
                nt += 1
                nm += moved
            else:
                ot += 1
                om += moved
    return nm, nt, om, ot


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
    out: list[str] = []
    for day in sorted(days, reverse=True):
        cohort = sorted(days[day])
        out.append(f"{day}（{len(cohort)}本）")
        for pub, vid, pts in cohort:
            mark = "新" if vid in mine else "旧"
            trail = " → ".join(f"{p['age_h']:.1f}h {p['views']}" for p in pts[-6:])
            out.append(f"  {pub:%H:%M} {mark} {vid:12s} {trail}{_growth(pts)}")
    if not out:
        out.append("（台帳に、この日数のうちに公開された本の measured がありません）")
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
