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

from fractions import Fraction

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
    "増えたぶんに掛かる手取り率は、(繰下げ後の手取り − 65歳の手取り) ÷ (繰下げ後の額面 − 65歳の額面) で出しています。表に出ている手取り率は年額全体に掛かる平均の率で、これとは別の数です",
    "取りこぼしの表は、寿命を75歳から100歳まで1か月きざみで301通り置き、それぞれの寿命での最善の総額との差を出したものです。寿命がその範囲の外なら、この答えも変わります",
    "手取り率の前提を振る表の k は、手取り率の下がり方だけを何倍にするかです。k が0なら額面と同じ、1ならこの計算で使っている前提そのもので、制度に k という値があるわけではありません",
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

    # --- 繰下げの年利（`deferral_irr` 以下の5節の主題）---------------------
    # (1) **累計の追い越し（`break_even`）と、正味現在価値の符号（`irr_zero_age`）は
    #     別々に書いてある。** 同じ年齢に着かなければ、どちらかが壊れています。
    #     年利がプラスに変わる最初の「歳」は、分岐点の歳（月が余っていれば+1歳）。
    for m in (12, 60, 96):
        be = break_even(m, 180.0)
        z = irr_zero_age(m, 180.0)
        want = be[0] + (1 if be[1] > 0 else 0)
        if z != want:
            raise ValueError(
                f"繰下げ{m}か月: 分岐点は {be[0]}歳{be[1]}か月なのに、"
                f"年利がプラスに変わるのは {z}歳（{want}歳のはず）")

    # (2) **額面の年利は年金額によらない**（節「谷は内側」の前半そのもの）。
    #     割引率の式で額が約分されるので、どの年額でも同じ値になります。
    gross_by_base = [deferral_irr(60, float(x), 85) for x in (78, 180, 350, 500)]
    if any(abs(g - gross_by_base[0]) > 1e-6 for g in gross_by_base):
        raise ValueError(f"額面の年利が年金額で動いています: {gross_by_base}")

    # (3) **手取りの年利の谷は、端ではなく内側**（節の主題）。
    #     端で額面に戻るのは、下は課税されないから・上は手取り率が一定だから。
    w = irr_worst_base(60, 85, step_man=4)
    if not (w["谷の年利_手取り"] < w["下の端の年利_手取り"]
            and w["谷の年利_手取り"] < w["上の端の年利_手取り"]):
        raise ValueError(f"手取りの年利の谷が端にあります: {w}")

    # (4) **待つほど年利は下がる。** 「1か月0.7%増」は一定なのに年利が落ちる、
    #     というのが節の主題なので、向きが変わったら節ごと書き直すこと。
    seq = [r["年利_額面"] for r in irr_grid(180.0, 85, 12)
           if r["年利_額面"] is not None]
    for a, b in zip(seq, seq[1:]):
        if b >= a:
            raise ValueError(f"繰り下げるほど年利が上がっています: {seq}")

    # (5) **手取りで見ると、元が取れる最後の月は前へ動く**（縮まない向きなら節が逆）。
    ceiling = (MAX_DEFER_AGE - BASE_AGE) * 12
    lg = irr_last_month(180.0, 85, net=False)["最後の月数"]
    ln = irr_last_month(180.0, 85, net=True)["最後の月数"]
    if ln > lg or (ln == lg and lg < ceiling):
        # 額面のほうが上限に張り付いている（`lg == ceiling`）ときは、
        # 手取りが同じ月で止まっていても**繰下げの上限で切れただけ**なので通す。
        raise ValueError(
            f"手取りのほうが遅くまで元が取れています（額面{lg}か月 / 手取り{ln}か月）")

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

    # --- 増えたぶんに掛かる手取り率（`marginal_net_rate` の節）--------------
    # 1. **節の主張そのもの**: 増えたぶんの率は、平均の率より必ず低い。
    #    等しくなるのは手取り率が平らなときだけで、そうなったら節が消えます。
    for r in marginal_net_grid(180.0):
        if r["限界の手取り率"] is None or r["限界の手取り率"] >= r["平均の手取り率"]:
            raise ValueError(
                f"{r['開始']}: 増えたぶんの率 {r['限界の手取り率']} が"
                f"平均の率 {r['平均の手取り率']} を下回っていません")
    # 2. **平均の率で見込むと、必ず多く見える**（差が負の向きで揃うこと）。
    if any(r["実際の手取り増_円"] >= r["平均の率で見込んだ手取り増_円"]
           for r in marginal_net_grid(180.0)):
        raise ValueError("平均の率で見込んだ額より、実際のほうが多い行があります")
    # 3. **差の定義を、独立にもう1本で裏取りする。**
    #    限界の率 ＝ (手取りの差) ÷ (額面の差) を、`lifetime` 側から解き直す
    #    （こちらは年額から直に、あちらは総額から）。1年ぶんに揃えて比べる。
    for m in (12, 60, 120):
        r = marginal_net_rate(m, 180.0)
        g_up = 180.0 * (rate_for(m) - rate_for(0))
        n_up = (lifetime(m, 180.0, (BASE_AGE * 12 + m) + 12, net=True)
                - lifetime(0, 180.0, BASE_AGE * 12 + 12, net=True))
        if abs(n_up / g_up - r["限界の手取り率"]) > 1e-9:
            raise ValueError(
                f"{m}か月: 限界の率が2つの解き方で食い違います"
                f"（{r['限界の手取り率']} 対 {n_up / g_up}）")

    # --- 寿命が読めないときの開始（`minimax_start` の節）--------------------
    # 4. **節の題そのもの**: 最大の取りこぼしを最小にする開始は、端でも
    #    「よく言われる年齢」でもない。ここが 60/65/70/75 のどれかに
    #    なったら、題を書き直すこと。
    mm = minimax_start(180.0, (75, 100), net=False)
    for key in ("金額で選ぶ", "割合で選ぶ"):
        if mm[key]["月数"] in (-60, 0, 60, 120):
            raise ValueError(
                f"{key}の答えが {mm[key]['開始']} です。"
                "節は『よく言われる年齢ではない』が主題なので、題ごと見直すこと")
    # 5. **金額と割合で答えが割れること**（割れないなら、節が半分になります）。
    if mm["金額で選ぶ"]["月数"] == mm["割合で選ぶ"]["月数"]:
        raise ValueError("金額で選んだ答えと、割合で選んだ答えが同じになっています")
    # 6. **選んだ開始が、比べる相手より本当に小さいこと**（最小化の裏取り）。
    for key in ("65歳開始", "70歳繰下げ", "75歳繰下げ", "60歳繰上げ"):
        if mm[key]["最大の取りこぼし_円"] < mm["金額で選ぶ"]["最大の取りこぼし_円"]:
            raise ValueError(f"{key} のほうが取りこぼしが小さい。最小化が壊れています")
        if mm[key]["最大の取りこぼし_割合"] < mm["割合で選ぶ"]["最大の取りこぼし_割合"]:
            raise ValueError(f"{key} のほうが割合が小さい。最小化が壊れています")
    # 7. 帯の下の端で亡くなると、そこまで1円も受け取らない開始は**全額**の
    #    取りこぼしになる（割合が 1.0）。ここが 1.0 でなければ、
    #    取りこぼしの定義か `lifetime` のどちらかが壊れています。
    if abs(mm["75歳繰下げ"]["最大の取りこぼし_割合"] - 1.0) > 1e-12:
        raise ValueError(
            f"75歳0か月開始で75歳まで生きた場合の取りこぼしが全額になっていません"
            f"（{mm['75歳繰下げ']['最大の取りこぼし_割合']}）")

    # --- 前提を振ると裏返る点（`assumption_flip` の節）----------------------
    # 8. **裏返る k は、二分法とは別に閉じた形でも出せる。**
    #    差は k について1次なので `flip = d0 / (d0 - d1)`。
    #    二分法と一致しなければ、どちらかが壊れています。
    for age in (85, 88, 90):
        af = assumption_flip(180.0, age, 60)
        d0 = af["額面での差_円"] / 10_000
        d1 = af["いまの前提での差_円"] / 10_000
        want = d0 / (d0 - d1)
        if af["裏返る_k"] is None or abs(af["裏返る_k"] - want) > 1e-6:
            raise ValueError(
                f"{age}歳: 裏返る k が二分法({af['裏返る_k']})と式({want})で"
                "食い違います")
    # 9. **手取りの前提は、繰下げを不利にする向きにしか効かない**
    #    （k を上げると差が縮む）。向きが変われば節の文言ごと逆になります。
    for age in (82, 85, 88, 90, 95):
        af = assumption_flip(180.0, age, 60)
        if af["いまの前提での差_円"] >= af["額面での差_円"]:
            raise ValueError(
                f"{age}歳: 手取りで見たほうが繰下げの差が大きくなっています")
    # 10. 長生きを見込むほど、裏返るまでの余裕は大きくなる（単調）。
    ks = [assumption_flip(180.0, a, 60)["裏返る_k"] for a in (85, 88, 90, 95)]
    for a, b in zip(ks, ks[1:]):
        if a is None or b is None or b <= a:
            raise ValueError(f"寿命を長く見たのに、裏返る k が増えていません: {ks}")


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


