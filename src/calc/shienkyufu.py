"""年金生活者支援給付金 —— **崖を消すために作った帯が、別の崖を作っている。**

老齢年金生活者支援給付金には「補足的老齢年金生活者支援給付金」という仕組みが
付いています。基準額を1円こえた瞬間に給付金が丸ごと消えるのを避けるため、
基準額の上に**10万円の帯**を置いて、そこを滑らかに落とす、という設計です。

ところが調整支給率が掛かるのは、**保険料納付済期間に基づく額**だけです。
**保険料免除期間に基づく額には掛かりません。** 帯に入った瞬間、免除分は
調整も按分もされずに0円になります。

    納付済480月・免除0月     809,000円 → 809,001円 で **月 0.06円** しか動かない（設計どおり）
    納付済240月・免除240月   809,000円 → 809,001円 で **月 5,884円 減る**（年 70,608円）

**崖は、基準額の 909,000円ではなく、帯の入口の 809,000円にあります。**
そして落ちる額は、免除期間が長いほど大きい —— つまり
**保険料を払えなかった人ほど、深い崖を踏みます。**

もう1つ。給付金の単価は、**免除期間のほうが納付済期間より高い**です。

    保険料納付済期間  月 5,620円 ÷ 480月
    保険料免除期間    月 11,768円 ÷ 480月   ← **2.094倍**

老齢基礎年金の本体は、全額免除の月が納付済の月の**半分**にしかなりません。
給付金はその穴を埋めるためのものなので、単価が高いこと自体は設計どおりです。
**ですが給付金だけを取り出すと、納付と免除の大小がひっくり返っています。**
本体と給付金を足してどうなるかまで、この表で出します。

障害・遺族のほうには、この帯がそもそもありません。所得基準 4,794,000円 を
1円こえたら、**1級は年 84,300円 が調整なしで消えます。**
同じ制度の中に「10万円かけて滑らかに落とす崖」と「1円で落ちる崖」が同居しています。
"""
from __future__ import annotations

from . import _checks

ASSUMPTIONS = [
    "令和8年度（2026年4月分から）の額です。制度は毎年度改定されます",
    "昭和31年4月2日以後に生まれた方の額で計算しています。"
    "昭和31年4月1日以前生まれの方は基準額が906,700円、免除期間の単価が11,734円で、"
    "この表とは別の数字になります",
    "老齢の給付金は、65歳以上の老齢基礎年金の受給者で、"
    "同一世帯の全員が市町村民税非課税であることが前提です。"
    "この2つを満たさない場合は、収入がいくらでも支給されません",
    "「収入」は、前年の公的年金等の収入金額と、その他の所得の合計額を指します。"
    "公的年金等控除を引く前の年金の額に、給与所得などの所得を足したものです",
    "老齢基礎年金の本体は、令和8年度の満額を831,700円として置いています。"
    "全額免除の期間は本体では2分の1で数えます",
    "月額は1円未満を四捨五入しています。実際の支給は2か月分ずつです",
    "所得や世帯の状況によっては、ここに入れていない他の判定が入ります。"
    "この表は制度の形を見るためのもので、個別の支給額の証明ではありません",
]

# ---- 制度の値（令和8年度。日本年金機構・厚生労働省の公表資料） -------------
NOFU_UNIT = 5_620          # 保険料納付済期間に基づく額の月額単価（÷480月）
MENJO_UNIT = 11_768        # 全額免除・4分の3免除・半額免除の月額単価（÷480月）
MENJO_UNIT_QUARTER = 5_884  # 4分の1免除の月額単価（÷480月）
FULL_MONTHS = 480          # 分母

BAND_LOW = 809_000         # ここまでは老齢年金生活者支援給付金（免除分も出る）
BAND_HIGH = 909_000        # ここをこえると1円も出ない
BAND_WIDTH = 100_000       # 調整支給率の分母

SHOGAI_1 = 7_025           # 障害年金生活者支援給付金 1級 月額
SHOGAI_2 = 5_620           # 同 2級 月額 ＝ 遺族の月額
IZOKU = 5_620              # 遺族年金生活者支援給付金 月額（子が複数なら人数で按分）
SHOTOKU_LIMIT = 4_794_000  # 障害・遺族の所得基準額

KISO_FULL = 831_700        # 老齢基礎年金の満額（年額・令和8年度）

MENJO_KINDS = {
    "全額免除": MENJO_UNIT,
    "4分の3免除": MENJO_UNIT,
    "半額免除": MENJO_UNIT,
    "4分の1免除": MENJO_UNIT_QUARTER,
}


def nofu_part(nofu_months: int) -> float:
    """保険料納付済期間に基づく額（月額・丸める前）。"""
    return NOFU_UNIT * nofu_months / FULL_MONTHS


