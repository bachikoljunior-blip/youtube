"""生命保険料控除 —— **「4段の表」と書いてありますが、手取りで見ると6段あります。**

一般の解説は、所得税と住民税の段階表を2つ並べるところで終わります。
この計算が出すのは、その2つを**同時に**動かして初めて見える数字です。

## 段は4段ではなく6段です。境目が完全に交互に並びます

所得税の表は4段（2万・4万・8万で折れる）、住民税の表も4段（1.2万・3.2万・5.6万で
折れる）。**折れる点が1つも重なりません。** 保険料を1円ずつ増やしていくと、
2つの表が交互に折れるので、**手取りで見た段は6段**になります。

    保険料の帯          所得税の傾き   住民税の傾き   1円あたり戻る額（税率20%）
         0 〜 12,000        1.00          1.00           0.300円
    12,000 〜 20,000        1.00          0.50           0.250円
    20,000 〜 32,000        0.50          0.50           0.150円
    32,000 〜 40,000        0.50          0.25           0.125円
    40,000 〜 56,000        0.25          0.25           0.075円
    56,000 〜 80,000        0.25          0.00           0.050円
    80,000 〜               0.00          0.00           0円

**境目は 12,000 / 20,000 / 32,000 / 40,000 / 56,000 / 80,000 の6つで、
住民税・所得税・住民税・所得税・住民税・所得税と完全に交互**です。
どちらか一方の表だけを見ているかぎり、この6段は一度も現れません。

## 頭打ちになる保険料が、所得税と住民税で24,000円ちがいます

1つの区分だけに払う人で見ると、住民税の控除は**保険料56,000円で止まり**、
所得税の控除は**80,000円まで伸びます。**

**そのあいだの24,000円は、住民税の減税が1円も増えません。**
所得税の控除は6,000円増えるので、税率20パーセントなら減税は1,200円。
**24,000円払って1,200円** ＝ 戻り率5.0パーセントです。

同じ保険なのに、**「まだ効く上限」が制度によって別の場所にあります。**

## 住民税だけ、区分ごとの上限を足すと全体の上限をはみ出します

    　　　　　区分ごとの上限   ×3区分     全体の上限     差
    所得税      40,000円     120,000円   120,000円    **0円**
    住民税      28,000円      84,000円    70,000円  **−14,000円**

**所得税はぴったり一致します。** 3区分それぞれで上限まで取ると、合計上限と
1円も違わない。**住民税だけが14,000円はみ出して、その分は必ず捨てられます。**

14,000円は、住民税の区分ごとの上限28,000円の**ちょうど半分**です。
つまり住民税では、**3区分のうち実質2.5区分ぶんしか使えません。**

## 同じ控除に届く保険料が、払い方で16,000円ちがいます（住民税だけ）

住民税の合計上限70,000円に届く払い方は1つではありません。

    3区分に均等に払う      37,334円 × 3 ＝ **112,000円**
    2区分に寄せて払う      56,000円 × 2 ＋ 16,000円 ＝ **128,000円**

**同じ控除70,000円に、16,000円ちがう保険料が要ります**（1.14倍）。
寄せると、上限28,000円に当たった区分の傾きが0になるからです。

**所得税では、この差が出ません。** 区分ごとの上限40,000円の3倍が全体の上限
120,000円とぴったり同じなので、**どう配っても240,000円が要ります。**
住民税は寄せると損をし、所得税は寄せても寄せなくても同じ。**向きが違います。**

## 最初の1円と最後の1円の戻り率の比は、税率が低い人ほど大きくなります

    所得税率     最初の1円   最後に効く1円    比
      5%        0.150円     0.0125円     **12.00倍**
     10%        0.200円     0.0250円       8.00倍
     20%        0.300円     0.0500円       6.00倍
     23%        0.330円     0.0575円       5.74倍
     33%        0.430円     0.0825円       5.21倍
     40%        0.500円     0.1000円       5.00倍
     45%        0.550円     0.1125円     **4.89倍**

最後に効く帯（56,000〜80,000円）では住民税の傾きが0なので、戻るのは
**所得税ぶんの4分の1だけ**です。住民税の10パーセントは全員に同じだけ効くので、
**所得税率が低い人ほど、その一定分が消えたときの落ち幅が大きくなります。**

**「高い税率の人ほど控除が有利」と言われますが、この比では逆向き**です。
額では高税率の人が得をし、**前半と後半の落差では低税率の人のほうが大きい。**

## 保険料を6.7倍払っても、戻る額は2.9倍にしかなりません

    保険料           控除（所得税）   控除（住民税）   戻る額（税率20%）   戻り率
     36,000円         36,000円        36,000円      10,800円        30.00%
    112,000円         86,001円        70,000円      24,200円        21.61%
    240,000円        120,000円        70,000円      31,000円        12.92%

**保険料は6.67倍、戻る額は2.87倍**です。戻り率は30.00パーセントから
12.92パーセントへ、**半分以下**に落ちます。
"""
from __future__ import annotations

