"""障害年金。**「1級は2級の1.25倍」は、受け取る額では成り立ちません。**

障害年金は2階建てです。障害基礎年金（国民年金）と、
厚生年金に入っていた人だけの障害厚生年金が重なります。

制度の説明でいちばんよく出てくるのは **「1級は2級の1.25倍」** です。
この 1.25 は本当ですが、**掛かる先が全部ではありません。**

- 1.25倍されるのは **障害基礎年金の本体** と **障害厚生年金の報酬比例部分**だけ
- **子の加算も、配偶者加給年金も、1.25倍されません**（定額のまま乗ります）

だから **受け取る合計では、倍率は必ず 1.25 を下回ります。**
そして下がり方は、**その人の家族の人数と報酬の大きさで変わります** ——
制度の説明のどこにも載っていない数字です。ここから出てくるもの:

- **家族が多い人ほど、1級と2級の差は小さくなります。**
  加算は定額なので、分母だけが太る。**等級が上がっても、増える割合は薄まります**
- **3級には障害基礎年金がありません。** 配偶者加給も付きません。
  だから **2級と3級の差は「1階ぶん」まるごと**で、
  **家族の人数が、等級の崖の高さを決めます**（等級の判定に家族は入らないのに）
- **障害手当金（一時金）と3級は、どんな報酬でもちょうど2年で並びます。**
  手当金は報酬比例の2倍、最低保障も3級の最低保障のちょうど2倍なので、
  **報酬の大きさが約分で消えます。** 3級が2年より長く続くなら3級のほうが多い
- **20歳前の傷病でもらう障害基礎年金には所得の制限があり、崖が2つあります。**
  1円こえると半分止まり、もう1つこえると全部止まります
- **300月みなしがあるので、若くして重い障害を負った人ほど、
  1か月あたりの報酬比例が大きく出ます**（実際に働いた月数では割りません）
- **3級の最低保障と障害手当金の最低保障は、同じ1円で同時に外れます。**
  300月なら平均標準報酬額 372,195円。手当金の最低保障は3級の最低保障の
  ちょうど2倍で、計算どおりの額も報酬比例のちょうど2倍なので、
  **2倍どうしが約分で消えて、線が1本になります**
- **2級と3級の崖は、その線から上では1円も動きません。**
  上では同じ報酬比例が両方に乗るので、差は「1階ぶん」で頭打ちです。
  **線より下では3級だけが止まっている**ので、報酬が増えるほど崖は開きます
- **20歳前傷病の所得制限では、線を動かすのは扶養親族、崖を高くするのは子**です。
  同じ子が両方に数えられるので、1人増えると線は380,000円 上がり、
  崖は117,400円 高くなります。**第3子からは崖の伸びだけが落ちます**
"""
from __future__ import annotations

from . import _checks

# ---- 制度の値（令和6年度・新規裁定の額）--------------------------------
# `src/calc/izoku.py` の 816,000円 と同じ年度で揃えています。
BASIC_FULL = 816_000            # 障害基礎年金2級の額（＝老齢基礎年金の満額。国民年金法33条）
GRADE1_RATE = 1.25              # 1級は2級の1.25倍（国民年金法33条2項・厚生年金保険法50条2項）

CHILD_ADD_1_2 = 234_800         # 子の加算。第1子・第2子（国民年金法33条の2）
CHILD_ADD_3_ON = 78_300         # 子の加算。第3子以降
SPOUSE_ADD = 234_800            # 配偶者加給年金（厚生年金保険法50条の2。**1級と2級だけ**）

# 障害厚生年金3級の最低保障額。**障害基礎年金2級の4分の3**です。
GRADE3_MIN = 612_000
GRADE3_MIN_RATE = 3 / 4

# 障害手当金は報酬比例の2倍の一時金。最低保障も3級の最低保障の2倍です。
TEATE_MULTIPLE = 2

MIN_MONTHS = 300                # 300月みなし（厚生年金保険法51条）
ACCRUAL = 5.481 / 1000          # 報酬比例の給付乗率（平成15年4月以降の期間）

CHILD_END_AGE = 18              # 子の要件は18歳到達年度の3月31日まで

# ---- 20歳前傷病による障害基礎年金の所得制限（国民年金法36条の3）---------
# **扶養親族がいない人の所得額**です。扶養親族1人につき38万円ずつ上がります。
ZENGAKU_TEISHI = 4_721_000      # これをこえると全部停止
HANGAKU_TEISHI = 3_704_000      # これをこえると2分の1停止
FUYO_KASAN = 380_000            # 扶養親族1人あたりの加算

ASSUMPTIONS = [
    "障害基礎年金2級の額は年816,000円、1級はその1.25倍の年1,020,000円として"
    "計算しています。令和6年度の新規裁定の額です",
    "子の加算は第1子と第2子が各234,800円、第3子以降が各78,300円です。"
    "**子の加算は1.25倍されません**（1級でも2級でも同じ額です）",
    "配偶者加給年金は年234,800円で、障害厚生年金の1級と2級にだけ付きます。"
    "**3級には付きません。**こちらも1.25倍されません",
    "障害厚生年金の報酬比例部分は、平均標準報酬額に1000分の5.481を掛け、"
    "被保険者期間の月数を掛けて出しています。"
    "平成15年4月より前の期間がある人は、別の乗率が混ざります",
    "被保険者期間が300月に足りないときは300月として計算しています"
    "（厚生年金保険法51条）",
    "障害厚生年金3級の最低保障額は年612,000円としています。"
    "障害基礎年金2級の4分の3です",
    "障害手当金は報酬比例部分の2倍の一時金で、最低保障は1,224,000円"
    "（3級の最低保障の2倍）としています",
    "20歳前の傷病による障害基礎年金の所得制限は、扶養親族がいない人で、"
    "所得が3,704,000円をこえると2分の1停止、4,721,000円をこえると全部停止として"
    "計算しています。扶養親族1人につき38万円ずつ上がります",
    "子は18歳到達年度の3月31日までを対象にしています。"
    "障害のある子は20歳までですが、ここには入れていません",
    "初診日の要件・保険料の納付要件は満たしているものとしています",
    "傷病手当金と並べる計算では、同一の傷病で両方の受給権があるものとしています。"
    "別の傷病なら調整はありません",
    "傷病手当金と並べる計算では、健康保険の標準報酬月額と、厚生年金の平均標準報酬額を"
    "同じ額に置いています。前者は直近12か月の平均、後者は生涯の平均で賞与も入り"
    "再評価もされるので、実際は一致しません。賞与のある人は平均標準報酬額のほうが"
    "大きくなり、年金が増えるぶん傷病手当金はもっと減ります。"
    "この計算が出しているのは、減り方のいちばん小さい形です",
    "傷病手当金の日額は、標準報酬月額を30で割って10円未満を四捨五入し、"
    "3分の2をかけて1円未満を四捨五入したものです（健康保険法99条）",
    "傷病手当金と調整される年金の1日ぶんは、年金額を360で割って"
    "1円未満を四捨五入したものです（健康保険法108条4項）",
    "傷病手当金と並べる表は、標準報酬月額を58,000円から650,000円まで"
    "1,000円きざみで動かしています。650,000円は厚生年金の上限等級で、"
    "健康保険の等級はその上にもありますが、そこでは年金の側が増えません",
    "障害手当金と傷病手当金の計算では、傷病手当金の日額が支給期間を通じて"
    "変わらないものとしています（健康保険法108条5項）",
]


# ---- 部品 --------------------------------------------------------------
def grade_rate(grade: int) -> float:
    """等級 → 本体に掛かる倍率。**1級だけ1.25倍。3級は本体がありません。**"""
    if grade == 1:
        return GRADE1_RATE
    if grade in (2, 3):
        return 1.0
    raise ValueError(f"知らない等級: {grade}")


def child_add(children: int) -> int:
    """子の加算の合計。**等級で変わりません**（1級でも2級でも同じ額）。"""
    if children <= 0:
        return 0
    first = min(children, 2) * CHILD_ADD_1_2
    return first + max(0, children - 2) * CHILD_ADD_3_ON


def kiso(grade: int, children: int = 0) -> dict:
    """障害基礎年金。**3級にはありません**（1階が丸ごと無い）。"""
    if grade == 3:
        return {"本体": 0, "子の加算": 0, "合計": 0}
    honntai = round(BASIC_FULL * grade_rate(grade))
    add = child_add(children)
    return {"本体": honntai, "子の加算": add, "合計": honntai + add}


def houshu_hirei(hyoujun: int, months: int) -> int:
    """報酬比例部分。**300月に足りなければ300月で計算します。**"""
    m = max(months, MIN_MONTHS)
    return round(hyoujun * ACCRUAL * m)


def kousei(grade: int, hyoujun: int, months: int, *,
           spouse: bool = False) -> dict:
    """障害厚生年金。**配偶者加給は1級と2級だけ**で、1.25倍されません。"""
    base = round(houshu_hirei(hyoujun, months) * grade_rate(grade))
    if grade == 3:
        base = max(base, GRADE3_MIN)          # 3級だけ最低保障がある
        kakyu = 0
    else:
        kakyu = SPOUSE_ADD if spouse else 0
    return {"報酬比例": base, "配偶者加給": kakyu, "合計": base + kakyu,
            "最低保障が効いたか": grade == 3 and base == GRADE3_MIN}


def nenkin(grade: int, hyoujun: int = 0, months: int = 0, *,
           children: int = 0, spouse: bool = False,
           kousei_kanyu: bool = True) -> dict:
    """1年ぶんの障害年金（年額）。"""
    k = kiso(grade, children)
    ko = (kousei(grade, hyoujun, months, spouse=spouse)
          if kousei_kanyu else {"報酬比例": 0, "配偶者加給": 0, "合計": 0,
                                "最低保障が効いたか": False})
    return {
        "等級": grade,
        "障害基礎年金": k["合計"],
        "基礎の本体": k["本体"],
        "子の加算": k["子の加算"],
        "障害厚生年金": ko["合計"],
        "報酬比例": ko["報酬比例"],
        "配偶者加給": ko["配偶者加給"],
        "合計": k["合計"] + ko["合計"],
    }


