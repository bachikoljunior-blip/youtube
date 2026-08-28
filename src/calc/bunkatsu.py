"""離婚したときの年金分割で、実際に移る年金額。

**一般の解説は「相手の年金の半分をもらえる」で止まります。**
その先に、口を開けている段が4つあります。

1つめ。**動くのは厚生年金の報酬比例部分だけです。**基礎年金は1円も動きません。
2つめ。**動くのは婚姻期間のぶんだけです。**加入40年のうち婚姻20年なら、
半分の半分、つまり全体の4分の1が上限になります。
3つめ。**「半分」は相手の額の半分ではなく、二人の合計を半分に割った線です。**
自分にも厚生年金があるなら、移るのは**差額の半分**です。
4つめ。**3号分割だけを請求すると、対象は2008年4月以後の期間だけです。**

この表が出す数字（実行して出たものを、丸めずに写しています）:

- 婚姻20年・相手の平均標準報酬額400,000円・自分は0円なら、移る年金は**年263,088円**。
  ひと月あたり **21,924円**です
- 自分にも平均標準報酬額200,000円があると、移るのは**年131,544円**まで落ちます。
  相手の額は1円も変わっていないのに、**ちょうど半分**になります
- 相手の厚生年金の加入が40年で婚姻が20年なら、移るのは相手の報酬比例部分の
  **0.25**です。基礎年金まで含めた「年金全体」で見ると、さらに下がります
- 2026年に離婚する人が3号分割だけを請求すると、1995年結婚なら移るのは**年236,779円**で、
  合意分割の **0.5806**しかありません。1990年結婚ならもっと開いて **0.5** です
- 2003年3月以前の期間は乗率が1000分の7.125で、2003年4月以後の1000分の5.481より
  大きい。同じ婚姻25年でも、1985年結婚なら**年399,881円**、2003年結婚なら
  **年328,860円**で、**いつ結婚したかで71,021円ちがいます**
- 請求を2年の期限まで放っておくと、25年受け取る人で**生涯6,577,200円**を失います。
  1日あたり **721円**です
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値（厚生年金保険法78条の2〜78条の14。長く動いていないものだけ）----

# 報酬比例部分の給付乗率（本来水準）。総報酬制が始まる2003年4月で切り替わる。
RATE_AFTER_2003 = 5.481 / 1000      # 2003年4月以後（平均標準報酬額・賞与込み）
RATE_BEFORE_2003 = 7.125 / 1000     # 2003年3月以前（平均標準報酬月額・賞与を含まない）

SPLIT_MAX = 0.5                     # 按分割合の上限（厚年法78条の3）
KIND3_RATE = 0.5                    # 3号分割の割合は一律2分の1（厚年法78条の14）
KIND3_START_YEAR = 2008             # 3号分割の対象は2008年4月以後の第3号期間
KIND3_START_MONTH = 4
CLAIM_LIMIT_YEARS = 2               # 請求期限は離婚の翌日から2年（厚年法78条の2）

TOTAL_MONTHS_2003 = (2003 - 1900) * 12 + 4   # 乗率が切り替わる月を通し番号で持つ

ASSUMPTIONS = [
    "離婚したときの厚生年金の分割で計算しています。"
    "分割されるのは厚生年金の報酬比例部分だけで、老齢基礎年金は1円も動きません",
    "報酬比例部分の年金額は、平均標準報酬額に給付乗率と加入月数を掛けて出しています。"
    "乗率は2003年4月以後が1000分の5.481、2003年3月以前が1000分の7.125です",
    "按分割合の上限は2分の1です。これは相手の額の半分ではなく、"
    "二人の対象期間の標準報酬総額を合わせたものを半分に割る線です",
    "3号分割の対象は2008年4月以後の第3号被保険者期間だけで、割合は一律2分の1です",
    "請求できるのは離婚した日の翌日から2年までです",
    "平均標準報酬額は婚姻期間を通して一定としています。"
    "代表として相手が月40万円、自分が月0円から30万円までを並べています",
    "物価や賃金による年金額の改定は入れていません。今の乗率のまま計算しています",
    "加給年金や振替加算、経過的加算は入れていません",
    "受け取る年数は制度の値ではなく、この計算での仮定です。"
    "65歳から15年、20年、25年、30年の4つを並べ、代表として25年を使っています",
    "標準報酬月額の等級の上限と下限は入れていません。"
    "入れると高い側の額はここより小さくなります",
]


def pension_from(total_reward: float, rate: float = RATE_AFTER_2003) -> float:
    """対象期間の標準報酬総額から、報酬比例部分の年金額（年額）を出す。"""
    return total_reward * rate


def total_reward(monthly: float, months: int) -> float:
    """平均標準報酬額と月数から、対象期間の標準報酬総額を出す。"""
    return monthly * months


def transferred(mine: float, yours: float, months: int,
                share: float = SPLIT_MAX,
                rate: float = RATE_AFTER_2003) -> float:
    """分割で自分へ移る年金額（年額）。

    按分割合 `share` は「分割後に自分が持つ割合」なので、
    移る標準報酬総額は **(二人の合計 × share) − 自分の総額** になる。
    `share` が上限の2分の1なら、これは**差額の半分**と同じ。
    """
    a = total_reward(yours, months)
    b = total_reward(mine, months)
    moved = (a + b) * share - b
    return pension_from(max(moved, 0.0), rate)


def by_partner_reward(months: int = 20 * 12) -> list[dict]:
    """相手の平均標準報酬額べつに、移る年金額。自分は0円。"""
    rows = []
    for monthly in (200_000, 250_000, 300_000, 350_000, 400_000, 450_000, 500_000):
        year = transferred(0, monthly, months)
        rows.append({
            "相手の平均標準報酬額": int(monthly),
            "移る年金の年額": round(year),
            "移る年金の月額": round(year / 12),
        })
    return rows


def by_my_reward(partner: float = 400_000, months: int = 20 * 12) -> list[dict]:
    """自分の平均標準報酬額べつに、移る年金額。**相手の額は動かしていない。**"""
    rows = []
    for monthly in (0, 50_000, 100_000, 150_000, 200_000, 250_000, 300_000):
        year = transferred(monthly, partner, months)
        base = transferred(0, partner, months)
        rows.append({
            "自分の平均標準報酬額": int(monthly),
            "移る年金の年額": round(year),
            "自分が0円のときとの比": round(year / base, 4) if base else 0.0,
        })
    return rows


def by_years(partner: float = 400_000) -> list[dict]:
    """婚姻年数べつに、移る年金額。自分は0円。"""
    rows = []
    for years in (5, 10, 15, 20, 25, 30, 35):
        year = transferred(0, partner, years * 12)
        rows.append({
            "婚姻年数": years,
            "移る年金の年額": round(year),
            "1年あたりの増え方": round(year / years),
        })
    return rows


def by_share(partner: float = 400_000, months: int = 20 * 12) -> list[dict]:
    """按分割合べつに、移る年金額。自分は0円。上限の2分の1を超える段は無い。"""
    rows = []
    for share in (0.1, 0.2, 0.3, 0.4, 0.5):
        year = transferred(0, partner, months, share=share)
        rows.append({
            "按分割合": share,
            "移る年金の年額": round(year),
            "上限の2分の1との差": round(transferred(0, partner, months) - year),
        })
    return rows


def kind3_months(marry_year: int, divorce_year: int,
                 marry_month: int = 4, divorce_month: int = 4) -> int:
    """3号分割の対象になる月数。**2008年4月より前は1か月も入らない。**"""
    start = max((marry_year - 1900) * 12 + marry_month,
                (KIND3_START_YEAR - 1900) * 12 + KIND3_START_MONTH)
    end = (divorce_year - 1900) * 12 + divorce_month
    return max(end - start, 0)


def marriage_months(marry_year: int, divorce_year: int,
                    marry_month: int = 4, divorce_month: int = 4) -> int:
    """婚姻期間の月数。合意分割はこちらが対象になる。"""
    return max((divorce_year - 1900) * 12 + divorce_month
               - ((marry_year - 1900) * 12 + marry_month), 0)


def kind3_table(divorce_year: int = 2026, partner: float = 400_000) -> list[dict]:
    """結婚した年べつに、3号分割だけの額と合意分割の額を並べる。"""
    rows = []
    for marry_year in (1990, 1995, 2000, 2005, 2010, 2015, 2020):
        m_all = marriage_months(marry_year, divorce_year)
        m_3 = kind3_months(marry_year, divorce_year)
        agreed = transferred(0, partner, m_all)
        kind3 = transferred(0, partner, m_3, share=KIND3_RATE)
        rows.append({
            "結婚した年": marry_year,
            "婚姻の月数": m_all,
            "3号分割の対象月数": m_3,
            "合意分割の年額": round(agreed),
            "3号分割だけの年額": round(kind3),
            "合意分割に対する割合": round(kind3 / agreed, 4) if agreed else 0.0,
        })
    return rows


def rate_gap_table(years: int = 25, partner: float = 400_000,
                   divorce_year: int = 2026) -> list[dict]:
    """結婚した年べつに、2003年3月以前の月がいくつ入るかで移る額が変わる表。

    **同じ婚姻年数でも、いつ結婚したかで額が変わる**ところが主題。
    """
    def moved(marry_year: int) -> float:
        start = (marry_year - 1900) * 12 + 4
        end = start + years * 12
        old = max(min(end, TOTAL_MONTHS_2003) - start, 0)
        new = max(end - max(start, TOTAL_MONTHS_2003), 0)
        return (pension_from(total_reward(partner, old), RATE_BEFORE_2003)
                + pension_from(total_reward(partner, new), RATE_AFTER_2003)) * SPLIT_MAX

    # **差そのものが主題なので、表に印字します**（`docs/JOURNAL.md` 2026-08-29 の線）。
    # 2003年4月以後だけの人＝乗率の線をまたがない人を、比べる相手に置いています。
    base = moved(2003)
    rows = []
    for marry_year in (1985, 1990, 1995, 2000, 2001, 2003, 2005):
        start = (marry_year - 1900) * 12 + 4
        end = start + years * 12
        old = max(min(end, TOTAL_MONTHS_2003) - start, 0)
        new = max(end - max(start, TOTAL_MONTHS_2003), 0)
        year = moved(marry_year)
        rows.append({
            "結婚した年": marry_year,
            "2003年3月以前の月数": old,
            "2003年4月以後の月数": new,
            "移る年金の年額": round(year),
            "線をまたがない人との差": round(year - base),
        })
    return rows


def share_of_partner(enrolled_years: int, married_years: int = 20) -> float:
    """相手の報酬比例部分ぜんぶに対して、移るのが何割か。"""
    if enrolled_years <= 0:
        return 0.0
    return min(married_years / enrolled_years, 1.0) * SPLIT_MAX


def half_myth_table(married_years: int = 20) -> list[dict]:
    """「半分」との距離。加入年数が長いほど、割合は下がる。"""
    rows = []
    for enrolled in (20, 25, 30, 35, 38, 40, 45):
        rows.append({
            "相手の厚生年金の加入年数": enrolled,
            "婚姻年数": married_years,
            "移るのは報酬比例部分の何割": round(share_of_partner(enrolled, married_years), 4),
        })
    return rows


def lifetime_loss(partner: float = 400_000, months: int = 20 * 12) -> list[dict]:
    """請求しないまま2年の期限を過ぎたときに失う生涯額。"""
    year = transferred(0, partner, months)
    rows = []
    for years in (15, 20, 25, 30):
        rows.append({
            "受け取る年数": years,
            "失う生涯額": round(year * years),
            "1日あたり": round(year * years / (years * 365)),
        })
    return rows


def zero_sum_table(partner: float = 400_000, months: int = 20 * 12) -> list[dict]:
    """分割はゼロサム。**相手が減る額と自分が増える額は同じ。**"""
    rows = []
    for mine in (0, 100_000, 200_000, 300_000):
        moved = transferred(mine, partner, months)
        rows.append({
            "自分の平均標準報酬額": int(mine),
            "自分が増える年額": round(moved),
            "相手が減る年額": round(moved),
            "二人の合計の変化": 0,
        })
    return rows


def grid() -> list[dict]:
    """図解の元になる表。"""
    return by_partner_reward()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""

    # 1. 法令が名指ししている値
    _checks.statutory(RATE_AFTER_2003, 5.481 / 1000, "2003年4月以後の給付乗率",
                      source="厚生年金保険法43条・平成12年改正法附則20条")
    _checks.statutory(RATE_BEFORE_2003, 7.125 / 1000, "2003年3月以前の給付乗率",
                      source="厚生年金保険法43条・平成12年改正法附則20条")
    _checks.statutory(SPLIT_MAX, 0.5, "按分割合の上限",
                      source="厚生年金保険法78条の3")
    _checks.statutory(KIND3_RATE, 0.5, "3号分割の割合",
                      source="厚生年金保険法78条の14")
    _checks.statutory(CLAIM_LIMIT_YEARS, 2, "請求期限の年数",
                      source="厚生年金保険法78条の2第1項")
    _checks.ratio(SPLIT_MAX, "按分割合の上限")
    _checks.ratio(KIND3_RATE, "3号分割の割合")

    # 2. **主題その1**: 移るのは「相手の額の半分」ではなく「差額の半分」。
    #    自分に報酬があるほど減る。相手の額は1円も動かしていない。
    _checks.decreases_with(lambda m: transferred(m, 400_000, 240),
                           [0, 100_000, 200_000, 300_000],
                           "自分の報酬が増えたのに移る額が減っていない")
    _checks.rounding(round(transferred(200_000, 400_000, 240)),
                     round(transferred(0, 400_000, 240) / 2),
                     "自分が相手の半分のときに移る額（差額の半分になっていない）")

    # 3. **主題その2**: 婚姻期間と按分割合の両方に比例する。
    _checks.increases_with(lambda y: transferred(0, 400_000, y * 12),
                           [5, 10, 20, 30],
                           "婚姻年数が増えたのに移る額が増えていない")
    _checks.increases_with(lambda s: transferred(0, 400_000, 240, share=s),
                           [0.1, 0.2, 0.3, 0.4, 0.5],
                           "按分割合が上がったのに移る額が増えていない")

    # 4. **主題その3**: 3号分割だけでは、2008年4月より前が1か月も入らない。
    _checks.rounding(kind3_months(1995, 2008, divorce_month=4), 0,
                     "2008年4月に離婚したときの3号分割の対象月数")
    _checks.greater(marriage_months(1995, 2026), kind3_months(1995, 2026),
                    "3号分割の対象月数が婚姻の月数以上（2008年4月の線が効いていない）")
    early = next(r for r in kind3_table() if r["結婚した年"] == 1995)
    _checks.greater(early["合意分割の年額"], early["3号分割だけの年額"],
                    "1995年結婚で3号分割だけのほうが合意分割以上")

    # 5. **主題その4**: 2003年3月以前の乗率のほうが大きい。
    _checks.greater(RATE_BEFORE_2003, RATE_AFTER_2003,
                    "2003年3月以前の乗率が2003年4月以後以下")
    _checks.close(RATE_BEFORE_2003 / RATE_AFTER_2003, 7.125 / 5.481,
                  "乗率の倍率")
    _checks.decreases_with(lambda y: rate_gap_table()[
        [r["結婚した年"] for r in rate_gap_table()].index(y)]["移る年金の年額"],
        [1985, 1990, 1995, 2000], "結婚が遅いのに移る額が減っていない")

    # 6. **主題その5**: 加入年数が長いほど「半分」から遠ざかる。
    _checks.decreases_with(lambda e: share_of_partner(e),
                           [20, 30, 40, 45],
                           "加入年数が増えたのに割合が減っていない")
    _checks.rounding(round(share_of_partner(40) * 10000), 2500,
                     "加入40年・婚姻20年で移る割合（万分率）")

    # 7. 生涯額は受け取る年数に比例して増えること。
    _checks.increases_with(
        lambda y: transferred(0, 400_000, 240) * y, [15, 20, 25, 30],
        "受け取る年数が増えたのに失う生涯額が増えていない")

    # 8. ゼロサム。増える額と減る額が同じでなければ、この表の主題が消える。
    for row in zero_sum_table():
        _checks.rounding(row["自分が増える年額"], row["相手が減る年額"],
                         "分割で増える額と減る額")

    _checks.unique_by(by_partner_reward(), lambda r: r["相手の平均標準報酬額"],
                      "相手の平均標準報酬額")
    _checks.unique_by(kind3_table(), lambda r: r["結婚した年"], "結婚した年")
    _checks.assumption_values(ASSUMPTIONS, name="bunkatsu")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 相手の平均標準報酬額べつに、年金分割で移る年金は月いくらか ===")
    for row in by_partner_reward():
        print(row)

    print("\n=== 移るのは「相手の半分」ではない。自分に厚生年金があるほど減る ===")
    for row in by_my_reward():
        print(row)

    print("\n=== 婚姻年数べつに、年金分割で移る年金の年額 ===")
    for row in by_years():
        print(row)

    print("\n=== 按分割合を2分の1より低く合意すると、いくら減るか ===")
    for row in by_share():
        print(row)

    print("\n=== 3号分割だけを請求すると、2008年4月より前は1か月も入らない ===")
    for row in kind3_table():
        print(row)

    print("\n=== 同じ婚姻年数でも、2003年4月の乗率の線をまたぐかで額が変わる ===")
    for row in rate_gap_table():
        print(row)

    print("\n=== 「年金の半分」からどれだけ遠いか。加入年数べつの割合 ===")
    for row in half_myth_table():
        print(row)

    print("\n=== 請求しないまま2年の期限を過ぎると、生涯でいくら失うか ===")
    for row in lifetime_loss():
        print(row)

    print("\n=== 分割はゼロサム。相手が減る額と自分が増える額は同じ ===")
    for row in zero_sum_table():
        print(row)
