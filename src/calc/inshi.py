"""印紙税の階段 —— **記載金額が1円ちがうだけで、印紙代が5倍になる点があります。**

一般の解説はここで止まります ——「不動産の売買契約書なら、1,000万円超5,000万円以下は
2万円、軽減後は1万円です」。**税額表を写すところで終わります。**

この計算が出すのは、その表を割ったり並べ替えたりして初めて出る数字です。

## 跳ぶ額の1位は2つあって、まったくの同額です

記載金額が帯の境目を1円こえると、印紙代が跳びます（第1号文書・本則）。

    境目          手前 → 1円こえた額     跳ぶ額      倍率
      500万円     2,000 → 10,000円      8,000円   **5.00倍**  ← 倍率の1位
    5,000万円    20,000 → 60,000円     40,000円     3.00倍
      5億円      60,000 → 100,000円    40,000円     1.67倍
     10億円     200,000 → 400,000円  **200,000円**  2.00倍  ← 額の1位
     50億円     400,000 → 600,000円  **200,000円**  1.50倍  ← 額の1位

**跳ぶ額でいちばん大きい境目は10億円と50億円の2つで、どちらも200,000円**です。
**どちらか一方を「いちばん大きい崖」と呼ぶと嘘になります。**
そして**倍率で聞くと答えが変わり、500万円が単独の1位**（5.00倍）になります。
その500万円の跳ぶ額は8,000円で、額の順では上から7番目です。

## 記載金額に対する割合は、のこぎりの形をしています

印紙代を記載金額で割ると、帯の入口でいちばん高く、出口でいちばん安くなります。

    帯の入口     1万円ちょうど     **2.0000%**   ← 全体の最大
                10万円と1円         0.4000%
               100万円と1円         0.2000%
    帯の出口   5,000万円            0.0400%
                50億円            **0.0080%**   ← 全体の最小

**最大と最小の比はちょうど250.0倍**です（2.0000 ÷ 0.0080）。
非課税をまたいだ1万円ちょうどの契約書は、200円で **2.00パーセント** ——
印紙税でいちばん重い金額は、いちばん小さい契約書です。

**そして「金額が大きいほど率は下がる」は成り立ちません。** 出口どうしを並べると
3か所で逆転します。

     500万円ちょうど  2,000円   0.0400%
    1,000万円ちょうど 10,000円  0.1000%   ← **2.50倍に上がる**

**倍の金額の契約書が、2.5倍の率を払います。**（ほかに 50万→100万 が1.25倍、
5,000万→1億 が1.50倍）

## 軽減措置は「一律半額」ではありません。金額が大きい帯ほど効きません

租税特別措置法91条の軽減を、本則と帯ごとに突き合わせると、減り方は4種類あります。

    減る割合    段数    帯
      50%      6段    10万円超 〜 1億円以下
      40%      1段    1億円超5億円以下
      20%      3段    5億円超 〜 50億円超
       0%      1段    10万円以下（**軽減の対象外**）

**率で見ると金額が大きいほど効かず、額で見ると増え続けます**（200円 → 120,000円）。
そして**5億円の帯と10億円の帯は、減る額が同じ40,000円**です
（100,000→60,000 と 200,000→160,000）。ここでも額と率で答えが違います。

**軽減は、崖を1つ消してもいます。** 本則では10万円ちょうどで 200円 → 400円
（2.00倍）の崖がありますが、軽減後は10万円超が200円なので、**この崖だけが平ら**に
なります。軽減が対象外にしている10万円以下と、軽減後の額が、たまたま同じ200円だからです。

## 同じ金額の契約でも、売買か請負かで5倍ちがいます

第1号文書（不動産の譲渡）と第2号文書（請負）は、別の階段です。

    記載金額     第1号（譲渡）   第2号（請負）    倍率
      80万円      1,000円        200円      **5.00倍**
     150万円      2,000円        400円      **5.00倍**
     250万円      2,000円      1,000円        2.00倍
     400万円      2,000円      2,000円        1.00倍

**5倍になるのは2か所（50万円超100万円以下と、100万円超200万円以下）**です。
そして**300万円を超えると、2つの表は1円も違いません** ——
違いがあるのは300万円以下の範囲だけで、そこから上はまったく同じ階段です。

## 消費税を分けて書くと印紙代が変わる金額は、境目のすぐ上にしかありません

消費税額が区分して記載されていれば、階段は税抜きの金額で判定されます。
だから**効くのは、税込みが境目をこえていて、税抜きなら下の帯に入る金額だけ**です。
領収書（第17号の1文書）で境目ごとに幅を出すと、こうなります。

    境目          効く税込の帯           幅          浮く額   幅1円あたり
      5万円     50,000〜54,999円     **5,000円**    200円   **0.0400**
    100万円   1,000,001〜1,100,001円  100,001円    200円     0.0020
    500万円   5,000,001〜5,500,001円  500,001円  1,000円     0.0020

**5万円の境目だけが、2位の20.0倍の濃さ**です。5万円未満は非課税なので、
浮くのは200円ではなく**200円と0円の差そのもの**で、しかも幅が5,000円しかありません。
**税込み50,000円から54,999円の領収書は、書き方だけで印紙が要らなくなります。**

## 契約を2通に分けると、安くなる金額と、逆に高くなる金額があります

階段なので、総額を割って2通にすると税額の合計は上にも下にも動きます。
帯の出口ちょうどの10点で見ると、**高くなるのが6点、安くなるのが3点、
変わらないのが1点**でした。

      500万円   1通 2,000円 → 2通 4,000円   **2.00倍に増える**
    1,000万円   1通10,000円 → 2通 4,000円   6,000円安くなる
    2,000万円   1通20,000円 → **4通 8,000円**（最安）  12,000円安くなる

**「分ければ安い」は成り立ちません。** 帯の出口ちょうどでは、分けたほうが高くなる
ほうが多数です。2,000万円のように**2通ではなく4通がいちばん安い**金額もあります
（2通は20,000円で1通と同額、4通で8,000円）。
ここで出しているのは階段の形であって、**取引そのものが分かれていない契約を
書面の上だけで分けることはできません。**
"""
from __future__ import annotations

