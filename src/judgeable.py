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
        """判定に要る本が**落ち着いて、Analytics に載る**日。そろわなければ `None`。

        ## **公開されただけでは、値は出ません**（2026-09-01 に実測して足した）

        ここは長らく「N本目が公開された日 ＋ 落ち着き ＋ 遅れ」でした。
        ところが**公開されても Analytics に行が来ない本があります** ——
        実測 2026-09-01 の `title_form`: 断定の群 19本 のうち **4本**は
        公開から5日たっても `data/scan.jsonl` に行が無く（例 `A91-FSp6liY`
        2026-08-27 08:00 JST 公開）、**0再生**でした。
        engaged は `engagedViews ÷ views` なので、**再生 0 の本には値がありません。**

        `ready` はそのまま `scripts/deadline_check.py --shrink` が期限を縮める
        根拠になるので、ここが楽観だと**まだ値の出ていない標本で判定**します。
        `falsified_if` は「上回らなければ外れ」なので、
        **見分けられなかっただけの実験が『外れ』で閉じ、`next_if_false` が
        腕ごと畳みます。** 実測でその腕は `per_video` ＝ `scripts/eta.py` が
        「引けるのはこれだけ」と名指ししている、ただ1本の腕でした。

        だから **`src.ab_verdict.earliest()`（値の出る本で解いた日）と、
        遅いほうを取ります。** 遅い import は循環を避けるためです
        （`ab_verdict` → `ab_split` → ここ）。

        **覆る条件**: 0再生の本が出なくなれば `earliest()` は `None` を返し、
        ここは元の式に戻ります（**自動で戻ります。条件を書き足さないこと**）。
        """
        nth = self.nth
        if not nth or any(d is None for d in nth.values()):
            return None
        latest = max(d for d in nth.values() if d is not None)
        base = latest + timedelta(days=SETTLE_DAYS + ANALYTICS_LAG_DAYS)
        try:
            from src import ab_verdict  # noqa: PLC0415

            got = ab_verdict.earliest(self.key)
        except Exception:  # 走査が無い環境では、元の式のまま
            return base
        return base if got is None else max(base, got[0])

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
    """`ab_split.EXPERIMENTS` の A/B（IDで振り分け・指示より前の本は落とす）。

    ## **`Experiment.eligible` を読みます**（2026-08-28 に足した。最適化の回）

    `ab_split` は 2026-08-27 に `eligible=_shorts_only` を **`request_form` と
    `slide_pace` の両方**へ足しました。`ab_split.split_counts()` はそれを読みます。
    **ここは読んでいませんでした。** 同じ問い（「その本は群に入るか」）を
    2か所が別々に解いて、**片方だけが `eligible` を見ていた**形です
    （`docs/JOURNAL.md` にある、この repo で通算13回目）。

    ### 実測（塞ぐ前に、実際に出ていた害）

    `slide_pace` の群に、**長尺が3本**入っていました —— どれも
    2026-08-27 夜に主実行が作った長尺です:

        8hJnwkC8NU0  iryohi-furusato-joge-nenshubetsu  285.9s  → 速い  10/06
        KfQeYEJwL7Q  iryohi-zeiritsu-dan-kaidan        302.8s  → 速い  10/11
        f9WbldIUYpk  iryohi-jikofutan-2percent         363.2s  → 遅い  10/07

    **長尺は `reveal_variants` を1度も通らない**ので、この3本には
    刻みの処置が**入っていません**。IDのハッシュだけで群を名乗っていました。

    害は標本の汚れだけでは済みません。`scripts/deadline_check._project_nth()` は
    群がまだ N本 に満たないとき **`max(積み上がる日, pub[-1])`** で N本目を出します。
    `pub[-1]` がこの長尺（10/11・10/07）なので:

        長尺こみ（旧）  16本目 10/11・10/07 → 判定 **10-17**
                        → 門が「**`deadline: "2026-10-17"` へ延ばすこと**」と印字
        長尺を落とす    16本目 09/13・09/17 → 判定 **09-23**（期限 09-24 の**内側**）

    **`eta.py` の到達日が動くのは前提を1件 閉じたときだけ**なので、
    あの `[!!]` に従った回は、**期限を 23日 後ろへ送っていました。**
    処置の入っていない3本が、軌跡から 24日 を持って行っていた形です。

    ### 覆る条件

    - `eligible` を持たない実験（いまは `title_form` / `hook_form` /
      `stat_split` / `opening_motion`）は、**1本も落ちません**（`None` で素通り）。
      あれらが長尺を含むべきかは、**この回では測っていません** ——
      含むべきでないと分かったら、`ab_split` 側に `eligible` を足すこと。
      **ここに条件を書き足さないこと**（それが上の「2か所」を作ります）
    - `judgeable.shorts_only()` は**宣言ではなく標本**からこれを見ます。
      あれが `slide_pace` を返さない回があれば、この門が効いていません
    """
    from src import ab_split as ab_split_mod
    from src.ab_split import EXPERIMENTS

    exp = EXPERIMENTS[name]
    builds, pub, vid = build_times(), _publish_by_topic(), _video_by_topic()
    allowed = exp.eligible() if exp.eligible is not None else None
    out: dict[str, list[Member]] = {exp.treated: [], exp.control: []}
    for topic, built in builds.items():
        if built < exp.landed:
            continue  # 指示が入る前に作った本。IDが何と言おうと処置は入っていない
        if allowed is not None and topic not in allowed:
            continue  # 処置がそもそも掛からない本（長尺など）。上の docstring
        # **凍らせた名札が勝ちます**（`ab_split.group_of` に実測と理由 ——
        # `SLOW_PACE_SHARE = 0` の1行で、処置群 7本 が丸ごと消えます）。
        group = ab_split_mod.group_of(exp, topic)
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
    from src import ab_split as ab_split_mod
    from src.ab_split import EXPERIMENTS

    exp = EXPERIMENTS["request_form"]
    builds, pub, vid = build_times(), _publish_by_topic(), _video_by_topic()
    shorts = _short_topics()
    out: dict[str, list[Member]] = {exp.treated: [], exp.control: []}
    for topic, built in builds.items():
        if built < exp.landed or topic not in shorts:
            continue
        day = pub.get(topic)
        # **ここも凍らせた名札を通すこと**（2026-08-28）。
        # `_members_by_split()` だけを通しても、`request_form` はこの関数から
        # 群を作るので素通りします —— **同じ問いを解く関数が2本あって、
        # 片方だけ直っている**形（この repo でくり返し出ている形）。
        # 実測: `_members_by_split` だけ直した時点で、`MID_REQUEST_SHARE = 0` は
        # `slide_pace` を守れて `request_form` は **途中あり 23 → 0** でした。
        group = ab_split_mod.group_of(exp, topic)
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
    """`YT_OPENING_MOTION` の値で割る（`src/motion_groups.py` が実物から引きます）。

    ## **共有日だけを数えます**（2026-08-27 に直した。**同じ穴の4件目**）

    ここは長らく `motion_groups.groups()`（**生の合計**）を読んでいました。
    ところが `falsified_if` は「**動きありと同じ日に交互で予約する**」と言っており、
    **片方しか居ない日の本は使えません**（動きの差と、その日の配信の差を
    分けられない —— 1日に配信されるのは 10本ちょうど・`src/day_cap.py`）。
    `motion_groups.paired()` の docstring が同じことを3件ぶん書いています。

    **食い違いは、期限の側に出ていました**（2026-08-27 の実測）:

        `deadline_check.py`（ここ・生の合計）        判定できるのは **09/21**
        `tests/test_hypothesis_deadline_reachable`   判定できるのは **09/26**
                                                     （`earliest_opening_motion`＝共有日）

    **どの期限を書いても、必ずどちらかの検査が赤くなる状態**でした
    （09/21 なら「まだ判定できない」、09/26 なら「データは揃うのに期限が先」）。
    `test_遅すぎる期限が残っていないこと` の docstring が
    「**期限を意図して先に置きたいなら `needs` に書くこと**」と言っているとおり、
    直すのは日付ではなく**数え方**のほうです。

    **覆る条件**: `falsified_if` から「同じ日に交互」が外れたら、`groups()` に戻すこと
    （そのときは片方しか居ない日の本も標本になります）。
    """
    from src import motion_groups

    off, on = motion_groups.paired(*motion_groups.groups())
    pub = _publish_by_video()
    return {
        "対照(動きなし)": sorted((d, v) for v in off if (d := pub.get(v))),
        "処置(動きあり)": sorted((d, v) for v in on if (d := pub.get(v))),
    }


