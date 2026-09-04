"""**規則3 の相手に手が届くのかを、画面が言うこと。**

## なぜ要るか（2026-09-05 07:2x に実測して踏んだ）

規則3 は「次の枠で出る1本を、出る瞬間まで良くし続ける」。
**その1本の題・説明・絵を変える道は `videos.update` だけ**で、日枠が尽きると 403、
戻るのは翌 16:00 JST（`next_slot.writable_from`）。

実測（09/05 07:2x JST）:

    次の枠の1本 `kzefG44_APU`   公開 **09:00 JST**
    `videos.update` が戻るのは   **16:00 JST**（**7時間 遅い**）
    ＝ **公開までに1文字も書けない。**

**規則3 が名指しする相手が、構造上 手の届かない所に居ました。**
そして画面はそれを一言も言っていませんでした —— `writable_from()` は
`reschedule`（動かす側）と `slot_gate` からしか呼ばれておらず、
**「良くし続ける」と書いてある側からは1度も呼ばれていません。**

＝ 回は当てどころを探し、**撃てないと分かるまでの時間を毎回 使います。**
届かない相手を名指ししているあいだ、届く相手（**その次の日の1本** ——
まだ `insert` していないので台本ごと変えられる）は名指しされません。

## 覆る条件

`reschedule` が `videos.update` を使わない道を持ったら（差し替えが日枠の外に
出たら）、この検査ごと要りません（`next_slot.writable_from()` の覆る条件と同じ日）。
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import daily_pick as dp  # noqa: E402

_UTC = timezone.utc


def _row(at: datetime) -> dict:
    return {"video_id": "vid1", "topic": "s-x", "title": "t #Shorts", "_at": at}


def _patch(monkeypatch, wf: datetime | None):
    from src import next_slot as ns
    monkeypatch.setattr(ns, "writable_from", lambda now=None: wf)


def test_it_says_when_the_book_cannot_be_written_before_it_publishes(monkeypatch):
    """**窓が公開より後なら、はっきりそう言うこと。**"""
    at = datetime(2026, 9, 5, 0, 0, tzinfo=_UTC)        # 09:00 JST 公開
    _patch(monkeypatch, datetime(2026, 9, 5, 7, 0, tzinfo=_UTC))   # 16:00 JST に戻る
    out = "\n".join(dp.improve_window_lines(_row(at)))
    assert "公開までに1文字も書けません" in out, out
    assert "7.0時間 遅い" in out, out
    # **届く相手を名指ししていること** —— 「できません」で終えない
    assert "その次の日の1本" in out, out
    assert "metadata_fix" in out, out


def test_it_says_the_book_is_still_reachable_when_the_window_opens_in_time(monkeypatch):
    """窓が公開より前に戻るなら、「間に合う」と言うこと（止めない）。"""
    at = datetime(2026, 9, 5, 12, 0, tzinfo=_UTC)       # 21:00 JST 公開
    _patch(monkeypatch, datetime(2026, 9, 5, 7, 0, tzinfo=_UTC))   # 16:00 JST に戻る
    out = "\n".join(dp.improve_window_lines(_row(at)))
    assert "公開には間に合います" in out, out
    assert "公開までに1文字も書けません" not in out, out


def test_it_says_the_book_is_writable_now(monkeypatch):
    """日枠が尽きていない回は、持ち時間だけを言うこと。"""
    at = datetime(2026, 9, 5, 12, 0, tzinfo=_UTC)
    _patch(monkeypatch, None)
    out = "\n".join(dp.improve_window_lines(_row(at)))
    assert "いま書けます" in out, out
    assert "規則3 の持ち時間" in out, out


def test_no_row_no_line(monkeypatch):
    """次の枠が無ければ、何も出さないこと。"""
    _patch(monkeypatch, None)
    assert dp.improve_window_lines(None) == []


def test_the_window_line_is_on_the_main_screen(monkeypatch):
    """**規則3 の相手を名指しする行のすぐ下に出ること。**"""
    at = datetime(2026, 9, 5, 0, 0, tzinfo=_UTC)
    _patch(monkeypatch, datetime(2026, 9, 5, 7, 0, tzinfo=_UTC))
    out = dp.lines(_row(at))
    joined = "\n".join(out)
    assert "[窓]" in joined, "窓の行が `[きょうの1本]` に出ていません"
    named = next(i for i, ln in enumerate(out) if "次に出る本" in ln)
    win = next(i for i, ln in enumerate(out) if "[窓]" in ln)
    assert win == named + 1, (
        f"窓の行が、相手を名指しする行の真下にありません（{named} → {win}）")