# ---- 主題1: 1.25倍が掛からない部分 -------------------------------------
def baisuu(hyoujun: int, months: int, *, children: int = 0,
           spouse: bool = False) -> dict:
    """**1級 ÷ 2級の、本当の倍率。**

    1.25倍されるのは基礎の本体と報酬比例だけで、
    **子の加算と配偶者加給は定額のまま**乗ります。
    だから合計の倍率は**必ず1.25を下回り**、加算が厚い人ほど下がります。
    """
    g1 = nenkin(1, hyoujun, months, children=children, spouse=spouse)
    g2 = nenkin(2, hyoujun, months, children=children, spouse=spouse)
    teigaku = g2["子の加算"] + g2["配偶者加給"]
    return {
        "子の人数": children,
        "配偶者": spouse,
        "2級の合計": g2["合計"],
        "1級の合計": g1["合計"],
        "差": g1["合計"] - g2["合計"],
        "本当の倍率": g1["合計"] / g2["合計"] if g2["合計"] else 0.0,
        "1.25倍されない額": teigaku,
        "1.25倍からの目減り": GRADE1_RATE - (g1["合計"] / g2["合計"]
                                            if g2["合計"] else 0.0),
    }


def baisuu_saitei() -> dict:
    """**倍率がいちばん低くなる形はどれか。**

    定額の加算だけが分母を太らせるので、**加算の割合が最大のとき**に底を打ちます。
    報酬比例が0（厚生年金に入っていない人）で、子が多いときです。
    """
    rows = []
    for children in range(0, 5):
        r = baisuu(0, 0, children=children, spouse=False)
        r["厚生年金"] = False
        rows.append(r)
    low = min(rows, key=lambda r: r["本当の倍率"])
    return {"行": rows, "いちばん低い倍率": low["本当の倍率"],
            "そのときの子の人数": low["子の人数"]}


# ---- 主題2: 2級と3級の崖 -----------------------------------------------
def gake_2_3(hyoujun: int, months: int, *, children: int = 0,
             spouse: bool = False) -> dict:
    """**2級と3級の差は「1階ぶん」まるごと。**

    3級には障害基礎年金がなく、配偶者加給も付きません。
    **等級の判定に家族の人数は入らないのに、崖の高さは家族で決まります。**
    """
    g2 = nenkin(2, hyoujun, months, children=children, spouse=spouse)
    g3 = nenkin(3, hyoujun, months, children=children, spouse=spouse)
    return {
        "子の人数": children,
        "配偶者": spouse,
        "3級の合計": g3["合計"],
        "2級の合計": g2["合計"],
        "差": g2["合計"] - g3["合計"],
        "倍率": g2["合計"] / g3["合計"] if g3["合計"] else 0.0,
        "消える基礎年金": g2["障害基礎年金"],
        "消える配偶者加給": g2["配偶者加給"],
    }


# ---- 主題3: 障害手当金と3級が並ぶ年数 ----------------------------------
def teatekin(hyoujun: int, months: int) -> dict:
    """障害手当金（一時金）。**報酬比例の2倍**、最低保障は3級の最低保障の2倍。"""
    hirei = houshu_hirei(hyoujun, months)
    raw = hirei * TEATE_MULTIPLE
    floor = GRADE3_MIN * TEATE_MULTIPLE
    return {"報酬比例": hirei, "計算どおりの額": raw,
            "最低保障": floor, "手当金": max(raw, floor)}


def narabu_toshi(hyoujun: int, months: int) -> dict:
    """**障害手当金と3級が並ぶまでの年数。**

    3級は年額 `max(報酬比例, 612,000)`、手当金は一時金 `max(報酬比例, 612,000) × 2`。
    **どちらも同じものの2倍**なので、**報酬の大きさが約分で消えます。**
    だから **誰でもちょうど2年**です。
    """
    t = teatekin(hyoujun, months)
    y3 = nenkin(3, hyoujun, months)["合計"]
    return {
        "平均標準報酬額": hyoujun,
        "3級の年額": y3,
        "障害手当金": t["手当金"],
        "並ぶ年数": t["手当金"] / y3 if y3 else 0.0,
        "3年受けたときの差": y3 * 3 - t["手当金"],
        "10年受けたときの差": y3 * 10 - t["手当金"],
    }


# ---- 主題4: 300月みなし ------------------------------------------------
def minashi(hyoujun: int, months: int, *, grade: int = 2) -> dict:
    """**実際に働いた月数では割りません。**

    300月に足りない人は300月として計算するので、
    **加入が短いほど「1か月あたり」が大きく出ます。**
    """
    real = round(hyoujun * ACCRUAL * months)
    mitomeru = houshu_hirei(hyoujun, months)
    return {
        "実際の月数": months,
        "計算に使う月数": max(months, MIN_MONTHS),
        "実際の月数どおりの報酬比例": real,
        "みなしを入れた報酬比例": mitomeru,
        "増える額": mitomeru - real,
        "倍率": mitomeru / real if real else 0.0,
        "年金の合計": nenkin(grade, hyoujun, months)["合計"],
    }


def minashi_moto_ga_toru() -> int:
    """みなしが効かなくなる月数（＝300月ちょうど）。"""
    return MIN_MONTHS


# ---- 主題5: 20歳前傷病の所得制限 ---------------------------------------
def teishi_line(fuyo: int = 0) -> dict:
    """扶養親族の人数に応じた、2つの停止の線。"""
    return {
        "扶養親族": fuyo,
        "半額停止の線": HANGAKU_TEISHI + FUYO_KASAN * fuyo,
        "全額停止の線": ZENGAKU_TEISHI + FUYO_KASAN * fuyo,
    }


def hatachi_mae(shotoku: int, grade: int = 2, *, children: int = 0,
                fuyo: int = 0) -> dict:
    """**20歳前の傷病でもらう障害基礎年金の、2つの崖。**

    止まるのは**基礎年金の全部**（子の加算も一緒に止まります）。
    """
    line = teishi_line(fuyo)
    full = kiso(grade, children)["合計"]
    if shotoku > line["全額停止の線"]:
        rate, name = 0.0, "全部停止"
    elif shotoku > line["半額停止の線"]:
        rate, name = 0.5, "2分の1停止"
    else:
        rate, name = 1.0, "全額もらえる"
    return {
        "所得": shotoku,
        "止まり方": name,
        "止まらずに受け取れる年金": round(full * rate),
        "止まる額": full - round(full * rate),
        "半額停止の線": line["半額停止の線"],
        "全額停止の線": line["全額停止の線"],
        "所得と年金の合計": shotoku + round(full * rate),
    }


def hatachi_mae_gake(grade: int = 2, children: int = 0, fuyo: int = 0) -> dict:
    """**1円こえたときに、いくら減るか。** 崖は2つあります。"""
    line = teishi_line(fuyo)
    rows = []
    for base in (line["半額停止の線"], line["全額停止の線"]):
        before = hatachi_mae(base, grade, children=children, fuyo=fuyo)
        after = hatachi_mae(base + 1, grade, children=children, fuyo=fuyo)
        rows.append({
            "線": base,
            "こえる前の合計": before["所得と年金の合計"],
            "こえた後の合計": after["所得と年金の合計"],
            "減る額": before["所得と年金の合計"] - after["所得と年金の合計"],
            "取り返すのに要る所得": (before["所得と年金の合計"]
                                    - after["所得と年金の合計"]),
        })
    return {"崖": rows, "子の人数": children, "扶養親族": fuyo}


# ---- 主題7: 最低保障が外れる平均標準報酬額 ------------------------------
#
# **3級の最低保障（612,000円）と障害手当金の最低保障（1,224,000円）は、
# 同じ1点で同時に外れます。** 手当金の最低保障は3級の最低保障のちょうど2倍で、
# 計算どおりの額も報酬比例のちょうど2倍だからです（`narabu_toshi` が
# 「誰でも2年」になるのと、同じ約分）。**線は2本ではなく1本です。**
def saitei_hoshou_line(months: int = MIN_MONTHS) -> dict:
    """**最低保障が外れる、いちばん低い平均標準報酬額。**

    報酬比例 ＝ 平均標準報酬額 × 1000分の5.481 × 月数 が
    3級の最低保障 612,000円 に届く点を、1円きざみで探します。
    **月数が長い人ほど、この線は低くなります**（同じ報酬でも報酬比例が太るため）。
    """
    m = max(months, MIN_MONTHS)
    lo = round(GRADE3_MIN / (ACCRUAL * m))          # 端数のぶん前後するので
    while lo > 0 and houshu_hirei(lo, m) >= GRADE3_MIN:   # 下へ落として
        lo -= 1
    while houshu_hirei(lo, m) < GRADE3_MIN:               # 上へ戻す（＝最小の点）
        lo += 1
    return {
        "計算に使う月数": m,
        "線": lo,
        "線での報酬比例": houshu_hirei(lo, m),
        "線での3級の年額": nenkin(3, lo, m)["合計"],
        "線での障害手当金": teatekin(lo, m)["手当金"],
        "1円下の報酬比例": houshu_hirei(lo - 1, m),
        "1円下の3級の年額": nenkin(3, lo - 1, m)["合計"],
        "1円下の障害手当金": teatekin(lo - 1, m)["手当金"],
    }


def saitei_ga_kiku(hyoujun: int, months: int = MIN_MONTHS) -> bool:
    """**最低保障が「額を持ち上げている」か。**

    `kousei()` の印は `max()` の等号を含むので、**ちょうど線の上の人まで
    「効いている」**と答えます。表で帯を分けるときに要るのは
    **1円でも足されたか**のほうなので、こちらを使います。
    """
    return houshu_hirei(hyoujun, max(months, MIN_MONTHS)) < GRADE3_MIN


def saitei_hoshou_tsuki(months: int = MIN_MONTHS) -> list[dict]:
    """**加入月数べつの線。** 長く入っていた人ほど、線は低いところにあります。"""
    rows = []
    for m in (MIN_MONTHS, 360, 420, 480):
        line = saitei_hoshou_line(m)
        rows.append({
            "月数": m,
            "線": line["線"],
            "300月のときとの差": line["線"] - saitei_hoshou_line(MIN_MONTHS)["線"],
        })
    return rows


