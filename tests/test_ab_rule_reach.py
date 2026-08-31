"""**A/B が、規則（1日1本）の下で期限に間に合うか**を数える側の検査。

## なぜ要るか（2026-08-31 に測って足した）

`src/ab_split.Outlook.reachable` は、**未投稿の在庫**（`batch_build.pick`）だけで
「足ります／足りません」を決めていました。2026-08-31 のオーナー規則で
**その在庫は供給ではなくなりました**（規則1 公開は1日1本／規則2 作り置きをしない
＝ 予約は池へ戻す・材料としても再利用しない。`src/house_rule.py`）。

`scripts/eta.py`（`house_rule.drop_stockpile()`）と `scripts/reschedule.py`
（`--compact`）は同じ日に同じ直しを受けています。**A/B の側だけが、
消えた供給で「足ります」と言い続けていました。**

ここが見ているのは3つ:

    1. `reachable_under_rule` が、**在庫ではなく残り日数**で決まること
    2. `house_rule.cap()` を読んでいること（**規則が外れたら自然に緩む**）
    3. 届かないとき、**いちばん早く判定できる日**を出すこと
       （期限を延ばす先が「勘」にならないため）

**しきい値（床）は1つも触っていません。** 触ると、見分けられなかっただけの
実験が「効かない実験」として閉じ、`next_if_false` が腕ごと畳みます。
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import ab_split, house_rule  # noqa: E402
from src.settle import SETTLE_DAYS  # noqa: E402


def _outlook(need: dict[str, int], settle_by: date, today: date,
             stock: dict[str, int] | None = None) -> ab_split.Outlook:
    return ab_split.Outlook(
        experiment="t", settle_by=settle_by, need=need,
        stock=stock or {}, stock_total=sum((stock or {}).values()), today=today,
    )


def test_在庫がいくらあっても_残り日数が足りなければ届かない():
    """**これがこの検査の本体です。**

    在庫 1,000本 でも、規則の下で公開できるのは `残り日数 × 1本` だけ。
    """
    o = _outlook({"早枠": 16, "遅枠": 16}, date(2026, 9, 4), date(2026, 8, 31),
                 stock={"早枠": 500, "遅枠": 500})
    assert o.reachable is True, "在庫だけを見る古い判定は、そのまま残してあります"
    assert o.reachable_under_rule is False
    assert o.days_left == 4
    assert o.allowed_under_rule == 4 * house_rule.cap()
    assert o.short_under_rule == 32 - 4 * house_rule.cap()


def test_在庫が0でも_残り日数が足りれば届く():
    """**逆向きも見ること。** 規則の下の供給は「これから作る1日1本」です。"""
    o = _outlook({"遅い": 6, "速い": 4}, date(2026, 10, 7), date(2026, 8, 31))
    assert o.reachable is False, "在庫0なので、古い判定は「足りません」のまま"
    assert o.reachable_under_rule is True
    assert o.short_under_rule == 0


def test_床に届いていれば_あと0本():
    o = _outlook({"問い": 0, "断定": 0}, date(2026, 9, 3), date(2026, 8, 31))
    assert o.reachable_under_rule is True
    assert o.short_under_rule == 0
    assert "あと0本" in "".join(o.rule_lines())


def test_いちばん早く判定できる日を出す():
    """**期限を延ばす先が「勘」にならないため。**

    あと N本 ＝ `ceil(N / cap)` 日 ＋ 落ち着き `SETTLE_DAYS` 日。
    """
    from datetime import timedelta
    o = _outlook({"早枠": 16, "遅枠": 16}, date(2026, 9, 4), date(2026, 8, 31))
    days = -(-32 // max(1, house_rule.cap()))
    assert o.earliest_under_rule == date(2026, 8, 31) + timedelta(days=days + SETTLE_DAYS)
    # **締切（09/04）より後ろになること** —— そうでなければ届かないと言う理由が無い
    assert o.earliest_under_rule > o.settle_by


def test_規則が外れたら自然に緩む(monkeypatch):
    """**`house_rule.cap()` を読んでいること。**

    定数を写していると、オーナーが規則を外した日にここだけ取り残されます。
    """
    o = _outlook({"早枠": 16, "遅枠": 16}, date(2026, 9, 4), date(2026, 8, 31))
    assert o.reachable_under_rule is False
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", 10)
    assert o.allowed_under_rule == 40
    assert o.reachable_under_rule is True


def test_届かない実験は_その理由と日付を印字する():
    o = _outlook({"早枠": 16, "遅枠": 16}, date(2026, 9, 4), date(2026, 8, 31))
    text = "\n".join(o.rule_lines())
    assert "構造的に届きません" in text
    assert "いちばん早く判定できるのは" in text
    # **在庫を根拠にしないことを、文面でも言うこと**（次に来た回が読む先）
    assert "作り置きは規則2" in text


def test_日を跨いだ過去の締切は_0日で数える():
    """締切が過ぎていても落ちないこと（負の日数を作らない）。"""
    o = _outlook({"早枠": 16, "遅枠": 16}, date(2026, 8, 1), date(2026, 8, 31))
    assert o.days_left == 0
    assert o.allowed_under_rule == 0
    assert o.reachable_under_rule is False


def test_実物の報告に_規則の行が必ず出る():
    """**`--outlook` を付けない回でも出ること。**

    在庫を数えるのに数十秒かかるので `--outlook` は任意のままですが、
    「この期限は規則の下では届きません」は在庫を1本も数えずに出せます。
    黙っていると、届かない期限が「まだ判定しない」に混ざって素通りします。
    """
    text = ab_split.report(today=date(2026, 8, 31))
    for name in ab_split.EXPERIMENTS:
        assert name in text
    assert text.count(f"規則（1日{house_rule.cap()}本）の下") >= len(ab_split.EXPERIMENTS)
