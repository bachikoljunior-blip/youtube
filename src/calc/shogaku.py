"""奨学金の返還を、月ごとに解いて実額を出す。

    python -m src.calc.shogaku

## この計算で出したいこと

奨学金の解説は「第一種は無利子、第二種は有利子で上限が年3パーセント」で止まる。
**その3パーセントが、返し終わるまでにいくらになるのかは、どこにも出ていない。**
利率だけ書いてあっても、元利均等は毎月の利息が残高に比例して減るので、
掛け算では出ない。**月ごとに解かないと出ない。**

ここで解くと、次の5つが出る。

1. **月10万円を4年 借りて、15年で返すと 5,966,625円。**
   借りたのは 4,800,000円 なので、利息だけで 1,166,625円。
   毎月の返還額は 33,148円 で、無利子の 26,667円 より 6,481円 多い。
2. **減額返還で月々を3分の1にすると、完済は67歳。**
   毎月は 11,049円 まで下がるが、返還年数は 15年 から 45年 に延びる。
   **返還の総額は 5,966,625円 のまま1円も変わらない。**
   動くのは完済する年齢だけで、22歳 で始めた人が 67歳 で終わる。
3. **同じ100万円の繰上返還でも、1年目なら 441,853円、11年目なら 83,310円。**
   効きは 5倍 以上ちがう。短くなる月数は 43.5か月 と 32.7か月 で
   1年ぶんも変わらないのに、**削減額のほうは 358,543円 も開く。**
4. **返還年数を15年から20年に延ばすと、毎月は 33,148円 から 26,621円 に下がるが、
   利息は 1,166,625円 から 1,588,964円 に増える。**
   月々を 6,527円 軽くするのに、422,339円 払っている。
5. **返還期限猶予を通算10年 使っても、返還の総額は 5,966,625円 で変わらない。**
   変わるのは完済する年齢で、37歳 から 47歳 になる。

## 前提（動画にそのまま出すこと）

- 日本学生支援機構の奨学金。第一種は利率 年0パーセント、
  第二種の利率は法令の上限である 年3パーセント を仮定として置く
- 在学中は利息が付かない。返還が始まる時点の元金は借りた額そのもの
- 毎月の返還額が最後まで変わらない元利均等。実際の割賦金は貸与総額ごとの
  区分で決まるので、ここでは返還年数のほうを10年から20年まで並べる
- 返還が始まるのは貸与が終わった月の6か月後（3月に終わるなら10月）
- 大学を22歳で出て、その年から返還を始めるものとして完済年齢を出す
- 機関保証の保証料と延滞金は入れていない。所得連動返還方式は入れていない

## 根拠の探し方（動画の説明欄用。URLは書かない）

- 第二種の利率の上限（年3パーセント） … 独立行政法人日本学生支援機構法施行令2条
- 第一種が無利子であること … 独立行政法人日本学生支援機構法13条
- 据置期間・減額返還・返還期限猶予 … 日本学生支援機構「返還のてびき」
"""
from __future__ import annotations

import math

from . import _checks

# ---- 制度の値。**長く動いていないものだけをここに置く** ----------------
#
# 第二種奨学金（利息の付くほう）の利率の上限。
# 独立行政法人日本学生支援機構法施行令2条が「年3パーセントを超えない」と定めている。
# **実際に適用される利率はこれより低いことが多いが、上限はここで止まる。**
RATE_CAP = 0.03

# 第一種奨学金（利息の付かないほう）の利率。
RATE_FIRST = 0.0

# 貸与が終わってから返還が始まるまでの据置期間（月）。
# 貸与終了の翌月から数えて7か月目に初回の返還が来る（3月終了なら10月）。
DEFER_MONTHS = 6

# 返還期限猶予を受けられる通算の年数の上限。
DEFER_LIMIT_YEARS = 10

# 減額返還で選べる、月々の返還額の割合。
REDUCE_RATIOS = (0.5, 1 / 3)

# 大学を出る年齢。返還はその年から始まるものとして置く。
GRAD_AGE = 22

