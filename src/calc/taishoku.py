"""退職金にかかる税金（退職所得控除・2分の1課税）を、自分で計算する。

**2026-08-15 に追加。** 理由は在庫ではなく**題材の幅**のほうが大きい。

`scripts/topic_forge.py` は「1つの計算モジュールから、節の数だけテーマが取れる」
仕組みだが、**節を掘り尽くすとそこで止まる**（`--list` がそう言う）。
8/15 17:1x の時点で未使用は 8節。**在庫の律速は calc の本数**に落ちていた。

だが、それだけなら既存モジュールに節を足せば済む。**新しい制度を選んだ理由は別**:

    いまの9本（手取り・残業代・失業給付・ふるさと納税・医療費・住宅ローン・
    副業・年金・控除）は、**ほぼ全部が現役世代の給与まわり**だった。

`docs/STRATEGY.md` の掛け算は「RPM はニッチで10倍以上変わる」。退職金は
**金額の桁が大きく、視聴者の年齢層が上**で、いまの9本とは別のニッチに当たる。
在庫を増やすついでに**当たりを引く確率を上げる**ほうが、目標には近い。

## 計算の中身（所得税法30条・31条、地方税法50条の2）

    勤続年数A（1年未満は切り上げ）
      A ≤ 20年 : 控除 = 40万円 × A（80万円に満たないときは80万円）
      A > 20年 : 控除 = 800万円 + 70万円 × (A - 20)

    課税退職所得 = (退職金 - 控除) × 1/2      （1000円未満切捨）
    所得税 = 速算表(課税退職所得) × 1.021     （分離課税。他の所得と合算しない）
    住民税 = 課税退職所得 × 10%               （分離課税）

**「2分の1」が効かない場合が2つある**（2022年改正）。ここが動画の核になる。

    勤続5年以下の役員等          : 1/2 なし（全額）
    勤続5年以下の役員以外        : (退職金 - 控除) のうち **300万円を超える部分**は 1/2 なし

## どこにも表になっていない数字（＝この動画で出すもの）

**勤続20年の前後で、控除の増え方が 40万円/年 → 70万円/年 に跳ねる。**
つまり「あと1年勤めると手取りがいくら増えるか」は、19年目と20年目で違う。
一般の解説は控除の式までは書くが、**年数を1年動かしたときの手取りの差**は出さない。
そこを金額で出す。

**確定拠出年金（iDeCo）の一時金受取や、退職所得の受給に関する申告書を
出さなかった場合（一律20.42%源泉）は入れない。** 条件が別立てになり、
1本の動画に2つの制度を混ぜると前提が追えなくなる（`iryohi.py` と同じ方針）。
"""
from __future__ import annotations

import math

ASSUMPTIONS = [
    "勤続年数は1年未満を切り上げて数えています",
    "退職所得控除は、勤続20年までが1年あたり40万円、20年を超える部分が1年あたり70万円です",
    "控除が80万円に満たないときは80万円としています",
    "課税退職所得は、退職金から控除を引いた額の2分の1です",
    "勤続5年以下で役員以外の場合、控除を引いた額のうち300万円を超える部分は2分の1になりません",
    "所得税は復興特別所得税2.1パーセントを含めています",
    "住民税は標準税率10パーセントで計算しています",
    "退職金は他の所得と合算しない分離課税で計算しています",
    "障害が原因の退職による100万円の上乗せは含めていません",
    "確定拠出年金の一時金や、退職所得の受給に関する申告書を出さなかった場合は含めていません",
]

# 制度の値。**改正が続くものは入力に逃がす**（docs/CONSTRAINTS.md B4）が、
# ここは長く動いていない。2分の1が効かない範囲だけ 2022年に変わった。
YEARS_BORDER = 20            # 控除の増え方が変わる勤続年数
RATE_UNDER = 400_000         # 20年以下の1年あたり控除（円）
RATE_OVER = 700_000          # 20年超の1年あたり控除（円）
DEDUCTION_FLOOR = 800_000    # 控除の下限（円）
SHORT_YEARS = 5              # 「短期退職手当等」の勤続年数
SHORT_HALF_CAP = 3_000_000   # 短期でも2分の1が効く上限（円）
RECONSTRUCTION = 0.021       # 復興特別所得税
RESIDENT_RATE = 0.10         # 住民税の標準税率

