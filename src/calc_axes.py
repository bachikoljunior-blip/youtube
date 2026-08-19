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
             "hourly", "deduction", "flat",
             # 2026-08-19 に足した（計器 UNCALLABLE から）。**どちらも金額です** ——
             # `estate` は相続財産、`base` は課税標準（`tokutei.tax_of` /
             # `zoyo.tax_of` / `yoteinozei.with_fukko` / `shokibo.income_tax`）。
             # 寄せていなかったので、この 11関数が掃引から丸ごと落ちていました。
             "estate", "base"),
    "年齢": ("age", "start_age", "wife_age", "months_from_65", "age_gap_years",
             "birth"),
    "世帯": ("members", "children", "heads", "earners", "setainushi",
             "max_children", "dependents", "kazoku", "spouse", "heirs",
             "people", "claimants"),
    "期間": ("months", "years", "days", "period", "kikan", "fuka_months",
             "years_since", "start", "end", "duration", "year", "hours",
             # 2026-08-19 に足した。`saishushoku` の所定給付日数と支給残日数＝
             # **どちらも日数**。7関数がここで落ちていた（`rate_of` は2つとも
             # 必須なので、**片方だけ足しても戻りません**）。
             "prescribed", "remaining"),
    "率": ("rate", "social_rate", "rate_max", "percent", "ritsu", "waricho"),
    "面積": ("floor_area", "land_area", "area", "menseki", "km", "distance"),
    # `units` は 2026-08-19 に足した（`kaigo.used_units`）。**寄せられなかった名前**
    # として出ていて、そのせいで `kaigo` の主役の引数が軸を持たず、
    # `pair_sweep` が既知の当たり（gassan の元の2本）を組にできなかった。
    "回数": ("count", "times", "kaisu", "units"),
    "帯": ("low", "high", "upto", "min_point", "cap", "limit"),
}


#: 意味の軸 → **他の引数を埋めるときの代表値**。
#: **引数名ごとの表は作りません**（上の `SEMANTIC_AXES` が既に名前を軸へ寄せて
#: いるので、そちらに1語足せば全部の掃引に効きます）。
#:
#: **ここに置いてある理由**（2026-08-19 に `pair_sweep` から移した）。
#: この表は `pair_sweep` の中にあり、`section_sweep` からは見えませんでした
#: （`pair_sweep` が `section_sweep` を import するので、逆向きは輪になります）。
#: そのせいで **`section_sweep` だけが「既定値の無い数値の引数」で降り続けて**
#: いました。写して2つ持つと、次に軸を足した回が片方だけ書きます
#: （この輪は同じ形で7回踏んでいます）。**持つのは1つだけ。**
AXIS_FILL: dict[str, float] = {
    "所得": 3_000_000,
    "年齢": 65,
    "世帯": 2,
    "期間": 12,
    "率": 0.3,
    "面積": 100,
    "回数": 10_000,
    "帯": 44_400,
}


#: **軸の代表値では合わない引数に、名前で置く値**（2026-08-19 に足した）。
#: `AXIS_FILL` は軸ごとに1つの値しか持てないので、同じ軸でも桁の違う引数は
#: そこで壊れます —— `estate`（相続財産）を所得の代表値 3,000,000 で埋めると
#: **基礎控除（3,600万〜）に届かず税額がどの行でも 0** になり、掃引は
#: 「不変」を返して落とします。**呼べるようになっても、中身が空になる**わけです。
#: ここに書いた名前は `AXIS_FILL` より**先に**引きます。
PARAM_FILL: dict[str, float] = {
    "estate": 100_000_000,     # 1億円。基礎控除を超え、税率の段が何段も乗る
    "prescribed": 90,          # 所定給付日数の下限（`saishushoku`）
    "remaining": 45,           # 支給残日数。1/3 と 2/3 の崖のあいだに置く
}

#: **埋めるためだけの語彙**（2026-08-19 に足した）。
#:
#: `SEMANTIC_AXES` には消費者が2つあり、**要求が正反対**でした:
#:
#:   `axis_of`（`pair_sweep`）  … 表どうしを繋ぐ意味の軸。
#:                                **格子のつまみを入れると母数だけ膨らむ**
#:   `_axis_fill`（`section_sweep`）… 既定値の無い引数に置く値。
#:                                **寄せられない名前は関数ごと消える**
#:
#: 上の docstring は「`step` `points` `grade` はわざと入れていない」と言い、
#: それは `axis_of` の側では正しいのですが、そのせいで **`grade` を必須に持つ
#: 8関数が掃引から丸ごと落ちて**いました（`shougai` 5本・`zaishoku` 3本）。
#: **どちらか一方を選ぶ話ではありません。表を分ければ両方立ちます。**
#: ここに置いた名前は **`axis_of` からは見えません**（＝組は増えません）。
FILL_ONLY: dict[str, float] = {
    "grade": 1,       # 障害等級／標準報酬の等級。どちらも 1 は必ず在る
}


def axis_of(param: str) -> str | None:
    """引数名を意味の軸へ寄せる。寄せられなければ `None`。"""
    for axis, keys in SEMANTIC_AXES.items():
        for key in keys:
            if key == param or key in param:
                return axis
    return None


def real_params(fn) -> list:
    """`fn` の**本当の引数**だけを `(名前, Parameter)` で返す。

    除くのは `*args` と `**kw` の2つです。**どちらも渡さなくても呼べる**ので、
    「既定値が無い ＝ 必ず埋めなければならない引数」には入りません。
    ところが `inspect.signature` は、その2つにも
    `Parameter.empty` を既定値として入れます。**そのまま素の
    `sig.parameters.items()` を歩くと、名前 `kw` を埋めようとして
    関数ごと落ちます**（2026-08-19 に実測。`furusato.bracket_income` と
    `izoku.cliff_grid` の2本が、これだけで掃引の対象外でした）。

    **語彙で直せる形ではありません。** `PARAM_FILL` に `kw` を足すと、
    実在しない引数名に代表値を配ることになります ——
    その回の申し送りは、残り42件をまとめて「語彙に足せば戻る」と読んでいて、
    **2件はそこではありませんでした。**

    正本をここに置くのは `AXIS_FILL` と同じ理由です（`section_sweep` にも
    `pair_sweep` にも歩く場所があるので、写しを持つと片方だけ直ります）。
    """
    import inspect

    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return []
    kinds = (inspect.Parameter.VAR_POSITIONAL, inspect.Parameter.VAR_KEYWORD)
    return [(n, p) for n, p in sig.parameters.items() if p.kind not in kinds]


def numeric_params(fn) -> list[str]:
    """`fn` の**数値の引数の名前**。既定値が無くても数える。

    **`section_sweep._sweepable_params` を使わないこと**（2026-08-19 に踏んだ）。
    あちらは「**そのまま呼べる**」ことを条件にしていて、既定値の無い引数が
    1つでもあると **`return []`** で関数ごと降ります。掃引には正しい条件ですが、
    軸を数えるだけならその必要はありません。実際 `kogaku`（`cost` が必須）と
    `kaigo`（`used_units` `rate` が必須）は、あちらを使うと**軸ゼロ**になり、
    **`gassan` の元になった2本が一覧から丸ごと消えていました。**
    """
    out = []
    for name, p in real_params(fn):
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