import math

from . import _checks

# ---- 制度の値 -----------------------------------------------------------
# 新制度（平成24年1月1日以後に締結した契約）の段階表。
# (この額まで, 支払保険料に掛ける割合, 足す額)。**最後の段は上限額そのもの。**
# 所得税法76条1項（一般生命保険料）・同2項（介護医療保険料）・同3項（個人年金保険料）
INCOME_STEPS: list[tuple[int | None, float, int]] = [
    (20_000, 1.0, 0),
    (40_000, 0.5, 10_000),
    (80_000, 0.25, 20_000),
    (None, 0.0, 40_000),
]

# 地方税法34条の2第1項・同314条の2第1項（道府県民税・市町村民税）
RESIDENT_STEPS: list[tuple[int | None, float, int]] = [
    (12_000, 1.0, 0),
    (32_000, 0.5, 6_000),
    (56_000, 0.25, 14_000),
    (None, 0.0, 28_000),
]

# 区分ごとの上限（表の最後の段）。
INCOME_CAP_PER_KIND = INCOME_STEPS[-1][2]        # 40,000円
RESIDENT_CAP_PER_KIND = RESIDENT_STEPS[-1][2]    # 28,000円

# 3区分（一般生命保険料・介護医療保険料・個人年金保険料）を合計したときの上限。
INCOME_CAP_TOTAL = 120_000       # 所得税法76条4項
RESIDENT_CAP_TOTAL = 70_000      # 地方税法34条の2第1項ただし書
KINDS = 3

# 住民税の所得割の標準税率（道府県民税4% ＋ 市町村民税6%）。
RESIDENT_RATE = 0.10

# 所得税の速算表の税率（所得税法89条）。
INCOME_RATES = (0.05, 0.10, 0.20, 0.23, 0.33, 0.40, 0.45)

# 節1・節5で代表として使う所得税率。
SAMPLE_RATE = 0.20

ASSUMPTIONS = [
    "生命保険料控除は、払った保険料そのものではなく、"
    "段階表で計算した控除額が所得から引かれる仕組みです。"
    "この計算は、平成24年1月1日以後に契約した新制度の表だけを使っています",
    "所得税の控除額は、年間の支払保険料が20,000円以下なら全額、"
    "20,000円超40,000円以下なら支払額の2分の1に10,000円を足した額、"
    "40,000円超80,000円以下なら支払額の4分の1に20,000円を足した額、"
    "80,000円超なら一律40,000円としています",
    "住民税の控除額は、年間の支払保険料が12,000円以下なら全額、"
    "12,000円超32,000円以下なら支払額の2分の1に6,000円を足した額、"
    "32,000円超56,000円以下なら支払額の4分の1に14,000円を足した額、"
    "56,000円超なら一律28,000円としています",
    "区分は一般生命保険料・介護医療保険料・個人年金保険料の3区分とし、"
    "3区分を合計した控除額の上限は所得税120,000円・住民税70,000円としています",
    "住民税の所得割の税率は、道府県民税と市町村民税を合わせた標準税率の"
    "10パーセントで置いています。自治体によって異なる場合があります",
    "所得税率は仮定です。断りのない表では20パーセントとして置いています。"
    "実際には課税所得に応じて5パーセントから45パーセントまで変わります",
    "復興特別所得税（所得税額の2.1パーセント）は入れていません。"
    "入れれば戻る額はわずかに増えます",
    "控除額に1円未満の端数が出たときは切り上げています",
    "旧制度（平成23年12月31日以前の契約）の表と、"
    "新旧を合わせて適用する場合の調整は入れていません",
]


