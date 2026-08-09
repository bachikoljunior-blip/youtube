"""**年収を上げたとき、手取りはいくら増えるのか。**

「年収が上がっても手取りが増えない」はよく言われるが、**いくら増えるのかを
自分の前提で計算した表は、ほとんど公開されていない。** 出回っているのは
年収ごとの手取り額の一覧で、**上げたぶんが何円残るか**（限界手取り率）ではない。
転職や昇給の判断に要るのは後者のほうです。

計算は `furusato.py` の表を使い回します。**同じ表を二度書かない。**
給与所得控除も所得税の速算表も、あちらの `check_tables()` が検算しています。
ここで書き写すと、片方だけ直したときに静かにずれます。

## この計算で見ないもの（前提として画面に出す）

- **住民税の均等割**（定額）は入れていません。**限界手取り率には影響しない**
  ためです（上げても下げても同額なので、増加分の計算で消えます）。
- **社会保険料は年収に対する一定率**として置いています。実際には
  標準報酬月額の等級で階段状に動き、厚生年金は上限（標準報酬月額65万円、
  年収でおよそ790万円）で頭打ちになります。**だから表は年収700万円までに
  したうえで、率は前提として画面に出します。**
- 所得控除は基礎控除だけです。扶養や保険料控除があると税は下がります。
"""
from __future__ import annotations

from .furusato import (BASIC_INCOME, BASIC_RESIDENT, INCOME_TAX_BRACKETS,
                       RECONSTRUCTION, RESIDENT_RATE, TYPICAL_SOCIAL_RATE,
                       salary_deduction)

ASSUMPTIONS = [
    "給与収入のみの人を想定しています。事業所得や不動産所得があると変わります",
    "所得控除は基礎控除だけで計算しています。扶養控除や保険料控除があると税は下がります",
    "社会保険料は年収に対する一定率として置いています。実際は標準報酬月額の等級で階段状に動きます",
    "厚生年金の保険料は標準報酬月額65万円（年収でおよそ790万円）で頭打ちになるため、表は年収700万円までにしています",
    "住民税の均等割（定額）は入れていません。上げても下げても同額なので、増える額の計算では消えます",
    "住民税の所得割は標準税率の10パーセントです。超過課税のある自治体では変わります",
    "所得税には復興特別所得税を含めています（1.021倍）",
]

# 年収をいくら上げたときの話をするか
RAISE = 500_000


def income_tax(taxable: int) -> int:
    """課税所得から所得税額を出す。**速算表の控除額は使わない。**

    速算表の「控除額」を書き写すと、写し間違えても数字はそれらしく出ます。
    区分ごとに積み上げれば、控除額の列そのものが要らなくなる。
    """
    if taxable <= 0:
        return 0
    tax = 0.0
    for i, (floor, rate) in enumerate(INCOME_TAX_BRACKETS):
        if taxable <= floor:
            break
        ceiling = (
            INCOME_TAX_BRACKETS[i + 1][0]
            if i + 1 < len(INCOME_TAX_BRACKETS)
            else taxable
        )
        tax += (min(taxable, ceiling) - floor) * rate
    return int(tax * RECONSTRUCTION)


def resident_tax(income: int, social_rate: float) -> int:
    """住民税の所得割。均等割は入れない（この計算では消える）。"""
    social = int(income * social_rate)
    taxable = income - salary_deduction(income) - social - BASIC_RESIDENT
    return max(0, int(taxable * RESIDENT_RATE))


def take_home(income: int, social_rate: float = TYPICAL_SOCIAL_RATE) -> dict:
    """年収から手取りを出す。"""
    social = int(income * social_rate)
    taxable = max(0, income - salary_deduction(income) - social - BASIC_INCOME)
    it = income_tax(taxable)
    rt = resident_tax(income, social_rate)
    return {
        "年収": income,
        "社会保険料": social,
        "所得税": it,
        "住民税": rt,
        "手取り": income - social - it - rt,
    }


def marginal(income: int, raise_amount: int = RAISE,
             social_rate: float = TYPICAL_SOCIAL_RATE) -> dict:
    """**年収を上げたとき、手取りはいくら増えるか。**"""
    before = take_home(income, social_rate)
    after = take_home(income + raise_amount, social_rate)
    gain = after["手取り"] - before["手取り"]
    return {
        "年収": income,
        "上げた後": income + raise_amount,
        "手取り前": before["手取り"],
        "手取り後": after["手取り"],
        "手取り増": gain,
        "残る割合": gain / raise_amount,
        "消えた額": raise_amount - gain,
    }


