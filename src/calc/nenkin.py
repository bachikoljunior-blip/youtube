"""老齢年金の繰下げ・繰上げが、いつ得に変わるのかを計算する。

狙いは「繰下げると42パーセント増える」を紹介することではない。それはどこにでもある。
ここで出したいのは **その増額を取り返し終わる年齢** ——損益分岐点を、
開始年齢1か月きざみで全部出したもの。

--------------------------------------------------------------------------
広く出回っている数字と、何が違うのか
--------------------------------------------------------------------------
よく見るのは「70歳まで繰り下げると81歳11か月で追いつく」という一点だけ。
これは **額面** の比較で、しかも70歳という区切りの良い1点しか見ていない。

実際には二つずれる。

1. **手取りで見ると分岐点は後ろに動く。** 年金は雑所得として課税され、
   国民健康保険料や介護保険料の算定にも入る。増えた額の全部が手に入るわけではない。
   額面で追いついても、手取りではまだ追いついていない。

2. **繰下げは1か月きざみで選べる。** 65歳0か月から75歳0か月まで121通りある。
   「70歳」だけを見るのは、121分の1しか見ていないということ。

そこでここでは、**121通りすべての損益分岐点**を、額面と手取りの両方で出す。
どこにも出ていないのは、この表そのもの。

--------------------------------------------------------------------------
なぜ手取り率が分岐点を後ろに動かすのか
--------------------------------------------------------------------------
直感に反するが、**手取り率が一律なら分岐点は動かない。** 両方に同じ率が掛かる
だけなので、比の交点は変わらない。

動くのは、**繰り下げて年金額が上がると手取り率そのものが下がる**から。
課税所得が増えて税率区分が上がり、保険料の算定基礎も上がる。
つまり増額分には、元の年金より重い率が掛かる。ここが効く。

だからこの計算では、手取り率を「額に応じて変わるもの」として扱う。
一律の率で計算すると分岐点は動かず、それでは何も言っていないのと同じになる。

--------------------------------------------------------------------------
繰上げ側には、そもそも分岐点の表が無い
--------------------------------------------------------------------------
繰下げの損益分岐点は「81歳11か月」という形で出回っている。**繰上げの側には、
それに当たる数字がほとんど出ていない。** 出ていても「60歳で受け取ると
80歳10か月で逆転する」の一点だけで、繰下げと同じく60通りのうち1つしか見ていない。

繰上げは「先に受け取ってしまう」ので、しばらくは繰上げた側が勝っている。
65歳開始が**追い抜くのはいつか**が、繰上げ側の分岐点にあたる。
ここではそれを1か月きざみで全部出す。

そして額面で見ると、この分岐点には短い式がある。

    追い抜かれる年齢 ＝ 65歳 ＋ （1 − 0.004 × 繰上げ月数）÷ 0.048 年

先に受け取った累計は「倍率 × 繰上げ年数」、65歳以降に開く差は年あたり
「1 − 倍率」なので、割ると月額も年額も約分されて消える。**もらう額がいくらでも、
額面の分岐点は同じ**ということ。ここは繰上げ側にだけ現れる性質で、
繰下げ側は「増えた額に重い率が掛かる」ぶん、こうきれいには消えない。

**手取りで見ると、この式は成り立たなくなる。** 繰上げると年額が下がり、
手取り率は逆に**上がる**。だから繰上げた側の目減りは額面ほどではなく、
追い抜かれるのはもっと後ろになる。

--------------------------------------------------------------------------
ずれの向きが、繰上げと繰下げで逆を向く
--------------------------------------------------------------------------
繰下げも繰上げも、手取りで計算すると分岐点は**後ろへ**動く。同じ向きに動くのに、
**判断としては逆を向く。**

  繰下げ  追いつくのが遅くなる → 繰下げは **不利** になる
  繰上げ  追い抜かれるのが遅くなる → 繰上げは **有利** になる

つまり手取りを入れた瞬間、天秤は繰上げ側に傾く。「繰下げたほうが得」という
広く出回っている結論は、額面で計算したときのものにすぎない。
どちらへどれだけ傾くかは、この計算でしか出ない。

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
国民年金法・厚生年金保険法の繰上げ・繰下げの規定。

  繰下げ  1か月あたり **0.7パーセント** 増（65歳超〜75歳まで、最大 +84.0%）
  繰上げ  1か月あたり **0.4パーセント** 減（60歳〜65歳未満、最大 −24.0%）

繰下げの上限が75歳になったのは令和4年4月から（昭和27年4月2日以降生まれが対象）。
繰上げの減額率が0.4パーセントなのは昭和37年4月2日以降生まれ。
それ以前の生まれは繰上げ0.5パーセントで、最大−30パーセント。ここでは0.4で計算し、
生年で変わることを必ず画面に出す。

**増額率そのものは終身続く。** 一度繰り下げれば、その率のまま生涯もらう。
分岐点より長く生きれば得、短ければ損。ここは賭けであって、正解は無い。

手取り率は制度の値ではなく **こちらの前提** なので、必ず前提として画面に出す。
裏の取れない数字は出さない、という方針どおり、ここは「仮定」と明示する。
"""
from __future__ import annotations

