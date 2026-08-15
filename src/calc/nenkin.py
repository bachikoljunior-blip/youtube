"""老齢年金の繰下げ・繰上げが、いつ得に変わるのかを計算する。

狙いは「繰下げると42パーセント増える」を紹介することではない。それはどこにでもある。
ここで出したいのは **その増額を取り返し終わる年齢** ——損益分岐点を、
開始年齢1か月きざみで全部出したもの。

--------------------------------------------------------------------------
広く出回っている数字と、何が違うのか
--------------------------------------------------------------------------
よく見るのは「70歳まで繰り下げると81歳11か月で追いつく」という一点だけ。
これは **額面** の比較で、しかも70歳という区切りの良い1点しか見ていない。

実際には二つずれる。

1. **手取りで見ると分岐点は後ろに動く。** 年金は雑所得として課税され、
   国民健康保険料や介護保険料の算定にも入る。増えた額の全部が手に入るわけではない。
   額面で追いついても、手取りではまだ追いついていない。

2. **繰下げは1か月きざみで選べる。** 65歳0か月から75歳0か月まで121通りある。
   「70歳」だけを見るのは、121分の1しか見ていないということ。

そこでここでは、**121通りすべての損益分岐点**を、額面と手取りの両方で出す。
どこにも出ていないのは、この表そのもの。

--------------------------------------------------------------------------
なぜ手取り率が分岐点を後ろに動かすのか
--------------------------------------------------------------------------
直感に反するが、**手取り率が一律なら分岐点は動かない。** 両方に同じ率が掛かる
だけなので、比の交点は変わらない。

動くのは、**繰り下げて年金額が上がると手取り率そのものが下がる**から。
課税所得が増えて税率区分が上がり、保険料の算定基礎も上がる。
つまり増額分には、元の年金より重い率が掛かる。ここが効く。

だからこの計算では、手取り率を「額に応じて変わるもの」として扱う。
一律の率で計算すると分岐点は動かず、それでは何も言っていないのと同じになる。

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
国民年金法・厚生年金保険法の繰上げ・繰下げの規定。

  繰下げ  1か月あたり **0.7パーセント** 増（65歳超〜75歳まで、最大 +84.0%）
  繰上げ  1か月あたり **0.4パーセント** 減（60歳〜65歳未満、最大 −24.0%）

繰下げの上限が75歳になったのは令和4年4月から（昭和27年4月2日以降生まれが対象）。
繰上げの減額率が0.4パーセントなのは昭和37年4月2日以降生まれ。
それ以前の生まれは繰上げ0.5パーセントで、最大−30パーセント。ここでは0.4で計算し、
生年で変わることを必ず画面に出す。

**増額率そのものは終身続く。** 一度繰り下げれば、その率のまま生涯もらう。
分岐点より長く生きれば得、短ければ損。ここは賭けであって、正解は無い。

手取り率は制度の値ではなく **こちらの前提** なので、必ず前提として画面に出す。
裏の取れない数字は出さない、という方針どおり、ここは「仮定」と明示する。
"""
from __future__ import annotations

from dataclasses import dataclass

ASSUMPTIONS = [
    "繰下げは1か月あたり0.7パーセント増、繰上げは1か月あたり0.4パーセント減で計算しています",
    "繰上げの0.4パーセントは昭和37年4月2日以降に生まれた人の率です。それ以前は0.5パーセントです",
    "繰下げの上限が75歳なのは昭和27年4月2日以降に生まれた人です",
    "増額率も減額率も、一度決まると生涯そのままです",
    "手取り率は制度の値ではなく、この計算での仮定です。年額78万円で100パーセント、"
    "120万円で96パーセント、180万円で91パーセント、250万円で87パーセント、"
    "350万円で83パーセント、500万円で79パーセントとして置き、あいだは線形で補っています",
    "在職老齢年金による支給停止、加給年金、振替加算は入れていません",
    "分岐点は月単位で、累計が追い抜いた最初の月を書いています",
    "70歳繰下げの分岐点はよく81歳11か月と紹介されます。ここでは81歳10か月になりますが、"
    "これは月の数えはじめをどちらに置くかの違いで、1か月ずれます。どちらも間違いではありません",
]

