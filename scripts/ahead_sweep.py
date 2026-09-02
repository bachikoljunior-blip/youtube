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


def _run_out(argv: list[str], label: str, timeout: int = 1800) -> tuple[int, str]:
    """`_run` と同じだが標準出力も返す（`upload_only.py` の `VIDEO_ID …` を読むため）。"""
    print(f"[sweep] $ {' '.join(argv)}", flush=True)
    try:
        got = subprocess.run(argv, cwd=str(ROOT), timeout=timeout,
                             capture_output=True, text=True)
    except subprocess.TimeoutExpired:
        print(f"[sweep] [!] {label} が {timeout}秒 で切れました", flush=True)
        return 124, ""
    for line in (got.stdout or "").splitlines():
        print(f"[sweep]   {line}", flush=True)
    for line in (got.stderr or "").splitlines()[-20:]:
        print(f"[sweep]   ! {line}", flush=True)
    return got.returncode, got.stdout or ""


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
# 時刻は `place_hour()` —— **掃く側**（`src/publish_hour.sweep_hour`・偶数日は対照、
# 奇数日は未試行の時刻）が先、根拠が無ければ `config/channel.yaml` の `publish_hour_jst`
#（2026-09-03 00:4x に直した。それまで置く側だけが 9時 固定で、掃きは助言止まりだった）。
# その時刻を過ぎている回は、
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
#: 30分 —— `videos.insert` の道（`place_by_insert`: 焼き直し 約1分 ＋ 上げ 数分）が
#: 10分 を超えることがあるため（2026-09-03 に 10分 → 30分）。
TODAY_STALE = timedelta(minutes=30)

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


def place_hour(day, *, sweep=None, config=None) -> int:
    """**その日に置く時刻（JST の時）。** 掃く側（`publish_hour.sweep_hour`）が先、
    根拠が無ければ `config/channel.yaml` の既定、それも無ければ 9。**API 0単位。**

    ## なぜ `config_hour()` だけではいけないか（2026-09-03 00:4x に踏んだ）

    `src/publish_hour.sweep_hour()` は 09/01 に「**偶数日は対照（9時）・奇数日は
    未試行の時刻**」と交互に置く形で足され、`scripts/slot_gate.py` はその時刻を
    回に**助言**していました。ところが 09/02 に置く手そのものが回の裁量から
    この関数（`place_today`）へ移り、**ここは `config_hour()`（9時 固定）しか
    読んでいませんでした** —— 助言する側は掃き、置く側は掃かない。
    「**言っている所と、している所が別**」（`src/publish_hour.py` 冒頭が名指しした、
    この repo でいちばん多い壊れ方）が、道具を1段 移した日にそのまま再発していました。

    実測 09/03 00:4x: `sweep_hour(2026-09-04)` は **17時**、機械が置くのは **9時**。
    規則の密度で一度も試していない時刻は **20／24** のまま（`python -m src.publish_hour`）。
    1日1本 ＝ 1日に1点しか増えないので、置く側が掃かない限り**永久に 0本** です。

    `sweep`／`config` は検査のための差し替え口（省略時は `src.publish_hour` の実物）。

    ## 覆る条件

    - 前提（`config/hypotheses.yaml` の「公開時刻は per_video に効かない」）が閉じたら、
      `sweep_hour()` 自身が対照だけを返すようになります。ここは変えなくてよい
    - `sweep_hour()` が `None`（対照が `MIN_N` に届かない）のあいだは、既定に倒れます
    """
    # **正本は `src/publish_hour.place_hour`**（2026-09-03 02:5x に寄せた —— 同じ順が
    # ここ・`daily_pick._hour_default`・`next_slot._move_lines` の3か所に書かれ、1か所だけ
    # 古かった。順はあちらに1回だけ書く。ここは検査の差し替え口を残して呼ぶだけ）。
    try:
        from src import publish_hour                            # noqa: PLC0415
        return publish_hour.place_hour(day, sweep=sweep, config=config)
    except Exception:                                          # noqa: BLE001
        pass
    h = None
    try:
        h = sweep(day) if sweep else None
    except Exception:                                          # noqa: BLE001
        h = None
    if h is None:
        try:
            h = config() if config else None
        except Exception:                                      # noqa: BLE001
            h = None
    return 9 if h is None else int(h)


