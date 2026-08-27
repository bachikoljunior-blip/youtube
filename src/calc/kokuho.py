"""国民健康保険料の賦課限度額。**「上限は113万円」の手前に、折れ目が3つあります。**

一般の解説は「国民健康保険料には上限があって、令和8年度は113万円」で止まります。
ところがその113万円は**4本の別々の上限を足しただけの数字**で、
**4本はそれぞれ独立に頭打ちになります。**

- 医療分（基礎賦課分） **67万円**
- 後期高齢者支援金分 **26万円**
- 介護納付金分 **17万円**（40〜64歳だけ）
- 子ども・子育て支援金分 **3万円**（令和8年度に新設）

4本は所得割の率が違うので、**頭打ちになる所得も別々**です。つまり
「所得が増えると保険料も増え、113万円で止まる」のではなく、
**途中で3回、増え方そのものが変わります。** そこから出てくる、公表されていない数字:

- **上限の小さい区分ほど早く止まる、ではありません。** 決めているのは上限額でも率でもなく
  **上限額 ÷ 率**です。だから**いちばん上限の小さい子ども・子育て支援金分（3万円）が、
  いちばん最後まで止まりません** —— 率も0.30パーセントと小さいからです。
  逆に**いちばん先に止まるのは介護納付金分**（上限17万円）で、
  **上限がいちばん大きい医療分（67万円）が2番目**。率が7.71パーセントと高いためです
- **所得が1万円増えたときに増える保険料は、階段状に減っていきます** ——
  1,295円 → 1,070円 → **299円** → 30円 → 0円。
  **医療分が止まるところで4分の1以下に落ちます**（率の大半をこの1本が持っているため）
- **「上限113万円に達した」と言えるのは、いちばん遅い1本が止まったとき**です。
  最初の1本が止まってからそこまで、**所得で約255万円ぶん開いています**
- **軽減の判定に、所得割は1円も入りません。** 軽減は**均等割にだけ**効きます。
  同じ所得でも、均等割の重い世帯ほど軽減の値打ちが大きい
- **7割軽減の基準額 43万円は、世帯人数が何人でも動きません。**
  5割は「43万円＋31万円×人数」、2割は「43万円＋57万円×人数」で人数とともに上がるのに、
  **7割だけが動かない。** だから**世帯が大きいほど、7割と5割の境目は離れます**
  （単身なら 43万→74万 の31万円ぶんですが、5人世帯では 43万→198万 の155万円ぶん）
- **2割軽減の境目を1円こえると、均等割が2割ぶん戻ってきます。**
  戻る額は**世帯人数に比例する** —— **ただし5人まで**です（2026-08-17 に測り直した）。
  2割の境目は「43万円＋57万円×人数」で上がるので、**大きい世帯はその所得で
  既に限度額に当たっています。** 6人で比例から折れ、**6人の9万2,570円が頂点**、
  7人はそれより低く、**10人では0円**（軽減があってもなくても113万円）
- **軽減の崖は1つではなく3つあり、いちばん高いのは真ん中です。**
  7割→5割 と 2割→なし は**同額**（均等割の20パーセント）で、
  **5割→2割 だけが30パーセント ＝ 1.50倍**。
  「軽減が完全に消えるところがいちばん痛い」は違います。
  崖の高さは所得にも保険料にもよらず、**均等割の合計 × 落ちるポイント**です
- **その崖の高さは、所得にも保険料にもよらないのに、年齢では変わります**
  （2026-08-18 に足した）。**均等割の合計そのものが動く**からです ——
  介護納付金分の均等割1万6,600円は40歳から64歳までしか乗らないので、
  **同じ所得・同じ世帯のまま、40歳の誕生日で崖が1万3,200円から1万6,520円へ上がり、
  65歳の誕生日でぴったり元に戻ります。** 上がる3,320円は介護分の均等割のちょうど2割。
  **22歳と75歳は、崖も保険料も1円も違いません。**
  そして**軽減の境目のほうは年齢で1円も動きません**（判定に入るのは所得と人数だけ）。
  つまり**同じ所得・同じ世帯で、「1円こえたときに失う額」だけが年齢で変わります**
- **40歳の誕生日で介護分が乗ります。** 39歳と40歳で、同じ所得・同じ世帯なのに
  保険料が変わる。**乗る額は所得によらず一定ではありません** ——
  介護分にも所得割があるので、所得とともに増え、17万円で止まります
- **世帯の所得を変えないまま被保険者が1人ふえて、保険料が下がる点があります**
  （2026-08-26 に足した）。均等割は1人ぶん増えるのに、です。
  軽減の判定基準が人数とともに上がるからで、**所得200万円・45歳なら5人から6人へ、
  頭数が1つふえて8万2,600円 安くなります。** 5人では均等割41万3,000円の2割
  （8万2,600円）しか消えていませんが、6人では49万5,600円の5割（24万7,800円）が
  消える。差し引き16万5,200円 多く消えて、ふえた均等割8万2,600円 を上回ります
- **その「折り返す人数」は、所得が上がるほど遠くなる、ではありません。**
  150万円で4人目、200万円で6人目、250万円で7人目、300万円で9人目と進んだあと、
  **350万円では6人目へ戻ります。** 軽減の境目が2本あり、5割は1人あたり31万円・
  2割は1人あたり57万円ずつと**上がる速さが違う**からです。所得が低いうちは
  5割の境目に先に当たり、350万円をこえると2割の境目のほうが先になる。
  落ちる先が変わるので、**下がる額も15万6,940円 から 1万6,520円 へ落ちます**
- **軽減は、額面どおりには受け取れません。** 額面は「均等割の合計 × 軽減の割合」
  ぴったりで所得は1円も入りませんが、**減らす前に限度額で切られていた区分は、
  減らしても切られたまま**です。いちばん極端なのは**被保険者9人の2割軽減**で、
  額面14万8,680円 のうち **14万6,707円 が限度額に吸われ、手元に残るのは1,973円**
  （額面の1.3パーセント）。この目減りは、軽減の判定にも割合にも書かれていません
- **保険料が1円も違わない、人数のちがう世帯があります**（2026-08-26 に足した）。
  軽減は「割合」で書いてあるので人数と掛け合わせられ、
  **実質の頭数 ＝ 被保険者数 × （1 − 軽減の割合）**になります。
  **所得割は被保険者数で1円も動かない**ので、保険料は
  **所得割 ＋ 均等割の単価 × 実質の頭数**の形になり、
  **実質の頭数が同じなら、人数が違っても保険料は同じ**です。
  所得350万円・45歳なら、**5人世帯と10人世帯がどちらも81万565円**
  （5×1.00 も 10×0.50 も 5.0）。**あいだの5人は保険料を1円も増やしていません。**
  並ぶ比は軽減の割合の比だけで決まる（無軽減:2割 = 1:1.25、2割:5割 = 1:1.6、
  無軽減:5割 = 1:2）ので、**組は (4人,5人) (5人,8人) (5人,10人) のような形に限られ**、
  どれが起きるかは所得が決めます
"""
from __future__ import annotations

import math

from . import _checks

# ---- 制度の値（**ここは政令で全国一律**）--------------------------------
# 賦課限度額（地方税法施行令56条の88の2ほか。令和8年度）。
# 令和7年度は 医療66・支援26・介護17 の合計109万円で、令和8年度に
# 医療が67万円へ上がり、**子ども・子育て支援金分3万円が新設**されて113万円
LIMIT_IRYO = 670_000          # 医療分（基礎賦課分）
LIMIT_SHIEN = 260_000         # 後期高齢者支援金分
LIMIT_KAIGO = 170_000         # 介護納付金分（40〜64歳だけ）
LIMIT_KODOMO = 30_000         # 子ども・子育て支援金分（令和8年度に新設）
LIMIT_TOTAL = LIMIT_IRYO + LIMIT_SHIEN + LIMIT_KAIGO + LIMIT_KODOMO   # 1,130,000円

# 軽減判定の基準額（地方税法703条の5・施行令ほか。令和8年度）。
# **7割の43万円だけ、被保険者数が入りません。**
KEIGEN_BASE = 430_000
KEIGEN_STEPS: list[tuple[int, int]] = [
    # (軽減の割合パーセント, 被保険者1人あたりの加算額)
    (7 * 10, 0),          # 7割軽減: 43万円以下。**人数によらない**
    (5 * 10, 310_000),    # 5割軽減: 43万円 ＋ 31万円 × 被保険者数
    (2 * 10, 570_000),    # 2割軽減: 43万円 ＋ 57万円 × 被保険者数
]

# 介護納付金分がかかる年齢（介護保険法9条2号。第2号被保険者）
KAIGO_FROM = 40
KAIGO_TO = 64

# ---- 率（**ここは市町村ごとに違います。例として置いています**）----------
# 令和7年度のある自治体の公表値。**この4行だけが全国一律ではありません。**
# だから下では「率によらない結論」と「率を置いたときの結論」を分けています。
RATES: dict[str, dict[str, float | int]] = {
    "医療分":            {"所得割": 0.0771, "均等割": 47_300, "限度額": LIMIT_IRYO},
    "後期高齢者支援金分": {"所得割": 0.0269, "均等割": 16_800, "限度額": LIMIT_SHIEN},
    "介護納付金分":      {"所得割": 0.0225, "均等割": 16_600, "限度額": LIMIT_KAIGO},
    "子ども子育て支援金分": {"所得割": 0.0030, "均等割": 1_900, "限度額": LIMIT_KODOMO},
}

# 国保の所得割は「総所得金額等 − 基礎控除43万円」に掛けます（旧ただし書き所得）
KISO_KOJO = 430_000

ASSUMPTIONS = [
    "令和8年度の国民健康保険料を計算しています。賦課限度額は医療分67万円、"
    "後期高齢者支援金分26万円、介護納付金分17万円、子ども・子育て支援金分3万円の"
    "合計113万円としています",
    "賦課限度額と軽減の判定基準額は政令で全国一律です。**所得割の率と均等割の額は"
    "市町村ごとに違います。**ここでは医療分の所得割7.71パーセント・均等割4万7,300円、"
    "後期高齢者支援金分の所得割2.69パーセント・均等割1万6,800円、"
    "介護納付金分の所得割2.25パーセント・均等割1万6,600円、"
    "子ども・子育て支援金分の所得割0.30パーセント・均等割1,900円を例として置いています。"
    "**お住まいの市町村の率に置き換えてください**",
    "所得割は、総所得金額等から基礎控除43万円を引いた額に掛けています。"
    "国民健康保険では、これを旧ただし書き所得と呼びます。"
    "所得税や住民税の所得控除は引きません",
    "軽減の判定基準額は、7割軽減が43万円、5割軽減が43万円に被保険者1人あたり31万円を"
    "足した額、2割軽減が43万円に被保険者1人あたり57万円を足した額としています",
    "軽減は均等割にだけかかります。所得割は軽減されません",
    "軽減の判定に入る給与所得者等の数による加算は入れていません。"
    "ここでは、その加算に当たらない世帯を見ています",
    "介護納付金分は40歳から64歳までの人にかかるものとしています。"
    "39歳以下と65歳以上にはかかりません",
    "平等割（1世帯あたりいくら、という部分）を採っている市町村がありますが、"
    "ここでは所得割と均等割の2本立てとしています",
    "世帯の所得は、世帯主1人だけが得ているものとしています。"
    "軽減の判定は世帯全員の所得の合計で行うので、ほかに所得のある人がいれば変わります",
]


