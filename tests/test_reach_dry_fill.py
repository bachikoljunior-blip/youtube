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


# --- **描画が速くても、描くものが無ければ穴は埋まらない**（2026-08-29 に足した） ---
#
# `make_per_day` は `eta.long_supply_per_day()` ＝ `data/batch_runs.jsonl` の
# 「作れた本」で、**題材が在った日の記録**です。題材が尽きた日も、この数は
# 高いままになります（記録は過去の窓を見ているので）。
#
# 実測 2026-08-29（この検査を書いた回）::
#
#     eta._long_make_per_day()                 **9.14本/日**（7日で 64/86本）
#     supply.surfaces()['long']['stock']       **0本**
#     topic_forge --list 「7日ぶんで取れる」   **0本**
#     → 旧: 空き枠 17 ÷ 9.14 = 1.9日 <= 穴まで 15日 → **ok=True**
#            印字は「**放っておいて埋まります／その日に置きにいかないこと**」
#
# **4,000時間の門に入るのは長尺だけ**なので、これは門に直結した面について
# 「手を出すな」と言っていました。`eta._long_make_per_day()` の docstring が
# 名指ししている壊れ方（「願望で割ると『埋まります』と出て、実際には空のまま
# 公開日が来ます」）そのもので、あちらの守りは `measured: False` の枝だけでした。

REAL_PUBS = {"20260828": 11, "20260829": 12, "20260830": 5, "20260831": 7,
             "20260901": 7, "20260902": 5, "20260903": 9}
REAL_SPAN = ("20260912", "20260922", 11)
REAL_TODAY = date(2026, 8, 28)


def _real(stock):
    return reach_split.dry_fill(REAL_SPAN, REAL_PUBS, make_per_day=9.142857,
                                slots_per_day=5, today=REAL_TODAY, stock=stock)


def test_在庫が0なら_描画が速くても埋まらないと言う():
    got = _real(0)
    assert got["ok"] is False, "在庫0で『放っておいて埋まります』に戻っています"
    assert got["bound"] == "topics", "縛っている側が題材だと言えていません"
    assert got["stock"] == 0
    # 描画の側は足りている（＝『作る速さを上げろ』は誤った助言）
    assert got["reach_days"] <= got["gap_days"]
    assert got["topics_needed"] == got["open_slots"]
    assert got["topics_per_day_needed"] == got["open_slots"] / got["gap_days"]


def test_在庫が空き枠を賄えるなら_これまでどおり埋まる():
    got = _real(99)
    assert got["ok"] is True
    assert got["bound"] is None
    assert got["topics_needed"] == 0


def test_在庫がちょうど空き枠と同じなら_埋まる側():
    n = _real(None)["open_slots"]
    assert _real(n)["ok"] is True
    assert _real(n - 1)["ok"] is False
    assert _real(n - 1)["bound"] == "topics"


def test_在庫を渡さない回は_1文字も変わらない():
    # **測っていないことを、埋まる/埋まらないのどちらにも倒さない。**
    #     `src/supply.py` が読めなかった回に 0 を入れると、その回は全部
    #     「題材が無い」になります（`eta._long_stock()` は `None` を返します）。
    old = _real(None)
    assert old["ok"] is True
    assert old["bound"] is None
    assert old["stock"] is None
    assert old["topics_needed"] is None


def test_描画が足りない回は_縛っているのは描画だと言う():
    # 在庫は潤沢・描画が遅い → `bound="render"`（助言は「作る速さ」で正しい）
    got = reach_split.dry_fill(REAL_SPAN, REAL_PUBS, make_per_day=0.2,
                               slots_per_day=5, today=REAL_TODAY, stock=999)
    assert got["ok"] is False
    assert got["bound"] == "render"
    assert got["short_per_day"] and got["short_per_day"] > 0


def test_eta_は在庫を読んで渡している():
    # **配線の検査**（`stock=` を落とすと、この道具は静かに元の答えへ戻ります）
    import inspect

    import eta  # noqa: PLC0415

    src = inspect.getsource(eta._recent_surface)
    assert "stock=_long_stock()" in src, "eta が在庫を渡していません"
    assert callable(eta._long_stock)


def _note(stock):
    """`eta._gate2_surface_note()` の**印字そのもの**（註ではなく出る字を見る）。"""
    import eta  # noqa: PLC0415

    return eta._gate2_surface_note(
        318.0, 190.0, basis="実測",
        others={"dry_span": REAL_SPAN, "dry_fill": _real(stock)})


def test_題材が尽きた回の印字は_描画を直せと言わない():
    # 旧い枝は「**直す先はサムネでも題でも予定表でもなく、作る速さです**」。
    #     題材が尽きた回にこれを出すと、9.14本/日 出ている描画を速くしにいきます。
    s = _note(0)
    assert "[!]" in s, "題材が尽きた回が、注意として出ていません"
    assert "放っておいて埋まります" not in s
    assert "作る速さです" not in s, "描画を直せと言っています（律速は題材）"
    assert "題材" in s and "在庫は 0本" in s
    assert "src/calc/" in s and "topic_forge" in s, "直す先を名指ししていません"
    # **ショートで埋まると読ませないこと**（門に入るのは長尺だけ）
    assert "4,000時間" in s


def test_在庫が足りる回は_これまでどおり埋まると言い_在庫も並べる():
    s = _note(99)
    assert "放っておいて埋まります" in s
    assert "[!]" not in s
    # 「埋まります」だけで終えないこと —— 在庫0の回、ここは黙っていました
    assert "題材の在庫 99本" in s


def test_在庫が読めない回は_読めないと言う():
    s = _note(None)
    assert "放っておいて埋まります" in s
    assert "題材の在庫は読めていません" in s
