"""**未払利息を止める上乗せ額**（`src/calc/hendo.guard_grid`）を守る。

## なぜ足したか（2026-09-01・規則3 の improve）

`src/calc/hendo.py` の7つの表は「**何が起きるか**」を全部 出していましたが、
「**どうすれば起きないか**」を出す表が1つもありませんでした。
視聴者が自分の金で動ける数は、そこにしかありません。

## この表がいちばん言いたいこと

    4.0% まで上がったとき、止めるのに要る毎月は 113,608円 ＝ **1.2504倍**
    125パーセントルールの上限は                113,568円 ＝ 1.25倍
                                                差 **40円**

**見直しを満額 使っても、4.0パーセントの未払利息は止められません。**
「1.25倍まで」の上限は、この借り方では**ちょうど止められなくなる線の
すぐ内側**に置かれています。**この検査は、その 40円 を守ります** ——
どちらかの側が動いたら、動画で言っている話が変わります。

## 覆る条件

- 前提（`PRINCIPAL` / `YEARS` / `START_RATE` / `RISE_AT`）を変えたら、
  この 40円 は動きます。**そのときは数を測り直して、ここも動画も直すこと**
- 未払利息に利息を付ける約款を出すようになったら、`guard_grid` は
  それだけでは足りなくなります（`ASSUMPTIONS` の4）
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.calc import hendo  # noqa: E402


def test_上乗せの向きが_simulateと一致する() -> None:
    """**出どころが2つあること自体が守り**。片方が壊れたら、ここで割れる。"""
    for row in hendo.guard_grid():
        rate = float(row["上がった先の年利"].rstrip("%")) / 100
        got = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS,
                             ((0, hendo.START_RATE), (hendo.RISE_AT, rate)))
        if row["要る上乗せ"] == 0:
            assert got["unpaid"] == 0, (
                f"{row['上がった先の年利']}: 上乗せ不要と言っているのに未払利息が積む")
        else:
            assert got["unpaid"] > 0, (
                f"{row['上がった先の年利']}: 上乗せが要ると言っているのに未払利息が0")


def test_上乗せ後の毎月は_その月の利息とぴったり同じ() -> None:
    """**元金充当 0円 の点**です。「元金が減る額」ではありません。"""
    for row in hendo.guard_grid():
        if row["要る上乗せ"] > 0:
            assert row["上乗せ後の毎月"] == row["その月の利息"]
        else:
            assert row["上乗せ後の毎月"] == row["いまの返済額"]


def test_4パーセントの行が_125パーセントの上限を40円超える() -> None:
    """**この動画のいちばんの主張**。数が動いたら、言っている話が変わります。"""
    rows = {r["上がった先の年利"]: r for r in hendo.guard_grid()}
    row = rows["4.0%"]
    pay = row["いまの返済額"]
    cap = int(pay * hendo.CAP_RATIO)          # 見直しで上げられる上限（切り捨て）
    need = row["上乗せ後の毎月"]              # 止めるのに要る毎月
    assert need > cap, "125パーセントの上限で止められることになっている"
    assert need - cap == 40, f"差が {need - cap}円（40円 のはず）"
    assert cap == 113_568 and need == 113_608


def test_上乗せは金利が高いほど単調に増える() -> None:
    rows = hendo.guard_grid()
    got = [r["要る上乗せ"] for r in rows]
    assert got == sorted(got), f"上乗せが単調でない: {got}"


def test_残高は上げ幅に依らない一つの値() -> None:
    """**上乗せ額の計算に上げ幅は要りません**（残高は上がる前の返済で決まる）。"""
    seen = {r["上がった月の残高"] for r in hendo.guard_grid()}
    assert len(seen) == 1, f"上がった月の残高が行ごとに違う: {seen}"


def test_check_tablesがguard_gridを見ている() -> None:
    """**表を足しても検査に入れなければ、壊れても誰も気づきません。**"""
    src = (ROOT / "src" / "calc" / "hendo.py").read_text(encoding="utf-8")
    _head, _, tail = src.partition("def check_tables(")
    assert "guard_grid(" in tail, "check_tables が guard_grid を突き合わせていない"


def test_mainがguard_gridを印字する() -> None:
    src = (ROOT / "src" / "calc" / "hendo.py").read_text(encoding="utf-8")
    _head, _, tail = src.partition("def main(")
    assert "guard_grid()" in tail, "main が新しい表を出していない"
