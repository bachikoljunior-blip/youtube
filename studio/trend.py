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
    return out


def report(within_h: float = 24 * 3) -> list[str]:
    return lines(ledger_rows(), within_h=within_h)
