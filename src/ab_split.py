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

from src import ab_power
from src.settle import SETTLE_DAYS  # noqa: F401  （**ここでは定義しません**。下の註）
from src.script_writer import hook_form, request_form, title_form

ROOT = Path(__file__).resolve().parent.parent
BATCH = ROOT / "data" / "batch_runs.jsonl"
LEDGER = ROOT / "data" / "uploaded.jsonl"

JST = timezone(timedelta(hours=9))

#: 判定に要る、**片群あたりの本数**。`config/hypotheses.yaml` の
#: 「どちらの群も 16本に満たなければ判定しない」と同じ数。**ここだけで持たないこと** ——
#: 数を変えるなら yaml も同時に変える（`tests/test_ab_split.py` が突き合わせています）。
#:
#: **8 → 16 に上げました（2026-08-20 05:2x）。** 緩めたのでも厳しくしたのでもなく、
#: **8本では狙っている差が見分けられない**ことを実データで測ったからです
#: （`src/ab_power.py`。順位和を足した規則で、1.3倍を当てる率が 8本 64% → 16本 76%）。
#: **80% に届かせるには片群 32本**要りますが、そこは在庫が尽きます —— だから
#: yaml の「満たないときは**期限だけを延ばす**」のほうを使うこと。
MIN_PER_GROUP = 16


def floor_of(name: str) -> int:
    """その実験の、**片群あたりの床**。`MIN_PER_GROUP` を全部に当てないこと。

    ## なぜ要るか（2026-08-27 に踏んだ。**同じ形の3件目**）

    床は実験ごとに違います。**`request_form` は 72本**です ——
    測っているのが engaged ではなく**登録**だから（登録率の実測 0.0318% ＝
    3,066再生に1人。片群 16本 ＝ 約 6,700再生 では期待 2.1人で、
    **効きが2倍でも見分けられません**）。理由ごと
    `src/judgeable.MEMBER_SOURCES` に書いてあります。

    ところが**この帳面の道具は、全部に 16 を当てていました。** 実測（この回）:

        scripts/ab_split.py    途中あり 12本 → **まだ判定しない（あと4本）**
        deadline_check.py      途中あり  9本 → **あと 63本**（床 72）

    **`config/hypotheses.yaml` の `falsified_if` は、数える道具として
    `scripts/ab_split.py` を名指ししています。** その道具が「あと4本」と言えば、
    次の回は「もう埋まる」と読んで別の腕へ移ります —— **6,700再生で登録率を
    比べる標本のまま「判定できます」が出て、`falsified_if` は
    「上回らなければ外れ（同点も外れ）」なので、そのまま『外れ』に化けます。**
    `next_if_false` は腕ごと畳むので、**見分けられなかっただけの実験が、
    効かない実験として閉じます。**

    **同じ穴は `src/watches.py` が 2026-08-26 22:5x に踏んで直しています**
    （`_k_ab_group`。「`ab_split.MIN_PER_GROUP` を床に使わないこと」）。
    **直したのはあちらの1か所だけで、こちらは残っていました。**

    ## 覆る条件

    `judgeable.MEMBER_SOURCES` に無い実験は `MIN_PER_GROUP` に落とします。
    そこへ載せた回は、床もそちらに書くこと（**同じ数を2箇所で持たない**）。
    """
    # **遅らせて読み込みます** —— `src/judgeable.py` はこの帳面を読み込むので、
    # 上で import すると輪になります。
    from src import judgeable

    src = judgeable.MEMBER_SOURCES.get(name)
    return int(src[1]) if src else MIN_PER_GROUP

