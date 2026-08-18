"""小規模企業共済 —— **「全額所得控除」の値打ちは、掛けた額ではなく税率で決まります。**

一般の解説はこう言います ——「掛金は全額が所得控除になり、20年（240か月）未満で
任意解約すると元本割れします」。**どちらも合っています。そのうえで、
この2つを同じ表に並べた数字は、どこにも出ていません。**

以下は掛金の上限 70,000円／月で、所得税率と掛けた月数を同時に動かした結果です。

## 全額所得控除の値打ちは、所得税の帯で 3.6667倍 ちがいます

    所得税率   節税率    年間の節税額    実質の負担（年間の掛金 840,000円）
      5%      15.0%    126,000円      714,000円
     10%      20.0%    168,000円      672,000円
     20%      30.0%    252,000円      588,000円
     23%      33.0%    277,200円      562,800円
     33%      43.0%    361,200円      478,799円
     40%      50.0%    420,000円      420,000円
     45%      55.0%    462,000円      377,999円

**同じ 840,000円を掛けて、手元から出ていく額が 714,000円 の人と 377,999円 の人がいます。**
制度のどこにも「高所得者ほど有利」とは書いてありません。
**所得控除は税率を掛けてから効くので、率の差がそのまま値打ちの差になります。**

## 「80パーセントしか戻らない」を節税が埋める線は、税率だけでは決まりません

12か月以上84か月未満で任意解約すると、戻るのは掛金の 80パーセントです。
**節税ぶんを足して元本を割らない最低の節税率**（所得税率 ＋ 住民税 10パーセント）は、
こうなります。

    掛けた月数   掛金累計       分かれ目の節税率   足りる最低の所得税率
      12か月    840,000円      22.28%          20%
      24か月   1,680,000円     26.71%          20%
      36か月   2,520,000円     28.6%           20%
      48か月   3,360,000円     29.66%          20%
      60か月   4,200,000円     30.32%          **23%**   ← ここで帯が1つ上がる
      72か月   5,040,000円     30.79%          23%
      83か月   5,810,000円     31.1%           23%

**同じ「80パーセントしか戻らない」でも、必要な税率が上がっていきます。**
一時所得の特別控除 500,000円 が掛けた額によらず一定なので、
**掛金累計が大きいほど、その一定額の効きが薄まる**ためです。
上限は 33.33パーセント（＝3分の1）で、**それを超えることは原理的にありません。**

## 支給率が 80パーセントで止まっているあいだ、続けるほど損が増えます

所得税率 20パーセントの人で、任意解約したときの「元本との差」です。

    12か月    +58,200円   ← **いちばん得**
    13か月    +56,800円
    24か月    +41,400円
    54か月    ここでマイナスに転じる
    83か月    -41,200円

**傾きは毎月 -1,400円 で一定**です。1か月かけるごとに、掛金 70,000円 の
20パーセントを失い、節税で 21,000円 を得て、一時所得の税で戻すからです。
**「20年続ければ元本割れしない」は正しいのですが、
その手前は上りではなく、まっすぐな下り坂**でした。

## 退職所得控除で無税にできる掛金月額は、上限 70,000円 に一度も届きません

共済金を一括で受け取ると退職所得です。**退職所得控除が掛金累計以上なら、
受取時の税は0円**になります。その条件を満たす掛金月額の上限はこうなります。

    掛けた年数   退職所得控除     無税の月額上限   上限 70,000円との差
      5年      2,000,000円     33,333円      36,667円
     10年      4,000,000円     33,333円      36,667円
     20年      8,000,000円     33,333円      36,667円
     25年     11,500,000円     38,333円      31,667円
     30年     15,000,000円     41,666円      28,334円
     40年     22,000,000円     45,833円      24,167円

**20年以下は、何年掛けても 33,333円で一定**です（控除が1年あたり 400,000円 なので
400,000 ÷ 12 になります）。20年を超えると上がりますが、**漸近線は
700,000 ÷ 12 ＝ 58,333円** で、**掛金の上限 70,000円 には何年掛けても届きません。**
つまり **上限まで掛ける人は、受取時に必ず課税されます。**

## 掛金を1か月延ばすだけで、退職所得控除が1年ぶん跳ぶ月が 38件 あります

退職所得の勤続年数は、掛金納付月数の1年未満を**切り上げ**ます。
だから 240か月 と 241か月 は、20年 と 21年 です。

    掛けた月数   勤続年数   退職所得控除    税額         手取り
      240か月    20年     8,000,000円   892,500円   15,907,500円
      241か月    21年     8,700,000円   798,000円   16,072,000円

**掛金は 70,000円 しか増えていないのに、手取りは 164,500円 増えます。**
跳びの大きさは一定ではありません（課税退職所得が下がるとき、
速算表のどの帯を通り抜けるかで変わります）。

    差し引き 24,750円 …  7件（25か月〜97か月）
    差し引き 26,250円 …  1件（109か月）
    差し引き 33,000円 …  6件（121か月〜181か月）
    差し引き 49,500円 …  4件（193か月〜229か月）
    差し引き 94,500円 … 20件（241か月〜469か月）  ← 20年を超えたあと

## 同じ額を受け取っても、辞め方の名前で税額が 3.46倍 変わります

掛金累計 8,400,000円（70,000円 × 120か月）を受け取ったときの税です。

    受け取り方              所得の種類   課税される額     税額
    共済金A（廃業）・一括      退職所得    2,200,000円   342,500円
    準共済金（法人成り）・一括  退職所得    2,200,000円   342,500円
    解約手当金（任意解約）      一時所得    3,950,000円  1,185,000円

**額はまったく同じで、受け取る理由の名前だけが違います。**
退職所得は控除を引いてから2分の1・分離課税、一時所得は
500,000円 を引いてから2分の1を**ほかの所得と合算**するためです。

## 11か月と12か月のあいだで、手元が 597,200円 動きます

任意解約の解約手当金は、掛金納付月数 12か月未満で **0円**（掛け捨て）です。

    掛けた月数   掛金累計      解約手当金    節税累計     元本との差
      6か月     420,000円        0円    126,000円   -294,000円
     11か月     770,000円        0円    231,000円   -539,000円
     12か月     840,000円   672,000円   252,000円    +58,200円

**掛金は 70,000円 しか増えていないのに、手元は 597,200円 動きます。
掛金1か月ぶんの 8.53倍 です。** この表でいちばん深い段差は、
20年の元本割れの線ではなく、**最初の1年の入口**にありました。
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値 -----------------------------------------------------------
# 掛金月額（小規模企業共済法。中小機構の公表する掛金の範囲）。500円きざみ。
KAKEKIN_MIN = 1_000
KAKEKIN_MAX = 70_000
KAKEKIN_STEP = 500

# 掛金は全額が「小規模企業共済等掛金控除」（所得税法75条）。上限は無い。
# **社会保険料控除と違い、生計を一にする親族のぶんは対象になりません。**

# 任意解約の解約手当金。掛金納付月数が12か月未満だと掛け捨て（0円）。
KAIYAKU_MIN_MONTHS = 12
# 12か月以上84か月未満の支給率は掛金合計額の100分の80。
KAIYAKU_FLOOR_RATE = 0.80
KAIYAKU_FLOOR_UNTIL = 84
# 240か月（20年）で100パーセント。**それ未満は必ず元本割れ。**
KAIYAKU_PAR_MONTHS = 240

# 退職所得控除（所得税法30条3項）。勤続20年以下は1年40万円（最低80万円）、
# 20年を超える部分は1年70万円。
TAISHOKU_UNIT_LOW = 400_000
TAISHOKU_UNIT_HIGH = 700_000
TAISHOKU_BORDER_YEARS = 20
TAISHOKU_MIN = 800_000
TAISHOKU_HALF = 0.5

# 一時所得（所得税法34条）。特別控除50万円、課税されるのは2分の1。
ICHIJI_DEDUCTION = 500_000
ICHIJI_HALF = 0.5

# 住民税の所得割（標準税率）。
JUMINZEI_RATE = 0.10

# 所得税の速算表（所得税法89条）。(課税所得の上限, 税率, 控除額)
TAX_TABLE: list[tuple[int | None, float, int]] = [
    (1_950_000, 0.05, 0),
    (3_300_000, 0.10, 97_500),
    (6_950_000, 0.20, 427_500),
    (9_000_000, 0.23, 636_000),
    (18_000_000, 0.33, 1_536_000),
    (40_000_000, 0.40, 2_796_000),
    (None, 0.45, 4_796_000),
]

ASSUMPTIONS = [
    "小規模企業共済の掛金と、受け取るときの税を計算しています。"
    "掛金の月額は1,000円から70,000円までの500円きざみです",
    "掛金は全額が小規模企業共済等掛金控除として所得から引けるものとして置いています。"
    "所得税法75条の掛金控除で、上限はありません",
    "住民税の所得割は10パーセントの標準税率としています。均等割は入れていません",
    "復興特別所得税（所得税額の2.1パーセント）は入れていません。"
    "入れると節税額も受取時の税額も、どちらも同じ向きに約2パーセント増えます",
    "任意解約の解約手当金は、掛金納付月数が12か月未満のとき0円としています。"
    "12か月以上84か月未満は掛金合計額の80パーセントです",
    "84か月から240か月までの支給率は、この計算では使っていません。"
    "240か月で100パーセントになるまで段階的に上がりますが、"
    "その途中の率は月数ごとの表で決まるためです。"
    "使っているのは80パーセントと100パーセントの2点だけです",
    "解約手当金は一時所得として計算しています。特別控除50万円を引いた残りの"
    "2分の1が、ほかの所得と合算されます。"
    "掛金は一時所得の必要経費に入れていません。"
    "すでに掛けた年に所得控除を受けているためです",
    "共済金と準共済金は、一括で受け取ると退職所得として計算しています。"
    "退職所得控除は勤続20年以下が1年あたり40万円（最低80万円）、"
    "20年を超える部分が1年あたり70万円です",
    "退職所得の勤続年数は、掛金を納めた月数を12で割り、"
    "1年に満たない端数を1年に切り上げたものとして置いています",
    "勤続年数5年以下の短期退職手当等（300万円を超える部分に2分の1を使わない扱い）は"
    "入れていません。この計算で5年以下を出しているのは解約手当金の側だけで、"
    "そちらは一時所得なので影響しません",
    "共済金Aや共済金Bにつく付加共済金と、掛金を上回る上乗せは入れていません。"
    "掛けた額がそのまま戻るものとして計算しています。"
    "実際の共済金は掛金合計額を上回りますが、その額は運用状況で決まるためです",
    "受け取る年に、ほかの退職金や一時所得が無いものとして置いています",
    "所得税率は掛けているあいだも受け取る年も同じものとして置いています。"
    "節の中で1つの値を使うときは、所得税率20パーセントに住民税10パーセントを足した"
    "30パーセントとして置いています",
]


# ---- 税 -----------------------------------------------------------------
def income_tax(base: float) -> float:
    """所得税の速算表を引く。**課税所得の額を渡すこと。**"""
    for cap, rate, sub in TAX_TABLE:
        if cap is None or base <= cap:
            return base * rate - sub
    raise ValueError(f"速算表に当たらない: {base}")


BRACKET_RATES = [rate for _, rate, _ in TAX_TABLE]


def combined_rate(income_rate: float) -> float:
    """所得税率に住民税10パーセントを足した、掛金1円あたりの節税率。"""
    return income_rate + JUMINZEI_RATE


# ---- 掛金 ---------------------------------------------------------------
def total_paid(monthly: int, months: int) -> int:
    """掛金の累計。"""
    return monthly * months


def tax_saved(monthly: int, months: int, income_rate: float) -> float:
    """掛けているあいだの節税額の累計。**全額所得控除なので掛金 × 税率です。**"""
    return total_paid(monthly, months) * combined_rate(income_rate)


# ---- 退職所得 -----------------------------------------------------------
def service_years(months: int) -> int:
    """退職所得控除の勤続年数。**1年未満の端数は1年に切り上げます。**"""
    return -(-months // 12)


def taishoku_deduction(years: int) -> int:
    """退職所得控除額（所得税法30条3項）。"""
    if years <= TAISHOKU_BORDER_YEARS:
        return max(TAISHOKU_MIN, TAISHOKU_UNIT_LOW * years)
    return (TAISHOKU_UNIT_LOW * TAISHOKU_BORDER_YEARS
            + TAISHOKU_UNIT_HIGH * (years - TAISHOKU_BORDER_YEARS))


def taishoku_tax(amount: int, months: int) -> dict:
    """一括で受け取ったときの退職所得の税。**分離課税・2分の1課税。**"""
    years = service_years(months)
    ded = taishoku_deduction(years)
    base = max(0, amount - ded) * TAISHOKU_HALF
    base = int(base // 1000) * 1000          # 課税退職所得は1,000円未満切り捨て
    it = max(0.0, income_tax(base))
    jt = base * JUMINZEI_RATE
    return {
        "勤続年数": years,
        "退職所得控除": ded,
        "課税退職所得": base,
        "所得税": it,
        "住民税": jt,
        "税額": it + jt,
    }


# ---- 一時所得 -----------------------------------------------------------
def ichiji_tax(amount: int, income_rate: float) -> dict:
    """一時所得の税。**掛金は経費に入りません**（掛けた年に控除済みのため）。"""
    base = max(0, amount - ICHIJI_DEDUCTION) * ICHIJI_HALF
    return {
        "一時所得（課税分）": base,
        "税額": base * combined_rate(income_rate),
    }


def kaiyaku_amount(monthly: int, months: int) -> int:
    """任意解約の解約手当金。**12か月未満は0円、84か月未満は80パーセント。**"""
    if months < KAIYAKU_MIN_MONTHS:
        return 0
    if months < KAIYAKU_FLOOR_UNTIL:
        return int(total_paid(monthly, months) * KAIYAKU_FLOOR_RATE)
    if months >= KAIYAKU_PAR_MONTHS:
        return total_paid(monthly, months)
    raise ValueError(
        f"84か月以上240か月未満の支給率はこの表では計算しません: {months}か月")


# ---- 節1: 全額所得控除の値打ちは、税率で何倍変わるか ----------------------
def deduction_grid(monthly: int = KAKEKIN_MAX) -> list[dict]:
    """年間の掛金に対する節税額を、所得税の帯べつに並べる。"""
    rows = []
    annual = monthly * 12
    for rate in BRACKET_RATES:
        saved = annual * combined_rate(rate)
        rows.append({
            "所得税率": rate,
            "節税率": combined_rate(rate),
            "年間の掛金": annual,
            "年間の節税額": int(saved),
            "実質の負担": int(annual - saved),
        })
    return rows


# ---- 節2: 80パーセントしか戻らなくても、損しない税率の線 ------------------
def break_even_rate(monthly: int, months: int) -> float:
    """任意解約（支給率80パーセント）でも手元が元本を割らない、最低の節税率。

    手元 ＝ 解約手当金 ＋ 節税累計 − 一時所得の税 で、これが掛金累計以上になる線。
    **t（節税率）について解くと、掛金累計 P に対して**

        t ≧ 0.2 P ／（0.6 P ＋ 250,000）

    となります。**P が大きいほど右辺が上がり、3分の1に近づきます**
    （一時所得の特別控除50万円が、P に関わらず一定だからです）。
    """
    p = total_paid(monthly, months)
    got = kaiyaku_amount(monthly, months)
    taxable = max(0, got - ICHIJI_DEDUCTION) * ICHIJI_HALF
    # (p - got) = t * (p - taxable)  を解く
    return (p - got) / (p - taxable)


def net_after_kaiyaku(monthly: int, months: int, income_rate: float) -> dict:
    """任意解約したときの、税を入れた手元。"""
    p = total_paid(monthly, months)
    got = kaiyaku_amount(monthly, months)
    saved = tax_saved(monthly, months, income_rate)
    tax = ichiji_tax(got, income_rate)["税額"]
    net = got + saved - tax
    return {
        "掛金累計": p,
        "解約手当金": got,
        "節税累計": int(saved),
        "一時所得の税": int(tax),
        "手元の合計": int(net),
        "元本との差": int(net - p),
    }


def surplus_curve(monthly: int = KAKEKIN_MAX,
                  income_rate: float = 0.20) -> list[dict]:
    """12か月から83か月まで、任意解約したときの元本との差。

    **支給率が80パーセントで止まっているあいだ、1か月かけるごとに
    掛金の20パーセントを失い、節税で 掛金 ×（税率）を得ます。**
    差は一定なので、この区間の曲線は**まっすぐな下り坂**になります
    （一時所得の2分の1課税ぶんだけ、傾きが緩みます）。
    """
    return [{"掛けた月数": m, "元本との差": net_after_kaiyaku(monthly, m, income_rate)["元本との差"]}
            for m in range(KAIYAKU_MIN_MONTHS, KAIYAKU_FLOOR_UNTIL)]


def best_month(monthly: int = KAKEKIN_MAX, income_rate: float = 0.20) -> dict:
    """支給率80パーセントの区間で、手元がいちばん多くなる月と、赤に転じる月。"""
    rows = surplus_curve(monthly, income_rate)
    top = max(rows, key=lambda r: r["元本との差"])
    neg = next((r for r in rows if r["元本との差"] < 0), None)
    slope = rows[1]["元本との差"] - rows[0]["元本との差"]
    return {
        "いちばん得な月数": top["掛けた月数"],
        "そのときの元本との差": top["元本との差"],
        "赤に転じる月数": neg["掛けた月数"] if neg else None,
        "1か月あたりの傾き": slope,
        "83か月まで続けたときの差": rows[-1]["元本との差"],
    }


def break_even_grid(monthly: int = KAKEKIN_MAX) -> list[dict]:
    """掛けた月数べつに、損益が分かれる節税率と、それに届く所得税の帯。"""
    rows = []
    for months in (12, 24, 36, 48, 60, 72, 83):
        t = break_even_rate(monthly, months)
        need = next((r for r in BRACKET_RATES if combined_rate(r) >= t), None)
        rows.append({
            "掛けた月数": months,
            "掛金累計": total_paid(monthly, months),
            "分かれ目の節税率": t,
            "足りる最低の所得税率": need,
        })
    return rows


# ---- 節3: 退職所得控除で無税になる掛金月額の上限 --------------------------
def tax_free_monthly(years: int) -> int:
    """その年数まで掛けたとき、受取時の税が0になる掛金月額の上限（円未満切り捨て）。

    **退職所得控除 ≧ 掛金累計** となる月額 ＝ 控除 ÷（12 × 年数）。
    **平均であって、増え方ではありません。**
    20年以下は 400,000 ÷ 12 ＝ 33,333円で年数によらず一定、
    20年を超えると上がりますが、**700,000 ÷ 12 ＝ 58,333円 が漸近線**で、
    掛金の上限 70,000円 には**何年掛けても届きません。**
    """
    return int(taishoku_deduction(years) / (12 * years))


def tax_free_grid() -> list[dict]:
    """年数べつの、無税で受け取れる掛金月額の上限。"""
    rows = []
    for years in (5, 10, 15, 20, 25, 30, 35, 40):
        cap = tax_free_monthly(years)
        rows.append({
            "掛けた年数": years,
            "退職所得控除": taishoku_deduction(years),
            "無税の月額上限": cap,
            "上限70,000円との差": KAKEKIN_MAX - cap,
            "上限まで掛けたときの課税退職所得":
                taishoku_tax(KAKEKIN_MAX * 12 * years, 12 * years)["課税退職所得"],
        })
    return rows


# ---- 節4: 20年の1か月先で、控除が跳ぶ ------------------------------------
def month_step_grid(monthly: int = KAKEKIN_MAX) -> list[dict]:
    """240か月の前後1か月で、退職所得控除と税がどう動くか。"""
    rows = []
    for months in (228, 237, 238, 239, 240, 241, 249, 252):
        amount = total_paid(monthly, months)
        t = taishoku_tax(amount, months)
        rows.append({
            "掛けた月数": months,
            "勤続年数": t["勤続年数"],
            "掛金累計": amount,
            "退職所得控除": t["退職所得控除"],
            "税額": int(t["税額"]),
            "手取り": int(amount - t["税額"]),
        })
    return rows


def month_step_jumps(monthly: int = KAKEKIN_MAX) -> list[dict]:
    """1か月増やしたときに、手取りが掛金より増える月（＝控除が1年ぶん跳ぶ月）。"""
    jumps = []
    prev = None
    for months in range(12, 481):
        amount = total_paid(monthly, months)
        net = amount - taishoku_tax(amount, months)["税額"]
        if prev is not None and net - prev > monthly:
            jumps.append({
                "この月数で跳ぶ": months,
                "手取りの増え方": int(net - prev),
                "掛けた額の増え方": monthly,
                "差し引き": int(net - prev - monthly),
            })
        prev = net
    return jumps


def jump_sizes(monthly: int = KAKEKIN_MAX) -> list[dict]:
    """跳ぶ月を、跳びの大きさべつにまとめる。

    **跳びの大きさは一定ではありません。** 退職所得控除が1年ぶん増えると
    課税退職所得が下がり、**そのとき通り抜けた速算表の帯によって減る税額が変わる**ためです。
    """
    out: dict[int, list[int]] = {}
    for j in month_step_jumps(monthly):
        out.setdefault(j["差し引き"], []).append(j["この月数で跳ぶ"])
    return [{"差し引き": k, "件数": len(v), "最初の月": v[0], "最後の月": v[-1]}
            for k, v in sorted(out.items())]


# ---- 節5: 同じ額でも、辞め方の名前で税が変わる ----------------------------
def exit_kind_grid(monthly: int = KAKEKIN_MAX, months: int = 120,
                   income_rate: float = 0.20) -> list[dict]:
    """同じ掛金累計を、退職所得と一時所得のそれぞれで受け取ったときの税。"""
    amount = total_paid(monthly, months)
    t = taishoku_tax(amount, months)
    i = ichiji_tax(amount, income_rate)
    return [
        {"受け取り方": "共済金A（廃業）・一括",
         "所得の種類": "退職所得", "受取額": amount,
         "課税される額": t["課税退職所得"], "税額": int(t["税額"])},
        {"受け取り方": "準共済金（法人成り）・一括",
         "所得の種類": "退職所得", "受取額": amount,
         "課税される額": t["課税退職所得"], "税額": int(t["税額"])},
        {"受け取り方": "解約手当金（任意解約）",
         "所得の種類": "一時所得", "受取額": amount,
         "課税される額": int(i["一時所得（課税分）"]), "税額": int(i["税額"])},
    ]


def exit_kind_ratio(monthly: int = KAKEKIN_MAX, months: int = 120,
                    income_rate: float = 0.20) -> float:
    """一時所得の税 ÷ 退職所得の税。**同じ額を受け取ったときの倍率です。**"""
    rows = exit_kind_grid(monthly, months, income_rate)
    return rows[2]["税額"] / rows[0]["税額"]


# ---- 節6: 11か月と12か月のあいだ ----------------------------------------
def cliff_grid(monthly: int = KAKEKIN_MAX, income_rate: float = 0.20) -> list[dict]:
    """掛け捨ての線（12か月）の前後で、税を入れた手元がどう動くか。"""
    rows = []
    for months in (6, 11, 12, 13, 24):
        p = total_paid(monthly, months)
        got = kaiyaku_amount(monthly, months)
        saved = tax_saved(monthly, months, income_rate)
        tax = ichiji_tax(got, income_rate)["税額"]
        rows.append({
            "掛けた月数": months,
            "掛金累計": p,
            "解約手当金": got,
            "節税累計": int(saved),
            "手元の合計": int(got + saved - tax),
            "元本との差": int(got + saved - tax - p),
        })
    return rows


def cliff_step(monthly: int = KAKEKIN_MAX, income_rate: float = 0.20) -> dict:
    """11か月と12か月の差。**掛金は1か月ぶんしか増えていません。**"""
    rows = {r["掛けた月数"]: r for r in cliff_grid(monthly, income_rate)}
    a, b = rows[11], rows[12]
    return {
        "11か月の元本との差": a["元本との差"],
        "12か月の元本との差": b["元本との差"],
        "1か月で動く額": b["元本との差"] - a["元本との差"],
        "掛金1か月": monthly,
        "掛金の何倍": (b["元本との差"] - a["元本との差"]) / monthly,
    }


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(KAKEKIN_MAX, 70_000, "掛金の月額上限",
                      source="小規模企業共済法・中小機構の公表資料")
    _checks.statutory(TAISHOKU_UNIT_LOW, 400_000, "退職所得控除（20年以下・1年）",
                      source="所得税法30条3項")
    _checks.statutory(TAISHOKU_UNIT_HIGH, 700_000, "退職所得控除（20年超・1年）",
                      source="所得税法30条3項")
    _checks.statutory(ICHIJI_DEDUCTION, 500_000, "一時所得の特別控除",
                      source="所得税法34条3項")
    _checks.statutory(KAIYAKU_FLOOR_RATE, 0.80, "任意解約の最低支給率",
                      source="小規模企業共済法施行令・中小機構の公表資料")
    _checks.ratio(KAIYAKU_FLOOR_RATE, "任意解約の最低支給率")
    _checks.ratio(JUMINZEI_RATE, "住民税の所得割")

    # 2. 速算表
    _checks.bracket_table(TAX_TABLE, income_tax, name="所得税の速算表")

    # 3. 退職所得控除は年数で増え、20年の前後で増え方が変わる
    _checks.increases_with(taishoku_deduction, range(3, 41), "勤続年数が増えたのに控除が増えていない")
    _checks.statutory(taishoku_deduction(20), 8_000_000, "20年の退職所得控除",
                      source="所得税法30条3項（40万円 × 20年）")
    _checks.statutory(taishoku_deduction(21) - taishoku_deduction(20), 700_000,
                      "20年→21年の増え方", source="所得税法30条3項")
    _checks.statutory(taishoku_deduction(19) - taishoku_deduction(18), 400_000,
                      "18年→19年の増え方", source="所得税法30条3項")
    _checks.statutory(taishoku_deduction(1), 800_000, "1年の退職所得控除（最低額）",
                      source="所得税法30条3項ただし書き")

    # 4. 勤続年数は切り上げ。**240か月と241か月で1年ちがう**
    _checks.statutory(service_years(240), 20, "240か月の勤続年数")
    _checks.statutory(service_years(241), 21, "241か月の勤続年数")
    _checks.statutory(service_years(1), 1, "1か月の勤続年数（切り上げ）")

    # 5. 節税額は税率が上がれば増える
    _checks.increases_with(lambda r: tax_saved(KAKEKIN_MAX, 12, r), BRACKET_RATES,
                           "所得税率が上がったのに節税額が増えていない")

    # 6. 掛け捨ての線。**11か月は0円、12か月は80パーセント**
    _checks.statutory(kaiyaku_amount(KAKEKIN_MAX, 11), 0, "11か月の解約手当金")
    _checks.statutory(kaiyaku_amount(KAKEKIN_MAX, 12), 672_000, "12か月の解約手当金",
                      source="掛金合計840,000円 × 80パーセント")

    # 7. **分かれ目の節税率は、掛けた額が増えると上がる**（この表の主題）
    _checks.increases_with(lambda m: break_even_rate(KAKEKIN_MAX, m),
                           [12, 24, 36, 48, 60, 72, 83],
                           "掛けた月数が増えたのに分かれ目の節税率が上がっていない")
    for months in (12, 36, 83):
        t = break_even_rate(KAKEKIN_MAX, months)
        _checks.greater(1 / 3, t, "分かれ目の節税率が3分の1以上（上限のはず）")

    # 8. **分かれ目のちょうど上と下で、符号が変わること**
    for months in (12, 36, 83):
        t = break_even_rate(KAKEKIN_MAX, months)
        below = net_after_kaiyaku(KAKEKIN_MAX, months, t - JUMINZEI_RATE - 0.01)
        above = net_after_kaiyaku(KAKEKIN_MAX, months, t - JUMINZEI_RATE + 0.01)
        _checks.greater(0, below["元本との差"], f"{months}か月・分かれ目の下で元本を割っていない")
        _checks.greater(above["元本との差"], 0, f"{months}か月・分かれ目の上で元本を上回っていない")

    # 9. 無税の月額上限は、20年以下でも20年超でも 70,000円に届かない
    for years in (5, 10, 20, 30, 40):
        _checks.greater(KAKEKIN_MAX, tax_free_monthly(years),
                        f"{years}年で無税の月額上限が掛金上限70,000円を超えている")
    _checks.statutory(tax_free_monthly(10), 33_333, "10年の無税の月額上限")
    _checks.statutory(tax_free_monthly(20), 33_333, "20年の無税の月額上限")
    _checks.statutory(tax_free_monthly(40), 45_833, "40年の無税の月額上限")
    # **20年以下は年数によらず一定**（控除が1年40万円だから）
    for years in (2, 5, 10, 15, 20):
        _checks.statutory(tax_free_monthly(years), 33_333,
                          f"{years}年の無税の月額上限", source="40万円 ÷ 12か月")
    # **20年を超えると上がるが、70万円 ÷ 12 ＝ 58,333円を永久に超えない**
    _checks.increases_with(tax_free_monthly, [20, 25, 30, 40, 60, 100],
                           "20年超で無税の月額上限が上がっていない")
    _checks.greater(TAISHOKU_UNIT_HIGH / 12, tax_free_monthly(10_000),
                    "無税の月額上限が漸近線 58,333円 を超えている")

    # 10. **同じ額でも一時所得のほうが重い**
    _checks.greater(exit_kind_ratio(), 1.0, "一時所得の税が退職所得の税以下")

    # 11. **80パーセントの区間は、まっすぐな下り坂**（この表の主題の2つ目）
    _checks.decreases_with(
        lambda m: net_after_kaiyaku(KAKEKIN_MAX, m, 0.20)["元本との差"],
        range(KAIYAKU_MIN_MONTHS, KAIYAKU_FLOOR_UNTIL),
        "20パーセント帯で、掛ける月数が増えたのに元本との差が減っていない")
    b = best_month()
    _checks.statutory(b["いちばん得な月数"], KAIYAKU_MIN_MONTHS,
                      "20パーセント帯でいちばん得な月数",
                      source="支給率が80パーセントで止まっている区間の左端")
    _checks.greater(0, b["1か月あたりの傾き"], "傾きが下向きでない")
    _checks.greater(b["赤に転じる月数"], KAIYAKU_MIN_MONTHS,
                    "赤に転じる月数が12か月以下")

    # 12. **跳びの大きさは一定ではない**（速算表の帯を通り抜けるため）
    _checks.greater(len(jump_sizes()), 1, "跳びの大きさが1種類しかない")
    _checks.statutory(jump_sizes()[-1]["差し引き"], 94_500,
                      "20年を超えたあとの跳びの差し引き",
                      source="控除70万円 × 2分の1 × (所得税20% + 住民税10%) ×… の実計算")

    # 13. 表に同じ行が2つ入っていないこと
    _checks.unique_by(deduction_grid(), lambda r: r["所得税率"], "節1の表")
    _checks.unique_by(tax_free_grid(), lambda r: r["掛けた年数"], "節3の表")
    _checks.unique_by(month_step_grid(), lambda r: r["掛けた月数"], "節4の表")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 全額所得控除の値打ちは、所得税の帯で3.67倍ちがう ===")
    rows = deduction_grid()
    for row in rows:
        print(row)
    print("いちばん上といちばん下の比:",
          round(rows[-1]["年間の節税額"] / rows[0]["年間の節税額"], 4), "倍")
    print("節税率:", [round(r["節税率"] * 100, 2) for r in rows], "パーセント")

    print("\n=== 80パーセントしか戻らなくても損しない線は、税率だけでは決まらない ===")
    for row in break_even_grid():
        print(row)
    print("分かれ目の節税率（パーセント）:",
          [round(r["分かれ目の節税率"] * 100, 2) for r in break_even_grid()])
    print("上限（掛金が無限に大きいとき）:", round(100 / 3, 2), "パーセント")
    for months in (12, 83):
        print(months, "か月:", net_after_kaiyaku(KAKEKIN_MAX, months, 0.20))
        print(months, "か月:", net_after_kaiyaku(KAKEKIN_MAX, months, 0.23))
    print("所得税20%帯の曲線:", best_month())

    print("\n=== 退職所得控除で無税にできる掛金月額は、上限70,000円に一度も届かない ===")
    for row in tax_free_grid():
        print(row)

    print("\n=== 掛金を1か月延ばすと、退職所得控除が1年ぶん跳ぶ月がある ===")
    for row in month_step_grid():
        print(row)
    print("跳ぶ月は全部で", len(month_step_jumps()), "件。大きさべつ:")
    for row in jump_sizes():
        print("  ", row)

    print("\n=== 同じ額を受け取っても、辞め方の名前で税額が変わる ===")
    for row in exit_kind_grid():
        print(row)
    print("倍率:", round(exit_kind_ratio(), 2))

    print("\n=== いちばん深い段差は20年ではなく、11か月と12か月のあいだにある ===")
    for row in cliff_grid():
        print(row)
    print(cliff_step())
    print("掛金の何倍:", round(cliff_step()["掛金の何倍"], 2), "倍")
