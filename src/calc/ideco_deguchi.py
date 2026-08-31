"""iDeCo と新NISA、先に埋めるべきはどちらか。**出口の税を入れると、掛金を増やすほど損になる帯がある。**

一般の解説はここで止まります ——「iDeCo は掛金が全額所得控除。新NISA には所得控除が
無い。だから節税だけ見れば iDeCo が先」。

**それは入口だけの話です。** iDeCo は受け取るときに課税されます（退職所得）。
新NISA は受け取るときに1円もかかりません。だから両者の差は

    1,060,896円 ＝ 2,853,120円 − 1,792,224円
    （iDeCo の得 ＝ 掛けた年に戻った税の合計 − 受け取るときに払う税。
      年収5,000,000円・自営業の上限・20年・利回り3パーセント）

**裸の式を書かないこと** —— 台本がそのまま写すので、投稿前の検査が
「formula に数字がほとんど無い」で落とします（2026-08-23 に2回踏んだ）。
**右の項は掛金と利回りで決まります。** 退職所得控除は勤続20年までが
1年40万円、20年を超えた部分が1年70万円 —— **年数に比例して伸びるだけ**です。
ところが残高は利回りで指数に膨らむので、**追い越した時点から得が減りはじめます。**

この計算は `ideco.saving`（掛けた年の税を2回計算してその差を取る）と
`taishoku.tax`（退職所得控除・2分の1課税・復興特別所得税）を**そのまま繋いだ**ものです。
どちらも既に表として検査を通っているので、ここで新しく置いた仮定は
「その年の年収」「利回り」「受け取りが iDeCo 一本であること」の3つだけです。

この表が出す数字（実行して出たものを、丸めずに写しています）:

- **年数はいくら伸ばしても出口の税を生みません。** 年収5,000,000円・会社員の上限
  （年276,000円）・利回り3パーセントなら、10年でも40年でも出口の税は **0円** です。
  40年で残高 21,435,070円 に対し控除は 22,000,000円 —— **控除のほうが後ろにいます**
- **効きを落とすのは利回りのほうです。** 同じ20年で、利回り5パーセントなら出口の税
  119,480円（戻った税 1,115,600円 の **10.71パーセント**）、
  7パーセントなら **315,363円**（**28.27パーセント**）
- **出口の税が初めて1円以上になる利回りは、会社員の上限・20年で 3.5パーセント**です。
  30年に伸ばしても **3.6パーセント** で、**年数を足しても 0.1ポイントしか動きません**
- **掛金を増やすと、得が減ることがあります。** 自営業の上限（年816,000円）は
  会社員の上限の **2.9565217391304346倍** ですが、20年・利回り3パーセントでの
  iDeCo の得は **1,115,600円 → 1,060,896円** と **54,704円 減ります**。
  戻った税は 1,115,600円 → 2,853,120円 と増えるのに、出口の税が
  0円 → 1,792,224円 になるためです。**自営業の上限では、利回り0パーセントでも
  出口の税がかかります**（残高 16,320,000円 に対し控除 8,000,000円）
- **入口の戻りは年収に対して単調ではありません。** 年収3,000,000円 で 833,800円、
  4,000,000円 で **833,780円** —— **20円 下がります。**
  ただし20円は主張になりません（端数の切り捨てが動いただけ）。表には出します
"""
from __future__ import annotations

from . import _checks
from .ideco import SALARIED_CAP, SELF_CAP, saving
from .taishoku import deduction, tax

