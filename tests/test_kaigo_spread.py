"""`src/calc/kaigo.py` の新しい2節 —— 介護保険の上限が「開き」に何をするか。

制度の説明はどれも「限度額は要介護度で決まる」「自己負担は1〜3割」
「高額介護サービス費の上限は一般区分44,400円」の3つを**別々に**書きます。
**3つを同じ表に並べると、どこにも書かれていないことが2つ出ます。**

1. 限度額は 要支援1 → 要介護5 で **7.20倍**に開く。ところが上限は
   **上の段にしか当たらない**ので、実際に払う額の開きは
   **1割 7.20倍 → 2割 4.41倍 → 3割 2.94倍** と縮む。
   同額で並ぶ段は **0段 → 3段 → 5段**（3割は要介護1から上が全部44,400円）。
   上が同じ額で止まるので、**2割と3割の倍率の比は負担割合の比そのもの（1.50倍）**。
   実効の負担率で見ると、「3割負担」の人は **30.0% → 12.26%** まで下がる。
2. 上限は**5段ある**（24,600〜140,100円）。一般区分だけを見ていると
   「1割には効かない」で終わるが、**住民税非課税の世帯（24,600円）は
   1割負担でも要介護3から効く**。逆に**課税所得690万円以上（140,100円）は、
   3割負担でもどの要介護度にも当たらない**（届くのに46,700単位が要り、
   限度額の最大 36,217単位を超えている）。

**`同額で並ぶ段` は「上限に当たっている段」そのものです。**
最上段は必ず入るので、1割の「0段」は一覧としては1件（要介護5）になります。
数え方を変えるときは、この検査の期待値も一緒に変えること。
"""
from __future__ import annotations

import pytest

from src.calc import _checks, kaigo as kg


def test_制度の値の検査が通る():
    kg.check_tables()


def test_限度額そのものは7段で7_20倍に開く():
    sp = kg.level_spread(0.1)
    assert sp["いちばん低い段"] == "要支援1"
    assert sp["いちばん高い段"] == "要介護5"
    assert sp["限度額の倍率"] == pytest.approx(36_217 / 5_032, rel=1e-12)
    assert sp["限度額の倍率"] == pytest.approx(7.1973, abs=1e-4)


def test_1割では上限がどこにも当たらないので支払いの開きが限度額の開きと同じ():
    sp = kg.level_spread(0.1)
    assert sp["倍率"] == pytest.approx(sp["限度額の倍率"], rel=1e-12)
    assert sp["同額で並ぶ段"] == ["要介護5"]      # 最上段だけ＝当たっている段は0
    assert all(row["実効の負担率"] == pytest.approx(10.0)
               for row in sp["行"])


@pytest.mark.parametrize("rate, want", [(0.1, 7.1973), (0.2, 4.4118), (0.3, 2.9412)])
def test_負担割合が重いほど開きが縮む(rate, want):
    assert kg.level_spread(rate)["倍率"] == pytest.approx(want, abs=1e-4)


def test_開きは割合の順に単調に縮む():
    got = [kg.level_spread(r)["倍率"] for r, _lb, _w in kg.COPAY_RATES]
    assert got == sorted(got, reverse=True)
    assert len(set(got)) == 3        # **同じ値が並んでいたら節が言えません**


@pytest.mark.parametrize("rate, want", [
    (0.1, ["要介護5"]),
    (0.2, ["要介護3", "要介護4", "要介護5"]),
    (0.3, ["要介護1", "要介護2", "要介護3", "要介護4", "要介護5"]),
])
def test_同額で並ぶ段は割合が重いほど増える(rate, want):
    assert kg.level_spread(rate)["同額で並ぶ段"] == want


def test_同額で並ぶ段は本当に同じ額():
    for rate, _lb, _w in kg.COPAY_RATES:
        sp = kg.level_spread(rate)
        flat = [row["1か月に払う額"] for row in sp["行"]
                if row["要介護度"] in sp["同額で並ぶ段"]]
        assert len(set(flat)) == 1


