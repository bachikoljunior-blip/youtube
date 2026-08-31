"""亡くなった人の未支給年金が、何か月分になるか。

**一般の解説は「亡くなった月の分まで年金は出ます。遺族が請求してください」で止まります。**
その先に、口を開けている段が3つあります。

1つめ。**受け取れるのは1か月分から3か月分まで、3倍の幅があります。**
年金は偶数月の15日に前の2か月分をまとめて払う仕組みなので（国民年金法18条3項）、
**亡くなった日が偶数月の15日の前か後かで、まだ払われていない月数が変わります。**
金額も年齢も加入歴も関係ありません。**カレンダーだけで決まります。**

2つめ。**1年365日のうち、3か月分に当たるのは半分もありません。**
偶数月の1日から14日までだけが3か月分で、それ以外は2か月分か1か月分です。

3つめ。**未支給年金は相続財産ではなく、請求した人の一時所得です。**
一時所得には500,000円の特別控除があり、さらに残りの2分の1しか課税されないので、
**3か月分でも税金が出ないことがほとんどです。**ただし他に一時所得があると、
その控除は先に使われています。

この表が出す数字（実行して出たものを、丸めずに写しています）:

- 年金月額150,000円の人が4月14日に亡くなると未支給は**450,000円**、
  2日あとの4月16日なら**150,000円**。**300,000円ちがいます**
- 1年365日のうち、3か月分に当たるのは**84日**、2か月分が**184日**、
  1か月分が**97日**です。3か月分は**0.2301**しかありません
- 年金月額150,000円の3か月分450,000円は、他に一時所得が無ければ課税所得**0円**。
  月額200,000円の3か月分600,000円だと課税所得は**50,000円**になります
- 請求しないまま5年の時効が過ぎると、年金月額150,000円・3か月分で
  **450,000円**がまるごと消えます
"""
from __future__ import annotations

import calendar

from . import _checks

# ---- 制度の値（国民年金法18条・19条、厚生年金保険法36条・37条）--------------

PAY_DAY = 15                    # 偶数月の15日に支払う（国年法18条3項）
MONTHS_PER_PAYMENT = 2          # 1回の支払でまとめて出る月数
TIME_LIMIT_YEARS = 5            # 未支給年金の請求権の時効（会計法30条）

ICHIJI_DEDUCTION = 500_000      # 一時所得の特別控除（所得税法34条3項）
ICHIJI_HALF = 0.5               # 一時所得は2分の1だけ課税される（所得税法22条2項）

MIN_MONTHS = 1                  # まだ払われていない月数の下限
MAX_MONTHS = 3                  # 同じく上限

ASSUMPTIONS = [
    "亡くなった人に払われずに残った年金、いわゆる未支給年金で計算しています。"
    "年金は亡くなった月の分まで出ます",
    "年金は偶数月の15日に、その前の2か月分をまとめて払う仕組みで置いています。"
    "2月に12月分と1月分、4月に2月分と3月分という順です",
    "15日が土日祝日のときに前倒しになる扱いは入れていません。"
    "入れると15日の前後の線が数日ずれます",
    "年金月額は制度の値ではなく、この計算での仮定です。"
    "50,000円から250,000円までを並べ、代表として150,000円を使っています",
    "未支給年金は相続財産ではなく、請求した人の一時所得として扱っています。"
    "特別控除は500,000円で、残りの2分の1だけが課税されます",
    "請求できるのは生計を同じくしていた遺族で、"
    "配偶者、子、父母、孫、祖父母、兄弟姉妹、それ以外の3親等内の親族の順です。"
    "順位そのものは金額に影響しないので、表には入れていません",
    "請求権の時効は5年としています",
    "年金額の改定や、亡くなった月の途中で額が変わる場合は入れていません",
    "加給年金や振替加算は入れていません",
]


def unpaid_months(month: int, day: int) -> int:
    """亡くなった月と日から、まだ払われていない月数を出す。

    偶数月の15日に「前の2か月分」が出る。だから

        偶数月の15日以後に死亡  → その月の分だけ残る          → 1か月
        奇数月に死亡            → 前の月とその月が残る        → 2か月
        偶数月の15日より前に死亡 → 前々月・前月・その月が残る → 3か月
    """
    if month % 2 == 0:
        return 1 if day >= PAY_DAY else 3
    return 2


