"""**Analytics の「遅れ」は JST の日で数え、読む刻で数え直す**
（2026-09-13 19:3x・optimizer・Opus。derivation は JOURNAL 19:3x・註は
`studio/analytics.lag_days` と `studio/trend.analytics_state`）。

**規則A**（`studio` を import しているので live の印が機械で付く・§6）。
**陽性対照は「壊したら落ちる」まで撃つこと**（§5 の教訓の形3つ目）—— 下の 3つ は、
この回に **UTC へ戻して／台帳の数へ戻して** 落ちるのを見てから置いています。
"""
from __future__ import annotations

import datetime as dt

from studio import analytics, trend
from studio.common import JST, ledger_rows


def test_遅れはJSTの日で数える(monkeypatch):
    """**JST 00:00〜09:00 に撃つと、UTC の日は 1日 手前です。**

    実測（台帳の `analytics_traffic`）: 09/13 04:38 JST の引きが、最後の日 09-10 に対して
    **2日** と書いていた（JST では 3日）。**API の遅れは 4回 とも 3日 で動いていません。**
    """
    rows = [{"day": "2026-09-08"}, {"day": "2026-09-10"}, {"day": "2026-09-09"}]
    # JST 04:38 ＝ UTC では前日 19:38。**UTC で数えると 2日 になります。**
    monkeypatch.setattr(analytics, "now_jst",
                        lambda: dt.datetime(2026, 9, 13, 4, 38, tzinfo=JST))
    assert analytics.lag_days(rows) == 3
    # 陽性対照: UTC の日で数えると 2日（この 2日 が、註の 覆る条件 (1) を偽で鳴らした側）
    assert analytics.lag_days(rows, today=dt.date(2026, 9, 12)) == 2
    # **`dt.date.today()`（UTC）へ戻ったら落ちること** —— 上の monkeypatch は `now_jst` しか
    # 差し替えないので、UTC へ戻した回は**この機械の日しだいで緑にも赤にもなります**
    # （実測: 09/13 10:5x UTC に戻して撃ったら、たまたま 3日 で通りました ＝ 振る舞いだけでは
    #  押さえられない側。旧道具の `tests/test_status_analytics_lag.py` が同じ形で字を見ています）。
    from conftest import source_of
    # **註の中にも `dt.date.today()` の字が在る**ので、既定の値の形そのものを見ること。
    src = source_of(analytics.lag_days, "lag_days")
    assert "today or now_jst().date()" in src, "既定が JST ではありません"
    assert "today or dt.date.today()" not in src, "UTC の日で数え直しています（`lag_days` の註）"


def test_遅れは読む刻から数え直す():
    """台帳の `lag_days`（**引いた刻の数**）をそのまま印字しないこと。

    この行の言い分は「**きょう**公開した本には答えません」＝ **いま**の話なので、
    引いてから日が変わったら数も変わること。
    """
    at = dt.datetime(2026, 9, 13, 4, 38, tzinfo=JST).isoformat(timespec="seconds")
    rows = [
        {"event": "analytics_day", "id": "2026-09-10", "views": 797, "minutes": 60, "at": at},
        {"event": "analytics_traffic", "id": "2026-09-10", "lag_days": 2,
         "sources": {"SHORTS": 100}, "at": at},
    ]
    same = trend.analytics_state(rows, now=dt.datetime(2026, 9, 13, 19, 33, tzinfo=JST))
    assert same["lag_days"] == 3            # 台帳の 2 ではなく、いま から数えた 3
    assert same["lag_at_pull"] == 2         # 引いた刻の数は残す（割れたら日が変わった印）
    later = dt.datetime(2026, 9, 15, 19, 33, tzinfo=JST)
    assert trend.analytics_state(rows, now=later)["lag_days"] == 5   # 引き直さなければ伸びる
    assert "**遅れ 5日" in trend.analytics_line(rows, now=later)


def test_本物の台帳でも遅れは3日のまま():
    """**本物の台帳**（live）: 引きは 4回 とも「最後の日 ＝ 引いた JST の日 - 3日」。

    **1行でも 3日 でない回が出たら、まず「引いた刻」を見ること**（`analytics` の 覆る条件 (1)）——
    API が速くなったのではなく、数え方が UTC へ戻った側かもしれません。
    """
    pulls: dict[str, str] = {}
    for r in ledger_rows():
        if r.get("event") == "analytics_day":
            pulls[r["at"]] = max(pulls.get(r["at"], ""), str(r.get("id") or ""))
    if not pulls:
        return
    for at, last_day in pulls.items():
        got = (dt.datetime.fromisoformat(at).astimezone(JST).date()
               - dt.date.fromisoformat(last_day)).days
        assert got == 3, f"{at} の引きの遅れが {got}日（最後の日 {last_day}）"