def menjo_part(menjo_months: int, kind: str = "全額免除") -> float:
    """保険料免除期間に基づく額（月額・丸める前）。"""
    return MENJO_KINDS[kind] * menjo_months / FULL_MONTHS


def adjust_rate(income: int) -> float:
    """補足的給付金の調整支給率。帯の外では意味を持たない。"""
    return (BAND_HIGH - income) / BAND_WIDTH


def monthly(income: int, nofu_months: int, menjo_months: int = 0,
            kind: str = "全額免除") -> int:
    """収入と加入月数から、この月にもらえる給付金の月額（円）。

    **帯の中では免除分が消えます。** そこがこの表の主題です。
    """
    if income <= BAND_LOW:
        return round(nofu_part(nofu_months) + menjo_part(menjo_months, kind))
    if income <= BAND_HIGH:
        return round(nofu_part(nofu_months) * adjust_rate(income))
    return 0


def cliff_at_band_entry(nofu_months: int, menjo_months: int,
                        kind: str = "全額免除") -> int:
    """帯の入口（809,000円 → 809,001円）で、月額がいくら落ちるか。"""
    return monthly(BAND_LOW, nofu_months, menjo_months, kind) - \
        monthly(BAND_LOW + 1, nofu_months, menjo_months, kind)


def kiso_nenkin(nofu_months: int, menjo_months: int) -> int:
    """老齢基礎年金の本体（年額）。全額免除の期間は2分の1で数える。"""
    return round(KISO_FULL * (nofu_months + menjo_months / 2) / FULL_MONTHS)


def splits(total_months: int = FULL_MONTHS) -> list[dict]:
    """納付済と全額免除の分け方を変えて、本体と給付金と合計を並べる。"""
    rows = []
    for menjo in range(0, total_months + 1, 48):
        nofu = total_months - menjo
        kyufu_year = monthly(BAND_LOW, nofu, menjo) * 12
        honntai = kiso_nenkin(nofu, menjo)
        rows.append({
            "免除月数": menjo,
            "納付済月数": nofu,
            "本体": honntai,
            "給付金": kyufu_year,
            "合計": honntai + kyufu_year,
            "入口の崖": cliff_at_band_entry(nofu, menjo) * 12,
        })
    return rows


def band_walk(nofu_months: int, menjo_months: int,
              step: int = 20_000) -> list[dict]:
    """帯を刻んで歩く。免除のある人は入口で落ちる。"""
    rows = []
    # **帯は BAND_LOW の「超」から始まります。**BAND_LOW ちょうどは帯の外なので、
    # ここに混ぜると「調整支給率 1.00000 なのに免除分が出ている行」ができ、
    # 帯の中の話と帯の手前の話が1つの表に同居します（読み違えの元）。
    for income in range(BAND_LOW + 1, BAND_HIGH + 1, step):
        rows.append({
            "収入": income,
            "月額": monthly(income, nofu_months, menjo_months),
            "調整支給率": round(adjust_rate(income), 5),
        })
    return rows


def recover_income(nofu_months: int, menjo_months: int) -> int | None:
    """帯に入って落ちたぶんを、年収の増加だけで取り返せる点。

    帯の中では給付金は減る一方なので、**取り返せる点は帯の中には存在しません。**
    帯を出て給付金が0になったあとで、初めて収入の増加が手取りに素直に効きます。
    ここでは「基準額のときの合計（収入＋給付金）に戻る収入」を返します。
    """
    base = BAND_LOW + monthly(BAND_LOW, nofu_months, menjo_months) * 12
    for income in range(BAND_LOW, BAND_HIGH + 200_000):
        if income + monthly(income, nofu_months, menjo_months) * 12 >= base:
            if income > BAND_LOW:
                return income
    return None


