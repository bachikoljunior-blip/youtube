"""**構造を測る検査が、実測の天井に乗らないようにする。**（2026-08-22 に足した）

## なぜ要るか（実測。同じ形で**2回**落ちています）

`scripts/eta.py` の `plan()` は、天井を2つ**実測から直に**読みます。

    view_cap ＝ `src/day_cap.cap()`      1日に再生が付く本数（`data/views.jsonl`）
    mix      ＝ `src/rpm_mix.last()`     長尺とショートの混ざり方（実効 RPM の天井）

**どちらも、こちらが1回測るたびに動きます。** ところが検査の側は
「段4 は段3 の写しではない」「腕を引いたら日付が動く」のような**形**を見ていて、
形は天井が動いても壊れません。**壊れるのは合成データが「届く帯」に居るかどうかだけ**です。

    08/20 の `rpm_mix --record` 初測  帯¥400 → 実効¥253  合格点 500,000 → 789,922回/月
    08/21 の `day_cap` の実測         25本/日 → 17本/日   天井   714,000 → 485,520回/月

**この2つで合格点が天井を追い越し、`days_to_target` が全部 `NEVER` に落ちました** ——
形は1行も壊れていないのに、**検査が15件 赤**になっています
（`docs/JOURNAL.md` 2026-08-22。8/21 の回は「最優先」と申し送って、直せずに終わった）。

## 使い方

    import _eta_pin                                   # tests/ は package ではないので
    pl = eta.plan(m, a, **pinned())                   # 天井を2つとも明示する

**帯（`mix={}`）＝「混ざり方をまだ測っていない」**で、据え置きの RPM に落ちます。
**`view_cap`＝25本/日** は `PLAN_PUBLISH_PER_DAY` そのもの（＝天井で縛らない）。

## 縛ってよい理由（**天井そのものを隠していません**）

天井の効きは、**天井を主題にした検査**が別に持っています ——
`tests/test_eta_day_cap.py`（本数の天井）、`tests/test_eta_surface_cap.py`（面と RPM）、
`tests/test_eta_target_date.py::test_再生数が届かないなら到達日も出ない`（届かない側）。
**置き場所を分けているだけ**で、どちらも消していません。
"""
from __future__ import annotations


def pinned(**over) -> dict:
    """`plan()` に渡す「実測に乗らない天井」。**上書きしたい分だけ渡す。**"""
    out: dict = {"view_cap": 25.0, "mix": {}}
    out.update(over)
    return out


def pin_day_cap(monkeypatch, value: float = 25.0) -> float:
    """`analyse()` 側の天井も止める（`a["view_cap_per_day"]` → `days_subs_at`）。

    **`plan()` に `view_cap` を渡すだけでは足りません** —— 段1（登録者の門）は
    `analyse()` の中で天井を当てており、そちらは引数で差せないからです。
    """
    from src import day_cap
    monkeypatch.setattr(day_cap, "cap", lambda *a, **k: value)
    return value


def pin_mix(monkeypatch) -> None:
    """混ざり方の実測を**当てない**（帯の RPM で解く）。

    `plan(mix=...)` で差せますが、**呼び出しが何十箇所もある file** では
    こちらで `src.rpm_mix.last` ごと止めるほうが漏れません
    （`scripts/eta.py` は importlib で file ごとに別インスタンスになりますが、
    `src.rpm_mix` は**共有**なので1回で効きます）。
    """
    from src import rpm_mix
    monkeypatch.setattr(rpm_mix, "last", lambda *a, **k: None)


def pin_ceilings(monkeypatch, cap: float = 25.0) -> None:
    """**実測から来る天井を2つとも止める。** 構造を測る file の autouse から呼ぶこと。"""
    pin_day_cap(monkeypatch, cap)
    pin_mix(monkeypatch)
