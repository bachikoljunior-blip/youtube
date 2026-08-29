"""住宅ローン控除で、**実際には取り戻せない額**を計算する。

狙いは制度の紹介ではない。「控除率0.7パーセント・最大13年」はどこにでもある。
ここで出したいのは、その控除可能額のうち **いくらが宙に浮くか** ——
つまり「取りこぼし」を、課税所得とローン残高の組み合わせで全部出したもの。

--------------------------------------------------------------------------
なぜ取りこぼしが出るのか
--------------------------------------------------------------------------
住宅ローン控除は **税額控除** で、納めた税金から差し引く形をとる。
だから **納めている税金より多くは戻らない。**

年末残高3000万円なら控除可能額は21万円だが、その年の所得税が12万円しかなければ、
所得税からは12万円しか引けない。残りの9万円は住民税に回るが、そこにも上限がある。

  住民税から引ける額 ＝ 課税総所得金額等の5パーセント、**ただし97,500円まで**

この上限に当たると、残りはどこからも戻らない。**繰り越しもできない。**
広告や記事に出る「最大○○万円」は控除可能額であって、受け取れる額ではない。

--------------------------------------------------------------------------
この計算が扱わないもの（意図的に外している）
--------------------------------------------------------------------------
**借入限度額は入れていない。** 住宅の種類と入居した年で変わり、改正も続いている。
確定した数字を確認できないものは使わない、という方針どおり、ここでは残高を
**入力として受け取る**。視聴者が自分の残高を入れる形にすれば、限度額の改正に
左右されずに答えが出る。

**年収からの換算も主役にしない。** 給与所得控除は令和2年以降変わっていないが、
基礎控除は改正が続いていて、令和8年分の確定した額を確認できていない。
だから計算の主役は **課税総所得金額**（源泉徴収票に載っている数字）にする。
視聴者は手元の紙を見ればよく、こちらが改正を追う必要もない。

これは制約ではなく、**そのほうが正確で、視聴者が自分で追試できる**という理由。

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
租税特別措置法の住宅借入金等特別控除。控除率 **0.7パーセント**（令和4年入居分から）。
所得税から引ききれない分の住民税からの控除上限は
**課税総所得金額等の5パーセント、かつ97,500円**（令和4年入居分から）。

所得税の速算表は平成27年分以降のもので、長く動いていない。
復興特別所得税（所得税額の2.1パーセント）は、住宅ローン控除を差し引いた
**あとの**所得税額に掛かる。ここも計算に入れている。
"""
from __future__ import annotations

from dataclasses import dataclass

from . import _checks

ASSUMPTIONS = [
    "控除率は0.7パーセントで計算しています。令和4年に入居した分からの率です",
    "課税総所得金額は源泉徴収票の「課税される所得金額」です。年収ではありません",
    "住民税から引ける額は、課税総所得金額等の5パーセントかつ9万7500円が上限です",
    "所得税から引ききれず住民税の上限にも当たった分は、どこからも戻りません。翌年に繰り越すこともできません",
    "借入限度額は住宅の種類と入居した年で変わるため、この計算には入れていません。年末残高をそのまま使っています",
    "所得税の速算表は平成27年分以降のものです",
    "復興特別所得税は、住宅ローン控除を差し引いたあとの所得税額に2.1パーセント掛かるものとしています",
    "ふるさと納税や医療費控除など、他の控除は入れていません",
    "返済は元利均等返済で、返済期間は35年、金利は年1.0パーセントとして置いています。期間と金利を変えた節では、その値を表に書いています",
    "繰り上げ返済は期間短縮型（毎月の返済額は変えず、残高だけを減らす形）で置いています。返済額軽減型なら、失う控除はこれより小さくなります",
    "2人で借りる節では、各自の年末残高が持分の比でそのまま立つものとして置いています。持分と実際の負担額がずれている場合は、この計算どおりにはなりません",
    "2人で借りる節では、2人とも控除の要件を満たして初年度に確定申告することを前提にしています。片方が要件を満たさない場合は、その人の枠は使えません",
]

CREDIT_RATE = 0.007            # 控除率 0.7%
RESIDENT_CAP_RATE = 0.05       # 住民税から引ける額は課税総所得等の5%まで
RESIDENT_CAP_YEN = 97_500      # かつ、この額まで
RECONSTRUCTION_TAX = 0.021     # 復興特別所得税

# 所得税の速算表（平成27年分以降）。(課税所得の上限, 税率, 控除額)
BRACKETS: list[tuple[int, float, int]] = [
    (1_950_000, 0.05, 0),
    (3_300_000, 0.10, 97_500),
    (6_950_000, 0.20, 427_500),
    (9_000_000, 0.23, 636_000),
    (18_000_000, 0.33, 1_536_000),
    (40_000_000, 0.40, 2_796_000),
    (10**12, 0.45, 4_796_000),
]


@dataclass(frozen=True)
class Result:
    """ある年の1回ぶんの結果。円単位。"""

    balance: int          # 年末のローン残高
    taxable: int          # 課税総所得金額
    credit: int           # 控除可能額（残高 × 0.7%）
    from_income_tax: int  # 所得税から引けた額
    from_resident: int    # 住民税から引けた額
    lost: int             # どこからも戻らなかった額

    @property
    def recovered(self) -> int:
        return self.from_income_tax + self.from_resident

    @property
    def lost_ratio(self) -> float:
        return self.lost / self.credit if self.credit else 0.0


def income_tax(taxable: int) -> int:
    """課税総所得金額から所得税額（復興特別所得税を除く）を出す。"""
    taxable = max(0, taxable)
    for cap, rate, deduct in BRACKETS:
        if taxable <= cap:
            return max(0, int(taxable * rate - deduct))
    return 0


