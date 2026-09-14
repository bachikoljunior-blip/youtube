from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "work"            # 生成物（gitignore）
DATA = ROOT / "data" / "studio"  # 台帳（commit する）
LEDGER = DATA / "ledger.jsonl"
#: **本物の台帳の道を、読み込みのときに凍らせる**（`_ledger_blocked` の註）。
#: `LEDGER` は検査が tmp へ差し替えるので、比べる相手に使えません。
_REAL_LEDGER = LEDGER
JST = dt.timezone(dt.timedelta(hours=9))


def now_jst() -> dt.datetime:
    return dt.datetime.now(JST)


def today_jst() -> str:
    return now_jst().strftime("%Y-%m-%d")


def env(name: str) -> str:
    v = os.environ.get(name, "").strip()
    if not v:
        raise SystemExit(f"環境変数 {name} が無い")
    return v


def run(cmd: list[str], **kw) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def probe_duration(path: Path) -> float:
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "csv=p=0", str(path)]).stdout.strip()
    return float(out)


def _ledger_blocked() -> bool:
    """**検査を撃つだけで本物の台帳に行が入る口を、書く側で塞ぐ**（2026-09-14 19:5x・optimizer・Opus）。

    **この回に踏んだ**: 19:1x に足した `cli.main()` の門が `ledger("token_rejected", …)` を書くようになり、
    `tests/test_studio_auth_line.py` を撃っただけで **本物の `data/studio/ledger.jsonl` に 6行**
    （`cmd: analytics` / `reporting`）入りました。**その 2件 は `cli.ledger` を差し替えていなかった**だけで、
    差し替え忘れは**書き口が増えるたびに起きます** —— §8 の 4つ目（`run_marker._marks_blocked()`・
    `next_round.log_wake()`）と**同じ形**で、あちらの決めは
    「**守りは『呼ぶ側』ではなく『書く側』に置くこと**」でした。`studio` の側にはその門がありませんでした
    （`conftest.py` は `scripts/` の台帳しか tmp へ向けていない ＝ 撃って確かめた）。

    **門**: `PYTEST_CURRENT_TEST` が立っていて、**かつ `LEDGER` が本物を指している**ときだけ書かない。
    **`LEDGER` を tmp へ差し替えた検査は書けます**（`monkeypatch.setattr(common, "LEDGER", tmp)` ＝
    台帳の中身を読む検査はそのまま通る）。

    **覆る条件**: (1) `conftest.py` が `studio` の `LEDGER` も毎回 tmp へ向けるようになったら、この門は外してよい
    （見張りがその日に落ちて教える）。(2) 本物の台帳へ**わざと**書く検査が要る回が出たら、`LEDGER` を
    差し替えるのではなく、その検査をここに名指しで書くこと（黙って門を外さない）。
    見張りは `tests/test_studio_no_real_ledger.py`（**陽性対照つき** ＝ 門を外すと本物の md5 が動く）。
    derivation は `docs/JOURNAL.md` 2026-09-14 19:2x。
    """
    return bool(os.environ.get("PYTEST_CURRENT_TEST")) and LEDGER == _REAL_LEDGER


def ledger(event: str, vid: str, **detail) -> None:
    """何をしたかを1行 足す。「出した」の定義はこの台帳の event 名で決まる（docs/METHOD.md §記録）。"""
    if _ledger_blocked():   # 検査から本物の台帳へは書かない（`_ledger_blocked` の註・§8）
        return
    DATA.mkdir(parents=True, exist_ok=True)
    # 予約は "at" を「公開の時刻」の意味で渡していたので、**detail が「いつやったか」を上書きしていた
    # （09/07 12:3x・optimizer が実測。3行とも公開時刻・09/06 の2行は元と差し替えが同じ刻で見分けられない）。
    # 予約された "at"/"id"/"event" は行の骨なので、detail に同じ名前が来ても骨を勝たせる。
    row = {**detail, "at": now_jst().isoformat(timespec="seconds"), "id": vid, "event": event}
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def ledger_rows() -> list[dict]:
    if not LEDGER.exists():
        return []
    return [json.loads(l) for l in LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]


def workdir(vid: str) -> Path:
    d = WORK / vid
    d.mkdir(parents=True, exist_ok=True)
    return d
