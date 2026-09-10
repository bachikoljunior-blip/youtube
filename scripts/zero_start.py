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
(5) **尺を混ぜないこと**（2026-09-11 08:0x・optimizer・Opus。**この回に踏んだ**）:
    20:0x の形は「いま 0回 のまま」の本を**尺を混ぜて 1つの列**に並べており、実物は
    **91秒・314.9秒・1580.0秒 の 3本**でした。**下 2本 は Shorts フィードに乗らない尺**で、
    §1 の「長尺は 1〜25回」で説明が付きます（`SHORT_MAX_S`）。混ぜたまま数えると
    「0回 の本が 3本 も在る ＝ 配りが止まった」と読めます。**下敷きが答えられるのはショートだけ。**
    いまは尺で分けて印字し、ショートだけを下敷きの初点の下端（45.0h）／上端（77.6h）に当てます。
    **下敷きの側の尺は測れていません** —— 60本 のうち `duration_s` が在るのは **5本** だけ
    （中央 27.3秒・最大 303.0秒・180秒 超 1本）。
    **【2026-09-11 08:3x に 2つ目の口で埋めました】向き**（`data/critique_queue` の `orientation`）は
    **58/60 に在り、58本 とも `縦`・`横` は 0本**（残り 2本 は控えが無い）＝ **下敷きは縦だけで出来ています**。
    そして いま 0回 のまま並ぶ旧作りの 2本 は **どちらも `横`** ＝ 尺の側（1580.0秒・314.9秒）と
    **同じ答えを、別の口が返しました**（§5 の教訓の形1つ目 ＝ 足す前に「違う物を見ているか」を確かめる。
    尺は 60本 中 5本・向きは 58本 ＝ **別の物を見ています**）。
    いまは **尺 が上限を越える か 向きが `横`** で「下敷きの外」に落とします（`standing`）。
    **覆る条件**: (a) 旧データの尺が別の口から埋まったら（873本 中 353本 に `duration_s` が在る）、
    下敷きの側も `SHORT_MAX_S` で絞って取り直すこと ——そのとき B の 3本 が長尺なら、
    上の「B の初点は 45h 以降」ごと引かれます。(b) **studio の本には控えが無い**ので、
    向きの口は旧作りにしか答えません ——`縦` が無いことを「横だ」と読まないこと。
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


SHORT_MAX_S = 180.0
"""**ショートの上限（秒）。** これを越える本は Shorts フィードに乗らない ＝ §1 の
「長尺は 1〜25回」の側で、**この下敷きに当てて読めません**。"""

QUEUE = ROOT / "data" / "critique_queue"
"""旧道具が本ごとに残した控え（**過去のデータ** ＝ §8 の「使わない道具」ではない）。
`orientation`（縦／横）が **2,714本** に在り、尺が書かれていない本の**向き**を言います。"""


def shapes(ids: list[str] | None = None) -> dict[str, str]:
    """id → 向き（`縦`／`横`）。**分かる本だけ**。API 0単位・ファイルを読むだけ。

    **なぜ2つ目の口が要ったか**（2026-09-11 08:3x・optimizer・Opus）:
    08:0x は尺（`duration_s`）だけで群を分け、**下敷き 60本 のうち尺が分かるのは 5本**
    だったので「下敷きはショートだけと読まないこと」としか言えませんでした。
    向きは **58/60 に在り、58本 とも `縦`・`横` は 0本**（残り 2本 は控えが無い）＝
    **下敷きは縦だけで出来ています**。そして いま 0回 のまま並ぶ旧作りの 2本
    （`fMlY_uzHOMw`・`m7BRQs9X6Jc`）は **どちらも `横`** ＝ 尺の側（1580.0秒・314.9秒）と
    **同じ答え**を、別の口が返しました（§5 の教訓の形1つ目 ＝ 2つ目の口は違う物を見ているか）。

    **覆る条件**: studio の本には控えが無い（この口は旧作りにしか答えません）ので、
    **`縦` が無いことを「横だ」と読まないこと**。新しい作りの向きは 台帳 `built` の側
    （1080×1920 固定）で、**尺のほうで分けます**。
    """
    if not QUEUE.is_dir():
        return {}
    out: dict[str, str] = {}
    for vid in (ids if ids is not None else [p.stem for p in QUEUE.glob("*.json")]):
        p = QUEUE / f"{vid}.json"
        if not p.is_file():
            continue
        try:
            v = json.loads(p.read_text(encoding="utf-8")).get("orientation")
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(v, str) and v.strip():
            out[vid] = v.strip()
    return out


