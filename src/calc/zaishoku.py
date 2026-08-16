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


def basic_monthly() -> int:
    """老齢基礎年金の月額（満額・円）。**止まらない側**。"""
    return round(BASIC_ANNUAL / 12)


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

    print("\n=== 支給停止調整額が1万円上がっても、戻るのは5千円 ===")
    print(f"  前提: 報酬比例部分は月{KIHON:,}円 / 賞与なし / "
          f"令和6年度{STOP_BASE_R6:,}円と令和7年度{STOP_BASE_R7:,}円の比較")
    for row in year_change_grid(KIHON):
        print(f"  標準報酬{row['標準報酬月額']:>7,d}円  "
              f"令和6年度{row['令和6年度_止まる_月']:>7,d}円/月  "
              f"令和7年度{row['令和7年度_止まる_月']:>7,d}円/月  "
              f"差{row['差_月']:>6,d}円/月（年{row['差_年']:>7,d}円）")
