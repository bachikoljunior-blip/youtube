# -*- coding: utf-8 -*-
"""`cli.analytics_days_to_log` —— **台帳へ足す日だけ**を返すこと（2026-09-11 07:1x・optimizer・Opus）。

**見つけ方は台帳の列挙**（§5 の教訓の形4つ目「引けない条件を直したら、直した門が
実物のどの形を通るかを、台帳から列挙して確かめること」）:
`analytics` を 3回 撃った台帳に `analytics_day` が **12 × 3 ＝ 36行** 在り、
畳んだ日は 12日 しか無かった ＝ **skip の門が 1件も通っていない**。

原因は `known = {r.get("day") ...}` で、**行に `day` は無く 日は `id` に入る**
（`common.ledger` が骨を `id` に置く）＝ `known` は必ず `{None}`。
**この repo で 3例目の「1件も通れない門」**（06:3x `n_values`・08:4x `flats`）。

**直す向きは「id で skip」ではありません** —— Analytics は遅れて入った日を後から
書き直すので、id で skip すると**最初に引いた値が凍り** `trend` が古い数を印字し続けます。
**同じ数のときだけ落とす。** 覆る条件は `cli.analytics_days_to_log` の註。
"""
from studio import cli


def _row(day, views, minutes):
    return {"event": "analytics_day", "id": day, "views": views, "minutes": minutes}


def _api(day, views, minutes):
    return {"day": day, "views": views, "estimatedMinutesWatched": minutes}


def test_同じ数の日は足さない():
    rows = [_row("2026-09-07", 318, 104)]
    assert cli.analytics_days_to_log(rows, [_api("2026-09-07", 318, 104)]) == []


def test_書き直された日は足す():
    """**遅れて入った日は後から動きます** —— 動いた日を落とすと `trend` が古い数を印字する。"""
    rows = [_row("2026-09-07", 318, 104)]
    got = cli.analytics_days_to_log(rows, [_api("2026-09-07", 400, 104)])
    assert [r["day"] for r in got] == ["2026-09-07"]
    got = cli.analytics_days_to_log(rows, [_api("2026-09-07", 318, 120)])
    assert [r["day"] for r in got] == ["2026-09-07"]


def test_台帳に無い日は足す():
    assert [r["day"] for r in cli.analytics_days_to_log([], [_api("2026-09-08", 5, 1)])] == ["2026-09-08"]


def test_同じ日が何行あっても_いちばん新しい行と比べること():
    """台帳には**同じ日が何行も**在ります（36行 の実物がそれ）。比べる相手は最後の行。"""
    rows = [_row("2026-09-07", 318, 104), _row("2026-09-07", 400, 110)]
    assert cli.analytics_days_to_log(rows, [_api("2026-09-07", 400, 110)]) == []
    assert [r["day"] for r in cli.analytics_days_to_log(rows, [_api("2026-09-07", 318, 104)])] == ["2026-09-07"]


def test_positive_control_古い門は_1件も_skip_しないこと():
    """**壊したら落ちるまで撃つ**（§5 の教訓の形3つ目）。

    直す前の形（`r.get("day")` で名簿を作る）を、この検査の中で再現する ——
    **台帳に同じ日が在っても 1件も落ちない**ことを、実物の形の行で見せる。
    """
    rows = [_row("2026-09-07", 318, 104)]
    d = [_api("2026-09-07", 318, 104)]
    known = {r.get("day") for r in rows if r.get("event") == "analytics_day"}
    assert known == {None}                                   # ← 行に `day` は無い
    assert [r for r in d if r["day"] not in known] == d      # ← 1件も skip しない
    assert cli.analytics_days_to_log(rows, d) == []          # ← 直した側は落とす


def test_positive_control_実物の台帳が_同じ日を何行も持っていること():
    """**この欠陥の実物**（台帳の列挙）—— 直した後も、過去の重なりは消しません（§8「消さない」）。"""
    rows = [r for r in cli.ledger_rows() if r.get("event") == "analytics_day"]
    if not rows:
        return                                               # まだ 1度も引いていない環境
    days = {r["id"] for r in rows}
    assert len(rows) > len(days)                             # 36行 / 12日