def check_tables() -> None:
    """速算表と上限の値を、法令が名指ししている点で確かめる。

    表の書き写しは列ずれと桁落ちが起きるが、目で読み直しても見つからない。
    境目の値だけを不変条件に置き、外れたら止める。
    """
    if CREDIT_RATE != 0.007:
        raise ValueError(f"控除率が {CREDIT_RATE}。令和4年入居分からの率は 0.007")
    if RESIDENT_CAP_YEN != 97_500:
        raise ValueError(f"住民税からの控除上限が {RESIDENT_CAP_YEN}。法令の値は 97500")
    if RESIDENT_CAP_RATE != 0.05:
        raise ValueError(f"住民税からの控除上限の率が {RESIDENT_CAP_RATE}。法令の値は 0.05")

    # 速算表の境目。境目ちょうどの額は、下の区分の税率で計算される。
    for taxable, want in (
        (1_950_000, 97_500),      # 195万 × 5%
        (3_300_000, 232_500),     # 330万 × 10% - 97,500
        (6_950_000, 962_500),     # 695万 × 20% - 427,500
        (9_000_000, 1_434_000),   # 900万 × 23% - 636,000
        (18_000_000, 4_404_000),  # 1800万 × 33% - 1,536,000
    ):
        got = income_tax(taxable)
        if got != want:
            raise ValueError(f"課税所得{taxable:,}円の所得税が {got:,}円。速算表では {want:,}円")

    # 速算表の形・境目の連続・全体の向きは `_checks` にまとめてある
    # （12本が同じものを別々に書いていた）。上の「手で解いた値」は残すこと ——
    # あちらは**写し間違いそのもの**を捕まえていて、形の検査では代わりにならない。
    _checks.bracket_table(BRACKETS, income_tax, name="所得税の速算表")
    _checks.never_decreases(income_tax, range(0, 20_000_000, 250_000),
                            "課税所得に対する所得税額")

    # 所得税が控除可能額を上回るなら、取りこぼしは出ない
    rich = compute(30_000_000, 20_000_000)
    if rich.lost != 0:
        raise ValueError("所得税が十分にあるのに取りこぼしが出ている")

    # 課税所得が0なら、どこからも戻らない
    poor = compute(30_000_000, 0)
    if poor.recovered != 0 or poor.lost != poor.credit:
        raise ValueError("課税所得0で戻る額が出ている")

    # 住民税からの控除は上限を超えない
    mid = compute(40_000_000, 3_000_000)
    if mid.from_resident > RESIDENT_CAP_YEN:
        raise ValueError(f"住民税からの控除が上限を超えている: {mid.from_resident}")

    # --- 2026-08-17 に足した節ぶん（`docs/JOURNAL.md`）------------------
    # **主張そのものを検査に置くこと。**「上限が入れ替わる点」「期間が短いほど減る」
    # 「利息の2%」は、どれも汎用の検査では守れません。
    sw = resident_cap_switch()
    _checks.close(sw, 1_950_000, "住民税の上限が入れ替わる課税所得")
    # **ここが節の主張です** —— 入れ替わる点が、所得税5%の区分の上限と同じ1点であること
    if sw != BRACKETS[0][0]:
        raise _checks.TableError(
            f"住民税の上限が入れ替わる点 {sw:,}円 が、所得税の第1区分の上限 "
            f"{BRACKETS[0][0]:,}円 と違います。**節の主張はこの一致そのもの**です")
    for taxable, want in ((1_000_000, "5パーセント"), (3_000_000, "97,500円")):
        if resident_cap_of(taxable)[1] != want:
            raise _checks.TableError(f"課税所得{taxable:,}円で効く上限が {want} ではない")

    # 返済期間が短いほど、13年で戻る額は小さい（残高が早く減るので）
    _checks.increases_with(
        lambda term: thirteen_years(30_000_000, 3_000_000,
                                    term_years=int(term))["実際に戻る合計"],
        [20, 25, 30, 35],
        "返済期間が長いのに、13年で戻る額が増えていない")

    # 金利が高いほど利息も控除も増える。**ただし控除の増えは利息の増えの一部**
    lo_c = thirteen_years(30_000_000, 6_000_000, annual_rate=0.005)["実際に戻る合計"]
    hi_c = thirteen_years(30_000_000, 6_000_000, annual_rate=0.030)["実際に戻る合計"]
    lo_i, hi_i = interest_paid(30_000_000, 0.005), interest_paid(30_000_000, 0.030)
    _checks.greater(hi_i - lo_i, hi_c - lo_c,
                    "増えた利息が、増えた控除より小さい（金利で得をすることになる）")
    if not 0.01 <= (hi_c - lo_c) / (hi_i - lo_i) <= 0.05:
        raise _checks.TableError(
            "取り返し率が1〜5パーセントの外に出ました。**節の主張が『2パーセント前後』**"
            "なので、印字より先にここで止めます")

    # 繰上げ返済は控除を減らす。**早い年ほど大きく減る**（残る年数が多いので）
    _checks.decreases_with(
        lambda y: prepay_loss(30_000_000, 6_000_000, 5_000_000, int(y))["失う控除"],
        [1, 3, 5, 8, 11],
        "繰上げが遅いのに、失う控除が減っていない")
    if prepay_loss(30_000_000, 6_000_000, 5_000_000, 1)["失う控除"] <= 0:
        raise _checks.TableError("繰上げ返済で失う控除が0以下。**節の主張と符号が逆**です")

    # --- 節6（2026-08-25）: 戻せる枠は195万円で折れる -----------------------
    switch = resident_cap_switch()
    _checks.rounding(switch, int(RESIDENT_CAP_YEN / RESIDENT_CAP_RATE),
                     "住民税の上限が切り替わる課税総所得")
    # (1) **195万円以下では、住民税の上限が所得税額とぴったり同じ**
    #     （どちらも 課税総所得 × 5%）。だから枠はちょうど2倍になる
    for t in (500_000, 1_000_000, 1_500_000, 1_940_000, switch):
        r = relief_room(t)
        if r["住民税から引ける上限"] != r["所得税額"]:
            raise _checks.TableError(
                f"課税総所得{t:,}円で、住民税の上限 {r['住民税から引ける上限']:,} と"
                f"所得税額 {r['所得税額']:,} が一致していません")
        _checks.rounding(r["枠が所得税の何倍か"], 2.0,
                         f"課税総所得{t:,}円での枠の倍率")
    # (2) **195万円を超えると倍率は落ち続ける**（住民税だけが 97,500円 で止まる）
    _checks.decreases_with(
        lambda t: relief_room(int(t))["枠が所得税の何倍か"],
        [switch + 10_000, 2_500_000, 3_300_000, 4_500_000, 6_000_000],
        "195万円より上で、枠の倍率が落ちていない")
    for t in (2_500_000, 6_000_000):
        if relief_room(t)["住民税から引ける上限"] != RESIDENT_CAP_YEN:
            raise _checks.TableError(
                f"課税総所得{t:,}円で、住民税の上限が {RESIDENT_CAP_YEN:,}円 で"
                "止まっていません")
    d = relief_room_doubling()
    _checks.greater(d["折れる前の倍率"] - d["折れたあとの倍率"], 0.5,
                    "195万円の前後で、枠の倍率の落ち幅が")
    # (3) **枠は残高によらない。** どの残高で当てても、戻る額はこれを超えない
    for t in (1_000_000, 3_300_000, 6_000_000):
        room = relief_room(t)["戻せる枠"]
        for bal in (10_000_000, 50_000_000, 100_000_000):
            got = compute(bal, t).recovered
            if got > room:
                raise _checks.TableError(
                    f"課税総所得{t:,}円・残高{bal:,}円で、戻る額 {got:,} が"
                    f"枠 {room:,} を超えました")
        _checks.rounding(compute(relief_room(t)["使い切るのに要る残高"] + 10_000,
                                 t).recovered, room,
                         f"課税総所得{t:,}円で、枠を使い切ったときに戻る額")
    _check_pair()


