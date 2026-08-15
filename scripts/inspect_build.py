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


def planned_frames(work: Path) -> int:
    """`slides_plan.json` が言っているコマ数。無ければ 0。"""
    plan = work / "slides_plan.json"
    if not plan.exists():
        return 0
    try:
        import json
        data = json.loads(plan.read_text(encoding="utf-8"))
    except Exception:
        return 0
    return len(data) if isinstance(data, list) else 0


#: sheet の枚数の上下。上は「Read 1回で全部見える」大きさ、下は等間隔が粗くなりすぎない数。
TILES_MIN, TILES_MAX = 6, 18


def tile_count(planned: int, given: int = 0) -> int:
    """何枚抜くか。**明示された枚数が最優先**、次に計画のコマ数、無ければ 8。

    **関数にしてあるのは、検査が同じ式を書き写さないため**です。
    書き写すと、片方だけ直したときに**検査は緑のまま**になります
    （このリポジトリで通算5回起きています）。
    """
    if given > 0:
        return given
    return min(max(planned or 8, TILES_MIN), TILES_MAX)


def main(topic: str, count: int = 0, with_thumb: bool = False) -> int:
    work = Path("build") / topic
    video = work / "final.mp4"
    if not video.exists():
        print(f"{video} がありません")
        return 1

    total = _duration(video)
    tiles: list[Image.Image] = []

    # **枚数は、動画のコマ数に合わせること**（2026-08-16 に実測して直した）。
    #
    # ここは長らく **8枚固定**でした。ところが1本のコマ数は8ではありません ——
    # `9hqzUxqBjBE` の `slides_plan.json` は **13コマ**で、
    # **8枚の等間隔サンプルは5コマを飛ばしていました。**
    #
    # 飛ばされた中に**最後のコマ**が入ります。実測:
    #
    #     計画の12番目  「あなたはどちら側　2/2」  A と B の両方
    #     sheet の最後  「あなたはどちら側」      **A だけ**
    #
    # そして独立評価の2体が、別々の本について
    # **「最後のコマは選択肢Aだけで、Bが出ないまま終わる」**と書いて減点しました。
    # **動画には B が出ています。** 評価者が見ていたのは、
    # **終わりのコマを落とした sheet** です。
    #
    # これは 8/15 の「左上がサムネイルで、動画の一部ですらなかった」・
    # 8/16 の「余った枠を最後のコマと読ませていた」と**同じ種類**で、
    # **3件とも『計器が、動画に無いものを見せた／あるものを隠した』**です。
    # 独立評価の点は `config/hypotheses.yaml` の反証にかかっているので、
    # **計器のうそで引かれた点は、その予測をそのまま濁します。**
    #
    # **等間隔のままなのは承知のうえ**です。コマの長さは揃っていない
    # （`reveal_variants` が1枚を2つに割る）ので、枚数を合わせても
    # 取りこぼしは残りえます。**残るなら、残ったと言わせること** —— 下で数えます。
    planned = planned_frames(work)
    count = tile_count(planned, count)

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
        # **余った枠を「動画の最後のコマ」と読ませないこと**（2026-08-16 に実測して直した）。
        #
        # 3列に並べるので、枚数が3の倍数でないと**最後の行に余りが出ます。**
        # 余った枠は `Image.new` の地の色（20,20,24）のまま残るので、
        # **ほぼ真っ黒な、平らな1枚**に見えます。
        #
        # 実測（`8PMLfjjCe4w`・タイル8枚 → 3×3 で1枠余り）: 右下の枠の輝度が
        # **extrema (20,20)** ＝ 完全に平ら。**画像として地の色そのもの**でした。
        #
        # これを独立評価の3体が **「最後のコマが空（真っ黒）で終わる」** と読み、
        # **点を引いていました**（8/16 03:0x で2体、この回で2体。計4体）。
        # 前の回の申し送りは、これを**生成側の欠陥**として
        # 「問いに対する答えの画面が用意されていない」と書いています ——
        # **誤診です。** `slides_plan.json` を見ると最後のコマは問いかけの絵で、
        # **空の枠は1枚もありません。** 直しに行けば、無い穴を埋めることになりました。
        #
        # **計器がうそをついていたので、計器を直します。** 余りには
        # 「動画のコマではない」と書き込む。**地の色のままにしないこと。**
        blanks = rows * COLS - len(scaled)
        if blanks:
            from PIL import ImageDraw

            draw = ImageDraw.Draw(sheet)
            top = sum(row_h[:-1])
            for i in range(blanks):
                x0 = CELL_W * (COLS - blanks + i)
                box = (x0, top, x0 + CELL_W - 1, top + row_h[-1] - 1)
                # 地の色と混ざらない色で塗り、斜線と文字を置く
                draw.rectangle(box, fill=(96, 32, 32), outline=(220, 180, 180), width=6)
                draw.line((x0, top, x0 + CELL_W, top + row_h[-1]),
                          fill=(220, 180, 180), width=4)
                draw.line((x0, top + row_h[-1], x0 + CELL_W, top),
                          fill=(220, 180, 180), width=4)
                draw.text((x0 + 24, top + 24),
                          "この枠は動画のコマではありません\n"
                          "（3列に並べた余り。動画はここで終わっていません）",
                          fill=(255, 240, 240))

        out = work / "inspect.jpg"
        sheet.save(out, "JPEG", quality=88, optimize=True)

    print(f"[inspect] {len(tiles)}枚を1枚にまとめました: {out}")
    # **計器に、自分の見落としを言わせる。**
    # 黙って足りない sheet は「全部見た」として読まれます（8/15〜8/16 に3回）。
    if planned:
        if len(tiles) < planned:
            print(f"[inspect] **この sheet は {planned}コマ中 {len(tiles)}枚しか見ていません。**"
                  f" 落ちたコマは採点されません（`inspect_build.py <ID> {planned}` で全部見えます）")
        else:
            print(f"[inspect] 計画は {planned}コマ。{len(tiles)}枚で全部に届いています")
    else:
        print("[inspect] `slides_plan.json` が無いので、コマ数と突き合わせていません")
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
    raise SystemExit(main(argv[0], int(argv[1]) if len(argv) == 2 else 0, with_thumb))
