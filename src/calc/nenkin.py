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

import math
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
    "いちばん多くもらえる開始年齢は、60歳0か月から75歳0か月までの181通りを"
    "全部計算して選んだものです。同じ額なら早いほうを採っています",
    "何歳まで生きるかは誰にも分かりません。ここでは「その年齢まで生きたら」という"
    "仮定を置いて計算しています。仮定が変われば答えも変わります",
    "あと1か月待つ・早めるの取り返しは、その1か月ぶんの累計が入れ替わる最初の月です。"
    "取り返しの月数は、繰下げが倍率÷0.007＋1、繰上げが倍率÷0.004＋1で、年額は約分で消えます",
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

    # --- 最適な開始月（`best_start` 以下の3節の主題）-----------------------
    # 1. **75歳まで繰り下げるのが最適になるのは、うんと長生きする場合だけ**。
    #    ここが「85歳で最適」に変わる表になったら、節の文言ごと逆になります。
    #    数え上げ（`best_start`）と、限界の1か月の式（`defer_one_more_month`）は
    #    **独立に書いてあるので、一致することが両方の裏取り**になります。
    last = rate_for((MAX_DEFER_AGE - BASE_AGE) * 12 - 1)
    want_full = (BASE_AGE * 12 + (MAX_DEFER_AGE - BASE_AGE) * 12 - 1
                 + math.ceil(last / RATE_UP_PER_MONTH + 1))
    got_full = next(um for um in range(BASE_AGE * 12, 120 * 12)
                    if best_start(um) == (MAX_DEFER_AGE - BASE_AGE) * 12)
    if got_full != want_full:
        raise ValueError(
            f"75歳0か月が最適になる寿命が、数え上げ({got_full}か月)と"
            f"式({want_full}か月)で食い違っています")
    if got_full < 90 * 12:
        raise ValueError(
            "75歳まで繰り下げるのが、90歳前で最適になっています。"
            "best_start() の節は『端はめったに最適にならない』が主題なので、"
            "表が変わったなら節の文言ごと見直すこと")

    # 2. **最適は連続に動かない**（倍率が65歳で折れているので山が2つある）。
    #    飛びが消えたら、`optimum_jumps()` の節そのものが無くなります。
    jumps = optimum_jumps()
    if not jumps:
        raise ValueError(
            "最適な開始が飛ぶところが1つもありません。"
            "optimum_jumps() の節は『1か月の見込み違いで最適が飛ぶ』が主題です")
    if max(j["飛ぶ幅_月"] for j in jumps) < 12:
        raise ValueError("飛び幅が1年未満です。節の主題（4年半飛ぶ）と合いません")

    # 3. 見込む寿命が延びて、最適な開始が**早くなる**ことはない（単調）
    bests = [best_start(um) for um in range(BASE_AGE * 12, 100 * 12, 3)]
    for a, b in zip(bests, bests[1:]):
        if b < a:
            raise ValueError("寿命を長く見たのに、最適な開始が早くなっています")

    # 4. **繰上げの1か月のほうが、繰下げの1か月より高くつく**（0.004 対 0.007）。
    #    ここが逆転する表になったら、advance_one_more_month() の文言が嘘になります。
    if (1.0 / RATE_DOWN_PER_MONTH) <= (1.0 / RATE_UP_PER_MONTH):
        raise ValueError("繰上げの1か月の回収が、繰下げより早くなっています")

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


def worst_gap_by_base(step_man: int = 20,
                      low_man: int = 60,
                      high_man: int = 300) -> list[dict]:
    """年金額べつに「ずれの最大値」を出す。**額面が増えてもずれは増え続けない。**

    `worst_gap` は年額を1つ決めて、その中でずれが最大になる開始月を返す。
    ここはその外側を回して、**年額そのものを動かしたときにずれがどう動くか**を見る。

    掃引の道具はここを「189万で最大（32か月）」と拾ったが、**それは違う。**
    32か月は 276万でも出るし、131万から上は 30〜32か月を行き来するだけの
    のこぎりで、189 という数字に意味は無い（月きざみで数えているので、
    ±1か月は丸めの幅の中）。**形は「山」ではなく「頭打ち」。**

    動いているのは下の端のほうで、60万 → 131万 で 11 → 31か月と **約3倍**。
    そこから先は年額をいくら増やしても、ずれは 1か月ぶんも動かない。
    """
    rows = []
    for man in range(low_man, high_man + 1, step_man):
        w = worst_gap(float(man))
        rows.append({
            "65歳の年額_万": float(man),
            "開始": w["開始"],
            "分岐点_額面": w["分岐点_額面"],
            "分岐点_手取り": w["分岐点_手取り"],
            "ずれ_月": w["ずれ_月"],
        })
    return rows


