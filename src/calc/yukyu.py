"""**年5日しか使わない人は、勤続20年で241日を捨てている。**

一般の解説はここで止まります ——「有給は勤続6か月で10日、6年6か月で20日。
使わなかった分は翌年に繰り越せます。時効は2年です」。

**繰り越せる、で終わると、捨てている量が見えません。** 繰越は1年ぶんだけなので、
付与日数が消化日数を上回っている人は、**その差がそのまま毎年消えます。**
年20日もらって年5日使う人が失うのは、**勤続12年で121日、20年で241日**。
週5日勤務の労働日でかぞえて**11か月ぶん**です。

消える量は一定ではありません。**勤続2年6か月から始まり、7年6か月で毎年15日に達して
そこで止まります**（付与が20日で頭打ちになるため）。

もう1つ、比例付与の側に、誰も掛け算していない境目があります。
**年5日の時季指定義務は「10日以上付与された人」にかかります**（労働基準法39条7項）。
週4日勤務が10日に届くのは**勤続3年6か月**、週3日は**5年6か月**、
**週2日以下は勤続何年でも一生かかりません**（最大でも7日）。
同じ「パート」でも、週の日数が1日ちがうだけで、
**会社が5日取らせる義務を負うかどうかが変わります。**

**そして、比例付与の要件そのものが、ほとんど正しく書かれていません。**
39条3項・施行規則24条の3は「週4日以下」**かつ**「週30時間未満」の**AND**です。
一般の解説は前半だけを書いて「週4日なら15日が上限」で止まりますが、
**週4日でも1日7時間30分（週30時間）働けば、上限は20日**になります。
勤続20年でかぞえると **269日 → 361日**、月給30万の日給に直して
**1,592,308円**の差が、**1日の所定労働時間1分**の側に立っています。

しかも1日の上限は8時間（32条2項）なので、**この抜け道があるのは週4日だけ**です
（週3日は1日8時間でも週24時間で、30時間に永久に届かない）。
逆向きの帰結もあります —— **週5日は時間を見ずに通常の労働者**なので、
**週25時間（5日×5時間）は生涯361日、週28時間（4日×7時間）は生涯269日**。
**3時間よけいに働いて、92日少ない。**

もう1つ、退職の側。有給は付与日に**一括で**発生します（日割りではありません）。
だから**退職日が付与日の前日か当日か**で、その回の付与がまるごと在るか無いかに
分かれます。月給30万・週5日なら、**勤続6か月の1日で138,462円、
6年6か月以降はどの回も276,923円**。**在籍1日の値段**です。

## この計算で見ないもの（前提として画面に出す）

- 消化の順序は**古いほうから**としています。法律は順序を定めていないので、
  新しいほうから消化する運用だと、捨てる量はここより増えます。
- 出勤率8割の要件は、満たしている前提です（別の節で切ったときの影響を出します）。
- 会社が独自に上乗せしている日数、時間単位年休、計画的付与は入れていません。
- 1日の所定労働時間は8時間までとしています。変形労働時間制を使えば1日8時間を
  超えられるので、その場合は週3日以下でも週30時間に届きます（入れていません）。
- 退職の節は「付与されるかどうか」だけを見ています。**付与された有給を
  実際に消化できるか**は、残りの在籍日数と会社の時季変更権しだいです。
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "労働基準法39条の法定日数だけで計算しています。会社が独自に上乗せしている分は入れていません",
    "出勤率8割の要件は満たしている前提です。8割を切った年は付与がゼロになります",
    "繰り越した有給は古いほうから使う前提です。新しいほうから使う運用だと、消える日数はここより増えます",
    "時効は2年なので、繰り越せるのは1年ぶんだけです。2年前の分は消えます",
    "週の所定労働日数は5日・4日・3日・2日・1日のどれかで、年間を通じて一定としています。"
    "途中で変わると付与日数も変わります",
    "時間単位年休や半日単位の取得は、日数に換算せずそのまま日でかぞえています",
    "有給1日の賃金は「通常の賃金」を払う方式とし、月給 ÷ 1か月平均所定労働日数 で出しています。"
    "平均賃金方式や標準報酬日額方式だと、1日あたりの額は変わります",
    "1か月平均所定労働日数は 週の所定労働日数 × 52 ÷ 12 としています。"
    "祝日や年末年始の休みは引いていないので、実際の日給はここより高く出ます",
]

# ---- 制度の値。**労働基準法39条・同施行規則24条の3。1999年以降変わっていない** ----
# 勤続の刻み（年）。6か月、1年6か月、…、6年6か月以上
SERVICE_YEARS: tuple[float, ...] = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5)

# 通常の労働者（週5日以上、または週30時間以上）。労働基準法39条1項・2項
FULL_TIME: tuple[int, ...] = (10, 11, 12, 14, 16, 18, 20)

# 比例付与。週の所定労働日数 → 勤続の刻みごとの日数（施行規則24条の3）
PRORATED: dict[int, tuple[int, ...]] = {
    4: (7, 8, 9, 10, 12, 13, 15),
    3: (5, 6, 6, 8, 9, 10, 11),
    2: (3, 4, 4, 5, 6, 6, 7),
    1: (1, 2, 2, 2, 3, 3, 3),
}

# 比例付与の「対象になる側」の要件。**39条3項・施行規則24条の3は2つの条件のANDです**
# —— 週の所定労働日数が4日以下、**かつ**週の所定労働時間が30時間未満。
# 片方だけを覚えていると、週4日30時間の人を15日で止めてしまいます（実際は20日）。
FULLTIME_WEEKLY_HOURS = 30    # これ以上なら、週4日でも通常の労働者と同じ付与
PRORATED_MAX_WEEKLY_DAYS = 4  # 週5日以上は、時間を見るまでもなく通常の労働者
LEGAL_DAILY_HOURS = 8         # 労働基準法32条2項。変形労働時間制を使わない場合の1日の上限

OBLIGATION_THRESHOLD = 10   # 39条7項。10日以上つく人に、年5日の時季指定義務
OBLIGATION_DAYS = 5         # 同項。会社が時季を指定して取らせる日数
CARRY_YEARS = 1             # 時効2年（115条）＝繰り越せるのは1年ぶん
WEEKS_PER_YEAR = 52         # 1か月平均所定労働日数を出すための週数（暦の近似）


def table_for(weekly_days: int) -> tuple[int, ...]:
    """週の所定労働日数ごとの付与日数の並び。5日以上は通常の労働者。"""
    if weekly_days >= 5:
        return FULL_TIME
    if weekly_days not in PRORATED:
        raise ValueError(f"週{weekly_days}日の表は無い")
    return PRORATED[weekly_days]


def granted_at(nth: int, weekly_days: int = 5) -> int:
    """`nth` 回目（0起点）の付与日数。7回目以降は頭打ちで同じ日数。"""
    row = table_for(weekly_days)
    return row[min(nth, len(row) - 1)]


def cumulative(years: int, weekly_days: int = 5) -> int:
    """勤続 `years` 年までに**付与された**日数の累計（使ったかどうかは見ない）。

    付与は勤続6か月のときが1回目で、以後1年ごと。**勤続20年なら20回**です。
    """
    return sum(granted_at(i, weekly_days) for i in range(years))


def obligation_starts(weekly_days: int) -> float | None:
    """年5日の時季指定義務がかかる最初の勤続年数。**一生かからないなら None。**"""
    row = table_for(weekly_days)
    for i, days in enumerate(row):
        if days >= OBLIGATION_THRESHOLD:
            return SERVICE_YEARS[i]
    return None


def expiry_run(years: int, used_per_year: int, weekly_days: int = 5) -> list[dict]:
    """毎年 `used_per_year` 日だけ使ったとき、時効で消える日数を年ごとに出す。

    繰越は1年ぶんだけなので、**前の年の残りは、その年に使い切らなければ消えます。**
    消化は古いほうから（`ASSUMPTIONS` に書いてあります）。
    """
    rows: list[dict] = []
    carry = 0          # 前の年に付与されて、まだ残っている日数
    lost_total = 0
    for i in range(years):
        grant = granted_at(i, weekly_days)
        used_from_carry = min(carry, used_per_year)
        used_from_grant = min(grant, used_per_year - used_from_carry)
        lost = carry - used_from_carry          # 使い残した繰越は、ここで時効
        lost_total += lost
        rows.append({
            "勤続年": SERVICE_YEARS[min(i, len(SERVICE_YEARS) - 1)] if i < len(
                SERVICE_YEARS) else i + 0.5,
            "その年の付与": grant,
            "使った日数": used_from_carry + used_from_grant,
            "時効で消えた日数": lost,
            "消えた日数の累計": lost_total,
        })
        carry = grant - used_from_grant
    return rows


def grid(weekly_days: int = 5) -> list[dict]:
    """勤続ごとの付与日数と、そこまでの累計。**図解がそのまま食える形。**"""
    out: list[dict] = []
    for i, years in enumerate(SERVICE_YEARS):
        out.append({
            "勤続年数": years,
            "付与日数": granted_at(i, weekly_days),
            "累計": cumulative(i + 1, weekly_days),
        })
    return out


def skip_one_year(years: int, skipped_nth: int, weekly_days: int = 5) -> dict:
    """出勤率8割を1年だけ切ったとき、生涯の累計が何日減るか。

    **勤続年数の時計は止まりません。**切った年の付与がゼロになるだけで、
    翌年は「切らなかった場合と同じ段」に戻ります。
    """
    full = cumulative(years, weekly_days)
    lost = granted_at(skipped_nth, weekly_days)
    return {
        "切らなかった場合の累計": full,
        "切った回": skipped_nth + 1,
        "その年に失った日数": lost,
        "切った場合の累計": full - lost,
    }


def daily_wage(monthly_wage: int, weekly_days: int = 5) -> float:
    """有給1日ぶんの賃金。**月給 ÷ 1か月平均所定労働日数。**

    1か月平均所定労働日数 ＝ 週の所定労働日数 × 52 ÷ 12。
    **週の日数が少ないほど、同じ月給なら1日の単価は高くなります。**
    """
    return monthly_wage / (weekly_days * WEEKS_PER_YEAR / 12)


def expiry_money(monthly_wage: int, years: int, used_per_year: int,
                 weekly_days: int = 5) -> dict:
    """**時効で消えた日数を、円で出す。**

    日数のままだと「241日」で終わりますが、賃金に直すと
    **その人が働いて得た権利を、いくら捨てているか**が出ます。
    どこにも公開されていない数字なので、前提（`ASSUMPTIONS`）ごと画面に出すこと。
    """
    run = expiry_run(years, used_per_year, weekly_days)
    lost_days = run[-1]["消えた日数の累計"] if run else 0
    per_day = daily_wage(monthly_wage, weekly_days)
    return {
        "月給": monthly_wage,
        "週の所定労働日数": weekly_days,
        "1か月平均所定労働日数": weekly_days * WEEKS_PER_YEAR / 12,
        "有給1日の賃金": per_day,
        "勤続年数": years,
        "年の消化日数": used_per_year,
        "時効で消えた日数": lost_days,
        "捨てた金額": per_day * lost_days,
        "1年あたり": per_day * lost_days / years if years else 0.0,
    }


def used_sensitivity(years: int, weekly_days: int = 5) -> list[dict]:
    """**年の消化日数を0日から1日ずつ増やして、消える日数の累計を出す。**

    「もう1日使う」の効きは一定ではありません。**付与日数に届いた時点で
    0になり、そこから先は1日増やしても1日も助かりません**（頭打ち）。
    その境目がどこかは、勤続年数と週の日数で動きます。
    """
    top = table_for(weekly_days)[-1]
    out: list[dict] = []
    prev: int | None = None
    for used in range(0, top + 1):
        run = expiry_run(years, used, weekly_days)
        lost = run[-1]["消えた日数の累計"] if run else 0
        out.append({
            "年の消化日数": used,
            "時効で消えた日数の累計": lost,
            "1日増やして助かった日数": None if prev is None else prev - lost,
        })
        prev = lost
    return out


def zero_loss_at(years: int, weekly_days: int = 5) -> int | None:
    """**1日も時効で消えなくなる、年の消化日数**（最小）。届かないなら None。"""
    for row in used_sensitivity(years, weekly_days):
        if row["時効で消えた日数の累計"] == 0:
            return int(row["年の消化日数"])
    return None


def is_prorated(weekly_days: int, weekly_hours: float) -> bool:
    """比例付与の対象か。**週4日以下「かつ」週30時間未満のときだけ。**

    労働基準法39条3項・同施行規則24条の3。**ANDなので、週4日でも30時間以上なら
    通常の労働者と同じ日数がつきます。** 一般の解説はここを「週4日なら15日が上限」と
    書いて止まりますが、**上限を決めているのは日数ではなく、日数と時間の組**です。
    """
    return (weekly_days <= PRORATED_MAX_WEEKLY_DAYS
            and weekly_hours < FULLTIME_WEEKLY_HOURS)


def granted_by_hours(nth: int, weekly_days: int, weekly_hours: float) -> int:
    """`nth` 回目（0起点）の付与日数を、**週の日数と時間の組**から出す。"""
    if not is_prorated(weekly_days, weekly_hours):
        return FULL_TIME[min(nth, len(FULL_TIME) - 1)]
    return granted_at(nth, weekly_days)


def cumulative_by_hours(years: int, weekly_days: int, weekly_hours: float) -> int:
    """勤続 `years` 年までに付与される日数の累計（週の日数と時間の組で決まる）。"""
    return sum(granted_by_hours(i, weekly_days, weekly_hours) for i in range(years))


def escape_reachable(weekly_days: int) -> bool:
    """**1日8時間の上限のなかで、週30時間に届くか。**

    労働基準法32条2項が1日8時間で頭を押さえているので、
    **週3日以下では、何時間まで働いても30時間に届きません**（週3日でも24時間）。
    変形労働時間制を使えば1日8時間を超えられますが、この計算には入れていません
    （`ASSUMPTIONS` に書いてあります）。
    """
    return weekly_days * LEGAL_DAILY_HOURS >= FULLTIME_WEEKLY_HOURS


def hours_cliff(weekly_days: int, years: int, monthly_wage: int,
                lo_minutes: int = 6 * 60, hi_minutes: int = 8 * 60,
                step_minutes: int = 15) -> list[dict]:
    """**1日の所定労働時間を刻んで、生涯の付与日数がどこで飛ぶかを出す。**

    刻みは分（既定15分）。**境目は週30時間ちょうど**なので、週4日なら
    1日7時間30分。刻みを分まで細かくしても、飛ぶ点は1つしか出ません
    （`check_tables` が、刻みを半分にしても答えが変わらないことを見ています）。
    """
    per_day = daily_wage(monthly_wage, weekly_days)
    rows: list[dict] = []
    prev: int | None = None
    for m in range(lo_minutes, hi_minutes + 1, step_minutes):
        weekly_hours = weekly_days * m / 60
        total = cumulative_by_hours(years, weekly_days, weekly_hours)
        rows.append({
            "1日の所定労働時間（分）": m,
            "週の所定労働時間": weekly_hours,
            "比例付与か": is_prorated(weekly_days, weekly_hours),
            "生涯の付与日数": total,
            "1段前との差": None if prev is None else total - prev,
            "1段前との差（円）": None if prev is None else (total - prev) * per_day,
        })
        prev = total
    return rows


def shorter_but_more(years: int, monthly_wage: int) -> list[dict]:
    """**週の総時間が短いほうが、有給が多くなる組を出す。**

    週5日は時間を見ずに通常の労働者なので（39条1項）、
    **週5日5時間（週25時間）は20日つき、週4日7時間（週28時間）は15日で止まります。**
    働く時間は3時間長いのに、生涯の付与は少ない。
    """
    out: list[dict] = []
    for weekly_days, daily_hours in ((5, 5.0), (5, 6.0), (4, 7.0), (4, 7.5), (4, 8.0),
                                     (3, 8.0), (2, 8.0)):
        weekly_hours = weekly_days * daily_hours
        total = cumulative_by_hours(years, weekly_days, weekly_hours)
        out.append({
            "週の所定労働日数": weekly_days,
            "1日の所定労働時間": daily_hours,
            "週の所定労働時間": weekly_hours,
            "比例付与か": is_prorated(weekly_days, weekly_hours),
            "上限の付与日数": granted_by_hours(6, weekly_days, weekly_hours),
            "生涯の付与日数": total,
            "有給1日の賃金": daily_wage(monthly_wage, weekly_days),
            "生涯の付与を円で": total * daily_wage(monthly_wage, weekly_days),
        })
    return out


def same_hours_split(weekly_hours: float, years: int, monthly_wage: int) -> list[dict]:
    """**週の総労働時間と月給を固定して、それを何日に割るかだけを変える。**

    同じ時間を働き、同じ月給をもらっていても、**有給の生涯価値は日数の割り方で
    変わります。** 2つの力が逆を向いているからです。

        日数を減らす  → 1日の賃金は上がる（月給 ÷ 週の日数 × 52 ÷ 12）
        日数を減らす  → 週4日以下かつ週30時間未満だと比例付与に落ちて、日数が減る

    **1日8時間の上限（32条2項）があるので、割り方は自由ではありません** ——
    週30時間を週3日に割ると1日10時間になり、この計算の外に出ます。
    そこは行ごと落としてあります（成り立たない組を並べない）。
    """
    rows: list[dict] = []
    for weekly_days in (5, 4, 3, 2, 1):
        daily_hours = weekly_hours / weekly_days
        if daily_hours > LEGAL_DAILY_HOURS:
            continue
        total = cumulative_by_hours(years, weekly_days, weekly_hours)
        per_day = daily_wage(monthly_wage, weekly_days)
        rows.append({
            "週の所定労働時間": weekly_hours,
            "週の所定労働日数": weekly_days,
            "1日の所定労働時間": daily_hours,
            "比例付与か": is_prorated(weekly_days, weekly_hours),
            "生涯の付与日数": total,
            "有給1日の賃金": per_day,
            "生涯の付与を円で": total * per_day,
        })
    return rows


def best_split(weekly_hours: float, years: int, monthly_wage: int) -> dict | None:
    """その週の総時間で、**有給の生涯価値がいちばん高くなる割り方**。無ければ None。

    同額が並んだときは**日数の多いほう**を返します（週5日が既定の働き方なので、
    「入れ替わった」と言えるのは週5日を**上回った**ときだけ）。
    """
    rows = same_hours_split(weekly_hours, years, monthly_wage)
    if not rows:
        return None
    return max(rows, key=lambda r: (r["生涯の付与を円で"], r["週の所定労働日数"]))


def split_window(years: int, monthly_wage: int,
                 lo_minutes: int = 10 * 60, hi_minutes: int = 40 * 60,
                 step_minutes: int = 30) -> list[dict]:
    """**週の総時間を刻んで、勝つ割り方がどこで入れ替わるかを出す。**

    刻みは週あたりの分。返す各行は、その総時間での勝ち（`best_split`）と、
    **既定の週5日との差**です。差が正の行が「週5日より得な帯」になります。
    """
    rows: list[dict] = []
    for m in range(lo_minutes, hi_minutes + 1, step_minutes):
        weekly_hours = m / 60
        best = best_split(weekly_hours, years, monthly_wage)
        if best is None:
            continue
        five = [r for r in same_hours_split(weekly_hours, years, monthly_wage)
                if r["週の所定労働日数"] == 5]
        base = five[0]["生涯の付与を円で"] if five else 0.0
        rows.append({
            "週の所定労働時間": weekly_hours,
            "勝つ週の所定労働日数": best["週の所定労働日数"],
            "その1日の所定労働時間": best["1日の所定労働時間"],
            "勝ちの生涯の付与を円で": best["生涯の付与を円で"],
            "週5日にしたときの生涯の付与を円で": base,
            "週5日との差": best["生涯の付与を円で"] - base,
        })
    return rows


def split_window_edges(years: int, monthly_wage: int,
                       step_minutes: int = 30) -> tuple[float, float] | None:
    """**週5日より得になる帯の、左端と右端**（週の総時間）。無ければ None。

    実測ではここが**とても狭い**ので、「週4日にすれば得」とは言い切れません。
    帯の外では、同じ総時間・同じ月給でも**週5日のほうが上**です。
    """
    win = [r for r in split_window(years, monthly_wage, step_minutes=step_minutes)
           if r["週5日との差"] > 0]
    if not win:
        return None
    return (win[0]["週の所定労働時間"], win[-1]["週の所定労働時間"])


def quit_day_value(monthly_wage: int, weekly_days: int = 5,
                   grants: int = 21) -> list[dict]:
    """**付与日の前日に辞めるか、その日まで在籍するか。1日の差で何日・何円変わるか。**

    有給は勤続6か月のときに1回目、以後1年ごとに**その日に一括で**発生します
    （労働基準法39条1項・2項）。**日割りではありません。**
    だから退職日が付与日の前日か当日かで、**その回の付与がまるごと在るか無いかに
    分かれます。** どこにも公開されていない数字なので、前提ごと画面に出すこと。
    """
    per_day = daily_wage(monthly_wage, weekly_days)
    rows: list[dict] = []
    for i in range(grants):
        days = granted_at(i, weekly_days)
        rows.append({
            "付与の回": i + 1,
            "勤続年数": 0.5 + i,
            "前日に辞めた場合の累計": cumulative(i, weekly_days),
            "その日の付与": days,
            "在籍した場合の累計": cumulative(i + 1, weekly_days),
            "1日の差（日）": days,
            "1日の差（円）": per_day * days,
        })
    return rows


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(FULL_TIME[0], 10, "勤続6か月の付与日数",
                      source="労働基準法39条1項")
    _checks.statutory(FULL_TIME[-1], 20, "勤続6年6か月以上の付与日数",
                      source="労働基準法39条2項")
    _checks.statutory(OBLIGATION_DAYS, 5, "時季指定義務の日数",
                      source="労働基準法39条7項")
    _checks.statutory(OBLIGATION_THRESHOLD, 10, "時季指定義務がかかる付与日数",
                      source="労働基準法39条7項")
    _checks.statutory(PRORATED[4][0], 7, "週4日・勤続6か月の付与日数",
                      source="労働基準法施行規則24条の3")
    _checks.statutory(PRORATED[1][-1], 3, "週1日・勤続6年6か月の付与日数",
                      source="労働基準法施行規則24条の3")

    # 2. 表の形。**段の数が揃っていないと、勤続の刻みと対応が取れない**
    if len(SERVICE_YEARS) != len(FULL_TIME):
        raise _checks.TableError("勤続の刻みと通常の労働者の日数の段数が違う")
    for wd, row in PRORATED.items():
        if len(row) != len(SERVICE_YEARS):
            raise _checks.TableError(f"週{wd}日の段数が {len(row)}。刻みは {len(SERVICE_YEARS)} 段")
        _checks.ascending(row, f"週{wd}日の付与日数")
        _checks.greater(FULL_TIME[0], row[0], "通常の労働者の初回が比例付与の初回")
        _checks.greater(FULL_TIME[-1], row[-1], "通常の労働者の上限が比例付与の上限")
    _checks.ascending(FULL_TIME, "通常の労働者の付与日数")

    # 3. 週の日数が多いほど、同じ勤続でも日数が多いこと（表の列ずれを弾く）
    for i in range(len(SERVICE_YEARS)):
        _checks.increases_with(lambda wd: granted_at(i, wd), (1, 2, 3, 4, 5),
                               f"{SERVICE_YEARS[i]}年で、週の日数が増えたのに付与日数が増えていない")

    # 4. 計算の向き —— この計算の主題そのもの
    #    (a) 勤続が延びれば累計は増える
    _checks.increases_with(lambda y: cumulative(y), (1, 5, 10, 20), "勤続が延びたのに累計が増えていない")
    #    (b) **主題**: 付与より少なく使うと、差がそのまま毎年消える（定常状態）
    run = expiry_run(12, 5)
    steady = run[-1]
    _checks.rounding(steady["時効で消えた日数"], 20 - 5,
                     "勤続12年目に時効で消える日数（付与20日・消化5日）")
    #    (c) 使い切れば1日も消えない
    if any(r["時効で消えた日数"] for r in expiry_run(12, 20)):
        raise _checks.TableError("20日つく人が20日使っているのに、消えている日がある")
    #    (d) **主題**: 時季指定義務の境目が週の日数で動くこと。週2日以下は永久にかからない
    if obligation_starts(4) != 3.5:
        raise _checks.TableError(f"週4日で義務がかかるのは3年6か月のはず: {obligation_starts(4)}")
    if obligation_starts(3) != 5.5:
        raise _checks.TableError(f"週3日で義務がかかるのは5年6か月のはず: {obligation_starts(3)}")
    for wd in (1, 2):
        if obligation_starts(wd) is not None:
            raise _checks.TableError(f"週{wd}日は10日に届かないはず")
    #    (e) 1年切っても、時計は止まらない（翌年の付与が前年と同じ段に戻らない）
    s = skip_one_year(20, 3)
    _checks.greater(s["切らなかった場合の累計"], s["切った場合の累計"], "切らなかった累計が切った累計")
    #    (f) **主題**: 消化を増やすほど、消える日数は減る（増えることはない）
    seq = [r["時効で消えた日数の累計"] for r in used_sensitivity(20, 5)]
    for a, b in zip(seq, seq[1:]):
        if b > a:
            raise _checks.TableError("消化を1日増やしたのに、消える日数が増えた")
    #    (g) **主題**: 「1日も捨てない線」は上限とは限らない。
    #        繰越は1年ぶんしか無く、残りは1年に1日ずつしか積み上がらないので、
    #        **勤続が浅いうちは、上限より少ない消化でも1日も捨てません。**
    #        線は勤続とともに上がり、上限で止まる（超えない）。
    for wd in (1, 2, 3, 4, 5):
        cap = table_for(wd)[-1]
        seq = [zero_loss_at(y, wd) for y in (5, 10, 20, 30, 40)]
        if any(v is None for v in seq):
            raise _checks.TableError(f"週{wd}日で、上限まで使っても捨てる年がある")
        for a, b in zip(seq, seq[1:]):
            if b < a:
                raise _checks.TableError(f"週{wd}日の線が、勤続が延びたのに下がった")
        if seq[-1] != cap:
            raise _checks.TableError(f"週{wd}日の線が上限{cap}日に収束しない: {seq[-1]}")
        if max(seq) > cap:
            raise _checks.TableError(f"週{wd}日の線が上限{cap}日を超えた")
    #        通常の労働者は、**勤続20年でもまだ上限に届かない**（19日）
    if zero_loss_at(20, 5) >= FULL_TIME[-1]:
        raise _checks.TableError(
            f"勤続20年の線が上限に届いている: {zero_loss_at(20, 5)}")
    #    (h) 金額の向き —— 週の日数が少ないほど、同じ月給なら1日の単価は高い
    _checks.greater(daily_wage(300_000, 3), daily_wage(300_000, 5),
                    "週3日の日給が週5日の日給")
    m = expiry_money(300_000, 20, 5)
    _checks.rounding(m["捨てた金額"], m["有給1日の賃金"] * m["時効で消えた日数"],
                     "捨てた金額 ＝ 日給 × 消えた日数")
    if expiry_money(300_000, 20, FULL_TIME[-1])["捨てた金額"] != 0:
        raise _checks.TableError("20日つく人が20日使っているのに、捨てた金額が出ている")

    # 5. 比例付与の要件は、日数と時間の **AND**（2026-08-24 に足した節の主題）
    _checks.statutory(FULLTIME_WEEKLY_HOURS, 30, "比例付与の対象外になる週の所定労働時間",
                      source="労働基準法39条3項・同施行規則24条の3")
    _checks.statutory(PRORATED_MAX_WEEKLY_DAYS, 4, "比例付与の対象になる週の所定労働日数の上限",
                      source="労働基準法施行規則24条の3")
    _checks.statutory(LEGAL_DAILY_HOURS, 8, "1日の法定労働時間",
                      source="労働基準法32条2項")
    #    (i) 境目そのもの。**30時間ちょうどは「未満」ではないので、通常の労働者側**
    if not is_prorated(4, FULLTIME_WEEKLY_HOURS - 0.1):
        raise _checks.TableError("週4日29.9時間が比例付与から外れている")
    if is_prorated(4, FULLTIME_WEEKLY_HOURS):
        raise _checks.TableError("週4日30時間ちょうどが比例付与に入っている（未満のはず）")
    if is_prorated(5, 10):
        raise _checks.TableError("週5日が比例付与に入っている（39条1項の通常の労働者）")
    if granted_by_hours(6, 4, 30) != FULL_TIME[-1]:
        raise _checks.TableError("週4日30時間の上限が20日になっていない")
    if granted_by_hours(6, 4, 29) != PRORATED[4][-1]:
        raise _checks.TableError("週4日29時間の上限が15日になっていない")
    #    (j) **主題**: 1日8時間の上限のなかで30時間に届くのは週4日だけ
    if not escape_reachable(4):
        raise _checks.TableError("週4日で30時間に届かない（4×8=32時間のはず）")
    for wd in (1, 2, 3):
        if escape_reachable(wd):
            raise _checks.TableError(
                f"週{wd}日が1日8時間の上限のなかで30時間に届いている（{wd * 8}時間のはず）")
    #    (k) **主題**: 週4日30時間の生涯付与は、週5日と同じ段になる
    if cumulative_by_hours(20, 4, 30) != cumulative(20, 5):
        raise _checks.TableError("週4日30時間の生涯付与が、通常の労働者と揃っていない")
    if cumulative_by_hours(20, 4, 29) != cumulative(20, 4):
        raise _checks.TableError("週4日29時間の生涯付与が、比例付与の表と揃っていない")
    #    (l) **主題**: 週の総時間が短いほうが多くつく組がある（週5日25時間 対 週4日28時間）
    short_more = cumulative_by_hours(20, 5, 25.0)
    long_less = cumulative_by_hours(20, 4, 28.0)
    _checks.greater(short_more, long_less,
                    "週25時間（5日）の生涯付与が、週28時間（4日）の生涯付与")
    #    (m) 崖は1つだけ。**刻みを半分にしても答えが変わらないこと**（_template の「刻み」の節）
    for step in (15, 1):
        jumps = [r for r in hours_cliff(4, 20, 300_000, step_minutes=step)
                 if r["1段前との差"]]
        if len(jumps) != 1:
            raise _checks.TableError(
                f"刻み{step}分で、生涯付与が飛ぶ点が {len(jumps)}か所（1か所のはず）")
        if jumps[0]["週の所定労働時間"] < FULLTIME_WEEKLY_HOURS:
            raise _checks.TableError("飛ぶ点が週30時間より手前にある")
        if jumps[0]["1段前との差"] <= 0:
            raise _checks.TableError("時間が増えたのに生涯付与が減っている")
    #    (n) 退職日の1日 —— 差はその回の付与そのもので、円は日給×日数
    q = quit_day_value(300_000, 5)
    for i, row in enumerate(q):
        if row["1日の差（日）"] != granted_at(i, 5):
            raise _checks.TableError(f"{i + 1}回目の1日の差が、その回の付与と違う")
        if row["在籍した場合の累計"] - row["前日に辞めた場合の累計"] != row["1日の差（日）"]:
            raise _checks.TableError(f"{i + 1}回目の累計の差が、1日の差と合わない")
        _checks.rounding(row["1日の差（円）"], daily_wage(300_000, 5) * row["1日の差（日）"],
                         f"{i + 1}回目の1日の差（円）")
    if max(r["1日の差（日）"] for r in q) != FULL_TIME[-1]:
        raise _checks.TableError("退職日1日の差の最大が、付与の上限20日になっていない")
    if q[0]["1日の差（日）"] != FULL_TIME[0]:
        raise _checks.TableError("1回目（勤続6か月）の1日の差が10日になっていない")
    #    (o) **主題**: 週の総時間を固定して日数だけ替えると、勝つ割り方が入れ替わる帯がある
    for hours in (10.0, 20.0, 24.0, 28.0, 30.0, 32.0, 35.0, 40.0):
        rows = same_hours_split(hours, 20, 300_000)
        if not rows:
            continue
        for row in rows:
            if row["1日の所定労働時間"] > LEGAL_DAILY_HOURS:
                raise _checks.TableError(
                    f"週{hours}時間の割り方に、1日{LEGAL_DAILY_HOURS}時間を超える行がある")
            _checks.rounding(row["生涯の付与を円で"],
                             row["生涯の付与日数"] * row["有給1日の賃金"],
                             f"週{hours}時間・週{row['週の所定労働日数']}日の生涯の付与を円で")
        if not any(r["週の所定労働日数"] == 5 for r in rows):
            raise _checks.TableError(f"週{hours}時間の割り方に、週5日の行が無い")
    #        帯の端は週30時間と週32時間ちょうど。**刻みを30分から1分にしても動かないこと**
    edges = {step: split_window_edges(20, 300_000, step_minutes=step)
             for step in (30, 15, 1)}
    if len(set(edges.values())) != 1:
        raise _checks.TableError(f"帯の端が刻みで動いている: {edges}")
    edge = edges[1]
    if edge is None:
        raise _checks.TableError("週5日より得になる帯が1つも出ていない")
    if edge[0] != float(FULLTIME_WEEKLY_HOURS):
        raise _checks.TableError(
            f"帯の左端が週{FULLTIME_WEEKLY_HOURS}時間になっていない（{edge[0]}）")
    if edge[1] != float(PRORATED_MAX_WEEKLY_DAYS * LEGAL_DAILY_HOURS):
        raise _checks.TableError(f"帯の右端が週4日×1日8時間になっていない（{edge[1]}）")
    #        帯の中は週4日が勝ち、帯の外は週5日と同額（下回ることはない）
    for row in split_window(20, 300_000, step_minutes=30):
        inside = edge[0] <= row["週の所定労働時間"] <= edge[1]
        if inside:
            if row["勝つ週の所定労働日数"] != PRORATED_MAX_WEEKLY_DAYS:
                raise _checks.TableError(
                    f"帯の中（週{row['週の所定労働時間']}時間）で週4日が勝っていない")
            _checks.greater(row["勝ちの生涯の付与を円で"],
                            row["週5日にしたときの生涯の付与を円で"],
                            f"週{row['週の所定労働時間']}時間の勝ちが、週5日")
        else:
            if row["週5日との差"] != 0:
                raise _checks.TableError(
                    f"帯の外（週{row['週の所定労働時間']}時間）で週5日と差が付いている")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 年5日しか使わないと、毎年何日が時効で消えるか ===")
    for row in expiry_run(12, 5):
        print(f"  {row['勤続年']:>4}年  付与{row['その年の付与']:>3}日"
              f"  使用{row['使った日数']:>3}日"
              f"  消えた{row['時効で消えた日数']:>3}日"
              f"  累計{row['消えた日数の累計']:>4}日")

    print("\n=== 年5日の時季指定義務は、週の日数で「かかる年」が違う ===")
    print(f"  かかる条件は「その年の付与が{OBLIGATION_THRESHOLD}日以上」"
          f"（1年で{OBLIGATION_DAYS}日）")
    for wd in (5, 4, 3, 2, 1):
        starts = obligation_starts(wd)
        row = table_for(wd)
        top = row[-1]
        if starts is None:
            print(f"  週{wd}日  一生かからない  生涯の上限{top}日"
                  f"  {OBLIGATION_THRESHOLD}日まであと{OBLIGATION_THRESHOLD - top}日")
        else:
            nth = SERVICE_YEARS.index(starts)
            print(f"  週{wd}日  勤続{starts}年から  そのときの付与{row[nth]}日"
                  f"  そこまでの累計{cumulative(nth + 1, wd)}日")

    print("\n=== 勤続20年までに付与される日数の累計（週の日数べつ） ===")
    base = cumulative(20, 5)
    for wd in (5, 4, 3, 2, 1):
        c = cumulative(20, wd)
        print(f"  週{wd}日  累計{c:>4}日  通常との差 {base - c:>3}日"
              f"（{c / base * 100:4.1f}%）")

    print("\n=== 勤続ごとの付与日数と、そこまでの累計（通常の労働者） ===")
    for row in grid(5):
        print(f"  勤続{row['勤続年数']:>4}年  付与{row['付与日数']:>3}日  累計{row['累計']:>3}日")

    print("\n=== 捨てている有給を、円で出す（月給30万・週5日） ===")
    m0 = expiry_money(300_000, 20, 5)
    print(f"  1か月平均所定労働日数 {m0['1か月平均所定労働日数']:.1f}日"
          f"  → 有給1日 {m0['有給1日の賃金']:,.0f}円")
    for used in (0, 3, 5, 10, 15):
        m = expiry_money(300_000, 20, used)
        print(f"  年{used:>2}日しか使わない  20年で{m['時効で消えた日数']:>3}日が時効"
              f"  → **{m['捨てた金額']:>10,.0f}円**"
              f"（1年あたり {m['1年あたり']:>8,.0f}円）")
    print("  週の日数べつ（年5日消化・月給30万・勤続20年）:")
    for wd in (5, 4, 3, 2, 1):
        m = expiry_money(300_000, 20, 5, wd)
        print(f"    週{wd}日  日給{m['有給1日の賃金']:>7,.0f}円"
              f"  消えた{m['時効で消えた日数']:>3}日  **{m['捨てた金額']:>10,.0f}円**")

    print("\n=== 「1日も捨てない線」は付与の上限ではない。勤続で動く ===")
    print(f"  通常の労働者の付与の上限は {FULL_TIME[-1]}日。"
          "**だが年20日使わなくても、捨てない年がある** ——")
    print("  繰越は1年ぶんしか無く、使い残しは1年に1日ずつしか積み上がらないため。")
    print("  勤続  週5日  週4日  週3日  週2日  週1日   （1日も捨てない、年の消化日数）")
    for y in (5, 10, 12, 20, 25, 30, 40):
        cells = "".join(f"{zero_loss_at(y, wd):>6}" for wd in (5, 4, 3, 2, 1))
        print(f"  {y:>3}年{cells}")
    caps = "".join(f"{table_for(wd)[-1]:>6}" for wd in (5, 4, 3, 2, 1))
    print(f"  付与上限{caps}   ← **週5日だけ、勤続30年まで上限に届かない**")
    print(f"  週5日・勤続20年で見ると、線は 年{zero_loss_at(20, 5)}日。"
          "そこから1日増やしても、助かる日数は0日です:")
    for row in used_sensitivity(20, 5):
        saved = row["1日増やして助かった日数"]
        mark = "" if saved is None else f"  1日増やして助かった {saved:>2}日"
        print(f"    年{row['年の消化日数']:>2}日消化  消える累計"
              f"{row['時効で消えた日数の累計']:>3}日{mark}")

    print("\n=== 出勤率8割を1年だけ切ると、生涯の累計は何日減るか ===")
    for nth in (0, 3, 6, 10):
        s = skip_one_year(20, nth)
        print(f"  {s['切った回']:>2}回目に切る  失う{s['その年に失った日数']:>3}日"
              f"  累計 {s['切らなかった場合の累計']}日 → {s['切った場合の累計']}日")

    print("\n=== 退職日を1日ずらすと、有給は何日ふえるか（月給30万・週5日） ===")
    q = quit_day_value(300_000, 5)
    print(f"  有給は付与日に**一括で**発生します（39条1項・2項）。日割りではありません。")
    print(f"  だから「付与日の前日に辞める」と「その日まで在籍する」で、"
          f"その回の付与がまるごと在るか無いかに分かれます。")
    print("  付与の回  勤続      前日で辞める   在籍する   1日の差")
    for row in q:
        print(f"  {row['付与の回']:>6}回  {row['勤続年数']:>4}年"
              f"  累計{row['前日に辞めた場合の累計']:>4}日"
              f"  → 累計{row['在籍した場合の累計']:>4}日"
              f"  **+{row['1日の差（日）']:>2}日 = {row['1日の差（円）']:>10,.0f}円**")
    biggest = max(q, key=lambda r: r["1日の差（円）"])
    print(f"  いちばん大きいのは {biggest['勤続年数']}年（{biggest['付与の回']}回目）の"
          f"**{biggest['1日の差（円）']:,.0f}円**。"
          f"1回目（勤続6か月）でも {q[0]['1日の差（円）']:,.0f}円です。")

    print("\n=== 比例付与から抜けられるのは週4日だけ。1日の所定労働時間30分の崖 ===")
    print(f"  比例付与の要件は **週{PRORATED_MAX_WEEKLY_DAYS}日以下「かつ」"
          f"週{FULLTIME_WEEKLY_HOURS}時間未満**（39条3項・施行規則24条の3）。**ANDです。**")
    print(f"  1日の上限は{LEGAL_DAILY_HOURS}時間（32条2項）なので、"
          f"週{FULLTIME_WEEKLY_HOURS}時間に届く週の日数は:")
    for wd in (4, 3, 2, 1):
        cap_h = wd * LEGAL_DAILY_HOURS
        mark = "**届く**" if escape_reachable(wd) else "届かない"
        print(f"    週{wd}日  1日8時間でも週{cap_h}時間  → {mark}")
    print(f"  週4日・勤続20年・月給30万で、1日の所定労働時間を刻むと:")
    for row in hours_cliff(4, 20, 300_000):
        h, m = divmod(row["1日の所定労働時間（分）"], 60)
        d = row["1段前との差"]
        jump = "" if not d else f"  ← **ここで +{d}日 = {row['1段前との差（円）']:,.0f}円**"
        kind = "比例付与" if row["比例付与か"] else "通常の労働者"
        print(f"    1日{h}時間{m:02d}分  週{row['週の所定労働時間']:>4.1f}時間"
              f"  {kind}  生涯{row['生涯の付与日数']:>3}日{jump}")
    print("  **働く時間が短いほうが、有給が多くなる組があります**"
          "（週5日は時間を見ずに通常の労働者だから）:")
    for row in shorter_but_more(20, 300_000):
        kind = "比例付与" if row["比例付与か"] else "通常"
        print(f"    週{row['週の所定労働日数']}日 × 1日{row['1日の所定労働時間']:>3.1f}時間"
              f"  = 週{row['週の所定労働時間']:>4.1f}時間  {kind:<4}"
              f"  上限{row['上限の付与日数']:>2}日  生涯{row['生涯の付与日数']:>3}日"
              f"  = {row['生涯の付与を円で']:>11,.0f}円")
    a = cumulative_by_hours(20, 5, 25.0)
    b = cumulative_by_hours(20, 4, 28.0)
    print(f"  週25時間（5日×5時間）は生涯{a}日、週28時間（4日×7時間）は生涯{b}日。"
          f"**3時間よけいに働いて、{a - b}日少ない。**")

    edge = split_window_edges(20, 300_000, step_minutes=1)
    lo, hi = edge  # type: ignore[misc]
    win = [r for r in split_window(20, 300_000, step_minutes=30)
           if r["週5日との差"] > 0]
    gap = win[0]["週5日との差"]
    ratio = win[0]["勝ちの生涯の付与を円で"] / win[0]["週5日にしたときの生涯の付与を円で"]
    print(f"\n=== 同じ週の総時間・同じ月給でも、何日に割るかで有給の生涯価値が変わる。"
          f"得な帯は週{lo:.0f}〜{hi:.0f}時間の{hi - lo:.0f}時間だけ ===")
    print(f"  月給30万・勤続20年で固定し、**週の総労働時間だけを刻んで**、"
          f"それを何日に割るのがいちばん得かを出しました（1日{LEGAL_DAILY_HOURS}時間の上限つき）。")
    print("    週の総時間  勝つ割り方           勝ちの生涯価値      週5日にしたとき      差")
    for row in split_window(20, 300_000, step_minutes=60):
        mark = "  ← **入れ替わる**" if row["週5日との差"] > 0 else ""
        print(f"    週{row['週の所定労働時間']:>4.1f}時間"
              f"  週{row['勝つ週の所定労働日数']}日×1日{row['その1日の所定労働時間']:>4.2f}時間"
              f"  {row['勝ちの生涯の付与を円で']:>11,.0f}円"
              f"  {row['週5日にしたときの生涯の付与を円で']:>11,.0f}円"
              f"  {row['週5日との差']:>10,.0f}円{mark}")
    print(f"  **入れ替わるのは週{lo:.0f}時間から週{hi:.0f}時間までの{hi - lo:.0f}時間だけ**です。"
          f"そこでは週4日が週5日を **{gap:,.0f}円**（{ratio:.3f}倍）上回ります。")
    print(f"  左端が週{lo:.0f}時間なのは比例付与を抜ける線（39条3項）、"
          f"右端が週{hi:.0f}時間なのは1日{LEGAL_DAILY_HOURS}時間×4日の上限（32条2項）。"
          "**帯の幅は、この2つの条文の差そのものです。**")
    print(f"  週{hi:.0f}時間を超えると週4日は1日{LEGAL_DAILY_HOURS}時間に収まらないので、"
          "行ごと消えます。**帯の外では、週5日と同額か、週5日のほうが上**です。")
    for hours in (28.0, 30.0, 36.0):
        print(f"  週{hours:.0f}時間の内訳:")
        for row in same_hours_split(hours, 20, 300_000):
            kind = "比例付与" if row["比例付与か"] else "通常"
            print(f"    週{row['週の所定労働日数']}日 × 1日{row['1日の所定労働時間']:>4.2f}時間"
                  f"  {kind:<4}  生涯{row['生涯の付与日数']:>3}日"
                  f"  1日{row['有給1日の賃金']:>9,.0f}円"
                  f"  = {row['生涯の付与を円で']:>11,.0f}円")
    print("  **「週4日にすれば得」ではありません。** 得なのは、"
          f"週の総時間を週{lo:.0f}〜{hi:.0f}時間に置いたまま4日に詰めたときだけです。")
