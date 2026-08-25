"""住んでいた家を売ったときの3,000万円特別控除 —— **同じ3,000万円でも、消える税は
4,263,000円 から 6,094,500円 まで、1.4296倍 の幅がある。**

    python -m src.calc.jouto

一般の解説はこう言います ——「マイホームを売った利益は3,000万円まで税金がかかりません」。
**合っています。そのうえで、その3,000万円が実際に何円の税を消しているのかを、
利益の大きさべつに並べた数字は、どこにも出ていません。**

特別控除は「所得を3,000万円減らす」制度であって、「税を一定額まけてくれる」制度では
ないからです。**減った所得にどの税率が当たっていたかで、効き目は変わります。**

## 効き目は3段。折れているのは譲渡益6,000万円と9,000万円

10年超所有の軽減税率（措置法31条の3）が当たる家では、
課税長期譲渡所得の6,000万円以下の部分が14.21パーセント、
超える部分が20.315パーセントです。特別控除は**上から3,000万円を消す**ので、

    譲渡益 3,000万円   消える税 4,263,000円  （3,000万円 × 14.21パーセント）
    譲渡益 7,000万円   消える税 4,873,500円
    譲渡益 9,000万円   消える税 6,094,500円  （3,000万円 × 20.315パーセント）
    譲渡益 1億5,000万円 消える税 6,094,500円  ← ここから上は動かない

**譲渡益が2倍の人の控除が2倍効くわけではなく、9,000万円で頭打ちになります。**

## 買った値段が分からない家は、売値 32,787,350円 から税金が出ます

取得費が分からないときは譲渡価額の5パーセントを取得費とします（措置法31条の4）。
売値の95パーセントが利益として残るので、3,000万円の控除では足りなくなる点があります。
仲介手数料を上限（売買価格の3パーセント＋6万円）＋消費税10パーセントとして置くと、
**その点は 32,787,350円** です。売値が1億円なら、税額は 8,857,947円 になります。

## 所有期間は「売った年の1月1日」で数えます

譲渡益5,000万円（課税2,000万円）の家で、税額は

    5年以下（短期・39.63パーセント）    7,926,000円
    5年超（長期・20.315パーセント）     4,063,000円
    10年超（軽減・14.21パーセント）     2,842,000円

**同じ家を年内に売るか年明けに売るかで 3,863,000円 動きます。**
実際に住んでいた年数ではなく、**売った年の1月1日時点**で数えるためです。

## 共有名義なら、控除は人ごとに3,000万円

譲渡益6,000万円の家を夫婦で2分の1ずつ持っていれば、
1人あたりの譲渡益が3,000万円になり、**2人とも控除の中に収まって税額は0円**です。
単独名義なら 4,263,000円 かかります。持分を10パーセント動かすごとに、
2人合計の税額は 852,600円 ずつ動きます。
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値（長く動いていないものだけ）--------------------------------
TOKUBETSU_KOJO = 30_000_000     # 居住用財産の特別控除（措置法35条1項）
FUKKO = 0.021                   # 復興特別所得税（所得税額の2.1パーセント・2037年分まで）

CHOKI_SHOTOKU = 0.15            # 長期譲渡所得の所得税（措置法31条1項）
CHOKI_JUMIN = 0.05              # 長期譲渡所得の住民税（地方税法附則34条）
TANKI_SHOTOKU = 0.30            # 短期譲渡所得の所得税（措置法32条1項）
TANKI_JUMIN = 0.09              # 短期譲渡所得の住民税（地方税法附則35条）
KEIGEN_SHOTOKU = 0.10           # 10年超所有の軽減税率・所得税（措置法31条の3第1項）
KEIGEN_JUMIN = 0.04             # 同・住民税（地方税法附則34条の3）
KEIGEN_CAP = 60_000_000         # 軽減税率が当たる課税長期譲渡所得の上限（同項）

GAISAN_RATE = 0.05              # 概算取得費（措置法31条の4）
CHUKAI_RATE = 0.03              # 仲介手数料の上限の率（宅建業法46条・告示）
CHUKAI_ADD = 60_000             # 同・加算額
SHOHIZEI = 0.10                 # 仲介手数料にかかる消費税

ASSUMPTIONS = [
    "自分が住んでいた家と土地を売ったときの、所得税と住民税を計算しています。"
    "居住用財産の3,000万円特別控除は租税特別措置法35条1項の額です",
    "特別控除が使えるのは、住まなくなってから3年を経過する日の属する年の"
    "12月31日までに売った場合で、前年と前々年に同じ特例を受けていないことが条件です。"
    "この計算では条件を満たしているものとしています",
    "所有期間は売った年の1月1日で数えます。5年以下が短期、5年超が長期、"
    "10年超だと軽減税率の対象になります。実際に住んでいた年数ではありません",
    "税率は短期が39.63パーセント、長期が20.315パーセント、"
    "10年超の軽減税率が課税長期譲渡所得6,000万円以下の部分で14.21パーセントです。"
    "いずれも復興特別所得税として所得税額の2.1パーセントを含めています",
    "軽減税率で6,000万円を超える部分は20.315パーセントに戻ります。"
    "この6,000万円は特別控除を引いたあとの金額で測ります",
    "譲渡費用は仲介手数料の上限だけを置いています。売買価格の3パーセントに6万円を足し、"
    "消費税10パーセントを加えた額です。これは仮定で、測量費や解体費は入れていません",
    "取得費が分からない場合は、譲渡価額の5パーセントを取得費とする概算取得費を使っています。"
    "建物の減価償却は、取得費が分かる場合の計算に含めていません",
    "共有名義の場合は、家屋と土地を同じ持分で共有し、"
    "どちらの持分の人もその家に住んでいたものとしています。"
    "土地だけを持っている人には特別控除の上限が別にあります",
    "住民税は譲渡した年の翌年度に課税されます。この計算では年をまたぐ分は分けていません",
    "国民健康保険料や医療費の窓口負担への影響は入れていません。"
    "分離課税の譲渡所得も、これらの判定では所得に数えられます",
]


# ---- 計算 ---------------------------------------------------------------

def rate_tanki() -> float:
    """短期譲渡（5年以下）の合計税率。"""
    return round(TANKI_SHOTOKU * (1 + FUKKO) + TANKI_JUMIN, 6)


def rate_choki() -> float:
    """長期譲渡（5年超）の合計税率。"""
    return round(CHOKI_SHOTOKU * (1 + FUKKO) + CHOKI_JUMIN, 6)


def rate_keigen() -> float:
    """10年超所有の軽減税率（6,000万円以下の部分）。"""
    return round(KEIGEN_SHOTOKU * (1 + FUKKO) + KEIGEN_JUMIN, 6)


KINDS = ("短期", "長期", "軽減")


def taxable(gain: float, *, kojo: bool = True) -> float:
    """課税譲渡所得。**特別控除は所得を減らすのであって、税を減らすのではない。**"""
    base = gain - (TOKUBETSU_KOJO if kojo else 0)
    return max(0.0, base)


def tax_on_base(base: float, kind: str) -> float:
    """課税譲渡所得 base にかかる税額（所得税＋住民税）。"""
    if kind == "短期":
        return base * rate_tanki()
    if kind == "長期":
        return base * rate_choki()
    if kind == "軽減":
        low = min(base, KEIGEN_CAP)
        high = max(0.0, base - KEIGEN_CAP)
        return low * rate_keigen() + high * rate_choki()
    raise ValueError(f"所有期間の区分が違う: {kind}")


def tax_of(gain: float, kind: str, *, kojo: bool = True) -> float:
    """譲渡益 gain にかかる税額。"""
    return tax_on_base(taxable(gain, kojo=kojo), kind)


def kojo_value(gain: float, kind: str) -> float:
    """特別控除が実際に消している税額。**これが「3,000万円の値打ち」。**"""
    return tax_of(gain, kind, kojo=False) - tax_of(gain, kind, kojo=True)


def marginal_rate(gain: float, kind: str) -> float:
    """譲渡益をあと1万円増やしたときに、増える税の割合。"""
    step = 10_000
    return round((tax_of(gain + step, kind) - tax_of(gain, kind)) / step, 6)


def hiyo(price: float) -> float:
    """譲渡費用（仲介手数料の上限＋消費税）。**仮定。ASSUMPTIONS に書いてある。**"""
    return (price * CHUKAI_RATE + CHUKAI_ADD) * (1 + SHOHIZEI)


def gain_from_price(price: float, cost: float | None) -> float:
    """売値と取得費から譲渡益を出す。cost が None なら概算取得費（5パーセント）。"""
    shutoku = price * GAISAN_RATE if cost is None else cost
    return price - shutoku - hiyo(price)


def gaisan_breakeven() -> float:
    """取得費が分からない家で、税額が出はじめる売値。**式で解く（走査しない）。**

    price - price*0.05 - (price*0.03 + 60,000)*1.1 - 30,000,000 = 0
    """
    slope = 1 - GAISAN_RATE - CHUKAI_RATE * (1 + SHOHIZEI)
    const = CHUKAI_ADD * (1 + SHOHIZEI) + TOKUBETSU_KOJO
    return const / slope


# ---- 表（図解がそのまま食える dict のリスト）-----------------------------

GAINS = [10_000_000, 20_000_000, 30_000_000, 40_000_000, 50_000_000,
         60_000_000, 70_000_000, 80_000_000, 90_000_000,
         100_000_000, 150_000_000]


def rate_grid() -> list[dict]:
    """区分ごとの税率。**復興特別所得税を含めた形で並べる。**"""
    return [
        {"区分": "短期（5年以下）", "所得税": round(TANKI_SHOTOKU * (1 + FUKKO), 6),
         "住民税": TANKI_JUMIN, "合計": rate_tanki(),
         "合計（パーセント）": round(rate_tanki() * 100, 4)},
        {"区分": "長期（5年超）", "所得税": round(CHOKI_SHOTOKU * (1 + FUKKO), 6),
         "住民税": CHOKI_JUMIN, "合計": rate_choki(),
         "合計（パーセント）": round(rate_choki() * 100, 4)},
        {"区分": "軽減（10年超・6,000万円以下）",
         "所得税": round(KEIGEN_SHOTOKU * (1 + FUKKO), 6),
         "住民税": KEIGEN_JUMIN, "合計": rate_keigen(),
         "合計（パーセント）": round(rate_keigen() * 100, 4)},
    ]


def value_grid(kind: str = "軽減") -> list[dict]:
    """譲渡益べつに、特別控除が消している税額。**3段で折れる。**"""
    out = []
    for g in GAINS:
        v = kojo_value(g, kind)
        out.append({"譲渡益": g,
                    "控除前の税額": round(tax_of(g, kind, kojo=False)),
                    "控除後の税額": round(tax_of(g, kind)),
                    "控除が消した税額": round(v),
                    "控除1円あたりの効き目": round(v / TOKUBETSU_KOJO, 6)})
    return out


def marginal_grid(kind: str = "軽減") -> list[dict]:
    """譲渡益を1万円増やしたときの、増える税の割合。**9,000万円で段が上がる。**"""
    return [{"譲渡益": g, "1円あたりの税": marginal_rate(g, kind),
             "パーセント": round(marginal_rate(g, kind) * 100, 4)}
            for g in [50_000_000, 80_000_000, 85_000_000, 90_000_000,
                      95_000_000, 120_000_000]]


def kind_grid(gain: float = 50_000_000) -> list[dict]:
    """同じ譲渡益を、3つの区分で並べる。**1月1日の判定だけで動く幅。**"""
    base = taxable(gain)
    return [{"区分": k, "課税譲渡所得": round(base),
             "税額": round(tax_of(gain, k)),
             "長期との差": round(tax_of(gain, k) - tax_of(gain, "長期"))}
            for k in KINDS]


PRICES = [30_000_000, 32_787_350, 40_000_000, 50_000_000,
          60_000_000, 80_000_000, 100_000_000]


def gaisan_grid() -> list[dict]:
    """取得費が分からない家。**売値の95パーセントが利益として残る。**"""
    out = []
    for p in PRICES:
        g = gain_from_price(p, None)
        out.append({"売値": p,
                    "概算取得費": round(p * GAISAN_RATE),
                    "譲渡費用": round(hiyo(p)),
                    "譲渡益": round(g),
                    "課税譲渡所得": round(taxable(g)),
                    "税額（軽減税率）": round(tax_of(g, "軽減"))})
    return out


def known_cost_grid(price: float = 50_000_000) -> list[dict]:
    """同じ売値で、取得費が分かっている場合と分からない場合。"""
    out = []
    for ratio in (None, 0.3, 0.5, 0.7, 0.9):
        cost = None if ratio is None else price * ratio
        g = gain_from_price(price, cost)
        out.append({"取得費": "分からない（5パーセント）" if ratio is None else round(cost),
                    "譲渡益": round(g),
                    "課税譲渡所得": round(taxable(g)),
                    "税額（軽減税率）": round(tax_of(g, "軽減"))})
    return out


def share_grid(gain: float = 60_000_000) -> list[dict]:
    """共有名義。**控除は人ごとに3,000万円なので、持分で税額が動く。**"""
    out = []
    for share in (0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        a = gain * share
        b = gain * (1 - share)
        ta = tax_of(a, "軽減")
        tb = tax_of(b, "軽減")
        out.append({"多いほうの持分": share,
                    "多いほうの譲渡益": round(a),
                    "多いほうの税額": round(ta),
                    "少ないほうの税額": round(tb),
                    "2人合計の税額": round(ta + tb)})
    return out


def price_cost_grid() -> list[dict]:
    """売値と取得費の格子。**「3,000万円まで無税」は売値の話ではない。**"""
    out = []
    for price in (40_000_000, 60_000_000, 80_000_000):
        for cost in (10_000_000, 20_000_000, 30_000_000, 40_000_000):
            g = gain_from_price(price, cost)
            out.append({"売値": price, "取得費": cost,
                        "譲渡益": round(g),
                        "課税譲渡所得": round(taxable(g)),
                        "税額（軽減税率）": round(tax_of(g, "軽減"))})
    return out


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(TOKUBETSU_KOJO, 30_000_000, "居住用財産の特別控除",
                      source="租税特別措置法35条1項")
    _checks.statutory(KEIGEN_CAP, 60_000_000, "軽減税率が当たる上限",
                      source="租税特別措置法31条の3第1項")
    _checks.statutory(FUKKO, 0.021, "復興特別所得税の率",
                      source="復興財源確保法13条")
    for r, name in ((CHOKI_SHOTOKU, "長期の所得税"), (CHOKI_JUMIN, "長期の住民税"),
                    (TANKI_SHOTOKU, "短期の所得税"), (TANKI_JUMIN, "短期の住民税"),
                    (KEIGEN_SHOTOKU, "軽減の所得税"), (KEIGEN_JUMIN, "軽減の住民税"),
                    (GAISAN_RATE, "概算取得費の率"), (CHUKAI_RATE, "仲介手数料の率"),
                    (SHOHIZEI, "消費税")):
        _checks.ratio(r, name)

    # 2. 合計税率。**公表されている形と一致すること**
    _checks.close(rate_tanki(), 0.3963, "短期の合計税率")
    _checks.close(rate_choki(), 0.20315, "長期の合計税率")
    _checks.close(rate_keigen(), 0.1421, "軽減の合計税率")
    _checks.greater(rate_tanki(), rate_choki(), "短期の税率が長期以下")
    _checks.greater(rate_choki(), rate_keigen(), "長期の税率が軽減以下")

    # 3. この計算の主題そのもの
    # 控除の値打ちは、譲渡益が増えても減らない（3段で上がって止まる）
    _checks.never_decreases(lambda g: kojo_value(g, "軽減"),
                            [30_000_000, 60_000_000, 75_000_000,
                             90_000_000, 150_000_000],
                            "譲渡益が増えたのに控除の効き目が下がっている")
    _checks.rounding(kojo_value(30_000_000, "軽減"), 4_263_000,
                     "譲渡益3,000万円のときに控除が消す税額")
    _checks.rounding(kojo_value(90_000_000, "軽減"), 6_094_500,
                     "譲渡益9,000万円のときに控除が消す税額")
    _checks.rounding(kojo_value(150_000_000, "軽減"), 6_094_500,
                     "譲渡益1億5,000万円のときに控除が消す税額（頭打ちのはず）")
    _checks.close(kojo_value(90_000_000, "軽減") / kojo_value(30_000_000, "軽減"),
                  6_094_500 / 4_263_000, "控除の効き目の幅")
    # 譲渡益が控除以下なら税額は0
    _checks.statutory(tax_of(30_000_000, "軽減"), 0, "譲渡益3,000万円の税額")
    _checks.statutory(tax_of(29_999_999, "短期"), 0, "譲渡益3,000万円未満の税額")
    _checks.greater(tax_of(30_000_001, "短期"), 0, "譲渡益3,000万円超で税額が0")
    # 区分の大小は、どの譲渡益でもひっくり返らない
    for g in (40_000_000, 90_000_000, 150_000_000):
        _checks.greater(tax_of(g, "短期"), tax_of(g, "長期"),
                        f"譲渡益{g:,}円で短期の税額が長期以下")
        _checks.greater(tax_of(g, "長期"), tax_of(g, "軽減"),
                        f"譲渡益{g:,}円で長期の税額が軽減以下")
    # 軽減税率の段は、控除を引いたあとの6,000万円＝譲渡益9,000万円にある
    _checks.close(marginal_rate(80_000_000, "軽減"), rate_keigen(),
                  "譲渡益8,000万円のところで軽減の税率が当たっていない")
    _checks.close(marginal_rate(95_000_000, "軽減"), rate_choki(),
                  "譲渡益9,500万円のところで長期の税率に戻っていない")
    # 概算取得費の折れ点は、式で解いた値と走査が一致すること
    be = gaisan_breakeven()
    _checks.rounding(round(be), 32_787_350, "取得費が分からない家で税額が出はじめる売値")
    _checks.statutory(round(tax_of(gain_from_price(be, None), "軽減")), 0,
                      "折れ点ちょうどの売値の税額")
    _checks.greater(tax_of(gain_from_price(be + 1_000_000, None), "軽減"), 0,
                    "折れ点より100万円高く売っても税額が0")
    _checks.increases_with(lambda p: tax_of(gain_from_price(p, None), "軽減"),
                           [40_000_000, 60_000_000, 80_000_000, 100_000_000],
                           "売値が増えたのに税額が増えていない")
    # 共有は、単独より必ず軽いか同じ。持分の段は一定
    rows = share_grid()
    _checks.statutory(rows[0]["2人合計の税額"], 0,
                      "譲渡益6,000万円を2分の1ずつ持ったときの税額")
    _checks.rounding(rows[-1]["2人合計の税額"], 4_263_000,
                     "譲渡益6,000万円を単独で持ったときの税額")
    steps = [rows[i + 1]["2人合計の税額"] - rows[i]["2人合計の税額"]
             for i in range(len(rows) - 1)]
    for s in steps:
        _checks.rounding(s, 852_600, "持分を10パーセント動かしたときの税額の段")
    _checks.unique_by(value_grid(), lambda r: r["譲渡益"], "譲渡益べつの控除の効き目")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 3,000万円の控除が消す税は4,263,000円から6,094,500円まで1.4296倍変わる ===")
    for row in rate_grid():
        print(row)
    for row in value_grid():
        print(row)
    print("効き目の幅（倍）:",
          round(kojo_value(90_000_000, "軽減") / kojo_value(30_000_000, "軽減"), 4))

    print("\n=== 控除の効き目が折れるのは譲渡益6,000万円と9,000万円。1円あたりの税が段で上がる ===")
    for row in marginal_grid():
        print(row)

    print("\n=== 所有期間は売った年の1月1日で数える。譲渡益5,000万円なら3,863,000円動く ===")
    for row in kind_grid():
        print(row)
    print("短期と長期の差:",
          round(tax_of(50_000_000, "短期") - tax_of(50_000_000, "長期")))
    print("短期と軽減の差:",
          round(tax_of(50_000_000, "短期") - tax_of(50_000_000, "軽減")))

    print("\n=== 買った値段が分からない家は、売値32,787,350円から税金が出る ===")
    for row in gaisan_grid():
        print(row)
    print("税額が出はじめる売値:", round(gaisan_breakeven()))

    print("\n=== 同じ売値5,000万円でも、取得費が分かるかどうかで税額は0円から2,242,906円まで動く ===")
    for row in known_cost_grid():
        print(row)

    print("\n=== 共有名義なら控除は人ごとに3,000万円。持分10パーセントごとに852,600円動く ===")
    for row in share_grid():
        print(row)

    print("\n=== 「3,000万円まで無税」は売値ではなく譲渡益の話。売値8,000万円でも取得費次第で0円 ===")
    for row in price_cost_grid():
        print(row)
