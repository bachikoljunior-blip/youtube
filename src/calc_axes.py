"""引数の名前を、**意味の軸**へ寄せる（M19 の1手目）。

## なぜ要るか

`section_sweep` は表を**1本ずつ**掃きます。`gassan`（医療×介護）のような
**2本を同じ物差しに載せて初めて出る節**は、そこからは原理的に出ません。
機械で組を作るには「どの表とどの表が同じ軸を持つか」が要ります。

**引数の名前では繋がりません**（2026-08-19 に実測）——
名前の一致で数えると **44組 / 741組**、いちばん多い軸は `step`（15組）と
`months`（10組）で、**どちらも走査の刻みと期間＝格子のつまみ**です。
同じ「年収」が `income` `monthly` `avg_monthly` `kyuyo_shotoku` … と
**77種**に散っているので、名前は軸の代わりになりません。

**寄せると 292組（6.6倍）／3本組 1,330組**になります。数え直しは:

    python -m src.calc_axes

## 割り引いて読むこと

- **寄せは手で書いた表です。** 新しい引数名は勝手には入りません。
  `python -m src.calc_axes` の「寄せられなかった名前」を毎回見ること
- **`step` `points` `grade` などは、わざと軸に入れていません。**
  格子のつまみで組を作ると、意味の無い組が母数を膨らませます
- **組の数は節の数ではありません。** 1組から何節出るかは `gassan` の
  **7節（n=1）**しか実測がありません。`docs/MEANS.md` M19 の掛け算は
  控えめに **5節/組** で置いてあります。**3組で測るまで、この数を動かさないこと**
"""
from __future__ import annotations

import collections
import importlib
import itertools

#: 意味の軸 → その軸に寄せる引数名の断片。**部分一致**で引きます。
#: **格子のつまみ（step / points / grade …）は、わざと入れていません。**
SEMANTIC_AXES: dict[str, tuple[str, ...]] = {
    "所得": ("income", "shotoku", "nenshu", "salary", "wage", "pay", "monthly",
             "annual", "sales", "profit", "hyojun", "avg_monthly", "monthly_pay",
             "kyuyo", "nenkin", "sonota", "w60", "premium", "bonus", "shoyo",
             "taxable", "total_income", "value", "amount", "cost", "price",
             "unit_price", "gaku", "money", "yen", "tedori", "koujo",
             "deduction_amount", "resident_tax", "tax", "shunyu", "jikofutan",
             "sou_iryohi", "paid", "reimbursed", "withheld", "total",
             "purchase", "balance", "jogen", "hyoujun", "surcharge", "credit",
             "hourly", "deduction", "flat"),
    "年齢": ("age", "start_age", "wife_age", "months_from_65", "age_gap_years",
             "birth"),
    "世帯": ("members", "children", "heads", "earners", "setainushi",
             "max_children", "dependents", "kazoku", "spouse", "heirs",
             "people", "claimants"),
    "期間": ("months", "years", "days", "period", "kikan", "fuka_months",
             "years_since", "start", "end", "duration", "year", "hours"),
    "率": ("rate", "social_rate", "rate_max", "percent", "ritsu", "waricho"),
    "面積": ("floor_area", "land_area", "area", "menseki", "km", "distance"),
    "回数": ("count", "times", "kaisu"),
    "帯": ("low", "high", "upto", "min_point", "cap", "limit"),
}


def axis_of(param: str) -> str | None:
    """引数名を意味の軸へ寄せる。寄せられなければ `None`。"""
    for axis, keys in SEMANTIC_AXES.items():
        for key in keys:
            if key == param or key in param:
                return axis
    return None


def numeric_params(fn) -> list[str]:
    """`fn` の**数値の引数の名前**。既定値が無くても数える。

    **`section_sweep._sweepable_params` を使わないこと**（2026-08-19 に踏んだ）。
    あちらは「**そのまま呼べる**」ことを条件にしていて、既定値の無い引数が
    1つでもあると **`return []`** で関数ごと降ります。掃引には正しい条件ですが、
    軸を数えるだけならその必要はありません。実際 `kogaku`（`cost` が必須）と
    `kaigo`（`used_units` `rate` が必須）は、あちらを使うと**軸ゼロ**になり、
    **`gassan` の元になった2本が一覧から丸ごと消えていました。**
    """
    import inspect

    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    out = []
    for name, p in sig.parameters.items():
        if isinstance(p.default, bool):
            continue
        numeric = isinstance(p.default, (int, float))
        anno = p.annotation
        if isinstance(anno, str) and anno.split("|")[0].strip() in ("int", "float"):
            numeric = True
        elif anno in (int, float):
            numeric = True
        if numeric:
            out.append(name)
    return out


def axes_by_calc() -> tuple[dict[str, set[str]], collections.Counter]:
    """表の名前 → その表が持つ意味の軸。2つめは**寄せられなかった名前**。"""
    from src.section_sweep import calc_modules

    out: dict[str, set[str]] = collections.defaultdict(set)
    unmapped: collections.Counter = collections.Counter()
    for name in calc_modules():
        mod = importlib.import_module(f"src.calc.{name}")
        for fname, fn in vars(mod).items():
            if fname.startswith("_") or not callable(fn):
                continue
            if getattr(fn, "__module__", "") != mod.__name__:
                continue
            for param in numeric_params(fn):
                axis = axis_of(param)
                if axis:
                    out[name].add(axis)
                else:
                    unmapped[param] += 1
    return dict(out), unmapped


def shared_pairs(axes: dict[str, set[str]] | None = None) -> list[tuple[str, str, set[str]]]:
    """同じ意味の軸を持つ表の**組**。`(表A, 表B, 共有する軸)`。"""
    if axes is None:
        axes, _ = axes_by_calc()
    return [(a, b, axes[a] & axes[b])
            for a, b in itertools.combinations(sorted(axes), 2)
            if axes[a] & axes[b]]


def _main() -> None:
    axes, unmapped = axes_by_calc()
    pairs = shared_pairs(axes)
    trips = sum(1 for a, b, c in itertools.combinations(sorted(axes), 3)
                if axes[a] & axes[b] & axes[c])
    total = len(axes) * (len(axes) - 1) // 2

    print(f"軸を持つ表 {len(axes)} 本")
    tally: collections.Counter = collections.Counter()
    for got in axes.values():
        tally.update(got)
    print("\n意味の軸ごとの表の数（組の数は表の本数の2乗・3乗で増えます）:")
    for axis, n in tally.most_common():
        print(f"  {axis:4s} 表{n:3d}本 → 組 {n * (n - 1) // 2:5d}"
              f"   3本組 {n * (n - 1) * (n - 2) // 6:6d}")
    print(f"\n意味の軸を共有する表の組: **{len(pairs)}組** / 全{total}組"
          f"   3本組 **{trips}組**")
    if unmapped:
        print(f"\n寄せられなかった名前 {len(unmapped)}種（格子のつまみなら、"
              f"このままで正しい）:")
        print("  " + " ".join(n for n, _ in unmapped.most_common()))


if __name__ == "__main__":
    _main()
