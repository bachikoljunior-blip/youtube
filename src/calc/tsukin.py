"""通勤手当の非課税限度額 —— **「非課税」は「タダで受け取れる」という意味ではありません。**

一般の解説はここで止まります ——「交通機関なら月15万円まで、マイカーなら距離に応じて
最高31,600円まで非課税です」。**限度額の表を写すところで終わります。**

この計算が出すのは、その表を割ったり比べたりして初めて出る数字です。

## 距離の崖は、額でいちばん大きいものが2つあります

片道の距離が1メートル違うだけで、1か月の非課税限度額が跳びます。

    境目      跳ぶ額      倍率
     2km    ＋4,200円    0円から
    10km    ＋2,900円    1.69倍
    15km    **＋5,800円**  **1.82倍**
    25km    **＋5,800円**  1.45倍
    35km    ＋5,700円    1.30倍
    45km    ＋3,600円    1.15倍
    55km    ＋3,600円    1.13倍

**額でいちばん大きい崖は15kmと25kmの2つで、まったくの同額**です（月5,800円・年69,600円）。
**どちらか一方を「いちばん大きい崖」と呼ぶと嘘になります。**
**率で聞くと答えが変わり、15kmが単独の1位**（1.82倍）になります。
**同じ表に「いちばん」を聞いて、額と率で答えが違う**ということです。

## 1kmあたりの単価は、のこぎりの形をしています

限度額を距離で割ると、帯の入口でいちばん高く、帯の出口でいちばん安くなります。

    帯の入口   2km     **2,100円/km**   ← 全体の最大
              10km       710円/km
              15km       860円/km      ← 入口の高さも単調ではない
              25km       748円/km
              55km       575円/km
    帯の出口   10km直前   **420円/km**   ← 全体の最小

**最大と最小の比はちょうど5.0倍**です（2,100 ÷ 420）。
そして**入口の高さそのものが単調ではありません** —— 10kmの710円/kmより
15kmの860円/kmのほうが高い。**「遠いほど1kmあたりは安くなる」も成り立ちません。**

## 非課税でも、厚生年金保険料は通勤手当にかかります

非課税なのは**所得税と住民税だけ**です。標準報酬月額を決める「報酬」には
通勤手当が入るので（健康保険法3条5項・厚生年金保険法3条1項3号）、
**通勤手当が等級を押し上げれば、保険料はその場で増えます。**

報酬月額300,000円の人が月31,600円の通勤手当を受け取ると、
標準報酬月額は300,000円 → 340,000円。厚生年金の本人負担は
**年43,920円増えます**（通勤手当の年額379,200円に対して11.58パーセント）。

そして**逃げ道がありません。** 報酬月額20万〜50万円の帯で、
標準報酬月額の段の幅はいちばん広いところでも30,000円。
**55km以上の通勤手当31,600円は、その幅より大きい** ——
つまり**どの報酬月額から出発しても、必ず1つ以上の等級をまたぎます。**
31本の点を並べて、**保険料が1円も増えない人は0人**でした。

    増える年額     手当に対する割合
     21,960円        5.79%   ← 保険料率9.15%より低い
     32,940円        8.69%
     43,920円       11.58%   ← 保険料率9.15%より高い

**保険料率は9.15パーセントの一定なのに、通勤手当に対して実際にかかる割合は
5.79〜11.58パーセントに散らばります。** 段の幅と手当の額の噛み合わせで決まるので、
**通勤距離が同じでも、月給によって取られる額が2倍違います。**

2キロメートル帯の4,200円なら段の幅より小さいので、
またぐ人とまたがない人に分かれます（1,000円刻みで見て301点中52点だけが増える）。
**手当が小さいうちは運ですが、31,600円になると運の要素が消えます。**

## 同じ距離でも、電車とマイカーで上限が4.75倍ちがいます

交通機関の限度額は月150,000円、マイカーの最高額は月31,600円。
**差は月118,400円、年1,420,800円**です。

**距離が同じでも、通う手段が変わるだけでこれだけ動きます。**
両方を使う場合は合算して150,000円が限度なので（所得税法施行令20条の2第4号）、
マイカーで31,600円を使うと、定期券に回せる非課税枠は118,400円になります。

## 非課税枠が実費に届かないのは、近い人と、9km台と、68km以上だけです

ガソリン代を1kmあたり11.67円（燃費15km/L・ガソリン175円/L）、
月20日の往復として置くと、月の実費は片道距離の466.7倍です。
限度額と突き合わせると、**足りなくなる距離は3か所しかありません。**

    2km未満        限度額は0円      **全額が課税**
    9.00〜10.00km  4,200円が上限     実費のほうが上（1kmぶんの窓）
    67.71km以上    31,600円で頭打ち  以後ずっと足りない

**いちばん近い人と、9km台の人と、68km以上の人だけが自腹になります。**
10.0kmから67.7kmまでのあいだは、この置き方では実費を上回ります。
**「遠い人ほど損をする」ではありません。**

## 55km以上は頭打ちで、距離が2倍でも1円も増えません

    55km   31,600円   実費の123パーセント
   100km   31,600円   実費の 68パーセント
   200km   31,600円   実費の 34パーセント

**限度額の表は55kmで終わっているので、そこから先は距離という軸そのものが消えます。**
"""
from __future__ import annotations

