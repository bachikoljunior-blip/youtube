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


def _split_days(limit: date, in_time: int, late: int) -> list[str]:
    """`limit` に**間に合う本**を `in_time` 本、**間に合わない本**を `late` 本。

    ## なぜ日付をべた書きしないか（2026-08-30 に、同じ形で2度目を踏んだ）

    `last_useful_day` は `SETTLE_DAYS + ANALYTICS_LAG_DAYS` から決まり、
    **`ANALYTICS_LAG_DAYS` は定数ではなく実測です**（`settle.analytics_lag_days()`）。
    だから日付をべた書きすると、**遅れを測り直した日に、何も壊れていないのに
    検査のほうが赤くなります。**

    すぐ下の `test_間に合っていれば両方とも0` の docstring が、
    **その事故（3日 → 4日）を 2026-08-27 に記録しています。**
    ところがあの回が組み立て直したのは**自分の検査だけ**で、
    同じファイルの上下2件は `== 4` を写したまま残りました ——
    そして 2026-08-30 に遅れが **4日** になり、**2件そろって赤**になりました
    （`in_time` は 4 ではなく 2、`shortfall_in_time` は 4 ではなく 6）。
    **`Floor` の側は1行も壊れていません。**

    **この repo が繰り返している「片方だけ直す」です。**
    ここに畳んだので、次に遅れが動いても3件とも付いていきます。
    """
    last = limit - timedelta(days=J.SETTLE_DAYS + J.ANALYTICS_LAG_DAYS)
    days = [last - timedelta(days=i) for i in range(in_time)]
    days += [last + timedelta(days=i + 1) for i in range(late)]
    return sorted(d.isoformat() for d in days)


def test_本数はそろっているのに期限に間に合わない形():
    """**これが 2026-08-26 に踏んだ形そのもの。**"""
    limit = date(2026, 9, 13)
    # **8本そろっているが、間に合うのは半分**（日付は定数から組み立てます）
    ctrl = _split_days(limit, in_time=4, late=4)
    treat = _split_days(limit, in_time=8, late=0)
    f = _floor({"対照": ctrl, "処置": treat}, limit.isoformat())
    # 本数だけを見る側は「足りている」と言う
    assert f.shortfall()["対照"] == 0
    # 期限を見る側は足りていない
    assert f.in_time()["対照"] == 4
    assert f.shortfall_in_time()["対照"] == 4
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
    """**期限をこちら側に書き写さないこと。** 延ばした回に、ここも動くこと。"""
    limit = date(2026, 9, 13)
    ctrl = _split_days(limit, in_time=4, late=4)
    # **延ばす先も定数から**（いちばん遅い本が、ちょうど間に合う所まで）
    far = (date.fromisoformat(ctrl[-1])
           + timedelta(days=J.SETTLE_DAYS + J.ANALYTICS_LAG_DAYS))
    tight = _floor({"対照": ctrl}, limit.isoformat())
    loose = _floor({"対照": ctrl}, far.isoformat())
    assert tight.shortfall_in_time()["対照"] == 4
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
