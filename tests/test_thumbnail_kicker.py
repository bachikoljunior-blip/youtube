"""**サムネの上の1行（題材）が、書いた側から絵まで届くこと。**（2026-09-03 に足した）

## 何が壊れていたか

2026-08-31 に `src/thumbnail.create(kicker=)` と `src/pipeline.py` の
`getattr(script, "thumbnail_kicker", None)` が足されました。**読む側だけ**です ——
`VideoScript`（`src/script_writer.py`）にその欄が無く、pydantic は知らない欄を
黙って落とすので、**書き手が書いても `None` のまま**。足した日から 09/03 まで、
控え 694本 のどれにも題材の1行は載っていません（`grep -rn thumbnail_kicker` が
読む側の 2か所しか返さない）。**言っている所と、している所が別**、の1件。

## ここが見るのは3つ

    1. `VideoScript.model_validate_json` が `thumbnail_kicker` を落とさないこと
    2. 欄が無い古い台本も、いままでどおり通ること（既定は空）
    3. `style=outside_long` の絵は、上に黄色い箱（kicker）が在り、既定の絵とは別物で、
       字の無い帯が黒い長方形になっていないこと（`test_thumbnail_not_black` と同じ帯）

## 覆る条件

`thumbnail_kicker` を欄ごと外すなら、`src/pipeline.py` と `scripts/refresh_thumbnail.py`
の読む側も同じ commit で消すこと。片方だけ残すと、この検査が同じ穴をまた見つけます。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image, ImageStat

from src import thumbnail
from src.script_writer import VideoScript

ROOT = Path(__file__).resolve().parent.parent


def _minimal_script(**extra) -> dict:
    seg = {"narration": "ひとこと。", "visual": {
        "kind": "stat", "headline": "見出し", "stat": "1", "note": "", "stat_source": "",
        "formula": "", "items": [], "headers": [], "rows": [], "bars": []}}
    base = {
        "title": "題", "title_alternatives": ["a", "b"], "description_body": "本文",
        "tags": ["t"], "thumbnail_line1": "1行目", "thumbnail_line2": "2行目",
        "first_comment": "c", "segments": [seg], "chapters": [{"segment_index": 0, "label": "章"}],
    }
    base.update(extra)
    return base


def test_kicker_survives_validation():
    raw = json.dumps(_minimal_script(thumbnail_kicker="2026年4月からルール変更"), ensure_ascii=False)
    s = VideoScript.model_validate_json(raw)
    assert s.thumbnail_kicker == "2026年4月からルール変更"
    # pipeline が読む形（getattr）でも届くこと
    assert getattr(s, "thumbnail_kicker", None) == "2026年4月からルール変更"


def test_old_script_without_kicker_still_loads():
    s = VideoScript.model_validate_json(json.dumps(_minimal_script(), ensure_ascii=False))
    assert s.thumbnail_kicker == ""


def test_readers_and_schema_agree():
    """読む側（pipeline / refresh_thumbnail）が在る限り、型にも欄が在ること。"""
    readers = [ROOT / "src" / "pipeline.py", ROOT / "scripts" / "refresh_thumbnail.py"]
    assert any("thumbnail_kicker" in p.read_text(encoding="utf-8") for p in readers)
    assert "thumbnail_kicker" in VideoScript.model_fields


@pytest.fixture
def source(tmp_path: Path) -> Path:
    img = Image.new("RGB", (1920, 1080), (40, 20, 60))
    p = tmp_path / "slide.png"
    img.save(p)
    return p


def test_outside_style_has_kicker_box_and_is_not_black(source: Path, tmp_path: Path):
    work = tmp_path / "w"
    work.mkdir()
    a = thumbnail.create(source, "働く年金受給者", "年54万円増える", tmp_path / "a.jpg", work,
                         kicker="2026年4月からルール変更", style=thumbnail.OUTSIDE_STYLE)
    b = thumbnail.create(source, "働く年金受給者", "年54万円増える", tmp_path / "b.jpg", work,
                         kicker="2026年4月からルール変更")
    ia, ib = Image.open(a).convert("RGB"), Image.open(b).convert("RGB")
    assert ia.size == (thumbnail.W, thumbnail.H)
    # 既定の絵とは別物
    diff = ImageStat.Stat(Image.eval(Image.blend(ia, ib, 0.5), lambda v: v)).mean
    assert ia.tobytes() != ib.tobytes()
    assert diff is not None
    # 黄色い箱（kicker）が上に在る: 箱の色に近い画素が、上 1/3 に十分ある
    top = ia.crop((0, 0, thumbnail.W, thumbnail.H // 3))
    px = list(top.getdata())
    yellow = sum(1 for r, g, bl in px if r > 220 and g > 190 and bl < 90)
    assert yellow > 20_000, yellow
    # 字の無い右下の帯が黒い長方形ではない（`test_thumbnail_not_black` と同じ読み）
    band = ia.crop((thumbnail.W - 200, thumbnail.H - 60, thumbnail.W, thumbnail.H)).convert("L")
    assert ImageStat.Stat(band).mean[0] > 25


def test_default_style_unchanged_without_style(source: Path, tmp_path: Path):
    """`style` を渡さない呼び手は、これまでと1ピクセルも変わらない。"""
    work = tmp_path / "w"
    work.mkdir()
    a = thumbnail.create(source, "1行目", "2行目", tmp_path / "a.jpg", work)
    b = thumbnail.create(source, "1行目", "2行目", tmp_path / "b.jpg", work, style="")
    assert Image.open(a).tobytes() == Image.open(b).tobytes()
