"""後期高齢者医療の保険料。**同じ人に、所得が2つあります。**

75歳になると、それまでの健康保険から後期高齢者医療制度へ移ります。
保険料は「均等割 ＋ 所得割」で、そこまでは国民健康保険と同じ形です。

**違うのは、所得の数え方が2本立てになっていることです。**

- **所得割を計算するとき**は、総所得金額等から **43万円**（基礎控除）を引きます
- **均等割の軽減を判定するとき**は、**43万円を引きません。**
  代わりに、65歳以上の公的年金所得からだけ **15万円**（高齢者特別控除）を引きます

**同じ人の、同じ年金収入から、金額の違う2つの所得が出ます。**
そしてどちらの側にも、相手の控除は1円も入りません。
ここから出てくる、まとめて公表されていない数字:

- **「年金収入168万円までは7割軽減」という、よく出てくる数字の中身**は
  **43万円 ＋ 110万円 ＋ 15万円** の足し算です。43万は軽減の基準額、
  110万は65歳以上の公的年金等控除の下限、**15万が高齢者特別控除**。
  **3つ目を落とすと153万円になり、15万円ぶん低く出ます**
- **年金の人と給与の人で、軽減の境目が15万円ずれます。**
  高齢者特別控除は**公的年金所得にしか掛からない**ので、
  **所得金額がぴったり同じ2人でも、片方だけ軽減が当たる帯があります**
- **本人の所得が0円でも、軽減が1つも当たらないことがあります。**
  軽減の判定は**世帯主の所得も足して**行い、
  **世帯主が被保険者でなくても足されます。** 同居している子が世帯主なら、
  その子の所得で親の均等割が満額になる
- **被扶養者だった人は、3年目に跳ねます。**
  勤めている子の被扶養者だった人は、加入から2年は**均等割5割軽減・所得割ゼロ**。
  2年が過ぎると所得割が丸ごと乗るので、**跳ぶ額は所得に比例して大きくなります**
- **75歳以上の人も、子ども・子育て支援金を払います**（令和8年度に新設）。
  均等割1,300円・所得割0.26パーセント・上限2万1,000円。
  **子どもがいるかどうかも、何歳かも、条件に入っていません**
"""
from __future__ import annotations

import math

from . import _checks

# ---- 制度の値（**軽減の基準と控除は全国一律**）--------------------------
# 均等割の軽減判定の基準額（地方税法703条の5ほか。令和8年度）。
# **国民健康保険と同じ額**です（`src/calc/kokuho.py` と揃っていること）。
KEIGEN_BASE = 430_000
KEIGEN_STEPS: list[tuple[int, int]] = [
    # (軽減の割合パーセント, 被保険者1人あたりの加算額)
    (7 * 10, 0),          # 7割軽減: 43万円以下。**人数によらない**
    (5 * 10, 310_000),    # 5割軽減: 43万円 ＋ 31万円 × 被保険者数
    (2 * 10, 570_000),    # 2割軽減: 43万円 ＋ 57万円 × 被保険者数
]
# 給与所得者・公的年金所得者が2人以上いる世帯への加算（1人あたり10万円、1人目は数えない）
KYUYO_KASAN = 100_000

# **高齢者特別控除。** 軽減の判定にだけ効き、所得割には1円も効きません。
# 65歳以上の公的年金所得からだけ引きます（給与所得には掛かりません）。
KOREISHA_TOKUBETSU = 150_000
KOREISHA_AGE = 65

# 所得割の土台を出すときに引く額（基礎控除。**軽減の判定には入りません**）
KISO_KOJO = 430_000

# 後期高齢者医療の被保険者になる年齢（高齢者医療確保法50条）
KOUKI_AGE = 75

# 被用者保険の被扶養者だった人の軽減（均等割5割・所得割は負担なし）。
# **加入から2年を経過する月まで**なので、3年目から普通の保険料に戻ります。
HIFUYOSHA_KEIGEN_PCT = 50
HIFUYOSHA_YEARS = 2

# ---- 公的年金等控除（65歳以上。公的年金等以外の所得が1,000万円以下）------
# 所得税法35条4項・別表。**下限110万円がそのまま「168万円」の一部になります。**
NENKIN_KOJO_MIN = 1_100_000
NENKIN_KOJO_BANDS: list[tuple[int, float, int]] = [
    # (この収入未満まで, 収入に掛ける率, 足す額)
    (3_300_000,  0.00, 1_100_000),
    (4_100_000,  0.25,   275_000),
    (7_700_000,  0.15,   685_000),
    (10_000_000, 0.05, 1_455_000),
]
NENKIN_KOJO_MAX = 1_955_000     # 収入1,000万円以上は定額

# ---- 率（**ここは広域連合ごとに違います。例として置いています**）--------
# 東京都後期高齢者医療広域連合の令和8・9年度の公表値。
# **この6つだけが全国一律ではありません。**
RATES: dict[str, dict[str, float | int]] = {
    "医療分":             {"所得割": 0.0988, "均等割": 53_300, "限度額": 850_000},
    "子ども子育て支援金分": {"所得割": 0.0026, "均等割":  1_300, "限度額":  21_000},
}
LIMIT_TOTAL = sum(int(r["限度額"]) for r in RATES.values())   # 871,000円

