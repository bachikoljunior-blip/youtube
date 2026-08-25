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
上限を超えた分は、**その 79.79 パーセント**（所得税率10パーセントの帯）が自己負担になる。
下回った分は、単に使い残しになるだけ。つまり誤差は対称ではなく、
**多く見積もる誤差のほうが痛い。**

**ここは 2026-08-24 まで「超えた分は全額自己負担」と書いていた。誤りだった** ——
頭打ちがあるのは3階の住民税・特例分だけで、1階と2階は超過分にも効く。
向き（多く見積もるほうが痛い）は変わらないが、**痛さの大きさは 8割**になる。
下の節を見ること。

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
「超えた分は全額自己負担」は、2階ぶん数え落としている（2026-08-24 に足した）
--------------------------------------------------------------------------
どの解説も「上限を超えた分は自己負担」で止まります。**正確ではありません。**
頭打ちがあるのは **3階の住民税・特例分だけ**で、1階（所得税）と2階（住民税の基本分）は
**超過分にも効きます。** だから自己負担になるのは超過額の全部ではなく、

    1 −（所得税率 × 1.021 ＋ 10パーセント）

の割合だけ。所得税率10パーセントの帯なら **79.79パーセント**。

そして超過がいちばん起きやすいのは **年収が下がった年**です。上限は**その年**の
所得で決まるのに、寄付するときに手元にあるのは**去年**の源泉徴収票だから。
年収600万で枠いっぱい（77,949円）寄付した人の自己負担は:

    年収が変わらない      2,000円
    10パーセント下がる    9,800円（**4.9倍**）
    20パーセント下がる   17,600円（**8.8倍**）
    30パーセント下がる   29,277円（**14.6倍**）

--------------------------------------------------------------------------
扶養1人あたりの減りは、1人目だけ深い（2026-08-24 に足した）
--------------------------------------------------------------------------
扶養控除は住民税で1人33万円。所得割が33,000円減り、特例分の頭打ちが6,600円下がるので、
上限は **6,600 ÷ 分母 ＝ 8,272円**（所得税率10パーセントの帯）だけ減ります。
**揃うのは、段を割らない年収だけです。**

年収700万・社会保険料15パーセントだと、扶養1人目で所得税の課税所得が330万円を割り、
税率が20→10パーセントへ落ちて分母が広がります。**1人目だけ 21,954円（2.65倍）。**
2人目からは 8,272円に戻ります。

深くなる年収の帯は、速算表の段の数だけあります（1万円刻みで走査）:

    年収  6,500,000 〜  7,010,000円   20% → 10%   減り 20,611 〜 21,981円
    年収 11,040,000 〜 11,480,000円   23% → 20%   減り 18,756 〜 19,252円
    年収 13,450,000 〜 13,890,000円   33% → 23%   減り 59,277 〜 61,316円

**同じ「扶養1人」で、場所によって桁がちがいます。**

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

from . import _checks

