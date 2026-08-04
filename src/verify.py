"""投稿前の検査。

無人で本番チャンネルに出すので、生成物が壊れていないかを確認してから投稿する。
1つでも外れたら投稿しない。壊れた動画が上がるより、その日1本落ちるほうがいい。
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .util import require, run


class VerificationError(RuntimeError):
    pass


def _probe(path: Path) -> dict:
    require("ffprobe")
    proc = subprocess.run(
        ["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(path)],
        capture_output=True, text=True,
    )
    if proc.returncode != 0:
        raise VerificationError(f"ffprobe が読めませんでした: {proc.stderr[:300]}")
    return json.loads(proc.stdout)


def check(path: Path, video_cfg: dict, min_minutes: float, work: Path) -> float:
    """問題があれば VerificationError。無ければ尺（秒）を返す。"""
    probe = _probe(path)
    streams = probe.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    duration = float(probe.get("format", {}).get("duration") or 0)
    width, height = video_cfg["resolution"]

    problems: list[str] = []
    if not video:
        problems.append("映像トラックが無い")
    if not audio:
        problems.append("音声トラックが無い")
    if duration < min_minutes * 60:
        problems.append(
            f"尺が {duration / 60:.1f}分 で下限の {min_minutes}分 未満"
            "（8分を切るとミッドロール広告を入れられない）"
        )
    if video and (int(video.get("width", 0)) != width or int(video.get("height", 0)) != height):
        problems.append(f"{video.get('width')}x{video.get('height')} で、期待は {width}x{height}")

    # 先頭が真っ黒なら、素材の生成か合成のどこかが黙って失敗している。
    # 一様な画は PNG にするとほとんど圧縮されるので、バイト数で判定できる。
    if video:
        frame = work / "_first.png"
        run(["ffmpeg", "-y", "-v", "error", "-ss", "0.4", "-i", str(path),
             "-frames:v", "1", "-vf", "scale=160:90", str(frame)])
        size = frame.stat().st_size if frame.exists() else 0
        frame.unlink(missing_ok=True)
        if size < 1200:
            problems.append(f"冒頭のフレームが真っ白か真っ黒に見える（{size} バイト）")

    if problems:
        raise VerificationError("投稿前の検査に落ちました: " + " / ".join(problems))

    codec = audio.get("codec_name") if audio else "?"
    print(f"[verify] 合格: {duration / 60:.1f}分, {video.get('width')}x{video.get('height')}, 音声 {codec}")
    return duration
