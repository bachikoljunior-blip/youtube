#!/usr/bin/env python3
"""§5 の取り分の**いま生きている覆る条件を数える**（API 0単位・git と repo の字だけ）。

    python scripts/turf_run.py             # いまの連と、数えた周の並び
    python scripts/turf_run.py --laps 30   # さかのぼって見る周の数

**この道具が数えるのは §5 の覆る条件 (2)**（`!!` の連・門 3回）です。
**02:5x の「file ごとの取り分」の連（門 3回）は、2026-09-13 11:0x に引かれて閉じました**
（§5 は「同じ関数だけ」へ緩みました）＝ **ここではもう数えません。**

**なぜ書き直したか**（2026-09-13 13:0x JST・optimizer・Opus）:
11:0x に作ったこの道具は、**自分が引いた条件を、そのあとも毎周「引かれました」と印字し続けて**いました
（連 4回／門 3回）。**それは次の回に「まだ緩めろ」と言う印字**で、決めのほうは既に緩み終えています。
**§5 教訓の形 7つ目**（覆る条件を註に書いたら、その条件を読む印字も一緒に作ること ——
**註と印字が食い違えば、読まれるのは印字のほう**）の、**印字だけが古くなった側**です。
同時に、11:0x が §5 へ置いた**新しい**覆る条件 (2)（「`!!` が 3回 続き、そのどれも二重にならなかったら」）は、
**§5 が「`turf_run` の `!!`」と名指ししているのに、この道具が連を 1度も数えていませんでした**
＝ **数える物が無い条件**の族の **12例目**（`trend.views_streak`・`late_run`・`blind_run`・
`reporting_empty_run`・`outside_runs`・`feature_cohorts`・`shape_run`・11:0x のこの道具 …）。
**型**: **条件を引いた回が作る道具は、引いた側ではなく「引いたあとに残る側」を数えること。**

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
    数える連        **`!!` の付いた周が、末尾から何回 続いているか**（§5 の覆る条件 (2) の「3回 続き」）。
                    **`!!` の付かない周は、連を切ります** —— その周は「両方が同じ file に居たのに
                    二重にならなかった」の**反例ではなく、そもそも居合わせていない**からです。
                    触れていない周は marks に入らないので、伸ばしも切りもしません（`voice_runs` と同じ規則）。
                    **二重が起きた回は §5 に書かれ、起点が動く** ＝ 連はそこから 0 に戻ります。

**粒は file のまま**（§5 が「同じ関数だけ」へ緩んだあとも）: 覆る条件 (2) の `!!` は
§5 自身が「**同じ周に両方が同じ file へ触れた**」と定義しています ——
**関数の粒で数えるべきなのは「二重が起きたか」の側で、そちらは git では分からず §5 の字が持ちます**
（11:0x の覆る条件 (3)「関数の粒で数え直す」は、この定義に当てて**落としました**）。

**門**: **3回**（§5 の覆る条件 (2) そのもの）。引かれたときの当て先は**取り分ではなく申し送りの側**（§5）。

**覆る条件**:
(1) `!!` の付いた周で二重が起きたのに §5 に書かれなかった回が出たら、起点の取り方が違う
    ＝ 起点を JOURNAL の側から取り直すこと。
(2) 「判定は `hourly`」の行が `studio/` 以外の file（`scripts/` や `docs/`）を名指しし始めたら、
    `judged_files()` の当たりを広げること（いまは `studio/*.py` だけ。§5 の覆る条件 (3) と同じ物）。
(3) §5 が「同じ file の別の関数で二重」で **file の粒へ戻した**ら、そのとき §5 に書かれる
    「N回目の二重」で起点が動くので、この道具はそのまま使えます ——
    **書き換えが要るのは、§5 が `!!` の定義（同じ周・同じ file）を変えた回だけです。**
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


def bang_streak(marks: list[dict]) -> int:
    """**末尾から**続いている `!!`（同じ周に両方が同じ file へ触れた）の数 ＝ §5 の覆る条件 (2) の連。

    `!!` の付かない周は連を切る（そこは「居合わせたのに二重にならなかった」ではない）。
    """
    n = 0
    for m in reversed(marks):
        if not m["both"]:
            break
        n += 1
    return n


def verdict(marks: list[dict]) -> dict:
    """marks から**連・触れた周・引かれたか**を決める（**ここだけを検査で押さえる**）。

    **`drawn` は「触れた周」ではなく `!!` の連で決まる** —— 触れた周の数は
    02:5x の**閉じた**連で、いまの門ではありません。
    """
    streak = bang_streak(marks)
    return {"touched": len(marks), "run": streak, "gate": GATE, "drawn": streak >= GATE}


def run(laps: int = 40) -> dict:
    files = judged_files()
    start = last_double()
    rs = rounds(laps)
    if start is not None:
        rs = [r for r in rs if r >= start] or rs[-1:]
    tt = touches(rs[0]) if rs else []
    marks = marks_from(rs, tt, files)
    return {"start": start, "files": sorted(files), "marks": marks, **verdict(marks)}


def line(res: dict | None = None) -> str:
    res = run() if res is None else res
    s = res["start"]
    head = ("§5 の取り分（いまは **同じ関数だけ**）の覆る条件 (2) ——"
            f" `!!` の連: **{res['run']}回**（門 {res['gate']}回）"
            f" ＝ **{'引かれました' if res['drawn'] else 'まだ引けません'}**"
            + (f"（起点 {s.astimezone(JST):%m/%d %H:%M} JST ＝ いちばん新しく記録された二重・"
               f"そこから 判定を持たない側が触れた周 {res['touched']}つ）"
               if s else f"（起点なし ＝ 二重の記録が §5 に 1件も無い・触れた周 {res['touched']}つ）"))
    body = [f"  {m['round'].astimezone(JST):%m/%d %H:%M} JST  "
            + "・".join(m["files"])
            + ("  !! 同じ周に両方が触れた: " + "・".join(m["both"]) if m["both"] else "")
            for m in res["marks"]]
    tail = ("  数えた file（「判定は `hourly`」が名指し）: " + "・".join(res["files"])
            + "\n  **`!!` は「二重が起きた」ではありません** —— 起きた回は §5 に「N回目の二重」"
              "として書かれ、そのとき起点が動きます（この道具の覆る条件 (1)）。"
              "**引かれたときの当て先は、取り分ではなく申し送りの側**（§5）"
            + "\n  **02:5x の「file ごとの取り分」の連（門 3回）は 11:0x に引かれて閉じました** ＝ "
              "ここではもう数えません（上の「触れた周」は、その連が数えていた物と同じ数え方です）")
    return "\n".join([head, *body, tail])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--laps", type=int, default=40)
    a = ap.parse_args()
    print(line(run(a.laps)))