def today_plan(now: datetime, *, count: int, cap: int, candidate: dict | None,
               hour: int, quota_open: bool, rule_on: bool = True,
               paused: str = "", insert_ok: bool = False) -> dict:
    """**置くか・何を・いつ**を決める（**API 0単位・純関数**）。

    返り: `{"do": bool, "why": str, "video_id": str|None, "when": "YYYY-MM-DDTHH:00"|None,
            "via": "update" | "insert"}`

    `insert_ok=True` は「その本は `videos.insert` で置き直せる」の印
    （台本の控え `data/critique_queue/<ID>.script.json` が在る）。**日枠が尽きていても、
    その道なら置けます** —— `videos.insert` は日枠を使いません（`src/upload_cap.day_quota`
    の註・08/27 に 403 の後で 3本 通った実測）。印が無ければ従来どおり置きません。
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
    if not quota_open and not insert_ok:
        return {"do": False, "why": "日枠が尽きています（この窓では `videos.update` が通りません。"
                "台本の控えも無いので `videos.insert` でも置き直せません）",
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
            "video_id": vid, "when": slot.strftime("%Y-%m-%dT%H:%M"),
            "via": "insert" if (not quota_open and insert_ok) else "update"}


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
    # 決めていない → 形は**収益化の門に近い側**（`daily_pick.fallback_form`・2026-09-03 夜。
    #     それまで「齢48h の中央値の大きい形」で選んでいた ＝ 毎日ショート。ショートの視聴時間は
    #     4,000時間 の門に 0 入る —— `daily_pick.gate_arithmetic` の註）。同じ形の中では
    #     外の作りの下書き（`style: outside_long`）を先に、あとは族の数で。
    try:
        cmp = daily_pick.compare(now)
        forms = cmp["all"]
        best_form = daily_pick.fallback_form(cmp)
        pool = daily_pick.outside_first(daily_pick.pool_candidates(best_form, rows=cmp["rows"]))
    except Exception:                                          # noqa: BLE001
        pool, best_form, forms = [], None, {}
    if pool:
        top = pool[0]
        st = forms.get(best_form) or {}
        why = (f"決めた本が無かったので機械が数で選んだ: 形 {best_form}"
               f"（収益化の門に近い側・`daily_pick.gate_arithmetic`／齢48h 中央値 {st.get('median')}回・n={st.get('n')}）・"
               f"族 {top.get('family')} 残差 ×{top.get('fam_res')}"
               f"（生 {top.get('fam_median')}回・n={top.get('fam_n')}）")
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


STASH = "data/critique_queue"


def stash_script(video_id: str, root: Path | None = None) -> Path | None:
    """その本を**焼き直せる台本の控え**（`critique_queue.stash()` が残す）。無ければ `None`。"""
    if not video_id:
        return None
    f = Path(root or config.ROOT) / STASH / f"{video_id}.script.json"
    return f if f.exists() else None


def _uploaded_row(video_id: str) -> dict | None:
    """`data/uploaded.jsonl` の、その本の（いちばん新しい）行 —— 題材と尺。"""
    import json                                                # noqa: PLC0415
    f = Path(config.ROOT) / "data" / "uploaded.jsonl"
    try:
        lines = f.read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    hit = None
    for ln in lines:
        try:
            r = json.loads(ln)
        except Exception:                                      # noqa: BLE001
            continue
        if r.get("video_id") == video_id:
            hit = r
    return hit


def place_by_insert(plan: dict, now: datetime) -> tuple[int, str | None]:
    """**`videos.update` が撃てない窓で、きょうの1本を `videos.insert` で置く**（2026-09-03 00:1x）。

    返りは `(rc, 新しい動画ID or None)`。

    ## なぜ要るか（同じ夜に実測）

    09/03 00:03 JST の `[today]` は `reschedule.py --move OBJdXEr6gLg 2026-09-03T09:00` を
    撃ち、**帳面の取り置き**（`upload_cap._ledger_hold`: 使った 12,368 ／ 枠 10,000）で
    止められました。窓が変わるのは **16:00 JST** —— 既定の枠 **09:00** はその 7時間 前です。
    ＝ **前の日の夕方に帳面が焼けた日は、翌朝の1本が毎回 置けません**（09/01 も同じ形）。
    規則5 は「作るのは前の日・予約だけが当日」なので、**当日の朝に `videos.update` が
    要る作り**そのものが、この窓と噛み合っていませんでした。

    `videos.insert` は日枠を使いません（`src/upload_cap.day_quota` の註・
    `tests/test_insert_never_marked_ok.py`）。**同じ台本（`critique_queue/<ID>.script.json`）を
    `--script` で焼き直せば `claude -p` も要らず（約1分）、`upload_only.py <題材> "" "<日>@<時>"`
    が `publishAt` 付きで上げます。** 実測 09/03 00:08 JST: `9zkfjEH48PY` が 09:00 JST に載った
    （回が手で撃った。ここはそれを機械へ移したもの）。
    古い下書きは `--replaces` で突き合わせから外すだけで、**消しません**（private の池に残る）。

    ## 覆る条件

    - `videos.insert` が同じ 403 で落ちるようになったら（枠が1つに統合された）、この道は
      閉じます。そのときは `day_quota()` の註と `RESERVE_UNITS` の覆る条件も同じ日に発火します
    - 置く既定の時刻が窓の切り替わり（16:00 JST）より後になったら、この道はほぼ要りません
    """
    vid = str(plan.get("video_id") or "")
    script = stash_script(vid)
    if script is None:
        print(f"[today] [!] `{vid}` の台本の控えが無いので、`videos.insert` では置き直せません",
              flush=True)
        return 2, None
    row = _uploaded_row(vid) or {}
    topic = str(row.get("topic") or "")
    if not topic:
        print(f"[today] [!] `{vid}` の題材が `data/uploaded.jsonl` に無いので置き直せません",
              flush=True)
        return 2, None
    try:
        from src import daily_pick                              # noqa: PLC0415
        cur = daily_pick.current(now.astimezone(JST).date()) or {}
    except Exception:                                          # noqa: BLE001
        cur = {}
    form = str(cur.get("form") or "")
    if not form:
        dur = float(row.get("duration_s") or 0)
        form = "ショート" if 0 < dur <= 60 else "長尺"
    py = sys.executable or "python3"
    argv = [py, "-m", "src.pipeline", "--script", str(script), "--topic", topic, "--dry-run"]
    if form == "ショート":
        argv.append("--short")
    rc = _run(argv, "pipeline --script（焼き直し）", 1500)
    if rc != 0:
        return rc, None
    day, hm = str(plan["when"]).split("T")
    rc, out = _run_out([py, "scripts/upload_only.py", topic, "", f"{day}@{hm}",
                        "--replaces", vid], "upload_only（insert・publishAt）", 1200)
    if rc != 0:
        return rc, None
    new_id = None
    for ln in out.splitlines():
        if ln.startswith("VIDEO_ID "):
            new_id = ln.split(None, 1)[1].strip()
    if not new_id:
        print("[today] [!] `upload_only` は通ったが `VIDEO_ID` が読めません", flush=True)
        return 3, None
    try:
        from src import daily_pick                              # noqa: PLC0415
        daily_pick.record(
            form, topic,
            f"{now.astimezone(JST).strftime('%H:%M')} 機械: 帳面の取り置き（日枠 10,000）で "
            f"`--move {vid}` が書けず、同じ台本を焼き直して `videos.insert`（日枠 0単位）で "
            f"{plan['when']} JST に置いた。{vid} は private の池",
            day=now.astimezone(JST).date(), now=now, video_id=new_id)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[today] 決定を書き換えられませんでした（置けてはいます）: {str(exc)[:100]}",
              flush=True)
    return 0, new_id


def place_today(now: datetime | None = None, *, dry_run: bool = False) -> dict:
    """**きょうの1本を、回の意思と関係なく置く。** 返りは `today_plan()` の dict に
    `rc`（撃った結果。撃っていなければ `None`）を足したもの。

    置く道は2つ。`videos.update`（`reschedule --move`・50単位）が既定で、
    **日枠が尽きている／帳面の取り置きが止める窓**では `videos.insert`（`place_by_insert`・
    日枠 0単位）へ倒れます —— その本の台本の控えが在るときだけ。"""
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
    hour = place_hour(now.astimezone(JST).date())
    cand = None
    if count < house_rule.cap():
        # **日枠が尽きていても候補は読む**（0単位）—— `videos.insert` の道が在るかは
        # 候補が決まって初めて分かります（`place_by_insert` の註）。
        try:
            cand = _today_candidate(now)
        except Exception as exc:                               # noqa: BLE001
            print(f"[today] 候補を読めませんでした: {str(exc)[:120]}", flush=True)
    insert_ok = stash_script(str((cand or {}).get("video_id") or "")) is not None
    plan = today_plan(now, count=count, cap=house_rule.cap(), candidate=cand, hour=hour,
                      quota_open=quota_open, rule_on=house_rule.same_day_only(),
                      paused=_paused(), insert_ok=insert_ok)
    plan["rc"] = None
    if plan["do"] and plan.get("via") == "update" and insert_ok:
        # **帳面の取り置きが `videos.update` を止める窓**（403 はまだ見ていないが、
        # `reschedule._update` は `reserve_hold()` で `SystemExit` する）。撃つ前に同じ門に
        # 訊いて、止まるなら最初から `videos.insert` の道へ（実測 09/03 00:03 の形）。
        try:
            held = upload_cap.reserve_hold(now)
        except Exception:                                      # noqa: BLE001
            held = None
        if held:
            plan["via"] = "insert"
            plan["why"] = f"{plan['why']}／`videos.update` は取り置きで止まる → insert"
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
        if plan.get("via") == "insert":
            rc, new_id = place_by_insert(plan, now)
            if new_id:
                plan["placed_id"] = new_id
        else:
            rc = _run([py, "scripts/reschedule.py", "--move", plan["video_id"], plan["when"]],
                      "reschedule --move", 300)
    finally:
        drop_lock(lock)
    plan["rc"] = rc
    if rc == 0:
        print(f"[today] **置きました**: `{plan.get('placed_id') or plan['video_id']}` "
              f"{plan['when']} JST（{plan.get('via', 'update')}）", flush=True)
    else:
        print(f"[today] [!] 置けませんでした（rc={rc}）。次の回の SessionStart が"
              " もう一度 試します（`scripts/stop_check.sh` (1.4) も引き止めます）", flush=True)
    return plan


# ---------------------------------------------------------------- きょうの1本のサムネイル
#
# ## なぜ要るか（2026-09-03 03:xx JST・最適化の回。「最適化されてんの？」→ いいえ の理由を1つ潰す）
#
# 09/04 の1本（`6PKux5HNnUE`・外の作りを写した長尺 19.6分）は `videos.insert` で上げた本で、
# **`thumbnail_set: False`** のまま池に在ります（帳面が焼けた窓で `thumbnails.set` だけ 403）。
# `place_today` は 17:00 JST にその本を枠へ置きますが、**サムネイルは押しません**。
# 押す口は3つ在って、3つとも この日には起きません:
#
#     pool_drain.thumbnail_first()     `pool_drain --apply` の頭 —— 掃きは「先の日付 0本」で
#                                      `reasons_to_skip` が返すので、規則5 の下では **毎日 走らない**
#     refresh_thumbnail --missing --video   日誌の「次の回へ 2.」（**書き置き** ＝ 人の記憶）
#     uploader._set_thumbnail          上げた瞬間だけ。窓が閉じていれば 403 で終わり
#
# ＝ **`eta.py` が「引けるのは `per_video` だけ・天井を ×21.88」と名指しし、その唯一の試験
# （前提「外の作り方を写した長尺」・門 100回/48h）に出る本が、サムネイル無しで出る形でした。**
# 長尺の露出は 検索／おすすめ のサムネイルで決まります（ショートのフィードとは違う）——
# 試験の本にだけ無いなら、外れても「作り」の外れとは読めません（試験が壊れる）。
#
# だから **置く手と同じ口**（`place_today` の直後・毎周 起こされる）で、**きょう出る1本**の
# サムネイルが控えに在って載っていなければ、その1本だけ押します（**50単位**・
# `refresh_thumbnail.push_missing(only_video=…)`。門はあちらのまま: 日枠・取り置き）。
#
# ## 覆る条件
#
# - `uploader._set_thumbnail` が窓の外でも通るようになったら（枠が統合された）、ここは要りません
# - 押す先が「きょうの1本」以外に広がったら（例: 先の日付の本）、それは `pool_drain.thumbnail_first`
#   の仕事です。**ここは1日1本・50単位 以上は撃ちません**
# - `critique_queue.missing_thumbnail()` が `None`（分からない）を返すようになったら、
#   ここも「分からない本は押さない」のままにすること（全部を押しに行かないため）


def today_video_id(now: datetime, plan: dict | None = None) -> str:
    """**きょう（JST）公開される本の ID**（無ければ空文字）。**API 0単位。**

    置いた本（`place_today` の返り）が先。無ければ控えの「次に公開される本」で、
    その `at` がきょうのものだけ（明日の本は押さない —— 規則5 の下では在りませんが、
    在っても `pool_drain.thumbnail_first` の仕事です）。"""
    plan = plan or {}
    if plan.get("rc") == 0:
        vid = str(plan.get("placed_id") or plan.get("video_id") or "")
        if vid:
            return vid
    try:
        from src import next_slot                              # noqa: PLC0415
        nxt = next_slot.next_video(now) or {}
        at = nxt.get("at")
        if isinstance(at, str):
            at = next_slot._parse(at)
        if at is not None and at.astimezone(JST).date() == now.astimezone(JST).date():
            return str(nxt.get("video_id") or "")
    except Exception:                                          # noqa: BLE001
        pass
    return ""


def thumb_today(now: datetime | None = None, *, plan: dict | None = None,
                dry_run: bool = False, missing=None, quota_open=None, push=None) -> str:
    """**きょう出る1本のサムネイルが載っていなければ、その1本だけ押す**（50単位）。
    返りは1行の理由（押した／押さない／押せなかった）。

    `missing`／`quota_open`／`push` は検査のための差し替え口（省略時は実物:
    `critique_queue.missing_thumbnail()`／`upload_cap.day_quota().open`／
    `refresh_thumbnail.push_missing(only_video=…)`）。"""
    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(JST).strftime("%m/%d %H:%M JST")
    vid = today_video_id(now, plan)
    if not vid:
        line = "きょう公開される本が無い（置いていない・控えにも無い）"
        print(f"[thumb-today] {stamp} 押しません —— {line}", flush=True)
        return line
    if missing is None:
        try:
            import critique_queue                              # noqa: PLC0415
            missing = [r["video_id"] for r in critique_queue.missing_thumbnail()]
        except Exception as exc:                               # noqa: BLE001
            missing = []
            print(f"[thumb-today] 控えを読めませんでした: {str(exc)[:100]}", flush=True)
    if vid not in set(missing or []):
        line = f"`{vid}` はサムネイルが載っている（か、控えに無い）"
        print(f"[thumb-today] {stamp} 押しません —— {line}", flush=True)
        return line
    if quota_open is None:
        try:
            from src import upload_cap                          # noqa: PLC0415
            quota_open = bool(upload_cap.day_quota(now).open)
        except Exception:                                      # noqa: BLE001
            quota_open = True
    if not quota_open:
        line = f"`{vid}` のサムネイルは載っていないが、日枠が尽きている（次の窓の回が押す）"
        print(f"[thumb-today] {stamp} 押しません —— {line}", flush=True)
        return line
    if dry_run:
        line = f"`{vid}` のサムネイルを押します（`--dry-run` なので押していません）"
        print(f"[thumb-today] {stamp} {line}", flush=True)
        return line
    if push is None:
        def push(video_id: str) -> int:
            import refresh_thumbnail                           # noqa: PLC0415
            return int(refresh_thumbnail.push_missing(only_video=video_id))
    print(f"[thumb-today] {stamp} **きょうの1本 `{vid}` のサムネイルを押します**（50単位）",
          flush=True)
    try:
        rc = int(push(vid))
    except Exception as exc:                                   # noqa: BLE001
        line = f"`{vid}` のサムネイルを押せませんでした: {str(exc)[:120]}"
        print(f"[thumb-today] [!] {line}", flush=True)
        return line
    line = (f"`{vid}` に載せました" if rc == 0
            else f"`{vid}` は押せませんでした（rc={rc}・控えは残る。次の回がもう一度 押す）")
    print(f"[thumb-today] {line}", flush=True)
    return line


def comment_pending(now: datetime | None = None, *, dry_run: bool = False,
                    pending=None, quota_open=None, run=None) -> str:
    """**公開ずみで最初のコメントの無い本に、コメントを付ける**（1本 50単位）。返りは1行の理由。

    ## なぜここに在るか（2026-09-03 04:xx に踏んだ）

    規則5（下書きで上げ、当日に予約）の下では**全部の本が private で上がる**ので、
    `uploader._post_actions` の `commentThreads.insert` は毎本 403 で落ち、拾い直しは
    `scripts/post_pending_comments.py` だけです。**その道具は `build/` を読んでいて、
    まっさらなコンテナには `build/` が無い**（`.gitignore`）—— 申し送りが 6周 続けて
    「16:00 以降の回で撃て」と運び、撃たれても 0本 でした（`retro.py` の持ち越し・
    実物に当たった回 0／`data/api_calls.jsonl` 08/31〜 `commentThreads` 0件）。

    **「16:00 以降に撃つ」を回が憶えておく形は、6周で 0本 です。** `place_today` /
    `thumb_today` と同じ理由で、この掃きの中へ移しました —— `kick()` から 20分ごと。
    控えに未処理の本が無ければ **API 0単位**（`pending` が空なら呼びません）。

    `pending`／`quota_open`／`run` は検査のための差し替え口（省略時は実物:
    `critique_queue.pending_first_comments()`／`upload_cap.day_quota().open`／
    `_run([... scripts/post_pending_comments.py])`）。
    """
    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(JST).strftime("%m/%d %H:%M JST")
    if pending is None:
        try:
            import critique_queue                              # noqa: PLC0415
            pending = critique_queue.pending_first_comments()
        except Exception as exc:                               # noqa: BLE001
            pending = []
            print(f"[comment] 控えを読めませんでした: {str(exc)[:100]}", flush=True)
    if not pending:
        line = "控えに、最初のコメントの未処理な本はありません（API 0単位）"
        print(f"[comment] {stamp} 付けません —— {line}", flush=True)
        return line
    if quota_open is None:
        try:
            from src import upload_cap                          # noqa: PLC0415
            quota_open = bool(upload_cap.day_quota(now).open)
        except Exception:                                      # noqa: BLE001
            quota_open = True
    if not quota_open:
        line = (f"未処理 {len(pending)}本 あるが、日枠が尽きている（次の窓の回が付ける）")
        print(f"[comment] {stamp} 付けません —— {line}", flush=True)
        return line
    argv = [sys.executable or "python3", "scripts/post_pending_comments.py"]
    if dry_run:
        argv.append("--dry-run")
    if run is None:
        run = lambda a: _run(a, "post_pending_comments", 600)  # noqa: E731
    print(f"[comment] {stamp} **未処理 {len(pending)}本。公開ずみの本に最初のコメントを付けます**"
          f"（1本 50単位{'・`--dry-run`' if dry_run else ''}）", flush=True)
    try:
        rc = int(run(argv))
    except Exception as exc:                                   # noqa: BLE001
        line = f"付ける手が落ちました: {str(exc)[:120]}"
        print(f"[comment] [!] {line}", flush=True)
        return line
    line = ("付ける手を通しました（付いた本は控えに印）" if rc == 0
            else f"付ける手が rc={rc} で戻りました（控えは残る。次の回がもう一度 通す）")
    print(f"[comment] {line}", flush=True)
    return line


#: **起こした印**（`kick()` が、この時間の内なら二度 起こさない）。
# ---------------------------------------------------------------- 決めた本の焼き直し（規則3 を機械へ）
#
# ## なぜ要るか（2026-09-03 05:xx JST・最適化の回。「最適化されてんの？」→ いいえ の理由を1つ潰す）
#
# 規則3（次の枠で出る1本を、出る瞬間まで良くし続ける）の**物が変わる1手**は焼き直しです
# （`pipeline --script … --dry-run` → `upload_only.py <題材> --draft --replaces <旧ID>`）。
# ところがその手は `[きょうの1本]` が**印字するだけ**で、撃つかどうかは回の裁量でした。
# 実測（`data/runs.jsonl` 08/29〜09/03・ship 282件）: `fix` 200（71%）／ `improve` 20。
# 印字された手が撃たれなかった例は繰り返し在ります —— 「外せ」（459本 → 2日で 107本）、
# 最初のコメント（申し送り 6周・実物 0回）、`SessionStart` フック（一度も起きていない）。
# 09/04 の試験の本（`6PKux5HNnUE`・唯一の腕 `per_video` の前提）は、冒頭を外の型に直した台本が
# `data/scripts/` に在るのに、焼き直しは「16:00 以降の回が撃てば」の形でした。
#
# だから **置く手と同じ口**（毎周 起こされる `kick` → `main`）で、
# 決めた本の**台本の控え**（`data/critique_queue/<ID>.script.json`・上げたときの写し）と
# **手元の台本**（`data/scripts/<題材>.script.json`）が違えば、背景で焼き直して差し替えます。
# 撃った結果、`upload_only` が決めを新しい ID へ写す（`daily_pick.replace_video`）ので、
# 置く手はそのまま新しい本を枠へ置きます。
#
# ## 門（撃たない条件。全部 0単位で決める）
#
#     決めが無い／控えか台本が無い    何も分からないので撃たない
#     中身が同じ                      焼いても1バイトも変わらない
#     台本が控えより新しくない        古い台本で新しい本を上書きしない（`git log` の時刻 対 `uploaded_at`・
#                                     未 commit の変更は「新しい」と読む）
#     同じ台本（sha）を一度 試した     verify で落ちた台本を毎周 40分ずつ焼かない（印は機械にひとつ・
#                                     `_rebake_marks_dir()`）
#     もう予約が付いている            `--replaces` が断る側（private・予約なし だけ外せる）
#     枠まで `REBAKE_LEAD` 未満         焼き上がる前に出てしまう
#
# 上げるのは `videos.insert`（日枠の 403 の窓でも通っていた・09/03 00:09 実測）。
# 同時に走らないよう、機械にひとつの錠（`rebake.lock`・flock）を焼く側が持ちます。
#
# ## 覆る条件
#
# - 焼き直した本と しない本の 48h に差が無いと分かったら（前提「外の作り方を写した長尺」の n が 3 を超えたところで
#   `daily_pick` が数える）、この手は台本の差ではなく「決めが変わった日」だけに絞ること
# - `data/rebake.jsonl` に `rc != 0` が3件 続いたら、焼く側（pipeline／upload_only）の欠陥。ここを止めるのではなく直す
# - 1日に 2回 以上 焼いた日が続くなら、台本を小刻みに commit する回のほう（`REBAKE_MAX_PER_DAY`）

#: 枠までこれより短ければ焼かない（合成 ＋ 64コマ の描画 ＋ 上げ ≈ 40〜60分）
REBAKE_LEAD = timedelta(minutes=100)
#: 同じ日に焼き直す上限（`videos.insert` 1本ぶんの上げ・TTS の費用・帳面）
REBAKE_MAX_PER_DAY = 2
REBAKE_LEDGER = "data/rebake.jsonl"
REBAKE_LOG = "data/rebake.log"


def _rebake_marks_dir() -> Path:
    """**同じ台本を二度 焼かない印の置き場**（機械にひとつ）。作業コピーごとに `data/` は
    別なので、`.git` の共通の場所（`src/history._git_common_dir`）に置く。取れなければ `data/`。"""
    try:
        from src import history                                # noqa: PLC0415
        common = history._git_common_dir()
    except Exception:                                          # noqa: BLE001
        common = None
    base = (common or (Path(config.ROOT) / "data")) / "rebake"
    try:
        base.mkdir(parents=True, exist_ok=True)
    except OSError:
        pass
    return base


def _canon(text: str) -> str:
    """台本の中身を、空白や鍵の順に依らない1つの字にする。"""
    import json                                                # noqa: PLC0415
    try:
        return json.dumps(json.loads(text), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    except Exception:                                          # noqa: BLE001
        return (text or "").strip()


def script_sha(text: str) -> str:
    import hashlib                                             # noqa: PLC0415
    return hashlib.sha1(_canon(text).encode("utf-8")).hexdigest()[:12]


def draft_newer_than(draft: Path, uploaded_at: str | None, root: Path | None = None) -> bool | None:
    """**手元の台本が、上げた本より新しいか。** 未 commit の変更が在れば `True`。
    commit 済みなら `git log -1` の時刻 対 `uploaded_at`。分からなければ `None`（撃たない側）。"""
    root = Path(root or config.ROOT)
    try:
        rel = str(draft.resolve().relative_to(root.resolve()))
    except ValueError:
        rel = str(draft)
    try:
        st = subprocess.run(["git", "status", "--porcelain", "--", rel], cwd=str(root),
                            capture_output=True, text=True, timeout=30)
        if st.returncode == 0 and st.stdout.strip():
            return True
        lg = subprocess.run(["git", "log", "-1", "--format=%cI", "--", rel], cwd=str(root),
                            capture_output=True, text=True, timeout=30)
        committed = ahead_gate._parse(lg.stdout.strip()) if lg.returncode == 0 else None
    except Exception:                                          # noqa: BLE001
        return None
    up = ahead_gate._parse(uploaded_at) if uploaded_at else None
    if committed is None or up is None:
        return None
    return committed > up


def rebake_plan(*, cur: dict | None, stash_text: str | None, draft_text: str | None,
                draft_newer: bool | None, attempted: bool, scheduled: bool,
                slot_at: datetime | None, now: datetime, baked_today: int = 0,
                lead: timedelta = REBAKE_LEAD, max_per_day: int = REBAKE_MAX_PER_DAY) -> dict:
    """**焼き直すかを決める（純関数・API 0単位）。** 返りは `{do, why, sha, video_id, topic}`。"""
    out = {"do": False, "why": "", "sha": "", "video_id": str((cur or {}).get("video_id") or ""),
           "topic": str((cur or {}).get("topic") or "")}
    if not cur or not out["video_id"] or not out["topic"]:
        out["why"] = "決めた本が無い（`[きょうの1本]` が ID と題材で名指ししていない）"
        return out
    if stash_text is None:
        out["why"] = f"`{out['video_id']}` の台本の控えが無い（`data/critique_queue/`）"
        return out
    if draft_text is None:
        out["why"] = f"手元の台本 `data/scripts/{out['topic']}.script.json` が無い"
        return out
    out["sha"] = script_sha(draft_text)
    if _canon(stash_text) == _canon(draft_text):
        out["why"] = f"控えと台本は同じ中身（sha {out['sha']}）—— 焼いても変わらない"
        return out
    if scheduled:
        out["why"] = f"`{out['video_id']}` にはもう予約が付いている（`--replaces` が断る側）"
        return out
    if draft_newer is not True:
        out["why"] = ("台本が控えより新しいと言えない（commit の時刻 ≤ 上げた時刻・"
                      "古い台本で上書きしない）")
        return out
    if attempted:
        out["why"] = f"同じ台本（sha {out['sha']}）は一度 焼いた（印 `_rebake_marks_dir()`）—— verify の赤なら台本を直すこと"
        return out
    if baked_today >= max_per_day:
        out["why"] = f"きょう既に {baked_today}回 焼いた（上限 {max_per_day}）"
        return out
    if slot_at is None:
        out["why"] = "きょうの中に置ける枠が残っていない"
        return out
    if slot_at - now < lead:
        out["why"] = (f"枠 {slot_at.astimezone(JST).strftime('%m/%d %H:%M')} JST まで "
                      f"{(slot_at - now).total_seconds() / 60:.0f}分 —— 焼き上がる前に出る（要る {lead.total_seconds() / 60:.0f}分）")
        return out
    out["do"] = True
    out["why"] = (f"控え（上げたときの写し）と台本 `data/scripts/{out['topic']}.script.json` が違う"
                  f"（sha {out['sha']}・台本のほうが新しい）→ 焼き直して `{out['video_id']}` を差し替える")
    return out


def _rebake_rows(root: Path | None = None) -> list[dict]:
    import json                                                # noqa: PLC0415
    f = Path(root or config.ROOT) / REBAKE_LEDGER
    rows: list[dict] = []
    try:
        for ln in f.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(ln))
            except Exception:                                  # noqa: BLE001
                continue
    except OSError:
        pass
    return rows


def _rebake_note(row: dict, root: Path | None = None) -> None:
    import json                                                # noqa: PLC0415
    f = Path(root or config.ROOT) / REBAKE_LEDGER
    try:
        f.parent.mkdir(parents=True, exist_ok=True)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
    except OSError:
        pass


#: 決めが在る先の日を、きょうの他に何日ぶん見るか（2026-09-03 05:xx・最適化の回）。
#: 09/05 の本 `dRZnZrRy2Lw` は 09/03 の時点で冒頭が旧の型のまま決まっていて、`for_day()` だけを見る形だと
#: 09/04 17:00 に 09/04 の枠が埋まるまで**誰も焼き直さない**（規則3 の「出る瞬間まで良くし続ける」が、
#: 手前の1日ぶんしか効かない）。先の決めも同じ門で見れば、直した台本は commit した次の周に本になる。
REBAKE_DAYS_AHEAD = 2
#: 焼く印（`_rebake_marks_dir()/<ID>-<sha>`）が「まだ焼いている」と読める上限。これより古く、帳面に
#: `done` が無ければ、焼く側が途中で死んだ（容器の回収・親の畳み）と読んで、もう一度 焼く。
REBAKE_MARK_STALE = timedelta(hours=3)


def rebake_attempted(vid: str, sha: str, *, now: datetime, root: Path | None = None) -> bool:
    """**同じ台本（sha）を一度 焼いたか。** 印が在って、帳面に `done` が在る（rc を問わない）か、
    印が `REBAKE_MARK_STALE` より若い（＝いま焼いている）なら True。
    印だけ在って `done` が無く古い ＝ 焼く側が途中で死んだ → False（もう一度 焼く）。"""
    if not sha or not vid:
        return False
    mark = _rebake_marks_dir() / f"{vid}-{sha}"
    if not mark.exists():
        return False
    for r in _rebake_rows(root):
        if r.get("kind") == "done" and r.get("video_id") == vid and r.get("sha") == sha:
            return True
    try:
        raw = mark.read_text(encoding="utf-8").strip()
        at = ahead_gate._parse(raw) if raw else None
    except OSError:
        at = None
    if at is None:
        return True
    return (now - at) < REBAKE_MARK_STALE


def rebake_plan_for(day, now: datetime, *, root: Path | None = None) -> dict:
    """その日の決めた本について `rebake_plan()` を組む（読むだけ・0単位）。"""
    from src import daily_pick, next_slot                      # noqa: PLC0415
    root = Path(root or config.ROOT)
    cur = daily_pick.current(day)
    vid = str((cur or {}).get("video_id") or "")
    topic = str((cur or {}).get("topic") or "")
    stash = stash_script(vid, root) if vid else None
    draft = root / "data" / "scripts" / f"{topic}.script.json" if topic else None
    stash_text = stash.read_text(encoding="utf-8") if stash else None
    draft_text = draft.read_text(encoding="utf-8") if (draft and draft.exists()) else None
    up = _uploaded_row(vid) if vid else None
    newer = draft_newer_than(draft, (up or {}).get("uploaded_at"), root) if (draft_text and draft) else None
    scheduled = False
    try:
        r = next_slot.latest_rows().get(vid) if vid else None
        scheduled = bool(r and r.get("at"))
    except Exception:                                          # noqa: BLE001
        scheduled = False
    sha = script_sha(draft_text) if draft_text else ""
    attempted = rebake_attempted(vid, sha, now=now, root=root)
    today_s = now.astimezone(JST).date().isoformat()
    baked_today = sum(1 for r in _rebake_rows(root)
                      if r.get("kind") == "start" and str(r.get("at", ""))[:10] == today_s)
    t = now.astimezone(JST)
    if day == t.date():
        slot_at = today_slot(now, place_hour(day))
    else:
        slot_at = datetime(day.year, day.month, day.day, place_hour(day), tzinfo=JST)
    plan = rebake_plan(cur=cur, stash_text=stash_text, draft_text=draft_text, draft_newer=newer,
                       attempted=attempted, scheduled=scheduled, slot_at=slot_at, now=now,
                       baked_today=baked_today)
    plan["for_day"] = day.isoformat()
    plan["decided"] = bool(cur)
    return plan


def rebake_today(now: datetime | None = None, *, dry_run: bool = False) -> dict:
    """**決めた本の台本が、上げたときより良くなっていれば、背景で焼き直して差し替える。**
    見るのは `for_day()` の日と、その先 `REBAKE_DAYS_AHEAD` 日の決め（先の決めは決めが在る日だけ）。
    返りは最初に「焼く」と出た日の `rebake_plan()` の dict（無ければ最初の日のもの）に `started` を足したもの。
    **決めるのは 0単位。** 起こすのは1周に1本（錠は焼く側が持つ）。"""
    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(JST).strftime("%m/%d %H:%M JST")
    from src import daily_pick                                 # noqa: PLC0415
    root = Path(config.ROOT)
    try:
        first = daily_pick.for_day(now)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[rebake] {stamp} 決めを読めませんでした: {str(exc)[:120]}", flush=True)
        return {"do": False, "started": False, "why": "決めを読めない"}
    days = [first + timedelta(days=i) for i in range(REBAKE_DAYS_AHEAD + 1)]
    chosen: dict | None = None
    head: dict | None = None
    for i, day in enumerate(days):
        try:
            plan = rebake_plan_for(day, now, root=root)
        except Exception as exc:                               # noqa: BLE001
            print(f"[rebake] {stamp} {day.isoformat()} の決めを読めませんでした: {str(exc)[:120]}", flush=True)
            continue
        if i > 0 and not plan.get("decided"):
            continue                                           # 先の日は決めが在るときだけ
        head = head or plan
        if plan["do"] and chosen is None:
            chosen = plan
        else:
            print(f"[rebake] {stamp} {day.isoformat()} は焼き直しません —— {plan['why']}", flush=True)
    plan = chosen or head or {"do": False, "why": "決めが無い", "video_id": "", "topic": "", "sha": ""}
    plan["started"] = False
    if not plan["do"]:
        return plan
    vid, topic, sha = plan["video_id"], plan["topic"], plan["sha"]
    day_s = plan.get("for_day", first.isoformat())
    print(f"[rebake] {stamp} **焼き直します**（{day_s} の本）: `{vid}`（{topic}）—— {plan['why']}", flush=True)
    if dry_run:
        print("[rebake] **焼いていません**（`--dry-run`）", flush=True)
        return plan
    mark = _rebake_marks_dir() / f"{vid}-{sha}"
    try:
        mark.write_text(now.isoformat() + "\n", encoding="utf-8")
    except OSError:
        pass
    t = now.astimezone(JST)
    _rebake_note({"at": t.isoformat(timespec="seconds"), "kind": "start", "video_id": vid,
                  "topic": topic, "sha": sha, "for_day": day_s,
                  "session": os.environ.get("CLAUDE_SESSION_ID") or ""}, root)
    try:
        log = open(root / REBAKE_LOG, "ab")                     # noqa: SIM115
        subprocess.Popen([sys.executable or "python3", "scripts/ahead_sweep.py",
                          "--rebake-run", vid, topic, sha],
                         cwd=str(root), stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        plan["started"] = True
        print(f"[rebake] 背景で起こしました（log は `{REBAKE_LOG}`・帳面は `{REBAKE_LEDGER}`）", flush=True)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[rebake] [!] 起こせませんでした: {str(exc)[:120]}", flush=True)
    return plan


def rebake_run(vid: str, topic: str, sha: str) -> int:
    """**焼く側**（背景・`--rebake-run`）。機械にひとつの錠を持って
    `pipeline --script --dry-run` → `upload_only --draft --replaces` を撃ち、結果を帳面へ。"""
    import fcntl                                               # noqa: PLC0415
    root = Path(config.ROOT)
    t0 = time.time()
    lock_path = _rebake_marks_dir() / "rebake.lock"
    fh = open(lock_path, "a+", encoding="utf-8")              # noqa: SIM115
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        print(f"[rebake-run] 別の焼き直しが走っています（錠 `{lock_path}`）。この回は焼きません", flush=True)
        _rebake_note({"at": datetime.now(JST).isoformat(timespec="seconds"), "kind": "skip",
                      "video_id": vid, "topic": topic, "sha": sha, "why": "locked"}, root)
        return 0
    py = sys.executable or "python3"
    draft = f"data/scripts/{topic}.script.json"
    print(f"[rebake-run] {datetime.now(JST).strftime('%m/%d %H:%M JST')} `{vid}`（{topic}・sha {sha}）を焼きます", flush=True)
    rc = _run([py, "-m", "src.pipeline", "--script", draft, "--topic", topic, "--dry-run"],
              "pipeline --dry-run", 5400)
    new_id = ""
    if rc == 0:
        rc, out = _run_out([py, "scripts/upload_only.py", topic, "--draft", "--replaces", vid],
                           "upload_only --draft --replaces", 1800)
        for ln in (out or "").splitlines():
            if ln.startswith("VIDEO_ID "):
                new_id = ln.split(None, 1)[1].strip()
    _rebake_note({"at": datetime.now(JST).isoformat(timespec="seconds"), "kind": "done",
                  "video_id": vid, "topic": topic, "sha": sha, "rc": rc, "new_id": new_id,
                  "seconds": round(time.time() - t0)}, root)
    if rc == 0 and new_id:
        print(f"[rebake-run] **差し替えました**: `{vid}` → `{new_id}`（{time.time() - t0:.0f}秒）", flush=True)
        # **押すところまでが1手**（`src/inbox.git_save` の註と同じ穴）—— 決めの写し（`daily_pick.jsonl`）と
        # 控え（`critique_queue/<新ID>.*`）はこの作業コピーの `data/` にしか無く、置く手は別の作業コピーの
        # `kick` から起きることがある。押さなければ、置かれるのは旧 ID のまま。
        try:
            from src import inbox                              # noqa: PLC0415
            paths = [root / "data" / "daily_pick.jsonl", root / "data" / "uploaded.jsonl",
                     root / "data" / "published_bars.json", root / REBAKE_LEDGER,
                     root / "data" / "api_calls.jsonl"]
            paths += sorted((root / "data" / "critique_queue").glob(f"{new_id}.*"))
            paths = [p for p in paths if p.exists()]
            ok, note = inbox.git_save(
                f"rebake: {topic} を焼き直して差し替えた {vid} → {new_id}（台本 sha {sha}・"
                f"scripts/ahead_sweep.rebake_today・決めは新 ID へ）", paths)
            print(f"[rebake-run] {'押しました' if ok else '[!] 押せませんでした'}: {note[-200:]}", flush=True)
        except Exception as exc:                               # noqa: BLE001
            print(f"[rebake-run] [!] 押せませんでした: {str(exc)[:160]} —— "
                  f"`git add data/daily_pick.jsonl data/critique_queue && git commit && git push` を手で", flush=True)
    else:
        print(f"[rebake-run] [!] 焼き直せませんでした（rc={rc}・{time.time() - t0:.0f}秒）。"
              f"同じ台本は二度 焼きません —— 台本を直して commit すること", flush=True)
    try:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()
    except OSError:
        pass
    return rc


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
        plan = None
        try:
            plan = place_today(now, dry_run=args.dry_run)
        except Exception as exc:                               # noqa: BLE001
            print(f"[today] [!] 置く手が落ちました: {str(exc)[:200]}", flush=True)
        # **置いたら、その本のサムネイル**（`thumb_today` の註。50単位・きょうの1本だけ）。
        try:
            thumb_today(now, plan=plan if isinstance(plan, dict) else None,
                        dry_run=args.dry_run)
        except Exception as exc:                               # noqa: BLE001
            print(f"[thumb-today] [!] 押す手が落ちました: {str(exc)[:200]}", flush=True)
        # **公開ずみの本の最初のコメント**（`comment_pending` の註。private で上がる
        # 規則5 の下では、付ける口がここしかない）。
        try:
            comment_pending(now, dry_run=args.dry_run)
        except Exception as exc:                               # noqa: BLE001
            print(f"[comment] [!] 付ける手が落ちました: {str(exc)[:200]}", flush=True)
        # **決めた本の台本が良くなっていれば、背景で焼き直す**（規則3 を機械へ・`rebake_today` の註）。
        try:
            rebake_today(now, dry_run=args.dry_run)
        except Exception as exc:                               # noqa: BLE001
            print(f"[rebake] [!] 焼き直す手が落ちました: {str(exc)[:200]}", flush=True)
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
    # **焼く側**（`rebake_today` が背景で起こす）。位置引数 3つ: 旧ID・題材・台本の sha。
    if len(sys.argv) >= 5 and sys.argv[1] == "--rebake-run":
        raise SystemExit(rebake_run(sys.argv[2], sys.argv[3], sys.argv[4]))
    raise SystemExit(main())
