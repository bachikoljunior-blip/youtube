"""住宅ローン控除で、**実際には取り戻せない額**を計算する。

狙いは制度の紹介ではない。「控除率0.7パーセント・最大13年」はどこにでもある。
ここで出したいのは、その控除可能額のうち **いくらが宙に浮くか** ——
つまり「取りこぼし」を、課税所得とローン残高の組み合わせで全部出したもの。

--------------------------------------------------------------------------
なぜ取りこぼしが出るのか
--------------------------------------------------------------------------
住宅ローン控除は **税額控除** で、納めた税金から差し引く形をとる。
だから **納めている税金より多くは戻らない。**

年末残高3000万円なら控除可能額は21万円だが、その年の所得税が12万円しかなければ、
所得税からは12万円しか引けない。残りの9万円は住民税に回るが、そこにも上限がある。

  住民税から引ける額 ＝ 課税総所得金額等の5パーセント、**ただし97,500円まで**

この上限に当たると、残りはどこからも戻らない。**繰り越しもできない。**
広告や記事に出る「最大○○万円」は控除可能額であって、受け取れる額ではない。

--------------------------------------------------------------------------
この計算が扱わないもの（意図的に外している）
--------------------------------------------------------------------------
**借入限度額は入れていない。** 住宅の種類と入居した年で変わり、改正も続いている。
確定した数字を確認できないものは使わない、という方針どおり、ここでは残高を
**入力として受け取る**。視聴者が自分の残高を入れる形にすれば、限度額の改正に
左右されずに答えが出る。

**年収からの換算も主役にしない。** 給与所得控除は令和2年以降変わっていないが、
基礎控除は改正が続いていて、令和8年分の確定した額を確認できていない。
だから計算の主役は **課税総所得金額**（源泉徴収票に載っている数字）にする。
視聴者は手元の紙を見ればよく、こちらが改正を追う必要もない。

これは制約ではなく、**そのほうが正確で、視聴者が自分で追試できる**という理由。

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
租税特別措置法の住宅借入金等特別控除。控除率 **0.7パーセント**（令和4年入居分から）。
所得税から引ききれない分の住民税からの控除上限は
**課税総所得金額等の5パーセント、かつ97,500円**（令和4年入居分から）。

所得税の速算表は平成27年分以降のもので、長く動いていない。
復興特別所得税（所得税額の2.1パーセント）は、住宅ローン控除を差し引いた
**あとの**所得税額に掛かる。ここも計算に入れている。
"""
from __future__ import annotations

from dataclasses import dataclass

from . import _checks

ASSUMPTIONS = [
    "控除率は0.7パーセントで計算しています。令和4年に入居した分からの率です",
    "課税総所得金額は源泉徴収票の「課税される所得金額」です。年収ではありません",
    "住民税から引ける額は、課税総所得金額等の5パーセントかつ9万7500円が上限です",
    "所得税から引ききれず住民税の上限にも当たった分は、どこからも戻りません。翌年に繰り越すこともできません",
    "借入限度額は住宅の種類と入居した年で変わるため、この計算には入れていません。年末残高をそのまま使っています",
    "所得税の速算表は平成27年分以降のものです",
    "復興特別所得税は、住宅ローン控除を差し引いたあとの所得税額に2.1パーセント掛かるものとしています",
    "ふるさと納税や医療費控除など、他の控除は入れていません",
]

CREDIT_RATE = 0.007            # 控除率 0.7%
RESIDENT_CAP_RATE = 0.05       # 住民税から引ける額は課税総所得等の5%まで
RESIDENT_CAP_YEN = 97_500      # かつ、この額まで
RECONSTRUCTION_TAX = 0.021     # 復興特別所得税

# 所得税の速算表（平成27年分以降）。(課税所得の上限, 税率, 控除額)
BRACKETS: list[tuple[int, float, int]] = [
    (1_950_000, 0.05, 0),
    (3_300_000, 0.10, 97_500),
    (6_950_000, 0.20, 427_500),
    (9_000_000, 0.23, 636_000),
    (18_000_000, 0.33, 1_536_000),
    (40_000_000, 0.40, 2_796_000),
    (10**12, 0.45, 4_796_000),
]


