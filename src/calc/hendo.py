"""変動金利の「5年ルール・125パーセントルール」を、回ごとに解いて実額を出す。

    python -m src.calc.hendo

## この計算で出したいこと

変動金利の説明は「5年間は返済額が変わりません」「上がっても1.25倍まで」で止まる。
**止まったところから先が、この計算の中身。** 返済額が据え置かれても、利息は
金利のとおりに発生する。返済額より利息が大きくなった月は、**元金が1円も減らず**、
差額は「未払利息」として積み上がる。**その額は、月ごとに解かないと出ない。**

3,500万円・35年・当初 年0.5パーセントで、13回目から年4.0パーセントに上がった場合。

1. **毎月の返済額は 90,855円 のまま、利息が 113,608円 になる。**
   返済額のほうが 22,753円 足りないので、**その月の元金は0円**。
   これが **108回** 続く（**9年間、元金が1円も減らない**）。
2. **積み上がった未払利息は 1,094,544円。** これは毎月の返済とは別に、
   最後にまとめて払う。「返済額が変わらない」は「払う額が変わらない」ではない。
3. **125パーセントの頭打ちが解けるのは 241回目 ＝ 21年目。**
   61回目の見直しで必要だったのは 167,930円 だが、上げられるのは 113,568円 まで。
   **上げ幅が足りないまま、次の5年へ持ち越す。**それが3回続く。
4. **ルールが付いているほうが、総支払額は 6,611,976円 多い**
   （70,108,284円 対 63,496,308円）。ルールが無い契約は13回目から
   152,956円 に上がって終わるが、**据え置いたほうは元金が減らないぶん、
   同じ残高に利息を払い続ける。**「急に上がらない安心」の値段がこれ。

## 掛け算1回で出るほうの答え

**元金が1円も減らなくなる金利は、借入額に依らない。**

    残高 × 年利 ÷ 12 ＝ 毎月の返済額   →   年利 ＝ 返済額 × 12 ÷ 残高

元利均等の返済額は元金に比例するので、割ると元金が消える。
2,500万円でも 5,000万円でも、**35年・当初0.5パーセントなら 3.115パーセント。**
決めているのは**期間と当初金利の2つだけ**で、20年なら 5.255パーセント まで耐える。
**期間を延ばして毎月を軽くするほど、元金が止まる金利は低くなる。**

## 上がる時期で、答えが変わる

同じ「年4.0パーセントまで上昇」でも、**初回から上がると未払利息は 1,734,540円**、
**60回目からなら 10,628円**、**61回目からなら 0円**。
5年ルールの据え置きが解けた直後に上がれば、見直しがそのまま効く。
**危ないのは最初の5年の中で上がったときだけ**という、時期の話になる。

## 前提（動画にそのまま出すこと）

- 3,500万円・35年・元利均等返済、当初 年0.5パーセント。ボーナス返済と繰上返済は無し
- 金利は13回目に年4.0パーセントへ一段だけ上がる（上下を混ぜると原因が分けられない）
- 5年ルールと125パーセントルールは**法律ではなく銀行の約款の取り扱い**。
  付いていない契約もあるので、**付いた場合と付かない場合の両方**を出す
- 未払利息には利息を付けない。付ける約款なら、この計算より大きくなる
- 毎月の利息は1円未満切り捨て、毎月の返済額は1円未満切り上げ
- 税・保証料・団体信用生命保険・繰上返済の手数料は1円も入れていない

## 根拠の探し方（動画の説明欄用。URLは書かない）

- 5年ルール・125パーセントルール … 各行の住宅ローン約款と「商品概要説明書」の
  「返済額の見直し」の項。**全行に在るものではない**
- 元利均等返済の式 … どの金融機関の資料にも同じ形で載っている
- 未払利息の扱い（最終回に一括か、繰り延べか）… 同じく約款の「未払利息」の項
"""
from __future__ import annotations

import math

from . import _checks

