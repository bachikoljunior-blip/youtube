"""**年5日しか使わない人は、勤続20年で241日を捨てている。**

一般の解説はここで止まります ——「有給は勤続6か月で10日、6年6か月で20日。
使わなかった分は翌年に繰り越せます。時効は2年です」。

**繰り越せる、で終わると、捨てている量が見えません。** 繰越は1年ぶんだけなので、
付与日数が消化日数を上回っている人は、**その差がそのまま毎年消えます。**
年20日もらって年5日使う人が失うのは、**勤続12年で121日、20年で241日**。
週5日勤務の労働日でかぞえて**11か月ぶん**です。

消える量は一定ではありません。**勤続2年6か月から始まり、7年6か月で毎年15日に達して
そこで止まります**（付与が20日で頭打ちになるため）。

もう1つ、比例付与の側に、誰も掛け算していない境目があります。
**年5日の時季指定義務は「10日以上付与された人」にかかります**（労働基準法39条7項）。
週4日勤務が10日に届くのは**勤続3年6か月**、週3日は**5年6か月**、
**週2日以下は勤続何年でも一生かかりません**（最大でも7日）。
同じ「パート」でも、週の日数が1日ちがうだけで、
**会社が5日取らせる義務を負うかどうかが変わります。**

## この計算で見ないもの（前提として画面に出す）

- 消化の順序は**古いほうから**としています。法律は順序を定めていないので、
  新しいほうから消化する運用だと、捨てる量はここより増えます。
- 出勤率8割の要件は、満たしている前提です（別の節で切ったときの影響を出します）。
- 会社が独自に上乗せしている日数、時間単位年休、計画的付与は入れていません。
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "労働基準法39条の法定日数だけで計算しています。会社が独自に上乗せしている分は入れていません",
    "出勤率8割の要件は満たしている前提です。8割を切った年は付与がゼロになります",
    "繰り越した有給は古いほうから使う前提です。新しいほうから使う運用だと、消える日数はここより増えます",
    "時効は2年なので、繰り越せるのは1年ぶんだけです。2年前の分は消えます",
    "週の所定労働日数は年間を通じて一定としています。途中で変わると付与日数も変わります",
    "時間単位年休や半日単位の取得は、日数に換算せずそのまま日でかぞえています",
]

# ---- 制度の値。**労働基準法39条・同施行規則24条の3。1999年以降変わっていない** ----
# 勤続の刻み（年）。6か月、1年6か月、…、6年6か月以上
SERVICE_YEARS: tuple[float, ...] = (0.5, 1.5, 2.5, 3.5, 4.5, 5.5, 6.5)

# 通常の労働者（週5日以上、または週30時間以上）。労働基準法39条1項・2項
FULL_TIME: tuple[int, ...] = (10, 11, 12, 14, 16, 18, 20)

# 比例付与。週の所定労働日数 → 勤続の刻みごとの日数（施行規則24条の3）
PRORATED: dict[int, tuple[int, ...]] = {
    4: (7, 8, 9, 10, 12, 13, 15),
    3: (5, 6, 6, 8, 9, 10, 11),
    2: (3, 4, 4, 5, 6, 6, 7),
    1: (1, 2, 2, 2, 3, 3, 3),
}

OBLIGATION_THRESHOLD = 10   # 39条7項。10日以上つく人に、年5日の時季指定義務
OBLIGATION_DAYS = 5         # 同項。会社が時季を指定して取らせる日数
CARRY_YEARS = 1             # 時効2年（115条）＝繰り越せるのは1年ぶん


def table_for(weekly_days: int) -> tuple[int, ...]:
    """週の所定労働日数ごとの付与日数の並び。5日以上は通常の労働者。"""
    if weekly_days >= 5:
        return FULL_TIME
    if weekly_days not in PRORATED:
        raise ValueError(f"週{weekly_days}日の表は無い")
    return PRORATED[weekly_days]


def granted_at(nth: int, weekly_days: int = 5) -> int:
    """`nth` 回目（0起点）の付与日数。7回目以降は頭打ちで同じ日数。"""
    row = table_for(weekly_days)
    return row[min(nth, len(row) - 1)]


def cumulative(years: int, weekly_days: int = 5) -> int:
    """勤続 `years` 年までに**付与された**日数の累計（使ったかどうかは見ない）。

    付与は勤続6か月のときが1回目で、以後1年ごと。**勤続20年なら20回**です。
    """
    return sum(granted_at(i, weekly_days) for i in range(years))


def obligation_starts(weekly_days: int) -> float | None:
    """年5日の時季指定義務がかかる最初の勤続年数。**一生かからないなら None。**"""
    row = table_for(weekly_days)
    for i, days in enumerate(row):
        if days >= OBLIGATION_THRESHOLD:
            return SERVICE_YEARS[i]
    return None


def expiry_run(years: int, used_per_year: int, weekly_days: int = 5) -> list[dict]:
    """毎年 `used_per_year` 日だけ使ったとき、時効で消える日数を年ごとに出す。

    繰越は1年ぶんだけなので、**前の年の残りは、その年に使い切らなければ消えます。**
    消化は古いほうから（`ASSUMPTIONS` に書いてあります）。
    """
    rows: list[dict] = []
    carry = 0          # 前の年に付与されて、まだ残っている日数
    lost_total = 0
    for i in range(years):
        grant = granted_at(i, weekly_days)
        used_from_carry = min(carry, used_per_year)
        used_from_grant = min(grant, used_per_year - used_from_carry)
        lost = carry - used_from_carry          # 使い残した繰越は、ここで時効
        lost_total += lost
        rows.append({
            "勤続年": SERVICE_YEARS[min(i, len(SERVICE_YEARS) - 1)] if i < len(
                SERVICE_YEARS) else i + 0.5,
            "その年の付与": grant,
            "使った日数": used_from_carry + used_from_grant,
            "時効で消えた日数": lost,
            "消えた日数の累計": lost_total,
        })
        carry = grant - used_from_grant
    return rows


def grid(weekly_days: int = 5) -> list[dict]:
    """勤続ごとの付与日数と、そこまでの累計。**図解がそのまま食える形。**"""
    out: list[dict] = []
    for i, years in enumerate(SERVICE_YEARS):
        out.append({
            "勤続年数": years,
            "付与日数": granted_at(i, weekly_days),
            "累計": cumulative(i + 1, weekly_days),
        })
    return out


def skip_one_year(years: int, skipped_nth: int, weekly_days: int = 5) -> dict:
    """出勤率8割を1年だけ切ったとき、生涯の累計が何日減るか。

    **勤続年数の時計は止まりません。**切った年の付与がゼロになるだけで、
    翌年は「切らなかった場合と同じ段」に戻ります。
    """
    full = cumulative(years, weekly_days)
    lost = granted_at(skipped_nth, weekly_days)
    return {
        "切らなかった場合の累計": full,
        "切った回": skipped_nth + 1,
        "その年に失った日数": lost,
        "切った場合の累計": full - lost,
    }


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    # 1. 法令が名指ししている値
    _checks.statutory(FULL_TIME[0], 10, "勤続6か月の付与日数",
                      source="労働基準法39条1項")
    _checks.statutory(FULL_TIME[-1], 20, "勤続6年6か月以上の付与日数",
                      source="労働基準法39条2項")
    _checks.statutory(OBLIGATION_DAYS, 5, "時季指定義務の日数",
                      source="労働基準法39条7項")
    _checks.statutory(OBLIGATION_THRESHOLD, 10, "時季指定義務がかかる付与日数",
                      source="労働基準法39条7項")
    _checks.statutory(PRORATED[4][0], 7, "週4日・勤続6か月の付与日数",
                      source="労働基準法施行規則24条の3")
    _checks.statutory(PRORATED[1][-1], 3, "週1日・勤続6年6か月の付与日数",
                      source="労働基準法施行規則24条の3")

    # 2. 表の形。**段の数が揃っていないと、勤続の刻みと対応が取れない**
    if len(SERVICE_YEARS) != len(FULL_TIME):
        raise _checks.TableError("勤続の刻みと通常の労働者の日数の段数が違う")
    for wd, row in PRORATED.items():
        if len(row) != len(SERVICE_YEARS):
            raise _checks.TableError(f"週{wd}日の段数が {len(row)}。刻みは {len(SERVICE_YEARS)} 段")
        _checks.ascending(row, f"週{wd}日の付与日数")
        _checks.greater(FULL_TIME[0], row[0], "通常の労働者の初回が比例付与の初回")
        _checks.greater(FULL_TIME[-1], row[-1], "通常の労働者の上限が比例付与の上限")
    _checks.ascending(FULL_TIME, "通常の労働者の付与日数")

    # 3. 週の日数が多いほど、同じ勤続でも日数が多いこと（表の列ずれを弾く）
    for i in range(len(SERVICE_YEARS)):
        _checks.increases_with(lambda wd: granted_at(i, wd), (1, 2, 3, 4, 5),
                               f"{SERVICE_YEARS[i]}年で、週の日数が増えたのに付与日数が増えていない")

    # 4. 計算の向き —— この計算の主題そのもの
    #    (a) 勤続が延びれば累計は増える
    _checks.increases_with(lambda y: cumulative(y), (1, 5, 10, 20), "勤続が延びたのに累計が増えていない")
    #    (b) **主題**: 付与より少なく使うと、差がそのまま毎年消える（定常状態）
    run = expiry_run(12, 5)
    steady = run[-1]
    _checks.rounding(steady["時効で消えた日数"], 20 - 5,
                     "勤続12年目に時効で消える日数（付与20日・消化5日）")
    #    (c) 使い切れば1日も消えない
    if any(r["時効で消えた日数"] for r in expiry_run(12, 20)):
        raise _checks.TableError("20日つく人が20日使っているのに、消えている日がある")
    #    (d) **主題**: 時季指定義務の境目が週の日数で動くこと。週2日以下は永久にかからない
    if obligation_starts(4) != 3.5:
        raise _checks.TableError(f"週4日で義務がかかるのは3年6か月のはず: {obligation_starts(4)}")
    if obligation_starts(3) != 5.5:
        raise _checks.TableError(f"週3日で義務がかかるのは5年6か月のはず: {obligation_starts(3)}")
    for wd in (1, 2):
        if obligation_starts(wd) is not None:
            raise _checks.TableError(f"週{wd}日は10日に届かないはず")
    #    (e) 1年切っても、時計は止まらない（翌年の付与が前年と同じ段に戻らない）
    s = skip_one_year(20, 3)
    _checks.greater(s["切らなかった場合の累計"], s["切った場合の累計"], "切らなかった累計が切った累計")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 年5日しか使わないと、毎年何日が時効で消えるか ===")
    for row in expiry_run(12, 5):
        print(f"  {row['勤続年']:>4}年  付与{row['その年の付与']:>3}日"
              f"  使用{row['使った日数']:>3}日"
              f"  消えた{row['時効で消えた日数']:>3}日"
              f"  累計{row['消えた日数の累計']:>4}日")

    print("\n=== 年5日の時季指定義務は、週の日数で「かかる年」が違う ===")
    print(f"  かかる条件は「その年の付与が{OBLIGATION_THRESHOLD}日以上」"
          f"（1年で{OBLIGATION_DAYS}日）")
    for wd in (5, 4, 3, 2, 1):
        starts = obligation_starts(wd)
        row = table_for(wd)
        top = row[-1]
        if starts is None:
            print(f"  週{wd}日  一生かからない  生涯の上限{top}日"
                  f"  {OBLIGATION_THRESHOLD}日まであと{OBLIGATION_THRESHOLD - top}日")
        else:
            nth = SERVICE_YEARS.index(starts)
            print(f"  週{wd}日  勤続{starts}年から  そのときの付与{row[nth]}日"
                  f"  そこまでの累計{cumulative(nth + 1, wd)}日")

    print("\n=== 勤続20年までに付与される日数の累計（週の日数べつ） ===")
    base = cumulative(20, 5)
    for wd in (5, 4, 3, 2, 1):
        c = cumulative(20, wd)
        print(f"  週{wd}日  累計{c:>4}日  通常との差 {base - c:>3}日"
              f"（{c / base * 100:4.1f}%）")

    print("\n=== 勤続ごとの付与日数と、そこまでの累計（通常の労働者） ===")
    for row in grid(5):
        print(f"  勤続{row['勤続年数']:>4}年  付与{row['付与日数']:>3}日  累計{row['累計']:>3}日")

    print("\n=== 出勤率8割を1年だけ切ると、生涯の累計は何日減るか ===")
    for nth in (0, 3, 6, 10):
        s = skip_one_year(20, nth)
        print(f"  {s['切った回']:>2}回目に切る  失う{s['その年に失った日数']:>3}日"
              f"  累計 {s['切らなかった場合の累計']}日 → {s['切った場合の累計']}日")
