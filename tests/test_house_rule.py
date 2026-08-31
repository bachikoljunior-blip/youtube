"""床（オーナーの固定の与件）が、実装のどこかに実在すること。

2026-08-31 に数えたところ、申し送りが「床は `src/house_rule.PUBLISH_PER_DAY = 1`、
検査は `tests/test_house_rule.py`」と書いていたのに、**どちらも存在しなかった。**
書き置かれた結論より先に、その根拠のほうが腐る、の実例。

この検査は、床が消えたり黙って上がったりしたら赤くする。
"""
from __future__ import annotations

import re
from pathlib import Path

from src import house_rule

ROOT = Path(__file__).resolve().parent.parent


def test_floor_is_one_per_day():
    """与件: 「明日の投稿から一本のみ」。上げも下げもしない。"""
    assert house_rule.PUBLISH_PER_DAY == 1


def test_backlog_is_not_counted_as_supply():
    """与件4: 作り置きは前提にしない（消さない・使わない・再利用しない）。"""
    assert house_rule.COUNT_BACKLOG_AS_SUPPLY is False


def test_floor_effective_from_september_first():
    assert house_rule.EFFECTIVE_FROM == "2026-09-01"


def test_forecast_can_express_the_floor():
    """予測が床を表現できること。

    2026-08-31 まで `PUBLISH_SCENARIOS = (4, 10, 25, 92)` で、**下限が 4**。
    オーナーの 1本/日 はこの表に無く、エンジンは与件を解けなかった。
    """
    text = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    match = re.search(r"^PUBLISH_SCENARIOS\s*=\s*\(([^)]*)\)", text, re.M)
    assert match, "PUBLISH_SCENARIOS が見つからない"
    body = match.group(1)
    assert "HOUSE_PUBLISH_PER_DAY" in body or "1," in body, (
        "予測の密度表に床（1本/日）が無い。"
        "床を表現できない予測の上で腕を選ぶと、順位が壊れる。"
    )


def test_house_gap_tool_exists_and_is_analysis_only():
    """差を数える道具が在ること。そして止められる口に入っていないこと
    （分析はポリシー停止中も動かしてよい）。"""
    from src import pause_guard

    assert (ROOT / "scripts" / "house_gap.py").is_file()
    assert "house_gap.py" not in pause_guard.BLOCKED_ENTRYPOINTS
