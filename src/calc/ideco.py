"""**iDeCo の掛金は「税率ぶん戻る」とは限らない。最後の1万円ほど効きが落ちる。**

一般の解説はここで止まります ——「掛金は全額が所得控除。所得税率20パーセントの人なら
住民税10パーセントと合わせて掛金の30パーセントが戻る」。

**それは掛金の1円目の話です。** 所得控除は課税所得を**上から削る**ので、
掛金が所得税の区分の境目をまたぐと、**削った後半は1つ下の税率でしか効きません。**
年27万6000円を掛けた人の実効節税率は、**年収460万円で17.3パーセント、680万円で28.3パーセント**。
どちらも「税率＋10パーセント」（20.2／30.4パーセント）では出てこない数字です。
年収460万円の人は、**税率で計算した5万5779円ではなく4万7816円**しか戻りません。

そして、ずれる向きは**下**です。掛ける前の税率で計算すると必ず多めに出ます。

**この表はどこにも公開されていません。** 出回っているのは「税率べつの節税額」の
一覧で、税率は掛ける前のものを1つ選んで掛け算しているだけです。
ここでは `tedori.py` と同じ経路で**掛ける前と後の税額を2回計算し、その差**を出します。
区分をまたいだかどうかを気にしなくてよいのは、そのためです。

## この計算で見ないもの（前提として画面に出す）

- **運用益が非課税であること・受け取るときの課税**は入れていません。
  ここで出しているのは**掛けた年に戻る税金だけ**です。
- 掛金の上限は**職業と、勤め先に企業年金があるかで変わります**。
  3通りを並べ、どれがどの条件かを表に書いています。
- 所得控除は基礎控除だけです。扶養控除や生命保険料控除があると、
  もともとの課税所得が下がるので、**節税額はここより小さくなることがあります。**
"""
from __future__ import annotations

from . import _checks
from .furusato import (BASIC_INCOME, BASIC_RESIDENT, RESIDENT_RATE,
                       TYPICAL_SOCIAL_RATE, income_tax_rate, salary_deduction)
from .tedori import income_tax

ASSUMPTIONS = [
    "給与収入のみの人を想定しています。事業所得や不動産所得があると変わります",
    "所得控除は基礎控除だけで計算しています。扶養控除や保険料控除があると、節税額はここより小さくなります",
    "社会保険料は年収の15パーセントとして置いています。実際は標準報酬月額の等級で階段状に動きます",
    "住民税の所得割は標準税率の10パーセントです。均等割は定額なので掛金では動きません",
    "所得税には復興特別所得税を含めています（1.021倍）",
    "戻るのは掛けた年の所得税と翌年度の住民税です。運用でふえた分や、受け取るときの税金は入れていません",
    "掛金の上限は職業と、勤め先の企業年金の有無で変わります。会社員で企業年金がない場合は月2万3000円です",
    "掛金は年の途中で変えられるため、ここでは1年ぶんを満額かけた場合で計算しています",
]

# ---- 制度の値。**長く動いていないものだけを置く** ----------------------
# 拠出限度額は月額。年額は12倍（`CAPS` の第2要素）。
# 会社員（企業年金なし）2万3000円・公務員および企業年金がある会社員2万円・
# 自営業（第1号被保険者）6万8000円。**公務員が2万円になったのは2024年12月から。**
CAPS: list[tuple[str, int, str]] = [
    ("自営業", 68_000, "第1号被保険者。国民年金基金の掛金と合わせて月6万8000円"),
    ("会社員（企業年金なし）", 23_000, "勤め先に確定給付年金も企業型DCも無い場合"),
    ("公務員・企業年金あり", 20_000, "2024年12月から月2万円。それ以前は公務員は月1万2000円"),
]

MONTHS = 12
SALARIED_CAP = 23_000 * MONTHS   # 年27万6000円。表の主役
SELF_CAP = 68_000 * MONTHS       # 年81万6000円


def _taxable(income: int, extra: int, *, resident: bool,
             social_rate: float) -> int:
    """課税所得。`extra` が小規模企業共済等掛金控除（iDeCo の掛金）。"""
    basic = BASIC_RESIDENT if resident else BASIC_INCOME
    social = int(income * social_rate)
    return max(0, income - salary_deduction(income) - social - basic - extra)


def taxes(income: int, premium: int = 0,
          social_rate: float = TYPICAL_SOCIAL_RATE) -> dict:
    """掛金を引いた後の所得税と住民税。**引く前と後で2回呼んで、差を取る。**"""
    it = income_tax(_taxable(income, premium, resident=False,
                             social_rate=social_rate))
    rt = int(_taxable(income, premium, resident=True,
                      social_rate=social_rate) * RESIDENT_RATE)
    return {"所得税": it, "住民税": rt, "合計": it + rt}


