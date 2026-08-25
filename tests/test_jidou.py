"""`src/calc/jidou.py` の**足した節の主張**を固定する（2026-08-18）。

**この表には検査ファイルがありませんでした**（`check_tables()` だけ）。
`check_tables()` は自分自身を呼んで自分を確かめるので、
**式を壊したときに本当に落ちるか**は外から壊さないと分かりません
（`tests/test_calc_checks.py` と同じ考え方）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calc import _checks, jidou  # noqa: E402


def test_制度の値の検査は通る():
    jidou.check_tables()

# ---- 1人あたりの総額（2026-08-18 に足した節。**故障注入つき**）--------------


def test_3人目から先の増分は一定():
    steps = [jidou.household_total(n + 1) - jidou.household_total(n) for n in range(3, 12)]
    assert len(set(steps)) == 1
    assert steps[0] == jidou.total_for(3) == 6_480_000


def test_1人あたりは第3子1人ぶんに永久に届かない():
    """**この節の主題そのもの。** 数字は `python -m src.calc.jidou` の印字のまま。"""
    rows = {r["人数"]: r for r in jidou.per_child_table()}
    assert rows[3]["1人あたり"] == 3_720_000
    assert rows[5]["1人あたり"] == 4_824_000
    assert rows[8]["1人あたり"] == 5_445_000
    for n in (3, 10, 200, 5_000):
        assert jidou.household_total(n) // n < jidou.total_for(3)


def test_人数が増えるほど1人あたりは増える():
    per = [r["1人あたり"] for r in jidou.per_child_table()][1:]
    assert per == sorted(per)


def test_第1子と第2子を第3子と同額にすると落ちる(monkeypatch):
    """**壊す向きの検査。** 2人ぶんの引きずりが無ければ、漸近線に届いてしまう。"""
    monkeypatch.setattr(jidou, "total_for", lambda order: 6_480_000)
    with pytest.raises(_checks.TableError):
        jidou.check_tables()
