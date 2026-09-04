"""**前提のために枠を取りながら、処置になっていない本を枠へ入れないこと。**

実測（2026-09-04 19:5x・最適化の回）:

    `daily_pick.treated_count("長尺")` → (0, 36)
    09-04 の枠に入った `1huadpEk6HY` の脚 → (2)(4)(5) が ✗ → 公開・齢6時間で 0回
    09-04 の決めは 14回、全部 長尺。`standing_pick_treatment()` が刷ったあとも 6回 長尺

**印字は選び直しを止めませんでした。** ここは止める側の検査です。
戻すと、この4件が落ちます。
"""
from __future__ import annotations

import json

import pytest

from src import daily_pick


TOPICS = [{"id": "out", "style": "outside_long"},
          {"id": "plain", "style": "normal"}]


def _script(tmp_path, vid: str, body: dict) -> None:
    (tmp_path / f"{vid}.script.json").write_text(
        json.dumps(body, ensure_ascii=False), encoding="utf-8")


def test_脚が欠けた本は枠へ入れない(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_pick, "treated_count", lambda *a, **k: (0, 36))
    monkeypatch.setattr(daily_pick, "pick_legs",
                        lambda vid, **k: (["(2) 章・締め", "(4) 題・サムネ"], None))
    out = daily_pick.untreated_slot_block(
        {"topic": "out", "video_id": "V1"}, topics=TOPICS, queue=tmp_path)
    assert out, "脚が ✗ で処置 0本 なら、理由の1行が返ること"
    assert "V1" in out and "0/36" in out


def test_脚が全部通っていれば止めない(tmp_path, monkeypatch):
    monkeypatch.setattr(daily_pick, "treated_count", lambda *a, **k: (0, 36))
    monkeypatch.setattr(daily_pick, "pick_legs", lambda vid, **k: ([], None))
    assert daily_pick.untreated_slot_block(
        {"topic": "out", "video_id": "V1"}, topics=TOPICS, queue=tmp_path) == ""


def test_処置ずみが1本でも出たら黙る(tmp_path, monkeypatch):
    """**分母が出来たら、この門は仕事を終えます**（docstring の「覆る条件」）。"""
    monkeypatch.setattr(daily_pick, "treated_count", lambda *a, **k: (1, 36))
    monkeypatch.setattr(daily_pick, "pick_legs",
                        lambda vid, **k: (["(2) 章・締め"], None))
    assert daily_pick.untreated_slot_block(
        {"topic": "out", "video_id": "V1"}, topics=TOPICS, queue=tmp_path) == ""


@pytest.mark.parametrize("cur", [
    None,
    {"topic": "plain", "video_id": "V1"},          # 型の無い題材には言わない
])
def test_当たらない場合(tmp_path, monkeypatch, cur):
    monkeypatch.setattr(daily_pick, "treated_count", lambda *a, **k: (0, 36))
    monkeypatch.setattr(daily_pick, "pick_legs",
                        lambda vid, **k: (["(2) 章・締め"], None))
    assert daily_pick.untreated_slot_block(cur, topics=TOPICS, queue=tmp_path) == ""


def test_控えが読めない本は止めない(tmp_path, monkeypatch):
    """**読めないものを ✗ に数えない**（`pick_legs` と同じ向き）。"""
    monkeypatch.setattr(daily_pick, "treated_count", lambda *a, **k: (0, 36))
    monkeypatch.setattr(daily_pick, "pick_legs",
                        lambda vid, **k: ([], "控えが読めません"))
    assert daily_pick.untreated_slot_block(
        {"topic": "out", "video_id": "V1"}, topics=TOPICS, queue=tmp_path) == ""
