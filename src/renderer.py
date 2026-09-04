"""ffmpeg で最終動画を組み立てる。

方針: セグメント単位で規格の揃った無音クリップを作る → concat（再エンコードなし）
      → 最後に一度だけ字幕を焼き込みつつ音声を合成する。
      全体を1つの filter_complex でやるより、途中で落ちたときに原因が分かりやすい。
"""
from __future__ import annotations

import hashlib
import inspect
import os
import shutil

from pathlib import Path

from . import config
from .util import require, run

SILENCE_SECONDS = 0.35
V_ARGS = [
    "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
    "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.1",
]

# ---------------------------------------------------------------- クリップの控え
#
# **焼き直しが 25回 起きて、本になったのは 1回 です**（2026-09-04 17:0x に数えた・
# `data/rebake.jsonl`: `start` 25件 ／ `done` 3件（rc=0 は 1件）／
# **`done` が1行も無い `start` が 13件**）。`1huadpEk6HY` ひとつで
# 09/03 11:41〜23:28 に **11回** 起きて、**1回も焼き上がっていません。**
#
# 死因は分かっています —— 焼く側は回（`create_session` の子）の器の中の背景プロセスで、
# **回が畳まれると道連れ**です。焼きは実測 55〜90分、回は 30〜60分。**構造的に届きません。**
#
# ここまでは、直近の回が何度も直してきました。**ただし直したのは帳面の読み方だけです**
# （時間切れの `done` を「焼いた」に数えない／日の上限が別の本まで数える／
#  殺す秒数と `REBAKE_LEAD` の食い違い —— 09/04 だけで 4件）。
# **どれも「死んだことを正しく読む」直しで、死ぬと何が失われるかは誰も変えていません。**
#
# 失われるものはこれです。`src/pipeline.py` は毎回いちばん最初に
#
#     if work.exists(): shutil.rmtree(work)
#
# を撃ちます。＝ **前の焼きが作ったクリップは、次の焼きの1行目で全部 消えます。**
# 途中で死んだ焼きが 40/83 まで進んでいても、次は 0/83 から焼き直します。
#
# クリップは**純粋な関数**です —— 絵（PNG の中身）と 秒数・fps・寸法・冒頭かどうか、
# それに焼き方（`_clip_from_slide` の中身と `V_ARGS`）だけで決まります。
# だから中身で名前を付けて `build/.clip_cache/` に置けば、
#
#   * 途中で死んだ焼きの成果が、次の焼きに**そのまま残る**（0/83 から始まらない）
#   * 規則3 の焼き直し（毎回いじるのは数コマ）で、**残りの数十コマを焼き直さない**
#
# 実測（2026-09-04 17:0x・遊んでいる器で1コマ）: 13秒のコマ 1本 = **8.2秒**
# → 83コマ = **11.4分**。焼き 55分 のうち **21%** がこれです。
# 器が混んでいるとここが伸びます（09/04 15:09 の焼きは 5400秒 で
# **クリップ 5/83** までしか行かずに殺されました ＝ 1コマ 17分）。
#
# **置き場所は `build/` の直下**です（`build/<題材>/` の**外**）。`rmtree` が消すのは
# `build/<題材>` なので、ここは残ります。`build/` は `.gitignore` 済み（commit されません）。
# 器の外に出す必要はありません —— 実測、器のファイルは回をまたいで残ります
# （`build/zaishoku-2026-62man/` に 09/03 23:32 JST の物が在りました）。
#
# **焼き方を変えたら控えは自動で無効になります** —— 鍵に `_clip_recipe_sha()`
# （`_clip_from_slide` の**中身の写し** ＋ `V_ARGS` ＋ 冒頭の動かし方の定数）が入るので、
# `_clip_from_slide` を1文字でも直せば、次の焼きは全部 焼き直します。
# **「その直しは、この本に入っていません」を控えの側で起こさないための鍵です。**
#
# **覆る条件**: 焼く側が回の器の外へ出て（回が畳まれても生き残るように）、
# `data/rebake.jsonl` の `done`/`start` が 8割 を超えたら、
# 「途中で死ぬ」ぶんの理由は消えます。**そのときも規則3 のぶん（毎回 数コマだけ直す）は
# 残る**ので、この控えを外す理由にはなりません。
CLIP_CACHE_DIR = config.BUILD_DIR / ".clip_cache"
#: 控えの合計の上限。超えたら古い順（mtime）に捨てる。
#: 18分の本 1本ぶんが 83コマ × 0.8MB ≒ 66MB なので、3GB は **45本ぶん**。
#: 器の空きは実測 22GB（2026-09-04）。
CLIP_CACHE_CAP_BYTES = 3 * 1024 ** 3