ASSUMPTIONS = [
    "給与収入のみの人を想定しています。所得控除は基礎控除だけで、社会保険料は年収の15パーセントとして置いています",
    "掛金は毎年おなじ額を、年のはじめに1回入れたものとして積み上げています",
    "利回りは毎年おなじだけ増えるものとして、0パーセント・3パーセント・5パーセント・7パーセントの複利で計算しています。実際の運用は年ごとに上下します",
    "受け取りは一時金1回で、退職所得控除は掛金を10年・20年・30年・40年 出した場合について計算しています",
    "上の表は iDeCo を一本で受け取る年の話です。会社の退職金と同じ年に受け取る場合は、"
    "控除に使う年数が「重ならない期間を合わせた年数」になります"
    "（会社員の上限・20年・利回り3パーセントなら 20年 が 38年 になり、控除は 8,000,000円 が 20,600,000円）。"
    "そのため退職金が 12,970,000円 までは出口の税が増えず、そこを超えると増えます",
    "同じ年ではなく別の年に受け取る場合の年数の調整（受け取る順番と間隔で控除が削られる決まり）は、"
    "この表に1つも入れていません。ここが言えるのは「同じ年に受け取ったとき」だけです",
    "戻った税は、掛けた各年の年収が変わらないものとして同じ額を年数ぶん足しています",
    "新NISA は掛金の所得控除が無く、受け取るときの税も無いので、この表では所得税・住民税ともに0円として置いています",
    "iDeCo・新NISA とも運用益は非課税なので、同じ利回りなら受け取る前の残高は同じです。差がつくのは入口の控除と出口の税だけです",
]

#: **画面に出す標本。** ここを `__main__` 側で書き直さないこと。
SCAN_INCOMES = (3_000_000, 4_000_000, 5_000_000, 6_000_000,
                8_000_000, 10_000_000)
SCAN_YEARS = (10, 20, 30, 40)
SCAN_RATES = (0.0, 0.03, 0.05, 0.07)


def balance(premium: int, years: int, rate: float) -> int:
    """年のはじめに `premium` を入れて `rate` で回した `years` 年後の残高。"""
    total = 0.0
    for _ in range(years):
        total = (total + premium) * (1 + rate)
    return int(total)


def entry_saving(income: int, premium: int, years: int) -> int:
    """掛けた年に戻った税の、`years` 年ぶんの合計。"""
    return saving(income, premium)["節税額"] * years


def exit_tax(premium: int, years: int, rate: float) -> dict:
    """受け取るときに払う税。**退職所得控除は掛けた年数で決まる。**"""
    bal = balance(premium, years, rate)
    t = tax(bal, years)
    return {"残高": bal, "退職所得控除": deduction(years),
            "課税退職所得": t["taxable"], "出口の税": t["total"]}


def verdict(income: int, premium: int, years: int, rate: float) -> dict:
    """iDeCo が新NISA より得か。**得 ＝ 入口で戻った税 − 出口の税。**"""
    got = entry_saving(income, premium, years)
    out = exit_tax(premium, years, rate)
    net = got - out["出口の税"]
    return {
        "年収": income, "掛金": premium, "年数": years, "利回り": rate,
        "戻った税": got, "残高": out["残高"],
        "退職所得控除": out["退職所得控除"],
        "出口の税": out["出口の税"],
        "iDeCoの得": net,
        "持っていかれる割合": out["出口の税"] / got if got else 0.0,
        "先に埋めるべき": "iDeCo" if net > 0 else "新NISA",
    }


def years_table(income: int = 5_000_000, premium: int = SALARIED_CAP,
                rate: float = 0.03) -> list[dict]:
    """年数べつ。**控除は年数で伸び、残高は年数で膨らむ。どちらが速いか。**"""
    return [verdict(income, premium, y, rate) for y in SCAN_YEARS]


def rate_table(income: int = 5_000_000, premium: int = SALARIED_CAP,
               years: int = 20) -> list[dict]:
    """利回りべつ。**利回りは入口を1円も増やさず、出口だけを増やす。**"""
    return [verdict(income, premium, years, r) for r in SCAN_RATES]


def income_table(premium: int = SALARIED_CAP, years: int = 20,
                 rate: float = 0.03) -> list[dict]:
    """年収べつ。**入口だけが年収で動く。出口は年収と無関係。**"""
    return [verdict(i, premium, years, rate) for i in SCAN_INCOMES]


def cap_table(income: int = 5_000_000, years: int = 20,
              rate: float = 0.03) -> list[dict]:
    """掛金の上限べつ（会社員と自営業）。**入口が3倍なら出口は3倍では済まない。**"""
    return [verdict(income, p, years, rate)
            for p in (SALARIED_CAP, SELF_CAP)]


