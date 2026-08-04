"""外部コマンドまわりの薄いラッパ。"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


def require(binary: str) -> str:
    path = shutil.which(binary)
    if not path:
        raise RuntimeError(f"{binary} が見つかりません。ffmpeg を含む環境で実行してください。")
    return path


def run(args: list[str]) -> None:
    """失敗したら stderr をそのまま見せて落とす。無音で失敗するより速く直せる。"""
    proc = subprocess.run(args, capture_output=True, text=True)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
        raise RuntimeError(f"コマンド失敗: {' '.join(args[:3])} ...\n{tail}")


def probe_duration(path: Path) -> float:
    require("ffprobe")
    proc = subprocess.run(
        [
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"ffprobe 失敗: {path}\n{proc.stderr}")
    return float(proc.stdout.strip())


def fmt_timestamp(seconds: float) -> str:
    """YouTube のチャプター用 M:SS / H:MM:SS。"""
    total = int(seconds)
    h, rem = divmod(total, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
