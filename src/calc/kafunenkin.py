"""寡婦年金と死亡一時金は**どちらか一方しか選べない**。その分かれ目を全部計算する。

    python -m src.calc.kafunenkin

## この計算で出したいこと

国民年金の第1号被保険者だった夫が亡くなったとき、妻が受け取れるものは
（遺族基礎年金の対象になる子がいない場合）次の2つで、
**両方の受給権があるときは、どちらか一方を選びます**（国民年金法52条の6）。

    寡婦年金    夫の第1号期間だけで計算した老齢基礎年金額 × 3/4 を、
                妻の **60歳から65歳になるまで** 支給
    死亡一時金  夫の第1号期間の納付月数で決まる **1回きり** の 12万〜32万円

解説はここで止まります ——「多くの場合は寡婦年金のほうが多い」。
**では、いつ死亡一時金が勝つのか。** どこにも数字がありません。

一方は**期間×年額**、もう一方は**1回きりの定額**なので、
**妻の年齢**が分かれ目を作ります。65歳が近いほど寡婦年金の残り期間が短い。
その逆転する年齢を、夫の納付月数べつに全部出します。

そして、そこで**逆向きのこと**が起きます ——
**夫の納付月数が増えると死亡一時金も 12万 → 32万 と2.67倍に増え続ける**のに、
**寡婦年金がいちばん有利なのは、いちばん長く納めた人ではありません。**
区分の下端どうしを並べると、境目は **20年（240月）で頂点**を作り、そこから戻ります。

**この節は、最初「月数が増えるほど寡婦年金が有利」と書いて、`check_tables()` に
落とされました**（`ascending` が通らなかった）。形は昇順ではなく**上がって戻る**。
死亡一時金が**階段**、寡婦年金が**直線**なので、区分の中では境目が上がり続け、
**区分をまたぐ1か月だけ下がる** —— のこぎりの歯になります。
それでも歯は 64.22〜64.55歳 の中に収まるので、**結論は「妻が64歳を過ぎていなければ
寡婦年金」**で変わりません。**変わるのは理由のほうです。**

## いちばん大きいのは、額ではなく「消え方」

- **10年の崖**: 寡婦年金は、夫の納付＋免除が **10年（120月）以上** ないと出ません。
  9年11か月なら死亡一時金だけ。**1か月の差で、受け取る総額が6倍以上変わります。**
- **夫が老齢基礎年金を1回でも受け取ると、寡婦年金は丸ごと消えます**
  （国民年金法49条1項ただし書き）。繰上げ受給がここに当たる。
  **夫が受け取った額より、妻が失う額のほうが大きい**組合せを出します。

## 前提（動画にそのまま出すこと）

- 遺族基礎年金の対象になる子がいない場合（子がいる間は遺族基礎年金が優先します）
- 夫は国民年金の第1号被保険者だけだった（厚生年金の期間は入れていません）
- 婚姻期間10年以上・生計維持あり・妻は65歳未満で、寡婦年金の要件は満たす
- 妻は繰上げ支給の老齢基礎年金を受けていない（受けていると寡婦年金は出ません）
- 老齢基礎年金の満額は年816,000円（`nenkinmenjo.py` と同じ年度で揃えています）
- 物価スライドと年度改定は入れていません。**将来の額は動きます**

## 根拠の探し方（動画の説明欄用。URLは書かない）

- 寡婦年金の要件と額 … 国民年金法49条・50条
- 支給される期間（60歳から65歳まで） … 国民年金法51条
- 死亡一時金の要件と額 … 国民年金法52条の2・52条の4
- どちらか一方の選択 … 国民年金法52条の6
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値（国民年金法）--------------------------------------------
FULL_PENSION_YEAR = 816_000     # 老齢基礎年金の満額（年額）。nenkinmenjo.py と同じ年度
MONTHS_FULL = 480               # 満額になる月数（国民年金法27条）

KAFU_RATE = 0.75                # 寡婦年金は老齢基礎年金額の4分の3（国民年金法50条）
KAFU_FROM_AGE = 60              # 支給が始まる年齢（国民年金法51条）
KAFU_TO_AGE = 65                # 支給が終わる年齢（同上）
KAFU_MIN_MONTHS = 120           # 夫の納付＋免除がこれ未満だと出ない（国民年金法49条1項）
KAFU_MARRIAGE_YEARS = 10        # 婚姻期間の要件（同上）

ICHIJI_MIN_MONTHS = 36          # 死亡一時金に必要な月数（国民年金法52条の2第1項）
# 額の表（国民年金法52条の4別表）。`(月数の下限, 額)` を昇順に置く。
ICHIJI_TABLE: list[tuple[int, int]] = [
    (36, 120_000),
    (180, 145_000),
    (240, 170_000),
    (300, 220_000),
    (360, 270_000),
    (420, 320_000),
]
FUKA_ADD = 8_500                # 付加保険料を36月以上納めたときの加算（同条2項）
FUKA_ADD_MONTHS = 36

KURIAGE_RATE_PER_MONTH = 0.004  # 繰上げの減額率（1か月あたり0.4%）
KURIAGE_MIN_AGE = 60

ASSUMPTIONS = [
    "遺族基礎年金の対象になる子がいない場合の計算です。"
    "18歳になった年度末までの子がいる間は遺族基礎年金が優先するので、"
    "この2つの選択はその後の話になります",
    "夫は国民年金の第1号被保険者だけだったとしています。"
    "厚生年金の期間があると遺族厚生年金の側が出るので、比べる相手が変わります",
    "婚姻期間が10年以上あり、夫に生計を維持されていて、"
    "妻は65歳未満という寡婦年金の要件は満たしているものとしています",
    "妻は繰上げ支給の老齢基礎年金を受けていないものとしています。"
    "受けていると寡婦年金は支給されません",
    "老齢基礎年金の満額は年81万6,000円として計算しています。"
    "年度ごとに改定されるので、実際の額は変わります",
    "寡婦年金の額は、夫の第1号被保険者期間だけで計算した老齢基礎年金額の4分の3です。"
    "夫に厚生年金の期間があっても、そこは寡婦年金の計算に入りません",
    "免除期間がある場合、寡婦年金の額の計算では免除の種類ごとに反映割合が下がりますが、"
    "ここでは全期間が納付済みとして計算しています",
    "死亡一時金の額は納付済月数の区分で決まる定額で、1回きりの支給です。"
    "請求できる期間は死亡日の翌日から2年です",
    "物価や賃金による年度改定は入れていません。"
    "妻が受け取る5年分も、いまの額のまま置いています",
]


# ---- 寡婦年金の側 -------------------------------------------------------
def basic_pension(months: int) -> int:
    """夫の第1号期間だけで計算した老齢基礎年金の年額（円）。"""
    months = min(int(months), MONTHS_FULL)
    return round(FULL_PENSION_YEAR * months / MONTHS_FULL)


def kafu_year(months: int) -> int:
    """寡婦年金の年額（円）。要件を満たさない月数では 0。"""
    if int(months) < KAFU_MIN_MONTHS:
        return 0
    return round(basic_pension(months) * KAFU_RATE)


def kafu_years_left(wife_age: float) -> float:
    """妻がこれから寡婦年金を受け取れる年数。

    60歳前に夫が亡くなっても、支給は60歳からなので**5年まるまる**残ります。
    """
    start = max(float(wife_age), float(KAFU_FROM_AGE))
    return max(0.0, KAFU_TO_AGE - start)


def kafu_total(months: int, wife_age: float) -> int:
    """寡婦年金を選んだときに受け取る総額（円）。"""
    return round(kafu_year(months) * kafu_years_left(wife_age))


# ---- 死亡一時金の側 -----------------------------------------------------
def ichiji(months: int, fuka_months: int = 0) -> int:
    """死亡一時金の額（円）。36月に満たなければ 0。"""
    months = int(months)
    if months < ICHIJI_MIN_MONTHS:
        return 0
    amount = 0
    for low, yen in ICHIJI_TABLE:
        if months >= low:
            amount = yen
    if int(fuka_months) >= FUKA_ADD_MONTHS:
        amount += FUKA_ADD
    return amount


# ---- 分かれ目 -----------------------------------------------------------
def better(months: int, wife_age: float, fuka_months: int = 0) -> dict:
    """その月数・その妻の年齢で、どちらが多いか。"""
    k = kafu_total(months, wife_age)
    i = ichiji(months, fuka_months)
    return {
        "納付月数": int(months),
        "妻の年齢": float(wife_age),
        "寡婦年金の総額": k,
        "死亡一時金": i,
        "多いほう": "寡婦年金" if k > i else ("死亡一時金" if i > k else "同額"),
        "差": abs(k - i),
    }


def crossover_age(months: int, fuka_months: int = 0) -> float | None:
    """死亡一時金のほうが多くなる、妻の年齢の境目。

    これより**上**なら死亡一時金。寡婦年金が1円も出ない月数では `None`
    （比べる相手がいないので、境目という言い方が成り立ちません）。
    """
    year = kafu_year(months)
    if year <= 0:
        return None
    need = ichiji(months, fuka_months) / year        # 何年ぶんに当たるか
    if need >= (KAFU_TO_AGE - KAFU_FROM_AGE):
        return float(KAFU_FROM_AGE)                  # 60歳でも死亡一時金が勝つ
    return KAFU_TO_AGE - need


def crossover_grid(fuka_months: int = 0) -> list[dict]:
    """死亡一時金の区分ごとに、境目の年齢を並べる。"""
    rows = []
    for low, _yen in ICHIJI_TABLE:
        months = max(low, KAFU_MIN_MONTHS)
        age = crossover_age(months, fuka_months)
        rows.append({
            "納付月数": months,
            "寡婦年金の年額": kafu_year(months),
            "死亡一時金": ichiji(months, fuka_months),
            "境目の年齢": age,
            "境目までの月数": None if age is None else round((KAFU_TO_AGE - age) * 12, 1),
        })
    return rows


def ten_year_cliff(wife_age: float = 60) -> dict:
    """10年（120月）の崖。**1か月で、受け取る総額がいくら変わるか。**"""
    before = KAFU_MIN_MONTHS - 1
    after = KAFU_MIN_MONTHS
    lo = max(kafu_total(before, wife_age), ichiji(before))
    hi = max(kafu_total(after, wife_age), ichiji(after))
    return {
        "手前の月数": before,
        "手前で受け取る総額": lo,
        "手前の中身": "死亡一時金",
        "10年ちょうどの総額": hi,
        "10年ちょうどの中身": "寡婦年金",
        "差": hi - lo,
        "倍率": hi / lo if lo else None,
    }


def ichiji_steps() -> list[dict]:
    """死亡一時金の階段を、寡婦年金の同じ1か月ぶんと並べる。

    **崖の高さは死亡一時金のほうが桁違いに大きいのに、選ぶ側は変わりません。**
    """
    rows = []
    step_year = FULL_PENSION_YEAR / MONTHS_FULL * KAFU_RATE       # 1か月ぶんの年額
    span = KAFU_TO_AGE - KAFU_FROM_AGE
    for low, _yen in ICHIJI_TABLE[1:]:
        rows.append({
            "またぐ月数": low,
            "死亡一時金の跳び": ichiji(low) - ichiji(low - 1),
            "寡婦年金の跳び（5年分）": round(step_year * span),
            "倍率": (ichiji(low) - ichiji(low - 1)) / (step_year * span),
        })
    return rows


def kuriage_loss(months: int, husband_months_received: int,
                 wife_age: float = 60) -> dict:
    """夫が繰上げ受給を1回でも受けると、寡婦年金は丸ごと消える。

    夫が **60歳ちょうど** で繰上げたとして、受け取った額と、妻が失う額を比べます。
    """
    reduction = 1 - KURIAGE_RATE_PER_MONTH * (65 - KURIAGE_MIN_AGE) * 12
    got = round(basic_pension(months) * reduction * husband_months_received / 12)
    lost = kafu_total(months, wife_age)
    left = ichiji(months)                       # 死亡一時金は残ります
    return {
        "納付月数": int(months),
        "夫が受け取った月数": int(husband_months_received),
        "夫が受け取った額": got,
        "妻が失う寡婦年金": lost,
        "妻に残る死亡一時金": left,
        "世帯の差引": got + left - lost,
        "取り返せる月数": None if basic_pension(months) <= 0 else round(
            lost / (basic_pension(months) * reduction / 12), 1),
    }


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""
    _checks.statutory(KAFU_RATE, 0.75, "寡婦年金の割合", source="国民年金法50条")
    _checks.statutory(KAFU_FROM_AGE, 60, "寡婦年金が始まる年齢", source="国民年金法51条")
    _checks.statutory(KAFU_TO_AGE, 65, "寡婦年金が終わる年齢", source="国民年金法51条")
    _checks.statutory(KAFU_MIN_MONTHS, 120, "寡婦年金に必要な月数",
                      source="国民年金法49条1項（平成29年8月から10年）")
    _checks.statutory(ICHIJI_MIN_MONTHS, 36, "死亡一時金に必要な月数",
                      source="国民年金法52条の2第1項")
    _checks.statutory(FUKA_ADD, 8_500, "付加保険料を納めたときの加算",
                      source="国民年金法52条の4第2項")
    _checks.statutory(MONTHS_FULL, 480, "満額になる月数", source="国民年金法27条")
    _checks.ratio(KAFU_RATE, "寡婦年金の割合")
    _checks.ratio(KURIAGE_RATE_PER_MONTH, "繰上げの1か月あたりの減額率")
    _checks.digits(FULL_PENSION_YEAR, 500_000, 1_200_000, "老齢基礎年金の満額")

    # 1. 死亡一時金の表は、月数でも額でも昇順（書き写しの取り違えを弾く）
    _checks.ascending([m for m, _ in ICHIJI_TABLE], "死亡一時金の区分の月数", strict=True)
    _checks.ascending([y for _, y in ICHIJI_TABLE], "死亡一時金の額", strict=True)
    _checks.unique_by(ICHIJI_TABLE, lambda r: r[0], "死亡一時金の区分")

    # 2. 要件に足りない月数では、それぞれ0
    if ichiji(ICHIJI_MIN_MONTHS - 1) != 0:
        raise _checks.TableError("36月未満で死亡一時金が出ています")
    if kafu_year(KAFU_MIN_MONTHS - 1) != 0:
        raise _checks.TableError("120月未満で寡婦年金が出ています")

    # 3. 月数が増えて、どちらも減らないこと
    months = list(range(120, 481, 12))
    _checks.never_decreases(kafu_year, months, "寡婦年金の年額")
    _checks.never_decreases(lambda m: ichiji(m), months, "死亡一時金")

    # 4. **満額のときの寡婦年金は、満額の4分の3**（式と独立に、数で置く）
    _checks.rounding(kafu_year(MONTHS_FULL), 612_000, "満額での寡婦年金の年額")

    # 5. 60歳前に夫が亡くなっても、支給期間は5年のまま（60歳からなので）
    for age in (40, 50, 59, 60):
        if kafu_years_left(age) != 5:
            raise _checks.TableError(
                f"妻{age}歳で寡婦年金の残り期間が5年になっていません: "
                f"{kafu_years_left(age)}")
    if kafu_years_left(65) != 0:
        raise _checks.TableError("65歳で寡婦年金の残り期間が0になっていません")

    # 6. **境目はどの月数でも64歳台**（＝寡婦年金が勝つ範囲のほうが広い）
    for row in crossover_grid():
        age = row["境目の年齢"]
        if age is None or not (64 <= age < 65):
            raise _checks.TableError(
                f"境目の年齢が64歳台に入っていません: 月数{row['納付月数']} → {age}")

    # 7. **境目は「上がって戻る」**（2026-08-18。**ここは暗算で「昇順」と書いて、
    #    この検査に落とされました**）。死亡一時金は階段・寡婦年金は直線なので、
    #    区分の下端どうしを並べると **240月（20年）で頂点**を作り、そこから下がります。
    #    「月数が増えるほど寡婦年金が有利」は**間違い**です。
    ages = [r["境目の年齢"] for r in crossover_grid()]
    top = ages.index(max(ages))
    if top in (0, len(ages) - 1):
        raise _checks.TableError(
            f"境目の頂点が端に来ています（上がって戻る形になっていない）: {ages}")
    _checks.ascending(ages[:top + 1], "頂点までの境目の年齢", strict=True)
    _checks.ascending(list(reversed(ages[top:])), "頂点から先の境目の年齢", strict=True)
    if crossover_grid()[top]["納付月数"] != 240:
        raise _checks.TableError(
            f"頂点が240月ではありません: {crossover_grid()[top]['納付月数']}月")

    # 8. **区分の中では、境目は上がり続けます**（死亡一時金が据え置きのまま
    #    寡婦年金だけ増えるため）。**下がるのは区分をまたぐ1か月だけ** ＝ のこぎり。
    for low, _yen in ICHIJI_TABLE[1:]:
        inside = crossover_age(low - 1)
        after = crossover_age(low)
        if inside is None or after is None or not (after < inside):
            raise _checks.TableError(
                f"{low}月をまたいで境目が下がっていません: {inside} → {after}")

    # 9. 10年の崖は、手前の6倍以上（1か月の差）
    cliff = ten_year_cliff()
    _checks.greater(cliff["倍率"], 6.0, "10年の崖の倍率が")
    _checks.greater(cliff["差"], 600_000, "10年の崖の差が")

    # 10. **死亡一時金の跳びは、同じ1か月の寡婦年金より必ず大きい**
    #    （それでも選ぶ側が変わらないことが、この表のいちばんの主題です）
    for row in ichiji_steps():
        _checks.greater(row["死亡一時金の跳び"], row["寡婦年金の跳び（5年分）"],
                        f"{row['またぐ月数']}月をまたぐ死亡一時金の跳びが")

    # 11. 繰上げで失うほうが大きいこと（世帯の差引がマイナス）
    loss = kuriage_loss(MONTHS_FULL, 12)
    _checks.greater(0, loss["世帯の差引"], "繰上げ1年での世帯の差引が0より")


def main() -> None:
    check_tables()

    print("\n=== 10年（120月）の崖 —— 1か月の差で、妻が受け取る総額が5倍以上になる ===")
    c = ten_year_cliff()
    print(f"  夫の納付 {c['手前の月数']}月（9年11か月）… "
          f"{c['手前の中身']} **{c['手前で受け取る総額']:,}円**")
    print(f"  夫の納付 {KAFU_MIN_MONTHS}月（10年ちょうど）… "
          f"{c['10年ちょうどの中身']} **{c['10年ちょうどの総額']:,}円**")
    print(f"  差 **{c['差']:,}円** ／ **{c['倍率']:.2f}倍**"
          "（寡婦年金は納付＋免除が10年以上ないと1円も出ない）")

    print("\n=== 死亡一時金が勝つのは、妻が65歳になる何か月前からか ===")
    for r in crossover_grid():
        print(f"  納付 {r['納付月数']:>3}月  寡婦年金 年{r['寡婦年金の年額']:>7,}円  "
              f"死亡一時金 {r['死亡一時金']:>7,}円  → 境目 "
              f"**{r['境目の年齢']:.2f}歳**（65歳の {r['境目までの月数']:.1f}か月前）")

    print("\n=== 寡婦年金がいちばん有利なのは、いちばん長く納めた人ではなく20年ちょうどの人 ===")
    g = crossover_grid()
    top = max(g, key=lambda r: r["境目の年齢"])
    for r in g:
        mark = "  ← **頂点**" if r is top else ""
        print(f"  納付 {r['納付月数']:>3}月（{r['納付月数'] // 12}年）  "
              f"死亡一時金 {r['死亡一時金']:>7,}円  → 境目 "
              f"{r['境目の年齢']:.2f}歳{mark}")
    print(f"  **上がって、戻ります。** 死亡一時金は {g[0]['死亡一時金']:,}円 → "
          f"{g[-1]['死亡一時金']:,}円 と **{g[-1]['死亡一時金'] / g[0]['死亡一時金']:.2f}倍**に"
          "増え続けるのに、境目は頂点を作って下がる")
    print(f"  頂点は **{top['納付月数'] // 12}年**（{top['境目の年齢']:.2f}歳）。"
          f"いちばん長い {g[-1]['納付月数'] // 12}年は {g[-1]['境目の年齢']:.2f}歳で、"
          f"**{(top['境目の年齢'] - g[-1]['境目の年齢']) * 12:.1f}か月ぶん手前**に戻っている")

    print("\n=== 境目が下がるのは、区分をまたぐ1か月だけ（区分の中では上がり続ける）===")
    for low, _yen in ICHIJI_TABLE[1:]:
        print(f"  {low - 1:>3}月 {crossover_age(low - 1):.3f}歳  →  "
              f"{low:>3}月 **{crossover_age(low):.3f}歳**"
              f"（1か月で {(crossover_age(low - 1) - crossover_age(low)) * 12:.2f}か月ぶん手前へ）")
    print(f"  いちばん遅い境目は **{max(crossover_age(m) for m in range(120, 481)):.3f}歳**、"
          f"いちばん早い境目は **{min(crossover_age(m) for m in range(120, 481)):.3f}歳**。"
          "**どの月数でも64歳台に収まります** ＝ 妻が64歳を過ぎていなければ、必ず寡婦年金")

    print("\n=== 死亡一時金の階段は大きいのに、選ぶ側は1回も入れ替わらない ===")
    for r in ichiji_steps():
        print(f"  {r['またぐ月数']:>3}月をまたぐ1か月  死亡一時金 "
              f"**+{r['死亡一時金の跳び']:,}円**  対  寡婦年金5年分 "
              f"+{r['寡婦年金の跳び（5年分）']:,}円  （**{r['倍率']:.2f}倍**）")
    print("  **跳ぶのは死亡一時金のほうですが、総額では寡婦年金が勝ったままです。**")

    print("\n=== 夫が繰上げ受給を1回受けると、妻の寡婦年金は丸ごと消える ===")
    for got_months in (1, 12, 36):
        k = kuriage_loss(MONTHS_FULL, got_months)
        print(f"  夫が繰上げで {k['夫が受け取った月数']:>2}か月ぶん受け取った "
              f"**{k['夫が受け取った額']:>9,}円**  →  "
              f"妻が失う寡婦年金 **{k['妻が失う寡婦年金']:,}円**"
              f"（残るのは死亡一時金 {k['妻に残る死亡一時金']:,}円）"
              f"  世帯の差引 **{k['世帯の差引']:,}円**")
    print(f"  夫が繰上げで取り戻すには **{kuriage_loss(MONTHS_FULL, 1)['取り返せる月数']:.1f}か月** "
          "受け取り続ける必要がある（65歳前に亡くなると、そこまで届かない）")

    print("\n=== 妻の年齢べつ、どちらを選ぶか（夫の納付480月）===")
    for age in (55, 60, 62, 64, 64.4, 64.5, 65):
        b = better(MONTHS_FULL, age)
        print(f"  妻 {age:>4}歳  寡婦年金 {b['寡婦年金の総額']:>9,}円  "
              f"死亡一時金 {b['死亡一時金']:>7,}円  → **{b['多いほう']}**"
              f"（差 {b['差']:,}円）")


if __name__ == "__main__":
    main()
