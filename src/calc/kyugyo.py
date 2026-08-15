"""**同じ月給・同じ休業日数でも、休業した季節で休業手当が変わる。**

一般の解説はここで止まります ——「会社の都合で休ませたら、平均賃金の60パーセント以上の
休業手当を払わなければなりません」（労働基準法26条）。

**60パーセントを掛ける相手が、月給そのものではありません。** 平均賃金は
**直前3か月の賃金総額を、その3か月の暦日数で割った額**です（12条1項）。
暦日で割るので、**31日の月が並ぶ期間は分母が大きくなり、平均賃金が下がります。**
3か月の暦日は**89日から92日まで**動くので、同じ月給30万円でも
1日あたりの休業手当は**6,067円から5,869円まで、198円ちがいます。**
20日休ませたら**3,960円**の差です。会社が悪いのでも計算を間違えたのでもなく、
**カレンダーだけで決まっています。**

そしてもう1つ、時給制と日給制には**最低保障**があります（12条1項但書）——
賃金総額を**労働日数**で割って60パーセント。暦日割と比べて高いほうが平均賃金です。
どちらが勝つかは**働いた日数の割合だけ**で決まり、境目は
**3か月で54.6日**（暦日91日のとき）。週5日勤務なら暦日割、
**週4日以下なら最低保障のほう**が採られます。同じ時給・同じ会社でも、
**シフトが週1日ちがうだけで、休業手当の出し方が変わります。**

## この計算で見ないもの（前提として画面に出す）

- 賃金総額には通勤手当などを含めますが、賞与（3か月を超える期間ごとの賃金）と
  臨時の賃金は入れません。ここでは月額の賃金だけで計算しています。
- 業務外の傷病や育児休業などの期間は、暦日と賃金の両方から除きます。
  ここでは、直前3か月にそれが無かった場合で計算しています。
- 26条は「60パーセント**以上**」なので、これは**下限**です。
  就業規則で上乗せしていれば、そちらが優先します。
- 天災など「使用者の責に帰すべき事由」に当たらない休業には、この手当は出ません。
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "直前3か月の賃金は毎月同額として計算しています。残業代が月によって違えば平均賃金も動きます",
    "賞与と臨時の賃金は賃金総額に入れていません。3か月を超える期間ごとに払われるものは除きます",
    "直前3か月に、業務外の傷病や育児休業などの控除する期間は無かったものとしています",
    "休業手当は平均賃金の60パーセントちょうどで出しています。26条は60パーセント以上なので、これは下限です",
    "平均賃金は銭未満を切り捨て、休業手当の日額は円未満を切り捨てています",
    "使用者の責に帰すべき事由による休業だけが対象です。天災などはこの手当の対象外です",
]

# ---- 制度の値。労働基準法12条・26条。1947年の制定から変わっていない -----------
KYUGYO_RATE = 0.6          # 休業手当の率（26条）
MINIMUM_RATE = 0.6         # 最低保障の率（12条1項但書）
LOOKBACK_MONTHS = 3        # 平均賃金の算定期間（12条1項）

# 直前3か月の暦日数として取りうる値。**連続する3か月の日数の和**
# 最短は2月・3月・4月の 28+31+30＝89（うるう年は90）
# 最長は 31+30+31＝92（5〜7月・7〜9月・10〜12月など）
CALENDAR_DAYS_MIN = 89
CALENDAR_DAYS_MAX = 92


def calendar_day_spans() -> list[tuple[str, int]]:
    """連続する3か月の暦日数を、実際に月の日数から足して並べる。**思い出しで書かない。**"""
    lengths = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # 平年
    names = ["1月", "2月", "3月", "4月", "5月", "6月",
             "7月", "8月", "9月", "10月", "11月", "12月"]
    out = []
    for i in range(12):
        span = sum(lengths[(i + k) % 12] for k in range(LOOKBACK_MONTHS))
        out.append((f"{names[i]}〜{names[(i + LOOKBACK_MONTHS - 1) % 12]}", span))
    return out


def average_wage(total_wage: int, calendar_days: int,
                 worked_days: int | None = None) -> dict:
    """平均賃金。**暦日で割った額と、最低保障の高いほう。**

    `worked_days` を渡さないと（月給制）、最低保障は使いません（12条1項但書は
    日給・時間給・出来高払にだけかかります）。
    """
    by_calendar = _sen(total_wage / calendar_days)
    row = {"暦日割": by_calendar, "最低保障": None, "採る額": by_calendar,
           "採った側": "暦日割"}
    if worked_days:
        floor = _sen(total_wage / worked_days * MINIMUM_RATE)
        row["最低保障"] = floor
        if floor > by_calendar:
            row["採る額"], row["採った側"] = floor, "最低保障"
    return row


def _sen(value: float) -> float:
    """銭未満を切り捨てる。**平均賃金は銭までで止めます。**"""
    return int(value * 100) / 100


def daily_allowance(total_wage: int, calendar_days: int,
                    worked_days: int | None = None) -> int:
    """休業手当の日額。**平均賃金の60パーセント、円未満は切り捨て。**"""
    return int(average_wage(total_wage, calendar_days, worked_days)["採る額"]
               * KYUGYO_RATE)


def season_grid(monthly: int = 300_000, days_off: int = 20) -> list[dict]:
    """同じ月給でも、算定期間の暦日数で休業手当が変わることを並べる。"""
    total = monthly * LOOKBACK_MONTHS
    out = []
    for label, span in calendar_day_spans():
        d = daily_allowance(total, span)
        out.append({
            "算定期間": label,
            "暦日数": span,
            "平均賃金": average_wage(total, span)["採る額"],
            "休業手当の日額": d,
            f"{days_off}日休んだとき": d * days_off,
        })
    return out


def boundary_worked_days(calendar_days: int = 91) -> float:
    """最低保障が暦日割を上回る境目の労働日数。

    暦日割は `W / 暦日`、最低保障は `W / 労働日 × 0.6`。
    賃金総額 `W` は両辺で消えるので、**境目は日数の比だけで決まります。**
    """
    return calendar_days * MINIMUM_RATE


def shift_grid(hourly: int = 1_200, hours_per_day: int = 8,
               calendar_days: int = 91) -> list[dict]:
    """週の勤務日数ごとに、暦日割と最低保障のどちらが採られるか。"""
    out = []
    weeks = calendar_days / 7
    for weekly_days in (5, 4, 3, 2):
        worked = round(weeks * weekly_days)
        total = int(hourly * hours_per_day * worked)
        a = average_wage(total, calendar_days, worked)
        out.append({
            "週の勤務日数": weekly_days,
            "3か月の労働日数": worked,
            "賃金総額": total,
            "暦日割": a["暦日割"],
            "最低保障": a["最低保障"],
            "採った側": a["採った側"],
            "休業手当の日額": int(a["採る額"] * KYUGYO_RATE),
        })
    return out


def ratio_to_monthly(monthly: int = 300_000) -> list[dict]:
    """「6割もらえる」と言うが、月給に対しては何パーセントになるか。

    月給を暦日で割ってから、月の**労働日数**だけ払うので、
    **6割にはなりません。**
    """
    total = monthly * LOOKBACK_MONTHS
    out = []
    for span, work_days in ((89, 20), (91, 20), (92, 20),
                            (91, 21), (91, 22), (91, 23)):
        d = daily_allowance(total, span)
        paid = d * work_days
        out.append({
            "3か月の暦日": span,
            "その月の労働日数": work_days,
            "休業手当の日額": d,
            "その月の休業手当": paid,
            "月給に対する率": paid / monthly,
        })
    return out


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(KYUGYO_RATE, 0.6, "休業手当の率", source="労働基準法26条")
    _checks.statutory(MINIMUM_RATE, 0.6, "最低保障の率", source="労働基準法12条1項但書")
    _checks.statutory(LOOKBACK_MONTHS, 3, "平均賃金の算定期間", source="労働基準法12条1項")
    _checks.ratio(KYUGYO_RATE, "休業手当の率")
    _checks.ratio(MINIMUM_RATE, "最低保障の率")

    # 2. 暦日数は思い出しではなく、月の日数から足したものと一致すること
    spans = [s for _, s in calendar_day_spans()]
    _checks.rounding(min(spans), CALENDAR_DAYS_MIN, "連続する3か月の暦日数の最小（平年）")
    _checks.rounding(max(spans), CALENDAR_DAYS_MAX, "連続する3か月の暦日数の最大")

    # 3. 計算の向き —— この計算の主題そのもの
    #    (a) **主題**: 暦日が増えれば、同じ月給でも休業手当は減る
    _checks.decreases_with(lambda d: daily_allowance(900_000, d),
                           (89, 90, 91, 92),
                           "算定期間の暦日が増えたのに、休業手当が減っていない")
    #    (b) 賃金が増えれば休業手当も増える
    _checks.increases_with(lambda w: daily_allowance(w * 3, 91),
                           (200_000, 300_000, 400_000, 500_000),
                           "月給が増えたのに、休業手当が増えていない")
    #    (c) **主題**: 境目は暦日の6割。週5日は暦日割、週4日以下は最低保障
    _checks.rounding(boundary_worked_days(91), 54.6, "最低保障が勝つ境目の労働日数")
    sides = {r["週の勤務日数"]: r["採った側"] for r in shift_grid()}
    if sides[5] != "暦日割":
        raise _checks.TableError(f"週5日で採られたのが {sides[5]}。暦日割のはず")
    for wd in (4, 3, 2):
        if sides[wd] != "最低保障":
            raise _checks.TableError(f"週{wd}日で採られたのが {sides[wd]}。最低保障のはず")
    #    (d) 最低保障は、暦日割を下回ることがあっても採られない（高いほうを採る）
    for row in shift_grid():
        _checks.greater(row["休業手当の日額"] + 1,
                        int(min(row["暦日割"], row["最低保障"]) * KYUGYO_RATE),
                        f"週{row['週の勤務日数']}日で、低いほうを採ってしまっている")
    #    (e) **主題**: 月給に対する率は6割にならない（暦日で割ってから労働日だけ払う）
    for row in ratio_to_monthly():
        _checks.ratio(row["月給に対する率"], "月給に対する休業手当の率")
        if row["月給に対する率"] >= KYUGYO_RATE:
            raise _checks.TableError(
                f"月給に対する率が {row['月給に対する率']:.3f}。"
                f"暦日で割って労働日だけ払うので、6割には届かないはず")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 同じ月給30万円でも、休業した季節で休業手当が変わる ===")
    for row in season_grid():
        print(f"  {row['算定期間']:>8}  暦日{row['暦日数']}日"
              f"  平均賃金 {row['平均賃金']:>9,.2f}円"
              f"  日額 {row['休業手当の日額']:>6,}円"
              f"  20日で {row['20日休んだとき']:>8,}円")

    print("\n=== 時給制は「暦日割」と「最低保障」の高いほう。境目は3か月で54.6日 ===")
    for row in shift_grid():
        print(f"  週{row['週の勤務日数']}日  労働{row['3か月の労働日数']:>2}日"
              f"  暦日割 {row['暦日割']:>8,.2f}円"
              f"  最低保障 {row['最低保障']:>8,.2f}円"
              f"  → {row['採った側']}  日額 {row['休業手当の日額']:>6,}円")

    print("\n=== 「6割もらえる」は、月給に対しては何パーセントか ===")
    for row in ratio_to_monthly():
        print(f"  暦日{row['3か月の暦日']}日  労働{row['その月の労働日数']}日"
              f"  日額 {row['休業手当の日額']:>6,}円"
              f"  その月 {row['その月の休業手当']:>8,}円"
              f"  月給の {row['月給に対する率'] * 100:4.1f}%")

    print("\n=== 連続する3か月の暦日数（分母は最大4日ぶれる） ===")
    for label, span in calendar_day_spans():
        print(f"  {label:>8}  {span}日")
