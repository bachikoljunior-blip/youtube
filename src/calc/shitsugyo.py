"""失業給付（雇用保険の基本手当）の「境界」がいくらの価値になるかを計算する。

狙いは制度の解説ではない。所定給付日数の表はどこにでもある。
ここで出したいのは **どこにも表になっていない数字** ——
「あと1日で区分をまたぐとき、その1日にいくらの価値があるのか」を、
すべての境界について並べた表。

--------------------------------------------------------------------------
なぜこの題材か（2026-08-04 時点）
--------------------------------------------------------------------------
基本手当日額の上限額・下限額は **毎年8月1日に改定される**。
直近の改定は令和8年8月1日で、この計算はその新しい値で行っている。
去年の値で書かれた記事は、この日を境に全部ずれている。

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
雇用保険法 22条・23条  所定給付日数。年齢と算定基礎期間で決まる。
                       倒産・解雇等（特定受給資格者等）は別表で優遇される。
厚生労働省 令和8年8月1日改定  基本手当日額の上限額（年齢別）と下限額。

--------------------------------------------------------------------------
この計算で「使わない」もの
--------------------------------------------------------------------------
賃金日額から基本手当日額を出す給付率（賃金日額の区分で 80%〜45% に変わる）は、
区分の境目まで裏を取れていないので **使わない**。
代わりに、確定している上限額と下限額で挟んで「いくらから、いくらまで」と出す。
裏の取れない数字を動画に入れないための設計上の判断であり、
結果として「自分がどこに当てはまるか」も視聴者が判断しやすくなる。
"""
from __future__ import annotations

# 動画と説明欄にそのまま出す前提。
ASSUMPTIONS = [
    "所定給付日数は雇用保険法22条・23条の別表どおりに置いています",
    "基本手当日額は令和8年8月1日改定の上限額と下限額を使っています",
    "金額は下限額と上限額で挟んだ幅で出しています。実際の額は賃金日額で決まります",
    "給付制限期間・受給期間の延長・給付日数の延長は考慮していません",
    "就職困難者に該当する場合は別の表になるため、この計算の対象外です",
]

# 令和8年8月1日改定。年齢は離職日時点。
DAILY_CAP = {
    "30歳未満": 7450,
    "30歳以上45歳未満": 8270,
    "45歳以上60歳未満": 9110,
    "60歳以上65歳未満": 7830,
}
DAILY_FLOOR = 2562  # 全年齢共通

TENURE_BANDS = ["1年未満", "1年以上5年未満", "5年以上10年未満", "10年以上20年未満", "20年以上"]

# 自己都合・定年など。年齢に関係なく同じ。None は受給資格が無いか該当なし。
DAYS_GENERAL = {
    "1年未満": None,
    "1年以上5年未満": 90,
    "5年以上10年未満": 90,
    "10年以上20年未満": 120,
    "20年以上": 150,
}

# 倒産・解雇など（特定受給資格者および一部の特定理由離職者）。
DAYS_INVOLUNTARY = {
    "30歳未満":          {"1年未満": 90, "1年以上5年未満": 90,  "5年以上10年未満": 120, "10年以上20年未満": 180, "20年以上": None},
    "30歳以上45歳未満":  {"1年未満": 90, "1年以上5年未満": 120, "5年以上10年未満": 180, "10年以上20年未満": 210, "20年以上": 240},
    "45歳以上60歳未満":  {"1年未満": 90, "1年以上5年未満": 180, "5年以上10年未満": 240, "10年以上20年未満": 270, "20年以上": 330},
    "60歳以上65歳未満":  {"1年未満": 90, "1年以上5年未満": 150, "5年以上10年未満": 180, "10年以上20年未満": 210, "20年以上": 240},
}


class TableError(AssertionError):
    """表そのものが壊れている。数字を出す前にここで止める。"""


