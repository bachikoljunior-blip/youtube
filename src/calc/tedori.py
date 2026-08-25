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
    "社会保険料は年収に対する一定率15パーセントとして置いています。"
    "実際は標準報酬月額の等級で階段状に動きます",
    "厚生年金の保険料は標準報酬月額65万円（年収でおよそ790万円）で頭打ちになるため、表は年収700万円までにしています",
    "住民税の均等割（定額）は入れていません。上げても下げても同額なので、増える額の計算では消えます",
    "住民税の所得割は標準税率の10パーセントです。超過課税のある自治体では変わります",
    "所得税には復興特別所得税を含めています（1.021倍）",
    "給与所得控除は速算表の算式で計算しています。収入が660万円未満の場合、所得税法別表第五では千円単位の区分表になるため、数百円ずれることがあります",
]

# **660万円は「控除額が減る」段差ではない。**
# 額そのものは連続している（どちらの式でも 176万円）。
#   660万円以下   収入 × 20% + 44万円  → 0.2 × 660万 + 44万 = 176万円
#   660万円超     収入 × 10% + 110万円 → 0.1 × 660万 + 110万 = 176万円
# 変わるのは**増え方**で、収入を1万円上げたときに控除が増える額が
# 2千円から1千円に落ちる。だから**昇給の手取りの残り方**だけが段になる。
# 動画でここを「控除が減る」と言うと誤りになる。言い方を変えないこと。
SALARY_DEDUCTION_KNEE = 6_600_000

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


def knee_grid(incomes=(6_200_000, 6_400_000, 6_500_000, 6_800_000),
              step: int = 100_000,
              social_rate: float = TYPICAL_SOCIAL_RATE) -> list[dict]:
    """**段差は1つではなく、2つが20万円のあいだに続けて来る。**

    `marginal_grid()` は50万円刻みなので、**この2つを平均してならしてしまう。**
    10万円刻みにすると分かれて見える。

        年収 約645万円  所得税率が 10% → 20%（課税所得が330万円を超える）
        年収   660万円  給与所得控除の伸びが 10万円あたり2万円 → 1万円

        残る割合 71.9% →（645万）→ 65.2% →（660万）→ 62.2%

    **これを取り違えないこと。** 「660万円の壁」で説明できるのは
    **落差の半分だけ**で、大きいほうの段は**その手前の所得税率**です。
    2026-08-09、10万円刻みで引き直して初めて分かれた。
    50万円刻みの表だけを見ていたら、**全部を給与所得控除のせいにしていた。**

    `driver` にどちらの段かを入れて返す。**数字と原因を離さない。**
    """
    out = []
    for i in incomes:
        r = marginal(i, step, social_rate)
        before = salary_deduction(i)
        after = salary_deduction(i + step)
        soc = int(i * social_rate)
        taxable = i - before - soc - BASIC_INCOME
        taxable_after = (i + step) - after - int((i + step) * social_rate) - BASIC_INCOME
        drivers = []
        if _bracket(taxable) != _bracket(taxable_after):
            drivers.append(f"所得税率が{_bracket(taxable):.0%}から{_bracket(taxable_after):.0%}へ")
        if after - before < step * 0.2 - 1:
            drivers.append("給与所得控除の伸びが半分に")
        out.append(dict(r, driver=("・".join(drivers) if drivers else "段差なし")))
    return out


