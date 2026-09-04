"""**床が外れたら、`density` は「規則で死んだ腕」から戻ること。**（2026-09-04 17:5x）

`scripts/eta.physical_caps()` は `rule_cap = house_rule.PUBLISH_PER_DAY` を
**無条件に天井として掛けて**いました。定数は 1 のままなので、オーナーが 17:3x に
床を外しても `density` は ×1.00 のまま。そして `scripts/deadline_check.py` は
それを読んで、こう印字し続けます::

    **天井ではなく規則で止まっています**（`src/house_rule.py`・**覆る条件はありません**）。
    **測り直しても上がりません。外せるのはオーナーだけです**: `density` 2件

**「外せるのはオーナーだけ」——そのオーナーが、同じ日に外しました。**
`src/levers._density_ceiling_is_rule()` の docstring は
「**そのとき `rule_binds` は自然に False になります。手で消さないこと**」と
書いていましたが、**自然にはなりませんでした** —— 見ていたのが旗ではなく数だからです。

値段は `density` の前提 **2件** が燃料（30件）から外れたままだったこと。
`eta.py` は毎周「軌跡の腕が動くのは前提を1件 閉じたときだけ」と印字します。
"""
from __future__ import annotations

import inspect

from src import house_rule


def test_床が外れていれば_1日1本は既定値(monkeypatch):
    monkeypatch.setattr(house_rule, "OWNER_FLOORS_LIFTED", True)
    assert house_rule.publish_per_day_is_floor() is False


def test_床が戻れば_また床(monkeypatch):
    monkeypatch.setattr(house_rule, "OWNER_FLOORS_LIFTED", False)
    assert house_rule.publish_per_day_is_floor() is True


def test_本数は_測った上限の中に在る():
    """**この検査の条件は、自分で書いたとおりに満ちました。**（2026-09-05 に書き替えた）

    ここには「1日1本 は既定値として残ります —— **測って別のほうが速いと出るまで**、
    機械が勝手に増やす話ではありません」と書いて `== 1` を守っていました。
    **その「測って別のほうが速いと出た」が 2026-09-05 です**（`src/house_rule.py`
    の `PUBLISH_PER_DAY` の註に、実測と覆る条件を3つ書いてあります）。

    **だから守る物を移します** —— 数そのものではなく、
    **「測った上限の中に居ること」**のほうへ。ここを緩めると、
    `eta.py` の `physical_caps()` が使っている天井（`day_cap`）の外へ
    機械だけが歩き出せます ＝ **また「言っている所と、している所が別」**です。

    **覆る条件**: `day_cap.cap()` が実測ではなくなったとき（あそこが定数に
    なったら、この検査は上限を守っていないので作り直すこと）。
    """
    from src import day_cap

    n = house_rule.PUBLISH_PER_DAY
    assert n >= 1, n
    assert n <= day_cap.cap(), (
        f"{n}本/日 は、再生が付く実測の上限 {day_cap.cap()}本/日 の外です")


def test_模型は数ではなく旗を見る():
    """`rule_cap <= view_cap` だけで決めると、床が外れても ×1.00 のままです。"""
    import importlib.util
    from pathlib import Path

    src = Path(__file__).resolve().parent.parent / "scripts" / "eta.py"
    text = src.read_text(encoding="utf-8")
    assert "publish_per_day_is_floor()" in text, \
        "`eta.physical_caps` が旗を見ていません（数だけで決めています）"
    assert "rule_binds = rule_is_floor and rule_cap <= view_cap" in text, \
        "床が外れているのに `rule_binds` が立ちます"
    assert "arm_cap = min(view_cap, rule_cap) if rule_is_floor else view_cap" in text, \
        "床が外れているのに、天井を 1本/日 で切っています"


def test_覆る条件が書いてある():
    """**理由の書いていない規則は、次に来た側が判断できず惰性で残ります。**"""
    doc = inspect.getdoc(house_rule.publish_per_day_is_floor) or ""
    assert "覆る条件" in doc
    assert "-0.663" in doc, "密度を上げると1本あたりが薄まる実測が書かれていません"
    assert "1.80" in doc, "外しても天井は ×1.80 止まり、という数が書かれていません"