def amount(monthly: float, month: int, day: int) -> float:
    """未支給年金の額。"""
    return monthly * unpaid_months(month, day)


def by_day(monthly: float = 150_000, month: int = 4) -> list[dict]:
    """偶数月の日べつに、未支給年金の額。**15日の前後で3倍ちがう。**"""
    rows = []
    for day in (1, 10, 13, 14, 15, 16, 20, 28):
        rows.append({
            "亡くなった日": day,
            "未支給の月数": unpaid_months(month, day),
            "未支給年金の額": round(amount(monthly, month, day)),
        })
    return rows


def by_month(monthly: float = 150_000, day: int = 10) -> list[dict]:
    """亡くなった月べつに、未支給年金の額。日は10日でそろえている。"""
    rows = []
    for month in range(1, 13):
        rows.append({
            "亡くなった月": month,
            "未支給の月数": unpaid_months(month, day),
            "未支給年金の額": round(amount(monthly, month, day)),
        })
    return rows


def by_monthly() -> list[dict]:
    """年金月額べつに、1か月分から3か月分までの幅。"""
    rows = []
    for monthly in (50_000, 100_000, 150_000, 200_000, 250_000):
        rows.append({
            "年金月額": int(monthly),
            "1か月分": int(monthly * MIN_MONTHS),
            "3か月分": int(monthly * MAX_MONTHS),
            "いちばん多い日と少ない日の差": int(monthly * (MAX_MONTHS - MIN_MONTHS)),
        })
    return rows


def day_census(year: int = 2026) -> list[dict]:
    """1年365日を、未支給が何か月分になる日かで数える。"""
    counts = {1: 0, 2: 0, 3: 0}
    total = 0
    for month in range(1, 13):
        for day in range(1, calendar.monthrange(year, month)[1] + 1):
            counts[unpaid_months(month, day)] += 1
            total += 1
    return [{
        "未支給の月数": months,
        "その日数": counts[months],
        "1年に占める割合": round(counts[months] / total, 4),
    } for months in (1, 2, 3)]


def ichiji_taxable(gross: float, other: float = 0.0) -> float:
    """一時所得の課税所得。特別控除500,000円のあと、残りの2分の1。"""
    left = max(ICHIJI_DEDUCTION - other, 0.0)
    return max(gross - left, 0.0) * ICHIJI_HALF


def tax_table(months: int = MAX_MONTHS) -> list[dict]:
    """年金月額べつに、未支給年金の課税所得。他に一時所得は無いものとする。"""
    rows = []
    for monthly in (50_000, 100_000, 150_000, 200_000, 250_000, 300_000):
        gross = monthly * months
        rows.append({
            "年金月額": int(monthly),
            f"{months}か月分": int(gross),
            "課税される所得": round(ichiji_taxable(gross)),
        })
    return rows


def other_income_table(monthly: float = 150_000,
                       months: int = MAX_MONTHS) -> list[dict]:
    """他に一時所得があると、特別控除が先に使われている。"""
    gross = monthly * months
    rows = []
    for other in (0, 100_000, 200_000, 300_000, 400_000, 500_000):
        rows.append({
            "ほかの一時所得": int(other),
            "残っている特別控除": int(max(ICHIJI_DEDUCTION - other, 0)),
            "課税される所得": round(ichiji_taxable(gross, other)),
        })
    return rows


def timeout_table(monthly: float = 150_000) -> list[dict]:
    """請求しないまま時効が来ると、いくら消えるか。"""
    rows = []
    for months in (1, 2, 3):
        rows.append({
            "未支給の月数": months,
            "消える額": int(monthly * months),
            "時効までの年数": TIME_LIMIT_YEARS,
        })
    return rows


