"""**差し替えの2手が枠を要ることを、焼き直しの案内と同じ所で言う。**

## なぜ要るか（2026-09-01 09:1x に、一歩手前で気づいた）

`next_slot.lines()` は「焼き直すのが `improve` の1手です
（`--unschedule <古い方>` → 新しい方を `--move`）」と案内します。
**その2手はどちらも `videos.update`（50単位）** で、日枠が尽きた窓では 403 です。

**一方で、焼き直し（`python -m src.pipeline`）は 0単位、`videos.insert` も
日枠を1単位も使いません**（`tests/test_insert_never_marked_ok.py` に実測3度）。
**そこだけ撃てる**ので、次の形になります:

    新しい本を 22:00 に insert する  → 通る
    古い本の予約を外す              → **403**
    結果                            → **22:00 に 2本 公開される**

**オーナー規則1（1日1本・`src/house_rule.py`）に正面から当たります。**
2026-09-01 09:1x の回は、`upload_cap` の「insert は日枠を使わない」を
読んだ直後にこの案内を撃とうとして、**外す側が 403 だと気づいて止めました。**
**気づかなければ、規則が破れていました。**

## 覆る条件

- `reschedule` が `videos.update` を使わない道を持ったら、この案内は要りません
- **これは門ではありません。** 撃つ側が判断します（止めると、枠の在る窓まで
  焼き直しが止まる）
"""
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import next_slot  # noqa: E402


def test_差し替えの値段は_videos_updateを2回ぶん() -> None:
    """**焼き直しそのものは 0単位。** 枠を要るのは外す側と入れ直す側だけ。"""
    assert next_slot.SWAP_UNITS == 100


def test_枠が尽きた窓では_2本出る危険を名指しする(monkeypatch) -> None:
    from src import quota_ledger, upload_cap

    monkeypatch.setattr(quota_ledger, "spent",
                        lambda *a, **k: {"data": quota_ledger.DAY_UNITS + 1})
    monkeypatch.setattr(upload_cap, "window_end",
                        lambda *a, **k: datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc))
    got = "\n".join(next_slot.swap_cost_lines())
    assert "403" in got, "撃てないことを言っていない"
    assert "2本" in got, "**同じ枠に2本 出る**ことを言っていない"
    assert "規則1" in got, "どの規則に当たるかを名指ししていない"
    assert "videos.insert" in got, (
        "「insert は通る」を言っていない —— そこが落とし穴の入口です")


def test_枠が在る窓では_在ると言うだけ(monkeypatch) -> None:
    """**止める門ではありません。** 枠が在れば、値段を言って通す。"""
    from src import quota_ledger, upload_cap

    monkeypatch.setattr(quota_ledger, "spent", lambda *a, **k: {"data": 10})
    monkeypatch.setattr(upload_cap, "window_end",
                        lambda *a, **k: datetime(2026, 9, 1, 7, 0, tzinfo=timezone.utc))
    got = "\n".join(next_slot.swap_cost_lines())
    assert "枠は在ります" in got
    assert "403" not in got


def test_帳面が読めない回は何も言わない(monkeypatch) -> None:
    """**推測で手を止めないこと**（この repo の他の門と同じ姿勢）。"""
    from src import quota_ledger

    def boom(*a, **k):
        raise RuntimeError("帳面が読めない（テスト）")

    monkeypatch.setattr(quota_ledger, "spent", boom)
    assert next_slot.swap_cost_lines() == []


def test_焼き直しの案内と同じ所に出ている() -> None:
    """**別の節に置かないこと。** 案内の直後でなければ、読む側は届く前に撃ちます。"""
    src = (ROOT / "src" / "next_slot.py").read_text(encoding="utf-8")
    i = src.index("焼き直すのが `improve` の1手です")
    # **`(t)` で綴じないこと**（2026-09-01 22:0x）—— 2つ目の引数
    # （`publish_at`）が足されて、この索きが `ValueError` で落ちました。
    # 見ているのは「案内の直後に在るか」だけなので、開き括弧までで足ります。
    j = src.index("swap_cost_lines(t")
    assert 0 < j - i < 400, (
        "差し替えの値段が、焼き直しの案内から離れています")
