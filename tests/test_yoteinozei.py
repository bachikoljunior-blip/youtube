"""**予定納税の表。**（2026-08-18 に新設）

`check_tables()` が守っているのは「値」で、**主張のほうは守れません。**
ここで固定するのは、docstring が言い切っている7つの主張そのものです。

**故障注入つき** —— 値を壊したときに落ちる側も見ます。片側だけでは
「この検査が効いている」とは言えません。
"""
from __future__ import annotations

import pytest

from src.calc import _checks, yoteinozei as y


def test_崖は課税所得2444150円に立つ():
    """**この表の中心。**1円の左右で、先払いが 0円と100,000円に分かれる。"""
    rows = {r["位置"]: r for r in y.cliff()}
    below, above = rows["崖の1円手前"], rows["崖のちょうど上"]
    assert above["課税所得（円）"] == 2_444_150
    assert below["課税所得（円）"] == 2_444_149
    assert above["予定納税基準額（円）"] == 150_000
    assert below["予定納税基準額（円）"] == 149_999
    assert below["先に払う合計（円）"] == 0
    assert above["先に払う合計（円）"] == 100_000
    # **1円の差で10万円**（この主張が docstring の見出し）
    assert above["課税所得（円）"] - below["課税所得（円）"] == 1


def test_崖の1円下は基準額が15万円に1円だけ足りない():
    assert y.kijun(2_444_149) == y.LINE - 1
    assert not y.hitsuyou(y.kijun(2_444_149))
    assert y.hitsuyou(y.kijun(2_444_150))


def test_増えた税は3月に3倍で来る():
    """**帯がちがっても比は 3.0倍で揃う。**3月に残るのが必ず3分の1だから。"""
    got = []
    for r in y.sangatsu():
        if r["今年の増え（パーセント）"] == 0:
            continue
        got.append(r["3月の増え（パーセント）"] / r["年税額の増え（パーセント）"])
    assert got, "増えのある行が1つも無い"
    for ratio in got:
        assert 2.95 <= ratio <= 3.05, f"3倍から外れた: {got}"


def test_3月の増えの実額():
    rows = {(r["前年の課税所得（円）"], r["今年の増え（パーセント）"]): r
            for r in y.sangatsu()}
    assert rows[(5_000_000, 10)]["年税額の増え（パーセント）"] == 17.5
    assert rows[(5_000_000, 10)]["3月の増え（パーセント）"] == 52.4
    assert rows[(8_000_000, 10)]["3月の増え（パーセント）"] == 45.8
    assert rows[(12_000_000, 10)]["3月の増え（パーセント）"] == 49.0


def test_落ちる幅は19から24パーセントで所得と一緒には動かない():
    """**上の所得ほど余裕がある、とは言えない。**速算表の段のどこに落ちるかで決まる。"""
    haba = [r["落ちる幅（パーセント）"] for r in y.haraisugi()]
    assert min(haba) == 19.1
    assert max(haba) == 24.2
    # 単調ではない（**単調なら「所得が上がるほど余裕がある」と言えてしまう**）
    assert haba != sorted(haba)
    assert haba != sorted(haba, reverse=True)


def test_減額申請の戻りは所得で3倍以上ひらく():
    per = [r["減った所得100円あたり（円）"] for r in y.genkaku()]
    assert min(per) == 7.2
    assert max(per) == 27.2
    assert round(max(per) / min(per), 2) == 3.78


def test_源泉徴収で消える線は年税額の26から95パーセント():
    rows = {r["課税所得（円）"]: r for r in y.genzen()}
    assert rows[3_000_000]["年税額に対する割合（パーセント）"] == 26.9
    assert rows[20_000_000]["年税額に対する割合（パーセント）"] == 95.2
    # **所得が上がるほど、源泉徴収では逃がしてもらえない**（ここは単調）
    warr = [rows[t]["年税額に対する割合（パーセント）"] for t in sorted(rows)]
    assert warr == sorted(warr)


def test_100円未満の切り捨ては2回で199円まで():
    rows = {r["予定納税基準額（円）"]: r for r in y.hasuu()}
    assert rows[150_000]["2回で切り捨てた額（円）"] == 0.0
    assert rows[150_299]["1回ぶん（円）"] == rows[150_000]["1回ぶん（円）"] == 50_000
    assert max(r["2回で切り捨てた額（円）"] for r in y.hasuu()) == pytest.approx(199.33, abs=0.01)


def test_復興特別所得税が崖を30850円手前に引く():
    """**3,085円の税が、100,000円の前払いを発生させている。**"""
    rows = {r["復興特別所得税"]: r for r in y.fukko_cliff()}
    assert rows["含めない"]["崖に立つ課税所得（円）"] == 2_475_000
    assert rows["含める（いまの制度）"]["崖に立つ課税所得（円）"] == 2_444_150
    assert rows["差"]["崖に立つ課税所得（円）"] == 30_850
    assert rows["差"]["そこでの基準所得税額（円）"] == 3_085
    # 32.4倍（docstring が言っている比）
    assert round(100_000 / rows["差"]["そこでの基準所得税額（円）"], 1) == 32.4


def test_先払いは基準額の3分の2を超えない():
    for k in (150_000, 200_000, 999_999, 5_000_000):
        assert y.maebarai(k) <= k * 2 / 3


# ---- 故障注入（**壊したときに落ちる側**）--------------------------------

def test_崖の判定を壊すと検査が落ちる(monkeypatch):
    monkeypatch.setattr(y, "LINE", 100_000)
    with pytest.raises(_checks.TableError):
        y.check_tables()


def test_復興特別所得税を消すと崖が動かなくなり検査が落ちる(monkeypatch):
    monkeypatch.setattr(y, "FUKKO_RATE", 0.0)
    with pytest.raises(_checks.TableError):
        y.check_tables()
    # そして崖は速算表そのものの位置に戻る
    assert y._taxable_for_kijun(y.LINE) == 2_475_000


def test_速算表を降順にすると検査が落ちる(monkeypatch):
    broken = list(reversed(y.TAX_TABLE))
    monkeypatch.setattr(y, "TAX_TABLE", broken)
    with pytest.raises(_checks.TableError):
        y.check_tables()


def test_3分の1を2分の1に変えると3分の2の不変条件が落ちる(monkeypatch):
    monkeypatch.setattr(y, "SHARE", 2)
    with pytest.raises(_checks.TableError):
        y.check_tables()