def gake_by_hyoujun(months: int = MIN_MONTHS, *, children: int = 0,
                    spouse: bool = False) -> list[dict]:
    """**2級と3級の崖を、平均標準報酬額べつに並べる。**

    最低保障が効いている帯では、3級だけが動かないので**崖は報酬とともに開き**、
    線をこえた後は 2級 も 3級 も同じ報酬比例を持つので
    **崖は「1階ぶん」で止まり、1円も動きません。**
    """
    m = max(months, MIN_MONTHS)
    line = saitei_hoshou_line(m)["線"]
    rows = []
    for hyoujun in (150_000, 250_000, 350_000, line, line + 50_000,
                    500_000, 650_000):
        g = gake_2_3(hyoujun, m, children=children, spouse=spouse)
        g["平均標準報酬額"] = hyoujun
        g["3級の年額"] = nenkin(3, hyoujun, m)["合計"]
        g["障害手当金"] = teatekin(hyoujun, m)["手当金"]
        g["最低保障が効いたか"] = saitei_ga_kiku(hyoujun, m)
        rows.append(g)
    return rows


def gake_atama_uchi(*, children: int = 0, spouse: bool = False) -> int:
    """**線から上での、2級と3級の差**（＝障害基礎年金＋配偶者加給）。"""
    return gake_2_3(1_000_000, MIN_MONTHS, children=children,
                    spouse=spouse)["差"]


# ---- 主題8: 扶養親族と子は、別々のところに効く ---------------------------
#
# **20歳前傷病の所得制限で、線を動かすのは「扶養親族の人数」だけ**です
# （国民年金法36条の3・施行令5条の4）。**崖の高さを決めるのは「子の人数」**で、
# こちらは年金額の側に入っています。**同じ子が両方に数えられる**ことが多いので、
# 1人増えると **線も上がり、崖も高くなります。** どちらが速いかは表が答えます。
def fuyo_gake_grid(grade: int = 2) -> list[dict]:
    """扶養親族＝子の人数として、線と崖を同時に動かす。"""
    rows = []
    for n in range(0, 4):
        line = teishi_line(n)
        g = hatachi_mae_gake(grade, children=n, fuyo=n)
        rows.append({
            "人数": n,
            "半額停止の線": line["半額停止の線"],
            "全額停止の線": line["全額停止の線"],
            "基礎年金": kiso(grade, n)["合計"],
            "半額停止の崖": g["崖"][0]["減る額"],
            "全額停止の崖": g["崖"][1]["減る額"],
        })
    return rows


def fuyo_ippo(grade: int = 2) -> dict:
    """**1人増えたときに、線と崖がそれぞれいくら動くか。**"""
    rows = fuyo_gake_grid(grade)
    return {
        "線の動き": rows[1]["半額停止の線"] - rows[0]["半額停止の線"],
        "半額の崖の動き": rows[1]["半額停止の崖"] - rows[0]["半額停止の崖"],
        "全額の崖の動き": rows[1]["全額停止の崖"] - rows[0]["全額停止の崖"],
        "第3子での線の動き": rows[3]["半額停止の線"] - rows[2]["半額停止の線"],
        "第3子での半額の崖の動き": (rows[3]["半額停止の崖"]
                                    - rows[2]["半額停止の崖"]),
    }


# ---- 主題6: 厚生年金のあるなしで、同じ等級がいくら変わるか ---------------
def kousei_no_umu(grade: int, hyoujun: int, months: int, *,
                  children: int = 0, spouse: bool = False) -> dict:
    """**同じ障害・同じ等級でも、加入していた制度で額が変わります。**"""
    ari = nenkin(grade, hyoujun, months, children=children, spouse=spouse)
    nashi = nenkin(grade, children=children, spouse=spouse,
                   kousei_kanyu=False)
    return {
        "等級": grade,
        "厚生年金あり": ari["合計"],
        "厚生年金なし": nashi["合計"],
        "差": ari["合計"] - nashi["合計"],
        "倍率": (ari["合計"] / nashi["合計"]) if nashi["合計"] else 0.0,
    }


# ---- 主題6: 差は定額・倍率だけが動く ------------------------------------
def sa_ittei(hyoujun: int, months: int, *, children: int = 0,
             spouse: bool = False) -> dict:
    """**1級と2級の差は、家族が何人いても1円も動きません。**

    合計の倍率は家族が増えるほど下がります（`baisuu`）。
    **同じ表から「差は動かない」も出ます。**矛盾ではありません ——
    定額の加算は1級にも2級にも同じ額だけ乗るので、**引き算で消えます。**

        1級の合計 − 2級の合計
          = 0.25 × 障害基礎年金の本体 + 0.25 × 報酬比例
          = 204,000円 + 報酬比例の4分の1

    **子の加算も配偶者加給も、この式のどこにも出てきません。**
    動くのは分母だけなので、**倍率は下がるのに、差は1円も動かない。**
    """
    b = baisuu(hyoujun, months, children=children, spouse=spouse)
    hirei = houshu_hirei(hyoujun, months) if hyoujun else 0
    teigaku = round(BASIC_FULL * (GRADE1_RATE - 1))
    return {
        "子の人数": children,
        "配偶者": spouse,
        "2級の合計": b["2級の合計"],
        "1級の合計": b["1級の合計"],
        "差": b["差"],
        "本当の倍率": b["本当の倍率"],
        "定額の部分": teigaku,
        "報酬比例の4分の1": round(hirei * (GRADE1_RATE - 1)),
        "1.25倍されない額": b["1.25倍されない額"],
    }


def sa_ittei_hyou(hyoujun: int = 300_000, months: int = MIN_MONTHS) -> dict:
    """`sa_ittei` を家族べつに並べる。**差の欄は1つの値に潰れます。**"""
    rows = [sa_ittei(hyoujun, months, children=c, spouse=sp)
            for c, sp in ((0, False), (0, True), (1, True), (2, True),
                          (3, True), (5, True))]
    sa = {r["差"] for r in rows}
    return {
        "行": rows,
        "差の種類": sorted(sa),
        "差は1つか": len(sa) == 1,
        "倍率の幅": (min(r["本当の倍率"] for r in rows),
                     max(r["本当の倍率"] for r in rows)),
    }


# ---- 主題7: 報酬がゼロの人の「床」 --------------------------------------
def yuka() -> dict:
    """**報酬比例が0円の人が受け取る額は、4つとも204,000円の等差で並びます。**

        障害手当金の最低保障  1,224,000円   = 204,000円 × 6
        1級の障害基礎年金     1,020,000円   = 204,000円 × 5
        2級の障害基礎年金       816,000円   = 204,000円 × 4
        3級の最低保障           612,000円   = 204,000円 × 3

    **6 : 5 : 4 : 3。**別々の条文から出てきた4つの額が、等差数列になります。
    公差の 204,000円 は、**`sa_ittei` の「定額の部分」と同じ数**です ——
    どちらも `BASIC_FULL × 0.25` だからです。
    """
    step = round(BASIC_FULL * (GRADE1_RATE - 1))
    rows = [
        {"名前": "障害手当金の最低保障", "額": GRADE3_MIN * TEATE_MULTIPLE,
         "根拠": "3級の最低保障の2倍（厚生年金保険法57条）"},
        {"名前": "1級の障害基礎年金", "額": round(BASIC_FULL * GRADE1_RATE),
         "根拠": "2級の1.25倍（国民年金法33条2項）"},
        {"名前": "2級の障害基礎年金", "額": BASIC_FULL,
         "根拠": "老齢基礎年金の満額と同額（国民年金法33条）"},
        {"名前": "3級の最低保障", "額": GRADE3_MIN,
         "根拠": "障害基礎年金2級の4分の3"},
    ]
    for r in rows:
        r["公差の何倍"] = r["額"] / step
    diffs = [rows[i]["額"] - rows[i + 1]["額"] for i in range(len(rows) - 1)]
    return {
        "行": rows,
        "公差": step,
        "差": diffs,
        "等差か": len(set(diffs)) == 1,
        "比": [int(r["公差の何倍"]) for r in rows],
    }


# ---- 主題8: 同じ手当金でも、2級とは報酬で動く --------------------------
def teatekin_vs_2kyuu(hyoujun: int, months: int = MIN_MONTHS, *,
                      children: int = 0, spouse: bool = False) -> dict:
    """**障害手当金は、2級の何年ぶんか。**

    3級とは**どんな報酬でもちょうど2年**です（`narabu_toshi`）——
    手当金も3級も報酬比例の定数倍なので、報酬が約分で消えるからです。
    **2級には約分の効かない障害基礎年金が乗ります。**だから動きます。
    """
    t = teatekin(hyoujun, months)
    g2 = nenkin(2, hyoujun, months, children=children, spouse=spouse)
    g3 = nenkin(3, hyoujun, months, children=children, spouse=spouse)
    return {
        "平均標準報酬額": hyoujun,
        "報酬比例": t["報酬比例"],
        "手当金": t["手当金"],
        "最低保障が効いている": t["計算どおりの額"] < t["最低保障"],
        "2級の年額": g2["合計"],
        "3級の年額": g3["合計"],
        "2級と並ぶ年数": t["手当金"] / g2["合計"] if g2["合計"] else 0.0,
        "3級と並ぶ年数": t["手当金"] / g3["合計"] if g3["合計"] else 0.0,
    }


def teatekin_vs_2kyuu_soko(months: int = MIN_MONTHS) -> dict:
    """**その年数がいちばん短くなる1点と、1年を割る帯の両端。**

    底は **3級の最低保障が外れる線と同じ1点**です。そこより下では手当金が
    最低保障で止まっていて分子が動かず、上では分子だけが2倍の速さで伸びます。

        帯の下端  報酬比例 = 基礎年金の半分（408,000円）
        底        報酬比例 = 3級の最低保障（612,000円）→ **ちょうど 6/7 年**
        帯の上端  報酬比例 = 基礎年金と同額（816,000円）

    **下端の平均標準報酬額を2倍すると上端**になります（どちらも
    `報酬比例 = 定数 × 平均標準報酬額` の1次式で、定数が2倍だから）。
    """
    line = saitei_hoshou_line(months)
    m = max(months, MIN_MONTHS)
    per = ACCRUAL * m                       # 平均標準報酬額1円あたりの報酬比例
    floor = GRADE3_MIN * TEATE_MULTIPLE
    # 手当金（最低保障）＝ 2級の1年ぶん になる点
    shita = (floor - BASIC_FULL) / per
    # 2 × 報酬比例 ＝ 基礎年金 + 報酬比例 になる点
    ue = BASIC_FULL / per
    return {
        "計算に使う月数": m,
        "底の平均標準報酬額": line["線"],
        "底の年数": (GRADE3_MIN * TEATE_MULTIPLE)
                    / (BASIC_FULL + GRADE3_MIN),
        "1年を割る下端": round(shita),
        "1年に戻る上端": round(ue),
        "下端の報酬比例": round(shita * per),
        "上端の報酬比例": round(ue * per),
        "上端は下端の何倍": ue / shita if shita else 0.0,
    }


