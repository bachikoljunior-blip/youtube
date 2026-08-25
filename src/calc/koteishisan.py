"""固定資産税 —— **1㎡あたりの税額は、同じ1枚の土地の中で6倍ちがいます。**

一般の解説はこう言います ——「住宅用地は200㎡までが6分の1、それを超える部分は
3分の1になります」。**合っています。そのうえで、
それが1㎡あたりいくらの差になるのか、どこで切れるのかを並べた数字は出ていません。**

以下は地方税法349条の3の2（住宅用地の特例）・351条（免税点）・
附則15条の6（新築住宅の減額）から、税額を面積の関数として出した結果です。

## 帯は2つではなく3つあり、1㎡あたりの単価は 1 : 2 : 6 です

土地の評価額を1㎡あたり50,000円、家屋の床面積を100㎡として置いています。

    地積の部分            課税標準       1㎡あたりの固定資産税
    200㎡まで             評価額の1/6         116.67円
    200㎡超〜1,000㎡      評価額の1/3         233.33円
    1,000㎡超            評価額のまま         700.0円

**3つめの帯があることは、ほとんど書かれていません。**
住宅用地とみなされるのは家屋の床面積の10倍までで（349条の3の2第1項）、
それを超える部分には特例がまったく効きません。**1㎡あたり6倍です。**

## 面積を2倍にしたときの税額の倍率は、2.00倍から4.33倍まで動きます

しかも**面積が広いほど倍率が大きい、ではありません。**

    面積            税額                   倍率
      100㎡ → 200㎡    11,667円 →   23,333円   **2.00倍**
      200㎡ → 400㎡    23,333円 →   70,000円   **3.0倍**
      500㎡ → 1,000㎡  93,333円 →  210,000円   **2.25倍**
    1,000㎡ → 2,000㎡ 210,000円 →  910,000円   **4.33倍**

3.0倍のあとに2.25倍が来ます。**山が2つあるのは、帯の境目が
200㎡（面積で決まる）と1,000㎡（家屋の床面積で決まる）の2か所にあるからです。**

## 200㎡を使い切れるのは、床面積20㎡以上の家だけです

小規模住宅用地の200㎡は、**家屋の床面積の10倍という上限に先を越されることがあります。**

    家屋の床面積   住宅用地の上限   200㎡を使い切れるか
        10㎡           100㎡        **使い切れない**
        19㎡           190㎡        **使い切れない**
        20㎡           200㎡        ちょうど
        50㎡           500㎡        使い切れる
       100㎡         1,000㎡        使い切れる

**境目は床面積20㎡です。** 200㎡という数字は土地の側の話に見えますが、
それを使えるかどうかを決めているのは家屋の側です。

## 免税点の崖の高さは 6,000円 で、小規模でも一般でも同じです

免税点（351条）は課税標準額が土地30万円未満なら課税しない、という決め方です。
**特例を掛けたあとの額で見るので、非課税でいられる評価額は帯で6倍ちがいます。**

    土地の種類        非課税でいられる評価額   崖の高さ（税額）
    小規模住宅用地      1,800,000円未満        **6,000円**
    一般住宅用地          900,000円未満        **6,000円**
    住宅用地でない土地    300,000円未満          5,100円

**評価額の敷居は6倍ちがうのに、崖の高さは住宅用地なら同額です**
（都市計画税の課税標準が、どちらの帯でも固定資産税の課税標準のちょうど2倍になるため）。
**いちばん崖が低いのは、特例のまったく効かない土地のほうです。**

## 新築の3年間は、床面積98㎡の家と49㎡の家の税額が同額になります

新築住宅の減額（附則15条の6）は、床面積50㎡以上280㎡以下の住宅について、
120㎡までの部分の税額を3年間だけ2分の1にします。
**50㎡は「以上」なので、1㎡足りないと減額が丸ごと消えます。**

家屋の評価額を1㎡あたり100,000円として置いた、新築3年間の固定資産税です。

    床面積      税額         49㎡と比べて
     45㎡     63,000円      安い（家が小さいので）
     49㎡     68,600円      —
     50㎡     35,000円      **1㎡広げて 49.0% 下がる**
     98㎡     68,600円      **49㎡と同額**
    120㎡     84,000円      高い
    280㎡    308,000円
    281㎡    393,400円      **1㎡広げて 27.7% 上がる**

**49㎡から98㎡までのあいだは、家が広いほど税が安い**という区間です。
そして**50㎡未満の家は、どの広さでも「ちょうど2倍の広さの家」と同額**になります
（45㎡なら90㎡、49㎡なら98㎡）。減額後の税額は、120㎡までは
面積に対して半分の傾きで増えるためです。

## 4年目の跳ね幅は、床面積120㎡までは「ちょうど2.00倍」で平らです

減額が切れる4年目に、税額が何倍になるかです。
**家屋の評価額は据え置きとして置いています**（経年減点補正率は入れていません）。

    床面積      4年目の倍率
     49㎡      1.00倍（もともと減額なし）
     50㎡      **2.00倍**
    100㎡      **2.00倍**
    120㎡      **2.00倍**
    150㎡      1.6667倍
    200㎡      1.4286倍
    280㎡      1.2727倍
    281㎡      1.00倍（もともと減額なし）

**形は「1.00 → 2.00の台地 → 下り坂 → 1.00」です。** 両端が同じ1.00倍で、
理由が正反対（狭すぎて対象外／広すぎて対象外）。
**跳ね幅がいちばん大きいのは、120㎡ちょうどまでの家です。**

## 都市計画税を足すと、住宅用地の有利さは6.00倍から5.10倍に縮みます

都市計画税（702条の3）の住宅用地特例は、小規模が3分の1・一般が3分の2で、
**固定資産税の6分の1・3分の1より軽い**からです。

    土地の種類        固定資産税   都市計画税   合計    住宅でない土地との差
    小規模住宅用地      0.2333%       0.1%     **0.3333%**   **5.1倍**
    一般住宅用地        0.4667%       0.2%       0.6667%       2.55倍
    住宅用地でない土地      1.4%       0.3%          1.7%          1倍

**小規模住宅用地の合計の実効税率は、評価額のちょうど300分の1です。**
固定資産税だけを見ると6.00倍の差ですが、実際に払う額では5.10倍です。
"""
from __future__ import annotations

