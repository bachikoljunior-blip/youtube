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

from . import _checks

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

    # 速算表の形と連続性は `_checks` にまとめてある（12本が同じものを書いていた）。
    _checks.bracket_table(TAX_TABLE, income_tax_raw, name="所得税の速算表")

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

    # --- 2026-08-17 に足した節ぶん（`docs/JOURNAL.md` M17）------------------
    # **主張そのものを検査に置くこと。** 汎用の検査では守れません。
    # 1. 役員のほうが必ず重い（全額 対 300万円を超える部分だけ）
    for row in officer_grid():
        if row["diff"] <= 0:
            raise _checks.TableError(
                f"退職金{row['payout']:,}円で、役員のほうが軽い（{row['diff']:,}円）。"
                "**節の主張と符号が逆**です")
    # 2. 1日で21年になり、控除が RATE_OVER だけ増える
    if deduction(YEARS_BORDER + 0.01) - deduction(YEARS_BORDER) != RATE_OVER:
        raise ValueError("20年と1日で、控除が70万円ふえていない")
    for row in one_day_grid():
        if row["gain"] <= 0:
            raise _checks.TableError(
                f"退職金{row['payout']:,}円で、1日長く勤めたのに手取りが増えていない")
    # 3. 実効の負担率は天井を超えない。**天井は率から独立に出す**
    ceiling = effective_rate_ceiling()
    _checks.close(ceiling, (0.45 * 1.021 + 0.10) / 2, "実効の負担率の天井")
    for row in effective_rate_grid():
        if row["rate"] >= ceiling:
            raise _checks.TableError(
                f"退職金{row['payout']:,}円の実効 {row['rate']:.4f} が"
                f"天井 {ceiling:.4f} 以上。**2分の1課税が効いていません**")
    _checks.increases_with(
        lambda p: tax(int(p), 30)["total"] / p, [20_000_000, 80_000_000, 200_000_000],
        "退職金が増えたのに、実効の負担率が上がっていない")

    # --- 2026-08-25 に足した節ぶん（控除の「単価」）------------------------
    # **主張は3つあり、3つとも数で置きます。**
    # 4. 単価は「下がって、上がる」——端が頂点なら形が違う
    units = [deduction(a) / a for a in (1, 2, 3, 5, 10, 20, 21, 25, 30, 40)]
    bottom = units.index(min(units))
    if bottom in (0, len(units) - 1):
        raise _checks.TableError(
            f"控除の単価の底が端に来ています（下がって上がる形になっていない）: {units}")
    if units[0] != float(DEDUCTION_FLOOR):
        raise _checks.TableError(
            f"勤続1年の単価が下限の {DEDUCTION_FLOOR:,}円 になっていません: {units[0]:,.0f}")
    # 5. **2年目から20年目までは、単価が動かない**（平ら）
    flat = {deduction(a) / a for a in range(2, YEARS_BORDER + 1)}
    if flat != {float(RATE_UNDER)}:
        raise _checks.TableError(f"2年目から20年目の単価が平らではありません: {sorted(flat)}")
    # 6. **1年目の単価には二度と追いつかない**（解が負・40年でも差が残る）
    never = deduction_unit_never_recovers()
    if never["追いつく勤続年数"] >= 0:
        raise _checks.TableError(
            "1年目の単価に追いつく勤続年数が正で出ています: "
            f"{never['追いつく勤続年数']:.1f}年。**節の主張と逆**です")
    _checks.greater(never["40年でも残る差"], 0, "40年勤めても1年目の単価に残る差が")
    _checks.increases_with(
        lambda a: deduction(int(a)) / a, [YEARS_BORDER + 1, 30, 40],
        "20年を超えたのに、控除の単価が上がっていない")


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



def officer_grid(payouts: list[int] | None = None, years: float = 5) -> list[dict]:
    """勤続5年以下で、**役員か役員以外か**だけを変えたときの税金。

    2つの例外は同じ2022年改正で入りましたが、**効き方が違います** ——
    役員は全額、役員以外は300万円を超える部分だけが2分の1になりません。
    """
    payouts = payouts or [5_000_000, 10_000_000, 15_000_000, 20_000_000, 30_000_000]
    out = []
    for p in payouts:
        o = tax(p, years, officer=True)["total"]
        e = tax(p, years, short_term=True)["total"]
        out.append({"payout": p, "officer": o, "employee": e, "diff": o - e})
    return out


