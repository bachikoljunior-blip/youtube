"""65歳を過ぎてから辞めると、雇用保険からもらえる日数がいくつになるか。

**一般の解説は「65歳以降は基本手当ではなく高年齢求職者給付金（一時金）になる」で止まります。**
その先に、口を開けている段が3つあります。

1つめ。**壁の高さは、勤続年数で決まります。** 高年齢求職者給付金は
算定基礎期間1年以上なら 50日、1年未満なら 30日の**2段しかありません**
（雇用保険法37条の4第1項）。65歳未満の側は勤続でのびていくので、
**長く勤めた人ほど、65歳をまたいだときに落ちる日数が大きくなります。**
倒産・解雇で勤続20年なら 240日 が 50日 になり、**落ちるのは 190日**です。

2つめ。**離職理由で日数が変わるのは、65歳未満だけです。**
65歳未満なら勤続20年で自己都合 150日・解雇 240日 と 90日 ひらきますが、
高年齢求職者給付金に離職理由の区分はありません。
**「解雇されたほうが日数が多い」という構造そのものが、65歳で消えます。**

3つめ。**高年齢求職者給付金は、離職のたびに何度でも受け取れます。**
だから「1回あたり何年働いて辞めるか」で、1年あたりに積み上がる日数が変わります。
**6か月ごとに辞めるのがいちばん多くて 1年あたり 60.0日**、
1年ごとなら 50.0日、**9か月ごとだと 40.0日 まで落ちます**（30日を0.75年で割るため）。
**短いほど多い、ではありません。**

この表が出す数字（実行して出たものを、丸めずに写しています）:

- 倒産・解雇・勤続20年で65歳をまたぐと、240日 が 50日 になります。
  基本手当日額 7,000円 の人なら **1,330,000円** を失い、受け取るのは 350,000円 です
- 自己都合・勤続20年なら 150日 が 50日 で、落ちるのは 100日
- 65歳以降は、勤続を何年のばしても **1年目から先は1日も増えません**
- 算定基礎期間が1年に届かないと 30日、届けば 50日。**この1日の境目で 20日分**が動きます
- 65歳未満の1回ぶんに追いつくには、解雇・勤続20年なら **5回・5.0年**、
  自己都合・勤続20年なら **3回・3.0年** かかります
- **勤続1年未満・自己都合のときだけ、65歳以降のほうが多くなります。**
  65歳未満では受給資格が立たず 0日 ですが、65歳以降は 30日 出ます（**+30日**）
- **「解雇されると何日多いか」は 90日 が既定で、勤続1年以上5年未満だけ 60日 に沈みます。**
  0.99年でも 90日（0日 対 90日）、5年でも 90日（90日 対 180日）なのに、
  そのあいだの 1〜4.99年 だけ 60日（90日 対 150日）。
  **条文にそう書いてあるのではなく、2つの表の段の位置がずれているだけ**です ——
  1年で自己都合は 90日 跳び、解雇は 60日 しか跳ばない。5年で解雇だけ +30 して戻る
"""
from __future__ import annotations

import math

from . import _checks

# ---- 制度の値 -------------------------------------------------------------
# 雇用保険法22条1項（一般の受給資格者の所定給付日数）。**年齢の区分はありません。**
# 被保険者であった期間の下限（年）→ 所定給付日数
KIHON_JIKO: tuple[tuple[float, int], ...] = (
    (0.0, 0),      # 1年未満は、そもそも受給資格が立たない（自己都合は2年間に12か月）
    (1.0, 90),
    (10.0, 120),
    (20.0, 150),
)

# 雇用保険法23条2項（特定受給資格者。倒産・解雇）。**60歳以上65歳未満の欄**
KIHON_KAIKO_60: tuple[tuple[float, int], ...] = (
    (0.0, 90),     # 1年未満でも90日（1年間に6か月で受給資格が立つ）
    (1.0, 150),
    (5.0, 180),
    (10.0, 210),
    (20.0, 240),
)

