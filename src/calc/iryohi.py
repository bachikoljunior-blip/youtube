"""医療費控除で、実際にいくら戻るかを計算する。

**「取り返せる」×「対象が広い」を狙って作った**（2026-08-08）。

これまでの実測で、伸びる動画には2つの特徴があった:

    年末調整「扶養控除は5年戻せる」 1508回 … 取り返せる・対象が広い
    残業代「年8万円の差」            769回 … 損している・対象は中くらい
    住宅ローン控除「6万円戻らず」     438回 … 損している・対象が狭い

医療費控除は**誰でも対象になり得て、しかも5年さかのぼれる**。
どちらの軸でも上に来る題材のはず（これは推測。実績で確かめる）。

## 計算の中身

    控除額 = 支払った医療費 － 保険で補填された額 － 足切り
    足切り = min(10万円, 総所得金額等 × 5%)     ← **ここが誤解の的**
    還付   = 控除額 × 所得税率 × 1.021 ＋ 控除額 × 住民税率

**「10万円を超えないと使えない」は総所得200万円以上の人の話。**
総所得が200万円未満なら足切りは5%なので、10万円未満でも使える。
そこを金額で出す。どこにも表になっていない。

セルフメディケーション税制は入れない。選択制で条件が別立てになり、
1本の動画に2つの制度を混ぜると前提が追えなくなる。
"""
from __future__ import annotations

ASSUMPTIONS = [
    "足切りは「10万円」と「総所得金額等の5パーセント」の少ないほうで計算しています",
    "控除の上限は200万円です",
    "所得税は復興特別所得税2.1パーセントを含めています",
    "住民税は標準税率10パーセントで計算しています",
    "保険金や高額療養費で補填された額は、支払った医療費から引いています",
    "更正の請求ができる5年をさかのぼれる期間としています",
    "セルフメディケーション税制は含めていません（選択制で条件が別立てのため）",
    "生計を一にする家族の医療費は、まとめて1人が申告できるものとしています",
    "所得税率は仮定です。共働きの比較では、高いほうを総所得500万円で所得税率20パーセント、"
    "低いほうを所得税率5パーセントとして置いています。"
    "税率は課税所得で決まるもので、足切りを決める総所得金額等から計算したものではありません",
]

# 制度の値。**改正が続くものは入力に逃がす**（docs/CONSTRAINTS.md B4）が、
# ここは長く動いていない。
FLOOR_CAP = 100_000          # 足切りの上限（円）
FLOOR_RATE = 0.05            # 足切りの率（総所得金額等に対して）
DEDUCTION_CAP = 2_000_000    # 控除額の上限（円）
RECONSTRUCTION = 0.021       # 復興特別所得税
RESIDENT_RATE = 0.10         # 住民税の標準税率
RECLAIM_YEARS = 5            # 更正の請求ができる期間

# 所得税の速算表の税率。課税所得ではなく「総所得金額等」で足切りが決まるので、
# この2つを取り違えないこと。
INCOME_TAX_RATES = [0.05, 0.10, 0.20, 0.23, 0.33, 0.40, 0.45]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    if not 0 < FLOOR_RATE < 1:
        raise ValueError(f"足切りの率が範囲外: {FLOOR_RATE}")
    if FLOOR_CAP <= 0 or DEDUCTION_CAP <= FLOOR_CAP:
        raise ValueError("足切りの上限と控除の上限の大小が逆")
    if not INCOME_TAX_RATES == sorted(INCOME_TAX_RATES):
        raise ValueError("所得税率が昇順に並んでいない")

    # 足切りは総所得200万円で切り替わる（200万×5% = 10万）
    if floor_amount(2_000_000) != FLOOR_CAP:
        raise ValueError("総所得200万円で足切りが10万円にならない")
    if floor_amount(1_000_000) >= FLOOR_CAP:
        raise ValueError("総所得100万円の足切りが10万円を下回っていない")

    # 医療費が足切り以下なら控除は0
    if deduction(50_000, 0, 3_000_000) != 0:
        raise ValueError("足切り以下なのに控除が出ている")
    # 医療費が増えれば控除も増える
    if not deduction(300_000, 0, 3_000_000) > deduction(200_000, 0, 3_000_000):
        raise ValueError("医療費が増えたのに控除が増えていない")
    # 税率が高いほど戻る額は大きい
    if not refund(200_000, 0, 3_000_000, 0.20)["total"] > refund(200_000, 0, 3_000_000, 0.05)["total"]:
        raise ValueError("税率が高いのに戻る額が増えていない")

    # --- 共働きの入れ替わり（crossover_paid の主題そのもの）-------------
    # 足切りが同じなら入れ替わらない。**この向きが変わったら節の答えが逆になる**
    if crossover_paid(5_000_000, 0.20, 3_000_000, 0.05) is not None:
        raise ValueError("足切りが同じ（どちらも総所得200万円以上）なのに入れ替わりが出ている")
    x = crossover_paid(5_000_000, 0.20, 1_600_000, 0.05)
    if x is None:
        raise ValueError("足切りが下がる側があるのに入れ替わりが出ていない")
    if not floor_amount(5_000_000) < x:
        raise ValueError("入れ替わりの額が高いほうの足切り以下")
    # 境目の両側で、勝つ側が実際に入れ替わること（式を解いた結果の裏取り）
    below = (refund(x - 10_000, 0, 1_600_000, 0.05)["total"]
             > refund(x - 10_000, 0, 5_000_000, 0.20)["total"])
    above = (refund(x + 10_000, 0, 5_000_000, 0.20)["total"]
             > refund(x + 10_000, 0, 1_600_000, 0.05)["total"])
    if not (below and above):
        raise ValueError(f"境目 {x} 円の前後で勝つ側が入れ替わっていない")

    # --- 分けると損する（split_loss の主題そのもの）---------------------
    floor = floor_amount(3_000_000)
    # 小さいほうが足切り以上なら、損失は足切りぶんで頭打ち（医療費に依らず一定）
    a = split_loss(400_000, floor, 3_000_000, 0.20)["lost_deduction"]
    b = split_loss(600_000, 200_000, 3_000_000, 0.20)["lost_deduction"]
    if not a == b == floor:
        raise ValueError(f"足切り以上の分担で損失が一定になっていない: {a} {b} {floor}")
    # 小さいほうが足切り未満なら、その全額が消える
    c = split_loss(400_000, 60_000, 3_000_000, 0.20)["lost_deduction"]
    if c != 60_000:
        raise ValueError(f"足切り未満の分担で、全額が消えていない: {c}")
    # 分けて得になることは無い
    if split_loss(400_000, 0, 3_000_000, 0.20)["lost_deduction"] != 0:
        raise ValueError("分担0なのに損失が出ている")


