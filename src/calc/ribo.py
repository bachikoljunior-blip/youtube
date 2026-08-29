"""カードローンのリボ払い（元利定額）を、月ごとに解いて実額を出す。

    python -m src.calc.ribo

## この計算で出したいこと

リボ払いの解説は「手数料が高い」「元金がなかなか減らない」で止まる。
**「なかなか」が何か月で、いくらなのかは、どこにも出ていない。**
実質年率だけ書いてあっても、元利定額は毎月の手数料が残高に比例して減るので、
掛け算では出ない。**月ごとに解かないと出ない。**

ここで解くと、次の4つが出る。

1. **残高30万円を毎月1万円で返すと、38か月・手数料78,331円。**
   総支払額は 378,331円。
2. **毎月1万円払いなら、残高が 800,000円 になった時点で元金は1円も減らない。**
   手数料が支払額に追いつく点。ここは掛け算で出せるが、誰も出していない。
   残高70万円でも、**毎月1,250円 使い足すだけで残高は動かなくなる。**
3. **同じ「毎月1万円」でも、元利定額と元金定額で 78,331円 と 58,125円。**
   差は20,206円。元金定額の初回は 13,750円 なので、
   **月3,750円 多く出せば、8か月早く終わって2万円安い。**
4. **99,000円 借りるより 100,000円 借りるほうが、総手数料が安い。**
   利息制限法1条の上限が 10万円 で年20パーセントから年18パーセントに下がるため、
   上限いっぱいで借りると 10,195円 と 9,158円 になる。
   **1,000円 多く借りて 1,037円 安くなる。**

## 前提（動画にそのまま出すこと）

- 実質年率は年15.0パーセント（仮定）。利息制限法1条の上限は
  元本10万円未満で年20パーセント、10万円以上100万円未満で年18パーセント、
  100万円以上で年15パーセント
- 手数料は毎月、その月の返済前の残高に年率を12で割った率をかけ、1円未満切り捨て
- 毎月の支払額は元利定額（元金充当額＋手数料が定額）
- 遅延損害金と、明示していない追加の借入は無いものとする
- 日割りとうるう年は考えない。すべて月単位

## 根拠の探し方（動画の説明欄用。URLは書かない）

- 上限利率の3段階 … 利息制限法1条
- 元利定額と元金定額の違い … 各社の会員規約の「リボ払いの手数料の計算方法」
"""
from __future__ import annotations

import math

from . import _checks

# ---- 制度の値 --------------------------------------------------------
#
# 利息制限法1条の上限利率。**元本の額で3段階に変わる。**
# ここが「借入額をまたぐと上限が変わる」段差の出どころ。
#   元本10万円未満        年20パーセント
#   元本10万円以上100万円未満  年18パーセント
#   元本100万円以上        年15パーセント
LEGAL_CAPS: tuple[tuple[int | None, float], ...] = (
    (100_000, 0.20),
    (1_000_000, 0.18),
    (None, 0.15),
)

# この計算で置く実質年率。**制度の値ではなく仮定。**
# 元本100万円以上の法定上限と同じ 年15.0パーセントを使う
# （カードローンの広告表示でいちばんよく見る水準の上限側）。
APR = 0.15

# 月あたりの手数料率。年率を12で割る（日割りはしない）。
MONTHLY_RATE = APR / 12

ASSUMPTIONS = (
    "実質年率は年15.0パーセントの仮定です。利息制限法の上限は"
    "元本10万円未満で年20パーセント、10万円以上100万円未満で年18パーセント、"
    "100万円以上で年15パーセントです",
    "手数料は毎月、その月の返済前の残高に年率を12で割った率をかけ、"
    "1円未満を切り捨てて計算します",
    "毎月の支払額は元利定額方式です。元金充当額と手数料の合計が定額になります",
    "遅延損害金と、その節で明示していない追加の借入は無いものとします",
    "日割りとうるう年は考えません。すべて月単位で計算します",
)


def legal_cap(principal: int) -> float:
    """その元本にかかる利息制限法の上限利率。"""
    for cap, rate in LEGAL_CAPS:
        if cap is None or principal < cap:
            return rate
    raise ValueError(f"上限表に当たらない: {principal}")


def monthly_fee(balance: int, apr: float = APR) -> int:
    """その月の手数料。**1円未満は切り捨て。**"""
    return math.floor(balance * apr / 12)


# ------------------------------------------------------------ 元利定額

