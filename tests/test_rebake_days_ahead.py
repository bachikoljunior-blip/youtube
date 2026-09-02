"""**先の日の決めた本も、台本が良くなっていれば焼き直されること。** そして**焼く側が途中で死んだ印は、
二度と焼かない印にならないこと。**（`scripts/ahead_sweep.rebake_attempted` / `rebake_today` の日の並び）

## なぜ要るか（2026-09-03 05:xx・最適化の回）

`rebake_today` は `daily_pick.for_day()` の1日しか見ていなかった。09/05 の本 `dRZnZrRy2Lw` は 09/03 の時点で
冒頭が旧の型のまま決まっていて、規則3（出る瞬間まで良くし続ける）が手前の1日ぶんにしか効かなかった。
また、焼く印（`<ID>-<sha>`）は起こした瞬間に置かれ、焼く側が容器の回収で死ぬと、その sha は永久に「一度 焼いた」に
なっていた（サブは親の容器の中で走る —— `docs/spawn_prompt.md`「親が畳まれるとコンテナが回収され…」）。

## 覆る条件

- `REBAKE_DAYS_AHEAD` / `REBAKE_MARK_STALE` は `scripts/ahead_sweep.py` の定数（ここに数は写さない）
- 規則2（作り置きしない）が「決めも1日ぶんだけ」と読まれるようになったら、先の日を見る側は要らない
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

_gspec = importlib.util.spec_from_file_location(
    "ahead_gate_for_rebake_days", ROOT / "scripts" / "ahead_gate.py")
ahead_gate = importlib.util.module_from_spec(_gspec)
sys.modules.setdefault("ahead_gate", ahead_gate)
_gspec.loader.exec_module(ahead_gate)

_sspec = importlib.util.spec_from_file_location(
    "ahead_sweep_rebake_days", ROOT / "scripts" / "ahead_sweep.py")
sweep = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(sweep)

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 3, 6, 0, tzinfo=JST).astimezone(timezone.utc)


def _marks(tmp_path, monkeypatch):
    d = tmp_path / "rebake"
    d.mkdir()
    monkeypatch.setattr(sweep, "_rebake_marks_dir", lambda: d)
    return d


# ---------------------------------------------------------------- 印の読み方
def test_印が無ければ焼いていない(tmp_path, monkeypatch):
    _marks(tmp_path, monkeypatch)
    monkeypatch.setattr(sweep, "_rebake_rows", lambda root=None: [])
    assert sweep.rebake_attempted("VID", "abc", now=NOW) is False


def test_印が若ければ_いま焼いている(tmp_path, monkeypatch):
    d = _marks(tmp_path, monkeypatch)
    (d / "VID-abc").write_text((NOW - timedelta(minutes=30)).isoformat() + "\n", encoding="utf-8")
    monkeypatch.setattr(sweep, "_rebake_rows", lambda root=None: [])
    assert sweep.rebake_attempted("VID", "abc", now=NOW) is True


def test_帳面に_done_が在れば_一度焼いた(tmp_path, monkeypatch):
    d = _marks(tmp_path, monkeypatch)
    (d / "VID-abc").write_text((NOW - timedelta(days=2)).isoformat() + "\n", encoding="utf-8")
    monkeypatch.setattr(sweep, "_rebake_rows",
                        lambda root=None: [{"kind": "done", "video_id": "VID", "sha": "abc", "rc": 1}])
    assert sweep.rebake_attempted("VID", "abc", now=NOW) is True


def test_印だけ古く_done_が無ければ_焼く側が死んだと読んで_もう一度焼く(tmp_path, monkeypatch):
    d = _marks(tmp_path, monkeypatch)
    (d / "VID-abc").write_text((NOW - sweep.REBAKE_MARK_STALE - timedelta(minutes=1)).isoformat() + "\n",
                               encoding="utf-8")
    monkeypatch.setattr(sweep, "_rebake_rows",
                        lambda root=None: [{"kind": "start", "video_id": "VID", "sha": "abc"}])
    assert sweep.rebake_attempted("VID", "abc", now=NOW) is False


# ---------------------------------------------------------------- 日の並び
def _plan_for_days(monkeypatch, plans: dict):
    """`rebake_plan_for` を日 → 計画 に差し替える。"""
    from src import daily_pick
    monkeypatch.setattr(daily_pick, "for_day", lambda now=None: datetime(2026, 9, 4, tzinfo=JST).date())

    def fake(day, now, *, root=None):
        base = {"do": False, "why": "決めが無い", "video_id": "", "topic": "", "sha": "",
                "for_day": day.isoformat(), "decided": False}
        base.update(plans.get(day.isoformat(), {}))
        return base
    monkeypatch.setattr(sweep, "rebake_plan_for", fake)


def test_きょうの本が同じ中身でも_先の日の本が違えば_そちらを焼く(monkeypatch, capsys):
    _plan_for_days(monkeypatch, {
        "2026-09-04": {"decided": True, "why": "控えと台本は同じ中身"},
        "2026-09-05": {"decided": True, "do": True, "video_id": "NEXT0000001", "topic": "t2", "sha": "s2",
                       "why": "台本のほうが新しい"},
    })
    r = sweep.rebake_today(NOW, dry_run=True)
    assert r["do"] is True and r["video_id"] == "NEXT0000001" and r["for_day"] == "2026-09-05"
    assert r["started"] is False
    out = capsys.readouterr().out
    assert "2026-09-04 は焼き直しません" in out and "2026-09-05 の本" in out


def test_先の日に決めが無ければ_読み飛ばす(monkeypatch, capsys):
    _plan_for_days(monkeypatch, {"2026-09-04": {"decided": True, "why": "控えと台本は同じ中身"}})
    r = sweep.rebake_today(NOW, dry_run=True)
    assert r["do"] is False and r["for_day"] == "2026-09-04"
    out = capsys.readouterr().out
    assert "2026-09-05" not in out and "2026-09-06" not in out


def test_一周に起こすのは一本(monkeypatch):
    _plan_for_days(monkeypatch, {
        "2026-09-04": {"decided": True, "do": True, "video_id": "A0000000001", "topic": "ta", "sha": "sa"},
        "2026-09-05": {"decided": True, "do": True, "video_id": "B0000000001", "topic": "tb", "sha": "sb"},
    })
    r = sweep.rebake_today(NOW, dry_run=True)
    assert r["video_id"] == "A0000000001"      # 手前の日が先
