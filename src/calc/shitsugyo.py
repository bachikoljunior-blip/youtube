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
    "基本手当日額の上限額は45歳以上60歳未満が9110円、60歳以上65歳未満が7830円です。"
    "下限額は2562円で全年齢共通です",
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

    # 7. **60歳の境目で上限額が下がること**（`age_cap_cliff()` の主題そのもの）。
    #    ここが上がる表に差し替わったら、あの節の答えは逆になります。**黙って逆を
    #    出させないために書いています**（毎年8月1日改定なので、いつか動きます）。
    if DAILY_CAP["60歳以上65歳未満"] >= DAILY_CAP["45歳以上60歳未満"]:
        raise TableError(
            "60歳以上の上限額が45歳以上60歳未満を下回っていません。"
            "改定で向きが変わったなら age_cap_cliff() の文言ごと見直すこと")


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


def age_cap_cliff(reason: str = "倒産・解雇など") -> list[dict]:
    """**60歳の誕生日をまたぐと、上限額そのものが下がる。**

    上の `age_boundaries()` が見ているのは**日数だけ**です。ところが 60歳の境目では
    `DAILY_CAP` も 9,110円 → 7,830円 と **1,280円下がります**（令和8年8月1日改定）。
    日数と単価が同じ向きに動くので、**総額の落ち込みは日数だけで見たより深い。**

    実測（倒産・解雇、上限額に当たる人）:

        20年以上   330日→240日   3,006,300円→1,879,200円   **−1,127,100円**
                   日数だけで見ると −819,900円 ＝ **30万7200円ぶん浅く見えていた**
        1年未満     90日→ 90日     819,900円→  704,700円   **−115,200円**
                   日数は1日も変わらないので、`age_boundaries()` は**この行を落とします**

    **下限額に当たる人には、この段差はありません**（`DAILY_FLOOR` は全年齢共通）。
    だから幅で出します —— 段差は「上限に当たる人ほど深い」という形の答えになります。
    """
    check_tables()
    before, after = "45歳以上60歳未満", "60歳以上65歳未満"
    table = DAYS_INVOLUNTARY if reason == "倒産・解雇など" else None
    out = []
    for band in TENURE_BANDS:
        if table is None:
            d_before = d_after = DAYS_GENERAL[band]
        else:
            d_before, d_after = table[before][band], table[after][band]
        if d_before is None or d_after is None:
            continue
        out.append({
            "band": band,
            "days_before": d_before,
            "days_after": d_after,
            "days_gained": d_after - d_before,
            # 上限額に当たる人。**単価が下がるので、日数の差だけでは足りない**
            "cap_yen_before": d_before * DAILY_CAP[before],
            "cap_yen_after": d_after * DAILY_CAP[after],
            "cap_yen_gained": d_after * DAILY_CAP[after] - d_before * DAILY_CAP[before],
            # 日数だけで見たとき（＝`age_boundaries()` の見え方）。差が「浅く見えた幅」
            "days_only_yen": (d_after - d_before) * DAILY_CAP[before],
            # 下限額に当たる人。単価は変わらないので日数ぶんだけ
            "floor_yen_gained": (d_after - d_before) * DAILY_FLOOR,
        })
    return out


if __name__ == "__main__":
    # **ここが無かった（2026-08-05 に発覚）。** kojo・zangyo と同じ穴。
    # 標準出力が空のまま台本を書かせると、数字を発明させることになる。
    check_tables()
    print("制度の値の検査: 通過")

    for age in DAILY_CAP:
        print(f"\n=== {age} / 勤続年数の境界（あと少し在籍していたら） ===")
        print(f"{'離職理由':>12s} {'境界':>6s} {'前':>4s} {'後':>4s} {'増える日数':>6s} {'金額の幅':>20s}")
        for r in tenure_boundaries(age):
            print(f"{r['reason']:>12s} {r['boundary']:>6s} {r['days_before']:3d}日 "
                  f"{r['days_after']:3d}日 {r['days_gained']:5d}日 "
                  f"{r['yen_low']:9,d}円〜{r['yen_high']:9,d}円")

        print(f"\n=== {age} / 離職理由の境界（同じ勤続年数で自己都合と倒産・解雇） ===")
        for r in reason_boundary(age):
            print("  " + " ".join(f"{k}={v}" for k, v in r.items()))

    print("\n=== 年齢の境界（倒産・解雇の場合） ===")
    for band in TENURE_BANDS:
        for r in age_boundaries(band):
            print("  " + " ".join(f"{k}={v}" for k, v in r.items()))

    print("\n=== 60歳の誕生日で上限額が下がる分（倒産・解雇） ===")
    print(f"  上限額 {DAILY_CAP['45歳以上60歳未満']:,d}円 → "
          f"{DAILY_CAP['60歳以上65歳未満']:,d}円（"
          f"{DAILY_CAP['45歳以上60歳未満'] - DAILY_CAP['60歳以上65歳未満']:,d}円下がる）")
    print(f"  下限額 {DAILY_FLOOR:,d}円 は全年齢で同じ（下限に当たる人に段差はありません）")
    print(f"{'勤続':>16s} {'前':>5s} {'後':>5s} {'上限の人の総額':>26s} "
          f"{'差':>12s} {'日数だけで見た差':>14s} {'下限の人の差':>12s}")
    for r in age_cap_cliff():
        print(f"{r['band']:>16s} {r['days_before']:4d}日 {r['days_after']:4d}日 "
              f"{r['cap_yen_before']:11,d}円→{r['cap_yen_after']:11,d}円 "
              f"{r['cap_yen_gained']:11,d}円 {r['days_only_yen']:13,d}円 "
              f"{r['floor_yen_gained']:11,d}円")
