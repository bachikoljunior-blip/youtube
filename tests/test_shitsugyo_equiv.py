"""**離職理由の差は、在籍何年ぶんか**（`src/calc/shitsugyo.reason_equivalent_tenure`）。

既存の `reason_boundary()` は**同じ勤続年数を横に**比べます。この節は**縦に**探して、
「自己都合の帯に、倒産・解雇の何年目が並ぶか」を当てます。**交換レートの表**です。

## ここで固定すること

1. **並ぶ相手は、届く帯のうちいちばん短いもの**（「最初に日数以上になる帯」）。
   ここが「いちばん長い帯」に変わると、`years_saved` が最小値になって主題が消えます
2. **`years_saved` は下端どうしの差**（＝「何年ぶん得か」の下限）。
   帯の中のどこに居るかで実際の差は前後するので、**上限を名乗らせないこと**
3. **自己都合に受給資格の無い帯（1年未満）は行にしない。** 比べる相手になりません
4. `check_tables()` の性質9 —— **表が変わって主題が消えたら落ちること**

**2 が要る理由**: この数字は動画の画面に出ます。`+19年` と出しておいて中身が
「最大19年」だったら、それは**裏の取れない数字**です（`CLAUDE.md`）。
下限として出すぶんには、どの人にも当てはまります。
"""
from __future__ import annotations

import pytest

from src.calc import shitsugyo as S


def test_自己都合の1年未満は行にならない():
    for age in S.AGE_ORDER:
        assert all(r["self_band"] != "1年未満" for r in S.reason_equivalent_tenure(age))


def test_並ぶ相手はいちばん短い帯():
    for age in S.AGE_ORDER:
        row = S.DAYS_INVOLUNTARY[age]
        for r in S.reason_equivalent_tenure(age):
            if r["match_band"] is None:
                assert all(d is None or d < r["self_days"] for d in row.values())
                continue
            assert r["match_days"] >= r["self_days"]
            # **これより短い帯はどれも届いていないこと**（＝最小性）
            for band in S.TENURE_BANDS:
                if S.TENURE_MIN_YEARS[band] >= S.TENURE_MIN_YEARS[r["match_band"]]:
                    continue
                assert row[band] is None or row[band] < r["self_days"], band


def test_在籍の差は下端どうしの差():
    for age in S.AGE_ORDER:
        for r in S.reason_equivalent_tenure(age):
            if r["match_band"] is None:
                continue
            assert r["years_saved"] == (
                S.TENURE_MIN_YEARS[r["self_band"]] - S.TENURE_MIN_YEARS[r["match_band"]])


def test_余りの金額は下限額と上限額で挟む():
    for age in S.AGE_ORDER:
        for r in S.reason_equivalent_tenure(age):
            if r["match_band"] is None:
                continue
            assert r["excess_yen_low"] == r["excess_days"] * S.DAILY_FLOOR
            assert r["excess_yen_high"] == r["excess_days"] * S.DAILY_CAP[age]
            assert r["excess_yen_low"] <= r["excess_yen_high"]


def test_45歳以上は19年ぶん():
    """**この節を書いた理由そのもの。** 数字が変わったら、文言ごと見直すこと。"""
    rows = {r["self_band"]: r for r in S.reason_equivalent_tenure("45歳以上60歳未満")}
    r = rows["20年以上"]
    assert (r["self_days"], r["match_band"], r["match_days"]) == (150, "1年以上5年未満", 180)
    assert r["years_saved"] == 19
    assert (r["excess_days"], r["excess_yen_high"]) == (30, 30 * 9110)


def test_表が主題を失ったら検査で落ちる(monkeypatch):
    """性質9。**倒産・解雇の側を自己都合と同じにすると、交換レートが消えます。**"""
    flat = {b: S.DAYS_GENERAL[b] for b in S.TENURE_BANDS}
    flat["1年未満"] = 90
    monkeypatch.setattr(S, "DAYS_INVOLUNTARY", {a: dict(flat) for a in S.DAILY_CAP})
    with pytest.raises(S.TableError):
        S.check_tables()
