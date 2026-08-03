"""ffmpeg で最終動画を組み立てる。

方針: セグメント単位で規格の揃った無音クリップを作る → concat（再エンコードなし）
      → 最後に一度だけ字幕を焼き込みつつ音声を合成する。
      全体を1つの filter_complex でやるより、途中で落ちたときに原因が分かりやすい。
"""
from __future__ import annotations

from pathlib import Path

from .util import require, run

SILENCE_SECONDS = 0.35
V_ARGS = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
    "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
]


def build_narration(segment_audios: list[Path], work: Path, sample_rate: int = 24000) -> Path:
    """セグメント音声のあいだに無音を挟んで1本のwavにする。"""
    require("ffmpeg")
    silence = work / "silence.wav"
    run([
        "ffmpeg", "-y", "-f", "lavfi",
        "-i", f"anullsrc=r={sample_rate}:cl=mono",
        "-t", str(SILENCE_SECONDS), str(silence),
    ])

    listing = work / "audio_concat.txt"
    lines = []
    for path in segment_audios:
        lines.append(f"file '{path.resolve()}'")
        lines.append(f"file '{silence.resolve()}'")
    listing.write_text("\n".join(lines) + "\n", encoding="utf-8")

    narration = work / "narration.wav"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(listing), "-c", "copy", str(narration),
    ])
    return narration


def segment_timeline(durations: list[float]) -> list[tuple[float, float]]:
    """各セグメントの (開始, 終了)。間の無音ぶんを足していく。"""
    spans: list[tuple[float, float]] = []
    cursor = 0.0
    for duration in durations:
        spans.append((cursor, cursor + duration))
        cursor += duration + SILENCE_SECONDS
    return spans


def _clip_from_slide(src: Path, duration: float, dest: Path, fps: int, w: int, h: int) -> None:
    """図解1枚から、ゆっくり寄っていくクリップを作る。

    元の PNG は出力より大きい（2560x1440 → 1920x1080）。大きいまま寄ってから
    縮小するので、文字が甘くならない。動きを完全に止めると10分は退屈なので、
    気づかない程度だけ動かす。
    """
    frames = max(2, int(duration * fps))
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(src),
        "-t", f"{duration:.3f}", "-an",
        "-vf", (
            f"zoompan=z='min(zoom+0.00035,1.06)':d={frames}"
            f":x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={w}x{h}:fps={fps},"
            "setsar=1"
        ),
        *V_ARGS, "-r", str(fps), str(dest),
    ])


def build_video(
    slides: list[Path],
    durations: list[float],
    narration: Path,
    subtitles: Path,
    out_path: Path,
    work: Path,
    video_cfg: dict,
) -> Path:
    require("ffmpeg")
    width, height = video_cfg["resolution"]
    fps = int(video_cfg["fps"])
    clips_dir = work / "clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    clips: list[Path] = []
    for i, (slide, duration) in enumerate(zip(slides, durations)):
        # 無音の分だけクリップを伸ばして、カットの切れ目と発話の切れ目をずらす
        dest = clips_dir / f"clip_{i:03d}.mp4"
        _clip_from_slide(slide, duration + SILENCE_SECONDS, dest, fps, width, height)
        clips.append(dest)
        print(f"[render] クリップ {i + 1}/{len(slides)}")

    listing = work / "video_concat.txt"
    listing.write_text(
        "\n".join(f"file '{c.resolve()}'" for c in clips) + "\n", encoding="utf-8"
    )
    silent = work / "silent.mp4"
    run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0",
        "-i", str(listing), "-c", "copy", str(silent),
    ])

    print("[render] 字幕焼き込み + 音声合成")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    run([
        "ffmpeg", "-y",
        "-i", str(silent),
        "-i", str(narration),
        "-vf", f"ass={subtitles.as_posix()}",
        "-af", "loudnorm=I=-15:TP=-1.5:LRA=11",
        *V_ARGS, "-r", str(fps),
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        "-shortest",
        str(out_path),
    ])
    return out_path
