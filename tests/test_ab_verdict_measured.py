"""A/B の床は、**値の出る本**の上に立っているか。

2026-09-01 の実測: `scripts/ab_split.py` は `title_form` を
「問い 23本 / 断定 19本 → **判定できます**」と印字していたが、
**その 42本のうち 13本には Analytics の行が無かった**
（断定の 4本 は公開から5日たって 0再生・9本 は遅れ待ち）。
engaged は `engagedViews ÷ views` なので、**0再生の本には値が存在しない。**

`falsified_if` は「上回らなければ外れ」なので、値の出ない本を床に数えると
**見分けられなかっただけの実験が『外れ』で閉じ、`next_if_false` が腕ごと畳む。**
`title_form` の腕は `per_video` ＝ `scripts/eta.py` が「引けるのはこれだけ」と
名指ししている腕なので、ここが倒れると到達日を動かす手が消える。

**この検査が守るのは1つだけ**: 「判定できます」と印字する経路のどれかが、
**値の出る本の数を同じ画面に出すこと。**
"""
from __future__ import annotations

from datetime import date

import pytest

from src import ab_verdict
from src.ab_split import EXPERIMENTS


def test_値の出る本は予約の本数と別に数えられる():
    """0再生の本と、遅れ待ちの本を、`counted` から分けて数える。"""
    values = {
        "動画.aaa.views": 100, "動画.aaa.engagedViews": 30,
        "動画.bbb.views": 200, "動画.bbb.engagedViews": 20,
        # ccc は行が無い（＝0再生）／ddd も行が無いが、まだ若い
    }

    class _Fake:
        metric = "engaged"

    def fake_members(_key):
        return {
            "問い": [(date(2026, 8, 20), "aaa"), (date(2026, 8, 20), "ccc")],
            "断定": [(date(2026, 8, 20), "bbb"), (date(2026, 8, 31), "ddd")],
        }

    import src.ab_verdict as mod

    old_members = mod.judgeable.members
    old_exp = mod.EXPERIMENTS
    mod.judgeable.members = fake_members  # type: ignore[assignment]
    mod.EXPERIMENTS = {"x": _Fake()}  # type: ignore[assignment]
    try:
        gcs = mod.counts("x", today=date(2026, 9, 1), values=values,
                         since=date(2026, 8, 4))
    finally:
        mod.judgeable.members = old_members  # type: ignore[assignment]
        mod.EXPERIMENTS = old_exp  # type: ignore[assignment]

    assert gcs["問い"].counted == 2 and gcs["問い"].usable == 1
    # 08/20 公開で行が無い ＝ 0再生（遅れではない）
    assert gcs["問い"].zero == 1 and gcs["問い"].young == 0
    # 08/31 公開で行が無い ＝ Analytics の遅れ待ち（**0再生と数えない**）
    assert gcs["断定"].zero == 0 and gcs["断定"].young == 1
    assert gcs["問い"].zero_rate == pytest.approx(0.5)


def test_実物で床に届いているのは予約の本数だけかを毎回数え直す():
    """**実物で撃つ。** 数は固定しない —— 日が動けば数も動くのが正しい。

    守るのは形だけ: `usable` は `counted` を超えない。
    """
    for key in EXPERIMENTS:
        gcs = ab_verdict.counts(key)
        for group, gc in gcs.items():
            assert gc.usable <= gc.counted, (key, group)
            assert gc.usable + gc.zero + gc.young + gc.unknown == gc.counted, (key, group)


def test_判定できますを裸で出す経路が値の出る本も出す():
    """`src/ab_split.report()` は、`判定できます` の直後に値の出る本を出すこと。"""
    from src.ab_split import report

    text = report()
    if "判定できます" not in text:
        pytest.skip("いま『判定できます』と出る実験がありません（それ自体は正常）")
    head = text.split("判定できます", 1)[1]
    assert "値の出る本" in head[:600], (
        "「判定できます」の直後に、値の出る本の数が出ていません。"
        "予約の本数だけで判定すると、見分けられなかっただけの実験が外れで閉じます"
    )