from . import _checks
from . import shahoken

# ---- 制度の値（所得税法施行令20条の2。平成28年度改正後の額）---------------
# 交通機関または有料道路を利用する人の1か月あたりの非課税限度額（同条1号）。
KOTSU_CAP = 150_000

# 交通機関とマイカーを併用する人も、合算してこの額が限度（同条4号）。
HEIYO_CAP = KOTSU_CAP

# マイカー・自転車などで通う人の、片道の通勤距離に応じた1か月の限度額（同条2号）。
# (下限km, 上限km or None, 限度額)。**下限以上・上限未満**で読みます。
CAR_BANDS: list[tuple[float, float | None, int]] = [
    (0, 2, 0),
    (2, 10, 4_200),
    (10, 15, 7_100),
    (15, 25, 12_900),
    (25, 35, 18_700),
    (35, 45, 24_400),
    (45, 55, 28_000),
    (55, None, 31_600),
]

# 実費を置くための仮定（制度の値ではありません）。
FUEL_YEN_PER_LITER = 175
KM_PER_LITER = 15
WORK_DAYS = 20
YEN_PER_KM = FUEL_YEN_PER_LITER / KM_PER_LITER      # 11.667円/km
KM_PER_MONTH_FACTOR = WORK_DAYS * 2                 # 往復・月20日

# 節3で使う報酬月額の代表値。
BASE_MONTHLY = 300_000
TOP_ALLOWANCE = CAR_BANDS[-1][2]                    # 31,600円（55km以上）
SMALL_ALLOWANCE = CAR_BANDS[1][2]                   # 4,200円（2km以上10km未満）

ASSUMPTIONS = [
    "会社から通勤手当をもらっている給与所得者について、"
    "そのうちいくらまでが所得税と住民税のかからない額かを計算しています",
    "交通機関で通う人の非課税限度額は1か月150,000円としています。"
    "マイカーや自転車で通う人は、片道の通勤距離で決まる額が限度です",
    "マイカーの限度額は、片道2キロメートル未満が0円、"
    "2キロメートル以上10キロメートル未満が4,200円、"
    "10キロメートル以上15キロメートル未満が7,100円、"
    "15キロメートル以上25キロメートル未満が12,900円、"
    "25キロメートル以上35キロメートル未満が18,700円、"
    "35キロメートル以上45キロメートル未満が24,400円、"
    "45キロメートル以上55キロメートル未満が28,000円、"
    "55キロメートル以上が31,600円として計算しています",
    "交通機関とマイカーを両方使う人は、合わせて150,000円が限度としています",
    "ガソリン代は仮定です。1リットル175円、燃費は1リットルあたり15キロメートル、"
    "月の勤務は20日で毎日往復するものとして、1キロメートルあたり11.67円で置いています",
    "駐車場代・高速道路代・車の減価・タイヤや保険の費用は入れていません。"
    "入れれば実費はもっと大きくなるので、自腹になる距離の範囲は広がります",
    "厚生年金保険料は標準報酬月額に9.15パーセントをかけた本人負担分です。"
    "健康保険料と雇用保険料は入れていません",
    "標準報酬月額を決める報酬には通勤手当を含めています。"
    "非課税であっても社会保険料の計算からは外れないためです",
    "厚生年金の標準報酬月額が上がると将来の年金も増えますが、"
    "この計算には入れていません。増える保険料だけを出しています",
    "通勤手当が非課税限度額を超えた分は給与として課税されますが、"
    "その所得税額は計算に入れていません。限度額そのものを比べています",
]


