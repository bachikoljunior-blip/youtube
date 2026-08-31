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
import functools
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


@functools.lru_cache(maxsize=8)
def _rows(name: str) -> list[dict]:
    """`data/<name>` を1行1件で読む。**1回の走りにつき1度だけ読みます。**

    ## なぜ `lru_cache` なのか（2026-08-31 に、`eta.py` を profile して足した）

    **`python scripts/eta.py` の 375秒 のうち 297秒（79%）がここでした。**
    `cProfile` の実測（`--offline` でも同じ。**API ではありません**）:

        deadline_check.check()          297.3秒   ← 全体の 79%
          latest_views()                285.1秒   （1,665回 呼ばれる）
            _rows()                     211.9秒   （1,705回）
              json.loads                197.8秒   **37,991,128回**

    `data/views.jsonl` は **21,055行**。それを **1,705回** 読み直していました
    （21,055 × 1,705 ≒ 3,590万 ＝ 上の `json.loads` の回数）。
    **同じファイルを、同じ走りの中で、1,700回 パースし直していた**だけです。

    ## **これは、この repo で2度目です**

    `CLAUDE.md` に前の1件が書いてあります —— `eta.py --reflect` が
    **1分37秒 → 8.5秒**になったとき、原因は
    「`day_cap.cap()`（`data/views.jsonl` を丸ごと読む・59ms）を
    1回の走りで 1,000回 前後 呼び直していた」ことでした。
    **同じファイル・同じ形・別の入口**です。**直したのは片方だけでした。**

    ## 走っている最中に書き換わらないか

    `data/*.jsonl` は**追記**で、書くのは別の回（別プロセス）です。
    1回の走りの中で `eta.py` / `deadline_check.py` がここへ書くことはありません
    （書くのは `config/hypotheses.yaml` の期限の行だけ）。
    **返りのリストを呼ぶ側が書き換えないこと** —— いまの呼び出しは
    走査と絞り込みだけで、1か所も書き換えていません（`uploaded()` /
    `latest_views()` / `long_ids()` / 1334行 / 1986行）。

    ## これが覆る条件

    - **同じプロセスの中で `data/*.jsonl` に追記してから読み直す**手ができたら、
      そこは `_rows.cache_clear()` を呼ぶこと。**呼ばずに足すと、
      追記したはずの行が見えません**（いちばん見つけにくい壊れ方）。
    - 返りを書き換える呼び出しを足すなら、**そこで `list(...)` すること。**
      ここでコピーを返さないのは、コピー自体が 21,055件 × 呼び出し回数 だからです。
    - `src/day_cap.py` 側は **`lru_cache` にしていません**（検査が
      `day_cap.cap` を差し替えるため。`scripts/eta.py:286` の註）。**あちらを
      同じ形にしないこと** —— 理由が違います。
    """
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


def _deep_short():
    """`src/deep_short.py` を遅延で読む（`day_cap` が `views.jsonl` を舐めるので重い）。"""
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src import deep_short
    return deep_short


def deep_short_arm(side: str = "処置") -> int:
    """**比べられる本**の数（`falsified_if` の群の作り方そのまま）。

    **`uploaded` の本数を数えないこと**（2026-08-29 06:3x に踏んだ）。
    台帳の `count_expr` は「`s-` で始まらない公開済みの本」を数えていて
    **15本 → 足りています**と出していましたが、`falsified_if` が要求する群
    （**その日の生きた帯 ＋ 齢48時間 の読み ＋ ショートに分類済み**）は
    **4本**でした。門は「作った／公開した」を、手順は「**比べられる**」を
    数えています。
    """
    return _deep_short().arm_n(side)


def deep_short_usable_days() -> int:
    """**比が出せる公開日**の数（生きた帯 ＋ 齢48時間 ＋ 両群そろい）。

    すぐ上の `deep_short_days()` は、そのうち**分類だけ**を見ています ——
    実測 2026-08-29: あちらは **3日**、こちらは **2日**。
    **`falsified_if` が数えているのはこちら**なので、門はこれを読みます。
    `deep_short_days()` は古い台帳の行が残っているあいだ置いてあります。
    """
    return _deep_short().usable_days()


def reveal_hold_arm(side: str = "処置") -> int:
    """**「完成形の保持」で比べられる本**の数（`src/reveal_hold.arm_n`）。

    **`rows('uploaded.jsonl')` を直接 数えないこと**（2026-08-31 に踏んだ）。
    控えは**1本につき1行ではありません**（実測 850行 / 735本 —— 予約を動かす
    たびに行が増える）。この前提の `count_expr` は行を数えていて、

        式の答え          **17** → この関数のすぐ下 `_ans_accrual` が
                                   「要 16 ／ いま 17 → **足りています**」
        本で畳むと        **11**（`KfQeYEJwL7Q` だけで4行）
        うちショート       **8**（長尺は `reveal_variants` を通らない）
        齢48時間 を超えた  **1** ← `falsified_if` が比べられるのはこれだけ

    そこから `ready_by_claim()` → `arm_speed.next_close()` →
    `scripts/eta.py` の頭3行「**この回は `verdict` で日付が動かせます**」
    まで通ります。**頭3行しか読まない回は、処置1本で前提を閉じます。**

    `deep_short_arm()`（すぐ上）と**同じ形の穴で、こちらが2件目**です。
    """
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from src import reveal_hold                                # noqa: PLC0415
    return reveal_hold.arm_n(side)


EXPR_NS = {"json": json, "rows": _rows, "date": date, "ab_members": ab_members,
           "deep_short_days": deep_short_days,
           "deep_short_arm": deep_short_arm,
           "deep_short_usable_days": deep_short_usable_days,
           "reveal_hold_arm": reveal_hold_arm,
           "latest_views": latest_views, "uploaded": uploaded, "long_ids": long_ids}


#: **`count_expr` の中の名前 → その数が読んでいる計器**（と、取り直す手）。
#:
#: ## なぜ要るか（2026-08-31・最適化の回。**この回に実測して足した**）
#:
#: すぐ下の `_stale_todo` は「計器が止まっているのに『あと N日』と出る」を塞ぐ門で、
#: **要件が `needs.data_file:` で自己申告したときだけ**効きます。
#: `_data_file_coverage` はその申告率を毎回 印字し、docstring にこう書いています ——
#: 「**ここは埋めません。数を出すだけにします。どの計器を読むかは要件ごとに違い、
#: 機械には決められません（`count_expr` の中身は読めない）。推測で `data_file:` を
#: 書くと、こんどは「在ることになっている点」で判定します。それは黙って通すより悪い**」。
#:
#: **前半は正しく、後半は外れています。** 「機械には決められません」の根拠は
#: 「`count_expr` の中身は読めない」ですが、**`count_expr` が動くのは
#: すぐ上の `EXPR_NS` の中だけ**です。名前は閉じた集合で、どれがどのファイルを
#: 開くかは、このファイル自身に書いてあります（`latest_views` → `views.jsonl` …）。
#: **散文からパスを拾うのとは別物です**（`newest_point` の「散文から拾わないこと」は
#: `what:` の地の文の話で、**式そのもの**の話ではありません）。
#:
#: ## 埋めないでいるあいだに何が起きていたか（実測 2026-08-31 05:0x）
#:
#:     `data/views.jsonl` のいちばん新しい点   **2026-08-29T08:31Z**（**45時間 前**）
#:     08/30・08/31 に積まれた行               **0行**（08/06 以来はじめて2日 続けて0）
#:     その計器を数えている開いた前提           **3件**（期限 09-02 / 09-03 / 09-23）
#:     そのどれかが `data_file:` を申告している  **0件**
#:     そのとき `deadline_check` が出していた文  「あと 3日」「まだ数えはじめたところです」
#:
#: **「あと3日」は待てば来る文です。計器は止まっているので、待っても来ません。**
#: `scripts/eta.py` の頭は、その日「**この回に閉じられる前提はありません**」と
#: 印字しています —— 到達日をいちばん大きく動かすのは θ（前提が閉じる速さ）で、
#: **その θ が、止まった計器のぶんだけ低く出ていた**ことになります。
#:
#: ## 何を門にするか
#:
#: **申告が先。** `data_file:` が書いてあればそちらを使います（人が
#: 「この式はこの計器で待つ」と決めた場合を、機械が上書きしないため）。
#: 書いていないときだけ、ここから引きます。**引けなければ、今までどおり黙ります。**
#:
#: ## 覆る条件
#:
#: - **`EXPR_NS` に名前を足したら、ここにも足すこと。**
#:   `tests/test_deadline_expr_meters.py` が、片方だけ増えたら落とします
#:   （計器を開かない名前は `_EXPR_NO_METER` に置くこと）
#: - 1周ごとに全計器を取り直す作りにしたら、この表ごと外してよい
#:   （`_stale_todo` の「覆る条件」と同じ）
_EXPR_METERS: dict[str, tuple[str, ...]] = {
    # `latest_views()` は `views.jsonl` の累計を読むだけ。**この行が積まれるのは
    # `snapshot.record()`（＝ `status.py` から毎回）だけ**で、チャンネル側で
    # 再生が伸びても、取り直さないかぎり1回も動きません。
    "latest_views": ("data/views.jsonl",),
    "long_ids": ("data/batch_runs.jsonl",),
    "uploaded": ("data/uploaded.jsonl",),
    # `src/deep_short` は3つ読みますが、**止まるのは `views.jsonl`** です
    # （齢48時間 の読み。`video_forms.json` は `rpm_mix` が別に取り直す）。
    "deep_short_arm": ("data/views.jsonl", "data/video_forms.json"),
    "deep_short_days": ("data/video_forms.json",),
    "deep_short_usable_days": ("data/views.jsonl", "data/video_forms.json"),
}

