"""遺族年金 —— **受け取る額を決めているのは、亡くなった人ではなく「末子の年齢」です。**

一般の解説はここで止まります ——「遺族基礎年金は年816,000円に子の加算。
遺族厚生年金は報酬比例部分の4分の3。子が18歳になるまで」。
**そのあと何が起きるかを、金額で言いません。**

そこから出てくる、公表されていない数字（すべて下の `__main__` が印字します。
金額は平均標準報酬額30万円・被保険者期間300月の場合）:

- **末子が18歳到達年度末に達した瞬間、年額は 1,420,768円 → 981,968円**（子1人）。
  **残るのは 69.1%。** 子4人なら 1,812,168円 → 同じ 981,968円 で **54.2%**。
  **子が多い世帯ほど落差が深い。** 落ちる先（中高齢寡婦加算）は
  **子の数を1人も数えないから**です。遺族基礎年金だけで見れば
  1,050,800円 → 612,000円 で 58.2% になります
- 落ちる先の 612,000円は、遺族基礎年金の基本額 816,000円の**ちょうど4分の3**。
  遺族厚生年金が報酬比例部分の4分の3であるのと**同じ分数が2か所に出ます**
- **子の加算は第3子から3分の1になりますが、ちょうど3分の1ではありません。**
  78,300円 × 3 ＝ 234,900円 で、第1子の加算 234,800円 とは **100円ずれます**
- **末子を21歳以下で産んだ妻は、中高齢寡婦加算を1円も受け取れません。**
  末子が18歳到達年度末に達したとき、まだ40歳になっていないからです。
  **失うのは 612,000円 × 25年 ＝ 15,300,000円。**
  境目は **21歳と22歳のあいだ**にあり、**21歳のときだけ末子の誕生月で決まります**
- **子のいない妻には「40歳の壁」があり、判定は夫が亡くなった1回だけです。**
  39歳で亡くされた人は、翌年40歳になっても付きません。65歳までの総額は
  **39歳 9,619,168円 に対して 40歳 24,549,200円 —— 1歳の差で 14,930,032円、2.55倍。**
  **1年長く受け取るほうが、1,493万円少ない。** 年齢と総額の向きが、ここだけ逆になります
- **被保険者期間が300月に足りない人は、あと1か月働いても遺族厚生年金が1円も増えません。**
  300月みなしがあるからです。120月の人と300月の人は**完全に同額**（369,968円）で、
  納めた保険料は **2.50倍**ちがいます。301月目に入った瞬間、
  1か月の値打ちが **0円から1,233円**（年額）へ立ち上がります
- **子のない妻は、30歳の誕生日の前か後かで生涯の受取額が 7.00倍**ちがいます
  （30歳未満は5年で打ち切り。65歳までを見た比較）。
  **この 7.00倍は金額にも報酬にもよりません** —— 35年 ÷ 5年 だからです。
  **子が1人でもいれば、30歳未満でも打ち切られません**

**遺族基礎年金は子の数で増えるのに、その子がいなくなった後に残るものは
子の数を見ない。そして「40歳以上か」は一度しか判定されない。**
この2つの非対称が、上の数字を全部生んでいます。
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値。**長く動いていないものだけをここに置く** ----------------
# 令和6年度・新規裁定の額。`nenkinmenjo.py` の満額 816,000円と同じ年度で揃えています。
BASIC_FULL = 816_000            # 遺族基礎年金の基本額（＝老齢基礎年金の満額。国民年金法38条）
CHILD_ADD_1_2 = 234_800         # 子の加算。第1子・第2子（国民年金法39条）
CHILD_ADD_3_ON = 78_300         # 子の加算。第3子以降
MIDDLE_WIDOW_ADD = 612_000      # 中高齢寡婦加算（厚生年金保険法62条。基本額の4分の3）

SURVIVOR_RATE = 3 / 4           # 遺族厚生年金＝老齢厚生年金の報酬比例部分の4分の3
MIN_MONTHS = 300                # 300月みなし（厚生年金保険法60条1項但書）
ACCRUAL = 5.481 / 1000          # 報酬比例の給付乗率（平成15年4月以降の期間）
PREMIUM_RATE_SELF = 0.0915      # 厚生年金保険料の本人負担（18.3%の半分）

CHILD_END_AGE = 18              # 子の要件は18歳到達年度の3月31日まで
WIDOW_ADD_FROM = 40             # 中高齢寡婦加算は40歳以上
WIDOW_ADD_TO = 65               # 65歳未満（65歳からは自分の老齢基礎年金）
YOUNG_WIDOW_AGE = 30            # 子のない妻がこの年齢未満だと有期
YOUNG_WIDOW_YEARS = 5           # 有期の年数

ASSUMPTIONS = [
    "遺族基礎年金の基本額は年816,000円、子の加算は第1子と第2子が各234,800円、"
    "第3子以降が各78,300円として計算しています。令和6年度の新規裁定の額です",
    "中高齢寡婦加算は年612,000円です。妻が40歳以上65歳未満で、"
    "遺族基礎年金を受けられないときに付きます",
    "遺族厚生年金は、亡くなった人の老齢厚生年金の報酬比例部分の4分の3です。"
    "報酬比例部分は、平均標準報酬額に1000分の5.481を掛け、被保険者期間の月数を掛けて出しています。"
    "平成15年4月より前の期間がある人は、別の乗率が混ざります",
    "被保険者期間が300月に足りないときは300月として計算しています。"
    "亡くなった時点で厚生年金に入っていた場合などの取り扱いです",
    "厚生年金保険料の本人負担は9.15パーセントとして計算しています。"
    "保険料率18.3パーセントを労使で半分ずつ負担するためです",
    "子は18歳到達年度の3月31日までを対象にしています。障害のある子は20歳までですが、"
    "ここには入れていません",
    "妻の年齢は、末子が18歳到達年度の3月31日を迎えた時点のものです。"
    "末子の誕生月によって、その時点の妻の年齢は末子を産んだ年齢に18を足した値と"
    "19を足した値のあいだで変わります",
    "生涯の受取額は、妻が65歳になるまでで区切っています。"
    "65歳からは自分の老齢年金との調整が入り、この計算の外になるためです",
    "物価と賃金による年度ごとの改定は入れていません。すべて令和6年度の額のまま"
    "据え置いて足し上げています",
    "遺族厚生年金の受給権は、亡くなった人に生計を維持されていたことが条件です。"
    "収入の要件（年収850万円未満など）は満たしているものとしています",
]


# ---- 遺族基礎年金 ------------------------------------------------------
def child_add(children: int) -> int:
    """子の加算の合計。**第3子から1人あたりが3分の1になります。**"""
    if children <= 0:
        return 0
    first = min(children, 2) * CHILD_ADD_1_2
    rest = max(0, children - 2) * CHILD_ADD_3_ON
    return first + rest


def basic_pension(children: int) -> int:
    """遺族基礎年金の年額。**子が0人なら受給権そのものがありません。**"""
    if children <= 0:
        return 0
    return BASIC_FULL + child_add(children)


def child_steps(max_children: int = 5) -> list[dict]:
    """子が1人増えると、遺族基礎年金はいくら増えるか。**段で幅が変わります。**"""
    rows = [{"子の数": n, "遺族基礎年金": basic_pension(n)}
            for n in range(1, max_children + 1)]
    steps = _checks.per_unit_steps(rows, "子の数", "遺族基礎年金",
                                   label="1人あたりの増え方", x_unit="人")
    for row, step in zip(rows, steps):
        row["1人あたりの増え方"] = None if step is None else round(step)
    return rows


# ---- 遺族厚生年金 ------------------------------------------------------
def proportional(avg_monthly: int, months: int) -> float:
    """報酬比例部分（年額）。**300月に足りなければ300月として計算します。**"""
    return avg_monthly * ACCRUAL * max(months, MIN_MONTHS)


def survivor_employee(avg_monthly: int, months: int) -> int:
    """遺族厚生年金の年額（報酬比例部分の4分の3）。"""
    return round(proportional(avg_monthly, months) * SURVIVOR_RATE)


def months_grid(avg_monthly: int = 300_000,
                months_list: tuple[int, ...] = (60, 120, 180, 240, 300, 301, 360, 480)
                ) -> list[dict]:
    """被保険者期間ごとの遺族厚生年金と、**納めた保険料に対する値打ち。**"""
    rows = []
    for m in months_list:
        pension = survivor_employee(avg_monthly, m)
        paid = round(avg_monthly * PREMIUM_RATE_SELF * m)
        rows.append({
            "平均標準報酬額": avg_monthly,
            "被保険者期間の月数": m,
            "計算に使われる月数": max(m, MIN_MONTHS),
            "遺族厚生年金": pension,
            "本人が納めた保険料の総額": paid,
            "保険料に対する年金の割合": pension / paid * 100 if paid else 0.0,
            "回収にかかる年数": paid / pension if pension else 0.0,
        })
    return rows


def one_more_month(avg_monthly: int, months: int) -> int:
    """「あと1か月働く」と、遺族厚生年金は年額でいくら増えるか。

    **300月に届いていない人は、必ず0円です。**
    """
    return survivor_employee(avg_monthly, months + 1) - survivor_employee(avg_monthly, months)


# ---- 末子が18歳になった瞬間 -------------------------------------------
def widow_add(age: float) -> int:
    """中高齢寡婦加算。**40歳以上65歳未満のあいだだけ。**"""
    return MIDDLE_WIDOW_ADD if WIDOW_ADD_FROM <= age < WIDOW_ADD_TO else 0


def cliff(children: int, avg_monthly: int = 300_000, months: int = 300,
          widow_age: float = 45) -> dict:
    """末子が18歳到達年度末に達した瞬間、年額はどう変わるか。

    **落ちる先は子の数を見ません。だから子が多いほど落差が深くなります。**
    """
    employee = survivor_employee(avg_monthly, months)
    before = basic_pension(children) + employee
    after = widow_add(widow_age) + employee
    return {
        "子の数": children,
        "18歳到達年度末の前": before,
        "18歳到達年度末の後": after,
        "落ちる額": before - after,
        "残る割合": after / before * 100,
        "1か月あたりの落ち込み": round((before - after) / 12),
    }


def cliff_grid(max_children: int = 4, **kw) -> list[dict]:
    return [cliff(n, **kw) for n in range(1, max_children + 1)]


# ---- 中高齢寡婦加算に、そもそも届くか ----------------------------------
def widow_age_range(mother_age_at_birth: int) -> tuple[int, int]:
    """末子が18歳到達年度末を迎えたときの、妻の年齢の幅。

    18歳の誕生日から次の3月31日までは0か月から11か月あるので、
    **妻の年齢は「産んだ年齢＋18」から「＋19」のあいだ**になります。
    """
    return mother_age_at_birth + CHILD_END_AGE, mother_age_at_birth + CHILD_END_AGE + 1


def widow_add_lifetime(reached: bool) -> int:
    """中高齢寡婦加算を、40歳から65歳まで受け取ったときの総額。"""
    return MIDDLE_WIDOW_ADD * (WIDOW_ADD_TO - WIDOW_ADD_FROM) if reached else 0


def reach_grid(ages: tuple[int, ...] = (16, 18, 19, 20, 21, 22, 23, 25, 28)) -> list[dict]:
    """末子を産んだ年齢べつに、中高齢寡婦加算に届くかどうか。"""
    rows = []
    for a in ages:
        low, high = widow_age_range(a)
        if low >= WIDOW_ADD_FROM:
            verdict, reached = "届く", True
        elif high >= WIDOW_ADD_FROM:
            verdict, reached = "末子の誕生月しだい", True
        else:
            verdict, reached = "届かない", False
        rows.append({
            "末子を産んだ年齢": a,
            "末子が18歳到達年度末のときの妻の年齢": f"{low}〜{high}",
            "中高齢寡婦加算": verdict,
            "受け取れる総額": widow_add_lifetime(reached),
            "届く人との差": widow_add_lifetime(True) - widow_add_lifetime(reached),
        })
    return rows


# ---- 子のない妻の「30歳の壁」 ------------------------------------------
def young_widow_years(age: float, children: int) -> int:
    """遺族厚生年金を受け取れる年数（65歳まで）。

    **子がいなくて30歳未満なら5年で終わります。子が1人でもいれば終わりません。**
    """
    if children == 0 and age < YOUNG_WIDOW_AGE:
        return YOUNG_WIDOW_YEARS
    return max(0, WIDOW_ADD_TO - int(age))


def young_widow_grid(ages: tuple[float, ...] = (25, 28, 29, 29.99, 30, 31, 35),
                     avg_monthly: int = 300_000, months: int = 300) -> list[dict]:
    pension = survivor_employee(avg_monthly, months)
    rows = []
    for a in ages:
        years = young_widow_years(a, children=0)
        rows.append({
            "夫が亡くなったときの妻の年齢": a,
            "受け取れる年数": years,
            "1年あたり": pension,
            "65歳までの総額": pension * years,
        })
    return rows


# ---- 生涯の総額 --------------------------------------------------------
def widow_add_eligible(widow_age: int, children: int,
                       youngest_child_age: int = 0) -> bool:
    """中高齢寡婦加算の要件を満たすか。**判定は一度きりで、あとから満たせません。**

    - 子がいない妻は、**夫が亡くなった時点で40歳以上65歳未満**であること。
      39歳で亡くされた人は、その後40歳になっても**付きません**
    - 子がいる妻は、**末子が18歳到達年度末に達した時点で**40歳以上65歳未満であること
    """
    if children == 0:
        return WIDOW_ADD_FROM <= widow_age < WIDOW_ADD_TO
    age_at_end = widow_age + (CHILD_END_AGE - youngest_child_age)
    return WIDOW_ADD_FROM <= age_at_end < WIDOW_ADD_TO


def lifetime(widow_age: int, children: int, youngest_child_age: int = 0,
             avg_monthly: int = 300_000, months: int = 300) -> dict:
    """妻が65歳になるまでに受け取る総額を、1年ずつ積み上げる。

    子の数は、上の子から順に18歳到達年度末で抜けていくものとして数えます
    （末子との年齢差は1歳きざみ）。
    """
    employee = survivor_employee(avg_monthly, months)
    if children == 0 and widow_age < YOUNG_WIDOW_AGE:
        return {
            "妻の年齢": widow_age, "子の数": children,
            "遺族厚生年金": employee * YOUNG_WIDOW_YEARS,
            "遺族基礎年金": 0, "中高齢寡婦加算": 0,
            "65歳までの総額": employee * YOUNG_WIDOW_YEARS,
        }
    eligible = widow_add_eligible(widow_age, children, youngest_child_age)
    # 上の子ほど早く抜ける。末子は youngest_child_age から数えて 18 年後まで
    child_ages = [youngest_child_age + i for i in range(children)]
    basic_total = 0
    add_total = 0
    emp_total = 0
    for year in range(WIDOW_ADD_TO - widow_age):
        alive = sum(1 for a in child_ages if a + year < CHILD_END_AGE)
        emp_total += employee
        if alive:
            basic_total += basic_pension(alive)
        elif eligible:
            add_total += widow_add(widow_age + year)
    return {
        "妻の年齢": widow_age,
        "子の数": children,
        "遺族厚生年金": emp_total,
        "遺族基礎年金": basic_total,
        "中高齢寡婦加算": add_total,
        "65歳までの総額": emp_total + basic_total + add_total,
    }


def childless_wall(ages: tuple[int, ...] = (36, 38, 39, 40, 41, 45),
                   avg_monthly: int = 300_000, months: int = 300) -> list[dict]:
    """**子のいない妻の「40歳の壁」。** 判定は夫が亡くなった時点の1回だけ。

    39歳で亡くされた人は、翌年40歳になっても中高齢寡婦加算が付きません。
    """
    rows = []
    for a in ages:
        row = lifetime(a, children=0, avg_monthly=avg_monthly, months=months)
        rows.append({
            "夫が亡くなったときの妻の年齢": a,
            "中高齢寡婦加算": row["中高齢寡婦加算"],
            "遺族厚生年金": row["遺族厚生年金"],
            "65歳までの総額": row["65歳までの総額"],
        })
    return rows


def lifetime_grid(ages: tuple[int, ...] = (30, 35, 40, 45),
                  children_list: tuple[int, ...] = (0, 1, 2, 3)) -> list[dict]:
    return [lifetime(a, c) for a in ages for c in children_list]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(BASIC_FULL, 816_000, "遺族基礎年金の基本額",
                      source="国民年金法38条（令和6年度・新規裁定）")
    _checks.statutory(CHILD_ADD_1_2, 234_800, "子の加算（第1子・第2子）",
                      source="国民年金法39条")
    _checks.statutory(CHILD_ADD_3_ON, 78_300, "子の加算（第3子以降）",
                      source="国民年金法39条")
    _checks.statutory(MIDDLE_WIDOW_ADD, 612_000, "中高齢寡婦加算",
                      source="厚生年金保険法62条")
    _checks.statutory(MIN_MONTHS, 300, "300月みなし",
                      source="厚生年金保険法60条1項但書")
    _checks.ratio(SURVIVOR_RATE, "遺族厚生年金の割合")
    _checks.ratio(ACCRUAL, "報酬比例の給付乗率")
    _checks.ratio(PREMIUM_RATE_SELF, "厚生年金保険料の本人負担")
    _checks.digits(BASIC_FULL, 500_000, 1_500_000, "遺族基礎年金の基本額")
    _checks.digits(MIDDLE_WIDOW_ADD, 300_000, 1_000_000, "中高齢寡婦加算")

    # 2. **この題材の主題そのもの。**汎用の検査では守れないところ
    # 中高齢寡婦加算は基本額のちょうど4分の3。遺族厚生年金と同じ分数
    _checks.rounding(MIDDLE_WIDOW_ADD, BASIC_FULL * SURVIVOR_RATE,
                     "中高齢寡婦加算は遺族基礎年金の基本額の4分の3")
    # 第3子以降の加算は、第1子・第2子の「ほぼ」3分の1。**ちょうどではありません。**
    # 78,300 × 3 = 234,900 で、実際の 234,800 とは 100円ずれます
    # （改定のたびに別々に丸めるため）。**この100円は主張の一部なので、
    # 「3分の1ちょうど」に直さないこと。**幅だけ見ます
    gap = CHILD_ADD_3_ON * 3 - CHILD_ADD_1_2
    if not 0 < gap <= 1_000:
        raise _checks.TableError(
            f"第3子の加算の3倍と第1子の加算の差が {gap:,}円。"
            f"100円前後のはず（どちらかの値が古い可能性）")

    # 子が増えれば遺族基礎年金も増える（ただし増え方は落ちる）
    _checks.increases_with(basic_pension, [1, 2, 3, 4, 5],
                           "子が増えたのに遺族基礎年金が増えていない")
    _checks.greater(CHILD_ADD_1_2, CHILD_ADD_3_ON,
                    "第1子の加算が第3子の加算以下")

    # **崖は必ず下向き**（子1人でも、落ちた先が元より大きくなってはいけない）
    for n in range(1, 5):
        row = cliff(n)
        _checks.greater(row["18歳到達年度末の前"], row["18歳到達年度末の後"],
                        f"子{n}人で、末子が抜けた後のほうが多くなっている")
    # **子が多いほど落差が深い**（落ちる先が子の数を見ないため）
    _checks.increases_with(lambda n: cliff(n)["落ちる額"], [1, 2, 3, 4],
                           "子が増えたのに落差が深くなっていない")

    # 300月みなし: 300月未満はすべて同額。「あと1か月」は0円
    _checks.rounding(survivor_employee(300_000, 120), survivor_employee(300_000, 300),
                     "120月と300月の遺族厚生年金が同額")
    for m in (60, 120, 240, 299):
        if one_more_month(300_000, m) != 0:
            raise _checks.TableError(
                f"被保険者期間{m}月で「あと1か月」が0円になっていない "
                f"（300月みなしが効いていません）")
    if one_more_month(300_000, 300) <= 0:
        raise _checks.TableError("300月を超えても「あと1か月」が増えていない")
    _checks.never_decreases(lambda m: survivor_employee(300_000, m),
                            [60, 120, 240, 300, 360, 480],
                            "被保険者期間が増えたのに遺族厚生年金が減っている")

    # 30歳の壁: 子がいなければ29歳と30歳で受給年数が跳ぶ。子がいれば跳ばない
    _checks.greater(young_widow_years(30, 0), young_widow_years(29, 0),
                    "子のない妻で、30歳のほうが29歳より受給年数が短い")
    _checks.greater(young_widow_years(29, 1), young_widow_years(29, 0),
                    "子がいる29歳のほうが、子のいない29歳より受給年数が短い")
    _checks.rounding(young_widow_years(30, 0) / YOUNG_WIDOW_YEARS, 7.0,
                     "30歳の壁の倍率（65歳までの35年 ÷ 5年）")

    # **40歳の壁。** 子のいない妻は、判定が夫の死亡時の1回だけなので、
    # **1歳若いほうが総額で少なくなります**（受け取る年数は1年長いのに）。
    # ここが逆転していなければ、要件をあとから満たせる実装になっています
    younger = lifetime(WIDOW_ADD_FROM - 1, children=0)["65歳までの総額"]
    older = lifetime(WIDOW_ADD_FROM, children=0)["65歳までの総額"]
    _checks.greater(older, younger,
                    "子のない妻で、40歳のほうが39歳より65歳までの総額が少ない"
                    "（中高齢寡婦加算をあとから満たせてしまっています）")
    if lifetime(WIDOW_ADD_FROM - 1, children=0)["中高齢寡婦加算"] != 0:
        raise _checks.TableError(
            "39歳で子のない妻に中高齢寡婦加算が付いている。"
            "要件は夫の死亡当時40歳以上で、あとから満たすことはできません")
    # 子がいれば、同じ39歳でも末子が抜けるときに40歳を超えるので付きます
    if lifetime(WIDOW_ADD_FROM - 1, children=1)["中高齢寡婦加算"] <= 0:
        raise _checks.TableError(
            "39歳で子が1人いる妻に中高齢寡婦加算が付いていない。"
            "末子が18歳到達年度末に達する時点では40歳を超えています")

    # 中高齢寡婦加算に届くかどうかの境目
    _checks.ascending([widow_age_range(a)[0] for a in (18, 20, 22, 25)],
                      "産んだ年齢と、末子が抜けるときの妻の年齢", strict=True)

    _checks.unique_by(child_steps(), lambda r: r["子の数"], "子の加算の表")
    _checks.unique_by(months_grid(), lambda r: r["被保険者期間の月数"], "被保険者期間の表")
    _checks.assumption_values(ASSUMPTIONS, name="izoku")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 子の加算は第3子から3分の1になる（1人増える値打ちが段で変わる） ===")
    for row in child_steps():
        print(row)

    print("\n=== 末子が18歳になった瞬間の崖（落ちる先は子の数を見ない） ===")
    for row in cliff_grid():
        print(row)

    print("\n=== 末子を21歳以下で産んだ妻は、中高齢寡婦加算に一生届かない ===")
    for row in reach_grid():
        print(row)

    print("\n=== 300月に足りない人は、あと1か月働いても1円も増えない ===")
    for row in months_grid():
        print(row)
    print({"平均標準報酬額": 300_000,
           "あと1か月の値打ち（240月）": one_more_month(300_000, 240),
           "あと1か月の値打ち（299月）": one_more_month(300_000, 299),
           "あと1か月の値打ち（300月）": one_more_month(300_000, 300),
           "あと1か月の値打ち（360月）": one_more_month(300_000, 360)})

    print("\n=== 子のない妻の「30歳の壁」——1日の差で総額が7倍 ===")
    for row in young_widow_grid():
        print(row)

    print("\n=== 子のない妻の「40歳の壁」——判定は夫が亡くなった1回だけ ===")
    for row in childless_wall():
        print(row)

    print("\n=== 妻の年齢と子の数べつ、65歳までに受け取る総額 ===")
    for row in lifetime_grid():
        print(row)