from fractions import Fraction

from . import _checks

# ---- 制度の値（印紙税法別表第一・租税特別措置法91条）---------------------
# 帯は (その帯の上限（円・**以下**）, 税額)。上限 None は最上段。
# 「1万円未満は非課税」は先頭の (9_999, 0) が持ちます。

# 第1号文書（不動産の譲渡に関する契約書など）の本則税額。
DAI1_HONSOKU: list[tuple[int | None, int]] = [
    (9_999, 0),
    (100_000, 200),
    (500_000, 400),
    (1_000_000, 1_000),
    (5_000_000, 2_000),
    (10_000_000, 10_000),
    (50_000_000, 20_000),
    (100_000_000, 60_000),
    (500_000_000, 100_000),
    (1_000_000_000, 200_000),
    (5_000_000_000, 400_000),
    (None, 600_000),
]

# 同じ第1号文書の軽減後（措置法91条。記載金額10万円超のものが対象）。
DAI1_KEIGEN: list[tuple[int | None, int]] = [
    (9_999, 0),
    (100_000, 200),          # 10万円以下は軽減の対象外。本則のまま
    (500_000, 200),
    (1_000_000, 500),
    (5_000_000, 1_000),
    (10_000_000, 5_000),
    (50_000_000, 10_000),
    (100_000_000, 30_000),
    (500_000_000, 60_000),
    (1_000_000_000, 160_000),
    (5_000_000_000, 320_000),
    (None, 480_000),
]

# 第2号文書（請負に関する契約書）の本則税額。
DAI2_HONSOKU: list[tuple[int | None, int]] = [
    (9_999, 0),
    (1_000_000, 200),
    (2_000_000, 400),
    (3_000_000, 1_000),
    (5_000_000, 2_000),
    (10_000_000, 10_000),
    (50_000_000, 20_000),
    (100_000_000, 60_000),
    (500_000_000, 100_000),
    (1_000_000_000, 200_000),
    (5_000_000_000, 400_000),
    (None, 600_000),
]