#: **計器を開かない名前**（`EXPR_NS` にあるが、この表に載らないもの）。
#: `rows` は引数でファイルが決まるので、`_expr_meters()` が別に拾います。
_EXPR_NO_METER = ("json", "date", "rows", "ab_members", "reveal_hold_arm")

#: その計器を取り直す手（`needs.refresh:` を書いていない要件に添える）。
#:
#: **`_refresh_pool_note` が読める名前で書くこと。** あちらは
#: `src.upload_cap.DATA_API_TOOLS` との文字列一致で「いまこの窓で撃てるか」を
#: 決めるので、同じことをする道具でも**一覧に載っているほうの名前**を書きます ——
#: `views.jsonl` は `scripts/status.py` でも積めますが、あれは一覧に無く
#: （Analytics も棚卸しも回すので 40〜60秒）、**日枠を使わない手として印字されます。**
#: 実際には `channels.list` で 403 を踏んで**表ごと落ち、`record()` まで届きません**
#: （2026-08-31 05:1x の実測。だから `views.jsonl` が 45時間 止まっていました）。
#: `scripts/snapshot.py` は `videos.list` だけ・**571本 で 12単位**で、
#: 一覧にも載っています。
#:
#: **作る台帳（`batch_runs.jsonl`）はここに載せません** —— あれは「取り直す」もので
#: はなく「作ると増える」ものなので、取り直す手を名指しすると嘘になります
#: （`_ledger_frozen` の註）。載せなければ「…を取り直すこと」に落ちます。
_METER_REFRESH: dict[str, str] = {
    "data/views.jsonl": "python scripts/snapshot.py",
    "data/video_forms.json": "python -m src.rpm_mix --forms",
    "data/reach.jsonl": "python scripts/reach.py",
}

_ROWS_CALL = re.compile(r"""rows\(\s*['"]([^'"]+)['"]\s*\)""")


def _expr_meters(expr: str) -> list[str]:
    """**その `count_expr` が開くファイル**（`data/` からの相対）。読めなければ空。

    `EXPR_NS` の名前と `rows('X')` の実引数からだけ引きます。
    **地の文は1文字も読みません**（`newest_point` の註）。
    """
    out: list[str] = []
    for name, files in _EXPR_METERS.items():
        if re.search(r"\b" + re.escape(name) + r"\s*\(", expr):
            out += [f for f in files if f not in out]
    for m in _ROWS_CALL.finditer(expr):
        f = "data/" + m.group(1).lstrip("/")
        if f not in out:
            out.append(f)
    return out


@dataclass
class Answer:
    """1つの `needs` に対する答え。"""

    #: 判定できる最早の日。`None` ＝ この道具では出せない（外の出来事・伸び率ゼロ）
    ready: date | None
    #: なぜその日か。**必ず数字を入れること**
    why: str
    #: 待っても来ない種類か（外の出来事）
    unreachable: bool = False
    #: **停止（`src/pause_guard`）のせいで埋まらないとき、あと何本 要るか。**
    #:
    #: `unreachable` だけだと「収益化の審査（こちらでは起こせない）」と区別が
    #: 付きません。**こちらは解除すれば動きます** —— 直し方が正反対なので、
    #: 別の欄で持ちます（`Verdict.unreachable` の docstring と同じ理由）。
    #: 立てたのは `_paused_supply()`。読むのは `paused_claims()`。
    paused_short: int | None = None
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
    # **今日の点と比べないこと**（2026-08-29 に直した。**この関数は自分と比べていました**）。
    #
    #   `record_estimates()` は **1鍵1日1行**を、印字する道で毎回 書きます。
    #   だから**その日の最初の回**が今日の行を積んだ瞬間、`pts[-1]` は
    #   **今日の行**になり、`days = 0` → `days < 1` で **`None`**。
    #   この註が名指ししている警告（「直近 N日 は1件も増えていません」）は、
    #   **その日の2回目以降、1度も出ません。**
    #
    #   実測 2026-08-29 02:5x（この関数が 08-27 夜に作られた、まさにその前提）::
    #
    #       控え  08-27 have=5 ／ 08-28 have=5 ／ 08-29 have=5   ← **3日 動いていない**
    #       印字  「要 6 ／ いま 5（5日で **1.00/日**）→ **あと 1日**」（警告なし）
    #       実物  失敗の実測は 08/27 **0/15**・08/28 **0/7**・08/29 **0/4**
    #             ＝ **26本 連続で失敗ゼロ**。1.00/日 は 08/24 と 08/26 の平均
    #
    #   この機械は毎日 15周 前後 走るので、**14/15 の回が警告なしの版**を読みます。
    #   `_rate_scatter` の註が同じ帳面について書いている
    #   「**控えは、この機械が何回 撃たれたかを数えるようになる**」の、読む側の形です。
    #
    #   **覆る条件**: `record_estimates()` が1日1行をやめて、
    #   `have` の変わった回だけ積むようになったら、この選り分けは要らなくなります
    #   （`tests/test_deadline_recent_rate_same_day.py` がそこを見ています）。
    prev = [p for p in pts if p[0] < as_of.isoformat()]
    if not prev:
        return None
    at0, have0 = prev[-1]
    try:
        days = (as_of - date.fromisoformat(at0)).days
    except ValueError:
        return None
    if days < 1:                       # 同じ日の点どうしは「率」になりません
        return None
    return (have - have0) / days, days, have - have0


def _stall_days(key: str, have: int, as_of: date,
                path: Path | None = None) -> int | None:
    """**その数が動いていない日数**（控えの点で数える。動いていれば `None`）。

    `_recent_rate()` が返すのは**いちばん新しい点との差**だけなので、
    3日 止まっていても「**直近 1日 は増えていません**」と出ます
    （実測 2026-08-29: 控えは 08-27／08-28／08-29 とも `have=5`、
    印字は「直近 1日」）。**1日 と 3日 では、読む側の扱いが変わります。**

    ここは**窓を選びません** —— 数えるのは「`have` が同じまま連なっている
    いちばん古い点まで」で、答えは1つです（`_recent_rate` の註が避けている
    「どの窓を読むか」は増えません）。

    **日付は動かしません。印字だけ**（`tests/test_accrual_stall.py` の覆る条件:
    日付に効かせてよくなるのは、2点 ではなく窓で解けるようになったとき）。
    """
    p = path or RATE_LOG
    if not key or not p.exists():
        return None
    by_day: dict[str, int] = {}
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
            by_day[str(r["at"])[:10]] = int(r["have"])
        except (KeyError, TypeError, ValueError):
            continue
    # **今日の行は入れません**（`_recent_rate` と同じ理由 —— 自分と比べない）
    days = sorted(d for d in by_day if d < as_of.isoformat())
    if not days:
        return None
    oldest = None
    for d in reversed(days):
        if by_day[d] != have:
            break
        oldest = d
    if oldest is None:
        return None
    try:
        return (as_of - date.fromisoformat(oldest)).days
    except ValueError:
        return None


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


#: **`count_expr` が「作った本」の台帳そのものを数えている印。**
#: `long_ids()` / `latest_views()` 越しに触るものは入りません —— あちらは
#: **既に予約に在る本に再生が積む**ので、停止中でも数は動きます。
_BUILD_LEDGER = "rows('batch_runs.jsonl')"


