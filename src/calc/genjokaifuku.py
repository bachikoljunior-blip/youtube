"""賃貸を出るときの原状回復を、月ごとに解いて実額を出す。

    python -m src.calc.genjokaifuku

## この計算で出したいこと

原状回復の解説は「クロスの耐用年数は6年」「6年住めば負担はゼロ」で止まる。
**その6年の途中にいる人が、いくら払うことになるのかは、どこにも出ていない。**
割合だけ書いてあっても、実際に引かれるのは**割合 × 単価 × 面積**なので、
そこまで置かないと金額にならない。

ここで解くと、次の5つが出る。

1. **3年住んだ人のクロスの負担は 12,000円。** 6年で価値が1円まで下がる直線なので、
   ちょうど半分の 0.5 が残る。同じ部屋でも入居直後なら 24,000円 で、**2倍ちがう。**
2. **直線なので、1か月ごとに 333円 ずつ減る。** どの月でも同じ額で、
   住んだ月数が 0・6・12・18…と進むと 24,000円 → 22,000円 → 20,000円 → 18,000円。
   **1年 早く出ると 4,000円 高い。**
3. **同じ3年でも、耐用年数が5年なら 9,600円、15年なら 19,200円。**
   割合は 0.4 と 0.8 で、**長持ちするものほど、途中で出たときの負担が重い。**
   クロスの6年（0.5・12,000円）はその真ん中にある。
4. **負担が半分になるのは 36か月目**、4分の1になるのは **54か月目**。
   直線なので、耐用年数のちょうど半分・4分の3で割るだけ。
5. **敷金2か月 160,000円 のうち、1年で出ると 140,000円、3年なら 148,000円、
   6年なら 160,000円 が返る。** 差額の 20,000円 は、
   **住んだ年数だけで決まっていて、部屋の使い方では動かない。**

## 前提（動画にそのまま出すこと）

- 国土交通省「原状回復をめぐるトラブルとガイドライン」の考え方。
  通常の使い方でついた傷みと経年変化は、借りた人の負担に入れない（民法621条）
- 壁のクロスの耐用年数は6年。6年で価値が1円まで下がる直線として置く
- 単価は1平方メートルあたり 1,000〜2,000円（代表 1,200円）、
  面積は 6〜30平方メートル（代表 20平方メートル）。**どちらも仮定**
- 敷金は家賃80,000円の1〜3か月分。代表は2か月分の160,000円
- クリーニングの特約・鍵の交換代・未払い分は入れていない。
  特約があると、実際に引かれる額はここより大きくなることがある

## 根拠の探し方（動画の説明欄用。URLは書かない）

- 耐用年数6年と、残存価値1円までの直線 … 国土交通省
  「原状回復をめぐるトラブルとガイドライン」の経過年数の考え方
- 通常損耗・経年変化が原状回復に含まれないこと … 民法621条
- 敷金を賃貸借の終了時に返すこと … 民法622条の2
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値。**長く動いていないものだけをここに置く** ----------------
#
# 壁のクロスの耐用年数。国土交通省「原状回復をめぐるトラブルとガイドライン」が
# **6年**と置いている。6年を過ぎると、入居者の負担割合はゼロに近づく。
CLOTH_LIFE_YEARS = 6

# 耐用年数を過ぎた時点で残る価値。ガイドラインは**1円**まで直線で下げる。
RESIDUAL_YEN = 1

# 敷金は賃貸借が終わったときに返す（民法622条の2）。
# 通常の使用でついた傷みと経年変化は、原状回復の義務に入らない（民法621条）。

ASSUMPTIONS = [
    "賃貸住宅を出るときの原状回復で計算しています。"
    "国土交通省の原状回復をめぐるトラブルとガイドラインの考え方に沿っています",
    "通常の使い方でついた傷みと経年変化は、借りた人の負担に入れていません。"
    "負担に入れているのは、借りた人の側に原因がある傷みだけです",
    "壁のクロスの耐用年数は6年としています。"
    "6年で価値が1円まで下がる直線として置いています",
    "耐用年数は、ほかの部分では6年ではありません。"
    "ここでは5年から15年までを並べて、年数がちがうと負担がどう変わるかを出しています",
    "クロスの単価は制度の値ではなく、この計算での仮定です。"
    "1平方メートルあたり1,000円から2,000円までを並べ、"
    "代表として1,200円を使っています",
    "張り替える面積も仮定です。6平方メートルから30平方メートルまでを並べ、"
    "代表として20平方メートルを使っています",
    "敷金は家賃の1か月分から3か月分までを並べ、"
    "家賃80,000円、敷金2か月分の160,000円を代表として使っています",
    "経過年数は月きざみで数えています。日割りは入れていません",
    "クリーニング代の特約、鍵の交換代、原状回復以外の未払い分は入れていません。"
    "特約があると、実際に引かれる額はここに出る額より大きくなることがあります",
]


# ---- 計算 --------------------------------------------------------------
def burden_ratio(months: int, life_years: int = CLOTH_LIFE_YEARS) -> float:
    """入居した月数から、借りた人の負担割合。**直線で下がり、0で止まる。**"""
    life_months = life_years * 12
    return max(1.0 - months / life_months, 0.0)


def burden_yen(months: int, unit_price: float = 1_200, area: float = 20,
               life_years: int = CLOTH_LIFE_YEARS) -> float:
    """負担額。**割合 × 単価 × 面積**。"""
    return burden_ratio(months, life_years) * unit_price * area


def by_years(unit_price: float = 1_200, area: float = 20,
             life_years: int = CLOTH_LIFE_YEARS) -> list[dict]:
    """住んだ年数べつに、クロスの負担割合と負担額。"""
    rows = []
    for years in (0, 1, 2, 3, 4, 5, 6, 7):
        months = years * 12
        rows.append({
            "住んだ年数": years,
            "負担割合": round(burden_ratio(months, life_years), 4),
            "負担額": round(burden_yen(months, unit_price, area, life_years)),
        })
    return rows


def by_month(unit_price: float = 1_200, area: float = 20,
             life_years: int = CLOTH_LIFE_YEARS) -> list[dict]:
    """月きざみ。**1か月で負担額がいくら減るか。**"""
    rows = []
    step = 6
    for months in range(0, life_years * 12 + 1, step):
        rows.append({
            "住んだ月数": months,
            "負担割合": round(burden_ratio(months, life_years), 4),
            "負担額": round(burden_yen(months, unit_price, area, life_years)),
            "1か月あたり減る額": round(unit_price * area / (life_years * 12)),
        })
    return rows


def by_life(months: int = 36, unit_price: float = 1_200,
            area: float = 20) -> list[dict]:
    """耐用年数べつに、**同じ3年住んだ人**の負担割合。"""
    rows = []
    for life in (5, 6, 8, 10, 15):
        rows.append({
            "耐用年数": life,
            "負担割合": round(burden_ratio(months, life), 4),
            "負担額": round(burden_yen(months, unit_price, area, life)),
        })
    return rows


def by_area(months: int = 36, unit_price: float = 1_200,
            life_years: int = CLOTH_LIFE_YEARS) -> list[dict]:
    """張り替える面積べつに、負担額。"""
    rows = []
    for area in (6, 10, 15, 20, 25, 30):
        rows.append({
            "面積": area,
            "負担額": round(burden_yen(months, unit_price, area, life_years)),
            "6年住んだ場合": round(
                burden_yen(life_years * 12, unit_price, area, life_years)),
        })
    return rows


def by_unit_price(months: int = 36, area: float = 20,
                  life_years: int = CLOTH_LIFE_YEARS) -> list[dict]:
    """単価べつに、負担額。"""
    rows = []
    for unit in (1_000, 1_200, 1_500, 1_800, 2_000):
        rows.append({
            "1平方メートルの単価": unit,
            "負担額": round(burden_yen(months, unit, area, life_years)),
        })
    return rows


def deposit_table(rent: float = 80_000, unit_price: float = 1_200,
                  area: float = 20,
                  life_years: int = CLOTH_LIFE_YEARS) -> list[dict]:
    """敷金の月数べつに、住んだ年数で返ってくる額がどう変わるか。"""
    rows = []
    for m in (1, 2, 3):
        deposit = rent * m
        row = {"敷金の月数": m, "敷金": int(deposit)}
        for years in (1, 3, 6):
            burden = burden_yen(years * 12, unit_price, area, life_years)
            row[f"{years}年で返る額"] = round(max(deposit - burden, 0.0))
        rows.append(row)
    return rows


def half_point(life_years: int = CLOTH_LIFE_YEARS) -> list[dict]:
    """負担が半分・4分の1になるのは何か月目か。**直線なので割るだけ。**"""
    life_months = life_years * 12
    rows = []
    for ratio in (1.0, 0.75, 0.5, 0.25, 0.0):
        months = round(life_months * (1 - ratio))
        rows.append({
            "負担割合": round(ratio, 4),
            "その月数": months,
            "年でいうと": round(months / 12, 2),
        })
    return rows


def grid() -> list[dict]:
    """図解の元になる表。"""
    return by_years()


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""

    # 1. 公表資料が名指ししている値
    _checks.statutory(CLOTH_LIFE_YEARS, 6, "壁のクロスの耐用年数",
                      source="国土交通省 原状回復をめぐるトラブルとガイドライン")
    _checks.statutory(RESIDUAL_YEN, 1, "耐用年数を過ぎた時点の残存価値",
                      source="国土交通省 原状回復をめぐるトラブルとガイドライン")

    # 2. **主題その1**: 負担割合は直線で下がり、耐用年数でゼロに着く。
    _checks.rounding(round(burden_ratio(0), 4), 1.0, "入居直後の負担割合")
    _checks.rounding(round(burden_ratio(CLOTH_LIFE_YEARS * 12), 4), 0.0,
                     "6年ちょうどの負担割合")
    _checks.rounding(round(burden_ratio(CLOTH_LIFE_YEARS * 12 + 24), 4), 0.0,
                     "6年を超えた人の負担割合（0で止まるはず）")
    _checks.decreases_with(lambda m: burden_ratio(m), [0, 12, 24, 36, 48, 60],
                           "住んだ月数が増えたのに負担割合が減っていない")

    # 3. **主題その2**: 直線なので、1か月で減る額はどの月でも同じ。
    rows = by_month()
    steps = [rows[i]["負担額"] - rows[i + 1]["負担額"]
             for i in range(len(rows) - 1)]
    _checks.rounding(len(set(steps)), 1,
                     "1か月あたり減る額が月によって違う（直線のはず）")

    # 4. **主題その3**: 耐用年数が長いほど、同じ年数住んだ人の負担は重い。
    _checks.increases_with(lambda life: burden_ratio(36, life),
                           [5, 6, 8, 10, 15],
                           "耐用年数が長いのに負担割合が増えていない")
    _checks.rounding(round(burden_ratio(36, 5), 4), 0.4,
                     "耐用年数5年の部屋に3年住んだ人の負担割合")
    _checks.rounding(round(burden_ratio(36, 6), 4), 0.5,
                     "耐用年数6年の部屋に3年住んだ人の負担割合")
    _checks.greater(burden_ratio(36, 15), burden_ratio(36, 6),
                    "耐用年数15年の負担が6年以下")

    # 5. **主題その4**: 面積と単価には比例する。
    _checks.increases_with(lambda a: burden_yen(36, 1_200, a),
                           [6, 10, 20, 30],
                           "面積が増えたのに負担額が増えていない")
    _checks.increases_with(lambda u: burden_yen(36, u, 20),
                           [1_000, 1_500, 2_000],
                           "単価が上がったのに負担額が増えていない")

    # 6. **主題その5**: 敷金から引くので、長く住むほど返る額は増える。
    dep = deposit_table()
    for row in dep:
        _checks.greater(row["6年で返る額"] + 1, row["3年で返る額"],
                        "6年 住んだ人の返る額が3年の人より少ない")
        _checks.greater(row["3年で返る額"] + 1, row["1年で返る額"],
                        "3年 住んだ人の返る額が1年の人より少ない")

    # 7. 半分になる点は、耐用年数のちょうど半分。
    half = next(r for r in half_point() if r["負担割合"] == 0.5)
    _checks.rounding(half["その月数"], CLOTH_LIFE_YEARS * 12 // 2,
                     "負担が半分になる月数")

    _checks.unique_by(by_years(), lambda r: r["住んだ年数"], "住んだ年数")
    _checks.unique_by(by_life(), lambda r: r["耐用年数"], "耐用年数")
    _checks.unique_by(by_area(), lambda r: r["面積"], "面積")
    _checks.assumption_values(ASSUMPTIONS, name="genjokaifuku")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 住んだ年数べつに、クロスの原状回復はいくら負担するか ===")
    for row in by_years():
        print(row)

    print("\n=== 直線なので、1か月ごとに同じ額だけ負担が減っていく ===")
    for row in by_month():
        print(row)

    print("\n=== 耐用年数がちがうと、同じ3年住んだ人の負担はどう変わるか ===")
    for row in by_life():
        print(row)

    print("\n=== 張り替える面積べつに、3年住んだ人の負担額 ===")
    for row in by_area():
        print(row)

    print("\n=== クロスの単価べつに、3年住んだ人の負担額 ===")
    for row in by_unit_price():
        print(row)

    print("\n=== 敷金の月数べつに、何年住むと いくら返ってくるか ===")
    for row in deposit_table():
        print(row)

    print("\n=== 負担が半分・4分の1になるのは、何か月目か ===")
    for row in half_point():
        print(row)
