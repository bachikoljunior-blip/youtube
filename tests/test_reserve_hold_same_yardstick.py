"""**`floor` と `spent` を、違う物差しで引き算しないこと**（2026-08-29 15:4x）。

`src/upload_cap.py` の註は 08/29 14:0x から
「`note_quota_ok` を**読みにも足せ**」を「次にここへ来た回がやること」として
置いています。**そのまま撃つと、1窓ぶん 逆を踏みます。**

    measured_budget()["floor"]   `if start != here` ＝ **いまの窓を数えない**
                                 → 読みを数え始めても、しばらく**書き込みだけの古い値**
    measured_budget()["spent"]   **いまの窓** → 読みを足した瞬間に増える

`reserve_hold()` の門は `spent < floor - RESERVE_UNITS` なので、
**新しい物差しの `spent` から古い物差しの `floor` を引くと、窓の頭から
止まりっぱなし**になります。

**止まる先が問題です** —— `reserve_hold()` を呼ぶのは
`scripts/reschedule.py:434`、**`queue_lag.py --apply` が通る道そのもの**。
そこには `opening_motion` の判定日を **30日** 倒す手が乗っています
（`data/queue_lag.jsonl` は全4行 08/27・`after` なし ＝ 一度も当たっていない）。

**この検査が守っているのは「読みを数えるな」ではありません。**
守っているのは**順番**です —— 数えるなら、`floor` を同じ物差しで
積み直せるようにしてから。

**外してよいとき**: `measured_budget()` が `floor` と `spent` を同じ物差しで
返すようになったら（読みを数え始めた窓に印が付き、その窓を `floor` に
採らなくなったら）。そのときは `src/upload_cap.py` の該当の註も一緒に消すこと。
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


def _fill_window(day: str, writes: int, reads: int = 0) -> None:
    """`day` の窓（16:00 JST 始まり）に、通った呼び出しを積む。

    `videos.update` は 50単位・`search.list` は表に無ければ既定の 1単位。
    **読みは、いまは1件も帳面に載りません** —— それを載せるのが、
    上の註が名指ししている「次の回の仕事」です。ここでは載った場合を作ります。
    """
    minute = 0
    for i in range(writes):
        upload_cap.note_quota_ok(
            _jst(f"{day} 16:00") + timedelta(seconds=minute),
            detail=f"videos.update w{i}")
        minute += 1
    for i in range(reads):
        upload_cap.note_quota_ok(
            _jst(f"{day} 16:00") + timedelta(seconds=minute),
            detail=f"playlistItems.list r{i}")
        minute += 1


def test_floor_never_includes_the_current_window(ledger) -> None:
    """**これが、物差しがずれる仕組みそのものです。**

    `floor` はいまの窓を採らないので、**会計を変えた最初の窓では
    必ず「古い物差しの floor」と「新しい物差しの spent」**になります。
    """
    _fill_window("2026-08-27", writes=100)              # 5,000単位（過去の窓）
    _fill_window("2026-08-28", writes=100, reads=400)   # いまの窓
    b = upload_cap.measured_budget(_jst("2026-08-28 18:00"))
    assert b["floor"] == 5000, "floor はいまの窓を数えてはいけません"
    assert b["spent"] == 5400, "spent はいまの窓ぜんぶ（読み込み込み）"


def test_counting_reads_locks_the_window_that_carries_the_apply(ledger) -> None:
    """**読みを `spent` に足すと、`reserve_hold()` が窓の頭から止めます。**

    書き込みの量は前の窓と**同じ**（5,000単位）です ——
    増えたのは読みのぶんだけ。それでも門が閉じます。
    """
    _fill_window("2026-08-27", writes=100)              # floor = 5,000

    # (1) いまの会計（読みは載らない）: 書き込みだけなら、まだ止めません
    _fill_window("2026-08-28", writes=90)               # 4,500 < 5,000 - 400
    assert upload_cap.reserve_hold(_jst("2026-08-28 18:00")) is None

    # (2) 「読みも数える」に変えた世界: **同じ書き込み量のまま**止まります
    _fill_window("2026-08-28", writes=0, reads=200)     # +200 → 4,700
    hold = upload_cap.reserve_hold(_jst("2026-08-28 18:30"))
    assert hold, "読みを数えると、書き込みが同じでも門が閉じます"


def test_the_gate_that_protects_reads_is_closed_by_reads(ledger) -> None:
    """**円環です。** 門の文面は「残しているのは**前提を閉じる読み**のため」と
    言っています。その読みを `spent` に数えると、**読みを守る門が読みで閉じます。**
    """
    _fill_window("2026-08-27", writes=100)              # floor = 5,000
    _fill_window("2026-08-28", writes=0, reads=4700)    # 読みだけで 4,700単位
    hold = upload_cap.reserve_hold(_jst("2026-08-28 18:00"))
    assert hold, "読みだけで門が閉じるなら、門は自分の目的を壊しています"
    assert "前提を閉じる読み" in hold, (
        "門の文面が変わったら、この検査の理由も書き直すこと")