def catch_up(months_before_65: int, base_annual_man: float, net: bool = False,
             born_before_s37: bool = False) -> tuple[int, int] | None:
    """繰り上げた人が、65歳開始に **追い抜かれる** 年齢を (歳, 月) で返す。

    繰上げは先に受け取りはじめるので、しばらくは繰上げた側の累計が上にいる。
    65歳開始の累計が上回った最初の月が、繰上げ側の損益分岐点。

    `break_even()` と対になる関数で、向きだけが逆。追い抜かれないなら None。
    """
    if months_before_65 <= 0:
        return None

    # **額面はここを厳密にやること**（2026-08-18 に測って直した）。
    # 累計が入れ替わる月は **必ず厳密な同点**に着きます —— 解くと
    # `t = (m + 倍率 - 1) / (1 - 倍率)` で、繰上げ月数 m が約分で消えて
    # **新率は 249、旧率は 199 の一定値**。つまりこの関数は毎回、
    # 「ちょうど並ぶ月」の隣を返しています。
    # `1 - 0.005 * 60` が `0.7` にならない（`0.6999999999999999`）ので、
    # **浮動小数の最後の1桁が、返す月を1か月ずらしていました**（実測4/5行）。
    # 手取り側は `_clamp_rate` が補間なので同点には着きません（float のまま）。
    if net:
        early_year = base_annual_man * rate_for(-months_before_65, born_before_s37)
        base_year = base_annual_man * rate_for(0)
        early_year *= _clamp_rate(early_year)
        base_year *= _clamp_rate(base_year)
        early_month = early_year / 12.0
        base_month = base_year / 12.0
    else:
        down = (Fraction(RATE_DOWN_PER_MONTH_OLD).limit_denominator(10_000)
                if born_before_s37
                else Fraction(RATE_DOWN_PER_MONTH).limit_denominator(10_000))
        rate = 1 - down * months_before_65
        base = Fraction(str(base_annual_man))
        early_month = base * rate / 12
        base_month = base / 12

    # t=0 は繰上げ開始の月。65歳開始はそこから months_before_65 か月おくれる。
    total_early = early_month * 0
    total_base = base_month * 0
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


# ------------------------------- 生まれた日で減額率が変わる（昭和37年4月2日）

def _monthly_flows(months_from_65: int, base_annual_man: float,
                   until_age: int, net: bool = False) -> list[float]:
    """65歳0か月を第0月として、「繰り下げた側 − 65歳開始側」の月ごとの差額を並べる。

    繰下げを**投資**として見るための並びです。待っているあいだは
    65歳開始なら入っていたはずの額が入らないので **マイナス**、
    受け取りが始まってからは増額ぶんだけ **プラス**。
    符号が変わるのは1回だけなので、内部収益率がただ1つに決まります。
    """
    base_year = base_annual_man * rate_for(0)
    plan_year = base_annual_man * rate_for(months_from_65)
    if net:
        base_year *= _clamp_rate(base_year)
        plan_year *= _clamp_rate(plan_year)
    base_month = base_year / 12.0
    plan_month = plan_year / 12.0

    total = (until_age - BASE_AGE) * 12
    flows = []
    for m in range(total):
        got = plan_month if m >= months_from_65 else 0.0
        flows.append(got - base_month)
    return flows