# 雇用保険法37条の4第1項（高年齢求職者給付金）。**離職理由の区分はありません。**
KOUNEN_UNDER_1Y = 30           # 算定基礎期間 1年未満
KOUNEN_1Y_OVER = 50            # 算定基礎期間 1年以上
KOUNEN_LADDER: tuple[tuple[float, int], ...] = (
    (0.0, KOUNEN_UNDER_1Y),
    (1.0, KOUNEN_1Y_OVER),
)

WAIT_DAYS = 7                  # 待期（雇用保険法21条・37条の4第5項が準用）

# 高年齢求職者給付金を受けるのに要る被保険者期間（37条の3第1項）。
# 離職の日以前**1年間**に通算6か月。基本手当（自己都合）は**2年間**に12か月。
KOUNEN_NEED_MONTHS = 6
KIHON_NEED_MONTHS = 12

# 特別支給の老齢厚生年金が無くなる生年月日（厚生年金保険法附則8条の2。男性）。
TOKUROU_GONE_BIRTH = "昭和36年4月2日"
TOKUROU_GONE_FISCAL_AGE_2026 = 64   # 2026年に64歳になる人は昭和37年生まれ＝もう無い

ASSUMPTIONS = [
    "所定給付日数は雇用保険法22条1項（自己都合など一般の受給資格者）と"
    "23条2項の60歳以上65歳未満の欄（倒産・解雇などの特定受給資格者）を使っています",
    "高年齢求職者給付金の日数は雇用保険法37条の4第1項で、"
    "算定基礎期間が1年以上なら50日、1年未満なら30日の2段しかありません",
    "高年齢求職者給付金には離職理由による区分がありません。"
    "自己都合でも解雇でも同じ日数です",
    "65歳に達した日とは誕生日の前日のことなので、"
    "誕生日の前々日までに離職すれば65歳未満として扱われます",
    "基本手当日額は賃金日額と給付率から決まり、上限額は毎年8月に改定されます。"
    "この表では日額そのものを変数に置いて、日数の差だけを計算しています",
    "待期7日は基本手当にも高年齢求職者給付金にもかかるので、差には出しません",
    "給付制限の日数は改正が続いているので、この表には入れていません",
    "高年齢求職者給付金は一時金なので、受け取ったあとに働いても返す必要はありません。"
    "基本手当のように4週ごとの失業の認定を続ける必要もありません",
]


# ---- 計算 -----------------------------------------------------------------

def _ladder(table: tuple[tuple[float, int], ...], years: float) -> int:
    """下限つきの段の表から、その年数に当たる日数を引く。"""
    days = 0
    for low, d in table:
        if years >= low:
            days = d
    return days


def kihon_days(years: float, *, kaiko: bool = False) -> int:
    """65歳未満で離職したときの所定給付日数。"""
    return _ladder(KIHON_KAIKO_60 if kaiko else KIHON_JIKO, years)


def kounen_days(years: float) -> int:
    """65歳以降に離職したときの高年齢求職者給付金の日数。"""
    return _ladder(KOUNEN_LADDER, years)


def lost_days(years: float, *, kaiko: bool = False) -> int:
    """65歳の壁をまたいだときに落ちる日数。"""
    return kihon_days(years, kaiko=kaiko) - kounen_days(years)


def wall_table() -> list[dict]:
    """勤続年数ごとに、65歳をまたぐと日数がいくつ落ちるか。"""
    out = []
    for y in (0.5, 1, 3, 5, 9, 10, 15, 19, 20, 25, 30, 40):
        out.append({
            "勤続年数": y,
            "自己都合（65歳未満）": kihon_days(y),
            "倒産・解雇（65歳未満）": kihon_days(y, kaiko=True),
            "65歳以降": kounen_days(y),
            "自己都合で落ちる日数": lost_days(y),
            "解雇で落ちる日数": lost_days(y, kaiko=True),
        })
    return out


