"""個人事業主の経費 —— **「経費は税率ぶんだけ得」は、6分の1しか数えていません。**

一般の解説はこう言います ——「経費を1万円増やしても、戻ってくるのは税率ぶん。
税率5パーセントの人なら500円だけ。だから節税のために無駄な物を買うのは損」。

**税率5パーセントの人が実際に取り戻すのは 3,155円です**（事業所得300万円・本人1人・
45歳・青色申告特別控除65万円）。**速算表の税率の6.3倍**で、
経費1万円の正味の費用は 10,000円ではなく **6,845円**です。

数えていないものが3つあります。**住民税10パーセント・国民健康保険料・個人事業税。**
どれも「経費を引いたあとの所得」から計算されるので、経費と一緒に減ります。

    事業所得（青色控除前）   速算表   経費1万円の値打ち   正味の費用
      200万円               5%        2,654円          7,346円
      300万円               5%        3,155円          6,845円
      500万円              10%        3,614円          6,386円
      700万円              20%        4,533円          5,467円
      900万円              20%        4,308円          5,692円
    1,200万円              33%        4,869円          5,131円

## 所得が上がるほど値打ちが大きい、ではありません

**700万円の人（45.33パーセント）は、900万円の人（43.08パーセント）より
経費の値打ちが大きい。** 同じ速算表20パーセントの帯にいるのにです。

国民健康保険料には賦課限度額があり、**医療分67万円・後期高齢者支援金分26万円・
介護納付金分17万円・子ども子育て支援金分3万円が、区分ごとに別々に頭を打ちます。**
上から順に消えていくので、値打ちは**所得税の階段を上がりながら、
国保の階段を下りる**という形になります。900万円は、下りたほうが勝っている点です。

## 経費1万円で、負担が2万5千円減る所得があります。**山の幅は1円です**

事業所得（青色控除前）**1,390,200円**のところで、経費1万円の値打ちは **25,176円**。
**払った額より多く戻ります**（正味の費用がマイナス15,176円）。

国民健康保険の軽減の判定が、青色申告特別控除を引いたあとの所得
**74万円**（43万円 ＋ 31万円×1人）をまたぐためです。**2割軽減が5割軽減に変わり、
均等割が一段で落ちます。** 150万円まで上がると、値打ちは 26.54パーセントに戻ります。

**この山は、同じ値打ちになる所得が1円しかありません。** 10万円きざみで探すと
1,400,000円・24,475円（**701円低い**）を、1,000円きざみでも 1,391,000円・25,076円を
返します。**格子の上に山は乗っていません。**

同じ形の山が、軽減の段の数だけあります。**どれも幅10円未満です。**

    事業所得（青色控除前）   経費1万円の値打ち   同じ値打ちの幅
      1,089,994円            17,815円           7円
      1,390,200円            25,176円           1円   ← いちばん高い
      1,651,800円            16,758円           1円

## 所得が1円ちがうと、経費1万円の値打ちが22,980円ちがいます

事業所得 **1,390,000円** では 2,195円。その **1円上**の 1,390,001円では **25,175円**。
実効率で **21.95パーセント → 251.75パーセント**（**229.8ポイント**の跳ね）。
軽減の判定は所得の1円で切り替わるので、**跳びは1円の中で起きます。**

## 事業税の290万円は、青色申告特別控除を引く「前」で判定されます

個人事業税の事業主控除は年290万円ですが、**個人事業税では青色申告特別控除が引けません。**
だから事業税がかかり始める人の事業所得（青色控除後）は **225万円**です。
所得税・住民税の側から見ると、**65万円ずれた位置に段があります。**

    青色控除前 290万円のすぐ下   26.55%
    青色控除前 290万円のすぐ上   31.55%   ← **5ポイント上がる**

## 率をそのまま足すと、必ず多すぎます

「所得税20.42パーセント ＋ 住民税10 ＋ 国保12.95 ＋ 事業税5 ＝ 48.37パーセント」
と足したくなりますが、**実際は45.33パーセント**です（事業所得700万円）。

**国民健康保険料が減ると、社会保険料控除も同じだけ減る**ので、
そのぶん所得税と住民税が増えて戻ってきます。差は 304円 ＝ **足し算の6.3パーセント**。

    300万円  足し算 33.05% → 実際 31.55%（4.5%が戻る）
    500万円  足し算 38.16% → 実際 36.14%（5.3%が戻る）
    700万円  足し算 48.37% → 実際 45.33%（6.3%が戻る）
    900万円  足し算 46.12% → 実際 43.08%（6.6%が戻る）
  1,200万円  足し算 48.69% → 実際 48.69%（**0%**）

**1,200万円で戻りが消えるのは、国保が限度額に当たって1円も動かないから**です。
戻る道が無ければ、二重勘定も起きません。

## 青色申告特別控除を10万円から65万円にしても、事業税は1円も減りません

事業所得500万円（青色控除前）で並べると:

    簡易簿記10万円   所得税 288,024円  住民税 364,800円  事業税 105,000円  国保 661,465円  計 1,419,289円
    複式簿記55万円   所得税 222,680円  住民税 325,600円  事業税 105,000円  国保 603,190円  計 1,256,470円
    e-Tax 65万円     所得税 213,797円  住民税 316,900円  事業税 105,000円  国保 590,240円  計 1,225,937円

**55万円ぶん増やして減るのは 193,352円**（うち国保が 71,225円）。
**事業税の列だけが、3行とも同じ 105,000円**です。
"""
from __future__ import annotations

from functools import lru_cache as _lru_cache

from . import _checks, kokuho
from .jutaku import BRACKETS, income_tax as _income_tax_bracket

# ---- 制度の値 -----------------------------------------------------------
# 青色申告特別控除（租税特別措置法25条の2）。e-Tax による申告か電子帳簿保存で65万円、
# 複式簿記で55万円、簡易簿記（現金主義など）で10万円。
AOIRO_ETAX = 650_000
AOIRO_FUKUSHIKI = 550_000
AOIRO_KANI = 100_000

# 基礎控除。所得税は48万円（所得税法86条・合計所得金額2,400万円以下）、
# 住民税は43万円（地方税法314条の2第1項の2）。**同じ人に2つの額が使われます。**
KISO_SHOTOKU = 480_000
KISO_JUMIN = 430_000

JUMIN_RATE = 0.10              # 住民税の所得割（市町村6% ＋ 道府県4%）
JUMIN_KINTOWARI = 5_000        # 住民税の均等割（森林環境税1,000円を含む）
FUKKO_RATE = 0.021             # 復興特別所得税（所得税額の2.1%）

# 個人事業税（地方税法72条の49の14ほか）。事業主控除は年290万円。
# 税率は業種で3〜5%。第1種事業（物品販売業・請負業など37業種）が5%。
JIGYOZEI_KOJO = 2_900_000
JIGYOZEI_RATE = 0.05

# 国民年金保険料（令和7年度）。月額17,510円。**全額が社会保険料控除**。
NENKIN_MONTH = 17_510
NENKIN_YEAR = NENKIN_MONTH * 12

STEP = 10_000                  # 「経費1万円」の1万円

ASSUMPTIONS = [
    "個人事業主が、経費を1万円増やしたときに、税と保険料がいくら減るかを計算しています。"
    "収入は事業所得だけで、給与も年金も他の所得もないものとしています",
    "青色申告特別控除は65万円として置いています。"
    "e-Taxによる申告か電子帳簿保存をしている場合の額で、複式簿記だけなら55万円、"
    "簡易簿記なら10万円になります。節によっては3つを並べています",
    "所得控除は、基礎控除と社会保険料控除だけを入れています。"
    "基礎控除は所得税で48万円、住民税で43万円です。"
    "配偶者控除、扶養控除、生命保険料控除、小規模企業共済等掛金控除は入れていません",
    "社会保険料控除には、国民健康保険料と国民年金保険料を入れています。"
    "国民年金保険料は仮定で、月額1万7,510円の年額21万120円として置いています",
    "国民健康保険料は市町村ごとに率が違います。ここでは医療分の所得割7.71パーセント・"
    "均等割4万7,300円、後期高齢者支援金分の所得割2.69パーセント・均等割1万6,800円、"
    "介護納付金分の所得割2.25パーセント・均等割1万6,600円、"
    "子ども・子育て支援金分の所得割0.30パーセント・均等割1,900円を例として置いています。"
    "賦課限度額は合計113万円です",
    "世帯は本人1人、年齢は45歳として置いています。"
    "40歳から64歳なので、国民健康保険料に介護納付金分がかかります。"
    "年齢だけを動かした節では、39歳（介護分なし）と45歳（介護分あり）を並べています",
    "個人事業税は第1種事業の5パーセントとして置いています。"
    "事業主控除は年290万円です。業種によっては3パーセントや4パーセント、"
    "また課税されない業種もあります",
    "個人事業税は、青色申告特別控除を引く前の所得で計算します。"
    "所得税と住民税では引けますが、事業税では引けません",
    "支払った個人事業税は、翌年の必要経費になります。この計算には入れていません",
    "住民税の調整控除と、所得税の予定納税は入れていません",
    "消費税は入れていません。免税事業者として置いています",
    "「全額所得控除」と並べる計算では、小規模企業共済等掛金控除のように"
    "所得金額から引く控除として置いています。国民健康保険料の算定基礎からも"
    "個人事業税の課税標準からも引けない控除です",
    "「全額所得控除」と並べる計算では、その控除を積んでも国民健康保険料と"
    "個人事業税が動かないものとしています。国民健康保険料の算定は"
    "総所得金額等から基礎控除43万円を引いた額で、個人事業税は事業所得から"
    "事業主控除290万円を引いた額です。どちらにも所得控除は入りません",
    "「全額所得控除」と並べる計算では、掛金や保険料を実際に払った年のことだけを"
    "見ています。小規模企業共済は受け取るときに退職所得や一時所得として課税され、"
    "経費にした物やサービスは手元に残ります。ここで並べているのは"
    "その年に戻る額だけで、どちらが得かを出したものではありません",
    "「全額所得控除」と並べる計算では、その控除に上限がないものとしています。"
    "小規模企業共済の掛金は月額7万円・年84万円が上限です",
]


# ---- 1年ぶんの負担 ------------------------------------------------------
def after_aoiro(profit: int, aoiro: int = AOIRO_ETAX) -> int:
    """青色申告特別控除を引いたあとの事業所得。**マイナスにはしません。**"""
    return max(0, profit - aoiro)


@_lru_cache(maxsize=65_536)
def kokuho_premium(profit: int, aoiro: int = AOIRO_ETAX,
                   members: int = 1, age: int = 45) -> int:
    """国民健康保険料。**総所得金額等は青色申告特別控除を引いたあとの額です。**

    ## なぜ控えるのか（2026-08-28・最適化の回。**値は1円も変わりません**）

    **`int` を返す純関数**です（引数だけで決まり、外を叩かない）。
    そして `burden()` は、同じ `(profit, aoiro, members, age)` で
    **4回ここへ来ます** —— `income_tax` と `resident_tax` がそれぞれ
    `social_insurance()` を呼び、`burden` 自身も呼ぶためです。

    実測 `check_tables()`: **2.06秒 → 0.26秒**
    （`kokuho.premium` の呼び出し 263,814回 → 約 66,000回。
    すぐ下の `_kojo_dead_bands` の控えと合わせて、**2.24秒 → 0.26秒**）。
    `tests/test_reschedule_move_ledger.py` の門は 1.0秒 で、
    `src/calc/keihi.py` はそこを **2.24秒** で割っていました。

    **覆る条件**: 返りが `dict` や `list` になったら、この控えは**同じ物**を
    配るので外すこと（呼ぶ側が書き換えたら、全員のぶんが変わります）。
    """
    return int(kokuho.premium(after_aoiro(profit, aoiro), members, age)["保険料"])


def social_insurance(profit: int, aoiro: int = AOIRO_ETAX,
                     members: int = 1, age: int = 45) -> int:
    """社会保険料控除に入る額（国民健康保険料 ＋ 国民年金保険料）。"""
    return kokuho_premium(profit, aoiro, members, age) + NENKIN_YEAR


def income_tax(profit: int, aoiro: int = AOIRO_ETAX,
               members: int = 1, age: int = 45) -> int:
    """所得税（復興特別所得税を含む）。"""
    base = after_aoiro(profit, aoiro) - social_insurance(profit, aoiro, members, age)
    taxable = max(0, int(base) - KISO_SHOTOKU) // 1_000 * 1_000
    return int(_income_tax_bracket(taxable) * (1 + FUKKO_RATE))


def resident_tax(profit: int, aoiro: int = AOIRO_ETAX,
                 members: int = 1, age: int = 45) -> int:
    """住民税（所得割 ＋ 均等割）。**基礎控除が所得税と5万円ちがいます。**"""
    base = after_aoiro(profit, aoiro) - social_insurance(profit, aoiro, members, age)
    taxable = max(0, int(base) - KISO_JUMIN) // 1_000 * 1_000
    return int(taxable * JUMIN_RATE) + JUMIN_KINTOWARI


def business_tax(profit: int) -> int:
    """個人事業税。**青色申告特別控除を引く前の所得**から事業主控除290万円を引きます。"""
    base = max(0, profit - JIGYOZEI_KOJO)
    return int(base * JIGYOZEI_RATE) // 100 * 100


