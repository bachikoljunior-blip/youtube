"""**ルールは毎月を守らない**（`src/calc/hendo.overtake_grid`）。

## なぜ足したか（2026-09-01・規則3 の improve）

この計算は「ルールが付いたほうが**総支払額**は 5,716,767円 多い」で締めます。
**総額は、毎月を払う人の実感に届きません** —— 35年で割れば月 13,611円 です。

**毎月のほうは、どの表にもありませんでした。**
`rule_grid()` が出していたのは「どちらも無し」の毎月だけ（4.0% で 152,956円）で、
**ルールが付いた契約の毎月は一度も画面に出ていません。**
そのせいで動画は「5年ルールがあるから毎月は据え置かれる」で止まり、
**据え置きが解けたあとに毎月がどこまで行くかを言っていませんでした。**

## 実測（3,500万円・35年・当初0.5%・13回目から上昇）

    上がった先 4.0%
      どちらも無しの毎月  152,956円（13回目から最後まで動かない）
      ルールありの毎月    90,855 → 113,568（61回目）→ 141,960（121回目）
                          → **177,450（181回目・16年目）** → 203,821（241回目）
      **181回目に追い越し**、そこから **240回** 高いほうを払い続ける
      最後の毎月 **203,819円** ＝ どちらも無しの **1.33倍**

**4本とも追い越します**（2.0% 121回目・1.05倍／3.0% 121回目・1.16倍／
5.0% 181回目・1.56倍）。

## この検査がいちばん言いたいこと

**(1) が破れたら、動画の締めを書き直すこと。**
「据え置いたぶんは、あとで上乗せして返す」が成り立たなくなります。

## 覆る条件

- **繰上返済を入れると崩れます**（`ASSUMPTIONS` の1 が「入れていません」）。
  元金を先に削れば必要額が上がらないので、追い越しが起きないことがあります。
  表に入れる回が来たら、この検査ごと前提つきに書き直すこと
- `ASSUMPTIONS` の2 を変えて**利率を複数回 動かす**ようにしたら、
  追い越す回は手前へ動きます（**向きは変わりません**）。実測を取り直すこと
"""
from __future__ import annotations

from src.calc import hendo


def test_どの金利でもルールありの最後の毎月が追い越す() -> None:
    """**この表の主張そのもの。** 破れたら動画の締めが成り立ちません。"""
    for row in hendo.overtake_grid():
        assert row["ルールありの最後の毎月"] > row["どちらも無しの毎月"], (
            f"上がった先 {row['上がった先']}: ルールありの最後の毎月 "
            f"{row['ルールありの最後の毎月']:,} が、どちらも無しの毎月 "
            f"{row['どちらも無しの毎月']:,} 以下"
        )
        assert row["追い越す回"] is not None


def test_追い越すのは据え置きが解けたあと() -> None:
    """据え置きの60回のあいだは返済額が動かないので、そこでは追い越せません。"""
    for row in hendo.overtake_grid():
        assert row["追い越す回"] > hendo.REVIEW_MONTHS, (
            f"上がった先 {row['上がった先']}: 追い越す回 {row['追い越す回']} が"
            f"据え置きの {hendo.REVIEW_MONTHS}回 の中"
        )


def test_追い越す回は見直しの回に実在する() -> None:
    """表の回が `simulate()` の見直しの回に無ければ、別の前提で解いています。"""
    for row in hendo.overtake_grid():
        rate = float(row["上がった先"].rstrip("%")) / 100
        got = hendo.simulate(
            hendo.PRINCIPAL, hendo.YEARS,
            ((0, hendo.START_RATE), (hendo.RISE_AT, rate)))
        months = {p["月"] for p in got["payments"]}
        assert row["追い越す回"] in months, (
            f"上がった先 {row['上がった先']}: 追い越す回 {row['追い越す回']} が"
            f"見直しの回 {sorted(months)} に無い"
        )


def test_4_0パーセントの実測が動いていない() -> None:
    """**動画が読み上げる数**。動いたら台本と `ASSUMPTIONS` を書き直すこと。"""
    row = next(r for r in hendo.overtake_grid() if r["上がった先"] == "4.0%")
    assert row["どちらも無しの毎月"] == 152_956
    assert row["ルールありの最後の毎月"] == 203_819
    assert row["追い越す回"] == 181
    assert row["追い越す年"] == 16
    assert row["追い越したあとの回数"] == 240
    assert row["何倍"] == "1.33倍"


def test_rule_gridの毎月の列は契約を名乗っている() -> None:
    """**旧 `なしの返済額` は、`split_grid()` と並べると読み違えます。**

    4.0% で `rule_grid()` の 152,956円 は「どちらも無し」の毎月、
    `split_grid()` の「5年ルールだけ」の最終返済額は 162,713円 で**別の数**です。
    **列の名前で契約を名乗ること。**
    """
    row = hendo.rule_grid()[0]
    assert "なしの返済額" not in row, (
        "`なしの返済額` はどちらの契約か言っていません。"
        "`どちらも無しの毎月` へ直したはずです"
    )
    assert "どちらも無しの毎月" in row
    assert "ルールありの最後の毎月" in row


def test_追い越しの数はASSUMPTIONSにも書いてある() -> None:
    """台本の書き手に渡るのは `ASSUMPTIONS` の文だけです（表は渡りません）。"""
    text = "".join(hendo.ASSUMPTIONS)
    for want in ("152,956", "203,819", "181回目", "240回", "1.33倍"):
        assert want in text, f"`ASSUMPTIONS` に {want} がありません"


def test_平均と混ぜていない() -> None:
    """**`何倍` は最後の毎月どうしの比で、平均どうしの比ではありません。**

    平均どうしなら **×1.07**（162,185円 対 151,182円）、
    最後の毎月どうしは **×1.33**。**向きは同じですが、別の数です。**

    **この検査は、書いた回に一度 逆を主張して赤くなりました**
    （「据え置きの60回が効くので平均なら 1.0倍 を割る」）。
    実際は据え置きの60回より、**そのあと元金が減らないまま払い続ける回数**の
    ほうがずっと多いので、**平均でも割りません。**
    """
    row = next(r for r in hendo.overtake_grid() if r["上がった先"] == "4.0%")
    path = ((0, hendo.START_RATE), (hendo.RISE_AT, 0.040))
    on = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path)
    off = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path,
                         five_year_rule=False, cap_125=False)
    mean_on = sum(r["返済額"] for r in on["rows"]) / len(on["rows"])
    mean_off = sum(r["返済額"] for r in off["rows"]) / len(off["rows"])
    assert round(mean_on) == 162_185
    assert round(mean_off) == 151_182
    # 向きは同じ（平均でもルールありのほうが高い）
    assert mean_on > mean_off
    # **数は別**。平均の比を `何倍` に書かないこと
    assert round(mean_on / mean_off, 2) == 1.07
    assert row["何倍"] == "1.33倍"
