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
]

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
