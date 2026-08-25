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
DAYS_PER_WEEK = 7          # 暦の値。制度の値ではない（週あたりに直すときだけ使う）

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


def calendar_span_cost(monthly: int = 300_000, days_off: int = 20) -> dict:
    """**暦日数のぶれが、いくらの差になるか**を1つの金額にして返す。

    ## この関数を足した理由（2026-08-16）

    「連続する3か月の暦日数（分母は最大4日ぶれる）」の節は、**日数しか
    出していませんでした**（`1月〜3月 90日` …）。そのせいで `topic_forge` が
    この節を**2回連続で落としています** —— 書き手は「◯◯円変わる」という題を
    立てるのに、**その金額が節のどこにも載っていない**からです。
    節は在庫として数えられているのに、**実際には一度も動画にできませんでした。**

    `season_grid` は窓ごとの額を出しますが、**この節の主題は窓どうしの「差」**で、
    差そのものはどの表にも載っていませんでした。**主題の数字を表に載せます。**

    差が出る理屈は分母だけです。平均賃金は `3か月の賃金 ÷ 暦日数` なので、
    **月給が同じでも、休業が始まる月で分母が 89〜92日 に動きます。**
    有利なのは**暦日の短い窓**（2月をまたぐ側）で、不利なのは 92日 の窓です。
    """
    total = monthly * LOOKBACK_MONTHS
    rows = [(label, span, daily_allowance(total, span))
            for label, span in calendar_day_spans()]
    best = min(rows, key=lambda r: r[1])     # 暦日が短い＝分母が小さい＝手当が高い
    worst = max(rows, key=lambda r: r[1])
    return {
        "月給": monthly,
        "休んだ日数": days_off,
        "有利な窓": best[0], "有利な暦日": best[1],
        "有利な日額": best[2], "有利な総額": best[2] * days_off,
        "不利な窓": worst[0], "不利な暦日": worst[1],
        "不利な日額": worst[2], "不利な総額": worst[2] * days_off,
        "日額の差": best[2] - worst[2],
        "総額の差": (best[2] - worst[2]) * days_off,
        "暦日の差": worst[1] - best[1],
    }


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


def weekly_boundary() -> list[dict]:
    """最低保障が勝つ境目を、**週あたりの勤務日数**に直す。

    ## この節を足した理由（2026-08-17）

    `boundary_worked_days()` は「3か月で54.6日」を出しますが、**印字しているのは
    暦日91日の1点だけ**でした。暦日は 89〜92日 に動くので、境目の労働日数も
    **53.4日〜55.2日** と動きます。「54.6日」を覚えて帰った人は、
    2月をまたぐ期間では**間違えます。**

    ところが**週あたりに直すと、動きません。**
    境目は `暦日 × 0.6`、1週間は7日なので、週あたりでは

        暦日 × 0.6 ÷ (暦日 ÷ 7) = 0.6 × 7 = **4.2日**

    **暦日が約分で消えます。** 時給も賃金総額も先に消えているので
    （`boundary_worked_days` の説明）、**残るのは率と曜日だけ**です。
    だから境目は、誰にとっても・いつ休んでも **週4.2日**。
    """
    out = []
    for _, span in [(None, s) for s in (CALENDAR_DAYS_MIN, 90, 91, CALENDAR_DAYS_MAX)]:
        days = boundary_worked_days(span)
        out.append({
            "3か月の暦日": span,
            "境目の労働日数": days,
            "週あたりに直すと": days / (span / DAYS_PER_WEEK),
        })
    return out


