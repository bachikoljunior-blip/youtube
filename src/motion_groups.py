"""**冒頭の動きの A/B を「作ったときの値」で割る。**（2026-08-23）

## なぜ日付で割ってはいけないか（実測で2回踏んだ）

    2026-08-19  `src/ab_split.py` —— 題・冒頭の問いかけを**テーマIDで割っていた**。
                指示が入る前に作った本も「問い」側に数えられ、両群の中身が同じだった
    2026-08-23  「冒頭0.9秒の動き」（期限 09/05）—— **公開日で割っていた**。
                動きは 8/15 の実装で、**作った記録 405本すべてが 8/15 以降**。
                **対照群が1本も無く、測る前から「外れ」が確定**していた

**実装は在庫より先に効き、在庫は数週間先まで予約されています。**
だから「いつ公開したか」も「いつ実装したか」も群を表しません。
**表すのは「その本を作ったときに、どの設定だったか」だけ**です。

`scripts/batch_build.py` が `data/batch_runs.jsonl` の各回に `opening_motion` を
残すようにしたので（同日）、ここはそれを読むだけにしてあります。

## 記録の無い本は、どちらにも入れない

8/23 より前の回には `opening_motion` がありません。**「無い＝動きあり」と
みなすこともできますが、しません** —— 実装前に作った本が混ざる可能性を
ゼロにできないからです。**分からないものは数えない**（標本は減りますが、
群が汚れるより安いです。8/19 の教訓）。
"""
from __future__ import annotations

import collections
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from src import settle

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "data" / "batch_runs.jsonl"
#: **1本ごとのラベル**（`scripts/batch_build._flag_line` が作るたびに1行足す）。
#: `RUNS` は回のおしまいに1回しか書かれないので、**途中で落ちるとラベルが消える**
#: （2026-08-23 に実測: 8本中6本できた回が落ち、6本が「どちらか分からない本」になった）。
FLAGS = ROOT / "data" / "build_flags.jsonl"
UPLOADED = ROOT / "data" / "uploaded.jsonl"
JST = timezone(timedelta(hours=9))
#: 各群に要る本数（`config/hypotheses.yaml` の 09/05 の前提。**共有日だけで数える**）。
BAR = 8
#: **1日に配信される本数**（`src/day_cap.py` の実測。11本目から先は 0〜3再生）。
PER_DAY = 10


def motion_by_topic(runs: Path = RUNS, flags: Path | None = None) -> dict[str, bool]:
    """テーマID → **作ったときに動きが入っていたか**。

    **記録の無い回は入れない。食い違う記録があるテーマは落とす。**

    ## なぜ「最初の記録を採る」をやめたか（2026-08-23 に踏んだ）

    対照群を `--skip-upload` で8本作った直後、動きあり側を同じ引数で作ったところ、
    **`pick()` が同じ8テーマを選び直しました**（`--skip-upload` の本は「使った」に
    ならないため）。`build/` は上書きされ、**ディスクの中身は動きあり・
    記録の1件目は動きなし**という食い違いが生まれた。

    最初の記録を採る規則だと、**この本は「対照群」として集計されます** ——
    中身は動きありなのに。**群のラベルだけが静かに嘘になる**形で、
    今日ずっと潰してきた失敗（8/19・8/23 の2件）とまったく同じです。

    **だから食い違ったら、そのテーマは両方から落とします。**
    標本は減りますが、**嘘のラベルで判定するより安い。**
    """
    seen: dict[str, set[bool]] = {}
    # **1本ごとのラベルも読む。**（回のおしまいの記録だけだと、落ちた回のぶんが消える）
    #
    # **`flags` を引数にしたのは 2026-08-25。** それまでは `FLAGS` を直に読んでいたので、
    # `runs` に別の道を渡しても**本物の `data/build_flags.jsonl` が混ざっていました**
    # （`tests/test_motion_groups.py::test_missing_files_are_empty` が
    # 「空のはず」に実データ 29件を返して落ちていた）。
    flags = FLAGS if flags is None else flags
    if flags.exists():
        for line in flags.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if row.get("topic") and "opening_motion" in row:
                seen.setdefault(row["topic"], set()).add(bool(row["opening_motion"]))
    if not runs.exists():
        return {tid: f.pop() for tid, f in seen.items() if len(f) == 1}
    for line in runs.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if "opening_motion" not in row:
            continue
        flag = bool(row["opening_motion"])
        for res in row.get("results") or []:
            tid = res.get("topic")
            if tid:
                seen.setdefault(tid, set()).add(flag)
    return {tid: flags.pop() for tid, flags in seen.items() if len(flags) == 1}


def topic_by_video(uploaded: Path = UPLOADED) -> dict[str, str]:
    """video_id → テーマID。"""
    out: dict[str, str] = {}
    if not uploaded.exists():
        return out
    for line in uploaded.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("video_id") and row.get("topic"):
            out.setdefault(row["video_id"], row["topic"])
    return out


