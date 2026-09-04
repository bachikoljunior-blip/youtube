"""`scripts/run_marker._slot_baking()` の検査。**外へは1回も出ません・時計を読みません。**

## なぜ在るか（2026-09-05 06:3x に実物で踏んだ）

`_slot_baking()` は生死を**錠（`flock`）だけ**で読んでいました。ところが錠を握るのは
`ahead_sweep.rebake_run()` だけで、**`run_marker.py --write` がその場で印字している
焼き直しの1行**（`python -m src.pipeline --topic …`）は錠を1度も取りません。

実測 2026-09-05 06:3x（**同じ画面の中の食い違い**）::

    ps                 `python -m src.pipeline --topic nenkin-…-handan` が **2時間** 走っている
    data/rebake.jsonl  04:12 `start` `GFvAcxvDmYM` ＋ `beat` 04:39 / 04:45 / 05:14 / 05:46
    rebake_busy()      **False**
    → `untreated_slot()` は「焼きが走っていません。起こすこと」と言い、
      **全部の回の `fix` を止め続けていた**

そして門が指す手（`upload_only.py --draft --replaces`）は、走っている `pipeline` が
投稿の直前に書き戻す `build/` を先に上げます ＝ **同じ本が2本**。**錠が無いので、
二重を止めるものも在りません。**

もう1つ: 逃げ道が `draft_legs`（手元の台本が4脚とも ○）の**中**に在りました。
`data/scripts/` は作業コピーごとに別で、焼く側の書き直しは `done` まで commit
されないので、**焼いている器の外から見ると手元はいつまでも ✗** です
＝ 逃げ道は焼いている本人にしか開いていませんでした。
"""
from __future__ import annotations

import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
JST = timezone(timedelta(hours=9))