def reason_gap(years: float, *, over65: bool) -> int:
    """同じ勤続年数で、離職理由がちがうと日数がいくつ変わるか。"""
    if over65:
        return 0
    return kihon_days(years, kaiko=True) - kihon_days(years)


def reason_table() -> list[dict]:
    """離職理由の差は、65歳を過ぎると消える。"""
    out = []
    for y in (0.5, 1, 3, 5, 10, 20, 30):
        out.append({
            "勤続年数": y,
            "65歳未満の理由差": reason_gap(y, over65=False),
            "65歳以降の理由差": reason_gap(y, over65=True),
        })
    return out


def reason_gap_dip_table() -> list[dict]:
    """**「解雇されると何日多いか」は、勤続1年以上5年未満だけ 60日 に落ちます。**

    その外はどこを取っても 90日 ちょうどです。**理由は2つの表の段の位置がずれている
    ことだけ**で、条文にそう書いてあるわけではありません:

        自己都合（22条1項）  1年で 0 → 90 と、**90日 跳ぶ**
        倒産・解雇（23条2項） 1年で 90 → 150 と、**60日 しか跳ばない**
        → 1年をまたぐと、差は 90 から 60 へ**縮む**
        倒産・解雇は 5年で 150 → 180 と **+30**、自己都合は動かない
        → 5年で差は 60 から 90 へ**戻る**

    **10年でも20年でも、両方が同じだけ跳ぶ**（+30 と +30）ので、差は 90日 のままです。

    **掃引が見つけました**（`src.section_sweep` の `帯`。2026-08-27）。
    「離職理由の差は 90日」と読める表を、勤続を軸に振ると
    **1〜5年 のところだけ 60日 に沈んでいます。**
    格子は 0.5 / 1 / 3 / 5 / 10 / 20 / 30年 で、刻み直すと**入口 1.0年・出口 4.99年**。
    """
    out = []
    for y in (0.5, 0.99, 1.0, 3.0, 4.99, 5.0, 10.0, 20.0, 30.0):
        out.append({
            "勤続年数": y,
            "自己都合": kihon_days(y),
            "倒産・解雇": kihon_days(y, kaiko=True),
            "解雇のほうが多い日数": reason_gap(y, over65=False),
        })
    return out


def reason_gap_dip_range() -> tuple[float, float]:
    """差が 60日 に沈んでいる帯の、**入口と出口**（勤続年数）。

    表の段そのものから引きます。**数を写さないこと** ——
    `KIHON_JIKO` / `KIHON_KAIKO_60` を動かせば、ここも一緒に動きます。
    """
    edges = sorted({y for y, _ in KIHON_JIKO} | {y for y, _ in KIHON_KAIKO_60})
    outer = max(reason_gap(y, over65=False) for y in edges)
    dipped = [y for y in edges if reason_gap(y, over65=False) < outer]
    lo = min(dipped)
    # 出口は「次の段の直前」。段の刻みは年なので、1日ぶん手前を 0.01年 で置く。
    nxt = min((y for y in edges if y > max(dipped)), default=max(dipped))
    return lo, round(nxt - 0.01, 2)


def money(days: int, daily: float) -> float:
    """日数と基本手当日額から、受け取る総額。"""
    return days * daily


def money_table(daily_grid: tuple[int, ...] = (3_000, 4_000, 5_000, 6_000, 7_000)
                ) -> list[dict]:
    """日額べつに、勤続20年の人が65歳をまたいで失う金額。"""
    out = []
    for d in daily_grid:
        out.append({
            "基本手当日額": d,
            "自己都合で失う額": money(lost_days(20), d),
            "解雇で失う額": money(lost_days(20, kaiko=True), d),
            "65歳以降に受け取る額": money(kounen_days(20), d),
        })
    return out


def repeat_total(times: int, years_each: float = 1.0) -> int:
    """65歳以降に、離職と再就職をくり返したときの累計日数。"""
    return times * kounen_days(years_each)