# 所得税の速算表（課税所得の上限, 税率, 控除額）。**分離課税でも同じ表を使う。**
TAX_TABLE = [
    (1_950_000, 0.05, 0),
    (3_300_000, 0.10, 97_500),
    (6_950_000, 0.20, 427_500),
    (9_000_000, 0.23, 636_000),
    (18_000_000, 0.33, 1_536_000),
    (40_000_000, 0.40, 2_796_000),
    (None, 0.45, 4_796_000),
]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    if RATE_OVER <= RATE_UNDER:
        raise ValueError("20年超の控除単価が20年以下を下回っている")
    if DEDUCTION_FLOOR != RATE_UNDER * 2:
        raise ValueError("控除の下限が2年分と一致していない（80万円）")

    # 速算表が昇順で、境目で連続していること（不連続なら税額が飛ぶ＝表が壊れている）
    edges = [e for e, _, _ in TAX_TABLE if e is not None]
    if edges != sorted(edges):
        raise ValueError("速算表が昇順に並んでいない")
    for edge in edges:
        below = income_tax_raw(edge)
        above = income_tax_raw(edge + 1)
        if not below <= above <= below + 1:
            raise ValueError(f"速算表が{edge:,}円の境目で連続していない: {below} → {above}")

    # 控除の式の境目（20年ちょうど）で連続していること
    if deduction(20) != 8_000_000:
        raise ValueError("勤続20年の控除が800万円にならない")
    if deduction(21) != 8_700_000:
        raise ValueError("勤続21年の控除が870万円にならない")
    if deduction(1) != DEDUCTION_FLOOR:
        raise ValueError("勤続1年の控除が下限の80万円になっていない")

    # 端数の切り上げ（1年未満は1年）
    if deduction(10.1) != deduction(11):
        raise ValueError("勤続年数の端数が切り上げられていない")

    # 控除以下なら税金は0
    if tax(5_000_000, 20)["total"] != 0:
        raise ValueError("控除以下なのに税金が出ている")
    # 退職金が増えれば税金も増える
    if not tax(30_000_000, 20)["total"] > tax(20_000_000, 20)["total"]:
        raise ValueError("退職金が増えたのに税金が増えていない")
    # 同じ退職金なら、勤続が長いほど手取りは多い
    if not tax(20_000_000, 30)["net"] > tax(20_000_000, 20)["net"]:
        raise ValueError("勤続が長いのに手取りが増えていない")
    # 短期退職（5年以下・役員以外）は、300万円を超える部分で2分の1が効かない
    short = tax(15_000_000, 5, short_term=True)
    long_ = tax(15_000_000, 5, short_term=False)
    if not short["total"] > long_["total"]:
        raise ValueError("短期退職手当等のほうが税金が軽くなっている")


def years_counted(years: float) -> int:
    """勤続年数。**1年未満は切り上げ。** 10年1か月は11年で数える。"""
    return max(1, math.ceil(years))


def deduction(years: float) -> int:
    """退職所得控除額。**20年の前後で1年あたりの単価が跳ねる。**"""
    a = years_counted(years)
    if a <= YEARS_BORDER:
        return max(RATE_UNDER * a, DEDUCTION_FLOOR)
    return RATE_UNDER * YEARS_BORDER + RATE_OVER * (a - YEARS_BORDER)


