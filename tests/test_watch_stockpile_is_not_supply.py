"""**待ちの「予約表では N本」が、作り置きを供給に数えていないこと。**（規則2）

## なぜ要るか（2026-09-01・最適化の回に、実測で踏んだ）

`src/watches._publish_dates()` は docstring どおり **予約ぶんも入れます**。
そのまま `_k_published_count()` の `placed` に入るので、`status.py` の待ちは
こう印字していました（実測 2026-09-01）:

    配信抑制-0824（いま 16 / 要る 30） … **予約表では 66本**
        （差 50本 は「出ていない」ではなく**「まだ実データが来ていない」**）

**同じ日に数えた実測**: 控えの未来の予約 **293本 は、293本 とも作り置き**
（`house_rule.is_stockpile`・作り置きでない未来の予約は **0本**）。
オーナーが 2026-08-31 に固定した規則2 の下では、`pool_drain --apply` が
外して非公開のまま置くので **1本も公開されません。**

`src/house_rule.py` は、この壊れ方を名指しで警告しています ——
**「これから出る本」として数えると、在りもしない供給で日付が早く出ます。**
**「外した結果、到達日は後ろへ動きます。それが正しい姿です。隠さないこと。」**

`scripts/eta.py` は毎回「**軌跡の腕が動くのは、前提を1件 閉じたときだけ**」と
印字します。**満ちない待ちを「待てばよい」と読ませることは、到達日を
そこで止めることと同じ**なので、ここは検査で固定します。

**覆る条件**: オーナーが規則2 を外したら（`house_rule.STOCKPILE_IS_SUPPLY` が
`True`）、`is_stockpile()` が全部 `False` を返すので警告は自然に消えます ——
そのときはこのファイルごと落とすこと。
"""
from __future__ import annotations

import json
from datetime import date

import pytest

from src import watches


@pytest.fixture()
def _uploaded(monkeypatch, tmp_path):
    """公開ずみ2本 ＋ 実データ待ち1本 ＋ **作り置きの予約3本**。"""
    rows = [
        # 公開ずみ（実データも来ている）
        {"video_id": "P1", "at": "2026-08-28T04:00:00Z",
         "uploaded_at": "2026-08-27T04:00:00Z"},
        {"video_id": "P2", "at": "2026-08-29T04:00:00Z",
         "uploaded_at": "2026-08-28T04:00:00Z"},
        # 公開ずみだが Analytics がまだ届いていない（**本当の実データ待ち**）
        {"video_id": "W1", "at": "2026-08-31T04:00:00Z",
         "uploaded_at": "2026-08-30T04:00:00Z"},
        # **作り置き**（規則より前に作った・未来の予約）＝ 公開されない
        {"video_id": "S1", "at": "2026-09-20T04:00:00Z",
         "uploaded_at": "2026-08-25T04:00:00Z"},
        {"video_id": "S2", "at": "2026-09-21T04:00:00Z",
         "uploaded_at": "2026-08-25T04:00:00Z"},
        {"video_id": "S3", "at": "2026-09-22T04:00:00Z",
         "uploaded_at": "2026-08-26T04:00:00Z"},
    ]
    path = tmp_path / "uploaded.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    monkeypatch.setattr(watches, "UPLOADED", path)
    monkeypatch.setattr(watches, "analytics_last_day", lambda: date(2026, 8, 29))
    monkeypatch.setattr(watches, "_jst_today", lambda: "2026-09-01", raising=False)
    return path


BASE = {"since": "2026-08-27", "need": 6, "data_ready": True}


def test_作り置きは実データ待ちに数えない(_uploaded, monkeypatch):
    """差の内訳を出すこと。**「予約に在るから待てばよい」で済ませない。**"""
    monkeypatch.setattr(watches, "_stockpile_ids",
                        lambda today=None: {"S1", "S2", "S3"})
    g = watches._k_published_count(dict(BASE))
    assert g.now == 2                       # P1 P2（実データが来ている本だけ）
    note = g.note or ""
    assert "作り置き" in note
    assert "3本 は作り置き" in note          # S1 S2 S3
    assert "本当に実データ待ちなのは 1本" in note   # W1 だけ
    # **足りない 4本 のうち、来る本で埋まるのは 1本。残り 3本 は新しく作るしかない**
    assert "あと 3本" in note
    assert "最短 3日" in note


def test_来る本だけで満ちるなら黙る(_uploaded, monkeypatch):
    """満ちる待ちに毎回 同じ警告を出しても、読む側の手は1つも変わらない。"""
    monkeypatch.setattr(watches, "_stockpile_ids",
                        lambda today=None: {"S1", "S2", "S3"})
    g = watches._k_published_count(dict(BASE, need=3))
    assert g.now == 2
    assert "作り置き" not in (g.note or "")   # W1 の1本で満ちる


def test_窓が閉じていて規則が許す本数に届かない待ちは永久に満ちないと言う(_uploaded, monkeypatch):
    """1日1本 の下で、2日の窓に 5本 は入りません（`house_rule.cap()`）。"""
    monkeypatch.setattr(watches, "_stockpile_ids",
                        lambda today=None: {"S1", "S2", "S3"})
    g = watches._k_published_count(
        {"since": "2026-09-20", "until": "2026-09-21", "need": 5,
         "data_ready": True})
    note = g.note or ""
    assert "永久に満ちません" in note
    assert "規則1 が許すのは **2本**" in note


def test_実物の控えでは未来の予約がすべて作り置きだった():
    """**実測を1つ、検査に残します**（2026-09-01）。

    この行が落ちるようになったら、規則2 の下で作った本が予約に入った
    ということなので、**それは良い知らせ**です —— 数を書き換えること。
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from src import house_rule
    assert house_rule.STOCKPILE_IS_SUPPLY is False
    assert house_rule.PUBLISH_PER_DAY == 1
