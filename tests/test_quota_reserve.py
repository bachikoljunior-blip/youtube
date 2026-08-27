"""**計測のぶんの単位を、書き込みが食い切らないこと**（2026-08-28 に足した）。

## なぜ要るか（実測）

窓 08/27 07:00Z（＝ **16:00 JST**）〜 の `data/day_quota.jsonl`:

    16:11 JST  最初の `videos.update`
    16:47 JST  **最初の 403**（通った 183回 ＝ 9,150単位・枠は 10,000）
    ↓
    **残りの 23.2時間、読みも書きも 403**（403 を 194回 観測）

`config/hypotheses.yaml` の 08-28 の前提が要る読みは
**「22:00 JST 以降に `python scripts/snapshot.py` を1回」＝ 4単位**です。
**9,150単位 を 47分 で焼いて、そのあと 4単位 が撃てません。**

`eta.py` は毎回「**軌跡の腕が動くのは、前提を1件閉じたときだけ**」と印字します。
つまり **到達日を動かす唯一の操作が、到達日を 0日 しか動かさない操作に
先を越されて、毎日 23時間 不可能になっていました**（実際に 08/27 夕・
08/28 未明 と **2回 続けて**、期限の来た前提が閉じずに終わっています）。

## この検査が見ているもの

1. **推測では止めないこと。** 枠の実測（`measured_budget()["floor"]`）が
   無い窓では、必ず `None`（＝撃ってよい）
2. 実測があり、残りが `RESERVE_UNITS` を切ったら止めること
3. **止めるのは書き込みだけ。** `videos.insert`（投稿）はこの枠を1単位も
   使わないので、**投稿は1本も減りません**（`UNIT_COST` の註）
4. 書き込みの入口（`reschedule._update` / `uploader._set_thumbnail`）が、
   撃つ前に必ずここを通ること

## 覆る条件

`videos.insert` が同じ 403 で落ちるようになったら（＝枠が1つに統合された）、
この関門は**投稿を減らす側に効きはじめます。**そのときは大きさを測り直すこと。
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import upload_cap                                     # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def test_枠の実測が無い窓では止めない(monkeypatch):
    """**推測で書き込みを止めないこと。** 外す向きは、今までどおり 403 を見る側。"""
    monkeypatch.setattr(upload_cap, "measured_budget",
                        lambda now=None: {"floor": 0, "spent": 99_999, "left": 0})
    assert upload_cap.reserve_hold() is None


def test_残りが計測のぶんを切ったら止める(monkeypatch):
    monkeypatch.setattr(
        upload_cap, "measured_budget",
        lambda now=None: {"floor": 10_000,
                          "spent": 10_000 - upload_cap.RESERVE_UNITS, "left": 0})
    held = upload_cap.reserve_hold()
    assert held and "計測" in held


def test_まだ余っていれば止めない(monkeypatch):
    monkeypatch.setattr(
        upload_cap, "measured_budget",
        lambda now=None: {"floor": 10_000,
                          "spent": 10_000 - upload_cap.RESERVE_UNITS - 1, "left": 1})
    assert upload_cap.reserve_hold() is None


def test_外せること(monkeypatch):
    """**逃げ道は残すこと。** 使った回は理由を JOURNAL に。"""
    monkeypatch.setattr(upload_cap, "measured_budget",
                        lambda now=None: {"floor": 10_000, "spent": 10_000, "left": 0})
    monkeypatch.setenv("YT_NO_RESERVE", "1")
    assert upload_cap.reserve_hold() is None


def test_書き込みの入口が関門を通っていること():
    """**入口ごとに1回ずつ。** どちらかが抜けると、そちらから全部 焼けます。"""
    resched = (ROOT / "scripts" / "reschedule.py").read_text(encoding="utf-8")
    body = resched.split("def _update(")[1].split("\ndef ")[0]
    assert "reserve_hold()" in body.split("videos().update(")[0], (
        "`reschedule._update` が `videos.update` を撃つ前に "
        "`upload_cap.reserve_hold()` を見ていません")

    up = (ROOT / "src" / "uploader.py").read_text(encoding="utf-8")
    thumb = up.split("def _set_thumbnail(")[1].split("\ndef ")[0]
    assert "reserve_hold()" in thumb.split("thumbnails().set(")[0], (
        "`uploader._set_thumbnail` が `thumbnails.set` を撃つ前に "
        "`upload_cap.reserve_hold()` を見ていません")


def test_投稿そのものは止めないこと():
    """**`videos.insert` に関門を置かないこと** —— 別の枠から出ています
    （実測 08/17 以後3度）。置くと `docs/GOAL.md`「投稿が途切れるのが
    最大の損失」に真っ向から反します。
    """
    up = (ROOT / "src" / "uploader.py").read_text(encoding="utf-8")
    for chunk in up.split("videos().insert(")[:-1]:
        tail = chunk.rsplit("def ", 1)[-1]
        assert "reserve_hold()" not in tail, (
            "`videos.insert` の手前で `reserve_hold()` を見ています。"
            "**投稿はこの枠を1単位も使いません**")