ASSUMPTIONS = [
    "日本学生支援機構の奨学金の返還で計算しています。"
    "利息の付かない第一種と、利息の付く第二種の2つを並べます",
    "第二種の利率は制度の値ではなく、この計算での仮定です。"
    "法令の上限である年3パーセントと、"
    "低い側の例として年0.3パーセントを並べ、代表として年3パーセントを使っています",
    "第一種の利率は年0パーセントです",
    "在学中は利息が付かないものとしています。"
    "返還が始まる時点の元金は、借りた額そのものです",
    "毎月の返還額が最後まで変わらない元利均等で置いています。"
    "実際の割賦金は貸与総額ごとの区分で決まるので、"
    "ここでは返還年数のほうを10年から20年まで並べています",
    "返還が始まるのは貸与が終わった月の6か月後で、"
    "3月に貸与が終わるなら10月が初回です",
    "大学を22歳で出て、その年から返還を始めるものとして完済年齢を出しています",
    "減額返還は月々の返還額を2分の1か3分の1に減らし、"
    "そのぶん返還の期間が2倍か3倍に延びる仕組みとして置いています。"
    "返還する総額は変わりません",
    "返還期限猶予は通算10年までとしています",
    "機関保証を選んだときの保証料と、延滞したときの延滞金は入れていません。"
    "入れると第二種の負担はここに出る額より重くなります",
    "所得連動返還方式と、機関保証か人的保証かの違いは入れていません",
]


# ---- 計算 --------------------------------------------------------------
def monthly_payment(principal: float, annual_rate: float, years: int) -> float:
    """元利均等の毎月の返還額。**利率0でも割り算だけで出る。**"""
    n = years * 12
    if annual_rate == 0:
        return principal / n
    i = annual_rate / 12
    return principal * i / (1 - (1 + i) ** (-n))


def total_repaid(principal: float, annual_rate: float, years: int) -> float:
    """返還の総額。"""
    return monthly_payment(principal, annual_rate, years) * years * 12


def interest_of(principal: float, annual_rate: float, years: int) -> float:
    """利息の総額。"""
    return total_repaid(principal, annual_rate, years) - principal


def by_principal(annual_rate: float = RATE_CAP, years: int = 15) -> list[dict]:
    """貸与総額べつに、無利子と年3パーセントの差。"""
    rows = []
    for principal in (1_200_000, 2_400_000, 3_600_000, 4_800_000,
                      6_000_000, 7_200_000):
        rows.append({
            "貸与総額": int(principal),
            "無利子の総額": round(total_repaid(principal, RATE_FIRST, years)),
            "年3パーセントの総額": round(total_repaid(principal, annual_rate, years)),
            "その差": round(interest_of(principal, annual_rate, years)),
        })
    return rows


def by_lend_years(monthly_lend: float = 100_000,
                  annual_rate: float = RATE_CAP,
                  years: int = 15) -> list[dict]:
    """月々いくら借りるかを固定して、借りる年数べつに返還の総額。"""
    rows = []
    for lend_years in (2, 3, 4, 6):
        principal = monthly_lend * 12 * lend_years
        rows.append({
            "借りる年数": lend_years,
            "貸与総額": int(principal),
            "返還の総額": round(total_repaid(principal, annual_rate, years)),
            "そのうち利息": round(interest_of(principal, annual_rate, years)),
        })
    return rows


def by_rate(principal: float = 4_800_000, years: int = 15) -> list[dict]:
    """利率べつに、毎月の返還額と利息の総額。"""
    rows = []
    for rate in (0.0, 0.003, 0.005, 0.01, 0.02, RATE_CAP):
        rows.append({
            "年利率": rate,
            "毎月の返還額": round(monthly_payment(principal, rate, years)),
            "返還の総額": round(total_repaid(principal, rate, years)),
            "利息の総額": round(interest_of(principal, rate, years)),
        })
    return rows


def by_years(principal: float = 4_800_000,
             annual_rate: float = RATE_CAP) -> list[dict]:
    """返還年数べつに、毎月の返還額と利息。**延ばすほど月々は軽く、利息は重い。**"""
    rows = []
    for years in (10, 12, 14, 15, 18, 20):
        rows.append({
            "返還年数": years,
            "毎月の返還額": round(monthly_payment(principal, annual_rate, years)),
            "利息の総額": round(interest_of(principal, annual_rate, years)),
            "完済する年齢": GRAD_AGE + years,
        })
    return rows