def check_tables() -> None:
    """表が壊れていないことを、性質から確かめる。

    公表資料の読み取りは列がずれることがある（実際に一度ずれた）。
    ずれた表は「もっともらしい数字」を出してしまい、目視では気づけない。
    だから、表が満たすべき性質を書いて、破れたらここで落とす。
    """
    for age, row in DAYS_INVOLUNTARY.items():
        if set(row) != set(TENURE_BANDS):
            raise TableError(f"{age} の期間区分が表と違います")

        # 1. 期間が長くなって日数が減ることはない
        seen = [row[b] for b in TENURE_BANDS if row[b] is not None]
        if seen != sorted(seen):
            raise TableError(f"{age} の日数が期間に対して単調でありません: {seen}")

        # 2. 30歳未満に「20年以上」は存在しない。それ以外には存在する
        if age == "30歳未満":
            if row["20年以上"] is not None:
                raise TableError("30歳未満に20年以上の区分があります")
        elif row["20年以上"] is None:
            raise TableError(f"{age} の20年以上が欠けています")

        # 3. 倒産・解雇のほうが自己都合より少ないことはない
        for band in TENURE_BANDS:
            general, involuntary = DAYS_GENERAL[band], row[band]
            if general is None or involuntary is None:
                continue
            if involuntary < general:
                raise TableError(f"{age} {band}: 倒産・解雇が自己都合より少ない")

        # 4. 法定の範囲
        for band, days in row.items():
            if days is not None and not 90 <= days <= 330:
                raise TableError(f"{age} {band}: {days}日は法定の範囲外")

    # 5. 自己都合は1年未満だと受給資格が無い
    if DAYS_GENERAL["1年未満"] is not None:
        raise TableError("自己都合の1年未満に日数が入っています")

    # 6. 上限額は下限額より大きい
    for age, cap in DAILY_CAP.items():
        if cap <= DAILY_FLOOR:
            raise TableError(f"{age} の上限額が下限額以下です")


def yen_range(days: int, age: str) -> tuple[int, int]:
    """日数を、下限額と上限額で挟んだ金額の幅にする。"""
    return days * DAILY_FLOOR, days * DAILY_CAP[age]


def tenure_boundaries(age: str) -> list[dict]:
    """勤続年数の境界。あと少し在籍していたら何日増えたか。"""
    check_tables()
    out = []
    for reason, table in (("自己都合など", DAYS_GENERAL), ("倒産・解雇など", DAYS_INVOLUNTARY[age])):
        for before, after in zip(TENURE_BANDS, TENURE_BANDS[1:]):
            a, b = table[before], table[after]
            if a is None or b is None or b == a:
                continue
            lo, hi = yen_range(b - a, age)
            out.append({
                "reason": reason,
                "boundary": after.replace("以上", "").split("年")[0] + "年",
                "days_before": a,
                "days_after": b,
                "days_gained": b - a,
                "yen_low": lo,
                "yen_high": hi,
            })
    return out


def reason_boundary(age: str) -> list[dict]:
    """離職理由の境界。同じ勤続年数で、自己都合と倒産・解雇でどれだけ違うか。"""
    check_tables()
    out = []
    for band in TENURE_BANDS:
        a, b = DAYS_GENERAL[band], DAYS_INVOLUNTARY[age][band]
        if a is None or b is None or b == a:
            continue
        lo, hi = yen_range(b - a, age)
        out.append({
            "band": band,
            "days_self": a,
            "days_involuntary": b,
            "days_gained": b - a,
            "yen_low": lo,
            "yen_high": hi,
        })
    return out


def age_boundaries(band: str) -> list[dict]:
    """年齢の境界。誕生日を挟むと何日変わるか（倒産・解雇の場合）。"""
    check_tables()
    ages = list(DAILY_CAP)
    out = []
    for before, after in zip(ages, ages[1:]):
        a, b = DAYS_INVOLUNTARY[before][band], DAYS_INVOLUNTARY[after][band]
        if a is None or b is None or b == a:
            continue
        lo, hi = yen_range(abs(b - a), after if b > a else before)
        out.append({
            "band": band,
            "from_age": before,
            "to_age": after,
            "days_before": a,
            "days_after": b,
            "days_gained": b - a,
            "yen_low": lo,
            "yen_high": hi,
        })
    return out