def deferral_irr(months_from_65: int, base_annual_man: float = 180.0,
                 until_age: int = 85, net: bool = False) -> float | None:
    """繰下げを「投資」とみなしたときの**年利**を返す（％）。届かないなら None。

    繰下げの説明は「1か月で 0.7% 増える」で止まっていて、**増える率**しか
    言っていません。増額は終身ですが、**待っているあいだの受給を差し出して
    買っている**ので、率だけでは損得になりません。

    ここで出すのは、差し出したぶんと受け取るぶんが釣り合う割引率
    —— つまり **その人が何歳まで生きるかを決めたときの、繰下げの年利**です。
    どこにも出ていないのは、これを **1か月きざみ × 寿命べつ**で全部出した表。

    符号が変わるのは1回だけ（待機中はマイナス・受給後はプラス）なので、
    正味現在価値は割引率について単調に減り、**答えはただ1つ**に決まります。
    寿命が分岐点より手前なら、どんな割引率でも釣り合わない ＝ None。
    """
    if months_from_65 <= 0:
        return None
    flows = _monthly_flows(months_from_65, base_annual_man, until_age, net=net)
    if sum(flows) <= 0:
        return None      # 総額で追いついていない＝分岐点の手前

    def npv(monthly_rate: float) -> float:
        acc = 0.0
        for m, f in enumerate(flows):
            acc += f / ((1.0 + monthly_rate) ** m)
        return acc

    lo, hi = 0.0, 1.0        # 月利 0%〜100%
    if npv(hi) > 0:
        return None          # 現実には来ない（念のため）
    # **幅が縮まなくなったら抜ける。** 200回は倍精度の限界（約60回）の3倍以上あり、
    # 61回目から先の `mid` は `lo` か `hi` そのものになって**答えが1ビットも動きません**。
    # それでも 200回 回すと `npv()`（月数ぶんの累乗）を空回しします ——
    # 実測で `check_tables()` が 1.47秒、上限 1.0秒 の検査が赤でした（2026-08-25）。
    # 抜け方を「幅で」書いてあるので、**返る値は前と同じ**です（下の検査で確かめています）。
    for _ in range(200):
        mid = (lo + hi) / 2
        if mid <= lo or mid >= hi:
            break            # これ以上は倍精度で割れない
        if npv(mid) > 0:
            lo = mid
        else:
            hi = mid
    monthly = (lo + hi) / 2
    return ((1.0 + monthly) ** 12 - 1.0) * 100.0


def irr_grid(base_annual_man: float = 180.0, until_age: int = 85,
             step_months: int = 12) -> list[dict]:
    """繰り下げた月数ごとに、額面と手取りの年利を並べる。"""
    rows = []
    for m in range(step_months, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1, step_months):
        gross = deferral_irr(m, base_annual_man, until_age, net=False)
        netv = deferral_irr(m, base_annual_man, until_age, net=True)
        rows.append({
            "開始": Plan(m, rate_for(m)).age_text,
            "月数": m,
            "倍率": round(rate_for(m), 3),
            "年利_額面": None if gross is None else round(gross, 2),
            "年利_手取り": None if netv is None else round(netv, 2),
            "差_ポイント": None if (gross is None or netv is None)
                         else round(gross - netv, 2),
        })
    return rows


def irr_by_lifespan(months_from_65: int = 60, base_annual_man: float = 180.0,
                    low_age: int = 80, high_age: int = 100,
                    step_age: int = 2) -> list[dict]:
    """寿命を動かしたときに、繰下げの年利がどう動くかを出す。"""
    rows = []
    for age in range(low_age, high_age + 1, step_age):
        gross = deferral_irr(months_from_65, base_annual_man, age, net=False)
        netv = deferral_irr(months_from_65, base_annual_man, age, net=True)
        rows.append({
            "何歳まで": age,
            "年利_額面": None if gross is None else round(gross, 2),
            "年利_手取り": None if netv is None else round(netv, 2),
        })
    return rows


def irr_best_months(base_annual_man: float = 180.0, until_age: int = 85,
                    net: bool = False) -> dict:
    """121通りのうち、年利がいちばん高い繰下げ月数を1か月きざみで探す。

    **総額がいちばん多い開始月とは別のもの**です。総額は「いくら受け取るか」、
    こちらは「差し出したものに対して、どれだけの率で戻るか」。
    どちらを選ぶかで答えが変わること自体が、この表の主張です。
    """
    best = {"月数": 0, "年利": None}
    for m in range(1, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1):
        v = deferral_irr(m, base_annual_man, until_age, net=net)
        if v is None:
            continue
        if best["年利"] is None or v > best["年利"]:
            best = {"月数": m, "開始": Plan(m, rate_for(m)).age_text,
                    "年利": round(v, 2)}
    return best


def irr_zero_age(months_from_65: int, base_annual_man: float = 180.0,
                 net: bool = False) -> int | None:
    """年利がプラスに変わる最初の寿命（歳）を返す。**分岐点と一致するはず**。

    `break_even` は累計の追い越しで、こちらは正味現在価値の符号。
    **別の道から同じ年齢に着かなければ、どちらかが壊れています。**
    `check_tables` の不変条件はこの一致を見ています。
    """
    for age in range(BASE_AGE + 1, 121):
        if deferral_irr(months_from_65, base_annual_man, age, net=net) is not None:
            return age
    return None