# ---- 軽減 --------------------------------------------------------------
def keigen_threshold(rate_percent: int, members: int) -> int:
    """軽減が受けられる、世帯の所得の上限。

    **7割の基準額だけ、被保険者数が入りません**（加算が0円）。
    """
    for pct, per_head in KEIGEN_STEPS:
        if pct == rate_percent:
            return KEIGEN_BASE + per_head * members
    raise ValueError(f"知らない軽減の割合: {rate_percent}")


def keigen_rate(shotoku: int, members: int) -> int:
    """世帯の所得から、均等割の軽減の割合（パーセント）。**大きいほうから当てます。**"""
    for pct, _per_head in KEIGEN_STEPS:
        if shotoku <= keigen_threshold(pct, members):
            return pct
    return 0


def keigen_spread(members: int) -> dict:
    """**7割と5割の境目が、世帯人数でどれだけ離れるか。**

    7割は動かず、5割は人数とともに上がるので、**世帯が大きいほど開きます。**
    """
    seven = keigen_threshold(70, members)
    five = keigen_threshold(50, members)
    two = keigen_threshold(20, members)
    return {
        "被保険者数": members,
        "7割の境目": seven,
        "5割の境目": five,
        "2割の境目": two,
        "7割と5割の開き": five - seven,
        "5割と2割の開き": two - five,
        "7割と2割の開き": two - seven,
    }


# ---- 保険料 ------------------------------------------------------------
def kyu_tadashigaki(shotoku: int) -> int:
    """総所得金額等 → 旧ただし書き所得（所得割の土台）。"""
    return max(0, shotoku - KISO_KOJO)


def part(name: str, shotoku: int, members: int, *, keigen: bool = True,
         hantei: int | None = None) -> dict:
    """1本ぶんの保険料。**所得割と均等割を出してから、限度額で頭を切ります。**

    軽減は**均等割にだけ**掛かります（所得割は軽減されません）。

    `hantei` は**軽減の判定にだけ使う所得**です。既定の `None` は
    「総所得金額等をそのまま判定に使う」＝ **これまでと1円も変わりません。**

    **なぜ口を開けたか**（2026-08-28 に足した）。軽減の判定所得は総所得と
    同じではありません —— **65歳以上の公的年金等所得者は、そこから15万円を
    引きます**（地方税法施行令29条の7）。この表は既定の `age=45` を土台に
    書かれているので、これまでその15万円が要る場面がありませんでした。
    ところが **74歳の国保**（＝75歳の後期高齢者医療と並べる相手）では効きます:
    年金収入168万円の人は、総所得58万円で見ると**5割軽減**、
    15万円を引いた43万円で見ると**7割軽減**。**1段ちがいます。**
    `src/calc/kouki.py` の「75歳の誕生日で保険料はいくら変わるか」が、
    実際にここへ15万円を引いた額を渡します。

    **既定を変えていないのは、この表の他の14節が全部 `age=45` 側だから**です
    （そちらでは15万円は引きません）。**覆る条件**: この表に65歳以上を
    土台にした節が増えたら、`age` から自動で引く側へ寄せること。
    """
    r = RATES[name]
    shotokuwari = round(kyu_tadashigaki(shotoku) * float(r["所得割"]))
    kintowari_full = int(r["均等割"]) * members
    judge = shotoku if hantei is None else hantei
    pct = keigen_rate(judge, members) if keigen else 0
    kintowari = round(kintowari_full * (100 - pct) / 100)
    raw = shotokuwari + kintowari
    limit = int(r["限度額"])
    return {
        "区分": name,
        "所得割": shotokuwari,
        "軽減の前の均等割": kintowari_full,
        "軽減の割合": pct,
        "均等割": kintowari,
        "限度額で切る前": raw,
        "限度額": limit,
        "頭打ちか": raw >= limit,
        "保険料": min(raw, limit),
    }


def parts_for(age: int) -> list[str]:
    """その年齢にかかる区分。**介護分は40〜64歳だけ。**"""
    return [n for n in RATES
            if n != "介護納付金分" or KAIGO_FROM <= age <= KAIGO_TO]


def premium(shotoku: int, members: int = 1, age: int = 45,
            *, keigen: bool = True, hantei: int | None = None) -> dict:
    """世帯の国民健康保険料。

    `hantei` は**軽減の判定にだけ使う所得**（`part` の註）。既定の `None` は
    これまでと同じで、総所得金額等をそのまま判定に使います。
    """
    rows = [part(n, shotoku, members, keigen=keigen, hantei=hantei)
            for n in parts_for(age)]
    judge = shotoku if hantei is None else hantei
    return {
        "所得": shotoku,
        "被保険者数": members,
        "年齢": age,
        "内訳": rows,
        "軽減の割合": keigen_rate(judge, members) if keigen else 0,
        "保険料": sum(r["保険料"] for r in rows),
        "頭打ちの本数": sum(1 for r in rows if r["頭打ちか"]),
        "かかる上限": sum(r["限度額"] for r in rows),
    }


# ---- 折れ目（**この表の主題**）-----------------------------------------
def cap_at(name: str, members: int) -> int:
    """その区分が限度額に届く、いちばん低い所得。

    所得割 ＝ (所得 − 43万) × 率、均等割は所得によらないので、
    **限度額 − 均等割 を率で割り、43万円を足す**と境目が出ます。
    軽減は所得が上がれば外れているので、ここでは軽減なしの均等割で見ます。
    """
    r = RATES[name]
    need = int(r["限度額"]) - int(r["均等割"]) * members
    if need <= 0:
        return KISO_KOJO          # 均等割だけで上限に届く
    return KISO_KOJO + math.ceil(need / float(r["所得割"]))


def cap_order(members: int = 1, age: int = 45) -> list[dict]:
    """**どの区分が、どの順に頭打ちになるか。** 率の高い順ではありません。"""
    rows = []
    for name in parts_for(age):
        r = RATES[name]
        rows.append({
            "区分": name,
            "限度額": int(r["限度額"]),
            "所得割の率": float(r["所得割"]),
            "均等割": int(r["均等割"]) * members,
            "頭打ちになる所得": cap_at(name, members),
        })
    rows.sort(key=lambda x: x["頭打ちになる所得"])
    for i, row in enumerate(rows, 1):
        row["順番"] = i
    return rows


# ---- 節10: 頭打ちが早まる速さ（2026-08-25 に足した）---------------------
#
# **節1 と同じ `cap_at()` を使いますが、動かす軸が違います。**
# あちらは**単身**に固定して、区分ごとの折れ目を所得の上に並べます。
# こちらは**世帯人数**を動かして、折れ目が所得のどこまで下りてくるかを出します。
def cap_shift_per_member(name: str) -> float:
    """被保険者が1人増えると、その区分の頭打ちが**いくら低い所得で来るか**。

    `cap_at()` は `基礎控除 + (限度額 − 均等割×人数) ÷ 率` なので、
    人数について**傾き `均等割 ÷ 率` の直線**です。
    つまり早まる速さを決めるのは**均等割の額ではなく、率との比**です。
    """
    r = RATES[name]
    return int(r["均等割"]) / float(r["所得割"])


def cap_shift_table(age: int = 45) -> list[dict]:
    """区分べつに、**均等割の額の順**と**早まる速さの順**を並べる。

    この2つは**一致しません。** 均等割がいちばん小さい区分が、
    いちばん速く早まることがあります（率のほうがもっと小さいため）。
    """
    rows = []
    for name in parts_for(age):
        r = RATES[name]
        rows.append({
            "区分": name,
            "1人あたりの均等割": int(r["均等割"]),
            "所得割の率": float(r["所得割"]),
            "1人ふえると早まる所得": cap_shift_per_member(name),
        })
    by_kinto = sorted(rows, key=lambda x: -x["1人あたりの均等割"])
    by_speed = sorted(rows, key=lambda x: -x["1人ふえると早まる所得"])
    for i, row in enumerate(by_kinto, 1):
        row["均等割の順位"] = i
    for i, row in enumerate(by_speed, 1):
        row["早まる速さの順位"] = i
    return rows


def cap_by_members(upto: int = 8, age: int = 45) -> list[dict]:
    """**世帯人数べつに、保険料が頭打ちになる所得。**

    「最初の1本」が頭打ちになる所得と、「4本ぜんぶ」が頭打ちになる所得
    （＝賦課限度額 113万円 に届く所得）を並べます。
    """
    rows = []
    prev = None
    for m in range(1, upto + 1):
        order = cap_order(m, age)
        first = order[0]["頭打ちになる所得"]
        last = order[-1]["頭打ちになる所得"]
        rows.append({
            "被保険者数": m,
            "最初に頭打ちになる所得": first,
            "その区分": order[0]["区分"],
            "全部が頭打ちになる所得": last,
            "上限に届いたときの保険料": premium(last, m, age)["保険料"],
            "前の人数からの下がり": None if prev is None else prev - last,
        })
        prev = last
    return rows


def marginal_steps(members: int = 1, age: int = 45) -> list[dict]:
    """**所得が1万円増えたときに増える保険料が、階段状に減っていく。**

    折れ目ごとに、そこから先の「増え方」を出します。
    """
    order = cap_order(members, age)
    live = {r["区分"]: float(RATES[r["区分"]]["所得割"]) for r in order}
    rows = [{
        "ここから": KISO_KOJO,
        "止まった区分": "（まだ無し）",
        "生きている本数": len(live),
        "1万円あたり": round(sum(live.values()) * 10_000),
    }]
    for r in order:
        live.pop(r["区分"])
        rows.append({
            "ここから": r["頭打ちになる所得"],
            "止まった区分": r["区分"],
            "生きている本数": len(live),
            "1万円あたり": round(sum(live.values()) * 10_000),
        })
    return rows


def kaigo_step(shotoku: int, members: int = 1) -> dict:
    """**39歳と40歳の差。** 誕生日ひとつで乗る額。"""
    before = premium(shotoku, members, KAIGO_FROM - 1)
    after = premium(shotoku, members, KAIGO_FROM)
    return {
        "所得": shotoku,
        "被保険者数": members,
        "39歳の保険料": before["保険料"],
        "40歳の保険料": after["保険料"],
        "乗る額": after["保険料"] - before["保険料"],
        "介護分の限度額": LIMIT_KAIGO,
        "介護分は頭打ちか": after["内訳"][-1]["頭打ちか"],
    }


def keigen_cliff(members: int = 1, age: int = 45) -> dict:
    """**2割軽減の境目を1円こえると、均等割はいくら戻るか。**

    戻るのは**軽減されていた2割ぶん**なので、**均等割の重い世帯ほど大きい**。
    """
    limit = keigen_threshold(20, members)
    before = premium(limit, members, age)
    after = premium(limit + 1, members, age)
    return {
        "被保険者数": members,
        "年齢": age,
        "2割の境目": limit,
        "境目での保険料": before["保険料"],
        "1円こえたときの保険料": after["保険料"],
        "跳ぶ額": after["保険料"] - before["保険料"],
        "境目での軽減": before["軽減の割合"],
        "1円こえたときの軽減": after["軽減の割合"],
    }


