"""A/B の**判定に実際に使える本**を数える（**API 0単位**）。

読むのは `data/scan.jsonl` の最後の1行（Analytics の累計）と
`src.judgeable.members()` だけです。**日枠が尽きていても通ります。**

## なぜ要るか（2026-09-01 に実測して足した）

`scripts/ab_split.py` は `title_form` について **「問い 23本 / 断定 19本 →
判定できます」** と印字します。ところが**その 42本のうち 13本には、
Analytics の行がありません**（`data/scan.jsonl` に `動画.<id>.views` が無い）:

    問い  23本中 **7本**が公開から1日（Analytics の遅れ 3〜4日・まだ来ていない）
    断定  19本中 **6本**（うち **4本は公開から5日たっても0再生**。
          例 `A91-FSp6liY` 2026-08-27 08:00 JST 公開・行なし）

**engaged 比率は `engagedViews ÷ views` なので、再生 0 の本には値が存在しません。**
つまり床（片群16本）は**値の出ない本の上に立っていました。**
`falsified_if` は「上回らなければ外れ」なので、
**見分けられなかっただけの実験が「効かない実験」として閉じ、
`next_if_false` が腕ごと畳みます**（`config/hypotheses.yaml` の `title_form` は
腕 `per_video`）。**その腕は `eta.py` が「引けるのはこれだけ」と名指ししている腕です。**

数えるのを「予約に在る本」から「**値の出る本**」へ変えるのがこの道具です。

## 「0再生を落とすのは、結果で条件付けることでは？」

**半分そうです。だから落とすのではなく、別に数えて出します。**
`src.judgeable.members()` の冒頭が言うとおり、結果（再生数）で標本を絞ると
「処置が再生を落としている」場合にその効果を隠します。
ここでは **(a) 値の出る本の数**と **(b) 群べつの0再生率**の両方を出し、
**(b) に群の差があるときは、engaged の順位和ではなく 0再生率のほうを見ること**を
印字します（0再生率の差は、engaged では原理的に測れません）。

## 覆る条件

- `data/scan.jsonl` の窓（`since`）より前に公開した本は、行が無くても
  「0再生」ではありません。**窓より前の本は `未知` に数えます**（落としません）。
- Analytics の遅れが縮んで、公開当日から行が来るようになったら
  `src.settle.SETTLE_DAYS` 側と一緒に見直すこと。
- 実験の `metric` が engaged でも登録でもない値に変わったら、`_RATIO` に足すこと。
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

from src import judgeable
from src.ab_split import EXPERIMENTS, floor_of
from src.settle import SETTLE_DAYS

ROOT = Path(__file__).resolve().parent.parent
SCAN = ROOT / "data" / "scan.jsonl"

#: 実験の `metric` → (分子, 分母)。分母が 0 の本には値がありません。
_RATIO: dict[str, tuple[str, str]] = {
    "engaged": ("engagedViews", "views"),
    "登録": ("subscribersGained", "views"),
}


def latest_scan(path: Path | None = None) -> tuple[dict[str, float], date | None]:
    """`data/scan.jsonl` の最後の1行（値の表と、走査の窓の始まり）。"""
    p = path or SCAN
    if not p.exists():
        return {}, None
    last = None
    with p.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                last = line
    if not last:
        return {}, None
    row = json.loads(last)
    since = row.get("since")
    return dict(row.get("values") or {}), (date.fromisoformat(since) if since else None)


@dataclass
class GroupCount:
    """1つの群の、**判定に使える本の内訳**。"""

    group: str
    #: `members()` が返した本（＝いまの床が数えている本）
    counted: int = 0
    #: 値が出た本の比率（分母 > 0 の行が在る）
    measured: list[float] = field(default_factory=list)
    #: 公開から `SETTLE_DAYS` 日たっているのに行が無い ＝ **0再生**
    zero: int = 0
    #: まだ `SETTLE_DAYS` 日たっていない（Analytics の遅れ。**0再生ではない**）
    young: int = 0
    #: 走査の窓より前の公開（行が無くても 0再生とは言えない）
    unknown: int = 0

    @property
    def usable(self) -> int:
        return len(self.measured)

    @property
    def zero_rate(self) -> float | None:
        """0再生率（0再生 ÷（値の出る本 ＋ 0再生））。**若い本は入れません。**"""
        base = self.usable + self.zero
        return None if base == 0 else self.zero / base


def counts(key: str, *, today: date | None = None,
           values: dict[str, float] | None = None,
           since: date | None = None) -> dict[str, GroupCount]:
    """群ごとの内訳。**`members()` と同じ本を数えます**（群の作り方は1か所）。"""
    if values is None:
        values, since = latest_scan()
    today = today or datetime.now().date()
    exp = EXPERIMENTS.get(key)
    num, den = _RATIO.get(getattr(exp, "metric", "engaged"), _RATIO["engaged"])
    out: dict[str, GroupCount] = {}
    for group, ms in judgeable.members(key).items():
        gc = GroupCount(group=group, counted=len(ms))
        for pub, vid in ms:
            d = values.get(f"動画.{vid}.{den}")
            n = values.get(f"動画.{vid}.{num}")
            if d:
                gc.measured.append(float(n or 0) / float(d))
            elif since is not None and pub < since:
                gc.unknown += 1
            elif (today - pub).days < SETTLE_DAYS:
                gc.young += 1
            else:
                gc.zero += 1
        out[group] = gc
    return out


def earliest(key: str, *, today: date | None = None,
             gcs: dict[str, GroupCount] | None = None) -> tuple[date, dict[str, float]] | None:
    """**値の出る本**が床に届く、いちばん早い日。届いているなら `None`。

    `src.ab_split.Counts.earliest_under_rule` は「予約に載る本」で解いています。
    ここは**値の出る本**で解き直します —— 同じ日数でも、
    **0再生の本のぶんだけ遅い**（実測 2026-09-01: `title_form` の断定は
    0再生率 29%。1日1本の規則では、値の出る本は **1日 0.36本** しか増えません）。

    式（全部この回の実測から）::

        1日に増える値の出る本 ＝ 規則の上限（1本/日）× その群の取り分 × (1 − 0再生率)
        いちばん早い日 ＝ 今日 ＋ 足りない本 ÷ 上の速さ ＋ 落ち着き ＋ Analytics の遅れ

    **覆る条件**: 取り分は `members()` の実績（IDのハッシュ）から数えています。
    振り分けの塩を変えたら取り分も動くので、そのときは数え直すこと。
    """
    from src import house_rule

    today = today or datetime.now().date()
    gcs = gcs if gcs is not None else counts(key, today=today)
    if not gcs:
        return None
    floor = floor_of(key)
    lack = {g: floor - gc.usable for g, gc in gcs.items() if gc.usable < floor}
    if not lack:
        return None
    total = sum(gc.counted for gc in gcs.values()) or 1
    cap = max(1, house_rule.cap())
    days: dict[str, float] = {}
    for g, need in lack.items():
        gc = gcs[g]
        share = gc.counted / total
        alive = 1.0 - (gc.zero_rate or 0.0)
        rate = cap * share * alive
        days[g] = float("inf") if rate <= 0 else need / rate
    worst = max(days.values())
    if worst == float("inf"):
        return None
    when = today + timedelta(
        days=int(-(-worst // 1)) + SETTLE_DAYS + judgeable.ANALYTICS_LAG_DAYS
    )
    return when, days


def lines(key: str, *, today: date | None = None) -> list[str]:
    """`scripts/ab_split.py` が短く1〜4行 出す形。**床は `floor_of()`。**"""
    gcs = counts(key, today=today)
    if not gcs:
        return []
    floor = floor_of(key)
    parts = [f"{g} {gc.usable}本" for g, gc in sorted(gcs.items())]
    out = [
        "  **値の出る本**（Analytics に行が在る）: " + " / ".join(parts)
        + f"  ／ 床 片群 {floor}本"
    ]
    detail = " ／ ".join(
        f"{g}: 0再生 {gc.zero}本・遅れ待ち {gc.young}本"
        + (f"・窓の外 {gc.unknown}本" if gc.unknown else "")
        for g, gc in sorted(gcs.items())
        if gc.zero or gc.young or gc.unknown
    )
    if detail:
        out.append(f"    内訳（数には入っているが値が出ない本）: {detail}")
    lack = {g: floor - gc.usable for g, gc in gcs.items() if gc.usable < floor}
    if lack:
        need = ", ".join(f"{g} あと{n}本" for g, n in sorted(lack.items()))
        out.append(
            "  [!] **床に届いているのは予約の本数だけで、値の出る本は届いていません**"
            f"（{need}）。**いま判定すると、見分けられなかっただけの実験が"
            "『外れ』で閉じ、`next_if_false` が腕ごと畳みます。**"
        )
        got = earliest(key, today=today, gcs=gcs)
        if got is not None:
            when, days = got
            slow = " ／ ".join(f"{g} {d:.0f}日" for g, d in sorted(days.items()))
            out.append(
                f"    **値の出る本が床に届くのは、いちばん早くて {when:%Y-%m-%d}**"
                f"（規則 1本/日 × 群の取り分 ×（1−0再生率）で {slow}"
                f" ＋ 落ち着き{SETTLE_DAYS}日 ＋ 遅れ{judgeable.ANALYTICS_LAG_DAYS}日）。"
                "**期限がこれより手前なら、期限だけを延ばすこと。"
                "`falsified_if` は1文字も変えないこと。**"
            )
    rates = {g: gc.zero_rate for g, gc in gcs.items() if gc.zero_rate is not None}
    if len(rates) == 2 and max(rates.values()) - min(rates.values()) >= 0.15:
        hi = max(rates, key=lambda g: rates[g])
        out.append(
            "  [!] **0再生率が群で違います**（"
            + " / ".join(f"{g} {r:.0%}" for g, r in sorted(rates.items()))
            + f"）。**その差は engaged では測れません** —— `{hi}` の側が"
            "再生そのものを落としている可能性があるので、"
            "engaged の順位和より先に、0再生率のほうを判定すること。"
        )
    return out


def main(argv: list[str] | None = None) -> int:
    import sys

    # **既定は `judgeable.MEMBER_SOURCES` の全部**（`EXPERIMENTS` ではありません）。
    # `stat_split` と `opening_motion` は `ab_split.EXPERIMENTS` に無く、
    # `judgeable` 側にしかいません —— そこを既定から落とすと、
    # **いちばん判定が近い2件が、この道具の外に出ます**（実測 2026-09-01:
    # `stat_split` 処置(後) は 値の出る本 13本／床16、0再生率 24% 対 1%）。
    keys = (argv if argv is not None else sys.argv[1:]) or list(judgeable.MEMBER_SOURCES)
    for key in keys:
        if key not in judgeable.MEMBER_SOURCES:
            print(f"[ab_verdict] 知らない実験: {key}")
            continue
        print(f"=== {key} ===")
        for line in lines(key):
            print(line)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
