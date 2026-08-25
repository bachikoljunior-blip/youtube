"""ffmpeg で最終動画を組み立てる。

方針: セグメント単位で規格の揃った無音クリップを作る → concat（再エンコードなし）
      → 最後に一度だけ字幕を焼き込みつつ音声を合成する。
      全体を1つの filter_complex でやるより、途中で落ちたときに原因が分かりやすい。
"""
from __future__ import annotations

import os

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


# **冒頭だけ別の動かし方をする**（2026-08-15）。
#
# 独立評価（M13）を9回まわして、繰り返し出た指摘が2つあった。
# 「冒頭1.5秒に引きが無い」「画面が緑黒の文字スライドのまま動かない」。
# 実測もそこを指している —— 離脱は 4.7〜5.7秒に来るのに、**画面は
# 一度も変わらないまま**その時刻を通過していた（`src/script_writer.py`）。
#
# 台本側は既に手を打ってある（1枚目22文字 ＝ 約4.2秒で1回目のカット）。
# **だが 0〜4.2秒はまだ完全な静止画のまま**で、ショートのフィードで
# 指を止めるかどうかが決まるのはそこ。ここを絵の側から埋める。
#
# やること: 冒頭クリップだけ、**寄った状態から引く**。
#
# **上寄せにしたかったが、数えたらできなかった**（下に書く）。中央から引く。
#
# 縦の実寸（`src/visuals.py` は 540x960 CSS を2倍で焼く。以下は画面比）:
#   中身の下端   上から 68.75%（body の padding-bottom 300px ぶんを引いた位置）
#   中身の上端   上から  5.83%（padding-top 56px）
#   字幕の上端   上から 73.4%（`src/subtitles.py` MarginV=420・字 72px の1行）
#
# **いまの余裕は 4.65% しかありません**（中身の下端 68.75% ↔ 字幕 73.4%）。
# だから寄せ方で結果が変わる:
#   上寄せ 1.12  → 中身の下端が 77.0%。**字幕と重なる**（過去11回再発した形）
#   上寄せ 1.06  → 72.9%。余裕 0.5%。**近すぎる**
#   中央  1.10  → 70.6%。余裕 2.8%。上の切り取りは 4.5% で、上余白 5.83% に収まる
#
# **1.10 は「気づく最小」ではなく「両端が安全な最大」です。**
# 見た目の強さより、字幕と重ねないほうを取っています。
OPENING_ZOOM = 1.10           # 上の計算の上限。上げると上が切れるか字幕に当たる
OPENING_SETTLE_SECONDS = 0.9  # 引き切るまで。1.5秒より前に動きが終わるようにする


def opening_motion_on() -> bool:
    """**冒頭0.9秒の動きを入れるか。** `YT_OPENING_MOTION=0` で切れる（既定は入れる）。

    ## なぜ切れる必要があるのか（2026-08-23 に測って足した）

    `config/hypotheses.yaml` の「**冒頭0.9秒に絵そのものの動きを入れると engaged が
    上がる**」（期限 09/05）は、**8/23以降の3本 と 8/19〜8/21の3本**を比べる形でした。
    ところが動きが入ったのは **8/15 の実装**で、効くのは公開日ではなく**作った日**です。

    実測（8/23。`data/batch_runs.jsonl` の作成時刻で数えた）:

        作った記録のある本 405本 —— **8/15 より前に作った本は 0本**
        B群（8/19〜8/21 公開）63/63本 が 8/15 以降
        C群（8/23 以降 公開）93/93本 が 8/15 以降

    **つまり対照群が1本も無く、両群とも動きが入っています。** 比べても差は出ず、
    `falsified_if` は「上回らなければ外れ」なので **測る前から「外れ」が確定**していました。
    しかも `next_if_false` は「**静止画スライド＋合成音声という形式そのものを疑う**」で、
    **形式側で最後に残った仮説が、測らずに殺される**ところでした
    （8/19 の `src/ab_split.py` と同型の事故。あちらは「指示が入った本だけで割る」で直した）。

    **待っても対照群は現れません。** こちらから作るしかないので、この切り替えを置きます。

    ## 使い方

        YT_OPENING_MOTION=0 python -m src.pipeline ...   ← 動きなし（対照群）
        （既定）                                          ← 動きあり

    **群の再構成は「作った日」ではなく、この値を記録して行うこと。**
    実装日で割ると、また同じ穴に落ちます。
    """
    return (os.environ.get("YT_OPENING_MOTION", "1").strip() not in {"0", "false", "off"})


def _clip_from_slide(src: Path, duration: float, dest: Path, fps: int, w: int, h: int,
                     opening: bool = False) -> None:
    """図解1枚から、ゆっくり寄っていくクリップを作る。

    元の PNG は出力より大きい（2560x1440 → 1920x1080）。大きいまま寄ってから
    縮小するので、文字が甘くならない。動きを完全に止めると10分は退屈なので、
    気づかない程度だけ動かす。

    `opening=True`（1枚目）だけは別扱い。上の定数のコメントを読むこと。
    """
    frames = max(2, int(duration * fps))
    if opening:
        # 中央から引く。引き切ったあとは、他のクリップと同じ速さの流しに渡す。
        settle = max(2, int(min(OPENING_SETTLE_SECONDS, duration * 0.5) * fps))
        step = (OPENING_ZOOM - 1.0) / settle
        z = (f"if(lte(on,{settle}),{OPENING_ZOOM:.4f}-{step:.6f}*on,"
             f"min(1.0+0.00035*(on-{settle}),1.06))")
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    else:
        z = "min(zoom+0.00035,1.06)"
        x = "iw/2-(iw/zoom/2)"
        y = "ih/2-(ih/zoom/2)"
    run([
        "ffmpeg", "-y", "-loop", "1", "-i", str(src),
        "-t", f"{duration:.3f}", "-an",
        "-vf", (
            f"zoompan=z='{z}':d={frames}"
            f":x='{x}':y='{y}':s={w}x{h}:fps={fps},"
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
        _clip_from_slide(slide, duration + SILENCE_SECONDS, dest, fps, width, height,
                         opening=(i == 0 and opening_motion_on()))
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