def burden(profit: int, aoiro: int = AOIRO_ETAX,
           members: int = 1, age: int = 45) -> dict:
    """その年の税と保険料の合計。**4本の内訳つき。**"""
    it = income_tax(profit, aoiro, members, age)
    rt = resident_tax(profit, aoiro, members, age)
    bt = business_tax(profit)
    kh = kokuho_premium(profit, aoiro, members, age)
    return {
        "所得（青色控除前）": profit,
        "所得税": it,
        "住民税": rt,
        "事業税": bt,
        "国民健康保険料": kh,
        "国民年金保険料": NENKIN_YEAR,
        "合計": it + rt + bt + kh + NENKIN_YEAR,
        "年金を除く合計": it + rt + bt + kh,
    }


def marginal(profit: int, step: int = STEP, aoiro: int = AOIRO_ETAX,
             members: int = 1, age: int = 45) -> dict:
    """経費を `step` 円ふやしたときに、負担がいくら減るか。

    **これがこの表の主題です。** 返す「値打ち」は減った負担の合計で、
    「実効率」はそれを `step` で割ったもの。**所得税の税率とは別物です。**
    """
    a = burden(profit, aoiro, members, age)
    b = burden(profit - step, aoiro, members, age)
    got = {k: a[k] - b[k] for k in ("所得税", "住民税", "事業税", "国民健康保険料")}
    value = sum(got.values())
    return {
        "所得（青色控除前）": profit,
        "経費": step,
        "所得税の減り": got["所得税"],
        "住民税の減り": got["住民税"],
        "事業税の減り": got["事業税"],
        "国保の減り": got["国民健康保険料"],
        "値打ち": value,
        "実効率": value / step,
        "正味の費用": step - value,
    }


def bracket_rate(profit: int, aoiro: int = AOIRO_ETAX,
                 members: int = 1, age: int = 45) -> float:
    """その人が乗っている所得税の速算表の税率。**一般の解説はこれで止まります。**"""
    base = after_aoiro(profit, aoiro) - social_insurance(profit, aoiro, members, age)
    taxable = max(0, int(base) - KISO_SHOTOKU) // 1_000 * 1_000
    for cap, rate, _ in BRACKETS:
        if taxable <= cap:
            return rate
    return BRACKETS[-1][1]


def naive_rate(profit: int, aoiro: int = AOIRO_ETAX,
               members: int = 1, age: int = 45) -> float:
    """「税率ぶんだけ得をする」と言うときの率（所得税の税率だけ）。"""
    return bracket_rate(profit, aoiro, members, age)


# ---- 表 -----------------------------------------------------------------
PROFITS = [1_000_000, 2_000_000, 3_000_000, 4_000_000, 5_000_000,
           7_000_000, 9_000_000, 12_000_000, 16_000_000, 20_000_000]


def grid(profits: list[int] | None = None) -> list[dict]:
    """図解の元になる表。所得ごとの「経費1万円の値打ち」。"""
    rows = []
    for p in (profits or PROFITS):
        m = marginal(p)
        rows.append({
            "所得": p,
            "速算表の税率": round(bracket_rate(p) * 100, 1),
            "値打ち": m["値打ち"],
            "実効率": round(m["実効率"] * 100, 2),
            "正味の費用": m["正味の費用"],
        })
    return rows



# ---- 年齢だけで動く「経費の値打ち」 -------------------------------------
# **掃引が拾った形**（`python -m src.section_sweep --calc keihi`）:
#     帯  keihi.marginal（実効率）… age が 46〜62 のあいだだけ 0.3155、その前後は 0.293
# 目盛りが粗いだけで、実際の境目は **40歳と65歳**（介護保険法9条2号の第2号被保険者）。
# ここで出したいのは保険料そのものではなく（それは `kokuho` の節）、
# **同じ所得・同じ1万円の経費が、年齢だけで値打ちを変えるか**のほうです。

#: 介護納付金分が乗らない年齢と、乗る年齢。**境目は `kokuho.KAIGO_FROM` / `KAIGO_TO`。**
AGE_NO_KAIGO = 39
AGE_KAIGO = 45


def care_age_gap(profit: int, step: int = STEP,
                 young: int = AGE_NO_KAIGO, care: int = AGE_KAIGO) -> dict:
    """同じ所得で、介護分の乗らない年齢と乗る年齢の「経費の値打ち」の差。"""
    a = marginal(profit, step, age=young)
    b = marginal(profit, step, age=care)
    return {
        "所得": profit,
        "経費": step,
        f"{young}歳の値打ち": a["値打ち"],
        f"{care}歳の値打ち": b["値打ち"],
        "差": b["値打ち"] - a["値打ち"],
        f"{young}歳の実効率": a["実効率"],
        f"{care}歳の実効率": b["実効率"],
        f"{young}歳の国保": kokuho_premium(profit, age=young),
        f"{care}歳の国保": kokuho_premium(profit, age=care),
        "国保の差": kokuho_premium(profit, age=care) - kokuho_premium(profit, age=young),
    }


def care_age_rows(profits: list[int] | None = None) -> list[dict]:
    """所得べつに並べた、年齢だけで動く値打ちの差。"""
    return [care_age_gap(p) for p in (profits or PROFITS)]


def care_gap_vanishes(low: int = 5_000_000, high: int = 12_000_000,
                      step_yen: int = 10_000, floor_yen: int = 100) -> int:
    """差が残っている、いちばん上の所得を `step_yen` きざみで探す。

    **介護納付金分の賦課限度額（17万円）に当たると、経費を増やしても
    介護分は1円も減りません。** そこから上では、年齢の差が消えます。

    `floor_yen` は端数処理のゆらぎを外すための下限です。**1円の差を拾うと
    嘘の点が出ます** —— 実測で、限度額に当たったあとの帯にも ±1円が散らばります
    （所得943万・946万・952万…）。本物の差は所得割そのものの225円なので、
    100円を境にすれば、ゆらぎと本物は混ざりません。
    """
    found = low
    for p in range(low, high + 1, step_yen):
        if care_age_gap(p)["差"] >= floor_yen:
            found = p
    return found


def rate_curve(low: int = 1_000_000, high: int = 20_000_000,
               step: int = 100_000) -> list[dict]:
    """所得を刻んで実効率を出す。**山と谷を探すための細かい表。**"""
    out = []
    p = low
    while p <= high:
        m = marginal(p)
        out.append({"所得": p, "実効率": m["実効率"], "値打ち": m["値打ち"]})
        p += step
    return out


def _refine(low: int, high: int, better) -> int:
    """`low`〜`high` を1円ずつ見て、`better` がいちばん大きい所得を返す。

    **粗い格子で決めないため**にあります（2026-08-19）。`rate_curve()` の刻みは
    既定10万円で、下の3つの山は**どれも幅10円未満**なので、格子の上には
    1つも乗りません。**刻みを答えにしないこと。**
    """
    best, best_key = low, better(low)
    for p in range(low + 1, high + 1):
        k = better(p)
        if k > best_key:
            best, best_key = p, k
    return best


def peak(step: int = 1_000) -> dict:
    """実効率がいちばん高くなる所得。**上に行くほど高い、ではありません。**

    **格子の上を探して終わりにしません**（2026-08-19 に直した）。`step` で粗く
    探してから、その前後を**1円ずつ**見直します。既定の10万円きざみが返していたのは
    1,400,000円・24,475円で、**本当の山は 1,390,200円・25,176円**でした
    （701円の取り逃し。山は**幅1円**なので、10万円でも1,000円でも乗りません）。
    """
    coarse = max(rate_curve(step=step), key=lambda r: r["実効率"])
    p = _refine(max(0, coarse["所得"] - step), coarse["所得"] + step,
                lambda x: marginal(x)["実効率"])
    m = marginal(p)
    return {"所得": p, "実効率": m["実効率"], "値打ち": m["値打ち"]}


def drops(min_point: float = 0.001) -> list[dict]:
    """所得が1段上がったのに、実効率が**下がった**点。

    `min_point` より小さい落ちは出しません。**千円未満の切り捨てが作る
    0.01ポイントの揺れ**が、本物の段と同じ顔で並ぶためです
    （既定は0.1ポイント ＝ 経費1万円あたり10円）。
    """
    curve = rate_curve()
    out = []
    for a, b in zip(curve, curve[1:]):
        fall = a["実効率"] - b["実効率"]
        if fall > min_point:
            out.append({"所得": b["所得"], "前の実効率": a["実効率"],
                        "実効率": b["実効率"], "落ち幅": fall})
    return out


def kokuho_rate(profit: int, aoiro: int = AOIRO_ETAX,
                members: int = 1, age: int = 45) -> float:
    """国民健康保険の所得割の合計率。**限度額に当たっている区分は0%です。**"""
    got = kokuho.premium(after_aoiro(profit, aoiro), members, age)
    return sum(float(kokuho.RATES[r["区分"]]["所得割"])
               for r in got["内訳"] if not r["頭打ちか"])


def naive_sum(profit: int, aoiro: int = AOIRO_ETAX,
              members: int = 1, age: int = 45) -> dict:
    """**率をそのまま足したらいくらか。** 実際の値打ちとの差が二重勘定です。"""
    rates = {
        "所得税": bracket_rate(profit, aoiro, members, age) * (1 + FUKKO_RATE),
        "住民税": JUMIN_RATE,
        "国保": kokuho_rate(profit, aoiro, members, age),
        "事業税": JIGYOZEI_RATE if profit > JIGYOZEI_KOJO else 0.0,
    }
    return {"率": rates, "合計率": sum(rates.values()),
            "足し算": int(sum(rates.values()) * STEP)}


def chain_loss(profit: int = 5_000_000) -> dict:
    """**足し算では出ないぶん。** 国保が減ると社会保険料控除も減り、税が戻ります。"""
    m = marginal(profit)
    n = naive_sum(profit)
    return {
        "所得": profit,
        "素直な足し算": n["足し算"],
        "合計率": n["合計率"],
        "実際の値打ち": m["値打ち"],
        "実効率": m["実効率"],
        "差": n["足し算"] - m["値打ち"],
        "取り返される割合": (n["足し算"] - m["値打ち"]) / n["足し算"] if n["足し算"] else 0.0,
    }


def cliff(step: int = 1_000) -> dict:
    """実効率がいちばん跳ねる点。**国民健康保険の軽減の判定をまたぐところ。**

    2026-08-19 まで、ここは `peak()` と**1文字ちがわない複製**でした（`max` を
    実効率で取るだけ）。名前も docstring も「跳ぶ」と言っているのに、
    **跳び幅はどこでも計算していませんでした。** いまは隣どうしの上がり幅を見て、
    粗い格子で当たりを付けてから**1円ずつ**跳ぶ場所を挟み込みます。
    `drops()` の向きを裏返したものです。
    """
    curve = rate_curve(step=step)
    a, b = max(zip(curve, curve[1:]),
               key=lambda ab: ab[1]["実効率"] - ab[0]["実効率"])
    lo, hi = a["所得"], b["所得"]
    while hi - lo > 1:                      # 上がる1円を挟み込む
        mid = (lo + hi) // 2
        if marginal(mid)["実効率"] > marginal(lo)["実効率"]:
            hi = mid
        else:
            lo = mid
    before, after = marginal(lo), marginal(hi)
    return {"所得": hi, "1円下の所得": lo,
            "前の実効率": before["実効率"], "実効率": after["実効率"],
            "上がり幅": after["実効率"] - before["実効率"],
            "前の値打ち": before["値打ち"], "値打ち": after["値打ち"]}


def reversals(rows: list[dict] | None = None) -> list[dict]:
    """**所得が多いほうが、経費1万円の値打ちが小さい**組。表の行どうしで見ます。"""
    rows = rows or grid()
    out = []
    for i, a in enumerate(rows):
        for b in rows[i + 1:]:
            if b["実効率"] < a["実効率"]:
                out.append({"低いほうの所得": a["所得"], "低いほうの実効率": a["実効率"],
                            "高いほうの所得": b["所得"], "高いほうの実効率": b["実効率"],
                            "差": round(a["実効率"] - b["実効率"], 2)})
    return out


def aoiro_rows(profit: int = 5_000_000) -> list[dict]:
    """青色申告特別控除の3つの額を並べる。**事業税は1円も動きません。**"""
    rows = []
    for a, name in ((AOIRO_KANI, "簡易簿記10万円"),
                    (AOIRO_FUKUSHIKI, "複式簿記55万円"),
                    (AOIRO_ETAX, "e-Tax65万円")):
        b = burden(profit, a)
        rows.append({"青色申告特別控除": name, "所得税": b["所得税"],
                     "住民税": b["住民税"], "事業税": b["事業税"],
                     "国民健康保険料": b["国民健康保険料"],
                     "合計": b["年金を除く合計"]})
    return rows


def jigyozei_edge() -> dict:
    """事業税の入口と、所得税から見たその位置。**65万円ずれます。**"""
    return {
        "事業税の入口（青色控除前）": JIGYOZEI_KOJO,
        "そのときの事業所得（青色控除後）": after_aoiro(JIGYOZEI_KOJO),
        "青色申告特別控除": AOIRO_ETAX,
        "入口の下の実効率": marginal(JIGYOZEI_KOJO)["実効率"],
        "入口の上の実効率": marginal(JIGYOZEI_KOJO + 100_000)["実効率"],
    }