from dataclasses import dataclass

ASSUMPTIONS = [
    "繰下げは1か月あたり0.7パーセント増、繰上げは1か月あたり0.4パーセント減で計算しています",
    "繰上げの0.4パーセントは昭和37年4月2日以降に生まれた人の率です。それ以前は0.5パーセントです",
    "繰下げの上限が75歳なのは昭和27年4月2日以降に生まれた人です",
    "増額率も減額率も、一度決まると生涯そのままです",
    "手取り率は制度の値ではなく、この計算での仮定です。年額78万円で100パーセント、"
    "120万円で96パーセント、180万円で91パーセント、250万円で87パーセント、"
    "350万円で83パーセント、500万円で79パーセントとして置き、あいだは線形で補っています",
    "在職老齢年金による支給停止、加給年金、振替加算は入れていません",
    "分岐点は月単位で、累計が追い抜いた最初の月を書いています",
    "70歳繰下げの分岐点はよく81歳11か月と紹介されます。ここでは81歳10か月になりますが、"
    "これは月の数えはじめをどちらに置くかの違いで、1か月ずれます。どちらも間違いではありません",
    "繰上げ側の分岐点は、65歳から受け取った累計が繰上げた累計を追い抜いた最初の月です。"
    "基準にした年額は180万円で、額面の分岐点はこの年額を変えても動きません",
    "年金額べつの表は、繰り下げた後の年額が350万円までの人だけを出しています。"
    "手取り率の仮定が年額500万円までしか無く、それを超えると率が平らになって"
    "手取りと額面の差が消えてしまうためです",
]

# 制度の値
RATE_UP_PER_MONTH = 0.007       # 繰下げ 1か月あたり
RATE_DOWN_PER_MONTH = 0.004     # 繰上げ 1か月あたり（昭和37年4月2日以降生まれ）
RATE_DOWN_PER_MONTH_OLD = 0.005  # それ以前の生まれ
BASE_AGE = 65
MAX_DEFER_AGE = 75
MIN_ADVANCE_AGE = 60

# 手取り率の仮定。額が上がるほど下がる。詳しくは冒頭の説明。
# 年額（万円）→ 手取り率。あいだは線形で補う。
NET_RATE_POINTS = [
    (78.0, 1.000),    # 老齢基礎年金の満額程度。公的年金等控除と基礎控除でほぼ課税されない
    (120.0, 0.960),
    (180.0, 0.910),
    (250.0, 0.870),
    (350.0, 0.830),
    (500.0, 0.790),
]


@dataclass(frozen=True)
class Plan:
    """受給開始をずらしたときの1つの選択肢。"""

    months_from_65: int    # 正が繰下げ、負が繰上げ
    rate: float            # 65歳を1.0としたときの倍率

    @property
    def age_text(self) -> str:
        total = BASE_AGE * 12 + self.months_from_65
        return f"{total // 12}歳{total % 12}か月"


def _clamp_rate(annual_man: float) -> float:
    """年額（万円）から手取り率を補間する。"""
    points = NET_RATE_POINTS
    if annual_man <= points[0][0]:
        return points[0][1]
    if annual_man >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= annual_man <= x1:
            span = x1 - x0
            return y0 + (y1 - y0) * ((annual_man - x0) / span)
    return points[-1][1]


def rate_for(months_from_65: int, born_before_s37: bool = False) -> float:
    """65歳を1.0としたときの倍率。繰上げは負の月数で渡す。"""
    if months_from_65 >= 0:
        return 1.0 + RATE_UP_PER_MONTH * months_from_65
    down = RATE_DOWN_PER_MONTH_OLD if born_before_s37 else RATE_DOWN_PER_MONTH
    return 1.0 + down * months_from_65


