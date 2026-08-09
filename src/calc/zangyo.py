"""残業代の割増賃金を、条文どおりに計算する。

狙いは「残業代の計算方法の解説」ではない。解説は無数にある。
ここで出したいのは **どこにも表になっていない数字** ——
「よくある誤った計算をされていると、年間いくら失うのか」を、
手当の額と残業時間の組み合わせで一枚の表にする。

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
労働基準法 37条    割増賃金。時間外25%以上、深夜25%以上、休日35%以上。
                   月60時間を超える時間外は50%以上（中小企業も2023年4月から適用）。
労働基準法 37条5項  割増賃金の算定基礎から除外できる賃金。
労働基準法施行規則 21条  同上。除外できるのは次の7つ **だけ**（限定列挙）。

    1 家族手当
    2 通勤手当
    3 別居手当
    4 子女教育手当
    5 住宅手当
    6 臨時に支払われた賃金
    7 1か月を超える期間ごとに支払われる賃金

--------------------------------------------------------------------------
この計算の肝（＝動画で言いたいこと）
--------------------------------------------------------------------------
上の7つは **名称ではなく実質で判断される**。ここが誤りの発生源になる。

  ・扶養家族の人数に関係なく一律で支給される「家族手当」は、
    家族手当として除外できない。算定基礎に **入れる**。
  ・住宅費用に応じて算定されていない一律定額の「住宅手当」も同じく、
    算定基礎に **入れる**。

名前だけを見て除外している場合、基礎賃金が低く出るので、
残業代は毎月少なく支払われる。差は1時間あたりでは小さく、
**年間で見て初めて見える大きさになる**。それを計算する。
"""
from __future__ import annotations

from dataclasses import dataclass

# 動画と説明欄にそのまま出す前提。ここを省くと「裏の取れない数字」になる。
ASSUMPTIONS = [
    "割増率は法定の下限（時間外25%、月60時間超の部分50%）で計算しています",
    "算定基礎から除外できる賃金は労働基準法37条5項と施行規則21条の7つに限られます",
    "一律支給の家族手当・住宅手当は、名称にかかわらず除外できないものとして扱っています",
    "1か月の平均所定労働時間は、年間所定休日から計算しています",
    "深夜割増と法定休日労働は含めていません。含めれば差はさらに広がります",
    "さかのぼれる期間は3年で計算しています（労働基準法115条の賃金請求権の時効）",
]

# 賃金請求権の時効。2020年4月の改正で2年→5年になったが、当分のあいだ3年。
# **改正が続く数字なので、変わったらここだけ直す**（docs/CONSTRAINTS.md B4）。
RECLAIM_YEARS = 3

# 法定の下限。これを下回る取り決めは無効になる。
RATE_OVERTIME = 0.25
RATE_OVERTIME_OVER_60 = 0.50
OVER_60_THRESHOLD = 60.0


@dataclass(frozen=True)
class Wage:
    """月給の内訳。円単位。"""

    base: int                 # 基本給
    role_allowance: int = 0   # 役職手当など、除外できない手当
    family_flat: int = 0      # 一律支給の家族手当（除外できない）
    housing_flat: int = 0     # 一律定額の住宅手当（除外できない）
    commute: int = 0          # 通勤手当（除外できる）

    def base_for_premium(self, *, mistaken: bool) -> int:
        """割増賃金の算定基礎になる月額。

        mistaken=True は、名称だけを見て家族手当と住宅手当を除いた場合。
        通勤手当はどちらでも除外できるので、常に除く。
        """
        total = self.base + self.role_allowance + self.family_flat + self.housing_flat
        if mistaken:
            total -= self.family_flat + self.housing_flat
        return total


# 労基法37条5項と施行規則21条が挙げる、割増賃金の算定基礎から除外できる手当。
# **ただし「個人ごとの事情に応じて支給される場合」に限る。**
# 一律定額で配っているものは、名前が家族手当でも除外できない。
EXCLUDABLE_NAMES = (
    "家族手当", "通勤手当", "別居手当", "子女教育手当", "住宅手当",
    "臨時に支払われた賃金", "1か月を超える期間ごとに支払われる賃金",
)