def worst_gap_plateau(step_man: int = 1,
                      low_man: int = 60,
                      high_man: int = 300) -> dict:
    """頭打ちの入口（ずれが最大帯に初めて入る年額）と、その先の幅を返す。

    「最大は 189万」と名指しさせないための道具。**最大値そのものではなく、
    最大帯の入口と、入ってからの振れ幅**を出す（振れ幅が小さいことが主張）。
    """
    gaps = {man: worst_gap(float(man))["ずれ_月"]
            for man in range(low_man, high_man + 1, step_man)}
    top = max(gaps.values())
    entry = min(man for man, g in gaps.items() if g >= top - 1)
    after = [g for man, g in gaps.items() if man >= entry]
    return {
        "最大のずれ_月": top,
        "頭打ちの入口_万": float(entry),
        "入口でのずれ_月": gaps[entry],
        "入口より上の振れ幅_月": max(after) - min(after),
        "下の端_万": float(low_man),
        "下の端でのずれ_月": gaps[low_man],
        "入口までの倍率": round(gaps[entry] / gaps[low_man], 2),
    }


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


def lifetime(months_from_65: int, base_annual_man: float,
             until_months: int, net: bool = False) -> float:
    """受給開始から `until_months`（65歳を780として数えた月齢）までの総額（万円）。

    `lifetime_net` は「年」でしか受け取れませんが、**最適な開始月がどこで
    切り替わるか**は1か月きざみで見ないと出ません（実際、切り替わりは
    1か月の差で4年半飛びます）。だから月で受ける入口をこちらに置き、
    `lifetime_net` はここを呼ぶだけにしてあります（式は1か所）。
    """
    start_months = BASE_AGE * 12 + months_from_65
    if until_months <= start_months:
        return 0.0
    annual = base_annual_man * rate_for(months_from_65)
    if net:
        annual *= _clamp_rate(annual)
    return annual * (until_months - start_months) / 12


def lifetime_net(months_from_65: int, base_annual_man: float,
                 until_age: int = 85) -> float:
    """受給開始から `until_age` の誕生日までに受け取る**手取りの総額**（万円）。

    倍率は終身なので、開始を遅らせると「もらえる年数」と「1年あたりの額」が
    逆向きに動きます。**その掛け算の答えが、ここで出る1つの金額**です。

    手取り率は年額から補間する**こちらの前提**（`NET_RATE_POINTS`）なので、
    画面には必ず前提として出すこと。繰下げると年額が上がり、手取り率は下がります
    —— 額面の倍率がそのまま手取りの倍率にならないのは、これが理由です。
    """
    return lifetime(months_from_65, base_annual_man, until_age * 12, net=True)


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


def _age_text(months: int) -> str:
    return f"{months // 12}歳{months % 12}か月"


def best_start(until_months: int, base_annual_man: float = 180.0,
               net: bool = False) -> int:
    """`until_months` まで生きたとき、生涯の受取総額がいちばん多くなる開始月。

    返すのは 65歳からの月数（負は繰上げ）。同点なら**早いほう**を返します
    （受け取りが早いほうが手元の自由度が高いので、迷ったら前を採る）。

    ## この問いが、既存の5つの節と違うところ（2026-08-17）

    既存の節は全部「**65歳受給と比べて**、いつ追いつくか／追い抜かれるか」です。
    比べる相手が65歳に固定されている。**ここでは相手を固定しません** ——
    60歳0か月から75歳0か月までの**181通りを全部評価して、いちばん多い1つ**を出します。

    出てくる形は直感に反します。

    1. **75歳まで繰り下げるのが最適になることは、ほとんどありません。**
       待つあいだ1円も受け取らない代償が、0.7パーセントの増額を上回るからです。
    2. **最適は連続に動きません。** 倍率の傾きが65歳で 0.4→0.7 に折れているので、
       総額は**山が2つある形**になります。見込む寿命が1か月ずれただけで、
       最適が繰上げ側の山から繰下げ側の山へ**飛びます**。
       この飛びは「損益分岐点」を見ているかぎり絶対に見えません。
    """
    best_m, best_v = None, None
    for m in range(-(BASE_AGE - MIN_ADVANCE_AGE) * 12, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1):
        v = lifetime(m, base_annual_man, until_months, net=net)
        if best_v is None or v > best_v + 1e-12:
            best_m, best_v = m, v
    return best_m


