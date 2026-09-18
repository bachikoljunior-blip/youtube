"""`studio/series_taishoku_years.py`（退職金 2000万円 × 勤続年数の連作 5本）の検査。

2026-09-18 21:xx・optimizer。**何を守っているか**:
 (1) **数を 1つ も新しく作っていないこと** —— 5本 の手取り・税金が、長尺
     `2026-09-17-taishokukin-2000man-tedori` の説明欄の年数の表（`series_taishoku.YEARS_TABLE`）
     と 1円 まで一致する（**陽性対照つき** ＝ 表の字から読み直して比べる）。
 (2) 連作の形（10コマ・450字・`form: short`・09/20 の日付）。
 (3) **出口の一手が在ること**（`script.has_cta` ＝ 登録 か 説明欄のリンク）。
 (4) **09/19 に上げた 4本 の台本を、この file が書き換えないこと**（id が別・`DATE` が 09/20）。
"""
from __future__ import annotations

import re

import pytest

from studio import script, series_taishoku, series_taishoku_years as SY

BOOKS = [f() for f in SY.ALL]


def _table_rows() -> dict[int, tuple[int, int]]:
    """`YEARS_TABLE` の字から {年数: (税金, 手取り)} を読み直す（**陽性対照**）。"""
    out = {}
    for line in series_taishoku.YEARS_TABLE.splitlines():
        m = re.match(r"・(\d+)年.*税金 (\S+)　手取り (\S+)", line.replace("　", "　"))
        if m:
            out[int(m.group(1))] = (_yen(m.group(2)), _yen(m.group(3)))
    return out


def _yen(s: str) -> int:
    m = re.fullmatch(r"(?:(\d+)万)?(\d+)?円", s)
    assert m, s
    return int(m.group(1) or 0) * 10_000 + int(m.group(2) or 0)


def test_陽性対照_表が読めている():
    rows = _table_rows()
    assert set(rows) == {20, 25, 30, 35, 38}, rows
    assert rows[30] == (405_700, 19_594_300)


@pytest.mark.parametrize("y", [20, 25, 35, 38])
def test_長尺の表と1円まで一致(y):
    want_tax, want_net = _table_rows()[y]
    t = series_taishoku.tax(SY.AMOUNT, y)
    assert (t["tax"], t["net"]) == (want_tax, want_net)


def test_31年は端数の切り上げ():
    """30年2か月 → 31年（No.1420）。長尺の説明欄に在る 9つ の数のうちの 1つ。"""
    t = series_taishoku.tax(SY.AMOUNT, 31)
    assert t["deduction"] == 15_700_000
    assert t["tax"] == 334_900 and t["net"] == 19_665_100


def test_連作の形():
    assert len(BOOKS) == 5
    for d in BOOKS:
        assert d["form"] == "short"
        assert d["date"] == "2026-09-20"
        assert len(d["segments"]) == 10
        n = sum(len(s["say"]) for s in d["segments"])
        assert n <= 450, (d["id"], n)          # METHOD §31
        assert max(len(s["say"]) for s in d["segments"]) <= 70, d["id"]


def test_出口の一手が在る():
    """登録 か 説明欄のリンク（`script.CTA_RE`・2026-09-18 20:3x に「説明欄」を足した）。"""
    for d in BOOKS:
        s = script.Script.model_validate(d)
        assert script.has_cta(s.segments[-1]), d["id"]


def test_09_19の4本を書き換えない():
    """id が別であること ＝ `write()` を撃っても、上げた本の `build_sig` は動かない。"""
    ours = {d["id"] for d in BOOKS}
    assert not (ours & set(series_taishoku.BAKED_BEFORE_CTA_SWITCH))
    assert all(d["id"].startswith("2026-09-20-") for d in BOOKS)


def test_数はtaxの返りそのもの():
    """本文に出る手取りが、丸めた数ではないこと（`man()` の字で照合）。"""
    for d, y in zip(BOOKS, (20, 25, 31, 35, 38)):
        t = series_taishoku.tax(SY.AMOUNT, y)
        hook = d["segments"][0]["say"]
        assert series_taishoku.man(t["net"]) in hook, (d["id"], hook)