def check_tables() -> None:
    """制度の値がずれていないかを、法令で決まっている端の値で確かめる。

    表を書き写すときの列ずれ・桁落ちは、目で読み直しても見つからない。
    法令が名指ししている値だけを不変条件として置き、そこから外れたら止める。
    """
    at_70 = rate_for(60)
    at_75 = rate_for(120)
    at_60 = rate_for(-60)
    at_60_old = rate_for(-60, born_before_s37=True)

    for label, got, want in (
        ("70歳まで繰下げ", at_70, 1.42),
        ("75歳まで繰下げ", at_75, 1.84),
        ("60歳まで繰上げ", at_60, 0.76),
        ("60歳まで繰上げ（昭和37年4月1日以前）", at_60_old, 0.70),
        ("65歳", rate_for(0), 1.00),
    ):
        if abs(got - want) > 1e-9:
            raise ValueError(f"{label} の倍率が {got:.4f}。法令の値は {want:.2f}")

    # 繰下げは単調に増え、繰上げは単調に減る
    rates = [rate_for(m) for m in range(-60, 121)]
    for a, b in zip(rates, rates[1:]):
        if b <= a:
            raise ValueError("受給開始を遅らせたのに倍率が増えていない")

    # 手取り率は額が上がるほど下がる（ここが分岐点を動かす唯一の理由）
    nets = [_clamp_rate(x) for x in (78, 120, 180, 250, 350, 500)]
    for a, b in zip(nets, nets[1:]):
        if b > a:
            raise ValueError("年額が上がったのに手取り率が上がっている")
    if nets[0] <= nets[-1]:
        raise ValueError("手取り率が額によらず一定になっている。これでは分岐点が動かない")

    # --- 繰上げ側の分岐点 -------------------------------------------------
    # 額面では、年額が約分されて消える（冒頭の説明の式）。**これが崩れたら、
    # どこかで年額が残っている**ので、金額を変えて2回引き、一致を要求する。
    for m in (12, 36, 60):
        a = catch_up(m, 180.0)
        b = catch_up(m, 90.0)
        if a is None or b is None:
            raise ValueError(f"{m}か月の繰上げで、額面の分岐点が出ていない")
        if a != b:
            raise ValueError(
                f"{m}か月の繰上げで、額面の分岐点が年額によって変わっている"
                f"（180万で{a}、90万で{b}）。式の上では消えるはず")
        want = BASE_AGE * 12 + round(rate_for(-m) / (RATE_DOWN_PER_MONTH * 12) * 12)
        got = a[0] * 12 + a[1]
        if abs(got - want) > 1:      # 累計は月きざみなので1か月ぶれる
            raise ValueError(
                f"{m}か月の繰上げの分岐点が式と合わない（計算 {got}か月 / 式 {want}か月）")

    # 深く繰り上げるほど、追い抜かれるのは早い（単調）
    grosses = [catch_up(m, 180.0) for m in range(1, (BASE_AGE - MIN_ADVANCE_AGE) * 12 + 1)]
    if any(g is None for g in grosses):
        raise ValueError("繰上げのどこかで、額面の分岐点が出ていない")
    months = [g[0] * 12 + g[1] for g in grosses]
    for a, b in zip(months, months[1:]):
        if b > a:
            raise ValueError("深く繰り上げたのに、追い抜かれるのが遅くなっている")

    # 手取りで見ると、繰上げ側は必ず後ろへ動く（＝繰上げが有利になる向き）
    for m in (12, 24, 36, 48, 60):
        g = catch_up(m, 180.0)
        n = catch_up(m, 180.0, net=True)
        if n is None or g is None:
            raise ValueError(f"{m}か月の繰上げで、手取りの分岐点が出ていない")
        if (n[0] * 12 + n[1]) <= (g[0] * 12 + g[1]):
            raise ValueError(
                f"{m}か月の繰上げで、手取りの分岐点が額面より後ろになっていない。"
                "繰上げると年額が下がり手取り率は上がるので、必ず後ろへ動くはず")

    # 繰下げ側は「不利になる向き」、繰上げ側は「有利になる向き」。
    # **同じ『後ろへ』なので、符号だけを見ていると取り違える。**ここで固定する。
    tilt = net_tilt(180.0)
    if len(tilt) != 4:
        raise ValueError("天秤の表の行数が変わっている")
    if not all(r["後ろへ_月"] > 0 for r in tilt):
        raise ValueError("手取りで分岐点が後ろへ動いていない行がある")
    if len({r["手取りで見ると"] for r in tilt}) != 2:
        raise ValueError("繰下げと繰上げで、有利・不利の向きが分かれていない")

    # 年金額べつの表。**この節の主張そのもの**を不変条件にする。
    by_base = by_base_grid()
    if not by_base:
        raise ValueError("年金額べつの表が空になっている")
    top = NET_RATE_POINTS[-1][0]
    if any(r["繰下げ後の年額_万"] > top for r in by_base):
        raise ValueError("手取り率の前提の外（年額500万円超）の行が残っている")
    if len({r["分岐点_額面"] for r in by_base}) != 1:
        raise ValueError("額面の分岐点が年額で動いている。ASSUMPTIONS の記述と食い違う")
    if len({r["分岐点_手取り"] for r in by_base}) < 2:
        raise ValueError("手取りの分岐点が年額で動いていない。この節が何も言っていない")
    if any(r["ずれ_月"] <= 0 for r in by_base):
        raise ValueError("手取りの分岐点が額面より前に来ている行がある")
    if any(r["差_円"] <= 0 for r in by_base):
        raise ValueError("85歳まで生きて繰下げの生涯手取りが増えていない行がある")


