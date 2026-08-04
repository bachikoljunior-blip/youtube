"""投稿前の検査。

無人で本番チャンネルに出すので、生成物が壊れていないかを確認してから投稿する。
1つでも外れたら投稿しない。壊れた動画が上がるより、その日1本落ちるほうがいい。

**ここに何を足すかの基準。** 実際に壊れて、しかも機械が素通りしたものを足す。
思いつきの網羅ではない。これまでの故障はすべて「誰も見ていなかったもの」で、
フレームを抜いて目で見たときにだけ見つかっている。目視が抜けるのは注意力の
問題ではなく手間の問題なので、**手間のかからない側（機械）に寄せる**のが筋。

機械で見られないものは `scripts/inspect.py` が1枚にまとめる。そちらは最後の砦で、
ここに書けるものをそちらに残さないこと。
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from .subtitles import _NUM_TOKEN
from .util import require, run

# サムネイルの上限（YouTube）と、いつも作っている寸法
THUMB_MAX_BYTES = 2_000_000
THUMB_SIZE = (1280, 720)
# 実測: 公開済み7本は 39.8 以上、単色は 0.0。あいだに置く。
THUMB_MIN_STDDEV = 12.0
# 量産テンプレート判定を避けるための下限。CLAUDE.md「この作りの根幹」より。
MIN_CHARTS = 3


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


def _check_thumbnail(work: Path) -> list[str]:
    """サムネイルは一度も検査されておらず、一度も見られないまま2本壊れて公開された。"""
    thumb = work / "thumbnail.jpg"
    if not thumb.exists():
        return ["サムネイルが作られていない"]

    problems = []
    size = thumb.stat().st_size
    if size > THUMB_MAX_BYTES:
        problems.append(f"サムネイルが {size} バイトで上限の {THUMB_MAX_BYTES} を超えている")
    try:
        from PIL import Image, ImageStat

        with Image.open(thumb) as img:
            if img.size != THUMB_SIZE:
                problems.append(f"サムネイルが {img.size} で、期待は {THUMB_SIZE}")
            spread = min(ImageStat.Stat(img.convert("RGB")).stddev)
        # バイト数ではなく画素のばらつきで見る。バイト数は圧縮率の話で、
        # 中身が空かどうかの話ではない。実測では本物が 39.8 以上、単色が 0。
        if spread < THUMB_MIN_STDDEV:
            problems.append(
                f"サムネイルの画素のばらつきが {spread:.1f} しかなく、ほぼ単色に見える"
            )
    except Exception as exc:
        problems.append(f"サムネイルを開けない: {exc}")
    return problems


def _check_subtitles(work: Path) -> list[str]:
    """字幕は「。」だけの行と、数字の途中での改行で壊れた。どちらも機械で見える。"""
    ass = work / "subtitles.ass"
    if not ass.exists():
        return []

    # Dialogue の書式は Layer..Effect の9項目のあとに本文。本文にも読点が入るので
    # カンマで9回だけ割る。`,,` を目印にすると Name と Effect の両方に当たる。
    rows = [
        row[len("Dialogue:"):].split(",", 9)
        for row in ass.read_text(encoding="utf-8").splitlines()
        if row.startswith("Dialogue:")
    ]
    lines = [r[9].strip() for r in rows if len(r) == 10]
    if not lines:
        return ["字幕に1行も入っていない"]

    problems = []
    orphans = [t for t in lines if t and not re.search(r"[^\s。、！？…・]", t)]
    if orphans:
        problems.append(f"記号だけの字幕行が {len(orphans)} 行ある（例『{orphans[0]}』）")

    # 行末と次の行頭が両方とも数字・単位なら、かたまりの途中で割れている。
    split_nums = [
        (a, b) for a, b in zip(lines, lines[1:])
        if a and b and a[-1] in _NUM_TOKEN and b[0] in _NUM_TOKEN
    ]
    if split_nums:
        a, b = split_nums[0]
        problems.append(f"数字の途中で改行している箇所が {len(split_nums)} 件（『{a}』→『{b}』）")
    return problems


def _check_slides(work: Path, script: dict | None) -> list[str]:
    """同じ絵が続くこと自体がポリシー上の risk。chart の枚数もここで数える。

    「テンプレートを使用して作成されたと思われるコンテンツ」に当たると
    収益化されない。収益化されなければ RPM がいくつでも収入はゼロなので、
    これは見栄えの話ではなく到達可能性の話。
    """
    problems = []
    slides = sorted((work / "slides").glob("*.png"))
    if slides:
        digests = [hashlib.sha1(p.read_bytes()).hexdigest() for p in slides]
        dupes = sum(1 for a, b in zip(digests, digests[1:]) if a == b)
        if dupes:
            problems.append(f"隣り合う図解が同じ画像になっている箇所が {dupes} 件")

    if script:
        kinds = [s.get("visual", {}).get("kind") for s in script.get("segments", [])]
        charts = kinds.count("chart")
        if charts < MIN_CHARTS:
            problems.append(
                f"chart が {charts} 枚しかない（下限 {MIN_CHARTS} 枚）。"
                "計算結果で図の形を変えるのが量産テンプレート判定との分かれ目"
            )
    return problems


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

    problems += _check_thumbnail(work)
    problems += _check_subtitles(work)

    script = None
    script_path = work / "script.json"
    if script_path.exists():
        try:
            script = json.loads(script_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            problems.append(f"script.json が読めない: {exc}")
    # ショート（縦画面）は1本＝1つの計算結果なので chart の下限は当てない。
    problems += _check_slides(work, None if height > width else script)

    if problems:
        raise VerificationError("投稿前の検査に落ちました: " + " / ".join(problems))

    codec = audio.get("codec_name") if audio else "?"
    charts = 0
    if script:
        charts = [s.get("visual", {}).get("kind") for s in script.get("segments", [])].count("chart")
    print(
        f"[verify] 合格: {duration / 60:.1f}分, {video.get('width')}x{video.get('height')}, "
        f"音声 {codec}, chart {charts}枚, サムネ・字幕とも異常なし"
    )
    return duration
