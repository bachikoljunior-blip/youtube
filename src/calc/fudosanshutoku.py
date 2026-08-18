"""不動産取得税 —— **「1,200万円まで非課税」は、1,222万9,999円までの間違いです。**

一般の解説はここで止まります ——「新築住宅なら評価額から1,200万円を引けます。
税率は3パーセントです」。**控除額と税率を写すところで終わります。**

この計算が出すのは、その2つを組み合わせて初めて出る数字です。

## 0円で済むのは控除額までではありません。免税点のぶん、上に伸びます

不動産取得税には免税点があり、**控除を引いたあとの課税標準が23万円に満たなければ
課税されません**（建築に係る家屋）。控除と免税点は別の条文なので、両方効きます。

    評価額 12,000,000円   課税標準 0円         税額 0円   ← よく言われる控除額
    評価額 12,229,999円   課税標準 229,999円   税額 0円   ← **ここまで0円**
    評価額 12,230,000円   課税標準 230,000円   税額 **6,900円**

**1円で6,900円**が立ち上がります。認定長期優良住宅（控除1,300万円）でも、
0円で済む上限は 13,229,999円で、**余白は同じ229,999円、崖も同じ6,900円**です。
**控除額が100万円ちがうのに、崖の額も余白の幅も1円も違いません。**

## 床面積1平方メートルで360,000円。しかも崖は上と下の両方にあります

控除が使えるのは床面積50平方メートル以上240平方メートル以下の住宅だけで、
**外れると1円も引けません。**

    評価額 15,000,000円   240平方メートル 90,000円 → 241平方メートル 450,000円   **5.0倍**
    評価額 20,000,000円   240平方メートル 240,000円 → 241平方メートル 600,000円   2.5倍
    評価額 30,000,000円   240平方メートル 540,000円 → 241平方メートル 900,000円   1.67倍

**跳ぶ額は 360,000円で頭打ち**です（控除1,200万円×3パーセント）。
倍率で聞くと答えが変わり、**1位は評価額1,500万円の5.0倍**になります。

そして**同じ崖が49平方メートルにもあります**。評価額2,000万円の家は、
50平方メートルでも240平方メートルでも240,000円ですが、
**49平方メートルと241平方メートルはどちらも600,000円**です。

## 土地の税額を決めているのは、面積でも単価でもなく「はみ出した面積」

住宅用の土地は、**床面積の2倍（200平方メートルが上限）まで**の税額が控除で消えます。
つまり土地の税額は「土地面積 − 床面積の2倍」だけで決まります。

    床面積100平方メートル・土地200平方メートル
      1平方メートル単価     50,000円 → 税額 0円
      1平方メートル単価  1,000,000円 → 税額 **0円**（評価額2億円でも0円）

**単価をいくら上げても、0円で済む土地面積は200平方メートルから動きません。**
1平方メートル広げた瞬間に税額が立ち上がり、そこから先は
はみ出した面積に比例します（単価200,000円なら、250平方メートルで150,000円、
300平方メートルで300,000円、400平方メートルで600,000円）。

## 家を2.4倍広くしても、土地の税は1円も変わりません

控除の中の「床面積の2倍」には200平方メートルの上限があるので、
**床面積100平方メートルで頭打ち**です。

    床面積  50平方メートル   土地の控除 300,000円
    床面積 100平方メートル   土地の控除 600,000円   ← ここで頭打ち
    床面積 240平方メートル   土地の控除 600,000円

100平方メートルから240平方メートルまで、**140平方メートルぶんが全部同額**です。
一方で50平方メートルと100平方メートルの間では、**控除がちょうど2倍**変わります。

## 45,000円の下限に守られるのは、家が広い人ほど安い土地だけ

控除には45,000円の下限があります。**この下限が効くのは、床面積の2倍から出る額が
45,000円に届かない土地だけ**なので、敷居は床面積で動きます。

    床面積  50平方メートル   1平方メートル 30,000円以下
    床面積  90平方メートル   1平方メートル 16,667円以下
    床面積 100平方メートル   1平方メートル 15,000円以下   ← ここから動かない

**敷居の開きは2.0倍**（30,000円 対 15,000円）。家が広いほど、
下限に助けられるのは安い土地だけになります。

## 宅地の「2分の1」は、税額が半分になるという意味ではありません

課税標準が半分になると同時に、**控除の計算に使う1平方メートル単価も半分**になります。
だから多くの土地では税額もちょうど半分ですが、45,000円の下限が効く帯では違います。

    1平方メートル  30,000円   90,000円 → 45,000円    残る割合 0.5
    1平方メートル  12,000円   36,000円 →  9,000円    残る割合 **0.25**
    1平方メートル   8,000円   24,000円 →     0円     残る割合 **0**

**0.5は上限であって、下回ることはあっても上回りません。**
税額がまるごと消える単価の上限は、特例ありで **10,026円**、特例なしで 5,013円 ——
**特例は「半額にする制度」ではなく、消える境目を約2倍に動かす制度**です。

## 中古住宅は、建った時期で控除が12倍ちがいます

中古住宅の控除額は新築された時期で決まり、8段あります（100万円〜1,200万円）。
評価額1,500万円の家で税額を並べると:

    昭和29年7月〜昭和38年12月   控除 1,000,000円   税額 420,000円
    昭和60年7月〜平成元年3月    控除 4,500,000円   税額 315,000円
    平成元年4月〜平成9年3月     控除 10,000,000円  税額 150,000円
    平成9年4月以降              控除 12,000,000円  税額  90,000円

**段差は単調ではありません。** いちばん浅いのが昭和60年7月の 9,000円で、
**その次がいちばん深い165,000円**（平成元年4月）。上と下の差は330,000円です。
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値 ----------------------------------------------------------
RATE_JUTAKU = 0.03            # 住宅・住宅用土地（地方税法附則11条の2。令和9年3月31日まで）
RATE_HIJUTAKU = 0.04          # 住宅以外の家屋（同73条の15の標準税率）
SHINCHIKU_KOJO = 12_000_000   # 新築住宅の課税標準控除（73条の14第1項）
CHOKI_KOJO = 13_000_000       # 認定長期優良住宅（附則11条第10項）
TAKUCHI_HANGAKU = 0.5         # 宅地評価土地の課税標準（附則11条の5）
LAND_CREDIT_FLOOR = 45_000    # 土地の税額控除の下限（73条の24第1項一号）
LAND_AREA_CAP = 200           # 床面積の2倍の上限（同二号）
FLOOR_MIN = 50                # 床面積の下限（施行令37条の16）
FLOOR_MAX = 240               # 床面積の上限（同）
MENZEI_TOCHI = 100_000        # 免税点・土地（73条の15の2）
MENZEI_SHINCHIKU = 230_000    # 免税点・家屋のうち建築に係るもの
MENZEI_BAIBAI = 120_000       # 免税点・家屋のうちその他（売買など）

# 中古住宅の控除額は「新築された時期」で決まる（施行令37条の18）
CHUKO_KOJO: list[tuple[str, int]] = [
    ("昭和29年7月〜昭和38年12月", 1_000_000),
    ("昭和39年1月〜昭和47年12月", 1_500_000),
    ("昭和48年1月〜昭和50年12月", 2_300_000),
    ("昭和51年1月〜昭和56年6月", 3_500_000),
    ("昭和56年7月〜昭和60年6月", 4_200_000),
    ("昭和60年7月〜平成元年3月", 4_500_000),
    ("平成元年4月〜平成9年3月", 10_000_000),
    ("平成9年4月以降", 12_000_000),
]

ASSUMPTIONS = [
    "不動産取得税を計算しています。土地や家屋を買ったとき、建てたとき、"
    "もらったときに1回だけかかる都道府県の税です。毎年かかる固定資産税とは別の税です",
    "税額のもとになるのは買った値段ではなく、固定資産課税台帳に載っている評価額です。"
    "この計算では、評価額そのものを入力として置いています",
    "税率は住宅と土地が3パーセント、住宅以外の家屋が4パーセントとして計算しています。"
    "3パーセントは令和9年3月31日までに取得したものに適用される軽減後の率で、"
    "本来の標準税率は4パーセントです",
    "宅地として評価された土地は、課税標準が評価額の2分の1になるものとして計算しています。"
    "これも令和9年3月31日までの取得が対象です",
    "新築住宅は課税標準から1,200万円、認定長期優良住宅は1,300万円を引けるものとして"
    "計算しています。引けるのは床面積が50平方メートル以上240平方メートル以下の"
    "住宅だけで、この範囲を外れると1円も引けません",
    "貸家として建てる共同住宅は床面積の下限が40平方メートルになりますが、"
    "この計算では自分で住む住宅として、下限を50平方メートルに置いています",
    "住宅用の土地は、税額そのものからも引けるものとして計算しています。"
    "引ける額は45,000円か、土地1平方メートルあたりの価格に床面積の2倍"
    "（200平方メートルが上限）を掛けて3パーセントを掛けた額の、大きいほうです",
    "土地1平方メートルあたりの価格は、宅地の場合は2分の1にした後の額で計算しています",
    "免税点は土地が10万円、家屋のうち建てたものが1戸につき23万円、"
    "買ったものが1戸につき12万円として計算しています。"
    "控除を引いた後の課税標準がこの額に満たなければ、税額は0円になります",
    "課税標準は1,000円未満を、税額は100円未満を切り捨てて計算しています",
    "中古住宅の控除額は、その住宅が新築された時期で決まるものとして計算しています。"
    "平成9年4月以降の新築が1,200万円、昭和29年7月から昭和38年12月までの新築が"
    "100万円で、間に6段あります。昭和56年12月31日以前に新築された住宅は"
    "耐震基準に適合していることの証明が要りますが、この計算では"
    "適合しているものとして置いています",
    "登録免許税・司法書士の報酬・仲介手数料は入れていません。"
    "不動産取得税だけを見ています",
]


# ---- 端数処理 ----------------------------------------------------------
def _floor1000(x: float) -> int:
    return int(x) // 1000 * 1000


def _floor100(x: float) -> int:
    return int(x) // 100 * 100


# ---- 家屋 --------------------------------------------------------------
def kaoku_kojo(floor_area: float, *, choki: bool = False,
               chuko: str | None = None) -> int:
    """家屋の課税標準から引ける額。**床面積が範囲を外れると0円。**"""
    if not (FLOOR_MIN <= floor_area <= FLOOR_MAX):
        return 0
    if chuko is not None:
        for name, amount in CHUKO_KOJO:
            if name == chuko:
                return amount
        raise ValueError(f"新築時期の区分に無い: {chuko}")
    return CHOKI_KOJO if choki else SHINCHIKU_KOJO


def kaoku_tax(value: float, floor_area: float, *, choki: bool = False,
              chuko: str | None = None, jutaku: bool = True) -> int:
    """家屋の不動産取得税。**免税点と端数処理まで入れた実額。**"""
    if not jutaku:
        base = max(0.0, value)
        if base < MENZEI_SHINCHIKU:
            return 0
        return _floor100(_floor1000(base) * RATE_HIJUTAKU)
    base = max(0.0, value - kaoku_kojo(floor_area, choki=choki, chuko=chuko))
    menzei = MENZEI_BAIBAI if chuko is not None else MENZEI_SHINCHIKU
    if base < menzei:
        return 0
    return _floor100(_floor1000(base) * RATE_JUTAKU)


def kaoku_zero_limit(floor_area: float = 100, *, choki: bool = False,
                     chuko: str | None = None) -> int:
    """税額が0円で済む評価額の上限（**控除額そのものではありません**）。"""
    return kaoku_kojo(floor_area, choki=choki, chuko=chuko) + (
        (MENZEI_BAIBAI if chuko is not None else MENZEI_SHINCHIKU) - 1)


# ---- 土地 --------------------------------------------------------------
def tochi_credit(unit_price: float, floor_area: float) -> float:
    """住宅用土地の税額控除。**45,000円と、床面積から出る額の大きいほう。**

    `unit_price` は**2分の1にする前**の1平方メートルあたり評価額。
    """
    area = min(floor_area * 2, LAND_AREA_CAP)
    by_area = unit_price * TAKUCHI_HANGAKU * area * RATE_JUTAKU
    return max(float(LAND_CREDIT_FLOOR), by_area)


def tochi_tax(land_area: float, unit_price: float, floor_area: float) -> int:
    """住宅用土地の不動産取得税。**引ききれない分は0円で止まります。**"""
    value = land_area * unit_price
    base = value * TAKUCHI_HANGAKU
    if base < MENZEI_TOCHI:
        return 0
    before = _floor100(_floor1000(base) * RATE_JUTAKU)
    return max(0, _floor100(before - tochi_credit(unit_price, floor_area)))


def tochi_zero_area(floor_area: float) -> float:
    """土地の税額が0円で済む土地面積の上限（**単価によりません**）。"""
    return min(floor_area * 2, LAND_AREA_CAP)


def floor_credit_cap(floor_area: float) -> float:
    """床面積べつ「45,000円の下限が効く1平方メートル単価の上限」。"""
    area = min(floor_area * 2, LAND_AREA_CAP)
    return LAND_CREDIT_FLOOR / (TAKUCHI_HANGAKU * area * RATE_JUTAKU)


def tochi_tax_raw(land_area: float, unit_price: float, floor_area: float,
                  *, hangaku: bool = True) -> int:
    """2分の1の特例を外したときの土地の税額（**節6の比較用**）。"""
    half = TAKUCHI_HANGAKU if hangaku else 1.0
    base = land_area * unit_price * half
    if base < MENZEI_TOCHI:
        return 0
    before = _floor100(_floor1000(base) * RATE_JUTAKU)
    area = min(floor_area * 2, LAND_AREA_CAP)
    credit = max(float(LAND_CREDIT_FLOOR), unit_price * half * area * RATE_JUTAKU)
    return max(0, _floor100(before - credit))


# ---- 節1: 「1,200万円まで非課税」ではない ------------------------------
def kaoku_zero_grid() -> list[dict]:
    """新築住宅の評価額を1円ずつまたいで、税額が立ち上がる点を出す。"""
    rows = []
    for label, kojo, choki in (("一般の新築住宅", SHINCHIKU_KOJO, False),
                               ("認定長期優良住宅", CHOKI_KOJO, True)):
        limit = kojo + MENZEI_SHINCHIKU - 1
        for value, note in ((kojo, "よく言われる控除額そのもの"),
                            (limit, "**ここまで0円**"),
                            (limit + 1, "**1円こえた額**")):
            rows.append({
                "住宅": label,
                "評価額": value,
                "課税標準": max(0, value - kojo),
                "税額": kaoku_tax(value, 100, choki=choki),
                "註": note,
            })
    return rows


def kaoku_zero_cliff() -> list[dict]:
    """免税点の1円で跳ぶ額。**控除額の1円上ではなく、その23万円上にあります。**"""
    rows = []
    for label, kojo, choki in (("一般の新築住宅", SHINCHIKU_KOJO, False),
                               ("認定長期優良住宅", CHOKI_KOJO, True)):
        limit = kojo + MENZEI_SHINCHIKU - 1
        rows.append({
            "住宅": label,
            "0円で済む上限": limit,
            "1円こえた税額": kaoku_tax(limit + 1, 100, choki=choki),
            "控除額との差": limit - kojo,
        })
    return rows


# ---- 節2: 床面積1平方メートルの崖 --------------------------------------
def floor_cliff_grid(values: list[int] | None = None) -> list[dict]:
    """床面積が要件を外れる1平方メートルで、税額がいくら跳ぶか。"""
    values = values or [8_000_000, 12_000_000, 15_000_000, 20_000_000, 30_000_000]
    rows = []
    for value in values:
        inside = kaoku_tax(value, FLOOR_MAX)
        outside = kaoku_tax(value, FLOOR_MAX + 1)
        rows.append({
            "評価額": value,
            f"{FLOOR_MAX}平方メートル": inside,
            f"{FLOOR_MAX + 1}平方メートル": outside,
            "跳ぶ額": outside - inside,
            "倍率": None if inside == 0 else round(outside / inside, 2),
        })
    return rows


def floor_cliff_max() -> dict:
    """崖の頭打ち。**控除額そのものに税率を掛けた額で止まります。**"""
    top = max(floor_cliff_grid([10_000_000, 12_000_000, 20_000_000,
                                50_000_000, 100_000_000]),
              key=lambda r: r["跳ぶ額"])
    return {"跳ぶ額の上限": top["跳ぶ額"],
            "控除額×税率": _floor100(SHINCHIKU_KOJO * RATE_JUTAKU),
            "この額で頭打ちになる評価額": SHINCHIKU_KOJO + MENZEI_SHINCHIKU}


def floor_both_ends() -> list[dict]:
    """崖は上だけではありません。**49平方メートルにも同じ額の崖があります。**"""
    value = 20_000_000
    return [
        {"床面積": FLOOR_MIN - 1, "税額": kaoku_tax(value, FLOOR_MIN - 1)},
        {"床面積": FLOOR_MIN, "税額": kaoku_tax(value, FLOOR_MIN)},
        {"床面積": FLOOR_MAX, "税額": kaoku_tax(value, FLOOR_MAX)},
        {"床面積": FLOOR_MAX + 1, "税額": kaoku_tax(value, FLOOR_MAX + 1)},
    ]


# ---- 節3: 土地の税額は「はみ出した面積」だけで決まる --------------------
def tochi_area_grid(floor_area: float = 100,
                    unit_prices: list[int] | None = None) -> list[dict]:
    """単価を変えても、税額が0円で済む土地面積は動きません。"""
    unit_prices = unit_prices or [50_000, 100_000, 200_000, 500_000, 1_000_000]
    rows = []
    for unit in unit_prices:
        limit = tochi_zero_area(floor_area)
        rows.append({
            "1平方メートル単価": unit,
            "0円で済む土地面積": limit,
            f"{limit:.0f}平方メートルの税額": tochi_tax(limit, unit, floor_area),
            "1平方メートル広い土地の税額": tochi_tax(limit + 1, unit, floor_area),
        })
    return rows


def tochi_excess_grid(floor_area: float = 100, unit_price: int = 200_000,
                      areas: list[int] | None = None) -> list[dict]:
    """土地面積べつの税額。**効いているのは面積そのものではなく、はみ出した分。**"""
    areas = areas or [100, 150, 200, 250, 300, 400]
    rows = []
    for area in areas:
        rows.append({
            "土地面積": area,
            "評価額": area * unit_price,
            "はみ出した面積": max(0.0, area - tochi_zero_area(floor_area)),
            "税額": tochi_tax(area, unit_price, floor_area),
        })
    return rows


# ---- 節4: 土地の控除は床面積100平方メートルで頭打ち --------------------
def floor_credit_grid(unit_price: int = 200_000,
                      floors: list[int] | None = None) -> list[dict]:
    """床面積を広げても、土地の控除が増えるのは100平方メートルまで。"""
    floors = floors or [50, 70, 90, 100, 110, 150, 200, 240]
    rows = []
    for floor in floors:
        rows.append({
            "床面積": floor,
            "床面積の2倍": min(floor * 2, LAND_AREA_CAP),
            "土地の控除": round(tochi_credit(unit_price, floor)),
            "土地300平方メートルの税額": tochi_tax(300, unit_price, floor),
        })
    return rows


def floor_credit_flat_from() -> dict:
    """控除が伸びなくなる床面積と、そこから上がどれだけ同額で並ぶか。"""
    unit = 200_000
    rows = floor_credit_grid(unit)
    top = max(r["土地の控除"] for r in rows)
    flat = [r["床面積"] for r in rows if r["土地の控除"] == top]
    return {"頭打ちになる床面積": LAND_AREA_CAP / 2,
            "頭打ちの控除額": top,
            "同額で並ぶ床面積": flat,
            "同額で並ぶ幅": max(flat) - min(flat)}


# ---- 節5: 45,000円の下限が効く土地 -------------------------------------
def floor_price_threshold_grid(floors: list[int] | None = None) -> list[dict]:
    """床面積べつ「45,000円の下限が効く1平方メートル単価の上限」。"""
    floors = floors or [50, 60, 75, 90, 100, 150, 240]
    rows = []
    for floor in floors:
        limit = floor_credit_cap(floor)
        rows.append({
            "床面積": floor,
            "下限が効く単価の上限": round(limit),
            "その単価での控除": round(tochi_credit(limit, floor)),
            "上限の2倍の単価での控除": round(tochi_credit(limit * 2, floor)),
        })
    return rows


def floor_price_threshold_span() -> dict:
    """敷居の開き。**床面積が広いほど、下限に守られる土地は安い側だけになります。**"""
    rows = floor_price_threshold_grid()
    hi = max(rows, key=lambda r: r["下限が効く単価の上限"])
    lo = min(rows, key=lambda r: r["下限が効く単価の上限"])
    return {"最大": (hi["床面積"], hi["下限が効く単価の上限"]),
            "最小": (lo["床面積"], lo["下限が効く単価の上限"]),
            "倍率": round(hi["下限が効く単価の上限"] / lo["下限が効く単価の上限"], 2)}


# ---- 節6: 2分の1の特例は「税額が半分」ではない -------------------------
def hangaku_grid(floor_area: float = 100, land_area: float = 300,
                 unit_prices: list[int] | None = None) -> list[dict]:
    """特例のあり・なしを並べる。**控除も半分になるので、比は一定ではありません。**"""
    unit_prices = unit_prices or [5_000, 8_000, 10_000, 12_000, 15_000,
                                  30_000, 100_000, 300_000]
    rows = []
    for unit in unit_prices:
        with_h = tochi_tax_raw(land_area, unit, floor_area, hangaku=True)
        without = tochi_tax_raw(land_area, unit, floor_area, hangaku=False)
        rows.append({
            "1平方メートル単価": unit,
            "特例なしの税額": without,
            "特例ありの税額": with_h,
            "残る割合": None if without == 0 else round(with_h / without, 4),
        })
    return rows


def hangaku_zero_limit(floor_area: float = 100, land_area: float = 300,
                       *, hangaku: bool = True) -> int:
    """税額が0円で消える1平方メートル単価の上限（**1円きざみで探します**）。"""
    lo, hi = 0, 1_000_000
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if tochi_tax_raw(land_area, mid, floor_area, hangaku=hangaku) == 0:
            lo = mid
        else:
            hi = mid - 1
    return lo


def hangaku_extremes() -> dict:
    """残る割合の両端。**ちょうど半分になるのは、下限が効かない土地だけ。**"""
    rows = [r for r in hangaku_grid() if r["残る割合"] is not None]
    hi = max(rows, key=lambda r: r["残る割合"])
    lo = min(rows, key=lambda r: r["残る割合"])
    return {"最大": (hi["1平方メートル単価"], hi["残る割合"]),
            "最小": (lo["1平方メートル単価"], lo["残る割合"]),
            "半分ちょうどの件数": sum(1 for r in rows if r["残る割合"] == 0.5)}


# ---- 節7: 中古住宅は新築時期で控除が12倍ちがう -------------------------
def chuko_grid(value: int = 15_000_000) -> list[dict]:
    """新築時期べつの控除額と税額。**同じ家でも、建った年で税が変わります。**"""
    rows = []
    prev = None
    for name, kojo in CHUKO_KOJO:
        tax = kaoku_tax(value, 100, chuko=name)
        rows.append({
            "新築された時期": name,
            "控除額": kojo,
            "税額": tax,
            "1つ前の段との差": None if prev is None else prev - tax,
        })
        prev = tax
    return rows


def chuko_span() -> dict:
    """控除額と税額の開き。**段の数と、いちばん深い段差。**"""
    rows = chuko_grid()
    diffs = [(r["新築された時期"], r["1つ前の段との差"])
             for r in rows if r["1つ前の段との差"]]
    top = max(diffs, key=lambda d: d[1])
    return {"控除の倍率": CHUKO_KOJO[-1][1] // CHUKO_KOJO[0][1],
            "段数": len(CHUKO_KOJO),
            "税額の最大差": rows[0]["税額"] - rows[-1]["税額"],
            "いちばん深い段差": top}


def grid() -> list[dict]:
    """図解の既定の表。"""
    return kaoku_zero_grid()


def check_tables() -> None:
    """制度の値と、この計算の主題そのものを確かめる。"""
    # 1. 法令が名指ししている値
    _checks.statutory(RATE_JUTAKU, 0.03, "住宅・土地の税率",
                      source="地方税法附則11条の2")
    _checks.statutory(RATE_HIJUTAKU, 0.04, "住宅以外の家屋の標準税率",
                      source="地方税法73条の15")
    _checks.statutory(SHINCHIKU_KOJO, 12_000_000, "新築住宅の控除",
                      source="地方税法73条の14第1項")
    _checks.statutory(CHOKI_KOJO, 13_000_000, "認定長期優良住宅の控除",
                      source="地方税法附則11条第10項")
    _checks.statutory(LAND_CREDIT_FLOOR, 45_000, "土地の税額控除の下限",
                      source="地方税法73条の24第1項一号")
    _checks.statutory(LAND_AREA_CAP, 200, "床面積の2倍の上限",
                      source="地方税法73条の24第1項二号")
    _checks.statutory(MENZEI_SHINCHIKU, 230_000, "免税点・建築に係る家屋",
                      source="地方税法73条の15の2")
    _checks.statutory(FLOOR_MAX, 240, "床面積の上限",
                      source="地方税法施行令37条の16")
    for value, name in ((RATE_JUTAKU, "住宅の税率"),
                        (RATE_HIJUTAKU, "住宅以外の税率"),
                        (TAKUCHI_HANGAKU, "宅地の課税標準の割合")):
        _checks.ratio(value, name)

    # 2. 節1 —— 0円で済む上限は、控除額そのものではなく免税点のぶん上
    limit = kaoku_zero_limit()
    _checks.greater(limit, SHINCHIKU_KOJO,
                    "0円で済む評価額の上限が、控除額を上回っていない")
    _checks.rounding(limit, 12_229_999, "一般の新築住宅で0円で済む評価額の上限")
    _checks.rounding(kaoku_tax(limit, 100), 0, "その上限ちょうどの税額")
    _checks.rounding(kaoku_tax(limit + 1, 100), 6_900, "1円こえたときの税額")
    _checks.rounding(kaoku_zero_limit(choki=True) - limit,
                     CHOKI_KOJO - SHINCHIKU_KOJO,
                     "長期優良と一般で、0円の上限の差が控除額の差と一致しない")

    # 3. 節2 —— 床面積の崖は上と下の両方にあり、同じ額
    for value in (15_000_000, 20_000_000, 30_000_000):
        low = kaoku_tax(value, FLOOR_MIN - 1) - kaoku_tax(value, FLOOR_MIN)
        high = kaoku_tax(value, FLOOR_MAX + 1) - kaoku_tax(value, FLOOR_MAX)
        _checks.rounding(low, high,
                         f"評価額{value}円で、下の崖と上の崖の額が違う")
        _checks.greater(low, 0, "床面積の要件を外れたのに税額が増えていない")
    _checks.rounding(floor_cliff_max()["跳ぶ額の上限"], 360_000,
                     "床面積の崖の頭打ち")

    # 4. 節3 —— 0円で済む土地面積は、単価によらない
    zero_area = tochi_zero_area(100)
    for unit in (50_000, 200_000, 1_000_000):
        _checks.rounding(tochi_tax(zero_area, unit, 100), 0,
                         f"単価{unit}円で、はみ出していない土地に税がかかっている")
        _checks.greater(tochi_tax(zero_area + 50, unit, 100), 0,
                        f"単価{unit}円で、はみ出した土地に税がかかっていない")
    _checks.increases_with(lambda a: tochi_tax(a, 200_000, 100),
                           [200, 250, 300, 400],
                           "土地が広くなったのに税額が増えていない")

    # 5. 節4 —— 土地の控除は床面積100平方メートルで頭打ち
    _checks.never_decreases(lambda f: tochi_credit(200_000, f),
                            [50, 70, 90, 100, 150, 240],
                            "床面積が広いのに土地の控除が減っている")
    _checks.rounding(tochi_credit(200_000, 100), tochi_credit(200_000, 240),
                     "床面積100と240で土地の控除が違う（頭打ちになっていない）")
    _checks.rounding(floor_credit_flat_from()["頭打ちになる床面積"],
                     LAND_AREA_CAP / 2, "控除が頭打ちになる床面積")

    # 6. 節5 —— 下限が効く単価の敷居は、床面積100平方メートルから動かない
    _checks.rounding(round(floor_credit_cap(100)), 15_000,
                     "床面積100平方メートルで下限が効く単価の上限")
    _checks.rounding(round(floor_credit_cap(50)), 30_000,
                     "床面積50平方メートルで下限が効く単価の上限")
    _checks.rounding(round(floor_credit_cap(240)), round(floor_credit_cap(100)),
                     "床面積240と100で敷居が違う（頭打ちになっていない）")

    # 7. 節6 —— 「2分の1」は上限であって、下回ることはあっても上回らない
    for row in hangaku_grid():
        if row["残る割合"] is not None:
            _checks.greater(TAKUCHI_HANGAKU + 1e-12, row["残る割合"],
                            f"単価{row['1平方メートル単価']}円で、"
                            "特例ありの税額が半分を上回っている")
    _checks.greater(hangaku_zero_limit(), hangaku_zero_limit(hangaku=False),
                    "特例があるのに、税額が消える単価の上限が上がっていない")

    # 8. 節7 —— 中古の控除は新築が新しいほど大きく、税額はその逆
    _checks.unique_by(CHUKO_KOJO, lambda r: r[0], "中古住宅の新築時期の区分")
    _checks.ascending([k for _, k in CHUKO_KOJO], "中古住宅の控除額", strict=True)
    rows = chuko_grid()
    _checks.ascending([-r["税額"] for r in rows], "中古住宅の税額（新しいほど安い）")
    _checks.rounding(chuko_span()["控除の倍率"], 12,
                     "中古住宅の控除額の、いちばん上と下の倍率")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 新築住宅が0円で済むのは1,200万円までではない。1,222万9,999円まで ===")
    for row in kaoku_zero_grid():
        print(row)
    print("崖:", kaoku_zero_cliff())

    print("\n=== 床面積1平方メートルで360,000円。しかも崖は49平方メートルにもある ===")
    for row in floor_cliff_grid():
        print(row)
    print("頭打ち:", floor_cliff_max())
    print("両端:", floor_both_ends())

    print("\n=== 土地の税額を決めているのは面積でも単価でもなく、はみ出した面積 ===")
    for row in tochi_area_grid():
        print(row)
    for row in tochi_excess_grid():
        print(row)

    print("\n=== 家を2.4倍広くしても、土地の税は1円も変わらない（100平方メートルで頭打ち）===")
    for row in floor_credit_grid():
        print(row)
    print("頭打ち:", floor_credit_flat_from())

    print("\n=== 45,000円の下限に守られるのは、床面積が広い家ほど安い土地だけ ===")
    for row in floor_price_threshold_grid():
        print(row)
    print("敷居の開き:", floor_price_threshold_span())

    print("\n=== 宅地の2分の1は「税額が半分」ではない。4分の1にも0円にもなる ===")
    for row in hangaku_grid():
        print(row)
    print("両端:", hangaku_extremes())
    print("税額が消える単価の上限:", hangaku_zero_limit(),
          "／特例なし:", hangaku_zero_limit(hangaku=False))

    print("\n=== 中古住宅は、建った時期で控除が12倍ちがう。段差は単調ではない ===")
    for row in chuko_grid():
        print(row)
    print("開き:", chuko_span())