def crossover_rate(premium: int = SALARIED_CAP,
                   years: int = 20) -> float | None:
    """**出口の税が初めて1円以上になる利回り**（0.1パーセントきざみ）。

    ここを超えると、利回りを上げるほど iDeCo の取り分が減ります。
    見つからなければ None。

    **年収を引数に取りません。** 出口の税は退職所得だけで決まり、
    その年の年収は1円も効かないからです（`income_table` の「出口の税」列が
    どの年収でも同じなのが、その裏です）。
    """
    for step in range(0, 301):
        r = step / 1000
        if exit_tax(premium, years, r)["出口の税"] > 0:
            return r
    return None


#: 会社の退職手当の標本。**0円は入れません**（払われないなら「同じ年に2つ」が起きない）。
SCAN_SEVERANCE = (1_000_000, 5_000_000, 10_000_000, 13_000_000,
                  15_000_000, 20_000_000, 30_000_000)


def union_years(service_years: int, years: int,
                overlap_years: int | None = None) -> int:
    """**同じ年に2つ受け取るときの、控除を出すための年数。**

    重なっている期間は**二度かぞえません**（所得税法施行令69条）。
    掛金を出していたあいだ会社にも居たのが普通なので、
    既定の重なりは短いほう（`min`）です。
    """
    if overlap_years is None:
        overlap_years = min(service_years, years)
    return service_years + years - overlap_years


def same_year_exit(severance: int, premium: int, years: int, rate: float,
                   service_years: int = 38,
                   overlap_years: int | None = None) -> dict:
    """**会社の退職金と iDeCo の一時金を、同じ年に受け取ったときの出口。**

    `ASSUMPTIONS` は長らく「重なると控除を分け合うので出口の税はここより増えます」と
    書いていて、**いくつ増えるかを1度も計算していませんでした。** ここがその数です。

    `iDeCoに乗った税` は、**退職金だけを受け取ったときの税との差**です
    （その年に iDeCo を足したことで、いくら増えたか）。
    `単独なら` は、いま表が出している `exit_tax` の数（iDeCo 一本で受け取る場合）。
    """
    bal = balance(premium, years, rate)
    u = union_years(service_years, years, overlap_years)
    alone_only = tax(severance, service_years)          # 退職金だけの年
    together = tax(severance + bal, u)                  # 同じ年に2つ
    ideco_alone = tax(bal, years)                       # iDeCo だけの年
    added = together["total"] - alone_only["total"]
    return {
        "会社の退職金": severance,
        "会社の勤続年数": service_years,
        "iDeCoの年数": years,
        "控除に使う年数": u,
        "iDeCoの残高": bal,
        "2つ合わせた控除": together["deduction"],
        "別々にとった場合の控除の和": alone_only["deduction"] + ideco_alone["deduction"],
        "同じ年の税の合計": together["total"],
        "退職金だけの税": alone_only["total"],
        "iDeCoに乗った税": added,
        "単独なら": ideco_alone["total"],
        "重なりで増えた税": added - ideco_alone["total"],
    }


def same_year_table(premium: int = SALARIED_CAP, years: int = 20,
                    rate: float = 0.03, service_years: int = 38,
                    severances: tuple[int, ...] = SCAN_SEVERANCE) -> list[dict]:
    """会社の退職金の額を刻んで、**重なりで増える税がどこから立つか**を出す。"""
    return [same_year_exit(s, premium, years, rate, service_years)
            for s in severances]


def same_year_break(premium: int = SALARIED_CAP, years: int = 20,
                    rate: float = 0.03, service_years: int = 38,
                    step: int = 500_000, top: int = 60_000_000) -> int | None:
    """**重なりで増える税が、初めて1円以上になる会社の退職金**。無ければ None。

    ここより下では、控除を分け合っても**まだ控除のほうが後ろにいる**ので、
    同じ年に受け取っても1円も増えません。
    """
    for s in range(0, top + 1, step):
        if same_year_exit(s, premium, years, rate, service_years)["重なりで増えた税"] > 0:
            return s
    return None


