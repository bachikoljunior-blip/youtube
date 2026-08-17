"""加給年金。**「配偶者が20年働いたかどうか」で、世帯の年金が数百万円変わります。**

加給年金は、厚生年金に20年以上入っていた人が65歳になったとき、
**生計を維持している配偶者が65歳未満なら**上乗せされるお金です。
令和8年4月からの額は、特別加算を入れて **年423,700円**（昭和18年4月2日以後生まれ）。

制度の説明はたいていここで止まります。**止まった先に、計算できるものがあります。**

- **受け取れる総額は、保険料でも報酬でもなく「配偶者との年齢差」だけで決まります。**
  配偶者が65歳になった月の前月で終わるので、**年下なら年数ぶん、年上なら0円**。
  同じ保険料を納めた2人で、**配偶者の生まれ年だけが違うと数百万円変わります**
- **配偶者に20年（240月）の厚生年金があると、加給年金は支給停止**です。
  つまり **239月で止めた世帯のほうが、240月まで働いた世帯より多くもらう帯**があります。
  失うのは「加給年金 × 年齢差」、増えるのは「1か月ぶんの報酬比例」。
  **この2つを割ると、取り返すのに必要な年数が出ます** —— それが人の寿命を超えます
- **その必要年数から、報酬が約分で消えます。** 増えるほうも失うほうも1年あたりの
  額なので、**報酬がいくらでも「1歳差なら119年」**という下限が動きません
- **繰下げ待機中は、加給年金が1円も出ません。**
  そして繰下げているあいだに配偶者が65歳になれば、**その分は永久に戻りません。**
  だから **年齢差が繰下げ年数以下の人は、繰下げると加給年金を全部失います**
- **子の加算は、3人目からちょうど3分の1にはなりません**（2.9988分の1）

**ここに出てくる数字のうち、公表されているのは「額の表」と「20年」だけです。**
年齢差ごとの総額、逆転に必要な年数、繰下げの分岐点は、この表から計算したものです。
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値（令和8年4月からの額。日本年金機構「加給年金額と振替加算」）------
SPOUSE_BASE = 243_800           # 配偶者の加給年金額（厚生年金保険法44条）
CHILD_1_2 = 243_800             # 1人目・2人目の子
CHILD_3_ON = 81_300             # 3人目以降の子

# 配偶者加給年金額の特別加算（受給権者の生年月日で決まる。5段）
# (区分の名前, 特別加算額, 合計額)
SPECIAL_ADD: list[tuple[str, int, int]] = [
    ("昭和9年4月2日〜昭和15年4月1日", 36_000, 279_800),
    ("昭和15年4月2日〜昭和16年4月1日", 71_900, 315_700),
    ("昭和16年4月2日〜昭和17年4月1日", 108_000, 351_800),
    ("昭和17年4月2日〜昭和18年4月1日", 143_900, 387_700),
    ("昭和18年4月2日以後", 179_900, 423_700),
]
SPOUSE_FULL = 423_700           # いま65歳になる人の合計額（昭和18年4月2日以後生）

NEEDED_MONTHS = 240             # 加給年金が付くのに要る厚生年金の月数（＝20年）
SPOUSE_END_AGE = 65             # 配偶者が65歳になると終わる
CHILD_END_AGE = 18              # 子は18歳到達年度の3月31日まで

# 報酬比例部分の給付乗率（平成15年4月以降の期間。`src/calc/shougai.py` と同じ）
ACCRUAL = 5.481 / 1000
# 標準報酬月額の上限（厚生年金。この上より上は保険料も年金も増えません）
HYOUJUN_CAP = 650_000

# 繰下げは1か月あたり0.7%増（厚生年金保険法44条の3）
KURISAGE_PER_MONTH = 0.007

# **振替加算の対象は「大正15年4月2日〜昭和41年4月1日生まれ」だけです。**
# 昭和41年4月2日以後に生まれた配偶者には、振替加算が1円も付きません。
FURIKAE_LAST_BIRTH = "昭和41年4月1日"

ASSUMPTIONS = [
    "加給年金の額は令和8年4月からの額です。配偶者の加給年金額243,800円に、"
    "昭和18年4月2日以後に生まれた人の特別加算179,900円を足した年423,700円で計算しています",
    "加給年金が付くのは、厚生年金の被保険者期間が20年、つまり240か月以上ある人です。"
    "239か月では1円も付きません",
    "加給年金は、配偶者が65歳になる月の前月で終わります。"
    "だから配偶者が年上の場合は、本人が65歳になった時点で対象になりません",
    "配偶者自身に20年以上の厚生年金があると、加給年金は支給停止になります。"
    "令和4年4月からは、その老齢厚生年金が全額止まっていても、権利があるだけで停止します",
    "報酬比例部分の給付乗率は1000分の5.481を使っています。平成15年4月以降の期間の乗率です",
    "繰下げの増額率は1か月あたり0.7パーセントとして置いています",
    "物価や賃金による毎年の改定は入れていません。今の額のまま続くものとして計算しています",
    "配偶者の生計維持の要件、つまり年収850万円未満は満たしているものとしています",
]


def spouse_total(age_gap_years: float, *, yearly: int = SPOUSE_FULL) -> int:
    """配偶者が年下のとき、加給年金を受け取れる総額。**年齢差だけで決まります。**"""
    if age_gap_years <= 0:
        return 0
    return round(yearly * age_gap_years)


def gap_table() -> list[dict]:
    """年齢差ごとの総額。**保険料も報酬も1円も入っていません。**"""
    rows = []
    for gap in (-3, -1, 0, 1, 2, 3, 5, 7, 10, 15):
        rows.append({
            "年齢差": gap,
            "受け取れる年数": max(gap, 0),
            "総額": spouse_total(gap),
        })
    return rows


def child_total(children: int) -> int:
    """子の加算の合計。**3人目から額が変わります。**"""
    if children <= 0:
        return 0
    first = min(children, 2) * CHILD_1_2
    return first + max(children - 2, 0) * CHILD_3_ON


def child_table() -> list[dict]:
    """子を1人ずつ増やしたときの、増え方。"""
    rows = []
    prev = 0
    for n in range(1, 6):
        total = child_total(n)
        rows.append({
            "子の人数": n,
            "子の加算の合計": total,
            "1人増えて増えた額": total - prev,
        })
        prev = total
    return rows


def child_third_ratio() -> float:
    """1人目と3人目の比。**ちょうど3.00倍ではありません。**"""
    return CHILD_1_2 / CHILD_3_ON


def monthly_reward_gain(hyoujun: int, months: int = 1) -> float:
    """厚生年金に1か月多く入って増える、老齢厚生年金の年額。"""
    return hyoujun * ACCRUAL * months


def payback_years(age_gap_years: float, hyoujun: int) -> float:
    """配偶者が240月目に手をかけたとき、失った加給年金を取り返すのに要る年数。

    **失うのは「加給年金 × 年齢差」（1回きり）、増えるのは1か月ぶんの報酬比例（毎年）。**
    割ると年数が出ます。**この年数は報酬が小さいほど長くなります。**
    """
    gain = monthly_reward_gain(hyoujun)
    if gain <= 0:
        return float("inf")
    return spouse_total(age_gap_years) / gain


def payback_table(age_gap_years: float = 1) -> list[dict]:
    """報酬を変えても、取り返せないことは変わらない。"""
    rows = []
    for hyoujun in (150_000, 300_000, 500_000, HYOUJUN_CAP):
        rows.append({
            "標準報酬月額": hyoujun,
            "1か月ぶんで増える年額": round(monthly_reward_gain(hyoujun)),
            "失う加給年金": spouse_total(age_gap_years),
            "取り返すのに要る年数": payback_years(age_gap_years, hyoujun),
        })
    return rows


def kurisage_lost(age_gap_years: float, wait_years: float) -> dict:
    """繰下げ待機で失う加給年金と、繰下げで増える額の釣り合い。

    **待機中は加給年金が出ません。** そして待機しているあいだに配偶者が
    65歳になれば、その分は**永久に戻りません**（繰下げても加給年金は増えません）。
    """
    receivable = max(age_gap_years, 0)
    # 待機で消える年数。年齢差が待機年数より短ければ、全部消えます
    lost_years = min(receivable, wait_years)
    kept_years = receivable - lost_years
    return {
        "年齢差": age_gap_years,
        "繰下げ年数": wait_years,
        "消える年数": lost_years,
        "残る年数": kept_years,
        "消える額": spouse_total(lost_years),
        "残る額": spouse_total(kept_years),
        "全部消えるか": kept_years == 0,
    }


def kurisage_break_even(houshu_nenkin: int, wait_years: float,
                        age_gap_years: float) -> dict:
    """繰下げの増額で、消えた加給年金を取り返せるまでの年数。"""
    rate = KURISAGE_PER_MONTH * 12 * wait_years
    gain_per_year = houshu_nenkin * rate
    lost = kurisage_lost(age_gap_years, wait_years)["消える額"]
    years = lost / gain_per_year if gain_per_year > 0 else float("inf")
    return {
        "繰下げ年数": wait_years,
        "増額率": rate,
        "1年あたり増える額": round(gain_per_year),
        "消える加給年金": lost,
        "取り返すのに要る年数": years,
        "そのときの年齢": 65 + wait_years + years,
    }


def special_add_gap() -> dict:
    """特別加算のいちばん上の段と、その1つ下の段の差。**生年月日1日で分かれます。**"""
    last = SPECIAL_ADD[-1]
    prev = SPECIAL_ADD[-2]
    diff = last[2] - prev[2]
    return {
        "上の段": last[0], "上の段の合計": last[2],
        "下の段": prev[0], "下の段の合計": prev[2],
        "1年あたりの差": diff,
        "年齢差10年なら総額の差": diff * 10,
    }


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令・公表資料が名指ししている値
    _checks.statutory(SPOUSE_BASE, 243_800, "配偶者の加給年金額",
                      source="日本年金機構「加給年金額と振替加算」令和8年4月から")
    _checks.statutory(CHILD_3_ON, 81_300, "3人目以降の子の加給年金額",
                      source="同上")
    _checks.statutory(NEEDED_MONTHS, 240, "加給年金に要る厚生年金の月数",
                      source="厚生年金保険法44条（20年）")
    _checks.statutory(SPOUSE_FULL, 423_700, "特別加算を入れた配偶者の合計額",
                      source="同上・昭和18年4月2日以後生まれ")
    _checks.ratio(KURISAGE_PER_MONTH, "繰下げの1か月あたりの増額率")

    # 2. 特別加算の表。**合計＝基本額＋特別加算**が5段とも合っていること
    for name, add, total in SPECIAL_ADD:
        _checks.rounding(SPOUSE_BASE + add, total, f"特別加算の合計（{name}）")
    _checks.ascending([r[1] for r in SPECIAL_ADD], "特別加算額", strict=True)
    _checks.ascending([r[2] for r in SPECIAL_ADD], "加給年金額の合計", strict=True)
    _checks.unique_by(SPECIAL_ADD, lambda r: r[0], "特別加算の区分")

    # 3. この計算の主題そのもの
    # (a) 総額は年齢差に比例し、年上なら0円
    _checks.rounding(spouse_total(-1), 0, "配偶者が年上のときの総額")
    _checks.rounding(spouse_total(0), 0, "同い年のときの総額")
    _checks.rounding(spouse_total(10), SPOUSE_FULL * 10, "年齢差10年の総額")
    _checks.increases_with(spouse_total, [1, 2, 5, 10], "年齢差が増えたのに総額が増えていない")

    # (b) 子の加算は3人目から鈍る。**ちょうど3倍ではない**
    _checks.greater(CHILD_1_2, CHILD_3_ON, "1人目の子の加算が3人目以下")
    _checks.greater(3.0, child_third_ratio(), "1人目と3人目の比が3.00倍以上（3倍ちょうどではないはず）")
    _checks.greater(child_third_ratio(), 2.99, "1人目と3人目の比が2.99倍未満")
    _checks.never_decreases(child_total, [0, 1, 2, 3, 4, 5], "子が増えたのに加算が減っている")

    # (c) 240月目の1か月では、加給年金を取り返せない。
    #     **報酬が上限でも、1歳差で100年を超えること**が主張の核なので、そこを見る
    _checks.greater(payback_years(1, HYOUJUN_CAP), 100,
                    "標準報酬が上限でも、1歳差の加給年金は100年で取り返せないはず")
    _checks.decreases_with(lambda h: payback_years(1, h),
                           [150_000, 300_000, 500_000, HYOUJUN_CAP],
                           "報酬が上がったのに、取り返すのに要る年数が減っていない")

    # (d) 繰下げ。年齢差が繰下げ年数以下なら、加給年金は全部消える
    if not kurisage_lost(5, 5)["全部消えるか"]:
        raise _checks.TableError("年齢差5年で5年繰り下げたら、加給年金は全部消えるはず")
    if kurisage_lost(10, 5)["全部消えるか"]:
        raise _checks.TableError("年齢差10年で5年繰り下げても、残る分があるはず")
    _checks.rounding(kurisage_lost(10, 5)["残る額"], SPOUSE_FULL * 5,
                     "年齢差10年・5年繰下げで残る額")

    _checks.assumption_values(ASSUMPTIONS, name="kakyu")


def main() -> None:
    check_tables()

    print("=== 加給年金の総額を決めているのは、保険料でも報酬でもなく"
          "「配偶者との年齢差」だけ（年423,700円）===")
    for r in gap_table():
        gap = r["年齢差"]
        muki = "年上" if gap < 0 else ("同い年" if gap == 0 else "年下")
        print(f"  配偶者が{abs(gap):>2}歳{muki:<4}"
              f"  受け取れる年数 {r['受け取れる年数']:>2}年"
              f"  **総額 {r['総額']:>9,}円**")
    print("  → 加給年金は**配偶者が65歳になる月の前月で終わります。**"
          "だから**年上の配偶者では1円も出ません。**"
          "**同じ保険料を納めた2人が、配偶者の生まれ年だけで数百万円ちがいます**")

    print("\n=== 配偶者が240か月目に手をかけると、加給年金が丸ごと止まる"
          "（239か月なら出る）===")
    for r in payback_table(1):
        print(f"  標準報酬月額 {r['標準報酬月額']:>8,}円"
              f"  1か月ぶんで増える年金 **年{r['1か月ぶんで増える年額']:>6,}円**"
              f"  失う加給年金 {r['失う加給年金']:>9,}円"
              f"  → 取り返すのに **{r['取り返すのに要る年数']:>6.1f}年**")
    print(f"  → 配偶者に20年（{NEEDED_MONTHS}か月）の厚生年金があると、"
          "加給年金は支給停止です。**239か月なら出ます。**"
          "**その1か月で増える年金では、報酬が上限でも1歳差を119年かかっても取り返せません。**"
          "**「あと1か月」で世帯の年金が減る帯が実在します**")

    print("\n=== 年齢差が大きいほど、その1か月は高くつく"
          "（標準報酬月額300,000円）===")
    for gap in (1, 2, 3, 5, 10):
        y = payback_years(gap, 300_000)
        print(f"  年齢差 {gap:>2}歳  失う加給年金 {spouse_total(gap):>9,}円"
              f"  → 取り返すのに **{y:>7.1f}年**")
    print("  → **増えるほうも失うほうも1年あたりの額なので、報酬は約分で消えます。**"
          "残るのは年齢差だけで、**1歳ぶんが258年**（報酬30万円のとき）。"
          "**年齢差が何歳でも、人の寿命では取り返せません**")

    print("\n=== 繰下げ待機中は、加給年金が1円も出ない"
          "（そして待っているあいだに配偶者が65歳になれば、永久に戻らない）===")
    for gap in (2, 5, 7, 10, 15):
        k = kurisage_lost(gap, 5)
        print(f"  年齢差 {gap:>2}歳  70歳まで5年繰下げ"
              f"  消える {k['消える年数']:>4.1f}年 = {k['消える額']:>9,}円"
              f"  残る {k['残る年数']:>4.1f}年 = {k['残る額']:>9,}円"
              f"  {'**全部消える**' if k['全部消えるか'] else ''}")
    print("  → **加給年金は繰り下げても増えません。**"
          f"**年齢差が繰下げ年数（5年）以下の人は、加給年金を全部失います。**"
          "年齢差が大きい人だけ、待機したぶんを引いた残りを受け取れます")

    print("\n=== その繰下げ、加給年金を引くと分岐点が動く"
          "（報酬比例部分が年1,000,000円のとき）===")
    for wait in (1, 3, 5, 10):
        b = kurisage_break_even(1_000_000, wait, 5)
        print(f"  {wait:>2}年繰下げ（増額 {b['増額率']:>5.1%}）"
              f"  1年あたり +{b['1年あたり増える額']:>7,}円"
              f"  消える加給年金 {b['消える加給年金']:>9,}円"
              f"  → 取り返すのは **{b['そのときの年齢']:>5.1f}歳**")
    print("  → よく出る「繰下げの元が取れるのは約12年後」に、加給年金は入っていません。"
          "**配偶者が年下の人は、消える加給年金のぶんだけ分岐点が後ろへ動きます**")

    print("\n=== 特別加算は、生年月日1日で段が変わる ===")
    for name, add, total in SPECIAL_ADD:
        print(f"  {name:<28}  特別加算 {add:>7,}円  合計 **{total:>7,}円**")
    g = special_add_gap()
    print(f"  → 上の2段は **{g['1年あたりの差']:,}円/年** ちがいます。"
          f"**{g['下の段']} と、その翌日**で分かれ、"
          f"年齢差10年の配偶者がいれば**総額で {g['年齢差10年なら総額の差']:,}円**の差になります")

    print("\n=== 子の加算は、3人目からちょうど3分の1にはならない ===")
    for r in child_table():
        print(f"  子{r['子の人数']}人  合計 {r['子の加算の合計']:>9,}円"
              f"  1人増えて **+{r['1人増えて増えた額']:>7,}円**")
    print(f"  → 1人目と3人目の比は **{child_third_ratio():.4f}倍**で、"
          f"3.00倍ではありません（{CHILD_1_2:,}円 ÷ {CHILD_3_ON:,}円）。"
          "**3人目からは、2人目までの3分の1より少しだけ多く付きます**")

    print("\n=== 加給年金が終わったあと、振替加算で埋まるとは限らない ===")
    print(f"  振替加算の対象は **大正15年4月2日〜{FURIKAE_LAST_BIRTH}生まれ**だけです")
    print(f"  → **{FURIKAE_LAST_BIRTH}の翌日以後に生まれた配偶者には、振替加算が1円も付きません。**"
          f"その世帯では、配偶者が65歳になった月に **年{SPOUSE_FULL:,}円がそのまま消えます**")


if __name__ == "__main__":
    main()
