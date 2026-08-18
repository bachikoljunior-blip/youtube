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

from . import kogaku

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
    "高額療養費と合わせる計算は、70歳未満・窓口3割・同じ月の同じ医療機関にかかった医療費として置いています",
    "高額療養費の区分は標準報酬月額で決まります。区分ウは28万円から50万円までで、限度額は8万100円に"
    "医療費が26万7000円を超えた分の1パーセントを足した額です",
    "高額療養費で戻る額は「保険で補填された額」なので、医療費控除の対象からは差し引いています",
    "高額療養費と合わせる計算では、その月にかかった医療費だけを1年分の医療費とみなしています。"
    "同じ年に別の月の医療費があれば、控除はその分だけ増えます",
    "何人で分けて申告するかの計算では、分ける相手の総所得も同じとしています"
    "（足切りが同じになります）。相手の総所得が200万円未満なら足切りはさらに下がるので、"
    "分けたほうが有利になる額はもっと小さくなります",
    "何人で分けて申告するかの計算では、それぞれが控除を使い切るだけの課税所得があるものとしています。"
    "医療費控除は所得控除なので、その人の所得を超えた分は戻りません",
    "医療費を分けて申告できるのは、その医療費を実際に負担した人の分だけです。"
    "誰が払ったかを動かせない医療費は、この計算の対象になりません",
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

    # --- 高額療養費と重ねたとき（`tier_thresholds` 以下の主題そのもの）-----
    # 1. **限度額が低い区分ほど、控除に届くのが遅い。** ここが逆になったら節の答えが逆になる
    hi = deduction_start_cost("ア", 3_000_000)
    mid = deduction_start_cost("ウ", 3_000_000)
    if hi is None or mid is None or not mid > hi:
        raise ValueError(f"区分ウが区分アより早く控除に届いている: ウ={mid} ア={hi}")
    # 2. 定額で頭打ちの区分（エ・オ）は、足切り10万円には**1か月では永久に届かない**
    for name in ("エ", "オ"):
        if deduction_start_cost(name, 3_000_000) is not None:
            raise ValueError(f"区分{name} が1か月で足切りに届いている（限度額は定額のはず）")
    # 3. 届く額のところで、自己負担がちょうど足切りに一致すること（式を解いた結果の裏取り）
    if self_pay(mid, "ウ") != floor_amount(3_000_000):
        raise ValueError(f"区分ウ {mid:,}円 の自己負担が足切りに一致しない: {self_pay(mid, 'ウ')}")
    # 4. **月をまたいで増えた自己負担は、どの税率でも全額は戻らない**
    #    （戻る係数は最大でも 0.45×1.021＋0.10 ＝ 0.5595）。ここが1を超える表に
    #    差し替わったら「分けたほうが得」になり、`split_recovery()` の節は逆になる
    for r in split_recovery():
        if not 0 < r["recovered_ratio"] < 1:
            raise ValueError(f"税率{r['rate']} で取り返し率が範囲外: {r['recovered_ratio']}")
    # 5. 区分オの限度額 35,400円 と、足切りが一致する総所得（708,000円 × 5%）
    if floor_amount(708_000) != kogaku.tier("オ")[3]:
        raise ValueError("区分オの限度額と、総所得708,000円の足切りが一致しない")
    # 6. **その一致する点では、控除は出ません**（自己負担は足切りに並ぶだけで、
    #    定額なのでそこから先も動かない）。`deduction_start_cost` の `<` はこのため
    if deduction_start_cost("オ", 708_000) is not None:
        raise ValueError("足切りと限度額がちょうど一致する総所得で、控除が出ることになっている")
    if deduction_start_cost("オ", 700_000) is None:
        raise ValueError("足切りが限度額より低い総所得で、控除が出ないことになっている")

    # --- 上限200万円に当たると「まとめる」が逆転する（best_claimants の主題）---
    # **`split_loss` の「分けると必ず損」は、上限に当たらない範囲でだけ正しい。**
    # 2026-08-18 まで、この向きはどの節も言っておらず、
    # 「分けて得になることは無い」という**誤った註が docstring に残っていました**
    # （検査も 400,000円 の1点でしか見ておらず、素通りしていた）。
    f3 = floor_amount(3_000_000)
    if split_loss(3_000_000, 1_500_000, 3_000_000, 0.20)["lost_deduction"] >= 0:
        raise ValueError("上限を超える医療費でも、分けると損のままになっている")
    # 逆転はちょうど「上限 ＋ 足切り × 2」で起きる（＝この表では 2,200,000円）
    tip = DEDUCTION_CAP + f3 * 2
    if together_deduction(tip, 3_000_000) != split_deduction(tip, 2, 3_000_000):
        raise ValueError(f"逆転の境目 {tip:,}円 で、まとめと2人分けが並んでいない")
    if together_deduction(tip - 20_000, 3_000_000) <= split_deduction(tip - 20_000, 2, 3_000_000):
        raise ValueError("境目の手前で、まとめが勝っていない")
    if together_deduction(tip + 20_000, 3_000_000) >= split_deduction(tip + 20_000, 2, 3_000_000):
        raise ValueError("境目の先で、2人に分けたほうが勝っていない")
    # 最適な人数は「上限に当たらない最小の人数」の前後1つに必ず収まる
    for paid in (1_000_000, 2_200_000, 3_000_000, 5_000_000, 9_000_000):
        n = best_claimants(paid, 3_000_000)["claimants"]
        best = split_deduction(paid, n, 3_000_000)
        for m in range(1, 8):
            if split_deduction(paid, m, 3_000_000) > best:
                raise ValueError(f"{paid:,}円 で {m}人 のほうが多い（{n}人 を最適と言っている）")
    # 境目の間隔は「上限 ＋ 足切り」で一定（＝この表では 2,100,000円ごと）
    tips = claimant_tips(3, 3_000_000)
    gaps = {b - a for a, b in zip(tips, tips[1:])}
    if gaps != {DEDUCTION_CAP + f3}:
        raise ValueError(f"人数が増える境目の間隔が一定でない: {gaps}")

    # --- 現金と翌年の負担減の主客が入れ替わる（refund_timing_grid の主題）---
    # 入れ替わる率は速算表に**無い**（5% と 10% のあいだに落ちる）。
    # ここが速算表の率と一致するようになったら、節の「誰もその点に立たない」は嘘になる
    tip_rate = cash_share_tipping_rate()
    if tip_rate in INCOME_TAX_RATES:
        raise ValueError(f"入れ替わりの率 {tip_rate} が速算表の率と一致している")
    if not INCOME_TAX_RATES[0] < tip_rate < INCOME_TAX_RATES[1]:
        raise ValueError(f"入れ替わりの率 {tip_rate} が速算表の 5% と 10% のあいだにない")
    # 5%の帯では住民税ぶんのほうが多く、10%以上では所得税ぶんのほうが多い
    # **`refund_timing_grid()` を呼ばないこと**（あちらが check_tables() を呼ぶので
    # 無限再帰になります。2026-08-18 に踏んだ）。部品のほうを直に回す
    for r in [refund_split(200_000, rate) for rate in INCOME_TAX_RATES]:
        bigger_cash = r["cash_now"] > r["next_year"]
        if bigger_cash != (r["rate"] > tip_rate):
            raise ValueError(f"税率{r['rate']} で内訳の大小が向きと合っていない: {r}")


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

    **ここには「分けて得になることは無い」と書いてありました。嘘です**（2026-08-18 に直した）。
    上の2つの帯は、**まとめた側が控除の上限200万円に当たらない範囲**でしか成り立ちません。
    上限に当たると `lost_deduction` は**負**になります（＝分けたほうが多く乗る）。
    向きが変わる額と、そこから先の最適な人数は `best_claimants()` を見ること。
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


