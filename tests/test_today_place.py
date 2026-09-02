"""**回が何もしなくても、きょうの1本が その日の枠へ置かれること。**（`scripts/ahead_sweep.place_today`）

## なぜ要るか（2026-09-02 夜・最適化の回）

規則5（固定その4）の下で、外す側は3つ 揃っています（関門・門・掃き）。
**置く側は「その回が選べば撃つ」のまま**でした —— 実測 09/01 以降の ship 130件 のうち
`upload` は 1件。09/01・09/02 の「1日1本」は規則の前に積んだ作り置きが出ただけで、
作り置きが 0本 になった 09/03 からは、置く手が回の裁量のままなら**空く日が出ます**。

この検査が見るのは**決める側（純関数）**です —— 撃つ側は `reschedule.py` の検査が持っています。

## 覆る条件

- `house_rule.same_day_only()` が `False` になったら、この手はまるごと黙ります
- 置く時刻の既定は `config/channel.yaml`（ここに数は書きません）
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
    "ahead_gate_for_today", ROOT / "scripts" / "ahead_gate.py")
ahead_gate = importlib.util.module_from_spec(_gspec)
sys.modules.setdefault("ahead_gate", ahead_gate)
_gspec.loader.exec_module(ahead_gate)

_sspec = importlib.util.spec_from_file_location(
    "ahead_sweep_today", ROOT / "scripts" / "ahead_sweep.py")
sweep = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(sweep)

JST = timezone(timedelta(hours=9))


def _jst(h: int, m: int = 0, d: int = 3) -> datetime:
    return datetime(2026, 9, d, h, m, tzinfo=JST).astimezone(timezone.utc)


CAND = {"video_id": "DtpnSVFDtAE", "why": "族 shokibo 1,036回(n=4)"}


# ---------------------------------------------------------------- 時刻
def test_既定の時刻がまだ先なら_その時刻():
    slot = sweep.today_slot(_jst(0, 30), 9)
    assert slot.strftime("%Y-%m-%dT%H:%M") == "2026-09-03T09:00"


def test_既定の時刻を過ぎていれば_次の正時():
    """10:30 → 11:00（20分 より先の正時）。10:50 → 12:00（11:00 は 20分 以内）。"""
    assert sweep.today_slot(_jst(10, 30), 9).hour == 11
    assert sweep.today_slot(_jst(10, 50), 9).hour == 12


def test_きょうの中に正時が残っていなければ_None():
    assert sweep.today_slot(_jst(23, 5), 9) is None
    assert sweep.today_slot(_jst(22, 50), 9) is None      # 次の正時は 00:00（明日）


# ---------------------------------------------------------------- 置く／置かない
def test_空いていて候補が在れば_置く():
    p = sweep.today_plan(_jst(0, 30), count=0, cap=1, candidate=CAND, hour=9, quota_open=True)
    assert p["do"] is True
    assert p["video_id"] == "DtpnSVFDtAE"
    assert p["when"] == "2026-09-03T09:00"


def test_きょうが埋まっていれば_置かない():
    """**規則1（1日1本）を、この手が破らないこと。**"""
    p = sweep.today_plan(_jst(14, 0), count=1, cap=1, candidate=CAND, hour=9, quota_open=True)
    assert p["do"] is False and "埋まって" in p["why"]


def test_日枠が尽きていれば_置かない():
    p = sweep.today_plan(_jst(0, 30), count=0, cap=1, candidate=CAND, hour=9, quota_open=False)
    assert p["do"] is False and "日枠" in p["why"]


def test_候補が無ければ_置かない():
    p = sweep.today_plan(_jst(0, 30), count=0, cap=1, candidate=None, hour=9, quota_open=True)
    assert p["do"] is False and "候補" in p["why"] or "置ける本" in p["why"]


def test_規則5が外れていれば_置かない():
    p = sweep.today_plan(_jst(0, 30), count=0, cap=1, candidate=CAND, hour=9,
                         quota_open=True, rule_on=False)
    assert p["do"] is False and "規則5" in p["why"]


def test_一時停止なら_置かない():
    p = sweep.today_plan(_jst(0, 30), count=0, cap=1, candidate=CAND, hour=9,
                         quota_open=True, paused="/repo/.owner-pause")
    assert p["do"] is False and "一時停止" in p["why"]


def test_置く先は_必ずきょう():
    """**明日には置かない**（規則5）。`today_slot` が `None` を返す時間帯は置かない。"""
    p = sweep.today_plan(_jst(23, 30), count=0, cap=1, candidate=CAND, hour=9, quota_open=True)
    assert p["do"] is False
    for h in range(0, 23):
        q = sweep.today_plan(_jst(h, 0), count=0, cap=1, candidate=CAND, hour=9, quota_open=True)
        if q["do"]:
            assert q["when"].startswith("2026-09-03T")


# ---------------------------------------------------------------- 配線
def test_main_は置く手を先に呼ぶ(monkeypatch):
    """**掃きより先に置くこと**（掃きは日枠を食う。51単位 を先に取る）。"""
    order: list[str] = []
    monkeypatch.setattr(sweep, "place_today",
                        lambda now=None, dry_run=False: order.append("today") or {"do": False})
    monkeypatch.setattr(sweep, "reasons_to_skip",
                        lambda now=None: order.append("sweep") or "先の日付は 0本 です")
    assert sweep.main(["--dry-run"]) == 0
    assert order == ["today", "sweep"]


def test_kick_は同じ印の内では二度起こさない(tmp_path, monkeypatch):
    """**同じ周の2体が同時に起こさないこと。** 印が `KICK_EVERY` の内なら起こさない。"""
    calls: list[list[str]] = []
    monkeypatch.setattr(sweep.subprocess, "Popen",
                        lambda argv, **kw: calls.append(argv) or None)
    now = _jst(0, 30)
    assert "起こしました" in sweep.kick(now, root=tmp_path)
    assert "前に起こしてあります" in sweep.kick(now + timedelta(minutes=5), root=tmp_path)
    assert "起こしました" in sweep.kick(now + sweep.KICK_EVERY + timedelta(minutes=1),
                                  root=tmp_path)
    assert len(calls) == 2 and calls[0][-1].endswith("ahead_sweep.py")


def test_kick_は台本生成の子プロセスでは黙る(tmp_path, monkeypatch):
    monkeypatch.setenv("YOUTUBE_PIPELINE_CHILD", "1")
    assert "起こしません" in sweep.kick(_jst(0, 30), root=tmp_path)


def test_毎周_必ず撃たれる2つの口から起こされる():
    """**フックではなく、実際に撃たれる口に配線してあること**（`kick()` の註）。

    `run_marker.py --write`（サブの §1）と `next_round.py`（親の毎周）の2つ。
    """
    for name in ("run_marker.py", "next_round.py"):
        src = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        assert "ahead_sweep" in src and ".kick()" in src, name


def test_SessionStart_から起きるフックは_この道具を呼ぶ():
    sh = (ROOT / "scripts" / "ahead_sweep.sh").read_text(encoding="utf-8")
    assert "ahead_sweep.py" in sh
    hooks = (ROOT / ".claude" / "settings.json").read_text(encoding="utf-8")
    assert "ahead_sweep.sh" in hooks
