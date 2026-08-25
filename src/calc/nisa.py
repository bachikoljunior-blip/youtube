"""NISAの非課税保有限度額と、売却したときに戻る枠。

**一般の解説は「総枠1,800万円・年360万円・売った枠は翌年復活」で止まります。**
その先に、口を開けている段が2つあります。

1つめ。**成長投資枠だけを使う人は、総枠1,800万円のうち1,200万円で頭打ちになります。**
成長投資枠には1,200万円という別の上限があるので（租税特別措置法37条の14）、
残りの600万円は**つみたて投資枠でしか埋められません**。
つまり「1,800万円」は誰にでも同じ数字ではなく、**使う枠の組み合わせで決まる数字**です。

2つめ。**売って戻る枠は、売った額ではありません。買った額です**（簿価残高方式）。
だから**含み益が乗っているほど、戻ってくる枠は目減りします。**
同じ10,000,000円を売っても、含み益0パーセントなら10,000,000円ぶん戻り、
含み益100パーセントなら**5,000,000円ぶんしか戻りません。**

この表が出す数字（実行して出たものを、丸めずに写しています）:

- 成長投資枠だけで積むと **5.0年**で **12,000,000円** に着き、そこから**何年たっても増えません**。
  総枠に対する到達率は **66.7パーセント**
- つみたて投資枠だけなら **15.0年**、両方を満額なら **5.0年**で 18,000,000円
- 時価10,000,000円を売って戻る枠は、含み益100パーセントで **5,000,000円**、
  含み益200パーセントで **3,333,333円**
- 18,000,000円の総枠をすべて売り切って入れ直すには、年間の上限があるので **5.0年**かかります。
  非課税で運用できない期間が**その5.0年ぶん空きます**
- 18,000,000円を年5パーセントで20年運用したときの益は **29,759,359円**。
  課税口座なら **6,045,614円**の税金がかかります（20.315パーセント）
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値（租税特別措置法37条の14。2024年1月からの制度）----------------

TSUMITATE_YEAR = 1_200_000      # つみたて投資枠の年間上限
GROWTH_YEAR = 2_400_000         # 成長投資枠の年間上限
ANNUAL_CAP = 3_600_000          # 年間投資枠の合計
TOTAL_CAP = 18_000_000          # 非課税保有限度額（総枠・簿価）
GROWTH_CAP = 12_000_000         # そのうち成長投資枠で持てる上限

TAX_RATE = 0.20315              # 課税口座の税率（所得税15％＋復興0.315％＋住民税5％）

ASSUMPTIONS = [
    "2024年1月から始まった制度で計算しています。"
    "年間投資枠はつみたて投資枠が120万円、成長投資枠が240万円、合わせて360万円です",
    "非課税保有限度額は簿価で1,800万円、"
    "そのうち成長投資枠で持てるのは1,200万円までです",
    "売却した枠が戻るのは、売った値段ではなく買った値段の分です。"
    "これを簿価残高方式といいます",
    "戻った枠が使えるのは翌年からで、その年もやはり年間360万円の上限がかかります",
    "非課税で持てる期間と口座を開ける期間には、期限を置いていません",
    "課税口座にかかる税率は20.315パーセントとしています。"
    "所得税15パーセント、復興特別所得税0.315パーセント、住民税5パーセントの合計です",
    "利回りは制度の値ではなく、この計算での仮定です。"
    "年1パーセントから年7パーセントまでを並べ、代表として年5パーセントを使っています",
    "配当や分配金は再投資され、その分も非課税の枠を新たに使わないものとしています",
    "毎年の投資は年の初めに一度おこなうものとしています",
    "口座を持てるのは18歳以上ですが、年齢による差は入れていません",
]


# ---- 1. 枠を埋めるのに何年かかるか ----------------------------------------

def years_to_fill(per_year: float, cap: float = TOTAL_CAP) -> float:
    """1年に `per_year` ずつ入れて、`cap` に着くまでの年数。"""
    if per_year <= 0:
        raise ValueError("1年あたりの額は正の数で")
    return cap / per_year


def reachable(per_year: float, sub_cap: float, years: int) -> float:
    """その枠だけを `years` 年つかったときに積み上がる簿価。**枠の上限で止まります。**"""
    return min(per_year * years, sub_cap)


def lanes_table(years: int = 15) -> list[dict]:
    """使う枠の組み合わせごとに、`years` 年でどこまで積めるか。

    **成長投資枠だけを選ぶと、総枠1,800万円には永久に届きません。**
    """
    lanes = [
        ("つみたて投資枠だけ", TSUMITATE_YEAR, TOTAL_CAP),
        ("成長投資枠だけ", GROWTH_YEAR, GROWTH_CAP),
        ("両方を満額", ANNUAL_CAP, TOTAL_CAP),
    ]
    out = []
    for name, per_year, sub_cap in lanes:
        ceiling = min(sub_cap, TOTAL_CAP)
        out.append({
            "使う枠": name,
            "1年あたり": per_year,
            "この枠の上限": ceiling,
            f"{years}年後": reachable(per_year, ceiling, years),
            "上限に着く年数": years_to_fill(per_year, ceiling),
            "総枠に対する到達率": ceiling / TOTAL_CAP,
        })
    return out


def fill_years_table() -> list[dict]:
    """1年あたりの投資額ごとに、総枠1,800万円に着く年数。

    **刻みは10万円**。年間上限360万円までを並べます。
    """
    out = []
    step = 100_000
    amount = step
    while amount <= ANNUAL_CAP:
        out.append({
            "1年あたり": amount,
            "1,800万円に着く年数": years_to_fill(amount),
            "年間上限に対する割合": amount / ANNUAL_CAP,
        })
        amount += step
    return out


# ---- 2. 売って戻る枠（簿価残高方式）----------------------------------------

def restored_room(market_value: float, gain_ratio: float) -> float:
    """時価 `market_value` を売ったときに戻る枠。**戻るのは簿価の分だけです。**

    含み益が `gain_ratio` なら 時価 ＝ 簿価 ×（1＋`gain_ratio`）なので、
    戻る枠は 時価 ÷（1＋`gain_ratio`）になります。
    """
    if gain_ratio < 0:
        raise ValueError("含み益の割合は0以上で")
    return market_value / (1 + gain_ratio)


def restore_table(market_value: float = 10_000_000) -> list[dict]:
    """含み益の割合ごとに、時価 `market_value` を売って戻る枠。

    **刻みは10パーセント**。含み益0から200パーセントまで。
    """
    out = []
    for pct in range(0, 201, 10):
        ratio = pct / 100
        room = restored_room(market_value, ratio)
        out.append({
            "含み益の割合": ratio,
            "売った時価": market_value,
            "戻る枠": room,
            "戻らなかった分": market_value - room,
            "時価に対する割合": room / market_value,
        })
    return out


# ---- 3. 総枠を売り切って入れ直すのに何年かかるか ----------------------------

def refill_years(room: float = TOTAL_CAP, per_year: float = ANNUAL_CAP) -> float:
    """戻った枠 `room` を、年間上限 `per_year` の中で使い切るまでの年数。

    **枠が戻っても、年間の上限は消えません。** ここが空く期間になります。
    """
    return years_to_fill(per_year, room)


def refill_table() -> list[dict]:
    """含み益の割合ごとに、総枠を全部売ってから入れ直し終わるまでの年数。"""
    out = []
    for pct in range(0, 201, 25):
        ratio = pct / 100
        # 簿価1,800万円ぶんを売る。**戻るのは簿価なので、常に1,800万円**。
        # 変わるのは手にする時価のほうです。
        market = TOTAL_CAP * (1 + ratio)
        out.append({
            "含み益の割合": ratio,
            "売って手にする時価": market,
            "戻る枠": TOTAL_CAP,
            "入れ直しにかかる年数": refill_years(),
            "その間に非課税で運用できない額": market,
        })
    return out


# ---- 4. 課税口座なら払っていた税金 ------------------------------------------

def grown(principal: float, rate: float, years: int) -> float:
    """`principal` を年利 `rate` で `years` 年運用したあとの額。"""
    return principal * (1 + rate) ** years


def tax_saved(principal: float, rate: float, years: int) -> float:
    """同じ運用を課税口座でしていたら払っていた税金。"""
    gain = grown(principal, rate, years) - principal
    return gain * TAX_RATE


def tax_table(principal: float = TOTAL_CAP, years: int = 20) -> list[dict]:
    """利回りごとに、`years` 年後の益と、課税口座なら払っていた税金。

    **刻みは1パーセント**。年1から年7パーセントまで。
    """
    out = []
    for pct in range(1, 8):
        rate = pct / 100
        after = grown(principal, rate, years)
        out.append({
            "利回り": rate,
            "元本": principal,
            f"{years}年後": after,
            "益": after - principal,
            "課税口座なら払う税": tax_saved(principal, rate, years),
        })
    return out


def grid() -> list[dict]:
    """図解の元になる表。**枠の組み合わせが、この表のいちばんの主題です。**"""
    return lanes_table()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""

    # 1. 法令が名指ししている値
    _checks.statutory(TSUMITATE_YEAR, 1_200_000, "つみたて投資枠の年間上限",
                      source="租税特別措置法37条の14")
    _checks.statutory(GROWTH_YEAR, 2_400_000, "成長投資枠の年間上限",
                      source="租税特別措置法37条の14")
    _checks.statutory(TOTAL_CAP, 18_000_000, "非課税保有限度額",
                      source="租税特別措置法37条の14")
    _checks.statutory(GROWTH_CAP, 12_000_000, "成長投資枠の保有上限",
                      source="租税特別措置法37条の14")
    _checks.statutory(TAX_RATE, 0.20315, "課税口座の税率",
                      source="所得税法・地方税法・復興財源確保法")
    _checks.ratio(TAX_RATE, "課税口座の税率")

    # **年間の合計は、2つの枠の和そのものであること。**
    _checks.statutory(TSUMITATE_YEAR + GROWTH_YEAR, ANNUAL_CAP,
                      "年間投資枠の合計", source="つみたて120万円＋成長240万円")

    # 2. **主題その1**: 成長投資枠だけでは総枠に届かない。
    _checks.greater(TOTAL_CAP, GROWTH_CAP,
                    "総枠が成長投資枠の上限以下（成長投資枠だけで埋まってしまう）")
    growth_only = next(r for r in lanes_table() if r["使う枠"] == "成長投資枠だけ")
    _checks.rounding(growth_only["この枠の上限"], GROWTH_CAP,
                     "成長投資枠だけで着ける上限")
    # 何年たっても増えないこと。**上限に着いたあとが平らでなければ主題が消えます。**
    _checks.rounding(reachable(GROWTH_YEAR, GROWTH_CAP, 5),
                     reachable(GROWTH_YEAR, GROWTH_CAP, 40),
                     "成長投資枠だけの5年後と40年後（上限で止まっていない）")

    # 3. **主題その2**: 戻る枠は、含み益が乗るほど減る。
    _checks.decreases_with(lambda g: restored_room(10_000_000, g),
                           [0.0, 0.5, 1.0, 2.0],
                           "含み益が増えたのに戻る枠が減っていない")
    _checks.rounding(restored_room(10_000_000, 1.0), 5_000_000,
                     "含み益100パーセントで時価1,000万円を売って戻る枠")

    # 4. **主題その3**: 枠が戻っても、年間上限のせいで入れ直しに年数がかかる。
    _checks.rounding(refill_years(), 5, "総枠を入れ直すのにかかる年数")
    _checks.greater(refill_years(), 1,
                    "入れ直しが1年で終わる（年間上限が効いていない）")

    # 5. 埋める年数は、1年あたりの額が増えれば減ること。
    _checks.decreases_with(lambda a: years_to_fill(a),
                           [600_000, 1_200_000, 2_400_000, 3_600_000],
                           "1年あたりの額が増えたのに年数が減っていない")
    _checks.increases_with(lambda p: tax_saved(TOTAL_CAP, p / 100, 20),
                           [1, 3, 5, 7],
                           "利回りが上がったのに税額が増えていない")

    _checks.unique_by(lanes_table(), lambda r: r["使う枠"], "枠の組み合わせ")
    _checks.assumption_values(ASSUMPTIONS, name="nisa")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 成長投資枠だけを使うと、総枠1,800万円は1,200万円で頭打ちになる ===")
    for row in lanes_table():
        print(f"  {row['使う枠']:<12} 1年 {row['1年あたり']:>9,.0f}円"
              f"  上限 {row['この枠の上限']:>10,.0f}円"
              f"  着くまで {row['上限に着く年数']:>5.1f}年"
              f"  総枠の {row['総枠に対する到達率']:>6.1%}")

    print("\n=== 1年あたりいくら入れると、1,800万円に何年で着くか ===")
    for row in fill_years_table():
        print(f"  1年 {row['1年あたり']:>9,.0f}円"
              f"（年間上限の {row['年間上限に対する割合']:>6.1%}）"
              f"  → {row['1,800万円に着く年数']:>6.1f}年")

    print("\n=== 売って戻る枠は「売った額」ではなく「買った額」なので、含み益のぶん目減りする ===")
    for row in restore_table():
        print(f"  含み益 {row['含み益の割合']:>6.0%}"
              f"  時価 {row['売った時価']:>10,.0f}円を売る →"
              f" 戻る枠 {row['戻る枠']:>10,.0f}円"
              f"（時価の {row['時価に対する割合']:>6.1%}）"
              f"  戻らない {row['戻らなかった分']:>10,.0f}円")

    print("\n=== 総枠を全部売って入れ直すには、年間上限があるので5年かかる ===")
    for row in refill_table():
        print(f"  含み益 {row['含み益の割合']:>6.0%}"
              f"  手にする時価 {row['売って手にする時価']:>11,.0f}円"
              f"  戻る枠 {row['戻る枠']:>10,.0f}円"
              f"  入れ直し {row['入れ直しにかかる年数']:>4.1f}年")

    print("\n=== 1,800万円を20年運用したとき、課税口座なら払っていた税金 ===")
    for row in tax_table():
        print(f"  利回り {row['利回り']:>5.0%}"
              f"  20年後 {row['20年後']:>12,.0f}円"
              f"  益 {row['益']:>12,.0f}円"
              f"  課税口座なら税 {row['課税口座なら払う税']:>11,.0f}円")