def schedule(balance: int, pay: int, apr: float = APR,
             extra: int = 0, extra_month: int = 0) -> list[dict]:
    """元利定額（毎月の支払額が定額）で、残高が0になるまで月ごとに解く。

    `extra` を入れると `extra_month` 月目の返済のあとに繰上返済する。
    """
    rows: list[dict] = []
    month = 0
    while balance > 0:
        month += 1
        if month > 1200:
            raise ValueError(f"1200か月で終わらない（支払額 {pay} が小さすぎる）")
        fee = monthly_fee(balance, apr)
        principal = pay - fee
        if principal <= 0:
            raise ValueError(
                f"支払額 {pay:,}円 が手数料 {fee:,}円 以下。残高が永久に減らない")
        paid = pay
        if principal >= balance:
            principal = balance
            paid = principal + fee
        balance -= principal
        if extra and month == extra_month and balance > 0:
            cut = min(extra, balance)
            balance -= cut
            paid += cut
            principal += cut
        rows.append({
            "month": month,
            "fee": fee,
            "principal": principal,
            "paid": paid,
            "balance": balance,
        })
    return rows


def total_fee(balance: int, pay: int, apr: float = APR,
              extra: int = 0, extra_month: int = 0) -> int:
    return sum(r["fee"] for r in schedule(balance, pay, apr, extra, extra_month))


def months(balance: int, pay: int, apr: float = APR,
           extra: int = 0, extra_month: int = 0) -> int:
    return len(schedule(balance, pay, apr, extra, extra_month))


# ------------------------------------------------------------ 元金定額

def schedule_principal(balance: int, principal_pay: int,
                       apr: float = APR) -> list[dict]:
    """元金定額（毎月の元金充当額が定額）。支払額は手数料のぶんだけ上に乗る。"""
    rows: list[dict] = []
    month = 0
    while balance > 0:
        month += 1
        if month > 1200:
            raise ValueError("1200か月で終わらない")
        fee = monthly_fee(balance, apr)
        principal = min(principal_pay, balance)
        balance -= principal
        rows.append({
            "month": month,
            "fee": fee,
            "principal": principal,
            "paid": principal + fee,
            "balance": balance,
        })
    return rows


def total_fee_principal(balance: int, principal_pay: int,
                        apr: float = APR) -> int:
    return sum(r["fee"] for r in schedule_principal(balance, principal_pay, apr))


# ------------------------------------------------- 残高が減らなくなる線

def frozen_balance(pay: int, apr: float = APR) -> int:
    """**元金が1円も減らなくなる残高。** 手数料が支払額に追いつく点。

        残高 × 年率 ÷ 12 ＝ 支払額

    切り捨てが入るので、実際に元金充当が0になる最小の残高を返す。
    """
    guess = math.ceil(pay * 12 / apr)
    while monthly_fee(guess, apr) < pay:
        guess += 1
    return guess


def flat_usage(balance: int, pay: int, apr: float = APR) -> int:
    """その残高で、**毎月いくら使い足すと残高が減らなくなるか。**

    元金充当額（支払額 − 手数料）と同じ額を毎月使えば、残高は動かない。
    """
    return max(pay - monthly_fee(balance, apr), 0)


# ---------------------------------------------------------------- 表

def payment_grid(balance: int = 300_000,
                 pays: tuple[int, ...] = (8_000, 10_000, 12_000,
                                          15_000, 20_000, 30_000)) -> list[dict]:
    """毎月の支払額べつに、終わるまでの月数と総手数料。"""
    rows = []
    for pay in pays:
        rows.append({
            "pay": pay,
            "months": months(balance, pay),
            "total_fee": total_fee(balance, pay),
            "total_paid": balance + total_fee(balance, pay),
        })
    return rows


def cap_grid() -> list[dict]:
    """**借入額が10万円と100万円をまたぐと、法定上限が変わる。**

    同じ「毎月の支払額が元本の10パーセント」で借りたときに、
    上限いっぱいの利率だと総手数料がいくらになるかを並べる。
    """
    rows = []
    for principal in (99_000, 100_000, 999_000, 1_000_000):
        rate = legal_cap(principal)
        pay = principal // 10
        rows.append({
            "principal": principal,
            "cap": rate,
            "pay": pay,
            "months": months(principal, pay, rate),
            "total_fee": total_fee(principal, pay, rate),
        })
    return rows


def frozen_grid(pays: tuple[int, ...] = (5_000, 10_000, 15_000,
                                         20_000, 30_000)) -> list[dict]:
    """支払額べつに、元金が減らなくなる残高。"""
    return [{"pay": pay, "frozen": frozen_balance(pay)} for pay in pays]