def best_start_grid(base_annual_man: float = 180.0,
                    until_ages: tuple[int, ...] = (75, 80, 82, 85, 88, 90, 95, 100)) -> list[dict]:
    """何歳まで生きるかべつに、最適な開始年齢と、そのときの総額を出す。"""
    rows = []
    for age in until_ages:
        um = age * 12
        g = best_start(um, base_annual_man, net=False)
        n = best_start(um, base_annual_man, net=True)
        rows.append({
            "何歳まで": age,
            "最適な開始_額面": _age_text(BASE_AGE * 12 + g),
            "最適な開始_手取り": _age_text(BASE_AGE * 12 + n),
            "手取りで_月": n - g,
            "総額_最適_円": round(lifetime(g, base_annual_man, um) * 10_000),
            "総額_65歳開始_円": round(lifetime(0, base_annual_man, um) * 10_000),
            "総額_75歳開始_円": round(lifetime(120, base_annual_man, um) * 10_000),
            "65歳開始との差_円": round((lifetime(g, base_annual_man, um)
                                  - lifetime(0, base_annual_man, um)) * 10_000),
            "75歳開始との差_円": round((lifetime(g, base_annual_man, um)
                                  - lifetime(120, base_annual_man, um)) * 10_000),
        })
    return rows


def optimum_jumps(base_annual_man: float = 180.0, net: bool = False,
                  span_ages: tuple[int, int] = (65, 105)) -> list[dict]:
    """最適な開始が**1か月より大きく動く**ところ（＝飛ぶところ）だけを出す。

    切り替わり自体は130か所ありますが、そのほとんどは「1か月ずれる」だけで、
    表にすると読めません。**表に値打ちがあるのは、飛ぶ1か所と、両端**です。
    """
    lo, hi = span_ages
    rows, prev_m, prev_um = [], None, None
    for um in range(lo * 12, hi * 12 + 1):
        m = best_start(um, base_annual_man, net=net)
        if prev_m is not None and m - prev_m > 1:
            rows.append({
                "見込む寿命_手前": _age_text(prev_um),
                "見込む寿命_ここから": _age_text(um),
                "最適な開始_手前": _age_text(BASE_AGE * 12 + prev_m),
                "最適な開始_ここから": _age_text(BASE_AGE * 12 + m),
                "飛ぶ幅_月": m - prev_m,
                "寿命の差_月": 1,
                "総額_手前の選択_円": round(lifetime(prev_m, base_annual_man, um, net) * 10_000),
                "総額_ここからの選択_円": round(lifetime(m, base_annual_man, um, net) * 10_000),
            })
        prev_m, prev_um = m, um
    return rows


def optimum_edges(base_annual_man: float = 180.0) -> list[dict]:
    """端（60歳0か月・75歳0か月）が最適でいられる範囲を、額面と手取りで出す。"""
    rows = []
    for net in (False, True):
        low = high = None
        for um in range(BASE_AGE * 12, 110 * 12 + 1):
            m = best_start(um, base_annual_man, net=net)
            if low is None and m > -(BASE_AGE - MIN_ADVANCE_AGE) * 12:
                low = um                              # 60歳0か月が最適でなくなる
            if high is None and m == (MAX_DEFER_AGE - BASE_AGE) * 12:
                high = um                             # 75歳0か月が最適になる
        rows.append({
            "見方": "手取り" if net else "額面",
            "60歳0か月が最適なのは": f"{_age_text(low - 1)}まで",
            "75歳0か月が最適になるのは": f"{_age_text(high)}から" if high else "この範囲では無い",
            "そのあいだの幅_年": round((high - low) / 12, 1) if high else None,
        })
    return rows


