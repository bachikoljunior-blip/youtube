"""再就職手当の「崖」が、基本手当の何日分にあたるかを計算する。

狙いは制度の解説ではない。「支給残日数が3分の1以上で60パーセント、
3分の2以上で70パーセント」という条文は、どこにでも書いてある。

ここで出したいのは **どこにも表になっていない数字** ——
**その境目を1日またぐと、いくら消えるのか**を、
所定給付日数のすべての区分について並べた表。

--------------------------------------------------------------------------
なぜこの題材か
--------------------------------------------------------------------------
再就職手当は「早く決まった人への報奨」と説明される。
ところが**報奨の額は、残っている日数に比例する**ので、
**決まるのが1日遅れるたびに減っていく**。減り方は連続ではなく、
**2か所で階段状に落ちる**（3分の2の線と、3分の1の線）。

一般の解説はここで止まる。止まる理由は、
**落差が「所定給付日数」ごとに違う**からで、8区分ぶん計算しないと表にならない。

--------------------------------------------------------------------------
金額ではなく「基本手当の何日分」で出している理由
--------------------------------------------------------------------------
再就職手当には、基本手当日額とは**別の上限額**があり、
これは毎年8月1日に改定される。**その年の値の裏が取れないので使わない。**

代わりに全部を **「基本手当の何日分か」** という単位で出す。
この単位なら**上限額が改定されても答えが変わらない**ので、
去年の値で書かれた記事のように、ある日を境にずれることがない。
視聴者は自分の基本手当日額を掛けるだけでよい。

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
雇用保険法 56条の3         就業促進手当（再就職手当）。支給残日数の要件と給付率。
雇用保険法 22条・23条       所定給付日数。年齢と算定基礎期間で決まる。

--------------------------------------------------------------------------
この計算で「使わない」もの
--------------------------------------------------------------------------
就業促進定着手当（再就職後の賃金が下がったときの上乗せ）は、
上限率の裏が取れていないので入れていない。**入れれば答えは上振れする側**なので、
ここで出す損失は「少なくともこれだけは消える」という下限になる。
"""
from __future__ import annotations

from . import _checks

# 動画と説明欄にそのまま出す前提。
ASSUMPTIONS = [
    "再就職手当は雇用保険法56条の3どおり、支給残日数が所定給付日数の3分の1以上のときに支給されるものとして置いています",
    "給付率は、支給残日数が所定給付日数の3分の2以上なら70パーセント、"
    "3分の1以上3分の2未満なら60パーセント、3分の1未満なら0パーセントです",
    "金額ではなく「基本手当の何日分か」で出しています。"
    "再就職手当には基本手当日額とは別の上限額があり、毎年8月1日に改定されるためです",
    "所定給付日数は雇用保険法22条・23条の別表のうち、実際に現れる8つの日数"
    "（90日、120日、150日、180日、210日、240日、270日、330日）を使っています",
    "就業促進定着手当、給付制限期間、待期期間、就職困難者の別表は入れていません",
    "再就職後の賃金は入れていません。ここで比べているのは、雇用保険から受け取る分だけです",
]

# ---- 制度の値。**長く動いていないものだけをここに置く** ----------------
# 雇用保険法56条の3。給付率は平成29年1月1日から変わっていない。
RATE_HIGH = 0.70          # 支給残日数が所定給付日数の 2/3 以上
RATE_LOW = 0.60           # 支給残日数が所定給付日数の 1/3 以上 2/3 未満
THRESHOLD_HIGH = 2 / 3    # 上の線
THRESHOLD_LOW = 1 / 3     # 下の線

# 雇用保険法22条・23条の別表に実際に現れる所定給付日数（自己都合・会社都合の両方）。
# **すべて3で割り切れる**ので、2つの線はちょうど整数日に来る。
PRESCRIBED_DAYS = [90, 120, 150, 180, 210, 240, 270, 330]

# 自己都合・定年など（年齢によらない）と、倒産・解雇など（45歳以上60歳未満が最長）。
DAYS_VOLUNTARY_MAX = 150
DAYS_INVOLUNTARY_MAX = 330


