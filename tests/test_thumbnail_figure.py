"""**外の型の絵（`outside_long`）に、描いた人物1体が右側に在ること。**（2026-09-03 に足した）

## なぜ

前提「外の作り方を写した長尺」の2本（09/04 `1huadpEk6HY`・09/05 `DfFyu8qZq3I`）は
題・尺・中身・絵・冒頭を写して、**顔だけ写していなかった**（外の上位4本は 4/4 が人の顔）。
実在の人物は使えない（なりすまし）ので、**描いた人物（固定の1体・名乗り無し）**を置く
（`src/thumbnail.OUTSIDE_FIGURE` の註）。

## ここが見るのは3つ

    1. `outside_long` の絵の右側に、肌の色と背広の色の画素が在ること（人物が描かれている）
    2. 主語（赤い字）が人物の左端 `OUTSIDE_FIGURE_LEFT` を越えないこと（字と人物が重ならない）
    3. 既定の絵（style 無し）には人物が無いこと（ほかの題材は1ピクセルも変わらない）

## 覆る条件

`OUTSIDE_FIGURE = False` に戻したら 1 と 2 は要らない（3 は残る）。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from PIL import Image

from src import thumbnail


@pytest.fixture
def source(tmp_path: Path) -> Path:
    img = Image.new("RGB", (1920, 1080), (20, 50, 40))
    p = tmp_path / "slide.png"
    img.save(p)
    return p


def _near(px, ref, tol=40) -> bool:
    return all(abs(a - b) <= tol for a, b in zip(px, ref))


def test_outside_style_has_figure_on_the_right(source: Path, tmp_path: Path):
    out = thumbnail.create(source, "働く年金受給者", "年54万円増える", tmp_path / "t.jpg",
                           tmp_path / "w", kicker="2026年4月からルール変更",
                           style=thumbnail.OUTSIDE_STYLE)
    img = Image.open(out).convert("RGB")
    cx = thumbnail.FIGURE_CX
    assert _near(img.getpixel((cx, 200)), thumbnail.FIGURE_HAIR)         # 髪
    assert _near(img.getpixel((cx - 30, 345)), thumbnail.FIGURE_SKIN)    # 頬（目と口のあいだ）
    assert _near(img.getpixel((cx - 150, 700)), thumbnail.FIGURE_SUIT)   # 背広の肩
    assert cx > thumbnail.OUTSIDE_FIGURE_LEFT


def test_red_subject_stays_left_of_the_figure(source: Path, tmp_path: Path):
    out = thumbnail.create(source, "働く年金受給者", "年54万円増える", tmp_path / "t.jpg",
                           tmp_path / "w", kicker="2026年4月からルール変更",
                           style=thumbnail.OUTSIDE_STYLE)
    img = Image.open(out).convert("RGB")
    w, h = img.size
    # 赤い主語の画素（ネクタイは y≥480 なので、上半分だけ数える）
    reds = [(x, y) for x in range(thumbnail.OUTSIDE_FIGURE_LEFT, w) for y in range(0, 470, 2)
            if (lambda p: p[0] > 200 and p[1] < 80 and p[2] < 80)(img.getpixel((x, y)))]
    assert not reds, f"赤い字が人物の側へ {len(reds)} 画素 はみ出しています"


def test_default_style_has_no_figure(source: Path, tmp_path: Path):
    out = thumbnail.create(source, "働く年金受給者", "年54万円増える", tmp_path / "t.jpg",
                           tmp_path / "w", kicker="2026年4月からルール変更")
    img = Image.open(out).convert("RGB")
    cx = thumbnail.FIGURE_CX
    assert not _near(img.getpixel((cx - 30, 345)), thumbnail.FIGURE_SKIN)
    assert not _near(img.getpixel((cx - 150, 700)), thumbnail.FIGURE_SUIT)
