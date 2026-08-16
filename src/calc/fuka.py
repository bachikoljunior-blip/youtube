"""付加年金 —— 月400円が、何年で元を取り、何を犠牲にしているのかを計算する。

狙いは「2年で元が取れます」を紹介することではない。それはどこにでもある。
ここで出したいのは、その2年の裏にある **3つの、ほとんど書かれていない数字** である。

--------------------------------------------------------------------------
1. 「2年で元が取れる」は、受け取りはじめてからの2年である
--------------------------------------------------------------------------
付加保険料は月400円、付加年金は年額200円に納付月数を掛けた額。
だから納めた総額の半分が毎年戻る。何か月納めても、何歳から納めても、ちょうど2年。
納付月数が約分で消えるので、**人によらず2年**になる。

ここまではよく紹介される。書かれていないのは、**繰上げ・繰下げで
この2年が動く**ことである。付加年金は老齢基礎年金と一緒に繰り上がり、繰り下がり、
同じ率が掛かる。60歳に繰り上げれば年額は0.76倍になり、回収には2年8か月ほどかかる。
75歳に繰り下げれば1.84倍になり、1年1か月で終わる。

そして**元が取れる年齢**で見ると、順番がひっくり返る。繰り上げた人は
62歳台で回収を終え、繰り下げた人は76歳まで待つ。増額率が高いほうが、
元を取り終えるのは遅い。付加年金だけを見るなら、**繰上げが最も早く元を取る。**

--------------------------------------------------------------------------
2. 400円を払うために、iDeCoの枠を1,000円捨てている
--------------------------------------------------------------------------
自営業などの第1号被保険者のiDeCoの上限は月6万8千円だが、これは
**国民年金基金の掛金と付加保険料を合わせた上限**である。掛金は千円単位なので、
付加保険料400円を払うと、iDeCoに出せるのは6万7千円までになる。

つまり **400円のために1,000円ぶんの枠が消える。** 差の600円は、どこにも行かない。
これは制度の紹介ではまず出てこない。ここでは、その捨てた600円ぶんの
所得控除を税率べつに金額にして、付加年金の年額と並べる。

--------------------------------------------------------------------------
3. 200円は増えない
--------------------------------------------------------------------------
老齢基礎年金は毎年度改定されるが、**付加年金の200円は定額で、物価にも賃金にも
連動しない。** 20歳で納めはじめた人が受け取るのは45年後で、そのあいだ物価が動いても
200円のままである。「2年で元が取れる」という話に、この目減りは入っていない。

ここでは、受け取りはじめるまでの年数と物価の上がり方から、
**実質でいくらになるか**を出す。これも表としてはどこにも無い。
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "付加保険料は月400円、付加年金は年額200円に付加保険料の納付月数を掛けた額で計算しています。"
    "どちらも国民年金法が定めた定額で、物価や賃金では改定されません",
    "付加年金を納められるのは国民年金の第1号被保険者と任意加入被保険者です。"
    "国民年金基金に加入している人は納められません",
    "付加年金は老齢基礎年金と一緒に繰上げ・繰下げされ、同じ率が掛かります。"
    "繰下げは1か月あたり0.7パーセント増、繰上げは1か月あたり0.4パーセント減です",
    "繰上げの0.4パーセントは昭和37年4月2日以降に生まれた人の率です",
    "国民年金保険料は令和7年度の月1万7510円で計算しています。令和6年度は1万6980円で、"
    "この額は毎年度改定されます",
    "第1号被保険者のiDeCoの上限は月6万8千円で、国民年金基金の掛金と付加保険料を"
    "合わせた額です。掛金は千円単位なので、付加保険料400円を払うと"
    "iDeCoに出せるのは月6万7千円までになります",
    "税率は所得税と住民税を合わせた率として置いています。住民税は10パーセントで固定し、"
    "所得税は5パーセントから45パーセントまでを見ています",
    "物価の上がり方は制度の値ではなく、この計算での仮定です。"
    "年0パーセント、1パーセント、2パーセントの3通りを置いています",
    "付加保険料そのものは全額が社会保険料控除の対象です。ここではその節税分も出しています",
    "受け取る側の税金は入れていません。付加年金の年額は額面です",
]

# ---- 制度の値 ------------------------------------------------------------
FUKA_PREMIUM = 400          # 付加保険料 月額（国民年金法第87条の2）
FUKA_PER_MONTH = 200        # 付加年金 年額に効く 1か月あたりの額（同法第44条）

KOKUMIN_PREMIUM_R7 = 17_510  # 国民年金保険料 令和7年度 月額
KOKUMIN_PREMIUM_R6 = 16_980  # 令和6年度 月額

IDECO_CAP_1GO = 68_000      # 第1号被保険者のiDeCo上限（付加保険料・基金と合算）
IDECO_UNIT = 1_000          # iDeCoの掛金の単位
# 付加保険料を払ったときに出せるiDeCoの額（千円単位で切り下げ）
IDECO_WITH_FUKA = ((IDECO_CAP_1GO - FUKA_PREMIUM) // IDECO_UNIT) * IDECO_UNIT

RATE_UP_PER_MONTH = 0.007   # 繰下げ
RATE_DOWN_PER_MONTH = 0.004  # 繰上げ（昭和37年4月2日以降生まれ）
BASE_AGE = 65
MAX_DEFER_AGE = 75
MIN_ADVANCE_AGE = 60

RESIDENT_TAX_RATE = 0.10    # 住民税の所得割（標準税率）
INCOME_TAX_RATES = [0.05, 0.10, 0.20, 0.23, 0.33, 0.40, 0.45]


def rate_for(months_from_65: int) -> float:
    """65歳を1.0としたときの倍率。繰上げは負の月数で渡す。"""
    if months_from_65 >= 0:
        return 1.0 + RATE_UP_PER_MONTH * months_from_65
    return 1.0 + RATE_DOWN_PER_MONTH * months_from_65


def paid_total(months: int) -> int:
    """付加保険料の総額（円）。"""
    return FUKA_PREMIUM * months


def annual(months: int, months_from_65: int = 0) -> float:
    """付加年金の年額（円）。繰上げ・繰下げの率が掛かる。"""
    return FUKA_PER_MONTH * months * rate_for(months_from_65)


def payback_months(months: int, months_from_65: int = 0) -> float:
    """受け取りはじめてから元を取るまでの月数。

    納付月数が約分で消えるので、**何か月納めたかによらない**。
        総額 ÷ 年額 = 400×n ÷ (200×n×倍率) = 2 ÷ 倍率（年）
    """
    return paid_total(months) / annual(months, months_from_65) * 12


def payback_age(months_from_65: int = 0) -> tuple[int, int]:
    """元を取り終える年齢（歳, か月）。開始年齢に回収期間を足す。"""
    start = BASE_AGE * 12 + months_from_65
    total = start + payback_months(480, months_from_65)
    whole = int(total // 1)
    return int(whole // 12), int(round(total - (whole // 12) * 12))


def months_grid() -> list[dict]:
    """納付月数ごとに、総額と年額と回収期間を出す。**回収期間は動かない。**"""
    rows = []
    for years in (5, 10, 20, 30, 40):
        m = years * 12
        rows.append({
            "納付年数": years,
            "納付月数": m,
            "払った総額": paid_total(m),
            "付加年金の年額": round(annual(m)),
            "回収_月": round(payback_months(m)),
            "10年受け取った合計": round(annual(m) * 10),
            "差引": round(annual(m) * 10 - paid_total(m)),
        })
    return rows


def defer_grid(months: int = 480) -> list[dict]:
    """繰上げ・繰下げごとに、年額・回収期間・元を取る年齢を出す。

    **増額率が高いほど、元を取り終えるのは遅い。**
    """
    rows = []
    for age in range(MIN_ADVANCE_AGE, MAX_DEFER_AGE + 1):
        m65 = (age - BASE_AGE) * 12
        r = rate_for(m65)
        pb = payback_months(months, m65)
        y, mo = payback_age(m65)
        rows.append({
            "受給開始": age,
            "倍率": round(r, 3),
            "年額": round(annual(months, m65)),
            "回収_月": round(pb),
            "回収_年月": f"{int(pb // 12)}年{int(round(pb % 12))}か月",
            "元を取る年齢": f"{y}歳{mo}か月",
            "元を取る年齢_月通算": y * 12 + mo,
        })
    return rows


def ideco_cost_grid() -> list[dict]:
    """付加保険料を払うと消えるiDeCoの枠を、税率べつに金額にする。

    付加保険料は400円だが、iDeCoは千円単位なので枠は1,000円減る。
    **差の600円は、払ってもいないのに控除の対象から外れる。**
    """
    lost_room = IDECO_CAP_1GO - IDECO_WITH_FUKA          # 1,000円
    dead = lost_room - FUKA_PREMIUM                      # 600円
    rows = []
    for it in INCOME_TAX_RATES:
        total = it + RESIDENT_TAX_RATE
        rows.append({
            "所得税率": it,
            "合計税率": round(total, 2),
            "消える枠_月": lost_room,
            "うち払っていない_月": dead,
            "失う節税_年": round(dead * 12 * total),
            "付加保険料の節税_年": round(FUKA_PREMIUM * 12 * total),
            "差引の節税_年": round((FUKA_PREMIUM - dead) * 12 * total),
        })
    return rows


def ideco_breakeven_grid(months: int = 480) -> list[dict]:
    """捨てた600円の枠を40年ぶん積み上げ、付加年金の何年ぶんに当たるかを出す。

    **納めているあいだの損は一度きり、付加年金は死ぬまで**なので、
    比べるなら「40年ぶんの損が、付加年金の何年ぶんか」で見るのが正しい。
    """
    dead = IDECO_CAP_1GO - IDECO_WITH_FUKA - FUKA_PREMIUM
    fuka_annual = annual(months)
    rows = []
    for it in INCOME_TAX_RATES:
        total = it + RESIDENT_TAX_RATE
        lost_life = dead * months * total          # 納付期間ぜんぶの損
        rows.append({
            "所得税率": it,
            "合計税率": round(total, 2),
            "捨てた控除_総額": dead * months,
            "失う税_総額": round(lost_life),
            "付加年金_年": round(fuka_annual),
            "付加年金の何年ぶんか": round(lost_life / fuka_annual, 2),
            "取り返す月数": round(lost_life / (fuka_annual / 12), 1) if fuka_annual else 0,
        })
    return rows


def inflation_grid(months: int = 480, start_age: int = 20) -> list[dict]:
    """受け取りはじめる時点で、200円が実質いくらになっているか。

    **付加年金は定額で改定されない。**納めはじめから受給までの年数だけ目減りする。
    """
    years_to_65 = BASE_AGE - start_age
    base = annual(months)
    rows = []
    for infl in (0.00, 0.01, 0.02):
        factor = (1 + infl) ** years_to_65
        rows.append({
            "物価の上がり方": infl,
            "受給までの年数": years_to_65,
            "額面の年額": round(base),
            "実質の年額": round(base / factor),
            "目減り": round(base - base / factor),
            "実質の1か月あたり": round(FUKA_PER_MONTH / factor, 1),
        })
    return rows


def premium_share_grid() -> list[dict]:
    """国民年金保険料に対して、付加保険料はどれだけの上乗せか。"""
    rows = []
    for label, base in (("令和6年度", KOKUMIN_PREMIUM_R6),
                        ("令和7年度", KOKUMIN_PREMIUM_R7)):
        rows.append({
            "年度": label,
            "国民年金保険料_月": base,
            "付加を足した_月": base + FUKA_PREMIUM,
            "上乗せの割合": round(FUKA_PREMIUM / base, 4),
            "40年の総額_付加なし": base * 480,
            "40年の総額_付加あり": (base + FUKA_PREMIUM) * 480,
        })
    return rows


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(FUKA_PREMIUM, 400, "付加保険料の月額",
                      source="国民年金法第87条の2")
    _checks.statutory(FUKA_PER_MONTH, 200, "付加年金の1か月あたりの額",
                      source="国民年金法第44条")
    _checks.statutory(KOKUMIN_PREMIUM_R7, 17_510, "国民年金保険料（令和7年度）",
                      source="令和7年度国民年金保険料")
    _checks.statutory(KOKUMIN_PREMIUM_R6, 16_980, "国民年金保険料（令和6年度）",
                      source="令和6年度国民年金保険料")
    _checks.statutory(IDECO_CAP_1GO, 68_000, "第1号被保険者のiDeCo上限",
                      source="確定拠出年金法施行令第36条")
    _checks.statutory(RATE_UP_PER_MONTH, 0.007, "繰下げの増額率",
                      source="国民年金法第28条")
    _checks.statutory(RATE_DOWN_PER_MONTH, 0.004, "繰上げの減額率",
                      source="国民年金法施行令第12条")
    _checks.ratio(RATE_UP_PER_MONTH, "繰下げの増額率")
    _checks.ratio(RESIDENT_TAX_RATE, "住民税の所得割")
    for r in INCOME_TAX_RATES:
        _checks.ratio(r, "所得税率")
    _checks.ascending(INCOME_TAX_RATES, "所得税率", strict=True)

    # 2. 千円単位の切り下げが効いていること（**この計算の要**）
    _checks.rounding(IDECO_WITH_FUKA, 67_000, "付加保険料を払ったときのiDeCo上限")
    if IDECO_CAP_1GO - IDECO_WITH_FUKA <= FUKA_PREMIUM:
        raise _checks.TableError(
            "消える枠が付加保険料以下になっている。千円単位の切り下げが効いていない")

    # 3. 計算の向き（**この計算の主題そのもの**）
    # 65歳開始なら、何か月納めても回収はちょうど2年
    for m in (60, 120, 240, 480):
        _checks.rounding(payback_months(m), 24, f"{m}か月納めたときの回収期間")
    # 繰り下げるほど年額は増える
    _checks.increases_with(lambda a: annual(480, (a - BASE_AGE) * 12),
                           [60, 65, 70, 75],
                           "繰り下げたのに年額が増えていない")
    # 繰り下げるほど回収期間は短い
    _checks.decreases_with(lambda a: payback_months(480, (a - BASE_AGE) * 12),
                           [60, 65, 70, 75],
                           "繰り下げたのに回収期間が短くなっていない")
    # だが元を取り終える年齢は、繰り下げるほど遅い
    _checks.increases_with(
        lambda a: (lambda t: t[0] * 12 + t[1])(payback_age((a - BASE_AGE) * 12)),
        [60, 65, 70, 75],
        "繰り下げたのに元を取る年齢が遅くなっていない")
    # 40年納めた場合の年額（200円 × 480か月）
    _checks.rounding(annual(480), 96_000, "40年納めたときの付加年金の年額")
    _checks.rounding(paid_total(480), 192_000, "40年納めたときの総額")
    # 物価が上がるほど実質は減る
    _checks.decreases_with(
        lambda i: annual(480) / (1 + i) ** (BASE_AGE - 20),
        [0.00, 0.01, 0.02], "物価が上がったのに実質が減っていない")
    # 表の行が重複していないこと
    _checks.unique_by(defer_grid(), lambda r: r["受給開始"], "繰上げ繰下げの表")
    _checks.unique_by(months_grid(), lambda r: r["納付年数"], "納付年数べつの表")
    _checks.assumption_values(ASSUMPTIONS, name="fuka")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過\n")

    print("=== 付加年金の「2年で元が取れる」は、納付月数によらない ===")
    print(f"  前提: 付加保険料は月{FUKA_PREMIUM}円 / 付加年金は年額"
          f"{FUKA_PER_MONTH}円 × 納付月数 / 65歳から受け取る場合")
    for row in months_grid():
        print(f"  {row['納付年数']:>2d}年（{row['納付月数']:>3d}か月）  "
              f"払った総額{row['払った総額']:>8,d}円  "
              f"年額{row['付加年金の年額']:>7,d}円  "
              f"回収{row['回収_月']:>3d}か月  "
              f"10年で{row['10年受け取った合計']:>8,d}円（差引{row['差引']:>+8,d}円）")

    print("\n=== 繰り下げるほど元を取り終えるのは遅い（付加年金だけで見た場合）===")
    print(f"  前提: 40年（480か月）納めた場合 / 年額{annual(480):,.0f}円が基準 / "
          f"繰下げは1か月0.7パーセント増、繰上げは1か月0.4パーセント減")
    for row in defer_grid():
        print(f"  {row['受給開始']:>2d}歳から  倍率{row['倍率']:.3f}  "
              f"年額{row['年額']:>7,d}円  回収{row['回収_年月']:>8s}  "
              f"元を取るのは{row['元を取る年齢']:>9s}")

    print("\n=== 400円を払うために、iDeCoの枠が1,000円消える ===")
    print(f"  前提: 第1号被保険者のiDeCo上限は月{IDECO_CAP_1GO:,}円（付加保険料と合算）/ "
          f"掛金は{IDECO_UNIT:,}円単位なので付加を払うと月{IDECO_WITH_FUKA:,}円まで / "
          f"住民税は{RESIDENT_TAX_RATE:.0%}")
    for row in ideco_cost_grid():
        print(f"  所得税率{row['所得税率']:>5.0%}（合計{row['合計税率']:>5.0%}）  "
              f"消える枠{row['消える枠_月']:,}円/月  "
              f"うち払っていない{row['うち払っていない_月']:>3,d}円  "
              f"失う節税 年{row['失う節税_年']:>5,d}円  "
              f"付加の節税 年{row['付加保険料の節税_年']:>5,d}円  "
              f"差引 年{row['差引の節税_年']:>+5,d}円")

    print("\n=== 40年ぶん枠を捨てた損は、最高税率でも付加年金1年8か月ぶん ===")
    print(f"  前提: 40年納めた場合の年額{annual(480):,.0f}円 / "
          f"捨てた枠は月{IDECO_CAP_1GO - IDECO_WITH_FUKA - FUKA_PREMIUM}円ぶん × 480か月 / "
          f"損は納めているあいだの一度きり、付加年金は死ぬまで")
    for row in ideco_breakeven_grid():
        print(f"  所得税率{row['所得税率']:>5.0%}（合計{row['合計税率']:>5.0%}）  "
              f"捨てた控除{row['捨てた控除_総額']:>7,d}円  "
              f"失う税{row['失う税_総額']:>7,d}円  "
              f"付加年金 年{row['付加年金_年']:>6,d}円  "
              f"付加年金の{row['付加年金の何年ぶんか']:>4.2f}年ぶん"
              f"（{row['取り返す月数']:>4.1f}か月で取り返す）")

    print("\n=== 200円は改定されない（20歳から納めて65歳で受け取るまでの目減り）===")
    print(f"  前提: 20歳から40年納め、65歳から受け取る / 額面の年額"
          f"{annual(480):,.0f}円 / 物価の上がり方は仮定（0・1・2パーセント）")
    for row in inflation_grid():
        print(f"  物価{row['物価の上がり方']:>5.0%}  {row['受給までの年数']}年後  "
              f"額面{row['額面の年額']:>7,d}円  実質{row['実質の年額']:>7,d}円  "
              f"目減り{row['目減り']:>7,d}円  "
              f"1か月ぶんは実質{row['実質の1か月あたり']:>5.1f}円")

    print("\n=== 国民年金保険料に対して、付加保険料は2パーセント台の上乗せ ===")
    for row in premium_share_grid():
        print(f"  {row['年度']}  保険料{row['国民年金保険料_月']:>6,d}円/月  "
              f"付加を足すと{row['付加を足した_月']:>6,d}円/月  "
              f"上乗せ{row['上乗せの割合']:>6.2%}  "
              f"40年の総額 {row['40年の総額_付加なし']:>10,d}円 → "
              f"{row['40年の総額_付加あり']:>10,d}円")
