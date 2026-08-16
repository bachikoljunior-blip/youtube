"""ふるさと納税の控除上限額を、目安表ではなく式から出す。

狙いは目安表を載せ直すことではない。目安表はどこにでもある。
ここで出したいのは **目安表が、実際の上限からどれだけ外れるか** ——
そのずれを、年収べつ・社会保険料べつに全部出す。

--------------------------------------------------------------------------
なぜ目安表は外れるのか
--------------------------------------------------------------------------
広く配られている目安表は「年収」と「家族構成」の2つだけで引く。
ところが上限額を決めるのは **住民税の所得割額** であって、年収ではない。

年収から所得割額に落ちるまでに、少なくとも次が挟まる。

  給与所得控除 → 社会保険料控除 → 各種所得控除 → 課税所得 → 所得割額

このうち **社会保険料控除は人によって実額が違う**。目安表は「年収の約15パーセント」
のような一律の仮定を置いている。だが実際の社会保険料率は、加入している健康保険組合、
介護保険の対象かどうか、標準報酬月額の等級で変わる。

つまり**同じ年収でも上限額は違う。** 目安表はその違いを潰している。

--------------------------------------------------------------------------
外れる向きが問題
--------------------------------------------------------------------------
上限を **超えた分は全額自己負担** になる。下回った分は、単に使い残しになるだけ。
つまり誤差は対称ではなく、**多く見積もる誤差のほうが痛い。**

目安表が実際より高く出るのは、社会保険料が仮定より多い人。
ここではその条件を特定して、超過額がいくらになるかまで出す。

--------------------------------------------------------------------------
分母に所得税率がいる（2026-08-16 に足した。**実測してから書いている**）
--------------------------------------------------------------------------
    上限額 = 所得割額 × 20% ÷ (**90% - 所得税率 × 1.021**) + 2,000

**所得税率は分母にいる。** だから税率が1段上がると分母が小さくなり、
上限は**上がる**。所得割額は境目で連続（年収1円ぶんしか動かない）なので、
境目での動きは**ほぼ全部が分母の段差**になる。

実測（社会保険料15%・独身・扶養なし）:

    課税所得 330万で20%へ   年収  6,492,306円   85,970 →   98,292円（**+12,322円**）
    課税所得 900万で33%へ   年収 13,447,058円  274,110 →  323,452円（**+49,342円 / +18.0%**）

**年収が1円ふえるだけで、寄付できる枠が数千円〜十数万円ふえる。**
「税率が上がった＝損」という向きと逆で、年収の表にも目安表にも出てこない
（どちらも境目をまたいで平らに描く）。

そして境目は**年収ではなく課税所得**で決まるので、同じ年収でも人によって位置が違う。
年収650万で社会保険料率だけ動かすと:

    13% → 14%   102,172 → 100,304円（−1,868円）
    15% → 16%    98,435 →  84,466円（**−13,969円**。ここだけ 7.5倍）

15%と16%のあいだで課税所得が330万を割り、**1つ下の税率帯へ落ちる。**
目安表の「同じ年収なら同じ上限」がいちばん壊れるのがここで、
**壊れ方は年収では引けない。**

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
控除の3階建て（地方税法・所得税法）。

  1. 所得税から   (寄付額 - 2,000) × 所得税率 × 1.021
  2. 住民税・基本  (寄付額 - 2,000) × 10%
  3. 住民税・特例  (寄付額 - 2,000) × (90% - 所得税率 × 1.021)

3 には上限があり、**住民税の所得割額の20パーセント**まで。
ここを超えると自己負担が2,000円で収まらなくなる。この上限が実質の上限額を決める。

    上限額 = 所得割額 × 20% ÷ (90% - 所得税率 × 1.021) + 2,000

1.021 は復興特別所得税。この式そのものは制度から決まるもので、仮定ではない。
仮定なのは **社会保険料率** のほうで、そこは必ず前提として画面に出す。

住民税の所得割は標準税率10パーセント（市町村6・道府県4）で計算している。
自治体によって超過課税があるが、ここでは標準税率で置いている。
"""
from __future__ import annotations

from dataclasses import dataclass