# 制度の値
RATE_UP_PER_MONTH = 0.007       # 繰下げ 1か月あたり
RATE_DOWN_PER_MONTH = 0.004     # 繰上げ 1か月あたり（昭和37年4月2日以降生まれ）
RATE_DOWN_PER_MONTH_OLD = 0.005  # それ以前の生まれ
BASE_AGE = 65
MAX_DEFER_AGE = 75
MIN_ADVANCE_AGE = 60

# 手取り率の仮定。額が上がるほど下がる。詳しくは冒頭の説明。
# 年額（万円）→ 手取り率。あいだは線形で補う。
NET_RATE_POINTS = [
    (78.0, 1.000),    # 老齢基礎年金の満額程度。公的年金等控除と基礎控除でほぼ課税されない
    (120.0, 0.960),
    (180.0, 0.910),
    (250.0, 0.870),
    (350.0, 0.830),
    (500.0, 0.790),
]


@dataclass(frozen=True)
class Plan:
    """受給開始をずらしたときの1つの選択肢。"""

    months_from_65: int    # 正が繰下げ、負が繰上げ
    rate: float            # 65歳を1.0としたときの倍率

    @property
    def age_text(self) -> str:
        total = BASE_AGE * 12 + self.months_from_65
        return f"{total // 12}歳{total % 12}か月"


def _clamp_rate(annual_man: float) -> float:
    """年額（万円）から手取り率を補間する。"""
    points = NET_RATE_POINTS
    if annual_man <= points[0][0]:
        return points[0][1]
    if annual_man >= points[-1][0]:
        return points[-1][1]
    for (x0, y0), (x1, y1) in zip(points, points[1:]):
        if x0 <= annual_man <= x1:
            span = x1 - x0
            return y0 + (y1 - y0) * ((annual_man - x0) / span)
    return points[-1][1]


def rate_for(months_from_65: int, born_before_s37: bool = False) -> float:
    """65歳を1.0としたときの倍率。繰上げは負の月数で渡す。"""
    if months_from_65 >= 0:
        return 1.0 + RATE_UP_PER_MONTH * months_from_65
    down = RATE_DOWN_PER_MONTH_OLD if born_before_s37 else RATE_DOWN_PER_MONTH
    return 1.0 + down * months_from_65


def check_tables() -> None:
    """制度の値がずれていないかを、法令で決まっている端の値で確かめる。

    表を書き写すときの列ずれ・桁落ちは、目で読み直しても見つからない。
    法令が名指ししている値だけを不変条件として置き、そこから外れたら止める。
    """
    at_70 = rate_for(60)
    at_75 = rate_for(120)
    at_60 = rate_for(-60)
    at_60_old = rate_for(-60, born_before_s37=True)

    for label, got, want in (
        ("70歳まで繰下げ", at_70, 1.42),
        ("75歳まで繰下げ", at_75, 1.84),
        ("60歳まで繰上げ", at_60, 0.76),
        ("60歳まで繰上げ（昭和37年4月1日以前）", at_60_old, 0.70),
        ("65歳", rate_for(0), 1.00),
    ):
        if abs(got - want) > 1e-9:
            raise ValueError(f"{label} の倍率が {got:.4f}。法令の値は {want:.2f}")

    # 繰下げは単調に増え、繰上げは単調に減る
    rates = [rate_for(m) for m in range(-60, 121)]
    for a, b in zip(rates, rates[1:]):
        if b <= a:
            raise ValueError("受給開始を遅らせたのに倍率が増えていない")

    # 手取り率は額が上がるほど下がる（ここが分岐点を動かす唯一の理由）
    nets = [_clamp_rate(x) for x in (78, 120, 180, 250, 350, 500)]
    for a, b in zip(nets, nets[1:]):
        if b > a:
            raise ValueError("年額が上がったのに手取り率が上がっている")
    if nets[0] <= nets[-1]:
        raise ValueError("手取り率が額によらず一定になっている。これでは分岐点が動かない")