def saving(income: int, premium: int,
           social_rate: float = TYPICAL_SOCIAL_RATE) -> dict:
    """掛金でいくら税が減るか。**掛ける前の税率を掛け算しない。**

    区分をまたいだかどうかを気にしなくてよいのは、税額を2回計算しているためです。
    """
    before = taxes(income, 0, social_rate)
    after = taxes(income, premium, social_rate)
    cut = before["合計"] - after["合計"]
    naive_rate = income_tax_rate(
        _taxable(income, 0, resident=False, social_rate=social_rate))
    return {
        "年収": income,
        "掛金": premium,
        "所得税の減り": before["所得税"] - after["所得税"],
        "住民税の減り": before["住民税"] - after["住民税"],
        "節税額": cut,
        "実効節税率": cut / premium if premium else 0.0,
        "掛ける前の税率で見た額": int(premium * (naive_rate * 1.021 + RESIDENT_RATE)),
    }


def grid(premium: int = SALARIED_CAP,
         incomes: tuple[int, ...] = (3_000_000, 4_000_000, 4_600_000,
                                     4_800_000, 5_000_000, 6_600_000,
                                     6_800_000, 8_000_000)) -> list[dict]:
    """年収べつ。**主役は「実効節税率」の列**（税率＋10%にならない）。"""
    return [saving(income, premium) for income in incomes]


def last_step(income: int, premium: int = SALARIED_CAP,
              step: int = 12_000) -> list[dict]:
    """掛金を `step` ずつ積んだとき、**その1段が何円の節税になったか。**

    後半の段のほうが安くなる年収がある、というのがこの表の主題です。
    """
    rows, prev = [], 0
    paid = 0
    while paid < premium:
        paid = min(paid + step, premium)
        cut = saving(income, paid)["節税額"]
        rows.append({"掛金の累計": paid, "節税額": cut,
                     "この1段ぶん": cut - prev,
                     "この1段の効き": (cut - prev) / step})
        prev = cut
    return rows


#: またぐ年収を探すときの標本。**画面に出す前提そのもの**なので、
#: `__main__` 側で `range(...)` を書き直さないこと ——
#: 書き直すと、上端が `12,000,001`（range が終端を含まないぶん）になり、
#: **画面に出ていない数字で計算していることになります**（`src/premise.py` が落とします）。
SCAN_INCOMES = tuple(range(3_000_000, 12_000_001, 100_000))


def cliff_incomes(premium: int = SALARIED_CAP) -> list[dict]:
    """**掛金が区分をまたぐ年収**だけを拾う（1段目と最終段の効きが違う行）。"""
    out = []
    for income in SCAN_INCOMES:
        rows = last_step(income, premium)
        first, last = rows[0]["この1段の効き"], rows[-1]["この1段の効き"]
        # **0.005 は丸めの幅です。** 1e-9 で見ると、またいでいない年収も
        # 円未満の切り捨てで拾ってしまい、表が「またいだ年収の一覧」でなくなります
        if abs(first - last) > 0.005:
            out.append({"年収": income, "最初の1段": first, "最後の1段": last,
                        "実効節税率": saving(income, premium)["実効節税率"]})
    return out


#: 復興特別所得税の係数（所得税額 × 2.1%）。**住民税には掛かりません。**
RECON = 1.021


