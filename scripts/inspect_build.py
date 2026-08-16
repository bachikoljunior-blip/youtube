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

# **`python scripts/inspect_build.py <ID>` で呼ばれます**（`batch_build` がそう呼ぶ）。
# その形だと `sys.path[0]` は `scripts/` で、**cwd は入りません** ——
# つまり `from src.thumbnail import _font` が `ModuleNotFoundError` になります。
# 2026-08-16 21:5x に実際に踏みました（`pytest` は根を入れるので緑のまま通り、
# **走らせて初めて落ちた**）。**道具は `-m` でも直接でも通ること。**
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# **読み込みは頭でやること。** 関数の中に置くと、動画が無い回は素通りするので
# 「走らせたのに落ちなかった」が起きます（2026-08-16 21:5x に、まさにそれで
# 検査を1つ書き損ねました）。**頭に置けば、呼んだ瞬間に落ちます。**
from src.thumbnail import _font  # noqa: E402

COLS = 3
CELL_W = 640
SHEET_BG = (20, 20, 24)      # 並べたときの地の色
BLANK_LABEL = "空き枠"       # 余った枠の見出し（検査もこれを見る）


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


def compose(tiles: list) -> "Image.Image":
    """コマを3列に並べて1枚にする。**余った枠には「空き枠」と書き込む。**

    **`main` から切り出してあるのは、検査が並べ方を書き写さないため**です
    （`tile_count` と同じ理由。書き写すと片方だけ直したときに検査は緑のまま残り、
    このリポジトリで通算7回起きています）。実際、8/16 21:0x まで
    `tests/test_contact_sheet_padding.py` は**この処理を丸ごと写していました。**

    ## 余った枠の意匠（**2回直しています。2回目は1回目が裏目に出たから**）

    3列に並べるので、枚数が3の倍数でないと最後の行に余りが出ます。

    **1回目（8/16）**: 余りは `Image.new` の地の色（20,20,24）のまま残るので、
    **ほぼ真っ黒な平らな1枚**に見えていました（実測 extrema (20,20) ＝ 完全に平ら）。
    これを独立評価が「最後のコマが空（真っ黒）で終わる」と読み、**4体が点を引いた。**
    さらに前の回はこれを**生成側の欠陥**と誤診して申し送っています
    （`slides_plan.json` の最後のコマは問いかけの絵で、空のコマは1枚もありません）。
    そこで **赤地（96,32,32）＋×＋日本語の註**を描き込みました。

    **2回目（8/16 21:4x。これが現行）**: 1回目は `draw.text` に**フォントを渡していません**。
    PIL の既定はビットマップフォントなので**日本語が1字も出ず**（□□□＝豆腐）、
    しかも約11px で、640px 幅の枠では縮めた sheet の上でほぼ消えます。

    結果、この回の目視3体のうち **2体が「赤地に×＋豆腐文字＝描画失敗のフレーム」**と読み、
    **両方が `VERDICT: 作り直し`** を返しました（実物の動画は無傷。
    `s-kyugyo-shu4-saitei-hosho` は 14コマ+余り1、`s-jikangai-futsu-6kagetsu-126` は
    11コマ+余り1、**余りの無い `s-yukyu-shu2-shogai-jogen-7` だけが `投稿可`**）。

    **黒いままより悪くなっています。** 前は「点を引かれる」で済んでいたものが、
    いまは**作り直しの判定**です。素直に従えば、無傷の2本を消して上げ直し、
    そのあいだ予約に穴が空きました。だから直しは2つ ——
    **日本語の出るフォントを渡す**ことと、**「失敗」に見える意匠（赤・×）をやめる**こと。
    """
    from PIL import ImageDraw

    # 縦横比はまちまち（縦動画とサムネが混ざる）。幅を揃えて高さは成り行き。
    scaled = []
    for t in tiles:
        h = round(t.height * CELL_W / t.width)
        scaled.append(t.resize((CELL_W, h), Image.LANCZOS))

    rows = (len(scaled) + COLS - 1) // COLS
    row_h = [max(s.height for s in scaled[r * COLS:(r + 1) * COLS]) for r in range(rows)]
    sheet = Image.new("RGB", (CELL_W * COLS, sum(row_h)), SHEET_BG)
    y = 0
    for r in range(rows):
        x = 0
        for s in scaled[r * COLS:(r + 1) * COLS]:
            sheet.paste(s, (x, y))
            x += CELL_W
        y += row_h[r]

    blanks = rows * COLS - len(scaled)
    if blanks:
        draw = ImageDraw.Draw(sheet)
        top = sum(row_h[:-1])
        f_big, f_small = _font(56), _font(34)
        for i in range(blanks):
            x0 = CELL_W * (COLS - blanks + i)
            box = (x0, top, x0 + CELL_W - 1, top + row_h[-1] - 1)
            # 落ち着いた灰色。**赤も×も使わない**（どちらも「壊れた」と読まれる）
            draw.rectangle(box, fill=(56, 56, 62), outline=(150, 150, 158), width=6)
            draw.text((x0 + 40, top + 40), BLANK_LABEL, font=f_big, fill=(240, 240, 244))
            draw.text((x0 + 40, top + 130),
                      "動画のコマでは\nありません\n\n"
                      "3列に並べたときの\n余りです。\n"
                      "動画はここで\n終わっていません",
                      font=f_small, fill=(215, 215, 222), spacing=10)
    return sheet


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

        sheet = compose(tiles)

        out = work / "inspect.jpg"
        sheet.save(out, "JPEG", quality=88, optimize=True)

    print(f"[inspect] {len(tiles)}枚を1枚にまとめました: {out}")
    # **余り枠の枚数を、必ず1行で言うこと**（2026-08-16 21:5x に測って足した）。
    #
    # この回いちばんの時間食いは、目視が返した `VERDICT: 作り直し` 2件の検証で
    # **約25分**でした。2体とも理由は「最終コマが赤地に×＝描画失敗」で、
    # **正体はこちらが描いた余り枠**です（`compose()` の註）。
    #
    # 突き止めるのに3手かかっています —— 実装を読む・画素で数える・
    # 実物のコマを1枚開く。**ここに1行あれば1手で済みます。**
    # 「余り 1枚」と出ていて、判定が最終コマを指しているなら、それは枠の話です。
    #
    # 前の回の「縮んだ contact sheet で棒の長さを目分量で比べない／
    # `_chart_html` を呼んで数字で見る」と**同じ形**で、あちらは棒、こちらは枠。
    blanks = (-len(tiles)) % COLS
    if blanks:
        print(f"[inspect] **この sheet には「{BLANK_LABEL}」が {blanks}枚あります**"
              f"（{len(tiles)}枚を{COLS}列に並べた余り）。**動画のコマではありません。**")
        print("          目視が最後のコマを「壊れている」と言ったら、まずこの枠を疑うこと。")
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