def rate_of(remaining: int, prescribed: int) -> float:
    """支給残日数から給付率を出す。**この関数がこの計算の全部**。"""
    if remaining >= prescribed * THRESHOLD_HIGH:
        return RATE_HIGH
    if remaining >= prescribed * THRESHOLD_LOW:
        return RATE_LOW
    return 0.0


def benefit_days(remaining: int, prescribed: int) -> float:
    """再就職手当を「基本手当の何日分か」で返す。"""
    return remaining * rate_of(remaining, prescribed)


def total_days(remaining: int, prescribed: int) -> float:
    """雇用保険から受け取る合計を「基本手当の何日分か」で返す。

    既に受け取った基本手当（所定給付日数 − 支給残日数）と、再就職手当の合計。
    """
    return (prescribed - remaining) + benefit_days(remaining, prescribed)


def cliff_low(prescribed: int) -> float:
    """下の線（3分の1）を1日またいだときに消える日数分。"""
    k = round(prescribed * THRESHOLD_LOW)
    return benefit_days(k, prescribed) - benefit_days(k - 1, prescribed)


def cliff_high(prescribed: int) -> float:
    """上の線（3分の2）を1日またいだときに消える日数分。"""
    k = round(prescribed * THRESHOLD_HIGH)
    return benefit_days(k, prescribed) - benefit_days(k - 1, prescribed)


def cliff_ratio_formula(prescribed: int) -> float:
    """崖の比を、数え上げずに式で出す。**数え上げと独立に一致することを検査する。**

    下の崖 = 0.6 × (d/3)                      = d/5
    上の崖 = 0.7 × (2d/3) − 0.6 × (2d/3 − 1)  = d/15 + 0.6
    比     = (d/5) ÷ (d/15 + 0.6)             = 3d / (d + 9)

    **9 は 0.6 ÷ (1/15)**、つまり「上の線では1日ぶんの残日数も一緒に失う」ことから出る。
    比は d が大きくなるほど3に近づくが、**どの区分でも3には届かない。**
    """
    return 3 * prescribed / (prescribed + 9)


def grid() -> list[dict]:
    """図解の元になる表。所定給付日数ごとの、2つの崖の深さ。"""
    rows = []
    for d in PRESCRIBED_DAYS:
        low = cliff_low(d)
        high = cliff_high(d)
        rows.append({
            "所定給付日数": d,
            "下の線の日": round(d * THRESHOLD_LOW),
            "下の崖": round(low, 1),
            "上の線の日": round(d * THRESHOLD_HIGH),
            "上の崖": round(high, 1),
            "崖の比": round(low / high, 2),
        })
    return rows


def loss_per_day(prescribed: int) -> dict:
    """1日遅く決まるごとに、雇用保険からの受取が何日分減るか（線の上では一定）。"""
    return {
        "70パーセントの帯": round(1 - RATE_HIGH, 2),
        "60パーセントの帯": round(1 - RATE_LOW, 2),
        "所定給付日数": prescribed,
    }


def day_price_multiple(prescribed: int) -> dict:
    """線の1日は、平常の1日の何倍の値段か。

    平常の1日に失うのは (1 − 給付率) 日分だけ。線の日はそれが崖ぶんに跳ね上がる。
    **受給期間のうち、この値段になる日は2日しかない。**
    """
    return {
        "上の線": cliff_high(prescribed) / (1 - RATE_HIGH),
        "下の線": cliff_low(prescribed) / (1 - RATE_LOW),
    }



def same_remaining(remaining: int = 100) -> list[dict]:
    """**支給残日数が同じでも、所定給付日数の区分がちがうと給付率が割れる。**

    給付率を決めているのは残日数そのものではなく、`残日数 ÷ 所定給付日数` です。
    だから**同じ「あと100日ある」人でも、区分が上のほうが率が低くなります。**
    """
    rows = []
    for d in PRESCRIBED_DAYS:
        if remaining > d:
            continue
        rows.append({
            "支給残日数": remaining,
            "所定給付日数": d,
            "残日数の割合": remaining / d,
            "給付率": rate_of(remaining, d),
            "再就職手当": round(benefit_days(remaining, d), 1),
            "受け取り済み": d - remaining,
            "合計": round(total_days(remaining, d), 1),
        })
    return rows


