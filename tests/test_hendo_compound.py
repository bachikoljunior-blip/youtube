"""**未払利息にも利息が付く約款**（`src/calc/hendo.compound_grid`）を守る。

## なぜ足したか（2026-09-01・規則3 の improve）

`ASSUMPTIONS` の4 は 08-31 から「未払利息には利息を付けない前提で積んでいます。
**利息を付ける約款なら、この計算より大きくなります**」と言っていました。
**どの表も、いくら大きくなるかを出していません。**
自分で名指しした穴を、自分で埋めていない形です。

しかも**向きが悪い** —— 断りは「小さく出している」側なので、
読んだ人は「多少は大きいのだろう」と受け取ります。実際は:

    3.5%   410,496円 →    523,887円（**×1.28**）
    4.0% 1,094,544円 →  1,765,742円（**×1.61**）
    5.0% 4,164,960円 → **13,193,096円**（**×3.17**・借入 3,500万円 の 38%）

## この検査がいちばん言いたいこと

**止めるのに要る上乗せ額は、約款で1円も変わりません。**
`guard_grid()` の額は未払利息を **0円 に保つ**ので、
**0円 に何を掛けても 0円** —— 付ける約款でも、ちょうど足ります。

`guard_grid()` の「覆る条件」は 08-31 から**逆を書いていました**
（「この約款では、これでは足りません」）。この回に取り消しています。
**変わるのは、止めなかったときの代償だけ。**

## 覆る条件

- 未払利息に**別の**（多くは低い）利率を当てる約款を出すようになったら、
  `simulate()` に利率をもう1つ渡すこと（いまは同じ利率を乗せています）
- 前提（`PRINCIPAL` / `YEARS` / `START_RATE` / `RISE_AT`）を変えたら、
  上の実測は動きます。**そのときは測り直して、ここも動画も直すこと**
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.calc import hendo  # noqa: E402


def test_既定は今までどおり利息を付けない() -> None:
    """**保存済みの数を1つも動かしていないこと。** 動画の台本がこれで焼かれています。"""
    path = ((0, hendo.START_RATE), (hendo.RISE_AT, 0.040))
    got = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path)
    assert got["unpaid"] == 1_094_544
    assert got["balloon"] == 1_094_544


def test_付ける約款のほうが必ず重い() -> None:
    for row in hendo.compound_grid():
        assert row["付ける約款の一括"] > row["付けない約款の一括"], row


def test_未払利息が積まない金利では約款の差も出ない() -> None:
    """**差は未払利息にしか乗りません。** 積まない金利では 1円も変わらない。"""
    path = ((0, hendo.START_RATE), (hendo.RISE_AT, 0.030))
    a = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path)
    b = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path, compound_unpaid=True)
    assert a["unpaid"] == 0
    assert b["unpaid"] == 0
    assert a["total"] == b["total"]


def test_止めるのに要る上乗せは約款で変わらない() -> None:
    """`guard_grid()` の「覆る条件」が 08-31 から**逆**を書いていた所。

    **0円 に何を掛けても 0円** —— 未払利息を 0 に保つ額は、
    利息を付ける約款でもちょうど足ります。
    """
    for row in hendo.guard_grid():
        if row["要る上乗せ"] <= 0:
            continue
        rate = float(row["上がった先の年利"].rstrip("%")) / 100
        bal, unpaid, pay = hendo.PRINCIPAL, 0, row["上乗せ後の毎月"]
        for m in range(hendo.YEARS * hendo.MONTHS_PER_YEAR):
            r_m = hendo.rate_at(m, ((0, hendo.START_RATE), (hendo.RISE_AT, rate)))
            interest = hendo.interest_of(bal + unpaid, r_m)
            if pay >= interest:
                bal -= min(pay - interest, bal)
            else:
                unpaid += interest - pay
            if bal <= 0:
                break
        assert unpaid == 0, (row["上がった先の年利"], unpaid)


def test_5パーセントでは残高が返し切れずに残る() -> None:
    """付けない約款では残高 0円（一括は未払利息だけ）。付ける約款では残ります ——
    **未払利息が複利で増え、毎月の返済が利息に食われるから。**"""
    path = ((0, hendo.START_RATE), (hendo.RISE_AT, 0.050))
    a = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path)
    b = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path, compound_unpaid=True)
    assert a["balloon"] - a["unpaid"] == 0
    assert b["balloon"] - b["unpaid"] > 0


def test_保存則は付ける約款でも成り立つ() -> None:
    """払った総額 ＝ 元金 ＋ 利息（上下 1円 まで）。`check_tables()` の 9 と同じ形。"""
    for rate in (0.035, 0.040, 0.050):
        path = ((0, hendo.START_RATE), (hendo.RISE_AT, rate))
        got = hendo.simulate(hendo.PRINCIPAL, hendo.YEARS, path,
                             compound_unpaid=True)
        interest_sum = sum(r["利息"] for r in got["rows"])
        assert abs(got["total"] - (hendo.PRINCIPAL + interest_sum)) <= 1, rate


def test_行が重なっていない() -> None:
    seen = [r["上がった先"] for r in hendo.compound_grid()]
    assert len(seen) == len(set(seen))


def test_check_tablesがcompound_gridを見ている() -> None:
    import inspect
    src = inspect.getsource(hendo.check_tables)
    assert "compound_grid(" in src, "check_tables が新しい表を突き合わせていない"


def test_mainがcompound_gridを印字する() -> None:
    """**印字されない表は、台本に届きません**（`script_writer.calc_block()` は
    `python -m src.calc.<名前>` の標準出力を読みます）。"""
    import inspect
    src = inspect.getsource(hendo.main)
    assert "compound_grid()" in src, "main が新しい表を出していない"


def test_前提の4番が数を持っている() -> None:
    """**自分で名指しした穴を、自分で埋めること。**「大きくなります」だけでは、
    読んだ人は『多少は』と受け取ります（実測は ×1.61〜×3.17）。"""
    line = [a for a in hendo.ASSUMPTIONS if "未払利息には利息を付けない" in a]
    assert line, "前提の4番が消えている"
    assert "1.61倍" in line[0] and "3.17倍" in line[0], line[0]
    assert "同じ" in line[0], "『上乗せ額は約款で変わらない』が抜けている"


def test_guard_gridの覆る条件は取り消されている() -> None:
    """08-31 の版は「この約款では、これでは足りません」と**逆**を書いていました。"""
    doc = hendo.guard_grid.__doc__ or ""
    assert "誤りでした" in doc, "取り消しの跡が消えている"
    assert "0円 に何を掛けても 0円" in doc, "取り消した理由が書かれていない"
