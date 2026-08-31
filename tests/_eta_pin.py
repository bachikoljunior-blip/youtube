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

#: **構造を測る検査が使う「計画の密度」。**（2026-08-31 に足した）
#:
#: 2026-08-30 までは `eta.PLAN_PUBLISH_PER_DAY` がそのまま 25 だったので、
#: 検査は `pin_ceilings(monkeypatch, eta.PLAN_PUBLISH_PER_DAY)` と書けました。
#: **2026-08-31 にオーナーの規則が乗って、あれは 1 になりました** ——
#: 同じ字面のまま、`day_cap` を **1本/日** に留める呼び出しへ変わっています
#: （字面は正しいのに意味が変わる、いちばん見つけにくい壊れ方）。
#: **検査の側の「計画の数」は、ここに置くこと。**
PLAN_DENSITY = 25.0


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


def pin_subs(monkeypatch) -> None:
    """登録率の天井の実測を**当てない**（定義上の 100% で解く。2026-08-28 に足した）。

    `scripts/eta.py` の `physical_caps()` は `sub_rate` の天井を
    `src/subs_cap.best_per_video()`（**1本あたり登録率の実測の最大**）から取ります。
    **これも `day_cap` / `rpm_mix` と同じで、1回測るたびに動きます** ——
    構造を測る検査がその値に乗ると、`data/shorts_subs.json` を取り直しただけで
    赤くなります（`pin_mix` の docstring と同じ形。**3つ目**）。

    天井そのものは `tests/test_eta_subs_cap.py` が主題として持っています。
    """
    from src import subs_cap
    monkeypatch.setattr(subs_cap, "best_per_video", lambda *a, **k: None)


def pin_ceilings(monkeypatch, cap: float = 25.0, eta=None,
                 per_day: float = 25.0) -> None:
    """**外から来る天井を4つとも止める。** 構造を測る file の autouse から呼ぶこと。

    4つ目（`pin_house_rule`）は 2026-08-31 に足しました。**`eta` を渡すこと** ——
    渡さないと `eta.PLAN_PUBLISH_PER_DAY` が規則の 1 のまま残ります。
    """
    pin_day_cap(monkeypatch, cap)
    pin_mix(monkeypatch)
    pin_subs(monkeypatch)
    pin_house_rule(monkeypatch, eta, per_day)


def pin_house_rule(monkeypatch, eta=None, per_day: float = 25.0) -> float:
    """**オーナーが固定した規則（1日1本）を、構造を測る検査に当てない。**（2026-08-31）

    これは `day_cap` / `rpm_mix` / `subs_cap` と**まったく同じ形の4つ目**です ——
    `src/house_rule.PUBLISH_PER_DAY = 1` は 2026-08-31 にオーナーが固定した
    **運転の規則**で、`scripts/eta.py` は2か所でそれを読みます:

        PLAN_PUBLISH_PER_DAY = house_rule.PUBLISH_PER_DAY   （import 時に1回）
        physical_caps() の `rule_cap`                        （呼ぶたび）

    規則が乗った瞬間、`sustained_density()` は `min(1, 7.8) = 1.0` を返し、
    `density` の腕の伸びしろは `max(1.0, 1/7.8) = ×1.0`（＝引き代なし）になります。
    **これは正しい振る舞いです。** 規則の外の世界を軌跡に歩かせないための天井で、
    `src/house_rule.py` の「覆る条件: ありません」がそれを固定しています。

    **落ちたのは検査のほうです。** `tests/test_eta_density_*` は
    「**分母が『続けられる速さ』か、それとも計画の数か**」という**形**を見ていて、
    形は1行も壊れていません。壊れたのは「合成データが、腕の動く帯に居るか」だけ ——
    `_eta_pin` の冒頭に書いてある**2回目・3回目とまったく同じ壊れ方**の、4回目です
    （実測 2026-08-31: この1行で `tests/test_eta_*` が **18件 赤**）。

    ## 規則そのものは、どこが見張っているか（**隠していません**）

        tests/test_house_rule.py       `PUBLISH_PER_DAY == 1`・原文の一致
        tests/test_density_cap.py      `batch_build` が規則より多く置かないこと
        tests/test_eta_house_rule.py   `eta` の腕が規則で頭打ちになること（**規則を主題にした側**）

    **置き場所を分けているだけ**で、天井そのものは消していません。

    ## 使い方

        import _eta_pin
        _eta_pin.pin_house_rule(monkeypatch, eta)     # eta を渡すと定数も差し替わる

    **`eta` を渡すこと。** `PLAN_PUBLISH_PER_DAY` は import 時に束ねられるので、
    `src.house_rule` 側だけ差し替えても `eta` の定数は 1 のままです。
    そして **既定引数（`density=PLAN_PUBLISH_PER_DAY`）は def の時点で束ねられている**
    ので、差し替えても効きません —— **密度は明示して渡すこと**。
    """
    import inspect

    from src import house_rule
    monkeypatch.setattr(house_rule, "PUBLISH_PER_DAY", per_day)
    if eta is None:
        return per_day
    monkeypatch.setattr(eta, "PLAN_PUBLISH_PER_DAY", per_day)
    # **既定引数は def の時点で束ねられています。** 定数を差し替えても、
    #     `plan(m, a)` のように密度を渡さない呼び出しは 1 のまま解きます
    #     （2026-08-31 の実測: 定数だけ差し替えて、なお 6件 赤のままでした）。
    #     **束ね直すのはここ1か所**で、`monkeypatch` が元へ戻します。
    for name in ("sustained_density", "physical_caps", "_capped_arms", "plan"):
        fn = getattr(eta, name, None)
        if fn is None or not getattr(fn, "__defaults__", None):
            continue
        params = [q for q in inspect.signature(fn).parameters.values()
                  if q.default is not inspect.Parameter.empty]
        names = [q.name for q in params]
        if "density" not in names:
            continue
        d = list(fn.__defaults__)
        d[names.index("density")] = per_day
        monkeypatch.setattr(fn, "__defaults__", tuple(d))
    return per_day