def check_tables() -> None:
    """繋ぎ方と、表の向きを確かめる。"""

    # 1. 借りている値が、借りた先のままであること。
    _checks.statutory(SALARIED_CAP, 276_000, "会社員（企業年金なし）の年間上限",
                      source="確定拠出年金法・同施行令")
    _checks.statutory(SELF_CAP, 816_000, "自営業の年間上限",
                      source="確定拠出年金法・同施行令")
    _checks.statutory(deduction(20), 8_000_000, "勤続20年の退職所得控除",
                      source="所得税法30条")
    _checks.statutory(deduction(30), 15_000_000, "勤続30年の退職所得控除",
                      source="所得税法30条")

    # 2. 積み上げの向き。**利回り0なら、残高は掛金×年数そのもの。**
    _checks.rounding(balance(SALARIED_CAP, 20, 0.0), SALARIED_CAP * 20,
                     "利回り0の20年後の残高")
    _checks.increases_with(lambda r: balance(SALARIED_CAP, 20, r),
                           [0.0, 0.03, 0.05, 0.07],
                           "利回りが上がったのに残高が増えていない")
    _checks.increases_with(lambda y: balance(SALARIED_CAP, y, 0.03),
                           [10, 20, 30, 40],
                           "年数が伸びたのに残高が増えていない")

    # 3. **主題その1**: 入口は年収で動くが、出口は年収で動かない。
    outs = {r["出口の税"] for r in income_table()}
    _checks.rounding(len(outs), 1, "年収を変えたのに出口の税の種類が1つでない")
    # **単調ではありません。** 年収3,000,000円 → 4,000,000円 で戻った税は
    # 833,800円 → 833,780円 と **20円 下がります**（掛金で削った後の課税所得が
    # どの区分に落ちるかで、住民税と所得税の端数の切り捨てが動くため）。
    # **20円は主張になりません** —— 表に出しはしますが、ここで確かめるのは
    # 「年収の端から端では増えている」ことだけです。
    _checks.greater(entry_saving(SCAN_INCOMES[-1], SALARIED_CAP, 20),
                    entry_saving(SCAN_INCOMES[0], SALARIED_CAP, 20),
                    "年収の端から端で戻った税が増えていない")

    # 4. **主題その2**: 利回りは入口を1円も動かさず、出口だけを押し上げる。
    ins = {r["戻った税"] for r in rate_table()}
    _checks.rounding(len(ins), 1, "利回りを変えたのに戻った税が動いている")
    _checks.never_decreases(lambda r: exit_tax(SALARIED_CAP, 20, r)["出口の税"],
                            [0.0, 0.03, 0.05, 0.07],
                            "利回りが上がったのに出口の税が減っている")
    _checks.decreases_with(lambda r: verdict(5_000_000, SALARIED_CAP, 20, r)["iDeCoの得"],
                           [0.03, 0.05, 0.07],
                           "利回りが上がったのに iDeCo の得が減っていない")

    # 5. **主題その3**: 掛金が3倍でも、出口の税は3倍では済まない。
    caps = cap_table()
    _checks.greater(caps[1]["出口の税"] / max(caps[0]["出口の税"], 1),
                    caps[1]["掛金"] / caps[0]["掛金"],
                    "出口の税の倍率が掛金の倍率を超えていない（控除が固定なのに効いていない）")

    # 6. 控除は年数で伸びること。**伸びなければ主題そのものが消えます。**
    _checks.increases_with(deduction, [10, 20, 30, 40],
                           "年数が伸びたのに退職所得控除が増えていない")

    # 7. **主題その4**: 同じ年に受け取ると、控除に使う年数が「union」になる。
    #    重なりを二度かぞえないこと（38年 と 20年 が重なっていれば 38年 のまま）
    if union_years(38, 20) != 38:
        raise _checks.TableError("重なっている20年を、38年に足してしまっている")
    if union_years(38, 20, overlap_years=0) != 58:
        raise _checks.TableError("重なりが0年のとき、年数が足し合わされていない")
    if union_years(10, 20) != 20:
        raise _checks.TableError("短いほうの勤続で union が決まってしまっている")
    #    **控除は「分け合う」より広くなることがある** ——
    #    iDeCo 単独（20年 = 8,000,000円）より、同じ年（38年 = 20,600,000円）のほうが大きい
    wide = same_year_exit(1_000_000, SALARIED_CAP, 20, 0.03)
    _checks.greater(wide["2つ合わせた控除"], deduction(20),
                    "同じ年に受け取ったときの控除が、iDeCo 単独の控除")
    if wide["2つ合わせた控除"] >= wide["別々にとった場合の控除の和"]:
        raise _checks.TableError("重なりを二度かぞえていない側のほうが小さくなっている")
    #    退職金を増やすほど「重なりで増えた税」は増える（減ってはいけない）
    _checks.never_decreases(
        lambda s: same_year_exit(s, SALARIED_CAP, 20, 0.03)["重なりで増えた税"],
        list(SCAN_SEVERANCE),
        "会社の退職金が増えたのに、重なりで増えた税が減っている")
    #    分かれ目は刻みを細かくしても、より手前へ寄るだけ（後ろへ動いたら壊れている）
    coarse = same_year_break(step=1_000_000)
    fine = same_year_break(step=10_000)
    if coarse is None or fine is None:
        raise _checks.TableError("重なりで税が増え始める退職金が見つからない")
    if fine > coarse:
        raise _checks.TableError(
            f"刻みを細かくしたら分かれ目が後ろへ動いた（{coarse:,} → {fine:,}）")
    #    分かれ目より下では1円も増えない
    if same_year_exit(fine - 10_000, SALARIED_CAP, 20, 0.03)["重なりで増えた税"] > 0:
        raise _checks.TableError("分かれ目の1つ手前で、もう税が増えている")

    _checks.unique_by(years_table(), lambda r: r["年数"], "年数")
    _checks.unique_by(rate_table(), lambda r: r["利回り"], "利回り")
    _checks.unique_by(income_table(), lambda r: r["年収"], "年収")
    _checks.assumption_values(ASSUMPTIONS, name="ideco_deguchi")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 年数を伸ばすと、退職所得控除と残高のどちらが速く伸びるか ===")
    for row in years_table():
        print(f"  {row['年数']:>2}年  戻った税 {row['戻った税']:>10,.0f}円"
              f"  残高 {row['残高']:>12,.0f}円"
              f"  控除 {row['退職所得控除']:>11,.0f}円"
              f"  出口の税 {row['出口の税']:>10,.0f}円"
              f"  → iDeCoの得 {row['iDeCoの得']:>10,.0f}円")

    print("\n=== 利回りは入口を1円も増やさず、出口だけを増やす ===")
    for row in rate_table():
        print(f"  利回り {row['利回り']:>5.1%}"
              f"  戻った税 {row['戻った税']:>10,.0f}円"
              f"  残高 {row['残高']:>12,.0f}円"
              f"  出口の税 {row['出口の税']:>10,.0f}円"
              f"（戻った税の {row['持っていかれる割合']:>6.2%}）"
              f"  → iDeCoの得 {row['iDeCoの得']:>10,.0f}円")

    print("\n=== 年収べつ。入口だけが動き、出口は1円も動かない ===")
    for row in income_table():
        print(f"  年収 {row['年収']:>10,.0f}円"
              f"  戻った税 {row['戻った税']:>10,.0f}円"
              f"  出口の税 {row['出口の税']:>10,.0f}円"
              f"  → iDeCoの得 {row['iDeCoの得']:>10,.0f}円"
              f"  先に埋めるべき {row['先に埋めるべき']}")

    print("\n=== 掛金の上限べつ。入口が3倍でも、出口は3倍では済まない ===")
    for row in cap_table():
        print(f"  掛金 {row['掛金']:>9,.0f}円/年"
              f"  戻った税 {row['戻った税']:>10,.0f}円"
              f"  残高 {row['残高']:>12,.0f}円"
              f"  控除 {row['退職所得控除']:>11,.0f}円"
              f"  出口の税 {row['出口の税']:>10,.0f}円"
              f"  → iDeCoの得 {row['iDeCoの得']:>10,.0f}円")

    caps = cap_table()
    print(f"\n  掛金を {caps[1]['掛金'] / caps[0]['掛金']}倍 にすると、"
          f"iDeCo の得は {caps[0]['iDeCoの得']:,.0f}円 → {caps[1]['iDeCoの得']:,.0f}円 と"
          f" **{caps[0]['iDeCoの得'] - caps[1]['iDeCoの得']:,.0f}円 減る**")

    print("\n=== 出口の税が初めて1円以上になる利回り（0.1パーセントきざみで探す）===")
    for label, prem, yrs in (("会社員の上限・20年", SALARIED_CAP, 20),
                             ("会社員の上限・30年", SALARIED_CAP, 30),
                             ("自営業の上限・20年", SELF_CAP, 20),
                             ("自営業の上限・30年", SELF_CAP, 30)):
        r = crossover_rate(prem, yrs)
        print(f"  {label:<16} → " + ("見つからない" if r is None else f"利回り {r:.1%}"))

    print("\n=== 会社の退職金と同じ年に受け取ると、控除に使う年数は「重ならない期間を合わせた年数」になる"
          f"（会社員の上限・20年・利回り3パーセント・勤続38年。分かれ目は10,000円きざみで探す）===")
    fine = same_year_break(step=10_000)
    self_fine = same_year_break(premium=SELF_CAP, step=10_000)
    print(f"  iDeCo を一本で受け取る年なら、控除は加入20年ぶんの {deduction(20):,}円。")
    print(f"  同じ年に会社の退職金も受け取ると、控除は"
          f" **{union_years(38, 20)}年ぶんの {deduction(union_years(38, 20)):,}円**"
          f"（重なっている20年は二度かぞえません）。")
    print(f"  **足し算ではありません** —— 別々にとった場合の控除の和は"
          f" {deduction(38) + deduction(20):,}円 で、こちらのほうが"
          f" {deduction(38) + deduction(20) - deduction(union_years(38, 20)):,}円 大きい。")
    print("    会社の退職金   控除に使う年数     2つ合わせた控除    iDeCoに乗った税   単独なら    差")
    for row in same_year_table():
        print(f"    {row['会社の退職金']:>11,}円"
              f"      {row['控除に使う年数']:>2}年"
              f"      {row['2つ合わせた控除']:>11,}円"
              f"  {row['iDeCoに乗った税']:>10,}円"
              f"  {row['単独なら']:>8,}円"
              f"  {row['重なりで増えた税']:>+10,}円")
    print(f"  **1万円きざみで探すと、増え始めるのは会社の退職金 {fine:,}円 から**です"
          f"（自営業の上限なら {self_fine:,}円）。それより下では1円も増えません。")
    print("  **自営業の上限では、同じ年のほうが安くなります** ——"
          f" iDeCo 単独なら {exit_tax(SELF_CAP, 20, 0.03)['出口の税']:,}円 かかるところ、"
          f" 退職金 {SCAN_SEVERANCE[0]:,}円 と同じ年なら"
          f" {same_year_exit(SCAN_SEVERANCE[0], SELF_CAP, 20, 0.03)['iDeCoに乗った税']:,}円。"
          f" **{-same_year_exit(SCAN_SEVERANCE[0], SELF_CAP, 20, 0.03)['重なりで増えた税']:,}円 安い。**")
    print("  控除に使う年数が、iDeCo の加入年数ではなく**会社の勤続年数のほうに引っぱられる**からです。")
    print("  **同じ年にまとめると損、はいつも本当ではありません。**"
          f" 分かれ目は退職金の額で、この前提では {fine:,}円 です。")
    print("  ※ 別の年に受け取る場合の年数の調整は、この表に1つも入れていません（`ASSUMPTIONS`）。")
