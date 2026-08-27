"""**腕べつの「予定表 θ」**（`src/arm_speed.forward_by_arm` / `speed_weights`）を見張る。

## なぜ要るか（2026-08-27 に足した）

`scripts/eta.py --alloc`（「次の前提をどの腕に立てるのがいちばん早いか」）は
`rate = focus_rate × share` の `share` だけを振り直します。
`focus_rate = p · log(g) · θ` の **θ は `throughput()` ＝ 全体の実測ひとつ**で、
しかも `arm()` は閉じた前提が `MIN_N`（=3）に満たない腕の `p` と `g` を
**全体で代用**します。**つまり薄い腕どうしは、順位が天井の遠さだけで決まります。**

実測 2026-08-27 —— `--alloc` は「いちばん早いのは `sub_rate`」と言い、
同じ日の台帳の予定表では **`sub_rate` だけが今後14日 に1件も閉じられません**
（いちばん早い判定日が 09-16 ＝ 20日 先。他は density 08-28 ／ rpm 09-01 ／
per_video 09-05）。**「いちばん早い」は「次の2週間で動く」ではありません。**

**この検査が守るのは4つ**です。どれも「黙って埋めると薄い腕ほど自信ありげに
見える」という、この帳面がくり返し踏んでいる形:

1. **腕で割れていること** —— 全体の値を4本に配っただけなら意味がありません
2. **`ready` が空なら黙って 1.0 にしないこと** —— 重みが 1.0 で返ると
   「腕べつに見た上で差が無かった」と読まれます。**読めなかったと言うこと**
3. **重みの平均が 1 であること** —— 水準ではなく並びだけを動かす道具です
4. **近い期日が1件も無い腕を 0 にしないこと** —— 予定表は**下限**なので、
   「いま近い期日が無い」は「永久に閉じない」ではありません
"""
from __future__ import annotations

from datetime import date

import pytest

from src import arm_speed


TODAY = date(2026, 8, 27)

#: 閉じた前提が2件（08-25 と 08-27 ＝ 3日 に 2件）。
#: 開いた前提は腕ごとに2件ずつ。**腕で割れているかを見るための最小の台帳**です。
DOC = {
    "hypotheses": [
        {"claim": "closed-a", "lever": "per_video", "effect": 1.5,
         "closed_on": "2026-08-25"},
        {"claim": "closed-b", "lever": "rpm", "effect": 2.0,
         "closed_on": "2026-08-27"},
        # --- 開いている ---
        {"claim": "pv-soon", "lever": "per_video"},
        {"claim": "pv-late", "lever": "per_video"},
        {"claim": "sr-late-1", "lever": "sub_rate"},
        {"claim": "sr-late-2", "lever": "sub_rate"},
        {"claim": "rpm-soon", "lever": "rpm"},
        {"claim": "rpm-soon-2", "lever": "rpm"},
        {"claim": "den-soon", "lever": "density"},
        {"claim": "den-undated", "lever": "density"},      # 日の出ない1件
        {"claim": "none-arm", "lever": "none"},            # 腕ではない
    ],
}

#: `sub_rate` だけ、14日 の外に置いてあります（**実測 2026-08-27 と同じ形**）。
READY = {
    "pv-soon": date(2026, 8, 30),
    "pv-late": date(2026, 10, 20),
    "sr-late-1": date(2026, 9, 16),
    "sr-late-2": date(2026, 10, 6),
    "rpm-soon": date(2026, 8, 29),
    "rpm-soon-2": date(2026, 9, 3),
    "den-soon": date(2026, 8, 28),
}


def _h(by_arm: dict, lever: str, days: int) -> dict:
    return [h for h in by_arm[lever]["horizons"] if h["days"] == days][0]


def test_腕で割れていること():
    """全体の値を4本に配っただけなら、この道具は何も言っていません。"""
    ba = arm_speed.forward_by_arm(READY, doc=DOC, today=TODAY, horizons=(14, 30))
    assert set(ba) == set(arm_speed.ARMS)

    # 14日 窓（〜09-10）に入るのは pv-soon / rpm-soon / rpm-soon-2 / den-soon
    assert _h(ba, "per_video", 14)["n"] == 1
    assert _h(ba, "rpm", 14)["n"] == 2
    assert _h(ba, "density", 14)["n"] == 1
    assert _h(ba, "sub_rate", 14)["n"] == 0, (
        "**`sub_rate` は 14日 の外にしか期日がありません。**"
        "ここが 0 でないなら、腕で割れていません")

    assert len({_h(ba, k, 14)["per_day"] for k in arm_speed.ARMS}) > 1, (
        "4本とも同じ値です。**腕べつに見た意味がありません**")


