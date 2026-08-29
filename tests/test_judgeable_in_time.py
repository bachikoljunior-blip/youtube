"""**床は「本数」ではなく「期限に間に合う本数」で数える。**（2026-08-26 に踏んだ）

## この検査が守っているもの

**同じ床を、2つの口が別々に数えていました。**

    scripts/batch_build.motion_shortfall()   対照 **8本** ／ 床 8 → **足りています**
    src/judgeable.Floor.ok                   8本目 **10/10** → 判定 10/16
                                             → **期限 09/13 を 33日 超えます**

実測（`opening_motion` の対照8本の公開日）——

    08/28 ／ 09/02 ／ 09/06 ／ 09/06 ／ 09/12 ／ **10/02 ／ 10/04 ／ 10/10**

**期限 09/13 に間に合うのは 4本**（`last_useful_day` は 09/07）。

**この食い違いは、実際に1本ぶんの生成を空振りさせました。** 08/26 の回が
`motion_shortfall()` の「あと 1本」を読んで対照を1本 作り、床は 7→8本 に
なりましたが、**赤い検査3件はそのまま**でした ——
縛っていたのは本数ではなく日付だったからです。
"""
from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src import judgeable as J  # noqa: E402


def _floor(days_by_group: dict[str, list[str]], deadline: str, n: int = 8) -> J.Floor:
    return J.Floor(
        key="t",
        deadline=date.fromisoformat(deadline),
        groups={g: sorted(date.fromisoformat(d) for d in ds)
                for g, ds in days_by_group.items()},
        min_per_group=n,
    )


def test_間に合う日は期限から落ち着きと遅れを引いた日():
    """**2つの定数から出すこと。** 期限を写すと、延ばした回にずれます。"""
    f = _floor({"A": []}, "2026-09-13")
    assert f.last_useful_day == (
        date(2026, 9, 13) - timedelta(days=J.SETTLE_DAYS + J.ANALYTICS_LAG_DAYS))


#: **間に合う側／間に合わない側に、何本ずつ置くか。** 下の2件が共有します。
#: 日付そのものは `_split_days()` が定数から組み立てます（べた書きしないこと）。
IN_TIME, LATE = 4, 4


def _split_days(limit: date) -> list[str]:
    """`limit` に**間に合う `IN_TIME` 本**と、**間に合わない `LATE` 本**の公開日。

    ## なぜ日付をべた書きしないか（2026-08-30 に踏んだ。**同じ形の3件目**）

    ここには `2026-08-28 … 2026-10-10` の8つがべた書きしてあり、
    「間に合うのは4本」という数はその並びと
    `SETTLE_DAYS + ANALYTICS_LAG_DAYS` の**両方**から出ていました。
    遅れは**測る値**です（`src/settle.py`）。実測が **3日 → 4日** に動いた日、
    `last_useful_day` が1日 前へ寄り、**何も壊れていないのに 4 が 6 になりました。**

    **同じファイルが、同じことを一度 直しています** ——
    `test_間に合っていれば両方とも0` の docstring が
    「**遅れは測る値です。写すと、測り直すたびに検査のほうが壊れます**」と書いて、
    自分のぶんだけ定数から組み立てるように書き換えました（2026-08-27）。
    **残りの2件は写されていません。** オーナーの問い（受け取り帳 `e6d3be89`）
    「**失敗したならそこだけ直すんじゃなくて応用しないの？**」がまさにこの形です。

    **覆る条件**: `Floor.last_useful_day` が2つの定数以外から出るようになったら、
    ここも同時に直すこと（**数を2箇所で持たない**）。
    """
    last = limit - timedelta(days=J.SETTLE_DAYS + J.ANALYTICS_LAG_DAYS)
    ok = [(last - timedelta(days=i)).isoformat() for i in range(IN_TIME)]
    late = [(last + timedelta(days=1 + i)).isoformat() for i in range(LATE)]
    return sorted(ok + late)


