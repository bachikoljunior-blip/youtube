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
- **40歳の誕生日で介護分が乗ります。** 39歳と40歳で、同じ所得・同じ世帯なのに
  保険料が変わる。**乗る額は所得によらず一定ではありません** ——
  介護分にも所得割があるので、所得とともに増え、17万円で止まります
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


def part(name: str, shotoku: int, members: int, *, keigen: bool = True) -> dict:
    """1本ぶんの保険料。**所得割と均等割を出してから、限度額で頭を切ります。**

    軽減は**均等割にだけ**掛かります（所得割は軽減されません）。
    """
    r = RATES[name]
    shotokuwari = round(kyu_tadashigaki(shotoku) * float(r["所得割"]))
    kintowari_full = int(r["均等割"]) * members
    pct = keigen_rate(shotoku, members) if keigen else 0
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
            *, keigen: bool = True) -> dict:
    """世帯の国民健康保険料。"""
    rows = [part(n, shotoku, members, keigen=keigen) for n in parts_for(age)]
    return {
        "所得": shotoku,
        "被保険者数": members,
        "年齢": age,
        "内訳": rows,
        "軽減の割合": keigen_rate(shotoku, members) if keigen else 0,
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
            "落ちる軽減": f"{before}割 → {after}割" if after else f"{before}割 → なし",
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
                    f"被保険者{members}人・所得{edge:,}円で{pct}割軽減が当たらない")
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
