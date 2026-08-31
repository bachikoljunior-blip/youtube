"""昇給率の複利を、年ごとに解いて生涯賃金の開きを実額で出す。

    python -m src.calc.shokyu

## この計算で出したいこと

昇給の話は「複利だから効く」「1パーセントでも大きい」で止まる。
**その1ポイントが何円なのか、どこまでの一時金と釣り合うのかは、どこにも出ていない。**
昇給は毎年 前の年に掛かるので、**掛け算では出ない。年ごとに解かないと出ない。**

ここで解くと、次の6つが出る。

1. **1ポイントの値打ちは、上ほど大きい。**年収 3,000,000円 から38年で、
   0パーセント → 1パーセント は 23,858,154円、
   4パーセント → 5パーセント は 65,217,626円。**同じ1ポイントで 41,359,472円 の差。**
   「1パーセントは大きい」は正しいが、**どの1パーセントかで値打ちがまるで違う。**
2. **転職の一撃には、取り返せる上限がある。**昇給を1ポイント上げる道と比べると、
   一度に上げる額が **690,000円 までなら、38年の合計で追い越す。**
   **700,000円 になると、38年かけても合計は並ばない。**
   年収だけなら 1,000,000円 の一撃でも 31年目 に並ぶのに、
   **合計はもう戻らない。**「いつか追いつく」が成り立たない境目がここ。
3. **定額の昇給にも、同じ境目がある。**毎年おなじ額が上がる形と、
   昇給2パーセントを比べると、**87,000円 までなら38年のうちに追い越される。
   88,000円 になると、38年かけても年収で並ばれない。**
4. **物価と同じだけ昇給しても、実質は1円も増えない。**昇給2パーセント・
   物価2パーセントなら、38年の実質の生涯賃金は 113,999,965円。
   これは初任給 3,000,000円 を38年ぶん足した 114,000,000円 とほぼ同じ。
   物価3パーセントなら、名目 168,344,805円 に対し実質は 95,719,809円 で、
   **72,624,996円 が消える。**
5. **頭打ちは、5年ごとに効きが変わる。**20年目 で止まると
   止まらない場合より 16,784,908円 少なく、35年目 なら 715,301円。
   5年ずらすごとの差は 7,260,037円 → 5,504,565円 → 3,305,005円 と**縮む。**
   **早い頭打ちほど、1年の重みが大きい。**
6. **賞与2か月より、昇給1ポイントのほうが大きい。**月給 200,000円・38年で、
   賞与を4か月から6か月へ増やすと 22,445,975円、
   昇給を1ポイント上げると 41,742,429円。**差は 19,296,454円。**

## 前提（動画にそのまま出すこと）

- 初任給は年収 3,000,000円 の額面。昇給は年1回、その年の初めに前の年の年収へ
  昇給率を掛ける。1円未満は切り捨て
- 働く期間は38年（22歳から60歳まで）。途中の転職・休職・残業代の増減は無いものとする
- 昇給率・物価上昇率・賞与の月数は、どれも制度の値ではなくこの計算での仮定
- 税と社会保険料は引いていない。すべて額面

## この族には条文がない

`src/calc/` の他の表は、税・年金・社会保険の**制度の値**を引いている。
この表は**1つも引いていない。**出てくる数は全部その場の算術で、
**前提の置き方そのものしか独自性が無い。**だから前提を全部 画面に出す。
"""
from __future__ import annotations

import math

from . import _checks

# ---- この計算で置く値。**制度の値は1つもありません** ------------------
#
# この族には条文がありません。**全部その場の算術**です。
# だから「制度がこうなっている」ではなく「この前提を置くとこうなる」しか言えず、
# **前提の置き方そのものが独自の視点**になります（`CLAUDE.md` の根幹）。

START = 3_000_000       # 初任給の年収（額面）
YEARS = 38              # 22歳から60歳まで働く年数
RATES = (0.00, 0.01, 0.02, 0.03, 0.04, 0.05)   # 並べる昇給率