# ---- 世帯の人数を動かす（2026-08-21 に足した3節）------------------------
MEMBER_MAX = 12


def member_rows(profit: int = 7_000_000, max_members: int = MEMBER_MAX) -> list[dict]:
    """世帯の被保険者数だけを動かした表。**所得も年齢も動かしていません。**"""
    rows = []
    for m in range(1, max_members + 1):
        b = burden(profit, members=m)
        g = marginal(profit, members=m)
        d = kokuho.premium(after_aoiro(profit), m, 45)
        rows.append({
            "被保険者数": m,
            "国民健康保険料": b["国民健康保険料"],
            "軽減の割合": d["軽減の割合"],
            "所得税": b["所得税"],
            "住民税": b["住民税"],
            "負担の合計": b["合計"],
            "値打ち": g["値打ち"],
            "実効率": g["実効率"],
            "国保の減り": g["国保の減り"],
        })
    return rows


def member_drops(profit: int, max_members: int = 20) -> list[dict]:
    """**人数が1人ふえたのに、保険料が下がった点。** 軽減の段をまたぐところです。"""
    out = []
    prev = None
    prev_keigen = None
    for m in range(1, max_members + 1):
        d = kokuho.premium(after_aoiro(profit), m, 45)
        now = int(d["保険料"])
        if prev is not None and now < prev:
            out.append({
                "所得（青色控除前）": profit,
                "人数": m,
                "1人前の保険料": prev,
                "保険料": now,
                "下がった額": prev - now,
                "1人前の軽減": prev_keigen,
                "軽減の割合": d["軽減の割合"],
            })
        prev, prev_keigen = now, d["軽減の割合"]
    return out


def member_limit(profit: int, max_members: int = 30) -> dict | None:
    """**経費1万円で国保が1円も減らなくなる人数。**

    **「賦課限度額に当たった点」とは限りません**（2026-08-26 に踏んだ）。
    0 になる理由は2つあり（`kokuho_zero_reason`）、
    **所得の下端では「所得割がそもそもかかっていない」ので 1人目から 0** です。
    所得 1,000,000円 で撃つと「1人目で止まる」と返りますが、
    **所得 12,000,000円 の「1人目で止まる」と意味が正反対**です。
    `MEMBER_PROFITS` は 500万円 から始まっているので既存の表は無傷ですが、
    **低い所得を渡すときは `理由` を読むこと。**
    """
    for m in range(1, max_members + 1):
        g = marginal(profit, members=m)
        if g["国保の減り"] == 0:
            return {
                "所得（青色控除前）": profit,
                "人数": m,
                "値打ち": g["値打ち"],
                "実効率": g["実効率"],
                "1人のときの値打ち": marginal(profit)["値打ち"],
                "落ちる額": marginal(profit)["値打ち"] - g["値打ち"],
                "理由": kokuho_zero_reason(profit, m)["理由"],
            }
    return None


MEMBER_PROFITS = [5_000_000, 6_000_000, 7_000_000, 8_000_000, 9_000_000, 12_000_000]
DROP_PROFITS = [2_000_000, 3_000_000, 4_000_000, 5_000_000]


def member_limit_rows(profits: list[int] | None = None) -> list[dict]:
    """所得ごとに「経費の値打ちが人数で動かなくなる人数」を並べた表。"""
    return [r for r in (member_limit(p) for p in (profits or MEMBER_PROFITS)) if r]


def member_drop_rows(profits: list[int] | None = None) -> list[dict]:
    """所得ごとの「人数がふえて保険料が下がった点」を全部つないだ表。"""
    out = []
    for p in (profits or DROP_PROFITS):
        out.extend(member_drops(p))
    return out


# ---- 帳簿の付け方で「経費1万円の値打ち」が変わる（2026-08-26 に足した3節）----
#
# **`src.arg_gaps` が名指ししていた軸です。** `marginal()` は `aoiro` を
# 引数で受け取れるのに、**どの節も渡していませんでした** ——
# `aoiro_rows()` が3つの控除額を並べていますが、あれが比べているのは
# **その年の負担の合計**で、**経費1万円の値打ち**ではありません。
#
# 実測（この節を書いた回）: 所得500万円で **簡易簿記10万円 4,533円 対
# e-Tax65万円 3,614円**。**同じ所得・同じ1万円の経費で 919円（20%）ちがいます。**

#: 帳簿の付け方（控除額, 呼び名）。**`aoiro_rows` と同じ並び**。
AOIRO_KINDS = ((AOIRO_KANI, "簡易簿記10万円"),
               (AOIRO_FUKUSHIKI, "複式簿記55万円"),
               (AOIRO_ETAX, "e-Tax65万円"))


def aoiro_marginal(profit: int, step: int = STEP) -> dict:
    """**同じ所得・同じ経費で、帳簿の付け方だけを変えた「値打ち」。**

    青色申告特別控除は課税所得を下げるので、**その人が乗っている帯が変わります。**
    帯が変われば、次の1万円の経費が効く率も変わる ——
    だから **「経費1万円の値打ち」は、帳簿の付け方で動きます。**

    **向きは一定ではありません。** 控除が大きいほうが値打ちが高い所得もあれば、
    低い所得もあります（帯の境目をどちら側でまたぐかで決まる）。
    """
    rows = []
    for aoiro, name in AOIRO_KINDS:
        m = marginal(profit, step, aoiro=aoiro)
        rows.append({
            "帳簿": name, "青色申告特別控除": aoiro,
            "値打ち": m["値打ち"], "実効率": m["実効率"],
            "所得税の減り": m["所得税の減り"], "住民税の減り": m["住民税の減り"],
            "事業税の減り": m["事業税の減り"], "国保の減り": m["国保の減り"],
        })
    vals = [r["値打ち"] for r in rows]
    top = max(rows, key=lambda r: r["値打ち"])
    return {
        "所得（青色控除前）": profit, "経費": step, "行": rows,
        "いちばん高い帳簿": top["帳簿"], "最大の差": max(vals) - min(vals),
        # **控除が大きいほうが高いか**（向きが所得で入れ替わることの印）
        "控除が大きいほうが高いか": rows[-1]["値打ち"] > rows[0]["値打ち"],
    }


def aoiro_marginal_rows(profits: list[int] | None = None) -> list[dict]:
    """所得べつに並べた、帳簿の付け方による値打ちの差。"""
    return [aoiro_marginal(p) for p in (profits or PROFITS)]


def aoiro_flip(low: int = 1_000_000, high: int = 20_000_000,
               step_yen: int = 100_000) -> list[dict]:
    """**向きが入れ替わる所得**を、`step_yen` きざみで全部拾う。

    「控除が大きいほうが、次の1万円も効く」は**いつでも真ではありません。**
    入れ替わる点が複数あるなら、**帯の境目がそれだけ絡んでいる**という意味です。
    """
    out = []
    prev = None
    p = low
    while p <= high:
        now = aoiro_marginal(p)["控除が大きいほうが高いか"]
        if prev is not None and now != prev:
            out.append({"所得（青色控除前）": p,
                        "手前": "控除が大きいほうが高い" if prev else "小さいほうが高い",
                        "ここから": "控除が大きいほうが高い" if now else "小さいほうが高い"})
        prev = now
        p += step_yen
    return out


# ---- 介護分は40歳で乗り、65歳で降りる ------------------------------------
#: 第2号被保険者を抜けた年齢（介護保険法9条1号の第1号被保険者になる）。
AGE_AFTER_KAIGO = 65


def care_age_both_edges(profit: int, step: int = STEP) -> dict:
    """**経費の値打ちは、年齢だけで2回動きます。**

    既存の節は「40歳で介護分が乗る」側だけを見ていました
    （`care_age_gap` の既定は 39歳 対 45歳）。**降りる側があります** ——
    65歳で第1号被保険者になり、**介護分は国保から外れます。**

    上がり幅と下がり幅は、**符号を除いて同じ**になるはずです
    （同じ介護分の所得割が、乗るか乗らないかだけなので）。
    ここではそれを**引き算で確かめて**返します。
    """
    up = care_age_gap(profit, step, young=AGE_NO_KAIGO, care=AGE_KAIGO)
    down = care_age_gap(profit, step, young=AGE_KAIGO, care=AGE_AFTER_KAIGO)
    return {
        "所得（青色控除前）": profit, "経費": step,
        "40歳で乗るときの値打ちの差": up["差"],
        "65歳で降りるときの値打ちの差": down["差"],
        "幅は同じか": up["差"] == -down["差"],
        f"{AGE_NO_KAIGO}歳の国保": up[f"{AGE_NO_KAIGO}歳の国保"],
        f"{AGE_KAIGO}歳の国保": up[f"{AGE_KAIGO}歳の国保"],
        f"{AGE_AFTER_KAIGO}歳の国保": down[f"{AGE_AFTER_KAIGO}歳の国保"],
        "国保が39歳に戻るか": (up[f"{AGE_NO_KAIGO}歳の国保"]
                        == down[f"{AGE_AFTER_KAIGO}歳の国保"]),
        "国保の差（乗るとき）": up["国保の差"],
    }


def care_age_both_rows(profits: list[int] | None = None) -> list[dict]:
    """所得べつに並べた、2つの境目。"""
    return [care_age_both_edges(p) for p in (profits or PROFITS)]


# ---- 同じ45万円でも、「経費」と「控除の上乗せ」で値打ちが違う ------------
def aoiro_vs_keihi(profit: int,
                   frm: int = AOIRO_KANI, to: int = AOIRO_FUKUSHIKI) -> dict:
    """**同じ額を「経費」で落とすのと「青色控除」で増やすのとで、値打ちが違う。**

    帳簿を簡易から複式に変えると、控除は `to - frm` 円ふえます。
    **同じ額を経費で落としても、課税所得は同じだけ下がります。**
    それでも負担の減り方は同じになりません ——
    **個人事業税は、青色申告特別控除を引く前の所得から計算する**からです
    （`business_tax`）。**控除をいくら増やしても、事業税は1円も減りません。**

    差はちょうど「その額 × 事業税の率」になるはずですが、
    **事業主控除290万円の入口をまたぐ所得では、そこまで届きません。**
    ここではその両方を返します。
    """
    amount = to - frm
    base = burden(profit, frm)
    by_kojo = burden(profit, to)                       # 控除を増やした
    by_keihi = burden(profit - amount, frm)            # 同じ額を経費で落とした
    d_kojo = base["年金を除く合計"] - by_kojo["年金を除く合計"]
    d_keihi = base["年金を除く合計"] - by_keihi["年金を除く合計"]
    return {
        "所得（青色控除前）": profit,
        "額": amount,
        "控除を増やしたときの値打ち": d_kojo,
        "経費で落としたときの値打ち": d_keihi,
        "差": d_keihi - d_kojo,
        "事業税の差": base["事業税"] - by_keihi["事業税"],
        "控除で減った事業税": base["事業税"] - by_kojo["事業税"],
        "満額なら": int(amount * JIGYOZEI_RATE),
        "入口の上か": profit - amount > JIGYOZEI_KOJO,
    }


def aoiro_vs_keihi_rows(profits: list[int] | None = None) -> list[dict]:
    """所得べつに並べた、「経費」と「控除の上乗せ」の値打ちの差。"""
    return [aoiro_vs_keihi(p) for p in (profits or PROFITS)]


# ---- 2026-08-26 の回に足した3節 -----------------------------------------
#
# **どれも既にある関数の「まだ誰も引いていない軸」です。**
# `section_sweep` が拾った候補のうち、実際に当たってみて残ったものだけを入れています
# （拾われた `逆転 burden（合計）… members=6 が最大` は**掃引の目盛りの粗さ**で、
#  1人ずつ数え直すと合計は単調にふえて7人目で止まります。**節にしていません**）。


def member_cost(profit: int = 7_000_000, max_members: int = 9,
                aoiro: int = AOIRO_ETAX, age: int = 45) -> list[dict]:
    """**被保険者が1人ふえたとき、国保料の増分のうち何割が税で戻るか。**

    国民健康保険料は**全額が社会保険料控除**なので、
    人数がふえて保険料が上がると、その額だけ課税所得が下がります。
    **上がった額がそのまま出ていくわけではありません。**
    """
    base = burden(profit, aoiro, 1, age)
    out = []
    for m in range(1, max_members + 1):
        b = burden(profit, aoiro, m, age)
        d_kokuho = b["国民健康保険料"] - base["国民健康保険料"]
        d_tax = (b["所得税"] + b["住民税"]) - (base["所得税"] + base["住民税"])
        out.append({
            "被保険者数": m,
            "国民健康保険料": b["国民健康保険料"],
            "国保のふえた額": d_kokuho,
            "所得税と住民税の減り": -d_tax,
            "正味のふえた額": d_kokuho + d_tax,
            "戻る割合": (-d_tax / d_kokuho) if d_kokuho else 0.0,
        })
    return out


def member_cost_rate(profit: int = 7_000_000, aoiro: int = AOIRO_ETAX,
                     age: int = 45) -> dict:
    """`member_cost` の「戻る割合」が人数によらず一定であることを1行にしたもの。"""
    rows = [r for r in member_cost(profit, 9, aoiro, age) if r["国保のふえた額"]]
    rates = [r["戻る割合"] for r in rows]
    top = max(r["国保のふえた額"] for r in rows)
    stop = next(r for r in rows if r["国保のふえた額"] == top)
    return {
        "所得（青色控除前）": profit,
        "いちばん低い割合": min(rates),
        "いちばん高い割合": max(rates),
        "幅": max(rates) - min(rates),
        "止まる人数": stop["被保険者数"],
        "止まるまでの国保のふえた額": stop["国保のふえた額"],
        "止まるまでの税の減り": stop["所得税と住民税の減り"],
        "止まるまでの正味": stop["正味のふえた額"],
    }


