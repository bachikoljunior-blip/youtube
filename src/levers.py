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


# ---------------------------------------------------------------------------
# **死んだ腕**（2026-08-24。**印字にしか無かった事実を、選ぶ側へ渡す**）
#
# `scripts/eta.py` の軌跡は、腕ごとに「天井（いまの何倍まで伸びうるか）」を
# 出しています。`_factors_at` は **`cap <= 1.0` の腕を `live` から外す** ——
# つまり **その腕をどれだけ引いても、到達日は1日も動きません。**
#
# 8/24 の実測: `density` の天井は **×1.00**
# （1日に再生が付く上限 10本 ÷ いま続けられる 12.1本/日 ＝ **すでに 1.2倍 超過**）。
# それでも同じ日の ship 12件のうち **5件が `--lever density`** でした。
# **選んだ側が悪いのではありません** —— 天井は `eta.py` を4分走らせた
# stdout にしか無く、`--ship` が撃つのは4秒の `--reflect` なので、
# **その数は選ぶ側に一度も届いていませんでした。**
#
# ここが渡すのは事実だけです。**止めません**（`none` を禁じないのと同じ理由で、
# 禁じると宣言が嘘になり、数えたいものが測れなくなる）。
# **覆る条件**: 天井そのものが未判定の前提に乗っているとき
# （`density` の ×1.00 は day_cap=10本 に乗っており、それは 13:30 の窓と
# **まだ切り分けられていません**。08/28 の判定で窓のほうなら、天井は上がります）。
# だから文言は「引き代なし」ではなく「**いまの実測では引き代なし**」にすること。
# ---------------------------------------------------------------------------

#: 天井がこれ以下なら「もう伸びない」。`eta.py` の `_factors_at` と同じ境目。
DEAD_CAP = 1.0


def arm_state(eta_row: dict | None) -> dict:
    """`data/eta.jsonl` の1行から、腕を選ぶのに要るものだけ取り出す。

    返す形（**読めなければ全部 `None`／空**。回は止めないこと）::

        {"hint": "rpm", "binding": "再生数が天井に当たっている",
         "caps": {"per_video": 2.84, ..., "density": 1.0},
         "dead": ("density",)}

    `caps` は 2026-08-24 より前の行には**ありません**（積んでいなかった）。
    無い行では `dead` は空になります —— **「死んだ腕は無い」ではなく
    「読めない」**なので、呼ぶ側はそう扱うこと。
    """
    row = eta_row or {}
    caps = row.get("arm_caps") or {}
    caps = {k: v for k, v in caps.items() if isinstance(v, (int, float))}
    dead = tuple(k for k, v in caps.items() if v <= DEAD_CAP)
    return {"hint": row.get("lever_hint"), "binding": row.get("binding"),
            "caps": caps, "dead": dead}


def lever_notes(lever: str | None, state: dict) -> list[str]:
    """宣言した腕について、**その場で言えることだけ**を返す（0〜3行）。

    出すのは2つです。どちらも `eta.py` が既に計算していて、
    **選ぶ側には届いていなかった**ものです:

        1. その腕の天井が ×1.00 …… 引いても到達日は動かない
        2. その腕が `lever_hint` と違う …… 縛っている床が別を名指ししている

    **どちらも門ではありません。** 1 は前提が未判定なら覆り、
    2 は「時差があるので今は別を引く」が正しい回があります
    （実測: 8/24 は「いちばん早い期日は 08/28」で、それまでどの腕も動かない）。
    """
    if not lever or lever == "none":
        return []
    out: list[str] = []
    cap = state.get("caps", {}).get(lever)
    if cap is not None and cap <= DEAD_CAP:
        out.append(f"         [!] **`{lever}` は、いまの実測では天井に着いています（×{cap:.2f}）。**"
                   " 引いても到達日は動きません（`eta.py` の軌跡がこの腕を外して解いています）。")
        out.append("             動かすなら、まず**天井そのものを上げる**こと"
                   "（天井が乗っている前提を1件、実データで判定する）。")
    hint = state.get("hint")
    if hint and hint in LEVERS and hint != lever:
        why = state.get("binding") or "（床の名前が読めません）"
        out.append(f"         [!] 縛っている床は **{why}** で、名指しは **`{hint}`** です。"
                   f" `{lever}` を選んだ理由を docs/JOURNAL.md に1行書くこと。")
    return out


def latest_arm_state(path: Path) -> dict:
    """`data/eta.jsonl` を**後ろから読んで**、腕の状態を組む。

    最後の1行では足りません。`--reflect` が積む行（`kind="reflect"`）は
    **差分の記録**で、`arm_caps` を持ちません —— そして `--ship` が
    既定で撃つのは `--reflect` なので、**最後の行はたいてい reflect** です。
    最後だけ読むと、天井は**永久に読めません**（入れた当日に踏みました）。

    だから「天井を持つ最後の行」と「名指しを持つ最後の行」を別々に拾います。
    どちらも無ければ空（`arm_state({})` と同じ）を返す ——
    **読めないことと「死んだ腕は無い」は別**です。
    """
    caps_row: dict = {}
    hint_row: dict = {}
    try:
        lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    except OSError:
        return arm_state({})
    for ln in reversed(lines):
        try:
            row = json.loads(ln)
        except json.JSONDecodeError:
            continue
        if not caps_row and isinstance(row.get("arm_caps"), dict):
            caps_row = row
        if not hint_row and row.get("lever_hint"):
            hint_row = row
        if caps_row and hint_row:
            break
    return arm_state({**caps_row, "lever_hint": hint_row.get("lever_hint"),
                      "binding": hint_row.get("binding")})