def irr_by_base(months_from_65: int = 60, until_age: int = 85,
                low_man: int = 78, high_man: int = 500,
                step_man: int = 2) -> list[dict]:
    """年金額べつに、繰下げの年利を出す。**額面は動かず、手取りだけが動く。**

    額面の年利は年金額によりません（差し出す額と受け取る額に同じ数が掛かる
    ので、割引率の式から約分で消えます）。**手取りだけが動くのは、
    年額によって手取り率が変わるから**です。
    """
    rows = []
    for man in range(low_man, high_man + 1, step_man):
        rows.append({
            "65歳の年額_万": float(man),
            "年利_額面": deferral_irr(months_from_65, float(man), until_age, net=False),
            "年利_手取り": deferral_irr(months_from_65, float(man), until_age, net=True),
        })
    return rows


def irr_worst_base(months_from_65: int = 60, until_age: int = 85,
                   low_man: int = 78, high_man: int = 500,
                   step_man: int = 1) -> dict:
    """手取りの年利がいちばん低くなる年金額を返す。**端ではなく途中にあります。**

    低いほうへ動かしても高いほうへ動かしても年利は上がるので、
    **谷は内側**です。理由は手取り率の折れ線の形にあります ——
    下の端（78万）では課税されないので額面と同じ、上の端（500万以上）では
    手取り率が一定になるのでやはり額面と同じ率に戻る。
    **その間だけ、繰り下げて増えたぶんに元より重い率が掛かります。**
    """
    rows = [r for r in irr_by_base(months_from_65, until_age,
                                   low_man, high_man, step_man)
            if r["年利_手取り"] is not None]
    if not rows:
        return {}
    worst = min(rows, key=lambda r: r["年利_手取り"])
    ends = [rows[0], rows[-1]]
    return {
        "谷の年額_万": worst["65歳の年額_万"],
        "谷の年利_手取り": round(worst["年利_手取り"], 2),
        "年利_額面": round(worst["年利_額面"], 2),
        "下の端_万": ends[0]["65歳の年額_万"],
        "下の端の年利_手取り": round(ends[0]["年利_手取り"], 2),
        "上の端_万": ends[1]["65歳の年額_万"],
        "上の端の年利_手取り": round(ends[1]["年利_手取り"], 2),
        "谷と額面の差_ポイント": round(worst["年利_額面"] - worst["年利_手取り"], 2),
    }


def irr_last_month(base_annual_man: float = 180.0, until_age: int = 85,
                   net: bool = False) -> dict:
    """その寿命で「元が取れる」最後の繰下げ月を返す。1か月きざみで探す。"""
    last = None
    for m in range(1, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1):
        if deferral_irr(m, base_annual_man, until_age, net=net) is not None:
            last = m
    if last is None:
        return {}
    return {
        "最後の月数": last,
        "最後の開始": Plan(last, rate_for(last)).age_text,
        "そこでの年利": round(deferral_irr(last, base_annual_man, until_age, net=net), 2),
        "次の月の開始": Plan(last + 1, rate_for(last + 1)).age_text,
    }


def birth_gap(months_before_65: int, base_annual_man: float = 180.0,
              until_age: int = 85) -> dict:
    """**繰上げの減額率は、生まれた日で 0.4% と 0.5% に分かれます。**

    昭和37年4月1日以前に生まれた人は 0.5%、翌日以降は 0.4%。
    **1日ちがうだけで、生涯そのままの倍率が変わります。**

    `advance_grid()` は倍率の列までしか出していませんでした。
    ここで出すのはその先 —— **65歳開始に追い抜かれる年齢が何か月ずれるか**と、
    **`until_age` まで生きたときの生涯の差**です。
    """
    new_rate = rate_for(-months_before_65)
    old_rate = rate_for(-months_before_65, born_before_s37=True)
    new_year = base_annual_man * new_rate
    old_year = base_annual_man * old_rate
    # 受け取る月数 ＝ 繰上げ開始（65歳の months_before_65 か月前）から until_age まで
    months_paid = (until_age - BASE_AGE) * 12 + months_before_65
    new_be = catch_up(months_before_65, base_annual_man)
    old_be = catch_up(months_before_65, base_annual_man, born_before_s37=True)
    return {
        "開始": Plan(-months_before_65, new_rate).age_text,
        "倍率_新": round(new_rate, 3),
        "倍率_旧": round(old_rate, 3),
        "年額_新": round(new_year, 1),
        "年額_旧": round(old_year, 1),
        "年の差": round(new_year - old_year, 1),
        "生涯の差": round((new_year - old_year) / 12.0 * months_paid, 1),
        "分岐点_新": f"{new_be[0]}歳{new_be[1]}か月" if new_be else "追い抜かれない",
        "分岐点_旧": f"{old_be[0]}歳{old_be[1]}か月" if old_be else "追い抜かれない",
        "ずれ_月": ((new_be[0] * 12 + new_be[1]) - (old_be[0] * 12 + old_be[1])
                    if new_be and old_be else None),
    }


def birth_gap_grid(base_annual_man: float = 180.0, step_months: int = 12,
                   until_age: int = 85) -> list[dict]:
    """繰上げの月数ごとに、生まれた日の差でつく開きを出す。"""
    check_tables()
    return [birth_gap(m, base_annual_man, until_age)
            for m in range(step_months, (BASE_AGE - MIN_ADVANCE_AGE) * 12 + 1,
                           step_months)]


def birth_gap_ratio(months_before_65: int) -> float:
    """**減る額の比。** 0.005 ÷ 0.004 で、繰り上げた月数によりません。"""
    return ((1 - rate_for(-months_before_65, born_before_s37=True))
            / (1 - rate_for(-months_before_65)))


