"""**その差額を作っているのは、2つのルールのどちらか**（`src/calc/hendo.split_grid`）。

## なぜ足したか（2026-09-01・規則3 の improve）

`rule_grid()` は **「ルールあり」対「ルールなし」の2択**しか出していませんでした。
ところが「ルール」は**別々の2つ**です ——
**5年ルール**（返済額を60回すえ置く）と
**125パーセントルール**（見直しの上げ幅を直前の1.25倍で頭打ちにする）。

`simulate()` は最初からこの2つを**別の旗**で持っています
（`five_year_rule` / `cap_125`）。**それでも、どの表も一度も分けていません。**
動画は 4.0% の例で「ルールありのほうが **5,716,767円 多い**」と言うだけで、
**その内訳を言っていませんでした。**

## 実測（3,500万円・35年・当初0.5%・13回目から上昇）

    上がった先 4.0%
      どちらも無し           63,495,265円
      ＋5年ルール            65,120,750円   **＋1,625,485円**（28.4%）
      ＋125パーセントルール  69,212,032円   **＋4,091,282円**（71.6%）
                                            計 5,716,767円

**重いのは 125 側**で、金利が高いほど偏ります（2.0% 21.6% → 5.0% 81.5%）。
**5年ルールは60回で必ず解ける**（61回目に必要額まで上がる）のに対し、
**125 側は上がり切るまで解けない** —— `catchup_grid()` の実測で、
4.0% の例は **241回目（21年目）**まで頭打ちが続きます。

## この検査がいちばん言いたいこと

**内訳の和は、`rule_grid()` の「差」に円まで一致すること。**
動画が読み上げるのは内訳のほうなので、
片方の列が別の前提で解かれたら**その場で赤にします**
（`check_tables()` の 12 と同じ縛りを、外からも掛けています）。

## 覆る条件

- `ASSUMPTIONS` の2（利率は一段だけ動く）を変えて**複数回 動かす**ように
  したら、4つ目の枡（`five_year_rule=False, cap_125=True`）が意味のある数に
  なります。そのときは `split_grid()` に列を足し、
  下の `test_125だけの枡は欄にしない()` を書き直すこと
- 前提（`PRINCIPAL` / `YEARS` / `START_RATE` / `RISE_AT`）を変えたら、
  上の実測は動きます。**そのときは測り直して、ここも動画も直すこと**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.calc import hendo  # noqa: E402


def test_内訳の和がrule_gridの差に円まで一致する() -> None:
    diff = {row["上がった先"]: row["差"] for row in hendo.rule_grid()}
    for row in hendo.split_grid():
        got = row["5年ルールの寄与"] + row["125%ルールの寄与"]
        assert got == diff[row["上がった先"]], (
            f"{row['上がった先']}: 内訳の和 {got:,} が "
            f"rule_grid の差 {diff[row['上がった先']]:,} と違う"
        )
        assert row["差の合計"] == got


def test_一本道の3列が単調に増える() -> None:
    """無し → 5年だけ → 両方。**ルールを足して安くなる列は無い。**"""
    for row in hendo.split_grid():
        assert row["どちらも無し"] <= row["5年ルールだけ"] <= row["両方"], row


def test_未払利息が積む帯では125の寄与のほうが重い() -> None:
    """4.0% / 5.0% ＝ `freeze_rate` の 3.115% を越えた側。"""
    for row in hendo.split_grid(rates=(0.040, 0.050)):
        assert row["125%ルールの寄与"] > row["5年ルールの寄与"], row


def test_125の取り分は金利が上がるほど大きくなる() -> None:
    shares = [
        row["125%ルールの寄与"] / row["差の合計"]
        for row in hendo.split_grid()
    ]
    assert shares == sorted(shares), shares


def test_4パーセントの内訳は動画で読み上げる数と同じ() -> None:
    row = next(r for r in hendo.split_grid() if r["上がった先"] == "4.0%")
    assert row["どちらも無し"] == 63_495_265
    assert row["5年ルールだけ"] == 65_120_750
    assert row["両方"] == 69_212_032
    assert row["5年ルールの寄与"] == 1_625_485
    assert row["125%ルールの寄与"] == 4_091_282
    assert row["差の合計"] == 5_716_767
    assert row["125%の取り分"] == "71.6%"


def test_その内訳がASSUMPTIONSにも書いてある() -> None:
    """**台本の書き手に渡るのは `ASSUMPTIONS` の文だけです**（表は渡りません）。"""
    line = next(a for a in hendo.ASSUMPTIONS if "1,625,485" in a)
    for want in ("5,716,767", "4,091,282", "71.6", "241"):
        assert want in line, f"{want} が前提の文に無い"


def test_125だけの枡は欄にしない() -> None:
    """**この模型では意味のある数になりません**（`split_grid()` の註）。

    5年ルールを外すと見直しは「利率が動いた回」だけになり、
    `ASSUMPTIONS` の2 では利率は一段しか動かないので、
    **生涯に1回きりの見直しで掛かった 1.25倍 が、420回のあいだ解けません。**
    ルールを1つ外したのに**両方付いた契約より重くなる** ——
    それが欄にしない理由です。ここでは、その事実そのものを固定します
    （実物が変わったら、註のほうを書き直すこと）。
    """
    path = ((0, hendo.START_RATE), (hendo.RISE_AT, 0.040))
    both = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path)
    only_125 = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path,
                              five_year_rule=False, cap_125=True)
    assert only_125["total"] > both["total"], (
        "125だけの枡が両方より軽くなった。"
        "`split_grid()` の「欄にしていない理由」を書き直すこと"
    )
    assert not any(k.startswith("125%ルールだけ")
                   for k in hendo.split_grid()[0])


def test_check_tablesがsplit_gridも見ている() -> None:
    hendo.check_tables()
