"""4月・5月・6月の報酬だけで、1年ぶんの厚生年金保険料が決まる（定時決定）。

**一般の解説は「4月から6月の残業を減らすと保険料が下がります」で止まります。**
その先に、口を開けている段が4つあります。

1つめ。**下がるかどうかは、等級の境目をまたぐかどうかだけで決まります。**
段の中でいくら減らしても、保険料は1円も動きません。

2つめ。**得か損かは、3か月の残業代と12か月の保険料を並べて初めて言えます。**
残業を減らせばその月の残業代も消えるので、**引き算をしないと向きが決まりません。**

3つめ。**その額に縛られるのは9月から翌年8月まで**です（健康保険法41条）。
4月の時点から数えると、**17か月**、その3か月の平均に縛られます。

4つめ。**払った保険料は年金にも効きます**（報酬比例部分・1000分の5.481）。
だから「保険料が増える」は片側しか見ていません。**何年で回収するか**が出せます。

この表が出す数字（実行して出たものを、丸めずに写しています）:

- 基本給300,000円の人が4〜6月に毎月30,000円 残業すると、標準報酬月額は
  300,000円から340,000円へ上がり、本人負担は月**31,110円**、
  1年で**43,920円**増えます
- そのとき受け取った残業代は3か月で**90,000円**。**差し引き46,080円のプラス**です
  ——「4〜6月の残業を減らせ」は、**この引き算をしていません**
- 毎月5,000円の残業なら標準報酬月額は300,000円のままで、保険料の増加は**0円**。
  残業代**15,000円**がまるごと残ります。**段の中は平ら**です
- **境目をまたいだ直後がいちばん損です。** 毎月10,000円の残業は
  残業代**30,000円**に対して保険料が**21,960円**増え、差し引きは**8,040円**。
  倍の20,000円 残業しても保険料は**21,960円**のままで、差し引きは**38,040円**になります
- 増えた保険料43,920円に対して、増える年金は年**2,631円**。**回収に16.7年**かかります
- 随時改定で2等級 動かすのに要る昇給額は等級で変わり、
  標準報酬月額88,000円の人は**16,000円**、380,000円の人は**60,000円**です
- 支払基礎日数17日未満の月が1つ外れると、平均は330,000円から**345,000円**へ上がります
  （外れるのは残業の無い月として置いています）
"""
from __future__ import annotations

from . import _checks
from .shahoken import BENEFIT_MULT, GRADES, HALF, bounds, grade_of, premium

# ---- 制度の値（健康保険法41条・42条、厚生年金保険法21条・23条）--------------

TARGET_MONTHS = (4, 5, 6)       # 定時決定で平均する月（4月・5月・6月）
APPLY_FROM_MONTH = 9            # 適用は9月から
APPLY_MONTHS = 12               # 翌年8月まで＝12か月
BASE_DAYS = 17                  # 支払基礎日数の下限（短時間労働者は11日）
KAITEI_GRADES = 2               # 随時改定に要る等級差（2等級以上）
KAITEI_MONTHS = 3               # その差が続く月数（3か月）
KAITEI_LAG = 1                  # 改定は4か月目から＝3か月＋1

ASSUMPTIONS = [
    "厚生年金の定時決定で計算しています。"
    "4月、5月、6月に受けた報酬の平均で標準報酬月額を決め、"
    "その年の9月から翌年8月までの12か月に使います",
    "平均に入るのは、支払基礎日数が17日以上の月だけです。"
    "短時間労働者は11日以上です",
    "保険料率は18.3パーセントで、本人負担はその半分の9.15パーセントです。"
    "2017年9月から動いていません",
    "標準報酬月額の等級は32段で、境目は隣り合う等級の中点に置いています",
    "随時改定は、固定的賃金が変わってからの3か月の平均が、"
    "いまの標準報酬月額と2等級以上ちがうときに、4か月目から行われます",
    "基本給と残業代は制度の値ではなく、この計算での仮定です。"
    "基本給300,000円、4月から6月の毎月の残業代0円から50,000円までを並べています",
    "増える年金は報酬比例部分だけで見ています。乗率は1000分の5.481です",
    "健康保険料と介護保険料は入れていません。入れると増え方はここより大きくなります",
    "賞与にかかる保険料は入れていません",
    "年金の改定や、受け取り始めるまでの物価の動きは入れていません",
]


def average_reward(base: float, overtime: float,
                   skipped_months: int = 0) -> float:
    """4〜6月の報酬の平均。`skipped_months` は支払基礎日数17日未満で外れた月数。

    **外れた月は分母からも分子からも消えます**（平均が残業のある月に寄ります）。
    ここでは「外れるのは残業の無い月」として置いています ——
    欠勤した月は残業もしていないのが普通なので、**平均は上がる向きに動きます。**
    """
    months = len(TARGET_MONTHS) - skipped_months
    if months <= 0:
        raise ValueError("3か月とも外れると定時決定はできない")
    total = base * months + overtime * months
    if skipped_months:
        total = base * months + overtime * len(TARGET_MONTHS)
    return total / months