def check_tables() -> None:
    """制度の値と計算の向きを確かめる。"""
    _checks.statutory(NOFU_UNIT, 5_620, "納付済期間の月額単価",
                      source="令和8年度 年金生活者支援給付金（日本年金機構）")
    _checks.statutory(MENJO_UNIT, 11_768, "免除期間の月額単価",
                      source="同上（昭和31年4月2日以後生まれ）")
    _checks.statutory(BAND_LOW, 809_000, "補足的給付金の下端",
                      source="同上")
    _checks.statutory(BAND_HIGH, 909_000, "補足的給付金の上端＝支給の基準額",
                      source="同上")
    _checks.statutory(SHOTOKU_LIMIT, 4_794_000, "障害・遺族の所得基準額",
                      source="同上")

    # 1. 帯の幅は、上端と下端の差そのもの（分母と一致していること）
    _checks.rounding(BAND_HIGH - BAND_LOW, BAND_WIDTH, "調整支給率の分母と帯の幅")

    # 2. 4分の1免除は、他の免除のちょうど半分
    _checks.rounding(MENJO_UNIT_QUARTER * 2, MENJO_UNIT,
                     "4分の1免除の単価の2倍")

    # 3. **この表の主題**: 免除の単価は納付済の単価より高い
    _checks.greater(MENJO_UNIT, NOFU_UNIT, "免除期間の単価が納付済期間の単価以下")
    _checks.close(MENJO_UNIT / NOFU_UNIT, 2.0939501779359432, "免除と納付済の単価比")

    # 4. **主題の裏側**: 老齢基礎年金の本体では、免除は納付済より少ない
    _checks.greater(kiso_nenkin(480, 0), kiso_nenkin(0, 480),
                    "本体で全額免除480月が納付済480月以上になっている")

    # 5. 調整支給率は、帯の下端で1に限りなく近く、上端でちょうど0
    _checks.close(adjust_rate(BAND_HIGH), 0.0, "上端の調整支給率")
    _checks.close(adjust_rate(BAND_LOW), 1.0, "下端の調整支給率")

    # 6. 帯に入っても、**納付済だけの人には崖がない**（1円ぶんしか動かない）
    only_nofu = cliff_at_band_entry(FULL_MONTHS, 0)
    if only_nofu != 0:
        raise _checks.TableError(
            f"納付済だけの人の入口の崖が {only_nofu}円。0円のはず（設計どおりなら滑らか）")

    # 7. **免除のある人には崖がある。** しかも免除が長いほど深い
    _checks.increases_with(lambda m: cliff_at_band_entry(FULL_MONTHS - m, m),
                           [48, 144, 240, 336, 432],
                           "免除期間が長いのに、入口の崖が深くなっていない")

    # 8. 崖の深さは、免除分の額そのものと一致する（調整も按分もされていない）
    for menjo in (120, 240, 360):
        _checks.rounding(cliff_at_band_entry(FULL_MONTHS - menjo, menjo),
                         round(menjo_part(menjo)),
                         f"免除{menjo}月の崖の深さと免除分の額")

    # 9. 帯の中では、収入が増えると給付金は減る一方
    _checks.decreases_with(lambda i: monthly(i, 240, 240),
                           [810_000, 850_000, 890_000, 905_000],
                           "帯の中で収入が増えたのに給付金が減っていない")

    # 10. 上端をこえたら0円
    if monthly(BAND_HIGH + 1, 480, 0) != 0:
        raise _checks.TableError("基準額をこえても給付金が残っている")

    # 11. 障害1級は2級より高く、2級と遺族は同額
    _checks.greater(SHOGAI_1, SHOGAI_2, "障害1級が2級以下")
    _checks.rounding(SHOGAI_2, IZOKU, "障害2級と遺族の月額")

    _checks.assumption_values(ASSUMPTIONS, name="shienkyufu")