# ---- 契約の値（**法律ではありません。約款の取り扱いです**） -------------
#
# **5年ルール**  金利が動いても、毎月の返済額は5年間（60回）据え置く。
#                見直しは 61回目・121回目… から効く。
# **125%ルール** 見直しのとき、新しい返済額は**直前の返済額の125パーセント**が上限。
#
# どちらも法令ではなく、**多くの銀行の約款・商品説明書に置かれている取り扱い**です。
# **付いていない契約もあります**（その場合は金利が動いた回から返済額がそのまま動く）。
# だからこの表は「付いた契約」と「付いていない契約」を**両方**出します。
REVIEW_MONTHS = 60          # 返済額を据え置く回数（5年ルール）
CAP_RATIO = 1.25            # 見直し1回で上げられる上限（125%ルール）

MONTHS_PER_YEAR = 12


# ---------------------------------------------------------------- 返済額
def level_payment(principal: int, annual_rate: float, months: int) -> int:
    """元利均等返済の毎月返済額（**円未満切り上げ**）。

    元利均等の式そのもの。`i = 年利 ÷ 12` として

        返済額 = 元金 × i ÷ (1 − (1+i)^−回数)

    金利0のときは 0 で割るので、そこだけ割り算に落とす。
    """
    if months <= 0:
        raise ValueError(f"回数が {months}")
    i = annual_rate / MONTHS_PER_YEAR
    if i <= 0:
        return math.ceil(principal / months)
    return math.ceil(principal * i / (1 - (1 + i) ** -months))


def interest_of(balance: int, annual_rate: float) -> int:
    """その月の利息（**円未満切り捨て**）。"""
    return math.floor(balance * annual_rate / MONTHS_PER_YEAR)


def freeze_rate(balance: int, payment: int) -> float:
    """**元金が1円も減らなくなる年利。** 掛け算1回で出る。

    毎月の利息が返済額に追いついた瞬間、元金充当額は0になる。

        残高 × 年利 ÷ 12 ＝ 返済額   →   年利 ＝ 返済額 × 12 ÷ 残高
    """
    if balance <= 0:
        raise ValueError(f"残高が {balance}")
    return payment * MONTHS_PER_YEAR / balance


# ---------------------------------------------------------------- 本体
def rate_at(month: int, path: tuple[tuple[int, float], ...]) -> float:
    """`path` は (何回目から, 年利) の並び。**昇順で書くこと。**"""
    rate = path[0][1]
    for start, value in path:
        if month >= start:
            rate = value
    return rate


def simulate(principal: int = 35_000_000,
             years: int = 35,
             path: tuple[tuple[int, float], ...] = ((0, 0.005),),
             *,
             five_year_rule: bool = True,
             cap_125: bool = True) -> dict:
    """1本のローンを、**回ごとに**解く。

    返すもの（**この表の主語は「未払利息」**）:

        rows          回ごとの明細（返済額・利息・元金充当・残高・未払利息の累計）
        unpaid        最後に残った未払利息の累計
        balloon       **最終回に一括で払う額**（残高＋未払利息）
        total         払った総額（毎回の返済額の合計＋最終回の一括）
        payments      返済額が変わった点（何回目・いくら・いくらなら足りたか）
        frozen_months 元金が1円も減らなかった回数
    """
    months = years * MONTHS_PER_YEAR
    balance = principal
    unpaid = 0
    payment = level_payment(principal, path[0][1], months)
    rows: list[dict] = []
    payments = [{"月": 1, "返済額": payment, "必要額": payment, "頭打ち": False}]
    frozen = 0
    paid_sum = 0
    balloon = 0

    for m in range(months):
        rate = rate_at(m, path)

        # ---- 返済額の見直し（**利率の見直しとは別の周期**）
        if m > 0 and balance > 0:
            due = (m % REVIEW_MONTHS == 0) if five_year_rule else \
                (rate != rate_at(m - 1, path))
            if due:
                need = level_payment(balance + unpaid, rate, months - m)
                capped = math.floor(payment * CAP_RATIO)
                new = min(need, capped) if cap_125 else need
                payments.append({"月": m + 1, "返済額": new, "必要額": need,
                                 "頭打ち": bool(cap_125 and need > capped)})
                payment = new

        interest = interest_of(balance, rate)
        last = (m == months - 1)

        if payment >= interest:
            to_principal = min(payment - interest, balance)
            balance -= to_principal
        else:
            to_principal = 0
            unpaid += interest - payment
            frozen += 1
        paid_sum += payment
        rows.append({"月": m + 1, "年利": rate, "返済額": payment,
                     "利息": interest, "元金": to_principal,
                     "残高": balance, "未払利息": unpaid})

        if last:
            # **最終回で終わりません。** 残高と未払利息は、そのあと一括で払う
            balloon = balance + unpaid

    return {"rows": rows, "unpaid": unpaid, "balloon": balloon,
            "total": paid_sum + balloon, "payments": payments,
            "frozen_months": frozen, "first_payment": payments[0]["返済額"]}


