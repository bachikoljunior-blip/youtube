"""**`untreated_slot()` は、焼いている最中の直しを「無い」と読まないこと。**

`run_marker.untreated_slot()` は控え（`data/critique_queue/<ID>.script.json`
＝ **いま実物に入っている台本**）で脚を数え、✗ が在れば `fix` を止めます。
控えは**焼きの 55〜90分 ぶん古い**ので、直した台本が焼かれている最中でも
「その脚を通すことに使え」と言い続けます。**回は 30〜60分**なので、
焼いている間ずっと、全部の回の `fix` が止まります（2026-09-04 17:1x に実物で踏んだ）。

逃がすのは **手元の台本が4脚とも ○ かつ その本の焼きが実際に走っている** ときだけ。
片方だけでは止めたままにすること —— **直しただけで一度も本に入らない台本を
素通りさせない**ため。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import run_marker as rm  # noqa: E402
from src import daily_pick as dp  # noqa: E402


@pytest.fixture
def slot(monkeypatch):
    """決めも題材の表も固定した、脚だけが動く台。"""
    monkeypatch.setattr(dp, "current", lambda *a, **k: {"video_id": "VID", "topic": "TOPIC"})
    monkeypatch.setattr(dp, "for_day", lambda *a, **k: None)
    monkeypatch.setattr(dp, "_topics", lambda *a, **k: [{"id": "TOPIC", "style": "outside_long"}])
    return rm


def _set(monkeypatch, *, stash, draft, baking):
    monkeypatch.setattr(dp, "pick_legs", lambda vid, **k: (stash, None))
    monkeypatch.setattr(dp, "draft_legs", lambda topic, **k: (draft, None))
    monkeypatch.setattr(rm, "_slot_baking", lambda vid: baking)


def test_控えが通っていれば黙る(slot, monkeypatch):
    _set(monkeypatch, stash=[], draft=[], baking=(False, "-"))
    assert slot.untreated_slot()["fired"] is False


def test_控えも手元も落ちていれば止める(slot, monkeypatch):
    _set(monkeypatch, stash=["(1) 冒頭"], draft=["(1) 冒頭"], baking=(True, "焼いている"))
    g = slot.untreated_slot()
    assert g["fired"] is True, "手元の台本が直っていないなら、焼いていても止めること"
    assert g["bad"] == ["(1) 冒頭"]


def test_手元が全脚まると焼いている最中なら通す(slot, monkeypatch):
    _set(monkeypatch, stash=["(1) 冒頭"], draft=[],
         baking=(True, "`VID` を 16:44:22 から（sha abc）"))
    g = slot.untreated_slot()
    assert g["fired"] is False, "直した台本が焼かれている最中まで止めると、回は何も出せません"
    assert "いま焼いています" in g["why"]
    assert "16:44:22" in g["why"], "いつから焼いているかを言うこと"


def test_手元が全脚まるでも焼いていなければ止める(slot, monkeypatch):
    """**ここを緩めると、直しただけで一度も本に入らない台本が素通りします。**"""
    _set(monkeypatch, stash=["(1) 冒頭"], draft=[],
         baking=(False, "錠（`rebake.lock`）が空 ＝ 誰も焼いていません"))
    g = slot.untreated_slot()
    assert g["fired"] is True
    assert "焼きが走っていません" in g["why"]
    assert "ahead_sweep" in g["why"], "起こす手を書くこと"


def test_手元の台本が読めない回は逃がさない(slot, monkeypatch):
    """**「測れない」を「通った」と読ませないこと**（`pick_legs` と同じ向き）。"""
    monkeypatch.setattr(dp, "pick_legs", lambda vid, **k: (["(1) 冒頭"], None))
    monkeypatch.setattr(dp, "draft_legs", lambda topic, **k: ([], "手元の台本が読めません"))
    monkeypatch.setattr(rm, "_slot_baking", lambda vid: (True, "焼いている"))
    g = slot.untreated_slot()
    assert g["fired"] is True, "読めない台本を『4脚とも ○』と読んではいけません"


# ---------------------------------------------------------------- `_slot_baking`

def _rows(monkeypatch, rows, busy=True):
    sys.path.insert(0, str(ROOT / "scripts"))
    import ahead_sweep as _as
    monkeypatch.setattr(_as, "rebake_busy", lambda: busy)
    monkeypatch.setattr(_as, "_rebake_rows", lambda *a, **k: rows)


def test_錠が空なら走っていない(monkeypatch):
    _rows(monkeypatch, [{"kind": "start", "video_id": "VID", "sha": "s1"}], busy=False)
    ok, why = rm._slot_baking("VID")
    assert ok is False and "錠" in why


def test_別の本を焼いていたら走っていない(monkeypatch):
    _rows(monkeypatch, [{"kind": "start", "video_id": "OTHER", "sha": "s1"}])
    ok, why = rm._slot_baking("VID")
    assert ok is False and "別の本" in why


def test_最後のstartにdoneが付いていたら終わっている(monkeypatch):
    _rows(monkeypatch, [
        {"kind": "start", "video_id": "VID", "sha": "s1"},
        {"kind": "done", "video_id": "VID", "sha": "s1", "rc": 0},
    ])
    ok, why = rm._slot_baking("VID")
    assert ok is False and "終わって" in why


def test_その本のstartが開いていれば走っている(monkeypatch):
    _rows(monkeypatch, [
        {"kind": "done", "video_id": "VID", "sha": "s0", "rc": 0},
        {"kind": "start", "video_id": "VID", "sha": "s1", "at": "2026-09-04T16:44:22+09:00"},
    ])
    ok, why = rm._slot_baking("VID")
    assert ok is True and "16:44:22" in why


def test_logの末尾は見ない():
    """**正本は錠と `data/rebake.jsonl`**（`docs/trigger_main.md`）——
    焼く側が死んでも log は残るので、末尾で生死を判じると死んだ焼きが生きて見えます。"""
    import inspect
    src = inspect.getsource(rm._slot_baking)
    assert "REBAKE_LOG" not in src, "log の定数を引いている ＝ 末尾を読んでいます"
    for reader in ("open(", "read_text", "readlines", "tail"):
        assert reader not in src, f"`{reader}` で何かを読んでいます（正本は錠と帳面だけ）"
    assert "rebake_busy" in src and "_rebake_rows" in src