def _check_pair() -> None:
    """節7（ペアローンの持分）の等式。**通ると思っている式ほど、先に書くこと。**

    2026-08-26 に書いたところ、(4) が最初は落ちました ——
    「半分ずつで損しない残高」を**2人の枠の合計**から出していたためです。
    実際に効いているのは**小さいほうの枠だけ**で、大きいほうは1円も関係しません。
    **検査に書かなければ、そのまま動画に出ていました。**
    """
    pairs = ((3_000_000, 1_500_000), (6_000_000, 1_000_000), (2_000_000, 2_000_000))
    for ta, tb in pairs:
        room = pair_room_ratio(ta, tb)
        # (1) **枠は人ごとに立つ。** 2人ぶんの合計を超えて戻ることはない
        for bal in (10_000_000, 45_000_000, 100_000_000):
            best = best_share(bal, ta, tb)
            if best["最適で戻る合計"] > room["枠の合計"]:
                raise _checks.TableError(
                    f"課税総所得{ta:,}/{tb:,}・残高{bal:,}円で、最適で戻る合計 "
                    f"{best['最適で戻る合計']:,} が枠の合計 {room['枠の合計']:,} を超えました")
            # (2) **最適は、半分ずつを下回らない**（半分ずつも候補の1つなので）
            _checks.greater(best["最適で戻る合計"] - best["半分ずつで戻る合計"] + 1,
                            0.0, f"残高{bal:,}円で、最適と半分ずつの差が")
        # (3) **2人で枠を使い切る残高を十分に超えたら、最適はちょうど枠の合計**
        big = room["2人で使い切るのに要る残高"] * 2
        _checks.rounding(best_share(big, ta, tb)["最適で戻る合計"],
                         room["枠の合計"],
                         f"課税総所得{ta:,}/{tb:,}で、枠を使い切ったときの合計")
        # (3b) **ただし「ちょうど」の残高では、1パーセント刻みが枠に届きません。**
        #      2026-08-26 に (3) がここで落ちて分かったことです ——
        #      両方が満たされる持分の幅は `枠A/(0.007×残高)` 〜 `1−枠B/(0.007×残高)` で、
        #      残高が使い切りにちょうどのときは**この幅が1パーセントより狭くなる**。
        #      **落ちたのは検査ではなく、刻みのほうです。** 実測（課税600万/100万）:
        #      969,529円 対 970,000円 ＝ **471円 届かない。**
        just = room["2人で使い切るのに要る残高"] + 1_000_000
        gap = room["枠の合計"] - best_share(just, ta, tb)["最適で戻る合計"]
        _checks.greater(int(just * 0.01 * CREDIT_RATE) + 1, float(gap),
                        f"課税総所得{ta:,}/{tb:,}で、刻み1つぶんより届かない額が")
        # (4) **半分ずつで損しない残高は、小さいほうの枠だけで決まる**
        safe = half_safe_balance(ta, tb)
        if pair_split(safe["半分ずつで損しない残高"], ta, tb, 0.5)["取りこぼし合計"] != 0:
            raise _checks.TableError(
                f"課税総所得{ta:,}/{tb:,}で、半分ずつの上限 "
                f"{safe['半分ずつで損しない残高']:,}円 のところで既に取りこぼしています")
        over = pair_split(safe["半分ずつで損しない残高"] + 1_000_000, ta, tb, 0.5)
        _checks.greater(over["取りこぼし合計"], 0.0,
                        f"課税総所得{ta:,}/{tb:,}で、上限を超えたときの取りこぼしが")
    # (5) **所得が同じなら、最適は半分ずつ**（左右対称なので幅の真ん中は 0.5）
    for bal in (10_000_000, 45_000_000, 90_000_000):
        _checks.rounding(best_share(bal, 3_000_000, 3_000_000)["最適な持分A"], 0.5,
                         f"所得が同じ2人・残高{bal:,}円での最適な持分")
    # (6) **残高が小さいうちは、持分がまったく効かない**（幅が 0〜1 の全部）
    small = best_share(5_000_000, 3_000_000, 1_500_000)
    _checks.rounding(small["最適の幅の広さ"], 1.0,
                     "残高5,000,000円での、最適な持分の幅")


def compute(balance: int, taxable: int) -> Result:
    """年末残高と課税総所得金額から、その年に実際に戻る額と取りこぼしを出す。"""
    credit = int(balance * CREDIT_RATE)
    tax = income_tax(taxable)

    from_income = min(credit, tax)
    remainder = credit - from_income
    cap = min(int(taxable * RESIDENT_CAP_RATE), RESIDENT_CAP_YEN)
    from_resident = min(remainder, max(0, cap))
    lost = credit - from_income - from_resident

    return Result(
        balance=balance, taxable=taxable, credit=credit,
        from_income_tax=from_income, from_resident=from_resident, lost=lost,
    )


def grid(balance: int, taxables: list[int] | None = None) -> list[Result]:
    """課税所得べつに、同じ残高で結果を並べる。"""
    taxables = taxables or [1_500_000, 2_000_000, 3_000_000, 4_000_000, 6_000_000]
    return [compute(balance, t) for t in taxables]


