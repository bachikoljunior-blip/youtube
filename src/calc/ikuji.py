"""育児休業給付を、**額面ではなく「働いていたときの手取り」と比べる。**

**2026-08-16 に追加。** `_template.py` を写して書いた1本目
（`docs/JOURNAL.md` 2026-08-16 00:1x の申し送り1 —— ひな型で何分になるかを測るため）。

## 一般の解説は、ここで止まる

    「育児休業給付金は、休業開始前の賃金の67パーセントが受け取れます」
    「社会保険料が免除されるので、実質8割くらいになります」

**「実質8割」は定数ではありません。** その比率は、
**働いていたときの手取り率の裏返し**なので、**月給によって違います。**

  - 給付の分子（67パーセント）は**額面に対する定率**
  - 比べる相手（働いていたときの手取り）は**累進課税で率が下がる**

つまり**月給が高い人ほど、手取りに対する比率は高く出ます。**
「8割」は、ある1点の月給でだけ正しい数字です。

**この表はどこにも無い。** そこを月給べつの金額で出す。

## 育児休業中に何が起き、何が起きないか（ここが計算の骨）

**受け取る側:**

  - 支給額 ＝ 休業開始時賃金日額 × 支給日数（原則30日）× 支給率
    （雇用保険法61条の7。**180日目までが67パーセント、181日目からは50パーセント**）
  - 休業開始時賃金日額 ＝ 休業開始前6か月の賃金総額 ÷ 180

**引かれない側（ここが「実質8割」の正体）:**

  - **非課税。** 所得税も住民税もかからない（雇用保険法12条）
  - **社会保険料は本人負担も事業主負担も免除**
    （健康保険法159条・厚生年金保険法81条の2）。
    **免除されても年金額は減りません**（保険料を納めたものとして扱われる）
  - **雇用保険料もかからない**（賃金が支払われていないため）

**引かれる側:**

  - **住民税は止まりません。** 前年の所得で決まるので、休んでいることと無関係にかかる。
    これは `shobyo.py` と同じ形で、**入力として扱います**（人によって額が違うため）

## 入れなかったもの

- **賞与は給付の算定に入りません**（3か月を超える期間ごとに支払われるものは
  雇用保険法上の「賃金」から除かれる）。**この表は賞与の無い月給だけで組んでいます。**
  賞与のある人は、**給付の側だけが下がる**ので、実際の比率はここより低く出ます
- **支給額には上限があります**（休業開始時賃金日額の上限。**毎年8月1日に改定**）。
  改定される値を画面に出すと古くなるので、**この表は上限に届かない月給帯だけを扱います。**
  月給45万円以上の人は、ここより比率が下がります
- **2025年に始まった出生後休業支援給付金（上乗せ）は入れていません。**
  対象期間も要件も別立てで、1本に2つの制度を混ぜると前提が追えなくなる
  （`shobyo.py` と同じ方針）
- 社会保険料率は入力に逃がしています（`docs/CONSTRAINTS.md` B4）。
  健康保険料率は都道府県ごとに違い、毎年3月に変わる
"""
from __future__ import annotations

from . import _checks
from . import tedori

ASSUMPTIONS = [
    "育児休業給付金は、休業開始前6か月の賃金の合計を180で割った1日あたりの額に、支給日数30日をかけて計算しています",
    "支給率は、休業を始めてから180日目までが67パーセント、181日目からは50パーセントとしています",
    "賞与のない月給だけで計算しています。賞与は給付の計算の基礎に入らないため、賞与がある人は実際の比率はこれより低くなります",
    "育児休業給付金は非課税なので、所得税も住民税もかかりません",
    "育児休業中は健康保険料と厚生年金保険料が本人負担も事業主負担も免除されるものとしています",
    "保険料が免除されても、将来の年金額は減らないものとして扱っています",
    "雇用保険料は賃金が支払われないため、かからないものとしています",
    "住民税は前年の所得で決まるため休んでも減りません。金額は人によって違うので入力として扱っています",
    "比べる相手の手取りは、給与収入だけで所得控除は基礎控除のみ、社会保険料は年収の15パーセントとして計算しています",
    "支給額の上限は毎年8月に改定されるため、この表は上限に届かない月給の範囲だけを扱っています",
    "2025年に始まった出生後休業支援給付金の上乗せは含めていません",
]

# ---- 制度の値。**長く動いていないものだけをここに置く** ----------------
RATE_FIRST = 0.67          # 180日目まで（雇用保険法61条の7第5項）
RATE_LATER = 0.50          # 181日目から（同）
FIRST_PERIOD_DAYS = 180    # 支給率が変わる境目
UNIT_DAYS = 30             # 支給単位期間の日数
WAGE_BASE_MONTHS = 6       # 休業開始時賃金日額の算定に使う月数
WAGE_BASE_DAYS = 180       # 同（6か月 = 180日として割る）

# 比べる相手（働いていたとき）の社会保険料率。**呼ぶ側で差し替えられる**
SOCIAL_RATE = 0.15

