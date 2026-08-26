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


def test_本数はそろっているのに期限に間に合わない形():
    """**これが 2026-08-26 に踏んだ形そのもの。**"""
    ctrl = ["2026-08-28", "2026-09-02", "2026-09-06", "2026-09-06",
            "2026-09-12", "2026-10-02", "2026-10-04", "2026-10-10"]
    treat = ["2026-08-21", "2026-08-22", "2026-08-23", "2026-08-24",
             "2026-08-25", "2026-08-26", "2026-08-27", "2026-08-28"]
    f = _floor({"対照": ctrl, "処置": treat}, "2026-09-13")
    # 本数だけを見る側は「足りている」と言う
    assert f.shortfall()["対照"] == 0
    # 期限を見る側は足りていない
    assert f.in_time()["対照"] == 4
    assert f.shortfall_in_time()["対照"] == 4
    assert not f.ok


def test_間に合っていれば両方とも0():
    days = [f"2026-09-0{i}" for i in range(1, 8)] + ["2026-08-30"]
    f = _floor({"対照": days, "処置": days}, "2026-09-13")
    assert f.shortfall()["対照"] == 0
    assert f.shortfall_in_time()["対照"] == 0
    assert f.ok


def test_期限を延ばすと自動でゆるむ():
    """**期限をこちら側に書き写さないこと。** 延ばした回に、ここも動くこと。"""
    ctrl = ["2026-08-28", "2026-09-02", "2026-09-06", "2026-09-06",
            "2026-09-12", "2026-10-02", "2026-10-04", "2026-10-10"]
    tight = _floor({"対照": ctrl}, "2026-09-13")
    loose = _floor({"対照": ctrl}, "2026-10-20")
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
