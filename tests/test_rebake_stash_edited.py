"""**控えを、上げた後に書き換えた回がありました**（2026-09-04 15:3x に足した）。

控え（`data/critique_queue/<ID>.script.json`）は「**その動画に実際に入っている台本**」の
記録で、焼き直しは 控え 対 手元の台本 の差で立ちます。09/04 04:46 の回（commit `69fe5244`）は
手元の台本と**控えの両方**を書き換えており、起きることは2つ:

    1. 同じ中身になるので「焼いても変わらない」＝ **直したものが動画に入らないまま気づかれない**
    2. 控えを読む側（`src/clarity.books()`・`src/frames.py`・前提の群分け）が実物と違う字を数える

実測: `Ec-j1-W4nqw`（07:42 に上げた 62コマ の本）の控えは **83コマ** になっていました。
**止めはしません**（読み違いのほうが高い）—— 同じ中身のときに、そう言うだけです。
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from scripts import ahead_sweep

JST = timezone(timedelta(hours=9))
NOW = datetime(2026, 9, 4, 15, 30, tzinfo=JST)
CUR = {"video_id": "V", "topic": "t"}
SAME = '{"segments": [{"narration": "a"}]}'


def _plan(**kw):
    args = dict(cur=CUR, stash_text=SAME, draft_text=SAME, draft_newer=True,
                attempted=False, scheduled=False, slot_at=None, now=NOW)
    args.update(kw)
    return ahead_sweep.rebake_plan(**args)


def test_同じ中身で控えが新しければ言う() -> None:
    out = _plan(stash_newer=True)
    assert out["do"] is False
    assert "焼いても変わらない" in out["why"]
    assert "上げた後に commit" in out["why"]


def test_控えが古ければ何も足さない() -> None:
    """**普通はこちら**（控えは上げたときに書かれ、その後 動かない）。"""
    for v in (False, None):
        out = _plan(stash_newer=v)
        assert "上げた後に commit" not in out["why"], v


def test_中身が違う回には出さない() -> None:
    """差が在れば焼くので、この註は要りません（画面の行を増やさないこと）。"""
    out = _plan(draft_text='{"segments": [{"narration": "b"}]}', stash_newer=True,
                slot_at=NOW + timedelta(hours=5))
    assert out["do"] is True
    assert "上げた後に commit" not in out["why"]


def test_呼ぶ側が控えの新しさを渡していること() -> None:
    """**数えても、渡されなければ 1度も出ません。**"""
    import inspect
    src = inspect.getsource(ahead_sweep.rebake_plan_for)
    assert "stash_newer=stash_newer" in src
