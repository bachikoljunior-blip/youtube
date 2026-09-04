"""**枠が 0本 の日に、どの道が開いているかを門が言うこと。**

## なぜ要るか（2026-09-05 未明・最適化の回。**この回に撃って踏んだ**）

門の最後の行は「**撃てないなら**（日枠 ＝ JST 16:00 に戻る）、理由を JOURNAL に
書いて終わること」でした。**「撃てないなら」の判定を回に任せています。**

そして日枠は**道ごとに別々に閉じます** —— `videos.update`（50単位）が 403 でも
`videos.insert`（1600単位）は通ります（`scripts/reschedule.py` の 403 の本文）。
**安いほうが先に閉じる**ので、「日枠だから何もできない」はたいてい誤りです。

実物（この検査を足した回）: 09/05 の枠を空けたあと `--move` が 403。
**`upload_only.py`（insert）なら、その同じ窓で埋められます。**

ここで固定するのは2つ:

    1. 差し替えが閉じている窓では、**戻る時刻**と**insert は通る**ことを門が言う
    2. 開いている窓では**1行も出さない**（毎周 鳴る行を増やさない）
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

slot_gate = pytest.importorskip("slot_gate")

JST = timezone(timedelta(hours=9))
BACK = datetime(2026, 9, 5, 7, 0, tzinfo=timezone.utc)      # 09/05 16:00 JST


def test_閉じている窓では戻る時刻とinsertの道を言う(monkeypatch):
    from src import next_slot
    monkeypatch.setattr(next_slot, "writable_from", lambda now=None: BACK)
    out = "\n".join(slot_gate.quota_lines())
    assert "16:00 JST" in out, out
    assert "videos.update" in out and "403" in out, out
    # **ここが本体** —— 閉じているのは差し替えの側だけだと言うこと
    assert "videos.insert" in out and "upload_only" in out, out


def test_開いている窓では1行も出さない(monkeypatch):
    from src import next_slot
    monkeypatch.setattr(next_slot, "writable_from", lambda now=None: None)
    assert slot_gate.quota_lines() == []


def test_読めない回は黙る(monkeypatch):
    """**推測しないこと。** 読めないのと「開いている」は別です。"""
    from src import next_slot

    def _boom(now=None):
        raise RuntimeError("読めない")

    monkeypatch.setattr(next_slot, "writable_from", _boom)
    assert slot_gate.quota_lines() == []


def test_枠が0本の日の本文に混ざる(monkeypatch):
    """**関数を足しただけでは効きません** —— 印字に入っていること。"""
    from src import next_slot
    monkeypatch.setattr(next_slot, "writable_from", lambda now=None: BACK)
    today = datetime.now(JST).date()
    rows = [{"video_id": "x", "at": None, "uploaded_at": "2026-09-01T00:00:00+00:00"}]
    out = "\n".join(slot_gate.lines(rows, today))
    assert out, "枠が 0本 なら、門は必ず何か言います"
    assert "videos.insert" in out, out
