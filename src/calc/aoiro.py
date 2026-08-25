"""青色申告特別控除で、実際に何円の負担が減るのかを計算する。

狙いは「65万円控除の条件」を並べることではない。条件はどこにでもある。
ここで出したいのは **広く出回っている節税額が、どれだけ少なく出ているか** ——
その差を、事業所得ごと・4つの負担ごとに全部表にする。

--------------------------------------------------------------------------
何が違うのか
--------------------------------------------------------------------------
よく見る計算は「控除額 × (所得税率 + 住民税率10パーセント)」。
事業所得300万円の人なら 97,500円 と出る。

実際に減るのは 192,281円 だった。倍近い。差は2つから出ている。

  1. **国民健康保険の所得割**。青色申告特別控除は所得控除ではなく
     所得金額そのものを減らすので、国保の算定基礎（総所得金額等）も下がる。
     所得割率10パーセントなら、それだけで 65,000円 がまるごと乗る
  2. **税率の段またぎ**。65万円を引くと課税所得が下の区分へ落ちることがある。
     事業所得400万円がそれで、所得税ぶんは 88,827円 —— 「税率20パーセント」でも
     「税率10パーセント」でもない額になる

--------------------------------------------------------------------------
逆に、減らないものが1つある
--------------------------------------------------------------------------
**個人事業税は 0円 のまま動かない。**
個人事業税の課税標準では青色申告特別控除を引けないからで（地方税法の個人の事業税の規定）、
事業所得がいくらであっても、この控除で事業税は1円も減らない。
「4つの負担のうち3つが減り、1つは減らない」——ここが4つに分けて出す理由。

--------------------------------------------------------------------------
引ききれない帯
--------------------------------------------------------------------------
控除額は事業所得が限度なので、所得が小さいほど引ける額も小さくなる。
ただし**値打ちがゼロになる境目は、そこではない**。
事業所得 400,000円 までは、引けた額があっても手元は 0円 しか変わらない
（基礎控除で所得税も住民税も国保の所得割も立たないため）。
「65万円まで引ける」と「65万円ぶん得をする」は別のことになる。

--------------------------------------------------------------------------
同じ控除でも、人によって値打ちが違う
--------------------------------------------------------------------------
国民健康保険に入っているかどうかで、同じ65万円控除の値打ちは
事業所得200万円で 1.6620倍、1,500万円で 1.2289倍 ひらく。
会社の社会保険に入ったままの副業なら、国保の所得割は動かないので下の側になる。

そして e-Tax で増える10万円（55万円控除 → 65万円控除）は、
事業所得200万円で 25,105円、1,500万円で 53,693円。

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
租税特別措置法25条の2（青色申告特別控除 650,000円・550,000円・100,000円）、
所得税法86条と地方税法314条の2（基礎控除）、地方税法の個人の事業税の規定（事業主控除）。
所得税の速算表、復興特別所得税、住民税の所得割の標準税率。

国民健康保険の所得割率は自治体で違うので、**制度の値ではなく仮定**として置いた。
その値は ASSUMPTIONS に書いてある。裏の取れない数字は出さない。
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "所得控除は基礎控除だけを置いています。所得税48万円、住民税43万円です",
    "国民健康保険の所得割率は仮定です。医療分・後期高齢者支援分・介護分の合計10パーセントとして置いています",
    "国民健康保険の所得割は、総所得金額等から基礎控除43万円を引いた額に掛けています",
    "国民健康保険の賦課限度額には達していない範囲だけを出しています",
    "個人事業税は第1種事業の5パーセント、事業主控除290万円で計算しています",
    "所得税には復興特別所得税を含めています。所得税額の2.1パーセント上乗せです",
    "住民税の所得割は標準税率の10パーセントです。均等割は青色申告特別控除では動かないので入れていません",
    "社会保険料控除は入れていません。入れると課税所得が下がるので、下の値打ちはその分だけ小さくなります",
]

# ---- 制度の値。**長く動いていないものだけをここに置く** ----------------

#: 青色申告特別控除の3つの額（租税特別措置法25条の2）。
#: 65万円は複式簿記＋期限内申告に加えて **e-Tax 申告か優良な電子帳簿保存**が要る。
DEDUCTIONS: dict[str, int] = {"65万円": 650_000, "55万円": 550_000, "10万円": 100_000}

BASIC_INCOME_TAX = 480_000     # 基礎控除（所得税）
BASIC_RESIDENT = 430_000       # 基礎控除（住民税）
BASIC_KOKUHO = 430_000         # 国民健康保険の基礎控除（所得割の算定）

RECONSTRUCTION_TAX = 0.021     # 復興特別所得税。所得税額に対して
RESIDENT_RATE = 0.10           # 住民税の所得割の標準税率
KOKUHO_RATE = 0.10             # 国民健康保険の所得割率（**仮定**。自治体で違う）

JIGYOZEI_RATE = 0.05           # 個人事業税（第1種事業）
JIGYOZEI_EXEMPTION = 2_900_000  # 事業主控除

#: 所得税の速算表 (区分の上限, 税率, 控除額)。最上段の上限は None。
#: **上限は次の段の始まりで書いてある**（1,949,000 ではなく 1,950,000）。
#: 課税所得は1,000円未満切捨てなので両者のあいだに値は無く、こう書くと
#: 境目で税額が連続します（`_checks.bracket_table` が見ているのはそこ）。
TAX_TABLE: list[tuple[int | None, float, int]] = [
    (1_950_000, 0.05, 0),
    (3_300_000, 0.10, 97_500),
    (6_950_000, 0.20, 427_500),
    (9_000_000, 0.23, 636_000),
    (18_000_000, 0.33, 1_536_000),
    (40_000_000, 0.40, 2_796_000),
    (None, 0.45, 4_796_000),
]

#: 表に並べる事業所得（青色申告特別控除を引く前）。
INCOMES = [2_000_000, 3_000_000, 4_000_000, 5_000_000,
           7_000_000, 10_000_000, 15_000_000]

#: 頭打ちの帯を出すための刻み。**65万円の境目より細かく取ること**。
SMALL_INCOMES = list(range(0, 850_000, 50_000))


def floor_to(value: float, unit: int) -> int:
    """`unit` 円未満を切り捨てる。**税額の丸めは順番が効くので関数にしてある。**"""
    return (int(value) // unit) * unit


def tax_of(base: float) -> float:
    """所得税の速算表を引く（復興特別所得税を含まない）。"""
    for cap, rate, sub in TAX_TABLE:
        if cap is None or base <= cap:
            return max(0.0, base * rate - sub)
    raise ValueError(f"速算表に当たらない: {base}")


def income_tax(taxable: float) -> int:
    """課税所得金額から所得税額（復興特別所得税込み）を出す。"""
    base = floor_to(max(0.0, taxable), 1_000)
    return int(tax_of(base) * (1 + RECONSTRUCTION_TAX))


def resident_tax(taxable: float) -> int:
    """住民税の所得割。**均等割は入れない**（青色申告特別控除では動かない）。"""
    base = floor_to(max(0.0, taxable), 1_000)
    return floor_to(base * RESIDENT_RATE, 100)


def kokuho(total_income: float, rate: float = KOKUHO_RATE) -> int:
    """国民健康保険の所得割。**総所得金額等から基礎控除43万円を引いた額**に掛ける。"""
    return int(max(0.0, total_income - BASIC_KOKUHO) * rate)


def jigyozei(business_income: float) -> int:
    """個人事業税。**青色申告特別控除は引けない**（地方税法の個人の事業税の規定）。

    だから引数は「青色申告特別控除を**引く前**の事業所得」そのものです。
    ここが、この表でいちばん効いている一点になります。
    """
    base = floor_to(max(0.0, business_income - JIGYOZEI_EXEMPTION), 1_000)
    return floor_to(base * JIGYOZEI_RATE, 100)


def applied(business_income: float, deduction: int) -> int:
    """実際に引けた青色申告特別控除。**事業所得が限度**（赤字は作れない）。"""
    return int(min(deduction, max(0.0, business_income)))


def burden(business_income: float, deduction: int = 0,
           rate: float = KOKUHO_RATE) -> dict:
    """その事業所得のとき、4つの負担がそれぞれいくらか。"""
    used = applied(business_income, deduction)
    after = business_income - used
    return {
        "applied": used,
        "income_tax": income_tax(after - BASIC_INCOME_TAX),
        "resident_tax": resident_tax(after - BASIC_RESIDENT),
        "kokuho": kokuho(after, rate),
        "jigyozei": jigyozei(business_income),   # **青色控除を引く前で決まる**
    }


def saving(business_income: float, deduction: int = DEDUCTIONS["65万円"],
           rate: float = KOKUHO_RATE, base_deduction: int = 0) -> dict:
    """`base_deduction` から `deduction` に変えたとき、何円ぶん軽くなるか。"""
    lo = burden(business_income, base_deduction, rate)
    hi = burden(business_income, deduction, rate)
    parts = {k: lo[k] - hi[k] for k in ("income_tax", "resident_tax",
                                        "kokuho", "jigyozei")}
    total = sum(parts.values())
    used = hi["applied"] - lo["applied"]
    return {
        "income": int(business_income),
        "applied": hi["applied"],
        "step": used,
        **parts,
        "total": total,
        # よく見る計算 ＝ 控除額 ×（所得税率＋住民税10パーセント）
        "naive": naive_saving(business_income, deduction, base_deduction),
        "effective_rate": (total / used) if used else 0.0,
    }


def marginal_rate(business_income: float, deduction: int) -> float:
    """その控除を引いた**後**の課税所得に当たる所得税の税率。"""
    taxable = floor_to(max(0.0, business_income - applied(business_income, deduction)
                           - BASIC_INCOME_TAX), 1_000)
    for cap, rate, _ in TAX_TABLE:
        if cap is None or taxable <= cap:
            return rate
    raise ValueError(f"速算表に当たらない: {taxable}")


def naive_saving(business_income: float, deduction: int,
                 base_deduction: int = 0) -> int:
    """**よく出回っている計算**: 控除額 ×（所得税率 ＋ 住民税10パーセント）。

    国民健康保険にも個人事業税にも触れない。ここが差の出どころです。
    """
    used = applied(business_income, deduction) - applied(business_income, base_deduction)
    rate = marginal_rate(business_income, deduction)
    return int(used * (rate + RESIDENT_RATE))


# ---------------------------------------------------------------- 表

def grid(deduction: int = DEDUCTIONS["65万円"], base_deduction: int = 0,
         rate: float = KOKUHO_RATE, incomes: list[int] | None = None) -> list[dict]:
    return [saving(i, deduction, rate, base_deduction)
            for i in (incomes or INCOMES)]


def ceiling_grid(deduction: int = DEDUCTIONS["65万円"]) -> list[dict]:
    """事業所得が控除額に届かない帯。**引けた額が頭打ちになる形を出す。**"""
    return [saving(i, deduction) for i in SMALL_INCOMES]


def kokuho_gap(deduction: int = DEDUCTIONS["65万円"]) -> list[dict]:
    """国保に入っている人と、入っていない人（社保の副業など）の差。"""
    out = []
    for i in INCOMES:
        with_k = saving(i, deduction, KOKUHO_RATE)
        without = saving(i, deduction, 0.0)
        out.append({
            "income": i,
            "with_kokuho": with_k["total"],
            "without_kokuho": without["total"],
            "gap": with_k["total"] - without["total"],
            "times": with_k["total"] / without["total"] if without["total"] else 0.0,
        })
    return out


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    _checks.statutory(DEDUCTIONS["65万円"], 650_000, "青色申告特別控除の最高額",
                      source="租税特別措置法25条の2")
    _checks.statutory(DEDUCTIONS["55万円"], 550_000, "複式簿記だけのときの控除額",
                      source="租税特別措置法25条の2")
    _checks.statutory(DEDUCTIONS["10万円"], 100_000, "簡易な記帳のときの控除額",
                      source="租税特別措置法25条の2")
    _checks.statutory(JIGYOZEI_EXEMPTION, 2_900_000, "個人事業税の事業主控除",
                      source="地方税法・個人の事業税の事業主控除")
    _checks.statutory(BASIC_INCOME_TAX, 480_000, "基礎控除（所得税）",
                      source="所得税法86条")
    _checks.statutory(BASIC_RESIDENT, 430_000, "基礎控除（住民税）",
                      source="地方税法314条の2")
    for name, value in (("住民税の所得割", RESIDENT_RATE),
                        ("国民健康保険の所得割率", KOKUHO_RATE),
                        ("個人事業税", JIGYOZEI_RATE),
                        ("復興特別所得税", RECONSTRUCTION_TAX)):
        _checks.ratio(value, name)

    _checks.bracket_table(TAX_TABLE, tax_of, name="所得税の速算表")
    _checks.ascending([DEDUCTIONS["10万円"], DEDUCTIONS["55万円"],
                       DEDUCTIONS["65万円"]], "青色申告特別控除の3つの額",
                      strict=True)

    # **この計算の主題そのもの。** 汎用の検査では守れない。
    # 1. 個人事業税は、青色申告特別控除では1円も減らない
    for i in (3_000_000, 5_000_000, 10_000_000):
        if saving(i, DEDUCTIONS["65万円"])["jigyozei"] != 0:
            raise _checks.TableError(
                f"事業所得 {i:,}円 で個人事業税が動いた（青色申告特別控除は事業税に効かない）")
        _checks.greater(jigyozei(i), 0, "事業主控除を超える所得で個人事業税がゼロでない")

    # 2. 所得が増えれば（税率が上がるので）値打ちも増える
    _checks.never_decreases(lambda x: saving(x, DEDUCTIONS["65万円"])["total"],
                            INCOMES, "事業所得が増えたのに65万円控除の値打ちが減った")

    # 3. よく見る計算は、必ず小さく出る（国保のぶんを落としているので）
    for i in INCOMES:
        r = saving(i, DEDUCTIONS["65万円"])
        _checks.greater(r["total"], r["naive"],
                        f"事業所得 {i:,}円 で、実際の値打ちがよく見る計算以下")

    # 4. 引けるのは事業所得まで。頭打ちの上では引けた額が増えない
    if applied(400_000, DEDUCTIONS["65万円"]) != 400_000:
        raise _checks.TableError("事業所得40万円で65万円を引いてしまっている")
    if applied(2_000_000, DEDUCTIONS["65万円"]) != DEDUCTIONS["65万円"]:
        raise _checks.TableError("事業所得200万円で65万円を引けていない")

    # 5. 控除が大きいほど軽くなる
    _checks.increases_with(
        lambda d: saving(5_000_000, d)["total"],
        [DEDUCTIONS["10万円"], DEDUCTIONS["55万円"], DEDUCTIONS["65万円"]],
        "控除額を上げたのに値打ちが増えていない")

    _checks.unique_by(grid(), lambda r: r["income"], "事業所得ごとの表")
    _checks.assumption_values(ASSUMPTIONS, name="aoiro")


def _row(r: dict) -> str:
    return (f"{r['income']:>11,d}円 {r['step']:>8,d}円 {r['income_tax']:>9,d}円 "
            f"{r['resident_tax']:>9,d}円 {r['kokuho']:>9,d}円 {r['jigyozei']:>7,d}円 "
            f"{r['total']:>9,d}円 {r['naive']:>9,d}円 {r['effective_rate']:>8.2%}")


HEAD = (f"{'事業所得':>12s} {'効いた控除':>8s} {'所得税':>10s} {'住民税':>10s} "
        f"{'国保':>10s} {'事業税':>8s} {'合計':>10s} {'よく見る計算':>10s} {'実効率':>9s}")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 65万円の青色申告特別控除は、実際いくらの負担を減らすか ===")
    print(HEAD)
    for row in grid():
        print(_row(row))

    print("\n=== e-Taxで増える10万円（55万円控除→65万円控除）は、いくらか ===")
    print(HEAD)
    for row in grid(DEDUCTIONS["65万円"], DEDUCTIONS["55万円"]):
        print(_row(row))

    print("\n=== 事業所得が65万円に届かない帯では、どこで頭打ちになるか ===")
    print(HEAD)
    for row in ceiling_grid():
        print(_row(row))

    print("\n=== 複式簿記の値段（10万円控除と65万円控除の差）===")
    print(HEAD)
    for row in grid(DEDUCTIONS["65万円"], DEDUCTIONS["10万円"]):
        print(_row(row))

    print("\n=== 国保か社保かで、同じ65万円控除の値打ちは何倍ひらくか ===")
    print(f"{'事業所得':>12s} {'国保あり':>10s} {'国保なし':>10s} {'差':>10s} {'倍率':>8s}")
    for row in kokuho_gap():
        print(f"{row['income']:>11,d}円 {row['with_kokuho']:>9,d}円 "
              f"{row['without_kokuho']:>9,d}円 {row['gap']:>9,d}円 {row['times']:>8.4f}倍")
