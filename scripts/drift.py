#!/usr/bin/env python3
"""**この輪が目標から外れていないかを、毎周ひとつの数で出す。**

## なぜ要るのか（2026-08-24。オーナー指摘「なんで実験そんな少ないの？」）

手で数えたら、こうでした:

    8/18以降の ship 240件   fix 115 ／ means 44 ／ upload 26 ／ **verdict 14**
    closes を宣言              26件
    moves を宣言 82件 …… うち **0以外は 17件**

**240回のうち223回が「この回で到達日は動かない」と自分で言いながら通っていました。**

そして `eta.py` は毎回こう印字しています ——
**「作る・出す・直すは、軌跡の入力に入りません。軌跡の腕が動くのは、
`config/hypotheses.yaml` の前提を1件閉じたときだけ」。**

**機械は「何が目標を動かすか」を既に知っている。門がそれを読んでいなかった。**
`stop_check.sh` は「1件出せば通す」で、`fix` はその回のうちに必ず完結するので
**いちばん安い。** 実験は16本作って2週間待たないと1件も閉じません。
**同じ「1件」なら `fix` を選ぶのが合理的で、実際そうなっていました。**
サボりではなく、**合格の定義が目標とつながっていなかった**だけです。

## この道具がやること

**比を印字するだけです。** 判断はしません ——
**印字されていない数字は、無い数字と同じ**だからです（このリポジトリは
`retention.py` で同じ穴を踏んでいる。10日間ずっと正しく印字していたのに、
その道具を走らせた回にしか届かなかった）。

`--gate` を付けると、**厳しい1条件のときだけ** exit 2 を返します:

    期限の来た前提がある、**かつ** 直近 STALE_ROUNDS 回に verdict が1件も無い

**`fix` を禁じてはいけません。** 壊れた計器で実験しても答えは出ないので、
直すこと自体は正しい。**上の条件は「直すのはいいが、期限の来た問いを
置き去りにしたまま直し続けるのはだめ」**という形にしてあります。

**覆る条件**: 実験の律速が動機ではなく**供給**（1つのA/Bに16本要るのに
日に4本しか作れない）だと分かったら、この門は効きません。そのときは
ここではなく `topic_forge` 側 —— **「節を書く」を実験に紐づいた成果に
格上げすること。** 2026-08-28 の `day_cap` 判定が、その切り分けになります。
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "runs.jsonl"
HYPS = ROOT / "config" / "hypotheses.yaml"

WINDOW_DAYS = 7
STALE_ROUNDS = 20
KINDS = ("upload", "means", "verdict", "fix")


def _kind_of(what: str) -> str:
    """ship の1行から種別を読む。**先頭の語だけを見ます。**

    `--ship "fix: ..."` の形が慣習で、`run_marker.py` は種別を別欄に
    持っていません。**欄を足すのが本筋ですが、既存の240件を読めなくなる**ので、
    ここは既にある書き方から読みます。
    """
    head = (what or "").strip().lower()
    for k in KINDS:
        if head.startswith(k):
            return k
    return "その他"


def load_runs(since: str | None = None) -> list[dict]:
    if not RUNS.exists():
        return []
    out = []
    for ln in RUNS.read_text(encoding="utf-8").splitlines():
        if not ln.strip():
            continue
        try:
            r = json.loads(ln)
        except Exception:
            continue
        if r.get("kind") != "ship":
            continue
        if since and str(r.get("at", "")) < since:
            continue
        out.append(r)
    return out


def overdue(today: str) -> list[dict]:
    """期限が来ていて、まだ閉じていない前提。"""
    try:
        import yaml
    except ImportError:
        return []
    if not HYPS.exists():
        return []
    try:
        d = yaml.safe_load(HYPS.read_text(encoding="utf-8"))
    except Exception:
        return []
    rows = d if isinstance(d, list) else (d.get("hypotheses") or next(iter(d.values()), []))
    out = []
    for h in rows or []:
        if not isinstance(h, dict):
            continue
        # **鍵があるかどうかで見ます。値の真偽で見ないこと。**
        # `verdict: false` は「前提が外れた」＝**閉じている**という意味で、
        # Python の偽値と衝突します。2026-08-24、検査がここを捕まえました
        # （`test_閉じた前提は期限切れに数えない`）。**外れた前提こそ、
        # いちばん価値のある判定**なので、これを未判定に数えると
        # 「ちゃんと判定した回」を外れ扱いにして止めることになります。
        if any(k in h for k in ("verdict", "closed_on", "outcome")):
            continue
        dl = str(h.get("deadline") or h.get("settle_by") or "")
        if dl and dl <= today:
            out.append(h)
    return out


def report(today: str, window_days: int = WINDOW_DAYS) -> tuple[str, bool]:
    """印字する本文と、「外れている」かどうかを返す。"""
    since = (date.fromisoformat(today) - timedelta(days=window_days)).isoformat()
    runs = load_runs(since)
    n = len(runs)
    kinds = Counter(_kind_of(r.get("what", "")) for r in runs)
    closes = sum(1 for r in runs if r.get("closes"))
    declared = sum(1 for r in runs if r.get("moves") is not None)
    nonzero = sum(1 for r in runs if r.get("moves"))

    # 直近 STALE_ROUNDS 回に verdict があるか（窓ではなく件数で見る）
    all_runs = load_runs()
    tail = all_runs[-STALE_ROUNDS:]
    verdicts_tail = sum(1 for r in tail if _kind_of(r.get("what", "")) == "verdict")

    od = overdue(today)
    drifting = bool(od) and verdicts_tail == 0

    lines = [
        "=== この輪は目標に向かっているか（直近 %d日 / ship %d件）===" % (window_days, n),
    ]
    if n:
        parts = " ／ ".join(f"{k} {kinds.get(k, 0)}" for k in KINDS)
        lines.append(f"  種別: {parts} ／ その他 {kinds.get('その他', 0)}")
        lines.append(
            f"  到達日を動かすと宣言した回: **{nonzero}/{n}**"
            f"（moves を書いた回 {declared}／前提を閉じた宣言 {closes}）"
        )
    else:
        lines.append("  この窓に ship がありません。")

    lines.append(f"  直近{STALE_ROUNDS}回の verdict: **{verdicts_tail}件**")
    if od:
        lines.append(f"  **期限の来た前提: {len(od)}件**")
        for h in od[:5]:
            claim = str(h.get("claim") or h.get("q") or "")[:64]
            lines.append(f"    {h.get('deadline', '?')}  {claim}")
    else:
        lines.append("  期限の来た前提: なし")

    lines.append("")
    if drifting:
        lines.append(
            "  [!] **外れています。** 期限の来た前提があるのに、"
            f"直近{STALE_ROUNDS}回で1件も判定していません。"
        )
        lines.append(
            "      `eta.py` は「作る・出す・直すは軌跡の入力に入らない。"
            "動くのは前提を1件閉じたときだけ」と印字しています。"
        )
        lines.append("      **この回は verdict を出すこと。** 出せないなら理由を JOURNAL に。")
    else:
        lines.append("  外れの条件（期限切れの前提 かつ 判定ゼロ）には当たっていません。")

    return "\n".join(lines), drifting


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", action="store_true",
                    help="外れているとき exit 2（stop フックから読む用）")
    ap.add_argument("--today", default=None, help="基準日（検査用）")
    ap.add_argument("--window", type=int, default=WINDOW_DAYS)
    a = ap.parse_args(argv)
    today = a.today or datetime.now().date().isoformat()
    text, drifting = report(today, a.window)
    print(text)
    return 2 if (a.gate and drifting) else 0


if __name__ == "__main__":
    sys.exit(main())
