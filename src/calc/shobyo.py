"""傷病手当金で、実際に手元にいくら残るかを計算する。

**2026-08-15 に追加。** 狙いは `taishoku.py` と同じで、在庫の数ではなく
**題材の幅**（いまの9本がほぼ全部「現役世代の給与まわり」に寄っていた）。

## この題材を選んだ理由は、計算そのものにある

一般の解説は、ここで止まる。

    「傷病手当金は、給料のおよそ3分の2が受け取れます」

**その先が抜けている。** 休んでいるあいだも、

  - **社会保険料の本人負担は続く**（免除されるのは育児休業と産前産後休業だけ）
  - **住民税も前年の所得で決まる**ので、休んでいることと無関係にかかる

一方で、

  - **傷病手当金は非課税**（所得税も住民税もかからない）
  - **雇用保険料はかからない**（賃金が支払われていないため）

つまり「3分の2」は**額面の話**で、**手元に残る割合はそれより低い。**
その割合はどこにも表になっていない。**そこを金額で出す。**

## 計算の中身（健康保険法99条・協会けんぽの支給額の求め方）

    日額 = 支給開始日以前の継続した12か月の標準報酬月額の平均 ÷ 30（10円未満四捨五入）
           × 2/3（1円未満四捨五入）

    支給は**連続した3日の待期のあと、4日目から。**
    通算して1年6か月（546日）まで。

## 入れなかったもの

**障害年金・老齢年金との調整、労災（業務上のけがや病気）、任意継続、
退職後の継続給付は入れない。** どれも条件が別立てで、1本の動画に2つの制度を
混ぜると前提が追えなくなる（`iryohi.py` と同じ方針）。

**保険料率は入力に逃がしている**（`docs/CONSTRAINTS.md` B4）。
健康保険料率は都道府県ごとに違い、毎年3月に変わるため、
**この計算では率を引数にして、既定値を画面に出す。**
"""
from __future__ import annotations

ASSUMPTIONS = [
    "1日あたりの額は、支給開始日以前12か月の標準報酬月額の平均を30で割り、3分の2をかけて計算しています",
    "30で割った額は10円未満を四捨五入し、3分の2をかけた額は1円未満を四捨五入しています",
    "連続した3日間の待期のあと、4日目から支給されるものとして計算しています",
    "支給は通算1年6か月、日数にして546日を上限としています",
    "傷病手当金は非課税なので、所得税と住民税はかかりません",
    "休んでいるあいだも健康保険料と厚生年金保険料の本人負担は続くものとして引いています",
    "健康保険料の本人負担は5パーセント、厚生年金保険料の本人負担は9.15パーセントで計算しています",
    "介護保険料の本人負担は0.8パーセントとし、40歳以上のときだけ引いています",
    "雇用保険料は賃金が支払われないため、かからないものとしています",
    "住民税は前年の所得で決まるため休んでも減りませんが、金額は人によって違うので入力として扱っています",
    "労災、退職後の継続給付、障害年金や老齢年金との調整は含めていません",
]

# 制度の値。**長く動いていないもの**だけをここに置く。
WAITING_DAYS = 3          # 待期（連続した3日間）
BENEFIT_RATIO = 2 / 3     # 支給割合
MAX_DAYS = 546            # 通算1年6か月

