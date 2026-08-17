"""**贈与税を「1年のばす」効きは、途中から毎年ぴったり11万円で一定になります。**

一般の解説はここで止まります ——「贈与税には年110万円の基礎控除がある。
まとめて渡すと高いので、何年かに分けたほうがよい」。

**分けたほうが安いのは本当です。問題は「何年に分けるか」を決める材料が無いことです。**
出回っているのは速算表そのものか、「110万円ずつなら無税」の2点だけで、
**その途中がどこにも書かれていません。**

1000万円を特例税率で贈与する場合の、年数ごとの総税額を全部計算しました。

    1年 177万円 ／ 2年 97万円 ／ 3年 70万5000円 ／ 4年 56万円 ／ 5年 45万円
    6年 34万円 ／ 7年 23万円 ／ 8年 12万円 ／ 9年 9999円 ／ 10年 0円

**ここから2つ、計算しないと出てこないことが分かります。**

**1つめ。5年目から先は、1年のばすごとに税額がぴったり11万円ずつ減ります。**
45万→34万→23万→12万。これは偶然ではなく、**1年あたりの贈与額が最低税率10パーセントの
帯に入ったあとは、総税額が「贈与額の10パーセント − 11万円×年数」という直線になる**
からです。傾きの11万円は、**基礎控除110万円に税率10パーセントを掛けた額**そのものです。
**表を引いても出てきません。年数で微分して初めて出る数字です。**

**2つめ。「2年に分ければ半分」は成り立ちません。** 1年の177万円に対し、
2年に分けると97万円で、**半分の88万5000円には届きません**（8万5000円ぶん高い）。
年数に反比例するという見立てが実際より安く出るのは2年から6年までで、
**7年目でようやく逆転します**（反比例の見立て25万2857円に対し、実際は23万円）。
**分割は「効きが一定」でも「反比例」でもなく、途中で向きが変わります。**

## この計算で見ないもの（前提として画面に出す）

- **暦年課税だけ**です。相続時精算課税を選んだ場合は別の計算になります。
- 相続が開始したとき、その前の一定期間の贈与を相続財産に足し戻す制度があります。
  **ここではその加算の対象にならない場合の贈与税額だけ**を出しています。
- **贈与を受けた人が1年に複数の人からもらった場合**は、合計してから基礎控除を引きます。
  ここでは1人から1人への贈与だけを見ています。
- 住宅取得資金や教育資金の非課税制度は入れていません。
"""
from __future__ import annotations

from . import _checks

BASIC = 1_100_000   # 暦年課税の基礎控除。年110万円（相続税法21条の5・措置法70条の2の4）

# ---- 贈与税の速算表（基礎控除後の課税価格, 税率, 控除額）。上限 None が最上段 ----
# **一般税率**: 特例税率に当たらない贈与（兄弟間・夫婦間・親から未成年の子など）
GENERAL: list[tuple[int | None, float, int]] = [
    (2_000_000, 0.10, 0),
    (3_000_000, 0.15, 100_000),
    (4_000_000, 0.20, 250_000),
    (6_000_000, 0.30, 650_000),
    (10_000_000, 0.40, 1_250_000),
    (15_000_000, 0.45, 1_750_000),
    (30_000_000, 0.50, 2_500_000),
    (None, 0.55, 4_000_000),
]

# **特例税率**: 直系尊属（父母・祖父母）から、その年の1月1日に18歳以上の子や孫への贈与
SPECIAL: list[tuple[int | None, float, int]] = [
    (2_000_000, 0.10, 0),
    (4_000_000, 0.15, 100_000),
    (6_000_000, 0.20, 300_000),
    (10_000_000, 0.30, 900_000),
    (15_000_000, 0.40, 1_900_000),
    (30_000_000, 0.45, 2_650_000),
    (45_000_000, 0.50, 4_150_000),
    (None, 0.55, 6_400_000),
]

ASSUMPTIONS = [
    "暦年課税の贈与税だけを計算しています。相続時精算課税を選んだ場合は別の計算になります",
    "基礎控除は年110万円です。1年のあいだに複数の人からもらった場合は、合計してから引きます",
    "特例税率は、父母や祖父母から、その年の1月1日に18歳以上である子や孫への贈与に使います",
    "一般税率は、それ以外の贈与に使います。兄弟のあいだ、夫婦のあいだ、未成年の子への贈与が入ります",
    "相続が始まったとき、その前の一定期間の贈与を相続財産に足し戻す制度があります。ここでは足し戻しの対象にならない場合の税額です",
    "住宅取得資金や教育資金の非課税制度は使っていません",
    "税額は円未満を切り捨てています",
    "毎年おなじ額を贈与する前提で計算しています。年ごとに額を変えると総額が同じでも税額は変わります",
]

