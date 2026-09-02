#!/usr/bin/env python3
"""**先の日付の予約を、回の意思と関係なく、毎周 掃く。**

    python scripts/ahead_sweep.py            # 数えて、要るなら掃く（日枠が開いていれば）
    python scripts/ahead_sweep.py --dry-run  # 何をするかだけ言う（**API 0単位**）

## なぜ門だけでは足りないか（2026-09-02・オーナー原文）

> **「1日一本になってないんだけど、今後こういうことが一切ないようにしろ」**

同じ日に3つ 置きました。**役割が違います**:

    置く側の関門   `house_rule.refuse_future_publish()`  **新しく置けなくする**
    終わりの門     `scripts/stop_check.sh` (1.45)        **0本にせずに終われなくする**
    ここ           `scripts/ahead_sweep.py`              **回が何もしなくても掃ける**

**門は「その回が終わろうとしたとき」に効きます。** ところが 09/01 07:0x に
再起動で 39分ぶんが消え、11:5x には3つ まとめて殺されています ——
**終わらなかった回には、終わりの門は当たりません。**
そして 08/31 の固定から2日で 459本 → 107本 にしか減っていないのは、
**減らす手が「その回が選べば撃つ」形だったから**です
（09/01 の実測: `fix` 82% ／ `upload` 0件）。

**だから、回の意思の外に置きます。** `.claude/settings.json` の `SessionStart` から
`scripts/ahead_sweep.sh` が**背景で**呼びます —— 回は何も選ばず、何も覚えません。

## 何をするか（順番も固定。**オーナーがこの順で名指ししています**）

    0. **きょうの1本を置く**（2026-09-02 夜に足した。`place_today()` の註 ——
       外す側が3つ 揃っても、**置く側が回の裁量のままなら空く日が出ます**）
    1. `ahead_gate --live`      実物を引く（読んだついでに控えが実物へ合う）
    2. `python -m src.ledger_truth`  控えと実物の食い違いを名指しする
    3. `pool_drain --apply --keep 0` **削除しない**・private の下書きへ戻すだけ
    4. `ahead_gate --live`      掃いたあとを、もう一度 実物で見て記録する

**きょうのぶんが未公開で予約に在るなら、それは外しません**（`pool_drain.plan()`
が規則5 の下で当日を別に守ります。`--keep 0` でも外れません）。

## 撃たない回（**推測で撃たないこと**）

    日枠が尽きている            `upload_cap.day_quota()` に自分で訊く
    先の日付が 0本              掃くものが無い
    もう別の掃きが走っている    ロック（`data/.ahead_sweep.lock`）
    `.owner-pause` が在る       `src.pause_guard`（**人だけが置ける印**）
    規則5 が外れている          `house_rule.same_day_only()` が `False`

## 覆る条件

- オーナーが「先の日付にも置いてよい」と言ったら、`same_day_only()` が `False` に
  なって**この掃きはまるごと黙ります**（判定はそこ1か所）
- 掃きが投稿の枠を食っていると実測で出たら、`pool_drain` 側の取り置き
  （`thumbnail_first` / `swap_reserve`）を広げること。**掃きを止めないこと** ——
  止めた2日で 459本 → 107本 にしかならなかったのが、この道具が在る理由です

検査は `tests/test_ahead_sweep.py`。
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import ahead_gate  # noqa: E402
from src import config, house_rule  # noqa: E402

#: **同じ掃きが2つ走らないための印。** 中身は `{pid} {開始時刻}`。
LOCK = "data/.ahead_sweep.lock"

#: 印が**この時間より古ければ、死んだ掃きの置き土産**として奪います。
#: 107本 ＝ 約 5,500単位・1本 2〜3秒 なので、1回の掃きは長くて 10分ほど。
STALE = timedelta(minutes=45)


def _lock_path() -> Path:
    return Path(config.ROOT) / LOCK


def take_lock(now: datetime | None = None, path: Path | None = None,
              stale: timedelta | None = None) -> bool:
    """**掃く権利を取る**（取れたら `True`）。**死んだ印は奪います。**

    死んだ印を奪わないと、**一度 落ちた回のあとは二度と掃けません** ——
    この輪はコンテナごと消える回があるので（09/01 07:0x に再起動で 39分、
    11:5x に3つ）、**必ず起きます**。

    `path` / `stale` は「きょうの1本を置く手」（`place_today`）が別の印を
    使うために在ります。**既定は掃きの印**で、呼び方は変わっていません。
    """
    now = now or datetime.now(timezone.utc)
    p = path or _lock_path()
    stale = STALE if stale is None else stale
    try:
        raw = p.read_text(encoding="utf-8").strip()
    except OSError:
        raw = ""
    if raw:
        parts = raw.split(None, 1)
        at = ahead_gate._parse(parts[1]) if len(parts) > 1 else None
        if at is not None and now - at < stale:
            return False
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{os.getpid()} {now.isoformat()}\n", encoding="utf-8")
    except OSError:
        return False
    return True


def drop_lock(path: Path | None = None) -> None:
    try:
        (path or _lock_path()).unlink()
    except OSError:
        pass


def _paused() -> str:
    """`.owner-pause` が在れば理由（**人だけが置ける印**。機械は作らないこと）。

    判定は `src.pause_guard.is_paused()` の1か所です（**写さないこと** ——
    2026-08-31 まで3か所が別々に見ていて、片方だけ直した回が
    「動いているのに停止中と印字する」形を作れました）。
    """
    try:
        from src import pause_guard                             # noqa: PLC0415
        if pause_guard.is_paused():
            return str(pause_guard.OWNER_PAUSE_MARKER)
    except Exception:                                           # noqa: BLE001
        return ""
    return ""


#: **その日の1本のために、掃きに食わせない単位**（2026-09-02）。
#:
#: ## なぜ要るか
#:
#: この掃きは**回の意思と関係なく**走ります。だから「今日はやめておこう」で
#: 手加減する人がいません。**窓を全部 焼くと、その日の投稿が撃てなくなります** ——
#: `CLAUDE.md`「**投稿が途切れるのが最大の損失**」。実測 2026-09-01 16:0x の窓は、
#: `pool_drain --apply` が 160本 で **12,258 / 10,000単位** を焼き、
#: 次の枠の本が「焼いたあとに入った 6件」を1つも入れずに出ました
#: （`pool_drain.SWAP_UNITS` の註）。
#:
#: その日の1本に要るのは、ざっと **`--move` 51 ＋ サムネイル 50 ＋ 差し替え 100
#: ＋ 読み**。**多めに 2,000単位** 残します（掃きは翌日の窓が続けます ——
#: 締切は `pool_drain.first_breach()` が言うとおり 09/24 で、まだ余裕があります）。
#:
#: **覆る条件**: 掃きが何日 経っても終わらないなら、ここを削る前に
#: `pool_drain` の取り置き（`swap_reserve`）と取り合っていないかを見ること。
RESERVE_UNITS = 2_000


def budget_max(now: datetime | None = None) -> int:
    """**この回の掃きで外してよい本数の上限**（0 ＝ 上限を置かない）。**API 0単位**。

    帳面（`src.quota_ledger`）が読めない回は **0**（上限なし）を返します ——
    **推測で締切を遅らせないこと**（`pool_drain._trim_for_swap` と同じ考え方）。
    """
    try:
        from src import quota_ledger                           # noqa: PLC0415
        used = int(quota_ledger.spent(now).get("data") or 0)
        cap = int(quota_ledger.DAY_UNITS)
    except Exception:                                          # noqa: BLE001
        return 0
    import pool_drain                                          # noqa: PLC0415
    left = cap - used - RESERVE_UNITS
    if left <= 0:
        return 1                    # **1本だけ**（0 は「上限なし」の意味なので使えない）
    return max(1, left // pool_drain.UNITS_PER_VIDEO)


def _run(argv: list[str], label: str, timeout: int = 1800) -> int:
    print(f"[sweep] $ {' '.join(argv)}", flush=True)
    try:
        got = subprocess.run(argv, cwd=str(ROOT), timeout=timeout,
                             capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        print(f"[sweep] [!] {label} が {timeout}秒 で切れました", flush=True)
        return 124
    for line in (got.stdout or "").splitlines():
        print(f"[sweep]   {line}", flush=True)
    for line in (got.stderr or "").splitlines()[-20:]:
        print(f"[sweep]   ! {line}", flush=True)
    return got.returncode


def reasons_to_skip(now: datetime | None = None) -> str:
    """**掃かない理由**（掃いてよければ空文字）。**API 0単位**。"""
    now = now or datetime.now(timezone.utc)
    if not house_rule.same_day_only():
        return "規則5 が外れています（先の日付に置いてよい）"
    stop = _paused()
    if stop:
        return f"一時停止の印が在ります: {str(stop)[:120]}"
    v = ahead_gate.verdict(now)
    if not v["quota_open"]:
        return "日枠が尽きています（この窓では `videos.update` が通りません）"
    if v["ahead"] <= 0 and (v["seen"] or {}).get("count", 0) in (0, None):
        # 控えも実物も 0本。**実物を見ていない回は掃きます**（読みは安い）。
        if v["seen"] is not None:
            return "先の日付は 0本 です（**これが正しい状態**）"
    return ""


# ---------------------------------------------------------------- きょうの1本を置く
#
# ## なぜ掃きと同じ所に在るか（2026-09-02 夜・最適化の回）
#
# 上の3つ（関門・門・掃き）は全部 **外す側** です。**置く側は「その回が選べば撃つ」
# のまま**でした —— `run_marker.py --write` が毎周
# `python scripts/reschedule.py --move <id> <きょう>T09:00`（**明日になってから
# 撃つこと**）と印字し、`scripts/stop_check.sh` (1.4) が「きょうの1本が無い」で
# 3回 引き止める。**それだけ**です。
#
# 実測（この回に `data/runs.jsonl` を数えた）: 09/01 以降の ship 130件 のうち
# `upload` は **1件**。09/01・09/02 の「1日1本」は、どちらも**規則の前に積んだ
# 作り置き**が出ただけです。作り置きは 09/02 の掃きで 0本 になったので、
# **09/03 は、この輪が自分で「きょうの1本」を置く最初の日**です。
# 置く手が回の裁量のままなら、08/31 の固定から 459本 → 107本 にしか減らなかった
# のと同じ形で、**空く日が出ます**（`CLAUDE.md`「途切れるのが最大の損失」・
# オーナー原文「**今後こういうことが一切ないようにしろ**」）。
#
# ## 何をするか（**API 51単位**・`videos.list` 1 ＋ `videos.update` 50）
#
#     きょう（JST）の枠が空 かつ 日枠が開いている かつ 置ける時刻が残っている なら
#       `[きょうの1本]` で決めた本（`data/daily_pick.jsonl`）
#         → 無ければ 池の private の本を**形と族の数で**選ぶ（`src.daily_pick`）
#         → それも無ければ 次に出る下書き（`src.next_slot.next_video`）
#       を `scripts/reschedule.py --move <id> <きょう>T<時>:00` で置く
#
# 時刻は `config/channel.yaml` の `publish_hour_jst`。その時刻を過ぎている回は、
# **いまから `TODAY_LEAD_MIN` 分 より先の、次の正時**（`TODAY_LAST_HOUR` まで）。
# **明日には置きません**（`house_rule.refuse_future_publish` が断ります）。
#
# ## 撃たない回
#
#     きょうの枠が埋まっている       `next_slot.today_count()` ≧ `house_rule.cap()`
#     日枠が尽きている               `upload_cap.day_quota().open` が False
#     置ける時刻が残っていない       `TODAY_LAST_HOUR` を過ぎた
#     候補が1本も無い                 決めた本も、池も、下書きも無い
#     規則5 が外れている／一時停止   上の掃きと同じ
#
# ## 覆る条件
#
# - `[きょうの1本]` の決め方（`src/daily_pick.py`）が変われば、ここは自動でそれに従います
#   （ここは選びません。**決めてある本を置くだけ**。決めていない回だけ、あちらの数で選ぶ）。
# - 置いた本が 48時間 で池の中央値を下回り続けるなら、悪いのは置き方ではなく選び方です。
#   `daily_pick` を直すこと。**この手を止めないこと** —— 止めると空く日が戻ります。
# - オーナーが「先の日付にも置いてよい」と言ったら、掃きと一緒に黙ります。

#: **きょうの1本を置く手の印**（掃きの印とは別。掃きは数分、こちらは数秒）。
TODAY_LOCK = "data/.today_place.lock"
TODAY_STALE = timedelta(minutes=10)

#: **いまから最低これだけ先に置く**（YouTube は過去の `publishAt` を受けません。
#: `reschedule.py --move` も `過去の時刻です` で落ちます）。
TODAY_LEAD_MIN = 20

#: **この時（JST）より後の正時には置かない**（23時 ＝ その日の最後の枠）。
TODAY_LAST_HOUR = 23

JST = timezone(timedelta(hours=9))


def today_slot(now: datetime, hour: int, *, lead_min: int = TODAY_LEAD_MIN,
               last_hour: int = TODAY_LAST_HOUR) -> datetime | None:
    """**きょう置ける時刻（JST）。** 既定の時刻がまだ先ならそれ。過ぎていれば次の正時。
    きょうの中に残っていなければ `None`。**API 0単位・純関数。**"""
    t = now.astimezone(JST)
    edge = t + timedelta(minutes=lead_min)
    slot = t.replace(hour=int(hour), minute=0, second=0, microsecond=0)
    if slot < edge:
        slot = edge.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1)
    if slot.date() != t.date() or slot.hour > last_hour:
        return None
    return slot


def today_plan(now: datetime, *, count: int, cap: int, candidate: dict | None,
               hour: int, quota_open: bool, rule_on: bool = True,
               paused: str = "") -> dict:
    """**置くか・何を・いつ**を決める（**API 0単位・純関数**）。

    返り: `{"do": bool, "why": str, "video_id": str|None, "when": "YYYY-MM-DDTHH:00"|None}`
    """
    day = now.astimezone(JST).date().isoformat()
    if not rule_on:
        return {"do": False, "why": "規則5 が外れています（この手は規則5 の下だけ）",
                "video_id": None, "when": None}
    if paused:
        return {"do": False, "why": f"一時停止の印が在ります: {paused[:120]}",
                "video_id": None, "when": None}
    if count >= max(1, cap):
        return {"do": False, "why": f"きょう {day} の枠は埋まっています（{count}本／規則 {cap}本）",
                "video_id": None, "when": None}
    if not quota_open:
        return {"do": False, "why": "日枠が尽きています（この窓では `videos.update` が通りません）",
                "video_id": None, "when": None}
    slot = today_slot(now, hour)
    if slot is None:
        return {"do": False, "why": f"きょう {day} に置ける正時が残っていません"
                f"（{TODAY_LAST_HOUR}時 まで・いまから {TODAY_LEAD_MIN}分 より先）",
                "video_id": None, "when": None}
    vid = str((candidate or {}).get("video_id") or "")
    if not vid:
        return {"do": False, "why": "置ける本が1本も無い（決めた本も、池も、下書きも無い）",
                "video_id": None, "when": None}
    return {"do": True, "why": str((candidate or {}).get("why") or ""),
            "video_id": vid, "when": slot.strftime("%Y-%m-%dT%H:%M")}


def _today_candidate(now: datetime) -> dict | None:
    """**きょう置く本**。`[きょうの1本]` で決めた本 → 池（形と族の数で）→ 次に出る下書き。
    決めていない回に池から選んだときは、**その決定を `data/daily_pick.jsonl` に残します**
    （次の回が「機械が数で決めた」ことを読めるように）。**API 0単位。**"""
    from src import daily_pick, next_slot                      # noqa: PLC0415
    day = now.astimezone(JST).date()
    try:
        cur = daily_pick.current(day)
    except Exception:                                          # noqa: BLE001
        cur = None
    if cur and cur.get("video_id"):
        return {"video_id": cur["video_id"], "why": f"[きょうの1本] {cur.get('form')} "
                f"`{cur.get('topic')}`（{str(cur.get('why'))[:80]}）", "source": "pick"}
    # 決めていない → 形と族の数で、池から
    try:
        cmp = daily_pick.compare(now)
        forms = cmp["all"]
        best_form = max(daily_pick.FORMS,
                        key=lambda f: ((forms.get(f) or {}).get("median") or 0,
                                       (forms.get(f) or {}).get("n") or 0))
        pool = daily_pick.pool_candidates(best_form, rows=cmp["rows"])
    except Exception:                                          # noqa: BLE001
        pool, best_form, forms = [], None, {}
    if pool:
        top = pool[0]
        st = forms.get(best_form) or {}
        why = (f"決めた本が無かったので機械が数で選んだ: 形 {best_form}"
               f"（齢48h 中央値 {st.get('median')}回・n={st.get('n')}）・"
               f"族 {top.get('family')} 中央値 {top.get('fam_median')}回(n={top.get('fam_n')})")
        try:
            daily_pick.record(best_form, str(top.get("topic") or ""), why, day=day,
                              now=now, video_id=top["video_id"])
        except Exception:                                      # noqa: BLE001
            pass
        return {"video_id": top["video_id"], "why": why, "source": "pool"}
    try:
        nxt = next_slot.next_video(now)
        if nxt is None:
            got = next_slot.drafts(now)
            nxt = got[0] if got else None
    except Exception:                                          # noqa: BLE001
        nxt = None
    if nxt and nxt.get("video_id") and not nxt.get("at"):
        return {"video_id": nxt["video_id"],
                "why": f"池が空なので次に出る下書き `{nxt.get('topic')}`", "source": "draft"}
    return None


def place_today(now: datetime | None = None, *, dry_run: bool = False) -> dict:
    """**きょうの1本を、回の意思と関係なく置く。** 返りは `today_plan()` の dict に
    `rc`（撃った結果。撃っていなければ `None`）を足したもの。"""
    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(JST).strftime("%m/%d %H:%M JST")
    from src import next_slot, upload_cap                       # noqa: PLC0415
    try:
        count = int(next_slot.today_count(now))
    except Exception:                                          # noqa: BLE001
        count = 0
    try:
        quota_open = bool(upload_cap.day_quota(now).open)
    except Exception:                                          # noqa: BLE001
        quota_open = True
    hour = None
    try:
        from src import publish_hour                            # noqa: PLC0415
        hour = publish_hour.config_hour()
    except Exception:                                          # noqa: BLE001
        hour = None
    hour = 9 if hour is None else int(hour)
    cand = None
    if count < house_rule.cap() and quota_open:
        try:
            cand = _today_candidate(now)
        except Exception as exc:                               # noqa: BLE001
            print(f"[today] 候補を読めませんでした: {str(exc)[:120]}", flush=True)
    plan = today_plan(now, count=count, cap=house_rule.cap(), candidate=cand, hour=hour,
                      quota_open=quota_open, rule_on=house_rule.same_day_only(),
                      paused=_paused())
    plan["rc"] = None
    if not plan["do"]:
        print(f"[today] {stamp} きょうの1本は置きません —— {plan['why']}", flush=True)
        return plan
    print(f"[today] {stamp} **きょうの1本を置きます**: `{plan['video_id']}` → "
          f"{plan['when']} JST（{plan['why'][:160]}）", flush=True)
    if dry_run:
        print("[today] **置いていません**（`--dry-run`）", flush=True)
        return plan
    lock = Path(config.ROOT) / TODAY_LOCK
    if not take_lock(now, path=lock, stale=TODAY_STALE):
        print(f"[today] もう別の手が置きに行っています（印: `{TODAY_LOCK}`）", flush=True)
        return plan
    try:
        py = sys.executable or "python3"
        rc = _run([py, "scripts/reschedule.py", "--move", plan["video_id"], plan["when"]],
                  "reschedule --move", 300)
    finally:
        drop_lock(lock)
    plan["rc"] = rc
    if rc == 0:
        print(f"[today] **置きました**: `{plan['video_id']}` {plan['when']} JST", flush=True)
    else:
        print(f"[today] [!] 置けませんでした（rc={rc}）。次の回の SessionStart が"
              " もう一度 試します（`scripts/stop_check.sh` (1.4) も引き止めます）", flush=True)
    return plan


#: **起こした印**（`kick()` が、この時間の内なら二度 起こさない）。
KICK_MARK = "data/.ahead_sweep.kick"
KICK_EVERY = timedelta(minutes=20)
LOG = "data/ahead_sweep.log"


def kick(now: datetime | None = None, *, root: Path | None = None,
         every: timedelta | None = None) -> str:
    """**この掃き（＋きょうの1本を置く手）を、背景で起こす。** 返りは1行の理由。

    ## なぜ SessionStart フックだけでは足りないか（2026-09-02 夜・実測）

    `.claude/settings.json` の `SessionStart` は `scripts/ahead_sweep.sh` を呼びますが、
    **このコンテナに `data/ahead_sweep.log` は1つも在りません**（親の checkout にも、
    どの worktree にも）。＝ **フックからは一度も起きていません。** 周を回しているのは
    Agent ツールのサブで、サブの始まりは `SessionStart` ではない（終わりも `Stop` ではなく
    `SubagentStop`・登録 0件 —— 日誌 2026-09-02 18:5x の 3-2）。
    **フックに置いた「回の意思の外」は、この形では回の外に出ていませんでした。**

    だから、**実際に毎周 撃たれている2つの口**から起こします:

        scripts/run_marker.py --write   サブが §1 で最初に撃つ（`data/runs.jsonl` の `start`）
        scripts/next_round.py           親が毎周 撃つ（`data/rounds.jsonl`）

    どちらも自分の checkout の `data/` へ印と log を書きます。印が `KICK_EVERY` の内なら
    起こしません（同じ周の2体が同時に起こさないため。**置く手は同じ本を同じ時刻へ
    置くので、二重に走っても規則1 は破れません** —— 2度目は `videos.list` が
    「もうその値です」と言って `videos.update` を撃ちません）。

    **覆る条件**: `data/ahead_sweep.log` に `[today]` の行が SessionStart 由来で
    並ぶようになったら（＝ フックが起きる環境になったら）、ここは要りません。
    """
    now = now or datetime.now(timezone.utc)
    root = Path(root or config.ROOT)
    every = KICK_EVERY if every is None else every
    if os.environ.get("YOUTUBE_PIPELINE_CHILD"):
        return "台本生成の子プロセスなので起こしません"
    mark = root / KICK_MARK
    try:
        raw = mark.read_text(encoding="utf-8").strip()
        at = ahead_gate._parse(raw) if raw else None
        if at is not None and now - at < every:
            return f"{(now - at).total_seconds() / 60:.0f}分 前に起こしてあります（`{KICK_MARK}`）"
    except OSError:
        pass
    try:
        mark.parent.mkdir(parents=True, exist_ok=True)
        mark.write_text(now.isoformat() + "\n", encoding="utf-8")
        log = open(root / LOG, "ab")                           # noqa: SIM115
        subprocess.Popen([sys.executable or "python3", "scripts/ahead_sweep.py"],
                         cwd=str(root), stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
    except Exception as exc:                                   # noqa: BLE001
        return f"起こせませんでした: {str(exc)[:120]}"
    return f"背景で起こしました（きょうの1本を置く手 ＋ 先の日付の掃き・log は `{LOG}`）"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="先の日付の予約を、回の意思と関係なく掃く。きょうの1本も置く")
    ap.add_argument("--dry-run", action="store_true",
                    help="何をするかだけ言う（**API 0単位**）")
    ap.add_argument("--no-today", action="store_true",
                    help="きょうの1本を置く手を飛ばす（検査・切り分け用）")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    stamp = now.astimezone(timezone(timedelta(hours=9))).strftime("%m/%d %H:%M JST")
    # **置く側を先に。** 掃きは数分 かかり、日枠を食います。きょうの1本の 51単位 を
    # 先に取ること（`RESERVE_UNITS` の註と同じ向き）。
    if not args.no_today:
        try:
            place_today(now, dry_run=args.dry_run)
        except Exception as exc:                               # noqa: BLE001
            print(f"[today] [!] 置く手が落ちました: {str(exc)[:200]}", flush=True)
    why = reasons_to_skip(now)
    if why:
        print(f"[sweep] {stamp} 掃きません —— {why}", flush=True)
        # **撃てない窓でも、残件は残すこと。** 次の窓の回が拾います。
        if "日枠" in why:
            ahead_gate.main([])
        return 0

    v = ahead_gate.verdict(now)
    print(f"[sweep] {stamp} **先の日付の予約 {v['ahead']}本**（控え）。掃きます",
          flush=True)
    if args.dry_run:
        for line in v["lines"]:
            print(line, flush=True)
        print("[sweep] **数えただけです**（`--dry-run`）", flush=True)
        return 0

    if not take_lock(now):
        print("[sweep] もう別の掃きが走っています（印: "
              f"`{LOCK}`）。この回は何もしません", flush=True)
        return 0

    t0 = time.time()
    try:
        py = sys.executable or "python3"
        # 1. 実物を引く（**読んだついでに控えが実物へ合います**）
        _run([py, "scripts/ahead_gate.py", "--live"], "ahead_gate --live", 300)
        # 2. 控えと実物の食い違いを名指しする（**API 0単位**）
        _run([py, "-m", "src.ledger_truth"], "ledger_truth", 120)
        # 3. 外す（**削除しません。private の下書きへ戻すだけ**）
        #    **その日の1本のぶんを残します**（`RESERVE_UNITS` の註）——
        #    この掃きは回の意思と関係なく走るので、手加減する人がいません。
        cap = budget_max(now)
        drain = [py, "scripts/pool_drain.py", "--apply", "--keep", "0"]
        if cap:
            drain += ["--max", str(cap)]
            print(f"[sweep] この回に外すのは **最大 {cap}本**"
                  f"（その日の1本に {RESERVE_UNITS:,}単位 残します）", flush=True)
        _run(drain, "pool_drain --apply", 3600)
        # 4. 掃いたあとを、もう一度 実物で見て記録する
        _run([py, "scripts/ahead_gate.py", "--live"], "ahead_gate --live", 300)
    finally:
        drop_lock()

    after = ahead_gate.verdict()
    print(f"[sweep] **{time.time() - t0:.0f}秒。先の日付の予約 "
          f"{v['ahead']}本 → {after['ahead']}本**（控え）", flush=True)
    for line in after["lines"]:
        print(line, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
