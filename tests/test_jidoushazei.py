"""**自動車税の13年超重課の表。**（2026-08-18 に新設）

`check_tables()` が守っているのは「値」で、**主張のほうは守れません。**
ここで固定するのは、docstring が言い切っている7つの主張そのものです。

**故障注入つき** —— 値を壊したときに落ちる側も見ます。
"""
from __future__ import annotations

from decimal import Decimal

import pytest

from src.calc import _checks, jidoushazei as j


# ---------------------------------------------------------------- 節1・節6

def test_実効の重課率はちょうど15パーセントが2区分だけ():
    """**この表の中心。** 「おおむね15パーセント」は率ではなく実額で決まっている。"""
    rows = {r["排気量の区分"]: r for r in j.jikko_ritsu()}
    assert rows["1,000cc超1,500cc以下"]["実効の重課率（パーセント）"] == 14.7826
    assert rows["3,000cc超3,500cc以下"]["実効の重課率（パーセント）"] == 15.0
    assert rows["4,500cc超6,000cc以下"]["実効の重課率（パーセント）"] == 15.0
    exact = [r for r in j.jikko_ritsu() if r["ちょうど15パーセントか"] == "はい"]
    assert len(exact) == 2


def test_実効の重課率は区分の順に並んでいない():
    """並んでいたら「大きい車ほど重い」と言えてしまう。**言えません。**"""
    rates = [r["実効の重課率（パーセント）"] for r in j.jikko_ritsu()]
    assert rates != sorted(rates)
    assert rates != sorted(rates, reverse=True)
    assert max(rates) - min(rates) == pytest.approx(0.2174, abs=1e-4)


def test_切り捨ては最大75円で合計425円():
    rows = {r["排気量の区分"]: r for r in j.kirisute()}
    cut = [r["切り捨てられた額（円）"] for r in j.kirisute()]
    assert max(cut) == 75.0
    assert cut.count(0.0) == 2
    assert j.kirisute_gokei() == 425.0
    # **同じ75円でも、率への効きは 2.2174倍 ちがう**
    a = rows["1,000cc超1,500cc以下"]
    b = rows["4,000cc超4,500cc以下"]
    assert a["切り捨てられた額（円）"] == b["切り捨てられた額（円）"] == 75.0
    assert a["率がいくつ下がったか（ポイント）"] == 0.2174
    assert b["率がいくつ下がったか（ポイント）"] == 0.098
    assert j.kirisute_kiki() == pytest.approx(2.2174, abs=1e-4)


# ---------------------------------------------------------------- 節2

def test_増える額は3_77倍ひらき元の税額の幅より広い():
    rows = j.zougaku()
    assert rows[0]["1年で増える額（円）"] == 4_400
    assert rows[-1]["1年で増える額（円）"] == 16_600
    assert rows[-1]["いちばん小さい区分の何倍か"] == 3.7727
    assert rows[-1]["重課前の税額が29,500円の何倍か"] == 3.7627
    # **増額の幅のほうが、元の税額の幅より広い**（切り捨てが小さい区分ほど深く効く）
    assert rows[-1]["いちばん小さい区分の何倍か"] > rows[-1]["重課前の税額が29,500円の何倍か"]


# ---------------------------------------------------------------- 節3

def test_旧税率の軽は79パーセント上がり乗用車のどれより大きい():
    rows = {r["区分"]: r for r in j.kei_juka()}
    kei = rows["軽・乗用・自家用"]
    assert kei["旧からの上がり幅（パーセント）"] == 79.1667
    assert kei["新からの上がり幅（パーセント）"] == 19.4444
    assert rows["軽・貨物・自家用"]["旧からの上がり幅（パーセント）"] == 50.0
    assert rows["軽・貨物・自家用"]["新からの上がり幅（パーセント）"] == 20.0
    hikaku = rows["（比較）乗用車 1,000cc超1,500cc以下"]
    assert hikaku["旧からの上がり幅（パーセント）"] == 14.7826


def test_重課という言葉の幅は5_36倍():
    assert j.juka_haba() == pytest.approx(5.3554, abs=1e-4)


def test_軽の重課後の額は新旧で分かれていない():
    """**ここが原因。** 分かれていれば79パーセントは出ません。"""
    for _name, _old, _new, juka in j.KEI:
        assert isinstance(juka, int)
    assert j.KEI[0][3] == 12_900


# ---------------------------------------------------------------- 節4

def test_重課の開始は登録年度プラス14でディーゼルは2年早い():
    rows = {r["初度登録の年度"]: r for r in j.kaishi_nendo()}
    assert rows[2012]["ガソリン車の重課開始年度"] == 2026
    assert rows[2012]["ディーゼル車の重課開始年度"] == 2024
    assert rows[2012]["2026年度に重課されているか"] == "はい"
    assert rows[2013]["2026年度に重課されているか"] == "いいえ"
    for r in j.kaishi_nendo():
        assert (r["ガソリン車の重課開始年度"]
                - r["ディーゼル車の重課開始年度"]) == 2