def by_overtime(base: int = 300_000) -> list[dict]:
    """4〜6月の毎月の残業代べつに、9月からの1年の保険料。"""
    zero = premium(base) * APPLY_MONTHS
    rows = []
    for ot in (0, 5_000, 10_000, 20_000, 30_000, 50_000):
        monthly = int(average_reward(base, ot))
        year = premium(monthly) * APPLY_MONTHS
        rows.append({
            "毎月の残業代": ot,
            "4〜6月の平均報酬": monthly,
            "標準報酬月額": grade_of(monthly),
            "本人負担の月額": premium(monthly),
            "1年の本人負担": year,
            "残業0円のときとの差": year - zero,
        })
    return rows


def net_table(base: int = 300_000) -> list[dict]:
    """**引き算する。** 3か月ぶんの残業代と、12か月ぶんの保険料の増加を並べる。"""
    zero = premium(base) * APPLY_MONTHS
    rows = []
    for ot in (0, 5_000, 10_000, 20_000, 30_000, 50_000):
        monthly = int(average_reward(base, ot))
        extra = premium(monthly) * APPLY_MONTHS - zero
        got = ot * len(TARGET_MONTHS)
        rows.append({
            "毎月の残業代": ot,
            "3か月で受け取る残業代": got,
            "1年で増える保険料": extra,
            "差し引き": got - extra,
        })
    return rows


def skipped_table(base: int = 300_000, overtime: int = 30_000) -> list[dict]:
    """支払基礎日数17日未満の月が外れると、平均はどう動くか。"""
    rows = []
    for skipped in (0, 1, 2):
        monthly = int(average_reward(base, overtime, skipped))
        rows.append({
            "外れた月数": skipped,
            "平均に入る月数": len(TARGET_MONTHS) - skipped,
            "4〜6月の平均報酬": monthly,
            "標準報酬月額": grade_of(monthly),
            "本人負担の月額": premium(monthly),
        })
    return rows


def payback_table(base: int = 300_000) -> list[dict]:
    """増えた保険料と、増える年金。**何年で回収するか。**"""
    zero_std = grade_of(base)
    zero = premium(base) * APPLY_MONTHS
    rows = []
    for ot in (10_000, 20_000, 30_000, 40_000, 50_000):
        monthly = int(average_reward(base, ot))
        std = grade_of(monthly)
        extra = premium(monthly) * APPLY_MONTHS - zero
        # 標準報酬月額が上がったぶん、その1年ぶんの報酬比例部分が増える
        gain = (std - zero_std) * APPLY_MONTHS * BENEFIT_MULT
        rows.append({
            "毎月の残業代": ot,
            "1年で増える保険料": extra,
            "増える年金の年額": round(gain),
            "回収にかかる年数": round(extra / gain, 1) if gain else None,
        })
    return rows


def lock_months() -> list[dict]:
    """4〜6月の報酬に縛られる長さ。**4月から数えると最長17か月。**"""
    rows = []
    for month in TARGET_MONTHS:
        wait = APPLY_FROM_MONTH - month
        rows.append({
            "その月": month,
            "適用が始まるまでの月数": wait,
            "適用される月数": APPLY_MONTHS,
            "その月から数えた縛り": wait + APPLY_MONTHS,
        })
    return rows


def kaitei_gap(std: int) -> int | None:
    """随時改定に要る「2等級 上」までの報酬の増え方（円）。上限の等級は None。"""
    i = GRADES.index(std)
    if i + KAITEI_GRADES >= len(GRADES):
        return None
    return GRADES[i + KAITEI_GRADES] - std


def kaitei_table() -> list[dict]:
    """等級べつに、随時改定が起きるまでに要る昇給額。**段の幅で変わる。**"""
    rows = []
    for std in (88_000, 150_000, 200_000, 260_000, 300_000, 380_000, 500_000):
        i = GRADES.index(std)
        low, _ = bounds(i + KAITEI_GRADES)
        gap = kaitei_gap(std)
        rows.append({
            "いまの標準報酬月額": std,
            "2等級 上の標準報酬月額": GRADES[i + KAITEI_GRADES],
            "2等級 上との差": gap,
            "そこに届く報酬月額の下限": low,
            "改定が効くまでの月数": KAITEI_MONTHS + KAITEI_LAG,
        })
    return rows


