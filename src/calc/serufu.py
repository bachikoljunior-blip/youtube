"""セルフメディケーション税制と医療費控除の、**選ぶ側が入れ替わる金額**を計算する。

`iryohi.py` は冒頭で「セルフメディケーション税制は入れない（選択制で条件が
別立てになり、1本の動画に2つの制度を混ぜると前提が追えなくなる）」と書いている。
**それは正しい。だから逆に、「どちらを選ぶか」だけを主題にした表をここに分けた。**
混ざって困るのは、片方の解説の途中にもう片方が挟まるときであって、
**比較そのものが主題なら、前提は2本立てで最初から並べられる。**

## 一般の解説はここで止まる

    「年間1万2000円を超えたらセルフメディケーション税制が使えます」
    「医療費控除とは選択制です。どちらか有利なほうを選びましょう」

**「どちらが有利か」を金額で言っている解説が無い。** 有利不利は3つの数で決まる:

    セルフの控除額 = min(購入費 − 12,000円, 88,000円)      ← **上限で頭打ち**
    医療費控除     = 家族の医療費合計 − min(10万円, 総所得の5%)
    戻る額         = 控除額 × (所得税率 × 1.021 + 住民税10%)

頭打ちがあるほうと、無いほうを比べるので、**必ずどこかで入れ替わる。**
その入れ替わりの金額は総所得で動く（足切りが動くから）。ここを表にする。

## この表で出る、どこにも載っていない数

1. **セルフのほうが得なのは、購入費が「足切り＋88,000円」まで。**
   総所得200万円以上なら **188,000円**、総所得160万円なら **168,000円**
2. **上限88,000円は偶然ではない。** 10万円 − 1万2000円 = 8万8000円。
   **セルフの控除額は、医療費控除の足切りを1円も超えられないように置かれている**
3. だから **OTC以外の医療費が88,000円ある人は、その時点で医療費控除のほうが得**
   （足切り10万円の人の場合。この88,000円も上の上限と同じ数字）
4. **どれだけ買っても、セルフで戻る額の天井は決まっている** ——
   所得税率20パーセントで **26,769円**

## 注意（前提の置き方そのものが独自の視点）

**セルフを使うには「一定の取組」が要る。** 健診・予防接種・がん検診などを
その年に受けていること。受けていない人は、そもそも選択肢が1つしかない。
**この条件を書かずに金額だけ比べる表は、成立していない。**
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "セルフメディケーション税制は、スイッチOTC医薬品などの購入費が"
    "年1万2000円を超えた部分を控除するものとしています",
    "セルフメディケーション税制の控除額の上限は8万8000円です",
    "セルフメディケーション税制を使うには、その年に健診や予防接種などの"
    "一定の取組を受けている必要があります。受けていない場合はこの比較は成り立ちません",
    "医療費控除の足切りは「10万円」と「総所得金額等の5パーセント」の少ないほうです",
    "医療費控除とセルフメディケーション税制は選択制で、両方は使えないものとしています",
    "同じ市販薬の購入費は、どちらの制度でも対象になり得るものとしています"
    "（治療または療養のための購入であること）",
    "所得税は復興特別所得税2.1パーセントを含めています",
    "住民税は標準税率10パーセントで計算しています",
    "所得税率は仮定です。表では5パーセント、10パーセント、20パーセント、"
    "33パーセントの4通りを並べています",
    "保険金や高額療養費で補填された額は、医療費から引いた後の数字としています",
]

# ---- 制度の値 ------------------------------------------------------------
SELF_FLOOR = 12_000          # セルフメディケーション税制の足切り（円）
SELF_CAP = 88_000            # セルフメディケーション税制の控除額の上限（円）
MEDICAL_FLOOR_CAP = 100_000  # 医療費控除の足切りの上限（円）
MEDICAL_FLOOR_RATE = 0.05    # 医療費控除の足切りの率（総所得金額等に対して）
MEDICAL_CAP = 2_000_000      # 医療費控除の上限（円）
RECONSTRUCTION = 0.021       # 復興特別所得税
RESIDENT_RATE = 0.10         # 住民税の標準税率

RATES = (0.05, 0.10, 0.20, 0.33)


def medical_floor(total_income: int) -> int:
    """医療費控除の足切り。**10万円と総所得の5パーセントの、少ないほう。**"""
    return int(min(MEDICAL_FLOOR_CAP, total_income * MEDICAL_FLOOR_RATE))


def self_deduction(purchase: int) -> int:
    """セルフメディケーション税制の控除額。**上限で頭打ちになる。**"""
    return max(0, min(purchase - SELF_FLOOR, SELF_CAP))


def medical_deduction(paid: int, total_income: int) -> int:
    """医療費控除の控除額。市販薬の購入費もここに含めて渡すこと。"""
    return max(0, min(paid - medical_floor(total_income), MEDICAL_CAP))


def coefficient(rate: float) -> float:
    """控除額1円あたり、実際に戻る額（所得税ぶん＋住民税ぶん）。"""
    return rate * (1 + RECONSTRUCTION) + RESIDENT_RATE


def refund(deduction: int, rate: float) -> int:
    """控除額から、実際に戻る額。"""
    return int(deduction * coefficient(rate))


def switch_purchase(total_income: int) -> int | None:
    """**市販薬の購入費だけで比べたとき、選ぶ側が入れ替わる金額。**

    市販薬しか医療費が無い人を考える。購入費を x とすると

        セルフ     = min(x − 12,000, 88,000)
        医療費控除 = x − 足切り

    足切りが12,000円より大きいあいだ、**セルフのほうが控除額は大きい。**
    ところがセルフは88,000円で止まるので、医療費控除がいつか追いつく。
    追いつくのは **x = 足切り + 88,000円**。戻り値はその金額（円）で、
    **これを超えたら医療費控除のほうが得**になる。

    足切りが12,000円以下（総所得24万円以下）なら、セルフが勝つ場面は無いので None。
    """
    floor = medical_floor(total_income)
    if floor <= SELF_FLOOR:
        return None
    return floor + SELF_CAP


def other_medical_break(total_income: int, purchase: int) -> int:
    """**市販薬のほかに医療費がいくらあれば、医療費控除のほうが得になるか。**

    市販薬 x 円に加えて、通院や入院の医療費が m 円あるとする。

        医療費控除 = m + x − 足切り
        セルフ     = min(x − 12,000, 88,000)

    セルフが頭打ちに当たっていない範囲（x < 10万円）では、
    **m ≧ 足切り − 12,000円** で医療費控除が勝つ。**購入費に依らない。**
    足切り10万円の人なら **88,000円** —— セルフの上限と同じ数字になる。

    購入費が10万円を超えてセルフが頭打ちなら、境目はさらに下がる。
    """
    floor = medical_floor(total_income)
    capped = purchase - SELF_FLOOR > SELF_CAP
    if capped:
        return max(0, floor + SELF_CAP - purchase)
    return max(0, floor - SELF_FLOOR)


def ceiling_refund(rate: float) -> int:
    """**セルフメディケーション税制で戻る額の天井。**買い足しても増えない。"""
    return refund(SELF_CAP, rate)


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(SELF_FLOOR, 12_000, "セルフメディケーション税制の足切り",
                      source="租税特別措置法41条の17の2")
    _checks.statutory(SELF_CAP, 88_000, "セルフメディケーション税制の控除の上限",
                      source="租税特別措置法41条の17の2")
    _checks.statutory(MEDICAL_FLOOR_CAP, 100_000, "医療費控除の足切りの上限",
                      source="所得税法73条")
    _checks.ratio(MEDICAL_FLOOR_RATE, "医療費控除の足切りの率")
    _checks.ratio(RESIDENT_RATE, "住民税の標準税率")
    _checks.digits(SELF_CAP, 10_000, 1_000_000, "セルフメディケーション税制の上限")

    # 2. **この表の主題そのもの** ——「上限88,000円は偶然ではない」
    if SELF_CAP != MEDICAL_FLOOR_CAP - SELF_FLOOR:
        raise _checks.TableError(
            "上限88,000円が「10万円 − 1万2000円」と一致していません。"
            f"{SELF_CAP} ≠ {MEDICAL_FLOOR_CAP - SELF_FLOOR}。"
            "制度が動いたなら、この表の主張そのものを書き直すこと")
    # 頭打ちに当たるまでは、セルフの控除額が医療費控除の足切りを超えない
    if self_deduction(MEDICAL_FLOOR_CAP) != MEDICAL_FLOOR_CAP - SELF_FLOOR:
        raise _checks.TableError("購入費10万円ちょうどでセルフの控除額が88,000円にならない")

    # 3. 計算の向き
    _checks.never_decreases(self_deduction, [0, 12_000, 50_000, 100_000, 200_000],
                            "購入費が増えたのにセルフの控除額が減っている")
    _checks.increases_with(lambda x: medical_deduction(x, 5_000_000),
                           [200_000, 300_000, 400_000],
                           "医療費が増えたのに医療費控除が増えていない")
    if self_deduction(SELF_FLOOR) != 0:
        raise _checks.TableError("足切りちょうどで控除が出ている")
    if self_deduction(1_000_000) != SELF_CAP:
        raise _checks.TableError("購入費100万円でも上限で止まっていない")

    # 4. 入れ替わりの金額が、境目の両側で本当に入れ替わること（式を解いた裏取り）
    for income in (5_000_000, 1_600_000, 1_000_000):
        x = switch_purchase(income)
        if x is None:
            raise _checks.TableError(f"総所得{income}円で入れ替わりが出ていない")
        if self_deduction(x) != medical_deduction(x, income):
            raise _checks.TableError(
                f"総所得{income}円・購入費{x}円で両制度の控除額が並んでいない")
        if not self_deduction(x - 10_000) > medical_deduction(x - 10_000, income):
            raise _checks.TableError(f"境目の手前でセルフが勝っていない（総所得{income}円）")
        if not medical_deduction(x + 10_000, income) > self_deduction(x + 10_000):
            raise _checks.TableError(f"境目の先で医療費控除が勝っていない（総所得{income}円）")
    # 足切りが12,000円以下なら、セルフが勝つ場面は無い
    if switch_purchase(200_000) is not None:
        raise _checks.TableError("足切りが12,000円以下なのに入れ替わりが出ている")

    # 5. 「ほかの医療費」の境目も、両側で入れ替わること
    income, purchase = 5_000_000, 50_000
    m = other_medical_break(income, purchase)
    if m != MEDICAL_FLOOR_CAP - SELF_FLOOR:
        raise _checks.TableError(f"足切り10万円の境目が88,000円になっていない: {m}")
    if not medical_deduction(purchase + m, income) >= self_deduction(purchase):
        raise _checks.TableError("境目で医療費控除がセルフに追いついていない")
    if not medical_deduction(purchase + m - 10_000, income) < self_deduction(purchase):
        raise _checks.TableError("境目の手前で医療費控除が勝ってしまっている")

    # 6. 天井は税率で増えるが、購入費では増えない
    _checks.increases_with(ceiling_refund, list(RATES), "税率が上がったのに天井が上がっていない")
    if refund(self_deduction(500_000), 0.20) != ceiling_refund(0.20):
        raise _checks.TableError("購入費を増やすと天井を超えている")

    _checks.assumption_values(ASSUMPTIONS, name="serufu")


def switch_grid() -> list[dict]:
    """総所得べつ、セルフのほうが得な購入費の上限。"""
    check_tables()
    rows = []
    for ti in (500_000, 1_000_000, 1_600_000, 2_000_000, 3_000_000, 5_000_000):
        rows.append({
            "total_income": ti,
            "floor": medical_floor(ti),
            "switch": switch_purchase(ti),
        })
    return rows


def ceiling_grid() -> list[dict]:
    """税率べつ、セルフで戻る額の天井。"""
    check_tables()
    return [{"rate": r, "deduction": SELF_CAP, "ceiling": ceiling_refund(r),
             "per_yen": round(coefficient(r), 5)} for r in RATES]


def other_grid(total_income: int) -> list[dict]:
    """購入費べつ、「ほかの医療費」がいくらで入れ替わるか。"""
    check_tables()
    rows = []
    for x in (20_000, 50_000, 88_000, 100_000, 150_000, 188_000):
        rows.append({
            "purchase": x,
            "self": self_deduction(x),
            "break": other_medical_break(total_income, x),
            "capped": x - SELF_FLOOR > SELF_CAP,
        })
    return rows


def compare_grid(total_income: int, rate: float) -> list[dict]:
    """購入費べつに、両方の制度で戻る額を並べる（市販薬しか医療費が無い人）。"""
    check_tables()
    rows = []
    for x in (12_000, 30_000, 60_000, 88_000, 100_000, 150_000, 188_000, 250_000):
        sd, md = self_deduction(x), medical_deduction(x, total_income)
        rows.append({
            "purchase": x,
            "self_refund": refund(sd, rate),
            "medical_refund": refund(md, rate),
            "diff": refund(sd, rate) - refund(md, rate),
        })
    return rows


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 上限8万8000円は偶然ではない（10万円 − 1万2000円）===")
    print(f"  医療費控除の足切りの上限   {MEDICAL_FLOOR_CAP:,}円")
    print(f"  セルフの足切り            −{SELF_FLOOR:,}円")
    print(f"  差                         {MEDICAL_FLOOR_CAP - SELF_FLOOR:,}円"
          f"  ← セルフの控除の上限 {SELF_CAP:,}円 と一致")
    print("  **セルフの控除額は、医療費控除の足切りを1円も超えられない置き方になっている。**")
    print(f"  購入費10万円ちょうどのとき セルフの控除 {self_deduction(100_000):,}円 / "
          f"医療費控除（総所得500万円）{medical_deduction(100_000, 5_000_000):,}円")

    print("\n=== 総所得べつ、セルフのほうが得な購入費の上限 ===")
    print(f"{'総所得':>11s} {'医療費控除の足切り':>12s} {'ここを超えたら医療費控除':>16s}")
    for r in switch_grid():
        s = f"{r['switch']:,}円" if r["switch"] else "セルフが勝つ場面なし"
        print(f"{r['total_income']:10,d}円 {r['floor']:11,d}円 {s:>18s}")

    print("\n=== どれだけ買っても、セルフで戻る額はここで止まる（税率べつの天井）===")
    print(f"{'所得税率':>8s} {'控除額':>9s} {'控除1円あたり':>12s} {'戻る額の天井':>11s}")
    for r in ceiling_grid():
        print(f"{r['rate']:7.0%} {r['deduction']:8,d}円 {r['per_yen']:12.5f} {r['ceiling']:10,d}円")

    TI = 5_000_000
    print(f"\n=== 市販薬のほかに医療費がいくらあると、選ぶ側が入れ替わるか（総所得{TI:,}円）===")
    print(f"{'市販薬の購入費':>12s} {'セルフの控除':>11s} {'ほかの医療費がこの額以上なら医療費控除'}")
    for r in other_grid(TI):
        print(f"{r['purchase']:11,d}円 {r['self']:10,d}円 {r['break']:20,d}円"
              + ("  ← セルフは頭打ち" if r["capped"] else ""))

    for ti, rate in ((5_000_000, 0.20), (1_600_000, 0.05)):
        print(f"\n=== 市販薬しか医療費が無い人が、購入費べつにいくら戻るか"
              f"（総所得{ti:,}円・所得税率{rate:.0%}）===")
        print(f"{'購入費':>10s} {'セルフで戻る':>11s} {'医療費控除で戻る':>13s} {'差':>10s}")
        for r in compare_grid(ti, rate):
            print(f"{r['purchase']:9,d}円 {r['self_refund']:10,d}円 "
                  f"{r['medical_refund']:12,d}円 {r['diff']:9,d}円"
                  + ("  ← 医療費控除が勝つ" if r["diff"] < 0 else ""))
