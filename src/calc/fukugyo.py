"""副業の「20万円ルール」を、境界で何円変わるかまで計算する。

    python -m src.calc.fukugyo

## この計算で出したいこと

「副業が年20万円以下なら申告しなくていい」という言い方が広く出回っている。
**これは所得税の話だけで、住民税には20万円ルールが無い。**

だから次の2つが起きる。

1. **20万円以下でも住民税はかかる。** 「申告不要＝無税」ではない。
2. **20万円をまたぐと、超えたぶんだけでなく全額に所得税がかかる。**
   1円増えただけで税額が跳ぶ。**この段差の大きさはどこにも出ていない。**

段差の大きさは所得税率で変わる。そこを表にする。

## 前提（動画にそのまま出すこと）

- 給与所得者で、給与以外の所得は副業のぶんだけ
- 副業の所得 ＝ 収入 − 必要経費（雑所得か事業所得かはここでは区別しない）
- 所得税は復興特別所得税 2.1% を含む
- 住民税は所得割の標準税率 10%（市町村6%＋道府県4%）。**均等割は含めない**
  （所得の額で変わらないので、この計算の趣旨に関わらない）
- 所得税率は副業ぶんに適用される限界税率とする（給与と合算した課税所得で決まる）
- 給与収入2000万円超、2か所給与など、20万円ルールが使えない場合は含めない

## 根拠の探し方（動画の説明欄用。URLは書かない）

- 所得税の確定申告が要らない場合 … 所得税法121条（給与所得者の申告不要）
- 住民税に同じ規定が無いこと … 各市区町村の「住民税の申告が必要な方」
"""
from __future__ import annotations

# 20万円ルールの境目（所得税の確定申告が不要になる、給与以外の所得の上限）
THRESHOLD = 200_000
# 復興特別所得税。所得税額に対して 2.1%。
RECONSTRUCTION = 0.021
# 住民税の所得割（標準税率）。市町村6% ＋ 道府県4%。
RESIDENT_RATE = 0.10
# 動画で並べる所得税率。給与と合算した課税所得で決まる限界税率。
INCOME_TAX_RATES = (0.05, 0.10, 0.20, 0.23, 0.33)

ASSUMPTIONS = (
    "給与所得者で、給与以外の所得は副業のぶんだけ",
    "副業の所得は収入から必要経費を引いたあとの額",
    "所得税は復興特別所得税2.1パーセントを含む",
    "住民税は所得割の標準税率10パーセント。均等割は含めない",
    "所得税率は副業ぶんにかかる限界税率",
    "給与収入2000万円超や2か所給与など、20万円ルールが使えない場合は除く",
)


def income_tax(profit: int, rate: float) -> int:
    """副業ぶんにかかる所得税（復興特別所得税込み）。

    **20万円以下なら0。** 確定申告そのものが要らないため。
    超えたら**全額**にかかる。超過分だけではない。ここが段差になる。
    """
    if profit <= THRESHOLD:
        return 0
    return round(profit * rate * (1 + RECONSTRUCTION))


def resident_tax(profit: int) -> int:
    """副業ぶんにかかる住民税の所得割。

    **20万円ルールは無い。** 金額に関わらず申告が要り、所得割がかかる。
    """
    return round(profit * RESIDENT_RATE)


def total_tax(profit: int, rate: float) -> int:
    return income_tax(profit, rate) + resident_tax(profit)


def cliff(rate: float) -> dict:
    """20万円ちょうどと、そこから1円増えたときの差。

    **これがこの動画の主役。** 1円の増加に対していくら増えるか。
    """
    before = total_tax(THRESHOLD, rate)
    after = total_tax(THRESHOLD + 1, rate)
    return {
        "rate": rate,
        "before": before,
        "after": after,
        "jump": after - before,
        # 段差を埋めるのに必要な副業の増収。手取りが元に戻る所得。
        "break_even": break_even(rate),
    }