# ---------------------------------------------------------------- 表
#: 表の既定。**3,500万円・35年・当初 年0.5パーセント**（画面に出す前提）
PRINCIPAL = 35_000_000
YEARS = 35
START_RATE = 0.005
RISE_AT = 12                # 何回目から上がるか（0 なら初回。12 なら13回目から）


def rise_grid(rates: tuple[float, ...] = (0.010, 0.020, 0.030, 0.035,
                                          0.040, 0.050),
              principal: int = PRINCIPAL, years: int = YEARS,
              start: float = START_RATE, at: int = RISE_AT) -> list[dict]:
    """**上がった先の金利べつ**、未払利息と最終回の一括。"""
    rows = []
    for r in rates:
        s = simulate(principal, years, ((0, start), (at, r)))
        rows.append({
            "上がった先": f"{r * 100:.1f}%",
            "未払利息": s["unpaid"],
            "最終回の一括": s["balloon"],
            "元金が動かない回数": s["frozen_months"],
            "総支払額": s["total"],
        })
    return rows


def rule_grid(rates: tuple[float, ...] = (0.020, 0.030, 0.040, 0.050),
              principal: int = PRINCIPAL, years: int = YEARS,
              start: float = START_RATE, at: int = RISE_AT) -> list[dict]:
    """**ルールが付いた契約と、付いていない契約の総支払額。**

    「返済額が急に上がらない」ほうが、**総額では高くつく**。
    据え置いたぶん元金が減らず、その残高に利息が乗り続けるため。
    """
    rows = []
    for r in rates:
        on = simulate(principal, years, ((0, start), (at, r)))
        off = simulate(principal, years, ((0, start), (at, r)),
                       five_year_rule=False, cap_125=False)
        rows.append({
            "上がった先": f"{r * 100:.1f}%",
            "ルールあり": on["total"],
            "ルールなし": off["total"],
            "差": on["total"] - off["total"],
            "なしの返済額": off["payments"][-1]["返済額"],
        })
    return rows


def catchup_grid(rate: float = 0.040, principal: int = PRINCIPAL,
                 years: int = YEARS, start: float = START_RATE,
                 at: int = RISE_AT) -> list[dict]:
    """**125パーセントの頭打ちが、何回目まで続くか。**

    見直しのたびに「必要額」と「実際に上げられた額」を並べる。
    差がゼロになった回が、返済額が実力に**追いついた**回。
    """
    s = simulate(principal, years, ((0, start), (at, rate)))
    rows = []
    for p in s["payments"]:
        rows.append({
            "何回目から": p["月"],
            "何年目": (p["月"] - 1) // MONTHS_PER_YEAR + 1,
            "実際の返済額": p["返済額"],
            "必要だった額": p["必要額"],
            "足りない額": p["必要額"] - p["返済額"],
            "頭打ち": "頭打ち" if p["頭打ち"] else "追いついた",
        })
    return rows


def timing_grid(starts: tuple[int, ...] = (1, 7, 13, 25, 37, 49, 60, 61),
                rate: float = 0.040, principal: int = PRINCIPAL,
                years: int = YEARS, start: float = START_RATE) -> list[dict]:
    """**同じ上げ幅でも、上がる回が違うと未払利息が変わる。**

    `starts` は**何回目から上がるか**（1 なら初回から）。
    """
    rows = []
    for m in starts:
        s = simulate(principal, years, ((0, start), (m - 1, rate)))
        rows.append({
            "何回目から上がるか": m,
            "未払利息": s["unpaid"],
            "元金が動かない回数": s["frozen_months"],
            "総支払額": s["total"],
        })
    return rows


