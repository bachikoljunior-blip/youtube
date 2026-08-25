"""経営セーフティ共済（中小企業倒産防止共済）の**「全額損金」がいくらの得なのか**を計算する。

`grep -l セーフティ src/calc/*.py` も `倒産防止` も **0件**だった。62本のどれも
この共済を計算していない。`shokibo`（小規模企業共済）とは**別の制度**で、
あちらは受け取りが退職所得、こちらは**そのまま事業の収入**になる。**そこが全部です。**

## 一般の解説はここで止まる

    「掛金は全額を損金にできます。節税になります」
    「40か月以上納めれば、解約手当金は掛金の100パーセントが戻ります」
    「共済金の借入は無利子です」

**この3つとも、金額まで詰めると別のことを言っている。**

## この表で出る、どこにも載っていない数

1. **「全額損金」の差引の得は、0円。** 掛金 月200,000円を40か月で
    **8,000,000円** 落としても、解約手当金は**そのまま収入**になるので、
    同じ税率なら行って来い。**5つの税率で並べて、5行とも0円です。**
    この共済が減らすのは税額ではなく、**税を払う時期**
2. **得になるのは「税率が下がる年に解約したとき」だけで、額は掛金 × 税率差。**
    43パーセントで積んで15パーセントの年に解約すれば **2,240,000円**、
    掛金1円あたり **0.28円**。**同じ税率のまま解約すると、40か月かけて0円**
3. **階段の手前で解約したときに捨てる額。** 11か月で解約すると **2,200,000円** が
    まるごと戻らない。**1か月待つだけで戻る額は 1,720,000円 増える**
    （増やした掛金を引いた後の差）
4. **「無利子」の実質の金利。** 借りた額の10分の1にあたる掛金の権利が消えるので、
    8,000,000円 を借りると **800,000円**。5年で返すなら年 **4.00%** に相当する
    （元金均等・平均残高を元金の半分と置いた場合）
5. **上限の月200,000円で積むと、限度額に着く月数と「全額戻る」月数が
    どちらも40か月で一致する。** 800万円 ÷ 20万円 が40だから。
    **月5,000円だと 133.3年**かかる ＝ 下限で入ると、この制度の出口には**着かない**
6. **2024年10月の改正で、回転させる使い方が止まった。** 解約から2年
    （**24か月**）は再加入しても落とせないので、月200,000円なら
    **4,800,000円** ぶんの損金を失う。43パーセントの人で **2,064,000円**

## 注意（前提の置き方そのものが独自の視点）

**この共済は運用ではありません。** 利息は付かないので、
上の1が言っているのは「損も得もしない」ではなく、
**「40か月ぶん資金を寝かせて、税を払う時期だけ動かした」**ということ。
**得と呼べるのは 2 の税率差だけで、それは解約する年の所得を自分で選べる人にしか作れません。**
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "経営セーフティ共済（中小企業倒産防止共済）の掛金は、法人なら損金、個人事業なら必要経費になるものとしています",
    "解約手当金は、受け取った年の益金または事業所得の収入金額になるものとしています",
    "限界税率は仮定です。表では15パーセント、20パーセント、30パーセント、33パーセント、43パーセントの5通りを並べています（所得税と住民税10パーセントの合計）",
    "掛金は毎月同じ額を、途中で変えずに払い続けるものとしています",
    "掛金の月額は5000円から20万円までで、5000円きざみです",
    "掛金の積立限度額は800万円です。ここに達すると、それ以上は払えません",
    "解約手当金の割合は、任意解約の場合の割合です。機構解約やみなし解約では割合が変わります",
    "共済金の借入は無利子ですが、借りた額の10分の1にあたる掛金の権利が消えるものとしています",
    "借入の限度額は掛金総額の10倍か、回収が困難な売掛金などの額の少ないほうで、上限は8000万円です",
    "2024年10月1日以後に解約した場合、解約の日から2年のあいだは、再加入しても掛金を損金や必要経費にできないものとしています",
    "運用の利回りは0パーセントとしています。この共済に利息は付きません",
    "掛金を前納した場合の減額分は入れていません",
]

# ---- 制度の値 ----------------------------------------------------------
MIN_MONTHLY = 5_000              # 掛金の下限
MAX_MONTHLY = 200_000            # 掛金の上限
STEP_MONTHLY = 5_000             # きざみ
TOTAL_CAP = 8_000_000            # 積立限度額
LOAN_MULTIPLE = 10               # 借入は掛金総額の10倍まで
LOAN_CAP = 80_000_000            # 借入の上限
LOAN_FORFEIT = 0.10              # 借りた額の10分の1の掛金の権利が消える
REJOIN_BLOCK_YEARS = 2           # 2024年10月改正。解約から2年は損金にできない

# (この月数まで, 解約手当金の割合)。**任意解約の場合**
REFUND_STEPS: list[tuple[int, float]] = [
    (11, 0.00),
    (23, 0.80),
    (29, 0.85),
    (35, 0.90),
    (39, 0.95),
    (999, 1.00),
]
FULL_MONTHS = 40                 # 100パーセントになる月数

TAX_RATES = (0.15, 0.20, 0.30, 0.33, 0.43)


def refund_rate(months: int) -> float:
    """納付月数から解約手当金の割合を出す。"""
    for cap, rate in REFUND_STEPS:
        if months <= cap:
            return rate
    raise ValueError(f"月数が表に当たらない: {months}")


def paid(monthly: int, months: int) -> int:
    """払った掛金の総額。積立限度額で頭打ちになる。"""
    return min(monthly * months, TOTAL_CAP)


def refund(monthly: int, months: int) -> int:
    return int(paid(monthly, months) * refund_rate(months))


def months_to_cap(monthly: int) -> int:
    """積立限度額に着くまでの月数。"""
    return -(-TOTAL_CAP // monthly)


MONTH_GRID = (6, 11, 12, 23, 24, 29, 30, 35, 36, 39, 40, 48)


def step_grid(monthly: int = 200_000) -> list[dict]:
    rows = []
    for m in MONTH_GRID:
        p, r = paid(monthly, m), refund(monthly, m)
        rows.append({
            "months": m, "rate": refund_rate(m), "paid": p,
            "refund": r, "lost": p - r,
            "lost_share": (p - r) / p if p else 0.0,
        })
    return rows


CLIFF_EDGES = (11, 23, 29, 35, 39)


def cliff_grid(monthly: int = 200_000) -> list[dict]:
    """**1か月待つだけで戻る額がいくら増えるか。**"""
    rows = []
    for edge in CLIFF_EDGES:
        a, b = refund(monthly, edge), refund(monthly, edge + 1)
        extra = monthly if paid(monthly, edge + 1) > paid(monthly, edge) else 0
        rows.append({
            "edge": edge,
            "rate_before": refund_rate(edge), "rate_after": refund_rate(edge + 1),
            "before": a, "after": b, "gain": b - a, "extra_paid": extra,
            "net": b - a - extra,
        })
    return rows


def deferral_grid(monthly: int = 200_000, months: int = FULL_MONTHS) -> list[dict]:
    """**「全額損金」は減税ではなく繰延べ。** 同じ税率で解約すると、得は0円。"""
    rows = []
    p = paid(monthly, months)
    r = refund(monthly, months)
    for rate in TAX_RATES:
        saved = int(p * rate)          # 払っている間に減った税
        taxed = int(r * rate)          # 解約した年に増える税
        rows.append({
            "rate": rate, "paid": p, "saved": saved,
            "refund": r, "taxed": taxed, "net": saved - taxed,
        })
    return rows


RATE_PAIRS = (
    (0.43, 0.33), (0.43, 0.30), (0.43, 0.20), (0.43, 0.15),
    (0.33, 0.20), (0.33, 0.15), (0.30, 0.15), (0.20, 0.15),
)


def rate_gap_grid(monthly: int = 200_000, months: int = FULL_MONTHS) -> list[dict]:
    """**得になるのは、税率が下がる年に解約したときだけ。**"""
    p, r = paid(monthly, months), refund(monthly, months)
    rows = []
    for high, low in RATE_PAIRS:
        net = int(p * high) - int(r * low)
        rows.append({
            "high": high, "low": low, "gap": high - low,
            "saved": int(p * high), "taxed": int(r * low),
            "net": net, "per_yen": net / p,
        })
    return rows


MONTHLY_GRID = (5_000, 20_000, 50_000, 100_000, 150_000, 200_000)


def cap_grid() -> list[dict]:
    """積立限度額に着くまでの月数と、着いた後に落とせる掛金はゼロになること。"""
    rows = []
    for mo in MONTHLY_GRID:
        m = months_to_cap(mo)
        rows.append({
            "monthly": mo, "months": m, "years": m / 12,
            "full_at": max(m, FULL_MONTHS),
            "after_cap": 0,
        })
    return rows


LOAN_TERMS = (5, 6, 7)   # 借入額に応じた返済年数（据置6か月を含む年数の目安）


def loan_grid(loan: int = 8_000_000) -> list[dict]:
    """**無利子の借入の、実質の金利。** 借りた額の10分の1の掛金の権利が消える。"""
    rows = []
    forfeit = int(loan * LOAN_FORFEIT)
    for years in LOAN_TERMS:
        # 元金均等で返すときの平均残高はおよそ元金の半分
        avg_balance = loan / 2
        rows.append({
            "loan": loan, "years": years, "forfeit": forfeit,
            "per_year": forfeit / years,
            "effective": (forfeit / years) / avg_balance,
        })
    return rows


def rejoin_grid(monthly: int = 200_000) -> list[dict]:
    """2024年10月改正。解約から2年、掛金を落とせない。"""
    rows = []
    blocked = REJOIN_BLOCK_YEARS * 12
    for rate in TAX_RATES:
        rows.append({
            "rate": rate, "months": blocked,
            "premium": monthly * blocked,
            "lost_deduction": int(monthly * blocked * rate),
        })
    return rows


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""
    # 1. 制度が名指ししている値
    _checks.statutory(TOTAL_CAP, 8_000_000, "積立限度額",
                      source="中小企業倒産防止共済法・中小機構の公表資料")
    _checks.statutory(MAX_MONTHLY, 200_000, "掛金の月額上限", source="同")
    _checks.statutory(MIN_MONTHLY, 5_000, "掛金の月額下限", source="同")
    _checks.statutory(LOAN_MULTIPLE, 10, "借入は掛金総額の何倍か", source="同")
    _checks.statutory(LOAN_CAP, 80_000_000, "借入の上限", source="同")
    _checks.statutory(FULL_MONTHS, 40, "解約手当金が100パーセントになる月数",
                      source="同（任意解約）")
    _checks.statutory(REJOIN_BLOCK_YEARS, 2, "再加入しても損金にできない年数",
                      source="令和6年度税制改正（2024年10月1日以後の解約）")
    _checks.ratio(LOAN_FORFEIT, "借入で消える掛金の割合")
    for _cap, rate in REFUND_STEPS:
        # **100パーセントは制度の値**。`ratio` は 0 と 1 のあいだしか通さないので、
        # ここは上限を含む形で書く（`zasson` の軽減割合と同じ理由）
        if not 0 <= rate <= 1:
            raise _checks.TableError(f"解約手当金の割合が {rate}")
    _checks.ascending([r for _c, r in REFUND_STEPS], "解約手当金の割合")
    _checks.ascending([c for c, _r in REFUND_STEPS], "解約手当金の月数の区分",
                      strict=True)
    _checks.rounding(MAX_MONTHLY % STEP_MONTHLY, 0, "掛金の上限がきざみに乗っていない")

    # 2. この計算の主題そのもの
    #   月数が増えれば戻る額は減らない
    _checks.never_decreases(lambda m: refund(200_000, m), list(MONTH_GRID),
                            "月数が増えたのに戻る額が減っている")
    #   12か月未満はゼロ、40か月で全額
    _checks.rounding(refund(200_000, 11), 0, "11か月の解約手当金")
    _checks.rounding(refund(200_000, FULL_MONTHS),
                     paid(200_000, FULL_MONTHS), "40か月の解約手当金")
    #   崖: 1か月またぐと戻る額が増える
    for row in cliff_grid():
        _checks.greater(row["after"], row["before"],
                        f"{row['edge']}か月の段で戻る額が増えていない")
    #   同じ税率なら、繰延べの得はゼロにならない（全額戻るので税額も同額）
    for row in deferral_grid():
        _checks.rounding(row["net"], 0,
                         f"同じ税率{row['rate']:.0%}なのに得が出ている（繰延べのはず）")
    #   税率差が大きいほど得が増える
    _checks.increases_with(
        lambda g: int(paid(200_000, FULL_MONTHS) * 0.43)
        - int(refund(200_000, FULL_MONTHS) * (0.43 - g)),
        [0.10, 0.13, 0.23, 0.28],
        "税率差が広がったのに得が増えていない")
    #   積立限度額に着く月数は、掛金が多いほど短い
    _checks.decreases_with(months_to_cap, [5_000, 50_000, 200_000],
                           "掛金を増やしたのに限度額まで長くなっている")
    _checks.rounding(months_to_cap(MAX_MONTHLY), FULL_MONTHS,
                     "月20万円で積立限度額に着く月数")
    #   返済が長いほど実質金利は下がる
    _checks.decreases_with(lambda y: loan_grid()[LOAN_TERMS.index(y)]["effective"],
                           list(LOAN_TERMS),
                           "返済が長いのに実質の金利が下がっていない")
    _checks.unique_by(cap_grid(), lambda r: r["monthly"], "掛金べつの表")
    _checks.assumption_values(ASSUMPTIONS, name="tousan")


def main() -> None:
    check_tables()
    print("制度の値の検査: 通過")

    MO = 200_000
    print(f"\n=== 40か月に届かないと、掛金は戻ってこない（掛金 月{MO:,}円）===")
    print(f"{'納付月数':>8s} {'割合':>7s} {'払った額':>12s} {'戻る額':>12s} "
          f"{'捨てる額':>12s} {'捨てる割合'}")
    for r in step_grid(MO):
        print(f"{r['months']:6d}か月 {r['rate']:7.0%} {r['paid']:11,d}円 "
              f"{r['refund']:11,d}円 {r['lost']:11,d}円 {r['lost_share']:10.0%}")
    print(f"  → **{FULL_MONTHS}か月が境目です。** ここまでの階段は5段あり、"
          "**どの段も「1か月待つかどうか」で戻る額が変わります。**"
          "「全額戻る」と説明されるのは、いちばん上の段のことです。")

    print(f"\n=== 1か月待つだけで、戻る額はいくら増えるか（掛金 月{MO:,}円）===")
    print(f"{'この月数で解約':>12s} {'割合':>7s} {'戻る額':>12s} → "
          f"{'翌月なら':>9s} {'戻る額':>12s} {'増える額':>12s} {'増やした掛金を引いた差'}")
    for r in cliff_grid(MO):
        print(f"{r['edge']:10d}か月 {r['rate_before']:7.0%} {r['before']:11,d}円 → "
              f"{r['rate_after']:12.0%} {r['after']:11,d}円 {r['gain']:11,d}円 "
              f"{r['net']:16,d}円")
    print("  → 右端が**1か月ぶん多く払ったうえでの差**です。5段とも右端がプラスなので、"
          "**段の手前で解約する理由は、資金繰り以外にありません。**"
          f"いちばん大きいのは11か月の段で、**{cliff_grid(MO)[0]['net']:,}円**。")

    print(f"\n=== 「全額損金」は減税ではない（{FULL_MONTHS}か月で解約・掛金 月{MO:,}円）===")
    print(f"{'限界税率':>8s} {'払った掛金':>12s} {'払う間に減った税':>14s} "
          f"{'戻る額':>12s} {'解約した年に増える税':>16s} {'差引の得'}")
    for r in deferral_grid(MO):
        print(f"{r['rate']:7.0%} {r['paid']:11,d}円 {r['saved']:13,d}円 "
              f"{r['refund']:11,d}円 {r['taxed']:15,d}円 {r['net']:9,d}円")
    print("  → **5行とも差引の得は0円です。** 掛金は全額落ちますが、"
          "解約手当金は**そのまま収入になる**ので、同じ税率なら行って来い。"
          "**この共済が減らすのは税額ではなく、税を払う時期です。**")

    print(f"\n=== 得になるのは「税率が下がる年に解約したとき」だけ（{FULL_MONTHS}か月・"
          f"掛金 月{MO:,}円）===")
    print(f"{'払う間の税率':>11s} {'解約する年の税率':>14s} {'差':>7s} "
          f"{'減った税':>12s} {'増える税':>12s} {'差引の得':>12s} {'掛金1円あたり'}")
    for r in rate_gap_grid(MO):
        print(f"{r['high']:10.0%} {r['low']:13.0%} {r['gap']:7.0%} "
              f"{r['saved']:11,d}円 {r['taxed']:11,d}円 {r['net']:11,d}円 "
              f"{r['per_yen']:12.2f}円")
    print("  → **得は「掛金総額 × 税率差」とほぼ同じ額になります**（全額戻るので）。"
          "だから使いどころは、**廃業する年・赤字の年・所得が落ちる年に解約すること。**"
          "**同じ税率のまま解約すると、40か月かけて0円です。**")

    print("\n=== 積立限度額800万円に着くまでの月数（着いた後は落とせる掛金がゼロになる）===")
    print(f"{'掛金の月額':>11s} {'限度額まで':>10s} {'年でいうと':>11s} "
          f"{'100パーセントになる月数':>18s} {'着いた後の年の損金'}")
    for r in cap_grid():
        print(f"{r['monthly']:10,d}円 {r['months']:8d}か月 {r['years']:9.1f}年 "
              f"{r['full_at']:16d}か月 {r['after_cap']:14,d}円")
    print(f"  → **月{MAX_MONTHLY:,}円で積み立てると、限度額に着く月数と"
          f"「全額戻る」月数がどちらも{FULL_MONTHS}か月で一致します。**"
          "偶然ではなく、800万円 ÷ 20万円 が40だからです。"
          "**上限で積むと、いちばん短い期間で「全額戻る」に着く**ことになります。"
          "その代わり、着いたあとの年は損金がゼロになります。")

    LOAN = 8_000_000
    print(f"\n=== 無利子の借入を、実質の金利に直す（借入{LOAN:,}円）===")
    print(f"{'返済年数':>8s} {'消える掛金の権利':>14s} {'1年あたり':>12s} {'実質の金利'}")
    for r in loan_grid(LOAN):
        print(f"{r['years']:6d}年 {r['forfeit']:13,d}円 {r['per_year']:11,.0f}円 "
              f"{r['effective']:11.2%}")
    print("  → 「無利子」と説明されますが、**借りた額の10分の1にあたる掛金の権利が消えます。**"
          "元金均等で返すとして平均残高を元金の半分と置くと、"
          f"**{LOAN_TERMS[0]}年で返すなら年{loan_grid(LOAN)[0]['effective']:.2%}に相当します。**"
          "**返済が長いほど、この率は下がります。**")

    print(f"\n=== 2024年10月の改正 —— 解約から2年、掛金を落とせない（掛金 月{MO:,}円）===")
    print(f"{'限界税率':>8s} {'落とせない期間':>12s} {'そのあいだの掛金':>14s} "
          f"{'失う損金の値打ち'}")
    for r in rejoin_grid(MO):
        print(f"{r['rate']:7.0%} {r['months']:10d}か月 {r['premium']:13,d}円 "
              f"{r['lost_deduction']:14,d}円")
    print("  → 2024年10月1日以後に解約すると、**解約の日から2年**は再加入しても"
          "掛金を落とせません。**「40か月で解約して入り直す」を繰り返す使い方が、"
          "ここで止まりました。** 上の表は、その2年で落とせなくなる額です。"
          "**解約の日を決める前に、次に入り直す日まで数えること。**")


if __name__ == "__main__":
    main()