_RECIPE_SHA: str | None = None


def _clip_recipe_sha() -> str:
    """**焼き方の写し。** これが変われば控えは全部 無効になる（上の註）。"""
    global _RECIPE_SHA
    if _RECIPE_SHA is None:
        try:
            src = inspect.getsource(_clip_from_slide)
        except OSError:                                        # pragma: no cover
            src = "?"
        h = hashlib.sha256()
        h.update(src.encode("utf-8"))
        h.update(repr(V_ARGS).encode("utf-8"))
        h.update(f"{SILENCE_SECONDS}|{OPENING_ZOOM}|{OPENING_SETTLE_SECONDS}".encode())
        _RECIPE_SHA = h.hexdigest()[:12]
    return _RECIPE_SHA


def clip_cache_key(src: Path, duration: float, fps: int, w: int, h: int,
                   opening: bool) -> str:
    """**そのクリップの中身の名前。** 絵の中身と、焼くときに渡す全部から作る。

    `duration` は `-t` に渡す字（小数3桁）でそろえること —— 丸めが違うと
    同じクリップに別の名前が付き、控えが効かなくなります。
    """
    d = hashlib.sha256()
    d.update(Path(src).read_bytes())
    d.update(f"|{duration:.3f}|{fps}|{w}x{h}|{int(bool(opening))}|".encode())
    d.update(_clip_recipe_sha().encode("utf-8"))
    return d.hexdigest()


def prune_clip_cache(cap: int = CLIP_CACHE_CAP_BYTES,
                     cache_dir: Path | None = None) -> int:
    """控えが `cap` を超えていたら、古い順（mtime）に捨てる。捨てた数を返す。"""
    d = Path(cache_dir or CLIP_CACHE_DIR)
    if not d.is_dir():
        return 0
    files: list[tuple[float, int, Path]] = []
    total = 0
    for p in d.glob("*.mp4"):
        try:
            st = p.stat()
        except OSError:
            continue
        files.append((st.st_mtime, st.st_size, p))
        total += st.st_size
    if total <= cap:
        return 0
    dropped = 0
    for _, size, p in sorted(files):
        if total <= cap:
            break
        try:
            p.unlink()
        except OSError:
            continue
        total -= size
        dropped += 1
    return dropped


def _clip_cache_get(key: str, dest: Path, cache_dir: Path) -> bool:
    """控えに在れば `dest` に置いて True。**同じ器の中なのでハードリンク**（0バイト）。"""
    src = cache_dir / f"{key}.mp4"
    try:
        if not src.is_file() or src.stat().st_size == 0:
            return False
    except OSError:
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.unlink(missing_ok=True)
    try:
        os.link(src, dest)
    except OSError:
        try:
            shutil.copy2(src, dest)
        except OSError:
            return False
    os.utime(src, None)                                        # 使ったので新しくする（prune 用）
    return True


def _clip_cache_put(key: str, made: Path, cache_dir: Path) -> None:
    """焼き上がったクリップを控えに入れる（**入らなくても焼きは止めない**）。"""
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        tmp = cache_dir / f".{key}.{os.getpid()}.tmp"
        tmp.unlink(missing_ok=True)
        try:
            os.link(made, tmp)
        except OSError:
            shutil.copy2(made, tmp)
        os.replace(tmp, cache_dir / f"{key}.mp4")
    except OSError:
        pass


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

    cache_dir = CLIP_CACHE_DIR
    clips: list[Path] = []
    reused = 0
    for i, (slide, duration) in enumerate(zip(slides, durations)):
        # 無音の分だけクリップを伸ばして、カットの切れ目と発話の切れ目をずらす
        dest = clips_dir / f"clip_{i:03d}.mp4"
        span = duration + SILENCE_SECONDS
        opening = (i == 0 and opening_motion_on())
        # **同じ中身のクリップは焼き直さない**（`CLIP_CACHE_DIR` の註）。
        #     鍵は絵の中身と焼き方だけなので、**題材も本もまたいで**効きます。
        key = clip_cache_key(slide, span, fps, width, height, opening)
        if _clip_cache_get(key, dest, cache_dir):
            clips.append(dest)
            reused += 1
            print(f"[render] クリップ {i + 1}/{len(slides)}（控えから・焼いていません）")
            continue
        _clip_from_slide(slide, span, dest, fps, width, height, opening=opening)
        _clip_cache_put(key, dest, cache_dir)
        clips.append(dest)
        print(f"[render] クリップ {i + 1}/{len(slides)}")
    if reused:
        print(f"[render] **控えから {reused}/{len(slides)}コマ**（焼いたのは "
              f"{len(slides) - reused}コマ・1コマ 約8秒）")
    prune_clip_cache(cache_dir=cache_dir)

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
