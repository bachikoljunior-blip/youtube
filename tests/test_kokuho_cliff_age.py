"""`src/calc/kokuho.py` の**この回で足した2節の主張**を固定する（2026-08-18）。

節は (C)（機械の掃引が拾った形）から出しました。掃引が言っていたのは
2行だけです ——「`age` が 70 から上は 126,990 で止まる」「同 13,200 で止まる」。
**掃引は頭打ちしか見ないので、下側の台地は言いません。** 実物に当たると
形は**頭打ちではなく台形**で、そこが主張になりました。

1. **崖の高さは所得にも保険料にもよらないが、年齢にはよる** ——
   既存の節は「崖の高さは**均等割の合計 × 落ちるポイント**」で締めています。
   その均等割の合計そのものが、介護納付金分の乗る 40〜64歳だけ 16,600円 多い
2. **22歳と75歳は1円も違わない** —— 上がるのは 25年間だけで、
   65歳の誕生日にちょうど元へ戻る（片道の階段ではない）
3. **境目のほうは年齢で1円も動かない** —— 軽減の判定に入るのは所得と人数だけ。
   だから「同じ所得・同じ世帯で、1円こえたときに失う額だけが年齢で変わる」

あわせて、**この回で見つけた誤植を固定します**（`keigen_cliffs` の見出し）。
`KEIGEN_STEPS` はパーセントで持っているので、10で割らずに書くと
**`70割 → 50割`** と印字されます。**値はどれも正しいので、
既存の検査は1件も落ちませんでした** —— 画面に出る字を直に見るしかない形です。

**`check_tables()` が緑であることは、ここでは証拠になりません**
（自分を呼んで自分を確かめているだけ）。壊したときに**本当に落ちるか**は
外から壊して確かめます（`tests/test_calc_checks.py` と同じ考え方）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.calc import _checks, kokuho  # noqa: E402


def test_制度の値の検査は通る():
    kokuho.check_tables()


# ---- 1. 崖の高さは年齢で変わる -----------------------------------------

def test_介護分の乗らない年齢は崖も保険料も1円も違わない():
    rows = {r["年齢"]: r for r in kokuho.cliff_by_age(1)}
    off = [rows[a] for a in (22, 39, 65, 75)]
    for key in ("跳ぶ額", "境目での保険料", "1円こえたときの保険料"):
        assert len({r[key] for r in off}) == 1, f"{key} が年齢で違う: {off}"
    assert off[0]["跳ぶ額"] == 13_200


def test_40歳から64歳までだけ崖が高い():
    rows = {r["年齢"]: r for r in kokuho.cliff_by_age(1)}
    assert rows[40]["跳ぶ額"] == rows[64]["跳ぶ額"] == 16_520
    assert rows[39]["跳ぶ額"] == rows[65]["跳ぶ額"] == 13_200
    assert rows[40]["跳ぶ額"] > rows[39]["跳ぶ額"]


def test_上がる幅は介護分の均等割のちょうど2割():
    rows = {r["年齢"]: r for r in kokuho.cliff_by_age(1)}
    tanto = int(kokuho.RATES["介護納付金分"]["均等割"])
    assert rows[40]["跳ぶ額"] - rows[39]["跳ぶ額"] == tanto * 20 // 100 == 3_320


def test_崖の高さは人数に比例したまま年齢でも動く():
    """**2つの軸は独立です。**人数で比例し（5人まで）、年齢で 16,600円×人数×2割 増える。"""
    for members in (1, 3, 5):
        rows = {r["年齢"]: r for r in kokuho.cliff_by_age(members)}
        tanto = int(kokuho.RATES["介護納付金分"]["均等割"])
        assert rows[40]["跳ぶ額"] - rows[39]["跳ぶ額"] == tanto * members * 20 // 100


# ---- 2. 境目のほうは動かない -------------------------------------------

def test_2割の境目は年齢では1円も動かない():
    limits = {r["2割の境目"] for r in kokuho.cliff_by_age(1)}
    assert limits == {1_000_000}, limits


def test_年齢で動くのは保険料のほうだけ():
    """**軽減の判定に年齢は入りません。**入るのは所得と人数だけ。"""
    for age in (22, 39, 40, 64, 65, 75):
        assert kokuho.keigen_threshold(20, 1) == kokuho.keigen_cliff(1, age)["2割の境目"]


# ---- 3. 3つの崖の上がり幅は 20/30/20 の比 ------------------------------

def test_3つの崖の上がり幅は落ちるポイントに比例する():
    rows = kokuho.cliffs_by_age(1)
    tanto = int(kokuho.RATES["介護納付金分"]["均等割"])
    assert [r["落ちるポイント"] for r in rows] == [20, 30, 20]
    assert [r["差"] for r in rows] == [3_320, 4_980, 3_320]
    for r in rows:
        assert r["差"] == tanto * r["落ちるポイント"] // 100


def test_3つの差の合計は介護分の均等割の70パーセント():
    rows = kokuho.cliffs_by_age(1)
    tanto = int(kokuho.RATES["介護納付金分"]["均等割"])
    assert sum(r["差"] for r in rows) == tanto * 70 // 100 == 11_620


# ---- 4. 見出しの誤植（`70割 → 50割`）--------------------------------------

def test_崖の見出しは割の単位で書かれている():
    got = [c["落ちる軽減"] for c in kokuho.keigen_cliffs(1, 45)]
    assert got == ["7割 → 5割", "5割 → 2割", "2割 → なし"], got


def test_見出しにパーセントの数がそのまま出ていない():
    """**`70割` は存在しない単位です。**動画に出れば誤情報になります。"""
    for members in (1, 3):
        for age in (39, 45, 70):
            for c in kokuho.keigen_cliffs(members, age):
                assert "70割" not in c["落ちる軽減"]
                assert "50割" not in c["落ちる軽減"]
                assert "20割" not in c["落ちる軽減"]


# ---- 5. 壊したときに、検査が本当に落ちるか ------------------------------

def test_見出しを壊すと検査が落ちる(monkeypatch):
    """**この誤植は、値の検査を1件も落としませんでした。**字を見る検査だけが捕まえます。"""
    real = kokuho.keigen_cliffs

    def broken(members=1, age=45):
        rows = real(members, age)
        for r in rows:
            r["落ちる軽減"] = r["落ちる軽減"].replace("7割", "70割")
        return rows

    monkeypatch.setattr(kokuho, "keigen_cliffs", broken)
    with pytest.raises(_checks.TableError):
        kokuho.check_tables()


def _kaigo_only_at(ages):
    """`parts_for` を、**指定した年齢だけ**介護分が乗る形に差し替えて返す。"""
    def patched(age: int) -> list[str]:
        return [n for n in kokuho.RATES
                if n != "介護納付金分" or age in ages]
    return patched


NORMAL = set(range(kokuho.KAIGO_FROM, kokuho.KAIGO_TO + 1))


def test_差し替えの土台そのものは検査を通る(monkeypatch):
    """**故障注入の前に、注入の道具が無実であることを見る。**

    これが落ちると、下の2件は「壊したから落ちた」ではなく
    「差し替えたから落ちた」になり、**何も測っていないことになります。**
    """
    monkeypatch.setattr(kokuho, "parts_for", _kaigo_only_at(NORMAL))
    kokuho.check_tables()


def test_75歳にだけ介護分が乗ると落ちる(monkeypatch):
    """**既存の検査は 39歳と 65歳しか見ていません。**

    75歳を汚しても既存の8番は素通りするので、**これを捕まえるのは
    「介護分の乗らない年齢どうしは1円も違わない」の側だけ**です。
    """
    monkeypatch.setattr(kokuho, "parts_for", _kaigo_only_at(NORMAL | {75}))
    with pytest.raises(_checks.TableError):
        kokuho.check_tables()


def test_64歳だけ介護分が外れると落ちる(monkeypatch):
    """帯の**内側の端**も既存の検査の外です（8番が見るのは 40 と 64 の在否だけ）。"""
    monkeypatch.setattr(kokuho, "parts_for", _kaigo_only_at(NORMAL - {64}))
    with pytest.raises(_checks.TableError):
        kokuho.check_tables()


# ---- 6. 節が `__main__` の出力に出ていること ----------------------------

def test_節が_main_の出力に出ている():
    """**印字されていない節は、テーマになりません**（`topic_forge` は見出しで数えます）。"""
    import io
    import contextlib
    import runpy

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runpy.run_module("src.calc.kokuho", run_name="__main__")
    out = buf.getvalue()
    assert "=== 同じ所得のまま、40歳で崖が高くなり、65歳で元に戻る（単身）===" in out
    assert "=== 3つの崖は、40歳をまたぐと 20・30・20 の比で高くなる（単身）===" in out
    assert "13,200" in out and "16,520" in out and "3,320" in out
    assert "70割" not in out
