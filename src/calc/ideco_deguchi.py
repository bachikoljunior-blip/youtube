"""iDeCo と新NISA、先に埋めるべきはどちらか。**出口の税を入れると、掛金を増やすほど損になる帯がある。**

一般の解説はここで止まります ——「iDeCo は掛金が全額所得控除。新NISA には所得控除が
無い。だから節税だけ見れば iDeCo が先」。

**それは入口だけの話です。** iDeCo は受け取るときに課税されます（退職所得）。
新NISA は受け取るときに1円もかかりません。だから両者の差は

    iDeCo の得 ＝ 掛けた年に戻った税の合計 − 受け取るときに払う税

であって、**右の項は掛金と利回りで決まります。** 退職所得控除は勤続20年までが
1年40万円、20年を超えた部分が1年70万円 —— **年数に比例して伸びるだけ**です。
ところが残高は利回りで指数に膨らむので、**追い越した時点から得が減りはじめます。**

この計算は `ideco.saving`（掛けた年の税を2回計算してその差を取る）と
`taishoku.tax`（退職所得控除・2分の1課税・復興特別所得税）を**そのまま繋いだ**ものです。
どちらも既に表として検査を通っているので、ここで新しく置いた仮定は
「その年の年収」「利回り」「受け取りが iDeCo 一本であること」の3つだけです。

この表が出す数字（実行して出たものを、丸めずに写しています）:

- **年数はいくら伸ばしても出口の税を生みません。** 年収5,000,000円・会社員の上限
  （年276,000円）・利回り3パーセントなら、10年でも40年でも出口の税は **0円** です。
  40年で残高 21,435,070円 に対し控除は 22,000,000円 —— **控除のほうが後ろにいます**
- **効きを落とすのは利回りのほうです。** 同じ20年で、利回り5パーセントなら出口の税
  119,480円（戻った税 1,115,600円 の **10.71パーセント**）、
  7パーセントなら **315,363円**（**28.27パーセント**）
- **出口の税が初めて1円以上になる利回りは、会社員の上限・20年で 3.5パーセント**です。
  30年に伸ばしても **3.6パーセント** で、**年数を足しても 0.1ポイントしか動きません**
- **掛金を増やすと、得が減ることがあります。** 自営業の上限（年816,000円）は
  会社員の上限の **2.9565217391304346倍** ですが、20年・利回り3パーセントでの
  iDeCo の得は **1,115,600円 → 1,060,896円** と **54,704円 減ります**。
  戻った税は 1,115,600円 → 2,853,120円 と増えるのに、出口の税が
  0円 → 1,792,224円 になるためです。**自営業の上限では、利回り0パーセントでも
  出口の税がかかります**（残高 16,320,000円 に対し控除 8,000,000円）
- **入口の戻りは年収に対して単調ではありません。** 年収3,000,000円 で 833,800円、
  4,000,000円 で **833,780円** —— **20円 下がります。**
  ただし20円は主張になりません（端数の切り捨てが動いただけ）。表には出します
"""
from __future__ import annotations

from . import _checks
from .ideco import SALARIED_CAP, SELF_CAP, saving
from .taishoku import deduction, tax

ASSUMPTIONS = [
    "給与収入のみの人を想定しています。所得控除は基礎控除だけで、社会保険料は年収の15パーセントとして置いています",
    "掛金は毎年おなじ額を、年のはじめに1回入れたものとして積み上げています",
    "利回りは毎年おなじ率で複利にしています。実際の運用は年ごとに上下します",
    "受け取りは一時金1回で、退職所得控除の勤続年数には掛金を出した年数をそのまま当てています",
    "会社の退職金や、他の一時金と同じ年に受け取る場合は入れていません。重なると控除を分け合うので出口の税はここより増えます",
    "戻った税は、掛けた各年の年収が変わらないものとして同じ額を年数ぶん足しています",
    "新NISA は掛金の所得控除が無く、受け取るときの税も無いので、この表では所得税・住民税ともに0円として置いています",
    "iDeCo・新NISA とも運用益は非課税なので、同じ利回りなら受け取る前の残高は同じです。差がつくのは入口の控除と出口の税だけです",
]

#: **画面に出す標本。** ここを `__main__` 側で書き直さないこと。
SCAN_INCOMES = (3_000_000, 4_000_000, 5_000_000, 6_000_000,
                8_000_000, 10_000_000)
SCAN_YEARS = (10, 20, 30, 40)
SCAN_RATES = (0.0, 0.03, 0.05, 0.07)


def balance(premium: int, years: int, rate: float) -> int:
    """年のはじめに `premium` を入れて `rate` で回した `years` 年後の残高。"""
    total = 0.0
    for _ in range(years):
        total = (total + premium) * (1 + rate)
    return int(total)