# 表に載せる月給の帯。**上限に届かない範囲だけ**（上の docstring を見ること）
MONTHLY_PAYS = (200_000, 250_000, 300_000, 350_000, 400_000, 450_000)


def wage_daily(monthly_pay: int) -> int:
    """休業開始時賃金日額。**6か月ぶんの賃金 ÷ 180。**

    月給が一定なら `月給 × 6 ÷ 180` = `月給 ÷ 30` と同じ額になる。
    **割る順番を変えても同じ値になるが、条文の形のまま書いておく**
    （賞与や月ごとの変動を足すときに、ここが分岐点になる）。
    """
    return int(monthly_pay * WAGE_BASE_MONTHS / WAGE_BASE_DAYS)


def benefit_month(monthly_pay: int, rate: float = RATE_FIRST) -> int:
    """1か月（30日）ぶんの育児休業給付金。"""
    return int(wage_daily(monthly_pay) * UNIT_DAYS * rate)


def working_net_month(monthly_pay: int, social_rate: float = SOCIAL_RATE) -> int:
    """**比べる相手。** 同じ月給で働き続けたときの、手取り月額。

    `tedori.take_home` をそのまま使う（税と社会保険の式を2か所に置かない）。
    賞与が無い前提なので、年収は月給の12倍。
    """
    year = tedori.take_home(monthly_pay * 12, social_rate)
    return year["手取り"] // 12


def compare(monthly_pay: int, rate: float = RATE_FIRST,
            resident_tax: int = 0, social_rate: float = SOCIAL_RATE) -> dict:
    """**この計算の主題。** 給付は、働いていたときの手取りの何パーセントか。"""
    benefit = benefit_month(monthly_pay, rate)
    net = working_net_month(monthly_pay, social_rate)
    left = benefit - resident_tax
    return {
        "monthly_pay": monthly_pay,
        "benefit": benefit,
        "resident_tax": resident_tax,
        "left": left,
        "working_net": net,
        "gross_ratio": benefit / monthly_pay,   # 額面比（67%に近い）
        "net_ratio": left / net,                # **手取り比。ここが出したい数字**
        "gap": net - left,                      # 1か月あたり手元がいくら減るか
    }


def compare_grid(rate: float = RATE_FIRST, resident_tax: int = 0) -> list[dict]:
    """月給べつ。**「実質8割」が月給でどう動くか。**"""
    check_tables()
    return [compare(p, rate, resident_tax) for p in MONTHLY_PAYS]


def phase_grid(monthly_pay: int = 300_000) -> list[dict]:
    """**181日目に何が起きるか。** 67パーセントの期と50パーセントの期を並べる。"""
    check_tables()
    return [
        {"phase": f"1〜{FIRST_PERIOD_DAYS}日目", "rate": RATE_FIRST,
         **compare(monthly_pay, RATE_FIRST)},
        {"phase": f"{FIRST_PERIOD_DAYS + 1}日目〜", "rate": RATE_LATER,
         **compare(monthly_pay, RATE_LATER)},
    ]


def exemption_grid(social_rate: float = SOCIAL_RATE) -> list[dict]:
    """**免除だけで、いくら得しているか。** 給付とは別勘定の分子。

    比べているのは「働いていたら払っていた社会保険料の本人負担」で、
    育休中はこれが**まるごとゼロ**になる。
    """
    check_tables()
    out = []
    for p in MONTHLY_PAYS:
        month = int(p * social_rate)
        out.append({"monthly_pay": p, "month": month,
                    "half_year": month * 6, "year": month * 12})
    return out