def pay_form_gap(hourly: int = 1_200, hours_per_day: int = 8,
                 calendar_days: int = 91, days_off: int = 20) -> list[dict]:
    """**賃金も労働日数もまったく同じで、給与の形だけが違う2人**を並べる。

    ## この節を足した理由（2026-08-17）

    `average_wage()` は `worked_days` を渡さなければ最低保障を使いません。
    これは条文どおりで、**12条1項但書は日給・時間給・出来高払にしか掛かりません。**
    ところが `shift_grid()` は時給制の側しか印字しておらず、
    **月給制の同じ人がいくらになるかは、どの表にも出ていませんでした。**

    並べると、最低保障は「安全網」ではなく**支給額そのものを分ける線**です ——
    週4日以下では、**同じ賃金・同じ勤務日数でも、時給制のほうが高くなります。**
    しかも時給制の側は `日給 × 0.6 × 0.6` なので、
    **勤務日数を減らしても日額が1円も動きません**（週4日も週2日も同額）。
    月給制は暦日で割るだけなので、**減らしたぶんだけ下がり続けます。**
    """
    weeks = calendar_days / DAYS_PER_WEEK
    daily_wage = hourly * hours_per_day
    out = []
    for weekly_days in (5, 4, 3, 2):
        worked = round(weeks * weekly_days)
        total = int(daily_wage * worked)
        by_hour = int(average_wage(total, calendar_days, worked)["採る額"] * KYUGYO_RATE)
        by_month = int(average_wage(total, calendar_days)["採る額"] * KYUGYO_RATE)
        out.append({
            "週の勤務日数": weekly_days,
            "3か月の労働日数": worked,
            "賃金総額": total,
            "時給制の日額": by_hour,
            "月給制の日額": by_month,
            "日額の差": by_hour - by_month,
            f"{days_off}日休んだときの差": (by_hour - by_month) * days_off,
            "倍率": by_hour / by_month,
        })
    return out


def ratio_span(monthly: int = 300_000) -> dict:
    """**月給に対する率を決めているのは、金額ではなくカレンダーだけ。**

    ## この節を足した理由（2026-08-17）

    `ratio_to_monthly()` は月給30万円の1点しか印字していませんでした。
    **月給は引数として書いてあるのに、一度も動かしていません。**

    動かすと、率は**変わりません**（円未満の切り捨てのぶれだけ）。
    平均賃金も休業手当も賃金に比例するので、**月給が約分で消えます。**
    代わりに率を動かしているのは `暦日` と `その月の労働日数` の2つで、
    その組み合わせだけで **37.17% から 46.51% まで、9.3ポイント**開きます。

    つまり「6割もらえる」の実質は月給では決まらず、
    **休んだのが何月か・その月に何日出勤日があったか**で決まります。
    """
    total = monthly * LOOKBACK_MONTHS
    rows = []
    for span in range(CALENDAR_DAYS_MIN, CALENDAR_DAYS_MAX + 1):
        for work_days in (19, 20, 21, 22, 23):
            d = daily_allowance(total, span)
            rows.append({"3か月の暦日": span, "その月の労働日数": work_days,
                         "休業手当の日額": d, "その月の休業手当": d * work_days,
                         "月給に対する率": d * work_days / monthly})
    best = max(rows, key=lambda r: r["月給に対する率"])
    worst = min(rows, key=lambda r: r["月給に対する率"])
    return {
        "月給": monthly,
        "いちばん高い率": best, "いちばん低い率": worst,
        "率の幅": best["月給に対する率"] - worst["月給に対する率"],
        "率の倍率": best["月給に対する率"] / worst["月給に対する率"],
        "組み合わせ": rows,
    }


