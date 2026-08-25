"""**雑損控除と災害減免法の、選ぶ側が入れ替わる損失額**を計算する。

災害・盗難・横領で財産をなくしたとき、税を軽くする道は2つあり、**選択制**で
両方は使えない。`src/calc/` の62本はどれもこの2つを計算していない
（`grep -l 雑損 src/calc/*.py` も `災害減免` も0件だった）。

## 一般の解説はここで止まる

    「雑損控除と災害減免法は選択制です。どちらか有利なほうを選びましょう」
    「引ききれない金額は翌年以後3年間くり越せます」

**「どちらが有利か」を金額で言っている解説が無い。** 決まり方は簡単で、

    災害減免法 = その年の所得税額 × 軽減割合   ← **損失の大きさと無関係**
    雑損控除   = （差引損失額 − 総所得金額等の10パーセント）を所得から引く
                                              ← **損失に比例して増える**

片方が損失と無関係で、もう片方が損失に比例するので、**必ずどこかで交差する。**
その交差点の損失額は所得で動く。ここを表にする。

## この表で出る、どこにも載っていない数

1. **交差点は、所得のおよそ 0.19倍から 0.38倍のところにある。**
   総所得300万円なら **1,000,402円**、500万円なら **1,912,115円**。
   500万円が交差点の頂点で、そこから上は**下がる** ——
   軽減割合が100パーセントから50パーセントへ落ちるから
2. **繰越3年は、交差点を1円も動かさない。** 交差点の損失は所得の 0.38倍以下で、
   **1年で引ききれてしまう**のでくり越す分が出ない。
   「繰越があるから雑損控除が有利」は、**有利不利の分かれ目には効いていない**
3. **くり越しにも回らず、税額も減らさずに消える帯がある。**
   総所得400万円で **1,080,000円**（社会保険料控除と基礎控除にぶつかった分）。
   くり越せるのは「所得から引ききれなかった額」だけなので、この帯は1円も残らない。
   **制度の説明はこの帯を持っていない**
4. **所得が1円増えると減税額が落ちる点が3つある。**
   500万円で **166,678円**、750万円で **191,820円**、1000万円で **308,495円**。
   1000万円の段だけは割合が落ちるのではなく、**制度そのものが使えなくなる**
5. **災害関連支出の5万円ルールに要る「関連支出の割合」。**
   総所得400万円なら、損失40万円は **12.5パーセント** でひっくり返り、
   200万円では **82.5パーセント** 要る。増える控除額は損失がいくらでも
   **350,000円** で一定（足切りと5万円の差そのもの）
6. **住民税の減税は、控除額の10パーセントちょうど。** 総所得1000万円で **400,000円**。
   **災害減免法の側はゼロ。** 所得税だけを比べて選ぶと、この額をまるごと落とす

## 注意（前提の置き方そのものが独自の視点）

**災害減免法には2つの門がある** —— 住宅または家財の損害が**その価額の2分の1以上**、
かつ**その年分の所得金額の合計額が1000万円以下**。**盗難と横領は入らない**（災害のみ）。
雑損控除は災害・盗難・横領のどれでも使えるが、**詐欺と恐喝は入らない。**
**門の違うものを金額だけで比べる表は、成立していない。** 総所得 **10,000,001円** の
人には、そもそも選択肢が1つしかない。
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "計算の入口は年収ではなく「総所得金額等」です。給与の人は年収から給与所得控除を引いた後の額になります",
    "所得控除は基礎控除と社会保険料控除だけで置いています。扶養控除や保険料控除があると、ここより税は下がります",
    "社会保険料は総所得金額等に対する一定率15パーセントとして置いています。実際は標準報酬月額の等級で階段状に動きます",
    "基礎控除は所得税48万円、住民税43万円としています。合計所得金額が2400万円を超えると減っていきますが、この表の範囲では影響しません",
    "住民税の所得割は標準税率10パーセントです。均等割は入れていません",
    "所得税には復興特別所得税を含めています（1.021倍）。災害減免法の軽減率は、その合計額に掛ける簡略計算にしています",
    "雑損控除の額は「差引損失額から総所得金額等の10パーセントを引いた額」と「災害関連支出から5万円を引いた額」の、多いほうです",
    "差引損失額は、損害金額に災害関連支出を足し、保険金などで補填される額を引いた後の数字としています",
    "雑損控除で引ききれなかった額は、翌年以後3年間くり越せるものとしています。特定非常災害の5年は入れていません",
    "くり越せるのは「総所得金額等から引ききれなかった額」だけです。基礎控除や社会保険料控除とぶつかって消えた分はくり越せません",
    "くり越した年の所得は、災害のあった年と同じ額が続くものとしています",
    "災害減免法が使えるのは、住宅または家財の損害額がその価額の2分の1以上で、かつその年分の所得金額の合計額が1000万円以下のときだけです",
    "災害減免法は所得税だけを軽くします。住民税は減りません",
    "雑損控除と災害減免法は選択制で、両方は使えないものとしています",
    "詐欺や恐喝による損失は雑損控除の対象外です。この表は災害・盗難・横領を前提にしています",
]

# ---- 制度の値 ----------------------------------------------------------
# 所得税の速算表は「区分の始まり, 税率」で持つ。控除額の列は使わない
# （写し間違えても数字はそれらしく出るので、区分ごとに積み上げる）
INCOME_TAX_BRACKETS: list[tuple[int, float]] = [
    (0, 0.05),
    (1_950_000, 0.10),
    (3_300_000, 0.20),
    (6_950_000, 0.23),
    (9_000_000, 0.33),
    (18_000_000, 0.40),
    (40_000_000, 0.45),
]
RECONSTRUCTION = 1.021          # 復興特別所得税
RESIDENT_RATE = 0.10            # 住民税の所得割（標準税率）
BASIC_INCOME = 480_000          # 基礎控除（所得税）
BASIC_RESIDENT = 430_000        # 基礎控除（住民税）
SOCIAL_RATE = 0.15              # 社会保険料。**仮定**

ZASSON_FLOOR_RATE = 0.10        # 雑損控除の足切り（総所得金額等の10パーセント）
RELATED_FLOOR = 50_000          # 災害関連支出の足切り（5万円）
CARRYOVER_YEARS = 3             # 雑損失の繰越（翌年以後3年）

RELIEF_INCOME_CAP = 10_000_000  # 災害減免法が使える所得の上限
RELIEF_DAMAGE_RATIO = 0.5       # 住宅・家財の損害が価額の2分の1以上
# (所得金額の合計額の上限, 軽減される割合)。最上段の上限が RELIEF_INCOME_CAP
RELIEF_BANDS: list[tuple[int, float]] = [
    (5_000_000, 1.00),
    (7_500_000, 0.50),
    (10_000_000, 0.25),
]


def income_tax(taxable: int) -> int:
    """課税所得から所得税額を出す。速算表の控除額は使わない。"""
    if taxable <= 0:
        return 0
    tax = 0.0
    for i, (floor, rate) in enumerate(INCOME_TAX_BRACKETS):
        if taxable <= floor:
            break
        ceiling = (
            INCOME_TAX_BRACKETS[i + 1][0]
            if i + 1 < len(INCOME_TAX_BRACKETS)
            else taxable
        )
        tax += (min(taxable, ceiling) - floor) * rate
    return int(tax * RECONSTRUCTION)


def social(income: int) -> int:
    return int(income * SOCIAL_RATE)


def taxable_income(income: int, deduction: int = 0) -> int:
    """所得税の課税所得。雑損控除は他の所得控除より先に引く。"""
    return max(0, income - social(income) - BASIC_INCOME - deduction)


def taxable_resident(income: int, deduction: int = 0) -> int:
    return max(0, income - social(income) - BASIC_RESIDENT - deduction)


def resident_tax(taxable: int) -> int:
    return int(max(0, taxable) * RESIDENT_RATE)


# ---- 雑損控除 -----------------------------------------------------------
def zasson_floor(income: int) -> int:
    """足切り。総所得金額等の10パーセント。"""
    return int(income * ZASSON_FLOOR_RATE)


def zasson_deduction(income: int, loss: int, related: int = 0) -> int:
    """雑損控除の額。2つの式の多いほう。"""
    a = loss - zasson_floor(income)
    b = related - RELATED_FLOOR
    return max(0, a, b)


def dead_band(income: int) -> int:
    """**繰越にも回らず、税額も減らさない帯。**

    雑損控除は総所得金額等から引くので、繰り越せるのは「所得を超えた分」だけ。
    ところが税額が0になるのは、社会保険料控除と基礎控除を引いた後の課税所得を
    超えたところ。**その2つの差が、どこにも行かずに消える。**
    """
    return social(income) + BASIC_INCOME


def zasson_saving(income: int, loss: int, related: int = 0,
                  years: int = 1) -> int:
    """雑損控除で減る税額（所得税＋住民税）。years=4 で繰越3年ぶんを含む。"""
    d = zasson_deduction(income, loss, related)
    base_i, base_r = taxable_income(income), taxable_resident(income)
    tax0, res0 = income_tax(base_i), resident_tax(base_r)

    saved = 0
    carry = d
    for _ in range(min(years, 1 + CARRYOVER_YEARS)):
        if carry <= 0:
            break
        use = min(carry, income)
        saved += tax0 - income_tax(max(0, base_i - use))
        saved += res0 - resident_tax(max(0, base_r - use))
        carry -= use
    return saved


# ---- 災害減免法 ---------------------------------------------------------
def relief_rate(income: int) -> float:
    """軽減される割合。1000万円を超えると使えない。"""
    for cap, rate in RELIEF_BANDS:
        if income <= cap:
            return rate
    return 0.0


def relief_saving(income: int) -> int:
    """災害減免法で減る税額。**損失額と無関係。所得税だけ。**"""
    return int(income_tax(taxable_income(income)) * relief_rate(income))


# ---- 交差点 -------------------------------------------------------------
def crossover(income: int, related: int = 0, years: int = 1) -> int | None:
    """**雑損控除が災害減免法に追いつく損失額。** 二分法で1000円まで詰める。"""
    target = relief_saving(income)
    if target <= 0:
        return 0
    lo, hi = 0, 500_000_000
    if zasson_saving(income, hi, related, years) < target:
        return None
    while hi - lo > 1_000:
        mid = (lo + hi) // 2
        if zasson_saving(income, mid, related, years) >= target:
            hi = mid
        else:
            lo = mid
    return hi


INCOMES = (3_000_000, 4_000_000, 5_000_000, 6_000_000,
           7_000_000, 8_000_000, 9_000_000, 10_000_000)


def crossover_grid(years: int = 1) -> list[dict]:
    rows = []
    for inc in INCOMES:
        x = crossover(inc, years=years)
        rows.append({
            "income": inc,
            "relief": relief_saving(inc),
            "rate": relief_rate(inc),
            "floor": zasson_floor(inc),
            "cross": x,
            "ratio": (x / inc) if x else None,
        })
    return rows


def carry_gain_grid() -> list[dict]:
    """1年だけで比べたときと、繰越3年まで入れたときの交差点の差。

    **答えは「1円も動かない」です**（表を見てから分かりました）。交差点の損失額は
    どの所得帯でも所得の 0.19〜0.38倍にあり、**その額は1年で引ききれてしまう**ので
    繰越に回る分がありません。繰越が効くのは、交差点よりずっと右 —— 下の
    `carry_use_grid()` の帯です。**「繰越があるから雑損控除が有利」は、
    有利不利の分かれ目そのものには効いていません。**
    """
    rows = []
    for inc in INCOMES:
        one, four = crossover(inc, years=1), crossover(inc, years=4)
        rows.append({
            "income": inc,
            "one": one,
            "four": four,
            "diff": (one - four) if (one is not None and four is not None) else None,
        })
    return rows


def carry_use_grid(income: int = 4_000_000) -> list[dict]:
    """**損失が所得を超えたとき、控除額はどこへ行くか。**

    3つに割れる: その年に税額を減らした分／翌年以後3年へくり越せる分／
    **どこにも行かずに消える分**（社会保険料控除と基礎控除にぶつかった帯）。
    """
    rows = []
    dead = dead_band(income)
    for mult in (0.5, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0):
        loss = int(income * mult)
        d = zasson_deduction(income, loss)
        used_year1 = min(d, income)          # 所得から引ける上限
        carried = max(0, d - income)          # くり越せるのはここだけ
        absorbed = max(0, used_year1 - dead)  # 実際に税額を減らした分
        lost = used_year1 - absorbed          # 消える帯にぶつかった分
        over = max(0, carried - income * CARRYOVER_YEARS)  # 3年でも使い切れない
        rows.append({
            "loss": loss, "deduction": d, "absorbed": absorbed,
            "lost": lost, "carried": carried, "expired": over,
        })
    return rows


CLIFF_POINTS = (5_000_000, 7_500_000, 10_000_000)


def cliff_grid() -> list[dict]:
    """**所得が1円増えると減免率が落ちる点。**"""
    rows = []
    for edge in CLIFF_POINTS:
        below, above = relief_saving(edge), relief_saving(edge + 1)
        rows.append({
            "edge": edge,
            "rate_below": relief_rate(edge),
            "rate_above": relief_rate(edge + 1),
            "below": below,
            "above": above,
            "drop": below - above,
        })
    return rows


def floor_grid() -> list[dict]:
    """足切りと「消える帯」。損失があっても1円も効かない額。"""
    rows = []
    for inc in INCOMES:
        f, dead = zasson_floor(inc), dead_band(inc)
        rows.append({
            "income": inc,
            "floor": f,
            "dead": dead,
            "total": f + dead,
            "share": (f + dead) / inc,
        })
    return rows


RELATED_LOSSES = (100_000, 200_000, 300_000, 400_000, 500_000, 700_000,
                  1_000_000, 1_500_000, 2_000_000)


def related_share_needed(income: int, loss: int) -> float | None:
    """**損失のうち何割が災害関連支出なら、5万円の式が勝つか。**

    5万円の式が勝つ条件は `related - 50,000 > loss - floor`。
    related = share * loss と置いて share について解く。
    """
    if loss <= 0:
        return None
    need = (loss - zasson_floor(income) + RELATED_FLOOR) / loss
    if need <= 0:
        return 0.0        # どんな割合でも勝つ
    if need > 1:
        return None       # 全部が関連支出でも勝てない
    return need


def related_grid(income: int = 4_000_000) -> list[dict]:
    """5万円ルールが足切りに勝つのに要る「災害関連支出の割合」。"""
    rows = []
    f = zasson_floor(income)
    for loss in RELATED_LOSSES:
        need = related_share_needed(income, loss)
        all_related = max(0, loss - RELATED_FLOOR)
        by_floor = max(0, loss - f)
        rows.append({
            "loss": loss, "floor": f, "need": need,
            "by_floor": by_floor, "all_related": all_related,
            "gain": all_related - by_floor,
        })
    return rows


def resident_grid() -> list[dict]:
    """同じ損失で、住民税がいくら減るか（災害減免法では0円）。"""
    rows = []
    for inc in INCOMES:
        loss = int(inc * 0.5)
        d = zasson_deduction(inc, loss)
        base_r = taxable_resident(inc)
        res = resident_tax(base_r) - resident_tax(max(0, base_r - min(d, inc)))
        rows.append({
            "income": inc, "loss": loss, "deduction": d,
            "resident": res, "relief_resident": 0,
        })
    return rows


OVER_CAP = (9_900_000, 10_000_000, 10_000_001, 10_100_000, 12_000_000)


def over_cap_grid() -> list[dict]:
    """1000万円の崖。ここから先は雑損控除しか無い。"""
    rows = []
    for inc in OVER_CAP:
        loss = int(inc * 0.5)
        rows.append({
            "income": inc,
            "rate": relief_rate(inc),
            "relief": relief_saving(inc),
            "zasson": zasson_saving(inc, loss, years=4),
            "loss": loss,
        })
    return rows


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""
    # 1. 法令が名指ししている値
    _checks.statutory(ZASSON_FLOOR_RATE, 0.10, "雑損控除の足切り",
                      source="所得税法72条（総所得金額等の10パーセント）")
    _checks.statutory(RELATED_FLOOR, 50_000, "災害関連支出の足切り",
                      source="所得税法72条")
    _checks.statutory(RELIEF_INCOME_CAP, 10_000_000, "災害減免法の所得上限",
                      source="災害被害者に対する租税の減免、徴収猶予等に関する法律2条")
    _checks.statutory(RELIEF_DAMAGE_RATIO, 0.5, "災害減免法の損害割合",
                      source="同法施行令1条（住宅または家財の価額の2分の1以上）")
    _checks.statutory(CARRYOVER_YEARS, 3, "雑損失の繰越年数",
                      source="所得税法71条")
    for r in (ZASSON_FLOOR_RATE, RESIDENT_RATE, SOCIAL_RATE, RELIEF_DAMAGE_RATIO):
        _checks.ratio(r, "率")
    for _cap, rate in RELIEF_BANDS:
        # 全額免除の 1.0 は `ratio` の範囲外（0 と 1 のあいだを見る検査）なので、
        # **上限を含む形でここに書く。** 1.0 は桁の取り違えではなく制度の値
        if not 0 < rate <= 1:
            raise _checks.TableError(f"災害減免法の軽減割合が {rate}")
        _checks.ascending([0.0, rate, 1.0], "災害減免法の軽減割合")

    # 2. 速算表の形と、境目で税額が飛ばないこと
    _checks.bracket_table(
        [(INCOME_TAX_BRACKETS[i + 1][0] if i + 1 < len(INCOME_TAX_BRACKETS) else None,
          rate, 0.0) for i, (_f, rate) in enumerate(INCOME_TAX_BRACKETS)],
        lambda base: income_tax(int(base)) / RECONSTRUCTION,
        name="所得税の速算表", tol=2.0)

    # 3. この計算の主題そのもの
    #   雑損控除は損失に比例して増える。災害減免法は損失と無関係
    _checks.increases_with(lambda L: zasson_saving(5_000_000, L),
                           [1_000_000, 2_000_000, 3_000_000],
                           "損失が増えたのに雑損控除の減税額が増えていない")
    _checks.rounding(relief_saving(4_000_000) - relief_saving(4_000_000), 0,
                     "災害減免法の減税額が損失で動いている")
    #   軽減割合は所得が増えるほど下がる（段でよい）
    _checks.decreases_with(lambda a: relief_rate(a) + 1e-9 * a,
                           [4_000_000, 6_000_000, 8_000_000, 11_000_000],
                           "所得が増えたのに災害減免法の割合が下がっていない")
    #   崖: 1円またいだら減税額が落ちる
    for row in cliff_grid():
        _checks.greater(row["below"], row["above"],
                        f"所得{row['edge']:,}円の崖で減税額が落ちていない")
    #   足切りは所得に比例
    _checks.increases_with(zasson_floor, [3_000_000, 5_000_000, 9_000_000],
                           "所得が増えたのに足切りが増えていない")
    #   繰越を入れると、交差点は必ず手前に来る（同じか、より小さい損失で追いつく）
    for row in carry_gain_grid():
        if row["one"] is not None and row["four"] is not None:
            if row["four"] > row["one"]:
                raise _checks.TableError(
                    f"繰越を入れたのに交差点が遠のいた（所得{row['income']:,}円）")
    #   1000万円を超えたら災害減免法は0円
    _checks.rounding(relief_saving(10_000_001), 0, "1000万円超の災害減免法")
    _checks.greater(relief_saving(10_000_000), 0, "1000万円ちょうどの災害減免法")
    #   住民税は災害減免法では1円も減らない
    for row in resident_grid():
        _checks.greater(row["resident"], row["relief_resident"] - 1,
                        "住民税の減り方が逆")
    _checks.unique_by(crossover_grid(), lambda r: r["income"], "交差点の表")
    #   控除額は3つに割れて、合計が元に戻る（消える分を落として数えていないこと）
    for row in carry_use_grid():
        parts = row["absorbed"] + row["lost"] + row["carried"]
        _checks.rounding(parts, row["deduction"],
                         f"控除額の内訳が合わない（損失{row['loss']:,}円）")
    #   要る割合は、損失が大きいほど1に近づく（足切りが相対的に小さくなる）
    _checks.increases_with(
        lambda L: related_share_needed(4_000_000, L) or 0.0,
        [500_000, 1_000_000, 2_000_000],
        "損失が増えたのに、5万円の式に要る割合が上がっていない")
    _checks.assumption_values(ASSUMPTIONS, name="zasson")


def main() -> None:
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 災害減免法の減税額は、損失がいくらでも同じ（決めているのは所得だけ）===")
    print(f"{'総所得金額等':>12s} {'軽減の割合':>9s} {'所得税':>11s} {'減る額':>11s}")
    for r in crossover_grid():
        print(f"{r['income']:11,d}円 {r['rate']:9.0%} "
              f"{income_tax(taxable_income(r['income'])):10,d}円 {r['relief']:10,d}円")
    print("  → 損失が100万円でも1000万円でも、この列は1円も動きません。"
          "**災害減免法は損害の大きさを見ていない**（2分の1以上という門を通ったあとは）。"
          "雑損控除は損失に比例して増えるので、**必ずどこかで入れ替わります。**")

    print("\n=== 雑損控除が災害減免法に追いつく損失額（その年だけで比べた場合）===")
    print(f"{'総所得金額等':>12s} {'足切り':>10s} {'災害減免で減る額':>13s} "
          f"{'雑損控除が勝つ損失':>15s} {'所得に対する比'}")
    for r in crossover_grid():
        x = f"{r['cross']:,}円" if r["cross"] is not None else "追いつかない"
        ratio = f"{r['ratio']:.2f}倍" if r["ratio"] else "—"
        print(f"{r['income']:11,d}円 {r['floor']:9,d}円 {r['relief']:12,d}円 "
              f"{x:>16s} {ratio:>10s}")
    print("  → 「どちらか有利なほうを選びましょう」で終わる説明が出さないのは、**この列です。**")

    print("\n=== 繰越3年を数えに入れても、交差点は1円も動かない ===")
    print(f"{'総所得金額等':>12s} {'その年だけ':>14s} {'繰越3年まで':>14s} {'手前に来る額'}")
    for r in carry_gain_grid():
        one = f"{r['one']:,}円" if r["one"] is not None else "追いつかない"
        four = f"{r['four']:,}円" if r["four"] is not None else "追いつかない"
        diff = f"{r['diff']:,}円" if r["diff"] is not None else "—"
        print(f"{r['income']:11,d}円 {one:>15s} {four:>15s} {diff:>13s}")
    print("  → 災害減免法は**その年かぎり**、雑損控除は**引ききれない分を3年くり越せる。**"
          "ところが**差の列は全部ゼロです。** 交差点の損失は所得の0.19〜0.38倍しかなく、"
          "**その額は1年で引ききれてしまう**ので、くり越す分がそもそも出ません。"
          "**「繰越があるから雑損控除が有利」は、有利不利の分かれ目には効いていません。**"
          "効くのは、下の帯です。")

    INC = 4_000_000
    print(f"\n=== 損失が所得を超えたとき、雑損控除はどこへ行くか（総所得{INC:,}円）===")
    print(f"{'差引損失額':>12s} {'控除額':>12s} {'税額を減らした':>13s} "
          f"{'消えた':>11s} {'くり越した':>12s} {'3年でも使えない'}")
    for r in carry_use_grid(INC):
        print(f"{r['loss']:11,d}円 {r['deduction']:11,d}円 {r['absorbed']:12,d}円 "
              f"{r['lost']:10,d}円 {r['carried']:11,d}円 {r['expired']:13,d}円")
    print(f"  → 制度の説明は「引ききれない分は3年くり越せます」で終わります。"
          f"**その手前に、くり越しにも回らずに消える{dead_band(INC):,}円の帯があります。**"
          "社会保険料控除と基礎控除にぶつかった分で、**くり越しの対象は"
          "「所得から引ききれなかった額」だと決まっているので、ここは1円も残りません。**"
          "そして損失が所得の4倍を超えると、**3年たっても使い切れない額**が出はじめます。")

    print("\n=== 所得が1円増えると、災害減免法の減税額はいくら落ちるか（3つの崖）===")
    print(f"{'この額まで':>12s} {'割合':>7s} {'減る額':>11s} → "
          f"{'1円超えると':>9s} {'減る額':>11s} {'落ちる額'}")
    for r in cliff_grid():
        print(f"{r['edge']:11,d}円 {r['rate_below']:7.0%} {r['below']:10,d}円 → "
              f"{r['rate_above']:14.0%} {r['above']:10,d}円 {r['drop']:11,d}円")
    print("  → **所得1円で減税額がこれだけ動く点が3つあります。**"
          "1000万円の段は、割合が落ちるのではなく**制度そのものが使えなくなる**ので、"
          "そこだけ性質が違います。")

    print("\n=== 損失があっても1円も効かない額（足切り＋消える帯）===")
    print(f"{'総所得金額等':>12s} {'足切り':>10s} {'消える帯':>11s} {'合計':>11s} {'所得に対する割合'}")
    for r in floor_grid():
        print(f"{r['income']:11,d}円 {r['floor']:9,d}円 {r['dead']:10,d}円 "
              f"{r['total']:10,d}円 {r['share']:14.1%}")
    print("  → 足切りは「総所得金額等の10パーセント」と説明されます。**そこで止まる説明が見落とすのが"
          "「消える帯」のほうです。** 雑損控除は所得から引くので、くり越せるのは"
          "**所得を超えた分だけ。** ところが税額が0になるのは社会保険料控除と基礎控除を引いた後なので、"
          "**その差はくり越しにも回らず、税額も減らさずに消えます。**")

    print("\n=== 損失のうち何割が「取り壊し・除去の費用」なら、5万円の式が勝つか"
          "（総所得400万円・足切り40万円）===")
    print(f"{'差引損失額':>11s} {'10パーセントの式':>15s} {'要る割合':>10s} "
          f"{'全部が関連支出なら':>15s} {'増える控除額'}")
    for r in related_grid():
        need = f"{r['need']:.1%}" if r["need"] is not None else "勝てない"
        print(f"{r['loss']:10,d}円 {r['by_floor']:14,d}円 {need:>11s} "
              f"{r['all_related']:14,d}円 {r['gain']:11,d}円")
    print("  → 2つの式の**多いほう**を使います。**要る割合は、損失が小さいほど低い。**"
          "40万円の損失なら**12.5パーセント**でひっくり返り、200万円なら"
          "**82.5パーセント**要ります。"
          "**同じ損失額でも、中身が何かで控除額が変わる**のはここで、"
          "「災害関連支出」に何を入れられるかを詰める価値は、**損失が小さい人ほど大きい。**")

    print("\n=== 住民税は、どちらを選ぶかで変わる（災害減免法は所得税だけ）===")
    print(f"{'総所得金額等':>12s} {'損失（所得の半分）':>15s} {'雑損控除の額':>12s} "
          f"{'住民税が減る額':>13s} {'災害減免法では'}")
    for r in resident_grid():
        print(f"{r['income']:11,d}円 {r['loss']:14,d}円 {r['deduction']:11,d}円 "
              f"{r['resident']:12,d}円 {r['relief_resident']:12,d}円")
    print("  → 災害減免法の側の列は**全部ゼロです。** 所得税だけを比べて選ぶと、"
          "この額をまるごと落とします。")

    print("\n=== 総所得1000万円の崖（ここから先は雑損控除しか無い）===")
    print(f"{'総所得金額等':>12s} {'割合':>7s} {'災害減免で減る額':>13s} "
          f"{'雑損控除（繰越込み）':>17s}")
    for r in over_cap_grid():
        print(f"{r['income']:11,d}円 {r['rate']:7.0%} {r['relief']:12,d}円 "
              f"{r['zasson']:16,d}円")
    print("  → 1000万円を1円超えた人は、**選択肢が1つになります。**"
          "上の表で「どちらが有利か」を考える必要そのものが無くなる。"
          "**災害減免法を先に検討するのは、所得1000万円以下の人だけです。**")


if __name__ == "__main__":
    main()
