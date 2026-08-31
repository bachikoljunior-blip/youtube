"""**サムネイルが、一覧の中で黒い長方形になっていないか。**（2026-08-31 に足した）

## 何が壊れていたか

`src/thumbnail._base_image()` は背景の明るさを
`ImageEnhance.Brightness(img).enhance(0.42)` の**固定の掛け算**で作っていました。
掛け算は**元の明るさに対して相対的**なので、暗いスライドから作った本は
ほぼ真っ黒になります。

実測（`data/critique_queue/UIWHsypOPPg.thumb.jpg`・09/01 22:00 JST に出る1本）:

    字の無い右下の帯   平均輝度 **7 / 255**
    字の無い上の帯     平均輝度 **16 / 255**

字は読めます。**面が死んでいます。** 一覧では、明るい競合の隣に置かれた
黒い長方形です。`_check_thumbnail()` は「ほぼ単色」を stddev で見ていますが、
**黒い面に白い字が乗っていれば stddev は十分に大きい** ので、この形は
1度も咎められませんでした。**「単色ではない」と「見える」は別の条件**です。

## これは、この file が1度 踏んだのと同じ形の間違いです

`_base_image()` の docstring に、ぼかしで同じことをやった記録があります ——
「ぼかしは文字の大きさに対して相対的で、160px の数字1つは 22 のぼかしでは
消えない。**大きさに依存しない方法**でないと、また同じ壊れ方をする」。
`MOSAIC_W`（幅80pxまで縮める）がその答えでした。

**明るさも同じです。** 元の明るさに依存しない方法 ＝ **行き先を決めて合わせる**
（`BG_TARGET_LUMA`）。素材が暗くても明るくても、背景は同じ濃さになります。

## ここが見るのは2つ

    1. **固定の掛け算に戻っていないこと**（`enhance(0.42)` のような定数）
    2. 暗い素材・明るい素材の**どちらから作っても**、背景が同じ帯に来ること

## 覆る条件

**行き先の輝度（`BG_TARGET_LUMA`）を変えたくなったとき。** そのときは
この検査の帯も一緒に動かすこと —— **数はここに写さず、`src/thumbnail` を読みます。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

PIL = pytest.importorskip("PIL")
from PIL import Image, ImageStat  # noqa: E402

from src import thumbnail  # noqa: E402

# 行き先からどれだけ離れてよいか。**数は `src/thumbnail` から取ります。**
TOLERANCE = 14.0


def _flat(rgb: tuple[int, int, int], path: Path) -> Path:
    Image.new("RGB", (1280, 720), rgb).save(path)
    return path


def test_固定の掛け算に戻っていない():
    """`enhance(0.42)` のような定数が背景の明るさを決めていないこと。"""
    src = (ROOT / "src" / "thumbnail.py").read_text(encoding="utf-8")
    assert "BG_TARGET_LUMA" in src, (
        "背景の明るさが行き先で決まっていません。"
        "固定の掛け算は、暗い素材をほぼ真っ黒にします"
    )
    assert "Brightness(img).enhance(0.42)" not in src, (
        "固定の掛け算に戻っています。**元の明るさに依存しない方法**にすること"
    )


@pytest.mark.parametrize("rgb", [(8, 9, 14), (30, 34, 44), (150, 155, 165), (245, 245, 245)])
def test_どの明るさの素材からでも背景は同じ帯に来る(tmp_path, rgb):
    """暗い素材と明るい素材で、出来上がりの背景が同じ濃さになること。"""
    out = thumbnail.create(
        _flat(rgb, tmp_path / "src.png"),
        "", "", tmp_path / "out.jpg", tmp_path,
    )
    # 字を置いていないので、画面ぜんたいが背景（左端のバーぶんだけ避ける）
    with Image.open(out) as im:
        luma = ImageStat.Stat(im.convert("L").crop((40, 0, 1280, 720))).mean[0]

    lo = thumbnail.BG_TARGET_LUMA - TOLERANCE
    hi = thumbnail.BG_TARGET_LUMA + TOLERANCE
    assert lo <= luma <= hi, (
        f"素材 {rgb} から作った背景の平均輝度が {luma:.1f} で、"
        f"行き先 {thumbnail.BG_TARGET_LUMA:.0f} ± {TOLERANCE:.0f} の外です。"
        "**素材の明るさが出来上がりに漏れています**"
    )


def test_黒い長方形にならない(tmp_path):
    """いちばん暗い素材でも、一覧で面が見えるところまで上がること。"""
    out = thumbnail.create(
        _flat((6, 6, 10), tmp_path / "src.png"),
        "元金0円が108回", "113,608円", tmp_path / "out.jpg", tmp_path,
    )
    with Image.open(out) as im:
        # 字の無い右下だけを見る（字の明るさで底上げされないように）
        luma = ImageStat.Stat(im.convert("L").crop((760, 600, 1280, 720))).mean[0]
    assert luma >= 12.0, (
        f"字の無いところの平均輝度が {luma:.1f} しかありません。"
        "**一覧では黒い長方形です** —— 直す前の控えがちょうどこの値（7〜16）でした"
    )
