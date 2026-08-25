"""**4か月免除は、1年でも少数派**（`sankyu` の6節目・2026-08-18 に足した）。

既にある節は「2026年9月の30日を1日ずつ動かすと3か月と4か月に割れる」まででした。
**その9月が当たりの多い月なのか少ない月なのかは、どの節も見ていません。**
産休の長さ98日は動かないのに、その98日がいくつの月末をまたぐかは
**月の日数の並び**で決まるので、出産月そのものが軸になります。

**年をまたぐと数が変わります**（2026年は81日／2028年は78日）。
だから表は年を引数に取り、検査も年を名指しします。
"""
from __future__ import annotations

import sys
from calendar import monthrange
from datetime import date
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.calc import _checks, sankyu  # noqa: E402


def test_2026年に4か月になる出産日は81日しかない():
    s = sankyu.birth_month_summary(2026)
    assert s["その年の日数"] == 365
    assert s["4か月になる日"] == 81
    assert s["3か月になる日"] == 284
    assert s["年間の割合"] == pytest.approx(81 / 365)


def test_出産月で当たりの割合が15倍ひらく():
    """**いちばん高い3月といちばん低い月で 1.5倍。** 同じ98日なのに。"""
    s = sankyu.birth_month_summary(2026)
    assert s["いちばん高い月"] == 3
    assert s["いちばん高い割合"] == pytest.approx(9 / 31)
    assert s["いちばん低い割合"] == pytest.approx(6 / 31)
    assert s["月の開き"] == pytest.approx(1.5)


def test_月ごとの日数の合計がその年に合う():
    """数え落としは**静かに**ずれます（合計を見ないと気づけない）。"""
    rows = sankyu.birth_month_grid(2026)
    assert len(rows) == 12
    for r in rows:
        assert r["4か月になる日"] + r["3か月になる日"] == r["その月の日数"]
        assert r["その月の日数"] == monthrange(2026, r["出産月"])[1]


def test_数えているのは実際の免除月数そのもの():
    """**表を別経路で数え直す。** 1月ぶんだけ、日ごとに引き直して突き合わせる。"""
    row = next(r for r in sankyu.birth_month_grid(2026) if r["出産月"] == 9)
    four = sum(
        1 for d in range(1, 31)
        if len(sankyu.exempt_months(*sankyu.sankyu_range(date(2026, 9, d)),
                                    ikuji=False)) == 4)
    assert row["4か月になる日"] == four == 6


def test_うるう年では数が変わる():
    """**年を添えずに読むと嘘になります。**この表の前提そのもの。"""
    assert sankyu.birth_month_summary(2028)["その年の日数"] == 366
    assert sankyu.birth_month_summary(2028)["4か月になる日"] != 81


def test_産休の日数を書き換えると落ちる(monkeypatch):
    """**故障注入。** 98日の内訳（42+56）が動けば、当たりの日数も動きます。"""
    monkeypatch.setattr(sankyu, "AFTER_DAYS", 60)
    with pytest.raises(_checks.TableError):
        sankyu.check_tables()