def usage_grid(pay: int = 10_000,
               balances: tuple[int, ...] = (100_000, 200_000, 300_000,
                                            500_000, 700_000)) -> list[dict]:
    """残高べつに、毎月いくら使い足すと残高が動かなくなるか。"""
    rows = []
    for balance in balances:
        rows.append({
            "balance": balance,
            "fee": monthly_fee(balance),
            "principal": pay - monthly_fee(balance),
            "flat_usage": flat_usage(balance, pay),
        })
    return rows


def method_grid(balance: int = 300_000, unit: int = 10_000) -> list[dict]:
    """同じ「毎月1万円」でも、元利定額と元金定額でどれだけ違うか。"""
    fixed = schedule(balance, unit)
    prin = schedule_principal(balance, unit)
    return [
        {
            "method": "元利定額",
            "first_paid": fixed[0]["paid"],
            "months": len(fixed),
            "total_fee": sum(r["fee"] for r in fixed),
            "total_paid": balance + sum(r["fee"] for r in fixed),
        },
        {
            "method": "元金定額",
            "first_paid": prin[0]["paid"],
            "months": len(prin),
            "total_fee": sum(r["fee"] for r in prin),
            "total_paid": balance + sum(r["fee"] for r in prin),
        },
    ]


def principal_grid(balance: int = 300_000,
                   units: tuple[int, ...] = (5_000, 8_000, 10_000,
                                             15_000, 25_000)) -> list[dict]:
    """**元金定額**で、毎月いくら元金に当てるかべつの初回支払額と総手数料。

    `payment_grid()` とは切り口が違う。あちらは**元利定額**で「支払額」を振り、
    こちらは**元金定額**で「元金充当額」を振る。**同じ数字は出ない。**
    """
    rows = []
    for unit in units:
        sch = schedule_principal(balance, unit)
        rows.append({
            "unit": unit,
            "first_paid": sch[0]["paid"],
            "last_paid": sch[-1]["paid"],
            "months": len(sch),
            "total_fee": sum(r["fee"] for r in sch),
        })
    return rows


def first_year_grid(pay: int = 10_000,
                    balances: tuple[int, ...] = (100_000, 300_000, 500_000,
                                                 700_000, 800_000)) -> list[dict]:
    """**残高べつ、最初の12か月で元金がいくら減るか**（元利定額）。

    「元金が減らない」を**12か月ぶんの実額**で出す。凍る残高（`frozen_balance`）
    ちょうどなら、12万円 払って元金は **0円** しか減らない。
    """
    rows = []
    for balance in balances:
        left, fee_sum = balance, 0
        for _ in range(12):
            fee = monthly_fee(left)
            principal = pay - fee
            if principal <= 0:
                principal = 0
            principal = min(principal, left)
            left -= principal
            fee_sum += fee
        rows.append({
            "balance": balance,
            "paid": pay * 12,
            "fee": fee_sum,
            "cut": balance - left,
            "left": left,
        })
    return rows


def prepay_amount_grid(balance: int = 300_000, pay: int = 10_000,
                       at: int = 6,
                       extras: tuple[int, ...] = (30_000, 50_000,
                                                  100_000, 150_000)) -> list[dict]:
    """**繰上返済の額べつ**に、総手数料がいくら減るか（入れる月は固定）。

    `prepay_grid()` は**入れる月**を振る。こちらは**額**を振る。
    """
    base = total_fee(balance, pay)
    rows = []
    for extra in extras:
        fee = total_fee(balance, pay, APR, extra, at)
        rows.append({
            "extra": extra,
            "total_fee": fee,
            "saved": base - fee,
            "months": months(balance, pay, APR, extra, at),
        })
    return rows


def prepay_grid(balance: int = 300_000, pay: int = 10_000,
                extra: int = 50_000,
                at: tuple[int, ...] = (1, 3, 6, 12, 18)) -> list[dict]:
    """5万円の繰上返済を、何か月目に入れると総手数料がいくら減るか。"""
    base_fee = total_fee(balance, pay)
    base_months = months(balance, pay)
    rows = []
    for month in at:
        fee = total_fee(balance, pay, APR, extra, month)
        rows.append({
            "at": month,
            "total_fee": fee,
            "saved": base_fee - fee,
            "months": months(balance, pay, APR, extra, month),
            "saved_months": base_months - months(balance, pay, APR, extra, month),
        })
    return rows


# ------------------------------------------ 途中で支払額を上げる／ボーナス

