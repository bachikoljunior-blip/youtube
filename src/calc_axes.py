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


#: **率の引数を、実在する幅で振るための表**（2026-08-20 に足した）。
#:
#: `section_sweep._grid` は長らく、率（0 < x < 1）を**一律 0.1〜0.9** で振って
#: いました。そのせいで `social_rate` 0.7〜0.9（社会保険料が手取りの7〜9割）や
#: `rate` 0.9（所得税率90%）のような、**実在しない世界の崖**が候補に並びます。
#: 8/20 15:5x に 32件を目で見て歩留りを測ったところ **5/32 = 0.156** で、
#: **落ちた27件の過半がこれ**でした（`supply.SWEEP_YIELD` の註）。
#:
#: **引き方は2段**です。ここに名前があればその幅、無ければ
#: **既定値のまわり（0.5倍〜2倍）**。既定値そのものは、その関数を書いた側が
#: 置いた「実在する1点」なので、**そのまわりは必ず実在の側にあります。**
#:
#: **同じ名前が族によって別の意味を持つとき**は `族.引数名` で書くこと
#: （`ikuji.rate` は育休の給付率、`kaigo.rate` は自己負担割合、
#: それ以外の `rate` は所得税率）。**族つきを先に引きます。**
#:
#: **覆る条件**: この幅の外に、実在する制度の点が見つかったとき。
#: 幅を狭めるほど候補は減るので、**歩留り × 件数**で見ること
#: （`python -m src.supply --measure` が両方を出します）。
RATE_BAND: dict[str, tuple[float, float]] = {
    # 所得税の速算表は 5%・10%・20%・23%・33%・40%・45% の7段。この外は無い
    "rate": (0.05, 0.45),
    "income_rate": (0.05, 0.45),
    "high_rate": (0.05, 0.45),
    "low_rate": (0.05, 0.45),
    # 育児休業給付金は 開始から180日 67%・以後 50%。制度上この帯の外へ出ない
    "ikuji.rate": (0.50, 0.67),
    # 介護保険の自己負担は 1割・2割・3割
    "kaigo.rate": (0.10, 0.30),
    # 社会保険料の本人負担の実効率。健保 約5% ＋ 厚年 9.15% ＋ 雇用 0.55% ≒ 14.7%。
    # 国保・国年の側（率ではなく定額）まで含めても、手取りの2割を超えない
    "social_rate": (0.10, 0.20),
    # 協会けんぽの本人負担（都道府県で 4.6%〜5.25%）
    "health_rate": (0.045, 0.055),
    # 厚生年金の本人負担。2004年 6.79% から段階的に上がり 2017年に 9.15% で固定
    "pension_rate": (0.068, 0.0915),
    # 高年齢雇用継続給付の最大給付率。2025年3月まで 15%・4月から 10%
    "rate_max": (0.10, 0.15),
    # 住宅ローンの金利。変動 0.3% 台〜固定 2% 台
    "annual_rate": (0.003, 0.025),
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

    # --- **月額の引数**（2026-08-20 に足した。**桁が10倍ちがっていた**）---
    # `monthly` / `monthly_pay` / `avg_monthly` / `kihon_monthly` /
    # `monthly_wage` / `monthly_before` / `monthly_after` は、どれも
    # `SEMANTIC_AXES["所得"]` に寄って **年収の代表値 3,000,000** が入っていました。
    # 月給300万円です。`_grid` は 0.5〜4倍で振るので **月150万〜1,200万**を歩き、
    # そこで見つかる崖は**どれも実在しません**（`zangyo.hours_error_shortfall` の
    # 「monthly_pay を 1,500,000→11,999,999 と動かしても」がそれ）。
    # **部分一致1語で7つの名前に効きます。**
    "monthly": 300_000,
    "standard_pay": 300_000,   # 労災・傷病手当金の標準報酬月額
    "w60": 300_000,            # 高年齢雇用継続給付の60歳時点賃金（**月額**）
    # 小規模企業共済の掛金は **月1,000〜70,000円**。上の 300,000 では
    # どの行も上限に張り付いて「不変」しか出ません（族つきが先に引かれます）
    "shokibo.monthly": 30_000,
    # 在職老齢年金の基本月額は老齢厚生年金の月額（10万円台）。支給停止の
    # 判定は「基本月額＋総報酬月額相当額 > 51万円」なので、崖は相手側で出ます
    "zaishoku.kihon_monthly": 100_000,

    # --- **量なのに所得の軸へ寄っていた引数**（同日）---
    # どれも名前の一部（`annual` / `bonus` / `ratio` / `rate`）が
    # `SEMANTIC_AXES["所得"]` に載っているせいで 3,000,000 が入っていました
    "annual_days_off": 120,    # 年間休日日数（`zangyo`）。3,000,000日ではない
    "bonus_months": 4,         # 賞与の月数（`rousai.year_ratio`）
    "purchase_ratio": 0.8,     # 課税仕入率（`invoice.honsoku`）。0〜1 の率
    "income_rate": 0.2,        # 所得税率（`shokibo`）。率なので `RATE_BAND` が効く
    "annual_rate": 0.01,       # 住宅ローンの金利（`jutaku`）。同上
}

