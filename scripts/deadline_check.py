#!/usr/bin/env python3
"""**その期限までに、判定に要るデータは存在しうるか。**

## なぜ要るか（2026-08-25 に足した）

`config/hypotheses.yaml` は「いつ判定するか」（`deadline`）と「何が起きていたら
外れか」（`falsified_if`）を持っています。**持っていないのは「その条件を当てる
データが、その日までに在るか」です。** 期限は、置いた回の勘で決まっていました。

実測（この道具を書く前）:

    A/B の仮説2件（期限 09/05）  処置群は 08/23 以降に作った本
                                  作ってから公開まで 中央値 13.4日 → 公開は 08/30 以降
                                  落ち着くのに 7日 → **判定できるのは 09/06 以降**
    「量産テンプレート判定を避けられる」（期限 09/01）
                                  条件は「**収益化を申請できる段階で**審査に落ちる」
                                  登録者はあと 999人 → **09/01 に起こりようがない**

**どちらも、期限が来た日に「まだ分からない」と言うことが最初から決まっています。**
`scripts/drift.py` は「直近20回の verdict **0件**」と出し、`eta.py` は
「軌跡の腕が動くのは前提を1件閉じたときだけ」と出します。
**閉じられない期限を並べているあいだ、到達日は1日も動きません。**

## 何を数えるか

前提に `needs:` を書くと、ここが**判定できる最早の日**を出します。

    needs:
      - kind: now                いま手元のデータだけで判定できる
      - kind: accrual            台帳が n に積み上がるのを待っている
        count_expr: "..."        いまの量を返す python 式（このリポジトリの中の式です）
        need: 6
        since: "2026-08-24"      この日から積み始めた（伸び率をここから出す）
      - kind: published_group    群の本が「公開 → 落ち着く → Analytics に出る」のを待つ
        created_after: "2026-08-16"
        count: 13
        settle_days: 7
      - kind: after              その日が来るのを待っているだけ
        on_date: "2026-08-29"      **`on:` にしないこと** —— YAML 1.1 は `on` を
        plus_lag: true             **真偽値 `True`** として読むので、値が消えます
      - kind: external           こちらの手では起こせない出来事を待っている
        what: "収益化の審査（登録者 1,000人）"

**`needs:` の無い前提は `[??]` で出します。** 黙って通さないこと ——
**この欠陥は、黙って通っていたから8日ぶん積みました。**

## Analytics の遅れを必ず引くこと

`data/scan.jsonl` も `data/views.jsonl` も **YouTube Analytics の日次**で、
実測で **3日 遅れています**。「公開から7日たった本」を判定日に数えると、
**報告されているのは4日ぶんだけ**です。だから

    判定できる日 = 公開日 + 落ち着く日数 + **Analytics の遅れ**

`src/ab_split.settle_by()` はこの遅れを引いていませんでした（同じ回に直した）。
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import endcard_verdict  # noqa: E402  （終端の型で処置群を絞る。`endcard:` のある要件だけ）
from src import settle as settle_mod  # noqa: E402  （`sys.path` を通した後でないと読めません）

JST = timezone(timedelta(hours=9))

#: Analytics の遅れが読めなかったときの控え。**0 にしないこと** ——
#: 0 にすると「遅れは無い」と言い切ることになり、いちばん危ない側へ倒れます。
FALLBACK_LAG_DAYS = 3

#: `needs` に `settle_days` が書いていないときの既定。**実測は `src/settle.py`**。
#: **ここに数を書かないこと（2026-08-26）** —— 元は `need.get("settle_days", 7)` と
#: 直に 7 が入っていて、`src/settle.py`（72時間で判定は入れ替わらない）と別々でした。
DEFAULT_SETTLE_DAYS = settle_mod.SETTLE_DAYS


def today_jst() -> date:
    return datetime.now(JST).date()


def analytics_lag_days(as_of: date | None = None) -> int:
    """**実データが何日 遅れているか。** 実測は `src/settle.py` が持ちます。

    **ここで数え直さないこと（2026-08-26）** —— 同じ量を `src/judgeable.py` が
    `= 3` のべた書きで持っていて、**A/B 4件だけ1日 楽観**に出ていました。
    """
    return settle_mod.analytics_lag_days(as_of or today_jst())


def analytics_lag_band() -> int:
    """**遅れそのもののゆらぎ（日）。**実測は `src/settle.analytics_lag_band()`。

    **遅れは1日の中で動きます**（Analytics が日の途中で新しい日を出すため）。
    実測 438観測で **3日が 381・4日が 57**、
    **1日のうちに両方を観測した日が 6日**（08/18〜08/22・08/26）。

    だから遅れを足して作った判定日は、**同じ日でも走った時刻で1日ずれます** ——
    そしてこの道具は、そのずれを見るたびに「期限を書き換えること」と言っていました。
    実測（2026-08-26 06:0x）: **「1日 後ろ」と言われた5件が、5件とも遅れを足す種類**
    （`after` ×2・`group_key` ×2・`published_group` ×1）。**1件も例外がありません。**

    `Answer.slack` はまさにこの churn を止めるために置かれた欄ですが、
    掛かっていたのは伸び率の推定（`accrual`）だけでした。ここで遅れ側にも掛けます。
    """
    return int(settle_mod.analytics_lag_band().get("band") or 0)


def _rows(name: str) -> list[dict]:
    path = ROOT / "data" / name
    try:
        return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
    except Exception:                                          # noqa: BLE001
        return []


def latest_views() -> dict[str, int]:
    """`video_id` → **いままでに観測した最大の再生数**（`data/views.jsonl`）。

    `views.jsonl` は `videos.list` の累計なので、**Analytics の3日遅れは掛かりません。**
    """
    out: dict[str, int] = {}
    for r in _rows("views.jsonl"):
        vid, v = r.get("id"), r.get("views")
        if vid and isinstance(v, (int, float)):
            out[str(vid)] = max(out.get(str(vid), 0), int(v))
    return out


def uploaded() -> list[dict]:
    return _rows("uploaded.jsonl")


def long_ids() -> set[str]:
    """長尺の `video_id`（`data/batch_runs.jsonl` の `long: true` から）。

    **台帳に残っている回のぶんだけ**です。それより前の長尺は入りません。
    """
    out: set[str] = set()
    for r in _rows("batch_runs.jsonl"):
        if r.get("long"):
            for x in r.get("results", []) or []:
                if x.get("video_id"):
                    out.add(str(x["video_id"]))
    return out


#: `count_expr` から使えるもの。**このリポジトリの中の式です**（外から来ません）
def ab_members(name: str) -> dict[str, int]:
    """`src/ab_split.EXPERIMENTS` の A/B の、**群べつ本数**（予約ぶんを含む）。

    `src/judgeable.members()` から数えるので、**再生が付かない枠の本は落ちます**
    （`src/day_cap.live_ids`）。`count_expr` から呼びます:

        count_expr: "min(ab_members('request_form').values())"

    **`min` で数えること。** 片群だけ積んでも判定はできません。
    """
    from src import judgeable

    return {g: len(v) for g, v in judgeable.members(name).items()}


def deep_short_days() -> int:
    """**深い題ショートの前提が「判定できる日」の数**（`falsified_if` は 3日 要る）。

    数えるのは「その公開日に、`s-` でない本と `s-` の本が**どちらも1本以上**、
    しかも両方 `data/video_forms.json` で『ショート』と分類されている日」。

    ## なぜ本数と別に要るか（2026-08-26 夜に数えて足した）

    その前提の `needs` は本数しか見ておらず、**本数が満ちても判定できません** ——
    `falsified_if` が「**使える日が 3日 未満なら判定できない**」と書いているのは、
    1本あたり再生を動かしている最大の要因が**その日に何本 出したか**だからです
    （同じ題の種類で ×3.3 散る。主張している差は ×1.2）。

    実測 2026-08-26: 本数は「16本 足りています」なのに、**使える日は 0日**でした
    （公開済みの `s-` でない本 7本のうち、分類が付いているのは **0本**。
    Analytics は3日遅れなので、08/25・08/26 の本にはまだ何も付いていません）。
    **期限はその日まで縮められていて、明日には「期限切れ・判定ゼロ」**でした。
    """
    forms = {}
    fp = ROOT / "data" / "video_forms.json"
    if fp.exists():
        try:
            forms = (json.loads(fp.read_text(encoding="utf-8")) or {}).get("forms") or {}
        except (OSError, ValueError):
            forms = {}
    last: dict[str, dict] = {}
    for r in uploaded():
        if r.get("video_id") and r.get("at"):
            last[str(r["video_id"])] = r          # **後の行が勝ち**（付け替えの控え）
    days: dict[str, set[str]] = {}
    for vid, r in last.items():
        if forms.get(vid) != "ショート":
            continue
        day = str(r["at"])[:10]
        if day > str(date.today()):
            continue
        side = "対照" if str(r.get("topic", "")).startswith("s-") else "処置"
        days.setdefault(day, set()).add(side)
    return sum(1 for sides in days.values() if len(sides) == 2)


EXPR_NS = {"json": json, "rows": _rows, "date": date, "ab_members": ab_members,
           "deep_short_days": deep_short_days,
           "latest_views": latest_views, "uploaded": uploaded, "long_ids": long_ids}


@dataclass
class Answer:
    """1つの `needs` に対する答え。"""

    #: 判定できる最早の日。`None` ＝ この道具では出せない（外の出来事・伸び率ゼロ）
    ready: date | None
    #: なぜその日か。**必ず数字を入れること**
    why: str
    #: 待っても来ない種類か（外の出来事）
    unreachable: bool = False
    #: **`ready` の日のうち、この時刻まで計器が読めない**（`None` ＝ 一日じゅう読める）。
    #:
    #: **2026-08-28 03:5x に足した。** `_quota_gate` は「枠が戻るのは
    #: **08/28 16:00 JST**」と**文字では**言っていましたが、機械が読める欄は
    #: `ready`（日付）だけでした。**16:00 という時刻が、そこで落ちます。**
    #: その日の 00:00〜16:00 に走る回は全部、`arm_speed.next_close()` から
    #: 「**今日が判定できる日**」を受け取り、`eta.py` の頭3行に
    #: 「**この回は `verdict` で日付が動かせます**」と出ます。**16時間ぶんの嘘**です。
    #:
    #: 実測 2026-08-28 03:1x: `data/views.jsonl` のいちばん新しい点は
    #: **08-27 16:34 JST**、要件は 08-27 22:00 JST 以降の点、
    #: 取り直す `snapshot.py` は 403（214回 観測）。**判定は1つも下せません。**
    #: それでも `eta.py` は「期日の来た前提があります → この回は `verdict` で
    #: 日付が動かせます」と出しました。
    #:
    #: これは `unready_claims()` が 2026-08-26 に塞いだ穴の**1段 深いところ**です
    #: —— あちらは「日が出せない」を捕まえ、ここは「**日は出たが、その日の中で
    #: まだ来ていない**」を捕まえます。
    ready_at: datetime | None = None
    #: **その日が「推定」のときの、意味のあるゆらぎ（日）。**（2026-08-26 に足した）
    #:
    #: 伸び率から解いた日（`accrual`）は、**その回の実測でしか出せません。**
    #: 実例: 同じ前提の判定日が 11-13 → 11-09 → 11-16 → 11-22 と動き、
    #: **3回とも「期限がずれています」と言われ、3回とも期限だけを書き換えました。**
    #: 動いたのは伸び率の見積りで、**前提も、届く日も、1日も動いていません。**
    #: 3回ぶんの `fix` は、到達日を1日も動かしていない churn です。
    #:
    #: だから**点ではなく帯**で見ます。帯の中なら「ずれ」と言いません。
    slack: int = 0
    #: **待っている側に渡す、具体的な次の手**（2026-08-27・最適化の回）。
    #:
    #: `warming` の行は「待てば出ます」しか言えませんでした。ところが
    #: **待ち方は2つあります** —— 時刻がまだ来ていない（＝本当に待つだけ）と、
    #: **時刻は来たがデータを取っていない**（＝待っても永久に出ない）。
    #: 後者を「待つこと」と印字すると、次の回は何もせずに帰り、
    #: **その前提は期限を過ぎたまま止まります。** ここに手を入れておくと、
    #: `lines()` がそのまま出します。
    todo: str = ""

    #: **`ready` が、この帯のぶん「早くなりうる」日数。** `None` ＝ `slack` と同じ。
    #:
    #: **帯は、いつも左右対称ではありません**（2026-08-27 夜・最適化の回）。
    #: 遅れから作った日はその典型で、`analytics_lag_band()` の実測は
    #: **3日が 381観測・4日が 57観測。2日は1度もありません。**
    #: そして印字する `ready` は**小さいほう（3日）で作っています** ——
    #: つまりその日は**もう最速**で、帯は **+1／−0** です。
    #:
    #: それを ±1 として扱うと、`slips` が `ready - 1` まで許します。
    #: **実測でそこが割れました**（`title_form`）:
    #:
    #:     `src/judgeable.py`      16本目 08/31 ＋ 3 ＋ 3 → **09/06 へ延ばすこと**
    #:     `deadline_check`        判定できるのは 09-06（±1日）→ **書き換えないこと**
    #:
    #: **同じ機械の2か所が、同じ数から逆の指示**を出していました。
    #: `docs/JOURNAL.md` が何度も書いている形です。**`judgeable` が正しい** ——
    #: 遅れが 2日 だった観測が1つも無い以上、09/05 に判定できる目は
    #: **ありません**。だから下向きの幅を別に持ちます。
    slack_down: int | None = None

    #: **この答えを出した伸び率**（`accrual` だけ。他は `None`）。
    #: `record_estimates()` が積み、次の回の帯がこれの散らばりから決まります。
    rate: float | None = None
    #: 伸び率を積むときの鍵（`count_expr`。前提ごとに一意で、動かない）
    rate_key: str = ""
    #: **その回に数えた実数**（`accrual` だけ）。2026-08-27 夜・最適化の回に足した。
    #:
    #: `rate` だけを控えていたので、**「その数が今日は1つも増えていない」を
    #: 誰も言えませんでした。** `rate = have / (今日 - since)` は**生涯の平均**で、
    #: 積みが完全に止まっても分母が伸びるぶんゆっくり下がるだけなので、
    #: **止まった当日も「あと1日」と出続けます。**
    #:
    #: 実例（2026-08-27 22:3x・前提「長尺の生成が落ちる主因は…」）:
    #:
    #:     台帳     要 6 ／ いま 5（3日で **1.67/日**）→ **あと 1日 ＝ 08-28**
    #:     実物     この要件が数えるのは**長尺の生成失敗**。
    #:              08/24 は 7/21 しか通らず（失敗 14）、
    #:              **08/26 は 25/28（89%）・08/27 は 15/15（100%）**
    #:              → **今日の失敗は 0件。** 1.67/日 は 08/24〜08/26 の平均です
    #:
    #: **`have` を控えれば、次の回は「前の点からいくつ増えたか」で解けます。**
    #: それが本当の伸び率で、`rate` はその上限にすぎません。
    have: int | None = None


#: 伸び率の控え。**1鍵1日1行**（`record_estimates()`）
RATE_LOG = ROOT / "data" / "deadline_est.jsonl"


def _rate_scatter(key: str, path: Path | None = None) -> float | None:
    """**その要件の伸び率が、実際にどれだけ散らばってきたか**（相対）。

    ## なぜ要るか（2026-08-27 夜・最適化の回。**実測で4回の空振りが出ていた**）

    `_ans_accrual` の帯は `1/√have` です —— **数え上げの誤差だけ**を見ています。
    ところが `days = (want - have) / rate` を動かしているのは **`rate` のほう**で、
    こちらは公開本数で日ごとに大きく振れます。

    実測（前提「長尺の登録率はショートより1桁以上高い」・`config/hypotheses.yaml`
    が自分で履歴を書いています）:

        08-25  あと 80日  → 期限 11-13
        08-25  （同じ日に）→ 11-09
        08-26  → 11-16                      （+7日）
        08-26  伸び率 7日で 10.57/日（have 74）→ 11-22   （+6日・帯 ±7）
        08-27  伸び率 8日で 13.38/日（have 107）→ 11-02  （**-20日**・帯 ±7）

    **伸び率が1日で +27% 動いています。** `1/√107` は **9.7%** なので、
    帯は ±7日。**実際の振れはその3倍**でした。だから毎回「帯の外だ、
    書き換えろ」と出て、**3日で4回 期限だけが書き換わりました。**
    その4回で、前提も、データの来る日も、**1日も動いていません。**

    `waits` の註は「**帯の中の待ちは数えません**（数えると、推定のゆらぎのぶんだけ
    『縮めること』と言い続け、書き換えても次の回にまた言われます）」と、
    **この失敗の形を正確に予言していました。** 足りなかったのは**帯の幅**です。

    ## 何を返すか

    `(相対的な広がり, 点の数)`。広がりは `(max - min) / median`。
    2点 未満なら `None`（散らばりを名乗れない）。
    **上限 2.0** —— 立ち上がりで 0 に近い点があると比が発散するので押さえます。

    **点の数を一緒に返すのは、少ない点の広がりが「下限」だから**です。
    2点 の範囲は真の散らばりを**必ず小さく見積もります**（点が増えるほど
    範囲は広がる一方）。だから `n` を印字して、
    **読む側が「この帯はまだ狭い側だ」と分かるように**します ——
    さもないと、2点 から出た帯を確定値として読んで、また書き換えが始まります。

    **覆る条件**: 控えが 1日1行 なので、**日ごとより速い振れは見えません。**
    1日のうちに大きく動く要件が出てきたら、鍵を「日」から「時」へ落とすこと。
    逆に、伸び率が落ち着いた要件では散らばりが縮み、帯は `1/√have` へ戻ります
    （**帯は狭くなる方向にも動きます。固定した幅ではありません**）。
    """
    p = path or RATE_LOG
    if not key or not p.exists():
        return None
    # **1鍵1日1行は、読む側でも守ること**（2026-08-27 夜に足した）。
    #
    # 控えは「1鍵1日1行」の約束ですが、**その約束は書く側にしかありません。**
    # 同じ日に2行 入る道が実際に出ました —— `have` を控え始めた回が、
    # **欄の足りない今日の行を書き直させた**ので、`have` 無しと `have` 付きが
    # 1日に2行 並びます（実測 2026-08-27: 3鍵 が2行ずつ）。
    #
    # 数えているのは「**何日ぶん観測したか**」なので、同じ日を2回 数えると
    # **`n_pts` が水増しされ、「まだ N点 なので、この帯は下限です」の註が
    # 1回 早く消えます** —— 帯を狭いと読ませる向きです。
    # **日ごとに最後の1行**を採ります（後から書いたほうが新しい）。
    by_day: dict[str, float] = {}
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("key") != key:
            continue
        try:
            v = float(r.get("rate"))
        except (TypeError, ValueError):
            continue
        if v > 0:
            by_day[str(r.get("at"))[:10]] = v
    rates = list(by_day.values())
    if len(rates) < 2:
        return None
    rates.sort()
    mid = rates[len(rates) // 2]
    if mid <= 0:
        return None
    return min(2.0, (rates[-1] - rates[0]) / mid), len(rates)


def _recent_rate(key: str, have: int, as_of: date,
                 path: Path | None = None) -> tuple[float, int, int] | None:
    """**直近の実測の伸び率**（`(1日あたり, 何日ぶん, いくつ増えたか)`）。

    ## なぜ要るか（2026-08-27 夜・最適化の回。**同じ形の3件目**）

    `_ans_accrual` の `rate = have / (as_of - since).days` は**生涯の平均**です。
    積みが完全に止まっても、分母が伸びるぶんゆっくり下がるだけなので、
    **止まった当日も「あと1日」と出続けます。**

    実測 2026-08-27 22:3x（前提「長尺の生成が落ちる主因は『過去の図と
    重なっています』の門で、公開が増えるほど落ちる率が上がる」）::

        台帳   要 6 ／ いま 5（3日で **1.67/日**）→ **あと 1日 ＝ 08-28**
        実物   この要件が数えるのは**長尺の生成失敗**（`batch_runs.jsonl`）。
               08/24  7/21 通過（失敗 14）
               08/26  25/28 通過（89%）
               08/27  **15/15 通過（100%）→ 今日の失敗は 0件**

    **1.67/日 は 08/24〜08/26 の平均**で、いまの実測ではありません。
    しかもこの要件は**失敗を数えている**ので、生成が直るほど**永久に満ちません**
    —— それでも台帳は毎周「あと1日」と言います。

    **同じ形は、今日だけで3件目**です:

        `arm_speed.throughput()`        θ ＝ 閉じた件数 ÷ 経過日数（生涯平均）
        `deadline_check._project_nth()` 伸び率 ＝ 本数 ÷ 経過日数（窓 0日 でも名乗る）
        ここ                            伸び率 ＝ 実数 ÷ 経過日数（止まっても下がらない）

    ## 何を返すか / 何を返さないか

    控えは **1鍵1日1行**なので、**日をまたいだ2点**が要ります。
    `have` を控え始めたのが 2026-08-27 なので、**それ以前の行からは出せません**
    （`have` が無い行は捨てます。**推定で埋めないこと** —— `since` が控えに無く、
    `rate × 経過` を逆算すると、丸めのぶんだけ偽の増減が生まれます）。

    返すのは**いちばん新しい点との差**だけです。窓の取り方を増やさないのは、
    増やすと「どの窓を読むか」が次の回の仕事になるからです。

    **覆る条件**: 1日より速く動く要件が出てきたら、鍵を「日」から「時」へ落とすこと
    （`_rate_scatter` の註と同じ）。
    """
    p = path or RATE_LOG
    if not key or not p.exists():
        return None
    pts: list[tuple[str, int]] = []
    for ln in p.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        if r.get("key") != key or r.get("have") is None:
            continue
        try:
            pts.append((str(r["at"])[:10], int(r["have"])))
        except (KeyError, TypeError, ValueError):
            continue
    if not pts:
        return None
    pts.sort()
    at0, have0 = pts[-1]
    try:
        days = (as_of - date.fromisoformat(at0)).days
    except ValueError:
        return None
    if days < 1:                       # 同じ日の点どうしは「率」になりません
        return None
    return (have - have0) / days, days, have - have0


def record_estimates(vs: list["Verdict"], path: Path | None = None,
                     as_of: date | None = None) -> int:
    """**この回の伸び率を控える**（1鍵1日1行）。返りは足した行数。

    **`_ans_accrual` の中では書きません。** あれは純粋な関数で、検査からも
    他の道具からも何度も呼ばれます。**呼ぶたびに repo へ書き足す作りにすると、
    控えは「この機械が何回 撃たれたか」を数えるようになり、
    伸び率の散らばりではなくなります。** 積むのは印字する道の1か所だけ。

    ## **「欄が足りない行を書き直す」を、1回だけにすること**（2026-08-27 夜・最適化の回）

    同じ日の夕方に足した「`have` の無い今日の行は済みにしない」は、
    **`have` を持たない答えに対して、毎周1行ずつ足していました。**
    条件が「その行に `have` が無いか」だったので、**書き直した行にも `have` が
    入らない**（＝答えの側が `have` を持たない）と、**次の周もまた足りない**
    ＝ 永久に書き足します。`tests/test_deadline_band_from_rate_scatter.py` の
    `test_控えは1鍵1日1行` が**その日から赤いまま押されていました**
    （この回が実測: 2回 撃つと 1件 → **1件**。あるべきは 1件 → 0件）。

    害は控えの行数ではなく**帯のほう**です —— `_rate_scatter()` は点の散らばりで
    ±N日 を出すので、**同じ値の行が増えるほど散らばりが小さく出ます**
    （＝帯が狭くなり、狭い帯は「書き換えてよい」に読めて churn が戻る。
    その churn は `_rate_scatter` の註が「3日に4回 期限が書き換わった」と
    書いているものです）。

    直し方: **その (鍵, 日) に `have` を持つ行が既に在るか**で見ます。
    在れば済み。無ければ、**これから書く答えが `have` を持つときだけ**書き足す
    （＝移行の1回だけ）。`have` を持たない答えは、その日の1行目だけが残ります。
    """
    p = path or RATE_LOG
    day = (as_of or today_jst()).isoformat()
    seen: set[tuple[str, str]] = set()
    #: その (鍵, 日) に **`have` を持つ行**が既に在るか
    filled: set[tuple[str, str]] = set()
    if p.exists():
        for ln in p.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            k = (str(r.get("key")), str(r.get("at")))
            seen.add(k)
            if r.get("have") is not None:
                filled.add(k)
    add = []
    for v in vs:
        for a in v.answers:
            if not a.rate_key or a.rate is None:
                continue
            k = (a.rate_key, day)
            if k in filled:
                continue
            # **`have` の無い今日の行は、1回だけ書き直します**（2026-08-27 夜）。
            #   `have` を控え始めた日は、その日の行が既に `have` 無しで在ります。
            #   そこを飛ばすと、**最初の点が1日 遅れて立つ** ＝ 止まりに気づけるのが
            #   1日 遅くなります。**書き直すのは、こんど書く側が `have` を持つ
            #   ときだけ** —— 持たないまま書き足すと、毎周1行ずつ増えます（上の註）。
            if k in seen and a.have is None:
                continue
            seen.add(k)
            if a.have is not None:
                filled.add(k)
            add.append({"at": day, "key": a.rate_key, "rate": round(a.rate, 6),
                        # **実数も控えます**（2026-08-27 夜）。`rate` は生涯の平均で、
                        # 積みが止まっても分母が伸びるぶん下がるだけ ——
                        # **止まった当日も「あと1日」と出ます**（`Answer.have` の註）。
                        "have": a.have,
                        "ready": a.ready.isoformat() if a.ready else None,
                        "claim": v.claim[:80]})
    if add:
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as fh:
            for r in add:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")
    return len(add)


def _ans_now() -> Answer:
    return Answer(today_jst(), "手元のデータだけで判定できます")


def _ans_external(need: dict) -> Answer:
    what = str(need.get("what") or "（何を待つか書かれていません）")
    return Answer(None, f"**こちらの手では起こせません**: {what}", unreachable=True)


#: **伸び率を出すのに要る、最低の観測窓（日）。**
#   これを下回るあいだは日を出しません（＝ `Verdict.warming`）。
#   2日 なのは「率」と呼べる最小の窓だから —— 1日では、その日が
#   ふつうの日なのか偶然なのかを、この機械は区別できません。
_MIN_SPAN_DAYS = 2


#: `data_file:` を書いた `accrual` を「古い」と呼ぶまでの時間（時）。
#: **24時間**。1周 1.5時間 のこの機械なら、毎周 取り直している計器は黙ります。
_STALE_AFTER_HOURS = 24.0


def _stale_todo(need: dict) -> str:
    """**その数が伸びないのは、計器を取り直していないからではないか。**

    ## なぜ `accrual` にも要るのか（2026-08-27 夜・最適化の回）

    同じ日の朝の回が、この穴を **`kind: on_date` にだけ**塞ぎました
    （`needs.data_file:`。「**時計は来ています。足りないのはデータのほうです**」）。
    **`accrual` には同じ穴がそのまま残っていました。** そして `accrual` のほうが
    危ないのは、**返す文が「待てば出ます」だから**です:

        要 3 ／ いま **0**（8日ぶん。**伸び率が出せないので、いつ届くか言えません**）
        → **まだ数えはじめたところです。この回は何もしないのが正解です**

    実測 2026-08-27（前提「深い題のショートは `s-` の題のショートより上」）:

        `deep_short_days()` が読む `data/video_forms.json`  取り直したのは **08-26**
        その控えが分類し終えている いちばん新しい公開日      **08-24**
        深い題のショートを**公開しはじめた**日              **08-25**
        08/25・08/26・08/27 の公開（両群とも在る）          **控えには1本も無い**

    **`falsified_if` が要る「両群がそろう公開日」は、もう 3日 ぶん公開済み**です。
    0 なのは日が足りないからではなく、**分類の控えが 08-24 で止まっている**から。
    `data/video_forms.json` を書き直すのは `src/rpm_mix` の主処理だけで、
    **1周の中で誰も撃ちません。待っても永久に 0 のまま**でした。

    「この回は何もしないのが正解です」は、その状態で**毎周 出続けます** ——
    これは `zero_means_never`（こちらから作らないかぎり来ない）と同じ形で、
    **違うのは「作る」ではなく「取り直す」で解けるところ**だけです。

    ## 何を門にするか

    **`count_expr` の中身は読みません**（読めません）。要件の側が
    `data_file:` でどの計器を読んでいるかを申告し、その計器の `at` が
    `_STALE_AFTER_HOURS`（既定 24時間）より古ければ、**取り直す手**を `todo` にします。
    `refresh:` にコマンドを書いておけば、そのまま撃てます。

    **書いていない要件は、今までどおり時計だけで通します**（`on_date` と同じ方針）。

    **覆る条件**: 1周ごとに全計器を取り直す作りにしたら、この門は毎回 黙るので
    外してよい。逆に「取り直したのに数が伸びない」が続くなら、
    見るべきは控えではなく `count_expr` のほうです。
    """
    src = str(need.get("data_file") or "").strip()
    if not src:
        return ""
    try:
        hours = float(need.get("stale_after_hours") or _STALE_AFTER_HOURS)
    except (TypeError, ValueError):
        hours = _STALE_AFTER_HOURS
    newest = newest_point(ROOT / src)
    now = datetime.now(timezone.utc)
    if newest is not None and (now - newest).total_seconds() / 3600.0 < hours:
        return ""                                   # **新しい。待つのが正しい**
    seen = (f"取り直したのは **{newest.astimezone(JST):%m/%d %H:%M} JST**"
            f"（**{(now - newest).total_seconds() / 3600:.0f}時間 前**）"
            if newest else "**いつ取り直したか読めません**")
    how = str(need.get("refresh") or "").strip()
    return ("**待ち方が違います。足りないのは日ではなく、計器のほうです** —— "
            f"この数が読んでいる `{src}` は {seen}。"
            "**取り直すまで、待っても増えません。**"
            + (f"  `{how}`" if how else f"  `{src}` を取り直すこと"))


def _ans_accrual(need: dict, as_of: date) -> Answer:
    expr = str(need.get("count_expr") or "")
    want = int(need.get("need") or 0)
    since_s = str(need.get("since") or "")
    try:
        have = int(eval(expr, dict(EXPR_NS)))                  # noqa: S307
    except Exception as e:                                     # noqa: BLE001
        return Answer(None, f"**数えられませんでした**: {e}")
    if have >= want:
        # **ここには門がありません。`count_expr` を丸ごと信じています。**
        #   （2026-08-26 夕・最適化の回。**自分の `--shrink` がここで踏みました**）
        #
        #   下の `_MIN_SPAN_DAYS`（1日の窓から伸び率を出さない）は
        #   **推定の道だけ**を守ります。**この行は推定ではないので素通りします** ——
        #   そして `--shrink` は `ready` を見て期限を書き換えるので、
        #   **`count_expr` が違うものを数えていると、期限が今日まで飛びます。**
        #
        #   実測: 「深い題ショート」の `count_expr` は `batch_runs.jsonl` の
        #   **作った本**を数えていて **16本 →「足りています」**。ところが
        #   **公開済みは 7本**、うち `video_forms` が「ショート」と言うのは **0本**、
        #   `falsified_if` が要る「両群がそろう公開日」は **0日**（3日 要る）。
        #   `--shrink` はその 16 を読んで **09-03 → 08-29 → 08-26（今日）** まで縮め、
        #   **判定できる本が1本も無いのに「今日が期限」**にしていました。
        #
        #   **数が門を通ったことと、`falsified_if` が当てられることは別です。**
        #   直すのは、その前提の `count_expr` を**公開済み・分類済み**で数え直すことと、
        #   「本数が満ちても判定できるとは限らない」を数える要件を足すこと
        #   （`src/watches.deep_short_days()` がその例）。**ここに一般の門は置けません** ——
        #   何を数えるべきかは、前提ごとに `falsified_if` が決めるからです。
        return Answer(as_of, f"要 {want} ／ いま **{have}** → 足りています")
    # **足りていない道は、全部ここを通ります。** 古い計器の申告は1度だけ引いて、
    # **日が出る道にも出ない道にも**同じものを載せます（下の3か所）。
    #
    # **`have == 0` の道にだけ載せて済ませないこと**（2026-08-27 夜に踏みかけた）。
    # 取り直して 0 → 1 になった瞬間、この要件は**日の出る道**へ移ります ——
    # そこに載せないと、翌日ふたたび控えが古びても**誰も言いません。**
    # 数は 1 のまま、伸び率だけが 0.50/日 → 0.33 → 0.25 と落ち、
    # **判定日が毎日 後ろへ滑るのに、理由がどこにも出ない**形になります。
    # **`have >= want` の道には載せません**（もう足りているので、取り直す用が無い）。
    stale = _stale_todo(need)
    try:
        spanned = (as_of - date.fromisoformat(since_s)).days
    except ValueError:
        return Answer(None, f"要 {want} ／ いま {have}（`since` が読めないので伸び率が出せません）",
                      todo=stale)
    # **1日の窓から伸び率を出さないこと**（2026-08-26 夕・最適化の回に踏んだ）。
    #
    #     実測: `since: 2026-08-26` の前提が、立った **1時間後**に
    #           「要 72 ／ いま **3**（**1日で 3.00/日**）→ あと 23日（±14日）」
    #           と projecting し、**期限を 11-09 → 09-18 へ 38日 縮めろ**と出した。
    #
    # **3本 から 72本 を見通しています。** 帯（±14日）は `1/√have` ——
    # **`have` の数え上げ誤差**だけを見ていて、**窓の短さ**を見ていません。
    # 同じ `have` でも、1日で3本と7日で3本は別の話です。
    #
    # **なぜこの回に効くか**: 同じ回に「遅すぎる期限は赤」を入れました。
    # 1日の窓の projection が `waits` を作ると、**赤 → 縮める → データが
    # 追いつかず `slips` → 延ばす** の往復になります。**縮める側の入力が
    # 推定でしかないときは、縮めないほうが速い。**
    # **`zero_means_never` は窓の話ではありません。** 「こちらから作らないかぎり
    #   来ない」は**そのものの性質**の宣言なので、何日 見ていても変わりません。
    #   **だから窓の門より先に見ること** —— 後ろに置いた版を一度書いて、
    #   `since` が今日の対照群が「まだ数えはじめたところ」に化けました
    #   （＝ **待てば来る**と読める。実際は永久に来ません）。
    if have == 0 and need.get("zero_means_never"):
        return Answer(None, f"要 {want} ／ いま **0**（`since` から {spanned}日。"
                            "**こちらから作らないかぎり来ません**）", unreachable=True)
    if spanned < _MIN_SPAN_DAYS:
        return Answer(None, f"要 {want} ／ いま {have}"
                            f"（`since` から {spanned}日。**{_MIN_SPAN_DAYS}日 ぶん"
                            "たまるまで伸び率を出しません** —— 1日の窓からの見通しは、"
                            "帯の外れ方が読めません）", todo=stale)
    elapsed = max(1, spanned)
    rate = have / elapsed
    if rate <= 0:
        # **0 を「待っても来ない」と読んでよいのは、そう宣言したときだけ。**
        # まだ公開していない本の再生は、いま 0 でも後から積みます。
        # 一方「`YT_OPENING_MOTION=0` の対照群」は、こちらが作らないかぎり
        # **永久に 0 のまま**です。その違いは式からは読めないので、欄で言うこと。
        if need.get("zero_means_never"):
            return Answer(None, f"要 {want} ／ いま **0**（{elapsed}日で1件も積んでいません。"
                                "**こちらから作らないかぎり来ません**）", unreachable=True)
        return Answer(None, f"要 {want} ／ いま **0**（{elapsed}日ぶん。"
                            "**伸び率が出せないので、いつ届くか言えません**）",
                      todo=stale)
    days = math.ceil((want - have) / rate)
    # **帯の幅**: 積み上げの数え上げ誤差 ≒ 1/√have（件数の相対標準誤差）を日数へ移す。
    # have=74・days=88 なら ±11日。**この幅の中で期限を書き換えても、何も動きません。**
    slack = max(1, math.ceil(days / max(1.0, have ** 0.5)))
    # **帯は、数え上げの誤差だけでは足りません**（2026-08-27 夜・`_rate_scatter`）。
    # `days = (want - have) / rate` を動かしているのは `rate` のほうで、
    # そちらは公開本数で日ごとに振れます。実測: ある前提の伸び率が1日で
    # **+27%** 動き、`1/√have` の 9.7% ＝ ±7日 では受け止められず、
    # **3日で4回 期限だけが書き換わりました**（前提もデータの来る日も1日も動かず）。
    # だから**その要件自身の、これまでの伸び率の散らばり**でも帯を張ります。
    # **広いほうを採ります** —— 狭いほうを採ると、churn がそのまま残ります。
    got = _rate_scatter(str(need.get("count_expr") or ""))
    note = ""
    if got is not None:
        scatter, n_pts = got
        wide = max(1, math.ceil(days * scatter))
        if wide > slack:
            # **点が少ないうちは「下限」だと言うこと。** 2点 の範囲は真の
            # 散らばりを必ず小さく見積もるので、確定値として読まれると
            # また書き換えが始まります（この帯は、それを止めるために在ります）。
            floor = ("。**まだ {n}点 なので、この幅は下限です**"
                     "（点が増えるほど広がります。**狭いと読まないこと**）"
                     ).format(n=n_pts) if n_pts < 3 else ""
            note = (f"。**うち ±{wide}日 は、この要件自身の伸び率の振れ**"
                    f"（{n_pts}点 の実測の広がり {scatter * 100:.0f}%。"
                    "数え上げの誤差だけなら "
                    f"±{slack}日 でした ——**狭いほうを使うと、書き換えても"
                    f"次の回にまた言われます**）{floor}")
            slack = wide
    # **日が出る道にも、古い計器の申告を載せます。** ここは `warming` ではないので
    # `todo` は印字されません —— だから `why` のほうへ足します。
    # **この推定は「計器を取り直しつづけたら」の話**で、止めれば伸び率は落ち、
    # 判定日は毎日 後ろへ滑ります。**滑っている理由が、同じ行に出ること。**
    tail = f"  ／ {stale}" if stale else ""
    # **「あと N日」は生涯の平均から出ています。止まっていたら、そう言うこと。**
    #   （2026-08-27 夜・最適化の回。`_recent_rate` の註に実測があります）
    #   **日付は動かしません** —— 2点 の差で動かすと、この repo が 3日で4回
    #   踏んだ churn（`_rate_scatter` の註）がそのまま戻ります。
    #   `CLAUDE.md`「**裸の『届きません』を出さないこと。何を固定したせいで
    #   そう出たのかを同じ行に並べること**」の、同じ扱いです。
    key = str(need.get("count_expr") or "")
    rec = _recent_rate(key, have, as_of)
    if rec is not None:
        r_rate, r_days, r_delta = rec
        if r_delta <= 0:
            note += (f"。**直近 {r_days}日 は1件も増えていません**"
                     f"（前の点も {have}）—— この「あと {days}日」は、"
                     "**止まる前の平均**から出ています。"
                     "**その要件が数えているものが、まだ起きているか**を見ること")
        elif r_rate < rate * 0.5:
            note += (f"。**直近の実測は {r_days}日 で +{r_delta}件 ＝ "
                     f"{r_rate:.2f}/日**（生涯の平均 {rate:.2f}/日 の半分以下）"
                     "—— この「あと」は**速いほうの平均**で出ています")
    return Answer(as_of + timedelta(days=days),
                  f"要 {want} ／ いま {have}（{elapsed}日で {rate:.2f}/日）→ あと {days}日"
                  f"（**±{slack}日**。伸び率からの推定なので、この幅の中の書き換えは"
                  f"意味を持ちません{note}）"
                  + tail,
                  slack=slack, todo=stale,
                  rate=rate, rate_key=key, have=have)


def _project_nth(rows: list[dict], pub: list[str], count: int, after: str,
                 as_of: date) -> tuple[date, float, int, int] | None:
    """群がまだ `count` 本に満たないとき、**`count` 本目が公開される日を推定する。**

    ## なぜ要るか（2026-08-26 夕・サブの回。**`sub_rate` の腕が丸ごと止まっていた**）

    ここは長らく、群が足りないと **`Answer(None, "予約にまだ在りません")`** で
    返していました。**`None` は「判定できる日が出せない」という意味**なので:

    - `src/arm_speed.forward()` の `undated` に落ちる ＝ **θ（腕の回転）に数えられない**
    - `scripts/queue_lag.py` も `src/judgeable.py` も、**判定日を持たない前提は動かせない**
    - `scripts/deadline_check.py` は `[!!] 判定できる日が出せません` と印字して終わる

    実測 2026-08-26: 期限 10/11 の「ショートの最後で登録を直接1回頼むと、登録率が
    上がる」（腕 `sub_rate`・**処置は既に生成に入っていて、予約に 21本 在る**）が
    **これに当たっていました。** `eta.py --alloc` は同じ回に
    「**次の1件は `sub_rate` がいちばん早い（5日）**」と出しており、
    **いちばん速い腕の、唯一 走っている実験が、機械から見えていなかった**わけです。

    **同じ機械の `_ans_group_key` は、同じ形をとっくに解いています**
    （`要 1000 ／ いま 78（7日で 11.14/日）→ あと 83日（±10日）`）。
    伸び率から日を出す道具が**すぐ上の関数に在って、こちらだけ諦めていました。**
    `docs/JOURNAL.md` が「いちばん当たる」と書いている形そのものです ——
    **同じことを2か所が別々に言っていて、片方しか読まれていない。**

    ## 何を積むか（**2段。作る速さと、作ってから出るまでの遅れ**）

    `_ans_group_key` は再生の積み上げなので1段で済みますが、こちらは
    **「作る」と「公開する」が別の日**です。予約は先の空き枠へ入るので、
    作った本が明日 出るとは限りません（実測 2〜49日 後）。

        作る速さ    `created_after` からの経過日数 ÷ 群の本数
        公開の遅れ  既に在る本の（公開日 − 作った日）の**中央値**

    そして**推定した日は、既に予約に入っている最後の1本より前になりません**
    （公開は前へは進まない）。`max()` で押さえています。

    ## この推定が言えないこと

    - **1本も作っていない群には出せません**（`None` を返す）。伸び率がゼロだと
      「待っても来ない」と区別が付かず、`zero_means_never` の判断は呼び手の側です
    - **帯は `1/√件数`**（`_ans_group_key` と同じ）。21本 なら ±22%。
      **帯の中で期限を書き換えても、届く日は1日も動きません**
    - **作る速さが落ちれば伸びます。** この推定は「いまの速さが続いたら」です

    返り: `(count 本目の公開日, 1日あたり作った本数, 公開の遅れの中央値, 帯)`
    """
    have = len(pub)
    if have <= 0:
        return None
    try:
        since = date.fromisoformat(after[:10])
    except ValueError:
        return None
    # **窓の下限は `_MIN_SPAN_DAYS`**（2026-08-27 夜・最適化の回に足した）。
    #
    # ここは長らく `max(1, ...)` でした。**同じファイルの `_ans_accrual` は、
    # 前の日に `_MIN_SPAN_DAYS` の門を足して、まったく同じ穴を塞いでいます** ——
    # あちらの註（原文）:
    #
    #     **1日の窓から伸び率を出さないこと**（2026-08-26 夕・最適化の回に踏んだ）。
    #     実測: `since: 2026-08-26` の前提が、立った **1時間後**に
    #           「要 72 ／ いま 3（**1日で 3.00/日**）→ あと 23日」と projecting し、
    #           **期限を 11-09 → 09-18 へ 38日 縮めろ**と出した。
    #
    # **こちらは同じ日に、同じ人が、同じ目的で書いた関数です。**
    # それでも門が付いていませんでした（`docs/JOURNAL.md`「同じことを2か所が
    # 別々に言っていて、片方しか読まれていない」——**この repo で通算12回目**）。
    #
    # 実測 2026-08-27 22:2x、**塞ぐ前に実際に出ていた偽の日付**::
    #
    #     slide_pace   since 2026-08-27（**窓 0日**）  速い 5本 → **5.00本/日**
    #                                                遅い 3本 → **3.00本/日**
    #                  → 16本目 09/13・09/15 → **判定 09-21** と印字
    #     request_form since 2026-08-26（**窓 1日**）  22本 → **22.00本/日**
    #
    # `slide_pace` は**この機械が今日 入れた A/B** です。**0日 の窓**から
    # 「1日 5本 作れる」と読み、そのまま到達日の入力（`arm_speed.forward()`）に
    # 乗っていました。
    #
    # ## **`None` には戻しません**（この関数が在る理由がそれです）
    #
    # `_ans_accrual` は窓が足りないと日を出さずに返しますが、**こちらで同じことを
    # すると `arm_speed.forward()` の `undated` に落ち、腕が丸ごと凍ります**
    # （上の docstring がその実測です）。だから**日は出し続けて、分母だけ
    # 下限で押さえます** —— 「`have` 本を `_MIN_SPAN_DAYS` 日で作った」より
    # 速い伸び率は、名乗らないということです。
    #
    # **覆る条件**: 群の本ごとに「作った時刻」が引けるようになったら
    # （`data/batch_runs.jsonl` の `at` を群へ結び直す）、`since` からの
    # 経過ではなく**実際の作った時刻の幅**で割れます。そのときこの下限は要りません。
    span = (as_of - since).days
    elapsed = max(_MIN_SPAN_DAYS, span)
    rate = have / elapsed
    if rate <= 0:
        return None
    leads = []
    for r in rows:
        at, up = str(r.get("at") or "")[:10], str(r.get("uploaded_at") or "")[:10]
        if not at or not up:
            continue
        try:
            leads.append((date.fromisoformat(at) - date.fromisoformat(up)).days)
        except ValueError:
            continue
    leads.sort()
    lead = leads[len(leads) // 2] if leads else 0
    days_to_build = math.ceil((count - have) / rate)
    nth = as_of + timedelta(days=days_to_build + max(0, lead))
    try:                                    # 公開は前へ進まない ＝ 既にある最後より後
        nth = max(nth, date.fromisoformat(pub[-1]))
    except ValueError:
        pass
    ahead = max(1, (nth - as_of).days)
    slack = max(1, math.ceil(ahead / max(1.0, have ** 0.5)))
    # **窓が下限に当たった回は、そう言うこと。** 言わないと、
    # `have / _MIN_SPAN_DAYS` が「実測の伸び率」として読まれます。
    warn = ("" if span >= _MIN_SPAN_DAYS else
            f"・**窓が {span}日 しかないので、分母に {_MIN_SPAN_DAYS}日 を当てています**"
            f"（この伸び率は上限です。実測は `since` を {_MIN_SPAN_DAYS}日 またいでから）")
    return nth, rate, max(0, lead), slack, warn


def _ans_published_group(need: dict, as_of: date, lag: int) -> Answer:
    """**作った日で決まる群**が、公開 → 落ち着く → 実データに出るまで。

    在庫の予約日は `data/uploaded.jsonl` の `at` に**実際に入っている**ので、
    中央値で見積もらずに、**その本の予約日そのもの**で解きます。
    """
    after = str(need.get("created_after") or "")
    count = int(need.get("count") or 1)
    settle = int(need.get("settle_days", DEFAULT_SETTLE_DAYS))
    since_pub = str(need.get("published_after") or "")
    endcard = str(need.get("endcard") or "")
    rows = [r for r in _rows("uploaded.jsonl") if str(r.get("uploaded_at") or "") >= after]
    # --- **処置群だけを数える**（2026-08-26 夕に足した） ---
    #
    # ここは長らく「その日以降に作った本」を**型を問わず全部**数えていました。
    # 実測 2026-08-26: 期限 10/11 の「ショートの最後で登録を直接1回頼む」の
    # `created_after: 2026-08-24` に当たる 51本 のうち、**依頼の型は 5本だけ**で、
    # 残りは問いかけ 25本・長尺の「明日やること」20本 でした（依頼が実際に
    # 出はじめたのは **08/26 02:50** で、同じ束の中にも問いかけが3本 混ざっています）。
    #
    # **この群は 30,000再生 から検出力を逆算して 72本 と置いてあります**
    # （`config/hypotheses.yaml` の note）。対照が混ざったまま満たすと、
    # **効きが薄まって「外れ」に化けます** —— そしてその前提の `next_if_false` は
    # 「登録率の腕を動画の外へ移す」なので、**律速の門（登録者1,000人）を
    # 誤った理由で手放す**ことになります。
    #
    # `endcard:` を書かない要件は、**今までどおり型を問いません。**
    if endcard:
        keep = []
        for r in rows:
            vid = r.get("video_id")
            if vid and endcard_verdict.form_of(str(vid)) == endcard:
                keep.append(r)
        rows = keep
    pub = sorted(p for p in (str(r["at"])[:10] for r in rows if r.get("at")) if p >= since_pub)
    if len(pub) < count:
        tail = f"（{since_pub} 以降に公開する本だけ）" if since_pub else ""
        form = f"・**終端が {endcard} の本だけ**" if endcard else ""
        head = (f"{after[:10]} 以降に作った本{tail}{form} **{len(pub)}本** ／ 要 {count}本")
        proj = _project_nth(rows, pub, count, after, as_of)
        if proj is None:
            return Answer(None, f"{head} —— **予約にまだ在りません**（作れば動きます）")
        nth, rate, lead, slack, warn = proj
        ready = nth + timedelta(days=settle + lag)
        return Answer(ready,
                      f"{head} —— **推定**（{rate:.2f}本/日 で作られ、作ってから公開まで "
                      f"中央値 {lead}日{warn}）→ {count}本目の公開 **{nth:%m/%d}** "
                      f"＋ 落ち着く {settle}日 ＋ 実データの遅れ {lag}日"
                      f"（**±{slack}日**。伸び率からの推定なので、この幅の中の"
                      "書き換えは意味を持ちません）",
                      slack=slack)
    nth = date.fromisoformat(pub[count - 1])
    ready = nth + timedelta(days=settle + lag)
    band = analytics_lag_band()
    tail = (f"（**＋{band}日／−0日** —— 遅れは1日の中で動きますが、**上にしか動きません**。実測 3日 が 381・4日 が 57・**2日 は 0**）" if band else "")
    return Answer(ready,
                  f"{after[:10]} 以降に作った本の **{count}本目の公開 {nth:%m/%d}** "
                  f"＋ 落ち着く {settle}日 ＋ 実データの遅れ {lag}日{tail}",
                  slack=band, slack_down=0)


#: **Data API の日枠（10,000単位）を使う取り直しの道具。**
#:
#: `refresh:` がこれを指しているなら、**日枠が閉じている窓では取り直せません。**
#: `needs.quota:` に `data_api` / `none` と書けば、この一覧より優先します。
#:
#: **中身を確かめてから足すこと。** `scripts/snapshot.py` は
#: `youtube.videos().list(part="snippet,status,statistics")` を撃つので Data API
#: です（同ファイルの註「571本 なら 12組 ＝ 12単位。日枠は10,000単位」）。
#: **Analytics API と Reporting API は別の枠**なので、ここに入れないこと ——
#: 入れると、読めるのに「読めません」と言う側に外れます。
#:
#: **2026-08-27 に、一覧そのものは `src/upload_cap.DATA_API_TOOLS` へ移しました。**
#: 同じ日のうちに読み手が3つになったからです（この門・`src/day_cap.readable_at()`・
#: `scripts/retro.py` の持ち越し）。**ここは名前を残すだけの窓**で、
#: 足すのは向こうです（`upload_cap` が日枠という事実の持ち主）。
def _data_api_tools() -> tuple[str, ...]:
    try:
        from src import upload_cap
        return tuple(upload_cap.DATA_API_TOOLS)
    except Exception:                                          # noqa: BLE001
        return ("scripts/snapshot.py",)


_DATA_API_REFRESH = _data_api_tools()


def _quota_gate(need: dict, when: datetime, what: str) -> Answer | None:
    """**その時刻に、計器がそもそも読めるか。** 読めるなら `None`。

    ## なぜ要るか（2026-08-27 に踏んだ。**同じ日の3件目**）

    この門は同じ日のうちに2段 直っています ——
    朝に `at_time_jst`（日 → 時刻）、昼に `data_file:`（時計 → **点が在るか**）。
    **3段目が抜けていました: その点を、取り直せるのか。**

    実測 2026-08-27 18:5x JST、前提「1日に再生が付く本数の上限は
    その日の本数（10本）であって、時刻の窓ではない」:

        門の言い分   **今日の 22:00 JST に出ます。その時刻を過ぎた回が拾うこと**
        取り直す道具  `python scripts/snapshot.py` ＝ `videos.list`（**Data API**）
        Data API 日枠 **この窓で 403 を 29回 観測**。戻るのは **08/28 16:00 JST**

    **22:00 JST に撃っても 403 です。** 読めるのはその 18時間 後。
    つまり門は**偽の判定日**を出していて、しかも
    「**その時刻を過ぎた回が拾うこと**」と名指しで指示していました ——
    拾いに行った回は 403 を1つ買って帰ります。

    ## なぜ `data_file:` では捕まらないか

    `data_file:` は「**点が在るか**」を見ます。在りません、と正しく言えますが、
    その次の行で「`python scripts/snapshot.py` を撃つこと」と**撃てない手**を
    出します。**在るかどうかと、取れるかどうかは別の事実**です
    （`upload_cap.day_quota()` の冒頭が、時計と単位について同じことを言っています）。

    ## 覆る条件

    `videos.list` が日枠の外に出たら（別の枠・別の口）、この門は黙るべきです ——
    `_DATA_API_REFRESH` からその道具を外すこと。
    逆に日枠を使う道具が増えたら、**中身を確かめてから**足すこと。
    """
    kind = str(need.get("quota") or "").strip()
    if kind == "none":
        return None
    if not kind:
        src = str(need.get("refresh") or "")
        if not any(tool in src for tool in _DATA_API_REFRESH):
            return None
    elif kind != "data_api":
        return None
    try:
        from src import upload_cap
        q = upload_cap.day_quota()
    except Exception:                                          # noqa: BLE001
        return None                     # **読めないときは黙る**（門を増やさない）
    if q.open:
        return None
    back = q.resets_at.astimezone(JST)
    if back <= when:
        return None                     # 枠のほうが先に戻る ＝ 時計だけの話
    # **いま見ている枠の中の時刻についてしか、この門は何も言えません**
    #     （2026-08-27 に検査が捕まえた）。過去の窓・先の窓の 22:00 に
    #     「いまの窓が尽きている」を当てると、**関係のない要件まで日が動きます**
    #     （`tests/test_deadline_data_file.py` が 2020-06-01 で組んでいて、
    #      2件 落ちました。**中身は1行も変わっていません**）。
    #     `tests/conftest.py` の `_measure_window_dynamic_off` と同じ形です。
    try:
        from src import upload_cap as _uc
        head = _uc.window_start().astimezone(JST)
    except Exception:                                          # noqa: BLE001
        return None
    if not (head <= when < back):
        return None
    how = str(need.get("refresh") or "").strip()
    return Answer(
        back.date(),
        ready_at=back,
        why=f"{what} —— ただし取り直す `{how}` は **Data API の日枠**を使い、"
        f"**この窓ではもう尽きています**（403 を {q.hits}回 観測）。"
        f" **{when:%m/%d %H:%M} JST に撃っても 403 です。**"
        f" 枠が戻るのは **{back:%m/%d %H:%M} JST**",
        todo=(f"**{when:%m/%d %H:%M} JST に拾いに行かないこと** —— 403 を1つ買って帰ります。"
              f" 撃つのは **{back:%m/%d %H:%M} JST 以降**。"
              f"  `{how}`  **条件は緩めないこと**"))


def newest_point(path: Path) -> datetime | None:
    """`data/*.jsonl` の中で **いちばん新しい観測時刻**。読めなければ `None`。

    **なぜ要るか**（2026-08-27・最適化の回。**その日のうちに踏みました**）

    `at_time_jst` は「**時計**が来たか」しか見ていませんでした。同じファイルの
    `_ans_after` の註が、その 14時間 前に自分でこう書いています ——
    『`falsified_if` が「`data/views.jsonl` が **08-27 14:00 JST 以降**の点を
    持っていること。持っていなければ判定せず、期限だけ延ばすこと」と**散文で**
    書いています。**正しい文はあって、門が読んでいたのは日付だけ**でした』。

    **時刻の粒に直しても、読んでいるのは時計のままです。**
    実測 2026-08-27 **14:24 JST**（時計は通った）:

        `data/views.jsonl` のいちばん新しい点  **08-26 01:53 JST**（**36時間 前**）
        `scripts/deadline_check.py`            [OK] 判定できるのは **08-27**
        `scripts/drift.py`                     **この回は verdict を出すこと**

    要るのは「05/06/07/08時に足した4本の、公開から6時間の読み」で、
    **その点は1つも在りません。** 同じ前提の `note` には、前回この門が早撃ちして
    「`verdict='count' confounded=False` を印字しました —— **確信つきで逆**です」
    と残っています。**時計だけの門は、同じ穴を時刻の粒で作り直しただけ**でした。

    だから `needs` に `data_file:` があるときは、**その計器に直接 訊きます**
    （＝この関数）。これは上の註が自分で書いた覆る条件そのものです ——
    『時刻の粒でも足りない要件が出てきたら、**その計器に直接 訊く `kind`** を足すこと』。

    **散文からパスを拾わないこと。** `what` の中の `` `data/views.jsonl` `` を
    正規表現で拾う手もありますが、この repo は同じ形で6回 転んでいます
    （**読み手が読まない欄に書いてある**）。だから `data_file:` という
    **機械が読む欄**にします。書いていない要件は、今までどおり時計だけで通します。

    ## 1行1件でない計器も読みます（2026-08-27 夜・最適化の回に足した）

    最初の版は `.jsonl` しか読めませんでした。**控え型の計器はそうではありません** ——
    `data/video_forms.json` は「いつ取り直したか」を**ファイル全体の `at`** で
    1つだけ持ちます（`src/rpm_mix.save_video_forms`）。行ごとに JSON として
    読もうとすると全行が落ちて、**`None`（＝1点も読めません）** に化けます。
    その化け方は「取り直せ」と同じ向きなので害は小さいのですが、
    **「いつ取り直したか」が出ないと、次の回が古さを測れません。**
    だから**まずファイル全体を JSON として読み**、駄目なら1行1件へ落とします。
    """
    if not path.exists():
        return None
    newest: datetime | None = None
    # **控え型（ファイル全体で1つの JSON）を先に試す。**
    try:
        whole = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        whole = None
    if isinstance(whole, dict):
        at = whole.get("at") or whole.get("ts") or whole.get("time")
        if isinstance(at, str):
            try:
                dt = datetime.fromisoformat(at.replace("Z", "+00:00"))
            except ValueError:
                dt = None
            if dt is not None:
                if dt.tzinfo is None:
                    # **日付だけの `at` は、その日の終わりではなく始まりで読む。**
                    # 「08-26 に取った」を 08-26 00:00 と読めば、古さは長めに出ます。
                    # **短く見積もって「まだ新しい」と言うほうが危険**です。
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:                                        # noqa: BLE001
            continue
        at = r.get("at") or r.get("ts") or r.get("time")
        if not isinstance(at, str):
            continue
        try:
            dt = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        if newest is None or dt > newest:
            newest = dt
    return newest


def _ans_after(need: dict, lag: int) -> Answer:
    """**その日が来るのを待っているだけ**の要件。

    `plus_lag: true` なら Analytics の遅れを足します —— 「08/29 時点の累計」は、
    08/29 に見ても **08/26 までの累計**しか出ていません。

    ## `at_time_jst` —— **日だけでは足りない要件**（2026-08-27・最適化の回）

    ここは長らく**日の粒**しか持っていませんでした。`drift.split_overdue()` は
    `str(ready) <= today` で見るので、**その日の 00:00 から「いま判定できる」**
    と言います。

    **実際に踏みました。** 2026-08-27 **00:22 JST** に `drift.py` が
    「**期限が来ていて、いま判定できる前提: 1件**」「**この回は verdict を出すこと**」
    と印字しました。その前提は `day_cap` の (A)/(B) の切り分けで、
    要るデータは **05/06/07/08時 の4本の、公開から6時間の読み**
    ——`config/hypotheses.yaml` の `falsified_if` が
    「`data/views.jsonl` が **08-27 14:00 JST 以降**の点を持っていること。
    持っていなければ判定せず、期限だけ延ばすこと」と**散文で**書いています。
    そのとき `src/day_cap.window()` は `confounded=True` / `verdict=None` でした。

    **正しい文はあって、門が読んでいたのは日付だけ**でした。
    しかも**その早撃ちは一度 起きています** —— 同じ前提の `note` に
    「本数モデルの予測（10本）に着地して `verdict='count' confounded=False` を
    印字しました —— **確信つきで逆**です」と記録があります。

    `at_time_jst: "14:00"` を書くと、**その日でも時刻が来るまでは日を返しません**
    （＝`warming` に落ちて、門は「待てば出ます」と言う）。

    **覆る条件**: 時刻の粒でも足りない要件が出てきたら（分・本数など）、
    ここではなく**その計器に直接 訊く `kind`** を足すこと ——
    日と時刻を足し続けると、台帳が計器の写しになります。
    """
    try:
        on = date.fromisoformat(str(need.get("on_date")))
    except (TypeError, ValueError):
        return Answer(None, f"**`on_date` が読めません**: {need.get('on_date')!r}")
    what = str(need.get("what") or "その日のデータ")
    at = need.get("at_time_jst")
    if at:
        try:
            hh, _, mm = str(at).partition(":")
            when = datetime(on.year, on.month, on.day,
                            int(hh), int(mm or 0), tzinfo=JST)
        except (TypeError, ValueError):
            return Answer(None, f"**`at_time_jst` が読めません**: {at!r}")
        # **その時刻に、計器が読めるか**（`_quota_gate` の註。時計より先に見ること）
        gate = _quota_gate(need, when, what)
        if gate is not None:
            return gate
        now = datetime.now(JST)
        if now < when:
            return Answer(
                None,
                f"{what} は **{on:%m/%d} {when:%H:%M} JST** に出ます"
                f"（いま {now:%m/%d %H:%M} JST。**まだ出ていません** ——"
                "日は来ていますが、この要件は日の粒ではありません）")
    # **時計が来た ＝ データが在る、ではありません**（2026-08-27・`newest_point` の註）。
    # `data_file:` が書いてあるときは、その計器に直接 訊きます。
    src = need.get("data_file")
    if src:
        when_data = when if at else datetime(on.year, on.month, on.day, tzinfo=JST)
        newest = newest_point(ROOT / str(src))
        if newest is None or newest < when_data:
            seen = (f"いちばん新しい点は **{newest.astimezone(JST):%m/%d %H:%M} JST**"
                    f"（**{(datetime.now(JST) - newest).total_seconds() / 3600:.0f}時間 前**）"
                    if newest else "**1点も読めません**")
            how = str(need.get("refresh") or "").strip()
            return Answer(
                None,
                f"{what} は **{when_data:%m/%d %H:%M} JST** の点が要りますが、"
                f"`{src}` にまだ在りません（{seen}）",
                todo=("**時計は来ています。足りないのはデータのほうです** —— "
                      f"`{src}` を取り直すまで、待っても永久に出ません。"
                      + (f"  `{how}`" if how else f"  `{src}` を取り直すこと")
                      + "  **取れるまで判定しないこと**"))
    if need.get("plus_lag"):
        band = analytics_lag_band()
        tail = (f"（**＋{band}日／−0日**。遅れは1日の中で {lag}日 と {lag + band}日 の"
                "間を動きますが、**下へは動きません**"
                f"（実測で {lag}日 未満の観測が1つもない）。"
                "だから期限をこの日より前に置かないこと）" if band else "")
        return Answer(on + timedelta(days=lag),
                      f"{what} は {on:%m/%d} の分 ＋ 実データの遅れ {lag}日{tail}",
                      slack=band, slack_down=0)
    return Answer(on, f"{what} は {on:%m/%d} に出ます")


def _ans_group_key(need: dict, as_of: date) -> Answer:
    """**群の床は `src/judgeable.py` に委ねる**（2026-08-25 の合流でこうした）。

    同じ日に、この道具と `src/judgeable.py` が**別々に同じ問いを解いていました。**
    答えが割れると、次に来た者はどちらを信じるか決められません ——
    実測でも割れました（対照(動きなし)を、こちらは `batch_runs` から **0本**、
    向こうは `src/motion_groups.py` が実物から **8本**）。**向こうが正しい。**

    だから群の作り方は `src/judgeable.SOURCES` の1か所だけに置き、
    こちらは「その key の床はいつか」を訊くだけにします。
    **新しい A/B を足すときも、足す先はあちらです。**
    """
    from src import judgeable as SJ                             # 遅く読む

    key = str(need.get("key") or "")
    src = SJ.SOURCES.get(key)
    if src is None and key in getattr(SJ, "ACCRUING", ()):
        # **これから積む群**（`src/judgeable.ACCRUING`）。`Floor` の見張りには
        # 入れないが、**期限はここで推定できる**（下の `_project_nth`）。
        _make_m, n_m = SJ.MEMBER_SOURCES[key]
        src = ((lambda k=key: SJ._days(SJ.members(k))), n_m)
    if src is None:
        return Answer(None, f"**`src/judgeable.SOURCES` に無い key です**: {key!r}"
                            "（新しい A/B は、あちらに足すこと）")
    make, n = src
    try:
        floor = SJ.Floor(key=key, deadline=as_of, groups=make(), min_per_group=n)
    except Exception as e:                                     # noqa: BLE001
        return Answer(None, f"**{key} の群を数えられませんでした**: {e}")
    ready = floor.ready
    parts = []
    for g in sorted(floor.groups):
        nth = floor.nth[g]
        parts.append(f"{g} 予約{len(floor.groups[g])}本/"
                     + (f"{n}本目 {nth:%m/%d}" if nth else f"**あと{n - len(floor.groups[g])}本**"))
    body = f"{key}（`src/judgeable.py`）: " + " ／ ".join(parts)
    if ready is None:
        # **「群がそろわない ＝ 日が出せない」は、もうやめます**（2026-08-26 夜）。
        #
        # 同じ機械の `_ans_published_group` は、**この形をとっくに解いています**
        # （すぐ上の `_project_nth`: 作る速さ × 作ってから公開までの遅れ）。
        # 前の回の申し送りが「同じ形を次は `eta.py` の外で探すこと。
        # `live_slots` ／ `judgeable` ／ `ab_split` は**まだ当てていません**」と
        # 名指ししていた、その `judgeable` 側がここです。
        #
        # **日が出ないと何が止まるか**（`_project_nth` の docstring と同じ）:
        # `arm_speed.forward()` の `undated` に落ちて θ に数えられず、
        # `queue_lag` も `Floor` も動かせず、到達日はそのぶん止まります。
        #
        # **推定に要るのは「群を作りはじめた日」だけ**なので、`needs` の `since:`
        # から取ります。**書いていない前提は、今までどおり `None`** ——
        # 勝手に日を作らないため（`landed` を推測すると、群ごとに別の日が出ます）。
        since = str(need.get("since") or "")
        if not since:
            return Answer(None, body + " → **群がそろわないので日が出ません**"
                                "（`needs` に `since:`（群を作りはじめた日）を足せば、"
                                "作る速さと公開の遅れから推定します）")
        rows_all = _rows("uploaded.jsonl")
        nths: list[date] = []
        slacks: list[int] = []
        notes: list[str] = []
        for g in sorted(floor.groups):
            got = floor.nth[g]
            if got is not None:
                nths.append(got)
                continue
            pub = sorted(d.isoformat() for d in floor.groups[g])
            proj = _project_nth(rows_all, pub, n, since, as_of)
            if proj is None:
                return Answer(None, body + f" → **{g} がまだ1本もありません**"
                                           "（作れば動きます）")
            nth_g, rate, lead, sl, warn = proj
            nths.append(nth_g)
            slacks.append(sl)
            notes.append(f"{g} は**推定**（{rate:.2f}本/日・作ってから公開まで"
                         f"中央値 {lead}日{warn}）→ {n}本目 {nth_g:%m/%d}")
        nth = max(nths)
        band = max(slacks) if slacks else analytics_lag_band()
        return Answer(nth + timedelta(days=SJ.SETTLE_DAYS + SJ.ANALYTICS_LAG_DAYS),
                      body + " ／ " + " ／ ".join(notes)
                      + f" ＋ 落ち着く {SJ.SETTLE_DAYS}日 ＋ 遅れ {SJ.ANALYTICS_LAG_DAYS}日"
                        f"（**±{band}日**。伸び率からの推定なので、この幅の中の"
                        "書き換えは意味を持ちません）",
                      slack=band)
    band = analytics_lag_band()
    tail = (f"（**＋{band}日／−0日** —— 遅れは1日の中で動きますが、**上にしか動きません**。実測 3日 が 381・4日 が 57・**2日 は 0**）" if band else "")
    return Answer(ready, body + f" ＋ 落ち着く {SJ.SETTLE_DAYS}日 "
                                f"＋ 遅れ {SJ.ANALYTICS_LAG_DAYS}日{tail}",
                  slack=band, slack_down=0)


def answer(need: dict, as_of: date, lag: int) -> Answer:
    kind = str(need.get("kind") or "").strip()
    if kind == "now":
        return _ans_now()
    if kind == "external":
        return _ans_external(need)
    if kind == "accrual":
        return _ans_accrual(need, as_of)
    if kind == "published_group":
        return _ans_published_group(need, as_of, lag)
    if kind == "after":
        return _ans_after(need, lag)
    if kind == "group_key":
        return _ans_group_key(need, as_of)
    return Answer(None, f"**知らない kind です**: {kind!r}")


@dataclass
class Verdict:
    claim: str
    deadline: date | None
    #: 判定できる最早の日（`needs` の最も遅いもの）
    ready: date | None
    answers: list[Answer]
    #: `needs:` が書かれていない
    unchecked: bool = False
    #: 元の `needs:`（`note` を横に出すため）
    needs: list[dict] | None = None

    @property
    def ready_at(self) -> datetime | None:
        """**`ready` の日のうち、この時刻まで計器が読めない**（`Answer.ready_at` の最も遅いもの）。

        `None` ＝ その日なら一日じゅう読める。**`ready` と対で読むこと** ——
        この時刻は `ready` の日についての話で、それより前の日には当たりません。
        """
        ats = [a.ready_at for a in self.answers if a.ready_at is not None]
        return max(ats) if ats else None

    @property
    def unreachable(self) -> bool:
        """**こちらの手では起こせない**要件を含むか（`Answer.unreachable`）。

        `Answer` はこれを 2026-08-25 から持っていましたが、**ここまで上がって
        いませんでした。** 結果、`mark` は下の2つに**同じ `[!!]`** を付けます:

            収益化の審査（登録者があと 999人）        …… **こちらでは起こせない**
            今日 立てたばかりで、伸び率がまだ出ない  …… **明日には出る**

        **直し方が正反対です。** 前者は前提の立て方ごと変えるしかなく、
        後者は**何もしないのが正解**です。同じ札を付けると、
        読んだ回は区別できません（`src/measure_window.py` が
        「直し方が違うものに同じ札が付く」と書いているのと同じ形）。
        """
        return any(a.unreachable for a in self.answers)

    @property
    def warming(self) -> bool:
        """**まだ数えはじめたところ**（日が出ないが、待てば出る）。

        **2026-08-26 夕に足した。** この日、きょうだいの回が 19:08 JST に
        前提を1件 立て、その 11分後 に `[!!] 判定できる日が出せません` と
        印字されました。**正しく走っている前提です** ——
        `since` から 1日 しか経っていないので伸び率が出ないだけで、
        **明日には日が出ます。**

        **なぜこの回に分けたか**: 同じ回に
        `test_遅すぎる期限が残っていないこと` を入れて、
        **`deadline_check` の出力に赤い検査を付けました。**
        読まれる度合いが上がったぶん、**紛らわしい札の危険も上がります** ——
        直す必要のない前提を「判定できない」と読んで畳む回が出ます。
        """
        return self.ready is None and not self.unchecked and not self.unreachable

    @property
    def mark(self) -> str:
        if self.unchecked:
            return "[??]"
        if self.warming:
            # **[!!] にしないこと。** 待てば日が出ます（上の `warming`）。
            return "[..]"
        if self.ready is None:
            return "[!!]"
        if self.deadline is None:
            return "[!!]"
        return "[!!]" if self.slips else "[OK]"

    @property
    def slack(self) -> int:
        """`ready` を決めた要件の帯の幅（日）。**推定でない要件は 0**。"""
        if self.ready is None:
            return 0
        return max([a.slack for a in self.answers if a.ready == self.ready] or [0])

    @property
    def slack_down(self) -> int:
        """**`ready` が早くなりうる幅**（`slack` は遅くなりうる幅）。

        **帯は左右対称ではありません**（`Answer.slack_down` の註）。
        遅れから作った日は **+1／−0** —— 遅れの実測は 3日 と 4日 だけで、
        **2日 だった観測が1つもない**のに、`ready` は小さいほう（3日）で
        作っているからです。**その日はもう最速**で、下へは動きません。
        """
        if self.ready is None:
            return 0
        got = [a.slack if a.slack_down is None else a.slack_down
               for a in self.answers if a.ready == self.ready]
        return max(got or [0])

    @property
    def slips(self) -> bool:
        """期限が、データの来る日より前に置かれているか。**帯の中なら言いません。**

        **見るのは下向きの幅です**（2026-08-27 夜に分けた）。ここが `slack`
        （上向き）だったせいで、**同じ機械の2か所が逆の指示**を出しました:

            `src/judgeable.py`  title_form 16本目 08/31 ＋3＋3 → **09/06 へ延ばすこと**
            ここ                判定できるのは 09-06（±1日）→ **書き換えないこと**

        遅れが 2日 だった観測は1つも無いので、**09/05 に判定できる目はありません。**
        `judgeable` が正しく、こちらが 1日 甘くしていました。
        """
        return (self.ready is not None and self.deadline is not None
                and (self.ready - timedelta(days=self.slack_down)) > self.deadline)

    @property
    def waits(self) -> int:
        """**データはもう揃うのに、期限がまだ先**。その待ち日数（0 なら待っていない）。

        **こちらの向きは、8日ぶん黙って流れていました**（2026-08-25 22:5x）。
        `slips`（期限が早すぎる）だけを見ていて、逆向きは
        「**期限に間に合います**」という緑の行になっていたからです。

        **軌跡の腕は、前提を1件閉じたときだけ動きます**（`src/arm_speed.py`）。
        だから「データは揃っているが期限がまだ先」の日数は、
        **到達日がまるごと止まっている日数**そのものです。
        実測（2026-08-25・開いている16件）: **10件・合計 46日・平均 4.6日**、
        いちばん大きいもので **14日**。
        """
        if self.ready is None or self.deadline is None:
            return 0
        # **帯の中の待ちは数えません**（数えると、推定のゆらぎのぶんだけ
        # 「縮めること」と言い続け、書き換えても次の回にまた言われます）。
        return max(0, (self.deadline - self.ready).days - self.slack)


def load(path: Path | None = None) -> list[dict]:
    p = path or (ROOT / "config" / "hypotheses.yaml")
    return yaml.safe_load(p.read_text(encoding="utf-8")).get("hypotheses", [])


def check(items: list[dict], as_of: date | None = None, lag: int | None = None) -> list[Verdict]:
    as_of = as_of or today_jst()
    lag = analytics_lag_days(as_of) if lag is None else lag
    out: list[Verdict] = []
    for h in items:
        if h.get("closed_on") or h.get("verdict"):
            continue
        try:
            dl = date.fromisoformat(str(h.get("deadline")))
        except (TypeError, ValueError):
            dl = None
        needs = h.get("needs") or []
        if not needs:
            out.append(Verdict(str(h.get("claim") or ""), dl, None, [], unchecked=True))
            continue
        ans = [answer(n, as_of, lag) for n in needs]
        # **判定できる日は、いちばん遅い要件で決まります。** 1つでも出せなければ出ません。
        ready = None if any(a.ready is None for a in ans) else max(a.ready for a in ans)
        out.append(Verdict(str(h.get("claim") or ""), dl, ready, ans, needs=list(needs)))
    return out


def lines(vs: list[Verdict], lag: int) -> list[str]:
    out = ["=== この期限までに、判定に要るデータは在るか（scripts/deadline_check.py）===",
           f"  実データは **{lag}日 遅れ**ています。"
           f"**「公開から{settle_mod.SETTLE_DAYS}日」に必ず足すこと。**"
           f"（この {settle_mod.SETTLE_DAYS}日 は実測です —— `python -m src.settle`）"]
    for v in sorted(vs, key=lambda x: (x.deadline or date(2099, 1, 1))):
        dl = f"{v.deadline:%m-%d}" if v.deadline else "  ??  "
        out.append(f"  {v.mark} {dl}  {v.claim[:58]}")
        if v.unchecked:
            out.append("         **`needs:` が書かれていません。** この期限は"
                       "「データが来るか」を一度も確かめていません")
            continue
        for a, n in zip(v.answers, [x.get("note") for x in (v.needs or [])] or
                                    [None] * len(v.answers)):
            out.append(f"         {a.why}")
            if n:
                out.append(f"           {str(n).strip()}")
        if v.warming:
            # **「出せません」と言わないこと。** 待てば出ます。
            #
            # **待ち方は1つではありません**（2026-08-27 に分けた）。ここは
            # 「伸び率が出れば」を**無条件**で言っていましたが、`at_time_jst` の
            # 要件は**今日の決まった時刻に出る**もので、伸び率とは関係ありません。
            # 待ち方を1つに丸めると、**次の回が「まだ何日も先だ」と読みます。**
            # **手が在るなら、待ち方より手を出すこと**（2026-08-27・`Answer.todo`）。
            # ここは `at_time_jst` が在れば無条件に「その時刻まで待つこと」と
            # 出していました。**時刻が過ぎた後も同じ文を出します** ——
            # 実測 14:24 JST に「今日の 14:00 JST に出ます。その時刻まで待つこと」。
            todo = next((a.todo for a in v.answers if a.todo), "")
            when = next((str(x.get("at_time_jst")) for x in (v.needs or [])
                         if x.get("at_time_jst")), "")
            if todo:
                out.append(f"         → {todo}")
            elif when:
                out.append(f"         → **今日の {when} JST に出ます。**"
                           "伸び率の話ではありません —— **その時刻まで待つこと**"
                           "（畳まないこと・条件を緩めないこと）")
            else:
                out.append("         → **まだ数えはじめたところです。**"
                           "伸び率が出れば日が出ます —— **この回は何もしないのが正解**です"
                           "（畳まないこと・条件を緩めないこと）")
        elif v.ready is None:
            out.append("         → **判定できる日が出せません。**"
                       "期限を置いても、その日に言えることはありません")
        elif v.slips:
            gap = (v.ready - v.deadline).days           # type: ignore[operator]
            out.append(f"         → **判定できるのは {v.ready:%m-%d}。期限は {gap}日 早すぎます。**"
                       f"  `deadline: \"{v.ready}\"` へ延ばすこと"
                       "（**`falsified_if` は緩めないこと** —— 動かすのは期限だけ）")
        elif v.waits:
            # **緑の行にしないこと。** ここが「もう判定できるのに待っている」側です。
            out.append(f"         → 判定できるのは {v.ready:%m-%d} なのに、"
                       f"期限は {v.waits}日 **後ろ**に置いてあります。"
                       f"  `deadline: \"{v.ready}\"` へ**縮めること**"
                       "（**`falsified_if` は緩めないこと** —— 動かすのは期限だけ）")
        elif v.slack:
            out.append(f"         → 判定できるのは {v.ready:%m-%d}（±{v.slack}日の推定）。"
                       f"**期限 {v.deadline:%m-%d} はその帯の中**です —— "
                       "**書き換えないこと**（帯の中で動かしても、届く日は1日も動きません）")
        else:
            out.append(f"         → 判定できるのは {v.ready:%m-%d}。**期限とちょうど同じ**です")
    bad = [v for v in vs if v.slips]
    unk = [v for v in vs if v.ready is None and not v.unchecked and not v.warming]
    warm = [v for v in vs if v.warming]
    non = [v for v in vs if v.unchecked]
    late = [v for v in vs if v.waits]
    out.append("")
    out.append(f"  期限が早すぎる **{len(bad)}件** ／ 判定できる日が出せない **{len(unk)}件** "
               f"／ 確かめていない **{len(non)}件** ／ 開いている {len(vs)}件")
    if warm:
        out.append(f"  まだ数えはじめたところ **{len(warm)}件**"
                   "（**直すところはありません。**待てば日が出ます）: "
                   + " ／ ".join(v.claim[:26] for v in warm))
    if late:
        total = sum(v.waits for v in late)
        worst = max(late, key=lambda v: v.waits)
        out.append(f"  **期限が遅すぎる {len(late)}件 —— 合計 {total}日 の待ち**"
                   f"（平均 {total / len(late):.1f}日・最大 {worst.waits}日）。")
        out.append("    **軌跡の腕は、前提を1件閉じたときだけ動きます。**"
                   "この合計は、**到達日がまるごと止まっている日数**です ——"
                   "データは揃っているのに、期限がまだ先だという理由だけで止まっています。")
        out.append(f"    最大: {worst.ready:%m-%d} に判定できるのに"
                   f" {worst.deadline:%m-%d}  {worst.claim[:44]}")
    return out


def ready_by_claim(items: list[dict] | None = None, as_of: date | None = None,
                   lag: int | None = None) -> dict[str, date]:
    """**claim → 判定できる最早の日。**（`src/arm_speed.next_close` が読みます）

    `deadline` は置いた回の勘、`ready` は**データが実際に揃う日**です。
    2つを別々の場所が持っていて、**到達日を印字する側は `deadline` しか
    読んでいませんでした**（2026-08-25 22:5x に繋いだ）。
    """
    vs = check(items if items is not None else load(), as_of=as_of, lag=lag)
    return {v.claim: v.ready for v in vs if v.ready is not None}


def unready_claims(items: list[dict] | None = None, as_of: date | None = None,
                   lag: int | None = None) -> set[str]:
    """**判定できる日が出せない claim**（`warming` と `unreachable`）。

    `ready_by_claim()` はこれを**黙って落とします**（`ready is not None` で絞るので）。
    落とされた claim を `src/arm_speed.next_close()` が受け取ると、
    **`deadline` のほうへ落ちます** —— `deadline` は置いた回の勘なので、
    **「今日が期限。だから今日 閉じられる」**という嘘になります。

    実測 2026-08-26 20:4x（この関数を足した回）:

        `scripts/eta.py`      「**期日の来た前提があります**（2026-08-26）→
                               **この回は `verdict` で日付が動かせます**」
        `scripts/deadline_check.py`
                              「[..] 要 8 ／ いま 7 ・ 要 3 ／ いま **0** →
                               **まだ数えはじめたところです。何もしないのが正解**」

    **同じ1件です。** 判定に要る本は1本もありませんでした。

    **`unchecked`（`needs:` が書かれていない）は入れません** ——
    「判定できない」と分かったのではなく、**何が要るか誰も書いていない**だけ。
    ここに入れると、`needs:` を書かないほうが得になります。
    """
    vs = check(items if items is not None else load(), as_of=as_of, lag=lag)
    return {v.claim for v in vs if v.ready is None and not v.unchecked}


def not_open_yet(items: list[dict] | None = None, now: datetime | None = None,
                 lag: int | None = None) -> set[str]:
    """**判定できる日は今日だが、その日の中でまだ時刻が来ていない claim。**

    ## なぜ `unready_claims()` では足りないのか（2026-08-28 03:1x に踏んだ）

    あちらは「**日が出せない**」を捕まえます。ここが捕まえるのは
    「**日は出た。今日だ。ただし読めるのは 16:00 から**」です。
    `Answer.ready` は日付なので、**時刻はそこで落ちます** ——
    落ちたぶん、その日の 00:00〜16:00 に走る回は全部
    `arm_speed.next_close()` から「今日が判定できる日」を受け取り、
    `eta.py` の頭3行に「**この回は `verdict` で日付が動かせます**」と出ます。

    実測 2026-08-28 03:1x（この関数を足した回）:

        `scripts/eta.py`   「**期日の来た前提があります**（2026-08-28）→
                            **この回は `verdict` で日付が動かせます**」
        `scripts/status.py`「期限が来ていて、**いま判定できる前提: なし**」
        実物              `data/views.jsonl` のいちばん新しい点は **08-27 16:34 JST**。
                          要件は 08-27 **22:00 JST 以降**の点。取り直す
                          `snapshot.py` は **403**（214回 観測）。枠が戻るのは 16:00 JST

    **2つの道具が同じ回に逆のことを言っていました。** `status.py` が正しい。
    この窓は **16時間**（00:00〜16:00 JST）あり、そのあいだの回は全部
    `verdict` を探しにいって、`403` を1つ買って帰ります ——
    `docs/JOURNAL.md` 2026-08-28 00:0x の申し送りが
    「**この回に verdict が選べなかったのは日枠のせいだけです**」と書いています。

    **覆る条件**: `Answer.ready` そのものが `datetime` になったら、
    この関数は要りません（呼び手が時刻ごと比べられるので）。
    """
    now = now or datetime.now(JST)
    vs = check(items if items is not None else load(), as_of=now.date(), lag=lag)
    out: set[str] = set()
    for v in vs:
        at = v.ready_at
        if v.ready is None or at is None:
            continue
        if v.ready == now.date() and at > now:
            out.add(v.claim)
    return out


# --- **印字ではなく、書き換えるところまでやる**（2026-08-26・最適化の回）---
#
# この道具は **2026-08-25 13:54Z** から「期限が遅すぎる N件 —— 合計 M日 の待ち」と
# 印字しています。`scripts/status.py` も同じ日の 22:5x から、**毎回の最初に読まれる
# 場所**で「→ `deadline` をその日まで**縮めること**。**この回の成果になります**」と
# 出しています。**それでも、1件も縮んでいません。**
#
#     検出を足した      2026-08-25 13:54Z   そのとき **46日**
#     それから撃った回  **666 commits**
#     いま              **64日**（3件・最大 33日）  ← **増えています**
#
# **同じ 20時間 に、逆向きの書き換えは起きています。**
# `e664d5a`（08-25 21:46Z）は stat_split を 09-14 → **10-06 へ 22日 延ばし**ました。
# 理由は commit がそのまま書いています ——「**赤い検査が2件**」。
# 遅すぎる側の検査は `assert total >= 0` ＝ **何も主張していません。**
#
#     延ばす向き  赤い検査あり  → 20時間で 2回 起きた
#     縮める向き  印字のみ      → 666 commits で 0回
#
# **印字が読まれていないのではありません。印字は「判断」を要求します。**
# 赤い検査は判断を要求しません（直すか、直さないかしかない）。
# だからここは、**印字と同じ内容を、自分で書き戻す手**を持ちます。


def _rewrite(want: str, path: Path | None = None, as_of: date | None = None,
             lag: int | None = None, dry_run: bool = False) -> list[tuple[str, str, str]]:
    """**期限の1行だけを、判定できる日（`ready`）へ寄せて書き戻す。**

    `want` は向き —— `"waits"`（遅すぎる期限を縮める）か
    `"slips"`（早すぎる期限を延ばす）。返りは `[(claim, 前, 後), ...]`。

    **2つの向きは同じ書き換えです。** 読むのも書くのも `deadline:` の1行で、
    寄せ先はどちらも `v.ready`（データが実際に揃う日）です。
    **違うのは「どちらへ動くか」だけ**なので、guard を2つに分けません ——
    分けたほうが、片方だけ直る事故が起きます。

    **`--shrink` の側の註**（この関数を2つの向きで共有する前からのもの）:

    返り: `[(claim, 前の期限, 後の期限), ...]`。**API 0単位・本は0本。**

    ## 触らないもの

    - **`falsified_if` には触りません。** 動かすのは `deadline:` の1行だけです。
      もっと n が要るなら、動かすのは **`needs.count` のほう**です ——
      期限を水増しして待つのは `needs` に嘘を書いているのと同じで、
      `src/arm_speed.forward()` は **`ready` の側**を読むので、
      **予測だけが「その日に閉じる」前提のまま**残ります（＝到達日が早すぎる）。
    - **`slips`（期限が早すぎる）側は動かしません。** ここは縮める向き専用です。
      延ばす側には、もう赤い検査が付いています。

    ## **`yaml.dump` で書き戻さないこと**

    `config/hypotheses.yaml` は 3,300行 のうちほとんどが註で、
    `safe_load` → `dump` すると**全部 消えます**（外れた理由も、
    しきい値の引き方も、次に来た側が判断する材料も）。
    だから**行単位で `deadline:` の1行だけ**を置き換え、
    書く前に **読み直して同じ値になるか**を確かめます。
    """
    p = path or (ROOT / "config" / "hypotheses.yaml")
    text = p.read_text(encoding="utf-8")
    rows = text.split("\n")
    start = next((i for i, l in enumerate(rows) if l.startswith("hypotheses:")), None)
    if start is None:
        raise RuntimeError("`hypotheses:` の節が見つかりません")
    end = next((i for i in range(start + 1, len(rows))
                if re.match(r"^[A-Za-z_]+:", rows[i])), len(rows))
    heads = [i for i in range(start + 1, end) if rows[i].startswith("  - ")]
    dl_at: dict[int, int] = {}
    for k, h in enumerate(heads):
        stop = heads[k + 1] if k + 1 < len(heads) else end
        j = next((i for i in range(h, stop) if re.match(r"^\s+deadline:", rows[i])), None)
        if j is not None:
            dl_at[k] = j
    items = yaml.safe_load(text).get("hypotheses", [])
    if len(items) != len(heads):
        raise RuntimeError(f"項目の数が合いません（読めた {len(items)} 対 行 {len(heads)}）"
                           "。**書きません**")
    by_claim: dict[str, int] = {}
    for k, h in enumerate(items):
        if h.get("closed_on") or h.get("verdict"):
            continue
        c = str(h.get("claim") or "")
        if c in by_claim:
            raise RuntimeError(f"開いている前提に同じ claim が2つあります: {c[:40]}。**書きません**")
        by_claim[c] = k
    done: list[tuple[str, str, str]] = []
    for v in check(items, as_of=as_of, lag=lag):
        if v.ready is None or v.deadline is None:
            continue
        # **向きは1か所でだけ決めます。** `waits` は「データは揃うのに期限が後ろ」、
        # `slips` は「期限がデータの来る日より前」。どちらも寄せ先は `v.ready` です。
        if want == "waits" and not v.waits:
            continue
        if want == "slips" and not v.slips:
            continue
        # **逆向きへは1日も動かしません。** `ready` は推定なので、帯の揺れで
        # 向きが裏返ることがあります。裏返ったぶんを書くと、
        # 「縮めたつもりで延ばした」が黙って通ります。
        if want == "waits" and v.ready >= v.deadline:
            continue
        if want == "slips" and v.ready <= v.deadline:
            continue
        k = by_claim.get(v.claim)
        j = dl_at.get(k) if k is not None else None
        if j is None:
            continue
        indent = re.match(r"^(\s*)", rows[j]).group(1)      # type: ignore[union-attr]
        rows[j] = f'{indent}deadline: "{v.ready}"'
        done.append((v.claim, str(v.deadline), str(v.ready)))
    if not done:
        return []
    out = "\n".join(rows)
    # **書く前に読み直す。** 註を1行も落としていないか・値が入ったかを確かめます。
    back = yaml.safe_load(out).get("hypotheses", [])
    if len(back) != len(items):
        raise RuntimeError("書き換えたら項目の数が変わりました。**書きません**")
    want = {c: a for c, _b, a in done}
    for h in back:
        c = str(h.get("claim") or "")
        if c in want and str(h.get("deadline")) != want[c]:
            raise RuntimeError(f"書き換えが入っていません: {c[:40]}。**書きません**")
    if not dry_run:
        p.write_text(out, encoding="utf-8")
    return done


def shrink(path: Path | None = None, as_of: date | None = None,
           lag: int | None = None, dry_run: bool = False) -> list[tuple[str, str, str]]:
    """**遅すぎる期限を、判定できる日まで縮める**（`waits` の側）。"""
    return _rewrite("waits", path=path, as_of=as_of, lag=lag, dry_run=dry_run)


def extend(path: Path | None = None, as_of: date | None = None,
           lag: int | None = None, dry_run: bool = False) -> list[tuple[str, str, str]]:
    """**早すぎる期限を、判定できる日（`ready`）まで延ばす**（`slips` の側）。

    ## なぜ足したか（2026-08-28）

    この道具は `slips` の1件ごとに **``deadline: "YYYY-MM-DD"`` へ延ばすこと**と
    印字し、`tests/test_deadline_check.py::test_期限が_判定できる日より前に置かれていない`
    が**赤で止めます。** それでも、この回に撃った時点で **5件が赤のまま**でした:

        長尺の再生シェア…        09-10 < 09-11
        長尺の生成が落ちる主因…   08-27 < 08-29   ← **期限は昨日**
        冒頭1枚目の主役…          09-09 < 09-10
        engaged 比率は…           10-02 < 10-03
        冒頭0.9秒に絵の動き…      10-06 < 10-07

    上の註は「**延ばす向き 赤い検査あり → 20時間で 2回 起きた**」と書いています。
    **その観測は、直す手が1件のときのものです。** 5件を直すには
    3,300行の YAML を**手で5か所**書き換えることになり、
    `config/hypotheses.yaml` には手で動かした跡が **33件** 残っています。
    **赤い検査は「判断を要求しない」が、「手を要求しない」わけではありません。**
    縮める向きに手があって延ばす向きに無いのは、ただの非対称です。

    ## 緩めていないこと

    - 寄せ先は **`v.ready`**（データが実際に揃う日）だけです。1日も先へは置きません。
    - **`falsified_if` にも `needs.count` にも触りません。** n が足りないのなら、
      動かすのは `needs` のほうです（`shrink()` の註）。
    - **`slips` は帯の下向きの幅を見ています**（`Verdict.slips`）。
      推定のゆらぎの中では、この手は1件も動かしません。

    ## **これは「待てばよい」ではありません**

    `ready` が**毎回 後ろへ逃げる**前提は、積みが止まっています
    （`Answer.have` が動いていない）。この手はそれを**印字で名指しします** ——
    延ばした先が動かない保証はここには無いので、
    **同じ claim が何度も出てきたら、疑うのは期限ではなく `needs` のほう**です。
    """
    return _rewrite("slips", path=path, as_of=as_of, lag=lag, dry_run=dry_run)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", help="この日に判定するつもりで解く（YYYY-MM-DD）")
    ap.add_argument("--shrink", action="store_true",
                    help="**遅すぎる期限を、判定できる日まで縮めて書き戻す**"
                         "（`falsified_if` は触りません。**API 0単位**）")
    ap.add_argument("--extend", action="store_true",
                    help="**早すぎる期限を、判定できる日まで延ばして書き戻す**"
                         "（`falsified_if` は触りません。**API 0単位**）"
                         "—— `tests/test_deadline_check.py` の赤を、そのまま消す手です")
    ap.add_argument("--fit", action="store_true",
                    help="**両方の向きを1手で寄せる**（`--shrink` と `--extend`）。"
                         "期限は置いた回の勘・`ready` はデータの来る日なので、"
                         "**普通の回はこれでよい**")
    ap.add_argument("--dry-run", action="store_true",
                    help="`--shrink` / `--extend` / `--fit` が何を書くかだけ出す（書きません）")
    a = ap.parse_args(argv)
    as_of = date.fromisoformat(a.as_of) if a.as_of else today_jst()
    lag = analytics_lag_days(as_of)
    if a.shrink or a.extend or a.fit:
        head = "**書いていません**（--dry-run）" if a.dry_run else "書きました"
        moved = 0
        # **縮めるほうを先に撃ちます。** どちらも `deadline:` の1行を書き戻すので、
        # 同じ読み込みを2回またぐと、あとの回が前の回の書き換えを踏みます。
        # `_rewrite` は毎回 読み直すので、順に撃てば安全です。
        if a.shrink or a.fit:
            done = shrink(as_of=as_of, lag=lag, dry_run=a.dry_run)
            moved += len(done)
            if not done:
                print("  **縮める期限はありません**（`waits` が 0件）")
            else:
                total = sum((date.fromisoformat(b) - date.fromisoformat(af)).days
                            for _c, b, af in done)
                print(f"=== 遅すぎた期限を {len(done)}件 縮めました（{head}）"
                      f"—— 合計 **{total}日** ===")
                for c, b, af in done:
                    d = (date.fromisoformat(b) - date.fromisoformat(af)).days
                    print(f"  {b} → **{af}**（{d}日）  {c[:44]}")
        if a.extend or a.fit:
            # **`--fit` で `--dry-run` のときは、縮めた側が書かれていません。**
            # だから2手目は1手目の結果を見ていません —— 向きが別なので、
            # 同じ claim が両方に出ることはありません（`slips` と `waits` は排他）。
            done = extend(as_of=as_of, lag=lag, dry_run=a.dry_run)
            moved += len(done)
            if not done:
                print("  **延ばす期限はありません**（`slips` が 0件）")
            else:
                total = sum((date.fromisoformat(af) - date.fromisoformat(b)).days
                            for _c, b, af in done)
                print(f"=== 早すぎた期限を {len(done)}件 延ばしました（{head}）"
                      f"—— 合計 **{total}日** ===")
                for c, b, af in done:
                    d = (date.fromisoformat(af) - date.fromisoformat(b)).days
                    print(f"  {b} → **{af}**（+{d}日）  {c[:44]}")
                print("  **延ばしたのは期限だけです。** 同じ claim が次の回にもここへ出たら、"
                      "疑うのは期限ではなく `needs`（積みが止まっている）ほうです")
        if moved:
            print("  **`falsified_if` は1文字も触っていません。**"
                  "もっと n が要るなら、動かすのは `needs.count` のほうです")
        return 0
    vs = check(load(), as_of=as_of, lag=lag)
    # **印字する道の1か所だけで積みます**（`record_estimates()` の註）。
    # 純粋な関数の中で書くと、控えは「この機械が何回 撃たれたか」を数えます。
    record_estimates(vs, as_of=as_of)
    print("\n".join(lines(vs, lag)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