def grid() -> list[dict]:
    """図解の元になる表。"""
    return by_overtime()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""

    # 1. 法令が名指ししている値
    _checks.statutory(BASE_DAYS, 17, "支払基礎日数の下限",
                      source="健康保険法41条・厚生年金保険法21条")
    _checks.statutory(APPLY_FROM_MONTH, 9, "定時決定の適用開始月",
                      source="健康保険法41条")
    _checks.statutory(APPLY_MONTHS, 12, "定時決定の適用月数",
                      source="9月から翌年8月まで")
    _checks.statutory(KAITEI_GRADES, 2, "随時改定に要る等級差",
                      source="健康保険法43条・厚生年金保険法23条")
    _checks.statutory(KAITEI_MONTHS, 3, "随時改定に要る月数",
                      source="健康保険法43条・厚生年金保険法23条")
    _checks.statutory(HALF, 0.183 / 2, "本人負担の保険料率",
                      source="厚生年金保険法81条（2017年9月から18.3%で固定）")
    _checks.ratio(HALF, "本人負担の保険料率")

    # 2. **主題その1**: 段の中では動かない。残業10,000円では等級が上がらない。
    small = next(r for r in by_overtime() if r["毎月の残業代"] == 5_000)
    _checks.rounding(small["残業0円のときとの差"], 0,
                     "毎月5,000円の残業で増える1年の保険料")
    _checks.rounding(small["標準報酬月額"], grade_of(300_000),
                     "毎月5,000円の残業のときの標準報酬月額")

    # 3. **主題その2**: それでも、いつかは段をまたぐ。
    big = next(r for r in by_overtime() if r["毎月の残業代"] == 30_000)
    _checks.greater(big["残業0円のときとの差"], 0,
                    "毎月30,000円の残業で保険料が1円も増えていない")
    _checks.increases_with(lambda o: premium(int(average_reward(300_000, o))),
                           [0, 20_000, 40_000, 60_000],
                           "残業が増えたのに保険料が増えていない")

    # 4. **主題その3**: 引き算すると、残業したほうが得（この前提では）。
    for row in net_table():
        if row["毎月の残業代"] == 0:
            continue
        _checks.greater(row["差し引き"], 0,
                        f"残業{row['毎月の残業代']}円で差し引きがマイナス"
                        f"（この前提では残業代のほうが大きいはず）")
    net30 = next(r for r in net_table() if r["毎月の残業代"] == 30_000)
    _checks.rounding(net30["3か月で受け取る残業代"], 90_000,
                     "毎月30,000円を3か月ぶん")

    # 5. **主題その4**: 縛りは4月から数えて17か月。
    april = next(r for r in lock_months() if r["その月"] == 4)
    _checks.rounding(april["その月から数えた縛り"], 17,
                     "4月から数えた縛りの月数")
    _checks.decreases_with(lambda m: (APPLY_FROM_MONTH - m) + APPLY_MONTHS,
                           [4, 5, 6], "月が後になるのに縛りが短くなっていない")

    # 6. **主題その5**: 随時改定に要る昇給額は、段の幅で変わる。
    _checks.rounding(kaitei_gap(300_000), 40_000,
                     "標準報酬月額300,000円から2等級 上までの差")
    _checks.rounding(kaitei_gap(88_000), 16_000,
                     "標準報酬月額88,000円から2等級 上までの差")
    _checks.greater(kaitei_gap(300_000), kaitei_gap(88_000),
                    "高い等級のほうが2等級ぶんの幅が狭い（段は上ほど広いはず）")

    # 7. 外れた月があると平均は上がる（この置き方では）。
    _checks.increases_with(
        lambda s: average_reward(300_000, 30_000, s), [0, 1, 2],
        "外れた月が増えたのに平均が上がっていない")

    # 8. 回収年数は、増える年金がある限り有限であること。
    for row in payback_table():
        if row["1年で増える保険料"] == 0:
            _checks.rounding(row["増える年金の年額"], 0,
                             "保険料が増えていないのに年金が増えている")
            continue
        _checks.greater(row["回収にかかる年数"], 0, "回収年数が0以下")

    _checks.unique_by(by_overtime(), lambda r: r["毎月の残業代"], "毎月の残業代")
    _checks.unique_by(kaitei_table(), lambda r: r["いまの標準報酬月額"],
                      "いまの標準報酬月額")
    _checks.assumption_values(ASSUMPTIONS, name="teiji")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 4月から6月の残業代べつに、9月からの1年の厚生年金保険料 ===")
    for row in by_overtime():
        print(row)

    print("\n=== 引き算する。3か月の残業代と、12か月ぶんの保険料の増加 ===")
    for row in net_table():
        print(row)

    print("\n=== 支払基礎日数17日未満の月が外れると、平均は上がる ===")
    for row in skipped_table():
        print(row)

    print("\n=== 増えた保険料は年金にも効く。回収に何年かかるか ===")
    for row in payback_table():
        print(row)

    print("\n=== 4月から6月の報酬に縛られるのは、最長17か月 ===")
    for row in lock_months():
        print(row)

    print("\n=== 随時改定の2等級。要る昇給額は16,000円から60,000円まで動く ===")
    for row in kaitei_table():
        print(row)