ASSUMPTIONS = [
    "給与収入のみの人を想定しています。事業所得や不動産所得がある場合は変わります",
    "住民税の所得割は標準税率の10パーセントで計算しています。超過課税のある自治体では変わります",
    "所得税率には復興特別所得税を含めています。所得税率に1.021を掛けています",
    "住民税の基礎控除は43万円、所得税の基礎控除は48万円で計算しています",
    "社会保険料率はこの計算での仮定で、15パーセントとして置いています。"
    "加入している健康保険や介護保険の対象かどうかで実際は変わります",
    "ふるさと納税以外の所得控除は入れていません。医療費控除や住宅ローン控除があると上限は下がります",
    "ワンストップ特例ではなく確定申告した場合で計算しています",
]

RECONSTRUCTION = 1.021          # 復興特別所得税
RESIDENT_RATE = 0.10            # 住民税の所得割（標準税率）
SPECIAL_CAP_RATE = 0.20         # 特例分の上限（所得割額に対する割合）
SELF_PAY = 2_000                # 自己負担
BASIC_INCOME = 480_000          # 所得税の基礎控除
BASIC_RESIDENT = 430_000        # 住民税の基礎控除

# 目安表がよく置いている社会保険料の仮定
TYPICAL_SOCIAL_RATE = 0.15

# 所得税の速算表（課税所得の下限, 税率）
INCOME_TAX_BRACKETS = [
    (0, 0.05),
    (1_950_000, 0.10),
    (3_300_000, 0.20),
    (6_950_000, 0.23),
    (9_000_000, 0.33),
    (18_000_000, 0.40),
    (40_000_000, 0.45),
]


@dataclass(frozen=True)
class Person:
    """上限額を決めるのに要る最小限。"""

    income: int              # 給与収入（額面の年収）
    social_rate: float       # 社会保険料の実効率
    dependents_general: int = 0   # 一般の扶養（16歳以上19歳未満・23歳以上）
    spouse: bool = False          # 配偶者控除の対象がいるか


def salary_deduction(income: int) -> int:
    """給与所得控除。令和2年分以降の額。"""
    if income <= 1_625_000:
        return 550_000
    if income <= 1_800_000:
        return int(income * 0.4) - 100_000
    if income <= 3_600_000:
        return int(income * 0.3) + 80_000
    if income <= 6_600_000:
        return int(income * 0.2) + 440_000
    if income <= 8_500_000:
        return int(income * 0.1) + 1_100_000
    return 1_950_000


def income_tax_rate(taxable: int) -> float:
    """課税所得から所得税率を引く。"""
    rate = INCOME_TAX_BRACKETS[0][1]
    for floor, r in INCOME_TAX_BRACKETS:
        if taxable >= floor:
            rate = r
    return rate


def _deductions(p: Person, *, resident: bool) -> int:
    """基礎控除・配偶者控除・扶養控除の合計。所得税と住民税で額が違う。"""
    if resident:
        basic, spouse, dependent = BASIC_RESIDENT, 330_000, 330_000
    else:
        basic, spouse, dependent = BASIC_INCOME, 380_000, 380_000
    return basic + (spouse if p.spouse else 0) + dependent * p.dependents_general


def resident_tax_income_levy(p: Person) -> int:
    """住民税の所得割額。上限額を決める本体。"""
    social = int(p.income * p.social_rate)
    taxable = p.income - salary_deduction(p.income) - social - _deductions(p, resident=True)
    return max(0, int(taxable * RESIDENT_RATE))


def taxable_income(p: Person) -> int:
    """所得税の課税所得。税率を引くのに使う。"""
    social = int(p.income * p.social_rate)
    return max(0, p.income - salary_deduction(p.income) - social - _deductions(p, resident=False))


def limit(p: Person) -> int:
    """自己負担が2,000円で収まる寄付額の上限。

        所得割額 × 20% ÷ (90% - 所得税率 × 1.021) + 2,000
    """
    levy = resident_tax_income_levy(p)
    rate = income_tax_rate(taxable_income(p))
    denominator = 0.90 - rate * RECONSTRUCTION
    if denominator <= 0:
        raise ValueError("分母が0以下になりました。所得税率の取り違えです")
    return int(levy * SPECIAL_CAP_RATE / denominator) + SELF_PAY


