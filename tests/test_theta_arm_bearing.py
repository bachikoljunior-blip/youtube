"""**θ（回転の速さ）は、腕の付いた前提だけで数えること。**（2026-08-27・最適化の回）

## 何が壊れていたか

`src/arm_speed.arm()` の速さは

    rate_X = p_X · log(gain_X) · θ · share_X

で、`share_X = len(mine) / len(pool)`、**`pool` は `lever` が `ARMS` の行だけ**です。
ところが `θ = throughput(rows)` の `rows` は **`closed()` そのもの** ——
**`lever: none` の前提も分子に入っていました。**

意味を書き下すと `θ · share_X` は「1日に腕 X で閉じる件数」のはずですが、

    θ · Σ share_X = n_all  / days       （`none` を含む）
    実際の腕の回転  = n_pool / days      （`none` を含まない）

実測 2026-08-27: **21件 ÷ 23日 = 0.913/日** に対し、腕の付いた実測は
**17件 ÷ 23日 = 0.739/日**。**すべての腕の伸び率が 23.5% 水増し**されていました。

**`none` は「この前提は腕を動かさない」と宣言した側**です。それが閉じるたびに
θ が上がり、**動かないと分かっている前提が、4本の腕を全部 速くしていました。**

## 同じファイルの他の2つは、既に正しい

`_pooled_p()` も `band()` も `[r for r in rows if r["lever"] in ARMS]` で絞っています。
`arm_speed.planned()`（未来の配分）も 2026-08-26 に `none` を分母から外しました。
**同じことを言う4か所のうち、θ の1か所だけが直っていなかった**形です
（`docs/JOURNAL.md`「同じことを2か所が別々に言っていて、片方しか読まれていない」）。

## 覆る条件

`rate` の式が `θ · share` を掛ける形をやめたら（例: 腕ごとに直接
「1日あたりの閉じた件数」を持つようにしたら）、この検査は用済みです。
**そのときは消してよい** —— ただし `θ · Σshare == n_pool / days` は保つこと。
"""
from __future__ import annotations

from datetime import date

from src import arm_speed


def _rows() -> list[dict]:
    """`none` を混ぜた閉じた前提。腕は 4件・`none` は 4件（＝半分）。"""
    out = []
    for i in range(4):
        out.append({"closed_on": date(2026, 8, 1), "lever": "per_video",
                    "effect": 2.0 if i == 0 else 1.0, "hit": i == 0, "claim": f"a{i}"})
    for i in range(4):
        out.append({"closed_on": date(2026, 8, 1), "lever": "none",
                    "effect": 1.0, "hit": False, "claim": f"n{i}"})
    return out


def test_theta_times_share_equals_arm_closes_per_day() -> None:
    """**θ × 配分の合計 ＝ 腕の付いた前提の、1日あたりの実測。**"""
    rows = _rows()
    today = date(2026, 8, 11)                 # 最初に閉じた日から 10日
    arms = arm_speed.all_arms(rows, today)
    got = sum(a["throughput"] * a["share"] for a in arms.values()
              if a["throughput"] and a["share"])
    want = 4 / 10                             # 腕の付いた 4件 ÷ 10日
    assert abs(got - want) < 1e-9, (
        f"θ×配分 {got:.4f}/日 は、腕の付いた実測 {want:.4f}/日 と合っていません"
        "（`none` を θ の分子に入れていませんか）")


def test_none_close_does_not_speed_up_the_arms() -> None:
    """**`lever: none` を1件 閉じても、腕の伸び率は上がらない。**

    上がるなら、**「動かさないと宣言した前提」が到達日を早めています。**
    """
    today = date(2026, 8, 11)
    base = [r for r in _rows() if r["lever"] != "none"]
    before = arm_speed.arm("per_video", base, today)["rate"]
    after = arm_speed.arm("per_video", base + [
        {"closed_on": date(2026, 8, 5), "lever": "none",
         "effect": 1.0, "hit": False, "claim": "n+"}], today)["rate"]
    assert before is not None and after is not None
    assert after <= before + 1e-12, (
        f"`none` を1件 閉じたら伸び率が {before:.5f} → {after:.5f} に**上がりました**")


def test_streak_counts_only_arm_bearing_rows() -> None:
    """連敗は、`expected_gap` と**同じ母集団**（腕の付いた行）で数えること。

    `expected_gap` は `_pooled_p()`（腕だけ）から出ています。連敗のほうが
    `none` も数えると、**別の母数どうしを比べて「外れすぎです」と言い出します。**
    """
    rows = [
        {"closed_on": date(2026, 8, 1), "lever": "per_video", "effect": 2.0, "hit": True},
        {"closed_on": date(2026, 8, 2), "lever": "none", "effect": 1.0, "hit": False},
        {"closed_on": date(2026, 8, 3), "lever": "none", "effect": 1.0, "hit": False},
    ]
    assert arm_speed.miss_streak(rows)["n"] == 0, (
        "腕を動かさないと宣言した前提が、腕の連敗に数えられています")
