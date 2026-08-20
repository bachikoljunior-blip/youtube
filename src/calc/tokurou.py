"""特別支給の老齢厚生年金を、いつからいくら受け取れるか。

**一般の解説は「生年月日によっては65歳より前に年金が出る」で止まります。**
その先に、口を開けている段が3つあります。

1つめ。**この年金は繰下げができません。** 厚生年金保険法附則8条の2の年金は
同法44条の3（繰下げ）の対象に入っていないので、**請求を遅らせても1円も増えません。**
本体の老齢厚生年金なら1か月で0.7パーセント増えるところが、ここでは
**遅らせた月数ぶん、そのまま消えます。** 60か月遅らせれば 6,000,000円 が消え、
繰下げができたなら +504,000円 増えていたはずなので、**損は二重です**（年額120万円のとき）。

2つめ。**5年をこえた分は、請求しても戻りません**（厚生年金保険法92条1項）。
72か月後に気づいた人は本来 7,200,000円 のところ 1,200,000円 が時効で消え、
取り返せるのは 6,000,000円 までです。

3つめ。**特別支給がある世代は、繰上げの減額率が全員 1か月0.5パーセントの側です。**
0.4パーセントに変わるのは昭和37年4月2日以降生まれで、
その世代には**そもそも特別支給がありません**。だから
「繰上げは0.4パーセントになったから軽くなった」は、この年金の当事者には当てはまりません。
60か月繰り上げると 840,000円 で、0.4パーセントの世代なら 912,000円。差は 72,000円 です。

この表が出す数字（実行して出たものを、丸めずに写しています。年額120万円のとき）:

- 男性は昭和28年4月1日以前生まれなら 60か月・6,000,000円、
  昭和34年4月2日〜昭和36年4月1日なら 12か月・1,200,000円、
  **昭和36年4月2日からは 0か月・0円**です
- **1日ちがいで 1,200,000円 が消えます**（昭和36年4月1日生まれと4月2日生まれ）。
  報酬比例部分の年額が 2,400,000円 の人なら、消えるのは 2,400,000円 です
- 女性は同じ階段を5年おくれで下るので、同じ区分で最大 2,400,000円 多く受け取れます
- 厚生年金の被保険者期間が **11か月なら0円、12か月なら 1,200,000円**。
  65歳からの老齢厚生年金は1か月でも出るので、**この段差は特別支給にだけあります**
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値 -------------------------------------------------------------
# 厚生年金保険法 附則8条・8条の2（報酬比例部分の支給開始年齢）。
# (区分の名前, 男性の開始年齢, 女性の開始年齢)。女性（第1号厚生年金被保険者）は
# **同じ階段を5年おくれで下ります**。
COHORTS: tuple[tuple[str, int, int], ...] = (
    ("昭和28年4月1日以前生まれ（女性は昭和33年4月1日以前）", 60, 60),
    ("昭和28年4月2日〜昭和30年4月1日（女性は5年おくれ）", 61, 60),
    ("昭和30年4月2日〜昭和32年4月1日（女性は5年おくれ）", 62, 60),
    ("昭和32年4月2日〜昭和34年4月1日（女性は5年おくれ）", 63, 61),
    ("昭和34年4月2日〜昭和36年4月1日（女性は5年おくれ）", 64, 62),
    ("昭和36年4月2日〜昭和38年4月1日（女性は5年おくれ）", 65, 63),
    ("昭和38年4月2日〜昭和40年4月1日（女性は5年おくれ）", 65, 64),
    ("昭和41年4月2日以降生まれ", 65, 65),
)

PENSION_AGE = 65               # 本体の老齢厚生年金が始まる年齢
KURIAGE_RATE_OLD = 0.005       # 繰上げの減額率（昭和37年4月1日以前生まれ）
KURIAGE_RATE_NEW = 0.004       # 繰上げの減額率（昭和37年4月2日以降生まれ）
KURISAGE_RATE = 0.007          # 繰下げの増額率（1か月あたり）
TIMEBAR_YEARS = 5              # 年金を受ける権利の時効（厚生年金保険法92条1項）
NEED_MONTHS_TOKUROU = 12       # 特別支給に要る厚生年金の被保険者期間
NEED_MONTHS_HONTAI = 1         # 65歳からの老齢厚生年金に要る期間

# **繰下げができないこと**は、厚生年金保険法附則8条の2の年金が
# 同法44条の3（繰下げ）の対象に入っていないことから来ています。
CAN_KURISAGE = False

ASSUMPTIONS = [
    "支給開始年齢は厚生年金保険法附則8条・8条の2の報酬比例部分で、"
    "女性（第1号厚生年金被保険者）は男性と同じ階段を5年おくれで下ります",
    "特別支給の老齢厚生年金は繰下げの対象外なので、"
    "請求を遅らせても1円も増えません",
    "受け取る権利の時効は5年です（厚生年金保険法92条1項）",
    "特別支給を受けるには厚生年金の被保険者期間が1年以上必要で、"
    "65歳からの老齢厚生年金は1か月でも足ります",
    "繰上げの減額率は昭和37年4月1日以前生まれが1か月0.5パーセント、"
    "昭和37年4月2日以降生まれが1か月0.4パーセントです",
    "繰下げの増額率は1か月0.7パーセントです",
    "報酬比例部分の年額はその人の記録で決まるので、"
    "この表では年額そのものを変数に置いています",
    "在職老齢年金による支給停止と、雇用保険との調整は、この表に入れていません",
]


# ---- 計算 -----------------------------------------------------------------

def start_age(cohort: int, *, female: bool = False) -> int:
    """その区分の、報酬比例部分がはじまる年齢。"""
    name, male_age, female_age = COHORTS[cohort]
    return female_age if female else male_age


def months_before_65(cohort: int, *, female: bool = False) -> int:
    """65歳になるまでに、特別支給として受け取れる月数。"""
    return (PENSION_AGE - start_age(cohort, female=female)) * 12


def total_before_65(annual: float, cohort: int, *, female: bool = False) -> float:
    """その月数ぶんの総額。"""
    return annual / 12 * months_before_65(cohort, female=female)


def cohort_table(annual: float = 1_200_000) -> list[dict]:
    """世代ごとに、65歳より前に受け取れる月数と総額。"""
    out = []
    for i, (name, _m, _f) in enumerate(COHORTS):
        out.append({
            "区分": name,
            "男性の開始年齢": start_age(i),
            "男性の月数": months_before_65(i),
            "男性の総額": total_before_65(annual, i),
            "女性の開始年齢": start_age(i, female=True),
            "女性の月数": months_before_65(i, female=True),
            "女性の総額": total_before_65(annual, i, female=True),
        })
    return out


def sex_gap(annual: float, cohort: int) -> float:
    """同じ区分で、女性のほうが多く受け取れる額。"""
    return total_before_65(annual, cohort, female=True) - total_before_65(annual, cohort)


def sex_gap_table(annual: float = 1_200_000) -> list[dict]:
    """5年おくれの階段が生む、同じ生年月日での差。"""
    out = []
    for i, (name, _m, _f) in enumerate(COHORTS):
        out.append({
            "区分": name,
            "男性の総額": total_before_65(annual, i),
            "女性の総額": total_before_65(annual, i, female=True),
            "差": sex_gap(annual, i),
        })
    return out


def lost_by_delay(annual: float, months: int) -> float:
    """請求を遅らせた月数ぶん、受け取り損ねる額（時効の中でも取り戻せる分は除く）。"""
    return annual / 12 * months


def would_be_kurisage(annual: float, months: int) -> float:
    """もし繰下げができたなら、その待ちで増えていたはずの年額。"""
    return annual * (1 + KURISAGE_RATE * months)


def delay_table(annual: float = 1_200_000) -> list[dict]:
    """遅らせた月数ごとに、消える額と「増えていたはずの額」。"""
    out = []
    for m in (6, 12, 24, 36, 48, 60, 72):
        out.append({
            "遅らせた月数": m,
            "受け取り損ねる額": lost_by_delay(annual, m),
            "時効で取り返せない額": lost_by_delay(annual, min(m, TIMEBAR_YEARS * 12))
            if m > TIMEBAR_YEARS * 12 else 0.0,
            "繰下げなら増えていた年額": would_be_kurisage(annual, m),
            "繰下げなら増えていた分": would_be_kurisage(annual, m) - annual,
        })
    return out


def timebar_lost(annual: float, months: int) -> float:
    """時効で完全に消える額（5年より前の分）。"""
    over = max(0, months - TIMEBAR_YEARS * 12)
    return annual / 12 * over


def timebar_table(annual: float = 1_200_000) -> list[dict]:
    """気づくのが遅れた月数ごとに、時効で消える額。"""
    out = []
    for m in (48, 60, 61, 72, 84, 96):
        out.append({
            "気づくまでの月数": m,
            "本来の額": lost_by_delay(annual, m),
            "時効で消える額": timebar_lost(annual, m),
            "まだ取り返せる額": lost_by_delay(annual, m) - timebar_lost(annual, m),
        })
    return out


def kuriage_rate(*, born_after_s37: bool) -> float:
    """繰上げの減額率。**特別支給がある世代は、全員が古いほうの率です。**"""
    return KURIAGE_RATE_NEW if born_after_s37 else KURIAGE_RATE_OLD


def kuriage_table(annual: float = 1_200_000) -> list[dict]:
    """60歳まで繰り上げたときの減額（世代でどちらの率が当たるか）。"""
    out = []
    for months in (12, 24, 36, 48, 60):
        old = annual * (1 - kuriage_rate(born_after_s37=False) * months)
        new = annual * (1 - kuriage_rate(born_after_s37=True) * months)
        out.append({
            "繰り上げた月数": months,
            "0.5パーセントの世代": old,
            "0.4パーセントの世代": new,
            "差": new - old,
        })
    return out


def need_months_table(annual: float = 1_200_000) -> list[dict]:
    """被保険者期間が11か月と12か月で、65歳前の総額がどう変わるか。"""
    out = []
    for m in (1, 11, 12, 13):
        ok = m >= NEED_MONTHS_TOKUROU
        out.append({
            "厚生年金の被保険者期間（月）": m,
            "特別支給": "出る" if ok else "出ない",
            "64歳開始なら65歳までの総額": total_before_65(annual, 4) if ok else 0.0,
            "65歳からの老齢厚生年金": "出る" if m >= NEED_MONTHS_HONTAI else "出ない",
        })
    return out


def one_day_gap(annual: float = 1_200_000) -> float:
    """昭和36年4月1日生まれと4月2日生まれの差（男性）。"""
    return total_before_65(annual, 4) - total_before_65(annual, 5)


def annual_grid_table(grid: tuple[int, ...] = (600_000, 1_200_000, 1_800_000,
                                              2_400_000)) -> list[dict]:
    """年額べつに、1日の生まれ違いで消える総額（男性・昭和36年4月）。"""
    out = []
    for a in grid:
        out.append({
            "報酬比例部分の年額": a,
            "1日ちがいで消える総額": one_day_gap(a),
            "64歳開始の総額": total_before_65(a, 4),
            "65歳開始の総額": total_before_65(a, 5),
        })
    return out


def grid() -> list[dict]:
    """図解の元になる表。**世代ごとの階段が、この表のいちばんの主題です。**"""
    return cohort_table()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""

    _checks.statutory(PENSION_AGE, 65, "老齢厚生年金の支給開始年齢",
                      source="厚生年金保険法42条")
    _checks.statutory(KURIAGE_RATE_OLD, 0.005,
                      "繰上げの減額率（昭和37年4月1日以前生まれ）",
                      source="厚生年金保険法施行令6条の3")
    _checks.statutory(KURIAGE_RATE_NEW, 0.004,
                      "繰上げの減額率（昭和37年4月2日以降生まれ）",
                      source="厚生年金保険法施行令6条の3")
    _checks.statutory(KURISAGE_RATE, 0.007, "繰下げの増額率",
                      source="厚生年金保険法44条の3")
    _checks.statutory(TIMEBAR_YEARS, 5, "年金を受ける権利の時効",
                      source="厚生年金保険法92条1項")
    _checks.statutory(NEED_MONTHS_TOKUROU, 12,
                      "特別支給に要る厚生年金の被保険者期間",
                      source="厚生年金保険法附則8条")
    _checks.ratio(KURIAGE_RATE_OLD, "繰上げの減額率（古い側）")
    _checks.ratio(KURISAGE_RATE, "繰下げの増額率")

    # 1. **主題その1**: 階段は下るだけ。世代が新しいほど月数は減る。
    _checks.never_decreases(lambda i: -months_before_65(i),
                            list(range(len(COHORTS))),
                            "世代が新しいのに月数が増えている")
    _checks.rounding(months_before_65(0), 60, "いちばん上の世代の月数")
    _checks.rounding(months_before_65(len(COHORTS) - 1), 0,
                     "いちばん下の世代の月数（特別支給が無い）")

    # 2. **主題その2**: 女性のほうが遅れて下るので、同じ区分では多い。
    for i in range(len(COHORTS)):
        # +1 は「以上」を言うため（`greater` は真に大きいことしか言えない）
        _checks.greater(months_before_65(i, female=True) + 1, months_before_65(i),
                        f"区分{i}で女性の月数が男性より少ない")
    _checks.greater(sex_gap(1_200_000, 5), 0,
                    "昭和36年4月2日〜の区分で男女差が無い")

    # 3. **主題その3**: 繰下げができないので、遅らせた分はそのまま消える。
    assert not CAN_KURISAGE, "特別支給は繰下げの対象外"
    _checks.increases_with(lambda m: lost_by_delay(1_200_000, m),
                           [6, 12, 24, 36, 60],
                           "遅らせたのに消える額が増えていない")
    _checks.rounding(lost_by_delay(1_200_000, 12), 1_200_000,
                     "1年遅らせて消える額")
    # 「増えていたはず」の側と比べると、損は二重になる。
    _checks.greater(would_be_kurisage(1_200_000, 12), 1_200_000,
                    "繰下げの増額が効いていない")

    # 4. 時効は5年より前だけを削ること。
    _checks.rounding(timebar_lost(1_200_000, 60), 0, "5年ちょうどで消える額")
    _checks.greater(timebar_lost(1_200_000, 61), 0, "5年を1か月こえても消えない")
    _checks.rounding(timebar_lost(1_200_000, 72), 1_200_000,
                     "6年で時効になる額")

    # 5. **主題その4**: 特別支給がある世代は、繰上げの率が全員 0.5 パーセント。
    _checks.greater(kuriage_rate(born_after_s37=False),
                    kuriage_rate(born_after_s37=True),
                    "古い世代のほうが減額率が小さい")
    row = next(r for r in kuriage_table() if r["繰り上げた月数"] == 60)
    _checks.greater(row["差"], 0, "0.4パーセントのほうが手取りが少ない")

    # 6. 1日ちがいの段差。
    _checks.rounding(one_day_gap(1_200_000), 1_200_000,
                     "昭和36年4月1日と4月2日の差（年額120万円）")
    _checks.increases_with(one_day_gap, [600_000, 1_200_000, 1_800_000, 2_400_000],
                           "年額が上がったのに段差が大きくなっていない")

    _checks.unique_by(cohort_table(), lambda r: r["区分"], "区分")
    _checks.unique_by(delay_table(), lambda r: r["遅らせた月数"], "遅らせた月数")
    _checks.assumption_values(ASSUMPTIONS, name="tokurou")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 生まれた年で、65歳より前に受け取れる月数が階段状に消えていく（年額120万円）===")
    for row in cohort_table():
        print(f"  {row['区分']}")
        print(f"      男性 {row['男性の開始年齢']}歳開始 {row['男性の月数']:>3}か月"
              f" {row['男性の総額']:>10,.0f}円"
              f"   女性 {row['女性の開始年齢']}歳開始 {row['女性の月数']:>3}か月"
              f" {row['女性の総額']:>10,.0f}円")

    print("\n=== 同じ区分でも、女性は5年おくれの階段なのでここまで差が付く（年額120万円）===")
    for row in sex_gap_table():
        print(f"  男性 {row['男性の総額']:>10,.0f}円"
              f"  女性 {row['女性の総額']:>10,.0f}円"
              f"  差 {row['差']:>+11,.0f}円   {row['区分']}")

    print("\n=== 繰下げができないので、請求を遅らせた分はそのまま消える（年額120万円）===")
    for row in delay_table():
        print(f"  {row['遅らせた月数']:>2}か月遅らせる"
              f"  消える {row['受け取り損ねる額']:>10,.0f}円"
              f"  （もし繰下げができたなら年額は {row['繰下げなら増えていた年額']:>10,.0f}円"
              f" ＝ +{row['繰下げなら増えていた分']:>9,.0f}円 だった）")

    print("\n=== 気づくのが5年をこえると、こえた分だけ時効で消える（年額120万円）===")
    for row in timebar_table():
        print(f"  {row['気づくまでの月数']:>2}か月後に気づく"
              f"  本来 {row['本来の額']:>10,.0f}円"
              f"  時効で消える {row['時効で消える額']:>10,.0f}円"
              f"  取り返せる {row['まだ取り返せる額']:>10,.0f}円")

    print("\n=== 特別支給がある世代は、繰上げの減額率が全員0.5パーセントの側（年額120万円）===")
    for row in kuriage_table():
        print(f"  {row['繰り上げた月数']:>2}か月 繰り上げる"
              f"  0.5パーセントの世代 {row['0.5パーセントの世代']:>10,.0f}円"
              f"  0.4パーセントの世代 {row['0.4パーセントの世代']:>10,.0f}円"
              f"  差 {row['差']:>+10,.0f}円")

    print("\n=== 被保険者期間が11か月と12か月で、65歳前の総額が0円か120万円かに分かれる ===")
    for row in need_months_table():
        print(f"  {row['厚生年金の被保険者期間（月）']:>2}か月"
              f"  特別支給 {row['特別支給']}"
              f"  64歳開始なら65歳までに {row['64歳開始なら65歳までの総額']:>10,.0f}円"
              f"  65歳からの老齢厚生年金 {row['65歳からの老齢厚生年金']}")

    print("\n=== 昭和36年4月1日生まれと4月2日生まれ、1日ちがいで消える総額 ===")
    for row in annual_grid_table():
        print(f"  年額 {row['報酬比例部分の年額']:>9,}円"
              f"  64歳開始 {row['64歳開始の総額']:>10,.0f}円"
              f"  65歳開始 {row['65歳開始の総額']:>10,.0f}円"
              f"  → 消える {row['1日ちがいで消える総額']:>10,.0f}円")