def marginal_grid(incomes=(3_000_000, 4_000_000, 5_000_000, 6_000_000, 7_000_000),
                  social_rate: float = TYPICAL_SOCIAL_RATE) -> list[dict]:
    return [marginal(i, RAISE, social_rate) for i in incomes]


def social_rate_grid(income: int = 5_000_000,
                     rates=(0.13, 0.14, 0.15, 0.16, 0.17)) -> list[dict]:
    """**社会保険料率の置き方で、残る割合がどれだけ動くか。**

    ここが一番効く前提なので、動かして見せる。
    """
    return [dict(marginal(income, RAISE, r), 率=r) for r in rates]


def check_tables() -> None:
    """**取り違えても、それらしい数字が出てしまう計算です。**

    だから中身を書き写した検算ではなく、**手で解いた答え**と突き合わせます。
    実装を変えたら、こちらの数字も手で解き直すこと。
    """
    # 年収500万円・社会保険料率15% を手で解いた値
    #   給与所得控除 = 500万 × 0.2 + 44万 = 144万
    #   給与所得     = 500万 - 144万 = 356万
    #   社会保険料   = 75万
    #   所得税の課税所得 = 356万 - 75万 - 48万 = 233万
    #   所得税 = (195万 × 5% + 38万 × 10%) × 1.021
    #          = (9.75万 + 3.8万) × 1.021 = 13.55万 × 1.021 = 138,345円
    #   住民税の課税所得 = 356万 - 75万 - 43万 = 238万 → 所得割 23.8万円
    #   手取り = 500万 - 75万 - 138,345 - 238,000 = 3,873,655円
    got = take_home(5_000_000, 0.15)
    for key, want in (
        ("社会保険料", 750_000),
        ("所得税", 138_345),
        ("住民税", 238_000),
        ("手取り", 3_873_655),
    ):
        if got[key] != want:
            raise AssertionError(
                f"年収500万・料率15%の{key}が {got[key]:,}円。"
                f"手で解くと {want:,}円 になります。表の取り違えを疑うこと"
            )

    # 給与所得控除の区分の境目。furusato 側を壊したらここで気づく。
    if salary_deduction(6_600_000) != 1_760_000:
        raise AssertionError("給与所得控除の660万円の区分がずれています")
    if salary_deduction(9_000_000) != 1_950_000:
        raise AssertionError("給与所得控除の上限（195万円）がずれています")

    # 所得税は課税所得が増えれば必ず増える（区分の境目で逆転しないこと）
    prev = -1
    for taxable in range(0, 12_000_000, 50_000):
        now = income_tax(taxable)
        if now < prev:
            raise AssertionError(f"課税所得 {taxable:,}円 で所得税が減りました")
        prev = now

    # **上げたぶんが全部消えることはない。** 逆転していたら計算違い。
    for row in marginal_grid():
        if not 0.0 < row["残る割合"] < 1.0:
            raise AssertionError(
                f"年収{row['年収']:,}円 の残る割合が {row['残る割合']:.3f}。"
                "0〜1の外に出ています"
            )


def main() -> None:
    check_tables()
    print("検算: 通過\n")

    print(f"=== 年収を{RAISE // 10_000}万円上げたとき手取りはいくら増えるか ===")
    print(f"（社会保険料率 {TYPICAL_SOCIAL_RATE:.0%} で計算）")
    print(f"{'年収':>10}{'上げた後':>10}{'手取り増':>12}{'残る割合':>10}{'消えた額':>12}")
    for r in marginal_grid():
        print(f"{r['年収']//10_000:>8}万{r['上げた後']//10_000:>9}万"
              f"{r['手取り増']:>11,}円{r['残る割合']:>9.1%}{r['消えた額']:>11,}円")

    print("\n=== 年収べつの手取り ===")
    print(f"{'年収':>10}{'社会保険料':>12}{'所得税':>11}{'住民税':>11}{'手取り':>12}")
    for i in (3_000_000, 4_000_000, 5_000_000, 6_000_000, 7_000_000):
        t = take_home(i)
        print(f"{i//10_000:>8}万{t['社会保険料']:>11,}円{t['所得税']:>10,}円"
              f"{t['住民税']:>10,}円{t['手取り']:>11,}円")

    print(f"\n=== 社会保険料率の置き方で残る割合がどれだけ動くか（年収500万）===")
    print(f"{'料率':>8}{'手取り増':>12}{'残る割合':>10}")
    for r in social_rate_grid():
        print(f"{r['率']:>7.0%}{r['手取り増']:>11,}円{r['残る割合']:>9.1%}")

    print("\n=== この計算の前提 ===")
    for a in ASSUMPTIONS:
        print(f"- {a}")


if __name__ == "__main__":
    main()
