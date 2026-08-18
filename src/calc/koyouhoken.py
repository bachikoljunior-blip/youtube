"""**雇用保険料 —— 労使で同じ率ではないし、業種の差は労働者側には来ない。**

雇用保険料は労働者と事業主の両方が払う。一般の解説はここで止まる ——
「令和7年度は一般の事業で1.45パーセント」と合計の率を1つ並べて終わり。
**その1.45パーセントが、労使でどう割れているのかは表の外にある。**

労働者が負担するのは**失業等給付のぶんだけ**で、事業主はそれと同額に加えて
**雇用保険二事業**のぶんを上乗せで払う。ここで出しているのは、その割れ方と、
割れ方が業種でどう動くかです。

## 出たもの

**1. 事業主が払うのは労働者の 1.538倍から 1.692倍。合計の率の順番とは一致しない。**

    一般の事業         労働者 0.55% ／ 事業主 0.90%（合計 1.45%）  → **1.636倍**
    農林水産・清酒製造  労働者 0.65% ／ 事業主 1.00%（合計 1.65%）  → **1.538倍**
    建設               労働者 0.65% ／ 事業主 1.10%（合計 1.75%）  → **1.692倍**

合計の率は 1.45 → 1.65 → 1.75 と上がりますが、**倍率は 1.636 → 1.538 → 1.692 と
いったん下がって上がります。** 合計が重い業種ほど事業主に寄っている、とは言えません。

**2. 業種の差は、労働者側には同じだけしか来ない。**
一般の事業を基準にすると、労働者側の差はどちらの業種も **0.1ポイント**。
事業主側は農林水産が **0.1ポイント**、建設だけ **0.2ポイント**です。
**同じ「業種が違うと率が違う」でも、建設だけが事業主側で2倍**になります。

**3. 労使あわせた保険料の 21.2〜25.7パーセントは、失業給付には使われない。**
雇用保険二事業（雇用調整助成金など）は事業主だけが負担します。
事業主の負担の中では **35.0〜40.9パーセント**、労使あわせた中では
**21.2パーセント（農林水産）から 25.7パーセント（建設）**。
**払っている保険料の4分の1は、失業したときに戻ってくる側の勘定ではありません。**

**4. 月給30万円で、会社は本人より年 12,600円多く払っている。**
賞与4か月を足すと **16,800円**。月給100万円なら年 42,000円・賞与込みで 56,000円です。

**5. 50銭ちょうどは切り捨て、1厘超えると切り上げ。境目は月給301,000円。**

    月給 300,999円 → 1,655.4945円（49.45銭）→ **1,655円**
    月給 301,000円 → 1,655.5000円（**50.00銭**）→ **1,655円**（ちょうどは切り捨て）
    月給 301,001円 → 1,655.5055円（50.55銭）→ **1,656円**

**月給1円の差で、引かれる額が1円動きます。**

**6. 率は業種でちがうのに、前の年度から下がった額は3業種とも同額。**
令和6年度から令和7年度で失業等給付の率が 0.05ポイント下がりました。月給30万円なら
本人 1,800円・会社 1,800円・**労使あわせて年 3,600円**。
**3業種すべてで同じ額**です（下げ幅が全業種で同じ 0.05ポイントだから）。

**7. 厚生年金には上限があるのに、雇用保険料には上限が無い。**
厚生年金の本人負担は標準報酬月額65万円で頭打ちになりますが、雇用保険料は
総支給額にそのまま掛かります。だから比が動きます:

    月給 30万円  → 雇用保険は厚生年金の **6.01%**
    月給 65万円  → **6.01%**（ここまでは一定）
    月給200万円  → **18.50%**（**3.08倍**）

**上限のある保険と無い保険が並んでいるので、高い給与ほど雇用保険の比重が上がります。**

## 前提の置き方（ここが独自の視点です）

**率は令和7年度のものを置いています。** 雇用保険料率は年度ごとに変わるので、
ここで出した実額は「その年度の値を掛けたらこうなる」という形の数字です。
**月給は総支給額（通勤手当を含む）として置き、標準報酬のような等級には当てはめていません** ——
雇用保険料は等級ではなく実際の賃金に掛かるからです。
節7の厚生年金は比べるためだけに置いた値で、こちらは等級の上限（65万円）を使っています。
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP

from . import _checks

ASSUMPTIONS = [
    "雇用保険料率は令和7年度の値です。一般の事業は労働者0.55パーセント・事業主0.90パーセントで合計1.45パーセント、"
    "農林水産・清酒製造は0.65パーセントと1.00パーセントで合計1.65パーセント、"
    "建設は0.65パーセントと1.10パーセントで合計1.75パーセントとして置いています",
    "労働者が負担するのは失業等給付のぶんだけで、雇用保険二事業のぶんは事業主だけが負担します。"
    "二事業の率は一般の事業と農林水産が0.35パーセント、建設が0.45パーセントです",
    "前の年度として令和6年度の失業等給付の率を置いています。一般の事業0.60パーセント、"
    "農林水産と建設は0.70パーセントです。二事業の率は同じです",
    "月給は総支給額として置いています。標準報酬月額のような等級には当てはめていません。"
    "雇用保険料は等級ではなく実際に払われた賃金に掛かるからです",
    "労働者の負担額は、掛けた額の50銭以下を切り捨て、50銭を超えたら切り上げています",
    "比べるために置いた厚生年金は、本人負担9.15パーセント・標準報酬月額の上限65万円です",
    "入れていないもの: 賞与に掛かるぶんの端数処理、日雇労働被保険者、"
    "労災保険料（こちらは事業主だけが負担します）",
]

# ---- 制度の値（令和7年度の雇用保険料率。雇用保険法第66条・第68条）--------
# (業種, 失業等給付の率（労使それぞれ）, 雇用保険二事業の率（事業主だけ）)
GYOSHU: list[tuple[str, Decimal, Decimal]] = [
    ("一般の事業", Decimal("0.0055"), Decimal("0.0035")),
    ("農林水産・清酒製造", Decimal("0.0065"), Decimal("0.0035")),
    ("建設", Decimal("0.0065"), Decimal("0.0045")),
]

# 令和6年度（前の年度）の失業等給付の率。二事業の率は同じ
LAST_YEAR: dict[str, Decimal] = {
    "一般の事業": Decimal("0.0060"),
    "農林水産・清酒製造": Decimal("0.0070"),
    "建設": Decimal("0.0070"),
}


def _row(name: str) -> tuple[str, Decimal, Decimal]:
    for r in GYOSHU:
        if r[0] == name:
            return r
    raise ValueError(f"業種に無い: {name}")


def worker_rate(name: str) -> Decimal:
    """労働者負担の率（＝失業等給付のぶんだけ）。"""
    return _row(name)[1]


def employer_rate(name: str) -> Decimal:
    """事業主負担の率（失業等給付＋雇用保険二事業）。"""
    _, shitsugyo, nijigyo = _row(name)
    return shitsugyo + nijigyo


def total_rate(name: str) -> Decimal:
    return worker_rate(name) + employer_rate(name)


def worker_yen(wage: int, name: str = "一般の事業") -> int:
    """労働者が1か月に引かれる額。**50銭以下は切り捨て、50銭超は切り上げ**。"""
    x = Decimal(wage) * worker_rate(name)
    return int((x - Decimal("0.000001")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def employer_yen(wage: int, name: str = "一般の事業") -> int:
    x = Decimal(wage) * employer_rate(name)
    return int((x - Decimal("0.000001")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


# ---- 節1: 労使は同じ率ではない。差は業種で開く ---------------------------
def roushi() -> list[dict]:
    rows = []
    for name, _, _ in GYOSHU:
        w, e = worker_rate(name), employer_rate(name)
        rows.append({
            "業種": name,
            "労働者（パーセント）": float(w * 100),
            "事業主（パーセント）": float(e * 100),
            "合計（パーセント）": float((w + e) * 100),
            "事業主は労働者の何倍": round(float(e / w), 3),
        })
    return rows


# ---- 節2: 業種の差は、事業主側では2倍ひらく ------------------------------
def gyoshu_sa() -> list[dict]:
    base = "一般の事業"
    rows = []
    for name, _, _ in GYOSHU:
        if name == base:
            continue
        rows.append({
            "業種": name,
            "労働者の差（ポイント）": float((worker_rate(name) - worker_rate(base)) * 100),
            "事業主の差（ポイント）": float((employer_rate(name) - employer_rate(base)) * 100),
            "合計の差（ポイント）": float((total_rate(name) - total_rate(base)) * 100),
        })
    return rows


# ---- 節3: 事業主の払う保険料の何割が、給付ではなく二事業に行くか ----------
def nijigyo_share() -> list[dict]:
    rows = []
    for name, shitsugyo, nijigyo in GYOSHU:
        e = employer_rate(name)
        rows.append({
            "業種": name,
            "事業主の率（パーセント）": float(e * 100),
            "うち二事業（パーセント）": float(nijigyo * 100),
            "二事業の割合（パーセント）": round(float(nijigyo / e * 100), 1),
            "労使あわせた中の割合（パーセント）": round(
                float(nijigyo / total_rate(name) * 100), 1),
        })
    return rows


# ---- 節4: 月給べつの実額と、賞与を足したときの動き -----------------------
def gaku(name: str = "一般の事業") -> list[dict]:
    rows = []
    for wage in (200_000, 300_000, 400_000, 600_000, 1_000_000):
        w, e = worker_yen(wage, name), employer_yen(wage, name)
        rows.append({
            "月給（円）": wage,
            "労働者が引かれる（月・円）": w,
            "会社が払う（月・円）": e,
            "年12か月ぶんの差（円）": (e - w) * 12,
            "賞与4か月を足した年の差（円）": (e - w) * 16,
        })
    return rows


# ---- 節5: 端数の丸めは、月給1円の差で1円動く ----------------------------
def hasuu(name: str = "一般の事業", start: int = 300_000) -> list[dict]:
    """**50銭ちょうどは切り捨て、50銭を1厘でも超えると切り上げ。**

    `start` 以上で、端数がちょうど50銭になるいちばん小さい月給を探して、その前後を並べる。
    """
    rate = worker_rate(name)
    center = None
    for wage in range(start, start + 100_000):
        exact = Decimal(wage) * rate
        if (exact - int(exact)) * 100 == 50:
            center = wage
            break
    if center is None:
        raise ValueError(f"{name}: 端数50銭ちょうどの月給が見つからない")
    rows = []
    for wage in (center - 1, center, center + 1):
        exact = Decimal(wage) * rate
        rows.append({
            "月給（円）": wage,
            "掛けた額（円）": float(exact),
            "端数（銭）": float((exact - int(exact)) * 100),
            "引かれる額（円）": worker_yen(wage, name),
        })
    return rows


# ---- 節6: 前の年度からいくら下がったか ----------------------------------
def zennendo(wage: int = 300_000) -> list[dict]:
    rows = []
    for name, shitsugyo, nijigyo in GYOSHU:
        old_w = LAST_YEAR[name]
        old_e = old_w + nijigyo
        rows.append({
            "業種": name,
            "労働者の率（前年度→今年度・パーセント）":
                (float(old_w * 100), float(shitsugyo * 100)),
            "労働者の年の減り（円）": int((Decimal(wage) * (old_w - shitsugyo)) * 12),
            "会社の年の減り（円）": int((Decimal(wage) * (old_e - employer_rate(name))) * 12),
            "労使あわせた年の減り（円）": int(
                (Decimal(wage) * ((old_w + old_e) - total_rate(name))) * 12),
        })
    return rows


# ---- 節7: 上限が無いので、高い給与ほど額はそのまま伸びる -----------------
def jougen() -> list[dict]:
    """**厚生年金には標準報酬の上限があるが、雇用保険料には上限が無い。**"""
    rows = []
    kousei_cap = 650_000          # 厚生年金の標準報酬月額の上限（第32等級）
    kousei_rate = Decimal("0.0915")  # 厚生年金の本人負担（18.3パーセントの半分）
    for wage in (300_000, 650_000, 1_000_000, 2_000_000):
        koyou = worker_yen(wage)
        kousei = int(Decimal(min(wage, kousei_cap)) * kousei_rate)
        rows.append({
            "月給（円）": wage,
            "雇用保険（本人・円）": koyou,
            "厚生年金（本人・円）": kousei,
            "雇用保険が厚生年金に占める割合（パーセント）": round(koyou / kousei * 100, 2),
        })
    return rows


def check_tables() -> None:
    _checks.statutory(float(worker_rate("一般の事業")), 0.0055,
                      "一般の事業の労働者負担の率", source="雇用保険法第68条（令和7年度）")
    _checks.statutory(float(employer_rate("一般の事業")), 0.0090,
                      "一般の事業の事業主負担の率", source="雇用保険法第66条・第68条（令和7年度）")
    _checks.statutory(float(total_rate("建設")), 0.0175,
                      "建設の合計の率", source="令和7年度の雇用保険料率表")
    for name, _, _ in GYOSHU:
        _checks.ratio(float(worker_rate(name)), f"{name}の労働者負担の率")
        _checks.ratio(float(employer_rate(name)), f"{name}の事業主負担の率")
        # **事業主のほうが必ず重い**（二事業のぶんが乗るので）
        _checks.greater(float(employer_rate(name)), float(worker_rate(name)),
                        f"{name}で事業主負担が労働者負担以下")

    # 掛けた額は月給が増えれば増える
    _checks.increases_with(lambda w: worker_yen(w), [100_000, 300_000, 900_000],
                           "月給が増えたのに引かれる額が増えていない")
    # 端数: 50銭ちょうどは切り捨て、その1円上は切り上げ
    h = hasuu()
    _checks.rounding(h[1]["端数（銭）"], 50.0, "50銭ちょうどの行の端数")
    _checks.rounding(h[0]["引かれる額（円）"], h[1]["引かれる額（円）"],
                     "50銭ちょうどの行が、その1円下と同じ額になっていない")
    _checks.greater(h[2]["引かれる額（円）"], h[1]["引かれる額（円）"],
                    "50銭を超えたのに引かれる額が上がっていない")
    # 前年度より下がっている（上がった業種は無い）
    for r in zennendo():
        _checks.greater(r["労使あわせた年の減り（円）"], 0,
                        f"{r['業種']}で前年度より下がっていない")
    _checks.unique_by(roushi(), lambda r: r["業種"], "労使の表")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 雇用保険料は労使で同じ率ではない。事業主は何倍払っているか ===")
    for row in roushi():
        print(row)

    print("\n=== 業種の差は労働者側では同じ0.1ポイント、建設だけ事業主で2倍になる ===")
    for row in gyoshu_sa():
        print(row)

    print("\n=== 労使あわせた保険料の4分の1は、失業給付ではないところへ行く ===")
    for row in nijigyo_share():
        print(row)

    print("\n=== 月給べつに、引かれる額と会社が払う額はいくら離れるか ===")
    for row in gaku():
        print(row)

    print("\n=== 月給が1円ふえるだけで引かれる額が1円上がる、50銭の境目 ===")
    for row in hasuu():
        print(row)

    print("\n=== 率は業種でちがうのに、前の年度から下がった額は3業種とも同額 ===")
    for row in zennendo():
        print(row)

    print("\n=== 厚生年金には上限があるのに、雇用保険料には上限が無い ===")
    for row in jougen():
        print(row)
