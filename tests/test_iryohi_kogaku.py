"""医療費控除 × 高額療養費（`src/calc/iryohi.py` の 2026-08-17 に足した節）。

**この節の答えは「向き」でできています** ——
「限度額が低い区分ほど、控除に届くのが遅い」「月をまたいだ損は税金では取り返せない」。
どちらも表が変われば逆になるので、**逆になったら落ちる**ようにしてあります。

故障注入を両向きに掛けています（当たる側と、鳴らしてはいけない側）。
"""
from __future__ import annotations

import pytest

from src.calc import iryohi, kogaku


def test_限度額が低い区分ほど控除に届くのが遅い():
    starts = {r["tier"]: r["start_cost"] for r in iryohi.tier_thresholds(3_000_000)}
    assert starts["ア"] == starts["イ"] == 333_334   # まだ3割の帯
    assert starts["ウ"] == 2_257_000                 # 限度額の帯に入っている
    assert starts["エ"] is None and starts["オ"] is None


def test_届く額では自己負担がちょうど足切りに一致する():
    start = iryohi.deduction_start_cost("ウ", 3_000_000)
    assert iryohi.self_pay(start, "ウ") == iryohi.floor_amount(3_000_000)
    # その1円先では控除が出る（＝「超えたら」の意味が守られている）
    assert iryohi.deduction(iryohi.self_pay(start + 100_000, "ウ"), 0, 3_000_000) > 0


def test_足切りと限度額がちょうど一致する総所得では出ない():
    """**`<=` で書くと、ここが「118,000円を超えたら出る」になります。**

    区分オの限度額 35,400円 ＝ 総所得 708,000円 の足切り。自己負担はその額で
    頭打ちなので、医療費をいくら足しても足切りを**超えません**。
    """
    assert iryohi.floor_amount(708_000) == kogaku.tier("オ")[3]
    assert iryohi.deduction_start_cost("オ", 708_000) is None
    # 足切りが下なら出る（鳴らしすぎていないこと）。35,000円 ÷ 0.3 の切り上げ
    assert iryohi.floor_amount(700_000) == 35_000
    assert iryohi.deduction_start_cost("オ", 700_000) == 116_667


def test_月をまたいだ損はどの税率でも取り返せない():
    rows = iryohi.split_recovery()
    assert [r["rate"] for r in rows] == iryohi.INCOME_TAX_RATES
    for r in rows:
        assert 0 < r["recovered_ratio"] < 1
        assert r["net_gap"] > 0          # 分けたほうが必ず高くつく
    # 税率が高いほど取り返せる（向き）
    ratios = [r["recovered_ratio"] for r in rows]
    assert ratios == sorted(ratios)


def test_医療費が10倍でも最後に残る負担はほとんど動かない():
    rows = {r["cost"]: r for r in iryohi.kogaku_grid(3_000_000, 0.10)}
    ten_x = rows[10_000_000]["net_burden"] / rows[1_000_000]["net_burden"]
    assert 1.0 < ten_x < 2.0            # 医療費は10倍、負担は2倍未満
    # 負担率は単調に下がる
    rates = [r["net_rate"] for r in iryohi.kogaku_grid(3_000_000, 0.10)]
    assert rates == sorted(rates, reverse=True)


def test_故障注入_区分ウの限度額を上げると検査が落ちる(monkeypatch):
    """区分ウの定額を区分アより上にすると、節の主張（向き）が逆になる。"""
    broken = [(("ウ", 280_000, 500_000, 900_000, 267_000, 0.01, 44_400)
               if row[0] == "ウ" else row) for row in kogaku.TIERS]
    monkeypatch.setattr(kogaku, "TIERS", broken)
    with pytest.raises(ValueError, match="区分ウが区分アより早く"):
        iryohi.check_tables()


def test_故障注入_区分エに1パーセント刻みを足すと検査が落ちる(monkeypatch):
    """定額で頭打ちの区分が頭打ちでなくなったら、「届きません」は嘘になる。"""
    broken = [(("エ", None, 260_000, 57_600, 200_000, 0.01, 44_400)
               if row[0] == "エ" else row) for row in kogaku.TIERS]
    monkeypatch.setattr(kogaku, "TIERS", broken)
    with pytest.raises(ValueError, match="区分エ が1か月で足切りに届いている"):
        iryohi.check_tables()


def test_壊していないときは通る():
    iryohi.check_tables()          # 鳴らしてはいけない側
