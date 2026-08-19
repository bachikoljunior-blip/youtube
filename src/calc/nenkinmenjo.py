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



def qualify_cliff(name: str = "納付", receive_years: int = 20) -> list[dict]:
    """**受給資格期間の1か月手前と、ちょうど。**片方は生涯0円です。

    資格期間（10年＝120か月）に1か月でも足りないと、
    **それまでに納めた保険料は1円も年金にならない**という形で効きます。
    """
    rows = []
    for months in (QUALIFY_MONTHS - 1, QUALIFY_MONTHS, QUALIFY_MONTHS + 1):
        qualified = months >= QUALIFY_MONTHS
        year = pension_for(name, months) if qualified else 0.0
        rows.append({
            "区分": name,
            "月数": months,
            "資格期間": QUALIFY_MONTHS,
            "資格を満たすか": qualified,
            "納めた額": round(premium_for(name, months)),
            "年額": round(year),
            "受け取る年数": receive_years,
            "生涯の受取": round(year * receive_years),
        })
    return rows


def qualify_by_kind(receive_years: int = 20) -> list[dict]:
    """資格期間ちょうどの120か月を、**どの区分で埋めたか**で結果を並べる。

    **免除は資格期間に入り、未納は入りません。**保険料が0円という点では同じでも、
    申請したかどうかで生涯の受取が分かれます。
    """
    rows = []
    for name, pay, reflect in KINDS:
        qualified = COUNTS_FOR_QUALIFY[name]
        year = pension_for(name, QUALIFY_MONTHS) if qualified else 0.0
        rows.append({
            "区分": name,
            "月数": QUALIFY_MONTHS,
            "納める割合": pay,
            "納めた額": round(premium_for(name, QUALIFY_MONTHS)),
            "資格期間に入るか": qualified,
            "年額": round(year),
            "受け取る年数": receive_years,
            "生涯の受取": round(year * receive_years),
        })
    return rows


def window_months(name: str) -> int:
    """あとから納められる期間（月数）。**免除は10年、未納は2年しかありません。**"""
    return (CATCHUP_YEARS if COUNTS_FOR_QUALIFY[name] and kind(name)[1] < 1.0
            else ARREARS_YEARS) * 12


def window_gap(receive_years: int = 20) -> list[dict]:
    """**申請して免除を受けた人と、黙って未納にした人の、あとから直せる幅の差。**

    どちらも保険料は0円ですが、免除は10年さかのぼって追納でき、
    未納は2年しかさかのぼれません。**その差は8年ぶん＝96か月**です。
    """
    lost = (CATCHUP_YEARS - ARREARS_YEARS) * 12
    rows = []
    for name, pay, reflect in KINDS:
        if pay >= 1.0:
            continue
        w = window_months(name)
        rows.append({
            "区分": name,
            "あとから納められる月数": w,
            "追納できない月数": (CATCHUP_YEARS * 12) - w,
            "手が届かない月数": lost if w == ARREARS_YEARS * 12 else 0,
            "その月数の年金（年額）": round(monthly_pension_unit() * lost
                                      * (1.0 - reflect)) if w == ARREARS_YEARS * 12 else 0,
            "受け取る年数": receive_years,
        })
    return rows


