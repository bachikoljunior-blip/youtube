"""**オーナーが固定した規則（1日1本）が、`scripts/eta.py` の中で本当に効いているか。**

2026-08-31 に足した。オーナー原文（**一字も変えないこと**）:

    「動画は1日一本作り置きはなしにして。次の投稿予定までにそこで投稿する動画を
      改善し続ける。それは固定にして。その上で目標を目指す」

`tests/test_house_rule.py` は**出どころ**（`src/house_rule.PUBLISH_PER_DAY == 1` と
原文が repo に在ること）を、`tests/test_density_cap.py` は**置く側**
（`batch_build` が規則より多く置かないこと）を持っています。
**この file が持つのは「読む側」** —— 到達日の道具が、規則の本数で解いて、
**その本数を画面に出しているか**です。

## なぜ要るか（**この回で実際に踏んだ**）

規則が入った瞬間、`tests/test_eta_*` が **20件 赤**になりました。
形は1行も壊れておらず、落ちたのは全部「合成データが腕の動く帯に居るか」だけです。
そこで `tests/_eta_pin.pin_house_rule()` を足して、**構造を測る検査には規則を当てない**
ことにしました —— `day_cap` / `rpm_mix` / `subs_cap` と同じ扱いです。

**縛らせないなら、縛られている側を誰かが持たないといけません。** それがここです。
**この file だけは、規則を実物のまま読みます**（`pin_house_rule` を呼びません）。

## この回に見つかった欠陥（`test_表にいまの計画の本数の行が出る`）

`report()` の密度の表は `PUBLISH_SCENARIOS`（4/10/13/25/92）だけを回していました。
規則で `PLAN_PUBLISH_PER_DAY` が **1** になると、**実際に走っている本数の行が
表から消えます** —— 読む側には 4本/日 が最小に見えるのに、機械は 1本/日 で
解いています。`analyse()` は同じ和集合（`PUBLISH_SCENARIOS | {PLAN}`）を作って
`days_subs_at` に鍵を持っており、**表に出す側だけが古い並びでした。**
この repo でいちばん多い壊れ方（**言っている所と、している所が別**）そのものです。

**覆る条件**: オーナーが自分の言葉で規則を外したとき。そのときは
`src/house_rule.py` に原文を書き足して `PUBLISH_PER_DAY` を動かし、
**この file の期待値は自動で追随します**（数をべた書きしていません）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("eta_house_rule_mod",
                                               ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)

from src import house_rule  # noqa: E402


def _measured():
    """2026-08-19 の実測（`tests/test_eta.py` と同じ点）。"""
    return dict(
        at="2026-08-19T02:30:00+00:00",
        subs_net=9,
        views_all=27_484,
        views_7d=11_002,
        views_28d=20_010,
        views_90d=22_241,
        subs_gained_28d=9,
        subs_gained_90d=11,
        long_hours_365=0.1,
        shorts_views_90d=22_222,
        views_per_video=922,
        median_views_per_video=1_092,
        videos_with_views_28d=21,
    )


def test_計画の本数は規則の本数と同じ():
    """**写しを持たないこと。** `eta` は `src/house_rule` を読むだけ。"""
    assert eta.PLAN_PUBLISH_PER_DAY == house_rule.PUBLISH_PER_DAY


def test_表にいまの計画の本数の行が出る():
    """**表から「実際に走っている本数」が消えないこと。**（2026-08-31 に踏んだ）

    `PUBLISH_SCENARIOS` だけを回すと、規則の 1本/日 は表に出ません ——
    読む側には 4本/日 が最小に見えます。`analyse()` 側と同じ和集合を回すこと。
    """
    m = _measured()
    a = eta.analyse(m)
    n = eta.PLAN_PUBLISH_PER_DAY
    assert n in a["days_subs_at"], "analyse() が計画の本数を解いていません"
    rows = [l for l in eta.report(m, a) if f"1日 {n:>3}本 公開" in l]
    assert len(rows) == 1, (
        f"密度の表に「1日 {n}本」の行がありません。"
        "`PUBLISH_SCENARIOS` だけを回していないか確かめること")
    assert eta._fmt_days(a["days_subs_at"][n]) in rows[0]


def test_その行が規則の行だと名乗る():
    """**どれが「いまの計画」かを、表の中で言うこと。** 並べるだけにしない。"""
    m = _measured()
    rows = [l for l in eta.report(m, eta.analyse(m))
            if f"1日 {eta.PLAN_PUBLISH_PER_DAY:>3}本 公開" in l]
    assert rows and "house_rule" in rows[0], rows


def test_密度の腕は規則より上へ歩けない():
    """腕の天井は「出せる本数」でも「再生が付く本数」でもなく、**いちばん低いもの**。

    規則が 1本/日 なので、`density` の腕には引き代がありません
    （`physical_caps` が ×1.0 を返す）。**ここが 1.0 を超えたら、
    軌跡は規則の外の世界を歩いています。**
    """
    sup = {"sustained_rate_per_day": 7.8, "rate_per_day": 36.5}
    caps = eta.physical_caps({"sub_rate": 0.0004}, supply=sup)
    rule = float(house_rule.PUBLISH_PER_DAY)
    dens = eta.sustained_density(sup)
    assert dens <= rule, f"続けられる密度が規則を超えています（{dens} > {rule}）"
    assert caps["density"]["factor"] <= max(1.0, rule / dens) + 1e-9, caps["density"]


def test_理由の行が規則を名指しする():
    """**裸の「引き代なし」を出さないこと**（`CLAUDE.md` の (イ)）。

    何を固定したせいでそう出たのかを、同じ行に並べること。
    """
    caps = eta.physical_caps({"sub_rate": 0.0004},
                             supply={"sustained_rate_per_day": 7.8})
    why = caps["density"]["why"]
    assert "house_rule" in why, why
    assert f"{float(house_rule.PUBLISH_PER_DAY):.0f}本/日" in why, why