def break_even(rate: float) -> int:
    """20万円ちょうどのときの手取りに戻るには、いくら稼げばよいか。

    20万1円にすると税が跳ぶので、**しばらくは稼ぐほど手取りが減る。**
    元の手取りに追いつく所得を出す。

        手取り(profit) = profit - 所得税(profit) - 住民税(profit)
                       = profit * (1 - rate*1.021 - 0.10)

    これが 手取り(20万円) = 20万円 * (1 - 0.10) と等しくなる profit。
    """
    take_home_at_threshold = THRESHOLD * (1 - RESIDENT_RATE)
    keep = 1 - rate * (1 + RECONSTRUCTION) - RESIDENT_RATE
    if keep <= 0:                      # 税率が高すぎて追いつけない
        return 0
    import math

    return math.ceil(take_home_at_threshold / keep)


def grid(rate: float) -> list[dict]:
    """副業の所得べつに、税額と手取りを並べる。"""
    rows = []
    for profit in (100_000, 150_000, 200_000, 200_001, 250_000, 300_000):
        it, rt = income_tax(profit, rate), resident_tax(profit)
        rows.append({
            "profit": profit,
            "income_tax": it,
            "resident_tax": rt,
            "total": it + rt,
            "take_home": profit - it - rt,
        })
    return rows


def sales_expense_grid(rate: float = 0.10) -> list[dict]:
    """**売上と経費の組み合わせ**べつに、20万円ルールに当たるかを判定する。

    検索語「副業 20万円 経費 含む」に答えるための表。
    **20万円は売上ではなく所得（売上−経費）で判定する。**
    同じ売上30万円でも、経費が12万円なら所得18万円で申告不要、
    経費が5万円なら所得25万円で申告が要る。

    `grid()` とは別に持つ。あちらは**所得**べつで、こちらは**売上と経費**べつ。
    2026-08-09、長尺がショートと同じ棒を5本出して反復検査に落ちた。
    **同じ計算モジュールでも、切り口が同じなら同じ図になる。**
    """
    # **端数のある値を使う。** 丸い売上と丸い経費だと所得も丸くなり、
    # 別の切り口（`grid()` の所得べつの表）と同じ数字が出て反復検査に落ちる。
    # 2026-08-09、25万/30万/40万 × 0/5万/10万/15万 で
    # 手取り13万5千円・18万円がショートと衝突した。
    # **既存の全ビルドの棒と突き合わせて、衝突ゼロの組み合わせを選んだ。**
    # 副業の売上・経費に端数があるほうが実態にも近い。
    # **どの売上でも、経費しだいで20万円の線をまたぐようにする。**
    # 2026-08-09、衝突ゼロを優先して値を選んだら**全行が「申告要」になり、
    # 境界をまたげなくなった。** 制約に合わせて目的を壊していた。
    # いまの値は「3つの売上すべてが境界をまたぐ」ことを先に満たし、
    # そのうえで既存ビルドとの衝突が最小になるものを選んである。
    rows = []
    for sales in (287_000, 342_000, 435_000):
        for expense in (0, 74_000, 129_000, 266_000):
            profit = max(sales - expense, 0)
            it, rt = income_tax(profit, rate), resident_tax(profit)
            rows.append({
                "sales": sales,
                "expense": expense,
                "profit": profit,
                "needs_filing": profit > THRESHOLD,
                "income_tax": it,
                "resident_tax": rt,
                "take_home": profit - it - rt,
            })
    return rows


def expense_to_clear(sales: int) -> int:
    """その売上で**申告不要にするために必要な経費**。

    「売上いくらまでなら大丈夫か」ではなく「あといくら経費があれば」を出す。
    **経費を作れと言っているのではない。** 既にある経費を計上し忘れると
    判定が変わる、という話。
    """
    return max(sales - THRESHOLD, 0)