# ---- 主題9: 傷病手当金との併給調整（**族をまたいだ比較**）-----------------
#
# **この2つを並べた金額表は、どこにも公表されていません。**
# 日本年金機構の障害年金の案内は傷病手当金に触れず、協会けんぽの傷病手当金の
# 案内は「障害厚生年金を受けられるときは調整されます」と**書くだけ**で、
# **いくらになるかの表を持っていません。**
# `src/calc/shobyo.py` の `ASSUMPTIONS` も、2026-08-28 まで
# 「障害年金や老齢年金との調整は含めていません」と**自分で言っていました**。
#
# **払う側から見れば同じ1つの病気なのに、境目を並べた表が無い。**
#
# 根拠は健康保険法108条4項:
#
#   > 傷病手当金の支給を受けるべき者が、同一の傷病について障害厚生年金の支給を
#   > 受けることができるときは、傷病手当金は、支給しない。ただし、その受けることが
#   > できる障害厚生年金の額（同一の傷病について障害基礎年金の支給を受けることが
#   > できるときは、その合算額）につき算定した額が傷病手当金の額より少ないときは、
#   > その差額を支給する。
#
# 施行規則が言う「算定した額」は **年金額 ÷ 360**（1円未満四捨五入）です。
# 同条5項の障害手当金（一時金）のほうは**差額ではなく日数**で効きます ——
# 傷病手当金の合算額が障害手当金の額に達するまで、1円も出ません。
#
# **ここで比べている2つの「標準報酬」は、本当は別のものです**（下の註）。
# 前提を置かないと並べられないので、**置いた前提を全部 画面に出します。**
SHOBYO_DIVISOR = 360            # 年金額をこれで割る（健康保険法施行規則84条の2）


def nenkin_nichigaku(nenkin_year: int) -> int:
    """**年金の1日ぶん**。年金額 ÷ 360（1円未満四捨五入）。

    **365 でも 366 でもありません。** 30日×12か月の 360 です。
    """
    return round(nenkin_year / SHOBYO_DIVISOR)


def shobyo_chousei(standard_pay: int, grade: int = 3, *,
                   hyoujun: int | None = None, months: int = MIN_MONTHS,
                   children: int = 0, spouse: bool = False) -> dict:
    """**障害年金をもらっている人の、傷病手当金の日額。**

    ## 並べるために置いた前提（**ここが効きます**）

    傷病手当金の `standard_pay` は**健康保険の標準報酬月額**（直近12か月の平均）、
    障害厚生年金の `hyoujun` は**厚生年金の平均標準報酬額**（生涯の平均・賞与込み・
    再評価後）で、**同じ人でも普通は一致しません。**
    `hyoujun` を省いたときは `standard_pay` と同額に置きます ——
    **賞与が無く、再評価率が1.0で、いまの報酬がずっと続いていた人**の形です。
    賞与のある人は `hyoujun` のほうが大きくなるので、**年金が増えて
    傷病手当金はもっと減ります**（この計算は、減り方の下限を出しています）。
    """
    from . import shobyo as _shobyo

    hy = standard_pay if hyoujun is None else hyoujun
    pension = nenkin(grade, hy, months, children=children, spouse=spouse)
    # **3級には障害基礎年金がありません。**108条4項が合算するのは
    # 「同一の傷病について障害基礎年金を受けられるとき」だけなので、
    # 3級の人はここが障害厚生年金だけになります（`nenkin()` が既にそう返します）。
    day_shobyo = _shobyo.daily(standard_pay)
    day_pension = nenkin_nichigaku(pension["合計"])
    sagaku = max(0, day_shobyo - day_pension)
    return {
        "標準報酬月額": standard_pay,
        "平均標準報酬額": hy,
        "等級": grade,
        "年金の年額": pension["合計"],
        "傷病手当金の日額": day_shobyo,
        "年金の日額": day_pension,
        "実際に出る傷病手当金": sagaku,
        "止まる額": day_shobyo - sagaku,
        "残る割合": sagaku / day_shobyo if day_shobyo else 0.0,
        "1円も出ないか": sagaku == 0,
    }


def shobyo_kieru_line(grade: int = 3, *, months: int = MIN_MONTHS,
                      children: int = 0, spouse: bool = False,
                      hi: int = 650_000) -> dict:
    """**傷病手当金が1円も出なくなる、標準報酬月額の上限。**

    `standard_pay` を 1,000円 きざみで上げると、傷病手当金は `standard_pay/45`
    で伸び、年金の日額は `standard_pay × 乗率 × 月数 ÷ 360` で伸びます。
    **傷病手当金のほうが必ず速い**ので、線は1本で、**その線以下が全部「出ない」**側。

    見つからないときは `線` に 0 を返します（＝ どの報酬でも差額が出る）。
    """
    step = 1_000
    line = 0
    pay = 58_000        # 健康保険の第1等級
    while pay <= hi:
        if shobyo_chousei(pay, grade, months=months, children=children,
                          spouse=spouse)["1円も出ないか"]:
            line = pay
        pay += step
    return {
        "等級": grade,
        "子の人数": children,
        "配偶者": spouse,
        "線": line,
        "線での年金の年額": (nenkin(grade, line or 58_000, months,
                                   children=children, spouse=spouse)["合計"]),
        "線の1つ上": line + step if line else 0,
        "線の1つ上で出る額": (shobyo_chousei(
            line + step, grade, months=months, children=children,
            spouse=spouse)["実際に出る傷病手当金"] if line else 0),
    }


def shobyo_chousei_grid(grade: int = 3, *, months: int = MIN_MONTHS,
                        children: int = 0, spouse: bool = False) -> list[dict]:
    """等級を1つ決めて、標準報酬月額べつに並べる。"""
    return [shobyo_chousei(pay, grade, months=months, children=children,
                           spouse=spouse)
            for pay in (58_000, 76_500, 100_000, 150_000, 200_000, 300_000,
                        440_000, 650_000)]


def teatekin_tomaru_hi(standard_pay: int, *, months: int = MIN_MONTHS) -> dict:
    """**障害手当金（一時金）は、日数で効きます**（健康保険法108条5項）。

    差額ではありません。**傷病手当金の合算額が障害手当金の額に達するまで、
    1円も出ません。** つまり「何日ぶん止まるか」が答えになります。

    546日（通算1年6か月）を全部 止めきる報酬かどうかも返します。
    """
    from . import shobyo as _shobyo

    ichiji = teatekin(standard_pay, months)["手当金"]
    day = _shobyo.daily(standard_pay)
    days = ichiji / day if day else 0.0
    return {
        "標準報酬月額": standard_pay,
        "障害手当金": ichiji,
        "傷病手当金の日額": day,
        "止まる日数": days,
        "上限の日数": _shobyo.MAX_DAYS,
        "上限を全部 止めるか": days >= _shobyo.MAX_DAYS,
        "残る日数": max(0.0, _shobyo.MAX_DAYS - days),
    }


def teatekin_tomaru_grid() -> list[dict]:
    """障害手当金が止める日数を、標準報酬月額べつに並べる。"""
    return [teatekin_tomaru_hi(pay)
            for pay in (58_000, 100_000, 200_000, 300_000, 372_195, 440_000,
                        650_000)]


# ---- 主題10: 約分で報酬が消える2つ（**この表のいちばん深いところ**）-------
#
# 傷病手当金の日額は `標準報酬月額 ÷ 45`（＝ ÷30 × 2/3）、
# 3級の報酬比例は `平均標準報酬額 × 乗率 × 月数` です。
# **2つを同じ報酬で並べると、報酬が約分で消えます。**
# 残るのは **月数だけ** —— だから「いくら止まるか」は人によって違うのに、
# **「何割 止まるか」は誰でも同じ**になります（最低保障が外れた帯で）。
SHOBYO_DAILY_DIVISOR = 45       # 30日 ÷ (2/3)。傷病手当金の日額 ＝ 月額 ÷ 45


def shobyo_tomaru_wariai(months: int = MIN_MONTHS) -> dict:
    """**3級で止まる割合。報酬によりません。**

        止まる割合 ＝ (乗率 × 月数 ÷ 360) × 45 ＝ 乗率 × 月数 ÷ 8

    最低保障（612,000円）が効いている帯の外だけの話です。
    帯の中では年金が定額なので、報酬が上がるほど止まる割合は下がります。
    """
    m = max(months, MIN_MONTHS)
    share = ACCRUAL * m / (SHOBYO_DIVISOR / SHOBYO_DAILY_DIVISOR)
    return {
        "月数": m,
        "止まる割合": share,
        "残る割合": 1 - share,
        "最低保障が外れる線": saitei_hoshou_line(m)["線"],
    }


def shobyo_tomaru_wariai_grid() -> list[dict]:
    """月数べつ。**60月ごとに、止まる割合は同じ幅だけ増えます**（1次式なので）。"""
    return [shobyo_tomaru_wariai(m) for m in (MIN_MONTHS, 360, 420, 480)]


def teatekin_tomaru_ittei(months: int = MIN_MONTHS) -> dict:
    """**最低保障が外れた帯で、障害手当金が止める日数。報酬によりません。**

        止まる日数 ＝ (報酬比例 × 2) ÷ (標準報酬月額 ÷ 45)
                    ＝ 乗率 × 月数 × 2 × 45

    3級の「止まる割合」の **2 × 45 ÷ (1/360) 倍**にあたる同じ約分です。
    """
    m = max(months, MIN_MONTHS)
    return {
        "月数": m,
        "止まる日数": ACCRUAL * m * TEATE_MULTIPLE * SHOBYO_DAILY_DIVISOR,
        "最低保障が外れる線": saitei_hoshou_line(m)["線"],
    }