def check_tables() -> None:
    """制度から決まる部分がずれていないかを確かめる。

    この計算の怖いところは、**取り違えても数字がそれらしく出る**こと。
    分母の 90% を 100% にしても、所得税率を復興税抜きにしても、
    出てくるのは「それっぽい上限額」で、見ただけでは分からない。

    だから法令が名指ししている値と、計算の向きを不変条件に置く。
    """
    if abs(RECONSTRUCTION - 1.021) > 1e-12:
        raise ValueError(f"復興特別所得税の係数が {RECONSTRUCTION}。法定は 1.021")
    if abs(SPECIAL_CAP_RATE - 0.20) > 1e-12:
        raise ValueError(f"特例分の上限が所得割額の {SPECIAL_CAP_RATE}。法定は 0.20")
    if abs(RESIDENT_RATE - 0.10) > 1e-12:
        raise ValueError(f"住民税の所得割が {RESIDENT_RATE}。標準税率は 0.10")
    if SELF_PAY != 2_000:
        raise ValueError(f"自己負担が {SELF_PAY}円。制度上は 2,000円")

    # 給与所得控除の頭打ち。令和2年分以降は195万円で止まる。
    if salary_deduction(10_000_000) != 1_950_000:
        raise ValueError("給与所得控除の上限が195万円になっていない")
    if salary_deduction(20_000_000) != salary_deduction(10_000_000):
        raise ValueError("給与所得控除が頭打ちになっていない")

    # 速算表の境目。課税所得195万円ちょうどは10%側。
    for taxable, want in ((1_949_999, 0.05), (1_950_000, 0.10),
                          (3_300_000, 0.20), (8_999_999, 0.23),
                          (9_000_000, 0.33), (40_000_000, 0.45)):
        got = income_tax_rate(taxable)
        if abs(got - want) > 1e-12:
            raise ValueError(f"課税所得{taxable:,}円の税率が {got}。速算表は {want}")

    # 年収が増えれば上限は増える
    limits = [limit(Person(income=i, social_rate=TYPICAL_SOCIAL_RATE))
              for i in range(3_000_000, 12_000_001, 1_000_000)]
    for a, b in zip(limits, limits[1:]):
        if b <= a:
            raise ValueError("年収が増えたのに上限額が増えていない")

    # 社会保険料が増えれば所得割が減り、上限も下がる（この計算の主題）
    low = limit(Person(income=6_000_000, social_rate=0.13))
    high = limit(Person(income=6_000_000, social_rate=0.17))
    if not high < low:
        raise ValueError("社会保険料が増えたのに上限額が下がっていない")

    # 扶養が増えれば所得割が減り、上限も下がる
    if not limit(Person(income=6_000_000, social_rate=0.15, dependents_general=2)) < \
           limit(Person(income=6_000_000, social_rate=0.15)):
        raise ValueError("扶養が増えたのに上限額が下がっていない")

    # --- 速算表の境目（2026-08-16 に足した節）-------------------------------
    #
    # **境目のすぐ上の上限額は、社会保険料率によらず同じ**になります。
    # 課税所得が境目ちょうどに揃うので、所得割額も税率も揃うからです
    # （住民税側の課税所得は基礎控除の差 5万円だけ上）。
    # **これは制度から決まる不変条件で、仮定ではありません。**
    # 分母の 90% や 1.021 を取り違えるとここが揃わなくなるので、門にします。
    at_floor = {limit(Person(income=bracket_income(3_300_000, r), social_rate=r))
                for r in (0.13, 0.15, 0.17)}
    if len(at_floor) != 1:
        raise ValueError(f"境目の上限額が社会保険料率で揺れています: {sorted(at_floor)}")

    # 税率は分母にいるので、境目を1円またぐと上限は**上がる**（下がったら符号違い）
    for row in bracket_jumps():
        if row["はね上がる額"] <= 0:
            raise ValueError(
                f"課税所得{row['課税所得の境目']:,}円の境目で上限が上がっていない"
                f"（{row['1円下の上限']:,}→{row['境目の上限']:,}）。分母の向きを疑うこと")

    # 段差は「所得割の1円ぶん」では説明できない大きさであること。
    # ここが同じ桁なら、それは境目ではなく、ただの丸め誤差を拾っています。
    jump = next(r for r in bracket_jumps() if r["課税所得の境目"] == 9_000_000)
    if jump["はね上がる額"] < 10_000:
        raise ValueError(f"33%帯の段差が {jump['はね上がる額']:,}円。分母の段差が効いていない")