def one_day_grid(payouts: list[int] | None = None) -> list[dict]:
    """**20年ちょうど**と**20年と1日**で、手取りがどれだけ変わるか。

    勤続年数は1年未満を切り上げるので、1日でも超えれば21年で数えます。
    控除の単価が跳ねる境目（`YEARS_BORDER`）と重なるので、**1日が効きます。**
    """
    payouts = payouts or [10_000_000, 20_000_000, 30_000_000, 40_000_000]
    out = []
    for p in payouts:
        a = tax(p, YEARS_BORDER)["net"]
        b = tax(p, YEARS_BORDER + 0.01)["net"]
        out.append({"payout": p, "net_20": a, "net_21": b, "gain": b - a})
    return out


def effective_rate_ceiling() -> float:
    """退職金をいくら増やしても超えない、実効の負担率。

    課税されるのが**控除を引いた額の2分の1**なので、
    いちばん高い税率の組み合わせを半分にした値が上限になります。
    """
    top_rate = TAX_TABLE[-1][1]
    return (top_rate * (1 + RECONSTRUCTION) + RESIDENT_RATE) / 2


def effective_rate_grid(years: float = 30, payouts: list[int] | None = None) -> list[dict]:
    """退職金べつの実効の負担率。**天井に近づくが、超えない。**"""
    payouts = payouts or [10_000_000, 20_000_000, 40_000_000, 80_000_000,
                          200_000_000, 1_000_000_000]
    out = []
    for p in payouts:
        t = tax(p, years)["total"]
        out.append({"payout": p, "total": t, "rate": t / p})
    return out


# ---- 控除の「単価」（2026-08-25 に足した節）------------------------------
#
# **`free_line()` と同じ数字を割っただけですが、形が逆を向きます。**
# 総額は勤続年数について単調に増えるので、棒は右肩上がりの1本調子です。
# 割った単価は **下がってから上がる** ので、絵がまったく別のものになります。
def deduction_unit_grid(years: list[int] | None = None) -> list[dict]:
    """**勤続1年あたりに直した退職所得控除**（＝控除の「単価」）。

    単価が動く理由は控除の下限（`DEDUCTION_FLOOR` ＝ 80万円）です。
    勤続1年でも80万円が保証されるので **1年目だけ単価が80万円**になり、
    2年目で 40万円 に落ちます（80万円 ÷ 2年）。そこから20年までは
    40万円 で平ら、20年を超えると1年あたり 70万円 が足されるので
    単価は上がり始めますが、**上がりきりません**（`deduction_unit_never_recovers`）。
    """
    check_tables()
    years = years or [1, 2, 3, 5, 10, 20, 21, 25, 30, 35, 40]
    return [{"years": a, "deduction": deduction(a),
             "per_year": deduction(a) / a} for a in years]