ASSUMPTIONS = [
    "令和8年度の後期高齢者医療の保険料を計算しています。"
    "75歳以上の人、または65歳以上で一定の障害の状態にあると認定された人が対象です",
    "均等割の軽減の判定基準額と、高齢者特別控除15万円、基礎控除43万円は全国一律です。"
    "**均等割の額と所得割の率は広域連合ごとに違います。**"
    "ここでは東京都後期高齢者医療広域連合の令和8・9年度の値として、"
    "医療分の均等割5万3,300円・所得割9.88パーセント・限度額85万円、"
    "子ども・子育て支援金分の均等割1,300円・所得割0.26パーセント・限度額2万1,000円を"
    "置いています。**お住まいの広域連合の値に置き換えてください**",
    "所得割は、総所得金額等から基礎控除43万円を引いた額に掛けています。"
    "**この43万円は、均等割の軽減の判定には入りません**",
    "均等割の軽減の判定は、総所得金額等で行っています。"
    "**65歳以上の公的年金所得からは、さらに高齢者特別控除15万円を引いています。**"
    "この15万円は給与所得には掛かりません",
    "均等割の軽減の判定は、同じ世帯の被保険者全員と世帯主の所得を合計して行っています。"
    "**世帯主が被保険者でない場合も、世帯主の所得は合計に入ります**",
    "軽減の判定基準額は、7割軽減が43万円、5割軽減が43万円に被保険者1人あたり31万円を"
    "足した額、2割軽減が43万円に被保険者1人あたり57万円を足した額としています。"
    "給与所得者・公的年金所得者が2人以上いる世帯には、1人あたり10万円を足しています"
    "（1人目は数えません）",
    "公的年金等控除は、65歳以上で公的年金等以外の所得が1,000万円以下の場合の額を"
    "使っています。収入330万円未満は110万円です",
    "被用者保険の被扶養者だった人の軽減は、均等割5割・所得割は負担なしとし、"
    "加入から2年を経過する月までとしています。"
    "国民健康保険や国民健康保険組合から移った人には、この軽減はかかりません",
    "保険料は年額です。年度の途中で75歳になった場合の月割りは入れていません",
]


# ---- 所得 --------------------------------------------------------------
def nenkin_kojo(shunyu: int) -> int:
    """公的年金等控除（65歳以上）。"""
    for upper, rate, add in NENKIN_KOJO_BANDS:
        if shunyu < upper:
            return round(shunyu * rate) + add
    return NENKIN_KOJO_MAX


def nenkin_shotoku(shunyu: int) -> int:
    """年金収入 → 公的年金等に係る雑所得。"""
    return max(0, shunyu - nenkin_kojo(shunyu))


def futan_no_moto(soshotoku: int) -> int:
    """**所得割の土台**（賦課のもととなる所得）。総所得金額等 − 43万円。"""
    return max(0, soshotoku - KISO_KOJO)


def hantei_shotoku(nenkin: int = 0, kyuyo_shotoku: int = 0,
                   sonota: int = 0, *, age: int = 75) -> int:
    """**軽減の判定に使う所得。** こちらは43万円を引きません。

    引くのは **65歳以上の公的年金所得からの15万円だけ**です
    （`nenkin` は年金収入で受けます）。**給与所得には掛かりません。**
    """
    n = nenkin_shotoku(nenkin)
    if age >= KOREISHA_AGE:
        n = max(0, n - KOREISHA_TOKUBETSU)
    return n + kyuyo_shotoku + sonota


# ---- 軽減 --------------------------------------------------------------
def keigen_threshold(rate_percent: int, members: int = 1,
                     earners: int = 1) -> int:
    """軽減が受けられる、世帯の判定所得の上限。

    **7割の基準額だけ、被保険者数が入りません**（加算が0円）。
    給与・年金所得者の加算は、**7割にも掛かります**（1人目は数えない）。
    """
    kasan = KYUYO_KASAN * max(0, earners - 1)
    for pct, per_head in KEIGEN_STEPS:
        if pct == rate_percent:
            return KEIGEN_BASE + per_head * members + kasan
    raise ValueError(f"知らない軽減の割合: {rate_percent}")


def keigen_rate(hantei: int, members: int = 1, earners: int = 1) -> int:
    """判定所得から、均等割の軽減の割合（パーセント）。**大きいほうから当てます。**"""
    for pct, _per_head in KEIGEN_STEPS:
        if hantei <= keigen_threshold(pct, members, earners):
            return pct
    return 0


def keigen_border_nenkin(rate_percent: int, members: int = 1,
                         earners: int = 1) -> dict:
    """**その軽減が当たる、年金収入の上限。**

    「年金収入168万円までは7割軽減」の **168万円がどこから来るか**を出します。
    判定所得の上限に、**高齢者特別控除15万円**と
    **公的年金等控除110万円**を足し戻したものです。
    """
    limit = keigen_threshold(rate_percent, members, earners)
    # 判定所得 = (年金収入 − 公的年金等控除) − 15万 なので、逆に足し戻す。
    # 収入が330万円未満のあいだは控除が110万円で一定なので、そのまま足せます。
    shunyu = limit + KOREISHA_TOKUBETSU + NENKIN_KOJO_MIN
    return {
        "軽減の割合": rate_percent,
        "被保険者数": members,
        "判定所得の上限": limit,
        "軽減の基準額": KEIGEN_BASE + KEIGEN_STEPS[
            [p for p, _ in KEIGEN_STEPS].index(rate_percent)][1] * members,
        "高齢者特別控除": KOREISHA_TOKUBETSU,
        "公的年金等控除": NENKIN_KOJO_MIN,
        "年金収入の上限": shunyu,
        "15万円を落としたとき": shunyu - KOREISHA_TOKUBETSU,
    }


