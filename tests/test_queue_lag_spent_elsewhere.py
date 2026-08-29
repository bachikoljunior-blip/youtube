"""**「枠が尽きた」と「先に別の所へ撃った」は、別の事実です。**

`quota_lines` は 403 を1回でも観測したら「**撃たないこと。枠は本当に
尽きています**」と印字します。正しいのですが、それが答えているのは
「**いま撃てるか**」だけで、「**この窓に、この入れ替えを買う金が在ったか**」
には1文字も答えません。**403 のあとに読む回には、金の無かった窓に見えます。**

実測（2026-08-29・窓 08/28 07:00Z〜）:

    通った `videos.update`   **62回 ＝ 3,100単位**（07:00Z〜11:02Z）
    この窓の `--apply`       **0行**（`data/queue_lag.jsonl`）
    その `--apply` の値段    **1,300単位**（26手／`opening_motion` **30日**）
    最初の 403               **12:37Z**（以後 110回）

**3,100 が同じ通貨で通ったあとに、1,300 の 30日 が撃たれていません。**

この検査が守るのは3つです:

1. 同じ通貨（`videos.update`）が入れ替えの値段ぶん通った窓では、必ず言う
2. その窓に `--apply` の行が在れば、「0行」とは言わない（撃った回の数を言う）
3. 値段に届かない窓では**黙る**（＝ 本当に金が無かった窓を責めない）

**覆る条件**: `videos.insert` が `videos.update` と同じ 403 で落ちるように
なったら（＝袋が1つになったら）、`videos.update` だけを数えるのをやめること。
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from scripts import queue_lag
from src import upload_cap


class _Plan:
    """`spent_elsewhere_lines` が読むのは `swaps` の長さだけです。"""

    def __init__(self, swaps: int) -> None:
        self.swaps = [object()] * swaps
        self.before = {"opening_motion": date(2026, 10, 6)}

    def readies(self) -> dict:
        return {"opening_motion": date(2026, 9, 7)}


@pytest.fixture()
def now() -> datetime:
    return datetime(2026, 8, 28, 20, 0, tzinfo=timezone.utc)


@pytest.fixture()
def ledgers(tmp_path, monkeypatch, now):
    """日枠の帳面（`videos.update` が N回）と、`--apply` の帳面（空）。"""
    quota = tmp_path / "day_quota.jsonl"
    progress = tmp_path / "queue_lag.jsonl"
    monkeypatch.setattr(queue_lag, "PROGRESS", progress)
    monkeypatch.setattr(upload_cap, "_in_window",
                        lambda name, when=None: _rows_holder["rows"])
    _rows_holder["rows"] = []
    return quota, progress


_rows_holder: dict = {"rows": []}


def _updates(n: int, head: datetime) -> list[dict]:
    """通った `videos.update` を n回（**別々の本・別々の秒**）。"""
    return [{"at": (head + timedelta(seconds=i)).isoformat(timespec="seconds"),
             "ok": True, "detail": f"videos.update vid{i}",
             "by": "reschedule.py:_update"} for i in range(n)]


def _spend() -> dict:
    return upload_cap.spend_in_window()


def test_says_it_when_the_same_currency_already_passed(ledgers, now) -> None:
    # 62回 × 50 ＝ 3,100単位。入れ替えは 13組 ＝ 26手 ＝ 1,300単位。
    _rows_holder["rows"] = _updates(62, upload_cap.window_start(now))
    lines = queue_lag.spent_elsewhere_lines(_Plan(13), _spend(), now)
    body = "\n".join(lines)
    assert "3,100単位" in body, body
    assert "1,300単位" in body, body
    assert "0行" in body, "この窓に `--apply` の行が無いことを言っていません"


def test_quiet_when_the_window_could_not_afford_it(ledgers, now) -> None:
    # 4回 × 50 ＝ 200単位。入れ替えは 1,300単位 —— **本当に金が無かった窓**。
    _rows_holder["rows"] = _updates(4, upload_cap.window_start(now))
    assert queue_lag.spent_elsewhere_lines(_Plan(13), _spend(), now) == []


def test_counts_the_applies_that_are_already_in_this_window(ledgers, now) -> None:
    quota, progress = ledgers
    _rows_holder["rows"] = _updates(62, upload_cap.window_start(now))
    progress.write_text(json.dumps({
        "at": (upload_cap.window_start(now) + timedelta(hours=1))
        .isoformat(timespec="seconds"),
        "before": {"opening_motion": "2026-10-06"},
        "promised": {"opening_motion": "2026-09-07"}, "moves": 20,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    body = "\n".join(queue_lag.spent_elsewhere_lines(_Plan(13), _spend(), now))
    assert "撃った 1回" in body, body
    assert "0行" not in body, "撃った回が在るのに『0行』と言っています"


def test_a_blocked_row_is_not_silence(ledgers, now) -> None:
    """**手前で返った回は「撃たなかった」ではありません。** 理由まで言うこと。"""
    quota, progress = ledgers
    _rows_holder["rows"] = _updates(62, upload_cap.window_start(now))
    progress.write_text(json.dumps({
        "at": (upload_cap.window_start(now) + timedelta(hours=2))
        .isoformat(timespec="seconds"),
        "blocked": "live_cost", "before": {"opening_motion": "2026-10-06"},
        "would_promise": {"opening_motion": "2026-09-07"}, "swaps": 13,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    body = "\n".join(queue_lag.spent_elsewhere_lines(_Plan(13), _spend(), now))
    assert "手前で返った 1回" in body, body
    assert "live_cost" in body, "返った理由が出ていません"


def test_rows_from_another_window_do_not_count(ledgers, now) -> None:
    """**前の窓の `--apply` は、この窓の答えではありません。**"""
    quota, progress = ledgers
    _rows_holder["rows"] = _updates(62, upload_cap.window_start(now))
    progress.write_text(json.dumps({
        "at": (upload_cap.window_start(now) - timedelta(days=1))
        .isoformat(timespec="seconds"),
        "before": {"opening_motion": "2026-10-06"},
        "promised": {"opening_motion": "2026-09-07"}, "moves": 20,
    }, ensure_ascii=False) + "\n", encoding="utf-8")
    body = "\n".join(queue_lag.spent_elsewhere_lines(_Plan(13), _spend(), now))
    assert "0行" in body, body


def test_ops_breakdown_is_priced_not_counted() -> None:
    """`ops` は**回数ではなく単位**で並ぶこと（`videos.update` は 1回 50単位）。"""
    _rows_holder["rows"] = []
    rows = [{"at": "2026-08-28T08:00:00+00:00", "ok": True,
             "detail": "videos.update a"},
            {"at": "2026-08-28T08:00:01+00:00", "ok": True,
             "detail": "playlistItems.list uploads"}]
    import unittest.mock as mock
    with mock.patch.object(upload_cap, "_in_window", lambda *a, **k: rows):
        ops = upload_cap.spend_in_window()["ops"]
    assert ops["videos.update"] == {"n": 1, "units": 50}
    # 表に無い読みは 1単位（**0 にしないこと** —— `unit_cost` の註）
    assert ops["playlistItems.list"]["units"] == 1