def durations(uploaded: list[dict], ledger: list[dict]) -> dict[str, tuple[float, str]]:
    """id → （尺の秒, 出どころ）。**分かる本だけ**（分からない本は入れない）。API 0単位。

    2つの口から拾う（どちらも repo の中）:
      * `data/uploaded.jsonl` の `duration_s`（旧道具が上げたときに書いた秒。873本 中 **353本**）
      * 台帳 `scheduled`（video_id ↔ 台本の id）→ 台帳 `built` の `seconds`（studio の本）

    **なぜ要るか**（2026-09-11 08:0x・optimizer・Opus。この回に踏んだ）:
    `standing()` は「いま 0回 のまま」の本を**尺を混ぜて 1つの列**に並べており、
    実物の 3本 は **91秒（studio の 5本目）・314.9秒・1580.0秒** でした。
    下 2本 は Shorts フィードに乗らない本で、**§1 の「長尺は 1〜25回」で説明が付きます**。
    列を混ぜたまま読むと「0回 の本が 3本 も在る」＝ 配りが止まった、と読めてしまいます。
    """
    out: dict[str, tuple[float, str]] = {}
    for r in uploaded:
        vid, d = r.get("video_id"), r.get("duration_s")
        if vid and isinstance(d, (int, float)):
            out[vid] = (float(d), "uploaded.jsonl")
    built: dict[str, float] = {}
    sched: dict[str, str] = {}
    for r in ledger:
        if r.get("event") == "built" and r.get("id") and isinstance(r.get("seconds"), (int, float)):
            built[r["id"]] = float(r["seconds"])
        elif r.get("event") == "scheduled" and r.get("id") and r.get("video_id"):
            sched[r["video_id"]] = r["id"]
    for vid, script_id in sched.items():
        if script_id in built:
            out[vid] = (built[script_id], "台帳 built")
    return out


def standing(ledger: list[dict], lo: float = LO,
             durs: dict[str, tuple[float, str]] | None = None,
             shape: dict[str, str] | None = None) -> list[dict]:
    """**いまの本の立ち位置** —— 台帳の `measured` の**いちばん新しい行**が 0回 で、齢が `lo` を越えた本。

    **尺と向きも一緒に返すこと**（`durations` / `shapes` の註）—— 下敷き（旧データ）は
    **縦だけ**で出来ているので、`SHORT_MAX_S` を越える本 **または `横` の本**は
    「下敷きの外」として読む側に渡します（`long` が True）。
    **どちらも分からない本は `long` が None**（「短い」と決めつけない）。
    """
    durs, shape = durs or {}, shape or {}
    last: dict[str, dict] = {}
    for r in ledger:
        if r.get("event") == "measured" and r.get("id") and isinstance(r.get("views"), int):
            last[r["id"]] = r
    out = []
    for vid, r in last.items():
        if r["views"] != 0 or not isinstance(r.get("age_h"), (int, float)) or r["age_h"] < lo:
            continue
        sec, src = durs.get(vid, (None, None))
        ori = shape.get(vid)
        if sec is not None:
            long_ = sec > SHORT_MAX_S or ori == "横"
        else:
            long_ = True if ori == "横" else None
        out.append({"id": vid, "age_h": r.get("age_h"), "title": r.get("title"),
                    "seconds": sec, "dur_src": src, "orientation": ori, "long": long_})
    return sorted(out, key=lambda d: d["age_h"] or 0)


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
    up_rows, led_rows = _rows(UPLOADED), _rows(LEDGER)
    durs = durations(up_rows, led_rows)
    base_ids = [x["id"] for x in g["A"]] + [x["id"] for x in g["B"]]
    now0 = standing(led_rows, lo)
    shape = shapes(base_ids + [x["id"] for x in now0])
    out.extend(_base_length_line(g, durs, shape))
    out.extend(_standing_lines(standing(led_rows, lo, durs, shape), lo,
                               [x["first_pos_h"] for x in g["B"] if x["first_pos_h"] is not None]))
    return "\n".join(out)