def _stockpiled_ids() -> set[str]:
    """**規則2 で1本も公開されない本の `video_id`**。読めなければ空（＝落とさない）。

    札は `src/ab_split.published()` が `house_rule.is_stockpile()` で付けています。
    **ここで判定を書き直さないこと** —— 条件（未公開 かつ 規則より前に作った）は
    `src/house_rule.is_stockpile()` の1か所です。

    読めない回は空集合を返し、**1本も落としません。**
    「測っていないことを、落とす側に倒さないこと」——
    控えが読めないだけで群が空になると、`ready` が消えて期限が壊れます
    （`_live_ids()` が `None` で絞らないのと同じ姿勢）。
    """
    try:
        from src.ab_split import published                 # noqa: PLC0415

        return {str(r["video_id"]) for r in published()
                if r.get("stockpile") and r.get("video_id")}
    except Exception:                                       # noqa: BLE001
        return set()


def _days(rows: dict[str, list[Member]]) -> dict[str, list[date]]:
    """群べつの本 → 群べつの公開日（昇順）。**`Floor` が要るのはこちらだけ。**

    **ここでは1本も落としません。畳むだけです。**
    `SOURCES` はこれで `members()` を畳んだものなので、**畳む側で員数を変えると
    `SOURCES` と `members()` が別の群を見ます**（`tests/test_live_slots.py::
    test_群の作り方は1か所`）。**絞りは `members()` の側に置くこと。**

    ## **作り置きの予約は、床に数えません**（2026-08-31 に足した。オーナー規則2）
    ##  —— **その絞りは `members()` へ移しました**（上の理由）。以下は経緯です。

    `Floor.ready` は「片群 N本 が**予約に**そろって初めて日が出る」形です。
    ところが規則2（原文「**作り置きはなしにして**」「**使わなければ良いだけ
    前提にも再利用もしない**」）の下では、**規則より前に作った未公開の予約は
    1本も公開されません。** 実測 2026-08-31: 未来の予約 294本 のうち **293本**
    が作り置きでした。

    **数えると、来ない本で期限が守れていることになります。** 実測（塞ぐ前）::

        hook_form  問い  予約 21本（うち作り置き 10本）→ 16本目 **09/23**
                         → ready **09-30**・期限 09-30 → **`[OK]` と印字**
                   実物  公開される見込みの本は **11本**（床 16本）→ **そろいません**

    `scripts/deadline_check.py` はこれを `[OK] 09-30 …に出ます` と出し、
    `scripts/eta.py` は「軌跡の腕が動くのは前提を1件 閉じたときだけ」と
    印字しているので、**閉じられない前提が「閉じられる」側に並びます。**
    さらに `scripts/queue_lag.py --plan` の「並び替えだけで 11日 手前へ倒せる」も
    **同じ 10本の上に乗っていました。**

    ## **`members()` の側では落としません**

    落とすのはここ（`Floor` が読む公開日）だけです。`members()` と
    `ab_split.published()` は `scripts/queue_lag.py` も読んでおり、
    あちらは**予約の実物**（何本目か・入れ替え先）が要ります
    （`published()` の「札を付けるだけです」の節）。

    **覆る条件**: オーナーが規則2 を外したら `house_rule.STOCKPILE_IS_SUPPLY`
    が `True` になり、`is_stockpile()` が全件 `False` を返すので、
    ここは自動で素通りになります（**この関数に条件を書き足さないこと**）。
    """
    return {g: sorted(d for d, _ in ms) for g, ms in rows.items()}