def freeze_grid(years_list: tuple[int, ...] = (20, 25, 30, 35),
                rates: tuple[float, ...] = (0.003, 0.005, 0.007, 0.010),
                principal: int = PRINCIPAL) -> list[dict]:
    """**元金が1円も減らなくなる金利**を、期間×当初金利で出す。

    **借入額には依りません**（返済額が元金に比例するので、割ると消える）。
    決めているのは**期間と当初金利の2つだけ**。
    """
    rows = []
    for y in years_list:
        row: dict = {"期間": f"{y}年"}
        for r in rates:
            pay = level_payment(principal, r, y * MONTHS_PER_YEAR)
            row[f"当初{r * 100:.1f}%"] = round(
                freeze_rate(principal, pay) * 100, 3)
        rows.append(row)
    return rows


def amount_grid(amounts: tuple[int, ...] = (25_000_000, 30_000_000,
                                            35_000_000, 40_000_000,
                                            50_000_000),
                years: int = YEARS, start: float = START_RATE) -> list[dict]:
    """**借入額を変えても、元金が止まる金利は動かない**ことを見せる表。"""
    rows = []
    for p in amounts:
        pay = level_payment(p, start, years * MONTHS_PER_YEAR)
        rows.append({
            "借入額": p,
            "毎月の返済額": pay,
            "元金が止まる金利": round(freeze_rate(p, pay) * 100, 3),
        })
    return rows


def inside_grid(rate: float = 0.040, principal: int = PRINCIPAL,
                years: int = YEARS, start: float = START_RATE,
                at: int = RISE_AT,
                months: tuple[int, ...] = (12, 13, 24, 36, 48, 60,
                                           61, 120, 121)) -> list[dict]:
    """**返済額は1円も動いていないのに、中身がどう入れ替わるか。**"""
    s = simulate(principal, years, ((0, start), (at, rate)))
    rows = []
    for m in months:
        r = s["rows"][m - 1]
        rows.append({
            "何回目": r["月"],
            "年利": f"{r['年利'] * 100:.1f}%",
            "返済額": r["返済額"],
            "うち利息": r["利息"],
            "うち元金": r["元金"],
            "未払利息の累計": r["未払利息"],
        })
    return rows


# ---------------------------------------------------------------- 前提
ASSUMPTIONS = [
    "借入は3,500万円・35年・元利均等返済、当初の年利は0.5パーセントとして置いています。"
    "ボーナス返済と繰上返済は入れていません",
    "金利が上がる時期は、13回目から年4.0パーセントへ一段だけ上がるものとして置いています。"
    "実際の変動金利は半年ごとに上下しますが、上下を混ぜると原因が分けられなくなるため、"
    "一段だけ動かしています",
    "5年ルール（返済額は60回すえ置き）と125パーセントルール（見直しの上限は直前の1.25倍）は、"
    "法律ではなく銀行の約款の取り扱いです。付いていない契約もあるので、"
    "付いた場合と付かない場合の両方を計算しています",
    "未払利息には利息を付けない前提で積んでいます。"
    "利息を付ける約款なら、この計算より大きくなります",
    "毎月の利息は1円未満切り捨て、毎月の返済額は1円未満切り上げとして置いています",
    "残った残高と未払利息は、最終回のあとに一括で払うものとして置いています。"
    "3,500万円・35年・0.5パーセントから4.0パーセントへ上がる例で1,094,544円です",
    "税・保証料・団体信用生命保険・繰上返済の手数料は、1円も入れていません",
]