def catch_up_times(years: float, *, kaiko: bool = False,
                   years_each: float = 1.0) -> int:
    """65歳未満の1回ぶんに追いつくのに、65歳以降で何回離職すればよいか。"""
    per = kounen_days(years_each)
    return math.ceil(kihon_days(years, kaiko=kaiko) / per)


def catch_up_years(years: float, *, kaiko: bool = False,
                   years_each: float = 1.0) -> float:
    """その回数を重ねるのに要る年数（1回ごとに算定基礎期間ぶん働く）。"""
    return catch_up_times(years, kaiko=kaiko, years_each=years_each) * years_each


def catch_up_table() -> list[dict]:
    """追いつくのに要る回数と年数。"""
    out = []
    for y in (1, 5, 10, 20, 30):
        out.append({
            "勤続年数": y,
            "自己都合の日数": kihon_days(y),
            "追いつく回数（自己都合）": catch_up_times(y),
            "追いつく年数（自己都合）": catch_up_years(y),
            "解雇の日数": kihon_days(y, kaiko=True),
            "追いつく回数（解雇）": catch_up_times(y, kaiko=True),
            "追いつく年数（解雇）": catch_up_years(y, kaiko=True),
        })
    return out


def days_per_year(years_each: float) -> float:
    """65歳以降、`years_each` 年ごとに離職をくり返したときの、1年あたりの日数。"""
    return kounen_days(years_each) / years_each


def pace_table() -> list[dict]:
    """1回あたり何年働いて辞めるかで、1年あたりの日数が変わる。"""
    out = []
    for y in (0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0):
        out.append({
            "1回あたりの期間": y,
            "1回の日数": kounen_days(y),
            "1年あたりの日数": days_per_year(y),
        })
    return out


def flip_table() -> list[dict]:
    """65歳以降のほうが多くなる帯（自己都合・勤続1年未満）。"""
    out = []
    for y in (0.5, 0.6, 0.9, 0.99, 1.0, 1.5):
        under, over = kihon_days(y), kounen_days(y)
        out.append({
            "勤続年数": y,
            "65歳未満・自己都合": under,
            "65歳以降": over,
            "65歳以降の取り分": over - under,
        })
    return out


def one_day_table(daily: float = 5_000) -> list[dict]:
    """算定基礎期間が1年に届くかどうかで、1日の差がいくら動くか。"""
    out = []
    base = None
    for y in (0.99, 1.0):
        amount = money(kounen_days(y), daily)
        out.append({
            "算定基礎期間": y,
            "日数": kounen_days(y),
            "受け取る額": amount,
            # **差そのものを印字します** —— 台本が引く「20日で100,000円」は
            # 引き算の結果なので、表に出しておかないと裏が取れません。
            "1年未満との差": 0.0 if base is None else amount - base,
            "1年未満との日数差": 0 if base is None else kounen_days(y) - kounen_days(0.99),
        })
        if base is None:
            base = amount
    return out


def per_year_table() -> list[dict]:
    """勤続を1年のばしたときに増える日数（65歳未満と65歳以降）。"""
    out = []
    prev_j = prev_k = prev_o = None
    for y in range(1, 26):
        j, k, o = kihon_days(y), kihon_days(y, kaiko=True), kounen_days(y)
        out.append({
            "勤続年数": y,
            "1年からのばした年数": y - 1,
            "自己都合": j,
            "自己都合の増分": 0 if prev_j is None else j - prev_j,
            "解雇": k,
            "解雇の増分": 0 if prev_k is None else k - prev_k,
            "65歳以降": o,
            "65歳以降の増分": 0 if prev_o is None else o - prev_o,
        })
        prev_j, prev_k, prev_o = j, k, o
    return out


def need_months_table() -> list[dict]:
    """受給資格に要る被保険者期間（さかのぼる窓もちがう）。"""
    return [
        {"制度": "基本手当（自己都合）", "さかのぼる窓（年）": 2,
         "要る被保険者期間（月）": KIHON_NEED_MONTHS},
        {"制度": "基本手当（倒産・解雇）", "さかのぼる窓（年）": 1,
         "要る被保険者期間（月）": KOUNEN_NEED_MONTHS},
        {"制度": "高年齢求職者給付金", "さかのぼる窓（年）": 1,
         "要る被保険者期間（月）": KOUNEN_NEED_MONTHS},
    ]