def keihi_ramp(frm: int = AOIRO_KANI, to: int = AOIRO_FUKUSHIKI) -> dict:
    """**「経費」と「控除の上乗せ」の差が満額になる所得。**

    差は「その額 × 事業税の率」で頭を打ちます（`aoiro_vs_keihi`）。
    **その満額に届く所得を1円きざみで探します。** 事業税は
    `(青色控除前の所得 − 事業主控除) × 率` なので、
    **入口 ＋ その額**でちょうど満額になるはずです —— それを確かめています。
    """
    amount = to - frm
    full = int(amount * JIGYOZEI_RATE)
    lo, hi = JIGYOZEI_KOJO, JIGYOZEI_KOJO + amount * 3
    while lo < hi:
        mid = (lo + hi) // 2
        if aoiro_vs_keihi(mid, frm, to)["差"] >= full:
            hi = mid
        else:
            lo = mid + 1
    return {
        "額": amount,
        "満額の差": full,
        "差が0で終わる所得": JIGYOZEI_KOJO,
        "満額になる所得": lo,
        "1円下の差": aoiro_vs_keihi(lo - 1, frm, to)["差"],
        "坂の幅": lo - JIGYOZEI_KOJO,
        "1万円あたり": int(STEP * JIGYOZEI_RATE),
    }


def keihi_ramp_rows(frm: int = AOIRO_KANI, to: int = AOIRO_FUKUSHIKI,
                    points: int = 6) -> list[dict]:
    """坂のあいだを等分して並べた表。**両端と、そのあいだ。**"""
    r = keihi_ramp(frm, to)
    lo, hi = r["差が0で終わる所得"], r["満額になる所得"]
    out = []
    for i in range(points + 1):
        p = lo + (hi - lo) * i // points
        v = aoiro_vs_keihi(p, frm, to)
        out.append({
            "所得（青色控除前）": p,
            "差": v["差"],
            "満額まで": r["満額の差"] - v["差"],
            "入口からの距離": p - lo,
        })
    return out


#: 「国保が1円も減らない」の2つの理由。**同じ結果で、意味は正反対です。**
ZERO_NO_SHOTOKUWARI = "所得割がそもそも0（旧ただし書き所得が0）"
ZERO_AT_LIMIT = "全区分が賦課限度額（これ以上は上がらない）"
ZERO_MIXED = "国保は減る（0ではない）"


def kokuho_zero_reason(profit: int, members: int = 1,
                       aoiro: int = AOIRO_ETAX, age: int = 45) -> dict:
    """**経費1万円で国保が1円も減らないとき、その理由はどちらか。**

    `member_limit()` は「国保の減りが0になった人数」を返しますが、
    **0 になる理由は2つあります** ——
    (1) 旧ただし書き所得が0で、**所得割がそもそもかかっていない**（所得の下端）
    (2) 4区分とも**賦課限度額に当たっている**（所得の上端）。
    **どちらも「1人目から動かない」と出ます。意味は正反対です。**
    """
    shotoku = after_aoiro(profit, aoiro)
    d = kokuho.premium(shotoku, members, age)
    n_capped = d["頭打ちの本数"]
    n_parts = len(d["内訳"])
    base = kokuho.kyu_tadashigaki(shotoku)
    got = marginal(profit, STEP, aoiro, members, age)
    if got["国保の減り"] != 0:
        why = ZERO_MIXED
    elif base <= 0:
        why = ZERO_NO_SHOTOKUWARI
    elif n_capped == n_parts:
        why = ZERO_AT_LIMIT
    else:
        why = ZERO_MIXED
    return {
        "所得（青色控除前）": profit,
        "被保険者数": members,
        "青色控除後の所得": shotoku,
        "旧ただし書き所得": base,
        "国民健康保険料": d["保険料"],
        "頭打ちの区分": n_capped,
        "区分の数": n_parts,
        "国保の減り": got["国保の減り"],
        "値打ち": got["値打ち"],
        "理由": why,
    }


#: 下端と上端を並べるための所得。**両端が同じ「0」を出します。**
ZERO_PROFITS = [1_000_000, 1_080_000, 1_090_000, 5_000_000,
                11_000_000, 12_000_000, 20_000_000]


def kokuho_zero_rows(profits: list[int] | None = None) -> list[dict]:
    """所得ごとに「国保の減り」と、その理由を並べた表。"""
    return [kokuho_zero_reason(p) for p in (profits or ZERO_PROFITS)]


def kokuho_zero_edges(aoiro: int = AOIRO_ETAX) -> dict:
    """**下端の帯がどこで終わり、上端の帯がどこから始まるか**（1円きざみ）。"""
    lo, hi = 0, 20_000_000
    while lo < hi:                        # 所得割が立ちはじめる所得
        mid = (lo + hi) // 2
        if kokuho.kyu_tadashigaki(after_aoiro(mid, aoiro)) > 0:
            hi = mid
        else:
            lo = mid + 1
    starts = lo
    lo, hi = starts, 60_000_000
    while lo < hi:                        # 4区分とも限度額に当たる所得
        mid = (lo + hi) // 2
        r = kokuho_zero_reason(mid)
        if r["理由"] == ZERO_AT_LIMIT:
            hi = mid
        else:
            lo = mid + 1
    return {
        "下端が終わる所得": starts,
        "下端の値打ち": marginal(starts - 1)["値打ち"],
        "そこから1円上の値打ち": marginal(starts)["値打ち"],
        "上端が始まる所得": lo,
        "上端の1円下の国保の減り": marginal(lo - 1)["国保の減り"],
        "上端の値打ち": marginal(lo)["値打ち"],
        "下端の帯の幅": starts,
        "そのあいだ": lo - starts,
    }


def ceiling_steps(upto: int = 80_000_000) -> list[dict]:
    """**国保が限度額に当たったあと、値打ちを動かすのは所得税の段だけ。**

    上端（`kokuho_zero_edges` の「上端が始まる所得」）から上では、
    経費1万円で国保も事業税も動きません（事業税の率は一定、国保は頭打ち）。
    残るのは**速算表の段**だけなので、値打ちは階段になり、
    **最高税率に入ったところで天井**になります。

    **±1円 は端数処理のゆらぎ**なので、100円 の床で丸めて段を数えます。
    """
    start = kokuho_zero_edges()["上端が始まる所得"]
    out: list[dict] = []
    seen: set[float] = set()
    p = start
    while p <= upto:
        rate = bracket_rate(p)
        if rate not in seen:
            seen.add(rate)
            m = marginal(p)
            lo, hi = (out[-1]["入る所得"] if out else start), p
            while lo < hi:                      # その段に入る所得を1円まで詰める
                mid = (lo + hi) // 2
                if bracket_rate(mid) >= rate:
                    hi = mid
                else:
                    lo = mid + 1
            # **境目ちょうどでは 1万円 が段をまたぐ**ので、少し内側で測ります。
            m = marginal(lo + 100_000)
            out.append({
                "入る所得": lo,
                "速算表の税率": int(rate * 100),
                "値打ち": m["値打ち"],
                "実効率": m["実効率"],
                "国保の減り": m["国保の減り"],
                "事業税の減り": m["事業税の減り"],
                "住民税の減り": m["住民税の減り"],
            })
        p += 100_000
    return out


def ceiling() -> dict:
    """**経費1万円の値打ちの天井。** 最高税率に入ったところから上は動きません。"""
    steps = ceiling_steps()
    top = steps[-1]
    far = marginal(1_000_000_000)
    return {
        "入る所得": top["入る所得"],
        "速算表の税率": top["速算表の税率"],
        "値打ち": far["値打ち"],
        "実効率": far["実効率"],
        "段の数": len(steps),
        "10億円のときの値打ち": far["値打ち"],
        "正味の費用": far["正味の費用"],
    }


# ---- 主題: 「経費」と「全額所得控除」の値打ちの差（**族をまたいだ比較**）----
#
# **この2つを同じ物差しで並べた表は、どこにも公表されていません。**
#
# 中小機構の小規模企業共済の案内は「掛金は全額が所得控除」と書き、
# 節税額の表も**所得税率と住民税10パーセントを足しただけ**の額を出します。
# `src/calc/shokibo.py` の表も同じ作りで、`ASSUMPTIONS` は
# 「所得税率は……同じものとして置いています」と**自分で言っています** ——
# **その人に課税所得があるかどうかも、国保も事業税も、一度も出てきません。**
#
# いっぽう `keihi` の側は、経費1万円の値打ちを国保と事業税まで入れて出しています
# （`marginal`）。**同じ1万円なのに、片方は税率だけ、片方は4本ぶん。**
# **どちらの案内も、相手の側の数字を持っていません。**
#
# **払う側から見れば、同じ1万円をどこに置くかの選択です。**
#
#     経費に落とす          事業所得が下がる → 所得税・住民税・国保・事業税
#     青色申告特別控除      同上だが事業税は動かない（`aoiro_vs_keihi` の節）
#     小規模企業共済の掛金  **所得控除なので、所得税と住民税しか動かない**
#
# 国民健康保険料の算定は「総所得金額等 − 基礎控除43万円」で、
# **所得控除は1円も引けません**（地方税法703条の4）。
# 個人事業税も事業所得から事業主控除290万円を引くだけで、**所得控除は入りません**
# （地方税法72条の49の12）。だから **3段めだけが、2本ぶん足りない。**
#
# **ここで比べているのは「値打ち」だけです。** 経費は物やサービスが手元に残り、
# 共済の掛金は**あとで戻ってきます**（`shokibo` の側の主題）。
# **同じ1万円の「戻り」だけを並べたのがこの節**で、どちらが得かの話ではありません。


def burden_with_kojo(profit: int, kojo: int, aoiro: int = AOIRO_ETAX,
                     members: int = 1, age: int = 45) -> dict:
    """所得控除を `kojo` 円 積み増したときの負担。

    **`burden(profit - kojo)` とは別物です。** あちらは事業所得そのものを
    下げるので国保と事業税まで動きますが、こちらは**所得税と住民税だけ**
    が動きます。国保の算定は「総所得金額等 − 基礎控除43万円」で
    所得控除を引かず、事業税も事業所得から事業主控除を引くだけだからです。
    """
    base = (after_aoiro(profit, aoiro)
            - social_insurance(profit, aoiro, members, age) - kojo)
    ti = max(0, int(base) - KISO_SHOTOKU) // 1_000 * 1_000
    it = int(_income_tax_bracket(ti) * (1 + FUKKO_RATE))
    tj = max(0, int(base) - KISO_JUMIN) // 1_000 * 1_000
    rt = int(tj * JUMIN_RATE) + JUMIN_KINTOWARI
    bt = business_tax(profit)
    kh = kokuho_premium(profit, aoiro, members, age)
    return {
        "所得（青色控除前）": profit,
        "所得控除の積み増し": kojo,
        "所得税": it,
        "住民税": rt,
        "事業税": bt,
        "国民健康保険料": kh,
        "年金を除く合計": it + rt + bt + kh,
    }


def kojo_vs_keihi(profit: int, amount: int = STEP, aoiro: int = AOIRO_ETAX,
                  members: int = 1, age: int = 45) -> dict:
    """**同じ額を「経費」にするのと「全額所得控除」にするのとで、戻る額が違う。**

    返す「倍率」は経費 ÷ 所得控除です。**所得控除が0円の帯では出ません**
    （`None` を返します。0で割らないため）。

    ## **差の内訳を、引き算で作らないこと**（2026-08-28 に測って直した）

    ここには最初 `"事業税の差"` という欄があり、中身は
    **`差 − 国保の減り`** でした。**合いません。**

        事業所得 300万円   欄の値 349円   実際に減った事業税 500円
        事業所得 900万円   欄の値 196円   実際に減った事業税 500円
        事業所得 200万円   欄の値 −151円  実際に減った事業税 0円（入口の下）

    **国保は全額が社会保険料控除**なので、経費で国保が減るとその年の
    課税所得が**上がり**、所得税と住民税がその分だけ戻ってきます
    （`chain_loss` の節がまさにこれを主題にしています）。
    だから「差」から国保の減りを引いても、残るのは事業税ではありません ——
    **戻ってきた税のぶんが混ざります。**

    いまは内訳を**引き算ではなく、それぞれの内訳から直に**取っています。
    **覆る条件**: `burden` が内訳を返さなくなったら、ここも作り直すこと。
    """
    a = burden(profit, aoiro, members, age)
    b = burden(profit - amount, aoiro, members, age)
    c = burden_with_kojo(profit, amount, aoiro, members, age)
    v_keihi = a["年金を除く合計"] - b["年金を除く合計"]
    v_kojo = a["年金を除く合計"] - c["年金を除く合計"]
    return {
        "所得（青色控除前）": profit,
        "額": amount,
        "経費にしたときの値打ち": v_keihi,
        "全額所得控除にしたときの値打ち": v_kojo,
        "差": v_keihi - v_kojo,
        "倍率": (v_keihi / v_kojo) if v_kojo else None,
        "経費の実効率": v_keihi / amount,
        "所得控除の実効率": v_kojo / amount,
        # **経費でだけ減る2本**（所得控除では、どちらも1円も動きません）
        "経費で減った事業税": a["事業税"] - b["事業税"],
        "経費で減った国保": a["国民健康保険料"] - b["国民健康保険料"],
    }


