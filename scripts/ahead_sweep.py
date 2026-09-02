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


def take_lock(now: datetime | None = None) -> bool:
    """**掃く権利を取る**（取れたら `True`）。**死んだ印は奪います。**

    死んだ印を奪わないと、**一度 落ちた回のあとは二度と掃けません** ——
    この輪はコンテナごと消える回があるので（09/01 07:0x に再起動で 39分、
    11:5x に3つ）、**必ず起きます**。
    """
    now = now or datetime.now(timezone.utc)
    p = _lock_path()
    try:
        raw = p.read_text(encoding="utf-8").strip()
    except OSError:
        raw = ""
    if raw:
        parts = raw.split(None, 1)
        at = ahead_gate._parse(parts[1]) if len(parts) > 1 else None
        if at is not None and now - at < STALE:
            return False
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{os.getpid()} {now.isoformat()}\n", encoding="utf-8")
    except OSError:
        return False
    return True


def drop_lock() -> None:
    try:
        _lock_path().unlink()
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


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="先の日付の予約を、回の意思と関係なく掃く")
    ap.add_argument("--dry-run", action="store_true",
                    help="何をするかだけ言う（**API 0単位**）")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    stamp = now.astimezone(timezone(timedelta(hours=9))).strftime("%m/%d %H:%M JST")
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
        _run([py, "scripts/pool_drain.py", "--apply", "--keep", "0"],
             "pool_drain --apply", 3600)
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
