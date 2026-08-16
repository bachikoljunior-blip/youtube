"""contact sheet の**余った枠**を「動画の最後のコマ」と読ませない（2026-08-16）。

## 何が起きていたか（**実測してから直しています**）

`inspect_build.py` は3列に並べるので、枚数が3の倍数でないと最後の行に余りが出ます。

**1回目（8/16 03:0x〜）**: 余った枠は `Image.new(..., (20,20,24))` の地の色のまま
残るので、**ほぼ真っ黒な、完全に平らな1枚**に見えていました。
実測（`8PMLfjjCe4w`・タイル8枚 → 3×3 で1枠余り）:
右下の枠の輝度が **extrema (20,20)** ＝ 画像として地の色そのもの。

これを独立評価が **「最後のコマが空（真っ黒）で終わる」** と読み、**点を引いていました** ——
8/16 03:0x で2体、その次の回で2体。**計4体が独立に同じことを書いています。**
前の回はこれを生成側の欠陥として申し送っていましたが、**誤診**でした
（`slides_plan.json` の最後のコマは問いかけの絵で、空のコマは1枚もありません）。

## そして、その直し自体が裏目に出ました（**2026-08-16 21:4x に測った**）

1回目の直しは **赤地（96,32,32）＋×＋日本語の註**を描き込むものでした。
ところが `draw.text` に**フォントを渡していません。** PIL の既定はビットマップ
フォントなので **日本語が1字も出ず**（□□□＝豆腐）、しかも約11px で、
640px 幅の枠では縮めた sheet の上でほぼ消えます。

実測（この回の目視3体）:

    s-kyugyo-shu4-saitei-hosho     14コマ+余り1  → **作り直し**（「赤地に×＋豆腐＝描画失敗」）
    s-jikangai-futsu-6kagetsu-126  11コマ+余り1  → **作り直し**（同上）
    s-yukyu-shu2-shogai-jogen-7    12コマ+余り0  → 投稿可

**余りのある本だけが落ちています。** 黒いままより悪くなっていて、
前は「点を引かれる」で済んだものが**作り直しの判定**になりました。
素直に従えば、無傷の2本を消して上げ直し、そのあいだ予約に穴が空きます。

## ここで留めていること

1. **余りの枠は地の色のままにしない**（平らな暗い1枚 ＝ コマに見える）
2. **余りの枠には読める大きさの日本語が入っている**（豆腐でも極小でもない）
3. **赤くない**（赤と×は「描画失敗」と読まれる。それが 2回目の壊れ方）
4. **枚数が3の倍数のときは、余計なものを描かない**（毎回描いたら邪魔になる）

**独立評価のスコアは `config/hypotheses.yaml` の反証にかかっています**
（「独立したエージェントの評価スコアは、engaged 比率を予測する」）。
**計器のうそで引かれた点は、その予測をそのまま濁します。**

## 検査は、並べ方を写しません（**8/16 21:4x に直した**）

ここは長く `inspect_build.main` の並べ方を**丸ごと写して**いました。
写しなので、本体を直しても検査は緑のまま残ります（このリポジトリで通算7回）。
実際、上の「2回目の壊れ方」は**写した側にも同じ赤×が書いてあり、
検査は最後まで緑でした。** 並べ方は `inspect_build.compose()` に切り出してあるので、
**ここからはそれを呼びます。**
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

BG = inspect_build.SHEET_BG


def _sheet(n_tiles: int, tile: tuple[int, int] = (1080, 1920)) -> Image.Image:
    """**本体をそのまま呼ぶ。** 写さないので、本体を変えたらここも動きます。"""
    tiles = [Image.new("RGB", tile, (200, 60 + i, 60)) for i in range(n_tiles)]
    return inspect_build.compose(tiles)


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


def _blank_boxes(sheet: Image.Image, n_tiles: int):
    """余りの枠を切り出して返す（RGB のまま）。"""
    cols, cell_w = inspect_build.COLS, inspect_build.CELL_W
    rows = (n_tiles + cols - 1) // cols
    row_h = sheet.height // rows
    blanks = rows * cols - n_tiles
    out = []
    for i in range(blanks):
        c = cols - blanks + i
        out.append(sheet.crop((c * cell_w + 30, (rows - 1) * row_h + 30,
                               (c + 1) * cell_w - 30, rows * row_h - 30)))
    return out


def test_3列に並べるので3の倍数でないと余りが出る():
    """**前提の確認。** 余りが出ない作りなら、この検査ごと不要になる。"""
    assert inspect_build.COLS == 3
    for n, blanks in [(8, 1), (13, 2), (9, 0), (12, 0), (7, 2), (14, 1)]:
        rows = (n + 3 - 1) // 3
        assert rows * 3 - n == blanks


@pytest.mark.parametrize("n_tiles", [7, 8, 13, 14])
def test_余った枠に地の色が残らない(n_tiles):
    """**1回目の壊れ方。** 平らな暗い枠は「動画の最後のコマ」に見える。

    実測した壊れ方は extrema が **(20, 20)** ——
    最小と最大が同じ ＝ 完全に平ら ＝ 地の色そのもの。
    """
    sheet = _sheet(n_tiles)
    flat_bg = [(r, c) for r, c, ex in _cells(sheet, n_tiles)
               if ex[0] == ex[1] == BG[0]]
    assert not flat_bg, f"地の色のままの枠が残っています: {flat_bg}"


@pytest.mark.parametrize("n_tiles", [7, 8, 13, 14])
def test_余った枠は平らではない(n_tiles):
    """文字が入るので、**必ず濃淡がある。**

    「平らかどうか」で見ているのは、**読み手が『空のコマ』と判断する条件**が
    それだからです（色を変えるだけでは、暗い色を選んだ日に元へ戻ります）。
    """
    sheet = _sheet(n_tiles)
    for box in _blank_boxes(sheet, n_tiles):
        ex = box.convert("L").getextrema()
        assert ex[1] - ex[0] > 30, f"余りの枠が平らです: {ex}"


@pytest.mark.parametrize("n_tiles", [8, 13])
def test_余った枠の文字が読める大きさで入っている(n_tiles):
    """**2回目の壊れ方はここで止まります。**

    豆腐（□）でも極小の既定フォントでもないこと。実測で、直した版は
    枠の **3%（18,516px / 625,240px）** が明るい文字の色です。
    既定フォント（約11px・2行）では**2桁ないし3桁**にしかなりません。
    """
    sheet = _sheet(n_tiles)
    for box in _blank_boxes(sheet, n_tiles):
        px = list(box.convert("RGB").getdata())
        bright = sum(1 for r, g, b in px if r > 200 and g > 200 and b > 200)
        assert bright > 5000, f"文字が小さすぎるか、出ていません: {bright}px"


@pytest.mark.parametrize("n_tiles", [8, 13])
def test_余った枠は赤くない(n_tiles):
    """**赤と×は「描画失敗のフレーム」と読まれます**（この回に2体が実際にそう読んだ）。

    余りは「壊れている」のではなく「動画のコマではない」だけなので、
    警告色を使わないこと。
    """
    sheet = _sheet(n_tiles)
    for box in _blank_boxes(sheet, n_tiles):
        px = list(box.convert("RGB").getdata())
        reddish = sum(1 for r, g, b in px if r > g + 30 and r > b + 30)
        assert reddish < len(px) * 0.02, f"赤い画素が {reddish}px あります"


def test_日本語のフォントが渡されている():
    """**豆腐の直接の原因**は「フォントを渡していない」ことでした。

    既定は `ImageFont.ImageFont`（ビットマップ・CJK なし）。
    truetype が取れていることを、描く前に確かめます。
    """
    from PIL import ImageFont

    from src.thumbnail import _font

    f = _font(56)
    assert isinstance(f, ImageFont.FreeTypeFont)
    left, top, right, bottom = f.getbbox(inspect_build.BLANK_LABEL)
    assert right - left > 100, "見出しが描けていません（CJK のグリフが無い）"


@pytest.mark.parametrize("n_tiles", [9, 12, 6, 3])
def test_3の倍数のときは余りの描き込みをしない(n_tiles):
    """**毎回描いたら邪魔になります。** 余りが無い回は何も足さないこと。"""
    sheet = _sheet(n_tiles)
    assert len(_cells(sheet, n_tiles)) == n_tiles
    assert _blank_boxes(sheet, n_tiles) == []


def test_直接呼びでも読み込みが通る():
    """**`pytest` は根を `sys.path` に入れるので、ここだけ緑になります。**

    実物の呼ばれ方は `batch_build` からの `python scripts/inspect_build.py <ID>` で、
    その形では `sys.path[0]` が `scripts/` になり **cwd は入りません。**
    2026-08-16 21:5x に `from src.thumbnail import _font` を足した回が、
    検査は緑のまま **走らせて初めて `ModuleNotFoundError: No module named 'src'`**
    を踏みました（生成6本のうち contact sheet が作られなかった）。

    だから**呼ばれ方そのもの**を検査します。動画が無いので `1` で終わりますが、
    そこへ届く時点で import は全部通っています。
    """
    import subprocess

    r = subprocess.run(
        [sys.executable, "scripts/inspect_build.py", "__no_such_topic__"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert "ModuleNotFoundError" not in r.stderr, r.stderr[-400:]
    assert "がありません" in r.stdout, (r.stdout, r.stderr[-400:])


def test_本体が並べ方を持っている():
    """**写しに戻さないこと。** 並べ方の正本は `compose()` の側です。"""
    src = (ROOT / "scripts" / "inspect_build.py").read_text(encoding="utf-8")
    assert "def compose(" in src
    assert "sheet = compose(tiles)" in src, "main が compose を使っていません"