def _base_length_line(g: dict, durs: dict[str, tuple[float, str]],
                      shape: dict[str, str] | None = None) -> list[str]:
    """**下敷きの側の尺と向き**を出す（`durations` / `shapes` の註）。
    **分かる本の数を必ず出すこと** —— 分からない本を「短い」と数えると、
    下敷きが絞れているように見えます。"""
    shape = shape or {}
    ids = [x["id"] for x in g["A"]] + [x["id"] for x in g["B"]]
    if not ids:
        return []
    secs = sorted(durs[i][0] for i in ids if i in durs)
    if not secs:
        out = ["  **この下敷きの尺は測れていません** —— "
               f"{len(ids)}本 のうち 尺 が分かる本は **0本**（`duration_s` が無い）"]
    else:
        out = ["  **この下敷きの尺は、ほとんど測れていません** —— "
               f"{len(ids)}本 のうち 尺 が分かるのは **{len(secs)}本** だけ"
               f"（中央 {st.median(secs):.1f}秒・最大 {max(secs):.1f}秒・"
               f"{SHORT_MAX_S:g}秒 超 {sum(1 for s in secs if s > SHORT_MAX_S)}本）"]
    tate = sum(1 for i in ids if shape.get(i) == "縦")
    yoko = sum(1 for i in ids if shape.get(i) == "横")
    unknown = len(ids) - tate - yoko
    if tate or yoko:
        verdict = ("**＝ この下敷きは縦だけで出来ています**" if yoko == 0
                   else "**＝ この下敷きは縦と横が混ざっています ＝ 横の本に当てて読まないこと**")
        out.append(f"  **向きは別の口が言います**（`data/critique_queue` の `orientation`）: "
                   f"縦 **{tate}本**・横 **{yoko}本**・控えなし {unknown}本 {verdict}")
    return out


def _standing_lines(now: list[dict], lo: float, firsts: list[float]) -> list[str]:
    """**いまの本の立ち位置**を、**尺で分けて**印字する（`durations` の註・2026-09-11 08:0x）。

    `SHORT_MAX_S` を越える本は **下敷きの外**（Shorts フィードに乗らない ＝ §1 の
    「長尺は 1〜25回」の側）。**この行を混ぜたまま「0回 が n本」と読まないこと。**
    ショートの側だけを、下敷きの初点の下端／上端に当てます。
    """
    out = [f"  **いま 0回 のまま 齢 {lo:g}h を越えている本: {len(now)}本**"
           + ("" if now else "（＝ この行は、次にそういう本が出た周に効きます）")]
    for x in now:
        sec = ("尺 不明" if x["seconds"] is None
               else f"{x['seconds']:.1f}秒（{x['dur_src']}）")
        ori = f"・{x['orientation']}" if x.get("orientation") else ""
        mark = "  ** **下敷きの外**（Shorts フィードに乗らない）" if x["long"] else ""
        out.append(f"    {x['id']}  齢 {x['age_h']:.1f}h  {sec}{ori}  {x['title'] or ''}{mark}")
    if not now:
        return out
    shorts = [x for x in now if x["long"] is False]
    longs = [x for x in now if x["long"] is True]
    if longs:
        why = "・".join(
            (("%.1f秒" % x["seconds"]) if x["seconds"] is not None else "尺 不明")
            + (f"／{x['orientation']}" if x.get("orientation") else "")
            for x in longs)
        out.append(f"  **この {len(now)}本 を 1つ に数えないこと** —— "
                   f"下敷きの外（{SHORT_MAX_S:g}秒 超 か 横）が **{len(longs)}本**"
                   f"（{why}）"
                   f" ＝ §1 の「長尺は 1〜25回」の側で、**この下敷きは答えません**。"
                   f" 下敷きが答えられるのは **ショート {len(shorts)}本**"
                   + ("" if shorts else "（＝ いまは 0本 ＝ この下敷きに当たる本が在りません）"))
    if shorts and firsts:
        lo_h, hi_h = min(firsts), max(firsts)
        over = [x for x in shorts if (x["age_h"] or 0) > hi_h]
        inside = [x for x in shorts if (x["age_h"] or 0) < lo_h]
        if over:
            out.append(f"  **下敷きの いちばん遅い初点 {hi_h:.1f}h を越えて 0回 のままのショートが "
                       f"{len(over)}本 在ります** ——（"
                       + "・".join(f"{x['id']} 齢 {x['age_h']:.1f}h ＝ +{(x['age_h'] - hi_h):.1f}時間"
                                   for x in over)
                       + "）**下敷きでは説明が付きません**（覆る条件 (5)）")
        else:
            out.append(f"  **下敷きの いちばん遅い初点 {hi_h:.1f}h を越えて 0回 のままのショートは 0本**"
                       f"（越えた回に、下敷きの外へ出ます ＝ 覆る条件 (5)）")
        if inside:
            out.append(f"  **まだ下敷きの中のショート {len(inside)}本**（初点の下端 {lo_h:.1f}h より手前 ＝ "
                       "**この齢の 0回 からは何も言えません**）: "
                       + "・".join(f"{x['id']} 齢 {x['age_h']:.1f}h" for x in inside))
    return out


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
