"""特定支出控除 —— **敷居は年収850万円で止まり、そこから上は1円も動きません。**

一般の解説はこう言います ——「研修費や資格取得費が、給与所得控除の2分の1を超えたら
その超えた分を引けます」。**合っています。そのうえで、
その2分の1がいくらなのかを年収べつに並べた数字は、どこにも出ていません。**

以下は給与所得控除の式（所得税法28条3項）から敷居を出し、
そこに所得税と住民税を掛けた結果です。

## 敷居は年収850万円の 975,000円 で止まります

    年収           給与所得控除      敷居（その半分）
    1,500,000円      550,000円      275,000円
    1,800,000円      620,000円      310,000円
    2,500,000円      830,000円      415,000円
    3,600,000円    1,160,000円      580,000円
    5,000,000円    1,440,000円      720,000円
    6,600,000円    1,760,000円      880,000円
    8,500,000円    1,950,000円      975,000円   ← ここで止まる
   15,000,000円    1,950,000円      975,000円

**年収1,500万円の人と年収850万円の人の敷居は、同じ 975,000円 です。**

## 敷居の増え方は、年収162万5千円で 0円 から 200,000円 へ跳ねて、4段で 0円 へ戻ります

年収を100万円増やしたときに、敷居が何円上がるかです。

    〜1,625,000円            **0円**（給与所得控除が550,000円で定額）
    1,625,000〜1,800,000円   **200,000円**  ← いちばん急
    1,800,000〜3,600,000円     150,000円
    3,600,000〜6,600,000円     100,000円
    6,600,000〜8,500,000円      50,000円
    8,500,000円〜             **0円**（頭打ち）

**両端が 0円 で、真ん中がいちばん急**です。「年収が上がるほど敷居も上がる」は、
6つの帯のうち4つでしか成り立ちません。

## 壁は下にも上にもあり、向きが逆です

敷居の下限は 275,000円（給与所得控除の最低額 550,000円 の半分）なので、
**それ以下の特定支出は、年収がいくらであっても控除額が 0円**です。
上の壁は逆向きで、敷居の上限が 975,000円 で止まるため、
**975,000円 を超える支出は、年収がいくらであっても必ず1円以上引けます。**
975,000円 ちょうどは、その境目です（年収 8,500,000円 以上で 0円 になる）。

    特定支出        引けなくなる年収
      300,000円     1,750,000円
      500,000円     3,066,667円
      650,000円     4,300,000円
      800,000円     5,800,000円
      975,000円     8,500,000円
    1,200,000円     **どの年収でも引ける**（敷居の上限を超えているため）

## 勤務必要経費は、上限いっぱいの 650,000円 を使っても年収430万円で消えます

図書費・衣服費・交際費（勤務必要経費）は合計 650,000円 が上限です。
その上限まで使い切っても、敷居が 650,000円 に達する **年収 4,300,000円** で
控除額は 0円 になります。

    年収 1,500,000円   375,000円 引ける
    年収 2,500,000円   235,000円
    年収 3,600,000円    70,000円
    年収 4,300,000円   **0円**  ← ここから上は、上限まで使っても引けない
    年収 5,000,000円     0円

## 節税額がいちばん大きいのは、いちばん年収が低い人ではありません

特定支出 1,200,000円 のときの、年収べつの結果です。

    年収           引ける額     所得税の課税所得   捨てた額     節税額
    1,500,000円   925,000円      245,000円   **680,000円**  104,750円
    1,800,000円   890,000円      430,000円     460,000円    110,500円
    2,457,143円   791,429円      791,429円          0円   **118,714円**  ← 最大
    3,600,000円   620,000円    1,420,000円          0円     93,000円
    8,500,000円   225,000円    4,795,000円          0円     67,500円
   15,000,000円   225,000円   10,320,000円          0円     96,750円

**引ける額が最大なのは年収がいちばん低いときですが、そこでは 680,000円 が
捨てられています** —— 引ける額が課税所得より大きいと、所得税では使い切れません。
山は**引ける額を所得税でちょうど使い切る年収 2,457,143円** にあり、
そこを1円でも下回ると捨てが出て、上回ると引ける額そのものが減ります。

**右端でもう一度上がっているのは税率のほう**です（年収1,500万円で33パーセントの帯）。
節税額は年収に対して単調ではありません。

## 敷居の重さが増える帯は、6つのうち1つだけです

敷居が年収に占める割合です。

    1,500,000円   18.333%
    1,625,000円   16.923%  ← いちばん軽い
    1,800,000円   **17.222%**  ← **増えている**
    3,600,000円   16.111%
    8,500,000円   11.471%
   15,000,000円    6.500%

**年収162万5千円から180万円のあいだだけ、年収が増えると敷居が重くなります。**
給与所得控除がこの帯で「収入×40パーセント−100,000円」となり、
**割合の式が 0.2 − 50,000 ÷ 年収 という増加関数に変わる**ためです。
ほかの5つの帯では、割合は下がり続けます。

---

**前提と計算式は ASSUMPTIONS に全部あります。**
社会保険料は年収の15パーセント、所得控除は基礎控除と社会保険料控除だけ、
住民税は10パーセントの標準税率です。復興特別所得税は入れていません。
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値 -----------------------------------------------------------
# 給与所得控除（所得税法28条3項。2020年分から動いていない）
# (収入金額の上限, 率, 加算額)。最上段の上限は None。
KYUYO_TABLE: list[tuple[int | None, float, int]] = [
    (1_625_000, 0.00, 550_000),
    (1_800_000, 0.40, -100_000),
    (3_600_000, 0.30, 80_000),
    (6_600_000, 0.20, 440_000),
    (8_500_000, 0.10, 1_100_000),
    (None, 0.00, 1_950_000),
]
KYUYO_MIN = 550_000          # 給与所得控除の最低額
KYUYO_MAX = 1_950_000        # 給与所得控除の上限（年収8,500,000円超で一定）
KYUYO_CAP_INCOME = 8_500_000  # 上限に達する年収

# 特定支出控除（所得税法57条の2）。
# 特定支出の合計額のうち、**その年の給与所得控除額の2分の1**を超える部分だけが、
# 給与所得控除後の所得金額からさらに引ける。
HALF = 0.5

# 特定支出のうち「勤務必要経費」（図書費・衣服費・交際費）の上限。
KINMU_HITSUYO_CAP = 650_000

# 所得税の速算表（所得税法89条）。(課税所得の上限, 税率, 控除額)
TAX_TABLE: list[tuple[int | None, float, int]] = [
    (1_950_000, 0.05, 0),
    (3_300_000, 0.10, 97_500),
    (6_950_000, 0.20, 427_500),
    (9_000_000, 0.23, 636_000),
    (18_000_000, 0.33, 1_536_000),
    (40_000_000, 0.40, 2_796_000),
    (None, 0.45, 4_796_000),
]

# 住民税の所得割（標準税率）と、この計算で置いた控除。
JUMINZEI_RATE = 0.10
KISO_KOJO_SHOTOKU = 480_000   # 所得税の基礎控除（合計所得2,400万円以下）
KISO_KOJO_JUMIN = 430_000     # 住民税の基礎控除
SHAHO_RATE = 0.15             # 社会保険料の仮定（年収に対する割合）

ASSUMPTIONS = [
    "給与所得者の特定支出控除を計算しています。所得税法57条の2で、"
    "特定支出の合計額のうち、その年の給与所得控除額の2分の1を超えた部分だけを、"
    "給与所得控除を引いたあとの所得からさらに引ける仕組みです",
    "この2分の1の額を、以下では敷居と呼びます。制度の呼び名ではありません",
    "給与所得控除は所得税法28条3項の式をそのまま使っています。"
    "最低額は550,000円、年収8,500,000円を超えると1,950,000円で頭打ちです。"
    "収入金額を4,000円単位に切り下げる実務の丸めはしていません",
    "特定支出に入るのは、通勤費、転居費、研修費、資格取得費、単身赴任者の帰宅旅費、"
    "そして勤務必要経費（図書費・衣服費・交際費）です。"
    "勤務必要経費だけは合計650,000円が上限です",
    "特定支出はどれも給与の支払者が証明したものとしています。"
    "証明が取れない支出は、金額がいくらでも対象になりません",
    "社会保険料は年収の15パーセントとして置いています。これは制度の値ではなく"
    "この計算での仮定です。年収や加入する制度で実際には13から16パーセントの幅があります",
    "所得控除は社会保険料控除と基礎控除だけを入れています。"
    "基礎控除は所得税480,000円、住民税430,000円です。"
    "扶養控除・生命保険料控除などは入れていません",
    "住民税の所得割は10パーセントの標準税率としています。均等割は入れていません",
    "復興特別所得税（所得税額の2.1パーセント）は入れていません。"
    "入れると節税額が同じ向きに約2パーセント増えます",
    "節税額は、特定支出控除を引く前と後で所得税額の差を取り、"
    "そこに控除額の10パーセント（住民税）を足したものです。"
    "帯をまたぐ場合も、またいだとおりに計算しています",
]


# ---- 計算 ---------------------------------------------------------------

def kyuyo_kojo(income: float) -> float:
    """給与所得控除。**この表の主役は、これを2で割った額のほう。**"""
    for cap, rate, add in KYUYO_TABLE:
        if cap is None or income <= cap:
            return income * rate + add
    raise ValueError(f"給与所得控除の表に当たらない: {income}")


def shikii(income: float) -> float:
    """敷居 ＝ 給与所得控除の2分の1。**ここを超えた分だけが引ける。**"""
    return kyuyo_kojo(income) * HALF


def tax_of(base: float) -> float:
    """所得税の速算表を引く。"""
    base = max(0.0, base)
    for cap, rate, sub in TAX_TABLE:
        if cap is None or base <= cap:
            return base * rate - sub
    raise ValueError(f"速算表に当たらない: {base}")


def tax_rate_of(base: float) -> float:
    """その課税所得に当たっている所得税の税率。"""
    base = max(0.0, base)
    for cap, rate, _sub in TAX_TABLE:
        if cap is None or base <= cap:
            return rate
    raise ValueError(f"速算表に当たらない: {base}")


def deductible(income: float, spend: float) -> float:
    """特定支出 spend のうち、実際に引ける額。"""
    return max(0.0, spend - shikii(income))


def vanish_income(spend: float) -> float | None:
    """その支出額が1円も引けなくなる年収（敷居が支出に追いつく点）。

    `None` は「年収がいくらでも引ける」（＝敷居の上限を超える支出）。
    敷居の下限 275,000円 以下の支出は、どの年収でも引けないので 0 を返す。
    """
    if spend <= KYUYO_MIN * HALF:
        return 0.0
    if spend > KYUYO_MAX * HALF:
        return None
    lo, hi = 0.0, float(KYUYO_CAP_INCOME)
    for cap, rate, add in KYUYO_TABLE:
        if cap is None:
            break
        top = shikii(cap)
        if spend <= top:
            # income * rate * HALF + add * HALF = spend
            slope = rate * HALF
            if slope == 0:
                return float(cap)
            return (spend - add * HALF) / slope
        lo = cap
    return hi


def taxable_income(income: float, extra_deduction: float = 0.0) -> float:
    """所得税の課税所得。**仮定は ASSUMPTIONS に全部書いてある。**"""
    kyuyo_shotoku = income - kyuyo_kojo(income) - extra_deduction
    kyuyo_shotoku = max(0.0, kyuyo_shotoku)
    return max(0.0, kyuyo_shotoku - income * SHAHO_RATE - KISO_KOJO_SHOTOKU)


def saving(income: float, spend: float) -> float:
    """特定支出控除で減る税額（所得税＋住民税）。"""
    d = deductible(income, spend)
    if d <= 0:
        return 0.0
    before = tax_of(taxable_income(income))
    after = tax_of(taxable_income(income, d))
    return (before - after) + d * JUMINZEI_RATE


# ---- 表（図解がそのまま食える dict のリスト）-----------------------------

INCOMES = [1_500_000, 1_625_000, 1_800_000, 2_500_000, 3_600_000,
           5_000_000, 6_600_000, 8_500_000, 10_000_000, 15_000_000]


def shikii_grid() -> list[dict]:
    """年収べつの敷居。**折れ点と、頭打ちの位置を出す。**"""
    return [{"年収": i,
             "給与所得控除": round(kyuyo_kojo(i)),
             "敷居": round(shikii(i)),
             "敷居の対年収比": round(shikii(i) / i, 6)}
            for i in INCOMES]


def slope_grid() -> list[dict]:
    """年収を1円増やしたとき、敷居が何円上がるか。**帯ごとに段で落ちる。**"""
    out = []
    for cap, rate, _add in KYUYO_TABLE:
        top = cap if cap is not None else None
        out.append({"帯の上限": top,
                    "1円あたりの敷居の増え方": round(rate * HALF, 4),
                    "年収100万円あたりの敷居の増え方": round(rate * HALF * 1_000_000)})
    return out


SPENDS = [250_000, 275_000, 300_000, 500_000, KINMU_HITSUYO_CAP,
          800_000, 975_000, 1_200_000]


def vanish_grid() -> list[dict]:
    """支出額べつの「引けなくなる年収」。**上下どちらにも壁がある。**"""
    out = []
    for s in SPENDS:
        v = vanish_income(s)
        out.append({"特定支出": s,
                    "引けなくなる年収": None if v is None else round(v),
                    "どの年収でも引けるか": v is None})
    return out


def spend_grid(spend: float) -> list[dict]:
    """同じ支出額が、年収でいくらの控除・いくらの節税になるか。"""
    return [{"年収": i,
             "特定支出": round(spend),
             "敷居": round(shikii(i)),
             "引ける額": round(deductible(i, spend)),
             "所得税の税率": tax_rate_of(taxable_income(i)),
             "節税額": round(saving(i, spend))}
            for i in INCOMES]


def wasted(income: float, spend: float) -> float:
    """引けるのに、課税所得が足りなくて所得税では使えなかった額。

    **住民税のぶん（10パーセント）は、この額にも効きます。**
    捨てているのは所得税の側だけです。
    """
    d = deductible(income, spend)
    return max(0.0, d - taxable_income(income))


def full_use_income(spend: float, *, lo: float = 300_000,
                    hi: float = 30_000_000) -> float:
    """引ける額を所得税でちょうど使い切る年収。**節税額はここで最大になる。**

    `taxable_income` は年収とともに増え、`deductible` は減るので、
    差は単調増加。**二分法で1円まで詰めれば、刻みに依存しません**
    （`_template.py` の「刻みは境目の幅より細かく」を、刻みごと消す形）。
    """
    def f(x: float) -> float:
        return taxable_income(x) - deductible(x, spend)

    if f(lo) >= 0:
        return lo
    if f(hi) <= 0:
        return hi
    while hi - lo > 1:
        mid = (lo + hi) / 2
        if f(mid) < 0:
            lo = mid
        else:
            hi = mid
    return round(hi)


def saving_peak(spend: float) -> dict:
    """節税額が最大になる年収と、そのときの額。**二分法なので刻みは無い。**"""
    x = full_use_income(spend)
    return {"特定支出": spend, "節税額が最大の年収": round(x),
            "そのときの節税額": round(saving(x, spend)),
            "引ける額": round(deductible(x, spend)),
            "捨てた額": round(wasted(x, spend))}


def waste_grid(spend: float) -> list[dict]:
    """年収べつに「引ける額・使えた額・捨てた額・節税額」を並べる。"""
    return [{"年収": i,
             "特定支出": round(spend),
             "引ける額": round(deductible(i, spend)),
             "所得税の課税所得": round(taxable_income(i)),
             "捨てた額": round(wasted(i, spend)),
             "節税額": round(saving(i, spend))}
            for i in INCOMES]


def kinmu_grid() -> list[dict]:
    """勤務必要経費の上限650,000円だけを使ったとき、年収べつに何円引けるか。"""
    return [{"年収": i,
             "敷居": round(shikii(i)),
             "上限いっぱい使っても引ける額": round(deductible(i, KINMU_HITSUYO_CAP))}
            for i in INCOMES]


def ratio_grid() -> list[dict]:
    """敷居の対年収比。**額は上がるのに、割合は下がり続ける。**"""
    return [{"年収": i,
             "敷居": round(shikii(i)),
             "年収に対する割合": round(shikii(i) / i * 100, 3)}
            for i in INCOMES]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""
    # 1. 法令が名指ししている値
    _checks.statutory(KYUYO_MIN, 550_000, "給与所得控除の最低額",
                      source="所得税法28条3項")
    _checks.statutory(KYUYO_MAX, 1_950_000, "給与所得控除の上限",
                      source="所得税法28条3項")
    _checks.statutory(HALF, 0.5, "特定支出控除の敷居の割合",
                      source="所得税法57条の2第1項")
    _checks.statutory(KINMU_HITSUYO_CAP, 650_000, "勤務必要経費の上限",
                      source="所得税法57条の2第2項6号")
    _checks.ratio(SHAHO_RATE, "社会保険料の仮定の率")
    _checks.ratio(JUMINZEI_RATE, "住民税の所得割の税率")
    _checks.bracket_table(TAX_TABLE, tax_of, name="所得税の速算表")

    # 2. 給与所得控除が帯の境目で切れていないこと（敷居の連続はここから来る）
    for cap, _rate, _add in KYUYO_TABLE:
        if cap is None:
            continue
        _checks.close(kyuyo_kojo(cap), kyuyo_kojo(cap + 1) - _step_at(cap),
                      f"給与所得控除が年収{cap:,}円の境目で切れている", tol=1.0)

    # 3. この計算の主題そのもの
    _checks.never_decreases(shikii, [1_000_000, 3_000_000, 6_000_000,
                                     8_500_000, 12_000_000],
                            "年収が増えたのに敷居が下がっている")
    _checks.statutory(shikii(KYUYO_CAP_INCOME), 975_000,
                      "年収8,500,000円の敷居", source="給与所得控除1,950,000円の半分")
    _checks.statutory(shikii(20_000_000), 975_000,
                      "年収20,000,000円の敷居", source="上限で頭打ちのはず")
    _checks.statutory(shikii(1_000_000), 275_000,
                      "敷居の下限", source="給与所得控除の最低額550,000円の半分")
    # 敷居の下限以下の支出は、どの年収でも1円も引けない
    _checks.statutory(deductible(1_000_000, 275_000), 0,
                      "敷居ちょうどの支出で引ける額")
    _checks.statutory(deductible(20_000_000, 975_000), 0,
                      "年収20,000,000円で、敷居の上限ちょうどの支出が引ける額")
    _checks.greater(deductible(5_000_000, 975_000), 0,
                    "年収5,000,000円なら975,000円の支出も引けるはず")
    _checks.greater(deductible(1_000_000, 300_000), deductible(5_000_000, 300_000),
                    "同じ300,000円の支出で、年収1,000,000円のほうが引ける額が多いはず")
    # 敷居の増え方は帯ごとに落ちる（同値を許さない段が5つ）
    slopes = [r["1円あたりの敷居の増え方"] for r in slope_grid()][1:]
    _checks.ascending(list(reversed(slopes)), "敷居の増え方が帯ごとに落ちていない")
    # 節税額の山は、細かく走査しても二分法の答えを超えないこと
    # （**走査で決めていない**ので、刻みの話にならない）
    for spend in (500_000, 1_200_000):
        top = saving(full_use_income(spend), spend)
        for x in range(400_000, 15_000_001, 10_000):
            if saving(x, spend) > top + 1:
                raise _checks.TableError(
                    f"特定支出{spend:,}円で、年収{x:,}円のほうが節税額が大きい"
                    f"（{saving(x, spend):,.0f} > {top:,.0f}）。山の求め方が違う")
        # 山の左では捨てている、右では捨てていない
        peak = full_use_income(spend)
        _checks.greater(wasted(peak - 100_000, spend), 0,
                        f"特定支出{spend:,}円の山の手前で捨てた額が0")
        _checks.statutory(wasted(peak + 100_000, spend), 0,
                          f"特定支出{spend:,}円の山の先で捨てた額")
    _checks.unique_by(shikii_grid(), lambda r: r["年収"], "年収べつの敷居")


def _step_at(cap: int) -> float:
    """境目の1円ぶんの増え方（連続かどうかを見るためだけの補助）。"""
    for c, rate, _add in KYUYO_TABLE:
        if c is None or cap < c:
            return rate * HALF * 2
    return 0.0


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 敷居は年収850万円の975,000円で止まり、そこから上は1円も動かない ===")
    for row in shikii_grid():
        print(row)

    print("\n=== 敷居の増え方は、年収162万5千円までは0円。そこで20万円へ跳ね、4段で0へ戻る ===")
    for row in slope_grid():
        print(row)

    print("\n=== 壁は下にも上にもあり向きが逆。27万5千円以下は必ず0円、97万5千円超は必ず引ける ===")
    for row in vanish_grid():
        print(row)

    print("\n=== 同じ120万円の資格費用の節税額は、年収245万7千円でいちばん大きい ===")
    for row in spend_grid(1_200_000):
        print(row)
    print("節税額の山:", saving_peak(1_200_000))
    print("節税額の山（50万円の支出）:", saving_peak(500_000))

    print("\n=== 引ける額が最大なのは年収がいちばん低いときで、そこでは68万円が捨てられている ===")
    for row in waste_grid(1_200_000):
        print(row)

    print("\n=== 勤務必要経費は上限いっぱいの65万円を使っても、年収430万円で消える ===")
    for row in kinmu_grid():
        print(row)
    print("650,000円が消える年収:", vanish_income(KINMU_HITSUYO_CAP))

    print("\n=== 敷居の重さが増える帯は1つだけ。年収162万5千円から180万円のあいだ ===")
    for row in ratio_grid():
        print(row)
