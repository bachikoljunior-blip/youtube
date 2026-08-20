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
from datetime import date
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


def reconcile(rows: list[dict]) -> list[str]:
    """**宣言（`--moves`）と、実際に動いた日数を並べる。**（2026-08-20 08:0x）

    オーナー指示（原文・3回目）——

    > 「20万達成までのプランを作って達成日時を予測して、
    >   **毎回達成日時を早めることを考えてから進める**ようにして」

    **「考えてから進めた」は、外から見えません。** 見えるようにする道は1つで、
    **先に言って、後で突き合わせる**ことです。だから ship は
    「この作業で予測日が何日動く見込みか」（`--moves`）と、
    **そのとき出ていた予測日**（`eta_target`）を一緒に残します。

    実際に動いた日数は、**次の ship が残した予測日との差**です
    （予測の入力は Analytics 由来で1日1回しか動かないので、
    回ごとではなく ship ごとに見るのがいちばん細かい目盛りになります）。

    **当てることが目的ではありません。** 外れたと分かることのほうが、
    何も言わずに進むより速い —— 外した回は、その腕の効き目を1つ潰したことになります。
    """
    chrono = list(reversed(rows))  # 古い順
    lines: list[str] = []
    sum_declared = sum_actual = 0
    hits = 0
    for i, r in enumerate(chrono):
        mv = r.get("moves")
        if mv is None:
            continue
        cur = r.get("eta_target")
        nxt_row = next((c for c in chrono[i + 1:] if c.get("eta_target")), None)
        nxt = nxt_row.get("eta_target") if nxt_row else None
        # **物差しの違う2点を引き算しないこと**（2026-08-20 18:xx に足した）。
        #     予測日は「腕を据え置いた線」から「軌跡」へ替わりました。
        #     替わった前後を引くと、**チャンネルは何も変わっていないのに
        #     149日ぶん動いた**と出ます。`eta_basis` が違う組は飛ばします
        #     （**古い行に `eta_basis` はありません** —— 後から書き足さないこと)。
        same_basis = (nxt_row is not None
                      and r.get("eta_basis") == nxt_row.get("eta_basis"))
        act = None
        if cur and nxt and same_basis:
            try:
                act = (date.fromisoformat(str(nxt)) - date.fromisoformat(str(cur))).days
            except ValueError:
                act = None
        when = str(r.get("at", ""))[5:16].replace("T", " ")
        if act is None:
            why = ("次の ship がまだ" if nxt is None or not cur
                   else "**物差しが替わった**（据え置きの線 → 軌跡）")
            lines.append(f"    {when}  {r.get('lever', '?'):<9} 宣言 {mv:+3d}日   実際 —（{why}）")
        else:
            sum_declared += mv
            sum_actual += act
            hits += 1
            mark = "" if mv == act else ("  ← **外した**" if abs(act - mv) >= 3 else "")
            lines.append(f"    {when}  {r.get('lever', '?'):<9} 宣言 {mv:+3d}日   実際 {act:+3d}日{mark}")
    if not lines:
        return ["", "  （`--moves` つきの ship がまだありません。"
                "**次の ship から、宣言と実際が並びます**）"]
    out = ["", "--- **宣言と実際**（`--moves` で先に言った日数と、次の ship までに動いた日数）---"]
    out += lines[-10:]
    if hits:
        out.append(f"    → 宣言の合計 {sum_declared:+d}日 ／ **実際の合計 {sum_actual:+d}日**"
                   f"（{hits}件）")
        if sum_actual > sum_declared + 2:
            out.append("      [!] **言ったより遠のいています。** 選んでいる腕が効いていないか、"
                       "予測の前提のほうが動いています。")
    return out


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
    out.extend(reconcile(rows))
    return out