#: yaml の `key:` → (**群べつの本**を作る関数, 片群あたりの必要本数)
def short_share(days: int = 30) -> tuple[int, int] | None:
    """直近に作った本のうち、**ショートだったもの**（実測。返り `(ショート数, 数えた数)`）。

    **べた書きしないこと。** 長尺の比率は回ごとに動きます（実測 2026-08-27 は 9%）。
    数が少なすぎる回は `None` —— 引きの偏りで反対を言うので、言わないほうが安全です。

    ここに置いてあるのは、`_short_topics()` と `build_times()` が
    **この1か所にしか無い**からです（`tests/test_queue_lag.py` の
    「群の作り方を、この道具の中で持ち直していない」が門）。
    """
    builds = build_times()
    if not builds:
        return None
    shorts = _short_topics()
    known = set(_video_by_topic())
    newest = max(builds.values())
    cut = newest - timedelta(days=days)
    rec = [t for t, b in builds.items() if b >= cut and t in known]
    if len(rec) < 8:
        return None
    return sum(1 for t in rec if t in shorts), len(rec)


def starved_share(keys: list[str]) -> tuple[int, int] | None:
    """**その実験が入った後に作ったショートのうち、実際に群へ入った割合**（実測）。

    返り `(入った本数, 数えた本数)`。標本 8本 未満なら `None`。

    ## なぜ要るか（2026-08-29・最適化の回。**別の数を証拠にしていました**）

    `scripts/queue_lag.py` は
    「**これから作るショートは、足りない群に自動で入ります**（直近の実測 87%）」
    と印字していました。**その 87% は `short_share()`** ——
    「直近30日に作った本のうち、**ショートだった**割合」です。
    **文と数が別のことを言っています**（片方は「群に入るか」、
    もう片方は「ショートか長尺か」）。

    実測 2026-08-29 —— 同じ日に3つの数が出ます:

        87%   `short_share()`             作った本のうち ショートだった割合
        13%   直近30日のショートのうち、いま足りない群に入っているもの
        100%  **実験が入った後**に作ったショートのうち、群に入ったもの ← これ

    **13% は不当に低い**（30日の窓のうち 28日ぶんは実験が入る前に作った本で、
    `_members_by_request_form()` の `built < exp.landed` で必ず落ちます）。
    **87% は無関係。** 文が言っているのは3つ目で、それは **100%** です ——
    `request_form` 58/58本・`slide_pace` 24/24本。

    **証拠のほうが結論より弱かった**わけです。結論（「作り続ける」）は正しく、
    弱い数を並べたせいで**「87% しか入らない」と読める**形でした。

    ## **規則の下で起きえない落ち方を、分母に置かないこと**（2026-08-31・最適化の回）

    同じ日の 12:56 と 13:33 に `members()` が2つ絞りを足しました ——
    **作り置き**（規則2 の下では1本も公開されない予約）と、
    **帯の外の本**（`day_cap`。1日10本超・30分より詰めた本は 0再生）。
    **正しい直しです。** ただし絞ったのは `members()` だけで、
    **この関数の分母はそのまま**でした。落ちた本は全部「群に入らなかった」側に
    数えられ、上の 100% が **35.5%（100/282本）** に落ちています。

    実測 2026-08-31（この節を足す前）:

        title_form    40/111   外れ 71本 ＝ 作り置き 42 ／ 帯の外 29
        hook_form     29/ 95   外れ 66本 ＝ 作り置き 37 ／ 帯の外 29
        request_form  22/ 54   外れ 32本 ＝ 作り置き 17 ／ 帯の外 15
        slide_pace     9/ 22   外れ 13本 ＝ 作り置き  6 ／ 帯の外  7

    **外れ 182本 は1本残らず、この2つのどちらかです。**
    どちらも**規則（1日1本・作り置きなし）の下では二度と起きません** ——
    作り置きは公開されず、1本/日 は `day_cap` の 10本 を超えようがない。
    つまり 35.5% は「**これから作る本が群に入る率**」ではなく、
    「**規則より前に作った本のうち、規則が公開を取り消したぶんを引いた率**」です。

    **害は `scripts/queue_lag.py` に出ていました。** あちらは要る本数を
    この率で割ります（124本 ÷ 0.355 ＝ 354日）。その結果:

        queue_lag   間に合わない前提 3件 —— request_form 超過219日 /
                    slide_pace 40日 / hook_form 11日
        ab_split    同じ3件とも **間に合います**（122本／139日・23本／36日・…）
                    構造的に届かないのは **`slot_half` 1件だけ**（29本 足りません）

    **同じ与件から、2つの道具が反対を印字していました。** そして queue_lag が
    名指しする直し方は「**期限を延ばす**か**群を畳む**」——
    元気な前提3件をそのどちらかにかけ、**本当に届かない1件は見逃す**形です。
    `eta.py` は「軌跡の腕が動くのは前提を1件 閉じたときだけ」・
    「今後60日 の θ は**台帳が 23件 しか無いのが天井**」と印字するので、
    **台帳を誤って 3件 削ることは、そのまま到達日の側に効きます。**

    ## 覆る条件

    振り分けが「テーマIDだけを見る純関数」でなくなったら、この 100% は割れます
    （`src/script_writer.request_form` / `src/pipeline.slide_pace`）。
    そのときこの関数がそのまま下がって教えます —— **写さずに毎回 撃つこと。**
    `tests/test_starved_share.py` が「入った後の本だけを数える」ことを留めています。
    """
    from src.ab_split import EXPERIMENTS

    builds, shorts = build_times(), _short_topics()
    vid = _video_by_topic()
    # **`members()` が構造で落とす本は、分母にも置かないこと**（2026-08-31）。
    # 理由は上の「規則の下で起きえない落ち方」の節。ここは同じ2つの口を使います
    # （**群の作り方は1か所** ——`members()` の本文と同じ `_stockpiled_ids()` /
    # `_live_ids()`。片方に条件を書き足したら、もう片方も同じ日に直すこと）。
    drop = _stockpiled_ids()
    keep = _live_ids()
    hit = seen = 0
    for key in keys:
        exp = EXPERIMENTS.get(key)
        if exp is None:
            continue
        try:
            ms = members(key)
        except Exception:                                        # noqa: BLE001
            continue
        joined = {v for g in ms.values() for _d, v in g}
        for topic, built in builds.items():
            # **実験が入った後に作ったショートだけ**を分母に置くこと。
            # 前に作った本は、群に入りようがありません（`built < exp.landed`）。
            if built < exp.landed or topic not in shorts or topic not in vid:
                continue
            video = vid[topic]
            if video in drop:
                continue        # 作り置き ——規則2 の下で1本も公開されません
            if keep is not None and video not in keep:
                continue        # 帯の外（`day_cap`）——1本/日 では起きません
            seen += 1
            if video in joined:
                hit += 1
    return (hit, seen) if seen >= 8 else None