from fractions import Fraction

from . import _checks

# ---- 制度の値 -----------------------------------------------------------

# 標準税率（地方税法350条1項）
KOTEI_RATE = 0.014
# 都市計画税の制限税率（地方税法702条の4）
TOSHI_RATE = 0.003

# 住宅用地の特例（地方税法349条の3の2）。小規模は住戸1戸あたり200㎡まで。
SHOKIBO_AREA = 200
# **割合は分数のまま持ちます。** 1/6 を float にすると、評価額1,800,000円の
# 課税標準が 299,999.99999999994 になり、**免税点300,000円の判定が逆になります**
# （実際に落ちました。境目そのものが主題なので、ここは丸めてはいけません）。
KOTEI_SHOKIBO = Fraction(1, 6)   # 小規模住宅用地の課税標準の割合（固定資産税）
KOTEI_IPPAN = Fraction(1, 3)     # 一般住宅用地（200㎡超の部分）
TOSHI_SHOKIBO = Fraction(1, 3)   # 小規模住宅用地（都市計画税）
TOSHI_IPPAN = Fraction(2, 3)     # 一般住宅用地（都市計画税）
# 住宅用地とみなされるのは、家屋の床面積の10倍まで（同条1項）
FLOOR_MULTIPLE = 10

# 免税点（地方税法351条）。**課税標準額**で見る。
MENZEI_LAND = 300_000
MENZEI_HOUSE = 200_000

