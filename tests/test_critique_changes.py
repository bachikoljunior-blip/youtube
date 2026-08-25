"""独立評価の報告のとなりに、**隣り合うコマの実測差**が出ること（2026-08-16 22:3x）。

## なぜこの検査が要るか

評価する体も目視する体も、見ているのは **contact sheet の縮んだタイル**です。
そこでは「表に1行増えた」「伏せていた数字が現れた」が読めないので、
**3回続けて「画面が変わっていない」と報告し、3回とも誤報**でした:

    08/16 21:5x  目視3体中2体「最終コマが描画失敗」  正体はこちらが描いた余り枠
    08/16 22:0x  独立評価3体「前提表が完全に同一」   実測 **16.10%** が違う
    08/16 22:3x  独立評価3体「冒頭2コマが同一」     実測 **12.24%** が違う

後の2件は `bake_slides.py` で焼き直して初めて否定できました（毎回10〜25分）。
**測る道具は最初からあり、値を捨てていただけ**です。

だから見るのは2つ。**両方向**を固定します（片方だけだと、
「いつも0件と言う」置物になっても検査は緑のままです）:

1. 差のある本では「同じ絵の組は0件」と言い、**指摘を打ち消しすぎない**
2. **本当に同じ組があるときは、ちゃんと本物だと言う**（故障注入）
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import critique_queue, critique_run  # noqa: E402


def _write_meta(tmp_path: Path, monkeypatch, video_id: str, payload: dict) -> None:
    (tmp_path / f"{video_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(critique_run, "QUEUE", tmp_path)


def test_ratios_above_floor_say_zero_pairs(tmp_path, monkeypatch):
    """差のある本 —— 「同じ絵の組は0件」と言い、**言いすぎない**。"""
    _write_meta(tmp_path, monkeypatch, "vid1",
                {"video_id": "vid1", "change_ratios": [0.1224, 0.161, 0.04]})
    out = critique_run._measured_changes("vid1")
    assert "同じ絵の組は0件" in out
    assert "4.00%" in out          # 最小がそのまま出る
    assert "16.10%" in out         # 最大も
    # **打ち消しすぎない。** 「変わったが気づかない」は否定できないと書いてあること
    assert "気づかない" in out


def test_ratio_below_floor_is_reported_as_real(tmp_path, monkeypatch):
    """故障注入 —— **本当に同じ組**があるときは、本物だと言うこと。

    ここが鳴らなければ、この節は「いつも0件」と言うだけの置物です。
    """
    _write_meta(tmp_path, monkeypatch, "vid2",
                {"video_id": "vid2", "change_ratios": [0.12, 0.0004, 0.08]})
    out = critique_run._measured_changes("vid2")
    assert "本物です" in out
    assert "2→3" in out            # 何組めかを名指しする
    assert "同じ絵の組は0件" not in out


def test_missing_ratios_are_not_silent(tmp_path, monkeypatch):
    """**「測っていない」と「差が無い」を混ぜないこと。**

    8/16 22:3x より前の本には `change_ratios` が入っていません。
    黙って空を返すと、次の回はそれを「同一の組は無い」と読みます。
    """
    _write_meta(tmp_path, monkeypatch, "vid3", {"video_id": "vid3"})
    out = critique_run._measured_changes("vid3")
    assert "実測がありません" in out
    assert "bake_slides.py" in out          # 測り直す道を必ず添える
    assert "同じ絵の組は0件" not in out


def test_no_meta_is_quiet(tmp_path, monkeypatch):
    """材料そのものが無い本では黙る（評価は材料が無くても回りうる）。"""
    monkeypatch.setattr(critique_run, "QUEUE", tmp_path)
    assert critique_run._measured_changes("nope") == ""


def _slide(path: Path, color: int) -> None:
    Image.new("L", (108, 192), color).save(path)


def test_change_ratios_measured_from_real_slides(tmp_path):
    """`stash()` の付録が、**焼いた実物**から測れていること。"""
    slides = tmp_path / "slides"
    slides.mkdir()
    _slide(slides / "slide_000.png", 0)
    _slide(slides / "slide_001.png", 255)     # 全面ちがう
    _slide(slides / "slide_002.png", 255)     # 前と同じ
    ratios = critique_queue._change_ratios(tmp_path)
    assert ratios is not None and len(ratios) == 2
    assert ratios[0] > 0.9                    # 塗り替わった
    assert ratios[1] == pytest.approx(0.0)    # 同じ絵


def test_change_ratios_none_when_too_few_slides(tmp_path):
    """1枚しか無い／slides が無い本では None。**投稿は止めない**（付録なので）。"""
    assert critique_queue._change_ratios(tmp_path) is None
    slides = tmp_path / "slides"
    slides.mkdir()
    _slide(slides / "slide_000.png", 0)
    assert critique_queue._change_ratios(tmp_path) is None
