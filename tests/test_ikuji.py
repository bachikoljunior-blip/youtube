"""`src/calc/ikuji.py` の**主張そのもの**を固定する（2026-08-16）。

この calc が動画で言うのは、次の3つです。**どれも「67パーセント」の外側にあります。**

1. **手取り比は額面比より高い** —— 社会保険料の免除と非課税のぶん
2. **手取り比は月給によって違う** —— 「実質8割」は定数ではない。
   比べる相手（働いていたときの手取り）が累進課税で下がるので、
   **月給が高いほど手取り比は高く出る**
3. **181日目から下がる** —— 支給率が67から50に落ちる

**`check_tables()` が緑であることは、ここでは証拠になりません。**
`check_tables()` は自分自身を呼んで自分を確かめており、
**式を壊したときに本当に落ちるか**は、外から壊してみないと分かりません
（`tests/test_calc_checks.py` と同じ考え方。故障注入で確かめる）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calc import _checks, ikuji  # noqa: E402


def test_制度の値の検査は通る():
    ikuji.check_tables()


def test_月給30万円の日額と1か月ぶんが条文どおりに出る():
    # 6か月ぶんの賃金 ÷ 180 = 月給 ÷ 30
    assert ikuji.wage_daily(300_000) == 10_000
    assert ikuji.benefit_month(300_000) == 201_000
    assert ikuji.benefit_month(300_000, ikuji.RATE_LATER) == 150_000


def test_手取り比は額面比より高い():
    """免除と非課税があるので、必ずこの向きになる。"""
    for pay in ikuji.MONTHLY_PAYS:
        r = ikuji.compare(pay)
        assert r["net_ratio"] > r["gross_ratio"], pay


def test_手取り比は月給が上がるほど高い():
    """**これが動画の主張。** 「実質8割」が定数でない、の中身。"""
    ratios = [ikuji.compare(p)["net_ratio"] for p in ikuji.MONTHLY_PAYS]
    assert ratios == sorted(ratios)
    assert ratios[0] < ratios[-1]
    # 額面比のほうは、逆にほとんど動かない（定率だから）
    gross = [ikuji.compare(p)["gross_ratio"] for p in ikuji.MONTHLY_PAYS]
    assert max(gross) - min(gross) < 0.005


def test_181日目から手取り比は下がる():
    first = ikuji.compare(300_000, ikuji.RATE_FIRST)["net_ratio"]
    later = ikuji.compare(300_000, ikuji.RATE_LATER)["net_ratio"]
    assert first > later


def test_住民税を引くと手元が減る():
    a = ikuji.compare(300_000, resident_tax=0)["left"]
    b = ikuji.compare(300_000, resident_tax=15_000)["left"]
    assert a - b == 15_000


@pytest.mark.parametrize("name,value", [
    ("RATE_FIRST", 0.5),      # 支給率を条文と違う値にする
    ("RATE_LATER", 0.8),      # 前半より後半を高くする（大小が逆）
    ("SOCIAL_RATE", 15),      # 率を % のまま書く（桁の取り違え）
    ("WAGE_BASE_DAYS", 200),  # 6か月 = 180日 の対応を崩す
])
def test_制度の値を壊すと検査が落ちる(monkeypatch, name, value):
    """**故障注入。** ここが落ちなければ、`check_tables()` は飾りです。"""
    monkeypatch.setattr(ikuji, name, value)
    with pytest.raises((_checks.TableError, ValueError, AssertionError)):
        ikuji.check_tables()


def test_月給の帯が上限の見えない範囲に収まっている():
    """支給額には毎年8月に改定される上限がある。

    **改定される値を表に置かない**と決めたので（`ikuji.py` の docstring）、
    代わりに**帯のほうを上限に届かない範囲に固定**します。
    ここを上へ広げるときは、上限の扱いを先に決めること。
    """
    assert max(ikuji.MONTHLY_PAYS) <= 450_000


def test_節の見出しが5つとも残っている():
    """節が `topic_forge.py` のテーマ単位。**減らすと在庫が減ります。**"""
    src = Path(__file__).resolve().parent.parent / "src" / "calc" / "ikuji.py"
    text = src.read_text(encoding="utf-8")
    assert text.count('print("\\n=== ') == 5
