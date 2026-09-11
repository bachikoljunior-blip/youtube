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
    pngs = [slide(seg.show, seg.sub, seg.say, i, n, image, d / f"slide-{i:02d}.png",
                  tag=seg.tag, board=seg.board)
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
    # **焼いた mp4 の指紋をその場で刻む**（2026-09-11 20:5x・hourly・Opus。`script.build_sig` の註）。
    # ここに置く理由: mp4 を書くのはこの関数だけなので、**刻み忘れる道がありません**
    # （呼ぶ側に置くと、次に別の口から焼いた回が黙って古い刻印を残します）。
    # `work/` は git に入らないので、**刻印は台帳の `built` の側にも要ります**（`cli.cmd_build`）。
    sig = s.build_sig(image)
    (d / "build.sig").write_text(sig, encoding="utf-8")
    return {"mp4": mp4, "wavs": wavs, "durations": durs, "total": probe_duration(mp4),
            "sheet": sheet, "slides": pngs, "sig": sig}


def built_sig(vid: str) -> str | None:
    """**いま `work/` に在る mp4 が、どの本文で焼かれたか**（無ければ None ＝ 焼いていないか、刻む前の版で焼いた）。"""
    p = workdir(vid) / "build.sig"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None
