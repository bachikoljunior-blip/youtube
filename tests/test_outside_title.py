"""`OUTSIDE_LONG_RULE` の**4つ目の脚**（題とサムネ）を数える口の検査。

規則は (1) 冒頭・(2) 章・(3) 締め・**(4) 題とサムネ** の4つを命じています。
(1) は 09-03 に、(2)(3) は 09-04 12:16 に数える口が入り、**(4) だけが文章の指示のまま**
残っていました。理由は同じ ——「文章の指示は守られない（`generate()` の実測）ので、数える」。

**この検査が押さえているのは、直した所より「黙らせないほう」です。**
実物 3本（`Ec-j1-W4nqw` / `1huadpEk6HY` / `6PKux5HNnUE`）が**3本とも外れていた**ので、
「実物が全部 通る」を検査にすると、この口はいつでも黙れます。
だから**外れている中身で鳴ること**を先に押さえます。
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import script_writer as sw

ROOT = Path(__file__).resolve().parents[1]


def _script(**kw):
    #: **`title` は 2026-09-04 20:2x に `【年金の受け取り方】` から替えました。**
    #: あれは規則の本文が例に挙げていた形ですが、**題材そのもの**で、本文の
    #: 「先頭に【 】で**相手か場面**」と逆を向いていました（(4a2)・
    #: `src/script_writer._OUTSIDE_BRACKET_WHO_RE` の註に外の帯の実測）。
    #: **ここを題材の【 】に戻さないこと** —— 戻すと「規則どおり」の見本が
    #: 規則に反した形になり、(4a2) は下の検査からは見えなくなります。
    base = {
        "title": "【65歳の前に】年240万円変わる どれを選ぶか",
        "thumbnail_line1": "生涯で240万円",
        "thumbnail_line2": "何歳から受け取るか",
    }
    base.update(kw)
    return base


def test_規則どおりの題とサムネは何も言わない():
    assert sw.outside_title_problems(_script()) == []


def test_サムネに金額が無いと鳴る():
    out = sw.outside_title_problems(
        _script(thumbnail_line1="最適が54か月飛ぶ", thumbnail_line2="何歳から受け取るか"))
    assert len(out) == 1
    assert "金額が無い" in out[0]


def test_か月と歳は金額として数えない():
    """**ここが 09/05 の1本が落ちた所**（`Ec-j1-W4nqw`）。

    「54か月」「69歳7か月」は計算出力の数字ですが、規則が命じているのは *金額* です。
    ここを緩めると、この口は 09/05 の本を黙って通します。
    """
    assert sw._OUTSIDE_MONEY_RE.search("最適が54か月飛ぶ") is None
    assert sw._OUTSIDE_MONEY_RE.search("69歳7か月") is None
    assert sw._OUTSIDE_MONEY_RE.search("年54万円増える") is not None
    assert sw._OUTSIDE_MONEY_RE.search("+2,476,950円") is not None


def test_サムネに判断の語が無いと鳴る():
    """**2026-09-04 23:0x に、当てる語を帯で測り直しました**（`_OUTSIDE_DECIDE_RE` の註）。

    前の版はここに「働く年金受給者」を置いて「1件 鳴る」と書いていました。
    **帯 335本 で数えたら、その行こそが いちばん強い特徴**でした ——
    相手の名指し（受給者・◯◯歳以上・の方へ）は 中央 525,475回 対 6,023回 ＝ **×87.2**。
    いま鳴らすのは、**判断の語も 場面も 相手も 無い行**です。
    """
    out = sw.outside_title_problems(
        _script(thumbnail_line1="年金の受け取り方", thumbnail_line2="年54万円増える"))
    assert len(out) == 1
    assert "判断の語が無い" in out[0]


def test_帯で強い特徴は判断の語として通る():
    """**外の帯 335本 で測った2つ**（`_OUTSIDE_DECIDE_RE` の註に表）。

        相手の名指し  中央 525,475回 対 6,023回 = ×87.2（n=26）
        場面（年・改正） 中央 233,558回 対 8,421回 = ×27.7（n=47）

    どちらも、前の版では「判断の語が無い」で落ちていました。
    **落としていたのは、帯でいちばん取れている作りのほうです。**
    """
    assert sw.outside_title_problems(
        _script(thumbnail_line1="働く年金受給者", thumbnail_line2="年54万円増える")) == []
    assert sw.outside_title_problems(
        _script(thumbnail_line1="2026年4月から", thumbnail_line2="年54万円増える")) == []


def test_帯で当たらない語は広げていない():
    """**緩めた向きは、測った2つだけ**（何でも通す口にしないこと）。"""
    out = sw.outside_title_problems(
        _script(thumbnail_line1="制度のしくみ", thumbnail_line2="年54万円増える"))
    assert any("判断の語が無い" in p for p in out)


def test_題が括弧で始まらないと鳴る():
    out = sw.outside_title_problems(_script(title="65歳の前に 年240万円変わる どれを選ぶか"))
    assert any("【 】で始まっていない" in p for p in out)


def test_題材を角括弧に入れると鳴る():
    """(4a2)（2026-09-04 20:2x）。**規則の本文の例そのものが逆を向いていました。**

    本文は「先頭に【 】で相手か場面（例:【65歳の前に】**【年金の受け取り方】**）」で、
    後ろはその動画の題材そのものです。数える口は `title.startswith("【")` だけだったので、
    outside_long の実物 3本のうち 2本（`Ec-j1-W4nqw`・`e6sLHLmPhrk`）がこの例を写して
    `【年金の受け取り方】…何歳から受け取るか` になりました（**【 】の中と本文で「受け取」が二重**）。

    外の帯の実測と覆る条件は `tests/test_outside_title_bracket.py` に在ります。
    """
    out = sw.outside_title_problems(
        _script(title="【年金の受け取り方】年240万円変わる どれを選ぶか"))
    assert len(out) == 1, out
    assert "相手でも場面でもない" in out[0]
    # 本文の例が (4a2) と同じ向きであること（例を戻したら赤になる）
    assert "【年金の受け取り方】" not in sw.OUTSIDE_LONG_RULE


def test_題が長すぎると鳴る():
    long_title = "【65歳の前に】" + "あ" * (sw.OUTSIDE_TITLE_MAX + 1)
    out = sw.outside_title_problems(_script(title=long_title))
    assert any("文字以内" in p for p in out)


def test_題が無い台本には何も言わない():
    """読めないものは通す（`outside_body_problems` と同じ姿勢）。"""
    assert sw.outside_title_problems({"thumbnail_line1": "あ"}) == []


def test_煽りの語は数えない():
    """**わざと数えていない脚**（`outside_title_problems` の docstring）。

    規則の本文は「『大損』のような煽りの語は使わない」と書き、同じ規則を測っている
    前提「外の作り方を写した長尺」の claim は「題は【緊急解説／知らないと損】＋…」と書いて
    **逆を向いています。** どちらへ倒すかは中身の方針の話なので、機械は数えません。
    **倒れたらこの検査を書き換えること。**
    """
    assert sw.outside_title_problems(
        _script(title="【知らないと損】年240万円変わる どれを選ぶか")) == []


@pytest.mark.parametrize("vid", ["1huadpEk6HY", "6PKux5HNnUE"])
def test_公開ずみのoutside_long2本は帯の特徴を持っている(vid):
    """**この検査は 2026-09-04 23:0x に向きが変わりました。実測で変えています。**

    前の版は「この2本は『判断の語が無い』で外れたままが正」と書いていました。
    **帯 335本 を撃って数えたら、外していたほうが誤りでした** ——
    2本のサムネは `働く年金受給者`（相手の名指し・**×87.2**）と
    `2026年4月からルール変更`（場面・**×27.7**）で、
    **帯でいちばん取れている2つの特徴を、どちらも持っています。**
    落とした理由の「判断の語」は、帯 335本 の **6本（1.8%）**にしか在りません
    （`_OUTSIDE_DECIDE_RE` の註に表と出どころ）。

    **＝ この脚は、帯の強い側を落として、弱い側を通していました。**
    ここが赤くなったら、`_OUTSIDE_DECIDE_RE` を帯で測り直すこと
    （`niche_ceiling.corpus_rows("long")`・撃たずに読めます・0単位）。
    """
    f = ROOT / "data" / "critique_queue" / f"{vid}.script.json"
    if not f.exists():
        pytest.skip(f"控えがありません: {f}")
    out = sw.outside_title_problems(json.loads(f.read_text(encoding="utf-8")))
    assert not any("判断の語が無い" in p for p in out), \
        f"{vid} のサムネは 相手の名指し と 場面 を持っています（帯で ×87.2 と ×27.7）"


def test_outside_longの枝から呼ばれている():
    """**数えるだけで配線しない**のが、(2)(3) を足す前の (1) の姿でした。"""
    src = (ROOT / "src" / "script_writer.py").read_text(encoding="utf-8")
    i = src.index("outside_body_problems(script)")
    assert "outside_title_problems(script)" in src[i:i + 600]