def floor_amount(total_income: int) -> int:
    """足切り。**10万円と総所得の5%の、少ないほう。**

    「10万円を超えないと医療費控除は使えない」と言われることが多いが、
    それは総所得200万円以上の人の話。**200万円未満なら足切りは下がる。**
    """
    return int(min(FLOOR_CAP, total_income * FLOOR_RATE))


def deduction(paid: int, reimbursed: int, total_income: int) -> int:
    """控除額。マイナスにはならず、上限で頭打ちになる。"""
    net = max(paid - reimbursed, 0)
    return max(0, min(net - floor_amount(total_income), DEDUCTION_CAP))


def refund(paid: int, reimbursed: int, total_income: int, rate: float) -> dict:
    """実際に戻る額。所得税ぶんは現金、住民税ぶんは翌年度の負担減。"""
    d = deduction(paid, reimbursed, total_income)
    income_tax = int(d * rate * (1 + RECONSTRUCTION))
    resident = int(d * RESIDENT_RATE)
    return {
        "deduction": d,
        "floor": floor_amount(total_income),
        "income_tax_refund": income_tax,
        "resident_tax_cut": resident,
        "total": income_tax + resident,
        "five_years": (income_tax + resident) * RECLAIM_YEARS,
    }


def coefficient(rate: float) -> float:
    """控除額1円あたり、実際に戻る額。**所得税ぶん＋住民税ぶん。**

    所得税は復興特別所得税を上乗せ、住民税は標準税率。
    `refund()` は円未満を切り捨てるが、こちらは境目を解くために丸めない。
    """
    return rate * (1 + RECONSTRUCTION) + RESIDENT_RATE


