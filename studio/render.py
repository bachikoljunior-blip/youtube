"""音と絵を mp4 に組む。ffmpeg の concat demuxer（1コマ 1枚の静止画 + そのコマの wav）。"""
from __future__ import annotations

from pathlib import Path

from .common import probe_duration, run, workdir
from .script import Script
from .slides import contact_sheet, slide
from .tts import concat, synth_script


def build(s: Script, image: Path | None = None) -> dict:
    d = workdir(s.id)
    audio = synth_script(s, d)
    wavs = [w for w, _ in audio]
    durs = [t for _, t in audio]
    full = concat(wavs, d / "voice.wav")
    n = len(s.segments)
    pngs = [slide(seg.show, seg.sub, seg.say, i, n, image, d / f"slide-{i:02d}.png")
            for i, seg in enumerate(s.segments, 1)]
    lst = d / "slides.txt"
    lines = []
    for p, t in zip(pngs, durs):
        lines.append(f"file '{p.resolve()}'\nduration {t:.3f}\n")
    lines.append(f"file '{pngs[-1].resolve()}'\n")   # concat demuxer の仕様: 最後の1枚は duration 無しで繰り返す
    lst.write_text("".join(lines), encoding="utf-8")
    mp4 = d / f"{s.id}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-i", str(full), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(mp4)])
    sheet = contact_sheet(pngs, d / "sheet.png")
    return {"mp4": mp4, "wavs": wavs, "durations": durs, "total": probe_duration(mp4), "sheet": sheet, "slides": pngs}
