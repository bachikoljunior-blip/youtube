"""音と絵を mp4 に組む。ffmpeg の concat demuxer（1コマ 1枚の静止画 + そのコマの wav）。"""
from __future__ import annotations

from pathlib import Path

from .common import probe_duration, run, workdir
from .script import Script, part_images
from .slides import contact_sheet, is_transient_frame, slide, slide_frames
from .tts import concat, synth_script


def build(s: Script, image: Path | None = None, parts: dict[str, Path] | None = None) -> dict:
    """`image` は本ぜんたいの背景・`parts` は**部の名 → その部の絵**（オーナー 09/16 12:1x `751f4947`）。

    `parts` に無い部（絵がまだ届いていない）は、本の背景へ落ちます ＝ **止まりません**
    （`docs/IMAGE_ORDERS.md`「来ていなければ待たずに焼く」と同じ扱い）。
    """
    d = workdir(s.id)
    audio = synth_script(s, d)
    wavs = [w for w, _ in audio]
    durs = [t for _, t in audio]
    full = concat(wavs, d / "voice.wav")
    n = len(s.segments)
    # **形は台本が持ちます**（既定 `short` ＝ 縦 1080x1920。`script.Script.form`・`docs/GOAL.md` (4-g) 2）。
    # ここで渡し忘れると横の本が縦の絵で焼けるので、`slide()` の既定値ではなく **必ず渡す**。
    parts = parts or {}
    names = part_images(s.segments)
    # **図の在るコマは動く数枚**（オーナー 2026-09-17 20:4x `d699098f`・`studio/viz.py`）。
    # 無いコマは今までどおり 1枚。`pngs` は sheet 用（コマごとに最後の 1枚）・`entries` は ffmpeg に渡す全部。
    pngs: list[Path] = []
    entries: list[tuple[Path, float]] = []
    for i, (seg, nm, t) in enumerate(zip(s.segments, names, durs), 1):
        bg = parts.get(nm) or image
        if seg.viz:
            fr = slide_frames(seg.show, seg.sub, seg.say, i, n, bg, d, t, seg.viz,
                              tag=seg.tag, board=seg.board, form=s.form)
            entries += fr
            pngs.append(fr[-1][0])
        else:
            p = slide(seg.show, seg.sub, seg.say, i, n, bg, d / f"slide-{i:02d}.png",
                      tag=seg.tag, board=seg.board, form=s.form)
            entries.append((p, t))
            pngs.append(p)
    lst = d / "slides.txt"
    lines = []
    for p, t in entries:
        lines.append(f"file '{p.resolve()}'\nduration {t:.4f}\n")
    lines.append(f"file '{pngs[-1].resolve()}'\n")   # concat demuxer の仕様: 最後の1枚は duration 無しで繰り返す
    lst.write_text("".join(lines), encoding="utf-8")
    mp4 = d / f"{s.id}.mp4"
    run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
         "-i", str(full), "-map", "0:v", "-map", "1:a", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
         "-r", "30", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "160k", "-shortest", "-movflags", "+faststart", str(mp4)])
    # **動く途中の絵は消す**（`slides.slide` の `fast` の註 —— 圧縮を最小にした 1枚 4MB を数百枚 残さない）。
    # 最後の 1枚（sheet に出る物）は残す。
    for p, _t in entries:
        if is_transient_frame(p):
            p.unlink(missing_ok=True)
    sheet = contact_sheet(pngs, d / "sheet.png")
    # **焼いた mp4 の指紋をその場で刻む**（2026-09-11 20:5x・hourly・Opus。`script.build_sig` の註）。
    # ここに置く理由: mp4 を書くのはこの関数だけなので、**刻み忘れる道がありません**
    # （呼ぶ側に置くと、次に別の口から焼いた回が黙って古い刻印を残します）。
    # `work/` は git に入らないので、**刻印は台帳の `built` の側にも要ります**（`cli.cmd_build`）。
    sig = s.build_sig(image)
    (d / "build.sig").write_text(sig, encoding="utf-8")
    return {"mp4": mp4, "wavs": wavs, "durations": durs, "total": probe_duration(mp4),
            "sheet": sheet, "slides": pngs, "sig": sig,
            "frames": len(entries), "viz": sum(1 for g in s.segments if g.viz)}


def built_sig(vid: str) -> str | None:
    """**いま `work/` に在る mp4 が、どの本文で焼かれたか**（無ければ None ＝ 焼いていないか、刻む前の版で焼いた）。"""
    p = workdir(vid) / "build.sig"
    return p.read_text(encoding="utf-8").strip() if p.exists() else None