def balance_grid(taxable: int, balances: list[int] | None = None) -> list[Result]:
    """残高べつに、同じ課税所得で結果を並べる。"""
    balances = balances or [20_000_000, 30_000_000, 40_000_000, 45_000_000]
    return [compute(b, taxable) for b in balances]


def break_even_balance(taxable: int) -> int:
    """その課税所得で、取りこぼしが出はじめる年末残高を1万円単位で探す。

    ここがこの計算の主役。**「いくら借りると損しはじめるか」**は
    どこにも出ていないのに、借りる前にいちばん知りたい数字のはず。
    """
    step = 10_000
    balance = step
    while balance <= 100_000_000:
        if compute(balance, taxable).lost > 0:
            return balance - step
        balance += step
    return 100_000_000


def thirteen_years(balance: int, taxable: int, annual_rate: float = 0.01,
                   years: int = 13, term_years: int = 35) -> dict:
    """13年ぶんの合計。元利均等返済で残高が減っていくものとして積む。

    金利は仮定なので、必ず前提として画面に出すこと。
    """
    monthly_rate = annual_rate / 12
    months = term_years * 12
    if monthly_rate > 0:
        factor = (1 + monthly_rate) ** months
        payment = balance * monthly_rate * factor / (factor - 1)
    else:
        payment = balance / months

    remaining = float(balance)
    total_credit = total_recovered = total_lost = 0
    rows = []
    for year in range(1, years + 1):
        for _ in range(12):
            interest = remaining * monthly_rate
            remaining = max(0.0, remaining - (payment - interest))
        r = compute(int(remaining), taxable)
        total_credit += r.credit
        total_recovered += r.recovered
        total_lost += r.lost
        rows.append({"年": year, "残高": int(remaining), "控除可能": r.credit,
                     "戻る": r.recovered, "取りこぼし": r.lost})

    return {
        "控除可能額の合計": total_credit,
        "実際に戻る合計": total_recovered,
        "取りこぼしの合計": total_lost,
        "取りこぼしの割合": total_lost / total_credit if total_credit else 0.0,
        "年ごと": rows,
    }


def resident_cap_switch() -> int:
    """住民税の上限が「5パーセント」から「97,500円」へ切り替わる課税総所得を返す。

    **上限は2つあって、低いほうが効きます**（`compute` の `min`）。
    切り替わる点は 97,500 ÷ 0.05 で決まるので、**残高にはよりません。**
    """
    return int(RESIDENT_CAP_YEN / RESIDENT_CAP_RATE)


def resident_cap_of(taxable: int) -> tuple[int, str]:
    """その課税総所得で、住民税から引ける上限と、**どちらの上限が効いたか**。"""
    five = int(taxable * RESIDENT_CAP_RATE)
    return (five, "5パーセント") if five < RESIDENT_CAP_YEN else (RESIDENT_CAP_YEN, "97,500円")


# ---- 節6: 戻せる枠の内訳（2026-08-25 に足した。**長尺向け**）----------------
#
# 既にある節は全部「残高を動かす」側です（取りこぼしの出る残高・13年の合計・
# 返済期間・金利・繰り上げ返済）。**この節は残高を1円も動かしません。**
# 動かすのは課税総所得のほうで、**戻せる枠そのものの上限**を出します。
def relief_room(taxable: int) -> dict:
    """その課税総所得で、**控除を吸える枠**はいくらか（残高によらない上限）。

    住宅ローン控除は
    **① 所得税から引く → ② 引ききれない分を住民税から引く**の順です。
    ②には上限が**2本**あり、低いほうが効きます（`compute` の `min`）——
    課税総所得の 5パーセント と、97,500円。

    つまり残高をいくら増やしても、**この2つの合計より多くは戻りません。**
    「年末残高の0.7パーセント」だけを見ていると、この天井が見えません。
    """
    tax = income_tax(taxable)
    cap, which = resident_cap_of(taxable)
    return {
        "課税総所得": taxable,
        "所得税額": tax,
        "住民税から引ける上限": cap,
        "効いている上限": which,
        "戻せる枠": tax + cap,
        "枠が所得税の何倍か": (tax + cap) / tax if tax else 0.0,
        "住民税の上限が所得税の何割か": cap / tax if tax else 0.0,
        # その枠を使い切るのに要る年末残高（控除率0.7%の逆算）
        "使い切るのに要る残高": int((tax + cap) / CREDIT_RATE),
    }


def relief_room_grid(taxables: list[int] | None = None) -> list[dict]:
    """課税総所得べつに、戻せる枠を並べる。**折れるのは195万円ちょうど。**"""
    check_tables()
    taxables = taxables or [1_000_000, 1_500_000, 1_940_000, 1_950_000,
                            2_500_000, 3_300_000, 4_500_000, 6_000_000]
    return [relief_room(t) for t in taxables]


def relief_room_doubling() -> dict:
    """**課税総所得195万円までは、住民税の上限が所得税額とぴったり同じ。**

    195万円以下は所得税の税率が5パーセントなので `所得税 ＝ 課税総所得 × 5%`、
    住民税の上限も `課税総所得 × 5%`。**同じ式の同じ値**です。
    だからこの帯の人は、**戻せる枠がちょうど所得税額の2倍**になります。

    195万円を1円でも超えると所得税だけが伸び、住民税の上限は 97,500円 で止まるので、
    **倍率はそこから落ち続けます。**
    """
    switch = resident_cap_switch()
    below = relief_room(switch - 10_000)
    above = relief_room(6_000_000)
    return {
        "折れる課税総所得": switch,
        "折れる前の倍率": below["枠が所得税の何倍か"],
        "折れたあとの倍率": above["枠が所得税の何倍か"],
        "折れる前の上限": below["住民税から引ける上限"],
        "折れたあとの上限": above["住民税から引ける上限"],
    }


