"""高額療養費（70歳未満）。**限度額の式に出てくる3つの数は、偶然ではありません。**

`252,600 + (医療費 − 842,000) × 1%` の **842,000** は、
**3割負担がちょうど 252,600円 になる医療費**です（842,000 × 0.3 = 252,600）。
区分イの 558,000 も、区分ウの 267,000 も同じ形で、
**どの区分でも「3割で払う額と定額がぴったり一致する点」から1%刻みが始まります。**
一般の解説は「80,100円＋1%」と式を写すところで止まり、
**この3つの数が何なのかを言いません。**

そこから出てくる、公表されていない数字:

- 区分ウ・医療費100万円で自己負担 **87,430円**。3割なら30万円なので **212,570円** ちがう
- **標準報酬月額 50万円と53万円**（月給3万円の差）で、
  医療費100万円のときの自己負担は **87,430円 対 171,820円 ＝ 84,390円**ちがう
- 医療費60万円を**1か月にまとめる**と 83,430円、**月をまたいで30万円ずつ**にすると
  160,860円。**同じ治療で 77,430円**ちがう（限度額は月ごとにかかる）
- 医療費が増えるほど**実効の負担率は下がる**。1,000万円なら **1.77%**
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値（健康保険法施行令42条。2015年1月から動いていない）------------
# (区分, 標準報酬月額の下限, 標準報酬月額の上限, 定額, 差引く医療費, 率, 多数回該当)
TIERS: list[tuple[str, int | None, int | None, int, int | None, float, int]] = [
    ("ア", 830_000, None, 252_600, 842_000, 0.01, 140_100),
    ("イ", 530_000, 790_000, 167_400, 558_000, 0.01, 93_000),
    ("ウ", 280_000, 500_000, 80_100, 267_000, 0.01, 44_400),
    ("エ", None, 260_000, 57_600, None, 0.0, 44_400),
    ("オ", None, None, 35_400, None, 0.0, 24_600),
]
COPAY_RATE = 0.3          # 70歳未満の窓口負担（健康保険法74条1項1号）
MULTI_HIT_FROM = 4        # 直近12か月で4回目から多数回該当（施行令41条）
HOUSEHOLD_FLOOR = 21_000  # 世帯合算に入れられる自己負担の下限（70歳未満・施行令41条）

ASSUMPTIONS = [
    "70歳未満・健康保険の被保険者本人として計算しています。70歳以上は別の表です",
    "窓口の負担割合は3割です。義務教育就学前と70歳以上は割合が違います",
    "区分は標準報酬月額で決まります。区分ウは28万円から50万円までです",
    "医療費は同じ月・同じ医療機関の保険がきく分だけの合計です。"
    "入院中の食事代・差額ベッド代・先進医療は入れていません",
    "多数回該当は直近12か月に3回あった場合の4回目からとして計算しています",
    "月をまたぐ計算では、限度額が月ごとに1回ずつかかるものとしています",
]


def tier(name: str) -> tuple[str, int | None, int | None, int, int | None, float, int]:
    for row in TIERS:
        if row[0] == name:
            return row
    raise ValueError(f"知らない区分: {name}")


def limit(name: str, cost: float) -> float:
    """その月の自己負担限度額。**医療費の総額（10割）を渡すこと。**"""
    _, _, _, flat, floor, rate, _ = tier(name)
    if floor is None:
        return float(flat)
    return flat + max(0.0, cost - floor) * rate


def paid(name: str, cost: float) -> float:
    """実際に払う額。3割と限度額の低いほう。"""
    return min(cost * COPAY_RATE, limit(name, cost))


def multi_hit(name: str) -> int:
    return tier(name)[6]


def crossing_cost(name: str) -> float:
    """**3割で払う額と、限度額がぴったり一致する医療費。**

    定額のところで頭打ちになる区分（エ・オ）は `定額 ÷ 3割`。
    1%刻みのある区分は、式の中の「差引く医療費」そのものになります
    （これがこのモジュールの主題です）。
    """
    _, _, _, flat, floor, rate, _ = tier(name)
    if floor is None:
        return flat / COPAY_RATE
    # 0.3x = flat + (x - floor) * rate  →  x = (flat - floor*rate) / (0.3 - rate)
    return (flat - floor * rate) / (COPAY_RATE - rate)


def cost_curve(costs: list[int], name: str = "ウ") -> list[dict]:
    return [{
        "医療費": c,
        "3割なら": round(c * COPAY_RATE),
        "実際に払う": round(paid(name, c)),
        "戻る額": round(c * COPAY_RATE - paid(name, c)),
        "実効の負担率": paid(name, c) / c * 100,
    } for c in costs]


def tier_edges(cost: int) -> list[dict]:
    """区分の境目。**標準報酬月額が1段ちがうだけで自己負担がいくら変わるか。**"""
    rows = []
    pairs = [("ウ", 500_000, "イ", 530_000), ("イ", 790_000, "ア", 830_000)]
    for lo_name, lo_pay, hi_name, hi_pay in pairs:
        lo, hi = paid(lo_name, cost), paid(hi_name, cost)
        rows.append({
            "低いほうの区分": lo_name,
            "低いほうの標準報酬月額": lo_pay,
            "高いほうの区分": hi_name,
            "高いほうの標準報酬月額": hi_pay,
            "月給の差": hi_pay - lo_pay,
            "低いほうの自己負担": round(lo),
            "高いほうの自己負担": round(hi),
            "自己負担の差": round(hi - lo),
        })
    return rows


def split_months(cost: int, name: str = "ウ", parts: int = 2) -> dict:
    """同じ医療費を1か月にまとめた場合と、月をまたいで分けた場合。"""
    each = cost / parts
    together = paid(name, cost)
    apart = sum(paid(name, each) for _ in range(parts))
    return {
        "医療費": cost,
        "1か月にまとめた場合": round(together),
        "分けた月数": parts,
        "1か月あたりの医療費": round(each),
        "分けた場合": round(apart),
        "差": round(apart - together),
    }


def year_with_multi_hit(cost: int, months: int, name: str = "ウ") -> dict:
    """1年のうち `months` か月、同じ医療費がかかった場合の合計。"""
    normal = min(months, MULTI_HIT_FROM - 1)
    reduced = max(0, months - normal)
    per = paid(name, cost)
    total = normal * per + reduced * multi_hit(name)
    return {
        "月数": months,
        "多数回該当より前": normal,
        "多数回該当": reduced,
        "1か月あたり": round(per),
        "多数回の額": multi_hit(name),
        "1年の合計": round(total),
        "多数回が無ければ": round(months * per),
        "軽くなる額": round(months * per - total),
    }


def household(costs: list[int], name: str = "ウ") -> dict:
    """世帯合算。**21,000円に届かない自己負担は、合算に入れられません。**"""
    each = [min(c * COPAY_RATE, limit(name, c)) for c in costs]
    countable = [p for p in each if p >= HOUSEHOLD_FLOOR]
    dropped = [p for p in each if p < HOUSEHOLD_FLOOR]
    merged_cost = sum(c for c, p in zip(costs, each) if p >= HOUSEHOLD_FLOOR)
    after = limit(name, merged_cost) + sum(dropped) if countable else sum(each)
    return {
        "人数": len(costs),
        "医療費の合計": sum(costs),
        "合算する前の自己負担": round(sum(each)),
        "合算に入れられない額": round(sum(dropped)),
        "合算した後": round(min(after, sum(each))),
        "戻る額": round(sum(each) - min(after, sum(each))),
    }


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(limit("ア", 842_000), 252_600, "区分アの定額",
                      source="健康保険法施行令42条1項1号")
    _checks.statutory(limit("イ", 558_000), 167_400, "区分イの定額",
                      source="健康保険法施行令42条1項2号")
    _checks.statutory(limit("ウ", 267_000), 80_100, "区分ウの定額",
                      source="健康保険法施行令42条1項3号")
    _checks.statutory(limit("エ", 1_000_000), 57_600, "区分エの限度額",
                      source="健康保険法施行令42条1項4号")
    _checks.statutory(limit("オ", 1_000_000), 35_400, "区分オの限度額",
                      source="健康保険法施行令42条1項5号")
    _checks.statutory(COPAY_RATE, 0.3, "70歳未満の窓口負担",
                      source="健康保険法74条1項1号")
    _checks.ratio(COPAY_RATE, "窓口の負担割合")
    _checks.statutory(HOUSEHOLD_FLOOR, 21_000, "世帯合算に入れる下限",
                      source="健康保険法施行令41条2項")

    # 2. 区分の並びと、多数回該当が必ず軽いこと
    _checks.ascending([multi_hit(n) for n in ("オ", "エ", "イ", "ア")],
                      "多数回該当の額が区分の順に並んでいない")
    for name, *_ in TIERS:
        _checks.greater(limit(name, 1_000_000), multi_hit(name),
                        f"区分{name}の多数回該当が、通常の限度額以上")

    # 3. **主題**: 式の中の「差引く医療費」は、3割がちょうど定額に一致する点
    for name, expect in (("ア", 842_000), ("イ", 558_000), ("ウ", 267_000)):
        _checks.rounding(crossing_cost(name), expect,
                         f"区分{name}で3割と限度額が一致する医療費")
        _checks.rounding(expect * COPAY_RATE, tier(name)[3],
                         f"区分{name}の定額（差引く医療費の3割）")
    _checks.rounding(crossing_cost("エ"), 192_000, "区分エで3割と限度額が一致する医療費")
    _checks.rounding(crossing_cost("オ"), 118_000, "区分オで3割と限度額が一致する医療費")

    # 4. その点より下では3割のほうが安く、上では限度額のほうが安いこと
    for name in ("ア", "イ", "ウ", "エ", "オ"):
        x = crossing_cost(name)
        _checks.rounding(paid(name, x), x * COPAY_RATE, f"区分{name}の交差点での自己負担")
        if not paid(name, x * 0.5) == x * 0.5 * COPAY_RATE:
            raise _checks.TableError(f"区分{name}: 交差点の手前なのに3割になっていない")
        if paid(name, x * 2) >= x * 2 * COPAY_RATE:
            raise _checks.TableError(f"区分{name}: 交差点の先なのに3割より安くなっていない")

    # 5. 計算の向き
    _checks.increases_with(lambda c: paid("ウ", c), (300_000, 1_000_000, 5_000_000),
                           "医療費が増えたのに自己負担が増えていない")
    _checks.decreases_with(lambda c: paid("ウ", c) / c,
                           (300_000, 1_000_000, 5_000_000, 10_000_000),
                           "医療費が増えたのに実効の負担率が下がっていない")
    _checks.increases_with(lambda n: paid(n, 1_000_000), ("エ", "ウ", "イ", "ア"),
                           "区分が上がったのに自己負担が増えていない")

    # 6. **主題**: 月をまたぐと限度額が2回かかる（分けたほうが必ず重い）
    for cost in (400_000, 600_000, 1_000_000):
        s = split_months(cost)
        _checks.greater(s["分けた場合"], s["1か月にまとめた場合"],
                        f"医療費{cost}円を2か月に分けた場合の負担が、まとめた場合")
    _checks.rounding(split_months(600_000)["差"], 77_430, "医療費60万円を分けたときの差")

    # 7. **主題**: 月給3万円の差で自己負担がいくら変わるか
    edge = tier_edges(1_000_000)[0]
    _checks.rounding(edge["月給の差"], 30_000, "区分ウと区分イの標準報酬月額の差")
    _checks.rounding(edge["自己負担の差"], 84_390, "区分ウと区分イの自己負担の差")

    # 8. 多数回該当は必ず軽くなる。見出しどおり1か月あたりで割れること
    y = year_with_multi_hit(1_000_000, 12)
    _checks.greater(y["多数回が無ければ"], y["1年の合計"],
                    "多数回該当があるのに1年の合計が軽くなっていない")
    _checks.never_decreases(lambda m: year_with_multi_hit(1_000_000, m)["1年の合計"],
                            range(1, 13), "月数が増えたのに1年の合計が減っている")

    # 9. 世帯合算は必ず得か同じ（21,000円未満は合算に入らない）
    for costs in ([1_000_000, 1_000_000], [1_000_000, 60_000], [60_000, 60_000]):
        h = household(costs)
        if h["戻る額"] < 0:
            raise _checks.TableError(f"世帯合算で負担が増えた: {costs}")

    _checks.assumption_values(ASSUMPTIONS, name="kogaku")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 限度額の式に出てくる数は、3割とぴったり一致する医療費 ===")
    for name, lo, hi, flat, floor, rate, _m in TIERS:
        x = crossing_cost(name)
        band = (f"標準報酬月額 {lo:,}円以上" if lo and not hi else
                f"標準報酬月額 {lo:,}〜{hi:,}円" if lo else
                f"標準報酬月額 {hi:,}円以下" if hi else "住民税が非課税")
        shape = (f"{flat:,}円＋(医療費−{floor:,})×{rate:.0%}" if floor
                 else f"{flat:,}円（定額）")
        print(f"  区分{name}  {band:<28} {shape:<34}"
              f" 3割と一致する医療費 {x:>9,.0f}円")

    print("\n=== 医療費が増えても、自己負担は1パーセントしか増えない（区分ウ）===")
    for row in cost_curve([267_000, 500_000, 1_000_000, 3_000_000,
                           5_000_000, 10_000_000]):
        print(f"  医療費 {row['医療費']:>10,}円  3割なら {row['3割なら']:>9,}円"
              f"  実際 {row['実際に払う']:>8,}円"
              f"  戻る {row['戻る額']:>9,}円"
              f"  実効 {row['実効の負担率']:>5.2f}%")

    print("\n=== 標準報酬月額が1段ちがうだけで、自己負担はいくら変わるか（医療費100万円）===")
    for row in tier_edges(1_000_000):
        print(f"  区分{row['低いほうの区分']}（{row['低いほうの標準報酬月額']:,}円）"
              f" {row['低いほうの自己負担']:>8,}円"
              f"  →  区分{row['高いほうの区分']}（{row['高いほうの標準報酬月額']:,}円）"
              f" {row['高いほうの自己負担']:>8,}円"
              f"   月給の差 {row['月給の差']:,}円 で 自己負担の差 {row['自己負担の差']:,}円")

    print("\n=== 同じ治療でも、月をまたぐと限度額が2回かかる（区分ウ）===")
    for cost in (300_000, 400_000, 600_000, 1_000_000, 2_000_000):
        s = split_months(cost)
        print(f"  医療費 {s['医療費']:>9,}円  1か月にまとめると {s['1か月にまとめた場合']:>8,}円"
              f"  2か月に分けると {s['分けた場合']:>8,}円  差 {s['差']:>8,}円")

    print("\n=== 4回目から軽くなる（多数回該当・区分ウ・毎月100万円）===")
    for months in (1, 3, 4, 6, 12):
        y = year_with_multi_hit(1_000_000, months)
        print(f"  {y['月数']:>2}か月  通常 {y['多数回該当より前']}回×{y['1か月あたり']:,}円"
              f" ＋ 多数回 {y['多数回該当']:>2}回×{y['多数回の額']:,}円"
              f"  合計 {y['1年の合計']:>9,}円"
              f"（多数回が無ければ {y['多数回が無ければ']:>9,}円・"
              f"{y['軽くなる額']:>8,}円 軽い）")

    print("\n=== 世帯で合算できるのは、1件21,000円以上の自己負担だけ（区分ウ）===")
    for costs in ([1_000_000, 1_000_000], [1_000_000, 300_000],
                  [1_000_000, 60_000], [300_000, 300_000], [60_000, 60_000]):
        h = household(costs)
        print(f"  {h['人数']}人ぶん 医療費 {h['医療費の合計']:>9,}円"
              f"  合算前 {h['合算する前の自己負担']:>8,}円"
              f"  → 合算後 {h['合算した後']:>8,}円"
              f"  戻る {h['戻る額']:>8,}円"
              f"（合算に入らない額 {h['合算に入れられない額']:>7,}円）")