#: **名前が完全に一致したときだけ引く表**（2026-08-20 に足した）。
#:
#: `PARAM_FILL` と `FILL_ONLY` は **部分一致**（`name in param`）で引きます。
#: そのおかげで `estate` 1語が `estate_total` にも効くのですが、
#: **短い名前はそこに置けません** —— `i` を置けば `income` にも `kikan` にも
#: 当たり、`n` はほぼ全部の引数に当たります。
#:
#: そのせいで、**引数が `i` や `n` や `step` というだけで関数が丸ごと
#: 掃引から落ちていました**（`shahoken.bounds(i)`・`inshi.split_cost(n)`・
#: `haiguusha.cliff(step)`）。**語彙の不足ではなく、引き方の不足**です。
#: 部分一致の3つより**先に**、ここを完全一致で引きます。
#:
#: **`axis_of` からは見えません**（＝`pair_sweep` の組は増えません）。
#: ここに並ぶのはどれも「その表の中の何番目か」「何回目か」の類で、
#: **表どうしを繋ぐ意味の軸ではない**からです（`FILL_ONLY` と同じ扱い）。
EXACT_FILL: dict[str, float] = {
    # 番号・回数（**その表の中でしか意味を持たない**）
    "i": 12,                 # `shahoken.bounds` の等級（0起点・全32段）
    "n": 3,                  # `inshi.split_cost` の分割の通数
    "step": 5,               # `haiguusha.cliff` / `recovery` の段（1〜9）
    "order": 2,              # `jidou` の第何子
    "parts": 3,              # `iryohi.split_months_tax` の分ける月数
    "nth": 3,                # `yukyu.granted_at` の付与の回（0起点）
    "skipped_nth": 3,        # `yukyu.skip_one_year`
    "points": 20,            # `ninikeizoku.keigen_kintou` の軽減のポイント
    # 量（**軸の代表値では桁が合わないもの**）
    "nth_hour": 20,          # `zangyo.marginal_hour` の残業の何時間目
    "this_month": 60,        # `jikangai.next_month_cap` の今月の残業時間
    "ratio": 0.6,            # `koureikoyou.keep_rate` の低下率
    "small": 100,            # `koteishisan.same_tax_floor` の狭い家の床面積（㎡）
    "edge": 1_000_000,       # `inshi.zeinuki_limit` の帯の入口（円）
    "std": 300_000,          # `sankyu.premium` の標準報酬月額（円）
    "hantei": 800_000,       # `kouki.keigen_rate` の判定所得（円）
    "target": 2_000,         # `zangyo.hours_for_average` の平均単価（円）
    "smaller_share": 100_000,  # `iryohi.split_loss` の分けた側の医療費（円）
    # **`shobyo.example_pay` の `remainder` は、ここに置きません。**
    # 届く余りは `gcd(1000, 900) = 100` の倍数だけで、`_grid` は 100 きざみの
    # 点を並べません（どの代表値を置いても、当たるのは1点だけ＝掃引に足りない）。
    # **埋められないのは語彙の不足ではなく、格子とその関数の刻みが噛み合わない**
    # からです。関数の側は同じ回に直しました（**無限ループ → `TableError`**）。
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