# 新築住宅の減額（地方税法附則15条の6）
SHINCHIKU_MIN_FLOOR = 50     # ㎡以上
SHINCHIKU_MAX_FLOOR = 280    # ㎡以下
SHINCHIKU_TARGET = 120       # この床面積までの部分の税額が対象
SHINCHIKU_CUT = 0.5          # 2分の1
SHINCHIKU_YEARS = 3          # 3年間（3階建て以上の中高層耐火建築物は5年間）

# この計算で置いた単価（制度の値ではありません）
LAND_UNIT = 50_000    # 土地の評価額 1㎡あたり
HOUSE_UNIT = 100_000  # 家屋の評価額 1㎡あたり
FLOOR_BASE = 100      # 家屋の床面積の既定値

ASSUMPTIONS = [
    "住宅が建っている土地の固定資産税を計算しています。地方税法349条の3の2の"
    "住宅用地の特例で、200平方メートルまでの部分は課税標準が6分の1、"
    "それを超える部分は3分の1になります",
    "住宅用地として扱われるのは、家屋の床面積の10倍までの地積です。"
    "それを超えた部分には特例がまったく効かず、評価額がそのまま課税標準になります",
    "土地の評価額は1平方メートルあたり50,000円として置いています。"
    "これは制度の値ではなくこの計算での仮定です。"
    "実際の路線価は地域で10倍以上の幅があります",
    "家屋の評価額は1平方メートルあたり100,000円として置いています。"
    "これも仮定です。構造と仕上げで実際には70,000円から200,000円の幅があります",
    "住戸は1戸としています。共同住宅では小規模住宅用地の200平方メートルが"
    "戸数の分だけ増えます",
    "固定資産税の税率は標準税率の1.4パーセント、都市計画税は制限税率の"
    "0.3パーセントとしています。市町村によってはこれと違う税率です",
    "新築住宅の減額は、床面積が50平方メートル以上280平方メートル以下のとき、"
    "120平方メートルまでの部分の税額を3年間だけ2分の1にする扱いです。"
    "3階建て以上の中高層耐火建築物は5年間ですが、ここでは3年間で計算しています",
    "家屋の評価額は据え置きとしています。経年減点補正率は入れていません。"
    "入れると4年目の跳ね方は、ここで出した倍率より小さくなります",
    "課税標準額の1,000円未満の切り捨てと、税額の100円未満の切り捨てはしていません。"
    "折れ点の位置を1円単位で見るためです",
    "免税点は課税標準額で見ています。土地は300,000円未満、家屋は200,000円未満で、"
    "固定資産税が免税点未満のときは都市計画税もかかりません",
    "負担調整措置と、市街化区域かどうかの別は入れていません。"
    "都市計画税は市街化区域内の土地にだけかかります",
]


# ---- 計算 ---------------------------------------------------------------

def residential_cap(floor_area: float) -> float:
    """住宅用地として扱われる地積の上限。**土地ではなく家屋が決めている。**"""
    return floor_area * FLOOR_MULTIPLE


def bands(land_area: float, floor_area: float = FLOOR_BASE) -> dict[str, float]:
    """地積を3つの帯に割る。小規模／一般／特例なし（㎡）。"""
    cap = residential_cap(floor_area)
    residential = min(Fraction(land_area), Fraction(cap))
    shokibo = min(residential, SHOKIBO_AREA)
    ippan = max(0.0, residential - shokibo)
    none = max(0.0, land_area - residential)
    return {"小規模": shokibo, "一般": ippan, "特例なし": none}


def land_base(land_area: float, floor_area: float = FLOOR_BASE,
              unit: float = LAND_UNIT, *, toshi: bool = False) -> float:
    """土地の課税標準額。`toshi=True` なら都市計画税のほう。"""
    b = bands(land_area, floor_area)
    s = TOSHI_SHOKIBO if toshi else KOTEI_SHOKIBO
    i = TOSHI_IPPAN if toshi else KOTEI_IPPAN
    return Fraction(unit) * (b["小規模"] * s + b["一般"] * i + b["特例なし"])