def defer_one_more_month(base_annual_man: float = 180.0,
                         step_months: int = 12) -> list[dict]:
    """「**あと1か月だけ**待つ」ことの値段と、それを取り返し終わる年齢。

    ## なぜ既存の分岐点の節と別物か

    既存の節が出しているのは**累計の分岐点**（65歳開始と比べて、いつ追いつくか）です。
    ここで出すのは**限界の分岐点** —— いま立っている月から、もう1か月だけ待つかどうか。
    判断は常にこちらの形で来ます。「70歳まで待つか」ではなく「今月受け取り始めるか」です。

    式は短く、**年額が約分で消えます**（もらう額がいくらでも同じ）。

        取り返し終わるまでの月数 ＝ 倍率 ÷ 0.007 ＋ 1

    だから**待てば待つほど、その1か月の回収は遅くなります**（倍率が上がるので）。
    65歳での1か月は約12年で取り返せますが、74歳11か月での1か月は**約22年**かかる。
    **これが「75歳まで繰り下げるのが最適になりにくい」ことの正体**で、
    `best_start()` の飛びも `optimum_edges()` の端も、全部この1本の式から出ています。
    """
    rows = []
    for m in range(0, (MAX_DEFER_AGE - BASE_AGE) * 12, step_months):
        r = rate_for(m)
        forgone = base_annual_man * r / 12            # 見送る1か月ぶん（万円）
        gained_year = base_annual_man * RATE_UP_PER_MONTH   # 増える年額（万円）
        months = r / RATE_UP_PER_MONTH + 1
        done = BASE_AGE * 12 + m + math.ceil(months)
        rows.append({
            "いま": _age_text(BASE_AGE * 12 + m),
            "あと1か月待つと年額_円": round(gained_year * 10_000),
            "見送る1か月ぶん_円": round(forgone * 10_000),
            "取り返すのに_月": math.ceil(months),
            "取り返し終わる年齢": _age_text(done),
            "取り返すのに_年": round(months / 12, 1),
        })
    return rows