def year_grid(resident_tax: int = 0) -> list[dict]:
    """**1年まるごと休んだとき**の合計。180日は67パーセント、残りは50パーセント。"""
    check_tables()
    first_months = FIRST_PERIOD_DAYS / UNIT_DAYS          # 6か月
    later_months = 12 - first_months                      # 6か月
    out = []
    for p in MONTHLY_PAYS:
        b1 = benefit_month(p, RATE_FIRST) * first_months
        b2 = benefit_month(p, RATE_LATER) * later_months
        total = int(b1 + b2) - resident_tax * 12
        working = working_net_month(p) * 12
        out.append({"monthly_pay": p, "first": int(b1), "later": int(b2),
                    "total": total, "working": working,
                    "gap": working - total, "ratio": total / working})
    return out


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(RATE_FIRST, 0.67, "育児休業給付金の支給率（180日目まで）",
                      source="雇用保険法61条の7第5項")
    _checks.statutory(RATE_LATER, 0.50, "育児休業給付金の支給率（181日目から）",
                      source="雇用保険法61条の7第5項")
    _checks.ratio(RATE_FIRST, "支給率（180日目まで）")
    _checks.ratio(RATE_LATER, "支給率（181日目から）")
    _checks.ratio(SOCIAL_RATE, "働いていたときの社会保険料率")
    _checks.greater(RATE_FIRST, RATE_LATER,
                    "180日目までの支給率が181日目からの支給率以下")
    if WAGE_BASE_DAYS != WAGE_BASE_MONTHS * UNIT_DAYS:
        raise _checks.TableError(
            f"賃金日額の算定期間が合わない: {WAGE_BASE_MONTHS}か月 と {WAGE_BASE_DAYS}日")

    # 2. 丸めと算式（月給30万 → 日額1万円 → 30日ぶんの67% = 20万1千円）
    _checks.rounding(wage_daily(300_000), 10_000, "月給30万円の休業開始時賃金日額")
    _checks.rounding(benefit_month(300_000), 201_000, "月給30万円の1か月ぶんの給付")

    # 3. 計算の向き（**この計算の主題そのもの**）
    # 月給が増えれば給付も増える
    _checks.increases_with(benefit_month, [200_000, 300_000, 400_000],
                           "月給が増えたのに給付が増えていない")
    # **手取り比は額面比を必ず上回る**（免除と非課税のぶん）。ここが動画の骨
    for p in MONTHLY_PAYS:
        r = compare(p)
        _checks.greater(r["net_ratio"], r["gross_ratio"],
                        f"月給{p:,}円で、手取り比が額面比以下")
    # **手取り比は月給が上がるほど高くなる**（比べる相手の手取り率が下がるため）
    _checks.increases_with(lambda p: compare(p)["net_ratio"], MONTHLY_PAYS,
                           "月給が上がったのに手取り比が上がっていない")
    # 額面比は月給によらずほぼ一定（定率なので）
    ratios = [compare(p)["gross_ratio"] for p in MONTHLY_PAYS]
    if max(ratios) - min(ratios) > 0.005:
        raise _checks.TableError(
            f"額面比が月給で動いている（定率のはず）: {min(ratios):.3f}〜{max(ratios):.3f}")
    # 181日目からは必ず下がる
    _checks.greater(compare(300_000, RATE_FIRST)["net_ratio"],
                    compare(300_000, RATE_LATER)["net_ratio"],
                    "180日目までの手取り比が181日目からの手取り比以下")
    # 住民税を払えば手元は減る
    _checks.decreases_with(lambda t: compare(300_000, resident_tax=t)["left"],
                           [0, 10_000, 15_000, 20_000],
                           "住民税が増えたのに手元に残る額が減っていない")
    # 表に同じ行が2つ入っていない（帯を書き写すときに実際に起きる）
    _checks.unique_by([{"p": p} for p in MONTHLY_PAYS], lambda r: r["p"], "月給の帯")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 育児休業給付の67パーセントは、働いていたときの手取りの何パーセントか ===")
    print(f"{'月給':>10s} {'給付30日ぶん':>12s} {'働いた場合の手取り':>16s} "
          f"{'額面比':>7s} {'手取り比':>8s}  {'1か月の差'}")
    for r in compare_grid():
        print(f"{r['monthly_pay']:9,d}円 {r['benefit']:11,d}円 {r['working_net']:15,d}円 "
              f"{r['gross_ratio']:6.1%} {r['net_ratio']:7.1%}  {r['gap']:,}円")

    print("\n=== 181日目に支給率が67から50に下がると、手取り比はいくつになるか（月給30万円）===")
    print(f"{'期間':>12s} {'支給率':>7s} {'給付30日ぶん':>12s} {'手取り比':>8s}  {'1か月の差'}")
    for r in phase_grid():
        print(f"{r['phase']:>12s} {r['rate']:6.0%} {r['benefit']:11,d}円 "
              f"{r['net_ratio']:7.1%}  {r['gap']:,}円")

    print("\n=== 住民税は育休中も止まらない。月1万5千円を払うと手取り比はいくつか ===")
    print(f"{'月給':>10s} {'給付30日ぶん':>12s} {'住民税':>9s} {'手元に残る':>11s} {'手取り比'}")
    for r in compare_grid(resident_tax=15_000):
        print(f"{r['monthly_pay']:9,d}円 {r['benefit']:11,d}円 {r['resident_tax']:8,d}円 "
              f"{r['left']:10,d}円 {r['net_ratio']:8.1%}")

    print("\n=== 社会保険料の免除だけで、いくら払わずに済んでいるか ===")
    print(f"{'月給':>10s} {'1か月':>10s} {'半年':>11s} {'1年'}")
    for r in exemption_grid():
        print(f"{r['monthly_pay']:9,d}円 {r['month']:9,d}円 {r['half_year']:10,d}円 "
              f"{r['year']:,}円")

    print("\n=== 1年まるごと育児休業をとると、働き続けた場合と手元でいくら違うか ===")
    print(f"{'月給':>10s} {'前半6か月':>12s} {'後半6か月':>12s} {'1年の合計':>12s} "
          f"{'働いた場合':>12s} {'差':>11s}  {'手取り比'}")
    for r in year_grid():
        print(f"{r['monthly_pay']:9,d}円 {r['first']:11,d}円 {r['later']:11,d}円 "
              f"{r['total']:11,d}円 {r['working']:11,d}円 {r['gap']:10,d}円  {r['ratio']:7.1%}")
