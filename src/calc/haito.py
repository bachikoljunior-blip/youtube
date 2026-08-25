"""上場株式の配当を総合課税で申告すべきかどうか —— **境目は課税所得695万円で、
そこでの差は 0.158ポイント しかない。**

    python -m src.calc.haito

一般の解説はこう言います ——「課税所得が900万円以下なら、配当は総合課税で
申告したほうが有利です」。**その言い方は、境目が900万円だと読めます。合っていません。**
そして**境目そのものより、境目のすぐ両側で差がほとんど無いことのほうが大事**なのに、
その幅を金額で並べた表はどこにも出ていません。

配当控除は所得税で10パーセント、住民税で2.8パーセント（所得税法92条・
地方税法37条の3）。総合課税で配当にかかる実効の税率は、所得税の税率を t として

    （t − 0.10）× 1.021 ＋ （0.10 − 0.028）

です（1.021 は復興特別所得税、0.10 は住民税の所得割）。申告分離は 20.315パーセント。

## 帯ごとに並べると、境目は695万円で、差は 0.158ポイント

    課税所得            総合の実効税率     分離との差
    195万円以下          2.095パーセント   **−18.22ポイント**（総合が有利）
    195万〜330万円       7.2パーセント     −13.115ポイント
    330万〜695万円      17.41パーセント    −2.905ポイント
    695万〜900万円     20.473パーセント    **＋0.158ポイント**（分離が有利）← ここが境目
    900万〜1,000万円   30.683パーセント    ＋10.368ポイント
    1,000万円超       37.188パーセント    ＋16.873ポイント（**配当控除が半分になる**）

**900万円は所得税の税率が23パーセントから33パーセントへ変わる線であって、
有利不利が入れ替わる線ではありません。** 入れ替わるのは695万円です。

## 課税所得1,000万円の線で、配当控除は半分になります

1,000万円を超える部分に対応する配当所得は、所得税5パーセント・住民税1.4パーセント。
実効税率はそこで **6.505ポイント** 跳ねます。**この線は配当を含めた課税所得で測る**ので、
**配当そのものが自分を線の向こうへ押し出します。**

## 配当控除は、所得税額を超えて引けません

課税所得が低いほど有利ですが、**引き切れなかった控除は捨てるだけ**です。
給与の課税所得が0円で配当が1,000,000円なら、所得税の配当控除100,000円のうち
**50,000円しか使えません**（所得税額が50,000円しかないため）。
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値 -----------------------------------------------------------
KOJO_LINE = 10_000_000          # 配当控除の率が変わる課税総所得金額等（所得税法92条1項）
KOJO_SHOTOKU_LOW = 0.10         # 配当控除・所得税（1,000万円以下の部分）
KOJO_SHOTOKU_HIGH = 0.05        # 同（1,000万円を超える部分）
KOJO_JUMIN_LOW = 0.028          # 配当控除・住民税（地方税法37条の3第1項）
KOJO_JUMIN_HIGH = 0.014         # 同（1,000万円を超える部分）

FUKKO = 0.021                   # 復興特別所得税（基準所得税額の2.1パーセント）
JUMIN_RATE = 0.10               # 住民税の所得割（標準税率）
BUNRI_SHOTOKU = 0.15            # 申告分離・源泉徴収の所得税（措置法8条の4）
BUNRI_JUMIN = 0.05              # 同・住民税（配当割）

# 所得税の速算表（上限は「次の段の始まり」で書く）
TAX_TABLE: list[tuple[int | None, float, int]] = [
    (1_950_000, 0.05, 0),
    (3_300_000, 0.10, 97_500),
    (6_950_000, 0.20, 427_500),
    (9_000_000, 0.23, 636_000),
    (18_000_000, 0.33, 1_536_000),
    (40_000_000, 0.40, 2_796_000),
    (None, 0.45, 4_796_000),
]

ASSUMPTIONS = [
    "上場株式の配当を、申告分離課税（源泉徴収のまま申告しない場合を含む）で置くか、"
    "総合課税で申告するかを比べています",
    "配当控除は所得税法92条と地方税法37条の3の率です。"
    "課税総所得金額等が1,000万円以下の部分に対応する配当所得は所得税10パーセント・"
    "住民税2.8パーセント、超える部分は所得税5パーセント・住民税1.4パーセントです",
    "配当控除は税額控除なので、所得税額と住民税の所得割額を超えて引くことはできません。"
    "引き切れなかった分は戻ってきません",
    "申告分離課税の税率は20.315パーセントです。"
    "所得税15パーセントに復興特別所得税2.1パーセントを乗せた15.315パーセントと、"
    "住民税5パーセントの合計です",
    "復興特別所得税は、配当控除を引いたあとの所得税額に2.1パーセントを掛けています",
    "住民税の所得割は10パーセントの標準税率としています。均等割は入れていません",
    "課税所得は、所得控除をすべて引いたあとの金額です。"
    "総合課税を選ぶと配当所得がここに足されるので、税率の帯が上がることがあります",
    "2023年分から、所得税と住民税で別々の課税方式を選ぶことはできません。"
    "この計算も、両方で同じ方式を選んだ場合として並べています",
    "配当所得を総合課税で申告すると合計所得金額が増えるため、"
    "国民健康保険料や配偶者控除の判定に響くことがあります。ここには入れていません",
    "上場株式の譲渡損失との損益通算は入れていません。"
    "通算するには申告分離課税を選ぶ必要があります",
    "外国株の配当や、不動産投資信託（J-REIT）の分配金は配当控除の対象外です。"
    "対象外の場合は控除率を0パーセントとして別の表に出しています",
]


# ---- 計算 ---------------------------------------------------------------

def tax_of(base: float) -> float:
    """所得税の速算表を引く（復興特別所得税は含めない）。"""
    base = max(0.0, base)
    for cap, rate, sub in TAX_TABLE:
        if cap is None or base <= cap:
            return base * rate - sub
    raise ValueError(f"速算表に当たらない: {base}")


def rate_of(base: float) -> float:
    """その課税所得に当たっている所得税の税率。"""
    base = max(0.0, base)
    for cap, rate, _sub in TAX_TABLE:
        if cap is None or base <= cap:
            return rate
    raise ValueError(f"速算表に当たらない: {base}")


def bunri_rate() -> float:
    """申告分離（源泉徴収）の合計税率。"""
    return round(BUNRI_SHOTOKU * (1 + FUKKO) + BUNRI_JUMIN, 6)


def kojo_split(base: float, haito: float) -> tuple[float, float]:
    """配当所得のうち、10パーセント側と5パーセント側に分かれる額。

    `base` は配当を含めた課税総所得金額等。**線は配当を含めた額で測る。**
    """
    over = max(0.0, base - KOJO_LINE)
    high = min(haito, over)
    return haito - high, high


def kojo_shotoku(base: float, haito: float) -> float:
    """配当控除（所得税）。"""
    low, high = kojo_split(base, haito)
    return low * KOJO_SHOTOKU_LOW + high * KOJO_SHOTOKU_HIGH


def kojo_jumin(base: float, haito: float) -> float:
    """配当控除（住民税）。"""
    low, high = kojo_split(base, haito)
    return low * KOJO_JUMIN_LOW + high * KOJO_JUMIN_HIGH


def sougou_tax(kazei: float, haito: float, *, kojo_ok: bool = True) -> float:
    """総合課税を選んだときの、所得税＋住民税の合計。

    `kazei` は配当を除いた課税所得。`kojo_ok=False` は配当控除の無い配当
    （外国株・J-REIT など）。
    """
    base = kazei + haito
    shotoku = tax_of(base)
    jumin = base * JUMIN_RATE
    if kojo_ok:
        shotoku = max(0.0, shotoku - kojo_shotoku(base, haito))
        jumin = max(0.0, jumin - kojo_jumin(base, haito))
    return shotoku * (1 + FUKKO) + jumin


def bunri_tax(kazei: float, haito: float) -> float:
    """申告分離（源泉徴収のまま）を選んだときの、所得税＋住民税の合計。"""
    return tax_of(kazei) * (1 + FUKKO) + kazei * JUMIN_RATE + haito * bunri_rate()


def sougou_marginal(kazei: float, *, kojo_ok: bool = True) -> float:
    """その課税所得の帯で、配当1円にかかる総合課税の実効税率。"""
    step = 10_000
    a = sougou_tax(kazei, 0.0, kojo_ok=kojo_ok)
    b = sougou_tax(kazei, step, kojo_ok=kojo_ok)
    return round((b - a) / step, 6)


def waste(kazei: float, haito: float) -> float:
    """配当控除のうち、所得税額が足りなくて捨てた額。"""
    base = kazei + haito
    return max(0.0, kojo_shotoku(base, haito) - tax_of(base))


# ---- 表（図解がそのまま食える dict のリスト）-----------------------------

BANDS = [1_000_000, 3_000_000, 5_000_000, 8_000_000, 9_500_000,
         12_000_000, 20_000_000, 45_000_000]

HAITO = 1_000_000


def band_grid(haito: float = HAITO) -> list[dict]:
    """課税所得の帯ごとに、総合の実効税率と分離との差。**境目は695万円。**"""
    out = []
    for k in BANDS:
        m = sougou_marginal(k)
        out.append({"配当を除いた課税所得": k,
                    "所得税の税率": rate_of(k),
                    "総合の実効税率": m,
                    "総合（パーセント）": round(m * 100, 4),
                    "分離（パーセント）": round(bunri_rate() * 100, 4),
                    "差（ポイント）": round((m - bunri_rate()) * 100, 4),
                    "有利なほう": "総合" if m < bunri_rate() else "分離"})
    return out


def border_grid(haito: float = HAITO) -> list[dict]:
    """695万円の境目の、すぐ両側。**差は 0.158ポイント しかない。**"""
    out = []
    for k in (6_800_000, 6_950_000, 7_000_000, 8_900_000, 9_100_000):
        s = sougou_tax(k, haito)
        b = bunri_tax(k, haito)
        out.append({"配当を除いた課税所得": k, "配当": round(haito),
                    "総合の税額": round(s), "分離の税額": round(b),
                    "総合−分離": round(s - b),
                    "有利なほう": "総合" if s < b else "分離"})
    return out


def waste_grid(haito: float = HAITO) -> list[dict]:
    """配当控除を引き切れずに捨てる額。**低いほど有利、は途中で止まる。**"""
    out = []
    for k in (0, 500_000, 1_000_000, 1_500_000, 2_000_000, 3_000_000):
        base = k + haito
        out.append({"配当を除いた課税所得": k, "配当": round(haito),
                    "所得税額（控除前）": round(tax_of(base)),
                    "配当控除（所得税）": round(kojo_shotoku(base, haito)),
                    "引き切れずに捨てた額": round(waste(k, haito)),
                    "総合の税額": round(sougou_tax(k, haito)),
                    "分離の税額": round(bunri_tax(k, haito))})
    return out


def line_grid(haito: float = 2_000_000) -> list[dict]:
    """1,000万円の線。**配当そのものが自分を線の向こうへ押し出す。**"""
    out = []
    for k in (7_000_000, 8_000_000, 9_000_000, 10_000_000, 11_000_000):
        base = k + haito
        low, high = kojo_split(base, haito)
        out.append({"配当を除いた課税所得": k, "配当": round(haito),
                    "配当を含めた課税所得": round(base),
                    "10パーセント側の配当": round(low),
                    "5パーセント側の配当": round(high),
                    "配当控除の合計": round(kojo_shotoku(base, haito)
                                            + kojo_jumin(base, haito)),
                    "総合の税額": round(sougou_tax(k, haito))})
    return out


def step_grid() -> list[dict]:
    """1,000万円の線をまたいだときに、実効税率が何ポイント跳ねるか。"""
    low = KOJO_SHOTOKU_LOW * (1 + FUKKO) + KOJO_JUMIN_LOW
    high = KOJO_SHOTOKU_HIGH * (1 + FUKKO) + KOJO_JUMIN_HIGH
    return [{"配当控除の効き目（1,000万円以下）": round(low, 6),
             "配当控除の効き目（1,000万円超）": round(high, 6),
             "跳ねる幅（ポイント）": round((low - high) * 100, 4),
             "所得税の率（以下）": KOJO_SHOTOKU_LOW,
             "所得税の率（超）": KOJO_SHOTOKU_HIGH,
             "住民税の率（以下）": KOJO_JUMIN_LOW,
             "住民税の率（超）": KOJO_JUMIN_HIGH}]


def amount_grid(haito: float = HAITO) -> list[dict]:
    """配当1,000,000円の税額を、帯ごとに実額で並べる。"""
    out = []
    for k in BANDS:
        s = sougou_tax(k, haito)
        b = bunri_tax(k, haito)
        out.append({"配当を除いた課税所得": k, "配当": round(haito),
                    "総合の税額": round(s), "分離の税額": round(b),
                    "総合を選んだときの差": round(s - b)})
    return out


def nokojo_grid(haito: float = HAITO) -> list[dict]:
    """配当控除の無い配当（外国株・J-REIT など）。**分離が有利になる線が下がる。**"""
    out = []
    for k in (1_000_000, 3_000_000, 3_300_000, 5_000_000, 8_000_000):
        m = sougou_marginal(k, kojo_ok=False)
        out.append({"配当を除いた課税所得": k, "配当": round(haito),
                    "総合の実効税率": m,
                    "総合（パーセント）": round(m * 100, 4),
                    "差（ポイント）": round((m - bunri_rate()) * 100, 4),
                    "有利なほう": "総合" if m < bunri_rate() else "分離"})
    return out


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""
    # 1. 法令が名指ししている値
    _checks.statutory(KOJO_LINE, 10_000_000, "配当控除の率が変わる線",
                      source="所得税法92条1項")
    _checks.statutory(KOJO_SHOTOKU_LOW, 0.10, "配当控除・所得税（1,000万円以下）",
                      source="所得税法92条1項1号")
    _checks.statutory(KOJO_JUMIN_LOW, 0.028, "配当控除・住民税（1,000万円以下）",
                      source="地方税法37条の3第1項")
    _checks.statutory(FUKKO, 0.021, "復興特別所得税の率",
                      source="復興財源確保法13条")
    for r, name in ((KOJO_SHOTOKU_HIGH, "配当控除・所得税（超）"),
                    (KOJO_JUMIN_HIGH, "配当控除・住民税（超）"),
                    (JUMIN_RATE, "住民税の所得割"),
                    (BUNRI_SHOTOKU, "分離の所得税"), (BUNRI_JUMIN, "分離の住民税")):
        _checks.ratio(r, name)
    _checks.bracket_table(TAX_TABLE, tax_of, name="所得税の速算表")
    _checks.close(bunri_rate(), 0.20315, "申告分離の合計税率")

    # 2. この計算の主題そのもの —— 境目は695万円であって900万円ではない
    _checks.close(sougou_marginal(5_000_000), 0.1741,
                  "課税所得500万円の帯の実効税率")
    _checks.close(sougou_marginal(8_000_000), 0.20473,
                  "課税所得800万円の帯の実効税率")
    _checks.greater(bunri_rate(), sougou_marginal(6_000_000),
                    "課税所得600万円で分離が総合より安い")
    _checks.greater(sougou_marginal(8_000_000), bunri_rate(),
                    "課税所得800万円で総合が分離より安い")
    _checks.close((sougou_marginal(8_000_000) - bunri_rate()) * 100, 0.158,
                  "境目のすぐ上での差（ポイント）", tol=1e-6)
    # 実効税率は帯が上がるほど上がる（同じ配当・同じ控除率）
    _checks.increases_with(sougou_marginal,
                           [1_000_000, 3_000_000, 5_000_000, 8_000_000,
                            12_000_000, 20_000_000],
                           "課税所得が上がったのに実効税率が上がっていない")
    # 1,000万円の線で跳ねる幅
    _checks.close(step_grid()[0]["跳ねる幅（ポイント）"], 6.505,
                  "1,000万円の線で跳ねる幅（ポイント）", tol=1e-6)
    # 配当控除は所得税額を超えて引けない（捨てる額が出る）
    _checks.greater(waste(0, 1_000_000), 0,
                    "課税所得0円・配当1,000,000円で捨てる額が0")
    _checks.statutory(round(waste(0, 1_000_000)), 50_000,
                      "課税所得0円・配当1,000,000円で捨てる配当控除")
    _checks.statutory(waste(5_000_000, 1_000_000), 0,
                      "課税所得500万円で捨てる配当控除")
    # 配当控除の無い配当は、境目が下がる
    _checks.greater(bunri_rate(), sougou_marginal(3_000_000, kojo_ok=False),
                    "控除の無い配当で、課税所得300万円なら総合が安いはず")
    _checks.greater(sougou_marginal(5_000_000, kojo_ok=False), bunri_rate(),
                    "控除の無い配当で、課税所得500万円なら分離が安いはず")
    # 線をまたぐと、10パーセント側の配当が減る
    rows = line_grid()
    _checks.never_decreases(lambda i: rows[i]["5パーセント側の配当"],
                            list(range(len(rows))),
                            "課税所得が上がったのに5パーセント側の配当が減っている")
    _checks.unique_by(band_grid(), lambda r: r["配当を除いた課税所得"],
                      "帯ごとの実効税率")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 配当を総合課税にする境目は課税所得695万円。900万円ではない ===")
    for row in band_grid():
        print(row)

    print("\n=== 境目のすぐ上での差は0.158ポイントしかない。配当100万円で1,580円 ===")
    for row in border_grid():
        print(row)

    print("\n=== 配当控除は所得税額を超えて引けない。課税所得0円なら50,000円を捨てる ===")
    for row in waste_grid():
        print(row)

    print("\n=== 課税所得1,000万円の線で配当控除は半分になり、実効税率が6.505ポイント跳ねる ===")
    for row in step_grid():
        print(row)

    print("\n=== 配当200万円は自分で自分を1,000万円の線の向こうへ押し出す ===")
    for row in line_grid():
        print(row)

    print("\n=== 配当1,000,000円の税額を帯ごとに実額で並べる ===")
    for row in amount_grid():
        print(row)

    print("\n=== 配当控除の無い配当（外国株・J-REIT）は、境目が課税所得330万円へ下がる ===")
    for row in nokojo_grid():
        print(row)
