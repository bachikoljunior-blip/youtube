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

from fractions import Fraction

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
    "標準報酬月額は1,000円きざみの値だけを入れています（実際の等級もそうなっています）",
    "健康保険料率は都道府県ごとに違うため、率そのものを入力として動かせるようにしています",
    "余りの表に出てくる月額は、その余りになる1,000円きざみの値の例であって、実在する等級とは限りません",
]

# 制度の値。**長く動いていないもの**だけをここに置く。
WAITING_DAYS = 3          # 待期（連続した3日間）
BENEFIT_RATIO = 2 / 3     # 支給割合
MAX_DAYS = 546            # 通算1年6か月

# 保険料率の本人負担（**改正が続くので既定値。呼ぶ側で差し替えられる**）
HEALTH_RATE = 0.05        # 健康保険（協会けんぽ 約10% の半分。都道府県で違う）
PENSION_RATE = 0.0915     # 厚生年金（18.3% の半分。固定）
CARE_RATE = 0.008         # 介護保険（40歳以上。約1.6% の半分）
RATE_DIGITS = 6           # 率をここまで丸めてから分数にする（`premiums`）


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
    """休んでいるあいだも引かれる、社会保険料の本人負担（1か月ぶん）。

    **率は「小数第6位まで」に丸めてから分数に直して掛ける**（2026-08-18 に直した）。
    `int(標準報酬 × 率)` は float の掛け算を切り捨てるので、
    **率を足して渡した瞬間に1円ずれる** —— `0.0915 + 0.01` は float では
    0.10149999999999999 になり、30万円に掛けると 30,449.999… で、
    切り捨てると **30,450 が 30,449** になる。
    `str()` で分数に直すだけでは足りない（**壊れた率をそのまま写すため**）。
    保険料率は百分率で小数第2位までしか動かないので、
    **10のマイナス6乗まで丸めれば、実在する率は1つも変わらない。**
    既定の3つの率では1件も変わらない（58,000〜1,400,000円の1,000円きざみ全部で確認）。
    **変わるのは、呼ぶ側が率を動かしたときだけ**で、動かせるようにしたのが上の
    `net_month` の直し。片方だけ直すと、そこで1円が消える。
    """
    def cut(rate: float) -> int:
        return int(Fraction(standard_pay) * Fraction(str(round(rate, RATE_DIGITS))))

    health = cut(health_rate)
    pension = cut(pension_rate)
    nursing = cut(CARE_RATE) if care else 0
    return {"health": health, "pension": pension, "care": nursing,
            "total": health + pension + nursing}


def net_month(standard_pay: int, care: bool = False, resident_tax: int = 0,
              days: int = 30, health_rate: float = HEALTH_RATE,
              pension_rate: float = PENSION_RATE) -> dict:
    """1か月まるごと休んだときに、**手元に残る額**。

    傷病手当金は非課税だが、社会保険料と住民税は休んでも減らない。

    **率はここまで通す。** `premiums()` は `health_rate` と `pension_rate` を
    受け取れるのに、ここが渡していなかったので、**呼ぶ側から率を動かす道が
    塞がっていた**（2026-08-18 に直した）。健康保険料率は都道府県ごとに違い、
    モジュールの docstring も「率は入力に逃がしている」と書いている。
    """
    benefit = daily(standard_pay) * days
    prem = premiums(standard_pay, care, health_rate, pension_rate)
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


# **日額の丸めの周期。** `daily()` は 標準報酬月額 ÷ 30 を10円未満四捨五入し、
# そのあと 2/3 をかけて1円未満四捨五入する。前の段は 900 で、後ろの段は 3 で
# 効くので、**得か損かは標準報酬月額を 900 で割った余りだけで決まる**（9通り）。
ROUND_MOD = 900
PAY_STEP = 1_000          # 標準報酬月額のきざみ（`ASSUMPTIONS`）


def daily_exact(standard_pay: int) -> Fraction:
    """**丸めを1つも入れない**1日あたり。分数のまま返す（float にしない）。"""
    return Fraction(standard_pay, 30) * Fraction(2, 3)


