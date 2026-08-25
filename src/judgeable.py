"""**その前提は、期限までに判定できるのか。**（API は 0 単位）

## なぜ要るか（2026-08-25 に実測して作った。**同じ形で6回踏んでいます**）

`config/hypotheses.yaml` は「期限」を日付で持ちますが、
**その日にデータが存在するかを誰も確かめていませんでした。**

    処置が実装に入る  →  その作りの本ができる  →  **予約の順番待ち**  →  公開
      →  **公開から7日**（初速だけを見ない）  →  **Analytics は3日遅れ**  →  判定できる

**真ん中の「予約の順番待ち」が伸び続けています** —— 8/16 に公開した本は
作ってから 0.9日、いま予約に入っている本は**中央値 13.4日・最大 40.2日**。
期限を切ったとき、この足し算を一度もしていません。

足し算をしないと何が起きるか。**期限の日に処置群が空のまま判定に入り、
「上回っていない＝外れ」で前提が倒れます。** 倒れた前提は
`arm_speed` が「当たらなかった腕」として数え、`eta.py` の軌跡が
**その腕を伸ばさなくなります。** つまり **測っていない腕を、測ったことにして捨てる。**

`src/ab_split.py` は同じ穴を「群の中身」の側で塞ぎました（指示より前に作った本を落とす）。
**こちらは「期限」の側です。** 中身が正しくても、**日付が早すぎれば同じ結末**になります。

## 何を出すか

**予約の実物から、判定に要る本が落ち着く日を数えます**（推測ではありません）。

    ready = （群ごとに N本目が公開される日）の**いちばん遅い群** + SETTLE_DAYS + ANALYTICS_LAG

`N` はその前提の「どちらの群も N本に満たなければ判定しない」の N。
`ready > deadline` なら、**その期限は構造的に守れません。**

## 直し方は1つだけ（yaml 冒頭の作法と同じ）

**期限だけを延ばすこと。`falsified_if` は変えないこと。**
条件を緩めるのと期限を動かすのは別のことです。ここが混ざると、
「測れないから条件を甘くした」に化けます。

## 数えていないもの（**言っておく**）

- **30再生以上・engaged が付いているか**は見ていません。ここが見るのは**日付だけ**です。
  だから `ready` は**下限**で、実際の判定日はこれ以降になります
- 予約が動けば `ready` も動きます（`reschedule.py` は日付を書き換えます）。
  **保存しないこと** —— 撃つたびに実物から数え直します
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import yaml

from src.ab_split import SETTLE_DAYS, MIN_PER_GROUP, build_times, published

ROOT = Path(__file__).resolve().parent.parent
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"

JST = timezone(timedelta(hours=9))

#: YouTube Analytics の日次は3日遅れます（`data/analytics_lag.jsonl` で毎回測っている値）。
#: **公開から7日たった日に判定しようとしても、その日のデータはまだ来ていません。**
ANALYTICS_LAG_DAYS = 3


@dataclass
class Floor:
    """1つの前提の「いちばん早く判定できる日」。"""

    key: str
    deadline: date
    #: 群名 → その群の本の公開日（昇順）
    groups: dict[str, list[date]] = field(default_factory=dict)
    #: 判定に要る、片群あたりの本数
    min_per_group: int = MIN_PER_GROUP

    @property
    def nth(self) -> dict[str, date | None]:
        """群名 → N本目が公開される日（そろわない群は `None`）。"""
        out: dict[str, date | None] = {}
        for g, days in self.groups.items():
            out[g] = days[self.min_per_group - 1] if len(days) >= self.min_per_group else None
        return out

    @property
    def ready(self) -> date | None:
        """判定に要る本が**落ち着いて、Analytics に載る**日。そろわなければ `None`。"""
        nth = self.nth
        if not nth or any(d is None for d in nth.values()):
            return None
        latest = max(d for d in nth.values() if d is not None)
        return latest + timedelta(days=SETTLE_DAYS + ANALYTICS_LAG_DAYS)

    @property
    def ok(self) -> bool:
        """期限までに判定できるか。**そろわない群があれば False。**"""
        r = self.ready
        return r is not None and r <= self.deadline

    def shortfall(self) -> dict[str, int]:
        """群名 → 予約の中にあと何本足りないか（0 なら足りている）。"""
        return {
            g: max(0, self.min_per_group - len(days)) for g, days in self.groups.items()
        }

    def lines(self) -> list[str]:
        out = [f"  {self.key}  期限 {self.deadline:%m/%d}"]
        for g in sorted(self.groups):
            days, nth = self.groups[g], self.nth[g]
            when = f"{self.min_per_group}本目 {nth:%m/%d}" if nth else "**そろいません**"
            out.append(f"    {g:14s} 予約 {len(days):3d}本  {when}")
        r = self.ready
        if r is None:
            need = ", ".join(f"{g} あと{n}本" for g, n in self.shortfall().items() if n)
            out.append(f"    → **判定できる日が出ません**（{need}）。在庫を割り当てるか、条件の N を見直すこと")
        elif r <= self.deadline:
            out.append(f"    → いちばん早い判定日 **{r:%m/%d}**（期限まで {(self.deadline - r).days}日の余裕）")
        else:
            out.append(
                f"    → [!] **期限までに判定できません。** いちばん早くて **{r:%m/%d}**"
                f"（期限を {(r - self.deadline).days}日 超えます）"
                f"\n       **期限だけを {r:%Y-%m-%d} 以降へ延ばすこと。`falsified_if` は変えないこと。**"
            )
        return out


# --- 群の作り方 -------------------------------------------------------------
#
# **前提ごとに群の割り方が違います。** 散文の `falsified_if` からは機械が読めないので、
# ここに1件ずつ置き、yaml 側の `key:` で結びます。
# **新しい A/B を足したら、ここにも足すこと**（`tests/test_judgeable.py` が
# yaml と突き合わせて、片方にしか無い `key` を落とします）。


def _publish_by_topic() -> dict[str, date]:
    return {
        str(r["topic"]): r["publish"]  # type: ignore[index]
        for r in published()
        if r.get("publish") and r.get("topic")
    }


def _video_by_topic() -> dict[str, str]:
    """テーマID → `video_id`。**`_publish_by_topic()` と同じ走査・同じ勝ち方**。

    同じ題材を別の本として2回上げた組が実測 20件あります（`ab_split.published`）。
    `_publish_by_topic` は素直な辞書内包なので**後の行が勝ち**ます。
    ここも同じ順で作らないと、**日は本Aのもの・IDは本Bのもの**という
    組み合わせが出ます（動かす先を決める側は、それを1本だと思って撃ちます）。
    """
    return {
        str(r["topic"]): str(r.get("video_id") or "")  # type: ignore[index]
        for r in published()
        if r.get("publish") and r.get("topic")
    }


def _publish_by_video() -> dict[str, date]:
    return {
        str(r["video_id"]): r["publish"]  # type: ignore[index]
        for r in published()
        if r.get("publish") and r.get("video_id")
    }


#: 群の1本 ＝ （公開日, `video_id`）。**`video_id` は「どの本を動かせば早まるか」に要る。**
#: 日だけを返していたので、`scripts/queue_lag.py` を書くときに
#: **振り分けをもう一度書き写す**しかありませんでした（このリポジトリで7回踏んでいる形）。
#: **群の作り方はここ1か所。日の一覧は下の `_days()` が畳んで出します。**
Member = tuple[date, str]


def _members_by_split(name: str) -> dict[str, list[Member]]:
    """`ab_split.EXPERIMENTS` の A/B（IDで振り分け・指示より前の本は落とす）。"""
    from src.ab_split import EXPERIMENTS

    exp = EXPERIMENTS[name]
    builds, pub, vid = build_times(), _publish_by_topic(), _video_by_topic()
    out: dict[str, list[Member]] = {exp.treated: [], exp.control: []}
    for topic, built in builds.items():
        if built < exp.landed:
            continue  # 指示が入る前に作った本。IDが何と言おうと処置は入っていない
        group = exp.split(topic)
        day = pub.get(topic)
        if group in out and day:
            out[group].append((day, vid.get(topic, "")))
    for rows in out.values():
        rows.sort()
    return out


def _members_by_landed(landed: datetime) -> dict[str, list[Member]]:
    """振り分けの無い変更（入った後に作る本は**全部**そうなる）を、作った時刻で割る。"""
    builds, pub, vid = build_times(), _publish_by_topic(), _video_by_topic()
    out: dict[str, list[Member]] = {"対照(前)": [], "処置(後)": []}
    for topic, built in builds.items():
        day = pub.get(topic)
        if day:
            out["処置(後)" if built >= landed else "対照(前)"].append(
                (day, vid.get(topic, "")))
    for rows in out.values():
        rows.sort()
    return out


def _members_by_opening_motion() -> dict[str, list[Member]]:
    """`YT_OPENING_MOTION` の値で割る（`src/motion_groups.py` が実物から引きます）。"""
    from src import motion_groups

    off, on = motion_groups.groups()
    pub = _publish_by_video()
    return {
        "対照(動きなし)": sorted((d, v) for v in off if (d := pub.get(v))),
        "処置(動きあり)": sorted((d, v) for v in on if (d := pub.get(v))),
    }


def _days(rows: dict[str, list[Member]]) -> dict[str, list[date]]:
    """群べつの本 → 群べつの公開日（昇順）。**`Floor` が要るのはこちらだけ。**"""
    return {g: sorted(d for d, _ in ms) for g, ms in rows.items()}


#: yaml の `key:` → (**群べつの本**を作る関数, 片群あたりの必要本数)
MEMBER_SOURCES: dict[str, tuple[Callable[[], dict[str, list[Member]]], int]] = {
    "title_form": (lambda: _members_by_split("title_form"), MIN_PER_GROUP),
    "hook_form": (lambda: _members_by_split("hook_form"), MIN_PER_GROUP),
    # d14dbf7「冒頭の stat を 前提を先・数字を後 に割る」 2026-08-23 22:03:31 JST
    "stat_split": (
        lambda: _members_by_landed(datetime(2026, 8, 23, 22, 3, 31, tzinfo=JST)),
        MIN_PER_GROUP,
    ),
    # `falsified_if` の「対照 8本以上・動きあり 8本以上」がこの前提の N
    "opening_motion": (_members_by_opening_motion, 8),
}

#: yaml の `key:` → (群べつの**公開日**を作る関数, 片群あたりの必要本数)。
#: **`MEMBER_SOURCES` から畳んで作ります。ここに直接足さないこと** ——
#: 足すと群の作り方が2か所になり、`queue_lag.py` と `Floor` が別の群を見ます。
SOURCES: dict[str, tuple[Callable[[], dict[str, list[date]]], int]] = {
    key: ((lambda make=make: _days(make())), n)
    for key, (make, n) in MEMBER_SOURCES.items()
}


def members(key: str) -> dict[str, list[Member]]:
    """その前提の、群べつの本（公開日つき）。**動かす先を決めるのに使う。**"""
    make, _ = MEMBER_SOURCES[key]
    return make()


def _hypotheses() -> list[dict]:
    doc = yaml.safe_load(HYPOTHESES.read_text(encoding="utf-8")) or {}
    return list(doc.get("hypotheses") or [])


def deadlines() -> dict[str, date]:
    """yaml の `key:` → 期限（**閉じた前提は返しません**）。"""
    out: dict[str, date] = {}
    for h in _hypotheses():
        key = h.get("key")
        if not key or h.get("closed_on"):
            continue
        raw = h.get("deadline")
        out[str(key)] = raw if isinstance(raw, date) else date.fromisoformat(str(raw))
    return out


def floors() -> list[Floor]:
    """`SOURCES` と yaml の両方にある前提について、いちばん早い判定日を数える。"""
    want = deadlines()
    out: list[Floor] = []
    for key, (make, n) in SOURCES.items():
        if key not in want:
            continue  # 閉じた前提、または yaml 側にまだ `key:` が無い
        out.append(Floor(key=key, deadline=want[key], groups=make(), min_per_group=n))
    return sorted(out, key=lambda f: f.deadline)


def report(items: list[Floor] | None = None) -> list[str]:
    items = floors() if items is None else items
    if not items:
        return ["  （`key:` の付いた開いている前提がありません）"]
    bad = [f for f in items if not f.ok]
    head = (
        f"=== 期限までに判定できるか（{len(items)}件） ==="
        if not bad
        else f"=== 期限までに判定できるか（{len(items)}件中 **{len(bad)}件が守れません**） ==="
    )
    out = [head, "  ready = 群ごとの N本目の公開日（いちばん遅い群）"
           f" + 落ち着き {SETTLE_DAYS}日 + Analytics の遅れ {ANALYTICS_LAG_DAYS}日"]
    for f in items:
        out.extend(f.lines())
    return out


def main() -> None:  # pragma: no cover - 目で見る用
    print("\n".join(report()))


if __name__ == "__main__":  # pragma: no cover
    main()
