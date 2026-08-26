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

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Callable

import yaml

from src import settle
from src.ab_split import SETTLE_DAYS, MIN_PER_GROUP, build_times, published

ROOT = Path(__file__).resolve().parent.parent
HYPOTHESES = ROOT / "config" / "hypotheses.yaml"

JST = timezone(timedelta(hours=9))

#: YouTube Analytics の日次の遅れ。**`data/analytics_lag.jsonl` の実測**（`src/settle.py`）。
#: **公開から落ち着いた日に判定しようとしても、その日のデータはまだ来ていません。**
#:
#: **2026-08-26 まで `= 3` のべた書きでした。** 同じ量を `scripts/deadline_check.py` が
#: 実測から出していて（そのとき **4日**）、**A/B 4件だけ1日 楽観**に出ていました。
#: 楽観へ期限を寄せると、**まだ来ていないデータで判定**することになります ——
#: `falsified_if` は「上回らなければ外れ」なので、**外れ側に倒れます。**
ANALYTICS_LAG_DAYS = settle.analytics_lag_days()


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
        """群名 → 予約の中にあと何本足りないか（0 なら足りている）。

        **本数しか見ません。** ここが 0 でも `ok` が False のことがあります ——
        本はそろっているが、**N本目が期限より後ろ**という形です。
        作る側が読むのは、下の `shortfall_in_time()` のほうです。
        """
        return {
            g: max(0, self.min_per_group - len(days)) for g, days in self.groups.items()
        }

    @property
    def last_useful_day(self) -> date:
        """**この日までに公開された本だけが、期限までの判定に間に合います。**

        期限から、落ち着き（`SETTLE_DAYS`）と Analytics の遅れを引いた日。
        `ready` の逆算なので、**同じ2つの定数から出しています**（写さないこと）。
        """
        return self.deadline - timedelta(days=SETTLE_DAYS + ANALYTICS_LAG_DAYS)

    def in_time(self) -> dict[str, int]:
        """群名 → **期限までの判定に間に合う**本数（`last_useful_day` 以前の公開）。"""
        cut = self.last_useful_day
        return {g: sum(1 for d in days if d <= cut) for g, days in self.groups.items()}

    def shortfall_in_time(self) -> dict[str, int]:
        """群名 → **期限に間に合う本**が、あと何本 足りないか。

        ## なぜ `shortfall()` と別に要るのか（2026-08-26 に踏んだ）

        **同じ床を、2つの口が別々に数えていました。**

            scripts/batch_build.motion_shortfall()   対照 **8本** ／ 床 8 → **足りています**
            src/judgeable.Floor.ok                   8本目 **10/10** → 判定 10/16
                                                     → **期限 09/13 を 33日 超えます**

        どちらも嘘ではありません。**前者は本数だけを数え、期限を見ていない**だけです。
        実測（`opening_motion` の対照8本の公開日）——

            08/28 ／ 09/02 ／ 09/06 ／ 09/06 ／ 09/12 ／ **10/02 ／ 10/04 ／ 10/10**

        **期限 09/13 に間に合うのは 5本**で、残り3本は判定のあとに公開されます。

        **この食い違いは、実際に1本ぶんの生成を空振りさせました。** 08/26 の回が
        `motion_shortfall()` の「**あと 1本**」を読んで対照を1本 作り、床は 7→8本 に
        なりましたが、**赤い検査は3件とも赤のまま**でした（本数ではなく日付が縛り）。

        **だから作る側は、こちらを読むこと。** そうすれば「あと 3本」と出て、
        `--long` を付けない回が**期限の内側の枠**へ自動で寄せます。

        **覆る条件**: 期限を延ばす判断をした回は、`last_useful_day` が後ろへ動くので、
        ここも自動でゆるみます。**この関数の側に期限を書き写さないこと。**
        """
        return {g: max(0, self.min_per_group - n) for g, n in self.in_time().items()}

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


#: ショートの上限（秒）。`config/hypotheses.yaml` の「ショート(3分以下)」と同じ数。
SHORT_MAX_S = 180.0


def _short_topics() -> set[str]:
    """**ショートとして出したテーマID**（控えの `duration_s` から。3分以下）。

    ## `s-` の接頭辞では割れません（2026-08-26 に実測）

    控えのうち `duration_s` を持つ 56件を数えると:

        `s-` で始まるのに **3分超** が **3件**
        `s-` で始まらないのに 3分以下 が **6件**（＝ 深い題ショート）

    **`request_form` の A/B は「ショートの終端の依頼」を測っています。**
    接頭辞で割ると、深い題ショート（`batch_build` が毎回 半分ぐらい混ぜる）が
    **処置も対照も無い所へ落ち**、群が半分の速さでしか積みません。

    `duration_s` は新しい欄なので、**無い行は接頭辞に落とします**（568件中 512件）。
    それらは全部 `landed`（2026-08-26 19:08）より前の本なので、この前提には入りません。
    """
    out: set[str] = set()
    for row in _ledger_rows():
        topic = str(row.get("topic") or "")
        if not topic:
            continue
        d = row.get("duration_s")
        if isinstance(d, (int, float)) and d > 0:
            if float(d) <= SHORT_MAX_S:
                out.add(topic)
            else:
                out.discard(topic)          # **後の行が勝ち**（`published()` と同じ）
        elif topic.startswith("s-"):
            out.add(topic)
    return out


def _ledger_rows() -> list[dict]:
    """`data/uploaded.jsonl` を素で。**`published()` は `duration_s` を捨てます。**"""
    path = ROOT / "data" / "uploaded.jsonl"
    out: list[dict] = []
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(json.loads(line))
        except ValueError:
            continue
    return out