def groups(video_ids: list[str] | None = None,
           motion: dict[str, bool] | None = None,
           topics: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """`(対照＝動きなし, 動きあり)`。**どちらにも入らない本は捨てます。**"""
    motion = motion_by_topic() if motion is None else motion
    topics = topic_by_video() if topics is None else topics
    ids = list(topics) if video_ids is None else video_ids
    off: list[str] = []
    on: list[str] = []
    for vid in ids:
        tid = topics.get(vid)
        if tid is None or tid not in motion:
            continue                       # **分からないものは数えない**
        (on if motion[tid] else off).append(vid)
    return sorted(off), sorted(on)


def scheduled_at(uploaded: Path = UPLOADED) -> dict[str, str]:
    """video_id → 予約の公開時刻（`data/uploaded.jsonl` の `at`。UTC の文字列）。

    **API は要りません。** 予約は投稿のときに手元へ落ちています。

    ## **後の行を採ること**（2026-08-25 に実測。ここを間違えると群が動きます）

    `uploaded.jsonl` は**足すだけの帳面**です。`scripts/reschedule.py` が
    公開時刻を動かすと、**同じ video_id の行がもう1行足されます。**
    実測: **14本**が2つの `at` を持っていました（491本中）。例——

        485行  QTL7_jky0o0  at=2026-09-23T03:00Z   ← 投稿したときの予約
        489行  QTL7_jky0o0  at=2026-09-22T00:30Z   ← **その後 --compact で前へ寄せた**

    `topic` は作り直しても変わらないので**最初の行**でよいのですが、
    `at` は**動かすためにある欄**なので、最初の行は「過去の予定」です。
    先の行を採ると、この本は 09/23 に居ることになります —— 実際は 09/22 です。

    **A/B の群はこの日で割ります。** 1日足りない側に落ちるだけで、
    共有日が消えたり生えたりします（実測: この1本で 09/22 の列が消え、
    09/24 に 1本 生えていました）。**だから後の行を採ります。**

    **本当の正は API です**（`scripts/reschedule.py --list`）。ここは
    日枠が切れている13時間でも読めるように、手元の帳面で代用しています。
    """
    out: dict[str, str] = {}
    if not uploaded.exists():
        return out
    for line in uploaded.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            continue
        if row.get("video_id") and row.get("at"):
            out[row["video_id"]] = row["at"]      # **後の行で上書きする**
    return out


def jst_day(at: str | None) -> str | None:
    """公開時刻 → **JST の日**。

    ## **UTC の日で割らないこと**（2026-08-25 に実測で踏みかけた）

    `at` は UTC で入っています。素直に先頭10文字を採ると **JST の朝が前日に落ちます**。
    実測（この日の A/B）——

        2026-08-26T20:00Z 〜 23:00Z の 4本  → **JST では 08/27 の 05〜08時**

    UTC の日で数えると 08/26 に対照 0本・動きあり 3本、08/27 に対照 2本・動きあり 1本。
    **JST で数え直すと 08/27 は 2本 対 5本**で、群の重なり方がまるで違います。
    予約も day_cap も JST で置いているので、**割るのも JST**です。
    """
    if not at:
        return None
    try:
        t = datetime.fromisoformat(at.replace("Z", "+00:00"))
    except ValueError:
        return None
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(JST).strftime("%Y-%m-%d")


def by_day(off: list[str], on: list[str],
           at: dict[str, str] | None = None,
           ) -> dict[str, tuple[list[str], list[str]]]:
    """JST の日 → `(その日の対照, その日の動きあり)`。時刻の無い本は落とします。"""
    at = scheduled_at() if at is None else at
    out: dict[str, tuple[list[str], list[str]]] = {}
    for ids, idx in ((off, 0), (on, 1)):
        for vid in ids:
            day = jst_day(at.get(vid))
            if day is None:
                continue
            out.setdefault(day, ([], []))[idx].append(vid)
    return {d: (sorted(a), sorted(b)) for d, (a, b) in sorted(out.items())}


def paired(off: list[str], on: list[str],
           at: dict[str, str] | None = None) -> tuple[list[str], list[str]]:
    """**両群がそろっている日の本だけ**を返す ＝ この A/B で実際に使える標本。

    ## なぜ生の本数を「標本」と呼んではいけないか（2026-08-25）

    `config/hypotheses.yaml` の 09/05 の前提は、条件にこう書いてあります ——
    **「動きありと同じ日に交互で予約する（公開時刻の差を群に混ぜないため）」**。
    片方しか無い日の本は、**動きの差と「その日の配信の差」を分けられません。**
    1日に配信されるのは 10本ちょうど（`src/day_cap.py`）で、
    **その10本をどの群が取ったかは日ごとに変わります。**

    それでもここは長らく生の合計だけを出していました。実測（2026-08-25）——

        生の合計    対照 8本 ／ 動きあり 19本   → **どちらも門(8)を越えて見える**
        共有日だけ  対照 6本 ／ 動きあり 8本    → **対照が 2本 足りない**

    **「越えて見える」ほうを読むと、条件を満たさないまま判定に入ります。**
    そして `next_if_false` は「静止スライド＋合成音声という形式そのものを疑う」なので、
    **形式側で最後に残った前提が、条件を満たさない標本で殺されます**
    （8/19 の `ab_split`・8/23 の「公開日で割る」と同型で、これが3件目）。

    ## **再生が付かない本も落とします**（2026-08-26 に足した）

    共有日にそろっていても、**その日の11本目から後ろは 0再生**です
    （`src/day_cap.py` の実測）。0再生の本は engaged 比率を持たないので、
    `falsified_if` の「30再生以上」にも入りません。

    **同じ絞り込みが `src/judgeable.members()` に先に入り、ここだけ残っていました。**
    実測（2026-08-26）: ここは「共有日だけで両群とも 8本に達しています」と印字し、
    `python -m src.judgeable` は同じ群を「**3本 —— そろいません**」と出していました。
    **同じ群について、2つの道具が逆のことを言っていた**ということです。
    数える所を増やさず、`day_cap.live_ids()` を呼びます。
    """
    keep = _live(at)
    days = by_day(off, on, at)
    p_off: list[str] = []
    p_on: list[str] = []
    for a, b in days.values():
        a = [v for v in a if keep is None or v in keep]
        b = [v for v in b if keep is None or v in keep]
        if a and b:
            p_off += a
            p_on += b
    return sorted(p_off), sorted(p_on)


def _live(at: dict[str, str] | None) -> set[str] | None:
    """**再生が付く側の `video_id`**（判定は `src/day_cap.py` が1か所で持っています）。

    読めない回は `None`（＝絞らない）。**観測していないものを、無いことにしない** ——
    控えが読めないだけで群が空になると、判定できる日そのものが消えます。
    """
    try:
        from src import day_cap
        from src.ab_split import published

        rows = [r for r in published() if r.get("at")]
        return day_cap.live_ids(rows)
    except Exception:                                    # noqa: BLE001
        return None


def free_slot(day: str, at: dict[str, str], *,
              hour: int = 9, until_hour: int = 21, step_min: int = 30) -> str | None:
    """その JST 日で、**まだ誰も居ない 30分きざみの時刻**を1つ返す（`HH:MM`）。

    `scripts/reschedule.py --move` は**時刻の取り合いを見ません**（`--compact` 側だけが
    見ています）。だから割り当てをそのまま貼れるように、ここで空きを選んでおきます。
    **長尺も数えます** —— 同じ時刻に2本置かないため（`reschedule.py:437` と同じ規則）。
    """
    taken = set()
    for v in at.values():
        d = jst_day(v)
        if d != day:
            continue
        t = datetime.fromisoformat(v.replace("Z", "+00:00")).astimezone(JST)
        taken.add((t.hour, t.minute))
    for h in range(hour, until_hour + 1):
        for m in range(0, 60, step_min):
            if (h, m) not in taken:
                return f"{h:02d}:{m:02d}"
    return None


def retime_plan(off: list[str], on: list[str],
                at: dict[str, str] | None = None,
                bar: int = BAR, per_day: int = PER_DAY) -> list[tuple[str, str, str]]:
    """共有日の標本を門まで持ち上げる、**いちばん本数の少ない動かし方**を出す。

    返すのは `(video_id, いまの JST 日, 送り先の JST 日)` の並び。
    撃つのは `scripts/reschedule.py --move <video_id> <JST>` です（1本 50単位）。

    **足りない側だけを動かします。** 足りているほうを動かすと、
    せっかく共有になっている日を壊すことがあるからです。
    送り先は「**相手だけが居る日のうち、その本にいちばん近い日**」——
    そこへ1本入れれば、その日はまるごと共有日に変わり、
    **相手のその日のぶんも一緒に標本へ入ります**（いちばん効率が良い）。

    ## **満杯の日へ送らないこと**（`per_day`）

    1日に配信されるのは **10本ちょうど**です（`src/day_cap.py`。08/20〜08/22 の3日とも
    一致し、08/21 は挟まれた7本が死んでいる）。**11本目から先は 0〜3再生**なので、
    満杯の日へ1本足すと、**その本は「動きが無かったから伸びなかった」ではなく
    「その日の11本目だったから伸びなかった」**ことになります。
    **群を揃えるために動かして、動かした本を殺す**——本末転倒なので、ここで弾きます。
    数えるのは A/B の本だけでなく**その日の予約すべて**です（長尺も配信の枠を取ります）。
    """
    at = scheduled_at() if at is None else at
    days = by_day(off, on, at)
    #: JST の日 → その日の予約の本数（**A/B 以外も全部**）
    load: dict[str, int] = collections.Counter(
        d for d in (jst_day(v) for v in at.values()) if d)
    plan: list[tuple[str, str, str]] = []
    moved: set[str] = set()

    def counts() -> tuple[int, int]:
        n_a = n_b = 0
        for x, y in days.values():
            if x and y:
                n_a += len(x)
                n_b += len(y)
        return n_a, n_b

    # **無限に回らないよう、動かす本数は在庫の数で止めます。**
    for _ in range(len(off) + len(on)):
        n_off, n_on = counts()
        if n_off >= bar and n_on >= bar:
            break
        short = 0 if n_off < bar else 1          # 0=対照が足りない / 1=動きありが足りない
        # 送り先: **相手だけが居る日**（そこへ1本足すと共有日になる）。
        # **満杯の日は外す** —— 11本目は配信されず、動きのせいで伸びなかったことにされる
        targets = [d for d, pair in days.items()
                   if pair[1 - short] and not pair[short] and load[d] < per_day]
        # 出し元: **自分だけが居る日**（そこから引いても共有日を壊さない）
        sources = [(d, v) for d, pair in days.items()
                   for v in pair[short]
                   if not pair[1 - short] and v not in moved]
        if not targets or not sources:
            break
        best: tuple[int, str, str, str] | None = None
        for d, v in sources:
            for t in targets:
                gap = abs((datetime.strptime(t, "%Y-%m-%d")
                           - datetime.strptime(d, "%Y-%m-%d")).days)
                cand = (gap, t, d, v)
                if best is None or cand < best:
                    best = cand
        gap, t, d, v = best
        days[d][short].remove(v)
        days[t][short].append(v)
        load[d] -= 1
        load[t] += 1
        moved.add(v)
        plan.append((v, d, t))
    return plan


def main() -> None:  # pragma: no cover - 画面出力だけ
    off, on = groups()
    at = scheduled_at()
    p_off, p_on = paired(off, on, at)
    print("=== 冒頭の動き A/B（作ったときの値で割る）===")
    print(f"  生の合計         対照（動きなし） {len(off)}本 ／ 動きあり {len(on)}本")
    print(f"  **共有日だけ**   対照 {len(p_off)}本 ／ 動きあり {len(p_on)}本"
          f"   ← **標本はこちら**（門は各 {BAR}本）")
    if len(off) >= BAR > len(p_off) or len(on) >= BAR > len(p_on):
        print("  [!] **生の合計は門を越えて見えますが、条件を満たしていません。**"
              " 片方しか居ない日の本は、動きの差と『その日の配信の差』を分けられません"
              "（1日に配信されるのは 10本ちょうど・`src/day_cap.py`）")
    if not off:
        print("  **対照群がまだ 0本です。** `YT_OPENING_MOTION=0` で作らないかぎり増えません")
        print("  （`config/hypotheses.yaml` の `control_group_todo`: 8本以上・同じ日に交互で予約）")

    days = by_day(off, on, at)
    if days:
        print("\n  --- JST の日ごと（**UTC の日で割らないこと**。JST の朝が前日に落ちます）---")
        print(f"  {'JST日':<12}{'対照':>5}{'動きあり':>8}   共有")
        for d, (a, b) in days.items():
            print(f"  {d:<12}{len(a):>5}{len(b):>8}   {'○' if a and b else '×'}")

    plan = retime_plan(off, on, at)
    if plan:
        print(f"\n  --- 門まで持ち上げる割り当て（**{len(plan)}本 動かすだけで済みます**）---")
        used = dict(at)
        for vid, src, dst in plan:
            slot = free_slot(dst, used)
            if slot is None:
                print(f"  {vid}  {src} → {dst}    **{dst} に空き時刻がありません**（別の日へ）")
                continue
            used[vid] = (datetime.strptime(f"{dst} {slot}", "%Y-%m-%d %H:%M")
                         .replace(tzinfo=JST)
                         .astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"))
            print(f"  {vid}  {src} → {dst}    "
                  f"python scripts/reschedule.py --move {vid} {dst}T{slot}")
        print("  **`videos.update` は 1本 50単位**。日枠が戻るのは JST 16:00")
    elif len(p_off) >= BAR and len(p_on) >= BAR:
        print(f"\n  **共有日だけで両群とも {BAR}本に達しています。**"
              f" あとは公開から{settle.SETTLE_DAYS}日・30再生以上を待って判定へ")
    else:
        print("\n  [!] **動かすだけでは門に届きません。**"
              " 足りない側を `YT_OPENING_MOTION` を明示して作り足すこと")


if __name__ == "__main__":  # pragma: no cover
    main()