@dataclass(frozen=True)
class Result:
    """ある年の1回ぶんの結果。円単位。"""

    balance: int          # 年末のローン残高
    taxable: int          # 課税総所得金額
    credit: int           # 控除可能額（残高 × 0.7%）
    from_income_tax: int  # 所得税から引けた額
    from_resident: int    # 住民税から引けた額
    lost: int             # どこからも戻らなかった額

    @property
    def recovered(self) -> int:
        return self.from_income_tax + self.from_resident

    @property
    def lost_ratio(self) -> float:
        return self.lost / self.credit if self.credit else 0.0


def income_tax(taxable: int) -> int:
    """課税総所得金額から所得税額（復興特別所得税を除く）を出す。"""
    taxable = max(0, taxable)
    for cap, rate, deduct in BRACKETS:
        if taxable <= cap:
            return max(0, int(taxable * rate - deduct))
    return 0


def check_tables() -> None:
    """速算表と上限の値を、法令が名指ししている点で確かめる。

    表の書き写しは列ずれと桁落ちが起きるが、目で読み直しても見つからない。
    境目の値だけを不変条件に置き、外れたら止める。
    """
    if CREDIT_RATE != 0.007:
        raise ValueError(f"控除率が {CREDIT_RATE}。令和4年入居分からの率は 0.007")
    if RESIDENT_CAP_YEN != 97_500:
        raise ValueError(f"住民税からの控除上限が {RESIDENT_CAP_YEN}。法令の値は 97500")
    if RESIDENT_CAP_RATE != 0.05:
        raise ValueError(f"住民税からの控除上限の率が {RESIDENT_CAP_RATE}。法令の値は 0.05")

    # 速算表の境目。境目ちょうどの額は、下の区分の税率で計算される。
    for taxable, want in (
        (1_950_000, 97_500),      # 195万 × 5%
        (3_300_000, 232_500),     # 330万 × 10% - 97,500
        (6_950_000, 962_500),     # 695万 × 20% - 427,500
        (9_000_000, 1_434_000),   # 900万 × 23% - 636,000
        (18_000_000, 4_404_000),  # 1800万 × 33% - 1,536,000
    ):
        got = income_tax(taxable)
        if got != want:
            raise ValueError(f"課税所得{taxable:,}円の所得税が {got:,}円。速算表では {want:,}円")

    # 速算表の形・境目の連続・全体の向きは `_checks` にまとめてある
    # （12本が同じものを別々に書いていた）。上の「手で解いた値」は残すこと ——
    # あちらは**写し間違いそのもの**を捕まえていて、形の検査では代わりにならない。
    _checks.bracket_table(BRACKETS, income_tax, name="所得税の速算表")
    _checks.never_decreases(income_tax, range(0, 20_000_000, 250_000),
                            "課税所得に対する所得税額")

    # 所得税が控除可能額を上回るなら、取りこぼしは出ない
    rich = compute(30_000_000, 20_000_000)
    if rich.lost != 0:
        raise ValueError("所得税が十分にあるのに取りこぼしが出ている")

    # 課税所得が0なら、どこからも戻らない
    poor = compute(30_000_000, 0)
    if poor.recovered != 0 or poor.lost != poor.credit:
        raise ValueError("課税所得0で戻る額が出ている")

    # 住民税からの控除は上限を超えない
    mid = compute(40_000_000, 3_000_000)
    if mid.from_resident > RESIDENT_CAP_YEN:
        raise ValueError(f"住民税からの控除が上限を超えている: {mid.from_resident}")


def compute(balance: int, taxable: int) -> Result:
    """年末残高と課税総所得金額から、その年に実際に戻る額と取りこぼしを出す。"""
    credit = int(balance * CREDIT_RATE)
    tax = income_tax(taxable)

    from_income = min(credit, tax)
    remainder = credit - from_income
    cap = min(int(taxable * RESIDENT_CAP_RATE), RESIDENT_CAP_YEN)
    from_resident = min(remainder, max(0, cap))
    lost = credit - from_income - from_resident

    return Result(
        balance=balance, taxable=taxable, credit=credit,
        from_income_tax=from_income, from_resident=from_resident, lost=lost,
    )


