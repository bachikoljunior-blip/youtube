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
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

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
    """**実データが何日 遅れているか。** `data/analytics_lag.jsonl` の実測から。"""
    path = ROOT / "data" / "analytics_lag.jsonl"
    try:
        rows = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        last = max(r["last_day"] for r in rows)
        return max(0, ((as_of or today_jst()) - date.fromisoformat(last)).days)
    except Exception:                                          # noqa: BLE001
        return FALLBACK_LAG_DAYS


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
EXPR_NS = {"json": json, "rows": _rows, "date": date,
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


def _ans_now() -> Answer:
    return Answer(today_jst(), "手元のデータだけで判定できます")


def _ans_external(need: dict) -> Answer:
    what = str(need.get("what") or "（何を待つか書かれていません）")
    return Answer(None, f"**こちらの手では起こせません**: {what}", unreachable=True)


def _ans_accrual(need: dict, as_of: date) -> Answer:
    expr = str(need.get("count_expr") or "")
    want = int(need.get("need") or 0)
    since_s = str(need.get("since") or "")
    try:
        have = int(eval(expr, dict(EXPR_NS)))                  # noqa: S307
    except Exception as e:                                     # noqa: BLE001
        return Answer(None, f"**数えられませんでした**: {e}")
    if have >= want:
        return Answer(as_of, f"要 {want} ／ いま **{have}** → 足りています")
    try:
        elapsed = max(1, (as_of - date.fromisoformat(since_s)).days)
    except ValueError:
        return Answer(None, f"要 {want} ／ いま {have}（`since` が読めないので伸び率が出せません）")
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
                            "**伸び率が出せないので、いつ届くか言えません**）")
    days = math.ceil((want - have) / rate)
    return Answer(as_of + timedelta(days=days),
                  f"要 {want} ／ いま {have}（{elapsed}日で {rate:.2f}/日）→ あと {days}日")


def _ans_published_group(need: dict, as_of: date, lag: int) -> Answer:
    """**作った日で決まる群**が、公開 → 落ち着く → 実データに出るまで。

    在庫の予約日は `data/uploaded.jsonl` の `at` に**実際に入っている**ので、
    中央値で見積もらずに、**その本の予約日そのもの**で解きます。
    """
    after = str(need.get("created_after") or "")
    count = int(need.get("count") or 1)
    settle = int(need.get("settle_days", DEFAULT_SETTLE_DAYS))
    since_pub = str(need.get("published_after") or "")
    rows = [r for r in _rows("uploaded.jsonl") if str(r.get("uploaded_at") or "") >= after]
    pub = sorted(p for p in (str(r["at"])[:10] for r in rows if r.get("at")) if p >= since_pub)
    if len(pub) < count:
        tail = f"（{since_pub} 以降に公開する本だけ）" if since_pub else ""
        return Answer(None,
                      f"{after[:10]} 以降に作った本{tail} **{len(pub)}本** ／ 要 {count}本 —— "
                      "**予約にまだ在りません**（作れば動きます）")
    nth = date.fromisoformat(pub[count - 1])
    ready = nth + timedelta(days=settle + lag)
    return Answer(ready,
                  f"{after[:10]} 以降に作った本の **{count}本目の公開 {nth:%m/%d}** "
                  f"＋ 落ち着く {settle}日 ＋ 実データの遅れ {lag}日")


def _ans_after(need: dict, lag: int) -> Answer:
    """**その日が来るのを待っているだけ**の要件。

    `plus_lag: true` なら Analytics の遅れを足します —— 「08/29 時点の累計」は、
    08/29 に見ても **08/26 までの累計**しか出ていません。
    """
    try:
        on = date.fromisoformat(str(need.get("on_date")))
    except (TypeError, ValueError):
        return Answer(None, f"**`on_date` が読めません**: {need.get('on_date')!r}")
    what = str(need.get("what") or "その日のデータ")
    if need.get("plus_lag"):
        return Answer(on + timedelta(days=lag),
                      f"{what} は {on:%m/%d} の分 ＋ 実データの遅れ {lag}日")
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
        return Answer(None, body + " → **群がそろわないので日が出ません**")
    return Answer(ready, body + f" ＋ 落ち着く {SJ.SETTLE_DAYS}日 "
                                f"＋ 遅れ {SJ.ANALYTICS_LAG_DAYS}日")


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
    def mark(self) -> str:
        if self.unchecked:
            return "[??]"
        if self.ready is None:
            return "[!!]"
        if self.deadline is None:
            return "[!!]"
        return "[OK]" if self.ready <= self.deadline else "[!!]"

    @property
    def slips(self) -> bool:
        """期限が、データの来る日より前に置かれているか。"""
        return (self.ready is not None and self.deadline is not None
                and self.ready > self.deadline)

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
        return max(0, (self.deadline - self.ready).days)


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
           f"  実データは **{lag}日 遅れ**ています。**「公開から7日」に必ず足すこと。**"]
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
        if v.ready is None:
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
        else:
            out.append(f"         → 判定できるのは {v.ready:%m-%d}。**期限とちょうど同じ**です")
    bad = [v for v in vs if v.slips]
    unk = [v for v in vs if v.ready is None and not v.unchecked]
    non = [v for v in vs if v.unchecked]
    late = [v for v in vs if v.waits]
    out.append("")
    out.append(f"  期限が早すぎる **{len(bad)}件** ／ 判定できる日が出せない **{len(unk)}件** "
               f"／ 確かめていない **{len(non)}件** ／ 開いている {len(vs)}件")
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--as-of", help="この日に判定するつもりで解く（YYYY-MM-DD）")
    a = ap.parse_args(argv)
    as_of = date.fromisoformat(a.as_of) if a.as_of else today_jst()
    lag = analytics_lag_days(as_of)
    vs = check(load(), as_of=as_of, lag=lag)
    print("\n".join(lines(vs, lag)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