def _ledger_frozen(expr: str) -> bool:
    """**その `count_expr` は、停止中に1件も増えないか。**（`_ans_accrual` が読む）

    ## なぜ要るか（2026-08-30・最適化の回に実測して足した）

    すぐ隣の `_paused_supply()` は、同じ穴を **`_project_nth()` の側**（`group_key`）
    だけで塞ぎました。**`_ans_accrual` は素通りです。** こちらも
    「**いまの伸び率が続いたら**」で日を出しますが、`count_expr` が
    `data/batch_runs.jsonl` を数えているとき、その伸び率を作っているのは
    **本を作る速さ**で、`src/pause_guard` はそれを **0 にしています。**

    **実測（この関数を足した回・`slot_half`／腕 `density`）**::

        count_expr が数える 作った本   **7本**（`batch_runs.jsonl`）
        そのうち 既に公開済み          **0本**
        齢4日以上（`falsified_if` が要る「落ち着き」）  **0本**
        予約に入ったまま未公開         **7本**

        → `since` からの平均で「**2日で 3.50/日 → あと 8日**」
        → `--shrink` が **2026-11-10 → 2026-09-08（63日）** 縮めろと出す

    **その 3.50/日 は、停止が入る前の2日ぶんです。** 停止後は 0 なので、
    32本 には永久に届きません。それでも機械は日付を出し、
    `arm_speed.forward()` の θ に**閉じる見込みとして数えられます。**

    ## これは「入力の側に、同じ強さの門を置く」ほうの直しです

    `docs/JOURNAL.md` 2026-08-26 が `--shrink` について残した1行:

    > **判断を抜くと、入力の質がそのまま結果になります。**
    > 印字だけの頃は誰も従わなかったので、悪い入力は無害でした。
    > **従わせる仕組みを入れた瞬間、入力の誤りが「機械が実行した誤り」に変わります。**

    同じ回に `--fit` を主実行へ配線しています（`docs/trigger_main.md` §2.6）。
    **配線だけを入れると、速くなるのは間違いのほうです** —— だから同じ回に、
    その入力を止める門をここへ置きます。**片方だけ入れないこと。**

    ## 覆る条件

    - `AUTOMATION_PAUSED.md` が消えたら、`pause_guard.is_paused()` が False になり黙ります
    - **台帳が停止後にも伸びていたら黙ります**（＝ 実際には作れている、という実測が
      文書より強い）。**「止まっているはず」で判断しません**
    - 検査は `tests/test_paused_accrual.py`
    """
    if _BUILD_LEDGER not in expr.replace('"', "'"):
        return False
    from src import pause_guard                                # 遅く読む（`sys.path` の後）

    if not pause_guard.is_paused():
        return False
    stamp = _pause_started()
    if stamp is None:
        return False
    # **「止まっているはず」で判断しません。実際に伸びたかを数え直します。**
    #   停止の時刻で台帳を切って、**同じ式をもう一度 評価**し、
    #   数が動いていなければ「この式は停止で凍っている」と言えます。
    #
    #   **式の絞り込みを、こちらで真似しないこと**（2026-08-30 に踏んだ）。
    #   最初は「台帳のいちばん新しい行 < 停止時刻」で見ていましたが、
    #   停止の 52分 後に `long: True` の回が1件 積まれており（停止を merge して
    #   いない作業コピーから走った回）、**`slot_half` の式は `not r.get('long')`
    #   でそれを外す**ので、台帳全体で見ると「伸びている」に化けました。
    #   **式が何を数えているかは、式に聞くのがいちばん確かです。**
    try:
        now_n = int(eval(expr, dict(EXPR_NS)))                 # noqa: S307
    except Exception:                                          # noqa: BLE001
        return False
    real_rows = _rows

    def _truncated(name: str) -> list[dict]:
        got = real_rows(name)
        if name != "batch_runs.jsonl":
            return got
        return [r for r in got if str(r.get("at") or "") < stamp]

    ns = dict(EXPR_NS)
    ns["rows"] = _truncated
    try:
        before_n = int(eval(expr, ns))                         # noqa: S307
    except Exception:                                          # noqa: BLE001
        return False
    return now_n == before_n


@functools.lru_cache(maxsize=1)
def _pause_started() -> str | None:
    """**停止が入った時刻**（ISO・`data/batch_runs.jsonl` の `at` と比べられる形）。

    出どころは **git**（`AUTOMATION_PAUSED.md` を足した commit の author 時刻）です。

    **mtime を読まないこと** —— まっさらなコンテナでは clone した時刻になります。
    **見出しの日付だけでも足りません** —— 停止は 2026-08-30 08:54 JST に入っており、
    **同じ日の 08:40 と 08:51 に本を作っています。** 日付までしか無いと、
    その2件が「停止の後に作った」に化けます（実測してここへ落ちた）。

    **覆る条件**: git が読めない木では `None` を返し、`_ledger_frozen()` は
    **False**（＝ 何も言わない）に倒れます。**黙るほうへ倒すこと** ——
    ここが誤って True に倒れると、動いている前提まで「停止中は埋まりません」
    になり、`arm_speed` から消えます。
    """
    import subprocess

    try:
        out = subprocess.run(
            ["git", "log", "--diff-filter=A", "--format=%aI", "--", "AUTOMATION_PAUSED.md"],
            cwd=ROOT, capture_output=True, text=True, timeout=20, check=False).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    stamps = [x.strip() for x in out.splitlines() if x.strip()]
    return stamps[-1] if stamps else None


#: `data_file:` を書いた `accrual` を「古い」と呼ぶまでの時間（時）。
#: **24時間**。1周 1.5時間 のこの機械なら、毎周 取り直している計器は黙ります。
_STALE_AFTER_HOURS = 24.0

#: **`needs.data_file:` が実際に読まれる `kind`。**
#:
#: `answer()` の分岐で、この欄へ手が伸びるのは2本だけです ——
#: `accrual`（`_stale_todo`）と `after`（計器へ直接 訊く枝）。
#: `group_key` / `published_group` / `external` / `now` に書いても、
#: **1文字も読まれません**（`_data_file_coverage` の註）。
#:
#: **足すときは `answer()` に枝を足してから。** 先にここへ書くと、
#: 「申告済み」に数えられて、守りは1つも増えません。
_DATA_FILE_KINDS = ("accrual", "after")


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
    try:
        hours = float(need.get("stale_after_hours") or _STALE_AFTER_HOURS)
    except (TypeError, ValueError):
        hours = _STALE_AFTER_HOURS
    now = datetime.now(timezone.utc)

    src = str(need.get("data_file") or "").strip()
    derived = False
    if src:
        newest = newest_point(ROOT / src)
        if newest is not None and (now - newest).total_seconds() / 3600.0 < hours:
            return ""                               # **新しい。待つのが正しい**
    else:
        # **申告が無いときは、式そのものに訊く**（2026-08-31・`_EXPR_METERS`）。
        # **いちばん古い計器**を採ります —— 1つでも止まっていれば数は伸びません。
        # **読めない計器では鳴らしません**（申告した場合と違って、ここは
        # こちらが引き当てた相手なので、「無い」を「取り直せ」に化けさせない）。
        stale: list[tuple[datetime, str]] = []
        for f in _expr_meters(str(need.get("count_expr") or "")):
            pt = newest_point(ROOT / f)
            if pt is not None and (now - pt).total_seconds() / 3600.0 >= hours:
                stale.append((pt, f))
        if not stale:
            return ""
        newest, src = min(stale)
        derived = True

    seen = (f"取り直したのは **{newest.astimezone(JST):%m/%d %H:%M} JST**"
            f"（**{(now - newest).total_seconds() / 3600:.0f}時間 前**）"
            if newest else "**いつ取り直したか読めません**")
    how = str(need.get("refresh") or "").strip()
    if not how and derived:
        how = _METER_REFRESH.get(src, "")
    tail = _refresh_pool_note(dict(need, refresh=how) if how else need)
    mark = ("（`data_file:` の申告はありません。**`count_expr` が呼んでいる名前**"
            "から引きました ——`_EXPR_METERS`）" if derived else "")
    return ("**待ち方が違います。足りないのは日ではなく、計器のほうです** —— "
            f"この数が読んでいる `{src}` は {seen}{mark}。"
            "**取り直すまで、待っても増えません。**"
            + (f"  `{how}`" if how else f"  `{src}` を取り直すこと")
            + tail)


