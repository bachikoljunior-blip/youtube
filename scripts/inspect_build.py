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


def main(topic: str, count: int = 8, with_thumb: bool = False) -> int:
    work = Path("build") / topic
    video = work / "final.mp4"
    if not video.exists():
        print(f"{video} がありません")
        return 1

    total = _duration(video)
    tiles: list[Image.Image] = []

    # **サムネイルは既定では入れません**（2026-08-15 に変えた）。
    #
    # ここは無条件に1枚目へサムネイル（16:9）を差していました。動画のコマは
    # 縦（9:16）なので、**同じ行に置くと行の高さが縦のコマに合わせて伸び、
    # サムネイルの下が地の色で埋まります。**
    # 独立評価の6体（2本×3体）が全員「**1コマ目は下2/3が真っ黒**」と書いたのは
    # **これ**です。動画にはそんな絵は1枚もありません。
    #
    # しかも `docs/CRITIQUE.md` の投げ文は「最初の1.5秒（**左上の1〜2コマ**）」と
    # 言っています。**左上はサムネイルで、動画の一部ですらありませんでした。**
    # **評価者は、存在しない冒頭を採点していました。**
    #
    # サムネイル自体の検査（背景に文字が透けていないか）は要るので、
    # `--with-thumb` で今までどおり入れられるようにしてあります。
    # **独立評価に渡すのは、既定の「動画のコマだけ」のほうを使うこと。**
    if with_thumb:
        thumb = work / "thumbnail.jpg"
        if thumb.exists():
            tiles.append(Image.open(thumb).convert("RGB"))
        else:
            print("[inspect] サムネイルがありません")

    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        # **冒頭を必ず1枚入れること**（2026-08-15 に直した）。
        #
        # ここは `total * (i + 0.5) / count` で抜いていました。count=8・30秒なら
        # **1枚目が 1.9秒**で、**最初の1.9秒からは1枚も入りません。**
        # いっぽう独立評価（`docs/CRITIQUE.md`）は
        # 「**最初の1.5秒**で親指が止まりますか」と聞いています。
        # **聞いている区間の絵を、1枚も渡していませんでした。**
        #
        # 8/15 の6体（2本×3体）は全員「冒頭で止まらない」と答えています。
        # **その判断の材料が無かった**ので、この点は評価として成立していません。
        #
        # 0.0秒ちょうどは暗転や無音を拾うことがあるので 0.25秒から始め、
        # 残りは末尾まで均す。
        head = 0.25
        for i in range(count):
            at = head + (total - head) * i / max(count - 1, 1)
            at = min(at, max(total - 0.2, 0.0))
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
    if with_thumb:
        print("  - サムネイルの背景に元スライドの文字が透けていないか")
    else:
        print("  ※ サムネイルは入れていません（縦のコマと並べると下が地の色で埋まり、"
              "**動画に無い『真っ黒な冒頭』**として採点されるため）。"
              "サムネイルを見るときは `--with-thumb` を付けること")
    print("  - 図解と字幕が重なっていないか")
    print("  - 字幕が数字の途中や句点だけで割れていないか")
    print("  - 文字がはみ出したり折り返したりしていないか")
    print("  - 図の形が動画の中で変化しているか（同じ絵が続いていないか）")
    return 0


if __name__ == "__main__":
    argv = [a for a in sys.argv[1:] if a != "--with-thumb"]
    with_thumb = "--with-thumb" in sys.argv
    if len(argv) not in (1, 2):
        print(__doc__)
        raise SystemExit(2)
    raise SystemExit(main(argv[0], int(argv[1]) if len(argv) == 2 else 8, with_thumb))