def reduce_table(principal: float = 4_800_000,
                 annual_rate: float = RATE_CAP,
                 years: int = 15) -> list[dict]:
    """減額返還。**総額は変わらないのに、完済年齢だけが動く。**"""
    base = monthly_payment(principal, annual_rate, years)
    total = base * years * 12
    rows = [{
        "月々の割合": 1.0,
        "毎月の返還額": round(base),
        "返還年数": years,
        "返還の総額": round(total),
        "完済する年齢": GRAD_AGE + years,
    }]
    for ratio in REDUCE_RATIOS:
        stretched = round(years / ratio)
        rows.append({
            "月々の割合": round(ratio, 4),
            "毎月の返還額": round(base * ratio),
            "返還年数": stretched,
            "返還の総額": round(total),
            "完済する年齢": GRAD_AGE + stretched,
        })
    return rows


def prepay_saving(principal: float, annual_rate: float, years: int,
                  amount: float, after_years: int) -> dict:
    """返還開始から `after_years` 年目に `amount` を繰上返還したときの、利息の削減額。

    毎月の返還額は変えず、残高から差し引いて期間を短くする。
    """
    m = monthly_payment(principal, annual_rate, years)
    i = annual_rate / 12
    k = after_years * 12
    if i == 0:
        balance = principal - m * k
    else:
        balance = principal * (1 + i) ** k - m * ((1 + i) ** k - 1) / i
    paid_before = m * k
    left = max(balance - amount, 0.0)
    if left <= 0:
        months_left = 0.0
    elif i == 0:
        months_left = left / m
    else:
        months_left = -math.log(1 - left * i / m) / math.log(1 + i)
    after_total = paid_before + amount + m * months_left
    return {
        "繰上返還する年": after_years,
        "そのときの残高": round(balance),
        "繰上返還後の総額": round(after_total),
        "利息の削減額": round(total_repaid(principal, annual_rate, years) - after_total),
        "短くなる月数": round(years * 12 - k - months_left, 1),
    }


def prepay_table(principal: float = 4_800_000,
                 annual_rate: float = RATE_CAP,
                 years: int = 15,
                 amount: float = 1_000_000) -> list[dict]:
    """同じ100万円の繰上返還を、いつやるかで並べる。"""
    return [prepay_saving(principal, annual_rate, years, amount, k)
            for k in (1, 3, 5, 7, 9, 11)]


def defer_table(principal: float = 4_800_000,
                annual_rate: float = RATE_CAP,
                years: int = 15) -> list[dict]:
    """返還期限猶予を使った年数べつに、完済年齢。**総額は変わらない。**"""
    rows = []
    for waited in (0, 2, 5, DEFER_LIMIT_YEARS):
        rows.append({
            "猶予を使った年数": waited,
            "返還を始める年齢": GRAD_AGE + waited,
            "完済する年齢": GRAD_AGE + waited + years,
            "返還の総額": round(total_repaid(principal, annual_rate, years)),
        })
    return rows