def break_even(months_from_65: int, base_annual_man: float, net: bool = False) -> tuple[int, int] | None:
    """繰り下げたぶんを取り返し終わる年齢を (歳, 月) で返す。

    比較するのは **65歳から受け取り続けた場合の累計** と
    **繰り下げてから受け取り続けた場合の累計**。追い抜いた最初の月を返す。
    追い抜かないなら None（繰上げの場合は一生追い抜かない）。
    """
    if months_from_65 <= 0:
        return None

    base_rate = rate_for(0)
    plan_rate = rate_for(months_from_65)
    base_year = base_annual_man * base_rate
    plan_year = base_annual_man * plan_rate
    if net:
        base_year *= _clamp_rate(base_year)
        plan_year *= _clamp_rate(plan_year)

    base_month = base_year / 12.0
    plan_month = plan_year / 12.0

    # 65歳0か月を起点にした通算月数で走らせる。上限は120歳。
    total_base = 0.0
    total_plan = 0.0
    for m in range(0, (120 - BASE_AGE) * 12 + 1):
        total_base += base_month
        if m >= months_from_65:
            total_plan += plan_month
        if total_plan > total_base:
            age = BASE_AGE * 12 + m
            return age // 12, age % 12
    return None


def defer_grid(base_annual_man: float = 180.0, step_months: int = 12) -> list[dict]:
    """繰下げの月数ごとに、倍率と損益分岐点を額面・手取りの両方で出す。"""
    rows = []
    for m in range(step_months, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1, step_months):
        gross = break_even(m, base_annual_man, net=False)
        netbe = break_even(m, base_annual_man, net=True)
        plan = Plan(m, rate_for(m))
        rows.append({
            "開始": plan.age_text,
            "倍率": round(rate_for(m), 3),
            "年額": round(base_annual_man * rate_for(m), 1),
            "分岐点_額面": f"{gross[0]}歳{gross[1]}か月" if gross else "追いつかない",
            "分岐点_手取り": f"{netbe[0]}歳{netbe[1]}か月" if netbe else "追いつかない",
            "ずれ_月": (
                (netbe[0] * 12 + netbe[1]) - (gross[0] * 12 + gross[1])
                if gross and netbe else None
            ),
        })
    return rows


def worst_gap(base_annual_man: float = 180.0) -> dict:
    """額面と手取りで分岐点が一番開く開始月を探す。動画の主役になる数字。"""
    best = {"月数": 0, "ずれ_月": -1}
    for m in range(1, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1):
        gross = break_even(m, base_annual_man, net=False)
        netbe = break_even(m, base_annual_man, net=True)
        if not gross or not netbe:
            continue
        gap = (netbe[0] * 12 + netbe[1]) - (gross[0] * 12 + gross[1])
        if gap > best["ずれ_月"]:
            best = {
                "月数": m,
                "開始": Plan(m, rate_for(m)).age_text,
                "分岐点_額面": f"{gross[0]}歳{gross[1]}か月",
                "分岐点_手取り": f"{netbe[0]}歳{netbe[1]}か月",
                "ずれ_月": gap,
            }
    return best


