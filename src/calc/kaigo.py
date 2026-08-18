"""介護保険の自己負担。**「1割負担」も「上限44,400円」も、そのままでは働きません。**

高額介護サービス費の上限は、**保険が効いた分の自己負担にしか掛かりません。**
区分支給限度基準額を超えて使った分は保険給付ではないので、10割で払ったうえに
**上限の計算にも入りません。** 一般の解説は「上限は月44,400円」と表を写すところで
止まり、**その上限に誰が届くのかを言いません。**

そこから出てくる、公表されていない数字:

- **1割負担では、どの要介護度でも一般区分の44,400円に届きません。**
  上限に届くには保険内で 44,400単位 使う必要がありますが、
  いちばん重い要介護5でも限度額は **36,217単位**。**8,183単位 足りない。**
  足りない分を使っても、それは限度額の外なので10割で払うだけで、
  **上限の計算には入りません。構造として届かない**
- 上限が効き始めるのは、**2割負担で要介護3、3割負担で要介護1**。
  同じ「上限44,400円」が、負担割合で効き始める段を変えます
- **要介護3以上では、2割の人と3割の人が完全に同額**（どちらも44,400円）。
  要介護5では、3割の人は1割の人の **1.23倍**しか払いません
- **限度額を1割こえるだけで、1割負担の人の支払いは2.00倍**（27,048円 → 54,098円）。
  超過分は割合によらず10割なので、**負担割合が軽い人ほど跳ねます**
  （超過率 p に対して 1 ＋ p ÷ 負担割合。3割の人は同じ1割超過で1.30倍）
- **上限は世帯にひとつ。** 要介護5・1割が2人いる世帯では、
  2人目の実質負担は **8,183円**（1人目の22.6%）。
  **1人では1円も効かない上限が、2人目から初めて効きます**
- 「要介護度が1段上がる」の意味は段によって違い、限度額の増え方は
  要介護1→2 の **29,400円** から 要介護2→3 の **73,430円** まで **2.5倍**ひらきます
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値 ----------------------------------------------------------
# 区分支給限度基準額（1か月あたりの単位数。介護保険法43条・施行規則。
# 2019年10月の改定以降、動いていない）
LIMIT_UNITS: list[tuple[str, int]] = [
    ("要支援1", 5_032),
    ("要支援2", 10_531),
    ("要介護1", 16_765),
    ("要介護2", 19_705),
    ("要介護3", 27_048),
    ("要介護4", 30_938),
    ("要介護5", 36_217),
]

UNIT_YEN = 10           # 1単位の単価。地域区分「その他」の値（10.00〜11.40円）
OVER_RATE = 1.0         # 限度額を超えた分の負担割合。**保険が使えないので10割**

# 自己負担の割合（介護保険法49条の2・59条の2）
COPAY_RATES: list[tuple[float, str, str]] = [
    (0.1, "1割", "一般"),
    (0.2, "2割", "合計所得金額160万円以上など"),
    (0.3, "3割", "合計所得金額220万円以上など"),
]

# 高額介護サービス費の負担上限額（1か月・世帯。2021年8月から動いていない）
CAPS: list[tuple[str, int]] = [
    ("課税所得690万円以上", 140_100),
    ("課税所得380万円以上690万円未満", 93_000),
    ("課税所得145万円以上380万円未満", 44_400),
    ("住民税課税（一般）", 44_400),
    ("住民税非課税の世帯", 24_600),
]
GENERAL_CAP = 44_400    # 一般区分の上限。この表の主役

ASSUMPTIONS = [
    "1単位の単価は10円として計算しています。地域区分とサービスの種類で"
    "10円から11円40銭まで変わります",
    "区分支給限度基準額は1か月あたりの単位数で、要介護5で36,217単位です。"
    "訪問介護や通所介護など、限度額の対象になるサービスだけの合計です",
    "福祉用具の購入費、住宅改修費、施設に入ったときの居住費と食費は入れていません。"
    "これらは限度額の外です",
    "高額介護サービス費の上限は世帯ごとに1か月単位でかかるものとしています。"
    "一般区分は44,400円です",
    "限度額を超えて使った分は保険が使えないので、割合は10割としています。"
    "この分は高額介護サービス費の計算にも入りません",
    "自己負担の割合は所得で1割・2割・3割に分かれます。ここでは割合そのものを"
    "与えて計算しています",
]


def limit_units(level: str) -> int:
    for name, units in LIMIT_UNITS:
        if name == level:
            return units
    raise ValueError(f"知らない要介護度: {level}")


def limit_yen(level: str) -> int:
    """その要介護度で、保険を使って組めるサービスの上限（円）。"""
    return limit_units(level) * UNIT_YEN


def level_steps() -> list[dict]:
    """要介護度が1段上がると、限度額はいくら増えるか。**段によって幅が違う。**"""
    rows = [{"要介護度": name, "限度額の単位": units, "限度額": units * UNIT_YEN}
            for name, units in LIMIT_UNITS]
    prev = None
    for row in rows:
        row["1段あたりの増え方"] = None if prev is None else row["限度額"] - prev
        prev = row["限度額"]
    return rows


def pay(level: str, used_units: int, rate: float, cap: int = GENERAL_CAP) -> dict:
    """1か月に実際に払う額。

    保険の効く分（限度額まで）は `rate` 割。**超えた分は10割**で、
    しかも**高額介護サービス費の上限の計算に入りません**（保険給付ではないため）。
    """
    limit = limit_units(level)
    inside = min(used_units, limit) * UNIT_YEN
    outside = max(0, used_units - limit) * UNIT_YEN
    inside_pay = inside * rate
    capped = min(inside_pay, cap)
    return {
        "要介護度": level,
        "使った単位": used_units,
        "限度額の単位": limit,
        "保険が効く分": round(inside),
        "限度額を超えた分": round(outside),
        "保険内の自己負担": round(inside_pay),
        "上限で戻る額": round(inside_pay - capped),
        "上限を当てたあと": round(capped),
        "超過分（10割）": round(outside * OVER_RATE),
        "1か月に払う額": round(capped + outside * OVER_RATE),
        "使ったサービスの総額": round(inside + outside),
        "実効の負担率": (capped + outside * OVER_RATE) / (inside + outside) * 100,
    }


def cap_reach_units(rate: float, cap: int = GENERAL_CAP) -> float:
    """**上限にちょうど届く、保険内の単位数。**

    上限は「保険内の自己負担」にしか掛からないので、
    `cap ÷ (単価 × 負担割合)` 単位ぶん使って、はじめて届きます。
    限度額を超えて使っても、超過分は10割で払うだけで**この計算には入りません。**
    """
    return cap / (UNIT_YEN * rate)


def cap_bites(rate: float, cap: int = GENERAL_CAP) -> list[dict]:
    """負担割合ごとに、**上限が効き始める要介護度**。"""
    need = cap_reach_units(rate, cap)
    rows = []
    for name, units in LIMIT_UNITS:
        rows.append({
            "要介護度": name,
            "限度額の単位": units,
            "上限に届く単位": round(need),
            "限度額いっぱいの自己負担": round(units * UNIT_YEN * rate),
            "上限が効くか": units >= need,
            "足りない単位": max(0, round(need - units)),
        })
    return rows


def first_biting_level(rate: float, cap: int = GENERAL_CAP) -> str | None:
    """上限が効き始める最初の要介護度。**効く段が無ければ None。**"""
    for row in cap_bites(rate, cap):
        if row["上限が効くか"]:
            return row["要介護度"]
    return None


def rate_compare(level: str, cap: int = GENERAL_CAP) -> list[dict]:
    """同じ使い方（限度額いっぱい）で、負担割合だけを変える。

    **上限があるので、3割は1割の3倍にはなりません。**
    """
    base = pay(level, limit_units(level), COPAY_RATES[0][0], cap)["1か月に払う額"]
    rows = []
    for rate, label, who in COPAY_RATES:
        p = pay(level, limit_units(level), rate, cap)
        rows.append({
            "負担割合": label,
            "割合の数字": rate,
            "だれが": who,
            "上限が無ければ": round(limit_yen(level) * rate),
            "1か月に払う額": p["1か月に払う額"],
            "1割の人の何倍": p["1か月に払う額"] / base,
        })
    return rows


def over_limit_curve(level: str, rate: float, overs: list[float],
                     cap: int = GENERAL_CAP) -> list[dict]:
    """限度額を何パーセント超えると、支払いは何倍になるか。

    超過分は10割なので、**負担割合が軽い人ほど倍率が跳ねます**
    （超過率 p に対して 1 + p ÷ 負担割合）。
    """
    limit = limit_units(level)
    # **上限を当てたあとの額**を基準にすること。
    # `限度額 × 負担割合` を基準にすると、上限に当たっている人（2割・3割）で
    # 「限度内なら」の見出しが実際の支払いと食い違います
    base = pay(level, limit, rate, cap)["1か月に払う額"]
    rows = []
    for over in overs:
        used = round(limit * (1 + over))
        p = pay(level, used, rate, cap)
        rows.append({
            "超過率": over * 100,
            "使った単位": used,
            "1か月に払う額": p["1か月に払う額"],
            "限度内で止めた場合": base,
            "ふえる額": p["1か月に払う額"] - base,
            "何倍になるか": p["1か月に払う額"] / base,
            "実効の負担率": p["実効の負担率"],
        })
    return rows


def household(level: str, people: int, rate: float,
              cap: int = GENERAL_CAP) -> dict:
    """世帯に要介護の人が何人いるか。**上限は世帯にひとつ。**"""
    each = limit_yen(level) * rate
    total = each * people
    capped = min(total, cap)
    return {
        "要介護度": level,
        "人数": people,
        "1人あたりの自己負担": round(each),
        "上限が無ければ": round(total),
        "世帯で払う額": round(capped),
        "戻る額": round(total - capped),
        "2人目以降の実質負担": round(capped - each) if people > 1 else 0,
        "1人目に対する割合": ((capped - each) / each * 100) if people > 1 else 0.0,
    }



def level_spread(rate: float, cap: int = GENERAL_CAP) -> dict:
    """限度額いっぱいに使ったとき、**7段の支払いがどれだけ開くか**。

    限度額そのものは 要支援1 → 要介護5 で **7.20倍**に開きます。
    ところが上限は**上の段にしか当たらない**ので、割合が重いほど
    上が先に頭打ちになり、**開きは縮みます**（1割 7.20倍・3割 2.94倍）。
    同じことを実効の負担率の側から見ると、**「3割負担」の人が実際に払う
    割合は、段が上がるほど下がります**（30.0% → 12.26%）。
    """
    rows = []
    for name, units in LIMIT_UNITS:
        p = pay(name, units, rate, cap)
        rows.append({
            "要介護度": name,
            "限度額": units * UNIT_YEN,
            "上限が無ければ": round(units * UNIT_YEN * rate),
            "1か月に払う額": p["1か月に払う額"],
            "実効の負担率": p["実効の負担率"],
        })
    lo = rows[0]["1か月に払う額"]
    hi = rows[-1]["1か月に払う額"]
    for row in rows:
        row["いちばん低い段の何倍"] = row["1か月に払う額"] / lo
    return {
        "負担割合": rate,
        "行": rows,
        "いちばん低い段": rows[0]["要介護度"],
        "いちばん高い段": rows[-1]["要介護度"],
        "倍率": hi / lo,
        "限度額の倍率": rows[-1]["限度額"] / rows[0]["限度額"],
        "同額で並ぶ段": [r["要介護度"] for r in rows
                         if r["1か月に払う額"] == hi],
    }


def cap_class_bites(rate: float) -> list[dict]:
    """上限の**区分**（`CAPS`）を変えると、上限が効き始める段が動く。

    表の主役は一般区分の44,400円ですが、上限は所得で5段あり、
    いちばん低い**住民税非課税の世帯（24,600円）は1割負担でも効きます**。
    逆にいちばん高い**課税所得690万円以上（140,100円）は、3割負担でも
    どの要介護度にも当たりません**（届くのに46,700単位が要り、
    限度額の最大 36,217単位を超えているため）。
    """
    rows = []
    for name, cap in CAPS:
        need = cap_reach_units(rate, cap)
        first = first_biting_level(rate, cap)
        rows.append({
            "上限の区分": name,
            "上限": cap,
            "上限に届く単位": need,
            "効き始める要介護度": first,
            "どこにも効かない": first is None,
            "いちばん高い段でも足りない単位":
                max(0, round(need - LIMIT_UNITS[-1][1])),
        })
    return rows

def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(limit_units("要介護5"), 36_217, "要介護5の区分支給限度基準額",
                      source="介護保険法施行規則（2019年10月改定）")
    _checks.statutory(limit_units("要支援1"), 5_032, "要支援1の区分支給限度基準額",
                      source="介護保険法施行規則（2019年10月改定）")
    _checks.statutory(GENERAL_CAP, 44_400, "高額介護サービス費の一般区分の上限",
                      source="介護保険法施行令22条の2の2（2021年8月から）")
    _checks.statutory(UNIT_YEN, 10, "1単位の単価（地域区分その他）",
                      source="厚生労働省告示・地域区分")
    for rate, _label, _who in COPAY_RATES:
        _checks.ratio(rate, "自己負担の割合")
    # OVER_RATE は 1.0（10割）なので `ratio` には掛けない。
    # あれは 0 と 1 のあいだを要求するので、**「保険が効かない」という
    # この表の主題そのものが桁の取り違えとして落ちます。**
    if OVER_RATE != 1.0:
        raise _checks.TableError(
            "限度額を超えた分は保険が使えないので10割のはず")

    # 2. 表の形
    _checks.ascending([u for _n, u in LIMIT_UNITS], "区分支給限度基準額", strict=True)
    _checks.ascending([c for _n, c in CAPS][::-1], "高額介護サービス費の上限")
    _checks.unique_by(LIMIT_UNITS, lambda r: r[0], "区分支給限度基準額の要介護度")

    # 3. 見出しが「1段あたり」と言っているので、実際に1段で割れること
    rows = level_steps()
    for i, row in enumerate(rows):
        if i == 0:
            if row["1段あたりの増え方"] is not None:
                raise _checks.TableError("先頭の行に前の段が無いのに差が入っている")
            continue
        want = row["限度額"] - rows[i - 1]["限度額"]
        _checks.rounding(row["1段あたりの増え方"], want,
                         f"{row['要介護度']}の1段あたりの増え方")

    # 4. **主題その1**: 上限は保険内の自己負担にしか掛からない。
    #    1割負担では、どの要介護度でも一般区分の44,400円に届かない
    if first_biting_level(0.1) is not None:
        raise _checks.TableError(
            "1割負担で一般区分の上限に届く要介護度が出た。"
            "限度額の最大（要介護5）でも 36,217円 のはず")
    _checks.rounding(cap_reach_units(0.1), 44_400, "1割で上限に届く単位数")
    _checks.rounding(cap_reach_units(0.2), 22_200, "2割で上限に届く単位数")
    _checks.rounding(cap_reach_units(0.3), 14_800, "3割で上限に届く単位数")
    if first_biting_level(0.2) != "要介護3":
        raise _checks.TableError("2割で上限が効き始めるのは要介護3のはず")
    if first_biting_level(0.3) != "要介護1":
        raise _checks.TableError("3割で上限が効き始めるのは要介護1のはず")

    # 5. **主題その2**: 上限があるので、3割は1割の3倍にならない。
    #    上限が効いている段では、2割と3割が同額になる
    for level in ("要介護3", "要介護4", "要介護5"):
        rows = rate_compare(level)
        two = [r for r in rows if r["割合の数字"] == 0.2][0]
        three = [r for r in rows if r["割合の数字"] == 0.3][0]
        if two["1か月に払う額"] != three["1か月に払う額"]:
            raise _checks.TableError(
                f"{level}: 2割と3割がどちらも上限に当たっているのに額が違う")
        if three["1割の人の何倍"] >= 3.0:
            raise _checks.TableError(f"{level}: 上限があるのに3割が1割の3倍以上")
    _checks.rounding(rate_compare("要介護5")[2]["1割の人の何倍"],
                     44_400 / 36_217, "要介護5で3割の人が1割の人の何倍払うか")

    # 6. **主題その3**: 超過分は10割。倍率の式は、**上限に当たっているかで変わる**
    #    （ここを分けずに「1 + 超過率 ÷ 負担割合」だけを書くと、
    #     2割・3割で外れます。上限に当たった時点で分母が固定されるため）
    limit3 = limit_units("要介護3")
    for rate, _label, _who in COPAY_RATES:
        base = pay("要介護3", limit3, rate)["1か月に払う額"]
        for extra in (1_000, 3_000, 8_000):
            got = pay("要介護3", limit3 + extra, rate)["1か月に払う額"] / base
            if limit3 * UNIT_YEN * rate <= GENERAL_CAP:
                want = 1 + (extra / limit3) / rate      # 上限に当たっていない
            else:
                want = 1 + extra * UNIT_YEN / GENERAL_CAP  # 上限で分母が固定
            # **`rounding` を使わないこと。** あれは丸めの順番を見る道具で、
            # ここは式どうしの一致（差は 1e-15）なので、桁の話ではありません
            if abs(got - want) > 1e-9:
                raise _checks.TableError(
                    f"負担割合{rate}・超過{extra}単位のときの倍率: "
                    f"{got} になった。{want} のはず")
    _checks.increases_with(
        lambda e: pay("要介護3", limit3 + e, 0.1)["1か月に払う額"],
        (0, 1_000, 5_000, 13_000), "限度額を超えて使ったのに支払いが増えていない")
    # 上限に当たっていない1割の人がいちばん激しく跳ねる。
    # 2割と3割は**どちらも上限で頭打ち**なので同じ倍率になる
    jump = {r: pay("要介護3", round(limit3 * 1.2), r)["1か月に払う額"]
               / pay("要介護3", limit3, r)["1か月に払う額"]
            for r, _lb, _w in COPAY_RATES}
    _checks.greater(jump[0.1], jump[0.2],
                    "1割の人の跳ね方が2割の人以下（超過分は割合によらず10割のはず）")
    if abs(jump[0.2] - jump[0.3]) > 1e-9:
        raise _checks.TableError("要介護3で2割と3割の跳ね方が違う（どちらも上限のはず）")

    # 7. **主題その4**: 世帯の2人目から上限が効く（1人では効かない段でも）
    one = household("要介護5", 1, 0.1)
    two = household("要介護5", 2, 0.1)
    if one["戻る額"] != 0:
        raise _checks.TableError("1割・単身なのに高額介護サービス費が出ている")
    _checks.greater(two["戻る額"], 0,
                    "1割・2人世帯で戻る額が出ていない（上限は世帯にひとつ）")
    _checks.greater(one["1人あたりの自己負担"], two["2人目以降の実質負担"],
                    "2人目の実質負担が1人目と同じかそれ以上")

    # 8. 実効の負担率は、限度額を境に上がる（負担割合より重くなる）
    _checks.greater(pay("要介護3", round(limit_units("要介護3") * 1.5), 0.1)["実効の負担率"],
                    10.0, "限度額の1.5倍まで使ったのに実効の負担率が1割のまま")


    # 9. **主題その5**: 上限は上の段にしか当たらないので、
    #    負担割合が重いほど「7段の開き」は縮む
    spreads = {r: level_spread(r) for r, _lb, _w in COPAY_RATES}
    _checks.rounding(spreads[0.1]["限度額の倍率"], 36_217 / 5_032,
                     "限度額の 要支援1 → 要介護5 の倍率")
    if abs(spreads[0.1]["倍率"] - spreads[0.1]["限度額の倍率"]) > 1e-9:
        raise _checks.TableError(
            "1割では上限がどこにも効かないので、支払いの倍率は"
            "限度額の倍率と同じはず")
    if not (spreads[0.1]["倍率"] > spreads[0.2]["倍率"] > spreads[0.3]["倍率"]):
        raise _checks.TableError(
            "負担割合が重いほど開きが縮んでいない（上限は上の段にしか当たらない）")
    # **上が同じ44,400円で止まっているので、2割と3割の倍率の比は
    #   下の端の比＝負担割合の比そのもの（ちょうど1.5倍）になります。**
    if abs(spreads[0.2]["倍率"] / spreads[0.3]["倍率"] - 0.3 / 0.2) > 1e-9:
        raise _checks.TableError(
            "2割と3割の倍率の比が、負担割合の比（1.5倍）と違う")
    # 同額で並ぶ段の数：1割は0段（上限が効かないので最上段だけ）
    if len(spreads[0.1]["同額で並ぶ段"]) != 1:
        raise _checks.TableError("1割で上限に当たっている段がある")
    if spreads[0.2]["同額で並ぶ段"] != ["要介護3", "要介護4", "要介護5"]:
        raise _checks.TableError("2割で同額に並ぶのは要介護3以上のはず")
    if spreads[0.3]["同額で並ぶ段"] != ["要介護1", "要介護2", "要介護3",
                                        "要介護4", "要介護5"]:
        raise _checks.TableError("3割で同額に並ぶのは要介護1以上のはず")
    # 実効の負担率は、上限に当たった段から**下がっていく**
    eff = [row["実効の負担率"] for row in spreads[0.3]["行"]]
    _checks.rounding(eff[0], 30.0, "3割・要支援1の実効の負担率")
    if not all(a >= b for a, b in zip(eff, eff[1:])):
        raise _checks.TableError(
            "3割の実効の負担率が段の上で上がっている（上限があるので下がるはず）")
    _checks.greater(eff[0] - eff[-1], 15.0,
                    "3割の実効の負担率が、7段で15ポイントも下がっていない")

    # 10. **主題その6**: 上限の区分を変えると、効き始める段が動く。
    #     一般区分だけを見ていると「1割には効かない」で終わる
    # **区分の名前で引くこと。**額で引くと、額を壊した検査が
    # `IndexError` で落ちて「制度の値が違う」と言えなくなります
    _checks.statutory(dict(CAPS)["住民税非課税の世帯"], 24_600,
                      "高額介護サービス費の上限（住民税非課税の世帯）",
                      source="介護保険法施行令22条の2の2（2021年8月から）")
    _checks.statutory(dict(CAPS)["課税所得690万円以上"], 140_100,
                      "高額介護サービス費の上限（課税所得690万円以上）",
                      source="介護保険法施行令22条の2の2（2021年8月から）")
    by_class = {r["上限の区分"]: r for r in cap_class_bites(0.1)}
    low = by_class["住民税非課税の世帯"]
    if low["効き始める要介護度"] != "要介護3":
        raise _checks.TableError(
            "住民税非課税の世帯（24,600円）は、1割負担でも要介護3から"
            "上限が効くはず")
    _checks.rounding(low["上限に届く単位"], 24_600, "1割・非課税世帯で上限に届く単位数")
    high = {r["上限の区分"]: r
            for r in cap_class_bites(0.3)}["課税所得690万円以上"]
    if not high["どこにも効かない"]:
        raise _checks.TableError(
            "課税所得690万円以上（140,100円）は、3割負担でも"
            "どの要介護度にも当たらないはず")
    _checks.greater(high["いちばん高い段でも足りない単位"], 0,
                    "140,100円の上限に、要介護5の限度額で届いてしまっている")

    _checks.assumption_values(ASSUMPTIONS, name="kaigo")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 「要介護度が1段上がる」の意味は、段によって2倍以上ちがう ===")
    for row in level_steps():
        step = row["1段あたりの増え方"]
        print(f"  {row['要介護度']}  {row['限度額の単位']:>7,}単位"
              f"  限度額 {row['限度額']:>9,}円"
              f"  1段あたりの増え方 "
              f"{('—' if step is None else format(step, ',') + '円'):>10}")

    print("\n=== 一般区分の上限44,400円は、1割負担ではどの要介護度でも効かない ===")
    for rate, label, who in COPAY_RATES:
        need = cap_reach_units(rate)
        first = first_biting_level(rate)
        print(f"  {label}負担（{who}）  上限に届くのに要る保険内の単位 "
              f"{need:>8,.0f}単位"
              f"  効き始めるのは {first or '**どの要介護度でも効かない**'}")
    top = cap_bites(0.1)[-1]
    print(f"  → 1割の人は、限度額いっぱいの要介護5でも自己負担は "
          f"{top['限度額いっぱいの自己負担']:,}円。"
          f"上限まで {GENERAL_CAP - top['限度額いっぱいの自己負担']:,}円 足りません")
    print(f"    足りない分を使おうとしても、それは限度額の外なので"
          f"10割で払うだけで、上限の計算には入りません")

    print("\n=== 上限があるので、3割負担は1割負担の3倍にならない（限度額いっぱいまで使った月）===")
    for level in ("要介護1", "要介護2", "要介護3", "要介護5"):
        print(f"  {level}（限度額 {limit_yen(level):,}円）")
        for row in rate_compare(level):
            print(f"    {row['負担割合']}負担  上限が無ければ "
                  f"{row['上限が無ければ']:>8,}円"
                  f"  → 実際は {row['1か月に払う額']:>8,}円"
                  f"  1割の人の {row['1割の人の何倍']:>4.2f}倍")

    print("\n=== 限度額を超えた分は10割。**負担割合が軽い人ほど跳ねる**（要介護3）===")
    for rate, label, _who in COPAY_RATES:
        inside = pay("要介護3", limit_units("要介護3"), rate)["1か月に払う額"]
        print(f"  {label}負担（限度内で止めれば {inside:,}円）")
        for row in over_limit_curve("要介護3", rate, [0.05, 0.1, 0.2, 0.5]):
            print(f"    限度額を {row['超過率']:>4.0f}% こえる"
                  f"  → {row['1か月に払う額']:>8,}円"
                  f"（+{row['ふえる額']:>7,}円・{row['何倍になるか']:>4.2f}倍）"
                  f"  実効 {row['実効の負担率']:>5.2f}%")

    print("\n=== 上限は世帯にひとつ。**2人目から初めて効く**（要介護5・1割）===")
    for people in (1, 2, 3):
        h = household("要介護5", people, 0.1)
        print(f"  {h['人数']}人  上限が無ければ {h['上限が無ければ']:>8,}円"
              f"  → 世帯で払う {h['世帯で払う額']:>8,}円"
              f"  戻る {h['戻る額']:>8,}円"
              f"  2人目以降の実質負担 {h['2人目以降の実質負担']:>8,}円"
              f"（1人目の {h['1人目に対する割合']:>5.1f}%）")

    print("\n=== 7段の開きは、負担割合が重いほど縮む（1割 7.20倍 → 3割 2.94倍）===")
    for rate, label, _who in COPAY_RATES:
        sp = level_spread(rate)
        print(f"  {label}負担  {sp['いちばん低い段']} → {sp['いちばん高い段']} で "
              f"**{sp['倍率']:.2f}倍**"
              f"（限度額そのものは {sp['限度額の倍率']:.2f}倍）"
              f"  同額で並ぶ段 {len(sp['同額で並ぶ段'])}個")
        for row in sp["行"]:
            print(f"    {row['要介護度']}  限度額 {row['限度額']:>9,}円"
                  f"  上限が無ければ {row['上限が無ければ']:>8,}円"
                  f"  → 実際は {row['1か月に払う額']:>8,}円"
                  f"  {row['いちばん低い段の何倍']:>5.2f}倍"
                  f"  実効 {row['実効の負担率']:>5.2f}%")
    print(f"  → 上が同じ {GENERAL_CAP:,}円 で止まるので、"
          f"2割と3割の倍率の比は下の端の比＝負担割合の比そのもの（1.50倍）です")

    print("\n=== 上限の区分を変えると、効き始める段が動く"
          "（非課税世帯は1割でも効き、690万円以上は3割でも効かない）===")
    for rate, label, _who in COPAY_RATES:
        print(f"  {label}負担")
        for row in cap_class_bites(rate):
            where = ("**どの要介護度でも効かない**"
                     f"（あと {row['いちばん高い段でも足りない単位']:,}単位）"
                     if row["どこにも効かない"] else
                     f"{row['効き始める要介護度']} から")
            print(f"    上限 {row['上限']:>7,}円（{row['上限の区分']}）"
                  f"  届くのに {row['上限に届く単位']:>8,.0f}単位"
                  f"  → {where}")