def rate_drop_points(remaining: int = 100) -> list[dict]:
    """同じ残日数で、**率が1段下がる最初の区分**を区分ごとに並べる。"""
    out = []
    prev: float | None = None
    for row in same_remaining(remaining):
        out.append({**row, "前の区分から下がったか": prev is not None and row["給付率"] < prev})
        prev = row["給付率"]
    return out


def cross_class(fast: int = 90) -> list[dict]:
    """**区分をまたぐと、待った人のほうが再就職手当が多くなる。**

    `fast` 日の区分で**1日も受給せずに決めた人**（残日数＝所定給付日数）と、
    各区分で**下の線（3分の1）ちょうど**まで受給してから決めた人を比べます。
    """
    base = benefit_days(fast, fast)
    rows = []
    for d in PRESCRIBED_DAYS:
        k = round(d * THRESHOLD_LOW)
        got = benefit_days(k, d)
        rows.append({
            "即決の区分": fast,
            "即決の再就職手当": round(base, 1),
            "所定給付日数": d,
            "下の線の残日数": k,
            "受給してから決めた日数": d - k,
            "再就職手当": round(got, 1),
            "差": round(got - base, 1),
            "追い越したか": got > base,
        })
    return rows


def cross_class_first(fast: int = 90) -> int | None:
    """`cross_class` で、**最初に追い越す所定給付日数**。"""
    for row in cross_class(fast):
        if row["追い越したか"]:
            return row["所定給付日数"]
    return None


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""

    # --- 2026-08-20 に足した節ぶん ------------------------------------------
    # (p) **主題**: 同じ残日数でも、区分が上がると給付率は下がるか同じ（上がらない）
    rows = same_remaining(100)
    if len(rows) < 3:
        raise _checks.TableError("残日数100日で比べられる区分が3つ未満（PRESCRIBED_DAYS が変わった）")
    _checks.never_decreases(lambda i: -rows[int(i)]["給付率"], list(range(len(rows))),
                            "区分が上がったのに給付率が上がっている")
    # 実際に1段下がる区分が少なくとも1つある（＝主張が空でない）
    if not any(r["前の区分から下がったか"] for r in rate_drop_points(100)):
        raise _checks.TableError("残日数100日で、率が下がる区分が1つも無い（主題が成り立たない）")
    # 率が下がっても、合計（受け取り済み＋再就職手当）は増える。**逆転するのは手当のほうだけ**
    _checks.never_decreases(lambda i: rows[int(i)]["合計"], list(range(len(rows))),
                            "区分が上がったのに、雇用保険からの合計が減っている")
    # (q) **主題**: 区分をまたぐと、待った人が即決の人を追い越す
    first = cross_class_first(90)
    if first is None:
        raise _checks.TableError("下の線まで待って 90日区分の即決を追い越す区分が1つも無い")
    for row in cross_class(90):
        want = row["再就職手当"] > row["即決の再就職手当"]
        if row["追い越したか"] != want:
            raise _checks.TableError(f"追い越し判定が合わない: {row}")
        if row["所定給付日数"] >= first and not row["追い越したか"]:
            raise _checks.TableError(
                f"{first}日 で追い越したのに、{row['所定給付日数']}日 で追い越していない")
    # 即決の額は「所定給付日数 × 70パーセント」そのもの
    if abs(cross_class(90)[0]["即決の再就職手当"] - 90 * RATE_HIGH) > 0.05:
        raise _checks.TableError("即決の再就職手当が 所定給付日数×70パーセント と違う")

    # 1. 法令が名指ししている値
    _checks.statutory(RATE_HIGH, 0.70, "支給残日数3分の2以上の給付率",
                      source="雇用保険法56条の3")
    _checks.statutory(RATE_LOW, 0.60, "支給残日数3分の1以上の給付率",
                      source="雇用保険法56条の3")
    _checks.ratio(RATE_HIGH, "3分の2以上の給付率")
    _checks.ratio(RATE_LOW, "3分の1以上の給付率")
    _checks.greater(RATE_HIGH, RATE_LOW, "早く決めたほうの給付率が、遅いほうの給付率以下")

    # 2. 所定給付日数の表そのもの
    _checks.ascending(PRESCRIBED_DAYS, "所定給付日数", strict=True)
    for d in PRESCRIBED_DAYS:
        if d % 3 != 0:
            raise _checks.TableError(
                f"所定給付日数 {d} が3で割り切れません。2つの線が整数日に来ません")
    _checks.greater(DAYS_INVOLUNTARY_MAX, DAYS_VOLUNTARY_MAX,
                    "会社都合の最長日数が、自己都合の最長日数以下")

    # 3. 計算の向き —— この計算の主題そのもの
    #    (a) 残日数が多いほど再就職手当は増える（同じ所定給付日数の中で）
    _checks.never_decreases(lambda k: benefit_days(k, 330), range(0, 331, 10),
                            "支給残日数が増えたのに再就職手当が減っている")

    #    (b) **早く決めるほど、雇用保険からの受取は必ず減る**（この計算の主張）
    _checks.decreases_with(lambda k: total_days(k, 330), [0, 110, 220, 330],
                           "支給残日数が増えたのに、雇用保険からの受取が減っていない")

    #    (c) 線のすぐ下では手当がゼロになる（崖であることの確認）
    if benefit_days(round(330 * THRESHOLD_LOW) - 1, 330) != 0:
        raise _checks.TableError("3分の1の線の1日下で、再就職手当がゼロになっていません")

    #    (d) 崖の比は、数え上げても式で出しても同じ（独立に一致する）
    for d in PRESCRIBED_DAYS:
        _checks.rounding(round(cliff_low(d) / cliff_high(d), 6),
                         round(cliff_ratio_formula(d), 6),
                         f"所定給付日数{d}日での崖の比（数え上げ 対 式）")

    #    (e) 比は3に近づくが、**どの区分でも3には届かない**
    _checks.increases_with(cliff_ratio_formula, PRESCRIBED_DAYS,
                           "所定給付日数が増えたのに崖の比が増えていない")
    for d in PRESCRIBED_DAYS:
        if cliff_ratio_formula(d) >= 3.0:
            raise _checks.TableError(
                f"所定給付日数{d}日で崖の比が3.0以上になりました。式は 3d/(d+9) < 3 のはず")

    #    (f) 線の日は、平常の日より必ず高い（崖と呼べることの確認）
    for d in PRESCRIBED_DAYS:
        m = day_price_multiple(d)
        _checks.greater(m["下の線"], m["上の線"],
                        f"所定給付日数{d}日で、下の線が上の線より高くない")
        _checks.greater(m["上の線"], 1.0,
                        f"所定給付日数{d}日で、上の線が平常の1日より高くない")

    #    (g) 表の行が所定給付日数で一意
    _checks.unique_by(grid(), lambda r: r["所定給付日数"], "崖の表")

    _checks.assumption_values(ASSUMPTIONS, name="saishushoku")