def entry_saving(income: int, premium: int, years: int) -> int:
    """掛けた年に戻った税の、`years` 年ぶんの合計。"""
    return saving(income, premium)["節税額"] * years


def exit_tax(premium: int, years: int, rate: float) -> dict:
    """受け取るときに払う税。**退職所得控除は掛けた年数で決まる。**"""
    bal = balance(premium, years, rate)
    t = tax(bal, years)
    return {"残高": bal, "退職所得控除": deduction(years),
            "課税退職所得": t["taxable"], "出口の税": t["total"]}


def verdict(income: int, premium: int, years: int, rate: float) -> dict:
    """iDeCo が新NISA より得か。**得 ＝ 入口で戻った税 − 出口の税。**"""
    got = entry_saving(income, premium, years)
    out = exit_tax(premium, years, rate)
    net = got - out["出口の税"]
    return {
        "年収": income, "掛金": premium, "年数": years, "利回り": rate,
        "戻った税": got, "残高": out["残高"],
        "退職所得控除": out["退職所得控除"],
        "出口の税": out["出口の税"],
        "iDeCoの得": net,
        "持っていかれる割合": out["出口の税"] / got if got else 0.0,
        "先に埋めるべき": "iDeCo" if net > 0 else "新NISA",
    }


def years_table(income: int = 5_000_000, premium: int = SALARIED_CAP,
                rate: float = 0.03) -> list[dict]:
    """年数べつ。**控除は年数で伸び、残高は年数で膨らむ。どちらが速いか。**"""
    return [verdict(income, premium, y, rate) for y in SCAN_YEARS]


def rate_table(income: int = 5_000_000, premium: int = SALARIED_CAP,
               years: int = 20) -> list[dict]:
    """利回りべつ。**利回りは入口を1円も増やさず、出口だけを増やす。**"""
    return [verdict(income, premium, years, r) for r in SCAN_RATES]


def income_table(premium: int = SALARIED_CAP, years: int = 20,
                 rate: float = 0.03) -> list[dict]:
    """年収べつ。**入口だけが年収で動く。出口は年収と無関係。**"""
    return [verdict(i, premium, years, rate) for i in SCAN_INCOMES]


def cap_table(income: int = 5_000_000, years: int = 20,
              rate: float = 0.03) -> list[dict]:
    """掛金の上限べつ（会社員と自営業）。**入口が3倍なら出口は3倍では済まない。**"""
    return [verdict(income, p, years, rate)
            for p in (SALARIED_CAP, SELF_CAP)]


def crossover_rate(premium: int = SALARIED_CAP,
                   years: int = 20) -> float | None:
    """**出口の税が初めて1円以上になる利回り**（0.1パーセントきざみ）。

    ここを超えると、利回りを上げるほど iDeCo の取り分が減ります。
    見つからなければ None。

    **年収を引数に取りません。** 出口の税は退職所得だけで決まり、
    その年の年収は1円も効かないからです（`income_table` の「出口の税」列が
    どの年収でも同じなのが、その裏です）。
    """
    for step in range(0, 301):
        r = step / 1000
        if exit_tax(premium, years, r)["出口の税"] > 0:
            return r
    return None


