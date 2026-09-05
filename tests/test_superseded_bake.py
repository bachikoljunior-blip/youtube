"""**いま焼いている本が、その日の決めから外れたら、そう言うこと。**

## なぜ要るか（2026-09-05 06:2x・最適化の回。**実物で走っていました**）

焼き直しは `ahead_sweep.rebake_plan_for()` が `daily_pick.current(day)` を読んで
始めます —— **始めるときは、決めに従っています。** 見ていなかったのは**そのあと**:

    04:12 JST  hourly が `GFvAcxvDmYM`（長尺・09/05 の枠）の焼き直しを始める
    05:09 / 05:11 / 05:37 JST  09/05 の決めが3回 動く（どれも ショート）
    06:18 JST  **長尺のほうは、まだ焼いている**（2時間・レンダリング中）

**規則は1日1本**なので、枠の形を1つ間違えるとその日の取り分がまるごと変わります
（齢48h 中央値: ショート 164回・n=216 ／ 長尺 1回・n=36）。

ここで固定するのは3つ:

    1. 決めと焼きが違えば言う（**止めない** —— どちらを捨てるかは読んだ回が決める）
    2. 同じなら1行も出さない（毎周 鳴る行を増やさない）
    3. **古い鼓動を「いま焼いている」と読まない**（落ちた焼きの残りが在る）
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

next_slot = pytest.importorskip("src.next_slot")
ahead_sweep = pytest.importorskip("ahead_sweep")

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 4, 21, 30, tzinfo=timezone.utc)     # 09/05 06:30 JST


def _beat(vid: str, at: datetime) -> dict:
    return {"at": at.isoformat(), "kind": "beat", "video_id": vid, "topic": "t"}


def _patch(monkeypatch, decided: str, rows: list[dict]) -> None:
    from src import daily_pick
    monkeypatch.setattr(daily_pick, "current",
                        lambda day=None: {"video_id": decided} if decided else None)
    monkeypatch.setattr(ahead_sweep, "_rebake_rows", lambda root=None: rows)


def test_決めと焼きが違えば言う(monkeypatch):
    _patch(monkeypatch, "SHORT_A", [_beat("LONG_B", NOW - timedelta(minutes=12))])
    out = "\n".join(next_slot.superseded_bake_lines(NOW))
    assert "LONG_B" in out and "SHORT_A" in out, out
    # **止めないこと** —— 決めるのは読んだ回
    assert "この回が決めること" in out, out


def test_同じなら黙る(monkeypatch):
    _patch(monkeypatch, "SHORT_A", [_beat("SHORT_A", NOW - timedelta(minutes=12))])
    assert next_slot.superseded_bake_lines(NOW) == []


def test_古い鼓動はいま焼いているではない(monkeypatch):
    """**落ちた焼きの残りが在ります。** 12時間より古い鼓動で鳴らさないこと。"""
    _patch(monkeypatch, "SHORT_A", [_beat("LONG_B", NOW - timedelta(hours=30))])
    assert next_slot.superseded_bake_lines(NOW) == []


def test_決めが無ければ黙る(monkeypatch):
    _patch(monkeypatch, "", [_beat("LONG_B", NOW - timedelta(minutes=12))])
    assert next_slot.superseded_bake_lines(NOW) == []


def test_焼いていなければ黙る(monkeypatch):
    _patch(monkeypatch, "SHORT_A", [])
    assert next_slot.superseded_bake_lines(NOW) == []


def test_skip_の行は焼いていない(monkeypatch):
    """`skip` は「焼きません」の記録で、焼いている証拠ではありません。"""
    rows = [{"at": (NOW - timedelta(minutes=5)).isoformat(),
             "kind": "skip", "video_id": "LONG_B"}]
    _patch(monkeypatch, "SHORT_A", rows)
    assert next_slot.superseded_bake_lines(NOW) == []


def test_鼓動のあとに_done_が在れば_もう焼いた(monkeypatch):
    """2026-09-05 15:1x に実測: `GFvAcxvDmYM` は 06:18 の `beat` のあと 07:58 に `done` を
    残していたのに、15:0x の画面がまだ「いま焼いているのは `GFvAcxvDmYM`」と刷っていた。"""
    rows = [_beat("LONG_B", NOW - timedelta(hours=8)),
            {"at": (NOW - timedelta(hours=6)).isoformat(), "kind": "done",
             "video_id": "LONG_B", "new_id": "LONG_C", "rc": 0}]
    _patch(monkeypatch, "SHORT_A", rows)
    assert next_slot.superseded_bake_lines(NOW) == []


def test_錠が空いていれば焼いていない(monkeypatch):
    """`flock` が直接の証拠（`rebake_busy()` の註）。鼓動だけで鳴らさない。"""
    _patch(monkeypatch, "SHORT_A", [_beat("LONG_B", NOW - timedelta(minutes=12))])
    assert next_slot.superseded_bake_lines(NOW, busy_call=lambda: False) == []
    assert "LONG_B" in "\n".join(next_slot.superseded_bake_lines(NOW, busy_call=lambda: True))