# 建設工事の請負契約書の軽減後（措置法91条。記載金額100万円超のものが対象）。
DAI2_KEIGEN: list[tuple[int | None, int]] = [
    (9_999, 0),
    (1_000_000, 200),        # 100万円以下は軽減の対象外
    (2_000_000, 200),
    (3_000_000, 500),
    (5_000_000, 1_000),
    (10_000_000, 5_000),
    (50_000_000, 10_000),
    (100_000_000, 30_000),
    (500_000_000, 60_000),
    (1_000_000_000, 160_000),
    (5_000_000_000, 320_000),
    (None, 480_000),
]

# 第17号の1文書（売上代金の受取書＝領収書）。5万円未満は非課税。
DAI17: list[tuple[int | None, int]] = [
    (49_999, 0),
    (1_000_000, 200),
    (2_000_000, 400),
    (3_000_000, 600),
    (5_000_000, 1_000),
    (10_000_000, 2_000),
    (20_000_000, 4_000),
    (30_000_000, 6_000),
    (50_000_000, 10_000),
    (100_000_000, 20_000),
    (200_000_000, 40_000),
    (300_000_000, 60_000),
    (500_000_000, 100_000),
    (1_000_000_000, 150_000),
    (None, 200_000),
]

TABLES: dict[str, list[tuple[int | None, int]]] = {
    "1号本則": DAI1_HONSOKU,
    "1号軽減": DAI1_KEIGEN,
    "2号本則": DAI2_HONSOKU,
    "2号軽減": DAI2_KEIGEN,
    "17号": DAI17,
}

# 非課税の下限（別表第一の非課税物件の欄）。
HIKAZEI_KEIYAKU = 10_000      # 第1号・第2号は記載金額1万円未満が非課税
HIKAZEI_RYOSHU = 50_000       # 第17号は受取金額5万円未満が非課税（平成26年4月1日以降）

# 消費税率（区分記載の節で使う）。制度の値です。
SHOHIZEI = Fraction(10, 100)

ASSUMPTIONS = [
    "契約書や領収書に貼る印紙税を計算しています。"
    "税額は文書の種類と、そこに書かれた記載金額だけで決まります",
    "不動産の譲渡に関する契約書（第1号文書）は、記載金額1万円未満が非課税、"
    "10万円以下が200円、10万円超50万円以下が400円、50万円超100万円以下が1,000円、"
    "100万円超500万円以下が2,000円、500万円超1,000万円以下が1万円、"
    "1,000万円超5,000万円以下が2万円、5,000万円超1億円以下が6万円、"
    "1億円超5億円以下が10万円、5億円超10億円以下が20万円、"
    "10億円超50億円以下が40万円、50億円超が60万円として計算しています",
    "軽減措置は租税特別措置法91条のものです。"
    "不動産の譲渡に関する契約書は記載金額10万円超、"
    "建設工事の請負契約書は記載金額100万円超のものが対象で、"
    "10万円以下や100万円以下の文書には適用されません",
    "請負に関する契約書（第2号文書）は、記載金額100万円以下が200円、"
    "100万円超200万円以下が400円、200万円超300万円以下が1,000円、"
    "300万円超500万円以下が2,000円で、500万円を超えると第1号文書と同じ額です",
    "売上代金の受取書（第17号の1文書）は、受取金額5万円未満が非課税、"
    "100万円以下が200円、100万円超200万円以下が400円、200万円超300万円以下が600円、"
    "300万円超500万円以下が1,000円、500万円超1,000万円以下が2,000円として計算しています",
    "消費税率は10パーセントとして置いています。軽減税率8パーセントの取引は"
    "この計算に入れていません",
    "消費税額が区分して記載されている文書は、税抜きの金額で階段を判定するものとして"
    "計算しています。区分記載がなければ税込みの金額で判定されます",
    "電子契約に印紙税がかからないのは、印紙税が紙の文書に課税される税だからです。"
    "電子データで作った契約書には印紙を貼りません。"
    "この計算では、電子にすると印紙代がそのまま0円になるものとして置いています",
    "契約を複数の文書に分けたときの税額も計算していますが、"
    "分けられるのは取引そのものが分かれている場合だけです。"
    "1つの取引を書面の上だけで分けることはできません",
    "1つの契約書を当事者がそれぞれ1通ずつ持つときは、2通とも課税されます。"
    "この計算では通数を1通として、1通あたりの額を出しています",
    "地方税や登録免許税、司法書士の報酬は入れていません。印紙税だけを見ています",
]