ASSUMPTIONS = (
    "初任給は年収300万円の額面とし、昇給は年1回、その年の初めに"
    "前の年の年収へ昇給率を掛ける形で置いています。1円未満は切り捨てです",
    "働く期間は38年です。22歳から60歳まで、途中の転職・休職・"
    "残業代の増減は無いものとします",
    "昇給率は制度の値ではなく、この計算での仮定です。"
    "0パーセントから5パーセントまで1ポイント刻みで並べています",
    "物価上昇率も仮定です。0.5パーセント・1パーセント・2パーセント・"
    "3パーセントの4つで並べ、実質の年収は名目の年収をその複利で割って出します",
    "賞与は月給の何か月ぶんかで置き、0か月・2か月・4か月・6か月を並べます。"
    "年収は月給に12と賞与の月数を足したものを掛けた額です",
    "税と社会保険料は引いていません。すべて額面の年収です",
)


# ------------------------------------------------------------ 年収の推移

def annual(start: int = START, rate: float = 0.02, year: int = 1,
           cap_year: int | None = None) -> int:
    """`year` 年目（1年目が初任給）の年収。**1円未満は切り捨て。**

    `cap_year` を入れると、その年で昇給が止まる（頭打ち）。
    """
    if year < 1:
        raise ValueError(f"年は1以上: {year}")
    n = year - 1
    if cap_year is not None:
        n = min(n, cap_year - 1)
    return math.floor(start * (1 + rate) ** n)


def path(start: int = START, rate: float = 0.02, years: int = YEARS,
         cap_year: int | None = None) -> list[int]:
    return [annual(start, rate, y, cap_year) for y in range(1, years + 1)]


def lifetime(start: int = START, rate: float = 0.02, years: int = YEARS,
             cap_year: int | None = None) -> int:
    """`years` 年ぶんの年収の合計。**これがこの計算の主役の数。**"""
    return sum(path(start, rate, years, cap_year))


# -------------------------------------------- 1. 昇給率1ポイントの値打ち

def rate_grid(start: int = START, years: int = YEARS,
              rates: tuple[float, ...] = RATES) -> list[dict]:
    """昇給率べつ、最終年の年収と生涯賃金。**0パーセントとの差も出す。**"""
    base = lifetime(start, 0.0, years)
    rows: list[dict] = []
    for r in rates:
        total = lifetime(start, r, years)
        rows.append({
            "rate": r,
            "final": annual(start, r, years),
            "lifetime": total,
            "gain": total - base,
        })
    return rows


def step_gain(start: int = START, years: int = YEARS,
              rates: tuple[float, ...] = RATES) -> list[dict]:
    """**1ポイント上げるごとに、生涯賃金がいくら増えるか。**

    増え方そのものが増えていく（複利なので直線ではない）ことがこの節の主題。
    """
    rows: list[dict] = []
    prev = None
    for r in rates:
        total = lifetime(start, r, years)
        if prev is not None:
            rows.append({
                "from": prev[0],
                "to": r,
                "step": total - prev[1],
            })
        prev = (r, total)
    return rows


# ------------------------------------- 2. 転職の一撃 と 昇給率1ポイント

JUMPS = (100_000, 300_000, 500_000, 1_000_000)   # 転職で一度だけ上がる年収の額
BASE_RATE = 0.02                                 # 比べる元の昇給率


def crossover(jump: int, start: int = START, base_rate: float = BASE_RATE,
              plus: float = 0.01, years: int = YEARS) -> dict:
    """転職で一度 `jump` 円 上げる道と、昇給率を `plus` 上げる道を比べる。

    返すのは、年収が追いつく年・合計が追いつく年・38年の合計の差。
    **どちらも1年目から始めます**（転職は1年目に済んでいるものとする）。
    """
    a = path(start + jump, base_rate, years)          # 転職した側
    b = path(start, base_rate + plus, years)          # 昇給率を上げた側
    year_cross = next((i + 1 for i in range(years) if b[i] >= a[i]), None)
    ca = cb = 0
    total_cross = None
    for i in range(years):
        ca += a[i]
        cb += b[i]
        if total_cross is None and cb >= ca:
            total_cross = i + 1
    return {
        "jump": jump,
        "year_cross": year_cross,
        "total_cross": total_cross,
        "jump_total": ca,
        "rate_total": cb,
        "diff": cb - ca,
    }


def crossover_grid(start: int = START, base_rate: float = BASE_RATE,
                   plus: float = 0.01, years: int = YEARS,
                   jumps: tuple[int, ...] = JUMPS) -> list[dict]:
    return [crossover(j, start, base_rate, plus, years) for j in jumps]


