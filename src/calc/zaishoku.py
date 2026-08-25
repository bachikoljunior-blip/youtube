"""在職老齢年金 —— 働きながら年金を受け取ると、いくら止まるのかを計算する。

狙いは「50万円を超えると年金が減ります」を紹介することではない。それはどこにでもある。
ここで出したいのは **止まる額そのものと、その裏にある実質的な手取りの傾き** ——
月給を1万円上げたとき、手元がいくら増えるのか（あるいは増えないのか）を、
標準報酬月額の等級きざみで全部出したもの。

--------------------------------------------------------------------------
広く出回っている数字と、何が違うのか
--------------------------------------------------------------------------
よく見るのは次の2つで止まっている。

1. 「基本月額と総報酬月額相当額の合計が支給停止調整額を超えると、超えた分の
   2分の1が止まる」という**式の紹介**
2. 「年金月額10万円・給与月額45万円なら2万5千円止まる」という**1点だけの例**

足りないのは、**その式が給与の側に何をしているか**である。
超えた分の2分の1が止まるということは、月給を1万円上げると年金が5千円減る。
つまり給与に対して**50パーセントの追加の目減り**が、税と社会保険料とは別に掛かる。
この帯にいる人にとって、月給1万円の値打ちは1万円ではない。

そしてもう1つ、ほとんど書かれていないのが **賞与の効き方** である。
総報酬月額相当額は「その月の標準報酬月額 ＋ その月以前1年間の標準賞与額の合計 ÷ 12」で、
賞与は12で割って**毎月に載る**。年間の賞与が120万円なら、月給が10万円上がったのと
同じ扱いになり、**12か月ぶん年金が止まり続ける**。同じ年収でも、賞与で受け取るか
月給で受け取るかで、止まる額は変わらない —— ここは直感に反する側で、
「賞与にすれば年金は止まらない」という誤解がよく流れている。実際には変わらない。

--------------------------------------------------------------------------
止まらないもの
--------------------------------------------------------------------------
止まるのは**老齢厚生年金の報酬比例部分だけ**である。老齢基礎年金は止まらない。
加給年金は、報酬比例部分が全額止まると一緒に止まる。

だから「年金が全部消える」ことは、基礎年金を受け取っている人には起きない。
ここでは、その**基礎年金を含めた手元の合計**まで出す。式の紹介で終わると、
「全額停止」という言葉だけが残って、実際に手元に何が残るのかが見えない。

--------------------------------------------------------------------------
この表がどこにも無い理由
--------------------------------------------------------------------------
標準報酬月額は32等級ある。基本月額は人によって違う。賞与の有無でも変わる。
掛け合わせると数百通りになり、記事の中に置ける大きさではない。
だから「例を1つ」で終わる。ここではその全部を出す。
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "在職老齢年金の支給停止調整額は令和7年度の51万円で計算しています。"
    "令和6年度は50万円で、この額は毎年度改定されます",
    "止まる額は、基本月額と総報酬月額相当額の合計から支給停止調整額を引き、"
    "その2分の1としています。合計が支給停止調整額以下なら止まりません",
    "基本月額は老齢厚生年金の報酬比例部分を12で割った額です。"
    "老齢基礎年金は在職老齢年金では止まりません",
    "総報酬月額相当額は、その月の標準報酬月額に、その月以前1年間の標準賞与額の合計を"
    "12で割った額を足したものです",
    "標準賞与額は、賞与の額から1000円未満を切り捨て、1回あたり150万円を上限として"
    "います。上限を超えたぶんは総報酬月額相当額に載りません",
    "標準報酬月額は厚生年金の第1等級8万8千円から第32等級65万円までで計算しています",
    "老齢基礎年金は満額の年額83万1700円、月額6万9308円として置いています。"
    "これは令和7年度の満額で、納付月数が480か月に満たない人はこれより少なくなります",
    "止まった年金は後から戻りません。受け取らずに消えるものとして計算しています",
    "税金と社会保険料は入れていません。ここで出しているのは年金が止まる額だけです",
    "加給年金と振替加算は入れていません",
]

# ---- 制度の値 ------------------------------------------------------------
# 支給停止調整額。厚生年金保険法第46条。毎年度改定される。
STOP_BASE_R7 = 510_000          # 令和7年度
STOP_BASE_R6 = 500_000          # 令和6年度
STOP_SHARE = 0.5                # 超えた分のうち止まる割合（2分の1）

# 標準報酬月額（厚生年金）。第1等級から第32等級まで。令和2年9月に32等級へ。
GRADE_MIN = 88_000              # 第1等級
GRADE_MAX = 650_000             # 第32等級

# 標準賞与額の1回あたりの上限（厚生年金）。
BONUS_CAP_PER_TIME = 1_500_000

# 老齢基礎年金の満額（令和7年度・年額）。在職老齢年金では止まらない。
BASIC_ANNUAL = 831_700

# 標準報酬月額表のうち、この計算で使う等級（第20等級以上。ここから下は
# 支給停止に届く組み合わせがほとんど無い）。厚生年金保険法別表。
GRADES_HIGH = [
    320_000, 340_000, 360_000, 380_000, 410_000, 440_000, 470_000,
    500_000, 530_000, 560_000, 590_000, 620_000, 650_000,
]


# 老齢基礎年金が満額になる納付月数（40年）。
FULL_MONTHS = 480


def kiso_monthly(months: int = FULL_MONTHS) -> int:
    """納付月数から老齢基礎年金の月額（円）を出す。**480か月で満額**。

    `ASSUMPTIONS` は「納付月数が480か月に満たない人はこれより少なくなります」と
    言っているのに、**それを入力として動かした節が1つもありませんでした**。
    基礎年金は在職老齢年金では止まらないので、ここは停止額とは独立に手元を動かす。
    """
    return round(BASIC_ANNUAL * min(months, FULL_MONTHS) / FULL_MONTHS / 12)


def basic_monthly() -> int:
    """老齢基礎年金の月額（満額・円）。**止まらない側**。"""
    return kiso_monthly(FULL_MONTHS)


def standard_bonus(amount: float) -> int:
    """標準賞与額（円）。1000円未満を切り捨て、**1回あたり150万円が上限**。"""
    return min(int(amount // 1000) * 1000, BONUS_CAP_PER_TIME)


def counted_annual_bonus(annual_bonus: float, times: int) -> int:
    """年間の賞与を `times` 回に分けて受け取ったとき、総報酬に載る合計（円）。

    **1回あたりの上限があるので、同じ年額でも回数で載る額が変わる。**
    """
    return standard_bonus(annual_bonus / times) * times


def total_monthly(grade: int, annual_bonus: int = 0) -> float:
    """総報酬月額相当額。標準報酬月額 ＋ 1年間の標準賞与額 ÷ 12。"""
    return grade + annual_bonus / 12


def stopped(kihon_monthly: float, grade: int, annual_bonus: int = 0,
            stop_base: int = STOP_BASE_R7) -> float:
    """止まる年金の月額（円）。止まらないときは 0。

    止まる額は基本月額を超えない（基本月額より多くは止められない）。
    """
    over = kihon_monthly + total_monthly(grade, annual_bonus) - stop_base
    if over <= 0:
        return 0.0
    return min(kihon_monthly, over * STOP_SHARE)


def paid(kihon_monthly: float, grade: int, annual_bonus: int = 0,
         stop_base: int = STOP_BASE_R7) -> float:
    """実際に受け取れる老齢厚生年金の月額（円）。"""
    return kihon_monthly - stopped(kihon_monthly, grade, annual_bonus, stop_base)


def full_stop_grade(kihon_monthly: float, annual_bonus: int = 0,
                    stop_base: int = STOP_BASE_R7) -> float:
    """報酬比例部分が全額止まる、総報酬月額相当額のさかい目（円）。

    止まる額が基本月額に等しくなるのは
        (基本月額 + 総報酬) − 停止調整額 = 基本月額 × 2
    つまり 総報酬 = 停止調整額 + 基本月額。
    """
    return stop_base + kihon_monthly


def grade_grid(kihon_monthly: float, annual_bonus: int = 0,
               stop_base: int = STOP_BASE_R7) -> list[dict]:
    """標準報酬月額の等級ごとに、止まる額と手元の合計を出す。"""
    rows = []
    basic = basic_monthly()
    for g in GRADES_HIGH:
        stop = stopped(kihon_monthly, g, annual_bonus, stop_base)
        rows.append({
            "標準報酬月額": g,
            "総報酬月額相当額": round(total_monthly(g, annual_bonus)),
            "止まる年金_月": round(stop),
            "受け取る厚生年金_月": round(kihon_monthly - stop),
            "基礎年金_月": basic,
            "年金の手元_月": round(kihon_monthly - stop + basic),
            "給与と年金の合計_月": round(g + kihon_monthly - stop + basic),
            "止まる年金_年": round(stop * 12),
        })
    return rows


def marginal_grid(kihon_monthly: float, annual_bonus: int = 0,
                  stop_base: int = STOP_BASE_R7) -> list[dict]:
    """等級を1つ上げたとき、月給の増えぶんのうち手元に残るのはいくらか。

    **この表がこの計算の主題。** 停止の帯にいるあいだは、増えた月給の半分が
    年金の停止で消える。帯の入口と出口で、残る割合が階段状に変わる。
    """
    rows = []
    for lo, hi in zip(GRADES_HIGH, GRADES_HIGH[1:]):
        up = hi - lo
        lost = stopped(kihon_monthly, hi, annual_bonus, stop_base) \
            - stopped(kihon_monthly, lo, annual_bonus, stop_base)
        rows.append({
            "等級を上げる": f"{lo:,}円 → {hi:,}円",
            "月給の増え": up,
            "年金の減り": round(lost),
            "手元の増え": round(up - lost),
            "残る割合": round((up - lost) / up, 3),
        })
    return rows


def bonus_grid(kihon_monthly: float, grade: int = 380_000,
               stop_base: int = STOP_BASE_R7) -> list[dict]:
    """年間の賞与ごとに、止まる額を出す。**賞与は12で割って毎月に載る。**

    「賞与で受け取れば年金は止まらない」という誤解に対する答えがここ。
    """
    rows = []
    for bonus in (0, 300_000, 600_000, 900_000, 1_200_000, 1_800_000, 2_400_000):
        stop = stopped(kihon_monthly, grade, bonus, stop_base)
        rows.append({
            "年間の賞与": bonus,
            "月に載る額": round(bonus / 12),
            "総報酬月額相当額": round(total_monthly(grade, bonus)),
            "止まる年金_月": round(stop),
            "止まる年金_年": round(stop * 12),
            "賞与100円あたり止まる額_年": round(stop * 12 / bonus * 100) if bonus else 0,
        })
    return rows


def threshold_grid(annual_bonus: int = 0,
                   stop_base: int = STOP_BASE_R7) -> list[dict]:
    """基本月額ごとに、止まりはじめる月給と、全額止まる月給を出す。

    止まりはじめるのは 総報酬 = 停止調整額 − 基本月額 を**超えた**ところ。
    全額止まるのは 総報酬 = 停止調整額 + 基本月額。
    **この2つの間隔は基本月額の2倍**で、基本月額が大きい人ほど帯が広い。
    """
    rows = []
    for kihon in (50_000, 80_000, 100_000, 120_000, 150_000, 180_000):
        start = stop_base - kihon
        full = full_stop_grade(kihon, annual_bonus, stop_base)
        rows.append({
            "基本月額": kihon,
            "止まりはじめる総報酬": start,
            "全額止まる総報酬": round(full),
            "帯の幅": round(full - start),
            "帯の幅は基本月額の何倍": round((full - start) / kihon, 1),
            "年金の年額": kihon * 12,
        })
    return rows


def year_change_grid(kihon_monthly: float, annual_bonus: int = 0) -> list[dict]:
    """令和6年度（50万円）と令和7年度（51万円）で、止まる額がどれだけ変わるか。

    調整額が1万円上がると、止まる額は**その半分の5千円**だけ減る。
    """
    rows = []
    for g in GRADES_HIGH:
        r6 = stopped(kihon_monthly, g, annual_bonus, STOP_BASE_R6)
        r7 = stopped(kihon_monthly, g, annual_bonus, STOP_BASE_R7)
        rows.append({
            "標準報酬月額": g,
            "令和6年度_止まる_月": round(r6),
            "令和7年度_止まる_月": round(r7),
            "差_月": round(r6 - r7),
            "差_年": round((r6 - r7) * 12),
        })
    return rows


def bonus_times_grid(kihon_monthly: float, grade: int = 380_000,
                     annual_bonus: int = 3_000_000,
                     stop_base: int = STOP_BASE_R7) -> list[dict]:
    """**同じ年間賞与でも、何回に分けて受け取るかで止まる額が変わる。**

    モジュールの冒頭は「賞与で受け取るか月給で受け取るかで、止まる額は変わらない」と
    書いている。それは正しいが、**1回あたり150万円の上限を無視したときだけ**である。
    まとめて受け取れば上限で切り捨てられ、総報酬月額相当額に載らない。
    """
    rows = []
    for times in (1, 2, 3, 4, 6, 12):
        per = annual_bonus / times
        counted = counted_annual_bonus(annual_bonus, times)
        stop = stopped(kihon_monthly, grade, counted, stop_base)
        rows.append({
            "受け取る回数": times,
            "年間の賞与": annual_bonus,
            "1回あたり": round(per),
            "標準賞与額_1回": standard_bonus(per),
            "総報酬に載る年間合計": counted,
            "切り捨てられた額": annual_bonus - counted,
            "標準報酬月額": grade,
            "総報酬月額相当額": round(total_monthly(grade, counted)),
            "止まる年金_月": round(stop),
            "受け取る厚生年金_月": round(paid(kihon_monthly, grade, counted, stop_base)),
            "止まる年金_年": round(stop * 12),
        })
    return rows


def months_grid(kihon_monthly: float, grade: int = 500_000,
                annual_bonus: int = 0,
                stop_base: int = STOP_BASE_R7) -> list[dict]:
    """**納付月数ごとに、停止が年金の手元の何割を持っていくか。**

    止まるのは報酬比例部分だけで、基礎年金は止まらない。だから納付月数が短い人ほど
    「止まらない側」が小さく、**同じ給与・同じ停止額でも打撃の割合は大きくなる**。
    """
    rows = []
    stop = stopped(kihon_monthly, grade, annual_bonus, stop_base)
    kosei = paid(kihon_monthly, grade, annual_bonus, stop_base)
    for months in (FULL_MONTHS, 420, 360, 300, 240, 180, 120):
        kiso = kiso_monthly(months)
        before = kihon_monthly + kiso
        after = kosei + kiso
        rows.append({
            "納付月数": months,
            "納付年数": round(months / 12, 1),
            "基礎年金_月": kiso,
            "止まらなければ年金の手元_月": round(before),
            "止まったあと年金の手元_月": round(after),
            "止まる年金_月": round(stop),
            "手元が減る割合": round(stop / before, 4),
            "標準報酬月額": grade,
        })
    return rows


def average_rate_grid(kihon_monthly: float, annual_bonus: int = 0,
                      stop_base: int = STOP_BASE_R7) -> list[dict]:
    """**給与に対する目減り率は、途中で頭打ちになって下がりはじめる。**

    限界（等級を1つ上げたぶん）は帯の中で 50%（`marginal_grid`）だが、
    給与の総額に対する平均の率は別物である。止まる額が基本月額で頭打ちになるので、
    **率の山は「全額止まるさかい目」にあり、そこから上は給与で薄まって下がる**。
    """
    rows = []
    for g in GRADES_HIGH:
        stop = stopped(kihon_monthly, g, annual_bonus, stop_base)
        rows.append({
            "標準報酬月額": g,
            "総報酬月額相当額": round(total_monthly(g, annual_bonus)),
            "止まる年金_月": round(stop),
            "受け取る厚生年金_月": round(paid(kihon_monthly, g, annual_bonus, stop_base)),
            "給与に対する目減り率": round(stop / g, 4),
            "年金に対する目減り率": round(stop / kihon_monthly, 4),
            "給与と年金の合計_月": round(g + paid(kihon_monthly, g, annual_bonus, stop_base)),
        })
    return rows


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(STOP_BASE_R7, 510_000, "支給停止調整額（令和7年度）",
                      source="厚生年金保険法第46条")
    _checks.statutory(STOP_BASE_R6, 500_000, "支給停止調整額（令和6年度）",
                      source="厚生年金保険法第46条")
    _checks.statutory(STOP_SHARE, 0.5, "超えた分のうち止まる割合",
                      source="厚生年金保険法第46条")
    _checks.ratio(STOP_SHARE, "止まる割合")
    _checks.statutory(GRADE_MIN, 88_000, "標準報酬月額の第1等級",
                      source="厚生年金保険法第20条別表")
    _checks.statutory(GRADE_MAX, 650_000, "標準報酬月額の第32等級",
                      source="厚生年金保険法第20条別表")
    _checks.statutory(BONUS_CAP_PER_TIME, 1_500_000, "標準賞与額の1回あたり上限",
                      source="厚生年金保険法第24条の4")
    _checks.statutory(BASIC_ANNUAL, 831_700, "老齢基礎年金の満額（令和7年度）",
                      source="令和7年度年金額改定")

    # 2. 表の等級が、法定の範囲におさまって昇順であること
    _checks.ascending(GRADES_HIGH, "標準報酬月額の等級", strict=True)
    if GRADES_HIGH[0] < GRADE_MIN or GRADES_HIGH[-1] > GRADE_MAX:
        raise _checks.TableError(
            f"等級が法定の範囲外: {GRADES_HIGH[0]}〜{GRADES_HIGH[-1]} "
            f"（{GRADE_MIN}〜{GRADE_MAX}）")

    # 3. 計算の向き（**この計算の主題そのもの**）
    # 停止調整額以下では1円も止まらない
    if stopped(100_000, 400_000) != 0:
        raise _checks.TableError("合計51万円ちょうどで止まっている。超えた分だけのはず")
    _checks.rounding(stopped(100_000, 410_000), 0.0,
                     "基本月額10万・月給41万（合計51万ちょうど）")
    # 1万円超えたら、その半分の5千円が止まる
    _checks.rounding(stopped(100_000, 420_000), 5_000,
                     "基本月額10万・月給42万（1万円超過）")
    # 停止の帯に入ったあとは、月給が上がるほど止まる額は増える
    # （基本月額10万なら総報酬41万円を超えてから。それ以下は0で平ら）
    band = [g for g in GRADES_HIGH if g > STOP_BASE_R7 - 100_000
            and g < full_stop_grade(100_000)]
    _checks.increases_with(lambda g: stopped(100_000, g), band,
                           "月給が上がったのに止まる額が増えていない")
    # 月給が上がるほど受け取る年金は減る
    _checks.decreases_with(lambda g: paid(100_000, g), band,
                           "月給が上がったのに受け取る年金が減っていない")
    # 帯に入る前は1円も止まらない（平らであること）
    for g in [g for g in GRADES_HIGH if g <= STOP_BASE_R7 - 100_000]:
        if stopped(100_000, g) != 0:
            raise _checks.TableError(f"総報酬{g:,}円で止まっている。41万円までは止まらないはず")
    # 止まる額は基本月額を超えない
    if stopped(100_000, 650_000) > 100_000:
        raise _checks.TableError("基本月額より多く止まっている")
    # 全額止まるさかい目は 停止調整額 + 基本月額
    _checks.rounding(full_stop_grade(100_000), 610_000,
                     "基本月額10万で全額止まる総報酬")
    _checks.rounding(stopped(100_000, 610_000), 100_000,
                     "全額止まるさかい目ちょうどの停止額")
    # 賞与は12で割って月に載る。年120万の賞与は月10万と同じ
    _checks.rounding(stopped(100_000, 380_000, 1_200_000),
                     stopped(100_000, 480_000), "年120万の賞与と月給10万上げ")
    # 調整額が1万円上がると、止まる額は5千円減る
    _checks.rounding(stopped(100_000, 450_000, 0, STOP_BASE_R6)
                     - stopped(100_000, 450_000, 0, STOP_BASE_R7),
                     5_000, "調整額50万→51万で止まる額の差")
    # 帯の幅は基本月額の2倍
    for kihon in (50_000, 100_000, 180_000):
        width = full_stop_grade(kihon) - (STOP_BASE_R7 - kihon)
        _checks.rounding(width, kihon * 2, f"基本月額{kihon}円の帯の幅")
    # 表の行が等級で重複していないこと
    _checks.unique_by(grade_grid(100_000), lambda r: r["標準報酬月額"],
                      "等級べつの表")

    # 4. 標準賞与額（1000円未満の切り捨てと、1回あたり150万円の上限）
    _checks.rounding(standard_bonus(999), 0, "賞与999円の標準賞与額")
    _checks.rounding(standard_bonus(150_999), 150_000, "1000円未満の切り捨て")
    _checks.rounding(standard_bonus(1_500_000), BONUS_CAP_PER_TIME, "上限ちょうど")
    _checks.rounding(standard_bonus(3_000_000), BONUS_CAP_PER_TIME, "上限を超えた賞与")
    # 年300万を1回で受け取ると半分しか載らない。2回に分ければ全額載る
    _checks.rounding(counted_annual_bonus(3_000_000, 1), 1_500_000,
                     "年300万を1回で受け取ったときに載る額")
    _checks.rounding(counted_annual_bonus(3_000_000, 2), 3_000_000,
                     "年300万を2回に分けたときに載る額")
    # 分けたあとは、これ以上分けても1円も変わらない（上限に当たらなくなるから）
    for t in (3, 4, 6, 12):
        if counted_annual_bonus(3_000_000, t) != counted_annual_bonus(3_000_000, 2):
            raise _checks.TableError(
                f"年300万を{t}回に分けた載る額が、2回のときと違う。"
                "上限に当たらなくなった後は回数で変わらないはず")
    # 回数を増やすほど載る額は減らない（＝止まる額は減らない）
    _checks.increases_with(lambda t: counted_annual_bonus(3_000_000, t),
                           [1, 2], "分けるほど載る額が増えていない")

    # 5. 納付月数（基礎年金は止まらない側）
    _checks.rounding(kiso_monthly(FULL_MONTHS), basic_monthly(),
                     "480か月の基礎年金は満額")
    _checks.rounding(kiso_monthly(240) * 2, basic_monthly(),
                     "240か月は満額のちょうど半分")
    _checks.rounding(kiso_monthly(600), basic_monthly(),
                     "480か月を超えても満額どまり")
    # 納付月数が短いほど、同じ停止額が手元に占める割合は大きい
    _checks.decreases_with(
        lambda m: stopped(100_000, 500_000) / (100_000 + kiso_monthly(m)),
        [120, 180, 240, 300, 360, 420, FULL_MONTHS],
        "納付月数が伸びたのに、手元が減る割合が下がっていない")
    # 停止額そのものは納付月数で1円も変わらない（基礎年金は止まらない）
    rows_m = months_grid(100_000)
    if len({r["止まる年金_月"] for r in rows_m}) != 1:
        raise _checks.TableError("納付月数で止まる額が変わっている。基礎年金は止まらないはず")

    # 6. 給与に対する目減り率は単調でない（全額止まるさかい目に山がある）
    rate = {r["標準報酬月額"]: r["給与に対する目減り率"] for r in average_rate_grid(100_000)}
    if rate[650_000] >= rate[620_000]:
        raise _checks.TableError(
            "給与に対する目減り率が最後まで上がり続けている。"
            "止まる額は基本月額で頭打ちなので、そこから上は薄まって下がるはず")
    peak = max(rate, key=lambda g: rate[g])
    if peak != 620_000:
        raise _checks.TableError(f"目減り率の山が{peak:,}円にある。62万円のはず")
    # 限界（50%）と平均は別物。平均はどこでも50%に届かない
    for g, r in rate.items():
        if r >= STOP_SHARE:
            raise _checks.TableError(f"総報酬{g:,}円で平均の目減り率が50%以上になっている")
    # 1等級あたりの手元の増えを、割り忘れずに出していること
    _checks.assumption_values(ASSUMPTIONS, name="zaishoku")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過\n")

    KIHON = 100_000   # 老齢厚生年金の報酬比例部分 月10万円（年120万円）

    print("=== 月給を1万円上げても、手元は5千円しか増えない帯がある ===")
    print(f"  前提: 老齢厚生年金の報酬比例部分は月{KIHON:,}円（年{KIHON*12:,}円）/ "
          f"賞与なし / 支給停止調整額は令和7年度の{STOP_BASE_R7:,}円")
    for row in marginal_grid(KIHON):
        print(f"  {row['等級を上げる']:>22s}  月給+{row['月給の増え']:>6,d}円  "
              f"年金{-row['年金の減り']:>+7,d}円  手元+{row['手元の増え']:>6,d}円  "
              f"残る割合 {row['残る割合']:.1%}")

    print("\n=== 標準報酬月額ごとに、止まる年金と手元に残る合計 ===")
    print(f"  前提: 報酬比例部分は月{KIHON:,}円 / 老齢基礎年金は満額の月"
          f"{basic_monthly():,}円（年{BASIC_ANNUAL:,}円）。**基礎年金は止まりません**")
    for row in grade_grid(KIHON):
        print(f"  標準報酬{row['標準報酬月額']:>7,d}円  止まる{row['止まる年金_月']:>7,d}円/月"
              f"（年{row['止まる年金_年']:>8,d}円）  受け取る厚生年金"
              f"{row['受け取る厚生年金_月']:>7,d}円  年金の手元{row['年金の手元_月']:>7,d}円  "
              f"給与と合わせて{row['給与と年金の合計_月']:>8,d}円")

    print("\n=== 賞与にすれば年金は止まらない、は誤り（12で割って毎月に載る）===")
    print(f"  前提: 標準報酬月額38万円 / 報酬比例部分は月{KIHON:,}円 / "
          f"支給停止調整額{STOP_BASE_R7:,}円")
    for row in bonus_grid(KIHON):
        print(f"  年間賞与{row['年間の賞与']:>9,d}円  月に載る{row['月に載る額']:>7,d}円  "
              f"総報酬月額相当額{row['総報酬月額相当額']:>7,d}円  "
              f"止まる{row['止まる年金_月']:>6,d}円/月（年{row['止まる年金_年']:>7,d}円）  "
              f"賞与100円あたり年{row['賞与100円あたり止まる額_年']:>3,d}円が止まる")

    print("\n=== 年金が多い人ほど、止まりはじめてから全額止まるまでが遠い ===")
    print(f"  前提: 賞与なし / 支給停止調整額は令和7年度の{STOP_BASE_R7:,}円")
    for row in threshold_grid():
        print(f"  基本月額{row['基本月額']:>7,d}円（年{row['年金の年額']:>9,d}円）  "
              f"止まりはじめる総報酬{row['止まりはじめる総報酬']:>7,d}円  "
              f"全額止まる総報酬{row['全額止まる総報酬']:>7,d}円  "
              f"帯の幅{row['帯の幅']:>7,d}円（基本月額の{row['帯の幅は基本月額の何倍']}倍）")

    print("\n=== 同じ年300万円の賞与でも、1回でもらうと止まる額が年63万円ちがう ===")
    print(f"  前提: 標準報酬月額38万円 / 報酬比例部分は月{KIHON:,}円 / "
          f"年間の賞与300万円 / 標準賞与額は1000円未満を切り捨て、"
          f"**1回あたり{BONUS_CAP_PER_TIME:,}円が上限**（別々の月に受け取るものとします）")
    for row in bonus_times_grid(KIHON):
        print(f"  {row['受け取る回数']:>2d}回に分ける  1回{row['1回あたり']:>9,d}円  "
              f"標準賞与額{row['標準賞与額_1回']:>9,d}円  "
              f"年に載る{row['総報酬に載る年間合計']:>9,d}円"
              f"（切り捨て{row['切り捨てられた額']:>9,d}円）  "
              f"総報酬月額相当額{row['総報酬月額相当額']:>7,d}円  "
              f"止まる{row['止まる年金_月']:>7,d}円/月（年{row['止まる年金_年']:>9,d}円）")

    print("\n=== 納付月数が短い人ほど、同じ停止額が手元の大きな割合を持っていく ===")
    print(f"  前提: 標準報酬月額50万円 / 報酬比例部分は月{KIHON:,}円 / 賞与なし / "
          f"老齢基礎年金は{FULL_MONTHS}か月で満額の年{BASIC_ANNUAL:,}円。"
          f"**基礎年金は止まりません**")
    for row in months_grid(KIHON):
        print(f"  納付{row['納付月数']:>3d}か月（{row['納付年数']:>4.1f}年）  "
              f"基礎年金{row['基礎年金_月']:>6,d}円/月  "
              f"止まらなければ{row['止まらなければ年金の手元_月']:>7,d}円/月  "
              f"止まったあと{row['止まったあと年金の手元_月']:>7,d}円/月  "
              f"止まる{row['止まる年金_月']:>6,d}円/月  "
              f"手元が減る割合 {row['手元が減る割合']:.2%}")

    print("\n=== 限界は50%でも、給与に対する平均の目減り率は16%で頭を打って下がる ===")
    print(f"  前提: 報酬比例部分は月{KIHON:,}円 / 賞与なし / "
          f"支給停止調整額{STOP_BASE_R7:,}円。"
          f"**止まる額は基本月額で頭打ちなので、そこから上は給与で薄まります**")
    for row in average_rate_grid(KIHON):
        print(f"  標準報酬{row['標準報酬月額']:>7,d}円  止まる{row['止まる年金_月']:>7,d}円/月  "
              f"給与に対する目減り率 {row['給与に対する目減り率']:>6.2%}  "
              f"年金に対する目減り率 {row['年金に対する目減り率']:>7.2%}  "
              f"給与と年金の合計{row['給与と年金の合計_月']:>8,d}円")

    print("\n=== 支給停止調整額が1万円上がっても、戻るのは5千円 ===")
    print(f"  前提: 報酬比例部分は月{KIHON:,}円 / 賞与なし / "
          f"令和6年度{STOP_BASE_R6:,}円と令和7年度{STOP_BASE_R7:,}円の比較")
    for row in year_change_grid(KIHON):
        print(f"  標準報酬{row['標準報酬月額']:>7,d}円  "
              f"令和6年度{row['令和6年度_止まる_月']:>7,d}円/月  "
              f"令和7年度{row['令和7年度_止まる_月']:>7,d}円/月  "
              f"差{row['差_月']:>6,d}円/月（年{row['差_年']:>7,d}円）")