def social_rate_grid(income: int, rates=(0.13, 0.14, 0.15, 0.16, 0.17)) -> list[dict]:
    """同じ年収で、社会保険料率だけを動かしたときの上限額。

    目安表が潰している差はここ。**同じ年収でも上限は違う。**
    """
    base = limit(Person(income=income, social_rate=TYPICAL_SOCIAL_RATE))
    rows = []
    for r in rates:
        got = limit(Person(income=income, social_rate=r))
        rows.append({
            "社会保険料率": f"{r * 100:.0f}%",
            "社会保険料": int(income * r),
            "上限額": got,
            "目安表との差": got - base,
            "超過自己負担": max(0, base - got),
        })
    return rows


def income_grid(social_rate: float = TYPICAL_SOCIAL_RATE,
                incomes=(3_000_000, 4_000_000, 5_000_000, 6_000_000,
                         8_000_000, 10_000_000, 12_000_000)) -> list[dict]:
    """年収べつの上限額。独身・扶養なしと、扶養2人を並べる。"""
    rows = []
    for income in incomes:
        alone = Person(income=income, social_rate=social_rate)
        family = Person(income=income, social_rate=social_rate, spouse=True, dependents_general=1)
        rows.append({
            "年収": income,
            "所得割額": resident_tax_income_levy(alone),
            "所得税率": f"{income_tax_rate(taxable_income(alone)) * 100:.0f}%",
            "上限_独身": limit(alone),
            "上限_配偶者と扶養1人": limit(family),
            "差": limit(alone) - limit(family),
        })
    return rows


def bracket_income(taxable_floor: int, social_rate: float = TYPICAL_SOCIAL_RATE,
                   **kw) -> int:
    """課税所得が `taxable_floor` に届く、いちばん低い年収を出す。

    速算表の境目は**課税所得**で決まるので、年収でどこに来るかは
    社会保険料率と扶養の数で動きます。**二分探索で毎回引き直します**
    （手で置いた年収を書くと、控除額を直した日に黙ってずれます）。
    """
    lo, hi = 1_000_000, 60_000_000
    while lo < hi:
        mid = (lo + hi) // 2
        if taxable_income(Person(income=mid, social_rate=social_rate, **kw)) >= taxable_floor:
            hi = mid
        else:
            lo = mid + 1
    return lo


def bracket_jumps(social_rate: float = TYPICAL_SOCIAL_RATE) -> list[dict]:
    """速算表の境目で、上限額が**はね上がる**幅。

    ここが、この calc でいちばん直感に反するところ。

        上限額 = 所得割額 × 20% ÷ (**90% - 所得税率 × 1.021**) + 2,000

    **所得税率は分母にいます。** 税率が上がると分母が小さくなるので、
    上限は**増えます**。所得割額のほうは境目で連続なので（年収1円ぶんしか動かない）、
    境目での動きは**ほぼ全部が分母の段差**です。

    つまり「税率が上がった＝損」という向きと**逆**で、
    **年収が1円ふえただけで、寄付できる枠が数千円〜十数万円ふえます。**
    この段差は年収の表にも目安表にも出てきません（どちらも境目をまたいで平らに描く）。
    """
    rows = []
    for floor, rate in INCOME_TAX_BRACKETS[1:]:
        inc = bracket_income(floor, social_rate)
        below = limit(Person(income=inc - 1, social_rate=social_rate))
        above = limit(Person(income=inc, social_rate=social_rate))
        rows.append({
            "課税所得の境目": floor,
            "所得税率": f"{rate * 100:.0f}%",
            "境目の年収": inc,
            "1円下の上限": below,
            "境目の上限": above,
            "はね上がる額": above - below,
            "はね上がる率": f"{(above / below - 1) * 100:.1f}%",
        })
    return rows


