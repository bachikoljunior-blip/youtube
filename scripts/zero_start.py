"""**「0回 のまま始まった本」は、そのあと伸びるか** —— 旧データの下敷きと、いまの本の立ち位置（API 0単位・数秒）。

    python scripts/zero_start.py                  # 齢 8〜12h の窓（いまの 5本目 が居る所）
    python scripts/zero_start.py --lo 20 --hi 28  # 別の齢の窓（24h の点で読み直すとき）
    python scripts/zero_start.py --all-hours      # 公開時刻の帯（09〜13時 JST）で絞らない（**下の (3)**）

**なぜ道具にしたか**（2026-09-10 20:0x JST・optimizer・Opus）:
5本目 `2YZ_4FXC-XI` が **齢 9.9h まで 0回** で、§7 (c) は「**齢 24h の点**を見る」と書いていました。
その 24h に何が言えるかは、**旧データ（`data/views.jsonl` 34,001点・`data/uploaded.jsonl` 873本）に
在るのに、1度も数えられていません**でした。数えたら、**判定の齢そのものが外れていました**（下）。
旧データは**凍結**なので下敷きは動きませんが、**いまの本の立ち位置は毎周 動きます** ——
だから散文ではなく道具にします（`method_growth.py`・`trend.py` の「毎周 印字する数」と同じ扱い）。

**数え方**（変えるときは、下の実測ごと取り直すこと）:

    帯          公開の刻（JST）が **09〜13時** の本だけ（§1 の表「14:00 以降 は 0〜4回」＝
                帯を混ぜると、0回 ではなく**公開の刻**を測ります。実測は下の (3)）
    窓          齢 `lo`〜`hi` の点を **1点でも持つ**本だけ（持たない本は「答えられない」ので外す）
    A / B       その窓の読みの**最大**が 0回 より上なら A・0回 のままなら B
    最終        その本の全部の点の**最大**（旧データに包絡は無いので最大で代える）
    初点        初めて 0回 でなくなった点の齢（**B の本にだけ意味がある数**）

**この回に撃った下敷き**（齢 8〜12h・帯 09〜13時。**旧データは凍結 ＝ この数は動きません**）:

    窓の点を持つ本 **60本**
    A（窓で再生が付いていた） **57本**  中央 **266回**・最大 1891回・100回超 **47本(82%)**・最後まで 0回 **0本**
    B（窓でも 0回）           **3本**   中央 1回・最大 **275回**・100回超 1本・最後まで 0回 0本
    B の初点                  **45.0h・77.1h・77.6h**（`_Mz5rg6jQ_A` 275回・`mULv9y-sTOo` 1回・`5Rn6skMzyjo` 1回）

**＝ §7 (c) の「齢 24h の点で読む」は、この下敷きでは何も分けません** ——
**下敷きの 3本 は 3本とも 24h の時点で 0回**で、そのうち 1本 はそのあと 275回 まで行きました。
分かれ目が在るのは **齢 45〜78h** の側です。**24h の 0回 を「終わり」と読まないこと。**
（逆向きは強く言えます: **窓で再生が付いていた 57本 に、最後まで 0回 だった本は 1本もありません**）

**覆る条件**:
(1) 5本目 が **齢 45h より前**に 1回目を取ったら、下敷きの「B の初点は 45h 以降」は 3本 で作った線なので引かれる
    ＝ そのときは B の初点の下端をこの本で置き直すこと。
(2) 旧データの 0回 に **`viewCount` の欄が無い読み**（§6 `yt.views_of` の族）が混ざっていたら B は水増しです。
    **B の 3本 は最後の点（齢 410h）まで 1回・1回・275回**なので、欄の話では説明が付きません
    —— ただし `--all-hours` の側の 25本 には、この検めを当てていません。
(3) **帯で絞らないと数が変わります**（撃って確かめた）: `--all-hours` の B は **25本**で、
    そのうち **19本 は 14時以降 か 刻が不明**。**帯を混ぜた数を §7 に写さないこと。**
(4) 新しい作りの本が 7本 たまったら、下敷きを旧データではなく**新しい作りの側**で取り直すこと
    （いまは新しい作りに B が 1本（5本目）しか無い ＝ 下敷きにならない）。
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import json
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VIEWS = ROOT / "data" / "views.jsonl"
UPLOADED = ROOT / "data" / "uploaded.jsonl"
LEDGER = ROOT / "data" / "studio" / "ledger.jsonl"

BAND = (9, 13)      # §1 の表の帯（JST の公開の刻）
LO, HI = 8.0, 12.0  # 既定の齢の窓（いまの 5本目 が居る所）


def _rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def series(rows: list[dict]) -> dict[str, list[tuple[float, int]]]:
    """`data/views.jsonl` を 本ごとの `(齢, 再生)` の並びにする（齢の順）。"""
    pts: dict[str, list[tuple[float, int]]] = collections.defaultdict(list)
    for r in rows:
        if isinstance(r.get("views"), int) and isinstance(r.get("hours"), (int, float)) and r.get("id"):
            pts[r["id"]].append((float(r["hours"]), r["views"]))
    return {k: sorted(v) for k, v in pts.items()}


def published_jst(rows: list[dict]) -> dict[str, dt.datetime]:
    """`data/uploaded.jsonl` の `at`（UTC・公開の刻）を JST にする。`at` が無い本は入れない。"""
    out = {}
    for r in rows:
        vid, at = r.get("video_id"), r.get("at")
        if vid and at:
            out[vid] = dt.datetime.fromisoformat(at.replace("Z", "+00:00")) + dt.timedelta(hours=9)
    return out


def split(pts: dict[str, list[tuple[float, int]]], pub: dict[str, dt.datetime],
          lo: float = LO, hi: float = HI, band: tuple[int, int] | None = BAND) -> dict:
    """窓 `lo`〜`hi` の点を持つ本を **A（再生が付いていた）/ B（0回 のまま）** に割る。"""
    A: list[dict] = []
    B: list[dict] = []
    for vid, ps in pts.items():
        if band is not None:
            t = pub.get(vid)
            if t is None or not (band[0] <= t.hour <= band[1]):
                continue
        win = [v for h, v in ps if lo <= h <= hi]
        if not win:
            continue
        pos = [h for h, v in ps if v > 0]
        item = {"id": vid, "final": max(v for _, v in ps), "first_pos_h": (min(pos) if pos else None),
                "last_h": max(h for h, _ in ps), "hour": (pub[vid].hour if vid in pub else None)}
        (A if max(win) > 0 else B).append(item)
    return {"lo": lo, "hi": hi, "band": band, "A": sorted(A, key=lambda d: -d["final"]),
            "B": sorted(B, key=lambda d: -d["final"])}


def summary(group: list[dict]) -> dict:
    """群の 本数・中央・最大・100回超・最後まで 0回。**空の群でも落ちないこと**（下敷きは細い）。"""
    vs = sorted(g["final"] for g in group)
    return {"n": len(vs), "median": (st.median(vs) if vs else None), "max": (max(vs) if vs else None),
            "over100": sum(1 for v in vs if v >= 100), "zero": sum(1 for v in vs if v == 0)}


def standing(ledger: list[dict], lo: float = LO) -> list[dict]:
    """**いまの本の立ち位置** —— 台帳の `measured` の**いちばん新しい行**が 0回 で、齢が `lo` を越えた本。"""
    last: dict[str, dict] = {}
    for r in ledger:
        if r.get("event") == "measured" and r.get("id") and isinstance(r.get("views"), int):
            last[r["id"]] = r
    return sorted(({"id": vid, "age_h": r.get("age_h"), "title": r.get("title")}
                   for vid, r in last.items()
                   if r["views"] == 0 and isinstance(r.get("age_h"), (int, float)) and r["age_h"] >= lo),
                  key=lambda d: d["age_h"] or 0)


def report(lo: float = LO, hi: float = HI, band: tuple[int, int] | None = BAND) -> str:
    pts = series(_rows(VIEWS))
    pub = published_jst(_rows(UPLOADED))
    g = split(pts, pub, lo, hi, band)
    a, b = summary(g["A"]), summary(g["B"])
    where = f"帯 {band[0]:02d}〜{band[1]:02d}時 JST 公開" if band else "**帯で絞っていない**（(3)）"
    out = [f"**0回 のまま始まった本**（旧データ・凍結。窓 齢 {lo:g}〜{hi:g}h・{where}・API 0単位）",
           f"  窓の点を持つ本 **{a['n'] + b['n']}本**"]
    for name, s in (("A 窓で再生が付いていた", a), ("B 窓でも 0回      ", b)):
        if s["n"] == 0:
            out.append(f"  {name}: **0本** —— この窓では下敷きになりません")
            continue
        out.append(f"  {name}: **{s['n']}本**  中央 **{s['median']:.0f}回**・最大 {s['max']}回・"
                   f"100回超 {s['over100']}本・最後まで 0回 **{s['zero']}本**")
    if g["B"]:
        firsts = [x["first_pos_h"] for x in g["B"] if x["first_pos_h"] is not None]
        out.append("  B の初点（初めて 0回 でなくなった齢）: "
                   + ("・".join(f"{h:.1f}h" for h in sorted(firsts)) if firsts else "**1本も付いていません**"))
        for x in g["B"]:
            out.append(f"    {x['id']}  最終 {x['final']}回／初点 "
                       + (f"{x['first_pos_h']:.1f}h" if x["first_pos_h"] is not None else "なし")
                       + f"（最後の点 {x['last_h']:.1f}h）")
        if firsts and min(firsts) > hi:
            out.append(f"  **＝ この下敷きでは、齢 {hi:g}h の 0回 は「終わり」を言いません** ——"
                       f" B の初点は どれも **{min(firsts):.1f}h より後**です")
    if b["n"] and a["zero"] == 0:
        out.append("  **逆向きは言えます**: 窓で再生が付いていた本に、最後まで 0回 だった本は **1本もありません**")
    now = standing(_rows(LEDGER), lo)
    out.append(f"  **いま 0回 のまま 齢 {lo:g}h を越えている本: {len(now)}本**"
               + ("" if now else "（＝ この行は、次にそういう本が出た周に効きます）"))
    for x in now:
        out.append(f"    {x['id']}  齢 {x['age_h']:.1f}h  {x['title'] or ''}")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser(description="0回 のまま始まった本は、そのあと伸びるか（API 0単位）")
    ap.add_argument("--lo", type=float, default=LO)
    ap.add_argument("--hi", type=float, default=HI)
    ap.add_argument("--all-hours", action="store_true", help="公開の刻の帯で絞らない（(3) を読むこと）")
    a = ap.parse_args()
    print(report(a.lo, a.hi, None if a.all_hours else BAND))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
