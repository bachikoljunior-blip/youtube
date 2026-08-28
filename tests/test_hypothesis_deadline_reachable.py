"""**期限が「その条件を判定できるいちばん早い日」より前なら、ここで落ちる。**

## なぜ要るか（2026-08-25 に、同じ形を **5件** まとめて見つけて足した）

期限を切るとき、**落ち着くまでの日数 × 作ってから公開までの間隔 × Analytics の遅れ**を
掛け忘れると、**測る前から届かないと決まっている期限**ができます。見た目は正常で、
`status.py` は期日が来たと鳴らし、来た側は「まだ判定できません」と書いて延ばす ——
**掛け算を忘れたことは、どこにも残りません。**

実例（この検査を足した回に直した5件。**どれも `falsified_if` は1字も変えていない**）:

    冒頭の stat の割り方   09/05 → 10/05  処置群の16本目の公開 09/03 ＋ 7日 ＋ 3日
    冒頭0.9秒の動き        09/05 → 10/10  共有日の対照8本目の公開 09/23 ＋ 7日 ＋ 3日
    登録の依頼             09/14 → 10/15  30,000再生に要る30本の枠が 09/22 以降
    長尺の失敗の理由       08/27 → 09/07  書き直しの輪が入って失敗率が 0/6 になった
    計算で独自性           09/01 → 2027-12-18  収益化の申請そのものが 2027-11-18

## 掛けているもの

    src.ab_split.SETTLE_DAYS   = 7   公開から落ち着くまで（初速だけを見ない）
    src.ab_split.MIN_PER_GROUP = 16  片群の床
    Analytics の遅れ           = 3日 `data/analytics_lag.jsonl` の実測から読む
    作ってから公開までの間隔         `data/uploaded.jsonl` の予約から**そのまま**読む
                                     （中央値13.4日・最大40.2日。定数で持たない）

**「作ってから公開まで」を定数で持たないのが肝です。** 予約が伸びるほどこの間隔は
伸びるので、**去年正しかった期限が、今日は届かなくなります。**

## 当てられた件（下の `CHECKABLE`）

    題を問いの形に            `ab_split.EXPERIMENTS["title_form"]`
    冒頭1枚目の主役を問いに    `ab_split.EXPERIMENTS["hook_form"]`
    冒頭の stat の割り方       `d14dbf7`（2026-08-23 22:03 JST）で割る処置群
    冒頭0.9秒の動き            `src.motion_groups` の**共有日の標本**（割り当て後）

## 当てられなかった件と、その理由（**名指しで全部書く**）

台帳の**数え上げ**に落ちないもの ——「将来いくつ再生が付くか」「次に何本落ちるか」は
予約表から出ません。**出ない以上、この検査は黙ります**（推測でしきい値を作らないこと）。

    ショートの最後で登録を直接1回頼む  条件が「計30,000再生」＝**将来の再生の合計**
    作る題材の順番（族べつ登録率）      条件が「計15,000再生」＝同上
    長尺の登録率はショートより1桁高い    条件が「計1000再生」＝同上
    WATCH の伸びは複利                  条件が「全走査の WATCH が60未満」＝将来の絶対値
    長尺の面は 1,285回/日 を再現する     条件が「最大の1日が643回」＝同上
    長尺の生成が落ちる主因               条件が「失敗が6本」＝**生成が落ちるという確率過程**
    長尺は1日4本 作れる                  判定日にローカルの台帳を数えるだけ（遅れが無い）
    1日に再生が付く本数の上限（08/27）   その日の配信を見る。観測は当日中に出る
    1日に再生が付く本数の上限（09/10）   同上
    1日に再生が付く本の集合（帯・09/02） 同上。切り分ける12本はもう予約に在る
    チャンネルのホーム（M22）           条件が「計15,000再生」＝将来の再生の合計
    族べつの engaged 比率は順番に使える  中央値の比較で、本数の床が条件に無い
    段階表示で増えた行を強調する         処置3本・対照11本とも公開済みで、床は満ちている
    計算で独自性を出す構成               **収益化の申請そのもの**が要る。`eta.py` の門1に乗る

**新しい前提を足したら、どちらかに名前を入れること。** どちらにも無ければ
`test_開いている前提は全部どちらかに入っていること` が落ちます ——
**黙って当たらないより、落ちるほうを選んでいます。**
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from src.ab_split import (
    EXPERIMENTS,
    MIN_PER_GROUP,
    SETTLE_DAYS,
    build_times,
    published,
)

ROOT = Path(__file__).resolve().parent.parent
YAML = ROOT / "config" / "hypotheses.yaml"
LAG = ROOT / "data" / "analytics_lag.jsonl"
JST = timezone(timedelta(hours=9))

#: Analytics の日次が遅れる日数。**定数で書かず、帳面の実測から読みます**
#: （`src/rpm_mix.pending_after` と同じ考え方）。読めなければ 3日。
FALLBACK_LAG_DAYS = 3


def analytics_lag_days() -> int:
    """`data/analytics_lag.jsonl` の最後の行から、実測の遅れを出す。"""
    if not LAG.exists():
        return FALLBACK_LAG_DAYS
    best: int | None = None
    for line in LAG.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
            seen = datetime.fromisoformat(str(row["at"])).astimezone(JST).date()
            last = date.fromisoformat(str(row["last_day"]))
        except (ValueError, KeyError, TypeError):
            continue
        best = (seen - last).days
    return best if best and best > 0 else FALLBACK_LAG_DAYS


def load_hypotheses() -> list[dict]:
    return yaml.safe_load(YAML.read_text(encoding="utf-8"))["hypotheses"]


def open_with_deadline() -> list[dict]:
    """**まだ閉じていない**うえで `deadline` を持つ前提だけ。"""
    return [
        h for h in load_hypotheses()
        if h.get("deadline") and not h.get("closed_on") and not h.get("outcome")
    ]


def deadline_of(key: str) -> date:
    """`claim` に `key` を含む、開いている前提の期限。"""
    hit = [h for h in open_with_deadline() if key in str(h.get("claim", ""))]
    assert len(hit) == 1, f"`{key}` に当たる開いている前提が {len(hit)} 件（1件であること）"
    d = hit[0]["deadline"]
    return d if isinstance(d, date) else date.fromisoformat(str(d))


def ready_on(publish_days: list[date], need: int) -> date | None:
    """`need` 本目が**落ち着いて、Analytics にも出る**日。届かなければ `None`。

    掛けているのは `SETTLE_DAYS` と Analytics の遅れの**大きいほう**です
    （7日たった本の数字は、その3日前にはもう届いています）。
    """
    if len(publish_days) < need:
        return None
    return sorted(publish_days)[need - 1] + timedelta(
        days=max(SETTLE_DAYS, analytics_lag_days())
    )


def publish_days(topics: list[str]) -> list[date]:
    """テーマIDの並び → **予約まで入っている公開日**（JST）の並び。"""
    want = set(topics)
    out: list[date] = []
    for row in published():
        pub = row.get("publish")
        if isinstance(pub, date) and str(row.get("topic") or "") in want:
            out.append(pub)
    return out


def treated_topics(landed: datetime) -> list[str]:
    """**その時刻より後に作った**本のテーマID（公開日ではなく作った時刻で割る）。"""
    return [t for t, at in build_times().items() if at >= landed]


# ---------------------------------------------------------------- 当てられる件

def earliest_ab(name: str) -> date | None:
    """A/B 1件が、**両群 `MIN_PER_GROUP` 本そろって落ち着く**いちばん早い日。"""
    exp = EXPERIMENTS[name]
    treated = set(treated_topics(exp.landed))
    per_group: dict[str, list[date]] = {exp.treated: [], exp.control: []}
    for row in published():
        pub, topic = row.get("publish"), str(row.get("topic") or "")
        if not isinstance(pub, date) or topic not in treated:
            continue
        g = exp.split(topic)
        if g in per_group:
            per_group[g].append(pub)
    days = [ready_on(v, MIN_PER_GROUP) for v in per_group.values()]
    return None if any(d is None for d in days) else max(d for d in days if d)


def earliest_stat_split() -> date | None:
    """「冒頭の stat の割り方」＝ `d14dbf7`（2026-08-23 22:03 JST）で割る前後。"""
    landed = datetime(2026, 8, 23, 22, 3, 31, tzinfo=JST)
    treated = set(treated_topics(landed))
    all_built = set(build_times())
    t_days = publish_days(sorted(treated))
    c_days = publish_days(sorted(all_built - treated))
    days = [ready_on(t_days, MIN_PER_GROUP), ready_on(c_days, MIN_PER_GROUP)]
    return None if any(d is None for d in days) else max(d for d in days if d)


#: 「冒頭0.9秒の動き」の床。yaml の「対照 8本以上・動きあり 8本以上」と同じ数。
MOTION_MIN_PER_GROUP = 8


def earliest_opening_motion() -> date | None:
    """「冒頭0.9秒の動き」＝ `src/motion_groups.py` の**共有日の標本**で数える。

    片方しか居ない日の本は使えない（動きの差と、その日の配信の差を分けられない）ので、
    **`paired()` が返す共有日の本だけ**を数えます。届いていなければ、
    道具が出す**割り当て（`retime_plan`）を当てた後**の姿で数え直します ——
    yaml が「次にこの前提へ触る回がやること」としてその2本を名指ししているからです。
    """
    from src import motion_groups as M

    off, on = M.groups()
    at = M.scheduled_at()
    plan = {vid: to for vid, _, to in M.retime_plan(off, on)}
    moved = {vid: (plan[vid] + "T09:00:00+09:00" if vid in plan else raw)
             for vid, raw in at.items()}
    p_off, p_on = M.paired(off, on, moved)

    def days(ids: list[str]) -> list[date]:
        out = []
        for vid in ids:
            day = M.jst_day(moved.get(vid))
            if day:
                out.append(date.fromisoformat(day))
        return out

    got = [ready_on(days(p_off), MOTION_MIN_PER_GROUP),
           ready_on(days(p_on), MOTION_MIN_PER_GROUP)]
    return None if any(d is None for d in got) else max(d for d in got if d)


#: `claim` の一部 → その前提を**いちばん早く判定できる日**を出す関数。
CHECKABLE = {
    "題を問いの形にすると": lambda: earliest_ab("title_form"),
    "冒頭1枚目の主役": lambda: earliest_ab("hook_form"),
    "冒頭の stat は": earliest_stat_split,
    "冒頭0.9秒に絵そのものの動き": earliest_opening_motion,
}

#: 当てられない件と、その理由。**docstring と同じ並び。**
UNCHECKABLE = {
    "ショートの最後で登録を直接1回頼む": "条件が「計30,000再生」＝将来の再生の合計",
    "作る題材の順番は": "条件が「計15,000再生」＝将来の再生の合計",
    "長尺の登録率はショートより1桁以上高い": "条件が「計1000再生」＝将来の再生の合計",
    "WATCH（視聴ページ）の伸びは複利": "条件が将来の絶対値（WATCH 60未満）",
    "長尺の面": "条件が将来の絶対値（最大の1日が643回）",
    # 条件は「**枠 × 面 × CTR** が 89回/日 以上」＝ 3つの実測の積の将来値。
    # `earliest_*` は「予約に既に在る本から床を数える」道具なので当てられません
    # （床が「本数」ではないため）。判定日は `kind: after` が持ちます。
    "門2a（長尺4,000時間）は": "条件が将来の絶対値（枠×面×CTR が 89回/日）",
    "長尺の生成が落ちる主因": "条件が「失敗が6本」＝生成が落ちるという確率過程",
    "長尺は1日4本 作れる": "判定日にローカルの台帳を数えるだけで、遅れが掛からない",
    "1日に再生が付く本数の上限は": "その日の配信を見る。観測は当日中に出る",
    "1日に再生が付く本数の上限（いま10本）": "同上（09/10 の16本を当日中に見る）",
    # 2026-08-28 に足した。切り分ける日（2026-09-02 の12本）は**もう予約に在り**、
    # 読むのは `data/views.jsonl`（`videos.list` の累計）なので Analytics の遅れは
    # 掛かりません。判定日は `kind: after`（09-03 04:00 JST）が持ちます。
    "1日に再生が付く本の集合は": "その日の配信を見る。観測は翌04:00 JST に出る（09/02 の12本は予約済み）",
    # 2026-08-28 に足した（M22 を実際に置いた回）。床は「08/29 以降に公開した本の
    # 合計再生が 15,000」＝**これから積む再生**なので、`earliest_*`（予約に既に在る
    # 本から床を数える道具）には当てられません。判定日は `kind: after` と
    # `watch: チャンネルのホーム-15000再生` が持ちます。
    "チャンネルのホームに紹介動画とバナーを置く": "条件が「計15,000再生」＝これから積む再生の合計",
    "族べつの engaged 比率は": "中央値の比較で、本数の床が条件に無い",
    "段階表示で": "処置3本・対照11本とも公開済みで、床は満ちている",
    "計算で独自性を出す構成": "収益化の申請そのものが要る（`eta.py` の門1に乗る）",
    # 床は「30再生以上 5本」だが、**その5本を作る作業は要らない** ——
    # 対照日（09/25〜09/26）も比較先（前後7日の高密度日）も**もう予約に入っています**。
    # 待っているのは公開と実データだけなので、`kind: after` で足ります
    # （`src/measure_window.py` の `density_engaged` の窓が、その2日を守ります）。
    "engaged 比率は、その日に出した本数が増えると下がる": "対照も比較先も予約済み。待つのは公開と実データだけ",
    # 床は「深い題のショート16本」＝**これから積む本数**なので、
    # 日を出すのは `scripts/deadline_check.py` の `accrual`（伸び率から解く）側です。
    # ここの `earliest_*` は**予約に既に在る本**から床を数える道具なので、当てられません。
    # 対照（`s-` の題のショート）は 379本 あり、待っているのは処置側だけ。
    "深い題（`s-` で始まらない・節を持つ題）をショートとして出すと": "条件が「深い題のショート16本」＝これから積む本数（accrual）",
    # 立てた 2026-08-26 の時点で両群とも **0本**、床は片群 **72本**。
    # `earliest_ab()` は「予約に既に在る本」から床を数える道具なので、
    # **これから積む群には当てられません**（`src/judgeable.ACCRUING` に同じ理由）。
    # 群がそろったら `ACCRUING` から外し、ここも `CHECKABLE` の
    # `lambda: earliest_ab("request_form")` へ移すこと。
    "登録の依頼を、終端だけでなく途中にも1回入れる": "条件が「両群72本」＝これから積む本数（accrual）",
    # 床は「08/27〜09/07 に長尺14本」＝**これから積む本数**で、しかも条件そのものは
    # 将来の絶対値（`long_share_now` が 1.2% に届くか）です。`earliest_*` は
    # 「予約に既に在る本から床を数える」道具なので、どちらの意味でも当てられません。
    # 判定日は `kind: after` と `watch: 長尺シェア-14本` が持ちます。
    "長尺の再生シェアは、長尺の公開本数を増やせば上がる": "条件が将来の絶対値（長尺シェア 1.2%）＋床がこれから積む本数",
    # 立てた 2026-08-27 21:30 の時点で両群とも **0本**（振り分けはその時刻より
    # 後に作った本にしか効かず、予約の 430本 は全部それより前）。床は片群 16本。
    # `earliest_ab()` は「予約に既に在る本」から床を数える道具なので、
    # **これから積む群には当てられません**（`src/judgeable.ACCRUING` に同じ理由）。
    # 群がそろったら `ACCRUING` から外し、ここも `CHECKABLE` の
    # `lambda: earliest_ab("slide_pace")` へ移すこと。
    "ショートの刻み（1コマ 2.5秒）は速すぎる": "条件が「両群16本」＝これから積む本数（accrual）",
    # 床は「2026-08-27 12:00 より後に作ったショート16本」＝**これから積む本数**。
    # しかも群は A/B ではなく**新旧の割り当て**（時刻で割る）なので、
    # `earliest_ab()` の見る `EXPERIMENTS` にそもそも載っていません。
    # 判定日は `kind: accrual` と `watch: 完成形の保持-16本` が持ちます。
    "完成した図を説明のあいだ画面に残す": "条件が「新しい割り当ての本16本」＝これから積む本数（accrual）",
    # 2026-08-28 に足した。条件は `day_cap.day_total()["rho_scale"]` ＝
    # **「上限まで出した日」の順位相関**で、床は本数ではなく**日数**（14日）。
    # `earliest_*` は「予約に既に在る本から床を数える」道具なので当てられません
    # （予約は既に在るが、床が本ではなく日なので数が合わない）。
    # 判定日は `kind: after`（09-05）が持ち、読むのは `data/views.jsonl` だけ ——
    # Analytics ではないので3日の遅れは掛かりません。
    "1日の再生の合計は、その日に出した本数では動かない": "床が本数ではなく日数（上限まで出した日 14日）",
    # 2026-08-28 に足した。床は「08/29〜09/04 に公開した日」＝**日数（7日）**で、
    # 本数ではありません（1日 10本 が毎日 入るので、本数で数えると床が
    # 先に埋まったように見えます）。`earliest_*` は「予約に既に在る本から
    # 床を数える」道具なので当てられません。判定日は `kind: after`（09-04）が持ち、
    # 読むのは `data/views.jsonl` だけ —— **Analytics ではないので3日の遅れは
    # 掛かりません**（同じ理由で `plus_lag: false`）。
    "落ちたのは、中身ではなく配信": "床が本数ではなく日数（08/29〜09/04 の公開日 7日）",
}


def _key_for(claim: str) -> str | None:
    for key in list(CHECKABLE) + list(UNCHECKABLE):
        if key in claim:
            return key
    return None


def test_開いている前提は全部どちらかに入っていること():
    """**新しい前提を足したら、当てるか名指しで外すかを決めること。**"""
    missing = [
        str(h.get("claim"))
        for h in open_with_deadline()
        if _key_for(str(h.get("claim", ""))) is None
    ]
    assert not missing, (
        "期限を持つ前提が `CHECKABLE` にも `UNCHECKABLE` にも入っていません。\n"
        "  当てられるなら `CHECKABLE` に、当てられないなら**理由つきで** `UNCHECKABLE` に:\n"
        + "\n".join(f"    - {c}" for c in missing)
    )


@pytest.mark.parametrize("key", sorted(CHECKABLE))
def test_期限は判定できる最短の日より後にあること(key: str):
    """`deadline` < 最短の判定可能日 なら落ちる。**条件は緩めず、期限だけを動かすこと。**"""
    earliest = CHECKABLE[key]()
    limit = deadline_of(key)
    assert earliest is not None, (
        f"「{key}」は、**いまの予約を全部使っても床に届きません**（期限 {limit}）。\n"
        "  条件を緩めるのではなく、**本を作って床まで積むか、期限を延ばすこと。**"
    )
    assert limit >= earliest, (
        f"「{key}」の期限 {limit} は、判定できる最短の日 {earliest} より前です。\n"
        f"  掛けるもの: 落ち着くまで {SETTLE_DAYS}日 ／ Analytics の遅れ "
        f"{analytics_lag_days()}日 ／ 作ってから公開までの間隔（予約からそのまま）。\n"
        f"  **`falsified_if` は1字も変えず、`deadline` だけを {earliest} 以降へ延ばすこと。**"
    )