# ---- 表を引く -----------------------------------------------------------
def stamp(amount: int, kind: str = "1号本則") -> int:
    """記載金額から印紙税額を引く。**帯は「〜以下」で読みます。**"""
    table = TABLES[kind]
    for cap, tax in table:
        if cap is None or amount <= cap:
            return tax
    raise ValueError(f"表に当たりません: {amount}")


def edges(kind: str) -> list[int]:
    """税額が変わる金額（＝帯の入口。「〜超」の側）を並べる。"""
    table = TABLES[kind]
    out = []
    for cap, _ in table[:-1]:
        assert cap is not None
        out.append(cap + 1)
    return out


# ---- 節1: 1円またぐ崖 ---------------------------------------------------
def cliffs(kind: str = "1号本則") -> list[dict]:
    """帯の境目ごとの跳び。**額の1位と倍率の1位は別の金額です。**"""
    table = TABLES[kind]
    rows = []
    for i in range(1, len(table)):
        before = table[i - 1][1]
        after = table[i][1]
        edge = table[i - 1][0]
        assert edge is not None
        rows.append({
            "境目の金額": edge,
            "手前の印紙代": before,
            "1円こえた印紙代": after,
            "跳ぶ額": after - before,
            "倍率": (Fraction(after, before) if before else None),
        })
    return rows


def top_cliffs(kind: str = "1号本則") -> dict:
    """跳ぶ額の1位と、倍率の1位を名指しする（同額なら全部返す）。"""
    rows = [r for r in cliffs(kind) if r["倍率"] is not None]
    max_yen = max(r["跳ぶ額"] for r in rows)
    max_ratio = max(r["倍率"] for r in rows)
    return {
        "額の1位": [r["境目の金額"] for r in rows if r["跳ぶ額"] == max_yen],
        "額の1位の跳び": max_yen,
        "倍率の1位": [r["境目の金額"] for r in rows if r["倍率"] == max_ratio],
        "倍率の1位の倍率": max_ratio,
    }


# ---- 節2: 実効率ののこぎり ----------------------------------------------
def rate_grid(kind: str = "1号本則") -> list[dict]:
    """帯の入口と出口で、記載金額に対する印紙代の割合を出す。"""
    table = TABLES[kind]
    rows = []
    for i, (cap, tax) in enumerate(table):
        if tax == 0:
            continue
        low = (table[i - 1][0] or 0) + 1
        rows.append({
            "帯の入口": low,
            "帯の出口": cap,
            "印紙代": tax,
            "入口の割合": Fraction(tax, low),
            "出口の割合": (Fraction(tax, cap) if cap is not None else None),
        })
    return rows


def rate_extremes(kind: str = "1号本則") -> dict:
    """割合の最大と最小（**上限のない最上段は出口を持たないので除きます**）。"""
    rows = rate_grid(kind)
    ins = [(r["入口の割合"], r["帯の入口"]) for r in rows]
    outs = [(r["出口の割合"], r["帯の出口"]) for r in rows
            if r["出口の割合"] is not None]
    hi = max(ins)
    lo = min(outs)
    return {
        "最大の割合": hi[0], "最大の金額": hi[1],
        "最小の割合": lo[0], "最小の金額": lo[1],
        "最大÷最小": hi[0] / lo[0],
    }


def non_monotone_exits(kind: str = "1号本則") -> list[dict]:
    """**金額が大きいほうが割合も大きい**という、順番が逆になる出口の組。"""
    rows = [r for r in rate_grid(kind) if r["出口の割合"] is not None]
    out = []
    for i in range(1, len(rows)):
        if rows[i]["出口の割合"] > rows[i - 1]["出口の割合"]:
            out.append({
                "小さい金額": rows[i - 1]["帯の出口"],
                "小さい側の割合": rows[i - 1]["出口の割合"],
                "大きい金額": rows[i]["帯の出口"],
                "大きい側の割合": rows[i]["出口の割合"],
                "割合の倍率": rows[i]["出口の割合"] / rows[i - 1]["出口の割合"],
            })
    return out