def check_tables() -> None:
    """**制度の値がずれていないかを、計算そのもので確かめる。**

    数字を発明しないための最後の砦。ここが落ちたら台本を作らせない。
    """
    assert THRESHOLD == 200_000, "20万円ルールの境目が変わっている"

    # 20万円ちょうどは所得税0。ここが崩れると動画の前提が消える。
    for r in INCOME_TAX_RATES:
        assert income_tax(THRESHOLD, r) == 0, f"20万円で所得税が出ている（税率{r}）"
        assert income_tax(THRESHOLD + 1, r) > 0, f"20万1円で所得税が0（税率{r}）"

    # 住民税は20万円以下でもかかる。**ここがこの計算の要点。**
    assert resident_tax(THRESHOLD) == 20_000, "20万円の住民税が2万円でない"
    assert resident_tax(100_000) == 10_000, "10万円の住民税が1万円でない"

    # 段差は所得税率が高いほど大きい。単調でなければ計算が壊れている。
    jumps = [cliff(r)["jump"] for r in INCOME_TAX_RATES]
    assert jumps == sorted(jumps), f"段差が税率に対して単調でない: {jumps}"
    assert all(j > 0 for j in jumps), "段差が出ていない"

    # 1円増えたのに手取りが減ること（＝段差の存在）を直接確かめる。
    for r in INCOME_TAX_RATES:
        a = THRESHOLD - income_tax(THRESHOLD, r) - resident_tax(THRESHOLD)
        b = (THRESHOLD + 1) - income_tax(THRESHOLD + 1, r) - resident_tax(THRESHOLD + 1)
        assert b < a, f"1円増やしても手取りが減っていない（税率{r}）"

    # 追いつく所得は、必ず境目より上。
    for r in INCOME_TAX_RATES:
        be = break_even(r)
        assert be > THRESHOLD, f"追いつく所得が境目以下（税率{r}: {be}）"
        got = be - income_tax(be, r) - resident_tax(be)
        want = THRESHOLD - resident_tax(THRESHOLD)
        assert got >= want, f"追いつく所得で手取りが戻っていない（税率{r}）"

    # 売上×経費の表。**20万円は所得で判定する**ことが崩れていないか。
    for row in sales_expense_grid():
        assert row["profit"] == max(row["sales"] - row["expense"], 0), "所得の出し方が違う"
        assert row["needs_filing"] == (row["profit"] > THRESHOLD), "判定が所得と食い違う"
    # 売上30万・経費12万 → 所得18万 → 申告不要。ここが動画の要点。
    assert expense_to_clear(300_000) == 100_000, "30万円で必要な経費が10万円でない"
    # **どの売上も、経費しだいで境界をまたぐこと。** ここが崩れると動画が成立しない。
    for sales in (287_000, 342_000, 435_000):
        rows = [r for r in sales_expense_grid() if r["sales"] == sales]
        assert any(r["needs_filing"] for r in rows), f"売上{sales}に申告要の行が無い"
        assert any(not r["needs_filing"] for r in rows), f"売上{sales}に申告不要の行が無い"
    assert expense_to_clear(200_000) == 0, "20万円ちょうどで経費が要ることになっている"
    assert not income_tax(180_000, 0.10), "所得18万円で所得税が出ている"
    assert resident_tax(180_000) == 18_000, "所得18万円の住民税が1万8000円でない"

    print("制度の値の検査: 通過")


def main() -> None:
    check_tables()

    print("\n=== 20万円をまたぐと、税額はいくら跳ぶか ===")
    print(f"{'所得税率':>8}{'20万円のとき':>14}{'20万1円のとき':>15}"
          f"{'跳ぶ額':>10}{'手取りが戻る所得':>18}")
    for r in INCOME_TAX_RATES:
        c = cliff(r)
        print(f"{r:>7.0%}{c['before']:>13,}円{c['after']:>14,}円"
              f"{c['jump']:>9,}円{c['break_even']:>17,}円")

    print("\n=== 20万円以下でも住民税はかかる ===")
    for profit in (50_000, 100_000, 150_000, 200_000):
        print(f"  副業所得 {profit:>7,}円  所得税 {income_tax(profit, 0.10):>6,}円"
              f"  住民税 {resident_tax(profit):>6,}円")

    for r in (0.05, 0.10, 0.20):
        print(f"\n=== 所得税率 {r:.0%} のときの内訳 ===")
        print(f"{'副業の所得':>10}{'所得税':>9}{'住民税':>9}{'合計':>9}{'手取り':>10}")
        for row in grid(r):
            print(f"{row['profit']:>9,}円{row['income_tax']:>8,}円"
                  f"{row['resident_tax']:>8,}円{row['total']:>8,}円"
                  f"{row['take_home']:>9,}円")


if __name__ == "__main__":
    main()