def keigen_cliffs(members: int = 1, age: int = 45) -> list[dict]:
    """**軽減の崖は1つではなく3つあります。**7→5・5→2・2→0 の順に返す。

    既存の節は「2割の境目を1円こえると」だけを見ていました。
    **軽減が完全に消える所がいちばん痛い、と読めますが、違います** ——
    落ちる幅は 7→5 が20ポイント・**5→2 が30ポイント**・2→0 が20ポイントで、
    **いちばん高い崖は真ん中**です。
    """
    out = []
    for before, after in ((70, 50), (50, 20), (20, 0)):
        limit = keigen_threshold(before, members)
        lo = premium(limit, members, age)
        hi = premium(limit + 1, members, age)
        out.append({
            "被保険者数": members,
            "年齢": age,
            # **`before` / `after` はパーセントです**（`KEIGEN_STEPS` が `7 * 10` で持っている）。
            # 「割」は10分の1なので、**10で割ってから書かないと `70割 → 50割` になります**
            # （2026-08-18 まで実際にそう印字していました。誤情報なので検査を下に置いています）
            "落ちる軽減": (f"{before // 10}割 → {after // 10}割" if after
                       else f"{before // 10}割 → なし"),
            "落ちるポイント": before - after,
            "境目": limit,
            "境目での保険料": lo["保険料"],
            "1円こえたときの保険料": hi["保険料"],
            "跳ぶ額": hi["保険料"] - lo["保険料"],
        })
    return out


def cliff_by_members(age: int = 45, upto: int = 10) -> list[dict]:
    """**2割の境目の崖が、人数に比例するのはどこまでか。**

    既存の節は「世帯の人数に比例して崖が高くなります」で締めていました。
    **5人までしか正しくありません。** 2割の境目は 43万円＋57万円×人数 で
    人数とともに上がるので、**大きい世帯はその所得で既に限度額に当たっています。**
    軽減の判定に所得割は1円も入らないのに、**崖の高さは所得割込みの合計が
    限度額に当たるかどうかで決まる** —— そこが折れ目です。
    """
    unit = keigen_cliff(1, age)["跳ぶ額"]
    out = []
    for m in range(1, upto + 1):
        c = keigen_cliff(m, age)
        out.append({
            "被保険者数": m,
            "2割の境目": c["2割の境目"],
            "跳ぶ額": c["跳ぶ額"],
            "比例なら": unit * m,
            "比例からの差": c["跳ぶ額"] - unit * m,
            "境目で限度額か": c["境目での保険料"] >= LIMIT_TOTAL,
        })
    return out


def cliff_by_age(members: int = 1) -> list[dict]:
    """**崖の高さは、所得にも保険料にもよらないが、年齢にはよる。**

    既存の節は「崖の高さは所得にも保険料にもよらず、**均等割の合計 × 落ちるポイント**」
    で締めていました。**そこで止めると、均等割の合計そのものが動くことが見えません。**

    介護納付金分の均等割は**40歳から64歳までしか乗りません。**だから
    同じ所得・同じ世帯人数のまま、**40歳の誕生日で崖が高くなり、
    65歳の誕生日で元に戻ります。** 軽減の境目のほうは1円も動きません
    （軽減の判定に入るのは所得と人数だけで、年齢は入らない）。
    """
    out = []
    for age in (22, 39, 40, 64, 65, 75):
        c = keigen_cliff(members, age)
        tanto = sum(int(RATES[n]["均等割"]) for n in parts_for(age)) * members
        out.append({
            "年齢": age,
            "介護分がかかるか": "介護納付金分" in parts_for(age),
            "均等割の合計": tanto,
            "2割の境目": c["2割の境目"],
            "境目での保険料": c["境目での保険料"],
            "1円こえたときの保険料": c["1円こえたときの保険料"],
            "跳ぶ額": c["跳ぶ額"],
        })
    return out


def cliffs_by_age(members: int = 1) -> list[dict]:
    """3つの崖のそれぞれが、**40歳をまたぐといくら高くなるか。**

    落ちるポイントが 20 / 30 / 20 なので、**上がり幅も 20 / 30 / 20 の比**になります。
    上がるのは介護納付金分の均等割ぶんだけで、**所得は1円も関係しません。**
    """
    young = {c["落ちるポイント"]: c for c in keigen_cliffs(members, 39)}
    old = {c["落ちるポイント"]: c for c in keigen_cliffs(members, 40)}
    out = []
    for c in keigen_cliffs(members, 39):
        p = c["落ちるポイント"]
        out.append({
            "落ちる軽減": c["落ちる軽減"],
            "落ちるポイント": p,
            "境目": c["境目"],
            "39歳以下・65歳以上の崖": young[p]["跳ぶ額"],
            "40〜64歳の崖": old[p]["跳ぶ額"],
            "差": old[p]["跳ぶ額"] - young[p]["跳ぶ額"],
        })
    return out



def members_curve(shotoku: int, upto: int = 9, age: int = 45) -> list[dict]:
    """**世帯の所得を変えないまま、被保険者の数だけ動かす。**

    均等割は1人ふえるごとに増えるので保険料は上がります。ところが
    **軽減の判定基準は「43万円 ＋ 1人あたりの加算額 × 被保険者数」で、
    人数とともに上がります。** だからある人数をこえた所で世帯が軽減に入り、
    **1人ふえたのに保険料が下がる**ことがあります。

    ここで置いている前提が答えを決めています —— **所得を世帯主1人が
    まるごと得ていて、ふえる人には所得が無い**という置き方です。
    ふえた人にも所得があれば判定所得も上がるので、折り返しは来ません。
    """
    out: list[dict] = []
    prev: int | None = None
    for m in range(1, upto + 1):
        p = premium(shotoku, m, age)
        row = {
            "被保険者数": m,
            "保険料": p["保険料"],
            "軽減の割合": p["軽減の割合"],
            "2割の境目": keigen_threshold(20, m),
            "前の人数からの差": None if prev is None else p["保険料"] - prev,
            "下がったか": False if prev is None else p["保険料"] < prev,
        }
        out.append(row)
        prev = p["保険料"]
    return out


def members_reversal(shotoku: int, upto: int = 9, age: int = 45) -> dict:
    """**その所得で、1人ふえて保険料が下がるのは何人目か。**

    下がる所が無ければ `折り返す人数` は None です。
    """
    rows = members_curve(shotoku, upto, age)
    drops = [r for r in rows if r["下がったか"]]
    peak = max(rows, key=lambda r: r["保険料"])
    first = drops[0] if drops else None
    return {
        "所得": shotoku,
        "折り返す人数": None if first is None else first["被保険者数"],
        "折り返しで下がる額": 0 if first is None else -first["前の人数からの差"],
        "いちばん高くなる人数": peak["被保険者数"],
        "いちばん高い保険料": peak["保険料"],
        "いちばん多い人数の保険料": rows[-1]["保険料"],
        "落ちる先の軽減": None if first is None else first["軽減の割合"],
    }


def reversal_by_shotoku(
    shotokus: tuple[int, ...] = (
        1_000_000, 1_500_000, 2_000_000, 2_500_000, 3_000_000,
        3_500_000, 4_000_000, 4_500_000, 5_000_000),
    upto: int = 9,
    age: int = 45,
) -> list[dict]:
    """**折り返す人数は、所得で動きます。**

    軽減の境目が「43万円 ＋ 57万円 × 人数」で上がるので、
    **所得が高いほど、折り返しは遠い人数へ動きます。**
    """
    return [members_reversal(s, upto, age) for s in shotokus]


# ---- 節14: 実質の頭数（2026-08-26 に足した）-----------------------------
# **軽減は「割合」で書いてあるので、人数と掛け合わせられます。**
# 保険料は「所得割 ＋ 均等割の単価 × 人数 × (1 − 軽減の割合)」なので、
# 後ろの `人数 × (1 − 軽減の割合)` を1つの数として読めます。
# これを **実質の頭数** と呼びます（この表だけの言い方です。法令用語ではありません）。
#
# **所得割は被保険者数で1円も動きません**（`part()` は `members` を
# 均等割にしか掛けていない）。だから **実質の頭数が同じ2つの世帯は、
# 人数が違っても保険料が1円も違いません。**
#
# **限度額に当たっている世帯では成り立ちません**（そこで頭を切られるため）。
# 下の関数は `限度額に当たったか` を必ず一緒に返します。
def jisshitsu(shotoku: int, members: int, age: int = 45) -> dict:
    """**実質の頭数 ＝ 被保険者数 × （1 − 軽減の割合）。**"""
    p = premium(shotoku, members, age)
    pct = p["軽減の割合"]
    tanka = sum(int(RATES[n]["均等割"]) for n in parts_for(age))
    return {
        "所得": shotoku,
        "被保険者数": members,
        "軽減の割合": pct,
        "実質の頭数": members * (100 - pct) / 100,
        "均等割の単価": tanka,
        "所得割の合計": sum(r["所得割"] for r in p["内訳"]),
        "保険料": p["保険料"],
        "限度額に当たったか": p["頭打ちの本数"] > 0,
    }


def onaji_ryou(shotoku: int, upto: int = 12, age: int = 45) -> dict:
    """**同じ所得で、保険料が1円も違わない「人数のちがう世帯」を探す。**

    軽減が深くなる人数をこえると、**実質の頭数はいったん減ってから増え直します。**
    その戻る途中で、**軽減の浅い少人数の世帯とぴったり並ぶ点**が出ます。

    実質の頭数が一致する比は、軽減の割合の比だけで決まります ——
    無軽減 : 2割 ＝ 1 : 1.25 ／ 2割 : 5割 ＝ 1 : 1.6 ／ 無軽減 : 5割 ＝ 1 : 2。
    **だから並ぶのは (4人, 5人) (5人, 8人) (8人, 10人) のような組だけ**で、
    どれが実際に起きるかは所得で決まります。

    **限度額に当たっている人数は外します**（そこは頭を切られて同額になるので、
    実質の頭数の話ではありません）。
    """
    rows = [jisshitsu(shotoku, m, age) for m in range(1, upto + 1)]
    live = [r for r in rows if not r["限度額に当たったか"]]
    by_price: dict[int, list[int]] = {}
    for r in live:
        by_price.setdefault(r["保険料"], []).append(r["被保険者数"])
    pairs = [{"保険料": v, "人数": ms,
              "実質の頭数": rows[ms[0] - 1]["実質の頭数"],
              "軽減の割合": [rows[m - 1]["軽減の割合"] for m in ms]}
             for v, ms in sorted(by_price.items()) if len(ms) > 1]
    return {
        "所得": shotoku,
        "年齢": age,
        "行": rows,
        "同額の組": pairs,
        "ただ乗りできる人数": max(
            (max(p["人数"]) - min(p["人数"]) for p in pairs), default=0),
    }


def onaji_ryou_table(
    shotokus: tuple[int, ...] = (
        1_000_000, 1_500_000, 2_000_000, 2_500_000, 3_000_000,
        3_500_000, 4_000_000),
    upto: int = 12,
    age: int = 45,
) -> list[dict]:
    """**同額の組を、所得べつに並べる。**所得によって組そのものが変わります。"""
    return [onaji_ryou(s, upto, age) for s in shotokus]


def keigen_value(shotoku: int, members: int = 1, age: int = 45) -> dict:
    """**軽減はいくらの値打ちか。**軽減を外して同じ世帯を計算し、差を取ります。

    ここが `premium` の `keigen` を実際に両方向へ動かす唯一の節です。
    軽減は均等割にしか効かないので、**値打ちは所得では決まらず、
    均等割の合計と軽減の割合だけで決まります** —— ただし
    **限度額で切られると、その値打ちは目減りします。**
    """
    withk = premium(shotoku, members, age, keigen=True)
    without = premium(shotoku, members, age, keigen=False)
    tanto = sum(int(RATES[n]["均等割"]) for n in parts_for(age)) * members
    pct = withk["軽減の割合"]
    return {
        "所得": shotoku,
        "被保険者数": members,
        "軽減の割合": pct,
        "軽減なしの保険料": without["保険料"],
        "軽減ありの保険料": withk["保険料"],
        "値打ち": without["保険料"] - withk["保険料"],
        "均等割の合計": tanto,
        "切られる前の値打ち": int(tanto * pct / 100),
        "限度額で消えた値打ち": int(tanto * pct / 100) - (
            without["保険料"] - withk["保険料"]),
    }