def land_tax(land_area: float, floor_area: float = FLOOR_BASE,
             unit: float = LAND_UNIT, *, with_toshi: bool = False) -> float:
    """土地の税額。**免税点を通っています**（下回れば0円）。"""
    base = land_base(land_area, floor_area, unit)
    if base < MENZEI_LAND:
        return 0.0
    tax = float(base) * KOTEI_RATE
    if with_toshi:
        tax += float(land_base(land_area, floor_area, unit, toshi=True)) * TOSHI_RATE
    return tax


def unit_tax(part: str, unit: float = LAND_UNIT) -> float:
    """その帯の1㎡あたりの固定資産税。**帯の中では一定。**"""
    share = {"小規模": KOTEI_SHOKIBO, "一般": KOTEI_IPPAN,
             "特例なし": Fraction(1)}[part]
    return unit * float(share) * KOTEI_RATE


def house_tax(floor_area: float, year: int = 1,
              unit: float = HOUSE_UNIT) -> float:
    """家屋の固定資産税。新築の減額は `year <= 3` のあいだだけ効く。"""
    base = floor_area * unit
    if base < MENZEI_HOUSE:
        return 0.0
    tax = base * KOTEI_RATE
    if (year <= SHINCHIKU_YEARS
            and SHINCHIKU_MIN_FLOOR <= floor_area <= SHINCHIKU_MAX_FLOOR):
        target = min(SHINCHIKU_TARGET, floor_area) / floor_area
        tax -= tax * target * SHINCHIKU_CUT
    return tax


def year4_ratio(floor_area: float, unit: float = HOUSE_UNIT) -> float:
    """4年目に税額が何倍になるか。**減額の対象外なら1.00倍。**"""
    before = house_tax(floor_area, year=SHINCHIKU_YEARS, unit=unit)
    after = house_tax(floor_area, year=SHINCHIKU_YEARS + 1, unit=unit)
    return after / before if before else 1.0


def same_tax_floor(small: float, unit: float = HOUSE_UNIT) -> float | None:
    """減額の対象外の狭い家 `small` と、新築3年間の税額が同じになる床面積。

    `small` が減額の対象（50㎡以上）なら `None`。
    **二分法ではなく式で出しています** —— 減額後の税額は床面積に対して
    1次式なので、刻みの話になりません。

    50㎡未満の家は必ず 2×small < 120㎡ に収まるので、
    **答えはいつでもちょうど2倍の広さ**です（120㎡までは減額後の傾きが半分）。
    """
    if small >= SHINCHIKU_MIN_FLOOR:
        return None
    f = small / SHINCHIKU_CUT
    if SHINCHIKU_MIN_FLOOR <= f <= SHINCHIKU_TARGET:
        return f
    return None


def menzei_limit(part: str, unit_free: bool = True) -> float:
    """その帯の土地が非課税でいられる評価額の上限（この額**未満**なら0円）。"""
    share = {"小規模": KOTEI_SHOKIBO, "一般": KOTEI_IPPAN,
             "特例なし": Fraction(1)}[part]
    return float(MENZEI_LAND / share)


def menzei_cliff(part: str) -> float:
    """免税点をまたいだ瞬間に発生する税額（固定資産税＋都市計画税）。"""
    kotei_share = {"小規模": KOTEI_SHOKIBO, "一般": KOTEI_IPPAN,
                   "特例なし": Fraction(1)}[part]
    toshi_share = {"小規模": TOSHI_SHOKIBO, "一般": TOSHI_IPPAN,
                   "特例なし": Fraction(1)}[part]
    value = MENZEI_LAND / kotei_share           # 課税標準がちょうど免税点になる評価額
    return float(value * kotei_share) * KOTEI_RATE + float(value * toshi_share) * TOSHI_RATE