# ---- 控除額を引く -------------------------------------------------------
def _deduction(premium: float, steps: list[tuple[int | None, float, int]]) -> int:
    """段階表から控除額を引く。**円未満は切り上げます。**"""
    if premium < 0:
        raise ValueError(f"保険料が負です: {premium}")
    for cap, slope, base in steps:
        if cap is None or premium <= cap:
            return math.ceil(premium * slope + base)
    raise ValueError(f"保険料が表に当たりません: {premium}")


def _slope(premium: float, steps: list[tuple[int | None, float, int]]) -> float:
    """その保険料の帯での傾き（1円多く払うと控除がいくら増えるか）。"""
    for cap, slope, _ in steps:
        if cap is None or premium < cap:
            return slope
    raise ValueError(f"保険料が表に当たりません: {premium}")


def income_deduction(premium: float) -> int:
    """1区分ぶんの所得税の生命保険料控除。"""
    return _deduction(premium, INCOME_STEPS)


def resident_deduction(premium: float) -> int:
    """1区分ぶんの住民税の生命保険料控除。"""
    return _deduction(premium, RESIDENT_STEPS)


# ---- 節1: 段は6段。境目が交互に並ぶ -------------------------------------
def breakpoints() -> list[dict]:
    """2つの表の折れ点を1本に並べる。**どちらの表の折れ点かも返します。**"""
    rows = []
    for cap, _, _ in INCOME_STEPS[:-1]:
        rows.append({"保険料": cap, "どちらの表": "所得税"})
    for cap, _, _ in RESIDENT_STEPS[:-1]:
        rows.append({"保険料": cap, "どちらの表": "住民税"})
    return sorted(rows, key=lambda r: r["保険料"])


def breakpoints_alternate() -> bool:
    """**折れ点が住民税と所得税で完全に交互か。**"""
    which = [r["どちらの表"] for r in breakpoints()]
    return all(a != b for a, b in zip(which, which[1:]))


def marginal_bands(rate: float = SAMPLE_RATE) -> list[dict]:
    """帯ごとの、1円あたり戻る額。**表は4段ずつなのに、ここは6段＋0になります。**"""
    edges = [0] + [r["保険料"] for r in breakpoints()]
    rows = []
    for low, high in zip(edges, edges[1:] + [None]):
        probe = (low + high) / 2 if high is not None else low + 10_000
        si = _slope(probe, INCOME_STEPS)
        sj = _slope(probe, RESIDENT_STEPS)
        rows.append({
            "下限": low, "上限": high,
            "所得税の傾き": si, "住民税の傾き": sj,
            "1円あたり戻る額": si * rate + sj * RESIDENT_RATE,
        })
    return rows


def marginal_levels(rate: float = SAMPLE_RATE) -> list[float]:
    """**戻る額が0でない帯の、値のちがい**（＝手取りで見た段の数）。"""
    seen: list[float] = []
    for row in marginal_bands(rate):
        v = row["1円あたり戻る額"]
        if v > 0 and not any(abs(v - s) < 1e-12 for s in seen):
            seen.append(v)
    return seen


# ---- 節2: 頭打ちになる点が2つある ---------------------------------------
def cap_points() -> dict:
    """区分ごとに、控除が伸びなくなる保険料。**所得税と住民税でずれます。**"""
    inc = INCOME_STEPS[-2][0]        # 80,000
    res = RESIDENT_STEPS[-2][0]      # 56,000
    return {
        "所得税が止まる保険料": inc,
        "住民税が止まる保険料": res,
        "ずれ": inc - res,
    }


def dead_zone(rate: float = SAMPLE_RATE) -> dict:
    """**住民税が1円も増えないのに、所得税だけが増える帯。**"""
    gap = cap_points()
    low, high = gap["住民税が止まる保険料"], gap["所得税が止まる保険料"]
    d_inc = income_deduction(high) - income_deduction(low)
    d_res = resident_deduction(high) - resident_deduction(low)
    paid = high - low
    back = d_inc * rate + d_res * RESIDENT_RATE
    return {
        "帯": (low, high), "払う額": paid,
        "増える所得税控除": d_inc, "増える住民税控除": d_res,
        "戻る額": back, "戻り率": back / paid,
    }