# ---- 節3: 軽減措置 ------------------------------------------------------
def keigen_grid(honsoku: str = "1号本則", keigen: str = "1号軽減") -> list[dict]:
    """帯ごとに、軽減で減る額と減る割合を並べる。**一律半額ではありません。**"""
    rows = []
    for (cap, tax), (cap2, tax2) in zip(TABLES[honsoku], TABLES[keigen]):
        assert cap == cap2
        if tax == 0:
            continue
        rows.append({
            "帯の出口": cap,
            "本則": tax,
            "軽減後": tax2,
            "減る額": tax - tax2,
            "減る割合": Fraction(tax - tax2, tax),
        })
    return rows


def keigen_shapes(honsoku: str = "1号本則", keigen: str = "1号軽減") -> dict:
    """減る割合を種類べつに数え、額の1位も出す。"""
    rows = keigen_grid(honsoku, keigen)
    counts: dict[Fraction, int] = {}
    for r in rows:
        counts[r["減る割合"]] = counts.get(r["減る割合"], 0) + 1
    max_yen = max(r["減る額"] for r in rows)
    return {
        "割合べつの段数": dict(sorted(counts.items())),
        "額の1位": [(r["帯の出口"] if r["帯の出口"] is not None else "50億円超")
                  for r in rows if r["減る額"] == max_yen],
        "額の1位の減る額": max_yen,
        "同額で並ぶ帯": [r["帯の出口"] for r in rows
                    if [x["減る額"] for x in rows].count(r["減る額"]) > 1],
    }


def killed_cliffs(honsoku: str = "1号本則", keigen: str = "1号軽減") -> list[dict]:
    """本則では崖なのに、軽減後は平らになる境目。"""
    out = []
    for a, b in zip(cliffs(honsoku), cliffs(keigen)):
        assert a["境目の金額"] == b["境目の金額"]
        if a["跳ぶ額"] > 0 and b["跳ぶ額"] == 0:
            out.append({
                "境目の金額": a["境目の金額"],
                "本則の跳び": a["跳ぶ額"],
                "本則の倍率": a["倍率"],
                "軽減後の跳び": b["跳ぶ額"],
            })
    return out


# ---- 節4: 売買と請負 ----------------------------------------------------
def kind_grid(amounts: list[int] | None = None) -> list[dict]:
    """同じ記載金額で、第1号（譲渡）と第2号（請負）を並べる。"""
    if amounts is None:
        amounts = [100_000, 300_000, 800_000, 1_500_000, 2_500_000,
                   4_000_000, 5_000_000, 8_000_000, 30_000_000]
    rows = []
    for a in amounts:
        one = stamp(a, "1号本則")
        two = stamp(a, "2号本則")
        rows.append({
            "記載金額": a,
            "第1号（譲渡）": one,
            "第2号（請負）": two,
            "差": one - two,
            "倍率": (Fraction(one, two) if two else None),
        })
    return rows


def kind_gap_top() -> dict:
    """第1号と第2号の倍率がいちばん大きい帯と、差が消える金額。"""
    rows = []
    for edge in sorted(set(edges("1号本則")) | set(edges("2号本則"))):
        one, two = stamp(edge, "1号本則"), stamp(edge, "2号本則")
        if two:
            rows.append((Fraction(one, two), edge))
    top = max(r[0] for r in rows)
    same_from = min(e for r, e in rows if r == 1
                    and all(stamp(x, "1号本則") == stamp(x, "2号本則")
                            for x in [e, e * 2, e * 10, e * 100]))
    return {
        "倍率の1位": top,
        "倍率の1位の金額": [e for r, e in rows if r == top],
        "以後ずっと同額になる金額": same_from,
    }