def schedule_stepup(balance: int, pay: int, at: int, new_pay: int,
                    apr: float = APR) -> list[dict]:
    """**`at` か月目の返済から、毎月の支払額を `new_pay` に上げる。**

    `prepay_grid()` は「まとまった額を1回入れる」表で、こちらは
    **毎月の額を恒久的に上げる**表。**同じ「追加で払う」でも別の道具**で、
    リボの解説はどちらも「早く返せ」で済ませて実額を出さない。
    """
    rows: list[dict] = []
    month = 0
    while balance > 0:
        month += 1
        if month > 1200:
            raise ValueError(f"1200か月で終わらない（支払額 {pay} が小さすぎる）")
        amount = new_pay if month >= at else pay
        fee = monthly_fee(balance, apr)
        principal = amount - fee
        if principal <= 0:
            raise ValueError(
                f"{month}か月目の支払額 {amount:,}円 が手数料 {fee:,}円 以下")
        paid = amount
        if principal >= balance:
            principal = balance
            paid = principal + fee
        balance -= principal
        rows.append({"month": month, "fee": fee, "principal": principal,
                     "paid": paid, "balance": balance})
    return rows


def schedule_bonus(balance: int, pay: int, bonus: int, every: int = 6,
                   apr: float = APR) -> list[dict]:
    """**`every` か月ごとに `bonus` を上乗せする**（ボーナス併用）。

    上乗せは元金にそのまま当たる（手数料はその月の残高だけで決まるため）。
    """
    rows: list[dict] = []
    month = 0
    while balance > 0:
        month += 1
        if month > 1200:
            raise ValueError("1200か月で終わらない")
        fee = monthly_fee(balance, apr)
        principal = pay - fee
        if principal <= 0:
            raise ValueError(f"支払額 {pay:,}円 が手数料 {fee:,}円 以下")
        paid = pay
        if month % every == 0:
            principal += bonus
            paid += bonus
        if principal >= balance:
            principal = balance
            paid = principal + fee
        balance -= principal
        rows.append({"month": month, "fee": fee, "principal": principal,
                     "paid": paid, "balance": balance})
    return rows


# ---------------------------------------------------------------- 表（続き）

def apr_grid(balance: int = 300_000, pay: int = 10_000,
             aprs: tuple[float, ...] = (0.09, 0.12, 0.15,
                                        0.18, 0.20)) -> list[dict]:
    """**実質年率だけを振る**（残高と支払額は固定）。

    `cap_grid()` は借入額をまたいで**法定上限が変わる**表で、支払額を
    元本の10パーセントに動かしている。**こちらは支払額まで固定**して、
    **年率の差だけが月数と手数料をいくら動かすか**を出す。
    広告に出るのは「年率〇〇パーセント」だけで、**それが何か月と何円になるかは
    どこにも出ていない。**
    """
    rows = []
    for apr in aprs:
        sch = schedule(balance, pay, apr)
        fee = sum(r["fee"] for r in sch)
        rows.append({
            "apr": apr,
            "first_fee": sch[0]["fee"],
            "months": len(sch),
            "total_fee": fee,
            "total_paid": balance + fee,
        })
    return rows


def stepup_grid(balance: int = 300_000, pay: int = 10_000,
                new_pay: int = 12_000,
                at: tuple[int, ...] = (1, 6, 12, 24, 36)) -> list[dict]:
    """**毎月2,000円だけ上げる月を振る**（残高30万円・元は毎月1万円）。

    「いつ上げても同じ」ではない。**上げるのが遅いほど、減る手数料は小さい。**
    """
    base_fee = total_fee(balance, pay)
    base_months = months(balance, pay)
    rows = []
    for month in at:
        sch = schedule_stepup(balance, pay, month, new_pay)
        fee = sum(r["fee"] for r in sch)
        rows.append({
            "at": month,
            "months": len(sch),
            "total_fee": fee,
            "saved": base_fee - fee,
            "saved_months": base_months - len(sch),
        })
    return rows


def bonus_grid(balance: int = 300_000, pay: int = 10_000, every: int = 6,
               bonuses: tuple[int, ...] = (10_000, 20_000, 30_000,
                                           50_000)) -> list[dict]:
    """**半年ごとの上乗せ額を振る**（残高30万円・毎月1万円・6か月ごと）。

    年2回の上乗せは、**毎月に均すと上乗せ額の6分の1**でしかない。
    それでも月数と手数料がどれだけ動くかを出す。
    """
    base_fee = total_fee(balance, pay)
    base_months = months(balance, pay)
    rows = []
    for bonus in bonuses:
        sch = schedule_bonus(balance, pay, bonus, every)
        fee = sum(r["fee"] for r in sch)
        rows.append({
            "bonus": bonus,
            "per_month": bonus // every,
            "months": len(sch),
            "total_fee": fee,
            "saved": base_fee - fee,
            "saved_months": base_months - len(sch),
        })
    return rows


