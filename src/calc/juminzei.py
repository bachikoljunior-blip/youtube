"""住民税の非課税限度額。**「年収100万円まで非課税」は、住む市によって違います。**

一般の解説は「住民税は年収100万円からかかる」で止まります。ところがその100万円は
**1級地（大都市）の単身の場合の数字**で、限度額は級地で3通りあります。
そして解説は「均等割と所得割では限度額が別」であることも、
**その2つの限度額のあいだに「均等割だけがかかる帯」があること**も言いません。

そこから出てくる、公表されていない数字:

- **同じ年収なのに、住む市で課税と非課税が分かれます。** 単身の均等割は
  1級地で給与収入 **1,000,000円**、3級地で **930,000円** が境目。**差は7万円**で、
  3級地に住む年収95万円の人は課税、1級地なら非課税
- **均等割だけがかかる帯**（所得割は0円のまま均等割5,000円だけ払う帯）は、
  **単身・1級地では1円もありません**が、**扶養が1人でもいれば11万円**できます。
  加算額が均等割21万円・所得割32万円と違うためで、**扶養の人数によらず11万円で一定**。
  3級地では **7万円 × 世帯人数 ＋ 15.2万円** で、**扶養が増えるほど広がります**
  （夫婦子1人の3級地なら **36.2万円**、給与収入でいうと **534,286円**ぶんの帯）
- **限度額を1円こえると、単身・1級地で住民税は 6,000円。** 内訳は
  均等割5,000円と所得割1,000円で、**所得割の 2,000円 のうち半分は調整控除で消えます**
- そのあと**手取りが元に戻るのは、合計所得があと 6,316円 増えたとき。**
  つまり 450,000円 から 456,316円 までは、**稼ぐほど手元が減ります**
- **その谷の幅を決めているのは、世帯人数でも級地でもありません。**
  取り返す額は、扶養がいればどの人数でも**均等割の5,000円ちょうど**（その帯では
  所得割が0円のまま）。ところが年収でいうと **5,000／5,556／6,250／7,143／8,333円**
  の5通りに化けます —— 給与所得控除の段で「合計所得の増える率」が
  1.0 / 0.6 / 0.7 / 0.8 / 0.9 と変わるためで、**幅は 5,000 ÷ その率**。
  だから**人数について単調ですらありません**（3級地は 世帯2人 5,000円 →
  3人 **8,333円** → 4人 7,143円）
- **所得割は「課税所得 × 10パーセント」ではありません。** 調整控除があるので、
  課税所得が5万円までは**実効で5パーセント**。10パーセントに近づくのは
  課税所得が5万円を超えてからで、**課税所得2万円のときの実効税率は5.00パーセント**
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値 ----------------------------------------------------------
# 均等割の標準税率（地方税法310条・38条）。市町村民税3,000円＋道府県民税1,000円。
# 2024年度から復興財源の上乗せ（各500円）が終わり、代わりに森林環境税（国税）
# 1,000円が住民税の均等割とあわせて徴収されるので、**納める合計は5,000円のまま**
KINTOWARI_CITY = 3_000
KINTOWARI_PREF = 1_000
FOREST_TAX = 1_000
KINTOWARI_TOTAL = KINTOWARI_CITY + KINTOWARI_PREF + FOREST_TAX   # 5,000円

# 所得割の標準税率（地方税法35条・314条の3）。市町村6％＋道府県4％
SHOTOKUWARI_RATE = 0.10

# 住民税の基礎控除（地方税法314条の2。合計所得金額2,400万円以下）
BASIC_DEDUCTION = 430_000

# 調整控除。人的控除の差（基礎控除は所得税48万円・住民税43万円で5万円）を、
# 合計課税所得金額が200万円以下なら小さいほうと比べて5％（地方税法附則5条の4の2）
JINTEKI_DIFF_BASIC = 50_000
CHOSEI_RATE = 0.05
CHOSEI_TURN = 2_000_000

# 均等割の非課税限度額（地方税法295条3項・各市町村の条例。級地区分で3通り）
#   合計所得金額 ≦ 本人分 × 世帯人数 ＋ 10万円 ＋（扶養がいるときだけ加算）
KINTOWARI_LIMITS: list[tuple[str, int, int]] = [
    # (級地, 1人あたり, 扶養がいるときの加算)
    ("1級地", 350_000, 210_000),
    ("2級地", 315_000, 189_000),
    ("3級地", 280_000, 168_000),
]
LIMIT_BASE_ADD = 100_000      # 2021年度から。給与所得控除が10万円下がったぶんの調整

# 所得割の非課税限度額（地方税法295条・施行令47条の3）。**級地によらず全国一律**
SHOTOKUWARI_PER_HEAD = 350_000
SHOTOKUWARI_ADD = 320_000

# 給与所得控除（所得税法28条3項。2020年分から動いていない）
KYUYO_MIN = 550_000

ASSUMPTIONS = [
    "住民税だけを計算しています。所得税と社会保険料は入れていません。"
    "給与収入103万円をこえると所得税もかかりますが、別の税なのでここでは見ていません",
    "均等割は標準税率で5,000円としています。市町村民税3,000円と道府県民税1,000円に、"
    "2024年度から森林環境税1,000円が加わったものです",
    "所得割の税率は標準税率の10パーセントとしています。市町村民税6パーセントと"
    "道府県民税4パーセントの合計です",
    "住民税の基礎控除は43万円としています。合計所得金額が2,400万円以下の場合の額です",
    "調整控除は、基礎控除の人的控除の差5万円と合計課税所得金額の小さいほうに"
    "5パーセントを掛けたものとしています。合計課税所得金額が200万円以下の場合の式です",
    "均等割の非課税限度額は級地区分で3通りあり、1人あたり1級地35万円、"
    "2級地31万5千円、3級地28万円としています。これに10万円を足し、"
    "扶養がいるときはさらに1級地21万円、2級地18万9千円、3級地16万8千円を足します",
    "所得割の非課税限度額は級地によらず、1人あたり35万円に10万円を足し、"
    "扶養がいるときはさらに32万円を足したものとしています",
    "給与収入から合計所得金額を出すときの給与所得控除は、収入162万5千円以下なら"
    "55万円としています",
    "障害者・未成年者・寡婦・ひとり親の非課税（合計所得135万円以下）は入れていません。"
    "ここでは、そのどれにも当たらない人を見ています",
    "基礎控除のほかの所得控除（社会保険料控除・生命保険料控除など）は0円としています。"
    "実際にあれば、所得割はここで出した額より小さくなります",
]


# ---- 給与収入と合計所得の行き来 ----------------------------------------
def kyuyo_deduction(income: int) -> int:
    """給与所得控除。**この表が扱うのは非課税限度額の周りなので、下端だけで足ります。**"""
    if income <= 1_625_000:
        return KYUYO_MIN
    if income <= 1_800_000:
        return round(income * 0.4 - 100_000)
    if income <= 3_600_000:
        return round(income * 0.3 + 80_000)
    if income <= 6_600_000:
        return round(income * 0.2 + 440_000)
    if income <= 8_500_000:
        return round(income * 0.1 + 1_100_000)
    return 1_950_000


def shotoku_of(income: int) -> int:
    """給与収入 → 合計所得金額。"""
    return max(0, income - kyuyo_deduction(income))


def income_of(shotoku: int) -> int:
    """合計所得金額 → それを生む給与収入。**限度額を年収で言うために要ります。**"""
    if shotoku <= 1_625_000 - KYUYO_MIN:
        return shotoku + KYUYO_MIN
    # **給与所得控除が「収入×40％−10万円」の帯だけ、合計所得は 0.6×収入＋10万円**
    # です（ほかの帯は控除が足し算なので、合計所得は「収入×係数−定数」）。
    # **ここだけ符号が逆**で、2026-08-17 に `+` のまま書いて素通りしました
    # （下の往復検査が、この帯を1点も踏んでいなかった）
    if shotoku <= round(1_800_000 * 0.6) + 100_000:
        return round((shotoku - 100_000) / 0.6)
    if shotoku <= round(3_600_000 * 0.7) - 80_000:
        return round((shotoku + 80_000) / 0.7)
    if shotoku <= round(6_600_000 * 0.8) - 440_000:
        return round((shotoku + 440_000) / 0.8)
    if shotoku <= round(8_500_000 * 0.9) - 1_100_000:
        return round((shotoku + 1_100_000) / 0.9)
    return shotoku + 1_950_000


# ---- 非課税限度額 ------------------------------------------------------
def kintowari_limit(grade: str, heads: int) -> int:
    """均等割の非課税限度額（合計所得金額）。`heads` は本人を含む世帯の人数。"""
    for name, per_head, add in KINTOWARI_LIMITS:
        if name == grade:
            return per_head * heads + LIMIT_BASE_ADD + (add if heads > 1 else 0)
    raise ValueError(f"知らない級地: {grade}")


def shotokuwari_limit(heads: int) -> int:
    """所得割の非課税限度額（合計所得金額）。**級地によらず全国一律。**"""
    return (SHOTOKUWARI_PER_HEAD * heads + LIMIT_BASE_ADD
            + (SHOTOKUWARI_ADD if heads > 1 else 0))


def limits_by_grade(heads: int) -> list[dict]:
    """級地3区分で、境目が年収でいくらずれるか。"""
    top = kintowari_limit("1級地", heads)
    rows = []
    for name, _per, _add in KINTOWARI_LIMITS:
        limit = kintowari_limit(name, heads)
        rows.append({
            "級地": name,
            "世帯の人数": heads,
            "均等割の非課税限度額": limit,
            "年収でいうと": income_of(limit),
            "1級地との差": top - limit,
            "年収での差": income_of(top) - income_of(limit),
        })
    return rows


def kintowari_only_band(grade: str, heads: int) -> dict:
    """**均等割だけがかかる帯。** 所得割の限度額のほうが高いぶんだけ空きます。"""
    low = kintowari_limit(grade, heads)
    high = shotokuwari_limit(heads)
    return {
        "級地": grade,
        "世帯の人数": heads,
        "均等割の非課税限度額": low,
        "所得割の非課税限度額": high,
        "帯の幅": max(0, high - low),
        "年収での下端": income_of(low),
        "年収での上端": income_of(high),
        "年収での帯の幅": max(0, income_of(high) - income_of(low)),
    }


# ---- 税額 --------------------------------------------------------------
def chosei_kojo(taxable: int) -> int:
    """調整控除。**所得割を「課税所得×10％」だと思っていると、必ず外れます。**"""
    if taxable <= 0:
        return 0
    if taxable <= CHOSEI_TURN:
        return round(min(JINTEKI_DIFF_BASIC, taxable) * CHOSEI_RATE)
    base = JINTEKI_DIFF_BASIC - (taxable - CHOSEI_TURN)
    return max(2_500, round(base * CHOSEI_RATE))


def tax(shotoku: int, grade: str = "1級地", heads: int = 1) -> dict:
    """合計所得金額から、その年の住民税。**2つの限度額を別々に当てます。**"""
    kin_free = shotoku <= kintowari_limit(grade, heads)
    sho_free = shotoku <= shotokuwari_limit(heads)
    taxable = max(0, shotoku - BASIC_DEDUCTION)
    gross = round(taxable * SHOTOKUWARI_RATE)
    chosei = chosei_kojo(taxable)
    shotokuwari = 0 if sho_free else max(0, gross - chosei)
    kintowari = 0 if kin_free else KINTOWARI_TOTAL
    return {
        "合計所得金額": shotoku,
        "級地": grade,
        "世帯の人数": heads,
        "均等割は非課税か": kin_free,
        "所得割は非課税か": sho_free,
        "課税所得": taxable,
        "調整控除の前": gross,
        "調整控除": 0 if sho_free else chosei,
        "所得割": shotokuwari,
        "均等割": kintowari,
        "住民税": shotokuwari + kintowari,
        "手取り": shotoku - (shotokuwari + kintowari),
        "実効の税率": (shotokuwari + kintowari) / shotoku * 100 if shotoku else 0.0,
    }


def cliff(grade: str = "1級地", heads: int = 1) -> dict:
    """**限度額を1円こえると、住民税はいくらになるか。**"""
    limit = min(kintowari_limit(grade, heads), shotokuwari_limit(heads))
    before = tax(limit, grade, heads)
    after = tax(limit + 1, grade, heads)
    return {
        "級地": grade,
        "世帯の人数": heads,
        "限度額": limit,
        "年収でいうと": income_of(limit),
        "限度額での住民税": before["住民税"],
        "1円こえたときの住民税": after["住民税"],
        "跳ぶ額": after["住民税"] - before["住民税"],
        "うち均等割": after["均等割"],
        "うち所得割": after["所得割"],
        "調整控除で消えた額": after["調整控除"],
    }


def recovery(grade: str = "1級地", heads: int = 1) -> dict:
    """**手取りが限度額のときの額に戻るのは、あといくら稼いだときか。**

    1円ずつ数え上げます（**式で解かずに数えるのは、調整控除の折れ目を
    またぐと式が変わるためです**。下の `check_tables` が式と突き合わせます）。
    """
    limit = min(kintowari_limit(grade, heads), shotokuwari_limit(heads))
    base = tax(limit, grade, heads)["手取り"]
    extra = 0
    while extra < 200_000:
        extra += 1
        if tax(limit + extra, grade, heads)["手取り"] >= base:
            break
    return {
        "級地": grade,
        "世帯の人数": heads,
        "限度額": limit,
        "限度額での手取り": base,
        "戻るのに要る増収": extra,
        "戻る点の合計所得": limit + extra,
        "谷の底": min(tax(limit + d, grade, heads)["手取り"]
                     for d in range(1, extra + 1)),
        "年収での谷の幅": income_of(limit + extra) - income_of(limit),
    }


def marginal_income_rate(shotoku: int) -> float:
    """合計所得を1円ふやすのに要る給与収入の逆数 ＝ **その段の「所得の増える率」**。

    給与所得控除は段ごとに 55万円（定額）／収入×40％−10万円／収入×30％＋8万円／
    収入×20％＋44万円／収入×10％＋110万円／195万円（定額）なので、
    **合計所得は収入の 1.0 / 0.6 / 0.7 / 0.8 / 0.9 / 1.0 倍**で増えます。
    """
    lo = income_of(shotoku)
    hi = income_of(shotoku + 1_000)
    return 1_000 / (hi - lo) if hi > lo else 1.0


def recovery_widths(grade: str = "1級地",
                    heads_list: tuple[int, ...] = (1, 2, 3, 5, 7, 13)) -> list[dict]:
    """**稼ぐほど手取りが減る帯**の幅を、世帯人数ごとに並べる。

    谷そのものは「取られた住民税を取り返すまで」なので、
    **合計所得でいえば均等割の 5,000円ちょうど**です（単身・1級地だけ、
    所得割も同時に始まるので 6,316円）。
    ところが**年収でいうと、同じ 5,000円 が段によって化けます** ——
    給与所得控除の段で「合計所得の増える率」が 1.0 / 0.6 / 0.7 / 0.8 / 0.9 と
    変わるためで、**世帯人数そのものは1円も効いていません。**
    """
    rows = []
    for heads in heads_list:
        r = recovery(grade, heads)
        rate = marginal_income_rate(r["限度額"])
        rows.append({
            "級地": grade,
            "世帯の人数": heads,
            "限度額": r["限度額"],
            "限度額の年収": income_of(r["限度額"]),
            "合計所得での谷の幅": r["戻るのに要る増収"],
            "年収での谷の幅": r["年収での谷の幅"],
            "所得の増える率": rate,
            "式で出した年収の幅": round(r["戻るのに要る増収"] / rate),
        })
    return rows


def effective_rate_curve(taxables: list[int]) -> list[dict]:
    """課税所得べつ、所得割の**実効税率**。調整控除があるので10％にはなりません。"""
    rows = []
    for t in taxables:
        gross = round(t * SHOTOKUWARI_RATE)
        chosei = chosei_kojo(t)
        rows.append({
            "課税所得": t,
            "10パーセントを掛けただけ": gross,
            "調整控除": chosei,
            "所得割": max(0, gross - chosei),
            "実効の税率": (max(0, gross - chosei) / t * 100) if t else 0.0,
        })
    return rows


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(KINTOWARI_CITY, 3_000, "均等割の市町村民税（標準税率）",
                      source="地方税法310条")
    _checks.statutory(KINTOWARI_PREF, 1_000, "均等割の道府県民税（標準税率）",
                      source="地方税法38条")
    _checks.statutory(FOREST_TAX, 1_000, "森林環境税",
                      source="森林環境税及び森林環境譲与税に関する法律（2024年度から）")
    _checks.statutory(KINTOWARI_TOTAL, 5_000, "均等割としてまとめて納める額",
                      source="地方税法310条・38条＋森林環境税")
    _checks.statutory(BASIC_DEDUCTION, 430_000, "住民税の基礎控除",
                      source="地方税法314条の2")
    _checks.statutory(JINTEKI_DIFF_BASIC, 50_000, "基礎控除の人的控除の差",
                      source="所得税48万円と住民税43万円の差")
    _checks.statutory(KYUYO_MIN, 550_000, "給与所得控除の最低額",
                      source="所得税法28条3項（2020年分から）")
    _checks.ratio(SHOTOKUWARI_RATE, "所得割の標準税率")
    _checks.ratio(CHOSEI_RATE, "調整控除の率")

    # 2. 表の形。級地は 1→3 で下がる（1級地がいちばん高い）
    _checks.ascending([p for _n, p, _a in KINTOWARI_LIMITS][::-1],
                      "級地べつの1人あたりの額", strict=True)
    _checks.ascending([a for _n, _p, a in KINTOWARI_LIMITS][::-1],
                      "級地べつの扶養加算", strict=True)
    _checks.unique_by(KINTOWARI_LIMITS, lambda r: r[0], "級地区分")

    # 3. 給与収入と合計所得の行き来が、往復して元に戻ること。
    #    **帯ごとに、境目とその内側を必ず1点ずつ踏むこと**（2026-08-17）。
    #    最初に書いた6点は 162万5千円〜180万円 の帯を1点も踏んでおらず、
    #    **そこだけ符号が逆だったのを素通りさせました。**
    #    帯の切れ目は 162.5万 / 180万 / 360万 / 660万 / 850万 です
    for income in (550_000, 930_000, 1_000_000, 1_624_999, 1_625_000,
                   1_680_000, 1_700_000, 1_799_999, 1_800_000,
                   1_800_001, 2_057_143, 3_599_999, 3_600_000,
                   3_600_001, 5_000_000, 6_599_999, 6_600_000,
                   6_600_001, 8_499_999, 8_500_000, 8_500_001, 12_000_000):
        # **1円のずれは許します。** 給与所得控除を1円単位で丸めてから引くので、
        # 逆写像は原理的に1円ぶん決まりません（`rounding` は完全一致を要求するので
        # ここでは使えない）。**桁や符号の間違いは、これでも必ず落ちます**
        got = income_of(shotoku_of(income))
        if abs(got - income) > 1:
            raise _checks.TableError(
                f"給与収入{income:,}円の往復: {got:,} になった")
    # 往復が通るだけでは足りません（同じ向きに2回ずれても通るため）。
    # **給与収入が増えたら合計所得も増える**ことを、帯をまたいで見ます
    _checks.increases_with(shotoku_of,
                           (1_600_000, 1_700_000, 1_900_000, 4_000_000,
                            7_000_000, 9_000_000),
                           "給与収入が増えたのに合計所得が増えていない")
    _checks.increases_with(income_of,
                           (1_000_000, 1_100_000, 1_300_000, 2_000_000,
                            5_000_000, 7_000_000),
                           "合計所得が増えたのに、それを生む給与収入が増えていない")

    # 4. **主題その1**: 級地で境目がずれる。単身の均等割は
    #    1級地で年収100万円、3級地で93万円
    _checks.rounding(kintowari_limit("1級地", 1), 450_000, "1級地・単身の均等割の限度額")
    _checks.rounding(kintowari_limit("3級地", 1), 380_000, "3級地・単身の均等割の限度額")
    _checks.rounding(income_of(kintowari_limit("1級地", 1)), 1_000_000,
                     "1級地・単身の境目の年収")
    _checks.rounding(income_of(kintowari_limit("3級地", 1)), 930_000,
                     "3級地・単身の境目の年収")
    # 同じ年収95万円が、級地で課税と非課税に分かれること
    if tax(shotoku_of(950_000), "1級地", 1)["住民税"] != 0:
        raise _checks.TableError("1級地・単身・年収95万円で住民税が出ている")
    _checks.greater(tax(shotoku_of(950_000), "3級地", 1)["住民税"], 0,
                    "3級地・単身・年収95万円で住民税が0になっている")

    # 5. **主題その2**: 均等割だけがかかる帯。
    #    単身は0円、扶養が1人でもいれば1級地で11万円（人数によらず一定）
    if kintowari_only_band("1級地", 1)["帯の幅"] != 0:
        raise _checks.TableError(
            "1級地・単身で均等割だけの帯ができた。加算が無いので両方45万円のはず")
    for heads in (2, 3, 4, 5):
        band = kintowari_only_band("1級地", heads)
        _checks.rounding(band["帯の幅"], 110_000,
                         f"1級地・{heads}人の均等割だけの帯")
    # 3級地は「7万円 × 世帯人数 ＋ 15.2万円」で、人数とともに広がる
    for heads in (2, 3, 4, 5):
        band = kintowari_only_band("3級地", heads)
        _checks.rounding(band["帯の幅"], 70_000 * heads + 152_000,
                         f"3級地・{heads}人の均等割だけの帯")
    _checks.increases_with(lambda h: kintowari_only_band("3級地", h)["帯の幅"],
                           (2, 3, 4, 5),
                           "3級地で扶養が増えたのに均等割だけの帯が広がっていない")
    # 帯の中では、所得割が0円のまま均等割だけがかかること
    band = kintowari_only_band("1級地", 3)
    mid = (band["均等割の非課税限度額"] + band["所得割の非課税限度額"]) // 2
    inside = tax(mid, "1級地", 3)
    if inside["所得割"] != 0 or inside["均等割"] != KINTOWARI_TOTAL:
        raise _checks.TableError(
            f"均等割だけの帯の中なのに 所得割{inside['所得割']}円・"
            f"均等割{inside['均等割']}円 になっている")

    # 6. **主題その3**: 1円の崖。単身・1級地で6,000円
    c = cliff("1級地", 1)
    _checks.rounding(c["限度額での住民税"], 0, "限度額ちょうどの住民税")
    _checks.rounding(c["跳ぶ額"], 6_000, "1級地・単身で限度額を1円こえたときの住民税")
    _checks.rounding(c["うち均等割"], 5_000, "1円こえたときの均等割")
    _checks.rounding(c["うち所得割"], 1_000, "1円こえたときの所得割")
    _checks.rounding(c["調整控除で消えた額"], 1_000, "1円こえたときの調整控除")

    # 7. **主題その4**: 手取りが戻るまでの谷。
    #    増収 x のうち残るのは (1 − 実効の限界税率) なので、
    #    調整控除の折れ目より内側では 0.95x。6,000 ÷ 0.95 で 6,316円
    r = recovery("1級地", 1)
    _checks.rounding(r["戻るのに要る増収"], 6_316, "手取りが戻るのに要る増収")
    want = -(-6_000 // (1 - SHOTOKUWARI_RATE + CHOSEI_RATE))   # 天井まで切り上げ
    if r["戻るのに要る増収"] != want:
        raise _checks.TableError(
            f"数え上げ {r['戻るのに要る増収']}円 と式 {want}円 が一致しない")
    _checks.greater(r["限度額での手取り"], r["谷の底"],
                    "限度額を1円こえても手取りが減っていない（谷ができていない）")
    # 折れ目（課税所得5万円）より手前にいること。またぐと上の式が変わります
    if r["戻る点の合計所得"] - BASIC_DEDUCTION > JINTEKI_DIFF_BASIC:
        raise _checks.TableError(
            "戻る点が調整控除の折れ目を越えている。式のほうを見直すこと")

    # 7.5 **主題その6**: 谷の幅を決めているのは、世帯人数でも級地でもなく
    #     **給与所得控除のどの段に限度額が乗るか**（2026-08-17 に足した）。
    #     合計所得での幅は 5,000円（＝均等割）で動かないのに、年収でいうと
    #     5,000 / 5,556 / 6,250 / 7,143 / 8,333 の5通りに化けます。
    for grade in ("1級地", "2級地", "3級地"):
        for row in recovery_widths(grade, (2, 3, 4, 5, 7, 9, 13)):
            # 扶養がいれば、均等割の限度額のほうが必ず低いので、
            # **谷の中では所得割が0円のまま** ＝ 取り返す額は均等割ちょうど
            _checks.rounding(row["合計所得での谷の幅"], KINTOWARI_TOTAL,
                             f"{grade}・{row['世帯の人数']}人の合計所得での谷の幅")
            # 数え上げ（`recovery`）と、段の率から出した式が一致すること。
            # **1,000円ぶんで率を測っているので、数円のずれは許します**
            if abs(row["式で出した年収の幅"] - row["年収での谷の幅"]) > 5:
                raise _checks.TableError(
                    f"{grade}・{row['世帯の人数']}人: 数え上げ "
                    f"{row['年収での谷の幅']:,}円 と式 "
                    f"{row['式で出した年収の幅']:,}円 が一致しない")
    # 幅は5通りしか出ないこと（段の数だけ）
    seen = {r["年収での谷の幅"]
            for g in ("1級地", "2級地", "3級地")
            for r in recovery_widths(g, tuple(range(2, 16)))}
    if not seen <= {5_000, 5_556, 6_250, 7_143, 8_333}:
        raise _checks.TableError(f"見たことのない谷の幅が出た: {sorted(seen)}")
    # **人数について単調ではないこと。** ここが主題です ——
    # 単調なら「大きい世帯ほど谷が広い」と言えてしまい、
    # **段の話ではなく人数の話になります**（実測は 5,000 → 8,333 → 7,143）
    widths3 = [r["年収での谷の幅"] for r in recovery_widths("3級地", (2, 3, 4))]
    if widths3 != [5_000, 8_333, 7_143]:
        raise _checks.TableError(f"3級地の谷の幅が実測と違う: {widths3}")
    if widths3 == sorted(widths3):
        raise _checks.TableError(
            "谷の幅が人数について単調になっている。主題は段の話であって人数の話ではない")

    # 8. **主題その5**: 所得割は課税所得×10％ではない。
    #    課税所得5万円までは実効5％で、そこから10％へ近づく
    for taxable in (10_000, 20_000, 50_000):
        row = effective_rate_curve([taxable])[0]
        _checks.rounding(row["実効の税率"], 5.0,
                         f"課税所得{taxable:,}円の所得割の実効税率")
    _checks.increases_with(lambda t: effective_rate_curve([t])[0]["実効の税率"],
                           (50_000, 100_000, 500_000, 2_000_000),
                           "課税所得が増えたのに実効税率が上がっていない")
    top = effective_rate_curve([2_000_000])[0]["実効の税率"]
    _checks.greater(SHOTOKUWARI_RATE * 100, top,
                    "調整控除があるのに実効税率が標準税率に届いている")

    # 9. 所得が増えたら住民税は減らない（谷は手取りの話で、税額は単調）
    _checks.never_decreases(lambda s: tax(s, "1級地", 1)["住民税"],
                            (400_000, 450_000, 500_000, 1_000_000, 3_000_000),
                            "合計所得が増えたのに住民税が減っている")

    _checks.assumption_values(ASSUMPTIONS, name="juminzei")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 「住民税は年収100万円から」は1級地の話。3級地なら93万円から ===")
    for heads in (1, 2, 3):
        who = {1: "単身", 2: "扶養1人", 3: "扶養2人"}[heads]
        print(f"  {who}（世帯{heads}人）")
        for row in limits_by_grade(heads):
            print(f"    {row['級地']}  限度額 {row['均等割の非課税限度額']:>9,}円"
                  f"  年収でいうと {row['年収でいうと']:>10,}円"
                  f"  1級地との差 {row['1級地との差']:>7,}円"
                  f"（年収で {row['年収での差']:>8,}円）")
    lo = income_of(kintowari_limit("3級地", 1))
    hi = income_of(kintowari_limit("1級地", 1))
    print(f"  → 単身で年収 {lo:,}円 から {hi:,}円 のあいだにいる人は、"
          f"**住む市だけで課税と非課税が分かれます**")

    print("\n=== 所得割は0円のまま均等割5,000円だけを払う帯が、扶養がいると生まれる ===")
    for grade in ("1級地", "2級地", "3級地"):
        print(f"  {grade}")
        for heads in (1, 2, 3, 4):
            b = kintowari_only_band(grade, heads)
            width = b["帯の幅"]
            print(f"    世帯{heads}人  均等割 {b['均等割の非課税限度額']:>9,}円"
                  f" / 所得割 {b['所得割の非課税限度額']:>9,}円"
                  f"  帯の幅 {width:>8,}円"
                  f"  年収では {b['年収での下端']:>9,}〜{b['年収での上端']:>10,}円"
                  f"（{b['年収での帯の幅']:>8,}円）")
    print("  → **1級地では、扶養が何人いても帯は110,000円で一定**"
          "（加算の差 320,000円 − 210,000円）")
    print("    3級地は **70,000円 × 世帯人数 ＋ 152,000円** で、"
          "扶養が増えるほど広がります")

    print("\n=== 非課税限度額を1円こえると、住民税はいくら跳ぶか ===")
    for grade in ("1級地", "2級地", "3級地"):
        for heads in (1, 3):
            c = cliff(grade, heads)
            print(f"  {c['級地']}・世帯{c['世帯の人数']}人"
                  f"  限度額 {c['限度額']:>9,}円（年収 {c['年収でいうと']:>10,}円）"
                  f"  → 1円こえると {c['跳ぶ額']:>7,}円"
                  f"（均等割 {c['うち均等割']:,}円 ＋ 所得割 {c['うち所得割']:,}円）")
    c = cliff("1級地", 1)
    print(f"  → 所得割は 10パーセントを掛けると "
          f"{tax(c['限度額'] + 1)['調整控除の前']:,}円 ですが、"
          f"調整控除で {c['調整控除で消えた額']:,}円 消えて {c['うち所得割']:,}円 になります")

    print("\n=== 手取りが元に戻るまで、あといくら稼ぐ必要があるか（稼ぐほど減る帯）===")
    for grade in ("1級地", "2級地", "3級地"):
        r = recovery(grade, 1)
        print(f"  {r['級地']}・単身  限度額 {r['限度額']:>9,}円"
              f"  手取り {r['限度額での手取り']:>9,}円"
              f"  → 戻るのに あと {r['戻るのに要る増収']:>6,}円"
              f"（合計所得 {r['戻る点の合計所得']:>9,}円・"
              f"年収の谷の幅 {r['年収での谷の幅']:>6,}円）")
    r = recovery("1級地", 1)
    print(f"  → 谷の底は {r['谷の底']:,}円 で、"
          f"限度額ちょうどの {r['限度額での手取り']:,}円 より "
          f"{r['限度額での手取り'] - r['谷の底']:,}円 少なくなります")
    print(f"    増えたぶんのうち手元に残るのは "
          f"{(1 - SHOTOKUWARI_RATE + CHOSEI_RATE) * 100:.0f}パーセントなので、"
          f"5,000円の均等割と1,000円の所得割を取り返すのに 6,316円 かかります")

    print("\n=== 稼ぐほど減る帯の幅を決めているのは、世帯人数ではなく給与所得控除の段 ===")
    for grade in ("1級地", "3級地"):
        print(f"  {grade}")
        for row in recovery_widths(grade, (2, 3, 4, 5, 7, 9, 13)):
            print(f"    世帯{row['世帯の人数']:>2}人  限度額 {row['限度額']:>9,}円"
                  f"（年収 {row['限度額の年収']:>9,}円）"
                  f"  合計所得での谷 {row['合計所得での谷の幅']:>5,}円"
                  f"  → 年収での谷 {row['年収での谷の幅']:>5,}円"
                  f"（合計所得の増える率 {row['所得の増える率']:.1f}）")
    print(f"  → 取り返す額は、どの人数でも均等割の {KINTOWARI_TOTAL:,}円 ちょうどです"
          "（扶養がいれば、その帯では所得割が0円のままなので）")
    print("    それでも年収での幅が変わるのは、給与所得控除の段で"
          "**合計所得の増える率**が 1.0 / 0.6 / 0.7 / 0.8 / 0.9 と変わるためで、"
          "幅は 5,000 ÷ その率 です")
    print("    だから幅は 5,000／5,556／6,250／7,143／8,333円 の5通りしかなく、"
          "**人数について単調ですらありません**"
          "（3級地は 世帯2人 5,000円 → 3人 8,333円 → 4人 7,143円）")

    print("\n=== 所得割は「課税所得 × 10パーセント」ではない（調整控除の効き方）===")
    for row in effective_rate_curve([10_000, 20_000, 50_000, 100_000, 300_000,
                                     1_000_000, 2_000_000, 3_000_000]):
        print(f"  課税所得 {row['課税所得']:>10,}円"
              f"  10パーセントなら {row['10パーセントを掛けただけ']:>9,}円"
              f"  調整控除 {row['調整控除']:>7,}円"
              f"  → 所得割 {row['所得割']:>9,}円"
              f"  実効 {row['実効の税率']:>5.2f}パーセント")
    print("  → 課税所得が5万円までは、人的控除の差5万円がまるごと効くので"
          "**実効5パーセント**。そこから10パーセントへ近づきます")