def _or_beyond(year: int | None, years: int = YEARS) -> int:
    """**追いつかなかった年は「期間の外」として `years + 1` で扱う。**

    `None` のまま並べると向きの検査が型で落ちるので、順序だけを保って数にする。
    表には `None` のまま出す（「38年では並ばず」と印字する）。
    """
    return years + 1 if year is None else year


def catch_up_limit(start: int = START, base_rate: float = BASE_RATE,
                   plus: float = 0.01, years: int = YEARS) -> int:
    """**38年の合計で取り返せる、転職の上げ幅の上限**（1万円きざみで探す）。

    これより大きい一撃は、昇給率を1ポイント上げても期間内には並びません。
    **どこにも出ていない境目。**
    """
    step = 10_000
    last = 0
    j = step
    while j <= 5_000_000:
        if crossover(j, start, base_rate, plus, years)["total_cross"] is None:
            return last
        last = j
        j += step
    raise ValueError("500万円まで探しても取り返せる（範囲を広げること）")


# ------------------------------------------------ 3. 定額の昇給 と 定率の昇給

FLAT_STEPS = (50_000, 60_000, 70_000, 80_000)   # 毎年いくら上がるか（定額）


def flat_annual(start: int = START, step: int = 80_000, year: int = 1) -> int:
    """定額の昇給（毎年おなじ額だけ上がる）での、その年の年収。"""
    return start + step * (year - 1)


def flat_vs_rate(step: int, start: int = START, rate: float = 0.02,
                 years: int = YEARS) -> dict:
    """定額 `step` 円 と 定率 `rate` を、年収と合計の両方で比べる。"""
    flat = [flat_annual(start, step, y) for y in range(1, years + 1)]
    comp = path(start, rate, years)
    # **1年目は両方とも初任給そのもの**なので、`>=` で見ると全部1年目になります
    # （2026-08-29 に踏んだ）。入れ替わりを見るので、比べるのは**厳密に上**のほう。
    year_cross = next((i + 1 for i in range(years) if comp[i] > flat[i]), None)
    cf = cc = 0
    total_cross = None
    for i in range(years):
        cf += flat[i]
        cc += comp[i]
        if total_cross is None and cc > cf:
            total_cross = i + 1
    return {
        "step": step,
        "flat_final": flat[-1],
        "rate_final": comp[-1],
        "year_cross": year_cross,
        "total_cross": total_cross,
        "flat_total": cf,
        "rate_total": cc,
        "diff": cc - cf,
    }


def flat_grid(start: int = START, rate: float = 0.02, years: int = YEARS,
              steps: tuple[int, ...] = FLAT_STEPS) -> list[dict]:
    return [flat_vs_rate(s, start, rate, years) for s in steps]


def flat_limit(start: int = START, rate: float = 0.02,
               years: int = YEARS) -> int:
    """**38年のあいだに定率が追い越せる、定額の昇給の上限**（1,000円きざみ）。

    これより大きい定額は、38年かけても年収で並ばれません。
    **どこにも出ていない境目。**
    """
    step = 1_000
    last = 0
    s = step
    while s <= 1_000_000:
        if flat_vs_rate(s, start, rate, years)["year_cross"] is None:
            return last
        last = s
        s += step
    raise ValueError("100万円まで探しても追い越せる（範囲を広げること）")


# ------------------------------------------------------ 4. 物価と実質の年収

INFLATIONS = (0.005, 0.01, 0.02, 0.03)


def real_annual(start: int = START, rate: float = 0.02, inflation: float = 0.01,
                year: int = 1) -> int:
    """物価上昇を割り戻した、その年の**実質**の年収。1円未満は切り捨て。"""
    return math.floor(annual(start, rate, year) / (1 + inflation) ** (year - 1))


def real_grid(start: int = START, rate: float = 0.02, years: int = YEARS,
              inflations: tuple[float, ...] = INFLATIONS) -> list[dict]:
    """物価上昇率べつ、38年目の名目と実質・実質の生涯賃金・目減り。"""
    nominal_total = lifetime(start, rate, years)
    rows: list[dict] = []
    for p in inflations:
        real_path = [real_annual(start, rate, p, y) for y in range(1, years + 1)]
        rows.append({
            "inflation": p,
            "nominal_final": annual(start, rate, years),
            "real_final": real_path[-1],
            "real_total": sum(real_path),
            "lost": nominal_total - sum(real_path),
        })
    return rows


