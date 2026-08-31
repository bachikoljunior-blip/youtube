"""**池化が、締切を言うか。**（2026-08-31 に足した）

## 何が足りなかったか

`scripts/pool_drain.py` は「外す **267本**（見積り 13,617単位）」までは言いますが、
**いつ規則1 が破れるかを1文字も言っていませんでした。**

数だけだと、後回しにしてよい仕事に見えます。**実測 2026-08-31 23:5x**:

    2026-09-01   1本   ← 規則どおり
    2026-09-02   1本   ← 規則どおり
    2026-09-04   1本   ← 規則どおり
    2026-09-12   2本   ← [!] ここから破れる
    2026-09-13  14本
      …          …     ← **26日ぶん・238本 多い**

**手前の3日が規則どおりなので、頭だけ見ると「進んでいる」と読めます。**
そして 13,617単位 は日枠（10,000）の **1.4日ぶん**なので、
**1回の回では終わりません** —— 何日か続けないと終わらない仕事です。
締切を言わないと、その「続ける」が起きません。

## ここが見るのは2つ

    1. `first_breach()` が、**規則の上限を超える最初の日**を返すこと
       （**上限は `house_rule` から読む**。ここに数を写さない）
    2. 破れる日が1つも無ければ `None` を返す（そのとき印字は自分で黙る）

## 覆る条件

**予約が規則の内側に収まったとき。** そのとき `first_breach()` は `None` を返し、
印字は「どれも規則1 の内側です」に変わります —— **検査はそのままで通ります。**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import house_rule  # noqa: E402

import pool_drain  # noqa: E402


def test_破れる日が無ければ黙る():
    cap = house_rule.cap()
    days = {"2026-09-01": cap, "2026-09-02": cap, "2026-09-03": cap}
    assert pool_drain.first_breach(days, today="2026-09-01") is None


def test_最初に破れる日を返す():
    cap = house_rule.cap()
    days = {
        "2026-09-01": cap,          # 規則どおり
        "2026-09-02": cap,          # 規則どおり
        "2026-09-05": cap + 1,      # ここが最初
        "2026-09-06": cap + 12,
    }
    first, left, ndays = pool_drain.first_breach(days, today="2026-09-01")
    assert first == "2026-09-05", (
        f"最初に破れる日が {first} になっています。"
        "**手前の規則どおりの日で止まってはいけません** —— "
        "頭だけ見て『進んでいる』と読めてしまうのが、この行を足した理由です"
    )
    assert left == 4
    assert ndays == 2


def test_過ぎた日は数えない():
    cap = house_rule.cap()
    days = {"2026-08-20": cap + 30, "2026-09-05": cap + 1}
    first, _, ndays = pool_drain.first_breach(days, today="2026-09-01")
    assert first == "2026-09-05"
    assert ndays == 1, "過ぎた日を数えると、もう打てない手が締切として出ます"


def test_上限はhouse_ruleから読む():
    """**数を写していないこと。** 規則を変えたら、ここは自動で追随する。"""
    src = (ROOT / "scripts" / "pool_drain.py").read_text(encoding="utf-8")
    assert "house_rule.cap()" in src, (
        "規則の上限を `house_rule.cap()` から読んでいません。"
        "写すと、規則を変えたときに池化だけが古い数で判定します"
    )