def grid() -> list[dict]:
    """図解の元になる表。"""
    return by_day()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""

    # 1. 法令が名指ししている値
    _checks.statutory(PAY_DAY, 15, "年金の支払日", source="国民年金法18条3項")
    _checks.statutory(MONTHS_PER_PAYMENT, 2, "1回の支払でまとめて出る月数",
                      source="国民年金法18条3項")
    _checks.statutory(ICHIJI_DEDUCTION, 500_000, "一時所得の特別控除",
                      source="所得税法34条3項")
    _checks.statutory(ICHIJI_HALF, 0.5, "一時所得の課税割合",
                      source="所得税法22条2項")
    _checks.statutory(TIME_LIMIT_YEARS, 5, "未支給年金の時効", source="会計法30条")
    _checks.ratio(ICHIJI_HALF, "一時所得の課税割合")

    # 2. **主題その1**: 偶数月の15日の前後で3倍ちがう。
    _checks.rounding(unpaid_months(4, 14), MAX_MONTHS, "4月14日の未支給の月数")
    _checks.rounding(unpaid_months(4, 16), MIN_MONTHS, "4月16日の未支給の月数")
    _checks.rounding(unpaid_months(4, 15), MIN_MONTHS, "4月15日の未支給の月数")
    _checks.greater(amount(150_000, 4, 14), amount(150_000, 4, 16),
                    "15日より前の日の未支給が、15日以後の日以下")
    _checks.rounding(round(amount(150_000, 4, 14) - amount(150_000, 4, 16)),
                     300_000, "4月14日と4月16日の差")

    # 3. **主題その2**: 奇数月はいつでも2か月分。**日で動かない。**
    for day in (1, 14, 15, 16, 28):
        _checks.rounding(unpaid_months(5, day), 2,
                         f"5月{day}日の未支給の月数（奇数月が日で動いている）")

    # 4. 月数は1から3の間に必ず収まること。
    for month in range(1, 13):
        for day in (1, 15, 28):
            months = unpaid_months(month, day)
            _checks.greater(MAX_MONTHS + 1, months, "未支給の月数が3を超えた")
            _checks.greater(months, MIN_MONTHS - 1, "未支給の月数が1を下回った")

    # 5. **主題その3**: 3か月分に当たる日は、1年の半分に遠く届かない。
    census = day_census()
    three = next(r for r in census if r["未支給の月数"] == 3)
    _checks.greater(0.5, three["1年に占める割合"],
                    "3か月分の日が1年の半分以上（偶数月の前半しか無いはず）")
    _checks.rounding(sum(r["その日数"] for r in census), 365,
                     "数えた日数の合計（2026年は平年）")

    # 6. **主題その4**: 特別控除のせいで、額が増えても課税所得は遅れて立ち上がる。
    _checks.rounding(round(ichiji_taxable(450_000)), 0,
                     "450,000円の一時所得の課税所得")
    _checks.rounding(round(ichiji_taxable(600_000)), 50_000,
                     "600,000円の一時所得の課税所得")
    _checks.increases_with(lambda g: ichiji_taxable(g),
                           [500_000, 600_000, 700_000, 900_000],
                           "一時所得が増えたのに課税所得が増えていない")
    _checks.increases_with(lambda o: ichiji_taxable(450_000, o),
                           [0, 200_000, 400_000, 500_000],
                           "ほかの一時所得が増えたのに課税所得が増えていない")

    # 7. 時効で消える額は、月数に比例すること。
    _checks.increases_with(lambda m: 150_000 * m, [1, 2, 3],
                           "月数が増えたのに消える額が増えていない")

    _checks.unique_by(by_month(), lambda r: r["亡くなった月"], "亡くなった月")
    _checks.unique_by(by_monthly(), lambda r: r["年金月額"], "年金月額")
    _checks.assumption_values(ASSUMPTIONS, name="mishikyu")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 偶数月の15日の前か後かで、未支給年金は3倍ちがう ===")
    for row in by_day():
        print(row)

    print("\n=== 亡くなった月べつに、未支給年金は何か月分か ===")
    for row in by_month():
        print(row)

    print("\n=== 年金月額べつに、いちばん多い日といちばん少ない日の差 ===")
    for row in by_monthly():
        print(row)

    print("\n=== 1年365日のうち、3か月分に当たるのは何日か ===")
    for row in day_census():
        print(row)

    print("\n=== 未支給年金は一時所得。特別控除50万円で課税所得はどうなるか ===")
    for row in tax_table():
        print(row)

    print("\n=== ほかに一時所得があると、特別控除は先に使われている ===")
    for row in other_income_table():
        print(row)

    print("\n=== 請求しないまま5年の時効が過ぎると、いくら消えるか ===")
    for row in timeout_table():
        print(row)