# ---- 限度額を引く -------------------------------------------------------
def car_limit(km: float) -> int:
    """片道の通勤距離から、マイカー通勤の1か月の非課税限度額を引く。"""
    for low, high, limit in CAR_BANDS:
        if km >= low and (high is None or km < high):
            return limit
    raise ValueError(f"距離が表に当たりません: {km}")


def band_of(km: float) -> tuple[float, float | None, int]:
    """その距離が入る帯を返す。"""
    for band in CAR_BANDS:
        low, high, _ = band
        if km >= low and (high is None or km < high):
            return band
    raise ValueError(f"距離が表に当たりません: {km}")


# ---- 節1: 境目の崖 ------------------------------------------------------
def cliffs() -> list[dict]:
    """帯の境目ごとの跳び。**額の1位と率の1位が違います。**"""
    rows = []
    for i in range(1, len(CAR_BANDS)):
        before = CAR_BANDS[i - 1][2]
        after = CAR_BANDS[i][2]
        rows.append({
            "境目km": CAR_BANDS[i][0],
            "手前の限度額": before,
            "境目の限度額": after,
            "跳ぶ額": after - before,
            "年で跳ぶ額": (after - before) * 12,
            "倍率": (after / before) if before else None,
        })
    return rows


def biggest_cliffs_by_yen() -> list[dict]:
    """**額でいちばん大きい崖。2件返ります**（15kmと25kmが同額）。"""
    rows = cliffs()
    top = max(r["跳ぶ額"] for r in rows)
    return [r for r in rows if r["跳ぶ額"] == top]


def biggest_cliff_by_ratio() -> dict:
    """**率でいちばん大きい崖。**0円からの2kmは倍率が出ないので外します。"""
    rows = [r for r in cliffs() if r["倍率"] is not None]
    return max(rows, key=lambda r: r["倍率"])


# ---- 節2: 1kmあたりの単価 -----------------------------------------------
EDGE_EPS = 0.001  # 帯の出口を見るための1メートル


def per_km_grid() -> list[dict]:
    """帯ごとの、入口と出口の1kmあたり単価。**のこぎりになります。**"""
    rows = []
    for low, high, limit in CAR_BANDS:
        if low == 0:
            continue
        entry = limit / low
        exit_km = (high - EDGE_EPS) if high is not None else None
        rows.append({
            "帯の入口km": low,
            "限度額": limit,
            "入口の単価": entry,
            "出口km": exit_km,
            "出口の単価": (limit / exit_km) if exit_km else None,
        })
    return rows


def per_km_extremes() -> dict:
    """単価の最大と最小。**上限のない帯は出口が無いので最小から外します。**"""
    rows = per_km_grid()
    hi = max(rows, key=lambda r: r["入口の単価"])
    bounded = [r for r in rows if r["出口の単価"] is not None]
    lo = min(bounded, key=lambda r: r["出口の単価"])
    return {
        "最大の単価": hi["入口の単価"], "最大の距離": hi["帯の入口km"],
        "最小の単価": lo["出口の単価"], "最小の距離": lo["出口km"],
        "比": hi["入口の単価"] / lo["出口の単価"],
    }


