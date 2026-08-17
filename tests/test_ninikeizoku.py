"""`src/calc/ninikeizoku.py` の主張を、**式と数え上げの独立一致**で固定する。

`check_tables()` は値の向きを見ますが、ここで固定するのは**主張そのもの**です。

1. 「在職中の2倍」が成り立たなくなる標準報酬月額は、**率によらず上限の2倍**
2. 逆転する年収は、**世帯人数が増えるほど下がる**
3. 2人・3人の逆転は追い越しではなく、**軽減の崖で1回で飛び越える**
4. **見出しの「割」は、パーセントを10で割った値**
   （2026-08-18 にここで踏んだ。`kokuho` の「70割 → 50割」と同じ形の2件目で、
   **値は全部正しいのに字だけが違う**ので、値を見る検査では捕まりません）
"""
from __future__ import annotations

import pytest

from src.calc import kokuho, ninikeizoku as N


def test_同額になる標準報酬月額は率によらず上限の2倍():
    assert N.baisuu_ichi() == N.NINI_CAP * 2

    # 率を動かしても、同額になる点は動かない
    orig_kenpo, orig_kaigo = N.KENPO_RATE, N.KAIGO_RATE
    try:
        for kenpo, kaigo in ((0.0850, 0.0100), (0.1150, 0.0200)):
            N.KENPO_RATE, N.KAIGO_RATE = kenpo, kaigo
            nenshu = N.baisuu_ichi() * 12
            assert N.nini_premium(nenshu) == N.zaishoku_premium(nenshu), (
                f"率 {kenpo}/{kaigo} で、上限の2倍が同額になっていない")
    finally:
        N.KENPO_RATE, N.KAIGO_RATE = orig_kenpo, orig_kaigo


def test_上限より上では退職したほうが安い():
    for h in (700_000, 900_000, 1_200_000):
        nenshu = h * 12
        assert N.nini_premium(nenshu) < N.zaishoku_premium(nenshu), (
            f"標準報酬月額 {h:,} 円で、任意継続が在職中より安くなっていない")


def test_上限より上では任意継続が1円も動かない():
    got = {N.nini_premium(h * 12) for h in (400_000, 600_000, 900_000)}
    assert len(got) == 1, f"上限をこえても保険料が動いている: {sorted(got)}"


def test_逆転する年収は人数が増えるほど下がる():
    rows = N.crossover_grid()
    years = [r["逆転する年収"] for r in rows]
    assert years == sorted(years, reverse=True), years
    # 4人以上は「年収0でも任意継続が安い」。
    # **`逆転なし`（＝ crossover が None）ではありません** —— 年収0の行で
    # 既に逆転しているので、道具は 0 を返します。ここを取り違えると、
    # 印字の分岐が一度も通らないまま誤った見出しが出ます（2026-08-18 に踏んだ）。
    assert not rows[3]["逆転なし"] and not rows[4]["逆転なし"]
    assert rows[3]["全域で任意継続が安い"] and rows[4]["全域で任意継続が安い"]
    assert not rows[0]["全域で任意継続が安い"]
    # 全域で安い行は、年収0の時点で既に国保のほうが高い
    for r in rows:
        if r["全域で任意継続が安い"]:
            assert r["そこでの国保"] > r["そこでの任意継続"]


def test_1人は追い越し_2人と3人は崖で飛び越える():
    assert N.jump_at_crossover(1)["崖で飛び越えたか"] is False
    for m in (2, 3):
        j = N.jump_at_crossover(m)
        assert j["崖で飛び越えたか"] is True
        # 飛び越えた1歩で、任意継続をまたいでいる
        assert j["手前の国保"] < j["任意継続"] < j["そこでの国保"]


def test_2人の30ポイントと3人の20ポイントは同額():
    assert N.keigen_kintou(2, 30) == N.keigen_kintou(3, 20)
    # 実際に落ちたポイントも、その組み合わせになっている
    assert N.jump_at_crossover(2)["落ちたポイント"] == 30
    assert N.jump_at_crossover(3)["落ちたポイント"] == 20


def test_軽減の見出しはパーセントを10で割った値():
    """**`kokuho` の「軽減の割合」はパーセントです**（7割軽減 → 70）。

    `70割 → 50割` と刷った回が前にあります。**値は正しいので、
    値を見る検査は1件も落ちません。** ここで字のほうを固定します。
    """
    for m in (2, 3):
        j = N.jump_at_crossover(m)
        assert j["手前の軽減"] * 10 == j["手前の軽減パーセント"]
        assert j["そこでの軽減"] * 10 == j["そこでの軽減パーセント"]
        assert 0 <= j["手前の軽減"] <= 7, j["手前の軽減"]
        assert 0 <= j["そこでの軽減"] <= 7, j["そこでの軽減"]
    # 軽減の割合の取りうる値は 0 と KEIGEN_STEPS のパーセントだけ
    allowed = {0} | {pct for pct, _ in kokuho.KEIGEN_STEPS}
    assert allowed == {0, 70, 50, 20}


def test_2年目は任意継続のほうが必ず高い():
    for nenshu in (3_600_000, 4_800_000, 7_200_000):
        s = N.second_year(nenshu)
        assert s["2年目の任意継続"] > s["2年目の国保"]
        assert s["倍率"] > 10


def test_2年ぶんの合計は混ぜた選び方が最小():
    totals = N.two_year_total(4_800_000)
    mixed = next(r for r in totals if r["選び方"].startswith("1年目"))
    assert mixed["合計"] == min(r["合計"] for r in totals)


def test_40歳の壁で動くのは1人世帯の逆転点だけ():
    assert N.kaigo_wall(1)["逆転点の動き"] != 0
    for m in (2, 3):
        assert N.kaigo_wall(m)["逆転点の動き"] == 0, (
            f"{m}人世帯の逆転点は軽減の崖に固定されているはず")


@pytest.mark.parametrize("age,expect", [(39, False), (40, True), (64, True),
                                        (65, False)])
def test_介護保険料率が乗る年齢は国保と同じ範囲(age, expect):
    assert (N.rate_for(age) > N.KENPO_RATE) is expect
    assert ("介護納付金分" in kokuho.parts_for(age)) is expect


def test_check_tables_が通る():
    N.check_tables()