def keep_rate(inflation: float, years: int = YEARS,
              start: int = START) -> float:
    """**実質の生涯賃金を、物価0パーセントのときと同じにする昇給率。**

    名目 `r`・物価 `p` の実質の年収は `start*(1+r)^n/(1+p)^n` なので、
    `(1+r)/(1+p)` が 1 になる `r`（＝ `r = p`）が答え。
    **掛け算で出るが、誰も出していない**ので表にする。
    """
    return inflation


def keep_grid(start: int = START, years: int = YEARS,
              inflations: tuple[float, ...] = INFLATIONS,
              rate: float = 0.02) -> list[dict]:
    """物価べつ、実質を保つのに要る昇給率と、2パーセントとの生涯賃金の差。"""
    rows: list[dict] = []
    for p in inflations:
        need = keep_rate(p, years, start)
        have = [real_annual(start, rate, p, y) for y in range(1, years + 1)]
        keep = [real_annual(start, need, p, y) for y in range(1, years + 1)]
        rows.append({
            "inflation": p,
            "need": need,
            "short": need - rate,
            "have_total": sum(have),
            "keep_total": sum(keep),
            "gap": sum(keep) - sum(have),
        })
    return rows


# ---------------------------------------------------- 5. 昇給が止まる年

CAPS = (20, 25, 30, 35, None)


def cap_grid(start: int = START, rate: float = 0.02, years: int = YEARS,
             caps: tuple[int | None, ...] = CAPS) -> list[dict]:
    """昇給が止まる年べつ、最終年の年収と生涯賃金。**止まらない場合との差も。**"""
    full = lifetime(start, rate, years)
    rows: list[dict] = []
    for c in caps:
        total = lifetime(start, rate, years, c)
        rows.append({
            "cap": c,
            "final": annual(start, rate, years, c),
            "lifetime": total,
            "loss": full - total,
        })
    return rows


def cap_year_cost(start: int = START, rate: float = 0.02, years: int = YEARS,
                  caps: tuple[int | None, ...] = CAPS) -> list[dict]:
    """**頭打ちが5年ちがうと、生涯賃金がいくら変わるか**（段の差）。"""
    rows: list[dict] = []
    prev = None
    for c in caps:
        total = lifetime(start, rate, years, c)
        if prev is not None and prev[0] is not None and c is not None:
            rows.append({"from": prev[0], "to": c, "step": total - prev[1]})
        prev = (c, total)
    return rows


# ---------------------------------------------------------- 6. 賞与の月数

BONUS_MONTHS = (0, 2, 4, 6)
MONTHLY = 200_000       # 比べるときの月給（額面）


def bonus_annual(monthly: int = MONTHLY, months: int = 4, rate: float = 0.02,
                 year: int = 1) -> int:
    """賞与が月給の `months` か月ぶんのときの、その年の年収。

    **賞与も月給と同じ率で上がる**（賞与は月数で決まるため）。
    """
    return math.floor(monthly * (12 + months) * (1 + rate) ** (year - 1))


def bonus_grid(monthly: int = MONTHLY, rate: float = 0.02, years: int = YEARS,
               months: tuple[int, ...] = BONUS_MONTHS) -> list[dict]:
    """賞与の月数べつ、初年度と最終年の年収・生涯賃金・0か月との差。"""
    base = sum(bonus_annual(monthly, 0, rate, y) for y in range(1, years + 1))
    rows: list[dict] = []
    for m in months:
        total = sum(bonus_annual(monthly, m, rate, y) for y in range(1, years + 1))
        rows.append({
            "months": m,
            "first": bonus_annual(monthly, m, rate, 1),
            "final": bonus_annual(monthly, m, rate, years),
            "lifetime": total,
            "gain": total - base,
        })
    return rows


