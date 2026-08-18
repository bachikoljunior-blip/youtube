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


def test_節の見出しが7つとも残っている():
    """節が `topic_forge.py` のテーマ単位。**減らすと在庫が減ります。**

    2026-08-18 に 5 → 7（賞与のある人の実質・181日目の崖の月給べつ）。
    """
    src = Path(__file__).resolve().parent.parent / "src" / "calc" / "ikuji.py"
    text = src.read_text(encoding="utf-8")
    assert text.count('print("\\n=== ') == 7


# ---- 足した2節の主張（**故障注入で、壊したら落ちることを見る**）----------


def test_賞与が増えると手取り比は必ず下がる():
    """給付の分子は賞与で1円も動かず、分母だけが増えるので。"""
    ratios = [r["net_ratio"] for r in ikuji.bonus_grid()]
    assert ratios == sorted(ratios, reverse=True)
    assert len({r["benefit"] for r in ikuji.bonus_grid()}) == 1, "給付が賞与で動いている"


def test_賞与5か月の67パーセント期は賞与なしの50パーセント期より低い():
    """**この節の主題そのもの。** 数字は `python -m src.calc.ikuji` の印字のまま。"""
    rows = {r["bonus_months"]: r for r in ikuji.bonus_grid()}
    assert round(rows[0]["net_ratio"] * 100, 4) == 84.9144
    assert round(rows[5]["net_ratio"] * 100, 4) == 61.1327
    later = ikuji.compare(300_000, ikuji.RATE_LATER)["net_ratio"]
    assert round(later * 100, 4) == 63.3689
    assert rows[5]["net_ratio"] < later


def test_賞与を給付の基礎に入れてしまうと落ちる(monkeypatch):
    """**壊す向きの検査。** 賞与を分子にも入れたら、主題が消える。"""
    真 = ikuji.benefit_month

    def 賞与こみ(monthly_pay, rate=ikuji.RATE_FIRST):
        return int(真(monthly_pay, rate) * 17 / 12)

    monkeypatch.setattr(ikuji, "benefit_month", 賞与こみ)
    with pytest.raises(_checks.TableError):
        ikuji.check_tables()


def test_181日目の崖はポイントで見ると月給が上がるほど深い():
    rows = ikuji.cliff_grid()
    drops = [r["drop_pt"] for r in rows]
    assert drops == sorted(drops)
    assert round(drops[0], 4) == 21.2454 and round(drops[-1], 4) == 22.0614


def test_崖の額のほうは月給に比例する():
    """**落差（ポイント）と額の差は、別の動き方をする。** ここが節の主題。"""
    shares = [r["gap_share"] for r in ikuji.cliff_grid()]
    assert max(shares) - min(shares) <= 0.0005
    assert round(max(shares) * 100, 5) == 17.00000


def test_崖の落差を月給で一定にすると落ちる(monkeypatch):
    真 = ikuji.compare

    def 平ら(monthly_pay, rate=ikuji.RATE_FIRST, resident_tax=0,
             social_rate=ikuji.SOCIAL_RATE):
        r = dict(真(monthly_pay, rate, resident_tax, social_rate))
        r["net_ratio"] = 0.85 if rate == ikuji.RATE_FIRST else 0.85 - 0.21
        return r

    monkeypatch.setattr(ikuji, "compare", 平ら)
    with pytest.raises(_checks.TableError):
        ikuji.check_tables()