# ---------------------------------------------------------------- 検査
def check_tables() -> None:
    """契約の値と、計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    _checks.assumption_values(ASSUMPTIONS, name="hendo")

    # 1. 契約の値（**法令ではないので `statutory` は使わない**）
    if REVIEW_MONTHS != 60:
        raise _checks.TableError(
            f"5年ルールの据え置き回数が {REVIEW_MONTHS}。5年 ＝ 60回のはず")
    if CAP_RATIO != 1.25:
        raise _checks.TableError(
            f"125パーセントルールの上限が {CAP_RATIO}。1.25 のはず")

    # 2. 元利均等の式が、教科書の形と合っていること
    #    金利0なら「元金 ÷ 回数」に落ちる
    _checks.rounding(level_payment(3_600_000, 0.0, 360), 10_000,
                     "金利0・360回の返済額")
    #    3,500万円・35年・0.5パーセントの毎月返済額
    _checks.rounding(level_payment(PRINCIPAL, START_RATE,
                                   YEARS * MONTHS_PER_YEAR), 90_855,
                     "3,500万円・35年・0.5パーセントの毎月返済額")

    # 3. 向き —— 上がった先が高いほど、未払利息も総支払額も増える
    _checks.increases_with(
        lambda r: simulate(PRINCIPAL, YEARS,
                           ((0, START_RATE), (RISE_AT, r)))["total"],
        [0.02, 0.03, 0.04, 0.05],
        "上がった先の金利が高いのに、総支払額が増えていない")
    _checks.increases_with(
        lambda r: simulate(PRINCIPAL, YEARS,
                           ((0, START_RATE), (RISE_AT, r)))["unpaid"],
        [0.035, 0.04, 0.045, 0.05],
        "上がった先の金利が高いのに、未払利息が増えていない")

    # 4. **この計算の主題そのもの** —— 遅く上がるほど未払利息は小さい
    _checks.decreases_with(
        lambda m: simulate(PRINCIPAL, YEARS,
                           ((0, START_RATE), (m, 0.040)))["unpaid"],
        [0, 12, 24, 36, 48],
        "上がるのが遅いのに、未払利息が減っていない")

    # 5. **ルールが付いたほうが総額は多い**（この表の一番の主張）
    for r in (0.02, 0.03, 0.04, 0.05):
        on = simulate(PRINCIPAL, YEARS, ((0, START_RATE), (RISE_AT, r)))
        off = simulate(PRINCIPAL, YEARS, ((0, START_RATE), (RISE_AT, r)),
                       five_year_rule=False, cap_125=False)
        _checks.greater(on["total"], off["total"],
                        f"上がった先 {r * 100:.1f}% で、"
                        "ルールありの総支払額がルールなし以下")

    # 6. **元金が止まる金利は、借入額に依らない**（割ると消える）
    seen = {row["元金が止まる金利"] for row in amount_grid()}
    if len(seen) != 1:
        raise _checks.TableError(
            f"元金が止まる金利が借入額で変わっている: {sorted(seen)}。"
            "返済額は元金に比例するので、割れば消えるはず")

    # 7. 期間が長いほど、元金が止まる金利は低い（同じ当初金利で）
    _checks.decreases_with(
        lambda y: freeze_rate(
            PRINCIPAL, level_payment(PRINCIPAL, START_RATE,
                                     y * MONTHS_PER_YEAR)),
        [20, 25, 30, 35],
        "期間が長いのに、元金が止まる金利が下がっていない")

    # 8. 表の行が重なっていないこと
    _checks.unique_by(rise_grid(), lambda r: r["上がった先"], "上がった先")
    _checks.unique_by(timing_grid(), lambda r: r["何回目から上がるか"],
                      "上がる回")


def main() -> None:
    check_tables()
    print("契約の値と計算の向きの検査: 通過")

    print("\n=== 金利が上がった先べつ 最終回に一括で払う額（3,500万円・35年・当初0.5%・13回目から上昇） ===")
    for row in rise_grid():
        print(row)

    print("\n=== 返済額が上がらないルールが付いた契約と、付いていない契約の総支払額 ===")
    for row in rule_grid():
        print(row)

    print("\n=== 125パーセントの頭打ちが解けるのは何年目か（0.5%→4.0%） ===")
    for row in catchup_grid():
        print(row)

    print("\n=== 同じ上げ幅でも、上がる回が1回ずれると未払利息はいくら変わるか（→4.0%） ===")
    for row in timing_grid():
        print(row)

    print("\n=== 元金が1円も減らなくなる金利は、期間と当初金利だけで決まる ===")
    for row in freeze_grid():
        print(row)

    print("\n=== 借入額を2倍にしても、元金が止まる金利は1ミリも動かない（35年・当初0.5%） ===")
    for row in amount_grid():
        print(row)

    print("\n=== 返済額は1円も動いていないのに、中身がどう入れ替わるか（0.5%→4.0%） ===")
    for row in inside_grid():
        print(row)

    print("\n=== 前提 ===")
    for line in ASSUMPTIONS:
        print("-", line)


if __name__ == "__main__":
    main()
