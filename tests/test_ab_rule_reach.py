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


#: **足りない場面を、規則の本数から作ること**（2026-09-05 に書き替えた）。
#:
#: ここは `need` に **16+16 ＝ 32本** をべた書きし、「4日 × 1本 では足りない」を
#: 見ていました。`PUBLISH_PER_DAY` が 10 になると **4日 × 10本 ＝ 40本 で足りて
#: しまい**、この file の「届かない側」の検査が3件とも、届く場面を測る形へ化けます
#: （＝ 見張っている物が消える。実際にこの回で3件 赤くなりました）。
#:
#: **算数はもともと `house_rule.cap()` を読んでいました。写しだったのは場面のほう**です。
#: **覆る条件**: `Outlook` が「残り日数 × 上限」以外の式になったら、ここも作り直すこと。
_DAYS_LEFT = 4
_SHORT_BY = 8            # **わざと足りなくする本数**（規則の何倍かに依りません）


def _need_pair() -> dict[str, int]:
    """**規則の下で必ず `_SHORT_BY` 本 足りない**2群の要り数。"""
    total = _DAYS_LEFT * house_rule.cap() + _SHORT_BY
    half = total // 2
    return {"早枠": half, "遅枠": total - half}


def test_在庫がいくらあっても_残り日数が足りなければ届かない():
    """**これがこの検査の本体です。**

    在庫 1,000本 でも、規則の下で公開できるのは `残り日数 × 上限` だけ。
    """
    need = _need_pair()
    o = _outlook(need, date(2026, 9, 4), date(2026, 8, 31),
                 stock={"早枠": 500, "遅枠": 500})
    assert o.reachable is True, "在庫だけを見る古い判定は、そのまま残してあります"
    assert o.reachable_under_rule is False
    assert o.days_left == _DAYS_LEFT
    assert o.allowed_under_rule == _DAYS_LEFT * house_rule.cap()
    assert o.short_under_rule == _SHORT_BY


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
    need = _need_pair()
    o = _outlook(need, date(2026, 9, 4), date(2026, 8, 31))
    total = sum(need.values())
    days = -(-total // max(1, house_rule.cap()))
    assert o.earliest_under_rule == date(2026, 8, 31) + timedelta(days=days + SETTLE_DAYS)
    # **締切（09/04）より後ろになること** —— そうでなければ届かないと言う理由が無い
    assert o.earliest_under_rule > o.settle_by


def test_規則が外れたら自然に緩む(monkeypatch):
    """**`house_rule.cap()` を読んでいること。**

    定数を写していると、オーナーが規則を外した日にここだけ取り残されます。
    **上限は、いまの値の何倍かで作ること**（2026-09-05）—— ここは 10 をべた書き
    しており、規則そのものが 10 になった日に「緩める前」と「緩めた後」が
    同じ数になって、この検査は何も見なくなりました。
    """
    need = _need_pair()
    o = _outlook(need, date(2026, 9, 4), date(2026, 8, 31))
    assert o.reachable_under_rule is False
    loosened = house_rule.cap() * 3
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", loosened)
    assert o.allowed_under_rule == _DAYS_LEFT * loosened
    assert o.reachable_under_rule is True


def test_届かない実験は_その理由と日付を印字する():
    o = _outlook(_need_pair(), date(2026, 9, 4), date(2026, 8, 31))
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
