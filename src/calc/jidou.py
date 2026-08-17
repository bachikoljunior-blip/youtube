"""児童手当。**額を決めているのは「子どもの人数」ではなく「いちばん上の子の年齢」。**

＜この docstring は、下の `main()` を1回走らせてから書いています＞

一般の解説は「3人目は月3万円」で止まります。**その3万円がいつ消えるかは、
末っ子の年齢では決まりません。** 数えるほうの上限が **22歳年度末**、
もらえるほうの上限が **18歳年度末**で、**4年ずれている**からです。

出した数字（全部この表の計算結果です）:

- **長子と3人目の年齢差が4歳までなら、3万円は216か月まるごと受け取れます。**
  5歳から削られはじめ、**1歳ひらくごとに12か月ぶん＝240,000円**ずつ消えます
- 差が10歳なら **1,440,000円**、差が18歳なら **3,360,000円** 失います。
  **子どもの人数は1人も減っていません**
- **失う額は「月20,000円 × 月数」ではありません。** 落ちた先の第2子は
  3歳未満だけ15,000円なので、そこだけ差が5,000円小さい。
  年齢差22歳なら 4,320,000円ではなく **4,140,000円**です
  （この180,000円の差は、`check_tables()` が実際に止めて分かりました）
- 18〜22歳の長子は **1円も受け取っていないのに、末っ子の月3万円を支えています。**
  この4年ぶんが **960,000円**
- 長子が数から抜けた月、**減るのは末っ子だけ**です。真ん中の子は
  第2子から第1子に繰り上がりますが、**額は1円も変わりません**（どちらも10,000円）
- **3歳の誕生月の段差は、第1子と第2子にしかありません**（15,000→10,000円）。
  **3人目は3歳をまたいでも30,000円のまま**なので、
  3人きょうだいの世帯月額は 60,000円 → 50,000円 と、**10,000円しか下がりません**
- 総額は 第1子 **2,340,000円** に対し 3人目 **6,480,000円** で **2.77倍**。
  「3人目は2倍」ではありません
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "2024年10月からの児童手当です。所得制限は撤廃されているので、年収は額に影響しません",
    "月額は、3歳未満が第1子・第2子で15,000円、3歳から高校生年代までが10,000円、"
    "第3子以降はどちらも30,000円です",
    "受け取れるのは18歳になった後の最初の3月31日まで、"
    "第3子として数えるのは22歳になった後の最初の3月31日までの子です",
    "子は全員3月生まれとして置いています。こうすると3月31日の区切りが誕生月の月末と"
    "そろうので、受け取る期間がちょうど216か月、数える期間がちょうど264か月になります。"
    "生まれ月が違うと、どちらも最大11か月ぶん長くなります",
    "きょうだいは全員を養育しているものとして数えています。"
    "施設に入っている場合や、養育していない子は数えません",
    "支給は偶数月の年6回ですが、ここでは受け取る総額だけを見ていて、"
    "受け取る時期のずれは入れていません",
]

# ---- 制度の値（2024年10月改正・こども家庭庁「児童手当制度のご案内」）----
UNDER3_1_2 = 15_000        # 3歳未満の第1子・第2子（月額）
OVER3_1_2 = 10_000         # 3歳から高校生年代までの第1子・第2子（月額）
THIRD_ON = 30_000          # 第3子以降（月額。**年齢で変わらない**）

MONTHS_PAID = 216          # 受け取れる月数（0歳〜18歳年度末＝18年）
MONTHS_UNDER3 = 36         # そのうち3歳未満（3年）
MONTHS_COUNTED = 264       # 第3子として数えられる月数（22歳年度末＝22年）

PAYS_PER_YEAR = 6          # 偶数月の年6回（1回に2か月ぶん）


def monthly(order: int, age_months: int) -> int:
    """その月の1人ぶんの月額。`order` は第何子か（数え直した後の順位）。"""
    if age_months >= MONTHS_PAID:
        return 0
    if order >= 3:
        return THIRD_ON
    return UNDER3_1_2 if age_months < MONTHS_UNDER3 else OVER3_1_2


def total_for(order: int) -> int:
    """順位が最後まで変わらなかったときの、1人ぶんの総額。"""
    return sum(monthly(order, m) for m in range(MONTHS_PAID))


def third_full_months(gap_years: int) -> int:
    """3人目が **30,000円** を受け取れる月数。

    長子が生まれてから `MONTHS_COUNTED` か月で数から抜けます。3人目から見ると
    それは `MONTHS_COUNTED - 12 * gap_years` か月後で、**受け取れる期間
    （216か月）より長ければ、削られません。**
    """
    left = MONTHS_COUNTED - 12 * max(0, gap_years)
    return max(0, min(MONTHS_PAID, left))


def third_total(gap_years: int) -> int:
    """3人目の総額（長子が抜けた後は第2子として10,000円）。"""
    full = third_full_months(gap_years)
    out = 0
    for m in range(MONTHS_PAID):
        out += THIRD_ON if m < full else monthly(2, m)
    return out


def third_loss(gap_years: int) -> int:
    """年齢差のせいで失う額（差が小さいときとの差）。"""
    return third_total(0) - third_total(gap_years)


def max_gap_without_loss() -> int:
    """**1円も失わずに済む、いちばん大きい年齢差。**"""
    gap = 0
    while third_loss(gap + 1) == 0:
        gap += 1
    return gap


def loss_per_extra_year() -> int:
    """境目を1歳こえるごとに消える額。"""
    top = max_gap_without_loss()
    return third_loss(top + 1) - third_loss(top)


def gap_table(gaps: list[int] | None = None) -> list[dict]:
    """年齢差ごとに、3人目の総額と失う額を並べる。"""
    rows = []
    for gap in gaps or [0, 2, 4, 5, 6, 8, 10, 14, 18, 22]:
        rows.append({
            "年齢差": gap,
            "3万円の月数": third_full_months(gap),
            "総額": third_total(gap),
            "失う額": third_loss(gap),
        })
    return rows


def unpaid_support_months() -> int:
    """長子が **受け取っていないのに数えられている** 月数（22歳年度末 − 18歳年度末）。"""
    return MONTHS_COUNTED - MONTHS_PAID


def unpaid_support_value() -> int:
    """その4年ぶんが、末っ子に運んでいる額。"""
    return unpaid_support_months() * (THIRD_ON - OVER3_1_2)


def household_month(children_ages: list[int]) -> dict:
    """きょうだいの月齢を渡すと、その月の世帯の受取額と内訳を返す。

    **順位は「数えられる子」の中で上から付け直します**（22歳年度末で抜ける）。
    """
    counted = sorted((a for a in children_ages if a < MONTHS_COUNTED), reverse=True)
    rows = []
    for order, age in enumerate(counted, 1):
        rows.append({"順位": order, "月齢": age, "月額": monthly(order, age)})
    return {"内訳": rows, "世帯の月額": sum(r["月額"] for r in rows)}


def eldest_exit(gap_years: int) -> dict:
    """長子が数から抜ける前後で、**誰の額がいくら変わるか**。

    3人きょうだい。長子と3人目が `gap_years` 差、**真ん中は3人目の1歳上**に置きます。

    等間隔にしないのは、差が大きいと**真ん中の子が先に18歳年度末を越えてしまい**、
    前も後も0円で「変わらない」ことになるからです（差6歳で19歳）。
    **見たいのは順位が繰り上がっても額が動かないこと**なので、
    真ん中の子が受け取っている場合を置きます。
    """
    third_age = MONTHS_COUNTED - 12 * gap_years          # 抜ける月の3人目の月齢
    middle_age = third_age + 12
    eldest_age = third_age + 12 * gap_years
    before = household_month([eldest_age - 1, middle_age - 1, third_age - 1])
    after = household_month([eldest_age, middle_age, third_age])
    return {
        "前の月額": before["世帯の月額"],
        "後の月額": after["世帯の月額"],
        "差": after["世帯の月額"] - before["世帯の月額"],
        "真ん中の子の前": before["内訳"][1]["月額"],
        "真ん中の子の後": after["内訳"][0]["月額"],
        "末っ子の前": before["内訳"][2]["月額"],
        "末っ子の後": after["内訳"][1]["月額"],
    }


def age3_step(children: int) -> dict:
    """**3歳の段差**（全員3歳未満のとき → 全員3歳以上のとき）。"""
    under = sum(monthly(o, 0) for o in range(1, children + 1))
    over = sum(monthly(o, MONTHS_UNDER3) for o in range(1, children + 1))
    return {"人数": children, "全員3歳未満": under, "全員3歳以上": over,
            "段差": under - over}


def order_table() -> list[dict]:
    """順位ごとの総額（順位が最後まで変わらなかった場合）。"""
    rows = []
    for order in (1, 2, 3):
        total = total_for(order)
        rows.append({"順位": order, "総額": total,
                     "1人目の何倍": round(total / total_for(1), 2)})
    return rows


def grid() -> list[dict]:
    """図解の元になる表。**年齢差の表がこの計算の主題です。**"""
    return gap_table()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 公表資料が名指ししている値
    _checks.statutory(UNDER3_1_2, 15_000, "3歳未満の第1子・第2子の月額",
                      source="こども家庭庁「児童手当制度のご案内」2024年10月から")
    _checks.statutory(OVER3_1_2, 10_000, "3歳から高校生年代までの月額", source="同上")
    _checks.statutory(THIRD_ON, 30_000, "第3子以降の月額", source="同上")
    _checks.statutory(MONTHS_PAID, 216, "受け取れる月数（18歳年度末まで）",
                      source="児童手当法4条・同上")
    _checks.statutory(MONTHS_COUNTED, 264, "第3子として数える月数（22歳年度末まで）",
                      source="同上・2024年10月からの多子加算の数え方")
    _checks.statutory(PAYS_PER_YEAR, 6, "1年の支給回数", source="同上")

    # 2. 月額の形。**3人目だけ、3歳の段差が無いこと**が主張の1つ
    _checks.rounding(monthly(1, 0), UNDER3_1_2, "第1子・0歳の月額")
    _checks.rounding(monthly(1, MONTHS_UNDER3), OVER3_1_2, "第1子・3歳の月額")
    _checks.rounding(monthly(3, 0), THIRD_ON, "第3子・0歳の月額")
    _checks.rounding(monthly(3, MONTHS_UNDER3), THIRD_ON, "第3子・3歳の月額")
    _checks.rounding(monthly(1, MONTHS_PAID), 0, "18歳年度末を過ぎた月の月額")
    if monthly(1, 0) == monthly(1, MONTHS_UNDER3):
        raise _checks.TableError("第1子には3歳の段差があるはず")
    if monthly(3, 0) != monthly(3, MONTHS_UNDER3):
        raise _checks.TableError("第3子には3歳の段差が無いはず")

    # 3. この計算の主題そのもの
    # (a) 数える上限が、もらえる上限より4年長い。**この4年が主題の源です**
    _checks.greater(MONTHS_COUNTED, MONTHS_PAID,
                    "数える期間が、受け取る期間より長くない")
    _checks.rounding(unpaid_support_months(), 48, "受け取らずに数えられる月数")
    _checks.rounding(unpaid_support_value(), 960_000, "その4年が末っ子に運ぶ額")

    # (b) 境目は4歳。**5歳から、1歳ごとに12か月ぶん消える**
    _checks.rounding(max_gap_without_loss(), 4, "1円も失わない年齢差の上限")
    _checks.rounding(third_loss(4), 0, "年齢差4歳で失う額")
    _checks.rounding(loss_per_extra_year(), 12 * (THIRD_ON - OVER3_1_2),
                     "境目を1歳こえたときに消える額")
    _checks.never_decreases(third_loss, [0, 4, 5, 10, 18, 22],
                            "年齢差がひらいたのに、失う額が減っている")
    _checks.rounding(third_full_months(22), 0, "年齢差22歳のとき、3万円の月数")
    # **「月20,000円 × 216か月」ではありません**（この検査が実際に止めました）。
    # 落ちたぶんの受け皿は第2子の額で、**3歳未満だけは15,000円**なので、
    # 最初の36か月の差は20,000円ではなく15,000円です。
    _checks.rounding(third_loss(22),
                     MONTHS_UNDER3 * (THIRD_ON - UNDER3_1_2)
                     + (MONTHS_PAID - MONTHS_UNDER3) * (THIRD_ON - OVER3_1_2),
                     "年齢差22歳で失う額（30,000円を1か月も受け取れない）")
    _checks.greater(MONTHS_PAID * (THIRD_ON - OVER3_1_2), third_loss(22),
                    "失う額が「月20,000円 × 216か月」以上になっている"
                    "（3歳未満の36か月ぶんだけ小さいはず）")

    # (c) 長子が抜けても、**真ん中の子の額は変わらない**
    ex = eldest_exit(6)
    if ex["真ん中の子の前"] != ex["真ん中の子の後"]:
        raise _checks.TableError("長子が抜けたとき、真ん中の子の額が変わっている")
    _checks.rounding(ex["差"], -(THIRD_ON - OVER3_1_2),
                     "長子が抜けた月の、世帯の月額の変化")

    # (d) 総額。**3人目は1人目の2倍ではない**
    _checks.rounding(total_for(1), 2_340_000, "第1子の総額")
    _checks.rounding(total_for(3), 6_480_000, "第3子の総額（順位が変わらない場合）")
    _checks.greater(total_for(3) / total_for(1), 2.5,
                    "3人目が1人目の2.5倍以下（2.77倍のはず）")
    _checks.greater(2.9, total_for(3) / total_for(1),
                    "3人目が1人目の2.9倍以上（2.77倍のはず）")
    _checks.unique_by(gap_table(), lambda r: r["年齢差"], "年齢差の表")

    _checks.assumption_values(ASSUMPTIONS, name="jidou")


def main() -> None:
    check_tables()

    print("=== 3人目の月3万円を止めるのは、末っ子の年齢ではなく"
          f"「長子との年齢差」（境目は{max_gap_without_loss()}歳）===")
    for r in gap_table():
        mark = "" if r["失う額"] == 0 else "  ←"
        print(f"  長子との年齢差 {r['年齢差']:>2}歳"
              f"  30,000円の月数 {r['3万円の月数']:>3}か月"
              f"  総額 {r['総額']:>9,}円"
              f"  **失う額 {r['失う額']:>9,}円**{mark}")
    print(f"  → 受け取れるのは18歳年度末までの{MONTHS_PAID}か月、"
          f"第3子として**数えられる**のは22歳年度末までの{MONTHS_COUNTED}か月で、"
          f"**4年ずれています。** だから年齢差{max_gap_without_loss()}歳までは"
          "1か月も削られず、"
          f"**{max_gap_without_loss() + 1}歳から1歳ひらくごとに"
          f"{loss_per_extra_year():,}円**ずつ消えます")

    print("\n=== 18歳から22歳の長子は、1円も受け取っていないのに"
          "末っ子の3万円を支えている ===")
    print(f"  受け取れる上限   18歳年度末 = {MONTHS_PAID}か月")
    print(f"  数えられる上限   22歳年度末 = {MONTHS_COUNTED}か月")
    print(f"  差               {unpaid_support_months()}か月"
          f"（{unpaid_support_months() // 12}年）")
    print(f"  その間に末っ子が受け取る差額  月{THIRD_ON - OVER3_1_2:,}円"
          f" × {unpaid_support_months()}か月 = **{unpaid_support_value():,}円**")
    print("  → **長子の手当は18歳年度末で止まります。** それでも22歳年度末までは"
          "第1子として数えられるので、**もらっていない4年間が、末っ子の額を"
          "第3子のまま保っています**")

    print("\n=== 長子が数から抜けた月、減るのは末っ子だけ"
          "（真ん中の子は繰り上がっても1円も変わらない）===")
    for gap in (6, 8, 10):
        ex = eldest_exit(gap)
        print(f"  年齢差 {gap:>2}歳"
              f"  世帯 {ex['前の月額']:>7,}円 → {ex['後の月額']:>7,}円"
              f"（{ex['差']:>+8,}円）"
              f"  真ん中 {ex['真ん中の子の前']:,}円 → {ex['真ん中の子の後']:,}円"
              f"  末っ子 {ex['末っ子の前']:,}円 → {ex['末っ子の後']:,}円")
    print("  → 真ん中の子は**第2子から第1子へ繰り上がります**が、"
          f"第1子も第2子も{OVER3_1_2:,}円なので**額は変わりません。**"
          "**順位が下がって損をするのは、いちばん下の子だけ**です")

    print("\n=== 3歳の段差は、第1子と第2子にしかない"
          "（3人目は3歳をまたいでも30,000円のまま）===")
    for n in (1, 2, 3, 4):
        r = age3_step(n)
        print(f"  子ども {r['人数']}人"
              f"  全員3歳未満 {r['全員3歳未満']:>7,}円"
              f"  → 全員3歳以上 {r['全員3歳以上']:>7,}円"
              f"  **段差 {r['段差']:>6,}円**")
    print(f"  → 段差は**第1子・第2子の{UNDER3_1_2 - OVER3_1_2:,}円ぶんだけ**です。"
          "3人きょうだいでも4人きょうだいでも段差は同じ10,000円で、"
          "**3人目から先を何人足しても増えません**")

    print("\n=== 順位ごとの総額（3人目は1人目の2倍ではない）===")
    for r in order_table():
        print(f"  第{r['順位']}子  総額 {r['総額']:>9,}円"
              f"  **1人目の {r['1人目の何倍']:.2f}倍**")
    print(f"  → 第1子は3歳で{UNDER3_1_2:,}円から{OVER3_1_2:,}円へ下がるのに、"
          f"第3子は{MONTHS_PAID}か月ずっと{THIRD_ON:,}円です。"
          "**下がる期間が無いぶんだけ、倍率が2倍を超えます**")


if __name__ == "__main__":
    main()