def test_2割と3割の倍率の比は負担割合の比そのもの():
    """上が同じ 44,400円 で止まるので、残るのは**下の端の比**だけ。"""
    two, three = kg.level_spread(0.2)["倍率"], kg.level_spread(0.3)["倍率"]
    assert two / three == pytest.approx(0.3 / 0.2, rel=1e-12)


def test_3割の実効の負担率は段が上がるほど下がる():
    eff = [row["実効の負担率"] for row in kg.level_spread(0.3)["行"]]
    assert eff == sorted(eff, reverse=True)
    assert eff[0] == pytest.approx(30.0)
    assert eff[-1] == pytest.approx(12.2594, abs=1e-4)
    # **1割負担（10%）との差は 2.27ポイントしか残りません。**
    assert eff[-1] - 10.0 < 2.3


def test_1割の実効の負担率は段によらず一定():
    eff = {round(row["実効の負担率"], 9) for row in kg.level_spread(0.1)["行"]}
    assert eff == {10.0}


def test_非課税世帯の上限は1割負担でも要介護3から効く():
    row = [r for r in kg.cap_class_bites(0.1) if r["上限"] == 24_600][0]
    assert row["効き始める要介護度"] == "要介護3"
    assert row["どこにも効かない"] is False
    assert row["上限に届く単位"] == pytest.approx(24_600)


def test_一般区分は1割負担ではどの要介護度でも効かない():
    rows = [r for r in kg.cap_class_bites(0.1) if r["上限"] == kg.GENERAL_CAP]
    assert rows and all(r["どこにも効かない"] for r in rows)
    assert all(r["いちばん高い段でも足りない単位"] == 8_183 for r in rows)


def test_1割で効く上限の区分は5つのうち1つだけ():
    got = [r for r in kg.cap_class_bites(0.1) if not r["どこにも効かない"]]
    assert [r["上限"] for r in got] == [24_600]


def test_690万円以上の上限は3割負担でもどこにも当たらない():
    row = [r for r in kg.cap_class_bites(0.3) if r["上限"] == 140_100][0]
    assert row["どこにも効かない"] is True
    assert row["効き始める要介護度"] is None
    assert row["上限に届く単位"] == pytest.approx(46_700)
    assert row["いちばん高い段でも足りない単位"] == 46_700 - 36_217


def test_割合が重いほど効き始める段は下がる():
    """同じ上限の区分でも、負担割合が重ければ早く当たる。**逆向きは無いこと。**"""
    order = [name for name, _u in kg.LIMIT_UNITS]

    def rank(level):
        return order.index(level) if level else len(order)

    for cap_name, cap in kg.CAPS:
        got = [rank([r for r in kg.cap_class_bites(rate)
                     if r["上限の区分"] == cap_name][0]["効き始める要介護度"])
               for rate, _lb, _w in kg.COPAY_RATES]
        assert got == sorted(got, reverse=True), f"{cap_name}（{cap:,}円）"


def test_上限の区分そのものは5_70倍に開く():
    caps = [c for _n, c in kg.CAPS]
    assert max(caps) / min(caps) == pytest.approx(140_100 / 24_600, rel=1e-12)
    assert max(caps) / min(caps) == pytest.approx(5.6951, abs=1e-4)


def test_節の見出しが2つとも出ている():
    """**印字を消しても検査は緑のまま通ります。**見出しそのものを見ること。"""
    import io
    import contextlib
    import runpy

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_module("src.calc.kaigo", run_name="__main__")
    out = buf.getvalue()
    assert "=== 7段の開きは、負担割合が重いほど縮む" in out
    assert "=== 上限の区分を変えると、効き始める段が動く" in out
    # **数字を画面に出していること**（前提と計算結果を出すのがこの作りの根幹）
    for want in ("7.20倍", "4.41倍", "2.94倍", "24,600円", "140,100円"):
        assert want in out, want


def test_検査は壊した値を落とす():
    """**通ることではなく、落ちることを確かめる。**"""
    before = kg.CAPS[:]
    try:
        kg.CAPS[:] = [(n, 999_999) for n, _c in before]
        with pytest.raises(_checks.TableError):
            kg.check_tables()
    finally:
        kg.CAPS[:] = before
    kg.check_tables()
