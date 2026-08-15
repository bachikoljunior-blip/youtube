"""contact sheet の**余った枠**を「動画の最後のコマ」と読ませない（2026-08-16）。

## 何が起きていたか（**実測してから直しています**）

`inspect_build.py` は3列に並べるので、枚数が3の倍数でないと最後の行に余りが出ます。
余った枠は `Image.new(..., (20,20,24))` の地の色のまま残るので、
**ほぼ真っ黒な、完全に平らな1枚**に見えます。

実測（`8PMLfjjCe4w`・タイル8枚 → 3×3 で1枠余り）:
右下の枠の輝度が **extrema (20,20)** ＝ 画像として地の色そのもの。

これを独立評価が **「最後のコマが空（真っ黒）で終わる」** と読み、**点を引いていました** ——
8/16 03:0x で2体、その次の回で2体。**計4体が独立に同じことを書いています。**

## そして前の回は、これを生成側の欠陥として申し送っていました

> 新しく出たのは「最後のコマが空（真っ黒）で終わる」で、2体が独立に書いています。
> 問いかけを足した回から出た形で、**問いに対する答えの画面が用意されていません。**

**誤診です。** `slides_plan.json` を見ると最後のコマは問いかけの絵で、
**空のコマは1枚もありません。** そのまま直しに行けば、**無い穴を埋めていました。**

`docs/trigger_main.md` の「申し送りの『なぜか』は、一度疑うこと」がそのまま当たった例です。
**受け取るのは「何が起きているか」までで、「なぜか」は自分で測り直すこと。**

## ここで留めていること

1. **余りの枠は地の色のままにしない**（平らな暗い1枚 ＝ コマに見える）
2. **余りの枠には「動画のコマではない」と書いてある**
3. **枚数が3の倍数のときは、余計なものを描かない**（毎回描いたら邪魔になる）

**独立評価のスコアは `config/hypotheses.yaml` の反証にかかっています**
（「独立したエージェントの評価スコアは、engaged 比率を予測する」）。
**計器のうそで引かれた点は、その予測をそのまま濁します。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from PIL import Image  # noqa: E402

import inspect_build  # noqa: E402

BG = (20, 20, 24)


def _sheet(n_tiles: int, tile: tuple[int, int] = (1080, 1920)) -> Image.Image:
    """`inspect_build` と同じ並べ方で n 枚を1枚にする。

    **本体と同じ手順を写しています。** 写しなので、本体を変えたらここも合わせること
    （合っていなければ下の「地の色が残らない」が落ちます）。
    """
    cols, cell_w = inspect_build.COLS, inspect_build.CELL_W
    scaled = []
    for i in range(n_tiles):
        t = Image.new("RGB", tile, (200, 60 + i, 60))     # 枚ごとに違う色
        h = round(t.height * cell_w / t.width)
        scaled.append(t.resize((cell_w, h), Image.LANCZOS))

    rows = (len(scaled) + cols - 1) // cols
    row_h = [max(s.height for s in scaled[r * cols:(r + 1) * cols])
             for r in range(rows)]
    sheet = Image.new("RGB", (cell_w * cols, sum(row_h)), BG)
    y = 0
    for r in range(rows):
        x = 0
        for s in scaled[r * cols:(r + 1) * cols]:
            sheet.paste(s, (x, y))
            x += cell_w
        y += row_h[r]

    blanks = rows * cols - len(scaled)
    if blanks:
        from PIL import ImageDraw

        draw = ImageDraw.Draw(sheet)
        top = sum(row_h[:-1])
        for i in range(blanks):
            x0 = cell_w * (cols - blanks + i)
            box = (x0, top, x0 + cell_w - 1, top + row_h[-1] - 1)
            draw.rectangle(box, fill=(96, 32, 32), outline=(220, 180, 180), width=6)
            draw.line((x0, top, x0 + cell_w, top + row_h[-1]),
                      fill=(220, 180, 180), width=4)
            draw.line((x0, top + row_h[-1], x0 + cell_w, top),
                      fill=(220, 180, 180), width=4)
            draw.text((x0 + 24, top + 24),
                      "この枠は動画のコマではありません\n"
                      "（3列に並べた余り。動画はここで終わっていません）",
                      fill=(255, 240, 240))
    return sheet


def _cells(sheet: Image.Image, n_tiles: int):
    """各枠の (行, 列, 輝度の extrema) を返す。"""
    cols, cell_w = inspect_build.COLS, inspect_build.CELL_W
    rows = (n_tiles + cols - 1) // cols
    row_h = sheet.height // rows
    out = []
    for r in range(rows):
        for c in range(cols):
            box = sheet.crop((c * cell_w + 30, r * row_h + 30,
                              (c + 1) * cell_w - 30, (r + 1) * row_h - 30))
            out.append((r, c, box.convert("L").getextrema()))
    return out


def test_3列に並べるので3の倍数でないと余りが出る():
    """**前提の確認。** 余りが出ない作りなら、この検査ごと不要になる。"""
    assert inspect_build.COLS == 3
    for n, blanks in [(8, 1), (13, 2), (9, 0), (12, 0), (7, 2), (14, 1)]:
        rows = (n + 3 - 1) // 3
        assert rows * 3 - n == blanks


@pytest.mark.parametrize("n_tiles", [7, 8, 13, 14])
def test_余った枠に地の色が残らない(n_tiles):
    """**これが本体。** 平らな暗い枠は「動画の最後のコマ」に見える。

    実測した壊れ方は extrema が **(20, 20)** ——
    最小と最大が同じ ＝ 完全に平ら ＝ 地の色そのもの。
    """
    sheet = _sheet(n_tiles)
    flat_bg = [(r, c) for r, c, ex in _cells(sheet, n_tiles)
               if ex[0] == ex[1] == BG[0]]
    assert not flat_bg, f"地の色のままの枠が残っています: {flat_bg}"


@pytest.mark.parametrize("n_tiles", [7, 8, 13, 14])
def test_余った枠は平らではない(n_tiles):
    """斜線と文字が入るので、**必ず濃淡がある。**

    「平らかどうか」で見ているのは、**読み手が『空のコマ』と判断する条件**が
    それだからです（色を変えるだけでは、暗い色を選んだ日に元へ戻ります）。
    """
    sheet = _sheet(n_tiles)
    cells = _cells(sheet, n_tiles)
    blanks = len(cells) - n_tiles
    # **余りの枠だけを見ること。** 本物のコマは検査の作りもので、
    # ここでは単色を置いているので平らです（実際の画面は平らではありません）。
    for r, c, ex in cells[len(cells) - blanks:]:
        assert ex[1] - ex[0] > 30, f"余りの枠 ({r},{c}) が平らです: {ex}"


@pytest.mark.parametrize("n_tiles", [9, 12, 6, 3])
def test_3の倍数のときは余りの描き込みをしない(n_tiles):
    """**毎回描いたら邪魔になります。** 余りが無い回は何も足さないこと。"""
    sheet = _sheet(n_tiles)
    # 枠の数とタイルの数が一致するので、描き込む場所がそもそも無い
    assert len(_cells(sheet, n_tiles)) == n_tiles


def test_本体にも同じ描き込みが入っている():
    """**この検査は並べ方を写しています。** 写し元が変わったら気づけるように。

    `inspect_build.py` の側を消して検査だけ緑になる、という形を防ぎます
    （8/15 に「足した検査が緑のまま0件で通る」を踏んでいるので）。
    """
    src = (ROOT / "scripts" / "inspect_build.py").read_text(encoding="utf-8")
    assert "この枠は動画のコマではありません" in src
    assert "blanks" in src
