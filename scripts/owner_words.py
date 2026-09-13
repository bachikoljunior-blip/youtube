#!/usr/bin/env python3
"""オーナーの「分かりにくい」の**連を数える**（API 0単位・`data/inbox.jsonl` の字だけ）。

    python scripts/owner_words.py            # いまの連と、言葉の並び
    python scripts/owner_words.py --days 21  # さかのぼって見る日数（既定 21）

**なぜ置いたか**（2026-09-13 14:0x JST・optimizer・Opus）:
オーナーは **2026-09-10 から 4日 続けて**「説明が分かりにくい／話がつかめない」と言っています。
その 3回（09/10・09/11・09/12）に対して、こちらは**毎回 `docs/METHOD.md` §3 に規則を 1つ 足して**
います（09/10 → 7-b 板と札／09/11 → 7-c しくみ／09/12 → 12 順）。
**それでも翌日、同じ族の言葉が来ています（3/3）。**
オーナー自身が 09/11 19:2x に **「今回だけ教えてもまたおんなじことになるだろ」**（`10f70f79`）と
言っており、**この手が効いているかどうかを数える口が、どこにもありませんでした**
＝ この repo でいちばん多い壊れ方（**「N回 続いたら」と書いて N を数える物が無い**）の族です
（`trend.views_streak`・`late_run`・`blind_run`・`reporting_empty_run`・`outside_runs`・
`feature_cohorts`・`shape_run`・`turf_run` …）。derivation は `docs/JOURNAL.md` 09/13 14:0x。

**この道具は判定しません。** 数を並べるだけです ——
**「形を変えるか」の判定は台本を持つ `hourly` とオーナー**（`docs/METHOD.md` §5・§7）。

**数え方**（変えるときは、この註と一緒に検査 `tests/test_owner_words.py` も直すこと）:

    札           `CLARITY_IDS`（下）に挙げた受け取り帳の id だけを「分かりにくさの言葉」として数える。
                 **語では拾いません** —— 実測: 「説明が」で引くと `f3edb61f`（説明した方が）と
                 `3f4ef885`（説明の解釈）が落ち、「説明」だけで引くと道具の話（分かりやすさループ）まで
                 拾います。**分類は判断なので、字ではなく id で置く**（オーナーの言葉は 38件 しかない）。
    日           JST の日付。**オーナーが 1言も言わなかった日は、連を伸ばしも切りもしません**
                 —— 沈黙は「分かりやすかった」の証拠ではないからです（`voice_runs` と同じ規則）。
    連           いちばん新しくオーナーが言った日から さかのぼって、**言った日のうち**
                 分かりにくさの言葉が在った日が何日 続いているか。
    未分類        いちばん新しい分かりにくさの言葉より**後**のオーナーの言葉。
                 **毎周 ここを読むこと** —— 新しい言葉が族に入るなら `CLARITY_IDS` に足す
                 （足さないと、この連は黙って古くなります ＝ §5 教訓の形 7つ目・17つ目）。

**門: 3日**（＝ 手を打った翌日に同じ族が来た回が 3回 続いたら、その手はこの口では効いていない）。
**引かれたときの当て先は §3 の規則ではありません** —— 規則を足す手そのものが分子だからです。

**覆る条件**:
 (1) 連が切れたら（オーナーが言った日に分かりにくさの言葉が 0件）、**その日に何を変えたか**を
     JOURNAL に書くこと。切れた回が 2回 出たら、この門は「効く手が在る」を示せた ＝ 門を 5日 へ上げてよい。
 (2) `CLARITY_IDS` に足すか迷う言葉が 2件 続いたら、族の切り方が粗い
     ＝ 「読み（TTS）」「画面」「言い回し」で札を割ること（いまは 1つ の族）。
 (3) オーナーが「もう分かりやすい」と言ったら、その言葉が正本 ＝ この道具ごと畳んでよい。
 (4) この連が引かれたまま **7日** 動かなかったら、数えているのは手の効きではなく
     **オーナーが毎日 見ている**という事実のほう ＝ 分母を「日」から「本」へ移すこと。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "data" / "inbox.jsonl"
JST = timezone(timedelta(hours=9))

#: 門（日）。§5 の「N回目」と同じ形 —— 引かれたら JOURNAL に刻むこと。
GATE = 3

#: **分かりにくさの言葉**（受け取り帳の id → 一言）。
#: 足すときの線: **その本を見た人が「話が追えない」と言っている**もの。
#: 道具・枠・模型・読み（TTS の誤読）そのものの話は入れない（(2) の覆る条件で割る）。
CLARITY_IDS: dict[str, str] = {
    "7a024c76": "2026-08-27 まず何言ってるか分かんない（旧作り）",
    "dd918e3f": "2026-09-05 何言ってるかわかんない動画ばっか → METHOD をゼロから組み直した",
    "0bd45ff7": "2026-09-06 ナレーションも文脈が全然追えない",
    "552fadf1": "2026-09-10 事実なのか前提なのか分かるように → §3 7-b（札）",
    "52f141fa": "2026-09-10 画面を有効活用できてない・整理しながら理解するのむずい → §3 7-b（板）",
    "3f4ef885": "2026-09-11 説明の解釈が誤解されないように → §2 の直す順・§4 (2)",
    "f3edb61f": "2026-09-11 制度の仕組みは説明した方が良くない？ → §3 7-c（しくみ）",
    "b8dab27b": "2026-09-12 説明が全体を通して分かりづらい → §3 12（順）",
    "2e87f87e": "2026-09-13 説明不足があると思うな。話がつかめない",
}

#: オーナー自身が、この輪について言った言葉（分子には数えない・読む側の材料）。
LOOP_ID = "10f70f79"


def owner_rows(path: Path | None = None) -> list[dict]:
    """受け取り帳のうち `source == "owner"` の行（古い順）。"""
    p = path or INBOX
    if not p.exists():
        return []
    out = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("source") != "owner" or not r.get("at"):
            continue
        out.append(r)
    out.sort(key=lambda r: r["at"])
    return out


def _day(row: dict) -> str:
    return datetime.fromisoformat(row["at"]).astimezone(JST).strftime("%Y-%m-%d")


def days(rows: list[dict]) -> list[tuple[str, list[dict], list[dict]]]:
    """(日, その日のオーナーの言葉, そのうち分かりにくさの言葉) を古い順に。"""
    order: list[str] = []
    byday: dict[str, list[dict]] = {}
    for r in rows:
        d = _day(r)
        if d not in byday:
            byday[d] = []
            order.append(d)
        byday[d].append(r)
    return [(d, byday[d], [r for r in byday[d] if r.get("id") in CLARITY_IDS]) for d in order]


def streak(rows: list[dict]) -> dict:
    """連（オーナーが言った日だけを数える。沈黙の日は伸ばしも切りもしない）。"""
    ds = days(rows)
    run = 0
    for _d, _all, hits in reversed(ds):
        if not hits:
            break
        run += 1
    silent = 0
    if run:
        first = datetime.strptime(ds[-run][0], "%Y-%m-%d")
        last = datetime.strptime(ds[-1][0], "%Y-%m-%d")
        silent = (last - first).days + 1 - run
    return {
        "run": run,
        "gate": GATE,
        "drawn": run >= GATE,
        "silent_in_run": silent,
        "spoke_days": len(ds),
        "clarity_days": sum(1 for _d, _a, h in ds if h),
    }


def unclassified(rows: list[dict]) -> list[dict]:
    """いちばん新しい分かりにくさの言葉より後の、まだ札の無いオーナーの言葉。"""
    last = None
    for r in rows:
        if r.get("id") in CLARITY_IDS:
            last = r["at"]
    if last is None:
        return [r for r in rows if r.get("id") not in CLARITY_IDS]
    return [r for r in rows if r["at"] > last and r.get("id") not in CLARITY_IDS]


def run(days_back: int = 21, path: Path | None = None) -> dict:
    rows = owner_rows(path)
    cut = (datetime.now(JST) - timedelta(days=days_back)).isoformat()
    recent = [r for r in rows if r["at"] >= cut]
    res: dict = {"rows": rows, "recent": recent, "unclassified": unclassified(rows), **streak(rows)}
    res["quiet_h"] = (
        (datetime.now(JST) - datetime.fromisoformat(rows[-1]["at"]).astimezone(JST)).total_seconds() / 3600
        if rows else None
    )
    return res


def line(res: dict | None = None) -> str:
    res = run() if res is None else res
    head = (
        "オーナーの「分かりにくい」の連: "
        f"**{res['run']}日**（門 {res['gate']}日・**オーナーが言った日だけを数える**）"
        f" ＝ **{'引かれました' if res['drawn'] else 'まだ引けません'}**"
        f"（言った日 {res['spoke_days']}日 のうち この族が在った日 {res['clarity_days']}日・"
        f"連の中の沈黙 {res['silent_in_run']}日）"
    )
    body = [
        f"  {CLARITY_IDS[r['id']]}  `{r['id']}`"
        for r in res["rows"] if r.get("id") in CLARITY_IDS
    ]
    tail = []
    if res["unclassified"]:
        tail.append("  **まだ札の無い、より新しいオーナーの言葉**（族に入るなら `CLARITY_IDS` に足すこと）:")
        tail += [f"    {r['at'][:16]} `{r.get('id')}` {r.get('text','')[:60]}" for r in res["unclassified"]]
    else:
        tail.append("  まだ札の無い、より新しいオーナーの言葉: **0件**")
    if res["quiet_h"] is not None:
        tail.append(f"  いちばん新しいオーナーの言葉から **{res['quiet_h']:.1f}時間**"
                    "（**沈黙は「分かりやすかった」ではありません** ＝ 連は動きません）")
    tail.append(
        "  **この道具は判定しません** —— 数を並べるまでです。**「形を変えるか」の判定は "
        "`hourly` とオーナー**（METHOD §5・§7）。**引かれたときの当て先は §3 の規則ではありません** "
        "—— 規則を足す手そのものが分子です（この道具の註）"
    )
    return "\n".join([head, *body, *tail])


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=21)
    a = ap.parse_args()
    print(line(run(a.days)))