def teatekin_zenbu_tomaru_line(months: int = MIN_MONTHS) -> dict:
    """**546日を まるごと 止めてしまう、標準報酬月額の上限。**

    最低保障の 1,224,000円 は定額なので、**報酬が低い人ほど日数が長くなります。**
    1,000円 きざみで探します（等級が 1,000円 きざみなので）。
    """
    from . import shobyo as _shobyo

    step = 1_000
    line = 0
    pay = 58_000
    while pay <= 650_000:
        if teatekin_tomaru_hi(pay, months=months)["上限を全部 止めるか"]:
            line = pay
        pay += step
    return {
        "月数": max(months, MIN_MONTHS),
        "線": line,
        "上限の日数": _shobyo.MAX_DAYS,
        "線での止まる日数": (teatekin_tomaru_hi(line, months=months)["止まる日数"]
                            if line else 0.0),
        "線の1つ上で残る日数": (teatekin_tomaru_hi(line + step,
                                                  months=months)["残る日数"]
                                if line else 0.0),
    }


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(BASIC_FULL, 816_000, "障害基礎年金2級の額",
                      source="国民年金法33条。老齢基礎年金の満額と同額（令和6年度）")
    _checks.statutory(GRADE1_RATE, 1.25, "1級の倍率",
                      source="国民年金法33条2項・厚生年金保険法50条2項")
    _checks.statutory(CHILD_ADD_1_2, 234_800, "子の加算（第1子・第2子）",
                      source="国民年金法33条の2。遺族基礎年金と同額")
    _checks.statutory(CHILD_ADD_3_ON, 78_300, "子の加算（第3子以降）",
                      source="国民年金法33条の2")
    _checks.statutory(SPOUSE_ADD, 234_800, "配偶者加給年金",
                      source="厚生年金保険法50条の2。1級と2級だけ")
    _checks.statutory(GRADE3_MIN, 612_000, "障害厚生年金3級の最低保障額",
                      source="障害基礎年金2級の4分の3")
    _checks.statutory(MIN_MONTHS, 300, "300月みなし",
                      source="厚生年金保険法51条")
    _checks.statutory(TEATE_MULTIPLE, 2, "障害手当金の倍率",
                      source="厚生年金保険法57条。報酬比例の2倍の一時金")
    _checks.statutory(ZENGAKU_TEISHI, 4_721_000, "20歳前傷病の全額停止の線",
                      source="国民年金法36条の3。扶養親族なしの所得額")
    _checks.statutory(HANGAKU_TEISHI, 3_704_000, "20歳前傷病の半額停止の線",
                      source="国民年金法36条の3")
    _checks.statutory(FUYO_KASAN, 380_000, "扶養親族1人あたりの加算",
                      source="国民年金法施行令5条の4")
    _checks.ratio(ACCRUAL, "報酬比例の給付乗率")

    # 2. 表の形
    # 3級の最低保障は、2級の本体のちょうど4分の3
    _checks.rounding(GRADE3_MIN, round(BASIC_FULL * GRADE3_MIN_RATE),
                     "3級の最低保障額（2級の4分の3）")
    _checks.greater(ZENGAKU_TEISHI, HANGAKU_TEISHI,
                    "全額停止の線が半額停止の線より高い")
    _checks.greater(CHILD_ADD_1_2, CHILD_ADD_3_ON,
                    "第1子・第2子の加算が第3子以降より多い")
    _checks.ascending([child_add(n) for n in range(0, 6)], "子の加算の合計")

    # 3. 計算の向き
    _checks.increases_with(lambda m: houshu_hirei(3_000_000, m),
                           (300, 360, 420, 480), "月数が増えれば報酬比例も増える")
    _checks.never_decreases(lambda m: houshu_hirei(3_000_000, m),
                            (0, 60, 120, 240, 299, 300, 360),
                            "月数が増えたのに報酬比例が減っている")
    _checks.increases_with(lambda h: nenkin(2, h, 300)["合計"],
                           (2_000_000, 3_000_000, 5_000_000),
                           "報酬が増えれば2級の合計も増える")
    # 等級が上がれば額も上がる（同じ人で）
    _checks.increases_with(lambda g: nenkin(4 - g, 3_000_000, 300,
                                            children=1, spouse=True)["合計"],
                           (1, 2, 3), "等級が上がれば年金も増える")

    # 4. **この表の主題そのもの**
    # 倍率は必ず1.25を下回る（加算がある人）。加算が0円なら1.25ちょうど。
    b0 = baisuu(3_000_000, 300)
    _checks.rounding(round(b0["本当の倍率"], 4), GRADE1_RATE,
                     "加算が無い人の1級÷2級")
    for children in (1, 2, 3):
        b = baisuu(3_000_000, 300, children=children, spouse=True)
        if not b["本当の倍率"] < GRADE1_RATE:
            raise _checks.TableError(
                f"子{children}人・配偶者ありの倍率が {b['本当の倍率']:.4f} で、"
                f"1.25 を下回っていません。**定額の加算が1.25倍されています**")
    # 加算が厚いほど倍率は下がる（単調）
    _checks.decreases_with(
        lambda c: baisuu(3_000_000, 300, children=c, spouse=True)["本当の倍率"],
        (0, 1, 2, 3), "加算が厚いほど倍率が下がる")

    # 5. **差は定額**（主題6）。倍率が下がるのと同じ表から出ます。
    h = sa_ittei_hyou(300_000, 300)
    if not h["差は1つか"]:
        raise _checks.TableError(
            f"1級と2級の差が家族で動いています: {h['差の種類']}。"
            f"**定額の加算が引き算で消えていません**")
    lo, hi = h["倍率の幅"]
    if not lo < hi:
        raise _checks.TableError(
            f"差が定額なのに倍率まで動いていません（{lo:.4f}〜{hi:.4f}）。"
            f"**この節は「差は不変・倍率だけが動く」を主張しています**")
    for hyoujun in (0, 300_000, 1_000_000):
        s = sa_ittei(hyoujun, 300, children=2, spouse=True)
        _checks.rounding(s["差"], s["定額の部分"] + s["報酬比例の4分の1"],
                         f"差＝204,000円＋報酬比例の4分の1（{hyoujun:,}円）")

    # 6. **床の等差**（主題7）。別々の条文の4つが 6:5:4:3 に並びます。
    y = yuka()
    if not y["等差か"]:
        raise _checks.TableError(
            f"報酬ゼロの4つの床が等差ではありません: 差 {y['差']}。"
            f"**制度の値のどれかが動いています**")
    _checks.rounding(y["公差"], round(BASIC_FULL * (GRADE1_RATE - 1)),
                     "床の公差（＝基礎年金の4分の1）")
    if y["比"] != [6, 5, 4, 3]:
        raise _checks.TableError(f"床の比が 6:5:4:3 ではありません: {y['比']}")
    _checks.rounding(y["公差"], sa_ittei(0, 0)["差"],
                     "床の公差と、報酬ゼロの人の1級2級の差は同じ数")

    # 7. **手当金は2級の何年ぶんか**（主題8）。3級とは定数、2級とは V字。
    for hyoujun in (0, 200_000, 372_195, 500_000, 2_000_000):
        v = teatekin_vs_2kyuu(hyoujun, 300)
        _checks.rounding(round(v["3級と並ぶ年数"], 6), float(TEATE_MULTIPLE),
                         f"3級とはどんな報酬でも2年（{hyoujun:,}円）")
    soko = teatekin_vs_2kyuu_soko(300)
    _checks.rounding(soko["底の平均標準報酬額"], saitei_hoshou_line(300)["線"],
                     "V字の底は、3級の最低保障が外れる線と同じ1点")
    _checks.rounding(round(soko["底の年数"], 6), round(6 / 7, 6),
                     "底の年数はちょうど 6/7 年")
    _checks.rounding(soko["下端の報酬比例"], round(BASIC_FULL / 2),
                     "1年を割る下端の報酬比例（基礎年金の半分）")
    _checks.rounding(soko["上端の報酬比例"], BASIC_FULL,
                     "1年に戻る上端の報酬比例（基礎年金と同額）")
    _checks.rounding(round(soko["上端は下端の何倍"], 6), 2.0,
                     "上端の平均標準報酬額は下端のちょうど2倍")
    # 底が本当に底か（両側より短い）
    base = teatekin_vs_2kyuu(soko["底の平均標準報酬額"], 300)["2級と並ぶ年数"]
    for other in (150_000, 250_000, 600_000, 1_500_000):
        if not teatekin_vs_2kyuu(other, 300)["2級と並ぶ年数"] > base:
            raise _checks.TableError(
                f"平均標準報酬額 {other:,}円 のほうが底（{base:.4f}年）より"
                f"短くなっています。**V字の底が動いています**")

    # 手当金と3級は、**どの報酬でもちょうど2年**（約分で報酬が消える）
    for hyoujun in (0, 200_000, 300_000, 500_000, 1_000_000):
        n = narabu_toshi(hyoujun, 300)
        _checks.rounding(round(n["並ぶ年数"], 6), float(TEATE_MULTIPLE),
                         f"平均標準報酬額 {hyoujun:,}円 での並ぶ年数")

    # 最低保障の線は**1本**。3級と障害手当金が、同じ1円で同時に外れる
    for m in (MIN_MONTHS, 360, 480):
        line = saitei_hoshou_line(m)
        lo = line["線"]
        if saitei_ga_kiku(lo, m):
            raise _checks.TableError(
                f"月数{m}・平均標準報酬額 {lo:,}円 で、3級の最低保障がまだ効いています。"
                "**線の探し方が1円ずれています**")
        if not saitei_ga_kiku(lo - 1, m):
            raise _checks.TableError(
                f"月数{m}・平均標準報酬額 {lo - 1:,}円 で、3級の最低保障が効いていません。"
                "**線より下なのに外れています**")
        # 手当金の側も、同じ1円で外れる（最低保障も計算どおりの額も、ちょうど2倍）
        if teatekin(lo - 1, m)["手当金"] != GRADE3_MIN * TEATE_MULTIPLE:
            raise _checks.TableError(
                f"月数{m}・平均標準報酬額 {lo - 1:,}円 で、障害手当金が"
                "最低保障から外れています。**線が2本になっています**")
    # 月数が長いほど線は低い
    _checks.decreases_with(lambda m: saitei_hoshou_line(m)["線"],
                           (MIN_MONTHS, 360, 420, 480),
                           "月数が長いほど、最低保障が外れる報酬は低い")
    # 線から上では、2級と3級の差は**1円も動かない**（＝1階ぶんで頭打ち）
    over = [r["差"] for r in gake_by_hyoujun(children=1, spouse=True)
            if not r["最低保障が効いたか"]]
    if len(set(over)) != 1:
        raise _checks.TableError(
            f"線から上で、2級と3級の差が {sorted(set(over))} と動いています。"
            "**同じ報酬比例が両方に乗っているはずです**")
    _checks.rounding(over[0], gake_atama_uchi(children=1, spouse=True),
                     "線から上での2級と3級の差")
    # 線より下では、報酬が増えるほど崖は開く（3級だけが止まっているため）
    under = [r for r in gake_by_hyoujun(children=1, spouse=True)
             if r["最低保障が効いたか"]]
    _checks.ascending([r["差"] for r in under], "線より下での崖の高さ",
                      strict=True)

    # 20歳前傷病: 線を動かすのは扶養親族、崖の高さを決めるのは子
    step = fuyo_ippo(2)
    _checks.rounding(step["線の動き"], FUYO_KASAN, "扶養親族1人での線の動き")
    _checks.rounding(step["半額の崖の動き"], round(CHILD_ADD_1_2 / 2),
                     "子1人での半額停止の崖の動き")
    _checks.greater(step["線の動き"], step["半額の崖の動き"],
                    "線の上がり方のほうが、崖の高くなり方より大きい")
    _checks.ascending([r["半額停止の線"] for r in fuyo_gake_grid(2)],
                      "扶養親族が増えたときの半額停止の線", strict=True)
    _checks.ascending([r["半額停止の崖"] for r in fuyo_gake_grid(2)],
                      "子が増えたときの半額停止の崖", strict=True)

    # 8. **傷病手当金との調整**（主題9・10）。
    # **報酬によらない側だけを固定します。** 線そのものの額は、
    # 「健康保険の標準報酬月額 ＝ 厚生年金の平均標準報酬額」という置き方に
    # 乗っているので、ここには入れません（`ASSUMPTIONS`）。
    _checks.statutory(SHOBYO_DIVISOR, 360, "年金を日額に直すときの除数",
                      source="健康保険法108条4項・同施行規則84条の2")
    _checks.statutory(SHOBYO_DAILY_DIVISOR, 45,
                      "傷病手当金の日額を出すときの除数（30 ÷ 2/3）",
                      source="健康保険法99条")
    # 線以下は1円も出ず、線の1つ上では出る（＝線が1本で、探し方がずれていない）
    for grade in (1, 2, 3):
        line = shobyo_kieru_line(grade)
        if not line["線"]:
            raise _checks.TableError(
                f"{grade}級で、傷病手当金が消える線が見つかりません。"
                "**調整の向きが逆になっています**")
        if not shobyo_chousei(line["線"], grade)["1円も出ないか"]:
            raise _checks.TableError(
                f"{grade}級・標準報酬月額 {line['線']:,}円 で傷病手当金が出ています。"
                "**線が1,000円 ずれています**")
        if shobyo_chousei(line["線の1つ上"], grade)["1円も出ないか"]:
            raise _checks.TableError(
                f"{grade}級・標準報酬月額 {line['線の1つ上']:,}円 でも"
                "傷病手当金が出ていません。**線より上なのに消えています**")
    # 等級が上がるほど線は上（年金が大きいので、消える帯が広がる）
    _checks.ascending([shobyo_kieru_line(g)["線"] for g in (3, 2, 1)],
                      "等級が上がったときの、傷病手当金が消える線", strict=True)
    # 家族が増えると線はさらに上（定額の加算がそのまま年金に乗るため）
    _checks.ascending([shobyo_kieru_line(2, children=c)["線"]
                       for c in (0, 1, 2)],
                      "子が増えたときの、傷病手当金が消える線", strict=True)
    # **止まる割合は報酬によらない**（最低保障が外れた帯で）。約分の結果
    want = shobyo_tomaru_wariai(MIN_MONTHS)["残る割合"]
    for pay in (400_000, 500_000, 650_000):
        got = shobyo_chousei(pay, 3)["残る割合"]
        if abs(got - want) > 1e-3:            # 10円未満四捨五入のぶんだけ揺れる
            raise _checks.TableError(
                f"標準報酬月額 {pay:,}円 で、3級の残る割合が {got:.4%} です"
                f"（報酬によらず {want:.4%} のはず）。**約分が壊れています**")
    _checks.close(shobyo_tomaru_wariai(MIN_MONTHS)["止まる割合"],
                  ACCRUAL * MIN_MONTHS / 8, "止まる割合＝乗率×月数÷8", tol=1e-12)
    # 月数の1次式なので、60月ごとの伸びはどこも同じ幅
    rows = shobyo_tomaru_wariai_grid()
    steps = {round(b["止まる割合"] - a["止まる割合"], 9)
             for a, b in zip(rows, rows[1:])}
    if len(steps) != 1:
        raise _checks.TableError(
            f"60月ごとの伸びが {sorted(steps)} と揃っていません。"
            "**止まる割合が月数の1次式になっていません**")
    # **障害手当金が止める日数も、線から上ではどの報酬でも同じ**
    ittei = teatekin_tomaru_ittei(MIN_MONTHS)["止まる日数"]
    _checks.close(ittei, ACCRUAL * MIN_MONTHS * TEATE_MULTIPLE
                  * SHOBYO_DAILY_DIVISOR, "止まる日数＝乗率×月数×2×45", tol=1e-9)
    for pay in (400_000, 500_000, 650_000):
        got = teatekin_tomaru_hi(pay)["止まる日数"]
        if abs(got - ittei) > 0.05:
            raise _checks.TableError(
                f"標準報酬月額 {pay:,}円 で、障害手当金の止める日数が {got:.2f}日 です"
                f"（線から上ではどの報酬でも {ittei:.2f}日 のはず）")
    # 最低保障が効いている帯では、報酬が低い人ほど長く止まる
    _checks.decreases_with(lambda p: teatekin_tomaru_hi(p)["止まる日数"],
                           (58_000, 100_000, 200_000, 300_000),
                           "最低保障の帯では、報酬が低いほど長く止まる")
    zenbu = teatekin_zenbu_tomaru_line()
    if not teatekin_tomaru_hi(zenbu["線"])["上限を全部 止めるか"]:
        raise _checks.TableError(
            f"標準報酬月額 {zenbu['線']:,}円 で、546日を全部は止めていません。"
            "**線が1,000円 ずれています**")
    if teatekin_tomaru_hi(zenbu["線"] + 1_000)["上限を全部 止めるか"]:
        raise _checks.TableError(
            f"標準報酬月額 {zenbu['線'] + 1_000:,}円 でも546日を全部 止めています。"
            "**線より上なのに止まりきっています**")


