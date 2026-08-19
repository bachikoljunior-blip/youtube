"""**予測日を動かす腕**の語彙と、その回がどれを選んだかの記録。

## なぜ要るか（2026-08-19 21:2x・オーナー指示）

オーナーの言葉（原文）: **「毎回達成までの予測して。20万の達成。それ以外のやつだけ
しかしてない。それを早めるための行動考えてから進めるのは毎回の最初にやること」**

裏を取りました。`data/eta.jsonl` の **18点は、入力が1つも動いていません** ——
`views_per_day` は 18点とも 1571.714…、`sub_rate` も 18点とも同値です。
そのあいだに回は18周まわり、`fix` と `means` を積んでいます。

**そしてこれは「予測が壊れている」話でもあります。** Analytics は日次で
**3日遅れ**、回は約41分ごとに回るので、**1日のうちに実データは1度も動きません。**
`eta.py` の「前の回からの差」は毎回 **-0.0日 ＝ 効いていません** と印字し、
**その回が何をしたかと無関係に、常に同じ字**を出していました。
「効いていません」を毎周見せられた側が、日付を動かす作業から離れていくのは自然です。

**だから1周ごとに測れる量を、日付の差から「どの腕を選んだか」へ置き換えます。**
腕は `scripts/eta.py` が実際に印字しているものだけです（勝手に増やさないこと）:

    天井   「動くのは **1本あたりの再生数** か **RPM（＝ニッチと尺）** の2つだけです」
    門1     登録者／日 ＝ **再生／日**（＝ 公開の密度 × 1本あたり）× **登録率**

**`none` を選ぶのは自由です。** 禁じると嘘の宣言が増えるだけで、数えられなくなります。
数えたいのは「動かす腕を選んだ回が、10回のうち何回か」のほうです。
"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

#: **腕の語彙。`scripts/eta.py` が印字するものと1対1にすること。**
#: 増やすときは、`eta.py` の側に「その腕を何倍にすればいいか」が出ていること。
#: 出ていない腕は、選んでも効いたかどうかを誰も測れません。
LEVERS: dict[str, str] = {
    "per_video": "1本あたりの再生を上げる（天井の帯の倍率が、そのままこれ）",
    "rpm": "RPM を上げる（＝ニッチ・尺・形式を変える）",
    "density": "公開の密度を上げる（1日に公開する本数。門1の日数に直で効く）",
    "sub_rate": "登録率を上げる（門1 ＝ 再生／日 × 登録率）",
    "none": "この回は予測日を動かさない（道具・手順・記録の整備）",
}

#: 動かす腕（`none` 以外）。
MOVING = tuple(k for k in LEVERS if k != "none")


def vocab_help() -> str:
    """`--lever` の説明文。**道具の口と文書で二重に持たないため、ここから出す。**"""
    return "／".join(f"{k}＝{v}" for k, v in LEVERS.items())


def recent(path: Path, limit: int = 10) -> list[dict]:
    """`data/runs.jsonl` から、直近の `ship` を新しい順に返す。

    **`lever` を持たない古い行も、そのまま返します**（`None`）。
    印を後から書き足さないこと —— 何を選んだかは、その回にしか分かりません。
    """
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("kind") == "ship":
            out.append(rec)
    return out[-limit:][::-1]


def tally(rows: list[dict]) -> Counter:
    """腕べつの回数。宣言の無い行は `未宣言` に落とす（0 にしない）。"""
    return Counter(r.get("lever") or "未宣言" for r in rows)


def report(path: Path, limit: int = 10) -> list[str]:
    """`eta.py` の末尾に出す数行。**予測のすぐ下に置くこと。**

    ここが「予測 → 腕を選ぶ → 進む」の、**選んだ側の実績**です。
    """
    rows = recent(path, limit)
    if not rows:
        return ["", "  （`--lever` つきの ship がまだありません）"]
    counts = tally(rows)
    moving = sum(counts[k] for k in MOVING)
    out = ["", f"--- **この機械が選んできた腕**（直近 {len(rows)}回の ship・`run_marker.py --ship --lever`）---"]
    for key, n in counts.most_common():
        label = LEVERS.get(key, "**語彙にない**" if key != "未宣言" else "宣言の無い回（`--lever` を足す前の行）")
        out.append(f"    {key:<10} {n:>2}回   {label}")
    out.append(f"    → **日付を動かす腕を選んだ回: {moving} / {len(rows)}**")
    if moving == 0:
        out.append("      [!] **1回もありません。** 予測は、動かす腕を選ばないかぎり動きません。")
        out.append("          **この回で選ぶこと。** 何を選ぶかは、上の「早めるには、どれを何倍にするか」から。")
    return out
