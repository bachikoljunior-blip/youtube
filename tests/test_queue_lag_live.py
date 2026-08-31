"""**計画そのものが、判定に要る本を割らないこと**（2026-08-26 の最適化の回に踏んだ）。

`Plan._pull()` は **日付だけ**を見て入れ替え、`live_cost_lines()` が**後から**
`src/day_cap.py` の枠で数えて「撃たないこと」を出していました。
**門が下流にあって、しかも全か無かです。** 実測（この検査を書いた回・予約 345本）:

    入れ替え 12手 まで   **33日 早まる／どの群も割らない**
    入れ替え 16手 から   35日 ／ `opening_motion 対照(動きなし)` 8→7（要 8）
    入れ替え 24手（既定）**38日 ——ただし まるごと拒否され、実際に撃てるのは 0日**

**最後の 5日 を取りに行って、33日 を捨てていました。**
`scripts/batch_build.py::_pull_verdicts_first()` は毎周これを撃つので、
**毎周「判定を 38日 手前に倒します」と印字してから、0日 も倒していません。**

直したのは1か所です —— `_pull()` が手を採る条件に、**枠の門を足しました**
（`Plan._breaks_live()`）。割る手は採らずに次の候補へ行くので、
**計画は必ず撃てる形で出てきます。** 実測では、避けた結果 **38日 のまま
どの群も割らない**組み合わせが見つかりました（33日 に落ちてすらいません）。

なぜ `needed()` では足りなかったか（**別のものです。両方 要ります**）:

    needed()        その本が「どれかの群の N本目まで」に入っているか ＝ **身元**
    _breaks_live()  その本が居る枠に、**再生が付くか**            ＝ **枠**

`_pull()` は身元しか見ていないので、要る本を**早い枠**へ動かしたつもりで
**死んだ枠**（その日の `day_cap.cap()` 本目より後ろ）へ落とせます。
日付は早まり、標本は消えます。`falsified_if` は「上回らなければ外れ（同点も外れ）」
なので、**足りない標本は、そのまま「外れ」に化けます。**

## 覆る条件

- `live_cost_lines()` が返す2つ目（撃ってよいか）が **`False` になりうるなら**、
  `_pull()` の門が抜けています。**下の1件目がそれを見ています。**
- `day_cap.cap()` は実測から動きます。上限が上がれば割る群も変わりますが、
  **性質（計画は割らない）は動きません。** 数字を写さないこと。
"""
from __future__ import annotations

import pathlib
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "scripts"))

from scripts import queue_lag  # noqa: E402

JST = timezone(timedelta(hours=9))


def test_組んだ計画は判定に要る本を割らない():
    """**実物の控えで**組んで、そのまま門に通す。割ったら、`_pull()` が抜けている。"""
    plan = queue_lag.Plan()
    plan.improve()
    if not plan.swaps:
        return                      # 入れ替える手が無い日は、見るものが無い
    _lines, safe = queue_lag.live_cost_lines(plan)
    bad = queue_lag.live_bad(queue_lag.live_counts(plan.before_at, plan.at))
    assert safe, "計画が判定に要る本を割っています: " + " / ".join(bad)


def test_手数を増やしても割らない():
    """**貪欲に伸ばすほど危ない**ので、上限を振って全部 見ておく。

    直す前は 16手 から割り始め、既定の 24手 で拒否されていました。
    """
    for limit in (2, 6, 12, 16, 24, queue_lag.MAX_SWAPS):
        plan = queue_lag.Plan()
        plan.improve(limit)
        if not plan.swaps:
            continue
        bad = queue_lag.live_bad(queue_lag.live_counts(plan.before_at, plan.at))
        assert not bad, f"{limit}手 で割っています: " + " / ".join(bad)


def test_割った群だけを数える():
    """`live_bad()` は「足りていたのに足りなくなった」群だけ。

    もともと足りていない群（`a < n`）は**入れ替えのせいではありません** ——
    本が足りないという別の話（`live_slots.py --plan` の担当）なので、
    ここで拾うと、**入れ替えが永久に撃てなくなります。**
    """
    counts = [
        ("x", "足りていたのに割った", 8, 7, 8),
        ("y", "もともと足りない", 3, 2, 8),
        ("z", "割っていない", 20, 19, 16),
        ("w", "増えた", 15, 17, 16),
    ]
    bad = queue_lag.live_bad(counts)
    assert len(bad) == 1, bad
    assert "足りていたのに割った" in bad[0]


def test_門と印字は同じ数を読む():
    """**同じことを2か所が別々に言っていて、片方しか読まれていない** を作らない。

    `live_cost_lines()`（印字）と `Plan._breaks_live()`（門）が、
    **同じ `live_counts()`** を読んでいること。
    """
    plan = queue_lag.Plan()
    plan.improve()
    _lines, safe = queue_lag.live_cost_lines(plan)
    assert safe is not plan._breaks_live()
