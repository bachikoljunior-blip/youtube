"""投稿前の目視を1枚にまとめる。

    python scripts/inspect_build.py <テーマID>

なぜ要るか。**verify.py が見ていないものは、これまで例外なく壊れていた。**
字幕と図解の重なり、stat の折り返し、句点だけの字幕行、数字の途中での改行、
棒ラベルの折り返し、サムネイルの二重写り。6件すべて、機械は素通りし、
フレームを抜いて目で見たときにだけ見つかっている。

目視が抜けるのは注意力の問題ではなく、**手間の問題**。
フレームを何枚も抜いて何度も Read するのは面倒で、面倒なことは飛ばされる。
だから1コマンドで1枚にまとめ、Read 1回で全部見えるようにする。

左上がサムネイル、その後が動画から等間隔に抜いたフレーム。
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

from PIL import Image

COLS = 3
CELL_W = 640


def _duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(path)],
        capture_output=True, text=True, check=True,
    )
    return float(out.stdout.strip())


def _frame(video: Path, at: float, dest: Path) -> Path | None:
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-ss", f"{at:.2f}", "-i", str(video),
         "-frames:v", "1", str(dest)],
        check=False,
    )
    return dest if dest.exists() else None


def main(topic: str, count: int = 8) -> int:
    work = Path("build") / topic
    video = work / "final.mp4"
    if not video.exists():
        print(f"{video} がありません")
        return 1

    total = _duration(video)
    tiles: list[Image.Image] = []

    thumb = work / "thumbnail.jpg"
    if thumb.exists():
        tiles.append(Image.open(thumb).convert("RGB"))
    else:
        print("[inspect] サムネイルがありません")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        # 冒頭と末尾は避ける。無音や暗転で判断材料にならないことがある。
        for i in range(count):
            at = total * (i + 0.5) / count
            got = _frame(video, at, tmpdir / f"f{i}.jpg")
            if got:
                tiles.append(Image.open(got).convert("RGB"))

        if not tiles:
            print("[inspect] フレームを抜けませんでした")
            return 1

        # 縦横比はまちまち（縦動画とサムネが混ざる）。幅を揃えて高さは成り行き。
        scaled = []
        for t in tiles:
            h = round(t.height * CELL_W / t.width)
            scaled.append(t.resize((CELL_W, h), Image.LANCZOS))

        rows = (len(scaled) + COLS - 1) // COLS
        row_h = [max(s.height for s in scaled[r * COLS:(r + 1) * COLS]) for r in range(rows)]
        sheet = Image.new("RGB", (CELL_W * COLS, sum(row_h)), (20, 20, 24))
        y = 0
        for r in range(rows):
            x = 0
            for s in scaled[r * COLS:(r + 1) * COLS]:
                sheet.paste(s, (x, y))
                x += CELL_W
            y += row_h[r]

        out = work / "inspect.jpg"
        sheet.save(out, "JPEG", quality=88, optimize=True)

    print(f"[inspect] {len(tiles)}枚を1枚にまとめました: {out}")
    print("[inspect] Read で開いて、次を見ること:")
    print("  - サムネイルの背景に元スライドの文字が透けていないか")
    print("  - 図解と字幕が重なっていないか")
    print("  - 字幕が数字の途中や句点だけで割れていないか")
    print("  - 文字がはみ出したり折り返したりしていないか")
    print("  - 図の形が動画の中で変化しているか（同じ絵が続いていないか）")
    return 0


if __name__ == "__main__":
    if len(sys.argv) not in (2, 3):
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) == 3 else 8))