def raise_size_grid(income: int = 6_400_000,
                    raises=(100_000, 200_000, 300_000, 500_000,
                            800_000, 1_000_000, 1_500_000),
                    social_rate: float = TYPICAL_SOCIAL_RATE) -> list[dict]:
    """**同じ年収からでも、昇給額を変えると「残る割合」が変わる。**

    `marginal_grid()` は 50万円、`knee_grid()` は 10万円で固定していて、
    **昇給額そのものを動かした節がありませんでした。** 段は年収の側に立っているので、
    昇給がまたぐ段の数は昇給額で変わり、**残る割合は昇給額に対して単調ではありません。**

    残る割合は昇給額に対して**必ず下がる**（1円ずつの残りが弱く減る平均なので単調非増加）。
    **値打ちは下がることではなく、下がり幅のほうにある** —— 幅は「段からの距離」で決まり、
    **段から遠い年収では、昇給額をいくら変えても1円も動きません。**

        年収640万（段のすぐ手前）  +10万 71.35% → +150万 **63.00%**（**8.35ポイント**）
        年収500万（段から遠い）    +10万 71.86% → +150万 **71.83%**（**0.03ポイント**）
    """
    rows = []
    for up in raises:
        r = marginal(income, up, social_rate)
        rows.append({
            "年収": income,
            "昇給額": up,
            "上げた後": r["上げた後"],
            "手取り増": r["手取り増"],
            "消えた額": r["消えた額"],
            "残る割合": round(r["残る割合"], 4),
            "1万円あたり手取り増": round(r["手取り増"] / up * 10_000),
        })
    return rows