def _refresh_pool_note(need: dict) -> str:
    """取り直す手が、**いまこの回で撃てるか**。撃てるなら、そう言う。

    ## なぜ要るか（2026-08-28 14:5x・最適化の回。**この回が実際に拾った**）

    `_stale_note` は「取り直せ」とコマンド名だけを出していました。
    **そのコマンドがいま通るかは、一言も言っていません。** 一方 `_quota_gate`
    は、同じファイルの中で**どの道具が Data API の日枠を使うかを正確に
    知っています**（`upload_cap.DATA_API_TOOLS`）。
    **同じことを2か所が別々に持っていて、下流が上流を読んでいない形**です。

    実害は、日枠が死んでいる窓で出ます。同じ出力の中に

        08-28 の行  「**この窓ではもう尽きています**（403 を 364回）。
                     枠が戻るのは 08/28 16:00 JST」
        08-31 の行  「取り直すまで、待っても増えません。 `python -m src.rpm_mix --forms`」

    が並びます。**後者には枠の話が1文字もありません。** 直前に「尽きている」を
    読んだ回は、**後者も尽きていると読みます** —— そして待ちます。
    2026-08-28 の前の回がそう読んで、**この1件を丸ごと飛ばしました。**

    **`rpm_mix --forms` は Analytics だけを引きます**（同関数の註
    「**Data API は0単位です**」）。**Analytics と Reporting は別の枠**なので、
    日枠が 403 を 364回 返していても**そのまま通ります。** 実際にこの回が
    撃って通り、要件の判定日が **09-03 → 08-30** へ 3日 手前に来ました。

    ## 黙るとき

    **日枠が開いているあいだは、何も足しません。** そのときは
    どちらの枠の道具も撃てるので、区別に意味がないからです。
    **口を開くのは、日枠が閉じている窓だけ** —— つまり
    「読み違えようがある場面」だけに出ます。

    **覆る条件**: Analytics / Reporting 側にも日枠と同じ「窓の中で尽きる」
    観測が入ったら、ここは「撃てます」と言い切れなくなります。
    そのときは `upload_cap` に枠べつの `day_quota()` を持たせて、
    **枠の名前で引く**形にすること。`tests/test_deadline_refresh_pool.py`
    が、いまの2つの向き（Data API の道具 / そうでない道具）を留めています。
    """
    how = str(need.get("refresh") or "").strip()
    if not how:
        return ""
    kind = str(need.get("quota") or "").strip()
    if kind == "data_api":
        uses_day_quota = True
    elif kind == "none":
        uses_day_quota = False
    else:
        uses_day_quota = any(tool in how for tool in _DATA_API_REFRESH)
    try:
        from src import upload_cap
        q = upload_cap.day_quota()
    except Exception:                                          # noqa: BLE001
        return ""                       # **読めないときは黙る**（門を増やさない）
    if q.open:
        return ""                       # 区別に意味がない ＝ 何も足さない
    back = q.resets_at.astimezone(JST)
    if uses_day_quota:
        return (f"  ← **この窓では撃てません**（Data API の日枠。403 を {q.hits}回 観測）。"
                f" 撃つのは **{back:%m/%d %H:%M} JST 以降**")
    return ("  ← **いま撃てます。この回で撃つこと**"
            f" —— Data API の日枠は尽きています（403 を {q.hits}回）が、"
            "**この手はその枠を使いません**（Analytics / Reporting は別の枠）。"
            "**同じ出力の他の行の「尽きています」を、ここへ持ち込まないこと**")


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
    # **停止中は、作った本の台帳が1件も伸びません**（2026-08-30・最適化の回）。
    #   ここを通す前に見ること —— 下の `rate = have / elapsed` は
    #   **停止が入る前の平均**を未来へ延ばし、`--shrink` がそれに従って
    #   期限を数十日 手前へ動かします（実測: `slot_half` を 11-10 → 09-08）。
    #   **`_MIN_SPAN_DAYS` の門より先に見ること** —— あちらは「窓が短い」の話で、
    #   こちらは「**窓がいくら長くても、もう増えない**」の話です。
    if _ledger_frozen(expr):
        paused = _paused_supply(f"要 {want} ／ いま {have}", want - have)
        if paused is not None:
            return paused
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
            # **止まりの長さは、いちばん新しい点との差ではありません**（2026-08-29）。
            #   `_recent_rate` は2点しか見ないので、3日 止まっていても「1日」と出ます。
            stalled = _stall_days(key, have, as_of) or r_days
            note += (f"。**直近 {stalled}日 は1件も増えていません**"
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


def _paused_supply(body: str, short: int) -> "Answer | None":
    """**停止中は、群に本が1本も足されない。**（`Answer` を返したら、そちらで打ち切る）

    ## なぜ要るか（2026-08-30・最適化の回に実測して足した）

    すぐ下の `_project_nth()` は「**いまの作る速さが続いたら**」で日を出します
    （その docstring が自分でそう言っています ——「作る速さが落ちれば伸びます」）。
    **2026-08-30 から、作る速さは 0 です** —— `src/pause_guard` が生成も投稿も
    塞いでいて、`AUTOMATION_PAUSED.md` が在るあいだ **1本も増えません。**

    それでも `_project_nth()` は**停止前に作った本**から率を読み、そのまま
    未来へ延ばしていました。**実測 2026-08-30 15:3x（この関数を足した回）**::

        opening_motion（腕 per_video）  対照(動きなし) あと **2本**
                                       → 「**0.86本/日**」で 8本目 09/15 → 判定 **09-22**
        request_form  （腕 sub_rate）   終端のみ あと **32本** ／ 途中あり あと **47本**
                                       → 「10.00本/日」「6.25本/日」で 72本目 09/30・10/04
                                       → 判定 **10-11**

    **合わせて 81本**。どれも `src/pause_guard` が塞いでいるので、
    **停止が解けるまで 1本も作れません。** それでも機械は日付を出し、
    `arm_speed.forward()` の予定表 θ に**閉じる見込みとして数えられていました。**
    `request_form` は **`sub_rate` の唯一 走っている A/B** です
    （`sub_rate` は閉じた前提が 2件 ＝ `arm_speed.MIN_N` 未満）。

    ## 何を返すか

    `unreachable=True` の `Answer` です。**`warming`（待てば来る）ではありません** ——
    `_ans_accrual` の `zero_means_never` と同じ形で、
    **「こちらが解除しないかぎり来ない」**という宣言です。
    `unready_claims()` がこれを拾い、`ready_by_claim()` から落ちます。

    ## **これは「遅らせる」変更です**

    到達日は後ろに動きます。**それが実測です** —— `scripts/eta.py` 自身が
    「止まっている間の到達日は上振れです」と印字しているのと同じ向きで、
    ここはその上振れの**具体的な出どころ**を1つ塞ぎます。
    そして塞いだぶんが、**門（`AUTOMATION_PAUSED.md` の Resume gate）を
    1日 早く閉じることの値段**として出ます。

    ## 覆る条件

    - `AUTOMATION_PAUSED.md` が消えたら、この関数は自分で黙ります
    - **既に予約に在る本は数に入っています**（`floor.groups` は予約を含む）。
      塞いでいるのは「これから作る本」だけです
    - 検査は `tests/test_paused_supply.py`
    """
    from src import pause_guard                                # 遅く読む（`sys.path` の後）

    if not pause_guard.is_paused():
        return None
    return Answer(
        None,
        body + f" → **停止中は埋まりません**（あと **{short}本** 要りますが、"
        "`AUTOMATION_PAUSED.md` が在るあいだ `src/pause_guard` が生成と投稿を"
        "塞いでいるので **1本も増えません**。**待っても来ません** —— "
        "来るのは門を閉じて解除したときで、**解除が N日 遅れれば、"
        "この前提の判定も N日 遅れます**）",
        unreachable=True,
        paused_short=short,
    )


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
        # **停止中は、あと {count - len(pub)}本 が 1本も作れません**（`_paused_supply`）。
        paused = _paused_supply(head, count - len(pub))
        if paused is not None:
            return paused
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
    # **何で絞ったかを、床が満ちた側にも書くこと**（2026-08-28・最適化の回）。
    #
    # `form` は長らく**「まだ足りない」枝にしか**出ていませんでした。
    # 床が満ちた瞬間、`why` から絞り込みの字が消えます —— そして
    # **消えた側の日付は、絞らない場合と 38日 ちがいます**（実測 2026-08-28、
    # 期限 10-12 の endcard: 絞らない 09/01 ／ 絞る **10/09**）。
    #
    # 害は「読みにくい」では済みません。読んだ回は
    # 「08-24 以降に作った本の 72本目の公開 10/09」だけを見て、
    # **自分で数え直すと 09/01 に届いている**ので、期限を手前へ倒しにきます。
    # 倒すと、**対照が9割の群で判定して「効かなかった＝外れ」に化けます** ——
    # そしてこの前提の `next_if_false` は「登録率の腕を**動画の外**へ移す」なので、
    # **律速の門（登録者1,000人）を、誤った理由で手放す**ことになります。
    # （この関数の上の長い註が、まさにその事故を防ぐために絞り込みを足しています。
    #   **絞りはしたが、絞ったと言っていなかった。**）
    tail2 = ""
    if since_pub:
        tail2 += f"（{since_pub} 以降に公開する本だけ）"
    if endcard:
        tail2 += f"・**終端が {endcard} の本だけ**"
    return Answer(ready,
                  f"{after[:10]} 以降に作った本{tail2}の **{count}本目の公開 {nth:%m/%d}** "
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


#: **観測の時刻が入っている欄**（先に見る順）。
#:
#: ## なぜ `at` を先頭にしないか（2026-08-28 13:5x に実測して直した）
#:
#: `at` は、この repo では**2つの意味**で使われています ——
#: 「**観測した時刻**」（`data/views.jsonl` / `data/day_quota.jsonl`）と、
#: 「**予約した公開時刻**」（`data/uploaded.jsonl`）。後者は**未来**です。
#:
#: 実測 2026-08-28 13:4x JST:
#:
#:     data/uploaded.jsonl の `newest_point()`  **2026-10-12 09:00**（**1,075時間 先**）
#:
#: この計器は `config/hypotheses.yaml` に `data_file:` として**申告済み**の3件の
#: 1つです。読み手はどちらも「新しいほど良い」向きに使います ——
#:
#:     `_ans_after`   `newest < when_data` が **偽** → **門を素通り**
#:     `_stale_note`  `(now - newest) < hours` が **真** → 「新しい。待つのが正しい」
#:
#: **つまり、何週間 取り直さなくても、この計器だけは永久に「新しい」と答えます。**
#: `newest_point` の註が「時計だけの門は、同じ穴を時刻の粒で作り直しただけ」と
#: 書いている、その穴を**計器の側で作り直していました。**
#: 同じ行に `uploaded_at`（＝**実際に上げた時刻**）が在るので、そちらを先に見ます。
#:
#: `_report_end` は Reporting API の「**この時刻までのぶんが入っている**」で、
#: `data/reach.jsonl` はこれしか時刻を持ちません（`date` は `"20260815"` で
#: `fromisoformat` が読めない）。**そのせいで 226KB・数千行 の計器が
#: `None`（＝1点も読めません）**と出ていました —— 向きは安全側ですが、
#: **在るデータを「取り直せ」と言い続ける**ので、Reporting の単位が毎回 出ていきます。
_POINT_KEYS = ("uploaded_at", "_report_end", "at", "ts", "time")


def _point_at(rec: dict) -> datetime | None:
    """1件の記録の**観測時刻**。読めなければ `None`。

    **未来の時刻は観測ではありません**（＝予約・期限）。落とします ——
    残すと、上の2つの読み手が**どちらも「いちばん新しい」側に外れます。**
    落とした結果 `None` になるなら、それが正しい答えです
    （「この計器は観測を1点も持っていない」）。
    """
    now = datetime.now(timezone.utc)
    for key in _POINT_KEYS:
        at = rec.get(key)
        if not isinstance(at, str):
            continue
        try:
            dt = datetime.fromisoformat(at.replace("Z", "+00:00"))
        except ValueError:
            continue
        if dt.tzinfo is None:
            # **日付だけの `at` は、その日の終わりではなく始まりで読む。**
            # 「08-26 に取った」を 08-26 00:00 と読めば、古さは長めに出ます。
            # **短く見積もって「まだ新しい」と言うほうが危険**です。
            dt = dt.replace(tzinfo=timezone.utc)
        if dt > now:
            continue                     # 予約・期限。**観測ではない**
        return dt
    return None


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
        dt = _point_at(whole)
        if dt is not None:
            return dt
    for ln in path.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except Exception:                                        # noqa: BLE001
            continue
        dt = _point_at(r)
        if dt is None:
            continue
        if newest is None or dt > newest:
            newest = dt
    return newest


def _after_tail(need: dict, on: date, what: str, lag: int) -> Answer:
    """`after` の要件の**答えそのもの**（`plus_lag` を足すかどうかだけ）。

    `_ans_after` の末尾から切り出しました（2026-08-28）。理由は
    **`data_file:` の枝から、同じ答えへ早く帰りたいから**です ——
    その時刻がまだ来ていない要件に、計器の古さを訊いても意味がありません。
    """
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
            # **日を捨てないこと**（2026-08-28 23:3x・最適化の回）。
            #
            # ここは長らく `Answer(None, ...)` を返していました。**時刻を足した
            # せいで、日付が消えます** —— `ready_by_claim()` は `ready is None`
            # の claim を落とすので、`unready_claims()` へ回り、
            # `arm_speed.forward()`（予定表の θ）と `next_when()` の**両方から
            # 見えなくなります。**
            #
            # 実測 2026-08-28 23:1x: `unready` 3件 のうち1件がこれ ——
            # **「1日に再生が付く本の集合は、左端つきの帯で決まる」**
            # （`day_cap.window()` の (A)/(B)。同じ回の `queue_lag.py` が
            # **27倍 ちがう**と印字している、いちばん高い前提）。
            # **台帳でいちばん正確に日の分かっている要件**（時計。伸び率の
            # 推定ですらない）が、**唯一「日が出せない」側に居ました。**
            #
            # そして `warming` に落ちるので、印字は
            # **「今日の 04:00 JST に出ます。その時刻まで待つこと」** ——
            # 実際は **09/03** で、**6日 ずれています。**
            # すぐ上の行が正しく「**09/03 04:00 JST**」と出しているので、
            # **同じ枠の2行が食い違い、結論を言う側（→ の行）が誤り**でした。
            #
            # 日は分かっています。**`ready=on` を返し、その日のうちの時刻は
            # `ready_at` に載せます** —— `drift.split_overdue()` が
            # 「`ready == today` かつ `ready_at` がまだ来ていない」を
            # **既に見ている**ので（2026-08-28 に足った枝）、早撃ちは
            # そちらで止まります。**日を捨てて止める必要はありません。**
            #
            # **覆る条件**: `split_overdue()` が `ready_at` を見なくなったら、
            # ここは早撃ちの唯一の門に戻ります —— そのときは
            # `tests/test_after_time_keeps_date.py` が落ちて、そう教えます。
            if now.date() == on:
                far = ("**まだ出ていません** ——"
                       "日は来ていますが、この要件は日の粒ではありません")
            else:
                left = (on - now.date()).days
                far = f"**その日はまだ来ていません**（あと {left}日）"
            return Answer(
                on,
                f"{what} は **{on:%m/%d} {when:%H:%M} JST** に出ます"
                f"（いま {now:%m/%d %H:%M} JST。{far}）",
                ready_at=when)
    # **時計が来た ＝ データが在る、ではありません**（2026-08-27・`newest_point` の註）。
    # `data_file:` が書いてあるときは、その計器に直接 訊きます。
    src = need.get("data_file")
    if src:
        # **「いつ訊いてよいか」と「どの点が要るか」は、別の日です**
        # （2026-08-29 05:2x・最適化の回。**同じ回のうちに1度 取り違えました**）。
        #
        # ここは長らく、両方を `on_date` の 00:00 でやっていました。
        # **この要件が「判定できる」と言う日は `on_date + lag`** です
        # （すぐ下の `_after_tail`）——**門と、門が守っている日が `lag` 日
        # ずれていました。**
        #
        # `plus_lag: true` は「**その日ぶんの点は、`lag` 日 あとに届く**」の意味
        # なので、`on_date` に計器へ訊けば、**要件自身の定義により、まだ在りません。**
        # `newest` が古ければ `ready=None` を返し、その claim は
        # 「判定できる日が出せません」の棚（＝収益化の審査待ちと同じ棚）へ落ち、
        # `arm_speed.forward()` と `next_when()` の**両方から消えます**
        # （3b18766 が時刻の粒で踏んだのと同じ穴）。しかも `refresh:` を撃つ回は、
        # **在りようのないデータのために Reporting／Data API の単位を捨てます。**
        #
        # ff1a8c1 は「**未来の** `on_date` には訊かない」を入れました。
        # **足りません** ——`on_date` が過ぎていても、`on_date + lag` が
        # 来ていなければ同じ話です。
        #
        # ## **要る点のほうは、動かしてはいけません**
        #
        # この回の最初の版は `when_data` を1つのまま `lag` 日 ずらしました。
        # **訊く時刻と、要る点の日付が、同時に動きます。** それは
        # `_report_end` を持つ計器で必ず外れます ——
        #
        #     `data/reach.jsonl` は `_POINT_KEYS` の `_report_end`（＝**データの日**）
        #     を返します。Reporting は3日 遅れなので、09/12 に読める
        #     いちばん新しい `_report_end` は **09/09 前後**。
        #     「09/12 以降の点」を要求すれば、**取り直しても永久に通りません。**
        #
        # 要件が名指ししているのは `on_date` の**データ**で、`lag` はそれが
        # **届くまでの時間**です。だから:
        #
        #     訊いてよい時刻  `on_date`（＋時刻）**＋ lag**   ← 遅れを足す
        #     要る点          `on_date`（＋時刻）             ← **足さない**
        #
        # **覆る条件**: `newest_point` が `_report_end` を見なくなり、
        # どの計器も「取り直した時刻」を返すようになったら、要る点の側にも
        # `lag` を足してよくなります。`tests/test_deadline_data_file.py` の
        # `test_遅れの後に訊くが_要る点は_on_date_のまま` が、そこを見ています。
        want = when if at else datetime(on.year, on.month, on.day, tzinfo=JST)
        ask_at = want + timedelta(days=lag) if need.get("plus_lag") else want
        when_data = want
        # **その時刻がまだ来ていないなら、計器には訊かないこと**（2026-08-28 14:2x）。
        #
        # この枝は `data_file:` が在れば**日付に関係なく**回っていました。
        # いま `data_file:` を持つ `after` の要件は1件だけで、その `on_date` は
        # 過ぎているので、**今日までは一度も踏んでいません。**
        # ところが同じ日の回が、`data_file:` を足す候補を **6件** 数えており
        # （散文が計器を1つだけ名指ししている要件）、**うち5件の `on_date` は
        # 未来**です（09/05・09/10・09/11・09/11・09/12）。足した瞬間、
        # 5件ともこう答えます ——
        #
        #     「**時計は来ています。足りないのはデータのほうです** ——
        #       取り直すまで、待っても永久に出ません」
        #
        # **2つとも偽です。** 時計は来ていない（09/07 の点を 08/28 に訊いている）し、
        # **待てば出ます**（Reporting が毎日 足していく）。しかも `ready=None` を
        # 返すので、要件は「判定できる日が出せません」の側 ——
        # **収益化の審査待ちと同じ棚**に落ちます。
        # そして `refresh:` を撃つ回は、**在りようのないデータのために
        # Reporting の単位を毎回 捨てます。**
        #
        # 上の `at_time_jst` の枝が `now < when` で先に帰るのと同じ理屈です。
        # **古さを問えるのは、その時刻が来てからだけ。**
        #
        # **覆る条件**: 「その日より前に、その日ぶんの点が在るべき」計器が
        # 出てきたら（先取りで書く帳面）、この門はその計器を素通りさせます。
        # そのときは `need` 側に印を足すこと（この行の判定を全部の要件に
        # 広げないこと）。`tests/test_deadline_data_file.py` の
        # `test_a_future_on_date_does_not_ask_the_instrument` が見ています。
        if ask_at > datetime.now(JST):
            return _after_tail(need, on, what, lag)
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
    return _after_tail(need, on, what, lag)


_QUEUE_GAIN: dict | None = None


def queue_gain() -> dict:
    """**その判定日は、予約の並び替えだけで手前に倒せないか。**（API 0単位・1回だけ解く）

    ## なぜ要るか（2026-08-29 に実測で見つけた。**2か所が別々に同じ日を言っていた**）

    この道具は `opening_motion` にこう出していました:

        [OK] 10-08  冒頭0.9秒に…
             対照(動きなし) 予約10本/**8本目 09/30** ＋ 落ち着く 4日 ＋ 遅れ 3日
             → 判定できるのは **10-07**。**期限 10-08 はその帯の中** ——
               **書き換えないこと**

    **正しいのですが、「予約の並びは動かせない」を暗に置いています。**
    同じ日に `scripts/queue_lag.py` はこう出していました:

        opening_motion  期限 10/08  判定 10/07 → **09/07** → **30日 早まる**

    対照は**ちょうど10本**しかなく、`min_per_group` は 8 —— **8本目 ＝
    後ろから3本目**です。だから後ろの6本を手前の空き枠へ入れ替えるだけで、
    8本目は 09/30 から 08/31 へ来ます（**新しい本は1本も要りません**）。

    **`[OK]` と「書き換えないこと」を読んだ回は、そこで手を止めます。**
    片方は「この日まで待つしかない」と読め、もう片方は「30日 手前に倒せる」と
    言っている —— **同じことを2か所が別々に言っていて、片方しか読まれていない。**

    ## 何を出すか

    **倒せる日数だけ**。手も、撃つかどうかも `queue_lag` の側にあります
    （枠の門・判定を壊さないかの門・約束の門が、あちらに3つ並んでいます）。
    **ここでは「待ちは自分で作っている」ことだけを言います。**

    **覆る条件**: `queue_lag` の入れ替えが実物に着かないままなら、この行は
    「倒せる」と言い続けます。**着いたかどうかは、あちらの `promise_lines` が
    帳面（`data/queue_lag.jsonl` の `after`）から言います** —— この行を
    根拠に期限を書き換えないこと。**倒してから書き換えること。**
    """
    global _QUEUE_GAIN
    if _QUEUE_GAIN is not None:
        return _QUEUE_GAIN
    _QUEUE_GAIN = {}
    # **`queue_lag` から読み込まれた写しでは、解きません**（実測 8.0秒 の丸損）。
    #   `queue_lag._ready_by_claim()` は、このファイルを `qlag_deadline_check`
    #   という別名で読み直し、**`ready_by_claim()` の日付だけ**を使います
    #   （`why` は捨てられる）。そこでこの関数を解くと、
    #   **`queue_lag` 自身が既に出している数を、誰も読まない所でもう一度**
    #   組み直すことになります —— しかも `Plan()+improve()` は 8.0秒。
    #   `queue_lag` は `status.py` と `batch_build` から毎周 呼ばれます。
    #
    #   **覆る条件**: `_ready_by_claim()` が `why` も使うようになったら、
    #   この門は外すこと（そのときは、あちらが読む側になります）。
    if __name__ == "qlag_deadline_check":
        return _QUEUE_GAIN
    try:
        from scripts import queue_lag as QL                    # 遅く読む
        plan = QL.Plan()
        before = dict(plan.before)
        plan.improve()
        after = plan.readies()
        for k, b in before.items():
            a = after.get(k)
            if b and a and a < b:
                _QUEUE_GAIN[k] = (b, a, (b - a).days)
    except Exception:                                          # noqa: BLE001
        # **落ちても、この道具そのものは止めません。**
        # 並び替えの話は「もっと早くできる」であって、期限の正しさではない。
        _QUEUE_GAIN = {}
    return _QUEUE_GAIN


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
        # **停止中は、床に足りない群がこれ以上 埋まりません**（`_paused_supply`）。
        # `since` の有無より先に見ること —— 停止中は「`since` を足せば推定できます」も
        # 嘘になります（推定の入力である「作る速さ」が 0 だからです）。
        short_all = sum(n - len(floor.groups[g]) for g in floor.groups
                        if floor.nth[g] is None)
        paused = _paused_supply(body, short_all)
        if paused is not None:
            return paused
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
    body = body + f" ＋ 落ち着く {SJ.SETTLE_DAYS}日 ＋ 遅れ {SJ.ANALYTICS_LAG_DAYS}日{tail}"
    # **この日は、予約の並びで決まっています**（`queue_gain()` の docstring）。
    # 並び替えだけで手前に来るなら、そう言うこと —— 言わないと、`[OK]` と
    # 「帯の中。書き換えないこと」を読んだ回が、**自分で作った待ちの前で止まります。**
    gain = queue_gain().get(key)
    if gain:
        _b, _a, _d = gain
        body += (f"　[!] **この日は予約の並びで決まっています** —— "
                 f"`python scripts/queue_lag.py --plan` は、**新しい本を1本も"
                 f"作らずに {_b:%m/%d} → {_a:%m/%d}（{_d}日 手前）**へ倒せると"
                 f"言っています（もう予約に在る本の入れ替えだけ）。"
                 f"**上の『帯の中。書き換えないこと』は期限の話で、"
                 f"『この日まで待つしかない』ではありません。**"
                 f" 撃つ・撃たないの門は3つとも `queue_lag` 側にあります"
                 f"（枠／判定を壊さないか／**前の約束は守られたか**）")
    return Answer(ready, body, slack=band, slack_down=0)


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
    def paused_short(self) -> int | None:
        """**停止のせいで埋まらない本数**（`Answer.paused_short` の合計）。`None` ＝ 停止は効いていない。"""
        ns = [a.paused_short for a in self.answers if a.paused_short is not None]
        return sum(ns) if ns else None

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

        実測（2026-08-25・開いている16件）: **10件・合計 46日・平均 4.6日**、
        いちばん大きいもので **14日**。

        ## **【2026-08-30 に、この欄の意味を測り直しました】**

        ここには長らく「**この日数は到達日がまるごと止まっている日数そのもの**」と
        書いてありました。**それは、書いた日（2026-08-25 22:5x）には本当で、
        その翌日に本当でなくなりました。**

        2026-08-26 20:4x に `ready` が `src/arm_speed.py` へ配線され、
        いまは **`deadline` より `ready` が優先**されます
        （`arm_speed.next_close()` の `r = ready.get(...); if r: when, src = r, "ready"`、
        `forward()` / `forward_by_arm()` は `ready` だけを読む）。
        `scripts/drift.py` の `split_overdue()` / `_closable` も同じく `ready` 側です。

        **実測 2026-08-30**: `opening_motion` の `deadline` を 10-07 → 09-22 へ
        15日 縮めて、`python scripts/eta.py --alloc` を撃ち直した ——

            腕べつの回転   per_video 0.233/日   （**変化なし**）
            台帳の配分     2027-01-21           （**変化なし**）
            過去との差     +11日                （**変化なし**）

        **`deadline` を動かしても、印字される到達日は1日も動きません。**

        ## では、この日数は何の日数か

        **`deadline` だけを読んでいる所が、1つ残っています** ——
        `drift.overdue()`（`dl = h["deadline"]; if dl <= today`）。
        これは `scripts/stop_check.sh` (1.7) の「期限の来た問いの置き去り」門の入力で、
        **「この回は verdict を出せ」と回に言う唯一の仕掛け**です。

        つまり `waits` は:

            **データはもう揃っているのに、どの門もまだ「閉じろ」と言わない日数**

        軌跡の腕は前提を1件閉じたときだけ動くので、これは
        **閉じるのが遅れる日数の上限**です。**「到達日が止まっている」とは違います**
        —— 閉じた時点で日付は動くので、失うのは日付ではなく**その日数ぶんの前倒し**。
        それでも縮める価値はありますが、**15日 縮めても `eta.py` の印字は動きません。**
        動いたかどうかを `eta.py` で確かめようとして「効かなかった」と結論しないこと。

        **覆る条件**: `drift.overdue()` が `ready` を読むようになったら、
        `deadline` はどの門の入力でもなくなります。そのときこの欄は
        **ただの記録**になるので、門（`--gate`）ごと畳んでよい。
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
            # **時刻だけを持ち上げないこと**（2026-08-28 23:3x）。
            #
            # ここは `at_time_jst`（"04:00"）だけを拾い、**`on_date` を
            # 見ずに「今日の」と書いていました。** 実測 08/28 23:16 JST、
            # `on_date: 2026-09-03` の要件が「**今日の 04:00 JST に出ます**」
            # ——**6日 ずれ**。すぐ上の `why` の行は「**09/03 04:00 JST**」と
            # 正しく出しており、**結論を言う側だけが誤り**でした。
            # （`_ans_after` を直したので、この枝は
            #  「同じ前提の**別の** need が warming」のときにしか通りません。
            #  そのときこそ日を間違えると読めないので、日ごと出します。）
            nd = next((x for x in (v.needs or []) if x.get("at_time_jst")), None)
            when = str(nd.get("at_time_jst")) if nd else ""
            on_s = str(nd.get("on_date") or "") if nd else ""
            if todo:
                out.append(f"         → {todo}")
            elif when:
                try:
                    on_d = date.fromisoformat(on_s)
                except ValueError:
                    on_d = None
                today_ = datetime.now(JST).date()
                if on_d is None:
                    head = f"**{on_s or '（日付なし）'} {when} JST に出ます。**"
                elif on_d == today_:
                    head = f"**今日（{on_d:%m/%d}）の {when} JST に出ます。**"
                else:
                    head = (f"**{on_d:%m/%d} {when} JST に出ます**"
                            f"（あと {(on_d - today_).days}日。**今日ではありません**）。")
                out.append(f"         → {head}"
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
    # **自分で並べた待ちは、まとめの側にも出すこと**（2026-08-29）。
    #   群の行にだけ書いた版は、**まとめしか読まない回には届きません** ——
    #   `CLAUDE.md` が「読むのは3行だけ」と言っているのと同じ形で、
    #   `eta.py` の `[!]` 18件 が「頭と尾だけ読む手順では1本も読まれない」と
    #   自分で印字しているのと同じ穴です。
    gains = queue_gain()
    if gains:
        tot = sum(g[2] for g in gains.values())
        top = max(gains.items(), key=lambda kv: kv[1][2])
        out.append(f"  **予約の並び替えだけで倒せる待ち: {len(gains)}件・合計 {tot}日**"
                   f"（最大 {top[0]} の **{top[1][2]}日**: "
                   f"{top[1][0]:%m/%d} → {top[1][1]:%m/%d}）。"
                   "**新しい本は1本も要りません** —— もう予約に在る本の入れ替えだけ。"
                   "`python scripts/queue_lag.py --plan`（API 0単位）が手を出し、"
                   "門を3つ（枠／判定を壊さないか／**前の約束は守られたか**）並べます")
        out.append("    **これは「期限が遅すぎる」とは別の話です** —— あちらは"
                   "データが揃っているのに期限が先の件。**こちらはデータがまだ無く、"
                   "その『まだ無い』をこちらの予約の並びが作っています。**")
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
    out.extend(_data_file_coverage(vs))
    return out


def _data_file_coverage(vs: list[Verdict]) -> list[str]:
    """**「時計だけで判定できると言っている」要件が、いま何件あるか。**

    ## なぜ要るか（2026-08-28 の2周目に測った）

    `needs.data_file:` は「時計は来ています。足りないのはデータのほうです」を
    言うための欄で、08/27 の2つの回が `on_date` と `accrual` の両方に足しました。
    **門としては正しい。** ただし `_stale_todo` も `_on_date_todo` も
    「**書いていない要件は、今までどおり時計だけで通します**」と書いてあり、
    **申告は任意**です。実測 2026-08-28（`config/hypotheses.yaml`）:

        前提                            **39件**
        `data_file:` を申告している     ** 3件**（**8%**）
        `needs:` はあるが申告なし       **21件**
        `needs:` そのものが無い         **15件**

    **つまり守りの当たる範囲は 8% です。** 残り 36件 は、08/27 の回が
    「偽の判定日」と呼んだものを、いまも出しえます。

    ## ~~ここは埋めません。**数を出すだけ**にします~~

    ~~どの計器を読むかは要件ごとに違い、機械には決められません
    （`count_expr` の中身は読めない ——`_stale_todo` の註）。
    **推測で `data_file:` を書くと、こんどは「在ることになっている点」で
    判定します。** それは黙って通すより悪い。~~

    **半分 取り消します**（2026-08-31・最適化の回）。「推測で書くのは悪い」は
    正しいままですが、その前の「**機械には決められません**」が外れています ——
    `count_expr` が動くのは `EXPR_NS` の中だけで、**名前は閉じた集合**、
    どれがどのファイルを開くかは**このファイル自身**に書いてあります。
    だから `_EXPR_METERS` から引きます（**推測ではなく、式そのものを読む**）。
    申告があればそちらが勝つので、人が決めた待ち方は上書きされません。

    **埋めないでいた 4日 の実費**（実測 2026-08-31 05:2x）:

        `data/views.jsonl` のいちばん新しい点  **08-29 17:31 JST**（**45時間 前**）
        08/30・08/31 に積まれた行              **0行**
        その計器を数えている開いた前提          **3件**（申告 0件 ＝ 全部 素通り）
        素通りしていた要件に出ていた文          「あと 3日」「あと 30日」
        引くようにして鳴った件数                **2件 → 7件**

    そして `eta.py` の頭は、同じ日に「**この回に閉じられる前提はありません**」。
    到達日をいちばん大きく動かすのは θ（前提が閉じる速さ）です。

    だから残りは `eta.py` の (イ) と同じ形にします ——
    **裸で「判定できます」と言うたびに、何を確かめていないかを並べる。**

    **覆る条件**: 申告が 39件 に届いたら、この行は毎回 0 を出すので外してよい。
    逆に**申告した件でだけ「取り直せ」が出続ける**なら、
    見るべきは申告の数ではなく `count_expr` のほうです。

    ## 分母に、この欄が**届かない**要件が入っていました（2026-08-29 05:0x）

    上の「覆る条件」は**満たせません。** `data_file:` を読む道は
    `answer()` の分岐に2本しかなく（`kind: accrual` → `_stale_todo` ／
    `kind: after` → 計器へ直接 訊く枝）、**残りの kind では1文字も読まれません** ——
    `group_key` は `src/judgeable.py` に委ねる（`_ans_group_key`）、
    `published_group` は予約の実物を数える、`external` はこちらの手で
    起こせないもの。**そこに書いても、何も起きません。**

    実測 2026-08-29（開いている 27件・needs 28件）:

        `accrual` ＋ `after`（この欄が効く）   **19件**  うち申告 **5件**
        `group_key` / `published_group` / `external`（効かない）  **9件**

    印字は **23/28** でした。**実際の穴は 14/19 です。**
    差の 9件 は「申告していない」のではなく、**申告する場所が無い**もの。
    分母に入れると、(1) 穴が 1.6倍 に見え、(2) 覆る条件（分母＝申告数）が
    **永久に成り立たず**、(3) 「その1件だけ足すのが安い」に従った回が、
    **足しても何も変わらない要件**を引き当てます。

    **「その数は、鎖のどの段で採られたか」の続きです** ——
    数（申告 5件）は正しく、支えている文（「28件が確かめられていない」）だけが
    別の母集団の話でした。

    **覆る条件（差し替え）**: `data_file:` を読む `kind` が増えたら、
    ここの `_DATA_FILE_KINDS` に足すこと。`tests/test_deadline_data_file.py` の
    `test_この欄が届かない_kind_を分母に入れないこと` が、
    `answer()` の分岐と食い違ったら落ちます。
    """
    total = declared = derived = 0
    for v in vs:
        for need in (v.needs or []):
            if not isinstance(need, dict):
                continue
            if str(need.get("kind") or "").strip() not in _DATA_FILE_KINDS:
                continue
            total += 1
            if str(need.get("data_file") or "").strip():
                declared += 1
            elif _expr_meters(str(need.get("count_expr") or "")):
                derived += 1
    covered = declared + derived
    if not total or covered >= total:
        return []
    return ["",
            f"  **時計だけで「判定できる」と言っている要件: "
            f"{total - covered}/{total}件**"
            f"（`needs.data_file:` の申告 {declared}件 ＋ "
            f"`count_expr` から引けた {derived}件（`_EXPR_METERS`）。"
            f"分母は **`data_file:` が効く kind だけ**"
            f"（{'/'.join(sorted(_DATA_FILE_KINDS))}）—— "
            "ほかの kind に書いても読まれません）。"
            " 申告した件と引けた件だけ、その計器の点が古ければ"
            "「取り直す手」が上に出ます ——"
            " **残りは、点が1つも無くても期限だけで通ります**"
            "（08/27 に取り下げた『偽の判定日』と同じ形）。",
            "    **推測で埋めないこと。** どの計器かは要件ごとに違い、"
            "外すと『在ることになっている点』で判定します。"
            " 閉じられなかった要件が出るたびに、**その1件だけ**"
            "`data_file:` を足すのが安いやり方です。"]


def ready_by_claim(items: list[dict] | None = None, as_of: date | None = None,
                   lag: int | None = None) -> dict[str, date]:
    """**claim → 判定できる最早の日。**（`src/arm_speed.next_close` が読みます）

    `deadline` は置いた回の勘、`ready` は**データが実際に揃う日**です。
    2つを別々の場所が持っていて、**到達日を印字する側は `deadline` しか
    読んでいませんでした**（2026-08-25 22:5x に繋いだ）。
    """
    vs = check(items if items is not None else load(), as_of=as_of, lag=lag)
    return {v.claim: v.ready for v in vs if v.ready is not None}


def paused_claims(items: list[dict] | None = None, as_of: date | None = None,
                  lag: int | None = None) -> dict[str, int]:
    """**停止のせいで判定日が出せない claim → あと何本 要るか。**（`scripts/eta.py` の頭が読みます）

    `unready_claims()` は「日が出せない」を全部まとめて返しますが、
    **直し方は3つに割れます**（`Verdict.unreachable` の docstring と同じ話）:

        warming        今日 立てたばかり           …… **何もしないのが正解**
        unreachable    収益化の審査（あと 999人）  …… **こちらでは起こせない**
        **paused**     群があと N本 足りない       …… **門を閉じて解除すれば動く**

    3つ目だけが、**この回の作業で動かせます。** だから別に数えます ——
    ここに出る本数は、`AUTOMATION_PAUSED.md` の Resume gate を
    1日 早く閉じることの**値段**そのものです（解除が N日 遅れれば、
    ここに出た前提の判定も N日 遅れます）。

    **覆る条件**: `AUTOMATION_PAUSED.md` が消えれば、これは空で返ります。
    """
    vs = check(items if items is not None else load(), as_of=as_of, lag=lag)
    return {v.claim: v.paused_short for v in vs if v.paused_short is not None}


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


def _print_starved_floors() -> None:
    """**題材の接頭辞で決まる床に、あと何本 足りないか**を一覧で出す（API 0単位）。

    ## なぜここか（2026-08-29 12:0x の申し送りの3番。原文）

    > 開いた前提の「床にあと何本 足りないか」を、一覧で出す道具が要ります。
    > いまは `status.py` の `pick()` が**副産物として1件だけ**出すので、
    > **在庫の節を読んだ回しか気づけません。** この回の `s-ribo-` は
    > 公開 0本 / 床 8本 で、気づかなければ 09-19 に「外れ」と出ていました。
    > **`deadline_check.py` の隣（同じ `needs` を読む）が置き場所として近い。**

    **物は既に在りました** —— `src/floor_topics.lines()` は最初から全行を返し、
    その docstring も「**`batch_build` と `deadline_check` が同じ字を出すため**」と
    書いています。ところが `deadline_check` 側からは**一度も呼ばれておらず**、
    `batch_build` は `lines([r])[0]`（**1件だけ**）で呼んでいました。
    **足りなかったのは道具ではなく、呼び口です。**

    ## なぜ `check()` の中に入れないか

    上の一覧は**期限の妥当性**（データが期限までに揃うか）を見ています。
    こちらは「**その本を誰かが作るか**」で、`falsified_if` の外の話です ——
    混ぜると `--shrink` / `--extend` が、作られていない床を理由に期限を動かします。
    **印字だけ隣に並べて、書き戻しには一切 触れません。**

    ## 覆る条件

    `pick()` が床を全件ぶん先頭へ寄せるようになったら（いまは1件だけ）、
    この印字は「まだ埋まっていない床の確認」に縮みます。
    """
    try:
        from src import floor_topics                            # noqa: PLC0415
        rows = floor_topics.starved()
    except Exception as exc:                                    # noqa: BLE001
        print(f"\n  **題材の床が読めませんでした**: {str(exc)[:120]}")
        return
    print("\n=== 題材の接頭辞で決まる床（**作る側が動かないかぎり埋まりません**）===")
    if not rows:
        print("  **足りない床はありません。**"
              " 開いている前提のうち、題材の接頭辞で数えているものは全部 足りています")
        return
    for line in floor_topics.lines(rows):
        print(f"  {line}")
    print("  **上の一覧（期限）とは別の話です** —— あちらは「期限までにデータが揃うか」、"
          "ここは「**その本を誰かが作るか**」。"
          " 埋める手は `python scripts/batch_build.py --topics <id1>,<id2>,…`"
          "（**`--count` では届きません** —— 床の題は定義上ぜんぶ同じ族なので、"
          "既定の `--per-calc 2` が2本で切ります。`docs/trigger_main.md` §4 の 5）。")


def gate(vs: list["Verdict"]) -> int:
    """**期限が実データとずれていたら 2 で落ちる。**（2026-08-30・最適化の回）

    ## なぜ「印字」でも「検査」でもなく、門なのか

    この症状は、この repo で**3つの置き方を順に試して、3つとも素通りしました。**

        (1) この道具の印字             `deadline_check.py` の末尾に出る
        (2) `status.py` の印字         `test_status_も_遅すぎる側を出すこと` が守っている
        (3) `tests/test_deadline_check.py::test_遅すぎる期限が残っていないこと`

    **(3) は 2026-08-30 の実測で、赤いまま 358回 の ship を通過していました。**
    理由は `scripts/fast_tests.py` の作りです —— あれは **その回の `git diff` の
    basename から `-k` を組む**ので、`deadline_check` を触らない回はこの検査を
    1件も走らせません。そして全体の `pytest` は 16分 かかるので、どの回も撃ちません。

    **ここが、この repo でいちばん見落としやすい形です**:
    diff から検査を選ぶ仕掛けは、**コードが変わって赤くなる検査**しか拾えません。
    この検査が赤くなるのは**世界のほうが動いたとき**（予約が公開され、データが
    揃い、`ready` が手前へ来る）で、**diff は空です。** 構造上、永久に選ばれません。

    ## 止める価値（実測 2026-08-30）

        opening_motion（冒頭0.9秒の動き）  判定できるのは 09-22 ／ 期限 10-07 → **15日**

    **その 15日 が何の日数かは、同じ回に測り直しました**（`Verdict.waits` の註）。
    `deadline` を 10-07 → 09-22 へ縮めて `eta.py --alloc` を撃ち直すと、
    **腕べつの回転も台帳の配分も1つも動きません** —— `arm_speed` も
    `drift.split_overdue()` も、いまは `ready` のほうを読むからです。

    **`deadline` だけを読んでいる所は1つ残っています**: `drift.overdue()`。
    それが `stop_check.sh` (1.7) の「期限の来た問いの置き去り」門の入力で、
    **「この回は verdict を出せ」と回に言う唯一の仕掛け**です。
    だから 15日 は「到達日が止まった日数」ではなく、
    **データが揃っているのに、どの門も閉じろと言わない日数**
    ＝ **閉じるのが遅れる日数**。軌跡の腕は閉じたときだけ動くので、遅れはそのまま前倒しの損です。

    同じ 6日間の実測: ship **358件**・verdict **6件**・到達予測 2026-12-21 → 2027-01-10
    （**+20日 遠のいた**）。**閉じる回が 1.7% しかない輪で、閉じる合図を 15日 遅らせていました。**

    ## 直し方は1手（だから門にしてよい）

        python scripts/deadline_check.py --fit     # 両方の向きを寄せる
        python scripts/deadline_check.py --shrink  # 遅すぎる側だけ
        python scripts/deadline_check.py --extend  # 早すぎる側だけ

    **`falsified_if` は触りません。** 動くのは `deadline:` の1行だけです。
    「もっと n が要る」なら、動かすのは `needs.count` のほう。

    ## 覆る条件

    - **`--fit` を撃った直後にまた赤い**なら、効いていないのは門ではなく
      `Verdict.slack`（帯）の幅です。**帯を広げること。門を消さないこと。**
    - 「期限を意図して先に置きたい」回が出てきたら、そのときは `needs` に書くこと。
      期限は日付の欄で、設計の欄ではありません。
    - `fast_tests.py` が **diff に依らず走る芯**（`CORE`）に `deadline_check` を
      入れ、かつ**その芯が毎周 実際に撃たれる**ようになったら、この門は重複です。
      2026-08-30 時点では `fast_tests.py` は手順のどこからも呼ばれていません
      （`docs/trigger_main.md` にも `stop_check.sh` にも名前がありません）。
    """
    late = sorted((v for v in vs if v.waits), key=lambda v: -v.waits)
    early = [v for v in vs if v.slips]
    if not late and not early:
        return 0
    out: list[str] = []
    if late:
        total = sum(v.waits for v in late)
        out.append(f"**データは揃うのに期限が先の前提 {len(late)}件・合計 {total}日。**"
                   " 軌跡の腕は前提を1件閉じたときだけ動き、"
                   "**「閉じろ」と回に言う門（`drift.overdue()`）は `deadline` だけを読みます** ——"
                   "**この合計は、閉じるのが遅れる日数**です"
                   "（`eta.py` の印字は `ready` 側なので動きません。`Verdict.waits` の実測）:")
        for v in late:
            out.append(f"  {v.deadline} → 判定できるのは **{v.ready}**"
                       f"（{v.waits}日）  {v.claim[:52]}")
        out.append("  → `python scripts/deadline_check.py --shrink`")
    if early:
        out.append(f"**判定できる日より前に置かれた期限 {len(early)}件。**"
                   " その日に言えることは無いので、"
                   "**対照群が空のまま「外れ」が確定します**（腕を1本 測らずに捨てる形）:")
        for v in early:
            out.append(f"  {v.deadline} → 判定できるのは **{v.ready}**  {v.claim[:52]}")
        out.append("  → `python scripts/deadline_check.py --extend`")
    out.append("  **`falsified_if` は緩めないこと。動かすのは `deadline:` の1行だけです。**")
    print("\n".join(out))
    return 2


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
    ap.add_argument("--gate", action="store_true",
                    help="**期限が実データとずれていたら 2 で落ちる**"
                         "（`scripts/stop_check.sh` が読む。**API 0単位**）")
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
    if a.gate:
        return gate(check(load(), as_of=as_of, lag=lag))
    vs = check(load(), as_of=as_of, lag=lag)
    # **印字する道の1か所だけで積みます**（`record_estimates()` の註）。
    # 純粋な関数の中で書くと、控えは「この機械が何回 撃たれたか」を数えます。
    record_estimates(vs, as_of=as_of)
    print("\n".join(lines(vs, lag)))
    _print_starved_floors()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