def shorts_only(keys: list[str]) -> list[str]:
    """その前提が**ショートだけ**を数えているか。**宣言を写さず、標本から見ます。**

    `_members_by_request_form()` の「長尺は群に入らない」を別の道具へ書き写すと、
    **片方が腐ります**（この repo で6回 起きた形。
    `docs/JOURNAL.md` 2026-08-27「1つの定数を全部に当てて、註に同じ数が出ると書いた」）。
    だから**いまの群の中身**を見て、全部ショートなら「ショートだけ」と読みます。

    **標本 8本 未満では言いません**（引きの偏りで反対を言います）。
    """
    shorts = _short_topics()
    topic_by_vid = {v: t for t, v in _video_by_topic().items() if v}
    out: list[str] = []
    for key in keys:
        try:
            ms = members(key)
        except Exception:                                        # noqa: BLE001
            continue
        ts = [topic_by_vid.get(v) for g in ms.values() for _d, v in g]
        ts = [t for t in ts if t]
        if len(ts) >= 8 and all(t in shorts for t in ts):
            out.append(key)
    return out


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
    # ショートの刻み（1コマの秒数）を 2.5 と 4.5 に振り分ける
    # （`src/pipeline.slide_pace`・2026-08-27 オーナー指摘）。
    # **測るのは engaged** なので、床は `MIN_PER_GROUP` のまま
    # （`request_form` の 72本 は登録を測るためで、ここには当たりません）。
    # **長尺は `reveal_variants` を1度も通らない**ので、群はショートだけです
    # （`ab_split` 側の `eligible=_shorts_only`）。
    "slide_pace": (lambda: _members_by_split("slide_pace"), MIN_PER_GROUP),
    # 帯の中の枠を、早い側／遅い側へ振り分ける
    # （`src/ab_split.slot_half`・`scripts/batch_build._ab_slot_order`）。
    # **測るのは1本あたり再生**ですが、床は `MIN_PER_GROUP` のまま ——
    # `request_form` の 72本 は**登録**（3,066再生に1人）を見分けるための数で、
    # 再生そのものを比べるここには当たりません。
    # **長尺は帯を1枠も使いません**（置き先は `_long_ring()` の 18〜22時）ので、
    # 群はショートだけです（`ab_split` 側の `eligible=_shorts_only`）。
    "slot_half": (lambda: _members_by_split("slot_half"), MIN_PER_GROUP),
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
#:
#: **`slide_pace` も同じ形です**（2026-08-27）—— 振り分けが入ったのは 21:30 JST で、
#: **予約に入っている本は全部それより前に作られています**（両群 0本 / 床 16本）。
#: `Floor.ready` は「片群 N本 が**予約に**そろって初めて日が出る」形なので、
#: ここに入れないと `test_実物で期限が構造的に守れる` が**赤で居座ります**。
#: **群の数え方は捨てません** —— `members("slide_pace")` はそのまま使えます。
#: **積み終わったらここから外すこと**（`needs` を `kind: group_key` のまま戻せば、
#: `Floor` の側で期限が守れるか見張られます）。
#: **`hook_form` は 2026-08-31 にここへ入りました**（オーナー規則2）。
#:
#: 問いの群は**予約 21本 で床 16本 を満たしていました** —— ところが 21本 のうち
#: **10本 は作り置き**で、規則2 の下では1本も公開されません（`_days()` の節）。
#: 公開される見込みは **11本**。**これから積む群**に変わったということです。
#:
#: `Floor.ready` は「予約にそろって初めて日が出る」形なので、ここに入れないと
#: `test_実物で期限が構造的に守れる` が**赤で居座ります**（上の2件と同じ形）。
#: `needs` に `since: 2026-08-19`（`ASK_HOOK_RULE` が入った日）を足したので、
#: `scripts/deadline_check.py` が**規則で押さえた伸び率**から 16本目を推定します。
#:
#: **覆る条件**: 規則の下で作った本が積み上がって問いの群が 16本 に届いたら、
#: ここから外すこと（`Floor` の側で期限が守れるか見張られます）。
ACCRUING: set[str] = {"request_form", "slide_pace", "slot_half", "hook_form"}

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

    **【2026-08-31】出どころを `src/ab_split.live_video_ids()` の1か所にしました。**
    ここと `ab_split.split_counts()` が**別々に数えていた**のが、同じ実験について
    2つの本数（`judgeable` は「まだ足りない」／`ab_split` は「判定できます」）を
    出していた理由です。**同じ絞りを2か所に書かないこと。**
    """
    try:
        from src.ab_split import live_video_ids

        return live_video_ids()
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

    ## **1本も公開されない本も、標本として数えません**（2026-08-31・オーナー規則2）

    上と同じ理由の、もう一段 手前の話です。**0再生の本**を落とすなら、
    **そもそも公開されない本**はなおさら落ちます —— 規則2
    （原文「**作り置きはなしにして**」「**使わなければ良いだけ 前提にも再利用もしない**」）
    の下では、規則より前に作った未公開の予約は**永久に公開されません。**

    実測 2026-08-31: `data/uploaded.jsonl` の未来の予約 **294本 のうち 293本**。
    塞ぐ前に実際に出ていた害::

        hook_form 問い  予約 21本（うち作り置き 10本）→ 16本目 09/23 → ready 09-30
                        → `scripts/deadline_check.py` は `[OK]` と印字
                  実物  公開される見込み 11本（床 16本）＝ **そろわない**

    `scripts/eta.py` は「軌跡の腕が動くのは前提を1件 閉じたときだけ」と印字するので、
    **閉じられない前提が「閉じられる」側に並ぶと、到達日はそこで止まります。**

    ### **落とすのは `_days()` ではなく、ここです**

    最初 `_days()`（`Floor` が読む口）だけで落としました。**`tests/test_live_slots.py::
    test_群の作り方は1か所` が赤くして、そちらが誤りだと教えました** ——
    `SOURCES` は `members()` を畳んだものなので、畳む側で員数を変えると
    **`SOURCES` と `members()` が別の群を見ます**（実測 title_form 23/19 対 41/43）。
    **群の作り方は1か所**。だから絞りもここに置きます（`_live_ids()` の隣）。

    **覆る条件**: オーナーが規則2 を外したら `house_rule.STOCKPILE_IS_SUPPLY` が
    `True` になり、`is_stockpile()` が全件 `False` を返すので、ここは自動で
    素通りになります（**この関数に条件を書き足さないこと**）。
    """
    make, _ = MEMBER_SOURCES[key]
    rows = make()
    drop = _stockpiled_ids()
    if drop:
        rows = {g: [(d, v) for d, v in ms if v not in drop] for g, ms in rows.items()}
    keep = _live_ids()
    if keep is None:
        return rows
    return {g: [(d, v) for d, v in ms if v in keep] for g, ms in rows.items()}