if __name__ == "__main__":
    check_tables()
    print("制度の値の検査: 通過")

    print("\n=== 崖を消すための帯が、免除のある人には崖を作っている ===")
    print("老齢年金生活者支援給付金は、収入が基準額をこえると出ません。")
    print(f"1円こえて丸ごと消えるのを避けるため、基準額 {BAND_HIGH:,d}円 の下に")
    print(f"**{BAND_WIDTH:,d}円の帯**（{BAND_LOW:,d}円超〜{BAND_HIGH:,d}円）が置いてあります。")
    print("この帯の中では『補足的老齢年金生活者支援給付金』が、調整支給率を掛けて出ます。")
    print("ところが調整支給率が掛かるのは**保険料納付済期間に基づく額だけ**です。")
    print("保険料免除期間に基づく額には掛かりません。**帯に入った瞬間に消えます。**")
    print()
    print("  加入480月の内訳ごとに、帯の入口（1円ふえるだけ）で何が起きるか:")
    for menjo in (0, 120, 240, 360, 480):
        nofu = FULL_MONTHS - menjo
        before = monthly(BAND_LOW, nofu, menjo)
        after = monthly(BAND_LOW + 1, nofu, menjo)
        print(f"    納付済{nofu:3d}月・免除{menjo:3d}月   "
              f"{BAND_LOW:,d}円 月{before:6,d}円 → "
              f"{BAND_LOW + 1:,d}円 月**{after:6,d}円**"
              f"（年 **{(before - after) * 12:6,d}円** 減）")
    print(f"  → **納付済だけの人は 0円しか減りません。**帯は設計どおり効いています。")
    print(f"     減るのは免除期間のある人だけで、**免除が長いほど深い。**")
    print(f"     つまり **保険料を払えなかった人ほど、深い崖を踏みます。**")

    print()
    print("=== 崖は基準額ではなく、帯の入口にある ===")
    print("「909,000円が基準額」と説明されますが、")
    print("免除期間のある人にとって、給付が大きく落ちるのは基準額ではありません。")
    print()
    print("  納付済240月・全額免除240月の人が、帯を歩いたとき:")
    print(f"    収入 {BAND_LOW:8,d}円（**帯の手前**）             "
          f"月額 **{monthly(BAND_LOW, 240, 240):6,d}円**")
    for row in band_walk(240, 240):
        print(f"    収入 {row['収入']:8,d}円   調整支給率 {row['調整支給率']:7.5f}   "
              f"月額 {row['月額']:6,d}円")
    drop = monthly(BAND_LOW, 240, 240) - monthly(BAND_LOW + 1, 240, 240)
    rest = monthly(BAND_LOW + 1, 240, 240) - monthly(BAND_HIGH, 240, 240)
    print(f"  → 入口の1円で **{drop:,d}円**、"
          f"そこから帯の {BAND_WIDTH:,d}円 かけて残り **{rest:,d}円**。")
    print(f"     **1円で落ちる額のほうが、10万円かけて落ちる額より大きい**"
          f"（{drop / rest:.2f}倍）。")

    print()
    print("=== 給付金だけを見ると、払わなかった月のほうが高い ===")
    print(f"  保険料納付済期間  月 {NOFU_UNIT:6,d}円 ÷ {FULL_MONTHS}月")
    print(f"  保険料免除期間    月 {MENJO_UNIT:6,d}円 ÷ {FULL_MONTHS}月   "
          f"← **{MENJO_UNIT / NOFU_UNIT:.3f}倍**")
    print(f"  4分の1免除だけは  月 {MENJO_UNIT_QUARTER:6,d}円 ÷ {FULL_MONTHS}月   "
          f"（ちょうど半分）")
    print("これは給付金が、老齢基礎年金の本体で免除期間が減るぶんを埋める仕組みだからです。")
    print("**本体と足すと向きが戻ります。**480月を納付済と全額免除で分けたとき:")
    print()
    print("    免除月数  納付済  本体(年)   給付金(年)   合計(年)   入口の崖(年)")
    for row in splits():
        print(f"    {row['免除月数']:6d}月  {row['納付済月数']:4d}月  "
              f"{row['本体']:8,d}円  {row['給付金']:8,d}円  "
              f"{row['合計']:9,d}円  {row['入口の崖']:8,d}円")
    top = splits()[0]
    bottom = splits()[-1]
    print(f"  → 本体は {top['本体']:,d}円 → {bottom['本体']:,d}円 と半分に落ちますが、")
    print(f"     給付金は {top['給付金']:,d}円 → {bottom['給付金']:,d}円 と"
          f"**{bottom['給付金'] / top['給付金']:.3f}倍にふえます。**")
    print(f"     合計では {top['合計']:,d}円 → {bottom['合計']:,d}円 で、"
          f"**{1 - bottom['合計'] / top['合計']:.1%} 少ない。**")
    print(f"     **穴は埋まりますが、埋まりきりません。**")

    print()
    print("=== 帯に入って落ちたぶんは、帯の中では取り返せない ===")
    print("収入が1円ふえて給付金が落ちたなら、収入をもう少しふやせば戻りそうに見えます。")
    print("ですが帯の中では、収入がふえるほど給付金は減ります。**戻る点は帯の中にありません。**")
    for nofu, menjo in ((240, 240), (360, 120), (120, 360)):
        base = BAND_LOW + monthly(BAND_LOW, nofu, menjo) * 12
        rec = recover_income(nofu, menjo)
        print(f"  納付済{nofu:3d}月・免除{menjo:3d}月:")
        print(f"    {BAND_LOW:,d}円のときの合計（収入＋給付金）  {base:9,d}円")
        if rec is None:
            print("    → 戻る収入が見つかりません")
        else:
            print(f"    → 同じ合計に戻るのは 収入 **{rec:,d}円**"
                  f"（**{rec - BAND_LOW:,d}円** ふやして、やっと元通り）")

    print()
    print("=== 障害・遺族には、この帯そのものが無い ===")
    print("同じ『年金生活者支援給付金』でも、障害と遺族には調整の帯がありません。")
    print(f"  所得基準額 {SHOTOKU_LIMIT:,d}円 —— **1円こえたら、そのまま0円です。**")
    for name, m in (("障害1級", SHOGAI_1), ("障害2級", SHOGAI_2), ("遺族", IZOKU)):
        print(f"    {name}   月 {m:5,d}円 → 年 **{m * 12:6,d}円** が"
              f"{SHOTOKU_LIMIT + 1:,d}円で消える")
    print(f"  → 老齢は {BAND_WIDTH:,d}円 かけて滑らかに落とすのに、")
    print(f"     障害1級は **年 {SHOGAI_1 * 12:,d}円** が1円で消えます。")
    print("     **同じ制度の中に、崖を消す設計と、崖のままの設計が同居しています。**")
