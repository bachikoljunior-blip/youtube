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