if __name__ == "__main__":
    check_tables()

    print("=== 3分の1の線を1日またぐと、何日分が消えるか ===")
    print("再就職手当は支給残日数が所定給付日数の3分の1以上のときだけ出ます。")
    print("その線の1日下に落ちると、手当は減るのではなく**丸ごとゼロ**になります。")
    for r in grid():
        d = r["所定給付日数"]
        print(f"  所定給付日数 {d:3d}日: "
              f"残り{r['下の線の日']:3d}日で決まれば {benefit_days(r['下の線の日'], d):5.1f}日分、"
              f"1日遅れて残り{r['下の線の日'] - 1:3d}日なら **0日分**"
              f"（消える {r['下の崖']:5.1f}日分）")
    top = grid()[-1]
    print(f"  → いちばん深いのは所定給付日数330日の人で、"
          f"**その1日に基本手当{top['下の崖']:.0f}日分の価値**があります。")

    print()
    print("=== 崖は2つあり、深さの比は 3d÷(d+9) で、3倍には届かない ===")
    print("線は2つありますが、深さは同じではありません。")
    for r in grid():
        print(f"  所定給付日数 {r['所定給付日数']:3d}日: "
              f"上の崖（残り{r['上の線の日']:3d}日）は {r['上の崖']:5.1f}日分、"
              f"下の崖（残り{r['下の線の日']:3d}日）は {r['下の崖']:5.1f}日分 "
              f"→ **{r['崖の比']:.2f}倍**")
    print("  → 上の線は70パーセントが60パーセントに落ちるだけ（残日数の0.1倍）ですが、")
    print("     下の線は60パーセントが0になる（残日数の0.6倍）。")
    print("     残日数そのものが下の線では半分なので、比はおおよそ3倍になります。")
    print("     ただし上の線では**1日ぶんの残日数も一緒に失う**ので、その分だけ上の崖が深くなり、")
    print("     比は **3d ÷ (d + 9)** —— 所定給付日数が長いほど3に近づき、"
          f"**どの区分でも3には届きません**（{cliff_ratio_formula(90):.2f}倍〜"
          f"{cliff_ratio_formula(330):.2f}倍）。")
    print("     **後から来る崖のほうが浅い**——直感と逆です。")

    print()
    print("=== 早く決めるほど、雇用保険からの受取は必ず減る ===")
    print("再就職手当は「早期就職への報奨」と説明されますが、")
    print("受け取る合計（もらった基本手当＋再就職手当）は、早く決めるほど**減ります**。")
    for d in (90, 150, 330):
        full = total_days(0, d)
        two3 = round(d * THRESHOLD_HIGH)
        one3 = round(d * THRESHOLD_LOW)
        print(f"  所定給付日数 {d:3d}日:")
        print(f"    最後までもらう（残り0日）              {full:6.1f}日分")
        print(f"    3分の2の線ちょうど（残り{two3:3d}日）で就職  "
              f"{total_days(two3, d):6.1f}日分（{total_days(two3, d) - full:+6.1f}）")
        print(f"    3分の1の線ちょうど（残り{one3:3d}日）で就職  "
              f"{total_days(one3, d):6.1f}日分（{total_days(one3, d) - full:+6.1f}）")
    lp = loss_per_day(330)
    print(f"  → 1日早く決めるごとに失うのは、"
          f"70パーセントの帯で **{lp['70パーセントの帯']:.1f}日分**、"
          f"60パーセントの帯で **{lp['60パーセントの帯']:.1f}日分**。")
    print("     所定給付日数にはよりません。**帯だけで決まります。**")

    print()
    print("=== では、いくらの仕事なら「早く決めて得」なのか ===")
    print("失うのは上の日数分なので、就職して稼ぐ額がそれを超えれば得になります。")
    print(f"  70パーセントの帯（残日数が多いうち）: "
          f"1日あたり基本手当日額の **{(1 - RATE_HIGH) * 100:.0f}パーセント**")
    print(f"  60パーセントの帯（線が近いところ）  : "
          f"1日あたり基本手当日額の **{(1 - RATE_LOW) * 100:.0f}パーセント**")
    print("  → 基本手当日額は賃金日額のおおむね5割から8割なので、")
    print("     **その4割を超える日給の仕事なら、待つより早く決めたほうが多く受け取れます。**")
    print("     言い換えると、**待って得になる場面はほとんどありません。**")
    print("     ただし下の線を割ると手当が0になるので、")
    print("     **「待つ」の損は連続ではなく、線の上で一気に大きくなります。**")

    print()
    print("=== 会社都合と自己都合で、崖の深さは何倍違うか ===")
    print("同じ制度ですが、所定給付日数が違うので崖の深さも違います。")
    v = cliff_low(DAYS_VOLUNTARY_MAX)
    i = cliff_low(DAYS_INVOLUNTARY_MAX)
    vmin = cliff_low(90)
    print(f"  自己都合の最長 {DAYS_VOLUNTARY_MAX}日: 下の崖 {v:5.1f}日分")
    print(f"  会社都合の最長 {DAYS_INVOLUNTARY_MAX}日: 下の崖 {i:5.1f}日分 "
          f"→ **{i / v:.2f}倍**")
    print(f"  自己都合の最短  90日: 下の崖 {vmin:5.1f}日分 "
          f"→ 会社都合の最長との差は **{i / vmin:.2f}倍**")
    print("  → **長くもらえる人ほど、境目の1日が高い**。")
    print("     「急がなくてよい」と言われがちな会社都合のほうが、")
    print("     1日の遅れの値段は自己都合の3.67倍です。")

    print()
    print("=== 「1日の値段」は、受給期間中のたった2日だけ跳ね上がる ===")
    print("ここまでで、1日決まるのが遅れる値段は2種類あると分かりました。")
    print("  平常の日: 0.3日分（70パーセントの帯）または 0.4日分（60パーセントの帯）")
    print("  線の日  : 上の崖 または 下の崖 の1回きり")
    print("同じ「1日」なのに、値段は何倍違うのか。")
    for d in PRESCRIBED_DAYS:
        print(f"  所定給付日数 {d:3d}日: "
              f"上の線で **{day_price_multiple(d)['上の線']:6.1f}倍**、"
              f"下の線で **{day_price_multiple(d)['下の線']:6.1f}倍**")
    top = day_price_multiple(330)
    print(f"  → いちばん高いのは所定給付日数330日の人の下の線で、"
          f"**平常の1日の{top['下の線']:.0f}倍**。")
    print("     受給期間の330日のうち、この値段になる日は**2日しかありません。**")
    print("     残りの328日は、1日あたり0.3日分か0.4日分で一定です。")
    print("     **「早く決めたほうがいい」は正しいのですが、効くのはこの2日の前後だけ**で、")
    print("     それ以外の日は、1日急いでも0.4日分しか変わりません。")

    REM = 100
    print(f"\n=== 「あと{REM}日ある」が同じでも、区分がちがえば給付率が割れる ===")
    print(f"{'支給残日数':>8s} {'所定給付日数':>9s} {'残日数の割合':>9s} {'給付率':>6s} "
          f"{'再就職手当':>9s} {'受け取り済み':>9s} {'合計'}")
    for row in rate_drop_points(REM):
        mark = "  ← **ここで1段下がる**" if row["前の区分から下がったか"] else ""
        print(f"{row['支給残日数']:7d}日 {row['所定給付日数']:8d}日 "
              f"{row['残日数の割合']:8.1%} {row['給付率']:5.0%} "
              f"{row['再就職手当']:8.1f}日 {row['受け取り済み']:8d}日 "
              f"{row['合計']:6.1f}日{mark}")
    print("  → 給付率を決めているのは残日数ではなく、**残日数 ÷ 所定給付日数**です。"
          f"だから**条件のよい区分（長くもらえる人）ほど、同じ「あと{REM}日」でも率が低くなります。**"
          "**それでも雇用保険からの合計は区分が上のほうが多い**ので、"
          "**損なのは再就職手当だけ**です。この向きの違いは、率の表からは読めません。")

    first = cross_class_first(90)
    print(f"\n=== {90}日の区分で1日も受給せず決めた人を、"
          f"**{first}日の区分で3分の1まで受給してから決めた人**が追い越す ===")
    print(f"{'即決の区分':>7s} {'即決の手当':>9s} {'所定給付日数':>9s} {'下の線の残日数':>10s} "
          f"{'受給した日数':>9s} {'再就職手当':>9s} {'差'}")
    for row in cross_class(90):
        mark = "  ← **追い越した**" if row["追い越したか"] else ""
        print(f"{row['即決の区分']:6d}日 {row['即決の再就職手当']:8.1f}日 "
              f"{row['所定給付日数']:8d}日 {row['下の線の残日数']:9d}日 "
              f"{row['受給してから決めた日数']:8d}日 {row['再就職手当']:8.1f}日 "
              f"{row['差']:+6.1f}日{mark}")
    print("  → 再就職手当は「早く決めた人ほど多い」と説明されますが、**それは同じ区分の中の話です。**"
          f"区分をまたぐと、**{first}日の区分で{round(first * THRESHOLD_LOW)}日まで減らしてから決めた人**が、"
          f"90日の区分で**1日も受給せずに決めた人**を上回ります。"
          "**同じ「基本手当の何日分」という単位で並べないと出てこない比較です。**")