# ---- 節7: ペアローンの持分（2026-08-26 に足した。**長尺向け**）--------------
#
# 既にある節7つは、全部「1人が借りる」前提です。**この節は同じ残高を2人で分けます。**
# 枠（`relief_room`）は**人ごとに立つ**ので、分け方を変えると戻る合計が変わります。
#
# 制度の側は「持分に応じて各自が控除を受ける」としか言いません。
# **どこにも出ていないのは「では何対何にするのが正解か」**のほうです。
# ここではそれを、1パーセント刻みで全部当てて出します。
#
# **狙って出す形は「台形」**です —— 最適はふつう1点ではなく**幅**を持ちます。
# 「ぴったり合わせないと損する」ではなく「この幅に入れば同じ」が答えになる。
def pair_split(balance: int, taxable_a: int, taxable_b: int,
               share_a: float) -> dict:
    """残高を A:B ＝ `share_a` : `1 - share_a` で分けたとき、2人ぶんの合計。

    **持分は借入の負担割合**として置いています（ペアローンでも連帯債務でも、
    各自の年末残高がこの比で立つ、という形）。
    端数は A に寄せず **B が残り全部**を持つので、合計は必ず `balance` に一致します。
    """
    if not 0.0 <= share_a <= 1.0:
        raise ValueError(f"持分は0〜1です: {share_a}")
    bal_a = int(balance * share_a)
    bal_b = balance - bal_a
    ra, rb = compute(bal_a, taxable_a), compute(bal_b, taxable_b)
    return {
        "持分A": share_a,
        "残高A": bal_a, "残高B": bal_b,
        "戻るA": ra.recovered, "戻るB": rb.recovered,
        "戻る合計": ra.recovered + rb.recovered,
        "取りこぼしA": ra.lost, "取りこぼしB": rb.lost,
        "取りこぼし合計": ra.lost + rb.lost,
    }


def pair_grid(balance: int, taxable_a: int, taxable_b: int,
              shares: list[float] | None = None) -> list[dict]:
    """持分べつに並べる。**山の形を見るための表**（既定は10パーセント刻み）。"""
    shares = shares or [i / 10 for i in range(11)]
    return [pair_split(balance, taxable_a, taxable_b, s) for s in shares]


def best_share(balance: int, taxable_a: int, taxable_b: int,
               step: float = 0.01) -> dict:
    """1パーセント刻みで全部当てて、**戻る合計がいちばん大きい持分**を出す。

    返すのは最大の1点だけではありません。**同じ最大に並ぶ持分の幅**も返します ——
    そこが「ぴったり合わせる必要があるのか」の答えになるからです。
    """
    n = int(round(1 / step))
    rows = [pair_split(balance, taxable_a, taxable_b, i / n) for i in range(n + 1)]
    best = max(r["戻る合計"] for r in rows)
    tied = [r["持分A"] for r in rows if r["戻る合計"] == best]
    half = pair_split(balance, taxable_a, taxable_b, 0.5)
    return {
        "残高": balance, "課税総所得A": taxable_a, "課税総所得B": taxable_b,
        # **幅の真ん中**を代表に取ります（並んだ点のどれを取っても戻る額は同じ）
        "最適な持分A": (min(tied) + max(tied)) / 2,
        "最適の幅": (min(tied), max(tied)),
        "最適の幅の広さ": max(tied) - min(tied),
        "最適で戻る合計": best,
        "半分ずつで戻る合計": half["戻る合計"],
        "半分ずつにすると捨てる額": best - half["戻る合計"],
        "全部Aで戻る合計": rows[-1]["戻る合計"],
        "全部Bで戻る合計": rows[0]["戻る合計"],
    }


def pair_room_ratio(taxable_a: int, taxable_b: int) -> dict:
    """**枠の比**。ここが、上の最適な持分の当たりを付ける先です。

    枠を使い切る残高までなら、**戻る合計は「各自の枠」で頭打ちになる**ので、
    最適な持分は **枠A : 枠B** に寄ります。**残高によりません。**
    残高が小さくて2人とも枠を余らせているうちは、**どの持分でも同じ**です
    （そこが上の「幅」がいちばん広くなる帯）。
    """
    ra, rb = relief_room(taxable_a), relief_room(taxable_b)
    total = ra["戻せる枠"] + rb["戻せる枠"]
    return {
        "枠A": ra["戻せる枠"], "枠B": rb["戻せる枠"], "枠の合計": total,
        "枠の比A": ra["戻せる枠"] / total if total else 0.0,
        "2人で使い切るのに要る残高": int(total / CREDIT_RATE),
    }


def half_safe_balance(taxable_a: int, taxable_b: int) -> dict:
    """**半分ずつ借りても1円も取りこぼさない、年末残高の上限。**

    この節のいちばん実用的な数字です。持分を細かく決めるのは面倒なので、
    現場ではまず 50:50 が置かれます。**その 50:50 が破綻するのは、
    枠の小さいほうが自分の半分を吸いきれなくなった瞬間**です。

        半分の控除可能額 ＝ 残高 ÷ 2 × 0.7パーセント
        これが「枠の小さいほう」を超えた時点で、超えた分はどこからも戻らない

    だから上限は **枠の小さいほう × 2 ÷ 0.7パーセント**。
    **枠の大きいほうは1円も関係しません** —— そこがこの数字の意外なところです。
    """
    ra, rb = relief_room(taxable_a), relief_room(taxable_b)
    smaller = min(ra["戻せる枠"], rb["戻せる枠"])
    return {
        "枠A": ra["戻せる枠"], "枠B": rb["戻せる枠"],
        "小さいほうの枠": smaller,
        "半分ずつで損しない残高": int(smaller * 2 / CREDIT_RATE),
        "1人で借りるなら損しない残高": int(max(ra["戻せる枠"], rb["戻せる枠"])
                                          / CREDIT_RATE),
    }


def pair_thirteen_years(balance: int, taxable_a: int, taxable_b: int,
                        share_a: float, annual_rate: float = 0.01,
                        years: int = 13, term_years: int = 35) -> dict:
    """13年ぶんの合計を、2人に分けて積む。

    **1年の表と符号が変わることがあります** —— 残高は毎年減るので、
    後半は2人とも枠を余らせる側に落ち、そこでは持分が効かなくなるからです。
    **「1年で見た最適」を13年に引き伸ばさないこと。**
    """
    bal_a = int(balance * share_a)
    bal_b = balance - bal_a
    ta = thirteen_years(bal_a, taxable_a, annual_rate, years, term_years)
    tb = thirteen_years(bal_b, taxable_b, annual_rate, years, term_years)
    return {
        "持分A": share_a,
        "戻る合計": ta["実際に戻る合計"] + tb["実際に戻る合計"],
        "取りこぼしの合計": ta["取りこぼしの合計"] + tb["取りこぼしの合計"],
        "戻るA": ta["実際に戻る合計"], "戻るB": tb["実際に戻る合計"],
    }