def grid(balance: int, taxables: list[int] | None = None) -> list[Result]:
    """課税所得べつに、同じ残高で結果を並べる。"""
    taxables = taxables or [1_500_000, 2_000_000, 3_000_000, 4_000_000, 6_000_000]
    return [compute(balance, t) for t in taxables]


def balance_grid(taxable: int, balances: list[int] | None = None) -> list[Result]:
    """残高べつに、同じ課税所得で結果を並べる。"""
    balances = balances or [20_000_000, 30_000_000, 40_000_000, 45_000_000]
    return [compute(b, taxable) for b in balances]


def break_even_balance(taxable: int) -> int:
    """その課税所得で、取りこぼしが出はじめる年末残高を1万円単位で探す。

    ここがこの計算の主役。**「いくら借りると損しはじめるか」**は
    どこにも出ていないのに、借りる前にいちばん知りたい数字のはず。
    """
    step = 10_000
    balance = step
    while balance <= 100_000_000:
        if compute(balance, taxable).lost > 0:
            return balance - step
        balance += step
    return 100_000_000


def thirteen_years(balance: int, taxable: int, annual_rate: float = 0.01,
                   years: int = 13, term_years: int = 35) -> dict:
    """13年ぶんの合計。元利均等返済で残高が減っていくものとして積む。

    金利は仮定なので、必ず前提として画面に出すこと。
    """
    monthly_rate = annual_rate / 12
    months = term_years * 12
    if monthly_rate > 0:
        factor = (1 + monthly_rate) ** months
        payment = balance * monthly_rate * factor / (factor - 1)
    else:
        payment = balance / months

    remaining = float(balance)
    total_credit = total_recovered = total_lost = 0
    rows = []
    for year in range(1, years + 1):
        for _ in range(12):
            interest = remaining * monthly_rate
            remaining = max(0.0, remaining - (payment - interest))
        r = compute(int(remaining), taxable)
        total_credit += r.credit
        total_recovered += r.recovered
        total_lost += r.lost
        rows.append({"年": year, "残高": int(remaining), "控除可能": r.credit,
                     "戻る": r.recovered, "取りこぼし": r.lost})

    return {
        "控除可能額の合計": total_credit,
        "実際に戻る合計": total_recovered,
        "取りこぼしの合計": total_lost,
        "取りこぼしの割合": total_lost / total_credit if total_credit else 0.0,
        "年ごと": rows,
    }


if __name__ == "__main__":
    check_tables()
    print("速算表と上限の検査: 通過\n")

    print("=== 年末残高3000万円のとき、課税所得べつに1年で戻る額 ===")
    for r in grid(30_000_000):
        print(f"  課税所得{r.taxable // 10_000:>4d}万  控除可能{r.credit:>7,}円  "
              f"所得税から{r.from_income_tax:>7,}  住民税から{r.from_resident:>6,}  "
              f"取りこぼし{r.lost:>7,}円（{r.lost_ratio * 100:4.1f}%）")

    print("\n=== 取りこぼしが出はじめる年末残高 ===")
    for taxable in (1_500_000, 2_000_000, 3_000_000, 4_000_000, 6_000_000):
        be = break_even_balance(taxable)
        print(f"  課税所得{taxable // 10_000:>4d}万  →  年末残高 {be:,}円 まで")

    print("\n=== 13年ぶんの合計（3000万円・35年・金利1.0%） ===")
    for taxable in (2_000_000, 3_000_000, 6_000_000):
        t = thirteen_years(30_000_000, taxable)
        print(f"  課税所得{taxable // 10_000:>4d}万  控除可能{t['控除可能額の合計']:>9,}円  "
              f"戻る{t['実際に戻る合計']:>9,}円  "
              f"取りこぼし{t['取りこぼしの合計']:>9,}円（{t['取りこぼしの割合'] * 100:4.1f}%）")
