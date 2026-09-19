"""**案件は「扉」ではなく「1クリックがいくら運ぶか」で選ぶ**（2026-09-20 08:xx・optimizer）。

**この検査が守っているもの**（決め・出どころ・覆る条件は `studio/asp.py`
「1クリックがいくら運ぶか」の註 ＝ **ここへ写さないこと**）:

 1. 要る 円/クリック ＝ 目標 ÷ クリック/月（クリック/月 ＝ 再生/月 × 押される率の実測）
 2. 単価が下がれば要る率は上がる（**前の周の「倍率の計算は変わりません」は、ここで割れます**）
 3. ¥1,000 の案件は門（`NEED_CONVERT_GATE`）を越える ＝ **目標の分子として数えない**
 4. **陽性対照**: ¥20,000 の候補は門を越えない（門が全部を落とす作りになっていないこと）
"""
from __future__ import annotations

import pytest

from studio import asp, trend


def test_要る円クリックは目標をクリック月で割った数():
    d = trend.need_yen_per_click(trend.ledger_rows())
    cap = d["cap"]
    assert d["click_rate"] == trend.PERF_CLICK_BAND[1], "押される率は実測の中段 1か所から引くこと"
    for case in (d, cap):
        if not case.get("clicks_month"):
            continue
        assert case["need_yen"] == pytest.approx(d["goal"] / case["clicks_month"])


def test_単価が下がると要る率は上がる():
    """**前の周の「¥5,000 でも倍率の計算は変わりません」が割れる所。**"""
    need = 257.0
    hi = asp.need_convert(need, 20_000.0)
    mid = asp.need_convert(need, 5_000.0)
    lo = asp.need_convert(need, 1_000.0)
    assert hi < mid < lo
    assert mid == pytest.approx(hi * 4.0)     # 単価 1/4 → 要る率 4倍
    assert lo == pytest.approx(hi * 20.0)


def test_千円の案件は門を越える():
    """¥1,000（墓じまい資料請求）は、扉が開いていても目標の分子にならない。"""
    need = 257.0
    assert asp.need_convert(need, 1_000.0) > asp.NEED_CONVERT_GATE


def test_陽性対照_二万円の案件は門を越えない():
    """**門が全部を落とす作りだと、この検査が落ちます**（＝ 門が意味を持つこと）。"""
    need = 257.0
    assert asp.need_convert(need, 20_000.0) <= asp.NEED_CONVERT_GATE


def test_候補の単価は字で分かっている数だけ():
    """`CANDIDATES` は「読んだ案件」だけ ＝ 帯（未測）を混ぜない。"""
    assert asp.CANDIDATES, "候補が空なら、この段は仕事をしていません"
    for name, yen, cond, aspname in asp.CANDIDATES:
        assert yen > 0 and name and cond and aspname
    # **いちばん高い候補が門の内側に在ること**（無ければ、この道に届く案件が 1件も無い）
    best = min(asp.need_convert(257.0, y) for _, y, _, _ in asp.CANDIDATES)
    assert best <= asp.NEED_CONVERT_GATE, (
        "門の内側の候補が 0件 ＝ 詰まりは案件ではなく分母（クリック/月）です"
        "（`studio/asp.py` 覆る条件 (6)）")


def test_行は引けないとき空を返す():
    assert asp.yen_per_click_line(None) == ""
    assert asp.yen_per_click_line(0) == ""


def test_行は要る率と門を印字する():
    s = asp.yen_per_click_line(257.0)
    assert "円/クリック" in s
    assert "いえカツLIFE" in s or "候補" in s
    assert f"{asp.NEED_CONVERT_GATE*100:,.0f}%" in s
