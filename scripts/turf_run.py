#!/usr/bin/env python3
"""§5 の「file ごとの取り分」の**覆る条件を数える**（API 0単位・git と repo の字だけ）。

    python scripts/turf_run.py             # いまの連と、数えた周の並び
    python scripts/turf_run.py --laps 30   # さかのぼって見る周の数

**なぜ道具にしたか**（2026-09-13 11:0x JST・optimizer・Opus）:
§5 の 2026-09-13 02:5x の段は、こう書いています ——
「**判定を持たない側が「その file の別の所」に手を入れて二重にならなかった回が 3回 続いたら、
この行は狭すぎる ＝ 「同じ関数だけ」へ緩めること**」。
**その「3回」を数える物が、どこにもありませんでした**（`trend.views_streak`・`late_run`・
`blind_run`・`reporting_empty_run`・`outside_runs`・`feature_cohorts`・`shape_run` と同じ族の **10例目**）。
数える物が無い条件は、次の回が手で数え直すか、数えずに素通りするかのどちらかになります
（族の 9例目 ＝ 09/13 10:1x の `shape_run` は、手で運んだ数が **24時間 で反転**していました）。

**数え方**（変えるときは、この註と一緒に検査 `tests/test_turf_run.py` も直すこと）:

    判定を持つ側    `docs/METHOD.md` の「判定は `hourly`」を含む**塊**（空行で区切った段）が
                    名指しした `studio/*.py`（`` `trend.late_gain` `` のような書き方も拾う）
    判定を持たない側 `optimizer`（上の塊が名指ししていない役）
    周              `data/rounds.jsonl` の `round`（**commit ではない** —— `method_growth` と同じ理由）
    役              commit の題の `<MM/DD HH:Mx> <役>:`（親の commit「周の台帳」「周の畳み」と merge は数えない）
    連の起点        `docs/METHOD.md` の「N回目の二重」のうち **N がいちばん大きい行の刻**
                    （＝ いちばん新しく記録された二重。新しい二重が §5 に書かれたら、連はそこから数え直す）
    数える周        起点より後の周のうち、**判定を持たない側が上の file に触れた周**だけ
                    （触れていない周は、連を伸ばしも切りもしません —— `voice_runs` と同じ規則）
    二重になり得た周 同じ周に**両方の役**が同じ file に触れた周（`!!` を付けて名指しする）。
                    **`!!` が付いていても、二重が起きたかは git では分かりません** ——
                    起きた回は §5 に「N回目の二重」として書かれ、そのとき起点が動きます

**門**: **3回**（§5 の 02:5x の段の覆る条件そのもの）。

**覆る条件**:
(1) `!!` の付いた周で二重が起きたのに §5 に書かれなかった回が出たら、起点の取り方が違う
    ＝ 起点を JOURNAL の側から取り直すこと。
(2) 「判定は `hourly`」の行が `studio/` 以外の file（`scripts/` や `docs/`）を名指しし始めたら、
    `judged_files()` の当たりを広げること（いまは `studio/*.py` だけ）。
(3) §5 が「同じ関数だけ」へ緩んだら、この道具は**関数の粒**で数え直すこと
    ＝ file の名では足りなくなる（そのときは点を 1点目から取り直す）。
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess

ROOT = pathlib.Path(__file__).resolve().parent.parent
METHOD = ROOT / "docs" / "METHOD.md"
ROUNDS = ROOT / "data" / "rounds.jsonl"
JST = dt.timezone(dt.timedelta(hours=9))
GATE = 3
JUDGE = "hourly"
OTHER = "optimizer"

# 親が押す commit（役の仕事ではない）。**merge も数えない。**
_PARENT_SUBJECTS = ("周の台帳", "周の畳み", "親の起き台帳", "Merge ")
_ROLE_RE = re.compile(r"\b(hourly|optimizer)\b\s*[:：]")
_DOUBLE_RE = re.compile(r"(\d+)\s*回目の二重")
_STAMP_RE = re.compile(r"(20\d\d-\d\d-\d\d)\s+(\d\d):(\d)x")


def studio_modules() -> set[str]:
    return {p.stem for p in (ROOT / "studio").glob("*.py") if p.stem != "__init__"}


def judged_files(text: str | None = None) -> set[str]:
    """「判定は `hourly`」を含む塊が名指しした `studio/*.py`。"""
    text = METHOD.read_text(encoding="utf-8") if text is None else text
    mods = studio_modules()
    out: set[str] = set()
    for block in re.split(r"\n\s*\n", text):
        if not re.search(r"判定は[^\n]{0,24}" + JUDGE, block):
            continue
        for m in re.finditer(r"`(?:studio/)?(\w+)(?:\.py|\.\w+)`", block):
            if m.group(1) in mods:
                out.add(f"studio/{m.group(1)}.py")
    return out


def last_double(text: str | None = None) -> dt.datetime | None:
    """§5 に記録された二重のうち、**N がいちばん大きい行の刻**（連の起点）。"""
    text = METHOD.read_text(encoding="utf-8") if text is None else text
    best: tuple[int, dt.datetime] | None = None
    for line_ in text.splitlines():
        m = _DOUBLE_RE.search(line_)
        s = _STAMP_RE.search(line_)
        if not m or not s:
            continue
        # `02:5x` は 10分 の幅。**幅の頭**を採る（その回の押しは必ずこれより後）。
        at = dt.datetime.strptime(f"{s.group(1)} {s.group(2)}:{s.group(3)}0", "%Y-%m-%d %H:%M")
        at = at.replace(tzinfo=JST)
        n = int(m.group(1))
        if best is None or n > best[0]:
            best = (n, at)
    return None if best is None else best[1]


def rounds(limit: int | None = None) -> list[dt.datetime]:
    seen: list[dt.datetime] = []
    for line_ in ROUNDS.read_text(encoding="utf-8").splitlines():
        if not line_.strip():
            continue
        r = json.loads(line_).get("round")
        if not r:
            continue
        at = dt.datetime.fromisoformat(r)
        if not seen or seen[-1] != at:
            seen.append(at)
    seen = sorted(set(seen))
    return seen if limit is None else seen[-limit:]


def _git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *args],
                          capture_output=True, text=True, check=True).stdout


def touches(since: dt.datetime, raw: str | None = None) -> list[tuple[dt.datetime, str, set[str]]]:
    """(刻, 役, 触った file) を**古い順**で返す。merge と親の commit は外す。"""
    if raw is None:
        raw = _git("log", "--no-merges", f"--since={since.isoformat()}",
                   "--name-only", "--pretty=format:%x00%aI%x01%s")
    out: list[tuple[dt.datetime, str, set[str]]] = []
    for chunk in raw.split("\x00"):
        if not chunk.strip():
            continue
        head, _, body = chunk.partition("\n")
        stamp, _, subject = head.partition("\x01")
        if any(subject.startswith(p) for p in _PARENT_SUBJECTS):
            continue
        m = _ROLE_RE.search(subject)
        if not m:
            continue
        files = {ln.strip() for ln in body.splitlines() if ln.strip()}
        out.append((dt.datetime.fromisoformat(stamp), m.group(1), files))
    return sorted(out, key=lambda t: t[0])


def marks_from(rs: list[dt.datetime],
               tt: list[tuple[dt.datetime, str, set[str]]],
               files: set[str]) -> list[dict]:
    """周ごとに、判定を持たない側が触れた judged file を並べる（**git を撃たない側**）。"""
    marks: list[dict] = []
    for i, r0 in enumerate(rs):
        r1 = rs[i + 1] if i + 1 < len(rs) else None
        by: dict[str, set[str]] = {}
        for at, role, fs in tt:
            if at < r0 or (r1 is not None and at >= r1):
                continue
            by.setdefault(role, set()).update(fs & files)
        mine = by.get(OTHER, set())
        if not mine:
            continue                      # 触れていない周は、連を伸ばしも切りもしない
        marks.append({"round": r0, "files": sorted(mine),
                      "both": sorted(mine & by.get(JUDGE, set()))})
    return marks


def run(laps: int = 40) -> dict:
    files = judged_files()
    start = last_double()
    rs = rounds(laps)
    if start is not None:
        rs = [r for r in rs if r >= start] or rs[-1:]
    tt = touches(rs[0]) if rs else []
    marks = marks_from(rs, tt, files)
    return {"start": start, "files": sorted(files), "marks": marks,
            "run": len(marks), "gate": GATE, "drawn": len(marks) >= GATE}


def line(res: dict | None = None) -> str:
    res = run() if res is None else res
    s = res["start"]
    head = (f"§5 の file ごとの取り分（02:5x の段）の連: **{res['run']}回**（門 {res['gate']}回）"
            f" ＝ **{'引かれました' if res['drawn'] else 'まだ引けません'}**"
            + (f"（起点 {s.astimezone(JST):%m/%d %H:%M} JST ＝ いちばん新しく記録された二重）"
               if s else "（起点なし ＝ 二重の記録が §5 に 1件も無い）"))
    body = [f"  {m['round'].astimezone(JST):%m/%d %H:%M} JST  "
            + "・".join(m["files"])
            + ("  !! 同じ周に両方が触れた: " + "・".join(m["both"]) if m["both"] else "")
            for m in res["marks"]]
    tail = ("  数えた file（「判定は `hourly`」が名指し）: " + "・".join(res["files"])
            + "\n  **`!!` は「二重が起きた」ではありません** —— 起きた回は §5 に「N回目の二重」"
              "として書かれ、そのとき起点が動きます（この道具の覆る条件 (1)）")
    return "\n".join([head, *body, tail])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--laps", type=int, default=40)
    a = ap.parse_args()
    print(line(run(a.laps)))