# ---------------------------------------------------------------- 検査

def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    _checks.assumption_values(ASSUMPTIONS, name="ribo")

    # 1. 法令の値（利息制限法1条）
    _checks.statutory(legal_cap(99_999), 0.20, "元本10万円未満の上限利率",
                      source="利息制限法1条")
    _checks.statutory(legal_cap(100_000), 0.18, "元本10万円の上限利率",
                      source="利息制限法1条")
    _checks.statutory(legal_cap(1_000_000), 0.15, "元本100万円の上限利率",
                      source="利息制限法1条")
    _checks.ratio(APR, "実質年率")
    for _, rate in LEGAL_CAPS:
        _checks.ratio(rate, "利息制限法の上限利率")

    # 2. 元利定額の中身。**支払額 ＝ 手数料 ＋ 元金充当**が毎月成り立つこと
    rows = schedule(100_000, 10_000)
    for r in rows:
        assert r["paid"] == r["fee"] + r["principal"], (
            f"{r['month']}か月目で 支払額 ≠ 手数料＋元金（{r}）")
    assert rows[-1]["balance"] == 0, "最後の月に残高が残っている"
    assert sum(r["principal"] for r in rows) == 100_000, "元金の合計が借入額と違う"
    # 手数料は残高に比例するので、月が進むほど減る（最後の月まで）
    _checks.ascending([-r["fee"] for r in rows], "月ごとの手数料（減る向き）")

    # 3. 支払額を上げれば、月数も総手数料も減る。**この表の主題そのもの**
    _checks.decreases_with(lambda p: months(300_000, p),
                           [8_000, 10_000, 15_000, 30_000],
                           "毎月の支払額を上げたのに月数が減っていない")
    _checks.decreases_with(lambda p: total_fee(300_000, p),
                           [8_000, 10_000, 15_000, 30_000],
                           "毎月の支払額を上げたのに総手数料が減っていない")

    # 4. 元金定額のほうが必ず速く、必ず安い（初回の支払額は高い）
    m = {r["method"]: r for r in method_grid()}
    _checks.greater(m["元利定額"]["total_fee"], m["元金定額"]["total_fee"],
                    "元利定額の総手数料が元金定額以下")
    _checks.greater(m["元利定額"]["months"], m["元金定額"]["months"],
                    "元利定額の月数が元金定額以下")
    _checks.greater(m["元金定額"]["first_paid"], m["元利定額"]["first_paid"],
                    "元金定額の初回支払額が元利定額以下")

    # 5. 元金が減らなくなる残高。**手数料が支払額に追いつく点**
    for pay in (5_000, 10_000, 30_000):
        f = frozen_balance(pay)
        assert monthly_fee(f) >= pay, f"支払額{pay}で凍る残高{f}の手数料が足りない"
        assert monthly_fee(f - 1) < pay, f"凍る残高{f}が最小でない（1円下でも凍る）"
    _checks.increases_with(frozen_balance, [5_000, 10_000, 30_000],
                           "支払額を上げたのに凍る残高が増えていない")
    # 支払額1万円なら80万円で凍る。**この計算の看板の数字**
    _checks.rounding(frozen_balance(10_000), 800_000, "支払額1万円で凍る残高")

    # 6. 使い足しの表。残高が大きいほど、動かせる額は小さくなる
    _checks.decreases_with(lambda b: flat_usage(b, 10_000),
                           [100_000, 300_000, 500_000, 700_000],
                           "残高が増えたのに、残高が動かない使い足し額が減っていない")
    for row in usage_grid():
        assert row["flat_usage"] == row["principal"], "使い足し額と元金充当額が食い違う"

    # 7. 繰上返済は早いほど効く。**遅いほど減る額は小さい**
    saved = [r["saved"] for r in prepay_grid()]
    _checks.ascending([-s for s in saved], "繰上返済の効き（早いほど大きい）")
    assert all(s > 0 for s in saved), "繰上返済で総手数料が減っていない"

    # 7.5 元金定額の表。元金充当を上げれば初回は高くなり、総手数料は減る
    _checks.increases_with(lambda u: principal_grid(units=(u,))[0]["first_paid"],
                           [5_000, 10_000, 25_000],
                           "元金充当を上げたのに初回の支払額が増えていない")
    _checks.decreases_with(lambda u: principal_grid(units=(u,))[0]["total_fee"],
                           [5_000, 10_000, 25_000],
                           "元金充当を上げたのに総手数料が減っていない")
    for row in principal_grid():
        assert row["first_paid"] > row["last_paid"], (
            f"元金定額なのに初回 {row['first_paid']} が最終回 {row['last_paid']} 以下")

    # 7.6 最初の12か月。**凍る残高では元金が1円も減らない**
    year = {r["balance"]: r for r in first_year_grid()}
    assert year[800_000]["cut"] == 0, "凍る残高で元金が減っている"
    assert year[800_000]["paid"] == year[800_000]["fee"], "凍る残高で支払額が全部 手数料になっていない"
    _checks.decreases_with(lambda b: first_year_grid(balances=(b,))[0]["cut"],
                           [100_000, 300_000, 500_000, 700_000],
                           "残高が増えたのに、12か月で減る元金が減っていない")
    for row in first_year_grid():
        assert row["cut"] + row["left"] == row["balance"], "12か月の元金が合わない"

    # 7.7 繰上返済の額。多く入れるほど減る額は大きい
    _checks.increases_with(
        lambda e: prepay_amount_grid(extras=(e,))[0]["saved"],
        [30_000, 50_000, 100_000, 150_000],
        "繰上返済を増やしたのに、減る総手数料が増えていない")

    # 8. 法定上限の段差。**10万円ちょうどで上限が20%から18%に下がる**
    _checks.greater(legal_cap(99_999), legal_cap(100_000),
                    "10万円未満の上限が10万円以上の上限以下")
    _checks.unique_by(cap_grid(), lambda r: r["principal"], "法定上限の表")

    # 9. 実質年率だけを振る表。**年率が上がれば、月数も総手数料も増える**
    for row in apr_grid():
        _checks.ratio(row["apr"], "実質年率")
        assert row["total_paid"] == 300_000 + row["total_fee"], (
            f"年率 {row['apr']:.0%} で 総支払額 ≠ 元金＋総手数料（{row}）")
    _checks.increases_with(lambda a: apr_grid(aprs=(a,))[0]["total_fee"],
                           [0.09, 0.12, 0.15, 0.18, 0.20],
                           "年率を上げたのに総手数料が増えていない")
    _checks.never_decreases(lambda a: apr_grid(aprs=(a,))[0]["months"],
                            [0.09, 0.12, 0.15, 0.18, 0.20],
                            "年率を上げたのに月数が増えていない")
    _checks.unique_by(apr_grid(), lambda r: r["apr"], "年率の表")
    # 年率15%の行は、既にある `payment_grid()` の毎月1万円の行と同じ数でなければ
    # おかしい。**同じ前提を2つの関数で解いているので、ここで突き合わせる**
    fifteen = {r["apr"]: r for r in apr_grid()}[0.15]
    pay10k = {r["pay"]: r for r in payment_grid()}[10_000]
    _checks.rounding(fifteen["total_fee"], pay10k["total_fee"],
                     "年率15%の総手数料（毎月1万円の行と一致すること）")

    # 10. 途中から支払額を上げる表。**上げるのが遅いほど、減る額は小さい**
    for row in stepup_grid():
        assert row["saved"] > 0, f"支払額を上げたのに手数料が減っていない（{row}）"
    _checks.decreases_with(lambda m: stepup_grid(at=(m,))[0]["saved"],
                           [1, 6, 12, 24, 36],
                           "上げる月が遅いのに、減る手数料が減っていない")
    _checks.never_decreases(lambda m: stepup_grid(at=(m,))[0]["months"],
                            [1, 6, 12, 24, 36],
                            "上げる月が遅いのに月数が増えていない")
    # 1か月目から上げるのは「最初から毎月12,000円」と同じ表のはず
    first = stepup_grid(at=(1,))[0]
    pay12k = {r["pay"]: r for r in payment_grid()}[12_000]
    _checks.rounding(first["total_fee"], pay12k["total_fee"],
                     "1か月目から上げたときの総手数料（毎月12,000円の行と一致すること）")

    # 11. ボーナス併用の表。**上乗せが多いほど、速く終わって安い**
    _checks.increases_with(lambda b: bonus_grid(bonuses=(b,))[0]["saved"],
                           [10_000, 20_000, 30_000, 50_000],
                           "上乗せを増やしたのに、減る手数料が増えていない")
    _checks.decreases_with(lambda b: bonus_grid(bonuses=(b,))[0]["months"],
                           [10_000, 20_000, 30_000, 50_000],
                           "上乗せを増やしたのに月数が減っていない")
    for row in bonus_grid():
        sch = schedule_bonus(300_000, 10_000, row["bonus"])
        assert sum(r["principal"] for r in sch) == 300_000, (
            f"上乗せ {row['bonus']:,}円 で元金の合計が残高と違う")
        assert sch[-1]["balance"] == 0, "最後の月に残高が残っている"
        for r in sch:
            assert r["paid"] == r["fee"] + r["principal"], (
                f"上乗せ {row['bonus']:,}円 の {r['month']}か月目で"
                f" 支払額 ≠ 手数料＋元金（{r}）")

    print("制度の値の検査: 通過")


