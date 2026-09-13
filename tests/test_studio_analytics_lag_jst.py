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


def test_本物の台帳の引きは_JSTの日で数えてある():
    """**本物の台帳**（live）: 引きごとに書かれた `lag_days` が、**JST の日の差**と合うこと。

    **2026-09-14 01:0x に書き直しました**（optimizer・Opus。**赤で見つけた**）——
    前の形は 2つ とも「きょうの状態」を不変条件にしていました（§5 の教訓の形 6つ目）:

      (i) **「遅れは 4回 とも 3日」を門にしていた** —— 遅れは API だけでは決まりません。
          **こちらが引く刻でも動きます**（門 20時間 ＝ 刻が 1日 4時間 ずつ前へ歩く・
          `trend.analytics_draws` の註）。実測 09/14 00:52 の引きは **遅れ 4日**。
      (ii) **引きの「最後の日」を `analytics_day` の max で当てていた** ——
          `cli.analytics_days_to_log` は**数が動いた日だけ**を足すので、
          **その max は API の最後の日ではありません**（実測 09/14 00:52 の引きは
          09-03〜09-05 の 3行 だけ ＝ max は 09-05・API の最後の日は 09-10）。
          **1回の引きで必ず 1行 書かれるのは `analytics_traffic`** のほう。

    **残す不変条件は 2つ**（どちらも日が経っても腐らない）:
      **(a) 遅れは 3日 より短くならない**（短くなったら `analytics` の 覆る条件 (1) の刻 ——
          そのときも**まず引いた刻を見ること**）。
      **(b) 書かれた `lag_days` は、引いた JST の日 − 最後の日**（＝ UTC へ戻ったら落ちる）。
          **(b) を当てるのは 2026-09-13 19:3x の直しより後の行だけ** ——
          それより前の 2行 は UTC で数えた偽の 2日 で、**台帳は書き換えません**（`lag_days` の註）。
    """
    fixed = dt.datetime(2026, 9, 13, 19, 30, tzinfo=JST)
    seen = 0
    for r in ledger_rows():
        if r.get("event") != "analytics_traffic" or not r.get("id"):
            continue
        at = dt.datetime.fromisoformat(r["at"]).astimezone(JST)
        got = (at.date() - dt.date.fromisoformat(r["id"])).days
        assert got >= 3, f"{at:%m/%d %H:%M} の引きの遅れが {got}日（`analytics` の 覆る条件 (1)）"
        if at >= fixed and r.get("lag_days") is not None:
            seen += 1
            assert r["lag_days"] == got, (
                f"{at:%m/%d %H:%M} の `lag_days` {r['lag_days']} が JST の日の差 {got} と割れています"
                "（UTC で数え直した側・`analytics.lag_days` の註）")
    assert seen, "直しより後の引きが 1行 もありません（この検査は何も見ていません）"


def test_直しより前の2行はUTCの偽の2日のまま_陽性対照():
    """**陽性対照**: 09/12 08:25・09/13 04:38 の 2行 は、いまも `lag_days: 2`（JST では 3）。

    ＝ 上の (b) を**全部の行**に当てたら落ちます（＝ 絞り `fixed` が効いていることの証拠）。
    **台帳を書き換えて緑にしないこと** —— この 2行 が「UTC で数えていた回が在った」の記録です。
    """
    bad = []
    for r in ledger_rows():
        if r.get("event") != "analytics_traffic" or r.get("lag_days") is None:
            continue
        at = dt.datetime.fromisoformat(r["at"]).astimezone(JST)
        if r["lag_days"] != (at.date() - dt.date.fromisoformat(r["id"])).days:
            bad.append(f"{at:%m/%d %H:%M}")
    assert bad == ["09/12 08:25", "09/13 04:38"], bad