# ---------------- 増えた額面のうち、手元に残るのは何円か（限界の手取り率）----
def marginal_net_rate(months_from_65: int, base_annual_man: float = 180.0) -> dict:
    """**繰り下げて増えた額面1円のうち、手取りとして残るのは何円か。**

    表に出ている手取り率（`NET_RATE_POINTS`）は**平均の率**です ——
    「年額180万円なら91パーセント」は、180万円**全体**に掛かる率のこと。

    **繰下げの説明が答えていないのは、増えたぶんに掛かる率のほう**です。
    年額が上がると平均の率そのものが下がるので、
    **増えた額面に掛かる率は、平均より必ず低くなります**:

        限界の手取り率 ＝ (繰下げ後の手取り − 65歳の手取り)
                        ÷ (繰下げ後の額面 − 65歳の額面)

    分母も分子も**差**なので、平均の率とは別の数です。
    「1か月0.7パーセント増える」は額面の話で、
    **手取りで見た増え方は、この率のぶんだけ薄まります。**
    """
    g0 = base_annual_man * rate_for(0)
    g1 = base_annual_man * rate_for(months_from_65)
    n0 = g0 * _clamp_rate(g0)
    n1 = g1 * _clamp_rate(g1)
    dg = g1 - g0
    marginal = None if abs(dg) < 1e-12 else (n1 - n0) / dg
    return {
        "開始": Plan(months_from_65, rate_for(months_from_65)).age_text,
        "月数": months_from_65,
        "倍率": rate_for(months_from_65),
        "額面_万": g1,
        "手取り_万": n1,
        "平均の手取り率": _clamp_rate(g1),
        "限界の手取り率": marginal,
        # 平均の率で増えると思った場合との差（年額・円）
        "平均の率で見込んだ手取り増_円": round((n0 / g0 * dg) * 10_000) if dg else 0,
        "実際の手取り増_円": round((n1 - n0) * 10_000),
    }


def marginal_net_grid(base_annual_man: float = 180.0,
                      step_months: int = 12) -> list[dict]:
    """繰下げの各段で、限界の手取り率がどこまで落ちるか。"""
    return [marginal_net_rate(m, base_annual_man)
            for m in range(step_months, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1,
                           step_months)]


def marginal_worst(base_annual_man: float = 180.0) -> dict:
    """**限界の手取り率がいちばん低くなる開始月**（1か月きざみで全部見る）。

    1か月ずつ刻んだ「その1か月ぶんの限界」も一緒に出します
    （前の月からの差ぶんに、どれだけの率が掛かるか）。
    """
    rows = []
    for m in range(1, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1):
        ga = base_annual_man * rate_for(m - 1)
        gb = base_annual_man * rate_for(m)
        na = ga * _clamp_rate(ga)
        nb = gb * _clamp_rate(gb)
        rows.append({
            "月数": m,
            "開始": Plan(m, rate_for(m)).age_text,
            "その1か月の限界の手取り率": (nb - na) / (gb - ga),
            "65歳からの限界の手取り率": marginal_net_rate(m, base_annual_man)["限界の手取り率"],
        })
    low = min(rows, key=lambda r: r["その1か月の限界の手取り率"])
    return {
        "行": rows,
        "いちばん低い月": low,
        "75歳での_65歳からの限界": rows[-1]["65歳からの限界の手取り率"],
        "65歳の平均の手取り率": _clamp_rate(base_annual_man),
    }


# ---------------- 寿命が分からないときの開始年齢（最大の取りこぼしを最小に）----
def regret_table(base_annual_man: float = 180.0,
                 span_ages: tuple[int, int] = (75, 100),
                 step_months: int = 12,
                 net: bool = False) -> list[dict]:
    """**候補の開始月ごとに、「外したときの取りこぼし」の最大値**を出す。

    既存の節は全部「何歳まで生きるかを**決め打ちして**最適を出す」形です。
    **決め打ちできないから誰も決められない**、というのが本当の問題なので、
    ここでは向きを変えます ——
    **寿命を 75〜100歳のどこかとしか言えないとき、
    どの開始月なら「いちばん外したときの損」がいちばん小さいか。**

    取りこぼし（後悔）＝ その寿命での最善の総額 − この開始での総額。
    金額の取りこぼしは長生きするほど大きくなるので、
    **割合（最善に対して何パーセント取りこぼすか）でも同じ表を出します。**
    どちらで測るかで答えが変わるなら、それ自体が結果です。
    """
    lo, hi = span_ages
    lifespans = list(range(lo * 12, hi * 12 + 1))
    best_by_span = {
        um: max(lifetime(m, base_annual_man, um, net=net)
                for m in range(-(BASE_AGE - MIN_ADVANCE_AGE) * 12,
                               (MAX_DEFER_AGE - BASE_AGE) * 12 + 1))
        for um in lifespans
    }
    rows = []
    for m in range(-(BASE_AGE - MIN_ADVANCE_AGE) * 12,
                   (MAX_DEFER_AGE - BASE_AGE) * 12 + 1, step_months):
        worst_yen, worst_yen_at = -1.0, None
        worst_pct, worst_pct_at = -1.0, None
        for um in lifespans:
            best = best_by_span[um]
            gap = best - lifetime(m, base_annual_man, um, net=net)
            if gap > worst_yen:
                worst_yen, worst_yen_at = gap, um
            pct = 0.0 if best <= 0 else gap / best
            if pct > worst_pct:
                worst_pct, worst_pct_at = pct, um
        rows.append({
            "開始": Plan(m, rate_for(m)).age_text,
            "月数": m,
            "最大の取りこぼし_円": round(worst_yen * 10_000),
            "そのときの寿命": _age_text(worst_yen_at),
            "最大の取りこぼし_割合": worst_pct,
            "割合が最大の寿命": _age_text(worst_pct_at),
        })
    return rows


def minimax_start(base_annual_man: float = 180.0,
                  span_ages: tuple[int, int] = (75, 100),
                  net: bool = False) -> dict:
    """**最大の取りこぼしを最小にする開始月**（1か月きざみで181通り全部）。

    金額で測った答えと、割合で測った答えの**両方**を返します。
    """
    rows = regret_table(base_annual_man, span_ages, step_months=1, net=net)
    by_yen = min(rows, key=lambda r: r["最大の取りこぼし_円"])
    by_pct = min(rows, key=lambda r: r["最大の取りこぼし_割合"])
    at65 = next(r for r in rows if r["月数"] == 0)
    at70 = next(r for r in rows if r["月数"] == 60)
    at60 = next(r for r in rows if r["月数"] == -60)
    at75 = next(r for r in rows if r["月数"] == 120)
    return {
        "寿命の帯": f"{span_ages[0]}〜{span_ages[1]}歳",
        "金額で選ぶ": by_yen,
        "割合で選ぶ": by_pct,
        "65歳開始": at65,
        "70歳繰下げ": at70,
        "75歳繰下げ": at75,
        "60歳繰上げ": at60,
    }


