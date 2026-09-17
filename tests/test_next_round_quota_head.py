"""**日枠が戻る刻（16:00 JST）が待ちの中に在るなら、起こしをそこへ手前倒しする。**

（2026-09-17 15:0x・optimizer・Fable 5.1・ultracode）

## 踏んだ当のもの（実測・`data/studio/ledger.jsonl` 09/16 の窓）

    16:00 JST  日枠が 10,000 に戻る
    16:49      `channels.list` **通った**
    19:01      **403**（うちはその間 1行 も撃っていません）

**＝ 戻った枠は 2〜3時間 で消えます。** 窓の頭に居るかどうかが、そのまま
「その日 1本 出せるか」です。ところが周の刻（床 129分）は 16:00 と合わず、
09/17 は 14:4x の周の次が **16:5x ＝ 窓の頭から 58分 遅れ**でした。
**5周 続けて `watermark`（50単位）が撃てずに終わった**のは、この刻ずれです。

## この検査が固定するもの

    1. 待ちの中に 16:00 JST が在れば、起こしはそこへ**手前倒し**される
    2. **手前へしか動かない**（間隔を伸ばす側には 1ミリも動かない）
    3. 窓の頭が待ちの外なら、**何も起きない**（＝ 陽性対照）

**覆る条件**: 窓の頭に立った周が 2窓 続けて 403 を踏んだら、遅れているのは刻ではなく枠
＝ 手前倒しを外すこと（`decide()` の註 (1)）。
"""
from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("next_round_head_mod",
                                               ROOT / "scripts" / "next_round.py")
nr = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(nr)

JST = timezone(timedelta(hours=9))
LAT = 3.0


def _pin(monkeypatch, tmp_path, now, floor):
    monkeypatch.setattr(nr, "floor_minutes", lambda: (floor, "検査で固定"))
    monkeypatch.setattr(nr, "wake_latency_minutes", lambda *a, **k: (LAT, "検査で固定"))
    monkeypatch.setattr(nr, "LIVE", tmp_path / "live_subs.json")
    monkeypatch.setattr(nr, "WAKE", tmp_path / "parent_wake.json")
    started = now - timedelta(minutes=5)
    group = [{"at": started.isoformat(), "role": r, "round": "R1"} for r in nr.ROLES]
    monkeypatch.setattr(nr, "current_round", lambda *a, **k: group)


def test_窓の頭が待ちの中なら起こしはそこへ手前倒しされる(monkeypatch, tmp_path):
    """**これが本体です。** 09/17 14:49 JST・床129分 → 素の起こしは 16:5x。窓の頭は 16:00。"""
    now = datetime(2026, 9, 17, 14, 49, tzinfo=JST)
    _pin(monkeypatch, tmp_path, now, 129.0)
    d = nr.decide(now=now, live=0)
    assert d["go"] is False and d.get("idle") is True, d
    assert d.get("quota_head_pull_min"), "手前倒しが効いていません"
    arrives = d["wake_at"] + timedelta(minutes=LAT)
    head = now.replace(hour=16, minute=0, second=0, microsecond=0)
    assert abs((arrives - head).total_seconds()) <= 90, \
        f"届く時刻が窓の頭に乗っていません（{arrives} / 頭 {head}）"


def test_手前へしか動かない(monkeypatch, tmp_path):
    """**陽性対照 1**: 窓の頭が素の起こしより後なら、1分 も動かないこと。"""
    now = datetime(2026, 9, 17, 14, 49, tzinfo=JST)
    _pin(monkeypatch, tmp_path, now, 30.0)      # 素の起こしは 15:1x ＝ 16:00 より手前
    d = nr.decide(now=now, live=0)
    assert d["go"] is False, d
    assert "quota_head_pull_min" not in d, "窓の頭が後ろなのに動かしています（伸ばす側へ動いた）"
    assert d["wake_min"] <= 30


def test_窓の頭を過ぎた直後は次の日の頭を見る(monkeypatch, tmp_path):
    """**陽性対照 2**: 16:05 JST に立った周が、いま過ぎたばかりの 16:00 へ倒れないこと。"""
    now = datetime(2026, 9, 17, 16, 5, tzinfo=JST)
    _pin(monkeypatch, tmp_path, now, 129.0)
    d = nr.decide(now=now, live=0)
    assert d["go"] is False, d
    assert "quota_head_pull_min" not in d, "過ぎた窓の頭へ倒しています（起こしが過去になります）"
    assert d["wake_at"] > now


def test_刻の写しを持たない(monkeypatch, tmp_path):
    """**陽性対照 3**: `budget.RESET_H` を動かすと、手前倒しの先も動くこと（16 を写していない）。"""
    import studio.budget as budget
    monkeypatch.setattr(budget, "RESET_H", 20)
    now = datetime(2026, 9, 17, 18, 49, tzinfo=JST)
    _pin(monkeypatch, tmp_path, now, 129.0)
    d = nr.decide(now=now, live=0)
    assert d.get("quota_head_pull_min"), "刻を動かしたのに追随していません"
    arrives = d["wake_at"] + timedelta(minutes=LAT)
    head = now.replace(hour=20, minute=0, second=0, microsecond=0)
    assert abs((arrives - head).total_seconds()) <= 90, f"{arrives} / 頭 {head}"
