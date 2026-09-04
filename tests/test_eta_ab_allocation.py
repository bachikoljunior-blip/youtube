"""`scripts/eta.py::_sub_rate_ab_power()` の**配り方**の検査。**外へは1回も出ません。**

## なぜ在るか（2026-09-05 06:2x に踏んだ）

この行は 2026-09-04 に足された時点から、日数を**治療群だけ**で数えていました::

    treated = per_day * share * med
    days    = SUBS_BADGE_NEED_VIEWS / treated

そして最後にこう書いていました ——
「`SUBS_BADGE_SHARE` を上げるのは、形を直しても届かないときだけ。」

**2群の判定は、両群が要る再生に届いてからしか出ません。** 決めるのは
`min(share, 1-share)` の側なので、`share` を 0.5 から上げると
**治療群が速くなる以上に対照群が遅くなり、判定は必ず遅くなります**
（総本数が固定なら 1/n1 + 1/n2 は n1 = n2 で最小 ＝ **50% が最速**）。

`SUBS_BADGE_SHARE` はいま 0.5 なので、**印字される日数は当時も正しい数**でした。
壊れていたのは**助言のほう**で、それに従った回は必ず遅いほうへ動きます。
0.5 から動いた瞬間に、日数のほうも楽観側へ外れます（0.7 で 155日 対 実物 364日）。

**覆る条件**: 割り当てが「本ごと」から「同じ本の中の再生ごと」に変わったら、
遅いほうの群は本数ではなく再生で決まります。そのときは `per_day * binding` を
その配り方の実測に置き換え、この検査の `min()` も一緒に直すこと。
"""
from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _eta():
    spec = importlib.util.spec_from_file_location("eta_alloc_mod", ROOT / "scripts" / "eta.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["eta_alloc_mod"] = m
    spec.loader.exec_module(m)
    return m


def _days(text: str) -> float:
    """「片群 14,085再生 まで **218日**」の数を拾う。"""
    hit = re.search(r"再生 まで\s*\*\*([\d,]+)日\*\*", text)
    assert hit, f"日数が印字されていません: {text[:200]}"
    return float(hit.group(1).replace(",", ""))


def test_days_are_set_by_the_slower_group():
    """**日数は遅いほうの群で決まる**こと（0.5 の両側で同じ数になる）。"""
    m = _eta()
    if m._settled_median_views() is None:
        return                                     # 控えが無い環境では測らない
    lo = _days("\n".join(m._sub_rate_ab_power("#", 0.3)))
    hi = _days("\n".join(m._sub_rate_ab_power("#", 0.7)))
    mid = _days("\n".join(m._sub_rate_ab_power("#", 0.5)))
    assert lo == hi, (
        f"30% と 70% で日数が違います（{lo} 対 {hi}）—— "
        "片方の群だけで数えています。判定は両群が届いてからです"
    )
    assert mid < lo, f"50% が最速になっていません（50%={mid} ／ 30%={lo}）"


def test_share_of_one_half_is_the_fastest():
    """**0.5 が最速**であること（山の頂点が 0.5 にある）。"""
    m = _eta()
    if m._settled_median_views() is None:
        return
    seen = {s: _days("\n".join(m._sub_rate_ab_power("#", s)))
            for s in (0.1, 0.3, 0.5, 0.7, 0.9)}
    assert min(seen, key=lambda s: seen[s]) == 0.5, f"最速が 0.5 ではありません: {seen}"


def test_it_does_not_tell_the_round_to_raise_the_share():
    """**「`SUBS_BADGE_SHARE` を上げろ」と書かない**こと（必ず遅くなる手）。"""
    m = _eta()
    if m._settled_median_views() is None:
        return
    for s in (0.3, 0.5, 0.7):
        text = "\n".join(m._sub_rate_ab_power("#", s))
        assert "`SUBS_BADGE_SHARE` を上げる" not in text, (
            f"share={s} で「上げろ」と書いています —— "
            "2群の判定は遅いほうの群で決まるので、0.5 から上げると必ず遅くなります"
        )
        assert "買えません" in text, f"share={s} で、配り方では日数が買えないと言っていません"


def test_the_live_share_is_the_fastest_one():
    """いま配線されている `SUBS_BADGE_SHARE` が 0.5（＝最速）であること。

    **これは「0.5 でなければ落ちる」検査ではありません。** 0.5 から動いた回に、
    上の3つの検査と一緒に「なぜ動かしたか」を JOURNAL で読ませるための印です。
    """
    from src import ab_split
    assert abs(float(ab_split.SUBS_BADGE_SHARE) - 0.5) < 1e-9, (
        f"SUBS_BADGE_SHARE が {ab_split.SUBS_BADGE_SHARE} です —— "
        "2群の判定は 50% がいちばん速いので、動かしたなら理由を "
        "docs/JOURNAL.md に数字で書くこと"
    )