def taxable(payout: int, years: float, short_term: bool = False,
            officer: bool = False) -> int:
    """課税退職所得金額（1000円未満切捨）。

    **2分の1が効かない場合が2つある**（2022年改正）。
      officer=True     : 勤続5年以下の役員等 → 全額が課税対象
      short_term=True  : 勤続5年以下の役員以外 → 300万円を超える部分だけ全額
    """
    base = max(payout - deduction(years), 0)
    if base == 0:
        return 0
    a = years_counted(years)
    if officer and a <= SHORT_YEARS:
        amount = base
    elif short_term and a <= SHORT_YEARS and base > SHORT_HALF_CAP:
        amount = SHORT_HALF_CAP // 2 + (base - SHORT_HALF_CAP)
    else:
        amount = base / 2
    return int(amount // 1000 * 1000)


def income_tax_raw(taxable_amount: int) -> int:
    """速算表そのもの（復興特別所得税を含まない）。"""
    for edge, rate, sub in TAX_TABLE:
        if edge is None or taxable_amount <= edge:
            return max(int(taxable_amount * rate - sub), 0)
    raise AssertionError("速算表を抜けた")


def tax(payout: int, years: float, short_term: bool = False,
        officer: bool = False) -> dict:
    """退職金にかかる税金と、手元に残る額。"""
    t = taxable(payout, years, short_term, officer)
    income = int(income_tax_raw(t) * (1 + RECONSTRUCTION))
    resident = int(t * RESIDENT_RATE)
    total = income + resident
    return {
        "payout": payout,
        "years": years_counted(years),
        "deduction": deduction(years),
        "taxable": t,
        "income_tax": income,
        "resident_tax": resident,
        "total": total,
        "net": payout - total,
        "rate": total / payout if payout else 0.0,
    }


def year_border_grid(payout: int) -> list[dict]:
    """勤続年数べつの手取り。**20年の前後で1年あたりの増え方が変わる。**

    「あと1年勤めると手取りがいくら増えるか」を出す。**ここが表になっていない。**
    """
    check_tables()
    out = []
    prev = None
    for a in (17, 18, 19, 20, 21, 22, 23, 25, 30, 35):
        r = tax(payout, a)
        r["gain"] = r["net"] - prev["net"] if prev else 0
        out.append(r)
        prev = r
    return out


def payout_grid(years: int) -> list[dict]:
    """退職金の額べつに、税金と手取り。"""
    check_tables()
    return [tax(p, years) for p in
            (5_000_000, 10_000_000, 15_000_000, 20_000_000, 25_000_000, 30_000_000)]


def short_term_grid(payout: int) -> list[dict]:
    """勤続5年以下のとき、2分の1が効く場合と効かない場合の差。"""
    check_tables()
    out = []
    for a in (3, 4, 5, 6):
        normal = tax(payout, a, short_term=False)
        short = tax(payout, a, short_term=True)
        out.append({
            "years": a,
            "applies": a <= SHORT_YEARS,
            "normal": normal["total"],
            "short": short["total"],
            "diff": short["total"] - normal["total"],
        })
    return out


def free_line() -> list[dict]:
    """**税金が1円もかからない退職金の上限**（＝控除そのもの）。

    「退職金にはいくらまで税金がかからないか」は、控除の式を金額に直すだけだが、
    **年数べつの表としては出回っていない。**
    """
    check_tables()
    return [{"years": a, "free": deduction(a)} for a in
            (5, 10, 15, 20, 21, 25, 30, 35, 38, 40)]


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 税金が1円もかからない退職金の上限（勤続年数べつ）===")
    print(f"{'勤続年数':>8s} {'ここまで無税':>12s}  {'1年あたりの伸び'}")
    prev = None
    for r in free_line():
        if prev:
            span = r["years"] - prev["years"]
            step = f"{(r['free'] - prev['free']) // span:,}円/年"
        else:
            step = "—"
        print(f"{r['years']:6d}年 {r['free']:11,d}円  {step}")
        prev = r

    print("\n=== 勤続20年の前後で、あと1年ぶんの手取りがどれだけ変わるか（退職金2000万円）===")
    print(f"{'勤続年数':>8s} {'控除':>11s} {'課税退職所得':>11s} {'税金合計':>10s} {'手取り':>12s} {'前年からの増え'}")
    for r in year_border_grid(20_000_000):
        gain = f"+{r['gain']:,}円" if r["gain"] else "—"
        print(f"{r['years']:6d}年 {r['deduction']:10,d}円 {r['taxable']:10,d}円 "
              f"{r['total']:9,d}円 {r['net']:11,d}円  {gain}")

    print("\n=== 退職金べつの税金と手取り（勤続25年）===")
    print(f"{'退職金':>12s} {'控除':>11s} {'所得税':>10s} {'住民税':>10s} {'税金合計':>10s} {'手取り':>12s} {'負担率'}")
    for r in payout_grid(25):
        print(f"{r['payout']:11,d}円 {r['deduction']:10,d}円 {r['income_tax']:9,d}円 "
              f"{r['resident_tax']:9,d}円 {r['total']:9,d}円 {r['net']:11,d}円  {r['rate']:.1%}")

    print("\n=== 勤続5年以下だと2分の1が効かない範囲がある（退職金1500万円・役員以外）===")
    print(f"{'勤続年数':>8s} {'短期の扱いか':>12s} {'通常の税金':>11s} {'短期の税金':>11s} {'差'}")
    for r in short_term_grid(15_000_000):
        mark = "短期になる" if r["applies"] else "ならない"
        print(f"{r['years']:6d}年 {mark:>12s} {r['normal']:10,d}円 {r['short']:10,d}円  "
              f"{r['diff']:,}円")