# ---- 保険料 ------------------------------------------------------------
def part(name: str, soshotoku: int, hantei: int, members: int = 1,
         earners: int = 1, *, hifuyosha: bool = False,
         years_since: int = 0) -> dict:
    """1本ぶんの保険料。**所得割と均等割を出してから、限度額で頭を切ります。**

    被扶養者だった人は、**加入から2年を経過するまで所得割がゼロ**で、
    均等割が5割軽減になります（普通の軽減のほうが厚ければ、厚いほうが当たります）。
    """
    r = RATES[name]
    genmen = hifuyosha and years_since < HIFUYOSHA_YEARS
    shotokuwari = 0 if genmen else round(futan_no_moto(soshotoku) * float(r["所得割"]))
    kintowari_full = int(r["均等割"])
    pct = keigen_rate(hantei, members, earners)
    if genmen:
        pct = max(pct, HIFUYOSHA_KEIGEN_PCT)
    kintowari = round(kintowari_full * (100 - pct) / 100)
    raw = shotokuwari + kintowari
    limit = int(r["限度額"])
    return {
        "区分": name,
        "所得割": shotokuwari,
        "軽減の前の均等割": kintowari_full,
        "軽減の割合": pct,
        "均等割": kintowari,
        "限度額": limit,
        "頭打ちか": raw >= limit,
        "保険料": min(raw, limit),
    }


def premium(nenkin: int = 0, kyuyo_shotoku: int = 0, sonota: int = 0,
            *, members: int = 1, earners: int = 1, setainushi: int = 0,
            hifuyosha: bool = False, years_since: int = 0) -> dict:
    """1人ぶんの後期高齢者医療の保険料（年額）。

    `setainushi` は **被保険者でない世帯主の判定所得**です。
    **軽減の判定にだけ足され、その人の所得割には入りません。**
    """
    soshotoku = nenkin_shotoku(nenkin) + kyuyo_shotoku + sonota
    hantei = hantei_shotoku(nenkin, kyuyo_shotoku, sonota) + setainushi
    rows = [part(n, soshotoku, hantei, members, earners,
                 hifuyosha=hifuyosha, years_since=years_since)
            for n in RATES]
    return {
        "年金収入": nenkin,
        "総所得金額等": soshotoku,
        "所得割の土台": futan_no_moto(soshotoku),
        "判定所得": hantei,
        "軽減の割合": rows[0]["軽減の割合"],
        "内訳": rows,
        "保険料": sum(r["保険料"] for r in rows),
    }


# ---- 主題 --------------------------------------------------------------
def futatsu_no_shotoku(nenkin: int) -> dict:
    """**同じ年金収入から出る、2つの所得。**

    所得割は43万円を引き、軽減の判定は15万円を引く。**互いに相手の控除を持ちません。**
    """
    soshotoku = nenkin_shotoku(nenkin)
    return {
        "年金収入": nenkin,
        "公的年金等控除": nenkin_kojo(nenkin),
        "総所得金額等": soshotoku,
        "所得割の土台": futan_no_moto(soshotoku),
        "軽減の判定に使う所得": hantei_shotoku(nenkin),
        "2つの差": hantei_shotoku(nenkin) - futan_no_moto(soshotoku),
    }


def nenkin_shunyu_from_shotoku(shotoku: int) -> int:
    """年金所得 → その所得になる年金収入（**控除の逆算**）。

    **`+110万円` で足し戻さないこと**（2026-08-17。`check_tables` に止められました）。
    公的年金等控除が110万円で一定なのは**収入330万円未満のあいだだけ**で、
    そこから上は率が入ります。素直に足し戻すと、
    所得300万円の人に**収入410万円**を割り当ててしまい、
    そこでの本当の所得は280万円 —— **20万円ずれます。**
    """
    # 帯ごとに解いてから、丸めのぶんだけ実測で寄せます（`round` が入るため）。
    lo, hi = shotoku, shotoku + NENKIN_KOJO_MAX + 1
    while lo < hi:                      # 二分探索。**単調なので必ず当たります**
        mid = (lo + hi) // 2
        if nenkin_shotoku(mid) < shotoku:
            lo = mid + 1
        else:
            hi = mid
    return lo


def shotokuwari_start() -> dict:
    """**所得割が始まる収入と、7割軽減が終わる収入。その差は15万円ちょうど。**

    所得割は総所得が43万円をこえてから。7割軽減が外れるのは
    **判定所得**が43万円をこえてから ——
    そして判定所得は年金所得から15万円を引いたものです。
    **だから所得割を払っているのに均等割は7割軽減、という帯が15万円ぶんあります。**
    """
    start = KISO_KOJO + NENKIN_KOJO_MIN                  # 所得割が始まる年金収入
    end = keigen_border_nenkin(70, 1)["年金収入の上限"]   # 7割軽減が終わる年金収入
    return {
        "所得割が始まる年金収入": start,
        "7割軽減が終わる年金収入": end,
        "帯の幅": end - start,
        "帯の下端の保険料": premium(nenkin=start + 1)["保険料"],
        "帯の上端の保険料": premium(nenkin=end)["保険料"],
    }


def nenkin_to_kyuyo(shotoku: int, members: int = 1) -> dict:
    """**所得金額が同じ2人で、軽減が違う帯。**

    高齢者特別控除は**公的年金所得にしか掛からない**ので、
    総所得金額等が1円まで同じでも、**年金の人だけ判定所得が15万円低くなります。**
    """
    # 年金の人: この総所得になる年金収入を逆算（**控除が帯で変わるので二分探索**）
    shunyu = nenkin_shunyu_from_shotoku(shotoku)
    n = premium(nenkin=shunyu, members=members)
    k = premium(kyuyo_shotoku=shotoku, members=members)
    return {
        "総所得金額等": shotoku,
        "年金の人の年金収入": shunyu,
        "年金の人の判定所得": n["判定所得"],
        "給与の人の判定所得": k["判定所得"],
        "年金の人の軽減": n["軽減の割合"],
        "給与の人の軽減": k["軽減の割合"],
        "年金の人の保険料": n["保険料"],
        "給与の人の保険料": k["保険料"],
        "差": k["保険料"] - n["保険料"],
    }