def allowance_grid(base: int = 268_000, scheduled: float = 163.3,
                   overtime_hours: float = 22.0) -> list[dict]:
    """**手当の種類べつに、一律支給だといくら変わるか。**

    検索語「残業代 計算 手当 含まれないもの」に答えるための表。

    除外できるかどうかは**名前では決まらない。**
    家族手当・住宅手当は、扶養人数や家賃に応じて変わるなら除外できるが、
    **全員に同額を配っているなら除外できない。**
    通勤手当は距離に応じるのが通常なので除外できる。
    役職手当は最初から除外の対象外。

    ここで出すのは「一律で配っているのに除外された場合、
    残業代が年いくら少なくなるか」。

    `shortfall_grid()` とは別の切り口。あちらは**手当の合計額**べつで、
    こちらは**手当の種類**べつ。
    2026-08-09、同じモジュールでも切り口が同じだと同じ図になると分かったので、
    数値が既存と重ならないことを確かめて額を選んである。
    """
    cases = [
        ("家族手当（一律）", 18_000, False),
        ("住宅手当（一律）", 23_000, False),
        ("役職手当", 31_000, False),
        ("通勤手当（実費）", 14_000, True),
        ("家族手当（扶養数で変動）", 18_000, True),
    ]
    rows = []
    for name, amount, excludable in cases:
        full = Wage(base=base, role_allowance=amount)
        correct = hourly_rate(full, scheduled, mistaken=False)
        # 除外できないものを除外した場合の単価
        wrong = hourly_rate(Wage(base=base), scheduled, mistaken=False)
        legal = excludable          # 法律上、除外してよいか
        diff_hour = 0.0 if legal else correct - wrong
        rows.append({
            "name": name,
            "amount": amount,
            "excludable": legal,
            "hourly_correct": round(correct),
            "hourly_if_excluded": round(wrong),
            "diff_per_hour": round(diff_hour),
            "annual_diff": round(diff_hour * RATE_OVERTIME * overtime_hours * 12),
        })
    return rows


def check_tables() -> None:
    """法令で決まっている割増率と、計算の向きを確かめる。

    このモジュールは表ではなく式でできているが、**式でも取り違えは起きる**。
    60時間超の率を通常の率と入れ替える、所定労働時間の分母を取り違える、
    一律手当を足すべきところで引く。どれも結果は一見それらしい数字になる。

    他の calc と同じく、法令が名指ししている値だけを不変条件に置く。
    calc_block() は台本を書かせる前にこれを呼ぶので、ここで止まれば
    壊れた数字で動画が作られることはない。
    """
    if RATE_OVERTIME != 0.25:
        raise ValueError(f"時間外の割増率が {RATE_OVERTIME}。労働基準法の値は 0.25")
    if RATE_OVERTIME_OVER_60 != 0.50:
        raise ValueError(f"月60時間超の割増率が {RATE_OVERTIME_OVER_60}。法定は 0.50")
    if OVER_60_THRESHOLD != 60.0:
        raise ValueError(f"割増率が上がる境目が {OVER_60_THRESHOLD} 時間。法定は 60 時間")
    if RATE_OVERTIME_OVER_60 <= RATE_OVERTIME:
        raise ValueError("60時間超の割増率が通常以下になっている")

    # 休日が多いほど所定労働時間は短くなり、単価は上がる
    a = monthly_scheduled_hours(105, 8.0)
    b = monthly_scheduled_hours(125, 8.0)
    if not b < a:
        raise ValueError("年間休日を増やしたのに所定労働時間が減っていない")

    # 一律手当を基礎に入れたほうが、残業代は必ず多くなる
    wage = Wage(base=250_000, family_flat=20_000, housing_flat=10_000)
    hours = monthly_scheduled_hours(120, 8.0)
    correct = monthly_overtime_pay(wage, hours, 30.0, mistaken=False)
    mistaken = monthly_overtime_pay(wage, hours, 30.0, mistaken=True)
    if not correct > mistaken:
        raise ValueError("一律手当を基礎に入れたのに残業代が増えていない")

    # 60時間を超えた1時間は、超える前の1時間より高い
    just_under = monthly_overtime_pay(wage, hours, 60.0, mistaken=False)
    just_over = monthly_overtime_pay(wage, hours, 61.0, mistaken=False)
    step_over = just_over - just_under
    step_under = just_under - monthly_overtime_pay(wage, hours, 59.0, mistaken=False)
    if not step_over > step_under:
        raise ValueError("60時間を超えた1時間の単価が上がっていない")

    # 手当の種類べつの表。**除外できるかは名前ではなく支給の仕方で決まる。**
    rows = allowance_grid()
    by = {r["name"]: r for r in rows}
    assert not by["家族手当（一律）"]["excludable"], "一律の家族手当が除外可になっている"
    assert by["家族手当（扶養数で変動）"]["excludable"], "変動する家族手当が除外不可になっている"
    assert by["通勤手当（実費）"]["excludable"], "通勤手当が除外不可になっている"
    assert not by["役職手当"]["excludable"], "役職手当が除外可になっている"
    # 除外できないものを除外すると、必ず単価が下がる（差が正）。
    for r in rows:
        if not r["excludable"]:
            assert r["diff_per_hour"] > 0, f"{r['name']}で差が出ていない"
            assert r["annual_diff"] > 0, f"{r['name']}の年間差が0"
        else:
            assert r["annual_diff"] == 0, f"{r['name']}は除外してよいので差は0のはず"


