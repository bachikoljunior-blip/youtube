#!/usr/bin/env python3
"""**月20万円に、いつ届くか。毎回これを出してから作業を決める。**

    python scripts/eta.py              # 予測を出して data/eta.jsonl に積む
    python scripts/eta.py --no-record  # 出すだけ（積まない）
    python scripts/eta.py --offline    # API を叩かず、積んである最後の点から出す

## なぜ要るか（2026-08-19 オーナー指示 33699957）

> 実行の初めに、YouTube収益月収20万がいつ達成されるかを予測し、
> それを早めることを考えてから進めること。

**この指示は「見積もりを書け」ではありません。**「早めることを考えてから進め」＝
**その回の作業をどれにするかを、予測日を動かすかどうかで決めろ**、という意味に読みます。

そして**文書に手順として書くだけでは飛ばされます。**`docs/trigger_main.md` は
135KB あり、実際に §3 が読み飛ばされた記録があります（2026-08-18 23:4x）。
だから**道具にして、数字が勝手に出る形**にしました。

## この道具が答えるのは3つ

1. **いつ届くか**（いまの実測のまま伸ばしたら）
2. **どの数字が止めているか**（門を1つずつ当てて、最初に落ちるものを名指しする）
3. **いま考えている作業は、その日付を動かすか**（動かさないなら、やる理由がない）

## 天井の検査が本体です

いちばん効くのは (1) ではなく、**「いまの構成の上限は目標に届くのか」**です。

    1本あたりの再生 × **1日に再生が付く上限**（実測 10本。`src/day_cap.py`）× 30日 ÷ 1000 × RPM
    （**92本は API の日枠であって、再生が付く本数ではありません。** 2026-08-25 に分母を移しました）

これが 200,000 円に届かないなら、**本数を増やしても、在庫を増やしても、
予測日は永遠に来ません。** 増やすべきは本数ではなく、
**1本あたりの再生数か RPM のほう**です。**その判定を毎回やります。**

## 割り引いて読むこと

- **RPM は実測ではありません**（収益化前なので自分の数字が無い）。
  だから幅で出します。**この幅の中で結論が変わるなら、結論は出ていません**
- 登録率・1本あたり再生は**実測**（YouTube Analytics）。ここは推測ではありません
- ショートの視聴時間は 4,000時間の門に**入りません**。長尺の視聴時間だけが入ります
- **門2の「届きません」は、長尺の実力ではありません**（2026-08-19 12:0x に直した）。
  `days_long_hours` は直近365日の伸びを延ばした数なので、**長尺を1本も出していない限り
  必ず無限**になります。「長尺では開かない」と「まだ試していない」は別の命題です。
  だから最後の節が、**開けるのに要る「長尺1本あたり再生」**を逆算して出します
"""
from __future__ import annotations

import argparse
import functools
import json
import math
import os
import re
import subprocess
import sys
from collections import deque
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import arm_speed, day_cap, levers, motion_groups, rpm_mix, settle, subs_cap  # noqa: E402  （`sys.path` を通した後でないと読めません）

LOG = ROOT / "data" / "eta.jsonl"


def _ledger_reach(need_ratio: float) -> list[str]:
    """**要る倍率のとなりに、この台帳が実際に出した倍率を置く。**

    ## なぜ要るか（2026-08-26・最適化の回）

    上の表は「いちばん近い帯でも 1本あたり **N倍** 要る」と印字します。
    その N のとなりに何も無いので、**「あと少し」なのか「桁がちがう」のかが
    読めません。** 実測（`docs/JOURNAL.md` 直近7日）:
    **255件の ship のうち 204件（80%）が道具と手順**、
    到達日を動かすと宣言した回は **22件（8.6%）**。
    **サブは怠けていません** —— 一件ずつは全部まともな作業です。
    見えていなかったのは
    **「その作業の効き幅が、埋める穴に足りているか」**のほうです。

    ## **比べるのは同じ腕どうし**（ここを間違えると逆に読めます）

    上の「要る倍率」は **`per_video` の倍率**です。だから並べるのも
    **`per_video` の腕で閉じた前提の実績**にします。実測（2026-08-26）:

        per_video で閉じた       11件
        いちばん大きかった伸び   **×1.85**（題材の選び方。年金1,257回 対 残業代680回）
        ちょうど ×1.0            9件 / 11件

    いっぽう「いちばん近い帯」は **×18.1**。
    **この腕のいちばん良い一手を当てても、まだ 9.8倍 足りません。**

    ## **台帳ぜんたいの最大（×256）を、ここに使わないこと**

    閉じた前提の最大は `rpm` の **×256**
    （「同じ日の同じ本数で **ショート256回 対 長尺1回**」）。
    **これは伸びしろではありません。すでに取ってある差です** ——
    予約の **92%（315/342）がショート**で、こちらはとっくに勝っている側にいます。
    **もう一度 ×256 を取り直すことはできません。**
    この回に独立に測り直しても同じでした（齢48時間でそろえて
    **ショート 666.8回 対 長尺 2.8回 ＝ ×238**・n=71/12）。

    **だから ×256 を「台帳の実力」として読むと、
    「積み上げれば届く」という逆の結論が出ます。** 出しているのは
    **`per_video` の最大**のほうで、`rpm` の最大は註として別に印字します。

    ## この行が言っていること

    **「いま開いている `per_video` の前提を全部 閉じても、この帯には届きません」。**
    題の形・冒頭の絵・stat の置き方は本当に効く種類の改良ですが、
    **効き幅が ±2倍 の道具**で、**穴は 18倍**あります。**種類がちがう**だけです。
    届かせるには **効き幅が桁でちがう前提** ——
    ニッチ・尺・形式・面そのものを的にしたもの（腕 `rpm`）が要ります。

    ## 覆る条件

    - **`per_video` で `effect` が ×3 を超える前提が1件でも閉じたら**、読みは変わります。
      「±2倍 の道具しかない」が事実でなくなるので、**積み上げで届く道が出ます**
    - **`per_video_ratio` が 2倍 を下回ったら**（実測が伸びるか、帯が変われば起きる）、
      台帳の最大 ×1.85 が射程に入ります。**そのときはこの行を消してよい**
    - **効き幅は掛け算では積み上がりません。** ここは「いちばん良い一手」1件と
      比べているだけで、開いている件数ぶんの積を主張していません。
      **積を主張したくなったら、同じ腕の前提が独立かどうかを先に測ること**
      （いまは測っていません）
    """
    try:
        rows = arm_speed.closed()
    except Exception:                                          # noqa: BLE001
        return []
    pv = [r for r in rows if r.get("effect") is not None and r.get("lever") == "per_video"]
    if not pv:
        return []
    eff = [float(r["effect"]) for r in pv]
    best = max(eff)
    flat = sum(1 for e in eff if abs(e - 1.0) < 1e-9)
    out = [
        f"      **この腕（`per_video`）が実際に出した伸び: 最大 ×{best:,.2f}"
        f"（閉じた {len(eff)}件。うち **{flat}件** はちょうど ×1.00 ＝ 何も動かず）**",
    ]
    if best < need_ratio:
        out.append(
            f"      [!] **いちばん近い帯は ×{need_ratio:,.1f} 要ります。"
            f"この腕のいちばん良い一手（×{best:,.2f}）を当てても、まだ"
            f"**{need_ratio / best:,.1f}倍** 足りません** ——"
            "**開いている `per_video` の前提を全部 閉じても、この帯には届きません。**")
        out.append(
            "      題の形・冒頭の絵・stat の置き方は **効き幅が ±2倍 の道具**で、"
            "**穴は桁がちがいます。** 届かせるには"
            "**ニッチ・尺・形式そのもの**を的にした前提（腕 `rpm`）が要ります。")
    # **台帳ぜんたいの最大は、伸びしろではありません**（上の docstring）。
    # 註として、何だったのかを添えて出す —— 数字だけ出すと
    # 「積み上げれば届く」と逆に読めます。
    big = max((r for r in rows if r.get("effect") is not None),
              key=lambda r: float(r["effect"]), default=None)
    if big is not None and float(big["effect"]) > best:
        note = str(big.get("note") or "").splitlines()[0][:52]
        out.append(
            f"      註: 台帳ぜんたいの最大は `{big.get('lever')}` の"
            f" **×{float(big['effect']):,.0f}**（{note}）。"
            "**これは伸びしろではなく、すでに取ってある差です**"
            "（予約の 92% はもうショート側）。**足し込まないこと。**")
    return out


@functools.lru_cache(maxsize=1)
def _ready_by_claim() -> dict:
    """**前提ごとの「判定できる最早の日」**（`scripts/deadline_check.py`）。

    `scripts/` の中の兄弟なので、**遅延して**読みます —— この1本が壊れても
    到達予測そのものは出し続けること（呼び手が `except` で受けています）。

    **1回の実行で2か所が呼びます**（頭の θ の行と、`next_close`）。
    `deadline_check` は毎回モジュールごと読み直して予約と Analytics を当たるので、
    **2度読むと素直に2倍かかります。** 同じ回の中で答えは変わらないので
    `lru_cache` で1回に畳みます（2026-08-26）。
    """
    return _deadline_check_mod().ready_by_claim()


@functools.lru_cache(maxsize=1)
def _deadline_check_mod():
    """`scripts/deadline_check.py` を1回だけ読み込む。**兄弟なので遅延で。**"""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "eta_deadline_check", ROOT / "scripts" / "deadline_check.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eta_deadline_check"] = mod        # dataclass が __module__ を引きます
    spec.loader.exec_module(mod)
    return mod


@functools.lru_cache(maxsize=1)
def _unready_claims() -> set:
    """**判定できる日が出せない claim**（`deadline_check.unready_claims()`）。

    `_ready_by_claim()` はこれを黙って落とし、`next_close()` が
    その claim を **`deadline` のほうへ流していました** ——
    「今日が期限 ＝ **この回は `verdict` で日付が動かせます**」という嘘の頭3行が、
    判定に要る本が0本の日に出ます（2026-08-26 20:4x に踏んだ）。
    """
    mod = _deadline_check_mod()
    out = set(mod.unready_claims())
    # **「日は出た。今日だ。ただし読めるのは 16:00 から」も、ここで外すこと**
    #   （2026-08-28 03:1x に踏んだ。`deadline_check.not_open_yet` の註）。
    #   `Answer.ready` は日付なので **時刻がそこで落ちます** —— 落ちたぶん、
    #   その日の 00:00〜16:00 に走る回は全部この頭3行で
    #   「この回は `verdict` で日付が動かせます」と言われます（**16時間ぶん**）。
    #   同じ回に `status.py` は「いま判定できる前提: なし」と正しく出していました。
    try:
        out |= set(mod.not_open_yet())
    except Exception:                                          # noqa: BLE001
        pass                            # **読めないときは黙る**（門を増やさない）
    return out


#: `day_cap.cap()` の答えを、この走りのあいだ持ち回るための1組
#: `(そのとき呼んだ関数そのもの, その返り)`。**関数を持っておくのが本体**です（下）。
_DAY_CAP_MEMO: tuple | None = None


def _view_cap_per_day() -> float:
    """**1日に再生が付く本数の上限**（`src/day_cap.py`）を、1回だけ読む。

    ## なぜ要るか（2026-08-28 に測った。**軌跡の 38% がこの1行でした**）

    `day_cap.cap()` は `measure()` → `by_day()` と降りて、
    **`data/views.jsonl` を毎回まるごと読み直します**（実測 **59.1 ms/回**）。
    ところがこの関数は `analyse()` と `plan()` の**中**にあり、
    その2つは `trajectory()` のループが `t` の日数ぶん回します。実測::

        analyse           58.0 ms/回   ← **うち day_cap.cap() が 59.1 ms**（＝ほぼ全部）
        plan(sens=False)  93.6 ms/回   ← ここにも1回 入っている
        軌跡 base 1本     20.0秒 ＝ 約131回まわる

    **1回の `eta.py` で 1,000回 前後 読み直しています。** 答えは毎回同じです ——
    `eta.py` は `data/views.jsonl` に**1行も書きません**（積むのは `data/eta.jsonl` だけ）。

    畳んだ後の実測（同じ機械・同じ点）::

        plan(sensitivity=True)   4.1秒 → 1.1秒
        軌跡 base               20.0秒 → 2.7秒
        solve() 合計           107.5秒 → **16.6秒**（**-85%**）

    **`§2.6`（4分）も `--reflect` も `--alloc`（6分）も、同じ道を通ります。**
    直近8回の「設計の見直し」問い1 は、**7回が「道具が答えを返すのを待つところ」**
    （体感 4〜6割）でした。**穴ではなく、穴を作っている側**がここです。

    ## なぜ `lru_cache` ではないか（**検査が `day_cap.cap` を差し替えます**）

    `tests/_eta_pin.py` と `tests/test_eta_day_cap.py` は
    **同じ関数の中で `day_cap.cap` を 10 → 1,000 と差し替えて**、
    天井が効いているかを見ます。`lru_cache` だと2つ目が素通りします。

    だから**差し替えを見て畳み直します** —— 覚えているのは
    「どの関数から取った答えか」で、`day_cap.cap` が別の関数になったら取り直す。
    **関数そのものを持っておくこと**（`id()` で覚えると、
    差し替えが GC された後に同じ id が別の関数へ回って、静かに誤答します）。

    **覆る条件**: `eta.py` が走っている最中に `data/views.jsonl` が
    書き換わるようになったら、この畳み方は外すこと（いまは誰も書きません）。
    **`tests/test_eta_day_cap_memo.py` が、差し替えを見落としたら落とします。**
    """
    global _DAY_CAP_MEMO
    fn = day_cap.cap
    if _DAY_CAP_MEMO is None or _DAY_CAP_MEMO[0] is not fn:
        _DAY_CAP_MEMO = (fn, fn())
    return _DAY_CAP_MEMO[1]


# --- 門（YouTube の公表値。守るのではなく、通らないと収入が0になる事実）---
SUBS_GATE = 1_000
LONG_HOURS_GATE = 4_000          # 直近12か月・長尺のみ
SHORTS_VIEWS_GATE = 10_000_000   # 直近90日・ショート
TARGET_YEN = 200_000             # 月収の目標

# --- 1日に出せる本数の上限（実測。data/upload_cap.jsonl の窓と同じ）---
UPLOAD_CAP_PER_DAY = 92

# --- 公開の密度（1日に何本「公開」するか。投稿＝予約とは別物）---
#     いまの予約は 246本が39.5日に散って 1日6.4本。詰めれば25本（受け取り帳 3c7e12a3）
PUBLISH_SCENARIOS = (4, 10, 25, 92)

# --- いま計画している密度（受け取り帳 3c7e12a3 の詰め直しが着地する所）---
#     門2a の逆算は「門1 が通る日まで」で割るので、この1つを正本にします
PLAN_PUBLISH_PER_DAY = 25

# --- 収益化の審査にかかる日数（YouTube 公表「通常1か月以内」。**実測ではない**）---
MONETIZE_REVIEW_DAYS = 30

# --- 「月20万」は**流量ではなく、30日ぶんの合計**です（2026-08-20 08:1x に足した）---
#
# ここが無かったので、段4 の期日に **段3（収益化の審査が終わる日）をそのまま代入**
# していました（`d_target = d_monetized`）。印字は「月20万の到達見込み」ですが、
# **中身は収益化の日付**です —— オーナー追記（原文）:
#
#   > 勝手に20万達成以外の日時の予測だけにしないで
#
# 収益化した日に入るのは**その日ぶんの収入**であって、月20万ではありません。
# 月20万を名乗れるのは、**収益化してから30日ぶん積んだ合計**が20万を超えた日です。
# 収益化前の再生は1円も生まないので、この30日は前借りできません。
REVENUE_WINDOW_DAYS = 30

# --- 段取りを立てるときに使う RPM は、その形の**いちばん低い帯** ---
#     `RPM_SCENARIOS` の 低/中/高 は「別の道」ではなく**同じニッチの幅**です。
#     いちばん高い帯で段取りを立てると、**計画そのものが上振れ側に乗ります**
#     （倍率の小さい帯を選ぶ `nearest` の論法をそのまま使うと、必ず「高」が出ます）。
PLAN_BAND_BY_FORM = {"ショート": "ショート 低", "長尺 お金": "長尺 お金 低"}

# --- RPM の幅（**実測ではない**。収益化前なので自分の数字が無い）---
RPM_SCENARIOS = {
    "ショート 低": 20,
    "ショート 中": 35,
    "ショート 高": 60,
    "長尺 お金 低": 400,
    "長尺 お金 中": 1_000,
    "長尺 お金 高": 2_000,
}

# --- 「長尺」と呼ぶ尺の下限（秒）---
#     Analytics は尺を返さないので、**平均視聴秒 ÷ 平均視聴率**で尺を復元して割ります
#     （`averageViewDuration / (averageViewPercentage/100)`）。ショートの上限は60秒、
#     この作りの長尺は4分以上（`src/verify.py`）なので、あいだの180秒に置いています。
LONG_FORM_SECONDS = 180

# --- 長尺1本が生む視聴分（**推測**。長尺の実測が無いので、尺×維持率で置く）---
#     ショートの実測は「1再生あたり22秒 ＝ 尺の49%」（2026-08-19 status.py）。
#     長尺は WATCH が通算13回しかないので、維持率を測れません。
#     **だから幅で置きます。** 低いほう（20%）で足りるなら、幅の中のどこでも足ります。
LONG_SHAPES = (
    ("尺4分・維持20%", 4, 0.20),
    ("尺5分・維持40%", 5, 0.40),
    ("尺7分・維持40%", 7, 0.40),
)

# --- 門2a を長尺で開けるとき、1日に何本の長尺を足すか ---
LONG_PER_DAY_SCENARIOS = (1, 2, 4)

NEVER = 10 ** 9  # 「届かない」を日数で表すときの番人

#: **凍らせた線（`frozen_days`）を、この走りで測るか。**（2026-08-26）
#:
#: **引数ではなく旗で持っています。** `solve(m, points)` の形は
#: `tests/test_eta_reflect.py` など**6つの検査が monkeypatch で差し替えて**おり、
#: キーワード引数を足した版は `TypeError` で7件 落ちました（同日に踏んだ）。
#: **呼び口の形は、検査ごと動かさないこと。**
#:
#: 落とすのは2か所だけです —— `--no-frozen` と、`--reflect`
#: （積み直すのは日付で、**腕の要否は問うていない**。軌跡1〜2本ぶんの節約）。
FROZEN_ARMS = True

# --- **1本あたり再生の標本に、入れてよい本の条件**（2026-08-20 03:1x に足した） ---
#
# **伸びきるまでに要る時間**（`data/views.jsonl` を実測。n=9 ＝ 最後の観測が
# 168時間より後で、かつ 100再生を超えた本だけ）:
#
#       6時間  中央値  0.0%      36時間  中央値  98.8%
#      12時間  中央値 77.6%      48時間  中央値 100.0%
#      24時間  中央値 99.1%     168時間  中央値 100.0%
#
# **48時間で伸びが終わります。** だから「まだ48時間経っていない本」を標本に入れると、
# その本は**一生ぶんではなく数時間ぶん**を持って平均に入り、天井を下振れさせます。
#
# **この数はここでは定義しません（2026-08-26）。** 同じ「いつ確定するか」を
# `src/ab_split.py` が `SETTLE_DAYS = 7`（勘）で別に持っていて、**判定の門はそちらだけを
# 読んでいました。** 実測と定義は `src/settle.py` に1か所へ寄せてあります
# （そこに「標本に入れる年齢」と「判定を待つ日数」が**なぜ違う数なのか**も書いてあります）。
MATURE_HOURS = settle.MATURE_HOURS


# --- **測定が返ってくる日**（2026-08-20 07:1x に足した） ---
#
# `blocking`（段取りを止めている未測定の入力）は「**どう測るか**」は書きますが、
# **「いつ答えが返るか」を1行も書いていませんでした。** そこが空いていたので、
# 測定の的にする日は「穴の空いている日」——つまり**公開の断絶を埋める都合**——で
# 選ばれていました（08/19 の申し送りは 3回続けて `--date 2026-09-02`）。
#
# **穴埋めと測定は、別の仕事です。** 穴埋めは「いつ埋めても同じ」ですが、
# 測定は**遅らせたぶんだけ段取り全体が遅れます**。実測（`data/uploaded.jsonl`・
# 2026-08-20 時点）では、いちばん近い穴は **09/02** で、いちばん早く予約できる日
# （明日）との差は **12日**。答えが返るのが 12日 遅くなります。
#
# 答えが返るまでにかかる日数は、この2つの和です:
#
#     公開 → 伸びきる    MATURE_HOURS（48時間）= 2日   `drop_unripe` が標本に入れる条件
#     伸びきる → 読める  ANALYTICS_LAG_DAYS（**実測**。`src/settle.py`）  Analytics は日次で遅れる
#
# **覆る条件**: 日枠が朝のうちに開いている回なら「今日」も予約できるので、
# `soonest` は1日早くなります。ここは**閉じている側に倒して**明日から数えています
# （名指しした日に予約できないほうが損なので）。
# **この数もここでは決めません（2026-08-26）。** 同じ「Analytics の遅れ」を
# `scripts/deadline_check.py` が `data/analytics_lag.jsonl` の実測から出していて
# （その日は **4日**）、`src/judgeable.py` は `= 3` のべた書きでした。
# **A/B 4件だけ1日 楽観**に出ていたのが、そのべた書きです。ここが最後の1か所。
#
# 1日 楽観だと、`answer_day()` が「測定の答えが返る日」を1日早く名指しします ——
# **その日に見にいっても、まだ数字はありません。**
ANALYTICS_LAG_DAYS = settle.analytics_lag_days()

# --- **長尺の標本が「薄い」と「無い」は別です**（2026-08-25 に直した） ---
#
# 合格点が推測になっている状態（`proxy`）の条件は、長らく裸の `n_long < 20` でした。
# **閾値そのものは正しい**（標本が薄いあいだ平均は暴れる）のに、`blocking` の文面が
#
#     「（n=14・**登録者が9人だった頃の標本**）」
#     「**まだ一度も測り直していない**」
#
# と**固定文字列**で書いてありました。**どちらも事実ではありません。**
# `measured()` は毎回 Analytics から `long_per_video` を取り直しており、
# **同じ画面の別の節が「長尺の1本あたり再生は測れています: 1本 4.0回
# （直近28日・n=14・合計 59回）」と印字しています。** 1つの出力が、
# 同じ数について「測っていない」と「測れています」を同時に言っていました。
#
# **何を損したか。** `blocking` は「次の回が何をするか」を決めるための欄です
# （すぐ下の註「計画を空にしない」）。そこが「測り直していない → 長尺を出して
# 測り直せ」と言い、`measure_targets()` が日付まで添えるので、
# **もう答えの返ってくる測定に、1回ぶんの ship を使わせます。**
# 2026-08-25 の実測では、長尺は**10本が予約済み**（08/25・08/26×2・08/27・
# 08/28×2・09/09・09/11・09/15・09/19）でした。
#
# **覆る条件**: `split_per_video()` が 0再生の長尺も標本に入れるようになったら、
# `long_sample_forecast()` の返す日は「最早」ではなく実際の日と一致します
# （いまは 0再生の本が標本に入らないぶん、上限側に寄っています）。
LONG_SAMPLE_MIN = 20

# **予約の日付は全部 JST です。**`date.today()` はコンテナの TZ（＝UTC）を読むので、
# **JST の 00:00〜09:00 は前日を返します。** 2026-08-20 07:1x（JST）に足したこの節が、
# 最初の版で「いちばん早く予約できる日 ＝ 08/20」と印字しました。08/20 は
# **その時点で既に今日**（しかも 25本 予約済み）で、明日ではありません。
JST = timezone(timedelta(hours=9))


def today_jst() -> date:
    return datetime.now(JST).date()


def answer_day(publish: date) -> date:
    """その日に**公開**した本の1本あたり再生を、**読めるようになる日**（JST）。"""
    return publish + timedelta(days=math.ceil(MATURE_HOURS / 24) + ANALYTICS_LAG_DAYS)


def measure_targets(today: date, uploaded_path: Path | None = None) -> dict:
    """測定の的にできる2つの日と、**選び方で失う日数**を出す。

    - `soonest` …… いちばん早く予約できる日（**明日**。上の「覆る条件」）
    - `hole`    …… いちばん近い「予約が0本の日」＝**穴埋めの手順が選ぶ日**
    - `days_lost` …… `hole` を選ぶと、答えが何日遅れるか

    穴が無ければ `hole` は `None`（そのときは失うものもありません）。
    """
    uploaded_path = uploaded_path or (ROOT / "data" / "uploaded.jsonl")
    booked: set[date] = set()
    if uploaded_path.exists():
        for line in uploaded_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            at = row.get("at")
            if not at:
                continue
            try:
                d = datetime.fromisoformat(str(at).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            booked.add(d.date())

    soonest = today + timedelta(days=1)
    hole: date | None = None
    # **予約が1件も無ければ「穴」はありません。** 空を「全部が穴」と読むと、
    # `soonest` 自身が穴として返り、差が 0日 なのに競合しているように見えます。
    last = max(booked) if booked else None
    day = soonest
    while last is not None and day <= last:
        if day not in booked:
            hole = day
            break
        day += timedelta(days=1)

    ans_soon = answer_day(soonest)
    out = {
        "soonest": soonest, "answer_soonest": ans_soon,
        "hole": hole, "answer_hole": answer_day(hole) if hole else None,
        "days_lost": (hole - soonest).days if hole else 0,
    }
    return out


def long_sample_forecast(today: date, n_now: int,
                         uploaded_path: Path | None = None) -> dict:
    """**予約済みの長尺だけで、標本が `LONG_SAMPLE_MIN` に届くか。**

    `blocking` が「長尺を出して測り直せ」と言うたびに、**その測定がもう
    予約済みかどうかは誰も見ていませんでした。** ここが空いている間、
    「予約済みの本を待てば返ってくる答え」に 1回ぶんの ship が使えます。

    返すのは:

        need      あと何本、標本に足りないか（`LONG_SAMPLE_MIN - n_now`）
        booked    まだ読めていない長尺の予約（**読める日の昇順**）
        reaches   `need` 本目が**読めるようになる日**（足りなければ `None`）
        short_by  予約だけでは足りない本数（足りていれば 0）

    ## **これは「最早」です**（上限側に寄っています）

    `split_per_video()` が見るのは **Analytics が返した本だけ**で、
    **0再生の長尺は標本に入りません。** 長尺の実測は 1本 4回なので、
    0 の本は必ず出ます。だから実際の n は、ここが言う日より**遅れて**届きます。
    **「この日には必ず n が埋まる」と読まないこと。**

    ## 帳面の読み手を増やしていません

    `data/uploaded.jsonl` は「後の行を採る・JST で割る」の2規則を要求しますが、
    それを別々に持った読み手が既に3つあります（`docs/JOURNAL.md` 2026-08-25）。
    ここは **`src.motion_groups` の `scheduled_at()` / `topic_by_video()` /
    `jst_day()` を借ります** —— 4つ目の読み手を書かないこと。
    """
    up = uploaded_path or (ROOT / "data" / "uploaded.jsonl")
    at = motion_groups.scheduled_at(up)
    topics = motion_groups.topic_by_video(up)

    booked: list[dict] = []
    for vid, when in at.items():
        tid = topics.get(vid, "")
        # ショートは `s-` で始まるIDを、その場で作って付けます
        # （`src/pipeline.py` の同じ判定）。長尺だけを数えます。
        if str(tid).startswith("s-"):
            continue
        day = motion_groups.jst_day(when)
        if not day:
            continue
        pub = date.fromisoformat(day)
        ans = answer_day(pub)
        # **もう読める本は、標本の n にもう入っています。** ここで二重に数えない
        if ans <= today:
            continue
        booked.append({"video_id": vid, "topic": tid, "publish": pub, "answer": ans})
    booked.sort(key=lambda r: (r["answer"], r["publish"], r["video_id"]))

    need = max(0, LONG_SAMPLE_MIN - int(n_now or 0))
    if need == 0:
        return {"need": 0, "booked": booked, "reaches": None, "short_by": 0}
    if len(booked) >= need:
        return {"need": need, "booked": booked,
                "reaches": booked[need - 1]["answer"], "short_by": 0}
    return {"need": need, "booked": booked,
            "reaches": None, "short_by": need - len(booked)}


def published_at(views_path: Path | None = None,
                 uploaded_path: Path | None = None) -> dict[str, datetime]:
    """`video_id` → **公開時刻**（UTC）。

    ## 出どころは2つ。**順番に意味があります**

    1. `data/views.jsonl` の `at - hours`（`hours` は公開からの経過時間）。
       **観測のたびに追記されるので、いちばん古い行がいちばん正確**です。
       `scripts/per_day_views.py` が同じ復元をしています
    2. `data/uploaded.jsonl` の `at`（**予約した公開時刻**）。1 に無い本 ——
       つまり**まだ一度も観測されていない本**は、ここでしか年齢が分かりません。
       **同じ本の行が2つあるときは、後の行を採ります**（下の註）

    **`src/build_perf.py` の `first_seen()` とは別物です。** あちらは
    「最初に観測した時刻」で、こちらは「公開した時刻」。観測は公開の後なので、
    `first_seen` は必ず遅れます（実測で最大 38.7時間）。
    **年齢の門に使うなら、遅れるほうを使ってはいけません。**
    """
    views_path = views_path or (ROOT / "data" / "views.jsonl")
    uploaded_path = uploaded_path or (ROOT / "data" / "uploaded.jsonl")
    out: dict[str, datetime] = {}

    def _parse(v) -> datetime | None:
        try:
            d = datetime.fromisoformat(str(v).replace("Z", "+00:00"))
        except (ValueError, TypeError):
            return None
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)

    if views_path.exists():
        for line in views_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = row.get("id") or row.get("video_id")
            at = _parse(row.get("at"))
            hours = row.get("hours")
            if not vid or at is None or hours is None:
                continue
            try:
                born = at - timedelta(hours=float(hours))
            except (TypeError, ValueError):
                continue
            # いちばん古い観測が、いちばん正確（誤差は観測の間隔ぶんしか無い）
            if vid not in out or born < out[vid]:
                out[vid] = born

    if uploaded_path.exists():
        # **控えは1行1件ではなく、1本1件**（2026-08-25 に `src/ab_split.published()`
        # が同じことを書いています）。`uploaded.jsonl` は足すだけの帳面で、
        # 予約を動かすと**同じ `video_id` の行がもう1行足されます**
        # （実測 505行 / 実物 491本 —— 14本が2つの `at` を持つ）。
        # **採るのは後の行。** 最初の行は「投稿したときの予約」＝すでに
        # 動かされた過去の予定です。ここは `setdefault` で**最初の行**を
        # 採っていたので、その14本だけ公開時刻が古いままでした。
        #
        # 実測（2026-08-25）: 14本とも `views.jsonl` に無い＝この控えが唯一の
        # 出どころで、JST の日で数えた本数が **09/20 7→9・09/21 8→10・
        # 09/23 8→7・09/24 8→5** とずれていました。09/21 は上限
        # （`src/day_cap.py` ＝ 10本/日）**ちょうど**なので、直す前は
        # **埋まっている日に空きが2つ見えていました**（`density` の腕そのもの）。
        #
        # 覆る条件: 控えが「足すだけ」でなくなり、動かした行で
        # 上書きするようになったら、後の行を採る理由は消えます。
        ledger: dict[str, datetime] = {}
        for line in uploaded_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            vid = row.get("video_id")
            at = _parse(row.get("at"))
            if vid and at is not None:
                ledger[vid] = at          # **後の行で上書きする**
        for vid, at in ledger.items():
            out.setdefault(vid, at)       # 1 のほうが正確なので、上書きしない
    return out


def drop_unripe(rows, pub: dict[str, datetime], now: datetime,
                window_days: int = 28) -> tuple[list, dict[str, list[str]]]:
    """**1本あたり再生の標本から、数えてはいけない本を落とす。**

    返すのは `(残した行, 落とした理由 → video_id の一覧)`。

    ## なぜ要るか（2026-08-20 03:1x。**実測で見つけました**）

    天井は `1本あたり再生 × 再生が付く上限（実測10本/日）× 30日` です。この `1本あたり再生` は
    **「1本が一生に集める再生数」**でなければ、掛け算が意味を持ちません。
    ところが測っていたのは **「直近28日の窓に落ちた再生数」**で、
    次の2つが混ざっていました。

    **(1) まだ公開されていない本**（`未公開`）。実測 2本 —— `KdlvGxloIg4` は
    `uploaded.jsonl` の `at` が **08/24**（予約）で、Analytics には
    **1再生**の行が立っています。**予約は 359本あります。**
    そのうち何本かが1再生ずつ漏れて標本に入るたび、平均は 0 のほうへ引かれます。
    **本数を増やすほど天井が下がる**という、向きの逆さまな計器になります。

    **(2) 公開から48時間が経っていない本**（`未熟`）。上の `MATURE_HOURS` の実測どおり、
    48時間で伸びは終わります。**それより若い本は、一生ぶんではなく数時間ぶん**を
    持って平均に入ります。

    **(3) 窓より前に公開された本**（`窓の外`）。いまは1本もいませんが、
    **08/22 ごろから出ます** —— 08/06 の本は、窓が動けば「28日窓の中の再生 ≒ 0」に
    なります。伸びは48時間で終わっているので、**残っているのは尻尾だけ**です。
    それを「1本あたり」として平均に入れると、**チャンネルが古くなるだけで
    天井が下がり続けます。**

    ## 落とし先が無くなったら、落とさない

    `views.jsonl` は Data API の読みで作られるので、**日枠が閉じた窓では更新が止まります**
    （実測: 08/18 09:08 で止まったまま 1.7日）。**年齢の出どころが全部欠けたときに
    標本を空にすると、この道具の本体（天井）が黙って 0 になります。**
    そのときは**落とさずに全部返し、理由に `落とし先なし` を立てます。**
    """
    kept: list = []
    dropped: dict[str, list[str]] = {"未公開": [], "未熟": [], "窓の外": []}
    ripe_before = now - timedelta(hours=MATURE_HOURS)
    window_open = now - timedelta(days=window_days)
    for r in rows:
        vid = r[0]
        born = pub.get(vid)
        if born is None or born > now:
            dropped["未公開"].append(vid)
        elif born > ripe_before:
            dropped["未熟"].append(vid)
        elif born < window_open:
            dropped["窓の外"].append(vid)
        else:
            kept.append(r)
    if not kept:
        return list(rows), {"落とし先なし": [r[0] for r in rows]}
    return kept, {k: v for k, v in dropped.items() if v}


def split_per_video(rows) -> tuple[list[int], list[int]]:
    """`dimensions=video` の行を、**尺で2つに割る**（2026-08-19 14:2x に足した）。

    返すのは `(ショートの再生・昇順, 長尺の再生・昇順)`。

    ## なぜ割るか

    ここは長らく1行でした ——

        vals = sorted(r[1] for r in per_video if r[1] >= 30)

    **その `>= 30` が、長尺を5本とも落としていました。** 実測は 4/3/2/1/1回で、
    **30を超える長尺は1本もありません。** 落ちた結果 `median_views_per_video` は
    **ショートだけの中央値（1,092回）**になり、天井の表がそれを長尺の帯にも当てて
    **「長尺 お金 中 … 届く／いまの 0.1倍」**と印字していました。
    **長尺の実測を当てると 36倍**です。**桁が2つちがい、向きが逆になります。**

    28b90d6 が門2a で塞いだのと同じ形（「まだ試していない」が
    「もう届いている」に化ける）が、**円の側に残っていました。**

    ## 尺の出し方

    Analytics は尺そのものを返しません。**平均視聴秒 ÷ 平均視聴率**で復元します。
    `averageViewPercentage` が 0 の行は割れないので、**ショート側**に置きます
    （長尺に置くと、測れていない行が長尺の中央値を下げます）。

    **長尺には 30再生の床を当てません。** 当てると1本も残らず、
    「測っていない」と「0だった」の区別がつかなくなります。

    ## **ショートの床も外しました**（2026-08-19 15:0x）

    ここは `elif views >= 30` でした。**床は標本からは落としますが、
    天井の掛け算からは落としません。** 天井は

        1本あたり再生 × **再生が付く上限（実測10本/日）** × 30日

    で、この本数は「作った本数」です。**床を通った本だけの数字を、
    落ちた本まで含む本数に掛けている**ので、
    **落ちた本が全部「通った本と同じだけ回る」ことになっていました。**

    **同じ形が、分母そのものにも残っていました**（2026-08-25 に直した）。
    ここは長らく `UPLOAD_CAP_PER_DAY = 92`（API の日枠）を掛けていましたが、
    実測は **10本/日**で、**それを超えて出したぶんは 0再生**です
    （`src/day_cap.py`）。**床の話より1桁大きい版**でした。

    実測（直近28日・ショート22本）: 床を通ったのは20本で、
    落ちた2本は**1回ずつ**。**床は「まだ伸びていない本」を落とすつもりの道具でしたが、
    見ているのは年齢ではなく再生数**なので、伸びなかった本と区別がつきません。

    落とすなら**本数のほうも同じ割合で削る**必要があり、それは結局
    **全部を平均する**のと同じです（`_measure` の平均）。
    """
    shorts: list[int] = []
    longs: list[int] = []
    for row in rows:
        views = row[1]
        avg_sec = row[2] if len(row) > 2 else 0
        avg_pct = row[3] if len(row) > 3 else 0
        seconds = (avg_sec / (avg_pct / 100)) if avg_pct else 0.0
        if seconds >= LONG_FORM_SECONDS:
            longs.append(views)
        else:
            shorts.append(views)
    return sorted(shorts), sorted(longs)


def live_band_views(rows, published=None, forms=None) -> list[int]:
    """**再生が付く帯に居た本だけ**の、1本あたり再生（ショート・昇順）。API 0単位。

    `rows` は `dimensions=video` の Analytics の行（`row[0]` が video_id）。
    帯は `src/day_cap.live_ids()`（間隔 → その日の先頭 `cap()` 本）で引きます。
    **上限を測っているのと同じ2段**なので、天井の掛け算と分母がそろいます。

    ## なぜ要るか（2026-08-29 に測って足した。**天井が同じ死を2回 数えていました**）

    天井は

        1本あたり再生 **×** 再生が付く上限（実測 10本/日・`src/day_cap.py`）**×** 30日

    です。**右の 10本/日 が「上限を超えて出した本は 0再生」を既に言っています。**
    ところが左の「1本あたり再生」は、**その死んだ本を分母に入れたままの平均**でした。
    **同じ死を、式の左と右で2回 引いています。**

    実測（`data/views.jsonl`・齢48時間 以上の 168本。2026-08-29）:

        0再生            24本   合計       0
        1〜9再生         42本   合計     126   ← **Analytics には出ます**（分母に入る）
        10〜49再生        4本   合計     105
        50再生 以上      98本   合計  69,081

    **1〜9再生 の 42本は、分母の 29% を占めて、再生の 0.18% しか持っていません。**
    薄まったぶんだけ天井が下がり、`eta.py` は7日の差を
    **「出すほど天井が下がります」**と印字していました。**それは実績ではなく、
    上限を 2.3倍 超えて出したぶんが平均を薄めた跡**です。

    帯で割った実測（同じ168本）:

        帯の中  n=84  平均 **678回**      帯の外  n=84  平均 168回
        帯の中で実際に生きた（50再生 以上） **82/84**（98%）
        帯の外で死んだ **68/84**（81%）  ← 一致 150/168 ＝ **89%**

    公開日ごとに見ると、**生きた本数は出した本数によらず 10本 前後で止まります**:

        08/20  25本 → 生 10本 / 6,445再生      08/23  13本 → 生 10本 / 10,232再生
        08/21  32本 → 生 11本 / 6,791再生      08/24  10本 → 生 10本 /  8,386再生
        08/22  25本 → 生 10本 / 5,892再生

    **32本 出した日より、10〜13本 の日のほうが再生は多い。** 分母だけが増えています。

    ## この関数が言えないこと

    - **帯は公開時刻から引いた予測**で、実測の生死ではありません（89% で一致）。
      帯の外で生きた 16本 を捨てているので、**帯の中の平均は上振れ側**です。
    - **長尺は帯に入れません**（`cap()` が測っているのはショートの面で、
      長尺はその枠を1つも使わないため）。落とすのは `day_cap.live_ids()` の
      既定になりました（2026-08-30。それまでは**ここだけが手前で落として**いて、
      他の呼び手は落としていませんでした）。**ここの前置きは二重ですが残します**
      —— `forms` を差し替えて呼ぶ道（検査・比べ物）が、この引数に乗っています。

    **覆る条件**: `day_cap.measure()` の `cap` が上がれば帯は自動で広がります。
    帯の中の平均が、帯の外の平均の **2倍 を下回ったら**、この切り方は効いていません
    （いまは 678 対 168 ＝ **4.0倍**）。そのときは分母を戻すこと。
    """
    try:
        from src import ab_split, day_cap
    except Exception:
        return []
    try:
        long_ids = day_cap._long_ids(forms)
        pub = published if published is not None else ab_split.published()
        band = day_cap.live_ids([r for r in pub
                                 if str(r.get("video_id") or "") not in long_ids])
    except Exception:
        return []
    if not band:
        return []
    shorts, _ = split_per_video([r for r in rows if str(r[0]) in band])
    return shorts


def _measure() -> dict:
    """YouTube Analytics から、予測に要る実測値だけを取る。"""
    from googleapiclient.discovery import build
    from src.auth import credentials

    analytics = build("youtubeAnalytics", "v2", credentials=credentials(), cache_discovery=False)
    end = date.today()

    def q(days: int, metrics: str, **kw) -> list:
        start = end - timedelta(days=days)
        res = analytics.reports().query(
            ids="channel==MINE", startDate=start.isoformat(), endDate=end.isoformat(),
            metrics=metrics, **kw,
        ).execute()
        return res.get("rows") or []

    base = "views,estimatedMinutesWatched,subscribersGained,subscribersLost"
    all_rows = q(3650, base)
    d90 = q(90, base)
    d28 = q(28, base)
    d7 = q(7, base)

    # 長尺の視聴時間は流入経路では割れない。再生場所（SHORTS_FEED か否か）で割る。
    place = q(365, "views,estimatedMinutesWatched", dimensions="insightPlaybackLocationType")
    long_minutes_365 = sum(r[2] for r in place if r[0] != "SHORTS_FEED")
    shorts_views_90 = 0
    place90 = q(90, "views,estimatedMinutesWatched", dimensions="insightPlaybackLocationType")
    shorts_views_90 = sum(r[1] for r in place90 if r[0] == "SHORTS_FEED")

    # 1本あたりの再生（直近28日に再生のあった本の中央値）。
    #
    # **形ごとに別々に出すこと**（2026-08-19 14:2x に足した）。ここは長らく
    # `if r[1] >= 30` の1本だけで、**その30が長尺を5本とも落としていました** ——
    # 実測は 4/3/2/1/1再生で、**30を超える長尺は1本もありません。**
    # 落ちた結果 `median_views_per_video` は**ショートだけの数**になり、
    # それを天井の表が長尺の帯にも当てて **「長尺 お金 中 … 届く」** と印字していました。
    # **「まだ試していない」を「もう届いている」と読み替える形**で、
    # 28b90d6 が門2a で塞いだ穴と同じものが、円の側に残っていました。
    #
    # 尺は Analytics では取れないので、**平均視聴秒 ÷ 平均視聴率**で復元します。
    per_video = q(28, "views,averageViewDuration,averageViewPercentage",
                  dimensions="video", sort="-views", maxResults=200)
    # **標本に入れてよい本だけにする**（2026-08-20 03:1x。`drop_unripe` に理由）。
    # 予約したまま公開されていない本と、公開から48時間が経っていない本は、
    # **一生ぶんではない再生数**を持って平均に入り、天井を下振れさせます。
    per_video, unripe = drop_unripe(per_video, published_at(),
                                    datetime.now(timezone.utc), window_days=28)
    vals, long_sorted = split_per_video(per_video)
    median_views = vals[len(vals) // 2] if vals else 0
    long_median = long_sorted[len(long_sorted) // 2] if long_sorted else None
    # **天井が要るのは中央値ではなく平均です**（2026-08-19 15:0x に直した）。
    # 天井は「N本ぶんの**合計**」なので、合計 ＝ N × **平均**。
    # 中央値を掛けてよいのは分布が対称なときだけで、ショートの再生は必ず右に歪みます。
    # 実測（直近28日・ショート22本）: 中央値 1,092 に対し **平均 909**（**17%の差**）。
    # そして「いちばん近い帯」の倍率は **1.1倍 → 1.33倍** に変わります。
    mean_views = round(sum(vals) / len(vals)) if vals else 0
    long_mean = round(sum(long_sorted) / len(long_sorted)) if long_sorted else None
    live_vals = live_band_views(per_video)
    live_mean = round(sum(live_vals) / len(live_vals)) if live_vals else None

    def row(rows, i):
        return rows[0][i] if rows else 0

    return {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subs_net": row(all_rows, 2) - row(all_rows, 3),
        "views_all": row(all_rows, 0),
        "views_7d": row(d7, 0),
        "views_28d": row(d28, 0),
        "views_90d": row(d90, 0),
        "subs_gained_28d": row(d28, 2),
        "subs_gained_90d": row(d90, 2),
        "long_hours_365": round(long_minutes_365 / 60, 1),
        "shorts_views_90d": shorts_views_90,
        # **天井を動かすのはこちら**（平均）。中央値は「典型的な1本」用に残します。
        "views_per_video": mean_views,
        "median_views_per_video": median_views,
        "videos_with_views_28d": len(vals),
        # **天井の分母は、再生が付く帯に居た本だけ**（2026-08-29 に足した。
        # `live_band_views` の docstring に、なぜ薄めた平均だと二重に数えるか）。
        # `None` ＝ 帯が引けなかった（`data/uploaded.jsonl` が無い等）。**その回は前の式に落ちます。**
        "views_per_video_live": live_mean,
        "videos_live_28d": len(live_vals) if live_vals else 0,
        # **長尺だけの1本あたり再生**（`None` ＝ 直近28日に長尺の再生が1本も無い）
        "long_per_video": long_mean,
        "long_median_per_video": long_median,
        "long_videos_28d": len(long_sorted),
        "long_views_28d": sum(long_sorted),
        # **標本から落とした本**（理由 → 本数）。0件でも鍵は残す（黙って消えないため）
        "per_video_dropped": {k: len(v) for k, v in unripe.items()},
    }


def _per_video(m: dict) -> float:
    """1本あたり再生（ショート）。**天井を動かす数なので、平均のほうを使います。**

    **採るのは「再生が付く帯に居た本だけ」の平均**です（2026-08-29 に直した。
    理由と実測は `live_band_views` の docstring）。天井は
    `1本あたり再生 × 再生が付く上限（10本/日） × 30日` なので、
    **上限を超えて死んだ本を分母にも入れると、同じ死を2回 引きます。**

    落ちる先は2段:

        views_per_video_live  帯の中だけの平均（**この点から既定**）
        views_per_video       帯を引けなかった点・2026-08-29 より前の点
        median_views_per_video  `views_per_video` も無い古い点（8点目まで）

    **無い点を 0 と読むと、差の節が「1,092 → 0」＝ -100% と印字します**ので、
    落ちる先を中央値に置いています。**中央値は上振れ側**なので、
    古い点との差は「縮んだ」側に寄って見えることに注意すること。
    """
    live = m.get("views_per_video_live")
    if live:
        return live
    v = m.get("views_per_video")
    return v if v is not None else m.get("median_views_per_video", 0)


def _days_to(need: float, per_day: float) -> float:
    """必要量と1日あたりから日数。進んでいないなら NEVER。"""
    if need <= 0:
        return 0.0
    if per_day <= 0:
        return NEVER
    days = need / per_day
    # 100年より先は「届かない」と同じに畳む。**桁の大きい数を残すと、
    # 前の回との差（縮んだぶん）がその桁に埋もれて読めなくなります。**
    return NEVER if days > 36_500 else days


def _print_dropped(P, m: dict) -> None:
    """**標本から何本落としたか**を、天井の行のすぐ下に出す（2026-08-20 03:1x）。

    ここは長らく、こう**断って済ませて**いました ——

        **下振れ側で読むこと** —— 直近数日に公開した本はまだ伸びきっていないので、
        平均はその分だけ低く出ます。

    **断りは、下振れの大きさを言いません。**（実測では 869 → 952 ＝ **+9.6%**、
    いちばん近い帯までの倍率が **1.4倍 → 1.27倍**）。**測って落とせるものでした。**
    """
    dropped = m.get("per_video_dropped") or {}
    if not dropped:
        P("      （標本から落とした本はありません）")
        return
    if "落とし先なし" in dropped:
        P(f"      [!] **年齢が1本も引けませんでした**（{dropped['落とし先なし']}本）。"
          "`data/views.jsonl` が古い可能性 → **落とさずに全部数えています。下振れ側で読むこと。**")
        return
    order = ("未公開", "未熟", "窓の外")
    why = {
        "未公開": "**まだ公開されていない**（予約のまま Analytics に行が立つ。予約は 359本ある）",
        "未熟": f"公開から **{MATURE_HOURS}時間**が経っていない（伸びが終わっていない）",
        "窓の外": "**28日の窓より前**に公開（窓に落ちているのは伸びた後の尻尾だけ）",
    }
    P("      標本から落とした本（**一生ぶんの再生数を持っていない本**）:")
    for k in order:
        if dropped.get(k):
            P(f"        {k}  {dropped[k]}本 …… {why[k]}")


def _fmt_days(days: float) -> str:
    if days >= NEVER:
        return "**届きません**（いまの速さでは増えていない）"
    if days <= 0:
        return "**通過済み**"
    if days > 36_500:  # 100年より先は、日付を書いても意味がない
        return f"**{days/365:,.0f}年後 ＝ 事実上いまの形では届きません**"
    # **JST で数えること。** この器は UTC なので `date.today()` を使うと、
    # 日本時間の朝9時までのあいだ **1日ずれた日付**を印字します。
    # `headline` は `today_jst()` で作るので、そこと1日ちがう字が並びます。
    when = today_jst() + timedelta(days=math.ceil(days))
    if days > 3650:
        return f"{days/365:.0f}年後（{when.isoformat()}）"
    if days > 365:
        return f"{days/365:.1f}年後 ＝ {math.ceil(days):,}日（{when.isoformat()}）"
    return f"**{math.ceil(days):,}日後（{when.isoformat()}）**"


def _long_break_even(a: dict, days: float | None = None) -> list[dict]:
    """**門1 が通る日までに門2a も開けるには、長尺1本あたり何回の再生が要るか。**

    返すのは形（尺×維持率）ごとの1行で、`views` は「長尺を1日L本足したとき」の
    必要な1本あたり再生を L べつに持ちます。

    **なぜ「本数」ではなく「1本あたり再生」を解くか。** 本数はこちらで決められます
    （在庫と日枠の話で、`upload_cap` が上限を知っている）。決められないのは
    **長尺が何回再生されるか**のほうで、そこだけが未知です。
    未知の側を解いて出せば、**段2 に入った瞬間に当たり外れが判定できます**
    （M20 の「推測を測れる形にする」と同じ形）。
    """
    # **門1 が通る日は、段1 が解いた日と同じものを使うこと**（2026-08-24）。
    #     ここは長らく `a["days_subs_at"][PLAN_PUBLISH_PER_DAY]` ＝ **25本/日**
    #     でした。段1 のほうは 2026-08-20 16:0x にオーナー指示
    #     （「25は物理的に不可ならそれを予測に使うのはどうなの？」）で
    #     `solve_gate1()` の実測へ移しています。**段2 だけが取り残されていました。**
    #     いまは `day_cap` が両方を 10本/日 に丸めるので**同じ数**ですが、
    #     上限が動いた日に**黙って割れます**（片方だけが動く）。
    #     呼ぶ側から差せるようにして、`plan()` は `g1["days"]` を渡します。
    days = a["days_subs_at"].get(PLAN_PUBLISH_PER_DAY, NEVER) if days is None else days
    minutes = a["long_minutes_needed"]
    rows = []
    for label, length_min, retention in LONG_SHAPES:
        per_view = length_min * retention
        views = {}
        for per_day in LONG_PER_DAY_SCENARIOS:
            slots = per_day * days
            views[per_day] = (minutes / (slots * per_view)) if slots > 0 and per_view > 0 else float("inf")
        rows.append({"label": label, "min_per_view": per_view, "views": views})
    return rows


def _gate2_bar(a: dict, row: dict, per_day: float, days: float) -> float:
    """**段2 の合格点**（長尺1本あたり何回の再生が要るか）を、任意のLで解く。

    `_long_break_even()` の `views` は筋書き（1・2・4本/日）ぶんしか持ちません。
    **実測の供給は 1.71本/日 のような端数**なので、同じ式をここで1回だけ書きます。
    式は1つ ——「要る視聴分 ÷ (L本/日 × 門1までの日数 × 1再生の視聴分)」。
    """
    slots = per_day * days
    per_view = row["min_per_view"]
    if slots <= 0 or per_view <= 0:
        return float("inf")
    return a["long_minutes_needed"] / (slots * per_view)


# --- 到達日を「解く」ための道具（2026-08-20 08:0x。**オーナー指示3回目**）---
#
# > 「20万達成までのプランを作って**達成日時を予測**して、
# >   毎回達成日時を早めることを考えてから進めるようにして」
#
# **段4（月20万）の期日は、8/20 まで `d_monetized` の写しでした。**
# つまり「収益化が終わる日」を「20万に届く日」として印字していた。
# 合格点（1本あたり◯回）は別に書いてあるのに、**それを満たす日を解いていません。**
# 写しである以上、per_video を10倍にしても RPM を5倍にしても**日付は1日も動きません** ——
# 「早めることを考えてから進めろ」という指示が、**動かない数字に向かって出されていました。**
#
# ここで解くのは次の1本です。
#
#     直近30日の再生数(d) ÷ 1000 × RPM ≧ 200,000円
#
# 未知は「再生数がどう伸びるか」だけなので、**伸び率を実測から出して**
# 上の不等式を満たす最初の日 d を探します（`solve_revenue_day`）。
# 天井（1日あたり出せる本数 × 1本あたり再生）で頭を打つので、
# **届かない帯は「届かない」と出ます** —— そこは伸び率の問題ではなく形の問題です。

#: 7日窓の重心は 3.5日前、28日窓の重心は 14日前。**差は 10.5日**。
#: 2つの窓の比を、この日数ぶんの複利として読みます。
WINDOW_CENTROID_GAP_DAYS = 10.5

#: `data/eta.jsonl` の履歴から伸び率を測るのに要る最小の期間（日）。
#: **これより短い履歴で測ると、Analytics の3日遅れと同じ幅のノイズを伸び率と読みます。**
GROWTH_MIN_SPAN_DAYS = 7.0

#: 「何を何倍にすれば何日後か」を出すときの、期日の候補（今日からの日数）。
GROWTH_HORIZONS = (30, 60, 90, 180, 365)

#: 伸び率を探すときの上限（1日で倍。**これを超える伸びは、探しても意味がない**）。
GROWTH_SEARCH_MAX = 1.0


def growth_per_day(m: dict, points: list[dict] | None = None) -> dict:
    """**再生数の1日あたり複利の伸び率**を実測から出す。

    出どころは2つあり、**長いほうを優先**します。

    1. `data/eta.jsonl` の履歴（`views_per_day` の最初と最後）。
       ただし **7日ぶん貯まってから**（それ未満だと Analytics の3日遅れが
       そのまま伸び率に化けます）
    2. **いま持っている2つの窓の比**（直近7日／直近28日）。重心の差 10.5日ぶんの
       複利として読む。**履歴が無い日でも必ず出る**のが利点で、
       欠点は**公開本数を増やしている最中の伸びが混ざる**こと（＝上振れ側）

    返すのは `{"g": 1日あたり, "basis": どちらで測ったか, "span_days": 期間, "caveat": 断り}`。
    **測れないときは `g=None`**（0 と区別すること。0 は「伸びていない」、
    None は「まだ言えない」）。
    """
    v7 = m.get("views_7d", 0) / 7 if m.get("views_7d") else 0.0
    v28 = m.get("views_28d", 0) / 28 if m.get("views_28d") else 0.0

    if points:
        rows = [p for p in points if p.get("views_per_day")]
        if len(rows) >= 2:
            try:
                t0 = datetime.fromisoformat(rows[0]["at"])
                t1 = datetime.fromisoformat(rows[-1]["at"])
                span = (t1 - t0).total_seconds() / 86400
            except (KeyError, ValueError):
                span = 0.0
            a0, a1 = rows[0]["views_per_day"], rows[-1]["views_per_day"]
            if span >= GROWTH_MIN_SPAN_DAYS and a0 > 0 and a1 > 0:
                return {
                    "g": (a1 / a0) ** (1 / span) - 1,
                    "basis": f"履歴（`data/eta.jsonl` の {len(rows)}点・{span:.1f}日）",
                    "span_days": span,
                    "caveat": "公開本数を増やしている最中の伸びが混ざります（＝上振れ側）",
                }

    if v7 > 0 and v28 > 0:
        return {
            "g": (v7 / v28) ** (1 / WINDOW_CENTROID_GAP_DAYS) - 1,
            "basis": f"2つの窓の比（直近7日 {v7:,.0f}／日 ÷ 直近28日 {v28:,.0f}／日）",
            "span_days": WINDOW_CENTROID_GAP_DAYS,
            "caveat": ("**公開本数を増やしている最中の伸びが混ざります**（＝上振れ側）。"
                       f"履歴が {GROWTH_MIN_SPAN_DAYS:.0f}日ぶん貯まったら、そちらに切り替わります"),
        }

    return {"g": None, "basis": "測れません（窓に再生がありません）",
            "span_days": 0.0, "caveat": ""}


def solve_revenue_day(views_day_now: float, growth: float | None,
                      ceiling_views_day: float, need_month: float,
                      horizon: int = 3_650) -> float:
    """**直近30日の再生数が `need_month` に達する最初の日**（今日を0日目）。

    `views_day_now` から複利 `growth` で伸ばし、**天井 `ceiling_views_day` で頭打ち**。
    天井のままで30日ぶんが足りないなら `NEVER`（＝**伸び率の問題ではなく形の問題**。
    そこで要るのは「もっと待つ」ではなく「1本あたり再生か RPM か密度を変える」）。

    **なぜ「その日の再生数」ではなく「直近30日の合計」で見るか。**
    月20万は**月の収入**なので、その水準の日が1日来ても届きません。
    伸びている最中は、日次が達したあとに合計が追いつきます —— その差を無視すると、
    **到達日が数日から数週間ぶん早く出ます。**

    ## **時間の頭打ちは入れません。頭打ちは `ceiling_views_day` のほうです**

    2026-08-20 20:0x に「伸び率を測った窓（10.5日）の先まで延ばすな」という
    指摘を受けて、**実際に入れて測りました。結果は入れないほうが正しい**です。

    伸び率は「天井へ**どれだけ速く**近づくか」しか決めていません。**水準を
    決めているのは天井**（密度 × 1本あたり再生）で、`v = min(v * (1 + growth), cap)`
    が毎日それを当てています。だから「1日5.38%を100日 ＝ 180倍」は**起きません**
    （実測では 56日目に天井に着いて、そこで止まります）。
    伸び率に時間の頭打ちを足すと、**天井と二重に縛る**ことになり、
    `plan()` は入力を問わず `NEVER` を返しました（検査10件が落ちた）——
    それは「**予測を届きませんで終わらせない**」（オーナー 2026-08-20 06:2x）に反します。

    **13倍の開きを埋めていたのは、伸び率ではなく天井のほうでした。**
    天井の密度が `min(25, 3.3時間の実測36.5) = 25` になっていて、
    直すと（`src.supply.MIN_SUSTAINED_HOURS`）天井は 1日 3,230回まで下がり、
    **同じ伸び率のままで到達日は「届かない」に変わります。**

    **覆る条件**: 天井が「速さ」まで決めるようになったら（例: 密度を時間の
    関数にしたら）、ここにも時間の制限が要ります。いまは天井が水準だけを
    決めているので、要りません。**`tests/test_eta_growth_ceiling.py` が
    「伸び率をいくら上げても天井×30日を超えない」を固定しています。**
    """
    if need_month <= 0:
        return 0.0
    if views_day_now <= 0:
        return NEVER
    cap = ceiling_views_day if ceiling_views_day and ceiling_views_day > 0 else float("inf")
    if cap * 30 < need_month:
        return NEVER
    v = min(views_day_now, cap)
    window = deque([v] * 30, maxlen=30)
    total = v * 30
    if total >= need_month:
        return 0.0
    if not growth or growth <= 0:
        return NEVER
    for d in range(1, horizon + 1):
        v = min(v * (1 + growth), cap)
        total += v - window[0]
        window.append(v)
        if total >= need_month:
            return float(d)
    return NEVER


def required_growth(views_day_now: float, ceiling_views_day: float,
                    need_month: float, days: int) -> float | None:
    """**その日までに届かせるには、1日あたり何%の伸びが要るか。**

    届かせられないなら `None`（＝天井が足りない。**伸び率をいくら上げても無駄**）。
    予測が「届きません」で終わらないための逆算です（オーナー指示 2026-08-20 06:2x）。
    """
    if days <= 0:
        return None
    if ceiling_views_day * 30 < need_month:
        return None
    if solve_revenue_day(views_day_now, GROWTH_SEARCH_MAX, ceiling_views_day, need_month) > days:
        return None
    lo, hi = 0.0, GROWTH_SEARCH_MAX
    for _ in range(60):
        mid = (lo + hi) / 2
        if solve_revenue_day(views_day_now, mid, ceiling_views_day, need_month) <= days:
            hi = mid
        else:
            lo = mid
    return hi


def double_days(growth: float) -> float:
    """その伸び率で、再生数が2倍になるまでの日数。**%より、こちらのほうが読める。**

    **`math.log(1 + growth)` は 0 を返します**（2026-08-20 23:3x に踏んだ）——
    `growth` が 1e-16 より小さいと `1 + growth` が浮動小数で 1.0 に丸まり、
    対数が厳密に 0 になって **`ZeroDivisionError` で回そのものが落ちます。**
    `required_growth` は「ほとんど伸びなくても間に合う」帯で、その大きさを返します。
    `log1p` なら丸まらず、それでも 0 なら **無限大（＝2倍にならない）**として返します。
    """
    if not growth or growth <= 0:
        return float("inf")
    denom = math.log1p(growth)
    return math.log(2) / denom if denom > 0 else float("inf")


#: 腕を1つだけ動かしてみるときの倍率（`lever_days`）。**1.0 が「いまのまま」**
DEFAULT_SCALE = {"per_video": 1.0, "sub_rate": 1.0, "rpm": 1.0, "density": 1.0}


def _scale(scale: dict | None) -> dict:
    sc = dict(DEFAULT_SCALE)
    for k, v in (scale or {}).items():
        if k not in sc:
            raise KeyError(f"知らない腕です: {k}（{sorted(DEFAULT_SCALE)}）")
        sc[k] = float(v)
    return sc


def analyse(m: dict, points: list[dict] | None = None,
            scale: dict | None = None) -> dict:
    """実測から、門ごとの日数と天井を出す。

    `points` は `data/eta.jsonl` の履歴（新しい順ではなく**積んだ順**）。
    **伸び率を測るためだけ**に使い、渡さなければ2つの窓の比で代用します
    （`growth_per_day`）。**渡しても渡さなくても、他の数字は1つも変わりません。**

    `scale` は「**その腕を◯倍にしたら**」を測るための倍率です（既定は全部 1.0
    ＝ いまの実測そのまま）。`lever_days` がここを使って、
    **腕べつに到達日が何日動くか**を出します —— オーナー指示（2026-08-20 16:0x）:

    > 分析して制作に活かして視聴回数などを上げることが予測に使えることじゃない？

    **`views_day_now` は倍率を掛けません。** いま出ている再生は、いま出ている数です。
    1本あたり再生を上げても、**過去に公開した本の再生数は遡って増えません** ——
    掛けると「明日から全部が2倍」を予測として印字することになります。
    倍率が効くのは**これから公開する本の側**（天井・門1の登録者）だけです。
    """
    sc = _scale(scale)
    views_day_7 = m["views_7d"] / 7
    views_day_28 = m["views_28d"] / 28
    # 予測には速いほうを使う（伸びている最中に遅いほうで測ると、悲観に倒れる）
    views_day = max(views_day_7, views_day_28)

    sub_rate = ((m["subs_gained_28d"] / m["views_28d"]) if m["views_28d"] else 0.0) * sc["sub_rate"]
    subs_per_day = views_day * sub_rate

    a = {
        "views_per_day": views_day,
        "views_per_day_7d": views_day_7,
        "views_per_day_28d": views_day_28,
        "sub_rate": sub_rate,
        "subs_per_day": subs_per_day,
        "subs_remaining": max(0, SUBS_GATE - m["subs_net"]),
    }

    # --- 門1: 登録者1,000人 ---
    a["days_subs"] = _days_to(a["subs_remaining"], subs_per_day)

    # 公開の密度べつの門1（report のループが手で計算していたものをここへ寄せた。
    # **門2a の逆算がこの日数を要る**ので、2か所で別々に計算すると必ずずれます）
    # **本数のうち、再生が付くぶんだけを数えます**（2026-08-21 16:2x）。
    # ここは長らく `n` をそのまま掛けていて、**25本/日 なら 25本ぶんの再生**と
    # 読んでいました。実測は違います（`src/day_cap.py`）:
    #   08/20 は 25本 公開して **#11から先の15本が 0〜3再生**。#10 は 1,111再生。
    #   時刻ではなく**その日の通し番号**で割れます（08/16 の14時 #4 は 1,361再生）。
    # つまり段1 の日付は、上限を超えて出したぶんだけ**楽観に倒れて**いました。
    a["view_cap_per_day"] = _view_cap_per_day()
    a["days_subs_at"] = {
        n: _days_to(a["subs_remaining"],
                    min(n, a["view_cap_per_day"]) * _per_video(m)
                    * sc["per_video"] * sub_rate)
        for n in sorted(set(PUBLISH_SCENARIOS) | {PLAN_PUBLISH_PER_DAY})
    }
    # **門1 に要る「本数」**（日数ではなく本数）。供給の側から日を解くのに要ります。
    _pv = _per_video(m) * sc["per_video"]
    a["videos_needed_gate1"] = (
        (a["subs_remaining"] / (_pv * sub_rate)) if (_pv > 0 and sub_rate > 0) else float("inf")
    )

    # --- 門2a: 長尺4,000時間（ショートは入らない）---
    long_hours_per_day = m["long_hours_365"] / 365
    a["days_long_hours"] = _days_to(LONG_HOURS_GATE - m["long_hours_365"], long_hours_per_day)

    # **その無限は「遠い」ではなく「測定になっていない」。**
    #
    # `days_long_hours` は伸び率を先へ延ばした数なので、伸びが実質ゼロなら
    # 必ず無限になります。**そのとき無限が言っているのは長尺の実力ではなく、
    # 長尺をまだ出していないこと**です。しきい値を手で決めずに済む言い方はこれ:
    # **延ばした先が100年より遠いなら、その伸び率は0と区別がつかない**
    # ＝ 測定として成立していない（`_days_to` が100年で NEVER に畳むのと同じ線）。
    # 実測 0.1時間/365日 は、まさにこの帯です。
    a["long_untried"] = a["days_long_hours"] >= NEVER
    a["long_hours_365_seen"] = m["long_hours_365"]

    # --- 門2b: ショート 直近90日で1,000万再生 ---
    a["shorts_needed_per_day"] = SHORTS_VIEWS_GATE / 90
    a["days_shorts_gate"] = 0.0 if views_day >= a["shorts_needed_per_day"] else NEVER

    # 収益化はどちらかの門2 ＋ 門1
    a["days_monetized"] = max(a["days_subs"], min(a["days_long_hours"], a["days_shorts_gate"]))

    # --- 門2a を「長尺を足して」開けるなら、長尺1本に何回の再生が要るか ---
    #
    # **これが無かったので、この道具は 8/19 の初回から「届きません」しか言えず、
    # 段2（M20）が要求している数字を一度も出していませんでした。**
    # `days_long_hours` は「直近365日の長尺の伸び」をそのまま延ばした数で、
    # 長尺を1本も出していない以上、**必ず「届かない」になります**（0で割る）。
    # それは「長尺では開かない」ではなく「**まだ試していない**」です。
    #
    # 開けるかどうかは、次の1本の式で決まります:
    #     残り視聴分 = 長尺の本数 × 長尺1本あたり再生 × 1再生あたり視聴分
    # 門1 が通る日までに開けたいので、本数は「1日L本 × 門1の日数」で埋まります。
    # **未知は「長尺1本あたり再生」だけ**なので、そこを解いて出します。
    a["long_minutes_needed"] = max(0.0, (LONG_HOURS_GATE - m["long_hours_365"]) * 60)
    a["long_break_even"] = _long_break_even(a)

    # --- 天井: いまの構成で出せる最大の月収 ---
    #
    # **帯ごとに、その形の実測を当てます**（2026-08-19 14:2x）。
    # ここは長らく1つの `per_video`（＝**ショートだけ**の中央値）を全部の帯に当てていて、
    # 長尺の帯に「**届く**」と印字していました。**長尺の実測は 1本 2回**（n=5）で、
    # ショートの 1,092回 とは**546倍ちがいます。** 混ぜると、
    # 「長尺をまだ出していない」が「長尺なら届く」に化けます。
    per_video = _per_video(m) * sc["per_video"]
    long_per_video = m.get("long_per_video")
    if long_per_video is not None:
        long_per_video = long_per_video * sc["per_video"]
    a["long_per_video"] = long_per_video
    a["long_videos_28d"] = m.get("long_videos_28d", 0)
    a["long_views_28d"] = m.get("long_views_28d", 0)

    def _band_per_video(key: str) -> float:
        """その帯の1本あたり再生。**長尺の実測が無いときだけ**ショートで代用する。"""
        if key.startswith("長尺") and long_per_video is not None:
            return long_per_video
        return per_video

    a["per_video_by_band"] = {k: _band_per_video(k) for k in RPM_SCENARIOS}
    a["band_measured"] = {
        k: ("長尺" if (k.startswith("長尺") and long_per_video is not None) else "ショート")
        for k in RPM_SCENARIOS
    }
    # **天井の分母は「口が受け付ける本数」ではなく「再生が付く本数」**（2026-08-25 22:4x）。
    #
    # ここは 08/24 に直し残った最後の1か所でした。`solve_gate1`・`days_subs_at`・
    # `physical_caps`（`density` の腕の天井）は、その回に **92 → `day_cap.cap()`**
    # へ移っています。**この表だけが 92 のまま**でした。
    #
    # 92 は API の日枠です。実測（`src/day_cap.py`・3日とも一致）は **10本/日** で、
    # **それを超えて出したぶんは 0再生**。いっぽう掛けている `per_video` は
    # **「再生が付いた本」だけの平均**なので、**92 を掛けると、再生の付かない
    # 82本まで「付いた本と同じだけ回る」ことになります** ——
    # 同じファイルの docstring が「床を通った本だけの数字を、落ちた本まで含む
    # 本数に掛けている」と書いて禁じている形の、いちばん大きい版です。
    #
    # **何が変わるか**: 天井が **9.2分の1**。いちばん効くのは「長尺がショート並みに
    # 伸びたら」の行で、¥400/¥1,000 の帯が **「届く」→「届かない」に反転**します。
    # つまり「長尺さえ動けば、どの帯でも目標を超える」は 92 の産物でした。
    #
    # **覆る条件**: `day_cap.cap()` が上がったとき（登録者が増えれば上がるはず、と
    # `src/day_cap.py` が書いています）。定数ではないので自動で追います。
    a["ceiling_per_day"] = min(float(UPLOAD_CAP_PER_DAY), float(a["view_cap_per_day"]))
    ceiling_per_day = a["ceiling_per_day"]
    ceiling_views_month = per_video * ceiling_per_day * 30
    a["ceiling_views_month"] = ceiling_views_month
    a["ceiling_views_month_by_band"] = {
        k: a["per_video_by_band"][k] * ceiling_per_day * 30 for k in RPM_SCENARIOS
    }
    a["ceiling"] = {
        k: a["ceiling_views_month_by_band"][k] / 1000 * rpm for k, rpm in RPM_SCENARIOS.items()
    }
    # **「ショート並みに伸びたら」の側も残します。** 実測 2回 は
    # 「登録者9人のチャンネルの長尺」であって「長尺の実力」ではない（M20）ので、
    # **片方だけ出すと、こんどは逆向きに読み違えます。**
    a["ceiling_if_shorts_rate"] = {
        k: ceiling_views_month / 1000 * rpm for k, rpm in RPM_SCENARIOS.items()
    }

    # 目標に要る月間再生数（RPM ごと）
    a["views_needed_month"] = {
        k: TARGET_YEN * 1000 / (rpm * sc["rpm"]) for k, rpm in RPM_SCENARIOS.items()
    }
    # **再生が付く本数**で、その再生数に要る「1本あたり再生」
    #     （92本/日 で割ると、要る倍率が 9.2分の1 に見えます。
    #      `tests/test_eta.py` が段取り側で禁じているのと同じ分母の話）
    a["per_video_needed"] = {
        k: v / (ceiling_per_day * 30) for k, v in a["views_needed_month"].items()
    }
    # **要る倍率は、その帯の形の実測で割ること**（ここが混ざると 36倍 が 0.1倍 に見える）
    a["per_video_ratio"] = {
        k: (a["per_video_needed"][k] / a["per_video_by_band"][k]
            if a["per_video_by_band"][k] else float("inf"))
        for k in RPM_SCENARIOS
    }
    a["per_video_now"] = per_video

    # --- 到達日を解くための入力（2026-08-20 08:0x に足した）---
    #     **ここが無い間、段4 の期日は段3 の写しでした。**
    g = growth_per_day(m, points)
    a["growth"] = g
    a["growth_per_day"] = g["g"] if g["g"] is not None else 0.0
    a["views_day_now"] = views_day
    a["scale"] = sc
    return a


def report(m: dict, a: dict) -> list[str]:
    out: list[str] = []
    P = out.append
    P("=" * 66)
    # **「RPM だけが推測」は、この道具の見出しとして正しくありませんでした**
    # （2026-08-23 にオーナーの問い「軌跡の予測は全て実測や確かな情報から
    # 導き出される妥当な可能性？」で数え直した）。**推測は少なくとも5つあります。**
    # 見出しが1つしか言わないと、読む側は残り4つを実測だと思って使います。
    P("=== 月20万円に、いつ届くか ===")
    P("  **実測**: 登録者・再生／日・登録率・視聴時間・1本あたり再生（Analytics）／"
      "腕の動く速さ（閉じた前提の実績）／1日の再生が付く本数の上限（day_cap）")
    P("  **推測**（この5つは測っていません。日付はこの上に乗っています）:")
    P(f"    1) RPM ——`RPM_SCENARIOS` の帯。ニッチで10倍変わる")
    P(f"    2) 収益化の審査 {MONETIZE_REVIEW_DAYS}日 —— YouTube の公表値。**実測ではない**")
    # **ここは n=8 の固定文字列でした**（2026-08-25 に直した）。実測は毎回
    # `measured()` が取り直しており、この日は n=14 です。**固定した数を
    # 「推測の出どころ」として出すと、読み手は測り直しが要ると読みます。**
    if a.get("long_per_video") is None:
        P("    3) 長尺の合格点 —— 直近28日に長尺の再生が0本。**ショートの実測で割っています**")
    else:
        P(f"    3) 長尺の合格点 —— 1本 {a['long_per_video']:,.1f}回"
          f"（n={a.get('long_videos_28d', 0)}・直近28日の Analytics・**毎回測り直し**）。"
          f"**{LONG_SAMPLE_MIN}本 に満たないので推測のまま**")
    P("    4) 1日N本出しても1本あたりが保つか —— **未測定**（配信の壁）")
    P("    5) **日次再生の複利は入っていません** —— 実測 10.2%/日（t=2.17・有意）だが、"
      "区間が 0.96〜20.3%/日 と広く、上端は30日で破綻値になるため保留（2026-08-23）")
    P("=" * 66)
    P("")
    P("--- いま出ている数（YouTube Analytics。推測ではありません）---")
    P(f"  登録者（純）      {m['subs_net']:>10,} 人   （門は {SUBS_GATE:,} 人・**あと {a['subs_remaining']:,} 人**）")
    P(f"  再生／日          {a['views_per_day_7d']:>10,.0f} 回（直近7日）  {a['views_per_day_28d']:>7,.0f} 回（直近28日）")
    P(f"  登録率            {a['sub_rate']*100:>10.4f} %   ＝ 再生 {1/a['sub_rate']:,.0f} 回につき1人" if a["sub_rate"] else "  登録率            **0** ＝ 何回再生されても増えていない")
    P(f"  長尺の視聴時間    {m['long_hours_365']:>10,.1f} 時間（直近365日。門は {LONG_HOURS_GATE:,}）")
    P(f"  ショート90日      {m['shorts_views_90d']:>10,} 回（門は {SHORTS_VIEWS_GATE:,}）")
    if m.get("views_per_video_live"):
        P(f"  1本あたり再生     {a['per_video_now']:>10,} 回（**ショート**・**平均**・"
          f"**再生が付く帯に居た {m.get('videos_live_28d', 0)} 本**）")
        P(f"    （帯の外まで入れた平均は {m['views_per_video']:,} 回／{m['videos_with_views_28d']} 本。"
          "**天井には帯の中だけを使います** —— 天井は「1本あたり再生 × 再生が付く上限（"
          f"{a.get('view_cap_per_day', 0):.0f}本/日）」なので、"
          "**帯の外の本を分母に残すと、同じ死を2回 引きます**。`live_band_views` に実測）")
    else:
        P(f"  1本あたり再生     {a['per_video_now']:>10,} 回（**ショート**・**平均**・"
          f"直近28日に再生のあった本のうち、**標本に残った {m['videos_with_views_28d']} 本**）")
    if m.get("median_views_per_video") and m["median_views_per_video"] != a["per_video_now"]:
        P(f"    （中央値は {m['median_views_per_video']:,} 回 ＝ **典型的な1本**。"
          "**天井には平均のほうを使います** —— 天井は N本ぶんの合計で、合計 ＝ N × 平均）")
    if a.get("long_per_video") is None:
        P("  1本あたり再生（長尺）    **測れていません**（直近28日に長尺の再生が0本）")
    else:
        P(f"  1本あたり再生（長尺）{a['long_per_video']:>10,} 回（平均・n={a['long_videos_28d']}・合計 {a['long_views_28d']:,}回）"
          f"  ← ショートの **1/{(a['per_video_now'] / a['long_per_video']):,.0f}**")
    P("")
    P("--- 門を1つずつ当てる（**最初に落ちるものが、いまの律速**）---")
    P(f"  [門1] 登録者 {SUBS_GATE:,}人      {_fmt_days(a['days_subs'])}")
    P(f"        いまの速さ ＝ 1日 {a['subs_per_day']:.2f} 人（再生 {a['views_per_day']:,.0f}／日 × 登録率 {a['sub_rate']*100:.4f}%）")
    P(f"  [門2a] 長尺 {LONG_HOURS_GATE:,}時間    {_fmt_days(a['days_long_hours'])}")
    if a["long_untried"]:
        # **「遠い」と「分母が0」は別。** ここを同じ字で出していたので、
        # 2回とも「長尺では開かない」と読まれかけました（下の逆算の節が答えです）。
        P(f"         ↑ **これは長尺の実力ではありません。** 直近365日の長尺の視聴時間が"
          f" {a['long_hours_365_seen']:,.1f}時間 ＝ **伸び率が0と区別がつきません**。")
        P("         延ばした数が無限なのは、長尺が弱いからではなく**まだ出していない**から。")
        P("         **「開かない」ではなく「まだ試していない」です。** 合格点は下の節に出します。")
    if a["days_shorts_gate"] == 0:
        shorts_line = "**通っています**"
    else:
        shorts_line = (f"**届きません**（1日 {a['shorts_needed_per_day']:,.0f}回 要る"
                       f"／いま {a['views_per_day']:,.0f}回）")
    P(f"  [門2b] ショート90日で{SHORTS_VIEWS_GATE:,}回    {shorts_line}")
    P(f"  → **収益化そのもの: {_fmt_days(a['days_monetized'])}**")
    if a["long_untried"] and a["days_monetized"] >= NEVER:
        P("       **この「届きません」を、諦める理由に使わないこと。** 門2a の無限が"
          "そのまま出ているだけで、**未着手を測った数ではありません**。")
    P("")
    P("--- 天井（**ここが本体**）---")
    lpv = a.get("long_per_video")
    P(f"  1本あたり再生は**形ごとに別の実測**です（直近28日。混ぜると長尺が「もう届く」に見えます）:")
    P(f"    ショート  **{a['per_video_now']:,}回**／本（**平均**・n={m.get('videos_with_views_28d', 0)}・**床は当てていません**）")
    P("      **床（30再生未満は除外）を外しました**（2026-08-19 15:0x）。床は標本からは落としますが、")
    P(f"      **下の {a['ceiling_per_day']:.0f}本 からは落としません。** 落ちた本まで「通った本と同じだけ回る」ことになっていました。")
    P("      **天井は「本数を増やす意味があるか」を決める数**なので、上振れ側で読むと『届く』を作ります。")
    _print_dropped(P, m)
    if lpv is None:
        P("    長尺      **測れていません**（直近28日に長尺の再生が1本もない）"
          " → 下の長尺の行は**ショートの数で代用**しています。**実測ではありません。**")
    else:
        P(f"    長尺      **{lpv:,}回**／本（**平均**・n={a['long_videos_28d']}・合計 {a['long_views_28d']:,}回・"
          "**30再生の床は当てていません**。当てると1本も残りません）")
    P(f"  **再生が付く上限 {a['ceiling_per_day']:.0f}本/日**（実測・`src/day_cap.py`）× 30日 に、"
      "**その形の実測**を当てた上限:")
    P(f"      （口が受け付けるのは {UPLOAD_CAP_PER_DAY}本/日 ですが、**それを超えて出したぶんは 0再生**です。"
      "掛けている1本あたり再生は**再生が付いた本だけの平均**なので、")
    P(f"       {UPLOAD_CAP_PER_DAY} を掛けると、付かない本まで「付いた本と同じだけ回る」ことになります。"
      "**2026-08-25 に直しました。それ以前の天井は 9.2倍 楽観です**）")
    for k in RPM_SCENARIOS:
        yen = a["ceiling"][k]
        need = a["per_video_needed"][k]
        mark = "**届く**" if yen >= TARGET_YEN else "届かない"
        ratio = a["per_video_ratio"][k]
        src = a["band_measured"][k]
        P(f"    {k:<12} RPM ¥{RPM_SCENARIOS[k]:>5,}  上限 ¥{yen:>10,.0f}  {mark:<8} "
          f"要 1本 {need:>9,.0f}回（{src}の実測の **{ratio:,.1f}倍**）")
    if lpv is not None:
        P("")
        P("  **長尺が「ショート並み（1本 "
          f"{a['per_video_now']:,}回）に伸びたら」の側も出します**（片方だけだと逆向きに読み違えます）:")
        for k in RPM_SCENARIOS:
            if not k.startswith("長尺"):
                continue
            yen2 = a["ceiling_if_shorts_rate"][k]
            mark2 = "**届く**" if yen2 >= TARGET_YEN else "届かない"
            P(f"    {k:<12} RPM ¥{RPM_SCENARIOS[k]:>5,}  上限 ¥{yen2:>10,.0f}  {mark2}")
        P(f"  **実測 {lpv:,}回 は「長尺の実力」ではありません**（M20）。"
          f"n={a['long_videos_28d']} で、登録者 {m['subs_net']} 人のチャンネルに出した本の数です。")
        P("  **決まったのは1つだけ**: いまの実測を当てるかぎり、"
          "**長尺の帯も上限が目標の下**にあります。")
        P("  だから段2 は「長尺に替えれば届く」ではなく、"
          f"**1本あたりを {lpv:,}回 から上げられるか**を測る段です。")
    P("")
    # **いちばん近い帯を名指しする**（2026-08-19 14:2x に足した）。
    #
    # 表は6行あって、どれも「届かない」と書いてあります。**そこで読むのをやめると、
    # 6つが同じくらい遠いように見えます。** 実際には倍率が2桁ちがい、
    # 前の回は「ショート単独は原理的に閉じている」と読んで長尺へ寄せました。
    # **RPM ¥60 の帯では、要るのは 1本あたり 1.1倍です。**
    nearest = min(RPM_SCENARIOS, key=lambda k: a["per_video_ratio"][k])
    nr = a["per_video_ratio"][nearest]
    npv = a["per_video_by_band"][nearest]
    P(f"  **いちばん近い帯: {nearest}**（RPM ¥{RPM_SCENARIOS[nearest]:,}）"
      f" ＝ 1本あたりを **{nr:,.1f}倍**（{npv:,}回 → {a['per_video_needed'][nearest]:,.0f}回）")
    P("      **6行とも「届かない」でも、遠さは同じではありません。**"
      "倍率の小さい帯から手を付けること。")
    for line in _ledger_reach(nr):
        P(line)
    P("")
    reachable = [k for k in RPM_SCENARIOS if a["ceiling"][k] >= TARGET_YEN]
    unreachable = [k for k in RPM_SCENARIOS if a["ceiling"][k] < TARGET_YEN]
    if unreachable:
        P(f"  [!] **1日の上限まで出しても月20万に届かない帯: {', '.join(unreachable)}**")
        P("      この帯にいる限り、**本数を増やしても在庫を増やしても、日付は動きません。**")
        P("      動くのは **1本あたりの再生数** か **RPM（＝ニッチと尺）** の2つだけです。")
    if not reachable:
        # **「いまの構成」が何を指すかを、同じ行に書くこと**（2026-08-29 12:4x に足した）。
        # ここに並ぶ 6帯 は `RPM_SCENARIOS` そのもの ＝ **分子は「再生 × 広告 RPM」の1つだけ**
        # です（`TARGET_YEN ÷ RPM × 1000`。`src/reach_split.py` 88行）。
        # **メンバーシップ・Super Thanks・企業案件は、この機械のどこにも入っていません**
        # （実測 2026-08-29: 4語とも `scripts/eta.py` / `src/*.py` / `docs/MEANS.md` /
        #  `docs/STRATEGY.md` / `docs/CONSTRAINTS.md` に **0件**）。
        # 断りが無いと、読む側はこの行を「**YouTube では届かない**」と読みます ——
        # `CLAUDE.md`「(イ) **裸の『届きません』を出さないこと**」の、この形ぶんの手です。
        # **帯は1つも増やしていません**（未測定の数を足すと、日付がその推測で動く）。
        # **覆る条件**: `RPM_SCENARIOS` の外の分子が1つでも入ったら、この断りは書き直すこと
        # （足し先・掛け算・着手条件は `docs/MEANS.md` の M23）。
        P("  [!] **どの帯でも届きません。いまの構成は、上限そのものが目標の下にあります。**"
          "　**その「構成」は帯だけの話ではありません** —— 上の6帯は `RPM_SCENARIOS`"
          " ＝ **分子が「再生 × 広告 RPM」の1つだけ**の模型です。"
          "**メンバーシップ・Super Thanks・企業案件は、この機械に入っていません**"
          "（`CLAUDE.md` は4つとも名指ししています）。"
          "だからこの行は『YouTube では届かない』ではなく"
          "**『広告だけを分子にすると届かない』**です（`docs/MEANS.md` の M23）。")
    else:
        P(f"  上限で届く帯: {', '.join(reachable)}")
        P("      **ただし RPM は実測ではありません。** 収益化後に自分の数字で測り直すこと。")
    P("")
    P("--- 早めるには、どれを何倍にするか（**倍率が小さいものから手を付ける**）---")
    for label, now, need in _levers(m, a):
        P(f"    {label:<26} いま {now:<16} → 要 {need}")
    P("")
    P("--- **公開の密度を上げたら、門1はいつ通るか**（1本あたり再生を据え置いた見積り）---")
    P(f"    ＝ 1日に公開する本数 × {a['per_video_now']:,}回 × 登録率 {a['sub_rate']*100:.4f}%")
    for n in PUBLISH_SCENARIOS:
        v = n * a["per_video_now"]
        P(f"    1日 {n:>3}本 公開 → 再生 {v:>9,.0f}／日 → 門1 {_fmt_days(a['days_subs_at'][n])}")
    P("    **これは推測です**（1日N本でも1本あたりが保つかは未測定＝M14 の「配信の壁」）。")
    P("    ただし 4本/日 までは崩れないことが実測済み（2026-08-19 04:4x・中央値 +50.5%）。")
    out.extend(_report_long_gate(m, a))
    return out


def _stage4(m: dict, a: dict, sp: dict, density: int, per_video: float,
            d_monetized: float, today: date, proxy: bool = False,
            d_revenue: float = 0.0) -> dict:
    """**月20万の期日を、20万の条件そのものから出す。段3の日を代入しない。**

    2026-08-20 08:1x・オーナー追記（原文）——

    > 勝手に20万達成以外の日時の予測だけにしないで

    **直していること。** ここは1行 `d_target = d_monetized` でした。
    段3（収益化の審査が終わる日）を段4の期日として印字していたので、
    画面の「月20万の到達見込み」は、**中身が収益化の日付**でした。
    門1（登録者1,000人）・門2a（長尺4,000時間）・審査30日 ——
    **どれも20万の日付ではありません。**

    月20万の条件は、門の条件とは形がちがいます。門は**積み上がれば通る**（累積）
    ので、速さで割れば日が出ます。20万は**その月の水準**なので、日が出るには
    2つ要ります:

        (1) 合格点が立つこと    1日に出す本数 × 1本あたり再生 × RPM が 20万に届く
        (2) その水準で30日ぶん積むこと（`REVENUE_WINDOW_DAYS`）

    (2) は収益化より前には始められません（収益化前の再生は1円も生まない）。
    **だから 段4 は、段3 + 30日 より後ろにしか来ません。** 同じ日には決してならない
    （例外は、門が「届かない」で返って下の `fallback` に落ちたとき —— そこでは
    段3 が日付を持っていないので、比べる相手そのものがありません）。

    そして (1) は**実測で立っているとは限りません。** 立っていないなら、
    「届きません」で畳まずに、**何を何倍にすれば、いつ出るのか**を返します
    （同じ追記の後半。倍率は `ratio`、その倍率が本当かを**確かめられる最短の日**が
    `verify_day` ＝ 公開の翌日 → 伸びきる48時間 → Analytics 3日遅れ）。
    """
    need_per_video = sp["per_video_needed"]
    ratio = (need_per_video / per_video) if per_video else float("inf")
    # **倍率が1を切っていても、それだけでは「立っている」と言えません。**
    #     `per_video` はショートの実測で、段4 が立てているのは長尺です。
    #     別の形の実測を当てているあいだは、合格点は**推測**です（`proxy`）——
    #     ここを見落とすと、20万の期日がまた「測っていない数字の写し」になります。
    met = (ratio <= 1.0) and not proxy

    # **倍率が本当かを確かめられる最短の日**（今日からの日数）。
    # 段4 は、確かめる前に来ることはありません —— 立っていない合格点の上に
    # 期日を置くと、それは予測ではなく願望になります。
    #     **日付そのものを持たせます**（`_fmt_days` は TZ を持たない `date.today()`
    #     ＝ UTC に足すので、JST の 00:00〜09:00 は1日ずれた日を印字します）。
    verify_on = answer_day(today + timedelta(days=1))
    verify_day = float((verify_on - today).days)

    # --- 合格点が立つ日 ---
    #
    # **`d_revenue` が入るまで、ここは「収益化の日」か「確かめる日」でした**
    # （2026-08-20 08:3x の版。同じ回の申し送りに「**要る倍率が上がっても日数は
    # 動かない（1本あたり再生の伸び率を持っていないため）**」と書いてあります）。
    # いまは伸び率を実測して解いた日が入ります（`solve_revenue_day`）——
    # **倍率が上がれば、この日が後ろへ動きます。**
    bar_day = max(d_revenue, d_monetized if met else max(d_monetized, verify_day))

    # --- 門が「届かない」で返ってきたときも、日付を1つ出す ---
    #     `days_subs_at` が NEVER になるのは、**登録が28日で0件**のとき（0で割る）。
    #     倍率では出ません（0 を何倍しても 0）。**出るのは「1人でも出れば」のほう**なので、
    #     28日に1人の線（＝この機械が観測しうる最小の非ゼロ）で引き直します。
    #     **見るのは門のほう**（`d_monetized`）です。`bar_day` で見ると、
    #     再生数の側が「届かない」でも門の引き直しが走り、**関係のない仮定で
    #     日付が出ます**（引き直しても再生数は届かないままなので、意味がない）。
    fallback = None
    if d_monetized >= NEVER:
        views_28d = m.get("views_28d") or 0
        rate_min = (1.0 / views_28d) if views_28d else 0.0
        subs_day = density * per_video * rate_min
        d1 = _days_to(a["subs_remaining"], subs_day)
        if d1 < NEVER:
            d_monetized = d1 + MONETIZE_REVIEW_DAYS
            bar_day = max(d_revenue, d_monetized if met else max(d_monetized, verify_day))
            fallback = {
                "why": "登録が28日で0件なので、いまの実測では門1が開きません",
                "assume": (f"**28日に1人でも登録が出れば**（登録率 {rate_min * 100:.4f}%"
                           f" ＝ この機械が観測しうる最小の非ゼロ）"),
                "gate1_days": d1,
            }

    # --- ②の30日は前借りできない ---
    #     **ただし `d_revenue` に足さないこと。** あちらは「直近30日の合計」が
    #     必要量に達する日なので、**30日ぶんの積み上げを既に含んでいます。**
    #     足すと二重に数え、到達日が1か月ぶん遠くなります。
    #     前借りできないのは**収益化より前の再生**のほうなので、床はこの2つ:
    gate_floor = d_monetized + REVENUE_WINDOW_DAYS if d_monetized < NEVER else NEVER
    verify_floor = (verify_day + REVENUE_WINDOW_DAYS) if (not met) else 0.0
    floor = max(gate_floor, verify_floor)
    when = max(d_revenue, floor) if (d_revenue < NEVER and floor < NEVER) else NEVER

    return {
        "when": when,
        "floor": floor, "gate_floor": gate_floor, "verify_floor": verify_floor,
        "d_revenue": d_revenue,
        "bar_day": bar_day,
        "verify_day": verify_day, "verify_on": verify_on,
        "ratio": ratio,
        "met": met,
        "need_per_video": need_per_video,
        "per_video_now": per_video,
        "window": REVENUE_WINDOW_DAYS,
        # **条件つきの日付であることを、道具の側が持っておく**（画面で断るため）。
        # 満たしていない合格点の上に立っているなら、それは「最早」であって見込みではない。
        "conditional": (not met) or fallback is not None,
        "fallback": fallback,
        "proxy": proxy,
    }


#: 腕を1つだけ「これだけ上げたら」と置いてみる倍率。**2倍は、この機械が
#: 実際に出した幅の中にあります**（1本あたり再生の実測は 22本で 30回〜4,000回超）。
#:
#: **この倍率だけで腕を選ばないこと**（2026-08-25 に踏んだ）。
#: 2026-08-25 の実測では、**4本とも ×2 では「届きません」**でした ——
#: 合格点が ×2.61 足りない回だったので、**2.0 < 2.61 の時点で、どの腕を
#: 入れても答えは「出ません」に確定していました。** `plan()` はこの表の
#: 最大値で `lever_hint` を上書きする作りでしたが、`gain > 0` が一度も真に
#: ならず、**8/20 に書いてから一度も動いていません**でした。
#: いまは各腕の**自分の天井**でも解き、そちらで選びます（`gain_at_cap`）。
LEVER_FACTOR = 2.0

#: `threshold`（日付が出はじめる倍率）を挟み込む回数。
#: 1回の探りは実測 0.12秒。4本 × 8回 ＝ **約4秒**で、`trajectory_all`（75秒）の
#: 5%。**ここを増やすなら、先に軌跡のほうを速くすること。**
LEVER_BISECT_ITERS = 8

#: 到達日を動かしうる腕。**`none`（道具の整備）はここには入りません** ——
#: 日付を動かさないと自分で言っている腕なので、比べる意味がありません。
LEVERS = ("per_video", "sub_rate", "rpm", "density")

LEVER_LABEL = {
    "per_video": "1本あたり再生（分析→制作に反映）",
    "sub_rate": "登録率（終端の作り・シリーズ化）",
    "rpm": "RPM（ニッチ・尺・形式）",
    "density": "作る速さ（節を書く／出す）",
}


def lever_days(m: dict, a: dict, pl0: dict, today: date | None = None,
               supply: dict | None = None, points: list[dict] | None = None,
               factor: float = LEVER_FACTOR, mix: dict | None = None,
               caps: dict[str, float | None] | None = None) -> list[dict]:
    """**腕べつに、到達日が何日動くか。**（2026-08-20 16:0x・オーナー指示）

    > 分析して制作に活かして視聴回数などを上げることが予測に使えることじゃない？

    **予測に使えていませんでした。** 到達日の入力は
    「1日25本」「収益化の審査30日」で、**1本あたり再生は天井の表に出てくるだけ**——
    上げても下げても、印字される日付は動きませんでした。だから
    「次にどの腕を引くか」は `binding`（どの床がいちばん遅いか）という
    **診断**から決めていて、**引いた結果どれだけ縮むか**は誰も出していません。

    ここがやるのは1つだけです。**腕を1つずつ `factor` 倍にして、
    予測をまるごと解き直し、到達日の差を取る。** 差が大きい腕が、
    この回に引くべき腕です。**名前ではなく、日数で決まります。**

    返り: 腕ごとに
    `{"lever", "label", "days", "date", "gain", "reachable",
      "cap", "days_at_cap", "date_at_cap", "gain_at_cap", "reachable_at_cap",
      "threshold", "at_ceiling"}`。
    `gain` は**縮んだ日数**（正なら早まる）。届かない側は `gain=0.0`。

    ## **同じ倍率だけで並べると、答えが「出ません」に固定されます**（2026-08-25）

    元の版はここが `factor`（＝×2）1本で、docstring はそれを
    「比べられるのは、どの腕も**同じ倍率**で並べているからです」と正当化していました。
    **並べる目的なら正しい。選ぶ目的には使えません。**

    2026-08-25 の実測:

        合格点は ×2.61 足りない（`per_video` いま 638回 → 要る 1,667回）
        → **2.0 < 2.61 なので、どの腕を ×2 にしても「届きません」**
        → `gain` は4本とも 0.0
        → `plan()` の `if best["gain"] > 0:` は **8/20 に書いてから一度も真になっていない**

    つまりこの表は、**構造として肯定的な答えを返せません**でした。
    毎周 `それでも出ません` を4行印字して、読み手に
    「どの腕でも届かない」という**誤った印象**を渡していました。実際は:

        per_video  天井 ×2.96 → **211.7日**（届く）
        rpm        天井 ×70.20 → **509.6日**（届く）
        sub_rate   天井 ×2,923.79 → **届かない**（再生の天井に触らない腕なので、何倍でも出ません）
        density    天井 ×1.00 → **引き代なし**（すでに上限を 1.3倍 超えて出している）

    **天井は `physical_caps` / `_capped_arms` が同じファイルの中で計算しています。**
    それをこの関数が読んでいなかった、というだけの話です
    （「同じことを2か所が別々に言っていて、片方しか読まれていない」の一例）。

    いまは3つ出します。**選ぶのは2番目です**:

        1. `days`        —— 同じ倍率（`factor`）で並べた線。**腕の感度**
        2. `days_at_cap` —— **その腕の天井まで引いた**線。**引けるところまで引いた実力**
        3. `threshold`   —— **日付が出はじめる倍率**。天井まで引いても出ないなら `None`

    `threshold` が要るのは、「あと何倍で景色が変わるか」が
    **`cap` とも `factor` とも別の数**だからです（実測 `per_video` は ×2.7 付近）。
    """
    base = pl0.get("days_to_target", NEVER)
    if caps is None:
        try:
            caps = {k: v.get("cap") for k, v in
                    _capped_arms(a, supply=supply).items()}
        except Exception:                                      # noqa: BLE001
            caps = {}

    def _days(lever: str, f: float) -> float:
        """腕 `lever` を `f` 倍にして、到達日（日数）を解き直す。"""
        a2 = analyse(m, points=points, scale={lever: f})
        pl2 = plan(m, a2, today=today, supply=supply, sensitivity=False,
                   points=points, mix=mix)
        return pl2.get("days_to_target", NEVER)

    def _date(d: float):
        return ((today or today_jst()) + timedelta(days=math.ceil(d))
                ) if d < NEVER else None

    rows: list[dict] = []
    for lever in LEVERS:
        try:
            d = _days(lever, factor)
        except Exception:                                      # noqa: BLE001
            continue
        reachable = d < NEVER
        # **`base` が NEVER のときも、そのまま引くこと。**
        #     ここを「届く側は一律に最大」と書いていたら、**届く腕が全部同点**になり、
        #     並び順は `LEVERS` に書いた順（＝こちらの都合）で決まっていました。
        #     引き算のままなら、`NEVER - d` は **d が小さい腕ほど大きい** ので、
        #     「いまは出ない」帯でも**早く出るほうが上**に来ます。
        gain = (base - d) if reachable else 0.0

        # --- その腕の天井まで引いたら ---
        #     **天井 ×1.00 は「引き代なし」**（`physical_caps` が
        #     `max(1.0, raw)` で潰しています）。解き直す意味がないので、そのまま 0。
        cap = caps.get(lever)
        at_ceiling = cap is not None and cap <= 1.0
        d_cap, threshold = NEVER, None
        if cap is not None and cap > 1.0:
            try:
                d_cap = _days(lever, cap)
            except Exception:                                  # noqa: BLE001
                d_cap = NEVER
            if d_cap < NEVER:
                # **日付が出はじめる倍率を挟み込む。**
                #     `cap` で出ている以上、`[1.0, cap]` のどこかに境目があります
                #     （出ない → 出る、は単調と置いています。倍率を上げて
                #     到達日が遠くなる腕は、この機械にはありません）。
                lo, hi = 1.0, cap
                for _ in range(LEVER_BISECT_ITERS):
                    mid = (lo + hi) / 2.0
                    try:
                        ok = _days(lever, mid) < NEVER
                    except Exception:                          # noqa: BLE001
                        break
                    if ok:
                        hi = mid
                    else:
                        lo = mid
                threshold = hi
        reachable_at_cap = d_cap < NEVER
        gain_at_cap = (base - d_cap) if reachable_at_cap else 0.0

        rows.append({
            "lever": lever,
            "label": LEVER_LABEL[lever],
            "factor": factor,
            "days": d,
            "date": _date(d),
            "gain": max(0.0, gain),
            "reachable": reachable,
            "cap": cap,
            "at_ceiling": at_ceiling,
            "days_at_cap": d_cap,
            "date_at_cap": _date(d_cap),
            "gain_at_cap": max(0.0, gain_at_cap),
            "reachable_at_cap": reachable_at_cap,
            "threshold": threshold,
        })
    # **並べ替えは「引けるところまで引いた実力」で。**
    #     同じ倍率の `gain` は、`factor` が合格点に足りない回は4本とも 0 になり、
    #     並び順が `LEVERS` に書いた順（＝こちらの都合）に戻ります。
    rows.sort(key=lambda r: (-r["gain_at_cap"], -r["gain"], r["days_at_cap"]))
    return rows


def sustained_density(supply: dict | None,
                     density: float = PLAN_PUBLISH_PER_DAY) -> float:
    """**天井を立てている密度**（1日に「続けられる」本数）を1か所で出す。

    `plan()` の `density_sustained`（`min(PLAN_PUBLISH_PER_DAY, 作る速さ)`）と
    **同じ数**です。写しではなく、同じ入口から読むために関数にしてあります。

    ## なぜ要るか（2026-08-21 01:5x に踏んだ）

    段4 の天井は `per_video × density_sustained`（実測 7.8本/日）で立ちます。
    ところが `physical_caps` は `density` の伸びしろを
    **`PLAN_PUBLISH_PER_DAY`（25本/日）で割っていました** ——
    25 は「予約を詰め直したらこうなる」という**計画の数**で、
    同じファイルが天井からは外している数です（`density_sustained` の注記）。

        天井が立っている密度   7.8本/日（実測）
        伸びしろの分母          25本/日（計画）  ← **別の数**
        → 腕は 7.8 × (92/25) ＝ **28.7本/日 で頭打ち**。実物の上限 92本/日 の **3.2分の1**

    軌跡は「腕を全部振っても出ません」と印字していましたが、その天井の
    3.2倍ぶんは**そもそも歩かせてもらえていません**でした。
    **`tests/test_eta_density_cap.py` が、分母が計画の数に戻ったら落とします。**
    """
    if supply is None:
        return float(density)
    rate = supply.get("sustained_rate_per_day")
    if rate is None:
        rate = supply.get("rate_per_day")
    if rate is None:
        return float(density)
    return min(float(density), float(rate))


def _long_form_per_day() -> float:
    """**いま、長尺を1日に何本出しているか。**（読めなければ 0.0）

    `day_cap.long_form()` の `per_day` は「長尺を出した日」だけを持つので、
    **その日数で割ると出していない日が消えます。** 割るのは
    **最初に出した日から今日まで**の暦日です（＝実際の密度）。
    """
    try:
        rows = day_cap.long_form().get("per_day") or {}
    except Exception:                                          # noqa: BLE001
        return 0.0
    if not rows:
        return 0.0
    days = sorted(rows)
    span = (date.today() - days[0]).days + 1
    return sum(rows.values()) / max(1, span)


def physical_caps(a0: dict, density: float = PLAN_PUBLISH_PER_DAY,
                  supply: dict | None = None) -> dict[str, dict]:
    """**腕を「実在する幅」で止める。**（軌跡が実在しない世界を歩かないため）

    最初の版はここが無く、実測の速さのまま 224日ぶん外挿して
    **`density` を ×4,421**（＝1日 110,525本）まで伸ばしていました。
    **同じ回に「1日25本」を外したばかり**で、まったく同じ欠陥です ——
    伸ばした先が満たせるかを、誰も確かめていませんでした。

    ここが返す倍率は全部**この機械の中にある数**で、出どころを併記します:

        density    `UPLOAD_CAP_PER_DAY`（92本/日・**実測**）÷ いまの密度
        rpm        `RPM_SCENARIOS` の最大（**推測の幅の上端**）÷ いま立てている帯
        sub_rate   `src/subs_cap.py`（**1本あたり登録率の実測の最大**）。
                   測れない回だけ 登録率 100%（**定義上の上限**）へ落ちます
        per_video  ここでは付けません（`config/hypotheses.yaml` の `ceiling` が実測で持っています）

    **`rpm` は実測の天井ではありません。**
    「これ以上は誰も主張していない」という線で、**測れば動きます**。

    **`sub_rate` は 2026-08-28 に実測へ替えました。** それまでは
    「登録率 100%」だけで、天井が **×3,153.91** と出ていました ——
    同じ日の軌跡は 56日目に `sub_rate` ×10.36 を歩いており、
    **その倍率が実在の幅の中かを誰も確かめられない**形です（100% は
    どんな倍率も下に入れます）。`per_video` の天井は実測の最大なので、
    **同じ物差しを当てます**: 実測 0.2066% ÷ いま 0.0317% ＝ **×6.5**。
    """
    caps: dict[str, dict] = {}
    # **分母は「天井が立っている密度」**（`sustained_density`）。
    #     計画の 25本/日 で割ると、腕は実物の上限 92本/日 まで歩けません。
    density = sustained_density(supply, density)
    if density > 0:
        # **腕の天井は「出せる本数」ではなく「再生が付く本数」**（2026-08-21 16:2x）。
        #     ここは `UPLOAD_CAP_PER_DAY`（1日92本・**投稿の口の上限**）で割って
        #     いました。出せはします。**ただし再生は付きません** ——
        #     08/20 は 25本 公開して #11から先の15本が 0〜3再生（`src/day_cap.py`）。
        #     天井を口の側で立てると、**腕を ×3.7 まで歩けると出て、
        #     実際には1日も縮まない**という形になります。
        arm_cap = min(float(UPLOAD_CAP_PER_DAY), float(_view_cap_per_day()))
        raw = arm_cap / density
        # **倍率が 1 を下回るのは「引き代がマイナス」ではありません** ——
        #     **すでに上限より多く出している**、という意味です。そのまま返すと
        #     腕を 0.4倍 に「引ける」ことになり、軌跡が**密度を減らす向きに歩きます**。
        #     引き代は 0（＝×1.0 が天井）。**超えていること自体は `why` に残します。**
        over = raw < 1.0
        caps["density"] = {"factor": max(1.0, raw),
                           "why": (f"1日に再生が付く上限 {arm_cap:.0f}本（実測・`src/day_cap.py`）"
                                   f" ÷ いま続けられる {density:.1f}本/日"
                                   f"（出せる口の上限は {UPLOAD_CAP_PER_DAY}本ですが、"
                                   f"そこまで出しても再生は付きません）"
                                   + ("。**すでに上限を {:.1f}倍 超えて出しています ＝ 引き代なし**"
                                      "（超えたぶんは 0再生）".format(1 / raw) if over else "")),
                           "measured": True,
                           "at_ceiling": over,
                           "surface": "ショート"}
        # --- **その「引き代なし」は、まだ決まっていない枝の上に立っています** ---
        #     （2026-08-26・最適化の回。`CLAUDE.md` の (イ) が禁じている形）
        #
        #     `day_cap.window()` は毎回 **`confounded=True`** と言っています ——
        #     同じ生データに当てはまる説明が2つあり、**測れている日はどれも
        #     同じ数**を出します:
        #
        #         (A) 1日 C本 まで          → 上の `cap()`。**早く置いても後ろが死ぬ**
        #         (B) T までに出した本は全部生きる → **T より前に置いたぶんは丸ごと上積み**
        #
        #     上の行はそのうち **(A) だけ**を読んで「引き代なし」と断定していました。
        #     (B) なら引き代は **×1.8**（05:00 から 30分きざみで 13:30 まで 18枠）で、
        #     **作る本数は1本も増えません** —— 置く時刻を変えるだけです。
        #
        #     **`factor` は動かしません。** 軌跡は保守的な (A) を歩くべきで、
        #     測っていない (B) で歩かせると、この関数の docstring が禁じている
        #     「実在しない世界」をそのまま歩きます。**変えるのは印字だけ。**
        #
        #     **覆る条件**: 08/27 の切り分けの日が答えます（`answer_on`）。
        #     決まれば `window()["confounded"]` が False になり、ここは自動で黙ります。
        try:
            fork = day_cap.cap_if_window()
        except Exception:                                      # noqa: BLE001
            fork = None
        if fork:
            # **比べる相手は「作る本数」ではなく「再生が付く本数」**（`arm_cap`）。
            #     (B) の 18本 を、出している 18.2本/日 と比べると ×0.99 と出て
            #     「(B) でも引き代なし」に見えます。**それは別の問いの答え**です ——
            #     (B) が言っているのは「**もっと作れ**」ではなく
            #     「**いま死んでいる本を、T より前に置き直せ**」。
            #     いま T より前に居るのは 10本（＝ `arm_cap`）なので、
            #     賭かっているのは **10本 → 18本**、つまり **×1.8** です。
            fork_factor = fork["cap"] / arm_cap if arm_cap else 1.0
            caps["density"]["confounded"] = True
            caps["density"]["factor_if_window"] = fork_factor
            caps["density"]["answer_on"] = fork["answer_on"]
            edge = fork.get("left_edge")
            if fork_factor > 1.0:
                caps["density"]["why"] += (
                    f"。ただし**この上限は「本数」と「時刻の窓」に切り分けられていません**"
                    f"（`day_cap.window()` が `confounded`）——"
                    f" **(B) 時刻の窓なら上限は {arm_cap:.0f}本 → {fork['cap']}本"
                    f"（×{fork_factor:.2f}）**"
                    f"（{fork['earliest']}→{fork['T']}・{fork['step_min']}分きざみ）。"
                    f"**作る本数は1本も増えません** —— いま {fork['T']} より後ろで"
                    f"0再生になっているぶんを、前へ置き直すだけです。"
                    f"上の「引き代なし」は **(A) 本数モデルを固定した場合**の数で、"
                    f"切り分けは **{fork['answer_on']}** に出ます"
                )
            else:
                # **(B) の側にも引き代が無いと分かった場合**（2026-08-27 に測った）。
                # ここは長らく「(B) なら ×1.80」を**無条件で**印字していました。
                # その 18枠 は 05:00〜13:30 から数えた数で、**05:00 が生きるかは
                # 測っていませんでした**（`collisions.LIVE_FROM_MIN` は
                # 切り分けの日を作るために広げてあった値）。
                # 2026-08-27 に実際に置いたら **05:00〜08:30 の 8本 が全部 0再生**で、
                # 窓の左端は 08:59 でした。08:59〜13:30 は30分きざみで
                # **ちょうど 10枠** ＝ (A) と同じです。
                # **賭かっているものが無いなら、そう言うこと** ——
                # 「切り分けが済んでいない」と「どちらでも同じ」は別の話で、
                # 前者だけを印字すると、次の回が**無い上振れ**を取りにいきます。
                caps["density"]["why"] += (
                    f"。**モデルの切り分けは済んでいません**"
                    f"（`day_cap.window()` が `confounded`）が、"
                    f"**(B) 時刻の窓の側にも引き代はありません** ——"
                    f" 窓の左端は実測で **{edge['by'] if edge else fork['earliest']}**"
                    + (f"（{edge['from']} に {edge['from_dead']}本 置いて、"
                       f"**全部 0再生**）" if edge else "")
                    + f"で、{fork['earliest']}→{fork['T']} は"
                    f"{fork['step_min']}分きざみで **{fork['cap']}枠** ＝ "
                    f"(A) の {arm_cap:.0f}本 と同じです（×{fork_factor:.2f}）。"
                    f"**早い時刻へ倒しても本が増えません。倒すと死にます。**"
                    f"残っているのは**右端**（{fork['T']} より後ろ）だけで、"
                    f"その切り分けは **{fork['answer_on']}** に出ます"
                )
                # **この枝にだけ `answer_on` が入っていませんでした**（2026-08-28）。
                #     上の (B) に引き代がある枝は最後に「切り分けは ○○ に出ます」と
                #     言うのに、こちらは「残っているのは右端だけです」で終わっており、
                #     **いつその右端が答えるかがどこにも出ません。**
                #     `tests/test_eta_density_confounded.py` は両方の枝に同じ行を
                #     求めていて、**その検査は赤のままでした。**
                #     日付が本文に無いと、次の回はそれを申し送りから読むことになり、
                #     申し送りの日付は腐ります（`retro.py` の持ち越しに
                #     「日枠が戻ったら」が3周 並んだのと同じ形）。
        # --- **長尺の面は、別の天井です**（2026-08-26。**3回続けて申し送られていた**）---
        #     上の `day_cap.cap()` は **ショートの面**の数です（`SHORTS_FEED` に
        #     1日に差し込まれる本数）。**長尺はその枠を1つも使いません**し、
        #     **4,000時間の門に入るのは長尺だけ**です。つまり上の「引き代なし」は、
        #     **唯一開いている門について何も言っていません。**
        #
        #     **数は作りません。** 長尺の面の上限は**まだ一度も測っていない**ので
        #     （`day_cap.long_form()` が常に `measured: False`）、ここに実測の顔を
        #     した数を置くと、`sub_rate` の ×2,923 と同じ「偽の緑」になります。
        #     置くのは **`sub_rate` と同じ扱い ＝ 定義上の上限**です:
        #     口が通す 1日 `UPLOAD_CAP_PER_DAY` 本 から、ショートの面で死ぬと
        #     **測れている**ぶんを引いた残り。**測った天井ではありません。**
        #
        #     **これは `LEVERS` に入れません。** 入れると `_capped_arms` が
        #     この未測定の天井で軌跡を歩かせます（08/21 に `UPLOAD_CAP_PER_DAY`
        #     そのままで歩かせて「×3.7 引けるのに1日も縮まない」を踏んだのと同じ形）。
        #     **軌跡は歩きません。使うのは `src/levers.py` の「死んだ腕」の判定だけ**で、
        #     そこが**面ごとに割れる**ようにするために置いています ——
        #     ショートの面が天井でも、**長尺を増やす作業を `none` へ落とさない**ため。
        #
        #     **【2026-08-29 に、ここが実物と食い違っていました】**
        #     上の註は「`day_cap.long_form()` が**常に** `measured: False`」と
        #     書いていますが、**もう False ではありません。**
        #     実測（`data/views.jsonl`・齢 48時間 でそろえた読み）:
        #
        #         2026-08-21  長尺 **7本** を出して、再生が付いたのは **5本**
        #         → `collapsed: True` / `most: 7` / `measured: True`
        #
        #     **崩れは観測されています。** `day_cap.long_form_lines()` は
        #     この日から「**7本/日 で崩れました → 上限は 6本/日**」と印字しており、
        #     `batch_build._long_ring()` も `most - 1` で正しく落としています。
        #     **ここだけが「一度も観測していない」と言い続けていました** ——
        #     `day_cap.py` の註が名指ししている
        #     「**機構は正しく、読まれる側だけが偽**」の3件目です。
        #
        #     食い違いの大きさ: 定義上の上限は 82本/日（92 - 10）で **×118**、
        #     実測の上限は 6本/日 で **×8.7**。**14倍 ちがいます。**
        #     この行は `eta.py` の頭・`--alloc` の2か所に毎回出て、
        #     「長尺の面は ×118 空いている」と読ませていました。
        #
        #     **測れているなら、測ったほうを使うこと。** 測れていない窓
        #     （崩れをまだ見ていない）では、これまでどおり定義上の上限に落とします。
        long_m: dict = {}
        try:
            long_m = day_cap.long_form() or {}
        except Exception:                                      # noqa: BLE001
            long_m = {}
        long_now = _long_form_per_day()
        long_measured = bool(long_m.get("measured"))
        if long_measured:
            # **崩れた日の1本 手前**が上限（`day_cap.long_form_lines()` と同じ式）。
            long_cap = float(max(1, int(long_m.get("most") or 1) - 1))
            long_why = (f"長尺の面は **{long_m.get('most')}本/日 で崩れました**"
                        f"（最大の日 {long_m.get('alive')}/{long_m.get('most')}本 しか"
                        f"生存していません・齢 {float(long_m.get('age_h') or 0):.0f}時間 で"
                        f"そろえた実測）→ 上限 **{long_cap:.0f}本/日**"
                        "（**測った天井です**。`src/day_cap.long_form()`）")
        else:
            long_cap = max(0.0,
                           float(UPLOAD_CAP_PER_DAY) - float(_view_cap_per_day()))
            long_why = (f"口が通す {UPLOAD_CAP_PER_DAY}本/日 から、ショートの面で死ぬ"
                        f" {_view_cap_per_day()}本 を引いた {long_cap:.0f}本"
                        "（**定義上の上限。測った天井ではありません** ——"
                        " 長尺の面が崩れるところは一度も観測していない）")
        long_raw = (long_cap / long_now) if long_now > 0 else None
        caps["density_long"] = {
            "factor": long_raw,
            "why": (long_why
                    + (f" ÷ いま出している長尺 {long_now:.2f}本/日"
                       if long_now > 0 else "。**長尺をまだ1本も出していません**")),
            "measured": long_measured,
            "at_ceiling": bool(long_raw is not None and long_raw <= 1.0),
            "surface": "長尺",
            "now_per_day": long_now,
        }
    # --- `rpm` の天井は、2026-08-20 22:2x に**実測に入れ替えました**（`src/rpm_mix.py`）---
    #     ここには `max(RPM_SCENARIOS) / band`（¥2,000 ÷ ¥20 ＝ ×100）が入っていて、
    #     この関数の docstring 自身が「測った天井ではありません」と言っていました。
    #     入れ替えたのは**混ざり方**です —— RPM は1本に付く数ではなく
    #     「視聴分がどちらの形に何%乗っているか」で決まるので、
    #     長尺のサムネが見せられている回数（実測）より上には行けません。
    #     初測: 実効 ¥20.9 → 天井 ¥866（×41.5）。**据え置きの ×100 は 2.4倍 甘かった。**
    #     **測れていないときだけ**、前の据え置きへ落ちます（黙って落ちないよう why に出す）。
    mixed = rpm_mix.last()
    if mixed and mixed.get("factor"):
        caps["rpm"] = {"factor": float(mixed["factor"]),
                       "why": (f"実測の混ざり方 ¥{mixed.get('rpm_now', 0):,.1f} → "
                               f"¥{mixed.get('rpm_max', 0):,.0f}（{mixed.get('why', '')}）"),
                       "measured": True}
    else:
        band = RPM_SCENARIOS.get(PLAN_BAND_BY_FORM.get("ショート", ""), 0)
        if band:
            caps["rpm"] = {"factor": max(RPM_SCENARIOS.values()) / band,
                           "why": (f"RPM の幅の上端 ¥{max(RPM_SCENARIOS.values()):,}"
                                   "（**まだ測っていません**: `python -m src.rpm_mix --record`）"),
                           "measured": False}
    sr = a0.get("sub_rate") or 0.0
    if sr > 0:
        caps["sub_rate"] = {"factor": 1.0 / sr,
                            "why": "登録率 100%（定義上の上限）",
                            "measured": False}
        # **測れた回は、定義の上限ではなく実測の最大を採る**（2026-08-28）。
        #     ここは長らく「登録率 100%」だけで、`sub_rate` の天井が
        #     **×3,153.91** と出ていました。同じ日の軌跡は 56日目に
        #     `sub_rate` ×10.36 を歩いており、**その倍率が実在の幅の中かを
        #     誰も確かめられない**（100% はどんな倍率も下に入れてしまう）。
        #     `per_video` の天井は実測の最大（1本あたり再生 1,891回）なので、
        #     **同じ物差しを登録率にも当てます**（`src/subs_cap.py`）。
        #     実測 2026-08-28: 最大 0.2066%（`CdX2oIb7BG8` 1,452再生 3人）
        #     ÷ いま 0.0317% ＝ **×6.5**。門に要るのは ×2.08 なので、
        #     **これは「届かない」ではありません** —— 要る倍率と実在の幅を、
        #     同じ物差しで並べられるようにしただけです。
        best = subs_cap.best_per_video()
        if best and best.get("rate", 0) > 0:
            f = best["rate"] / sr
            if f < caps["sub_rate"]["factor"]:
                over = f < 1.0
                caps["sub_rate"] = {
                    # **1 を下回るのは「引き代がマイナス」ではありません** ——
                    #     いまの登録率が、実測の最大より上にある（＝ 引き代なし）。
                    #     `density` と同じ扱いで、超えていること自体は `why` に残します。
                    "factor": max(1.0, f),
                    "why": (subs_cap.why(best)
                            + ("。**いまの登録率が実測の最大を超えています ＝ 引き代なし**"
                               if over else "")),
                    "measured": True}
    return caps


#: **1つの腕の天井が、面ごとに割れているもの。**（2026-08-28・最適化の回）
#:
#: `LEVERS` は4本ですが、`physical_caps` は `density` の天井を**2つ**立てます ——
#: `density`（ショートの面・実測 ×1.00・**天井**）と
#: `density_long`（長尺の面・**実測 ×8.7（上限 6本/日）で開いている**）。
#:
#: **【2026-08-29 に、ここの「×128・未測定」が古くなりました】**
#: 長尺の面の崩れは **2026-08-21 に観測されています**（7本 出して生存 5本）。
#: `physical_caps` は、その日から**実測の上限 6本/日**（`most - 1`）を使います。
#: **`LEVERS` に入れない理由も、それに合わせて置き直しています** ——
#: もう「未測定だから」ではありません。**段1（`PLAN_PUBLISH_PER_DAY`）が
#: ショートの面の上で解かれているから**です。軌跡に長尺の面を歩かせるには、
#: 先に段1 を面ごとに割る必要があります（そこを割らずに腕だけ足すと、
#: ショートの段の上を長尺の天井で歩きます）。
#: **覆る条件**: 段1 が面ごとに割れたら、`density_long` を `LEVERS` へ入れること。
#: （元の理由は「軌跡を未測定の天井で歩かせない。`physical_caps` の註に 08/21 の実害」）
#: そして
#: **「この腕は死んでいる」と印字する側**は、その割れを知らないままでした。
#: ここはその割れを、印字する側へ運ぶためだけの表です。**軌跡には渡しません。**
_SURFACE_SIBLINGS: dict[str, tuple[str, ...]] = {"density": ("density_long",)}


def _capped_arms(a0: dict, arms: dict | None = None,
                 density: float = PLAN_PUBLISH_PER_DAY,
                 supply: dict | None = None) -> dict:
    """実測の天井（`hypotheses.yaml`）と、実在する幅（`physical_caps`）の**低いほう**を当てる。"""
    if arms is None:
        arms = arm_speed.all_arms(per_video_now=a0.get("per_video_now"))
    phys = physical_caps(a0, density, supply=supply)
    out = {}
    for lever, a in arms.items():
        a = dict(a)
        p = phys.get(lever)
        if p and p["factor"] > 0:
            if a.get("cap") is None or p["factor"] < a["cap"]:
                a["cap"] = p["factor"]
                a["cap_why"] = p["why"]
                a["cap_measured"] = p["measured"]
        if a.get("cap") is not None and "cap_why" not in a and a.get("ceiling"):
            a["cap_why"] = f"実測の天井 {a['ceiling']['value']:,}（{a['ceiling']['unit']}）"
            a["cap_measured"] = True
        # --- **その天井が、いくつの面のうちの1つか**（2026-08-28）---
        #     ここを運ばないと、`cap_lines` と `alloc_search` は
        #     ショートの面の ×1.00 だけを見て「立てても、閉じても、
        #     上の日付は1日も動きません」と印字します。**印字だけの欄**で、
        #     `cap` そのものには触りません（軌跡は今までどおり）。
        p0 = phys.get(lever) or {}
        sib = []
        for key in _SURFACE_SIBLINGS.get(lever, ()):
            q = phys.get(key)
            if not q or not q.get("factor"):
                continue
            sib.append({"key": key,
                        "surface": q.get("surface") or key,
                        "factor": float(q["factor"]),
                        "measured": bool(q.get("measured")),
                        "at_ceiling": bool(q.get("at_ceiling")),
                        "why": q.get("why", "")})
        if sib:
            a["cap_surfaces"] = sib
            a["cap_surface"] = p0.get("surface")
        if p0.get("confounded"):
            a["cap_confounded"] = True
            a["cap_answer_on"] = p0.get("answer_on")
        out[lever] = a
    return out


def cap_caveats(lever: str, a: dict) -> list[str]:
    """**「この腕は死んでいる」と言い切れない理由**を、その場の数から並べる（0〜2件）。

    ## なぜ要るか（2026-08-28・最適化の回。**実測で見つけた**）

    この日の `--alloc` は、こう印字していました:

        次の1件を `density` に   2027-01-19
            ↑ **この腕は天井 ×1.00（引き代なし）です。**
              立てても、閉じても、上の日付は1日も動きません

    同じ回の `physical_caps` は、**density の天井を2つ**立てています:

        density       ×1.00    surface=ショート  measured=True   at_ceiling=True
        density_long  ×128.13  surface=長尺      measured=False  at_ceiling=False

    **【この2行目は 2026-08-26 の実物です。2026-08-29 に数が動きました】**
    長尺の面の崩れが `day_cap.long_form()` に入り（08/21・7本 出して生存 5本）、
    いまは `×8.67  surface=長尺  measured=True  at_ceiling=False`
    （実測の上限 6本/日 ÷ 0.69本/日）。**×128 は定義上の上限の名残**です。

    そして台帳の**開いている density の前提 6件**のうち **2件は長尺の面**です
    （「長尺は1日4本 作れる」期限 08-31 ／「長尺の生成が落ちる主因は…」期限 08-29）。
    **4,000時間の門に入るのは長尺だけ**なので、この2件は門に直結しています。
    それを「立てても、閉じても動きません」と読ませていました。

    残る4件も無傷ではありません —— **3件は `day_cap` の上限そのものを測る前提**
    （「上限10本はチャンネルが育っても上がらない」／「本の集合は帯で決まる。
    本数ではない」／「1日の合計は本数では動かない」）。
    つまり **×1.00 を作っている当の数を、いま測っている最中**です。
    `physical_caps` は同じ回に `caps["density"]["confounded"] = True`
    （`day_cap.window()` が (A)本数 と (B)時刻の窓 を切り分けていない）と
    立てており、**機械は「この天井は未決着」と知っていました。**

    **凍らせた入力から出した結論を、世界についての結論として印字する形**です ——
    `CLAUDE.md` が `eta.py` の「届きません」について言っているのと同じ壊れ方で、
    そちらは直っていて、こちらだけ残っていました。

    ## 何を言い、何を言わないか

    **`cap` は動かしません。** 軌跡は今までどおりショートの面の ×1.00 で歩きます
    （未測定の天井で歩かせた 08/21 の実害は `physical_caps` の註）。
    ここが直すのは**印字だけ**です:

        言う      「上の日付が動かない」は**この道具の作りの話**である
        言う      どの面で測った天井か・別の面はいくつ空いているか
        言わない  「だから long の面に立てれば日付が動く」（**動きません**。
                  `density_long` は `LEVERS` に無いので軌跡が歩きません）

    ## 覆る条件

    - `physical_caps` が面ごとに腕を立て、`LEVERS` に長尺の面が入ったら、
      この関数は要りません（そのとき軌跡が面を歩くので、印字は自動で正しくなる）
    - `day_cap.window()` が (A)/(B) を切り分けたら、2件目の理由（`confounded`）は
      自動で消えます。**消えるのが正しい** —— 手で消さないこと
    - `tests/test_cap_caveat_surface.py` が、裸の「動きません」に戻ったら落とします
    """
    out: list[str] = []
    open_sib = [s for s in (a.get("cap_surfaces") or []) if not s["at_ceiling"]]
    if open_sib:
        here = a.get("cap_surface") or "この面"
        for s in open_sib:
            out.append(
                f"**その ×{a.get('cap', 0):,.2f} は「{here}」の面だけの数です。**"
                f"「{s['surface']}」の面は **×{s['factor']:,.2f}**"
                + ("（**未測定**）" if not s["measured"] else "")
                + f" 空いています —— {s['why']}")
    if a.get("cap_confounded"):
        out.append(
            "**その天井そのものが、まだ決着していません**"
            "（`day_cap.window()` が (A)本数 と (B)時刻の窓 を切り分けていない"
            + (f"。答えが出るのは {a['cap_answer_on']}" if a.get("cap_answer_on") else "")
            + "）。**凍らせた入力から出した『動きません』です。**")
    return out


def cap_lines(arms: dict, indent: str = "      ") -> list[str]:
    """腕べつの**天井**と、その出どころを1行ずつ。**正本はここ1か所です。**

    ## なぜ関数にしたか（2026-08-27 に実測して足した）

    `alloc_search` の docstring は自分でこう言っています ——
    **「その2本の順位は天井の遠さだけで決まっています」**。
    ところが `--alloc` の出力には、**天井が1つも印字されていませんでした。**
    印字していたのは軌跡の側（`_trajectory_lines`）だけです。

    実測 2026-08-27 の `--alloc`:

        次の1件を `per_video` に   2027-01-07
        次の1件を `sub_rate` に    2027-01-03   ← **いちばん早い**
        次の1件を `rpm` に         2027-01-12
        次の1件を `density` に     2027-01-07

    同じ日の同じプログラムが、軌跡の側ではこう言っています:

        天井 `sub_rate` ×3,231.43 …… 登録率 100%（定義上の上限）← **実測の天井ではありません**
        天井 `density`  ×1.00 …… **引き代なし。この腕は何をしても上の日付を1日も動かしません**

    **順位を決めている当の数が、順位表に出ていない。**
    `density` は `per_video` と**同着**の顔で並び、「引き代0」とは1文字も
    書いてありません。実際 `data/runs.jsonl` の直近8件の ship のうち
    **2件が `lever=density`**（同じ行に `"lever_cap": 1.0` が記録済み）——
    **機械は知っていて、選ぶ側には見えていませんでした。**
    そして `--alloc` は **3回 続けて `sub_rate` を名指し**しています
    （`docs/JOURNAL.md` 2026-08-27）。その天井は「登録率100%」＝
    **定義上の上限**で、実測ではありません。

    **覆る条件**: `sub_rate` と `rpm` が `MIN_N`（3件）に届いて
    p・g が自前になったら、順位は天井だけでは決まらなくなります
    （`alloc_search` の「覆る条件」と同じ1件）。そのときもこの表は残すこと ——
    **消える理由は「天井が効かなくなった」ではなく「他も効くようになった」**です。
    """
    out: list[str] = []
    for lever, a in arms.items():
        cap = a.get("cap")
        if not cap or not a.get("cap_why"):
            continue
        caveats = cap_caveats(lever, a) if cap <= 1.0 else []
        if cap <= 1.0 and not caveats:
            mark = ("  ← **引き代なし。この腕に立てても、"
                    "上の日付は1日も動きません**")
        elif cap <= 1.0:
            # **裸の「動きません」を出さないこと**（2026-08-28。理由は `cap_caveats`）。
            #     ここで言えるのは「**上の日付**が動かない」までで、
            #     「この腕の作業が目標に効かない」ではありません。
            mark = ("  ← **上の日付は動きません。ただし『引き代なし』とは"
                    "言えません**（下の行）")
        elif not a.get("cap_measured"):
            mark = "  ← **実測の天井ではありません**"
        else:
            mark = ""
        out.append(f"{indent}天井 `{lever}` ×{cap:,.2f} …… {a['cap_why']}{mark}")
        for c in caveats:
            out.append(f"{indent}    [!] {c}")
    return out


#: 軌跡を追う地平（日）。ここより先は「届かない」と同じに扱う。
#: 3年 ＝ 目標の「最短」から見ればとっくに別の道を選んでいる長さです。
TRAJECTORY_HORIZON_DAYS = 1_095

#: **θ を「無限大にしたら」の代わりに撃つ倍率**（2026-08-30・最適化の回）。
#: `trajectory()` は `t_work` の探索を `saturate = log(cap)/rate` で打ち切るので、
#: 倍率を上げるほど**速く**なります（実測: ×1.0 が 5.4秒 に対し ×1000 は 0.1秒）。
#: 1000倍 で `t_work` は 1日 まで潰れる ＝ **腕が一瞬で天井に着いた世界**で、
#: そこから先は何倍にしても日付が動きません（＝これが θ の天井）。
THETA_INF_SCALE = 1_000.0


def _factors_at(arms: dict, days: float, *, focus: str | None = None,
                rate_scale: float = 1.0, realloc: bool = True) -> dict:
    """**`days` 日たったときの、腕ごとの倍率。**（天井で頭打ち）

    `focus` を渡すと、**その腕に回転を全部振った**場合になります
    （他の腕は動きません ＝ 1.0 のまま）。回転は1本しかないので、
    「全部の腕を全力で」は**実在しない世界**です。

    ## `realloc` ——**天井に着いた腕から、回転を引き上げる**（2026-08-21 02:1x）

    `rate = focus_rate × share` で、`share` は**実績の配分**（過去にどの腕を
    何回引いたか）です。ここが**固定**だったので、天井に着いた腕にも
    回転が回り続けていました。実測では `per_video` の配分が **57%** で、
    その腕は **×1.57 で天井**です —— **回転の半分以上を、
    もう伸びない腕に永久に注ぎ続ける世界**を歩いていました。
    軌跡が「腕を全部振っても出ません」と言っていた正体はこれです。

    これは物理ではなく**この機械の振る舞い**で、しかも
    **毎回 `lever_hint` を読んで腕を選び直している**のだから、
    固定するほうが手順と食い違っています。天井に着いた腕を外して
    **残りで配分を割り直す**のが、実際にやっていることです。

    `realloc=False` で前の（配分を固定した）線に戻せます。
    **`tests/test_eta_realloc.py` が、固定に戻ったら落とします。**
    """
    if focus is not None or not realloc:
        out = {}
        for lever, a in arms.items():
            if focus is None:
                rate = a.get("rate")
            else:
                rate = a.get("focus_rate") if lever == focus else 0.0
            rate = (rate or 0.0) * rate_scale
            out[lever] = arm_speed.factor_at({**a, "rate": rate}, days)
        return out

    # --- 天井に着いた腕を外しながら、配分を割り直して進める ---
    #     速さは log で線形（`x(t) = exp(rate·t)`）なので、
    #     「次にどれかが天井に着く時刻」まで進めては割り直す、で厳密に解けます。
    logf = {k: 0.0 for k in arms}
    # **`cap == 1.00` は「天井が無い」ではなく「もう伸びない」**（2026-08-22 に直した）。
    #     ここは `> 1.0` で弾いていたので、**伸びしろゼロの腕だけが野放し**になり、
    #     軌跡が `density` を ×3.43 まで歩いていました（`arm_speed.factor_at` に全文）。
    caps = {}
    for k in arms:
        c = arms[k].get("cap")
        caps[k] = None if (c is None or c <= 0) else max(float(c), 1.0)
    # **足すのではなく、空いた配分だけを配り直します。**
    #     `rate` は「実績の配分のまま進んだ速さ」＝ `focus_rate × share`。
    #     天井に着いた腕の `share` が空くので、残りは
    #     `rate ÷ (残っている share の合計)` に上がります。
    #     **全部が生きている t=0 では、これは `rate` そのもの**です
    #     （`share` の合計は1）。だから前の線と食い違いません ——
    #     `tests/test_eta_trajectory.py` の「倍率は速さと日数から出ている」が、
    #     そこ（`x(t) = exp(rate·t)`）を固定しています。
    base_rate = {k: ((arms[k].get("rate") or 0.0) * rate_scale) for k in arms}
    share = {k: (arms[k].get("share") or 0.0) for k in arms}
    live = {k for k in arms if base_rate[k] > 0
            and (caps[k] is None or caps[k] > 1.0)}
    t = 0.0
    while t < days and live:
        tot = sum(share[k] for k in live)
        if tot <= 0:
            break
        step = float("inf")
        rate = {}
        for k in live:
            rate[k] = base_rate[k] / tot
            if caps[k] is not None and rate[k] > 0:
                step = min(step, (math.log(caps[k]) - logf[k]) / rate[k])
        step = min(step, days - t)
        if not (step > 0):                       # 天井に着いている腕は外して割り直す
            live -= {k for k in live
                     if caps[k] is not None and logf[k] >= math.log(caps[k]) - 1e-12}
            continue
        for k in live:
            logf[k] += rate[k] * step
        t += step
        live -= {k for k in live
                 if caps[k] is not None and logf[k] >= math.log(caps[k]) - 1e-12}
    out = {}
    for k in arms:
        x = math.exp(logf[k])
        out[k] = min(x, caps[k]) if caps[k] else x
    return out


def trajectory(m: dict, a0: dict, *, supply: dict | None = None,
               points: list[dict] | None = None, today: date | None = None,
               arms: dict | None = None, focus: str | None = None,
               rate_scale: float = 1.0,
               horizon: int = TRAJECTORY_HORIZON_DAYS,
               mix: dict | None = None) -> dict:
    """**腕が実測の速さで動いていったとき、いつ月20万に届くか。**

    2026-08-20 18:xx・オーナー指示（原文）——

    > 腕とやらをそう設定した時に達成がいつになるって予測じゃなくて、じゃあその腕を
    > そうなるまでにどれくらい時間がかかるのかとか予測しないとダメだよ。**特定条件の
    > 予測じゃなくて、実際にどういう軌跡を辿るか予測して、いつ達成かを予測するんだよ。**

    `lever_days` が出していたのは「**×2 になったら** 2027-01-19」で、
    **×2 に何日かかるかを1行も予測していませんでした。** 同じ回に
    「1日25本」を外したばかりです —— **満たせるか分からない前提の上に日付が乗る**
    という、まったく同じ欠陥が腕の側に残っていました。

    ## 解いている形

    腕の倍率は時間の関数です（`src/arm_speed`。閉じた前提15件の実測）:

        x_l(t) = min( exp(rate_l · t), 天井_l )

    `t` 日ぶん腕を動かしてから走らせたときの到達日は `t + D(x(t))` で、
    `D` は既存の `plan()` をそのまま解き直したものです。**軌跡の到達日は
    その最小値**です:

        T = min_t [ t + D(x(t)) ]

    最小を取る `t` が「**腕をどれだけ動かしてから走らせるのが最短か**」で、
    そこが 0 なら**いま走らせるのが最短**、大きければ**先に腕を動かせ**という意味です。

    **`t` のあいだの進みを足していません**（＝ 遅い側に倒しています）。
    腕を動かしている最中にも公開は続き、登録者も再生も積み上がるので、
    実際の到達はこれより早いほうへ動きえます。**上振れ側に倒すより、
    こちらのほうが目標に対して安全です** —— 早く出た日付は、待つ理由に使われます。

    返り: `days` / `date` / `t_work`（腕を動かす日数）/ `factors`（そのときの倍率）/
    `blocking`（届かないときに**名指しした理由**）。
    """
    today = today or today_jst()
    # **腕は実在する幅の中でしか伸びません**（`physical_caps`）。
    #     ここを外すと、軌跡は 1日 110,525本 のような世界を歩きます。
    arms = _capped_arms(a0, arms, supply=supply)

    best = {"days": NEVER, "t_work": None, "factors": None}
    rates = {k: ((a.get("focus_rate") if focus == k else (0.0 if focus else a.get("rate"))) or 0.0)
             * rate_scale for k, a in arms.items()}
    # **腕が全部止まっているなら、`t` を回す意味はありません**（`t=0` だけ見る）。
    moving = any(r > 0 for r in rates.values())
    # **天井まで行き着いたら、その先は `t` が増えるだけ**なので打ち切る。
    saturate = 0.0
    for k, a in arms.items():
        r, cap = rates[k], a.get("cap")
        if r > 0:
            # **天井 ×1.00 の腕は、0日で行き着いています**（`t` を回す意味がない）。
            #     ここも `cap > 1` で弾いていたので、**動かない腕のために
            #     地平（3年）ぶんの探索**を回していました。
            if cap is not None and cap > 0:
                saturate = max(saturate, math.log(max(float(cap), 1.0)) / r)
            else:
                saturate = max(saturate, float(horizon))
    last = int(min(horizon, math.ceil(saturate))) if moving else 0

    for t_work in range(0, last + 1):
        # **打ち切りは厳密です**（近似ではありません）。`D >= 0` なので、
        #     `t` が今の最良を超えた時点で `t + D(t)` は必ずそれより大きくなります。
        if t_work >= best["days"]:
            break
        fac = _factors_at(arms, t_work, focus=focus, rate_scale=rate_scale)
        try:
            a2 = analyse(m, points=points, scale=fac)
            pl2 = plan(m, a2, today=today, supply=supply, sensitivity=False, points=points,
                       mix=mix)
        except Exception:                                      # noqa: BLE001 — 回を止めない
            continue
        d = pl2.get("days_to_target", NEVER)
        if d >= NEVER:
            continue
        total = t_work + d
        if total < best["days"]:
            best = {"days": total, "t_work": t_work, "factors": fac,
                    "binding": pl2.get("binding"), "plan_days": d}

    out = {
        "arms": arms, "focus": focus, "rate_scale": rate_scale,
        "days": best["days"], "t_work": best["t_work"], "factors": best["factors"],
        "binding": best.get("binding"), "plan_days": best.get("plan_days"),
        "date": (today + timedelta(days=math.ceil(best["days"])))
                if best["days"] < NEVER else None,
        "searched_days": last,
    }
    out["blocking"] = _trajectory_blocking(arms, out)
    return out


@functools.lru_cache(maxsize=1)
def _recent_surface() -> tuple[float, int, str] | None:
    """積んである `data/reach.jsonl` の「いま続いている量」（**API 0単位**）。

    **1回の実行で1度だけ読みます** —— `plan()` は感度と軌跡のループから
    何十回も呼ばれるので、そのたびに帳面を開き直すと回が重くなります。
    読めなければ `None`（回を止めない・推測で埋めない）。
    """
    try:
        from src import reach_split
        rows = reach_split.dedupe(reach_split.load_rows())
        if not rows:
            return None
        long = (reach_split.summary(rows, reach_split.long_ids()).get("長尺") or {})
        # **「続いている量」は平均ではありません**（2026-08-26 に直した）。
        #     窓の中の1日が半分以上を占めていたら中央値へ落ちます
        #     （`reach_split.BURST_SHARE` に実測。08/21 の 1,285回 の 99.3% は
        #      その日に公開した5本の立ち上がりで、既存の長尺は 1〜3回でした）。
        recent = float(long.get("per_day_sustained")
                       or long.get("per_day_recent") or 0.0)
        if recent <= 0:
            return None
        return (recent, int(long.get("recent_days") or reach_split.RECENT_DAYS),
                str(long.get("per_day_sustained_basis") or ""),
                int(long.get("recent_zero_publish_days") or 0),
                reach_split.surface_forecast(
                    reach_split.summary(rows, reach_split.long_ids()),
                    make_per_day=_long_make_per_day(),
                    slots_per_day=_long_slots_per_day(),
                    stock=_long_stock()),
                float(long.get("ctr") or 0.0),
                # **CTR の分母と分子**（2026-08-29 に足した）。率だけを渡すと、
                #     「要る CTR に届きうるか」を**振れの外か中か**で言えません。
                #     実測 08/29: 67/4,001 ＝ 1.67%・95%区間 [1.32%, 2.13%] に対し
                #     要る CTR は 7.3% —— **区間の外**です。それを言わずに
                #     「ここから先で効くのは CTR」と出していました。
                (float(long.get("impressions") or 0.0),
                 float(long.get("clicks") or 0.0)))
    except Exception:  # noqa: BLE001  （測れないことで回を止めない）
        return None


def _long_make_per_day() -> float | None:
    """**長尺を1日に何本 作れているか**（実測。読めなければ `None`）。

    `long_supply_per_day()` の `per_day`。**計画値へは落としません** ——
    ここが要るのは「予定表の穴が、放っておいて埋まるか」の判定で、
    **願望で割ると『埋まります』と出て、実際には空のまま公開日が来ます。**
    """
    try:
        got = long_supply_per_day()
        # **`rate` です**（`per_day` ではありません）。**測れていない回は使わない** ——
        # `measured: False` のときの数は計画値で、そこで割ると「埋まります」と出ます。
        if not got.get("measured"):
            return None
        v = float(got.get("rate") or 0.0)
        return v if v > 0 else None
    except Exception:                                  # noqa: BLE001 — 回を止めない
        return None


def _long_stock() -> int | None:
    """**いま在る長尺向けのテーマ**（本）。読めなければ `None`。**API 0単位。**

    `src/supply.py` の `surfaces()["long"]["stock"]` ＝ 未投稿・`calc` あり・
    **`s-` で始まらない**題（`batch_build.pick` の `long_usable` と同じ数え方。
    `scripts/batch_build.py`「`long_usable = [t for t in usable if not
    t["id"].startswith("s-")]`」）。

    **なぜ要るか**: `_long_make_per_day()` が測っているのは**描画の速さ**で、
    描く題材が在るかは1つも見ていません。2026-08-29 の実測は
    **描画 9.14本/日 ／ 在庫 0本** —— それで `dry_fill` は
    「放っておいて埋まります」と出していました（`reach_split.dry_fill` の docstring）。

    **`None` は「在庫0」ではありません。** 読めなかった回に 0 を返すと、
    その回は全部「題材が無い」になります。`dry_fill` は `None` を
    「測っていない」として、これまでどおりの枝へ落とします。
    """
    try:
        from src import supply                          # noqa: PLC0415
        v = (supply.surfaces() or {}).get("long", {}).get("stock")
        return None if v is None else int(v)
    except Exception:                                  # noqa: BLE001 — 回を止めない
        return None


def _long_family_ceiling() -> dict | None:
    """**長尺を1日に何本まで出せるか、の「構造の天井」**（族の数）。**API 0単位。**

    `_long_make_per_day()`（描く速さ）でも `long_supply_per_day()`（実測の産出）でも
    ありません。**在庫がいくら在っても、`batch_build.pick` が7日ぶんで取れるのは
    「族の数 × `per_calc`」まで**です（`scripts/topic_forge.print_long_stock()` と
    同じ式。`_drop_queue_tail_calcs` が、これから7日の予約に載っている calc を
    丸ごと落とすため）。

    ## なぜ段2 に要るか（2026-08-29 に足した）

    段2（門2a・長尺4,000時間）の表は L＝1/2/4本/日 の3列しか持たず、実測の
    1本あたり再生を当てて「**いちばん甘い行でも 5倍 足りない。全部の行を
    下回っています**」と印字し、そのあと「段2 が測るのは**1本あたりを何倍に
    できるか**」で閉じていました。**Lを凍らせて、もう一方だけを解いています。**

    **Lは、この機械が自分で動かせる側です。** 1本あたり再生は配信が決めますが、
    Lは族を1つ足せば `per_calc`本/7日 動きます。だから合格点は**Lの側でも解いて
    並べる**こと（`CLAUDE.md`「裸の『届きません』を出さないこと」／
    「何を何倍にすれば、いつ届くか」）。

    返り値:

        families    いま長尺の在庫を持っている族の数
        ceiling_7d  7日ぶんで `pick` が返せる上限（本）
        per_day     その 1日あたり
        spare       `config/topics.yaml` に `calc` が在って、**長尺のテーマを
                    1件も持っていない族**の数（＝ 表を書かずに族を増やせる余地。
                    `topic_forge` の実測 15分/件）
        stock       長尺向けの在庫（本）

    **覆る条件**: `per_calc` か `_drop_queue_tail_calcs` の窓が変わったら、この式ごと
    変わります —— どちらも `topic_forge` から読んでおり、**ここには写していません**。
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import topic_forge                              # noqa: PLC0415
        from src import config, dupes                   # noqa: PLC0415

        pool = config.load_topics()["topics"]
        used = {r["topic"] for r in dupes.ledger_rows() if r.get("topic")}
        longs = [t for t in pool
                 if t.get("calc") and t["id"] not in used
                 and not str(t["id"]).startswith("s-")]
        families = {t["calc"] for t in longs}
        per_calc = topic_forge.PER_CALC_DEFAULT
        window = topic_forge.LONG_WINDOW_DAYS
        ceiling = min(len(longs), len(families) * per_calc)
        spare = {t["calc"] for t in pool if t.get("calc")} - families
        return {"families": len(families), "ceiling_7d": ceiling,
                "per_day": (ceiling / window) if window else 0.0,
                "per_calc": per_calc, "window": window,
                "spare": len(spare), "stock": len(longs)}
    except Exception:                                  # noqa: BLE001 — 回を止めない
        return None


def _long_needed_per_day(a: dict, lpv: float, days: float) -> list[dict]:
    """**1本あたり再生を実測で固定したとき、長尺を1日何本 出せば門2a が開くか。**

    `_long_break_even()` の裏返しです。あちらはLを筋書き（1/2/4本/日）で固定して
    1本あたり再生を解き、こちらは**1本あたり再生を実測で固定してLを解きます。**

        L ＝ 要る視聴分 ÷ (1本あたり再生 × 門1までの日数 × 1再生の視聴分)

    **両方 要ります。** 片方だけだと、**動かせる側が画面に出ません** ——
    実測 2026-08-29: 表は L≤4本/日 しか持たず「全部の行を下回っています」で
    終わっており、**Lを上げれば開く**とはどこにも出ていませんでした。
    """
    out: list[dict] = []
    for r in a.get("long_break_even") or []:
        per_view = r["min_per_view"]
        slots = lpv * days * per_view
        out.append({"label": r["label"], "min_per_view": per_view,
                    "per_day": (a["long_minutes_needed"] / slots)
                    if slots > 0 else float("inf")})
    return out


def _long_slots_per_day() -> int | None:
    """**1日に長尺を置ける枠の数**（`batch_build._long_ring()` の実測の輪）。

    定数を写さないこと —— `_long_ring()` は `day_cap.long_form()` が
    崩れを見つけたら自動で1つ下げます。**写した瞬間に古くなります。**
    """
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import batch_build                             # noqa: PLC0415
        return len(batch_build._long_ring())
    except Exception:                                  # noqa: BLE001 — 回を止めない
        return None


def _with_recent_surface(mix: dict) -> dict:
    """点に「いま続いている量」と「**これからの予定で立つ量**」を足す。

    足せなければ**そのまま返す**（推測で埋めない）。
    `imp_day_planned` の中身は `src/reach_split.surface_forecast()` の docstring。
    """
    got = _recent_surface()
    if not got:
        return mix
    out = {**mix, "imp_day_recent": got[0], "imp_day_recent_days": got[1],
           "imp_day_recent_basis": got[2], "imp_day_recent_dry": got[3]}
    fc = got[4]
    if fc:
        out["imp_day_planned"] = fc["per_day_planned"]
        out["imp_day_planned_pubs"] = fc["pubs_per_day"]
        out["imp_day_per_publish"] = fc["per_publish"]
        out["imp_day_dry_span"] = fc["dry_span"]
        out["imp_day_dry_fill"] = fc.get("dry_fill")
    if len(got) > 5 and got[5]:
        out["imp_ctr_long"] = got[5]
    if len(got) > 6 and got[6]:
        out["imp_ctr_n"], out["imp_ctr_k"] = got[6]
    return out


def _wilson(k: float, n: float, z: float = 1.96) -> tuple[float, float] | None:
    """**割合の95%区間**（Wilson）。`k` 回のうち `n` 回。読めなければ `None`。

    正規近似（`p ± z√(p(1-p)/n)`）ではなく Wilson を使うのは、**分子が小さい側で
    区間が負に食い込まないから**です。ここで測るのは CTR で、実測は 1〜2% ——
    正規近似が最も外れる帯です。

    **なぜ要るか**（2026-08-29）: 段2 は「要る CTR 7.3%・サムネと題」と、
    **次に引く腕を名指し**していました。実測は 67/4,001 ＝ 1.67% で、
    区間は [1.32%, 2.13%]。**7.3% は区間の 3.4倍 外**です。
    「サムネを直せば届く」と読める字面が、**実測が否定している的**に向いていました。
    """
    if n <= 0 or k < 0:
        return None
    p = k / n
    d = 1.0 + z * z / n
    c = p + z * z / (2 * n)
    r = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (max(0.0, (c - r) / d), min(1.0, (c + r) / d))


def _gate2_surface_basis(mix: dict) -> tuple[float | None, str, dict]:
    """**段2 が読むべき面は「いま続いている量」です**（2026-08-25 に直した）。

    ## 直した理由（**同じ帳面の読み手2つが、逆を向いていた**。この形は4件目）

    ここは長らく `mix["imp_day"]` を読んでいました。あれは
    `rpm_mix.surface_ceiling()` の**天井**で、2026-08-24 から
    **38日でいちばん良かった1日**（1,285.0回/日・08/21）です。
    天井の質問（「腕 `rpm` は届きうるか」）にはそれで正しい。
    **段2 の質問は別です** ——「門2a を 450日 かけて開けられるか」。
    **1日ぶんの当たりは、450日 続く量の答えになりません。**

    実測（2026-08-25・同じ `data/reach.jsonl`）:

        eta.py 段2   最大の1日 1,285.0回/日 → 合格点 191 → **面は足りています（6.7倍）**
        status.py    直近7日  190.6回/日 → 段4 の要求  → **87倍 足りません**

    **同じ回の、同じ帳面です。** そして段2 の文はそのまま
    「ここから先で効くのは CTR のほう（サムネと題）」と、次の回に引く腕まで
    名指ししていました。**面が足りていないのに CTR を直しても、面は動きません。**

    返り: `(面の回/日, 何で出したか, 3つの数)`。**古い点は `imp_day_recent` を
    持ちません** —— そのときは**平均（下振れ側）へ落ちます。**
    最大へ落とすと、測っていない回ほど「足りている」と出ます。
    """
    recent = float(mix.get("imp_day_recent") or 0.0)
    mean = float(mix.get("imp_day_mean") or 0.0)
    top = float(mix.get("imp_day_max") or 0.0)
    planned = float(mix.get("imp_day_planned") or 0.0)
    dry_in_window = int(mix.get("imp_day_recent_dry") or 0)
    others = {"recent": recent or None, "mean": mean or None, "max": top or None,
              "recent_days": mix.get("imp_day_recent_days"),
              "planned": planned or None,
              "planned_pubs": mix.get("imp_day_planned_pubs"),
              "per_publish": mix.get("imp_day_per_publish"),
              "dry_span": mix.get("imp_day_dry_span"),
              "dry_fill": mix.get("imp_day_dry_fill"),
              "ctr": mix.get("imp_ctr_long"),
              "ctr_n": mix.get("imp_ctr_n"), "ctr_k": mix.get("imp_ctr_k")}
    # **窓が「公開を止めていた日」で埋まっているなら、中央値は段2 の答えではありません**
    #     （2026-08-26。`src/reach_split.surface_forecast()` の docstring に実測）。
    #     段2 の問いは「門2a を 450日 かけて開けられるか」で、
    #     **これから長尺を何本 公開するかは控えに入っています**（API 0単位）。
    #     公開が0本の日を1日でも窓に含んだ中央値は、
    #     **「公開を止めたら面はいくつか」**の答えで、別の問いです。
    #     **中央値のほうは消しません** —— `others["recent"]` にそのまま残り、
    #     印字は両方を同じ行に並べます（どちらも正しく、問いが別だから）。
    if planned > 0 and dry_in_window > 0:
        pubs = float(mix.get("imp_day_planned_pubs") or 0.0)
        per_pub = float(mix.get("imp_day_per_publish") or 0.0)
        basis = (f"これから{mix.get('imp_day_recent_days') or 7}日の予約から"
                 f"（公開1本あたり {per_pub:,.1f}回 × 長尺 {pubs:.2f}本/日）"
                 f"。**直近の中央値 {recent:,.1f}回/日 は、"
                 f"窓の{dry_in_window}日が長尺の公開0本だったぶん**")
        return planned, basis, others
    if recent > 0:
        basis = (mix.get("imp_day_recent_basis")
                 or f"直近{mix.get('imp_day_recent_days') or 7}日の平均")
        return recent, str(basis), others
    if mean > 0:
        return mean, "全期間の平均（**直近の点をまだ積んでいません**）", others
    # **2026-08-24 より前の点は、天井も平均でした**（`imp_day_basis` がまだ無い）。
    #     その `imp_day` は平均そのものなので、段取りの分母に使えます。
    if not mix.get("imp_day_basis") and float(mix.get("imp_day") or 0.0) > 0:
        v = float(mix["imp_day"])
        others["mean"] = v
        return v, "全期間の平均（この点は最大と分けて記録する前のもの）", others
    # **最大の1日しか無い点では、段2 の答えを出しません。**
    #     出すと、測っていない回ほど「足りている」と印字されます。
    return None, "測れていません", others


def _gate2_surface_note(imp_day: float, need_day: float,
                        basis: str = "最大の1日", others: dict | None = None) -> str:
    """**段2 の面が、合格点に対して足りているか足りていないか。**

    **どの数で出したかを必ず同じ行に書くこと。** 2026-08-24〜25 の壊れ方は
    「倍率の向き」ではなく「**分母の取り違え**」で、向きだけ直すと再発します。
    """
    others = others or {}
    head = (f"**いまの面（長尺のインプレッション {imp_day:,.1f}回/日・実測・"
            f"{basis}）は、CTR 100% でも {imp_day:,.0f}回/日**。"
            f"合格点は {need_day:,.0f}回/日。")
    span = ""
    if others.get("mean") and others.get("max"):
        span = (f"　（同じ帳面の他の読み: 全期間の平均 {others['mean']:,.1f}"
                f"／最大の1日 {others['max']:,.1f}回/日。"
                "**天井にだけ最大を使い、段取りには使わないこと**）")
    # **予定表の穴を、同じ行に出すこと**（2026-08-26）。面が公開で立つ以上、
    #     長尺の予約が0本の日は面も0に近づきます。**足りている/足りないより先に、
    #     どこで落ちるか**を見せる —— 直す先はサムネでも題でもなく、予定表です。
    dry = others.get("dry_span")
    if dry and dry[2] >= 3:
        a, b, n = dry
        head_dry = (f"{a[:4]}-{a[4:6]}-{a[6:]}〜{b[:4]}-{b[4:6]}-{b[6:]} の {n}日 は"
                    f"長尺の予約が0本です（控えの実物）。")
        # **「その日に置け」と言わないこと**（2026-08-26 夜に直した）。
        #     予約の時刻を決めているのは `uploader.next_publish_at()` だけで、
        #     **手前から順に**埋めます。だから未来の空き日は「穴」ではなく
        #     「**まだ順番が来ていない日**」で、作りつづけていれば頭が通過します。
        #     実測（`data/uploaded.jsonl` 長尺28本・全部 08/24 以降のアップ）:
        #     08/29 は 3.2〜3.7日前・09/06 は 10.9〜11.7日前・09/20〜10/10 は 25〜45日前
        #     （最後のは 1日1本 だった頃の残り）。空いているのは**その2つのあいだ**。
        #     **既にある本を後ろへ動かして埋めると、判定が遅れるぶん必ず損します。**
        fill = others.get("dry_fill")
        if not fill:
            span += (f"　[!] **{head_dry}** "
                     "**埋まるかどうかは、まだ数えていません**"
                     "（作る速さか、1日の枠のどちらかが読めていません）。"
                     "**『その日に置く』と読まないこと** —— "
                     "予約は手前から埋まるので、**未来の空き日は"
                     "『順番が来ていない日』かもしれません**")
        elif fill["ok"]:
            span += (f"　（{head_dry}"
                     f"ただし**放っておいて埋まります** ——"
                     f" 手前の空き枠 {fill['open_slots']}本 ÷ 作る速さ"
                     f" {fill['make_per_day']:.2f}本/日 ＝ **{fill['reach_days']:.1f}日** で"
                     f"頭が通過し、穴の初日までは {fill['gap_days']}日 あります。"
                     f"**その日に置きにいかないこと** —— 既にある本を後ろへ動かすので、"
                     f"判定が遅れるぶん損します。"
                     f"**割れる線は作る速さ {(fill.get('need_per_day') or 0):.2f}本/日**"
                     f"（いま {fill['make_per_day']:.2f}。"
                     f"余裕 {fill['gap_days'] - fill['reach_days']:.1f}日）"
                     # **題材の側も一緒に出すこと**（2026-08-29）。ここが
                     #     「埋まります」だけだった回、在庫は 0本 でした。
                     + (f"。**題材の在庫 {fill['stock']}本**（空き枠 "
                        f"{fill['open_slots']}本 ぶんは在ります）"
                        if fill.get("stock") is not None
                        else "。**題材の在庫は読めていません**"
                             "（`src/supply.py` が返さなかった回）")
                     + "）")
        elif fill.get("bound") == "topics":
            # **描画は速いが、描くものが無い枝**（2026-08-29 に足した）。
            #     ここを「作る速さです」と言うと、9.14本/日 出ている描画を
            #     さらに速くしにいきます —— 律速は `src/calc/` の節のほうです。
            span += (f"　[!] **{head_dry}** "
                     f"面は公開で立つので、**そこで {imp_day:,.0f}回/日 は保ちません。**"
                     f" 手前の空き枠 {fill['open_slots']}本 に対し、"
                     f"**長尺向けのテーマの在庫は {fill['stock']}本**です"
                     f"（`s-` で始まらない未投稿の題／`src/supply.py`）。"
                     f"**描く速さは足りています**"
                     f"（{fill['make_per_day']:.2f}本/日 ＝ 空き枠なら"
                     f" {fill['reach_days']:.1f}日 ・穴まで {fill['gap_days']}日）——"
                     f" **足りないのは題材のほうです。**"
                     f" あと **{fill['topics_needed']}本**"
                     f"（{(fill.get('topics_per_day_needed') or 0):.2f}本/日 × "
                     f"{fill['gap_days']}日）。"
                     # **「節を足せ」は、この穴には効きません**（2026-08-29 に踏んだ）。
                     #     ここは長らく「直す先は `src/calc/` の節です ——
                     #     (2) 既にある表に節を足して」と言っていました。
                     #     **同じ repo の `topic_forge.print_long_stock()` は、
                     #     同じ穴について逆を言っています**:
                     #       「**いま在庫は 17件 あるのに 8本 しか取れません** ——
                     #         詰まっているのは節ではなく**族の数**です。
                     #         **同じ族に節を足しても、この数は1本も増えません。**」
                     #     実物はあちらのほうです（`ceiling = min(len(longs),
                     #     len(families) * PER_CALC_DEFAULT)` を実際に計算している）。
                     #     `batch_build` は1つの calc から `--per-calc`（既定2）本まで
                     #     しか取らないので、**7日ぶんの上限は族の数で決まります。**
                     #     字面どおりに従うと、在庫（`fill['stock']`）だけ増えて
                     #     **穴は1本も埋まりません**。
                     #     **覆る条件**: `PER_CALC_DEFAULT` が 1 に落ちるか
                     #     `_drop_queue_tail_calcs` が消えたら、上限は族の数で
                     #     決まらなくなります（`print_long_stock()` の式ごと変わる）。
                     f"**直す先は描画でも予定表でもなく、"
                     f"`src/calc/` の**族**のほうです** ——"
                     f" 在庫を増やしても、`batch_build` は1つの calc から"
                     f" 2本 までしか取りません。"
                     f"**7日ぶんの上限は族の数で決まります**"
                     f"（`python scripts/topic_forge.py --list` の末尾。"
                     f"**「(2) 既にある表に節を足す」は族を増やしますが、"
                     f"長尺のテーマを既に持っている族に足しても1本も増えません**）。"
                     f"（**4,000時間の門に入るのは長尺だけ**なので、"
                     f"ショートを足してもこの穴は1本も埋まりません）")
        else:
            span += (f"　[!] **{head_dry}** "
                     f"面は公開で立つので、**そこで {imp_day:,.0f}回/日 は保ちません。**"
                     f" 手前の空き枠 {fill['open_slots']}本 を、作る速さ"
                     f" {fill['make_per_day']:.2f}本/日 で埋めるには"
                     f" **{fill['reach_days']:.0f}日** かかり、穴の初日まで"
                     f" {fill['gap_days']}日 しかありません。"
                     f"**直す先はサムネでも題でも予定表でもなく、作る速さです** ——"
                     f" あと **{(fill.get('short_per_day') or 0):.2f}本/日**"
                     f"（既にある本を後ろへ動かして穴を埋めると、判定が遅れるぶん必ず損します）")
    ratio = (need_day / imp_day) if imp_day else float("inf")
    # **「1.0倍 足りません」を印字しないこと。** 191 対 190.6 は倍率にすると
    #     ×1.00 で、丸めると「足りている」と読める字面になります。
    #     **同点は足りていない側**（合格点は 450日 続ける数なので、
    #     ちょうどの面には1日ぶんの余裕もありません）。
    if 1.0 < ratio < 1.05:
        return (head + " **ちょうど同じ（×1.00）＝ 余裕がありません**。"
                "合格点は 450日 続ける数なので、**いまの面では1日でも落ちたら届きません**。"
                "**先に増やすのはインプレッションのほうです**（`src/reach_split.py`）" + span)
    if need_day > imp_day:
        return (head + f" **{ratio:,.1f}倍 足りません**。"
                "**足りないのはインプレッションで、サムネと題（CTR）では動きません**"
                "（`src/reach_split.py`）" + span)
    # **「足りています」を裸で出さないこと**（2026-08-26）。この節は
    #     **CTR 100% を仮に置いた面**の話で、実際に再生になるのは
    #     `面 × 実測の CTR` です。要る CTR と実測を並べないと、
    #     「面は足りている ＝ もう手はいらない」と読めます。
    got_ctr = float(others.get("ctr") or 0.0)
    need_ctr = need_day / imp_day * 100
    gap_ctr = ""
    if got_ctr > 0:
        gap_ctr = (f"　**実測の CTR は {got_ctr:.2f}%** ＝ いまのままなら"
                   f" 長尺の再生は 1日 {imp_day * got_ctr / 100:,.1f}回 で、"
                   f"合格点に **{need_ctr / got_ctr:,.1f}倍 足りません**")
        # --- **要る CTR が、実測の振れの中か外か**（2026-08-29 に足した）---
        #
        # ここは長らく「（面ではなく CTR が縛っている、と読むこと）」で閉じ、
        # **次に引く腕を「サムネと題」と名指し**していました。
        # **要る CTR が実測の区間に入るかを、1度も見ていません。**
        # 実測 08/29: 67/4,001 ＝ 1.67%・95%区間 [1.32%, 2.13%]、要る CTR 7.3%
        # ＝ **区間の 3.4倍 外**。サムネを直して届く帯ではありません。
        #
        # **同じ不足は、面の側でも閉じられます。** 面は長尺の公開本数に比例し
        # （`others["per_publish"]` ＝ 公開1本あたりのインプレッション・実測）、
        # **本数はこの機械が動かせる側**です（族の数。`_long_family_ceiling`）。
        # だから「CTR では届きません」で終えず、**面の側の倍率を同じ行に出します**
        # （`CLAUDE.md`「裸の『届きません』を出さないこと」）。
        #
        # **覆る条件**: 区間の上端が要る CTR を超えたら（＝ 標本が薄い／CTR が
        # 上がった）、この枝は自分で「区間の中」と印字して名指しをやめます。
        n = float(others.get("ctr_n") or 0.0)
        k = float(others.get("ctr_k") or 0.0)
        ci = _wilson(k, n) if n > 0 else None
        if ci:
            lo, hi = ci[0] * 100, ci[1] * 100
            gap_ctr += (f"　（実測 {k:,.0f}/{n:,.0f}・**95%区間 [{lo:.2f}%, {hi:.2f}%]**）")
            if need_ctr > hi:
                short = need_ctr / hi
                gap_ctr += (f"　[!] **要る CTR {need_ctr:.1f}% は、その区間の外です"
                            f"（上端の {short:,.1f}倍）** ——"
                            "**サムネと題では届きません。**"
                            "「ここから先で効くのは CTR」と読まないこと")
                per_pub = float(others.get("per_publish") or 0.0)
                pubs = float(others.get("planned_pubs") or 0.0)
                if per_pub > 0:
                    need_imp = need_day / (got_ctr / 100)
                    line = (f"　**同じ不足を面の側で閉じるなら**: 要る面は"
                            f" {need_imp:,.0f}回/日（いま {imp_day:,.0f}）＝"
                            f" **{need_imp / imp_day:,.1f}倍**")
                    need_pub = need_imp / per_pub
                    if pubs > 0:
                        line += (f"、公開1本あたり {per_pub:,.1f}回 なので"
                                 f" **長尺 {need_pub:,.1f}本/日**"
                                 f"（いま {pubs:.2f}本/日）")
                    line += ("。**そちらは動かせる側です**（族の数。"
                             "下の「門2a を長尺で開けるなら」の節）")
                    # --- **その「動かせる側」にも、測った天井があります** ---
                    #     （2026-08-30・最適化の回。**同じ出力の2行が 5.75倍 離れていた**）
                    #
                    #     ここは長らく「そちらは動かせる側です（族の数）」で終わっていました。
                    #     ところが**同じ走りの下のほう**に、こう出ています ——
                    #
                    #       「長尺の面: 7本/日 で崩れました → **上限は 6本/日**」
                    #        （`src/day_cap.long_form()`・齢48時間でそろえた実測）
                    #
                    #     実測 2026-08-30: 要る本数 **34.5本/日** に対し、測った天井 **6本/日**。
                    #     **5.75倍 足りません。** つまり族をいくら増やしても、
                    #     この段は族では閉じません。**それでも上の行だけが読まれ、
                    #     直近の ship は2件とも長尺の族と長尺の予約**でした
                    #     （`data/runs.jsonl` 08/30 01:58 と 02:12）。
                    #
                    #     **天井そのものは動かせます**（`day_cap.long_form()` の「覆る条件」
                    #     ＝ 上限より多く出した日に、上限より後ろの本が再生を取ったとき）。
                    #     **だからこれは「無理」ではなく「先に天井を測り直す前提が要る」**です。
                    #     天井を据え置いたまま族だけ足す道は、そこで止まります。
                    #
                    #     **覆る条件**: `day_cap.long_form()` の上限が要る本数を上回ったら、
                    #     この断りは自分で消えます（数で書いてあるので、写しではありません）。
                    try:
                        from src import day_cap as _dc
                        _lf = _dc.long_form()
                    except Exception:                      # 帳面が読めない回は黙って飛ばす
                        _lf = {}
                    _cap_long = float(_lf.get("most") or 0) - 1 if _lf.get("collapsed") else 0.0
                    if _cap_long > 0 and need_pub > _cap_long:
                        line += (f"　[!] **その「動かせる側」にも、測った天井があります** ——"
                                 f" 長尺の面は **{_lf.get('most')}本/日 で崩れ**、上限は"
                                 f" **{_cap_long:,.0f}本/日**（`src/day_cap.long_form()`）。"
                                 f" 要る {need_pub:,.1f}本/日 は、その"
                                 f" **{need_pub / _cap_long:,.2f}倍**です ——"
                                 "**族を増やしても、この段は族では閉じません。**"
                                 "先に動かすのは天井のほう"
                                 "（`day_cap.long_form()` の「覆る条件」＝"
                                 "上限より多く出した日に、上限より後ろの本が再生を取ること。"
                                 "**前提を1件 立てて測る手**です）")
                    gap_ctr += line
            else:
                gap_ctr += (f"　要る CTR {need_ctr:.1f}% は**その区間の中**です ——"
                            "サムネと題で届きうる帯（標本を増やすと分かれます）")
        else:
            gap_ctr += "（面ではなく CTR が縛っている、と読むこと）"
    return (head + f" **面は足りています（{imp_day / need_day:,.1f}倍）** —— "
            f"**ただしそれは CTR 100% を置いた話です**"
            f"（要る CTR {need_ctr:.1f}%。`src/reach_split.py`）" + gap_ctr + span)


def _trajectory_blocking(arms: dict, out: dict) -> list[str]:
    """**軌跡が出なかったとき、何が塞いでいるかを名指しする。**

    「届きません」で終えないこと（`plan()` の `blocking` と同じ作り）。
    ここが空のまま「出ません」と印字したら、**次の回は何を測ればいいか分かりません。**
    """
    if out["date"] is not None:
        return []
    why: list[str] = []
    for lever, a in arms.items():
        if not a.get("rate"):
            note = a["missing"][-1] if a.get("missing") else "速さが出ていない"
            why.append(f"`{lever}` が動きません（{note}）")
        cap = a.get("cap")
        if cap and a.get("ceiling"):
            c = a["ceiling"]
            why.append(f"`{lever}` は **×{cap:.2f} が天井**（実測 {c['value']:,} ・{c['unit']}）。"
                       f"外す腕は `{c.get('escape')}`")
    if not why:
        why.append(f"腕を {out['searched_days']:,}日 動かしても、到達日が出ませんでした"
                   "（天井そのものが目標の下）")
    return why


def trajectory_choice(m: dict, a0: dict, base: dict, **kw) -> list[dict]:
    """**この回の回転を、どの腕に振るのがいちばん早いか。**

    `base` は実績の配分のまま進んだ軌跡です。ここが返すのは
    **「全部この腕に振ったら軌跡が何日動くか」** —— 名前ではなく日数で選べる形にします。
    **回転は1本しかありません。** 4本とも全力で動かす線は、実在しません。
    """
    rows = []
    for lever in arm_speed.ARMS:
        t = trajectory(m, a0, focus=lever, **kw)
        rows.append({
            "lever": lever, "days": t["days"], "date": t["date"],
            "t_work": t["t_work"],
            "gain": (base["days"] - t["days"]) if (base["days"] < NEVER and t["days"] < NEVER)
                    else (NEVER - t["days"] if t["days"] < NEVER else 0.0),
            "reachable": t["days"] < NEVER,
        })
    rows.sort(key=lambda r: (r["days"], r["lever"]))
    return rows


def trajectory_all(m: dict, a0: dict, *, supply: dict | None = None,
                   points: list[dict] | None = None,
                   today: date | None = None, full: bool = True) -> dict:
    """**軌跡を1回で全部解く**（本線・幅・腕べつ）。`main` と検査の入口はここ1つ。

    返り:

        base     実績の配分のまま進んだ軌跡（**これが印字する1つの日付**）
        fast/slow 当たる確率の幅（Jeffreys 90%）の両端で解き直した軌跡
        choice   「全部この腕に振ったら」を腕べつに解いたもの（早い順）
        streak   いま何連続で外しているか
        band     当たり件数と確率の幅（出どころ）

    ## `full=False` ——**印字しない呼び手のために、印字にしか使わない線を解かない**
    ##                 （2026-08-28。**`retro.py` の持ち越し① / (a2) 問い1 が8回中7回**）

    **`--reflect` は、この関数が解く7本の軌跡のうち3本を捨てています。**
    `fast` / `slow`（幅の両端）と `planned`（台帳の配分）は
    **`headline()` と `_report_trajectory()` の印字にしか使われません** ——
    `data/eta.jsonl` に積む行を組む `_row()` は、この3つを1つも読みません
    （読むのは `base` / `choice` / `arms` / `band` の4つだけ）。
    ところが `reflect()` は 10行しか印字しないので、**3本ぶんが丸ごと捨てられます。**

    実測（2026-08-28・この機械の上で1本ずつ時間を取った）。
    **同じ回に `_view_cap_per_day()`（`day_cap.cap()` を1回に畳む）も入れた**ので、
    2つの列を並べます::

                              畳む前     畳んだ後
        analyse + supply_state   0.3秒     0.3秒
        plan(sensitivity=True)   4.1秒     1.1秒
        軌跡 base               20.0秒     2.7秒
        軌跡 fast               16.1秒     2.5秒   ← `--reflect` は捨てる
        軌跡 slow               30.6秒     4.0秒   ← `--reflect` は捨てる
        軌跡 planned            21.9秒     3.1秒   ← `--reflect` は捨てる
        軌跡 choice（腕4本で）   14.5秒     2.9秒
                               ------    ------
        solve(full=True)       107.5秒    16.6秒
        solve(full=False)       38.9秒   **7.0秒** ← `--reflect` が通る道

    **`--reflect` は 107.5秒 → 7.0秒（-93%）**。2つの直しは別々に効きます ——
    `full=False` が「解く本数」を、`_view_cap_per_day()` が「1本の重さ」を削ります。

    **幅の両端（`fast`/`slow`）がいちばん高い**のは、当たる確率を下げた線ほど
    腕が遅く伸びて、`t` の探索が長く回るからです。
    **捨てる3本のほうが、印字する本線より高い**という配分でした。

    **なぜ「日付が変わらない」と言えるか。** `full` は
    **どの線を解くかだけ**を決めます。`base` も `choice` も `arms` も
    まったく同じ引数で同じ関数を通るので、**`_row()` が組む行は 1文字も変わりません**
    （`tests/test_eta_reflect_light.py` が、`fast`/`slow`/`planned` に
    でたらめを入れた行と入れない行が**同一**であることを固定します。
    誰かが `_row()` にこの3つを読ませたら、その検査が落ちます）。

    **`solve()` の docstring が「2つの道が別々に古びる」と言っているのは、
    `reflect()` が自前で解き直す形のことです。** ここは道を分けていません ——
    通る関数は同じ1本で、**末端の3本を解くか解かないか**だけが違います。

    **覆る条件**: `_row()` が `fast` / `slow` / `planned` のどれかを積むように
    なったら、`reflect()` は `full=True` に戻すこと（検査が先に落ちます）。
    """
    today = today or today_jst()
    rows = arm_speed.closed()
    bd = arm_speed.band(rows)
    arms = _capped_arms(a0, supply=supply)
    kw = dict(supply=supply, points=points, today=today, arms=arms)
    base = trajectory(m, a0, **kw)
    p = bd.get("p") or 0.0
    fast = slow = None
    if full and p > 0 and bd.get("lo") and bd.get("hi"):
        # **速さは当たる確率に比例します**（`rate = p·log g·θ`）。だから幅は
        # 確率の幅をそのまま倍率にして入れます。**腕ごとの p は別ですが、
        # 幅の出どころは1つ**（標本15件）なので、同じ比を当てています。
        fast = trajectory(m, a0, rate_scale=bd["hi"] / p, **kw)
        slow = trajectory(m, a0, rate_scale=bd["lo"] / p, **kw)
    # --- **台帳が実際に用意している配分**で、もう一度解く（2026-08-26・最適化の回） ---
    #
    # `base` は `share`（**閉じた前提の腕べつの割合 ＝ 過去にどう振ってきたか**）で
    # 解いています。**しかし未来の配分は、過去ではなく「いま開いている前提」が
    # 既に決めています** —— 16本作って2週間待たないと1件も閉じないので、
    # これから閉じるのは台帳に開いている分だけです。
    #
    # 実測 2026-08-26（`src.arm_speed.planned()`）::
    #
    #     実績（閉じた21件）   per_video 60% ／ density 25% ／ sub_rate 10% ／ rpm  5%
    #     台帳（開いた 5件）   rpm 60% ／ sub_rate 20% ／ density 20% ／ **per_video 0%**
    #
    # 軌跡は「回転の 60% が per_video に回る」前提で日付を出しますが、
    # **台帳には per_video の前提が1件もありません。**
    # どちらの数もこの機械が持っていて、**照らし合わせている所がどこにも
    # ありませんでした**（`docs/JOURNAL.md`「同じことを2か所が別々に言っていて、
    # 片方しか読まれていない」の形）。
    #
    # **これは `base` を置き換えるものではありません。** 台帳は書き換えられるので、
    # 「このまま台帳どおりに閉じたら」の線です。**2つの差が、
    # 「次の前提をどの腕に立てるか」で動く日数**そのものになります。
    pln = None
    try:
        pl_share = arm_speed.planned() if full else {}
        if pl_share.get("n"):
            # **`kw` は既に `arms` を持っています。** そのまま `arms=` を足すと
            #     `TypeError: got multiple values for keyword argument 'arms'` になり、
            #     下の `except` が飲み込んで **この節ごと黙って消えます**
            #     （2026-08-26、書いた直後に踏みました。印字が1行も出ませんでした）。
            kw2 = {k: v for k, v in kw.items() if k != "arms"}
            pln = trajectory(m, a0, arms=_realloc_arms(arms, pl_share["share"]), **kw2)
            pln["planned"] = pl_share
    except Exception:                                          # noqa: BLE001 — 回を止めない
        pln = None
    return {
        "base": base, "fast": fast, "slow": slow, "planned": pln,
        "theta": _theta_days(m, a0, base, rows, kw) if full else None,
        "choice": trajectory_choice(m, a0, base, **kw),
        "streak": arm_speed.miss_streak(rows),
        "band": bd, "arms": arms, "unread": arm_speed.unreadable(),
    }


def _theta_days(m: dict, a0: dict, base: dict, rows: list[dict],
                kw: dict) -> dict | None:
    """**θ（前提が閉じる速さ）を、到達日の「日数」に換算する。**

    ## なぜ要るか（2026-08-30・最適化の回。**盤面でいちばん大きい数に、値札が無かった**）

    この出力は、日数の値札を**腕**と**配分**にだけ付けていました ——
    「次の1件をどの腕に立てるか」で数日、「台帳の配分の振り直し」で +10日。
    ところが同じプログラムが、その2つより**桁の違う**数を持っています。

    `trajectory()` は `rate = p · log(g) · θ` を積分して
    `T = min_t [ t + D(x(t)) ]` を解きます。**θ はその式の中で
    唯一の「速さ」**で、`t_work`（「腕を N日 動かして」）にそのまま反比例します。
    実測（2026-08-30 の点・`rate_scale` を振って解き直した）::

        θ×0.5   2027-02-25   t_work 85日   **+46日**
        θ×1.0   2027-01-10   t_work 47日     ——（印字している線）
        θ×2.0   2026-12-17   t_work 24日   **-24日**
        θ×5.0   2026-12-03   t_work 10日   **-38日**
        θ→∞     2026-11-24   t_work  1日   **-47日**   ← 収益化の門＋30日 の床

    **-47日 は、腕の話でも配分の話でもありません。**「前提が閉じる速さ」だけを
    動かして出た差で、**この機械が1周で選べるどの手より大きい**数です。
    それが 200行目 にも出ていませんでした —— 出ていたのは θ の**値**
    （「1日 0.77件 が閉じている」）だけで、**日数への換算がどこにもない。**
    値だけの数は、他の手と並べて比べられません。

    ## **上げ方は「前提を増やすこと」ではありません**（同じ回に測った）

    `config/hypotheses.yaml` を git の履歴で数え直すと、**在庫は余っています**::

        08/24  開いた前提 15件      08/28  26件
        08/26  19件                08/30  **32件**   ＝ 6日で +17件（2.8件/日）

    閉じるほうは **0.77件/日** のままです（`arm_speed.throughput()`）。
    **立てる側は、閉じる側の 3.6倍 の速さで回っています。**
    だから θ を縛っているのは件数ではなく、**立ててから判定できるまでの日数**
    （`src/judgeable.py`: 群の床 → **予約の順番待ち** → 落ち着き7日 →
    Analytics の遅れ3日）。予約は 359本・いちばん後ろは 30日超 で、
    **新しい実験の本は毎回その最後尾に着きます。**

    つまり `upload` を1本 足すたびに待ち行列が深くなり、**次の前提の判定日が
    後ろへ動く** ＝ θ が下がる。`data/runs.jsonl` の直近 500回 は
    `fix` 203件 ／ `upload` 45件 に対し **`verdict` 6件** で、
    そのあいだ到達予測は **+22日 遠のいて** います（12-19 → 01-10）。

    ## 覆る条件

    ・`t_work` が 0日 になったら（＝いま走らせるのが最短）、この行は
      「θ をいくつにしても同じ」に落ちます。**そのときは消してよい。**
    ・在庫（開いた前提）が閉じる速さを**下回った**ら、上の「増やすことではない」は
      逆になります。**数え直すのは `config/hypotheses.yaml` の open 件数と
      `arm_speed.throughput()` の2つだけ**（どちらも API 0単位）。

    検査は `tests/test_eta_theta_days.py`。
    """
    try:
        pool = [r for r in rows if r.get("lever") in arm_speed.ARMS]
        now = arm_speed.throughput(pool, kw.get("today"))
        if not now.get("per_day"):
            return None
        x2 = trajectory(m, a0, rate_scale=2.0, **kw)
        inf = trajectory(m, a0, rate_scale=THETA_INF_SCALE, **kw)
    except Exception:                                          # noqa: BLE001 — 回を止めない
        return None
    if base.get("days", NEVER) >= NEVER:
        return None

    def _delta(t: dict) -> float | None:
        d = t.get("days")
        return None if d is None or d >= NEVER else d - base["days"]

    return {"per_day": now["per_day"], "n": now["n"], "days": now["days"],
            "x2": x2, "inf": inf,
            "x2_delta": _delta(x2), "inf_delta": _delta(inf),
            "t_work": base.get("t_work"), "open": _open_hypotheses()}


def _open_hypotheses() -> int | None:
    """**いま開いている前提の件数**（`config/hypotheses.yaml`・API 0単位）。

    `arm_speed.planned()` の `total` と同じ数ですが、**あちらは `lever` の
    付いた分だけを `n` に数えます。** ここで要るのは「在庫が余っているか」で、
    付け札の有無は関係ないので、**開いている行そのもの**を数えます。
    読めなければ `None`（**回は止めない**）。
    """
    try:
        import yaml
        doc = yaml.safe_load((ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
        rows = doc if isinstance(doc, list) else next(iter(doc.values()))
        return sum(1 for r in rows if isinstance(r, dict) and not r.get("closed_on"))
    except Exception:                                          # noqa: BLE001
        return None


def frozen_days(m: dict, a0: dict, tr: dict, levers_: list[str], *,
                supply: dict | None = None, points: list[dict] | None = None,
                today: date | None = None) -> dict[str, float | None]:
    """**その腕を凍らせたら、軌跡は何日 遠のくか。**（2026-08-26・最適化の回）

    ## なぜ要るか（**この関数が無かったせいで、同じ日に正反対が印字されていました**）

    `lever_days()` の表は「**他の3本を今日の実測で凍らせたまま、1本だけを
    天井まで引く**」モデルです。そこで届かなかった腕に、`_report_levers` は
    こう書いていました（原文・2026-08-26 に消した）:

        **上の日付を動かせない腕: `sub_rate`／`density`**
        —— **ここに前提を置いても、到達日は動きません**

    ところが同じプログラムの `--alloc` は、同じ日・同じ点で

        **いちばん早いのは `sub_rate`**（そのままより **3日 早い**）
        立てるときは `hypotheses.yaml` に `lever:` をその腕で書くこと

    と出します。**「置いても動かない」と「次はここに置くのが最短」が、
    同じプログラムから同時に出ていました。**

    正しいのは `--alloc` の側です。頭に出る日付は**軌跡**（4本とも動かす）で、
    その内訳は実測で `sub_rate` ×13.41、**そのとき縛っているのは
    収益化の門（登録者 1,000人 の AND）**——`sub_rate` はその床に直に触ります。
    `CLAUDE.md` が「凍らせた企画についての恒真式であって予測ではない」と
    名指ししているのが、まさに `lever_days` の側です。

    ## 何を測るか

    **その腕の `rate` を 0 にして、軌跡を解き直すだけ**です。
    `_factors_at()` は `rate == 0` の腕を `live` から外すので、
    **空いた配分は残りの腕へ配り直されます** —— つまりこれは
    「**この腕に回していた回転を、全部よその腕へ回したら**」の線です。
    **それが「必要か」の正しい問いの形**です（「十分か」ではなく）。

        戻り値 > 0   凍らせると遠のく ＝ **その腕は必要**（十分でなくても）
        戻り値 = 0   回転をよそへ回しても同じ ＝ **この腕は要らない**
        戻り値 None  base が届かない回など、比べられない

    **`src/levers.py` はこの数を べた書き していました**（「+115日（2026-08-26）」）。
    べた書きは腐ります。**ここで毎回 測り直して渡すこと。**

    費用: 腕1本につき軌跡1本（**API 0単位・実測 2〜4秒**（2026-08-28 に `day_cap.cap()` を畳むまでは 15〜20秒））。
    呼ぶのは「天井まで引いても届かない」と出た腕だけなので、普通は1〜2本です。
    """
    out: dict[str, float | None] = {}
    base = (tr or {}).get("base") or {}
    base_days = base.get("days")
    arms = (tr or {}).get("arms") or {}
    if not levers_ or not arms or base_days is None or base_days >= NEVER:
        return {k: None for k in levers_}
    kw = dict(supply=supply, points=points, today=today or today_jst())
    for lv in levers_:
        if lv not in arms:
            out[lv] = None
            continue
        cold = {k: (dict(v) if k != lv else {**v, "rate": 0.0}) for k, v in arms.items()}
        try:
            t = trajectory(m, a0, arms=cold, **kw)
        except Exception:                                      # noqa: BLE001 — 回を止めない
            out[lv] = None
            continue
        d = t.get("days")
        if d is None:
            out[lv] = None
            continue
        # **凍らせたら届かなくなる腕**は、差が `NEVER`（10億）になります。
        #     そのまま出すと「+1,000,000,000日」と印字され、**欠陥に見えます**
        #     （読み手はまず数字を疑い、主張のほうを読みません）。
        #     地平（3年）で頭打ちにします —— **意味は変わりません**
        #     「3年 先まで見ても戻ってこない ＝ 必要」。
        out[lv] = min(float(d), float(TRAJECTORY_HORIZON_DAYS)) - base_days
    return out


def _arm_rotation() -> tuple[dict, dict]:
    """**腕べつの「予定表 θ」と、その重み。**読めなくても回を止めない。

    `deadline_check` が落ちても `--alloc` は出ます（重みが全部 1.0 になり、
    `missing` に理由が残る ＝ **黙って 1.0 にしない**）。
    """
    ready: dict = {}
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import deadline_check                                   # noqa: PLC0415

        ready = deadline_check.ready_by_claim()
    except Exception as exc:                                    # noqa: BLE001
        by_arm = arm_speed.forward_by_arm({})
        return by_arm, {"weights": {k: 1.0 for k in arm_speed.ARMS}, "raw": {},
                        "mean": None, "window": arm_speed.SPEED_WINDOW_DAYS,
                        "missing": f"`deadline_check` が読めません（{exc}）"}
    by_arm = arm_speed.forward_by_arm(ready)
    return by_arm, arm_speed.speed_weights(by_arm)


def _realloc_arms(arms: dict, share: dict[str, float],
                  speed: dict[str, float] | None = None) -> dict:
    """腕の束を、**別の配分**で解けるように組み直す。

    `rate = focus_rate × share` は `src/arm_speed.arm()` が置いている形です。
    ここは `share` だけを差し替えて `rate` を引き直します ——
    **`focus_rate`（その腕に全部振ったときの速さ）は配分に依りません。**

    ## `speed` ——**腕べつの「回転の重み」**（2026-08-27 に足した）

    `focus_rate = p · log(g) · θ` の **θ は `arm_speed.throughput()`**、
    つまり**全体の実測ひとつ**です。4本とも同じ値なので、
    `--alloc` の順位は（代用の腕どうしでは）**天井の遠さだけ**で決まります。

    `speed` は `arm_speed.speed_weights()` が返す、**平均1に正規化した倍率**。
    掛けると、台帳の予定表が言っている**腕どうしの回転の差**が順位に入ります。
    **水準は動きません**（平均が1なので）。渡さなければ、いままでどおり。

    実測 2026-08-27 —— これを掛ける前の `--alloc` は
    「いちばん早いのは `sub_rate`」と言い、同じ日の予定表では
    **`sub_rate` だけが今後14日 に1件も閉じられません**（`forward_by_arm()`）。
    """
    out = {}
    for k, a in arms.items():
        w = float(share.get(k, 0.0) or 0.0)
        sp = 1.0 if speed is None else float(speed.get(k, 1.0) or 1.0)
        out[k] = {**a, "share": w, "speed_weight": sp,
                  "rate": (a.get("focus_rate") or 0.0) * w * sp}
    return out


def supply_min_sustained_hours() -> float:
    """`src.supply.MIN_SUSTAINED_HOURS`。**読めない回でも印字を止めない。**"""
    try:
        from src import supply as supply_mod

        return float(supply_mod.MIN_SUSTAINED_HOURS)
    except Exception:                                          # noqa: BLE001
        return 24.0


def supply_state() -> dict | None:
    """**予測に渡す供給の実測**（読めなければ `None`。回は止めない）。"""
    try:
        from src import supply as supply_mod

        return supply_mod.state()
    except Exception:                                          # noqa: BLE001
        return None


#: 長尺の供給を実測する窓（日）。**丸1日そろった日だけを数えます** ——
#: 今日は途中なので混ぜると必ず下振れします（`drift.rounds_per_day` と同じ置き方）。
LONG_SUPPLY_WINDOW_DAYS = 7

#: 長尺の作り置き帳。`scripts/batch_build.py` が1回ごとに1行足します。
BATCH_RUNS = ROOT / "data" / "batch_runs.jsonl"


UPLOADED = ROOT / "data" / "uploaded.jsonl"

#: 控えから長尺と認めるための、いちばん短い尺（秒）。
#
# **テーマIDの `s-` では分けられません**（2026-08-26 に測って捨てた案）。
# `s-` は新しいショートにしか付いておらず、`invoice-2wari-tokurei` /
# `tsukin-teate-hikazei` のような**古いショートには付いていません。**
# 実測: `s-` で分けたら 08/19 のショート9本が長尺に化け、
# 供給が 1日 2.86本 → 4.29本 に跳ねました（**08/31 の前提の合否がひっくり返る幅**）。
#
# 尺で分けます。投稿前の検査が長尺に **4分** の床を掛けているので
# （`CLAUDE.md`「4分を下回ると投稿前の検査が止める」）、ここも 240秒。
# **`duration_s` が控えに無い行は数えません** —— 分からないものを
# 長尺の側へ倒すと、`fail_rate` も供給も上振れします。
LONG_MIN_SEC = 240.0


def _rescued_long(window: set[str],
                  seen: set[str],
                  path: Path | None = None) -> list[str]:
    """**台帳（`batch_runs.jsonl`）に載っていない長尺**を、控えから拾う。

    ## なぜ要るか（2026-08-26 09:xx に踏んだ）

    `batch_build` は **回のいちばん最後に1行だけ** `batch_runs.jsonl` を書きます。
    だから**途中で死んだ回は、作った本ごと帳面から消えます** ——
    この回は `timeout 900` で殺され、**verify まで通った2本が
    `final.mp4` として残っているのに、台帳には1行も載りませんでした**
    （`scripts/upload_only.py` で拾って予約は通っています）。

    `long_supply_per_day()` の docstring は、まさにこの形を
    **「覆る条件: 長尺を帳面の外で作るようになったら、ここは実測ではなくなります」**
    と予告していました。**その条件が来たので、こちらで塞ぎます。**

    塞がないと、**08/31 の前提「長尺は1日4本 作れる」が、
    作った本を数え落としたまま外れに倒れます。**

    数えるのは `data/uploaded.jsonl`（`upload_only.py` が予約のたびに書く控え）で、
    **`video_id` で重複を外します** —— `batch_build` も予約は
    `upload_only.py` を子プロセスで呼ぶので、**同じ本が両方に載ります。**

    `uploaded_at` は UTC なので、**JST の暦日に直してから窓に当てること**
    （直さないと、日本時間の朝9時より前に予約した本が前日に落ちます）。

    **長尺かどうかは尺で見ます**（`LONG_MIN_SEC`）。テーマIDの `s-` では
    分けられません —— 上の定数に、そう測った実測があります。
    """
    p = UPLOADED if path is None else Path(path)
    if not p.exists():
        return []
    out: list[str] = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:                                      # noqa: BLE001
            continue
        vid = str(r.get("video_id") or "")
        if not vid or vid in seen:
            continue
        dur = r.get("duration_s")
        if not isinstance(dur, (int, float)) or dur < LONG_MIN_SEC:
            continue
        raw = str(r.get("uploaded_at") or "")
        try:
            when = datetime.fromisoformat(raw)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when.astimezone(JST).date().isoformat() not in window:
            continue
        seen.add(vid)
        out.append(vid)
    return out


def _ledger_video_ids(path: Path | None = None) -> set[str]:
    """`batch_runs.jsonl` に**どこかの回で**載っている `video_id` を全部。

    窓の中だけを見ないこと —— 窓の外の回で作った本が控えでは窓の中に
    見えることがあり（作った日と予約した日が違う）、**二重に数えます。**
    """
    p = BATCH_RUNS if path is None else Path(path)
    got: set[str] = set()
    if not p.exists():
        return got
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:                                      # noqa: BLE001
            continue
        for x in (r.get("results") or []):
            vid = str(x.get("video_id") or "")
            if vid:
                got.add(vid)
    return got

def long_supply_per_day(path: Path | None = None,
                        today: date | None = None,
                        window_days: int = LONG_SUPPLY_WINDOW_DAYS) -> dict:
    """**長尺を1日に何本、実際に作れているか**（実測。計画値ではありません）。

    ## なぜ要るのか（2026-08-24。**同じ定数が、片方の扉からしか外されていなかった**）

    段2（門2a・長尺4,000時間）の合格点は、`_long_break_even()` が

        1本あたり再生 ＝ 要る視聴分 ÷ (**1日L本** × 門1までの日数 × 1再生の視聴分)

    で解いています。この **L** が `max(LONG_PER_DAY_SCENARIOS)` ＝ **4本/日** の
    決め打ちでした。**この機械は、長尺を1日4本 作れた日が一度もありません。**

        08/19  1本 試して **0本**      08/22  6本 試して **1本**（5本が生成失敗）
        08/20  8本 試して  7本         08/23  0本
        08/21  0本                     08/24  5本 試して  4本
        → 直近7日: **20本 試して 12本 ＝ 1日 1.71本**（長尺の生成失敗率 **40%**）

    合格点はLに反比例するので、4本/日 と置くと **46回/本**、実測の 1.71本/日 なら
    **107回/本**。**2.3倍 甘い数字**が出ていました。しかもこの 46回 は、
    `plan()` が「**この段取りを止めている、まだ測っていない入力は1つ**」と
    名指ししている当のものです ——「測れ」と言っている的が、2.3倍 ずれていました。

    **これは 2026-08-20 16:0x にオーナーが外した定数と同じ形です**（原文
    「25は物理的に不可ならそれを予測に使うのはどうなの？」）。あのとき直したのは
    `solve_gate1()`（段1）だけで、**段2 の側は決め打ちのまま残っていました。**

    ## 「本数はこちらで決められる」は、決めただけでは成り立ちません

    `_long_break_even()` の註は「本数はこちらで決められる／決められないのは
    1本あたり再生のほう」と書いています。**決められるのは正しい。**
    ただし**決めた本数を出していない**あいだ、その本数で割った合格点は
    予測ではなく願望です。だから **計画（4本/日）と実測の低いほう**を使い、
    2つの数を画面に並べます —— 差が出たら、それは
    「**長尺の供給を上げる**」という腕がそこにある、という意味です。

    ## 出どころと、外れる条件

    `data/batch_runs.jsonl` の `long: true` の回で、`results[].video_id` が
    **空でない**ものだけを数えます（`count` は失敗も含むので使わない）。
    **この帳面に載らない作り方をしたぶんは、下振れとして出ます**
    （`batch_build.py` を通さず `src.pipeline` を直接叩いた回など）。
    覆る条件: 長尺を帳面の外で作るようになったら、ここは実測ではなくなります。

    測れないとき（帳面が無い・窓に1行も無い）は `measured: False` を返し、
    呼ぶ側は計画値へ落ちます。**そのとき画面は「未検証の前提」と断ること。**
    """
    p = BATCH_RUNS if path is None else Path(path)
    t = today or today_jst()
    # **今日は数えません**（途中の日を混ぜると必ず下振れします）
    window = {(t - timedelta(days=i)).isoformat() for i in range(1, window_days + 1)}
    ok = attempts = 0
    seen: set[str] = set()
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except Exception:                                  # noqa: BLE001
                continue
            if not r.get("long"):
                continue
            if str(r.get("at", ""))[:10] not in window:
                continue
            for x in (r.get("results") or []):
                attempts += 1
                vid = str(x.get("video_id") or "")
                if vid:
                    ok += 1
                    seen.add(vid)
    # **帳面の外で作ったぶんを足す**（回が途中で死んで台帳の行が書かれなかった本）。
    # `_rescued_long` の docstring に、なぜ要るかと重複の外し方があります。
    rescued = _rescued_long(window, seen | _ledger_video_ids(p))
    ok += len(rescued)
    attempts += len(rescued)
    return {
        "rate": (ok / window_days) if attempts else 0.0,
        "built": ok,
        "attempts": attempts,
        "rescued": len(rescued),
        "window_days": window_days,
        "fail_rate": ((attempts - ok) / attempts) if attempts else None,
        # **1本も試していない窓は「0本/日」ではなく「測っていない」です。**
        #     0 を実測として通すと、段2 の合格点が無限大になり、
        #     「届きません」だけが残ります（何を固定してそうなったかが消える）。
        "measured": attempts > 0,
    }


def solve_gate1(a: dict, *, density: float, supply: dict | None,
                view_cap: float | None = None) -> dict:
    """**門1（登録者1,000人）が通る日を、「出せる本数」から解く。**

    2026-08-20 16:0x・オーナー指示（原文）——

    > 25は物理的に不可ならそれを予測に使うのはどうなの？

    **そのとおりでした。** ここは `a["days_subs_at"][25]` の1行で、
    `25` は `PLAN_PUBLISH_PER_DAY` ——「**予約を詰め直したらこうなる**」という
    置き方であって、**作れる本数ではありません**（定数の脇の註がそう書いてある）。
    実測は **在庫37本・未使用の節0件**。25本/日 は 1.5日で尽きます。
    **満たせない前提を入力にした日付は、予測ではありません。**

    いま解いているのは、次の2本の直線の**低いほう**です（`src.supply`）:

        予約の詰め方   density × t           在庫が足りているあいだの上限
        作る速さ       在庫 + 実測の速さ × t  在庫を食い終わった先の上限

    **「作る速さ」は実測です**（`supply.make_rate`。テーマ総数の増え方）。
    固定値ではなく、**この回が節を書けば上がる数**なので、`density` の腕は
    ここに効きます —— 効いたぶんだけ、次の回の予測が前に動きます。

    **ただし、読むのは `sustained_rate_per_day`（1日続けられる速さ）のほうです**
    （2026-08-20 20:0x）。`rate_per_day` は窓が3時間でも数を返すので、
    **3.3時間で +5本 ＝ 1日 36.5本**というバーストが `min(25, 36.5) = 25` を通り、
    **同じ日に外させた 25 が別の入口から戻っていました。**
    窓が 24時間 をまたいでいない回は、`src.supply.state()` が
    **出口の実測**（実際に公開になった本数／日）へ落とします。

    供給が読めないとき（`supply is None`）は前と同じ直線に落ちますが、
    **`measured: False` を返すので、画面は「未検証の前提」と断ります。**
    """
    need = a.get("videos_needed_gate1", float("inf"))
    # **出した本数ではなく、再生が付いた本数だけが門を押します**（2026-08-21 16:2x）。
    #     ここは長らく `plan_density = 25` をそのまま使い、**25本/日 出せば
    #     25本ぶんの登録者が来る**と読んでいました。実測は違います
    #     （`src/day_cap.py`）—— 08/20 は 25本 公開して **#11から先の15本が
    #     0〜3再生**。時刻ではなく**その日の通し番号**で割れます
    #     （08/16 の 14時 #4 は 1,361再生／08/20 の 14時 #12 は 0再生）。
    #     **上限は腕では動きません。** `density` を倍に振っても、上限を超えたぶんは
    #     0再生のままなので、ここは倍率の**後**に掛けます。
    #     **これが `density` の腕の天井そのもの**で、`tests/test_eta_day_cap.py`
    #     が「上限を無視した側へ戻ったら」落とします。
    view_cap = _view_cap_per_day() if view_cap is None else view_cap
    density = min(float(density), float(view_cap))
    # **使ってよいのは「1日続けられる速さ」だけ**（2026-08-20 20:0x に踏んだ）。
    #     `rate_per_day` をそのまま使うと、**3.3時間で +5本 ＝ 1日36.5本**という
    #     バーストが入り、`min(25, 36.5)` を通って **25 が別の入口から戻ります**
    #     —— 同じ日にオーナーが「物理的に不可なら予測に使うな」と外させた数です。
    #     `src.supply.state()` が `sustained_rate_per_day` を出すので、そちらを読む。
    #     （手で作った塊にその欄が無い回は、前と同じ `rate_per_day` に落ちます）
    if supply is None:
        rate_raw = None
    elif "sustained_rate_per_day" in supply:
        rate_raw = supply["sustained_rate_per_day"]
    else:
        rate_raw = supply.get("rate_per_day")

    if rate_raw is None:
        return {"days": a["days_subs_at"].get(int(density), NEVER),
                "measured": False, "need_videos": need,
                "density_sustained": density, "dry_days": None,
                "rate_per_day": None, "stock": None, "density_basis": None}

    from src import supply as supply_mod

    rate = float(rate_raw)
    stock = int((supply or {}).get("stock") or 0)
    days = supply_mod.days_for(need, stock=stock, rate_per_day=rate,
                               plan_density=density, never=NEVER)
    return {
        "days": days,
        "measured": True,
        "need_videos": need,
        # 収益の窓（30日）は在庫を食い終わった先にあるので、**そこでの密度は
        # 「作る速さ」で頭打ち**です。段4 はこちらで立てること。
        "density_sustained": min(float(density), rate),
        "density_basis": (supply or {}).get("sustained_basis"),
        # **材料が尽きる日だけは、速いほうの実測で見ます。**
        #     掃引の候補を食うのは「節を書く手」＝ `make_rate` のほうで、
        #     持続する速さ（＝出口の実測）はその下限でしかありません。
        #     下限で割ると尽きる日が**後ろにずれ、警告が甘くなります**
        #     （実測: 3.5本/日 なら 22日、36.5本/日 なら 2日）。
        "dry_days": supply_mod.material_dry_days(
            novel=supply.get("novel"),
            rate_per_day=max(rate, float((supply or {}).get("rate_per_day") or 0.0))),
        "rate_per_day": rate,
        "rate_burst": (supply or {}).get("rate_per_day"),
        "stock": stock,
        "thin": bool(supply.get("rate", {}).get("thin")),
    }


def plan(m: dict, a: dict, density: int = PLAN_PUBLISH_PER_DAY,
         view_cap: float | None = None,
         today: date | None = None, supply: dict | None = None,
         sensitivity: bool = False, points: list[dict] | None = None,
         mix: dict | None = None) -> dict:
    """**月20万に届くまでの段取りを、必ず1つ返す。**

    2026-08-20 06:2x・オーナー指示（原文）——

    > 「毎回の実行の最初にいつ20万の達成できるかを予測して、それを早めるには
    >   どうしたらいいかを考えてから進めて。**予測は達成できないで終わらせず、
    >   達成できるまでのプランを決めるようにして。**」

    **この道具は「どの帯でも届きません」で終わっていました。**
    `data/eta.jsonl` の29点とも同じ行で終わっていて、**日付が1つも出ていません。**
    それは診断であって予測ではありません。そして診断で終わるので、
    次の回は「では何をするか」を毎回いちから決め直していました
    （`retro.py` の縦読み: 直近5回とも「何を出すか決めるところ」が最大の時間食い）。

    **なぜ「届かない」が出ていたか。** 天井の表は
    `1本あたり再生 × 92本/日 × 30日` で、この 92 は **API の日枠**であって
    出せる本数ではありません（08/19 の実測は 28本で閉じた）。そして長尺の帯は
    **実測 2回/本**（n=5・登録者9人・配信ゼロの頃）で割っていました。
    **上振れの本数と、下振れの1本あたりを、同時に当てていた**わけです。

    ここは逆に組みます。**出せる密度（既定 25本/日）で、目標に要る
    「1本あたり再生」を解き、それをショートの実測で割る。**
    ショートの1本あたりは、この機械が持つ**唯一の当てになる実測**です。

    返すのは段の並びで、**最後の段には必ず日付が入ります。**
    未測定の入力があるときは、その1つを `blocking` に名指しして
    「これを測れば期日が決まる」と言う形にします（**空で返さない**）。
    """
    per_video = a["per_video_now"]
    sc = a.get("scale") or DEFAULT_SCALE
    # **密度の腕は、いまや「作る速さ」に効きます**（`solve_gate1`）。
    #     予約の詰め方（`density`）も一緒に動かさないと、倍率が片肺になります。
    density = density * sc["density"]
    # **倍率は `sustained_rate_per_day` にも当てること**（2026-08-21 02:3x に踏んだ）。
    #     `solve_gate1` は 2026-08-20 20:0x に **読む欄を `rate_per_day` から
    #     `sustained_rate_per_day` へ移しました**。ところがここは古い欄だけを
    #     掛けたままで、**段4 の天井（`per_video × density_sustained`）に
    #     `density` の倍率が1ミリも入っていませんでした** ——
    #     `density_sustained = min(密度, 続けられる速さ)` の第2項が素通しなので、
    #     腕を天井（×11.79）まで振っても `7.8本/日` のまま。
    #     **`density` は、掛け値なしに「引いても日付が動かない腕」でした。**
    #     軌跡が「全部振っても出ません」と言っていた理由の1つがこれです。
    #     **`tests/test_eta_density_scale.py` が、片方だけに戻ったら落とします。**
    if supply is not None and sc["density"] != 1.0:
        upd = {}
        for key in ("rate_per_day", "sustained_rate_per_day"):
            if supply.get(key) is not None:
                upd[key] = supply[key] * sc["density"]
        if upd:
            supply = dict(supply, **upd)
    g1 = solve_gate1(a, density=density, supply=supply, view_cap=view_cap)
    # **段4（月20万）は在庫を食い終わった先にあります。**
    #     そこでの密度は「予約の詰め方」ではなく「作る速さ」で頭打ちなので、
    #     月に何本出せるかは `density_sustained` で数えること。
    #     ここを 25 のままにすると、**1.5日ぶんの在庫で1か月ぶんを数えます。**
    density_month = g1["density_sustained"]
    monthly_slots = density_month * 30

    # --- **面（サムネのインプレッション）の実測を、段2と段4に当てる**（2026-08-20 23:2x）---
    #
    #     **段2 と段4 は、同じ1つの測り忘れに乗っていました。**
    #
    #     段4 は「純長尺・RPM ¥400」で立っていました。¥400 は
    #     **再生の 100% が長尺**のときの数です。ところが長尺のサムネが
    #     見せられている面は実測 **37.6回/日**しかなく（`src/reach_split.py`）、
    #     **CTR 100% でも長尺は再生の 13.0% までしか取れません。**
    #     そのときの実効 RPM の天井は **¥313**（`src/rpm_mix.py`）で、
    #     **¥400 はその上にあります。** ＝ 段4 の合格点 500,000回/月 は
    #     実測だと **639,000回/月**で、**1.28倍 甘い**数字でした。
    #
    #     段2 も同じです。合格点は「長尺を1日4本・1本あたり 221回」＝ 884回/日 ですが、
    #     いまの面は CTR 100% でも 37.6回/日 です（**23.5倍 足りません**）。
    #     **足りないのはインプレッションで、サムネと題（CTR）では動きません。**
    #
    #     **天井は固定ではありません。** 長尺を出せば面が増え、次の回の
    #     `python -m src.rpm_mix --record` でこの天井は上がります。
    #     **測れていないときは据え置きの帯へ落ちます**（`capped=False` で分かるようにする）。
    #     **この天井は、呼ぶ側から差せます**（`mix=` / 2026-08-22 に足した）。
    #     既定（`None`）は今までどおり `rpm_mix.last()` ——**本番の数字は1つも変わりません。**
    #     差せるようにしたのは、**構造を測る検査が実測の混ざり方に乗っていた**からです:
    #     `tests/test_eta_target_date.py` は「段4 は段3 の写しでないこと」など
    #     **形**を固定していますが、合格点（`need_month`）は実効 RPM の逆数なので、
    #     `--record` を1回撃つたびに動きます。08/20 の初測（帯 ¥400 → 実効 ¥253）で
    #     合格点が 500,000 → 789,922回/月 に上がり、**天井 714,000回/月 を追い越して**
    #     `days_to_target` が全部 `NEVER` に落ち、検査3件が赤になりました
    #     （**形は1行も壊れていないのに**です）。`view_cap` を差せるようにしたのと同じ理由で、
    #     **物差しを実データの偶然から外します**（`docs/trigger_main.md` §4「既知の当たりを
    #     実データの偶然に置かないこと」）。`mix={}` ＝「混ざり方を測っていない」＝ 帯そのまま。
    if mix is None:
        # **積んである点。** 無ければ `{}`（＝「混ざり方を測っていない」）。
        mix = rpm_mix.last() or {}
        # **面の「いま続いている量」だけは、その場で測り直します**（**API 0単位**）。
        #     `rpm_mix --record` は Analytics の日枠を食うので、撃てない窓が
        #     1日16時間ほどあります。そこで古い点に合わせて段2 を読むと、
        #     **窓が閉じているあいだじゅう「全期間の平均」で判断する**ことに
        #     なります（存在しなかった日を分母に数えた数です）。
        #     `data/reach.jsonl` は `scripts/reach.py` が別に積んでいるので、
        #     **読むだけなら1単位も要りません。**
        #     **点そのものが無い回では測り直しません** —— 「測っていない」を
        #     「面だけ測れている」に変えると、段2 の注記が推測で出ます
        #     （`tests/test_eta_surface_cap.py`「面が測れていなければ出ない」）。
        #
        # **`imp_day_recent` が既に在っても、測り直します**（2026-08-27 に直した）。
        #     長らくここは `not mix.get("imp_day_recent")` で畳んでいました ——
        #     「もう続いている量を持っているなら、測り直す必要はない」。
        #     **持っている数が別の統計でした。**
        #
        #     積んである点（`rpm_mix --record` が書く）の `imp_day_recent` は
        #     **直近7日の平均**です。段2 が読みたいのは
        #     `reach_split.summary()` の `per_day_sustained`（**中央値**。
        #     窓の1日が半分以上を占めたら平均から落とす、と同 file が書いています）。
        #     実測 2026-08-27 の同じ帳面: 平均 **318.9回/日**／中央値 **17.0回/日**。
        #     **18.8倍** ちがい、合格点 178回/日 をまたぎます ——
        #     平均で読むと「**面は足りています（1.8倍）**」、
        #     中央値で読むと「**10.5倍 足りません。足りないのはインプレッションで、
        #     サムネと題（CTR）では動きません**」。**次の回に引く腕が正反対になります。**
        #
        #     そして畳んだ回は `_with_recent_surface()` が付ける**連れも全部**
        #     落としていました —— `imp_ctr_long`（実測 CTR）・
        #     `imp_day_recent_basis`（burst だと言う一行）・`imp_day_planned`・
        #     `imp_day_dry_span` / `imp_day_dry_fill`。
        #     とくに CTR が無いせいで、`_gate2_surface_note()` の
        #     **「『足りています』を裸で出さないこと」**の枝（実測 CTR 2.20% ＝
        #     **25.4倍 足りません**）が **一度も印字されていませんでした。**
        #     **正しい注記が、入力が無いというだけで黙っていた**形です。
        #
        #     **覆る条件**: `rpm_mix --record` が `per_day_sustained` と
        #     `imp_ctr_long` まで点に書くようになったら、ここは畳んでよい
        #     （そのときは点のほうが `data/reach.jsonl` より新しいことがある）。
        #     **それまでは、帳面が読める回は必ず測り直すこと**
        #     —— `_with_recent_surface()` は読めなければ `mix` をそのまま返します。
        if mix:
            mix = _with_recent_surface(mix)
    else:
        mix = dict(mix)
    rpm_cap = float(mix.get("rpm_max") or 0.0) or None
    long_views_day_cap = float(mix.get("imp_day") or 0.0) or None
    # **段2 の分母は天井ではありません**（2026-08-25）。`_gate2_surface_basis` を読むこと。
    long_views_day_now, gate2_basis, gate2_span = _gate2_surface_basis(mix)

    # --- どの形で月20万を取りに行くか（**下振れの RPM で比べる**）---
    forms: dict[str, dict] = {}
    for form, band in PLAN_BAND_BY_FORM.items():
        # **帯（¥400）と、実際に出せる実効 RPM（混ざり方）は別物です。**
        #     腕 `rpm` を何倍にしても、面が増えるまで実効 RPM は天井を越えません。
        band_rpm = RPM_SCENARIOS[band] * sc["rpm"]
        capped = bool(rpm_cap and band_rpm > rpm_cap)
        rpm_plan = min(band_rpm, rpm_cap) if rpm_cap else band_rpm
        need_month = (TARGET_YEN * 1000 / rpm_plan) if rpm_plan > 0 else float("inf")
        need_per_video = need_month / monthly_slots if monthly_slots else float("inf")
        forms[form] = {
            "band": band,
            "rpm": rpm_plan,
            "rpm_band": float(RPM_SCENARIOS[band] * sc["rpm"]),
            "capped": capped,
            "views_needed_month": need_month,
            "per_video_needed": need_per_video,
            # **物差しはショートの実測**。長尺の実測（2回）で割ると、
            # 「登録者9人の頃に出した5本」が計画の分母になります（M20）。
            "ratio_vs_shorts": (need_per_video / per_video) if per_video else float("inf"),
        }
    spine = min(forms, key=lambda f: forms[f]["ratio_vs_shorts"])
    sp = forms[spine]

    # --- 段1: 門1（登録者1,000人）。**実測のあるショートで開ける** ---
    #     **供給（作る速さ）で解きます。** 定数 25 は上限としてしか使いません。
    d_gate1 = g1["days"]

    # --- 段2: 門2a（長尺4,000時間）。段1と**並行**。合格点は1本あたり再生 ---
    #     いちばん甘い形（尺が長く維持率が高い）を取る。**本数は決められる／
    #     決められないのは1本あたり再生のほう**なので、そちらを解いて出す。
    rows = _long_break_even(a, days=g1["days"])
    # **Lは「計画」ではなく「実測との低いほう」**（2026-08-24。`long_supply_per_day`）。
    #     ここは `max(LONG_PER_DAY_SCENARIOS)` ＝ 4本/日 の決め打ちでした。
    #     合格点はLに反比例するので、出していない本数で割ると**そのぶん甘く**出ます
    #     （実測 1.71本/日 のとき 46回/本 → **107回/本**）。
    #     そしてこの数は、下の `blocking` が「**この段取りを止めている、
    #     まだ測っていない入力**」と名指ししている当のものです。
    long_sup = long_supply_per_day(today=today or today_jst())
    plan_long = max(LONG_PER_DAY_SCENARIOS)
    per_day_long = (min(float(plan_long), long_sup["rate"])
                    if long_sup["measured"] else float(plan_long))
    # **0本/日 を通さない。** 窓に1本も作れていない回に合格点を無限大にすると、
    #     画面には「届きません」だけが残り、**何を固定してそうなったかが消えます**
    #     （`CLAUDE.md`「裸の『届きません』を出さないこと」）。
    #     いちばん低い筋書き（1本/日）を床にして、**足りない事実は文言で言います。**
    long_dry = per_day_long < min(LONG_PER_DAY_SCENARIOS)
    per_day_long = max(per_day_long, float(min(LONG_PER_DAY_SCENARIOS)))
    best = min(rows, key=lambda r: -r["min_per_view"])
    gate2_bar = _gate2_bar(a, best, per_day_long, g1["days"])

    # --- 段3: 収益化の審査 ---
    d_monetized = d_gate1 + MONETIZE_REVIEW_DAYS if d_gate1 < NEVER else NEVER

    # --- 段4: 月20万に届く日を、**解いて出す**（2026-08-20 08:0x と 08:3x の合流）---
    #
    # **2つの回が、同じ1行（`d_target = d_monetized`）を別々に見つけました。**
    # 片方は「20万は水準なので、**収益化してから30日ぶん積んだ合計**でしか名乗れない」
    # （`REVENUE_WINDOW_DAYS`・`_stage4`）。もう片方は「**合格点が立つ日そのものを、
    # 実測の伸び率で解いていない**」（`solve_revenue_day`）。**どちらも要ります。**
    #
    #   ① 直近30日の再生が、月に要る回数に達する日          ← 伸び率で解く
    #   ② その30日が**まるごと収益化の後**にあること        ← 収益化前の再生は1円も生まない
    #   ③ 合格点の倍率が**推測**なら、確かめた後であること  ← 別の形の実測を当てている間
    #
    # 到達日は、この3つの**いちばん遅いほう**です。
    # **どれが縛っているかが、次に引く腕を決めます。**
    # 天井も**持続する密度**で。予約の詰め方で掛けると、在庫の無い先まで
    # 「1日25本」が続く天井を印字します。
    ceiling_day = per_video * density_month
    ceiling_day_long = (a.get("long_per_video") or 0) * density_month
    need_month = sp["views_needed_month"]
    growth = a.get("growth") or growth_per_day(m)
    g = growth.get("g")
    views_day_now = a.get("views_day_now", a["views_per_day"])

    d_revenue = solve_revenue_day(views_day_now, g, ceiling_day, need_month)
    # **長尺の実測（2回/本）をそのまま当てた側**も出します。片方だけ出すと、
    # 「まだ測っていない」が「届く」にも「届かない」にも化けます（M20）。
    d_revenue_long = solve_revenue_day(views_day_now, g, ceiling_day_long, need_month)

    # --- **物差しが「別の形の実測」になっていないか** ---
    #     段4 が立てているのは長尺で、割っているのはショートの実測です。
    #     長尺の実測が無い／標本が薄いあいだ、合格点は**推測**でしかありません。
    #     （下の `blocking` と同じ条件。2か所で別々に書くと必ずずれるので、ここで1回）
    lpv = a.get("long_per_video")
    n_long = a.get("long_videos_28d", 0)
    proxy = spine.startswith("長尺") and (lpv is None or n_long < LONG_SAMPLE_MIN)

    s4 = _stage4(m, a, sp, density_month, per_video, d_monetized,
                 today or today_jst(), proxy=proxy, d_revenue=d_revenue)
    d_target = s4["when"]

    # **どれが到達日を縛っているか。** ここが、この回に引く腕を決めます。
    if d_revenue >= NEVER:
        binding, hint = "再生数が天井に当たっている", "rpm"
    elif d_revenue >= s4["floor"]:
        binding, hint = "再生数（段4の (a)）", "per_video"
    elif s4["conditional"] and s4["verify_floor"] >= s4["gate_floor"]:
        binding, hint = "合格点がまだ推測（確かめ待ち）", "rpm"
    else:
        binding, hint = "収益化の門＋その後の30日", "density"

    # --- 「何を何倍にすれば何日後か」（**届かないで終わらせない**）---
    #     ②の30日は前借りできないので、**期日から30日を引いた所まで**に
    #     再生の水準が立っていなければ間に合いません。そこを逆算します。
    base = today or today_jst()
    horizons = []
    for h in GROWTH_HORIZONS:
        rg = required_growth(views_day_now, ceiling_day, need_month,
                             h - REVENUE_WINDOW_DAYS)
        horizons.append({
            "days": h,
            "date": base + timedelta(days=h),
            "growth": rg,
            "double_days": double_days(rg) if rg else None,
            "reachable": rg is not None,
        })
    # 天井そのものが足りないときは、**伸び率ではなく形の話**になる
    ceiling_month = ceiling_day * 30
    ceiling_short = need_month / ceiling_month if ceiling_month > 0 else float("inf")

    # --- **足りない天井を、面（長尺のインプレッション）で埋めるなら何回/日 要るか** ---
    #     「届きません」で畳まないための逆算（オーナー指示 2026-08-20 06:2x）。
    #     **この機械が RPM を上げる道は1つだけ**です —— 長尺が再生に占める割合を上げること。
    #     その割合の上限は面が決めます（`rpm_mix.surface_ceiling`: CTR 100% でも
    #     `imp_day / (imp_day + ショートの再生/日)` まで）。だから逆に解けます:
    #
    #         要る実効RPM = 20万 × 1000 ÷ いまの天井（月の再生）
    #         要る長尺の割合 = (要る実効RPM − ショートの帯) ÷ (長尺の帯 − ショートの帯)
    #         要る面 = 割合 ÷ (1 − 割合) × ショートの再生/日
    #
    #     **帯は `高` を使います**（¥2,000 / ¥60）。上の天井 ¥313 が `高` で出ているので、
    #     ここだけ `低` にすると、同じ画面の中で2つの物差しが混ざります。
    #     割合が 1 を超えたら、**面だけでは埋まりません**（＝1本あたり再生か密度も要る）。
    surface_needed: dict = {}
    if ceiling_short > 1 and ceiling_month > 0 and long_views_day_cap:
        r_long = float(RPM_SCENARIOS["長尺 お金 高"])
        r_short = float(RPM_SCENARIOS["ショート 高"])
        rpm_needed = TARGET_YEN * 1000 / ceiling_month
        share_needed = (rpm_needed - r_short) / (r_long - r_short)
        views_form = (mix.get("views_by_form") or {})
        days_mix = max(1.0, float((mix.get("window") or {}).get("days") or 1))
        short_day = float(views_form.get("ショート") or 0.0) / days_mix
        surface_needed = {
            "rpm_needed": rpm_needed, "rpm_long": r_long, "rpm_short": r_short,
            "share_needed": share_needed, "imp_day_now": long_views_day_cap,
        }
        if share_needed >= 1.0 or short_day <= 0:
            surface_needed.update({"impossible": True, "rpm_at_full": r_long,
                                   "still_short": rpm_needed / r_long})
        else:
            imp_req = share_needed / (1 - share_needed) * short_day
            surface_needed.update({"impossible": False, "imp_day_needed": imp_req,
                                   "imp_factor": imp_req / long_views_day_cap})

    # **結論はこの1つの比較に乗っています。**
    # 「②と③で決まる床までに、再生数のほうが間に合うか」——
    # 間に合うなら到達日は門と窓で決まり（引く腕は density / sub_rate）、
    # 間に合わないなら再生数で決まります（引く腕は per_video / rpm）。
    # **どちらかを言うだけでは、次の回が「余裕があるのか、ぎりぎりなのか」を測れません。**
    g_needed = (required_growth(views_day_now, ceiling_day, need_month,
                                int(s4["floor"]))
                if s4["floor"] < NEVER else None)

    stages = [
        {
            "no": 1, "lever": "density", "when": d_gate1,
            "title": "門1（登録者1,000人）を、実測のあるショートで開ける",
            "bar": (f"要る本数 **{g1['need_videos']:,.0f}本**"
                    f"（1本あたり {per_video:,.0f}回 × 登録率 {a['sub_rate'] * 100:.4f}%）を、"
                    + (f"在庫 {g1['stock']}本 ＋ **作る速さ 1日 {g1['rate_per_day']:.1f}本の実測**"
                       f"（詰め方の上限 {density:.0f}本/日）で埋める"
                       if g1["measured"] else
                       f"**1日{density:.0f}本という未検証の前提**で埋める"
                       "（`src/supply.py` が読めませんでした）")),
            "measured": g1["measured"],
        },
        {
            "no": 2, "lever": "rpm", "when": d_gate1,
            "title": f"門2a（長尺4,000時間）を、段1と並行で開ける",
            # **面（インプレッション）と突き合わせる。**
            #     合格点は「1日 per_day_long 本 × 1本あたり gate2_bar 回」＝ 再生/日 です。
            #     いまの面は CTR 100% でも `long_views_day_cap` 回/日 しか出せません。
            # **足りる側へ回った日に、文言も回ること**（2026-08-24）。
            #     ここは「必ず足りない」前提で書かれていて、面が合格点を越えた回に
            #     **「0.1倍 足りません」**と印字しました（倍率が1を割った ＝ 足りている）。
            #     面の天井を平均から最大へ直した回に、そのまま出ています。
            # **読むのは「いま続いている量」**（最大の1日ではありません。2026-08-25）。
            "note": (_gate2_surface_note(long_views_day_now,
                                         gate2_bar * per_day_long,
                                         gate2_basis, gate2_span)
                     if long_views_day_now else None),
            # **Lの出どころを、合格点と同じ行に書くこと**（`CLAUDE.md`「何を固定
            #     したせいでそう出たのかを同じ行に並べる」）。計画の 4本/日 と
            #     実測を並べておかないと、次の回は「46回」を天から降ってきた数として読みます。
            "bar": (f"長尺を1日{per_day_long:.2f}本・{best['label']} で出し、"
                    f"**1本あたり {gate2_bar:,.0f}回**"
                    + (f"（**Lは実測**: 直近{long_sup['window_days']}日に "
                       f"{long_sup['attempts']}本 試して **{long_sup['built']}本** ＝ "
                       f"1日 {long_sup['rate']:.2f}本"
                       + (f"・生成失敗 {long_sup['fail_rate'] * 100:.0f}%"
                          if long_sup["fail_rate"] else "")
                       + f"。計画は {plan_long}本/日 で、そこでは "
                       f"{_gate2_bar(a, best, float(plan_long), g1['days']):,.0f}回 に見えます）"
                       + ("　[!] **実測が筋書きの下限を割っています**（床の1本/日 で置いた）"
                          if long_dry else "")
                       if long_sup["measured"] else
                       f"（**Lは未検証の前提 {plan_long}本/日**。"
                       "`data/batch_runs.jsonl` に長尺の回がありませんでした）")
                    # **0除算で回を止めないこと。** 1本あたり再生が 0 で返る日
                    # （Analytics が空・窓に公開が1本も無い）に、予測そのものが落ちます。
                    # `plan()` は 2026-08-20 08:0x から `report()` より**先**に走るので、
                    # ここで落ちると**実測の表ごと失います**（前は段取りの節だけでした）。
                    + (f"（ショート実測の {gate2_bar / per_video:.2f}倍）"
                       if per_video else "（ショートの実測がまだありません）")),
            "measured": False,
            # **次の回が、この合格点を作った入力を機械から読めるようにする。**
            "long_per_day": per_day_long,
            "long_per_day_plan": float(plan_long),
            "long_supply": long_sup,
        },
        {
            "no": 3, "lever": "none", "when": d_monetized,
            "title": f"収益化の審査（公表「通常1か月以内」＝ {MONETIZE_REVIEW_DAYS}日と置く）",
            "bar": "門1・門2a の両方を満たしたら申請。**待つだけの段**",
            "measured": False,
        },
        {
            "no": 4, "lever": ("rpm" if ceiling_short > 1 else "per_video"),
            "when": d_target,
            "title": (f"月20万に到達（{sp['band']}・RPM ¥{sp['rpm']:,.0f}"
                      + ("／**帯の ¥{:,.0f} は、実測の混ざり方の天井で頭打ち**".format(sp["rpm_band"])
                         if sp.get("capped") else "")
                      + "）"),
            "bar": (f"直近30日で **{sp['views_needed_month']:,.0f}回**"
                    f"（＝1日{density}本 × 1本あたり {sp['per_video_needed']:,.0f}回）を、"
                    f"**収益化の後に {REVENUE_WINDOW_DAYS}日ぶん**積む。"
                    f"いま 1日 {views_day_now:,.0f}回、伸び率 "
                    + (f"**{g * 100:+.2f}%／日**（{double_days(g):,.0f}日で2倍）"
                       if g and g > 0 else "**0以下 ＝ 伸びていません**")
                    + f"、天井 1日 {ceiling_day:,.0f}回"),
            "measured": s4["met"],
            # **段取りの一覧だけを読む人にも、条件つきだと分かるようにする。**
            #     ここが無いと「2027-01-21 に届く」とだけ読めます。
            "note": ("**この日付は条件つきの「最早」です**（合格点がまだ実測で"
                     "立っていない）。下の「その日付は、どこから出ているか」を読むこと"
                     if s4["conditional"] else None),
        },
    ]

    # --- 段取り全体を止めている「まだ測っていない入力」を1つ名指しする ---
    #     **計画を空にしない**ための欄です。ここが埋まっていれば、
    #     次の回は「何をするか」を決め直さずに、この1手から始められます。
    if proxy:
        # **「薄い」と「無い」を書き分けること**（2026-08-25 に直した。
        # 理由は `LONG_SAMPLE_MIN` の註）。ここは長らく、値が出ている回にも
        # 「まだ一度も測り直していない」と**固定文字列**で印字していました。
        measured = lpv is not None
        fc = (long_sample_forecast(today or today_jst(), n_long)
              if measured else None)
        blocking = {
            "what": "長尺の1本あたり再生",
            # **測れているか／薄いだけか。** 読み手も検査も、ここで分岐します
            "measured": measured,
            "sample": fc,
            "now": (f"{lpv:,.1f}回（n={n_long}・**直近28日の Analytics**。"
                    f"**毎回測り直しています**。標本が {LONG_SAMPLE_MIN}本 に"
                    "満たないので、合格点は推測のまま）"
                    if measured
                    else "**測れていません**（直近28日に長尺の再生が0本）"),
            "need": f"{sp['per_video_needed']:,.0f}回（段4）／{gate2_bar:,.0f}回（段2）",
            "how": (f"長尺の本数を増やして標本を n≥{LONG_SAMPLE_MIN} にする"
                    f"（**あと {fc['need']}本**）"
                    if measured
                    else "長尺を出して、公開から48時間おいた本で測り直す"),
            "why": ("段2・段4 の期日がこの1つに乗っている。"
                    f"ショートは{per_video:,.0f}回出ているので、要るのはその"
                    f"{sp['ratio_vs_shorts']:.2f}倍。"
                    + (f"**値は出ています（1本 {lpv:,.1f}回）。薄いのは標本のほうです**"
                       if measured else "**一度も測れていない**")),
            "targets": measure_targets(today or today_jst()),
        }
    else:
        blocking = {
            "what": "段1の登録率",
            "now": f"{a['sub_rate'] * 100:.4f}%",
            "need": "据え置きでよい（段1は実測だけで立っている）",
            "how": "1日25本の公開を保つ",
            "why": "段取りの入力に、未測定のものが無い",
            "targets": None,
        }

    out = {
        "density": density, "density_month": density_month,
        "gate1": g1, "supply": supply,
        "spine": spine, "spine_band": sp["band"],
        # **面の実測**（段2 と段4 が、これを見ないまま立っていました）
        "surface": {"rpm_cap": rpm_cap, "long_views_day_cap": long_views_day_cap,
                    "capped": sp.get("capped", False),
                    "rpm_band": sp.get("rpm_band"), "rpm_plan": sp["rpm"]},
        "forms": forms, "stages": stages, "blocking": blocking,
        "days_to_target": d_target, "target": s4,
        "target_date": (base + timedelta(days=math.ceil(d_target))) if d_target < NEVER else None,
        "days_monetized": d_monetized,
        "days_revenue": d_revenue,
        "days_revenue_long": d_revenue_long,
        "binding": binding,
        "lever_hint": hint,
        "growth": growth,
        "ceiling_day": ceiling_day,
        "ceiling_day_long": ceiling_day_long,
        "ceiling_short": ceiling_short,
        "surface_needed": surface_needed,
        "growth_needed_by_gate": g_needed,
        "need_month": need_month,
        "views_day_now": views_day_now,
        "horizons": horizons,
    }
    # --- **腕べつに、到達日が何日動くか**（オーナー指示 2026-08-20 16:0x）---
    #     `sensitivity=False` で呼ばれた回は測りません（`lever_days` が
    #     `plan()` を呼び直すので、そのままだと無限に潜ります）。
    if sensitivity:
        out["lever_days"] = lever_days(m, a, pl0=out, today=today, supply=supply,
                                       points=points, mix=mix)
        # **選ぶのは「その腕の天井まで引いたら」のほう**（2026-08-25）。
        #     ここは `r["gain"]`（＝どの腕も一律 ×2）で選んでいましたが、
        #     合格点が ×2 より上にある回は**4本とも 0** になり、この分岐は
        #     一度も走りませんでした（8/20 に書いてから 8/25 まで死んだまま）。
        #     天井は腕ごとに ×1.00〜×2,923 と3桁ちがうので、
        #     **同じ倍率で並べた差は「引けるか」を含んでいません。**
        #
        #     **天井が1つも測れていない回は、同じ倍率の差へ落ちます。**
        #     落とさないと、`gain_at_cap` が全部 0 になった環境で
        #     **上書きごと消え、`lever_hint` が床の名前（＝診断）に戻ります** ——
        #     それは 8/20 に直したはずの状態そのものです。**黙って戻さないこと。**
        _rows = out["lever_days"]
        _key = "gain_at_cap" if any(r["gain_at_cap"] > 0 for r in _rows) else "gain"
        best = max(_rows, key=lambda r: r[_key], default=None)
        # **縛っている床の名前より、実測の差のほうを信じる。**
        #     「門が縛っている＝density」は正しい診断ですが、**どの腕がいちばん
        #     日付を動かすか**は別の問いで、そこは掛け算の形で決まります。
        if best and best[_key] > 0:
            out["lever_chosen_by"] = _key
            out["lever_measured"] = best["lever"]
            out["lever_hint_binding"] = out["lever_hint"]
            out["lever_hint"] = best["lever"]
    # --- **名指しした腕の測定が、もう予約済みの本で答えが返る回がある** ---
    #     （2026-08-26 に踏んだ。**この道具が自分と食い違っていました**）
    #
    #     この回の出力は、頭の3行で「この回に引く腕は `per_video`」と言い、
    #     200行下で「**この測定に ship を使わないこと。別の腕を引くこと**」と
    #     言っていました。**手順（`docs/trigger_main.md` の「普通の回の読む順」）は
    #     3行だけ読めと言っている**ので、下の断りは普通の回には届きません。
    #
    #     そして届いた回も罰されます —— `run_marker.py --ship --lever` は
    #     `lever_followed = (lever == lever_hint)` を残すので、
    #     **道具の指示どおり別の腕を引くと「名指しを外した」として記録されます。**
    #     受け取り帳 `68e90017` が 09/01 に数え直そうとしている
    #     `lever_followed`（いま 12/98＝12%）は、**その分だけ嘘をついています。**
    #
    #     だから「この名指しは、この回は引かなくてよい」を**同じ3行に**出し、
    #     `data/eta.jsonl` にも積んで、数える側が外せるようにします。
    #     **`date` のまま持たないこと**（2026-08-26。入れた直後に自分で踏みました）。
    #     この欄は `data/eta.jsonl` に積まれ、`--reflect` が JSON へ書き戻します ——
    #     `TypeError: Object of type date is not JSON serializable` で
    #     **反映だけが落ち、ship は残る**という形で出ます（回は止まりません）。
    _fc = ((out.get("blocking") or {}).get("sample")) or {}
    _rc = _fc.get("reaches")
    if _rc and out.get("lever_hint") == "per_video":
        out["lever_hint_covered"] = (_rc.isoformat() if hasattr(_rc, "isoformat")
                                     else str(_rc))
    return out


def _share_str(share: dict[str, float]) -> str:
    """配分を「腕 N%」の並びで。**0% の腕も出すこと** —— 0 が本体だからです。"""
    return " ／ ".join(f"{k} {(share.get(k) or 0.0):.0%}"
                       for k in arm_speed.ARMS if k in share)


def _planned_lines(bar: str, tr: dict | None, base: dict | None) -> list[str]:
    """**上の日付が前提にしている配分を、台帳が用意しているか。**（2026-08-26）

    `base` の速さは `rate = focus_rate × share` で、`share` は
    **閉じた前提の腕べつの割合 ＝ 過去にどう振ってきたか**です。
    **未来の配分を決めているのは、いま開いている前提のほう**で、
    それは `config/hypotheses.yaml` に既に書いてあります。

    実測 2026-08-26 —— 2つは食い違っていました::

        実績（閉じた21件）  per_video 60% ／ density 25% ／ sub_rate 10% ／ rpm  5%
        台帳（開いた 5件）  per_video  0% ／ density 20% ／ sub_rate 20% ／ rpm 60%
        **腕の名前が無い前提 10件**（開いた15件の 67%）

    **どちらの数もこの機械が持っていて、照らし合わせている所がありませんでした。**
    `docs/JOURNAL.md` が「いちばん当たる」と書いている形そのものです ——
    **同じことを2か所が別々に言っていて、片方しか読まれていない。**

    **これは「台帳が正しい」ではありません。** 台帳は書き換えられます。
    2つの差が、**次の前提をどの腕に立てるかで動く日数**そのものなので、
    そこを見せて、選べる形にするのがここの役目です。
    """
    pln = (tr or {}).get("planned")
    if pln is None:
        return []
    meta = pln.get("planned") or {}
    lines: list[str] = []
    have = base is not None and base.get("days", NEVER) < NEVER
    diff = ((pln["days"] - base["days"]) if have and pln["days"] < NEVER else None)
    past = {k: (v.get("share") or 0.0) for k, v in ((tr or {}).get("arms") or {}).items()}
    head = (f"{bar} 上の日付は**過去の配分**で解いています"
            f"（{_share_str(past)}）。"
            f" **台帳が実際に用意している配分**は"
            f"（{_share_str(meta.get('share') or {})}・開いた{meta.get('n', 0)}件）")
    if pln["days"] < NEVER and pln["date"] is not None:
        head += f" → **{pln['date'].isoformat()}**"
        if diff is not None:
            head += (f"（**{diff:+,.0f}日**）" if abs(diff) >= 1
                     else "（同じ）")
    else:
        head += " → **出ません**"
    lines.append(head)
    if diff is not None and abs(diff) >= 1:
        lines.append(f"{bar} **その差 {abs(diff):,.0f}日 は、"
                     "「次の前提をどの腕に立てるか」で動きます** ——"
                     " 台帳を書き換えれば配分は変わります"
                     "（`config/hypotheses.yaml` の `lever`）。"
                     " **どの腕が早いかは `python scripts/eta.py --alloc`**"
                     "（API 0単位・**実測 24秒**（2026-08-28 に `day_cap.cap()` を畳むまでは 4分）。**毎回 撃ってよい** —— 「毎回は撃たない」は 2026-08-28 に取り消した）")
        # **`lever_hint` とは別の問いです**（2026-08-26 に足した理由）。
        #     `lever_hint` は「**いま どの床が遅いか**」＝ 診断で、
        #     `--alloc` は「**次の前提をどの腕に立てるか**」＝ 配分の選択。
        #     頭の3行しか読まない側は、前者を後者だと読みます ——
        #     実測 2026-08-26: 名指しは `per_video` だが、per_video に1件 足しても
        #     日付は **0日** しか動かず、`sub_rate` に足すと **6日 早い**。
        lines.append(f"{bar} **`{'lever_hint'}` は「いまどの床が遅いか」で、"
                     "「次の前提をどの腕に立てるか」とは別の問いです** ——"
                     " 到達日を動かすのは後者のほう"
                     "（`eta.py` 自身が「腕が動くのは前提を1件閉じたときだけ」と"
                     "この下に印字しています）")
    un = meta.get("unassigned") or 0
    if un:
        lines.append(f"{bar} [!] **腕の名前が無い開いた前提が {un}件**"
                     f"（開いた{meta.get('total', 0)}件のうち）。"
                     " **閉じるときに `lever` が無い行は、`arm_speed.closed()` が"
                     "丸ごと飛ばします** —— 飛ばされた分は θ（回転の速さ）にも"
                     "入らないので、**腕の速さが全部いっしょに下がります。**"
                     " 上の配分は、その分だけ**当てにならない側**です")
    return lines


REFLECT_KIND = "reflect"


def _points(*, reflect: bool = False, offline: bool = False) -> list[dict]:
    """`data/eta.jsonl` を積んだ順に読む。**壊れた行は黙って飛ばす**（回を止めない）。

    **既定では「反映の行」を外します**（2026-08-20・オーナー指示「毎回その予測に
    反映して」の配線）。周の終わりに `--reflect` が積む行は、
    **同じ実測をもう一度解き直したもの**です。予測の点として数えると:

      * `growth_per_day()` の回帰に、**中身が同じで時刻だけ違う点**が入る
      * `_drift()` の「前の回」が、**同じ回の自分自身**になる

    どちらも「チャンネルが動いた」と読める形の嘘になります。**だから外す。**
    読みたいときだけ `reflect=True`（`_reflect_rows()` がそれを使います）。

    **`offline: true` の点も、同じ理由で外します**（2026-08-20 23:5x）。
    `--offline` は「最後の実測の**写し**をもう一度解く」ので、印は 875814c が
    足していました。**ところが、その印を読む側が1つもありませんでした。**

    実際に踏んだ形（この回）——
    周の中で `--offline` を3回撃って直しを確かめたら、その3点が末尾に積まれ、
    **周の終わりの `--reflect` が、自分の debug の点を「前の回」として掴みました。**
    結果、この回の前後差は **2027-04-06 → 届かない** ではなく
    **「どちらも届かない」**と出ました —— **その回の作業ぶんが、消えます。**

    読みたいときだけ `offline=True`。
    """
    if not LOG.exists():
        return []
    out = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not reflect and row.get("kind") == REFLECT_KIND:
            continue
        if not offline and row.get("offline"):
            continue
        out.append(row)
    return out


#: **累計の窓（日）。`scripts/drift.py` の窓と同じにしてあります** ——
#: 別々にすると「343 ship で +33日 遠のいた」を並べて読めません。
TREND_DAYS = 7


def ships_in_window(days: int = TREND_DAYS, *, now: datetime | None = None) -> int:
    """`data/runs.jsonl` の ship を、直近 `days` 日ぶん数える。**落ちないこと。**

    数そのものが要るのではなく、**「これだけ撃って、日付はこれだけ動いた」**の
    右辺を出すために在ります。読めなければ 0 を返して黙ります
    （予測を、記録の欠けで止めないこと）。
    """
    path = ROOT / "data" / "runs.jsonl"
    if not path.exists():
        return 0
    cut = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    n = 0
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return 0
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("kind") != "ship":
            continue
        at = str(row.get("at") or "")
        try:
            when = datetime.fromisoformat(at)
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= cut:
            n += 1
    return n


def traj_trend(points: list[dict], cur_date: date | None,
               *, days: int = TREND_DAYS,
               now: datetime | None = None) -> dict | None:
    """**この `days` 日で、到達日は正味どちらへ動いたか。**

    ## なぜ要るか（2026-08-29 04:0x・最適化の回の実測）

    `headline()` は「**前の回の予測 → ±N日**」しか出しません。**1歩ぶん**です。
    実測 2026-08-28 の回は **+3日**。読んだ回は誤差として通します。

    **同じ台帳（`data/eta.jsonl`）を 7日 ぶん足すと、こうなっていました**::

        08/21 の最後の点  2026-12-10（残り 111日）
        08/28 の最後の点  2027-01-12（残り 136日）
        → **+33日 遠のいた**（残りの距離は **+25日**）

    そのあいだに **147周・343 ship**（`scripts/drift.py` の同じ窓）。
    **1周ごとの ±N日 では、この向きは1度も見えません** ——
    9日ぶんの点を1つずつ見ても、日ごとの差は −9〜+15日 の振れにしか見えないからです。

    ## 何を並べるか（**「遠のいた」だけを出さない**）

    `CLAUDE.md` は「**裸の『届きません』を出さないこと**」と書いています。
    向きだけ出して理由を出さないのは、その最小版の違反です。だから
    **同じ行に、天井の分子と分母を並べます**（下の `headline()` が組みます）。

    実測 2026-08-21 → 08-28::

        月の再生 `views_28d`                33,405 → 69,386   **+108%**
        分母 `videos_with_views_28d`            29 → 126      **+334%**
        比  `per_video_now`                    982 → 550      **−44%**
        天井 `ceiling_views_month`           2.71e6 → 1.65e5

    **再生は2倍 になったのに、比は 44% 落ちています。** 落ちたのは分母のほうです
    （**齢で揃えていない**。公開した翌日の本も、分母には丸ごと1本 入ります）。
    そして `ceiling_views_month` は **その比 × 上限10本/日 × 30日**（08/25 以降）なので、
    **出すほど天井が下がり、`lever_hint` は `per_video` を指し続けます。**

    ## 返り

    `None`（比べられる点が無い・窓が短すぎる）か、
    `{from_date, from_at, to_date, delta, span_days, n, was, now}`。
    `was` / `now` は、その両端の点そのもの（呼ぶ側が中身を選ぶ）。

    ## 覆る条件

    - **物差しが変わった回は、この差に混ざります。** 08/24〜08/25 に
      `ceiling_views_month` が 1.69e6 → 1.84e5 と 9倍 落ちたのは式の入れ替えで、
      チャンネルは何も変わっていません。**だから `traj_date` どうしだけを比べ**、
      入力の内訳は「％」で並べて、日付の差とは別の欄に出します
    - `per_video_now` が**齢で揃った**推定に変わったら（`data/views.jsonl` の
      齢 48〜120h の読み。`_members_by_*` と同じ揃え方）、上の「分母」の行は
      要らなくなります。**そのときこの docstring の表ごと書き換えること**
    """
    if not points:
        return None
    rows = [r for r in points if r.get("traj_date") and r.get("at")]
    if len(rows) < 2 or cur_date is None:
        return None
    rows.sort(key=lambda r: str(r["at"]))
    cut = (now or datetime.now(timezone.utc)) - timedelta(days=days)
    inside = []
    for r in rows:
        try:
            when = datetime.fromisoformat(str(r["at"]))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=timezone.utc)
        if when >= cut:
            inside.append((when, r))
    if len(inside) < 2:
        return None
    # **起点は「窓の中でいちばん古い1点」ではなく、その日の中央値**
    # （2026-08-29 に測って変えた）。
    #
    # 1点だと、**同じ日の中の振れをそのまま起点にします。** 実測 08/21::
    #
    #     その日の点 9つ  2026-12-02 〜 2026-12-10（**同じ日で 8日 の幅**）
    #     16:28 の1点     2026-12-28   ← 端を掴むと、累計が 18日 ずれる
    #
    # 中央値なら、掴む点が1つ ずれても累計はほとんど動きません。
    # **「中央値どうし」であることを、印字にも出すこと**（下の `basis`）。
    first_day = inside[0][0].date()
    same_day = [(w, r) for w, r in inside if w.date() == first_day]
    dates = []
    for _, r in same_day:
        try:
            dates.append(date.fromisoformat(str(r["traj_date"])))
        except ValueError:
            continue
    if not dates:
        return None
    dates.sort()
    was = dates[len(dates) // 2]
    first_at = same_day[len(same_day) // 2][0]
    span = (inside[-1][0] - first_at).total_seconds() / 86400.0
    # **1日 未満の窓から「7日の累計」と名乗らないこと**（`_project_nth` が
    # 同じ穴で偽の伸び率を出していた —— この repo で通算13回目）。
    if span < 1.0:
        return None
    spread = (dates[-1] - dates[0]).days
    return {"from_date": was, "from_at": first_at, "to_date": cur_date,
            "delta": (cur_date - was).days, "span_days": span,
            "n": len(inside), "n_base": len(dates), "base_spread": spread,
            "was": same_day[len(same_day) // 2][1], "now": inside[-1][1]}


def _trend_why(tre: dict) -> str:
    """累計の向きの**隣に置く理由**。**「遠のきました」を裸で出さないため**に在ります。

    `CLAUDE.md` は「**裸の『届きません』を出さないこと**」「何を固定したせいで
    そう出たのかを**同じ行に**並べること」と書いています。向きだけ出して
    理由を出さないのは、その最小版の違反です。

    ## 何を並べるか —— **天井の分子と分母**（2026-08-29 の実測でここに決めた）

    軌跡が遠のく理由は原理的にいくつもありますが、**この台帳で実際に効いていたのは
    1つ**でした。08/21 → 08/28 の点::

        月の再生 `views_28d`                 33,405 → 69,386   **+108%**
        分母 `videos_with_views_28d`             29 → 126      **+334%**
        比  `per_video_now`（＝ 分子÷分母）      982 → 550      **−44%**

    **再生は2倍 になったのに、比は 44% 落ちています。落ちたのは分母のほう**です。

    **その理由は「齢で揃っていない」ではありませんでした**（2026-08-29 に測り直した。
    ここには長らくそう書いてありました）。`data/views.jsonl` を齢でそろえて読むと、
    **ショートは 24時間 でほぼ伸びきります** —— 08/19 の8本は
    **齢24h で平均 1,018回・齢168h で 1,015回**（+0%）。**昨日の本も 28日 回った本も、
    同じ「1本」として入れて構いません。**

    **本当の理由は、上限を超えて出したぶんが 0再生 のまま分母に入ることです。**
    実測（齢48時間 以上の 168本）: **1〜9再生 の 42本 が、分母の 29% を占めて、
    再生の 0.18% しか持っていません。** 公開日ごとに見ると、
    **生きた本数は出した本数によらず 10本 前後で止まります**:

        08/20  25本 → 生 10本 / 6,445再生      08/23  13本 → 生 10本 / 10,232再生
        08/21  32本 → 生 11本 / 6,791再生      08/24  10本 → 生 10本 /  8,386再生

    **32本 出した日より、10〜13本 の日のほうが再生は多い。**

    そしてこの比は捨て置かれません。`ceiling_views_month`（08/25 以降）は

        天井 = `per_video_now` × `view_cap_per_day`(10) × 30日

    なので、**出すほど天井が下がり**、`lever_hint` は `per_video` を指し続け、
    尾には「**どの帯でも届きません。いまの構成は、上限そのものが目標の下に
    あります**」が出ます。**主実行が毎周やっていること（出す）が、
    その回の採点を下げる形**です —— `src/arm_speed.forward()` の符号が
    逆だったのと同じ形（`scripts/drift.py` の註・2026-08-27 の実測）。

    ## **比のほうは 2026-08-29 に直しました**（この節は、直す前の記録です）

    齢で揃えた推定に替えるのは、**入力の総取り替え**です。実測 2026-08-29 に
    `data/views.jsonl` の齢 48〜120h の読みで公開日べつに出すと、標本は
    **1日 1〜32本**でばらつき、中央値は **08/20〜08/22 に 3・2・5回**まで落ちます
    （平均は 256・209・233）—— **上限10本/日 に当たった日は、大半の本が 0 に張り付く**
    ので、中央値と平均が二桁ちがいます。**どちらを取るかで天井が桁で変わる**入力を、
    確かめずに差し替えないこと。

    **その心配は当たっていましたが、替え先が違いました。** 齢で揃える必要は無く
    （上のとおり 24時間 で伸びきる）、替えるべきは**分母から「上限を超えて死んだ本」を
    外すこと**でした。中央値と平均が二桁ちがって見えたのは、
    **その日の大半が 0 に張り付いていたから**です ——
    **帯の中だけで見れば、中央値と平均は同じ桁に戻ります**（帯の中 n=84 平均 678回）。
    替えた側の定義と実測は `live_band_views` の docstring、
    検査は `tests/test_eta_live_band_per_video.py`。
    **判定日つきの前提は、もう立っています** —— `config/hypotheses.yaml` の
    「**1日の再生の合計は、その日に出した本数では動かない**」
    （`lever: density`・期限 **2026-09-05**・道具 `day_cap.day_total()`）。
    **同じことを二度 立てないこと。** あちらが「出す本数を増やしても
    その日の合計は増えない」を判定し、こちらは**その帰結を天井の式に写しただけ**です
    （分母から、増やしても 0再生 にしかならない本を外した）。
    あちらが **外れた**（`rho_scale` ≥ +0.30 ＝ 本数は合計を動かす）なら、
    **この分母の切り方も同時に外れます。** そのときは `_per_video()` の
    落ちる先を `views_per_video` に戻すこと。

    ## 覆る条件

    - `per_video_now` が齢を揃えた推定になったら、この関数の分母の行は
      **意味を失います**（そのとき `tests/test_eta_trend_line.py` の
      「分母を名指しする」検査を、新しい入力の名前へ書き換えること）
    - `ceiling_views_month` が `per_video_now` を掛けなくなったら、
      ここが名指ししている経路そのものが消えます
    """
    was, now = tre.get("was") or {}, tre.get("now") or {}

    def pct(k: str) -> tuple[float, float, float] | None:
        a, b = was.get(k), now.get(k)
        try:
            a, b = float(a), float(b)
        except (TypeError, ValueError):
            return None
        if a <= 0 or b <= 0 or a > 1e8 or b > 1e8:
            return None
        return a, b, (b - a) / a * 100.0

    # **物差しが窓の中で入れ替わっていないか**（2026-08-29・最適化の回。実測で踏んだ）。
    #
    # `traj_trend()` の覆る条件は「**物差しが変わった回は、この差に混ざります**」と
    # 書いており、**日付の側**はそれを `traj_date` どうしで比べることで守っています。
    # **％の側は守られていませんでした。**
    #
    # `_per_video()` は 2026-08-28 に落ち先を替えました（`views_per_video`
    # ＝帯の外まで入れた平均 → `views_per_video_live` ＝帯の中だけ）。
    # `data/eta.jsonl` の実測::
    #
    #     08/22 05:33  per_video_now 856 ＝ views_per_video 856（`_live` の欄なし）
    #     08/28 17:28  per_video_now 550 ＝ views_per_video 550（同上）
    #     08/28 23:57  per_video_now 665 ＝ views_per_video_live 665（views_per_video は 553）
    #
    # つまり 7日 の窓は**入れ替えの日をまたぎ**、この行は
    # 「**856 → 673 で −21%**」を、**左＝帯の外／右＝帯の中**で出していました。
    # 同じ物差しで並べると 856 → 553（**−35%**）です。
    #
    # しかも下の文言は「この行は `views_per_video` どうしの差で」と**名乗って**
    # いました —— 実際に割っているのは `per_video_now` なので、
    # **文言のほうが偽**です（`docs/JOURNAL.md`「枠の2行が食い違っていないか」の型）。
    #
    # **覆る条件**: 窓の両端がどちらも `views_per_video_live` を持つようになったら
    # （＝入れ替えから `TREND_DAYS` 日 たったら）、この枝は自分で黙ります。
    # 落ち先をまた替えたときは、ここの欄の名前も一緒に替えること。
    swapped = ((was.get("views_per_video_live") is None)
               != (now.get("views_per_video_live") is None))
    if swapped:
        raw = pct("views_per_video")
        same = ("**同じ物差しで並べると** `views_per_video` "
                "{a:,.0f} → {b:,.0f}（{p:+.0f}%）。").format(
                    a=raw[0], b=raw[1], p=raw[2]) if raw else \
               "**同じ物差しで並べられる点がありません。**"
        # **入れ替えの窓のあいだも、分母の話を落とさないこと**（2026-08-29・
        # この枝を足した回が、その場で気づいて足した）。
        # ここで早く返すと、7日 のあいだ「落ちたのは分母」が1度も出ません ——
        # **この行は輪が効いているかを読む唯一の行**なので、
        # 物差しの註を足す代わりに理由を消すのは、差し引きで悪くなります。
        den = pct("videos_with_views_28d")
        if den:
            same += ("**分母 `videos_with_views_28d` は {a:,.0f} → {b:,.0f}（{p:+.0f}%）** ——"
                     "**上限を超えて出したぶんが 0再生 のまま入ります**"
                     "（天井の分母からは `live_band_views` で外してあります）。").format(
                a=den[0], b=den[1], p=den[2])
        return ("[!] **この窓の中で、1本あたり再生の物差しが入れ替わりました** "
                "（`_per_video()` の落ち先: 帯の外まで入れた平均 `views_per_video` → "
                "**帯の中だけ** `views_per_video_live`）。"
                "**`per_video_now` の両端は、別の数です。比べないこと。** "
                + same
                + "**上の日数の差は `traj_date` どうしなので、この入れ替えは入っていません**"
                "（`traj_trend()` の覆る条件）。"
                "**窓が入れ替えの日を追い越せば、この行は自分で消えます。**")

    v = pct("views_28d")
    n = pct("videos_with_views_28d")
    r = pct("per_video_now")
    if not (v and n and r):
        return ""
    # **分子が増えたのに比が減った回だけ、名指しします。**
    # 両方 減った回は、本当に世界が悪くなっています（そこは名指ししない）。
    if not (v[2] > 0 and r[2] < 0):
        return ""
    return ("[!] **内訳: 月の再生 {vp:+.0f}%（{v0:,.0f}→{v1:,.0f}）**なのに "
            "**1本あたり再生 {rp:+.0f}%（{r0:,.0f}→{r1:,.0f}）** —— "
            "落ちたのは**分母**（`videos_with_views_28d` {np:+.0f}%・{n0:,.0f}→{n1:,.0f}）。"
            "**上限{cap:,.0f}本/日 を超えて出したぶんが、0再生のまま分母に入っています** "
            "（実測 2026-08-29: 1〜9再生 の 42本 が分母の 29%・再生の 0.18%）。"
            "**天井の分母からは外してあります**（`live_band_views`）ので、"
            "**この比の分母と、天井が使う分母は別です** —— "
            "この行が割っているのは `per_video_now`（＝ `_per_video()` の落ち先。"
            "いまは**帯の中だけ** `views_per_video_live`）で、"
            "**分母 `videos_with_views_28d` のほうは帯の外まで数えています。"
            "同じ行の分子と分母が、別の母集団です**").format(
        vp=v[2], v0=v[0], v1=v[1], rp=r[2], r0=r[0], r1=r[1],
        np=n[2], n0=n[0], n1=n[1],
        cap=float(now.get("view_cap_per_day") or 0))


#: `flagged()` が尾に運ぶ本数の上限。**多いほど尾が読まれなくなる**ので、
#: 増やす前に「頭と尾しか読まれない」という前提のほうを疑うこと。
FLAG_LIMIT = 12

#: `[!]` を**印として**打った所だけを拾う。行頭か、composed な行の区切り（全角空白）の直後。
#: **文の途中の `[!]` は、たいてい他人の文言の引き写しです**（ship の1行など）。
FLAG_MARK = re.compile(r"(?:^|　)[ \t]*\[!\][ \t]*")


def flagged(said: list[str], width: int = 116) -> list[str]:
    """**この回の出力の中で `[!]` が付いた所を、尾（読まれる場所）へ運ぶ。**

    ## なぜ要るか（2026-08-26・最適化の回の実測）

    `CLAUDE.md` は「**読むのは、出力の最初と最後に同じ字で出る3行だけ**」と
    書いています。**そのとおりに読むと、`[!]` は1本も読まれません。**

        実測 2026-08-26 …… 出力 297行・`[!]` **10本**（80〜289行目）
                            頭 8行 に **0本** ／ 尾 25行 に **0本**

    そのうち1本は、直す先を名指ししていました ——
    「**2026-09-06〜2026-09-18 の 13日 は長尺の予約が0本**です。
    直す先はサムネでも題でもなく、**その 13日 に長尺を置くこと**」。
    **どの回も読んでいません。**

    ## これは `headline()` が一度 学んだのと同じ話です

    `headline()` の説明が、その理由をこう書いています ——
    「**その日付が、出力の 200行目あたりにあった**。読み手が最初に見るのは
    天井の表です」。**そこで運んだのは日付だけで、警告は置いてきました。**
    **1つ上の階の同じ欠陥**で、この repo が「いちばん当たる」と言っている形
    （同じことを2か所が別々に言っていて、片方しか読まれていない）そのものです。

    ## 何をしないか

    **選り分けません。** 重要かどうかを決める規則を置くと、次の回はその規則の
    世話をします。ここは「`[!]` と書いた側が重要だと言っている」をそのまま
    信じて、**在り処と頭を運ぶだけ**です。全文は本文の側にあります。

    **覆る条件**: `[!]` が FLAG_LIMIT 本を超えて出るのが常態になったら、
    運ぶ側ではなく**付ける側**が緩んでいます（`[!]` を足した回が、
    尾に載るかを見て書かなくなったとき）。そのときはここを直すのではなく、
    **`[!]` を打つ場所を減らすこと。**
    """
    hits: list[tuple[int, str]] = []
    seen: set[str] = set()
    for i, line in enumerate(said):
        if "[!]" not in line:
            continue
        # **文の途中の `[!]` は拾わないこと**（2026-08-26 夜、入れた直後に踏んだ）。
        #     `levers.report()` は `data/runs.jsonl` の ship の1行をそのまま印字します。
        #     私自身が `--ship "eta の [!] 11本 を尾へ運び…"` と書いたので、
        #     **自分の ship の文言が「名指しされた欠陥」として尾に並びました。**
        #     印である `[!]` は、行頭か、composed な行の区切り（全角空白）の直後にしか出ません。
        for m in FLAG_MARK.finditer(line):
            t = " ".join(line[m.end():].split())
            if not t:
                continue
            key = t[:40]
            if key in seen:
                continue
            seen.add(key)
            hits.append((i, t))
    if not hits:
        return []
    bar = "###"
    out = [f"{bar} **この回に名指しされた欠陥: {len(hits)}件**"
           "（本文の真ん中に出ます。**頭と尾だけ読む手順では1本も読まれません**）"]
    for i, t in hits[:FLAG_LIMIT]:
        body = t if len(t) <= width else t[:width] + "…"
        out.append(f"{bar}   ・{body}")
    if len(hits) > FLAG_LIMIT:
        out.append(f"{bar}   （ほか {len(hits) - FLAG_LIMIT}件。全文は本文の `[!]` を見ること）")
    return out


#: **天井が乗っている控えと、それを取り直す手**（2026-08-28・最適化の回）。
#:
#: 値は `(表示名, 取り直す手)`。**手の名前だけ**を持ちます —— どの手がどの枠を
#: 使うかは `src.upload_cap.DATA_API_TOOLS` が持っているので、ここには写しません。
_CEILING_SOURCES: tuple[tuple[str, str, str], ...] = (
    ("面（インプレッション）", "data/reach.jsonl", "python scripts/reach.py"),
    ("混ざり方（RPM）", "data/rpm_mix.jsonl", "python -m src.rpm_mix"),
    ("1本あたり再生", "data/views.jsonl", "python scripts/snapshot.py"),
    ("本べつの形", "data/video_forms.json", "python -m src.rpm_mix --forms"),
)


def instrument_ages(now: datetime | None = None) -> list[str]:
    """**天井が、いつの控えに乗っているか。** API 0単位・ファイルを読むだけ。

    ## なぜ3行の側に出すか（2026-08-28）

    天井は **2つの実測の積**（混ざり方 × 面）です。そのどちらかが止まっても、
    **天井は黙って低く出ます** —— 実測 2026-08-24: `data/reach.jsonl` が 08/17 で
    止まったまま出た天井が **¥184**、`scripts/reach.py` を撃ち直したら **¥287**
    （**56% 低い**）。**止まっていたことは、どこにも表示されていませんでした。**

    `src.rpm_mix._reach_freshness_lines` は、この遅れを正しく測る書き方を
    **2026-08-24 に既に持っています**（「今日と比べないこと。比べるのは
    Analytics の中身の最終日」）。**それが読まれる場所に無いだけ**でした ——
    あれが出るのは `rpm_mix` 自身の出力で、**1周の中で誰も撃ちません。**
    ここは「同じことを2か所が別々に言っていて、片方しか読まれていない」の
    3例目です（`CLAUDE.md`）。

    ## 門にしないこと（**しきい値を置きません**）

    **「何時間で古い」を決めません。** 控えごとに追いつける最前線が違い
    （Reporting は3日、Analytics は3日、`views` は日枠しだい）、
    **時間で切ると、追いついている日にも鳴ります**（`_reach_freshness_lines`
    の註がそう言っています）。鳴りっぱなしの警告は読まれません。
    **だからここは事実だけを並べます** —— 天井の隣に、その控えの齢を置く。
    **どれを取り直すかは、その回が決めます。**

    ## いま撃てるかは、枠の持ち主に訊く

    `python scripts/snapshot.py` だけが Data API の日枠を使います
    （`src.upload_cap.DATA_API_TOOLS`）。**日枠が尽きていても、
    Analytics と Reporting は別の枠なので通ります** —— 2026-08-28 に
    実際に通り、要件1件の判定日が 09-03 → 08-30 へ動きました。
    **一覧をここに写さないこと**（写した日から古くなります）。

    **覆る条件**: 1周ごとに全部の控えを取り直す作りにしたら、この行は
    毎回おなじ齢を出すだけになるので外してよい。
    `tests/test_eta_instrument_ages.py` が、いまの向きを留めています。
    """
    now = now or datetime.now(timezone.utc)
    try:
        import deadline_check                                   # noqa: PLC0415
    except Exception:                                          # noqa: BLE001
        return []
    try:
        from src import upload_cap                             # noqa: PLC0415
        q = upload_cap.day_quota()
        dead = not q.open
        tools = tuple(upload_cap.DATA_API_TOOLS)
    except Exception:                                          # noqa: BLE001
        dead, tools = False, ()
    parts: list[str] = []
    for label, rel, how in _CEILING_SOURCES:
        path = ROOT / rel
        if not path.exists():
            parts.append(f"{label} **無し**")
            continue
        try:
            point = deadline_check.newest_point(path)
        except Exception:                                      # noqa: BLE001
            # **この行のために eta.py を落とさないこと。** 毎回いちばん最初に
            # 撃つ道具なので、齢が読めない控えが1つあるだけで回が死にます。
            parts.append(f"{label} **齢が読めません**")
            continue
        if point is None:
            parts.append(f"{label} **齢が読めません**")
            continue
        hours = (now - point).total_seconds() / 3600.0
        blocked = dead and any(t in how for t in tools)
        parts.append(f"{label} **{hours:,.0f}時間**"
                     + ("（日枠が尽きるまで取り直せません）" if blocked else ""))
    if not parts:
        return []
    return ["   天井が乗っている控えの齢: " + " ／ ".join(parts)
            + "  ← **古いほど天井は低く出ます**"
            " （実測 08/24: 面が 7日 遅れて ¥184、取り直して ¥287）。"
            " 取り直す手は `scripts/reach.py` / `-m src.rpm_mix [--forms]`"
            " / `scripts/snapshot.py`。"
            "**日枠が尽きていても、前の3つは別の枠なので通ります**"]


def _ab_side_clause() -> str:
    """**走っている A/B の内訳**を、頭の3行に入る長さで1節にする。

    **台帳の枠より、こちらが希少です** —— 開いている前提は 27件 ありますが、
    無作為化されて同じ本の流れに乗っているのは `ab_split.EXPERIMENTS` の数件だけ。
    実測 2026-08-29 は **4件とも `content`**（＝速いほうの枠が 0）。

    **読めなくても回を止めません**（空文字を返す）。
    """
    try:
        from src import ab_split                                # noqa: PLC0415

        ac = ab_split.side_counts()
        tot = sum(ac.values())
        if not tot:
            return ""
        if not ac.get("dist"):
            return (f"／ **無作為化して走っている A/B {tot}件 は、"
                    "配信の側 0件**（`src/ab_split.EXPERIMENTS`）")
        return (f"／ 走っている A/B {tot}件 は 配信 {ac.get('dist', 0)}件 ／"
                f" 中身 {ac.get('content', 0)}件")
    except Exception:                                           # noqa: BLE001
        return ""


def _theta_line(tr: dict | None, base: dict | None) -> list[str]:
    """`_theta_days()` を、頭の3行に並べる1行にする。**読めなければ黙って消える。**

    黙って消してよいのは「解けなかった」ときだけです（`theta` が `None`）。
    **`t_work == 0` の回は、消さずに『θ をいくつにしても同じ』と言います** ——
    消えたのが「解けなかった」なのか「効かない」なのか、読む側から
    区別が付かなくなるので。
    """
    th = (tr or {}).get("theta")
    if not th or base is None:
        return []
    bar = "###"
    if not th.get("t_work"):
        return [f"{bar} **θ（前提が閉じる速さ ＝ いま {th['per_day']:.2f}件/日）は、"
                "この回の到達日を動かしません** —— 軌跡の `t_work` が 0日"
                "（＝**いま走らせるのが最短**）なので、腕を速く動かしても"
                "同じ日付に着きます。**縛っているのは腕ではなく、下の床のほうです。**"]

    def _d(t: dict, delta: float | None) -> str:
        if t.get("date") is None or delta is None:
            return "**出ません**"
        return f"**{t['date'].isoformat()}**（**{delta:+,.0f}日**）"

    # **「いちばん大きい」を無条件に書かないこと**（2026-08-30、書いた直後に直した）。
    #     この回の実測では θ の天井が配分の差の 4.5倍 でしたが、`t_work` が
    #     縮んだ回は逆になり得ます。**比べてから、比べた結果を名乗ること** ——
    #     無条件の最上級は、次に読む側が確かめずに済む形です。
    alloc = None
    pln = (tr or {}).get("planned")
    if pln and pln.get("days") is not None and pln["days"] < NEVER:
        d = pln["days"] - base["days"]
        alloc = d if abs(d) > 0.5 else None
    inf_d = th.get("inf_delta")
    biggest = (alloc is None or inf_d is None or abs(inf_d) > abs(alloc))
    head = ("**到達日をいちばん大きく動かすのは θ" if biggest
            else "**θ")
    line = (f"{bar} {head}（前提が閉じる速さ ＝ いま"
            f" {th['per_day']:.2f}件/日・閉じた {th['n']}件 ÷ {th['days']:,.0f}日）です**"
            f" —— θ×2 で {_d(th['x2'], th['x2_delta'])}"
            f" ／ 天井（θ→∞）で {_d(th['inf'], th['inf_delta'])}。"
            f"（軌跡は θ に反比例する `t_work` を **{th['t_work']}日** 取っています）")
    # **配分の振り直しと、同じ行で並べること。** 単独で出すと「大きい数」に
    #     見えるだけで、**この回に選べる他の手より大きいのか**が言えません。
    if alloc is not None and inf_d:
        line += (f" **台帳の配分との差は {alloc:+,.0f}日**"
                 "（下の「台帳が実際に用意している配分」の行）で、"
                 f"θ の天井はその **{abs(inf_d / alloc):.1f}倍**"
                 + ("です。" if biggest else "しかありません ——"
                    " **この回は配分のほうが大きい。**"))
    # **上げ方を、同じ行で名指しすること。** 名前の無い所は「やれること」で埋まります
    #     （`tests/test_eta_covered_substitute.py` が一度 直した形）。
    #     **在庫が余っている回だけ**この節を出します。下回ったら逆の手なので、
    #     そのときは黙るのではなく「増やすこと」を出す（下の `else`）。
    n_open = th.get("open")
    if n_open:
        need = th["per_day"] * th["t_work"]
        line += (f" **上げ方は2つあり、どちらが縛っているかはここでは言えません** ——"
                 f" 軌跡は `t_work` のあいだに **{need:,.0f}件** 閉じる前提で"
                 f" 立っていて、台帳に開いているのは **{n_open}件**"
                 f"（{'足りない' if n_open < need else '足りる'}）。"
                 "**(1) 件数** → `python scripts/eta.py --alloc`（どの腕に立てるか）。"
                 "**(2) 立ててから判定できるまでの日数**（群の床 →"
                 f" **予約の順番待ち** → 落ち着き{settle.SETTLE_DAYS}日 →"
                 " Analytics の遅れ3日）→ `python scripts/queue_lag.py`。"
                 " **`(1)` は在庫の写真で、補充の速さを見ていません** ——"
                 "立つ速さは `closed_on` のような欄が無いので**この機械からは読めません**。"
                 " 数えるなら `git log -p config/hypotheses.yaml` の"
                 " `- claim:` の増え方（実測 2026-08-30: 開いた前提は"
                 " 08/24 15件 → 08/30 32件 ＝ **2.8件/日**・閉じるのは 0.77件/日 ＝"
                 " **在庫は増えつづけている** → そのときの縛りは (2) のほうでした）")
    return [line]


def headline(pl: dict, prev: dict | None = None,
             tr: dict | None = None,
             points: list[dict] | None = None,
             *, now: datetime | None = None) -> list[str]:
    """**この回のいちばん最初と、いちばん最後に出す3行。**

    ## なぜ2回出すか（2026-08-20 08:0x・オーナー指示3回目）

    > 「20万達成までのプランを作って**達成日時を予測**して、
    >   **毎回達成日時を早めることを考えてから進める**ようにして」

    同じ趣旨の指示は 08-19（33699957）・08-20 06:2x に続き**3回目**です。
    **3回言われている ＝ まだ形になっていない。**

    出ていなかった理由は2つあり、どちらも「書いてなかった」ではありません。

    1. **段4 の期日が段3 の写しだった** …… 日付は出ていたが、それは
       「収益化が終わる日」で、**20万に届く日ではありませんでした**（`plan()`）
    2. **その日付が、出力の 200行目あたりにあった** …… `eta.py` の出力は長く、
       読み手が最初に見るのは天井の表です。**最初に見た数字が、その回の入口**になります

    だから**日付と、引くべき腕を、最初と最後の両方に置きます。**
    真ん中は読み飛ばしても、この3行だけで「今日は何を動かすか」が決まる形にすること。
    """
    bar = "###"
    out = ["", "=" * 66]
    # **いちばん上に出す日付は「軌跡」のほうです**（2026-08-20 18:xx・オーナー指示）。
    #     腕を据え置いた線（`pl["target_date"]`）は、**腕が1ミリも動かない未来**の
    #     日付です。この機械は毎周かならず腕を1つ引いているので、それは
    #     「特定条件の予測」であって、辿る道ではありません。
    base = (tr or {}).get("base")
    if base is not None:
        if base["date"] is not None:
            out.append(f"{bar} **月20万の到達予測（軌跡）: {base['date'].isoformat()}**"
                       f"（{math.ceil(base['days']):,}日後）"
                       f" …… 腕を {base['t_work']}日 動かして、そこから"
                       f" {base['plan_days']:,.0f}日")
        else:
            out.append(f"{bar} **月20万の到達予測（軌跡）: 出ません**"
                       f" …… {base['blocking'][0] if base['blocking'] else '塞いでいる所が名指しできていません'}")
        fast, slow = (tr or {}).get("fast"), (tr or {}).get("slow")
        if fast and slow:
            def _d(x):
                return x["date"].isoformat() if x["date"] else "出ません"
            out.append(f"{bar} 幅（当たる確率の90%区間）: 早い **{_d(fast)}**"
                       f" ／ 遅い **{_d(slow)}**（遅い側が「外れ続けた場合」）")
        # --- **その幅は θ を固定して出しています**（2026-08-26・最適化の回） ---
        #     上の `t_work`（「腕を N日 動かして」）は `rate = p·log(g)·θ` の
        #     **θ にそのまま反比例**します。その θ は `arm_speed.throughput()`
        #     ＝ `closed_on` の**過去の実測 ÷ 経過日数**で、**未来を1件も見ていません。**
        #     実測 2026-08-26: 過去 0.95/日 に対し、**この機械自身の予定表**
        #     （開いた前提の「判定できる日」）は 今後14日 0.50/日・30日 0.33/日。
        #     **21件のうち12件が 08/20 の1日**（それ以前の16日間は 0件）で、
        #     分母の22日は「その速さで回っていた22日」ではありません。
        #     `CLAUDE.md` の (イ)「**何を固定したせいでそう出たのかを同じ行に並べる**」を、
        #     **θ にも当てます** —— 幅の遅い側（2027-03-14）でさえ、
        #     30日窓の θ が出す日付（≒2027-03-31）を含んでいませんでした。
        #
        #     ### **その「含んでいない」は、直しに行かないこと**（2026-08-27 に測った）
        #
        #     上の1行を「幅が狭すぎる欠陥だ」と読んで広げに行くと、空振りします。
        #     `forward()` の `per_day = n / h` は**分子が開いた前提の件数で頭打ち**、
        #     分母 `h` だけが伸びるので、**予定表が完璧でも**窓とともに 0 へ行きます。
        #     実測 2026-08-27（軌跡 2026-12-23・幅 2026-12-02〜**2027-03-01**）::
        #
        #         14日窓 θ×0.70 → 2027-01-11   最大の 47%  ← **幅の内側**
        #         30日窓 θ×0.40 → 2027-02-21   最大の 58%  ← **幅の内側**（08/26 は外だった）
        #         60日窓 θ×0.27 → 2027-03-31   最大の 79%  ← 外。**ただし artifact**
        #
        #     **外に出ているのは60日窓だけで、それは既に天井の 79%**（開いた前提が
        #     19件しか無い ＝ 60日窓で取りうる最大が 0.35倍）。**予定を1日も
        #     動かせないので、幅を広げても読みが良くなりません。**
        #     上げ方は `forward_line()` が窓ごとに名指しします。
        try:
            _fw = arm_speed.forward(_ready_by_claim())
            _fl = arm_speed.forward_line(_fw)
        except Exception:
            _fl = None
        if _fl:
            out.append(_fl)
        # --- **θ に、日数の値札を付ける**（2026-08-30・最適化の回に足した） ---
        #     値札の付いていない数は、他の手と並べて比べられません。
        #     理由と実測は `_theta_days()` の docstring。**消す条件もそこ。**
        out.extend(_theta_line(tr, base))
    # **軌跡が解けなかった回でも、「到達予測」の字は必ず出すこと。**
    #     ここを「据え置いた線」だけにすると、軌跡が落ちた回の出力から
    #     **到達予測という言葉ごと消えます**（検査が1件それを見ています）。
    label = ("腕を**据え置いた**線" if base is not None
             else "**月20万の到達予測（腕を据え置いた線）**")
    if pl["target_date"] is not None:
        out.append(f"{bar} {label}: {pl['target_date'].isoformat()}"
                   f"（{_fmt_days(pl['days_to_target'])}）"
                   + ("" if base is None else " ← **腕が1ミリも動かない未来。辿る道ではありません**"))
    else:
        out.append(f"{bar} {label}: **出ません**"
                   "（天井が足りない。下に「どの腕をいくつにすれば出るか」）")
    out.append(f"{bar} 縛っているのは **{pl['binding']}**"
               f" → **この回に引く腕は `{pl['lever_hint']}`**"
               + (f"（**軌跡が名指し**。床の名前は `{pl['lever_hint_binding']}` ですが、"
                  "それは診断であって、引いて何日縮むかは言っていません）"
                  if pl.get("lever_from") == "軌跡" else ""))
    if pl.get("lever_hint_covered"):
        out.append(f"{bar} **その `{pl['lever_hint']}` の測定は、予約済みの本が"
                   f" {pl['lever_hint_covered']} に答えます** →"
                   " **この回は別の腕を引くこと。**"
                   f" `--lever` が `{pl['lever_hint']}` でなくても、"
                   "この回は「名指しを外した」ではありません")
        # --- **「別の腕」に、名前を付ける**（2026-08-30・最適化の回に足した） ---
        #     ここは長らく「別の腕を引くこと」で終わっていました。**名前が無い**ので、
        #     回の側は「やれること」の中から選び、結果は毎回おなじ所へ落ちます ——
        #     実測 2026-08-30 05:5x、`data/runs.jsonl` の **ship 358件（7日ぶん）**:
        #     `lever_hint` は **358件とも `per_video`**（名指しは1本も変わっていない）、
        #     `lever_followed` は **False が 312件（87%）**。振り先は
        #     `none` 152 ／ `density` 106（**`lever_cap` は全件 1.0**）／
        #     `per_video` 46 ／ `rpm` 29 ／ `sub_rate` 25 ——
        #     **258件（72%）が、この機械が自分で「動かない」と測った側**です。
        #     ところが同じ回の `pl["lever_days"]` は `density` を
        #     **天井 ×1.00・`reachable_at_cap=False`** と出しており、
        #     `arm_frozen_days["density"]` は **0.0日**（＝丸ごと凍らせても
        #     到達日は1日も動かない）。**この機械は毎周、自分が 0日 と測った腕を
        #     引いていました。** 名指しが空欄だったことが、その既定を作っています。
        #     **そのあいだ到達予測は +20日 遠のいています**（2026-12-21 → 2027-01-10）。
        #
        #     出すのは1本だけ: **`reachable_at_cap` が真な腕のうち、
        #     `gain_at_cap` がいちばん大きいもの**（名指しされた腕は除く）。
        #     `lever_days` は既にその順で並んでいます（`lever_days()` の `rows.sort`）。
        #
        #     **覆る条件**: `reachable_at_cap` の真な腕が、名指しの1本しか
        #     無くなったら（＝除いたら候補が空）、この行は自分で消えます。
        #     そのときは腕を選ぶ話ではなく、天井そのものが足りない回です
        #     （頭の「腕を**据え置いた**線: 出ません」と同じ事情）。
        #     検査は `tests/test_eta_covered_substitute.py`。
        _rows = pl.get("lever_days") or []
        _alt = next((r for r in _rows
                     if r["lever"] != pl["lever_hint"]
                     and r.get("reachable_at_cap") and not r.get("at_ceiling")), None)
        _frz = pl.get("arm_frozen_days") or {}
        # **0日 の腕を、同じ行で名指しして塞ぐこと。** 代わりを出すだけでは、
        #     既定（`density`）は残ります —— 名前が2つ並んだときに読み手が
        #     選べてしまう形は、この道具が `lever_hint` で一度 直しています。
        # **`None` を先に落とすこと。** `frozen_days()` の返りは
        #     `dict[str, float | None]` で、軌跡が解けなかった腕は `None` です。
        #     並べ替えの鍵に混ぜると `TypeError` で頭の3行ごと落ちます
        #     （＝この回の入口が消える）。**選別が先、並べ替えが後。**
        _dead = [f"`{k}`（凍らせても **{v:,.0f}日**）"
                 for k, v in sorted(((k, v) for k, v in _frz.items()
                                     if v is not None and v < 1.0),
                                    key=lambda kv: kv[1])]
        # **`density` の 0日 は「ショートの面」だけの話です**（2026-08-30）。
        #     `arm_caps["density"]` は `day_cap.cap()`（ショートの面で1日に
        #     再生が付く本数）で立っており、**長尺はその枠を1つも使いません。**
        #     そして **4,000時間の門に入るのは長尺だけ**です。
        #     `src/levers.py` の `_long_surface_open()` は既にここを割っていて、
        #     長尺の面が開いていれば `density` を「死んだ腕」に入れません。
        #     **頭の3行だけが割らずに塞ぐと、長尺を増やす作業まで止まります** ——
        #     この repo が3回 申し送って直した所を、こちらから戻すことになります。
        #     **覆る条件**: 長尺の面が `at_ceiling` になったら、この但し書きは消えます。
        #     **文の途中に差し込まないこと**（2026-08-30 に踏んで直した）。
        #     いちど `_dead` の要素そのものに足したところ、行が
        #     「`density`（…）。**ただし…**（長い） **をこの回の `--lever` に
        #     しないこと**」となり、**禁止の述語が但し書きの向こう側へ飛びました。**
        #     頭の3行は「読み飛ばしても決まる形」なので、**述語を分断しないこと。**
        #     但し書きは行の**末尾**に付けます。
        _long = ((pl.get("density_surfaces") or {}).get("long") or {})
        _surface = ""
        if _dead and _long and not _long.get("at_ceiling") \
                and any(s.startswith("`density`") for s in _dead):
            _surface = ("　**ただし `density` のその 0日 は「ショートの面」だけの数です** ——"
                        "長尺の面はまだ天井ではありません"
                        + (f"（{_long.get('why')}）" if _long.get("why") else "")
                        + "。**止めているのはショートの本数を増やす回であって、"
                        "長尺を増やす回ではありません**（長尺は面とシェア ＝"
                        " `--lever rpm` で押すこと）")
        if _alt is not None:
            _th = _alt.get("threshold")
            # **勝った腕の天井が実測でないなら、勝ちの理由がそこにあります。**
            #     `--alloc` と `_report_levers` は既にこの注意を出しています
            #     （`alloc_search` の末尾・`tr["arms"]` の `cap_measured`）。
            #     **頭の3行にだけ無い**ので、ここへ持ってきます —— 実測 2026-08-30 の
            #     `rpm` は ×61.35 で、出どころは「長尺の面 × **CTR 100%**」＝
            #     測った天井ではありません。**黙って名指しすると、作り物の天井に
            #     回を1つ振らせることになります。**
            _arm = ((tr or {}).get("arms") or {}).get(_alt["lever"]) or {}
            _unmeasured = (" [!] ただしその天井は**測ったものではありません**"
                           f"（{_arm.get('cap_why', '出どころなし')}）——"
                           "**天井が作り物なら、名指しも作り物です**"
                           if _arm.get("cap") and not _arm.get("cap_measured") else "")
            out.append(
                f"{bar} **その「別の腕」は `{_alt['lever']}` です**"
                f"（天井 ×{_alt['cap']:,.2f} → {_alt['date_at_cap'].isoformat()}"
                + (f"・日付が出はじめるのは **×{_th:,.2f}** から" if _th else "")
                + "）—— **天井まで引けば日付が出る腕は、これと"
                f" `{pl['lever_hint']}` だけ**です（`reachable_at_cap`）。"
                + (" **" + "／".join(_dead) + " をこの回の `--lever` にしないこと**"
                   " —— この機械が自分で測った「引いても到達日が動かない」腕です"
                   if _dead else "")
                + _unmeasured + _surface)
        elif _dead:
            out.append(
                f"{bar} [!] **その「別の腕」がありません** ——"
                f" 天井まで引いて日付が出るのは `{pl['lever_hint']}` だけで、"
                + "／".join(_dead)
                + " は**凍らせても到達日が動きません**。"
                "**この回は腕を選ぶ回ではなく、天井そのものを測り直す回です**"
                "（上の「天井の齢」の行）")
    # --- **その日付が前提にしている配分を、台帳が用意しているか**（2026-08-26） ---
    #     上の日付は `share`（**閉じた前提の割合 ＝ 過去にどう振ってきたか**）で
    #     解かれています。**未来の配分を決めているのは、開いている前提のほう**です。
    #     食い違っていたら、上の日付は**台帳が用意していない世界**の日付です。
    out.extend(_planned_lines(bar, tr, base))
    # **天井の齢を、天井を名指しした行のすぐ隣に置く**（2026-08-28）。
    #   しきい値は置きません —— 理由は `instrument_ages()` の註。
    #
    #   **`base` で分けないこと**（同じ日に踏んで直した）。足したときは
    #   `if base is None` で括っていました —— 「据え置いた線の側に二重に
    #   出さない」つもりでしたが、**`base` が None なのは軌跡が解けなかった
    #   回だけ**です。ふだんは軌跡が解けるので `base` は埋まっており、
    #   **この行は一度も出ませんでした**（実測: `eta.py` の出力に1行も無し）。
    #   `headline()` は頭と末尾で2回 呼ばれますが、**同じ引数の同じ塊**なので、
    #   分ける理由はそもそもありません。
    out.extend(instrument_ages())
    top = next((r for r in (tr or {}).get("choice", []) if r["reachable"]), None)
    if top is not None:
        gain = (base["days"] - top["days"]) if base and base["days"] < NEVER else None
        out.append(f"{bar} **回転を全部振るなら `{top['lever']}`** →"
                   f" {top['date'].isoformat()}"
                   + (f"（軌跡より **{gain:,.0f}日 早い**）" if gain and gain > 0
                      else "（軌跡と同じか、遅い）"))
    # **腕の名前を出したら、その腕が何で動くのかも同じ3行に出す**
    # （2026-08-21 05:xx に測って足した）。この回は `density` の入力
    # `make_rate` を **22.85 → 46.7（2倍）** に動かしましたが、
    # 到達日は **+0日** でした。軌跡の腕は `config/hypotheses.yaml` の
    # **閉じた前提の実測**だけで動くので、テーマを作っても在庫から出しても
    # 1ミリも動きません。**その区別が3行の中に無いと、次の回も同じ所へ来ます。**
    arms = (tr or {}).get("arms") or {}
    hint = pl.get("lever_hint")
    a_hint = arms.get(hint)
    if a_hint is not None:
        th = a_hint.get("throughput")
        turn = f"実測 {1 / th:,.1f}日に1件" if th else "実測なし（閉じた前提が0件）"
        pr = a_hint.get("p")
        prob = f"・当たり {pr:.0%}" if pr is not None else ""
        out.append(
            f"{bar} **軌跡の腕が動くのは、`config/hypotheses.yaml` の前提を"
            f"1件閉じたときだけ**（`{hint}`: {turn}{prob}）。"
            "**作る・出す・直すは、軌跡の入力に入りません** ——"
            "段の側（`--reflect` が測る入力）は動きますが、"
            "**上の日付は動きません**")
        # **腕を名指ししたら、その隣で「側」も名指しすること**（2026-08-29 に足した）。
        #
        # 上の行は「前提を1件 閉じないと日付は動かない」と言いますが、
        # **どの前提を立てるかまでは言いません。** 同じ腕の中で、その回に
        # いじるのが**動画の外側**（形式・時刻・本数・間隔・面）か
        # **中身**（題・文言・冒頭の絵・尺）かで、実測の当たり方が
        # **13.9倍** ちがいます（`src/arm_speed.sides()`）。
        # **この1行を `--alloc` の中だけに置かないこと** —— `CLAUDE.md` が
        # 「読むのは頭と末尾の3行だけ」と書いている以上、
        # **決め手が本文の中にあると、決める回には届きません。**
        try:
            sd = arm_speed.sides()
            r = sd["ratio"]
            if r:
                out.append(
                    f"{bar} **その1件を、どちらの側に立てるか**: 実測で"
                    f" **配信の側（形式・時刻・本数・面）は中身の側（題・文言・絵・尺）の"
                    f" {r:.1f}倍**"
                    f"（当たり {sd['closed']['dist']['p']:.0%} 対"
                    f" {sd['closed']['content']['p']:.0%}"
                    f"・n={sd['closed']['dist']['n']} 対 {sd['closed']['content']['n']}）。"
                    f"**いま開いているのは 配信 {sd['open']['dist']}件 ／"
                    f" 中身 {sd['open']['content']}件**"
                    + _ab_side_clause() +
                    "。**この数で上の日付は動かしていません**（有意ではない ——"
                    " `src/arm_speed.sides()` の「覆る条件」）")
        except Exception:                                       # noqa: BLE001
            pass
        # **そのうえで「いつなら動くのか」を出す**（2026-08-21 06:xx）。
        # 期日の来た前提が1件も無い回は、**何をしても到達日は動きません。**
        # それを先に言わないと、その回は外れる `--moves` を立てるだけで終わります。
        # **`deadline` ではなく「データが揃う日」で聞くこと**（2026-08-25 22:5x）。
        # `deadline` は置いた回の勘です。`deadline_check.ready_by_claim()` は
        # 予約・台帳・Analytics の遅れから**実際に判定できる日**を出します。
        # 実測でここは **10件・合計46日**（平均4.6日・最大14日）ずれていて、
        # **その46日は軌跡がまるごと止まっている日数**でした
        # （腕は前提を1件閉じたときだけ動くので）。
        try:
            ready = _ready_by_claim()
        except Exception:
            ready = None
        # **`ready` が出せなかった claim を、`deadline` へ落とさないこと**
        # （`_unready_claims` の註。判定に要る本が0本の日に
        #   「この回は `verdict` で日付が動かせます」と出ていました）
        try:
            unready = _unready_claims()
        except Exception:
            unready = None
        try:
            nc = arm_speed.next_close(ready=ready, unready=unready)
        except Exception:
            nc = None
        if nc and nc.get("on") is not None:
            if (nc.get("days") or 0) > 0:
                # --- **「どんな作業をしても動きません」は嘘でした**（2026-08-26・最適化の回） ---
                #
                # ここは 2026-08-25 まで、こう印字していました::
                #
                #     **それまでは、どんな作業をしても上の日付は動きません**
                #     （`--moves 0` が正しい回です）
                #
                # **前提を1件も閉じなくても動くものが、すぐ上に1つ印字されています** ——
                # **配分**です（`_planned_lines`）。上の日付は「過去にどう振ってきたか」で
                # 解かれていて、これから閉じるのは**台帳に開いている分だけ**なので、
                # 2つが食い違っているぶん、日付はそのまま後ろへずれます。
                # **台帳は書き換えられます。閉じるのを待つ必要がありません。**
                #
                # 実測 2026-08-26（同じ回に実際にやった。API 0単位）::
                #
                #     過去の配分   2026-12-28      台帳のまま   2027-01-19（+22日）
                #     `lever: rpm` の開いた前提5件のうち**2件が RPM を測っていなかった**
                #     （「長尺の生成が落ちる主因」「長尺は1日4本 作れる」＝ どちらも本数）
                #     → `density` へ直して            2027-01-07（+10日）＝ **12日**
                #
                # **この回に閉じられる前提は0件でした。** それでも 12日 動いています。
                # 古い行はその手を**名指しで打ち消していました** ——
                # 実測で、到達日が動きえない回は 146/211（69%）・直近20回の
                # `verdict` は 0件。**読んだ側は正しく読んで、正しく手を止めています。**
                #
                # **覆る条件**: 配分の差が1日 未満になったら、この分岐は
                # 古い文面（「どんな作業をしても動きません」）に戻して構いません。
                # そのときは本当に動かせるものがありません。
                pln = (tr or {}).get("planned")
                gap = None
                if pln is not None and base is not None:
                    if pln["days"] < NEVER and base.get("days", NEVER) < NEVER:
                        gap = pln["days"] - base["days"]
                head = (f"{bar} **この回に閉じられる前提はありません** ——"
                        f" いちばん早い期日は **{nc['on'].isoformat()}**"
                        f"（{nc['days']}日後・開いている前提 {nc['open']}件）。")
                if gap is not None and abs(gap) >= 1:
                    # **「付け札を照合しろ」は、もう既定にしません**（2026-08-27 に直した）。
                    #
                    # ここは長らく無条件に「**付け札が実際に測っているものと
                    # 合っているかを、先に見ること** —— 2026-08-26 は、それだけで
                    # 12日 動きました」と印字していました。**その掃除は終わっています** ——
                    # `docs/JOURNAL.md` に2回、**開いた15件／21件を1件ずつ当たって
                    # 付け替え0件**と記録があります（2026-08-26 の最適化の回）。
                    #
                    # **頭の3行しか読まない手順では、この文が「次の一手」に見えます。**
                    # 実測 2026-08-27 07:5x のサブは、この行に従って
                    # `config/hypotheses.yaml` の開いた19件を並べ直し、
                    # **JOURNAL に「一巡ずみ・0件」と書いてあるのを見つけて捨てました**
                    # （約8分）。`retro.py` の持ち越しに `eta.py` が3回 並んでいるのも
                    # 同じ形です。**閉じた仕事を、道具が毎回 名指ししていました。**
                    #
                    # 空欄（`unassigned`）は**機械で数えられる**ので、そこだけ残します。
                    # 空欄は `arm_speed.closed()` から丸ごと落ち、θ にも入りません。
                    #
                    # **覆る条件**: `unassigned` が0のままでも付け替えが要る回が来たら、
                    # それは「意味の照合」であって空欄の話ではありません。そのときは
                    # 台帳側に「いつ照合したか」の欄を作ること（いまは日誌にしかない）。
                    unfilled = int((pln.get("planned") or {}).get("unassigned") or 0)
                    if unfilled:
                        tail = (" **`lever` の空欄が {n}件 あります。先にそこを"
                                "埋めること** —— 空欄の前提は `arm_speed.closed()` から"
                                "丸ごと落ち、θ にも配分にも入りません"
                                ).format(n=unfilled)
                    else:
                        tail = ("（**付け札の照合は一巡ずみです**: 空欄0件・"
                                "2026-08-26 に開いた21件を1件ずつ当たって付け替え0件。"
                                "**数え直さないこと** —— 見るのは、そのあとに"
                                "足した前提だけ。`docs/JOURNAL.md` 2026-08-26）")
                    out.append(
                        head + "**ただし『何をしても動かない』ではありません** ——"
                        f" **配分は、1件も閉じずに動きます**（いま **{gap:+,.0f}日**"
                        " ぶん、台帳は上の日付が前提にしていない振り方をしています）。"
                        " **次の1件をどの腕に立てるかを選ぶこと**"
                        "（`config/hypotheses.yaml` の `lever`。"
                        "どの腕が早いかは `python scripts/eta.py --alloc`）。" + tail)
                else:
                    out.append(
                        head + "**そして配分の差も1日 未満です** ——"
                        " この回は本当に上の日付が動きません（`--moves 0` が正しい回です）")
            else:
                out.append(
                    f"{bar} **期日の来た前提があります**"
                    f"（{nc['on'].isoformat()}・開いている前提 {nc['open']}件）→"
                    " **この回は `verdict` で日付が動かせます**")
    # **腕の名前だけで終わらせない。** その腕を引いたら日付が何日動くかを、
    # 同じ3行の中に出します（オーナー指示 2026-08-20 16:0x「分析して制作に
    # 活かして視聴回数などを上げることが予測に使えることじゃない？」）。
    ld = pl.get("lever_days") or []
    top = [r for r in ld if r["reachable"]][:2]
    if top:
        f = top[0]["factor"]
        out.append(f"{bar} **{f:.0f}倍にしたら:** "
                   + " ／ ".join(
                       f"`{r['lever']}` → **{r['date'].isoformat()}**"
                       + (f"（**{pl['days_to_target'] - r['days']:,.0f}日 早まる**）"
                          if pl["days_to_target"] < NEVER
                          else "（いまは日付が出ません → **出ます**）")
                       for r in top))
    how = _how_to_pull(pl)
    if how:
        out.append(f"{bar} {how}")
    prev_date = None
    # **比べるのは同じ物差しどうし。** 軌跡が出ている回は軌跡の日付と、
    # 出ていない回は据え置きの日付と比べます（混ぜると「1日で200日早まった」が出ます）。
    key = "traj_date" if (base is not None and prev and prev.get("traj_date")) else "target_date"
    cur_date = base["date"] if (key == "traj_date" and base is not None) else pl["target_date"]
    if prev and prev.get(key):
        try:
            prev_date = date.fromisoformat(str(prev[key]))
        except ValueError:
            prev_date = None
    if prev_date and cur_date:
        delta = (cur_date - prev_date).days
        mark = ("**早まりました**" if delta < 0
                else "動いていません" if delta == 0 else "**遠のきました**")
        out.append(f"{bar} 前の回の予測 {prev_date.isoformat()} → **{delta:+d}日** {mark}"
                   + ("（軌跡どうし）" if key == "traj_date" else "（据え置きの線どうし）"))
    elif prev_date and cur_date is None:
        out.append(f"{bar} 前の回は {prev_date.isoformat()} → **今回は日付が出ません**"
                   "（前提が変わったか、実測が落ちた）")
    # **1歩ぶんの差だけを出さないこと**（2026-08-29・最適化の回）。
    #
    # すぐ上の行は「前の回 → いま」で、実測 2026-08-28 は **+3日**。
    # **同じ台帳を 7日 足すと +33日** です（`traj_trend()` の docstring に実測）。
    # 1周ごとの差は −9〜+15日 で振れるので、**向きは1歩では出ません。**
    # そして頭と尾しか読まれない以上、ここに出さないと誰も足しません。
    # **`now` を渡すこと**（2026-08-29 に踏んだ）。渡さないと `traj_trend` は
    # 実時刻を読むので、**検査は壁時計が進んだ日に、黙って赤くなります** ——
    # `tests/test_eta_trend_line.py::test_累計の行が読まれる3行に出る` は
    # 08/28 に書かれ、08/29 に落ちました（点は 08/28 基準・窓は 7日）。
    # **中身は何も壊れていないのに、恒久的に赤い検査が1つ増える形**です
    # （`docs/JOURNAL.md` 2026-08-28 06:3x「恒久的に赤い検査を1つ置くと、
    #   同じファイルの本物の警報が読まれなくなります」）。
    tre = traj_trend(points or [], cur_date if key == "traj_date" else None, now=now)
    if tre and abs(tre["delta"]) >= 1:
        d = tre["delta"]
        mk = "**遠のきました**" if d > 0 else "**早まりました**"
        ships = ships_in_window()
        why = _trend_why(tre)
        base = (f"（起点は {tre['from_at']:%m/%d} の**中央値**"
                f"・その日 {tre.get('n_base', 0)}点"
                + (f"・**同じ日の幅 {tre['base_spread']}日**"
                   if tre.get("base_spread") else "")
                + f"／窓の中 {tre['n']}点）")
        out.append(
            f"{bar} **{tre['span_days']:.0f}日の累計**: "
            f"{tre['from_date'].isoformat()} → {tre['to_date'].isoformat()} = "
            f"**{d:+d}日** {mk}"
            + (f"（このあいだ ship **{ships}件**）" if ships else "")
            + "。**1周ごとの ±N日 では、この向きは見えません** " + base
            + (f"　{why}" if why else ""))
    # **物差しを取り替えた回は、その差を「遠のいた」と読ませない**（`_scale_note` と同じ形）。
    #     密度の入力が「1日25本という前提」から「作る速さの実測」に替わった回は、
    #     チャンネルは何も変わっていないのに日付が大きく動きます。
    if prev is not None and prev.get("make_rate_per_day") is None \
            and (pl.get("gate1") or {}).get("measured"):
        out.append(f"{bar} [!] **この回から、密度の入力が変わりました**"
                   f"（「1日{pl['density']:.0f}本」という前提 → "
                   f"**作る速さ {pl['gate1']['rate_per_day']:.1f}本/日 の実測**）。"
                   "**上の差は実績ではありません。**")

    elif prev and prev.get(key) is None and cur_date:
        out.append(f"{bar} 前の回は日付が出ていませんでした → **道が開きました**")
    elif prev_date is None:
        # **「前の点が無い」と言えるのは、本当に無いときだけ**（2026-08-29 に直した）。
        #
        # ここは長らく `else:` でした。上の `if` は
        # 「**密度の入力が入れ替わった回か**」を訊いており、**前の点の有無とは
        # 別の問い**です。だから前の点が在っても、入れ替えが無ければ `else` に落ち、
        #
        #     ### 前の回の予測 2027-01-09 → **+3日** **遠のきました**（軌跡どうし）
        #     ### （比べられる前の点がまだありません）
        #
        # が**同じ枠に並んで**出ていました（実測 2026-08-28 の回。**頭と尾の両方**）。
        # 読んだ回は、下の行を信じれば上の +3日 を捨てます。
        # `docs/JOURNAL.md` 2026-08-28「**枠の2行が食い違っていないか**」の型そのもの。
        out.append(f"{bar} （比べられる前の点がまだありません）")
    out.append("=" * 66)
    return out


def _report_plan(m: dict, a: dict, pl: dict | None = None) -> list[str]:
    """**この節を、いちばん最後に出すこと**（`main()` が `_drift` / `levers` の後に呼ぶ）。

    ここより後ろに「届きません」を置かないこと —— 読み手が最後に見るものが
    そのまま次の回の入口になります（オーナー指示 2026-08-20 06:2x）。
    """
    out: list[str] = []
    P = out.append
    pl = pl or plan(m, a, supply=supply_state(), sensitivity=True)
    d = pl["density"]

    P("")
    P("=" * 66)
    P("=== **月20万に到達するまでの段取り**（予測を「届きません」で終わらせない）===")
    P("=" * 66)
    g1 = pl.get("gate1") or {}
    if g1.get("measured"):
        P(f"  **密度は実測から解いています: 1日続けられる速さ {g1['rate_per_day']:.1f}本"
          f"（在庫 {g1['stock']}本）／詰め方の上限 {d:.0f}本/日**")
        if g1.get("density_basis"):
            P(f"     出どころ: **{g1['density_basis']}**")
        # **バーストを持続と読み替えていないか、画面に出す**（2026-08-20 20:0x）。
        #     3.3時間の窓の 36.5本/日 が `min(25, 36.5) = 25` を通って
        #     `density_month` に入り、**外させたはずの 25 が戻っていました。**
        burst = g1.get("rate_burst")
        if burst is not None and g1["rate_per_day"] < burst - 1e-9:
            P(f"     [!] **直近の作る速さ {burst:.1f}本/日 は使っていません**"
              f"（窓 {((pl.get('supply') or {}).get('rate') or {}).get('hours', 0.0):.1f}時間"
              f" < {supply_min_sustained_hours():.0f}時間 ＝ **1日続く速さとは言えない**）。"
              "24時間をまたぐ点が貯まれば、自動でそちらに切り替わります")
        P(f"  → **段4（月20万）が乗るのは、持続する {pl['density_month']:.1f}本/日 のほう**"
          "（収益の30日は在庫を食い終わった先にあります）")
        if g1.get("dry_days") is not None:
            P(f"  → 掃引の材料は **{g1['dry_days']:.0f}日**で尽きます"
              "（その先は `src/calc/` に**新しい表**が要る）")
        basis = ((pl.get("supply") or {}).get("rate") or {}).get("basis")
        if basis:
            P(f"     （作る速さの出どころ: **{basis}**。"
              "**2つの物差しは混ぜていません** —— 実測で 20本ちがいました）")
        if g1.get("thin"):
            P("  [!] **作る速さの窓が 6時間 未満です**（1本の増減で桁が動く帯）。"
              "`python -m src.supply --record` を毎周ぶん積むと締まります")
    else:
        P(f"  [!] **密度は未検証の前提です: 1日 {d:.0f}本**"
          "（`src/supply.py` が読めませんでした。**作れる本数ではありません**）")
    P("     （92本は API の日枠であって、出せる本数ではありません）")
    P(f"  **物差しはショートの実測 {a['per_video_now']:,.0f}回/本**"
      "（この機械が持つ唯一の当てになる1本あたり）")
    P("")
    P("--- どの形で取りに行くか（**その形のいちばん低い RPM で比べる**）---")
    sf = pl.get("surface") or {}
    if sf.get("rpm_cap"):
        P(f"    **帯（¥400 など）は「再生の100%がその形」のときの数です。**"
          f" いまの混ざり方の天井は **¥{sf['rpm_cap']:,.0f}**（実測）")
        P(f"      長尺の面 {sf['long_views_day_cap']:,.1f}回/日（実測）× CTR100% までしか"
          "長尺の再生は増えません。**帯をそのまま当てると合格点が甘くなります**")
    else:
        P("    [!] **面（長尺のインプレッション）が測れていません。**"
          " 帯をそのまま当てています（`python -m src.rpm_mix --record`）")
    for form, f in pl["forms"].items():
        mark = " ← **これで立てる**" if form == pl["spine"] else ""
        cap = "  ← **帯 ¥{:,.0f} を、実測の混ざり方の天井で頭打ち**".format(f["rpm_band"]) \
            if f.get("capped") else ""
        P(f"    {form:<8} RPM ¥{f['rpm']:>5,.0f}  月 {f['views_needed_month']:>10,.0f}回 要る"
          f"  → 1本あたり **{f['per_video_needed']:>7,.0f}回**"
          f"（ショート実測の {f['ratio_vs_shorts']:>5.2f}倍）{mark}{cap}")
    P("")
    P("--- 段取り（**最後の段に日付が入るまでが1つの予測**）---")
    for st in pl["stages"]:
        P(f"    段{st['no']}［腕 {st['lever']}］{st['title']}")
        P(f"        期日: {_fmt_days(st['when'])}")
        P(f"        合格点: {st['bar']}")
        if st.get("note"):
            P(f"        [!] {st['note']}")
    P("")
    tg = pl["target"]
    P(f"  → 月20万の到達見込み: {_fmt_days(pl['days_to_target'])}")
    P(f"     （{pl['spine_band']}・1日{d}本・審査{MONETIZE_REVIEW_DAYS}日を置いた線）")
    P(f"     内訳（**いちばん遅いものが到達日**）:")
    P(f"       (a) 直近30日の再生が、月に要る回数に達する日 …… {_fmt_days(pl['days_revenue'])}")
    P(f"       (b) その30日がまるごと収益化の後にある日 …… {_fmt_days(tg['gate_floor'])}"
      f"（収益化 {_fmt_days(pl['days_monetized'])} ＋ {REVENUE_WINDOW_DAYS}日）")
    if tg["verify_floor"]:
        P(f"       (c) 合格点の倍率を確かめ終えている日 …… {_fmt_days(tg['verify_floor'])}"
          f"（確認 {tg['verify_on'].isoformat()} ＋ {REVENUE_WINDOW_DAYS}日）")
    P(f"     **縛っているのは {pl['binding']}**"
      f" → **この回に引く腕は `{pl['lever_hint']}`**"
      "（ここを動かさない作業は、上の日付を1日も動かしません）")
    gr = pl["growth"]
    if gr.get("g") is not None:
        P(f"     伸び率 **{gr['g'] * 100:+.2f}%／日**"
          f"（{double_days(gr['g']):,.0f}日で2倍）… {gr['basis']}")
    else:
        P(f"     伸び率: {gr['basis']}")
    if gr.get("caveat"):
        P(f"       断り: {gr['caveat']}")
    # **測った窓と、延ばしている先の比を出す**（2026-08-20 20:0x）。
    #     水準を決めているのは天井のほうなので、ここに時間の頭打ちは入れません
    #     （`solve_revenue_day` の註）。**ただし、何倍先まで延ばしているかは見せる。**
    span = gr.get("span_days") or 0.0
    if span > 0 and tg.get("d_revenue", NEVER) < NEVER:
        P(f"       **{span:.1f}日ぶんの窓で測った伸びを、{tg['d_revenue']:,.0f}日先"
          f"（{tg['d_revenue'] / span:,.1f}倍）まで延ばしています。**"
          f" 水準の頭打ちは天井（1日 {pl['ceiling_day']:,.0f}回 ＝"
          f" 密度 {pl['density_month']:.1f}本 × {a['per_video_now']:,.0f}回）のほうです")
    gn, gnow = pl.get("growth_needed_by_gate"), (gr.get("g") or 0.0)
    if gn is not None:
        room = (gnow / gn) if gn > 0 else float("inf")
        P(f"     **(b)(c) の床（{_fmt_days(tg['floor'])}）までに (a) を満たすのに要る伸び:"
          f" {gn * 100:+.2f}%／日**"
          f" ／ 実測 {gnow * 100:+.2f}%／日"
          + (f" → **足りています（{room:,.1f}倍の余裕）**" if gnow >= gn
             else f" → **足りません（{gn / gnow:,.1f}倍 要る）**" if gnow > 0
             else " → **伸びていません**"))
        P("       ← **結論はこの1行に乗っています。** 伸びが落ちれば、"
          "到達日を縛るのは門と窓ではなく再生数 (a) のほうに移ります。")
    if pl["ceiling_day_long"] > 0:
        P(f"     **長尺の実測（{pl['ceiling_day_long'] / d:,.0f}回/本）をそのまま当てた側**: "
          f"再生数 {_fmt_days(pl['days_revenue_long'])}")
        P("       ← 上の線はショートの実測を長尺に当てています。"
          "**この2つの幅が、まだ測っていないぶんです**（下の1行）。")
    P("")
    P("--- **何を何倍にすれば、いつ届くか**（予測を「届きません」で終わらせない）---")
    for h in pl["horizons"]:
        if h["reachable"]:
            P(f"    {h['date']}（{h['days']:>3}日後）まで … 1日あたり **{h['growth'] * 100:+.2f}%** の伸び"
              f"（{h['double_days']:,.0f}日で2倍）")
        else:
            P(f"    {h['date']}（{h['days']:>3}日後）まで … **伸び率をいくら上げても届きません**")
    if pl["ceiling_short"] > 1:
        P(f"    → **天井が {pl['ceiling_short']:,.2f}倍 足りません。待っても届きません。**")
        # **「いま ¥400」と印字していました。** 帯をそのまま出していたので、
        #     実測の混ざり方で頭打ちになった後も、画面は帯のままでした。
        P(f"       1本あたり再生（いま {pl['ceiling_day'] / d:,.0f}回）か RPM（いま ¥{sf.get('rpm_plan', 0):,.0f}）"
          f"か 密度（いま {d}本/日）を、掛けて {pl['ceiling_short']:,.2f}倍 にすること")
        # --- **その天井を、面（長尺のインプレッション）で埋めるなら何回/日 要るか** ---
        #     「届きません」で畳まないための逆算です（オーナー指示 2026-08-20 06:2x）。
        #     RPM を上げる道はこの機械では1つしかありません ——
        #     **長尺の再生の割合を上げること**で、その割合の上限は面が決めます。
        need_sf = pl.get("surface_needed") or {}
        if need_sf.get("impossible"):
            P(f"       [!] **面だけでは埋まりません。** 再生の 100% を長尺にして"
              f"（RPM ¥{need_sf['rpm_long']:,.0f}）も 実効 ¥{need_sf['rpm_at_full']:,.0f} "
              f"＝ 要る ¥{need_sf['rpm_needed']:,.0f} に **{need_sf['still_short']:,.2f}倍 足りません**。"
              "**1本あたり再生か密度も、同時に動かすこと**")
        elif need_sf.get("imp_day_needed"):
            P(f"       **面で埋めるなら: 長尺のインプレッション {need_sf['imp_day_now']:,.1f}回/日 → "
              f"{need_sf['imp_day_needed']:,.0f}回/日（×{need_sf['imp_factor']:,.1f}）**"
              f"（長尺が再生の {need_sf['share_needed'] * 100:.1f}% になる面。実効 RPM ¥{need_sf['rpm_needed']:,.0f}）")
    else:
        P(f"    （天井は足りています: 1日 {pl['ceiling_day']:,.0f}回 × 30日 ＝ 月 {pl['ceiling_day'] * 30:,.0f}回"
          f" ≧ 要る {pl['need_month']:,.0f}回）")
    P("")
    P("--- **その日付は、どこから出ているか**（20万以外の日付で代用しない）---")
    P(f"    合格点 : 1本あたり **{tg['need_per_video']:,.0f}回**"
      f"（いまの物差し {tg['per_video_now']:,.0f}回 の **{tg['ratio']:.2f}倍**）")
    if tg["fallback"]:
        f = tg["fallback"]
        P(f"    [!] {f['why']}。**倍率では出ません**（0を何倍しても0）。")
        P(f"        {f['assume']} → 門1 {_fmt_days(f['gate1_days'])}")
    if tg["met"]:
        P(f"    ① 合格点は**いまの実測で立っています**（{tg['ratio']:.2f}倍 ≤ 1.00）"
          f" → 立つ日は収益化と同じ {_fmt_days(tg['bar_day'])}")
    else:
        if tg["proxy"]:
            P(f"    ① 合格点は**まだ立っていません**。倍率は ×{tg['ratio']:.2f} ですが、"
              "**割っているのはショートの実測**です。")
            P(f"        段4 が立てているのは長尺で、そこは測っていません"
              f"（{pl['blocking']['now']}）。**別の形の実測を当てているあいだ、"
              "合格点は推測です。**")
        else:
            P(f"    ① 合格点は**まだ立っていません**。要るのは"
              f" **1本あたり ×{tg['ratio']:.2f}**。")
        P(f"        それが本当かを確かめられる最短が"
          f" **{tg['verify_on'].isoformat()}**（{tg['verify_day']:.0f}日後"
          "。公開の翌日 → 伸びきる48時間 → Analytics 3日遅れ）")
        P(f"        → 合格点が立つ日 {_fmt_days(tg['bar_day'])}")
    P(f"    ② その水準で **{tg['window']}日ぶん積んだ合計**が、"
      "**まるごと収益化の後**にあること"
      "（収益化前の再生は1円も生まないので、この30日は前借りできません）")
    P(f"       → 床は {_fmt_days(tg['floor'])}")
    P(f"    ①と②の遅いほう ＝ {_fmt_days(pl['days_to_target'])}")
    P("      （①は伸び率で解いた日なので、**倍率が上がればここが後ろへ動きます**。"
      "**②に①を足さないこと** —— ①は直近30日の合計で見ているので、"
      "足すと1か月ぶん二重に数えます）")
    if tg["conditional"]:
        P("    [!] **これは「見込み」ではなく「最早」です。**"
          " 上の倍率が出なければ、この日は来ません（出た日に引き直すこと）。")
    P("")
    b = pl["blocking"]
    # **見出しを「測っていない」で固定しないこと**（2026-08-25）。
    # 値が出ている回に「測っていない」と書くと、**もう答えの返る測定に
    # 1回ぶんの ship が使われます**（`LONG_SAMPLE_MIN` の註）。
    if b.get("measured"):
        P("--- **この段取りを止めているのは、値ではなく「標本の薄さ」です** ---")
    else:
        P("--- **この段取りを止めている、まだ測っていない入力は1つです** ---")
    P(f"    {b['what']}")
    P(f"      いま: {b['now']}")
    P(f"      要る: {b['need']}")
    P(f"      測り方: {b['how']}")
    P(f"      なぜここか: {b['why']}")
    fc = b.get("sample")
    if fc:
        P("")
        P("      **予約済みの長尺だけで、その標本は埋まるか**"
          "（**最早**。0再生の本は標本に入らないので、実際はこれより遅い）:")
        P(f"        まだ読めていない長尺の予約 **{len(fc['booked'])}本**"
          f"／要る {fc['need']}本")
        if fc["reaches"]:
            P(f"        → **{fc['reaches']} に n≥{LONG_SAMPLE_MIN} に届きます"
              "（この回に長尺を足さなくても届く）**")
            P("        [!] **この測定に ship を使わないこと。**"
              " 予約済みの本が答えを返します。**別の腕を引くこと。**")
        else:
            P(f"        → 予約だけでは **{fc['short_by']}本 足りません**"
              "（この回に足すぶんが、そのまま前倒しになります）")
    t = b.get("targets")
    # **計算したものを黙って落とさないこと**（この repo の「片方だけ」＝通算9件）。
    # 予約で届く回は、的の日付を**1行に畳んで**「要りません」と添えます ——
    # 消すと道具が黙り、そのまま出すと**要らない測定に ship が使われます。**
    if t and fc and fc.get("reaches"):
        P(f"        （前倒ししたい場合の的: **{t['soonest']}** に置けば"
          f" {t['answer_soonest']} に読める。**この回は要りません** —— 上の予約で届きます）")
    if t and not (fc and fc.get("reaches")):
        P("")
        P("      **いつ答えが返るか**（公開 → 伸びきる 48時間 → Analytics 3日遅れ）:")
        P(f"        いちばん早く予約できる日 **{t['soonest']}** に置く"
          f" → 読めるのは **{t['answer_soonest']}**")
        if t["hole"]:
            P(f"        いちばん近い「予約0本の日」 {t['hole']} に置く"
              f" → 読めるのは {t['answer_hole']}"
              f"（**{t['days_lost']}日 遅い**）")
            if t["days_lost"] > 0:
                P("        [!] **穴埋めと測定を同じ `--date` で兼ねないこと。**"
                  " 穴はいつ埋めても同じですが、")
                P(f"            測定は遅らせたぶんだけ段取り全体が遅れます"
                  f"（この差が **{t['days_lost']}日**）。")
                P("            **穴は別の回に、ショートで埋めること。**")
        else:
            P("        予約0本の日はありません（穴埋めと測定が競合しません）")
    P("")
    out.extend(_report_supply(pl))
    P("")
    if pl["lever_hint"] == "density":
        P(f"  **この回の一手は、門を開ける側（`{pl['lever_hint']}` / `sub_rate`）です** ——"
          " 到達日を縛っているのは収益化の門と、その後の30日のほうで、")
        P("  再生数 (a) はそれより先に満たせる見込みだからです。"
          "**ただし段2 の合格点は上の1行が未測定のまま**なので、")
        P("  **同じ回で測定の的を撃てるなら撃つこと**（穴埋めとは別の日に）。")
    else:
        P(f"  **この回の一手は、`{pl['lever_hint']}` を動かすことです** ——"
          " 到達日を縛っているのは再生数（段4）のほうで、")
        P("  門をいくら早く開けても、20万に届く日は動きません。"
          "**上の1行の測定が、その倍率を確定させます。**")
    return out


def _report_levers(pl: dict) -> list[str]:
    """**腕べつに、到達日が何日動くか**（2026-08-20 16:0x・オーナー指示）。

    > 分析して制作に活かして視聴回数などを上げることが予測に使えることじゃない？

    **使えていませんでした。** 到達日を決めていたのは「1日25本」と「審査30日」で、
    1本あたり再生は**天井の表に出てくるだけ**。上げても下げても日付は動かず、
    それでいて `lever_hint` は毎回 `density` を名指ししていました。
    **動かない数字に向かって「早めろ」と言われていた**わけです。

    ここが出すのは、腕を1つずつ解き直した**到達日の差**です。**2つの倍率で出します**:

        ×N（同じ倍率）    腕の**感度**を並べる。どれが効きやすいか
        天井まで          その腕が**実際に引けるところまで**引いた線。**選ぶのはこちら**

    **同じ倍率だけで選ぶと、答えが「出ません」に固定されます**（2026-08-25 に判明）。
    合格点が ×2 より上にある回は、**どの腕を ×2 にしても届かない**ので4本とも
    同点 0 になり、`plan()` の上書きは 8/20 から一度も走っていませんでした。
    天井は腕ごとに ×1.00〜×2,923 と3桁ちがいます。**その差を含めないと選べません。**
    """
    rows = pl.get("lever_days") or []
    if not rows:
        return []
    base = pl.get("days_to_target", NEVER)
    out = ["", "--- **腕べつに、到達日が何日動くか**"
           f"（**×{rows[0]['factor']:.0f}（感度）** と **天井まで（実力）** の2本）---"]
    P = out.append
    if base < NEVER:
        P(f"    いまの実測のまま        {_fmt_days(base)}")
    else:
        P("    いまの実測のまま        **日付が出ません**（天井が足りない）")
    for r in rows:
        # --- ×N の側（感度）---
        if r["reachable"]:
            g = (f"**{base - r['days']:,.0f}日 早まる**" if base < NEVER
                 else "**日付が出るようになる**")
            sens = f"{r['date'].isoformat()}（{r['days']:,.0f}日後）  {g}"
        else:
            sens = "**それでも出ません**"
        P(f"    `{r['lever']:<10}` ×{r['factor']:.0f}   {sens}   {r['label']}")

        # --- 天井の側（実力）---
        cap = r.get("cap")
        if cap is None:
            P("                 天井 —— **測れていません**（この腕は実力で選べません）")
        elif r.get("at_ceiling"):
            P(f"                 天井 ×{cap:,.2f} …… **引き代なし。"
              f"この腕は何をしても上の日付を1日も動かしません**")
        elif r.get("reachable_at_cap"):
            g2 = (f"**{base - r['days_at_cap']:,.0f}日 早まる**" if base < NEVER
                  else "**日付が出る**")
            th = r.get("threshold")
            th_s = (f"／日付が出はじめるのは **×{th:,.2f}** から" if th else "")
            P(f"                 天井 ×{cap:,.2f} → "
              f"{r['date_at_cap'].isoformat()}（{r['days_at_cap']:,.0f}日後）  {g2}{th_s}")
        else:
            P(f"                 天井 ×{cap:,.2f} → **天井まで引いても出ません**"
              f"（この腕は、いまの縛りに触っていません）")

    if pl.get("lever_measured"):
        P(f"    → **この回に引く腕は `{pl['lever_measured']}`。**"
          f" 床の名前（{pl.get('lever_hint_binding')}）ではなく、"
          f"**天井まで引いたときの差の大きさで選んでいます**")
    dead = [r["lever"] for r in rows
            if r.get("cap") is not None and not r.get("reachable_at_cap")]
    if dead:
        # **ここには長らく「ここに前提を置いても、到達日は動きません」と
        #     書いてありました。偽です**（2026-08-26・最適化の回に消した）。
        #     同じプログラムの `--alloc` が、同じ日・同じ点で
        #     「**いちばん早いのは `sub_rate`**（そのままより 3日 早い）。
        #     立てるときは `hypotheses.yaml` に `lever:` をその腕で書くこと」
        #     と出していました。**「置いても動かない」と「次はここに置け」**です。
        #     上の表は**他の3本を今日の実測で凍らせた**モデルで、
        #     `CLAUDE.md` が「凍らせた企画についての恒真式」と名指ししている側。
        #     **十分でないことは、要らないことではありません。**
        frz = pl.get("arm_frozen_days") or {}
        P(f"    **この腕**だけ**を天井まで引いても届かない腕: "
          f"{'／'.join(f'`{d}`' for d in dead)}**"
          " —— 言っているのは**十分でない**ことだけです。"
          "**「ここに前提を置いても動かない」ではありません**"
          "（門1 など、別の段には効きます）。")
        for d in dead:
            v = frz.get(d)
            if v is None:
                P(f"      `{d:<10}` 凍らせた線が出ていません"
                  "（`--no-frozen` か、軌跡が解けなかった回）。"
                  " **『要らない』と読まないこと。**")
            elif v > 0.5:
                P(f"      `{d:<10}` **この腕を凍らせると軌跡は {v:+,.0f}日**"
                  "（回転はよその腕へ配り直したうえで）→ **必要な腕です。**"
                  " 次の1件をどの腕に立てるかは `python scripts/eta.py --alloc`")
            else:
                P(f"      `{d:<10}` 凍らせても軌跡は {v:+,.0f}日 ＝"
                  " **回転をよそへ回しても同じ。この腕は要りません。**")
    P("    **「その倍率にできる」とは言っていません。** 言っているのは"
      "「そこまで引けたら何日縮むか」だけで、**引けるかどうかは別の話**です。")
    return out


def _report_trajectory(tr: dict, pl: dict) -> list[str]:
    """**腕が動く速さを含んだ、1本の軌跡**（2026-08-20 18:xx・オーナー指示）。

    > 特定条件の予測じゃなくて、実際にどういう軌跡を辿るか予測して、
    > いつ達成かを予測するんだよ。

    上の `_report_levers` は「×2 にしたら」の表です。**そこには
    「×2 に何日かかるか」が1行もありません** —— 満たせるか分からない前提の上に
    日付が乗る形で、同じ回に外したばかりの「1日25本」とまったく同じ欠陥でした。

    ここが出すのは**時間の関数としての腕**です。倍率は実測の速さで伸び、
    実測の天井で止まります。**表ではなく、1つの日付**にすること。
    """
    base, bd, st = tr["base"], tr["band"], tr["streak"]
    out = ["", "=" * 66,
           "=== **軌跡**（腕が「実測の速さ」で動いていった場合。条件つきの表ではありません）===",
           "=" * 66]
    P = out.append
    for line in arm_speed.lines(tr["arms"], st, bd, tr.get("unread", 0)):
        P(line)
    for line in cap_lines(tr["arms"]):
        P(line)

    P("")
    if base["date"] is not None:
        P(f"  → **軌跡の到達日: {base['date'].isoformat()}**"
          f"（{math.ceil(base['days']):,}日後）")
        P(f"     内訳: **腕を {base['t_work']}日ぶん動かして**"
          f"（そのとき "
          + " ／ ".join(f"`{k}` ×{v:,.2f}" for k, v in (base["factors"] or {}).items())
          + f"）、そこから {base['plan_days']:,.0f}日 で届く")
        P(f"     そのとき縛っているのは **{base['binding']}**")
        # **軌跡が実際に歩いた腕の天井が、測った数かどうかをここで言う**（2026-08-28）。
        #     下の `_report_trajectory` の末尾には同じ趣旨の `[!]` が既にありますが、
        #     見ているのは **`choice` の1位（＝この回に振る腕）だけ**です。
        #     `sub_rate` は「全部振っても出ません」なので1位に**なりません** ——
        #     ところが軌跡はその腕を **×10.36** まで歩いていました
        #     （天井が「登録率 100%」＝ ×3,153.91 だったので、何倍でも下に入る）。
        #     **1位でない腕は、誰も測っていないまま日付を押していた**わけです。
        #     だから見る対象を「振る腕」から**「実際に歩いた腕」**に変えます。
        #     2026-08-28 に `sub_rate` を実測へ替えて 4本とも measured になりましたが、
        #     **同じ形は次の腕を足したときに必ず戻ります**（`physical_caps` の
        #     既定は「定義上の上限」に落ちる形なので、静かに再発します）。
        for _k, _v in sorted((base["factors"] or {}).items(),
                             key=lambda kv: -kv[1]):
            _a = (tr["arms"] or {}).get(_k) or {}
            if _v > 1.05 and _a.get("cap") and not _a.get("cap_measured"):
                P(f"     [!] **この内訳の `{_k}` ×{_v:,.2f} は、測っていない天井の上を歩いています**"
                  f"（天井 ×{_a['cap']:,.2f} …… {_a.get('cap_why', '出どころなし')}）。"
                  " **上の日付は、その倍率が実在するという前提の上に乗っています** ——"
                  "測れば動きます（`per_video` の天井は実測の最大です。同じ物差しを当てること）")
    else:
        P("  → **軌跡でも到達日が出ません。** 塞いでいるのは次のものです:")
        for why in base["blocking"]:
            P(f"       - {why}")

    if tr["fast"] and tr["slow"]:
        def _d(x):
            return x["date"].isoformat() if x["date"] else "出ません"
        P(f"     幅（当たる確率 {bd['k']}件/{bd['n']}件 の 90% 区間"
          f" {bd['lo']:.0%}〜{bd['hi']:.0%}）: "
          f"**早い {_d(tr['fast'])} ／ 遅い {_d(tr['slow'])}**")
        P("       **遅いほうが「外れ続けた場合」です。** いまの連敗を確率の更新に使うより、"
          "標本15件ぶんの幅で読むほうが素直です")
    if st["n"]:
        P(f"     いま **{st['n']}連続で外れ**。当たりの間隔の実測は "
          f"{st['expected_gap']:.1f}件 なので "
          + ("**外れすぎです**（速さの前提そのものを疑うこと）" if st["unusual"]
             else "**まだ範囲の中**（「次は当たる」でも「もう当たらない」でもありません）"))

    P("")
    P("--- **この回の回転を、どの腕に振るのがいちばん早いか**"
      "（回転は1本しかありません。4本とも全力の線は実在しません）---")
    for r in tr["choice"]:
        if not r["reachable"]:
            P(f"    `{r['lever']:<10}` **全部振っても出ません**")
            continue
        gain = ((base["days"] - r["days"]) if base["days"] < NEVER else None)
        note = (f"**{gain:,.0f}日 早い**" if gain and gain > 0
                else "**軌跡より遅い**" if gain is not None and gain < 0
                else "**日付が出るようになる**")
        P(f"    `{r['lever']:<10}` → {r['date'].isoformat()}"
          f"（腕を {r['t_work']}日 動かして 計 {math.ceil(r['days']):,}日）  {note}")
    top = next((r for r in tr["choice"] if r["reachable"]), None)
    if top:
        a = tr["arms"][top["lever"]]
        P(f"    → **この回に振る腕は `{top['lever']}`。**")
        if a["source"] != "自前":
            P(f"      [!] ただし `{top['lever']}` の速さは **{a['source']}**"
              f"（この腕で閉じた前提は {a['n']}件・当たり {a['hits']}件）。"
              "**この1行が、いま軌跡でいちばん薄い数です**")
        if a.get("cap") and not a.get("cap_measured"):
            P(f"      [!] `{top['lever']}` の天井 ×{a['cap']:,.2f} は"
              "**測った天井ではありません。** **軌跡はここに寄りかかっています** ——"
              " 測れば動きます")
    P("  **これは「腕がその倍率になる」と言っていません。** 言っているのは"
      "「閉じた前提15件の実測の速さで進んだら、そこに着く」だけです。"
      "速さも天井も、**次に閉じる1件で動きます**。")
    return out


def _report_supply(pl: dict) -> list[str]:
    """**その密度を出せるかを、在庫の側から確かめる**（2026-08-20 13:4x に足した）。

    ## なぜ要るか（**この節が無い間、日付は supply を一度も見ていませんでした**）

    `plan()` は `PLAN_PUBLISH_PER_DAY = 25` で段1 を解き、段1 が段3 を、
    段3 が段4 を押します。**到達予測の日付は、まるごとこの 25 の上に乗っています。**
    ところが定数の脇の註は「受け取り帳 3c7e12a3 の**詰め直し**が着地する所」——
    **予約の置き方**であって、**作れる本数ではありません。**

    実測（足した回）: 未投稿の在庫 36本・**未使用の節 0件**・
    `config/topics.yaml` は 08/19 16:34 UTC から **20時間 増えていません**。
    その 20時間に公開のほうは 25本/日 で進んでいます。
    **25本/日 × 157日 ＝ 3,925本** に対し、いま在るもの（在庫＋掃引の候補）は **527本**。

    **「届かない」と言うためではありません。** 出すのは
    **1周あたり何本の節を書けば 25本/日 が保つか**（実測 **1.0本/周**）——
    `density` の腕は、この回では**そこにしか無い**からです
    （投稿の本数枠が閉じている窓では `upload` を選べません。1日16時間前後がそれ）。

    ## **2026-08-20 16:0x に、ここは日付を動かすようになりました**

    足した回のこの註は「**この節は日付を動かしません**（`plan()` の段には
    入れていません）」でした。理由は「supply は人が節を書けば伸びるので、
    床として使うと『書かない未来』を予測として印字する」——
    **理屈は合っていますが、結論が逆でした。** オーナー指示（原文）:

    > 25は物理的に不可ならそれを予測に使うのはどうなの？

    **足りないと分かっている前提を、日付には反映しないまま印字していた**
    わけです。いま `plan()` が入力にしているのは、
    **在庫（＝いま在るもの）と、テーマが増える速さの実測**（`supply.make_rate`）です。

    - **材料（掃引の候補）は壁にしていません。** 壁にすれば、まさに
      「新しい表を1本も書かない未来」を印字することになります。
      材料は**尽きる日**として出すだけ（`material_dry_days`）
    - **速さのほうは実測**です。固定値ではなく、この回が節を書けば上がるので、
      `density` の腕はそこに効きます

    この節が残っているのは、**その密度が在庫の側から見てどう見えるか**を
    並べて読むためです。**日付そのものは `plan()` の `gate1` にあります。**
    """
    from src import supply as supply_mod

    out: list[str] = []
    P = out.append
    days = pl.get("days_to_target")
    horizon = days if isinstance(days, (int, float)) and days < NEVER else None
    try:
        sw = supply_mod.sweep_novel()
        sp = supply_mod.supply(pl["density"], novel=sw["novel"], horizon_days=horizon)
    except Exception as exc:      # 台帳が読めなくても、予測そのものは止めないこと
        return [f"    （在庫の supply は読めませんでした: {exc}）"]
    out.extend(supply_mod.lines(sp))
    g1 = pl.get("gate1") or {}
    if g1.get("measured"):
        P(f"    → **予測が使っているのはこちらです: 作る速さ 1日 {g1['rate_per_day']:.1f}本の実測**"
          f"（段1 は {_fmt_days(g1['days'])}）。**上の 25本/日 は詰め方の上限**です")
    # **作れても、出しても、再生が付く本数には上限があります**（2026-08-21 16:2x）
    out.extend(day_cap.lines())
    if sw.get("age_hours") is not None and sw["age_hours"] > 24:
        P(f"    （掃引の点は {sw['age_hours']:.0f}時間前。測り直しは"
          " `python -m src.supply --measure`。**掃引を回さず速さだけ積むなら**"
          " `python -m src.supply --record`）")
    return out



def _how_to_pull(pl: dict) -> str | None:
    """**腕の名前だけでは足りない。** その腕を、この窓でどう引くかまで書く。

    2026-08-20 14:2x に足した（前の回の宿題。`docs/JOURNAL.md` 問い3）。
    `density` には道が2つあります —— **出す**（`upload`）と **作る**（節を書く）。
    **どちらが今この窓で通るかは、この道具の外**（`upload_cap.state()`）にあり、
    2つの道具を突き合わせて初めて分かる形でした。**その突き合わせが、
    実測で1周の35分**です（8/20 13:1x と 14:1x が続けて同じ所で使っています）。

    `upload_cap.state()` は控えと `data/*.jsonl` だけを読みます（**API 0単位**）。
    読めなかったら黙って何も足しません —— **予測そのものは止めないこと。**
    """
    if pl.get("lever_hint") != "density":
        return None
    try:
        from src import supply as supply_mod
        from src import upload_cap

        st = upload_cap.state()
        days = pl.get("days_to_target")
        horizon = days if isinstance(days, (int, float)) and days < NEVER else None
        sw = supply_mod.sweep_novel()
        sp = supply_mod.supply(pl["density"], novel=sw["novel"], horizon_days=horizon)
        per_run = sp.get("sections_per_run_needed")
    except Exception:                                          # noqa: BLE001
        return None

    need = (f"この回ぶんは **節 {per_run:.1f}本**"
            if isinstance(per_run, (int, float)) and per_run == per_run
            and per_run != float("inf") else "この回ぶんは `src/supply.py` が出します")
    back = st.resets_at.astimezone(JST).strftime("%m/%d %H:%M JST")
    cap_open = st.remaining > 0 and not st.closed

    # **在庫が密度を支えていないなら、答えは本数枠と関係なく「作る」です**
    # （2026-08-21 04:0x に、この回の実測で直した）。
    #
    # ここは長らく **本数枠が開いているかどうかだけ**で「出す」「作る」を決めていました。
    # **本数枠は「今この窓で何本 API に通せるか」しか言っていません。**
    # ところが `density` の腕が読んでいる入力は `supply.make_rate`
    # ＝ **テーマが1日に何本増えているか**のほうです。
    #
    # **在庫から出すだけでは、その入力は1ミリも動きません。** それどころか、
    # 新しいテーマを1本も作らずに周を1つ進めると、窓だけ伸びて**下がります。**
    #
    # **実測（2026-08-21 03:1x の回）。** 本数枠は開（あと72本）で、ここは
    # 「引き方は『出す』」と言いました。そのとおり在庫から10本を予約したあとの
    # `--reflect` がこれです:
    #
    #     make_rate_per_day: 22.85 → **21.2**     ← 下がっている
    #     到達日（軌跡）: 2026-12-02 → 2026-12-02（**+0日**）
    #
    # **腕を選んで、その腕を引けない道を案内していた**ことになります。
    # `docs/JOURNAL.md`（8/20 18:1x）の申し送りは「`density` を引く回は、
    # 掃引ではなく表を1本書くこと」と、**既に正しいほうを言っていました** ——
    # この道具だけが、本数枠を見て逆を言っていた。
    #
    # **`holds` は「いまの在庫と作る速さで、その密度を期限まで保てるか」**です
    # （`src/supply.py`）。保てないなら、出す先は在庫の食い減らしにしかなりません。
    if sp.get("measured") and not sp.get("holds", True):
        covered = sp.get("days_covered")
        cov = f"{covered:.1f}日ぶん" if isinstance(covered, (int, float)) else "測定中"
        cap = (f"本数枠は開（あと {st.remaining}本）だが" if cap_open
               else f"本数枠は閉（{back} 戻り）。そのうえ")
        return (f"**{cap}、在庫が密度を支えていません（{cov}）"
                f"→ 引き方は「作る」**（`src/calc/` に節を書く）。{need}"
                f"  ＊**在庫から出しても `make_rate` は上がりません**"
                f"（08/21 03:1x の実測: 10本 予約して **+0日**・`make_rate` は下がった）")
    if cap_open:
        return (f"**本数枠は開（あと {st.remaining}本）→ 引き方は「出す」**"
                f"（`batch_build.py`）。作る側なら {need}")
    return (f"**本数枠は閉（{back} 戻り）→ 引き方は「作る」**"
            f"（`src/calc/` に節を書く）。{need}")


def _report_long_gate(m: dict, a: dict) -> list[str]:
    """**門2a を長尺で開けるなら、長尺1本に何回の再生が要るか。**

    ここが無い間、この道具は門2について「届きません」しか言えませんでした。
    **その「届きません」は、長尺の実力ではなく「長尺を1本も出していない」ことの
    言い換え**です（`days_long_hours` は直近365日の伸びを延ばした数なので、
    伸びが0なら必ず無限になる）。**別の命題を同じ字で書いていました。**
    """
    out: list[str] = []
    P = out.append
    days = a["days_subs_at"][PLAN_PUBLISH_PER_DAY]
    P("")
    P("--- **門2a（長尺4,000時間）を、長尺を足して開けるなら** ---")
    # **ここだけ `UPLOAD_CAP_PER_DAY = 92` が残っていました**（2026-08-26 に直した）。
    # 天井の掛け算は 2026-08-25 に **92 → `day_cap.cap()`（実測10本/日）**へ直っています
    # （`_measure` の註「それを超えて出したぶんは 0再生」）。
    # **`_report_long_gate` だけが取り残されていて**、門2b を **9.2倍 楽観**に
    # 出していました（0.53倍 と印字。実際は 0.06倍）。
    # `docs/trigger_main.md` §4 の「長尺が唯一の道」は、この 0.53倍 を引いています。
    # **同じ量を2か所が別々に持って、片方だけ直った形**の8件目です。
    _cap = min(float(UPLOAD_CAP_PER_DAY), float(a["view_cap_per_day"]))
    _got = a["per_video_now"] * _cap
    P(f"    門2b（ショート90日1,000万）は、**再生が付く上限 {_cap:,.0f}本/日"
      f"（口は92本/日 ですが、**超えたぶんは 0再生**）まで出しても"
      f"{a['shorts_needed_per_day']:,.0f}回/日に対し {_got:,.0f}回/日"
      f" ＝ {_got / a['shorts_needed_per_day']:.2f}倍**。門2a のほうを見ます。")
    P(f"    残り {a['long_minutes_needed']:,.0f}分（{a['long_minutes_needed']/60:,.0f}時間）を、"
      f"**門1 が通る日（1日{PLAN_PUBLISH_PER_DAY}本公開で {_fmt_days(days)}）までに**埋める。")
    P("")
    P("    **要る「長尺1本あたり再生」**（長尺を1日L本足したとき。**これが合格点**）:")
    P(f"      {'形（推測）':<18}{'1再生の視聴分':>12}" + "".join(f"{'L=' + str(n) + '本/日':>12}" for n in LONG_PER_DAY_SCENARIOS))
    for r in a["long_break_even"]:
        cells = "".join(
            (f"{r['views'][n]:>11,.0f}回" if r["views"][n] < 10 ** 6 else f"{'届かない':>12}")
            for n in LONG_PER_DAY_SCENARIOS
        )
        P(f"      {r['label']:<18}{r['min_per_view']:>10.1f}分" + cells)
    P("")
    P(f"    いまショートは **1本 {a['per_video_now']:,}回**（実測）。")
    lpv = a.get("long_per_video")
    if lpv is None:
        P("    長尺の1本あたり再生は**測れていません**（直近28日に長尺の再生が0本）。"
          "**上の数字は、その未知に対する合格点です。**")
    else:
        # **ここは「未測定」と書いてありました**（2026-08-19 14:2x に直した）。
        # 実際には直近28日に長尺が n 本ぶん再生されていて、**測れています。**
        # 「未測定」と書いてあるかぎり、この表は誰とも突き合わされません。
        P(f"    **長尺の1本あたり再生は測れています: 1本 {lpv:,}回**"
          f"（直近28日・n={a['long_videos_28d']}・合計 {a['long_views_28d']:,}回）。"
          "**上の合格点と、いま突き合わせます:**")
        worst = None
        for shape in a["long_break_even"]:
            for per_day in LONG_PER_DAY_SCENARIOS:
                need = shape["views"][per_day]
                if need == float("inf"):
                    continue
                short_by = need / lpv if lpv else float("inf")
                if worst is None or short_by < worst[0]:
                    worst = (short_by, shape["label"], per_day, need)
        if worst:
            short_by, label, per_day, need = worst
            P(f"    **いちばん甘い行でも {label}・L={per_day}本/日 で {need:,.0f}回 ＝ "
              f"実測の {short_by:,.0f}倍**。全部の行を下回っています。")
        P(f"    **これは「長尺では開かない」ではありません**（M20）。n={a['long_videos_28d']} で、"
          f"登録者 {m['subs_net']} 人のチャンネルに出した本の数です。"
          "**決まったのは「いまのままでは開かない」**で、段2 が測るのは"
          f"**1本あたりを {lpv:,}回 から何倍にできるか**のほうです。")
        # --- **Lの側でも解く**（2026-08-29 に足した。`_long_needed_per_day`）---
        #
        # ここまでの表は L＝1/2/4本/日 しか持たず、上の1行は**Lを凍らせて**
        # 「1本あたりを何倍にできるか」だけを段2 の的にしています。
        # **Lはこの機械が自分で動かせる側**（族を1つ足せば +2本/7日）で、
        # 1本あたり再生は配信が決める側です。**動かせるほうが画面に無い**のは、
        # 08/26 に踏んだ形の裏返しです（`config/hypotheses.yaml` の
        # 「『面が足りない』と読んでいるあいだ、`batch_build --long` は
        #   候補にすら挙がりませんでした」）。
        need_l = _long_needed_per_day(a, float(lpv), days)
        fam = _long_family_ceiling()
        best_l = min((r for r in need_l if r["per_day"] < float("inf")),
                     key=lambda r: r["per_day"], default=None)
        if best_l:
            P(f"    **もう一方の解き方**（1本あたり再生を実測の {lpv:,}回 で固定して、"
              f"Lのほうを解く）: **いちばん甘い行（{best_l['label']}）で "
              f"L＝{best_l['per_day']:,.1f}本/日**。"
              "**表の3列（1/2/4本/日）は、どれもここに届いていません** ——"
              "「全部の行を下回っています」は、**Lを4本/日 で止めたぶん**でもあります。")
            # **段2 の面の行も、同じLを別の道から出します**（`_gate2_surface_basis`）。
            #     あちらは「面 × 実測CTR」＝ 公開1本あたり 5.3回 で解き、こちらは
            #     Analytics の1本あたり再生 8.0回 で解くので、**数は 1.5倍 ちがいます。**
            #     **食い違いではありません** —— Analytics の1本あたり再生には
            #     サムネの面を通らない再生（関連・外部）が入り、面の側には入りません。
            #     **どちらも「Lは20本/日 台が要る」に着きます。**
            P("      （段2 の面の行は同じLを別の道から出します —— "
              "あちらは面×実測CTR、こちらは Analytics の1本あたり再生。"
              "**サムネの面を通らない再生のぶんだけ、こちらが小さく出ます。**"
              "食い違いではありません）")
            if fam and fam["per_day"] > 0:
                need_fam = int(-(-best_l["per_day"] * fam["window"] // fam["per_calc"]))
                P(f"    そのLを止めているのは**族の数**です: いま **{fam['families']}族**"
                  f"（在庫 {fam['stock']}本）→ {fam['window']}日ぶんで取れるのは"
                  f" **{fam['ceiling_7d']}本 ＝ {fam['per_day']:.2f}本/日**"
                  f"（1族から {fam['per_calc']}本まで。`scripts/topic_forge.py --list`）。"
                  f" **要るLとの差は {best_l['per_day'] / fam['per_day']:,.1f}倍**")
                # **この行だけ `[!]` を付けます**（2026-08-29）。
                #     この道具の手順は「頭と尾の3行だけ読む」で、真ん中は読まれません。
                #     尾の `[!]` 集めだけが中を運びます —— そこは**先頭 120字で切られる**ので、
                #     **動かす数（あと何族・在庫が何件）を頭に置くこと。**
                P(f"      [!] **長尺の律速は族の数: あと {max(0, need_fam - fam['families'])}族"
                  f"（要る {need_fam} ／ いま {fam['families']}）。"
                  f"表を書かずに増やせる族が {fam['spare']}件**"
                  f"（`topic_forge.py --list` の (2)・実測 15分/件）。"
                  f"要るLは {best_l['per_day']:,.1f}本/日、いまの天井は {fam['per_day']:.2f}本/日"
                  f"（{best_l['per_day']:,.1f} × {fam['window']}日 ÷ {fam['per_calc']}本 ＝"
                  f" {need_fam}族。`src/calc/` に表は在るが長尺のテーマを持っていない族が"
                  f" {fam['spare']}件）")
                P("      **これは「開く」と言っているのではありません** ——"
                  f" L を {fam['per_day']:.2f} → {best_l['per_day']:,.1f}本/日 に上げたとき"
                  f"1本あたり再生が {lpv:,}回 のまま保つかは**未測定**です"
                  "（`config/hypotheses.yaml`「長尺の1本あたり再生 8.0回 は長尺の天井ではない」が、"
                  "その1件を 1日8本 の帯で測っています）。"
                  "**ここで言えるのは1点だけ: Lの側の天井は族の数で決まっていて、"
                  "その族は「新しい表を書かずに」増やせる状態で置かれている。**")
                # **この節を足した回が、その場で同じ失敗をしました**（2026-08-29）。
                #
                # 上の「あと N族」は、**1本あたり再生を今日の実測で凍らせて**
                # 出した数です —— **直したはずの形の、そのままの再演**です
                # （直前の行が「Lを4本/日で凍らせていた」と言っている）。
                # **要るLは1本あたり再生に反比例する**ので、その倍率が動けば
                # 族の数は桁で変わります。**両方を同じ行に出すこと。**
                #
                # ここに倍率の相手（台帳が測っている「×10」など）を**写さないこと** ——
                # 写した瞬間に古くなります。**この機械が持っている数だけ**で言えます:
                # 「族を1つも足さずに足りるのは、1本あたり再生が ×(要るL ÷ 天井) のとき」。
                x = best_l["per_day"] / fam["per_day"]
                P(f"      **要るLは1本あたり再生に反比例します。** 族を1つも足さずに"
                  f"足りるのは、1本あたり再生が **×{x:,.1f}**"
                  f"（{lpv:,} → {lpv * x:,.0f}回）になったとき。"
                  f"**1本あたり再生が動かないなら あと {max(0, need_fam - fam['families'])}族、"
                  f"×{x:,.1f} が出れば あと0族** —— **桁が変わるのは、この2つのどちらが"
                  f"先に動くか**です。**倍率を測っている前提が台帳で開いているあいだ、"
                  f"族を {need_fam} まで積む理由はありません**"
                  f"（上の「あと {max(0, need_fam - fam['families'])}族」は、"
                  f"**1本あたり再生を今日の実測で凍らせた数**です）")
            elif fam:
                P(f"    そのLを止めているのは**族の数**です"
                  f"（いま {fam['families']}族・在庫 {fam['stock']}本 ＝ 7日で 0本）。")
    if a.get("long_per_video") is None:
        P("    **長尺を出したら、この表の1行と突き合わせること。** 下回るなら長尺では開きません。")
    return out


def _levers(m: dict, a: dict) -> list[tuple[str, str, str]]:
    """門1（登録者1,000人）を1年以内に通すのに、各数字が何倍要るか。"""
    rows = []
    need_subs_per_day = a["subs_remaining"] / 365
    if a["subs_per_day"] > 0:
        x = need_subs_per_day / a["subs_per_day"]
    else:
        x = float("inf")
    rows.append(("登録者／日（門1を1年で）", f"{a['subs_per_day']:.2f}人", f"{need_subs_per_day:.2f}人 ＝ **{x:,.0f}倍**"))
    rows.append(("　うち 登録率", f"{a['sub_rate']*100:.4f}%",
                 f"{a['sub_rate']*100*x:.3f}%（再生数を据え置くなら）"))
    rows.append(("　うち 再生／日", f"{a['views_per_day']:,.0f}回",
                 f"{a['views_per_day']*x:,.0f}回（登録率を据え置くなら）"))
    per_day_cap = a["per_video_now"] * UPLOAD_CAP_PER_DAY
    rows.append(("本数だけで届く上限", f"{a['views_per_day']:,.0f}回／日",
                 f"{per_day_cap:,.0f}回／日（92本の上限。**{per_day_cap/max(a['views_per_day'],1):,.1f}倍まで**）"))
    return rows


#: 実データが動いたかを見る鍵。**予測の入力そのものだけ**を並べること。
#: 派生値（`days_*`・天井）を混ぜると、こちらの計算式を変えただけで「動いた」になります。
_INPUT_KEYS = ("views_7d", "views_28d", "views_90d", "views_all",
               "subs_net", "subs_gained_28d", "long_hours_365", "shorts_views_90d")


def _same_inputs(a: dict, b: dict) -> bool:
    """2つの点で、**実測の入力が1つも動いていない**か。"""
    return all(a.get(k) == b.get(k) for k in _INPUT_KEYS)


def _drift(current: dict) -> list[str]:
    """前の回の予測と比べる。**近づいていないなら、その回の作業は効いていない。**"""
    if not LOG.exists():
        return ["", "  （前の点がありません。次の回からは、この行に「何日ぶん縮んだか」が出ます）"]
    points = []
    for line in LOG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                points.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    if not points:
        return []
    prev = points[-1]

    # **実データが動いていない回では、差を「効いていない」と読まないこと**
    # （2026-08-19 21:2x に、18点ぶんを数えて直した）。
    #
    # Analytics は**日次で、3日遅れ**です。回は約41分ごとに回るので、
    # **1日のうちに入力は1度も動きません。** 実際 `data/eta.jsonl` の18点は
    # `views_7d` も `subs_net` も**全部同じ値**でした。それでもここは毎回
    # 「**作業で縮んだぶん -0.0日 ← 効いていません**」と印字していました ——
    # **その回が何をしたかと無関係に、常に同じ字**です。
    #
    # 「効いていません」を毎周見せられた側が、日付を動かす作業から離れていくのは
    # 自然です。**だから、動いていないときは「測れない」と言うこと。**
    # 比べる相手も、**入力が実際に違う最後の点**にします（同じ値どうしを引いても
    # 0 しか出ません）。
    stale = _same_inputs(points[-1], current)
    older = next((p for p in reversed(points) if not _same_inputs(p, current)), None)
    if stale and older is not None:
        prev = older
    out = ["", "--- 前の回からの差（**縮んでいないなら、その回の作業は日付を動かしていない**）---"]
    if stale:
        span = ""
        try:
            hours = (datetime.fromisoformat(current["at"])
                     - datetime.fromisoformat(points[-1]["at"])).total_seconds() / 3600
            span = f"（前の点は {hours:.1f}時間前。そこから実データは1つも動いていません）"
        except (ValueError, KeyError):
            pass
        out.append(f"    [!] **実データがまだ動いていません**{span}")
        out.append("        Analytics は**日次で3日遅れ**。回はそれよりずっと速く回るので、"
                   "**この回の作業が効いたかは、ここでは測れません。**")
        out.append("        **「効いていない」ではありません。** 下の差は、"
                   + ("入力が最後に違った点との比較です。" if older is not None
                      else "比べられる点がまだありません。"))
        if older is None:
            out.append("    → いま1周ごとに測れるのは、**どの腕を選んだか**のほうです（下）。")
            # **物差しの断りは、この道でも出すこと**（2026-08-19 21:2x に検査が落ちて気づいた）。
            # 物差しの取り替えは**実データが動かなくても起きます**（こちらの計算式の話なので）。
            # 早い return で落とすと、**入力が同値の日にかぎって断りが消えます** ——
            # 取り替えの直後はまさにその形（同じ日に積み直す）なので、いちばん要る回で黙ります。
            out.extend(_scale_note(prev, current))
            return out
    pd_ = prev.get("days_monetized")
    cd = current["days_monetized"]
    if pd_ is None:
        return out
    try:
        elapsed = (datetime.fromisoformat(current["at"]) - datetime.fromisoformat(prev["at"])).total_seconds() / 86400
    except (ValueError, KeyError):
        elapsed = 0.0
    if pd_ >= NEVER and cd >= NEVER:
        out.append("    収益化まで: **どちらも「届かない」**。**律速はまだ1つも動いていません。**")
    elif pd_ >= NEVER:
        out.append("    収益化まで: 「届かない」→ " + _fmt_days(cd) + "  **道が開きました**")
    elif cd >= NEVER:
        out.append("    収益化まで: " + _fmt_days(pd_) + " → **「届かない」に戻りました**")
    else:
        # 何もしなければ、経過したぶんだけ縮む。それ以上縮んだぶんが「効いた」ぶん。
        gained = (pd_ - cd) - elapsed
        out.append(f"    収益化まで: {pd_:,.0f}日 → {cd:,.0f}日（{elapsed:.2f}日 経過）")
        out.append(f"    **作業で縮んだぶん: {gained:+,.1f}日**"
                   + ("  ← 効いています" if gained > 0.5 else "  ← **効いていません**"))
    # **収益化が「届かない」のままだと、上の3行は何周でも同じ字を出します。**
    # 動いている所が見えないので、門1（いまの律速）の日数も並べます。
    if prev.get("days_subs") and current.get("days_subs"):
        pds, cds = prev["days_subs"], current["days_subs"]
        if pds < NEVER and cds < NEVER:
            gained = (pds - cds) - elapsed
            out.append(f"    門1（登録者1,000人）: {pds:,.0f}日 → {cds:,.0f}日"
                       f"  **作業で縮んだぶん {gained:+,.1f}日**")
    for key, label in (("views_per_day", "再生／日"), ("sub_rate", "登録率"), ("per_video_now", "1本あたり再生")):
        if key in prev and prev[key]:
            now = current.get(key, 0)
            if now:
                out.append(f"    {label}: {prev[key]:,.4g} → {now:,.4g}（{(now/prev[key]-1)*100:+.1f}%）")
    # **物差しを取り替えた回は、その差を「悪くなった」と読まないこと**（2026-08-19 15:0x）。
    # 9点目までの `per_video_now` は「30再生の床つきの中央値」、10点目からは
    # 「床なしの平均」です。**チャンネルは何も変わっていないのに 1,092 → 869 と出ます。**
    # 差の節は「作業が効いたか」を見る所なので、ここで断らないと
    # **物差しの取り替えが、実績の悪化として next の判断に入ります。**
    out.extend(_scale_note(prev, current))
    return out


def _scale_note(prev: dict, current: dict) -> list[str]:
    """**物差しを取り替えた回は、その差を「悪くなった」と読ませない。**

    **向きは両方あります**（2026-08-20 03:1x に足した）。取り替えは
    悪くなる側にも良くなる側にも出るので、**良くなった側でも断ること** ——
    断らないと、次の回が **+9.6% を「この回の作業が効いた」と読みます。**
    """
    out: list[str] = []
    if prev.get("views_per_video") is None and current.get("views_per_video") is not None:
        out += ["    [!] **1本あたり再生の物差しが、この点から変わりました**"
                "（床つきの中央値 → 床なしの平均）。",
                "        **上の変化は実績ではありません。** 実績として読めるのは、次の点からです。"]
    if prev.get("views_per_video_live") is None and current.get("views_per_video_live") is not None:
        out += ["    [!] **1本あたり再生の分母が、この点から変わりました**"
                "（`day_cap` の帯の外に落ちた本 ＝ 上限を超えて出した 0再生の側 を、分母から外した）。",
                "        **上の変化は実績ではありません。** 天井は"
                "「1本あたり再生 × 再生が付く上限」なので、"
                "**帯の外の本を分母に残すと、同じ死を2回 引きます**"
                "（`live_band_views` の docstring に実測）。",
                "        実績として読めるのは、次の点からです。"]
    if prev.get("per_video_dropped") is None and current.get("per_video_dropped") is not None:
        out += ["    [!] **1本あたり再生の標本が、この点から変わりました**"
                "（予約のまま公開していない本・公開から48時間未満の本・28日の窓より前の本を落とした）。",
                "        **上の変化は実績ではありません**（実測 869 → 952 ＝ +9.6%）。"
                " 実績として読めるのは、次の点からです。"]
    return out


def solve(m: dict, points: list[dict], *, full: bool = True) -> dict:
    """**実測 `m` から、予測を最後まで解く。**（2026-08-20 に `main()` から出した）

    出したのは、**周の終わりの「反映」が同じ道を通るため**です
    （オーナー指示・原文: **「毎回その予測に反映して」**）。
    `reflect()` が自前で解き直す形にすると、**2つの道が別々に古びます** ——
    片方だけに腕の上限や供給が入る、という壊れ方は、外から見えません。

    返すのは `{"a", "sup", "pl", "tr", "row"}`。**印字はしません**
    （`main()` は 200行出し、`reflect()` は 10行しか出さないため）。

    `full=False` は**印字にしか使わない軌跡3本を解きません**
    （`trajectory_all` の docstring に、なぜ日付が変わらないかと実測）。
    **道は分けていません** —— 上の「2つの道が別々に古びる」は
    `reflect()` が**自前で解き直す**形のことで、ここは同じ1本の関数を通ります。
    """
    a = analyse(m, points)
    m["per_video_now"] = a["per_video_now"]

    # **段取りを先に解いて、日付を最初に出す**（オーナー指示3回目・2026-08-20 08:0x）。
    # 出力は200行あり、読み手が最初に見た数字がその回の入口になります。
    #     **供給の実測を渡すこと**（2026-08-20 16:0x）。渡さないと段1 は
    #     「1日25本」という**満たせない前提**で解かれます（`solve_gate1`）。
    sup = supply_state()
    pl = plan(m, a, supply=sup, sensitivity=True, points=points)
    # --- **面ごとの引き代を、印字する側にも渡す**（2026-08-30・最適化の回）---
    #     `_row()` は既にこれを `data/eta.jsonl` へ積んでいて、`src/levers.py` の
    #     `_long_surface_open()` がそれを読んで「`density` は死んでいない」と
    #     判定しています。**ところが `headline()` は積んだ行を読みません**
    #     （その回の行はまだ書かれていない）ので、頭の3行だけが
    #     「`density` は ×1.00」というショートの面の数で話すことになります。
    #     **同じことを2か所が別々に言っていて、片方しか読まれていない形**です。
    #     ここで `pl` に載せて、`headline()` と `_row()` が同じ1つを見ます。
    try:
        _ph_s = physical_caps(a, supply=sup)
        pl["density_surfaces"] = {
            name: {"at_ceiling": bool(_ph_s[key].get("at_ceiling")),
                   "measured": bool(_ph_s[key].get("measured")),
                   "why": _ph_s[key].get("why")}
            for name, key in (("short", "density"), ("long", "density_long"))
            if key in _ph_s
        }
    except Exception:                                          # noqa: BLE001 — 回を止めない
        pass
    # **腕が動く速さを含んだ軌跡**（2026-08-20 18:xx・オーナー指示）。
    #     ここが出ないと、印字される日付は「腕が1ミリも動かない未来」になります。
    #     **回を止めないこと** —— 軌跡が解けなくても、据え置きの線だけで出します。
    try:
        tr = trajectory_all(m, a, supply=sup, points=points, full=full)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[eta] 軌跡を解けませんでした: {type(exc).__name__}: {exc}")
        tr = None
    # --- **「天井まで引いても届かない」腕を、必要／不要で割る**（2026-08-26）---
    #     この1行が無かったせいで、頭の表は「ここに前提を置いても動きません」と
    #     書き、`--alloc` は同じ日に「次の1件はその腕に置くのが最短」と書いて
    #     いました。**測れば済む話です**（`frozen_days` の docstring に全文）。
    #     費用は腕1本につき軌跡1本（API 0単位・**2〜4秒**）。**普通は1〜2本**。
    if tr is not None and FROZEN_ARMS:
        _dead = [r["lever"] for r in (pl.get("lever_days") or [])
                 if r.get("cap") is not None and not r.get("reachable_at_cap")]
        if _dead:
            pl["arm_frozen_days"] = frozen_days(m, a, tr, _dead,
                                                supply=sup, points=points)
    # **引く腕は1つに絞ること。** 軌跡が出た回は、そちらが名指しした腕を採ります。
    #     `plan()` の `lever_hint` は「いちばん遅い床の名前」＝**診断**で、
    #     **引いたら何日縮むか**は言っていません。同じ見出しに2つの腕が並ぶと、
    #     読み手はどちらでも選べてしまい、**後から理由を付ける**側に戻ります。
    if tr is not None:
        _top = next((r for r in tr["choice"] if r["reachable"]), None)
        if _top is not None and _top["lever"] != pl["lever_hint"]:
            pl["lever_hint_binding"] = pl["lever_hint"]
            pl["lever_hint"] = _top["lever"]
            pl["lever_from"] = "軌跡"
    return {"a": a, "sup": sup, "pl": pl, "tr": tr,
            "row": _row(m, a, pl, tr, sup)}


def _row(m: dict, a: dict, pl: dict, tr: dict | None, sup: dict | None) -> dict:
    """`data/eta.jsonl` に積む1行を組む。**`solve()` と同じ理由でここに出しています。**"""
    row = {**m, **{k: v for k, v in a.items() if isinstance(v, (int, float))}}
    # **予測日そのものを積む。** 積まないと、次の回が「早まったか」を測れません
    # （`headline` の3行目と、`run_marker.py --ship --moves` の突き合わせ）。
    row["days_to_target"] = pl["days_to_target"]
    row["target_date"] = pl["target_date"].isoformat() if pl["target_date"] else None
    row["days_revenue"] = pl["days_revenue"]
    row["binding"] = pl["binding"]
    row["lever_hint"] = pl["lever_hint"]
    # **名指しを「引かなくてよい回」も積むこと**（2026-08-26）。
    #     積まないと `run_marker.py` から見えず、`lever_followed` が
    #     道具の指示どおりに動いた回を「外した」と数えつづけます。
    row["lever_hint_covered"] = pl.get("lever_hint_covered")
    # **供給の実測も積む**（次の回が「作る速さは上がったか」を測れる形にする）
    row["density_month"] = pl.get("density_month")
    row["make_rate_per_day"] = (sup or {}).get("rate_per_day")
    row["days_gate1"] = pl.get("gate1", {}).get("days")
    # --- **`density` の天井は、面ごとに割れている**（2026-08-26。3回続けて申し送られた）---
    #     `arm_caps["density"]` はショートの面の数だけです。**長尺の面は別**で、
    #     しかも**未測定**なので `LEVERS` には入れていません（軌跡に歩かせない）。
    #     ところが「死んだ腕」の判定は `data/eta.jsonl` しか読まないので、
    #     **ここに積まないかぎり、選ぶ側からは面の割れが永久に見えません。**
    # **`solve()` が先に載せていれば、それを使う**（2026-08-30）。同じ回に
    #     `physical_caps` を2回 解くと、**頭の3行と積んだ行がずれうる**ので
    #     （実測の齢が2回のあいだに変わる）、**1つを2か所で読む形**にします。
    if isinstance(pl.get("density_surfaces"), dict):
        row["density_surfaces"] = pl["density_surfaces"]
    else:
        try:
            _ph = physical_caps(a, supply=sup)
            row["density_surfaces"] = {
                name: {
                    "at_ceiling": bool(_ph[key].get("at_ceiling")),
                    "measured": bool(_ph[key].get("measured")),
                    "why": _ph[key].get("why"),
                }
                for name, key in (("short", "density"), ("long", "density_long"))
                if key in _ph
            }
        except Exception:                                      # noqa: BLE001 — 回を止めない
            pass
    # **軌跡そのものを積む。** 積まないと、次の回が「軌跡が早まったか」を測れません
    # （据え置きの線と混ぜないこと ＝ 別の欄にする）。
    if tr is not None:
        _b = tr["base"]
        row["traj_days"] = _b["days"]
        row["traj_date"] = _b["date"].isoformat() if _b["date"] else None
        row["traj_t_work"] = _b["t_work"]
        row["traj_focus"] = next((r["lever"] for r in tr["choice"] if r["reachable"]), None)
        row["arm_rates"] = {k: a["rate"] for k, a in tr["arms"].items()}
        row["arm_hits"] = f"{tr['band']['k']}/{tr['band']['n']}"
        # --- **天井と配分も積む**（2026-08-24。**印字にしか無かった数**）---
        #     `_factors_at` は `cap <= 1.0` の腕を `live` から外します ＝
        #     **その腕はこの先1日も動きません。** ところがこの事実は
        #     `data/eta.jsonl` に1つも入っていませんでした。
        #     結果、**この機械の外にいる誰も「どの腕が死んでいるか」を読めない**:
        #     `run_marker.py --ship --lever density` は、density の天井が
        #     ×1.00（引き代ゼロ）でも黙って通ります —— 実測で
        #     **8/24 の ship 12件のうち5件がそれ**でした。
        #     天井は `eta.py` を4分走らせた stdout にしか無く、
        #     `--ship` は4秒の `--reflect` しか撃たないので、届いていません。
        row["arm_caps"] = {k: a.get("cap") for k, a in tr["arms"].items()}
        row["arm_share"] = {k: a.get("share") for k, a in tr["arms"].items()}
    # --- **「天井まで引いたら届くのか」も積む**（2026-08-25）---
    #     `arm_caps` だけでは足りません。**天井が大きいことと、
    #     その腕が到達日を動かせることは別**です:
    #
    #         sub_rate  天井 ×2,923.79 …… **天井まで引いても月20万には届かない**
    #                   （いまの縛りは再生数（段4）で、登録率はそこに触らない）
    #
    #     `DEAD_CAP`（＝天井 ×1.00 以下）で数えると、この腕は
    #     **「引き代 ×2,923.79 の生きた腕」**に見えます。**偽の緑です。**
    #     8/25 の実測では、実績配分の 11% がここに載っていました
    #     （`density` の 28% と合わせて **39%**）。
    #     `lever_days` が既に解いているので、**印字だけで捨てないこと。**
    _ld = pl.get("lever_days") or []
    if _ld:
        row["arm_reaches"] = {r["lever"]: bool(r.get("reachable_at_cap")) for r in _ld}
        row["arm_threshold"] = {r["lever"]: r.get("threshold") for r in _ld}
    # **「凍らせたら何日 遠のくか」も積む**（2026-08-26）。
    #     `arm_reaches` だけを読むと、`drift.py` はその腕を「引き代なし」に
    #     数えます。**十分でないことと、要らないことは別**なので、
    #     判別できる数を同じ行に置きます（`frozen_days`）。
    if pl.get("arm_frozen_days"):
        row["arm_frozen_days"] = {k: (None if v is None else round(float(v), 1))
                                  for k, v in pl["arm_frozen_days"].items()}
    row["videos_needed_gate1"] = pl.get("gate1", {}).get("need_videos")
    # --- **天井（面と混ざり方）も積む**（2026-08-20 23:3x。前の周の申し送り②）---
    #     `--reflect` は「出発点の行」と「解き直した行」の差を取ります。
    #     ところが行には**天井が1つも入っていなかった**ので、
    #     22:2x の回が `rpm` の天井を ×100 → ×15.5 に**測り直したのに、
    #     反映は「動かせる入力なし」と言いました。** 測った当人の回が、です。
    #     天井は入力です（実測が同じでも、測り直せば動く ＝ その回の作業ぶん）。
    _sf = pl.get("surface") or {}
    row["rpm_cap"] = _sf.get("rpm_cap")                 # 実測の混ざり方の天井（¥）
    row["rpm_plan"] = _sf.get("rpm_plan")               # 段4 が実際に当てている RPM
    row["long_imp_day"] = _sf.get("long_views_day_cap")  # 長尺の面（回/日・実測）
    row["need_month"] = pl.get("need_month")            # 段4 の合格点（月の再生）
    row["ceiling_short"] = pl.get("ceiling_short")      # 天井が何倍 足りないか
    return row


# ---------------------------------------------------------------------------
# **周の終わりの「反映」**（2026-08-20・オーナー指示。原文は次の1行）
#
#     > 毎回の実行で予測するように言ったはずなので、毎回その予測に反映して
#
# **予測を出すことは、既に毎回やっています。** 言われているのは**反映**のほうです。
# いま起きているのはこう:
#
#   * 判定や実測が出ても、**予測に入るのは次の回か、あるいは入らない**
#   * 2026-08-20 の実例 —— 歩留り 1.0→0.156・供給 21日→4日・A/B の在庫の
#     数え方・掃引の候補数・`retention` の6本。**どれもその回の予測に
#     入っていません**
#   * 逆に、入れてはいけないもの（`density_month 25.0`）が別の欄から戻って
#     **予測を3分の1にしました**
#
# だから、周の終わりに**もう一度解いて、日付の前後差を残します。**
#
# ## なぜ Analytics を取り直さないか（`--reflect` が offline なのは、そのため）
#
# Analytics は**日次で3日遅れ**。回は1時間ごとに回るので、**1日のうち
# 入力は1度も動きません**（実測: `data/eta.jsonl` の18点は `views_7d` も
# `subs_net` も全部同値）。取り直すと API を叩く時間がかかるうえ、
# **たまたま日が変わった回だけ、チャンネル側の変化がこちらの作業のぶんに混ざります。**
#
# **出発点と同じ実測を使えば、動いた差は「この回が触った所」だけになります。**
# ＝ 反映の差は、定義として**この回の作業ぶん**です。
# ---------------------------------------------------------------------------

# **差として数えない鍵**（時刻・種別・反映そのものが書く欄）。
_REFLECT_IGNORE = {
    "at", "kind", "session", "base_at", "note", "moved", "no_movable_input",
    "traj_date_before", "target_date_before", "traj_delta_days", "target_delta_days",
    "traj_days_before", "days_to_target_before", "traj_solved",
}


def _reflect_session() -> str:
    """**この回を回している当人**（`run_marker.actor_id()` と同じ読み）。

    2026-08-25 22:0x に `session_id()` から差し替えました。毎時の回は
    親セッションの中の**サブエージェント**になり、素のIDだと
    **同時に走っている隣の回と同一人物**になるためです
    （`run_marker.worktree_tag()` に実測。ship 14件が親フィルタに落ちていました）。
    `stop_check.sh` の「反映したか」は `#` から前で見るので、こちらが長くても効きます。
    """
    raw = os.environ.get("CLAUDE_CODE_REMOTE_SESSION_ID", "")
    sid = ("session_" + raw[4:]) if raw.startswith("cse_") else raw
    parts = Path(__file__).resolve().parent.parent.parts
    for i in range(len(parts) - 2):
        if parts[i] == ".claude" and parts[i + 1] == "worktrees":
            tag = parts[i + 2]
            return f"{sid}#{tag}" if sid else tag
    return sid


def _moved(before: dict, after: dict) -> dict:
    """**この回で動いた入力**を、鍵ごとに `[前, 後]` で返す。

    **鍵を列挙しないこと。** 列挙すると、次に足された入力が黙って漏れます
    （`density_month` が別の欄から戻って予測を3分の1にしたのが、まさにその形）。
    実測（Analytics 由来）は出発点のものをそのまま使うので、**ここには構造上出ません** ——
    出るのは供給・密度・腕の速さ・こちらの計算式だけです。
    """
    out: dict = {}
    for k in sorted(set(before) | set(after)):
        if k in _REFLECT_IGNORE:
            continue
        b, a = before.get(k), after.get(k)
        if b == a:
            continue
        if isinstance(b, (int, float)) and isinstance(a, (int, float)) \
                and not isinstance(b, bool) and not isinstance(a, bool):
            if abs(a - b) <= 1e-9 * max(1.0, abs(b)):
                continue
        out[k] = [b, a]
    return out


def _date_delta(before: str | None, after: str | None) -> int | None:
    """**負なら早まった**（`--moves` と同じ向き）。片方でも無ければ `None`。"""
    if not before or not after:
        return None
    try:
        return (date.fromisoformat(after) - date.fromisoformat(before)).days
    except ValueError:
        return None


def _others_landed(since: str | None) -> list[str]:
    """**同じ周のあいだに、他の回が押した変更を数える。**

    サブの回は同じ枝の worktree が何枚も同時に走っており、
    **`--reflect` の「前 → 後」には、その周のあいだに merge された
    他の回の変更が全部 混ざります。** ここを黙っていると、
    上の「動いた入力」が**こちらの ship の成績に見えます。**

    実測（2026-08-26 07:5x）: `--moves 0` と宣言した回の軌跡が **+1日** 動き、
    追うと原因はきょうだいの `95cc164`（`config/hypotheses.yaml` の10件に
    `lever` を足した ＝ 飛ばされていた**外れ**の前提が1件 読めるようになった）で、
    **こちらの ship は `arm_speed.closed()` の分母に1件も入っていません。**

    **数えるだけで、差し引きはしません** —— どの入力が誰のものかは
    ここでは決められないからです。**「混ざっている」と言えれば足ります。**
    """
    if not since:
        return []
    try:
        out = subprocess.run(
            ["git", "log", f"--since={since}", "--no-merges",
             "--format=%h %s"],
            capture_output=True, text=True, cwd=ROOT, timeout=20,
        )
    except Exception:                                          # noqa: BLE001
        return []
    if out.returncode != 0:
        return []
    rows = [ln for ln in out.stdout.splitlines() if ln.strip()]
    if not rows:
        return []
    lines = [f"    [!] **この間に、この枝へ {len(rows)}件 のコミットが載っています。**"
             "「動いた入力」は**この回だけの成績ではありません**"
             "（同じ枝で複数の回が同時に走っています）。"]
    for r in rows[:6]:
        lines.append(f"        {r[:100]}")
    if len(rows) > 6:
        lines.append(f"        …ほか {len(rows) - 6}件")
    lines.append("        → **`--moves` の宣言と突き合わせるときは、"
                 "この行を先に読むこと。** どれが誰のぶんかは、"
                 "`git log -1 --format=%h -- <その入力を作るファイル>` で引けます。")
    return lines


def _fmt_moved(moved: dict, limit: int = 8) -> list[str]:
    def one(v):
        if isinstance(v, float):
            return f"{v:,.4g}"
        if isinstance(v, dict):
            return "{…}"
        return "無し" if v is None else str(v)
    keys = list(moved)
    out = [f"      {k}: {one(moved[k][0])} → {one(moved[k][1])}" for k in keys[:limit]]
    if len(keys) > limit:
        out.append(f"      （ほか {len(keys) - limit} 件。`data/eta.jsonl` の `moved` に全部あります）")
    return out


def reflect(note: str | None = None, *, record: bool = True) -> tuple[int, dict]:
    """**この回で動いた入力を、この回のうちに予測へ入れ直す。**

    返すのは `(終了コード, 積んだ行)`。**回を止めません** —— 解けなくても 0 を返し、
    「解けませんでした」とだけ言います（反映は記録であって門ではない）。
    """
    points = _points()
    if not points:
        print("[eta] 積んだ点がありません。**まず `python scripts/eta.py` を撃つこと。**")
        return 1, {}
    base = points[-1]
    # **出発点と同じ実測で解き直す**（上のコメント参照）。`solve()` は `m` を書き換えるので複製。
    m = {k: v for k, v in base.items() if k not in _REFLECT_IGNORE or k == "at"}
    try:
        # **`--reflect` では凍らせた線を測りません**（2026-08-26）。
        #     積み直すのは日付で、**腕の要否は問うていない** ——
        #     `--ship` は毎回ここを通るので、軌跡1〜2本ぶんが毎回の税になります。
        global FROZEN_ARMS
        _keep, FROZEN_ARMS = FROZEN_ARMS, False
        try:
            # **印字にしか使わない軌跡3本（`fast`/`slow`/`planned`）も解きません**
            #     （2026-08-28。同じ理由の続き —— 反映は 10行しか出しません）。
            #     `_row()` はこの3つを1つも読まないので、**積む行は 1文字も変わりません**
            #     （`tests/test_eta_reflect_light.py` が固定）。
            #     **実測 107.5秒 → 7.0秒**（`_view_cap_per_day()` と合わせて **-93%**）。
            s = solve(dict(m), points, full=False)
        finally:
            FROZEN_ARMS = _keep
    except Exception as exc:                                   # noqa: BLE001
        print(f"[eta] 反映を解けませんでした: {type(exc).__name__}: {exc}")
        print("[eta] **回は止めないこと。** 理由を docs/JOURNAL.md に1行書いて進むこと。")
        return 0, {}
    row = s["row"]
    # **軌跡が解けなかった回に、出発点の日付を「後」として読ませないこと。**
    #     `_row()` は `tr is None` のとき軌跡の欄を書きません。反映は
    #     **出発点の行そのものを `m` として渡す**ので、書かれなければ
    #     `traj_date` は出発点の値のまま残り、**差が黙って +0日**になります。
    #     ＝「動かなかった」と「測れなかった」が同じ字になる、いちばん悪い形。
    if s["tr"] is None:
        for k in ("traj_date", "traj_days", "traj_t_work", "traj_focus", "arm_rates", "arm_hits"):
            row.pop(k, None)
    moved = _moved(base, row)
    # **日付そのものは「動いた入力」ではなく「結果」です。** 差の一覧からは外し、
    # 下の前後差として別に出します（混ぜると「入力が動いた」に見える）。
    #     **`per_video_now` は落としません** —— あれは入力の側です
    #     （実測が同じでも、`_per_video()` の式を変えれば動く ＝ この回の作業ぶん）。
    for k in ("target_date", "traj_date", "days_to_target", "traj_days",
              "days_revenue", "binding", "lever_hint", "traj_focus"):
        moved.pop(k, None)
    t_before, t_after = base.get("traj_date"), row.get("traj_date")
    s_before, s_after = base.get("target_date"), row.get("target_date")
    t_delta, s_delta = _date_delta(t_before, t_after), _date_delta(s_before, s_after)

    out = ["", "=== この回の反映（**動いた入力を、この回のうちに予測へ入れ直す**）==="]
    out.append(f"    出発点: {base.get('at', '?')}（同じ実測で解き直しています）")
    if moved:
        out.append(f"    **この回で動いた入力: {len(moved)}件**")
        out.extend(_fmt_moved(moved))
        out.extend(_others_landed(base.get("at")))
    else:
        # **「効いていない」と混同しないこと**（`_drift` に同じ趣旨の断りがあります）。
        out.append("    [!] **この回で動かせる入力は、1つもありませんでした。**")
        out.append("        **「効いていない」ではありません。** Analytics は日次で3日遅れ、"
                   "回はそれよりずっと速い。")
        out.append("        この回が触った所が、**予測の入力に1つも入っていない**という意味です"
                   "（道具・文書・手順の整備はここに出ません）。")
        out.append("        → 次の回は、**入力に入る腕**（per_video / sub_rate / rpm / density）"
                   "を選ぶこと。")

    def line(label, b, a, d):
        if b is None and a is None:
            return f"    {label}: **どちらも「届かない」**"
        if d is None:
            return f"    {label}: {b or '届かない'} → **{a or '届かない'}**（前後のどちらかが「届かない」＝差は出せません）"
        arrow = "**早まりました**" if d < 0 else ("**遠のきました**" if d > 0 else "動いていません")
        return f"    {label}: {b} → **{a}**（{d:+d}日）  {arrow}"

    if s["tr"] is None:
        out.append("    [!] **軌跡を解けませんでした。** 下の「軌跡」の行は**測れていません**"
                   "（動かなかった、ではありません）。据え置きの線のほうを読むこと。")
    out.append(line("到達日（軌跡）", t_before, t_after, t_delta))
    out.append(line("到達日（腕を据え置いた線）", s_before, s_after, s_delta))
    if moved and t_delta == 0 and s_delta == 0:
        out.append("    → 入力は動いたのに**日付は動いていません。** その入力は"
                   "**いまの律速の外**にあります（`binding` を見ること）。")
    for ln in out:
        print(ln)

    rec = {
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kind": REFLECT_KIND,
        "session": _reflect_session() or None,
        "base_at": base.get("at"),
        "moved": moved,
        "no_movable_input": not moved,
        "traj_date_before": t_before, "traj_date": t_after, "traj_delta_days": t_delta,
        "target_date_before": s_before, "target_date": s_after, "target_delta_days": s_delta,
        "traj_days_before": base.get("traj_days"), "traj_days": row.get("traj_days"),
        "days_to_target_before": base.get("days_to_target"),
        "days_to_target": row.get("days_to_target"),
        "binding": row.get("binding"), "lever_hint": row.get("lever_hint"),
        "traj_solved": s["tr"] is not None,
    }
    if note:
        rec["note"] = note
    if record:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        try:
            where = LOG.relative_to(ROOT)
        except ValueError:                                     # 検査は tmp に積みます
            where = LOG
        print(f"[eta] **反映を残しました**: {where}"
              f"（`kind=\"{REFLECT_KIND}\"`。予測の点としては数えません）")
    return 0, rec


def _reflect_recap(limit: int = 3) -> list[str]:
    """**前の回たちが「入れ直した」結果を、この回の頭で見せる。**（2026-08-20）

    `_drift()` は**予測の点どうし**（周の頭と周の頭）を比べます。**周の中で
    動いた入力は、そこには出ません** —— 出るのは次の回か、あるいは永久に出ない。
    それがオーナー指示（**「毎回その予測に反映して」**）の指している穴でした。

    反映そのものは `reflect()` が周の終わりに残します。**ここはその読み口**です ——
    残す所と読む所の両方が無いと、`retention.py` が 8/10〜8/20 に踏んだ形
    （**正しく印字していたが、誰も読まなかった**）をもう一度やります。
    """
    rows = [r for r in _points(reflect=True) if r.get("kind") == REFLECT_KIND]
    if not rows:
        return []
    out = ["", "--- 前の回たちの**反映**（周の中で動いた入力 → 日付がどう動いたか）---"]
    for r in rows[-limit:]:
        when = str(r.get("at", "?"))[5:16].replace("T", " ")
        if r.get("no_movable_input"):
            out.append(f"    {when}  **動かせる入力なし**"
                       f"（{(r.get('note') or '')[:40]}）"
                       "  ← **「効いていない」ではありません**")
            continue
        d = r.get("traj_delta_days")
        if d is None:
            d = r.get("target_delta_days")
        moved = ", ".join(list(r.get("moved") or {})[:3])
        out.append(f"    {when}  {moved or '(入力の記録なし)'}"
                   + (f"  → **{d:+d}日**" if isinstance(d, int) else "  → 差は出せません")
                   + (f"（{(r.get('note') or '')[:40]}）" if r.get("note") else ""))
    n_moved = sum(1 for r in rows if not r.get("no_movable_input"))
    out.append(f"    **入れ直した回: {len(rows)}回 / うち入力が動いたのは {n_moved}回**"
               "（動かなかった回は、触った所が予測の入力に無かったということ）")
    return out


def alloc_search(with_speed: bool = False) -> int:
    """**次の前提をどの腕に立てるのが、いちばん早いか。**（2026-08-26・最適化の回）

    ## **順位を決めているのは回転ではなく天井です**（2026-08-27 に測って足した）

    ここが解いているのは `rate = focus_rate × share` の `share` だけで、
    `focus_rate = p · log(g) · θ` の **θ は `arm_speed.throughput()`
    ＝ 全体の実測ひとつ**です。しかも `arm()` は閉じた前提が `MIN_N`（=3）に
    満たない腕の `p` と `g` を**全体で代用**するので、
    `sub_rate`（2件）と `rpm`（1件）は **p も g も θ も同値**になります。
    **つまり、その2本の順位は天井の遠さだけで決まっています。**

    **そこで、台帳の予定表から腕べつの回転を測って掛けてみました**
    （`arm_speed.forward_by_arm()` / `speed_weights()`・`--alloc-speed`）。
    実測 2026-08-27（30日 窓）:

        per_video 0.100/日（×1.05）   sub_rate 0.033/日（**×0.68**）
        rpm       0.133/日（×1.23）   density  0.100/日（×1.05）

    **順位は変わりませんでした** —— `sub_rate` が 4日 早い → **5日 早い**。
    **回転を 3分の2 に落としても勝ちます。** 動かしているのは天井のほうです。

    だから既定では掛けません（掛けると水準がずれて、
    「過去の配分（＝頭の3行の日付）」の行が**頭の日付と一致しなくなります** ——
    実測 2026-12-23 → 2027-01-05。**同じプログラムが同じ日に別の日付を出す形**は、
    この道具がいちばん嫌っている壊れ方です）。

    **代わりに、回転そのものを表で出します。** 実測 2026-08-27 の
    `sub_rate` は**今後14日 に1件も閉じられません**（いちばん早い判定日が
    2026-09-16 ＝ 20日 先。他の3本は density 08-28 ／ rpm 09-01 ／
    per_video 09-05）。**「いちばん早い」は「次の2週間で動く」ではありません。**
    そこを黙って出すと、`sub_rate` に立て続けて 20日 間 何も動かない回が続きます
    —— 2026-08-27 06:1x の回が別の道から測った
    「`sub_rate` の実験は 15倍 遠い・**約20周** かかる」と同じ話です。

    ## 覆る条件

    - **`sub_rate` と `rpm` が `MIN_N`（3件）に届いたら**、p と g が自前になるので
      順位が天井だけで決まらなくなります。そのとき `--alloc-speed` を撃ち直して、
      順位が変わるかを見ること（変われば既定を掛ける側にする）
    - **予定表が過去に追いついたら**（`forward()` の 14日 窓の比が 0.8 以上）、
      この表は要りません

    ## なぜ別の口にしたか（**「毎回は撃たない」は 2026-08-28 に取り消しました**）

    軌跡は1本ごとに **2〜4秒** かかります（2026-08-28 に測り直した。それまでは 15〜20秒）。頭の3行では
    「過去の配分」と「台帳の配分」の**2本だけ**を解いて差を出しています。
    ここは**そこからさらに腕べつ**に解きます。

    **ここには「腕4つ ＝ 60〜80秒 なので毎回は撃たない」と書いてありました。
    その根拠はもうありません** —— `day_cap.cap()` を畳んだ 2026-08-28 の実測で
    **24秒**（それまで 3〜6分）。**毎回 撃ってよい費用です。**

    取り消しの条件は、08/28 14:4x の回が先に書いていました ——
    「**2周 続けて撃って、答え（いま `sub_rate`）が変わらないかを見ること。
    変わらないなら『毎回は撃たない』を外してよい**」。**満ちました**:

        2026-08-27        いちばん早いのは `sub_rate`
        2026-08-28 14:4x  いちばん早いのは `sub_rate`
        2026-08-28 19:5x  いちばん早いのは `sub_rate`   ← 3周 連続・順位も同じ

    **日付そのものは動きます**（08/26 の sub_rate 2027-01-07 → この回 2027-01-15）。
    動かないのは**順位**のほうで、`--alloc` が答えるのはそちらです。

    **覆る条件**: 順位が周ごとに入れ替わりはじめたら、それは
    「配分が毎周ぶれている」＝ `arm_speed.planned()` の側の話です。
    そのときは撃つ回数ではなく、**planned() が何本の前提で割っているか**を見ること
    （実測 24件。1件足すと 4% 動く ＝ **1件の増減で順位が変わりうる細さ**）。

    ## 何を解いているか

    台帳（`config/hypotheses.yaml` の開いた前提）の配分に、
    **前提を1件だけ足したら**どうなるかを腕ごとに解きます。
    これは「次に立てる1件」そのものなので、**この回に実際にできる手**です。

    実測 2026-08-26 —— 過去の配分 2026-12-28 に対し、台帳の配分は
    **2027-01-13（+17日）**でした。`share` は**閉じた前提の割合 ＝ 過去の写し**で、
    未来を決めているのは開いた前提のほうなので、
    **上の日付は台帳が用意していない世界のもの**です。

    **API は0単位です**（積んである最後の点で解き直すだけ）。
    """
    points = _points()
    if not points:
        print("[eta] 積んだ点がありません。**まず `python scripts/eta.py` を撃つこと。**")
        return 1
    m = dict({k: v for k, v in points[-1].items()
              if k not in _REFLECT_IGNORE or k == "at"})
    a = analyse(m, points)
    m["per_video_now"] = a["per_video_now"]
    sup = supply_state()
    arms = _capped_arms(a, supply=sup)
    kw = dict(supply=sup, points=points, today=today_jst())

    pln = arm_speed.planned()
    past = {k: (v.get("share") or 0.0) for k, v in arms.items()}
    print("=== 次の前提を、どの腕に立てるのがいちばん早いか ===")
    print("  **API は0単位**（積んである最後の点で解き直すだけ）。1本 2〜4秒。")
    # --- **どの腕の数が「その腕の実測」で、どれが代用か**（2026-08-26 に足した） ---
    #     `arm_speed.arm()` は、その腕で閉じた前提が `MIN_N`（=3）に満たないと
    #     **全体の当たり確率と伸び幅で代用**します。代用の腕どうしは
    #     `focus_rate` が同じ値になるので、**下の順位は「天井の遠さ」だけで
    #     決まっている**ことがあります。**黙って埋めると、薄い腕ほど自信ありげに見えます。**
    #     実測 2026-08-26: 自前は `per_video`（12件）と `density`（5件）だけ。
    #     `rpm` は1件、`sub_rate` は2件で、**どちらも代用**です。
    src = []
    for k in arm_speed.ARMS:
        v = arms.get(k) or {}
        src.append(f"{k} {v.get('n', 0)}件"
                   + ("（**代用**）" if v.get("source") != "自前" else ""))
    print("  腕べつに閉じた前提: " + " ／ ".join(src)
          + f"  ← {arm_speed.MIN_N}件 未満は**全体の値で代用**しています"
          "（代用どうしは速さが同値になるので、順位が天井の遠さだけで決まります）")

    # --- **その「天井の遠さ」そのものを出す**（2026-08-27 に足した） ---
    #     上の1行が「順位は天井の遠さだけで決まります」と言っているのに、
    #     **天井は1つも印字されていませんでした。** 理由と実測は `cap_lines`。
    for line in cap_lines(arms, indent="    "):
        print(line)

    # --- **腕べつの「予定表 θ」を出す**（2026-08-27 に足した） ---
    #     代用の腕どうしは p も g も θ も同値になるので、上の1行だけでは
    #     **順位が天井の遠さだけ**で決まります。台帳の予定表（開いている前提の
    #     「判定できる日」）は、腕によって回転がまるで違うと言っています ——
    #     この日の実測では `sub_rate` だけが**今後14日 に1件も閉じられません**。
    #     **既定では掛けません**（掛けると水準がずれて「過去の配分（＝頭の3行の
    #     日付）」が頭と食い違う。docstring の実測を読むこと）。`--alloc-speed` で掛かります。
    by_arm, sw = _arm_rotation()
    speed = (sw.get("weights") or {}) if with_speed else None
    if sw.get("missing"):
        print(f"  [!] **腕べつの回転が取れません**: {sw['missing']}"
              " —— 4本とも同じ θ（全体の実測）で解いています。"
              "**順位は天井の遠さだけで決まっているかもしれません。**")
    else:
        w = sw.get("weights") or {}
        raw = sw.get("raw") or {}
        cells = " ／ ".join(
            f"{k} **{raw.get(k, 0.0):.3f}/日**（×{w.get(k, 1.0):.2f}）"
            for k in arm_speed.ARMS)
        print(f"  腕べつの回転（台帳の予定表・今後{sw['window']}日 に判定できる件数 ÷ {sw['window']}）: "
              + cells)
        near = [k for k in arm_speed.ARMS
                if not [h for h in ((by_arm.get(k) or {}).get("horizons") or [])
                        if h.get("days") == 14 and h.get("n")]]
        if near:
            print(f"    [!] **今後14日 に1件も閉じられない腕: {', '.join(near)}**"
                  " —— 下の『いちばん早い』がその腕を指していても、"
                  "**次の2週間は1日も動きません**（その腕の`判定できる日`が全部 14日 より先）。")
        back = (by_arm.get(arm_speed.ARMS[0]) or {}).get("backward")
        if with_speed:
            print("    **下の日付は、この回転を掛けた側です**（`--alloc-speed`）。"
                  "頭の3行（`python scripts/eta.py`）は掛けていないので、"
                  "**『過去の配分』の行は頭の日付と一致しません。**")
        else:
            print("    **下の日付は、この回転を掛けていません**"
                  + (f"（4本とも θ＝{back:.2f}/日 ＝ 全体の実測）" if back else "")
                  + "。掛けた版は `--alloc --alloc-speed`。"
                  " **実測 2026-08-27 と 2026-08-30: どちらも掛けても順位は変わりませんでした**"
                  "（`sub_rate` のまま・差は 08-27 が 4日 → 5日、08-30 が 3日 → 3日）。"
                  "**×0.68 に落としても勝つ ＝ この順位を決めているのは回転ではなく天井のほうです。**"
                  " **08-30 に測り直したのは、3日 前の1点で「掛けない」を決め続けていたから**です ——"
                  "`--alloc --alloc-speed` は 24秒・API 0単位 なので、"
                  "**この行が古いと思ったら、思った回が測り直すこと。**")

    def _solve(share: dict[str, float], label: str) -> float:
        t = trajectory(m, a, arms=_realloc_arms(arms, share, speed), **kw)
        d = t["date"].isoformat() if t["date"] else "出ません"
        print(f"  {label:36s} {d}  ({_share_str(share)})", flush=True)
        return t["days"]

    base_days = _solve(past, "過去の配分（＝頭の3行の日付）")
    if not pln.get("n"):
        print("  [!] 台帳に腕の付いた開いた前提がありません。**比べる相手がいません。**")
        return 1
    now_days = _solve(pln["share"], "台帳の配分（いま開いている前提）")
    print(f"  → その差 **{now_days - base_days:+,.0f}日**"
          "（上の日付は、台帳が用意していない配分で解かれています）")

    # **「次の1件」は、いまの分母に1を足した配分です。** 分母が14件なら
    #     1件は 7pt —— **この回に実際にできる手の大きさ**そのもの。
    n = pln["n"]
    best = (now_days, "そのまま（足さない）")
    # **腕ごとの日数を捨てないこと**（2026-08-29 に足した）。
    #     下の `ban_lines` が1位を止めた回に、**次に読むべき行がありません** ——
    #     表は上に出ていますが、「いちばん早いのは」の1行だけを読む手順
    #     （この文書の冒頭「見出しと箇条書きだけ」）には届きません。
    #     実測 2026-08-29: 1位 `sub_rate` が禁じられ、回の側が表を
    #     縦に読み直して 2位 を手で拾っています。
    days_by_lever: dict[str, float] = {}
    print(f"\n  --- そこへ **前提を1件** 足したら（いま {n}件 ＝ 1件は {1 / (n + 1):.0%}）---")
    for lever in arm_speed.ARMS:
        share = {k: (pln["share"].get(k, 0.0) * n + (1 if k == lever else 0)) / (n + 1)
                 for k in arm_speed.ARMS}
        d = _solve(share, f"次の1件を `{lever}` に")
        days_by_lever[lever] = d
        # **引き代0の腕を、同着の顔で並べないこと。** `density` は ×1.00 で
        #     「何をしても日付は動かない」と軌跡の側が言っているのに、ここでは
        #     `per_video` と同じ日付で並びます（実測 2026-08-27・どちらも 2027-01-07）。
        #     **同着に見えるのは「効く」からではなく、5% の付け替えでは
        #     どちらも動かないから**です。理由は `cap_lines`。
        arm = arms.get(lever) or {}
        cap = arm.get("cap")
        if cap is not None and cap <= 1.0:
            # **正本は `cap_caveats` ひとつ**（2026-08-28）。ここと `cap_lines` が
            #     別々に文言を持っていると、片方だけが直る ——
            #     この repo がいちばん多く踏んでいる形です（`CLAUDE.md`
            #     「同じことを2か所が別々に言っていて、片方しか読まれていない」）。
            caveats = cap_caveats(lever, arm)
            if caveats:
                print(f"      ↑ **`{lever}` は天井 ×{cap:,.2f}。"
                      "上の日付は動きませんが、それは**この道具の作り**の話です**"
                      "（軌跡がこの面しか歩かない）")
                for c in caveats:
                    print(f"          [!] {c}")
            else:
                print("      ↑ **この腕は天井 ×1.00（引き代なし）です。**"
                      "立てても、閉じても、上の日付は1日も動きません")
        if d < best[0]:
            best = (d, lever)
    # **符号は「早い／遅い」の字で出すこと。** `+6日` は
    #     「6日 早い」とも「6日 遠のく」とも読めます —— この道具の頭の3行は
    #     `+17日` を「遠のく」の意味で使っているので、混ぜると逆に読まれます。
    gap = now_days - best[0]
    print(f"\n  **いちばん早いのは `{best[1]}`**"
          + (f"（そのままより **{gap:,.0f}日 早い**）" if gap >= 1
             else "（そのままと同じ。**どの腕に立てても日付は動きません**）"))
    # **台帳が「その腕には立てるな」と言っていないか**（2026-08-29 に足した）。
    #     この名指しは 08/27 から **5回 続けて `sub_rate`** で、
    #     **5回とも回の側が手で打ち消しています。** 打ち消す根拠は
    #     台帳の `next_if_false` にあり、**機械が読める字で書いてあります。**
    #     読まないので、毎回 人が思い出していました。
    #     **道具が言わないものは、毎回 人が思い出すことになります。**
    ban = arm_speed.ban_lines(best[1])
    for line in ban:
        print(line)
    # **止めるだけで終わらせないこと**（2026-08-29 に足した）。
    #     `next_if_false` は「そこに立てるな」の続きに **どこへ振り直すか**まで
    #     書いています（実測 08/29: 「per_video か rpm へ振り直す」）。
    #     ところが `ban_lines` は `line` をそのまま貼るだけで、
    #     **この道具が持っている腕べつの日数と突き合わせていません。**
    #     **1位が禁じられている回に、次に読むべき行が無い**のがそれまでの形でした。
    #     ここで出すのは「禁じられていない腕のうち、いちばん早いもの」1行だけ。
    #     **覆る条件**: 全腕に ban が立ったら（＝ `rest` が空）、
    #     出せるものがありません。そのときは台帳のほうが袋小路なので、
    #     **`next_if_false` を書き直す回**です（この関数ではなく `config/` の話）。
    # **側で限定された禁止は、腕を塞ぎません**（2026-08-30 に足した）。
    #     `sub_rate` の外れは 2件 とも**中身の側**で、配信の側は 0件。
    #     それでも `ban_lines` が空でないというだけで腕ごと落としており、
    #     **配信の側に立てる道まで塞いでいました** ——実測で **3日**
    #     （`sub_rate` 2027-01-18 対 `per_video` 2027-01-21）。
    #     見るのは `blocks_arm`（＝側の書いていない禁止が1件でもあるか）です。
    if arm_speed.blocks_arm(best[1]):
        rest = sorted(
            ((d, k) for k, d in days_by_lever.items()
             if k != best[1] and not arm_speed.blocks_arm(k)),
            key=lambda t: t[0])
        if rest:
            d2, k2 = rest[0]
            gap2 = now_days - d2
            print(f"  → **禁じられていない腕でいちばん早いのは `{k2}`**"
                  + (f"（そのままより **{gap2:,.0f}日 早い**"
                     f"・`{best[1]}` との差は {d2 - best[0]:,.0f}日）" if gap2 >= 1
                     else f"（そのままと同じ。`{best[1]}` との差は"
                          f" {d2 - best[0]:,.0f}日）")
                  + "。**この行は表を縦に読み直さなくても済むように出しています** ——"
                  " 上の `next_if_false` が振り直し先を名指ししているなら、"
                  "**そちらが優先**です（台帳のほうが、この道具より事情を知っています）。")
        else:
            print("  → **禁じられていない腕がありません。**"
                  " 台帳の `next_if_false` が全腕を塞いでいます ——"
                  "**そのときは腕を選ぶ話ではなく、`config/hypotheses.yaml` の"
                  "`next_if_false` を書き直す回**です。")
    elif ban:
        # **側で限定された禁止は、腕を落としません。**
        #     ただし黙って通すと、上に貼った禁止の行だけが残って
        #     「1位は禁じられている」と読まれます（それが 5回 起きた形）。
        sides_banned = sorted({r["side"] for r in arm_speed.standing_bans().get(best[1], [])
                               if r.get("side")})
        ja = "／".join(arm_speed.SIDE_JA[x] for x in sides_banned)
        print(f"  → **上の禁止は {ja} だけに掛かっています。"
              f"`{best[1]}` は1位のままです** ——"
              f" 立てる1件を **{ja} 以外**にすること"
              f"（`config/hypotheses.yaml` の `side:`）。"
              " **腕ごと落とすのは、側の書いていない禁止があるときだけ**です"
              "（`arm_speed.blocks_arm`）。")
    # **勝った腕の天井が実測でないなら、勝ちの理由がそこにあります。**
    #     この順位は天井の遠さで決まる（上の docstring）ので、
    #     **天井が作り物なら、勝ちも作り物**です。軌跡の側には同じ注意が
    #     既にありました（`_trajectory_lines` の `[!] … 測った天井ではありません`）——
    #     **`--alloc` にだけ無かった**ので、ここに置きます。
    top_arm = arms.get(best[1]) or {}
    if best[1] != "そのまま（足さない）" and top_arm.get("cap") \
            and not top_arm.get("cap_measured"):
        print(f"  [!] ただし `{best[1]}` の天井 ×{top_arm['cap']:,.2f} は"
              f"**測った天井ではありません**（{top_arm.get('cap_why', '')}）。"
              "**この順位は天井の遠さで決まっています**（上の docstring）ので、"
              "**天井が作り物なら、勝ちも作り物**です。"
              f"この腕で閉じた前提は {top_arm.get('n', 0)}件"
              f"（{arm_speed.MIN_N}件 で自前になります）——"
              "**1件 閉じるだけで、この順位そのものが引き直せます。**")
    # **腕を選んだあとに、まだ1つ選ぶものが残っています**（2026-08-29 に足した）。
    # 上の表は「どの腕に立てるか」しか言いません。同じ腕の中で、
    # **その回に何をいじるか**（動画の外側か・中身か）で当たり方が桁ちがいです。
    # 数と「日付を動かさない理由」は `src/arm_speed.sides()`。
    try:
        for _l in arm_speed.side_lines():
            print(_l)
    except Exception as _exc:                                   # noqa: BLE001
        print(f"  （側べつの実測は出せませんでした: {_exc}）")
    print("  立てるときは `config/hypotheses.yaml` に `lever:` を**その腕で**、"
          "`side:` を **`dist`（配信の側）／`content`（中身の側）／`infra`（道具の側）**で書くこと ——"
          " `lever:` が空欄だと `arm_speed.closed()` が閉じたときに行ごと飛ばし、"
          "`side:` が空欄だと上の2つの数から**その1件だけが黙って消えます**。")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="月20万に届く日を予測して積む")
    ap.add_argument("--no-record", action="store_true", help="data/eta.jsonl に積まない")
    ap.add_argument("--offline", action="store_true", help="API を叩かず、積んである最後の点から出す")
    # **周の終わりに打つ**（オーナー指示 2026-08-20「毎回その予測に反映して」）。
    # `run_marker.py --ship` が自動で呼びます。**手で打つのは、ship の外で入力を動かした回だけ。**
    ap.add_argument("--reflect", action="store_true",
                    help="周の終わり: この回で動いた入力を予測へ入れ直し、日付の前後差を残す")
    ap.add_argument("--note", metavar="1行", help="--reflect に添える1行（何を入れ直したか）")
    # **毎回は撃ちません**（軌跡1本 2〜4秒 × 腕4つ）。頭の3行が
    # 「過去の配分」と「台帳の配分」の差を出すので、**その差が気になった回だけ。**
    ap.add_argument("--no-frozen", action="store_true",
                    help="「その腕を凍らせたら何日 遠のくか」を測らない"
                         "（軌跡1本ぶん 2〜4秒 を省く。**普通は付けないこと** ——"
                         " 付けると『十分でない腕』と『要らない腕』が区別できません）")
    ap.add_argument("--alloc", action="store_true",
                    help="次の前提をどの腕に立てるのが早いか、腕べつに解く（API 0単位・**実測 24秒**（2026-08-28 に `day_cap.cap()` を畳むまでは 4分））")
    ap.add_argument("--alloc-speed", action="store_true",
                    help="`--alloc` を、**腕べつの回転**（台帳の予定表・"
                         "`arm_speed.speed_weights()`）を掛けて解く。"
                         "**水準がずれるので『過去の配分』の行は頭の日付と一致しません** ——"
                         " 見るのは順位だけ。2026-08-27 の実測では順位は変わりませんでした")
    args = ap.parse_args()

    if args.alloc or args.alloc_speed:
        return alloc_search(with_speed=args.alloc_speed)

    if args.reflect:
        return reflect(args.note, record=not args.no_record)[0]

    if args.offline:
        if not LOG.exists():
            print("[eta] 積んだ点がありません。--offline は使えません。")
            return 1
        # **反映の行を掴まないこと**（`_points()` が既に外しています）。
        m = _points()[-1]
        print("[eta] **積んである最後の点で出しています（いまの実測ではありません）**")
    else:
        try:
            m = _measure()
        except Exception as exc:  # noqa: BLE001 — 予測で回を止めない
            print(f"[eta] 実測を取れませんでした: {type(exc).__name__}: {exc}")
            print("[eta] **回は止めないこと。** `--offline` で最後の点から読めます。")
            return 1

    points = _points()
    if args.no_frozen:
        global FROZEN_ARMS
        FROZEN_ARMS = False
    _s = solve(m, points)
    a, sup, pl, tr = _s["a"], _s["sup"], _s["pl"], _s["tr"]
    prev = points[-1] if points else None
    # **この回が印字した行を、そのまま控えておく**（`flagged()` が尾へ運びます）。
    # `print` を差し替えているだけで、出る中身も順番も1文字も変えていません。
    said: list[str] = []

    def say(line: str) -> None:
        said.append(str(line))
        print(line)

    for line in headline(pl, prev, tr, points):
        say(line)

    for line in report(m, a):
        say(line)
    row = _row(m, a, pl, tr, sup)
    # **`--offline` の点だと分かる形で積む**（2026-08-20）。中身は最後の実測の**写し**で、
    # 新しい実測ではありません。印が無いと、次の回は写しを実測として数えます
    # （`_points()` の履歴は、伸び率の分母になります）。
    if args.offline:
        row["offline"] = True
    for line in _drift(row):
        say(line)
    # **周の中で動いた入力は `_drift` には出ません**（あれは点どうしの比較）。
    # 反映の読み口はこちら。**残す所と読む所の両方が要ります。**
    for line in _reflect_recap():
        say(line)
    # **「予測 → 腕を選ぶ → 進む」の、選んだ側の実績**（オーナー指示 2026-08-19 21:2x）。
    # 1周ごとに動くのは日付ではなく**ここ**です（`src/levers.py` の説明）。
    for line in levers.report(ROOT / "data" / "runs.jsonl"):
        say(line)
    # **腕を「日数の差」で並べる**（2026-08-20 16:0x）。ここが無いと、
    # 引く腕は `binding`（どの床が遅いか）という診断からしか決まりません。
    for line in _report_levers(pl):
        say(line)
    # **「×2 にしたら」の表の、すぐ下に軌跡を置くこと。**
    #     表だけを見た読み手は「2倍にすればいい」で終わります。
    #     2倍に何日かかるかは、ここにしかありません。
    if tr is not None:
        for line in _report_trajectory(tr, pl):
            say(line)
    # **段取りは、いちばん最後に出すこと**（オーナー指示 2026-08-20 06:2x）。
    # 読み手が最後に見たものが、そのまま次の回の入口になります。
    # ここより後ろに「届きません」を置かないこと。
    for line in _report_plan(m, a, pl):
        say(line)
    # **最後にもう一度、日付と腕。** 真ん中を読み飛ばしても、ここだけで決まる形にする。
    for line in headline(pl, prev, tr, points):
        print(line)
    # **`[!]` を尾へ運ぶ**（2026-08-26・最適化の回）。日付は 08-20 に運びましたが、
    # **欠陥の名指しは真ん中に置いたまま**でした。実測: `[!]` 10本／頭にも尾にも 0本。
    for line in flagged(said):
        print(line)
    print("  **この回の作業は、上の日付を動かすものを選ぶこと。**"
          " 出したら `run_marker.py --ship \"…\" --lever <腕> --moves <見込みの日数>`。")

    if not args.no_record:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"\n[eta] 積みました: {LOG.relative_to(ROOT)}（{sum(1 for _ in LOG.open(encoding='utf-8'))}点目）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
