"""高年齢雇用継続基本給付金。**上下の限度額が、片方の帯にしか効かない。**

一般の解説はここで止まります ——「60歳以降の賃金が75パーセント未満に下がったら、
賃金の最大10パーセントが出ます」。**率と境目までは、どこにでも書いてあります。**

ここから先を計算しました。

1. **支給限度額 370,452円は、この制度では一度も効きません。**
   賃金月額の上限 486,300円 × 0.75 = 364,725円 が「賃金＋給付」の構造上の最大で、
   **限度額に 5,727円 届きません。** 限度額のほうが高い所に置かれています。
2. **最低限度額 2,295円は、逆に本物の崖を作ります。**
   賃金を1円上げると給付 2,295円が丸ごと消える点があり、
   **元の総額に戻るまでに 2,294円の賃上げが要ります。**
   ただしこの崖も、61パーセント以下の帯には構造的に届きません
   （賃金月額の下限 82,380円 の10パーセント ＝ 8,238円 が既に 2,295円 を超えているため）。
3. **給付を最大にもらう賃金にすると、5年で必ず損をします。**
   給付が最大になるのは低下率ちょうど61パーセントですが、
   60歳到達時 40万円の人で **給付 +146万円に対し、賃金 −336万円。差引 −190万円**です。
4. **2025年4月の 15→10パーセント で、いちばん損をしたのは「ちょうど61パーセント」の人。**
   減額幅は 60歳到達時賃金の 3.05パーセントで頭打ちになり、
   **61パーセントより下でも上でも、損は小さくなります。**
5. **60歳到達時賃金の上限 486,300円 が、下がり幅の順序をひっくり返します。**
   賃金が 56パーセント下がった人の給付が、39パーセントしか下がっていない人の
   **3.8分の1**になる組み合わせが実在します（6,415円 対 24,400円）。

**前提と式は全部この画面に出します。** 誰でも同じ数字に行き着けます。
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "2025年4月1日以降に60歳になった人の支給率で計算します。最大10パーセントです。"
    "それより前に60歳になった人は最大15パーセントで、この計算とは別になります",
    "限度額は2024年8月1日改定の額を使います。"
    "支給限度額は370,452円、最低限度額は2,295円、"
    "60歳到達時の賃金月額は上限486,300円・下限82,380円です。"
    "これらは毎年8月1日に改定されるので、実際に申請する年の額を確かめてください",
    "賃金は月額で、賞与は入れていません。残業代や通勤手当は賃金に含めて考えます",
    "支給額は円未満を切り捨てて計算しています",
    "受給できる期間は60歳から65歳になるまでの最大5年間、60か月として計算します",
    "税と社会保険料は入れていません。給付金そのものは非課税ですが、"
    "賃金のほうには税と保険料がかかるので、手取りで見ると差はこの計算より小さくなります",
    "在職老齢年金との併給調整は入れていません。"
    "60歳台前半の老齢厚生年金を受けている人は、この給付とは別に年金が止まることがあります",
]

# ---- 制度の値（雇用保険法第61条、および厚生労働省の公表資料）----------------
RATE_MAX = 0.10          # 2025年4月1日以降に60歳到達。最大の支給率
RATE_MAX_OLD = 0.15      # それ以前。比較のために置いてある
LOW = 0.61               # この低下率以下は、賃金にそのまま最大率が掛かる
HIGH = 0.75              # この低下率以上は不支給

W60_CAP = 486_300        # 60歳到達時賃金月額の上限（2024年8月1日〜）
W60_FLOOR = 82_380       # 同・下限
PAY_LIMIT = 370_452      # 支給限度額。賃金＋給付がこれを超えたぶんは出ない
MIN_PAY = 2_295          # 最低限度額。給付がこれ未満なら1円も出ない

MONTHS = 60              # 60歳から65歳まで


def slope(rate_max: float = RATE_MAX) -> float:
    """低下率 61〜75パーセントの帯で、賃金1円あたり給付が減る量。

    帯の両端で連続するように決まっているので、率から一意に出ます
    （61パーセントで `rate_max × 0.61 × 賃金月額`、75パーセントで 0）。
    """
    return rate_max * LOW / (HIGH - LOW)


def capped_w60(w60: float) -> float:
    """60歳到達時の賃金月額に、上限と下限を掛ける。"""
    return min(max(w60, W60_FLOOR), W60_CAP)


def raw_benefit(wage: float, w60: float, rate_max: float = RATE_MAX) -> float:
    """限度額を掛ける前の給付額。**帯が3つあります。**"""
    base = capped_w60(w60)
    ratio = wage / base
    if ratio >= HIGH:
        return 0.0
    if ratio <= LOW:
        return rate_max * wage
    return slope(rate_max) * (HIGH * base - wage)


def benefit(wage: float, w60: float, rate_max: float = RATE_MAX) -> int:
    """実際に出る給付額（円）。上下の限度額を掛けてから切り捨てる。"""
    if wage >= PAY_LIMIT:
        return 0
    got = min(raw_benefit(wage, w60, rate_max), PAY_LIMIT - wage)
    if got < MIN_PAY:
        return 0
    return int(got)


def total(wage: float, w60: float, rate_max: float = RATE_MAX) -> int:
    """賃金＋給付。**この制度で手元に入る月額です。**"""
    return int(wage) + benefit(wage, w60, rate_max)


def keep_rate(w60: float, ratio: float) -> float:
    """低下率を `ratio` にしたとき、賃金の下げ幅の何割が給付で戻るか。

    比べる相手は「75パーセントちょうど（給付が0になる直前）」です。
    """
    base = capped_w60(w60)
    high_wage = HIGH * base
    wage = ratio * base
    cut = high_wage - wage
    if cut <= 0:
        return 0.0
    return benefit(wage, base) / cut


def max_total(w60: float) -> int:
    """その人にとって、賃金＋給付が最大になる額。**帯をまたいで探す。**"""
    base = capped_w60(w60)
    best = 0
    for step in range(0, int(HIGH * base) + 1, 1_000):
        best = max(best, total(step, base))
    for wage in range(max(0, int(HIGH * base) - 20_000), int(HIGH * base) + 1):
        best = max(best, total(wage, base))
    return best


def cliff_wage(w60: float) -> int:
    """給付が最低限度額に届かなくなる、いちばん高い賃金（＝崖の上の1円下）。

    ここから賃金を1円上げると、給付 2,295円 以上が丸ごと 0円になります。
    """
    base = capped_w60(w60)
    for wage in range(int(HIGH * base), int(LOW * base), -1):
        if benefit(wage, base) > 0:
            return wage
    raise ValueError(f"崖が見つからない: w60={w60}")


def best_benefit_wage(w60: float) -> int:
    """給付だけを最大にする賃金。**低下率ちょうど61パーセントです。**"""
    return int(LOW * capped_w60(w60))


def five_year(wage: float, w60: float, rate_max: float = RATE_MAX) -> int:
    """60か月ぶんの給付の総額。"""
    return benefit(wage, w60, rate_max) * MONTHS


def grid(w60: float = 400_000) -> list[dict]:
    """低下率ごとの給付と総額。図解がそのまま食える形。"""
    rows = []
    base = capped_w60(w60)
    for pct in (50, 55, 61, 65, 70, 74, 75, 80):
        wage = int(base * pct / 100)
        rows.append({
            "低下率": pct,
            "賃金": wage,
            "給付": benefit(wage, base),
            "賃金と給付の合計": total(wage, base),
        })
    return rows


def reform_loss(w60: float) -> list[dict]:
    """15パーセントから10パーセントへの改正で、月いくら減ったか。"""
    base = capped_w60(w60)
    rows = []
    for pct in (50, 55, 61, 65, 70, 74):
        wage = int(base * pct / 100)
        rows.append({
            "低下率": pct,
            "賃金": wage,
            "改正前の給付": benefit(wage, base, RATE_MAX_OLD),
            "改正後の給付": benefit(wage, base, RATE_MAX),
            "減った額": benefit(wage, base, RATE_MAX_OLD) - benefit(wage, base, RATE_MAX),
        })
    return rows


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令・公表資料が名指ししている値
    _checks.statutory(RATE_MAX, 0.10, "最大の支給率（2025年4月以降に60歳到達）",
                      source="雇用保険法第61条・2020年改正")
    _checks.statutory(LOW, 0.61, "最大率が掛かる低下率の上端",
                      source="雇用保険法第61条")
    _checks.statutory(HIGH, 0.75, "不支給になる低下率",
                      source="雇用保険法第61条")
    _checks.statutory(PAY_LIMIT, 370_452, "支給限度額",
                      source="2024年8月1日改定")
    _checks.statutory(MIN_PAY, 2_295, "最低限度額", source="2024年8月1日改定")
    _checks.statutory(W60_CAP, 486_300, "賃金月額の上限", source="2024年8月1日改定")
    _checks.ratio(RATE_MAX, "最大の支給率")
    _checks.ratio(LOW, "最大率が掛かる低下率の上端")
    _checks.ratio(HIGH, "不支給になる低下率")

    # 2. 帯の継ぎ目が連続していること（傾きは率から一意に決まる）
    base = 400_000
    edge = LOW * base
    _checks.rounding(raw_benefit(edge - 1, base), RATE_MAX * (edge - 1),
                     "61パーセントのすぐ下の給付")
    _checks.rounding(raw_benefit(edge + 1, base),
                     slope() * (HIGH * base - (edge + 1)),
                     "61パーセントのすぐ上の給付")
    if abs(raw_benefit(edge - 1, base) - raw_benefit(edge + 1, base)) > 2:
        raise _checks.TableError("61パーセントの継ぎ目で給付が飛んでいる")
    if raw_benefit(HIGH * base - 1, base) > slope() + 1:
        raise _checks.TableError("75パーセントのすぐ下で給付が0に向かっていない")
    # 公表されている係数（改正前 183/280・改正後 122/280）と一致すること。
    # **この一致が、傾きを手で置いていない証拠**です（率と境目だけから出しています）。
    _checks.close(slope(RATE_MAX_OLD), 183 / 280, "改正前の傾き")
    _checks.close(slope(RATE_MAX), 122 / 280, "改正後の傾き")

    # 3. 主張1: 支給限度額は構造上いちども効かない
    ceiling = int(HIGH * W60_CAP)
    _checks.greater(PAY_LIMIT, ceiling,
                    "支給限度額が「賃金＋給付」の構造上の最大以下になっている")
    if max_total(W60_CAP) >= PAY_LIMIT:
        raise _checks.TableError(
            f"賃金＋給付の最大 {max_total(W60_CAP):,d}円 が支給限度額に届いている")

    # 4. 主張2: 最低限度額は61パーセント以下の帯には届かない
    _checks.greater(RATE_MAX * W60_FLOOR, MIN_PAY,
                    "賃金月額の下限に最大率を掛けた額が最低限度額以下")
    # そして 61〜75 の帯には本物の崖がある
    for w60 in (300_000, 400_000, 486_300):
        c = cliff_wage(w60)
        if benefit(c, w60) < MIN_PAY:
            raise _checks.TableError(f"崖の上で給付が最低限度額未満: w60={w60}")
        if benefit(c + 1, w60) != 0:
            raise _checks.TableError(f"崖の1円上で給付が0円になっていない: w60={w60}")
        if total(c + 1, w60) >= total(c, w60):
            raise _checks.TableError(f"崖の1円上で総額が減っていない: w60={w60}")
        # 元の総額に戻るには、給付とほぼ同額の賃上げが要る
        need = total(c, w60) - c
        if total(c + need, w60) < total(c, w60):
            raise _checks.TableError(f"給付ぶん賃上げしても総額が戻らない: w60={w60}")

    # 5. 主張3: 給付を最大にする賃金だと、5年で必ず損をする
    for w60 in (250_000, 400_000, 486_300):
        b = best_benefit_wage(w60)
        h = int(HIGH * capped_w60(w60))
        gain = five_year(b, w60) - five_year(h, w60)
        loss = (h - b) * MONTHS
        _checks.greater(loss, gain,
                        f"給付の増えぶんが賃金の減りぶん以上（w60={w60}）")
    # 給付だけを見れば、最大は 61 パーセントちょうど
    for w60 in (300_000, 400_000):
        b = best_benefit_wage(w60)
        _checks.greater(benefit(b, w60), benefit(b - 10_000, w60),
                        f"61パーセントの給付が、その下より多くない（w60={w60}）")
        _checks.greater(benefit(b, w60), benefit(b + 10_000, w60),
                        f"61パーセントの給付が、その上より多くない（w60={w60}）")

    # 6. 主張4: 改正の減額幅は 61 パーセントで最大になり、率で頭打ち
    for w60 in (300_000, 400_000, 486_300):
        base_w = capped_w60(w60)
        losses = {r["低下率"]: r["減った額"] for r in reform_loss(w60)}
        peak = max(losses, key=lambda k: losses[k])
        if peak != 61:
            raise _checks.TableError(
                f"改正の減額が61パーセントで最大になっていない（w60={w60}・実際は{peak}）")
        _checks.close(losses[61] / base_w, (RATE_MAX_OLD - RATE_MAX) * LOW,
                      f"61パーセントでの減額の、賃金月額に対する比（w60={w60}）",
                      tol=1e-6)

    # 7. 総額は賃金について単調に増える（＝賃金を下げて得になる帯は無い）
    _checks.never_decreases(lambda w: total(w, 400_000),
                            list(range(100_000, 300_001, 10_000)),
                            "賃金を上げたのに賃金＋給付が減っている")

    # 8. 表の行が一意
    _checks.unique_by(grid(), lambda r: r["低下率"], "低下率ごとの表")
    _checks.unique_by(reform_loss(400_000), lambda r: r["低下率"], "改正の表")

    _checks.assumption_values(ASSUMPTIONS, name="koureikoyou")


if __name__ == "__main__":
    check_tables()

    W = 400_000

    print("=== 支給限度額370,452円は、この制度では一度も効かない ===")
    print("高年齢雇用継続給付には「支給限度額」があります。")
    print("賃金と給付の合計がこの額を超えたら、超えたぶんは出ない、という上限です。")
    print(f"  支給限度額                          {PAY_LIMIT:9,d}円")
    print(f"  60歳到達時の賃金月額の上限          {W60_CAP:9,d}円")
    print(f"  給付が出る賃金の上端（その75パーセント） {int(HIGH * W60_CAP):9,d}円")
    print(f"  → 賃金＋給付の、構造上の最大        **{max_total(W60_CAP):9,d}円**")
    print(f"  **限度額まで {PAY_LIMIT - max_total(W60_CAP):,d}円 足りません。**")
    print("  賃金がこれ以上だと低下率が75パーセント以上になって不支給になるので、")
    print("  **合計が限度額に届く組み合わせが1つも存在しません。**")
    print("  限度額は「効かない高さ」に置かれた上限だ、ということです。")

    print()
    print("=== 最低限度額2,295円のほうは、本物の崖を作る ===")
    print("同じ限度額でも、下のほうは効きます。給付が2,295円未満だと1円も出ません。")
    print("低下率が75パーセントに近づくと給付は0に向かって落ちるので、")
    print("**途中で「2,295円が丸ごと消える1円」があります。**")
    for w60 in (300_000, 400_000, W60_CAP):
        c = cliff_wage(w60)
        print(f"  60歳到達時 {w60:7,d}円 → 賃金 {c:7,d}円で給付 {benefit(c, w60):5,d}円、"
              f"{c + 1:7,d}円で **{benefit(c + 1, w60):d}円**")
        print(f"      合計 {total(c, w60):7,d}円 → {total(c + 1, w60):7,d}円 "
              f"（**賃金を1円上げて {total(c, w60) - total(c + 1, w60):,d}円 減る**）")
        print(f"      元の合計に戻るには、そこから **{total(c, w60) - c - 1:,d}円** の賃上げが要ります")
    print(f"  → ところが、61パーセント以下の帯にはこの崖が来ません。")
    print(f"     賃金月額の下限 {W60_FLOOR:,d}円 に10パーセントを掛けても "
          f"{int(RATE_MAX * W60_FLOOR):,d}円 で、")
    print(f"     もう最低限度額 {MIN_PAY:,d}円 を超えているからです。")
    print("     **上の限度額はどの帯にも効かず、下の限度額は片方の帯にしか効かない。**")

    print()
    print("=== 賃金を下げたとき、下げ幅の何割が給付で戻るのか ===")
    print(f"60歳到達時の賃金を {W:,d}円 として、75パーセント（給付ゼロの直前）から")
    print("どこまで下げるかで、戻ってくる割合が変わります。")
    for pct in (74, 70, 65, 61, 55, 50):
        wage = int(W * pct / 100)
        cut = int(HIGH * W) - wage
        print(f"  低下率 {pct}パーセント（賃金 {wage:7,d}円）: "
              f"下げ幅 {cut:7,d}円 に対し給付 {benefit(wage, W):6,d}円"
              f" → **{keep_rate(W, pct / 100) * 100:4.1f}パーセント戻る**")
    print(f"  → 61パーセントまでは、下げ幅の **{slope() * 100:.1f}パーセント** が一定で戻ります。")
    print("     この帯では、賃金を1円下げても手元は0.56円しか減りません。")
    print("     61パーセントを下回ると、給付も賃金に比例して減り始めるので、")
    print("     **戻る割合はそこから落ちていきます。** 61パーセントが折り返しです。")

    print()
    print("=== 給付を最大にもらう賃金にすると、5年で必ず損をする ===")
    print("給付だけを見れば、いちばん多くもらえるのは低下率ちょうど61パーセントです。")
    print("そこを狙うといくら損をするのかを、60か月ぶんで計算しました。")
    for w60 in (250_000, 300_000, 400_000, W60_CAP):
        b = best_benefit_wage(w60)
        h = int(HIGH * capped_w60(w60))
        gain = five_year(b, w60) - five_year(h, w60)
        loss = (h - b) * MONTHS
        print(f"  60歳到達時 {w60:7,d}円:")
        print(f"    75パーセント（{h:7,d}円）で5年働く → 賃金 {h * MONTHS:11,d}円 ＋ 給付 "
              f"{five_year(h, w60):9,d}円 ＝ {(h * MONTHS + five_year(h, w60)):11,d}円")
        print(f"    61パーセント（{b:7,d}円）で5年働く → 賃金 {b * MONTHS:11,d}円 ＋ 給付 "
              f"{five_year(b, w60):9,d}円 ＝ {(b * MONTHS + five_year(b, w60)):11,d}円")
        print(f"    → 給付は **+{gain:,d}円** 増えるが、賃金は **−{loss:,d}円**。"
              f" 差引 **{gain - loss:,d}円**")
    print("  → 給付は最大でも賃金の10パーセントなので、")
    print("     **賃金を下げて給付を取りに行く形は、どの賃金でも成立しません。**")
    print("     この制度は「下げてでも働き続けられるようにする」ためのもので、")
    print("     **下げたほうが得になるようには作られていない**ということです。")

    print()
    print("=== 15パーセントが10パーセントになって、いちばん損をしたのは誰か ===")
    print("2025年4月1日以降に60歳になった人から、最大の支給率が15→10パーセントになりました。")
    print(f"60歳到達時の賃金 {W:,d}円 で、月にいくら減ったのかを並べます。")
    for r in reform_loss(W):
        print(f"  低下率 {r['低下率']:2d}パーセント（賃金 {r['賃金']:7,d}円）: "
              f"{r['改正前の給付']:6,d}円 → {r['改正後の給付']:6,d}円"
              f"（**−{r['減った額']:5,d}円/月**・5年で −{r['減った額'] * MONTHS:,d}円）")
    peak = max(reform_loss(W), key=lambda r: r["減った額"])
    print(f"  → 減額が最大になるのは **低下率ちょうど61パーセント**。"
          f"月 {peak['減った額']:,d}円 です。")
    print(f"     これは60歳到達時賃金の "
          f"**{(RATE_MAX_OLD - RATE_MAX) * LOW * 100:.2f}パーセント** で、"
          f"賃金月額の上限 {W60_CAP:,d}円 でも "
          f"月 {int((RATE_MAX_OLD - RATE_MAX) * LOW * W60_CAP):,d}円 が上限です。")
    print("     **61パーセントより下げても、上げても、損は小さくなります。**")
    print("     いちばん制度に沿って賃金を決めた人が、いちばん減らされた形です。")

    print()
    print("=== 60歳到達時賃金の上限が、下がり幅の順序をひっくり返す ===")
    print(f"低下率の分母は、実際の賃金ではなく上限 {W60_CAP:,d}円 で頭打ちになります。")
    print("だから元の賃金が高い人ほど、実際の下がり幅より低下率が浅く見えます。")
    cases = [(400_000, 244_000), (800_000, 350_000), (600_000, 300_000), (486_300, 296_000)]
    for w60, wage in cases:
        real = wage / w60
        seen = wage / capped_w60(w60)
        print(f"  60歳到達時 {w60:7,d}円 → いま {wage:7,d}円:")
        print(f"    実際の低下率 {real * 100:5.1f}パーセント / "
              f"制度が見る低下率 **{seen * 100:5.1f}パーセント** → 給付 **{benefit(wage, w60):6,d}円**")
    a = benefit(244_000, 400_000)
    b = benefit(350_000, 800_000)
    print(f"  → 賃金が {(1 - 350_000 / 800_000) * 100:.0f}パーセント下がった人の給付が {b:,d}円、")
    print(f"     {(1 - 244_000 / 400_000) * 100:.0f}パーセントしか下がっていない人の給付が {a:,d}円。")
    print(f"     **下がり幅が大きいほうが、{a / b:.1f}分の1**です。")
    print("     上限は高い賃金への給付を抑えるために置かれていますが、")
    print("     **結果として「大きく下がった人ほど出ない」向きにも効いています。**")
