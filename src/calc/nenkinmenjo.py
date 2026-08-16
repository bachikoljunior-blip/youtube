"""国民年金の免除と追納。**追納の回収年数は、免除の区分がどれでも同じです。**

全額免除・4分の3免除・半額免除・4分の1免除。払う額も、増える年金額も、
区分ごとに全部ちがいます。**それなのに「追納した額を年金で取り返すまでの年数」は
4つとも同じ**になります。しかも**ふつうに保険料を払うときの、ちょうど2倍**です。

理由は、免除期間の反映割合が `2分の1 ＋ 2分の1 × 納付割合` という形をしているからです
（国民年金法27条）。追納する額は納めていない割合に比例し、増える年金も同じ割合に比例するので、
**割合が約分で消えます。** 消えたあとに残るのが「2分の1」＝**国庫負担のぶん**で、
これが2倍の正体です。**免除期間には、税金のぶんだけ既に年金が付いています。**

そこから出てくる、公表されていない数字（令和6年度の額で計算した場合）:

- ふつうに払う1か月は **約10.0年**で回収、**免除を追納した1か月は約20.0年**
- 学生納付特例と納付猶予は、**保険料0円という点では全額免除と同じなのに、
  年金額への反映は0**。全額免除なら10年で年 **102,000円**付くところが **0円**
- **半額免除の承認を受けて払わなかった1年**は、全額免除を選んでいた場合と比べて
  **年10,200円**を一生失う。**払った額は同じ0円**
- 2009年3月までの全額免除は3分の1しか反映されない。10年ぶんで年 **34,000円**の差
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値（国民年金法。割合そのものは長く動いていない）------------------
MONTHS_FULL = 480          # 40年（国民年金法27条）
NATIONAL_SHARE = 0.5       # 免除期間に入る国庫負担の割合（2009年4月から）
NATIONAL_SHARE_OLD = 1 / 3  # 2009年3月まで
QUALIFY_MONTHS = 120       # 受給資格期間 10年（国民年金法26条）
CATCHUP_YEARS = 10         # 追納できるのは10年以内（国民年金法94条）
ARREARS_YEARS = 2          # 未納のまま納められるのは2年以内（国民年金法102条4項）

# (区分, 納める割合, 年金への反映割合, 年金額に反映されるか)
# 反映割合は 2分の1 ＋ 2分の1 × 納める割合（国民年金法27条5号〜8号）
KINDS: list[tuple[str, float, float]] = [
    ("納付", 1.00, 1.0),
    ("4分の1免除", 0.75, 7 / 8),
    ("半額免除", 0.50, 6 / 8),
    ("4分の3免除", 0.25, 5 / 8),
    ("全額免除", 0.00, 4 / 8),
    ("納付猶予・学生納付特例", 0.00, 0.0),
    ("未納", 0.00, 0.0),
]
# 受給資格期間（10年）に数えるか。**未納だけが数えられません**
COUNTS_FOR_QUALIFY = {name: name != "未納" for name, _, _ in KINDS}

# ---- 年度で改定される額。**これは制度の骨格ではなく、この計算の前提です** ----
FULL_PENSION_YEAR = 816_000  # 老齢基礎年金の満額（令和6年度・新規裁定）
PREMIUM_MONTH = 16_980       # 国民年金保険料（令和6年度）

ASSUMPTIONS = [
    "老齢基礎年金の満額は年816,000円として計算しています。"
    "令和6年度の額で、毎年度改定されます",
    "国民年金保険料は月16,980円として計算しています。"
    "令和6年度の額で、毎年度改定されます",
    "免除期間が年金額に反映される割合は、2分の1に2分の1かける納める割合を足した値です。"
    "全額免除は2分の1、4分の3免除は8分の5、半額免除は8分の6、4分の1免除は8分の7です",
    "2009年4月より前の免除期間は、国庫負担が3分の1だったため反映が下がります",
    "追納の加算額は年度ごとに決まるため、加算なしの場合と、"
    "加算が0パーセントから10パーセントまでの場合を並べています",
    "受け取りは65歳からとし、繰上げも繰下げもしていません",
    "物価や賃金による改定、マクロ経済スライドは入れていません",
]


def kind(name: str) -> tuple[str, float, float]:
    for row in KINDS:
        if row[0] == name:
            return row
    raise ValueError(f"知らない区分: {name}")


def monthly_pension_unit() -> float:
    """1か月ぶんの、満額での年金額（年額）。"""
    return FULL_PENSION_YEAR / MONTHS_FULL


def pension_for(name: str, months: int) -> float:
    """その区分で `months` か月過ごしたときに増える老齢基礎年金（年額）。"""
    return monthly_pension_unit() * months * kind(name)[2]


def premium_for(name: str, months: int) -> float:
    """その区分で実際に納める保険料の合計。"""
    return PREMIUM_MONTH * months * kind(name)[1]


def catchup_cost(name: str, months: int = 1, surcharge: float = 0.0) -> float:
    """追納する額。**納めていない割合ぶんを、あとから納めます。**"""
    return PREMIUM_MONTH * (1 - kind(name)[1]) * months * (1 + surcharge)


def catchup_gain(name: str, months: int = 1) -> float:
    """追納で増える年金（年額）。反映割合が満額（1.0）まで上がります。"""
    return monthly_pension_unit() * months * (1.0 - kind(name)[2])


def catchup_years(name: str, surcharge: float = 0.0) -> float:
    """追納した額を、増えた年金で取り返すまでの年数。"""
    gain = catchup_gain(name)
    if gain <= 0:
        return float("inf")
    return catchup_cost(name, surcharge=surcharge) / gain


def normal_years() -> float:
    """ふつうに1か月ぶん納めたときの回収年数（未納を2年以内に納めた場合も同じ）。"""
    return PREMIUM_MONTH / monthly_pension_unit()


def kinds_table(months: int = 12) -> list[dict]:
    rows = []
    for name, pay, reflect in KINDS:
        rows.append({
            "区分": name,
            "納める割合": pay,
            "納める額": round(premium_for(name, months)),
            "反映割合": reflect,
            "増える年金": round(pension_for(name, months)),
            "未納との差": round(pension_for(name, months) - pension_for("未納", months)),
            "資格期間に入るか": COUNTS_FOR_QUALIFY[name],
        })
    return rows


def catchup_table() -> list[dict]:
    rows = []
    for name, pay, reflect in KINDS:
        if name in ("納付", "未納", "納付猶予・学生納付特例"):
            continue
        rows.append({
            "区分": name,
            "追納する額": round(catchup_cost(name)),
            "増える年金": round(catchup_gain(name), 1),
            "回収年数": catchup_years(name),
            "ふつうに払う場合との比": catchup_years(name) / normal_years(),
        })
    return rows


def surcharge_table(name: str = "全額免除") -> list[dict]:
    return [{
        "加算": s,
        "追納する額": round(catchup_cost(name, surcharge=s)),
        "回収年数": catchup_years(name, surcharge=s),
        "加算なしとの差": catchup_years(name, surcharge=s) - catchup_years(name),
    } for s in (0.0, 0.01, 0.03, 0.05, 0.10)]


def zero_yen_table(months: int = 120) -> list[dict]:
    """**保険料が0円という点では同じ**なのに、結果が3通りに分かれる。"""
    return [{
        "区分": name,
        "納める額": round(premium_for(name, months)),
        "増える年金": round(pension_for(name, months)),
        "資格期間に入るか": COUNTS_FOR_QUALIFY[name],
        "20年ぶん受け取ると": round(pension_for(name, months) * 20),
    } for name in ("全額免除", "納付猶予・学生納付特例", "未納")]


def half_exempt_unpaid(months: int = 12) -> dict:
    """**半額免除の承認を受けて、残りの半額を納めなかった場合。**

    その月は未納として扱われ、年金額に1円も反映されません。
    **同じ0円でも、全額免除を申請していれば2分の1が付いていました。**
    """
    full = pension_for("全額免除", months)
    return {
        "月数": months,
        "半額免除で納めた場合の負担": round(premium_for("半額免除", months)),
        "半額免除で納めた場合の年金": round(pension_for("半額免除", months)),
        "納めなかった場合の負担": 0,
        "納めなかった場合の年金": 0,
        "全額免除にしていた場合の負担": 0,
        "全額免除にしていた場合の年金": round(full),
        "取り逃がした年金": round(full),
        "20年ぶん": round(full * 20),
    }


def old_period_table(months_list: tuple[int, ...] = (12, 60, 120, 240)) -> list[dict]:
    """2009年3月までの全額免除は3分の1しか反映されません。"""
    rows = []
    for m in months_list:
        new = monthly_pension_unit() * m * NATIONAL_SHARE
        old = monthly_pension_unit() * m * NATIONAL_SHARE_OLD
        rows.append({
            "月数": m,
            "年数": m / 12,
            "2009年4月から": round(new),
            "2009年3月まで": round(old),
            "差": round(new - old),
        })
    # **見出しが「1年あたり」と言っているので、実際に年で割らせる**（割り忘れができない）
    steps = _checks.per_unit_steps(rows, "年数", "差",
                                   label="1年あたりの差", x_unit="年")
    for row, step in zip(rows, steps):
        row["1年あたりの差"] = None if step is None else round(step)
    return rows


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(MONTHS_FULL, 480, "満額になる月数", source="国民年金法27条")
    _checks.statutory(QUALIFY_MONTHS, 120, "受給資格期間の月数", source="国民年金法26条")
    _checks.statutory(CATCHUP_YEARS, 10, "追納できる年数", source="国民年金法94条1項")
    _checks.statutory(NATIONAL_SHARE, 0.5, "免除期間の国庫負担", source="国民年金法85条")
    _checks.ratio(NATIONAL_SHARE, "国庫負担の割合")
    _checks.ratio(NATIONAL_SHARE_OLD, "2009年3月までの国庫負担の割合")

    # 2. **反映割合は「2分の1 ＋ 2分の1 × 納める割合」**（この形が主題の土台）
    for name, pay, reflect in KINDS:
        if name in ("納付猶予・学生納付特例", "未納"):
            _checks.rounding(reflect, 0.0, f"{name}の反映割合")
            continue
        _checks.rounding(reflect, NATIONAL_SHARE + NATIONAL_SHARE * pay,
                         f"{name}の反映割合")
        # `ratio` は 0 < x < 1 を見る。納付は 1.0 ちょうど、全額免除は 0.0 ちょうど
        if 0 < pay < 1:
            _checks.ratio(pay, f"{name}の納める割合")
        elif pay not in (0.0, 1.0):
            raise _checks.TableError(f"{name}の納める割合が {pay}")
        if reflect < 1:
            _checks.ratio(reflect, f"{name}の反映割合")
    _checks.unique_by(KINDS, lambda r: r[0], "免除の区分")

    # 3. 並び（納める割合が高いほど、反映も高い）
    ordered = ["全額免除", "4分の3免除", "半額免除", "4分の1免除", "納付"]
    _checks.ascending([kind(n)[1] for n in ordered], "納める割合の並び", strict=True)
    _checks.ascending([kind(n)[2] for n in ordered], "反映割合の並び", strict=True)

    # 4. **主題**: 追納の回収年数は、区分がどれでも同じで、ふつうの2倍
    base = catchup_years("全額免除")
    for row in catchup_table():
        _checks.rounding(row["回収年数"], base,
                         f"{row['区分']}の回収年数（区分によらず同じはず）")
        _checks.rounding(row["ふつうに払う場合との比"], 2.0,
                         f"{row['区分']}の回収年数がふつうの2倍")
    _checks.rounding(base, normal_years() * 2, "追納の回収年数（ふつうの2倍）")
    _checks.rounding(normal_years(), PREMIUM_MONTH * MONTHS_FULL / FULL_PENSION_YEAR,
                     "ふつうに払ったときの回収年数")

    # 5. **主題**: 保険料0円の3つは、結果が3通りに分かれる
    zero = {r["区分"]: r for r in zero_yen_table()}
    for r in zero.values():
        _checks.rounding(r["納める額"], 0, f"{r['区分']}の納める額")
    _checks.greater(zero["全額免除"]["増える年金"],
                    zero["納付猶予・学生納付特例"]["増える年金"],
                    "全額免除の年金が、納付猶予の年金")
    _checks.rounding(zero["納付猶予・学生納付特例"]["増える年金"], 0, "納付猶予の年金")
    if zero["未納"]["資格期間に入るか"]:
        raise _checks.TableError("未納が受給資格期間に入る扱いになっている")
    if not zero["納付猶予・学生納付特例"]["資格期間に入るか"]:
        raise _checks.TableError("納付猶予が受給資格期間に入らない扱いになっている")

    # 6. **主題**: 半額免除を払わなかった年は、全額免除より損（負担はどちらも0円）
    h = half_exempt_unpaid()
    _checks.rounding(h["納めなかった場合の負担"], h["全額免除にしていた場合の負担"],
                     "どちらも負担は0円")
    _checks.greater(h["取り逃がした年金"], 0, "全額免除にしていた場合に付いた年金")
    _checks.rounding(h["取り逃がした年金"], round(pension_for("全額免除", 12)),
                     "取り逃がした年金（全額免除1年ぶん）")

    # 7. 2009年3月までは必ず低い。見出しどおり1年あたりで割れること
    for row in old_period_table():
        _checks.greater(row["2009年4月から"], row["2009年3月まで"],
                        f"{row['月数']}か月の新しい免除が古い免除")

    # 8. 計算の向き
    _checks.increases_with(lambda m: pension_for("全額免除", m), (12, 60, 120),
                           "免除の月数が増えたのに年金が増えていない")
    _checks.increases_with(lambda s: catchup_years("全額免除", s), (0.0, 0.03, 0.10),
                           "加算が増えたのに回収年数が延びていない")
    _checks.increases_with(lambda n: pension_for(n, 12), ordered,
                           "納める割合が上がったのに年金が増えていない")

    _checks.assumption_values(ASSUMPTIONS, name="nenkinmenjo")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 免除は「払っていない」ではない（1年ぶん）===")
    for row in kinds_table(12):
        mark = "◯" if row["資格期間に入るか"] else "×"
        print(f"  {row['区分']:<22} 納める {row['納める額']:>7,}円"
              f"  反映 {row['反映割合']:>5.1%}"
              f"  増える年金 {row['増える年金']:>7,}円/年"
              f"  10年の資格期間に入るか {mark}")

    print("\n=== 追納の回収年数は、どの免除区分でも同じ（ふつうに払う場合のちょうど2倍）===")
    print(f"  ふつうに1か月ぶん納める     {PREMIUM_MONTH:>7,}円 →"
          f" 年金 {monthly_pension_unit():>6.0f}円/年  回収 {normal_years():>5.2f}年")
    for row in catchup_table():
        print(f"  {row['区分']:<12} を追納  {row['追納する額']:>7,}円 →"
              f" 年金 {row['増える年金']:>6.1f}円/年  回収 {row['回収年数']:>5.2f}年"
              f"（ふつうの {row['ふつうに払う場合との比']:.2f}倍）")

    print("\n=== 保険料が0円という点では同じなのに、結果は3通りに分かれる（10年ぶん）===")
    for row in zero_yen_table():
        mark = "◯" if row["資格期間に入るか"] else "×"
        print(f"  {row['区分']:<22} 納める {row['納める額']:>2,}円"
              f"  増える年金 {row['増える年金']:>7,}円/年"
              f"  20年で {row['20年ぶん受け取ると']:>9,}円"
              f"  資格期間 {mark}")

    print("\n=== 半額免除の承認を受けて、残りを納めなかった1年 ===")
    h = half_exempt_unpaid()
    print(f"  半額を納めた場合    負担 {h['半額免除で納めた場合の負担']:>7,}円"
          f"  年金 {h['半額免除で納めた場合の年金']:>7,}円/年")
    print(f"  納めなかった場合    負担 {h['納めなかった場合の負担']:>7,}円"
          f"  年金 {h['納めなかった場合の年金']:>7,}円/年  ← 未納として扱われます")
    print(f"  全額免除にしていた  負担 {h['全額免除にしていた場合の負担']:>7,}円"
          f"  年金 {h['全額免除にしていた場合の年金']:>7,}円/年")
    print(f"  **負担は同じ0円なのに、取り逃がした年金は"
          f" {h['取り逃がした年金']:,}円/年（20年で {h['20年ぶん']:,}円）**")

    print("\n=== 同じ全額免除でも、2009年3月までは3分の1しか反映されない ===")
    for row in old_period_table():
        per = ("—" if row["1年あたりの差"] is None
               else f"{row['1年あたりの差']:,}円")
        print(f"  {row['年数']:>4.0f}年ぶん  2009年4月から {row['2009年4月から']:>7,}円/年"
              f"  2009年3月まで {row['2009年3月まで']:>7,}円/年"
              f"  差 {row['差']:>6,}円/年（1年あたり {per:>7}）")

    print("\n=== 追納の加算が、回収年数をどれだけ延ばすか（全額免除の1か月）===")
    for row in surcharge_table():
        print(f"  加算 {row['加算']:>5.0%}  追納 {row['追納する額']:>7,}円"
              f"  回収 {row['回収年数']:>5.2f}年"
              f"（加算なしより {row['加算なしとの差']:>4.2f}年 長い）")