def rounding_gain(standard_pay: int) -> Fraction:
    """丸めで**増えた（減った）**1日あたりの額。プラスなら得、マイナスなら損。"""
    return Fraction(daily(standard_pay)) - daily_exact(standard_pay)


def example_pay(remainder: int, floor: int = 200_000) -> int:
    """その余りを持つ、`floor` 以上でいちばん小さい標準報酬月額（1,000円きざみ）。"""
    pay = floor - floor % PAY_STEP
    while pay % ROUND_MOD != remainder % ROUND_MOD:
        pay += PAY_STEP
    return pay


def rounding_grid() -> list[dict]:
    """**丸めの得損は9通りしかない。** 標準報酬月額を900で割った余りで決まる。

    1,000円きざみの標準報酬月額は、900で割った余りが
    0・100・200 …… 800 の**9つのどれか**にしかならない。
    """
    check_tables()
    out = []
    for r in range(0, ROUND_MOD, PAY_STEP % ROUND_MOD):
        pay = example_pay(r)
        g = rounding_gain(pay)
        out.append({"remainder": r, "example_pay": pay, "daily": daily(pay),
                    "per_day": g, "per_month": g * 30, "per_limit": g * MAX_DAYS})
    return out


def rounding_spread() -> dict:
    """**上と下の差**。546日ぶんで何円ひらくか。"""
    rows = rounding_grid()
    hi = max(rows, key=lambda r: r["per_day"])
    lo = min(rows, key=lambda r: r["per_day"])
    return {"best": hi, "worst": lo,
            "spread_day": hi["per_day"] - lo["per_day"],
            "spread_limit": hi["per_limit"] - lo["per_limit"]}


def premium_ratio(care: bool = False, health_rate: float = HEALTH_RATE,
                  pension_rate: float = PENSION_RATE) -> float:
    """**標準報酬月額に対する保険料の割合。** 額ではなく率なので、金額によらない。"""
    return health_rate + pension_rate + (CARE_RATE if care else 0.0)


def drop_grid(care: bool = False) -> list[dict]:
    """**「3分の2」から手元までの落ち幅**を、標準報酬月額べつに並べる。

    落ち幅（額面比 − 手元比）は**保険料の割合そのもの**なので、
    標準報酬月額がいくらでも同じになる。手元比が行ごとに動いて見えるのは、
    **日額の丸めだけ**が理由。
    """
    check_tables()
    out = []
    for p in (200_000, 260_000, 300_000, 380_000, 440_000, 500_000, 650_000):
        r = net_month(p, care=care)
        pr = premiums(p, care)["total"] / p
        out.append({"standard_pay": p, "benefit_ratio": r["benefit_ratio"],
                    "premium_ratio": pr, "net_ratio": r["net_ratio"],
                    "drop": r["benefit_ratio"] - r["net_ratio"]})
    return out


def net_ratio_spread(care: bool = False) -> dict:
    """手元比が、上の行と下の行でどれだけしかひらかないか（＝丸めのぶんだけ）。"""
    rows = drop_grid(care=care)
    hi = max(rows, key=lambda r: r["net_ratio"])
    lo = min(rows, key=lambda r: r["net_ratio"])
    return {"high": hi, "low": lo, "spread": hi["net_ratio"] - lo["net_ratio"],
            "drop": rows[0]["drop"]}


def resident_tax_edges(care: bool = False) -> list[dict]:
    """**住民税がいくらを超えると、手元が額面の半分を割るか。**

    傷病手当金そのものは非課税でも、住民税は前年の所得で決まるので休んでも減らない。
    「半分を割る住民税」＝ 手元（住民税ゼロ） − 標準報酬月額の半分。
    """
    check_tables()
    out = []
    for p in (200_000, 260_000, 300_000, 380_000, 440_000, 500_000):
        r = net_month(p, care=care)
        half = r["net"] - p // 2
        out.append({"standard_pay": p, "net": r["net"], "half_edge": half,
                    "zero_edge": r["net"], "half_edge_ratio": half / p})
    return out