def test_腕ではない前提を混ぜないこと():
    """`lever: none` は腕ではありません（`ARMS` に入っていない）。"""
    ba = arm_speed.forward_by_arm(READY, doc=DOC, today=TODAY, horizons=(30,))
    assert "none" not in ba
    total = sum(ba[k]["dated"] for k in arm_speed.ARMS)
    assert total == len(READY), (
        f"日の付いた前提の数が合いません（{total} ≠ {len(READY)}）")


def test_日の出ない開いた前提を数に残すこと():
    """**落とすと「予定表に全部 載っている」に見えます。**"""
    ba = arm_speed.forward_by_arm(READY, doc=DOC, today=TODAY, horizons=(30,))
    assert ba["density"]["undated"] == 1, (
        "`den-undated`（判定できる日が出ない1件）が数から消えています")
    assert ba["per_video"]["undated"] == 0


def test_readyが空なら黙って1倍にしないこと():
    """**1.0 で返ると「腕べつに見た上で差が無かった」と読まれます。**"""
    ba = arm_speed.forward_by_arm({}, doc=DOC, today=TODAY)
    assert all(ba[k]["missing"] for k in arm_speed.ARMS), (
        "読めなかったことを言っていません")

    sw = arm_speed.speed_weights(ba)
    assert sw["missing"], (
        "**重みが黙って 1.0 で返っています。** 読めなかったのか、"
        "差が無かったのかが区別できません")
    assert all(v == 1.0 for v in sw["weights"].values()), (
        "読めていないのに重みを付けています")


def test_重みの平均が1であること():
    """**水準ではなく並びだけを動かす道具**です（平均が1でなければ水準が動く）。"""
    ba = arm_speed.forward_by_arm(READY, doc=DOC, today=TODAY,
                                  horizons=arm_speed.FORWARD_HORIZONS)
    sw = arm_speed.speed_weights(ba)
    assert sw["missing"] is None
    mean = sum(sw["weights"].values()) / len(sw["weights"])
    assert mean == pytest.approx(1.0), (
        f"重みの平均が 1 ではありません（{mean:.3f}）。**水準が動きます**")


def test_遅い腕の重みが軽く速い腕の重みが重いこと():
    ba = arm_speed.forward_by_arm(READY, doc=DOC, today=TODAY,
                                  horizons=arm_speed.FORWARD_HORIZONS)
    w = arm_speed.speed_weights(ba)["weights"]
    assert w["sub_rate"] < 1.0 < w["rpm"], (
        f"回転の速い腕と遅い腕が並べ替わっていません: {w}")


def test_近い期日が無い腕でも0にしないこと():
    """**予定表は下限です。**「いま近い期日が無い」は「永久に閉じない」ではありません。

    0 にすると `rate` が 0 になり、その腕が「出ません」に化けます。
    """
    ba = arm_speed.forward_by_arm(READY, doc=DOC, today=TODAY, horizons=(14,))
    w = arm_speed.speed_weights(ba, window=14)["weights"]
    assert w["sub_rate"] > 0.0, (
        "**14日 に1件も無い腕の重みが 0 です。** 予定表は下限なので行きすぎです")
    assert w["sub_rate"] < w["rpm"]


def test_どの腕にも近い期日が無ければ並べ替えないこと():
    """全部 0 なら比が出ません。**黙って 0 で返すと到達日が「出ません」に化けます。**"""
    far = {k: date(2027, 1, 1) for k in READY}
    ba = arm_speed.forward_by_arm(far, doc=DOC, today=TODAY, horizons=(14,))
    sw = arm_speed.speed_weights(ba, window=14)
    assert sw["missing"], "根拠が無いのに黙っています"
    assert all(v == 1.0 for v in sw["weights"].values())


def test_窓が無ければ黙って埋めないこと():
    ba = arm_speed.forward_by_arm(READY, doc=DOC, today=TODAY, horizons=(7,))
    sw = arm_speed.speed_weights(ba, window=30)
    assert sw["missing"], "**無い窓を黙って埋めています**"
    assert all(v == 1.0 for v in sw["weights"].values())