def check_tables() -> None:
    """繋ぎ方と、表の向きを確かめる。"""

    # 1. 借りている値が、借りた先のままであること。
    _checks.statutory(SALARIED_CAP, 276_000, "会社員（企業年金なし）の年間上限",
                      source="確定拠出年金法・同施行令")
    _checks.statutory(SELF_CAP, 816_000, "自営業の年間上限",
                      source="確定拠出年金法・同施行令")
    _checks.statutory(deduction(20), 8_000_000, "勤続20年の退職所得控除",
                      source="所得税法30条")
    _checks.statutory(deduction(30), 15_000_000, "勤続30年の退職所得控除",
                      source="所得税法30条")

    # 2. 積み上げの向き。**利回り0なら、残高は掛金×年数そのもの。**
    _checks.rounding(balance(SALARIED_CAP, 20, 0.0), SALARIED_CAP * 20,
                     "利回り0の20年後の残高")
    _checks.increases_with(lambda r: balance(SALARIED_CAP, 20, r),
                           [0.0, 0.03, 0.05, 0.07],
                           "利回りが上がったのに残高が増えていない")
    _checks.increases_with(lambda y: balance(SALARIED_CAP, y, 0.03),
                           [10, 20, 30, 40],
                           "年数が伸びたのに残高が増えていない")

    # 3. **主題その1**: 入口は年収で動くが、出口は年収で動かない。
    outs = {r["出口の税"] for r in income_table()}
    _checks.rounding(len(outs), 1, "年収を変えたのに出口の税の種類が1つでない")
    # **単調ではありません。** 年収3,000,000円 → 4,000,000円 で戻った税は
    # 833,800円 → 833,780円 と **20円 下がります**（掛金で削った後の課税所得が
    # どの区分に落ちるかで、住民税と所得税の端数の切り捨てが動くため）。
    # **20円は主張になりません** —— 表に出しはしますが、ここで確かめるのは
    # 「年収の端から端では増えている」ことだけです。
    _checks.greater(entry_saving(SCAN_INCOMES[-1], SALARIED_CAP, 20),
                    entry_saving(SCAN_INCOMES[0], SALARIED_CAP, 20),
                    "年収の端から端で戻った税が増えていない")

    # 4. **主題その2**: 利回りは入口を1円も動かさず、出口だけを押し上げる。
    ins = {r["戻った税"] for r in rate_table()}
    _checks.rounding(len(ins), 1, "利回りを変えたのに戻った税が動いている")
    _checks.never_decreases(lambda r: exit_tax(SALARIED_CAP, 20, r)["出口の税"],
                            [0.0, 0.03, 0.05, 0.07],
                            "利回りが上がったのに出口の税が減っている")
    _checks.decreases_with(lambda r: verdict(5_000_000, SALARIED_CAP, 20, r)["iDeCoの得"],
                           [0.03, 0.05, 0.07],
                           "利回りが上がったのに iDeCo の得が減っていない")

    # 5. **主題その3**: 掛金が3倍でも、出口の税は3倍では済まない。
    caps = cap_table()
    _checks.greater(caps[1]["出口の税"] / max(caps[0]["出口の税"], 1),
                    caps[1]["掛金"] / caps[0]["掛金"],
                    "出口の税の倍率が掛金の倍率を超えていない（控除が固定なのに効いていない）")

    # 6. 控除は年数で伸びること。**伸びなければ主題そのものが消えます。**
    _checks.increases_with(deduction, [10, 20, 30, 40],
                           "年数が伸びたのに退職所得控除が増えていない")

    _checks.unique_by(years_table(), lambda r: r["年数"], "年数")
    _checks.unique_by(rate_table(), lambda r: r["利回り"], "利回り")
    _checks.unique_by(income_table(), lambda r: r["年収"], "年収")
    _checks.assumption_values(ASSUMPTIONS, name="ideco_deguchi")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 年数を伸ばすと、退職所得控除と残高のどちらが速く伸びるか ===")
    for row in years_table():
        print(f"  {row['年数']:>2}年  戻った税 {row['戻った税']:>10,.0f}円"
              f"  残高 {row['残高']:>12,.0f}円"
              f"  控除 {row['退職所得控除']:>11,.0f}円"
              f"  出口の税 {row['出口の税']:>10,.0f}円"
              f"  → iDeCoの得 {row['iDeCoの得']:>10,.0f}円")

    print("\n=== 利回りは入口を1円も増やさず、出口だけを増やす ===")
    for row in rate_table():
        print(f"  利回り {row['利回り']:>5.1%}"
              f"  戻った税 {row['戻った税']:>10,.0f}円"
              f"  残高 {row['残高']:>12,.0f}円"
              f"  出口の税 {row['出口の税']:>10,.0f}円"
              f"（戻った税の {row['持っていかれる割合']:>6.2%}）"
              f"  → iDeCoの得 {row['iDeCoの得']:>10,.0f}円")

    print("\n=== 年収べつ。入口だけが動き、出口は1円も動かない ===")
    for row in income_table():
        print(f"  年収 {row['年収']:>10,.0f}円"
              f"  戻った税 {row['戻った税']:>10,.0f}円"
              f"  出口の税 {row['出口の税']:>10,.0f}円"
              f"  → iDeCoの得 {row['iDeCoの得']:>10,.0f}円"
              f"  先に埋めるべき {row['先に埋めるべき']}")

    print("\n=== 掛金の上限べつ。入口が3倍でも、出口は3倍では済まない ===")
    for row in cap_table():
        print(f"  掛金 {row['掛金']:>9,.0f}円/年"
              f"  戻った税 {row['戻った税']:>10,.0f}円"
              f"  残高 {row['残高']:>12,.0f}円"
              f"  控除 {row['退職所得控除']:>11,.0f}円"
              f"  出口の税 {row['出口の税']:>10,.0f}円"
              f"  → iDeCoの得 {row['iDeCoの得']:>10,.0f}円")

    print("\n=== 出口の税が初めて1円以上になる利回り（0.1パーセントきざみで探す）===")
    for label, prem, yrs in (("会社員の上限・20年", SALARIED_CAP, 20),
                             ("会社員の上限・30年", SALARIED_CAP, 30),
                             ("自営業の上限・20年", SELF_CAP, 20),
                             ("自営業の上限・30年", SELF_CAP, 30)):
        r = crossover_rate(prem, yrs)
        print(f"  {label:<16} → " + ("見つからない" if r is None else f"利回り {r:.1%}"))
