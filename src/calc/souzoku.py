"""相続税を、法定相続分課税方式のとおりに最後まで計算する。

**既存の calc 11本が、全部「現役世代の給与まわり」でした**（2026-08-15 に確認）。
手取り・残業代・失業・傷病・退職金・副業・ふるさと納税・住宅ローン・医療費・
控除・年金。**財産の側を計算するモジュールが1本もありません。**

在庫の天井は `topic_forge.py` が数える「計算の節」で、8/15 21:xx の時点で
**54節すべてが使用済み・未使用0件**でした。節を増やす道は
`src/calc/` に新しい表を足すことだけです（`docs/MEANS.md` M14）。

## なぜ相続税を選んだか

これまでの実測で伸びた動画には2つの軸がありました（`iryohi.py` の観察）——
**「取り返せる／損している」×「対象が広い」**。相続税はどちらにも乗ります。

- **対象が広い。** 親に持ち家があれば、金額の桁だけで基礎控除を超えます
- **誤解の的がはっきりしている。** 「配偶者は1億6000万まで無税だから、
  一次相続は全部配偶者に寄せれば得」——**これは二次相続を足すと逆転します。**
  逆転する金額は財産額と子の人数で動き、**表になっていません**

そして**この逆転点は、どこにも公開されていない数字です。**
制度の解説ではなく、こちらが計算した結果を発表する（`CLAUDE.md` の根幹）。

## 計算の中身（国税庁の順序をそのまま）

    1. 課税価格の合計 － 基礎控除（3,000万 ＋ 600万 × 法定相続人の数）
       ＝ 課税遺産総額
    2. 課税遺産総額を**法定相続分**で按分する（実際の分け方ではない）
    3. 按分した額それぞれに速算表を当て、足し戻す ＝ **相続税の総額**
    4. 相続税の総額を、**実際に取得した割合**で按分 ＝ 各人の税額
    5. 配偶者の税額軽減を引く

**2 と 4 で割合が2回出てきて、しかも別物です。** ここが混ざると答えが変わります。

## 入れていないもの（前提が追えなくなるので、1本に混ぜない）

小規模宅地等の特例、生命保険金・死亡退職金の非課税枠、相続時精算課税、
生前贈与の加算、未成年者控除・障害者控除、2割加算（配偶者と子だけを扱う）、
相続税の申告期限や延納。**どれも条件が別立てで、画面に前提を全部出せません。**
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "法定相続人は配偶者と子だけとして計算しています",
    "基礎控除は3000万円に法定相続人1人あたり600万円を足した額です",
    "相続税の総額は、実際の分け方ではなく法定相続分で按分してから計算しています",
    "配偶者の税額軽減は、法定相続分と1億6000万円の多いほうまでとしています",
    "小規模宅地等の特例と生命保険金の非課税枠は含めていません",
    "二次相続では、配偶者が一次相続で取得した財産だけが残るとしています",
    "相続人どうしの争いや、申告期限までの分割ができない場合は考えていません",
]

# 制度の値。**2015年1月1日の改正からこの表で動いています。**
# 改正が続くものは入力に逃がす（docs/CONSTRAINTS.md B4）が、
# ここは基礎控除・速算表とも長く据え置かれている。
BASE_DEDUCTION = 30_000_000      # 基礎控除の定額部分（円）
PER_HEIR_DEDUCTION = 6_000_000   # 法定相続人1人あたりの加算（円）
SPOUSE_FLOOR = 160_000_000       # 配偶者の税額軽減の下限（円）

# 相続税の速算表。(法定相続分に応ずる取得金額の上限, 税率, 控除額)
# 上限 None が最上段。**課税遺産総額そのものではなく、按分したあとの額に当てる。**
TAX_TABLE: list[tuple[int | None, float, int]] = [
    (10_000_000, 0.10, 0),
    (30_000_000, 0.15, 500_000),
    (50_000_000, 0.20, 2_000_000),
    (100_000_000, 0.30, 7_000_000),
    (200_000_000, 0.40, 17_000_000),
    (300_000_000, 0.45, 27_000_000),
    (600_000_000, 0.50, 42_000_000),
    (None, 0.55, 72_000_000),
]

SPOUSE_SHARE = 0.5  # 配偶者と子が相続人のときの、配偶者の法定相続分


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 速算表の形と連続性は `_checks` にまとめてある（12本が同じものを書いていた）。
    _checks.bracket_table(TAX_TABLE, tax_of, name="相続税の速算表")

    if BASE_DEDUCTION <= 0 or PER_HEIR_DEDUCTION <= 0:
        raise ValueError("基礎控除の値が正でない")
    # 相続人が1人増えれば基礎控除も増える
    if not basic_deduction(3) > basic_deduction(2):
        raise ValueError("相続人が増えたのに基礎控除が増えていない")
    # 基礎控除以下なら相続税の総額は0
    if total_tax(basic_deduction(3), 3) != 0:
        raise ValueError("基礎控除ちょうどなのに相続税が出ている")
    # 財産が増えれば総額も増える
    if not total_tax(200_000_000, 3) > total_tax(100_000_000, 3):
        raise ValueError("財産が増えたのに相続税が増えていない")
    # 相続人が増えれば総額は減る（基礎控除と按分の両方が効く）
    if not total_tax(200_000_000, 4) < total_tax(200_000_000, 3):
        raise ValueError("相続人が増えたのに相続税が減っていない")
    # 財産が1億6000万円以下なら、配偶者に全部寄せた一次相続の納税は0になる
    if first_estate(150_000_000, 2, 1.0)["paid"] != 0:
        raise ValueError("1億5000万を配偶者に全部寄せたのに一次相続で納税が出ている")
    # **1億6000万を超えた分は、配偶者でも課税される。**
    # 「配偶者は1億6000万まで無税」を「配偶者なら無税」と読むと、ここで外れる。
    if first_estate(200_000_000, 2, 1.0)["paid"] <= 0:
        raise ValueError("1億6000万を超えて寄せたのに一次相続の納税が0になっている")


def basic_deduction(heirs: int) -> int:
    """基礎控除。**法定相続人の数だけで決まる。** 財産額とは無関係。"""
    if heirs < 1:
        raise ValueError("法定相続人は1人以上")
    return BASE_DEDUCTION + PER_HEIR_DEDUCTION * heirs


def tax_of(amount: int) -> int:
    """速算表を1回当てる。**按分したあとの金額に当てること。**"""
    if amount <= 0:
        return 0
    for cap, rate, sub in TAX_TABLE:
        if cap is None or amount <= cap:
            return int(amount * rate) - sub
    raise AssertionError("速算表に当たらなかった")


def statutory_shares(children: int, spouse: bool) -> list[float]:
    """法定相続分。配偶者がいれば2分の1、残りを子で等分する。"""
    if children < 0 or (children == 0 and not spouse):
        raise ValueError("法定相続人がいない")
    if not spouse:
        return [1.0 / children] * children
    if children == 0:
        return [1.0]
    return [SPOUSE_SHARE] + [(1 - SPOUSE_SHARE) / children] * children


def total_tax(estate: int, heirs: int, children: int | None = None,
              spouse: bool = True) -> int:
    """相続税の**総額**。ここまでは、誰がいくら取るかに一切よらない。

    `heirs` は法定相続人の数、`children` は子の数。省略すると
    配偶者あり（`heirs - 1` 人が子）とみなす。
    """
    if children is None:
        children = heirs - 1 if spouse else heirs
    taxable = max(estate - basic_deduction(heirs), 0)
    if taxable == 0:
        return 0
    return sum(tax_of(int(taxable * s)) for s in statutory_shares(children, spouse))


def spouse_relief(estate: int, heirs: int, spouse_ratio: float) -> int:
    """配偶者の税額軽減。**法定相続分と1億6000万円の、多いほうまで。**

    「1億6000万まで無税」だけが知られているが、法定相続分のほうが大きければ
    そちらが効く。財産3億・相続人が配偶者と子1人なら、法定相続分は1億5000万で
    1億6000万に届かないため、**この場合は1億6000万のほうが効く。**
    """
    gross = total_tax(estate, heirs)
    if gross == 0:
        return 0
    limit = max(int(estate * SPOUSE_SHARE), SPOUSE_FLOOR)
    covered = min(int(estate * spouse_ratio), limit)
    return int(gross * covered / estate)


def first_estate(estate: int, children: int, spouse_ratio: float) -> dict:
    """一次相続（配偶者が生きている側）。配偶者が `spouse_ratio` を取る。"""
    heirs = children + 1
    gross = total_tax(estate, heirs)
    spouse_gross = int(gross * spouse_ratio)
    relief = spouse_relief(estate, heirs, spouse_ratio)
    return {
        "estate": estate,
        "heirs": heirs,
        "basic_deduction": basic_deduction(heirs),
        "gross": gross,
        "spouse_ratio": spouse_ratio,
        "spouse_gross": spouse_gross,
        "relief": relief,
        "spouse_paid": max(spouse_gross - relief, 0),
        "children_paid": gross - spouse_gross,
        "paid": max(spouse_gross - relief, 0) + (gross - spouse_gross),
        "spouse_takes": int(estate * spouse_ratio),
    }


def second_estate(spouse_takes: int, children: int) -> dict:
    """二次相続。**配偶者が一次相続で取った財産を、子だけで相続する。**

    相続人が1人減り、配偶者の税額軽減も無くなる。**基礎控除も600万減ります。**
    """
    gross = total_tax(spouse_takes, children, children=children, spouse=False)
    return {
        "estate": spouse_takes,
        "heirs": children,
        "basic_deduction": basic_deduction(children),
        "paid": gross,
    }


def two_step(estate: int, children: int, spouse_ratio: float) -> dict:
    """一次と二次を足した、**本当に払う合計**。

    ここが `CLAUDE.md` の言う「どこにも公開されていない数字」です。
    一次相続だけを見ると配偶者に寄せるほど安く、**合計で見ると逆になります。**
    """
    first = first_estate(estate, children, spouse_ratio)
    second = second_estate(first["spouse_takes"], children)
    return {
        "spouse_ratio": spouse_ratio,
        "first_paid": first["paid"],
        "second_paid": second["paid"],
        "total": first["paid"] + second["paid"],
        "first": first,
        "second": second,
    }


def best_ratio(estate: int, children: int,
               steps: tuple[float, ...] = (0.0, 0.25, 0.5, 0.75, 1.0)) -> dict:
    """合計がいちばん小さくなる寄せ方と、いちばん大きい寄せ方の差。"""
    rows = [two_step(estate, children, r) for r in steps]
    best = min(rows, key=lambda r: r["total"])
    worst = max(rows, key=lambda r: r["total"])
    return {"best": best, "worst": worst, "gap": worst["total"] - best["total"],
            "rows": rows}


def threshold_grid() -> list[dict]:
    """基礎控除の境界。**財産がここを超えなければ、申告そのものが要らない。**"""
    check_tables()
    return [{"heirs": n, "deduction": basic_deduction(n)} for n in range(1, 7)]


def total_grid(children: int = 2) -> list[dict]:
    """財産べつの相続税の総額（配偶者と子）。**分け方によらない額です。**"""
    check_tables()
    heirs = children + 1
    return [
        {"estate": e, "deduction": basic_deduction(heirs),
         "taxable": max(e - basic_deduction(heirs), 0), "gross": total_tax(e, heirs)}
        for e in (50_000_000, 80_000_000, 100_000_000, 150_000_000,
                  200_000_000, 300_000_000)
    ]


def heirs_grid(estate: int = 150_000_000) -> list[dict]:
    """子の人数が1人ちがうと、総額がどれだけ変わるか。"""
    check_tables()
    return [
        {"children": c, "heirs": c + 1, "deduction": basic_deduction(c + 1),
         "gross": total_tax(estate, c + 1),
         "diff": total_tax(estate, c + 1) - total_tax(estate, c + 2)}
        for c in (1, 2, 3, 4)
    ]


def two_step_grid(estate: int = 150_000_000, children: int = 2) -> list[dict]:
    """配偶者にどれだけ寄せるかで、一次と二次の合計がどう動くか。"""
    check_tables()
    return [two_step(estate, children, r) for r in (0.0, 0.25, 0.5, 0.75, 1.0)]


def gap_grid(children: int = 2) -> list[dict]:
    """財産べつに「いちばん安い寄せ方」と「全部配偶者」の差を出す。"""
    check_tables()
    out = []
    for e in (80_000_000, 100_000_000, 150_000_000, 200_000_000, 300_000_000):
        r = best_ratio(e, children)
        allin = two_step(e, children, 1.0)
        out.append({
            "estate": e,
            "best_ratio": r["best"]["spouse_ratio"],
            "best_total": r["best"]["total"],
            "allin_total": allin["total"],
            "loss": allin["total"] - r["best"]["total"],
        })
    return out


def _man(yen: int) -> str:
    """円を万円で読む（画面に出す桁を1つにするため）。"""
    return f"{yen / 10_000:,.1f}万円"


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 法定相続人の数べつ 申告が要るかどうかの境界 ===")
    print(f"{'法定相続人':>8s} {'基礎控除':>12s}  この額までなら相続税はかからない")
    for r in threshold_grid():
        print(f"{r['heirs']:7d}人 {r['deduction']:11,d}円  {_man(r['deduction'])}")

    print("\n=== 財産べつの相続税の総額（配偶者と子2人）===")
    print(f"{'課税価格':>12s} {'基礎控除':>12s} {'課税遺産総額':>13s} {'相続税の総額':>13s}")
    for r in total_grid(2):
        print(f"{r['estate']:11,d}円 {r['deduction']:11,d}円 "
              f"{r['taxable']:12,d}円 {r['gross']:12,d}円")

    print("\n=== 子の人数が1人ちがうと総額がどれだけ変わるか（課税価格1億5000万円）===")
    print(f"{'子の人数':>7s} {'基礎控除':>12s} {'相続税の総額':>13s} {'1人多いときとの差':>15s}")
    for r in heirs_grid(150_000_000):
        print(f"{r['children']:6d}人 {r['deduction']:11,d}円 {r['gross']:12,d}円 "
              f"{r['diff']:14,d}円")

    print("\n=== 配偶者にどれだけ寄せるか（課税価格1億5000万円・子2人・一次と二次の合計）===")
    print(f"{'配偶者の取り分':>12s} {'一次で払う':>12s} {'二次で払う':>12s} {'合計':>12s}")
    for r in two_step_grid(150_000_000, 2):
        print(f"{r['spouse_ratio']:11.0%} {r['first_paid']:11,d}円 "
              f"{r['second_paid']:11,d}円 {r['total']:11,d}円")

    print("\n=== 「全部配偶者に寄せる」が、いくら高くつくか（子2人）===")
    print(f"{'課税価格':>12s} {'いちばん安い寄せ方':>16s} {'その合計':>12s} "
          f"{'全部配偶者の合計':>15s} {'差':>12s}")
    for r in gap_grid(2):
        print(f"{r['estate']:11,d}円 {r['best_ratio']:15.0%} {r['best_total']:11,d}円 "
              f"{r['allin_total']:14,d}円 {r['loss']:11,d}円")