def ratio_by_monthly(monthlies: tuple[int, ...] = (150_000, 300_000, 600_000,
                                                   1_000_000),
                     calendar_days: int = 91, work_days: int = 20) -> list[dict]:
    """同じ暦日・同じ労働日数で、月給だけを動かす。**率は動きません。**"""
    out = []
    for m in monthlies:
        d = daily_allowance(m * LOOKBACK_MONTHS, calendar_days)
        out.append({"月給": m, "休業手当の日額": d,
                    "その月の休業手当": d * work_days,
                    "月給に対する率": d * work_days / m})
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

    #    (f) **主題**: 境目を週あたりに直すと、暦日が約分で消えて 4.2日 で一定
    for row in weekly_boundary():
        _checks.close(row["週あたりに直すと"], MINIMUM_RATE * DAYS_PER_WEEK,
                      f"暦日{row['3か月の暦日']}日での境目（週あたり）", tol=1e-9)
    #    (g) **主題**: 賃金も労働日数も同じで、給与の形だけが違うとどうなるか
    gap = pay_form_gap()
    by_week = {r["週の勤務日数"]: r for r in gap}
    if by_week[5]["日額の差"] != 0:
        raise _checks.TableError(
            f"週5日で時給制と月給制の差が {by_week[5]['日額の差']}円。"
            f"暦日割が勝つ側なので、同額のはず")
    for wd in (4, 3, 2):
        _checks.greater(by_week[wd]["時給制の日額"], by_week[wd]["月給制の日額"],
                        f"週{wd}日で、時給制が月給制を上回っていない")
    #        時給制の側は 日給 × 0.6 × 0.6 なので、勤務日数を減らしても動かない
    fixed = {by_week[wd]["時給制の日額"] for wd in (4, 3, 2)}
    if len(fixed) != 1:
        raise _checks.TableError(
            f"週4日以下で時給制の日額が {sorted(fixed)} と割れています。"
            f"最低保障は日給に率を掛けるだけなので、勤務日数では動かないはず")
    _checks.rounding(fixed.pop(), int(1_200 * 8 * MINIMUM_RATE * KYUGYO_RATE),
                     "最低保障で決まる日額（日給の36パーセント）")
    #        月給制の側は暦日で割るだけなので、勤務日数を減らせば下がり続ける
    _checks.increases_with(lambda wd: by_week[wd]["月給制の日額"], (2, 3, 4, 5),
                           "月給制の日額が、勤務日数を増やしても増えていない")
    #    (h) **主題**: 率を動かしているのは月給ではなく暦日と労働日数
    ratios = [r["月給に対する率"] for r in ratio_by_monthly()]
    for r in ratios:
        _checks.close(r, ratios[0], "月給を変えたのに率が動いた", tol=1e-4)
    span = ratio_span()
    if (span["いちばん高い率"]["3か月の暦日"], span["いちばん高い率"]["その月の労働日数"]) \
            != (CALENDAR_DAYS_MIN, 23):
        raise _checks.TableError(
            "率がいちばん高いのは「暦日が最短・労働日数が最多」のはず。"
            f"出たのは {span['いちばん高い率']}")
    if (span["いちばん低い率"]["3か月の暦日"], span["いちばん低い率"]["その月の労働日数"]) \
            != (CALENDAR_DAYS_MAX, 19):
        raise _checks.TableError(
            "率がいちばん低いのは「暦日が最長・労働日数が最少」のはず。"
            f"出たのは {span['いちばん低い率']}")
    _checks.ratio(span["率の幅"], "率の幅")


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
    _gap = calendar_span_cost()
    print(f"  前提: 月給{_gap['月給']:,}円 / {_gap['休んだ日数']}日休んだ場合")
    _total = _gap["月給"] * LOOKBACK_MONTHS
    for label, span in calendar_day_spans():
        _d = daily_allowance(_total, span)
        print(f"  {label:>8}  {span}日  日額 {_d:>6,}円"
              f"  {_gap['休んだ日数']}日で {_d * _gap['休んだ日数']:>8,}円")
    print(f"  **暦日が {_gap['暦日の差']}日ちがうだけで、"
          f"{_gap['休んだ日数']}日ぶんの休業手当は {_gap['総額の差']:,}円 変わります**"
          f"（日額の差 {_gap['日額の差']:,}円）")
    print(f"    有利 {_gap['有利な窓']}（{_gap['有利な暦日']}日）"
          f" {_gap['有利な総額']:,}円  ／  "
          f"不利 {_gap['不利な窓']}（{_gap['不利な暦日']}日）"
          f" {_gap['不利な総額']:,}円")
    print("    **月給は同じです。**変わっているのは平均賃金の分母（暦日数）だけ。")

    print("\n=== 最低保障が勝つ境目は、暦日が何日でも「週4.2日」 ===")
    for row in weekly_boundary():
        print(f"  3か月の暦日 {row['3か月の暦日']}日"
              f"  境目の労働日数 {row['境目の労働日数']:>5.1f}日"
              f"  → 週あたり {row['週あたりに直すと']:.1f}日")
    print(f"  **労働日数のほうは {weekly_boundary()[0]['境目の労働日数']:.1f}日〜"
          f"{weekly_boundary()[-1]['境目の労働日数']:.1f}日 と動きます。**"
          f"週あたりに直すと暦日が約分で消え、"
          f"{MINIMUM_RATE} × {DAYS_PER_WEEK}日 = "
          f"{MINIMUM_RATE * DAYS_PER_WEEK:.1f}日 だけが残ります。")
    print("    だから週5日勤務は暦日割、**週4日以下は最低保障**。"
          "時給にも、休んだ季節にもよりません。")

    print("\n=== 賃金も勤務日数も同じ。ちがうのは時給制か月給制かだけ ===")
    _gapf = pay_form_gap()
    print(f"  前提: 時給1,200円 × 1日8時間（日給9,600円） / 暦日91日 / 20日休んだ場合")
    for row in _gapf:
        print(f"  週{row['週の勤務日数']}日  労働{row['3か月の労働日数']:>2}日"
              f"  賃金総額 {row['賃金総額']:>9,}円"
              f"  時給制 {row['時給制の日額']:>6,}円"
              f"  月給制 {row['月給制の日額']:>6,}円"
              f"  差 {row['日額の差']:>6,}円"
              f"（20日で {row['20日休んだときの差']:>7,}円・{row['倍率']:.2f}倍）")
    print("  **週5日では1円も違いません**（どちらも暦日割が勝つ）。"
          "**週4日から下は、時給制のほうが高くなります。**")
    print(f"  時給制の日額は週4日でも週2日でも "
          f"{_gapf[-1]['時給制の日額']:,}円 のまま ——"
          f" 最低保障は「日給 × {MINIMUM_RATE} × {KYUGYO_RATE}」で、"
          f"**勤務日数が式に入っていないから**です。")
    print("    月給制の側は暦日で割るだけなので、**働く日を減らしたぶん下がり続けます。**")

    print("\n=== 月給に対する率を決めているのは、金額ではなくカレンダー ===")
    for row in ratio_by_monthly():
        print(f"  月給 {row['月給']:>9,}円  日額 {row['休業手当の日額']:>7,}円"
              f"  その月 {row['その月の休業手当']:>9,}円"
              f"  月給の {row['月給に対する率'] * 100:5.2f}%")
    _span = ratio_span()
    _hi, _lo = _span["いちばん高い率"], _span["いちばん低い率"]
    print(f"  **月給を{ratio_by_monthly()[0]['月給']:,}円から"
          f"{ratio_by_monthly()[-1]['月給']:,}円まで動かしても率は同じ**"
          f"（円未満の切り捨てのぶれだけ）。賃金は約分で消えます。")
    print(f"  代わりに率を動かすのは暦日と労働日数の2つで、"
          f"**{_lo['月給に対する率'] * 100:.2f}% 〜 {_hi['月給に対する率'] * 100:.2f}%"
          f"（{_span['率の幅'] * 100:.2f}ポイント・{_span['率の倍率']:.2f}倍）**:")
    print(f"    いちばん高い  暦日{_hi['3か月の暦日']}日 × 労働{_hi['その月の労働日数']}日"
          f"  → {_hi['月給に対する率'] * 100:.2f}%")
    print(f"    いちばん低い  暦日{_lo['3か月の暦日']}日 × 労働{_lo['その月の労働日数']}日"
          f"  → {_lo['月給に対する率'] * 100:.2f}%")