def kojo_vs_keihi_rows(profits: list[int] | None = None,
                       amount: int = STEP) -> list[dict]:
    """所得べつに並べた、「経費」と「全額所得控除」の値打ちの差。"""
    return [kojo_vs_keihi(p, amount) for p in (profits or PROFITS)]


def kojo_dead_bands(amount: int = STEP, lo: int = 500_000,
                    hi: int = 2_000_000, coarse: int = 100,
                    aoiro: int = AOIRO_ETAX, members: int = 1,
                    age: int = 45) -> list[tuple[int, int]]:
    """**「全額所得控除」が1円も戻らない所得の帯を、1円の端まで出す。**

    課税所得（所得税・住民税とも）が0の帯では、所得控除をいくら積んでも
    税は1円も減りません。**同じ帯で、経費のほうは国保が減るので戻ります。**

    ## **帯は1本ではありません**（2026-08-28 に、二分法で外して気づいた）

    ここは最初「所得が上がれば課税所得も上がるので境目は1つ」と書いて
    **二分法**で解いていました。**単調ではありません。**

        1,390,000円   国保  81,445円   所得控除の値打ち 1,000円
        1,390,200円   国保 106,251円   所得控除の値打ち     0円  ← 戻った

    **国民健康保険料の軽減が1段 外れると、保険料が 24,806円 跳ね上がります。**
    保険料は全額が社会保険料控除なので、**課税所得はそのぶん押し戻されて
    また0になります。** だから「戻らない帯」は谷をはさんで2本あり、
    二分法は**下の1本の上端**（1,369,970円）を返して、
    本当の上端（1,398,436円）を 28,466円 取りこぼしていました。

    **総当たりは 0.11ms × 150万回 ＝ 165秒** で、毎回の生成には重すぎます。
    だから `coarse` 円きざみで帯を見つけ、**変わり目の窓の中だけ1円で詰めます**
    （実測 3秒）。**窓の中を1円で全部見るので、二分法の単調の仮定は要りません。**

    **覆る条件**: `coarse` より狭い帯があると、粗いほうで見落とします。
    いまの軽減の段（5割・2割）の幅は 数万円 なので 100円 で足りますが、
    **段の数が増えたら、この幅を疑うこと。**
    """
    return _kojo_dead_bands(amount, lo, hi, coarse, aoiro, members, age)


@_lru_cache(maxsize=64)
def _kojo_dead_bands(amount: int, lo: int, hi: int, coarse: int,
                     aoiro: int, members: int, age: int) -> list[tuple[int, int]]:
    """`kojo_dead_bands()` の中身。**控えを効かせるためだけに分けてあります。**

    ## なぜ分けるのか（2026-08-28・最適化の回）

    `lru_cache` は**呼び出しの字**で控えます。`kojo_dead_bands()`（引数なし）と
    `kojo_dead_edge()` の中の `kojo_dead_bands(amount, lo, hi, ...)`（位置引数）は
    **値が全部おなじでも、別の鍵**になります。だから公開の関数の側で既定を
    埋めきってから、**必ず7つの位置引数**でここを呼びます。

    実測: `check_tables()` は 2.06秒 → **1.14秒**（同じ盤面を2度 走っていた）。
    **これだけでは門（1.0秒）を割れません** —— 効いたのは
    `kokuho_premium` の控えのほうで、合わせて **0.26秒** です。
    **両方 残すこと**: 片方だけだと、盤面が広がった日にまた越えます。

    **返り値を書き換えないこと。** 控えは同じリストを配ります。
    """
    def dead(p: int) -> bool:
        return kojo_vs_keihi(p, amount, aoiro, members, age)[
            "全額所得控除にしたときの値打ち"] == 0

    marks = [(p, dead(p)) for p in range(lo, hi + 1, coarse)]
    bands: list[tuple[int, int]] = []
    start: int | None = None
    for i, (p, d) in enumerate(marks):
        if d and start is None:
            # 帯の入口。1つ前の窓を1円で詰める
            back = marks[i - 1][0] if i else p
            start = next((q for q in range(back, p + 1) if dead(q)), p)
        elif not d and start is not None:
            end = next((q - 1 for q in range(marks[i - 1][0], p + 1)
                        if not dead(q)), p - 1)
            bands.append((start, end))
            start = None
    if start is not None:
        bands.append((start, marks[-1][0]))
    return bands


def kojo_dead_edge(amount: int = STEP, lo: int = 500_000,
                   hi: int = 2_000_000, coarse: int = 100,
                   aoiro: int = AOIRO_ETAX, members: int = 1,
                   age: int = 45) -> int:
    """**「全額所得控除」が1円も戻らない、いちばん上の所得。**

    `kojo_dead_bands` の**最後の帯の上端**です。
    **「いちばん下の帯の上端」ではありません**（あちらは 1,369,970円）。
    """
    bands = kojo_dead_bands(amount, lo, hi, coarse, aoiro, members, age)
    return bands[-1][1] if bands else lo - 1


def kojo_gap_settles(amount: int = STEP, lo: int = 5_000_000,
                     hi: int = 30_000_000, step_yen: int = 10_000,
                     aoiro: int = AOIRO_ETAX, members: int = 1,
                     age: int = 45) -> dict:
    """**差が「額 × 事業税の率」だけになる、いちばん下の所得。**

    国民健康保険料が賦課限度額に当たると、経費を増やしても国保は1円も
    減りません。そこから上では、経費と所得控除の違いは**事業税だけ**です。
    """
    target = int(amount * JIGYOZEI_RATE)
    found = None
    for p in range(hi, lo - 1, -step_yen):
        if kojo_vs_keihi(p, amount, aoiro, members, age)["差"] != target:
            break
        found = p
    return {
        "額": amount,
        "事業税ぶん": target,
        "差がここだけになる所得": found,
        "きざみ": step_yen,
    }

