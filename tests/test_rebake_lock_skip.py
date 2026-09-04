"""錠に弾かれた焼き直しは、印も その日の上限も 食わないこと。

実測 2026-09-03: 11:41 に印が立ち 1秒後に `skip`（`why: locked`）→
13:10 の掃きが 09/04 も 09/05 も焼かなかった（片方は「一度 焼いた」、
片方は「きょう既に 2回 焼いた」）。註は `ahead_sweep._drop_mark()`。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts import ahead_sweep

JST = timezone(timedelta(hours=9))


def _rows() -> list[dict]:
    """A/s1 は 05:02 に起きて `done` を残さず消えた（器の回収）。B/s2 は錠に弾かれた。
    **どちらも1本も焼いていません。**"""
    return [
        {"at": "2026-09-03T05:02:35+09:00", "kind": "start", "video_id": "A", "sha": "s1"},
        {"at": "2026-09-03T11:41:52+09:00", "kind": "start", "video_id": "B", "sha": "s2"},
        {"at": "2026-09-03T11:41:53+09:00", "kind": "skip", "video_id": "B", "sha": "s2",
         "why": "locked"},
    ]


def test_弾かれた回は上限の分子に入らない() -> None:
    """2026-09-03 16:0x に **1 → 0** へ直した。A/s1 も `done` が無く、錠も空いている
    （＝ 器ごと消えた）ので、上限を食う理由がありません。`_baked_today()` の註。"""
    assert ahead_sweep._baked_today(_rows(), "2026-09-03", busy=False) == 0


def test_走っている1本は分子に入る() -> None:
    """錠を誰かが握っていれば、`done` の無い `start` は「いま焼いている」1本です。"""
    assert ahead_sweep._baked_today(_rows(), "2026-09-03", busy=True) == 1


def test_焼き終わった回は分子に入る() -> None:
    rows = _rows() + [{"at": "2026-09-03T05:25:00+09:00", "kind": "done",
                       "video_id": "A", "sha": "s1", "rc": 0}]
    assert ahead_sweep._baked_today(rows, "2026-09-03", busy=False) == 1


def test_失敗した焼きも分子に入る() -> None:
    """rc≠0 でも `done` は書かれる ＝ 壊れた台本が無限に焼き直されないこと。"""
    rows = _rows() + [{"at": "2026-09-03T05:25:00+09:00", "kind": "done",
                       "video_id": "A", "sha": "s1", "rc": 1}]
    assert ahead_sweep._baked_today(rows, "2026-09-03", busy=False) == 1


def test_別の日は数えない() -> None:
    assert ahead_sweep._baked_today(_rows(), "2026-09-04", busy=False) == 0


def test_同じ本を何度も起こしても1回() -> None:
    """**数えるのは焼いた本であって、起こした回数ではありません**（2026-09-04 15:0x）。

    実測: `DfFyu8qZq3I`（sha 7fe81c38a757）は 01:01〜06:22 に **8回** 起こされ
    （そのつど器が回収され）、07:40 に1回だけ `done` を残しました。
    `start` の行を数えていたので分子は **8**、`Ec-j1-W4nqw` と合わせて **9**。
    上限 2 なので、**その日はもう1本も焼き直せません** —— 規則3 の当てどころが、
    翌日まで消えます。実際に焼いたのは 2本。
    """
    rows = [{"at": f"2026-09-03T0{h}:01:00+09:00", "kind": "start",
             "video_id": "A", "sha": "s1"} for h in range(1, 7)]
    rows.append({"at": "2026-09-03T07:40:00+09:00", "kind": "done",
                 "video_id": "A", "sha": "s1", "rc": 1})
    assert ahead_sweep._baked_today(rows, "2026-09-03", busy=False) == 1
    rows += [{"at": "2026-09-03T13:46:00+09:00", "kind": "start", "video_id": "B", "sha": "s2"},
             {"at": "2026-09-03T14:42:00+09:00", "kind": "done", "video_id": "B", "sha": "s2",
              "rc": 0}]
    assert ahead_sweep._baked_today(rows, "2026-09-03", busy=False) == 2


def test_別の本の焼きはその本の上限を食わない() -> None:
    """**上限は「同じ日に（同じ本を）焼き直す上限」です**（2026-09-04 15:0x）。

    実測 09/04: 09/04 の本（`DfFyu8qZq3I`・rc=1）と 09/05 の本（`Ec-j1-W4nqw`）で
    ちょうど 2回。全部の本を足して数えていたので、**09/05 の本はその日じゅう
    二度と焼けません** —— 規則3 の当てどころは 09/05 の本なので、
    これは規則3 を1日ぶん止めます。
    """
    rows = [{"at": "2026-09-03T01:00:00+09:00", "kind": "start", "video_id": "A", "sha": "s1"},
            {"at": "2026-09-03T02:00:00+09:00", "kind": "done", "video_id": "A", "sha": "s1",
             "rc": 1},
            {"at": "2026-09-03T13:00:00+09:00", "kind": "start", "video_id": "B", "sha": "s2"},
            {"at": "2026-09-03T14:00:00+09:00", "kind": "done", "video_id": "B", "sha": "s2",
             "rc": 0}]
    assert ahead_sweep._baked_today(rows, "2026-09-03", busy=False) == 2
    assert ahead_sweep._baked_today(rows, "2026-09-03", busy=False, video_id="B") == 1
    assert ahead_sweep._baked_today(rows, "2026-09-03", busy=False, video_id="C") == 0


def test_本ごとに数える側が配線されていること() -> None:
    """**数え方を直しても、呼ぶ側が全部の本を足していれば1ミリも変わりません。**"""
    import inspect
    src = inspect.getsource(ahead_sweep.rebake_plan_for)
    assert "video_id=vid" in src, "`rebake_plan_for()` が本ごとに数えていません"


def test_同じ本でも台本が違えば別に数える() -> None:
    """緩めすぎないこと —— 鍵は（本 × sha）。台本が変われば、それは別の焼きです。"""
    rows = [{"at": "2026-09-03T01:00:00+09:00", "kind": "start", "video_id": "A", "sha": "s1"},
            {"at": "2026-09-03T02:00:00+09:00", "kind": "done", "video_id": "A", "sha": "s1"},
            {"at": "2026-09-03T03:00:00+09:00", "kind": "start", "video_id": "A", "sha": "s2"},
            {"at": "2026-09-03T04:00:00+09:00", "kind": "done", "video_id": "A", "sha": "s2"}]
    assert ahead_sweep._baked_today(rows, "2026-09-03", busy=False) == 2


def test_弾かれた回が印を残さない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """印が残ると `rebake_attempted()` が 3時間 True を返し、その台本が焼けなくなる。"""
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    mark = tmp_path / "B-s2"
    now = datetime(2026, 9, 3, 11, 41, tzinfo=JST)
    mark.write_text(now.isoformat(timespec="seconds"), encoding="utf-8")

    assert ahead_sweep.rebake_attempted(
        "B", "s2", now=now + timedelta(minutes=30), root=tmp_path) is True
    ahead_sweep._drop_mark("B", "s2")
    assert not mark.exists()
    assert ahead_sweep.rebake_attempted(
        "B", "s2", now=now + timedelta(minutes=30), root=tmp_path) is False


def test_印が無くても倒れない(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    ahead_sweep._drop_mark("nope", "nope")


def test_焼いている最中は_起こす側が見送る(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """掃きは 20分 ごとに来る。長い1本（実測 25分 超）のあいだ、起こすたびに
    `start` と `skip` が1組 積まれていた（09/03 13:2x〜13:3x に実物で2組）。"""
    import fcntl

    monkeypatch.setattr(ahead_sweep, "_rebake_marks_dir", lambda: tmp_path)
    assert ahead_sweep.rebake_busy() is False

    fh = open(tmp_path / "rebake.lock", "a+", encoding="utf-8")
    fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        assert ahead_sweep.rebake_busy() is True
    finally:
        fcntl.flock(fh, fcntl.LOCK_UN)
        fh.close()

    assert ahead_sweep.rebake_busy() is False