#: 「初速だけを見ない」ための日数は **`src/settle.py` が持ちます**（上で読み込み済み）。
#: yaml の「公開から3日以上たっていること」と同じ数で、`tests/test_ab_split.py` が
#: 突き合わせています。
#:
#: **ここに数を書かないこと（2026-08-26）。** 元は `SETTLE_DAYS = 7` という**勘**が
#: この行にあり、`scripts/eta.py` の `MATURE_HOURS = 48`（実測つき）と、
#: `config/hypotheses.yaml` が 2026-08-21 に測って書き換えた「24時間」と、
#: **同じ量について3つの数が別々に立っていました。** 判定の門が読むのはこの行だけ
#: だったので、**すべての前提の判定日が 4日 遠いまま**でした。実測は `src/settle.py`。


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
    #: **この実験が比べている値**（2026-08-27 に足した。既定は `"engaged"`）。
    #:
    #: `src/ab_power.py` の当てっこは、**実データ 90本の engaged 比率**を
    #: ブートストラップして作っています。**engaged で測っていない実験に
    #: 当てると、要る本数が嘘になります。**
    #:
    #: 実測 2026-08-27 —— `request_form`（測るのは**登録**）の出力::
    #:
    #:     片群 72本で 1.3倍は当てられます（**要る本数は 25本**）
    #:
    #: 床 72本 は `judgeable.MEMBER_SOURCES` が**登録率 0.0318%**（3,066再生に
    #: 1人）から引いた数です。engaged の当てっこが出す 25本 は
    #: **約 10,500再生 ＝ 期待 3.3人** で、効きが2倍でも見分けられません。
    #: そして `falsified_if` は「上回らなければ外れ（同点も外れ）」、
    #: `next_if_false` は**腕ごと畳みます** —— つまりこの1行は、
    #: **`--alloc` が3回 続けて名指ししている `sub_rate` の腕を、
    #: 見分けられなかっただけで畳ませる形**で置かれていました。
    #: `src/ab_split.floor_of()` が2026-08-27 に直したのと**同じ穴の4件目**です。
    metric: str = "engaged"
    #: **この実験に入れてよいテーマID**を返す関数（`None` なら全部）。
    #: 2026-08-27 に足した。理由は下の `_shorts_only()`。
    eligible: Callable[[], set[str]] | None = None


def _shorts_only() -> set[str]:
    """**ショートとして出したテーマIDだけ**（控えの `duration_s` で 3分以下）。

    ## なぜ要るか（2026-08-27 に測って足した。**同じ穴の5件目**）

    `request_form` の A/B は「**ショートの登録の依頼**を途中にも入れるか」です。
    長尺は依頼そのものを1文字も書きません（`src/script_writer.ROLE`）——
    **どちらの群にも入れてはいけない本**です。

    ところが `Experiment.split`（＝ `script_writer.request_form()`）は
    **テーマIDのハッシュだけ**を見ており、長尺にも `途中あり` / `終端のみ` を返します。
    `src/ab_split.py` のこの行のすぐ上には長らく

        **長尺は `request_form` が `"長尺"` を返し、どちらの群にも入りません。**

    と書いてありましたが、**そんな枝は関数にありません**（2026-08-27 に実物を読んだ）。
    註だけが正しく、実装が黙って長尺を数えていました。

    実測（同じ日・同じ枝・API 0単位）::

        split_counts   途中あり **17本** ／ 終端のみ **20本**
        judgeable      途中あり   14本  ／ 終端のみ   16本

    差の 7本 は全部 長尺でした（`duration_s` 298〜442秒）::

        jutaku-mochibun-13nen-389546     keihi-kokuho-zero-ryoutan
        keihi-zero-taiki-1080000         jouto-kyouyu-mochibun-852600
        jutaku-kuriage-tadade-11600000   keihi-keihi-vs-kojo-22500
        keihi-kokuho-hihokensha-195280

    **`judgeable` のほうが正しい。** `src/judgeable._members_by_request_form()` は
    控えの `duration_s` で長尺を落としています。**負けたほうを消すのがこの関数**です
    —— 数え方を2つ並べて残すと、次の回がまた両方読みます
    （`src/watches.py` が 2026-08-26 に同じ結論を出しています:
    「`MEMBER_SOURCES` に在る群は、床も数え方もそちらに訊くこと」）。

    ## なぜ「数えない」であって「stale」ではないか

    `stale` は「**指示より前に作ったのにこの群にいる本**」で、作り直せば処置群に入ります。
    長尺は作り直しても**永久に依頼を書きません**。混ぜると
    「あと N本」の N が実際より小さく見え、**床に届く前に判定できると読みます** ——
    `falsified_if` は「上回らなければ外れ（同点も外れ）」で、`next_if_false` は
    腕ごと畳むので、**見分けられなかっただけの実験が、効かない実験として閉じます**
    （`floor_of()` の註と同じ壊れ方です）。

    ## 覆る条件

    長尺にも依頼を書くようになったら（`src/script_writer.ROLE` を変えたら）、
    この絞り込みを外すこと。**そのときは `judgeable._short_topics()` の側も同時に。**
    """
    # **遅らせて読み込みます** —— `src/judgeable.py` はこの帳面を読み込むので、
    # 上で import すると輪になります（`floor_of()` と同じ）。
    from src import judgeable

    return judgeable._short_topics()