def catch_up(months_before_65: int, base_annual_man: float, net: bool = False) -> tuple[int, int] | None:
    """繰り上げた人が、65歳開始に **追い抜かれる** 年齢を (歳, 月) で返す。

    繰上げは先に受け取りはじめるので、しばらくは繰上げた側の累計が上にいる。
    65歳開始の累計が上回った最初の月が、繰上げ側の損益分岐点。

    `break_even()` と対になる関数で、向きだけが逆。追い抜かれないなら None。
    """
    if months_before_65 <= 0:
        return None

    early_year = base_annual_man * rate_for(-months_before_65)
    base_year = base_annual_man * rate_for(0)
    if net:
        early_year *= _clamp_rate(early_year)
        base_year *= _clamp_rate(base_year)

    early_month = early_year / 12.0
    base_month = base_year / 12.0

    # t=0 は繰上げ開始の月。65歳開始はそこから months_before_65 か月おくれる。
    total_early = 0.0
    total_base = 0.0
    start = BASE_AGE * 12 - months_before_65
    for t in range(0, (120 * 12) - start + 1):
        total_early += early_month
        if t >= months_before_65:
            total_base += base_month
        if total_base > total_early:
            age = start + t
            return age // 12, age % 12
    return None


def catch_up_grid(base_annual_man: float = 180.0, step_months: int = 12) -> list[dict]:
    """繰上げの月数ごとに、65歳開始に追い抜かれる年齢を額面・手取りで出す。"""
    rows = []
    for m in range(step_months, (BASE_AGE - MIN_ADVANCE_AGE) * 12 + 1, step_months):
        gross = catch_up(m, base_annual_man, net=False)
        netbe = catch_up(m, base_annual_man, net=True)
        rows.append({
            "開始": Plan(-m, rate_for(-m)).age_text,
            "倍率": round(rate_for(-m), 3),
            "年額": round(base_annual_man * rate_for(-m), 1),
            "分岐点_額面": f"{gross[0]}歳{gross[1]}か月" if gross else "追い抜かれない",
            "分岐点_手取り": f"{netbe[0]}歳{netbe[1]}か月" if netbe else "追い抜かれない",
            "ずれ_月": (
                (netbe[0] * 12 + netbe[1]) - (gross[0] * 12 + gross[1])
                if gross and netbe else None
            ),
        })
    return rows


def lifetime_net(months_from_65: int, base_annual_man: float,
                 until_age: int = 85) -> float:
    """受給開始から `until_age` の誕生日までに受け取る**手取りの総額**（万円）。

    倍率は終身なので、開始を遅らせると「もらえる年数」と「1年あたりの額」が
    逆向きに動きます。**その掛け算の答えが、ここで出る1つの金額**です。

    手取り率は年額から補間する**こちらの前提**（`NET_RATE_POINTS`）なので、
    画面には必ず前提として出すこと。繰下げると年額が上がり、手取り率は下がります
    —— 額面の倍率がそのまま手取りの倍率にならないのは、これが理由です。
    """
    start_months = BASE_AGE * 12 + months_from_65
    end_months = until_age * 12
    if end_months <= start_months:
        return 0.0
    annual = base_annual_man * rate_for(months_from_65)
    return annual * _clamp_rate(annual) * (end_months - start_months) / 12


