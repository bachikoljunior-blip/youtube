"""「いちばん多くもらえる開始年齢」まわりの検査（2026-08-17 に足した）。

ここで見ているのは**節の答えそのもの**です。既存の5節は「65歳と比べて、いつ
追いつくか」で、比べる相手が固定でした。新しい節は**181通りから選ぶ**ので、
壊れ方も違います —— 数え上げが1か所ずれても、それらしい年齢が出てしまう。

だから**独立な2つの道で同じ数字に着くこと**を要求します。

    数え上げ    `best_start()` が181通りを全部評価して最大を選ぶ
    式          `defer_one_more_month()` の「倍率 ÷ 0.007 ＋ 1」

この2つは実装を共有していません。**一致しなければ、どちらかが壊れています。**
"""
from __future__ import annotations

import math

import pytest

from src.calc import nenkin


def test_寿命を長く見るほど最適な開始は後ろへ動く():
    """単調性。ここが崩れる表は、山の形そのものが壊れています。"""
    bests = [nenkin.best_start(um) for um in range(65 * 12, 100 * 12, 2)]
    for a, b in zip(bests, bests[1:]):
        assert b >= a, (a, b)


def test_最適は端に張り付かない():
    """**85歳まで生きる想定で、最適が60歳でも75歳でもないこと。**

    節の主題は「端はめったに最適にならない」です。ここが端に張り付く表に
    なったら、節の文言ごと嘘になります。
    """
    m = nenkin.best_start(85 * 12)
    assert -60 < m < 120, m
    assert nenkin._age_text(65 * 12 + m) == "69歳1か月"


def test_最適が飛ぶ場所は1か所で_4年以上飛ぶ():
    jumps = nenkin.optimum_jumps()
    assert len(jumps) == 1, jumps
    assert jumps[0]["飛ぶ幅_月"] >= 48, jumps
    # 飛ぶ前後で、寿命の見込みは**1か月しか違わない**。ここが節の値打ち
    assert jumps[0]["寿命の差_月"] == 1


def test_数え上げと式が同じ答えに着く():
    """`best_start` の切り替わりが、限界の1か月の式と一致すること。

    ある寿命 `T` で、開始 `m+1` が `m` を追い抜くのは
    「`m` から数えて 倍率÷0.007＋1 か月後」。**数え上げ側はこの式を知りません。**
    """
    for m in (0, 12, 36, 60, 96, 119):
        want = 65 * 12 + m + math.ceil(nenkin.rate_for(m) / nenkin.RATE_UP_PER_MONTH + 1)
        # その寿命では m+1 が m 以上、1か月手前では m のほうが多い
        assert nenkin.lifetime(m + 1, 180.0, want) >= nenkin.lifetime(m, 180.0, want)
        assert nenkin.lifetime(m + 1, 180.0, want - 1) < nenkin.lifetime(m, 180.0, want - 1)


def test_繰上げの1か月のほうが高くつく():
    """同じ「1か月」でも、向きで値段が違う（0.007 対 0.004）。"""
    defer = nenkin.defer_one_more_month()[0]["取り返すのに_月"]
    advance = nenkin.advance_one_more_month()[0]["払い終わるまで_月"]
    assert advance > defer * 1.5, (defer, advance)
    # 繰上げの表では、年額は**減る**。符号を落とすと逆の意味になる
    assert all(r["1か月早めると年額_円"] < 0 for r in nenkin.advance_one_more_month())


def test_年額を変えても取り返しの月数は動かない():
    """式の上で年額は約分で消えます。**消えていなければ、どこかに残っています。**"""
    a = [r["取り返すのに_月"] for r in nenkin.defer_one_more_month(180.0)]
    b = [r["取り返すのに_月"] for r in nenkin.defer_one_more_month(90.0)]
    assert a == b


def test_lifetime_net_は_lifetime_の言い換えでしかない():
    """入口を1つにまとめた（2026-08-17）。**式が2本あると片方だけ直せます。**"""
    for m in (-60, -12, 0, 24, 120):
        assert nenkin.lifetime_net(m, 180.0, 85) == pytest.approx(
            nenkin.lifetime(m, 180.0, 85 * 12, net=True))


# --------------------------------------------------------------------------
# 故障注入。**壊したときに `check_tables()` が落ちること**を確かめる。
# --------------------------------------------------------------------------

# **壊す場所を選び直しました**（2026-08-17）。最初はここで増額率・減額率そのものを
# 書き換えていましたが、**2つとも別の検査が先に落ちていました** ——
# 冒頭の「法令の端の値」（70歳で1.42、60歳で0.76）が率を釘で留めているので、
# 率を触った時点でそこに当たります。`pytest.raises(ValueError)` だけで書いていた
# あいだ、この2件は**緑なのに、守るはずの検査を一度も通っていませんでした。**
# だから `match=` を必ず付けること。そして壊すのは、**その検査だけが見ている側**です。

def test_故障注入_探索を繰下げ側だけにすると落ちる(monkeypatch):
    """繰上げを候補から外すと山が1つになり、**飛びが消えます。**

    飛びは「節そのもの」なので、消えたまま数字を出させない。
    """
    monkeypatch.setattr(nenkin, "MIN_ADVANCE_AGE", nenkin.BASE_AGE)
    with pytest.raises(ValueError, match="飛ぶところが1つもありません"):
        nenkin.check_tables()


def test_故障注入_繰下げの上限を70歳にすると落ちる(monkeypatch):
    """上限が70歳なら、**その端は86歳10か月で最適**になります。

    「端はめったに最適にならない」が節の主題なので、
    端が手前に来た表を**黙って出させない**（文言ごと見直すべき場面）。
    """
    monkeypatch.setattr(nenkin, "MAX_DEFER_AGE", 70)
    with pytest.raises(ValueError, match="90歳前で最適"):
        nenkin.check_tables()