# **表の中ほどを思い出しで書いていないと言うための点**（`shahoken.py` と同じ考え方）。
# 基礎控除を引いたあとの課税価格 → 一般税率での税額 / 特例税率での税額。
# 端・低い側・両表が分かれる中ほど・高い側に散らしてある。**1段でも取り違えれば外れます。**
ANCHORS: list[tuple[int, int, int]] = [
    (2_000_000, 200_000, 200_000),      # 200万：両表とも10パーセントで、まだ同じ
    (3_000_000, 350_000, 350_000),      # 300万：一般は15パーセントの段の端、特例も15パーセント
    (4_000_000, 550_000, 500_000),      # 400万：ここで初めて差が出る（一般20／特例15）
    (6_000_000, 1_150_000, 900_000),    # 600万：一般30／特例20
    (10_000_000, 2_750_000, 2_100_000),  # 1000万：一般40／特例30
    (15_000_000, 5_000_000, 4_100_000),  # 1500万：一般45／特例40
    (30_000_000, 12_500_000, 10_850_000),  # 3000万：一般50／特例45
    (45_000_000, 20_750_000, 18_350_000),  # 4500万：特例50パーセントの段の端
]


def tax_of(base: float, table: list[tuple[int | None, float, int]]) -> float:
    """速算表を引く。`base` は**基礎控除を引いたあと**の課税価格。"""
    if base <= 0:
        return 0.0
    for cap, rate, sub in table:
        if cap is None or base <= cap:
            return base * rate - sub
    raise ValueError(f"速算表に当たらない: {base}")


def gift_tax(amount: float, *, special: bool = True) -> int:
    """1年に `amount` 円もらったときの贈与税。円未満は切り捨て。"""
    return int(tax_of(max(0.0, amount - BASIC), SPECIAL if special else GENERAL))


def split_total(amount: float, years: int, *, special: bool = True) -> int:
    """`amount` 円を `years` 年に**均等に分けて**渡したときの、贈与税の総額。"""
    if years < 1:
        raise ValueError("年数は1以上")
    return gift_tax(amount / years, special=special) * years


def years_to_zero(amount: float) -> int:
    """税額が0円になる最短の年数。**基礎控除110万円だけで収まる年数**です。"""
    import math
    return max(1, math.ceil(amount / BASIC))


def split_grid(amount: float = 10_000_000, upto: int = 10,
               *, special: bool = True) -> list[dict]:
    """年数ごとの総税額と、「1年のばすと浮く額」の表。"""
    rows = []
    prev: int | None = None
    for n in range(1, upto + 1):
        total = split_total(amount, n, special=special)
        rows.append({
            "years": n,
            "per_year": int(amount / n),
            "total_tax": total,
            "saved_by_one_more_year": None if prev is None else prev - total,
            "effective_rate": round(total / amount * 100, 2),
        })
        prev = total
    return rows


def rate_gap_grid(amounts: tuple[int, ...] = (
        3_000_000, 5_000_000, 10_000_000, 20_000_000, 30_000_000,
        50_000_000)) -> list[dict]:
    """同じ額でも、**誰から誰への贈与か**で税額がいくら違うかの表。"""
    rows = []
    for amount in amounts:
        general = gift_tax(amount, special=False)
        special = gift_tax(amount, special=True)
        rows.append({
            "amount": amount,
            "general_tax": general,
            "special_tax": special,
            "gap": general - special,
            "gap_ratio": round((general - special) / general * 100, 1) if general else 0.0,
        })
    return rows



def special_gap_grid(amounts: tuple[int, ...] = (
        3_000_000, 6_000_000, 10_000_000, 15_000_000, 30_000_000,
        45_000_000, 46_100_000, 60_000_000, 100_000_000)) -> list[dict]:
    """一般税率と特例税率の**差**。**この差は途中で頭打ちになります。**

    どちらの表も最上段は同じ55パーセントなので、**両方が最上段に入ったところで
    差が増えなくなります**（上に行くほど得、ではありません）。
    """
    out = []
    for a in amounts:
        g = gift_tax(a, special=False)
        sp = gift_tax(a, special=True)
        out.append({"amount": a, "general": g, "special": sp, "gap": g - sp})
    return out


def special_gap_ceiling(step: int = 1_000, upto: int = 200_000_000) -> tuple[int, int]:
    """差が頭打ちになる**最初の贈与額**と、そのときの差を返す。

    **刻みは1000円**（1万円刻みで探すと、境目を1万円ぶん取り違えます）。
    """
    best_gap, first_at = 0, 0
    for a in range(BASIC, upto + step, step):
        gap = gift_tax(a, special=False) - gift_tax(a, special=True)
        if gap > best_gap:
            best_gap, first_at = gap, a
    return first_at, best_gap


