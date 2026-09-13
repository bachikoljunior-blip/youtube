"""**引きの刻の正本は `analytics_traffic`**（`analytics_day` は「動いた日だけ」）
（2026-09-14 01:0x・optimizer・Opus。derivation は JOURNAL 01:0x・註は
`cli.analytics_last_at` と `trend.analytics_draws`）。

**規則A**（`studio` を import しているので live の印が機械で付く・§6）。
**陽性対照は「壊したら落ちる」まで撃つこと**（§5 の教訓の形3つ目）。
"""
from __future__ import annotations

import datetime as dt

from studio import cli, trend
from studio.common import JST


def _pull(at: str, last_day: str, lag: int = 3) -> list[dict]:
    """1回の引きが台帳に残す行（`analytics_day` は**動いた日だけ**なので 0行 のことが在る）。"""
    return [{"event": "analytics_traffic", "id": last_day, "lag_days": lag, "at": at}]


def test_何も動かなかった引きでも門は閉じる():
    """**`analytics_day` が 0行 の引き**（数がどの日も動かなかった回）でも、門が閉じること。

    **前の形は `analytics_day` だけを見ており**、この回は前の引きの刻を返し続けて
    **毎周 Analytics API を撃ちました**（別枠のクエリ 1周 3回＋カーブ）。
    """
    at = "2026-09-14T00:52:16+09:00"
    rows = _pull(at, "2026-09-10", lag=4)
    assert cli.analytics_last_at(rows) == dt.datetime.fromisoformat(at)
    now = dt.datetime(2026, 9, 14, 1, 30, tzinfo=JST)
    assert cli.analytics_due(rows, now=now) is False
    # 門（20時間）を過ぎたら、また撃つ回になること
    assert cli.analytics_due(rows, now=now + dt.timedelta(hours=20)) is True


def test_陽性対照_analytics_dayだけを見ると門が開きっぱなし():
    """壊したら落ちること ＝ 上の直しが本当に効いている証拠。"""
    rows = _pull("2026-09-14T00:52:16+09:00", "2026-09-10", lag=4)
    ats = [dt.datetime.fromisoformat(r["at"]) for r in rows
           if r.get("event") == "analytics_day"]          # **前の形**
    assert not ats, "この引きは `analytics_day` を 1行も残していません"
    # ＝ 前の形は None を返し、`analytics_due` は必ず True（毎周 撃つ）


def test_古い台帳にanalytics_dayしか無い回も読める():
    """この口が入る前の台帳（`analytics_traffic` を書く前の行）も、刻を失わないこと。"""
    at = "2026-09-10T16:07:00+09:00"
    rows = [{"event": "analytics_day", "id": "2026-09-07", "views": 1, "at": at}]
    assert cli.analytics_last_at(rows) == dt.datetime.fromisoformat(at)


def test_空引きは門を通った回だけ数える():
    """`--force` の引き直し（数分 差）は空引きに数えないこと。"""
    rows = (_pull("2026-09-10T16:07:00+09:00", "2026-09-07")
            + _pull("2026-09-10T16:17:00+09:00", "2026-09-07")     # force（10分 差）
            + _pull("2026-09-11T12:18:00+09:00", "2026-09-08")
            + _pull("2026-09-14T00:52:00+09:00", "2026-09-08", lag=6))  # 門を通った空引き
    got = trend.analytics_draws(rows)
    assert got["draws"] == 4
    assert got["empty"] == 1 and got["empty_run"] == 1
    # 陽性対照: 門を無視して数えると 2回 になる（force を混ぜた側）
    naive = sum(1 for a, b in zip(rows, rows[1:]) if a["id"] == b["id"])
    assert naive == 2


def test_空引きが無ければ印字にも出ない():
    rows = (_pull("2026-09-10T16:07:00+09:00", "2026-09-07")
            + _pull("2026-09-11T12:18:00+09:00", "2026-09-08"))
    assert trend.analytics_draws(rows)["empty"] == 0
    day = [{"event": "analytics_day", "id": "2026-09-08", "views": 10, "minutes": 1,
            "at": "2026-09-11T12:18:00+09:00"}]
    line = trend.analytics_line(rows + day,
                               now=dt.datetime(2026, 9, 11, 13, 0, tzinfo=JST))
    assert "空引き" not in line
