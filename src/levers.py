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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

#: **腕の語彙。`scripts/eta.py` が印字するものと1対1にすること。**
#: 増やすときは、`eta.py` の側に「その腕を何倍にすればいいか」が出ていること。
#: 出ていない腕は、選んでも効いたかどうかを誰も測れません。
LEVERS: dict[str, str] = {
    "per_video": "1本あたりの再生を上げる（天井の帯の倍率が、そのままこれ）",
    "rpm": "RPM を上げる（＝ニッチ・尺・形式を変える）",
    "density": "公開の密度を上げる（1日に公開する本数。門1の日数に直で効く）",
    "sub_rate": "登録率を上げる（門1 ＝ 再生／日 × 登録率）",
    # **2026-08-30 に足した腕**（`src/resume_gate.py`）。
    #
    # 上の4本は**審査に受かった世界の中**にあります。受からなければ再生が
    # いくつでも収入は 0 円なので（`CLAUDE.md`）、`p_pass` は到達日に**掛かる**項で、
    # 4本はその内側です。**外側が 0 なら、内側を何倍にしても 0。**
    #
    # そして 08/30 の停止中は、4本とも**1つも引けません**（`src/pause_guard` が
    # 生成と投稿を塞いでいる）。語彙に引ける腕が無いので、停止中の回は
    # `--lever none` へ落ちます —— 実測 08/30 の ship 40件 中 **20件**。
    # **`none` は「予測日を動かさない」という意味なので、
    #   律速そのものを進めた回が、動かさない回として数えられていました。**
    #
    # 天井の倍率（この dict に載せる条件）は `resume_gate.cap()`: 閉じた k件 に対し
    # **×(6/k)**、k=0 では定義できないので `None`（**0倍 では 6件 になりません**）。
    "gate": "収益化の審査に通る形を決める（`docs/RESUME_GATE.md` の6件）",
    # **2026-08-31 に足した腕**（最適化の回に実測して足した）。
    #
    # `scripts/eta.py` の頭3行は、**θ（前提が閉じる速さ）を到達日の
    # いちばん大きい動かし手として印字しています**（実測 2026-08-31:
    # θ×2 で **-26日** ／ 天井 θ→∞ で **-51日**。上の4本のどれよりも大きい）。
    # **その θ を指す語が、この語彙にありませんでした。**
    #
    # だから θ を進めた回は `none`（＝日付を動かさない）か、意味の合わない
    # `gate` に落ちます。実測（`data/runs.jsonl`・直近7日・ship 359件）:
    #
    #     `none` **147件（41%）** ／ `gate` 17件（5%）
    #     `fix` **219件（61%）** ／ `verdict` **11件（3%）**
    #     同じ7日で到達日は **+13日 遠のいた**（宣言は -55日）
    #
    # **`none` は「予測日を動かさない」という意味なので、律速そのものを
    # 進めた回が、動かさない回として数えられます。** 08/30 に `gate` を
    # 足したのと**同じ形の穴**が、もう1つ空いていました。
    #
    # **この dict に載せる条件**（すぐ上の註）は「`eta.py` の側に
    # 『その腕を何倍にすればいいか』が出ていること」です。**θ は出ています** ——
    # 頭3行の「到達日をいちばん大きく動かすのは θ」の行がそれです。
    #
    # **`gate` との違い**: `gate` は審査に**通るかどうか**（掛かる項）。
    # `theta` は前提が**閉じる速さ**（`t_work` が反比例する項）。別の項です。
    # **4本の腕との違い**: 4本は「閉じた前提が何を動かすか」。
    # `theta` は「閉じるのが何日に1件か」。**分子と分母**です。
    #
    # **覆る条件**: `eta.py` が θ の倍率を印字しなくなったら、この腕は
    # 選んでも効いたかどうかを誰も測れません（上の註）。そのときは外すこと。
    "theta": "前提が閉じる速さを上げる（判定できる前提を見つけやすくする・"
             "立ててから判定できるまでの日数を縮める。`eta.py` の θ）",
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


#: **合計を採る窓（日）。`scripts/drift.py` / `scripts/eta.py` と同じにしてあります。**
#: 別々にすると、「343 ship で +33日」と「宣言 −915日」を並べて読めません。
TOTAL_DAYS = 7


def since(path: Path, days: int = TOTAL_DAYS,
          *, now: datetime | None = None) -> list[dict]:
    """直近 `days` 日の ship を**古い順**に返す。**合計はこちらで採ること。**

    ## なぜ「直近10件」ではいけないか（2026-08-29・最適化の回の実測）

    `recent(path, 10)` が返す 10件 は、いまの回転では **1.4〜5.2時間**しかありません
    （実測。ship は 7日 で 342件 ＝ 1時間に 2件 前後）。
    そして **`eta_target` は Analytics 由来で1日に1度しか動きません**
    （このファイルの冒頭が、その裏取りです）。

    **つまり 10件 の窓では、`実際` は構造上ほぼ 0 です。** 実測（末尾 60件 を
    3件ずつずらして 21箇所）::

        実際が 0 か −1        21箇所 中 **18箇所**
        `[!] 言ったより遠のいています` が出た  **11箇所（52%）**
        そのほとんどは 宣言が負・実際が 0

    **`--moves` に負を書く ＝ 腕を引いて日付を早めると宣言する**ことなので、
    **手順どおりに宣言した回ほど、この門が鳴ります。**
    `src/arm_speed.forward()` が「閉じると下がる」だった のと同じ形の符号違いです
    （`scripts/drift.py` の註）。

    ## 7日 で採ると、何が見えるか（同じ実測）

        宣言の合計 **−915日** ／ 実際の合計 **+33日**（329件）

    **これは本物の赤字**です。窓が 1.5時間 だと、この 948日 の差が
    「宣言 −3 ／ 実際 0」に化けて、**鳴ったり鳴らなかったりします。**

    ## 覆る条件

    - `eta_target` が1日に何度も動くようになったら（実測の取り直しが回ごとに
      入るようになったら）、窓を短くしてよい。**そのときは
      `tests/test_levers_window.py` の「10件 では 1.4〜5.2時間 にしかならない」を
      測り直すこと**（あの数は回転の速さで変わります）
    """
    if not path.exists():
        return []
    cut = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if rec.get("kind") != "ship":
            continue
        try:
            when = datetime.fromisoformat(str(rec.get("at") or ""))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= cut:
            out.append(rec)
    return out


def tally(rows: list[dict]) -> Counter:
    """腕べつの回数。宣言の無い行は `未宣言` に落とす（0 にしない）。"""
    return Counter(r.get("lever") or "未宣言" for r in rows)


def _pairs(chrono: list[dict]):
    """`(行, 実際に動いた日数 or None, 理由)` を古い順に返す。**印字と合計で共有する。**

    実際に動いた日数は、**次の ship が残した予測日との差**です
    （予測の入力は Analytics 由来で1日1回しか動かないので、
    回ごとではなく ship ごとに見るのがいちばん細かい目盛りになります）。
    """
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
        why = ""
        if act is None:
            why = ("次の ship がまだ" if nxt is None or not cur
                   else "**物差しが替わった**（据え置きの線 → 軌跡）")
        yield r, act, why


def reconcile(rows: list[dict], totals: list[dict] | None = None) -> list[str]:
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
    for r, act, why in _pairs(chrono):
        mv = r["moves"]
        when = str(r.get("at", ""))[5:16].replace("T", " ")
        if act is None:
            lines.append(f"    {when}  {r.get('lever', '?'):<9} 宣言 {mv:+3d}日   実際 —（{why}）")
        else:
            mark = "" if mv == act else ("  ← **外した**" if abs(act - mv) >= 3 else "")
            lines.append(f"    {when}  {r.get('lever', '?'):<9} 宣言 {mv:+3d}日   実際 {act:+3d}日{mark}")
    if not lines:
        return ["", "  （`--moves` つきの ship がまだありません。"
                "**次の ship から、宣言と実際が並びます**）"]
    out = ["", "--- **宣言と実際**（`--moves` で先に言った日数と、次の ship までに動いた日数）---"]
    out += lines[-10:]
    # **合計は、行と同じ窓では採りません**（2026-08-29・最適化の回に分けた）。
    #
    # 上の 10行 は **1.4〜5.2時間**ぶんしかなく（実測）、`eta_target` は
    # 1日に1度しか動かないので、**その窓の「実際」は構造上ほぼ 0** です。
    # そこへ合計と門を載せると、**宣言に負を書いた回ほど門が鳴ります** ——
    # 手順が「腕を引いて早めると宣言せよ」と言っているのに、です
    # （実測: 末尾60件を3件ずつずらした 21箇所 のうち **11箇所（52%）で
    #  `[!]` が鳴り、そのほとんどが 宣言が負・実際が 0**）。
    #
    # だから**行は直近10件・合計は `since()` の 7日**にします。
    # 呼ぶ側が `totals` を渡さない回は、今までどおり同じ行から採ります
    # （道具を単体で呼ぶ回を落とさないため。ただし窓は名乗ります）。
    if totals is None:
        span = chrono
        label = f"直近 {len(rows)}件"
    else:
        span = totals
        label = f"直近 {TOTAL_DAYS}日・{len(totals)}件"
    sum_declared = sum_actual = hits = 0
    for r, act, _ in _pairs(span):
        if act is None:
            continue
        sum_declared += r["moves"]
        sum_actual += act
        hits += 1
    if hits:
        out.append(f"    → **{label}**の 宣言の合計 {sum_declared:+d}日 ／"
                   f" **実際の合計 {sum_actual:+d}日**（{hits}件）")
        if sum_actual > sum_declared + 2:
            # **数を、この行そのものに入れること**（2026-08-30・最適化の回）。
            #     `eta.flagged()` が尾へ運ぶのは **`[!]` の付いた行だけ**で、
            #     すぐ上の「宣言の合計 … ／ 実際の合計 …」は置いていかれます。
            #     `CLAUDE.md` の読み方（頭と尾の3行）に従うと、**警告は届くが
            #     いくら外したかは届きません。** この repo の言い方では
            #     「印字されていない数字は、無い数字と同じ」——
            #     実測 2026-08-30: 尾には「言ったより遠のいています」だけが並び、
            #     **宣言 -63日 ／ 実際 +3日（360件）という差は本文の 151行目**にありました。
            out.append(f"      [!] **言ったより {sum_actual - sum_declared:+d}日 遠のいています**"
                       f"（{label}: 宣言 **{sum_declared:+d}日** ／ "
                       f"実際 **{sum_actual:+d}日**・{hits}件）。"
                       "選んでいる腕が効いていないか、"
                       "予測の前提のほうが動いています。"
                       f"（**上の10行の窓ではありません** —— あちらは {TOTAL_DAYS}日 より"
                       "ずっと短く、`eta_target` は1日に1度しか動かないので、"
                       "**その窓の「実際」は構造上ほぼ 0** です）")
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
    out.extend(reconcile(rows, since(path)))
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


def _long_surface_measured() -> bool:
    """**長尺の面の上限を、もう測ったか。**（`src/day_cap.py`）

    読めなければ **False**（＝「まだ測っていない」側）を返します ——
    ここで True に倒すと、**測っていないものを「天井」として黙らせる**ことに
    なります。**分からないときは、分からないと言う側へ倒すこと。**

    **2026-08-26 に、向こうの意味がはっきりしました。**
    もとは「常に False」と書いてありました（実装がそう固定していた）。
    いまは **`collapsed` ＝ いちばん多く出した日に「出したのに付かない」本が出たか**
    です。**まだ 5本/日 までしか出しておらず、そこでは崩れていない**ので、
    値は False のまま —— **ただし「面が狭い」ではなく「広いほうの端をまだ見ていない」**
    という意味に変わりました。**5本/日 を超えた日が出れば、ここは動きます。**
    """
    try:
        from src import day_cap                      # 遅く読む（循環を避ける）
        return bool(day_cap.long_form().get("measured"))
    except Exception:                                # noqa: BLE001
        return False


#: **`dead_why` の前置き。「天井」ではない死に方**（2026-08-31・最適化の回）。
#: `scripts/drift.py` は前方一致で読みます。**完全一致で読まないこと** ——
#: 理由には但し書きが付きます。
RULE_DEAD = "規則"



def _rule_lift_gain() -> dict | None:
    """**規則（1日1本）を外して、物理の上限まで出したら天井は何倍か。**

    ## なぜ要るか（2026-09-01・最適化の回）

    すぐ上の行は「規則が止めている・外せるのはオーナーだけ」までしか言いません。
    読む側の次の問いは必ず **「では外したら届くのか」** で、そこに数が無いと
    **オーナーに返すかどうかを誰も決められません。**

    掛け算は2つです。本数は増えますが、**1本あたりは薄まります**::

        天井の倍率 = (上限本数 / 規則の本数) ** (1 + b)

    `b` は「その日の本数 → 1本あたり再生」の弾力性（`src/rule_per_video.py`・
    実測 -0.663・n=25日・95% [-0.991, -0.335]）。この回に撃った数::

        上限 10本/日   1本あたり ×0.217   天井 **×2.17**

    `scripts/eta.py` の `ceiling_short`（天井の不足）はこの回 **×17.69** なので、
    **規則を外しても律速にはなりません。** それを言わずに「規則が止めている」
    だけを出すと、次の回はオーナーへ返す相談を組み立てはじめます。

    `None` を返すのは「弾力性が測れない／95%区間が 0 をまたぐ」回で、
    そのとき呼び手は**この行を出しません**（測っていない数を出さないこと）。

    **覆る条件**: `day_cap` の上限が測り直されたら倍率は動きます（定数ではなく
    毎回 読みます）。区間が 0 をまたいだら `None` に戻ります。
    """
    try:
        from . import day_cap, house_rule, rule_per_video
    except Exception:                                          # noqa: BLE001
        return None
    try:
        e = rule_per_video.estimate()
        el = (e or {}).get("elasticity") or {}
        if not (el.get("ok") and e.get("significant")):
            return None
        b = float(el["b"])
        cap = float(day_cap.cap())
        base = float(house_rule.PUBLISH_PER_DAY)
    except Exception:                                          # noqa: BLE001
        return None
    if not base or cap <= base:
        return None
    n = cap / base
    return {"cap": cap, "base": base, "b": b,
            "thin": n ** b, "gain": n ** (1.0 + b)}


def _density_ceiling_is_rule(row: dict) -> bool:
    """**`density` の天井は、観測ではなく「オーナーが固定した規則」か。**

    ## なぜ要るか（2026-08-31・最適化の回。**自分で撃った数**）

    この回の実データ（`data/eta.jsonl` の最後の天井の行）は、こうでした:

        arm_caps    {'per_video': 2.01, 'sub_rate': 6.64, 'rpm': 59.77, 'density': 1.00}
        dead        ('per_video', 'sub_rate', 'rpm')      ← **動かせる腕が全部 死んでいる**
        open_why    {'density': '…長尺の面は開いています…'}  ← **`density` だけが生きている**

    そして門1（登録者1,000人）を、腕ごとに解き直すとこうです（`house_rule.cap()` を掛けて）:

        いま                      3,292日
        per_video を天井 ×2.01     1,640日   （**−1,652日**）
        sub_rate  を天井 ×6.64       495日   （**−2,797日**）
        density   を天井 ×1.00     3,292日   （**    0日**）
        density   を **無限大**    3,292日   （**    0日**）  ← **規則が頭を押さえる**

    **`density` は、無限大にしても到達日を1日も動かしません。**
    `scripts/eta.py` の `PLAN_PUBLISH_PER_DAY` は
    `src.house_rule.PUBLISH_PER_DAY` をそのまま読み、その規則の
    **「覆る条件: ありません」** はオーナーの言葉でしか外れません。

    それでもこの機械は `density` を**唯一の生きた腕**として差し出していました。
    実測 —— 直近10回の ship の腕は `density` **3回**、過去の配分の **39%** が
    ここに載っています（`scripts/eta.py` の「上の日付は過去の配分で解いています」）。

    ## 直したのは「面の話」ではありません

    2026-08-26〜27 に入った救済（`_long_surface_open`）は**正しい**ものでした ——
    当時の天井は `day_cap.cap()` ＝ **観測**で、観測は測り直せば動くからです。
    **2026-08-31 に、その上に規則が乗りました。** 規則は測り直しても動きません。
    だから救済の前提（「測り直せば引ける」）が、この腕についてだけ消えています。

    **長尺の面が開いている、という事実は正しいままです。** 変わったのは
    **その事実がどの腕を指すか**です —— 1日の本数は規則で固定なので、
    自由なのは**その1本がどの形か**のほうで、それは `rpm`
    （`LEVERS["rpm"]` ＝「ニッチ・尺・**形式**を変える」）です。

    ## 読み方

    `scripts/eta.physical_caps` が `caps["density"]["rule_binds"]` を立て、
    `_row()` が `density_surfaces["short"]["rule_binds"]` として積みます。

    **欄が無い行では False**（＝前のまま）。`_long_surface_open` と同じ姿勢で、
    **済んだ回の判定を、あとから足した欄で塗り替えないこと。**
    新しい行は毎回この欄を持つので、次の `eta.py` で入ります。

    ## 覆る条件

    **オーナーが自分の言葉で 1日1本 を外したとき。** そのとき
    `house_rule.PUBLISH_PER_DAY` が上がり、`physical_caps` の `rule_binds` は
    自然に False になって、この関数は黙ります。**手で消さないこと。**
    """
    surfaces = (row or {}).get("density_surfaces")
    if isinstance(surfaces, dict) and isinstance(surfaces.get("short"), dict):
        return bool(surfaces["short"].get("rule_binds"))
    return False


def _long_surface_open(row: dict) -> bool:
    """**長尺の面に、まだ引き代があるか。**（2026-08-26。3回続けて申し送られた話の本体）

    ここまでは「ショートの面の数だ」と**名乗るだけ**でした。名乗っても
    `density` は「死んだ腕」に入ったままなので、**長尺を増やす作業は
    やはり `none` に落ちます** —— 申し送りが3回とも言っていたのはそこです。

    見るのは `scripts/eta.py` が積む `density_surfaces`（面ごとの `at_ceiling`）。

    **`density_surfaces` を持たない行では、前のまま（閉じている側）に倒します。**
    そこを「開いている」に倒すと、**過去の行の判定が全部ひっくり返り**、
    `drift.dead_arm_report` の「到達日を動かせない腕を選んだ回」が
    **さかのぼって書き換わります** —— 済んだ回の記録を、あとから足した欄で
    塗り替えないこと。新しい行は毎回この欄を持つので、**次の `eta.py` で直ります。**
    """
    surfaces = row.get("density_surfaces")
    if isinstance(surfaces, dict) and isinstance(surfaces.get("long"), dict):
        return not bool(surfaces["long"].get("at_ceiling"))
    return False


def arm_state(eta_row: dict | None) -> dict:
    """`data/eta.jsonl` の1行から、腕を選ぶのに要るものだけ取り出す。

    返す形（**読めなければ全部 `None`／空**。回は止めないこと）::

        {"hint": "rpm", "binding": "再生数が天井に当たっている",
         "caps": {"per_video": 2.84, ..., "density": 1.0},
         "reaches": {"per_video": True, ..., "sub_rate": False},
         "dead": ("density", "sub_rate"),
         "dead_why": {"density": "天井", "sub_rate": "天井まで引いても届かない"}}

    `caps` は 2026-08-24 より前の行には**ありません**（積んでいなかった）。
    無い行では `dead` は空になります —— **「死んだ腕は無い」ではなく
    「読めない」**なので、呼ぶ側はそう扱うこと。

    ## **天井が大きいことと、その腕が日付を動かせることは別です**（2026-08-25）

    ここは長らく `cap <= DEAD_CAP` だけで数えていました。それだと:

        sub_rate  天井 ×2,923.79 → **「引き代 ×2,923 の生きた腕」に見える**
                  実際は**天井まで引いても月20万には届きません**
                  （いまの縛りは再生数（段4）で、登録率はそこに触らない）

    **偽の緑です。** 8/25 の実測では実績配分の 11% がここに載っていました
    （`density` の 28% と合わせて **39%** が、到達日を動かせない腕）。
    `scripts/eta.py` の `lever_days()` が `reachable_at_cap` を解いているので、
    それを `arm_reaches` として読みます。**無い行では判定しません**（`None`）。
    """
    row = eta_row or {}
    caps = row.get("arm_caps") or {}
    caps = {k: v for k, v in caps.items() if isinstance(v, (int, float))}
    reaches = row.get("arm_reaches") or {}
    reaches = {k: bool(v) for k, v in reaches.items() if isinstance(v, bool)}

    dead_why: dict[str, str] = {}
    for k, v in caps.items():
        if v <= DEAD_CAP:
            dead_why[k] = "天井"
    # **`density` の「天井」は、ショートの面の数です**（2026-08-26 に足した）。
    #     `physical_caps` はここを `day_cap.cap()`（＝ショートの面で1日に再生が
    #     付く本数）で立てています。**長尺はその枠を1つも使いません**し、
    #     **4,000時間の門に入るのは長尺だけ**です。つまりこの「引き代なし」は、
    #     **唯一開いている門について何も言っていません。**
    #     数字は足しません（長尺の面の上限は**まだ一度も測っていない**ので、
    #     足せば推測を実測に見せることになります）。**名前だけ正します。**
    #     **2026-08-26 夜に直した。** ここは `and not _long_surface_measured()` で
    #     囲ってありました。**2つの別のことを1つの条件に畳んでいます**:
    #         (あ) この数字が**どの面のものか**  …… いつでも「ショートの面」
    #         (い) **もう片方の面を測ったか**    …… 日によって変わる
    #     `src/day_cap.long_form()` が 08/21 の 7本（生きた 5本）を拾って
    #     `collapsed` を True にした瞬間、(い) が反転し、**(あ) の名前ごと消えました** ——
    #     `dead_why["density"]` が裸の「天井」に戻り、
    #     `tests/test_levers_density_surface.py` が 3件 赤いまま 20時間 残りました。
    #     **名前は、旗が立っても消えません。** 分けて言います。
    #
    #     **【2026-08-29 に、下の3行を直しました】** ここは `measured` を
    #     **「長尺の面も天井」と読んでいました。別の量です** ——
    #     `measured` は「崩れる所を**見たか**」で、
    #     `at_ceiling` は「**いま**その天井に当たっているか」。
    #     実物（08/29）は **measured=True かつ at_ceiling=False**
    #     （実測の上限 6本/日 に対し、出しているのは 0.69本/日 ＝ ×8.7 空き）で、
    #     この枝は「**長尺の面も測って天井**」と印字します —— **偽です。**
    #     同じ関数の 20行 下では `density_open_why` が
    #     「**長尺の面は開いています**」と言うので、
    #     **同じ出力の中で、自分の言っていることを自分で否定していました。**
    # --- **その天井は、測り直せる観測か。それとも規則か**（2026-08-31・最適化の回）---
    #     下の名乗り直しも救済も、**天井が観測であること**を前提にしています
    #     （「ショートの面の数」＝ `day_cap.cap()`）。**2026-08-31 に、その上に
    #     オーナーの規則が乗りました**（`src/house_rule.PUBLISH_PER_DAY = 1`）。
    #     規則は測り直しても動かないので、**面がいくつ開いていても引けません。**
    #     根拠は `_density_ceiling_is_rule` の docstring（この回に自分で撃った数）。
    rule_pins_density = _density_ceiling_is_rule(row)
    if rule_pins_density and "density" in dead_why:
        dead_why["density"] = (
            f"{RULE_DEAD}（**オーナーが固定した 1日1本**・`src/house_rule.py`。"
            "**覆る条件はありません**）"
            " —— 天井ではないので、測り直しても上がりません")
    if not rule_pins_density and dead_why.get("density") == "天井":
        if not _long_surface_measured():
            dead_why["density"] = "天井（**ショートの面だけ。長尺の面は未測定**）"
        elif _long_surface_open(row):
            dead_why["density"] = (
                "天井（**ショートの面の数。長尺の面は実測して、まだ開いています**）")
        else:
            dead_why["density"] = "天井（**ショートの面の数。長尺の面も実測して天井**）"
    # **そして、面が割れているなら `density` は死んでいません**（2026-08-26）。
    #     上の1行は**名前を正すだけ**で、`density` は「死んだ腕」に入ったままでした。
    #     だから `--ship --lever density` はいまも叱られ、
    #     **長尺を増やした回が `none` を選び直す**という形が3周続いています
    #     （`retro.py` の持ち越し `physical_caps` / `density`）。
    #     **片方の面が天井でも、もう片方が開いているなら、その腕は引けます。**
    #     殺すのは**両方の面が閉じたとき**だけ。**理由のほうは残します**
    #     （`open_why` として返し、`lever_notes` がそのまま出す）。
    density_open_why = None
    #: **規則で `density` が死んでいるとき、長尺の面の話が指す腕**（2026-08-31）。
    #:     救済の中身（「長尺は `SHORTS_FEED` の枠を使わない・4,000時間の門に
    #:     入るのは長尺だけ・その作業を `none` へ落とすな」）は**そのまま正しい**
    #:     ので、捨てません。**指す先だけを、引ける腕へ付け替えます。**
    redirect_why: dict[str, str] = {}
    #: **面が割れているから外した腕**。下の `reaches` の輪が入れ直さないため。
    rescued: set[str] = set()
    if rule_pins_density and _long_surface_open(row):
        _note = (
            "**長尺の面は開いています**"
            + ("（**実測の上限**まで、まだ引き代があります）"
               if _long_surface_measured() else "（未測定）")
            + "。 長尺は `SHORTS_FEED` の枠を1つも使わず、"
            "**4,000時間の門に入るのは長尺だけ**です。"
            " **長尺の仕事を `none` へ落とさないこと。**"
            " ただし **1日の本数は規則で 1本 に固定**なので、"
            "それを指すのは `density` ではなく **`rpm`**"
            "（`LEVERS['rpm']` ＝ ニッチ・尺・**形式**を変える）です ——"
            " 自由なのは**その1本がどの形か**のほうです。")
        redirect_why["density"] = _note
        redirect_why["rpm"] = _note
    if not rule_pins_density and "density" in dead_why and _long_surface_open(row):
        # **「（未測定）」を、ここに焼き込まないこと**（2026-08-29 に直した）。
        #     長尺の面の崩れは **2026-08-21 に観測されています**
        #     （7本 出して生存 5本 → 上限 6本/日・`src/day_cap.long_form()`）。
        #     それでもこの行は「開いています（**未測定**）」と言い続けていました ——
        #     **開いていることと、測っていないことは別の話**です。
        density_open_why = (
            "ショートの面は天井ですが、**長尺の面は開いています**"
            + ("（**実測の上限**まで、まだ引き代があります）"
               if _long_surface_measured() else "（未測定）")
            + "。 長尺は `SHORTS_FEED` の枠を1つも使わず、"
            "**4,000時間の門に入るのは長尺だけ**です。"
            " **長尺を増やす作業を `none` へ落とさないこと。**")
        dead_why.pop("density")
        rescued.add("density")
    # **「天井まで引いても届かない」は、天井の大小と別の理由です。**
    #     両方に当たる腕は、天井のほうを理由として残します（そちらが手前の話）。
    #
    # **ただし、上で外した腕をここで入れ直さないこと**（2026-08-27・最適化の回）。
    #     08/26 に入れた上の3行は、実データでは**1行も効いていませんでした。**
    #     `pop` した2行あとに、この輪が `density` をそのまま戻します:
    #
    #         arm_caps    {'density': 1.0, ...}        ← ショートの面の数
    #         arm_reaches {'density': False, ...}      ← **同じ 1.0 から出た数**
    #         → dead_why  {'density': '天井まで引いても届かない'}
    #
    #     `eta.lever_days()` の `reachable_at_cap` は
    #     **`cap <= 1.0` なら解き直さず `NEVER` のまま**返します
    #     （`at_ceiling` の枝）。つまり `reaches["density"] is False` は
    #     **「天井が ×1.00 だ」の言い直し**で、別の証拠ではありません。
    #     **同じ数を2回 数えて、2回目で殺していた**ということです。
    #
    #     何が起きていたか（実測 2026-08-27・`data/eta.jsonl` の最後の天井の行）:
    #       `_long_surface_open(row)` は **True**（長尺の面 82枠/日 ÷
    #       いま出している 0.65本/日 ＝ ×126 空いている）。それでも
    #       `drift.dead_arm_report` は **`density` 64回（ship の 23%）**を
    #       「引き代が無かった回」に数え、「この回では到達日が動きえない回
    #       179/274（65%）」の分子に入れていました。
    #       **長尺の再生は、台帳でいちばん大きい前提**
    #       （「長尺の登録率はショートより1桁以上高い」・`sub_rate`・期限 11/22。
    #        `needs` は「長尺の合計が 1,000再生」で、いま 74・10.6回/日 ＝ あと 88日）
    #       **の待ち時間そのもの**です。その期限は**すでに3回 延ばされています。**
    #       つまりこの1行は、**唯一の桁ちがいの前提を遅らせている側の作業を、
    #       毎回「無駄だった」と記録していました。**
    #
    # **覆る条件**: `physical_caps` が `density` の天井を**面ごとに**立てるように
    #     なったら（いまは `arm_caps["density"]` がショートの面の数ひとつだけ）、
    #     `reaches["density"]` は独立した証拠になります。**そのときはこの除外を外すこと。**
    #     見分け方: `arm_caps` に `density_long` が入っているかどうか。
    for k, ok in reaches.items():
        if not ok and k not in dead_why and k not in rescued:
            dead_why[k] = "天井まで引いても届かない"
    dead = tuple(k for k in dead_why)
    return {"hint": row.get("lever_hint"), "binding": row.get("binding"),
            # **その名指しは、この回に引かなくてよいか**（2026-08-26）。
            #     `eta.py` が「予約済みの本が答えを返すので別の腕を引け」と
            #     言っている回は、名指しを外すのが**正しい**です。
            "hint_covered": row.get("lever_hint_covered"),
            "caps": caps, "reaches": reaches,
            # **「その腕を凍らせたら軌跡は何日 遠のくか」**（2026-08-26）。
            #     `reaches=False`（＝この腕だけを天井まで引いても届かない）は
            #     **十分でない**ことしか言っていません。**必要かどうかは別の問い**で、
            #     それに答えるのがこの数です（`scripts/eta.py` の `frozen_days`）。
            #     `>0` なら、回転をよその腕へ全部 配り直しても遠のく ＝ 必要。
            "frozen": {k: v for k, v in (row.get("arm_frozen_days") or {}).items()
                       if isinstance(v, (int, float))},
            "thresholds": row.get("arm_threshold") or {},
            # **面が割れていて生きている腕の、その理由**（`density` だけ）。
            "open_why": ({"density": density_open_why} if density_open_why else {}),
            # **規則で死んだ腕から、引ける腕への付け替え**（2026-08-31）。
            "redirect_why": redirect_why,
            # --- **無限大にしても 0日 の腕**（2026-08-31・最適化の回）---
            #     `caps` / `reaches` は「**天井まで**引いたら」しか見ていないので、
            #     「天井が足りないだけの腕」と「**無限大でも 0日** の腕」が
            #     `reaches=False` の同じ字に潰れます。**別の話です** ——
            #     前者は天井を壊せば引けますが、後者は**何をしても引けません。**
            #     `scripts/eta.py` の `lever_days()` が `LEVER_INF_SCALE`（×10^9）
            #     で1回 撃って分けるようにしたので、それを読みます。
            #
            #     実測 2026-08-31（`points` 付き ＝ 本番と同じ道）::
            #
            #         per_video  天井 ×2.01  → ×17.69 で出る（**天井 ×8.81 上げ**）
            #         sub_rate   天井 ×6.64  → **×7.1e+09 でも出ない**
            #         rpm        天井 ×28.05 → **×3.0e+10 でも出ない**
            #         density    天井 ×1.00  → **×2.1e+09 でも出ない**
            #
            #     そのあいだ画面は **`rpm` を「この回に引く腕」として直近 50 ship
            #     連続で名指し**し、選んだ **24回の全部**が到達日を1日も
            #     動かしていません（`data/runs.jsonl`）。オーナー規則2
            #     （ゼロなら律速ではない）に反する名指しが、数えられないまま
            #     50回 通っていた、ということです。
            #
            #     **覆る条件**: `arm_dead_at_inf` を積まない版の `eta.py` に
            #     戻ったら、ここは空になります —— **「死んだ腕は無い」ではなく
            #     「読めない」**なので、呼ぶ側はそう扱うこと（`caps` と同じ）。
            "dead_at_inf": tuple(row.get("arm_dead_at_inf") or ()),
            "need_over_cap": {
                k: v for k, v in (row.get("arm_need_over_cap") or {}).items()
                if isinstance(v, (int, float))},
            "hint_measured": (False if row.get("lever_hint_measured") is False
                              else None),
            "all_dead": bool(row.get("lever_all_dead")),
            "dead": dead, "dead_why": dead_why}


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
    # --- **無限大にしても 0日 の腕は、天井の話をする前に止める**（2026-08-31）---
    #     下の全部（天井 ×1.00・面が割れている・名指しとの一致）は「**天井を
    #     壊せば引ける**」を前提にしています。`dead_at_inf` の腕はそうではない
    #     ので、その前提から先に断ちます。**理由は `arm_state` の注記に実測。**
    #     ここが黙ると、次の回は「天井を上げる前提を1件 立てよう」に向かい、
    #     **無限大でも 0日 の腕について、閉じても日付が動かない前提**を積みます。
    if lever in (state.get("dead_at_inf") or ()):
        out.append(f"         [!] **`{lever}` は、無限大にしても到達日が"
                   "1日も動きません。** 天井の話ではありません ——"
                   " `×10^9` まで引いても `days_to_target` は出ませんでした"
                   "（`eta.py` の `LEVER_INF_SCALE`）。")
        out.append("             **オーナー規則2: 答えがゼロなら、そこは律速では"
                   "ありません。** この腕で前提を立てても、閉じた日に"
                   "到達日は動きません。")
        _live = {k: v for k, v in (state.get("need_over_cap") or {}).items()
                 if k not in (state.get("dead_at_inf") or ())}
        if _live:
            _k = min(_live, key=lambda k: _live[k])
            out.append(f"             → 引けるのは **`{_k}`**（天井を"
                       f" **×{_live[_k]:.2f}** 上げれば日付が出ます）。")
        return out
    cap = state.get("caps", {}).get(lever)
    redirect = (state.get("redirect_why") or {}).get(lever)
    # --- **規則で死んだ腕は、「天井」と同じ字で叱らないこと**（2026-08-31）---
    #     「天井に着いています」は「**測り直せば上がる**」と読めます。
    #     規則（`src/house_rule.py`・覆る条件: ありません）はそうではありません。
    #     読み違えると、次の回が「天井を上げる前提を1件 立てよう」に向かい、
    #     **オーナーが外すまで永久に閉じない前提**を積みます。
    _why = (state.get("dead_why") or {}).get(lever) or ""
    if _why.startswith(RULE_DEAD):
        out.append(f"         [!] **`{lever}` を止めているのは天井ではありません。** {_why}")
        out.append("             **無限大にしても到達日は1日も動きません**"
                   "（`scripts/eta.py` の `PLAN_PUBLISH_PER_DAY` は"
                   " `src.house_rule.PUBLISH_PER_DAY` をそのまま読みます）。"
                   " **天井を上げる前提を立てないこと** —— 外せるのはオーナーだけです。")
        # --- **「では外したら幾ら？」に、その場で答えること**（2026-09-01）---
        #     上の1行は「規則が止めている」までしか言いません。読む側の次の問いは
        #     必ず **「外したら届くのか」** で、答えが無いと毎回そこで止まります
        #     （＝オーナーに返すかどうかを、誰も数で決められません）。
        _rule = _rule_lift_gain()
        if _rule:
            out.append(
                f"             **外したら幾らか**: 物理の上限まで"
                f"（{_rule['cap']:.0f}本/日・`src/day_cap.py` の実測）出しても、"
                f"1本あたりは薄まるので天井は **×{_rule['gain']:.2f}** です"
                f"（弾力性 {_rule['b']:+.3f}・`src/rule_per_video.py`。"
                f"1本あたり ×{_rule['thin']:.3f} × 本数 ×{_rule['cap']:.0f}）。"
                " **`density` の腕は、規則を外しても律速になりません** ——"
                " 天井の不足は `scripts/eta.py` の `ceiling_short` を見ること"
                "（この倍率より大きければ、規則はそもそも答えではありません）。")
        if redirect:
            out.append(f"             {redirect}")
        return out
    # **面が割れていて生きている腕は、叱らないこと**（2026-08-26）。
    #     `arm_state` が `density` を「死んだ腕」から外したのに、ここが
    #     `caps` の生の数（＝ショートの面）だけを見て叱り続けていました。
    #     **同じ回に「引いてよい」と「引いても動かない」を両方出す形**です。
    open_why = (state.get("open_why") or {}).get(lever)
    if open_why:
        out.append(f"         **`{lever}` は、面が割れています。** {open_why}")
        out.append("             ショートの面の数（"
                   + (f"×{cap:.2f}" if cap is not None else "×1.00")
                   + "）を、この腕ぜんぶの天井として読まないこと。")
    elif cap is not None and cap <= DEAD_CAP:
        out.append(f"         [!] **`{lever}` は、いまの実測では天井に着いています（×{cap:.2f}）。**"
                   " 引いても到達日は動きません（`eta.py` の軌跡がこの腕を外して解いています）。")
        out.append("             動かすなら、まず**天井そのものを上げる**こと"
                   "（天井が乗っている前提を1件、実データで判定する）。")
        if lever == "density" and not _long_surface_measured():
            out.append("             [!] **ただし、その天井はショートの面の数です**"
                       "（`day_cap.cap()`）。**長尺はその枠を1つも使いません**し、"
                       "**4,000時間の門に入るのは長尺だけ**です。")
            out.append("             **長尺の面の上限は、まだ一度も測っていません。**"
                       " 長尺を増やす作業を、この ×1.00 を理由に `none` へ落とさないこと。")
    elif state.get("reaches", {}).get(lever) is False:
        # **天井は大きいのに、その天井まで引いても到達日に届かない腕。**
        #     `cap` だけ見ていると生きて見えます（`sub_rate` は ×2,923.79）。
        cap_s = f"（天井 ×{cap:,.2f}）" if cap is not None else ""
        out.append(f"         [!] **`{lever}` は、この腕**だけ**を天井まで引いても届きません**{cap_s}。"
                   " 天井が大きいことと、単独で日付を動かせることは別です。")
        out.append("             **「要らない」という意味ではありません。**"
                   " ここが言っているのは**十分でない**ことだけで、"
                   "**必要かどうかは別の問い**です。")
        # **2026-08-26 に、この2つを取り違えた読みが実際に運ばれました**（受け取り帳 303b3e65）。
        #     「登録者は AND の門なのに `sub_rate` が届かないと出る ＝
        #       eta は登録者を増やさずに届く道を予測しているのでは？」
        #     **凍らせて測ったら、逆でした**（下の1行が誰でも引き直せます）:
        #       いまの軌跡 2026-12-28 → `sub_rate` を凍結すると **2027-04-21（+115日）**。
        #     **門は効いています。** 直したのは模型ではなく、この文言のほうです。
        # **ここは長らく「+115日（2026-08-26）」と べた書き でした**（同日に直した）。
        #     べた書きは腐ります —— この本文が名指ししている壊れ方そのものです。
        #     いまは `eta.py` の `frozen_days` が毎回 測り直した数を運びます。
        frozen = (state.get("frozen") or {}).get(lever)
        if frozen is not None and frozen > 0.5:
            out.append(f"             [!] **ただし、この腕を凍らせると軌跡は {frozen:+,.0f}日**"
                       "（回転はよその腕へ配り直したうえで）。"
                       " **十分でないだけで、必要な腕です。**")
        elif frozen is not None:
            out.append(f"             凍らせても軌跡は {frozen:+,.0f}日 ＝"
                       " **回転をよそへ回しても同じ。この腕は要りません。**")
        if lever == "sub_rate":
            out.append("             **登録者は AND の門です**（1,000人）。"
                       "この行を「登録者は要らない」と読まないこと。")
        out.append("             **単独で到達日を動かしたいなら、別の腕にすること。**"
                   " 確かめ方（`arms` に `rate=0` を渡して解き直す）:")
        out.append("               `eta.trajectory(m, a, arms=<その腕だけ rate=0>)`"
                   " —— **凍らせて日付が動けば、その腕は効いています。**")
    # **規則で `density` が死んだとき、その仕事の行き先を引ける腕の側にも出す**
    #     （2026-08-31）。`density` の側だけに書くと、**`rpm` を選んだ回が
    #     「長尺を増やす仕事は自分の担当だ」と気づけません。**
    if redirect and not _why.startswith(RULE_DEAD):
        out.append(f"         {redirect}")
    hint = state.get("hint")
    if hint and hint in LEVERS and hint != lever:
        why = state.get("binding") or "（床の名前が読めません）"
        covered = state.get("hint_covered")
        if covered:
            # **道具の指示どおりに動いた回を、叱らないこと**（2026-08-26）。
            #     `eta.py` は同じ回に「引く腕は `per_video`」と
            #     「この測定に ship を使うな・別の腕を引け」を両方言います。
            #     後者に従うと、ここが前者を根拠に「外した」と言っていました。
            out.append(f"         名指しは **`{hint}`**（床は {why}）ですが、"
                       f" **その測定は予約済みの本が {covered} に答えます** ——"
                       f" `{lever}` を引いたのは、`eta.py` の指示どおりです。")
        else:
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
    # **「無限大でも 0日 の腕」は、3つ目の行から拾う**（2026-08-31・最適化の回）。
    #     `caps_row`（＝`arm_caps` を持つ最後の行）は**軌跡を解いた回にしか
    #     付きません**。`--ship` が撃つのは `--reflect` だけなので、
    #     `caps_row` は平気で数十分 古くなります —— 実測 08/31 は 33分 差で、
    #     **新しい行が `dead_at_inf` を持っているのに、古い `caps_row` を見て
    #     「そんな腕は無い」と読んでいました。** 別の行として拾います。
    #     **読めなければ空**（＝「死んだ腕は無い」ではなく「読めない」）。
    inf_row: dict = {}
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
        if not inf_row and row.get("arm_dead_at_inf") is not None:
            inf_row = row
        if caps_row and hint_row and inf_row:
            break
    return arm_state({**caps_row,
                      # **新しいほうが勝つこと。** `caps_row` に古い
                      # `arm_dead_at_inf` が入っていても、こちらで上書きします。
                      **{k: v for k, v in inf_row.items()
                         if k in ("arm_dead_at_inf", "arm_need_over_cap",
                                  "lever_hint_measured")},
                      "lever_hint": hint_row.get("lever_hint"),
                      "binding": hint_row.get("binding")})


# ---------------------------------------------------------------------------
# **註ではなく門**（2026-09-02・最適化の回）
# ---------------------------------------------------------------------------

def blocked(lever: str | None, state: dict) -> list[str]:
    """**引いても到達日が動かないと分かっている腕**なら、断る文面を返す。

    空リスト ＝ 通す。`scripts/run_marker.py --ship` が、**書き込む前**に呼びます。

    ## なぜ門にしたか（**この回に自分で撃った数**・`data/runs.jsonl` 500行）

    `lever_notes()` は既にこの2つを印字していました。その docstring はこう
    言っています —— **「どちらも門ではありません」**。**その判断は正しく、
    そして `cap <= DEAD_CAP` の一般形については、いまも変えていません**
    （前提が未判定なら覆るため）。

    **覆らない2つだけを、ここで断ります**:

        RULE_DEAD      `density` …… オーナーが固定した 1日1本（`src/house_rule.py`）。
                       **覆る条件はありません**（外せるのはオーナーだけ）
        dead_at_inf    `sub_rate` …… `×10^9` まで引いても `days_to_target` が出ない。
                       **オーナー規則2: 答えがゼロなら、そこは律速ではない**

    **実測（2026-09-02 12:4x・`data/runs.jsonl` の ship 308件）**::

        density  を宣言した ship            76件
          うち 規則が乗った 08/31 以降       **12件**（moves 0 が 9・**-1 が 3**）
          そのうち kind=verdict             ** 4件**  ← **軌跡を動かす唯一の通貨**
        sub_rate を宣言した ship            ** 8件**（moves 0 が 7・**-4 が 1**）

    **註は毎回 出ていました。** それでも 20件 が通り、うち **4件 は負の
    `--moves`**（＝この腕を引けば到達日が早まる、という宣言）です。
    **その腕では、閉じた日に1日も動きません。** ＝ 註は効いていません
    （`scripts/run_marker.py` の「**註や警告ではなく、通さないことだけが
    効いています**」・2026-08-19 の `--lever` と同じ形。**この repo で2度目**）。

    ## どれだけ買うか（**手を決める前に答えること**）

    **到達日は 1日も早まりません** —— いまの軌跡は `出ません` で、θ を上げても
    `出ません` は `出ません` のままです（`scripts/eta.py`）。**それが上限で
    頭打ちになっているだけ**なので、そこで止めずに数えます:

        軌跡が動くのは前提を1件 閉じたときだけ（`per_video` 実測 1.0日に1件）。
        上の **verdict 4件** は、閉じても定義上 0日 の腕に落ちていました。
        ＝ **回転 4件ぶん**（`per_video` なら 20% の当たりで 0.8件）が消えています。

    **買うのは日付ではなく、日付を動かせる通貨のほう**です。

    ## 覆る条件

    - オーナーが 1日1本 を外したら、`density` はここから外れます
      （`arm_state` が `RULE_DEAD` を名乗らなくなるので、**自動で外れます**）。
    - `dead_at_inf` は `eta.py` が毎回 測り直します。出なくなれば通ります。
    - **`caps` が読めない行では、何も断りません**（「読めない」と
      「死んだ腕は無い」は別・`arm_state` の約束）。

    >>> blocked("density", {})            # 読めなければ通す
    []
    >>> blocked(None, {"dead_at_inf": ("sub_rate",)})
    []
    """
    if not lever or lever == "none":
        return []
    why = (state.get("dead_why") or {}).get(lever) or ""
    inf = lever in (state.get("dead_at_inf") or ())
    if not inf and not why.startswith(RULE_DEAD):
        return []
    out = [f"[marker] **断りました。`--lever {lever}` は記録していません。**"]
    if inf:
        out.append(f"         `{lever}` は**無限大にしても到達日が1日も動きません**"
                   "（`eta.py` の `LEVER_INF_SCALE` で `×10^9` まで実測）。"
                   " **オーナー規則2: 答えがゼロなら、そこは律速ではありません。**")
    else:
        out.append(f"         `{lever}` を止めているのは天井ではありません —— {why}")
    out.append("         **仕事を捨てろとは言っていません。** 断っているのは"
               "**腕の宣言のほう**です。出したものはそのまま、腕だけ選び直すこと:")
    hint = state.get("hint")
    if hint and hint in LEVERS and hint != lever:
        out.append(f"           `--lever {hint}`   ← いま名指しされている腕"
                   f"（床は {state.get('binding') or '（読めません）'}）")
    out.append("           `--lever none`   ← 道具・手順の整備。"
               "**これも正しい答えです**（`ship()` の註）")
    out.append("         **どちらでもないなら、この作業は到達日を動かしません。**"
               " そう書いて `none` にすること —— 嘘の腕を1件 積むより、"
               "**動かない回を1件 数えるほうが速い**です。")
    return out