# ---- 節5: 消費税の区分記載 ----------------------------------------------
def zeinuki_limit(edge: int) -> int:
    """税込でいくらまでなら、区分記載で1つ下の帯に落ちるか。

    **税抜き ＝ 税込 ÷ 1.1 の切り捨て**で判定します。

    ## **1円ずつ数え上げないこと**（2026-08-18 に踏んだ）

    ここは最初 `while` で1円ずつ上げていました。**答えは合っていましたが、
    第17号の10億円の境目で約1億回まわり**、`tests/test_topic_stock.py`
    （節を数えるので、この関数を実際に呼びます）が **9分を超えました。**
    掃引を抜いた検査ですら 900秒で終わらなくなっています。

    閉じた式で出ます。税抜きは `X × den ÷ num` の切り捨て（`num/den` ＝ 1＋税率）なので、

        税抜き < edge  ⟺  X × den < edge × num  ⟺  X ≤ (edge × num − 1) ÷ den

    **`_checks` は速さを見ません。** 見ているのは値だけなので、
    **この種の遅さは検査を全部通ったうえで残ります。**
    """
    step = 1 + SHOHIZEI
    num, den = step.numerator, step.denominator
    return (edge * num - 1) // den


def zeinuki_grid(kind: str = "17号") -> list[dict]:
    """境目ごとに、区分記載が効く税込の帯と、そこで浮く額を出す。"""
    table = TABLES[kind]
    rows = []
    for i in range(1, len(table)):
        edge_cap = table[i - 1][0]
        assert edge_cap is not None
        edge = edge_cap + 1
        top = zeinuki_limit(edge)
        saved = table[i][1] - table[i - 1][1]
        width = top - edge + 1
        rows.append({
            "境目の金額": edge,
            "効く税込の上限": top,
            "帯の幅": width,
            "浮く額": saved,
            "幅1円あたり": Fraction(saved, width),
        })
    return rows


def zeinuki_top(kind: str = "17号") -> dict:
    """幅あたりでいちばん効く境目を名指しする。"""
    rows = zeinuki_grid(kind)
    best = max(rows, key=lambda r: r["幅1円あたり"])
    second = max((r for r in rows if r is not best),
                 key=lambda r: r["幅1円あたり"])
    return {
        "1位の境目": best["境目の金額"],
        "1位の帯": (best["境目の金額"], best["効く税込の上限"]),
        "1位の幅": best["帯の幅"],
        "1位の浮く額": best["浮く額"],
        "2位との比": best["幅1円あたり"] / second["幅1円あたり"],
    }


# ---- 節6: 1通にまとめるか、分けるか -------------------------------------
def split_cost(total: int, n: int, kind: str = "1号本則") -> int:
    """総額を n 通に均等に分けたときの、印紙代の合計。"""
    each = total // n
    rest = total - each * (n - 1)
    return stamp(rest, kind) + stamp(each, kind) * (n - 1)


def best_split(total: int, kind: str = "1号本則", n_max: int = 12) -> dict:
    """1通のときと、分けたときのいちばん安い組み合わせを比べる。"""
    one = stamp(total, kind)
    costs = [(split_cost(total, n, kind), n) for n in range(1, n_max + 1)]
    low, n = min(costs)
    return {
        "総額": total,
        "1通の印紙代": one,
        "いちばん安い通数": n,
        "そのときの印紙代": low,
        "差": one - low,
        "2通にしたとき": split_cost(total, 2, kind),
        "2通で高くなるか": split_cost(total, 2, kind) > one,
    }


def split_grid(kind: str = "1号本則") -> list[dict]:
    """代表的な総額で、まとめるのと分けるのを比べる。"""
    amounts = [1_000_000, 3_000_000, 5_000_000, 6_000_000,
               10_000_000, 20_000_000, 50_000_000, 100_000_000]
    return [best_split(a, kind) for a in amounts]