def entry_prices_are_monotone() -> bool:
    """入口の単価が距離とともに単調に下がるか。**下がりません。**"""
    prices = [r["入口の単価"] for r in per_km_grid()]
    return all(a > b for a, b in zip(prices, prices[1:]))


# ---- 節3: 非課税でも社会保険料はかかる ----------------------------------
def pension_increase(base: int, allowance: int = TOP_ALLOWANCE) -> dict:
    """通勤手当で増える厚生年金の本人負担。**等級をまたがなければ0円です。**"""
    before = shahoken.premium(base)
    after = shahoken.premium(base + allowance)
    yearly = (after - before) * 12
    return {
        "報酬月額": base,
        "通勤手当": allowance,
        "標準報酬月額(前)": shahoken.grade_of(base),
        "標準報酬月額(後)": shahoken.grade_of(base + allowance),
        "保険料(前)": before,
        "保険料(後)": after,
        "増える月額": after - before,
        "増える年額": yearly,
        "手当に対する割合": yearly / (allowance * 12) if allowance else 0.0,
    }


def pension_grid(allowance: int = TOP_ALLOWANCE,
                 step: int = 10_000) -> list[dict]:
    """報酬月額べつに並べる。**刻みを細かくすると、またがない人が現れます。**"""
    return [pension_increase(base, allowance)
            for base in range(200_000, 500_001, step)]


def pension_zero_rows(allowance: int = TOP_ALLOWANCE,
                      step: int = 10_000) -> list[dict]:
    """**1円も増えない報酬月額。**等級をまたがない人です。"""
    return [r for r in pension_grid(allowance, step) if r["増える年額"] == 0]


def grade_widths(low: int = 200_000, high: int = 500_000) -> list[int]:
    """その範囲の等級の幅。**通勤手当がこれを超えると、必ずまたぎます。**"""
    grades = [g for g in shahoken.GRADES if low <= g <= high]
    return [b - a for a, b in zip(grades, grades[1:])]


def always_crosses(allowance: int) -> bool:
    """**その手当なら、どの報酬月額でも必ず等級をまたぐか。**"""
    return allowance > max(grade_widths())


def pension_over_rate_rows(allowance: int = TOP_ALLOWANCE) -> list[dict]:
    """**保険料率9.15パーセントを超えて取られる報酬月額。**"""
    return [r for r in pension_grid(allowance)
            if r["手当に対する割合"] > shahoken.HALF]


# ---- 節4: 手段でちがう上限 ----------------------------------------------
def mode_gap() -> dict:
    """交通機関とマイカーの上限の差。**距離を見ずに決まります。**"""
    return {
        "交通機関の上限": KOTSU_CAP,
        "マイカーの上限": TOP_ALLOWANCE,
        "月の差": KOTSU_CAP - TOP_ALLOWANCE,
        "年の差": (KOTSU_CAP - TOP_ALLOWANCE) * 12,
        "倍率": KOTSU_CAP / TOP_ALLOWANCE,
        "併用したとき定期券に回せる額": HEIYO_CAP - TOP_ALLOWANCE,
    }


# ---- 節5・6: 実費と突き合わせる -----------------------------------------
def monthly_cost(km: float) -> float:
    """1か月のガソリン代。**片道距離の466.7倍**（往復・月20日）。"""
    return km * KM_PER_MONTH_FACTOR * YEN_PER_KM


def break_even_km(limit: int) -> float:
    """その限度額とガソリン代がちょうど並ぶ距離。"""
    return limit / (KM_PER_MONTH_FACTOR * YEN_PER_KM)


def short_windows() -> list[dict]:
    """**限度額が実費に届かない距離の範囲。**帯ごとに見ます。"""
    out = []
    for low, high, limit in CAR_BANDS:
        be = break_even_km(limit)
        if limit == 0:
            out.append({"帯": (low, high), "限度額": limit,
                        "自腹の始まり": low, "自腹の終わり": high,
                        "帯の全部": True})
            continue
        if high is None:
            out.append({"帯": (low, high), "限度額": limit,
                        "自腹の始まり": be, "自腹の終わり": None,
                        "帯の全部": False})
        elif low < be < high:
            out.append({"帯": (low, high), "限度額": limit,
                        "自腹の始まり": be, "自腹の終わり": high,
                        "帯の全部": False})
    return out