def setainushi_eikyou(nenkin: int, setainushi_shotoku: int) -> dict:
    """**本人の所得は1円も変わっていないのに、軽減が消える。**

    判定には**世帯主の所得も足します**。世帯主が被保険者でなくても足されます。
    """
    alone = premium(nenkin=nenkin)
    # 世帯主が別にいると、給与・年金所得者が2人になるので加算10万円も付きます
    with_child = premium(nenkin=nenkin, earners=2, setainushi=setainushi_shotoku)
    return {
        "年金収入": nenkin,
        "世帯主の所得": setainushi_shotoku,
        "1人世帯の判定所得": alone["判定所得"],
        "同居のときの判定所得": with_child["判定所得"],
        "1人世帯の軽減": alone["軽減の割合"],
        "同居のときの軽減": with_child["軽減の割合"],
        "1人世帯の保険料": alone["保険料"],
        "同居のときの保険料": with_child["保険料"],
        "増える額": with_child["保険料"] - alone["保険料"],
    }


def hifuyosha_gake(nenkin: int) -> dict:
    """**被扶養者だった人の、3年目の崖。**

    2年は均等割5割軽減・所得割ゼロ。3年目に**所得割が丸ごと乗ります。**
    """
    before = premium(nenkin=nenkin, hifuyosha=True, years_since=1)
    after = premium(nenkin=nenkin, hifuyosha=True, years_since=HIFUYOSHA_YEARS)
    return {
        "年金収入": nenkin,
        "2年目の保険料": before["保険料"],
        "3年目の保険料": after["保険料"],
        "跳ぶ額": after["保険料"] - before["保険料"],
        "倍率": (after["保険料"] / before["保険料"]) if before["保険料"] else 0.0,
        "2年目の所得割": sum(r["所得割"] for r in before["内訳"]),
        "3年目の所得割": sum(r["所得割"] for r in after["内訳"]),
    }


def hifuyosha_kikime(nenkin: int) -> dict:
    """**被扶養者だった人への軽減が、実際に効いているか。**

    2026-08-17 に `check_tables` に止められて分かったことです。
    「年金収入150万円で3年目に跳ねていない（0 ≦ 0）」——**欠陥ではありませんでした。**

    この措置は2つでできています ——「均等割5割軽減」と「所得割は負担なし」。
    ところが**低い年金収入の人には、どちらも1円も効きません**:

    - **均等割**: 普通の軽減が **7割**なので、**5割のほうが薄い。**
      厚いほうが当たるので、5割軽減は素通りします
    - **所得割**: 総所得が43万円に届かないので、**もともと0円**です

    効きはじめる境目は、**所得割が153万円・均等割が168万円**。
    """
    normal = premium(nenkin=nenkin)
    special = premium(nenkin=nenkin, hifuyosha=True, years_since=0)
    return {
        "年金収入": nenkin,
        "普通の軽減": normal["軽減の割合"],
        "被扶養者のときの軽減": special["軽減の割合"],
        "普通の保険料": normal["保険料"],
        "被扶養者のときの保険料": special["保険料"],
        "安くなる額": normal["保険料"] - special["保険料"],
        "均等割で効いているか": special["軽減の割合"] > normal["軽減の割合"],
        "所得割で効いているか": sum(r["所得割"] for r in normal["内訳"]) > 0,
    }


def hifuyosha_kikime_border() -> dict:
    """**被扶養者の軽減が、実際に効きはじめる年金収入。**

    2つの部品が、**別々の収入から**効きはじめます。
    どちらも「制度の説明に書いてある額」からは出てきません。
    """
    # 所得割: 総所得が43万円をこえてから（＝年金収入153万円をこえてから）
    shotokuwari = KISO_KOJO + NENKIN_KOJO_MIN
    # 均等割: 普通の軽減が5割より薄くなってから（5割どうしでは効かない）
    lo, hi = 0, 10_000_000
    while lo < hi:
        mid = (lo + hi) // 2
        if keigen_rate(hantei_shotoku(nenkin=mid), 1) >= HIFUYOSHA_KEIGEN_PCT:
            lo = mid + 1
        else:
            hi = mid
    return {
        "所得割が効きはじめる年金収入": shotokuwari,
        "均等割が効きはじめる年金収入": lo,
        "7割軽減が終わる年金収入": keigen_border_nenkin(70, 1)["年金収入の上限"],
        "5割軽減が終わる年金収入": keigen_border_nenkin(50, 1)["年金収入の上限"],
        "2つのずれ": lo - shotokuwari,
    }


def cap_at(name: str) -> int:
    """その区分が限度額に届く、いちばん低い総所得金額等。"""
    r = RATES[name]
    need = int(r["限度額"]) - int(r["均等割"])
    if need <= 0:
        return KISO_KOJO
    return KISO_KOJO + math.ceil(need / float(r["所得割"]))


