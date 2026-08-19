"""**A/B の群を「指示が入った本」だけで割る。**

## なぜ要るか（2026-08-19 22:2x に測って作った）

`config/hypotheses.yaml` の走っている実験は2件あり、どちらも
**群をテーマIDから引き直す**と書いてあります（`title_form()` / `hook_form()`）。

    2026-09-12  題を問いの形にすると engaged が上がる     ← `title_form`
    2026-09-16  冒頭1枚目の主役を問いかけにすると…        ← `hook_form`

**IDから引けるのは「どちらの群か」だけで、「その指示が入ったか」ではありません。**
指示（`ASK_TITLE_RULE` / `ASK_HOOK_RULE`）は**その日に足したもの**なので、
それより前に作った本は、IDが「問い」と言っていても**題も冒頭も問いになっていません。**

そして予約は 359本ぶん先まで入っています。**判定日までに公開される本は、
ほとんど全部が指示より前に作られた本**でした —— 実測（この道具で数えた）:

    hook_form  判定 09/16・公開から7日 ⇒ 09/09 までに公開する本
        問い 127本 —— **指示が入った本 0本**
        条件 123本 —— 指示が入った本 0本

**両群とも中身が完全に同じもの**を突き合わせることになります。差は出ません。
`falsified_if` は「上回っていない（同点も外れ）」なので、**外れが確定する形**です。
そして `next_if_false` は「問いかけの形は畳む」→「題も冒頭も空振りなら
**作りではなく題材の側** ＝ M20（長尺・別のニッチ）を繰り上げる」と続きます。

つまり **`eta.py` が名指しする唯一の近い腕（1本あたり 1.4倍）を、
一度も試さないまま畳む**ところでした。件数も見た目も正常なまま、
**「どちらが効いたか」だけが壊れている**形です（8/19 20:5x の塩の件と同じ）。

## 直し方は1つだけ

**比べる本を「指示が入ってから作った本」に限ること。** 閾値（両群8本・
公開から7日・中央値・同点も外れ）は**1つも変えていません。**
条件を緩めたのではなく、**母集団が claim と食い違っていたのを合わせた**だけです。

**まだ1本も判定していない時点で直しています**（結果を見てから動かしたのでは
ありません）。判定日は 09/12 と 09/16 で、実データは3日遅れです。

## 読むファイル（**API を1単位も使いません**）

    data/batch_runs.jsonl   テーマID → **いつ作ったか**（`at` ＋ `results[].topic`）
    data/uploaded.jsonl     テーマID → video_id → **いつ公開するか**（`at`）

**控えに作った記録が無い本は「指示が入っていない」側に数えます**（実測 50/419）。
古い本ほど記録が無いので、**安全側**です。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

from src.script_writer import hook_form, title_form

ROOT = Path(__file__).resolve().parent.parent
BATCH = ROOT / "data" / "batch_runs.jsonl"
LEDGER = ROOT / "data" / "uploaded.jsonl"

JST = timezone(timedelta(hours=9))

#: 判定に要る、**片群あたりの本数**。`config/hypotheses.yaml` の
#: 「どちらの群も 8本に満たなければ判定しない」と同じ数。**ここだけで持たないこと** ——
#: 数を変えるなら yaml も同時に変える（`tests/test_ab_split.py` が突き合わせています）。
MIN_PER_GROUP = 8

#: 「初速だけを見ない」ための日数。yaml の「公開から7日以上たっていること」と同じ。
SETTLE_DAYS = 7


@dataclass(frozen=True)
class Experiment:
    """走っている A/B 1件。**指示が実装に入った時刻を持つのが本体です。**"""

    name: str
    #: テーマID → 群名
    split: Callable[[str], str]
    #: 指示が足される側の群名（`ASK_*_RULE` が入るほう）
    treated: str
    #: 何も足さない側の群名
    control: str
    #: **その指示が `src/script_writer.py` に入った時刻**（JST）。
    #: これより前に作った本には、IDが何と言おうと指示は入っていません。
    landed: datetime
    #: `config/hypotheses.yaml` の判定日
    deadline: date
    #: 由来（`git log -S` で引ける commit）
    commit: str = ""


#: 走っている実験。**新しく振り分けを足したら、ここにも足すこと。**
#: 足し忘れると `status.py` が「指示が入った本 0本」を言わないまま、
#: 中身の同じ2群を突き合わせて外れを出します。
EXPERIMENTS: dict[str, Experiment] = {
    "title_form": Experiment(
        name="title_form",
        split=title_form,
        treated="問い",
        control="断定",
        # 6a7520f「道具は『無関係』でなく『一度も試していない』と言っていた」
        landed=datetime(2026, 8, 19, 16, 50, 5, tzinfo=JST),
        deadline=date(2026, 9, 12),
        commit="6a7520f",
    ),
    "hook_form": Experiment(
        name="hook_form",
        split=hook_form,
        treated="問い",
        control="条件",
        # 443c66b「冒頭1枚目の主役（kind=stat の note）を問いかけに振り分ける A/B」
        landed=datetime(2026, 8, 19, 21, 0, 3, tzinfo=JST),
        deadline=date(2026, 9, 16),
        commit="443c66b",
    ),
}


def build_times(path: Path | None = None) -> dict[str, datetime]:
    """テーマID → **いちばん早い作成時刻**（JST）。

    撃ち直した本は複数回出てきます。**早いほうを採ります** ——
    「指示が入る前に一度作られている」なら、その本は指示より前の作りです。
    """
    src = path or BATCH
    out: dict[str, datetime] = {}
    if not src.exists():
        return out
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            at = datetime.fromisoformat(str(row["at"]))
        except (ValueError, KeyError, TypeError):
            continue
        for res in row.get("results") or []:
            topic = res.get("topic")
            if not topic or not res.get("video_id") or res.get("error"):
                continue
            if topic not in out or at < out[topic]:
                out[topic] = at
    return out


def published(path: Path | None = None) -> list[dict[str, object]]:
    """控えの1行1本。`topic` と **公開日**（`at`・UTC）だけ取り出す。

    `at` が無い行（実測 46/419）は**公開日が分からない**ので落とします。
    落とした数は `split_counts` が返して、`status.py` が印字します。
    """
    src = path or LEDGER
    out: list[dict[str, object]] = []
    if not src.exists():
        return out
    for line in src.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        topic = row.get("topic")
        if not topic:
            continue
        at = row.get("at")
        pub: date | None = None
        if at:
            try:
                pub = datetime.fromisoformat(str(at).replace("Z", "+00:00")).date()
            except ValueError:
                pub = None
        out.append({"topic": topic, "video_id": row.get("video_id"), "publish": pub})
    return out


@dataclass
class Counts:
    """1つの実験の、いまの姿。"""

    experiment: str
    #: 群名 → 指示が入った本の数（公開から `SETTLE_DAYS` たつものだけ）
    treated_ready: dict[str, int] = field(default_factory=dict)
    #: 群名 → 指示が入った本の数（判定日までに公開されるが、まだ落ち着かない本も含む）
    treated_all: dict[str, int] = field(default_factory=dict)
    #: 群名 → **指示が入っていないのに、その群に振り分けられている本**の数
    stale: dict[str, int] = field(default_factory=dict)
    #: 公開日が控えから読めなかった本
    unknown_publish: int = 0

    @property
    def judgeable(self) -> bool:
        """両群とも `MIN_PER_GROUP` に届いているか。"""
        return bool(self.treated_ready) and all(
            n >= MIN_PER_GROUP for n in self.treated_ready.values()
        )

    def short(self) -> str:
        """`status.py` が1行で出す形。"""
        parts = [f"{g} {self.treated_ready.get(g, 0)}本" for g in sorted(self.treated_ready)]
        head = "指示が入って落ち着いた本: " + " / ".join(parts)
        if self.judgeable:
            return head + "  → **判定できます**"
        need = ", ".join(
            f"{g} あと{MIN_PER_GROUP - n}本"
            for g, n in sorted(self.treated_ready.items())
            if n < MIN_PER_GROUP
        )
        return head + f"  → **まだ判定しない**（{need}）"


def split_counts(
    exp: Experiment,
    *,
    as_of: date | None = None,
    builds: dict[str, datetime] | None = None,
    ledger: list[dict[str, object]] | None = None,
) -> Counts:
    """`exp` について、いま何本そろっているかを数える。

    `as_of` は判定日（既定は `exp.deadline`）。
    **「落ち着いた本」＝ `as_of` の `SETTLE_DAYS` 日前までに公開する本**です。
    """
    when = as_of or exp.deadline
    settled_by = when - timedelta(days=SETTLE_DAYS)
    bt = build_times() if builds is None else builds
    rows = published() if ledger is None else ledger

    c = Counts(experiment=exp.name)
    for g in (exp.treated, exp.control):
        c.treated_ready[g] = 0
        c.treated_all[g] = 0
        c.stale[g] = 0

    for row in rows:
        topic = str(row.get("topic") or "")
        pub = row.get("publish")
        if pub is None:
            c.unknown_publish += 1
            continue
        assert isinstance(pub, date)
        if pub > when:
            continue  # 判定日より後に公開する本は、この判定には入らない
        group = exp.split(topic)
        if group not in c.treated_all:
            continue
        built = bt.get(topic)
        if built is None or built < exp.landed:
            c.stale[group] += 1
            continue
        c.treated_all[group] += 1
        if pub <= settled_by:
            c.treated_ready[group] += 1
    return c


def report(as_of: date | None = None) -> str:
    """全部の実験を、人が読む形で。"""
    lines: list[str] = []
    for exp in EXPERIMENTS.values():
        c = split_counts(exp, as_of=as_of)
        lines.append(f"=== {exp.name}（判定 {exp.deadline} / 指示は {exp.landed:%m/%d %H:%M} に入った・{exp.commit}）===")
        for g in (exp.treated, exp.control):
            lines.append(
                f"  {g:4s} 群  指示が入って落ち着いた {c.treated_ready[g]:4d}本"
                f" ／ 判定日までに公開する指示入り {c.treated_all[g]:4d}本"
                f" ／ **指示が入っていないのにこの群にいる {c.stale[g]:4d}本**"
            )
        lines.append("  " + c.short())
        if c.unknown_publish:
            lines.append(f"  （控えに公開日が無い {c.unknown_publish}本は、どちらにも数えていません）")
        lines.append("")
    lines.append(
        "**`stale` の本を混ぜて判定しないこと。** IDが群を決めるので件数は正常に見えますが、"
        "\n中身は両群とも指示より前の作りで同じです。差が出ないのは当たり前で、"
        "\nそれを『外れ』と読むと `next_if_false` が腕ごと畳みます（`src/ab_split.py` の冒頭）。"
    )
    return "\n".join(lines)