def keigen_value_table(members: int = 1, age: int = 45) -> list[dict]:
    """軽減の値打ちを、所得の低いほうから並べる。**同じ割合でも同額とは限りません。**"""
    out = []
    for pct in (70, 50, 20):
        limit = keigen_threshold(pct, members)
        out.append(keigen_value(limit, members, age))
    return out

def keigen_value_by_members(pct: int, upto: int = 12, age: int = 45) -> list[dict]:
    """**その軽減の割合の境目ちょうどにいる世帯**の値打ちを、被保険者数の順に並べる。

    `keigen_value_table` は「1つの世帯人数で、3つの割合を縦に」並べます。
    こちらは**軸を入れ替えて**「1つの割合で、人数を横に」並べたものです。

    **人数を動かすと、境目の所得も一緒に動きます**（`keigen_threshold`）——
    5割は「43万円＋31万円×人数」、2割は「43万円＋57万円×人数」。
    **7割の基準額 43万円だけは人数で動きません。**
    だから3本の並びは、同じ形になりません。
    """
    out = []
    for m in range(1, upto + 1):
        limit = keigen_threshold(pct, m)
        r = keigen_value(limit, m, age)
        r["境目の所得"] = limit
        out.append(r)
    return out


def keigen_value_shape(pct: int, upto: int = 12, age: int = 45) -> dict:
    """上の並びの**形**。額面どおりの最後・頂点・0円になる最初の人数を返す。

    **`頂点の人数` が `上限まで見た人数` と同じなら、まだ折り返していません** ——
    そのときは `頂点は端か` が真になります。**端の値を「頂点」と呼ばないこと**
    （ここを区別しないと、7割軽減が「12人で頂点」に見えます。実際は
    12人までのどこでも折り返していないだけです）。
    """
    rows = keigen_value_by_members(pct, upto, age)
    full = [r for r in rows if r["限度額で消えた値打ち"] == 0]
    zero = [r for r in rows if r["値打ち"] == 0]
    top = max(rows, key=lambda r: r["値打ち"])
    return {
        "軽減の割合": pct,
        "額面どおりの最後の人数": full[-1]["被保険者数"] if full else None,
        "頂点の人数": top["被保険者数"],
        "頂点の値打ち": top["値打ち"],
        "頂点は端か": top["被保険者数"] == upto,
        "0円になる最初の人数": zero[0]["被保険者数"] if zero else None,
        "上限まで見た人数": upto,
        "境目の所得の増え方": (rows[-1]["境目の所得"] - rows[0]["境目の所得"])
        // (upto - 1) if upto > 1 else 0,
        "行": rows,
    }


