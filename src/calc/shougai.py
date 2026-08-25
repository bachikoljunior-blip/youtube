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
    step = fuyo_ippo(2)
    print(f"  → 1人増えると、**線は {step['線の動き']:,}円 上がり、"
          f"半額停止の崖は {step['半額の崖の動き']:,}円 高くなります**"
          f"（全額停止の崖は {step['全額の崖の動き']:,}円）。"
          f"**上がり方のほうが速いので、こえにくくはなります。**"
          f"ただし第3子からは、線は同じ {step['第3子での線の動き']:,}円 上がるのに"
          f"崖の伸びは {step['第3子での半額の崖の動き']:,}円 まで落ちます"
          f"（子の加算が {CHILD_ADD_1_2:,}円 から {CHILD_ADD_3_ON:,}円 に減るため）")

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


if __name__ == "__main__":
    main()
