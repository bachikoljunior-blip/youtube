"""**403 のあとに通った呼び出しは、その 403 を反証する**（2026-08-26 に実測して足した）。

`day_quota()` は長らく「この窓で 403 を1回でも観測したら閉じている」でした。
**窓の中で単位が戻ることは無いので、正しい形に見えます。** 実測はそうではなく:

    16:12 JST  live_slots の `videos.update h35ot6MqYso` → **403**（帳面に載った）
    16:13 JST  同じ本を手で `--move`                      → **通った**

**日枠は1分では戻りません。** あの 403 は日枠ではなく、短い間に 120本 撃った側でした。
それでも帳面に載った瞬間に `day_quota().open` が False になり、
`queue_lag` / `live_slots` / `refresh_thumbnail` /
`batch_build._pull_verdicts_first()` が**そこから 24時間 まるごと降ります。**

**枠を推測して直しません。** 足すのは同じくらい確かな実測のほう ——
**後の成功が、前の 403 を反証します。**
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from src import upload_cap

JST = timezone(timedelta(hours=9))


@pytest.fixture()
def ledger(tmp_path, monkeypatch):
    monkeypatch.setattr(upload_cap, "_root", lambda: tmp_path)
    return tmp_path


def _jst(text: str) -> datetime:
    return datetime.strptime(text, "%Y-%m-%d %H:%M").replace(tzinfo=JST)


def test_a_lone_403_still_closes_the_window(ledger) -> None:
    """**外す向きは変えていません。** 403 だけなら、今までどおり閉じます。"""
    upload_cap.note_quota_hit(_jst("2026-08-26 16:12"), detail="videos.update X")
    q = upload_cap.day_quota(_jst("2026-08-26 17:00"))
    assert q.open is False
    assert q.observed is True


def test_a_later_success_reopens_it(ledger) -> None:
    upload_cap.note_quota_hit(_jst("2026-08-26 16:12"), detail="videos.update X")
    upload_cap.note_quota_ok(_jst("2026-08-26 16:13"), detail="videos.update X")
    q = upload_cap.day_quota(_jst("2026-08-26 17:00"))
    assert q.open is True
    assert q.observed is False
    assert "日枠ではありません" in q.line
    assert "videos.update X" in q.line


def test_a_success_before_the_403_does_not_reopen_it(ledger) -> None:
    """**順番が本体です。** 403 より前に通っていても、何も言いません。"""
    upload_cap.note_quota_ok(_jst("2026-08-26 16:05"), detail="videos.update X")
    upload_cap.note_quota_hit(_jst("2026-08-26 16:12"), detail="videos.update Y")
    q = upload_cap.day_quota(_jst("2026-08-26 17:00"))
    assert q.open is False


def test_the_last_403_is_the_one_that_counts(ledger) -> None:
    """403 → 成功 → 403 なら、**最後の 403 が生きています。**"""
    upload_cap.note_quota_hit(_jst("2026-08-26 16:12"), detail="a")
    upload_cap.note_quota_ok(_jst("2026-08-26 16:13"), detail="b")
    upload_cap.note_quota_hit(_jst("2026-08-26 16:40"), detail="c")
    q = upload_cap.day_quota(_jst("2026-08-26 17:00"))
    assert q.open is False


def test_ok_rows_are_not_counted_as_hits(ledger) -> None:
    """`quota_hits_in_window()` は `ok` の行を数えません。"""
    upload_cap.note_quota_ok(_jst("2026-08-26 16:13"), detail="b")
    assert upload_cap.quota_hits_in_window(_jst("2026-08-26 17:00")) == []
    q = upload_cap.day_quota(_jst("2026-08-26 17:00"))
    assert q.open is True
    assert q.hits == 0


def test_success_in_a_previous_window_does_not_reopen_this_one(ledger) -> None:
    """**窓をまたいだ成功は効きません**（窓の中の行しか読みません）。"""
    upload_cap.note_quota_ok(_jst("2026-08-26 15:00"), detail="old")   # 前の窓
    upload_cap.note_quota_hit(_jst("2026-08-26 16:12"), detail="new")
    q = upload_cap.day_quota(_jst("2026-08-26 17:00"))
    assert q.open is False