def grid() -> list[dict]:
    """図解の元になる表。"""
    return by_principal()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""

    # 1. 法令が名指ししている値
    _checks.statutory(RATE_CAP, 0.03, "第二種奨学金の利率の上限",
                      source="独立行政法人日本学生支援機構法施行令2条")
    _checks.statutory(RATE_FIRST, 0.0, "第一種奨学金の利率",
                      source="独立行政法人日本学生支援機構法13条")
    _checks.statutory(DEFER_MONTHS, 6, "貸与が終わってから返還が始まるまでの月数",
                      source="日本学生支援機構の返還のてびき")
    _checks.statutory(DEFER_LIMIT_YEARS, 10, "返還期限猶予の通算の上限",
                      source="日本学生支援機構の返還のてびき")
    _checks.ratio(RATE_CAP, "第二種奨学金の利率の上限")

    # 2. **主題その1**: 利率が上がれば返還の総額は増える。
    _checks.increases_with(lambda r: total_repaid(4_800_000, r, 15),
                           [0.0, 0.005, 0.01, 0.02, RATE_CAP],
                           "利率が上がったのに返還の総額が増えていない")
    _checks.rounding(round(total_repaid(4_800_000, RATE_FIRST, 15)), 4_800_000,
                     "無利子で15年返したときの総額（元金と同じはず）")
    _checks.rounding(round(interest_of(4_800_000, RATE_FIRST, 15)), 0,
                     "無利子の利息")

    # 3. **主題その2**: 返還年数を延ばすと、月々は軽くなり利息は重くなる。
    _checks.decreases_with(lambda y: monthly_payment(4_800_000, RATE_CAP, y),
                           [10, 12, 15, 18, 20],
                           "返還年数を延ばしたのに毎月の返還額が減っていない")
    _checks.increases_with(lambda y: interest_of(4_800_000, RATE_CAP, y),
                           [10, 12, 15, 18, 20],
                           "返還年数を延ばしたのに利息が増えていない")

    # 4. **主題その3**: 減額返還は総額を変えない。**動くのは完済年齢だけ。**
    rows = reduce_table()
    totals = {r["返還の総額"] for r in rows}
    _checks.rounding(len(totals), 1,
                     "減額返還で返還の総額が変わっている（変わらないはず）")
    _checks.greater(rows[-1]["完済する年齢"], rows[0]["完済する年齢"],
                    "減額返還したのに完済年齢が遅くなっていない")
    _checks.greater(rows[0]["毎月の返還額"], rows[-1]["毎月の返還額"],
                    "減額返還したのに毎月の返還額が減っていない")

    # 5. **主題その4**: 同じ額の繰上返還でも、早いほど効く。
    _checks.decreases_with(
        lambda k: prepay_saving(4_800_000, RATE_CAP, 15, 1_000_000, k)["利息の削減額"],
        [1, 3, 5, 7, 9, 11],
        "繰上返還を遅らせたのに利息の削減額が減っていない")

    # 6. **主題その5**: 猶予は総額を変えない。**動くのは完済年齢だけ。**
    dt = defer_table()
    _checks.rounding(len({r["返還の総額"] for r in dt}), 1,
                     "猶予で返還の総額が変わっている（変わらないはず）")
    _checks.greater(dt[-1]["完済する年齢"], dt[0]["完済する年齢"],
                    "猶予を使ったのに完済年齢が遅くなっていない")

    # 7. 借りる年数が増えれば、返還の総額も増える。
    _checks.increases_with(
        lambda y: total_repaid(100_000 * 12 * y, RATE_CAP, 15),
        [2, 3, 4, 6],
        "借りる年数が増えたのに返還の総額が増えていない")

    _checks.unique_by(by_principal(), lambda r: r["貸与総額"], "貸与総額")
    _checks.unique_by(by_rate(), lambda r: r["年利率"], "年利率")
    _checks.unique_by(by_years(), lambda r: r["返還年数"], "返還年数")
    _checks.assumption_values(ASSUMPTIONS, name="shogaku")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 無利子と年3パーセントで、奨学金の返還総額はいくら違うか ===")
    for row in by_principal():
        print(row)

    print("\n=== 月10万円を借りる年数がちがうと、返還の総額はいくら変わるか ===")
    for row in by_lend_years():
        print(row)

    print("\n=== 利率が0.3パーセントと3パーセントで、毎月の返還額と利息 ===")
    for row in by_rate():
        print(row)

    print("\n=== 返還年数を10年から20年に延ばすと、月々と利息はどう動くか ===")
    for row in by_years():
        print(row)

    print("\n=== 減額返還は総額を変えない。変わるのは完済する年齢だけ ===")
    for row in reduce_table():
        print(row)

    print("\n=== 同じ100万円の繰上返還でも、何年目にやるかで削減額が変わる ===")
    for row in prepay_table():
        print(row)

    print("\n=== 返還期限猶予を使った年数べつに、完済する年齢 ===")
    for row in defer_table():
        print(row)
