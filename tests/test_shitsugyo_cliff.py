"""60歳の境目 —— **日数だけを見ると、落ち込みが浅く見える。**

## なぜこの節を足したか（2026-08-16）

`status.py` の「族べつの実績」が **shitsugyo を engaged 45.6% で2位**に置きながら、
**未使用の節が0件**でした（上位3族が全部そう）。M15 は「実績の順に作る」手ですが、
**上位の族に作れるものが1つも無ければ、順番を持っていても選べません。**
だから在庫を、いちばん当たっている族に足しています。

## 足した節が、既にある節の欠けを見せた

`age_boundaries()` は年齢の境目を**日数の差**で出しています。ところが 60歳では
`DAILY_CAP` そのものが 9,110円 → 7,830円 と下がるので、**総額の差は日数の差より深い。**

    20年以上   日数だけ −819,900円   実際 **−1,127,100円**（30万7200円ぶん浅い）
    1年未満    日数の差が0なので **`age_boundaries()` はこの行ごと落とす**
               実際は上限に当たる人で **−115,200円**

**「見せなさすぎ」の側の欠け**なので、目視でも機械検査でも気づけません
（出ていないものは読めない）。ここで数字ごと留めます。
"""
from __future__ import annotations

from src.calc import shitsugyo


def _row(band: str) -> dict:
    (r,) = [x for x in shitsugyo.age_cap_cliff() if x["band"] == band]
    return r


def test_上限額は60歳で下がる():
    assert shitsugyo.DAILY_CAP["60歳以上65歳未満"] < shitsugyo.DAILY_CAP["45歳以上60歳未満"]


def test_日数が変わらない帯でも上限の人は減る():
    """**`age_boundaries()` が落としている行。** ここが0円なら、節の主張が消えます。"""
    r = _row("1年未満")
    assert r["days_gained"] == 0
    assert r["cap_yen_gained"] == -115_200
    assert r["days_only_yen"] == 0


def test_いちばん深いのは20年以上():
    r = _row("20年以上")
    assert r["cap_yen_before"] == 3_006_300
    assert r["cap_yen_after"] == 1_879_200
    assert r["cap_yen_gained"] == -1_127_100
    # 日数だけで見た差より、必ず深い（これがこの節の主張そのもの）
    assert r["cap_yen_gained"] < r["days_only_yen"]
    assert r["days_only_yen"] - r["cap_yen_gained"] == 307_200


def test_全部の帯で日数だけより深いか同じ():
    for r in shitsugyo.age_cap_cliff():
        assert r["cap_yen_gained"] <= r["days_only_yen"], r


def test_下限に当たる人には単価の段差が無い():
    """`DAILY_FLOOR` は全年齢共通。**段差は「上限に当たる人ほど深い」**という形。"""
    for r in shitsugyo.age_cap_cliff():
        assert r["floor_yen_gained"] == r["days_gained"] * shitsugyo.DAILY_FLOOR


def test_改定で向きが変わったら検査が落ちる(monkeypatch):
    """**故障注入。** 上限額は毎年8月1日に改定されます。向きが変わった表を
    黙って通すと、節の答えが逆のまま動画になります。"""
    monkeypatch.setitem(shitsugyo.DAILY_CAP, "60歳以上65歳未満", 9_999)
    try:
        shitsugyo.check_tables()
    except shitsugyo.TableError:
        return
    raise AssertionError("60歳の上限額が上がっても check_tables() が通ってしまいます")


def test_前提に上限額と下限額の値が入っている():
    """値の無い前提を渡すと、書き手は黙って落とすか数字を作るかの2択になります。"""
    joined = "".join(shitsugyo.ASSUMPTIONS)
    for v in ("9110", "7830", "2562"):
        assert v in joined, v
