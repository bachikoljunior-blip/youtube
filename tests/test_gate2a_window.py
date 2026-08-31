"""**門2a の合格点は、門1 までの日数ではなく「門の窓」で割ること。**

## なぜ要るか（2026-08-31・最適化の回。**この回に自分で撃った数**）

`scripts/eta.LONG_HOURS_GATE` は初日から

    LONG_HOURS_GATE = 4_000          # 直近12か月・長尺のみ

と書いてあります。**「直近12か月」です。** ところが合格点を解く側
（`_long_break_even` / `_gate2_bar` / `_long_needed_per_day`）は、
その窓を1度も見ずに **門1 が通る日までの日数**で割っていました。

オーナー規則（1日1本）の下で門1 は **3,292日後**（2035年）です。
4,000時間ぶんの視聴分を 3,292日 に散らすと、**初日に積んだ視聴時間は
8年 も前に窓から落ちています。** 積んでよいのは**申請の前 365日**のぶんだけ。

実測（API 0単位）—— 要る「長尺1本あたり再生」（L=1本/日 ＝ 規則の上限）:

    形                いまの式    窓365日     ずれ
    尺4分・維持20%       91回      821回    9.0倍
    尺5分・維持40%       36回      329回    9.0倍
    尺7分・維持40%       26回      235回    9.0倍

**9.0倍 楽観**でした。前の回が**分子**で踏んだのと同じ形
（規則と単位が揃っていない）が、**分母の窓**にも在ったということです。

## これは「届かない」を増やす直しではありません

**門2a は、直したあとも いちばん近い門のままです** ——
いちばん甘い行 **235回/本** は、門2b（ショート90日1,000万 ＝ 規則の 1本/日 なら
**111,111回/本**）の **473倍 近い**。この機械の長尺の**記録は 156回/本**
（`src/form_record.py`）なので、隔たりは **×1.50**。**桁ではありません。**

規則3（「次の投稿予定までにそこで投稿する動画を改善し続ける」）が毎日 追う数が、
**6回/本 から 235回/本** に変わります。

## 覆る条件

**YouTube が窓を変えたら**取り直すこと（出どころは
`support.google.com/youtube/answer/72851` の1枚）。そのとき
`LONG_HOURS_WINDOW_DAYS` を動かせば、下の3つは自動で追います。
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("_eta_for_test", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
sys.modules["_eta_for_test"] = eta
_spec.loader.exec_module(eta)


def _a(days_to_gate1: float = 3292.0) -> dict:
    """**実データと同じ形**（規則 1本/日 で門1 が 3,292日後の回）。"""
    return {"long_minutes_needed": (eta.LONG_HOURS_GATE - 2.5) * 60,
            "days_subs_at": {eta.PLAN_PUBLISH_PER_DAY: days_to_gate1}}


def test_窓は門の定数と同じ12か月():
    assert eta.LONG_HOURS_WINDOW_DAYS == 365


def test_門1が窓より遠くても窓で割る():
    """**8年 かけて積んでよい門ではありません。**"""
    rows = eta._long_break_even(_a())
    got = {r["label"]: r["views"][1] for r in rows}
    # 尺7分・維持40% ＝ 2.8分/再生 → 239,850 / (1 x 365 x 2.8)
    want = (eta.LONG_HOURS_GATE - 2.5) * 60 / (1 * 365 * 2.8)
    softest = min(got.values())
    assert abs(softest - want) < 1.0, got
    assert softest > 200, (
        "門1 までの日数で割っています（9倍 楽観）。合格点=" + repr(got))


def test_門1が窓より近ければ門1のほうで割る():
    """**頭打ちであって、置き換えではありません。**"""
    near = eta._long_break_even(_a(days_to_gate1=100.0))
    far = eta._long_break_even(_a(days_to_gate1=3292.0))
    assert min(r["views"][1] for r in near) > min(r["views"][1] for r in far), (
        "門1 が 100日後 なら、365日 ぶんは積めません")


def test_裏返しの解き方も同じ窓で割る():
    """`_long_needed_per_day` だけ別の窓だと、2つの答えが 9倍 ずれます。"""
    a = _a()
    a["long_break_even"] = eta._long_break_even(a)
    # 1本あたり再生を、いちばん甘い行の合格点そのものに固定すれば L は 1.0 に出る
    softest = min(a["long_break_even"], key=lambda r: r["views"][1])
    rows = eta._long_needed_per_day(a, softest["views"][1], 3292.0)
    got = next(r["per_day"] for r in rows if r["label"] == softest["label"])
    assert abs(got - 1.0) < 0.01, (
        f"表（1本あたり再生を解く）と裏（Lを解く）が同じ窓を見ていません: L={got}")


def test_任意のLを解く道具も同じ窓で割る():
    a = _a()
    rows = eta._long_break_even(a)
    softest = min(rows, key=lambda r: r["views"][1])
    got = eta._gate2_bar(a, softest, 1.0, 3292.0)
    assert abs(got - softest["views"][1]) < 1.0, (
        f"`_gate2_bar` と `_long_break_even` が別の窓を見ています: {got}")


def test_門2bより近いまま():
    """**「届かない」を増やす直しではありません。**

    直したあとも門2a が いちばん近い門であること。ここが逆転したら、
    この機械が追うべき門そのものが変わります（そのときは JOURNAL に書くこと）。
    """
    rows = eta._long_break_even(_a())
    softest = min(r["views"][1] for r in rows)
    gate2b_per_video = eta.SHORTS_VIEWS_GATE / 90 / eta.PLAN_PUBLISH_PER_DAY
    assert softest < gate2b_per_video, (softest, gate2b_per_video)


# ======================================================================
# 記録で割った隔たり（2026-08-31 に足した）
# ======================================================================

def test_合格点を記録で割ると平均で割るより小さい():
    """**同じ隔たりを「平均」ではなく「これまでの最高」でも測ること。**

    この機械は天井の帯で既に同じ直しを済ませています —— 記録で割ったら
    いちばん近い帯が `ショート 高 ×117.9` から `長尺 お金 高 ×21.4` へ
    **入れ替わりました**。**門2a の側だけ、その直しが入っていませんでした。**

    そして規則3 が追うのは**1本**です（「次の投稿予定までにそこで投稿する
    動画を改善し続ける」）。1本が門を越えられるかを問うなら、
    **分母は平均ではなく記録**のほうが単位が合います。

    実測 2026-08-31: 合格点 235回 ／ 平均 16.0回 → ×14.7 ／
    記録 156回 → **×1.50**（9.8分の1）。

    **値はべた書きしません**（べた書きは腐ります）。縛るのは関係のほうです ——
    **記録は平均以上**なので、記録で割った隔たりが平均で割ったものを
    上回ることはありません。

    **覆る条件**: `form_record.per_video_best()` が長尺を返さない回
    （形の分かった長尺が1本も無い）は、この検査は何も言いません。
    """
    from src import form_record
    lg = (form_record.per_video_best() or {}).get("長尺")
    if not lg:
        return                          # 測っていないことを、落とす側に倒さない
    assert lg["best"] >= lg["mean"], (
        "記録が平均を下回っています（`per_video_best` の中身が壊れています）")
    rows = eta._long_break_even(_a())
    bar = min(r["views"][1] for r in rows)
    assert bar / lg["best"] <= bar / lg["mean"], (
        "記録で割った隔たりが、平均で割ったものより大きく出ています")


def test_記録が伸びきっているかを名乗る():
    """**記録が下限なら、そこから出した倍率は隔たりの『上限』です。**

    `settle.settles_at('長尺')` はどの地平でも伸びきる年齢を返しません
    （`MATURE_HOURS_BY_FORM['長尺'] = 96` で打ち切った数）。
    **名乗らないと、上限が実測として運ばれます。**
    """
    from src import form_record
    lg = (form_record.per_video_best() or {}).get("長尺")
    if not lg:
        return
    assert "settled" in lg, (
        "記録が伸びきった本のものかを名乗っていません（上限が実測として運ばれます）")