def test_本数はそろっているのに期限に間に合わない形():
    """**これが 2026-08-26 に踏んだ形そのもの。**"""
    limit = date(2026, 9, 13)
    ctrl = _split_days(limit)
    last = limit - timedelta(days=J.SETTLE_DAYS + J.ANALYTICS_LAG_DAYS)
    treat = [(last - timedelta(days=i)).isoformat() for i in range(IN_TIME + LATE)]
    f = _floor({"対照": ctrl, "処置": treat}, limit.isoformat(), n=IN_TIME + LATE)
    # 本数だけを見る側は「足りている」と言う
    assert f.shortfall()["対照"] == 0
    # 期限を見る側は足りていない
    assert f.in_time()["対照"] == IN_TIME
    assert f.shortfall_in_time()["対照"] == LATE
    assert not f.ok


def test_間に合っていれば両方とも0():
    """**日付を手で置かないこと**（2026-08-27 に書き直した）。

    ここは `2026-09-01`〜`09-07` を**べた書き**していて、期限 `09-13` との差が
    ちょうど `落ち着き3 ＋ Analytics の遅れ3 ＝ 6日`、**余裕 0日** でした。
    `judgeable.ANALYTICS_LAG_DAYS` が実測で **3日 → 4日** に動いた日
    （`data/analytics_lag.jsonl` の `last_day` が 08-23 のまま JST の日が回った）、
    **この検査は、何も壊れていないのに赤くなりました。**

    同じ日に `config/hypotheses.yaml` の期限も3件 同時に赤くなっています
    （どれも 1日 きっかり）。**原因は1つで、症状が4つ**でした。

    **遅れは測る値です。写すと、測り直すたびに検査のほうが壊れます。**
    だからここは、その2つの定数から日付を組み立てます。
    """
    from datetime import date, timedelta

    from src import judgeable

    lag = judgeable.ANALYTICS_LAG_DAYS + judgeable.SETTLE_DAYS
    limit = date(2026, 9, 13)
    last = limit - timedelta(days=lag)          # ここまでに公開すれば間に合う
    days = [(last - timedelta(days=i)).isoformat() for i in range(8)]
    f = _floor({"対照": days, "処置": days}, limit.isoformat())
    assert f.shortfall()["対照"] == 0
    assert f.shortfall_in_time()["対照"] == 0, (
        "**ちょうど間に合う日に置いた本**を、間に合わない側に数えています"
    )
    assert f.ok

    # **1日 遅らせたら、間に合わない側へ移ること**（境目が本当にそこにあるか）
    late = [(last + timedelta(days=1)).isoformat()] + days[1:]
    assert _floor({"対照": late, "処置": days}, limit.isoformat())\
        .shortfall_in_time()["対照"] == 1


def test_期限を延ばすと自動でゆるむ():
    """**期限をこちら側に書き写さないこと。** 延ばした回に、ここも動くこと。

    緩めるほうの期限も**定数から組み立てます**（`_split_days()` の docstring）——
    `2026-10-20` のべた書きは、いまの遅れではたまたま足りているだけで、
    遅れが2日 伸びれば黙って足りなくなります。
    """
    limit = date(2026, 9, 13)
    ctrl = _split_days(limit)
    n = IN_TIME + LATE
    # **いちばん遅い本が間に合う**ところまで延ばす（＝ 全部そろう最小の期限）
    far = max(date.fromisoformat(d) for d in ctrl) + timedelta(
        days=J.SETTLE_DAYS + J.ANALYTICS_LAG_DAYS)
    tight = _floor({"対照": ctrl}, limit.isoformat(), n=n)
    loose = _floor({"対照": ctrl}, far.isoformat(), n=n)
    assert tight.shortfall_in_time()["対照"] == LATE
    assert loose.shortfall_in_time()["対照"] == 0


def test_作る側は期限を見る側から引いていること():
    """`scripts/batch_build.motion_shortfall()` が本数だけで数えていないこと。

    **数そのものは固定しません**（予約は毎周 動きます）。固定するのは
    **「期限に間に合う」という語が印字に出ること**だけ ——
    出ていなければ、また本数だけの口に戻っています。
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "bb_for_test", ROOT / "scripts" / "batch_build.py")
    bb = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bb)
    _, why = bb.motion_shortfall()
    if "群を読めませんでした" in why:
        return                      # 帳面が無い機械では何も言わない
    assert "期限に間に合う" in why or "足りています" in why, why
