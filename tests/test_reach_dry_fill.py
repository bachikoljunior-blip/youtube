"""**予定表の「穴」は、たいてい穴ではない。**

`surface_forecast().dry_span` は「これから長尺の予約が0本の日の連なり」で、
その註は長らく「**直す先はサムネでも題でもなく、その N日 に長尺を置くこと**」
と書いていました。**それは、たいていの回で間違った手を指します。**

予約の時刻を決めているのは `uploader.next_publish_at()` だけで、
**その時刻で最初に空いている日**へ置く ＝ **手前から順に埋まります。**
だから未来の空き日は「穴」ではなく「**まだ順番が来ていない日**」で、
作りつづけていれば、その日が来る前に頭が通過します。

実測 2026-08-26（`data/uploaded.jsonl` の長尺 28本）::

    公開 08/29 [3.2 3.3 3.4 3.7日前]      公開 09/06 [10.9 11.7日前]
    公開 09/20〜10/10 [25〜45日前]          ← 1日1本 だった頃の置き方の残り
    空いているのは 09/07〜09/19 ＝ **頭と、古い残りのあいだ**

    手前の空き枠 26本 ÷ 作る速さ 2.86本/日 ＝ 9.1日 で頭が通過。
    穴の初日まで 11日 → **放っておいて埋まる**（余裕 1.9日）

**既にある本を後ろへ動かして穴を埋めると、判定が遅れるぶん必ず損します。**
"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from src import reach_split  # noqa: E402


TODAY = date(2026, 8, 26)


def test_作る速さが足りていれば_穴は自分で埋まる():
    # 実物の形（`reach_split.publishes_per_day()` 2026-08-26）
    pubs = {"20260826": 4, "20260828": 2, "20260829": 4, "20260830": 6,
            "20260831": 3, "20260901": 2, "20260902": 1, "20260903": 2,
            "20260904": 4, "20260905": 2}
    got = reach_split.dry_fill(("20260906", "20260918", 13), pubs,
                               make_per_day=2.857, slots_per_day=5, today=TODAY)
    # 11日 × 枠5 ＝ 55。**枠を超えて出した日は「借り」にしない**
    #     （08/30 は 6本 だが、`max(0, 5-6)` で 0。負にすると穴が早く埋まって見える）
    assert got["open_slots"] == 26
    assert got["gap_days"] == 11
    assert round(got["reach_days"], 2) == round(26 / 2.857, 2)
    assert got["ok"] is True
    assert got["short_per_day"] is None
    # **埋まる回でも「どこで割れるか」を返すこと**（余裕は 1.9日 しかない）
    assert round(got["need_per_day"], 2) == round(26 / 11, 2)


def test_作る速さが割れる線を下回ったら_足りない本数を言う():
    # 実物の形（`reach_split.publishes_per_day()` 2026-08-26）
    pubs = {"20260826": 4, "20260828": 2, "20260829": 4, "20260830": 6,
            "20260831": 3, "20260901": 2, "20260902": 1, "20260903": 2,
            "20260904": 4, "20260905": 2}
    got = reach_split.dry_fill(("20260906", "20260918", 13), pubs,
                               make_per_day=1.0, slots_per_day=5, today=TODAY)
    assert got["ok"] is False
    assert round(got["short_per_day"], 2) == round(26 / 11 - 1.0, 2)


def test_測っていなければ_どちらにも倒さない():
    span = ("20260906", "20260918", 13)
    assert reach_split.dry_fill(span, {}, None, 5, today=TODAY) is None
    assert reach_split.dry_fill(span, {}, 2.86, None, today=TODAY) is None
    assert reach_split.dry_fill(None, {}, 2.86, 5, today=TODAY) is None
    assert reach_split.dry_fill(span, {}, 0.0, 5, today=TODAY) is None


def test_穴が今日以前なら数えない():
    assert reach_split.dry_fill(("20260820", "20260825", 6), {}, 2.86, 5,
                                today=TODAY) is None


def test_埋まる回は_bang_を出さない():
    """**穴が自分で埋まる回に `[!]` を出さないこと。**

    `eta.flagged()` が尾へ運ぶので、`[!]` を付けたぶんだけ
    **毎周 その手を検討させます。** ここは検討する価値がありません。
    """
    import scripts.eta as eta

    fill = {"open_slots": 26, "reach_days": 9.1, "gap_days": 11, "ok": True,
            "make_per_day": 2.86, "slots_per_day": 5, "need_per_day": 2.36,
            "short_per_day": None}
    line = eta._gate2_surface_note(837.0, 178.0, basis="実測", others={
        "dry_span": ("20260906", "20260918", 13), "dry_fill": fill, "ctr": 1.44})
    assert "[!]" not in line
    assert "放っておいて埋まります" in line
    assert "その日に置きにいかないこと" in line
    assert "2.36" in line


def test_埋まらない回は_作る速さを名指しする():
    import scripts.eta as eta

    fill = {"open_slots": 40, "reach_days": 40.0, "gap_days": 11, "ok": False,
            "make_per_day": 1.0, "slots_per_day": 5, "need_per_day": 3.64,
            "short_per_day": 2.64}
    line = eta._gate2_surface_note(837.0, 178.0, basis="実測", others={
        "dry_span": ("20260906", "20260918", 13), "dry_fill": fill, "ctr": 1.44})
    assert "[!]" in line
    assert "作る速さです" in line
    assert "2.64" in line
    # **予定表を直せと言わないこと**（既にある本を後ろへ動かすのは必ず損）
    assert "その 13日 に長尺を置くこと" not in line


def test_数えていない回は_どちらにも読ませない():
    import scripts.eta as eta

    line = eta._gate2_surface_note(837.0, 178.0, basis="実測", others={
        "dry_span": ("20260906", "20260918", 13), "dry_fill": None, "ctr": 1.44})
    assert "まだ数えていません" in line
    assert "順番が来ていない日" in line


def test_作る速さは実測でしか使わない():
    """`measured: False`（＝計画値）で割ると「埋まります」と嘘が出る。"""
    import scripts.eta as eta

    real = eta.long_supply_per_day
    try:
        eta.long_supply_per_day = lambda *a, **k: {"rate": 4.0, "measured": False}
        assert eta._long_make_per_day() is None
        eta.long_supply_per_day = lambda *a, **k: {"rate": 2.86, "measured": True}
        assert round(eta._long_make_per_day(), 2) == 2.86
    finally:
        eta.long_supply_per_day = real