def window_cost(receive_years: int = 20) -> dict:
    """**「申請しなかった」ことの値段。**未納8年ぶんが取り返せないことの生涯の額。"""
    lost = (CATCHUP_YEARS - ARREARS_YEARS) * 12
    year = monthly_pension_unit() * lost * (1.0 - kind("未納")[2])
    return {"追納できる年数": CATCHUP_YEARS, "未納で戻れる年数": ARREARS_YEARS,
            "手が届かない月数": lost,
            "その月数を納めたときの額": round(PREMIUM_MONTH * lost),
            "年額の差": round(year), "受け取る年数": receive_years,
            "生涯の差": round(year * receive_years)}


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""

    # --- 2026-08-20 に足した節ぶん ------------------------------------------
    # (r) **主題**: 資格期間に1か月足りないと、納めた額があっても生涯0円
    rows = qualify_cliff("納付")
    short, exact = rows[0], rows[1]
    if short["年額"] != 0:
        raise _checks.TableError(f"{short['月数']}か月で年金が {short['年額']:,}円 出ている")
    if exact["年額"] <= 0:
        raise _checks.TableError("資格期間ちょうどで年金が0円")
    if short["納めた額"] <= 0:
        raise _checks.TableError("1か月手前でも納めた額は0でないはず（崖の前提）")
    if exact["生涯の受取"] - short["生涯の受取"] != exact["生涯の受取"]:
        raise _checks.TableError("崖の高さが、資格を満たしたときの生涯受取と一致しない")
    # (s) **主題**: 保険料0円でも、免除は資格期間に入り、未納は入らない
    by_kind = {r["区分"]: r for r in qualify_by_kind()}
    if by_kind["未納"]["生涯の受取"] != 0:
        raise _checks.TableError("未納120か月で生涯の受取が0でない")
    for name in ("全額免除", "納付猶予・学生納付特例"):
        if not by_kind[name]["資格期間に入るか"]:
            raise _checks.TableError(f"{name} が資格期間に入らない扱いになっている")
        if by_kind[name]["納めた額"] != by_kind["未納"]["納めた額"]:
            raise _checks.TableError(f"{name} と未納で納めた額が違う（どちらも0円のはず）")
    if by_kind["全額免除"]["生涯の受取"] <= by_kind["納付猶予・学生納付特例"]["生涯の受取"]:
        raise _checks.TableError("全額免除の生涯受取が、納付猶予以下になっている")
    # (t) **主題**: あとから納められる幅が、免除は10年・未納は2年
    if window_months("全額免除") != CATCHUP_YEARS * 12:
        raise _checks.TableError("免除の追納の幅が10年でない")
    if window_months("未納") != ARREARS_YEARS * 12:
        raise _checks.TableError("未納の幅が2年でない")
    w = window_cost()
    if w["手が届かない月数"] != (CATCHUP_YEARS - ARREARS_YEARS) * 12:
        raise _checks.TableError("手が届かない月数が8年ぶんでない")
    if w["年額の差"] <= 0 or w["生涯の差"] <= 0:
        raise _checks.TableError("申請しなかったことの値段が0以下")
    if abs(w["年額の差"] - monthly_pension_unit() * w["手が届かない月数"]) > 1:
        raise _checks.TableError("未納の反映割合が0でない前提になっている")

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

    YEARS = 20
    print(f"\n=== 受給資格の{QUALIFY_MONTHS}か月に1か月足りないと、"
          f"納めた保険料は1円も年金にならない（納付・{YEARS}年受け取る場合）===")
    print(f"{'区分':>4s} {'月数':>5s} {'資格期間':>6s} {'資格':>5s} {'納めた額':>11s} "
          f"{'年額':>9s} {'受け取る年数':>7s} {'生涯の受取'}")
    for row in qualify_cliff("納付", YEARS):
        print(f"{row['区分']:>4s} {row['月数']:4d}月 {row['資格期間']:5d}月 "
              f"{'満たす' if row['資格を満たすか'] else '**×**':>6s} "
              f"{row['納めた額']:>10,d}円 {row['年額']:>8,d}円 "
              f"{row['受け取る年数']:6d}年 {row['生涯の受取']:>11,d}円")
    print(f"  → **1か月の差**（保険料 {PREMIUM_MONTH:,}円）で、"
          f"生涯の受取が **0円 と {qualify_cliff('納付', YEARS)[1]['生涯の受取']:,}円** に分かれます。"
          "制度の説明にあるのは「10年で受給資格」という一文だけで、"
          "**その1か月手前にいる人がいくら失うかは、どこにも書かれていません。**")

    print(f"\n=== 同じ{QUALIFY_MONTHS}か月を、どの区分で埋めたか（{YEARS}年受け取る場合）===")
    print(f"{'区分':<20s} {'月数':>5s} {'納める割合':>7s} {'納めた額':>11s} "
          f"{'資格':>5s} {'年額':>9s} {'生涯の受取'}")
    for row in qualify_by_kind(YEARS):
        print(f"{row['区分']:<20s} {row['月数']:4d}月 {row['納める割合']:6.0%} "
              f"{row['納めた額']:>10,d}円 "
              f"{'入る' if row['資格期間に入るか'] else '**×**':>6s} "
              f"{row['年額']:>8,d}円 {row['生涯の受取']:>11,d}円")
    zero_pay = [r for r in qualify_by_kind(YEARS) if r["納めた額"] == 0]
    kinds_n = len({r["生涯の受取"] for r in qualify_by_kind(YEARS)})
    print(f"  → **納めた額が0円の区分が{len(zero_pay)}つあります**"
          f"（{'・'.join(r['区分'] for r in zero_pay)}）。"
          "**払った額は同じ0円なのに、生涯の受取は "
          + "・".join(f"{v:,}円" for v in sorted({r["生涯の受取"] for r in zero_pay},
                                                reverse=True)) + " に分かれます。**"
          "（納付猶予・学生納付特例は、年金額には1円も入りませんが"
          "**資格期間には入る**ので、未納とも別ものです。）"
          f"表の全体では{kinds_n}通りです。"
          "分けているのは**申請したかどうか**と、**どの申請をしたか**だけで、"
          "**「払えないなら申請する」の値段が、ここで初めて額になります。**")

    w = window_cost(YEARS)
    print(f"\n=== 申請して免除を受けた人は{w['追納できる年数']}年さかのぼれる。"
          f"黙って未納にした人は{w['未納で戻れる年数']}年しか戻れない ===")
    print(f"{'区分':<20s} {'あとから納められる':>10s} {'手が届かない':>8s} {'その月数の年金（年額）'}")
    for row in window_gap(YEARS):
        print(f"{row['区分']:<20s} {row['あとから納められる月数']:9d}月 "
              f"{row['手が届かない月数']:7d}月 {row['その月数の年金（年額）']:>12,d}円")
    print(f"  手が届かない月数            {w['手が届かない月数']}月"
          f"（{w['追納できる年数']}年 − {w['未納で戻れる年数']}年）")
    print(f"  その月数を納めたときの額    {w['その月数を納めたときの額']:,}円")
    print(f"  年額の差                    {w['年額の差']:,}円")
    print(f"  **{w['受け取る年数']}年受け取ったときの差   {w['生涯の差']:,}円**")
    print("  → 保険料を払えない年に**申請したかどうか**が、"
          f"**あとから直せる幅を{w['手が届かない月数']}か月ぶん**変えます。"
          "「免除は年金が減る」という説明はよく見ますが、"
          "**申請しないと追納の窓そのものが狭くなる**ことは、額で語られていません。")