def pair_thirteen_best(balance: int, taxable_a: int, taxable_b: int,
                       step: float = 0.05, annual_rate: float = 0.01,
                       years: int = 13, term_years: int = 35) -> dict:
    """13年の合計で、最適な持分と「半分ずつ」との差。**刻みは5パーセント**。"""
    n = int(round(1 / step))
    rows = [pair_thirteen_years(balance, taxable_a, taxable_b, i / n,
                                annual_rate, years, term_years)
            for i in range(n + 1)]
    best = max(r["戻る合計"] for r in rows)
    tied = [r["持分A"] for r in rows if r["戻る合計"] == best]
    half = pair_thirteen_years(balance, taxable_a, taxable_b, 0.5,
                               annual_rate, years, term_years)
    return {
        "最適な持分A": tied[len(tied) // 2],
        "最適の幅": (min(tied), max(tied)),
        "最適で戻る合計": best,
        "半分ずつで戻る合計": half["戻る合計"],
        "半分ずつにすると捨てる額": best - half["戻る合計"],
        "年ごと": rows,
    }


def interest_paid(balance: int, annual_rate: float,
                  years: int = 13, term_years: int = 35) -> int:
    """元利均等返済で、`years` 年のあいだに払う利息の合計。

    **控除の側だけを見ると金利は「得」に見えます**（残高が減りにくいので控除可能額が増える）。
    払った側を同じ土俵に出すために置いています。
    """
    monthly_rate = annual_rate / 12
    months = term_years * 12
    if monthly_rate > 0:
        factor = (1 + monthly_rate) ** months
        payment = balance * monthly_rate * factor / (factor - 1)
    else:
        payment = balance / months
    remaining, total = float(balance), 0.0
    for _ in range(years * 12):
        interest = remaining * monthly_rate
        total += interest
        remaining = max(0.0, remaining - (payment - interest))
    return int(total)


def prepay_loss(balance: int, taxable: int, prepay: int, at_year: int,
                annual_rate: float = 0.01, years: int = 13,
                term_years: int = 35) -> dict:
    """`at_year` 年目の末に `prepay` 円を繰り上げ返済したとき、13年で失う控除。

    **期間短縮型**（毎月の返済額は変えず、残高だけを減らす）で置いています。
    返済額を下げる型（返済額軽減型）だと残高の減りが遅くなるので、
    **失う控除はこれより小さくなります。** きつい側を出しています。
    """
    monthly_rate = annual_rate / 12
    months = term_years * 12
    if monthly_rate > 0:
        factor = (1 + monthly_rate) ** months
        payment = balance * monthly_rate * factor / (factor - 1)
    else:
        payment = balance / months

    remaining, total = float(balance), 0
    for year in range(1, years + 1):
        for _ in range(12):
            interest = remaining * monthly_rate
            remaining = max(0.0, remaining - (payment - interest))
        if year == at_year:
            remaining = max(0.0, remaining - prepay)
        total += compute(int(remaining), taxable).recovered

    plain = thirteen_years(balance, taxable, annual_rate, years, term_years)
    lost = plain["実際に戻る合計"] - total
    return {"繰上げ": prepay, "年": at_year, "戻る合計": total,
            "繰上げなし": plain["実際に戻る合計"], "失う控除": lost,
            "繰上げ額に対する割合": lost / prepay if prepay else 0.0}


def prepay_free_amount(balance: int, taxable: int, at_year: int,
                       annual_rate: float = 0.01, years: int = 13,
                       term_years: int = 35, step: int = 100_000) -> dict:
    """`at_year` 年目の末に繰り上げ返済しても、**13年ぶんの控除を1円も減らさずに済む**額。

    `prepay_loss` を 0円 から `step` きざみで実際に回して、
    **失う控除が 0 のままでいられる最後の額**を返します（推定ではなく総当たり）。

    ## なぜこの数字が要るか

    「繰り上げ返済は控除が終わってから」は、どこにでもある言い方です。
    **だがそれは、控除が残高で決まっている人の話**です。

    住宅ローン控除は `min(残高 × 0.7パーセント, その人の戻せる枠)` で、
    **枠のほうが小さい人は、残高を減らしても控除が1円も減りません**
    （`relief_room` の「使い切るのに要る残高」より上に居るあいだは、
    残高は余っているだけだから）。

    つまり **課税所得が低い人ほど、繰り上げ返済は「タダ」でできます。**
    ここで出すのは、その「タダで返せる額」を円で言い切った数です。

    ## 前提（画面と説明欄に必ず出すこと）

    - 元利均等返済・**期間短縮型**（毎月の返済額は変えない）。
      返済額軽減型なら残高の減りが遅いので、**タダで返せる額はこれより大きく**なります
    - 年末残高だけで判定します（月々の残高は見ません）
    - 借入限度額・住宅の種類・入居年は入れていません（このファイルの方針どおり）
    """
    free = 0
    amount = step
    while amount <= balance:
        if prepay_loss(balance, taxable, amount, at_year,
                       annual_rate, years, term_years)["失う控除"] > 0:
            break
        free = amount
        amount += step
    room = relief_room(taxable)
    return {
        "課税総所得": taxable,
        "戻せる枠": room["戻せる枠"],
        "使い切るのに要る残高": room["使い切るのに要る残高"],
        "タダで返せる額": free,
        "元の残高に対する割合": free / balance if balance else 0.0,
    }


if __name__ == "__main__":
    check_tables()
    print("速算表と上限の検査: 通過\n")

    print("=== 年末残高3000万円のとき、課税所得べつに1年で戻る額 ===")
    for r in grid(30_000_000):
        print(f"  課税所得{r.taxable // 10_000:>4d}万  控除可能{r.credit:>7,}円  "
              f"所得税から{r.from_income_tax:>7,}  住民税から{r.from_resident:>6,}  "
              f"取りこぼし{r.lost:>7,}円（{r.lost_ratio * 100:4.1f}%）")

    print("\n=== 取りこぼしが出はじめる年末残高 ===")
    for taxable in (1_500_000, 2_000_000, 3_000_000, 4_000_000, 6_000_000):
        be = break_even_balance(taxable)
        print(f"  課税所得{taxable // 10_000:>4d}万  →  年末残高 {be:,}円 まで")

    print("\n=== 13年ぶんの合計（3000万円・35年・金利1.0%） ===")
    for taxable in (2_000_000, 3_000_000, 6_000_000):
        t = thirteen_years(30_000_000, taxable)
        print(f"  課税所得{taxable // 10_000:>4d}万  控除可能{t['控除可能額の合計']:>9,}円  "
              f"戻る{t['実際に戻る合計']:>9,}円  "
              f"取りこぼし{t['取りこぼしの合計']:>9,}円（{t['取りこぼしの割合'] * 100:4.1f}%）")

    sw = resident_cap_switch()
    print(f"\n=== 住民税の上限は2つあり、切り替わるのは課税所得{sw // 10_000}万円"
          f"（所得税5パーセントの区分の上限と同じ点）===")
    for taxable in (1_000_000, 1_500_000, 1_900_000, sw, 2_000_000, 3_000_000):
        cap, which = resident_cap_of(taxable)
        mark = "  ← **ここで入れ替わる**" if taxable == sw else ""
        print(f"  課税所得{taxable // 10_000:>4d}万  住民税から引ける上限{cap:>7,}円"
              f"（効いているのは {which}）{mark}")
    print(f"  → 上限の 97,500円 は {sw:,}円 の5パーセントちょうどで、"
          f"**{sw:,}円 は所得税が5パーセントで済む区分の上限そのもの**です。"
          "2つの上限は別々の場所に書かれていますが、**同じ1点で入れ替わるように置かれています**")

    print("\n=== 同じ3000万円を借りても、返済期間が短いほど控除は減る（課税所得300万・金利1.0%）===")
    base_term = thirteen_years(30_000_000, 3_000_000, term_years=35)["実際に戻る合計"]
    for term in (20, 25, 30, 35):
        t = thirteen_years(30_000_000, 3_000_000, term_years=term)
        got = t["実際に戻る合計"]
        print(f"  返済期間{term:>3d}年  13年で戻る{got:>9,}円  "
              f"35年との差 {got - base_term:>9,}円")
    print(f"  → **借りた額も金利も同じ**なのに、20年で組むと13年で戻る額は "
          f"{base_term - thirteen_years(30_000_000, 3_000_000, term_years=20)['実際に戻る合計']:,}円 少なくなります。"
          "控除は残高に掛かるので、**早く減らすほど掛ける相手が小さくなる**ためです")

    print("\n=== 金利が高いほど控除は増えるが、増えた利息の2パーセントしか取り返せない"
          "（3000万円・35年・課税所得600万）===")
    ref_credit = thirteen_years(30_000_000, 6_000_000, annual_rate=0.005)["実際に戻る合計"]
    ref_interest = interest_paid(30_000_000, 0.005)
    for rate in (0.005, 0.01, 0.015, 0.02, 0.03):
        got = thirteen_years(30_000_000, 6_000_000, annual_rate=rate)["実際に戻る合計"]
        paid = interest_paid(30_000_000, rate)
        d_credit, d_interest = got - ref_credit, paid - ref_interest
        ratio = f"{d_credit / d_interest * 100:5.1f}%" if d_interest else "    —"
        print(f"  金利{rate * 100:4.1f}%  13年で戻る{got:>9,}円  払う利息{paid:>10,}円  "
              f"控除の増{d_credit:>8,}円 / 利息の増{d_interest:>10,}円 ＝ {ratio}")
    print("  → **金利が上がると控除は確かに増えます。**"
          "ただし増えるのは、**余計に払った利息の2パーセント前後**だけです"
          "（金利が上がっても、この割合はほとんど動きません）")

    print("\n=== 戻せる枠は課税総所得195万円で折れる。住民税だけが97,500円で止まる ===")
    print(f"  控除は **① 所得税から引く → ② 引ききれない分を住民税から引く** の順です。"
          f"②の上限は2本あり（課税総所得の{RESIDENT_CAP_RATE:.0%} と {RESIDENT_CAP_YEN:,}円）、"
          "**低いほうが効きます**")
    print(f"{'課税総所得':>12s} {'所得税額':>10s} {'住民税の上限':>12s} {'効いた側':>10s} "
          f"{'戻せる枠':>10s} {'所得税の何倍':>11s} {'使い切るのに要る残高'}")
    for r in relief_room_grid():
        print(f"  {r['課税総所得']:>10,}円 {r['所得税額']:>9,}円 "
              f"{r['住民税から引ける上限']:>11,}円 {r['効いている上限']:>10s} "
              f"{r['戻せる枠']:>9,}円 {r['枠が所得税の何倍か']:>10.4f}倍 "
              f"{r['使い切るのに要る残高']:>13,}円")
    d = relief_room_doubling()
    print(f"  → **{d['折れる課税総所得']:,}円 までは、住民税の上限が所得税額と1円まで同じ**です"
          f"（どちらも 課税総所得 × {RESIDENT_CAP_RATE:.0%}）。"
          f"だから戻せる枠は**ちょうど所得税の {d['折れる前の倍率']:.0f}倍**になります")
    print(f"  → {d['折れる課税総所得']:,}円 を超えると所得税だけが伸び、住民税の上限は "
          f"{RESIDENT_CAP_YEN:,}円 で止まります。"
          f"課税総所得600万円では倍率が **{d['折れたあとの倍率']:.4f}倍**まで落ちます")
    print("  → **この枠は年末残高によりません。** 残高をいくら増やしても、"
          "戻る額はこの枠を超えません。表のいちばん右が、その枠を使い切る残高です")

    print("\n=== 繰り上げ返済で消える控除（3000万円・35年・金利1.0%・課税所得600万）===")
    for at_year in (1, 3, 5, 8, 11):
        p = prepay_loss(30_000_000, 6_000_000, 5_000_000, at_year)
        print(f"  {at_year:>2d}年目の末に500万円  13年で戻る{p['戻る合計']:>9,}円  "
              f"**失う控除{p['失う控除']:>8,}円**（繰上げ額の"
              f"{p['繰上げ額に対する割合'] * 100:4.2f}パーセント）")
    print("  → 繰上げ返済は利息を減らしますが、**同時に控除の掛ける相手も減らします。**"
          "早い年ほど残る年数が多いので、**失う控除も早いほど大きくなります**")

    print("\n=== 2人で借りるとき、半分ずつで損しなくなる残高の上限 ===")
    for ta, tb in ((3_000_000, 1_500_000), (6_000_000, 1_000_000),
                   (4_000_000, 2_500_000), (2_000_000, 2_000_000)):
        s = half_safe_balance(ta, tb)
        print(f"  課税総所得{ta:>9,}円 と {tb:>9,}円  枠 {s['枠A']:>7,}／{s['枠B']:>7,}円"
              f"  → **半分ずつなら年末残高 {s['半分ずつで損しない残高']:>11,}円 まで**")
    print(f"  → 上限を決めているのは**小さいほうの枠だけ**です"
          f"（小さいほうの枠 × 2 ÷ {CREDIT_RATE:.1%}）。"
          "**大きいほうの人がいくら稼いでいても、この上限は1円も動きません**")

    print("\n=== 持分を振ると、戻る合計はどう動くか（課税総所得600万と100万）===")
    for bal in (30_000_000, 45_000_000, 60_000_000):
        b = best_share(bal, 6_000_000, 1_000_000)
        lo, hi = b["最適の幅"]
        print(f"  年末残高{bal:>11,}円  最適な持分 **{b['最適な持分A'] * 100:.0f}対"
              f"{100 - b['最適な持分A'] * 100:.0f}**（同じ額で済む幅 {lo * 100:.0f}〜{hi * 100:.0f}パーセント）"
              f"  最適{b['最適で戻る合計']:>8,}円  半分ずつ{b['半分ずつで戻る合計']:>8,}円"
              f"  **捨てる{b['半分ずつにすると捨てる額']:>7,}円**")
    print("  → **最適は1点ではなく幅です。** その幅に入ってさえいれば、"
          "持分を1パーセント単位で詰めても戻る額は1円も変わりません")

    t = pair_thirteen_best(45_000_000, 6_000_000, 1_000_000)
    # **「同じペア」と書くだけにしないこと**（2026-08-27 に `premise.scan` が当てた）。
    # 節は1本ずつ切り出されるので、**前の節は読まれません。**
    # 誰のことかは、この見出しに書いてある数だけで決まります。
    print(f"\n=== 同じペアの13年ぶんの合計"
          f"（課税総所得600万と100万・4500万円・35年・金利1.0%）===")
    print(f"  最適な持分 {t['最適な持分A'] * 100:.0f}対{100 - t['最適な持分A'] * 100:.0f}"
          f"  最適{t['最適で戻る合計']:>10,}円  半分ずつ{t['半分ずつで戻る合計']:>10,}円"
          f"  **13年で捨てる{t['半分ずつにすると捨てる額']:>9,}円**")
    print("  → 残高は毎年減るので、後半は2人とも枠を余らせます。"
          "**持分が効くのは前半だけ**で、13年の差は1年の差の13倍にはなりません")

    print("\n=== 繰り上げ返済でも控除を1円も失わずに済む額（3000万円・35年・金利1.0%・3年目末）===")
    print("  住宅ローン控除は **min(残高×0.7パーセント, その人の戻せる枠)** です。"
          "**枠のほうが小さい人は、残高が減っても控除が減りません**")
    print(f"{'課税総所得':>12s} {'戻せる枠':>10s} {'枠を使い切る残高':>16s} "
          f"{'タダで返せる額':>14s} {'元の残高の'}")
    frees = []
    for tx in (500_000, 1_000_000, 1_500_000, 1_950_000, 3_000_000, 6_000_000):
        f = prepay_free_amount(30_000_000, tx, 3)
        frees.append(f)
        print(f"  {f['課税総所得']:>10,}円 {f['戻せる枠']:>9,}円 "
              f"{f['使い切るのに要る残高']:>15,}円 "
              f"**{f['タダで返せる額']:>11,}円** "
              f"{f['元の残高に対する割合'] * 100:>5.1f}パーセント")
    top = frees[0]
    zero = [f for f in frees if f["タダで返せる額"] == 0]
    print(f"  → **課税総所得{top['課税総所得']:,}円の人は、3000万円のうち "
          f"{top['タダで返せる額']:,}円（{top['元の残高に対する割合'] * 100:.1f}パーセント）まで"
          f"繰り上げても控除を1円も失いません。** 枠が{top['戻せる枠']:,}円しかないので、"
          f"残高が{top['使い切るのに要る残高']:,}円 を切るまでは控除が頭打ちのままだからです")
    if zero:
        z = zero[0]
        print(f"  → 逆に課税総所得{z['課税総所得']:,}円 から上は**1円 返した時点で失いはじめます。**"
              f"枠を使い切る残高が{z['使い切るのに要る残高']:,}円 と、3年目末の残高より大きいので、"
              "残高の減りがそのまま控除の減りになります")
    print("  → **「繰り上げ返済は控除が終わってから」は、枠が残高より大きい人だけの話です。**"
          "前提: 元利均等・期間短縮型・年末残高で判定")

    print("\n=== 繰り上げ返済で失う控除は「繰上げ額×0.7%×残り年数」では足りない ===")
    print("  期間短縮型は毎月の返済額を変えないので、**繰り上げた翌月から元金の減りが速くなります。**"
          "だから減るのは繰上げ額そのものだけではありません")
    print(f"{'繰上げの年':>10s} {'失う控除':>10s} {'素朴な見積り':>12s} {'実際は何倍'}")
    ratios = []
    for at_year in (1, 3, 5, 8, 11):
        pl = prepay_loss(30_000_000, 6_000_000, 5_000_000, at_year)
        naive = int(5_000_000 * CREDIT_RATE * (13 - at_year))
        ratio = pl["失う控除"] / naive if naive else 0.0
        ratios.append(ratio)
        print(f"  {at_year:>7d}年目 {pl['失う控除']:>9,}円 {naive:>11,}円 "
              f"**{ratio:>6.2f}倍**")
    print(f"  → 素朴な見積り（繰上げ額 × 0.7パーセント × 残り年数）は、"
          f"**どの年でも実際より小さく出ます**（この条件で "
          f"{min(ratios):.2f}〜{max(ratios):.2f}倍）")
    print("  → 差が出るのは、繰り上げた額そのものではなく"
          "**その後の元金の減りが速くなるぶん**です。"
          "返済額軽減型ならこの差は出ません（残高の減り方が変わらないので）")
    print("  → 前提: 3000万円・35年・金利1.0%・課税総所得600万円・期間短縮型・"
          "500万円を各年の末に1回だけ繰り上げ")