def _members_by_request_form() -> dict[str, list[Member]]:
    """登録の依頼を途中にも入れる A/B。**ショートだけ**を、テーマIDのハッシュで割る。

    `_members_by_split()` を使わないのは、**長尺を落とす必要がある**からです
    （長尺は依頼そのものを書かない ＝ `src/script_writer.ROLE`）。
    落とし方は接頭辞ではなく**控えの `duration_s`**（上の `_short_topics`）。
    """
    from src.ab_split import EXPERIMENTS
    from src.script_writer import request_form

    exp = EXPERIMENTS["request_form"]
    builds, pub, vid = build_times(), _publish_by_topic(), _video_by_topic()
    shorts = _short_topics()
    out: dict[str, list[Member]] = {exp.treated: [], exp.control: []}
    for topic, built in builds.items():
        if built < exp.landed or topic not in shorts:
            continue
        day = pub.get(topic)
        group = request_form(topic)
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
    # 登録の依頼を途中にも入れるか（`src/script_writer.request_form`）。
    # **ショートだけ**が群に入ります（長尺は `"長尺"` が返り、`out` に無いので落ちます）。
    #
    # **床が 16本 ではなく 72本 なのは、測っているのが engaged ではなく登録だから**です。
    # 登録率の実測は **0.0318%**（3,066再生に1人）。片群 16本 ＝ 約 6,700再生 では
    # 期待 2.1人 で、2群を比べても**効きが2倍でも見分けられません**。
    # 30,000再生 ÷ 418.7再生/本（公開済み130本の実測）＝ **72本**。
    # ここは `config/hypotheses.yaml` の期限 2026-10-11 と同じ引き方です
    # （あちらは対照群が無いので絶対値、こちらは2群）。
    "request_form": (_members_by_request_form, 72),
    # d14dbf7「冒頭の stat を 前提を先・数字を後 に割る」 2026-08-23 22:03:31 JST
    "stat_split": (
        lambda: _members_by_landed(datetime(2026, 8, 23, 22, 3, 31, tzinfo=JST)),
        MIN_PER_GROUP,
    ),
    # `falsified_if` の「対照 8本以上・動きあり 8本以上」がこの前提の N
    "opening_motion": (_members_by_opening_motion, 8),
}

#: `MEMBER_SOURCES` には在るが、**期限は `kind: accrual`（伸び率）で解く**もの。
#:
#: `Floor.ready` は「片群 N本 が予約にそろって初めて日が出る」形なので、
#: **これから積む群**を `SOURCES` に入れると `ready is None` のまま
#: `tests/test_judgeable.py::test_実物で期限が構造的に守れる` が**赤で居座ります**。
#: 実際、`request_form` は立てた回に 0本 / 0本 で、床は 72本 —— 赤が2週間 続きます。
#:
#: **群の数え方は捨てません**（`members("request_form")` はそのまま使えます。
#: `scripts/deadline_check.py` の `ab_members()` がここから数え、
#: 伸び率で「72本目はいつか」を出します）。
#:
#: **積み終わったらここから外すこと。** そのとき yaml の `needs` を
#: `kind: group_key` に戻せば、`Floor` の側で期限が守れるか見張られます。
ACCRUING: set[str] = {"request_form"}

#: yaml の `key:` → (群べつの**公開日**を作る関数, 片群あたりの必要本数)。
#: **`members()` から畳んで作ります。ここに直接足さないこと** ——
#: 足すと群の作り方が2か所になり、`queue_lag.py` と `Floor` が別の群を見ます。
SOURCES: dict[str, tuple[Callable[[], dict[str, list[date]]], int]] = {
    key: ((lambda k=key: _days(members(k))), n)
    for key, (_make, n) in MEMBER_SOURCES.items()
    if key not in ACCRUING
}


def _live_ids() -> set[str] | None:
    """**再生が付く側の `video_id`**（`src/day_cap.py` が1か所で決めています）。

    読めない回は `None` を返し、**絞りません**。
    「観測していないものを、無いことにしない」——
    控えが読めないだけで群が空になると、`ready` が消えて期限が壊れます。
    """
    try:
        from src import day_cap
        from src.ab_split import published

        return day_cap.live_ids([r for r in published() if r.get("at")])
    except Exception:                                    # noqa: BLE001
        return None


def members(key: str) -> dict[str, list[Member]]:
    """その前提の、群べつの本（公開日つき）。**動かす先を決めるのに使う。**

    ## **再生が付かない本は、標本として数えません**（2026-08-26 に足した）

    ここは長いあいだ**公開日だけ**で数えていました。ところが `src/day_cap.py` は
    「1日 10本を超えたぶんと、30分より詰めた本は 0再生」を**実測で**持っています。
    実測の差は**再生の中央値 718 対 2**（`day_cap.live_ids` の節）。

    **0再生の本を1本と数えると、`falsified_if` は「上回らなければ外れ」なので、
    足りない標本がそのまま「外れ」に化けます。** 2026-08-26 の実物では
    `opening_motion 対照(動きなし)` が 8本中 **5本**、
    `stat_split 処置(後)` が 23本中 **10本** そちら側に落ちていて、
    **どちらも期限どおりに「外れ」と判定されるところ**でした。

    落とす条件は **その日の何本目か** だけです（予約を置いた側が決める量なので、
    処置とは独立）。**再生数そのものでは落としません** —— 結果で条件付けると、
    処置が再生を落としている場合にその効果を隠します。
    """
    make, _ = MEMBER_SOURCES[key]
    rows = make()
    keep = _live_ids()
    if keep is None:
        return rows
    return {g: [(d, v) for d, v in ms if v in keep] for g, ms in rows.items()}


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