def keigen_value_shapes(upto: int = 12, age: int = 45) -> list[dict]:
    """3つの割合の形を、薄いほうから並べる。**7割・5割・2割で消え方が違います。**"""
    return [keigen_value_shape(pct, upto, age) for pct in (20, 50, 70)]


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値（**限度額と軽減の基準は全国一律**）
    _checks.statutory(LIMIT_IRYO, 670_000, "医療分（基礎賦課分）の賦課限度額",
                      source="地方税法施行令（令和8年度）")
    _checks.statutory(LIMIT_SHIEN, 260_000, "後期高齢者支援金分の賦課限度額",
                      source="地方税法施行令（令和8年度）")
    _checks.statutory(LIMIT_KAIGO, 170_000, "介護納付金分の賦課限度額",
                      source="地方税法施行令（令和8年度）")
    _checks.statutory(LIMIT_KODOMO, 30_000, "子ども・子育て支援金分の賦課限度額",
                      source="地方税法施行令（令和8年度に新設）")
    _checks.statutory(LIMIT_TOTAL, 1_130_000, "賦課限度額の合計",
                      source="4本の合計。令和7年度は109万円だった")
    _checks.statutory(KEIGEN_BASE, 430_000, "軽減判定の基準額",
                      source="地方税法703条の5")
    _checks.statutory(KISO_KOJO, 430_000, "旧ただし書き所得を出すときに引く額",
                      source="国民健康保険法施行令。住民税の基礎控除と同額")
    _checks.statutory(KAIGO_FROM, 40, "介護納付金分がかかりはじめる年齢",
                      source="介護保険法9条2号（第2号被保険者）")
    _checks.statutory(KAIGO_TO, 64, "介護納付金分がかかる最後の年齢",
                      source="介護保険法9条2号")
    for name, r in RATES.items():
        _checks.ratio(float(r["所得割"]), f"{name}の所得割の率")

    # 2. 表の形
    _checks.unique_by(KEIGEN_STEPS, lambda r: r[0], "軽減の割合")
    _checks.unique_by(list(RATES), lambda r: r, "保険料の区分")
    # 軽減が薄くなるほど、基準額の加算は大きい（7割 < 5割 < 2割）
    _checks.ascending([p for _pct, p in KEIGEN_STEPS], "軽減の基準額の加算",
                      strict=False)
    # 限度額の合計が、4本を足したものと一致すること
    if LIMIT_TOTAL != sum(int(r["限度額"]) for r in RATES.values()):
        raise _checks.TableError("限度額の合計が、区分ごとの限度額の和と合わない")

    # 3. **主題その1**: 7割の基準額だけ、人数で動かない
    for members in (1, 2, 3, 4, 5):
        _checks.rounding(keigen_threshold(70, members), KEIGEN_BASE,
                         f"被保険者{members}人の7割軽減の基準額")
    _checks.increases_with(lambda m: keigen_threshold(50, m), (1, 2, 3, 4, 5),
                           "被保険者が増えたのに5割軽減の基準額が上がっていない")
    _checks.increases_with(lambda m: keigen_threshold(20, m), (1, 2, 3, 4, 5),
                           "被保険者が増えたのに2割軽減の基準額が上がっていない")
    # だから「7割と5割の開き」は人数とともに広がる
    _checks.increases_with(lambda m: keigen_spread(m)["7割と5割の開き"],
                           (1, 2, 3, 4, 5),
                           "人数が増えたのに7割と5割の開きが広がっていない")
    _checks.rounding(keigen_spread(1)["7割と5割の開き"], 310_000,
                     "単身の7割と5割の開き")
    _checks.rounding(keigen_spread(5)["7割と5割の開き"], 1_550_000,
                     "5人世帯の7割と5割の開き")

    # 4. 軽減の当たり方。境目のちょうどは軽減され、1円こえると外れる
    for members in (1, 3, 5):
        for pct in (70, 50, 20):
            edge = keigen_threshold(pct, members)
            if keigen_rate(edge, members) < pct:
                raise _checks.TableError(
                    f"被保険者{members}人・所得{edge:,}円で{pct // 10}割軽減が当たらない")
        top = keigen_threshold(20, members)
        if keigen_rate(top + 1, members) != 0:
            raise _checks.TableError(
                f"被保険者{members}人・2割の境目を1円こえても軽減が残っている")

    # 5. **主題その2**: 軽減は均等割にだけ効く（所得割は動かない）
    members = 3
    low = part("医療分", 400_000, members)               # 7割軽減が当たる帯
    if low["軽減の割合"] != 70:
        raise _checks.TableError("所得40万円・3人世帯で7割軽減が当たっていない")
    _checks.rounding(low["均等割"], round(low["軽減の前の均等割"] * 0.3),
                     "7割軽減が当たったときの均等割")
    # 所得割のほうは、軽減の有無で1円も変わらないこと
    with_k = part("医療分", 400_000, members, keigen=True)
    without_k = part("医療分", 400_000, members, keigen=False)
    if with_k["所得割"] != without_k["所得割"]:
        raise _checks.TableError("軽減の有無で所得割が変わっている（均等割にだけ効くはず）")

    # 6. **主題その3**: 頭打ちの順番と、階段状に減る増え方
    order = cap_order(1, 45)
    _checks.ascending([r["頭打ちになる所得"] for r in order],
                      "頭打ちになる所得（順番に並んでいること）", strict=True)
    if order[0]["区分"] != "介護納付金分":
        raise _checks.TableError(
            f"いちばん先に頭打ちになるのが {order[0]['区分']} になっている")
    # **いちばん上限の小さい区分が、いちばん最後まで止まらない**（ここが主題）
    if order[-1]["区分"] != "子ども子育て支援金分":
        raise _checks.TableError(
            f"いちばん最後まで止まらないのが {order[-1]['区分']} になっている")
    smallest = min(order, key=lambda r: r["限度額"])["区分"]
    if smallest != order[-1]["区分"]:
        raise _checks.TableError("上限がいちばん小さい区分が、最後に止まっていない")
    # **率の高い順でも、上限の小さい順でもないこと。** 決めるのは比のほう
    live = {r["区分"] for r in order}
    by_rate = [n for n in sorted(RATES, key=lambda n: -float(RATES[n]["所得割"]))
               if n in live]
    by_limit = [n for n in sorted(RATES, key=lambda n: int(RATES[n]["限度額"]))
                if n in live]
    got = [r["区分"] for r in order]
    if got == by_rate:
        raise _checks.TableError(
            "頭打ちの順番が率の高い順と一致した。主題（比で決まる）が成り立っていない")
    if got == by_limit:
        raise _checks.TableError(
            "頭打ちの順番が上限の小さい順と一致した。主題（比で決まる）が成り立っていない")
    # 順番が「上限 ÷ 率」の小さい順であること（**これが主題の式そのもの**）
    by_ratio = sorted(live, key=lambda n: int(RATES[n]["限度額"])
                      / float(RATES[n]["所得割"]))
    if got != by_ratio:
        raise _checks.TableError(
            f"頭打ちの順番 {got} が、上限÷率の順 {by_ratio} と一致しない")
    # 折れ目を越えるたび、1万円あたりの増え方が減ること
    steps = marginal_steps(1, 45)
    _checks.decreases_with(lambda i: steps[i]["1万円あたり"],
                           range(len(steps)),
                           "折れ目を越えたのに1万円あたりの増え方が減っていない")
    if steps[-1]["1万円あたり"] != 0:
        raise _checks.TableError("全部が頭打ちなのに、まだ増えている")
    # 境目の実物: その所得では頭打ちで、1円手前ではまだ頭打ちでないこと
    for row in order:
        name, at = row["区分"], row["頭打ちになる所得"]
        if not part(name, at, 1, keigen=False)["頭打ちか"]:
            raise _checks.TableError(f"{name} が {at:,}円 で頭打ちになっていない")
        # **手前は1万円で見ます。** 率がいちばん低い区分（0.30パーセント）では、
        # 所得10円の差が所得割を0.03円しか動かさず、**丸めると同じ額になります**
        if part(name, at - 10_000, 1, keigen=False)["頭打ちか"]:
            raise _checks.TableError(f"{name} が {at:,}円 の1万円手前で既に頭打ち")

    # 7. 上限に達するのは、いちばん遅い1本が止まったとき
    last = order[-1]["頭打ちになる所得"]
    _checks.rounding(premium(last, 1, 45)["保険料"], LIMIT_TOTAL,
                     "いちばん遅い1本が止まった所得での保険料")
    if premium(last - 10_000, 1, 45)["保険料"] >= LIMIT_TOTAL:
        raise _checks.TableError("その1万円手前で、もう上限に達している")

    # 8. **主題その4**: 40歳で介護分が乗る。所得によらず一定ではない
    small = kaigo_step(1_000_000, 1)
    big = kaigo_step(10_000_000, 1)
    _checks.greater(small["乗る額"], 0, "40歳になっても介護分が乗っていない")
    _checks.greater(big["乗る額"], small["乗る額"],
                    "所得が高いほうで、乗る額が大きくなっていない")
    _checks.rounding(big["乗る額"], LIMIT_KAIGO,
                     "所得1,000万円で乗る介護分（限度額まで乗るはず）")
    # 39歳と65歳には介護分がかからないこと
    for age in (39, 65):
        if "介護納付金分" in parts_for(age):
            raise _checks.TableError(f"{age}歳に介護分がかかっている")
    for age in (40, 64):
        if "介護納付金分" not in parts_for(age):
            raise _checks.TableError(f"{age}歳に介護分がかかっていない")

    # 9. **主題その5**: 2割軽減の崖は、人数に比例して高くなる
    _checks.increases_with(lambda m: keigen_cliff(m)["跳ぶ額"], (1, 2, 3, 4, 5),
                           "人数が増えたのに2割軽減の崖が高くなっていない")
    c = keigen_cliff(1)
    _checks.greater(c["跳ぶ額"], 0, "2割の境目を1円こえても保険料が増えていない")
    # 崖の正体は「軽減されていた2割ぶんの均等割」なので、
    # 均等割の合計の2割と一致すること（**式と突き合わせる**）
    for members in (1, 3, 5):
        cl = keigen_cliff(members, 45)
        want = round(sum(int(RATES[n]["均等割"]) for n in parts_for(45))
                     * members * 0.2)
        if abs(cl["跳ぶ額"] - want) > len(parts_for(45)):
            raise _checks.TableError(
                f"被保険者{members}人の崖 {cl['跳ぶ額']:,}円 と "
                f"均等割の2割 {want:,}円 が一致しない")

    # 10. 所得が増えたら保険料は減らない
    _checks.never_decreases(lambda s: premium(s, 3, 45)["保険料"],
                            (0, 430_000, 1_000_000, 3_000_000, 8_000_000,
                             20_000_000),
                            "所得が増えたのに保険料が減っている")
    # どれだけ所得があっても、合計は限度額を超えないこと
    for shotoku in (10_000_000, 50_000_000, 200_000_000):
        got = premium(shotoku, 4, 45)["保険料"]
        if got > LIMIT_TOTAL:
            raise _checks.TableError(
                f"所得{shotoku:,}円の保険料 {got:,}円 が限度額を超えている")

    # 3本の崖。**いちばん高いのは真ん中**（落ちるポイントが 20 / 30 / 20 だから）
    cliffs = keigen_cliffs(1, 45)
    if [c["落ちるポイント"] for c in cliffs] != [20, 30, 20]:
        raise _checks.TableError("軽減の落ち幅が 20/30/20 になっていない")
    # **見出しの字そのものを見る。** `KEIGEN_STEPS` はパーセントで持っているので、
    # 10で割り忘れると `70割 → 50割` と印字されます（2026-08-18 まで実際にそうでした）。
    # 数字はどれも正しいので、**値の検査は1件も落ちません。**画面に出る字を直に見るしかない
    if [c["落ちる軽減"] for c in cliffs] != ["7割 → 5割", "5割 → 2割", "2割 → なし"]:
        raise _checks.TableError(
            f"軽減の崖の見出しが 割 の単位になっていない: "
            f"{[c['落ちる軽減'] for c in cliffs]}")
    if not (cliffs[1]["跳ぶ額"] > cliffs[0]["跳ぶ額"] == cliffs[2]["跳ぶ額"]):
        raise _checks.TableError(
            f"真ん中の崖がいちばん高くない: {[c['跳ぶ額'] for c in cliffs]}")
    # 崖の高さは**均等割の合計 × 落ちるポイント**で、保険料でも所得でもない
    for c in cliffs:
        tanto = sum(int(RATES[n]["均等割"]) for n in parts_for(45))
        want = tanto * c["落ちるポイント"] // 100
        _checks.rounding(c["跳ぶ額"], want,
                         f"{c['落ちる軽減']} の崖が均等割×{c['落ちるポイント']}%と合わない")
    # **比例は5人まで。** 6人で折れ、大きい世帯では 0 になること
    rows = cliff_by_members(45, 12)
    for r in rows[:5]:
        if r["比例からの差"] != 0:
            raise _checks.TableError(
                f"{r['被保険者数']}人で比例が崩れている（5人までは崩れないはず）")
    if not any(r["比例からの差"] < 0 for r in rows[5:]):
        raise _checks.TableError("6人以上でも比例したまま＝限度額が効いていない")
    if rows[-1]["跳ぶ額"] != 0:
        raise _checks.TableError(
            f"人数を増やしても崖が消えない（{rows[-1]['跳ぶ額']:,}円）")

    # 11. **主題その6**: 崖の高さは所得にも保険料にもよらないが、**年齢にはよる**
    for members in (1, 3):
        by_age = {r["年齢"]: r for r in cliff_by_age(members)}
        # 介護分の乗らない年齢どうしは、**1円も違わない**（22 / 39 / 65 / 75）
        off = [by_age[a] for a in (22, 39, 65, 75)]
        for r in off[1:]:
            for key in ("跳ぶ額", "境目での保険料", "1円こえたときの保険料"):
                if r[key] != off[0][key]:
                    raise _checks.TableError(
                        f"介護分の乗らない{off[0]['年齢']}歳と{r['年齢']}歳で"
                        f"{key}が違う（{off[0][key]:,} と {r[key]:,}）")
        # 介護分の乗る帯の両端（40 / 64）も、たがいに一致すること
        if by_age[40]["跳ぶ額"] != by_age[64]["跳ぶ額"]:
            raise _checks.TableError("40歳と64歳で崖の高さが違う")
        _checks.greater(by_age[40]["跳ぶ額"], by_age[39]["跳ぶ額"],
                        "40歳の崖が39歳より高くなっていない")
        # 上がり幅は **介護分の均等割 × 人数 × 落ちるポイント** ちょうど
        want = int(RATES["介護納付金分"]["均等割"]) * members * 20 // 100
        _checks.rounding(by_age[40]["跳ぶ額"] - by_age[39]["跳ぶ額"], want,
                         f"被保険者{members}人・40歳で上がる崖の幅")
        # **境目のほうは、年齢では1円も動かない**（判定に入るのは所得と人数だけ）
        if len({r["2割の境目"] for r in by_age.values()}) != 1:
            raise _checks.TableError("2割軽減の境目が年齢で動いている")

    # 3つの崖の上がり幅は、落ちるポイント（20 / 30 / 20）に比例すること
    steps3 = cliffs_by_age(1)
    if [r["落ちるポイント"] for r in steps3] != [20, 30, 20]:
        raise _checks.TableError("崖の落ちるポイントが 20/30/20 になっていない")
    kaigo_tanto = int(RATES["介護納付金分"]["均等割"])
    for r in steps3:
        _checks.rounding(r["差"], kaigo_tanto * r["落ちるポイント"] // 100,
                         f"{r['落ちる軽減']} で40歳をまたぐと上がる幅")
    if not (steps3[1]["差"] > steps3[0]["差"] == steps3[2]["差"]):
        raise _checks.TableError(
            f"真ん中の上がり幅がいちばん大きくない: {[r['差'] for r in steps3]}")

    # --- 節10（2026-08-25）: 頭打ちが早まる速さ ---------------------------
    # **主張は2つ。どちらも数で置きます。**
    # (1) 人数が増えるほど、上限に届く所得は下がる。しかも**一定の傾き**
    caps = cap_by_members()
    drops = [r["前の人数からの下がり"] for r in caps[1:]]
    if not all(d > 0 for d in drops):
        raise _checks.TableError(
            f"人数が増えても上限に届く所得が下がっていない: {drops}")
    if max(drops) - min(drops) > 1:      # 丸めの1円ぶんだけ許す
        raise _checks.TableError(f"下がり方が一定になっていない: {drops}")
    # **`cap_at()` は `ceil` で切り上げるので、1円ぶんずれます。**
    # `rounding` は丸めの順番を見る道具なので、ここでは使えません
    want_drop = cap_shift_per_member("子ども子育て支援金分")
    if abs(drops[0] - want_drop) > 1.0:
        raise _checks.TableError(
            f"1人ふえたときに、全部が頭打ちになる所得の下がり: {drops[0]:,} になった。"
            f"均等割 ÷ 率 ＝ {want_drop:,.1f} のはず")
    # 上限に届いたときの保険料は、どの人数でも賦課限度額そのもの
    for row in caps:
        _checks.rounding(row["上限に届いたときの保険料"],
                         sum(int(RATES[n]["限度額"]) for n in parts_for(45)),
                         f"{row['被保険者数']}人世帯で上限に届いたときの保険料")
    _checks.greater(caps[0]["全部が頭打ちになる所得"] - caps[-1]["全部が頭打ちになる所得"],
                    4_000_000, "単身と8人世帯で、上限に届く所得の差が")
    # (2) **均等割の額の順位と、早まる速さの順位は一致しない**
    shifts = cap_shift_table()
    if all(r["均等割の順位"] == r["早まる速さの順位"] for r in shifts):
        raise _checks.TableError(
            "均等割の順位と早まる速さの順位が全部一致している（節の主張と逆）")
    top_kinto = [r for r in shifts if r["均等割の順位"] == 1][0]
    if top_kinto["早まる速さの順位"] == 1:
        raise _checks.TableError(
            f"均等割がいちばん大きい {top_kinto['区分']} が、"
            "早まる速さでも1位になっている（率との比で決まるはず）")
    for row in shifts:
        _checks.rounding(row["1人ふえると早まる所得"],
                         row["1人あたりの均等割"] / row["所得割の率"],
                         f"{row['区分']}の、1人ふえて早まる所得")

    # (3) **人数が1人ふえて保険料が下がる点が、実際にある**（節の主張そのもの）
    curve = members_curve(2_000_000, 9, 45)
    drops = [r for r in curve if r["下がったか"]]
    if not drops:
        raise _checks.TableError(
            "所得200万円で、被保険者が1人ふえて保険料が下がる点が1つも無い（節の主張と逆）")
    d = drops[0]
    prev = curve[d["被保険者数"] - 2]
    if d["軽減の割合"] <= prev["軽減の割合"]:
        raise _checks.TableError(
            f"下がった {d['被保険者数']}人目で、軽減の割合が上がっていない"
            f"（{prev['軽減の割合']} → {d['軽減の割合']}）。下がる理由が軽減でないことになる")
    tanto1 = sum(int(RATES[n]["均等割"]) for n in parts_for(45))
    off_prev = tanto1 * prev["被保険者数"] * prev["軽減の割合"] // 100
    off_now = tanto1 * d["被保険者数"] * d["軽減の割合"] // 100
    _checks.rounding(-d["前の人数からの差"], (off_now - off_prev) - tanto1,
                     "1人ふえて下がる額（多く消えた軽減 − ふえた均等割）")

    # (4) **折り返す人数は、所得について単調ではない**（節の主張）
    rev = [r for r in reversal_by_shotoku() if r["折り返す人数"] is not None]
    if all(a["折り返す人数"] <= b["折り返す人数"]
           for a, b in zip(rev, rev[1:])):
        raise _checks.TableError(
            "折り返す人数が所得について単調に増えている（節の主張と逆）")
    kinds = {r["落ちる先の軽減"] for r in rev}
    if kinds != {50, 20}:
        raise _checks.TableError(
            f"折り返しの落ちる先が2種類（5割・2割）になっていない: {sorted(kinds)}")
    # 5割で折り返す帯が先、2割で折り返す帯が後。**入れ替わりが1回だけ**
    seq = [r["落ちる先の軽減"] for r in rev]
    if seq != sorted(seq, key=lambda v: -v):
        raise _checks.TableError(f"5割の帯と2割の帯が入り混じっている: {seq}")

    # (5) **軽減の額面は、均等割の合計 × 割合ぴったり**（所得割も所得も1円も入らない）
    for members in (1, 4, 8, 9):
        for r in keigen_value_table(members, 45):
            _checks.rounding(r["切られる前の値打ち"],
                             r["均等割の合計"] * r["軽減の割合"] / 100,
                             f"被保険者{members}人・{r['軽減の割合']}パーセント軽減の額面")
            _checks.rounding(r["値打ち"],
                             r["切られる前の値打ち"] - r["限度額で消えた値打ち"],
                             f"被保険者{members}人・{r['軽減の割合']}パーセント軽減の手取り")
            if r["限度額で消えた値打ち"] < 0:
                raise _checks.TableError(
                    f"限度額で消えた値打ちが負（被保険者{members}人・"
                    f"{r['軽減の割合']}パーセント）: {r['限度額で消えた値打ち']:,}円")
    # 小さい世帯では1円も食われない。大きい世帯では食われる（節の主張）
    for members in (1, 4):
        for r in keigen_value_table(members, 45):
            if r["限度額で消えた値打ち"] != 0:
                raise _checks.TableError(
                    f"被保険者{members}人・{r['軽減の割合']}パーセントで限度額に当たっている"
                    f"（この世帯では額面どおり受け取れるはず）")
    worst = keigen_value_table(9, 45)[-1]
    if worst["限度額で消えた値打ち"] <= 0:
        raise _checks.TableError(
            "被保険者9人の2割軽減で、限度額に食われる額が0円になっている（節の主張と逆）")
    _checks.greater(worst["限度額で消えた値打ち"], worst["値打ち"] * 10,
                    "9人世帯の2割軽減で、限度額に食われる額が手取りの10倍を")
    # 同じ割合でも、人数が4倍なら額面も4倍（均等割にしか効かないから）
    one = keigen_value_table(1, 45)[0]
    four = keigen_value_table(4, 45)[0]
    _checks.rounding(four["値打ち"], one["値打ち"] * 4,
                     "4人世帯の7割軽減の値打ちが、単身の4倍であること")

    # --- 節14（2026-08-26）: 実質の頭数 --------------------------------
    # (1) **所得割は被保険者数で1円も動かない**（動くのは均等割だけ）。
    #     ここが崩れると、この節の式そのものが成り立ちません
    for shotoku in (2_000_000, 3_500_000):
        wari = {sum(r["所得割"] for r in premium(shotoku, m, 45)["内訳"])
                for m in range(1, 13)}
        if len(wari) != 1:
            raise _checks.TableError(
                f"所得{shotoku:,}円で、所得割の合計が人数で動いている: {sorted(wari)}")
    # (2) **実質の頭数が同じなら、保険料が1円も違わない**
    tanka35 = sum(int(RATES[n]["均等割"]) for n in parts_for(45))
    j35 = onaji_ryou(3_500_000, 12, 45)
    if not j35["同額の組"]:
        raise _checks.TableError(
            "所得350万円・45歳で、保険料が同額になる人数の組が1つも出ない")
    for pair in j35["同額の組"]:
        for m in pair["人数"]:
            row = j35["行"][m - 1]
            _checks.rounding(row["実質の頭数"], pair["実質の頭数"],
                             f"{m}人世帯の実質の頭数")
            # 保険料 ＝ 所得割 ＋ 均等割の単価 × 実質の頭数（**式そのもの**）
            _checks.rounding(row["保険料"],
                             row["所得割の合計"] + round(tanka35 * row["実質の頭数"]),
                             f"{m}人世帯の保険料が『所得割＋単価×実質の頭数』と合わない")
    # 5人と10人がそろっていること（**節が名指ししている組**）
    if [5, 10] not in [p["人数"] for p in j35["同額の組"]]:
        raise _checks.TableError(
            f"所得350万円で (5人, 10人) が同額になっていない: "
            f"{[p['人数'] for p in j35['同額の組']]}")
    # (3) **実質の頭数は人数について単調ではない**（軽減が深くなる所で下がる）
    jis = [r["実質の頭数"] for r in j35["行"]]
    if all(b >= a for a, b in zip(jis, jis[1:])):
        raise _checks.TableError(
            f"実質の頭数が単調に増えている（節の主張と逆）: {jis}")
    # (4) 並ぶ組の比は、軽減の割合の比だけで決まる（1.25 / 1.6 / 2 のどれか）
    want_ratios = {1.25, 1.6, 2.0, 10 / 3, 8 / 3, 5 / 3}
    for row in onaji_ryou_table():
        for pair in row["同額の組"]:
            lo, hi = min(pair["人数"]), max(pair["人数"])
            if not any(abs(hi / lo - w) < 1e-9 for w in want_ratios):
                raise _checks.TableError(
                    f"所得{row['所得']:,}円の同額の組 {pair['人数']} の比 "
                    f"{hi / lo} が、軽減の割合の比のどれとも一致しない")
            # 比は、そのまま「1 − 軽減の割合」の逆比であること
            lo_pct, hi_pct = pair["軽減の割合"]
            _checks.rounding(hi / lo, (100 - lo_pct) / (100 - hi_pct),
                             f"所得{row['所得']:,}円の同額の組 {pair['人数']} の比")

    # 12. **主題その6**: 軽減が薄いほど、限度額に早く食べられる
    #     （`keigen_value_shapes`。2026-08-26 に足した節の裏）
    shapes = {s["軽減の割合"]: s for s in keigen_value_shapes(12, 45)}
    last = [shapes[p]["額面どおりの最後の人数"] for p in (20, 50, 70)]
    if not all(x is not None for x in last):
        raise _checks.TableError(
            "12人まで見て、額面どおり受け取れる人数が出ない割合がある")
    _checks.ascending(last, "額面どおり受け取れる最後の人数（2割→5割→7割）",
                      strict=True)
    # 額面どおりの区間では、値打ちは「均等割の合計 × 割合」ぴったりであること
    for pct, s in shapes.items():
        for r in s["行"]:
            if r["限度額で消えた値打ち"] != 0:
                continue
            _checks.rounding(r["値打ち"], int(r["均等割の合計"] * pct / 100),
                             f"{pct // 10}割軽減・被保険者{r['被保険者数']}人の値打ち")
    # **7割の境目だけ、人数で1円も動かない**（上の 3 と同じことを、この軸でも当てる）
    if shapes[70]["境目の所得の増え方"] != 0:
        raise _checks.TableError("7割軽減の境目が、人数で動いている")
    for pct in (20, 50):
        if shapes[pct]["境目の所得の増え方"] <= 0:
            raise _checks.TableError(f"{pct // 10}割軽減の境目が、人数で上がっていない")
    # 2割だけが、12人までのうちに **完全に0円** になること
    if shapes[20]["0円になる最初の人数"] is None:
        raise _checks.TableError("2割軽減の値打ちが、12人まで見ても0円にならない")
    for pct in (50, 70):
        if shapes[pct]["0円になる最初の人数"] is not None:
            raise _checks.TableError(
                f"{pct // 10}割軽減の値打ちが、12人までのうちに0円になっている")

    _checks.assumption_values(ASSUMPTIONS, name="kokuho")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 「上限113万円」の手前に、折れ目が3つある（単身・45歳）===")
    for row in cap_order(1, 45):
        print(f"  {row['順番']}番目  {row['区分']:<22}"
              f"  限度額 {row['限度額']:>9,}円"
              f"  所得割 {row['所得割の率'] * 100:>5.2f}パーセント"
              f"  → 頭打ちになる所得 {row['頭打ちになる所得']:>12,}円")
    order = cap_order(1, 45)
    print(f"  → **上限がいちばん小さい子ども・子育て支援金分（3万円）が、"
          f"いちばん最後まで止まりません**。率も0.30パーセントと小さいからです")
    print(f"    決めているのは上限でも率でもなく **上限 ÷ 率** で、"
          f"いちばん先に止まるのは介護納付金分、"
          f"**上限がいちばん大きい医療分（67万円）が2番目**です")
    print(f"    最初の1本が止まる {order[0]['頭打ちになる所得']:,}円 から、"
          f"最後の1本が止まる {order[-1]['頭打ちになる所得']:,}円 までは、"
          f"**{order[-1]['頭打ちになる所得'] - order[0]['頭打ちになる所得']:,}円** 開いています")

    print("\n=== 所得が1万円増えたときに増える保険料は、階段状に減る（単身・45歳）===")
    for row in marginal_steps(1, 45):
        print(f"  所得 {row['ここから']:>12,}円 から"
              f"  1万円あたり {row['1万円あたり']:>7,}円"
              f"  （生きている区分 {row['生きている本数']}本"
              f" / 直前に止まったのは {row['止まった区分']}）")

    print("\n=== 7割軽減の境目だけ、世帯人数で動かない ===")
    for members in (1, 2, 3, 4, 5):
        s = keigen_spread(members)
        print(f"  被保険者{members}人"
              f"  7割 {s['7割の境目']:>10,}円"
              f"  5割 {s['5割の境目']:>10,}円"
              f"  2割 {s['2割の境目']:>10,}円"
              f"  → 7割と5割の開き {s['7割と5割の開き']:>10,}円")
    print(f"  → 7割の基準額は **43万円のまま**で、被保険者が何人いても動きません。"
          f"5割は1人あたり31万円・2割は1人あたり57万円ずつ上がります")

    print("\n=== 2割軽減の境目を1円こえると、均等割が2割ぶん戻る（45歳）===")
    for members in (1, 2, 3, 4, 5):
        c = keigen_cliff(members, 45)
        print(f"  被保険者{members}人  境目 {c['2割の境目']:>10,}円"
              f"  {c['境目での保険料']:>9,}円 → {c['1円こえたときの保険料']:>9,}円"
              f"  **跳ぶ額 {c['跳ぶ額']:>7,}円**")
    print("  → 戻るのは軽減されていた均等割の2割ぶんなので、"
          "**世帯の人数に比例して崖が高くなります**")

    print("\n=== 40歳の誕生日で介護分が乗る。乗る額は所得で変わる（単身）===")
    for shotoku in (500_000, 1_000_000, 2_000_000, 4_000_000, 8_000_000):
        k = kaigo_step(shotoku, 1)
        atama = "（頭打ち）" if k["介護分は頭打ちか"] else ""
        print(f"  所得 {k['所得']:>10,}円"
              f"  39歳 {k['39歳の保険料']:>9,}円"
              f"  → 40歳 {k['40歳の保険料']:>9,}円"
              f"  **乗る額 {k['乗る額']:>7,}円**{atama}")
    print(f"  → 介護分にも所得割があるので、**乗る額は一定ではありません**。"
          f"上限の {LIMIT_KAIGO:,}円 で止まります")

    print("\n=== 軽減の崖は3つあり、いちばん高いのは真ん中（単身・45歳）===")
    for c in keigen_cliffs(1, 45):
        print(f"  {c['落ちる軽減']:<10}（{c['落ちるポイント']}ポイント）"
              f"  境目 {c['境目']:>10,}円"
              f"  {c['境目での保険料']:>9,}円 → {c['1円こえたときの保険料']:>9,}円"
              f"  **跳ぶ額 {c['跳ぶ額']:>7,}円**")
    cl = keigen_cliffs(1, 45)
    tanto = sum(int(RATES[n]["均等割"]) for n in parts_for(45))
    print(f"  → **軽減が完全に消える2割の境目が、いちばん痛いわけではありません。**"
          f"7割→5割 と 2割→なし は {cl[0]['跳ぶ額']:,}円 で同額、"
          f"**真ん中の 5割→2割 だけが {cl[1]['跳ぶ額']:,}円** ＝ "
          f"**{cl[1]['跳ぶ額'] / cl[0]['跳ぶ額']:.2f}倍**")
    print(f"    落ちる幅が 20・**30**・20 ポイントだからです。"
          f"崖の高さは所得にも保険料にもよらず、**均等割の合計 {tanto:,}円 × 落ちるポイント**"
          f"（{tanto:,}×30% = {cl[1]['跳ぶ額']:,}円）")

    print("\n=== 2割の崖が人数に比例するのは5人まで。10人で0円になる（45歳）===")
    for r in cliff_by_members(45, 11):
        mark = "  ← **限度額**" if r["境目で限度額か"] else ""
        print(f"  被保険者{r['被保険者数']:>2}人  境目 {r['2割の境目']:>10,}円"
              f"  跳ぶ額 {r['跳ぶ額']:>7,}円"
              f"  （比例なら {r['比例なら']:>7,}円 / 差 {r['比例からの差']:>8,}円）{mark}")
    rr = cliff_by_members(45, 11)
    peak = max(rr, key=lambda r: r["跳ぶ額"])
    zero = next(r for r in rr if r["跳ぶ額"] == 0)
    print(f"  → **1人から5人までは、ぴったり {rr[0]['跳ぶ額']:,}円 × 人数**です。"
          f"6人で折れ、**{peak['被保険者数']}人の {peak['跳ぶ額']:,}円 が頂点**、"
          f"**{zero['被保険者数']}人で 0円**（軽減があってもなくても {LIMIT_TOTAL:,}円）")
    print(f"    2割の境目は 43万円＋57万円×人数 で上がるので、"
          f"**大きい世帯はその所得で既に限度額に当たっています。**"
          f"軽減の判定に所得割は1円も入らないのに、"
          f"**崖の高さは所得割込みの合計が限度額に届くかで決まる**")

    print("\n=== 同じ所得のまま、40歳で崖が高くなり、65歳で元に戻る（単身）===")
    for r in cliff_by_age(1):
        mark = "  ← **介護分あり**" if r["介護分がかかるか"] else ""
        print(f"  {r['年齢']:>2}歳  均等割の合計 {r['均等割の合計']:>7,}円"
              f"  境目 {r['2割の境目']:>10,}円"
              f"  {r['境目での保険料']:>9,}円 → {r['1円こえたときの保険料']:>9,}円"
              f"  **跳ぶ額 {r['跳ぶ額']:>7,}円**{mark}")
    ba = {r["年齢"]: r for r in cliff_by_age(1)}
    kaigo_tanto = int(RATES["介護納付金分"]["均等割"])
    print(f"  → **崖の高さは所得にも保険料にもよりませんが、年齢にはよります。**"
          f"39歳以下と65歳以上は {ba[39]['跳ぶ額']:,}円、"
          f"**40歳から64歳までだけ {ba[40]['跳ぶ額']:,}円** ＝ "
          f"**{ba[40]['跳ぶ額'] / ba[39]['跳ぶ額']:.4f}倍**")
    print(f"    上がる {ba[40]['跳ぶ額'] - ba[39]['跳ぶ額']:,}円 は、"
          f"**介護納付金分の均等割 {kaigo_tanto:,}円 のちょうど2割**です。"
          f"所得は1円も関係しません")
    print(f"    **軽減の境目のほうは、年齢では1円も動きません**"
          f"（{ba[39]['2割の境目']:,}円 のまま）。判定に入るのは所得と人数だけで、"
          f"年齢は入らないからです。**同じ所得・同じ世帯で、"
          f"1円こえたときに失う額だけが年齢で変わります**")
    print(f"    22歳と75歳は、崖も保険料も**1円も違いません**"
          f"（どちらも {ba[75]['境目での保険料']:,}円 → {ba[75]['1円こえたときの保険料']:,}円）。"
          f"高くなるのは**40歳から64歳までの25年間だけ**です")

    print("\n=== 世帯人数が1人ふえるごとに、上限113万円に届く所得は63万円ずつ下がる（40〜64歳）===")
    print(f"{'被保険者数':>10s} {'最初の1本が頭打ち':>16s} {'4本ぜんぶが頭打ち':>16s} {'前の人数から'}")
    for row in cap_by_members():
        drop = ("—" if row["前の人数からの下がり"] is None
                else f"−{row['前の人数からの下がり']:,}円")
        print(f"  {row['被保険者数']:>4}人 {row['最初に頭打ちになる所得']:>15,}円"
              f"（{row['その区分']}） {row['全部が頭打ちになる所得']:>13,}円  {drop}")
    caps = cap_by_members()
    print(f"  → 上限そのものは動きません（どの人数でも "
          f"{caps[0]['上限に届いたときの保険料']:,}円）。動くのは**そこへ届く所得**のほうで、"
          f"単身 {caps[0]['全部が頭打ちになる所得']:,}円 に対し "
          f"8人世帯は {caps[-1]['全部が頭打ちになる所得']:,}円 ＝ "
          f"**{caps[0]['全部が頭打ちになる所得'] - caps[-1]['全部が頭打ちになる所得']:,}円 低い**")
    print("  → 均等割は人数ぶん増えるので、そのぶん所得割が少なくても限度額に届きます。"
          "**人数が多い世帯ほど、保険料は早く『所得に反応しなくなる』**わけです")
    print("\n  --- 早まる速さを決めるのは、均等割の額ではなく**率との比**です ---")
    print(f"{'区分':<20s} {'1人あたり均等割':>14s} {'所得割の率':>10s} "
          f"{'1人ふえて早まる所得':>18s}  順位（額 / 速さ）")
    for row in cap_shift_table():
        print(f"  {row['区分']:<18s} {row['1人あたりの均等割']:>12,}円 "
              f"{row['所得割の率'] * 100:>9.2f}% "
              f"{row['1人ふえると早まる所得']:>16,.0f}円   "
              f"{row['均等割の順位']}位 / **{row['早まる速さの順位']}位**")
    sh = cap_shift_table()
    big = [r for r in sh if r["均等割の順位"] == 1][0]
    fast = [r for r in sh if r["早まる速さの順位"] == 1][0]
    print(f"  → 均等割がいちばん大きいのは {big['区分']}（{big['1人あたりの均等割']:,}円）ですが、"
          f"早まる速さでは **{big['早まる速さの順位']}位**。"
          f"いちばん速いのは {fast['区分']}（均等割 {fast['1人あたりの均等割']:,}円）で、"
          f"1人ふえるごとに **{fast['1人ふえると早まる所得']:,.0f}円** 早まります")
    print("  → **額の大きさの順と、効きの順は一致しません。**"
          "早まる所得は `均等割 ÷ 所得割の率` なので、率が小さい区分ほど大きく動きます")

    print("\n=== 3つの崖は、40歳をまたぐと 20・30・20 の比で高くなる（単身）===")
    for r in cliffs_by_age(1):
        print(f"  {r['落ちる軽減']:<10}（{r['落ちるポイント']}ポイント）"
              f"  境目 {r['境目']:>10,}円"
              f"  39歳以下・65歳以上 {r['39歳以下・65歳以上の崖']:>7,}円"
              f"  → 40〜64歳 {r['40〜64歳の崖']:>7,}円"
              f"  **差 {r['差']:>6,}円**")
    s3 = cliffs_by_age(1)
    print(f"  → 上がるのは介護納付金分の均等割 {kaigo_tanto:,}円 のうち、"
          f"**落ちるポイントぶんだけ**です（{kaigo_tanto:,}×20% = {s3[0]['差']:,}円、"
          f"{kaigo_tanto:,}×30% = {s3[1]['差']:,}円）。"
          f"**3つの崖の差を全部足すと {sum(r['差'] for r in s3):,}円** ＝ "
          f"介護納付金分の均等割の {sum(r['落ちるポイント'] for r in s3)}パーセントです")

    print("\n=== 同じ所得のまま被保険者が1人ふえると、保険料が下がることがある（45歳・所得200万円）===")
    for r in members_curve(2_000_000, 9, 45):
        diff = ("—" if r["前の人数からの差"] is None
                else f"{r['前の人数からの差']:+,}円")
        mark = "  ← **1人ふえて下がった**" if r["下がったか"] else ""
        print(f"  被保険者{r['被保険者数']:>2}人  保険料 {r['保険料']:>9,}円"
              f"  軽減 {r['軽減の割合']:>2}パーセント"
              f"  2割の境目 {r['2割の境目']:>10,}円"
              f"  {diff}{mark}")
    mc = members_curve(2_000_000, 9, 45)
    drop = next(r for r in mc if r["下がったか"])
    before = mc[drop["被保険者数"] - 2]
    print(f"  → **{before['被保険者数']}人から{drop['被保険者数']}人へ、頭数が1つふえて "
          f"{-drop['前の人数からの差']:,}円 安くなります。**"
          f"均等割は1人ぶん {sum(int(RATES[n]['均等割']) for n in parts_for(45)):,}円 増えているのに、です")
    _tanto1 = sum(int(RATES[n]["均等割"]) for n in parts_for(45))
    _b_tanto = _tanto1 * before["被保険者数"]
    _a_tanto = _tanto1 * drop["被保険者数"]
    _b_off = _b_tanto * before["軽減の割合"] // 100
    _a_off = _a_tanto * drop["軽減の割合"] // 100
    print(f"    軽減の判定基準が **43万円＋1人あたりの加算額×人数** で上がるからです。"
          f"{before['被保険者数']}人では 均等割 {_b_tanto:,}円 の"
          f"{before['軽減の割合']}パーセントぶん {_b_off:,}円 しか消えていませんが、"
          f"{drop['被保険者数']}人では {_a_tanto:,}円 の"
          f"{drop['軽減の割合']}パーセントぶん {_a_off:,}円 が消えます")
    print(f"    差し引き **{_a_off - _b_off:,}円 多く消えて**、"
          f"ふえた均等割 {_tanto1:,}円 を上回るので、"
          f"**{_a_off - _b_off:,} − {_tanto1:,} = {-drop['前の人数からの差']:,}円 安くなります**")
    print(f"    **この結論は、こちらが置いた前提で決まっています** —— "
          f"所得 {2_000_000:,}円 を世帯主1人がまるごと得ていて、"
          f"**ふえる人には所得が無い**という置き方です。"
          f"ふえた人にも所得があれば判定所得も上がるので、折り返しは来ません")

    print("\n=== 折り返す人数は、所得が上がるほど遠くなる —— ではありません（45歳）===")
    print(f"{'世帯の所得':>12s} {'折り返す人数':>12s} {'下がる額':>12s} "
          f"{'落ちる先':>10s} {'いちばん高くなる人数'}")
    for r in reversal_by_shotoku():
        if r["折り返す人数"] is None:
            print(f"  {r['所得']:>10,}円  {'折り返さない':>12s}"
                  f"  {'—':>12s}  {'—':>10s}  {r['いちばん高くなる人数']}人")
            continue
        print(f"  {r['所得']:>10,}円  {r['折り返す人数']:>10}人目"
              f"  {r['折り返しで下がる額']:>10,}円"
              f"  {r['落ちる先の軽減']:>7}パーセント軽減"
              f"  {r['いちばん高くなる人数']}人")
    rv = [r for r in reversal_by_shotoku() if r["折り返す人数"] is not None]
    go = [r for r in rv if r["落ちる先の軽減"] == 50]
    back = [r for r in rv if r["落ちる先の軽減"] == 20]
    print(f"  → 順に {'→'.join(str(r['折り返す人数']) for r in rv)} と進んで、"
          f"**{go[-1]['所得']:,}円 の {go[-1]['折り返す人数']}人目から "
          f"{back[0]['所得']:,}円 の {back[0]['折り返す人数']}人目へ戻ります。**"
          f"単調ではありません")
    print(f"    **軽減の境目が2本あり、上がる速さが違うからです** ——"
          f"5割は1人あたり{KEIGEN_STEPS[1][1]:,}円、2割は1人あたり{KEIGEN_STEPS[2][1]:,}円ずつ上がります。"
          f"所得が低いうちは**5割の境目に先に当たり**、"
          f"{back[0]['所得']:,}円 をこえると**2割の境目のほうが先**になります")
    print(f"    落ちる先が2割に変わると、消える均等割は5割ぶんから2割ぶんへ減るので、"
          f"**下がる額も {go[-1]['折り返しで下がる額']:,}円 から {back[0]['折り返しで下がる額']:,}円 へ、"
          f"{go[-1]['折り返しで下がる額'] / back[0]['折り返しで下がる額']:.1f}分の1 に落ちます**")

    print("\n=== 軽減の値打ちは、額面どおりには受け取れない（軽減ありと無しを両方計算する）===")
    for members in (1, 4, 9):
        print(f"  --- 被保険者{members}人（均等割の合計 "
              f"{sum(int(RATES[n]['均等割']) for n in parts_for(45)) * members:,}円）---")
        for r in keigen_value_table(members, 45):
            eaten = ("" if r["限度額で消えた値打ち"] == 0
                     else f"  ← **限度額が {r['限度額で消えた値打ち']:,}円 食べた**")
            print(f"    軽減 {r['軽減の割合']:>2}パーセント  境目の所得 {r['所得']:>10,}円"
                  f"  軽減なし {r['軽減なしの保険料']:>9,}円"
                  f"  → 軽減あり {r['軽減ありの保険料']:>9,}円"
                  f"  額面 {r['切られる前の値打ち']:>8,}円"
                  f"  **手元に残る {r['値打ち']:>8,}円**{eaten}")
    kv1 = keigen_value_table(1, 45)
    kv4 = keigen_value_table(4, 45)
    kv9 = keigen_value_table(9, 45)
    print(f"  → 額面は **均等割の合計 × 軽減の割合** ぴったりで、"
          f"**所得割も所得も1円も入りません。**"
          f"単身の7割軽減は {kv1[0]['値打ち']:,}円、4人世帯なら {kv4[0]['値打ち']:,}円 ＝ "
          f"**ちょうど{kv4[0]['値打ち'] / kv1[0]['値打ち']:.0f}倍**です")
    print(f"    ところが**額面どおり受け取れるのは、どの区分も限度額に当たっていない世帯だけ**です。"
          f"軽減は均等割を減らしますが、**減らす前に限度額で切られていた区分は、"
          f"減らしても切られたまま**なので、そのぶんは1円も返ってきません")
    worst = kv9[-1]
    print(f"    いちばん極端なのは**被保険者9人の2割軽減**（境目の所得 {worst['所得']:,}円）——"
          f"額面 {worst['切られる前の値打ち']:,}円 のうち "
          f"**{worst['限度額で消えた値打ち']:,}円 が限度額に吸われ、"
          f"手元に残るのは {worst['値打ち']:,}円 だけ**です "
          f"（額面の {worst['値打ち'] / worst['切られる前の値打ち'] * 100:.1f}パーセント）")
    print(f"    **「2割軽減が受けられます」と言われて、実際に安くなるのが "
          f"{worst['値打ち']:,}円**。"
          f"この目減りは、**軽減の判定にも軽減の割合にも書かれていません** ——"
          f"限度額のほうから来ます")

    print("\n=== 軽減が薄いほど、限度額に早く食べられる —— 7割は10人まで無傷、2割は10人で0円（45歳）===")
    _shapes = keigen_value_shapes(12, 45)
    for _s in _shapes:
        _pct = _s["軽減の割合"]
        print(f"  --- {_pct // 10}割軽減の境目ちょうどにいる世帯 ---")
        for _r in _s["行"]:
            _eaten = ("" if _r["限度額で消えた値打ち"] == 0
                      else f"  ← **限度額が {_r['限度額で消えた値打ち']:>9,}円 食べた**")
            print(f"    被保険者{_r['被保険者数']:>2}人  境目の所得 {_r['境目の所得']:>10,}円"
                  f"  額面 {_r['切られる前の値打ち']:>8,}円"
                  f"  **手元に残る {_r['値打ち']:>8,}円**{_eaten}")
        _zero = _s["0円になる最初の人数"]
        _top = ("**まだ折り返していません**（12人まで見て、いちばん高いのが12人）"
                if _s["頂点は端か"]
                else f"頂点は**{_s['頂点の人数']}人の {_s['頂点の値打ち']:,}円**")
        print(f"    → 額面どおり受け取れるのは **{_s['額面どおりの最後の人数']}人まで**。{_top}。"
              + (f"**{_zero}人からは1円も安くなりません**"
                 if _zero else "12人まで見ても0円にはなりません"))
    _thin, _mid, _thick = _shapes           # 2割・5割・7割の順
    print(f"  → **薄い軽減ほど、早く食べられます。** 額面どおり受け取れる最後の人数は "
          f"**2割 {_thin['額面どおりの最後の人数']}人 ／ 5割 {_mid['額面どおりの最後の人数']}人 ／ "
          f"7割 {_thick['額面どおりの最後の人数']}人**。"
          f"**割合が厚いほうが、人数に強い**という向きです")
    print(f"    理由は**軽減の判定基準額のほう**にあります —— "
          f"境目の所得は1人ふえるごとに **2割 {_thin['境目の所得の増え方']:,}円 ／ "
          f"5割 {_mid['境目の所得の増え方']:,}円 ／ 7割 {_thick['境目の所得の増え方']:,}円** 動きます。"
          f"**7割だけが1円も動きません**（基準額 {KEIGEN_BASE:,}円 は人数で加算されない）。"
          f"薄い軽減ほど**高い所得で当たる**ので、当たった時点でもう限度額の側にいます")
    print(f"    軽減は均等割を減らしますが、**減らす前に限度額で切られていた区分は、"
          f"減らしても切られたまま**です。だから"
          f"**「対象になる所得の上限」は薄い軽減ほど速く上がるのに、"
          f"「実際に安くなる額」は薄い軽減ほど早く消えます** —— 向きが逆です")
    _z = _thin["行"][_thin["0円になる最初の人数"] - 1]
    print(f"    いちばん極端なのが**被保険者{_z['被保険者数']}人の2割軽減**"
          f"（境目の所得 {_z['境目の所得']:,}円）—— "
          f"額面 {_z['切られる前の値打ち']:,}円 が**まるごと限度額に吸われ、手元に残るのは0円**。"
          f"軽減があってもなくても保険料は {_z['軽減ありの保険料']:,}円 で、"
          f"**1円も違いません**")
    print(f"    **この並びは「境目ちょうどの所得」で揃えています** —— "
          f"人数を動かすと境目も動くので、**所得を固定した比較ではありません。**"
          f"所得を固定すると軽減の割合そのものが変わるため、"
          f"「同じ割合の中で人数だけを動かす」にはこの揃え方しかありません")

    print("\n=== 保険料が1円も違わない、人数のちがう世帯がある（45歳・所得350万円）===")
    _j = onaji_ryou(3_500_000, 12, 45)
    for r in _j["行"]:
        mark = "  ← **限度額に当たっている**" if r["限度額に当たったか"] else ""
        print(f"  被保険者{r['被保険者数']:>2}人  軽減 {r['軽減の割合']:>2}パーセント"
              f"  **実質の頭数 {r['実質の頭数']:>4.1f}**"
              f"  所得割の合計 {r['所得割の合計']:>9,}円"
              f"  保険料 {r['保険料']:>9,}円{mark}")
    _pair = _j["同額の組"][0]
    _lo, _hi = min(_pair["人数"]), max(_pair["人数"])
    _tanka = _j["行"][0]["均等割の単価"]
    print(f"  → **{_lo}人世帯と{_hi}人世帯が、どちらも {_pair['保険料']:,}円。1円も違いません。**"
          f"あいだの {_hi - _lo}人 は、世帯の保険料を1円も増やしていません")
    print(f"    軽減は「割合」で書いてあるので、人数と掛け合わせられます ——"
          f"**実質の頭数 ＝ 被保険者数 × （1 − 軽減の割合）**。"
          f"{_lo}人は軽減 {_pair['軽減の割合'][0]}パーセントで {_lo} × 1.00 = {_pair['実質の頭数']:.1f}、"
          f"{_hi}人は軽減 {_pair['軽減の割合'][1]}パーセントで {_hi} × 0.50 = {_pair['実質の頭数']:.1f}")
    print(f"    そして**所得割は被保険者数で1円も動きません**"
          f"（この所得ならどの人数でも {_j['行'][0]['所得割の合計']:,}円）。"
          f"保険料は **所得割 ＋ 均等割の単価 {_tanka:,}円 × 実質の頭数** なので、"
          f"**実質の頭数が同じなら保険料も同じ**になります")
    print("\n  --- 所得を変えると、並ぶ組そのものが変わります（45歳・12人まで）---")
    for _row in onaji_ryou_table():
        if not _row["同額の組"]:
            print(f"  所得 {_row['所得']:>10,}円  同額の組は無し")
            continue
        for _p in _row["同額の組"]:
            _ms = "人と".join(str(m) for m in _p["人数"]) + "人"
            print(f"  所得 {_row['所得']:>10,}円  **{_ms}** が同額 "
                  f"{_p['保険料']:>9,}円"
                  f"  （実質の頭数 {_p['実質の頭数']:.1f}"
                  f" / 軽減 {_p['軽減の割合'][0]}→{_p['軽減の割合'][1]}パーセント）")
    print(f"    並ぶ比は**軽減の割合の比だけ**で決まります ——"
          f"無軽減 : 2割 ＝ 1 : 1.25、2割 : 5割 ＝ 1 : 1.6、無軽減 : 5割 ＝ 1 : 2。"
          f"**だから並ぶのは (4人, 5人) (5人, 8人) (5人, 10人) のような組だけ**で、"
          f"どれが起きるかは所得が決めます")
    print(f"    **限度額に当たっている人数は外してあります** ——"
          f"そこは頭を切られて同額になるので、実質の頭数の話ではありません")
    print(f"    **この結論も、こちらが置いた前提で決まっています** ——"
          f"所得を世帯主1人がまるごと得ていて、**ふえる人には所得が無い**という置き方です")
