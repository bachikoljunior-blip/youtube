"""**「まだ数えきっていない形」を、天井の逃げ先として名指してよいか。**

## なぜ要るか（2026-09-01・最適化の回に実測して足した）

`scripts/eta.py` の頭の3行に、2026-08-31 から こう出ていました ——

    → **その天井 ×8.82 を、ショートの中で探さないこと。**
      長尺の1本あたり再生は、天井ではなく**まだ1回も数えきっていない**側です。
      **数えきるのは API 0単位・新しく1本も出さずに進みます。**

**「未計数」から「だから大きいかもしれない」へ、測らずに渡っています。**
同じ回の `src/form_record.per_video_best()` が、渡った先の数を出しています ——

    ショート  記録 1,891回 × 打ち切り補正 1.00 → `best_settled` **1,891**（settled）
    長尺      記録   156回 × 打ち切り補正 2.00 → `best_settled`   **312**（未settled）

`best_settled` は「**伸びきったことにして**、いま在る記録を最大まで数えた」値です。
**長尺を数えきった側の上限が 312**で、天井 1,891 の **×0.17** ——
オーナー規則2（無限大にして 0日 なら、そこは律速ではない）が、この枝に掛かります。
同じ日に `config/hypotheses.yaml` の `長尺1本あたり-13本` も
**外れで閉じています**（中央値 4回 対 門 80回・符号検定 p=0.0001）。

**台帳が閉じた道を、画面の頭が毎周 名指ししていました。**
頭の3行しか読まれない手順（`CLAUDE.md`）では、これは「次の一手」に見えます。

## もう1つ、同じ回に見つけた形

`_long_ceiling_lines()` は `long_ceiling.lines(m)` と呼んでいましたが、
`long_ceiling.lines()` は**引数を取りません**。毎周 `TypeError` が出て、
すぐ下の `except Exception` が飲み、**画面には空が出ていました** ——
「判定できます。外れです（p=0.0001）」の4行が **1度も印字されないまま**
台帳の側だけが閉じています。**回を止めない `except` は、こう効きます。**

## ここで固定するもの

1. `_escape_form()` は、**数えきった側の上限が天井を超えるときだけ** `escapes` を真にする
2. `_long_ceiling_lines()` は**空を返さない**（本物のデータで撃って、行が出ること）
3. 台帳の名前は**写さない**（`long_ceiling.KEY` から読む）

## 覆る条件

`best_settled` は打ち切り補正込みで毎回 数え直します。長尺の記録が伸びて
天井を超えたら `escapes` は自分で真に戻り、元の招待の行が戻ります。
**この検査は数を固定しません**（下の 1,891／312 は作った標本です）。
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "eta_escape_form_mod", ROOT / "scripts" / "eta.py")
eta = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eta)


def _recs(long_best_settled: float):
    return {
        "ショート": {"best": 1891, "best_settled": 1891.0, "settled": True},
        "長尺": {"best": 156, "best_settled": long_best_settled, "settled": False},
    }


def test_数えきっても天井に届かない形は逃げ先ではない():
    e = eta._escape_form(_recs(312.0))
    assert e["form"] == "長尺"
    assert e["cap"] == 1891.0
    assert e["top"] == 312.0
    assert e["escapes"] is False, (
        "**未計数であることは、大きいことではありません。** "
        "数えきった側の上限（312）が天井（1,891）に届かないなら、"
        "そこを数えても天井は上がりません")


def test_数えきった側が天井を超える形だけが逃げ先():
    e = eta._escape_form(_recs(3000.0))
    assert e["escapes"] is True
    assert e["over"] > 1.0


def test_settled_な形しか無ければ逃げ先は無い():
    e = eta._escape_form({"ショート": {"best": 1891, "best_settled": 1891.0,
                                       "settled": True}})
    assert e["form"] is None
    assert e["escapes"] is False


def test_読めなくても回を止めない():
    e = eta._escape_form({})
    assert e["escapes"] is False
    assert e["form"] is None


def test_長尺の判定の行が空で落ちない():
    """**`except` が飲んだ `TypeError` を、ここで見つける。**

    実データで撃ちます（`data/views.jsonl`・API 0単位）。長尺の読みが
    1件も無い環境では `long_ceiling.lines()` 自身が「**測っていません**」を
    出すので、**どちらにせよ空にはなりません。**
    """
    out = eta._long_ceiling_lines({})
    assert out, ("`long_ceiling.lines()` の行が1本も出ていません —— "
                 "呼び方が合っていない（引数を渡している）か、例外が飲まれています")


def test_台帳の名前は写さず正本から読む():
    from src import long_ceiling
    assert eta._long_ceiling_key() == long_ceiling.KEY
    src = (ROOT / "scripts" / "eta.py").read_text(encoding="utf-8")
    # **印字される文字列の中に古い名前を残さないこと。**
    #     註と docstring は履歴として残してよい（**なぜ変えたか**が消えると、
    #     次に来た側が惰性で戻します）。見るのは f 文字列の行だけです。
    printed = [ln for ln in src.splitlines()
               if "長尺1本あたり-30本" in ln and ('f"' in ln or "f'" in ln)]
    assert not printed, printed


# ===================================================================
# **比べる相手が居ない回**（2026-09-02 に足した。**この日、道具が落ちました**）
#
#   `python scripts/eta.py` が、手順（§2.6）の「最初の2手」で落ちました ——
#
#       TypeError: unsupported format string passed to NoneType.__format__
#
#   `_escape_form()` の `over` は `cap` が 0 のとき `None` を返します。
#   `cap` は「**伸びきった形の記録の最大**」で、この日は**ショートまで
#   `settled: False`** に落ちたので（`data/views.jsonl` の打ち切り補正が
#   効く齢に届かなくなった）、伸びきった形が0 ＝ `cap` が 0 になりました。
#   下の枝は `x{over:.2f}` を刷ろうとします。
#
#   **`escapes` の偽には2つの意味が混ざっていました** ——
#     (1) 比べて、逃げ先のほうが低かった
#     (2) **比べる相手が居ない**（`cap` が 0）
#   画面は (2) を (1) の文（「この回に数え直して、逃げ先のほうが低いと出ました」）で
#   刷ろうとして落ちます。**落ちなかったとしても、それは嘘です。**
#
#   ここで固定するのは3つ:
#     1. `comparable` が、その2つを分ける
#     2. `over` は `cap` が 0 のとき `None` のまま（0.0 に丸めない ＝「x0.00」は嘘）
#     3. `_escape_lines()` が**どの形でも落ちない**（`headline()` の外へ出したので撃てます）
# ===================================================================


def test_伸びきった形が1つも無ければ比べられない():
    e = eta._escape_form({
        "ショート": {"best": 1891, "best_settled": 1891.0, "settled": False},
        "長尺": {"best": 191, "best_settled": 525.25, "settled": False},
    })
    assert e["comparable"] is False, (
        "**伸びきった形が1つも無い回です。** `cap` が 0 なので、"
        "低いとも高いとも言えません")
    assert e["escapes"] is False
    assert e["over"] is None, "**0.0 に丸めないこと** ——「x0.00」は測った数ではありません"
    assert e["all_unsettled"] == ["ショート", "長尺"]


def test_比べられる回は_comparable_が真():
    e = eta._escape_form(_recs(312.0))
    assert e["comparable"] is True
    assert e["escapes"] is False, "比べて、逃げ先のほうが低い回"


def test_逃げ先の行はどの形でも落ちない():
    """**この検査が無かったので、本物のデータでしか落ちませんでした。**"""
    pl = {"lever_hint": "per_video", "lever_need_over_cap": 21.61}
    for recs in (
        {},
        {"ショート": {"best": 1891, "best_settled": 1891.0, "settled": False},
         "長尺": {"best": 191, "best_settled": 525.25, "settled": False}},
        _recs(312.0),
        _recs(3000.0),
    ):
        orig = eta._escape_form
        eta._escape_form = lambda _r=None, _v=recs: orig(_v)
        try:
            got = eta._escape_lines(pl)
        finally:
            eta._escape_form = orig
        assert isinstance(got, list)


def test_比べられない回は低いとは言わない():
    pl = {"lever_hint": "per_video", "lever_need_over_cap": 21.61}
    orig = eta._escape_form
    eta._escape_form = lambda _r=None: orig({
        "ショート": {"best": 1891, "best_settled": 1891.0, "settled": False},
        "長尺": {"best": 191, "best_settled": 525.25, "settled": False}})
    try:
        got = "".join(eta._escape_lines(pl))
    finally:
        eta._escape_form = orig
    assert "逃げ先のほうが低いと出ました" not in got, (
        "**比べていません。** `cap` が 0 の回に「低いと出ました」と刷らないこと")
    assert "comparable: False" in got, got[:400]
    assert "比べられません" in got and "伸びきったと言える形が1つも無い" in got
    assert "ショート／長尺" in got, "**どの形が伸びきっていないか**を名前で出すこと"
