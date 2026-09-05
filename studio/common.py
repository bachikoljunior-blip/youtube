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


def ledger(event: str, vid: str, **detail) -> None:
    """何をしたかを1行 足す。「出した」の定義はこの台帳の event 名で決まる（docs/METHOD.md §記録）。"""
    DATA.mkdir(parents=True, exist_ok=True)
    row = {"at": now_jst().isoformat(timespec="seconds"), "id": vid, "event": event, **detail}
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