def main() -> None:
    check_tables()

    print("=== 「1級は2級の1.25倍」は、受け取る合計では成り立たない"
          "（平均標準報酬額 300,000円・300月）===")
    for children, spouse in ((0, False), (0, True), (1, True), (2, True),
                             (3, True)):
        b = baisuu(300_000, 300, children=children, spouse=spouse)
        print(f"  子{children}人・配偶者{'あり' if spouse else 'なし'}"
              f"  2級 {b['2級の合計']:>9,}円"
              f"  → 1級 {b['1級の合計']:>9,}円"
              f"  **{b['本当の倍率']:.4f}倍**"
              f"（1.25 との差 {b['1.25倍からの目減り']:.4f}）"
              f"  1.25倍されない額 {b['1.25倍されない額']:>8,}円")
    print("  → 1.25倍が掛かるのは**基礎の本体と報酬比例だけ**です。"
          "子の加算と配偶者加給は定額のまま乗るので、**分母だけが太ります。**"
          "**家族が多い人ほど、等級が上がったときに増える割合は薄くなります**")

    print("\n=== 倍率がいちばん低くなるのは、厚生年金に入っていない人"
          "（報酬比例が0円なので、加算の割合が最大になる）===")
    s = baisuu_saitei()
    for r in s["行"]:
        print(f"  子{r['子の人数']}人  2級 {r['2級の合計']:>9,}円"
              f"  → 1級 {r['1級の合計']:>9,}円"
              f"  **{r['本当の倍率']:.4f}倍**"
              f"  差 {r['差']:>8,}円")
    print(f"  → いちばん低いのは **子{s['そのときの子の人数']}人 の "
          f"{s['いちばん低い倍率']:.4f}倍**。"
          f"1級と2級は**同じ判定表で分かれる**のに、**増える割合は家族で決まります**")

    print("\n=== 2級と3級の崖は「1階ぶん」まるごと"
          "（平均標準報酬額 300,000円・300月）===")
    for children, spouse in ((0, False), (0, True), (1, True), (2, True)):
        g = gake_2_3(300_000, 300, children=children, spouse=spouse)
        print(f"  子{children}人・配偶者{'あり' if spouse else 'なし'}"
              f"  3級 {g['3級の合計']:>9,}円"
              f"  → 2級 {g['2級の合計']:>9,}円"
              f"  **{g['倍率']:.2f}倍・差 {g['差']:>9,}円**"
              f"（消える基礎年金 {g['消える基礎年金']:>9,}円"
              f" ／ 消える配偶者加給 {g['消える配偶者加給']:>7,}円）")
    print("  → **3級には障害基礎年金がありません。**配偶者加給も付きません。"
          "**等級の判定に家族の人数は入らないのに、崖の高さは家族で決まります**")

    print("\n=== 障害手当金（一時金）と3級は、どんな報酬でもちょうど2年で並ぶ ===")
    for hyoujun in (150_000, 300_000, 500_000, 1_000_000):
        n = narabu_toshi(hyoujun, 300)
        print(f"  平均標準報酬額 {hyoujun:>9,}円"
              f"  3級の年額 {n['3級の年額']:>9,}円"
              f"  ／ 障害手当金 {n['障害手当金']:>10,}円"
              f"  → **並ぶのは {n['並ぶ年数']:.2f}年**"
              f"  （3年で {n['3年受けたときの差']:>9,}円"
              f" ／ 10年で {n['10年受けたときの差']:>10,}円 の差）")
    print("  → 手当金は報酬比例の2倍、**最低保障も3級の最低保障のちょうど2倍**です。"
          "**報酬の大きさが約分で消えるので、誰でも2年**。"
          "3級が2年より長く続くなら、3級のほうが多くなります")

    print("\n=== 300月みなし。**実際に働いた月数では割らない**"
          "（平均標準報酬額 300,000円・2級・子なし）===")
    for months in (12, 24, 60, 120, 240, 300, 360):
        m = minashi(300_000, months)
        print(f"  実際 {months:>3}か月"
              f"  → 計算は {m['計算に使う月数']:>3}か月"
              f"  報酬比例 {m['実際の月数どおりの報酬比例']:>9,}円"
              f" → **{m['みなしを入れた報酬比例']:>9,}円**"
              f"  {m['倍率']:>6.2f}倍"
              f"  年金の合計 {m['年金の合計']:>10,}円")
    print(f"  → みなしが効かなくなるのは **{minashi_moto_ga_toru()}か月**（25年）から。"
          f"**加入が短い人ほど、1か月あたりが大きく出ます**")

    print("\n=== 20歳前の傷病でもらう障害基礎年金には、崖が2つある"
          "（2級・子なし・扶養親族なし）===")
    line = teishi_line(0)
    for shotoku in (3_000_000, line["半額停止の線"], line["半額停止の線"] + 1,
                    4_500_000, line["全額停止の線"], line["全額停止の線"] + 1):
        h = hatachi_mae(shotoku)
        print(f"  所得 {shotoku:>9,}円"
              f"  {h['止まり方']:<10}"
              f"  年金 {h['止まらずに受け取れる年金']:>8,}円"
              f"  （止まる額 {h['止まる額']:>8,}円）"
              f"  所得と年金の合計 {h['所得と年金の合計']:>10,}円")
    g = hatachi_mae_gake(2, 0, 0)
    for row in g["崖"]:
        print(f"  → **{row['線']:,}円 を1円こえると、"
              f"手にする合計は {row['減る額']:,}円 減ります**"
              f"（{row['こえる前の合計']:,}円 → {row['こえた後の合計']:,}円）")
    print("  → 止まるのは**基礎年金の全部**で、**子の加算も一緒に止まります。**"
          "だから子が多い人ほど、この崖は高くなります")

    print("\n=== 子が多い人ほど、20歳前の所得制限の崖は高くなる"
          "（半額停止の線を1円こえたとき・扶養親族なし）===")
    for children in (0, 1, 2, 3):
        g = hatachi_mae_gake(2, children, 0)
        half = g["崖"][0]
        full = g["崖"][1]
        print(f"  子{children}人"
              f"  基礎年金 {kiso(2, children)['合計']:>9,}円"
              f"  → 半額停止の崖 **{half['減る額']:>8,}円**"
              f"  ／ 全額停止の崖 **{full['減る額']:>8,}円**")
    print("  → 崖の高さは**年金額の半分**です。"
          "**所得の線は子の人数で1円も動きません**（動くのは扶養親族の人数だけ）。"
          "**もらう額だけが増えて、線は同じ**なので、崖は子の人数に比例して高くなります")

    L = saitei_hoshou_line()
    print(f"\n=== 3級と障害手当金の最低保障は、"
          f"**同じ1円（平均標準報酬額 {L['線']:,}円）で同時に外れる**"
          f"（{L['計算に使う月数']}月）===")
    print(f"  1円下（{L['線'] - 1:,}円）: 報酬比例 {L['1円下の報酬比例']:,}円 "
          f"→ 3級は最低保障の {L['1円下の3級の年額']:,}円、"
          f"手当金は最低保障の {L['1円下の障害手当金']:,}円")
    print(f"  線ちょうど（{L['線']:,}円）: 報酬比例 {L['線での報酬比例']:,}円 "
          f"→ 3級 {L['線での3級の年額']:,}円、手当金 {L['線での障害手当金']:,}円")
    print(f"{'平均標準報酬額':>13s} {'報酬比例':>10s} {'3級の年額':>10s} "
          f"{'障害手当金':>11s}  {'最低保障'}")
    for r in gake_by_hyoujun():
        print(f"{r['平均標準報酬額']:12,d}円 "
              f"{houshu_hirei(r['平均標準報酬額'], MIN_MONTHS):9,d}円 "
              f"{r['3級の年額']:9,d}円 {r['障害手当金']:10,d}円  "
              + ("効いている（額を持ち上げている）" if r["最低保障が効いたか"]
                 else "外れている"))
    print(f"  → **線は2本ではなく1本です。** 手当金の最低保障 "
          f"{GRADE3_MIN * TEATE_MULTIPLE:,}円 は3級の最低保障 {GRADE3_MIN:,}円 の"
          f"ちょうど2倍で、計算どおりの額も報酬比例のちょうど2倍。"
          f"**2倍どうしが約分で消える**ので、外れる点が一致します")
    print(f"{'加入月数':>8s} {'最低保障が外れる平均標準報酬額':>22s} "
          f"{'300月のときとの差':>16s}")
    for r in saitei_hoshou_tsuki():
        print(f"{r['月数']:7d}月 {r['線']:21,d}円 {r['300月のときとの差']:15,d}円")
    print("  → **長く入っていた人ほど、線は低いところにあります。**"
          "同じ報酬でも報酬比例が太るので、最低保障を先に追い抜きます")

    print(f"\n=== 2級と3級の崖は、平均標準報酬額 {L['線']:,}円 から上では"
          "1円も動かない（子1人・配偶者あり・300月）===")
    print(f"{'平均標準報酬額':>13s} {'3級の合計':>10s} {'2級の合計':>10s} "
          f"{'差':>10s} {'倍率':>6s}  {'最低保障'}")
    for r in gake_by_hyoujun(children=1, spouse=True):
        print(f"{r['平均標準報酬額']:12,d}円 {r['3級の合計']:9,d}円 "
              f"{r['2級の合計']:9,d}円 {r['差']:9,d}円 {r['倍率']:5.2f}倍  "
              + ("効いている" if r["最低保障が効いたか"] else "外れている"))
    print(f"  → 線から上では、2級にも3級にも**同じ報酬比例**が乗るので、"
          f"差は「1階ぶん」の {gake_atama_uchi(children=1, spouse=True):,}円 "
          f"（障害基礎年金＋配偶者加給）で頭打ちです。"
          f"**線より下では3級だけが {GRADE3_MIN:,}円 で止まっている**ので、"
          f"報酬が増えるほど崖は開きます")

    print("\n=== 20歳前の傷病。**線を動かすのは扶養親族、崖を高くするのは子**"
          "（2級・扶養親族＝子として）===")
    print(f"{'人数':>4s} {'半額停止の線':>12s} {'全額停止の線':>12s} "
          f"{'基礎年金':>10s} {'半額停止の崖':>12s} {'全額停止の崖':>12s}")
    for r in fuyo_gake_grid(2):
        print(f"{r['人数']:3d}人 {r['半額停止の線']:11,d}円 "
              f"{r['全額停止の線']:11,d}円 {r['基礎年金']:9,d}円 "
              f"{r['半額停止の崖']:11,d}円 {r['全額停止の崖']:11,d}円")
    rows = fuyo_gake_grid(2)
    gaps = {r["全額停止の線"] - r["半額停止の線"] for r in rows}
    print(f"  → **2本の線の間隔は、人数が変わっても "
          f"{sorted(gaps)[0]:,}円 のまま**です"
          f"（{ZENGAKU_TEISHI:,} − {HANGAKU_TEISHI:,}）。"
          "**どちらの線も同じ扶養親族加算で動く**ので、間隔は動きません")
    step = fuyo_ippo(2)
    print(f"  → 1人増えると、**線は {step['線の動き']:,}円 上がり、"
          f"半額停止の崖は {step['半額の崖の動き']:,}円 高くなります**"
          f"（全額停止の崖は {step['全額の崖の動き']:,}円）。"
          f"**上がり方のほうが速いので、こえにくくはなります。**"
          f"ただし第3子からは、線は同じ {step['第3子での線の動き']:,}円 上がるのに"
          f"崖の伸びは {step['第3子での半額の崖の動き']:,}円 まで落ちます"
          f"（子の加算が {CHILD_ADD_1_2:,}円 から {CHILD_ADD_3_ON:,}円 に減るため）")

    print("\n=== 家族が増えると**倍率は下がるのに、金額の差は1円も動かない**"
          "（平均標準報酬額 300,000円・300月）===")
    h = sa_ittei_hyou(300_000, 300)
    for r in h["行"]:
        print(f"  子{r['子の人数']}人・配偶者{'あり' if r['配偶者'] else 'なし'}"
              f"  2級 {r['2級の合計']:>9,}円"
              f"  → 1級 {r['1級の合計']:>9,}円"
              f"  倍率 {r['本当の倍率']:.4f}"
              f"  → **差 {r['差']:>8,}円**"
              f"（定額 {r['定額の部分']:>7,}円"
              f" ＋ 報酬比例の4分の1 {r['報酬比例の4分の1']:>7,}円）")
    lo, hi = h["倍率の幅"]
    print(f"  → 倍率は {hi:.4f} から {lo:.4f} まで下がるのに、"
          f"**差は {h['差の種類'][0]:,}円 の1つきり**です。"
          f"定額の加算は1級にも2級にも**同じ額**乗るので、**引き算で消えます。**"
          f"**「1級になっても割合はあまり増えない」と"
          f"「1級になれば誰でも同じ額だけ増える」は、両方とも本当**です")

    print("\n=== 報酬がゼロの人が受け取る4つの額は、"
          "**204,000円の等差**で 6:5:4:3 に並ぶ ===")
    y = yuka()
    for r in y["行"]:
        print(f"  {r['名前']:<12}  {r['額']:>10,}円"
              f"  ＝ {y['公差']:,}円 × **{int(r['公差の何倍'])}**"
              f"   （{r['根拠']}）")
    sashi = " / ".join(f"{d:,}円" for d in y["差"])
    print(f"  → 隣どうしの差はどこも {y['公差']:,}円 ちょうど（{sashi}）。"
          f"**別々の条文から出てきた4つが、等差数列になります。**"
          f"公差の {y['公差']:,}円 は 816,000円 の4分の1で、"
          f"**上の節の「定額の部分」と同じ数**です")

    print("\n=== 同じ障害手当金でも、**3級とはどんな報酬でも2年、"
          "2級とは報酬で動いてV字を描く**（子なし・配偶者なし・300月）===")
    soko = teatekin_vs_2kyuu_soko(300)
    for hyoujun in (0, 150_000, soko["1年を割る下端"], 300_000,
                    soko["底の平均標準報酬額"], 400_000,
                    soko["1年に戻る上端"], 800_000, 2_000_000):
        v = teatekin_vs_2kyuu(hyoujun, 300)
        mark = "  ← **底**" if hyoujun == soko["底の平均標準報酬額"] else ""
        if hyoujun in (soko["1年を割る下端"], soko["1年に戻る上端"]):
            mark = "  ← **1年ちょうど**"
        print(f"  平均標準報酬額 {hyoujun:>9,}円"
              f"  手当金 {v['手当金']:>10,}円"
              f"  2級の年額 {v['2級の年額']:>9,}円"
              f"  → 2級と並ぶ **{v['2級と並ぶ年数']:.4f}年**"
              f"  ／ 3級と並ぶ {v['3級と並ぶ年数']:.2f}年{mark}")
    print(f"  → 手当金も3級も**報酬比例の定数倍**なので、"
          f"3級とは報酬が約分で消えて誰でも2年です。"
          f"**2級には約分の効かない障害基礎年金が乗る**ので動きます —— "
          f"下がって、**{soko['底の平均標準報酬額']:,}円 で底**（ちょうど 6/7年）、"
          f"そこから上がって2年に近づく。"
          f"底は**3級の最低保障が外れる線と同じ1点**です")
    print(f"  → **{soko['1年を割る下端']:,}円 から {soko['1年に戻る上端']:,}円 "
          f"の帯にいる人は、手当金が2級の1年ぶんにも届きません。**"
          f"帯の下端は報酬比例が基礎年金の半分（{soko['下端の報酬比例']:,}円）、"
          f"上端は基礎年金と同額（{soko['上端の報酬比例']:,}円）になる点で、"
          f"**上端の平均標準報酬額は下端のちょうど2倍**です")

    print("\n=== 同じ障害・同じ等級でも、入っていた制度で額が変わる"
          "（平均標準報酬額 300,000円・300月・配偶者あり）===")
    for grade in (1, 2, 3):
        k = kousei_no_umu(grade, 300_000, 300, children=1, spouse=True)
        nashi = "0円（**3級は基礎年金が無いので、厚生年金に入っていない人は0円**）" \
            if grade == 3 else f"{k['厚生年金なし']:,}円"
        print(f"  {grade}級  厚生年金あり {k['厚生年金あり']:>10,}円"
              f"  ／ なし {nashi}"
              f"  → 差 {k['差']:>9,}円")
    print("  → **3級は障害厚生年金にしかありません。**"
          "国民年金だけの人は、同じ障害の重さでも**3級では1円も出ません**")

    L3 = shobyo_kieru_line(3)
    print(f"\n=== 障害年金をもらうと、傷病手当金は差額だけになる。"
          f"**3級でも、標準報酬月額 {L3['線']:,}円 までは1円も出ない**"
          f"（同じ病気・300月）===")
    print(f"{'標準報酬月額':>13s} {'傷病手当金の日額':>16s} {'年金の日額':>11s} "
          f"{'実際に出る額':>13s} {'残る割合':>9s}")
    for r in shobyo_chousei_grid(3):
        print(f"{r['標準報酬月額']:12,d}円 {r['傷病手当金の日額']:15,d}円 "
              f"{r['年金の日額']:10,d}円 {r['実際に出る傷病手当金']:12,d}円 "
              f"{r['残る割合']:8.2%}"
              + ("  ← **1円も出ない**" if r["1円も出ないか"] else ""))
    print(f"  → 健康保険法108条4項は、**年金額を{SHOBYO_DIVISOR}で割った額**を"
          f"傷病手当金から引きます。3級の最低保障 {GRADE3_MIN:,}円 は"
          f"日額 {nenkin_nichigaku(GRADE3_MIN):,}円 —— "
          f"**報酬が低い人ほど、この定額に食われます。**"
          f"標準報酬月額 {L3['線']:,}円 までは丸ごと消え、"
          f"{L3['線の1つ上']:,}円 の人が受け取るのは"
          f"**1日 {L3['線の1つ上で出る額']:,}円**です")
    print(f"{'等級・家族':>18s} {'消える上限':>11s} {'そこでの年金':>13s} "
          f"{'1つ上で出る日額':>16s}")
    for grade, children, spouse, label in ((3, 0, False, "3級"),
                                           (2, 0, False, "2級"),
                                           (1, 0, False, "1級"),
                                           (2, 2, True, "2級・子2人・配偶者")):
        k = shobyo_kieru_line(grade, children=children, spouse=spouse)
        print(f"{label:>18s} {k['線']:10,d}円 {k['線での年金の年額']:12,d}円 "
              f"{k['線の1つ上で出る額']:15,d}円")
    print("  → **重い等級ほど、傷病手当金の消える帯は広くなります。**"
          "子の加算も配偶者加給も定額のまま年金に乗って、そのまま差し引かれるので、"
          "**家族が多い人ほど、傷病手当金は先に消えます** —— "
          "1.25倍の話とは逆に、ここでは**定額の加算が効きすぎます**")

    W = shobyo_tomaru_wariai()
    print(f"\n=== 3級で止まる傷病手当金は、"
          f"**最低保障が外れた帯では「報酬によらず {W['止まる割合']:.2%}」**"
          f"（決めるのは加入月数だけ）===")
    print(f"{'標準報酬月額':>13s} {'傷病手当金の日額':>16s} {'止まる額':>10s} "
          f"{'止まる割合':>10s}")
    for pay in (400_000, 500_000, 550_000, 650_000):
        r = shobyo_chousei(pay, 3)
        print(f"{pay:12,d}円 {r['傷病手当金の日額']:15,d}円 "
              f"{r['止まる額']:9,d}円 {1 - r['残る割合']:9.2%}")
    print(f"  → 傷病手当金の日額は **月額 ÷ {SHOBYO_DAILY_DIVISOR}**、"
          f"3級の日額は **月額 × {ACCRUAL} × 月数 ÷ {SHOBYO_DIVISOR}**。"
          f"**割ると報酬が約分で消えて、`乗率 × 月数 ÷ 8` だけが残ります。**"
          f"だから「いくら止まるか」は人それぞれなのに、"
          f"**「何割 止まるか」は誰でも同じ**です")
    print(f"{'加入月数':>8s} {'止まる割合':>10s} {'残る割合':>10s} "
          f"{'最低保障が外れる線':>18s}")
    for r in shobyo_tomaru_wariai_grid():
        print(f"{r['月数']:7d}月 {r['止まる割合']:9.2%} {r['残る割合']:9.2%} "
              f"{r['最低保障が外れる線']:17,d}円")
    rows = shobyo_tomaru_wariai_grid()
    step = rows[1]["止まる割合"] - rows[0]["止まる割合"]
    print(f"  → **60月 長く入っているごとに、止まる割合は {step:.2%} ずつ増えます**"
          f"（どこも同じ幅 ＝ 月数の1次式）。"
          f"**長く働いた人ほど、休んだときに手元へ残る割合は小さくなります。**"
          f"帯の中（最低保障が効いている側）は逆で、"
          f"報酬が上がるほど止まる割合は下がります")

    Z = teatekin_zenbu_tomaru_line()
    I = teatekin_tomaru_ittei()
    print(f"\n=== 障害手当金（一時金）は差額ではなく**日数**で効く。"
          f"標準報酬月額 {Z['線']:,}円 までは、"
          f"**{Z['上限の日数']}日 ぶんが丸ごと消える**（300月）===")
    print(f"{'標準報酬月額':>13s} {'障害手当金':>12s} {'傷病手当金の日額':>16s} "
          f"{'止まる日数':>11s} {'残る日数':>10s}")
    for r in teatekin_tomaru_grid():
        print(f"{r['標準報酬月額']:12,d}円 {r['障害手当金']:11,d}円 "
              f"{r['傷病手当金の日額']:15,d}円 {r['止まる日数']:10.2f}日 "
              f"{r['残る日数']:9.2f}日"
              + ("  ← **全部 消える**" if r["上限を全部 止めるか"] else ""))
    print(f"  → 健康保険法108条5項は、**傷病手当金の合計が障害手当金の額に"
          f"達するまで**支給しません。障害手当金の最低保障 "
          f"{GRADE3_MIN * TEATE_MULTIPLE:,}円 は定額なので、"
          f"**報酬が低い人ほど、止まる日数が長くなります** —— "
          f"{Z['線']:,}円 の人は {Z['線での止まる日数']:.2f}日 で"
          f"{Z['上限の日数']}日 を越え、**1円も受け取れません。**"
          f"{Z['線'] + 1_000:,}円 になって、やっと "
          f"{Z['線の1つ上で残る日数']:.2f}日 ぶんが戻ります")
    print(f"  → 最低保障が外れる {I['最低保障が外れる線']:,}円 から上では、"
          f"障害手当金も傷病手当金も**報酬に比例**するので、"
          f"止まる日数は **どの報酬でも {I['止まる日数']:.2f}日**"
          f"（＝ {ACCRUAL} × {I['月数']}月 × {TEATE_MULTIPLE} × "
          f"{SHOBYO_DAILY_DIVISOR}）。"
          f"**一時金をもらった人は、そこから約5か月ぶん、"
          f"傷病手当金の口が閉じます**")


if __name__ == "__main__":
    main()