def grid() -> list[dict]:
    """図解の元になる表。**65歳の壁の高さが、この表のいちばんの主題です。**"""
    return wall_table()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""

    # 1. 法令が名指ししている値
    _checks.statutory(KOUNEN_UNDER_1Y, 30, "高年齢求職者給付金（1年未満）",
                      source="雇用保険法37条の4第1項")
    _checks.statutory(KOUNEN_1Y_OVER, 50, "高年齢求職者給付金（1年以上）",
                      source="雇用保険法37条の4第1項")
    _checks.statutory(kihon_days(20), 150, "自己都合・勤続20年の所定給付日数",
                      source="雇用保険法22条1項")
    _checks.statutory(kihon_days(20, kaiko=True), 240,
                      "倒産・解雇・60歳以上65歳未満・勤続20年の所定給付日数",
                      source="雇用保険法23条2項")
    _checks.statutory(WAIT_DAYS, 7, "待期", source="雇用保険法21条")
    _checks.statutory(KOUNEN_NEED_MONTHS, 6,
                      "高年齢求職者給付金に要る被保険者期間",
                      source="雇用保険法37条の3第1項")
    _checks.statutory(KIHON_NEED_MONTHS, 12,
                      "基本手当（自己都合）に要る被保険者期間",
                      source="雇用保険法13条1項")

    # 2. **主題その1**: 65歳をまたぐと日数が落ちる。落ちない年数は1つも無い。
    for row in wall_table():
        if row["勤続年数"] >= 1:
            _checks.greater(row["自己都合で落ちる日数"], 0,
                            f"勤続{row['勤続年数']}年・自己都合で日数が落ちていない")
        _checks.greater(row["解雇で落ちる日数"], 0,
                        f"勤続{row['勤続年数']}年・解雇で日数が落ちていない")

    # 落ちる日数がいちばん大きいのは、解雇・勤続20年以上。
    _checks.rounding(lost_days(20, kaiko=True), 190, "解雇・勤続20年で落ちる日数")
    _checks.rounding(lost_days(20), 100, "自己都合・勤続20年で落ちる日数")

    # 3. **主題その2**: 壁は勤続が長いほど高い（65歳以降が1年で頭打ちだから）。
    _checks.never_decreases(lambda y: lost_days(y, kaiko=True),
                            [1, 5, 10, 20, 30],
                            "勤続がのびたのに解雇の壁が低くなっている")
    _checks.rounding(kounen_days(1), kounen_days(40),
                     "65歳以降が1年より先ものびている（頭打ちでない）")

    # 4. **主題その3**: 離職理由の差が、65歳を過ぎると消える。
    _checks.greater(reason_gap(20, over65=False), 0,
                    "65歳未満で離職理由の差が無い")
    _checks.rounding(reason_gap(20, over65=True), 0,
                     "65歳以降に離職理由の差が残っている")
    _checks.rounding(reason_gap(20, over65=False), 90,
                     "勤続20年の離職理由の差（65歳未満）")

    # 4b. **主題その6**（2026-08-27 に掃引が見つけた）: 理由差は 90日 が既定で、
    #     **勤続1年以上5年未満だけ 60日 に沈む。**
    _checks.rounding(reason_gap(3, over65=False), 60,
                     "勤続3年の離職理由の差（65歳未満）")
    _checks.rounding(reason_gap(0.5, over65=False), 90,
                     "勤続0.5年の離職理由の差（65歳未満）")
    _checks.rounding(reason_gap(5, over65=False), 90,
                     "勤続5年の離職理由の差（65歳未満）")
    lo, hi = reason_gap_dip_range()
    _checks.rounding(lo, 1.0, "理由差が沈む帯の入口")
    _checks.rounding(hi, 4.99, "理由差が沈む帯の出口")
    for row in reason_gap_dip_table():
        want = 60 if lo <= row["勤続年数"] <= hi else 90
        _checks.rounding(row["解雇のほうが多い日数"], want,
                         f"勤続{row['勤続年数']}年の理由差")

    # 5. 金額は日額に比例して増えること。
    _checks.increases_with(lambda d: money(lost_days(20, kaiko=True), d),
                           [3_000, 4_000, 5_000, 6_000, 7_000],
                           "日額が上がったのに失う額が増えていない")

    # 6. 追いつく回数は、日数が多いほど増えること。
    _checks.never_decreases(lambda y: catch_up_times(y, kaiko=True),
                            [1, 5, 10, 20, 30],
                            "日数が増えたのに追いつく回数が減っている")
    _checks.rounding(catch_up_times(20, kaiko=True), 5,
                     "解雇・勤続20年に追いつく回数")
    _checks.rounding(catch_up_times(20), 3, "自己都合・勤続20年に追いつく回数")

    # 7. 1年の境目で20日ぶん動くこと。
    _checks.rounding(kounen_days(1.0) - kounen_days(0.99), 20,
                     "算定基礎期間1年の境目で動く日数")

    # 8. 65歳以降は、勤続を1年のばしても2年目から1日も増えないこと。
    later = [r for r in per_year_table() if r["勤続年数"] >= 2]
    for r in later:
        _checks.rounding(r["65歳以降の増分"], 0,
                         f"勤続{r['勤続年数']}年で65歳以降の日数が増えている")

    # 9. **主題その4**: 勤続1年未満・自己都合では、65歳以降のほうが多い。
    _checks.rounding(kihon_days(0.5), 0, "勤続0.5年・自己都合の所定給付日数")
    _checks.greater(kounen_days(0.5), kihon_days(0.5),
                    "勤続0.5年で65歳以降のほうが少ない（逆転していない）")

    # 10. **主題その5**: 短く区切って辞めるほうが、1年あたりの日数は多い。
    _checks.rounding(days_per_year(0.5), 60, "6か月ごとに辞めたときの1年あたり日数")
    _checks.rounding(days_per_year(1.0), 50, "1年ごとに辞めたときの1年あたり日数")
    _checks.greater(days_per_year(0.5), days_per_year(1.0),
                    "6か月ごとのほうが1年あたりで少ない")
    _checks.decreases_with(days_per_year, [1.0, 1.5, 2.0, 3.0, 5.0],
                           "期間をのばしたのに1年あたりの日数が減っていない")

    _checks.unique_by(wall_table(), lambda r: r["勤続年数"], "勤続年数")
    _checks.unique_by(pace_table(), lambda r: r["1回あたりの期間"], "1回あたりの期間")
    _checks.unique_by(need_months_table(), lambda r: r["制度"], "制度")
    _checks.assumption_values(ASSUMPTIONS, name="koureikyushoku")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 65歳の誕生日の前々日までに辞めるかどうかで、もらえる日数がここまで変わる ===")
    for row in wall_table():
        print(f"  勤続 {row['勤続年数']:>4}年"
              f"  自己都合 {row['自己都合（65歳未満）']:>4}日"
              f"  解雇 {row['倒産・解雇（65歳未満）']:>4}日"
              f"  → 65歳以降 {row['65歳以降']:>3}日"
              f"（自己都合 {-row['自己都合で落ちる日数']:>+4}日"
              f" / 解雇 {-row['解雇で落ちる日数']:>+4}日）")

    print("\n=== 65歳以降は、勤続を何年のばしても日数が1日も増えない ===")
    for row in per_year_table():
        if row["勤続年数"] in (1, 2, 5, 9, 10, 11, 19, 20, 21, 25):
            print(f"  勤続 {row['勤続年数']:>3}年"
                  f"（1年から +{row['1年からのばした年数']:>2}年）"
                  f"  自己都合 {row['自己都合']:>4}日（+{row['自己都合の増分']:>2}）"
                  f"  解雇 {row['解雇']:>4}日（+{row['解雇の増分']:>2}）"
                  f"  65歳以降 {row['65歳以降']:>3}日（+{row['65歳以降の増分']:>2}）")

    print("\n=== 離職理由で日数が変わるのは65歳未満だけ。65歳を過ぎると差は消える ===")
    for row in reason_table():
        print(f"  勤続 {row['勤続年数']:>4}年"
              f"  65歳未満は解雇のほうが {row['65歳未満の理由差']:>3}日 多い"
              f"  / 65歳以降の差 {row['65歳以降の理由差']:>3}日")

    _lo, _hi = reason_gap_dip_range()
    print(f"\n=== 解雇のほうが多い日数は 90日 が既定で、勤続{_lo:g}年以上{_hi:g}年以下だけ 60日 に沈む ===")
    for row in reason_gap_dip_table():
        mark = "  ← 沈んでいる" if _lo <= row["勤続年数"] <= _hi else ""
        print(f"  勤続 {row['勤続年数']:>5}年"
              f"  自己都合 {row['自己都合']:>4}日"
              f"  解雇 {row['倒産・解雇']:>4}日"
              f"  → 解雇のほうが {row['解雇のほうが多い日数']:>3}日 多い{mark}")

    print("\n=== 勤続20年の人が、65歳をまたいで失う金額（基本手当日額べつ）===")
    for row in money_table():
        print(f"  日額 {row['基本手当日額']:>6,}円"
              f"  自己都合 -{row['自己都合で失う額']:>10,.0f}円"
              f"  解雇 -{row['解雇で失う額']:>10,.0f}円"
              f"  （65歳以降に受け取るのは {row['65歳以降に受け取る額']:>9,.0f}円）")

    print("\n=== 高年齢求職者給付金は何度でも受け取れる。1回ぶんに追いつくまでの回数と年数 ===")
    for row in catch_up_table():
        print(f"  勤続 {row['勤続年数']:>3}年"
              f"  自己都合 {row['自己都合の日数']:>4}日 →"
              f" {row['追いつく回数（自己都合）']:>2}回・{row['追いつく年数（自己都合）']:>4.1f}年"
              f"   解雇 {row['解雇の日数']:>4}日 →"
              f" {row['追いつく回数（解雇）']:>2}回・{row['追いつく年数（解雇）']:>4.1f}年")

    print("\n=== 算定基礎期間が1年に1日届かないだけで、20日分が消える（日額5,000円）===")
    for row in one_day_table():
        print(f"  算定基礎期間 {row['算定基礎期間']:>5}年"
              f"  {row['日数']:>3}日"
              f"  {row['受け取る額']:>9,.0f}円"
              f"  （1年未満との差 {row['1年未満との日数差']:>2}日"
              f"・{row['1年未満との差']:>8,.0f}円）")

    print("\n=== 受給資格に要る期間は、さかのぼる窓のほうが先に効く ===")
    for row in need_months_table():
        print(f"  {row['制度']:<22}"
              f" さかのぼる窓 {row['さかのぼる窓（年）']}年"
              f"  要る被保険者期間 {row['要る被保険者期間（月）']}か月")

    print("\n=== 勤続1年未満で自己都合なら、65歳以降のほうが多い（基本手当は受給資格が立たない）===")
    for row in flip_table():
        print(f"  勤続 {row['勤続年数']:>5}年"
              f"  65歳未満・自己都合 {row['65歳未満・自己都合']:>4}日"
              f"  65歳以降 {row['65歳以降']:>3}日"
              f"  → 65歳以降の取り分 {row['65歳以降の取り分']:>+4}日")

    print("\n=== 何年ごとに辞めるかで、1年あたりの日数が変わる（6か月ごとがいちばん多い）===")
    for row in pace_table():
        print(f"  1回あたり {row['1回あたりの期間']:>4}年"
              f"  1回 {row['1回の日数']:>3}日"
              f"  → 1年あたり {row['1年あたりの日数']:>5.1f}日")