def straddle_bands(premium: int = SALARIED_CAP,
                   step: int = 12_000) -> list[dict]:
    """`cliff_incomes()` を**帯にまとめる**。

    またぐ年収は連続した1本の帯ではなく、**離れた島**として現れます。
    掛金 `premium` が所得税の区分の境目をまたぐのは、
    **課税所得が境目のすぐ上 `premium` 円ぶんに入っているとき**だけだからです。

    各帯について返すもの:

        帯の下端 / 帯の上端 / 点の数
        いちばん深い年収          … その帯で「最初の1段」と「最後の1段」の差が最大の年収
        落ち幅                    … その差（率）
        またいだ所得税率の段差    … 落ち幅 ÷ 1.021（住民税10%は定率なので差では消える）

    **帯の端は「途中まで」です。** 掛金の一部しか境目を越えないので落ち幅が浅く出ます
    （実測: 年収650万は 4.17pt で、同じ帯の中の最大 10.21pt に届かない）。
    だから帯の性質は**端ではなく最大**で見ること。
    """
    rows = cliff_incomes(premium)
    bands: list[list[dict]] = []
    prev_income = None
    for row in rows:
        if prev_income is None or row["年収"] - prev_income != 100_000:
            bands.append([])
        bands[-1].append(row)
        prev_income = row["年収"]

    out = []
    for band in bands:
        deepest = max(band, key=lambda r: r["最初の1段"] - r["最後の1段"])
        gap = deepest["最初の1段"] - deepest["最後の1段"]
        out.append({
            "帯の下端": band[0]["年収"],
            "帯の上端": band[-1]["年収"],
            "点の数": len(band),
            "いちばん深い年収": deepest["年収"],
            "落ち幅": gap,
            "またいだ所得税率の段差": gap / RECON,
            "最初の1段の円": int(deepest["最初の1段"] * step),
            "最後の1段の円": int(deepest["最後の1段"] * step),
            "倍率": deepest["最初の1段"] / deepest["最後の1段"],
        })
    return out


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(SALARIED_CAP, 276_000, "会社員（企業年金なし）の年間拠出限度額",
                      source="確定拠出年金法施行令 第36条")
    _checks.statutory(SELF_CAP, 816_000, "第1号被保険者の年間拠出限度額",
                      source="確定拠出年金法施行令 第36条")
    _checks.digits(SALARIED_CAP, 100_000, 1_000_000, "会社員の年間拠出限度額")
    _checks.unique_by(CAPS, lambda r: r[0], "拠出限度額の表")
    for name, monthly, _cond in CAPS:
        _checks.digits(monthly, 10_000, 100_000, f"{name}の月額限度額")

    # 2. 計算の向き —— この計算の主題そのもの
    #    (a) 掛金が増えれば節税額も増える（減ることはありえない）
    _checks.never_decreases(
        lambda p: saving(6_000_000, p)["節税額"],
        (12_000, 60_000, 120_000, 240_000, SALARIED_CAP),
        "掛金を増やしたのに節税額が減っている")
    #    (b) 年収が上がれば、同じ掛金でも節税額は減らない（税率が上がる側）
    _checks.never_decreases(
        lambda y: saving(y, SALARIED_CAP)["節税額"],
        (3_000_000, 5_000_000, 7_000_000, 10_000_000),
        "年収が上がったのに、同じ掛金の節税額が減っている")
    #    (c) **この計算の核**: 掛ける前の税率で出した額は、実額を下回らない。
    #        上から削るので、またいだぶんだけ実額のほうが小さくなる
    #        **許容は2円**。所得税と住民税をそれぞれ円未満で切り捨てているので、
    #        差には最大2円の丸めが乗ります。ここを 0 にすると、またいでいない年収が
    #        1円の丸めで落ちます（実際に落ちました）。**2円を超える超過はまたぎ**
    #        ではなく計算の誤りなので、そちらは通しません
    for income in (3_000_000, 4_000_000, 5_000_000, 6_000_000,
                   7_000_000, 8_000_000, 10_000_000):
        r = saving(income, SALARIED_CAP)
        naive = SALARIED_CAP * (income_tax_rate(
            _taxable(income, 0, resident=False,
                     social_rate=TYPICAL_SOCIAL_RATE)) * 1.021 + RESIDENT_RATE)
        _checks.greater(naive + 2, r["節税額"],
                        f"年収{income:,}円で、掛ける前の税率で出した額が実額を下回った")
    #    (d) 実効節税率は 0 と 1 のあいだ（桁の取り違えを弾く）
    for income in (3_000_000, 6_000_000, 10_000_000):
        _checks.ratio(saving(income, SALARIED_CAP)["実効節税率"], f"年収{income:,}円の実効節税率")
    #    (e) またぐ年収が実在すること。**無ければこの動画の主題そのものが消えます**
    if not cliff_incomes():
        raise _checks.TableError(
            "掛金が区分をまたぐ年収が1つも見つからない。主題が成立していない")
    #    (f) **落ち幅は、またいだ所得税率の段差そのもの**（住民税10%は定率なので差では消える）。
    #        数え上げ（`last_step` の実額）と、式（税率の段差 × 1.021）が独立に一致すること。
    #        **許容 0.02ポイント**は、1段 12,000円を円未満で切り捨てるぶん（0.6円ぶん）。
    #        ここを 0 にすると、切り捨てだけで落ちます。
    for band in straddle_bands():
        implied = band["またいだ所得税率の段差"] * 100
        nearest = min((5.0, 10.0, 3.0, 13.0, 7.0, 5.0),
                      key=lambda r: abs(r - implied))
        _checks.close(implied, nearest, tol=0.02,
                      what=f"年収{band['いちばん深い年収']:,}円の落ち幅が、"
                           "所得税率の段差に還元できない")
    #    (g) **いちばん深い帯は真ん中**（10%→20% の段差が所得税でいちばん大きい）。
    #        端でないことがこの節の主題なので、崩れたら台本を書かせない。
    bands = straddle_bands()
    if len(bands) >= 3:
        depths = [b["落ち幅"] for b in bands]
        if max(depths) != max(depths[1:-1]):
            raise _checks.TableError(
                "落ち幅がいちばん大きい帯が、端に移った。"
                f"（帯ごとの落ち幅 {['%.4f' % d for d in depths]}）")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 会社員が満額かけたときの実効節税率は、税率＋10%にならない ===")
    for row in grid():
        print(f"  年収{row['年収']:>10,}円  節税{row['節税額']:>8,}円"
              f"  実効{row['実効節税率']*100:5.1f}%"
              f"  （税率で出すと {row['掛ける前の税率で見た額']:,}円）")

    print("\n=== 掛金の最後の1万2000円は、最初の1万2000円より安く効く年収がある ===")
    # **年収を必ず印字すること**（2026-08-17。`src/premise.py` が落とします）。
    # 20.2%→15.1% の落ち方は所得税率の境目に乗るかで決まるので、
    # **年収が画面に無いと、視聴者は追試も自分への当てはめもできません。**
    print(f"  前提の年収 {4_600_000:,}円（会社員・企業年金なし）")
    for row in last_step(4_600_000):
        print(f"  累計{row['掛金の累計']:>8,}円  この1段 {row['この1段ぶん']:>6,}円"
              f"  効き {row['この1段の効き']*100:5.1f}%")

    print("\n=== 掛金が所得税の区分をまたぐ年収（最初の1段と最後の1段で効きが違う） ===")
    for row in cliff_incomes():
        print(f"  年収{row['年収']:>10,}円  最初 {row['最初の1段']*100:5.1f}%"
              f"  最後 {row['最後の1段']*100:5.1f}%"
              f"  ならすと {row['実効節税率']*100:5.1f}%")

    print("\n=== 自営業（年81万6000円）と会社員（年27万6000円）の差 ===")
    for income in (4_000_000, 6_000_000, 8_000_000, 10_000_000):
        a = saving(income, SALARIED_CAP)
        b = saving(income, SELF_CAP)
        print(f"  年収{income:>10,}円  会社員 {a['節税額']:>8,}円"
              f"  自営業 {b['節税額']:>8,}円"
              f"  差 {b['節税額']-a['節税額']:>8,}円"
              f"（{b['節税額']/a['節税額']:.2f}倍）")

    print("\n=== 「掛けるほど効きが落ちる」年収は、91点のうち11点しかない ===")
    # **年収を必ず印字すること**（`src/premise.py` が落とします）。
    _hit = cliff_incomes()
    print(f"  年収 {SCAN_INCOMES[0]:,}円〜{SCAN_INCOMES[-1]:,}円を"
          f"{SCAN_INCOMES[1]-SCAN_INCOMES[0]:,}円きざみで {len(SCAN_INCOMES)}点みて、"
          f"またぐのは {len(_hit)}点（{len(_hit)/len(SCAN_INCOMES)*100:.1f}%）")
    for row in straddle_bands():
        print(f"  帯 年収{row['帯の下端']:>10,}〜{row['帯の上端']:,}円"
              f"（{row['点の数']}点・幅 {row['帯の上端']-row['帯の下端']:,}円）")
    print("  → **残りの年収では、1円目も最後の1円も同じ率で効きます。**"
          "掛金 276,000円が境目をまたげる年収が、その幅しかないため")

    print("\n=== 効きの落ち幅がいちばん大きいのは、いちばん高い年収ではなく真ん中 ===")
    print(f"  前提: 会社員・企業年金なし／掛金 年{SALARIED_CAP:,}円／1段 {12_000:,}円")
    for row in straddle_bands():
        print(f"  年収{row['いちばん深い年収']:>10,}円"
              f"  最初の1段 {row['最初の1段の円']:>6,}円"
              f"  最後の1段 {row['最後の1段の円']:>6,}円"
              f"  {row['倍率']:.3f}倍"
              f"（またいだ所得税率の段差 {row['またいだ所得税率の段差']*100:.0f}ポイント）")
    print("  → **落ち幅は、またいだ所得税率の段差 × 1.021 そのもの。**"
          "住民税10%は定率なので差では消え、**年収にも掛金の額にもよりません**")
    print("  → 所得税の段差は 5→10→20→23→33→40→45%。"
          "**いちばん大きい段差は 10→20% の10ポイント**なので、"
          "年収660万台がいちばん深く、**年収1,110万台は3ポイントでいちばん浅い**")

    print("\n=== 所得税がほとんど戻らない年収でも、住民税ぶんは残る ===")
    for income in (1_500_000, 2_000_000, 2_500_000, 3_000_000, 3_500_000):
        r = saving(income, SALARIED_CAP)
        print(f"  年収{income:>10,}円  所得税 {r['所得税の減り']:>7,}円"
              f"  住民税 {r['住民税の減り']:>7,}円  合計 {r['節税額']:>8,}円")