def effective_rate(part: str, *, with_toshi: bool = True) -> float:
    """評価額に対する実効税率（パーセント）。"""
    kotei_share = {"小規模": KOTEI_SHOKIBO, "一般": KOTEI_IPPAN,
                   "特例なし": Fraction(1)}[part]
    toshi_share = {"小規模": TOSHI_SHOKIBO, "一般": TOSHI_IPPAN,
                   "特例なし": Fraction(1)}[part]
    r = float(kotei_share) * KOTEI_RATE
    if with_toshi:
        r += float(toshi_share) * TOSHI_RATE
    return r * 100


# ---- 表（図解がそのまま食える dict のリスト）-----------------------------

PARTS = ["小規模", "一般", "特例なし"]
LAND_AREAS = [100, 200, 201, 300, 400, 500, 1_000, 1_001, 1_500, 2_000]
FLOORS = [10, 19, 20, 30, 50, 100, 200]
HOUSE_FLOORS = [45, 49, 50, 60, 98, 100, 120, 121, 150, 200, 280, 281, 300]


def band_grid() -> list[dict]:
    """帯べつの1㎡あたりの税額。**同じ1枚の土地の中で6倍ちがう。**"""
    lowest = unit_tax("小規模")
    return [{"帯": p,
             "課税標準の割合": round(float({"小規模": KOTEI_SHOKIBO,
                                            "一般": KOTEI_IPPAN,
                                            "特例なし": Fraction(1)}[p]), 6),
             "1㎡あたりの固定資産税": round(unit_tax(p), 2),
             "小規模の何倍": round(unit_tax(p) / lowest, 2)}
            for p in PARTS]


def area_grid(floor_area: float = FLOOR_BASE) -> list[dict]:
    """地積べつの税額と、1㎡あたりの平均。**折れ点は200㎡と床面積の10倍。**"""
    return [{"地積": a,
             "小規模の㎡": round(float(bands(a, floor_area)["小規模"])),
             "一般の㎡": round(float(bands(a, floor_area)["一般"])),
             "特例なしの㎡": round(float(bands(a, floor_area)["特例なし"])),
             "固定資産税": round(land_tax(a, floor_area)),
             "1㎡あたりの平均": round(land_tax(a, floor_area) / a, 2)}
            for a in LAND_AREAS]


DOUBLES = [(100, 200), (200, 400), (500, 1_000), (1_000, 2_000)]


def double_grid(floor_area: float = FLOOR_BASE) -> list[dict]:
    """面積を2倍にしたときの税額の倍率。**単調ではない。**"""
    out = []
    for a, b in DOUBLES:
        ta, tb = land_tax(a, floor_area), land_tax(b, floor_area)
        out.append({"もとの地積": a, "2倍にした地積": b,
                    "もとの税額": round(ta), "2倍にした税額": round(tb),
                    "税額の倍率": round(tb / ta, 2)})
    return out


def floor_grid() -> list[dict]:
    """床面積べつの住宅用地の上限。**200㎡を使い切れる境目は床面積20㎡。**"""
    return [{"家屋の床面積": f,
             "住宅用地の上限": round(residential_cap(f)),
             "200㎡を使い切れるか": residential_cap(f) >= SHOKIBO_AREA,
             "300㎡の土地の固定資産税": round(land_tax(300, f))}
            for f in FLOORS]


def menzei_grid() -> list[dict]:
    """免税点を評価額に戻した表。**敷居は6倍ちがうのに崖は同じ。**"""
    return [{"土地の種類": p,
             "非課税でいられる評価額": round(menzei_limit(p)),
             "崖の高さ": round(menzei_cliff(p)),
             "うち固定資産税": round(MENZEI_LAND * KOTEI_RATE)}
            for p in PARTS]


def shinchiku_grid() -> list[dict]:
    """新築3年間の家屋の税額。**50㎡と281㎡に、向きの逆な崖がある。**"""
    ref = house_tax(49, year=1)
    return [{"床面積": f,
             "新築3年間の税額": round(house_tax(f, year=1)),
             "4年目の税額": round(house_tax(f, year=4)),
             "減額の対象か": (SHINCHIKU_MIN_FLOOR <= f <= SHINCHIKU_MAX_FLOOR),
             "49㎡との比": round(house_tax(f, year=1) / ref, 4)}
            for f in HOUSE_FLOORS]