def crossover_paid(
    high_income: int, high_rate: float, low_income: int, low_rate: float
) -> int | None:
    """**共働きで、どちらが申告すると得か**が入れ替わる医療費の額。

    一般の解説はここで止まる ——「税率の高いほうが申告するのが得」。
    **足切りが総所得の5パーセントで決まることを併せて考えると、そうならない範囲がある。**
    総所得200万円未満の側は足切りが10万円より下がるので、控除額が大きくなる。
    医療費が小さいうちは、その差のほうが税率の差より大きい。

    戻り値は「これを**超えたら**税率の高いほうが得になる」医療費（円）。
    入れ替わりが起きないときは None（＝どの額でも税率の高いほうが得）。
    """
    fh, fl = floor_amount(high_income), floor_amount(low_income)
    ch, cl = coefficient(high_rate), coefficient(low_rate)
    if ch <= cl or fh <= fl:
        return None  # 足切りが同じか、税率の高い側が有利なまま。入れ替わらない
    paid = (fh * ch - fl * cl) / (ch - cl)
    return int(-(-paid // 1))  # 「超えたら」なので切り上げ


def split_loss(total_paid: int, smaller_share: int, income: int, rate: float) -> dict:
    """**世帯の医療費を2人に分けて申告すると、足切りがもう1回引かれる。**

    医療費控除は生計を一にする親族の分をまとめて1人が申告できる。
    分けると足切りが人数分だけ引かれるので、**同じ医療費でも戻る額が減る。**
    減り方は2つの帯に分かれ、境目は足切りそのもの:

        小さいほうが足切り未満  → **その全額が消える**（控除に1円も乗らない）
        小さいほうが足切り以上  → 損失は**足切りぶんで頭打ち**（医療費が増えても一定）

    どちらも2人の総所得が同じ場合の話（足切りが同じ）。
    """
    if not 0 <= smaller_share <= total_paid / 2:
        raise ValueError(f"小さいほうの分担が範囲外: {smaller_share}")
    larger = total_paid - smaller_share
    together = deduction(total_paid, 0, income)
    apart = deduction(larger, 0, income) + deduction(smaller_share, 0, income)
    lost_deduction = together - apart
    return {
        "smaller_share": smaller_share,
        "deduction_together": together,
        "deduction_apart": apart,
        "lost_deduction": lost_deduction,
        "lost_yen": int(lost_deduction * coefficient(rate)),
        "capped": smaller_share >= floor_amount(income),
    }


def claimant_grid(
    high_income: int, high_rate: float, low_rate: float
) -> list[dict]:
    """低いほうの総所得べつに、入れ替わりが起きる医療費。"""
    check_tables()
    rows = []
    for li in (800_000, 1_200_000, 1_600_000, 2_000_000, 3_000_000):
        rows.append({
            "low_income": li,
            "low_floor": floor_amount(li),
            "crossover": crossover_paid(high_income, high_rate, li, low_rate),
        })
    return rows


def split_grid(total_paid: int, income: int, rate: float) -> list[dict]:
    """分担べつの損失。**足切りで折れる。**"""
    check_tables()
    floor = floor_amount(income)
    shares = sorted({0, 30_000, 60_000, floor, 90_000, 120_000, total_paid // 2})
    return [split_loss(total_paid, s, income, rate)
            for s in shares if 0 <= s <= total_paid / 2]


def floor_grid() -> list[dict]:
    """総所得べつの足切り。**「10万円」が効かない範囲を見せる。**"""
    check_tables()
    return [
        {"total_income": ti, "floor": floor_amount(ti), "capped": floor_amount(ti) == FLOOR_CAP}
        for ti in (800_000, 1_200_000, 1_600_000, 2_000_000, 3_000_000, 5_000_000)
    ]


def refund_grid(total_income: int, rate: float) -> list[dict]:
    """医療費べつに、いくら戻るか。"""
    check_tables()
    return [
        dict(paid=paid, **refund(paid, 0, total_income, rate))
        for paid in (80_000, 100_000, 150_000, 200_000, 300_000, 500_000)
    ]


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 総所得べつの足切り（10万円が効かない範囲がある）===")
    print(f"{'総所得':>10s} {'足切り':>9s}  {'10万円で頭打ちか'}")
    for r in floor_grid():
        print(f"{r['total_income']:9,d}円 {r['floor']:8,d}円  {'頭打ち' if r['capped'] else '5%のほうが小さい'}")

    for ti, rate in ((3_000_000, 0.10), (1_600_000, 0.05)):
        print(f"\n=== 総所得{ti:,}円・所得税率{rate:.0%} のとき、医療費べつに戻る額 ===")
        print(f"{'支払った医療費':>12s} {'控除額':>9s} {'所得税で戻る':>10s} {'住民税が減る':>10s} {'合計':>9s} {'5年分':>10s}")
        for r in refund_grid(ti, rate):
            print(f"{r['paid']:11,d}円 {r['deduction']:8,d}円 {r['income_tax_refund']:9,d}円 "
                  f"{r['resident_tax_cut']:9,d}円 {r['total']:8,d}円 {r['five_years']:9,d}円")

    HI, HR, LR = 5_000_000, 0.20, 0.05
    print(f"\n=== 共働き 税率{HR:.0%}の側が申告して損になる医療費（相手の総所得べつ）===")
    print(f"  高いほう: 総所得{HI:,}円・所得税率{HR:.0%}・足切り{floor_amount(HI):,}円")
    print(f"  低いほう: 所得税率{LR:.0%}")
    print(f"{'低いほうの総所得':>14s} {'低いほうの足切り':>15s}  {'どちらが申告すると得か'}")
    for r in claimant_grid(HI, HR, LR):
        x = r["crossover"]
        print(f"{r['low_income']:13,d}円 {r['low_floor']:14,d}円  "
              + (f"医療費 {x:,}円 以下なら**低いほう**が得（超えたら高いほう）" if x
                 else "どの医療費でも高いほうが得（足切りが同じ）"))

    TOTAL, TI2, RATE2 = 400_000, 3_000_000, 0.20
    print(f"\n=== 医療費{TOTAL:,}円を夫婦で分けて申告すると、いくら捨てるか ===")
    print(f"  総所得はどちらも{TI2:,}円・所得税率{RATE2:.0%}・足切り{floor_amount(TI2):,}円")
    print(f"{'小さいほうの分担':>14s} {'まとめた控除':>11s} {'分けた控除':>10s} {'消えた控除':>10s} {'捨てた額':>9s}")
    for r in split_grid(TOTAL, TI2, RATE2):
        print(f"{r['smaller_share']:13,d}円 {r['deduction_together']:10,d}円 "
              f"{r['deduction_apart']:9,d}円 {r['lost_deduction']:9,d}円 {r['lost_yen']:8,d}円"
              + ("  ← 足切りぶんで頭打ち" if r["capped"] else ""))