def _bracket(taxable: int) -> float:
    rate = INCOME_TAX_BRACKETS[0][1]
    for floor, r in INCOME_TAX_BRACKETS:
        if taxable >= floor:
            rate = r
    return rate


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

    # **660万円で控除額そのものは飛ばない。** 両側の式が同じ値を返すこと。
    # ここが飛んでいたら「控除が減る」という誤った説明を作りかねない。
    knee = SALARY_DEDUCTION_KNEE
    if salary_deduction(knee) != 1_760_000:
        raise AssertionError("給与所得控除の660万円の区分がずれています")
    if salary_deduction(knee + 1) - salary_deduction(knee) > 1:
        raise AssertionError(
            "660万円の前後で給与所得控除の額が飛んでいます。"
            "**段差になるのは増え方だけ**で、額は連続しているはずです"
        )
    # 増え方が 20% から 10% に落ちること（動画の主張そのもの）
    below = salary_deduction(knee - 100_000) - salary_deduction(knee - 200_000)
    above = salary_deduction(knee + 200_000) - salary_deduction(knee + 100_000)
    if not (19_000 <= below <= 21_000 and 9_000 <= above <= 11_000):
        raise AssertionError(
            f"10万円あたりの控除の増え方が 660万円以下で {below:,}円、"
            f"超で {above:,}円。2万円→1万円 になっていません"
        )
    if salary_deduction(9_000_000) != 1_950_000:
        raise AssertionError("給与所得控除の上限（195万円）がずれています")

    # 所得税は課税所得が増えれば必ず増える（区分の境目で逆転しないこと）
    prev = -1
    for taxable in range(0, 12_000_000, 50_000):
        now = income_tax(taxable)
        if now < prev:
            raise AssertionError(f"課税所得 {taxable:,}円 で所得税が減りました")
        prev = now

    # **段差は2つある。** 片方だけを見て「660万円の壁」と言わないための固定。
    # 2026-08-09、50万円刻みの表しか見ていなかったので、**大きいほうの段
    # （所得税率 10%→20%、年収およそ645万円）を給与所得控除のせいにしかけた。**
    steps = {r["年収"]: round(r["残る割合"], 3) for r in knee_grid()}
    want = {6_200_000: 0.719, 6_400_000: 0.714, 6_500_000: 0.652, 6_800_000: 0.622}
    for income, ratio in want.items():
        if steps.get(income) != ratio:
            raise AssertionError(
                f"年収{income:,}円 からの10万円昇給で残る割合が {steps.get(income)}。"
                f"{ratio} のはずです。**2つの段差のどちらかが動いています**"
            )
    # 原因の割り当てそのものも固定する（数字が合っていても説明が入れ替わりうる）。
    # **ここで一度間違えた。** 所得税率が変わるのは 650万→660万 ではなく
    # **640万→650万**（課税所得が330万を超えるのがこの区間）。
    # 650万の行はすでに20%帯に入っていて、控除の伸びもまだ2万円なので**段は無い**。
    # 残る割合は 71.9%（10%帯・控除2万）→ 65.2%（20%帯・控除2万）
    # → 62.2%（20%帯・控除1万）の3段。
    drivers = {r["年収"]: r["driver"] for r in knee_grid()}
    if "所得税率" not in drivers[6_400_000]:
        raise AssertionError("640万→650万 の段が所得税率だと出ていません")
    if "給与所得控除" not in drivers[6_800_000]:
        raise AssertionError("660万円より上の段が給与所得控除だと出ていません")
    if drivers[6_500_000] != "段差なし":
        raise AssertionError(
            f"650万→660万 に段があることになっています（{drivers[6_500_000]}）。"
            "**この区間は20%帯のままで、控除の伸びも2万円のままです**"
        )

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

    print("\n=== 段差は2つ。10万円の昇給がいくら残るか ===")
    print("（**「660万円の壁」で説明できるのは落差の半分だけ。**"
          "大きいほうは手前の所得税率です）")
    print(f"{'年収':>10}{'上げた後':>10}{'手取り増':>12}{'残る割合':>10}  原因")
    for r in knee_grid():
        print(f"{r['年収']//10_000:>8}万{r['上げた後']//10_000:>9}万"
              f"{r['手取り増']:>11,}円{r['残る割合']:>9.1%}  {r['driver']}")

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

    print("\n=== 昇給額を変えて残る割合が動くのは、段のすぐ手前にいる人だけ ===")
    print(f"  前提: 社会保険料率は年収に対する一定率{TYPICAL_SOCIAL_RATE:.0%} / "
          f"所得控除は基礎控除だけ / 住民税の所得割は標準税率{RESIDENT_RATE:.0%} / "
          f"所得税は復興特別所得税を含む（{RECONSTRUCTION}倍）")
    for base in (6_400_000, 5_000_000):
        rows = raise_size_grid(base)
        width = rows[0]["残る割合"] - rows[-1]["残る割合"]
        print(f"  --- 年収{base:,}円から（昇給{rows[0]['昇給額']:,}円と"
              f"{rows[-1]['昇給額']:,}円で {width * 100:.2f}ポイントの差）---")
        for row in rows:
            print(f"    昇給{row['昇給額']:>9,d}円  手取り増{row['手取り増']:>9,d}円  "
                  f"消えた{row['消えた額']:>9,d}円  残る割合 {row['残る割合']:.2%}  "
                  f"1万円あたり手取り+{row['1万円あたり手取り増']:>5,d}円")

    print("\n=== この計算の前提 ===")
    for a in ASSUMPTIONS:
        print(f"- {a}")


    # **昇給額を動かしたときの残る割合は、単調に下がる**（1円ずつの残りの平均だから）。
    for start in (5_000_000, 6_400_000):
        ratios = [r["残る割合"] for r in raise_size_grid(start)]
        for a, b in zip(ratios, ratios[1:]):
            if b > a + 1e-9:
                raise AssertionError(
                    f"年収{start:,}円で、昇給額を増やしたのに残る割合が上がりました "
                    f"（{a} → {b}）。1円ずつの残りは弱く減るので、平均は下がるはずです")
    # **下がり幅は「段からの距離」で決まる。** 段のすぐ手前と、段から遠い年収で桁が違うこと。
    near = [r["残る割合"] for r in raise_size_grid(6_400_000)]
    far = [r["残る割合"] for r in raise_size_grid(5_000_000)]
    if not (near[0] - near[-1] > 0.08):
        raise AssertionError(
            f"年収640万円の下がり幅が {near[0] - near[-1]:.4f}。8ポイントを超えるはずです")
    if not (far[0] - far[-1] < 0.001):
        raise AssertionError(
            f"年収500万円の下がり幅が {far[0] - far[-1]:.4f}。"
            "段から遠いので、ほとんど動かないはずです")


if __name__ == "__main__":
    main()
