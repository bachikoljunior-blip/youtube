"""労災の休業補償 —— **「8割」が8割になるのは、賞与が1円も無い人だけです。**

一般の解説はこう言います ——「労災で休むと、給付基礎日額の60パーセントの休業補償給付と、
20パーセントの休業特別支給金で、あわせて**8割**が出ます」。

率としては合っています。**そのうえで、実際に手元に入る額は 8割になりません。**
給付基礎日額は**賞与を除いた3か月の賃金を、暦日数で割ったもの**だからです
（月給30万円・直前3か月91日・1年休んだ場合）。

    賞与（年）   年収        1年の給付      年収に対する割合
      0か月    360万円   2,887,880円      80.22%
      2か月    420万円   2,887,880円      68.76%
      4か月    480万円   2,887,880円      **60.16%**   ← 「8割」が6割になります
      6か月    540万円   2,887,880円      53.48%

**分子は1円も動きません。** 賞与は給付基礎日額に入らないので、
賞与でいくら年収が増えても、労災の給付は1円も増えないためです。
割合はおよそ **9.6 ÷（12 ＋ 賞与の月数）**で決まり、**月給の額にはよりません**
（給付基礎日額 × 0.8 × 365日 ＝ 月給 × 3 ÷ 暦日数 × 0.8 × 365 で、月給が約分で消える）。

## 同じ月給でも、休み始めた月で日額が3.37パーセント変わります

給付基礎日額は「直前3か月の賃金 ÷ その3か月の**暦日数**」です。
3か月の暦日数は **89日から92日**まで動きます。

    休み始めた月   直前3か月    暦日   給付基礎日額   1年の給付
      5月         2・3・4月    89日   10,113円   2,952,485円   ← いちばん高い
      6月         3・4・5月    92日    9,783円   2,856,125円   ← いちばん低い

**隣り合う月で 96,360円の差**（月給30万円・平年）。
制度のどこにも「5月に休むと得」とは書いていません。**2月が28日しかないからです。**

**いちばん高い月は5月だけですが、いちばん低い月は7つあります**
（1・2・6・8・9・10・11月）。92日は「31・30・31」と「30・31・31」の
並びが何通りもあるためで、**低いほうを1つ名指しすると嘘になります。**

## 待期3日は、業務災害と通勤災害で額が違います

最初の3日は労災保険から出ません。**業務災害のときだけ、事業主が労働基準法76条により
平均賃金の60パーセントを補償します。通勤中のけがには、この義務がありません。**

    業務災害   3日 × 60%  ＝ 17,802円
    通勤災害   3日 × 0%   ＝ 0円

**同じけが・同じ日額でも、通勤中というだけで 17,802円 少なくなります。**

## 「労災は8割、健康保険は3分の2」の倍率は、1.2倍ではありません

0.8 ÷ (2/3) は 1.2倍です。**実際は 1.1737倍から 1.2133倍のあいだで動き、
1.2倍をまたぎます**（月給30万円・標準報酬月額も30万円）。

    直前3か月の暦日   労災 1日   傷病手当金 1日   倍率
      89日           8,089円      6,667円      1.2133   ← **1.2倍より得**
      90日           8,000円      6,667円      1.1999   ← 1.2倍に 0.0001 届かない
      91日           7,912円      6,667円      1.1867
      92日           7,825円      6,667円      1.1737   ← 1.2倍より損

傷病手当金は**標準報酬月額を30で割る**ので、月が何日あっても同じ額です。
労災だけが暦日で割るので、**同じ人・同じ月給で、休み始めた月によって
「1.2倍より得」にも「損」にもなります。** 1.2倍を上回るのは89日のときだけ、
つまり **5月に休み始めた人だけ**です。

## 半日働くと9割になりますが、働いて得た賃金の8割は消えます

一部だけ働いた日は、**（給付基礎日額 − その日の賃金）× 80パーセント**が出ます。

    その日の賃金        給付      手元の合計   日額に対する割合
      0円            7,912円     7,912円      80.0%
      4,945円（半日） 3,956円     8,901円      90.0%
      9,891円（全日）      0円     9,891円     100.0%

**賃金を1万円ふやしても、手元は2,000円しかふえません**（限界の手取り率20パーセント）。
半日で9割に届くのはそのためで、**残りの半日の値打ちは10パーセント**しかありません。

## 待期3日の差は、休みが長くなるほど消えます

    休んだ日数   業務災害   通勤災害    差
        30日     77.99%    71.99%   6.00ポイント
        90日     79.33%    77.33%   2.00ポイント
       180日     79.66%    78.66%   1.00ポイント
       365日     79.83%    79.33%   0.49ポイント

**業務災害か通勤災害かで変わる額は、3日ぶんで固定**（この例で 17,802円）なので、
日数で割ると薄まります。**割合の差を見て「通勤災害は不利」と言えるのは、
短く休むときだけ**です。長く休む人にとっての差は、率ではなく最初の1回きりの金額です。

（80.0パーセントではなく 79.99パーセント止まりなのは、
60パーセントぶんと20パーセントぶんを別々に1円未満切り捨てするためです。
9,891円の日額で 5,934円 ＋ 1,978円 ＝ 7,912円 になります。）
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値 -----------------------------------------------------------
# 休業補償給付（労災保険法14条1項）。給付基礎日額の100分の60。
KYUGYO_RATE = 0.60

# 休業特別支給金（労働者災害補償保険特別支給金支給規則3条）。給付基礎日額の100分の20。
TOKUBETSU_RATE = 0.20

# 待期期間（労災保険法14条1項）。休業の初日から3日間は支給されない。
# **健康保険の傷病手当金と違い、連続している必要はありません**（通算3日）。
WAITING_DAYS = 3

# 事業主の休業補償（労働基準法76条1項）。平均賃金の100分の60。
# **業務上の負傷・疾病だけ**で、通勤災害にはこの義務がありません。
ROUKI_HOSHO_RATE = 0.60

# 傷病手当金（健康保険法99条）。標準報酬月額の平均を30で割った額の3分の2。
SHOBYO_RATE = 2 / 3
SHOBYO_DIVISOR = 30

# 平均賃金（労働基準法12条1項）。直前3か月の賃金総額 ÷ その期間の総日数（暦日）。
# **賞与（3か月を超える期間ごとに支払われる賃金）は入りません**（同条4項）。
AVG_MONTHS = 3

# 3か月の暦日数が取りうる範囲。平年で 89日（2・3・4月）〜92日。
CAL_DAYS_MIN = 89
CAL_DAYS_MAX = 92

MONTH_DAYS = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # 平年

ASSUMPTIONS = [
    "労災保険の休業補償給付と休業特別支給金を計算しています。"
    "給付基礎日額の60パーセントが休業補償給付、20パーセントが休業特別支給金で、"
    "あわせて80パーセントです",
    "給付基礎日額は、労働基準法12条の平均賃金として計算しています。"
    "直前3か月に支払われた賃金の総額を、その3か月の暦の日数で割った額です。"
    "3か月の暦日数は、平年で89日から92日のあいだで動きます",
    "賞与は給付基礎日額に入れていません。3か月を超える期間ごとに支払われる賃金は、"
    "労働基準法12条4項で平均賃金の計算から外れるためです",
    "平均賃金は銭未満を切り捨て、給付基礎日額は1円未満を切り上げとして置いています。"
    "休業補償給付と休業特別支給金は、それぞれ1円未満を切り捨てています",
    "待期は3日間として計算しています。労災では連続していなくてもよく、通算で3日です。"
    "健康保険の傷病手当金は連続した3日が必要ですが、その差はここでは計算していません",
    "待期の3日について、業務災害では事業主が労働基準法76条により平均賃金の"
    "60パーセントを補償するものとして置いています。通勤災害では0円です",
    "傷病手当金は、標準報酬月額の平均を30で割った額（10円未満四捨五入）の"
    "3分の2として計算しています。標準報酬月額は月給と同じ額として置いていますが、"
    "実際は等級表の額に丸められます",
    "月給は毎月同じ額として置いています。欠勤や残業による変動は入れていません",
    "給付基礎日額の年齢階層別の最高限度額・最低限度額は入れていません。"
    "療養開始から1年6か月を過ぎた休業給付にだけ適用されるものです",
    "スライド制（平均給与額が10パーセントを超えて変動したときの改定）は入れていません",
    "休業補償給付も休業特別支給金も、所得税・住民税はかかりません。"
    "社会保険料は免除されないため、健康保険料と厚生年金保険料の負担は残りますが、"
    "この計算には入れていません",
]


# ---- 給付基礎日額 -------------------------------------------------------
def calendar_days(end_month: int) -> int:
    """`end_month` 月の末日で締めたときの、直前3か月の暦日数。**89〜92日。**"""
    return sum(MONTH_DAYS[(end_month - 1 - i) % 12] for i in range(AVG_MONTHS))


def average_wage(monthly: int, cal_days: int) -> float:
    """平均賃金（労基法12条）。**賞与を含めず、暦日で割ります。銭未満切り捨て。**"""
    return int(monthly * AVG_MONTHS * 100 / cal_days) / 100


def daily_base(monthly: int, cal_days: int = 91) -> int:
    """給付基礎日額。**1円未満は切り上げ。**"""
    avg = average_wage(monthly, cal_days)
    return int(-(-avg // 1))


def benefit(monthly: int, cal_days: int = 91) -> dict:
    """1日あたりの給付。**60パーセントと20パーセントは別々に切り捨てます。**"""
    d = daily_base(monthly, cal_days)
    kyugyo = int(d * KYUGYO_RATE)
    tokubetsu = int(d * TOKUBETSU_RATE)
    return {
        "給付基礎日額": d,
        "休業補償給付": kyugyo,
        "休業特別支給金": tokubetsu,
        "合計": kyugyo + tokubetsu,
        "日額に対する割合": (kyugyo + tokubetsu) / d,
    }


# ---- 節1: 「8割」は年収の8割ではない ------------------------------------
BONUS_MONTHS = [0, 1, 2, 3, 4, 5, 6]


def year_ratio(bonus_months: float) -> float:
    """1年ぶんの給付 ÷ 年収。**9.6 ÷（12 ＋ 賞与の月数）。**

    給付基礎日額 × 0.8 × 365 ＝ 月給 × 3 ÷ 暦日数 × 0.8 × 365 で、
    3か月の暦日数はおよそ 365 ÷ 4 なので、**暦日数も月給も約分で消えます。**
    """
    return (KYUGYO_RATE + TOKUBETSU_RATE) * 12 / (12 + bonus_months)


def bonus_grid(monthly: int = 300_000) -> list[dict]:
    """賞与の月数べつに、年収に対する割合を出す。**この表の主題です。**"""
    rows = []
    for b in BONUS_MONTHS:
        annual = monthly * (12 + b)
        got = int(benefit(monthly)["合計"] * 365)
        rows.append({
            "賞与の月数": b,
            "年収": annual,
            "1年の給付": got,
            "年収に対する割合": got / annual,
            "式の値": year_ratio(b),
        })
    return rows


# ---- 節2: 休み始めた月で日額が変わる ------------------------------------
def month_grid(monthly: int = 300_000) -> list[dict]:
    """休業を始めた月べつの給付基礎日額。**2月が28日しかないことが効きます。**"""
    rows = []
    for m in range(1, 13):
        end = m - 1 if m > 1 else 12   # 前月末で締める
        days = calendar_days(end)
        d = daily_base(monthly, days)
        b = benefit(monthly, days)
        rows.append({
            "休み始めた月": m,
            "暦日数": days,
            "給付基礎日額": d,
            "1日の給付": b["合計"],
            "1年の給付": b["合計"] * 365,
        })
    return rows


def month_spread(monthly: int = 300_000) -> dict:
    """いちばん高い月といちばん低い月の差。

    **高いほうは1つだけ、低いほうは複数あります。**
    最小の暦日数89日は「2・3・4月」の1通りしかありませんが、
    最大の92日は「31・30・31」と「30・31・31」の並びが何通りもあるためです。
    **どちらも1つ名指しすると嘘になります**ので、両方とも一覧で返します。
    """
    rows = month_grid(monthly)
    top = max(r["給付基礎日額"] for r in rows)
    bottom = min(r["給付基礎日額"] for r in rows)
    hi = [r for r in rows if r["給付基礎日額"] == top]
    lo = [r for r in rows if r["給付基礎日額"] == bottom]
    return {
        "高い月": [r["休み始めた月"] for r in hi], "高い暦日数": hi[0]["暦日数"],
        "高い日額": top, "高い1年": hi[0]["1年の給付"],
        "低い月": [r["休み始めた月"] for r in lo], "低い暦日数": lo[0]["暦日数"],
        "低い日額": bottom, "低い1年": lo[0]["1年の給付"],
        "日額の差": top - bottom,
        "1年の差": hi[0]["1年の給付"] - lo[0]["1年の給付"],
        "倍率": top / bottom,
        "高い月は1つか": len(hi) == 1,
        "隣り合う組": [(h["休み始めた月"], l["休み始めた月"]) for h in hi for l in lo
                   if abs(h["休み始めた月"] - l["休み始めた月"]) in (1, 11)],
    }


# ---- 節3: 待期3日 -------------------------------------------------------
def waiting_pay(monthly: int, cal_days: int = 91, commuting: bool = False) -> int:
    """待期3日ぶんに出る額。**通勤災害は0円です。**"""
    if commuting:
        return 0
    return int(daily_base(monthly, cal_days) * ROUKI_HOSHO_RATE) * WAITING_DAYS


def waiting_gap(monthly: int = 300_000, cal_days: int = 91) -> dict:
    """業務災害と通勤災害の、待期3日ぶんの差。"""
    work = waiting_pay(monthly, cal_days, commuting=False)
    commute = waiting_pay(monthly, cal_days, commuting=True)
    return {"業務災害": work, "通勤災害": commute, "差": work - commute}


# ---- 節4: 傷病手当金との倍率 --------------------------------------------
def shobyo_daily(standard_pay: int) -> int:
    """傷病手当金の1日あたり。**標準報酬月額を30で割るので、月の日数によりません。**"""
    base = round(standard_pay / SHOBYO_DIVISOR / 10) * 10
    return round(base * SHOBYO_RATE)


def ratio_grid(monthly: int = 300_000) -> list[dict]:
    """暦日数べつの「労災 ÷ 傷病手当金」。**1.2倍をまたぎます。**"""
    s = shobyo_daily(monthly)
    rows = []
    for days in range(CAL_DAYS_MIN, CAL_DAYS_MAX + 1):
        r = benefit(monthly, days)["合計"]
        rows.append({
            "暦日数": days, "労災": r, "傷病手当金": s,
            "倍率": r / s, "率どうしの倍率": (KYUGYO_RATE + TOKUBETSU_RATE) / SHOBYO_RATE,
        })
    return rows


def ratio_crossing(monthly: int = 300_000) -> dict:
    """率どうしの倍率（1.2）を、実際の倍率がまたぐかどうか。"""
    rows = ratio_grid(monthly)
    nominal = (KYUGYO_RATE + TOKUBETSU_RATE) / SHOBYO_RATE
    above = [r for r in rows if r["倍率"] > nominal]
    below = [r for r in rows if r["倍率"] < nominal]
    return {
        "率どうしの倍率": nominal,
        "またぐか": bool(above) and bool(below),
        "上の暦日数": [r["暦日数"] for r in above],
        "下の暦日数": [r["暦日数"] for r in below],
        "いちばん高い倍率": max(r["倍率"] for r in rows),
        "いちばん低い倍率": min(r["倍率"] for r in rows),
    }


# ---- 節5: 一部だけ働いた日 ----------------------------------------------
def partial_day(monthly: int, wage: int, cal_days: int = 91) -> dict:
    """一部だけ働いた日の手元。**（日額 − 賃金）× 80パーセント が出ます。**"""
    d = daily_base(monthly, cal_days)
    w = min(wage, d)
    kyugyo = int((d - w) * KYUGYO_RATE)
    tokubetsu = int((d - w) * TOKUBETSU_RATE)
    total = w + kyugyo + tokubetsu
    return {
        "給付基礎日額": d, "その日の賃金": w,
        "休業補償給付": kyugyo, "休業特別支給金": tokubetsu,
        "手元の合計": total, "日額に対する割合": total / d,
    }


def partial_grid(monthly: int = 300_000, cal_days: int = 91,
                 steps: int = 4) -> list[dict]:
    """賃金を0から日額まで刻む。**直線です（傾きは0.2）。**"""
    d = daily_base(monthly, cal_days)
    return [partial_day(monthly, int(d * i / steps), cal_days)
            for i in range(steps + 1)]


def partial_marginal(monthly: int = 300_000, cal_days: int = 91) -> float:
    """賃金を1円ふやしたときに、手元がいくらふえるか。**0.2 です。**"""
    d = daily_base(monthly, cal_days)
    a = partial_day(monthly, int(d * 0.25), cal_days)["手元の合計"]
    b = partial_day(monthly, int(d * 0.75), cal_days)["手元の合計"]
    return (b - a) / (int(d * 0.75) - int(d * 0.25))


# ---- 節6: 待期の差は日数で薄まる ----------------------------------------
ABSENCE_DAYS = [30, 60, 90, 180, 365]


def absence_total(monthly: int, days: int, cal_days: int = 91,
                  commuting: bool = False) -> dict:
    """休んだ日数ぶんの合計。**最初の3日は労災から出ません。**"""
    b = benefit(monthly, cal_days)
    paid = max(0, days - WAITING_DAYS)
    got = b["合計"] * paid + waiting_pay(monthly, cal_days, commuting)
    return {
        "休んだ日数": days, "支給日数": paid, "合計": got,
        "日額に対する割合": got / (b["給付基礎日額"] * days),
    }


def waiting_fade(monthly: int = 300_000, cal_days: int = 91) -> list[dict]:
    """業務災害と通勤災害の差が、日数でどう薄まるか。**金額の差は一定です。**"""
    rows = []
    for d in ABSENCE_DAYS:
        w = absence_total(monthly, d, cal_days, commuting=False)
        c = absence_total(monthly, d, cal_days, commuting=True)
        rows.append({
            "休んだ日数": d,
            "業務災害の割合": w["日額に対する割合"],
            "通勤災害の割合": c["日額に対する割合"],
            "ポイント差": (w["日額に対する割合"] - c["日額に対する割合"]) * 100,
            "金額の差": w["合計"] - c["合計"],
        })
    return rows


# ---- 図解の元 -----------------------------------------------------------
MONTHLIES = [200_000, 250_000, 300_000, 350_000, 400_000, 500_000]


def grid() -> list[dict]:
    """月給べつの1日あたりと、待期を含めた30日ぶん。"""
    rows = []
    for m in MONTHLIES:
        b = benefit(m)
        rows.append({
            "月給": m,
            "給付基礎日額": b["給付基礎日額"],
            "1日の給付": b["合計"],
            "30日（業務災害）": absence_total(m, 30)["合計"],
            "30日（通勤災害）": absence_total(m, 30, commuting=True)["合計"],
            "傷病手当金の30日": shobyo_daily(m) * (30 - WAITING_DAYS),
        })
    return rows


def check_tables() -> None:
    """制度の値と、この計算の主題そのものを確かめる。"""
    _checks.statutory(KYUGYO_RATE, 0.60, "休業補償給付の割合",
                      source="労災保険法14条1項")
    _checks.statutory(TOKUBETSU_RATE, 0.20, "休業特別支給金の割合",
                      source="労働者災害補償保険特別支給金支給規則3条")
    _checks.statutory(WAITING_DAYS, 3, "待期期間",
                      source="労災保険法14条1項")
    _checks.statutory(ROUKI_HOSHO_RATE, 0.60, "事業主の休業補償の割合",
                      source="労働基準法76条1項")
    _checks.statutory(SHOBYO_DIVISOR, 30, "傷病手当金の除数",
                      source="健康保険法99条")
    _checks.ratio(KYUGYO_RATE, "休業補償給付の割合")
    _checks.ratio(TOKUBETSU_RATE, "休業特別支給金の割合")
    _checks.ratio(SHOBYO_RATE, "傷病手当金の割合")
    _checks.assumption_values(ASSUMPTIONS, name="rousai")

    # 1. 月給が上がれば給付も上がる（**符号を落としていないこと**）
    _checks.increases_with(lambda m: benefit(m)["合計"], MONTHLIES,
                           "月給が増えたのに1日の給付が増えていない")

    # 2. **この表の主題。** 賞与があると、年収に対する割合は8割を必ず下回る
    for row in bonus_grid():
        if row["賞与の月数"] == 0:
            _checks.close(row["式の値"], KYUGYO_RATE + TOKUBETSU_RATE,
                          "賞与0か月のときの年収に対する割合", tol=1e-9)
        else:
            _checks.greater(KYUGYO_RATE + TOKUBETSU_RATE, row["式の値"],
                            f"賞与{row['賞与の月数']}か月で割合が8割を下回っていない")
    _checks.close(year_ratio(4), 0.60, "賞与4か月のときの年収に対する割合")
    _checks.decreases_with(year_ratio, BONUS_MONTHS,
                           "賞与が増えたのに年収に対する割合が下がっていない")

    # 3. 3か月の暦日数は 89〜92日。**この幅が無ければ節2と節4が消えます**
    days = {calendar_days(m) for m in range(1, 13)}
    if min(days) != CAL_DAYS_MIN or max(days) != CAL_DAYS_MAX:
        raise _checks.TableError(
            f"3か月の暦日数の範囲が {min(days)}〜{max(days)} 日です"
            f"（{CAL_DAYS_MIN}〜{CAL_DAYS_MAX} のはず）")

    # 4. **いちばん高い月は1つだけ。低い月は複数ある**（名指しできるのは高いほうだけ）
    #    そのうえで、高い月と隣り合う低い月が実在すること（節2の「隣り合う月で」の根拠）
    sp = month_spread()
    if not sp["高い月は1つか"]:
        raise _checks.TableError(
            f"日額が最大の月が {sp['高い月']} と複数あります。"
            f"1つ名指しする書き方ができません")
    if not sp["隣り合う組"]:
        raise _checks.TableError(
            f"日額が最大の月 {sp['高い月']} と隣り合う最小の月がありません"
            f"（最小は {sp['低い月']}）")

    # 5. **率どうしの倍率 1.2 を、実際の倍率がまたぐこと**（節4の主題）
    cr = ratio_crossing()
    if not cr["またぐか"]:
        raise _checks.TableError(
            f"労災と傷病手当金の倍率が {cr['率どうしの倍率']:.4f} をまたいでいません"
            f"（{cr['いちばん低い倍率']:.4f}〜{cr['いちばん高い倍率']:.4f}）")

    # 6. **一部労働の日の限界の手取り率は 0.2**（節5の主題）
    _checks.close(partial_marginal(), 1 - (KYUGYO_RATE + TOKUBETSU_RATE),
                  "一部労働した日の限界の手取り率", tol=0.01)
    half = partial_grid(steps=2)[1]
    _checks.close(half["日額に対する割合"], 0.90,
                  "半日ぶんの賃金が出る日の、日額に対する割合", tol=0.001)

    # 7. **待期の差は金額では一定、割合では薄まる**（節6の主題）
    fade = waiting_fade()
    if len({r["金額の差"] for r in fade}) != 1:
        raise _checks.TableError(
            f"待期の金額の差が日数で動いています: {[r['金額の差'] for r in fade]}")
    _checks.decreases_with(
        lambda d: waiting_fade()[ABSENCE_DAYS.index(d)]["ポイント差"],
        ABSENCE_DAYS, "休んだ日数が増えたのに、割合の差が薄まっていない")
    _checks.unique_by(fade, lambda r: r["休んだ日数"], "待期の薄まりの表")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 「8割」が8割になるのは、賞与が1円も無い人だけ ===")
    for row in bonus_grid():
        print(f"  賞与 {row['賞与の月数']}か月  年収 {row['年収']:>10,}円  "
              f"1年の給付 {row['1年の給付']:>10,}円  "
              f"→ 年収の {row['年収に対する割合'] * 100:>5.2f}%")

    print("\n=== 同じ月給でも、休み始めた月で日額が変わる ===")
    for row in month_grid():
        print(f"  {row['休み始めた月']:>2}月に休業開始  直前3か月 {row['暦日数']}日  "
              f"給付基礎日額 {row['給付基礎日額']:>7,}円  "
              f"1年の給付 {row['1年の給付']:>10,}円")
    sp = month_spread()
    print(f"  → 最大は {sp['高い月']}月だけ（{sp['高い暦日数']}日・{sp['高い日額']:,}円）。"
          f"最小は {sp['低い月']}月（{sp['低い暦日数']}日・{sp['低い日額']:,}円）で複数あります")
    print(f"     隣り合う組 {sp['隣り合う組']} で、1年 {sp['1年の差']:,}円の差"
          f"（{sp['倍率']:.4f}倍）")

    print("\n=== 待期3日は、業務災害と通勤災害で額が違う ===")
    g = waiting_gap()
    print(f"  業務災害 {g['業務災害']:,}円  通勤災害 {g['通勤災害']:,}円  "
          f"差 {g['差']:,}円")

    print("\n=== 「8割 対 3分の2」の倍率は 1.2倍ではない ===")
    for row in ratio_grid():
        mark = "  ← 1.2倍より得" if row["倍率"] > 1.2 else (
            "  ← 1.2倍より損" if row["倍率"] < 1.2 else "")
        print(f"  直前3か月 {row['暦日数']}日  労災 {row['労災']:>6,}円  "
              f"傷病手当金 {row['傷病手当金']:>6,}円  倍率 {row['倍率']:.4f}{mark}")

    print("\n=== 半日働くと9割。ただし賃金の8割は消える ===")
    for row in partial_grid():
        print(f"  その日の賃金 {row['その日の賃金']:>6,}円  "
              f"給付 {row['休業補償給付'] + row['休業特別支給金']:>6,}円  "
              f"手元 {row['手元の合計']:>6,}円  "
              f"（日額の {row['日額に対する割合'] * 100:>5.1f}%）")
    print(f"  → 賃金を1円ふやしたときに手元がふえるのは "
          f"{partial_marginal():.2f}円（限界の手取り率 "
          f"{partial_marginal() * 100:.0f}%）")

    print("\n=== 待期3日の差は、休みが長くなるほど消える ===")
    for row in waiting_fade():
        print(f"  {row['休んだ日数']:>3}日休む  業務災害 "
              f"{row['業務災害の割合'] * 100:>5.2f}%  通勤災害 "
              f"{row['通勤災害の割合'] * 100:>5.2f}%  "
              f"差 {row['ポイント差']:>4.2f}ポイント（金額では {row['金額の差']:,}円）")