def effective_rate_grid(amounts: tuple[int, ...] = (
        5_000_000, 10_000_000, 50_000_000, 100_000_000, 1_000_000_000),
        special: bool = True) -> list[dict]:
    """贈与額べつの実効の税率。**最高税率に近づきますが、届きません。**"""
    return [{"amount": a, "tax": gift_tax(a, special=special),
             "rate": gift_tax(a, special=special) / a} for a in amounts]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""

    # --- 2026-08-17 に足した節ぶん（`docs/JOURNAL.md` M17）------------------
    # **主張そのものを検査に置くこと。**
    at, gap = special_gap_ceiling()
    if gap != 2_400_000:
        raise ValueError(f"特例税率で得する額の頭打ちが {gap:,}円。表からは 2,400,000円")
    # **頭打ちであること** —— そこから上でいくら増やしても差が変わらない
    for a in (at, at + 10_000_000, at + 100_000_000):
        if gift_tax(a, special=False) - gift_tax(a, special=True) != gap:
            raise ValueError(f"贈与{a:,}円で差が {gap:,}円 から動いた。**節の主張は頭打ち**")
    # **その1000円手前ではまだ小さいこと**（頭打ちの「最初の点」であること）
    if gift_tax(at - 1_000, special=False) - gift_tax(at - 1_000, special=True) >= gap:
        raise ValueError("頭打ちの手前で、もう差が最大になっている")
    # 実効の税率は最高税率に届かない
    top = SPECIAL[-1][1]
    for r in effective_rate_grid():
        if r["rate"] >= top:
            raise ValueError(f"実効 {r['rate']:.4f} が最高税率 {top} 以上。速算表の控除が効いていない")
    _checks.statutory(BASIC, 1_100_000, "暦年課税の基礎控除",
                      source="相続税法21条の5・租税特別措置法70条の2の4")

    # 1. 速算表の形（段が上がること・境目で切れ目がないこと）
    _checks.bracket_table(GENERAL, lambda b: tax_of(b, GENERAL), name="贈与税の速算表（一般税率）")
    _checks.bracket_table(SPECIAL, lambda b: tax_of(b, SPECIAL), name="贈与税の速算表（特例税率）")

    # 2. 表の中ほどを思い出しで書いていないと言うための点
    # **円未満を切り捨てた値で突き合わせます。**速算表は率を掛けてから控除額を引くので、
    # 浮動小数の端数が出ます（4500万円の一般税率が 20,750,000.000000004 になりました）。
    for base, want_general, want_special in ANCHORS:
        _checks.rounding(int(tax_of(base, GENERAL)), want_general,
                         f"一般税率・課税価格{base:,}円の税額")
        _checks.rounding(int(tax_of(base, SPECIAL)), want_special,
                         f"特例税率・課税価格{base:,}円の税額")

    # 3. この計算の主題そのもの
    # (a) 特例税率は一般税率より重くならない。200万円までは同額
    for base in (1_000_000, 2_000_000, 4_000_000, 10_000_000, 45_000_000):
        if tax_of(base, SPECIAL) > tax_of(base, GENERAL):
            raise _checks.TableError(
                f"課税価格{base:,}円で特例税率のほうが重い（表の取り違え）")
    _checks.rounding(tax_of(2_000_000, SPECIAL), tax_of(2_000_000, GENERAL),
                     "200万円までは両表が同額であること")
    _checks.greater(tax_of(4_000_000, GENERAL), tax_of(4_000_000, SPECIAL),
                    "400万円で一般税率のほうが重くなっていない（差が出る最初の段）")

    # (b) 基礎控除より下は0円、1円超えたところから課税
    _checks.rounding(gift_tax(BASIC), 0, "110万円ちょうどの贈与税")
    if gift_tax(BASIC + 1_000_000) <= 0:
        raise _checks.TableError("基礎控除を超えたのに贈与税が0円")

    # (c) **主題**: 分ける年数を増やすと総税額は減り、増えることはない
    _checks.never_decreases(lambda n: -split_total(10_000_000, int(n)),
                            [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
                            "年数を増やしたのに贈与税の総額が増えている")
    # (d) **主題その1**: 「2年に分ければ半分」は成り立たない。
    # **書いたときは逆を書いていて、この検査に落とされました**（2026-08-16）。
    # 見立て（反比例）のほうが安く出ます。差は実測で8万5000円。
    one, two = split_total(10_000_000, 1), split_total(10_000_000, 2)
    _checks.greater(two, one / 2,
                    "2年に分けた総税額が、1年ぶんの半分以下になっている（反比例の見立てと逆）")

    # (e) **主題その2**: 1年あたりが最低税率の帯に入ってからは、
    # 1年のばすごとに **基礎控除×最低税率** ちょうどずつ減る（＝直線）。
    # 傾きが表に載っていないので、ここで固定しておく。
    slope = BASIC * SPECIAL[0][1]     # 110万円 × 10パーセント ＝ 11万円
    for n in (5, 6, 7, 8):
        got = split_total(10_000_000, n) - split_total(10_000_000, n + 1)
        # 1年あたりの額を整数に丸めるぶん、数円ずれます
        if abs(got - slope) > 10:
            raise _checks.TableError(
                f"{n}年→{n + 1}年で減った額が {got:,.0f} 円。"
                f"最低税率の帯では {slope:,.0f} 円のはず（基礎控除×最低税率）")
    # (f) 0円になる年数と、実際に0円になる点が一致すること
    n0 = years_to_zero(10_000_000)
    _checks.rounding(split_total(10_000_000, n0), 0, f"1000万円を{n0}年に分けたときの総税額")
    if split_total(10_000_000, n0 - 1) <= 0:
        raise _checks.TableError(f"{n0 - 1}年でも0円なら、0円になる年数の計算が違う")
    # (g) 「1年のばすと浮く額」は、**帯に入るまでは**急に小さくなり、入ったあとは一定。
    # **ここは最初「ずっと小さくなり続ける」と書いて落ちました**（2026-08-16）。
    # 実測は 80万→26万5000→14万5000→11万→11万→11万→11万→11万 で、
    # **後半は下がりません**（下がると (e) の直線が壊れます）。曲がるのは前半だけです。
    saved = [r["saved_by_one_more_year"] for r in split_grid(10_000_000, 9)
             if r["saved_by_one_more_year"] is not None]
    _checks.ascending(list(reversed(saved[:4])),
                      "帯に入るまでの「1年のばすと浮く額」が、後ろの年ほど小さくなっていない")
    for got in saved[4:]:
        if abs(got - slope) > 10:
            raise _checks.TableError(
                f"帯に入ったあとの「1年のばすと浮く額」が {got:,} 円。"
                f"{slope:,.0f} 円で一定のはず")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 1000万円を何年に分けるか。税額は年数に反比例しない ===")
    for row in split_grid(10_000_000, 10):
        saved = row["saved_by_one_more_year"]
        print(f"{row['years']:2d}年  1年あたり {row['per_year']:>9,}円  "
              f"総税額 {row['total_tax']:>9,}円  実効 {row['effective_rate']:>5.2f}%  "
              f"1年のばすと浮く額 {'—' if saved is None else f'{saved:,}円'}")

    print("\n=== 同じ額でも、誰から誰への贈与かで税額が変わる ===")
    for row in rate_gap_grid():
        print(f"{row['amount']:>11,}円  一般 {row['general_tax']:>9,}円  "
              f"特例 {row['special_tax']:>9,}円  差 {row['gap']:>8,}円（{row['gap_ratio']}%）")

    print("\n=== 基礎控除110万円のすぐ上。またいでも税額はすぐには出ない ===")
    for amount in (1_100_000, 1_100_001, 1_200_000, 2_000_000, 3_100_000):
        print(f"贈与額 {amount:>9,}円  特例 {gift_tax(amount):>8,}円  "
              f"一般 {gift_tax(amount, special=False):>8,}円")

    print("\n=== 無税で渡し切るには何年かかるか。一括の税額と並べる ===")
    for amount in (5_000_000, 10_000_000, 20_000_000, 30_000_000, 50_000_000):
        n = years_to_zero(amount)
        print(f"{amount:>11,}円  0円になる年数 {n:>3d}年  "
              f"1年で渡した場合の税額 {gift_tax(amount):>10,}円")

    at, gap = special_gap_ceiling()
    print(f"\n=== 特例税率で得する額は{gap // 10_000}万円で頭打ち"
          f"（贈与{at // 10_000}万円から上は、いくら増えても変わらない）===")
    print(f"{'贈与額':>13s} {'一般税率の税':>13s} {'特例税率の税':>13s} {'差'}")
    for r in special_gap_grid():
        mark = "  ← **ここから増えない**" if r["amount"] == at else ""
        print(f"{r['amount']:12,d}円 {r['general']:12,d}円 {r['special']:12,d}円  "
              f"**{r['gap']:,}円**{mark}")
    print("  → どちらの表も最上段は**同じ55パーセント**なので、"
          "**両方が最上段に入った時点で差が増えなくなります。**"
          "「親から子への贈与は得」は本当ですが、**得する額には上限があります**")

    print("\n=== 贈与税の実効の税率は、55パーセントに近づくが届かない（特例税率）===")
    print(f"{'贈与額':>15s} {'税額':>15s} {'実効の税率'}")
    for r in effective_rate_grid():
        print(f"{r['amount']:14,d}円 {r['tax']:14,d}円  {r['rate'] * 100:6.2f}%")
    print("  → 速算表の控除額が効くので、**最高税率の55パーセントは名目です。**"
          "10億円を一度に贈与しても実効は54.30パーセントで、"
          "**額を増やすほど55に近づきますが、超えることはありません**")
