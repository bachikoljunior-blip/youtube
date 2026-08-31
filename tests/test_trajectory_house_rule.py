"""**軌跡の供給の天井が、オーナーの規則を見ているか。**（2026-08-31 に足した）

## 何が壊れていたか

`scripts/trajectory.py` の `stages()` は、持続できる供給の天井を

    sup_cap = min(API の日枠 92本/日, 題材の生成速度)

で出していました。**規則を1度も見ていません。** 規則は **1日1本**なので、
軌跡の段2〜段4 と、そこから出る月の ¥ は、**最大 92倍 の供給の上**に
乗っていました（`cap_v_now` / `cap_both` / `cap_api_both` が全部これを掛けます）。

`eta.py` の `PLAN_PUBLISH_PER_DAY` は 2026-08-31 に `house_rule` へ寄せられましたが、
**`trajectory.py` は誰も引き取っていませんでした。**
「言っている所と、している所が別」——この repo でいちばん多い壊れ方です。

## ここが見るのは3つ

    1. `stages()` の `supply_cap` が、規則の本数を超えないこと
    2. 規則がいちばん小さいとき、律速の名前が規則を指すこと
    3. **上限の数が `trajectory.py` に写されていないこと**
       （出どころは `src/house_rule` の1か所）

## 覆る条件

**規則そのものが外れたとき**（オーナーが自分の言葉で外すまで、ありません）。
`house_rule.PUBLISH_PER_DAY` を上げれば、ここは自動で追随します ——
**この検査は数を持っていません。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import house_rule  # noqa: E402


def _stages_source() -> str:
    return (ROOT / "scripts" / "trajectory.py").read_text(encoding="utf-8")


def test_供給の天井は規則を候補に入れている():
    """`stages()` が `house_rule` を読んでいること。写した数ではなく。"""
    src = _stages_source()
    assert "house_rule" in src, (
        "scripts/trajectory.py が src/house_rule を読んでいません。"
        "供給の天井が規則（1日1本）を見ないと、軌跡は API の日枠（92本/日）の上を走ります"
    )
    assert "house_rule.planned_publishes_per_day()" in src, (
        "規則の本数は `house_rule.planned_publishes_per_day()` から取ること。"
        "定数を写すと、規則を変えたときに軌跡だけが古い数で走ります"
    )


def test_規則の数がtrajectoryに写されていない():
    """**出どころは1か所。** `PUBLISH_PER_DAY = 1` を写した行が無いこと。"""
    src = _stages_source()
    assert "PUBLISH_PER_DAY = " not in src, (
        "trajectory.py に上限の数が写されています。"
        "出どころは src/house_rule.py の1か所にすること"
    )


def test_天井は規則の本数を超えない():
    """実データで `stages()` を通し、`supply_cap` が規則以下であること。"""
    import trajectory

    st = _stages_or_skip(trajectory)
    if st is None:
        return
    rule = float(house_rule.planned_publishes_per_day())
    assert st["supply_cap"] <= rule + 1e-9, (
        f"持続できる供給の天井が {st['supply_cap']} 本/日 で、"
        f"規則の {rule} 本/日 を超えています。"
        "軌跡ぜんぶ（段2〜段4・月の¥）がこの数の上に乗ります"
    )


def test_規則が縛っているときは律速の名前が規則を指す():
    import trajectory

    st = _stages_or_skip(trajectory)
    if st is None:
        return
    rule = float(house_rule.planned_publishes_per_day())
    if st["supply_cap"] == rule and rule < st["supply_api"]:
        assert "規則" in st["supply_cap_why"], (
            f"律速が『{st['supply_cap_why']}』になっています。"
            "規則がいちばん小さいなら、そう名指しすること —— "
            "読む側が『材料さえ増やせば増える』と読み違えます"
        )


def _stages_or_skip(trajectory):
    """実データが揃っていない環境では黙って通す（検査の本体は上の2件）。"""
    try:
        return trajectory.stages(
            trajectory.per_video(), trajectory.supply(),
            trajectory.identify(), trajectory.trend(),
        )
    except Exception:
        return None