ASSUMPTIONS = [
    "給与収入のみの人を想定しています。事業所得や不動産所得がある場合は変わります",
    "住民税の所得割は標準税率の10パーセントで計算しています。超過課税のある自治体では変わります",
    "所得税率には復興特別所得税を含めています。所得税率に1.021を掛けています",
    "住民税の基礎控除は43万円、所得税の基礎控除は48万円で計算しています",
    "社会保険料率はこの計算での仮定で、15パーセントとして置いています。"
    "加入している健康保険や介護保険の対象かどうかで実際は変わります",
    "ふるさと納税以外の所得控除は入れていません。医療費控除や住宅ローン控除があると上限は下がります",
    "ワンストップ特例ではなく確定申告した場合で計算しています",
    "上限を超えた寄付の計算では、寄付金控除の枠を入れています。"
    "所得税は総所得金額等の40パーセントまで、住民税の基本分は30パーセントまでです",
    "年収が下がった年の計算では、去年の年収で引いた上限額をそのまま寄付したものとしています。"
    "社会保険料率は去年も今年も15パーセントの仮定で置いています",
    "扶養控除は一般の扶養（16歳以上19歳未満・23歳以上）とし、住民税33万円・所得税38万円で"
    "計算しています。特定扶養親族や同居老親等だと額が変わります",
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


def total_income(p: Person) -> int:
    """総所得金額等（給与収入 − 給与所得控除）。**寄付金控除の枠の分母。**"""
    return max(0, p.income - salary_deduction(p.income))


def out_of_pocket(p: Person, donation: int) -> dict:
    """**上限を超えて寄付したとき、自己負担がいくらになるか。**

    3階建てのうち、**上限があるのは住民税の特例分だけ**です
    （所得割額の20パーセント）。だから超えた分は
    「所得税ぶん ＋ 住民税の基本分」だけしか戻らず、
    **残りがそのまま自己負担になります。**

        所得税      (min(寄付額, 総所得×40%) − 2,000) × 所得税率 × 1.021
        住民税・基本 (min(寄付額, 総所得×30%) − 2,000) × 10%
        住民税・特例 (寄付額 − 2,000) × (90% − 所得税率×1.021)  ← 所得割額×20% で頭打ち

    一般の解説は「超えた分は自己負担」で止まります。**それは正確ではありません** ——
    超えた分にも所得税と住民税の基本分（合わせて所得税率×1.021＋10パーセント）は
    効くので、**自己負担になるのは超過額の全部ではなく、その残り**です。
    """
    ti = total_income(p)
    levy = resident_tax_income_levy(p)
    rate = income_tax_rate(taxable_income(p))
    base = max(0, donation - SELF_PAY)

    income_base = max(0, min(donation, int(ti * 0.40)) - SELF_PAY)
    income_tax_cut = income_base * rate * RECONSTRUCTION
    resident_base_target = max(0, min(donation, int(ti * 0.30)) - SELF_PAY)
    resident_basic = resident_base_target * RESIDENT_RATE
    special_uncapped = base * (0.90 - rate * RECONSTRUCTION)
    special_cap = levy * SPECIAL_CAP_RATE
    resident_special = min(special_uncapped, special_cap)

    refund = income_tax_cut + resident_basic + resident_special
    return {
        "寄付額": donation,
        "上限額": limit(p),
        "所得税から戻る": income_tax_cut,
        "住民税・基本分": resident_basic,
        "住民税・特例分": resident_special,
        "特例分の頭打ち": special_cap,
        "頭打ちに当たったか": special_uncapped > special_cap,
        "戻る合計": refund,
        "自己負担": donation - refund,
    }


def income_drop_grid(last_year: int, social_rate: float = TYPICAL_SOCIAL_RATE,
                     drops=(0.0, 0.05, 0.10, 0.20, 0.30, 0.40)) -> list[dict]:
    """**去年の年収で枠いっぱい寄付して、今年の年収が下がったとき。**

    上限額は**その年の所得**で決まるのに、寄付は**その年が終わる前**にします。
    目安表を引くときに手元にあるのは去年の源泉徴収票なので、
    **年収が下がった年は、去年の枠がそのまま超過額になります。**
    """
    donation = limit(Person(income=last_year, social_rate=social_rate))
    rows: list[dict] = []
    for d in drops:
        this_year = int(last_year * (1 - d))
        p = Person(income=this_year, social_rate=social_rate)
        o = out_of_pocket(p, donation)
        rows.append({
            "年収の下がり方": d,
            "今年の年収": this_year,
            "去年の枠で寄付した額": donation,
            "今年の上限額": o["上限額"],
            "超過額": max(0, donation - o["上限額"]),
            "自己負担": o["自己負担"],
            "自己負担の増え方": o["自己負担"] / SELF_PAY,
            "超過額のうち自己負担になる割合": (
                (o["自己負担"] - SELF_PAY) / (donation - o["上限額"])
                if donation > o["上限額"] else 0.0),
        })
    return rows


def dependent_grid(income: int, social_rate: float = TYPICAL_SOCIAL_RATE,
                   upto: int = 3) -> list[dict]:
    """**扶養が1人ふえると、枠は何円減るか。**

    扶養控除は住民税で1人33万円。所得割はその10パーセント＝33,000円減り、
    特例分の頭打ちはその20パーセント＝6,600円ぶん下がります。
    **上限額はそれを分母で割った額だけ減ります** ——
    所得税率10パーセントの帯なら 6,600 ÷ 0.7979 ＝ **8,272円**。
    **ところが、それで揃うのは段を割らない年収だけです** ——
    扶養控除は所得税の課税所得も同時に下げるので、
    **税率の段を割る年収では分母が広がり、そこだけ深く落ちます。**
    """
    rows: list[dict] = []
    prev: int | None = None
    for n in range(upto + 1):
        p = Person(income=income, social_rate=social_rate, dependents_general=n)
        lim = limit(p)
        rows.append({
            "扶養の人数": n,
            "住民税の所得割額": resident_tax_income_levy(p),
            "所得税の課税所得": taxable_income(p),
            "所得税率": income_tax_rate(taxable_income(p)),
            "上限額": lim,
            "1人ふえて減った額": None if prev is None else prev - lim,
        })
        prev = lim
    return rows


def dependent_cliff(social_rate: float = TYPICAL_SOCIAL_RATE,
                    lo: int = 5_000_000, hi: int = 15_000_000,
                    step: int = 10_000) -> list[dict]:
    """**扶養が1人ふえたせいで所得税の段を割る年収**を、全部拾う。

    段を割らない年収なら減りは 6,600円ぐらいで揃います。
    **割る年収だけ、そこが数倍から十数倍に深くなります。**
    刻みは既定1万円。`check_tables` が、刻みを半分にしても
    見つかる帯が同じであることを見ています。
    """
    out: list[dict] = []
    for income in range(lo, hi + 1, step):
        p0 = Person(income=income, social_rate=social_rate)
        p1 = Person(income=income, social_rate=social_rate, dependents_general=1)
        r0 = income_tax_rate(taxable_income(p0))
        r1 = income_tax_rate(taxable_income(p1))
        if r0 != r1:
            out.append({
                "年収": income,
                "扶養0人の所得税率": r0,
                "扶養1人の所得税率": r1,
                "扶養0人の上限額": limit(p0),
                "扶養1人の上限額": limit(p1),
                "減った額": limit(p0) - limit(p1),
            })
    return out


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

    # --- 崖の深さの順番（2026-08-17 に足した節）-----------------------------
    #
    # **いちばん深いのは最上段ではなく 33% の境目**、
    # **いちばん浅いのは真ん中の 23%**。端ではないので、
    # 「税率が高いほど段差が大きい」で読むと必ず外します。
    steps = jump_by_step()
    深さ = [r["はね上がる率パーセント"] for r in steps]
    if 深さ.index(max(深さ)) in (0, len(深さ) - 1):
        raise ValueError(
            f"いちばん深い崖が端にあります（{[round(x, 2) for x in 深さ]}）。"
            f"深さを決めるのは税率の高さではなく段の幅のはず")
    if 深さ.index(min(深さ)) in (0, len(深さ) - 1):
        raise ValueError(
            f"いちばん浅い崖が端にあります（{[round(x, 2) for x in 深さ]}）")
    top = max(steps, key=lambda r: r["はね上がる率パーセント"])
    if abs(top["所得税率"] - 0.33) > 1e-12:
        raise ValueError(f"いちばん深い崖が {top['所得税率']} 帯。速算表では 33% のはず")

    # 1ポイントあたりの効きは、税率が上がるほど**必ず**強くなる（分母が縮むから）
    _checks.increases_with(
        lambda i: steps[i]["1ポイントあたりパーセント"], range(len(steps)),
        "1ポイントあたりの跳ね幅が、税率が上がっても強くなっていない")

    # 式の分母は `90% − 所得税率 × 1.021`。**取り違えるとここが合わない。**
    for r in steps:
        _checks.close(r["式の分母"],
                      0.9 - r["所得税率"] * RECONSTRUCTION, "上限の式の分母")
        if r["段の幅ポイント"] <= 0:
            raise ValueError(f"段の幅が {r['段の幅ポイント']}ポイント。速算表は必ず上がる")

    # --- 上限を超えた寄付と、扶養（2026-08-24 に足した2節）-------------------
    #
    # (1) 枠ちょうどなら自己負担は2,000円。**式の3階建てが揃っている証拠**
    p0 = Person(income=6_000_000, social_rate=TYPICAL_SOCIAL_RATE)
    at_limit = out_of_pocket(p0, limit(p0))
    _checks.close(at_limit["自己負担"], float(SELF_PAY), "枠ちょうど寄付した人の自己負担")
    if at_limit["頭打ちに当たったか"]:
        raise ValueError("枠ちょうどで特例分の頭打ちに当たっている（上限の式と矛盾）")

    # (2) **主題**: 超えた分は「全額」自己負担ではない。
    #     所得税ぶんと住民税の基本分は超過分にも効くので、
    #     自己負担になるのは **1 −（所得税率×1.021 ＋ 10%）** の割合だけ。
    over = out_of_pocket(p0, limit(p0) * 3)
    if not over["頭打ちに当たったか"]:
        raise ValueError("枠の3倍を寄付して、特例分の頭打ちに当たっていない")
    rate0 = income_tax_rate(taxable_income(p0))
    share = (over["自己負担"] - SELF_PAY) / (over["寄付額"] - over["上限額"])
    #     **1e-9 では通りません** —— `limit()` が円未満を切り捨てるので、
    #     割合には 1円 ÷ 超過額ぶん（実測 1.9e-06）のずれが必ず残ります。
    _checks.close(share, 1 - (rate0 * RECONSTRUCTION + RESIDENT_RATE),
                  "超過額のうち自己負担になる割合", tol=1e-4)
    if share >= 1.0:
        raise ValueError(f"超過額が全額自己負担になっています（{share}）。3階建ての1と2が効いていない")

    # (3) 年収が下がるほど自己負担は増える（この節の主題）
    drops = income_drop_grid(6_000_000)
    _checks.close(drops[0]["自己負担"], float(SELF_PAY), "年収が変わらない人の自己負担")
    seq = [r["自己負担"] for r in drops]
    for a, b in zip(seq, seq[1:]):
        if b <= a:
            raise ValueError("年収の下がり方が大きいのに、自己負担が増えていない")

    # (4) 扶養が1人ふえて減る額は、**段を割らないなら分母で割った額で揃う**
    dep = dependent_grid(7_000_000)
    flat = [r for r in dep[1:] if r["所得税率"] == dep[-1]["所得税率"]
            and r["1人ふえて減った額"] is not None]
    plateau = {r["1人ふえて減った額"] for r in flat[1:]}
    if len(plateau) != 1:
        raise ValueError(f"段を割らない扶養1人あたりの減りが揃っていません: {sorted(plateau)}")
    only = plateau.pop()
    _checks.close(float(only),
                  330_000 * RESIDENT_RATE * SPECIAL_CAP_RATE
                  / (0.90 - dep[-1]["所得税率"] * RECONSTRUCTION),
                  "扶養1人あたりの上限額の減り", tol=2.0)

    # (5) **主題**: 段を割る年収では、1人目だけが深い
    if dep[1]["1人ふえて減った額"] <= only:
        raise ValueError("段を割る扶養1人目が、割らない2人目より浅い")

    # (6) 崖の帯は、**刻みを半分にしても同じ数**（_template の「刻み」の節）
    def _bands(step: int) -> int:
        rows = dependent_cliff(step=step)
        n, prev = 0, None
        for r in rows:
            if prev is None or r["年収"] - prev != step:
                n += 1
            prev = r["年収"]
        return n
    if _bands(10_000) != _bands(5_000):
        raise ValueError(
            f"崖の帯の数が刻みで変わります（1万円 {_bands(10_000)} / 5千円 {_bands(5_000)}）")
    if _bands(10_000) != len(INCOME_TAX_BRACKETS) - 4:
        raise ValueError(f"崖の帯が {_bands(10_000)}本。速算表の段から出る本数と違う")


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


def jump_by_step(social_rate: float = TYPICAL_SOCIAL_RATE) -> list[dict]:
    """**いちばん深い崖は、いちばん上の段ではありません。**

    ## この節を足した理由（2026-08-17。**機械の掃引が指した所の、隣**）

    `src/section_sweep.py`（この日に入れた道具）は `bracket_jumps` の
    「境目の上限が 40%→45% で 1,083,845円 跳ぶ」を候補として出しました。
    **これは節になりません** —— 速算表の段は 1,800万→4,000万 と幅そのものが
    桁違いなので、**跳んでいるのは制度ではなく段の置き方**です。

    ところが実物を並べると、掃引が**見られなかった欄**に本物がありました ——
    `はね上がる率` は `f"{...:.1f}%"` の**文字列**なので、
    `_scalars()` が数字として拾えず、掃引に載っていませんでした。

    **2026-08-17 18:2x に直しました**（`section_sweep._as_number`）。
    いまは掃引がこの欄を**自分で**名指します ——
    「`はね上がる率`… いちばん高いのは端ではなく 33% のとき（18／端では 11.6）」。
    **人が手で並べて見つけたものと同じです。**

        10%  +6.14%    20%  +14.33%   23%  **+4.56%**
        33%  **+18.00%**   40%  +14.49%   45%  +11.57%

    **いちばん深いのは 33% の境目**で、最上段の 45%（11.57%）より深い。
    **いちばん浅いのは真ん中の 23%**（4.56%）。
    つまり「税率が高い人ほど段差が大きい」ではありません。

    決めているのは**税率の高さではなく、その境目で税率が何ポイント上がるか**です
    （23% は 20→23 の **3ポイント**、33% は 23→33 の **10ポイント**）。
    上限の式の分母は `90% − 所得税率 × 1.021` なので、
    **段を1つまたぐと分母がその幅ぶん縮みます。**

    そのうえで、**1ポイントあたりの効きは税率が上がるほど必ず強くなります**
    （1.23% → 2.32%）。分母が小さいほど、同じ幅の縮みが効くからです。
    **深さ ＝ 段の幅 × 1ポイントあたりの効き**で、**前者のほうが大きく振れる**。
    """
    rows = []
    brackets = INCOME_TAX_BRACKETS
    for i, jump in enumerate(bracket_jumps(social_rate)):
        rate_below, rate_above = brackets[i][1], brackets[i + 1][1]
        step_points = round((rate_above - rate_below) * 100)
        pct = (jump["境目の上限"] / jump["1円下の上限"] - 1) * 100
        rows.append({
            "所得税率": rate_above,
            "1つ下の税率": rate_below,
            "段の幅ポイント": step_points,
            "はね上がる率パーセント": pct,
            "1ポイントあたりパーセント": pct / step_points,
            "式の分母": RESIDENT_RATE * 9 - rate_above * RECONSTRUCTION,
            "境目の年収": jump["境目の年収"],
            "はね上がる額": jump["はね上がる額"],
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
    目安表の額まで寄付すると**上限を超える。**

    **超過分が「全額」自己負担になるわけではありません**（2026-08-24 に正した）——
    頭打ちがあるのは住民税の特例分だけで、所得税ぶんと住民税の基本分は
    超過分にも効きます。実際に自己負担になるのは
    **1 −（所得税率×1.021 ＋ 10パーセント）** の割合で、
    所得税率10パーセントの帯なら **79.79パーセント**（`out_of_pocket`）。
    ここが返す「超過自己負担」は、**その割引をかける前の超過額**です。
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

    print("\n=== いちばん深い崖は、いちばん上の段ではない ===")
    for row in jump_by_step():
        print(f"  所得税率 {row['所得税率'] * 100:>4.0f}%"
              f"（1つ下は {row['1つ下の税率'] * 100:>2.0f}% ＝ 段の幅"
              f" {row['段の幅ポイント']:>2}ポイント）"
              f"  年収 {row['境目の年収']:>10,}円"
              f"  はね上がる {row['はね上がる率パーセント']:>5.2f}%"
              f"  1ポイントあたり {row['1ポイントあたりパーセント']:.3f}%")
    _steps = jump_by_step()
    _deep = max(_steps, key=lambda r: r["はね上がる率パーセント"])
    _shallow = min(_steps, key=lambda r: r["はね上がる率パーセント"])
    print(f"  **いちばん深いのは {_deep['所得税率'] * 100:.0f}% の境目"
          f"（{_deep['はね上がる率パーセント']:.2f}%）で、最上段の"
          f" {_steps[-1]['所得税率'] * 100:.0f}%"
          f"（{_steps[-1]['はね上がる率パーセント']:.2f}%）より深い。**")
    print(f"    いちばん浅いのは {_shallow['所得税率'] * 100:.0f}% の境目"
          f"（{_shallow['はね上がる率パーセント']:.2f}%）＝ 段の幅が"
          f" {_shallow['段の幅ポイント']}ポイントしかないから。")
    print("    **決めているのは税率の高さではなく、その境目で税率が何ポイント上がるか**"
          "（上限の式の分母は 90% − 所得税率 × 1.021）。")
    print(f"    1ポイントあたりの効きは、税率が上がるほど必ず強くなります"
          f"（{_steps[0]['1ポイントあたりパーセント']:.3f}% →"
          f" {_steps[-1]['1ポイントあたりパーセント']:.3f}%）。")

    print("\n=== 同じ年収650万でも、社会保険料率1%で境目をまたぐ ===")
    for row in straddle(6_500_000):
        print(f"  {row['社会保険料率']:>4s}  課税所得{row['課税所得']:>10,}円  "
              f"所得税率{row['所得税率']:>4s}  上限{row['上限額']:>9,}円  "
              f"1つ前との差{row['1つ前との差']:>+9,}円")

    print("\n=== 目安表どおり寄付して一番損をする条件 ===")
    for k, v in worst_overrun().items():
        print(f"  {k}: {v:,}" if isinstance(v, int) else f"  {k}: {v}")


    print("\n=== 上限を超えて寄付しても、超過分は「全額」自己負担にはならない ===")
    _p = Person(income=6_000_000, social_rate=TYPICAL_SOCIAL_RATE)
    _rate = income_tax_rate(taxable_income(_p))
    print(f"  年収600万・社会保険料{TYPICAL_SOCIAL_RATE:.0%}・所得税率{_rate:.0%}"
          f"（上限 {limit(_p):,}円）")
    print("  頭打ちがあるのは**住民税の特例分だけ**。所得税ぶんと住民税の基本分は、")
    print("  超えた寄付にも効きます。だから自己負担になるのは超過額の一部です:")
    print("   寄付額     上限     超過      所得税    住民税基本   住民税特例    自己負担")
    for mult in (1.0, 1.5, 2.0, 3.0, 5.0):
        _d = int(limit(_p) * mult)
        o = out_of_pocket(_p, _d)
        print(f"  {o['寄付額']:>8,}  {o['上限額']:>7,}  {max(0, o['寄付額'] - o['上限額']):>7,}"
              f"  {o['所得税から戻る']:>9,.0f}  {o['住民税・基本分']:>9,.0f}"
              f"  {o['住民税・特例分']:>10,.0f}  **{o['自己負担']:>9,.0f}円**")
    _o3 = out_of_pocket(_p, limit(_p) * 3)
    _share = (_o3["自己負担"] - SELF_PAY) / (_o3["寄付額"] - _o3["上限額"])
    print(f"  超過額のうち自己負担になるのは **{_share * 100:.2f}%**"
          f"（＝ 1 − 所得税率{_rate:.0%}×1.021 − 住民税{RESIDENT_RATE:.0%}）。")
    print("  **「超えた分は全額自己負担」は、この2階ぶんを数え落としています。**")
    print("  そして、その超過はいちばん起きやすいのが**年収が下がった年**です")
    print("  （上限はその年の所得で決まるのに、目安表を引くのは去年の源泉徴収票だから）:")
    print("   去年比      今年の年収    今年の上限     超過      自己負担    2,000円の何倍")
    for row in income_drop_grid(6_000_000):
        print(f"  {-row['年収の下がり方'] * 100:>6.0f}%  {row['今年の年収']:>11,}円"
              f"  {row['今年の上限額']:>9,}円  {row['超過額']:>7,}円"
              f"  **{row['自己負担']:>9,.0f}円**  {row['自己負担の増え方']:>7.1f}倍")

    print("\n=== 扶養が1人ふえて枠が減る額は、1人目だけ深い（年収で場所が動く）===")
    _inc = 7_000_000
    print(f"  年収{_inc:,}円・社会保険料{TYPICAL_SOCIAL_RATE:.0%}:")
    print("   扶養   住民税の所得割   所得税の課税所得   所得税率      上限      1人ふえて減る額")
    for row in dependent_grid(_inc):
        d = row["1人ふえて減った額"]
        mark = "" if d is None else f"  **−{d:,}円**"
        print(f"  {row['扶養の人数']:>3}人  {row['住民税の所得割額']:>12,}円"
              f"  {row['所得税の課税所得']:>14,}円  {row['所得税率']:>8.0%}"
              f"  {row['上限額']:>9,}円{mark}")
    _dep = dependent_grid(_inc)
    _flat = _dep[-1]["1人ふえて減った額"]
    print(f"  段を割らない人の減りは {_flat:,}円で揃います"
          f"（＝ 33万円 × 10% × 20% ÷ (90% − {_dep[-1]['所得税率']:.0%}×1.021)）。")
    print(f"  この年収では**1人目だけ {_dep[1]['1人ふえて減った額']:,}円**"
          f"（{_dep[1]['1人ふえて減った額'] / _flat:.2f}倍）——"
          "扶養控除が所得税の課税所得も下げて、税率の段を割るから。")
    print("  **深くなる年収の帯は、速算表の段の数だけあります**（1万円刻みで走査）:")
    _rows = dependent_cliff()
    _bands: list[list[int]] = []
    for r in _rows:
        if _bands and r["年収"] - _bands[-1][1] == 10_000:
            _bands[-1][1] = r["年収"]
        else:
            _bands.append([r["年収"], r["年収"]])
    for lo_i, hi_i in _bands:
        a = next(r for r in _rows if r["年収"] == lo_i)
        b = next(r for r in _rows if r["年収"] == hi_i)
        print(f"    年収 {lo_i:,}円 〜 {hi_i:,}円"
              f"  所得税率 {a['扶養0人の所得税率']:.0%} → {a['扶養1人の所得税率']:.0%}"
              f"  減る額 {a['減った額']:,}円 〜 {b['減った額']:,}円")
    print(f"  帯の外なら {_flat:,}円ぐらいで済むところが、"
          f"帯の中では最大 {max(r['減った額'] for r in _rows):,}円。"
          "**同じ「扶養1人」で、場所によって桁がちがいます。**")
