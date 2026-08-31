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


def multi_hit_paid(name: str, cost: float) -> float:
    """**多数回該当の月に、実際に払う額。**

    多数回該当が変えるのは**限度額**であって、払う額そのものではありません。
    窓口で払うのは**3割と限度額の低いほう**なので、
    **3割のほうが小さい月は、そちらが上限**です（`paid()` と同じ形）。

    ## なぜ分けて書いたか（2026-08-26 に踏んだ）

    ここまで `multi_hit(name)` を**そのまま「その月の自己負担」**として
    使っていました。区分ウ・医療費30万円以上の節しか無かったので
    （3割 90,000円 ＞ 多数回 44,400円）**一度も表に出ていません。**
    区分を横に並べた瞬間に出ます —— **区分ア・医療費30万円で
    「多数回該当だと 140,100円 払う」**（3割は 90,000円）。
    **軽くなるはずの制度が、3割より高い額を出していました。**
    """
    return min(cost * COPAY_RATE, float(multi_hit(name)))


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
    low = multi_hit_paid(name, cost)          # **3割のほうが低い月はそちら**
    total = normal * per + reduced * low
    return {
        "月数": months,
        "多数回該当より前": normal,
        "多数回該当": reduced,
        "1か月あたり": round(per),
        "多数回の額（1か月）": round(low),
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



def household_floor_cost(name: str = "ウ") -> dict:
    """世帯合算に入れられる自己負担 21,000円 は、**医療費でいくらか**。

    窓口が3割なので `21,000 ÷ 0.3` です。**この額は制度のどこにも書かれていません**
    —— 書いてあるのは自己負担のほうの 21,000円 だけで、
    受診する側が見ているのは医療費（総額）のほうです。
    """
    cost = HOUSEHOLD_FLOOR / COPAY_RATE
    return {"区分": name, "合算に入る自己負担の下限": HOUSEHOLD_FLOOR,
            "窓口の割合": COPAY_RATE,
            "医療費でいくらか": round(cost),
            "1円下の自己負担": (cost - 1) * COPAY_RATE,
            "1円下は合算に入るか": (cost - 1) * COPAY_RATE >= HOUSEHOLD_FLOOR}


def household_cliff(members: tuple[int, ...] = (1, 2, 3, 4, 5),
                    anchor: int = 1_000_000, name: str = "ウ") -> list[dict]:
    """**あと1円で合算に入る家族**が、世帯の自己負担をいくら変えるか。

    入院した人（医療費 `anchor`）がいる世帯に、
    「合算に入る最低額ちょうど」の家族を `members` 人足した場合と、
    **その1円下**だった場合を比べます。
    """
    edge = round(HOUSEHOLD_FLOOR / COPAY_RATE)
    rows = []
    for n in members:
        over = household([anchor] + [edge] * n, name)
        under = household([anchor] + [edge - 1] * n, name)
        rows.append({
            "区分": name,
            "入院した人の医療費": anchor,
            "境目の家族の人数": n,
            "1人あたりの医療費": edge,
            "世帯の医療費の差": n,
            "ちょうどの世帯の自己負担": over["合算した後"],
            "1円下の世帯の自己負担": under["合算した後"],
            "自己負担の差": under["合算した後"] - over["合算した後"],
        })
    return rows


def multi_hit_flat(costs: tuple[int, ...] = (300_000, 500_000, 1_000_000,
                                             3_000_000, 10_000_000),
                   name: str = "ウ") -> list[dict]:
    """**4か月目からは、医療費がいくら増えても自己負担が1円も動きません。**

    多数回該当の限度額は**定額**で、1%の上乗せがありません。
    3か月目までは医療費に比例して増える部分があるのに、そこで完全に止まります。
    """
    return [{
        "区分": name,
        "医療費": c,
        "3か月目までの自己負担": round(paid(name, c)),
        "4か月目からの自己負担": round(multi_hit_paid(name, c)),
        "止まる額": round(paid(name, c)) - round(multi_hit_paid(name, c)),
        "4か月目の実効の負担率": multi_hit_paid(name, c) / c * 100,
    } for c in costs]


def multi_hit_year(cost: int = 1_000_000, name: str = "ウ") -> list[dict]:
    """同じ医療費が続いた1年。**何か月目から「増えない」に変わるか。**"""
    rows = []
    running = 0.0
    for m in range(1, 13):
        per = (paid(name, cost) if m < MULTI_HIT_FROM
               else multi_hit_paid(name, cost))
        running += per
        rows.append({"区分": name, "医療費": cost, "月": m,
                     "その月の自己負担": round(per),
                     "ここまでの合計": round(running),
                     "多数回該当か": m >= MULTI_HIT_FROM})
    return rows


# ---- 多数回該当の「割引」を、区分べつに読む（2026-08-26 に足した）--------
#
# ここまでの節は**区分ウだけ**を見ていました。多数回該当の額 `multi_hit` は
# 区分ごとの定額なのに、**そこから引く前の限度額は区分ア・イ・ウだけが
# 医療費に連動します**（1パーセントの項）。だから「4回目から軽くなる額」は
# **区分によって、性質そのものが違います** —— 伸びる区分と、1円も動かない区分。
def multi_hit_gap(name: str, cost: int) -> dict:
    """**多数回該当で、1か月あたりいくら軽くなるか。**"""
    per = paid(name, cost)
    m = multi_hit_paid(name, cost)
    return {
        "区分": name,
        "医療費": cost,
        "ふだんの自己負担": round(per),
        "多数回の額（1か月）": round(m),
        "1か月の割引": round(per - m),
        "割引の割合": (per - m) / per if per else 0.0,
    }


def multi_hit_gap_grid(cost: int = 1_000_000) -> list[dict]:
    """5つの区分ぜんぶで、1か月の割引を並べる。"""
    return [multi_hit_gap(row[0], cost) for row in TIERS]


def multi_hit_gap_by_cost(costs: tuple[int, ...] = (300_000, 1_000_000,
                                                    3_000_000, 10_000_000)
                          ) -> list[dict]:
    """**医療費を動かすと、割引が伸びる区分と伸びない区分に割れる。**

    1パーセントの項を持つのは区分ア・イ・ウだけです
    （`TIERS` の5番目の欄。エとオは 0.0）。
    """
    rows = []
    for cost in costs:
        row: dict = {"医療費": cost}
        for t in TIERS:
            row[t[0]] = multi_hit_gap(t[0], cost)["1か月の割引"]
        rows.append(row)
    return rows


def multi_hit_catch_up(name: str, cost: int = 1_000_000) -> dict:
    """**割引だけで、最初の3か月ぶんの自己負担と同じ額になるのは何か月目か。**

    「取り返す」という話ではありません。**割引の累積が、多数回該当に入る前の
    3か月ぶんの自己負担に並ぶ月数**を、そのまま割り算で出しています。
    `MULTI_HIT_FROM` が 4 なので、割引が付くのは4か月目からです。
    """
    g = multi_hit_gap(name, cost)
    first3 = (MULTI_HIT_FROM - 1) * g["ふだんの自己負担"]
    months = first3 / g["1か月の割引"] if g["1か月の割引"] else 0.0
    return {
        "区分": name,
        "医療費": cost,
        "最初の3か月": round(first3),
        "1か月の割引": g["1か月の割引"],
        "並ぶ月数": months,
        "1年で並ぶか": months <= 12,
    }


def multi_hit_catch_up_grid(cost: int = 1_000_000) -> list[dict]:
    """5つの区分ぜんぶ。**額の大きい区分が、必ずしも速くありません。**"""
    return [multi_hit_catch_up(row[0], cost) for row in TIERS]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""

    # --- 2026-08-20 に足した節ぶん ------------------------------------------
    # (x) 世帯合算の 21,000円 を医療費に直すと 70,000円ちょうど
    f = household_floor_cost()
    if f["医療費でいくらか"] != 70_000:
        raise _checks.TableError(
            f"合算に入る医療費の下限が {f['医療費でいくらか']:,}円。"
            f"{HOUSEHOLD_FLOOR:,} ÷ {COPAY_RATE} ＝ 70,000円 のはず")
    if f["1円下は合算に入るか"]:
        raise _checks.TableError("下限の1円下でも合算に入ってしまっている（境目が甘い）")
    # (y) **主題**: 1人あたり1円下だと、世帯合算が丸ごと効かない
    for row in household_cliff():
        if row["自己負担の差"] <= 0:
            raise _checks.TableError(
                f"境目の家族{row['境目の家族の人数']}人の世帯で、1円下のほうが安いか同じ"
                f"（差 {row['自己負担の差']:,}円）。**合算が効かないぶん高くなるはず**")
    # 人数が増えるほど、落ちる額は大きくなる
    _checks.never_decreases(lambda i: household_cliff()[int(i)]["自己負担の差"],
                            list(range(len(household_cliff()))),
                            "人数を増やしたのに、合算が効かない損が小さくなっている")
    # (w) **多数回該当の月でも、3割を超えて払うことはない**（2026-08-26 に踏んだ）
    #     `multi_hit(name)` をそのまま「その月の自己負担」にしていたので、
    #     区分アで医療費30万円のとき **140,100円**（3割は 90,000円）が出ていました。
    for name in [row[0] for row in TIERS]:
        for c in (100_000, 300_000, 1_000_000, 10_000_000):
            if multi_hit_paid(name, c) > c * COPAY_RATE + 1e-9:
                raise _checks.TableError(
                    f"区分{name}・医療費{c:,}円 の多数回該当で "
                    f"{multi_hit_paid(name, c):,.0f}円 払うことになっています。"
                    f"**3割の {c * COPAY_RATE:,.0f}円 を超えています**")
            g = multi_hit_gap(name, c)
            if g["1か月の割引"] < 0:
                raise _checks.TableError(
                    f"区分{name}・医療費{c:,}円 の割引が {g['1か月の割引']:,}円 で"
                    "マイナスです。**多数回該当のほうが高くなっています**")
    # (w2) **主題**: 1パーセントの項を持つ区分だけ、割引が医療費で伸びる
    for name in ("ア", "イ", "ウ"):
        _checks.increases_with(
            lambda c, n=name: multi_hit_gap(n, int(c))["1か月の割引"],
            (1_000_000, 3_000_000, 10_000_000),
            f"区分{name}の割引が、医療費とともに伸びる")
    for name in ("エ", "オ"):
        vals = {multi_hit_gap(name, c)["1か月の割引"]
                for c in (1_000_000, 3_000_000, 10_000_000)}
        if len(vals) != 1:
            raise _checks.TableError(
                f"区分{name}の割引が {sorted(vals)} と動いています。"
                "**定額の区分なので、医療費では動かないはず**")
    # (w3) **主題**: 割引の額が大きいエのほうが、オより「並ぶ月数」が遅い
    e = multi_hit_catch_up("エ")
    o = multi_hit_catch_up("オ")
    if not (e["1か月の割引"] > o["1か月の割引"] and e["並ぶ月数"] > o["並ぶ月数"]):
        raise _checks.TableError(
            f"区分エ（割引 {e['1か月の割引']:,}円・{e['並ぶ月数']:.2f}か月）と"
            f"区分オ（割引 {o['1か月の割引']:,}円・{o['並ぶ月数']:.2f}か月）で、"
            "**額と速さの逆転が起きていません**")
    if e["1年で並ぶか"] or not o["1年で並ぶか"]:
        raise _checks.TableError(
            "12か月を超えるのが区分エだけ、という形が崩れています")
    # (z) **主題**: 多数回該当の額は定額で、医療費に依らない
    flat = {r["4か月目からの自己負担"] for r in multi_hit_flat()}
    if len(flat) != 1:
        raise _checks.TableError(f"4か月目からの自己負担が {sorted(flat)} と割れた。**定額のはず**")
    if flat.pop() != multi_hit("ウ"):
        raise _checks.TableError("多数回該当の額が TIERS と食い違う")
    # 3か月目までは医療費とともに増える（＝止まるのは4か月目から、という主張の裏）
    _checks.never_decreases(lambda i: multi_hit_flat()[int(i)]["3か月目までの自己負担"],
                            list(range(len(multi_hit_flat()))),
                            "3か月目までの自己負担が、医療費を増やしても増えていない")
    # 1年の並びで、4か月目に段が下がってそこから一定
    year = multi_hit_year()
    if year[MULTI_HIT_FROM - 2]["その月の自己負担"] <= year[MULTI_HIT_FROM - 1]["その月の自己負担"]:
        raise _checks.TableError("4か月目で自己負担が下がっていない")
    later = {r["その月の自己負担"] for r in year[MULTI_HIT_FROM - 1:]}
    if len(later) != 1:
        raise _checks.TableError(f"4か月目から先が一定でない: {sorted(later)}")

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
              f" ＋ 多数回 {y['多数回該当']:>2}回×{y['多数回の額（1か月）']:,}円"
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

    f = household_floor_cost()
    print(f"\n=== 世帯合算の「21,000円」は、医療費だと{f['医療費でいくらか']:,}円ちょうど（区分ウ）===")
    print(f"  合算に入れられる自己負担の下限   {f['合算に入る自己負担の下限']:,}円")
    print(f"  窓口の割合                       {f['窓口の割合']}")
    print(f"  **医療費でいくらか**             {f['医療費でいくらか']:,}円"
          f"（{f['合算に入る自己負担の下限']:,} ÷ {f['窓口の割合']}）")
    print(f"  その1円下の自己負担              {f['1円下の自己負担']:,.1f}円 → "
          f"合算に入る: {'はい' if f['1円下は合算に入るか'] else '**いいえ**'}")
    print(f"{'区分':>3s} {'入院した人の医療費':>13s} {'境目の家族':>7s} {'1人の医療費':>11s} "
          f"{'世帯の差':>7s} {'ちょうど':>10s} {'1円下':>10s} {'自己負担の差'}")
    for row in household_cliff():
        print(f"{row['区分']:>3s} {row['入院した人の医療費']:>12,d}円 "
              f"{row['境目の家族の人数']:5d}人 {row['1人あたりの医療費']:>10,d}円 "
              f"{row['世帯の医療費の差']:>6,d}円 {row['ちょうどの世帯の自己負担']:>9,d}円 "
              f"{row['1円下の世帯の自己負担']:>9,d}円 **{row['自己負担の差']:,}円**")
    print(f"  → 制度が書いているのは自己負担の {HOUSEHOLD_FLOOR:,}円 だけですが、"
          f"**受診する側が見ているのは医療費のほう**です。"
          f"{f['医療費でいくらか']:,}円 に1円届かない家族は、"
          "**その自己負担を1円も合算に持ち込めません。**"
          "世帯の医療費が数円ちがうだけで、返ってくる額が万単位で変わります。")

    print(f"\n=== 4か月目からは、医療費がいくら増えても自己負担が1円も増えない"
          f"（区分ウ・多数回該当 {multi_hit('ウ'):,}円）===")
    print(f"{'区分':>3s} {'医療費':>12s} {'3か月目まで':>11s} {'4か月目から':>11s} "
          f"{'止まる額':>10s} {'4か月目の実効の負担率'}")
    for row in multi_hit_flat():
        print(f"{row['区分']:>3s} {row['医療費']:>11,d}円 {row['3か月目までの自己負担']:>10,d}円 "
              f"{row['4か月目からの自己負担']:>10,d}円 {row['止まる額']:>9,d}円 "
              f"{row['4か月目の実効の負担率']:>8.3f}%")
    print("  → 3か月目までの限度額には「医療費の1パーセント」が乗っていますが、"
          "**多数回該当の限度額は定額で、1パーセントの上乗せがありません。**"
          "だから医療費30万円の月も1000万円の月も、4か月目からは**まったく同じ額**です。"
          "**上乗せが消えることは、式を見ても書いてありません。**")

    print(f"\n=== 同じ治療が1年つづいた場合の、月ごとの自己負担（区分ウ・医療費"
          f"{1_000_000 // 10_000}万円）===")
    print(f"{'区分':>3s} {'医療費':>11s} {'月':>3s} {'その月':>10s} {'ここまでの合計':>12s} 多数回該当")
    for row in multi_hit_year():
        print(f"{row['区分']:>3s} {row['医療費']:>10,d}円 {row['月']:2d}月 "
              f"{row['その月の自己負担']:>9,d}円 {row['ここまでの合計']:>11,d}円   "
              f"{'**該当**' if row['多数回該当か'] else '—'}")
    print("  → **4か月目に段が1つ下がり、そこから12月まで1円も動きません。**"
          "「高額療養費で戻る」という話は月ごとに語られますが、"
          "**続いた場合の1年の合計は、月額の12倍にはなりません。**")

    C = 1_000_000
    print(f"\n=== 多数回該当で軽くなる額は、区分で何倍ちがうか"
          f"（医療費{C:,}円・1か月あたり）===")
    print(f"{'区分':>3s} {'ふだんの自己負担':>15s} {'多数回の額':>11s} "
          f"{'1か月の割引':>12s} {'割引の割合':>10s}")
    g = multi_hit_gap_grid(C)
    for r in g:
        print(f"{r['区分']:>3s} {r['ふだんの自己負担']:14,d}円 {r['多数回の額（1か月）']:10,d}円 "
              f"{r['1か月の割引']:11,d}円 {r['割引の割合']:9.1%}")
    hi = max(g, key=lambda r: r["1か月の割引"])
    lo = min(g, key=lambda r: r["1か月の割引"])
    print(f"  → **区分{hi['区分']}の {hi['1か月の割引']:,}円 は、"
          f"区分{lo['区分']}の {lo['1か月の割引']:,}円 の "
          f"{hi['1か月の割引'] / lo['1か月の割引']:.2f}倍**です。"
          f"ところが**割合で見ると逆**で、"
          f"{hi['区分']}は{hi['割引の割合']:.1%}、{lo['区分']}は{lo['割引の割合']:.1%}。"
          "**多数回該当の額だけが定額で、そこから引く前の限度額は"
          "区分ア・イ・ウだけが医療費に連動する**からです")

    print("\n=== 医療費を増やすと、割引が伸びる区分と、1円も伸びない区分に割れる"
          "（1か月あたりの割引）===")
    print(f"{'医療費':>12s} " + " ".join(f"{t[0]:>11s}" for t in TIERS))
    for r in multi_hit_gap_by_cost():
        print(f"{r['医療費']:11,d}円 "
              + " ".join(f"{r[t[0]]:10,d}円" for t in TIERS))
    print("  → **区分エとオは、医療費が33倍になっても割引が1円も動きません。**"
          f"1パーセントの項を持つのは区分ア・イ・ウだけで（`TIERS` の5番目の欄）、"
          "**エとオの限度額はもともと定額**だからです。"
          "**「重い月ほど多数回該当が効く」は、上の3区分だけの話です**")
    print(f"  → そして**上の行では、区分アとイの割引が 0円**です。"
          f"医療費{300_000:,}円 の3割は {round(300_000 * COPAY_RATE):,}円 で、"
          f"多数回該当の限度額（ア {multi_hit('ア'):,}円 ／ "
          f"イ {multi_hit('イ'):,}円）より低い。"
          "**払うのは3割と限度額の低いほう**なので、"
          "**限度額をいくら下げても、その月の負担は1円も変わりません。**"
          "**区分が上の人ほど、多数回該当が効きはじめる医療費が高いところにあります**")

    print(f"\n=== 割引だけで、最初の3か月ぶんの自己負担に並ぶのは何か月目か"
          f"（医療費{C:,}円）===")
    print(f"{'区分':>3s} {'最初の3か月':>12s} {'1か月の割引':>12s} "
          f"{'並ぶ月数':>9s}  {'1年で並ぶか'}")
    for r in multi_hit_catch_up_grid(C):
        print(f"{r['区分']:>3s} {r['最初の3か月']:11,d}円 {r['1か月の割引']:11,d}円 "
              f"{r['並ぶ月数']:8.2f}か月  "
              + ("並びます" if r["1年で並ぶか"] else "**並びません（12か月を超える）**"))
    e = multi_hit_catch_up("エ", C)
    o = multi_hit_catch_up("オ", C)
    print(f"  → **割引の額が大きい区分エ（{e['1か月の割引']:,}円）のほうが、"
          f"区分オ（{o['1か月の割引']:,}円）より遅い**"
          f"（{e['並ぶ月数']:.2f}か月 と {o['並ぶ月数']:.2f}か月）。"
          "**最初の3か月ぶんが、割引の差より大きく開いている**からです。"
          "**5つの区分のうち、12か月を超えるのは区分エだけ**です")