def monthly_scheduled_hours(annual_days_off: int, hours_per_day: float) -> float:
    """1か月の平均所定労働時間。

    (365 - 年間所定休日) × 1日の所定労働時間 ÷ 12
    """
    return (365 - annual_days_off) * hours_per_day / 12


def hourly_rate(wage: Wage, scheduled_hours: float, *, mistaken: bool) -> float:
    """1時間あたりの単価（割増前）。"""
    return wage.base_for_premium(mistaken=mistaken) / scheduled_hours


def monthly_overtime_pay(
    wage: Wage, scheduled_hours: float, overtime_hours: float, *, mistaken: bool
) -> float:
    """その月の残業代。月60時間を超える部分は割増率が上がる。"""
    rate = hourly_rate(wage, scheduled_hours, mistaken=mistaken)
    under = min(overtime_hours, OVER_60_THRESHOLD)
    over = max(overtime_hours - OVER_60_THRESHOLD, 0.0)
    return rate * (under * (1 + RATE_OVERTIME) + over * (1 + RATE_OVERTIME_OVER_60))


def annual_shortfall(
    wage: Wage, scheduled_hours: float, overtime_hours: float
) -> float:
    """一律手当を誤って除外された場合に、年間で失う額。"""
    correct = monthly_overtime_pay(wage, scheduled_hours, overtime_hours, mistaken=False)
    mistaken = monthly_overtime_pay(wage, scheduled_hours, overtime_hours, mistaken=True)
    return (correct - mistaken) * 12


def hours_error_shortfall(
    monthly_pay: int,
    annual_days_off: int,
    hours_per_day: float,
    assumed_hours: float,
    overtime_hours: float,
) -> dict:
    """所定労働時間を多く見積もられている場合の、年間の差額。

    もう一つのよくある誤り。1か月の平均所定労働時間は
    (365 - 年間所定休日) × 1日の所定労働時間 ÷ 12 で出すが、
    ここに実態より大きい数字（月21.7日×8時間＝173.3時間など）を使うと、
    時給が小さく出るので残業代も小さくなる。

    年間所定休日が多い会社ほど、正しい所定労働時間は小さくなり、
    差は大きくなる。
    """
    correct_hours = monthly_scheduled_hours(annual_days_off, hours_per_day)
    correct_rate = monthly_pay / correct_hours
    assumed_rate = monthly_pay / assumed_hours
    under = min(overtime_hours, OVER_60_THRESHOLD)
    over = max(overtime_hours - OVER_60_THRESHOLD, 0.0)
    weighted = under * (1 + RATE_OVERTIME) + over * (1 + RATE_OVERTIME_OVER_60)
    return {
        "correct_hours": correct_hours,
        "correct_rate": correct_rate,
        "assumed_rate": assumed_rate,
        "annual_shortfall": (correct_rate - assumed_rate) * weighted * 12,
    }


def reclaimable(
    wage: Wage, scheduled_hours: float, overtime_hours: float
) -> dict:
    """**さかのぼって請求できる額。**

    `annual_shortfall` は「1年でいくら失うか」を出す。こちらは
    **「いま請求すればいくら戻るか」**。同じ計算だが、視聴者から見ると別の話。

    2026-08-07 の実測で、「戻せる」と言う動画が「差がある」と言う動画より
    2倍伸びた（年末調整の還付が13時間で1510回、残業代の差額が37時間で764回）。
    **同じ数字でも、取り返せる側から見せるほうが効くかもしれない**（検証中）。
    """
    per_year = annual_shortfall(wage, scheduled_hours, overtime_hours)
    return {
        "per_year": per_year,
        "years": RECLAIM_YEARS,
        "total": per_year * RECLAIM_YEARS,
    }