def deduction_unit_never_recovers() -> dict:
    """**1年目の単価（80万円）に追いつく勤続年数は、存在しない。**

    20年超の単価は `(40万×20 + 70万×(a−20)) ÷ a` で、`a` を伸ばすと
    `RATE_OVER`（70万円）に近づきます。**70万 < 80万** なので、
    どれだけ長く勤めても1年目の単価には届きません。

    「いつ追いつくか」を式で解くと `a` が**負**になります。
    ここではその `a` を返して、**追いつかないことを数で示します。**

    （`check_tables()` はここから呼びません。**この関数を検査が呼ぶ**ので、
    呼ぶと再帰します。`officer_grid` などと同じ扱いです）
    """
    # (RATE_UNDER*20 + RATE_OVER*(a-20)) / a = DEDUCTION_FLOOR を a について解く
    numer = float(RATE_UNDER * YEARS_BORDER - RATE_OVER * YEARS_BORDER)
    denom = float(DEDUCTION_FLOOR - RATE_OVER)
    return {
        "追いつく勤続年数": numer / denom,
        "単価が近づく先": float(RATE_OVER),
        "1年目の単価": float(DEDUCTION_FLOOR),
        "40年でも残る差": DEDUCTION_FLOOR - deduction(40) / 40,
    }


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    # **行は5年とびで並んでいます。** 2026-08-15 の最初の版は、この列に
    # 前の行との差そのものを出しながら見出しを「1年あたり」と書いていました
    # （200万円/年に見える）。値は合っていて、嘘をついていたのは見出しです。
    # `per_unit_steps` は見出しの単位で実際に割るので、同じ間違いは書けません。
    LABEL = "1年あたりの伸び"
    print("\n=== 税金が1円もかからない退職金の上限（勤続年数べつ）===")
    print(f"{'勤続年数':>8s} {'ここまで無税':>12s}  {LABEL}")
    rows = free_line()
    for r, step in zip(rows, _checks.per_unit_steps(
            rows, "years", "free", label=LABEL, x_unit="年")):
        cell = "—" if step is None else f"{step:,.0f}円/年"
        print(f"{r['years']:6d}年 {r['free']:11,d}円  {cell}")

    print("\n=== 控除の単価は1年目がいちばん高く、そこへは二度と戻らない（勤続年数べつ）===")
    print(f"{'勤続年数':>8s} {'控除の総額':>12s} {'1年あたりの単価'}")
    for r in deduction_unit_grid():
        print(f"{r['years']:6d}年 {r['deduction']:11,d}円  {r['per_year']:,.0f}円/年")
    nv = deduction_unit_never_recovers()
    print(f"  → 控除には下限 {DEDUCTION_FLOOR:,}円 があるので、"
          f"**勤続1年の単価だけが {nv['1年目の単価']:,.0f}円/年** になります。"
          f"2年目で {RATE_UNDER:,}円/年 に落ち、20年目まで平らです")
    print(f"  → 20年を超えると1年あたり {RATE_OVER:,}円 が足されるので単価は戻り始めますが、"
          f"**近づく先は {nv['単価が近づく先']:,.0f}円/年**（20年超の単価そのもの）。"
          f"1年目の {nv['1年目の単価']:,.0f}円/年 より低いので、**追いつきません**")
    print(f"  → 式で解くと、追いつく勤続年数は **{nv['追いつく勤続年数']:.0f}年**（負の数）。"
          f"40年勤めても **{nv['40年でも残る差']:,.0f}円/年** の差が残ります。"
          "**総額は増え続けるのに、1年あたりの値打ちは1年目が頂点**です")

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

    print("\n=== 同じ勤続5年・同じ退職金でも、「役員」かどうかで税金が変わる ===")
    print(f"{'退職金':>12s} {'役員の税金':>12s} {'役員以外の税金':>13s} {'差'}")
    for r in officer_grid():
        print(f"{r['payout']:11,d}円 {r['officer']:11,d}円 {r['employee']:12,d}円  "
              f"**{r['diff']:,}円**")
    print("  → 役員は**全額が課税対象**、役員以外は**300万円を超える部分だけ**が"
          "2分の1になりません（どちらも勤続5年以下）。"
          "**勤めた年数も受け取った額も同じ**なのに、肩書きだけで変わります")

    print("\n=== 20年ちょうどで辞めるか、1日だけ長く勤めるかで、手取りが変わる ===")
    print(f"{'退職金':>12s} {'20年ちょうど':>13s} {'20年と1日':>13s} {'手取りの差'}")
    for r in one_day_grid():
        print(f"{r['payout']:11,d}円 {r['net_20']:12,d}円 {r['net_21']:12,d}円  "
              f"**+{r['gain']:,}円**")
    print(f"  → 勤続年数は**1年未満を切り上げ**て数えるので、"
          f"20年と1日は**21年**として扱われます。控除が {RATE_OVER:,}円 増え、"
          "その半分が課税から外れます。**1日で決まります**")

    print("\n=== 退職金がいくら高くても、実効の負担率は27パーセント台で頭打ちになる ===")
    print(f"{'退職金':>15s} {'税金合計':>15s} {'実効の負担率'}")
    for r in effective_rate_grid():
        print(f"{r['payout']:14,d}円 {r['total']:14,d}円  {r['rate'] * 100:6.2f}%")
    print(f"  → 課税されるのが**控除を引いた額の2分の1**なので、"
          f"いちばん高い税率でも実効はその半分に落ちます。"
          f"上限は **{effective_rate_ceiling() * 100:.2f}パーセント**で、"
          "これは退職金をいくら増やしても超えません")