# 保険料率の本人負担（**改正が続くので既定値。呼ぶ側で差し替えられる**）
HEALTH_RATE = 0.05        # 健康保険（協会けんぽ 約10% の半分。都道府県で違う）
PENSION_RATE = 0.0915     # 厚生年金（18.3% の半分。固定）
CARE_RATE = 0.008         # 介護保険（40歳以上。約1.6% の半分）


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。**壊れた数字で台本を書かせない。**"""
    if not 0 < BENEFIT_RATIO < 1:
        raise ValueError(f"支給割合が範囲外: {BENEFIT_RATIO}")
    if WAITING_DAYS < 0 or MAX_DAYS <= WAITING_DAYS:
        raise ValueError("待期と上限日数の大小が逆")
    if PENSION_RATE <= 0 or HEALTH_RATE <= 0:
        raise ValueError("保険料率が0以下")

    # 日額の丸め。標準報酬30万 → 30万÷30 = 1万 → 2/3 = 6,667円
    if daily(300_000) != 6_667:
        raise ValueError(f"標準報酬30万円の日額が6,667円にならない: {daily(300_000)}")
    # 10円未満四捨五入が効いていること（26万 ÷ 30 = 8,666.7 → 8,670）
    if daily(260_000) != round(8_670 * BENEFIT_RATIO):
        raise ValueError("30で割った額の10円未満四捨五入が効いていない")

    # 待期の3日は出ない
    if paid_days(3) != 0:
        raise ValueError("待期3日で支給日数が0になっていない")
    if paid_days(4) != 1:
        raise ValueError("4日目に1日ぶん出ていない")
    # 上限を超えない
    if paid_days(1000) != MAX_DAYS:
        raise ValueError("通算の上限を超えている")

    # 標準報酬が上がれば手取りも上がる
    if not net_month(400_000)["net"] > net_month(300_000)["net"]:
        raise ValueError("標準報酬が上がったのに手元に残る額が増えていない")
    # 40歳以上のほうが手元に残る額は少ない
    if not net_month(300_000, care=True)["net"] < net_month(300_000)["net"]:
        raise ValueError("介護保険料を引いたのに手元が減っていない")
    # 手取り率は支給割合を必ず下回る（保険料が引かれるため）
    if not net_month(300_000)["net_ratio"] < BENEFIT_RATIO:
        raise ValueError("保険料を引いたのに手取り率が3分の2を下回っていない")


def daily(standard_pay: int) -> int:
    """1日あたりの傷病手当金。**丸めの順番が決まっている。**

    標準報酬月額の平均 ÷ 30 を**10円未満四捨五入**してから 2/3 をかけ、
    その結果を**1円未満四捨五入**する。順番を入れ替えると1円ずれる。
    """
    base = round(standard_pay / 30, -1)
    return round(base * BENEFIT_RATIO)


def paid_days(absent_days: int) -> int:
    """支給される日数。**最初の3日は出ない。** 通算546日で頭打ち。"""
    return max(0, min(absent_days - WAITING_DAYS, MAX_DAYS))


def premiums(standard_pay: int, care: bool = False,
             health_rate: float = HEALTH_RATE,
             pension_rate: float = PENSION_RATE) -> dict:
    """休んでいるあいだも引かれる、社会保険料の本人負担（1か月ぶん）。"""
    health = int(standard_pay * health_rate)
    pension = int(standard_pay * pension_rate)
    nursing = int(standard_pay * CARE_RATE) if care else 0
    return {"health": health, "pension": pension, "care": nursing,
            "total": health + pension + nursing}


def net_month(standard_pay: int, care: bool = False, resident_tax: int = 0,
              days: int = 30) -> dict:
    """1か月まるごと休んだときに、**手元に残る額**。

    傷病手当金は非課税だが、社会保険料と住民税は休んでも減らない。
    """
    benefit = daily(standard_pay) * days
    prem = premiums(standard_pay, care)
    net = benefit - prem["total"] - resident_tax
    return {
        "standard_pay": standard_pay,
        "daily": daily(standard_pay),
        "benefit": benefit,
        "premiums": prem["total"],
        "resident_tax": resident_tax,
        "net": net,
        "benefit_ratio": benefit / standard_pay,
        "net_ratio": net / standard_pay,
    }


def daily_grid() -> list[dict]:
    """標準報酬月額べつの日額と、1か月ぶんの額面。"""
    check_tables()
    return [
        {"standard_pay": p, "daily": daily(p), "month": daily(p) * 30,
         "ratio": daily(p) * 30 / p}
        for p in (200_000, 260_000, 300_000, 380_000, 440_000, 500_000, 650_000)
    ]


def absence_grid(standard_pay: int) -> list[dict]:
    """休んだ日数べつに、実際に受け取る額。**最初の3日は出ない。**"""
    check_tables()
    d = daily(standard_pay)
    return [
        {"absent": n, "paid": paid_days(n), "amount": d * paid_days(n),
         "lost": d * min(n, WAITING_DAYS)}
        for n in (3, 4, 7, 14, 30, 60, 90, 180)
    ]


def net_grid(care: bool = False, resident_tax: int = 0) -> list[dict]:
    """**「3分の2」がいくらまで目減りするか。** この表がどこにも無い。"""
    check_tables()
    return [net_month(p, care=care, resident_tax=resident_tax)
            for p in (200_000, 260_000, 300_000, 380_000, 440_000, 500_000)]


def limit_grid() -> list[dict]:
    """通算1年6か月を使い切るまでに、合計いくら受け取れるか。"""
    check_tables()
    out = []
    for p in (200_000, 300_000, 380_000, 500_000):
        d = daily(p)
        prem = premiums(p)["total"] * (MAX_DAYS / 30)
        out.append({"standard_pay": p, "daily": d, "total": d * MAX_DAYS,
                    "premiums": int(prem), "net": int(d * MAX_DAYS - prem)})
    return out


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 標準報酬月額べつ 1日あたりの傷病手当金 ===")
    print(f"{'標準報酬月額':>12s} {'1日あたり':>9s} {'30日ぶん':>11s}  {'額面の割合'}")
    for r in daily_grid():
        print(f"{r['standard_pay']:11,d}円 {r['daily']:8,d}円 {r['month']:10,d}円  {r['ratio']:.1%}")

    print("\n=== 休んだ日数べつ 実際に受け取る額（最初の3日は出ない・標準報酬30万円）===")
    print(f"{'休んだ日数':>10s} {'支給される日数':>12s} {'受け取る額':>11s}  {'待期で出ない額'}")
    for r in absence_grid(300_000):
        print(f"{r['absent']:8d}日 {r['paid']:11d}日 {r['amount']:10,d}円  {r['lost']:,}円")

    print("\n=== 3分の2から社会保険料を引くと、手元に残るのは何パーセントか（40歳未満）===")
    print(f"{'標準報酬月額':>12s} {'手当金30日':>11s} {'引かれる保険料':>12s} {'手元に残る':>11s}  "
          f"{'額面比':>7s} {'手元比'}")
    for r in net_grid():
        print(f"{r['standard_pay']:11,d}円 {r['benefit']:10,d}円 {r['premiums']:11,d}円 "
              f"{r['net']:10,d}円  {r['benefit_ratio']:6.1%} {r['net_ratio']:6.1%}")

    print("\n=== 40歳以上で介護保険料も引かれ、住民税が月1万円ある場合 ===")
    print(f"{'標準報酬月額':>12s} {'手当金30日':>11s} {'保険料':>10s} {'住民税':>9s} {'手元に残る':>11s}  {'手元比'}")
    for r in net_grid(care=True, resident_tax=10_000):
        print(f"{r['standard_pay']:11,d}円 {r['benefit']:10,d}円 {r['premiums']:9,d}円 "
              f"{r['resident_tax']:8,d}円 {r['net']:10,d}円  {r['net_ratio']:.1%}")

    print("\n=== 通算1年6か月（546日）を使い切るまでに受け取る合計 ===")
    print(f"{'標準報酬月額':>12s} {'1日あたり':>9s} {'546日の合計':>13s} {'そのあいだの保険料':>15s} {'差引'}")
    for r in limit_grid():
        print(f"{r['standard_pay']:11,d}円 {r['daily']:8,d}円 {r['total']:12,d}円 "
              f"{r['premiums']:14,d}円 {r['net']:,}円")