def _deadline_from_yaml(name: str, fallback: date) -> date:
    """**期限は `config/hypotheses.yaml` が正本**（2026-08-25 22:5x）。

    ここは長らく `date(2026, 9, 12)` のような**べた書き**でした。
    `tests/test_ab_split.py::test_期限は_yaml_と同じ` が
    「**`deadline` を2か所で持っているので、ずれたら止める**」と書いて
    見張っていましたが、**見張るだけでは同期しません** ——
    実際 2026-08-25 に、`deadline_check.py` の `ready` まで期限を縮めた回で
    **2件ともずれて落ちました**（title_form 09-12→09-09・hook_form 09-16→09-14）。

    **そして期限を縮めるのは、これから毎回起きます**（`status.py` が
    「期限が遅すぎる N件」を毎回出して縮めさせる）。**べた書きのままだと、
    縮めるたびにここが落ちます。** だから写しをやめて、**引く**ようにしました。

    紐づけの鍵は `falsified_if` の中の `script_writer.<name>` です
    （その前提が、この振り分けを名指ししている所）。

    **見つからなければ `fallback` に落ちます。** ここで例外を上げると、
    `status.py` ごと止まって**投稿が止まります** ——
    `CLAUDE.md`「投稿を途切れさせないこと」。ずれたことは検査が言います。
    """
    try:
        import yaml
        doc = yaml.safe_load(
            (ROOT / "config" / "hypotheses.yaml").read_text(encoding="utf-8"))
        hit = [h for h in (doc.get("hypotheses") or [])
               if f"script_writer.{name}" in str(h.get("falsified_if", ""))
               and not h.get("closed_on")]
        if len(hit) == 1:
            d = hit[0].get("deadline")
            if isinstance(d, date):
                return d
            if isinstance(d, str):
                return date.fromisoformat(d)
    except Exception:
        pass
    return fallback


