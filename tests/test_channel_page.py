"""`src/channel_page.py` の検査。**外へは1回も出ません。**"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from src import channel_page as cp


def test_床に届かない行は選ばない():
    """**1再生1人が勝たないこと。** 登録率 0.0443% では 100再生の期待値は 0.04人。"""
    rows = [("a", 1, 1), ("b", 400, 5), ("c", 600, 1)]
    assert cp.pick_trailer(rows) is None


def test_登録に変えた率がいちばん高い本を選ぶ():
    """**再生がいちばん多い本ではありません。** 選ぶのは率のほう。"""
    rows = [("many", 5000, 2), ("best", 1451, 3), ("mid", 1740, 2)]
    assert cp.pick_trailer(rows) == "best"


def test_実測の行でCdX2oIb7BG8が出る():
    """2026-08-20 20:2x の実データ。**この並びで別の本が出たら、床が動いています。**"""
    rows = [
        ("NHKylqsNfTw", 1864, 0), ("gPusj-Y2404", 1740, 1), ("YmJ7psxW3co", 1508, 0),
        ("CdX2oIb7BG8", 1451, 3), ("pMHDwK5tB2E", 1437, 0), ("7b2-Z6Jw5DQ", 1360, 1),
    ]
    assert cp.pick_trailer(rows) == "CdX2oIb7BG8"


def test_床の値が掛け算から出ていること():
    """**勘で置いた床は、この repo が一度踏んだ形です**（`hypotheses.yaml` 冒頭）。

    床の再生数 × ショートの実測 0.0355% が、要求する人数を**下回っていない**こと。
    下回るなら、その床では偶然と区別が付きません。
    """
    assert cp.MIN_VIEWS * 0.000355 < cp.MIN_SUBS


def test_バナーは寸法と安全帯を守る(tmp_path: Path):
    out = cp.render_banner(tmp_path / "b.png")
    with Image.open(out) as img:
        assert img.size == cp.BANNER_SIZE
        # 安全帯の外（左端）は、背景のままであること ＝ 字がはみ出していない
        assert img.getpixel((10, cp.BANNER_SIZE[1] // 2)) == cp.BANNER_BG
        assert img.getpixel((cp.BANNER_SIZE[0] - 10, cp.BANNER_SIZE[1] // 2)) == cp.BANNER_BG


def test_安全帯の中には何か描かれている(tmp_path: Path):
    """**空の画像を「描けた」と言わないこと。**"""
    out = cp.render_banner(tmp_path / "b.png")
    sx = (cp.BANNER_SIZE[0] - cp.SAFE_SIZE[0]) // 2
    sy = (cp.BANNER_SIZE[1] - cp.SAFE_SIZE[1]) // 2
    with Image.open(out) as img:
        band = img.crop((sx, sy, sx + cp.SAFE_SIZE[0], sy + cp.SAFE_SIZE[1]))
        assert len(band.getcolors(maxcolors=1 << 16) or []) > 8
