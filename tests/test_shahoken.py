"""`src/calc/shahoken.py` の**主張そのもの**を固定する（2026-08-16）。

この calc が動画で言うのは、次の4つです。
**どれも「標準報酬月額の等級で決まります」の外側にあります。**

1. **段の中は平ら** —— 月給が最大 29,999円ちがっても、厚生年金保険料は1円も変わらない
2. **境界は垂直** —— 月給 1,000円の昇給で、年 32,940円まで跳ぶ段がある
3. **昇給したのに手取りが減る組み合わせが実在する** —— 段の幅と段差の
   両方を掛け合わせないと出てこないので、**等級表のどこにも載っていません**
4. **取り返す年数は32段すべて 16.7年で、1段も外れない** ——
   本人負担 9.15% ÷ 給付乗率 0.5481% に約分され、標準報酬月額の跳びが消えるため

**`check_tables()` が緑であることは、ここでは証拠になりません。**
`check_tables()` は自分自身を呼んで自分を確かめており、**式や表を壊したときに
本当に落ちるか**は、外から壊してみないと分かりません
（`tests/test_calc_checks.py` と同じ考え方。故障注入で確かめる）。

## とくに `ANCHORS` は、ここで壊して確かめる値打ちがあります

等級表の中ほど（4〜18・20〜30等級）は**公表資料の全表を取れていません。**
取れたのは8点で、**境界が「隣り合う標準報酬月額の中点」であることは
その8点すべてで合っています。** 逆に言えば、**中ほどの1段を書き間違えても、
両端と中点の規則だけでは気づけません** —— 気づけるのは `ANCHORS` だけです。

だから「`ANCHORS` が実際に落とすか」を検査します。**落ちない `ANCHORS` は、
裏を取ったふりです。**
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calc import _checks, shahoken  # noqa: E402


def test_制度の値の検査は通る():
    shahoken.check_tables()


# ---- 制度の値（法令が名指ししているもの）------------------------------------

def test_保険料率は法律で固定された値():
    assert shahoken.RATE == 0.183
    assert shahoken.HALF == 0.0915          # 会社と本人で半分ずつ


def test_等級は32段で両端が公表値():
    assert len(shahoken.GRADES) == 32
    assert shahoken.GRADES[0] == 88_000
    assert shahoken.GRADES[-1] == 650_000


def test_境界は隣り合う標準報酬月額の中点():
    """**規則そのもの。** 8点で照合してあるが、規則が壊れたらここで落ちる。"""
    for i in range(1, len(shahoken.GRADES) - 1):
        low, high = shahoken.bounds(i)
        assert low == (shahoken.GRADES[i - 1] + shahoken.GRADES[i]) // 2
        assert high == (shahoken.GRADES[i] + shahoken.GRADES[i + 1]) // 2


def test_公表資料で読んだ8点は導いた境界と一致する():
    """`ANCHORS` は8点。**端・低い側・中ほど・高い側に散らしてある。**"""
    assert len(shahoken.ANCHORS) == 8
    for no, std, low, high in shahoken.ANCHORS:
        i = no - 1
        assert shahoken.GRADES[i] == std
        assert shahoken.bounds(i) == (low, high)


# ---- 故障注入。**壊したときに落ちること** -----------------------------------

def test_中ほどの等級を1段書き間違えるとANCHORSが落とす(monkeypatch):
    """**これがこの calc でいちばん高い検査です。**

    中ほどの等級は公表資料の全表を取れていないので、思い出しで書いています。
    **1段ずれても、両端と中点の規則だけでは気づけません。**
    ずらすのは 19等級の隣（18等級 280,000 → 281,000）——
    こうすると 19等級の下限が 290,000 から 290,500 に動き、
    **`ANCHORS` の19等級の点が外れます。**
    """
    broken = list(shahoken.GRADES)
    broken[17] = 281_000                     # 18等級を 280,000 から1,000円ずらす
    monkeypatch.setattr(shahoken, "GRADES", broken)
    with pytest.raises(_checks.TableError, match="報酬月額の範囲が公表資料と合いません"):
        shahoken.check_tables()


def test_等級を1段落とすと段数の検査が落ちる(monkeypatch):
    monkeypatch.setattr(shahoken, "GRADES", shahoken.GRADES[:-1])
    with pytest.raises(_checks.TableError):
        shahoken.check_tables()


def test_料率を動かすと法定値の検査が落ちる(monkeypatch):
    monkeypatch.setattr(shahoken, "RATE", 0.18)
    with pytest.raises(_checks.TableError, match="厚生年金保険料率"):
        shahoken.check_tables()


def test_給付乗率を動かすと取り返す年数の主張が落ちる(monkeypatch):
    """**「32段すべてで16.7年」は画面に出る主張なので、検査が要ります。**"""
    monkeypatch.setattr(shahoken, "BENEFIT_MULT", 6.0 / 1000)
    with pytest.raises(_checks.TableError, match="報酬比例部分の給付乗率"):
        shahoken.check_tables()


def test_等級を降順に入れると昇順の検査が落ちる(monkeypatch):
    monkeypatch.setattr(shahoken, "GRADES", list(reversed(shahoken.GRADES)))
    with pytest.raises(_checks.TableError):
        shahoken.check_tables()


# ---- 主張1: 段の中は平ら ----------------------------------------------------

def test_同じ等級の中では月給が動いても保険料が1円も変わらない():
    """20等級は 310,000〜329,999円。**19,999円ちがっても同じ。**"""
    assert shahoken.grade_of(310_000) == 320_000
    assert shahoken.grade_of(329_999) == 320_000
    assert shahoken.premium(310_000) == shahoken.premium(329_999)


def test_いちばん広い平らな区間は約3万円():
    widest = max(shahoken.flat_bands(), key=lambda r: r["同じ保険料の幅"])
    assert widest["同じ保険料の幅"] == 29_999
    # 24等級（410,000円）から上は 30,000円刻みなので、そこが最初に来る
    assert widest["等級"] == 24


# ---- 主張2: 境界は垂直 ------------------------------------------------------

def test_境界の1円で保険料が跳ぶ():
    """309,999円 → 310,000円 で標準報酬月額が 300,000 → 320,000 に跳ぶ。"""
    assert shahoken.grade_of(309_999) == 300_000
    assert shahoken.grade_of(310_000) == 320_000
    diff = shahoken.premium(310_000) - shahoken.premium(309_999)
    assert diff == 1_830                     # 20,000円 × 9.15%
    assert diff * 12 == 21_960


def test_年の列は本当に12倍():
    """**taishoku.py と同じ壊れ方（嘘が見出しの側）を、ここでも塞いでいる。**"""
    for row in shahoken.steps():
        assert row["保険料の増(年)"] == row["保険料の増(月)"] * 12


def test_上限と下限では張り付く():
    """65万円を超えても増えない。**頭打ちは制度の側の事実。**"""
    assert shahoken.premium(650_000) == shahoken.premium(2_000_000)
    assert shahoken.premium(88_000) == shahoken.premium(10_000)


# ---- 主張3: 昇給したのに減る ------------------------------------------------

def test_昇給で手取りが減る組み合わせが実在する():
    """**在ることが動画の前提。** 0件ならこの題材は成立しない。"""
    neg = shahoken.raise_is_negative()
    assert neg, "1件も出ていない"
    for row in neg:
        assert row["差引(年)"] < 0
        assert row["保険料の増(年)"] > row["昇給(年)"]


def test_いちばん損な境界は年2万940円のマイナス():
    """月給 394,000 → 395,000円。段差30,000円は昇給12,000円を大きく超える。"""
    worst = min(shahoken.raise_is_negative(), key=lambda r: r["差引(年)"])
    assert worst["昇給前の月給"] == 394_000
    assert worst["昇給後の月給"] == 395_000
    assert worst["昇給(年)"] == 12_000
    assert worst["保険料の増(年)"] == 32_940
    assert worst["差引(年)"] == -20_940


def test_昇給額を上げると損な境界は減る():
    """**しきい値の向き。** 昇給が大きければ段差を飲み込める。"""
    small = len(shahoken.raise_is_negative(1_000))
    large = len(shahoken.raise_is_negative(3_000))
    assert large < small


# ---- 主張4: 取り返す年数は定数 ----------------------------------------------

def test_取り返す年数は32段すべて同じ():
    yrs = {row["取り返す年数"] for row in shahoken.payback_table()}
    assert len(yrs) == 1


def test_取り返す年数は率の比に約分される():
    """**なぜ定数なのかを式で押さえる。** 偶然そう見えているのではない。

    保険料の増  = Δ標準報酬月額 × 9.15%   × 月数
    年金の増    = Δ標準報酬月額 × 0.5481% × 月数
    → 比 = 9.15 ÷ 0.5481。**Δ標準報酬月額と月数が消える。**
    """
    yrs = shahoken.payback_table()[0]["取り返す年数"]
    assert yrs == round(shahoken.HALF / shahoken.BENEFIT_MULT, 1) == 16.7


def test_年金が増える向きは正():
    """**「損」だけ出すと誤情報になる。** 段が上がれば将来の年金は増える。"""
    p = shahoken.payback(309_000, 310_000)
    assert p["標準報酬月額(前)"] == 300_000
    assert p["標準報酬月額(後)"] == 320_000
    assert p["年金の増(年・生涯)"] > 0
    assert p["取り返す年数"] > 0


# ---- 前提 -------------------------------------------------------------------

def test_前提に健康保険を外した理由が入っている():
    """**入れなかったものも書く**（前提の置き方そのものが独自の視点）。"""
    joined = "".join(shahoken.ASSUMPTIONS)
    assert "健康保険" in joined
    assert "都道府県" in joined              # 外した理由
    assert "9.15" in joined                  # 本人負担の率
    assert "賞与" in joined                  # 入れていないもの