def _rm():
    sys.path.insert(0, str(ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location(
        "run_marker_beat_mod", ROOT / "scripts" / "run_marker.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["run_marker_beat_mod"] = m
    spec.loader.exec_module(m)
    return m


def _rows(*, start_min: float, beat_min: float | None, vid: str = "VID1"):
    """**時計を読ませない**ため、いまからの分で組み立てる（`test_tests_are_clockless`）。"""
    now = datetime.now(JST)
    out = [{"at": (now - timedelta(minutes=start_min)).isoformat(timespec="seconds"),
            "kind": "start", "video_id": vid, "sha": "abc"}]
    if beat_min is not None:
        out.append({"at": (now - timedelta(minutes=beat_min)).isoformat(timespec="seconds"),
                    "kind": "beat", "video_id": vid, "sha": ""})
    return out


class _Fake:
    """`ahead_sweep` の代わり（錠と帳面だけを持つ）。"""

    def __init__(self, locked, rows):
        self._locked, self._rows = locked, rows

    def rebake_busy(self):
        return self._locked

    def _rebake_rows(self):
        return self._rows


def _run(m, monkeypatch, locked, rows, vid="VID1"):
    monkeypatch.setitem(sys.modules, "ahead_sweep", _Fake(locked, rows))
    return m._slot_baking(vid)


def test_a_lockless_bake_with_a_fresh_beat_counts_as_running(monkeypatch):
    """**錠が空でも、帳面の心拍が新しければ「焼いている」**（実物の 09-05 の形）。"""
    m = _rm()
    ok, why = _run(m, monkeypatch, False, _rows(start_min=110, beat_min=29))
    assert ok, f"錠の無い焼きを見落としています: {why}"
    assert "錠は空" in why, "錠が無いことを言っていません（起こし直しを止める根拠）"


def test_a_stale_beat_is_a_dead_bake(monkeypatch):
    """**心拍が `SLOT_BAKE_STALE_MIN` より古ければ、死んだ焼き**（門は鳴ってよい）。"""
    m = _rm()
    stale = m.SLOT_BAKE_STALE_MIN + 30
    ok, why = _run(m, monkeypatch, False, _rows(start_min=stale + 10, beat_min=stale))
    assert not ok, f"死んだ焼きを「走っている」と読んでいます: {why}"
    assert "死んだ焼き" in why


def test_the_lock_still_wins_when_it_is_held(monkeypatch):
    """錠が握られていれば、これまでどおり「焼いている」。"""
    m = _rm()
    ok, why = _run(m, monkeypatch, True, _rows(start_min=10, beat_min=None))
    assert ok and "錠" in why


def test_a_finished_bake_is_not_running(monkeypatch):
    """`done` が付いた `start` は、走っていない。"""
    m = _rm()
    rows = _rows(start_min=60, beat_min=30)
    rows.append({"at": datetime.now(JST).isoformat(timespec="seconds"),
                 "kind": "done", "video_id": "VID1", "sha": "abc"})
    ok, why = _run(m, monkeypatch, False, rows)
    assert not ok and "終わっています" in why


def test_a_bake_of_another_video_does_not_count(monkeypatch):
    """別の本を焼いていても、この本の焼きではない。"""
    m = _rm()
    ok, why = _run(m, monkeypatch, True, _rows(start_min=10, beat_min=5, vid="OTHER"))
    assert not ok and "別の本" in why


def test_the_stale_line_matches_the_procedure(monkeypatch):
    """**降りる線と同じ 120分** であること（`docs/trigger_main.md`）。

    ここを下げると、**まだ生きている焼き**（下限 37分・実測 55〜90分）を殺します。
    """
    m = _rm()
    assert m.SLOT_BAKE_STALE_MIN >= 120.0, (
        f"{m.SLOT_BAKE_STALE_MIN}分 —— 焼きの実測は 55〜90分 で、"
        "降りる線は 120分。これより短くすると生きている焼きを殺します"
    )


# ------------------------------------------------- `untreated_slot()` 側（よその器）

def test_a_foreign_bake_is_not_judged_by_this_worktrees_script(monkeypatch):
    """**よその器が焼いている本を、手元の `data/scripts/` で ✗ と判じないこと。**

    `data/scripts/` は作業コピーごとに別で、焼く側の書き直しは `done` まで
    commit されません。実測 09-05 06:3x: 焼く側の心拍は「台本が帯に入った・
    26.3分」＝ **尺は通っている**のに、隣の器の `draft_legs` は `['尺']` でした。
    **✗ を出していたのは、焼かれている台本ではありません。**
    """
    m = _rm()
    from src import daily_pick as dp
    from src import next_slot as ns
    monkeypatch.setattr(ns, "next_video", lambda *a, **k: None)
    monkeypatch.setattr(dp, "current", lambda *a, **k: {"video_id": "VID", "topic": "TOPIC"})
    monkeypatch.setattr(dp, "for_day", lambda *a, **k: None)
    monkeypatch.setattr(dp, "_topics", lambda *a, **k: [{"id": "TOPIC", "style": "outside_long"}])
    monkeypatch.setattr(dp, "pick_legs", lambda vid, **k: (["尺"], None))
    monkeypatch.setattr(dp, "draft_legs", lambda topic, **k: (["尺"], None))
    monkeypatch.setattr(m, "_slot_baking", lambda vid: (True, "焼いている"))
    monkeypatch.setattr(m, "_bake_elsewhere", lambda vid: "起こしたのは `agent-OTHER`")
    g = m.untreated_slot()
    assert g["fired"] is False, (
        "よその器の焼きを、手元の古い写しで止めています —— "
        "焼きの 2時間 ずっと、全部の回の `fix` が止まります"
    )
    assert "起こし直さないこと" in g["why"], "二重に焼かせない1行を書くこと"


def test_our_own_bake_still_needs_the_local_script_to_pass(monkeypatch):
    """**自分の器の焼き**は今までどおり2条件（手元 ○ ＋ 焼いている）。

    手元が読めるのだから、読んで判じるほうが強い。ここを緩めると
    「直しただけで一度も本に入らない台本」が素通りします。
    """
    m = _rm()
    from src import daily_pick as dp
    from src import next_slot as ns
    monkeypatch.setattr(ns, "next_video", lambda *a, **k: None)
    monkeypatch.setattr(dp, "current", lambda *a, **k: {"video_id": "VID", "topic": "TOPIC"})
    monkeypatch.setattr(dp, "for_day", lambda *a, **k: None)
    monkeypatch.setattr(dp, "_topics", lambda *a, **k: [{"id": "TOPIC", "style": "outside_long"}])
    monkeypatch.setattr(dp, "pick_legs", lambda vid, **k: (["尺"], None))
    monkeypatch.setattr(dp, "draft_legs", lambda topic, **k: (["尺"], None))
    monkeypatch.setattr(m, "_slot_baking", lambda vid: (True, "焼いている"))
    monkeypatch.setattr(m, "_bake_elsewhere", lambda vid: "")       # 自分の器
    g = m.untreated_slot()
    assert g["fired"] is True, "手元が読めて、その手元が ✗ なら止めること"


def test_a_start_row_without_a_session_counts_as_foreign(monkeypatch):
    """**起こした器が読めない回は「よそ」**へ倒すこと（手元で判じられない側）。"""
    m = _rm()
    rows = [{"kind": "start", "video_id": "VID1", "sha": "abc"}]      # `session` が無い
    monkeypatch.setitem(sys.modules, "ahead_sweep", _Fake(False, rows))
    assert m._bake_elsewhere("VID1"), "器が読めないのに『自分の焼き』と読んでいます"


def test_our_own_session_is_not_foreign(monkeypatch):
    """自分の `actor_id()` で起こした焼きは「よそ」ではない。"""
    m = _rm()
    rows = [{"kind": "start", "video_id": "VID1", "sha": "abc", "session": m.actor_id()}]
    monkeypatch.setitem(sys.modules, "ahead_sweep", _Fake(False, rows))
    assert m._bake_elsewhere("VID1") == ""


def test_no_start_row_is_not_foreign(monkeypatch):
    """帳面に `start` が無ければ、そもそも焼いていない（空を返す）。"""
    m = _rm()
    monkeypatch.setitem(sys.modules, "ahead_sweep", _Fake(False, []))
    assert m._bake_elsewhere("VID1") == ""