# ---- 控除の上限200万円に当たると、「1人にまとめる」が逆転する ----------------
#
# `split_loss()` は「分けると足切りがもう1回引かれるので損」と言います。**足りません。**
# 控除には**上限200万円**があり、1人にまとめるとそこで切られます。
# 分けた側は上限が人数ぶんあるので、**支払額が大きいほど分けたほうが多く乗る。**
#
#     まとめ（1人）  min(支払額 − 足切り, 200万円)
#     n人に等分      min(支払額 − 足切り × n, 200万円 × n)
#
# 前者は増えなくなり、後者は足切りを n回ぶん引かれるかわりに天井が n倍。
# **どちらも「支払額」の関数として折れるので、交わる点が1つずつ出ます。**


def together_deduction(paid: int, total_income: int) -> int:
    """1人にまとめて申告したときの控除額。**上限で頭打ち。**"""
    return deduction(paid, 0, total_income)


def split_deduction(paid: int, claimants: int, total_income: int) -> int:
    """n人に等分して申告したときの控除額の合計。

    **全員の総所得が同じ**（＝足切りが同じ）としています。端数は1人目に寄せます。
    """
    if claimants < 1:
        raise ValueError(f"申告する人数が範囲外: {claimants}")
    each = paid // claimants
    return sum(deduction(each + (paid - each * claimants if i == 0 else 0),
                         0, total_income)
               for i in range(claimants))