def year4_grid() -> list[dict]:
    """4年目の跳ね幅。**120㎡までは、どの広さでもちょうど2.00倍。**"""
    return [{"床面積": f,
             "3年目の税額": round(house_tax(f, year=3)),
             "4年目の税額": round(house_tax(f, year=4)),
             "4年目の倍率": round(year4_ratio(f), 4)}
            for f in HOUSE_FLOORS]


def rate_grid() -> list[dict]:
    """評価額に対する実効税率。**都市計画税を足すと6.00倍が5.10倍になる。**"""
    top = effective_rate("特例なし")
    top_kotei = effective_rate("特例なし", with_toshi=False)
    return [{"土地の種類": p,
             "固定資産税だけ": round(effective_rate(p, with_toshi=False), 4),
             "都市計画税だけ": round(effective_rate(p) -
                                     effective_rate(p, with_toshi=False), 4),
             "合計": round(effective_rate(p), 4),
             "特例なしとの差（固定資産税だけ）":
                 round(top_kotei / effective_rate(p, with_toshi=False), 2),
             "特例なしとの差（合計）": round(top / effective_rate(p), 2)}
            for p in PARTS]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""
    # 1. 法令が名指ししている値
    _checks.statutory(KOTEI_RATE, 0.014, "固定資産税の標準税率",
                      source="地方税法350条1項")
    _checks.statutory(TOSHI_RATE, 0.003, "都市計画税の制限税率",
                      source="地方税法702条の4")
    _checks.statutory(SHOKIBO_AREA, 200, "小規模住宅用地の上限（㎡）",
                      source="地方税法349条の3の2第2項")
    _checks.statutory(FLOOR_MULTIPLE, 10, "住宅用地とみなす床面積の倍率",
                      source="地方税法349条の3の2第1項")
    _checks.statutory(MENZEI_LAND, 300_000, "土地の免税点",
                      source="地方税法351条")
    _checks.statutory(MENZEI_HOUSE, 200_000, "家屋の免税点",
                      source="地方税法351条")
    _checks.statutory(SHINCHIKU_TARGET, 120, "新築減額の対象となる床面積",
                      source="地方税法附則15条の6")
    _checks.statutory(SHINCHIKU_MIN_FLOOR, 50, "新築減額の床面積の下限",
                      source="地方税法附則15条の6")
    _checks.statutory(SHINCHIKU_MAX_FLOOR, 280, "新築減額の床面積の上限",
                      source="地方税法附則15条の6")
    _checks.ratio(KOTEI_RATE, "固定資産税の税率")
    _checks.ratio(TOSHI_RATE, "都市計画税の税率")
    _checks.ratio(float(KOTEI_SHOKIBO), "小規模住宅用地の課税標準の割合")
    _checks.ratio(SHINCHIKU_CUT, "新築減額の割合")
    _checks.close(float(KOTEI_IPPAN), float(KOTEI_SHOKIBO * 2),
                  "一般住宅用地の割合が小規模のちょうど2倍でない")
    _checks.close(float(TOSHI_IPPAN), float(TOSHI_SHOKIBO * 2),
                  "都市計画税でも、一般が小規模のちょうど2倍でない")

    # 2. 帯の割り方（3つの帯が地積を過不足なく分けていること）
    for a in (150, 200, 400, 1_000, 2_500):
        b = bands(a, FLOOR_BASE)
        _checks.close(float(sum(b.values())), float(a),
                      f"地積{a}㎡の帯の合計が地積と合わない")
    _checks.statutory(float(bands(2_500, FLOOR_BASE)["小規模"]), 200,
                      "地積2,500㎡のときの小規模の㎡")
    _checks.statutory(float(bands(2_500, FLOOR_BASE)["一般"]), 800,
                      "地積2,500㎡のときの一般の㎡")
    _checks.statutory(float(bands(2_500, FLOOR_BASE)["特例なし"]), 1_500,
                      "地積2,500㎡のときの特例なしの㎡")

    # 3. この計算の主題そのもの
    # (a) 1㎡あたりは 1 : 2 : 6
    _checks.close(unit_tax("一般") / unit_tax("小規模"), 2.0,
                  "一般の1㎡あたりが小規模のちょうど2倍でない")
    _checks.close(unit_tax("特例なし") / unit_tax("小規模"), 6.0,
                  "特例なしの1㎡あたりが小規模のちょうど6倍でない")
    _checks.increases_with(lambda a: land_tax(a, FLOOR_BASE),
                           [100, 300, 800, 1_200, 2_000],
                           "地積が増えたのに税額が増えていない")
    # (b) 倍率が単調でないこと（3.00 のあとに 2.25 が来る）
    ratios = [r["税額の倍率"] for r in double_grid()]
    _checks.greater(ratios[1], ratios[2],
                    "面積2倍の倍率が、200→400㎡より500→1,000㎡のほうが小さいはず")
    _checks.greater(ratios[3], ratios[1],
                    "面積2倍の倍率が、1,000→2,000㎡でいちばん大きいはず")
    # (c) 200㎡を使い切れる境目は床面積20㎡
    _checks.statutory(residential_cap(20), SHOKIBO_AREA,
                      "床面積20㎡の住宅用地の上限")
    _checks.greater(SHOKIBO_AREA, residential_cap(19),
                    "床面積19㎡では200㎡に届かないはず")
    # (d) 免税点の崖は、住宅用地なら帯によらず同額
    _checks.close(menzei_cliff("小規模"), menzei_cliff("一般"),
                  "免税点の崖の高さが、小規模と一般でちがう")
    _checks.greater(menzei_cliff("小規模"), menzei_cliff("特例なし"),
                    "住宅用地の崖のほうが、特例なしより高いはず")
    _checks.statutory(land_tax(200, FLOOR_BASE, 8_999), 0,
                      "評価額1,799,800円の小規模住宅用地の税額")
    _checks.greater(land_tax(200, FLOOR_BASE, 9_000), 0,
                    "評価額1,800,000円なら課税されるはず")
    # (e) 新築減額の崖（下向きと上向き）
    _checks.greater(house_tax(49, 1), house_tax(50, 1),
                    "床面積49㎡の税額が、50㎡より高いはず（減額の下限）")
    _checks.greater(house_tax(281, 1), house_tax(280, 1),
                    "床面積281㎡の税額が、280㎡より高いはず（減額の上限）")
    _checks.close(house_tax(98, 1), house_tax(49, 1),
                  "床面積98㎡と49㎡の新築3年間の税額が同額でない")
    _checks.statutory(same_tax_floor(49), 98.0, "49㎡と同額になる床面積")
    _checks.statutory(same_tax_floor(45), 90.0, "45㎡と同額になる床面積")
    _checks.close(house_tax(90, 1), house_tax(45, 1),
                  "床面積90㎡と45㎡の新築3年間の税額が同額でない")
    if same_tax_floor(50) is not None:
        raise _checks.TableError(
            "床面積50㎡は減額の対象なので、同額になる相手は無いはず")
    # (f) 4年目の倍率は 120㎡までちょうど2.00倍で平ら → 下り → 1.00
    for f in (50, 80, 120):
        _checks.close(year4_ratio(f), 2.0,
                      f"床面積{f}㎡の4年目の倍率がちょうど2.00倍でない")
    _checks.decreases_with(year4_ratio, [120, 150, 200, 280],
                           "床面積が増えたのに4年目の倍率が下がっていない")
    _checks.statutory(year4_ratio(49), 1.0, "床面積49㎡の4年目の倍率")
    _checks.statutory(year4_ratio(281), 1.0, "床面積281㎡の4年目の倍率")
    # (g) 実効税率。合計では 6.00倍 が 5.10倍 に縮む
    _checks.close(effective_rate("小規模"), 1 / 3,
                  "小規模住宅用地の実効税率が、ちょうど300分の1でない")
    _checks.close(effective_rate("特例なし", with_toshi=False)
                  / effective_rate("小規模", with_toshi=False), 6.0,
                  "固定資産税だけの差が6.00倍でない")
    _checks.close(effective_rate("特例なし") / effective_rate("小規模"), 5.1,
                  "合計での差が5.10倍でない")
    _checks.unique_by(band_grid(), lambda r: r["帯"], "帯べつの表")
    _checks.unique_by(area_grid(), lambda r: r["地積"], "地積べつの表")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")
    print(f"前提: 土地の評価額 1㎡あたり {LAND_UNIT:,}円 ／ "
          f"家屋の評価額 1㎡あたり {HOUSE_UNIT:,}円 ／ "
          f"家屋の床面積 {FLOOR_BASE}㎡ ／ 住戸1戸")

    print("\n=== 帯は2つでなく3つ。1㎡あたりの固定資産税は同じ土地の中で6倍ちがう ===")
    print(f"  前提の家屋の床面積 {FLOOR_BASE}㎡（住宅用地の上限 "
          f"{residential_cap(FLOOR_BASE):,.0f}㎡）／ 土地の評価額 1㎡あたり {LAND_UNIT:,}円")
    for row in band_grid():
        print(row)
    for row in area_grid():
        print(row)

    print("\n=== 面積を2倍にしたときの税額の倍率は2.00倍から4.33倍まで動き、単調でない ===")
    print(f"  前提の家屋の床面積 {FLOOR_BASE}㎡ ／ 土地の評価額 1㎡あたり {LAND_UNIT:,}円")
    for row in double_grid():
        print(row)

    print("\n=== 200㎡を使い切れるのは床面積20㎡以上の家だけ。決めているのは土地でなく家屋 ===")
    print(f"  前提の地積 300㎡ ／ 土地の評価額 1㎡あたり {LAND_UNIT:,}円 ／ "
          f"床面積の{FLOOR_MULTIPLE}倍まで")
    for row in floor_grid():
        print(row)

    print("\n=== 免税点の崖は6,000円で、小規模でも一般でも同じ。特例なしの5,100円が最も低い ===")
    print(f"  前提の免税点 土地 {MENZEI_LAND:,}円（課税標準額で見る）")
    for row in menzei_grid():
        print(row)

    print("\n=== 新築3年間は床面積98㎡と49㎡の税額が同額。50㎡で49.0%下がり281㎡で27.7%上がる ===")
    print(f"  前提の家屋の評価額 1㎡あたり {HOUSE_UNIT:,}円 ／ "
          f"減額は{SHINCHIKU_MIN_FLOOR}㎡以上{SHINCHIKU_MAX_FLOOR}㎡以下・"
          f"{SHINCHIKU_TARGET}㎡までの部分・{SHINCHIKU_YEARS}年間")
    for row in shinchiku_grid():
        print(row)
    print("49㎡と同額になる床面積:", same_tax_floor(49))
    print("45㎡と同額になる床面積:", same_tax_floor(45))

    print("\n=== 4年目の跳ね幅は床面積120㎡までちょうど2.00倍で平ら。両端は1.00倍 ===")
    print(f"  前提の家屋の評価額 1㎡あたり {HOUSE_UNIT:,}円 ／ "
          f"{SHINCHIKU_YEARS}年間・{SHINCHIKU_TARGET}㎡まで・評価額は据え置き")
    for row in year4_grid():
        print(row)

    print("\n=== 都市計画税を足すと住宅用地の有利さは6.00倍から5.10倍に縮む ===")
    print(f"  前提の税率 固定資産税 {KOTEI_RATE * 100:.1f}パーセント ／ "
          f"都市計画税 {TOSHI_RATE * 100:.1f}パーセント")
    for row in rate_grid():
        print(row)