def bonus_vs_rate(monthly: int = MONTHLY, rate: float = 0.02,
                  years: int = YEARS) -> dict:
    """**賞与2か月ぶんと、昇給率1ポイントは、どちらが大きいか。**

    どちらも「生涯賃金がいくら増えるか」で並べる。
    """
    base = sum(bonus_annual(monthly, 4, rate, y) for y in range(1, years + 1))
    plus_bonus = sum(bonus_annual(monthly, 6, rate, y) for y in range(1, years + 1))
    plus_rate = sum(bonus_annual(monthly, 4, rate + 0.01, y)
                    for y in range(1, years + 1))
    return {
        "base": base,
        "plus_bonus": plus_bonus - base,
        "plus_rate": plus_rate - base,
        "diff": (plus_rate - base) - (plus_bonus - base),
    }


# ------------------------------------------------------------------ 検査

def check_tables() -> None:
    """**この計算の主題そのものを確かめる。**制度の値は1つも無いので、
    見るのは全部「向き」と「境目」のほう。"""
    # 1. 昇給率を上げれば、最終年の年収も生涯賃金も増える
    _checks.increases_with(lambda r: annual(START, r, YEARS), list(RATES),
                           "昇給率を上げたのに最終年の年収が増えていない")
    _checks.increases_with(lambda r: lifetime(START, r), list(RATES),
                           "昇給率を上げたのに生涯賃金が増えていない")
    _checks.ratio(RATES[-1], "並べる昇給率の上端")

    # 2. **1ポイントの値打ちは、上へ行くほど大きくなる**（複利なので直線でない）
    steps = [r["step"] for r in step_gain()]
    _checks.ascending(steps, "1ポイントの値打ち（上ほど大きい）", strict=True)
    assert all(s > 0 for s in steps), "1ポイント上げて生涯賃金が増えていない"

    # 3. 1年目は初任給そのもの。昇給0パーセントなら38年とも同じ額
    _checks.rounding(annual(START, 0.03, 1), START, "1年目の年収")
    assert len(set(path(START, 0.0))) == 1, "昇給0パーセントで年収が動いている"
    _checks.rounding(lifetime(START, 0.0), START * YEARS, "昇給0パーセントの生涯賃金")

    # 4. 転職の一撃と昇給率。**上げ幅が大きいほど、追いつく年は遅くなる**
    _checks.increases_with(lambda j: crossover(j)["year_cross"], list(JUMPS),
                           "転職の上げ幅が大きいのに、追いつく年が遅くなっていない")
    _checks.increases_with(lambda j: _or_beyond(crossover(j)["total_cross"]),
                           list(JUMPS),
                           "転職の上げ幅が大きいのに、合計で追いつく年が遅くなっていない")
    for row in crossover_grid():
        assert row["year_cross"] is not None, (
            f"年収が38年で追いつかない: 上げ幅 {row['jump']:,}円")
        assert row["year_cross"] < _or_beyond(row["total_cross"]), (
            "年収より先に合計が追いついている（順序が逆）")
    # **境目そのもの。**この上限のすぐ上は、38年かけても並びません
    limit = catch_up_limit()
    assert crossover(limit)["total_cross"] is not None, "上限で並んでいない"
    assert crossover(limit + 10_000)["total_cross"] is None, (
        "上限の1万円上でも並んでいる（上限が最大でない）")

    # 5. 定額と定率。**定額の幅が大きいほど、定率が勝つ年は遅い**
    _checks.increases_with(lambda s: _or_beyond(flat_vs_rate(s)["year_cross"]),
                           list(FLAT_STEPS),
                           "定額の幅が大きいのに、定率が勝つ年が遅くなっていない")
    for row in flat_grid():
        assert row["year_cross"] is None or (
            row["total_cross"] is None or row["year_cross"] <= row["total_cross"]), (
            "年収より先に合計が入れ替わっている（順序が逆）")
    fl = flat_limit()
    assert flat_vs_rate(fl)["year_cross"] is not None, "上限で追い越せていない"
    assert flat_vs_rate(fl + 1_000)["year_cross"] is None, (
        "上限の1,000円上でも追い越せている（上限が最大でない）")

    # 6. 物価。**上がるほど実質は小さくなり、目減りは大きくなる**
    _checks.decreases_with(lambda p: real_annual(START, 0.02, p, YEARS),
                           list(INFLATIONS),
                           "物価が上がったのに、38年目の実質の年収が減っていない")
    _checks.increases_with(lambda p: real_grid(inflations=(p,))[0]["lost"],
                           list(INFLATIONS),
                           "物価が上がったのに、目減りが増えていない")
    # 名目の昇給率と物価上昇率が同じなら、実質の年収は初任給のまま動かない
    # **1円のずれは切り捨てを2回かけているからです**（`annual` で1回、
    # 割り戻しでもう1回）。ここを `rounding` で見ると 2,999,999 で落ちます。
    for p in INFLATIONS:
        got = real_annual(START, p, p, YEARS)
        assert abs(got - START) <= 1, (
            f"昇給{p:.1%}・物価{p:.1%}のときの38年目の実質年収が "
            f"{got:,}円。初任給 {START:,}円 のままのはず（切り捨て2回ぶんの1円まで）")
    for row in keep_grid():
        _checks.close(row["need"], row["inflation"],
                      "実質を保つのに要る昇給率が、物価上昇率と一致していない")

    # 7. 頭打ち。**遅いほど生涯賃金は大きく、止まらない場合が最大**
    _checks.increases_with(
        lambda c: cap_grid(caps=(c,))[0]["lifetime"], [20, 25, 30, 35],
        "頭打ちが遅いのに、生涯賃金が増えていない")
    rows = cap_grid()
    assert rows[-1]["cap"] is None, "最後の行が『止まらない』でない"
    assert rows[-1]["loss"] == 0, "止まらない場合に損が出ている"
    assert all(r["loss"] > 0 for r in rows[:-1]), "頭打ちがあるのに損が0"
    _checks.unique_by(rows, lambda r: r["cap"], "頭打ちの表")

    # 8. 賞与。**月数が増えれば年収も生涯賃金も増える**
    _checks.increases_with(lambda m: bonus_grid(months=(m,))[0]["lifetime"],
                           list(BONUS_MONTHS),
                           "賞与の月数が増えたのに、生涯賃金が増えていない")
    b = bonus_grid()
    assert b[0]["gain"] == 0, "賞与0か月との差が0でない"
    # 賞与4か月なら、年収は月給の16か月ぶん
    _checks.rounding(bonus_annual(MONTHLY, 4, 0.02, 1), MONTHLY * 16,
                     "月給20万円・賞与4か月の初年度の年収")

    print("制度の値の検査: 通過")