# ---- 節3: 住民税だけ、上限の合計がはみ出す ------------------------------
def cap_overflow() -> list[dict]:
    """区分ごとの上限 × 3 と、全体の上限を突き合わせる。"""
    rows = []
    for name, per, total in (("所得税", INCOME_CAP_PER_KIND, INCOME_CAP_TOTAL),
                             ("住民税", RESIDENT_CAP_PER_KIND, RESIDENT_CAP_TOTAL)):
        rows.append({
            "制度": name, "区分ごとの上限": per, "3区分の合計": per * KINDS,
            "全体の上限": total, "はみ出す額": per * KINDS - total,
            "使える区分の数": total / per,
        })
    return rows


# ---- 節4: 同じ控除に届く保険料が、払い方でちがう ------------------------
def even_premium_for_total(total_cap: int,
                           steps: list[tuple[int | None, float, int]]) -> float:
    """3区分に均等に払って、合計の上限にちょうど届く保険料の総額。"""
    per_deduction = total_cap / KINDS
    for cap, slope, base in steps:
        if slope == 0:
            continue
        premium = (per_deduction - base) / slope
        low = 0 if steps.index((cap, slope, base)) == 0 else \
            steps[steps.index((cap, slope, base)) - 1][0]
        if low <= premium <= (cap if cap is not None else premium):
            return premium * KINDS
    raise ValueError("均等に払って合計上限へ届く点が見つかりません")


def concentrated_premium_for_total(
        total_cap: int, per_cap: int,
        steps: list[tuple[int | None, float, int]]) -> float:
    """**上限に当たるまで区分に寄せて払った**ときの保険料の総額。"""
    full = total_cap // per_cap                 # 上限まで使い切る区分の数
    rest = total_cap - full * per_cap           # 残りの区分で要る控除額
    premium = full * _premium_for_deduction(per_cap, steps)
    if rest:
        premium += _premium_for_deduction(rest, steps)
    return premium


def _premium_for_deduction(deduction: float,
                           steps: list[tuple[int | None, float, int]]) -> float:
    """その控除額にちょうど届く、1区分ぶんの保険料。"""
    for cap, slope, base in steps:
        if slope == 0:
            return steps[-2][0]
        premium = (deduction - base) / slope
        if premium <= (cap if cap is not None else premium):
            return premium
    raise ValueError(f"控除額 {deduction} に届く保険料が見つかりません")


def split_cost() -> list[dict]:
    """均等と寄せで、同じ合計上限に届く保険料を比べる。"""
    rows = []
    for name, total, per, steps in (
            ("所得税", INCOME_CAP_TOTAL, INCOME_CAP_PER_KIND, INCOME_STEPS),
            ("住民税", RESIDENT_CAP_TOTAL, RESIDENT_CAP_PER_KIND, RESIDENT_STEPS)):
        even = even_premium_for_total(total, steps)
        conc = concentrated_premium_for_total(total, per, steps)
        rows.append({
            "制度": name, "合計上限": total,
            "均等に払う": even, "寄せて払う": conc,
            "差": conc - even, "倍率": conc / even,
        })
    return rows


# ---- 節5: 最初の1円と最後の1円 ------------------------------------------
def first_last_ratio(rate: float) -> dict:
    """**いちばん効く1円と、最後に効く1円**の比。"""
    bands = [b for b in marginal_bands(rate) if b["1円あたり戻る額"] > 0]
    first, last = bands[0], bands[-1]
    return {
        "所得税率": rate,
        "最初の1円": first["1円あたり戻る額"],
        "最後の1円": last["1円あたり戻る額"],
        "比": first["1円あたり戻る額"] / last["1円あたり戻る額"],
    }


def first_last_grid() -> list[dict]:
    """所得税率べつに並べる。**税率が低いほど比が大きくなります。**"""
    return [first_last_ratio(r) for r in INCOME_RATES]