def coverage(km: float) -> dict:
    """限度額が実費の何割をまかなうか。"""
    cost = monthly_cost(km)
    limit = car_limit(km)
    return {"片道km": km, "限度額": limit, "実費": cost,
            "まかなう割合": (limit / cost) if cost else 0.0}


def flat_top_grid() -> list[dict]:
    """55km以上の頭打ち。**距離が増えても限度額は動きません。**"""
    return [coverage(km) for km in (55, 67.71, 100, 150, 200)]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(KOTSU_CAP, 150_000, "交通機関の非課税限度額",
                      source="所得税法施行令20条の2第1号")
    _checks.statutory(CAR_BANDS[1][2], 4_200, "2km以上10km未満の限度額",
                      source="所得税法施行令20条の2第2号")
    _checks.statutory(CAR_BANDS[-1][2], 31_600, "55km以上の限度額",
                      source="同上")
    _checks.statutory(CAR_BANDS[0][2], 0, "2km未満の限度額", source="同上")
    _checks.ascending([b[2] for b in CAR_BANDS], "距離べつの限度額", strict=True)
    _checks.ascending([b[0] for b in CAR_BANDS], "帯の下限", strict=True)

    # 帯が隙間なく繋がっているか（上限＝次の下限）
    for (a_low, a_high, _), (b_low, _, _) in zip(CAR_BANDS, CAR_BANDS[1:]):
        if a_high != b_low:
            raise _checks.TableError(
                f"帯に隙間があります: {a_low}〜{a_high} と {b_low}〜")
    _checks.never_decreases(car_limit, [0, 1.9, 2, 9.99, 10, 54.9, 55, 500],
                            "距離が伸びたのに限度額が減っている")

    # 2. **この表の主題その1。** 額の1位は2件で同点、率の1位は単独
    yen_top = biggest_cliffs_by_yen()
    if len(yen_top) != 2:
        raise _checks.TableError(
            f"額でいちばん大きい崖が2件ではありません: {len(yen_top)}件")
    if [r["境目km"] for r in yen_top] != [15, 25]:
        raise _checks.TableError(
            f"額の1位が15kmと25kmではありません: {[r['境目km'] for r in yen_top]}")
    _checks.statutory(yen_top[0]["跳ぶ額"], 5_800, "いちばん大きい崖の額",
                      source="表から導いた値")
    ratio_top = biggest_cliff_by_ratio()
    if ratio_top["境目km"] != 15:
        raise _checks.TableError(
            f"率の1位が15kmではありません: {ratio_top['境目km']}km")
    if len([r for r in cliffs()
            if r["倍率"] is not None
            and abs(r["倍率"] - ratio_top["倍率"]) < 1e-12]) != 1:
        raise _checks.TableError("率の1位が単独ではありません")

    # 3. **主題その2。** 単価はのこぎりで、最大と最小はちょうど5.0倍
    ex = per_km_extremes()
    _checks.close(ex["最大の単価"], 2_100, "2kmの入口の単価", tol=1e-9)
    _checks.close(ex["比"], 5.0, "単価の最大と最小の比", tol=1e-3)
    if entry_prices_are_monotone():
        raise _checks.TableError(
            "入口の単価が単調に下がっています（のこぎりという主題が崩れます）")

    # 4. **主題その3。** 非課税でも保険料は増え、0円の行と率を超える行が両方ある
    p = pension_increase(BASE_MONTHLY)
    _checks.rounding(p["標準報酬月額(後)"], 340_000,
                     "報酬月額30万円に31,600円を足したときの標準報酬月額")
    _checks.rounding(p["増える年額"], 43_920, "増える厚生年金の本人負担（年）")
    _checks.greater(p["手当に対する割合"], shahoken.HALF,
                    "増える割合が保険料率9.15パーセントを超えていない")
    if not pension_over_rate_rows():
        raise _checks.TableError("保険料率を超える報酬月額が1件もありません")
    # 31,600円は等級の幅（20,000円）より大きいので、**どこでも必ずまたぐ**
    if not always_crosses(TOP_ALLOWANCE):
        raise _checks.TableError(
            f"31,600円が等級の幅を超えていません: 幅の最大 {max(grade_widths()):,}円")
    if pension_zero_rows(TOP_ALLOWANCE):
        raise _checks.TableError(
            "31,600円で保険料が増えない報酬月額があります（必ずまたぐはず）")
    # 4,200円は幅より小さいので、またぐ人とまたがない人に分かれる
    # （**1,000円刻みで見ること。**10,000円刻みでは境目が全部またがない側に
    #   そろってしまい、「誰もまたがない」という嘘の表になります）
    if always_crosses(SMALL_ALLOWANCE):
        raise _checks.TableError("4,200円が等級の幅を超えています")
    small_all = pension_grid(SMALL_ALLOWANCE, step=1_000)
    small_zero = pension_zero_rows(SMALL_ALLOWANCE, step=1_000)
    if not small_zero or len(small_zero) == len(small_all):
        raise _checks.TableError(
            f"4,200円でまたぐ人とまたがない人に分かれていません: "
            f"0円が {len(small_zero)}件 / {len(small_all)}件")

    # 5. **主題その4。** 手段の差は距離を見ずに決まる
    gap = mode_gap()
    _checks.rounding(gap["月の差"], 118_400, "交通機関とマイカーの上限の差")
    _checks.close(gap["倍率"], KOTSU_CAP / TOP_ALLOWANCE, "上限の倍率", tol=1e-12)
    _checks.greater(gap["倍率"], 4.0, "上限の倍率が4倍を超えていない")

    # 6. **主題その5。** 実費に届かないのは3か所だけ
    wins = short_windows()
    if len(wins) != 3:
        raise _checks.TableError(
            f"自腹になる範囲が3か所ではありません: {len(wins)}か所")
    _checks.close(break_even_km(4_200), 9.0, "4,200円とガソリン代が並ぶ距離",
                  tol=1e-9)
    _checks.close(break_even_km(TOP_ALLOWANCE), 67.714285, "31,600円で並ぶ距離",
                  tol=1e-4)
    # 10.0km から 67.7km のあいだは、どこを取っても限度額が実費を上回る
    for km in (10.0, 15, 25, 35, 45, 55, 67.0):
        if coverage(km)["まかなう割合"] <= 1.0:
            raise _checks.TableError(
                f"{km}km で限度額が実費を下回りました")

    # 7. **主題その6。** 55km以上は距離という軸そのものが消える
    tops = flat_top_grid()
    if len({r["限度額"] for r in tops}) != 1:
        raise _checks.TableError("55km以上で限度額が動いています")
    _checks.decreases_with(lambda km: coverage(km)["まかなう割合"],
                           [55, 100, 200],
                           "距離が伸びたのにまかなう割合が減っていない")
    _checks.unique_by(cliffs(), lambda r: r["境目km"], "境目の表")
    _checks.assumption_values(ASSUMPTIONS, name="tsukin")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 距離の崖は、額の1位が2つ同点。率で聞くと答えが変わる ===")
    for row in cliffs():
        r = f"{row['倍率']:.2f}倍" if row["倍率"] else "0円から"
        print(f"  片道 {row['境目km']:>4.0f}km  "
              f"{row['手前の限度額']:>7,}円 → {row['境目の限度額']:>7,}円  "
              f"跳び {row['跳ぶ額']:>+7,}円（年 {row['年で跳ぶ額']:>+8,}円・{r}）")
    top = biggest_cliffs_by_yen()
    names = "・".join(f"{r['境目km']:.0f}km" for r in top)
    print(f"  → 額の1位: {names} が "
          f"{top[0]['跳ぶ額']:,}円で**同点**（1つを名指すと嘘になる）")
    print(f"  → 率の1位: {biggest_cliff_by_ratio()['境目km']:.0f}km の "
          f"{biggest_cliff_by_ratio()['倍率']:.2f}倍（こちらは単独）")

    print("\n=== 1kmあたりの単価はのこぎり。最大と最小はちょうど5.0倍 ===")
    for row in per_km_grid():
        out = (f"出口 {row['出口km']:>7.3f}km {row['出口の単価']:>7.1f}円/km"
               if row["出口の単価"] else "出口 なし（上限のない帯）")
        print(f"  入口 {row['帯の入口km']:>4.0f}km  限度 {row['限度額']:>7,}円  "
              f"入口 {row['入口の単価']:>7.1f}円/km   {out}")
    ex = per_km_extremes()
    print(f"  → 最大 {ex['最大の単価']:,.1f}円/km（{ex['最大の距離']:.0f}km）／"
          f"最小 {ex['最小の単価']:,.1f}円/km（{ex['最小の距離']:.3f}km）＝ "
          f"**{ex['比']:.2f}倍**")
    print(f"  → 入口の単価は単調に下がるか: {entry_prices_are_monotone()}")

    print("\n=== 非課税でも厚生年金は引かれる。31,600円は必ず等級をまたぐ ===")
    for row in pension_grid():
        mark = "  ← 0円" if row["増える年額"] == 0 else (
            "  ← 9.15%超" if row["手当に対する割合"] > shahoken.HALF else "")
        print(f"  報酬月額 {row['報酬月額']:>8,}円  "
              f"標準報酬 {row['標準報酬月額(前)']:>8,} → {row['標準報酬月額(後)']:>8,}円  "
              f"保険料 年 {row['増える年額']:>+8,}円"
              f"（手当の {row['手当に対する割合']:>6.2%}）{mark}")
    print(f"  → 等級の幅は最大 {max(grade_widths()):,}円。"
          f"31,600円はこれを超えるので**またがない人はいません**"
          f"（0円 {len(pension_zero_rows(TOP_ALLOWANCE))}件）")
    print(f"  → 率9.15%を超える報酬月額: {len(pension_over_rate_rows())}件 / "
          f"{len(pension_grid())}件")
    small = pension_grid(SMALL_ALLOWANCE, step=1_000)
    print(f"  → 2km帯の 4,200円 は幅より小さいので分かれる（1,000円刻み）: "
          f"0円 {len(pension_zero_rows(SMALL_ALLOWANCE, 1_000))}件 / {len(small)}件")

    print("\n=== 同じ距離でも、電車とマイカーで上限が4.75倍ちがう ===")
    g = mode_gap()
    print(f"  交通機関 {g['交通機関の上限']:,}円 ／ マイカー {g['マイカーの上限']:,}円  "
          f"→ **{g['倍率']:.2f}倍**")
    print(f"  月の差 {g['月の差']:,}円 ＝ 年 {g['年の差']:,}円")
    print(f"  併用すると、定期券に回せる非課税枠は "
          f"{g['併用したとき定期券に回せる額']:,}円")

    print("\n=== 非課税枠が実費に届かないのは、2km未満と9km台と67.7km以上だけ ===")
    for row in short_windows():
        end = f"{row['自腹の終わり']}km" if row["自腹の終わり"] else "以降ずっと"
        print(f"  限度 {row['限度額']:>7,}円  "
              f"自腹 {row['自腹の始まり']:.2f}km 〜 {end}")
    for km in (1, 5, 9.5, 10, 30, 60, 70):
        c = coverage(km)
        print(f"  片道 {km:>5}km  限度 {c['限度額']:>7,}円  "
              f"実費 {c['実費']:>9,.0f}円  まかなう割合 {c['まかなう割合']:>7.1%}")

    print("\n=== 55km以上は頭打ち。距離が2倍でも1円も増えない ===")
    for row in flat_top_grid():
        print(f"  片道 {row['片道km']:>6}km  限度 {row['限度額']:>7,}円  "
              f"実費 {row['実費']:>9,.0f}円  "
              f"まかなう割合 {row['まかなう割合']:>7.1%}")