# ---------------- 手取り率の前提を振ると、結論はどこで裏返るか ---------------
def _net_rate_scaled(annual_man: float, k: float) -> float:
    """手取り率の**下がり方**を k 倍にした前提。k=1 がいまの前提、k=0 は額面。"""
    return 1.0 - k * (1.0 - _clamp_rate(annual_man))


def lifetime_scaled(months_from_65: int, base_annual_man: float,
                    until_months: int, k: float) -> float:
    """`lifetime` の手取り版を、手取り率の前提 k で解いたもの（万円）。"""
    start_months = BASE_AGE * 12 + months_from_65
    if until_months <= start_months:
        return 0.0
    annual = base_annual_man * rate_for(months_from_65)
    return annual * _net_rate_scaled(annual, k) * (until_months - start_months) / 12


def assumption_flip(base_annual_man: float = 180.0, until_age: int = 85,
                    months_from_65: int = 60,
                    k_max: float = 6.0) -> dict:
    """**この結論は、こちらの前提がどれだけ違っていたら裏返るか。**

    手取り率（`NET_RATE_POINTS`）は制度の値ではなく**こちらが置いた前提**です。
    節は毎回それを画面に出していますが、**「その前提がどれくらい違ったら
    答えが変わるのか」は、どの節も答えていません。**

    ここでは下がり方だけを k 倍に振ります（k=0 で額面と同じ、k=1 がいまの前提）。
    そして「繰下げが65歳受給に負ける」最初の k を、二分法で解きます。
    **k が1に近いほど、その結論は前提に寄りかかっている**ということです。
    """
    um = until_age * 12

    def diff(k: float) -> float:
        return (lifetime_scaled(months_from_65, base_annual_man, um, k)
                - lifetime_scaled(0, base_annual_man, um, k))

    d0 = diff(0.0)
    d1 = diff(1.0)
    dmax = diff(k_max)
    flip = None
    if d0 > 0 and dmax < 0:
        lo, hi = 0.0, k_max
        for _ in range(200):
            mid = (lo + hi) / 2
            if diff(mid) > 0:
                lo = mid
            else:
                hi = mid
        flip = (lo + hi) / 2
    return {
        "開始": Plan(months_from_65, rate_for(months_from_65)).age_text,
        "何歳まで": until_age,
        "65歳の年額_万": base_annual_man,
        "額面での差_円": round(d0 * 10_000),
        "いまの前提での差_円": round(d1 * 10_000),
        "裏返る_k": flip,
        "余裕_倍": None if flip is None else flip - 1.0,
    }