def kodomo_bun(nenkin: int) -> dict:
    """**75歳以上の人が払う、子ども・子育て支援金分。**

    令和8年度に新設されました。**年齢も、子どもがいるかどうかも条件に入っていません。**
    """
    p = premium(nenkin=nenkin)
    kodomo = [r for r in p["内訳"] if r["区分"] == "子ども子育て支援金分"][0]
    iryo = [r for r in p["内訳"] if r["区分"] == "医療分"][0]
    return {
        "年金収入": nenkin,
        "医療分": iryo["保険料"],
        "子ども子育て支援金分": kodomo["保険料"],
        "保険料に占める割合": (kodomo["保険料"] / p["保険料"] * 100)
        if p["保険料"] else 0.0,
        "子ども分の上限": int(RATES["子ども子育て支援金分"]["限度額"]),
        "子ども分が上限に届く総所得": cap_at("子ども子育て支援金分"),
        "医療分が上限に届く総所得": cap_at("医療分"),
    }


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値（**全国一律の側**）
    _checks.statutory(KEIGEN_BASE, 430_000, "軽減判定の基準額",
                      source="地方税法703条の5。国民健康保険と同額")
    _checks.statutory(KOREISHA_TOKUBETSU, 150_000, "高齢者特別控除",
                      source="高齢者医療確保法施行令。軽減の判定にだけ効く")
    _checks.statutory(KISO_KOJO, 430_000, "所得割の土台を出すときに引く額",
                      source="高齢者医療確保法施行令。住民税の基礎控除と同額")
    _checks.statutory(KOREISHA_AGE, 65, "高齢者特別控除がかかる年齢",
                      source="65歳以上の公的年金等控除を受けている人")
    _checks.statutory(KOUKI_AGE, 75, "後期高齢者医療の被保険者になる年齢",
                      source="高齢者医療確保法50条")
    _checks.statutory(NENKIN_KOJO_MIN, 1_100_000, "65歳以上の公的年金等控除の下限",
                      source="所得税法35条4項")
    _checks.statutory(HIFUYOSHA_KEIGEN_PCT, 50, "被扶養者だった人の均等割の軽減",
                      source="加入から2年を経過する月まで")
    _checks.statutory(HIFUYOSHA_YEARS, 2, "被扶養者だった人の軽減が続く年数",
                      source="高齢者医療確保法施行令")
    _checks.statutory(LIMIT_TOTAL, 871_000, "賦課限度額の合計",
                      source="医療分85万円 ＋ 子ども・子育て支援金分2万1,000円")
    for name, r in RATES.items():
        _checks.ratio(float(r["所得割"]), f"{name}の所得割の率")

    # 2. 表の形
    _checks.unique_by(KEIGEN_STEPS, lambda r: r[0], "軽減の割合")
    _checks.unique_by(list(RATES), lambda r: r, "保険料の区分")
    _checks.ascending([p for _pct, p in KEIGEN_STEPS], "軽減の基準額の加算",
                      strict=False)
    _checks.ascending([u for u, _r, _a in NENKIN_KOJO_BANDS],
                      "公的年金等控除の帯の上限", strict=True)
    # 公的年金等控除は、収入が増えて減らないこと（帯の継ぎ目で跳ねないこと）
    _checks.never_decreases(nenkin_kojo,
                            (0, 1_000_000, 3_299_999, 3_300_000, 4_099_999,
                             4_100_000, 7_699_999, 7_700_000, 9_999_999,
                             10_000_000, 20_000_000),
                            "収入が増えたのに公的年金等控除が減っている")
    # 年金所得も、収入が増えて減らないこと
    _checks.never_decreases(nenkin_shotoku,
                            (0, 1_100_000, 3_300_000, 4_100_000, 7_700_000,
                             10_000_000, 20_000_000),
                            "年金収入が増えたのに年金所得が減っている")
    # 収入110万円までは所得0円（下限がそのまま効く）
    _checks.rounding(nenkin_shotoku(NENKIN_KOJO_MIN), 0,
                     "年金収入110万円の年金所得")
    # **逆算が本当に逆になっていること**（往復で確かめる。帯をまたいで見ること）
    for shotoku in (100_000, 500_000, 2_199_999, 2_200_000, 2_500_000,
                    2_800_000, 3_000_000, 5_000_000, 5_860_000, 6_000_000,
                    8_045_000, 9_000_000):
        got = nenkin_shotoku(nenkin_shunyu_from_shotoku(shotoku))
        if got != shotoku:
            raise _checks.TableError(
                f"年金所得{shotoku:,}円の逆算が往復しない（{got:,}円 に戻った）")
    # **素直な足し戻しでは合わないこと**を、ここで固定します（この節の主題）。
    # 330万円の帯をこえると、`+110万円` は必ずずれます。
    if nenkin_shotoku(3_000_000 + NENKIN_KOJO_MIN) == 3_000_000:
        raise _checks.TableError(
            "収入330万円をこえた帯で、+110万円の足し戻しが成り立ってしまっている")

    # 3. **主題その1**: 168万円は3つの足し算
    b = keigen_border_nenkin(70, 1)
    _checks.rounding(b["年金収入の上限"], 1_680_000, "7割軽減が当たる年金収入の上限")
    _checks.rounding(b["軽減の基準額"] + b["高齢者特別控除"] + b["公的年金等控除"],
                     1_680_000, "43万＋15万＋110万の合計")
    # **15万円を落とすと153万円**（ここがこの節の主題）
    _checks.rounding(b["15万円を落としたとき"], 1_530_000,
                     "高齢者特別控除を落としたときの境目")
    # 逆算が本当に境目になっていること —— そのちょうどでは当たり、1円こえると外れる
    for pct in (70, 50, 20):
        row = keigen_border_nenkin(pct, 1)
        edge = row["年金収入の上限"]
        if keigen_rate(hantei_shotoku(nenkin=edge), 1) < pct:
            raise _checks.TableError(
                f"年金収入{edge:,}円で{pct}割軽減が当たっていない")
        if keigen_rate(hantei_shotoku(nenkin=edge + 1), 1) >= pct:
            raise _checks.TableError(
                f"年金収入{edge:,}円を1円こえても{pct}割軽減が残っている")
    # 境目は軽減が薄くなるほど高いこと
    _checks.ascending([keigen_border_nenkin(p, 1)["年金収入の上限"]
                       for p in (70, 50, 20)], "軽減の境目（年金収入）", strict=True)

    # 4. **主題その2**: 所得割と軽減判定で、控除が別々に効く
    for shunyu in (1_500_000, 2_000_000, 3_000_000):
        f = futatsu_no_shotoku(shunyu)
        # 判定のほうは43万円を引いていないので、**必ず所得割の土台より大きい**
        _checks.greater(f["軽減の判定に使う所得"], f["所得割の土台"],
                        f"年金収入{shunyu:,}円で、判定所得が所得割の土台より大きくない")
    # 差がちょうど 43万 − 15万 = 28万円 になるのは、**所得割の土台が床（0円）から
    # 離れてから**です。ここは書いたとき 150万円 も一緒に回そうとして、
    # **`check_tables` に止められました**（150万円では 25万円）。
    # 総所得が43万円に届かないあいだ、土台は0で止まっているので差が縮みます。
    for shunyu in (2_000_000, 3_000_000):
        f = futatsu_no_shotoku(shunyu)
        _checks.rounding(f["2つの差"], KISO_KOJO - KOREISHA_TOKUBETSU,
                         f"年金収入{shunyu:,}円での2つの所得の差")
    # **主題その2の裏側**: 所得割が始まる収入と、7割軽減が終わる収入の差は、
    # **ちょうど高齢者特別控除の15万円**（同じ15万円が別の場所にもう一度出ます）
    g = shotokuwari_start()
    _checks.rounding(g["所得割が始まる年金収入"], 1_530_000,
                     "所得割が1円でもかかりはじめる年金収入")
    _checks.rounding(g["7割軽減が終わる年金収入"], 1_680_000,
                     "7割軽減が当たる年金収入の上限")
    _checks.rounding(g["帯の幅"], KOREISHA_TOKUBETSU,
                     "所得割は払うのに7割軽減が当たる帯の幅")

    # 5. **主題その3**: 同じ所得金額でも、年金の人と給与の人で軽減が違う帯がある
    # 給与の人が5割から外れ、年金の人はまだ5割に当たる帯（境目の直上15万円）
    edge = keigen_threshold(50, 1)
    hit = nenkin_to_kyuyo(edge + 10_000)
    if hit["年金の人の軽減"] <= hit["給与の人の軽減"]:
        raise _checks.TableError(
            "同じ所得で、年金の人のほうが軽減が厚くなっていない")
    _checks.greater(hit["差"], 0, "同じ所得なのに保険料の差が出ていない")
    # 差が出るのは15万円ぶんの帯だけ。**十分に低い所得と高い所得では同じになること**
    same_low = nenkin_to_kyuyo(200_000)
    if same_low["年金の人の軽減"] != same_low["給与の人の軽減"]:
        raise _checks.TableError("どちらも7割に当たる帯で、軽減が食い違っている")
    same_high = nenkin_to_kyuyo(3_000_000)
    if same_high["年金の人の軽減"] != same_high["給与の人の軽減"]:
        raise _checks.TableError("どちらも軽減が無い帯で、軽減が食い違っている")
    # 判定所得の差は、必ず15万円ちょうど（所得が15万円以上あるとき）
    for shotoku in (500_000, 1_000_000, 3_000_000):
        r = nenkin_to_kyuyo(shotoku)
        _checks.rounding(r["給与の人の判定所得"] - r["年金の人の判定所得"],
                         KOREISHA_TOKUBETSU,
                         f"所得{shotoku:,}円での判定所得の差")

    # 6. **主題その4**: 世帯主の所得で、本人の軽減が消える
    s = setainushi_eikyou(1_500_000, 4_000_000)
    _checks.greater(s["増える額"], 0, "世帯主の所得が入っても保険料が増えていない")
    if s["同居のときの軽減"] >= s["1人世帯の軽減"]:
        raise _checks.TableError("世帯主の所得が入ったのに軽減が薄くなっていない")
    # **本人の所得割は1円も変わらないこと**（変わるのは均等割だけ）
    alone = premium(nenkin=1_500_000)
    together = premium(nenkin=1_500_000, earners=2, setainushi=4_000_000)
    if (sum(r["所得割"] for r in alone["内訳"])
            != sum(r["所得割"] for r in together["内訳"])):
        raise _checks.TableError("世帯主の所得が、本人の所得割に入ってしまっている")
    # 世帯主の所得が増えるほど、軽減は薄くなる（保険料は減らない）
    _checks.never_decreases(
        lambda x: setainushi_eikyou(1_500_000, x)["同居のときの保険料"],
        (0, 500_000, 1_000_000, 2_000_000, 5_000_000),
        "世帯主の所得が増えたのに保険料が減っている")

    # 7. **主題その5**: 被扶養者だった人の3年目の崖
    # **150万円を入れて止められました**（`hifuyosha_kikime`）。所得割の土台が0なので、
    # 崖そのものが立ちません。**欠陥ではなく、これがこの節の結果**です。
    for shunyu in (2_500_000, 4_000_000):
        g = hifuyosha_gake(shunyu)
        _checks.greater(g["跳ぶ額"], 0, f"年金収入{shunyu:,}円で3年目に跳ねていない")
        if g["2年目の所得割"] != 0:
            raise _checks.TableError("2年目に所得割がかかっている（負担なしのはず）")
        _checks.greater(g["3年目の所得割"], 0, "3年目に所得割が乗っていない")
    # **跳ぶ額は所得とともに大きくなる**（所得割が丸ごと乗るため）
    _checks.increases_with(lambda x: hifuyosha_gake(x)["跳ぶ額"],
                           (2_000_000, 2_500_000, 3_000_000, 3_500_000),
                           "年金収入が高いほうで、3年目の崖が大きくなっていない")

    # 7.5 **主題その5の裏側**: その軽減は、低い年金収入の人には1円も効いていない
    # 所得割が始まるのが153万円、7割軽減が5割軽減に負けなくなるのが168万円
    low = hifuyosha_kikime(1_500_000)
    if low["安くなる額"] != 0:
        raise _checks.TableError(
            f"年金収入150万円で、被扶養者の軽減が {low['安くなる額']:,}円 効いている"
            "（7割軽減のほうが厚く、所得割も0円のはず）")
    if low["均等割で効いているか"] or low["所得割で効いているか"]:
        raise _checks.TableError("年金収入150万円で、被扶養者の軽減が効いてしまっている")
    # **7割が外れても、まだ効きません**（ここで2回目に止められました）。
    # 外れた先が**5割**なので、被扶養者の5割と同じ厚さで、差が出ないためです。
    # 効きはじめるのは**普通の軽減が5割より薄くなってから** ＝ 199万円をこえてから。
    bd = hifuyosha_kikime_border()
    _checks.rounding(bd["所得割が効きはじめる年金収入"], 1_530_000,
                     "被扶養者の軽減のうち、所得割が効きはじめる年金収入")
    _checks.rounding(bd["均等割が効きはじめる年金収入"], 1_990_001,
                     "被扶養者の軽減のうち、均等割が効きはじめる年金収入")
    # **7割が外れる168万円でも、5割が外れる199万円でもない**のが主題です
    if bd["均等割が効きはじめる年金収入"] <= bd["7割軽減が終わる年金収入"]:
        raise _checks.TableError("7割軽減が終わる前に、均等割の側が効いてしまっている")
    for shunyu in (1_500_000, 1_680_000, 1_700_000, 1_990_000):
        k = hifuyosha_kikime(shunyu)
        if k["均等割で効いているか"]:
            raise _checks.TableError(
                f"年金収入{shunyu:,}円で、被扶養者の5割軽減が効いてしまっている")
    over = hifuyosha_kikime(bd["均等割が効きはじめる年金収入"])
    if not over["均等割で効いているか"]:
        raise _checks.TableError("境目の1円上でも、被扶養者の5割軽減が効いていない")
    _checks.greater(over["安くなる額"], 0,
                    "境目をこえた帯で、被扶養者の軽減が1円も効いていない")

    # 8. **主題その6**: 子ども・子育て支援金分は75歳以上にもかかる
    k = kodomo_bun(2_000_000)
    _checks.greater(k["子ども子育て支援金分"], 0,
                    "75歳の人に子ども・子育て支援金分がかかっていない")
    # 医療分のほうが必ず重い（率も上限も一桁以上ちがう）
    _checks.greater(k["医療分"], k["子ども子育て支援金分"],
                    "子ども分のほうが医療分より重くなっている")
    # 上限に届く所得は、子ども分のほうが先（上限 ÷ 率が小さい）
    if cap_at("子ども子育て支援金分") >= cap_at("医療分"):
        raise _checks.TableError("子ども分が医療分より後に頭打ちになっている")

    # 9. 単調性と上限
    _checks.never_decreases(lambda x: premium(nenkin=x)["保険料"],
                            (0, 1_100_000, 1_680_000, 2_000_000, 5_000_000,
                             10_000_000, 30_000_000),
                            "年金収入が増えたのに保険料が減っている")
    for shunyu in (20_000_000, 100_000_000):
        got = premium(nenkin=shunyu)["保険料"]
        if got > LIMIT_TOTAL:
            raise _checks.TableError(
                f"年金収入{shunyu:,}円の保険料 {got:,}円 が限度額を超えている")
    # 7割軽減の基準額だけ、被保険者数で動かないこと
    for members in (1, 2, 3):
        _checks.rounding(keigen_threshold(70, members), KEIGEN_BASE,
                         f"被保険者{members}人の7割軽減の基準額")

    _checks.assumption_values(ASSUMPTIONS, name="kouki")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 「年金収入168万円まで7割軽減」の中身は、3つの足し算 ===")
    for pct in (70, 50, 20):
        b = keigen_border_nenkin(pct, 1)
        print(f"  {pct // 10}割軽減  基準額 {b['軽減の基準額']:>9,}円"
              f"  ＋ 高齢者特別控除 {b['高齢者特別控除']:>7,}円"
              f"  ＋ 公的年金等控除 {b['公的年金等控除']:>9,}円"
              f"  → **年金収入 {b['年金収入の上限']:>9,}円 まで**")
    b = keigen_border_nenkin(70, 1)
    print(f"  → よく出てくる **168万円** は、43万円と110万円だけでは出ません"
          f"（{b['15万円を落としたとき']:,}円 にしかならない）。"
          f"**高齢者特別控除15万円が3つ目の部品**です")

    print("\n=== 同じ年金収入から、金額の違う所得が2つ出る ===")
    for shunyu in (1_500_000, 1_800_000, 2_400_000, 3_000_000):
        f = futatsu_no_shotoku(shunyu)
        print(f"  年金収入 {shunyu:>9,}円"
              f"  → 総所得 {f['総所得金額等']:>9,}円"
              f"  ／ 所得割の土台 {f['所得割の土台']:>9,}円"
              f"  ／ 軽減の判定 {f['軽減の判定に使う所得']:>9,}円"
              f"  （差 {f['2つの差']:>7,}円）")
    print(f"  → 差はいつでも **{KISO_KOJO - KOREISHA_TOKUBETSU:,}円**"
          f"（43万円 − 15万円）。**所得割は43万円を引き、軽減の判定は15万円を引く**ので、"
          f"どちらの側にも相手の控除が入りません")

    print("\n=== 所得割は払うのに、均等割は7割軽減。その帯の幅は15万円ちょうど ===")
    g = shotokuwari_start()
    print(f"  所得割が1円でもかかりはじめる年金収入  {g['所得割が始まる年金収入']:>9,}円"
          f"  （43万円 ＋ 110万円）")
    print(f"  7割軽減が当たる年金収入の上限          {g['7割軽減が終わる年金収入']:>9,}円"
          f"  （43万円 ＋ 110万円 ＋ **15万円**）")
    print(f"  → **同じ15万円が、別の場所にもう一度出ます。**"
          f"この {g['帯の幅']:,}円 ぶんの帯にいる人は、"
          f"**所得割を払いながら均等割は7割軽減**です")

    print("\n=== 総所得が1円まで同じでも、年金の人だけ軽減が当たる帯がある ===")
    edge = keigen_threshold(50, 1)
    for shotoku in (edge - 50_000, edge + 10_000, edge + 100_000,
                    edge + 200_000):
        r = nenkin_to_kyuyo(shotoku)
        print(f"  総所得 {shotoku:>9,}円"
              f"  → 年金の人 判定 {r['年金の人の判定所得']:>9,}円・軽減{r['年金の人の軽減'] // 10}割"
              f"  {r['年金の人の保険料']:>8,}円"
              f"  ／ 給与の人 判定 {r['給与の人の判定所得']:>9,}円・軽減{r['給与の人の軽減'] // 10}割"
              f"  {r['給与の人の保険料']:>8,}円"
              f"  → **差 {r['差']:>7,}円**")
    print("  → 高齢者特別控除15万円は**公的年金所得にしか掛かりません**。"
          "だから所得金額が同じでも、境目のすぐ上の15万円ぶんの帯では軽減が食い違います")

    print("\n=== 本人の所得は1円も変わらないのに、同居の世帯主の所得で軽減が消える"
          "（本人は年金収入 1,500,000円）===")
    for setai in (0, 1_000_000, 2_000_000, 4_000_000, 8_000_000):
        s = setainushi_eikyou(1_500_000, setai)
        print(f"  世帯主の所得 {setai:>9,}円"
              f"  → 判定所得 {s['同居のときの判定所得']:>9,}円"
              f"  軽減 {s['同居のときの軽減'] // 10}割"
              f"  保険料 {s['同居のときの保険料']:>8,}円"
              f"  （1人世帯なら {s['1人世帯の保険料']:>8,}円"
              f" ／ **+{s['増える額']:>7,}円**）")
    print("  → 判定には**世帯主の所得も足します**。**世帯主が被保険者でなくても足されます。**"
          "本人の所得割は1円も変わりません。動くのは均等割だけです")

    print("\n=== 被扶養者だった人は、3年目に跳ねる ===")
    for shunyu in (1_500_000, 2_000_000, 2_500_000, 3_000_000, 4_000_000):
        g = hifuyosha_gake(shunyu)
        print(f"  年金収入 {shunyu:>9,}円"
              f"  2年目 {g['2年目の保険料']:>8,}円"
              f"  → 3年目 {g['3年目の保険料']:>8,}円"
              f"  **{g['倍率']:>5.2f}倍・+{g['跳ぶ額']:>8,}円**"
              f"  （乗る所得割 {g['3年目の所得割']:>8,}円）")
    print("  → 2年は**均等割5割軽減・所得割ゼロ**。3年目に所得割が丸ごと乗るので、"
          "**所得が高い人ほど崖が高くなります**")

    print("\n=== その「被扶養者だった人への軽減」は、低い年金収入の人に1円も効かない ===")
    bd = hifuyosha_kikime_border()
    for shunyu in (1_500_000, 1_680_000, 1_990_000,
                   bd["均等割が効きはじめる年金収入"], 2_500_000):
        k = hifuyosha_kikime(shunyu)
        print(f"  年金収入 {shunyu:>9,}円"
              f"  普通の軽減 {k['普通の軽減'] // 10}割"
              f"  ／ 被扶養者のとき {k['被扶養者のときの軽減'] // 10}割"
              f"  → **安くなる額 {k['安くなる額']:>8,}円**"
              f"  （均等割で効く {'はい' if k['均等割で効いているか'] else 'いいえ'}"
              f" ／ 所得割で効く {'はい' if k['所得割で効いているか'] else 'いいえ'}）")
    print(f"  → 措置は2つ（均等割5割軽減・所得割ゼロ）で、**効きはじめる収入が別々**です ——"
          f"所得割は {bd['所得割が効きはじめる年金収入']:,}円 から、"
          f"均等割は **{bd['均等割が効きはじめる年金収入']:,}円** から")
    print(f"    均等割の側は、**7割軽減が終わる {bd['7割軽減が終わる年金収入']:,}円 でもまだ効きません。**"
          f"外れた先が**5割**で、被扶養者の5割と同じ厚さだからです。"
          f"効くのは**5割も外れてから**（{bd['5割軽減が終わる年金収入']:,}円 の1円上）")

    print("\n=== 75歳以上の人も、子ども・子育て支援金を払う（令和8年度に新設）===")
    for shunyu in (1_680_000, 2_400_000, 4_000_000, 8_000_000):
        k = kodomo_bun(shunyu)
        print(f"  年金収入 {shunyu:>9,}円"
              f"  医療分 {k['医療分']:>8,}円"
              f"  ／ 子ども・子育て支援金分 {k['子ども子育て支援金分']:>7,}円"
              f"  （保険料の {k['保険料に占める割合']:>4.1f}パーセント）")
    k = kodomo_bun(2_400_000)
    print(f"  → **年齢も、子どもがいるかどうかも条件に入っていません。**"
          f"上限は {k['子ども分の上限']:,}円 で、総所得 {k['子ども分が上限に届く総所得']:,}円 で頭打ち。"
          f"医療分（{k['医療分が上限に届く総所得']:,}円）より**先に止まります**")
