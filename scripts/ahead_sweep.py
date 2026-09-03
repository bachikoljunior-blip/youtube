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
        used = int(quota_ledger.used_units(now))
        cap = int(quota_ledger.DAY_UNITS)
    except Exception:                                          # noqa: BLE001
        return 0
    import pool_drain                                          # noqa: PLC0415
    left = cap - used - RESERVE_UNITS
    if left <= 0:
        return 1                    # **1本だけ**（0 は「上限なし」の意味なので使えない）
    return max(1, left // pool_drain.UNITS_PER_VIDEO)


def _run(argv: list[str], label: str, timeout: int = 1800) -> int:
    return _run_out(argv, label, timeout)[0]


def _run_out(argv: list[str], label: str, timeout: int = 1800) -> tuple[int, str]:
    """子の出力を**1行ずつ その場で**流しながら撃つ（返り値と全文も返す）。

    ## なぜ `capture_output` をやめたか（2026-09-03 16:1x に踏んだ）

    前は `subprocess.run(capture_output=True)` で、**子が終わるまで1行も出ませんでした。**
    焼き直しは 25分 かかるので、その間 `data/rebake.log` に在るのは `$ …` の1行だけ。
    そして**器ごと回収されると、その出力は永久に失われます** —— きょう死んだ2本
    （13:12・15:00）は、どこまで進んだのかを1文字も残していません。

    流しておくと3つ取れます:

        ・**生きているか**（`--write` の画面が「いま焼いています」と言う根拠になる）
        ・**どこで死んだか**（次の回が、同じ所で死ぬかを見られる）
        ・**どの段が遅いか** —— 分かりやすさの輪（`clarify_and_fix`）の1周が
          何分 かかるかは、いま誰も測れていません（この回の (a2) 問い3）

    `stderr` は `stdout` へ畳んでいます（**時系列が混ざらないため**。前は末尾 20行 に
    切っていて、途中で落ちた回の手がかりがそこで消えていました）。`VIDEO_ID …` を
    索く側（`rebake_run`）は行頭で見るので、混ざっても読めます。

    **止め方**: 出力が1行も来ないまま固まる子が居るので、待つ側ではなく
    `threading.Timer` で殺します（行が来たときだけ見る形だと、無言の固まりを取り逃がす）。

    **覆る条件**: `data/rebake.log` が大きくなりすぎたら、ここではなく**呼ぶ側**で
    間引くこと（何を落とすかは、そのとき何を読みたいかで決まる）。
    """
    import threading                                           # noqa: PLC0415
    print(f"[sweep] $ {' '.join(argv)}", flush=True)
    lines: list[str] = []
    # **子の側にも「ためるな」と言うこと**（2026-09-04 22:0x に踏んだ）。
    #     `bufsize=1` は**こちらの読み口**の話で、子の `stdout` は
    #     tty でないので **Python が既定で 8KB ずつためます。**
    #     ＝ 上の3つ（生きているか・どこで死んだか・どの段が遅いか）は、
    #     **8KB たまるまで1つも取れません。** 実測: 09/04 06:22 の焼きは
    #     `data/rebake.log` の末尾が **20分 のあいだ「分かりやすさの輪 2周目」のまま**で、
    #     実物はその間に 3周目・4周目 を終え、音まで焼き終えていました
    #     （`build/<題材>/clarity_loop.json` の mtime と `audio/` の 62本 で分かった）。
    #     **待つ側は、それを「固まった」と読みます** —— この回がまさに読みかけました。
    env = dict(os.environ, PYTHONUNBUFFERED="1")
    try:
        proc = subprocess.Popen(argv, cwd=str(ROOT), stdout=subprocess.PIPE,   # noqa: S603
                                stderr=subprocess.STDOUT, text=True, bufsize=1,
                                env=env)
    except OSError as exc:
        print(f"[sweep] [!] {label} が起きませんでした: {str(exc)[:200]}", flush=True)
        return 127, ""
    killed: list[bool] = []

    def _kill() -> None:
        killed.append(True)
        try:
            proc.kill()
        except OSError:
            pass

    timer = threading.Timer(timeout, _kill)
    timer.daemon = True
    timer.start()
    try:
        if proc.stdout is not None:
            for raw in proc.stdout:
                line = raw.rstrip("\n")
                lines.append(line)
                print(f"[sweep]   {line}", flush=True)
        rc = proc.wait()
    finally:
        timer.cancel()
    if killed:
        print(f"[sweep] [!] {label} が {timeout}秒 で切れました", flush=True)
        return 124, "\n".join(lines)
    return rc, "\n".join(lines)


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
               paused: str = "", insert_ok: bool = False,
               rebake_pending: bool = False, takeover_pending: bool = False) -> dict:
    """**置くか・何を・いつ**を決める（**API 0単位・純関数**）。

    返り: `{"do": bool, "why": str, "video_id": str|None, "when": "YYYY-MM-DDTHH:00"|None,
            "via": "update" | "insert"}`

    `insert_ok=True` は「その本は `videos.insert` で置き直せる」の印
    （台本の控え `data/critique_queue/<ID>.script.json` が在る）。**日枠が尽きていても、
    その道なら置けます** —— `videos.insert` は日枠を使いません（`src/upload_cap.day_quota`
    の註・08/27 に 403 の後で 3本 通った実測）。印が無ければ従来どおり置きません。

    `rebake_pending=True` は「**この本は、いま焼き直せば良くなる**」の印
    （`rebake_plan_for(きょう)` が `do: True` を返した ＝ 台本のほうが控えより新しい）。
    そのときは、枠まで `REBAKE_LEAD` 以上 残っているかぎり**置きません**。理由は下。
    """
    day = now.astimezone(JST).date().isoformat()
    if not rule_on:
        return {"do": False, "why": "規則5 が外れています（この手は規則5 の下だけ）",
                "video_id": None, "when": None}
    if paused:
        return {"do": False, "why": f"一時停止の印が在ります: {paused[:120]}",
                "video_id": None, "when": None}
    # **差し替えの途中の窓では置かない**（2026-09-04・`TAKEOVER_STALE` の註）。
    #     焼き上がった本と枠を入れ替える 2〜5分 のあいだ、その日は 0本 に見えます。
    #     ここで置くと、**旧 ID が枠へ戻り**、直後の `--move 新` が規則1 で弾かれます。
    #     印が古ければ（焼く側が消えた）この枝は立たず、次の掃きが旧 ID を戻します。
    if takeover_pending:
        return {"do": False, "why": "いま差し替えの途中です（焼き上がった本と枠を入れ替えています）。"
                f"置くと旧 ID が枠へ戻って `--move` が規則1 で弾かれる（印 `{_takeover_mark(day).name}`・"
                f"{int(TAKEOVER_STALE.total_seconds() // 60)}分 で無視）",
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
    # --- **焼き直しが先。置くのは後**（2026-09-04 に踏んだ）-----------------------
    #
    #     **固定その4（予約はその日のぶんだけ）と 規則3（次の枠の1本を改善し続ける）が、
    #     `upload_only --replaces` の所で衝突していました。** 掃きの中の順は
    #     `main()` で **`place_today()` → `rebake_today()`** で、置く手のほうが先です。
    #     置いた瞬間に `rebake_plan_for()` は
    #     **「`<ID>` にはもう予約が付いている（`--replaces` が断る側）」**で `do: False` に
    #     倒れるので、**同じ掃きの数行 下にある焼き直しが、自分で自分を塞いでいました。**
    #
    #     実測 2026-09-04: 09:00 に出る `1huadpEk6HY` は 09/03 04:37 に焼いてあり、
    #     そのあと入った 6件（登録の依頼を画面へ・GPT Image 2.0 の背景ほか）が
    #     1つも入っていない。絵は外の ChatGPT Works が 09/03 20:33 に納品ずみで
    #     `assets/images/` に在るのに、**本に入る道だけが閉じていました。**
    #     ＝ **規則3 のいちばん大きい手（焼き直し）が、まさに規則3 の時間帯だけ使えない。**
    #
    #     **待つ長さは `REBAKE_LEAD` と同じものを使います**（新しい定数を作らないこと）。
    #     焼く側は枠まで `REBAKE_LEAD` を切ったら自分で焼くのをやめるので、
    #     **この2つは同じ線の裏表で、構造上 かみ合いません**（永久に置かれない、は起きない）。
    #     枠が近づけば `rebake_pending` の値に関わらず、次の掃きが置きます。
    #
    #     **【2026-09-04 06:5x】その `scheduled` の枝は消しました**（`rebake_plan()` の
    #     `takeover` の註）。**この枝は残します** —— 消すと、置いてから焼くことになり、
    #     **50単位 ×2（外す・置き直す）を毎回 余分に払う**からです。枠が空のうちに
    #     焼いておけば、置くのは新しい本 1回（50単位）で済みます。
    #     ＝ いまの2つの役: **この枝は「まだ置いていない日」を安く回し**、
    #     `takeover` は「**もう置いてしまった日**」を救います。
    #     検査 `tests/test_place_waits_for_rebake.py`／`tests/test_rebake_takeover.py`。
    if rebake_pending and (slot - now) >= REBAKE_LEAD:
        return {"do": False,
                "why": f"`{vid}` は焼き直せば良くなる（台本のほうが控えより新しい）。"
                       f"**置くと `--replaces` が断る側に回る**ので、焼いてから置きます"
                       f"（枠 {slot.strftime('%H:%M')} JST まで"
                       f" {int((slot - now).total_seconds() // 60)}分・"
                       f"線は `REBAKE_LEAD` {int(REBAKE_LEAD.total_seconds() // 60)}分）",
                "video_id": vid, "when": slot.strftime("%Y-%m-%dT%H:%M")}
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
    # **この本は、いま焼き直せば良くなるか**（0単位・読むだけ）。`today_plan()` の
    #     「焼き直しが先。置くのは後」の枝へ渡します。**ここへ来るのは枠が空の日だけ**
    #     （埋まっていれば `today_plan()` が上で帰る）ので、予約つきの本は当たりません。
    rebake_pending = False
    try:
        _rp = rebake_plan_for(now.astimezone(JST).date(), now)
        rebake_pending = (bool(_rp.get("do"))
                          and str(_rp.get("video_id") or "")
                          == str((cand or {}).get("video_id") or "")
                          and bool((cand or {}).get("video_id")))
    except Exception as exc:                                   # noqa: BLE001
        print(f"[today] 焼き直しの予定を読めませんでした（置く側は止めません）: "
              f"{str(exc)[:120]}", flush=True)
    plan = today_plan(now, count=count, cap=house_rule.cap(), candidate=cand, hour=hour,
                      quota_open=quota_open, rule_on=house_rule.same_day_only(),
                      paused=_paused(), insert_ok=insert_ok,
                      rebake_pending=rebake_pending,
                      takeover_pending=takeover_in_flight(
                          now.astimezone(JST).date().isoformat(), now=now))
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


#: `sub_ask_pending()` が毎周 見る本数と、使ってよい単位。
#: **既定を小さく取っています** —— 掃きの本体（予約・サムネ・コメント）の枠を
#: 食わないため。置く先はふつう 0〜数本 で、そのときは読みの 1単位 だけです。
SUB_ASK_TOP = 40
SUB_ASK_BUDGET = 1200

def sub_ask_pending(now: datetime | None = None, *, dry_run: bool = False,
                    sweep=None) -> str:
    """**再生の付いている既存の本に、登録の依頼が入っているかを毎周 見る**。返りは1行。

    ## なぜここに在るか（2026-09-04・最適化の回）

    `eta.py` が毎周こう印字しています —— **最初に落ちる門は 門1'（登録者 500人）で
    532日後。動かす腕は `views/day × sub_rate` の積。`sub_rate` を天井まで引くと
    81日後**（`per_video` 単独の 118日後 より速い）。そして 直近7日 の ship は
    `per_video` 116件 対 `sub_rate` 10件 —— **積の片方しか引かれていません。**

    `src/sub_ask.py` は 2026-09-03 に、その `sub_rate` の 0単位 の手として足され、
    `pipeline` と `uploader` に**これから作る本**の口として繋がりました。
    ところが **すでに上がっている本**へ掛ける `apply_to_video()` は
    **動画IDを手で1本ずつ渡す形**しか無く、**repo のどこからも呼ばれていません**でした。

    2026-09-04 に実物を数えると、そのぶんがまるごと落ちていました:

        上がっている 249本 のうち、いま再生が動いているのは **36本**。
        その **36本 すべて**の説明欄に、依頼は1文字も入っていませんでした。
        ＝ **いまの再生/日 の 100%** が、依頼の無い本から来ていました。

    **新しい本は 1日1本（規則1）で、いまの再生の大半は過去の本が運んでいます。**
    だから「これから作る本にだけ掛ける」形は、`sub_rate` の腕をほとんど引きません。

    掛け直しが毎周 要るのは、**動いている本の顔ぶれが入れ替わる**からです ——
    きょう 0回/日 だった本が、明日 伸び始めます。そのとき掛かっていなければ、
    その再生は依頼を見ません。置く先が無ければ **読みの 1単位 だけ**です。

    **なぜ回の裁量にしないか。** この輪で「回が憶えておく」形は落ちます ——
    最初のコメント（申し送り 6周・実物 0回）、`SessionStart` フック（0回）、
    そして `apply_to_video()` 自身（足された日から 0回）。`comment_pending` と
    同じ口（毎周 起こされる `kick` → `main`）へ入れます。

    **覆る条件**: `config/hypotheses.yaml` の「説明欄の先頭とコメントに登録の依頼を
    置くと、登録率が上がる」が外れたら、`sub_ask.HEAD` を空にすること ——
    この手は `HEAD` が空なら**何もせず 0単位 で戻ります**（消しに来る必要はありません）。
    """
    now = now or datetime.now(timezone.utc)
    stamp = now.astimezone(JST).strftime("%m/%d %H:%M JST")
    if sweep is None:
        try:
            from src import sub_ask                            # noqa: PLC0415
            sweep = sub_ask.sweep
        except Exception as exc:                               # noqa: BLE001
            line = f"道具を読めませんでした: {str(exc)[:100]}"
            print(f"[sub-ask] [!] {line}", flush=True)
            return line
    try:
        from src import upload_cap                             # noqa: PLC0415
        if not bool(upload_cap.day_quota(now).open):
            line = "日枠が尽きているので見ません（次の窓の回が見ます）"
            print(f"[sub-ask] {stamp} {line}", flush=True)
            return line
    except Exception:                                          # noqa: BLE001
        pass
    print(f"[sub-ask] {stamp} 再生の付いている本に登録の依頼が入っているかを見ます"
          f"（読み 1単位・置く先があれば 1本 50単位{'・`--dry-run`' if dry_run else ''}）",
          flush=True)
    try:
        sweep(top=SUB_ASK_TOP, budget=SUB_ASK_BUDGET, dry_run=dry_run)
    except Exception as exc:                                   # noqa: BLE001
        line = f"見る手が落ちました: {str(exc)[:120]}"
        print(f"[sub-ask] [!] {line}", flush=True)
        return line
    return "見ました"


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
           "topic": str((cur or {}).get("topic") or ""), "takeover": bool(scheduled)}
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
    # **予約が付いていても焼き直します**（2026-09-04 06:5x。**ここが規則3 の最大の手を塞いでいました**）
    #
    #     旧: `if scheduled: return out` ＝ **一度 枠へ置いた本は、未来永劫 焼き直せない。**
    #     実測 09/04 06:3x —— 09:00 に出る `1huadpEk6HY` は 09/03 04:37 に焼いてあり、
    #     そのあと入ったコードが 6件（登録の依頼を説明欄／コメント／画面へ・GPT Image 2.0 の絵）。
    #     `rebake_plan_for(09/04)` は毎周 `do: False`。**規則3 の当てどころが、毎周 消えていました。**
    #
    #     `--replaces` が断るのは **重なりの検査**の話だけです（`scripts/upload_only.py`）——
    #     「private・予約なし ＝ 公開の並びに入っていない」本しか突き合わせから外しません。
    #     予約を外せば通ります。**外す時刻が問題**でした:
    #
    #         先に外す  焼く 30〜60分 のあいだ、その日の本が 0本（死んだら公開が飛ぶ）
    #         後で外す  外す→上げる→置く の 2〜5分 だけ 0本 ← **こちら（`takeover`）**
    #
    #     だから `do` は立てたまま `takeover: True` を返し、**外すのは焼き上がった後**
    #     （`rebake_run()` の `_takeover_*`）。焼く前の枠の線（`lead`）は下でそのまま効きます。
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
                  f"（sha {out['sha']}・台本のほうが新しい）→ 焼き直して `{out['video_id']}` を差し替える"
                  + ("（**予約つき** —— 焼き上がってから枠を引き継ぎます）" if out["takeover"] else ""))
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
#: 帳面に `start` を書いてから、焼く側が錠（`flock`）を握るまでの猶予（2026-09-03 15:5x）。
#: `start` は**決める側**（`rebake_today()`）が spawn の前に書くので、直後の数秒は
#: 「錠が空いている＝死んだ」と読めません。これより古い `start` で錠が空いていれば、
#: 焼く側はもう居ません（器の回収・親の畳み）。
REBAKE_START_GRACE = timedelta(minutes=3)