def net_tilt(base_annual_man: float = 180.0, until_age: int = 85) -> list[dict]:
    """手取りで計算したとき、天秤がどちらへ何か月ぶん傾くかを出す。

    繰下げも繰上げも分岐点は後ろへ動くが、**得か損かの向きは逆**。
    そこを1つの表にして並べる。

    ## 金額の列を足した理由（2026-08-16）

    ここは長らく**年齢しか出していませんでした**（`81歳10か月 → 84歳1か月`）。
    そのせいで `topic_forge` がこの節を **2回連続で落としています** ——
    書き手は「◯◯円得する」という題を立てるのに、**その金額がこの表のどこにも
    載っていない**ので、`realign` が「裏の取れない数字」として弾いていました。
    節は在庫として数えられているのに、**実際には一度も動画にできない**状態です。

    確率のぶれではありません。**表に金額が無いことが原因**なので、
    `until_age` まで生きた場合の**手取り総額と、65歳受給との差**を列に足します。
    分岐点（年齢）と総額（金額）は同じ計算の表と裏で、どちらも終身の倍率から出ます。
    """
    rows = []
    at65 = lifetime_net(0, base_annual_man, until_age)
    for m, label in ((60, "70歳まで繰下げ"), (120, "75歳まで繰下げ")):
        gross = break_even(m, base_annual_man, net=False)
        netbe = break_even(m, base_annual_man, net=True)
        gap = (netbe[0] * 12 + netbe[1]) - (gross[0] * 12 + gross[1])
        total = lifetime_net(m, base_annual_man, until_age)
        rows.append({
            "選択": label,
            "分岐点_額面": f"{gross[0]}歳{gross[1]}か月",
            "分岐点_手取り": f"{netbe[0]}歳{netbe[1]}か月",
            "後ろへ_月": gap,
            "生涯手取り_円": round(total * 10_000),
            "65歳受給との差_円": round((total - at65) * 10_000),
            "手取りで見ると": "不利になる（追いつくのが遅い）",
        })
    for m, label in ((60, "60歳まで繰上げ"), (24, "63歳まで繰上げ")):
        gross = catch_up(m, base_annual_man, net=False)
        netbe = catch_up(m, base_annual_man, net=True)
        gap = (netbe[0] * 12 + netbe[1]) - (gross[0] * 12 + gross[1])
        total = lifetime_net(-m, base_annual_man, until_age)
        rows.append({
            "選択": label,
            "分岐点_額面": f"{gross[0]}歳{gross[1]}か月",
            "分岐点_手取り": f"{netbe[0]}歳{netbe[1]}か月",
            "後ろへ_月": gap,
            "生涯手取り_円": round(total * 10_000),
            "65歳受給との差_円": round((total - at65) * 10_000),
            "手取りで見ると": "有利になる（逃げ切れる期間が伸びる）",
        })
    return rows


def by_base_grid(months_from_65: int = 60, until_age: int = 85) -> list[dict]:
    """**年金額べつ**に、額面と手取りの分岐点、そして生涯手取りの差を出す。

    ## なぜ足したか（2026-08-16）

    既存の5つの節は、**どれも年額180万円の1人ぶん**しか出していません。
    `ASSUMPTIONS` には「額面の分岐点はこの年額を変えても動きません」と書いてあり、
    それは正しいのですが、**手取りの側は動きます** ——
    そこを誰も表にしていませんでした。「年金がいくらの人ほど繰下げが不利か」は、
    この計算からしか出ません（`_clamp_rate` の折れ線が非線形なので、
    比の交点が年額によってずれる）。

    出てくる形は直感に反します。**ずれ幅は単調に増えて頭打ちになり、
    生涯手取りの差のほうは途中で逆転します** ——
    年額78万円の人は繰下げても手取り率がほぼ1.000 のままなので、
    **120万円の人より増える額が大きい**。表を作るまで分かりませんでした。

    ## 出さない組がある理由（**前提の外は空欄にしない。行ごと出さない**）

    繰り下げた後の年額が `NET_RATE_POINTS` の上端（500万円）を超えると、
    `_clamp_rate` は端の値で平らになります。すると 65歳受給と繰下げに
    **同じ手取り率が掛かり、分岐点のずれが 0 か月**になります。
    これは「差が無い」ではなく **「こちらの前提が届いていない」** です。
    見分けが付かない数字を画面に出すと、視聴者が追試できません。
    だから該当する組は**行ごと落とします**（`check_tables` で固定）。
    """
    top = NET_RATE_POINTS[-1][0]
    rate = rate_for(months_from_65)
    rows = []
    for base, _ in NET_RATE_POINTS:
        if base * rate > top:
            continue                      # 前提の外（上の説明）
        gross = break_even(months_from_65, base, net=False)
        netbe = break_even(months_from_65, base, net=True)
        if not gross or not netbe:
            continue
        at65 = lifetime_net(0, base, until_age)
        after = lifetime_net(months_from_65, base, until_age)
        rows.append({
            "65歳の年額_万": base,
            "繰下げ後の年額_万": round(base * rate, 1),
            "手取り率_65歳": round(_clamp_rate(base), 3),
            "手取り率_繰下げ後": round(_clamp_rate(base * rate), 3),
            "分岐点_額面": f"{gross[0]}歳{gross[1]}か月",
            "分岐点_手取り": f"{netbe[0]}歳{netbe[1]}か月",
            "ずれ_月": (netbe[0] * 12 + netbe[1]) - (gross[0] * 12 + gross[1]),
            "生涯手取り_65歳受給_円": round(at65 * 10_000),
            "生涯手取り_繰下げ_円": round(after * 10_000),
            "差_円": round((after - at65) * 10_000),
        })
    return rows