# ---- 節6: 払った額と戻る額 ----------------------------------------------
def total_deduction(premiums: list[float]) -> dict:
    """3区分ぶんの保険料から、合計の控除額を出す（**全体の上限で切ります**）。"""
    if len(premiums) != KINDS:
        raise ValueError(f"区分は {KINDS} つです: {len(premiums)}")
    inc = min(sum(income_deduction(p) for p in premiums), INCOME_CAP_TOTAL)
    res = min(sum(resident_deduction(p) for p in premiums), RESIDENT_CAP_TOTAL)
    return {"保険料": sum(premiums), "所得税の控除": inc, "住民税の控除": res}


def refund(premiums: list[float], rate: float = SAMPLE_RATE) -> dict:
    """戻る額と戻り率。"""
    d = total_deduction(premiums)
    back = d["所得税の控除"] * rate + d["住民税の控除"] * RESIDENT_RATE
    return {**d, "戻る額": back, "戻り率": back / d["保険料"] if d["保険料"] else 0.0}


def refund_grid(rate: float = SAMPLE_RATE) -> list[dict]:
    """**代表的な3つの払い方。**戻り率は単調に下がります。"""
    minimal = RESIDENT_STEPS[0][0]                        # 12,000円
    even = even_premium_for_total(RESIDENT_CAP_TOTAL, RESIDENT_STEPS) / KINDS
    full = INCOME_STEPS[-2][0]                            # 80,000円
    return [refund([p] * KINDS, rate) for p in (minimal, even, full)]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(INCOME_CAP_PER_KIND, 40_000, "所得税の区分ごとの上限",
                      source="所得税法76条1項")
    _checks.statutory(INCOME_CAP_TOTAL, 120_000, "所得税の合計上限",
                      source="所得税法76条4項")
    _checks.statutory(RESIDENT_CAP_PER_KIND, 28_000, "住民税の区分ごとの上限",
                      source="地方税法34条の2第1項")
    _checks.statutory(RESIDENT_CAP_TOTAL, 70_000, "住民税の合計上限",
                      source="地方税法34条の2第1項ただし書")
    _checks.statutory(RESIDENT_RATE, 0.10, "住民税の所得割の標準税率",
                      source="地方税法35条・314条の3")
    _checks.ratio(RESIDENT_RATE, "住民税の所得割の標準税率")
    # 表の折れ目が段階表のとおりか（段の入口で控除額が続いていること）
    _checks.statutory(income_deduction(20_000), 20_000, "保険料2万円の所得税控除",
                      source="所得税法76条1項1号")
    _checks.statutory(income_deduction(40_000), 30_000, "保険料4万円の所得税控除",
                      source="同2号")
    _checks.statutory(income_deduction(80_000), 40_000, "保険料8万円の所得税控除",
                      source="同3号")
    _checks.statutory(resident_deduction(12_000), 12_000, "保険料1.2万円の住民税控除",
                      source="地方税法34条の2第1項1号")
    _checks.statutory(resident_deduction(32_000), 22_000, "保険料3.2万円の住民税控除",
                      source="同2号")
    _checks.statutory(resident_deduction(56_000), 28_000, "保険料5.6万円の住民税控除",
                      source="同3号")
    _checks.never_decreases(income_deduction, [0, 20_000, 40_000, 80_000, 200_000],
                            "保険料が増えたのに所得税の控除が減っている")
    _checks.never_decreases(resident_deduction, [0, 12_000, 32_000, 56_000, 200_000],
                            "保険料が増えたのに住民税の控除が減っている")

    # 2. **主題その1。** 表は4段ずつなのに、手取りでは6段。境目は完全に交互
    if len(INCOME_STEPS) != 4 or len(RESIDENT_STEPS) != 4:
        raise _checks.TableError("段階表が4段ではありません")
    bp = breakpoints()
    if len(bp) != 6:
        raise _checks.TableError(f"折れ点が6つではありません: {len(bp)}")
    _checks.ascending([r["保険料"] for r in bp], "折れ点", strict=True)
    if not breakpoints_alternate():
        raise _checks.TableError(
            "折れ点が交互に並んでいません: "
            f"{[r['どちらの表'] for r in bp]}")
    if bp[0]["どちらの表"] != "住民税":
        raise _checks.TableError("いちばん低い折れ点が住民税の側ではありません")
    levels = marginal_levels()
    if len(levels) != 6:
        raise _checks.TableError(f"手取りで見た段が6段ではありません: {len(levels)}段")
    _checks.close(levels[0], 0.30, "最初の帯で1円あたり戻る額（税率20%）", tol=1e-12)
    _checks.close(levels[-1], 0.05, "最後の帯で1円あたり戻る額（税率20%）", tol=1e-12)
    # **段が下がりっぱなしであること**（途中で上がると「6段」の意味が変わります）
    for a, b in zip(levels, levels[1:]):
        if not a > b:
            raise _checks.TableError(f"戻る額が下がっていません: {a} → {b}")

    # 3. **主題その2。** 頭打ちの点が2つあり、あいだは住民税が動かない
    caps = cap_points()
    _checks.statutory(caps["所得税が止まる保険料"], 80_000, "所得税が頭打ちになる保険料",
                      source="所得税法76条1項3号")
    _checks.statutory(caps["住民税が止まる保険料"], 56_000, "住民税が頭打ちになる保険料",
                      source="地方税法34条の2第1項3号")
    _checks.statutory(caps["ずれ"], 24_000, "頭打ちの点のずれ", source="表から導いた値")
    dz = dead_zone()
    _checks.statutory(dz["増える住民税控除"], 0,
                      "住民税が止まったあとに増える住民税控除",
                      source="表から導いた値")
    _checks.greater(dz["増える所得税控除"], 0,
                    "その帯で所得税の控除が増えていない")
    _checks.close(dz["戻り率"], 0.05, "その帯の戻り率（税率20%）", tol=1e-12)

    # 4. **主題その3。** 住民税だけ、区分ごとの上限×3 が全体の上限をはみ出す
    over = {r["制度"]: r for r in cap_overflow()}
    _checks.statutory(over["所得税"]["はみ出す額"], 0,
                      "所得税で上限の合計がはみ出す額", source="表から導いた値")
    _checks.statutory(over["住民税"]["はみ出す額"], 14_000,
                      "住民税で上限の合計がはみ出す額", source="表から導いた値")
    _checks.close(over["住民税"]["はみ出す額"], RESIDENT_CAP_PER_KIND / 2,
                  "はみ出す額が区分ごとの上限の半分", tol=1e-12)
    _checks.close(over["住民税"]["使える区分の数"], 2.5,
                  "住民税で実際に使える区分の数", tol=1e-12)

    # 5. **主題その4。** 同じ控除に届く保険料が、払い方でちがう（住民税だけ）
    split = {r["制度"]: r for r in split_cost()}
    _checks.close(split["住民税"]["均等に払う"], 112_000,
                  "住民税の上限に均等で届く保険料", tol=1e-6)
    _checks.close(split["住民税"]["寄せて払う"], 128_000,
                  "住民税の上限に寄せて届く保険料", tol=1e-6)
    _checks.close(split["住民税"]["差"], 16_000, "払い方でちがう額", tol=1e-6)
    _checks.close(split["所得税"]["差"], 0, "所得税で払い方によってちがう額",
                  tol=1e-6)
    _checks.close(split["所得税"]["均等に払う"], 240_000,
                  "所得税の上限に届く保険料", tol=1e-6)

    # 6. **主題その5。** 最初と最後の比は、税率が低いほど大きい
    grid = first_last_grid()
    _checks.close(grid[0]["比"], 12.0, "税率5%での最初と最後の比", tol=1e-9)
    _checks.close(grid[-1]["比"], 4.888888888, "税率45%での最初と最後の比", tol=1e-6)
    _checks.decreases_with(lambda r: first_last_ratio(r)["比"], INCOME_RATES,
                           "税率が上がったのに最初と最後の比が下がっていない")
    # **額では逆向き**であること（高税率ほど1円あたりの戻りは大きい）
    _checks.increases_with(lambda r: first_last_ratio(r)["最初の1円"], INCOME_RATES,
                           "税率が上がったのに最初の1円の戻りが増えていない")

    # 7. **主題その6。** 払った額と戻る額の伸びが釣り合わない
    rows = refund_grid()
    _checks.close(rows[0]["戻り率"], 0.30, "保険料36,000円のときの戻り率", tol=1e-12)
    _checks.close(rows[-1]["戻る額"], 31_000, "保険料240,000円のときに戻る額",
                  tol=1e-9)
    _checks.decreases_with(lambda i: refund_grid()[i]["戻り率"], [0, 1, 2],
                           "保険料が増えたのに戻り率が下がっていない")
    paid = rows[-1]["保険料"] / rows[0]["保険料"]
    got = rows[-1]["戻る額"] / rows[0]["戻る額"]
    _checks.greater(paid, got, "払った額の倍率が戻った額の倍率より大きくない")
    _checks.close(paid, 20 / 3, "保険料の倍率", tol=1e-9)
    _checks.close(got, 31_000 / 10_800, "戻る額の倍率", tol=1e-9)

    _checks.unique_by(breakpoints(), lambda r: r["保険料"], "折れ点の表")
    _checks.assumption_values(ASSUMPTIONS, name="seimeihoken")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 表は4段ずつ。手取りで見ると6段で、境目は完全に交互 ===")
    for row in breakpoints():
        print(f"  {row['保険料']:>8,}円  ← {row['どちらの表']}の表が折れる")
    print(f"  → 交互に並んでいるか: {breakpoints_alternate()}")
    for row in marginal_bands():
        high = f"{row['上限']:>8,}" if row["上限"] else "  以上  "
        print(f"  {row['下限']:>8,} 〜 {high}  "
              f"所得税 {row['所得税の傾き']:.2f} / 住民税 {row['住民税の傾き']:.2f}  "
              f"→ 1円あたり **{row['1円あたり戻る額']:.4f}円**")
    print(f"  → 手取りで見た段: **{len(marginal_levels())}段**"
          f"（表はどちらも4段）")

    print("\n=== 頭打ちになる保険料が、所得税と住民税で24,000円ずれる ===")
    caps = cap_points()
    print(f"  住民税が止まる {caps['住民税が止まる保険料']:,}円 ／ "
          f"所得税が止まる {caps['所得税が止まる保険料']:,}円 "
          f"→ ずれ **{caps['ずれ']:,}円**")
    dz = dead_zone()
    print(f"  そのあいだの {dz['払う額']:,}円: "
          f"所得税の控除 +{dz['増える所得税控除']:,}円 ／ "
          f"住民税の控除 +{dz['増える住民税控除']:,}円 "
          f"→ 戻る額 {dz['戻る額']:,.0f}円（**戻り率 {dz['戻り率']:.1%}**）")

    print("\n=== 住民税だけ、区分ごとの上限×3 が全体の上限をはみ出す ===")
    for row in cap_overflow():
        print(f"  {row['制度']}  区分ごと {row['区分ごとの上限']:>7,}円 ×3 ＝ "
              f"{row['3区分の合計']:>8,}円  全体 {row['全体の上限']:>8,}円  "
              f"はみ出し **{row['はみ出す額']:>+7,}円**  "
              f"（使えるのは {row['使える区分の数']:.1f}区分ぶん）")

    print("\n=== 同じ控除に届く保険料が、払い方で16,000円ちがう（住民税だけ）===")
    for row in split_cost():
        print(f"  {row['制度']}  上限 {row['合計上限']:>8,}円  "
              f"均等 {row['均等に払う']:>9,.0f}円 ／ 寄せ {row['寄せて払う']:>9,.0f}円  "
              f"差 **{row['差']:>+8,.0f}円**（{row['倍率']:.2f}倍）")

    print("\n=== 最初の1円と最後の1円の比は、税率が低い人ほど大きい ===")
    for row in first_last_grid():
        print(f"  所得税率 {row['所得税率']:>5.0%}  "
              f"最初 {row['最初の1円']:.4f}円 ／ 最後 {row['最後の1円']:.4f}円  "
              f"→ **{row['比']:.2f}倍**")

    print("\n=== 保険料6.67倍に対して、戻る額は2.87倍 ===")
    for row in refund_grid():
        print(f"  保険料 {row['保険料']:>9,.0f}円  "
              f"控除 所得税 {row['所得税の控除']:>7,}円 / 住民税 {row['住民税の控除']:>6,}円  "
              f"戻る {row['戻る額']:>8,.0f}円  （**{row['戻り率']:.2%}**）")