#: **枠の引き継ぎ（takeover）が宙に浮いていられる上限**（2026-09-04 に足した）。
#: 焼き上がった本を差し替える 3手（`--unschedule 旧` → `upload_only` → `--move 新`）の
#: あいだ、その日の枠は **空**です。その窓に別の掃きが来ると
#: `place_today()` は「きょうは 0本」と読んで**旧 ID をもう一度 置き**、
#: 直後の `--move 新` が規則1（1日1本）で弾かれます（`reschedule.RC_RULE_FULL`）。
#: だから印（`_takeover_mark()`）を置き、置く側はその印が若いあいだ **置きません**。
#: **これより古い印は無視します** —— 焼く側が器ごと消えた回に、
#: 印だけが残って**その日が永久に空**になるほうが高い。無視されれば次の掃きが
#: 旧 ID を枠へ戻す（`daily_pick` はまだ旧 ID を指しているので、自分で治ります）。
TAKEOVER_STALE = timedelta(minutes=30)


def rebake_tally(root: Path | None = None) -> tuple[int, int]:
    """**焼き直しは、これまでに何回 起きて、何回 終わったか**（`(start, done)`・API 0単位）。

    ## なぜ数えるか（2026-09-04 06:4x に数えて、初めて分かった）

        data/rebake.jsonl   start 21件 ／ beat 15件 ／ skip 3件 ／ **done 0件**

    **21回 起きて、1回も終わっていません。** この repo の焼き直しは
    **一度も成功したことがない**まま、毎周 起き直しています。

    死に方は毎回 同じです —— `rebake_today()` は `subprocess.Popen(start_new_session=True)`
    で背景へ逃がしますが、**逃がす先はこの器の中**です。回が終われば器は回収され、
    焼く側も道連れになります（`docs/spawn_prompt.md` の「あなたは親のコンテナの中で
    走っています」と同じ話）。**直近5日のサブは `start` から中央値 11分 で終わっており**、
    焼き直しは（この回に実測した内訳で）分かりやすさの輪だけで 14分 を超えます。
    ＝ **背景へ逃がすかぎり、構造上 間に合いません。**

    だから画面（`next_slot.machine_rebake_lines`）は「いま焼いています」に
    **この数を並べます** —— 「走っている」と「終わる」は別で、
    **いまのところ後者は 0件 です。** 見た回は、**終わるまで待つこと**
    （待てる長さの根拠は `quota.py --pace` の「持続できる間隔」）。

    **覆る条件**: `done` が 1件でも出たら、この註は「何分 かかるか」の話に変わります。
    器の外（別のジョブ・別のセッション）で焼けるようになったら、待つ必要も消えます。
    """
    rows = _rebake_rows(root)
    return (sum(1 for r in rows if r.get("kind") == "start"),
            sum(1 for r in rows if r.get("kind") == "done"))