def test_2019年10月以降に登録した車はまだ1台も重課されていない():
    """**節4の主題。** いま重課されている車は、全部が引き下げ前の税率の車。"""
    for r in j.kaishi_nendo(2019, 2026):
        assert r["適用される税率"] == "2019年10月以降"
        assert r["2026年度に重課されているか"] == "いいえ"
    assert j.kaishi_nendo(2019, 2019)[0]["ガソリン車の重課開始年度"] == 2033


# ---------------------------------------------------------------- 節5

def test_累計は1年あたりが一定で5年で22000円():
    rows = j.ruikei()
    assert rows[4]["1,000cc以下の累計（円）"] == 22_000
    assert rows[4]["6,000cc超の累計（円）"] == 83_000
    assert rows[0][j.RUIKEI_LABEL] == "—"
    assert {r[j.RUIKEI_LABEL] for r in rows[1:]} == {4_400.0}


# ---------------------------------------------------------------- 節7

def test_新しい車との倍率は単調に下がるのに額の差は単調でない():
    """**節7の主題。** 率と額で向きが違う。"""
    rows = j.shinsha_hi()
    ratios = [r["何倍か"] for r in rows]
    gaps = [r["差（円）"] for r in rows]
    assert ratios == sorted(ratios, reverse=True)
    assert ratios[0] == 1.356
    assert ratios[-1] == 1.16
    assert gaps != sorted(gaps)
    # 1,500cc超2,000cc以下の9,400円から、次の区分で8,200円へ**下がる**
    assert gaps[2] == 9_400
    assert gaps[3] == 8_200


# ---------------------------------------------------------------- 故障注入

def test_重課後を掛けただけの額より上にすると落ちる(monkeypatch):
    broken = [(n, o, w, j_ + 200) for n, o, w, j_ in j.HAIKIRYO]
    monkeypatch.setattr(j, "HAIKIRYO", broken)
    with pytest.raises(_checks.TableError):
        j.check_tables()


def test_切り捨てを100円以上にすると落ちる(monkeypatch):
    broken = [(n, o, w, j_ - 100) for n, o, w, j_ in j.HAIKIRYO]
    monkeypatch.setattr(j, "HAIKIRYO", broken)
    with pytest.raises(_checks.TableError):
        j.check_tables()


def test_ちょうど15パーセントが2区分でなくなると落ちる(monkeypatch):
    """**主題そのものの検査。** 切りのよい数に丸めると、この表の面白さが消えます。"""
    broken = [(n, o, w, int(o * Decimal("1.15") // 1000 * 1000))
              for n, o, w, j_ in j.HAIKIRYO]
    monkeypatch.setattr(j, "HAIKIRYO", broken)
    with pytest.raises(_checks.TableError):
        j.check_tables()


def test_軽の重課を新税率だけに掛けると乗用車より上でなくなり落ちる(monkeypatch):
    """旧税率の軽が跳ねる、という節3の主題が消えたときに落ちること。"""
    broken = [(n, new, new, juka) for n, _old, new, juka in j.KEI]
    monkeypatch.setattr(j, "KEI", broken)
    with pytest.raises(_checks.TableError):
        j.check_tables()


def test_2019年の引き下げを消すと落ちる(monkeypatch):
    broken = [(n, o, o, j_) for n, o, _w, j_ in j.HAIKIRYO]
    monkeypatch.setattr(j, "HAIKIRYO", broken)
    with pytest.raises(_checks.TableError):
        j.check_tables()


def test_差を単調にすると節7の主題が消えて落ちる(monkeypatch):
    """**「額は単調でない」を主張するなら、単調になった瞬間に落ちること。**"""
    broken = [(n, o, j_ - 8_000 - i * 500, j_)
              for i, (n, o, _w, j_) in enumerate(j.HAIKIRYO)]
    monkeypatch.setattr(j, "HAIKIRYO", broken)
    with pytest.raises(_checks.TableError):
        j.check_tables()


def test_1年あたりの見出しから単位を消すと落ちる(monkeypatch):
    """`_checks.per_unit_steps` は、見出しが単位を宣言していないと通しません。"""
    monkeypatch.setattr(j, "RUIKEI_LABEL", "1,000cc以下の増え（円）")
    with pytest.raises(_checks.TableError):
        j.ruikei()


# ---------------------------------------------------------------- 前提と主張

def test_前提に値が入っている():
    _checks.assumption_values(j.ASSUMPTIONS, name="jidoushazei")


def test_docstring_の単位つきの数は全部出力で裏が取れる():
    import io
    import contextlib
    import runpy

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_module("src.calc.jidoushazei", run_name="__main__")
    _checks.numbers_backed(j.__doc__ or "", buf.getvalue(), name="jidoushazei")