def break_even(months_from_65: int, base_annual_man: float, net: bool = False) -> tuple[int, int] | None:
    """繰り下げたぶんを取り返し終わる年齢を (歳, 月) で返す。

    比較するのは **65歳から受け取り続けた場合の累計** と
    **繰り下げてから受け取り続けた場合の累計**。追い抜いた最初の月を返す。
    追い抜かないなら None（繰上げの場合は一生追い抜かない）。
    """
    if months_from_65 <= 0:
        return None

    base_rate = rate_for(0)
    plan_rate = rate_for(months_from_65)
    base_year = base_annual_man * base_rate
    plan_year = base_annual_man * plan_rate
    if net:
        base_year *= _clamp_rate(base_year)
        plan_year *= _clamp_rate(plan_year)

    base_month = base_year / 12.0
    plan_month = plan_year / 12.0

    # 65歳0か月を起点にした通算月数で走らせる。上限は120歳。
    total_base = 0.0
    total_plan = 0.0
    for m in range(0, (120 - BASE_AGE) * 12 + 1):
        total_base += base_month
        if m >= months_from_65:
            total_plan += plan_month
        if total_plan > total_base:
            age = BASE_AGE * 12 + m
            return age // 12, age % 12
    return None


def defer_grid(base_annual_man: float = 180.0, step_months: int = 12) -> list[dict]:
    """繰下げの月数ごとに、倍率と損益分岐点を額面・手取りの両方で出す。"""
    rows = []
    for m in range(step_months, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1, step_months):
        gross = break_even(m, base_annual_man, net=False)
        netbe = break_even(m, base_annual_man, net=True)
        plan = Plan(m, rate_for(m))
        rows.append({
            "開始": plan.age_text,
            "倍率": round(rate_for(m), 3),
            "年額": round(base_annual_man * rate_for(m), 1),
            "分岐点_額面": f"{gross[0]}歳{gross[1]}か月" if gross else "追いつかない",
            "分岐点_手取り": f"{netbe[0]}歳{netbe[1]}か月" if netbe else "追いつかない",
            "ずれ_月": (
                (netbe[0] * 12 + netbe[1]) - (gross[0] * 12 + gross[1])
                if gross and netbe else None
            ),
        })
    return rows


def worst_gap(base_annual_man: float = 180.0) -> dict:
    """額面と手取りで分岐点が一番開く開始月を探す。動画の主役になる数字。"""
    best = {"月数": 0, "ずれ_月": -1}
    for m in range(1, (MAX_DEFER_AGE - BASE_AGE) * 12 + 1):
        gross = break_even(m, base_annual_man, net=False)
        netbe = break_even(m, base_annual_man, net=True)
        if not gross or not netbe:
            continue
        gap = (netbe[0] * 12 + netbe[1]) - (gross[0] * 12 + gross[1])
        if gap > best["ずれ_月"]:
            best = {
                "月数": m,
                "開始": Plan(m, rate_for(m)).age_text,
                "分岐点_額面": f"{gross[0]}歳{gross[1]}か月",
                "分岐点_手取り": f"{netbe[0]}歳{netbe[1]}か月",
                "ずれ_月": gap,
            }
    return best


def advance_grid(base_annual_man: float = 180.0, step_months: int = 12) -> list[dict]:
    """繰上げの月数ごとに、倍率と年額の減り方を出す。"""
    rows = []
    for m in range(-step_months, -(BASE_AGE - MIN_ADVANCE_AGE) * 12 - 1, -step_months):
        r = rate_for(m)
        r_old = rate_for(m, born_before_s37=True)
        rows.append({
            "開始": Plan(m, r).age_text,
            "倍率": round(r, 3),
            "年額": round(base_annual_man * r, 1),
            "減る額": round(base_annual_man * (1 - r), 1),
            "倍率_昭37年4月1日以前": round(r_old, 3),
        })
    return rows


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過\n")

    base = 180.0
    print(f"=== 繰下げ（65歳で年{base}万円の場合）===")
    for row in defer_grid(base):
        print(f"  {row['開始']:>9s}  倍率{row['倍率']:.3f}  年額{row['年額']:6.1f}万  "
              f"額面{row['分岐点_額面']:>10s}  手取り{row['分岐点_手取り']:>10s}  "
              f"ずれ{row['ずれ_月']:>3d}か月")

    print("\n=== 額面と手取りで分岐点が一番開くところ ===")
    for k, v in worst_gap(base).items():
        print(f"  {k}: {v}")

    print(f"\n=== 繰上げ（65歳で年{base}万円の場合）===")
    for row in advance_grid(base):
        print(f"  {row['開始']:>9s}  倍率{row['倍率']:.3f}  年額{row['年額']:6.1f}万  "
              f"減る額{row['減る額']:5.1f}万")