def advance_grid(base_annual_man: float = 180.0, step_months: int = 12) -> list[dict]:
    """繰上げの月数ごとに、倍率と年額の減り方を出す。"""
    rows = []
    for m in range(-step_months, -(BASE_AGE - MIN_ADVANCE_AGE) * 12 - 1, -step_months):
        r = rate_for(m)
        r_old = rate_for(m, born_before_s37=True)
        rows.append({
            "開始": Plan(m, r).age_text,
            "倍率": round(r, 3),
            "年額": round(base_annual_man * r, 1),
            "減る額": round(base_annual_man * (1 - r), 1),
            "倍率_昭37年4月1日以前": round(r_old, 3),
        })
    return rows


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過\n")

    base = 180.0
    print(f"=== 繰下げ（65歳で年{base}万円の場合）===")
    for row in defer_grid(base):
        print(f"  {row['開始']:>9s}  倍率{row['倍率']:.3f}  年額{row['年額']:6.1f}万  "
              f"額面{row['分岐点_額面']:>10s}  手取り{row['分岐点_手取り']:>10s}  "
              f"ずれ{row['ずれ_月']:>3d}か月")

    print("\n=== 額面と手取りで分岐点が一番開くところ ===")
    for k, v in worst_gap(base).items():
        print(f"  {k}: {v}")

    print(f"\n=== 繰上げ（65歳で年{base}万円の場合）===")
    for row in advance_grid(base):
        print(f"  {row['開始']:>9s}  倍率{row['倍率']:.3f}  年額{row['年額']:6.1f}万  "
              f"減る額{row['減る額']:5.1f}万")

    print(f"\n=== 繰上げを65歳開始が追い抜く年齢（65歳で年{base}万円の場合）===")
    for row in catch_up_grid(base):
        print(f"  {row['開始']:>9s}  倍率{row['倍率']:.3f}  年額{row['年額']:6.1f}万  "
              f"額面{row['分岐点_額面']:>10s}  手取り{row['分岐点_手取り']:>10s}  "
              f"ずれ{row['ずれ_月']:>3d}か月")

    print("\n=== 年金額べつ / 額面の分岐点は全員おなじ、手取りの分岐点だけが動く ===")
    print("  前提: 70歳まで繰下げ（倍率1.420）/ 85歳の誕生日まで生きた場合 / "
          "手取り率は年額から補間（**制度の値ではなくこちらの前提**）")
    for row in by_base_grid():
        print(f"  65歳で年{row['65歳の年額_万']:5.1f}万 → 繰下げ後 {row['繰下げ後の年額_万']:5.1f}万  "
              f"手取り率 {row['手取り率_65歳']:.3f}→{row['手取り率_繰下げ後']:.3f}  "
              f"額面{row['分岐点_額面']:>10s}  手取り{row['分岐点_手取り']:>10s}"
              f"（{row['ずれ_月']:>2d}か月うしろ）  "
              f"85歳までの手取り {row['生涯手取り_65歳受給_円']:>11,d}円 → "
              f"{row['生涯手取り_繰下げ_円']:>11,d}円（差 {row['差_円']:>+10,d}円）")

    print("\n=== 手取りで計算すると、天秤は繰上げ側に傾く ===")
    print(f"  前提: 65歳で年{base}万円 / 85歳の誕生日まで生きた場合 / "
          f"手取り率は年額から補間（**制度の値ではなくこちらの前提**）")
    print(f"  {'65歳から受給':>12s}  生涯手取り "
          f"{round(lifetime_net(0, base) * 10_000):>10,d}円  ← 比べる相手")
    for row in net_tilt(base):
        print(f"  {row['選択']:>12s}  額面{row['分岐点_額面']:>10s} → "
              f"手取り{row['分岐点_手取り']:>10s}（{row['後ろへ_月']:>2d}か月うしろ）  "
              f"生涯手取り {row['生涯手取り_円']:>10,d}円"
              f"（65歳受給との差 {row['65歳受給との差_円']:>+11,d}円）  "
              f"{row['手取りで見ると']}")