def main() -> None:
    check_tables()

    print("\n=== 昇給率が1ポイントちがうと、38年の生涯賃金はいくら変わるか ===")
    print(f"{'昇給率':>7}{'38年目の年収':>15}{'生涯賃金':>16}{'0パーセントとの差':>20}")
    for row in rate_grid():
        print(f"{row['rate']:>6.0%}{row['final']:>14,}円"
              f"{row['lifetime']:>15,}円{row['gain']:>19,}円")
    print("  1ポイント上げるごとに、生涯賃金がいくら増えるか:")
    for row in step_gain():
        print(f"    {row['from']:.0%} → {row['to']:.0%}"
              f"  {row['step']:>14,}円")
    g = step_gain()
    print(f"  いちばん下の1ポイント（0パーセント → 1パーセント）は {g[0]['step']:,}円、"
          f"いちばん上（4パーセント → 5パーセント）は {g[-1]['step']:,}円。"
          f"差は {g[-1]['step'] - g[0]['step']:,}円")

    print("\n=== 転職で年収を一度上げるのと、昇給率を1ポイント上げるのは、"
          "何年で逆転するか ===")
    print(f"  元は 年収{START:,}円・昇給{BASE_RATE:.0%}。"
          f"片方は転職で一度だけ上げ、もう片方は昇給を1ポイント上げる")
    print(f"{'転職の上げ幅':>13}{'年収が並ぶ年':>15}{'合計が並ぶ年':>15}"
          f"{'38年の合計（転職）':>21}{'同（昇給率）':>16}{'差':>14}")
    for row in crossover_grid():
        tc = f"{row['total_cross']}年目" if row["total_cross"] else "38年では並ばず"
        print(f"{row['jump']:>12,}円{row['year_cross']:>13}年目"
              f"{tc:>15}{row['jump_total']:>19,}円"
              f"{row['rate_total']:>14,}円{row['diff']:>13,}円")
    limit = catch_up_limit()
    print(f"  38年の合計で取り返せる上げ幅の上限は {limit:,}円。"
          f"{limit + 10_000:,}円 になると、38年かけても合計は並びません")

    print("\n=== 毎年おなじ額の昇給と、毎年おなじ率の昇給は、何年目で入れ替わるか ===")
    print(f"  比べる相手は 昇給{BASE_RATE:.0%}（定率）。どちらも 年収{START:,}円 から")
    print(f"{'定額の昇給':>12}{'38年目（定額）':>17}{'38年目（定率）':>17}"
          f"{'年収が並ぶ年':>15}{'合計が並ぶ年':>15}{'38年の合計の差':>18}")
    for row in flat_grid():
        cross = f"{row['total_cross']}年目" if row["total_cross"] else "38年では並ばず"
        yc = f"{row['year_cross']}年目" if row["year_cross"] else "38年では並ばず"
        print(f"{row['step']:>11,}円{row['flat_final']:>16,}円"
              f"{row['rate_final']:>16,}円{yc:>15}"
              f"{cross:>15}{row['diff']:>17,}円")
    fl = flat_limit()
    print(f"  38年のあいだに昇給{BASE_RATE:.0%}が追い越せる定額の上限は {fl:,}円。"
          f"{fl + 1_000:,}円 になると、38年かけても年収で並ばれません")

    print("\n=== 物価が上がると、38年の生涯賃金は実質でいくら目減りするか ===")
    print(f"  昇給は{BASE_RATE:.0%}のまま。名目の生涯賃金は "
          f"{lifetime(START, BASE_RATE):,}円")
    print(f"{'物価上昇率':>12}{'38年目の名目':>15}{'38年目の実質':>15}"
          f"{'実質の生涯賃金':>18}{'目減り':>14}")
    for row in real_grid():
        print(f"{row['inflation']:>11.1%}{row['nominal_final']:>14,}円"
              f"{row['real_final']:>14,}円{row['real_total']:>17,}円"
              f"{row['lost']:>13,}円")

    print("\n=== 物価に負けない昇給率はいくつで、届かないと生涯賃金でいくら損か ===")
    print(f"{'物価上昇率':>12}{'要る昇給率':>13}{'2パーセントとの差':>20}"
          f"{'実質（昇給2パーセント）':>26}{'実質（要る昇給率）':>22}{'開き':>14}")
    for row in keep_grid():
        print(f"{row['inflation']:>11.1%}{row['need']:>12.1%}"
              f"{row['short']:>19.1%}{row['have_total']:>25,}円"
              f"{row['keep_total']:>21,}円{row['gap']:>13,}円")

    print("\n=== 昇給が止まる年が5年ちがうと、生涯賃金はいくら変わるか ===")
    print(f"  昇給{BASE_RATE:.0%}・年収{START:,}円 から38年")
    print(f"{'昇給が止まる年':>16}{'38年目の年収':>15}{'生涯賃金':>16}"
          f"{'止まらない場合との差':>23}")
    for row in cap_grid():
        label = f"{row['cap']}年目" if row["cap"] else "止まらない"
        print(f"{label:>16}{row['final']:>14,}円"
              f"{row['lifetime']:>15,}円{row['loss']:>22,}円")
    print("  5年ずれるごとに、生涯賃金がいくら変わるか:")
    for row in cap_year_cost():
        print(f"    {row['from']}年目 → {row['to']}年目  {row['step']:>14,}円")

    print("\n=== 賞与の月数が2か月ちがうのと、昇給率が1ポイントちがうのは、"
          "どちらが大きいか ===")
    print(f"  月給{MONTHLY:,}円・昇給{BASE_RATE:.0%}・38年")
    print(f"{'賞与の月数':>12}{'初年度の年収':>15}{'38年目の年収':>15}"
          f"{'生涯賃金':>16}{'0か月との差':>16}")
    for row in bonus_grid():
        print(f"{row['months']:>10}か月{row['first']:>14,}円"
              f"{row['final']:>14,}円{row['lifetime']:>15,}円{row['gain']:>15,}円")
    v = bonus_vs_rate()
    print(f"  賞与4か月・昇給{BASE_RATE:.0%} の生涯賃金 {v['base']:,}円 を元にすると、"
          f"賞与を2か月 増やすと {v['plus_bonus']:,}円、"
          f"昇給を1ポイント上げると {v['plus_rate']:,}円 増えます。"
          f"差は {v['diff']:,}円")


if __name__ == "__main__":
    main()