def assumption_flip_grid(base_annual_man: float = 180.0,
                         until_ages: tuple[int, ...] = (80, 82, 85, 88, 90, 95),
                         months_from_65: int = 60) -> list[dict]:
    """裏返る k を、見込む寿命べつに並べる。"""
    return [assumption_flip(base_annual_man, a, months_from_65)
            for a in until_ages]


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

    print(f"\n=== 生まれた日が1日ちがうと、繰上げの年額はいくら変わるか"
          f"（65歳で年{base:.1f}万円の場合）===")
    print("  減額率は**昭和37年4月1日以前に生まれた人が0.5%、翌日以降が0.4%**。"
          "1日ちがうだけで、**生涯そのままの倍率**が変わります。")
    print(f"{'開始':>9s} {'倍率(4月2日以降)':>16s} {'倍率(4月1日以前)':>16s} "
          f"{'年額の差':>9s} {'85歳まで生きたときの差':>21s}")
    for r in birth_gap_grid(base):
        print(f"{r['開始']:>9s} {r['倍率_新']:15.3f} {r['倍率_旧']:15.3f} "
              f"{r['年の差']:8.1f}万 {r['生涯の差']:20.1f}万")
    print(f"  **減る額の比は、繰り上げた月数によりません** —— "
          f"0.5% ÷ 0.4% ＝ {birth_gap_ratio(60):.2f}倍で、"
          f"1か月でも60か月でも同じです。")

    print(f"\n=== 生まれた日が1日ちがうと、65歳開始に追い抜かれる年齢が何年ずれるか"
          f"（65歳で年{base:.1f}万円の場合）===")
    print("  繰り上げた人は先に受け取りはじめますが、いつかは65歳開始に追い抜かれます。"
          "**減額が深いほど、追い抜かれるのが早い。**")
    print(f"{'開始':>9s} {'追い抜かれる(4月2日以降)':>24s} {'追い抜かれる(4月1日以前)':>24s} "
          f"{'ずれ':>7s}")
    for r in birth_gap_grid(base):
        print(f"{r['開始']:>9s} {r['分岐点_新']:>24s} {r['分岐点_旧']:>24s} "
              f"{r['ずれ_月']:5d}か月")
    print("  **ずれは、繰り上げた月数によらず ちょうど50か月（4年2か月）です。**"
          "厳密に解くと追い抜かれる月齢は「1030 − 繰上げ月数」と「980 − 繰上げ月数」で、"
          "**繰上げ月数が引き算で消えます。**")

    print(f"\n=== 繰下げを「投資」とみなしたときの年利（65歳で年{base:.1f}万円・85歳まで）===")
    print("  繰下げの説明は「1か月あたり0.7パーセント増える」で止まっています。"
          "**増える率は一定なのに、投資としての年利は待つほど下がります。**")
    print("  待っているあいだは、65歳開始なら入っていたはずの額が入りません。"
          "**それを差し出して、終身の増額を買っている**と見て、"
          "差し引きが釣り合う割引率（内部収益率）を月ごとに解いたものです。")
    print(f"{'開始':>9s} {'倍率':>6s} {'年利(額面)':>10s} {'年利(手取り)':>12s} {'差':>8s}")
    for r in irr_grid(base, 85, 12):
        g = "—" if r["年利_額面"] is None else f"{r['年利_額面']:.2f}%"
        nv = "—" if r["年利_手取り"] is None else f"{r['年利_手取り']:.2f}%"
        d = "—" if r["差_ポイント"] is None else f"{r['差_ポイント']:.2f}pt"
        print(f"{r['開始']:>9s} {r['倍率']:>6.3f} {g:>10s} {nv:>12s} {d:>8s}")
    print("  **「—」は、85歳までに差し出したぶんを取り返せないという意味です。**"
          "率がいくら高くても、受け取る年数が足りません。")

    last_g = irr_last_month(base, 85, net=False)
    last_n = irr_last_month(base, 85, net=True)
    print(f"\n=== 85歳まで生きるなら、繰下げが元を取れる最後の月は"
          f"「額面{last_g['最後の開始']}」「手取り{last_n['最後の開始']}」===")
    print(f"  額面で見ると {last_g['最後の開始']}開始が年利 {last_g['そこでの年利']:.2f}% で、"
          f"**{last_g['次の月の開始']}開始からは1円も取り返せません。**")
    print(f"  手取りで見ると、その境目は **{last_n['最後の開始']}** まで前へ動きます"
          f"（年利 {last_n['そこでの年利']:.2f}%）—— "
          f"**{last_g['最後の月数'] - last_n['最後の月数']}か月ぶん**、"
          f"手取りで計算するだけで繰下げの上限が縮みます。")
    print("  よく見る「70歳まで繰り下げると得」は額面の話です。"
          f"手取りだと、{last_n['次の月の開始']}から先は 85歳までの範囲で成立しません。")

    span = [r for r in irr_by_lifespan(60, base, 80, 100, 2)
            if r["年利_額面"] is not None]
    lo_r, hi_r = span[0], span[-1]
    print(f"\n=== 70歳まで繰り下げたときの年利は、寿命で "
          f"{lo_r['年利_額面']:.2f}% から {hi_r['年利_額面']:.2f}% まで動く"
          f"（65歳で年{base:.1f}万円）===")
    print(f"  同じ選択でも、何歳まで生きるかで年利は "
          f"**{hi_r['年利_額面'] / lo_r['年利_額面']:.0f}倍**ちがいます。"
          "**繰下げは率の決まった商品ではありません。**")
    print(f"{'何歳まで':>8s} {'年利(額面)':>10s} {'年利(手取り)':>12s}")
    for r in irr_by_lifespan(60, base, 80, 100, 2):
        g = "—" if r["年利_額面"] is None else f"{r['年利_額面']:.2f}%"
        nv = "—" if r["年利_手取り"] is None else f"{r['年利_手取り']:.2f}%"
        print(f"{r['何歳まで']:>6d}歳 {g:>10s} {nv:>12s}")

    worst = irr_worst_base(60, 85)
    print(f"\n=== 繰下げの年利がいちばん低くなる年金額は"
          f"{worst['谷の年額_万']:.0f}万円 —— 端ではなく途中にある ===")
    print(f"  **額面の年利は年金額によりません**（どの年額でも "
          f"{worst['年利_額面']:.2f}%）。差し出す額と受け取る額に同じ数が掛かるので、"
          "割引率の式から約分で消えます。")
    print(f"  **動くのは手取りだけです。** 下の端 {worst['下の端_万']:.0f}万で "
          f"{worst['下の端の年利_手取り']:.2f}%、"
          f"谷の {worst['谷の年額_万']:.0f}万で **{worst['谷の年利_手取り']:.2f}%**、"
          f"上の端 {worst['上の端_万']:.0f}万で {worst['上の端の年利_手取り']:.2f}%。")
    print("  **両端で額面に戻り、間だけ落ちます。** 下の端は公的年金等控除と"
          "基礎控除でほぼ課税されないから、上の端は手取り率が頭打ちで一定になるから。"
          f"その間だけ、繰り下げて増えたぶんに元より重い率が掛かります"
          f"（谷での落差 {worst['谷と額面の差_ポイント']:.2f}ポイント）。")

    ib_g = irr_best_months(base, 85, net=False)
    bs_g = best_start(85 * 12, base, net=False)
    bs_n = best_start(85 * 12, base, net=True)
    print(f"\n=== 年利がいちばん高い開始と、総額がいちばん多い開始は別の月 ===")
    print(f"  年利で選ぶなら **{ib_g['開始']}**（{ib_g['年利']:.2f}%）—— "
          "**繰り下げる月数がいちばん短いところ**です。")
    print(f"  総額で選ぶなら **{Plan(bs_g, rate_for(bs_g)).age_text}**（額面）／"
          f"**{Plan(bs_n, rate_for(bs_n)).age_text}**（手取り）。"
          "85歳まで生きる前提は同じです。")
    print("  **どちらが正しいという話ではありません。** 年利は「差し出したものに対して"
          "どれだけの率で戻るか」、総額は「いくら受け取るか」で、問いが違います。"
          "繰下げの説明が率だけを言うとき、答えているのは前者だけです。")

    mw = marginal_worst(base)
    m70 = marginal_net_rate(60, base)
    m75 = marginal_net_rate(120, base)
    print(f"\n=== 繰り下げて増えた額面のうち、手取りに残るのは"
          f"{m70['限界の手取り率'] * 100:.1f}パーセント（70歳・65歳で年{base:.0f}万円）===")
    print(f"  前提: 手取り率は年額から補間（**制度の値ではなくこちらの前提**）/ "
          f"65歳の年額 {base:.0f}万円")
    print(f"  表に出ている手取り率は**平均の率**です —— 年{base:.0f}万円で "
          f"{mw['65歳の平均の手取り率'] * 100:.1f}パーセントというのは、"
          f"{base:.0f}万円**全体**に掛かる率のこと。")
    print("  **繰下げの説明が答えていないのは、増えたぶんに掛かる率のほうです。**"
          "年額が上がると平均の率そのものが下がるので、"
          "**増えた額面に掛かる率は、平均より必ず低くなります。**")
    print(f"{'開始':>9s} {'額面':>9s} {'平均の率':>8s} {'増えたぶんの率':>13s} "
          f"{'平均の率で見込むと':>17s} {'実際':>12s} {'差':>12s}")
    for r in marginal_net_grid(base):
        print(f"{r['開始']:>9s} {r['額面_万']:8.1f}万 {r['平均の手取り率'] * 100:7.1f}% "
              f"{r['限界の手取り率'] * 100:12.1f}% "
              f"{r['平均の率で見込んだ手取り増_円']:>16,d}円 "
              f"{r['実際の手取り増_円']:>11,d}円 "
              f"{r['実際の手取り増_円'] - r['平均の率で見込んだ手取り増_円']:>+11,d}円")
    print(f"  **75歳まで繰り下げると、増えた額面 "
          f"{(m75['額面_万'] - base) * 10_000:,.0f}円 のうち手取りに残るのは "
          f"{m75['限界の手取り率'] * 100:.1f}パーセント**"
          f"（平均の率 {m75['平均の手取り率'] * 100:.1f}パーセントで見込むと、"
          f"年 {m75['平均の率で見込んだ手取り増_円'] - m75['実際の手取り増_円']:,d}円 多く見えます）。")
    print(f"  1か月きざみで見ると、いちばん低いのは "
          f"**{mw['いちばん低い月']['開始']}に入る1か月**で "
          f"{mw['いちばん低い月']['その1か月の限界の手取り率'] * 100:.1f}パーセント。"
          "**「1か月0.7パーセント増える」は額面の話**で、"
          "手取りで見た増え方はこの率のぶんだけ薄まります。")

    mm = minimax_start(base, (75, 100), net=False)
    print(f"\n=== 寿命が{mm['寿命の帯']}としか言えないとき、いちばん損の小さい開始は"
          f"**{mm['金額で選ぶ']['開始']}**（65歳でも70歳でも75歳でもない）===")
    print(f"  前提: 65歳で年{base:.0f}万円 / 額面で比べる / "
          f"寿命は {mm['寿命の帯']} の1か月きざみ301通り / "
          f"開始は60歳0か月〜75歳0か月の181通り")
    print("  ほかの節は「何歳まで生きるか」を決め打ちして最適を出しています。"
          "**決め打ちできないから誰も決められない**、というのが本当の問題なので、"
          "ここでは向きを変えます —— **どの開始なら、いちばん外したときの損が"
          "いちばん小さいか。**")
    print("  取りこぼし ＝ その寿命での最善の総額 − この開始での総額。"
          "**金額で測るか、割合で測るかで答えが変わります**（どちらも下に出します）。")
    print(f"{'開始':>9s} {'最大の取りこぼし':>15s} {'そのときの寿命':>14s} "
          f"{'割合で見た最大':>13s} {'その寿命':>10s}")
    for r in regret_table(base, (75, 100), step_months=12, net=False):
        print(f"{r['開始']:>9s} {r['最大の取りこぼし_円']:>14,d}円 "
              f"{r['そのときの寿命']:>14s} "
              f"{r['最大の取りこぼし_割合'] * 100:12.1f}% "
              f"{r['割合が最大の寿命']:>10s}")
    print(f"  **金額で選ぶと {mm['金額で選ぶ']['開始']}**"
          f"（最大の取りこぼし {mm['金額で選ぶ']['最大の取りこぼし_円']:,d}円）、"
          f"**割合で選ぶと {mm['割合で選ぶ']['開始']}**"
          f"（同 {mm['割合で選ぶ']['最大の取りこぼし_割合'] * 100:.1f}パーセント）。"
          "**どちらも「よく言われる年齢」ではありません。**")
    print(f"  比べる相手: 65歳開始は最大 "
          f"{mm['65歳開始']['最大の取りこぼし_円']:,d}円／"
          f"{mm['65歳開始']['最大の取りこぼし_割合'] * 100:.1f}パーセント、"
          f"70歳繰下げは {mm['70歳繰下げ']['最大の取りこぼし_円']:,d}円／"
          f"{mm['70歳繰下げ']['最大の取りこぼし_割合'] * 100:.1f}パーセント、"
          f"75歳繰下げは {mm['75歳繰下げ']['最大の取りこぼし_円']:,d}円／"
          f"{mm['75歳繰下げ']['最大の取りこぼし_割合'] * 100:.0f}パーセント"
          f"（75歳で亡くなると1円も受け取れないので、取りこぼしは全額です）。")

    af85 = assumption_flip(base, 85, 60)
    print(f"\n=== 「70歳まで繰り下げたほうが得」は、手取り率の前提が"
          f"{af85['裏返る_k']:.2f}倍 きつくなると消える（85歳まで生きる場合）===")
    print(f"  前提: 65歳で年{base:.0f}万円 / 手取り率の**下がり方**だけを k 倍に振る"
          f"（k=0 で額面と同じ、k=1 がこの計算で使っている前提）")
    print("  手取り率は制度の値ではなく**こちらが置いた前提**です。"
          "ほかの節は毎回それを画面に出していますが、"
          "**「その前提がどれくらい違ったら答えが変わるのか」には答えていません。**")
    print(f"{'何歳まで':>8s} {'額面での差':>13s} {'いまの前提での差':>17s} "
          f"{'裏返る k':>10s} {'いまの前提からの余裕':>20s}")
    for r in assumption_flip_grid(base):
        k = "—" if r["裏返る_k"] is None else f"{r['裏返る_k']:.2f}倍"
        yoyu = "—" if r["余裕_倍"] is None else f"{r['余裕_倍'] * 100:+.0f}%"
        print(f"{r['何歳まで']:>6d}歳 {r['額面での差_円']:>12,d}円 "
              f"{r['いまの前提での差_円']:>16,d}円 {k:>10s} {yoyu:>20s}")
    print(f"  **85歳までなら、余裕は "
          f"{af85['余裕_倍'] * 100:.0f}パーセントしかありません。** "
          "手取り率の下がり方をこれ以上きつく置くと、"
          "**同じ計算が逆の答えを出します。**")
    print("  「—」は、額面の時点で既に負けているか、k を6倍まで振っても裏返らないという意味です。"
          "**82歳までの行を見ること** —— 額面ではぎりぎり勝っているのに、"
          "いまの前提では既に負けています。")