def straddle(income: int, rates=(0.13, 0.14, 0.15, 0.16, 0.17)) -> list[dict]:
    """同じ年収で社会保険料率だけを動かし、**境目をまたぐ人**を見つける。

    `social_rate_grid()` は「率が上がると所得割が減って上限も少し下がる」を出します。
    **その差は率1%につき2千円ほどで、なだらかです。**

    ところがその年収が速算表の境目のすぐ上にあると、社会保険料が重い人だけ
    課税所得が境目を割り、**1つ下の税率帯へ落ちます。** 分母が大きくなるので、
    上限は**なだらかな差では説明できない幅で落ちます。**

    **目安表は「同じ年収なら同じ上限」と言います。** その仮定がいちばん壊れるのが
    ここで、壊れ方は年収では引けません（**課税所得でしか引けない**）。
    """
    rows = []
    prev = None
    for r in rates:
        p = Person(income=income, social_rate=r)
        tx = taxable_income(p)
        lim = limit(p)
        rows.append({
            "社会保険料率": f"{r * 100:.0f}%",
            "課税所得": tx,
            "所得税率": f"{income_tax_rate(tx) * 100:.0f}%",
            "上限額": lim,
            "1つ前との差": 0 if prev is None else lim - prev,
        })
        prev = lim
    return rows


def worst_overrun(incomes=(4_000_000, 6_000_000, 8_000_000, 10_000_000)) -> dict:
    """目安表どおりに寄付して、一番損をするのはどの条件か。

    目安表は社会保険料を年収の15パーセントと置いている。実際がそれより重い人は、
    目安表の額まで寄付すると**上限を超え、超過分が全額自己負担**になる。
    """
    worst = {"超過自己負担": -1}
    for income in incomes:
        assumed = limit(Person(income=income, social_rate=TYPICAL_SOCIAL_RATE))
        for r in (0.16, 0.17, 0.18):
            actual = limit(Person(income=income, social_rate=r))
            over = max(0, assumed - actual)
            if over > worst["超過自己負担"]:
                worst = {
                    "年収": income,
                    "実際の社会保険料率": f"{r * 100:.0f}%",
                    "目安表の上限": assumed,
                    "実際の上限": actual,
                    "超過自己負担": over,
                }
    return worst


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過\n")

    print("=== 年収べつの上限額（社会保険料15%の仮定）===")
    for row in income_grid():
        print(f"  年収{row['年収'] // 10000:>4d}万  所得割{row['所得割額']:>8,}円  税率{row['所得税率']:>4s}  "
              f"独身{row['上限_独身']:>8,}円  配偶者と扶養1人{row['上限_配偶者と扶養1人']:>8,}円  "
              f"差{row['差']:>7,}円")

    print("\n=== 同じ年収600万で、社会保険料率だけを動かす ===")
    for row in social_rate_grid(6_000_000):
        print(f"  {row['社会保険料率']:>4s}  社会保険料{row['社会保険料']:>9,}円  "
              f"上限{row['上限額']:>8,}円  目安表との差{row['目安表との差']:>+8,}円  "
              f"超過自己負担{row['超過自己負担']:>7,}円")

    print("\n=== 所得税率の境目で、上限額は年収1円差ではね上がる ===")
    for row in bracket_jumps():
        print(f"  課税所得{row['課税所得の境目']:>10,}円で{row['所得税率']:>4s}へ  "
              f"年収{row['境目の年収']:>10,}円  "
              f"上限 {row['1円下の上限']:>9,}→{row['境目の上限']:>9,}円  "
              f"はね上がる額{row['はね上がる額']:>+9,}円（{row['はね上がる率']}）")

    print("\n=== 同じ年収650万でも、社会保険料率1%で境目をまたぐ ===")
    for row in straddle(6_500_000):
        print(f"  {row['社会保険料率']:>4s}  課税所得{row['課税所得']:>10,}円  "
              f"所得税率{row['所得税率']:>4s}  上限{row['上限額']:>9,}円  "
              f"1つ前との差{row['1つ前との差']:>+9,}円")

    print("\n=== 目安表どおり寄付して一番損をする条件 ===")
    for k, v in worst_overrun().items():
        print(f"  {k}: {v:,}" if isinstance(v, int) else f"  {k}: {v}")
