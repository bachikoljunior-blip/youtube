"""**測れていない説明欄を、「0件」と印字しないこと。**（2026-08-31・最適化の回）

## なぜ要るか

`src/descriptions.py` は、停止の理由（`AUTOMATION_PAUSED.md` の解除条件1・2）が
**最後に残っていた面** —— 説明欄 —— を測るために書かれました。正本は Data API で、
控えには1文字も無いことを、この回に自分で数え直して確かめています
（`data/critique_queue/*.json` 694本・`*.plan.json` 655本・`data/uploaded.jsonl` 850行
に `description` 系の欄は **0件**）。

2026-08-31 07:3x に撃ったら、Data API の日枠で 403 が返り、**0本**を持ち帰りました。
それでも `report()` はこう出しました:

    台帳 735本 ／ 説明欄が返った 0本（差 735本 は**チャンネルに無い本**）
    --- 1) 説明欄で人間の専門家を装っているか（解除条件 1・2）---
      **0 / 0本**
    --- 2) 説明欄で行動を指図しているか ---
      **0 / 0本**

**2つとも嘘です。** 735本 はチャンネルに在ります（消えたのではなく、まだ訊いていない）。
そして「**0 / 0本**」は「測って0件」と1文字も違いません ——
番号の付いた節だけを読んだ回は、**停止の理由そのものが、最後の面でも綺麗だった**
と読みます。**測っていないのに。**

いまここが効く場所は1か所しかありません。`python scripts/eta.py --gate` が毎回
言うとおり、**停止中に到達日を動かせるのは審査の門だけ**です。その門のうち2件
（1・2）を、測っていない0で閉じたまま置ける道具が、その門の上に載っていました。

**この repo は同じ決まりを2か所で先に決めています** ——
`src/bars.py` と `verify._check_frame_repeat()`:
**比較対象が無いのは「合格」ではなく「判定していない」。**

## 覆る条件

台帳が本当に空のチャンネル（`asked == 0`）は、ここが邪魔をします。
そのときは `_UNMEASURED` の文言を分けること。
"""
from __future__ import annotations

import json

from src import descriptions, legacy_corpus


def _cache(tmp_path, **over):
    d = {"at": "2026-08-31T00:00:00+00:00", "asked": 735, "got": 0,
         "partial": True, "videos": []}
    d.update(over)
    p = tmp_path / "descriptions.json"
    p.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    return p


def test_1本も取れていない回は_0件と印字しない(tmp_path):
    out = descriptions.report(cache=_cache(tmp_path))
    assert "0 / 0本" not in out, (
        "**測っていない0を、測った0と同じ形で出しています。**\n"
        "0本の分母で『0 / 0本』と出すと、番号の節だけ読んだ回が\n"
        "『解除条件1・2 は説明欄でも0件だった』と読みます。\n" + out)
    assert "まだ1本も測れていません" in out


def test_1本も取れていない回は_差をチャンネルのせいにしない(tmp_path):
    out = descriptions.report(cache=_cache(tmp_path))
    assert "チャンネルに無い本" not in out, (
        "日枠で止まった回の差は『まだ訊いていない本』です。\n"
        "『チャンネルに無い』と出すと、**消えたのかと調べに行く回が出ます**。\n" + out)
    assert "まだ訊いていません" in out


def test_途中まで取れた回は_台帳の何割かを隣に置く(tmp_path):
    recs = [{"video_id": f"v{i}", "title": "t", "description": "本文\n\n▼ 目次\n",
             "privacy": "public"} for i in range(50)]
    out = descriptions.report(cache=_cache(tmp_path, got=50, videos=recs))
    assert "0 / 50本" in out, out
    assert "735本 の 7%" in out, (
        "**50本ぜんぶ綺麗**が、**735本ぜんぶ綺麗**に読めます。\n"
        "節ごとの数の隣に、台帳の何割かを置くこと。\n" + out)


def test_全部取れた回は_割合の但し書きを出さない(tmp_path):
    recs = [{"video_id": f"v{i}", "title": "t", "description": "本文\n\n▼ 目次\n",
             "privacy": "public"} for i in range(735)]
    out = descriptions.report(cache=_cache(tmp_path, got=735, partial=False,
                                           videos=recs))
    assert "だけ**です" not in out, out
    assert "0 / 735本" in out, out


def test_legacy_corpusの1行も_途中で止まったことを言う(monkeypatch):
    """`legacy_corpus` は解除条件5を閉じた道具です。**同じ穴を持たせないこと。**"""
    monkeypatch.setattr(descriptions, "load", lambda *a, **k: {
        "at": "2026-08-31T00:00:00+00:00", "asked": 735, "got": 50,
        "partial": True,
        "videos": [{"video_id": "v", "title": "t", "description": "本文",
                    "privacy": "public"}] * 50})
    line = legacy_corpus.description_line()
    assert "7% だけ" in line and "685本 は未測定" in line, line
    assert "日枠で途中で止まりました" in line, line
