"""**engaged で測っていない実験に、engaged の当てっこを出さないこと。**

## なぜ要るか（2026-08-27・最適化の回。**同じ穴の4件目**）

`src/ab_power.py` の当てっこは、**実データ 90本の engaged 比率**を
ブートストラップして作っています。`scripts/ab_split.py --outlook` は
それを**全部の実験に同じ形で**当てていました。

実測 2026-08-27、`request_form`（測るのは**登録**・床 72本）にこう出ていました::

    片群 72本で 1.3倍は当てられます（**要る本数は 25本**）

床 72本 は `src/judgeable.MEMBER_SOURCES` が**登録率 0.0318%**
（3,066再生に1人）から引いた数です。25本 ＝ 約 10,500再生 ＝ **期待 3.3人**で、
**効きが2倍でも見分けられません。**

**「72は過剰、25でよい」と読めるこの1行が危ないのは、下流の形のせいです**:

    falsified_if   「上回らなければ外れ（同点も外れ）」
    next_if_false  外れたら**腕ごと畳む**

つまり**見分けられなかっただけの実験が、効かない実験として閉じます。**
そして `request_form` の腕は `sub_rate` —— `scripts/eta.py --alloc` が
3回 続けて「次の1件はここ」と名指ししている腕で、台帳で唯一
桁がちがう前提（長尺の登録率）と同じ腕です。

**同じ穴は3回 直っています**（`src/ab_split.floor_of()` の註）:
`ab_split.py` の床・`deadline_check.py` の床・`src/watches._k_ab_group`。
**どれも「`MIN_PER_GROUP` を全部に当てていた」**で、
**4件目がここ**（当てっこの側）でした。
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from src import ab_power, ab_split


JST = timezone(timedelta(hours=9))


def test_登録で測る実験は要る本数を出さないこと():
    v = ab_power.verdict(72, values=[10.0, 20.0, 30.0, 40.0, 50.0], metric="登録")
    assert v is not None
    text = "\n".join(v.lines())
    # **見張るのは「数を名指しした2つの枝」だけ**です。註の地の文に
    #     「要る本数」の4字が出るのは構いません（数を出していないので）。
    assert "（要る本数は" not in text, (
        "**engaged の当てっこから出した本数を、登録の実験に出しています。**\n" + text)
    assert "要ります。" not in text, (
        "**足りないほうの枝も、engaged の本数で言っています。**\n" + text)
    assert "当てる率" not in text, (
        "**検出力そのものが engaged のものです。**\n" + text)
    assert "登録" in text and "engaged ではありません" in text, (
        "何が違うのかを言っていません:\n" + text)
    assert "next_if_false" in text, (
        "**床を下げたときに何が起きるか**を言っていません。"
        "見分けられなかっただけの実験が、腕ごと畳まれます")


def test_engaged_で測る実験は今までどおり出すこと():
    """**黙らせるのが目的ではありません。** 当たる実験では今までの行が要ります。"""
    v = ab_power.verdict(16, values=[10.0, 20.0, 30.0, 40.0, 50.0])
    assert v is not None
    text = "\n".join(v.lines())
    assert "engaged 比率から" in text, text
    assert "当てる率" in text, text


def test_request_form_だけが登録で測ると宣言していること():
    """**宣言の場所は1つ**（`Experiment.metric`）。増えたらここを直すこと。"""
    got = {name: e.metric for name, e in ab_split.EXPERIMENTS.items()}
    assert got.get("request_form") == "登録", (
        f"`request_form` は登録で測ります（床 72本 の出どころ）: {got}")
    for name, m in got.items():
        if name != "request_form":
            assert m == "engaged", f"{name} の metric が変わっています: {got}"


def test_実物の出力に_要る本数_が混ざらないこと():
    """**実データで**（API 0単位）。作り物だけで直したことにしないこと。"""
    text = ab_split.report()
    block = text.split("=== request_form")
    assert len(block) == 2, "request_form の節が出ていません"
    # **節の切れ目は行頭の `=== `** です。見出しの行末にも `===` が付くので、
    #     素の `split("===")` だと見出しの残りだけを見て通ってしまいます。
    body = block[1].split("\n=== ")[0]
    assert "（要る本数は" not in body and "要ります。" not in body, (
        "**実物の request_form の節に、engaged の要る本数が出ています。**\n" + body)
    assert "engaged ではありません" in body, (
        "**実物のほうに註が出ていません。**\n" + body)


def test_metric_の既定は_engaged_であること():
    """新しい実験を足した回が、**黙って engaged 扱いになる**ほうが安全です。

    逆（既定を「不明」にして全部 黙らせる）にすると、当たっている実験の
    検出力の行まで消え、**床を上げた 08/20 の根拠が読めなくなります。**
    """
    e = ab_split.Experiment(
        name="x", split=lambda t: "a", treated="a", control="b",
        landed=datetime(2026, 8, 1, tzinfo=JST), deadline=date(2026, 9, 1))
    assert e.metric == "engaged"
    assert ab_power.Verdict(
        sample=5, n_per_group=16, ratio=1.3, null_median=0.5,
        null_ranksum=0.2, power=0.8, need_n=16).metric == "engaged"