def bake_minutes() -> tuple[float | None, int]:
    """**1回の焼き直しは何分かかるか**（実測の中央値・分／標本数）。**API 0単位。**

    ## なぜ「焼き直しの帳面」から出せないか（2026-09-04 に踏んだ）

    `data/rebake.jsonl` の `done` は **0件** です（`rebake_tally()`）——
    **一度も終わっていないので、終わりの時刻がありません。**
    そこで、**中でいちばん長い所**（分かりやすさの輪）の実測を使います:

        data/clarity_loop.jsonl   `seconds` 1435秒 ＝ **24分**（4周・上限まで回った回）

    輪のあとに 焼き（実測 13分）と 読み照合の輪 と 上げ が続くので、
    **これは下限**です。**「40分 は要る」を下限として読むこと**（上振れはする）。

    使い道は1つ —— **回が「待つか、見送るか」を決めるとき**。
    枠まで これより短ければ、焼き始めても間に合いません（`rebake_run()` の `late`）。

    **覆る条件**: `done` が数件 出たら、`seconds` の中央値を直接 使うこと
    （そちらは上げまで含んだ本物の長さです）。
    """
    import json                                                # noqa: PLC0415
    f = Path(config.ROOT) / "data" / "clarity_loop.jsonl"
    vals: list[float] = []
    try:
        for ln in f.read_text(encoding="utf-8").splitlines():
            try:
                s = json.loads(ln).get("seconds")
            except Exception:                                  # noqa: BLE001
                continue
            if isinstance(s, (int, float)) and s > 0:
                vals.append(float(s))
    except OSError:
        return (None, 0)
    if not vals:
        return (None, 0)
    vals.sort()
    med = vals[len(vals) // 2] / 60.0
    return (round(med + BAKE_RENDER_MIN, 1), len(vals))


#: 分かりやすさの輪の**あと**に要る分（焼き 13分 ＋ 読み照合の輪 ＋ 上げ）。実測の下限。
BAKE_RENDER_MIN = 13.0


#: 焼きの段（新しい順に見て、最初に当たったものがいまの段）。`build/<題材>/` の実物で判じます。
#: **log では判じられません**（`_run_out` の註 —— 子が 8KB ためるので、20分 古い行が末尾に居ます）。
#: **並びは実測の順です**（2026-09-04 の焼き `nenkin-uketorikata-65-70-75-handan`・20分の長尺）:
#:
#:     21:22  焼き始め
#:     21:47  `clarity_loop.json`  分かりやすさの輪 おわり  **24.6分**（4周・上限まで・32コマ 直した）
#:     21:49  `audio/`             音 62本                **2分**
#:     22:21  `yomi_hear.json`     読み照合の輪 おわり      **32分**（誤読 0件・1周で通った）
#:     22:21  `slides_plan.json` → `slides/` → `clips/` → `final.mp4`
#:
#: **いちばん長いのは読み照合の輪**（`faster-whisper medium` を CPU で回す）で、
#: **誤読が出れば 合成し直して もう1周**なので、上の 32分 は**いちばん短い場合**です。
BAKE_STAGES = (
    ("final.mp4", "焼き上がり（あとは上げるだけ）"),
    ("clips", "映像を焼いています"),
    ("slides", "画を作っています（読み照合の輪は通った）"),
    ("slides_plan.json", "画の割りつけ（読み照合の輪は通った）"),
    ("yomi_hear.json", "読み照合の輪 おわり → 画へ"),
    ("audio", "**読み照合の輪**（`faster-whisper` を CPU で回すので、ここがいちばん長い・実測 32分）"),
    ("clarity_loop.json", "分かりやすさの輪 おわり → 音を作っています"),
    ("script.json", "台本を読み込みました（分かりやすさの輪の中・実測 24.6分）"),
)


def bake_stage(topic: str, *, root: Path | None = None) -> str:
    """**いま焼きがどこまで進んだか**（`build/<題材>/` の実物・API 0単位）。無ければ空。

    ## なぜ log ではなく `build/` を見るか（2026-09-04 22:0x に踏んだ）

    `data/rebake.log` の末尾は **20分 古いことがあります**（子が 8KB ずつためる・
    `_run_out()` の註）。実測: 末尾が「分かりやすさの輪 2周目」のまま止まって見えた 20分 の間に、
    実物は 3周目・4周目 を終え、**音 62本 まで焼き終えていました。**

    **待つ側は log だけを見ると「固まった」と読んで降ります。** `build/<題材>/` の
    mtime は子の buffer を通らないので、**そこだけは嘘をつきません。**
    """
    d = Path(root or config.ROOT) / "build" / (topic or "")
    if not topic or not d.is_dir():
        return ""
    newest = None
    for name, say in BAKE_STAGES:
        p = d / name
        if not p.exists():
            continue
        try:
            at = datetime.fromtimestamp(p.stat().st_mtime, tz=timezone.utc)
        except OSError:
            continue
        mins = (datetime.now(timezone.utc) - at).total_seconds() / 60
        newest = f"{say}（`build/{topic}/{name}` は {mins:.0f}分 前）"
        break
    return newest or ""


def _takeover_mark(day_s: str) -> Path:
    """**その日の枠を、いま引き継いでいる最中**の印（機械にひとつ・`<日>` ごと）。"""
    return _rebake_marks_dir() / f"takeover-{day_s}"


def takeover_in_flight(day_s: str, *, now: datetime | None = None) -> bool:
    """**その日の枠が、いま差し替えの途中で空いているか**（`TAKEOVER_STALE` より若い印）。"""
    now = now or datetime.now(timezone.utc)
    mark = _takeover_mark(day_s)
    try:
        raw = mark.read_text(encoding="utf-8").strip()
    except OSError:
        return False
    at = ahead_gate._parse(raw.splitlines()[0]) if raw else None
    if at is None:
        return False
    return (now - at) < TAKEOVER_STALE


def _drop_mark(vid: str, sha: str) -> None:
    """**焼かずに終わった回の印を消す。**

    ## なぜ要るか（2026-09-03 13:1x に実測。**その日の焼き直しが全部 止まっていました**）

    印（`_rebake_marks_dir()/<ID>-<sha>`）は**錠を取る前**に、決める側
    （`rebake_today()`）が書きます。焼く側（`rebake_run()`）が錠に弾かれると、
    **焼いていないのに印だけが残ります。** `rebake_attempted()` は
    「印が `REBAKE_MARK_STALE`（3時間）より若い ＝ いま焼いている」と読むので、
    **その台本は3時間 焼けません。**

    実測（09/03）: 11:41:52 に `1huadpEk6HY`（sha 65bd391332c2）の印が立ち、
    11:41:53 に `skip`（`why: locked`）。錠を握っていたのは 05:02 に起きて
    `done` を残さず消えた回（容器の回収）。**13:10 の掃きは
    「同じ台本は一度 焼いた」と言って 09/04 の本を飛ばしています** ——
    その本には、その朝の 6件 の直し（分かりやすさの輪・読み照合の門）と
    分かりやすさの輪が書き戻した 8コマ が**入っていません**。

    **飛ばした本が良くならない、では済みません。** 同じ `skip` が
    `baked_today` の分子にも入るので（`_baked_today()` の註）、
    **その日の上限 2回 も食います** —— 09/05 の本も同じ掃きで
    「きょう既に 2回 焼いた」と止まっていました。**1回の錠のすれ違いで、
    その日の焼き直しが全部 止まります。**

    **覆る条件**: 印を「錠を取ったあと」に書くように直せば、この関数は要りません
    （決める側と焼く側が別プロセスなので、いまは決める側しか書けません）。
    """
    try:
        (_rebake_marks_dir() / f"{vid}-{sha}").unlink()
    except OSError:
        pass


def _baked_today(rows: list[dict], today_s: str, *, busy: bool | None = None) -> int:
    """**きょう実際に焼いた回数**（上限 `REBAKE_MAX_PER_DAY` の分子）。

    数えるのは **`done` の在る `start`** だけ。それに、**いま走っている1本**
    （錠を誰かが握っていて、`done` の無い `start` が残っている）を足します。
    `skip`（錠に弾かれた回）は `done` を残さないので、この形で自然に落ちます。

    ## なぜ `start` を数えなくなったか（2026-09-03 16:0x に実測）

    `start` は**決める側**が spawn の前に書きます。焼く側が器ごと回収されると
    `done` が残らないので、**何も焼いていない `start` が上限を食います。** 実測:

        13:12:31  start `1huadpEk6HY`（sha 65bd391332c2）→ `done` 無し（器の回収）
        15:00:54  start `1huadpEk6HY`（sha bd162bda6fd5）→ `done` 無し（器の回収）
        16:00     `_baked_today` は **2**  ＝「きょう既に 2回 焼いた（上限 2）」
                  → **その日の焼き直しが、1本も焼けていないのに全部 止まる**

    `skip` を引く形（2026-09-03 13:1x）は**錠に弾かれた入口**しか塞いでいませんでした。
    これは同じ穴の2つ目の入口で、`rebake_died()` と対です。

    **失敗した焼きは、ちゃんと上限を食います** —— `rebake_run()` は rc≠0 でも
    `done` を書くので、壊れた台本が無限に焼き直されることはありません。
    食わないのは「器ごと消えた回」だけです。

    **覆る条件**: 焼く側が別の器で走るようになったら、`rebake_busy()`（`flock`）は
    器をまたがないので「走っている1本」を見落とします。帳面の心拍で読むこと。
    """
    def _day(r: dict) -> str:
        return str(r.get("at", ""))[:10]

    def _key(r: dict) -> tuple[str, str]:
        return (str(r.get("video_id") or ""), str(r.get("sha") or ""))

    done: set[tuple[str, str]] = {
        _key(r) for r in rows if r.get("kind") == "done" and _day(r) == today_s
    }
    n = 0
    in_flight = False
    for r in rows:
        if r.get("kind") != "start" or _day(r) != today_s:
            continue
        if _key(r) in done:
            n += 1
        else:
            in_flight = True
    if in_flight:
        alive = rebake_busy() if busy is None else busy
        if alive:
            n += 1          # 焼く側は機械にひとつ（錠）
    return n


def rebake_running(vid: str, sha: str, root: Path | None = None) -> bool:
    """**いま錠を握っているのが、この本か**（`rebake_busy()` の「誰か」を、本ごとに割る）。

    ## なぜ要るか（2026-09-04 03:2x に実測。**`rebake_died()` の 3つ目の入口**）

    `rebake_busy()` は錠がひとつしか無いので **「誰かが焼いている」しか言えません。**
    そこへ `rebake_died()` が `return not rebake_busy()` と書いてあったので、
    **別の本を焼いている間、すべての本が「いま焼いています」になっていました。** 実測:

        23:28:27  `1huadpEk6HY`（sha d4ec75716d0e）の `beat` —— そのあと `done` 無し
        03:15:50  `DfFyu8qZq3I` の `start` → 03:16:10 `beat`（**錠はこちらが握った**）
        03:2x     `machine_rebake_lines("1huadpEk6HY")` ＝ **「いま焼いています（23:28 JST に起きた）」**
                  `machine_rebake_lines("DfFyu8qZq3I")` ＝ **「いま焼いています（03:16 JST に起きた）」**
                  ＝ **同じ画面が、2本を同時に「焼いている」と言っていました**（焼く側は1本）

    そのせいで `--write` の `[次の枠]` は、**09/04 09:00 に出る `1huadpEk6HY`** について
    「`improve` は いま機械の側で進んでいます → **この回が打つなら、本ではなく別の所へ**」
    と刷り続けます。実物の機械は `rebake_plan_for(09/04)` で
    **`do: False`（「もう予約が付いている」）** ＝ **未来永劫この本を焼きません。**
    ＝ **規則3 の当てどころ（次の枠の1本）が、毎周 選択肢から消えていました。**
    その本は焼いた後にコードが 6件 入っており（登録の依頼を画面／説明欄／コメントへ・
    GPT Image 2.0 の絵）、そのどれも入っていません。

    ## なぜ `beat` で割れるか

    `beat` は **`rebake_run()` が `flock` を取った直後にしか書かれません**
    （`start` は決める側が spawn の**前**に書くだけなので、錠を1つも言っていません）。
    錠は排他なので、**より新しい `beat` が別の本に在る ＝ この本は錠を手放している**
    ——これは齢を待たずに言える、直接の証拠です。

    **覆る条件**: 焼く側が同時に2本 走れるようになったら（錠を本ごとに分けたら）、
    この判定は使えません。そのときは錠のファイル名に本を入れて、そちらを見ること。
    """
    if not vid or not sha:
        return False
    if not rebake_busy():
        return False
    last_beat = None
    for r in _rebake_rows(root):
        if r.get("kind") == "beat":
            last_beat = r
    if last_beat is None:
        # `beat` が1つも無い帳面（`--rebake-run` を手で撃った古い回）では割れない。
        # そのときは錠の「誰か」をそのまま返す（前の形と同じ）。
        return True
    return (str(last_beat.get("video_id") or "") == vid
            and str(last_beat.get("sha") or "") == sha)


def rebake_died(vid: str, sha: str, *, now: datetime, root: Path | None = None) -> bool:
    """**焼きかけのまま、焼く側が消えたか**（印は在る・`done` は無い・錠は空いている）。

    ## なぜ要るか（2026-09-03 15:5x に実測。**`_drop_mark` と同じ穴の、2つ目の入口**）

    印は錠を取る**前**に立ちます。錠に弾かれた回は `_drop_mark()` が消しますが、
    **錠を握ったまま器ごと回収された回は、誰も消しません。** 実測:

        15:00:54  `1huadpEk6HY`（sha bd162bda6fd5）の印 ＋ 帳面に `start`
        15:47     器が入れ替わる（`ps` に `pipeline` は1本も居ない）
        15:5x     `rebake_attempted()` は **True**（印が 3時間 より若い）
                  `next_slot.machine_rebake_lines()` は **「いま焼いています ——
                  手で撃たないこと」**

    ＝ **機械は 18:01 まで焼き直さず、回は「機械がやるだろう」と読んで見送ります。**
    9/03 の朝に 8時間 止まったのと同じ絵で、入口だけが違います。

    `flock` は**プロセスが死ねば OS が外す**ので、「錠が空いている」は
    「焼く側はもう居ない」の直接の証拠です（`rebake_busy()` の docstring）。
    印の齢（3時間）を待つ必要はありません。

    **覆る条件**: 焼く側が別の器で走るようになったら（`flock` は器をまたぎません）、
    この判定は「死んだ」を誤って返します。そのときは帳面に心拍（`kind: "beat"`）を
    書かせて、その齢で読むこと。
    """
    if not sha or not vid:
        return False
    mark = _rebake_marks_dir() / f"{vid}-{sha}"
    if not mark.exists():
        return False
    last = None
    for r in _rebake_rows(root):
        if r.get("video_id") == vid and r.get("sha") == sha:
            last = r
    if last is None or last.get("kind") not in ("start", "beat"):
        return False
    at = ahead_gate._parse(str(last.get("at") or ""))
    if at is None or (now - at) < REBAKE_START_GRACE:
        return False
    # **錠の「誰か」を、本ごとに割ること**（2026-09-04 に踏んだ・`rebake_running()` の註）。
    #     ここが `not rebake_busy()` だった間、**別の本を焼いている最中は
    #     すべての本が「いま焼いています」**になっていました。
    return not rebake_running(vid, sha, root)


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
    # **焼きかけで消えた回は「焼いた」ではありません**（印の齢 3時間 を待たない）。
    if rebake_died(vid, sha, now=now, root=root):
        return False
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
    booked: datetime | None = None
    try:
        r = next_slot.latest_rows().get(vid) if vid else None
        booked = ahead_gate._parse(str((r or {}).get("at") or ""))
        scheduled = bool(r and r.get("at"))
    except Exception:                                          # noqa: BLE001
        scheduled = False
    sha = script_sha(draft_text) if draft_text else ""
    attempted = rebake_attempted(vid, sha, now=now, root=root)
    today_s = now.astimezone(JST).date().isoformat()
    baked_today = _baked_today(_rebake_rows(root), today_s)
    t = now.astimezone(JST)
    if booked is not None:
        # **もう予約が付いている本の締切は、その予約そのもの**（2026-09-04）。
        #     `today_slot()` は「いまから置ける次の正時」を返すので、枠を過ぎた本に
        #     **1時間 後の存在しない締切**を与え、焼いている最中に公開されます。
        slot_at = booked.astimezone(JST)
    elif day == t.date():
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
    # **きょうを必ず見ること**（2026-09-04 06:5x に踏んだ。**`scheduled` の枝と同じ door の2つ目の錠**）
    #
    #     `daily_pick.for_day()` は「**きょうの枠が埋まっていれば あす**」を返します
    #     （`next_slot.today_full()`）。＝ **その日の本を置いた瞬間に、その日は
    #     焼き直しの視野から外れます。** `rebake_plan()` の `scheduled` の枝を外しても、
    #     ここが `first` から始まるかぎり **きょうの本は一度も plan に載りません。**
    #     実測 09/04 06:32: `--dry-run` の `[rebake]` は 09/05 の1行だけで、
    #     09:00 に出る `1huadpEk6HY`（焼いた後にコード 6件）は**印字されてすらいない。**
    #
    #     **2つとも外して初めて、規則3 の「次の枠の1本」に手が届きます。**
    #     きょうを足しても 1本/日 は破れません —— 焼き直しは本を**差し替える**だけで、
    #     枠は増えません（`takeover`）。
    base = now.astimezone(JST).date()
    days = sorted({base} | {first + timedelta(days=i) for i in range(REBAKE_DAYS_AHEAD + 1)})
    chosen: dict | None = None
    head: dict | None = None
    for day in days:
        try:
            plan = rebake_plan_for(day, now, root=root)
        except Exception as exc:                               # noqa: BLE001
            print(f"[rebake] {stamp} {day.isoformat()} の決めを読めませんでした: {str(exc)[:120]}", flush=True)
            continue
        if day != first and not plan.get("decided"):
            continue                                           # `first` 以外は決めが在るときだけ（きょうも）
        # **`head`（何も焼かない回に返す1件）は `first` に寄せること**（2026-09-04）。
        #     `base`（きょう）を一覧の頭に足したので、素直に「最初に見た日」を採ると、
        #     **決めの無いきょう**が「決めが無い」で `head` を取り、
        #     決めの在る日の理由（「控えと台本は同じ中身」）が画面から消えます。
        if head is None or day == first:
            head = plan
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
    if rebake_busy():
        # **もう1本 焼いている最中なら、起こさない**（2026-09-03 13:3x に実測）。
        #     焼く側は錠に弾かれて1秒で終わるので、起こしても
        #     `start` と `skip` が帳面に1組 増えるだけ。掃きは 20分 ごとに来るので、
        #     長い1本（実測 25分 超）のあいだ、その組が何度も積まれます。
        #     **`_baked_today()` はその組を引きますが、帳面と log は汚れ続けます。**
        print(f"[rebake] {stamp} 起こしません —— **もう1本 焼いています**"
              f"（錠 `{_rebake_marks_dir() / 'rebake.lock'}`・log は `{REBAKE_LOG}`）", flush=True)
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
        argv = ["--rebake-run", vid, topic, sha]
        if plan.get("takeover"):
            argv.append("--takeover")                           # 予約つきの本は、焼き上がってから枠を引き継ぐ
        subprocess.Popen([sys.executable or "python3", "scripts/ahead_sweep.py", *argv],
                         cwd=str(root), stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        plan["started"] = True
        print(f"[rebake] 背景で起こしました（log は `{REBAKE_LOG}`・帳面は `{REBAKE_LEDGER}`）", flush=True)
    except Exception as exc:                                   # noqa: BLE001
        print(f"[rebake] [!] 起こせませんでした: {str(exc)[:120]}", flush=True)
    return plan


def rebake_busy() -> bool:
    """**いま焼いている最中か**（錠を取ってすぐ返す・待たない）。

    `rebake_run()` が握る `flock` を、別の fd から取ってみるだけ。取れたら
    その場で外すので、焼く側の邪魔をしません。**取れなければ誰かが焼いています。**
    プロセスが死ねば `flock` は OS が外すので、`rebake.lock` の**ファイルが在ること**を
    「焼いている」と読まないこと（09/03 に 8時間 それを踏んでいます）。
    """
    import fcntl                                               # noqa: PLC0415
    path = _rebake_marks_dir() / "rebake.lock"
    try:
        fh = open(path, "a+", encoding="utf-8")                # noqa: SIM115
    except OSError:
        return False
    try:
        fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return True
    finally:
        try:
            fcntl.flock(fh, fcntl.LOCK_UN)
        except OSError:
            pass
        fh.close()
    return False


def same_topic_drafts(vid: str, topic: str, *, root: Path | None = None) -> list[str]:
    """**`--replaces` に渡す ID を全部そろえる**（いちばん新しい順・`vid` が先頭）。**API 0単位。**

    ## なぜ1本では足りないか（2026-09-04 22:2x に、焼き上がる前に気づいた）

    `rebake_run()` は長らく `--replaces <vid>` の**1本だけ**を渡していました。
    **同じ題材の下書きは、焼き直すたびに1本ずつ積みます**（消さない・固定その2 の4）。
    ＝ **3本目を上げる回は、「1つ前」を外しても「2つ前」に `same-topic` で当たります。**

    `src/dupes.blocking()` の `exclude` はこれを 2026-09-02 に直しており、
    `scripts/upload_only.py` も **`--replaces a,b`** を受けます。
    **渡す側だけが、1本のままでした。**

    実測（この回）: 題材 `nenkin-uketorikata-65-70-75-handan` の下書きは
    `dRZnZrRy2Lw`（09/02 上げ・予約なし）と `DfFyu8qZq3I`（09/03 上げ・予約なし）の **2本**。
    走っていた焼きは `--replaces DfFyu8qZq3I` だけを渡すので、
    **75分 かけて焼いたあと、`dRZnZrRy2Lw` の `same-topic` で断られます。**
    ＝ **いちばん高い所（焼き）を払ってから、いちばん安い所（引数）で落ちる形。**

    **予約の付いている本は入れません** —— `upload_only.drop_replaced()` は
    「private・予約なし」しか外さず、**1本でも欠けたら全部 断る**ので、
    予約つきを混ぜると、この関数のせいで上げられなくなります
    （予約つきの本は `takeover` が別に面倒を見ます・先頭の `vid` だけが例外）。
    """
    root = Path(root or config.ROOT)
    out = [vid] if vid else []
    if not topic:
        return out
    rows = []
    try:
        import json                                            # noqa: PLC0415
        f = root / "data" / "uploaded.jsonl"
        for ln in f.read_text(encoding="utf-8").splitlines():
            try:
                r = json.loads(ln)
            except Exception:                                  # noqa: BLE001
                continue
            if str(r.get("topic") or "") == topic and str(r.get("video_id") or ""):
                rows.append(r)
    except OSError:
        return out
    for r in reversed(rows):                                   # 新しい順
        other = str(r.get("video_id"))
        if other in out:
            continue
        if _slot_of(other):                                    # 予約つきは混ぜない（上の註）
            continue
        out.append(other)
    return out


def _slot_of(vid: str) -> str:
    """**その本に付いている予約の時刻**（`YYYY-MM-DDTHH:MM` JST・API 0単位）。無ければ空。"""
    from src import next_slot                                  # noqa: PLC0415
    try:
        row = next_slot.latest_rows().get(vid) or {}
        at = ahead_gate._parse(str(row.get("at") or ""))
    except Exception:                                          # noqa: BLE001
        return ""
    return at.astimezone(JST).strftime("%Y-%m-%dT%H:%M") if at else ""


def rebake_run(vid: str, topic: str, sha: str, *, takeover: bool = False) -> int:
    """**焼く側**（背景・`--rebake-run`）。機械にひとつの錠を持って
    `pipeline --script --dry-run` → `upload_only --draft --replaces` を撃ち、結果を帳面へ。

    `takeover=True` は「**旧 ID には予約が付いている**」の印（`rebake_plan()` の同名の欄）。
    そのときは焼き上がった**後**に枠を引き継ぎます:

        1. 旧 ID の予約の時刻を控える（`_slot_of`・0単位）
        2. `reschedule.py --unschedule <旧>`（50単位）← **ここから枠が空きます**
        3. `upload_only --draft --replaces <旧>`（`videos.insert`・日枠 0単位）
        4. `reschedule.py --move <新> <控えた時刻>`（50単位）← 枠が埋まります

    **2〜4 のあいだ、その日は 0本 です**（実測 2〜5分）。その窓に `place_today()` が来ると
    旧 ID を枠へ戻し、4 が規則1 で弾かれるので、**2 の前に印を置きます**（`_takeover_mark`）。
    **3 が落ちたら 2 を戻します**（旧 ID を同じ時刻へ）—— 焼き直しに失敗した日に
    公開そのものを落とさないため。**「焼けなかった」と「その日 出なかった」は別の損です。**
    """
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
        _drop_mark(vid, sha)
        return 0
    py = sys.executable or "python3"
    draft = f"data/scripts/{topic}.script.json"
    print(f"[rebake-run] {datetime.now(JST).strftime('%m/%d %H:%M JST')} `{vid}`（{topic}・sha {sha}）を焼きます", flush=True)
    # **錠を取ったのは、ここが初めて**（`start` は決める側が spawn の前に書くので、
    #     錠を握れたことを1つも言っていません）。手で `--rebake-run` を撃った回は
    #     `start` すら残らず、画面の「いま焼いています」が**前の回の時刻**を出します
    #     （2026-09-03 16:2x に実測）。**`done` を待たずに1行 残すこと。**
    #     `_baked_today()` は `start` しか数えないので、上限には入りません。
    _rebake_note({"at": datetime.now(JST).isoformat(timespec="seconds"), "kind": "beat",
                  "video_id": vid, "topic": topic, "sha": sha}, root)
    rc = _run([py, "-m", "src.pipeline", "--script", draft, "--topic", topic, "--dry-run"],
              "pipeline --dry-run", 5400)
    new_id = ""
    slot = _slot_of(vid) if takeover else ""
    mark_t: Path | None = None
    late = False                                               # 焼きが長引いて、枠に間に合わなかった
    if rc == 0 and takeover:
        # **枠の引き継ぎ** —— ここから `--move 新` までのあいだ、その日は 0本。
        # **焼き終えた「いま」で、もう一度 枠までを測ること**（2026-09-04）。
        #     枠の線（`REBAKE_LEAD`）を見たのは**焼く前**です。焼きが長引けば、
        #     引き継ぎに入る時点で枠が目の前（か、過ぎている）ことがあります。
        #     そこで予約を外すと、**その日の公開が遅れるか、飛びます。**
        #     間に合わない回は**引き継がない** —— 新しい本は private のまま池に残り、
        #     旧い本が予定どおり出ます（`daily_pick` は次の回が写せます）。
        #     線は置く側と同じ `TODAY_LEAD_MIN`（新しい定数を作らない）。
        left = None
        if slot:
            _s = ahead_gate._parse(slot + ":00+09:00")
            left = (_s - datetime.now(timezone.utc)).total_seconds() / 60 if _s else None
        if not slot:
            print(f"[rebake-run] [!] `{vid}` の予約の時刻が読めません（`data/next_slot` の控え）。"
                  f"**枠を外しません** —— 差し替えずに終わります", flush=True)
            rc = 1
        elif left is not None and left < TODAY_LEAD_MIN:
            # **上げないこと。** `--replaces` は予約の付いた本を断るので、ここで上げても
            #     重なりの検査で落ちます（＝ 焼いたぶんは、どのみち池にも入りません）。
            #     旧い本を予定どおり出すのが、この回のいちばん高い出口です。
            print(f"[rebake-run] [!] 枠 {slot} JST まで {left:.0f}分（線 {TODAY_LEAD_MIN}分）—— "
                  f"**引き継ぎません。** 焼きが長引いたので、旧 `{vid}` を予定どおり出します。"
                  f"台本は commit ずみなので、**次の回が余裕のある枠で焼き直せます**", flush=True)
            late = True
            takeover = False
        else:
            mark_t = _takeover_mark(slot[:10])
            try:
                mark_t.write_text(datetime.now(timezone.utc).isoformat() + "\n", encoding="utf-8")
            except OSError:
                mark_t = None
            print(f"[rebake-run] 枠を引き継ぎます: `{vid}` の {slot} JST を外します（50単位）", flush=True)
            rc = _run([py, "scripts/reschedule.py", "--unschedule", vid],
                      "reschedule --unschedule", 600)
            if rc != 0:
                print(f"[rebake-run] [!] 予約を外せませんでした（rc={rc}）。**枠はそのまま**"
                      f"（旧 `{vid}` が {slot} に出ます）", flush=True)
    if rc == 0 and not late:
        # **同じ題材の下書きを全部 渡すこと**（`same_topic_drafts()` の註）。
        #     1本だけだと、3本目の焼き直しが「2つ前」の `same-topic` で断られます ——
        #     **75分 かけて焼いたあと、引数1つで落ちる形。**
        drops = same_topic_drafts(vid, topic, root=root)
        if len(drops) > 1:
            print(f"[rebake-run] 同じ題材の下書き {len(drops)}本 を外します: {', '.join(drops)}",
                  flush=True)
        rc, out = _run_out([py, "scripts/upload_only.py", topic, "--draft",
                            "--replaces", ",".join(drops)],
                           "upload_only --draft --replaces", 1800)
        for ln in (out or "").splitlines():
            if ln.startswith("VIDEO_ID "):
                new_id = ln.split(None, 1)[1].strip()
        if takeover and slot:
            if rc == 0 and new_id:
                rc = _run([py, "scripts/reschedule.py", "--move", new_id, slot],
                          "reschedule --move（引き継ぎ）", 600)
                if rc == 0:
                    print(f"[rebake-run] 枠を引き継ぎました: `{new_id}` を {slot} JST へ", flush=True)
                else:
                    print(f"[rebake-run] [!] 新しい本を枠へ置けませんでした（rc={rc}）—— "
                          f"`python scripts/reschedule.py --move {new_id} {slot}` を手で撃つこと", flush=True)
            else:
                # **焼けなかった日に、公開まで落とさない。** 外した予約を旧 ID へ戻す。
                print(f"[rebake-run] [!] 上げられませんでした。**旧 `{vid}` を {slot} へ戻します**", flush=True)
                _run([py, "scripts/reschedule.py", "--move", vid, slot],
                     "reschedule --move（戻し）", 600)
    if mark_t is not None:
        try:
            mark_t.unlink()
        except OSError:
            pass
    # **間に合わなかった回は `done` ではありません**（2026-09-04）。
    #     `rebake_attempted()` は rc を問わず `done` を「焼いた」と読むので、
    #     `done` を残すと**同じ台本は二度と焼かれません** —— 焼く価値は残っているのに。
    #     `late` は印も落として、次の回が**余裕のある枠で**もう一度 焼けるようにします。
    _rebake_note({"at": datetime.now(JST).isoformat(timespec="seconds"),
                  "kind": "late" if late else "done",
                  "video_id": vid, "topic": topic, "sha": sha, "rc": rc, "new_id": new_id,
                  "seconds": round(time.time() - t0)}, root)
    if late:
        _drop_mark(vid, sha)
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
        # **再生の付いている既存の本に、登録の依頼が入っているか**（`sub_ask_pending` の註。
        # 門1' を動かす積のうち `sub_rate` の側。置く先が無ければ 1単位）。
        try:
            sub_ask_pending(now, dry_run=args.dry_run)
        except Exception as exc:                               # noqa: BLE001
            print(f"[sub-ask] [!] 見る手が落ちました: {str(exc)[:200]}", flush=True)
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
        raise SystemExit(rebake_run(sys.argv[2], sys.argv[3], sys.argv[4],
                                    takeover="--takeover" in sys.argv[5:]))
    raise SystemExit(main())