def shortfall_grid(
    wage: Wage,
    scheduled_hours: float,
    allowance_totals: list[int],
    overtime_hours: list[float],
) -> list[dict]:
    """「一律手当の合計」×「月の残業時間」で、年間の差額を並べる。

    この表が動画の中身になる。手当の内訳は結果に影響しないので、
    家族手当と住宅手当の合計だけを動かす。
    """
    rows = []
    for allowance in allowance_totals:
        # 総額を変えずに、一律手当の有無だけを比べる。
        # そうしないと「手当が多い人ほど月給も高い」効果が混ざる。
        w = Wage(
            base=wage.base + wage.role_allowance - allowance,
            family_flat=allowance,
        )
        for hours in overtime_hours:
            rows.append(
                {
                    "allowance": allowance,
                    "overtime_hours": hours,
                    "hourly_correct": hourly_rate(w, scheduled_hours, mistaken=False),
                    "hourly_mistaken": hourly_rate(w, scheduled_hours, mistaken=True),
                    "annual_shortfall": annual_shortfall(w, scheduled_hours, hours),
                }
            )
    return rows


if __name__ == "__main__":
    # **ここが無かった（2026-08-05 に発覚）。** 関数を定義するだけで何も出力せず、
    # `calc_block` は空のコードブロックを返していた。台本を書く側は「使ってよい
    # 数字」がゼロの状態で書くことになり、**数字を発明させる状態だった。**
    # 数字を発明させないために作った仕組みが、このテーマでは開いていた。
    check_tables()
    print("制度の値の検査: 通過")

    # 前提の値はここに置く。ASSUMPTIONS と食い違わせないこと。
    days_off, per_day = 120, 8.0
    hours = monthly_scheduled_hours(days_off, per_day)
    print("\n=== 1か月の平均所定労働時間 ===")
    print(f"  年間所定休日{days_off}日・1日{per_day}時間 → {hours:.1f}時間")

    base = Wage(base=250_000, role_allowance=20_000)
    print("\n=== 一律手当を誤って除外された場合の年間の差額 ===")
    print(f"{'一律手当':>8s} {'残業':>6s} {'正しい時給':>10s} {'誤った時給':>10s} {'年間の差':>10s}")
    for row in shortfall_grid(base, hours, [10_000, 20_000, 30_000, 50_000], [10.0, 20.0, 45.0, 80.0]):
        print(f"{row['allowance']:8,d}円 {row['overtime_hours']:5.0f}h "
              f"{row['hourly_correct']:9,.0f}円 {row['hourly_mistaken']:9,.0f}円 "
              f"{row['annual_shortfall']:9,.0f}円")

    print(f"\n=== さかのぼって請求できる額（時効{RECLAIM_YEARS}年） ===")
    print(f"{'一律手当':>8s} {'残業':>6s} {'1年ぶん':>10s} {'3年ぶん':>11s}")
    for allowance in (10_000, 20_000, 30_000, 50_000):
        w = Wage(base=base.base + base.role_allowance - allowance, family_flat=allowance)
        for ot in (20.0, 45.0):
            r = reclaimable(w, hours, ot)
            print(f"{allowance:8,d}円 {ot:5.0f}h {r['per_year']:9,.0f}円 {r['total']:10,.0f}円")

    print("\n=== 所定労働時間を多く見積もられている場合の年間の差額 ===")
    print(f"{'月給':>9s} {'年間休日':>6s} {'誤った所定':>8s} {'正しい所定':>8s} {'残業':>5s} {'年間の差':>10s}")
    for off in (105, 120, 125):
        for assumed in (173.3, 180.0):
            r = hours_error_shortfall(300_000, off, per_day, assumed, 20.0)
            print(f"{300_000:8,d}円 {off:5d}日 {assumed:7.1f}h "
                  f"{r['correct_hours']:7.1f}h {20:4.0f}h {r['annual_shortfall']:9,.0f}円")

    print("\n=== 手当の種類べつ 一律だと除外できない ===")
    print(f"{'手当':>26}{'月額':>9}{'除外':>6}{'正しい単価':>11}{'除外した単価':>13}{'年間の差':>11}")
    for r in allowance_grid():
        print(f"{r['name']:>26}{r['amount']:>8,}円{'  可' if r['excludable'] else ' 不可':>6}"
              f"{r['hourly_correct']:>10,}円{r['hourly_if_excluded']:>12,}円"
              f"{r['annual_diff']:>10,}円")
    print("  ※ 除外できるかは名前ではなく支給の仕方で決まる。")
    print("     扶養人数や家賃に応じて変わるなら除外できる。全員一律なら除外できない。")
