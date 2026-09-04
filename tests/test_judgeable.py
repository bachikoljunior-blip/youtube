"""**期限が守れるか**を数える道具（`src/judgeable.py`）の検査。

## この検査が赤くなったときにやること

**期限だけを延ばすこと。`falsified_if` は変えないこと。**
条件を緩めるのと期限を動かすのは別のことです。ここを混ぜると
「測れないから条件を甘くした」に化けます（`config/hypotheses.yaml` 冒頭の作法）。
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
import yaml

from src import judgeable as J


def _floor(deadline: date, groups: dict[str, list[date]], n: int = 2) -> J.Floor:
    return J.Floor(key="t", deadline=deadline, groups=groups, min_per_group=n)


def test_ready_は_N本目の公開に落ち着きとAnalyticsの遅れを足す():
    f = _floor(date(2026, 9, 30), {"a": [date(2026, 9, 1), date(2026, 9, 3)]}, n=2)
    assert f.ready == date(2026, 9, 3) + timedelta(
        days=J.SETTLE_DAYS + J.ANALYTICS_LAG_DAYS
    )
    assert f.ok


def test_いちばん遅い群が_ready_を決める():
    """**片方の群だけそろっても判定できません。** 遅いほうに合わせます。"""
    f = _floor(
        date(2026, 10, 31),
        {
            "早い": [date(2026, 9, 1), date(2026, 9, 2)],
            "遅い": [date(2026, 9, 1), date(2026, 9, 20)],
        },
        n=2,
    )
    assert f.ready == date(2026, 9, 20) + timedelta(
        days=J.SETTLE_DAYS + J.ANALYTICS_LAG_DAYS
    )


def test_N本に満たない群があれば_ready_は出ない():
    """**「そろわない」を「間に合う」と読まないこと。** ここが 8/25 の壊れどころ。"""
    f = _floor(date(2026, 12, 31), {"a": [date(2026, 9, 1)], "b": []}, n=2)
    assert f.ready is None
    assert not f.ok                      # 期限がどれだけ先でも、判定できないものは ok ではない
    assert f.shortfall() == {"a": 1, "b": 2}


def test_期限が_ready_より前なら_守れないと言う():
    f = _floor(date(2026, 9, 5), {"a": [date(2026, 9, 1), date(2026, 9, 3)]}, n=2)
    assert not f.ok
    assert any("構造的" in x or "判定できません" in x for x in f.lines())


def test_SOURCES_と_yaml_の_key_が一対一で対応する():
    """**片方にしか無い `key` は、静かに数えられなくなります。**

    `SOURCES` にだけ有る → yaml が閉じたか、まだ `key:` を書いていない
    yaml にだけ有る       → 群の作り方が無いので `judgeable` が黙って飛ばす
    """
    doc = yaml.safe_load(J.HYPOTHESES.read_text(encoding="utf-8")) or {}
    in_yaml = {
        str(h["key"])
        for h in (doc.get("hypotheses") or [])
        if h.get("key") and not h.get("closed_on")
    }
    assert in_yaml <= set(J.SOURCES), f"群の作り方が無い key: {in_yaml - set(J.SOURCES)}"
    assert set(J.SOURCES) <= in_yaml, f"yaml に無い key: {set(J.SOURCES) - in_yaml}"


def test_yaml_の_key_は重複しない():
    doc = yaml.safe_load(J.HYPOTHESES.read_text(encoding="utf-8")) or {}
    keys = [str(h["key"]) for h in (doc.get("hypotheses") or []) if h.get("key")]
    assert len(keys) == len(set(keys)), keys


@pytest.mark.parametrize("f", J.floors(), ids=lambda f: f.key)
def test_実物で期限が構造的に守れる(f: J.Floor):
    """**期限までに判定できること。**

    赤くなったら、`python -m src.judgeable` が出す日付へ
    **期限だけを**動かすこと（条件は1文字も変えない。`python scripts/deadline_check.py --extend`）。

    ## **「予約にそろっているか」では見ません**（2026-09-04 19:4x に直した）

    ここは長らく `assert f.ready is not None`（＝ **N本目がもう予約に在ること**）から
    始まっていました。**規則1（1日1本）と規則2（作り置きなし）の下では、
    片群 16本 が先に予約へ並ぶことは構造上ありません** —— 並んでいたら、それが作り置きです。
    実測 2026-09-04: `stat_split`（対照 あと10本）と `opening_motion`（対照 あと2本）が
    **2件とも、この1行だけで赤**でした。**規則が入る前に書かれた検査で、
    いまは「規則どおりに運転している」ことを赤で報せています。**

    **見るべきは「そろっているか」ではなく「期限までに そろえられるか」です。**
    `Floor.ready_at_rule` が、足りぶん ÷ 規則の密度 でその日を出します
    （`scripts/queue_lag.py` と同じ式・数え方の正本は `judgeable` の側）。

    **床（`MIN_PER_GROUP`）を下げて緑にしないこと。** 期限だけを動かすこと。
    """
    when = f.ready if f.ready is not None else f.ready_at_rule
    assert when is not None, (
        f"判定できる日が、実物からも規則の密度からも出せません: {f.shortfall()}\n"
        + "\n".join(f.lines()))
    assert when <= f.deadline, (
        f"期限 {f.deadline} までに判定できません（判定できるのは {when}"
        + ("・予約の実物" if f.ready is not None else "・規則の密度からの推定") + "）\n"
        + "\n".join(f.lines()))