def claimant_tips(count: int, total_income: int) -> list[int]:
    """人数が1人増える境目の医療費（円）を、小さいほうから `count` 件。

    k人と (k+1)人が並ぶのは `k × 上限 ＝ 支払額 − (k+1) × 足切り` のとき:

        支払額 = k × 上限 ＋ (k+1) × 足切り

    **隣り合う境目の差は、k に依らず「上限 ＋ 足切り」で一定です**
    （この表では 2,100,000円ごと）。
    """
    if count < 1:
        raise ValueError(f"件数が範囲外: {count}")
    f = floor_amount(total_income)
    return [k * DEDUCTION_CAP + (k + 1) * f for k in range(1, count + 1)]


def best_claimants(paid: int, total_income: int) -> dict:
    """**控除額がいちばん大きくなる申告人数。**

    上限に当たらない最小の人数 `paid / (上限 + 足切り)` の**前後1つ**が候補です
    （下は天井で切られ、上は足切りを1回多く引かれるので、必ずこの2つのどちらか）。
    同点のときは、手続きが1つで済む**少ないほう**を返します。
    """
    f = floor_amount(total_income)
    lo = max(1, int(paid // (DEDUCTION_CAP + f)))
    best_n, best_d = 1, together_deduction(paid, total_income)
    for n in (lo, lo + 1):
        d = split_deduction(paid, n, total_income)
        if d > best_d:
            best_n, best_d = n, d
    return {
        "paid": paid,
        "claimants": best_n,
        "deduction": best_d,
        "together": together_deduction(paid, total_income),
        "gain": best_d - together_deduction(paid, total_income),
    }


def claimant_grid_by_paid(total_income: int, rate: float) -> list[dict]:
    """医療費べつに、まとめた場合と分けた場合を1行に並べる。

    **境目の両側を必ず含めます**（`claimant_tips` の ±1万円）。
    1点だけ印字すると、折れているのか頭打ちなのかが読めないためです。
    """
    check_tables()
    tips = claimant_tips(2, total_income)
    paids = sorted({1_000_000, 2_000_000,
                    tips[0] - 10_000, tips[0], tips[0] + 10_000,
                    3_000_000, 4_000_000,
                    tips[1] - 10_000, tips[1], tips[1] + 10_000,
                    6_000_000})
    out = []
    for p in paids:
        b = best_claimants(p, total_income)
        out.append({
            "paid": p,
            "together": b["together"],
            "split2": split_deduction(p, 2, total_income),
            "split3": split_deduction(p, 3, total_income),
            "best_claimants": b["claimants"],
            "best_deduction": b["deduction"],
            "gain": b["gain"],
            "gain_yen": int(b["gain"] * coefficient(rate)),
            "at_tip": p in tips,
        })
    return out


# ---- 戻る額の内訳。**現金で戻るのは所得税ぶんだけ** -------------------------
#
# 医療費控除で戻る額は2つに分かれます。
#
#     所得税ぶん  税率 × 1.021   … 申告して数週間で**振り込まれる**
#     住民税ぶん  一律 10%        … **翌年6月からの1年間、毎月の天引きが減る**
#
# 住民税は税率が一律なので、**所得税率が低い人ほど、戻りに占める住民税の割合が高い。**
# 入れ替わるのは `税率 × 1.021 ＝ 10%` の点、つまり **所得税率 9.79%** です。
# 速算表の税率は 5% の次が 10% なので、**5%の帯にいる人は必ず住民税のほうが多く**、
# 10%以上の帯では必ず所得税のほうが多い。**境目は税率の段のあいだに落ちていて、
# どの納税者もその点には立ちません。**


def cash_share_tipping_rate() -> float:
    """所得税ぶんと住民税ぶんが並ぶ所得税率。**速算表には無い率です。**"""
    return RESIDENT_RATE / (1 + RECONSTRUCTION)


def refund_split(deduction_amount: int, rate: float) -> dict:
    """戻る額を「現金（所得税）」と「翌年の負担減（住民税）」に割る。"""
    income_tax = int(deduction_amount * rate * (1 + RECONSTRUCTION))
    resident = int(deduction_amount * RESIDENT_RATE)
    total = income_tax + resident
    return {
        "rate": rate,
        "deduction": deduction_amount,
        "cash_now": income_tax,
        "next_year": resident,
        "total": total,
        "cash_share": income_tax / total,
        "resident_over_cash": resident / income_tax,
    }


def refund_timing_grid(deduction_amount: int = 200_000) -> list[dict]:
    """所得税率べつに、戻る額の内訳。**5%と10%のあいだで主客が入れ替わる。**"""
    check_tables()
    return [refund_split(deduction_amount, r) for r in INCOME_TAX_RATES]


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


# ---- 高額療養費のあとの自己負担で、医療費控除がどこから出るか -------------
#
# 医療費控除の対象は「保険で補填された額を差し引いた後」＝**高額療養費で戻った後**
# の自己負担です。ところが高額療養費の限度額は、医療費が増えても1%ずつしか増えません。
# だから **窓口の医療費が10倍になっても、控除の対象になる自己負担はほとんど増えない。**
#
# 一般の解説は2つの制度を別々に説明して終わります。重ねると、
# **「限度額が低い区分（＝所得が低い側）ほど、医療費控除に届くのが遅い」**
# という、どこにも書かれていない向きが出てきます。


def self_pay(cost: int, tier_name: str = "ウ") -> int:
    """高額療養費のあとで、その月に実際に払う額（円）。"""
    return round(kogaku.paid(tier_name, cost))


def deduction_start_cost(tier_name: str, total_income: int) -> int | None:
    """**1か月の医療費がいくらを超えると、医療費控除が1円でも出るか。**

    自己負担が足切りを超えて初めて控除が乗ります。自己負担は
    「3割」と「限度額」の低いほうなので、境目は2通りの解き方に分かれます。

        3割の帯にあるうち   … 足切り ÷ 0.3
        限度額の帯に入った後 … 差引く医療費 ＋ (足切り − 定額) ÷ 1%

    定額で頭打ちの区分（エ・オ）は、限度額が医療費で増えないので **None**
    ＝ その月の医療費だけでは、いくら払っても足切りに届きません。
    """
    floor = floor_amount(total_income)
    _, _, _, flat, cost_floor, rate, _ = kogaku.tier(tier_name)
    x = floor / kogaku.COPAY_RATE
    # **ここは `<=` ではありません**（2026-08-17 に実データで踏んだ）。ちょうど一致する
    # とき（足切り＝限度額の定額。区分オなら総所得708,000円）、その額でようやく自己負担が
    # 足切りに**並ぶ**だけで、そこから先は定額で頭打ちなので **1円も超えません。**
    # `<=` だと「118,000円を超えたら控除が出る」と、出ないものを出ると言います。
    if x < kogaku.crossing_cost(tier_name):
        return int(-(-x // 1))          # まだ3割の帯。切り上げ（「超えたら」なので）
    if cost_floor is None or rate == 0:
        return None                     # 限度額が定額。**1か月では永久に届かない**
    return int(-(-(cost_floor + (floor - flat) / rate) // 1))


def tier_thresholds(total_income: int = 3_000_000) -> list[dict]:
    """区分べつの境目。**限度額が低い区分ほど、控除に届くのが遅い。**"""
    check_tables()
    out = []
    for name, *_ in kogaku.TIERS:
        start = deduction_start_cost(name, total_income)
        out.append({
            "tier": name,
            "flat": kogaku.tier(name)[3],
            "floor": floor_amount(total_income),
            "start_cost": start,
            "copay_at_start": None if start is None else int(start * kogaku.COPAY_RATE),
            "monthly_max_pay": None if start is not None else kogaku.tier(name)[3],
        })
    return out


def kogaku_grid(total_income: int, rate: float, tier_name: str = "ウ") -> list[dict]:
    """医療費べつに、窓口・高額療養費・医療費控除・戻る税金を1行に並べる。"""
    check_tables()
    out = []
    for cost in (300_000, 600_000, 1_000_000, 2_257_000, 5_000_000, 10_000_000):
        pay = self_pay(cost, tier_name)
        r = refund(pay, 0, total_income, rate)
        out.append({
            "cost": cost,
            "copay_30": int(cost * kogaku.COPAY_RATE),
            "self_pay": pay,
            "kogaku_back": int(cost * kogaku.COPAY_RATE) - pay,
            "deduction": r["deduction"],
            "tax_back": r["total"],
            "net_burden": pay - r["total"],
            "net_rate": (pay - r["total"]) / cost * 100,
        })
    return out


def split_months_tax(cost: int, parts: int, total_income: int, rate: float,
                     tier_name: str = "ウ") -> dict:
    """**同じ治療を1か月にまとめるか、月をまたいで分けるか。**

    高額療養費の限度額は月ごとに1回ずつかかるので、月をまたぐと自己負担は増えます。
    増えた自己負担は医療費控除に乗るので、**税金でいくらか戻ります。**
    「まとめたほうが得」は変わりませんが、**差は税金の分だけ縮みます。**
    """
    if parts < 1:
        raise ValueError(f"分ける月数が範囲外: {parts}")
    together = self_pay(cost, tier_name)
    each = cost // parts
    apart = sum(self_pay(each + (cost - each * parts if i == 0 else 0), tier_name)
                for i in range(parts))
    r_together = refund(together, 0, total_income, rate)
    r_apart = refund(apart, 0, total_income, rate)
    return {
        "cost": cost,
        "parts": parts,
        "pay_together": together,
        "pay_apart": apart,
        "pay_gap": apart - together,
        "tax_back_together": r_together["total"],
        "tax_back_apart": r_apart["total"],
        "net_together": together - r_together["total"],
        "net_apart": apart - r_apart["total"],
        "net_gap": (apart - r_apart["total"]) - (together - r_together["total"]),
    }


def split_recovery(cost: int = 600_000, total_income: int = 3_000_000,
                   tier_name: str = "ウ") -> list[dict]:
    """月をまたいで増えた自己負担のうち、税金で戻る割合（所得税率べつ）。

    **1を超えることはありません。** 戻る係数は控除額1円あたり
    `税率 × 1.021 ＋ 住民税10%` で、最高税率45%でも 0.5595 だからです。
    だから「医療費控除があるから月をまたいでもいい」は成り立ちません。
    """
    out = []
    for rate in INCOME_TAX_RATES:
        s = split_months_tax(cost, 2, total_income, rate, tier_name)
        out.append({
            "rate": rate,
            "pay_gap": s["pay_gap"],
            "tax_gain": s["tax_back_apart"] - s["tax_back_together"],
            "net_gap": s["net_gap"],
            "recovered_ratio": (s["tax_back_apart"] - s["tax_back_together"]) / s["pay_gap"],
        })
    return out


def low_income_grid(tier_name: str) -> list[dict]:
    """総所得べつ。**足切りが5%に下がる帯なら、定額の区分でも控除が出る。**

    足切りは総所得の5パーセント（上限10万円）なので、所得が低いほど下がります。
    ところが高額療養費の限度額も、所得が低い区分ほど下がる。
    **どちらが先に下がるかで、控除が出るかどうかが決まります。**
    """
    check_tables()
    out = []
    for ti in (600_000, 708_000, 900_000, 1_152_000, 1_600_000, 3_000_000):
        start = deduction_start_cost(tier_name, ti)
        out.append({
            "total_income": ti,
            "floor": floor_amount(ti),
            "flat": kogaku.tier(tier_name)[3],
            "start_cost": start,
        })
    return out


# ------------------------------------------------- 年をまたいで払ったとき

def year_split_shares(paid: int, years: int) -> list[int]:
    """総額を年ごとに等分する。**1円の端数は前の年から1円ずつ。**

    合計は必ず `paid` に一致する（捨てない）。
    """
    if years < 1:
        raise ValueError(f"分ける年数は1以上: {years}")
    base, rest = divmod(paid, years)
    return [base + (1 if i < rest else 0) for i in range(years)]


def year_split_deduction(paid: int, years: int, total_income: int) -> int:
    """`paid` を `years` 年に分けて払ったときの、控除額の合計。

    **医療費控除は年ごとに締めます。** 足切りも年ごとに引かれるので、
    「5年さかのぼれる」は「5年分をまとめて1回で申告できる」ではありません。
    """
    return sum(deduction(x, 0, total_income)
               for x in year_split_shares(paid, years))


def year_split_loss(paid: int, years: int, total_income: int, rate: float) -> dict:
    """年をまたいで払ったせいで消える控除と、消える還付。

    **消える控除は、医療費の額によりません** ——
    またぎ1回につき足切り1回ぶんで、`(years - 1) × 足切り`。
    ただし控除そのものが尽きたところで頭打ちになります。
    """
    together = deduction(paid, 0, total_income)
    apart = year_split_deduction(paid, years, total_income)
    floor = floor_amount(total_income)
    return {
        "paid": paid,
        "years": years,
        "per_year": paid // years,
        "deduction_together": together,
        "deduction_apart": apart,
        "lost_deduction": together - apart,
        "refund_together": refund(paid, 0, total_income, rate)["total"],
        "refund_apart": int(apart * coefficient(rate)),
        "lost_yen": int((together - apart) * coefficient(rate)),
        # **頭打ち ＝ 控除が尽きて、それ以上は消えようがない**
        "capped": apart == 0 and together < (years - 1) * floor,
    }


def year_split_grid(paid: int, total_income: int, rate: float,
                    upto: int = RECLAIM_YEARS) -> list[dict]:
    """1年に集中させた場合から、`upto` 年に分けた場合まで。"""
    check_tables()
    return [year_split_loss(paid, n, total_income, rate)
            for n in range(1, upto + 1)]


def cross_year_cost(total_income: int, rate: float) -> int:
    """**年を1回またぐごとに消える還付。** 医療費の額によらない。

    足切り1回ぶんの控除が消えるので、`足切り × 係数`。
    """
    return int(floor_amount(total_income) * coefficient(rate))


def cross_year_grid(rate: float, small_paid: int = 150_000) -> list[dict]:
    """総所得べつ。**またぎ1回の値段**と、頭打ちになる例を並べる。"""
    check_tables()
    out = []
    for ti in (600_000, 1_000_000, 1_600_000, 1_999_980, 2_000_000, 3_000_000,
               5_000_000):
        small = year_split_loss(small_paid, 2, ti, rate)
        out.append({
            "total_income": ti,
            "floor": floor_amount(ti),
            "lost_deduction": floor_amount(ti),
            "lost_yen": cross_year_cost(ti, rate),
            "capped_at": ti,
            "small_lost_yen": small["lost_yen"],
            "small_capped": small["capped"],
        })
    return out


def zero_years(paid: int, total_income: int) -> int:
    """**何年に分けたら、還付が1円も残らなくなるか。**

    1年あたりが足切り以下になった時点で控除は0。
    `-(-paid // floor)` ＝ 切り上げ。
    """
    floor = floor_amount(total_income)
    if paid <= floor:
        return 1
    return -(-paid // floor)


def zero_years_grid(total_income: int, rate: float) -> list[dict]:
    """医療費べつ。**5年に分けると何割が消えるか**と、0円になる年数。"""
    check_tables()
    out = []
    floor = floor_amount(total_income)
    for paid in (200_000, 300_000, floor * RECLAIM_YEARS,
                 floor * RECLAIM_YEARS + 1, 600_000, 1_000_000, 2_000_000):
        one = year_split_loss(paid, 1, total_income, rate)
        five = year_split_loss(paid, RECLAIM_YEARS, total_income, rate)
        out.append({
            "paid": paid,
            "refund_one": one["refund_together"],
            "deduction_five": five["deduction_apart"],
            "refund_five": five["refund_apart"],
            "lost_share": (1.0 if one["refund_together"] == 0
                           else 1 - five["refund_apart"] / one["refund_together"]),
            "zero_years": zero_years(paid, total_income),
        })
    return out


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

    print(f"\n=== 「1人にまとめる」が逆になる医療費（総所得{TI2:,}円・所得税率{RATE2:.0%}）===")
    tips = claimant_tips(2, TI2)
    print(f"  控除の上限 {DEDUCTION_CAP:,}円 ・ 足切り {floor_amount(TI2):,}円。"
          f"逆転は {tips[0]:,}円 ＝ 上限 ＋ 足切り×2。")
    print(f"  そこから先の境目は {DEDUCTION_CAP + floor_amount(TI2):,}円ごと（次は {tips[1]:,}円）。")
    print(f"{'支払った医療費':>13s} {'1人':>10s} {'2人で分ける':>11s} {'3人で分ける':>11s} "
          f"{'最善':>5s} {'まとめとの差':>11s}")
    for r in claimant_grid_by_paid(TI2, RATE2):
        mark = "  ← 境目（並ぶ）" if r["at_tip"] else ""
        print(f"{r['paid']:12,d}円 {r['together']:9,d}円 {r['split2']:10,d}円 "
              f"{r['split3']:10,d}円 {r['best_claimants']:4d}人 {r['gain_yen']:10,d}円" + mark)

    D = 200_000
    print(f"\n=== 控除{D:,}円で戻る額の内訳（現金は所得税ぶんだけ）===")
    print(f"  入れ替わるのは所得税率 {cash_share_tipping_rate():.4%}。"
          "速算表は 5% の次が 10% なので、**その率の人はいません。**")
    print(f"{'所得税率':>7s} {'現金（所得税）':>13s} {'翌年6月から（住民税）':>19s} "
          f"{'合計':>9s} {'現金の割合':>9s}")
    for r in refund_timing_grid(D):
        mark = "  ← 住民税のほうが多い" if r["cash_now"] < r["next_year"] else ""
        print(f"{r['rate']:6.0%} {r['cash_now']:12,d}円 {r['next_year']:18,d}円 "
              f"{r['total']:8,d}円 {r['cash_share']:9.1%}" + mark)

    print("\n=== 高額療養費のあと、医療費控除が1円でも出る医療費（総所得3,000,000円）===")
    print(f"  足切り {floor_amount(3_000_000):,}円（総所得3,000,000円）。"
          "自己負担がこれを超えて、初めて控除が1円乗ります。")
    print(f"{'区分':>4s} {'限度額の定額':>11s} {'控除が出る医療費':>17s} "
          f"{'そのときの窓口3割':>17s}")
    for r in tier_thresholds(3_000_000):
        if r["start_cost"] is None:
            print(f"{r['tier']:>4s} {r['flat']:10,d}円 "
                  f"{'届きません':>17s}  ← 限度額が定額なので、"
                  f"その月にいくら払っても自己負担は{r['monthly_max_pay']:,}円で頭打ち")
        else:
            print(f"{r['tier']:>4s} {r['flat']:10,d}円 {r['start_cost']:16,d}円 "
                  f"{r['copay_at_start']:16,d}円")
    print("  **限度額が低い区分ほど、控除に届くのが遅くなります**"
          "（自己負担そのものが小さいので、足切りに届かない）。")

    print("\n=== 区分ウ / 医療費べつ 窓口・高額療養費・医療費控除"
          "（総所得3,000,000円・所得税率10%）===")
    print(f"{'医療費':>12s} {'窓口3割':>11s} {'実際に払う':>10s} {'高額療養費で戻る':>13s} "
          f"{'控除額':>9s} {'税金で戻る':>10s} {'最後に残る負担':>12s} {'負担率':>7s}")
    for r in kogaku_grid(3_000_000, 0.10):
        print(f"{r['cost']:11,d}円 {r['copay_30']:10,d}円 {r['self_pay']:9,d}円 "
              f"{r['kogaku_back']:12,d}円 {r['deduction']:8,d}円 {r['tax_back']:9,d}円 "
              f"{r['net_burden']:11,d}円 {r['net_rate']:6.2f}%")
    print("  **医療費が10倍になっても、最後に残る負担はほとんど動きません。**")

    print("\n=== 月をまたぐと自己負担は増えるが、戻る税金では取り返せない"
          "（区分ウ・医療費600,000円）===")
    s = split_months_tax(600_000, 2, 3_000_000, 0.10)
    print(f"  1か月にまとめる: 自己負担 {s['pay_together']:,}円 → "
          f"税金で {s['tax_back_together']:,}円戻り、残る負担 {s['net_together']:,}円")
    print(f"  2か月に分ける  : 自己負担 {s['pay_apart']:,}円 → "
          f"税金で {s['tax_back_apart']:,}円戻り、残る負担 {s['net_apart']:,}円")
    print(f"  自己負担の差 {s['pay_gap']:,}円 が、税金を入れると {s['net_gap']:,}円 まで縮みます"
          f"（総所得3,000,000円・所得税率10%）")
    print(f"{'所得税率':>7s} {'増える自己負担':>12s} {'増える還付':>10s} "
          f"{'差し引き':>10s} {'取り返せる割合':>12s}")
    for r in split_recovery():
        print(f"{r['rate']:6.0%} {r['pay_gap']:11,d}円 {r['tax_gain']:9,d}円 "
              f"{r['net_gap']:9,d}円 {r['recovered_ratio']:11.1%}")
    print("  **どの税率でも1を超えません。**戻る係数は「税率×1.021＋住民税10%」で、"
          "最高税率45%でも 0.5595 だからです。")

    for t in ("エ", "オ"):
        print(f"\n=== 区分{t}（限度額が定額）で、医療費控除が出る総所得 ===")
        print(f"  限度額は {kogaku.tier(t)[3]:,}円。その月にいくら医療費がかかっても、"
              "自己負担はここで頭打ちです。")
        print(f"{'総所得':>11s} {'足切り':>9s}  {'控除が出る医療費'}")
        for r in low_income_grid(t):
            print(f"{r['total_income']:10,d}円 {r['floor']:8,d}円  "
                  + (f"{r['start_cost']:,}円 を超えたら" if r["start_cost"]
                     else f"届きません（自己負担は{r['flat']:,}円で頭打ちなので、"
                          f"足切り{r['floor']:,}円を超えられません）"))

    PAID_Y, TI_Y, RATE_Y = 600_000, 3_000_000, 0.10
    print(f"\n=== 医療費{PAID_Y:,}円を、何年に分けて払うかべつ"
          f"（総所得{TI_Y:,}円・所得税率{RATE_Y:.0%}）===")
    print(f"  足切り {floor_amount(TI_Y):,}円は**年ごとに引かれます。**"
          "「5年さかのぼれる」は「5年分をまとめて1回で申告できる」ではありません。")
    print(f"{'分けた年数':>9s} {'1年あたり':>10s} {'控除の合計':>10s} "
          f"{'戻る額の合計':>11s} {'まとめて払った場合との差':>20s}")
    for r in year_split_grid(PAID_Y, TI_Y, RATE_Y):
        mark = "  ← 1年あたりが足切り以下。1円も戻りません" if r["deduction_apart"] == 0 else ""
        print(f"{r['years']:8d}年 {r['per_year']:9,d}円 {r['deduction_apart']:9,d}円 "
              f"{r['refund_apart']:10,d}円 {r['lost_yen']:19,d}円" + mark)
    print(f"  **消える控除は、医療費の額によりません。**またぎ1回につき"
          f"足切り1回ぶん（{floor_amount(TI_Y):,}円）で、"
          f"還付にすると {cross_year_cost(TI_Y, RATE_Y):,}円です。")

    print("\n=== 総所得べつ / 年を1回またぐごとに消える還付"
          "（医療費の額によらない）===")
    print(f"  所得税率{RATE_Y:.0%}。足切りは「10万円と総所得の5%の少ないほう」なので、"
          "**またぎの値段も総所得200万円で頭打ち**になります。")
    print(f"{'総所得':>11s} {'足切り':>9s} {'消える控除':>10s} {'消える還付':>10s}  "
          f"{'医療費150,000円を2年に分けた実際の損'}")
    for r in cross_year_grid(RATE_Y):
        note = (f"{r['small_lost_yen']:,}円  ← 控除が尽きて頭打ち"
                if r["small_capped"] else f"{r['small_lost_yen']:,}円")
        print(f"{r['total_income']:10,d}円 {r['floor']:8,d}円 "
              f"{r['lost_deduction']:9,d}円 {r['lost_yen']:9,d}円  {note}")
    print("  **医療費が小さい人ほど、またぎの損は「消える還付」より小さくなります。**"
          "控除そのものが先に尽きるからです。")

    print(f"\n=== 医療費べつ / 何年に分けると1円も戻らなくなるか"
          f"（総所得{TI_Y:,}円・所得税率{RATE_Y:.0%}）===")
    print(f"  1年あたりが足切り{floor_amount(TI_Y):,}円以下になった時点で、控除は0です。")
    print(f"{'医療費の総額':>12s} {'1年で払った還付':>14s} {'5年に分けた控除':>14s} "
          f"{'5年に分けた還付':>14s} {'消える割合':>9s} {'控除が0になる分割年数':>19s}")
    for r in zero_years_grid(TI_Y, RATE_Y):
        mark = "  ← 5年に分けたら0円" if r["refund_five"] == 0 else ""
        print(f"{r['paid']:11,d}円 {r['refund_one']:13,d}円 {r['deduction_five']:13,d}円 "
              f"{r['refund_five']:13,d}円 {r['lost_share']:8.1%} "
              f"{r['zero_years']:18d}年" + mark)
    print("  **控除が1円残っても、還付は円未満を切り捨てるので0円になります**"
          f"（医療費{floor_amount(TI_Y) * RECLAIM_YEARS + 1:,}円の行）。")
    print(f"  **「5年さかのぼれる」を効かせようと5年に分けると、"
          f"医療費{floor_amount(TI_Y) * RECLAIM_YEARS:,}円以下では1円も戻りません**"
          f"（総所得{TI_Y:,}円のとき）。")