def rate_step(point: float = 0.01, care: bool = False) -> list[dict]:
    """**健康保険料率が1ポイント違うと、546日ぶんでいくら変わるか。**

    率は都道府県ごとに違うので、この計算では入力にしている（モジュールの docstring）。
    **額は標準報酬月額に比例して開くが、比で見ればどこでも同じ1ポイント。**
    """
    check_tables()
    out = []
    for p in (200_000, 300_000, 440_000, 650_000):
        base = net_month(p, care=care)
        up = net_month(p, care=care, health_rate=HEALTH_RATE + point)
        out.append({"standard_pay": p, "net": base["net"], "net_up": up["net"],
                    "diff_month": base["net"] - up["net"],
                    "diff_limit": (base["net"] - up["net"]) * MAX_DAYS / 30,
                    "diff_ratio": base["net_ratio"] - up["net_ratio"]})
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

    print("\n=== 日額の10円未満四捨五入で得か損かは、標準報酬月額を900で割った余りだけで決まる ===")
    print(f"{'900で割った余り':>14s} {'余りがこうなる月額の例':>22s} {'1日あたり':>9s} "
          f"{'丸めの差／日':>12s} {'30日ぶん':>10s}  {'546日ぶん'}")
    for r in rounding_grid():
        print(f"{r['remainder']:13d} {r['example_pay']:20,d}円 {r['daily']:8,d}円 "
              f"{float(r['per_day']):+11.3f}円 {float(r['per_month']):+9.1f}円  "
              f"{float(r['per_limit']):+,.1f}円")
    sp = rounding_spread()
    print(f"  上と下の差: 1日 {float(sp['spread_day']):.3f}円 / "
          f"546日 {float(sp['spread_limit']):,.1f}円"
          f"（得の最大は余り{sp['best']['remainder']}、損の最大は余り{sp['worst']['remainder']}）")

    print("\n=== 「3分の2」から手元までの落ち幅は、標準報酬月額がいくらでも変わらない（40歳未満）===")
    print(f"{'標準報酬月額':>12s} {'額面比':>8s} {'保険料の比':>10s} {'手元比':>8s}  {'落ち幅'}")
    for r in drop_grid():
        print(f"{r['standard_pay']:11,d}円 {r['benefit_ratio']:7.4%} {r['premium_ratio']:9.4%} "
              f"{r['net_ratio']:7.4%}  {r['drop'] * 100:.4f}ポイント")
    ns = net_ratio_spread()
    print(f"  手元比の幅は {ns['spread'] * 100:.4f}ポイントしかない"
          f"（{ns['high']['standard_pay']:,}円 と {ns['low']['standard_pay']:,}円）。"
          f"**動かしているのは保険料ではなく日額の丸めだけ。**")

    print("\n=== 住民税が月いくらを超えると、手元は標準報酬月額の半分を割るか（40歳未満）===")
    print(f"{'標準報酬月額':>12s} {'住民税0の手元':>13s} {'半分を割る住民税':>16s} "
          f"{'手元が0になる住民税':>18s}  {'標準報酬に対する割合'}")
    for r in resident_tax_edges():
        print(f"{r['standard_pay']:11,d}円 {r['net']:12,d}円 {r['half_edge']:15,d}円 "
              f"{r['zero_edge']:17,d}円  {r['half_edge_ratio']:.4%}")

    print("\n=== 健康保険料率が1ポイント違うと、546日ぶんでいくら変わるか（40歳未満）===")
    print(f"{'標準報酬月額':>12s} {f'率{HEALTH_RATE:.0%}の手元':>11s} "
          f"{f'率{HEALTH_RATE + 0.01:.0%}の手元':>11s} {'差／月':>9s} "
          f"{'546日ぶんの差':>13s}  {'比の差'}")
    for r in rate_step():
        print(f"{r['standard_pay']:11,d}円 {r['net']:10,d}円 {r['net_up']:10,d}円 "
              f"{r['diff_month']:8,d}円 {r['diff_limit']:12,.0f}円  {r['diff_ratio'] * 100:.4f}ポイント")
