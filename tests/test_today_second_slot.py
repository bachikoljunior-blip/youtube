"""**決めの本が もう きょうの枠に在る回は、同じ本を二度 置かない。2本目は開いている前提の処置。**
（`scripts/ahead_sweep._today_candidate` / `_probe_candidate` / `placed_today`）

## なぜ要るか（2026-09-05 09:0x に実測して足した）

`PUBLISH_PER_DAY` が 1 → 10 になった日から `place_today()` は毎周 候補を読みます。
候補は決めの本を**予約の有無を見ずに**返していたので、09/05 は 10:00 に予約ずみの
`a23e696j0f8` を毎周 返し、日枠が閉じた窓では同じ台本の分かりやすさの輪（40分）を
回して `videos.insert` へ向かいました（`--replaces` が断るので載らない ＝ 器と LLM だけ消える）。
一方、前提「外の作り方を写した長尺」の処置 `fMlY_uzHOMw`（5脚 全通・予約なし）には
置く手がひとつも無かった。

## 覆る条件

- `house_rule.cap()` が 1 に戻ったら、2本目の枝は黙る（`test_床が効いている日は2本目を出さない`）
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
    "ahead_gate_for_second", ROOT / "scripts" / "ahead_gate.py")
ahead_gate = importlib.util.module_from_spec(_gspec)
sys.modules.setdefault("ahead_gate", ahead_gate)
_gspec.loader.exec_module(ahead_gate)

_sspec = importlib.util.spec_from_file_location(
    "ahead_sweep_second", ROOT / "scripts" / "ahead_sweep.py")
sweep = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(sweep)

from src import daily_pick, house_rule, next_slot  # noqa: E402

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 5, 9, 5, tzinfo=JST).astimezone(timezone.utc)
PICK = {"video_id": "a23e696j0f8", "form": "ショート", "topic": "s-shokibo", "why": "n"}


def _rows(with_probe: bool = True, probe_at=None) -> dict[str, dict]:
    rows = {
        "kzefG44_APU": {"video_id": "kzefG44_APU", "topic": "s-shokibo",
                        "at": "2026-09-05T00:00:00Z", "uploaded_at": "2026-09-04T22:17:30+00:00"},
        "a23e696j0f8": {"video_id": "a23e696j0f8", "topic": "s-shokibo",
                        "at": "2026-09-05T01:00:00Z", "uploaded_at": "2026-09-04T22:40:04+00:00"},
        "GFvAcxvDmYM": {"video_id": "GFvAcxvDmYM", "topic": "nenkin-long",
                        "at": None, "uploaded_at": "2026-09-04T12:31:10+00:00"},
    }
    if with_probe:
        rows["fMlY_uzHOMw"] = {"video_id": "fMlY_uzHOMw", "topic": "nenkin-long",
                               "at": probe_at, "uploaded_at": "2026-09-04T22:57:00+00:00"}
    return rows


def _wire(monkeypatch, *, cap=10, rows=None, legs=None, pick=PICK):
    rows = _rows() if rows is None else rows
    monkeypatch.setattr(next_slot, "latest_rows", lambda path=None: rows)
    monkeypatch.setattr(daily_pick, "current", lambda day, path=None: pick)
    monkeypatch.setattr(daily_pick, "standing_form_stale", lambda day, cur=None, now=None: "")
    monkeypatch.setattr(daily_pick, "_topics",
                        lambda: [{"id": "nenkin-long", "style": "outside_long"},
                                 {"id": "s-shokibo"}])
    monkeypatch.setattr(daily_pick, "_observed_ids", lambda views_path=None: set())
    legs = legs or {}
    monkeypatch.setattr(daily_pick, "pick_legs",
                        lambda vid, queue=None: legs.get(vid, ([], None)))
    monkeypatch.setattr(house_rule, "cap", lambda: cap)


def test_きょうの枠に在る本を数える(monkeypatch):
    _wire(monkeypatch)
    assert sweep.placed_today(NOW) == {"kzefG44_APU", "a23e696j0f8"}


def test_決めの本が枠に無ければ_それを返す(monkeypatch):
    rows = _rows()
    rows["a23e696j0f8"]["at"] = None
    _wire(monkeypatch, rows=rows)
    c = sweep._today_candidate(NOW)
    assert c["video_id"] == "a23e696j0f8" and c["source"] == "pick"


def test_決めの本が枠に在れば_二度返さない_2本目は前提の処置(monkeypatch):
    _wire(monkeypatch, legs={"GFvAcxvDmYM": (["(4) 題・サムネ"], None)})
    c = sweep._today_candidate(NOW)
    assert c["video_id"] == "fMlY_uzHOMw"        # 脚 全通・予約なし・いちばん新しい
    assert c["source"] == "probe" and c["update_only"] is True


def _wire_pool(monkeypatch, pool):
    """池を差し替える（3本目からの枝。2026-09-05 11:xx に足した）。`record` は呼ばれないこと。"""
    calls = []
    monkeypatch.setattr(daily_pick, "compare", lambda now: {"all": {"ショート": {"median": 164, "n": 216}},
                                                            "rows": []})
    monkeypatch.setattr(daily_pick, "fallback_form", lambda cmp: "ショート")
    monkeypatch.setattr(daily_pick, "pool_candidates", lambda form, rows=None: list(pool))
    monkeypatch.setattr(daily_pick, "outside_first", lambda pool, topics=None: list(pool))
    monkeypatch.setattr(daily_pick, "claimed_elsewhere", lambda day: {"CLAIMED"})
    monkeypatch.setattr(daily_pick, "record", lambda *a, **k: calls.append((a, k)))
    return calls


POOL = [{"video_id": "CLAIMED", "topic": "s-x", "family": "x", "fam_res": 400, "fam_median": 400, "fam_n": 3},
        {"video_id": "a23e696j0f8", "topic": "s-shokibo", "family": "shokibo", "fam_res": 345, "fam_median": 1035, "fam_n": 4},
        {"video_id": "POOL1", "topic": "s-ikuji", "family": "ikuji", "fam_res": 108, "fam_median": 621, "fam_n": 4}]


def test_札だけの本は処置ではない_3本目は池から(monkeypatch):
    """処置が無ければ `None` で止まっていた（規則 10本/日 で候補は最大 2本）。3本目からは池。
    他日の決めが名指す本（CLAIMED）と、きょう置いた本（a23e696j0f8）は外す。決めは書き換えない。"""
    _wire(monkeypatch, rows=_rows(with_probe=False),
          legs={"GFvAcxvDmYM": (["(2) 章・締め"], None)})
    calls = _wire_pool(monkeypatch, POOL)
    c = sweep._today_candidate(NOW)
    assert c["video_id"] == "POOL1" and c["source"] == "pool"
    assert "3本目" in c["why"] and calls == []


def test_処置がもう予約ずみなら池へ(monkeypatch):
    _wire(monkeypatch, rows=_rows(probe_at="2026-09-05T08:00:00Z"),
          legs={"GFvAcxvDmYM": (["(4) 題・サムネ"], None)})
    _wire_pool(monkeypatch, POOL)
    c = sweep._today_candidate(NOW)
    assert c["video_id"] == "POOL1" and c["source"] == "pool"


def test_池も空なら_None(monkeypatch):
    _wire(monkeypatch, rows=_rows(with_probe=False),
          legs={"GFvAcxvDmYM": (["(2) 章・締め"], None)})
    _wire_pool(monkeypatch, [])
    monkeypatch.setattr(next_slot, "next_video", lambda now: None)
    monkeypatch.setattr(next_slot, "drafts", lambda now: [])
    assert sweep._today_candidate(NOW) is None


def test_置いた正時は飛ばす():
    """`today_slot(occupied=)`: 09:00・10:00 に本が在れば、9時 を頼まれても 11:00。"""
    assert sweep.today_slot(NOW, 9, occupied={9, 10}).hour == 11
    assert sweep.today_slot(NOW, 9, occupied=set()).hour == 10       # 09:05 + 20分 → 10:00
    assert sweep.today_slot(NOW, 9, occupied=set(range(10, 24))) is None


def test_きょうの正時を数える(monkeypatch):
    _wire(monkeypatch)
    assert sweep.today_hours(NOW) == {9, 10}


def test_床が効いている日は2本目を出さない(monkeypatch):
    _wire(monkeypatch, cap=1)
    assert sweep._today_candidate(NOW) is None


def test_処置は焼き直しの道へ倒れない():
    """`update_only` の候補は、日枠が閉じていても `videos.insert` に行かない（`today_plan` が待つ）。"""
    cand = {"video_id": "fMlY_uzHOMw", "update_only": True, "why": "probe"}
    p = sweep.today_plan(NOW, count=2, cap=10, candidate=cand, hour=9,
                         quota_open=False, insert_ok=False)
    assert p["do"] is False and "日枠" in p["why"]
    p = sweep.today_plan(NOW, count=2, cap=10, candidate=cand, hour=9,
                         quota_open=True, insert_ok=False)
    assert p["do"] is True and p["via"] == "update" and p["video_id"] == "fMlY_uzHOMw"


def test_錠は作業コピーをまたぐ(monkeypatch, tmp_path):
    from src import history
    monkeypatch.setattr(history, "_git_common_dir", lambda: tmp_path / ".git")
    assert sweep._lock_path().parent == tmp_path / ".git"
    assert (sweep._machine_dir() / sweep.TODAY_LOCK).parent == tmp_path / ".git"
