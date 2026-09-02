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


# ---------------------------------------------------------------- videos.insert の道（2026-09-03）
def test_日枠が尽きていても_台本の控えが在れば_insert_で置く():
    """**帳面が焼けた翌朝でも、きょうの1本が空かないこと。** 実測 09/03 00:03 JST:
    `--move` は帳面の取り置き（12,368／10,000）で止まり、既定の枠 09:00 は窓の戻る
    16:00 JST の 7時間 前だった。`videos.insert` は日枠を使わない。"""
    p = sweep.today_plan(_jst(0, 30), count=0, cap=1, candidate=CAND, hour=9,
                         quota_open=False, insert_ok=True)
    assert p["do"] is True and p["via"] == "insert"
    assert p["when"] == "2026-09-03T09:00"


def test_日枠が開いていれば_既定は_update():
    p = sweep.today_plan(_jst(0, 30), count=0, cap=1, candidate=CAND, hour=9,
                         quota_open=True, insert_ok=True)
    assert p["do"] is True and p["via"] == "update"


def test_日枠が尽きていて_控えも無ければ_置かない():
    p = sweep.today_plan(_jst(0, 30), count=0, cap=1, candidate=CAND, hour=9,
                         quota_open=False, insert_ok=False)
    assert p["do"] is False and "日枠" in p["why"]


def test_insert_の道は_控えが無ければ_何も撃たない(tmp_path):
    assert sweep.stash_script("no-such-video", root=tmp_path) is None
    rc, new_id = sweep.place_by_insert(
        {"video_id": "no-such-video-zzz", "when": "2026-09-03T09:00"}, _jst(0, 30))
    assert rc == 2 and new_id is None


def test_置く時刻は掃く側が先で_根拠が無ければ既定():
    """**置く側が `config_hour()` しか読まず、掃き（`sweep_hour`）が助言止まりだった**
    （2026-09-03 00:4x に踏んだ。`sweep_hour(09/04)`=17時・機械は 9時）。"""
    import datetime as _dt
    day = _dt.date(2026, 9, 4)
    assert sweep.place_hour(day, sweep=lambda d: 17, config=lambda: 9) == 17
    assert sweep.place_hour(day, sweep=lambda d: None, config=lambda: 11) == 11
    assert sweep.place_hour(day, sweep=lambda d: None, config=lambda: None) == 9


def test_place_today_は_place_hour_を読む():
    import inspect
    src = inspect.getsource(sweep.place_today)
    assert "place_hour(" in src, "置く側が掃く時刻を読んでいません（`place_hour`）"
    assert "config_hour()" not in src, "置く側が既定だけを読んでいます（掃きが助言止まりに戻る）"


# ---------------------------------------------------------------- きょうの1本のサムネイル（2026-09-03 03:xx）
def _plan_placed(vid: str) -> dict:
    return {"do": True, "rc": 0, "video_id": vid, "when": "2026-09-04T17:00", "via": "update"}


def test_置いた本のサムネイルが載っていなければ_その1本だけ押す():
    """**試験の本（外の作りを写した長尺）が、サムネイル無しで出ない**こと。
    実測 09/03 02:3x: `6PKux5HNnUE` は `thumbnail_set: False` のまま 09/04 の1本で、
    押す口は3つとも その日に起きない（掃きは「先の日付 0本」で走らない・日誌は書き置き・
    `uploader` は上げた瞬間だけ）。"""
    pushed: list[str] = []
    line = sweep.thumb_today(_jst(16, 30, 4), plan=_plan_placed("VID-LONG"),
                             missing=["VID-LONG", "OTHER"], quota_open=True,
                             push=lambda v: pushed.append(v) or 0)
    assert pushed == ["VID-LONG"]
    assert "載せました" in line


def test_載っている本は押さない():
    pushed: list[str] = []
    sweep.thumb_today(_jst(16, 30, 4), plan=_plan_placed("VID-LONG"),
                      missing=["OTHER"], quota_open=True,
                      push=lambda v: pushed.append(v) or 0)
    assert pushed == []


def test_日枠が尽きていれば押さず_理由を返す():
    pushed: list[str] = []
    line = sweep.thumb_today(_jst(9, 0, 4), plan=_plan_placed("VID-LONG"),
                             missing=["VID-LONG"], quota_open=False,
                             push=lambda v: pushed.append(v) or 0)
    assert pushed == [] and "日枠" in line


def test_dry_run_は押さない():
    pushed: list[str] = []
    sweep.thumb_today(_jst(16, 30, 4), plan=_plan_placed("VID-LONG"), dry_run=True,
                      missing=["VID-LONG"], quota_open=True,
                      push=lambda v: pushed.append(v) or 0)
    assert pushed == []


def test_置いていない回は_控えの次の1本がきょうなら_それを押す(monkeypatch):
    """**置く手が「きょうの枠は埋まっている」で黙った回**（`insert` で朝に置いた本・
    実測 09/03 `9zkfjEH48PY`）でも、16:00 の窓が戻った回に押せること。"""
    from src import next_slot
    monkeypatch.setattr(next_slot, "next_video",
                        lambda now=None, path=None: {"video_id": "VID-TODAY",
                                                     "at": "2026-09-04T08:00:00Z"})
    assert sweep.today_video_id(_jst(16, 30, 4), {"do": False}) == "VID-TODAY"
    # 明日の本は押さない（規則5 の下では在りませんが、在っても pool_drain の仕事）
    monkeypatch.setattr(next_slot, "next_video",
                        lambda now=None, path=None: {"video_id": "VID-TOMORROW",
                                                     "at": "2026-09-05T08:00:00Z"})
    assert sweep.today_video_id(_jst(16, 30, 4), {"do": False}) == ""


def test_置いた本が先で_insert_で置き直した新IDを採る():
    plan = {"do": True, "rc": 0, "video_id": "OLD", "placed_id": "NEW", "via": "insert"}
    assert sweep.today_video_id(_jst(16, 30, 4), plan) == "NEW"


def test_main_は置いた直後にサムネイルを押す(monkeypatch):
    order: list[str] = []
    monkeypatch.setattr(sweep, "place_today",
                        lambda now=None, dry_run=False: order.append("today") or {"do": False})
    monkeypatch.setattr(sweep, "thumb_today",
                        lambda now=None, plan=None, dry_run=False: order.append("thumb") or "")
    monkeypatch.setattr(sweep, "reasons_to_skip",
                        lambda now=None: order.append("sweep") or "先の日付は 0本 です")
    assert sweep.main(["--dry-run"]) == 0
    assert order == ["today", "thumb", "sweep"]