def _hypotheses() -> list[dict]:
    doc = yaml.safe_load(HYPOTHESES.read_text(encoding="utf-8")) or {}
    return list(doc.get("hypotheses") or [])


def deadlines() -> dict[str, date]:
    """yaml の群の key → 期限（**閉じた前提は返しません**）。

    ## **`needs:` の側の `key:` も拾います**（2026-08-27 に測って足した）

    ここは長らく**前提の直下の `key:` だけ**を読んでいました。ところが
    `request_form`（腕 `sub_rate`）は、直下に `key:` を**わざと付けていません** ——
    yaml のその行に理由が書いてあります（「立てた時点で両群 0本・床 72本 なので、
    `key:` を付けると `tests/test_judgeable.py` がそろうまで赤で居座る」）。
    群そのものは `needs: [{kind: group_key, key: request_form}]` に在ります。

    **その置き場所の都合が、群の一覧ごと消していました。** 実測 2026-08-27:
    `deadlines()` は4件を返し、`request_form` だけが落ちていました。
    落ちた1件は **`eta.py` が「凍らせると軌跡は +118日」と言う唯一の腕**の、
    ただ1つの走っている実験で、**床がいちばん遠い**（片群 72本 に対し 9本/7本）。
    **いちばん足りない群が、群の一覧から消えていた**ということです。

    **`floors()` は1件も変わりません** —— あちらは `SOURCES` を回り、
    `request_form` は `ACCRUING` で最初から外れています（実測で確認済み。
    `tests/test_judgeable.py::test_実物で期限が構造的に守れる` は緑のまま）。
    変わるのは「**群の一覧を訊く側**」（`scripts/queue_lag.py` の枠の節）だけです。

    **覆る条件**: `request_form` の群がそろって `ACCRUING` から外れ、
    yaml の直下に `key:` が戻ったら、この二重読みは要りません。
    """
    out: dict[str, date] = {}
    for h in _hypotheses():
        if h.get("closed_on"):
            continue
        raw = h.get("deadline")
        if not raw:
            continue
        when = raw if isinstance(raw, date) else date.fromisoformat(str(raw))
        keys = [str(h["key"])] if h.get("key") else []
        for need in (h.get("needs") or []):
            if isinstance(need, dict) and need.get("kind") == "group_key" and need.get("key"):
                keys.append(str(need["key"]))
        for key in keys:
            out.setdefault(key, when)
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