def split_turning_points(kind: str = "1号本則") -> list[dict]:
    """**2通に分けると高くなる金額**を、帯の出口の側から拾う。"""
    out = []
    for cap, _ in TABLES[kind][:-1]:
        assert cap is not None
        if cap < HIKAZEI_KEIYAKU:
            continue
        two = split_cost(cap, 2, kind)
        one = stamp(cap, kind)
        out.append({
            "金額": cap,
            "1通": one,
            "2通": two,
            "分けると": ("高くなる" if two > one
                       else "安くなる" if two < one else "変わらない"),
            "差": two - one,
        })
    return out


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""
    # 1. 法令が名指ししている値
    _checks.statutory(HIKAZEI_KEIYAKU, 10_000, "契約書の非課税の下限",
                      source="印紙税法別表第一 第1号・第2号 非課税物件")
    _checks.statutory(HIKAZEI_RYOSHU, 50_000, "受取書の非課税の下限",
                      source="印紙税法別表第一 第17号 非課税物件")
    _checks.statutory(float(SHOHIZEI), 0.10, "消費税率",
                      source="消費税法29条・地方税法72条の83")
    _checks.ratio(float(SHOHIZEI), "消費税率")
    _checks.statutory(stamp(50_000_000, "1号本則"), 20_000,
                      "5,000万円の譲渡契約書の本則",
                      source="印紙税法別表第一 第1号")
    _checks.statutory(stamp(50_000_001, "1号本則"), 60_000,
                      "5,000万円を1円こえた譲渡契約書の本則",
                      source="印紙税法別表第一 第1号")
    _checks.statutory(stamp(10_000_000, "1号軽減"), 5_000,
                      "1,000万円の譲渡契約書の軽減後",
                      source="租税特別措置法91条")
    _checks.statutory(stamp(1_000_000, "17号"), 200,
                      "100万円の領収書",
                      source="印紙税法別表第一 第17号の1")

    # 2. 表そのものの形（帯が昇順で、税額が下がらないこと）
    for name, table in TABLES.items():
        caps = [c for c, _ in table if c is not None]
        _checks.ascending(caps, f"{name} の帯の上限が昇順でない", strict=True)
        _checks.ascending([t for _, t in table], f"{name} の税額が途中で下がる")
        _checks.unique_by(table, lambda r: r[0], f"{name} の帯")
    _checks.statutory(stamp(HIKAZEI_KEIYAKU - 1, "1号本則"), 0,
                      "9,999円の契約書", source="印紙税法別表第一")
    _checks.statutory(stamp(HIKAZEI_RYOSHU - 1, "17号"), 0,
                      "49,999円の領収書", source="印紙税法別表第一")
    _checks.never_decreases(lambda a: stamp(a, "1号本則"),
                            [10_000, 500_000, 5_000_000, 100_000_000,
                             6_000_000_000],
                            "記載金額が増えたのに印紙代が減っている")

    # 3. 軽減は本則を上回らない。ただし一律半額でもない
    for h, k in (("1号本則", "1号軽減"), ("2号本則", "2号軽減")):
        for (_, a), (_, b) in zip(TABLES[h], TABLES[k]):
            if a < b:
                raise _checks.TableError(f"{k} が {h} を上回っています: {a} < {b}")
    shapes = keigen_shapes()
    if len(shapes["割合べつの段数"]) < 3:
        raise _checks.TableError(
            "軽減の減り方が1〜2種類しかありません。一律半額なら節になりません")

    # 4. この計算の主題そのもの
    # (a) 跳ぶ額の1位は2つあって同額。倍率の1位はそこではない
    top = top_cliffs("1号本則")
    if len(top["額の1位"]) != 2:
        raise _checks.TableError(
            f"跳ぶ額の1位が2つでない: {top['額の1位']}")
    _checks.statutory(top["額の1位の跳び"], 200_000, "跳ぶ額の1位",
                      source="印紙税法別表第一 第1号（この計算の結論）")
    _checks.close(float(top["倍率の1位の倍率"]), 5.0, "倍率の1位が5.00倍でない")
    if top["倍率の1位"] == top["額の1位"]:
        raise _checks.TableError("額の1位と倍率の1位が同じ金額になっています")
    # (b) 割合の最大は非課税のすぐ上、最小は上限のある最後の帯の出口
    ext = rate_extremes("1号本則")
    _checks.close(float(ext["最大の割合"]), 0.02, "割合の最大が2.00パーセントでない")
    _checks.statutory(ext["最大の金額"], HIKAZEI_KEIYAKU,
                      "割合が最大になる記載金額",
                      source="印紙税法別表第一（この計算の結論）")
    _checks.greater(float(ext["最大÷最小"]), 100.0,
                    "最大と最小の比が100倍を下回っています")
    # (c) 出口の割合は単調でない（大きい契約のほうが率が高い組がある）
    if not non_monotone_exits("1号本則"):
        raise _checks.TableError(
            "出口の割合が単調に下がっています。のこぎりの主題が消えます")
    # (d) 軽減は10万円の崖を1つ消している
    killed = killed_cliffs()
    if [k["境目の金額"] for k in killed] != [100_000]:
        raise _checks.TableError(f"軽減が消す崖が10万円だけでない: {killed}")
    # (e) 第1号と第2号は500万円を超えると完全に一致する
    gap = kind_gap_top()
    _checks.close(float(gap["倍率の1位"]), 5.0,
                  "譲渡と請負の倍率の1位が5.00倍でない")
    for a in (5_000_001, 9_000_000, 60_000_000, 700_000_000):
        _checks.close(float(stamp(a, "1号本則")), float(stamp(a, "2号本則")),
                      f"{a:,}円で譲渡と請負の額がちがう")
    _checks.greater(stamp(800_000, "1号本則"), stamp(800_000, "2号本則"),
                    "80万円では譲渡のほうが高いはず")
    # (f) 区分記載が効く帯は「境目のすぐ上」だけで、5万円がいちばん濃い
    z = zeinuki_top("17号")
    _checks.statutory(z["1位の境目"], HIKAZEI_RYOSHU,
                      "区分記載がいちばん効く境目",
                      source="印紙税法別表第一 第17号（この計算の結論）")
    _checks.statutory(z["1位の幅"], 5_000, "5万円の境目で効く税込の幅",
                      source="この計算の結論")
    _checks.greater(float(z["2位との比"]), 10.0,
                    "5万円の境目が2位の10倍を超えていません")
    # (g) 分けると安くなる金額と、高くなる金額の両方がある
    turns = split_turning_points("1号本則")
    if not any(t["分けると"] == "高くなる" for t in turns):
        raise _checks.TableError("分けると高くなる金額が1つもありません")
    if not any(t["分けると"] == "安くなる" for t in turns):
        raise _checks.TableError("分けると安くなる金額が1つもありません")
    _checks.greater(split_cost(5_000_000, 2, "1号本則"),
                    stamp(5_000_000, "1号本則"),
                    "500万円ちょうどは2通に分けると高くなるはず")
    _checks.greater(stamp(10_000_000, "1号本則"),
                    split_cost(10_000_000, 2, "1号本則"),
                    "1,000万円は2通に分けたほうが安いはず")

    _checks.assumption_values(ASSUMPTIONS, name="inshi")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 1円で跳ぶ額の1位は10億円と50億円の同額。倍率の1位はそこではない ===")
    for row in cliffs("1号本則"):
        print(row)
    print("1位:", top_cliffs("1号本則"))

    print("\n=== 記載金額に対する割合はのこぎり。最大は1万円ちょうどの2.00パーセント ===")
    for row in rate_grid("1号本則"):
        print(row)
    print("両端:", rate_extremes("1号本則"))
    print("大きいほうが率も高い組:", non_monotone_exits("1号本則"))

    print("\n=== 軽減措置は一律半額ではない。金額が大きい帯ほど効かない ===")
    for row in keigen_grid():
        print(row)
    print("形:", keigen_shapes())
    print("軽減が消した崖:", killed_cliffs())

    print("\n=== 同じ金額でも売買と請負で5倍。ただし300万円を超えると1円も違わない ===")
    for row in kind_grid():
        print(row)
    print("1位:", kind_gap_top())

    print("\n=== 消費税を分けて書くと印紙代が変わる金額は、境目のすぐ上の帯だけ ===")
    for row in zeinuki_grid("17号"):
        print(row)
    print("1位:", zeinuki_top("17号"))

    print("\n=== 契約を2通に分けると安くなる金額と、逆に高くなる金額がある ===")
    for row in split_grid("1号本則"):
        print(row)
    for row in split_turning_points("1号本則"):
        print(row)