#: 走っている実験。**新しく振り分けを足したら、ここにも足すこと。**
#: 足し忘れると `status.py` が「指示が入った本 0本」を言わないまま、
#: 中身の同じ2群を突き合わせて外れを出します。
#:
#: **`deadline` は書きません。`config/hypotheses.yaml` から引きます**
#: （上の `_deadline_from_yaml`）。下の日付は**その前提が消えたときの受け皿**で、
#: 正本ではありません。
EXPERIMENTS: dict[str, Experiment] = {
    "title_form": Experiment(
        name="title_form",
        split=title_form,
        treated="問い",
        control="断定",
        # 6a7520f「道具は『無関係』でなく『一度も試していない』と言っていた」
        landed=datetime(2026, 8, 19, 16, 50, 5, tzinfo=JST),
        deadline=_deadline_from_yaml("title_form", date(2026, 9, 12)),
        commit="6a7520f",
    ),
    "hook_form": Experiment(
        name="hook_form",
        split=hook_form,
        treated="問い",
        control="条件",
        # 443c66b「冒頭1枚目の主役（kind=stat の note）を問いかけに振り分ける A/B」
        landed=datetime(2026, 8, 19, 21, 0, 3, tzinfo=JST),
        deadline=_deadline_from_yaml("hook_form", date(2026, 9, 16)),
        commit="443c66b",
    ),
    "request_form": Experiment(
        name="request_form",
        split=request_form,
        treated="途中あり",
        control="終端のみ",
        # **長尺を落とすのは `eligible` です**（下の行）。2026-08-27 まで、ここには
        # 「長尺は `request_form` が `"長尺"` を返し、どちらの群にも入りません」と
        # 書いてありました。**そんな枝は関数にありません** —— 註だけが正しく、
        # 実装は長尺を 7本 数えていました（`_shorts_only()` に実測）。
        # 2026-08-26 19:08 JST に `MID_REQUEST_RULE` が `generate()` に入った。
        # **未来の時刻を書かないこと** —— この行より前に作った本は全部 落ちるので、
        # 書いた回が自分で作った本まで落とします（この行を最初 20:15 と書いて踏みかけた）。
        landed=datetime(2026, 8, 26, 19, 8, 0, tzinfo=JST),
        deadline=_deadline_from_yaml("request_form", date(2026, 11, 9)),
        commit="",
        # **登録で測ります**（engaged ではない）。上の `metric` の註を読むこと。
        metric="登録",
        # **長尺は依頼を1文字も書かないので、どちらの群にも入れません**（`_shorts_only()`）。
        eligible=_shorts_only,
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


def landed_groups(landed: datetime, builds: dict[str, datetime] | None = None,
                  ) -> tuple[list[str], list[str]]:
    """**時刻で入った作りの変更**を、`(変更前に作った本, 変更後に作った本)` に割る。

    返すのはテーマID。**公開日ではなく、作った時刻で割ります。**

    ## `EXPERIMENTS` と何が違うか

    上の `EXPERIMENTS` は **IDで2群に振り分ける A/B**（題を問いにするか断定にするか）で、
    `landed` は「その振り分けが実装に入る前の本を落とす」ために使います。
    こちらは**振り分けの無い変更** —— 入った後に作る本は**全部**そうなる、という形です
    （冒頭の stat の割り方・冒頭0.9秒の動き・描画の作り替えなど）。
    **群そのものが「入る前か後か」**なので、`split` は要りません。

    ## **公開日で割らないこと**（2026-08-25 に実測。同じ形で4回踏んでいます）

    **作ってから公開されるまでの間隔が伸び続けています。**

        8/16 に公開した本   作ってから **0.9日**
        8/21                          **2.2日**
        8/24                          **7.5日**
        いま（予約 443本）  中央値 **13.4日**・最大 40.2日

    だから「変更が入った日より後に**公開**された本」は、その大半が
    **入る前に作られた本**です。実測 —— `config/hypotheses.yaml` の
    「冒頭の stat は前提を先・数字を後」（期限 09/05）は、条件が
    「8/23 以降に**公開**されるもの」と書いてありました:

        条件が言う『処置群』 350本 …… **実際に新しい割り方で作った本は 21本（6.0%）**
        残り 329本（94.0%）は、**処置が入っていない本**

    処置が 6% しか入っていない群を対照と比べれば、差は出ません。
    条件は「上回らなければ外れ」なので、**測る前から「外れ」が確定**していました
    （8/23 に「冒頭0.9秒の動き」で直したのと**同じ形**です）。

    **在庫が数週間先まで予約されているかぎり、公開日は群を表しません。**
    """
    builds = build_times() if builds is None else builds
    before: list[str] = []
    after: list[str] = []
    for topic, at in builds.items():
        (after if at >= landed else before).append(topic)
    return sorted(before), sorted(after)


def published(path: Path | None = None) -> list[dict[str, object]]:
    """控えの1本1件。`topic` と **公開日（JST）** だけ取り出す。

    `at` が無い行（実測 44/491）は**公開日が分からない**ので `publish=None` で返し、
    `split_counts` が `unknown_publish` に数えます。

    ## **1行1件ではなく、1本1件**（2026-08-25 に実測。ここが2つ壊れていました）

    `uploaded.jsonl` は**足すだけの帳面**です。`scripts/reschedule.py` が
    公開時刻を動かすと、**同じ `video_id` の行がもう1行足されます。**
    実測 **505行 / 実物 491本** —— 14本が2つの `at` を持っていました。

    素直に1行1件で返すと、**動かした本だけが両群のどちらかで2回数えられます。**
    `split_counts` は `treated_ready` をそのまま `MIN_PER_GROUP` に当てるので、
    **15本しか無い群が「16本そろった」と言い、判定が始まります。**
    群の分母が条件と食い違う形は 8/19・8/23・8/25 に3回出ており、**これが4件目**です。

    **`topic` ではなく `video_id` で畳むこと。** `topic` で畳むと、
    **同じ題材を別の本として2回上げた 20件**（実測。`video_id` が違う）が
    1本に潰れて、**今度は実在する本が消えます。**
    動かした本（同じ `video_id`）は 12件で、そちらだけを畳むのが正です。

    **採るのは後の行**（`motion_groups.scheduled_at` と同じ理由）——
    最初の行は「投稿したときの予約」＝すでに動かされた過去の予定です。

    ## **日は JST で採ること**

    `at` は UTC です。素直に `.date()` を採ると **JST の朝が前日に落ちます**。
    実測でいま 4本 が食い違い、**それは 08/27 の 05〜08時 JST に置いた
    「時刻の窓か本数か」の実験そのもの**でした（UTC では 08/26 に落ちる）。
    予約も `day_cap` も JST で置いているので、**割るのも JST** です。
    `src/motion_groups.py` は 2026-08-25 にここを直しており、**この関数が
    帳面を UTC の日で割る最後の1つでした**（`src/` `scripts/` を全部見て確認）。
    """
    src = path or LEDGER
    if not src.exists():
        return []
    latest: dict[str, dict] = {}
    order: list[str] = []
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
        # `video_id` が無い帳面（古い形）は畳めないので、行そのものを鍵にする
        key = str(row.get("video_id") or f"__row__{len(order)}")
        if key not in latest:
            order.append(key)
        latest[key] = row              # **後の行で上書きする**

    out: list[dict[str, object]] = []
    for key in order:
        row = latest[key]
        at = row.get("at")
        pub: date | None = None
        if at:
            try:
                pub = (datetime.fromisoformat(str(at).replace("Z", "+00:00"))
                       .astimezone(JST).date())
            except ValueError:
                pub = None
        # **`at`（時刻つき・JST）も返します**（2026-08-26）。
        # 日だけだと「その本を別の本と入れ替える」が組めません
        # （入れ替えは**同じ時刻枠の交換**なので、時分が要る）。
        # **畳み方をもう一度書かせないため、ここから出します** ——
        # `scripts/queue_lag.py` が自前で畳むと、
        # 「動かした本が2回数えられる」形（この関数の冒頭）を作り直します。
        when: datetime | None = None
        if at:
            try:
                when = (datetime.fromisoformat(str(at).replace("Z", "+00:00"))
                        .astimezone(JST))
            except ValueError:
                when = None
        out.append({"topic": row.get("topic"), "video_id": row.get("video_id"),
                    "publish": pub, "at": when})
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
    #: **この実験の床**（片群あたり。`floor_of()`。**`MIN_PER_GROUP` を写さないこと**）
    floor: int = MIN_PER_GROUP

    @property
    def judgeable(self) -> bool:
        """両群とも**この実験の床**に届いているか（`floor_of()`）。"""
        return bool(self.treated_ready) and all(
            n >= self.floor for n in self.treated_ready.values()
        )

    def short(self) -> str:
        """`status.py` が1行で出す形。"""
        parts = [f"{g} {self.treated_ready.get(g, 0)}本" for g in sorted(self.treated_ready)]
        head = "指示が入って落ち着いた本: " + " / ".join(parts)
        if self.judgeable:
            return head + "  → **判定できます**"
        need = ", ".join(
            f"{g} あと{self.floor - n}本"
            for g, n in sorted(self.treated_ready.items())
            if n < self.floor
        )
        # **床を必ず書くこと。** 16 でない実験があるので、「あと N本」だけでは
        # 読む側が 16 を思い浮かべます（2026-08-27）。
        return head + f"  → **まだ判定しない**（{need} ／ 床 片群 {self.floor}本）"


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
    # **この実験に入れてよい本だけを数えます**（2026-08-27 に足した）。
    # `request_form` は長尺を落とします —— 理由と実測は `_shorts_only()`。
    allowed = exp.eligible() if exp.eligible is not None else None

    c = Counts(experiment=exp.name, floor=floor_of(exp.name))
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
        if allowed is not None and topic not in allowed:
            # **`stale` にも入れません。** 作り直しても永久に処置群へ入らない本です
            #（`_shorts_only()` の「なぜ stale ではないか」）。
            continue
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


#: 作りの通過率（直近5回で 30/34 ＝ 88%。`status.py` の「直近5回、作りを通ったのは」）。
#: **在庫の本数をそのまま「作れる本数」と読まないこと** —— 落ちる本があります。
BUILD_PASS_RATE = 0.88


@dataclass
class Outlook:
    """1つの実験が、**この先まだ判定に間に合うか**。

    `Counts` は「いま何本そろっているか」しか言いません。
    こちらは「**足りない本を、残りの在庫と残りの日数で埋められるか**」を言います。
    """

    experiment: str
    #: この日までに**公開**しないと、判定日に `SETTLE_DAYS` を満たさない
    settle_by: date
    #: 群 → あと何本要るか（0 なら足りている）
    need: dict[str, int] = field(default_factory=dict)
    #: 群 → 未投稿の在庫が何本あるか（`batch_build.pick` が返す本）
    stock: dict[str, int] = field(default_factory=dict)
    #: 在庫の総数（全部の群の合計）。**0 に近いほど、この判定は一度きりの賭けです**
    stock_total: int = 0

    def buildable(self, group: str) -> float:
        """在庫から**実際に作れる**見込み本数（通過率で割り引いた）。"""
        return self.stock.get(group, 0) * BUILD_PASS_RATE

    @property
    def reachable(self) -> bool:
        """全部の群が、在庫だけで床に届くか。"""
        return all(n <= self.buildable(g) for g, n in self.need.items())

    def lines(self) -> list[str]:
        out = [
            f"  **{self.settle_by:%m/%d} までに公開する本しか、この判定には入りません**"
            f"（公開から {SETTLE_DAYS}日）"
        ]
        for g in sorted(self.need):
            n, st = self.need[g], self.stock.get(g, 0)
            if n == 0:
                out.append(f"  {g:4s} 足りています（あと0本）")
                continue
            ok = "足ります" if n <= self.buildable(g) else "**足りません**"
            out.append(
                f"  {g:4s} あと {n}本 ／ 在庫 {st}本"
                f"（通過率 {BUILD_PASS_RATE:.0%} で {self.buildable(g):.1f}本）  → {ok}"
            )
        if not self.reachable:
            out.append(
                "  [!] **在庫だけでは床に届きません。**`python scripts/ab_balance.py --target N --apply` で"
                "\n      未投稿テーマのIDを付け替えて腕をそろえるか、節を掘って在庫を増やすこと。"
            )
        if any(n > 0 for n in self.need.values()):
            out.append(
                f"  [!] **在庫は全部で {self.stock_total}本しかありません。**"
                f"この本を {self.settle_by:%m/%d} より後の日に置くと、**判定には入りません。**"
                f"\n      `batch_build.py --date` は、**この日以前**を選ぶこと。"
            )
        return out


def settle_by(exp: Experiment, as_of: date | None = None) -> date:
    """判定に間に合う**公開の締切**。これより後に公開する本は数に入りません。"""
    return (as_of or exp.deadline) - timedelta(days=SETTLE_DAYS)


def outlook(
    exp: Experiment,
    stock: dict[str, int],
    *,
    as_of: date | None = None,
    counts: Counts | None = None,
) -> Outlook:
    """`exp` が**この先まだ判定に間に合うか**を返す。

    ## なぜ要るか（2026-08-20 04:4x に測って作った）

    `split_counts` は **いまの本数**しか言いません。「まだ判定しない（問い あと8本,
    条件 あと8本）」と出しますが、**その8本が作れるかどうかは一言も言いません。**

    この回に測った実物:

        hook_form  判定 09/16 ／ 落ち着く締切 **09/09**
          いま      問い 0本 / 条件 0本（指示は 08/19 21:00 に入った。**それ以降の作りは0本**）
          在庫      `pick(60)` が返すのは **28本** —— これが**在庫の全部**です
                    （`status.py`「未使用の節: 0件 / 全402件」）
          その割    問い 13 / 条件 15  → 通過率 88% で 11.4 / 13.2 本

    **足ります。ただし余りは 3.4本と 5.2本しかなく、置く日付を間違えると 0 になります。**
    28本を 09/09 より後（例: 予約の薄い 09/20〜09/26）に置くと、
    **在庫は尽きているので、埋め直す手がありません。**

    `next_if_false` は「問いかけの形は畳む」→「題も冒頭も空振りなら題材の側」＝
    M20 へ進みます。**`eta.py` が名指しする唯一の近い腕（1本あたり 1.3倍）を、
    一度も試さないまま畳む**形が、`split_counts` からは見えませんでした。

    `stock` は群名 → 未投稿の在庫本数（`scripts/ab_split.py --outlook` が
    `batch_build.pick` から数えます）。**API を1単位も使いません。**
    """
    c = counts or split_counts(exp, as_of=as_of)
    # **床は実験ごと**（`floor_of()`）。`MIN_PER_GROUP` を写すと `request_form`
    # （床 72本）が「あと4本」に見えます —— 2026-08-27 に踏んだ。
    need = {g: max(0, c.floor - n) for g, n in c.treated_ready.items()}
    return Outlook(
        experiment=exp.name,
        settle_by=settle_by(exp, as_of),
        need=need,
        stock={g: int(stock.get(g, 0)) for g in c.treated_ready},
        stock_total=int(sum(stock.values())),
    )


def report(as_of: date | None = None, stock: dict[str, dict[str, int]] | None = None) -> str:
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
        if stock is not None and exp.name in stock:
            lines.extend(outlook(exp, stock[exp.name], as_of=as_of, counts=c).lines())
        # **`metric` を渡すこと。** engaged で測っていない実験に、engaged の
        #     ブートストラップから出した「要る本数」を出すと嘘になります
        #     （`Experiment.metric` の註。実測 2026-08-27 に `request_form` で踏んだ）。
        v = ab_power.verdict(c.floor, metric=exp.metric)
        if v is not None:
            lines.extend(v.lines())
        if c.unknown_publish:
            lines.append(f"  （控えに公開日が無い {c.unknown_publish}本は、どちらにも数えていません）")
        lines.append("")
    lines.append(
        "**判定の規則そのものが当てられるかは、`src/ab_power.py` が測っています。**"
        "\n中央値の大小だけでは、**効きが無くても 49% で「上回った」と出ます**（コイン投げ）。"
        "\n順位和の門（片側 p ≤ 0.20）を足したうえで、床を片群 16本にしてあります。"
    )
    lines.append(
        "**`stale` の本を混ぜて判定しないこと。** IDが群を決めるので件数は正常に見えますが、"
        "\n中身は両群とも指示より前の作りで同じです。差が出ないのは当たり前で、"
        "\nそれを『外れ』と読むと `next_if_false` が腕ごと畳みます（`src/ab_split.py` の冒頭）。"
    )
    return "\n".join(lines)