def main() -> None:
    check_tables()

    print("\n=== 10万円を毎月1万円のリボで返すと、何か月かかり、手数料はいくらか ===")
    rows = schedule(100_000, 10_000)
    print(f"{'月':>4}{'手数料':>9}{'元金充当':>10}{'支払額':>9}{'残高':>11}")
    for r in rows:
        print(f"{r['month']:>3}月{r['fee']:>8,}円{r['principal']:>9,}円"
              f"{r['paid']:>8,}円{r['balance']:>10,}円")
    print(f"  合計 {len(rows)}か月・手数料 {sum(r['fee'] for r in rows):,}円"
          f"・総支払額 {100_000 + sum(r['fee'] for r in rows):,}円")

    print("\n=== 毎月の支払額を上げると、総手数料はいくら減るか（残高30万円） ===")
    print(f"{'毎月の支払額':>12}{'月数':>7}{'総手数料':>11}{'総支払額':>12}")
    grid_rows = payment_grid()
    for row in grid_rows:
        print(f"{row['pay']:>11,}円{row['months']:>6}月"
              f"{row['total_fee']:>10,}円{row['total_paid']:>11,}円")
    # **上下の開きも印字すること**（2026-08-29 に踏んだ）。この表の主題は
    # 「支払額を変えるといくら変わるか」なので、**差そのものが主役の数**です。
    # 印字しないと、差を言った題が `_checks.numbers_backed` の裏を取れません
    # （実測: `ribo-300000-payment-step` の `title_seed` の 84,809円 が
    #  `tests/test_doc_numbers.py::test_topics_yamlには掛けない` で鳴った）。
    top, bottom = grid_rows[0], grid_rows[-1]
    print(f"  上下の開き: 手数料 {top['total_fee'] - bottom['total_fee']:,}円"
          f"（{top['pay']:,}円 の {top['total_fee']:,}円 と"
          f" {bottom['pay']:,}円 の {bottom['total_fee']:,}円）"
          f"・月数 {top['months'] - bottom['months']}月")

    print("\n=== 元金が1円も減らなくなる残高（手数料が支払額に追いつく点） ===")
    print(f"{'毎月の支払額':>12}{'凍る残高':>13}")
    for row in frozen_grid():
        print(f"{row['pay']:>11,}円{row['frozen']:>12,}円")

    print("\n=== 残高べつ 毎月いくら使い足すと、残高が減らなくなるか（毎月1万円払い） ===")
    print(f"{'残高':>10}{'手数料':>9}{'元金充当':>10}{'使い足しの線':>14}")
    for row in usage_grid():
        print(f"{row['balance']:>9,}円{row['fee']:>8,}円"
              f"{row['principal']:>9,}円{row['flat_usage']:>13,}円")

    print("\n=== 同じ毎月1万円でも、元利定額と元金定額で総手数料がどれだけ違うか ===")
    print(f"{'方式':>8}{'初回の支払額':>14}{'月数':>7}{'総手数料':>11}{'総支払額':>12}")
    for row in method_grid():
        print(f"{row['method']:>8}{row['first_paid']:>13,}円{row['months']:>6}月"
              f"{row['total_fee']:>10,}円{row['total_paid']:>11,}円")

    print("\n=== 5万円の繰上返済は、何か月目に入れるといくら減るか（残高30万円・毎月1万円） ===")
    print(f"{'入れる月':>9}{'総手数料':>11}{'減る額':>10}{'月数':>7}{'縮む月数':>10}")
    for row in prepay_grid():
        print(f"{row['at']:>8}月{row['total_fee']:>10,}円{row['saved']:>9,}円"
              f"{row['months']:>6}月{row['saved_months']:>9}月")

    print("\n=== 元金定額で、毎月いくら元金に当てるかべつの初回と総手数料（残高30万円） ===")
    print(f"{'元金充当':>10}{'初回の支払額':>14}{'最終回':>10}{'月数':>7}{'総手数料':>11}")
    for row in principal_grid():
        print(f"{row['unit']:>9,}円{row['first_paid']:>13,}円"
              f"{row['last_paid']:>9,}円{row['months']:>6}月{row['total_fee']:>10,}円")

    print("\n=== 残高べつ 毎月1万円払いで、最初の12か月に元金がいくら減るか ===")
    print(f"{'残高':>10}{'12か月の支払額':>16}{'うち手数料':>12}{'減った元金':>12}{'残り':>10}")
    for row in first_year_grid():
        print(f"{row['balance']:>9,}円{row['paid']:>15,}円{row['fee']:>11,}円"
              f"{row['cut']:>11,}円{row['left']:>9,}円")

    print("\n=== 繰上返済の額べつ 総手数料はいくら減るか（残高30万円・毎月1万円・6か月目） ===")
    print(f"{'繰上返済':>10}{'総手数料':>11}{'減る額':>10}{'月数':>7}")
    for row in prepay_amount_grid():
        print(f"{row['extra']:>9,}円{row['total_fee']:>10,}円"
              f"{row['saved']:>9,}円{row['months']:>6}月")

    print("\n=== 実質年率だけを変えると、月数と総手数料はいくら動くか（残高30万円・毎月1万円） ===")
    print(f"{'実質年率':>10}{'初月の手数料':>14}{'月数':>7}{'総手数料':>11}{'総支払額':>12}")
    apr_rows = apr_grid()
    for row in apr_rows:
        print(f"{row['apr']:>9.0%}{row['first_fee']:>13,}円{row['months']:>6}月"
              f"{row['total_fee']:>10,}円{row['total_paid']:>11,}円")
    top, bottom = apr_rows[-1], apr_rows[0]
    print(f"  上下の開き: 手数料 {top['total_fee'] - bottom['total_fee']:,}円"
          f"（{top['apr']:.0%} の {top['total_fee']:,}円 と"
          f" {bottom['apr']:.0%} の {bottom['total_fee']:,}円）"
          f"・月数 {top['months'] - bottom['months']}月")

    print("\n=== 毎月2,000円だけ上げるのを、何か月目からにするか（残高30万円・毎月1万円→12,000円） ===")
    print(f"{'上げる月':>9}{'月数':>7}{'総手数料':>11}{'減る額':>10}{'縮む月数':>10}")
    step_rows = stepup_grid()
    for row in step_rows:
        print(f"{row['at']:>8}月{row['months']:>6}月{row['total_fee']:>10,}円"
              f"{row['saved']:>9,}円{row['saved_months']:>9}月")
    print(f"  上下の開き: 減る額 {step_rows[0]['saved'] - step_rows[-1]['saved']:,}円"
          f"（{step_rows[0]['at']}か月目の {step_rows[0]['saved']:,}円 と"
          f" {step_rows[-1]['at']}か月目の {step_rows[-1]['saved']:,}円）")

    print("\n=== 半年ごとに上乗せすると、何か月縮んでいくら安くなるか（残高30万円・毎月1万円） ===")
    print(f"{'半年の上乗せ':>13}{'月あたり':>10}{'月数':>7}{'総手数料':>11}{'減る額':>10}{'縮む月数':>10}")
    bonus_rows = bonus_grid()
    for row in bonus_rows:
        print(f"{row['bonus']:>12,}円{row['per_month']:>9,}円{row['months']:>6}月"
              f"{row['total_fee']:>10,}円{row['saved']:>9,}円{row['saved_months']:>9}月")
    print(f"  上下の開き: 減る額 {bonus_rows[-1]['saved'] - bonus_rows[0]['saved']:,}円"
          f"（{bonus_rows[-1]['bonus']:,}円 の {bonus_rows[-1]['saved']:,}円 と"
          f" {bonus_rows[0]['bonus']:,}円 の {bonus_rows[0]['saved']:,}円）")

    print("\n=== 借入額が10万円と100万円をまたぐと、法定上限が変わる ===")
    print(f"{'借入額':>11}{'法定上限':>10}{'毎月の支払額':>14}{'月数':>7}{'総手数料':>11}")
    for row in cap_grid():
        print(f"{row['principal']:>10,}円{row['cap']:>9.0%}"
              f"{row['pay']:>13,}円{row['months']:>6}月{row['total_fee']:>10,}円")


if __name__ == "__main__":
    main()