def check_tables() -> None:
    """制度の値と、この計算の主題そのものを確かめる。"""
    _checks.statutory(AOIRO_ETAX, 650_000, "青色申告特別控除（e-Tax等）",
                      source="租税特別措置法25条の2")
    _checks.statutory(AOIRO_FUKUSHIKI, 550_000, "青色申告特別控除（複式簿記）",
                      source="租税特別措置法25条の2")
    _checks.statutory(AOIRO_KANI, 100_000, "青色申告特別控除（簡易簿記）",
                      source="租税特別措置法25条の2")
    _checks.statutory(KISO_SHOTOKU, 480_000, "所得税の基礎控除",
                      source="所得税法86条")
    _checks.statutory(KISO_JUMIN, 430_000, "住民税の基礎控除",
                      source="地方税法314条の2第1項の2")
    _checks.statutory(JIGYOZEI_KOJO, 2_900_000, "個人事業税の事業主控除",
                      source="地方税法72条の49の14")
    _checks.ratio(JIGYOZEI_RATE, "個人事業税の税率")
    _checks.ratio(JUMIN_RATE, "住民税の所得割")
    _checks.ratio(FUKKO_RATE, "復興特別所得税")
    _checks.assumption_values(ASSUMPTIONS, name="keihi")

    # 1. 負担は所得とともに増える（**向きが逆なら、どこかで符号を落としています**）
    _checks.increases_with(lambda p: burden(p)["合計"], PROFITS,
                           "所得が増えたのに負担の合計が増えていない")

    # 2. **この表の主題。**「税率ぶんだけ得をする」は必ず小さすぎる
    for p in (3_000_000, 5_000_000, 9_000_000):
        _checks.greater(marginal(p)["実効率"], naive_rate(p),
                        f"所得{p:,}円で、経費の実効率が速算表の税率以下")

    # 3. **事業税の入口は、青色申告特別控除を引く前**。引いた額とは65万円ずれる
    edge = jigyozei_edge()
    _checks.rounding(edge["そのときの事業所得（青色控除後）"],
                     JIGYOZEI_KOJO - AOIRO_ETAX,
                     "事業税の入口に立つ人の、青色控除後の事業所得")

    # 4. **単調ではありません。** 上に行くほど値打ちが上がる、が嘘であること
    if not drops():
        raise _checks.TableError(
            "実効率が下がる点が1つもありません。"
            "国保の賦課限度額を越える所得が表に入っていないか、限度額が効いていません")

    # 5. 青色申告特別控除を増やしても、事業税は1円も動かない
    rows = aoiro_rows()
    if len({r["事業税"] for r in rows}) != 1:
        raise _checks.TableError(
            f"青色申告特別控除で事業税が動いています: "
            f"{[r['事業税'] for r in rows]}")
    _checks.unique_by(rows, lambda r: r["青色申告特別控除"], "青色申告特別控除の表")

    # 6. **人数がふえて保険料が「下がる」点があること。** 軽減の判定所得が
    #    「43万円 ＋ 人数×一定額」なので、人数のほうが段をまたぎます
    if not member_drop_rows():
        raise _checks.TableError(
            "人数を1人ふやして保険料が下がる点が1つもありません。"
            "国保の軽減判定に被保険者数が入っていないか、軽減が効いていません")

    # 7. **所得が高いほど、経費の値打ちが人数で動かなくなるのが早い**
    #    （賦課限度額に早く当たるので）。**逆向きなら限度額を落としています**
    _checks.decreases_with(lambda p: member_limit(p)["人数"],
                           MEMBER_PROFITS,
                           "所得が高いほど、国保が頭打ちになる人数が多くなっている")

    # 8. **この3節の主題。** 同じ所得・同じ経費でも、人数で戻る額が変わる
    lim = member_limit(7_000_000)
    _checks.greater(lim["落ちる額"], 500,
                    "所得700万円で、人数による値打ちの落差が500円以下")

    # --- 帳簿の付け方で値打ちが動く（`aoiro_marginal` の節）------------------
    # 1. **節の題そのもの**: 所得500万円で、3つの帳簿の値打ちが同じではない。
    #    ここが 0 になったら、`marginal()` が `aoiro` を無視しています。
    if aoiro_marginal(5_000_000)["最大の差"] <= 0:
        raise ValueError(
            "所得500万円で、帳簿の付け方による値打ちの差が0です。"
            "`marginal()` が `aoiro` を使っていないか、節の題が古くなっています")
    # 2. **向きが一定でないこと**（節の後半の主張）。
    #    入れ替わりが1つも無ければ、「控除が大きいほど効く」が言えてしまいます。
    if len(aoiro_flip()) < 2:
        raise ValueError(
            "帳簿の向きが入れ替わる所得が2つ未満です。"
            "節は『向きは一定ではない』が主題なので、書き直すこと")
    # 3. **控除が大きいほど、その年の負担そのものは必ず軽い**（値打ちとは別の話）。
    #    ここが崩れたら、上の節が「負担も逆転する」と読まれます。
    for p in PROFITS:
        tot = [burden(p, a)["年金を除く合計"] for a, _ in AOIRO_KINDS]
        for x, y in zip(tot, tot[1:]):
            if y > x:
                raise ValueError(
                    f"所得{p:,}円: 控除を増やしたのに負担が増えています {tot}")

    # --- 介護分の2つの境目（`care_age_both_edges` の節）----------------------
    # 4. **国保は65歳で、39歳の額にぴったり戻る**（節の題）。
    #    戻らなければ、介護分以外のものが年齢で動いています。
    for p in PROFITS:
        r = care_age_both_edges(p)
        if not r["国保が39歳に戻るか"]:
            raise ValueError(
                f"所得{p:,}円: 65歳の国保が39歳に戻っていません "
                f"({r[f'{AGE_NO_KAIGO}歳の国保']} → {r[f'{AGE_AFTER_KAIGO}歳の国保']})")
        # 5. **上がり幅と下がり幅は、符号を除いて同じ。**
        if not r["幅は同じか"]:
            raise ValueError(
                f"所得{p:,}円: 40歳の差 {r['40歳で乗るときの値打ちの差']} と "
                f"65歳の差 {r['65歳で降りるときの値打ちの差']} が釣り合っていません")
    # 6. **値打ちの差は所得によらず一定**（限度額の下では）。**節の後半そのもの**。
    #    国保そのものの差は所得で動くのに、値打ちの差は動かない ——
    #    そこが「率で決まっていて額では決まっていない」ことの証拠です。
    band = [care_age_both_edges(p)["40歳で乗るときの値打ちの差"]
            for p in (2_000_000, 3_000_000, 4_000_000, 5_000_000, 7_000_000)]
    if len(set(band)) != 1:
        raise ValueError(f"限度額の下で、年齢による値打ちの差が動いています: {band}")
    kokuho_gaps = [care_age_both_edges(p)["国保の差（乗るとき）"]
                   for p in (2_000_000, 5_000_000, 7_000_000)]
    if len(set(kokuho_gaps)) != 3:
        raise ValueError(
            f"国保そのものの差が所得で動いていません: {kokuho_gaps}。"
            "節は『額は動くのに値打ちは動かない』が主題です")

    # --- 経費と控除の上乗せ（`aoiro_vs_keihi` の節）--------------------------
    # 7. **入口より上では、差はちょうど「額 × 事業税の率」**（節の題）。
    for p in (4_000_000, 5_000_000, 7_000_000, 12_000_000):
        r = aoiro_vs_keihi(p)
        if not r["入口の上か"]:
            raise ValueError(f"所得{p:,}円が事業税の入口の下になっています")
        if r["差"] != r["満額なら"]:
            raise ValueError(
                f"所得{p:,}円: 差 {r['差']} が満額 {r['満額なら']} と合いません")
    # 8. **控除をいくら増やしても、事業税は1円も減らない**（節の根拠そのもの）。
    for p in PROFITS:
        r = aoiro_vs_keihi(p)
        if r["控除で減った事業税"] != 0:
            raise ValueError(
                f"所得{p:,}円: 青色控除を増やして事業税が {r['控除で減った事業税']}円 "
                "減っています。`business_tax` は青色控除前の所得で計算するはず")
    # 9. **入口の下では差が0**（事業税そのものが無いので）。
    for p in (1_000_000, 2_000_000):
        if aoiro_vs_keihi(p)["差"] != 0:
            raise ValueError(f"事業税の入口の下（所得{p:,}円）で、差が出ています")
    # 10. **経費のほうが必ず得か、同じ**（逆転したら節の向きが嘘になります）。
    for p in PROFITS:
        r = aoiro_vs_keihi(p)
        if r["経費で落としたときの値打ち"] < r["控除を増やしたときの値打ち"]:
            raise ValueError(
                f"所得{p:,}円: 控除の上乗せのほうが経費より得になっています")


    # --- 経費と「全額所得控除」（`kojo_vs_keihi` の節）----------------------
    # 11. **節の題そのもの**: 同じ額でも経費のほうが必ず大きい（か、等しい）。
    #     所得控除は所得税と住民税しか動かさず、経費はその2本も同じだけ動かす。
    for p in PROFITS:
        r = kojo_vs_keihi(p)
        if r["経費にしたときの値打ち"] < r["全額所得控除にしたときの値打ち"]:
            raise ValueError(
                f"所得{p:,}円: 全額所得控除 {r['全額所得控除にしたときの値打ち']}円 が "
                f"経費 {r['経費にしたときの値打ち']}円 を上回っています。"
                "`burden_with_kojo` が国保か事業税まで動かしています")
    # 12. **所得控除では、国保も事業税も1円も動かない**（節の根拠そのもの）。
    for p in PROFITS:
        a = burden(p)
        b = burden_with_kojo(p, STEP)
        if a["国民健康保険料"] != b["国民健康保険料"]:
            raise ValueError(
                f"所得{p:,}円: 所得控除で国保が動いています "
                f"({a['国民健康保険料']} → {b['国民健康保険料']})")
        if a["事業税"] != b["事業税"]:
            raise ValueError(
                f"所得{p:,}円: 所得控除で事業税が動いています "
                f"({a['事業税']} → {b['事業税']})")
    # 13. **「1円も戻らない帯」がある**（2節めの題）。そこでも経費は戻ること。
    bands = kojo_dead_bands()
    if len(bands) < 2:
        raise ValueError(
            f"所得控除が1円も戻らない帯が {len(bands)}本 しかありません。"
            "節の題は『1本ではなく2本ある』です。"
            "国保の軽減の段が消えたか、`kojo_dead_bands` の粗さが帯をまたいでいます")
    #     **帯が割れている理由そのもの**: 谷の右端で国保が跳ね、値打ちが落ちること。
    #     ここが単調に増えるようになったら、2節めの後半は書き直しです。
    gap_hi = bands[1][0]
    if kokuho_premium(gap_hi) <= kokuho_premium(gap_hi - 1):
        raise ValueError(
            f"事業所得 {gap_hi:,}円 で国保が上がっていません "
            f"({kokuho_premium(gap_hi - 1):,} → {kokuho_premium(gap_hi):,})。"
            "帯が2本に割れる理由（軽減が外れて保険料が跳ねる）が消えています")
    if (kojo_vs_keihi(gap_hi)["全額所得控除にしたときの値打ち"]
            >= kojo_vs_keihi(gap_hi - 1)["全額所得控除にしたときの値打ち"]):
        raise ValueError(
            f"事業所得 {gap_hi:,}円 で、所得控除の値打ちが下がっていません。"
            "節の後半（所得が増えたのに値打ちが下がる）が成り立ちません")
    edge = kojo_dead_edge()
    if edge != bands[-1][1]:
        raise ValueError(
            f"`kojo_dead_edge` が {edge:,}円 を返していますが、"
            f"最後の帯の上端は {bands[-1][1]:,}円 です")
    r_in = kojo_vs_keihi(edge)
    r_out = kojo_vs_keihi(edge + 1)
    if r_in["全額所得控除にしたときの値打ち"] != 0:
        raise ValueError(
            f"所得{edge:,}円で、所得控除の値打ちが "
            f"{r_in['全額所得控除にしたときの値打ち']}円 あります（0のはず）")
    if r_out["全額所得控除にしたときの値打ち"] == 0:
        raise ValueError(
            f"所得{edge + 1:,}円でも所得控除の値打ちが0です。"
            "`kojo_dead_edge` が上端を1円まで詰めていません")
    if r_in["経費にしたときの値打ち"] <= 0:
        raise ValueError(
            f"所得{edge:,}円で、経費の値打ちが "
            f"{r_in['経費にしたときの値打ち']}円 です。"
            "節は『所得控除が0でも経費は戻る』が主題なので、書き直すこと")
    # 14. **上では差が事業税ぶんだけになる**（3節めの題）。
    st = kojo_gap_settles()
    if st["差がここだけになる所得"] is None:
        raise ValueError(
            "経費と所得控除の差が「額×事業税の率」だけになる所得が見つかりません。"
            "国保の賦課限度額が効いていないか、事業税の率が変わっています")
    if kojo_vs_keihi(st["差がここだけになる所得"])["差"] != st["事業税ぶん"]:
        raise ValueError("`kojo_gap_settles` が返した所得で、差が事業税ぶんと合いません")
    # 15. **内訳の欄は、内訳そのものであること**（引き算で作らないこと）。
    #     ここは一度「差 − 国保の減り」で作って外しました ——
    #     国保は社会保険料控除なので、減ると所得税と住民税が戻ってきて混ざります。
    for p in PROFITS:
        r = kojo_vs_keihi(p)
        a, b = burden(p), burden(p - STEP)
        if r["経費で減った事業税"] != a["事業税"] - b["事業税"]:
            raise ValueError(
                f"所得{p:,}円: `経費で減った事業税` {r['経費で減った事業税']} が "
                f"内訳の差 {a['事業税'] - b['事業税']} と合いません")
        if r["経費で減った国保"] != a["国民健康保険料"] - b["国民健康保険料"]:
            raise ValueError(
                f"所得{p:,}円: `経費で減った国保` {r['経費で減った国保']} が "
                f"内訳の差 {a['国民健康保険料'] - b['国民健康保険料']} と合いません")
        # **上の帯では、差がまるごと事業税**（国保がもう減らないので）。
        if r["経費で減った国保"] == 0 and r["差"] != r["経費で減った事業税"]:
            raise ValueError(
                f"所得{p:,}円: 国保が1円も減らないのに、差 {r['差']} が "
                f"事業税の減り {r['経費で減った事業税']} と違います")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 経費1万円の値打ちは、所得税の税率の2倍以上ある ===")
    for row in grid():
        print(f"  所得 {row['所得']:>10,}円  速算表 {row['速算表の税率']:>4}%  "
              f"→ 値打ち {row['値打ち']:>7,}円（実効率 {row['実効率']:>5}%）  "
              f"正味の費用 {row['正味の費用']:>6,}円")

    print("\n=== 経費の値打ちは、所得が上がるほど大きい、ではない ===")
    for r in reversals():
        print(f"  所得 {r['低いほうの所得']:>10,}円 {r['低いほうの実効率']:>5}%  ＞  "
              f"所得 {r['高いほうの所得']:>10,}円 {r['高いほうの実効率']:>5}%"
              f"（{r['差']}ポイント低い）")

    print("\n=== 経費1万円で保険料が2万円以上下がる所得がある ===")
    pk = peak()
    print(f"  いちばん高いのは 所得 {pk['所得']:,}円 の {pk['実効率'] * 100:.2f}%"
          f"（値打ち {pk['値打ち']:,}円）")
    for d in drops(0.005):
        print(f"  所得 {d['所得']:>10,}円 で "
              f"{d['前の実効率'] * 100:.2f}% → {d['実効率'] * 100:.2f}% "
              f"（{d['落ち幅'] * 100:.2f}ポイント下がる）")

    print("\n=== いちばん得をする所得は、10万円きざみの表には1つも乗っていない ===")
    pk = peak()
    for st in (100_000, 10_000, 1_000):
        co = max(rate_curve(step=st), key=lambda r: r["実効率"])
        print(f"  {st:>7,}円きざみで探すと 所得 {co['所得']:>9,}円 "
              f"（値打ち {co['値打ち']:>6,}円）  本当の山との差 "
              f"{pk['値打ち'] - co['値打ち']:>5,}円")
    print(f"  1円きざみ            所得 {pk['所得']:>9,}円 "
          f"（値打ち {pk['値打ち']:>6,}円）  ← 同じ値打ちになる所得は**1円しかない**")
    for p0 in (1_089_994, 1_390_200, 1_651_800):
        m = marginal(p0)
        n = 1
        while marginal(p0 - n)["実効率"] == m["実効率"]:
            n += 1
        lo = p0 - n + 1
        n = 1
        while marginal(p0 + n)["実効率"] == m["実効率"]:
            n += 1
        print(f"  軽減の段の山 所得 {p0:>9,}円  値打ち {m['値打ち']:>6,}円  "
              f"同じ値打ちの幅 {p0 + n - lo}円")

    print("\n=== 所得が1円ちがうと、経費1万円の値打ちが22,980円ちがう ===")
    c = cliff()
    print(f"  所得 {c['1円下の所得']:,}円 → 値打ち {c['前の値打ち']:,}円"
          f"（{c['前の実効率'] * 100:.2f}%）")
    print(f"  所得 {c['所得']:,}円 → 値打ち {c['値打ち']:,}円"
          f"（{c['実効率'] * 100:.2f}%）")
    print(f"  1円で {c['値打ち'] - c['前の値打ち']:,}円 ＝ "
          f"{c['上がり幅'] * 100:.1f}ポイント跳ぶ")

    print("\n=== 事業税の290万円は、青色申告特別控除を引く前で判定される ===")
    e = jigyozei_edge()
    print(f"  事業税がかかり始めるのは 青色控除前 {e['事業税の入口（青色控除前）']:,}円")
    print(f"  そのときの事業所得（青色控除後）は "
          f"{e['そのときの事業所得（青色控除後）']:,}円")
    print(f"  入口の下 {e['入口の下の実効率'] * 100:.2f}% → "
          f"上 {e['入口の上の実効率'] * 100:.2f}%")

    print("\n=== 国保が減ると税が増える。差し引きは足し算より小さい ===")
    for pr in (3_000_000, 5_000_000, 7_000_000, 9_000_000, 12_000_000):
        c = chain_loss(pr)
        print(f"  所得 {c['所得']:>10,}円  率の足し算 {c['合計率'] * 100:>5.2f}%"
              f"（{c['素直な足し算']:>6,}円）  実際 {c['実効率'] * 100:>5.2f}%"
              f"（{c['実際の値打ち']:>6,}円）  差 {c['差']:>5,}円"
              f"＝{c['取り返される割合'] * 100:.1f}%が戻る")

    print("\n=== 40歳の誕生日から、同じ経費1万円の値打ちが225円ふえる"
          "（所得790万円から上では、ふえない）===")
    print(f"{'所得':>10}{'39歳の値打ち':>14}{'45歳の値打ち':>14}{'差':>7}"
          f"{'39歳の国保':>12}{'45歳の国保':>12}{'国保の差':>10}")
    for row in care_age_rows():
        print(f"{row['所得']:>9,}円{row['39歳の値打ち']:>13,}円"
              f"{row['45歳の値打ち']:>13,}円{row['差']:>6,}円"
              f"{row['39歳の国保']:>11,}円{row['45歳の国保']:>11,}円"
              f"{row['国保の差']:>9,}円")
    vanish = care_gap_vanishes()
    print(f"  → 介護納付金分（所得割2.25パーセント・均等割1万6,600円）は"
          f"**40歳から64歳までしか乗りません。** 保険料そのものが上がる話は"
          f"よく書かれていますが、**同時に「経費1万円で減る額」も上がります** ——"
          f"所得500万円なら 3,389円 → 3,614円 で、差は所得割そのものの 225円 です")
    print(f"  → **ただし、ふえるのは所得 {vanish:,}円 まで。** そこから上は"
          f"介護納付金分が賦課限度額の {kokuho.LIMIT_KAIGO:,}円 に当たっていて、"
          f"経費を1万円ふやしても介護分は1円も減りません。"
          f"**40歳になっても、経費の値打ちは1円も変わらない帯があります**"
          f"（この表では所得900万円以上）")
    print(f"  → 65歳の誕生日で、この 225円 はそのまま消えます"
          f"（介護保険の第2号被保険者は {kokuho.KAIGO_FROM}歳から{kokuho.KAIGO_TO}歳まで）")

    print("\n=== 青色申告特別控除を55万円から65万円にしても、事業税は1円も減らない ===")
    for row in aoiro_rows():
        print(f"  {row['青色申告特別控除']:<12} 所得税 {row['所得税']:>8,}円  "
              f"住民税 {row['住民税']:>8,}円  事業税 {row['事業税']:>8,}円  "
              f"国保 {row['国民健康保険料']:>8,}円  合計 {row['合計']:>9,}円")

    print("\n=== 家族が1人ふえたのに、国民健康保険料が10万7,380円「下がる」点がある ===")
    print("  **均等割は1人いくらなので、人数がふえれば必ず上がる**——ではありません。")
    print("  軽減の判定所得が「43万円 ＋ 被保険者数 × 一定額」で決まるので、")
    print("  **人数のほうが軽減の段をまたぎます。**")
    print(f"{'所得（青色控除前）':>12}{'人数':>6}{'1人前の保険料':>14}{'その人数の保険料':>16}"
          f"{'下がる額':>10}{'軽減':>12}")
    for r in member_drop_rows():
        print(f"{r['所得（青色控除前）']:>11,}円{r['人数']:>5}人{r['1人前の保険料']:>13,}円"
              f"{r['保険料']:>15,}円{r['下がった額']:>9,}円"
              f"{str(r['1人前の軽減']) + '%→' + str(r['軽減の割合']) + '%':>12}")
    print("  → いちばん大きいのは 所得400万円の10人目で **16万6,500円**。")
    print("     **1人ふえるほうが、年16万円あまり安い。**")
    print("  → 所得300万円では 7人目で 10万7,380円 下がります"
          "（2割軽減 → 5割軽減）。")
    print("  → 軽減の額は世帯の所得で決まり、**事業所得が同じでも人数で段が変わります。**")

    print("\n=== 同じ所得・同じ経費でも、戻ってくる額が家族の人数で991円ちがう ===")
    print("  所得700万円・経費1万円。**動かしているのは被保険者数だけです。**")
    print(f"{'人数':>5}{'国民健康保険料':>14}{'軽減':>6}{'所得税':>11}{'住民税':>11}"
          f"{'負担の合計':>13}{'値打ち':>9}{'実効率':>9}")
    for row in member_rows(7_000_000):
        print(f"{row['被保険者数']:>4}人{row['国民健康保険料']:>13,}円"
              f"{row['軽減の割合']:>5}%{row['所得税']:>10,}円{row['住民税']:>10,}円"
              f"{row['負担の合計']:>12,}円{row['値打ち']:>8,}円"
              f"{row['実効率'] * 100:>8.2f}%")
    print("  → 1人の 4,533円 から 7人の 3,542円 まで、**991円ちがいます。**")
    print("  → 減っていくのは、国保の所得割が**区分ごとに賦課限度額へ当たっていく**からです。")
    print("     当たった区分は、経費を1万円ふやしても1円も減りません。")
    print("  → **扶養家族が多い人ほど、経費の節税効果は小さい。**"
          "一般の解説の「税率ぶん」には、この差が1円も出てきません。")

    print("\n=== 経費の値打ちが家族の人数で動かなくなる人数は、所得で20人から1人まで変わる ===")
    print("  国保の所得割が4区分とも賦課限度額（合計113万円）に当たると、")
    print("  **そこから先は人数が何人ふえても、経費1万円の値打ちは1円も動きません。**")
    print(f"{'所得（青色控除前）':>12}{'止まる人数':>12}{'そこでの値打ち':>14}"
          f"{'1人のときの値打ち':>18}{'落ちる額':>10}")
    for r in member_limit_rows():
        print(f"{r['所得（青色控除前）']:>11,}円{r['人数']:>11,}人"
              f"{r['値打ち']:>13,}円{r['1人のときの値打ち']:>17,}円"
              f"{r['落ちる額']:>9,}円")
    print("  → 所得1,200万円は **1人目から**動きません（所得割だけで限度額に当たっている）。")
    print("  → 所得500万円で止まるのは20人目です。**実際の世帯では起こりません** ——")
    print("     つまり、所得500万円の帯では人数が値打ちを削り続けます。")
    print(f"  → 止まったあとの値打ちは、所得600万〜900万円では **3,542円** でそろいます"
          f"（所得税・住民税・事業税だけになった額）。**所得がちがっても同じ額です。**")

    am5 = aoiro_marginal(5_000_000)
    flips = aoiro_flip()
    print(f"\n=== 同じ所得・同じ経費1万円でも、帳簿の付け方で値打ちが"
          f"{am5['最大の差']:,}円 ちがう（所得500万円）===")
    print(f"  前提: 事業所得（青色控除前）／単身・{AGE_KAIGO}歳・国保／経費 {STEP:,}円 ／"
          f"青色申告特別控除は 10万・55万・65万の3つ")
    print("  青色申告特別控除は課税所得を下げるので、**その人が乗っている帯が変わります。**"
          "帯が変われば、次の1万円の経費が効く率も変わる ——"
          "**「経費1万円の値打ち」は、帳簿の付け方で動きます。**")
    print(f"{'所得':>11s} {'簡易10万':>10s} {'複式55万':>10s} {'eTax65万':>10s} "
          f"{'最大の差':>9s} {'いちばん高い帳簿':>16s}")
    for r in aoiro_marginal_rows():
        v = {x["帳簿"]: x["値打ち"] for x in r["行"]}
        print(f"{r['所得（青色控除前）']:>10,d}円 "
              f"{v['簡易簿記10万円']:>9,d}円 {v['複式簿記55万円']:>9,d}円 "
              f"{v['e-Tax65万円']:>9,d}円 {r['最大の差']:>8,d}円 "
              f"{r['いちばん高い帳簿']:>16s}")
    print(f"  **向きは一定ではありません。** 100万〜2,000万を10万円きざみで見ると、"
          f"「控除が大きいほうが高い」と「小さいほうが高い」が **{len(flips)}回 入れ替わります。**")
    print("  入れ替わる所得（先頭6件）: "
          + " / ".join(f"{r['所得（青色控除前）']:,}円" for r in flips[:6]))
    print("  **帯の境目をどちら側でまたぐかで決まる**ので、"
          "「控除が大きいほど次の1円も効く」は言えません。")

    cb = care_age_both_rows()
    cb5 = care_age_both_edges(5_000_000)
    print(f"\n=== 経費の値打ちは、年齢だけで2回動く —— 40歳で "
          f"{cb5['40歳で乗るときの値打ちの差']:+,}円、65歳で "
          f"{cb5['65歳で降りるときの値打ちの差']:+,}円（所得500万円）===")
    print(f"  前提: 事業所得（青色控除前）／単身・国保／経費 {STEP:,}円 ／"
          f"青色申告特別控除 65万円 ／ 介護分は40歳から65歳まで")
    print("  既存の表は「40歳で介護分が乗る」側だけを見ていました。"
          "**降りる側があります** —— 65歳で第1号被保険者になり、"
          "**介護分は国保から外れます。**")
    print(f"{'所得':>11s} {'39歳の国保':>12s} {'45歳の国保':>12s} {'65歳の国保':>12s} "
          f"{'40歳で':>8s} {'65歳で':>8s} {'国保の差':>10s}")
    for r in cb:
        print(f"{r['所得（青色控除前）']:>10,d}円 "
              f"{r[f'{AGE_NO_KAIGO}歳の国保']:>11,d}円 "
              f"{r[f'{AGE_KAIGO}歳の国保']:>11,d}円 "
              f"{r[f'{AGE_AFTER_KAIGO}歳の国保']:>11,d}円 "
              f"{r['40歳で乗るときの値打ちの差']:>+7,d}円 "
              f"{r['65歳で降りるときの値打ちの差']:>+7,d}円 "
              f"{r['国保の差（乗るとき）']:>9,d}円")
    print(f"  **国保は65歳で、39歳のときの額にぴったり戻ります**"
          f"（{cb5[f'{AGE_NO_KAIGO}歳の国保']:,}円 → "
          f"{cb5[f'{AGE_KAIGO}歳の国保']:,}円 → "
          f"{cb5[f'{AGE_AFTER_KAIGO}歳の国保']:,}円）。"
          f"**上がり幅と下がり幅も、符号を除いて同じ**です。")
    print(f"  **そして値打ちの差は、所得が変わっても "
          f"{cb5['40歳で乗るときの値打ちの差']:,}円 のまま**です ——"
          f"国保の差のほうは {cb[1]['国保の差（乗るとき）']:,}円 から "
          f"{cb[5]['国保の差（乗るとき）']:,}円 まで動くのに。"
          "**値打ちを決めているのは介護分の所得割の率そのもの**で、額ではありません。")
    print("  所得900万円から上で 0円 になるのは、"
          "**介護分が賦課限度額に当たって、経費を増やしても1円も減らなくなる**からです"
          "（±1円は端数処理のゆらぎ）。")

    vs = aoiro_vs_keihi_rows()
    vs5 = aoiro_vs_keihi(5_000_000)
    print(f"\n=== 同じ {vs5['額']:,}円 でも、「経費」なら "
          f"{vs5['経費で落としたときの値打ち']:,}円、"
          f"「青色控除の上乗せ」なら {vs5['控除を増やしたときの値打ち']:,}円"
          f"（差 {vs5['差']:,}円・所得500万円）===")
    print(f"  前提: 事業所得（青色控除前）／単身・{AGE_KAIGO}歳・国保 ／"
          f"簡易簿記10万円 → 複式簿記55万円（控除が {vs5['額']:,}円 ふえる）と、"
          f"同じ {vs5['額']:,}円 を経費で落とした場合を比べています")
    print("  課税所得はどちらも同じだけ下がります。それでも負担の減り方は同じになりません ——"
          "**個人事業税は、青色申告特別控除を引く前の所得から計算する**からです。"
          "**控除をいくら増やしても、事業税は1円も減りません。**")
    print(f"{'所得':>11s} {'控除で':>11s} {'経費で':>11s} {'差':>10s} "
          f"{'事業税の入口の上か':>18s}")
    for r in vs:
        print(f"{r['所得（青色控除前）']:>10,d}円 "
              f"{r['控除を増やしたときの値打ち']:>10,d}円 "
              f"{r['経費で落としたときの値打ち']:>10,d}円 "
              f"{r['差']:>9,d}円 "
              f"{('上' if r['入口の上か'] else '下'):>18s}")
    print(f"  **入口より上では、差はちょうど {vs5['額']:,}円 × "
          f"{JIGYOZEI_RATE * 100:.0f}パーセント ＝ {vs5['満額なら']:,}円** です。"
          f"事業主控除 {JIGYOZEI_KOJO:,}円 より下では事業税そのものが0なので、差も0。"
          "**またぐ所得だけ、その中間になります。**")

    ze = kokuho_zero_edges()
    print(f"\n=== 経費1万円で、税も保険料も1円も減らない所得がある"
          f"（{ze['下端が終わる所得']:,}円 まで）===")
    print(f"  前提: 事業所得（青色控除前）／単身・{AGE_KAIGO}歳・国保 ／"
          f"青色申告特別控除 {AOIRO_ETAX:,}円 ／ 経費 {STEP:,}円")
    print("  「経費は税率ぶんだけ得」の税率がいちばん低い人は5パーセントです。"
          "**その下に、0パーセントの帯があります。**")
    print(f"  所得 {ze['下端が終わる所得'] - 1:,}円 まで  値打ち "
          f"{ze['下端の値打ち']:,}円  ← **1円も戻りません**")
    print(f"  その1円上（{ze['下端が終わる所得']:,}円）  値打ち "
          f"{ze['そこから1円上の値打ち']:,}円  ← **1円で {ze['そこから1円上の値打ち']:,}円 跳ぶ**")
    print(f"  → 青色控除後の所得が {KISO_JUMIN:,}円 以下だと、"
          f"**国保の所得割の元になる旧ただし書き所得が0**になります。"
          f"所得税は基礎控除 {KISO_SHOTOKU:,}円、住民税の所得割は基礎控除 {KISO_JUMIN:,}円 で"
          f"どちらも0、事業税も事業主控除 {JIGYOZEI_KOJO:,}円 の下で0。"
          "**減らせるものが1つも残っていません。**")
    print(f"  → この帯では、経費1万円の正味の費用は {STEP:,}円 まるごとです。"
          "**「経費で落とせば安くなる」が、字義どおり成り立たない人がいます。**")

    print("\n=== 「国保が1円も減らない」は所得の上端と下端の両方で起きる。意味は正反対 ===")
    print(f"{'所得':>12}{'青色控除後':>12}{'旧ただし書き':>13}{'国保':>11}"
          f"{'頭打ち':>7}{'国保の減り':>11}{'値打ち':>9}  理由")
    for r in kokuho_zero_rows():
        print(f"{r['所得（青色控除前）']:>11,}円{r['青色控除後の所得']:>11,}円"
              f"{r['旧ただし書き所得']:>12,}円{r['国民健康保険料']:>10,}円"
              f"{str(r['頭打ちの区分']) + '/' + str(r['区分の数']):>7}"
              f"{r['国保の減り']:>10,}円{r['値打ち']:>8,}円  {r['理由']}")
    print(f"  → 上端が始まるのは 所得 {ze['上端が始まる所得']:,}円。"
          f"その1円下では国保はまだ {ze['上端の1円下の国保の減り']:,}円 減ります。")
    print(f"  → **同じ「0」でも、下端の値打ちは {ze['下端の値打ち']:,}円、"
          f"上端は {ze['上端の値打ち']:,}円** です。"
          "上端では所得税・住民税・事業税がそのぶん動くので、値打ちは残ります。")
    print(f"  → **`member_limit()` の『動かなくなる人数』は、この2つを区別しません。**"
          f"所得 {ZERO_PROFITS[0]:,}円 でも『1人目から動かない』と出ますが、"
          "**限度額に当たっているのではなく、そもそも所得割がかかっていない**からです。")

    mc = member_cost()
    mr = member_cost_rate()
    print(f"\n=== 家族が1人ふえて国保が {mr['止まるまでの国保のふえた額']:,}円 上がっても、"
          f"正味は {mr['止まるまでの正味']:,}円（3割が税で戻る）===")
    print(f"  前提: 事業所得（青色控除前）{mr['所得（青色控除前）']:,}円／"
          f"{AGE_KAIGO}歳・国保 ／ 青色申告特別控除 {AOIRO_ETAX:,}円 ／"
          "**動かしているのは被保険者数だけです**")
    print("  国民健康保険料は**全額が社会保険料控除**なので、"
          "**上がった額だけ課税所得が下がります。**"
          "「扶養がふえると国保が上がる」の額は、そのまま出ていく額ではありません。")
    print(f"{'人数':>5}{'国民健康保険料':>15}{'1人のときから':>14}"
          f"{'所得税と住民税の減り':>21}{'正味のふえた額':>15}{'戻る割合':>10}")
    for r in mc:
        print(f"{r['被保険者数']:>4}人{r['国民健康保険料']:>14,}円"
              f"{r['国保のふえた額']:>13,}円{r['所得税と住民税の減り']:>20,}円"
              f"{r['正味のふえた額']:>14,}円{r['戻る割合'] * 100:>9.2f}%")
    print(f"  → **戻る割合は人数によらず {mr['いちばん低い割合'] * 100:.2f}〜"
          f"{mr['いちばん高い割合'] * 100:.2f}パーセント**で、"
          f"幅は {mr['幅'] * 100:.2f}ポイントしかありません。"
          "所得税の限界税率 ＋ 住民税の所得割 —— **その人の帯が変わらない限り一定**です。")
    print(f"  → {mr['止まる人数']}人目から先は1円も動きません"
          f"（4区分とも賦課限度額 合計 {kokuho.LIMIT_TOTAL:,}円 に当たっている）。"
          "**8人でも20人でも、保険料も税も同じ額です。**")

    rp = keihi_ramp()
    print(f"\n=== 「経費」と「青色控除の上乗せ」の差 {rp['満額の差']:,}円 は、"
          f"{rp['差が0で終わる所得']:,}円 から {rp['満額になる所得']:,}円 までの坂 ===")
    print(f"  前提: 事業所得（青色控除前）／単身・{AGE_KAIGO}歳・国保 ／"
          f"簡易簿記 {AOIRO_KANI:,}円 → 複式簿記 {AOIRO_FUKUSHIKI:,}円"
          f"（控除が {rp['額']:,}円 ふえる）と、同じ額を経費で落とした場合")
    print("  既にある表は「入口の下では0、上では満額、またぐ所得だけ中間」と言っています。"
          "**その『またぐ所得』が、どこからどこまでかを1円きざみで出します。**")
    print(f"{'所得':>12}{'入口からの距離':>16}{'差':>10}{'満額まで':>11}")
    for r in keihi_ramp_rows():
        print(f"{r['所得（青色控除前）']:>11,}円{r['入口からの距離']:>15,}円"
              f"{r['差']:>9,}円{r['満額まで']:>10,}円")
    print(f"  → 坂の幅は {rp['坂の幅']:,}円 で、"
          f"**控除の額 {rp['額']:,}円 とぴったり同じ**です。"
          f"事業税は「青色控除前の所得 − 事業主控除 {JIGYOZEI_KOJO:,}円」に率を掛けるので、"
          "**経費で落とした側だけが事業主控除の中へ食い込んでいく**からです。")
    print(f"  → 坂の上では、所得が1万円ふえるごとに差が {rp['1万円あたり']:,}円 ずつ広がります"
          f"（{JIGYOZEI_RATE * 100:.0f}パーセント）。"
          f"**{rp['満額になる所得']:,}円 の1円下でも {rp['1円下の差']:,}円 で、まだ満額ではありません**"
          "（事業税は100円未満を切り捨てるので、表の値は階段状になります）。")

    cl = ceiling()
    print(f"\n=== 経費1万円の値打ちには天井がある —— {cl['値打ち']:,}円。"
          f"所得 {cl['入る所得']:,}円 から上は、10億円でも同じ額 ===")
    print(f"  前提: 事業所得（青色控除前）／単身・{AGE_KAIGO}歳・国保 ／"
          f"青色申告特別控除 {AOIRO_ETAX:,}円 ／ 経費 {STEP:,}円")
    print("  国保が4区分とも賦課限度額に当たったあと、経費1万円で減るのは"
          "**所得税・住民税・事業税だけ**になります。"
          "住民税の所得割と事業税の率は所得で動かないので、"
          "**残るのは所得税の速算表の段だけ** —— だから値打ちは階段になり、"
          "**最高税率に入ったところで止まります。**")
    print(f"{'その段に入る所得':>18}{'速算表':>8}{'値打ち':>10}{'実効率':>9}"
          f"{'国保の減り':>11}{'住民税の減り':>13}{'事業税の減り':>13}")
    for r in ceiling_steps():
        print(f"{r['入る所得']:>17,}円{str(r['速算表の税率']) + '%':>8}"
              f"{r['値打ち']:>9,}円{r['実効率'] * 100:>8.2f}%"
              f"{r['国保の減り']:>10,}円{r['住民税の減り']:>12,}円"
              f"{r['事業税の減り']:>12,}円")
    print(f"  → 段は {cl['段の数']}つ で、天井は速算表 {cl['速算表の税率']}パーセントの"
          f"{cl['値打ち']:,}円（{cl['実効率'] * 100:.2f}パーセント）。"
          f"**正味の費用は {cl['正味の費用']:,}円** です。")
    print(f"  → 天井の内訳は「所得税 {cl['速算表の税率']}パーセント × 復興特別所得税"
          f"{(1 + FUKKO_RATE):.3f} ＋ 住民税 {JUMIN_RATE * 100:.0f}パーセント ＋ "
          f"事業税 {JIGYOZEI_RATE * 100:.0f}パーセント」で、"
          "**国保がまったく効いていません。**"
          "「経費は税率ぶんだけ得」が当たるのは、**この帯だけ**です"
          "（それでも速算表より15ポイント高い）。")
    print("  → **所得が上がるほど値打ちが上がる、はここでも成り立ちません** ——"
          "上の段へ移るには年 900万円 から 2,200万円 の所得が要るのに、"
          "**値打ちは1万円につき数百円しか動きません。**")

    print("\n=== 同じ1万円でも、経費なら3,155円・「全額所得控除」なら1,511円しか戻らない ===")
    print(f"{'所得（青色控除前）':>18}{'経費にしたら':>14}{'全額所得控除なら':>18}"
          f"{'差':>9}{'倍率':>8}")
    for r in kojo_vs_keihi_rows():
        bai = f"{r['倍率']:.2f}倍" if r["倍率"] else "——"
        print(f"{r['所得（青色控除前）']:>17,}円{r['経費にしたときの値打ち']:>13,}円"
              f"{r['全額所得控除にしたときの値打ち']:>17,}円{r['差']:>8,}円{bai:>10}")
    print("  → 国民健康保険料の算定は「総所得金額等 − 基礎控除43万円」で、"
          "**所得控除は1円も引けません。** 個人事業税も事業所得から事業主控除"
          "290万円を引くだけです。**だから所得控除は、所得税と住民税の2本しか動かしません。**")
    print("  → 経費のほうは同じ2本に加えて国保と事業税も下がるので、"
          "**同じ1万円でも戻る額が違います。** 事業所得300万円なら "
          f"{kojo_vs_keihi(3_000_000)['倍率']:.2f}倍 です。")
    print("  → **どちらが得かの話ではありません。** 経費は物やサービスが手元に残り、"
          "共済の掛金はあとで戻ってきます。ここで並べているのは"
          "**その年に戻る額だけ**です。")

    bands = kojo_dead_bands()
    dead = kojo_dead_edge()
    print(f"\n=== 「全額所得控除」が1円も戻らない所得は、1本の帯ではなく"
          f"{len(bands)}本ある（上端は事業所得{dead:,}円）===")
    for lo_, hi_ in bands:
        a, b = kojo_vs_keihi(lo_), kojo_vs_keihi(hi_)
        print(f"  事業所得 {lo_:>10,}円 〜 {hi_:>10,}円   "
              f"全額所得控除 0円  ／ 経費なら {a['経費にしたときの値打ち']:,}円 〜 "
              f"{b['経費にしたときの値打ち']:,}円 戻る")
    r_in, r_out = kojo_vs_keihi(dead), kojo_vs_keihi(dead + 1)
    print(f"  上端 {dead:>10,}円 → 全額所得控除 "
          f"{r_in['全額所得控除にしたときの値打ち']:,}円 ／ "
          f"その1円上 {dead + 1:,}円 → "
          f"{r_out['全額所得控除にしたときの値打ち']:,}円")
    print("  → 青色申告特別控除65万円と社会保険料控除を引いた時点で"
          "**課税所得がもう0**なので、所得控除をいくら積んでも税は1円も減りません。")
    print("  → **同じ帯で、経費のほうは戻ります。** 国保の所得割は課税所得ではなく"
          "「総所得金額等 − 基礎控除43万円」で決まるので、"
          "**課税所得が0でも国保は残っていて、経費はそこを削れる**からです。")
    if len(bands) >= 2:
        gap_lo, gap_hi = bands[0][1], bands[1][0]
        g0, g1 = kojo_vs_keihi(gap_lo + 1), kojo_vs_keihi(gap_hi)
        print(f"  → **帯が2本に割れているのは、国保の軽減が1段 外れるから**です。"
              f"谷は {gap_lo + 1:,}円 〜 {gap_hi - 1:,}円 で、そこでは所得控除も"
              f"少しだけ戻ります（{g0['全額所得控除にしたときの値打ち']:,}円 から）。")
        k0 = kokuho_premium(gap_hi - 1)
        k1 = kokuho_premium(gap_hi)
        print(f"     ところが 事業所得 {gap_hi - 1:,}円 → {gap_hi:,}円 で"
              f"国保が {k0:,}円 → {k1:,}円（**{k1 - k0:,}円 上がる**）。"
              "**保険料は全額が社会保険料控除**なので、"
              f"課税所得がそのぶん押し戻されて、値打ちは "
              f"{g1['全額所得控除にしたときの値打ち']:,}円 に落ちます。")
        print("     → **所得が増えたのに、所得控除の値打ちが下がる。**"
              "「所得が高いほど所得控除が効く」は、この段では成り立ちません。")
    for p0 in (1_089_994, 1_390_200):
        r0 = kojo_vs_keihi(p0)
        print(f"     事業所得 {p0:>9,}円 …… 経費 "
              f"{r0['経費にしたときの値打ち']:>6,}円 / 全額所得控除 "
              f"{r0['全額所得控除にしたときの値打ち']:,}円"
              "（国保の軽減の段に乗っている所得）")
    print("  → 小規模企業共済の案内が出す「節税額」は"
          "**所得税率と住民税10パーセントを足した額**です。"
          "**その率を掛ける相手（課税所得）が0の人**は、この帯にいます。")

    st = kojo_gap_settles()
    settle = st["差がここだけになる所得"]
    print(f"\n=== 経費と「全額所得控除」の差は、事業所得{settle:,}円から上では"
          f"事業税の{st['事業税ぶん']:,}円だけになる ===")
    for p in (3_000_000, 7_000_000, 9_000_000, settle, 12_000_000, 20_000_000):
        r = kojo_vs_keihi(p)
        mark = "  ← ここから上は事業税だけ" if p == settle else ""
        print(f"  事業所得 {p:>10,}円  経費 {r['経費にしたときの値打ち']:>6,}円  "
              f"全額所得控除 {r['全額所得控除にしたときの値打ち']:>6,}円  "
              f"差 {r['差']:>6,}円{mark}")
    print(f"  → 国民健康保険料が賦課限度額（{kokuho.LIMIT_TOTAL:,}円）に当たると、"
          "**経費を1万円ふやしても国保は1円も減りません。** "
          "そこから上で経費に残っている取り柄は、**事業税だけ**です。")
    print(f"  → その差は 1万円 × 事業税{JIGYOZEI_RATE * 100:.0f}パーセント ＝ "
          f"{st['事業税ぶん']:,}円 で、**所得がいくら上がっても動きません。**")
    print("  → **差がいちばん大きいのは、上ではなく下です** —— "
          f"事業所得300万円の {kojo_vs_keihi(3_000_000)['差']:,}円 に対し、"
          f"2,000万円では {kojo_vs_keihi(20_000_000)['差']:,}円。"
          "**「高所得者ほど所得控除が効く」は、経費と並べると逆向きになります。**")