def advance_one_more_month(base_annual_man: float = 180.0,
                           step_months: int = 12) -> list[dict]:
    """「**あと1か月だけ**早める」ことの値段と、その代償を払い終わる年齢。

    繰下げと同じ形の式ですが、**分母が 0.004 なので回収は 1.75倍ずるずる後ろへ**動きます。

        払い終わるまでの月数 ＝ 倍率 ÷ 0.004 ＋ 1

    繰下げの1か月は約12年で取り返せるのに、繰上げの1か月の代償を払い終わるのは
    **約21年後**。**同じ「1か月」なのに、向きによって値段が倍近く違う。**
    ここが、額面で見たときに繰上げが長く有利でいられる理由です。
    """
    rows = []
    for m in range(0, (BASE_AGE - MIN_ADVANCE_AGE) * 12, step_months):
        r = rate_for(-m)
        gained = base_annual_man * rate_for(-m - 1) / 12   # 先に受け取る1か月ぶん
        lost_year = base_annual_man * RATE_DOWN_PER_MONTH  # 減る年額
        months = r / RATE_DOWN_PER_MONTH + 1
        done = BASE_AGE * 12 - m - 1 + math.ceil(months)
        rows.append({
            "いま": _age_text(BASE_AGE * 12 - m),
            # **減る側なので負で持つ**（繰下げの表と並ぶので、符号を落とすと
            # 「早めても年額が増える」と読めてしまう）
            "1か月早めると年額_円": -round(lost_year * 10_000),
            "先に受け取る1か月ぶん_円": round(gained * 10_000),
            "払い終わるまで_月": math.ceil(months),
            "払い終わる年齢": _age_text(done),
            "払い終わるまで_年": round(months / 12, 1),
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

    print("\n=== 年金額を増やしても、ずれはある所から先へ広がらない ===")
    pl = worst_gap_plateau()
    print(f"  前提: 65歳の年額を {pl['下の端_万']:.0f}万〜300万で1万きざみに動かし、"
          f"各年額でずれが最大になる開始月を探した / 手取り率は年額から補間"
          f"（**制度の値ではなくこちらの前提**）")
    print(f"  下の端 年{pl['下の端_万']:.0f}万 → ずれ {pl['下の端でのずれ_月']}か月")
    print(f"  頭打ちの入口 年{pl['頭打ちの入口_万']:.0f}万 → ずれ "
          f"{pl['入口でのずれ_月']}か月（**{pl['入口までの倍率']}倍**）")
    print(f"  入口より上は、300万まで振れ幅 {pl['入口より上の振れ幅_月']}か月だけ"
          f"（最大 {pl['最大のずれ_月']}か月）")
    print("  **「年金が多い人ほど手取りの分岐点が後ろへずれる」は、"
          "入口までの話。そこから上は年額を倍にしても1〜2か月しか動かない。**")
    for row in worst_gap_by_base():
        print(f"  65歳で年{row['65歳の年額_万']:5.1f}万  開始{row['開始']:>9s}  "
              f"額面{row['分岐点_額面']:>10s}  手取り{row['分岐点_手取り']:>10s}  "
              f"ずれ{row['ずれ_月']:>3d}か月")

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

    print(f"\n=== 何歳まで生きるかべつ / 181通りから選んだ、いちばん多くもらえる開始年齢"
          f"（65歳で年{base}万円の場合）===")
    print("  前提: 60歳0か月〜75歳0か月の181通りを全部計算して、総額がいちばん多い1つ / "
          "手取り率は年額から補間（**制度の値ではなくこちらの前提**）")
    for row in best_start_grid(base):
        print(f"  {row['何歳まで']:>3d}歳まで生きるなら  額面の最適 {row['最適な開始_額面']:>9s}  "
              f"手取りの最適 {row['最適な開始_手取り']:>9s}（{row['手取りで_月']:>+3d}か月）  "
              f"総額 {row['総額_最適_円']:>12,d}円  "
              f"65歳開始との差 {row['65歳開始との差_円']:>+11,d}円  "
              f"75歳開始との差 {row['75歳開始との差_円']:>+11,d}円")

    print(f"\n=== 見込む寿命が1か月ちがうだけで、最適な開始が4年半飛ぶところ"
          f"（65歳で年{base}万円の場合）===")
    print("  前提: 総額は「もらえる年数 × 倍率」で、倍率の傾きが65歳で 0.4→0.7 に折れる / "
          "だから山が2つあり、どちらの山が高いかが入れ替わる")
    for row in optimum_jumps(base):
        print(f"  {row['見込む寿命_手前']}まで → 最適は {row['最適な開始_手前']}   "
              f"{row['見込む寿命_ここから']}から → 最適は {row['最適な開始_ここから']}   "
              f"**寿命の見込みが1か月ちがうだけで {row['飛ぶ幅_月']}か月ぶん飛ぶ**  "
              f"（そのときの総額 {row['総額_手前の選択_円']:,d}円 → "
              f"{row['総額_ここからの選択_円']:,d}円）")
    for row in optimum_edges(base):
        print(f"  {row['見方']:>3s}で見たとき  60歳0か月が最適なのは {row['60歳0か月が最適なのは']}  "
              f"75歳0か月が最適になるのは {row['75歳0か月が最適になるのは']}")

    print(f"\n=== 繰下げ「あと1か月だけ待つ」の値段（65歳で年{base}万円の場合）===")
    print("  前提: 取り返し終わるまでの月数 ＝ 倍率 ÷ 0.007 ＋ 1（**年額は約分で消えるので、"
          "もらう額がいくらでも同じ**）")
    for row in defer_one_more_month(base):
        print(f"  {row['いま']:>9s}に立っているとき  1か月待つと年額 "
              f"{row['あと1か月待つと年額_円']:>+9,d}円  見送るのは "
              f"{row['見送る1か月ぶん_円']:>9,d}円  "
              f"取り返すのに {row['取り返すのに_月']:>3d}か月（{row['取り返すのに_年']:>4.1f}年）  "
              f"→ {row['取り返し終わる年齢']}")

    print(f"\n=== 繰上げ「あと1か月だけ早める」の値段（65歳で年{base}万円の場合）===")
    print("  前提: 払い終わるまでの月数 ＝ 倍率 ÷ 0.004 ＋ 1 / "
          "**繰下げと同じ形の式で、分母だけが 0.007 から 0.004 に変わる**")
    for row in advance_one_more_month(base):
        print(f"  {row['いま']:>9s}に立っているとき  1か月早めると年額は生涯 "
              f"{row['1か月早めると年額_円']:>+9,d}円  先に受け取れるのは "
              f"{row['先に受け取る1か月ぶん_円']:>9,d}円  "
              f"払い終わるまで {row['払い終わるまで_月']:>3d}か月（{row['払い終わるまで_年']:>4.1f}年）  "
              f"→ {row['払い終わる年齢']}")

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
