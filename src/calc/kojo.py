"""申告し漏れた所得控除が、実際いくら戻るのかを計算する。

狙いは控除の一覧を並べることではない。一覧はどこにでもある。
ここで出したいのは **広く出回っている計算が、どれだけ多めに出ているか** ——
その差額を、控除ごと・税率ごとに全部表にする。

--------------------------------------------------------------------------
何が違うのか
--------------------------------------------------------------------------
よく見る計算は「控除額 × (所得税率 + 住民税率10%)」。
これは **所得税と住民税で控除額が同じ** ことを前提にしている。

ところが多くの所得控除は、**所得税と住民税で額が違う**。
たとえば一般の扶養控除は所得税38万円だが住民税は33万円。
地震保険料控除は所得税で最高5万円だが住民税では最高2万5千円しかない。

つまり住民税側は、所得税側より小さい控除額で計算しなければならない。
同じ額で計算すると、その差の10%ぶんだけ多めに出る。

--------------------------------------------------------------------------
もう一つの区別
--------------------------------------------------------------------------
「戻る」と一括りにされがちだが、中身は二つに分かれる。

  所得税 … すでに源泉徴収された分から **現金で還付される**
  住民税 … 翌年度に課される額が **減る**（現金は戻ってこない）

手元に現金が入るのは所得税ぶんだけ。ここも分けて出す。

--------------------------------------------------------------------------
根拠
--------------------------------------------------------------------------
所得税法・地方税法の各控除の規定。復興特別所得税は所得税額の2.1%。
住民税の所得割は標準税率10%（市町村6%・道府県4%）。

ここに置いた控除額は、長く動いていないものだけを選んでいる。
令和8年度の改正で動くもの（生命保険料控除の子育て世帯の上乗せ、ひとり親控除など）は、
確定した数字を確認できるまで入れない。裏の取れない数字は出さない。
"""
from __future__ import annotations

from dataclasses import dataclass

ASSUMPTIONS = [
    "所得税は復興特別所得税を含めています。所得税額の2.1パーセント上乗せです",
    "住民税の所得割は標準税率の10パーセントで計算しています",
    "所得税ぶんは現金で還付され、住民税ぶんは翌年度の税額が減る形です",
    "控除額が所得税と住民税で違うものは、それぞれの額で計算しています",
    "令和8年度の改正で動く控除は、確定した数字を確認できるまで入れていません",
]

RECONSTRUCTION_TAX = 0.021   # 復興特別所得税。所得税額に対して
RESIDENT_RATE = 0.10         # 住民税の所得割の標準税率

# 所得税の速算表の税率。課税所得の区分ごと。
INCOME_TAX_RATES = [0.05, 0.10, 0.20, 0.23, 0.33, 0.40, 0.45]

# 更正の請求ができる期間。申告期限から5年。
YEARS_RECLAIMABLE = 5


@dataclass(frozen=True)
class Deduction:
    """所得控除。所得税と住民税で額が違うことがある。"""

    name: str
    income_tax: int      # 所得税の控除額
    resident_tax: int    # 住民税の控除額

    @property
    def gap(self) -> int:
        """所得税と住民税の控除額の差。ここが誤りの発生源。"""
        return self.income_tax - self.resident_tax


# 長く動いていない控除だけを選んでいる。
DEDUCTIONS = [
    Deduction("障害者控除", 270_000, 260_000),
    Deduction("特別障害者控除", 400_000, 300_000),
    Deduction("同居特別障害者控除", 750_000, 530_000),
    Deduction("一般の扶養控除", 380_000, 330_000),
    Deduction("特定扶養控除", 630_000, 450_000),
    Deduction("老人扶養控除 同居老親等", 580_000, 450_000),
    Deduction("老人扶養控除 その他", 480_000, 380_000),
    Deduction("地震保険料控除 最高額", 50_000, 25_000),
]


class TableError(AssertionError):
    """表そのものが壊れている。数字を出す前に止める。"""


def check_tables() -> None:
    """控除の表が壊れていないことを、性質から確かめる。

    公表資料の読み取りは実際に列がずれたことがある（JOURNAL.md 参照）。
    ずれた表はもっともらしい数字を出すので、目視では気づけない。
    """
    seen = set()
    for d in DEDUCTIONS:
        if d.name in seen:
            raise TableError(f"{d.name} が重複しています")
        seen.add(d.name)

        # 1. 住民税の控除額が所得税を超えることはない
        if d.resident_tax > d.income_tax:
            raise TableError(f"{d.name}: 住民税の控除額が所得税を超えています")
        # 2. どちらも正の額
        if d.income_tax <= 0 or d.resident_tax <= 0:
            raise TableError(f"{d.name}: 控除額が0以下です")
        # 3. 桁の取り違え（万円と円）を弾く
        if not 10_000 <= d.income_tax <= 1_000_000:
            raise TableError(f"{d.name}: 所得税の控除額の桁がおかしい")

    # 4. 特別障害者は障害者より大きい、といった大小関係
    by_name = {d.name: d for d in DEDUCTIONS}
    if by_name["特別障害者控除"].income_tax <= by_name["障害者控除"].income_tax:
        raise TableError("特別障害者控除が障害者控除以下です")
    if by_name["特定扶養控除"].income_tax <= by_name["一般の扶養控除"].income_tax:
        raise TableError("特定扶養控除が一般の扶養控除以下です")

    if not 0 < RESIDENT_RATE < 1:
        raise TableError("住民税率がおかしい")


def refund(d: Deduction, rate: float) -> dict:
    """その控除を申告したときに、実際にいくら変わるか。

    rate は所得税の税率（速算表の区分）。
    """
    income = int(d.income_tax * rate * (1 + RECONSTRUCTION_TAX))
    resident = int(d.resident_tax * RESIDENT_RATE)
    # よく見る計算：住民税側も所得税の控除額で計算してしまう
    naive_resident = int(d.income_tax * RESIDENT_RATE)
    return {
        "name": d.name,
        "rate": rate,
        "income_tax_refund": income,      # 現金で戻る
        "resident_tax_cut": resident,     # 翌年度の負担が減る
        "total": income + resident,
        "naive_total": income + naive_resident,
        "overstated_by": naive_resident - resident,
        "five_years": (income + resident) * YEARS_RECLAIMABLE,
    }


def table(rate: float) -> list[dict]:
    """ある税率のとき、控除ごとにいくらになるか。"""
    check_tables()
    return [refund(d, rate) for d in DEDUCTIONS]


def by_rate(name: str) -> list[dict]:
    """ある控除について、税率ごとにいくらになるか。"""
    check_tables()
    d = next(x for x in DEDUCTIONS if x.name == name)
    return [refund(d, r) for r in INCOME_TAX_RATES]
