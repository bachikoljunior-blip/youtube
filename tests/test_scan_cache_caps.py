"""**cap の違う呼び手が、互いの控えを消し合わないこと**（2026-09-03・最適化の回）。

実測 `data/api_calls.jsonl`（`history.py:channel_video_ids` の `search.list`・100単位/ページ）:

    08/31 の窓   33回 ＝ 3,300単位
    09/01 の窓   75回 ＝ 7,500単位
    09/02 の窓   51回 ＝ 5,100単位（窓が開いて 7分 で。5つの回が同時に走査）

原因は2つ。(1) 控えの file に記録が1つしか無く、`status`/`reschedule`（cap=400）と
`ahead_gate --live`（cap=5,000・毎周の掃きから2回）が**互いの記録を上書き**し、
cap=5,000 の側が毎回 `search.list` を 9ページ めくった。(2) 窓が開いた瞬間に
同時に立った回は、控えが書かれる前に全員が生で読んだ。

3日とも日枠 10,000 を超えて 403 で閉じ、その間はその日の1本を**焼き直しても
差し替えられない**（`videos.insert` 1,600 も同じ枠）＝ 規則3 が機械の側で死んでいた。

ここが落ちたら、その形が戻っています。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import history  # noqa: E402


@pytest.fixture(autouse=True)
def _sandbox(tmp_path, monkeypatch):
    (tmp_path / "data").mkdir()
    monkeypatch.setattr(history.config, "ROOT", tmp_path)
    monkeypatch.delenv("YT_NO_SCAN_CACHE", raising=False)
    monkeypatch.setattr(history, "_scan_window", lambda: "2026-09-03T07:00:00+00:00")
    yield tmp_path


def test_two_caps_coexist_in_one_window():
    """cap=400 を控えたあと cap=5000 を控えても、400 の記録が消えないこと。"""
    history._put_cached_video_ids("UU", 400, [f"v{i}" for i in range(400)])
    history._put_cached_video_ids("UU", 5000, [f"v{i}" for i in range(413)])

    got400 = history._cached_video_ids("UU", 400)
    got5000 = history._cached_video_ids("UU", 5000)
    assert got400 is not None and len(got400[0]) == 400
    assert got5000 is not None and len(got5000[0]) == 413


def test_an_untruncated_record_serves_any_cap():
    """チャンネルを最後まで読んだ記録（len < cap）は、どの cap の呼び手にも正しい。"""
    history._put_cached_video_ids("UU", 5000, [f"v{i}" for i in range(413)])

    got = history._cached_video_ids("UU", 400)
    assert got is not None, "切られていない記録は cap=400 の呼び手にも使えること"
    assert len(got[0]) == 413


def test_a_truncated_record_never_serves_a_bigger_cap():
    """cap=400 で切られた記録（len ≥ 400）を、cap=5000 の呼び手に渡さないこと。"""
    history._put_cached_video_ids("UU", 400, [f"v{i}" for i in range(400)])
    assert history._cached_video_ids("UU", 5000) is None


def test_old_single_record_format_is_still_read():
    """窓の途中に古い形の控えが残っていても、その窓のうちは効くこと。"""
    path = history._video_ids_cache_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"window": "2026-09-03T07:00:00+00:00",
                                "at": "2026-09-03T07:00:46+00:00", "uploads": "UU",
                                "cap": 400, "ids": ["a", "b"]}), encoding="utf-8")
    assert history._cached_video_ids("UU", 400) == (["a", "b"], "2026-09-03T07:00:46+00:00")


def test_a_different_window_replaces_everything():
    history._put_cached_video_ids("UU", 400, ["a"])
    history._put_cached_video_ids("UU", 5000, ["a", "b"])
    path = history._video_ids_cache_path()
    rec = json.loads(path.read_text(encoding="utf-8"))
    rec["window"] = "1999-01-01T00:00:00+00:00"
    path.write_text(json.dumps(rec), encoding="utf-8")

    assert history._cached_video_ids("UU", 400) is None
    history._put_cached_video_ids("UU", 400, ["z"])
    rec = json.loads(path.read_text(encoding="utf-8"))
    assert list(rec["recs"]) == ["400"], "窓が違えば、古い cap の記録も残さない"


class _Boom:
    def playlistItems(self):
        raise AssertionError("錠の中で控えが当たれば、口は1度も撃たれない")

    def search(self):
        raise AssertionError("錠の中で控えが当たれば、口は1度も撃たれない")


def test_the_lock_rereads_the_cache_before_scanning(monkeypatch):
    """錠を取ったあとに控えを読み直すこと（同時に立った回は 2人目から 0単位）。

    最初の読みでは無く、錠を取った瞬間に在る —— という形を作ります。
    """
    state = {"n": 0}
    real = history._cached_video_ids

    def first_miss_then_hit(uploads, cap):
        state["n"] += 1
        if state["n"] == 1:
            return None
        history._put_cached_video_ids(uploads, cap, ["a", "b"])
        return real(uploads, cap)

    monkeypatch.setattr(history, "_cached_video_ids", first_miss_then_hit)
    monkeypatch.setattr(history, "_with_ledger_ids", lambda found, since: found)
    assert history.channel_video_ids(_Boom(), "UU", cap=400) == ["a", "b"]
    assert state["n"] == 2
